"""VeighNa bar and tick storage on Apache IoTDB's Tree model."""

from __future__ import annotations

import base64
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from zoneinfo import ZoneInfo

from iotdb.Session import Session
from iotdb.SessionPool import PoolConfig, SessionPool
from iotdb.utils.IoTDBConstants import TSDataType
from iotdb.utils.Tablet import Tablet
from iotdb.utils.exception import StatementExecutionException

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import BaseDatabase, BarOverview, DB_TZ, TickOverview
from vnpy.trader.object import BarData, TickData
from vnpy.trader.setting import SETTINGS


BAR_MEASUREMENTS: tuple[str, ...] = (
    "volume",
    "turnover",
    "open_interest",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
)
TICK_VALUE_MEASUREMENTS: tuple[str, ...] = (
    "volume",
    "turnover",
    "open_interest",
    "last_price",
    "last_volume",
    "limit_up",
    "limit_down",
    "open_price",
    "high_price",
    "low_price",
    "pre_close",
    "bid_price_1",
    "bid_price_2",
    "bid_price_3",
    "bid_price_4",
    "bid_price_5",
    "ask_price_1",
    "ask_price_2",
    "ask_price_3",
    "ask_price_4",
    "ask_price_5",
    "bid_volume_1",
    "bid_volume_2",
    "bid_volume_3",
    "bid_volume_4",
    "bid_volume_5",
    "ask_volume_1",
    "ask_volume_2",
    "ask_volume_3",
    "ask_volume_4",
    "ask_volume_5",
)
TICK_MEASUREMENTS: tuple[str, ...] = ("name", *TICK_VALUE_MEASUREMENTS, "localtime")
_DOUBLE: TSDataType = TSDataType.DOUBLE
_SEGMENT_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EPOCH: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)


class IoTDBDatabase(BaseDatabase):
    """Store VeighNa bars and ticks as Tree-model device measurements."""

    def __init__(self) -> None:
        self.host: str = str(SETTINGS["database.host"])
        self.port: str = str(SETTINGS["database.port"])
        self.user: str = str(SETTINGS["database.user"])
        self.password: str = str(SETTINGS["database.password"])
        self.timezone: str = str(SETTINGS["database.timezone"])
        self.database: str = _database_path(str(SETTINGS["database.database"]))
        pool_size: int = int(SETTINGS.get("database.iotdb.pool_size", 5))
        wait_timeout: int = int(SETTINGS.get("database.iotdb.wait_timeout_ms", 30000))
        self.query_timeout: int = int(SETTINGS.get("database.iotdb.query_timeout_ms", 30000))

        config: PoolConfig = PoolConfig(
            host=self.host,
            port=self.port,
            user_name=self.user,
            password=self.password,
            time_zone=self.timezone,
            connection_timeout_in_ms=wait_timeout,
        )
        self.pool: SessionPool = SessionPool(config, pool_size, wait_timeout)
        self.pool.sql_dialect = "tree"

        try:
            with self._session() as session:
                try:
                    session.execute_non_query_statement(f"CREATE DATABASE {self.database}")
                except StatementExecutionException as exc:
                    if not str(exc).startswith("501:"):
                        raise
        except Exception:
            self.pool.close()
            raise

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session: Session = self.pool.get_session()
        try:
            yield session
        finally:
            self.pool.put_back(session)

    def close(self) -> None:
        """Close pooled IoTDB sessions when the application shuts down."""
        self.pool.close()

    def save_bar_data(self, bars: list[BarData], stream: bool = False) -> bool:
        if not bars:
            return True

        first: BarData = bars[0]
        interval: Interval = _required_interval(first.interval)
        _validate_bar_batch(bars, first, interval)
        device: str = self._bar_device(first.symbol, first.exchange, interval)
        types: list[TSDataType] = [_DOUBLE] * len(BAR_MEASUREMENTS)

        with self._session() as session:
            for batch in _chunks(bars, 1000):
                values: list[list[object]] = [
                    [float(getattr(bar, name)) for name in BAR_MEASUREMENTS]
                    for bar in batch
                ]
                tablet: Tablet = Tablet(
                    device,
                    list(BAR_MEASUREMENTS),
                    types,
                    values,
                    [_datetime_to_milliseconds(bar.datetime, self.timezone) for bar in batch],
                )
                session.insert_tablet(tablet)
        return True

    def save_tick_data(self, ticks: list[TickData], stream: bool = False) -> bool:
        if not ticks:
            return True

        first: TickData = ticks[0]
        _validate_tick_batch(ticks, first)
        device: str = self._tick_device(first.symbol, first.exchange)
        types: list[TSDataType] = [
            TSDataType.STRING,
            *([_DOUBLE] * len(TICK_VALUE_MEASUREMENTS)),
            TSDataType.INT64,
        ]

        with self._session() as session:
            for batch in _chunks(ticks, 1000):
                values: list[list[object]] = []
                timestamps: list[int] = []
                for tick in batch:
                    localtime: datetime = tick.localtime or tick.datetime
                    values.append(
                        [
                            tick.name,
                            *[float(getattr(tick, name)) for name in TICK_VALUE_MEASUREMENTS],
                            _datetime_to_milliseconds(localtime, self.timezone),
                        ]
                    )
                    timestamps.append(_datetime_to_milliseconds(tick.datetime, self.timezone))

                tablet: Tablet = Tablet(
                    device,
                    list(TICK_MEASUREMENTS),
                    types,
                    values,
                    timestamps,
                )
                session.insert_tablet(tablet)
        return True

    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> list[BarData]:
        device: str = self._bar_device(symbol, exchange, interval)
        sql: str = _select_sql(
            BAR_MEASUREMENTS,
            device,
            start,
            end,
            self.timezone,
        )
        bars: list[BarData] = []

        with self._session() as session:
            for timestamp, values in _query_rows(session, sql, self.query_timeout):
                fields: dict[str, float] = {
                    name: _as_float(value)
                    for name, value in zip(BAR_MEASUREMENTS, values, strict=True)
                }
                bars.append(
                    BarData(
                        symbol=symbol,
                        exchange=exchange,
                        datetime=_row_datetime(timestamp, self.timezone),
                        interval=interval,
                        gateway_name="DB",
                        **fields,
                    )
                )
        return bars

    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime,
    ) -> list[TickData]:
        device: str = self._tick_device(symbol, exchange)
        sql: str = _select_sql(TICK_MEASUREMENTS, device, start, end, self.timezone)
        ticks: list[TickData] = []

        with self._session() as session:
            for timestamp, values in _query_rows(session, sql, self.query_timeout):
                name: str = _as_string(values[0])
                tick_values: dict[str, float] = {
                    key: _as_float(value)
                    for key, value in zip(TICK_VALUE_MEASUREMENTS, values[1:-1], strict=True)
                }
                localtime: datetime | None = _row_datetime_or_none(values[-1], self.timezone)
                ticks.append(
                    TickData(
                        symbol=symbol,
                        exchange=exchange,
                        datetime=_row_datetime(timestamp, self.timezone),
                        name=name,
                        localtime=localtime,
                        gateway_name="DB",
                        **tick_values,
                    )
                )
        return ticks

    def delete_bar_data(self, symbol: str, exchange: Exchange, interval: Interval) -> int:
        device: str = self._bar_device(symbol, exchange, interval)
        with self._session() as session:
            count: int = self._count_device_rows(session, device, "open_price")
            if count:
                session.execute_non_query_statement(
                    f"DELETE FROM {device}.** WHERE time >= -9223372036854775807"
                )
        return count

    def delete_tick_data(self, symbol: str, exchange: Exchange) -> int:
        device: str = self._tick_device(symbol, exchange)
        with self._session() as session:
            count: int = self._count_device_rows(session, device, "last_price")
            if count:
                session.execute_non_query_statement(
                    f"DELETE FROM {device}.** WHERE time >= -9223372036854775807"
                )
        return count

    def get_bar_overview(self) -> list[BarOverview]:
        with self._session() as session:
            devices: set[str] = self._list_devices(session, "bars")
            overviews: list[BarOverview] = []
            for device in sorted(devices):
                symbol, exchange, interval = self._decode_bar_device(device)
                stats: tuple[int, datetime, datetime] | None = self._device_stats(
                    session, device, "open_price"
                )
                if stats is None:
                    continue
                count, start, end = stats
                overviews.append(
                    BarOverview(
                        symbol=symbol,
                        exchange=Exchange(exchange),
                        interval=Interval(interval),
                        start=start,
                        end=end,
                        count=count,
                    )
                )
        return overviews

    def get_tick_overview(self) -> list[TickOverview]:
        with self._session() as session:
            devices: set[str] = self._list_devices(session, "ticks")
            overviews: list[TickOverview] = []
            for device in sorted(devices):
                symbol, exchange = self._decode_tick_device(device)
                stats: tuple[int, datetime, datetime] | None = self._device_stats(
                    session, device, "last_price"
                )
                if stats is None:
                    continue
                count, start, end = stats
                overviews.append(
                    TickOverview(
                        symbol=symbol,
                        exchange=Exchange(exchange),
                        start=start,
                        end=end,
                        count=count,
                    )
                )
        return overviews

    def _bar_device(self, symbol: str, exchange: Exchange, interval: Interval) -> str:
        return ".".join(
            (
                self.database,
                "bars",
                _encode_component(symbol),
                _encode_component(exchange.value),
                _encode_component(interval.value),
            )
        )

    def _tick_device(self, symbol: str, exchange: Exchange) -> str:
        return ".".join(
            (self.database, "ticks", _encode_component(symbol), _encode_component(exchange.value))
        )

    def _list_devices(self, session: Session, data_kind: str) -> set[str]:
        pattern: str = f"SHOW TIMESERIES {self.database}.{data_kind}.**"
        result: set[str] = set()
        for _timestamp, fields in _query_rows(session, pattern, self.query_timeout):
            if not fields or fields[0] is None:
                continue
            path: str = _as_string(fields[0])
            prefix: str = f"{self.database}.{data_kind}."
            if path.startswith(prefix):
                result.add(".".join(path.split(".")[:-1]))
        return result

    def _decode_bar_device(self, device: str) -> tuple[str, str, str]:
        parts: list[str] = device.split(".")
        return (
            _decode_component(parts[-3]),
            _decode_component(parts[-2]),
            _decode_component(parts[-1]),
        )

    def _decode_tick_device(self, device: str) -> tuple[str, str]:
        parts: list[str] = device.split(".")
        return _decode_component(parts[-2]), _decode_component(parts[-1])

    def _device_stats(
        self,
        session: Session,
        device: str,
        measurement: str,
    ) -> tuple[int, datetime, datetime] | None:
        sql: str = (
            f"SELECT COUNT({measurement}), MIN_TIME({measurement}), MAX_TIME({measurement}) "
            f"FROM {device}"
        )
        rows: list[tuple[object, list[object]]] = _query_rows(
            session, sql, self.query_timeout
        )
        if not rows:
            return None
        values: list[object] = rows[0][1]
        count: int = _as_int(values[0])
        if count == 0 or values[1] is None or values[2] is None:
            return None
        return (
            count,
            _row_datetime(values[1], self.timezone),
            _row_datetime(values[2], self.timezone),
        )

    def _count_device_rows(self, session: Session, device: str, measurement: str) -> int:
        sql: str = f"SELECT COUNT({measurement}) FROM {device}"
        rows: list[tuple[object, list[object]]] = _query_rows(
            session, sql, self.query_timeout
        )
        if not rows or not rows[0][1]:
            return 0
        return _as_int(rows[0][1][0])


def _database_path(database: str) -> str:
    value: str = database if database.startswith("root.") else f"root.{database}"
    parts: list[str] = value.split(".")
    if len(parts) < 2 or parts[0] != "root" or any(
        not _SEGMENT_PATTERN.fullmatch(part) for part in parts[1:]
    ):
        raise ValueError("database.database must be a valid IoTDB Tree database path")
    return value


def _encode_component(value: str) -> str:
    encoded: str = base64.b32encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return f"s{encoded}"


def _decode_component(value: str) -> str:
    encoded: str = value[1:]
    encoded += "=" * ((8 - len(encoded) % 8) % 8)
    return base64.b32decode(encoded).decode("utf-8")


def _required_interval(interval: Interval | None) -> Interval:
    if interval is None:
        raise ValueError("BarData.interval is required")
    return interval


def _validate_bar_batch(bars: Sequence[BarData], first: BarData, interval: Interval) -> None:
    if any(
        bar.symbol != first.symbol
        or bar.exchange != first.exchange
        or bar.interval != interval
        for bar in bars
    ):
        raise ValueError("A bar batch must contain one symbol, exchange, and interval")


def _validate_tick_batch(ticks: Sequence[TickData], first: TickData) -> None:
    if any(tick.symbol != first.symbol or tick.exchange != first.exchange for tick in ticks):
        raise ValueError("A tick batch must contain one symbol and exchange")


def _chunks(items: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _datetime_to_milliseconds(value: datetime, timezone_name: str) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    delta: timedelta = value.astimezone(timezone.utc) - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _row_datetime(value: object, timezone_name: str) -> datetime:
    if isinstance(value, datetime):
        result: datetime = value
        if result.tzinfo is None:
            result = result.replace(tzinfo=ZoneInfo(timezone_name))
        return result.astimezone(DB_TZ)
    if value is None:
        raise ValueError("IoTDB returned a null timestamp")
    return datetime.fromtimestamp(_as_int(value) / 1000, timezone.utc).astimezone(DB_TZ)


def _row_datetime_or_none(value: object, timezone_name: str) -> datetime | None:
    if value is None:
        return None
    return _row_datetime(value, timezone_name)


def _select_sql(
    measurements: Sequence[str],
    device: str,
    start: datetime,
    end: datetime,
    timezone_name: str,
) -> str:
    start_ms: int = _datetime_to_milliseconds(start, timezone_name)
    end_ms: int = _datetime_to_milliseconds(end, timezone_name)
    columns: str = ", ".join(measurements)
    return f"SELECT {columns} FROM {device} WHERE time >= {start_ms} AND time <= {end_ms}"


def _query_rows(
    session: Session,
    sql: str,
    timeout: int,
) -> list[tuple[object, list[object]]]:
    result: Any = session.execute_query_statement(sql, timeout=timeout)
    rows: list[tuple[object, list[object]]] = []
    try:
        while result.has_next():
            row: Any = result.next()
            if row is None:
                break
            fields: list[object] = [field.value for field in row.get_fields()]
            rows.append((row.get_timestamp(), fields))
    finally:
        result.close_operation_handle()
    return rows


def _as_float(value: object) -> float:
    return float(cast(Any, value)) if value is not None else 0.0


def _as_int(value: object) -> int:
    return int(cast(Any, value)) if value is not None else 0


def _as_string(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
