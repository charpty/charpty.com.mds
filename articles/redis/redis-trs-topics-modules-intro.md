> https://redis.io/topics/modules-intro

解析难懂之处，并提供更多的代码示例帮助理解。   
原文还有不少章节是缺失的，这一部分我先将原文补齐，PR通过后我会补充。

---

The modules documentation is composed of the following files:

* `INTRO.md` (this file). An overview about Redis Modules system and API. It's a good idea to start your reading here.
* `API.md` is generated from module.c top comments of RedisMoule functions. It is a good reference in order to understand how each function works.
* `TYPES.md` covers the implementation of native data types into modules.
* `BLOCK.md` shows how to write blocking commands that will not reply immediately, but will block the client, without blocking the Redis server, and will provide a reply whenever will be possible.

Redis modules make possible to extend Redis functionality using external
modules, implementing new Redis commands at a speed and with features
similar to what can be done inside the core itself.

Redis modules are dynamic libraries, that can be loaded into Redis at
startup or using the `MODULE LOAD` command. Redis exports a C API, in the
form of a single C header file called `redismodule.h`. Modules are meant
to be written in C, however it will be possible to use C++ or other languages
that have C binding functionalities.

Modules are designed in order to be loaded into different versions of Redis,
so a given module does not need to be designed, or recompiled, in order to
run with a specific version of Redis. For this reason, the module will
register to the Redis core using a specific API version. The current API
version is "1".

This document is about an alpha version of Redis modules. API, functionalities
and other details may change in the future.

# Redis模块化概要介绍

本文章用于介绍Redis模块，分为以下几个文件

INTRO.md（当前文件），Redis模块化的概要介绍，先读这个比较好。   
API.md，介绍Redis的模块化提供的所有API，每个函数都有详细介绍。   
BLOCK.md，介绍写一个阻塞客户端但不阻塞服务器的命令。   

Redis内部命令的实现也使用了模块化，这种模式使得可以方便的自定义扩展模块，扩展的模块也可以方便的利用Redis中本来只能内部使用的优良特性。

Redis的模块化主要利用的是动态库（Windows的dll、Linux的so）特性，想实现自己的模块，需要实现```redismodule.h```头文件，用C和C++或其他语言写都行，只要最后能编译成so文件就可以。

Redis还是比较有良心的，模块化API不会大的调整或者会做高版本兼容，所以写好一个模块，一次编译好了就可以在多个Redis版本中使用而无需改代码或重新编译。

这个文件是初代版本的文档，后续会逐渐改进（很多内容包括示例都是3.x版本年代的了）。


# Loading modules

In order to test the module you are developing, you can load the module
using the following `redis.conf` configuration directive:

    loadmodule /path/to/mymodule.so

It is also possible to load a module at runtime using the following command:

    MODULE LOAD /path/to/mymodule.so

In order to list all loaded modules, use:

    MODULE LIST

Finally, you can unload (and later reload if you wish) a module using the
following command:

    MODULE UNLOAD mymodule

Note that `mymodule` above is not the filename without the `.so` suffix, but
instead, the name the module used to register itself into the Redis core.
The name can be obtained using `MODULE LIST`. However it is good practice
that the filename of the dynamic library is the same as the name the module
uses to register itself into the Redis core.


# 装载模块

你可以通过配置或命令方式来加载或卸载自己写的模块，也可以查看已加载的模块情况。

注册模块时，注册名默认约定是文件名filename去掉尾缀，好好取名，否则过段时间自己都不知道哪个模块对应着自己写的那个so了。



# The simplest module you can write

In order to show the different parts of a module, here we'll show a very
simple module that implements a command that outputs a random number.

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

The example module has two functions. One implements a command called
HELLOWORLD.RAND. This function is specific of that module. However the
other function called `RedisModule_OnLoad()` must be present in each
Redis module. It is the entry point for the module to be initialized,
register its commands, and potentially other private data structures
it uses.

Note that it is a good idea for modules to call commands with the
name of the module followed by a dot, and finally the command name,
like in the case of `HELLOWORLD.RAND`. This way it is less likely to
have collisions.

Note that if different modules have colliding commands, they'll not be
able to work in Redis at the same time, since the function
`RedisModule_CreateCommand` will fail in one of the modules, so the module
loading will abort returning an error condition.


# 模块编写示例

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


# Module initialization

The above example shows the usage of the function `RedisModule_Init()`.
It should be the first function called by the module `OnLoad` function.
The following is the function prototype:

    int RedisModule_Init(RedisModuleCtx *ctx, const char *modulename,
                         int module_version, int api_version);

The `Init` function announces the Redis core that the module has a given
name, its version (that is reported by `MODULE LIST`), and that is willing
to use a specific version of the API.

If the API version is wrong, the name is already taken, or there are other
similar errors, the function will return `REDISMODULE_ERR`, and the module
`OnLoad` function should return ASAP with an error.

Before the `Init` function is called, no other API function can be called,
otherwise the module will segfault and the Redis instance will crash.

The second function called, `RedisModule_CreateCommand`, is used in order
to register commands into the Redis core. The following is the prototype:

    int RedisModule_CreateCommand(RedisModuleCtx *ctx, const char *cmdname,
                                  RedisModuleCmdFunc cmdfunc);

As you can see, most Redis modules API calls all take as first argument
the `context` of the module, so that they have a reference to the module
calling it, to the command and client executing a given command, and so forth.

To create a new command, the above function needs the context, the command
name, and the function pointer of the function implementing the command,
which must have the following prototype:


    int mycommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc);

The command function arguments are just the context, that will be passed
to all the other API calls, the command argument vector, and total number
of arguments, as passed by the user.

As you can see, the arguments are provided as pointers to a specific data
type, the `RedisModuleString`. This is an opaque data type you have API
functions to access and use, direct access to its fields is never needed.

Zooming into the example command implementation, we can find another call:

    int RedisModule_ReplyWithLongLong(RedisModuleCtx *ctx, long long integer);

This function returns an integer to the client that invoked the command,
exactly like other Redis commands do, like for example `INCR` or `SCARD`.

# 模块的初始化

你应该发现了在模块入口函数RedisModule_OnLoad()的第一行调用的是RedisModule_Init()，函数RedisModule_Init()用于注册本模块，告知Redis系统本模块的名称、模块版本号，模块要使用的Redis API版本号。 新注册的模块名称不能是已存在的，要使用的API版本号也必须是Redis支持的。

在调用其他模块化API之前必须先调用RedisModule_Init()进行初始化。

初始化之后，可以使用RedisModule_CreateCommand()自定义一个Redis Command，第一个参数是模块上下文，创建命令或其他操作时都会使用到RedisModuleCtx上下文，这个上下文贯穿整个自定义模块。还需要两个参数，分别是command名称，command对应实现的函数指针。

实现函数指针必须是以下类型   

```
int mycommand(RedisModuleCtx *ctx, RedisModuleString **argv, int argc);
```
第一个参数还是模块上下文，第二个参数是装载模块时传递的参数值(module load xx1 xx2)，被封装为robj对象的参数，这个robj对象是个万能结构，几乎啥都能表示（字符串、列表、字典等），RedisModuleString只是它的#define。第三个参数是参数个数，Redis里一贯做法。

在command实现里还用到了RedisModule_ReplyWithLongLong用于向客户端展示结果，Redis模块化API还有很多，灵活使用它们才能充分利用Redis特性写好自定义模块。



# Setup and dependencies of a Redis module

Redis modules don't depend on Redis or some other library, nor they
need to be compiled with a specific `redismodule.h` file. In order
to create a new module, just copy a recent version of `redismodule.h`
in your source tree, link all the libraries you want, and create
a dynamic library having the `RedisModule_OnLoad()` function symbol
exported.

The module will be able to load into different versions of Redis.


# 模块库依赖问题


Redis模块本身不依赖于任何第三方模块或Redis本身，编写自定义模块只需要将头文件redismodule.h引入即可。

不管模块引入了哪些第三方库，只要最终将其静态编译成so动态库，即可在多个Redis版本中被载入使用。


# Passing configuration parameters to Redis modules

When the module is loaded with the `MODULE LOAD` command, or using the
`loadmodule` directive in the `redis.conf` file, the user is able to pass
configuration parameters to the module by adding arguments after the module
file name:

    loadmodule mymodule.so foo bar 1234

In the above example the strings `foo`, `bar` and `123` will be passed
to the module `OnLoad()` function in the `argv` argument as an array
of RedisModuleString pointers. The number of arguments passed is into `argc`.

The way you can access those strings will be explained in the rest of this
document. Normally the module will store the module configuration parameters
in some `static` global variable that can be accessed module wide, so that
the configuration can change the behavior of different commands.


# 模块初始化行为的配置

使用命令或者配置文件来装载模块时可以传递参数，如module load arg1 arg2 arg3，参数将传递给入口函数RedisModule_OnLoad中的RedisModuleString **argv，这样模块可以对参数自行解析，从而在装载时微调模块特性。


# Working with RedisModuleString objects

The command argument vector `argv` passed to module commands, and the
return value of other module APIs functions, are of type `RedisModuleString`.

Usually you directly pass module strings to other API calls, however sometimes
you may need to directly access the string object.

There are a few functions in order to work with string objects:

    const char *RedisModule_StringPtrLen(RedisModuleString *string, size_t *len);

The above function accesses a string by returning its pointer and setting its
length in `len`.
You should never write to a string object pointer, as you can see from the
`const` pointer qualifier.

However, if you want, you can create new string objects using the following
API:

    RedisModuleString *RedisModule_CreateString(RedisModuleCtx *ctx, const char *ptr, size_t len);

The string returned by the above command must be freed using a corresponding
call to `RedisModule_FreeString()`:

    void RedisModule_FreeString(RedisModuleString *str);

However if you want to avoid having to free strings, the automatic memory
management, covered later in this document, can be a good alternative, by
doing it for you.

Note that the strings provided via the argument vector `argv` never need
to be freed. You only need to free new strings you create, or new strings
returned by other APIs, where it is specified that the returned string must
be freed.

## Creating strings from numbers or parsing strings as numbers

Creating a new string from an integer is a very common operation, so there
is a function to do this:

    RedisModuleString *mystr = RedisModule_CreateStringFromLongLong(ctx,10);

Similarly in order to parse a string as a number:

    long long myval;
    if (RedisModule_StringToLongLong(ctx,argv[1],&myval) == REDISMODULE_OK) {
        /* Do something with 'myval' */
    }

## Accessing Redis keys from modules

Most Redis modules, in order to be useful, have to interact with the Redis
data space (this is not always true, for example an ID generator may
never touch Redis keys). Redis modules have two different APIs in order to
access the Redis data space, one is a low level API that provides very
fast access and a set of functions to manipulate Redis data structures.
The other API is more high level, and allows to call Redis commands and
fetch the result, similarly to how Lua scripts access Redis.

The high level API is also useful in order to access Redis functionalities
that are not available as APIs.

In general modules developers should prefer the low level API, because commands
implemented using the low level API run at a speed comparable to the speed
of native Redis commands. However there are definitely use cases for the
higher level API. For example often the bottleneck could be processing the
data and not accessing it.

Also note that sometimes using the low level API is not harder compared to
the higher level one.

# 重要数据结构--RedisModuleString

编写模块时很多函数的参数或返回值都有RedisModuleString类型，前面我们已经说了实际上它是robj类型，和JAVA的Object一样，啥都能表示，RedisModuleString用于存储参数和返回值，大多数情况下，它们都是字符串类型，模块化API提供了对各种类型包括字符串的操作函数，字符串最常见所以举了几个例子。

1. 设置字符串长度：RedisModule_StringPtrLen。   
2. 通过C字符串创建RedisModuleString：RedisModule_CreateString。  
3. 释放字符串空间：RedisModule_FreeString。   
4. 根据数字创建字符串对象RedisModuleString：RedisModule_CreateStringFromLongLong
5. 从字符串转为数字：RedisModule_StringToLongLong

自己编写模块，大多数情况下要访问DB中的键，Redis提供了两种方式来访问DB中的键。

一是直接调用Redis对外的高层API，这就类似写lua脚本来调用Redis API，效率比较低但是简单不容易出错。

二是调用Redis提供的底层API，它们效率很高，但是需要你对Redis的数据结构稍微有一定的了解（不复杂），出于效率考虑，应该优先选择使用底层API。


# Calling Redis commands

The high level API to access Redis is the sum of the `RedisModule_Call()`
function, together with the functions needed in order to access the
reply object returned by `Call()`.

`RedisModule_Call` uses a special calling convention, with a format specifier
that is used to specify what kind of objects you are passing as arguments
to the function.

Redis commands are invoked just using a command name and a list of arguments.
However when calling commands, the arguments may originate from different
kind of strings: null-terminated C strings, RedisModuleString objects as
received from the `argv` parameter in the command implementation, binary
safe C buffers with a pointer and a length, and so forth.

For example if I want to call `INCRBY` using a first argument (the key)
a string received in the argument vector `argv`, which is an array
of RedisModuleString object pointers, and a C string representing the
number "10" as second argument (the increment), I'll use the following
function call:

    RedisModuleCallReply *reply;
    reply = RedisModule_Call(ctx,"INCR","sc",argv[1],"10");

The first argument is the context, and the second is always a null terminated
C string with the command name. The third argument is the format specifier
where each character corresponds to the type of the arguments that will follow.
In the above case `"sc"` means a RedisModuleString object, and a null
terminated C string. The other arguments are just the two arguments as
specified. In fact `argv[1]` is a RedisModuleString and `"10"` is a null
terminated C string.

This is the full list of format specifiers:

* **c** -- Null terminated C string pointer.
* **b** -- C buffer, two arguments needed: C string pointer and `size_t` length.
* **s** -- RedisModuleString as received in `argv` or by other Redis module APIs returning a RedisModuleString object.
* **l** -- Long long integer.
* **v** -- Array of RedisModuleString objects.
* **!** -- This modifier just tells the function to replicate the command to slaves and AOF. It is ignored from the point of view of arguments parsing.

The function returns a `RedisModuleCallReply` object on success, on
error NULL is returned.

NULL is returned when the command name is invalid, the format specifier uses
characters that are not recognized, or when the command is called with the
wrong number of arguments. In the above cases the `errno` var is set to `EINVAL`. NULL is also returned when, in an instance with Cluster enabled, the target
keys are about non local hash slots. In this case `errno` is set to `EPERM`.


## Working with RedisModuleCallReply objects.

`RedisModuleCall` returns reply objects that can be accessed using the
`RedisModule_CallReply*` family of functions.

In order to obtain the type or reply (corresponding to one of the data types
supported by the Redis protocol), the function `RedisModule_CallReplyType()`
is used:

    reply = RedisModule_Call(ctx,"INCR","sc",argv[1],"10");
    if (RedisModule_CallReplyType(reply) == REDISMODULE_REPLY_INTEGER) {
        long long myval = RedisModule_CallReplyInteger(reply);
        /* Do something with myval. */
    }

Valid reply types are:

* `REDISMODULE_REPLY_STRING` Bulk string or status replies.
* `REDISMODULE_REPLY_ERROR` Errors.
* `REDISMODULE_REPLY_INTEGER` Signed 64 bit integers.
* `REDISMODULE_REPLY_ARRAY` Array of replies.
* `REDISMODULE_REPLY_NULL` NULL reply.

Strings, errors and arrays have an associated length. For strings and errors
the length corresponds to the length of the string. For arrays the length
is the number of elements. To obtain the reply length the following function
is used:

    size_t reply_len = RedisModule_CallReplyLength(reply);

In order to obtain the value of an integer reply, the following function is used, as already shown in the example above:

    long long reply_integer_val = RedisModule_CallReplyInteger(reply);

Called with a reply object of the wrong type, the above function always
returns `LLONG_MIN`.

Sub elements of array replies are accessed this way:

    RedisModuleCallReply *subreply;
    subreply = RedisModule_CallReplyArrayElement(reply,idx);

The above function returns NULL if you try to access out of range elements.

Strings and errors (which are like strings but with a different type) can
be accessed using in the following way, making sure to never write to
the resulting pointer (that is returned as as `const` pointer so that
misusing must be pretty explicit):

    size_t len;
    char *ptr = RedisModule_CallReplyStringPtr(reply,&len);

If the reply type is not a string or an error, NULL is returned.

RedisCallReply objects are not the same as module string objects
(RedisModuleString types). However sometimes you may need to pass replies
of type string or integer, to API functions expecting a module string.

When this is the case, you may want to evaluate if using the low level
API could be a simpler way to implement your command, or you can use
the following function in order to create a new string object from a
call reply of type string, error or integer:

    RedisModuleString *mystr = RedisModule_CreateStringFromCallReply(myreply);

If the reply is not of the right type, NULL is returned.
The returned string object should be released with `RedisModule_FreeString()`
as usually, or by enabling automatic memory management (see corresponding
section).

# 调用Redis高层API
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

当调用成功，会返回RedisModuleCallReply对象，失败则返回NULL。多种原因会导致返回NULL，发生错误时会将错误原因代码设置在全局变量EINVAL中。

比如当发现key对应的slot没落在当前节点上时，则会设置EINVAL=EPERM来告知调用者。


Redis的返回值RedisModuleCallReply存储的实际值一共有5种类型。

* REDISMODULE_REPLY_STRING：字符串（RESP响应格式）
* REDISMODULE_REPLY_ERROR：错误信息，一般是业务上的错误
* REDISMODULE_REPLY_INTEGER：long long数字
* REDISMODULE_REPLY_ARRAY：响应是个数组
* REDISMODULE_REPLY_NULL：代表NULL.

Redis还提供了一些辅助函数来帮助解析RedisModule_Call()的正确返回值RedisModuleCallReply，它们的命名方式都是RedisModule_CallReply*。

1. 比如想解析返回结构体的值数据类型可以使用RedisModule_CallReplyType()。  
2. 想获取返回数据的长度可以使用RedisModule_CallReplyLength()。  
3. 明确返回值是数字并想转换为数字可使用RedisModule_CallReplyInteger()。  
4. 获取返回结构体中结果数组的某一个元素可使用RedisModule_CallReplyArrayElement()。  
5. 提取响应结果中的字符串可用RedisModule_CallReplyStringPtr()。    
6. 直接将结果转换为字符串可用RedisModule_CreateStringFromCallReply()。    


# Releasing call reply objects

Reply objects must be freed using `RedisModule_FreeCallReply`. For arrays,
you need to free only the top level reply, not the nested replies.
Currently the module implementation provides a protection in order to avoid
crashing if you free a nested reply object for error, however this feature
is not guaranteed to be here forever, so should not be considered part
of the API.

If you use automatic memory management (explained later in this document)
you don't need to free replies (but you still could if you wish to release
memory ASAP).

## Returning values from Redis commands

Like normal Redis commands, new commands implemented via modules must be
able to return values to the caller. The API exports a set of functions for
this goal, in order to return the usual types of the Redis protocol, and
arrays of such types as elemented. Also errors can be returned with any
error string and code (the error code is the initial uppercase letters in
the error message, like the "BUSY" string in the "BUSY the sever is busy" error
message).

All the functions to send a reply to the client are called
`RedisModule_ReplyWith<something>`.

To return an error, use:

    RedisModule_ReplyWithError(RedisModuleCtx *ctx, const char *err);

There is a predefined error string for key of wrong type errors:

    REDISMODULE_ERRORMSG_WRONGTYPE

Example usage:

    RedisModule_ReplyWithError(ctx,"ERR invalid arguments");

We already saw how to reply with a long long in the examples above:

    RedisModule_ReplyWithLongLong(ctx,12345);

To reply with a simple string, that can't contain binary values or newlines,
(so it's suitable to send small words, like "OK") we use:

    RedisModule_ReplyWithSimpleString(ctx,"OK");

It's possible to reply with "bulk strings" that are binary safe, using
two different functions:

    int RedisModule_ReplyWithStringBuffer(RedisModuleCtx *ctx, const char *buf, size_t len);

    int RedisModule_ReplyWithString(RedisModuleCtx *ctx, RedisModuleString *str);

The first function gets a C pointer and length. The second a RedisMoudleString
object. Use one or the other depending on the source type you have at hand.

In order to reply with an array, you just need to use a function to emit the
array length, followed by as many calls to the above functions as the number
of elements of the array are:

    RedisModule_ReplyWithArray(ctx,2);
    RedisModule_ReplyWithStringBuffer(ctx,"age",3);
    RedisModule_ReplyWithLongLong(ctx,22);

To return nested arrays is easy, your nested array element just uses another
call to `RedisModule_ReplyWithArray()` followed by the calls to emit the
sub array elements.

## Returning arrays with dynamic length

Sometimes it is not possible to know beforehand the number of items of
an array. As an example, think of a Redis module implementing a FACTOR
command that given a number outputs the prime factors. Instead of
factorializing the number, storing the prime factors into an array, and
later produce the command reply, a better solution is to start an array
reply where the length is not known, and set it later. This is accomplished
with a special argument to `RedisModule_ReplyWithArray()`:

    RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);

The above call starts an array reply so we can use other `ReplyWith` calls
in order to produce the array items. Finally in order to set the length
se use the following call:

    RedisModule_ReplySetArrayLength(ctx, number_of_items);

In the case of the FACTOR command, this translates to some code similar
to this:

    RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
    number_of_factors = 0;
    while(still_factors) {
        RedisModule_ReplyWithLongLong(ctx, some_factor);
        number_of_factors++;
    }
    RedisModule_ReplySetArrayLength(ctx, number_of_factors);

Another common use case for this feature is iterating over the arrays of
some collection and only returning the ones passing some kind of filtering.

It is possible to have multiple nested arrays with postponed reply.
Each call to `SetArray()` will set the length of the latest corresponding
call to `ReplyWithArray()`:

    RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
    ... generate 100 elements ...
    RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
    ... generate 10 elements ...
    RedisModule_ReplySetArrayLength(ctx, 10);
    RedisModule_ReplySetArrayLength(ctx, 100);

This creates a 100 items array having as last element a 10 items array.


# 释放返回结果的内存空间
在使用完响应结果RedisModuleCallReply之后，必须手动释放其内存空间，Redis提供了函数RedisModule_FreeCallReply来帮助你正确释放内存。Redis模块化系统目前增加了防崩溃保护，以免错误的内存释放导致的系统崩溃，但是释放内存或其他风险操作时还是应该谨慎。

厉害的是，你可以选择让Redis自动管理内存，就和JAVA的GC一样，你只管用而不用释放内存，只需要一行配置代码即可开启自动管理内存功能。

自定义命令的实现函数必须要有返回值，而且返回值必须遵循既有的格式规范，为此Redis模块化系统提供了一组函数来帮助开发者实现该目标，这些名称函数皆如RedisModule_ReplyWith<something>。

好理解的几个函数

1. 返回错误信息：RedisModule_ReplyWithError(RedisModuleCtx *ctx, const char *errMsg)
2. 返回数字结果：RedisModule_ReplyWithLongLong(ctx,12345);
3. 返回简单字符串（加号前缀当行短字符串）：RedisModule_ReplyWithSimpleString(ctx,"OK");
4. 返回大字符串（RESP中的bulk strings）：RedisModule_ReplyWithStringBuffer或RedisModule_ReplyWithString
5. 返回数组（RESP Arrays）：和RESP实现模式类似，先设置数组长度RedisModule_ReplyWithArray，而后逐个元素输出

上面几个函数大都是对RESP格式的封装，比较好理解，还剩下一个动态数组和嵌套动态数组，道理一样。

动态数组，某些场景下，实现函数自己也是从别人那里流式接收列表数据，目前它还不知道长度，那么可以设置返回类型是一个动态数组，先将元素逐个返回，之后再设置返回数组长度。遍历列表并返回是最常见的应用场景。

```
// REDISMODULE_POSTPONED_ARRAY_LEN标记动态数组
RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
number_of_factors = 0;
while(still_factors) {
	 // 先将元素逐个返回
    RedisModule_ReplyWithLongLong(ctx, some_factor);
    number_of_factors++;
}
// 最后再设置数组长度
RedisModule_ReplySetArrayLength(ctx, number_of_factors);
```

嵌套动态数组就是其字面意思，在动态数组的基础上进行嵌套，数组里有数组或者说数组里的元素类型又是数组。

```
// 外层的数组
RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
... generate 100 elements ...
// 内层的数组
RedisModule_ReplyWithArray(ctx, REDISMODULE_POSTPONED_ARRAY_LEN);
... generate 10 elements ...
// 分别设置内外层数组长度
// 外层数组一共有100个元素，其中最后一个元素是一个数组，这个数组又存放了10个元素
RedisModule_ReplySetArrayLength(ctx, 10);
RedisModule_ReplySetArrayLength(ctx, 100);
```


# Arity and type checks

Often commands need to check that the number of arguments and type of the key
is correct. In order to report a wrong arity, there is a specific function
called `RedisModule_WrongArity()`. The usage is trivial:

    if (argc != 2) return RedisModule_WrongArity(ctx);

Checking for the wrong type involves opening the key and checking the type:

    RedisModuleKey *key = RedisModule_OpenKey(ctx,argv[1],
        REDISMODULE_READ|REDISMODULE_WRITE);

    int keytype = RedisModule_KeyType(key);
    if (keytype != REDISMODULE_KEYTYPE_STRING &&
        keytype != REDISMODULE_KEYTYPE_EMPTY)
    {
        RedisModule_CloseKey(key);
        return RedisModule_ReplyWithError(ctx,REDISMODULE_ERRORMSG_WRONGTYPE);
    }

Note that you often want to proceed with a command both if the key
is of the expected type, or if it's empty.

## Low level access to keys

Low level access to keys allow to perform operations on value objects associated
to keys directly, with a speed similar to what Redis uses internally to
implement the built-in commands.

Once a key is opened, a key pointer is returned that will be used with all the
other low level API calls in order to perform operations on the key or its
associated value.

Because the API is meant to be very fast, it cannot do too many run-time
checks, so the user must be aware of certain rules to follow:

* Opening the same key multiple times where at least one instance is opened for writing, is undefined and may lead to crashes.
* While a key is open, it should only be accessed via the low level key API. For example opening a key, then calling DEL on the same key using the `RedisModule_Call()` API will result into a crash. However it is safe to open a key, perform some operation with the low level API, closing it, then using other APIs to manage the same key, and later opening it again to do some more work.

In order to open a key the `RedisModule_OpenKey` function is used. It returns
a key pointer, that we'll use with all the next calls to access and modify
the value:

    RedisModuleKey *key;
    key = RedisModule_OpenKey(ctx,argv[1],REDISMODULE_READ);

The second argument is the key name, that must be a `RedisModuleString` object.
The third argument is the mode: `REDISMODULE_READ` or `REDISMODULE_WRITE`.
It is possible to use `|` to bitwise OR the two modes to open the key in
both modes. Currently a key opened for writing can also be accessed for reading
but this is to be considered an implementation detail. The right mode should
be used in sane modules.

You can open non exisitng keys for writing, since the keys will be created
when an attempt to write to the key is performed. However when opening keys
just for reading, `RedisModule_OpenKey` will return NULL if the key does not
exist.

Once you are done using a key, you can close it with:

    RedisModule_CloseKey(key);

Note that if automatic memory management is enabled, you are not forced to
close keys. When the module function returns, Redis will take care to close
all the keys which are still open.

## Getting the key type

In order to obtain the value of a key, use the `RedisModule_KeyType()` function:

    int keytype = RedisModule_KeyType(key);

It returns one of the following values:

    REDISMODULE_KEYTYPE_EMPTY
    REDISMODULE_KEYTYPE_STRING
    REDISMODULE_KEYTYPE_LIST
    REDISMODULE_KEYTYPE_HASH
    REDISMODULE_KEYTYPE_SET
    REDISMODULE_KEYTYPE_ZSET

The above are just the usual Redis key types, with the addition of an empty
type, that signals the key pointer is associated with an empty key that
does not yet exists.

## Creating new keys

To create a new key, open it for writing and then write to it using one
of the key writing functions. Example:

    RedisModuleKey *key;
    key = RedisModule_OpenKey(ctx,argv[1],REDISMODULE_WRITE);
    if (RedisModule_KeyType(key) == REDISMODULE_KEYTYPE_EMPTY) {
        RedisModule_StringSet(key,argv[2]);
    }

## Deleting keys

Just use:

    RedisModule_DeleteKey(key);

The function returns `REDISMODULE_ERR` if the key is not open for writing.
Note that after a key gets deleted, it is setup in order to be targeted
by new key commands. For example `RedisModule_KeyType()` will return it is
an empty key, and writing to it will create a new key, possibly of another
type (depending on the API used).

## Managing key expires (TTLs)

To control key expires two functions are provided, that are able to set,
modify, get, and unset the time to live associated with a key.

One function is used in order to query the current expire of an open key:

    mstime_t RedisModule_GetExpire(RedisModuleKey *key);

The function returns the time to live of the key in milliseconds, or
`REDISMODULE_NO_EXPIRE` as a special value to signal the key has no associated
expire or does not exist at all (you can differentiate the two cases checking
if the key type is `REDISMODULE_KEYTYPE_EMPTY`).

In order to change the expire of a key the following function is used instead:

    int RedisModule_SetExpire(RedisModuleKey *key, mstime_t expire);

When called on a non existing key, `REDISMODULE_ERR` is returned, because
the function can only associate expires to existing open keys (non existing
open keys are only useful in order to create new values with data type
specific write operations).

Again the `expire` time is specified in milliseconds. If the key has currently
no expire, a new expire is set. If the key already have an expire, it is
replaced with the new value.

If the key has an expire, and the special value `REDISMODULE_NO_EXPIRE` is
used as a new expire, the expire is removed, similarly to the Redis
`PERSIST` command. In case the key was already persistent, no operation is
performed.

## Obtaining the length of values

There is a single function in order to retrieve the length of the value
associated to an open key. The returned length is value-specific, and is
the string length for strings, and the number of elements for the aggregated
data types (how many elements there is in a list, set, sorted set, hash).

    size_t len = RedisModule_ValueLength(key);

If the key does not exist, 0 is returned by the function:

## String type API

Setting a new string value, like the Redis `SET` command does, is performed
using:

    int RedisModule_StringSet(RedisModuleKey *key, RedisModuleString *str);

The function works exactly like the Redis `SET` command itself, that is, if
there is a prior value (of any type) it will be deleted.

Accessing existing string values is performed using DMA (direct memory
access) for speed. The API will return a pointer and a length, so that's
possible to access and, if needed, modify the string directly.

    size_t len, j;
    char *myptr = RedisModule_StringDMA(key,&len,REDISMODULE_WRITE);
    for (j = 0; j < len; j++) myptr[j] = 'A';

In the above example we write directly on the string. Note that if you want
to write, you must be sure to ask for `WRITE` mode.

DMA pointers are only valid if no other operations are performed with the key
before using the pointer, after the DMA call.

Sometimes when we want to manipulate strings directly, we need to change
their size as well. For this scope, the `RedisModule_StringTruncate` function
is used. Example:

    RedisModule_StringTruncate(mykey,1024);

The function truncates, or enlarges the string as needed, padding it with
zero bytes if the previos length is smaller than the new length we request.
If the string does not exist since `key` is associated to an open empty key,
a string value is created and associated to the key.

Note that every time `StringTruncate()` is called, we need to re-obtain
the DMA pointer again, since the old may be invalid.

## List type API

It's possible to push and pop values from list values:

    int RedisModule_ListPush(RedisModuleKey *key, int where, RedisModuleString *ele);
    RedisModuleString *RedisModule_ListPop(RedisModuleKey *key, int where);

In both the APIs the `where` argument specifies if to push or pop from tail
or head, using the following macros:

    REDISMODULE_LIST_HEAD
    REDISMODULE_LIST_TAIL

Elements returned by `RedisModule_ListPop()` are like strings craeted with
`RedisModule_CreateString()`, they must be released with
`RedisModule_FreeString()` or by enabling automatic memory management.

## Set type API

Work in progress.

## Sorted set type API

Documentation missing, please refer to the top comments inside `module.c`
for the following functions:

* `RedisModule_ZsetAdd`
* `RedisModule_ZsetIncrby`
* `RedisModule_ZsetScore`
* `RedisModule_ZsetRem`

And for the sorted set iterator:

* `RedisModule_ZsetRangeStop`
* `RedisModule_ZsetFirstInScoreRange`
* `RedisModule_ZsetLastInScoreRange`
* `RedisModule_ZsetFirstInLexRange`
* `RedisModule_ZsetLastInLexRange`
* `RedisModule_ZsetRangeCurrentElement`
* `RedisModule_ZsetRangeNext`
* `RedisModule_ZsetRangePrev`
* `RedisModule_ZsetRangeEndReached`

## Hash type API

Documentation missing, please refer to the top comments inside `module.c`
for the following functions:

* `RedisModule_HashSet`
* `RedisModule_HashGet`

## Iterating aggregated values

Work in progress.


# 参数检查与使用
函数被调用时，一般来说做的第一件事情是检查调用者传递的参数是否正确，包括参数个数检查、参数类型检查、值边界检查、对应key是否存在等等，Redis提供了一组函数来帮助开发者检查参数以及在参数有误时返回错误信息。

比如检查参数个数是否正确以及返回错误

```
if (argc != 2) return RedisModule_WrongArity(ctx);

```
比如检查参数的类型是否正确

```
RedisModuleKey *key = RedisModule_OpenKey(ctx,argv[1],
    REDISMODULE_READ|REDISMODULE_WRITE);

int keytype = RedisModule_KeyType(key);
if (keytype != REDISMODULE_KEYTYPE_STRING &&
    keytype != REDISMODULE_KEYTYPE_EMPTY)
{
    RedisModule_CloseKey(key);
    // 预定好的REDISMODULE_ERRORMSG_WRONGTYPE表示参数类型错误
    return RedisModule_ReplyWithError(ctx,REDISMODULE_ERRORMSG_WRONGTYPE);
}
```

对于更深次的检查和操作，Redis模块化系统提供了许多底层API来完成，Redis作为一个K-V存储系统，最常见的当然是对key的操作（查找key对应元素、判断key还有多久过期、删除key等等），在对一个key进行操作前必须open它。

```
key = RedisModule_OpenKey(ctx,argv[1],REDISMODULE_READ);
```
只有在open之后，才能继续调用Redis模块化的底层API进行操作，底层API的效率很高，当然也意味着限制更少，防崩溃手段更少，所以开发者使用时需要注意以下事项。

1. 一个key只能被打开一次，多次打开某个key的结果是不可预料的
2. 当某个key被打开时，它只能被底层API访问和操作

在调用RedisModule_OpenKey时，第二个参数当然就是要open的具体key了，这个key必须是RedisModuleString类型，实质上它还必须是个string，Redis中的key都是string。  
第三个参数是open的模式，和打开文件一样有读（REDISMODULE_READ）、写（REDISMODULE_WRITE）模式。

以写模式open一个不存在的key就等同于创建这个key，然后可以写入自己的数据。如果以读模式open一个不存在的key则会返回空。

在使用一个key后，必须对它进行关闭，调用RedisModule_CloseKey(key)即可。   
和前面返回值一样，如果打开了自动内存管理则无需close操作，后续的许多操作在获取都返回值后，只要是打开了自动内存管理则都不需要主动close了（当然你也可以主动close来快速释放内存），后续就不再重复说明了。

接下来对常用的底层API进行简单的介绍

## 获取key类型
可以使用RedisModule_KeyType()函数获取key类型

```
int keytype = RedisModule_KeyType(key);
```
一共有5种类型（Redis的5种基本类型），再加一种空类型

* REDISMODULE_KEYTYPE_STRING
* REDISMODULE_KEYTYPE_LIST
* REDISMODULE_KEYTYPE_HASH
* REDISMODULE_KEYTYPE_SET
* REDISMODULE_KEYTYPE_ZSET
* REDISMODULE_KEYTYPE_EMPTY

空类型用于代表当前key不存在

## 创建新key
通过写模式打开一个不存在的key则可以创建该key

```
RedisModuleKey *key;
// 原文模式没写对，应该是写方式打开
key = RedisModule_OpenKey(ctx,argv[1],REDISMODULE_WRITE);
if (RedisModule_KeyType(key) == REDISMODULE_KEYTYPE_EMPTY) {
    RedisModule_StringSet(key,argv[2]);
}
```

## 删除key

```
RedisModule_DeleteKey(key);
```
必须先open后才能删除该key，open成功则意味着模块当前成功占用了该key，此时才能进行删除。

## 管理key剩余生存时间
和外部的expire命令一样，Redis模块化系统提供了后取和设置的命令来管理key的生存时间。

* 获取key的生存时间

```
mstime_t RedisModule_GetExpire(RedisModuleKey *key);
```
返回的时间单位是毫秒，如果key不存在或者未设置过期时间则都会返回REDISMODULE_NO_EXPIRE，如果想区分是哪种情况则先判断下key是否存在。

* 设置key的生存时间

```
int RedisModule_SetExpire(RedisModuleKey *key, mstime_t expire);
```
如果对不存在的或未open（任何操作都要先open，后续不再重复描述）的key设置过期则会返回REDISMODULE_ERR错误。

设置特殊的过期时间REDISMODULE_NO_EXPIRE代表取消该key的生存时间，该key永不过期。

## 获取key的长度

```
size_t len = RedisModule_ValueLength(key);
```
如果key是字符串则返回字符长度，如果key是集合则返回集合中元素的个数。


## 字符串类型常用的API

* 设置字符串内容，和命令SET同效果

```
int RedisModule_StringSet(RedisModuleKey *key, RedisModuleString *str);
```

* 直接访问字符串内存地址

```
size_t len, j;
char *myptr = RedisModule_StringDMA(key,&len,REDISMODULE_WRITE);
for (j = 0; j < len; j++) myptr[j] = 'A';
```
这种方式是直接操作内存，效率更高，当然也更不安全。此操作方式没法分配新内存，只能改变现有内存中的内容。

* 完全操作字符串
 
```
RedisModule_StringTruncate(mykey,1024);
```
这种方式是分配了一个新的内存地址，只是将原字符串拷贝过去，后续的操作都在新的地址上，此时想怎么设置都是随心所欲了。

## 列表类型常用的API

* 放入或弹出元素

```
// 在指定位置放入元素
int RedisModule_ListPush(RedisModuleKey *key, int where, RedisModuleString *ele);
// 获取指定位置元素
RedisModuleString *RedisModule_ListPop(RedisModuleKey *key, int where);

```

为了方便常用的操作，Redis定义好了一些常用宏

```
REDISMODULE_LIST_HEAD  列表头位置
REDISMODULE_LIST_TAIL  列表尾位置
```

## 集合set类型常用的API
还没有D--

## 有序集合zset常用的API
也没好好写，大概有这些API，在源代码中找到直接看代码吧

```
RedisModule_ZsetAdd
RedisModule_ZsetIncrby
RedisModule_ZsetScore
RedisModule_ZsetRem

RedisModule_ZsetRangeStop
RedisModule_ZsetFirstInScoreRange
RedisModule_ZsetLastInScoreRange
RedisModule_ZsetFirstInLexRange
RedisModule_ZsetLastInLexRange
RedisModule_ZsetRangeCurrentElement
RedisModule_ZsetRangeNext
RedisModule_ZsetRangePrev
RedisModule_ZsetRangeEndReached
```

## 哈希表
没写，自己看函数

```
RedisModule_HashSet
RedisModule_HashGet
```

## 迭代聚合
还没有


# Replicating commands

If you want to use module commands exactly like normal Redis commands, in the
context of replicated Redis instances, or using the AOF file for persistence,
it is important for module commands to handle their replication in a consistent
way.

When using the higher level APIs to invoke commands, replication happens
automatically if you use the "!" modifier in the format string of
`RedisModule_Call()` as in the following example:

    reply = RedisModule_Call(ctx,"INCR","!sc",argv[1],"10");

As you can see the format specifier is `"!sc"`. The bang is not parsed as a
format specifier, but it internally flags the command as "must replicate".

If you use the above programming style, there are no problems.
However sometimes things are more complex than that, and you use the low level
API. In this case, if there are no side effects in the command execution, and
it consistently always performs the same work, what is possible to do is to
replicate the command verbatim as the user executed it. To do that, you just
need to call the following function:

    RedisModule_ReplicateVerbatim(ctx);

When you use the above API, you should not use any other replication function
since they are not guaranteed to mix well.

However this is not the only option. It's also possible to exactly tell
Redis what commands to replicate as the effect of the command execution, using
an API similar to `RedisModule_Call()` but that instead of calling the command
sends it to the AOF / slaves stream. Example:

    RedisModule_Replicate(ctx,"INCRBY","cl","foo",my_increment);

It's possible to call `RedisModule_Replicate` multiple times, and each
will emit a command. All the sequence emitted is wrapped between a
`MULTI/EXEC` transaction, so that the AOF and replication effects are the
same as executing a single command.

Note that `Call()` replication and `Replicate()` replication have a rule,
in case you want to mix both forms of replication (not necessarily a good
idea if there are simpler approaches). Commands replicated with `Call()`
are always the first emitted in the final `MULTI/EXEC` block, while all
the commands emitted with `Replicate()` will follow.


# 副本集命令

如果想模块中执行的call代码和外部执行命令效果一样，很重要的一块是AOF备份与集群模式的主从同步。

在高层API或者命令行执行命令时，已经包含了这一部分功能，但是底层API却没有直接包含。

想要在底层API中实现这两个功能也比较简单，只需在call()命令的标记位中增加一个感叹号即可。

```
reply = RedisModule_Call(ctx,"INCR","!sc",argv[1],"10");
```

"!"感叹号不代表参数格式，而是代表必须执行AOF备份和主从同步（集群模式下）。   

当然这只是告知Redis核心必须进行备份，具体何种情况下备份则由Redis系统自行选择（配置相关）。如果想要逐行备份（或同步副本集）则可以使用ReplicateVerbatim来强制立刻执行。

```
RedisModule_ReplicateVerbatim(ctx);
```
这个命令是非事务的，即比方它只管同步它的上一条命令，但是我们知道上一条命令不一定是上一行代码，所以如果两行执行期间有其他带副本集功能（要写备份或同步的）的命令混入使用则可能会出问题。

如果想要原子执行一次副本集命令，则可以使用RedisModule_Replicate来执行备份（或同步）。

```
RedisModule_Replicate(ctx,"INCRBY","cl","foo",my_increment);
```
这个将数据操作命令和同步命令放在一起了，可以想到是原子操作了。

可以调用Replicate()多次，不管怎么玩，Redis会保证他们像单线程逐行执行一样的效果。

在一个命令实现代码中，如果既调用RedisModule_Call（带感叹号）带有副本集命令，又显式指定了RedisModule_Replicate等副本集命令（最好别这样做），在执行备份时，会让Call()命令副本集命令在事务最前。

这里要理解副本集执行时，会先将该模块实现的这个自定义命令的所有副本集命令都一起放到一个事务MULTI/EXEC block中，这时就可以先对各个命令进行顺序调整。

为何这么处理，我理解的是显式的副本集命令优先级更高，放在后面才能生效。

# Automatic memory management

Normally when writing programs in the C language, programmers need to manage
memory manually. This is why the Redis modules API has functions to release
strings, close open keys, free replies, and so forth.

However given that commands are executed in a contained environment and
with a set of strict APIs, Redis is able to provide automatic memory management
to modules, at the cost of some performance (most of the time, a very low
cost).

When automatic memory management is enabled:

1. You don't need to close open keys.
2. You don't need to free replies.
3. You don't need to free RedisModuleString objects.

However you can still do it, if you want. For example, automatic memory
management may be active, but inside a loop allocating a lot of strings,
you may still want to free strings no longer used.

In order to enable automatic memory management, just call the following
function at the start of the command implementation:

    RedisModule_AutoMemory(ctx);

Automatic memory management is usually the way to go, however experienced
C programmers may not use it in order to gain some speed and memory usage
benefit.

# 自动化内存管理
Redis使得写C代码也拥有GC特性，避免程序自行管理内存，虽然有一点小小的消耗，但是带来了很大的编程便利。Redis的自动内存管理有以下几个特性：  

1. 不需要显示关闭open的key
2. 不需要显示关闭返回的副本集
3. 不需要显示关闭作为参数或返回值的RedisModuleString

通过一句简单的配置即可启用自动内存管理

```
RedisModule_AutoMemory(ctx);
```

自动内存相当于一个定时器，通过定期检查来释放无用内存，开启了自动内存管理之后，还是可以手动free来立刻释放内存（某些大内存场景需要即刻释放）。

自动内存管理是一个编程友好的功能，推荐使用，但是对于那些充满自信、富有经验的老程序员，也可以自己管理内存，以便能提高性能和内存使用率。


# Allocating memory into modules

Normal C programs use `malloc()` and `free()` in order to allocate and
release memory dynamically. While in Redis modules the use of malloc is
not technically forbidden, it is a lot better to use the Redis Modules
specific functions, that are exact replacements for `malloc`, `free`,
`realloc` and `strdup`. These functions are:

    void *RedisModule_Alloc(size_t bytes);
    void* RedisModule_Realloc(void *ptr, size_t bytes);
    void RedisModule_Free(void *ptr);
    void RedisModule_Calloc(size_t nmemb, size_t size);
    char *RedisModule_Strdup(const char *str);

They work exactly like their `libc` equivalent calls, however they use
the same allocator Redis uses, and the memory allocated using these
functions is reported by the `INFO` command in the memory section, is
accounted when enforcing the `maxmemory` policy, and in general is
a first citizen of the Redis executable. On the contrar, the method
allocated inside modules with libc `malloc()` is transparent to Redis.

Another reason to use the modules functions in order to allocate memory
is that, when creating native data types inside modules, the RDB loading
functions can return deserialized strings (from the RDB file) directly
as `RedisModule_Alloc()` allocations, so they can be used directly to
populate data structures after loading, instead of having to copy them
to the data structure.

## Pool allocator

Sometimes in commands implementations, it is required to perform many
small allocations that will be not retained at the end of the command
execution, but are just functional to execute the command itself.

This work can be more easily accomplished using the Redis pool allocator:

    void *RedisModule_PoolAlloc(RedisModuleCtx *ctx, size_t bytes);

It works similarly to `malloc()`, and returns memory aligned to the
next power of two of greater or equal to `bytes` (for a maximum alignment
of 8 bytes). However it allocates memory in blocks, so it the overhead
of the allocations is small, and more important, the memory allocated
is automatically released when the command returns.

So in general short living allocations are a good candidates for the pool
allocator.


# 在模块里分配内存
在模块写的代码和普通代码一样，当然也可以使用malloc等原始方式进行内存分配，但是是不推荐这么做的，而应该使用Redis模块化系统定制好的API。

```
void *RedisModule_Alloc(size_t bytes);
void* RedisModule_Realloc(void *ptr, size_t bytes);
void RedisModule_Free(void *ptr);
void RedisModule_Calloc(size_t nmemb, size_t size);
char *RedisModule_Strdup(const char *str);
```
顾名思义，这几个函数很好理解，调用也很方便，和原始的内存分配不同，这几个函数会使用和Redis相同的内存分配方式（jemalloc、tcmalloc、标准libc），这样模块也会根据环境来选择最适合的内存分配方式。

使用这些定制的API还有一个好处，就是Redis内存可以根据要分配的内存场景进行特殊处理。

## 池化内存分配
当需要多次分配数据结构的内存，为了防止多次向操作系统申请内存，可以合并操作，一次性向操作系统申请好要用的内存，然后在内部慢慢使用。

Redis模块化系统也提供了池化分配内存的能力，可以使用PoolAlloc命令

```
void *RedisModule_PoolAlloc(RedisModuleCtx *ctx, size_t bytes);
```

申请的内存大小为大于bytes的最小2次幂，池化分配减少了内存分配的开销（减少申请次数），而且能够用完后一次性释放所有内存，避免碎片，也能很好的被自动内存管理器管理。

对于大量临时的或者说生命周期短的内存分配，很适合使用池化分配方式。


# Writing commands compatible with Redis Cluster

Documentation missing, please check the following functions inside `module.c`:

    RedisModule_IsKeysPositionRequest(ctx);
    RedisModule_KeyAtPos(ctx,pos);


# 模块兼容集群模式
还没写，自己看源代码中的函数

```
RedisModule_IsKeysPositionRequest(ctx);
RedisModule_KeyAtPos(ctx,pos);
```

