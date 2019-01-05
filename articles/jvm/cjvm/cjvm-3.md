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

这也是必须的，因为实现总是由难到易，比如oop-klass模型，需等到实现GC时才涉及，这时就需要回头去改部分运行时数据区的代码。



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
    UPDATE_PC_AND_CONTINUE
}
```

再比如`LCONST_0`是将long类型数值0推入操作数栈

> ins_constant.h

```c
void insm_9(Frame *frame, ByteCodeStream *stream)
{
    // LCONST_0
    pushLong(frame->operandStack, 0);
    UPDATE_PC_AND_CONTINUE
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
    UPDATE_PC_AND_CONTINUE
}
```

之所以说`BITPUSH`比`ICONST_5` 耗性能，是因为`BITPUSH`需要去取一次操作数，`BITPUSH`的操作数的长度是8位，取道之后将其推入操作数栈，这样的话可以将任意`-128 ~ 127`的数字推入操作数栈。`SITPUSH`实现也是一样，推入值范围是带符号的`short`类型范围。

每次读取操作码和获取操作数之后，下一次待执行的代码位置都已发生变化，所以都需要设置下一个PC的位置。一般情况下，下一个PC的位置也就是当前读取完操作数之后的指针位置，所以我们做一个简单的宏来设置下一个PC。

```c
#define UPDATE_PC_AND_CONTINUE frame->nextPC = stream->pc;
```



较为复杂的就是`LDC`指令了，它是将常量池中信息推入到操作数栈中。`LDC`指令共有3条

```c
LDC     将int、float、String、类引用、方法引用等类型常量值从常量池中推送至栈顶
LDC_W   将int、float、String、类引用、方法引用等类型常量值从常量池中推送至栈顶（宽索引）
LDC2_W  将long或double型常量值从常量池中推送至栈顶（宽索引）
```

我们仅讨论`LDC`即可，`LDC_W`和`LDC`类似，差别在于使用了16位的常量池索引，它们都只能用于操作单精读数据，而`LDC2_W`则用于操作double和long类型。



LDC的实现逻辑也比较简单，首先从常量池获取索引对应常量

* 如果常量是int或者float类型，则直接推入操作数栈

* 如果常量是字符串引用，则找到该字符串对应的对象引用推入操作数栈

* 如果常量是类引用，则load该class被将其推入操作数栈

* 否则那就是方法类型MethodType或者方法句柄MethodHandler，它们的解析非常复杂，后面版本再完善



按照这个逻辑我们进行实现

> ins_constant.h

```c
void insm_18(Frame *frame, ByteCodeStream *stream)
{
    // LDC
    uint8_t index = nextUint8(stream);
    RCP *rcp = frame->method->clazz->constantPool;
    RCPInfo *rcpInfo = getRCPInfo(rcp, (uint32_t)index);

    if (rcpInfo->type == CONSTANT_Integer)
    {
        pushInt(frame->operandStack, *(int32_t *)rcpInfo->data);
    }
    else if (rcpInfo->type == CONSTANT_Float)
    {
        pushFloat(frame->operandStack, *(float *)rcpInfo->data);
    }
    else if (rcpInfo->type == CONSTANT_String)
    {
        InstanceOOP *oop = resloveStringReference(frame->method->clazz, (char *)rcpInfo->data);
        pushRef(frame->operandStack, oop);
    }
    else if (rcpInfo->type == CONSTANT_Class)
    {
        IMKlass *imkclass = resloveClassReference(frame->method->clazz, (char *)rcpInfo->data);
        pushRef(frame->operandStack, imkclass);
    }
    else
    {
        // Method Type | Method Handler
        // TODO
    }
    UPDATE_PC_AND_CONTINUE
}
```



## 加载指令

加载指令的作用是将本地变量表的数据加载到操作数栈中，这部分指令比较直白。



把本地变量中第一个位置的int类型数值推入操作数栈中

```c
void insm_26(Frame *frame, ByteCodeStream *stream)
{
    // ILOAD_0
    pushInt(frame->operandStack, getInt(frame->localVars, 0));
    UPDATE_PC_AND_CONTINUE
}
```

当然还有将long、float、double等类型推入栈顶，都是类似的



也可以将指定下标的元素推入操作数栈，比如将指定下标的long类型推入操作数栈

```c
void insm_22(Frame *frame, ByteCodeStream *stream)
{
    // LLOAD
    pushLong(frame->operandStack, getLong(frame->localVars, nextInt8(stream)));
    UPDATE_PC_AND_CONTINUE
}

```

除了推入基础类型，还可以将指定数组中的元素推入操作数栈，比如将Boolean类型数组中的某个元素推入操作数栈

```c
void insm_51(Frame *frame, ByteCodeStream *stream)
{
    // BALOAD
    int32_t index = popInt(frame->operandStack);
    int8_t *arrRef = (int8_t *)popRef(frame->operandStack);
    pushInt(frame->operandStack, (int32_t)arrRef[index]);
    UPDATE_PC_AND_CONTINUE
}
```

在`BALOAD`实现中我可以看到，并没有取操作码后面的操作数，而是从操作数栈中弹出元素的下标和数组引用。



## 存储指令

加载指令的作用是将本地变量表中的数据加载到操作数栈，而存储指令的作用则恰恰相反。



仅举一个例子，将float类型的数据从操作数栈中弹出并存储到本地变量表指定位置中

```c
void insm_56(Frame *frame, ByteCodeStream *stream)
{
    // FSTORE
    setFloat(frame->localVars, nextInt8(stream), popFloat(frame->operandStack));
    UPDATE_PC_AND_CONTINUE
}
```



## 栈指令

大多数操作都是围绕操作数栈的，所以少不了对操作数栈的各种操作，总共有9个指令，都是对标准栈的常见操作。



最基本的弹出

```c
void insm_87(Frame *frame, ByteCodeStream *stream)
{
    // POP
    popVar(frame->operandStack);
    UPDATE_PC_AND_CONTINUE
}
```

一次弹出两个

```c
void insm_88(Frame *frame, ByteCodeStream *stream)
{
    // POP2
    popVar(frame->operandStack);
    popVar(frame->operandStack);
    UPDATE_PC_AND_CONTINUE
}
```

复制栈顶元素

```c
void insm_89(Frame *frame, ByteCodeStream *stream)
{
    // DUP
    union Slot *x = popVar(frame->operandStack);
    pushVar(frame->operandStack, x);
    pushVar(frame->operandStack, x);
    UPDATE_PC_AND_CONTINUE
}
```

复制两个

```c
void insm_92(Frame *frame, ByteCodeStream *stream)
{
    // DUP2
    union Slot *x1 = popVar(frame->operandStack);
    union Slot *x2 = popVar(frame->operandStack);

    pushVar(frame->operandStack, x2);
    pushVar(frame->operandStack, x1);
    pushVar(frame->operandStack, x2);
    pushVar(frame->operandStack, x1);
    UPDATE_PC_AND_CONTINUE
}
```

交换栈顶元素

```c
void insm_95(Frame *frame, ByteCodeStream *stream)
{
    // SWAP
    union Slot *x1 = popVar(frame->operandStack);
    union Slot *x2 = popVar(frame->operandStack);

    pushVar(frame->operandStack, x1);
    pushVar(frame->operandStack, x2);
    UPDATE_PC_AND_CONTINUE
}
```

当然还有稍微麻烦点的，比如复制栈顶值并将其插入栈顶第二个位置下面

```c
void insm_90(Frame *frame, ByteCodeStream *stream)
{
    // DUP_X1
    union Slot *x1 = popVar(frame->operandStack);
    union Slot *x2 = popVar(frame->operandStack);

    pushVar(frame->operandStack, x1);
    pushVar(frame->operandStack, x2);
    pushVar(frame->operandStack, x1);
    UPDATE_PC_AND_CONTINUE
}
```

另外还有组合变种`DUP2_X1`、`DUP2_X2`，道理都一样。



## 数学指令

数学指令就是进行各种数学运算，加减乘除、位运算、取模、取负等。和硬件CPU只能对寄存器进行操作类似，数学指令也只能对操作数栈中的数据进行运算，并只能将结果写入操作数栈。



将栈顶两个int类型数相加，并将结果存入操作数栈

```c
void insm_96(Frame *frame, ByteCodeStream *stream)
{
    // IADD
    int32_t x1 = popInt(frame->operandStack);
    int32_t x2 = popInt(frame->operandStack);
    pushInt(frame->operandStack, (x1 + x2));
    UPDATE_PC_AND_CONTINUE
}
```

其它还有long、float、double等类型的相加。

再比如乘法，将两个long类型数值相乘

```c
void insm_105(Frame *frame, ByteCodeStream *stream)
{
    // LMUL
    int64_t x1 = popLong(frame->operandStack);
    int64_t x2 = popLong(frame->operandStack);
    pushLong(frame->operandStack, (x1 * x2));
    UPDATE_PC_AND_CONTINUE
}
```

除了普通的加减乘除，还有常用的取负和取模，其实不管什么操作，解释器执行都是先从操作数栈中取出数据，然后利用C的语言执行运算，最后再将结果推入操作数栈中。

最后再看下位运算操作，比如两个int按位与

```c
void insm_126(Frame *frame, ByteCodeStream *stream)
{
    // LMUL
    int32_t x1 = popInt(frame->operandStack);
    int32_t x2 = popInt(frame->operandStack);
    pushInt(frame->operandStack, (x1 & x2));
    UPDATE_PC_AND_CONTINUE
}
```

还有各种类型的异或与位移操作，最后比较特殊的是无符号右移，也就是Java支持的`>>>`符号，我们通过先将其转换为无符号再右移来实现。

```c
void insm_125(Frame *frame, ByteCodeStream *stream)
{
    // LUSHR
    uint32_t offset = (uint32_t)popInt(frame->operandStack);
    int64_t x = popLong(frame->operandStack);
    pushInt(frame->operandStack, ((u_int64_t)x) >> offset);
    UPDATE_PC_AND_CONTINUE
}
```



## 转换指令

JVM标准提供了15条转换指令



将int类型转换为byte并将结果推入栈顶

```c
void insm_133(Frame *frame, ByteCodeStream *stream)
{
    // I2L
    int32_t x = popInt(frame->operandStack);
    pushLong(frame->operandStack, (int64_t)x);
    UPDATE_PC_AND_CONTINUE
}
```

将double转换为long

```c
void insm_143(Frame *frame, ByteCodeStream *stream)
{
    // D2L
    double x = popDouble(frame->operandStack);
    pushLong(frame->operandStack, (int64_t)x);
    UPDATE_PC_AND_CONTINUE
}
```

其它13条都是类似的



## 比较指令





## 控制指令

## 引用指令

## 扩展指令
