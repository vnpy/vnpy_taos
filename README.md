# VeighNa框架的TDengine数据库接口

<p align="center">
  <img src ="https://vnpy.oss-cn-shanghai.aliyuncs.com/vnpy-logo.png"/>
</p>

<p align="center">
    <img src ="https://img.shields.io/badge/version-1.0.4-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/platform-windows|linux-yellow.svg"/>
    <img src ="https://img.shields.io/badge/python-3.10|3.11|3.12-blue.svg" />
</p>

## 说明

基于TDengine的Python连接器taospy开发的TDengine数据库接口。

**需要使用TDengine 3.3.4.8以上版本。**

## 使用

在VeighNa中使用TDengine时，需要在全局配置中填写以下字段信息：

|名称|含义|必填|举例|
|---------|----|---|---|
|database.name|名称|是|taos|
|database.host|地址|是|localhost|
|database.port|端口|是|6030|
|database.database|实例|是|vnpy|
|database.user|用户名|是|root|
|database.password|密码|是|taosdata|

### 连接

连接前需要根据环境安装配置TDengine的客户端和服务端，TDengine的安装流程请参考[官方文档](https://docs.taosdata.com/get-started/docker/)。

新手用户推荐选择Docker方式运行，Windows系统上的整体流程如下：

1. 安装启动[Docker Desktop](https://www.docker.com/)软件
2. 在命令行中拉取最新版本TDengine容器镜像：```docker pull tdengine/tdengine:latest```
3. 运行当前仓库中的start_docker.sh脚本，启动TDengine容器
4. 安装TDengine的Windows客户端软件：[TDengine-client-3.3.4.8-Windows-x64.exe (10.2 M)](https://docs.taosdata.com/get-started/package/)
5. 安装vnpy_taos模块：```pip install vnpy_taos```
6. 参考上一步【使用】中的内容修改VeighNa Trader全局配置中的相关字段
7. 重启VeighNa Trader即可开始使用