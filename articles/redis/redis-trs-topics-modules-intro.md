## Redis模块化原文意译与解析

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
本文章用于介绍Redis模块，分为以下几个文件

INTRO.md（当前文件），Redis模块化的概要介绍，先读这个比较好。   
API.md，介绍Redis的模块化提供的所有API，每个函数都有详细介绍。   
BLOCK.md，这个就厉害了，介绍写一个阻塞客户端但不阻塞服务器的命令。   

Redis内部命令的实现也使用了模块化，这种模式使得可以方便的自定义扩展模块，扩展的模块也可以方便的利用Redis中本来只能内部使用的优良特性。

Redis的模块化主要利用的是动态库（Windows的dll、Linux的so）特性，想实现自己的模块，需要实现```redismodule.h```头文件，用C和C++或其他语言写都行，只要最后能编译成so文件就可以。

Redis还是比较有良心的，模块化API不会大的调整或者会做高版本兼容，所以写好一个模块，编译好了就可以在多个Redis版本中使用而勿须改代码或重新编译。

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

你可以通过配置或命令方式来加载或卸载自己写的模块，也可以查看已加载的模块情况。

注册模块时，注册名默认是文件名filename去掉尾缀，好好取名，不然久后自己都不知道哪个模块对应着自己写的那个so了。


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

对自定义命令取名字很重要，要防止冲突，一般的做法就是加上自己的命令空间，比如支付系统用的都叫pay.xxx，订单系统用的都叫order.xxx，官方建议使用实际调用的命令实现函数名称以点号分割。




