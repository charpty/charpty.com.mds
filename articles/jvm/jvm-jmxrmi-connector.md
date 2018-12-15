经常独自排查线上问题，最近不得不想着把它整理出来分享给小伙伴（因为有找不完的线上问题D#--），其实定位时用到的JVM相关工具就那么几个，常用就熟悉了。



## 使用JMX监控JVM

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

现在，我们运行在`$JAVA_HOME/bin`目录下的`jvisualvm`程序（在Windows则是`VisualVM.exe`)，输入地址，之后我们即可查看JVM的各种状态。

## 使用JMX的特殊场景

**在某些特殊的场景中**，我们还得配合一些其它手段来使用JMX

#### 服务器只开放了SSH端口，且JMX不止监听一个端口

在生产环境上往往不允许开放除应用监听端口以外的其它端口，此时我们不得不通过SSH的动态代理功能，映射服务器的所有端口。

JMX默认监听3个端口，3个端口都能连接才能获取最全的监控和控制信息，在不少生产应用中，为了节约性能，JMX代理是通过代码层面适时开启的。

```bash
ssh -o ServerAliveInterval=60 -D localhost:1080 my-user@my-java-server-ip sleep 6000
```

这是没有跳板的，有跳板的和上面通过跳板建立隧道类似配置即可。

随后，我们可以通过jvisualvm的socksProxy功能连接JMX

```bash
jvisualvm -J-DsocksProxyHost=localhost -J-DsocksProxyPort=1080 -J-DsocksNonProxyHosts=
```

之后我们即可添加远程监控

```bash
service:jmx:rmi:///jndi/rmi://127.0.0.1:30301/jmxrmi
```

#### 应用在容器环境，没有SSH

我们的大部分应用都部署在容器环境中，使用`Kubernetes`进行编排，我们知道，大多数容器的image都是没有ssh的，此时我们有两种方式，一是将容器的几个端口映射到物理机，然后通过物理机间接连接，但是容器很多而物理机端口有限，且容器随时可能被调度，所以这种方式比较麻烦，只在燃眉之急时可使用。

比较灵活的方式是通过`Kubernetes`的端口转发功能

```bash
kubectl port-forward 你的pod名称-548f968986-9zg57 30301
```

这样就将容器的30301端口映射到了本地的30301端口，虽然无法解决全部问题，但已经可以做一些基本的监控了



## VisualVM中各类有用参数

在VisualVM中有很多的监控参数，其中有不少有用的信息能够帮助我们定位问题

#### 概览

- 用了哪个JDK（及其目录），在存在多个版本JDK时很有效（which java显示的不一定是当前应用使用的版本）

- JVM运行参数，检查各项业务参数是否配对

- JVM系统属性，包括JVM详细版本，操作系统版本，各类System.setProperty()设置的各类属性

某些情况下，应用无法正常运行是由于各种所谓的“配置项”不正确导致的，包括JDK版本配错，配置的业务模块开关不正确，配置的某业务URL少了半截，某段代码没执行导致System.setProperty()没能正确执行等等。这个时候我们通过概览里就能看出端倪。

#### 基础监控

- CPU情况：显示了应用线程和垃圾回收线程的CPU使用情况

- 堆使用情况：JVM堆的使用情况，通过观察折线图我们能找到大多数问题

- Metaspace（方法区）：类（和常量池）所在区域，这里出问题大多因为反射

- 类装载情况：装载过多也可能是由于反射或不正当的字节码操作

- 线程量情况：线程过多时大多因为使用CacheThreadPool

- 执行垃圾回收：手动执行System.gc()

- 堆Dump：打dump

#### 线程

在创建线程时，一定要为线程设定名称

线程有运行，休眠，等待，驻留，监视几种状态

#### 取样器

// TODO

这个功能是对定位疑难问题最有用的功能

## 在线上环境监控JVM

由于线上环境有严格的网络限制，所以我们不能直接通过SSH代理（在容器内部可能本身都没安装SSH）



#### 通过Kubernetes端口转发

#### 通过VisualVM的socksProxy

## 通过命令查看JVM信息

#### jmap命令

jmap命令是定位Java应用线上问题非常重要的命令，最常见的有3种用法

###### 1、查看当前堆基本情况

可以使用jmap命令查看JVM当前堆使用的大概情况

```bash
jmap -heap Java应用进程ID
```

此时会输出该Java进程的堆栈情况

```java
Attaching to process ID 92968, please wait...
Debugger attached successfully.
// Java进程启动的模式和JVM的版本
Server compiler detected.
JVM version is 25.151-b12

using thread-local object allocation.
// 使用什么GC方式，简单记住CMS低延时，Parallel GC高吞吐，G1万能即可
Parallel GC with 8 thread(s)

// 堆区配置概览
Heap Configuration:
   // JVM堆的最小最大空闲比例
   MinHeapFreeRatio         = 0
   MaxHeapFreeRatio         = 100
   // 堆区能用的最大空间，可以通过-Xmx可配置
   MaxHeapSize              = 268435456 (256.0MB)
   // 新生代（年轻代）当前大小
   NewSize                  = 8388608 (8.0MB)
   // 新生代最大空间
   MaxNewSize               = 89128960 (85.0MB)
   // 年老代（老年代）大小
   OldSize                  = 16777216 (16.0MB)
   // 代表新生代与年老代的比例，此配置表示新生代占总堆内存的三分之一
   // 可以通过-XX:NewRatio配置, 这些配置大多都是-XX:类型（扩展配置）
   NewRatio                 = 2
   // 新生代中的Eden区和Survivor区（from和to区）的比例，此配置表示from区和to区各占新生代的十分之一大小
   SurvivorRatio            = 8
   // 当前MetaSpace区域的大小，随着所占内存增加可以自动进行扩展
   MetaspaceSize            = 21807104 (20.796875MB)
   // 专用于存放Klass数据的内存区域（klass是class文件在JVM中的运行时数据结构）
   CompressedClassSpaceSize = 1073741824 (1024.0MB)
   // 虽然MetaSpace可以自动扩展，但也可以对其进行限制，默认为几乎是无穷大
   // 为了防止Linux操作系统的OOM killer机制，还是建议设置这个区域的大小
   MaxMetaspaceSize         = 17592186044415 MB
   // 伟大的G1收集器中的Region概念，这里没用到
   G1HeapRegionSize         = 0 (0.0MB)

// 堆区的具体使用情况
// 分为新生代、From区、To区、年老代、字符串常量池
Heap Usage:
PS Young Generation
Eden Space:
   capacity = 24641536 (23.5MB)
   used     = 22923920 (21.861953735351562MB)
   free     = 1717616 (1.6380462646484375MB)
   93.02959036319814% used
From Space:
   capacity = 1048576 (1.0MB)
   used     = 589824 (0.5625MB)
   free     = 458752 (0.4375MB)
   56.25% used
To Space:
   capacity = 1048576 (1.0MB)
   used     = 0 (0.0MB)
   free     = 1048576 (1.0MB)
   0.0% used
PS Old Generation
   capacity = 117440512 (112.0MB)
   used     = 45693808 (43.57701110839844MB)
   free     = 71746704 (68.42298889160156MB)
   38.908045632498606% used

21193 interned Strings occupying 1894896 bytes.
```

###### 2、查看对象内存占用情况

可以通过jmap命令查看堆中对象的内存分布情况，一般我们也就看占用大小排前20左右的

```java
jmap -histo Java应用进程ID | head -23
```

```java
 num     #instances         #bytes  class name
----------------------------------------------
   1:        620411       91205776  [C
   2:         57327       24175912  [I
   3:         53925       24044552  [B
   4:        614228       19655296  java.lang.StackTraceElement
   5:        346760        8322240  java.lang.String
   6:        127910        6768432  [Ljava.lang.Object;
   7:         71759        6314792  java.lang.reflect.Method
   8:        194408        6221056  java.util.concurrent.ConcurrentHashMap$Node
   9:         15424        5294144  [Ljava.lang.StackTraceElement;
  10:         21063        3558992  [Ljava.util.concurrent.ConcurrentHashMap$Node;
  11:         43082        3431632  [S
  12:         68418        3284064  org.aspectj.weaver.reflect.ShadowMatchImpl
  13:        110559        2653416  java.lang.StringBuilder
  14:         68418        2189376  org.aspectj.weaver.patterns.ExposedState
  15:         45942        1837680  java.util.LinkedHashMap$Entry
  16:         20158        1773904  org.apache.catalina.session.StandardSession
  17:         43203        1728120  java.util.TreeMap$Entry
  18:         37469        1643240  [Ljava.lang.String;
  19:         14573        1631800  java.lang.Class
  20:         64431        1546344  java.util.ArrayList
```

一般来说，都是各种字面量占用空间最大（字符串、数字等），如果看到业务对象占用内存很靠前，就说明有些问题。

说到占用空间，就不得不说深堆和浅堆的概念，简单来说，浅堆就是单纯指一个对象在物理上占用的内存大小（包括对象头、对象数据），而深堆则是指由于某个对象存在而总共不能释放（保留集）的内存大小。



###### 3、输出堆dump



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
