import importlib
import sys
import types
from datetime import datetime

import pandas as pd
import pytest

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import DB_TZ
from vnpy.trader.object import BarData, TickData
from vnpy.trader.setting import SETTINGS


# taospy 在没有客户端动态库时 import 会抛 InterfaceError，模块缺失时则是 ImportError。
# 两种失败都换成不发起连接的模块，测试再替换 connect。
def _prepare_taos() -> None:
    try:
        importlib.import_module("taos")
    except Exception:
        for name in list(sys.modules):
            if name == "taos" or name.startswith("taos."):
                del sys.modules[name]
        module: types.ModuleType = types.ModuleType("taos")

        def connect(**_kwargs: object) -> object:
            raise AssertionError("taos.connect was not patched")

        module.connect = connect
        sys.modules["taos"] = module


_prepare_taos()

SETTINGS["database.database"] = "vnpy_test"
SETTINGS["database.host"] = "127.0.0.1"
SETTINGS["database.port"] = 6030
SETTINGS["database.user"] = "root"
SETTINGS["database.password"] = "taosdata"
SETTINGS["database.timezone"] = "Asia/Shanghai"

from vnpy_taos.taos_database import TaosDatabase  # noqa: E402
from vnpy_taos.taos_script import (  # noqa: E402
    CREATE_BAR_TABLE_SCRIPT,
    CREATE_DATABASE_SCRIPT,
    CREATE_TICK_TABLE_SCRIPT,
)
import vnpy_taos.taos_database as taos_db  # noqa: E402


statements: list[str] = []
read_sqls: list[str] = []
next_frames: list[pd.DataFrame] = []
connect_kwargs: dict[str, object] = {}
init_sql: list[str] = []


class _Cursor:
    def __init__(self) -> None:
        self.sql = ""

    def execute(self, sql: str) -> None:
        self.sql = sql
        statements.append(sql)

    def fetchall(self) -> list[tuple[object, ...]]:
        if self.sql.lower().startswith("select count"):
            return [(2,)]
        return [(None, None, 0)]


class _Connection:
    def __init__(self, kwargs: dict[str, object]) -> None:
        self.kwargs = kwargs
        self.cursor_obj = _Cursor()

    def cursor(self) -> _Cursor:
        return self.cursor_obj


def _connect(**kwargs: object) -> _Connection:
    connect_kwargs.clear()
    connect_kwargs.update(kwargs)
    return _Connection(dict(kwargs))


def _read_sql(sql: str, _conn: object) -> pd.DataFrame:
    read_sqls.append(sql)
    if next_frames:
        return next_frames.pop(0)
    return pd.DataFrame()


def _make_bars(symbol: str) -> list[BarData]:
    start: datetime = datetime(2024, 1, 15, 10, 0, tzinfo=DB_TZ)
    end: datetime = datetime(2024, 1, 15, 10, 1, tzinfo=DB_TZ)
    return [
        BarData(
            gateway_name="TEST",
            symbol=symbol,
            exchange=Exchange.SHFE,
            datetime=start,
            interval=Interval.MINUTE,
            volume=12.0,
            turnover=1.5,
            open_interest=3.0,
            open_price=100.0,
            high_price=110.0,
            low_price=90.0,
            close_price=105.0,
        ),
        BarData(
            gateway_name="TEST",
            symbol=symbol,
            exchange=Exchange.SHFE,
            datetime=end,
            interval=Interval.MINUTE,
            volume=8.0,
            open_price=105.0,
            high_price=112.0,
            low_price=101.0,
            close_price=108.0,
        ),
    ]


def _make_ticks(symbol: str) -> list[TickData]:
    start: datetime = datetime(2024, 1, 16, 10, 0, tzinfo=DB_TZ)
    end: datetime = datetime(2024, 1, 16, 10, 0, 1, tzinfo=DB_TZ)
    return [
        TickData(
            gateway_name="TEST",
            symbol=symbol,
            exchange=Exchange.SHFE,
            datetime=start,
            name="au",
            last_price=400.5,
            volume=20.0,
            localtime=start,
        ),
        TickData(
            gateway_name="TEST",
            symbol=symbol,
            exchange=Exchange.SHFE,
            datetime=end,
            name="au",
            last_price=401.0,
            volume=21.0,
            localtime=end,
        ),
    ]


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> TaosDatabase:
    statements.clear()
    read_sqls.clear()
    next_frames.clear()
    monkeypatch.setattr(taos_db.taos, "connect", _connect)
    monkeypatch.setattr(taos_db.pd, "read_sql", _read_sql)
    db: TaosDatabase = TaosDatabase()
    init_sql[:] = list(statements)
    statements.clear()
    return db


def test_init_executes_create_scripts(database: TaosDatabase) -> None:
    assert connect_kwargs == {
        "host": "127.0.0.1",
        "user": "root",
        "password": "taosdata",
        "port": 6030,
        "timezone": "Asia/Shanghai",
    }
    assert init_sql[0] == CREATE_DATABASE_SCRIPT.format("vnpy_test")
    assert init_sql[1] == "use vnpy_test"
    assert init_sql[2] == CREATE_BAR_TABLE_SCRIPT
    assert init_sql[3] == CREATE_TICK_TABLE_SCRIPT


def test_save_bar_data_inserts_ohlcv(database: TaosDatabase) -> None:
    symbol: str = "rb-main"
    table_name: str = "bar_rb_main_SHFE_1m"
    bars: list[BarData] = _make_bars(symbol)
    assert database.save_bar_data(bars) is True

    creates: list[str] = [sql for sql in statements if sql.startswith("CREATE TABLE")]
    assert len(creates) == 1
    assert table_name in creates[0]
    assert f"TAGS('{symbol}', '{Exchange.SHFE.value}', '{Interval.MINUTE.value}', '0')" in creates[0]

    inserts: list[str] = [sql for sql in statements if sql.startswith("insert into")]
    assert len(inserts) == 1
    assert inserts[0].startswith(f"insert into {table_name} values")
    assert "12.0" in inserts[0]
    assert "8.0" in inserts[0]
    assert "100.0" in inserts[0]
    assert "110.0" in inserts[0]
    assert "90.0" in inserts[0]
    assert "105.0" in inserts[0]
    assert "112.0" in inserts[0]
    assert "101.0" in inserts[0]
    assert "108.0" in inserts[0]
    assert str(bars[0].datetime) in inserts[0]
    assert str(bars[1].datetime) in inserts[0]

    alters: list[str] = [sql for sql in statements if sql.startswith("ALTER TABLE")]
    assert any(f"ALTER TABLE {table_name} SET TAG start_time=" in sql for sql in alters)
    assert any(f"ALTER TABLE {table_name} SET TAG end_time=" in sql for sql in alters)
    assert any(f"ALTER TABLE {table_name} SET TAG count_='2'" in sql for sql in alters)


def test_load_bar_data_queries_between_bounds(database: TaosDatabase) -> None:
    symbol: str = "rb-main"
    table_name: str = "bar_rb_main_SHFE_1m"
    start: datetime = datetime(2024, 1, 1, tzinfo=DB_TZ)
    end: datetime = datetime(2024, 2, 1, tzinfo=DB_TZ)
    bar_dt: datetime = datetime(2024, 1, 15, 10, 0, tzinfo=DB_TZ)
    next_frames.append(
        pd.DataFrame(
            [
                {
                    "datetime": bar_dt,
                    "volume": 12.0,
                    "turnover": 1.5,
                    "open_interest": 3.0,
                    "open_price": 100.0,
                    "high_price": 110.0,
                    "low_price": 90.0,
                    "close_price": 105.0,
                    "interval_": Interval.MINUTE.value,
                }
            ]
        )
    )

    loaded: list[BarData] = database.load_bar_data(
        symbol,
        Exchange.SHFE,
        Interval.MINUTE,
        start,
        end,
    )
    assert read_sqls == [
        f"select *, interval_ from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'"
    ]
    assert len(loaded) == 1
    assert loaded[0].symbol == symbol
    assert loaded[0].exchange == Exchange.SHFE
    assert loaded[0].interval == Interval.MINUTE
    assert loaded[0].datetime == bar_dt.astimezone(DB_TZ)
    assert loaded[0].volume == 12.0
    assert loaded[0].open_price == 100.0
    assert loaded[0].high_price == 110.0
    assert loaded[0].low_price == 90.0
    assert loaded[0].close_price == 105.0
    assert loaded[0].gateway_name == "DB"


def test_delete_bar_data_drops_symbol_table(database: TaosDatabase) -> None:
    symbol: str = "rb-main"
    table_name: str = "bar_rb_main_SHFE_1m"
    count: int = database.delete_bar_data(symbol, Exchange.SHFE, Interval.MINUTE)
    assert count == 2
    assert statements == [
        f"select count(*) from {table_name}",
        f"DROP TABLE {table_name}",
    ]


def test_save_load_delete_tick_uses_symbol_table(database: TaosDatabase) -> None:
    symbol: str = "au-main"
    table_name: str = "tick_au_main_SHFE"
    ticks: list[TickData] = _make_ticks(symbol)
    assert database.save_tick_data(ticks) is True
    creates: list[str] = [sql for sql in statements if sql.startswith("CREATE TABLE")]
    assert len(creates) == 1
    assert table_name in creates[0]
    assert f"TAGS ( '{symbol}', '{Exchange.SHFE.value}', '0')" in creates[0]
    inserts: list[str] = [sql for sql in statements if sql.startswith("insert into")]
    assert len(inserts) == 1
    assert inserts[0].startswith(f"insert into {table_name} values")
    assert "400.5" in inserts[0]
    assert "401.0" in inserts[0]
    assert "'au'" in inserts[0]
    assert "20.0" in inserts[0]
    assert "21.0" in inserts[0]

    start: datetime = datetime(2024, 1, 1, tzinfo=DB_TZ)
    end: datetime = datetime(2024, 2, 1, tzinfo=DB_TZ)
    loaded: list[TickData] = database.load_tick_data(symbol, Exchange.SHFE, start, end)
    assert loaded == []
    assert read_sqls == [
        f"select * from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'"
    ]

    count: int = database.delete_tick_data(symbol, Exchange.SHFE)
    assert count == 2
    assert f"select count(*) from {table_name}" in statements
    assert f"DROP TABLE {table_name}" in statements
