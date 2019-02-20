> 笔者博客地址：https://charpty.com
> 本文代码委托在：https://github.com/charpty/cjvm

编程时用到的很多API都必须和操作系统扯上关系，比如内存操作、网络编程都是需要借助操作系统本身提供的系统调用，主流JVM都提供了让Java方法能够直接调用本地方法的能力，称为JNI，现阶段笔者的任务是在自己的JVM中添加这种能力。

参照Oracle的HotSpot，有以下几种场景：

通过Java正向调用本地代码

- 要实现标准Java不支持的“系统层级”功能，如Java调用OpenCV进行图像识别

- 想在Java代码中调用已有的C++项目代码

- 想使用低级的编程语言来实现部分关键的代码，供Java代码调用，如Java调用加密狗或硬件解密

通过本地代码操作Java

- 增删改查Java对象

- 调用Java方法

- 捕捉或抛出异常

- 获取class信息或者装载class

- 运行时状态检查

笔者的目标是能“基本正常”的加载标准jdk(OpenJDK/jdk11/java.base)，那么实现JNI能力则是必然选择。

JNI只提供了一个框架和一些基本的函数，jdk中则提供了大量的JNI实现，这些JNI实现则是JDK所有代码的基础。JNI是对本地方法的统一封装，Java调用者只管调用Java方法，而无需关心不同操作系统上的本地实现，Java代码只管写一次，而JVM可以在不同操作系统上实现不同类型操作，我们也只管调用JDK中的许多标准方法即可。

## JNI标准概览

笔者参考的是[Oracle SE10 JNI标准](https://docs.oracle.com/javase/10/docs/specs/jni/index.html)，笔者简单对比了下，和前面一个版本（9）差别不大。

首先最重要的是，标准规定了`JNINativeInterface_`，简化的说，它是一个指向一堆标准JNI函数指针的指针，通过这些函数，本地代码的实现者才能友好的和`JVM`进行交互，这个指针在具体实现中被封装或重定义为`JNIEnv`（在C++实现中使用的是封装版）。

每个Java线程有一个独立的`JNIEnv`，所有JNI实现方法的第一个参数就是`JNIEnv`，其中提供了234个函数来控制VM和Java对象，可以访问Java方法、Java属性、异常信息等，还可以注册本地方法、操作java.lang.String、操作Java数组、调用NIO相关函数等等。这些封装后的方法，也使得本地代码实现者也无需关心`JVM`如何做到这些复杂的交互操作。

其次需要了解的是JNI规范中指明的通过Java方法签名来寻找本地实现代码的大致方式，首先是通过`System.loadLibrary()`将动态库连接到`JVM`中，然后则是通过名称`Java_类的全限定名(.改为_)`到动态库中查找函数符号。由于涉及到安全、性能、多线程等因素，native方法本地实现与Java方法签名关联的过程是比较复杂的，在笔者实现时，就简单的按照预先加载的方式来硬编码处理了，实际上HotSpot也会提前加载java.lang目录下的部分核心代码以便提前加载核心的native动态库（如java_lang_String、java_lang_System、java_lang_Thread等）。

最后需要了解的是JNI中数据类型，JNI通过C/C++定义了一套数据类型来表示Java语言中的类型。就基本类型而言， 只有Java中的char本质上对应的是C/C++中的无符号short（为了做到JVM层级别的Unicode兼容），其它byte、int、long、double等都是一一对应的，只是名称前加了一个j而已，比如Java中的int类型，对应jni中的jint。

引用类型在C和C++两种不同实现中表示方式不同，如果native方法的实现函数采用C++来编写，那么引用类型则有`jclass`、`jstring`、`j*array`3种类型，顾名思义就知道表示什么，本质上它们都是C++的类。而在C中只有`jobject`，虽然也有`jclass`、`jstring`、`j*array `这几种类型，但它们实际上只是`jobject`结构体的别名。

当然JNI规范中不止这些内容，但笔者认为知道这些就足以实现一个简单的JNI体系。

## HotSpot启动与JNI实现



#### 执行HelloWorld程序

HotSpot实现了一个复杂的JNI系统，有几种场景会用到`JVM`的JNI能力，首先是最简单的HelloWorld程序。

```java
public class HelloWorld {

    public static void main(String[] args) {
        System.out.println("Hello World");
    }
}
```

这个程序会在控制台输出Hello World字样，很明显，在屏幕上显示字符，这是操作系统才能干的事情。

这个System里的out变量是屏幕输出的关键，它是在`initPhase1()`（原名称为`initializeSystemClass()`）被初始化的。而函数`initPhase1()`则是在`JVM`完成线程加载后调用的，这个简单的过程就涉及到多次的JNI使用，那我们来看下这个过程中，关于`System.out`的调用顺序，顺便也引出来`JVM`的大致启动顺序。

```cpp
launcher -> JavaMain -> InitializeJVM
    -> JNI_CreateJavaVM()  调用JNI的Invocation API来创建VM
    -> Threads::create_vm()  模块配置并启动VM各类线程，特别是main_thread
    -> Threads::initialize_java_lang_classes()  顾名思义，加载java.lang目录下的关键类，有很多
    -- initialize_class(vmSymbols::java_lang_System())  调用<clinit>初始化System类的静态变量和代码块
                               这里会使用C++通过JNI调用Java代码，最终通过一个通用函数JavaCalls::call()
                               这里已经不是第一次调用Java函数了，第一次调用是初始化java.lang.Object
                               Object是所有类的父类，加载任何class前必须先加载它

    -> System.registerNatives()  java.lang.System静态块中再调用native方法，即使用Java通过JNI调用C++
                                 我们仅关心System.out的情况下，上述两个地方是首次JNI登上舞台的地方
                                 调用一个方法也就是前面文章说过的，将其翻译为invoke_*指令并执行该指令即可

    -> BytecodeInterpreter::run()  到这里会执行_invokestatic指令，执行该指令也就是获取具体方法并压入栈中
                                   具体如何解析则交由InterpreterRuntime::resolve_from_cache()
                                   
    -> InterpreterRuntime::resolve_invoke()  进行实际的转换操作，拿操作数index到常量池换取实际的方法信息
                             这里已经知道方法名字("registerNatives")、方法签名、方法所在class等信息了

    -> LinkResolver::resolve_method()  拿方法元信息换取具体的方法对象"methodHandle"
                                       这就是真正的Java方法表示了，后续就是要执行这个方法
                                                                           
    -> InterpreterRuntime::prepare_native_call()  尝试获取真实的本地函数首地址，没缓存就要去查找 
                     在解析classfile时，对native方法就进行了标记，所以registerNatives()是走native路线的                                         

    -> NativeLookup::lookup()  查找"java.lang.System.registerNatives()V"方法
                               实际上第一个查找的本地方法是"java.lang.Object.registerNatives()V"

    -> NativeLookup::lookup_base()  如果方法是native却没有设置native函数地址，则需要进行查找
    -> NativeLookup::lookup_entry()  尝试组装各种函数名称（带JNI前缀、带OS文件名后缀等）来查找本地代码
    -> NativeLookup::lookup_style()  查找本地代码的关键逻辑！一共有两种查找方式
          这里"System.registerNatives()"是直接属于JDK默认自带库"os::native_java_library()"其中的函数
          这些函数的特性就是它不是被任何Java的ClassLoader加载的，也就是不是被"System.loadLibrary()"加载的
          这些库都是JDK中的核心，加载甚至在众多Java代码之前，所以必须使用本地直接装载
          标准的DLL也就是"libjava"，在OSX系统上也就是在"$JAVA_HOME/jre/lib/libjava.dylib"这个文件中
          所以JVM直接加载的类即非Java ClassLoader加载的类，请求native方法的话，查找过程是比较容易的
          直接在预定好的库里dlsym()查找函数名称即可          

    -> System.c:Java_java_lang_System_registerNatives()  真正调用到JDK System的native方法实现函数
                                       这个函数基本上等于没做啥事，它也不是我们输出"Hello World"的关键

    -> thread.cpp:call_initPhase1()  阶段1：专门再"初始化"下"java.lang.System"类
            所以"System"类确实至关重要，这次主要是调用其initPhase1()函数，初始化一些关键的系统参数和变量
            最终通过通用函数JavaCalls::call_static()来调用到java.lang.System.initPhase1()

    -> System.initPhase1()  之前的initializeSystemClass()函数，进行了一阶段的许多初始化工作
         我们主要关心何时对System.out进行了设置，其实关键也就是在JVM初始化完输出流后通知Java也完成输出流初始化
         关键语句：setOut0(newPrintStream(fdOut, props.getProperty("sun.stdout.encoding")));                           
         其中最关键的是fdOut，它是文件输出流，自带有一个默认的FileDescriptor文件描述符
         FileDescriptor绑定了Windows的文件句柄或者Unix的标准输出流

    -> new FileDescriptor(1)  1代表标准输出流
    -> FileDescriptor.getAppend(1) 调用Java_java_io_FileDescriptor_getAppend()，获取文件输出流的状态
                                   在Windows下还需要调用getHandle(1)来初始化文件句柄

    -> out.println("Hello World")  多层封装，最终调用FileOutputStream的write方法，本质上也就是文件流输出
    -> FileOutputStream.writeBytes()  调用native方法
    -> FileDescriptor_md.c:Java_java_io_FileOutputStream_writeBytes()  natvie方法的本地实现
    -> io_util.c:writeBytes() -> io_util.c:handleWrite() -> write()系统调用
```

上述我们看到为了能做到输出Hello World，和其相关的步骤还是比较多的，这个例子主要看的是几个点。

##### Java方法调用一个native方法，如何实现？

```java
Java调用native函数a (被javac翻译为invokestatic #a)
     -- JVM解析classfile时将方法a标记为native
     -> JVM执行invokestatic指令时首先根据index来获取到方法信息
     -> 执行方法时，如果是native则需要查找native函数入口地址(不是native就直接执行属性表中的代码)
     -> 如果方法是被非Java ClassLoader加载的类调用的，则默认是系统native方法，直接到系统动态库中查找
     -> 执行native
```



##### JVM启动时需要调用Java代码做哪些事情

- 要提前初始化`java.lang`目录下的重要类，包括本例用到`java.lang.System`类

- 本例中还需要调用`System.initPhase1`方法来初始化`System.out`变量

- 还有最重要的，它需要调用Java代码的main函数



JVM的启动过程较为复杂，`HelloWorld`的例子围绕`System`类和`System.out`变量对Java调用C++代码进行了讲解，也稍微提到了C++调用Java代码。



#### 调用自定义的本地库

经过第一个例子，我们明白了JDK自带的这类动态库加载链接的方式，接下来看一下我们自行编写的动态库加载方式

```java
public class MyNumberDLLTest {

    public static void main(String[] args) {
        System.loadLibrary("number");
        System.out.println(getNumber());
    }

    // 本地代码实现就是返回个1而已
    public static native int getNumber();
}
```

代码很简单，也可以在静态块`loadLibrary()`，但在代码流程里装载更能直观反应问题，按照这个过程，我们来看下`JVM`又是如何做到动态加载这个`number`库的。

将写好的C代码编译成动态库之后，输出一个名为`libnumber.dylib`的共享库，随后我们在Java代码中加载这个共享库并执行其中的`getNumber()`方法。

```java
launcher -> JavaMain -> InitializeJVM
 -> JNI_CreateJavaVM() 
 -> Threads::create_vm() 
 -> Threads::initialize_java_lang_classes() 
 -> initialize_class(vmSymbols::java_lang_System())  也是要加载关键的System类，过程中上面讲过的就省略了
 -> 

```





## JNI实现概览

## JNI实现
