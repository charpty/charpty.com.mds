WebSocket协议以及STOMP子协议解析与实战

公司项目某在线聊天模块用到了```Spring WebSocket```，测试部门需要编写一个不依赖第三方模块的```python```脚本对该聊天模块进行测试。  
照例先找了现有的```python module```进行参考，虽不能直接使用却有很大的收益，现有的第三方模块对```WebSocket```协议有一定支持，对```STOMP```子协议的支持相对比较欠缺，特别是对于```Spring WebSocket```带自定义标示符的情况支持更差。   


在参考了```RFC```、```python```版本的```websocket-client```项目[(github)](https://github.com/websocket-client/websocket-client)、```spring-framwork/spring-websocket```项目源码中的测试用例之后，我开始自行编写一个协议客户端，要编写一个完善可靠的协议客户端是比较困难的，好在我们只是做测试，只要路能走通即可。


## WebSocket协议

```WebSocket```协议使得服务端可以随时向客户端推送消息，现在大多数浏览器都已支持，对于即时通讯、消息推送等应用有很大帮助。

如果有时间，可以看下```WebSocket```的```RFC```：```https://tools.ietf.org/html/rfc6455```，直接翻到```5.2.  Base Framing Protocol```，可以省去很多麻烦。  
<pre>
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-------+-+-------------+-------------------------------+
 |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
 |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
 |N|V|V|V|       |S|             |   (if payload len==126/127)   |
 | |1|2|3|       |K|             |                               |
 +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
 |     Extended payload length continued, if payload len == 127  |
 + - - - - - - - - - - - - - - - +-------------------------------+
 |                               |Masking-key, if MASK set to 1  |
 +-------------------------------+-------------------------------+
 | Masking-key (continued)       |          Payload Data         |
 +-------------------------------- - - - - - - - - - - - - - - - +
 :                     Payload Data continued ...                :
 + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
 |                     Payload Data continued ...                |
 +---------------------------------------------------------------+
</pre>

和解释TCP协议数据包一样，此	```RFC```也给出了结构图，在我看来一共分为4块

### 标记块
第一个字节8位属于标识符，一共标示5个信息

1. 第一位：表示该块是否是结束块，是结束块就不用read了，否则一直read到结束块为止
2. RSV1、2、3：默认至0，用于给协议实现者自定义用途，在```Spring WebSocket```使用RSV1表示是否使用```GZIP```压缩
3. opcode：表示这个数据包的数据类型，有```TEXT```、```BINARY```、```PING```等等，大多数情况下用的都是文本消息


### 掩码与业务数据长度
第二个字节的第一位表示的是后续的业务数据是否被掩码异或处理过了，客户端向服务端发送数据时，mask必须为1，也就是客户端必须将数据尽心掩码异或操作。 
 
后续7位表示的是业务数据的长度，且称其为X，分为3种情况。 

1. X值小于126: 那么业务数据的长度就是X
2. X值等于126: 那么业务数据长度是接下来两个字节表示的```short```数字的大小
3. X值等于127: 那么业务数据长度就是接下来八个字节表示的```long```数字的大小


### 随机掩码
如果mask标记位为0，则不需要这额外的4位，如果掩码mask被设置1，那么就必须提供4位掩码，可以是随机的4个```byte```，在客户端向服务器发送消息时必须提供，后面掩饰时我们将掩码设置为```0x00 0x00 0x00 0x00```。

### 业务数据块与子协议
接下来的就是业务数据块了，```WebSocket```数据帧是典型的```T-L-V```格式的数据结构，业务数据的长度在前面已经得到，这里只需```read```相应个字节的数据即可。

业务数据的格式完全是实现者自定义的，你想使用```1```代表显示“您好”，```2```代表“再见”也没问题，但是意义不大。为了能够通用、易解析的表达双方意图，就必须定义具体业务数据通信的子协议。

也就是说```WebSocket```协议只是规定了连接建立握手过程、安全保证、数据块承载方式等，它并没有规定业务数据如何通信，业务数据的通信可以使用很多方式，比如就前面说的```1```、```2```，那就是纯粹的私有协议。```WebSocket```没有专门的子协议（但出名的子协议应该向WebSocket注册--rfc5226），业务数据格式完全自由，所以可以使用许多我们目前本来就在进行消息通信的协议，如：```HTTP```、```STOMP```、```JSON-RPC```、```AMQP```等，本质上只要是通过文本交互不依赖语言特性的任何协议都可以。

### STOMP协议
其中```STOMP```-- ```Simple (or Streaming) Text Orientated Messaging Protocol``` 协议是```Spring WebSocket```采用的协议，```Spring```官方这样说道：
<pre>
The Spring Framework provides support for using STOMP — a simple, messaging protocol 
originally created for use in scripting languages with frames inspired by HTTP.
STOMP is widely supported and well suited for use over WebSocket and over the web.
</pre>
现在非常流行使用```STOMP```作为```WebSocket```业务数据通信的子协议。

```STOMP```是一个和```HTTP```格式很像的协议，它的格式分为：
  
``` 
COMMAND
header1:value1
header2:value2

Body^@
``` 
第一行是命令行，接下来是请求头，再接下来是请求体，最后带有```\0```结尾，和```HTTP```如出一辙，实际上它也就是参考```HTTP```来设计的。
COMMAND的命令不少，```CONNECT```、```CONNECTED```、```SUBSCRIBE```、```SEND```、```MESSAGE```这几个都是最常用的，分别用于连接服务器、服务器告诉客户端已连接、客户端向服务端订阅频道、客户端向服务端发送消息，服务端向客户端推送消息。

注意客户端的命令和服务端的命令是分开的，比如同样是发送消息就一个是```SEND```，另一个是```MESSAGE```。

举个例子，```WebSocket```协议是异步通信逻辑，使得服务端随时可以向客户端推送消息，但是服务端也不能什么消息都推给每个客户端，所以客户端需要订阅频道，告诉服务端它对哪些消息感兴趣。

```
SUBSCRIBE
id:0
destination:/buy/food
ack:client

^@
```
表示只接收```/buy/food```路径（频道）的消息，在```Spring WebSocket```中利用```@MessageMapping、@SendToUser```指明接收消息路径与推送消息路径，有一对一和广播等情况。

```STOMP```子协议不复杂，但还有许多的命令和交互方式，就不细说了，后面的代码仅需要了解上面提到的几个命令即可，更多可以参考：```https://stomp.github.io/```

大家可能也发现了，```STOMP```规定了命令行、请求头，但是body还是没说，body使用什么格式解析呢？
首先，许多命令没有body，如```CONNECT```、```CONNECTED```、```SUBSCRIBE``，其次有body的命令则又是自由风格body，你想使用什么格式做业务数据都行。
```STOMP```解决了消息“意义”的问题，具体业务数据格式还是自己造，到这里我们只要关心自己的业务数据意义即可，其它的两个协议已经帮我们解决了。
我们可以在客户端使用空格代表分隔符，拼装业务数据，在服务端用空格解析开来，只要双方约定好即可。

在```Spring WebSocket```与```SockJS``实现中采用```JSON```风格的业务数据格式，```JSON```是大家再熟悉不过了。

致此，我们已经能够得到一条完整的明文消息了，比如向服务端发送一句话：

```
SEND
destination:/app/cha
content-length:32
{"type":"text","message":"你好"}^@
```
当然这只是明文消息，也只是业务payload这一部分，还要组装成```WebSocket```帧Frame才能发送给服务器。


## Spring STOMP实现
在编写测试客户端的代码之前，还需要先了解下Spring对于```STOMP```的实现，对于```WebSocket```协议，```Spring```利用```Tomcat```、```Jetty```等容器的原生实现进行了封装。

值得注意的是，为了兼容部分不支持```WebSocket```的浏览器，```JS```提供了一套网络库API -- ```SockJS```，所以可以看到

对于```STOMP```协议，由于本身也比较简单，所以Spring自行实现了这一套逻辑，进行拼装。





