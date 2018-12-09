> 笔者博客地址：https://charpty.com       
> 本文代码委托在：https://github.com/charpty/cjvm



之前我们已经将class文件字节流解析为`ClassFile`结构体，为了能够运行Java程序，我们还需要构建一块内存区域，用来存放运行时用到的符号、指令、数据等信息，这个区域在虚拟机规范中称为运行时数据区。



运行时数据区包含程序计数器PC、Java虚拟机栈、堆区、方法区、运行时常量池、本地方法栈几大区域。其中PC、Java虚拟机栈是每个线程独有的，跟随线程的生命周期产生和销毁，而堆区、方法区则是线程共享的，随着虚拟机的生命周期创建和销毁，运行时常量池也是线程共享的，但它是在类被加载时才产生的，所以额外拿出来说下。

上述几个名称的术语，都是[Oracle JVM 11](https://docs.oracle.com/javase/specs/jvms/se11/html/index.html)规范中的术语，笔者在实现时也尽量按照这个规定来实现，保证每一个术语都一一对应的出现在代码里，但由于实现时有性能、便利性、语法限制等因素，所以并不能完全（包括官方实现）包含规范中的每一个概念。



在这一章节还和前面解析`ClassFile`结构体一样，无法实际运行Java代码，只能使用单元测试例检测我们的C代码。这一章节的工作也比较独立，我们的目标是构建出上述6大区域中的3个，其中本地方法栈等后面我们编写JNI时再补充，方法区涉及类加载子系统、堆区涉及代划分与GC比较复杂也后续实现，所以本章的内容更多是理论知识，相对还属于比较简单的。

另外，笔者原本打算先用Java SE7规范实现，后续再用Java SE11改一遍并对比有何变化，但为了减少工作且不做重复功，这章开始直接参考Java SE11的规范，写作不易，除了深入理解，提高效率也很重要。



笔者按照实现过程的顺序一一讲述，分为

> 线程  ->  栈帧  ->  运行时常量池 -> 类klass

## 线程

前面说了这5大区域分为两种，一种是线程私有的，一种是线程共享的，总之是以线程角度来区分的，那么首先我们得有线程。一个Java程序只要运行起来就会有多个线程，有主线程`main`，有垃圾回收前钩子线程`Finalizer`，有信号处理`Signal Dispatcher，有垃圾回收辅助Reference Handler，有垃圾回收Common-Cleaner（之前的GC-*）。

通过VisualVM、jstack命令都可以查看一个简单Java程序启动时JVM所运行的线程，通过一段简单Java代码也非常方便

```java
public class PrintRunThreadInJava11 {
    public static void main(String[] args) {
        Thread.getAllStackTraces().keySet().stream().forEach((t) -> {
            System.out.println(t.getThreadGroup() + " : " + t.getName());
        });
    }
}
```

现在看到的这些Java线程，我们都使用`JThread`结构体来表示

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
    // 创建Frame的操作比较复杂多变
    struct Frame (*createFrame)(struct JThread *thread);
} JThread;
```

PC程序计数器用于指向当前执行的指令位置，PC计数器在`javac`编译时就已经指定好，编译过程是一个`词法解析 -> 语法解析 -> 语义分析`的复杂过程，这里我们只需要用好PC即可而不必关系它是如何生成的。



Java虚拟机栈用于存储当前线程执行的一堆方法信息和数据信息，线程中最重要的结构就是虚拟机栈中的栈帧，也就是上面的`Frame`结构体，它决定了线程“要干什么”，线程的创建着总伴随着第一个栈帧（线程总得干点什么），不断的消化栈帧，直到虚拟机栈为空，这时无事可做线程也就没有存在的意义。



为了以上能进行获取PC、获取和推入栈帧等几个基本操作，我们为`JThread`添加几个方法

```c
struct JThread *createThread();
int getPC(struct JThread *thread);
void setPC(struct JThread *thread, int pc);

void pushFrame(struct JThread *thread);
struct Frame *popFrame(struct JThread *thread);
struct Frame *currentFrame(struct JThread *thread);
```



由于以上几个方法很简单，是很平常的栈操作，顾名思义即可知道实现，这里不再列出实现代码，有需要到本文开头笔者的github上查看。



## 栈帧

线程中的虚拟机栈很重要，是线程私有的不能被其它线程访问，而虚拟机栈是由一片片栈帧组成，栈帧是什么呢，在Oracle虚拟机规范中解释是

> A*frame*is used to store data and partial results, as well as to perform dynamic linking, return values for methods, and dispatch exceptions



栈帧可以说最复杂的虚拟机结构之一了，在HotSpot的实现中，会调用entry_point例程来创建栈帧，自信的笔者也看了不少遍了，涉及比较多的汇编知识，不是一时半会能描述清楚的。所以在当前阶段，我们使用C代码来模拟栈帧，就把栈帧想做是“方法”吧，虚拟机栈中存储了一个有一个待执行的方法。我们使用`Stack`和`Frame`来表示虚拟机栈和栈帧。

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



首先来看本地变量表，虚拟机规范规定，单个变量空间要能存储`boolean`、`byte`、`char`、`short`、`int`、`float`、`reference`、`returnAddress`类型的值，两个连续变量空间要能存储`long`、`double`。由于本地变量表和操作数栈都使用同一种存储单元，我们就使用名为`Slot`的联合体（同OpenJDK）来存储它。

> frame.h

```c
typedef union Slot {
    int32_t num;
    void *ref;
} Slot;
```

笔者使用的是osx系统，精力有限也就只管实现本地电脑上的版本了，笔者本地是64位系统。


本地变量就是存储着一个个Slot

> frame.h

```c
typedef struct LocalVars
{
    // 保存代码执行过程中本地变量的值
    uint32_t size;
    union Slot **vars;
} LocalVars;
```



操作数栈和本地变量表结构相同，只是意义不同，本地变量是用于存储值，而操作数栈只是一个辅助指令执行的临时结构，这个结构仅是模拟物理机CPU操作堆栈。

> frame.h

```c
typedef struct OperandStack
{
    // 只是模拟指令执行的栈，没有存储意义
    uint32_t size;
    // 模拟链表存储，使用数组存储有些浪费
    union Slot **vars;
} OperandStack;
```



当然，我们还得提供一整套操作本地变量表和操作数栈的函数。

> frame.h

```c
void *getThis(struct LocalVars *vars);
void setRef(struct LocalVars *vars, uint32_t index, void *ref);
void *getRef(struct LocalVars *vars, uint32_t index);
void setVar(struct LocalVars *vars, uint32_t index, union Slot *var);
union Slot *getVar(struct LocalVars *vars, uint32_t index);
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
void pushVar(struct OperandStack *stack, union Slot *var);
union Slot *popVar(struct OperandStack *stack);
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

在HotSpot实现中，其实常量池的解析是一步到位的，在`ClassFileParser:parseClassFile()`函数中有一行

```c
  constantPoolHandle cp = parse_constant_pool(CHECK_(nullHandle));
```

但是我觉得张秀宏老师的`静态常量吃 -> 运行时常量池`这种方式更易编写代码也更容易理解，也更直接符合虚拟机规范中的语义。否则的话我想就跟看《揭秘Java虚拟机》这本书类似，讲的非常细，正如书中所说“前面经历千辛万苦，终于完成了常量池oop的基本构建工作”，如此一来，估计读者和我都坚持不了多久就疯了D##。



我们使用`RCP`结构体来表示运行时常量池

```c
typedef struct RCPInfo
{
    uint8_t type;
    void *data;
} RCPInfo;

// https://docs.oracle.com/javase/specs/jvms/se11/html/jvms-2.html#jvms-2.5.5
// 必须在运行时才解析的动态符号信息
typedef struct RCP
{
    u_int32_t size;
    RCPInfo **info;
} RCP;
```

运行时常量池存放了两类信息，一是字面量信息，数字、字符串；二是符号引用信息，类符号引用、字段符号引用、方法符号引用。

字面量信息我们直接使用`void *`就可以表达了，对于各种符号信息我们则使用几个结构体表示

```c
// https://docs.oracle.com/javase/specs/jvms/se11/html/jvms-5.html
// 在类加载时进行解析
typedef struct ClassRef
{
    char *classname;
} SymbolRef;

typedef struct MemberRef
{
    char *classname;
    char *name;
    char *descriptor;
} MemberRef;
```



可以看到，其实这些结构体直接用`ClassFile`中的一些机构体也可以表示，但单独提出语义更加清晰。

运行时常量提供两个主要方法，一个用于构建运行时常量池，另一个用于各指令获取常量池中的信息。

```c
struct RCP *buildConstantPool(struct IKlass *clazz);
struct RCPInfo *getRCPInfo(struct RCP *rcp);
```



## 类klass

在HotSpot的实现中有一套oop-klass模型，是描述Java类和内存分配的关键，通过oop、klass、handle（非常讨厌的各种handle）来描述一种类型。我们暂时不弄成这么复杂，但是为了后续能向其靠拢，我们也将我们用于表示Java Class的结构体命名为`IKlass`，对应klass家族中的`instanceKlass`类（C++中的类）。



`IKlass`结构体如下

```c
typedef struct IKlass
{
    uint16_t accessFlags;
    char *name;
    char *superClassName;
    Interfaces *interfaces;
    RCP *constantPool;
    Fields *fields;
    Methods *methods;
    struct ClassLoader *loader;
    struct IKlass *superClass;
    uint32_t instanceSlotCount;
    uint32_t staticSlotCount;
} IKlass;
```



抛开`ClassLoader`先不谈，最重要的属性也就是`fields`和`methods`，分别存储了该类的静态属性、成员属性，以及该类的静态方法和成员方法。



我们先看下`Field`

```c
typedef struct Field
{
    uint16_t accessFlags;
    char *name;
    char *descriptor;
    // 属性的初始化值（程序员赋的值）
    uint32_t rcpInfoIndex;
    // 属性值存储的位置，后续要设置属性的值就放到该位置即可
    uint32_t slotIndex;
} Field;

typedef struct Fields
{
    uint32_t size;
    struct Field **fields;
} Fields;
```

基本上符合一个Java程序员对于一个属性的想象，属性的值在JVM是存储在类中的一个数组里，偏移量已经定好，所以在Java中可以通过native方法设置指定偏移量位置的值来修改属性值。



再来看下`Method`

```c
typedef struct Method
{
    uint16_t accessFlags;
    char *name;
    char *descriptor;
    // 我们实现时就不对参数个数和栈深校验了
    uint32_t maxLocals;
    uint32_t maxStack;
    uint32_t argCount;
    char *code;
} Method;

typedef struct Methods
{
    uint32_t size;
    struct Method **methods;
} Methods;
```

在这里，我们已经将属性表中的代码直接取出来放在`Method`结构体中了，为了后续操作更加方便。



Class中有非常多的方法，我们先列举一部分静态类型的判断

```c
/* acessflags */
int8_t isPublic(IKlass *clazz);
int8_t isFinal(IKlass *clazz);
int8_t isSuper(IKlass *clazz);
int8_t isInterface(IKlass *clazz);
int8_t isProtected(IKlass *clazz);
int8_t isAbstract(IKlass *clazz);
int8_t isStatic(IKlass *clazz);
int8_t isSynthetic(IKlass *clazz);
int8_t isAnnotation(IKlass *clazz);
int8_t isEnum(IKlass *clazz);
```

这是对类的ACESS_FLAGS的判断，当然还有对属性和方法的，就不一一举例了。



还有一些类的静态操作

```c
char *getName(IKlass *clazz);
char *getField(IKlass *clazz, char *name, char *descriptor, uint8_t static);
char *getMethod(IKlass *clazz, char *name, char *descriptor, uint8_t static);
```

顾名思义，获取类中的属性和方法。





至此，我们构建了一个简单的运行时数据区，虽然不复杂，但指令的实现和后续的改进完善都是以此为基础的，希望屏幕前的你有所收获。


