# vn.py框架的TDengine数据库接口

<p align="center">
  <img src ="https://vnpy.oss-cn-shanghai.aliyuncs.com/vnpy-logo.png"/>
</p>

<p align="center">
    <img src ="https://img.shields.io/badge/version-1.0.1-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/platform-windows|linux|macos-yellow.svg"/>
    <img src ="https://img.shields.io/badge/python-3.7-blue.svg" />
</p>

## 说明

基于taospy开发的Tdengine数据库接口。

**需要使用Tdengine 2.1.7.0以上版本。**

## 使用

在vn.py中使用Tdengine时，需要在全局配置中填写以下字段信息：

|名称|含义|必填|举例|
|---------|----|---|---|
|database.name|名称|是|tdengine|
|database.host|地址|是|localhost|
|database.port|端口|是|6030|
|database.database|实例|是|vnpy|
|database.user|用户名|是|root|
|database.password|密码|是|taosdata|
