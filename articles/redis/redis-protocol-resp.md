> 本文地址：https://charpty.com/article/redis-protocol-resp  
> 笔者博客地址： https://charpty.com


为了大家看整体源码方便，我将加上了完整注释的代码传到了我的github上供大家直接下载：
> https://github.com/charpty/redis4.0-source-reading

```RESP```全称为```Redis Serialization Protocol```，是Redis的客户端与服务端进行通信的标准协议。客户端只要按照规则发送简单的几行字符串，服务端的响应同样也是简单的几行字符串，```RESP```看名字就是为```Redis```量身定制的，但是官方也建议可以扩展到其它场景使用。 

```RESP```协议的设计思想依旧和```Redis```一样，追求极致的简单，追求快。所以```RESP```协议具备容易理解、容易解析、容易实现的特点。 ```RESP```使得用户可以使用任何流传输协议连接客户端，比如```TCP```、```Unix Socket```、```Linux Pipeline```，也就是说仅仅使用```nc```命令就可以连接```Redis```并进行日常操作。

## 协议通信模型   

可以说```Redis```的通信模型很简单：**客户端发送一个指令给服务端，服务端接收指令并响应结果给客户端**。这是非常简洁的通信模型，可以说就是简单的**一问一答**。  

但由于```Redis```的特性，有两点例外  
1. 多问一答：```Redis```支持使用```pipeline```将多个指令一次送给服务器并等待响应  
2. 订阅发布：```Redis```也支持消息订阅-发布模型，这时需要服务端主动给客户端发送消息

## 传输格式  

作为一个数据传输协议，```RESP```可以传输以下5种格式的数据   
1. ```Simple Strings```：一行简单字符串如```+OK```，一般为服务器响应OK等字符串  
2. ```Integers```：一个整数，很多命令如```INCR```, ```LLEN```会返回整数  
3. ```Bulk Strings```：其实就是带有前缀参数的字符串，前缀表明了字符串的长度，```L-V```形式，只要读L就知道V的长度  
4. ```Arrays```：这个就是将多种格式打包形成一个数组集合，一次传输多个上述格式的数组  
5. ```Errors```：特殊情况，这是服务端响应的错误信息，一般也为一行字符串如```-WRONGTYPE Operation ...```     

在```RESP```协议中规定，使用第一个字节来区分数据的传输格式，第一个字节的内容代表了后面的数据是何种格式，分别用```'+'```、```':'```、```'$'```、```'*'```、```'-'```来表示上述5种数据传输格式。传输数据都统一使用换行符```"\r\n(CRLF)"```结尾，当然也使用```CRLF```表示另一行。

客户端向```Redis```服务端发送消息时使用的是```Arrays```格式，也就是一个数组集合，数组里元素则都是```Bulk Strings```，也就是```L-V```（字符长度+字符值）形式的字符串。  
服务端响应客户端请求时可以发送的格式就多了，以上5种格式都有可能，这根据具体命令的实现而定。


### Simple Strings  

协议```RESP```使用第一个字节区分传输格式，而```Simple Strings```的第一个字节是```'+'```，所以```Simple Strings```一定是```'+'```号开头，```CRLF```结尾，中间是内容，并且只有一行，也就是有且只有一个```CRLF```。  
注意这个```CRLF```，在```RESP```协议里是强制使用```"\r\n"```作为换行分割的，也就是说单一个```'\n'```是可能出现问题的，会引起不可预见的异常。这也反应了```RESP```协议设计的简单性原则，不愿意过多的在多系统之间纠结，统一约定使用```"\r\n"```。  
最常见的```"+OK\r\n"```就是经典的```Simple Strings```，只有一行且满足```'+'```号开头，```CRLF```结尾，总共就5个字节。  
每种格式都一样，前面第一个标志符和最后的换行符不表示具体业务含义，对上述的```Simple Strings```来说，中间那```OK```两个字才真的具有意义，客户端也仅需要展示```OK```两字。  

### Integers   

整数格式```Integers```就是一行普通的数字，以```':'```开头，以```CRLF```结尾，有且只有一行。  
如```":123\r\n"```就是一个典型的```Integers```响应。  

在```Redis```中有很多响应是整数形式的命令：返回列表长度的```LLEN```、统计字符串字符个数的```BITCOUNT```、原子自增长命令```INCR```、查询KEY剩余有效时间的```TTL```等命令。

### Bulk Strings  

大字符串```Bulk Strings```是一种```L-V```形式的字符串，它以```'$'```开头，紧随其后的是一个数字，这个数字表示了实际的字符串数据有多少个字节，再之后则是一个换行```CRLF```以及后续实际的字符串数据。  

如```"$5\r\nhello\r\n"```就是一个```Bulk Strings```，第一行数据```$5```表示下一行的实际字符串值的长度为5，也就是下一次```read()```函数只要读7个字节(带结束符)就可以了，读取长度明确之后，少去了很多拆包、粘包判断，极大提高了协议解析效率。 

特殊情况是当想表示一个```NULL```串时的场景，空串```""```可以使用```"$0\r\n\r\n"```表示，但我们知道编程语言都有一个和```C```语言```NULL```类似的表示空的常量，在```Java```中是```null```，在```Python```中是```None```，如何告诉程序端这个命令的返回值是一个```NULL```呢。  
协议规定，```Redis```使用```"$-1\r\n"```来表示一个```NULL```串，```Redis```官方还特别提醒了```NULL```串和空串的区别。在```hiredis```客户端中，当服务端响应```NULL```串时展示的结果是```nil```，当服务端响应空串时展示的是```""```。

当命令需要返回一个长串字符时一般都使用```Bulk Strings```传输格式，比如```GET```命令。更多的情况是，```Bulk Strings```作为```Arrays```数组中的元素。

### Arrays   

其实```Redis```交互格式最多的是```Arrays```数组格式，元素基本上都是```Bulk Strings```。  

```Arrays```格式的开始标志是```'*'```，紧接着是一个数字如```*5\r\n```，表示该数组一共有多少个元素，第一行就结束了。接下来就是实际的元素数据，元素数据可以是```Bulk Strings```或```Integers```格式。  
举个例子：```"*3\r\n:1\r\n:55\r\n$4\r\nlike\r\n"```  
这个数组一共3个元素，这个可以从第一行```*3```中知道，第一个元素是一个整数```1```，整数的标记位是```':'```，第二个元素也是个整数，值为```55```，第三个元素则是一个```Bulk Strings```格式，该大字符串一共有4个字节，可以从第四行的```$4```中知道，真实数据值是```like```。

由上可见，```Arrays```格式也就是多个简单格式的组合，数组中的元素的类型可以各不相同，并且，```Arrays```数组是可以**嵌套**的，如下所示，为了展示清楚，我们每个```CRLF(\r\n)```都换下行。
    
``` cpp
*3\r\n  
*3\r\n  
:1\r\n  
:55\r\n  
$4\r\n  
like\r\n  
*2\r\n  
+OK\r\n  
-WRONGTYPE\r\n  
:22\r\n  
```

这个数组一共有三个元素，由第一行的```*3```可知，两个元素的类型是数组，一个是整数。第一个数组就是上面举例的那个数组，第二个元素则是一个包含两个简单字符串的数组，最后一个元素则是一个整数```22```。

和空```Bulk Strings```类似，```Arrays```也使用```-1```来表示```NULL```数组，也就是```"*-1\r\n"```，使用```0```表示空数组，也就是```"*0\r\n"```。当然数组里的元素也可以是```NULL```，如```[1,nil,3]```。

**客户端发送请求**  
客户端向```Redis```服务端发送请求时必须使用```Arrays```格式，且元素格式也只能是```Bulk Strings```，服务器响应格式则是根据具体命令实现而定。  
最经典的```GET a```(a已设值)，通过命令```echo '*2\r\n$3\r\nGET\r\n$1\r\na\r\n' | nc 127.0.0.1 6379```可以得到如下结果```$4\r\ntest```。  
类似的```SET a like```的命令格式则是```*3\r\n$3\r\nSET\r\n$1\r\na\r\n$4\r\nlike\r\n```，返回则是```Simple Strings```格式的 ```+OK\r\n```。

**关于Pipelining**  
服务端支持客户端一次性发送多个命令给服务端，由服务端一次性执行并一次性返回结果，类似```SET a 1;INCR a;GET a```，返回```OK;2;2```，也就是所谓的流水线```Pipeling```。  
其实```Pipeling```的实现就是嵌套```Arrays```，我想通过签名嵌套数组的描述不难理解。

### Errors   

错误格式```Redis```专门定义了一种格式用来传递错误信息，这种格式几乎和```Simple Strings```一样，唯一的区别是```Errors```第一个标记字符是```'-'```，而中间的字符串内容就是具体的错误信息。 
 
一般来说错误信息分为两段，第一段是一个单词，比如：```ERR```、```WRONGTYPE```，第一段是对这次错误的整体概述，也可以说是一个错误类型，像是错误编码。```Redis```官方称之为```Error Prefix```。第一段之后紧接着就是一个空格，然后就是第二段。
第二段就是具体的错误信息，帮助客户端理解服务器出错具体原因。

错误发生的情况有很多：  
1. 当你用```GET```命令操作一个```List```时，将返回```-WRONGTYPE Operation against a key holding the wrong kind of value```。  
2. 当你随意输入一个命令```abc```时，将返回```-ERR unknown command 'abc'```。  
3. 当使用```GETBIT```的offset参数输入一个负数时，将返回```-ERR bit offset is not an integer or out of range```

### Inline Commands   

内置命令并不是一种标准格式，它更多的是一种解析手段，主要是为了方便没有```Redis```客户端的场景，手里只有```nc```命令或者```telnet```，这个时候让用户手敲一段```*2\r\n$3\r\nGET\r\n$1\r\na\r\n```来实现```GET a```实在有点强人所难。  
所以```Redis```实现了一种所谓内置命令的形式的格式，让用户直接输入```GET a```也依然能够返回结果信息。  
几乎所有命令都支持以内置命令形式发送并解析，大多数常用且简单的命令，如```SET```、```GET```、```LPUSH```、```PING```等都是支持的，唯一的区别是内置命令支持的长度是有限的，一次性发送过长的字节可能会丢失。  

所以发送命令就两种形式，一种是元素为```Bulk Strings```的数组，一种是内置命令。  


## 协议实现  

协议```RESP```在```Redis```并没有个专门的```C```文件实现，而是主要包含在网络字节流处理过程中，这也是由于```RESP```本身足够简洁，不需要一个专门的解释器。  
所以也就是说主要实现都在```networking.c```文件中，实现分为两部分，一部分是接收字节流请求，并处理为```Redis```内部的数据结构，供具体命令实现函数调用；另一部分是将```Redis```内部的数据结构转换为字节流输出到客户端。  
接收请求的处理函数的名称大多为```process*```，响应客户端的处理函数的名称大多为```addReply*```。 

### 接收请求并解析
处理请求的函数入口是```processInputBuffer()```，它有两条分支：内置命令？```processInlineBuffer()```:```processMultibulkBuffer()```。也就是通过区分字节流第一个字符是不是```*```(```Arrays```格式标志)来调用不同的函数解析请求。

当第一个字节是```*```时当普通命令处理，其它则都认为是内置命令。  

#### 内置命令解析
内置命令解析由```processInlineBuffer()```函数实现   


``` cpp
/*
 * 尝试解析字节流为内置命令，最重要的是解析出第一个单词(命令)
 * 解析成功返回0，解析失败或还未读取完成返回-1
 */
int processInlineBuffer(client *c) {
...变量定义...

// 实际上RESP协议定制的分隔符必须是'\r\n'，这也反应了协议的设计原则之一简单
newline = strchr(c->querybuf,'\n');

// 如果没有CRLF则直接认为这串字节流还未读取完成，返回-1并在外循环再读取
if (newline == NULL) {
    // 不能无休止读取字节流
    if (sdslen(c->querybuf) > PROTO_INLINE_MAX_SIZE) {
        addReplyError(c,"Protocol error: too big inline request");
        setProtocolError("too big inline request",c,0);
    }
    return C_ERR;
}

// 处理'\r\n'，newline往前移一个字符
if (newline && newline != c->querybuf && *(newline-1) == '\r')
    newline--;

// 计算实际有效字节流长度并将其转换SDS字符串
querylen = newline-(c->querybuf);
aux = sdsnewlen(c->querybuf,querylen);
// 将字符串分割为一组入参，该函数里包含了各种空格、水平制动符、换行符的处理
// RESP内置命令来讲就是以空格分割字符串，其中分割后的第一个字符串就是命令名称
// 后续也就是根据这个命令名称到'redisCommandTable'中查找具体命令执行函数
argv = sdssplitargs(aux,&argc);
sdsfree(aux);
// 这里设计就稍显丑陋了'sdssplitargs()'函数返回NULL时一定就是因为字符串中引号数量不对
if (argv == NULL) {
    addReplyError(c,"Protocol error: unbalanced quotes in request");
    setProtocolError("unbalanced quotes in inline request",c,0);
    return C_ERR;
}

// 空命令被设定为从节点向主节点更新最后ACK时间的一种手段
if (querylen == 0 && c->flags & CLIENT_SLAVE)
    c->repl_ack_time = server.unixtime;

// 可以使用'\r\n'分割一次性传递多个命令过来
// 所以丢弃掉已处理完成的字符串，再次走外循环处理剩下的
sdsrange(c->querybuf,querylen+2,-1);

// 如果解析出来的参数不为空则将参数转换为robj结构体
// Redis中的键、值、参数、配置等都是使用robj结构体表示，用于提高操作灵活度和编程通用性
if (argc) {
    if (c->argv) zfree(c->argv);
    c->argv = zmalloc(sizeof(robj*)*argc);
}

// 循环将参数转换为robj结构体，方便后续操作
for (c->argc = 0, j = 0; j < argc; j++) {
    if (sdslen(argv[j])) {
        c->argv[c->argc] = createObject(OBJ_STRING,argv[j]);
        c->argc++;
    } else {
        sdsfree(argv[j]);
    }
}
// 释放SDS数组
zfree(argv);
return C_OK;
}
```

#### 普通命令解析
普通命令解析由```processMultibulkBuffer()```函数实现     

``` cpp

/*
 * 解析普通Redis命令，普通命令格式为: Bulk String数组，这是RESP协议中的一种标准格式
 * 当字节流第一个字节为'*'时就认为是普通命令，也就会调用该函数来尝试解析参数
 * 解析成功返回0，解析失败或还未读取完成-1
 */
int processMultibulkBuffer(client *c) {
...变量定义...

// 外循环的第一次读取字节流，此时需要获取数组中元素的个数
if (c->multibulklen == 0) {
    // 都还未读取过，c->argc当然是0
    serverAssertWithInfo(c,NULL,c->argc == 0);

    // 不论是内置命令还是RESP任何传输格式，都是使用'\r\n'作为分割
    // 使用单'\n'或者'\r'等都会引发不可预料的异常
    newline = strchr(c->querybuf,'\r');
    // 和内置命令一样，未读取完则返回让外循环继续读取，但限制最大读取长度
    if (newline == NULL) {
        if (sdslen(c->querybuf) > PROTO_INLINE_MAX_SIZE) {
            addReplyError(c,"Protocol error: too big mbulk count string");
            setProtocolError("too big mbulk count string",c,0);
        }
        return C_ERR;
    }

    // 解析实际命令长度，也就是第一行中'*'号的数字，最长为1M个元素
    ok = string2ll(c->querybuf+1,newline-(c->querybuf+1),&ll);
    if (!ok || ll > 1024*1024) {
        return C_ERR;
    }

    pos = (newline-c->querybuf)+2;
    // 这一个普通命令是个空命令，直接跳过
    if (ll <= 0) {
        // 去除掉已经解析过的字节，让外循环开始解析接下来的字节
        sdsrange(c->querybuf,pos,-1);
        return C_OK;
    }

    // 整个if逻辑最重要的就是计算出整个数组有多少个元素
    c->multibulklen = ll;

    if (c->argv) zfree(c->argv);
    // 请求数组元素的个数也就是请求参数的个数
    c->argv = zmalloc(sizeof(robj*)*c->multibulklen);
}

// 循环处理各个元素，也就是各Bulk Strings
while(c->multibulklen) {
// 读取Bulk Strings的实际字符串长度，也就是该元素第一行'$'符号后面的数字
if (c->bulklen == -1) {
    newline = strchr(c->querybuf+pos,'\r');
    if (newline == NULL) {
        ...长度检查...
        break;
    }

   ...格式检查...

    // 把Bulk Strings格式的长度读出来，这样可以一次性就取出实际字符串
    ok = string2ll(c->querybuf+pos+1,newline-(c->querybuf+pos+1),&ll);
    if (!ok || ll < 0 || ll > server.proto_max_bulk_len) {
        addReplyError(c,"Protocol error: invalid bulk length");
        setProtocolError("invalid bulk length",c,pos);
        return C_ERR;
    }

    pos += newline-(c->querybuf+pos)+2;
    // 当发现字符串的长度值很大(大于64K)，为了防止拷贝则直接使用buffer中的字节
    if (ll >= PROTO_MBULK_BIG_ARG) {
        size_t qblen;

        // 将当前字符串起以及后面的其它全部字节作为一个新的SDS
        sdsrange(c->querybuf,pos,-1);
        pos = 0;
        qblen = sdslen(c->querybuf);

        // 除了字符串本身还需要存放'\r\n'
        if (qblen < (size_t)ll+2)
            c->querybuf = sdsMakeRoomFor(c->querybuf,ll+2-qblen);
    }
    c->bulklen = ll;
}

if (sdslen(c->querybuf)-pos < (size_t)(c->bulklen+2)) {
    // 半包读取场景，返回到外循环继续读取剩下字节
    break;
} else {
    // 如果说恰好当前buffer仅剩下一个元素，且是个较长的字符串
    // 那么就直接使用buffer来表示字符串，形成robj结构体，避免内存拷贝
    // 这种场景还是比较常见的，所以可能长的参数尽量放在最后一个，也尽量避免粘包场景
    if (pos == 0 &&
        c->bulklen >= PROTO_MBULK_BIG_ARG &&
        sdslen(c->querybuf) == (size_t)(c->bulklen+2))
    {
        c->argv[c->argc++] = createObject(OBJ_STRING,c->querybuf);
        sdsIncrLen(c->querybuf,-2); /* remove CRLF */
        // 预测下一个元素也是类似的场景
        c->querybuf = sdsnewlen(NULL,c->bulklen+2);
        sdsclear(c->querybuf);
        pos = 0;
    } else {
        // 直接将buffer中字节拷贝出来构建新的robj结构体
        c->argv[c->argc++] =
            createStringObject(c->querybuf+pos,c->bulklen);
        pos += c->bulklen+2;
    }
    c->bulklen = -1;
    c->multibulklen--;
}
}

// 保证丢弃调已经处理过的字节
if (pos) sdsrange(c->querybuf,pos,-1);

// 如果数组里的元素都处理完毕返回0，否则代表还剩余元素没处理完
if (c->multibulklen == 0) return C_OK;

// 继续回到外循环接着处理
return C_ERR;
}

```


### 组装响应格式
和解析```RESP```传输格式一样，组装响应格式并输出的工作也是在```networking.c```中完成。将已知结构体解析为字节流肯定比从字节流解析出结构体要简单的多，少了很多不可预知性。所以如果不谈不深究网络交互，只将```RESP```传输格式组装还是简单易懂的。

#### 组装Bulk Strings数组结果
``` cpp
/*
 * 组装Bulk Strings格式输出到客户端
 *
 * 参数列表
 *      1. c: 客户端指针
 *      2. s: 待输出的大字符串
 */
void addReplyBulkSds(client *c, sds s)  {
    // 首先添加第一行，表明大字符串的长度，如"$27"表示实际字符串有27个字节
    addReplyLongLongWithPrefix(c,sdslen(s),'$');
    // 将字符串原模原样写出输出buffer中
    // 其调用的是更底层的字节输出函数addReplyBulkCBuffer()
    addReplySds(c,s);
    // 添加末尾的'\r\n'
    addReply(c,shared.crlf);
}
```
当比如要想返回一个字符串列表时，只要配合上设置数组长度的函数```addReplyMultiBulkLen()```即可(其实数组也就是开头有一个```*number```表示数组长度)。   

``` cpp
// 先设置好数组的长度
addReplyMultiBulkLen(c,len);
while(len--) {
      if (输出字符串实际值) {
          addReplyBulkCBuffer(c,value,len);
      } else {
      		// 如果是输出大字符串前缀长度,$number
          addReplyBulkLongLong(c,len);
      }   
    }   

```

#### 组装简单字符串结果
简单字符串是以'+'号开头，但在```Redis```实现中```Simple Strings```并不全是组装而来的，而是直接输出已经预定好的字符串。像```"+OK\r\n"```、```"+PONG"```这些都是预定义好了的字符串。  
这些预定义的字符串都存在```server.c```的```sharedObjectsStruct```结构体，属性名为```shared```，它的初始化在```createSharedObjects()```函数中。 

``` cpp
void createSharedObjects(void) {
    shared.crlf = createObject(OBJ_STRING,sdsnew("\r\n"));
    shared.ok = createObject(OBJ_STRING,sdsnew("+OK\r\n"));
    shared.err = createObject(OBJ_STRING,sdsnew("-ERR\r\n"));
    shared.emptybulk = createObject(OBJ_STRING,sdsnew("$0\r\n\r\n"));
    shared.czero = createObject(OBJ_STRING,sdsnew(":0\r\n"));
    shared.nullbulk = createObject(OBJ_STRING,sdsnew("$-1\r\n"));
    shared.nullmultibulk = createObject(OBJ_STRING,sdsnew("*-1\r\n"));
    shared.emptymultibulk = createObject(OBJ_STRING,sdsnew("*0\r\n"));
    shared.pong = createObject(OBJ_STRING,sdsnew("+PONG\r\n"));
    shared.queued = createObject(OBJ_STRING,sdsnew("+QUEUED\r\n"));
	 ...其它共享变量初始化...
	 }
``` 
组装```Simple Strings```的函数为```addReplyStatusLength()```，比较简单就不描述了。

## 总结
协议```RESP```设计的原则是简单易解析，所以在通用性方面不能顾及的特别全，比如一定要使用```'\r\n'```而不能使用```'\n'```，但是与其增加一堆复杂逻辑处理这种场景不如大家都遵守默认约定。  
我想这种**简单**的原则也是```Redis```如此高效且受欢迎的原因吧。

