from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid
from typing import Any

import pytest

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import DB_TZ
from vnpy.trader.object import BarData, TickData

from vnpy_iotdb import iotdb_database as iotdb_db
from vnpy_iotdb.iotdb_database import IoTDBDatabase


@pytest.mark.skipif(not os.getenv('IOTDB_TEST_PORT'), reason='requires an isolated Tree RPC endpoint')
def test_live_market_data(monkeypatch):
    name = 'root.vnpy_' + uuid.uuid4().hex
    for key, value in {'host': '127.0.0.1', 'port': os.environ['IOTDB_TEST_PORT'],
                       'database': name, 'user': os.environ['IOTDB_TEST_USER'],
                       'password': os.environ['IOTDB_TEST_PASSWORD']}.items():
        monkeypatch.setitem(iotdb_db.SETTINGS, 'database.' + key, value)
    db = IoTDBDatabase()
    try:
        bar, tick = _bar(), _tick()
        assert db.save_bar_data([bar]) and db.save_tick_data([tick])
        bars = db.load_bar_data(bar.symbol, bar.exchange, bar.interval, bar.datetime, bar.datetime)
        ticks = db.load_tick_data(tick.symbol, tick.exchange, tick.datetime, tick.datetime)
        assert len(bars) == len(ticks) == 1
        assert bars[0].close_price == bar.close_price and ticks[0].last_price == tick.last_price
        assert db.get_bar_overview()[0].count == db.get_tick_overview()[0].count == 1
        assert db.delete_bar_data(bar.symbol, bar.exchange, bar.interval) == db.delete_tick_data(tick.symbol, tick.exchange) == 1
    finally:
        try:
            with db._session() as session:
                session.execute_non_query_statement('DROP DATABASE ' + name)
        finally:
            db.close()


class _Field:
    def __init__(self, value: object) -> None:
        self.value = value


class _Row:
    def __init__(self, timestamp: object, values: list[object]) -> None:
        self.timestamp = timestamp
        self.values = values

    def get_timestamp(self) -> object:
        return self.timestamp

    def get_fields(self) -> list[_Field]:
        return [_Field(value) for value in self.values]


class _DataSet:
    def __init__(self, rows: list[_Row]) -> None:
        self.rows = rows
        self.index = 0
        self.closed = False

    def has_next(self) -> bool:
        return self.index < len(self.rows)

    def next(self) -> _Row | None:
        row = self.rows[self.index]
        self.index += 1
        return row

    def close_operation_handle(self) -> None:
        self.closed = True


class _Session:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.queries: list[str] = []
        self.tablets: list[_FakeTablet] = []
        self.query_handler: Any = lambda _sql: []
        self.results: list[_DataSet] = []

    def execute_non_query_statement(self, sql: str) -> None:
        self.statements.append(sql)

    def execute_query_statement(self, sql: str, timeout: int = 0) -> _DataSet:
        self.queries.append(sql)
        rows = self.query_handler(sql)
        result = _DataSet(rows)
        self.results.append(result)
        return result

    def insert_tablet(self, tablet: _FakeTablet) -> None:
        self.tablets.append(tablet)


class _Pool:
    def __init__(self) -> None:
        self.session = _Session()
        self.sql_dialect = ""
        self.put_back_count = 0
        self.closed = False

    def get_session(self) -> _Session:
        return self.session

    def put_back(self, _session: _Session) -> None:
        self.put_back_count += 1

    def close(self) -> None:
        self.closed = True


class _FakeTablet:
    def __init__(
        self,
        device: str,
        measurements: list[str],
        types: list[object],
        values: list[list[object]],
        timestamps: list[int],
    ) -> None:
        self.device = device
        self.measurements = measurements
        self.types = types
        self.values = values
        self.timestamps = timestamps


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> IoTDBDatabase:
    monkeypatch.setattr(iotdb_db, "Tablet", _FakeTablet)
    db: IoTDBDatabase = IoTDBDatabase.__new__(IoTDBDatabase)
    db.host = "localhost"
    db.port = "6667"
    db.user = "user"
    db.password = "password"
    db.timezone = "Asia/Shanghai"
    db.database = "root.vnpy_test"
    db.query_timeout = 1234
    db.pool = _Pool()
    return db


def _bar(symbol: str = "rb-main") -> BarData:
    return BarData(
        gateway_name="TEST",
        symbol=symbol,
        exchange=Exchange.SHFE,
        datetime=datetime(2024, 1, 15, 10, 0, tzinfo=DB_TZ),
        interval=Interval.MINUTE,
        volume=12.0,
        turnover=1.5,
        open_interest=3.0,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
    )


def _tick() -> TickData:
    return TickData(
        gateway_name="TEST",
        symbol="au-main",
        exchange=Exchange.SHFE,
        datetime=datetime(2024, 1, 16, 10, 0, tzinfo=DB_TZ),
        localtime=datetime(2024, 1, 16, 10, 0, 0, 123000, tzinfo=DB_TZ),
        name="黄金",
        last_price=400.5,
        last_volume=2.0,
        volume=20.0,
        bid_price_1=400.0,
        ask_price_1=401.0,
    )


def test_save_uses_path_safe_devices_and_tablet_batches(database: IoTDBDatabase) -> None:
    bars: list[BarData] = [_bar(), _bar()]
    assert database.save_bar_data(bars) is True

    tablet: _FakeTablet = database.pool.session.tablets[0]
    assert tablet.device.startswith("root.vnpy_test.bars.s")
    assert tablet.measurements == list(iotdb_db.BAR_MEASUREMENTS)
    assert tablet.values[0] == [12.0, 1.5, 3.0, 100.0, 110.0, 90.0, 105.0]
    assert tablet.timestamps == [1705284000000, 1705284000000]
    assert database.pool.put_back_count == 1

    assert database.save_tick_data([_tick()]) is True
    tick_tablet: _FakeTablet = database.pool.session.tablets[1]
    assert tick_tablet.measurements[0] == "name"
    assert tick_tablet.values[0][0] == "黄金"
    assert tick_tablet.values[0][-1] == 1705370400123


def test_rejects_mixed_symbols_in_one_batch(database: IoTDBDatabase) -> None:
    with pytest.raises(ValueError, match="one symbol"):
        database.save_bar_data([_bar("rb"), _bar("cu")])


def test_load_bar_data_converts_timestamp_and_uses_bounds(database: IoTDBDatabase) -> None:
    stored_datetime: datetime = datetime(2024, 1, 15, 10, 0, tzinfo=DB_TZ)
    database.pool.session.query_handler = lambda _sql: [
        _Row(
            1705284000000,
            [12.0, 1.5, 3.0, 100.0, 110.0, 90.0, 105.0],
        )
    ]
    start: datetime = datetime(2024, 1, 1, tzinfo=DB_TZ)
    end: datetime = datetime(2024, 2, 1, tzinfo=DB_TZ)

    bars: list[BarData] = database.load_bar_data(
        "rb-main", Exchange.SHFE, Interval.MINUTE, start, end
    )

    assert len(bars) == 1
    assert bars[0].datetime == stored_datetime
    assert bars[0].symbol == "rb-main"
    assert bars[0].close_price == 105.0
    assert bars[0].gateway_name == "DB"
    assert "time >= 1704038400000" in database.pool.session.queries[0]
    assert "time <= 1706716800000" in database.pool.session.queries[0]
    assert database.pool.session.results[0].closed is True


def test_overview_decodes_paths_and_counts_points(database: IoTDBDatabase) -> None:
    device: str = database._bar_device("rb.main-主力", Exchange.SHFE, Interval.MINUTE)
    series_path: str = f"{device}.open_price"
    another_series: str = f"{device}.close_price"
    start_ms: int = 1705284000000
    end_ms: int = 1705284060000

    def query(sql: str) -> list[_Row]:
        if sql.startswith("SHOW TIMESERIES"):
            return [_Row(0, [series_path]), _Row(0, [another_series])]
        if sql.startswith("SELECT COUNT(open_price)"):
            return [_Row(0, [2, start_ms, end_ms])]
        return []

    database.pool.session.query_handler = query
    overviews = database.get_bar_overview()

    assert len(overviews) == 1
    assert overviews[0].symbol == "rb.main-主力"
    assert overviews[0].exchange == Exchange.SHFE
    assert overviews[0].interval == Interval.MINUTE
    assert overviews[0].count == 2
    assert overviews[0].start == datetime.fromtimestamp(start_ms / 1000, timezone.utc).astimezone(DB_TZ)
    assert overviews[0].end == datetime.fromtimestamp(end_ms / 1000, timezone.utc).astimezone(DB_TZ)


def test_delete_counts_then_removes_all_timestamps(database: IoTDBDatabase) -> None:
    database.pool.session.query_handler = lambda _sql: [_Row(0, [3])]

    count: int = database.delete_tick_data("au-main", Exchange.SHFE)

    assert count == 3
    statements: list[str] = database.pool.session.statements
    assert statements == [
        "DELETE FROM " + database._tick_device("au-main", Exchange.SHFE) + ".** "
        "WHERE time >= -9223372036854775807"
    ]
