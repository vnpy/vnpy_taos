# VeighNa框架的TDengine数据库接口

<p align="center">
  <img src ="https://vnpy.oss-cn-shanghai.aliyuncs.com/vnpy-logo.png"/>
</p>

<p align="center">
    <img src ="https://img.shields.io/badge/version-1.0.0-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/platform-windows|linux-yellow.svg"/>
    <img src ="https://img.shields.io/badge/python-3.7|3.9|3.9|3.10-blue.svg" />
</p>

## 说明

基于TDengine的Python连接器taospy开发的TDengine数据库接口。

**需要使用TDengine 2.4.0.16以上版本。**

## 使用

在veighna中使用TDengine时，需要在全局配置中填写以下字段信息：

|名称|含义|必填|举例|
|---------|----|---|---|
|database.name|名称|是|taos|
|database.host|地址|是|localhost|
|database.port|端口|是|6030|
|database.database|实例|是|vnpy|
|database.user|用户名|是|root|
|database.password|密码|是|taosdata|

### 连接

连接前需要根据环境安装配置TDengine的客户端或服务端。

TDengine安装包下载地址：https://www.taosdata.com/cn/all-downloads/ 。服务端具体安装方法可参考[【安装包的安装与卸载】文档，](https://docs.taosdata.com/operation/pkg-install)客户端具体安装方法可参考[【安装客户端驱动】文档。](https://docs.taosdata.com/reference/connector/#%E5%AE%89%E8%A3%85%E5%AE%A2%E6%88%B7%E7%AB%AF%E9%A9%B1%E5%8A%A8)

#### Linux连接本地数据库

连接前需要安装TDengine的Linux服务端。

安装成功后，需要使用```systemctl start taosd```命令启动TDengine的服务进程。接下来可使用```systemctl status taosd```命令检查服务是否正常工作。如果TDengine服务正常工作，就可以通过veighna来访问TDengine了。

#### Windows客户端连接Linux服务端

连接前需要在服务端机器安装TDengine的Linux服务端，客户端机器安装Windows客户端。

请注意，为避免客户端驱动和服务端不兼容，请使用**一致**的版本。

TDengine使用FQDN来验证服务器地址，连接前可参考文章[保姆级演示一分钟搞定TDengine的下载安装](https://zhuanlan.zhihu.com/p/302413259#:~:text=%E5%8F%A6%E5%A4%96%EF%BC%8CTDengine%E9%99%A4%E4%BA%86%E6%94%AF%E6%8C%81%20Linux%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8C%E8%BF%98%E6%94%AF%E6%8C%81%20windows%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8CWindows%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E5%AE%89%E8%A3%85%E6%96%B9%E6%B3%95,%E5%8F%8C%E5%87%BB%E5%AE%89%E8%A3%85%E6%96%87%E4%BB%B6%20-%3E%20%E9%80%89%E6%8B%A9%E9%BB%98%E8%AE%A4%E5%8D%B3%E5%8F%AF%E5%AE%8C%E6%88%90%E5%AE%89%E8%A3%85%E3%80%82%20%E5%AE%89%E8%A3%85%E5%AE%8C%E6%88%90%E5%90%8E%EF%BC%8C%E5%9C%A8C%E7%9B%98%E4%BC%9A%E6%9C%89%E4%B8%80%E4%B8%AATDengine%E7%9A%84%E7%9B%AE%E5%BD%95%EF%BC%8C%E5%8C%85%E6%8B%AC%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E4%B8%80%E4%BA%9B%E6%96%87%E4%BB%B6%E3%80%82)配置FQDN，并将全局配置中的host由“localhost”改为服务器的IP地址。

若已在服务端机器启动TDengine服务进程并在客户端机器成功配置FQDN，即可通过veighna访问TDengine了。

#### Linux客户端连接docker服务端

连接前需要在服务端机器安装docker，客户端机器安装TDengine的Linux客户端（如已安装服务端无需安装客户端）。

请注意，为避免客户端驱动和服务端不兼容，请使用**一致**的版本（docker会拉取服务端最新版本，需要根据docker内服务端版本安装客户端）。

TDengine使用FQDN来验证服务器地址，连接前可参考文章[保姆级演示一分钟搞定TDengine的下载安装](https://zhuanlan.zhihu.com/p/302413259#:~:text=%E5%8F%A6%E5%A4%96%EF%BC%8CTDengine%E9%99%A4%E4%BA%86%E6%94%AF%E6%8C%81%20Linux%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8C%E8%BF%98%E6%94%AF%E6%8C%81%20windows%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8CWindows%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E5%AE%89%E8%A3%85%E6%96%B9%E6%B3%95,%E5%8F%8C%E5%87%BB%E5%AE%89%E8%A3%85%E6%96%87%E4%BB%B6%20-%3E%20%E9%80%89%E6%8B%A9%E9%BB%98%E8%AE%A4%E5%8D%B3%E5%8F%AF%E5%AE%8C%E6%88%90%E5%AE%89%E8%A3%85%E3%80%82%20%E5%AE%89%E8%A3%85%E5%AE%8C%E6%88%90%E5%90%8E%EF%BC%8C%E5%9C%A8C%E7%9B%98%E4%BC%9A%E6%9C%89%E4%B8%80%E4%B8%AATDengine%E7%9A%84%E7%9B%AE%E5%BD%95%EF%BC%8C%E5%8C%85%E6%8B%AC%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E4%B8%80%E4%BA%9B%E6%96%87%E4%BB%B6%E3%80%82)配置FQDN，并将全局配置中的host由“localhost”改为服务器的hostname。

docker安装成功后，执行以下命令创建容器：
```
docker run -d -p 6030-6049:6030-6049 -p 6030-6049:6030-6049/udp tdengine/tdengine
```

可通过```docker ps```命令确定该容器已经启动并且在正常运行。

若已在docker启动TDengine服务进程并在客户端机器成功配置FQDN，即可通过veighna访问TDengine了。

#### Windows客户端连接docker服务端

连接前需要在服务端机器安装docker，客户端机器安装TDengine的Windows客户端（如已安装服务端无需安装客户端）。

请注意，为避免客户端驱动和服务端不兼容，请使用**一致**的版本（docker会拉取服务端最新版本，需要根据docker内服务端版本安装客户端）。

TDengine使用FQDN来验证服务器地址，连接前可参考文章[保姆级演示一分钟搞定TDengine的下载安装](https://zhuanlan.zhihu.com/p/302413259#:~:text=%E5%8F%A6%E5%A4%96%EF%BC%8CTDengine%E9%99%A4%E4%BA%86%E6%94%AF%E6%8C%81%20Linux%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8C%E8%BF%98%E6%94%AF%E6%8C%81%20windows%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%8CWindows%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E5%AE%89%E8%A3%85%E6%96%B9%E6%B3%95,%E5%8F%8C%E5%87%BB%E5%AE%89%E8%A3%85%E6%96%87%E4%BB%B6%20-%3E%20%E9%80%89%E6%8B%A9%E9%BB%98%E8%AE%A4%E5%8D%B3%E5%8F%AF%E5%AE%8C%E6%88%90%E5%AE%89%E8%A3%85%E3%80%82%20%E5%AE%89%E8%A3%85%E5%AE%8C%E6%88%90%E5%90%8E%EF%BC%8C%E5%9C%A8C%E7%9B%98%E4%BC%9A%E6%9C%89%E4%B8%80%E4%B8%AATDengine%E7%9A%84%E7%9B%AE%E5%BD%95%EF%BC%8C%E5%8C%85%E6%8B%AC%E5%AE%A2%E6%88%B7%E7%AB%AF%E7%9A%84%E4%B8%80%E4%BA%9B%E6%96%87%E4%BB%B6%E3%80%82)配置FQDN，并将全局配置中的host由“localhost”改为服务器的hostname。

若已在docker启动TDengine服务进程并在客户端机器成功配置FQDN，即可通过veighna访问TDengine了。

#### 常见问题

**端口配置问题**

在Linux系统中连接TDengine服务器时，使用6030端口。

在Windows系统中连接TDengine服务器时，6030可能无法连接，此时需要将端口切换至0。

**FQDN配置问题**

除了在Linux连接本地数据库之外，TDengine都需要使用FQDN来验证服务器地址。若运行时出现“unable to resolve FQDN”提示时，可以检查是否有在客户端所在主机配置FQDN。

当使用docker启动Tdengine时，客户端中FQDN中配置的hostname应使用启用的docker的hostname
