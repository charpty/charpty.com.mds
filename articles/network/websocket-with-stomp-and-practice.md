公司项目某在线聊天模块用到了```Spring WebSocket```，测试部门需要编写一个不依赖第三方模块的```python```脚本对该聊天模块进行测试。  
照例先找了现有的```python module```进行参考，虽不能直接使用却有很大的收益，现有的第三方模块对```WebSocket```协议有一定支持，对```STOMP```子协议的支持相对比较欠缺，特别是对于```Spring WebSocket```带自定义标示符的情况支持更差。   


在参考了```RFC```、```python```版本的```websocket-client```项目[(github)](https://github.com/websocket-client/websocket-client)、```spring-framwork/spring-websocket```项目源码中的测试用例之后，我开始自行编写一个协议客户端，要编写一个完善可靠的协议客户端是比较困难的，好在我们只是做测试，只要路能走通即可。


## WebSocket协议   

2011年成为标准的```WebSocket```协议使得服务端可以随时向客户端推送消息，现在大多数浏览器都已支持，对于即时通讯、消息推送等应用有很大帮助。

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

其实```STOMP```是一个和```HTTP```格式很像的协议，它的格式分为：
  
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

虽然```STOMP```协议并不复杂，但还有许多的命令和交互方式，就不细说了，后面的代码仅需要了解上面提到的几个命令即可，更多可以参考：```https://stomp.github.io/```

大家可能也发现了，```STOMP```规定了命令行、请求头，但是body还是没说，body使用什么格式解析呢？
首先，许多命令没有body，如```CONNECT```、```CONNECTED```、```SUBSCRIBE``，其次有body的命令则又是自由风格body，你想使用什么格式做业务数据都行。
我们看到，```STOMP```解决了消息“意义”的问题，具体业务数据格式还是自己造，到这里我们只要关心自己的业务数据意义即可，其它的两个协议已经帮我们解决了。
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


## Spring WebSocket实现
在编写测试客户端的代码之前，还需要先了解下Spring对于```STOMP```的实现，对于```WebSocket```协议，```Spring```利用```Tomcat```、```Jetty```等容器的原生实现进行了封装。各种容器都以```Adapter```形式提供服务，如```JettyWebSocketHandlerAdapter```、```StandardWebSocketHandlerAdapter```等。

值得注意的是，为了兼容部分不支持```WebSocket```的浏览器，```JS```提供了一套网络库API -- ```SockJS```，所以在```Spring```中可以看到```AbstractSockJsSession```等类，正是为```SockJS```定制的，实际上，大多数情况下都是要兼容浏览器的，所以```SockJS```非常流行，包括我们需测试的项目，也是使用的```SockJS```。

其实，```SockJS```就是用于给不支持```WebSocket```的浏览器模拟```WebSocket```通信，它也是一个底层通信协议。```Spring```对于```SockJS```有对应的实现，也是```SockJS```指定的官方实现，包括服务端和客户端。```SockJS```是模仿```WebSocket```的，所以通信方式、数据帧都是非常相似的。

对于我们来说，唯一要注意的就是对于payload的处理，```SockJS```仅接收4中Frame，打开--o、心跳--h、数组消息--a、关闭--c。另外三种都比较简单，我们唯一关心的是发送消息，也没有太大的变化，只是将消息外面加了一个数组包起来。

```
"message" ->  a["message"]
```
我们只需要知道```SockJS```在我们的body消息体外加了一层数组即可，另外的还是参照和前面讲的```WebSocket```和```STOMP```。

除此之外，```SockJS```还要求支持许多默认的页面与端口为客户端提供信息，更多的信息可以查看：```https://github.com/sockjs/sockjs-protocol```。

对于```STOMP```协议，由于本身也比较简单，所以Spring自行实现了这一套逻辑进行拼装，其属于```spring messaging```大家族的一员，```StompSubProtocolHandler```是其主处理主要逻辑。


## Python客户端

### 主流程
主流程分为几个路程

```
升级HTTP连接 -> 协商WebSocket协议版本号 -> 启动接收线程 -> 订阅频道 -> 发送消息
```

代码示例如下

```
def main():
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.connect(('localhost', 8080))

    # 首先是建立连接，通过UPGRADE请求将"HTTP连接"升级为"WebSocket连接"
    sk.send(UPGRADE_REQUEST)
    time.sleep(1)
    # 正常升级连接则返回101状态码
    print "UPGRADE_REQUEST: " + sk.recv(4096)

    # WebSocket的connect，双方协商该使用的WebSocket协议版本号，同时约定心跳策略
    command = make_command(CONNECT_COMMAND)
    sk.send(command)

    # 启动接收消息线程
    t = threading.Thread(target=receive_action, args=(sk,))
    t.setName("socket receive")
    t.start()

    # 订阅感兴趣的频道
    command = make_command(SUBSCRIBE_COMMAND)
    sk.send(command)

    # 发送消息
    command = make_chat_command("jack")
    sk.send(command)

    while True:
        name = raw_input("what's your name?")
        command = make_chat_command(name)
        sk.send(command)

    t.join()
```

几个COMMAND字符串已经预先定义好了

```
# 一个普通的HTTP请求，带上Host以及升级为WebSocket连接必要的几个header
# 在测试中没有必要启用gzip压缩
# "Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits=15\r\n"
UPGRADE_REQUEST = "GET /gs-guide-websocket/382/4ekj1wpx/websocket HTTP/1.1\r\n" \
                  "Host: localhost:8080\r\n" \
                  "Sec-WebSocket-Key: Wge6UZ+MyDoA1swg1UaZqg==\r\n" \
                  "Sec-WebSocket-Version: 13\r\n" \
                  "Upgrade: websocket\r\n" \
                  "Connection: Upgrade\r\n" \
                  "\r\n"

# 告诉服务器我们支持的版本有1.2、1.1、1.0，服务器一般会选最高可支持版本
CONNECT_COMMAND = "[\"CONNECT\\n" \
                  "accept-version:1.2,1.1,1.0\\n" \
                  "heart-beat:1000,1000\\n" \
                  "\\n\u0000\"]"

# 我们订阅/topic/greetings，Spring WebSocket示例中会往这个频道发送消息
SUBSCRIBE_COMMAND = "[\"SUBSCRIBE\\n" \
                    "id:0\\n" \
                    "destination:/topic/greetings\\n" \
                    "\\n\u0000\"]"

# Spring WebSocket示例中往这个路径发送name会返回hello, name
CHAT_COMMAND_FORMAT = "[\"SEND\\n" \
                      "destination:/app/hello\\n" \
                      "content-length:%s\\n\\n" \
                      "{\\\"name\\\":\\\"%s\\\"}\u0000\"]"
```

其中建立连接的请求UPGRADE_REQUEST是一切的开始，其中```"Sec-WebSocket-Version"```头表示客户端版本兼容性，目前客户端版本为13，```Sec-WebSocket-Key```则用于安全校验，服务器需返回一个正确的校验后的字符串，双方方能建立连接。

另外可以使用```"Sec-WebSocket-Protocol"```告知服务器客户端能支持哪些通信子协议，若无此header则有服务器自行选择。


### 客户端拼装消息
客户端需要将文本消息经过掩码处理、进制处理、拼装等操作得到相应的字节流再发给服务器。

主要是两个步骤，一个是掩码处理业务数据payload，没有多余的操作，只是将业务数据每个字节逐一与掩码MY_MASK进行异或

```
MY_MASK = [0x00, 0x00, 0x00, 0x00]

def mask_payload(payload):
    mask_index = 0
    result = ""
    for c in payload:
        mask = MY_MASK[mask_index] & 0xFF
        c_int = ord(c)
        after_mask = (mask ^ c_int)
        result = result + chr(after_mask)
        mask_index = mask_index + 1
        if mask_index == 3:
            mask_index = 0
    return result

```
第二个步骤是制造消息的```WebSocket```协议头

```
def make_frame(payload):
    # 我们构造时都让长度小于65536
    p_len = len(payload)
    if p_len < 126:
        # 第二字节后7位就是表示payload长度
        mask_p_len = p_len | 0x80
        data_format = 'B' + 'B' + 'BBBB' + str(p_len) + 's'
        # 需要了解下python的struct模块
        frame = struct.pack(data_format, 129, mask_p_len, MY_MASK[0], MY_MASK[1], MY_MASK[2], MY_MASK[3], payload)
    elif p_len < 65536:
        # 之后的两个字节才是长度
        # mask_p_len = ((126 | 0x80) << 16) + p_len
        mask_flag = 126
        data_format = 'B' + 'BH' + 'BBBB' + str(len(payload)) + 's'
        frame = struct.pack(data_format, 129, mask_flag, p_len, MY_MASK[0], MY_MASK[1], MY_MASK[2], MY_MASK[3], payload)
    else:
        raise ValueError("这只是测试请不要发过长的内容")

    return frame
```

总的拼装流程就是结合前面两步  

```
# 1、第一个8位：1000 0001 代表发送文本消息，且是结束块
# 2、第二个8位：1X，X为负载数据的长度，无扩展数据情况下即指业务payload的长度，1代表该文本已经过mask处理，客户端送数据必须mask
# 3、接下来的32位：随机的4字节掩码，我们就全部使用0好了
# 4、业务数据
def make_command(payload):
    payload = mask_payload(payload)
    frame = make_frame(payload)
    return frame

```

注意发送消息时需要先格式化处理下消息内容，替换为自己想要说的话

```
def make_chat_command(name):
    chat_command = CHAT_COMMAND_FORMAT % ((11 + len(name)), name)
    final_command = make_command(chat_command)
    return final_command
```

拼装好了消息之后，就可以给服务器发送消息了，服务器根据数据指定的解析规则也就可以正确解析消息了。

### 解析服务器消息
在我们给服务器发送完消息之后，服务器也会有所回应，服务器回应的数据也是经过处理的，需要解析，处理方式和我们之前拼装给服务器的数据的处理方式是一样的，所以我们只需要将之前拼装的步骤倒过来处理一遍就可以了。

```
def receive_loop(sk, buf):
    # websocket是T-L-V格式的消息，大概是第一个字节表示类型，第二个字节表示长度，后续为具体数据
    buf = buf + sk.recv(4096)
    # 第一个byte一般都为1100 0001，表示fin结束块，rsv1=使用zlib压缩，文本消息
    # 高位1表示fin结束块，第二高位位1表示zlib压缩（spring自定义），末位为消息类型，一般都是1表示文本消息
    if buf is None:
        time.sleep(1)
        return
    flags = ord(buf[0])
    fin = flags >> 7
    # 不是结束块，那就还没读完
    if fin == 0:
        return
    # 是否使用gzip压缩
    is_compress = rsv1 = (flags & 0x40) >> 6
    # rsv2、rsv3目前都是保留使用
    # rsv2 = (flags & 0x20) >> 5
    # rsv3 = (flags & 0x10) >> 4
    mask_payload_len = ord(buf[1])
    # 是否使用掩埋异或，从客户端送过去消息是必须使用mask的，服务端发给客户端则不需要
    mask = mask_payload_len >> 7
    # 我们送过去是要求不mask的，所以这里不判断mask了，mask=0，mask_key为空，所以这里就不用取4位mask_key了
    payload_len = mask_payload_len & 0x7F
    # payload_len小于126的为实际长度，等于126时代表后两个byte才是真实长度，等于127代表后八哥byte才是真实长度
    payload_start = 0
    if payload_len < 126:
        payload_start = 2
    elif payload_len == 126:
        len_s = buf[2:4]
        # 处理字节序为大端字节序
        payload_len = struct.unpack('>H', bytes(len_s))[0]
        payload_start = 4
    elif payload_len == 127:
        len_s = buf[2:10]
        payload_len = struct.unpack('>Q', bytes(len_s))[0]
        payload_start = 10
    # payload还没读完整
    if len(buf) < payload_start + payload_len:
        return
    payload = buf[payload_start:(payload_start + payload_len)]
    # 大端字节序处理，不处理也可，在Spring WebSocket中已处理
    payload = struct.unpack('>' + str(payload_len) + 's', payload)[0]
    buf = buf[(payload_start + payload_len):]
    # 需要解压的时候，我们在建立WebSocket时已经指定了不需要解压，这里不会走到
    if is_compress == 1:
        payload = decompress_gzip_payload(payload)
    log_payload(payload)
```

这一段看上去比较绕，但其实就是刚才拼装的动作的逆过程，能明白拼装过程也一定能明白解析过程。

完整的代码示例 -> 请下载

## 总结
当然了，```WebSocket```还有很多的变化和更细节的东西，我们说的都是比较常用的，如果需要了解更多还是参考```RFC```比较准确，也可以看看```Spring WebSocket```的实现代码，实战之后印象更加深刻。

用到才去深究，没有用到的时候可以大致了解下即可，把时间花在更需要的地方。



