# 1.1.1版本

1. 优化get_bar_overview和get_tick_overview函数性能（直接访问超级表的tags）

# 1.1.0版本

1. vnpy框架4.0版本升级适配

# 1.0.4版本

1. 修复DataManager中加载数据时，时间戳的时区部分缺失问题

# 1.0.3版本

1. 升级支持TDengine的3.0版本
2. 移除不必要的时区转换提高性能
3. 添加Docker启动脚本

# 1.0.2版本

由于TDengine版本升级，之前版本的vnpy_taos出现一系列兼容问题。

1. 修复数据库创建报错
2. 修复超级表创建报错
3. 修复数据写入语句报错
4. 使用distinct减少汇总数据查询时的返回量

# 1.0.1版本

1. 增加TickOverview支持
2. 增加stream流式写入支持
