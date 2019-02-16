> 笔者博客地址：https://charpty.com
> 本文代码委托在：https://github.com/charpty/cjvm

编程时用到的很多API都必须和操作系统扯上关系，比如内存操作、网络编程都是需要借助操作系统本身提供的系统调用的，主流JVM都提供了让Java方法能够直接调用本地方法的能力，这种能力称为JNI，现阶段笔者的任务是在自己的JVM中添加这种能力。

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



首先最重要的是，标准规定了`JNINativeInterface_`，简化的说，它是一个指向一堆标准JNI函数的指针，通过这些函数，本地代码的实现者才能友好的和`JVM`进行交互，这个指针在具体实现中并封装或重定义为`JNIEnv`（在C++实现中使用的是封装版）。

每个Java线程有一个独立的`JNIEnv`，所有JNI实现方法的第一个参数就是`JNIEnv`，其中提供了234个函数来控制VM和Java对象，可以访问Java方法、Java属性、异常信息等。这些封装后的方法，也使得本地代码实现者也无需关心`JVM`如何做到这些复杂的交互操作。



其次需要了解的是





## HotSpot启动与JNI实现



LinkResolver::resolve_method   

Method, _i2i_entry

Method::link_method -> set_native_function








