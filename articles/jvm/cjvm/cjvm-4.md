> 笔者博客地址：https://charpty.com
> 本文代码委托在：https://github.com/charpty/cjvm

编程时用到的很多API都必须和操作系统扯上关系，比如内存操作、网络编程都是需要借助操作系统本身提供的系统调用的，JVM提供了让Java方法能够直接调用本地方法的能力，这种能力称为JNI。

有以下几种场景：

通过Java正向调用本地代码

- 要实现标准Java不支持的“系统层级”功能，如Java调用OpenCV进行图像识别

- 想在Java代码中调用已有的C++项目代码

- 想使用低级的编程语言来实现部分关键的代码，供Java代码调用，如Java调用加密狗或硬件解密

通过本地调用操作Java

- 增删改查Java对象

- 调用Java方法

- 捕捉或抛出异常

- 获取class信息或者装载class

- 运行时状态检查

JNI只提供了一个框架和一些基本的函数，JDK则提供了大量的JNI实现，这些JNI实现这是JDK所有代码的基础。JNI是对本地方法的统一封装，Java调用者只管调用Java方法，而无需关心不同操作系统上的本地实现，也就是Java代码只管写一次，而JVM可以在不同操作系统上实现不同类型操作，我们也只管用JDK中的许多标准方法即可。



Native code accesses Java VM features by calling JNI functions. JNI functions are available through an*interface pointer*. An interface pointer is a pointer to a pointer. This pointer points to an array of pointers, each of which points to an interface function. Every interface function is at a predefined offset inside the array. The following figure,[Interface Pointer](https://docs.oracle.com/javase/9/docs/specs/jni/design.html#interface-pointer), illustrates the organization of an interface pointer.







![Interface pointer](https://docs.oracle.com/javase/9/docs/specs/jni/images/interface-pointer.gif)

Interface pointer

[Description of Figure Interface Pointer](https://docs.oracle.com/javase/9/docs/specs/jni/interface-pointer.html)

The JNI interface is organized like a C++ virtual function table or a COM interface. The advantage to using an interface table, rather than hard-wired function entries, is that the JNI name space becomes separate from the native code. A VM can easily provide multiple versions of JNI function tables. For example, the VM may support two JNI function tables:

- one performs thorough illegal argument checks, and is suitable for debugging;
- the other performs the minimal amount of checking required by the JNI specification, and is therefore more efficient.

The JNI interface pointer is only valid in the current thread. A native method, therefore, must not pass the interface pointer from one thread to another. A VM implementing the JNI may allocate and store thread-local data in the area pointed to by the JNI interface pointer.

Native methods receive the JNI interface pointer as an argument. The VM is guaranteed to pass the same interface pointer to a native method when it makes multiple calls to the native method from the same Java thread. However, a native method can be called from different Java threads, and therefore may receive different JNI interface pointers.



## JNI实现概览

Since the Java VM is multithreaded, native libraries should also be compiled and linked with multithread aware native compilers. For example, the`-mt`flag should be used for C++ code compiled with the Sun Studio compiler. For code complied with the GNU gcc compiler, the flags`-D_REENTRANT`or`-D_POSIX_C_SOURCE`should be used. For more information please refer to the native compiler documentation.

Native methods are loaded with the`System.loadLibrary`method. In the following example, the class initialization method loads a platform-specific native library in which the native method`f`is defined:

```
package pkg;

class Cls {
    native double f(int i, String s);
    static {
        System.loadLibrary("pkg_Cls");
    }
}
```

The argument to`System.loadLibrary`is a library name chosen arbitrarily by the programmer. The system follows a standard, but platform-specific, approach to convert the library name to a native library name. For example, a Solaris system converts the name`pkg_Cls`to`libpkg_Cls.so`, while a Win32 system converts the same`pkg_Cls`name to`pkg_Cls.dll`.

The programmer may use a single library to store all the native methods needed by any number of classes, as long as these classes are to be loaded with the same class loader. The VM internally maintains a list of loaded native libraries for each class loader. Vendors should choose native library names that minimize the chance of name clashes.

Support for both dynamically and statically linked libraries, and their respective lifecycle management*"load"*and*"unload"*function hooks are detailed in the[Invocation API section on*Library and Version Management*](https://docs.oracle.com/javase/9/docs/specs/jni/invocation.html#library-and-version-management).
