
Redis官方在2016年12月发布了4.0-rc1版本，从此揭开了4.0版本的序幕，但到目前为止（2017年6月）还没有正式发布4.0版本提供给生产环境使用，笔者在2.8时代开始接触Redis，在做的几个项目中也都使用它作为缓存和数据交换的渠道，想着前辈们把3.0版本都源码解析的都差不多了，网上4.0版本解析却很少，所以和大家共同分享下Redis源码阅读的经历。
本文所指的新特性对比的是 https://github.com/antirez/redis 仓库中3.0分支和4.0分支的差异。

> 为了大家看整体源码方便，我将加上了完整注释的代码传到了我的github上供大家直接下载：
> https://github.com/charpty/redis4.0-source-reading


## SDS动态字符串
和其它分析Redis之前版本一样，先来看最基本字符串都处理，SDS是Redis自定义都动态字符串，全称为```Simple Dynamic Strings```，和之前版本一样SDS还是由两部分组成，结合代码我称之为头部（sdshdr结构体）和sds（实际字符串指针），组成如下：
+--------------------------------------------------------
| 头部 | 标准的C字符串 | 剩余的未分配空间
+--------------------------------------------------------

原理比较简单，头部中记录了已使用的长度和总的分配长度（之前版本是记录的剩余长度），这样想追加字符串时不需要像单纯C语言那样重新开辟一块空间然后将原字符串和追加内容一起拷贝过去，而是直接将其添加到SDS未分配的空间中，当然，遇到剩余未分配空间不足的情况则需要进行扩容。

 - ```sds.c```和```sds.h```文件为Redis的"动态字符串（SDS）"数据结构的实现
 - SDS分为两部分，一部分称为头部(```sdshdr```结构体)
 - 另一部分则是实际的字符串（地址紧跟```sdshdr```结构体后,代码中称为```sds```）
 - 小写的类型别名```sds```则是指实际的字符串，也就是SDS的第二部分


### SDS特性
SDS最大的一个好处就是它对C标准字符串的兼容是非常好的，它定义了一个类型别名
```
// 类型别名，指向sdshdr结构体中的buf属性，也就是实际的字符串的指针
// 注意将其与大写SDS区分
// SDS泛指的Redis设计的动态字符串结构(结构体sdshdr + 实际字符串sds)
typedef char *sds;
```
当进行创建字符串、追加字符串、拷贝字符串等等几乎所有操作时都是返回```sds```，大家也注意到其实sds也就是```char*```类型，加之SDS总是在字符串尾部添加```'\0'```所以它就是一个标准的C字符串，这样在使用时非常方便，不像其它动态字符串结构体一样，每次想获取实际的字符串都得```p->buf```，当然这么涉及带来了方便也带来了危险，由于是直接将实际的字符串返回给调用者使用，所以当程序在多处地方使用同一个引用时很容易出现内存泄漏问题。

除了兼容C字符串，SDS还具有动态扩容特性和二进制安全（操作都是memcpy）的特点，对于4.0版本的，我觉得很大的改进是SDS的空间利用率有显著的提高，但计算效率有所下降（为了区分具体使用哪种头部结构体不得不每次都计算或判断）

**Redis的作者为SDS单独开辟了一个仓库**，他希望将SDS独立于Redis，让SDS也可以被其它项目单独使用（我在某次向Redis提交PR的时候有个好心的哥们告诉我SDS的修改需要向新仓库提交）
独立的SDS仓库：https://github.com/antirez/sds

### 头部结构体
在之前的版本中，仅用一个结构体表示头部
```
struct sdshdr {
    // buf 中已使用的长度
    int len;
    // buf 中剩余可使用的长度
    int free;
    // 柔性数组，实际字符串地址
    char buf[];
};
```
在4.0版本少有变化，free改为了alloc（总分配长度），并添加了flags标记具体使用了哪一种结构体，这是因为4.0版本针对不同的字符串长度使用了不同的结构体，比如长度小于32的字符串，则会使用sdshdr5结构体
```
struct __attribute__ ((__packed__)) sdshdr5 {
	// flags既是标记了头部类型，同时也记录了字符串的长度
	// 共8位，flags用前5位记录字符串长度（小于32=1<<5），后3位作为标志
    unsigned char flags;
    char buf[];
};
```
在字符串本身较短的情况下，SDS的内存分配是非常节约的，巧妙的利用一个标志位来记录长度，减少头部所占内存。
再比如字符串长度大于32且小于256时则判定为```SDS_TYPE_8```类型
```
// __attribute__是为了增强编译器检查
// __packed__则是告诉编译器则可能少的分配内存
struct __attribute__ ((__packed__)) sdshdr8 {
    // 字符串的长度，即已经使用的buf长度
    uint8_t len;
    // 为buf分配的总长度，之前版本记录的是free(还剩下多少长度)
    uint8_t alloc;
    // 新增属性，记录该结构体的实际类型
    unsigned char flags;
    // 柔性数组，为结构体分配内存的时候顺带分配，作为字符串的实际存储内存
    // 由于buf不占内存，所以buf的地址就是结构体尾部的地址，也是实际字符串开始的地址
    char buf[];
};
```
新版本一共定义了5种类型，会根据不同的字符串长度来分配
```
/*
 * 根据字符串的长度确定要使用的实际sdshdr结构体的类型
 *
 * 参数列表
 *      1. string_size: 用于初始化的字符串的长度
 *
 * 返回值
 *      要使用的sdshdr类型，一共5种，仅SDS_TYPE_5比较特殊(sdshdr5是非常节约内存的一个结构体)
 *      其他类型都相同，记录了使用长度和总分配长度
 *      所有结构体都有记录具体结构体类型的flags属性和末尾柔性数组（用于动态分配实际字符串存储空间）
 */
static inline char sdsReqType(size_t string_size) {
    if (string_size < 1<<5)
        return SDS_TYPE_5;
    if (string_size < 1<<8)
        return SDS_TYPE_8;
    if (string_size < 1<<16)
        return SDS_TYPE_16;
#if (LONG_MAX == LLONG_MAX)
    if (string_size < 1ll<<32)
        return SDS_TYPE_32;
#endif
    return SDS_TYPE_64;
}
```
SDS的结构本质上和之前没有什么变化，只是添加了不同长度字符串不同头部结构体的特性，接下来我们通过SDS字符串最主要的几个操作来具体看下源码

## 创建SDS
创建一个SDS并返回实际的字符串指针sds一共有4种方法
```
// 实际上内部都调用这个函数
sds sdsnewlen(const void *init, size_t initlen);
sds sdsnew(const char *init);
sds sdsempty(void);
sds sdsdup(const sds s);
```
由于其它3个函数实际上都调用```sdsnewlen```这个函数，我们仅对该函数分析即可了解整个创建过程。
```
/*
 * 截取给定字符串指定长度作为初始化值来创建一个SDS(sdshdr结构体+实际字符串)动态字符串
 *
 * 参数列表
 *      1. init: 用于初始化sds的普通字符串, 将根据initlen截取其中一部分作为初始化值
 *      2. initlen: 指定要截取多少长度的init字符串作为初始化值
 *
 * 返回值
 *      SDS中的实际字符串的指针
 */
sds sdsnewlen(const void *init, size_t initlen) {
    // 为何什么一个void*而不是struct shshdr *sh呢
    // 因为新版本为了进一步提升性能，不同的长度的字符串将使用不同的结构体
    // SDS_HDR_VAR这个宏用于具体创建结构体，变量名必须为sh,宏里已经写死
    void *sh;
    // sds是类型别名，其实就是sdshdr中的buf属性的指针
    sds s;
    // 根据不同的长度决定使用不同的结构体
    // 在sds.h中共声明了5种sdshdr结构体
    char type = sdsReqType(initlen);
    // 这是个经验写法，当想构造空串时大多数情况都是为了放入超过32长度的字符串
    if (type == SDS_TYPE_5 && initlen == 0) type = SDS_TYPE_8;
    int hdrlen = sdsHdrSize(type);
    // 新版本中添加到sdshdr结构体中的新变量,为了标记到底使用了哪种结构体
    unsigned char *fp; /* flags pointer. */

    // +1是为了放字符串结尾'\0'
    sh = s_malloc(hdrlen+initlen+1);
    if (!init)
        memset(sh, 0, hdrlen+initlen+1);
    if (sh == NULL) return NULL;
    s = (char*)sh+hdrlen;
    // s是shshdr的末尾柔性数组，所以-1就得到结构体中的flags属性的地址
    fp = ((unsigned char*)s)-1;
    switch(type) {
        case SDS_TYPE_5: {
            // 标志位仅为后3位，左移3位相当于标志位置0
            // 且因为长度小于32所以不会丢失字符串长度真实数值
            // 此时字符串实际长度和总分配长度都不需要记录，fp >> 3就是结果
            *fp = type | (initlen << SDS_TYPE_BITS);
            break;
        }
        // 其他情况则按照长度分配不同的结构体并设置属性
        case SDS_TYPE_8: {
            SDS_HDR_VAR(8,s);
            sh->len = initlen;
            sh->alloc = initlen;
            *fp = type;
            break;
        }
        case SDS_TYPE_16: {
            ...省略
        }
        case SDS_TYPE_32: {
            ...省略
        }
        case SDS_TYPE_64: {
            ...省略
        }
    }
    // 将初始化字符串拷贝到sdshdr结构体的末尾
    // 这体现了柔性数组或者说动态数组确实分配方便且使用简洁
    if (initlen && init)
        memcpy(s, init, initlen);
    s[initlen] = '\0';
    // 这里返回的不是sdshrd结构体而是返回结构体中的buf，也就是真正的字符串
    // 这么做主要因为Redis代码中大多数用到的都是字符串而不是sdshdr结构体,直接用sds(char*)会比用结构体方便的多
    // 在新版本中由于采用多种sdshdr也没办法返回sdshdr结构体（老版本也是返回sds，这里仅做说明）
    return s;
}
```

## 追加字符串
和创建字符串一样，追加字符串最终也是调用同一个函数sdscatlen()进行追加
```
/*
 * 截取指定字符串的指定长度追加到原有字符串中
 *
 * 参数列表
 *      1. s: 原有字符串，空间不够则会对该字符串所在sdshdr结构体进行扩容
 *      2. t: 要追加到原有字符串后的值
 *      3. len: 要截取的待拷贝的值的长度
 *
 * 返回值
 *      新的sds字符串指针或原先的sds字符串指针
 */
sds sdscatlen(sds s, const void *t, size_t len) {
    // 先算出当前字符串所在sdshdr结构体中已使用的字符串长度
    // 这里可以使用标准的strlen计算因为确实添加'\0'到字符串尾部但这样做只是为了兼容字符串使用
    // 所以这里取结构体中记录的长度值而不是去依赖兼容写法
    size_t curlen = sdslen(s);
	// 根据新长度进行扩容或者保持不变
    s = sdsMakeRoomFor(s,len);
    if (s == NULL) return NULL;
    // 直接进行内存拷贝而不是字符串拷贝保证了二进制兼容
    memcpy(s+curlen, t, len);
    // 设置新长度
    sdssetlen(s, curlen+len);
    s[curlen+len] = '\0';
    return s;
}
```
追加函数本身并不是关键，我们关注的是它如何进行扩容，扩容都在sdsMakeRoomFor()函数中完成
```
/*
 * 在必要情况下对SDS进行扩容
 *
 * 参数列表
 *      1. s: 待扩容对SDS对字符串指针
 *      2. addlen: 需要新加入字符串的长度
 *
 * 返回值
 *      返回扩容后新的sds，如果没扩容则和入参sds地址相同
 */
sds sdsMakeRoomFor(sds s, size_t addlen) {
    void *sh, *newsh;
    // 首先计算出原SDS还剩多少可分配空间
    size_t avail = sdsavail(s);
    size_t len, newlen;
    char type, oldtype = s[-1] & SDS_TYPE_MASK;
    int hdrlen;

    /* Return ASAP if there is enough space left. */
    // 已经够用的情况下直接返回
    if (avail >= addlen) return s;

    len = sdslen(s);
    // 用sds（指向结构体尾部，字符串首部）减去结构体长度得到结构体首部指针
    // 结构体类型是不确定的，所以是void *sh
    sh = (char*)s-sdsHdrSize(oldtype);
    newlen = (len+addlen);
    // 如果新长度小于最大预分配长度则分配扩容为2倍
    // 如果新长度大于最大预分配长度则仅追加SDS_MAX_PREALLOC长度
    if (newlen < SDS_MAX_PREALLOC)
        newlen *= 2;
    else
        newlen += SDS_MAX_PREALLOC;
    // 字符串的长度更改了，使用对头部类型可能也会变化
    type = sdsReqType(newlen);
    // 由于SDS_TYPE_5没有记录剩余空间（用多少分配多少），所以是不合适用来进行追加的
    // 为了防止下次追加出现这种情况，所以直接分配SDS_TYPE_8类型
    if (type == SDS_TYPE_5) type = SDS_TYPE_8;

    hdrlen = sdsHdrSize(type);
    if (oldtype==type) {
        // 类型没变化则直接使用原起始地址重新分配下内存即可
        newsh = s_realloc(sh, hdrlen+newlen+1);
        if (newsh == NULL) return NULL;
        s = (char*)newsh+hdrlen;
    } else {
        /* Since the header size changes, need to move the string forward,
         * and can't use realloc */
        // 头部类型有变化则重新开辟一块内存并将原先整个SDS拷贝一份过去
        newsh = s_malloc(hdrlen+newlen+1);
        if (newsh == NULL) return NULL;
        memcpy((char*)newsh+hdrlen, s, len+1);
        // 旧的已经没用了
        s_free(sh);
        s = (char*)newsh+hdrlen;
        // 配置新类型
        s[-1] = type;
        sdssetlen(s, len);
    }
    // 设置新对分配对总长度
    sdssetalloc(s, newlen);
    return s;
}
```