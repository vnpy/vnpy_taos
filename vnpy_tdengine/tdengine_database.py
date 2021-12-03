from datetime import datetime
from typing import List, Optional
import shelve

import taos

from vnpy.trader.database import BaseDatabase, BarOverview, DB_TZ, convert_tz
from vnpy.trader.object import (
    BarData,
    TickData,
    Exchange,
    Interval
)
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import (
    generate_vt_symbol,
    get_file_path
)

from .tdengine_script import (
    CREATE_DATABASE_SCRIPT,
    CREATE_BAR_TABLE_SCRIPT,
    CREATE_TICK_TABLE_SCRIPT,
)


class TdengineDatabase(BaseDatabase):
    """Tdengine数据库接口"""

    # K线汇总数据存储路径
    overview_filename: str = "tdengine_overview"
    overview_filepath: str = str(get_file_path(overview_filename))

    def __init__(self) -> None:
        """构造函数"""
        self.user: str = SETTINGS["database.user"]
        self.password: str = SETTINGS["database.password"]
        self.host: str = SETTINGS["database.host"]
        self.port: int = SETTINGS["database.port"]
        self.config: str = "/etc/taos"

        self.conn = taos.connect(host=self.host, user=self.user, password=self.password, port=self.port, config=self.config)
        self.c1 = self.conn.cursor()

        self.c1.execute(CREATE_DATABASE_SCRIPT)
        self.c1.execute("use vnpy")
        self.c1.execute(CREATE_BAR_TABLE_SCRIPT)
        self.c1.execute(CREATE_TICK_TABLE_SCRIPT)

    def save_bar_data(self, bars: List[BarData]) -> bool:
        """保存k线数据"""
        # 读取主键参数
        bar: BarData = bars[0]
        symbol: str = bar.symbol
        exchange: Exchange = bar.exchange
        interval: Interval = bar.interval
        vt_symbol: str = bar.vt_symbol
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 以超级表为模版创建表，并存储k线数据
        self.c1.execute(f"CREATE TABLE IF NOT EXISTS {table_name} USING s_bar TAGS ( '{symbol}', '{exchange.value}' )")
        self.insert_in_batch(table_name, bars, 1000)

        # 更新K线汇总数据
        key: str = "_".join([vt_symbol, interval.value])

        f = shelve.open(self.overview_filepath)
        overview: Optional[BarOverview] = f.get(key, None)

        if not overview:
            overview: BarOverview = BarOverview(
                symbol=symbol,
                exchange=exchange,
                interval=interval
            )
            overview.count = len(bars)
            overview.start = bars[0].datetime.astimezone(DB_TZ)
            overview.end = bars[-1].datetime.astimezone(DB_TZ)
        else:
            overview.start = min(overview.start, bars[0].datetime)
            overview.end = max(overview.end, bars[-1].datetime)

            table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])
            result = self.conn.query(f"select count(*) from {table_name}")
            count: List[dict] = result.fetch_all_into_dict()
            bar_count: int = count[0]["count(*)"]

            overview.count = bar_count

        f[key] = overview
        f.close()

        return True

    def save_tick_data(self, ticks: List[TickData]) -> bool:
        """保存TICK数据"""
        bar: BarData = ticks[0]
        symbol: str = bar.symbol
        exchange: Exchange = bar.exchange
        table_name: str = "_".join(["tick", symbol, exchange.value])

        self.c1.execute(f"CREATE TABLE IF NOT EXISTS {table_name} USING s_tick TAGS ( '{symbol}', '{exchange.value}' )")
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
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        data = self.conn.query(f"select * from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'")

        bars: List[BarData] = []
        for d in data:
            dt: datetime = d[0].astimezone(DB_TZ)
            bar: BarData = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=Interval(d[1]),
                volume=d[2],
                turnover=d[3],
                open_interest=d[4],
                open_price=d[5],
                high_price=d[6],
                low_price=d[7],
                close_price=d[8],
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
        """读取TICK数据"""
        table_name: str = "_".join(["tick", symbol, exchange.value])

        data = self.conn.query(f"select * from {table_name} WHERE datetime BETWEEN '{start}' AND '{end}'")

        ticks: List[TickData] = []
        for d in data:
            dt: datetime = d[0].astimezone(DB_TZ)
            tick: TickData = TickData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
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
        table_name: str = "_".join(["bar", symbol, exchange.value, interval.value])

        # 查询K线数量
        result = self.conn.query(f"select count(*) from {table_name}")
        count: int = result.fetch_all_into_dict()[0]["count(*)"]

        # 删除K线数据
        self.c1.execute(f"DROP TABLE {table_name}")

        # 删除K线汇总
        f = shelve.open(self.overview_filepath)
        vt_symbol: str = generate_vt_symbol(symbol, exchange)
        key: str = "_".join([vt_symbol, interval.value])
        if key in f:
            f.pop(key)
        f.close()

        return count

    def delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange
    ) -> int:
        """删除TICK数据"""
        table_name: str = "_".join(["tick", symbol, exchange.value])

        # 查询TICK数量
        result = self.conn.query(f"select count(*) from {table_name}")
        count: dict = result.fetch_all_into_dict()

        # 删除TICK数据
        self.c1.execute(f"DROP TABLE {table_name}")

        return count[0]["count(*)"]

    def get_bar_overview(self) -> List[BarOverview]:
        """查询K线汇总信息"""
        f = shelve.open(self.overview_filepath)
        overviews = list(f.values())
        f.close()

        return overviews

    def insert_in_batch(self, table_name: str, data_set: list, batch_size: int) -> None:
        """数据批量插入数据库"""
        if table_name.split("_")[0] == "bar":
            generate = generate_bar
        else:
            generate = generate_tick

        data: List[str] = [f"insert into {table_name} values"]
        count: int = 0

        for d in data_set:
            if count < batch_size:
                data.append(generate(d))
                count += 1
            else:
                self.c1.execute(" ".join(data))

                data: List[str] = [f"insert into {table_name} values"]
                count = 0

        if count != 0:
            self.c1.execute(" ".join(data))


def generate_bar(bar: BarData) -> str:
    result: str = (f"('{convert_tz(bar.datetime)}', '{bar.interval.value}', {bar.volume}, {bar.turnover}, "
                   + f"{bar.open_interest}, {bar.open_price}, {bar.high_price}, {bar.low_price}, {bar.close_price})")
    return result


def generate_tick(tick: TickData) -> str:
    dt = convert_tz(tick.datetime)
    if tick.localtime:
        localtime = tick.localtime
    else:
        localtime = dt
    result: str = (f"('{dt}', '{tick.name}', {tick.volume}, {tick.turnover}, "
                   + f"{tick.open_interest}, {tick.last_price}, {tick.last_volume}, "
                   + f"{tick.limit_up}, {tick.limit_down}, {tick.open_price}, {tick.high_price}, {tick.low_price}, {tick.pre_close}, "
                   + f"{tick.bid_price_1}, {tick.bid_price_2}, {tick.bid_price_3}, {tick.bid_price_4}, {tick.bid_price_5}, "
                   + f"{tick.ask_price_1}, {tick.ask_price_2}, {tick.ask_price_3}, {tick.ask_price_4}, {tick.ask_price_5}, "
                   + f"{tick.bid_volume_1}, {tick.bid_volume_2}, {tick.bid_volume_3}, {tick.bid_volume_4}, {tick.bid_volume_5}, "
                   + f"{tick.ask_volume_1}, {tick.ask_volume_2}, {tick.ask_volume_3}, {tick.ask_volume_4}, {tick.ask_volume_5}, "
                   + f"'{localtime}')")
    return result
