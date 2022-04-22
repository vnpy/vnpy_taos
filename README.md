# vn.py框架的TDengine数据库接口

<p align="center">
  <img src ="https://vnpy.oss-cn-shanghai.aliyuncs.com/vnpy-logo.png"/>
</p>

<p align="center">
    <img src ="https://img.shields.io/badge/version-2.2.2.0-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/platform-windows|linux-yellow.svg"/>
    <img src ="https://img.shields.io/badge/python-3.7｜3.9｜3.9｜3.10-blue.svg" />
</p>

## 说明

基于taospy开发的Tdengine数据库接口。

**需要使用Tdengine 2.4.0.16以上版本。**

## 使用

在vn.py中使用Tdengine时，需要在全局配置中填写以下字段信息：

|名称|含义|必填|举例|
|---------|----|---|---|
|database.name|名称|是|tdengine|
|database.host|地址|是|localhost|
|database.port|端口|是|6030或者0|
|database.database|实例|是|vnpy|
|database.user|用户名|是|root|
|database.password|密码|是|taosdata|

### 使用注意说明

#### 端口说明

在linux系统中连接tdengine服务器时，使用6030端口。

在windows系统中连接tdengine服务器时，6030可能无法连接，此时需要将端口切换至0。

#### FQDN说明

tdengine使用FQDN来验证服务器地址，当出现“unable to resolve FQDN”提示时，需要按照tdengine官方教程【[**TDengine的FQDN**](https://www.taosdata.com/blog/2020/09/11/1824.html)】，在客户端所在主机配置FQDN。
