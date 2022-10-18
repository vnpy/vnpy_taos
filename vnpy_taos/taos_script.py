"""
TDengine脚本, 用于在TDengine中创建数据库和数据表。
"""

# 创建数据库
CREATE_DATABASE_SCRIPT = """
CREATE DATABASE IF NOT EXISTS {} KEEP 36500
"""

# 创建bar超级表
CREATE_BAR_TABLE_SCRIPT = """
CREATE STABLE IF NOT EXISTS s_bar (
    datetime TIMESTAMP,
    volume DOUBLE,
    turnover DOUBLE,
    open_interest DOUBLE,
    open_price DOUBLE,
    high_price DOUBLE,
    low_price DOUBLE,
    close_price DOUBLE
)
TAGS(
    symbol BINARY(20),
    exchange BINARY(10),
    interval_ BINARY(5),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    count_ DOUBLE
)
"""

# 创建tick超级表
CREATE_TICK_TABLE_SCRIPT = """
CREATE STABLE IF NOT EXISTS s_tick (
    datetime TIMESTAMP,
    name NCHAR(20),
    volume DOUBLE,
    turnover DOUBLE,
    open_interest DOUBLE,
    last_price DOUBLE,
    last_volume DOUBLE,
    limit_up DOUBLE,
    limit_down DOUBLE,
    open_price DOUBLE,
    high_price DOUBLE,
    low_price DOUBLE,
    pre_close DOUBLE,
    bid_price_1 DOUBLE,
    bid_price_2 DOUBLE,
    bid_price_3 DOUBLE,
    bid_price_4 DOUBLE,
    bid_price_5 DOUBLE,
    ask_price_1 DOUBLE,
    ask_price_2 DOUBLE,
    ask_price_3 DOUBLE,
    ask_price_4 DOUBLE,
    ask_price_5 DOUBLE,
    bid_volume_1 DOUBLE,
    bid_volume_2 DOUBLE,
    bid_volume_3 DOUBLE,
    bid_volume_4 DOUBLE,
    bid_volume_5 DOUBLE,
    ask_volume_1 DOUBLE,
    ask_volume_2 DOUBLE,
    ask_volume_3 DOUBLE,
    ask_volume_4 DOUBLE,
    ask_volume_5 DOUBLE,
    localtime TIMESTAMP
)
TAGS(
    symbol BINARY(20),
    exchange BINARY(10),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    count_ DOUBLE
)
"""
