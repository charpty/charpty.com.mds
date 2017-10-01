笔者博客地址：https://charpty.com


在前两篇文章中，我们讲到JVM已经把class文件加载为运行时数据结构并做了严格的校验，此时的```instanceKlass```需要进行进一步的数据上的处理才能交付使用，准备阶段就是其中相对简单的一步，这一步做的工作并不多，引用Oracle官方文档的话来说:

> Preparation involves creating the static fields for a class or interface and initializing such fields to their default values (§2.3, §2.4). This does not require the execution of any Java Virtual Machine code; explicit initializers for static fields are executed as part of initialization (§5.5), not preparation.

“准备"阶段是为class或者interface中的静态变量赋初始值，这其中的“赋值”并不是大家在Java代码为各个静态变量的赋值操作法，原文也明确了，准备阶段并不会执行任何大家写的Java代码，执行Java字节码的动作在后面的“初始化”阶段执行。举个例子：
``` java
public class StaticFiledTest {
// 在准备阶段，变量var的值会被赋为0而不是2017
public static int var = 2017;
}
```

所以，"准备"阶段赋的初始值仅仅和这个静态变量的类型相关，和在Java代码中对这个变量赋的值无关，Oracle对类型不同的各种变量应该分别赋予何种初始值做出了规定。HotSpot的实现流程如下：
![初始化基本流程](/images/jvm/classloading/prepare/hotspot_prepare_flow.png)

### 发生时间
“准备”动作可以发生在```instanceKlass```被创建后的任何时间，但是必须在“初始化”动作之前，前面我们也说到HotSpot在代码实现有穿插，“准备”阶段的代码一小部分就在“加载”阶段的```classFileParser.cpp```中（入口与准备工作），主要赋值部分则在```instanceKlass.cpp```中，在此处，类中的静态变量初始化发生在类刚刚被加载后：
![准备阶段触发时机](/images/jvm/classloading/prepare/time_to_trigger_class_prepare.png)
``` c
// javaClass.cpp create_mirror() 495行
// 第一个参数是函数指针，是赋值的关键函数
instanceKlass::cast(k())->do_local_static_fields(&initialize_static_field, CHECK_NULL);
```

### 基本类型赋值
刚开始工作经常被问的一道面试题，Java中一共有哪些基本类型呀，答不上来可就麻烦了。截止Java7，Java中一共有8种基本类型，分别是byte、short、int、long、char、float、double、boolean，但在JVM中一共有9种基本类型，多出来的一种是returnAddress类型。

1. ```byte``` 用8位补码表示，初始化为0
2. ```short``` 用16位补码表示，初始化为0
3. ```int``` 用32位补码表示，初始化为0
4. ```long``` 用64位补码表示，初始化为0L
5. ```char``` 用16位补码表示，初始化为"\u0000"，使用UTF-16编码
6. ```float``` 初始化为正0
7. ```double ``` 初始化为正0
8. ```boolean``` 初始化为0
9. ```returnAddress``` 初始化为字节码指令的地址,用于配合异常处理特殊指令

在```classFileParser.cpp```中（parse_fields()）有一段对各个类型赋值的预处理：
![根据不同类型赋值](/images/jvm/classloading/prepare/assign_value_by_field_type.png)

### 引用类型赋值
有三种引用类型：类类型、数组类型和接口类型，他们都将被赋值为null，null可以被转换为任意类型

### 特殊赋值场景
前面说到，JVM在“准备”阶段对静态变量的赋值和Java代码无关，大多数情况下确实如此，但也存在特殊情况。
赋值时会扫描类的字段属性表，如果此时发现有```ConstantValue```属性，那么在“准备”阶段就会将静态属性的值赋为```ConstantValue```指定的值。如何生成```ConstantValue```属性呢？在Java语言中，只要将静态变量声明为final即可。
```
public class StaticFiledTest {
// 声明为final后var的值在准备阶段则会被赋为2017
public static final int var = 2017;
}
```
其实这个特殊前面的讲解中也已提到，解析*.class文件中的属性表时，会把各个属性的```constantvalue_index```取出并存入```instanceKlass```中，后续赋值时也是从此处来取。
```
// 解析Field的attribute_info属性，其中包括ConstantValue
parse_field_attributes(cp, attributes_count, is_static, signature_index, &constantvalue_index, &is_synthetic,
&generic_signature_index .......);

fields->short_at_put(index++, access_flags.as_short());
fields->short_at_put(index++, name_index);
fields->short_at_put(index++, signature_index);
// 将constantvalue_index存入结构体中，用于后续给静态变量赋值
// 放入数组的下标为3
fields->short_at_put(index++, constantvalue_index);
```
何种条件下才会触发在“准备”阶段就赋值呢？HotSpot的```javaClasses.cpp```中给出了答案：
```
static void initialize_static_field(fieldDescriptor* fd, TRAPS) {
// 创建句柄以及是否静态校验
.......
// 如果存在有初始值即constantvalue_index是有效的则赋值
// constantvalue_index存放位置为属性数组的第4个值（index=3）
if (fd->has_initial_value()) {
BasicType t = fd->field_type();
switch (t) {
// 根据不同类型赋值
......
```

> 参考文档：
> https://docs.oracle.com/javase/specs/jvms/se7/html/jvms-5.html#jvms-5.4.2