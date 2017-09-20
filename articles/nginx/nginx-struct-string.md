考虑到跨平台、高效率、统一规范，Nginx封装了许多的数据结构，大多数都是我们在其他开发项目中经常用到的一些，当然还有一些复杂的容器，笔者每篇文章会对其中一至两个点进行分析和练习讲解。

在Nginx中，使用Ngx_str_t表示字符串，它的定义如下：
```
typedef struct {
    size_t      len;
    u_char     *data;
} ngx_str_t;
```
我们可以看到它是一个简单的结构体，只有两个成员，data指针指向字符串起始地址，len表示字符串的长度。
这里你可能会产生疑惑，C语言中的字符串只需要有一个指针就能表示了，为什么这里还需要一个长度呢？这是因为C语言中我们常说的字符串，其实是以'\0'结尾的一串字符，约定俗称的，一旦读取到这个标记则表示字符串结束了，在C++中建立字符串的时候编译器会自动在后面加上'\0'标记。但是Ngx_str_t中的data指针却不是指向C语言中的字符串，而只是一串普通字符的起始地址，这串字符串不会特别的使用'\0'标记作为自己的结尾，所以我们需要len来告诉使用者字符串的长度。
那这样做有什么好处呢？作为网络服务器，Nginx当然更多考虑的这一方便开发的需求，在网络请求中，我们最多接触的就是URL地址，请求头信息，请求实体等，就拿URL地址来说，例如用户请求:
```
GET /test/string?a=1&b=2 http/1.1\r\n
```
那如果我们使用了一个Ngx_str_t结构体来存储了这个值，现在我们想获取请求类型，是GET还是POST或是PUT？我们不需要拷贝一份内存，我们要做仅仅是做一个新的ngx_str_t，里面的data指针是指向和原先的ngx_str_t一个地址，然后将len改为3即可。
当然，这只是个一个最简单的应用，字符串类型几乎是各种业务系统也好，网络框架也好使用十分广泛的一种基本类型，良好的设计结构是Nginx低内存消耗的重要保证。

##ngx_str_t的操作
有了字符串这个简单的一个结构体其实并不是特别的方便，在Java，Python这样的现代高级语言中，都提供了丰富对于字符串类型的操作，Nginx也提供了不少的字符串操作公共函数，尽管有些看上去并不是那么容易用好，那么我们来一一看下这些函数。

在Ngx_string.h文件中定义了许多Nginx字符串操作函数或宏

###（1）字符串初始化相关宏
Nginx定义了一些用于初始化字符串的基本宏，方便用户用一个常面量字符串来初始化或简单设置一个ngx_str_t结构体。
#### 1）ngx_string宏
```c++
#define ngx_string(str)     { sizeof(str) - 1, (u_char *) str }
```
这是Nginx提供的用于初始化一个Nginx字符串的宏，传入的是一个普通的字符串，即我们常说的C语言字符串。
也如常见的宏的副作用一样，使用时需要注意不能像调用函数一样去操作。
```
// 错误的写法
ngx_str_t str_a;
str_a = ngx_string("abc");

// 正确的写法
ngx_str_t str_a = ngx_string("abc");
```
这是因为C语言允许给结构体初始化时使用{xxx,xxx}这种形式进行赋值，但是不允许在普通的赋值中使用这类形式，这是一种规定，也就是标准。如果非要推敲一下，个人认为，在初始化时，编译器会衡量 = 号左右两边的表达式，因为左边是一个定义语句，此时编译器可以轻松分辨出右侧的表达式是什么类型，则可以完成赋值，然后在定义完成之后，再想要进行普通的赋值，编译器会先计算 = 号右边的表达式，此时并不能确定子表达式的类型，编译器会直接抛出一个错误。
当然这并不是我们讨论的重点，笔者的意思，在使用这些Nginx提供的宏时，需要注意使用规范。

#### 2）ngx_null_string宏
```
#define ngx_null_string     { 0, NULL }
```
帮助快速定义一个“空字符串”

#### 3）ngx_str_set宏
```
#define ngx_str_set(str, text)  \
    (str)->len = sizeof(text) - 1; (str)->data = (u_char *) text
```
前面我们说到，一下写法是错误的。
```
// 错误的写法
ngx_str_t str_a;
str_a = ngx_string("abc");
```
那如果有的时候我们确实需要先定义，后根据情况再赋值，这时我们怎么办呢？这时我们可以使用ngx_str_set宏：
```
ngx_str_t str_a;
str_a = ngx_str_set(&str_a, "abc");
```

#### 4）ngx_str_null宏
其实我们感觉叫 ngx_str_set_null更好的，它的作用和ngx_str_set类似，就是将一个ngx_str_t结构体设置为“空字符串”。
```
#define ngx_str_null(str)   (str)->len = 0; (str)->data = NULL
```

### （2）C字符串信息获取宏
对于一个字符串，这里说的是C中的字符串，我们经常会查询这个字符串的长度，这个字符串是否包含另外一个字符串，这个字符串第某某位是什么字符等等，Nginx也为我们获取字符串的这一类信息提供了几个宏，它们大多采用C标准库来实现。
当然，也包括函数，由于功能比较单一，所以宏居多。
#### 1）ngx_strncmp宏
该宏的作用是是指定比较size个字符，也就是说，如果字符串s1与s2的前size个字符相同，函数返回值为0。
```
#define ngx_strncmp(s1, s2, n)  strncmp((const char *) s1, (const char *) s2, n)
```
若s1与s2的前n个字符相同，则返回0；若s1大于s2，则返回大于0的值；若s1 若小于s2，则返回小于0的值。
其实就是一个C标准库函数的使用，不太熟悉的同学可以写个小例子练习一下即可。
####2）ngx_strcmp宏
```
#define ngx_strcmp(s1, s2)  strcmp((const char *) s1, (const char *) s2)
```
同ngx_strncmp宏类似，只不过是比较整个字符串。

####3）ngx_strlen宏
用于得到字符串长度，Nginx习惯性的将其重定义以做到跨平台。
```
#define ngx_strlen(s)       strlen((const char *) s)
```

#### 4）ngx_strstr宏
```
#define ngx_strstr(s1, s2)  strstr((const char *) s1, (const char *) s2)
```
用于判断字符串s2是否是s1的子串，也即字符串s1是否包含s2。

#### 5）ngx_strchr宏
```
#define ngx_strchr(s1, c)   strchr((const char *) s1, (int) c)
```
查找字符串s1中首次出现字符c的位置。

#### 6）ngx_strlchr函数
返回某个字符之后的剩余字符串，前提是在last之前。
```
static ngx_inline u_char *
ngx_strlchr(u_char *p, u_char *last, u_char c)
{
    while (p < last) {

        if (*p == c) {
            return p;
        }

        p++;
    }

    return NULL;
}
```
这个函数是Nginx额外定义的，比如字符串```"Get /app/test?a=1&b=2"```，```last```指向最后一个字符，传入参数```c = 'p'```，则调用这个函数得到的结果是```pp/test?a=1&b=2```字符串的指针。

### （3）字符串操作相关函数
同（2）类似，这里不单单是函数，也存在宏，只不过函数占多数。
我们在实际的业务操作中，免不了多字符串进行尾部追加，截取，格式化输出等操作，同样的Nginx提供了一些简单的操作捷径，能够满足我们大多数的操作需求。

#### 1）ngx_cpy_mem宏
```
#if (NGX_MEMCPY_LIMIT)

void *ngx_memcpy(void *dst, const void *src, size_t n);
#define ngx_cpymem(dst, src, n)   (((u_char *) ngx_memcpy(dst, src, n)) + (n))

#else

/*
 * gcc3, msvc, and icc7 compile memcpy() to the inline "rep movs".
 * gcc3 compiles memcpy(d, s, 4) to the inline "mov"es.
 * icc8 compile memcpy(d, s, 4) to the inline "mov"es or XMM moves.
 */
#define ngx_memcpy(dst, src, n)   (void) memcpy(dst, src, n)
#define ngx_cpymem(dst, src, n)   (((u_char *) memcpy(dst, src, n)) + (n))

#endif
```
其实这里就将其看作是一个简单的memcpy就好。

#### 2）ngx_copy函数
```
/*
 * the simple inline cycle copies the variable length strings up to 16
 * bytes faster than icc8 autodetecting _intel_fast_memcpy()
 */

static ngx_inline u_char *
ngx_copy(u_char *dst, u_char *src, size_t len)
{
    if (len < 17) {

        while (len) {
            *dst++ = *src++;
            len--;
        }

        return dst;

    } else {
        return ngx_cpymem(dst, src, len);
    }
}
```
这个函数唯一让人感到困惑的地方在于，为什么少于17的字符串追加，直接使用普通的指针追加即可，而如果长于17则调用libc中的memcpy呢？

其实注释中已经讲的比较清楚，系统拷贝会对较长的字符串的拷贝做优化，也就是说，不是像我们这样指针一个个移动的方式来进行的，但是在这种优化执行之前，它也会做许多的检查还有初始化一些环境，如果本身字符串就比较小的话，这些就完全没必要了，Nginx的作者经过一系列的测试，从经验上得出了小于17个字符串时，还是手动拷贝效率高，感觉这更像是作者的一个经验值，如果是理论值的话，他的注释应该会列出来如何计算的。
