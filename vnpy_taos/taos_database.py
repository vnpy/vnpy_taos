from datetime import datetime
from typing import Callable, List

import taos
import pandas
from pandas import DataFrame

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData, TickData
from vnpy.trader.database import (
    BaseDatabase,
    BarOverview,
    TickOverview,
    DB_TZ
)
from vnpy.trader.setting import SETTINGS

from .taos_script import (
    CREATE_DATABASE_SCRIPT,
    CREATE_BAR_TABLE_SCRIPT,
    CREATE_TICK_TABLE_SCRIPT,
)


class TaosDatabase(BaseDatabase):
    """TDengine数据库接口"""

    def __init__(self) -> None:
        """构造函数"""
        self.user: str = SETTINGS["database.user"]
        self.password: str = SETTINGS["database.password"]
        self.host: str = SETTINGS["database.host"]
        self.port: int = SETTINGS["database.port"]
        self.timezone: str = SETTINGS["database.timezone"]
        self.database: str = SETTINGS["database.database"]

        # 连接数据库
        self.conn: taos.TaosConnection = taos.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            port=self.port,
            timezone=self.timezone
        )

        self.cursor: taos.TaosCursor = self.conn.cursor()

        # 初始化创建数据库和数据表
        self.cursor.execute(CREATE_DATABASE_SCRIPT.format(self.database))
        self.cursor.execute(f"use {self.database}")
        self.cursor.execute(CREATE_BAR_TABLE_SCRIPT)
        self.cursor.execute(CREATE_TICK_TABLE_SCRIPT)

    def save_bar_data(self, bars: List[BarData], stream: bool = False) -> bool:
        """保存k线数据"""
        # 缓存字段参数
        bar: BarData = bars[0]
        symbol: str = bar.symbol
        exchange: Exchange = bar.exchange
        interval: Interval = bar.interval

        count: int = 0
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 以超级表为模版创建表
        create_table_script: str = (
            f"CREATE TABLE IF NOT EXISTS {table_name} "
            "USING s_bar(symbol, exchange, interval_, count_) "
            f"TAGS('{symbol}', '{exchange.value}', '{interval.value}', '{count}')"
        )
        self.cursor.execute(create_table_script)

        # 写入k线数据
        self.insert_in_batch(table_name, bars, 1000)

        # 查询汇总信息
        self.cursor.execute(f"SELECT start_time, end_time, count_ FROM {table_name}")
        results: List[tuple] = self.cursor.fetchall()

        overview: tuple = results[0]
        overview_start: datetime = overview[0]
        overview_end: datetime = overview[1]
        overview_count: int = int(overview[2])

        # 没有该合约
        if not overview_count:
            overview_start: datetime = bars[0].datetime.astimezone(DB_TZ)
            overview_end: datetime = bars[-1].datetime.astimezone(DB_TZ)
            overview_count: int = len(bars)
        # 已有该合约
        elif stream:
            overview_end: datetime = bars[-1].datetime.astimezone(DB_TZ)
            overview_count += len(bars)
        else:
            overview_start: datetime = min(overview_start, bars[0].datetime)
            overview_end: datetime = max(overview_end, bars[-1].datetime)

            self.cursor.execute(f"select count(*) from {table_name}")
            results: List[tuple] = self.cursor.fetchall()

            bar_count: int = int(results[0][0])
            overview_count: int = bar_count

        # 更新汇总信息
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG start_time='{overview_start}';")
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG end_time='{overview_end}';")
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG count_='{overview_count}';")

        return True

    def save_tick_data(self, ticks: List[TickData], stream: bool = False) -> bool:
        """保存tick数据"""
        tick: TickData = ticks[0]
        symbol: str = tick.symbol
        exchange: Exchange = tick.exchange

        count: int = 0
        table_name: str = "_".join(["tick", symbol, exchange.value])

        # 以超级表为模版创建表
        create_table_script: str = (
            f"CREATE TABLE IF NOT EXISTS {table_name} "
            "USING s_tick(symbol, exchange, count_) "
            f"TAGS ( '{symbol}', '{exchange.value}', '{count}')"
        )
        self.cursor.execute(create_table_script)

        # 写入tick数据
        self.insert_in_batch(table_name, ticks, 1000)

        # 查询汇总信息
        self.cursor.execute(f"SELECT start_time, end_time, count_ FROM {table_name}")
        results: List[tuple] = self.cursor.fetchall()

        overview: tuple = results[0]
        overview_start: datetime = overview[0]
        overview_end: datetime = overview[1]
        overview_count: int = int(overview[2])

        # 没有该合约
        if not overview_count:
            overview_start: datetime = ticks[0].datetime.astimezone(DB_TZ)
            overview_end: datetime = ticks[-1].datetime.astimezone(DB_TZ)
            overview_count: int = len(ticks)
        # 已有该合约
        elif stream:
            overview_end: datetime = ticks[-1].datetime.astimezone(DB_TZ)
            overview_count += len(ticks)
        else:
            overview_start: datetime = min(overview_start, ticks[0].datetime)
            overview_end: datetime = max(overview_end, ticks[-1].datetime)

            self.cursor.execute(f"select count(*) from {table_name}")
            results: List[tuple] = self.cursor.fetchall()

            tick_count: int = int(results[0][0])
            overview_count: int = tick_count

        # 更新汇总信息
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG start_time='{overview_start}';")
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG end_time='{overview_end}';")
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG count_='{overview_count}';")

        return True

    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> List[BarData]:
        """读取K线数据"""
        # 生成数据表名
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 从数据库读取数据
        df: DataFrame = pandas.read_sql(f"select *, interval_ from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'", self.conn)

        # 返回BarData列表
        bars: List[BarData] = []

        for row in df.itertuples():
            bar: BarData = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=row.datetime.astimezone(DB_TZ.key),
                interval=Interval(row.interval_),
                volume=row.volume,
                turnover=row.turnover,
                open_interest=row.open_interest,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.low_price,
                close_price=row.close_price,
                gateway_name="DB"
            )
            bars.append(bar)

        return bars

    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime
    ) -> List[TickData]:
        """读取tick数据"""
        # 生成数据表名
        table_name: str = "_".join(["tick", symbol, exchange.value])

        # 从数据库读取数据
        df: DataFrame = pandas.read_sql(f"select * from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'", self.conn)

        # 返回TickData列表
        ticks: List[TickData] = []

        for row in df.itertuples():
            tick: TickData = TickData(
                symbol=symbol,
                exchange=exchange,
                datetime=row.datetime.astimezone(DB_TZ.key),
                name=row.name,
                volume=row.volume,
                turnover=row.turnover,
                open_interest=row.open_interest,
                last_price=row.last_price,
                limit_up=row.limit_up,
                limit_down=row.limit_down,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.last_price,
                pre_close=row.pre_close,
                bid_price_1=row.bid_price_1,
                bid_price_2=row.bid_price_2,
                bid_price_3=row.bid_price_3,
                bid_price_4=row.bid_price_4,
                bid_price_5=row.bid_price_5,
                ask_price_1=row.ask_price_1,
                ask_price_2=row.ask_price_2,
                ask_price_3=row.ask_price_3,
                ask_price_4=row.ask_price_4,
                ask_price_5=row.ask_price_5,
                bid_volume_1=row.bid_volume_1,
                bid_volume_2=row.bid_volume_2,
                bid_volume_3=row.bid_volume_3,
                bid_volume_4=row.bid_volume_4,
                bid_volume_5=row.bid_volume_5,
                ask_volume_1=row.ask_volume_1,
                ask_volume_2=row.ask_volume_2,
                ask_volume_3=row.ask_volume_3,
                ask_volume_4=row.ask_volume_4,
                ask_volume_5=row.ask_volume_5,
                localtime=row.localtime,
                gateway_name="DB"
            )
            ticks.append(tick)

        return ticks

    def delete_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval
    ) -> int:
        """删除K线数据"""
        # 生成数据表名
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 查询数据条数
        self.cursor.execute(f"select count(*) from {table_name}")
        result: list = self.cursor.fetchall()
        count: int = int(result[0][0])

        # 执行K线删除
        self.cursor.execute(f"DROP TABLE {table_name}")

        return count

    def delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange
    ) -> int:
        """删除tick数据"""
        # 生成数据表名
        table_name: str = "_".join(["tick", symbol, exchange.value])

        # 查询数据条数
        self.cursor.execute(f"select count(*) from {table_name}")
        result: list = self.cursor.fetchall()
        count: int = int(result[0][0])

        # 删除tick数据
        self.cursor.execute(f"DROP TABLE {table_name}")

        return count

    def get_bar_overview(self) -> List[BarOverview]:
        """查询K线汇总信息"""
        # 从数据库读取数据
        df: DataFrame = pandas.read_sql("SELECT DISTINCT symbol, exchange, interval_, start_time, end_time, count_ FROM s_bar", self.conn)

        # 返回BarOverview列表
        overviews: list[BarOverview] = []

        for row in df.itertuples():
            overview: BarOverview = BarOverview(
                symbol=row.symbol,
                exchange=Exchange(row.exchange),
                interval=Interval(row.interval_),
                start=row.start_time.astimezone(DB_TZ.key),
                end=row.end_time.astimezone(DB_TZ.key),
                count=int(row.count_),
            )
            overviews.append(overview)

        return overviews

    def get_tick_overview(self) -> List[TickOverview]:
        """查询Tick汇总信息"""
        # 从数据库读取数据
        df: DataFrame = pandas.read_sql("SELECT DISTINCT symbol, exchange, start_time, end_time, count_ FROM s_tick", self.conn)

        # TickOverview
        overviews: list[TickOverview] = []

        for row in df.itertuples():
            overview: TickOverview = TickOverview(
                symbol=row.symbol,
                exchange=Exchange(row.exchange),
                start=row.start_time.astimezone(DB_TZ.key),
                end=row.end_time.astimezone(DB_TZ.key),
                count=int(row.count_),
            )
            overviews.append(overview)

        return overviews

    def insert_in_batch(self, table_name: str, data_set: list, batch_size: int) -> None:
        """数据批量插入数据库"""
        if table_name.split("_")[0] == "bar":
            generate: Callable = generate_bar
        else:
            generate: Callable = generate_tick

        data: List[str] = [f"insert into {table_name} values"]
        count: int = 0

        for d in data_set:
            if count < batch_size:
                data.append(generate(d))
                count += 1
            else:
                self.cursor.execute(" ".join(data))

                data: List[str] = [f"insert into {table_name} values"]
                count = 0

        if count != 0:
            self.cursor.execute(" ".join(data))


def generate_bar(bar: BarData) -> str:
    """将BarData转换为可存储的字符串"""
    result: str = (f"('{bar.datetime}', {bar.volume}, {bar.turnover}, {bar.open_interest},"
                   + f"{bar.open_price}, {bar.high_price}, {bar.low_price}, {bar.close_price})")

    return result


def generate_tick(tick: TickData) -> str:
    """将TickData转换为可存储的字符串"""
    # tick不带localtime
    if tick.localtime:
        localtime: datetime = tick.localtime
    # tick带localtime
    else:
        localtime: datetime = tick.datetime

    result: str = (f"('{tick.datetime}', '{tick.name}', {tick.volume}, {tick.turnover}, "
                   + f"{tick.open_interest}, {tick.last_price}, {tick.last_volume}, "
                   + f"{tick.limit_up}, {tick.limit_down}, {tick.open_price}, {tick.high_price}, {tick.low_price}, {tick.pre_close}, "
                   + f"{tick.bid_price_1}, {tick.bid_price_2}, {tick.bid_price_3}, {tick.bid_price_4}, {tick.bid_price_5}, "
                   + f"{tick.ask_price_1}, {tick.ask_price_2}, {tick.ask_price_3}, {tick.ask_price_4}, {tick.ask_price_5}, "
                   + f"{tick.bid_volume_1}, {tick.bid_volume_2}, {tick.bid_volume_3}, {tick.bid_volume_4}, {tick.bid_volume_5}, "
                   + f"{tick.ask_volume_1}, {tick.ask_volume_2}, {tick.ask_volume_3}, {tick.ask_volume_4}, {tick.ask_volume_5}, "
                   + f"'{localtime}')")

    return result
