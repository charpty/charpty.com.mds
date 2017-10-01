> 笔者博客地址：https://charpty.com

JVM(本系列统指sun的HotSpot虚拟机1.7版本实现)加载类一共分为5步，分别是：1、加载 2、验证 3、准备 4、解析 5、初始化，简要的流程图如下
![类加载简述](/images/jvm/classloading/load/classloading_steps_simple_description.png)

“加载”是“类加载”的第一个步骤，“类加载”的总指挥是```ClassLoader```，加载步骤大多都是异步的，各个阶段都有交叉进行甚至仅在需要时才进行（如晚解析），不像图中这样规矩。但按照JVM规范中指明**"A class or interface is completely loaded before it is linked"**，所以虽然HotSpot实现有特性，但“加载”可以认为是同步的，且只有当“加载”步骤完成后才能进行后续动作。

“加载”，顾名思义就是要将*.class的文件读到内存中，读成虚拟机可以认识的结构体，做的事情比较简单，我们可以把它细化成3件事：

 1. 读取此类的二进制字节流
 2. 将字节流转换为运行时的数据结构
 3. 生成java.lang.Class对象

“加载”的动作主要在**classLoader.cpp(指包含类的子类)**和**classFileParser.cpp**文件中实现，在笔者看的1.7版本中，后者有4689行代码，算是篇幅比较大的类（C++）了。

### 一、读取此类的二进制字节流
 拿本地文件系统来说，读取一个类的二进制流无非就是读本地的一个*.class文件，但是JVM规范并没有限定一定要从本地读取类的二进制字节流，这给开发人员提供了很大的想象空间，目前很多的类加载技术都是依托于这点，举几个例子：

 1. 大家熟悉的JSP应用，JSP文件会自动生成Class类
 2. 从jar包（war包）中读取*.class文件，这让大家可以方便的把自己的项目打包并部署到WEB容器中
 3. Cglib或者其它asm操作库，它们可以动态的生成类的二进制字节流，这就使得动态代理技术得以实现


读取的方式不受限制，这让加载方式有无限扩展的可能，在各种云时代的今天，甚至可以全部通过网络来加载类的二进制字节流（Java的Applet应用就是从网络中加载）。

读取后最终会以```ClassFileStream```类来表示，读取方式是多种多样的，所以HotSpot实现时将读取的方法写成了纯虚函数以实现多态：
```
// classLoader.hpp[Class=ClassPathEntry]  66行
// Attempt to locate file_name through this class path entry.
// Returns a class file parsing stream if successfull.
virtual ClassFileStream* open_stream(const char* name) = 0;
```
如果读取成功则会返回```ClassFileStream```对象的指针，提供给后续步骤使用。


### 二、将字节流转换为运行时的数据结构
在获取到正确的```ClassFileStream```对象指针后，则会创建一个```ClassFileParser```实例并调用其```parseClassFile()```方法来解析```ClassFileStream```结构。其实第二、三步都在这个方法中，将其区分开来主要是为了方便理解两个步骤各自的功能。
现在所做的步骤更多的是读取值并进行简单的校验，包括JVM规范所说的**“Format Checking”**（校验*.class文件内容是否符合JVM关于class文件结构的定义），需要说明的是，这里一小部分的校验内容其实是“验证”阶段的工作（代码和“加载”混在一起），后续还会提到，需要获取或校验的值大致有：

 1. 读取魔数并校验
 魔数中有代表*.class文件编译时的版本信息，例如被JDK1.8编译过来的class文件不能被JDK1.7的虚拟机加载，逻辑很好理解，这是一个强校验，没有商量的余地，高版本的*.class文件不能被低版本的虚拟机加载，即使恰好这个class文件没有使用高版本特性也不行
 2. 获取常量池引用
 常量池信息主要包含两类，字面量和符号引用，字面量主要指文本字符串，声明为final的常量值等，符号引用主要包含父类或实现接口，字段和方法的名称和描述符
 3. 读取访问标志表示并校验
标志用于识别类或者接口层次的访问信息，例如：该Class是类还是接口，是否被public修饰，是否是抽象类
 4. 获取this类全限定名
 读取当前类索引，并在常量池中找到当前类的全限定名，前面在读取常量池信息时，解析器获得了一个常量池句柄，可以通过它和自身的```index```获取本类的在常量池中存储的全限定名
![获取常量池句柄](/images/jvm/classloading/load/get_current_class_index.png)
后面会对这个名称做一些基本的校验，正如图中所见，如果没问题则赋值给本地解析器变量以便后续处理
 5. 获取父类以及接口信息
 如果有继承父类或者实现接口，那么父类或接口需要被先加载，如果已经加载则获取它们的句柄记录到本类中，过程中会做一些简单的名称之类的校验
 6. 读取字段信息和方法信息
 读取字段信息存储到typeArrayHandle中，读取实例方法信息并存储到objArrayHandle中，这两部分信息在后续步骤都会填入instanceKlass对象中，成为类信息的一部分。
![读取字段和方法信息](/images/jvm/classloading/load/parse_field_and_method.png)
 字段和方法信息读取完成之后，还会进行排序以便后续对Class大小进行评估，需要注意的是当一个Java中的Class在被加载之后，它的大小就是固定的了。

### 三、生成java.lang.Class对象
前面已经读取到了*.class文件中的所有信息，接下来要做的就是进行一些计算并创建好Class对象以供其它阶段使用

 1. 计算Java vtable和itable大小
 根据已解析的父类、方法、接口等信息计算得到Java vtable（虚拟函数表）和itable（接口函数表）大小，这是后续创建klassOop时需要指定的参数
 当然还包括一些其它信息的计算，例如属性偏移量等，这里不一一列举
 2. 创建instanceKlass对象
```
     // We can now create the basic klassOop for this klass
    klassOop ik = oopFactory::new_instanceKlass(name, vtable_size, itable_size,XXX....., CHECK_(nullHandle));
    // 前面做的诸多工作都是为了创建这个对象
    instanceKlassHandle this_klass (THREAD, ik);
```
前面做了许多的工作，读取并解析了类的各种信息，终于到了创建一个用来表示这些类信息的结构的时候，```instanceKlass```负责存储*.class文件对应的所有类信息，创建完成之后，还会进行一些基本的校验，这些校验都是和语言特性相关的，所以不能像校验字符串级别的特性一样放在前面处理，校验的项大致如：check_super_class_access（父类可否继承）、check_final_method_override（是否重写final方法）等
 3. 创建Java镜像类并初始化静态域
```
// Allocate mirror and initialize static fields
java_lang_Class::create_mirror(this_klass,CHECK_(nullHandle));
// 通知虚拟机类已加载完成
ClassLoadingService::notify_class_loaded(instanceKlass::cast(this_klass()), false);
```
通过克隆```instanceKlass```创建一个Java所见的```java.lang.Class```对象并初始化静态变量，这个处理方式和JVM对于对象和类的表示方法有关系，后续会讲到。最后还需要通知虚拟机，更新```PerfData```计数器，“加载”阶段完成之后，虚拟机就在方法区为该类建立了类元数据。

## 小结
“加载”是“类加载”后续步骤的基石，JVM的规范体现了跨平台、跨语言的宏观理念，使用JVM上语言的同学可以不追究细节，但都应该了解“加载”的三小步。对Java程序员来说，这对写出可以在各个容器下稳定运行的代码是很重要的，对于解决平常遇到的“本地可运行，发布后不稳定”、“Tomcat下能运行Weblogic不能”、“log4j优先加载哪一个配置文件”等等问题有一定的帮助。
对于“加载”，HotSpot的实现代码非常庞大，所幸源码中有良好的注释，这提醒了我良好注释的重要性。


Oracle官方的文档对我的帮助很大
>参考： https://docs.oracle.com/javase/specs/jvms/se7/html/jvms-5.html
