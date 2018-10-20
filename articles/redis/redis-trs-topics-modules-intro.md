## Redis模块化介绍意译与解析

>> https://redis.io/topics/modules-intro

纯翻译意思，意思意思D-+，解析难懂之处，并提供更多的代码示例帮助理解。


```
Redis Modules: an introduction to the API
The modules documentation is composed of the following files:

INTRO.md (this file). An overview about Redis Modules system and API. It's a good idea to start your reading here.
API.md is generated from module.c top comments of RedisMoule functions. It is a good reference in order to understand how each function works.
TYPES.md covers the implementation of native data types into modules.
BLOCK.md shows how to write blocking commands that will not reply immediately, but will block the client, without blocking the Redis server, and will provide a reply whenever will be possible.
Redis modules make possible to extend Redis functionality using external modules, implementing new Redis commands at a speed and with features similar to what can be done inside the core itself.

Redis modules are dynamic libraries, that can be loaded into Redis at startup or using the MODULE LOAD command. Redis exports a C API, in the form of a single C header file called redismodule.h. Modules are meant to be written in C, however it will be possible to use C++ or other languages that have C binding functionalities.

Modules are designed in order to be loaded into different versions of Redis, so a given module does not need to be designed, or recompiled, in order to run with a specific version of Redis. For this reason, the module will register to the Redis core using a specific API version. The current API version is "1".

This document is about an alpha version of Redis modules. API, functionalities and other details may change in the future.
```
### Redis模块化概要介绍

本文章用于介绍Redis模块，分为以下几个文件

INTRO.md（当前文件），Redis模块化的概要介绍，先读这个比较好。   
API.md，介绍Redis的模块化提供的所有API，每个函数都有详细介绍。   
BLOCK.md，这个就厉害了，介绍写一个阻塞客户端但不阻塞服务器的命令。   

Redis内部命令的实现也使用了模块化，这种模式使得可以方便的自定义扩展模块，扩展的模块也可以方便的利用Redis中本来只能内部使用的优良特性。

Redis的模块化主要利用的是动态库（Windows的dll、Linux的so）特性，想实现自己的模块，需要实现```redismodule.h```头文件，用C和C++或其他语言写都行，只要最后能编译成so文件就可以。

Redis还是比较有良心的，模块化API不会大的调整或者会做高版本兼容，所以写好一个模块，一次编译好了就可以在多个Redis版本中使用而勿须改代码或重新编译。

这个文件是初代版本的文档，后续会逐渐改进（很多内容包括示例都是3.x版本年代的了）。



```
Loading modules
In order to test the module you are developing, you can load the module using the following redis.conf configuration directive:

loadmodule /path/to/mymodule.so
It is also possible to load a module at runtime using the following command:

MODULE LOAD /path/to/mymodule.so
In order to list all loaded modules, use:

MODULE LIST
Finally, you can unload (and later reload if you wish) a module using the following command:

MODULE UNLOAD mymodule

Note that mymodule above is not the filename without the .so suffix, but instead, the name the module used to register itself into the Redis core. The name can be obtained using MODULE LIST. However it is good practice that the filename of the dynamic library is the same as the name the module uses to register itself into the Redis core.

```

### 装载模块

你可以通过配置或命令方式来加载或卸载自己写的模块，也可以查看已加载的模块情况。

注册模块时，注册名默认约定是文件名filename去掉尾缀，好好取名，不然久后自己都不知道哪个模块对应着自己写的那个so了。


```
The simplest module you can write
In order to show the different parts of a module, here we'll show a very simple module that implements a command that outputs a random number.

#include "redismodule.h"
#include <stdlib.h>

int HelloworldRand_RedisCommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
    RedisModule_ReplyWithLongLong(ctx,rand());
    return REDISMODULE_OK;
}

int RedisModule_OnLoad(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
    if (RedisModule_Init(ctx,"helloworld",1,REDISMODULE_APIVER_1)
        == REDISMODULE_ERR) return REDISMODULE_ERR;

    if (RedisModule_CreateCommand(ctx,"helloworld.rand",
        HelloworldRand_RedisCommand) == REDISMODULE_ERR)
        return REDISMODULE_ERR;

    return REDISMODULE_OK;
}
The example module has two functions. One implements a command called HELLOWORLD.RAND. This function is specific of that module. However the other function called RedisModule_OnLoad() must be present in each Redis module. It is the entry point for the module to be initialized, register its commands, and potentially other private data structures it uses.

Note that it is a good idea for modules to call commands with the name of the module followed by a dot, and finally the command name, like in the case of HELLOWORLD.RAND. This way it is less likely to have collisions.

Note that if different modules have colliding commands, they'll not be able to work in Redis at the same time, since the function RedisModule_CreateCommand will fail in one of the modules, so the module loading will abort returning an error condition.

```

### 模块编写示例

自己写个模块试一下是最快的学习路径，这是个最简单示例，输出一个随机数字（这个示例比较老了，新版本对RedisModule_CreateCommand函数增加了3个参数），如下）

```
#include "redismodule.h"
#include <stdlib.h>

int HelloworldRand_RedisCommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
    RedisModule_ReplyWithLongLong(ctx,rand());
    return REDISMODULE_OK;
}

int RedisModule_OnLoad(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
    if (RedisModule_Init(ctx,"helloworld",1,REDISMODULE_APIVER_1)
        == REDISMODULE_ERR) return REDISMODULE_ERR;

	 // 这里增加了3个参数："readonly",0,0,0
    if (RedisModule_CreateCommand(ctx,"helloworld.rand",
        HelloworldRand_RedisCommand,"readonly",0,0,0) == REDISMODULE_ERR)
        return REDISMODULE_ERR;

    return REDISMODULE_OK;
}

```

RedisModule_OnLoad()是整个模块的初始化入口函数，可以在这里做很多的事情，包括：注册自定义的命令（RedisModule_CreateCommand）、初始化自定义的数据结构（RedisModule_CreateDataType
）、预先分配内存（RedisModule_Alloc）等等。

对自定义命令取名字很重要，要防止冲突，一般的做法就是加上自己的命令空间，比如支付系统用的都叫pay.xxx，订单系统用的都叫order.xxx，官方建议使用模块名、实际调用的命令实现函数名称以点号分割。


```
Module initialization
The above example shows the usage of the function RedisModule_Init(). It should be the first function called by the module OnLoad function. The following is the function prototype:

int RedisModule_Init(RedisModuleCtx *ctx, const char *modulename,
                     int module_version, int api_version);
The Init function announces the Redis core that the module has a given name, its version (that is reported by MODULE LIST), and that is willing to use a specific version of the API.

If the API version is wrong, the name is already taken, or there are other similar errors, the function will return REDISMODULE_ERR, and the module OnLoad function should return ASAP with an error.

Before the Init function is called, no other API function can be called, otherwise the module will segfault and the Redis instance will crash.

The second function called, RedisModule_CreateCommand, is used in order to register commands into the Redis core. The following is the prototype:

int RedisModule_CreateCommand(RedisModuleCtx *ctx, const char *cmdname,
                              RedisModuleCmdFunc cmdfunc);
As you can see, most Redis modules API calls all take as first argument the context of the module, so that they have a reference to the module calling it, to the command and client executing a given command, and so forth.

To create a new command, the above function needs the context, the command name, and the function pointer of the function implementing the command, which must have the following prototype:

int mycommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc);
The command function arguments are just the context, that will be passed to all the other API calls, the command argument vector, and total number of arguments, as passed by the user.

As you can see, the arguments are provided as pointers to a specific data type, the RedisModuleString. This is an opaque data type you have API functions to access and use, direct access to its fields is never needed.

Zooming into the example command implementation, we can find another call:

int RedisModule_ReplyWithLongLong(RedisModuleCtx *ctx, long long integer);
This function returns an integer to the client that invoked the command, exactly like other Redis commands do, like for example INCR or SCARD.
```

### 模块的初始化

你应该发现了在模块入口函数RedisModule_OnLoad()的第一行调用的是RedisModule_Init()，函数RedisModule_Init()用于注册本模块，告知Redis系统本模块的名称、模块版本号，模块要使用的Redis API版本号。 新注册的模块名称不能是已存在的，要使用的API版本号是Redis支持的。

在调用其他模块化API之前必须先调用RedisModule_Init()进行初始化。

初始化之后，可以使用RedisModule_CreateCommand()自定义一个Redis Command，第一个参数是模块上下文，创建命令或其他操作时都会使用到RedisModuleCtx上下文，这个上下文贯穿整个自定义模块。还需要两个参数，分别是command名称，command对应实现的函数指针。

实现函数指针必须是以下类型   

```
int mycommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc);
```
第一个参数还是模块上下文，第二个参数是装载模块时传递的参数值(module load xx1 xx2)，被封装为robj对象的参数，这个robj对象是个万能结构，几乎啥都能表示（字符串、列表、字典等），RedisModuleString只是它的#define。第三个参数是参数个数，Redis里一贯做法。

在command实现里还用到了RedisModule_ReplyWithLongLong用于向客户端展示结果，Redis模块化API还有很多，灵活使用他们才能充分利用Redis特性写好自定义模块。


```
Setup and dependencies of a Redis module
Redis modules don't depend on Redis or some other library, nor they need to be compiled with a specific redismodule.h file. In order to create a new module, just copy a recent version of redismodule.h in your source tree, link all the libraries you want, and create a dynamic library having the RedisModule_OnLoad() function symbol exported.

The module will be able to load into different versions of Redis.

```

### 模块的库依赖问题


Redis模块模块不依赖于任何第三方模块或Redis本身，编写自定义模块只需要将头文件redismodule.h引入即可，不管模块引入了哪些第三方库，只要最终将其静态编译成so动态库，即可在多个Redis版本中被载入使用。


```
Passing configuration parameters to Redis modules
When the module is loaded with the MODULE LOAD command, or using the loadmodule directive in the redis.conf file, the user is able to pass configuration parameters to the module by adding arguments after the module file name:

loadmodule mymodule.so foo bar 1234
In the above example the strings foo, bar and 123 will be passed to the module OnLoad() function in the argv argument as an array of RedisModuleString pointers. The number of arguments passed is into argc.

The way you can access those strings will be explained in the rest of this document. Normally the module will store the module configuration parameters in some static global variable that can be accessed module wide, so that the configuration can change the behavior of different commands.

```
### 模块初始化行为的配置

使用命令或者配置文件来装载模块时可以传递参数，如module load arg1 arg2 arg3，参数将传递给入口函数RedisModule_OnLoad中的RedisModuleString **argv，这样模块可以对参数自行解析，从而在装载时微调模块特性。

```
Working with RedisModuleString objects
The command argument vector argv passed to module commands, and the return value of other module APIs functions, are of type RedisModuleString.

Usually you directly pass module strings to other API calls, however sometimes you may need to directly access the string object.

There are a few functions in order to work with string objects:

const char *RedisModule_StringPtrLen(RedisModuleString *string, size_t *len);
The above function accesses a string by returning its pointer and setting its length in len. You should never write to a string object pointer, as you can see from the const pointer qualifier.

However, if you want, you can create new string objects using the following API:

RedisModuleString *RedisModule_CreateString(RedisModuleCtx *ctx, const char *ptr, size_t len);
The string returned by the above command must be freed using a corresponding call to RedisModule_FreeString():

void RedisModule_FreeString(RedisModuleString *str);
However if you want to avoid having to free strings, the automatic memory management, covered later in this document, can be a good alternative, by doing it for you.

Note that the strings provided via the argument vector argv never need to be freed. You only need to free new strings you create, or new strings returned by other APIs, where it is specified that the returned string must be freed.

Creating strings from numbers or parsing strings as numbers
Creating a new string from an integer is a very common operation, so there is a function to do this:

RedisModuleString *mystr = RedisModule_CreateStringFromLongLong(ctx,10);
Similarly in order to parse a string as a number:

long long myval;
if (RedisModule_StringToLongLong(ctx,argv[1],&myval) == REDISMODULE_OK) {
    /* Do something with 'myval' */
}
Accessing Redis keys from modules
Most Redis modules, in order to be useful, have to interact with the Redis data space (this is not always true, for example an ID generator may never touch Redis keys). Redis modules have two different APIs in order to access the Redis data space, one is a low level API that provides very fast access and a set of functions to manipulate Redis data structures. The other API is more high level, and allows to call Redis commands and fetch the result, similarly to how Lua scripts access Redis.

The high level API is also useful in order to access Redis functionalities that are not available as APIs.

In general modules developers should prefer the low level API, because commands implemented using the low level API run at a speed comparable to the speed of native Redis commands. However there are definitely use cases for the higher level API. For example often the bottleneck could be processing the data and not accessing it.

Also note that sometimes using the low level API is not harder compared to the higher level one.
```
### 重要数据结构--RedisModuleString

编写模块时很多函数的参数或返回值都有RedisModuleString类型，前面我们已经说了实际上它是robj类型，和JAVA的Object一样，啥都能表示，RedisModuleString用于存储参数和返回值，大多数情况下，它们都是字符串类型，模块化API提供了对各种类型包括字符串的操作函数，字符串最常见所以举了几个例子。

1. 设置字符串长度：RedisModule_StringPtrLen。   
2. 通过C字符串创建RedisModuleString：RedisModule_CreateString。  
3. 释放字符串空间：RedisModule_FreeString。   
4. 根据数字创建字符串对象RedisModuleString：RedisModule_CreateStringFromLongLong
5. 从字符串转为数字：RedisModule_StringToLongLong

自己编写模块，大多数情况下要访问DB中的键，Redis提供了两种方式来访问DB中的键。

一是直接调用Redis对外的高层API，这就类似写lua脚本来调用Redis API，效率比较低但是简单不容易出错。

二是调用Redis提供的底层API，它们效率很高，但是需要你对Redis的数据结构稍微有一定的了解（不复杂），处于效率考虑，应该选择使用底层API。

```
Calling Redis commands
The high level API to access Redis is the sum of the RedisModule_Call() function, together with the functions needed in order to access the reply object returned by Call().

RedisModule_Call uses a special calling convention, with a format specifier that is used to specify what kind of objects you are passing as arguments to the function.

Redis commands are invoked just using a command name and a list of arguments. However when calling commands, the arguments may originate from different kind of strings: null-terminated C strings, RedisModuleString objects as received from the argv parameter in the command implementation, binary safe C buffers with a pointer and a length, and so forth.

For example if I want to call INCRBY using a first argument (the key) a string received in the argument vector argv, which is an array of RedisModuleString object pointers, and a C string representing the number "10" as second argument (the increment), I'll use the following function call:

RedisModuleCallReply *reply;
reply = RedisModule_Call(ctx,"INCR","sc",argv[1],"10");
The first argument is the context, and the second is always a null terminated C string with the command name. The third argument is the format specifier where each character corresponds to the type of the arguments that will follow. In the above case "sc" means a RedisModuleString object, and a null terminated C string. The other arguments are just the two arguments as specified. In fact argv[1] is a RedisModuleString and "10" is a null terminated C string.

This is the full list of format specifiers:

c -- Null terminated C string pointer.
b -- C buffer, two arguments needed: C string pointer and size_t length.
s -- RedisModuleString as received in argv or by other Redis module APIs returning a RedisModuleString object.
l -- Long long integer.
v -- Array of RedisModuleString objects.
! -- This modifier just tells the function to replicate the command to slaves and AOF. It is ignored from the point of view of arguments parsing.
The function returns a RedisModuleCallReply object on success, on error NULL is returned.

NULL is returned when the command name is invalid, the format specifier uses characters that are not recognized, or when the command is called with the wrong number of arguments. In the above cases the errno var is set to EINVAL. NULL is also returned when, in an instance with Cluster enabled, the target keys are about non local hash slots. In this case errno is set to EPERM.

Working with RedisModuleCallReply objects.
RedisModuleCall returns reply objects that can be accessed using the RedisModule_CallReply* family of functions.

In order to obtain the type or reply (corresponding to one of the data types supported by the Redis protocol), the function RedisModule_CallReplyType() is used:

reply = RedisModule_Call(ctx,"INCR","sc",argv[1],"10");
if (RedisModule_CallReplyType(reply) == REDISMODULE_REPLY_INTEGER) {
    long long myval = RedisModule_CallReplyInteger(reply);
    /* Do something with myval. */
}
Valid reply types are:

REDISMODULE_REPLY_STRING Bulk string or status replies.
REDISMODULE_REPLY_ERROR Errors.
REDISMODULE_REPLY_INTEGER Signed 64 bit integers.
REDISMODULE_REPLY_ARRAY Array of replies.
REDISMODULE_REPLY_NULL NULL reply.
Strings, errors and arrays have an associated length. For strings and errors the length corresponds to the length of the string. For arrays the length is the number of elements. To obtain the reply length the following function is used:

size_t reply_len = RedisModule_CallReplyLength(reply);
In order to obtain the value of an integer reply, the following function is used, as already shown in the example above:

long long reply_integer_val = RedisModule_CallReplyInteger(reply);
Called with a reply object of the wrong type, the above function always returns LLONG_MIN.

Sub elements of array replies are accessed this way:

RedisModuleCallReply *subreply;
subreply = RedisModule_CallReplyArrayElement(reply,idx);
The above function returns NULL if you try to access out of range elements.

Strings and errors (which are like strings but with a different type) can be accessed using in the following way, making sure to never write to the resulting pointer (that is returned as as const pointer so that misusing must be pretty explicit):

size_t len;
char *ptr = RedisModule_CallReplyStringPtr(reply,&len);
If the reply type is not a string or an error, NULL is returned.

RedisCallReply objects are not the same as module string objects (RedisModuleString types). However sometimes you may need to pass replies of type string or integer, to API functions expecting a module string.

When this is the case, you may want to evaluate if using the low level API could be a simpler way to implement your command, or you can use the following function in order to create a new string object from a call reply of type string, error or integer:

RedisModuleString *mystr = RedisModule_CreateStringFromCallReply(myreply);
If the reply is not of the right type, NULL is returned. The returned string object should be released with RedisModule_FreeString() as usually, or by enabling automatic memory management (see corresponding section).
```

### 调用Redis高层API
Redis高层API是对外开放的，在lua脚本中可以使用redis.call()调用，在扩展模块中则可以使用RedisModule_Call()调用，调用的方式和lua的调用方式形式一致，只是不同语言写法不同。

调用RedisModule_Call()时传递的参数形式比较自由，比如调用INCY增加某个key计数时可以用如下写法

```
// 第一个参数key是RedisModuleString类型，第二个参数增加数是标准C字符串类型
reply = RedisModule_Call(ctx,"INCR","sc",argv[1],"10");
```
"sc"是标记位，代表实际参数的类型，传递参数时，允许以下几种类型（和它们的标记位）：  

1. c：标准的NULL结尾的字符串   
2. b：buffer+长度形式的字符串   
3. s：RedisModuleString，前面介绍的通用结构体   
4. v：RedisModuleString的数组   
5. l：数字   
6. !：这个标记位不表示参数类型，仅用于告知Reids将操作同步给slave或备份   

当调用成功，会返回RedisModuleCallReply对象，失败则返回NULL。多种原因会导致返回NULL，错误时会将错误原因代码设置在全局变量EINVAL中。

比如当发现key对应的slot没落在当前节点上时，则会设置EINVAL=EPERM来告知调用者。


Redis提供了一些辅助函数来帮助解析RedisModule_Call()的正确返回值RedisModuleCallReply，它们的命名方式都是RedisModule_CallReply*。

1. 比如想解析返回结构体的值数据类型可以使用RedisModule_CallReplyType()。  
2. 想获取返回数据的长度可以使用RedisModule_CallReplyLength()。  
3. 明确返回值是数字并想转换为数字可使用RedisModule_CallReplyInteger()。  
4. 获取返回结构体中结果数组的某一个元素可使用RedisModule_CallReplyArrayElement()。  
5. 提取响应结果中的字符串可用RedisModule_CallReplyStringPtr()。    
6. 直接将结果转换为字符串可用RedisModule_CreateStringFromCallReply()。    














