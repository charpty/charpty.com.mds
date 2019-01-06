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

- __栈：对栈的各种操作

- 数学：在栈上进行加减乘除、位移、异或等数学操作

- 转换：long、int、char、byte、short等类型的各种转换操作

- 比较：比较两个变量并压入比较结果，同时也是条件语句实现的关键，通过比较进行跳转

- 控制：强制跳转和结果返回

- 引用：属性赋值、方法调用、并发同步、对象创建、抛出异常等操作

- 扩展：宽字扩展、多维数组相关指令

- 保留：仅关心调试指令即可

Java虚拟机规范一共规定了205条指令，其中3条是保留指令，在实际运行期间共有202条指令，通过仅仅200多条指令，就能模拟大多数汇编指令做的事情，简单又强大！如何将代码有效的编译成一个个的指令则是编译器的事情，后续我们再分析。

我们不讨论扩展和保留指令，在目前用不着。



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
        IKlass *clazz = resloveClassReference(frame->method->clazz, (char *)rcpInfo->data);
        pushRef(frame->operandStack, getInstaceMirroClass(clazz));
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

> ins_load.h

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

> ins_load.h

```c
void insm_22(Frame *frame, ByteCodeStream *stream)
{
    // LLOAD
    pushLong(frame->operandStack, getLong(frame->localVars, nextInt8(stream)));
    UPDATE_PC_AND_CONTINUE
}

```

除了推入基础类型，还可以将指定数组中的元素推入操作数栈，比如将Boolean类型数组中的某个元素推入操作数栈

> ins_load.h

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

> ins_store.h

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

> ins_stack.h

```c
void insm_87(Frame *frame, ByteCodeStream *stream)
{
    // POP
    popVar(frame->operandStack);
    UPDATE_PC_AND_CONTINUE
}
```

一次弹出两个

> ins_stack.h

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

> ins_stack.h

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

> ins_stack.h

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

> ins_stack.h

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

> ins_stack.h

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

> ins_math.h

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

> ins_math.h

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

> ins_math.h

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

> ins_math.h

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

> ins_convert.h

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

> ins_convert.h

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

比较指令包含两个功能

* 比较两个值，并将结果推入操作数栈

* 比较两个值，当结果符合预期时进行跳转

前者就是常见比较了

```java
boolean isDone = time > 500
```

后者就是`if`、`for`、`while`等条件型跳转了（还得结合控制指令），这是实现循环和条件控制的关键。



先看简单的比较，比较两个long类型数值并将结果压入操作数栈中。

> ins_compare.h

```c
void insm_148(Frame *frame, ByteCodeStream *stream)
{
    // LCMP
    long v2 = popLong(frame->operandStack);
    long v1 = popLong(frame->operandStack);
    pushInt(frame->operandStack, v1 > v2 ? 1 : (v1 == v2 ? 0 : -1));
    UPDATE_PC_AND_CONTINUE
}
```

容易理解，使用0表示相等，1表示第一个值更大，-1表示第二个值更大。

对于浮点型数据，则还存在数值为`NaN`的情况，此时不同指令处理结果不相同，`DCMPL`表示在有double类型数值为`NaN`时压入结果-1，而对应的`DCMPG`则代表有double类型数值为`NaN`时压入1。

> ins_compare.h

```c
void insm_151(Frame *frame, ByteCodeStream *stream)
{
    // DCMPL
    double v2 = popFloat(frame->operandStack);
    double v1 = popFloat(frame->operandStack);
    pushInt(frame->operandStack, v1 > v2 ? 1 : (v1 == v2 ? 0 : -1));
    UPDATE_PC_AND_CONTINUE
}
```

这里没有出现判断NaN情况，其实是简化了，相当于代码

```c
pushInt(frame->operandStack, v1 > v2 ? 1 : (v1 == v2 ? 0 : -1));
```

或者

```c
if (v1 > v2)
{
    pushInt(frame->operandStack, 1);
}
else if (v1 == v2)
{
    pushInt(frame->operandStack, 0);
}
else if (v1 < v2)
{
    pushInt(frame->operandStack, -1);
}
else
{
    // 数值为NaN的情况
    pushInt(frame->operandStack, -1);
}
```

对应的，`DCMPG`的代码为

> ins_compare.h

```c
void insm_152(Frame *frame, ByteCodeStream *stream)
{
    // DCMPG
    float v2 = popFloat(frame->operandStack);
    float v1 = popFloat(frame->operandStack);
    pushInt(frame->operandStack, v1 < v2 ? -1 : (v1 == v2 ? 0 : 1));
    UPDATE_PC_AND_CONTINUE
}

```



条件跳转也是类似的，只不过不是将结果压入操作数栈，而是跳转到指定位置

比如，比较栈顶两个int的值，如果相等则跳转

> ins_compare.h

```c
void insm_159(Frame *frame, ByteCodeStream *stream)
{
    // IF_ICMPEQ
    int32_t v2 = popInt(frame->operandStack);
    int32_t v1 = popInt(frame->operandStack);
    int32_t offset = (int32_t)nextInt16(stream);
    if (v1 == v2)
    {
        frame->nextPC = frame->thread->pc + offset;
    }
}
```

也可以比较栈顶值与0的关系，比如栈顶值小于等于0则跳转

> ins_compare.h

```c
void insm_158(Frame *frame, ByteCodeStream *stream)
{
    // IFLE
    int32_t v = popInt(frame->operandStack);
    int32_t offset = (int32_t)nextInt16(stream);
    if (v <= 0)
    {
        frame->nextPC = frame->thread->pc + offset;
    }
}
```

除了比较基础数值，也可以比较引用是否相同。比如判断栈顶两个引用，如果不相同则跳转

> ins_compare.h

```c
void insm_166(Frame *frame, ByteCodeStream *stream)
{
    // IF_ACMPNE
    void *r2 = popRef(frame->operandStack);
    void *r1 = popRef(frame->operandStack);
    int32_t offset = (int32_t)nextInt16(stream);
    if (r1 != r2)
    {
        frame->nextPC = frame->thread->pc + offset;
    }
}
```



## 控制指令

`JSR`和`RET`用于控制finally子句， 在新版本里已不再使用，我们也不在讨论。

剩下的其实也就3种，第一种是无条件跳转`GOTO`

> ins_control.h

```c
void insm_167(Frame *frame, ByteCodeStream *stream)
{
    // GOTO
    int32_t offset = (int32_t)nextInt16(stream);
    frame->nextPC = frame->thread->pc + offset;
}
```

第二种则是`switch`语句，有两种语句，一种是case的值是连续，一种是不连续的。

连续的case值是使用`TABLESWITCH`指令

> ins_control.h

```c
void insm_170(Frame *frame, ByteCodeStream *stream)
{
    // TABLESWITCH
    skipPadding(stream);
    int32_t defaultOffset = nextInt32(stream);
    int32_t low = nextInt32(stream);
    int32_t high = nextInt32(stream);
    int32_t offsetCount = high - low + 1;
    int32_t *offsets = nextInt32s(stream, offsetCount);
    int32_t index = popInt(frame->operandStack);
    int32_t offset;
    if (index >= low && index <= high)
    {
        offset = offsets[index - low];
    }
    else
    {
        offset = defaultOffset;
    }
    frame->nextPC = frame->thread->pc + offset;
} 
```

`TABLESWITCH`操作码后紧跟的是0～3个字节的填充字节，需要跳过。跳转策略也很好理解，跳到哪里执行和当前index有关，如果index在`switch`第一个case和最后一个case之间则是合法的，取道其case下的代码位置进行跳转，否则跳转到默认的位置。

`TABLESWITCH`的case值是连续的，用下标即可访问，而`LOOKUP_SWITCH`则是采用类似MAP的形式来存放offset的，我们使用一个数组来存储这样的关系，数组第i个值表示key，第i+1个值表示offset。

> ins_control.h

```c
void insm_171(Frame *frame, ByteCodeStream *stream)
{
    // LOOKUPSWITCH
    int32_t key = popInt(frame->operandStack);
    int32_t defaultOffset = nextInt32(stream);
    int32_t offsetCount = nextInt32(stream);
    int32_t *offsets = nextInt32s(stream, offsetCount);
    for (int i = 0; i < offsetCount; i = i + 2)
    {
        if (offsets[i] == key)
        {
            int32_t offset = offsets[i + 1];
            frame->nextPC = frame->thread->pc + offset;
            break;
        }
    }
}
```



第三种是return类型指令，都类似，就看一个返回int数值的例子

> ins_control.h

```c
void insm_172(Frame *frame, ByteCodeStream *stream)
{
    // IRETURN
    JThread *thread = frame->thread;
    Frame *currentFrame = popFrame(thread);
    Frame *invokerFrame = topFrame(thread);
    pushInt(invokerFrame->operandStack, popInt(currentFrame->operandStack));
}
```

将当前的Frame弹出，并将当前的Frame栈顶的int数值压入上一个Frame的操作数栈。



## 引用指令

引用指令是最为复杂的指令集了，主要功能是对方法和对象进行操作，大致分为创建对象、对象检查、获取类的属性和方法、调用方法、对象锁、异常几种类型。



首先来看创建对象，最简单的就是`NEW`指令了，它会创建一个对象，并将其引用压入操作数栈

> ins_reference.h

```c
void insm_187(Frame *frame, ByteCodeStream *stream)
{
    // NEW
    int16_t index = (int16_t)nextInt16(stream);
    IKlass *clazz = frame->method->clazz;
    char *className = ((ClassRef *)getRCPInfo(clazz->constantPool, index)->data)->classname;
    IKlass *refClass = resloveClassReference(clazz, className);
    if (!isClassInit(refClass))
    {
        initClass(refClass);
    }
    InstanceOOP *oop = newObject(refClass);
    pushRef(frame->operandStack, oop);
    UPDATE_PC_AND_CONTINUE
}
```



获取数组长度

> ins_reference.h

```c
void insm_190(Frame *frame, ByteCodeStream *stream)
{
    // ARRAYLENGTH

    ArrayOOP *arrayRef = (ArrayOOP *)popRef(frame->operandStack);
    if (arrayRef == NULL)
    {
        // java.lang.NullPointerException
    }
    pushInt(frame->operandStack, arrayRef->length);

    UPDATE_PC_AND_CONTINUE
}
```



获取类的某个静态属性的值

> ins_reference.h

```c
void insm_178(Frame *frame, ByteCodeStream *stream)
{
    // GETSTATIC
    int16_t index = nextInt16(stream);
    IKlass *clazz = frame->method->clazz;
    MemberRef *fieldRef = (MemberRef *)getRCPInfo(clazz->constantPool, index)->data;
    Field *field = resloveFieldReference(fieldRef);
    if (!isClassInit(field->clazz))
    {
        initClass(field->clazz);
    }
    char *descriptor = field->descriptor;
    uint32_t index = field->slotIndex;
    Slots *slots = getStaticVars(field->clazz);

    char flag = descriptor[0];
    if (flag == 'Z' || flag == 'B' || flag == 'C' || flag == 'S' || flag == 'I')
    {
        pushInt(frame->operandStack, getSlotInt(slots, index));
    }
    else if (flag == 'F')
    {
        pushFloat(frame->operandStack, getSlotFloat(slots, index));
    }
    else if (flag == 'J')
    {
        pushLong(frame->operandStack, getSlotLong(slots, index));
    }
    else if (flag == 'D')
    {
        pushDouble(frame->operandStack, getSlotDouble(slots, index));
    }
    else if (flag == 'L')
    {
        pushRef(frame->operandStack, getSlotRef(slots, index));
    }
    else
    {
    }
    UPDATE_PC_AND_CONTINUE
}
```

属性的存储顺序是固定的，每个属性只是对应下标的`Slot`而已，静态属性是直接存在类中的，所以我们通过`IKlass`的`getStaticVars`方法即可获得静态属性数组。

而成员属性也是类似的，只不过是从对象中获取属性数组，对象则是从操作数栈中弹出

> ins_reference.h

```c
// 对比与静态属性的：Slots *slots = getStaticVars(field->clazz);
InstanceOOP *oop = (InstanceOOP *)popRef(frame->operandStack);
Slots slots =  getIntanceVars(oop);
```

由于方法和属性表现是完全类似的，都是使用类名称、名称、描述符来表示一个属性或方法，所以这里就不再重复描述静态方法和实例方法的获取了。



我们再来实现方法调用，分为几种

JVM使用`INVOKE_SPECIAL`专门用于调用对象的构造方法

> ins_reference.h

```c
void insm_183(Frame *frame, ByteCodeStream *stream)
{
    // INVOKESPECIAL
    int16_t methodRefIndex = nextInt16(stream);
    IKlass *clazz = frame->method->clazz;
    RCP *rcp = clazz->constantPool;
    MemberRef *methodRef = (MemberRef *)getRCPInfo(clazz->constantPool, methodRefIndex)->data;
    Method *method = resloveMethodReference(methodRef);

    if (method->name == "<init>" && clazz != method->clazz)
    {
        // java.lang.NoSuchMethodError
    }
    if (isMethodStatic(method))
    {
        // java.lang.IncompatibleClassChangeError
    }

    void *ref = getRefFromTop(frame->operandStack, method->argCount - 1);
    if (ref == NULL)
    {
        // java.lang.NullPointerException
    }

    if (isMethodProtected(method))
    {
        // java.lang.IllegalAccessError
    }

    Method *methodToBeInvoked = lookupMethodInClass(clazz, method);

    JThread *thread = frame->thread;
    Frame *newFrame = thread->createFrame(thread, methodToBeInvoked);
    pushFrame(thread, newFrame);

    uint32_t argSlotCount = method->argCount;
    if (argSlotCount > 0)
    {
        for (int i = argSlotCount - 1; i >= 0; i--)
        {
            union Slot *slot = popVar(newFrame->operandStack);
            setVar(newFrame->localVars, (uint32_t)i, slot);
        }
    }
}
```

方法的调用就是创建新的栈帧并压入线程栈中，过程涉及到参数的传递和方法的查找。

之所以需要查找方法，是因为Java中允许方法多态，子类可以继承父类的方法，到底调用哪个方法需要在运行时决定。



其实已经可以想见，`INVOKE_STATIC`也是和上面代码类似，只是省去了方法查找的过程，同时`INVOKE_VIRTUAL`也几乎上述代码相同，只是省去了部分判断。



异常和监视器锁涉及到内存管理模型，后续再讲解。
