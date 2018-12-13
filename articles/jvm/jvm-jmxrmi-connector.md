经常独自排查线上问题，最近不得不想着把它整理出来分享给小伙伴（因为有找不完的线上问题D#--），其实定位时用到的JVM相关工具就那么几个，常用就熟悉了。




JMX全称是Java管理扩展（Java Management Extensions），是Java SE平台的一部分。说白了，JMX是一个很强大的管理Java应用管理工具，可以在Java程序运行时动态监控和管理Java应用，当然JMX的功能远不止于此。我们这里主要关心的是JMX能够帮助我们在实战中定位问题的一些功能。



JMX提供了3种能力来管理Java应用，分别是网页形式管理，SNMP管理，以及通过RMI管理，我们这一阶段要关心的是通过RMI连接器来监控JVM。

想监控JVM，所以我们先得开启JMX代理，我们通过在Java运行时配置以下参数开启JMX Agent

```bash
// 开启JMX代理
-Dcom.sun.management.jmxremote
// 连接JMX代理不需要账号信息
-Dcom.sun.management.jmxremote.authenticate=false
// 禁用SSL连接
-Dcom.sun.management.jmxremote.ssl=false
// 用于启用RMI连接的端口，相当于主管理端口
-Dcom.sun.management.jmxremote.port=30301
// RMI连接器绑定的端口，实际命令接收端口，可以和管理端口配置成同一个
-Dcom.sun.management.jmxremote.rmi.port=30301
// 统一设置为localhost，随后通过网络隧道或代理连接
-Djava.rmi.server.hostname=localhost                 
```

从[Oracle JMX 文档](https://docs.oracle.com/javase/8/docs/technotes/guides/management/agent.html)中可以发现，其实JMX的配置项还有很多，不少是关于安全配置的，在我们的实际环境中，我们通过VPC组网（服务器内部局域网）和堡垒机来保证网络安全，所以在**测试环境**中，我们直接就这样配置了，方便查找问题。



随后，我们通过一个SSH建立一个简单的单接口隧道

```bash
ssh -L 9999:my-java-server-ip:30301 my-user@my-proxy-server
```

通过代理机器`my-proxy-server`与部署Java应用的机器`my-java-server`建立隧道，将本地的9999端口映射到`my-java-server`服务器的30301端口。

如果`my-java-server`是直接可达的，那么就更简单些

```bash
ssh -L 9999:127.0.0.1:30301 my-user@my-proxy-server
```



随后，我们运行在`$JAVA_HOME/bin`目录下的`jvisualvm`程序（在Windows则是`VisualVM.exe`)，之后我们即可查看JVM的各种状态。



## VisualVM中各类参数

#### 概览

#### 基础监控

#### 线程

#### 取样器



## 在线上环境监控JVM

#### 通过Kubernetes端口转发



#### 通过VisualVM的socksProxy



## 通过命令查看JVM信息

## 通过命令查看JVM信息



#### jmap

#### jstat

#### jstack

#### jinfo



## 定制JMXConnectorServer



## 定制StatsBean

#### Java代码生成



#### 利用Spring的@EnableMBeanExport



## 其它

#### JCONSOLE



#### TPROFILE












