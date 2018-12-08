> 笔者博客地址：https://charpty.com       
> 本文代码（章节名即分支名）委托在：https://github.com/charpty/cjvm



之前我们已经将class文件字节流解析为`ClassFile`结构体，为了能够运行Java程序，我们还需要构建一块内存区域，用来存放运行时用到的符号、指令、数据等信息，这个区域在虚拟机规范中称为运行时数据区。



运行时数据区包含程序计数器PC、Java虚拟机栈、堆区、方法区、运行时常量池、本地方法栈几大区域。其中PC、Java虚拟机栈是每个线程独有的，跟随线程的生命周期产生和销毁，而堆区、方法区则是线程共享的，随着虚拟机的生命周期创建和销毁，运行时常量池也是线程共享的，但它是在类被加载时才产生的，所以额外拿出来说下。



在这一章节还和前面解析`ClassFile`结构体一样，无法实际运行Java代码，只能使用单元测试例检测我们的C代码。这一章节的工作也比较独立，我们的目标是构建出上述6大区域中的3个，其中本地方法栈等后面我们编写JNI时再补充，方法区涉及类加载子系统、堆区涉及代划分与GC比较复杂。另外，笔者原本打算先用Java SE7规范实现，后续再用Java SE11改一遍并对比有何变化，但为了减少工作且不做重复功，这章开始直接参考Java SE11的规范。



笔者采用实现过程的顺序一一讲述，分为

> 线程  ->  栈帧  ->  运行时常量池

## 线程

前面说了这5大区域分为两种，一种是线程私有的，一种是线程共享的，总之是以线程角度来区分的，那么首先我们得有线程。一个Java程序只要运行起来就会有多个线程，有主线程`main`，有垃圾回收前钩子线程`Finalizer`，有信号处理`Signal Dispatcher，有垃圾回收辅助Reference Handler，有垃圾回收Common-Cleaner（之前的GC-*）。



我们使用`JThread`结构体来对应Java的线程

> thread.c

```c
// https://docs.oracle.com/javase/specs/jvms/se11/html/jvms-2.html#jvms-2.6
typedef struct Stack
{
 uint32_t maxSize;
 uint32_t size;
 // 栈中存的都是一个又一个栈帧
 struct Frame *topFrame;
} Stack;

// Java11 Run-Time Data Areas: https://docs.oracle.com/javase/specs/jvms/se11/html/jvms-2.html#jvms-2.5
typedef struct JThread
{
    int pc;
    // 每个线程都私有一个Java虚拟机栈
    struct Stack stack;
} JThread;
```

PC计数器用于指向当前执行的指令位置，Java虚拟机栈用于存储当前线程执行的一堆方法信息和数据信息。线程中最重要的就是虚拟机栈中的栈帧，也就是上面的`Frame`结构体，它决定了线程“要干什么”，线程的创建着总伴随着第一个栈帧（线程总得干点什么），不断的消化栈帧，直到虚拟机栈为空，这时无事可做线程也就没有存在的意义。



为了以上能进行以上几个操作，我们为`JThread`添加几个方法



```c
struct JThread *createThread();
struct Frame *createFrame(struct JThread *thread);

int getPC(struct JThread *thread);
void setPC(struct JThread *thread, int pc);

void pushFrame(struct JThread *thread);
struct Frame *popFrame(struct JThread *thread);
struct Frame *currentFrame(struct JThread *thread);
```



由于以上几个方法很简单，是平常的栈操作，顾名思义即可知道实现，这里不再列出实现代码，有需要到本文开头笔者的github上查看。



## 栈帧

线程中的虚拟机栈很重要，是线程私有的不能被其它线程访问，而虚拟机栈是由一片片栈帧组成，栈帧是什么呢，在Oracle虚拟机规范中解释是

> A*frame*is used to store data and partial results, as well as to perform dynamic linking, return values for methods, and dispatch exceptions



在当前阶段，我们就把它想做是“方法”吧，虚拟机栈中存储了一个有一个待执行的方法。我们使用`Stack`和`Frame`来表示虚拟机栈和栈帧。

> frame.c

```c
typedef struct Frame
{
    // 栈中桢通过链表形式连接
    Frame *lower;
    // 本地变量表
    LocalVars *localVars;
    // 操作数栈
    OperandStack *operandStack;
    // 所属线程
    struct Thread *thread;
    // 当前帧所在方法
    struct Method *method;
    // 下一个执行指令位置
    int nextPC;
} Frame;
```

栈帧中最重要的是本地变量表和操作数栈，这两个结构体是大多数指令实现时要用到的，通过这两个简单的结构体就可以完成大多数计算、赋值等指令。



首先来看本地变量表，虚拟机规范规定，单个变量空间要能存储`boolean`、`byte`、`char`、`short`、`int`、`float`、`reference`、`returnAddress`类型的值，两个连续变量空间要能存储`long`、`double`。由于笔者使用的是osx系统，精力有限也就只管实现本地电脑上的版本了。



我们使用一个联合体来存储一个本地变量

> frame.c

```c
typedef union LocalVar {
    int32_t num;
    void *ref;
} LocalVar;

typedef struct LocalVars
{
    // 保存代码执行过程中本地变量的值
    uint32_t size;
    union LocalVar **localVars;
} LocalVars;
```



操作数栈和本地变量表结构相同，只是意义不同，本地变量是用于存储值，而操作数栈只是一个辅助指令执行的临时结构，这个结构仅是模拟物理机CPU操作堆栈。

> frame.c

```c
typedef struct OperandStack
{
    // 只是模拟指令执行的栈，没有存储意义
    uint32_t size;
    // 模拟链表存储，使用数组存储有些浪费
    union LocalVar **vars;
} OperandStack;
```



当然，我们还得提供一整套操作本地变量表和操作数栈的函数。

> frame.c

```c
void *getThis(struct LocalVars *vars);
void setRef(struct LocalVars *vars, uint32_t index, void *ref);
void *getRef(struct LocalVars *vars, uint32_t index);
void setVar(struct LocalVars *vars, uint32_t index, union LocalVar *var);
union LocalVar *getVar(struct LocalVars *vars, uint32_t index);
void setInt(struct LocalVars *vars, uint32_t index, int32_t value);
int32_t getInt(struct LocalVars *vars, uint32_t index);
void setLong(struct LocalVars *vars, uint32_t index, int64_t value);
int64_t getLongstruct(LocalVars *localVars, uint32_t index);
void setFloat(struct LocalVars *vars, uint32_t index, float value);
float getFloat(struct LocalVars *vars, uint32_t index);
void setDobule(struct LocalVars *vars, uint32_t index, double value);
double getDobule(struct LocalVars *vars, uint32_t index);
void pushRef(struct OperandStack *stack, void *ref);
void *popRef(struct OperandStack *stack);
void *topRef(struct OperandStack *stack);
void pushVar(struct OperandStack *stack, union LocalVar *var);
union LocalVar *popVar(struct OperandStack *stack);
void pushBoolean(struct OperandStack *stack, int8_t *value);
int8_t popBoolean(struct OperandStack *stack);
void popInt(struct OperandStack *stack, int32_t value);
int32_t popInt(struct OperandStack *stack);
void pushLong(struct OperandStack *stack, int64_t value);
int64_t popLong(struct OperandStack *stack);
void pushFloat(struct OperandStack *stack, float value);
float popFloat(struct OperandStack *stack);
void pushDouble(struct OperandStack *stack, double value);
double popDouble(struct OperandStack *stack);
```



## 运行时常量池




