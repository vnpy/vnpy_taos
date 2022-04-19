from datetime import datetime
from typing import Callable, List

import taos

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData, TickData
from vnpy.trader.database import (
    BaseDatabase,
    BarOverview,
    DB_TZ
)
from vnpy.trader.setting import SETTINGS

from .tdengine_script import (
    CREATE_DATABASE_SCRIPT,
    CREATE_BAR_TABLE_SCRIPT,
    CREATE_TICK_TABLE_SCRIPT,
)


class TdengineDatabase(BaseDatabase):
    """Tdengine数据库接口"""

    def __init__(self) -> None:
        """构造函数"""
        self.user: str = SETTINGS["database.user"]
        self.password: str = SETTINGS["database.password"]
        self.host: str = SETTINGS["database.host"]
        self.port: int = SETTINGS["database.port"]
        self.config: str = "/etc/taos"
        self.timezone: str = SETTINGS["database.timezone"]

        # 连接数据库
        self.conn: taos.TaosConnection = taos.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            port=self.port,
            config=self.config,
            timezone=self.timezone
        )

        self.cursor: taos.TaosCursor = self.conn.cursor()

        # 初始化创建数据库和数据表
        self.cursor.execute(CREATE_DATABASE_SCRIPT)
        self.cursor.execute("use vnpy")
        self.cursor.execute(CREATE_BAR_TABLE_SCRIPT)
        self.cursor.execute(CREATE_TICK_TABLE_SCRIPT)

    def save_bar_data(self, bars: List[BarData]) -> bool:
        """保存k线数据"""
        # 缓存字段参数
        bar: BarData = bars[0]
        symbol: str = bar.symbol
        exchange: Exchange = bar.exchange
        interval: Interval = bar.interval

        count: int = 0
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 以超级表为模版创建表
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name}
            USING s_bar(symbol, exchange, interval_, count)
            TAGS('{symbol}', '{exchange.value}', '{interval.value}', '{count}')
            """)

        # 写入k线数据
        self.insert_in_batch(table_name, bars, 1000)

        # 查询汇总信息
        self.cursor.execute(f"SELECT start_time, end_time, count FROM {table_name}")
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
        self.cursor.execute(f"ALTER TABLE {table_name} SET TAG count='{overview_count}';")

        return True

    def save_tick_data(self, ticks: List[TickData]) -> bool:
        """保存tick数据"""
        bar: BarData = ticks[0]
        symbol: str = bar.symbol
        exchange: Exchange = bar.exchange
        table_name: str = "_".join(["tick", symbol, exchange.value])

        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} USING s_tick TAGS ( '{symbol}', '{exchange.value}' )")
        self.insert_in_batch(table_name, ticks, 1000)

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
        self.cursor.execute(f"select *, interval_ from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'")
        data: List[tuple] = self.cursor.fetchall()

        # 返回BarData列表
        bars: List[BarData] = []

        for d in data:
            bar: BarData = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=d[0],
                interval=Interval(d[8]),
                volume=d[1],
                turnover=d[2],
                open_interest=d[3],
                open_price=d[4],
                high_price=d[5],
                low_price=d[6],
                close_price=d[7],
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
        self.cursor.execute(f"select * from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'")
        data: List[tuple] = self.cursor.fetchall()

        # 返回TickData列表
        ticks: List[TickData] = []

        for d in data:
            tick: TickData = TickData(
                symbol=symbol,
                exchange=exchange,
                datetime=d[0],
                name=d[1],
                volume=d[2],
                turnover=d[3],
                open_interest=d[4],
                last_price=d[5],
                limit_up=d[6],
                limit_down=d[7],
                open_price=d[8],
                high_price=d[9],
                low_price=d[10],
                pre_close=d[11],
                bid_price_1=d[12],
                bid_price_2=d[13],
                bid_price_3=d[14],
                bid_price_4=d[15],
                bid_price_5=d[16],
                ask_price_1=d[17],
                ask_price_2=d[18],
                ask_price_3=d[19],
                ask_price_4=d[20],
                ask_price_5=d[21],
                bid_volume_1=d[22],
                bid_volume_2=d[23],
                bid_volume_3=d[24],
                bid_volume_4=d[25],
                bid_volume_5=d[26],
                ask_volume_1=d[27],
                ask_volume_2=d[28],
                ask_volume_3=d[29],
                ask_volume_4=d[30],
                ask_volume_5=d[31],
                localtime=d[32],
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
        self.cursor.execute("SELECT symbol, exchange, interval_, start_time, end_time, count FROM s_bar")
        results: List[tuple] = self.cursor.fetchall()

        # 返回BarOverview列表
        overviews: list[BarOverview] = []

        for i in results:
            overview: BarOverview = BarOverview(
                symbol=i[0],
                exchange=Exchange(i[1]),
                interval=Interval(i[2]),
                start=i[3],
                end=i[4],
                count=int(i[5]),
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
