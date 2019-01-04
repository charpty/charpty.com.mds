> 笔者博客地址：https://charpty.com       
> 本文代码委托在：https://github.com/charpty/cjvm

在说JVM的指令集前，先总结下近几篇文章以及后续的编码思路。在Java虚拟机规范中，按照

```java
整体架构 -> 编译器 -> class文件定义 -> 启动与类加载 -> 指令集
```

的方式讲述了虚拟机的设计，在张秀宏老师的动手用go写Java虚拟机书中，则是避开了很多复杂的模式，实现了一个实验性质的Java虚拟机，同时笔者也受封亚飞的揭秘Java虚拟机文章的影响，希望实现一个带动态编译和解释执行的虚拟机。

如此多的方式，笔者最终选择了一种“渐进式”的形式实现，一方面是考虑先易后难便于写代码，二来便于写文章，最终形式如下

```java
class文件解析 -> 运行时数据区 -> 指令集 -> JNI -> 内存管理与GC -> 启动与JDK加载 -> JIT -> 实战运行网站
```

其中`class文件解析`和`运行时数据区`和在之前已经写过，但是笔者在写后面文章时也发现了之前思路的一些问题，为了保留思路样本，就不直接修改原来的文章了，而是出“修订版”，比如对于文章`cjvm-1.md`，则其修订版本为`cjvm-1-m1.md`、`cjvm-1-m2.md`等，在修订版本前面说明修订的内容。



## 指令集概述

按虚拟机规范，将指令集划分为11中类型，分别是

- 常量：将一个字面常量推入栈顶，或从常量池获取常量并推入栈顶，最出名的是ldc指令

- 加载：将本地变量表中的某个变量推入栈顶

- 存储：和加载指令对应，这是将栈顶变量写回到本地变量表中

- 栈：对栈的各种操作

- 数学：在栈上进行加减乘除、位移、异或等数学操作

- 转换：long、int、char、byte、short等类型的各种转换操作

- 比较：比较两个变量并压入比较结果，同时也是条件语句实现的关键，通过比较进行跳转

- 控制：强制跳转和结果返回

- 引用：属性赋值、方法调用、并发同步、对象创建、抛出异常等操作

- 扩展：宽字扩展、多维数组相关指令

- 保留指令：仅关心调试指令即可

Java虚拟机规范一共规定了205条指令，其中3条是保留指令，在实际运行期间共有202条指令，通过仅仅200多条指令，就能模拟大多数汇编指令做的事情，简单又强大！



在引入静态编译和混合执行引擎之前，我们先全部使用解释执行引擎，相对于`JRockit`的全面静态编译执行而言，纯解释引擎要简单的多。



## 指令运行概要

我们使用结构体`BC_IPT`来表示字节码解释器ByteCodeInterpreter

> bytecode_interpreter.h

```c
#define INS_METHOD(OP) insm_##OP
#define REGISTER_INS_METHOD(r, op) r->call[op] = INS_METHOD(op)
// byte code interpreter
typedef struct BC_IPT
{
    // 对应205个指令，其opcode即数组下标
    void (*call[256])(Frame *frame, ByteCodeStream *stream);
} BC_IPT;

BC_IPT *buildByteCodeInterpreter();
int execute(BC_IPT *bcIpt, JThread *thread, Method *method);

```

我们使用一个函数指针数组来存储各个指令，通过`execute`方法可以执行指定方法，方法只能在指定线程上执行，这里传入的一般是`main`函数。

为了编程方便，我们205条指令的实现函数命名都统一为`insm_操作码`，比如`NOP`指令的操作码为0，那么它的实现函数名称为`insm_0`。这里提供了两个简单宏`INS_METHOD`和`REGISTER_INS_METHOD`来进一步简化方法注入指令集合。



执行指令的主要逻辑是

```c
创建并压入首个栈帧 -> 循环执行当前栈帧的代码段 -> 直到栈中没有栈帧
```

实现`execute`的主要逻辑如下

> bytecode_interpreter.c

```c
int execute(BC_IPT *bcIpt, JThread *thread, Method *method)
{
    Frame *frame = thread->createFrame(thread, method);
    pushFrame(thread, frame);
    ByteCodeStream *stream = (ByteCodeStream *)malloc(sizeof(ByteCodeStream));
    Frame *current;
    while ((current = currentFrame(thread)) != NULL)
    {
        thread->pc = frame->nextPC;
        stream->code = current->method->code;
        stream->pc = frame->nextPC;
        uint8_t opCode = readUint8(stream);
        // 在指令中实现对nextPC的设置
        (*bcIpt->call[opCode])(current, stream);
    }
}

```

其中`ByteCodeStream`用来记录一个栈帧中代码指向PC，也就是执行到哪一行了，各个指令可以通过设置PC来实现跳转。

第一`uint8`是操作码，操作码后紧跟着的是该操作码的操作数，每个指令的操作数长度不同，以`int8`和`int16`长度索引值居多，在读取了自己的操作数后，每个指令都需要重新设置PC到已读取后的位置。

大多数指令实现都是围着操作数栈转的，在硬件实现中有寄存器，但在JVM中没有，所以也没有像

```c
将寄存器edx值和寄存器eax的值相加，并将结果存储到寄存器eax中
```

这样的语法，所以JVM需要使用操作数栈来存储和获取操作数。



## 常量指令

常量指令顾名思义就是操作常量的，最简单的是真正的固定常量类型的操作，这些指令是不需要获取操作数的，指令即代表了整个操作。

比如`ICONST4`指令是将int类型数值4推入操作数栈

> ins_constant.h

```c
void insm_7(Frame *frame, ByteCodeStream *stream)
{
    // ICONST_4
    pushInt(frame->operandStack, 4);
}
```

再比如`LCONST_0`是将long类型数值0推入操作数栈

> ins_constant.h

```c
void insm_9(Frame *frame, ByteCodeStream *stream)
{
    // LCONST_0
    pushLong(frame->operandStack, 0);
}
```

也可以推入int类型负数-1和NULL值，还有将float、double类型的0或1推进操作数栈的，都是比较简单的常量指令。

在205条指令集中，int类型或者说小数值有特殊待遇，有`ICONST_0 ~ ICONST_5`，6个指令，个人认为这是基于经验进行的优化，大多数情况下，使用小数值的概率非常高，所以使用一条指令就能表达这些场景可以简化字节码，提高效率。



如果大小超过了5呢？那就需要使用`BIPUSH`或者`SIPUSH`指令，分别将8位或16位的数字推入操作数栈。

比如`BITPUSH 18`代表着将数字18推入操作数栈。

> ins_constant.h

```c
void insm_16(Frame *frame, ByteCodeStream *stream)
{
    // BIPUSH
    int x = nextInt8(stream);
    pushDouble(frame->operandStack, x);
    frame->nextPC = stream->pc;
}
```

之所以说`BITPUSH`比`ICONST_5` 耗性能，是因为`BITPUSH`需要去取一次操作数，`BITPUSH`的操作数的长度是8位，取道之后将其推入操作数栈，这样的话可以将任意`-128 ~ 127`的数字推入操作数栈。`SITPUSH`实现也是一样，推入值范围是带符号的`short`类型范围。



较为复杂的就是`LDC`指令了，它是将常量池中信息推入到操作数栈中。

// TODO

## 加载指令

加载指令的作用是将本地变量表的数据加载



## 存储指令

## 栈指令

## 数学指令

## 转换指令

## 比较指令

## 控制指令

## 引用指令

## 扩展指令

## 执行引擎
