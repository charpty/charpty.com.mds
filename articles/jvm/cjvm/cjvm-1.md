> 笔者博客地址：https://charpty.com       
> 本文代码（章节名即分支名）委托在：https://github.com/charpty/cjvm

许多同学看了不少关于JVM和GC相关的书，很多概念都熟悉了，但本着经历过才能身入其境的原则，我觉得必须要自己写一写，体会下前人的思想和辛苦，才能对所学JVM和GC相关知识进行实践性总结。

业余时间的乐趣型项目，使用C语言实现的一个可高效运行的Java虚拟机，包括解释执行实现和CS|IP方式实现。使用C99编写，仅在类unix系统上运行，包含类加载子系统、执行子系统（常用字节码指令实现）、运行时数据区、GC、JIT等组件的实现。最终的目标是能够使用该虚拟机运行笔者网站的Java代码。

## 01-搜索class文件
这基本上就是一个简单的文件搜索并读取的操作，代码也比较好理解，只是有几个注意事项：

* 要遵循规范中ClassLoader的**双亲委托模型**，总是尝试在父ClassLoader中找寻文件
* 要加载的不仅仅是直接的class文件，还有压缩在jar包、war包中的class文件


### 双亲委托加载方式
在虚拟机中有3种类加载器，分别是：`BootstrpLoader`、`ExtClassLoader`、`AppClassLoader`。  

对应的我们称被这3个类加载器加载的class文件路径为：`bootStrapPath`、`extPath`、`userPath `，其中AppClassLoader也称为SystemClassLoader，它用于加载系统（用户的项目）里的class文件，所以称这些class的路径为userPath更加形象。

> classpath.c

``` c
typedef struct ClassPath
{
    char *bootStrapPath;
    char *extPath;
    char *userPath;
    char *(*readClass)(ClassPath *classPath, char *classname);
} ClassPath;

SClass *readClass(ClassPath *classPath, char *classname)
{
    SClass *r;
    if ((r = readBootStrap(classPath, classname)) != NULL)
        return r;
    else if ((r = readExt(classPath, classname)) != NULL)
        return r;
    else
        return readUser(classPath, classname);
}
```

### 从jar包中加载

jar包本质上就是zip压缩包，所以我们使用[libzip](https://libzip.org/)来读取它。

> classpath.c

``` c
SClass *readClassInJar(char *jarPath, char *classname)
{
    int err;
    struct zip *z = zip_open(jarPath, 0, &err);
    // TODO I can't find err code >39 means in zip.h
    if (err != 0 && err < 39)
    {
        LOG_ERROR(__FILE__, __LINE__, "open jar file %s failed, error code is: %d", jarPath, err);
        return NULL;
    }

    const char *name = classname;
    struct zip_stat st;
    zip_stat_init(&st);
    zip_stat(z, name, 0, &st);
    if (st.size <= 0)
        return NULL;
    char *contents = malloc(st.size);
    struct zip_file *f = zip_fopen(z, name, 0);
    zip_fread(f, contents, st.size);
    zip_fclose(f);
    zip_close(z);

    struct SClass *r = (SClass *)malloc(sizeof(struct SClass));
    r->len = st.size;
    r->bytes = contents;
    r->name = classname;
    return r;
}
```

## 02-解析class文件的内容
这里也就是将class文件的里的字节内容，解析成语言可识别的数据结构，这里我们将其解析成称为`ClassFile`的结构体。`ClassFile`将单个字节码文件的内容解析成C语言的结构体，方便后续能够被`ClassLoader`加载为`Class`结构体。

仅看第一层内容，`ClassFile`并不复杂。

> classfile.c

``` c
// 属性命名和oracle虚拟机规范尽量保持一直(规范中属性名都使用下划线，但结构体我习惯用驼峰形式)
// https://docs.oracle.com/javase/specs/jvms/se7/html/jvms-4.html
ClassFile *readAsClassFile(ClassReader *r)
{
    ClassFile *rs = (ClassFile *)malloc(sizeof(struct ClassFile));
    // 读取版本信息
    rs->magic = readUint32(r);
    checkMagic(rs->magic);
    rs->minor_version = readUint16(r);
    rs->major_version = readUint16(r);
    checkClassVersion(rs->major_version, rs->minor_version);
    // 读取常量池，动长
    struct CP *csp = readConstantPool(r);
    rs->constant_pool = csp;
    // 访问标志，是一个位图标记，记录了类的访问级别，类是否为final，是否是注解类型等等
    rs->access_flags = readUint16(r);
    // 当前类名在常量池中的索引
    rs->this_class = readUint16(r);
    // 当前类父类名在常量池中的索引
    rs->super_class = readUint16(r);
    // 读取该类实现的所有的接口
    rs->interfaces = readUint16s(r, &(rs->interfaces_count));
    // 读取当前类的属性，包括静态属性
    rs->fields = readMembers(r, csp);
    // 读取当前类的方法信息，包括静态方法
    rs->methods = readMembers(r, csp);
    // 读取剩余的不包含在方法或者字段里的其它属性表信息
    rs->attributes = readAttributes(r, csp);
    return rs;
}
```

我们第一步要做的就是将class文件里的内容解析为这么一个不太复杂的结构体，仅有这么一个结构体还不够，为了统一表示对一个class文件的读取操作，我们使用一个叫`ClassReader`的结构体表示该操作。

> classreader.h

``` c
typedef struct ClassReader
{
    // 逐个字节读下去
    uint32_t position;
    uint32_t len;
    unsigned char *data;
} ClassReader;

// 提供了以下几种读取方式
static uint8_t readUint8(ClassReader *r);
static uint16_t readUint16(ClassReader *r);
static uint32_t readUint32(ClassReader *r);
static uint64_t readUint64(ClassReader *r);
static uint16_t *readUint16s(ClassReader *r, u_int16_t *size);
static char *readBytes(ClassReader *r, u_int32_t n);

```

可以看出，同时对应该结构体也准备了一系列读取方法，几个典型实现如下：

> classreader.h

``` c
static uint16_t readUint16(ClassReader *r)
{
    return (uint16_t)r->data[r->position++] << 8 | (uint16_t)r->data[r->position++];
}

static uint32_t readUint32(ClassReader *r)
{
    u_int8_t x1 = r->data[r->position++];
    u_int8_t x2 = r->data[r->position++];
    u_int8_t x3 = r->data[r->position++];
    u_int8_t x4 = r->data[r->position++];
    // *(uint32_t *)(r->data + r->position);
    return (uint32_t)x1 << 24 | (uint32_t)x2 << 16 | (uint32_t)x3 << 8 | (uint32_t)x4;
}

... 其它函数

static uint16_t *readUint16s(ClassReader *r, u_int16_t *size)
{
    uint16_t *rs = (uint16_t *)malloc((*size = readUint16(r)) * sizeof(u_int16_t));
    for (int i = 0; i < (*size); i++)
    {
        rs[i] = readUint16(r);
    }
    return rs;
}
```

有了这两个基础，剩下的事情就是按字节和规律一个个读取了。

> classfile.c

``` c
ClassFile *readAsClassFile(ClassReader *r)
{
    ClassFile *rs = (ClassFile *)malloc(sizeof(struct ClassFile));
    // 读取版本信息
    rs->magic = readUint32(r);
    checkMagic(rs->magic);
    rs->minor_version = readUint16(r);
    rs->major_version = readUint16(r);
    checkClassVersion(rs->major_version, rs->minor_version);
    // 读取常量池，动长
    struct CP *csp = readConstantPool(r);
    rs->constant_pool = csp;
    // 访问标志，是一个位图标记，记录了类的访问级别，类是否为final，是否是注解类型等等
    rs->access_flags = readUint16(r);
    // 当前类名在常量池中的索引
    rs->this_class = readUint16(r);
    // 当前类父类名在常量池中的索引
    rs->super_class = readUint16(r);
    // 读取该类实现的所有的接口
    rs->interfaces = readUint16s(r, &(rs->interfaces_count));
    // 读取当前类的属性，包括静态属性
    rs->fields = readMembers(r, csp);
    // 读取当前类的方法信息，包括静态方法
    rs->methods = readMembers(r, csp);
    // 读取剩余的不包含在方法或者字段里的其它属性表信息
    rs->attributes = readAttributes(r, csp);
    return rs;
}
```

接下来比较复杂的就是常量池、方法和属性签名、属性表这3个了。


### Class中的常量池
当前这个常量池和后面运行时数据区的常量池不同，它仅是当前这个class文件里使用的。

> constant_pool.h

``` c
typedef struct CPInfo
{ 
    uint8_t tag;
    // 常量池里存着各种各样类型的信息
    void *v1;
    void *v2;
} CPInfo;

// 用CP表示class里的常量池，运行期的常量池则用GCP来表示，更亲切
typedef struct CP
{
    uint32_t len;
    CpInfo **infos;
} CP;
```

接下来的任务是将class字节码的常量池部分解析成常量池对应结构体。

> constant_pool.h

``` c
static CP *readConstantPool(ClassReader *r)
{
    CP *rs = (CP *)malloc(sizeof(struct CP));
    int cpCount = readUint16(r);
    rs->len = cpCount;
    rs->infos = (CPInfo **)malloc(cpCount * sizeof(CPInfo *));

    // 常量池从下标1开始
    for (int i = 1; i < cpCount; i++)
    {
        rs->infos[i] = readConstantInfo(r, rs);
        // http://docs.oracle.com/javase/specs/jvms/se8/html/jvms-4.html#jvms-4.4.5
        // 这就是个数的特殊情况，读到long和double时，必须下一个元素是个空，以兼容老版本
        // 这是由于一个byte占常量池2个位置
        if (rs->infos[i]->tag == CONSTANT_Long || (rs->infos[i]->tag == CONSTANT_Double))
        {
            ++i;
            continue;
        }
    }
    return rs;
}
```

常量池里存着各种类型的信息，但最多的也就两个属性，所以这里就用两个`void*`指针表示了。常量信息使用`tag`表示属性类型，有14种类型。

> constant_pool.h

``` c
#define CONSTANT_Class 7
#define CONSTANT_Fieldref 9
#define CONSTANT_Methodref 10
#define CONSTANT_InterfaceMethodref 11
#define CONSTANT_String 8
#define CONSTANT_Integer 3
#define CONSTANT_Float 4
#define CONSTANT_Long 5
#define CONSTANT_Double 6
#define CONSTANT_NameAndType 12
#define CONSTANT_Utf8 1
#define CONSTANT_MethodHandle 15
#define CONSTANT_MethodType 16
#define CONSTANT_InvokeDynamic 18
```
根据不同的类型，我们需要不同的方式，列举一部分。

> constant_pool.h

``` c
static CPInfo *readConstantInfo(ClassReader *r, CP *cp)
{
    CPInfo *rs = (CPInfo *)malloc(sizeof(struct CPInfo));
    uint8_t tag = rs->tag = readUint8(r);
    if (tag == CONSTANT_Class)
    {
        // nameIndex
        // 存储class存储的位置索引
        rs->v1 = malloc(sizeof(uint16_t));
        *(uint16_t *)rs->v1 = readUint16(r);
    }
    else if (tag == CONSTANT_Fieldref)
    {
        // classIndex and nameAndTypeIndex
        rs->v1 = malloc(sizeof(uint16_t));
        rs->v2 = malloc(sizeof(uint16_t));
        *(uint16_t *)rs->v1 = readUint16(r);
        *(uint16_t *)rs->v2 = readUint16(r);
    }
    ... 各种类似解析
    else if (tag == CONSTANT_InvokeDynamic)
    {
        // bootstrapMethodAttrIndex and nameAndTypeIndex
        rs->v1 = malloc(sizeof(uint16_t));
        rs->v2 = malloc(sizeof(uint16_t));
        *(uint16_t *)rs->v1 = readUint16(r);
        *(uint16_t *)rs->v2 = readUint16(r);
    }
```

### 方法和属性签名
方法和属性签名带的几个属性是相同的，所以都用同一个结构体表示了。

> member_info.h

``` c
typedef struct MemberInfo
{
    // 访问控制符，是否静态，是否公开等
    uint16_t accessFlags;
    // 方法名|字段名在常量池中索引
    uint16_t nameIndex;
    // 描述符字符串
    // https://docs.oracle.com/javase/specs/jvms/se8/html/jvms-4.html#jvms-4.3.2
    uint16_t descriptorIndex;
    // 属性表，方法代码存在属性表中
    AttributeInfos *attributes;
} MemberInfo;
```

可以看到，在这个结构体中外层只有一些签名信息。

就方法而言，包括方法的访问控制信息和特性信息、方法的名称信息、方法的描述信息3部分，其中方法的描述符也是一串字符串，如下：

```
(IDLjava/lang/Thread;)Ljava/lang/Object;
```
实际就是方法

```
Object m(int i, double d, Thread t) {...}
```

那么方法中的具体实现代码存在哪里呢？答案是属性表中，属性表可以说是最复杂多样的一个结构了，基本上什么都有。


### 属性表
我们使用一个简单的结构体来表示属性表

> attribute_info.h

``` c
typedef struct AttributeInfo
{
    // 保留文件常量池的指针，后续不用每次传递了
    CP *cp;
    // 一共23中属性表，CJVM中仅解析需要用到的部分
    // https://docs.oracle.com/javase/specs/jvms/se8/html/jvms-4.html#jvms-4.7
    void *info;
} AttributeInfo;

typedef struct AttributeInfos
{
    uint32_t size;
    AttributeInfo **infos;
} AttributeInfos;
```

和常量池信息类似，属性表中的信息也有多种类型，类型很多，我们就不一一解析了，仅解析我们需要用到的几个。

> attribute_info.h

``` c
typedef struct ExceptionTableEntry
{
    // PC计数器起，可以理解为代码起，包括
    uint16_t startPc;
    // try-catch代码行止，不包括
    uint16_t endPc;
    // catch时处理行起，必须指向有效的code数组某一个下标
    uint16_t handlerPc;
    // catch异常类型类名
    uint16_t catchType;
} ExceptionTableEntry;

typedef struct ExceptionTable
{
    uint32_t size;
    ExceptionTableEntry **entrys;
} ExceptionTable;

/*
 * 实际的代码（指令）存储在属性表中
 */
typedef struct AttrCode
{
    uint16_t maxStack;
    uint16_t maxLocals;
    uint32_t codeLen;
    char *code;
    ExceptionTable *exceptionTable;
    AttributeInfos *attributes;
} AttrCode;


// Deprecated过期、内部生成字段等标记位
typedef struct MarkerAttribute
{

} MarkerAttribute;

// 定长属性
typedef struct ConstantValueAttribute
{
    uint16_t constantValueIndex;
} ConstantValueAttribute;

// 方法表示
typedef struct EnclosingMethodAttribute
{
    uint16_t classIndex;
    uint16_t methodIndex;
} EnclosingMethodAttribute;

// 指向异常表
typedef struct ExceptionsAttribute
{
    uint32_t len;
    uint16_t *exceptionIndexTable[];
} ExceptionsAttribute;

// 内部类
typedef struct InnerClassInfo
{
    uint16_t innerClassInfoIndex;
    uint16_t outerClassInfoIndex;
    uint16_t innerNameIndex;
    uint16_t innerClassAccessFlags;
} InnerClassInfo;

// 代码行数信息，方便在出错时定位问题，但不完全准确
typedef struct LineNumberTableEntry
{
    uint16_t startPc;
    uint16_t lineNumber;
} LineNumberTableEntry;

// 栈帧本地变量表
typedef struct LocalVariableTableEntry
{
    uint16_t startPc;
    uint16_t length;
    uint16_t nameIndex;
    uint16_t descriptorIndex;
    uint16_t index;
} LocalVariableTableEntry;

typedef struct MethodParameter
{
    uint16_t nameIndex;
    // 参数、方法、属性、类都有权限控制标记
    uint16_t accessFlags;
} MethodParameter;

// JDK8以后可以指定编译器保留形参的名称
typedef struct MethodParameters
{
    uint8_t len;
    MethodParameter **parameters;
} MethodParameters;

// 从哪编译而来
typedef struct SourceFileAttribute
{
    uint16_t signatureIndex;
} SourceFileAttribute;

// 后续再解析的属性
typedef struct UnparsedAttribute
{
    uint32_t nameLen;
    char *name;
    uint32_t length;
    uint32_t infoLen;
    char *info;
} UnparsedAttribute;

```
只展示了一部分解析后的结构体，对于我们不想解析的或者后续再解析的，我们统一使用```UnparsedAttribute```表示。

同样的，我们也是按照类型逐个解析这些属性表

> attribute_info.h

```
static AttributeInfo *readAttribute(ClassReader *r, CP *cp)
{
    uint16_t attrNameIndex = readUint16(r);
    char *attrName = getUtf8(cp, attrNameIndex);
    u_int32_t attrLen = readUint32(r);
    struct AttributeInfo *rs = (AttributeInfo *)malloc(sizeof(struct AttributeInfo));
    rs->cp = cp;
    if (strcmp(attrName, "Code") == 0)
    {
        struct AttrCode *attr = (AttrCode *)malloc(sizeof(struct AttrCode));
        attr->maxStack = readUint16(r);
        attr->maxLocals = readUint16(r);
        attr->codeLen = readUint32(r);
        attr->code = readBytes(r, attr->codeLen);

        uint16_t exceptionTableLength = readUint16(r);
        ExceptionTable *exceptionTable = malloc(sizeof(ExceptionTable));
        exceptionTable->size = exceptionTableLength;
        exceptionTable->entrys = malloc(sizeof(ExceptionTableEntry *) * exceptionTableLength);

        for (int i = 0; i < exceptionTableLength; i++)
        {
            exceptionTable->entrys[i] = malloc(sizeof(ExceptionTableEntry));
            exceptionTable->entrys[i]->startPc = readUint16(r);
            exceptionTable->entrys[i]->endPc = readUint16(r);
            exceptionTable->entrys[i]->handlerPc = readUint16(r);
            exceptionTable->entrys[i]->catchType = readUint16(r);
        }
        attr->attributes = readAttributes(r, cp);
        rs->info = attr;
    }
    else if (strcmp(attrName, "ConstantValue") == 0)
    {
        struct ConstantValueAttribute *attr = (ConstantValueAttribute *)malloc(sizeof(struct ConstantValueAttribute));
        attr->constantValueIndex = readUint16(r);
        rs->info = attr;
    }
    
    ...其他类型的解析
    
    else
    {
        struct UnparsedAttribute *attr = (UnparsedAttribute *)malloc(sizeof(struct UnparsedAttribute));
        attr->name = attrName;
        attr->infoLen = attrLen;
        attr->info = readBytes(r, attrLen);
    }
}
```

至此，我们已经将class文件解析为`ClassFile`结构体，接下来可以把它交给`ClassLoader`加载为运行时的`Class`结构体。