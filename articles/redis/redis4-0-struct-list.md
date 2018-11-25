> 笔者博客地址： https://charpty.com

> 为了大家看整体源码方便，我将加上了完整注释的代码传到了我的github上供大家直接下载：
> https://github.com/charpty/redis-source-reading

上一章讲了SDS动态字符串，大概讲了看的方向，其实更深层次的还是要请读者自己看源码，我将源码加上了注释，这样大家看起来也更加的方便，本文讲Redis中的链表。


----------
Redis中的链表地位很高，除了Redis对外暴露的list功能用到内部的链表之外，其实内部的很多结构和功能都间接使用了链表来实现，Redis中链表的实现分为3个部分，也使用了3个C文件来描述：```ziplist.c```、```adlist.c```、```quicklist.c```，其中```quicklist.c```是在前两者的基础上实现的Redis对外暴露的列表，也就是我们经常使用的```lpush```、```linsert```、```lindex```等命令的具体实现，我们称之为```快速列表```，既然他是基于前两者（压缩列表ziplist和双向链表adlist）来实现的，那想要了解它就必须先了解前两者。

细心的读者应该注意到，我称```ziplist```为列表，称```adlist```为链表，个人理解的列表指的是内存连续或者大多数内存连续的数据结构,也就是平常所说的顺序表，而链表则用于指仅仅在逻辑上连续而在内存上不连续的列表结构。```adlist```是一个双向链表，各个节点包含了前一个节点和后一个节点指针，在```quicklist```中使用类似```adlist```的链表作为作为中控器，也就是连接一个又一个```ziplist```的链表嵌套层，```quicklist```使用双向链表存储底层数据结构```ziplist```，这样既保留了动态扩展链表的需求，又尽可能的使用了连续内存，提高了内存使用率和查询效率，大家平常所用的```LPUSH```、```LRANGE```等命令就是使用的```quicklist```。

其实```quicklist```就是```adlist```这个通用双向链表的思想加上ziplist的结合体，所以我们先来了解下通用链表```adlist```，它是Redis内部使用最多最广泛的链表，比较简单，也就是大家平常最常了解的链表，虽然实现方式没有太多的特殊点，但我们也大致讲下，方便我们后续读```quicklist```中的双向链表时做铺垫。

## 一、通用双向链表adlist
```adlist```，```a double linked list```，和这个间接普通的C源文件名字以一样，```adlist```的实现也是非常简单明了，一个普通的双向链表，我们先看其节点定义
``` c
typedef struct listNode {
    // 前一个节点
    struct listNode *prev;
    struct listNode *next;
    // 节点的具体值指针，由于为void*，所以链表中节点的值类型可以完全各不相同
    void *value;
} listNode;
```
节点的定义很简单，存储了前一个节点和后一个节点，值可以存储任意值，按理说直接使用```listNode```就直接能够构成链表结构，但是使用```adlist```定义的 ```list```结构体操作会更加的方便，我们来看下使用该结构体更加方便
``` c
  typedef struct list {
      // 链表的首个元素
      listNode *head;
      // 链表的尾部元素
      // 之所以记录尾部元素是因为可以方便的支持redis能够通过负数表示从尾部倒数索引
      listNode *tail;
      // 节点拷贝函数,在对链表进行复制时会尝试调用该函数
      // 如果没有设置该函数则仅会对链表进行浅拷贝（直接拷贝将值的地址赋给新链表节点）
      void *(*dup)(void *ptr);
      // 在释放链表节点元素内存前会尝试调用该函数,相当于节点销毁前的一个监听
      void (*free)(void *ptr);
      // 在搜索链表中节点时会调用该函数来判断两个节点是否相等
      // 如果没有设置该函数则会直接比较两个节点的内存地址
      int (*match)(void *ptr, void *key);
      // 链表当前的节点个数，即链表长度，方便统计(因为有提供给用户获取链表长度的命令llen)
      unsigned long len;
  } list;
```
虽然listNode本身可以表示链表，但是```list```结构体操作更加方便并且记录了一些关键信息，降低了查询复杂度，另外由于```list```的函数指针，使得对于链表的复制、节点释放、节点的搜索可以更加的灵活，由调用者自由定义。特别是```match```函数，由于链表的值是各异的，所以如何比较两个值是否相等是仅有链表的使用者才最清楚。

### 1.1 adlist链表插入值
创建链表的过程很简单，不再单独列出，仅是创建一个```list```结构体并设置初始值，我们看下在链表中插入值的过程
``` c
/*
   * 插入一个节点到指定节点的前面或者后面
   *
   * 参数列表
   *      1. list: 待操作的链表
   *      2. old_node: 要插入到哪一个节点的前面或者后面
   *      3. value: 要插入的值
   *      4. after: 如果为0则插入到old_value的前面，非0则插入到old_value的后面
   *
   * 返回值
   *      返回值即是链表本身，仅是为了方便链式操作
   */
  list *listInsertNode(list *list, listNode *old_node, void *value, int after) {
      listNode *node;

      // 如果不能插入新节点则返回空告诉上层调用者插入失败
      if ((node = zmalloc(sizeof(*node))) == NULL)
          return NULL;
      node->value = value;
      if (after) {
          // 插入到指定节点的后面
          node->prev = old_node;
          node->next = old_node->next;
          // 如果正好插入到了链表的尾部则将新插入的节点设置链表尾
          if (list->tail == old_node) {
              list->tail = node;
          }
      } else {
          // 插入到指定节点的前面
          node->next = old_node;
          node->prev = old_node->prev;
          // 如果正好插入到了链表头部则将新的节点设置为链表头
          if (list->head == old_node) {
              list->head = node;
          }
      }
      // 设置前后节点对应的前后指针值
      if (node->prev != NULL) {
          node->prev->next = node;
      }
      if (node->next != NULL) {
          node->next->prev = node;
      }
      list->len++;
      return list;
  }
```

### 1.2 adlist链表查询
插入链表的过程基本上能够了解到Redis这个双向链表的内部结构以及设计原理，除了这个还剩下的就是对链表的查询了，其中搜索```listSearchKey```很好的展示了链表查询的过程
``` c
/*
   * 搜索指定与key值匹配的节点, 返回第一个匹配的节点
   * 如果有链表中有匹配函数则使用匹配函数，否则直接判断key值地址与节点值地址是否相等
   *
   * 参数列表
   *      1. list: 待搜索的链表
   *      2. key: 用于搜索的key值
   *
   * 返回值
   *      与key值匹配的节点或者空
   */
  listNode *listSearchKey(list *list, void *key)
  {
      listIter iter;
      listNode *node;

      // 先重置迭代器的迭代起始位置为链表头
      listRewind(list, &iter);
      // 调用链表的迭代器逐一遍历链表元素
      while((node = listNext(&iter)) != NULL) {
          // 如果链表设置了节点匹配函数则使用否则直接比较内存地址
          if (list->match) {
              if (list->match(node->value, key)) {
                  return node;
              }
          } else {
              if (key == node->value) {
                  return node;
              }
          }
      }
      return NULL;
  }
```
Redis的通用双向链表实现比较简单，通过这两个函数基本上就对整个```adlist```有了一定的了解。

## 二、压缩列表ziplist
Redis是非常注意节约内存的，极高的内存利用率是Redis的一大特点，也是因为目前服务器的计算能力是大量富余的，所以拿计算换内存是很值得的。
```zippiest``` 的结构体比较复杂，先从最外层看起，结构体如下
```
<total-bytes><tail-offset><len><entry>...<entry><end-mark>
```
名称均是按我自己的理解命名的，也就是
```
<总的内存分配大小> <末尾元素地址> <列表长度> <节点> <节点> ... <结束标记>
```
这个结构仅仅是根据源码逻辑构思出来的，在Redis中没有声明任何结构体来表示这个结构，压缩列表```ziplist```的表示方法就是一个普通```char*```指针，再加上一大堆的宏操作，就构成了这个压缩列表，具体看下各个值的情况

 1.  **total-bytes**：32位整型，表示```ziplist```所用的总内存数
 2. **tail-offset**:  表示列表最有一个元素的地址，之所以有它是因为Redis的风格是大量的支持倒序索引的，有了它就很方便在尾端进行操作。
 3. **len**：列表的长度，16位整型，为了表示更大意义上的长度值甚至无限长，当它小于2^16-1时表示的是节点的个数，但是等于2^16-1时则代表该列表长度不可存储，必须要遍历列表才能得出长度
 4. **entry**：表示真正存放数据的数据项，长度是不固定的，每个entry都有自己的数据结构，用于动态表示节点长度以及编码方式
 5. **end-mark**：标记列表结束，固定值255

列表中的具体节点```entry```则显得有点复杂了，它的结构是比较典型的TLV格式，前几位来表示编码类型，然后是数据长度，接着就是数据，具体的结构如下
```
<prevrawlen><len><data>
```
这几个名称是在Redis源码注释中有出现的，分别代表着

 1. **prevrawlen**：前一个节点的总长度，该属性本身长度也是动态的，当前一个节点的长度小于254时，则为1个char长度，其它情况长度则为5个char，第一位char为标记位(254)，后4位char用于表示前一个节长度
 2. **len**：当前节点的真实数据的长度，和**prevrawlen**一样，该属性本身的长度也是动态的，如前文所说采用TLV形式，不同的类型对应不同的长度和数据存储方式，稍后单独讲解
 3. **data**：实际的数据，分为字符或整型两种形式存储，具体形式由**len**中设定编码决定

 对于len值编码的设定一共分为9种，我们通过宏```ZIP_DECODE_LENGTH```来了解下

``` c
 /*
 * 解析指定到entry节点并将编码类型，存储长度的元素的长度，列表长度的值设置到对应的变量中
 * 步骤如下
 *  1、先得到编码类型，一共9种，分别表示使用了几位字符来表示该节点的总长度
 *  2、编码小于1100 0000共有3种类型，此类型下数据(data)存储的都是字符(char)
 *      1. 00xxxxxx: 前两位作为标志位，后6位用来记录长度
 *      2. 01xxxxxx xxxxxxxx 共2位: 使用14位来记录长度，最大值位2^14 - 1
 *      3. 10xxxxxx xxxxxxxx...共5位: 使用32位来记录长度(带标记位的char整个舍弃不用)，最大值2^32 - 1
 *  3、编码大于1100 0000共规定了6种类型，长度均采用1个字符表示，每种类型数据的存储格式也各不相同
 *      4. 1100 0000: data指针存储数据格式为16字节整型
 *      5. 1101 0000: data指针存储数据格式为32字节整型
 *      6. 1110 0000: data指针存储数据格式为64字节整型
 *      7. 1111 0000: data指针存储数据格式为3字节整型
 *      8. 1111 1110: data指针存储数据格式为1字节整型
 *      9. 1111 dddd: 特殊情况，后4位表示真实数据，0～12，也就是dddd的值减去1就是真实值
 *                    之所以减1是因为较小的数字肯定是从0开始，但1111 0000又和第6点冲突
 *                    最大只到1101因为1110又和第8点冲突
 */
define ZIP_DECODE_LENGTH(ptr, encoding, lensize, len) do {                    \
    ZIP_ENTRY_ENCODING((ptr), (encoding));                                     \
    if ((encoding) < ZIP_STR_MASK) {                                           \
        if ((encoding) == ZIP_STR_06B) {                                       \
            (lensize) = 1;                                                     \
            (len) = (ptr)[0] & 0x3f;                                           \
        } else if ((encoding) == ZIP_STR_14B) {                                \
            (lensize) = 2;                                                     \
            (len) = (((ptr)[0] & 0x3f) << 8) | (ptr)[1];                       \
        } else if ((encoding) == ZIP_STR_32B) {                                \
            (lensize) = 5;                                                     \
            (len) = ((ptr)[1] << 24) |                                         \
                    ((ptr)[2] << 16) |                                         \
                    ((ptr)[3] <<  8) |                                         \
                    ((ptr)[4]);                                                \
        } else {                                                               \
            panic("Invalid string encoding 0x%02X", (encoding));               \
        }                                                                      \
    } else {                                                                   \
        (lensize) = 1;                                                         \
        (len) = zipIntSize(encoding);                                          \
    }                                                                          \
} while(0);
```
 根据不同的编码类型，Redis使用尽可能小的内存对其进行存储，了解了存储结构，基本上就对压缩列表```ziplist```了解了大半了，接下来我们看下它的插入操作

### 2.1 压缩列表插入值
```c
/*
 * 在压缩列表指定位置插入一个字符串值
 *
 * 参数列表
 *      1. zl: 待插入的压缩列表
 *      2. p: 要插入到哪个位置
 *      3. s: 待插入的字符串(不以NULL结尾)的起始地址
 *      4. slen: 待插入的字符串的长度，由于不是标准的C字符串，所以需要指定长度
 *
 * 返回值
 *      压缩列表地址
 */
unsigned char *__ziplistInsert(unsigned char *zl, unsigned char *p, unsigned char *s, unsigned int slen) {
    // 先取出当前压缩列表总内存分配长度
    size_t curlen = intrev32ifbe(ZIPLIST_BYTES(zl)), reqlen;
    unsigned int prevlensize, prevlen = 0;
    size_t offset;
    int nextdiff = 0;
    unsigned char encoding = 0;
    // 这个初始化值只是为了防止编译器警告
    long long value = 123456789;
    zlentry tail;

    // 因为每个节点都会记录上一个节点数据占用的内存长度(方便倒序索引)，所以先查出该值
    // 如果待插入的位置是压缩列表的尾部, 则相当于尾部追加
    if (p[0] != ZIP_END) {
        // 如果不是插入尾部则根据p正常获取前一个节点的长度
        ZIP_DECODE_PREVLEN(p, prevlensize, prevlen);
    } else {
        // 如果是尾部追加则先获取列表中最后一个节点的地址(注意最后一个节点并不一定是列表结束)
        unsigned char *ptail = ZIPLIST_ENTRY_TAIL(zl);
        // 如果最后一个节点也是空的(ptail[0]==列表结束标记)则代表整个压缩列表都还是空列表
        // 如果不是空列表则正常取出最后一个节点的长度
        if (ptail[0] != ZIP_END) {
            // 取出尾部节点所占内存字符长度
            prevlen = zipRawEntryLength(ptail);
        }
    }

    // 如果可以转换为整型存储则使用整型存储
    if (zipTryEncoding(s,slen,&value,&encoding)) {
        // 计算整型所占长度
        // 1位: -128~127，2位: -32768~3276...
        reqlen = zipIntSize(encoding);
    } else {
        // 如果不能转换为整型存储则直接使用字符串(char)方式存储
        reqlen = slen;
    }
    // 除了存储数据(V)，一个节点还还需要存储编码类型(T)和节点长度(L)以及前一个节点的长度
    // 计算出存储上一个节点长度的值所需要的内存大小
    reqlen += zipStorePrevEntryLength(NULL,prevlen);
    // 计算处需要存储自己的编码类型所需的内存大小
    reqlen += zipStoreEntryEncoding(NULL,encoding,slen);

    // 计算出存储该节点的长度所需的内存大小并尝试赋值给该节点的下一个节点(每个都节点存储上一个节点的长度)
    int forcelarge = 0;
    // 如果插入的节点不是列表尾的话，那该节点的下一个节点应该存储该节点的长度
    // 计算出下一个节点之前已经分配的用于存储上一个节点长度的内存和目前存储实际所需内存的差距
    nextdiff = (p[0] != ZIP_END) ? zipPrevLenByteDiff(p,reqlen) : 0;
    // 其实存储长度值仅有两种可能，小于254则使用一个char存储，其它则使用5个char存储
    if (nextdiff == -4 && reqlen < 4) {
        // 如果所需内存减少了(之前一个节点长度比当前节点长)
        // 但是当前节点又已经存储为较小的整数的情况下(共两种编码)则不进行缩小了
        nextdiff = 0;
        forcelarge = 1;
    }

    offset = p-zl;
    // 根据新加入的元素所需扩展的内存重新申请内存
    zl = ziplistResize(zl,curlen+reqlen+nextdiff);
    // 重新申请之后原来的p有可能失效(因为整块列表地址都换了)，所以根据原先偏移量重新计算出地址
    p = zl+offset;

    // 接下来开始挪动p两端的位置并把新的节点插入
    if (p[0] != ZIP_END) {
        // 把p位置之后的元素都往后移动reqlen个位置，空出reqlen长度的内存给新节点使用
        memmove(p+reqlen,p-nextdiff,curlen-offset-1+nextdiff);
        // 将新节点的长度设置到后一个节点之中
        if (forcelarge)
            // 如果满足我们前面计算nextdiff的所设定的不缩小条件则强行保留5个char来存储新节点的长度
            zipStorePrevEntryLengthLarge(p+reqlen,reqlen);
        else
            zipStorePrevEntryLength(p+reqlen,reqlen);

        // 设置zl头部中尾部元素偏移量
        ZIPLIST_TAIL_OFFSET(zl) =
            intrev32ifbe(intrev32ifbe(ZIPLIST_TAIL_OFFSET(zl))+reqlen);

        // 节约变量，直接使用tail作为节点
        zipEntry(p+reqlen, &tail);
        if (p[reqlen+tail.headersize+tail.len] != ZIP_END) {
            ZIPLIST_TAIL_OFFSET(zl) =
                intrev32ifbe(intrev32ifbe(ZIPLIST_TAIL_OFFSET(zl))+nextdiff);
        }
    } else {
        // 如果本身要插到尾部则元素偏移位置就是头部到插入位置p的
        ZIPLIST_TAIL_OFFSET(zl) = intrev32ifbe(p-zl);
    }

    // 如果下个节点的长度有所变化(因为存储当前节点的长度所占内存变化了)
    // 那意味着因为下个节点长度变化，下下个节点存储下个节点长度的内存也发生了变化又导致下下个节点的长度变化
    // 这改变是个蝴蝶效应，所以需要逐一遍历修改
    if (nextdiff != 0) {
        offset = p-zl;
        zl = __ziplistCascadeUpdate(zl,p+reqlen);
        p = zl+offset;
    }

    /* Write the entry */
    // 将前一个节点的长度存入该节点首部
    p += zipStorePrevEntryLength(p,prevlen);
    // 存储该节点数据编码方式和长度
    p += zipStoreEntryEncoding(p,encoding,slen);
    if (ZIP_IS_STR(encoding)) {
        // 如果是字符编码则直接拷贝
        memcpy(p,s,slen);
    } else {
        // 整型编码则存储对应整型
        zipSaveInteger(p,value,encoding);
    }
    // 将列表的长度加1
    ZIPLIST_INCR_LENGTH(zl,1);
    return zl;
}
```

虽然代码中已经有很多的注释，但还是简单解释一下，函数的功能是在指定的位置p插入一个新的entry，起始位置为p，数据的地址指针是s，原来位于p位置的数据项以及后面的所有数据项，需要统一向后偏移。该函数可以将数据插入到列表中的某个节点后，也可以插入到列表尾部。

1. 首先计算出待插入位置的前一个entry的长度prevlen，稍后要将这个值存入到新节点的**prevrawlen**属性中
2. 计算新的entry总共需要内存数，一个entry包含3个部分，所以这个内存数是这3部分的总和，当然也可能因为值小于13而变成没有data部分
3. 压缩列表有一个比较麻烦的地方就是每个节点都存储了前一个节点的长度，而且存储内存本身也是动态的，那么当新节点插入，它的下一个节点则要存储它的长度，这有可能引起下一个节点发生长度变化，因为可能原先下一个节点的**prevrawlen**仅需一个字符存储，结果新的节点的长度大于254了，那就需要5个字符来存储了，此时下一个节点的长度发生了变化，更可怕的是，由于下一个节点长度发生了变化，下下一个节点也面临着同样的问题，这就像是蝴蝶效应，一个小小的改动却带来惊天动地的变化， Redis称之为瀑布式改变，当然Redis也做了些许优化，当节点尝试变短时会根据某些条件仅可能避免这种大量改动的发生
4. 既然长度发生了变化则要申请新的内存空间并将原来的值拷贝过去，之后就是生成新的节点，并将其插入到列表中，设置新节点的各个属性值，当然还有对列表本身的长度和总内存等进行设置

### 2.2 压缩列表获取值
```ziplist```获取值的方法基本上就是插入的逆序，根据编码类型和值长度来算出具体值的位置并转换为相应结果。
``` C
/*
 * 获取p节点的实际数据的值并设置到sstr或sval中，如何设置取决于节点的编码类型
 *
 * 参数列表
 *      1. p: 指定的节点，该节点为列表尾或者指针无效时则告诉调用者获取节点值失败
 *      2. sstr: 出参字符串，如果该节点是以字符串形式编码的话则会设置该出参
 *      3. slen: 出参字符串长度
 *      4. sval: 出参整型，如果该节点是以整型编码(任何一种整型编码)则会设置该出参为节点实际数据值
 *
 * 返回值
 *      返回0代表指定的节点无效，返回1则代表节点有效并成功获取到其实际数据值
 */
unsigned int ziplistGet(unsigned char *p, unsigned char **sstr, unsigned int *slen, long long *sval) {
    zlentry entry;
    if (p == NULL || p[0] == ZIP_END) return 0;
    // 调用者是以sstr有没有被设置值来判断该节点是以整型编码还是字符串编码的
    // 为了防止出现歧义所以强制将sstr先指向空
    if (sstr) *sstr = NULL;

    // 将节点p的属性设置到工具结构体中，这样处理起来方便的多
    zipEntry(p, &entry);
    if (ZIP_IS_STR(entry.encoding)) {
        // 如果是以字符串编码则设置字符串出参
        if (sstr) {
            *slen = entry.len;
            *sstr = p+entry.headersize;
        }
    } else {
        if (sval) {
            // 取出实际的整型数据
            *sval = zipLoadInteger(p+entry.headersize,entry.encoding);
        }
    }
    return 1;
}
```
```ziplist```没有明确的定义，大多数操作都是通过宏定义的，获取值也不例外
``` C
/*
 * 设置压缩列表节点的属性值
 *
 * 参数列表
 *      1.p: 新节点内存的起始地址
 *      2.e: 一个节点结构体的指针
 */
void zipEntry(unsigned char *p, zlentry *e) {
    // 首先设置该节点第一个元素(存储前一个节点的长度)
    ZIP_DECODE_PREVLEN(p, e->prevrawlensize, e->prevrawlen);
    // 设置该节点的数据编码类型和数据长度
    ZIP_DECODE_LENGTH(p + e->prevrawlensize, e->encoding, e->lensize, e->len);
    // 记录节点头部总长度
    e->headersize = e->prevrawlensize + e->lensize;
    e->p = p;
}
```

## 三、快速链表quicklist
Redis暴露给用户使用的list数据类型（即```LPUSH```、```LRANGE```等系列命令），实现所用的内部数据结构就是```quicklist```，```quicklist```的实现是一个封装了```ziplist```的双向链表，既然和```adlist```一样就是个双向链表，那我们在已经了解```adlist```的情况下学习```quicklist```就会快很多，但是```quicklist```要比```adlist```复杂的多，原因在于额外的压缩和对```ziplist```的封装，首先我们来看下它是如何```ziplist```的，每一个```ziplist```都会被封装为一个```quicklistNode```，它的结构如下
``` C
/*
 * 快速列表的具体节点
 */
typedef struct quicklistNode {
    // 前一个节点
    struct quicklistNode *prev;
    // 后一个节点
    struct quicklistNode *next;
    // ziplist首部指针，各节点的实际数据项存储在ziplist中(连续内存空间的压缩列表)
    unsigned char *zl;
    // ziplist占用的总内存大小，不论压缩与否都是存储实际的总内存大小
    unsigned int sz;
    // ziplist的数据项的个数
    unsigned int count : 16;
    // 该节点是否被压缩过了，1代表没压缩，2代表使用LZF算法压缩过了
    // 可能以后会有别的压缩算法，目前则只有这一种压缩算法
    unsigned int encoding : 2;
    // 该节点使用何种方式来存储数据，1代表没存储数据，2代表使用ziplist存储数据
    // 这个节点目前看来都是2，即使用ziplist来存储数据，后续可能会有别的方式
    unsigned int container : 2;
    // 这个节点是否需要重新压缩？
    // 某些情况下需要临时解压下这个节点，有这个标记则会找机会再重新进行压缩
    unsigned int recompress : 1;
    // 节点数据不能压缩？
    unsigned int attempted_compress : 1;
    // 只是一个int正好剩下的内存，目前还没使用上，可以认为是扩展字段
    unsigned int extra : 10;
} quicklistNode;
```
可以清楚到看到快速链表的节点（```quicklistNode```）主要是对```ziplist```封装，复杂的地方在于控制各个```ziplist```的长度和压缩情况，从结构设计上可以看到Redis可能还打算使用别的结构代替```ziplist```作为存储实际数据的节点，但目前在4.0版本中仅有```ziplist```这一种，压缩算法也只有```lzf```。

### 3.1 创建快速链表
当用户执行```LPUSH```命令时，如果指定的列表名称在Redis不存在则会创建一个新的快速链表，代码调用路径大致如下
```
server.c 事件循环 --> 调用module API --> module.c moduleCreateEmptyKey() --> object.c createQuicklistObject() --> quicklist.c quicklistCreate()
```
主要判断逻辑在```module.c```中
``` C
/*
 * LPUSH命令的实现
 * 将元素加入到一个Redis List集合中(快速链表quicklist)，如果该key的List不存在则会创建一个List
 * 当key存在确不是List类型时则会抛出类型不符合错误
 *
 */
int RM_ListPush(RedisModuleKey *key, int where, RedisModuleString *ele) {
    // 如果对应的key是只读的则会返回键值不可写错误
    if (!(key->mode & REDISMODULE_WRITE)) return REDISMODULE_ERR;
    // 如果存在key但是类型不是List则会返回类型不符合错误
    if (key->value && key->value->type != OBJ_LIST) return REDISMODULE_ERR;
    // 如果指定key不存在则创建一个quicklist类型的对象
    if (key->value == NULL) moduleCreateEmptyKey(key,REDISMODULE_KEYTYPE_LIST);
    // 将具体的值存入List值
    listTypePush(key->value, ele,
        (where == REDISMODULE_LIST_HEAD) ? QUICKLIST_HEAD : QUICKLIST_TAIL);
    return REDISMODULE_OK;
}

```
之后就是调用quicklist.c中的方法来创建一个快速链表
``` C
/*
 * 创建一个快速链表
 * 当使用LPUSH创建List时会调用该函数
 *
 * 返回值
 *      新的快速链表的指针
 */
quicklist *quicklistCreate(void) {
    struct quicklist *quicklist;

    quicklist = zmalloc(sizeof(*quicklist));
    quicklist->head = quicklist->tail = NULL;
    quicklist->len = 0;
    quicklist->count = 0;
    quicklist->compress = 0;
    // -2代表ziplist的大小不超过8kb
    quicklist->fill = -2;
    return quicklist;
}
```

### 3.2 快速链表插入值
插入值的方式有很多种，比如从插入到头部、插入到尾部、插入到某个节点前面、从其他ziplist导入等等，但原理都差不多，我们这里仅看插入到头部即可
``` C
/*
   * 在链表的首部添加一个节点
   *
   * 参数列表
   *      1. quicklist: 待操作的快速链表
   *      2. value: 待插入的值
   *      3. sz: 值的内存长度
   *
   * 返回值
   *      返回1代表创建了一个新的节点，返回0代表使用了既有的节点
   */
  int quicklistPushHead(quicklist *quicklist, void *value, size_t sz) {
      quicklistNode *orig_head = quicklist->head;
      // likely是条件大概率为真时的语法优化写法
      // 首先需要判断当前快速链表节点是否能够再添加值
      if (likely(
              _quicklistNodeAllowInsert(quicklist->head, quicklist->fill, sz))) {
          // 能的话则将值插入到当前节点对应的ziplist中即可
          quicklist->head->zl =
              ziplistPush(quicklist->head->zl, value, sz, ZIPLIST_HEAD);
          quicklistNodeUpdateSz(quicklist->head);
      } else {
          // 不能则创建一个新的快速链表节点并将值插入
          quicklistNode *node = quicklistCreateNode();
          node->zl = ziplistPush(ziplistNew(), value, sz, ZIPLIST_HEAD);

          quicklistNodeUpdateSz(node);
          _quicklistInsertNodeBefore(quicklist, quicklist->head, node);
      }
      quicklist->count++;
      quicklist->head->count++;
      return (orig_head != quicklist->head);
  }
```

### 3.3 从快速链表中获取值
获取值最麻烦的地方在于需要解压```ziplist```，目前Redis使用的是```lzf```压缩算法（也可以说是个编码算法），要注意的是```quicklist```中的获取值都是指获取真实的数据项的值，也就是存储在各个```ziplist```中的数据项，而不是指```quicklistNode```。
``` C
/*
 * 获取指定位置的节点
 *
 * 参数列表
 *      1. quicklist: 待操作的链表
 *      2. idx: 节点位置序号，大于0表示从链表头开始索引，小于代表从链表尾部开始索引
 *              注意这个序号是所有ziplist的所有节点的序号，不是quicklist节点的序号
 *      3. entry: 出参，如果找到节点则将节点的属性设置到该entry中
 *
 * 返回值
 *      返回1代表成功找到指定位置节点，否则返回0
 */
int quicklistIndex(const quicklist *quicklist, const long long idx,
                   quicklistEntry *entry) {
    quicklistNode *n;
    unsigned long long accum = 0;
    unsigned long long index;
    // 小于0从后往前搜索
    int forward = idx < 0 ? 0 : 1; /* < 0 -> reverse, 0+ -> forward */

    // 这里会对entry设置一些初始值，所以必须通过该函数返回值判断获取成功失败
    // 而不能通过entry是否设置来判断
    initEntry(entry);
    entry->quicklist = quicklist;

    if (!forward) {
        // 从尾部开始遍历-1代表第1个节点(位置0),-2代表第二个节点(位置1)
        index = (-idx) - 1;
        n = quicklist->tail;
    } else {
        index = idx;
        n = quicklist->head;
    }

    // 如果指定位置超出了链表本身长度
    if (index >= quicklist->count)
        return 0;

    // 编译器和linux系统的一种优化语法糖
    // 当条件为真的可能性很大时使用该写法可以提高执行效率
    while (likely(n)) {
        // 这个循环只能算出想要的节点在哪个ziplist中，后续再从ziplist取出真正节点
        if ((accum + n->count) > index) {
            break;
        } else {
            D("Skipping over (%p) %u at accum %lld", (void *)n, n->count,
              accum);
            // 每个快速列表的节点都记录了它附带的ziplist中的节点个数
            accum += n->count;
            n = forward ? n->next : n->prev;
        }
    }
    // 如果没有找到指定节点则返回失败
    if (!n)
        return 0;
    // 调试日志
    D("Found node: %p at accum %llu, idx %llu, sub+ %llu, sub- %llu", (void *)n,
      accum, index, index - accum, (-index) - 1 + accum);
    entry->node = n;
    // 设置在当前ziplist中还要偏移多少个位置才是真正的数据节点
    if (forward) {
        entry->offset = index - accum;
    } else {
        entry->offset = (-index) - 1 + accum;
    }

    // 解压当前节点的ziplist，由于是将该节点给调用者使用，所以解压之后不再重新压缩
    // 由调用者根据重压缩标志决定是否需要再压缩
    quicklistDecompressNodeForUse(entry->node);
    // 获取实际的数据节点首部指针
    entry->zi = ziplistIndex(entry->node->zl, entry->offset);
    // 到此已找到数据节点，现把数据节点中的实际数据取出并根据编码类型设置不同属性
    // 值得注意的是调用者通过entry的value属性是否有值来判断实际数据是否是字符串编码
    ziplistGet(entry->zi, &entry->value, &entry->sz, &entry->longval);
    return 1;
}
```
我们看到最终的出参是```quicklistEntry```，这是一个工具型结构体，主要用于中间过渡和方便程序调用，在```ziplist```的实现中也有类似的工具型结构体，```quicklistEntry```的定义如下
``` C
// 快速列表节点表示的工具型结构体
// 和ziplist的zlenty类似，一切为了操作方便
typedef struct quicklistEntry {
    // 快速链表
    const quicklist *quicklist;
    // 对应的节点
    quicklistNode *node;
    // 在ziplist中的实际的数据节点的首部指针
    unsigned char *zi;
    // 如果实际数据是字符串编码类型则值设置在该属性中
    unsigned char *value;
    // 如果实际数据是整型编码类型则值设置在该属性中
    long long longval;
    // 不同使用场景下表示意义稍有不同
    // 获取指定节点实际数据值时表示字符串编码情况下字符串的长度
    unsigned int sz;
    int offset;
} quicklistEntry;
```
我们经常使用的```LRANGE```命令则是通过链表的迭代器来实现的，其实```adlist```和```ziplist```都是有迭代器的，通过迭代器可以从指定位置开始逐个遍历链表中的值，非常方便且安全。
```LRANGE```的主要调用流程如下
```
server.c 事件循环 --> 命令表 lrangeCommand命令 --> t_list.c lrangeCommand() --> quicklist.c quicklistGetIteratorAtIdx() --> quicklist.c quicklistNext()
```
初始化迭代器的过程很简单
``` C
/*
 * 创建一个从链表指定位置开始的迭代器
 *
 * 参数列表
 *      1. quicklist: 待操作的链表
 *      2. direction: 迭代方向
 *      3. idx: 从哪个位置开始
 *
 * 返回值
 *      链表迭代器，是链表迭代函数的入参
 */
quicklistIter *quicklistGetIteratorAtIdx(const quicklist *quicklist,
                                         const int direction,
                                         const long long idx) {
    quicklistEntry entry;

    if (quicklistIndex(quicklist, idx, &entry)) {
        quicklistIter *base = quicklistGetIterator(quicklist, direction);
        base->zi = NULL;
        base->current = entry.node;
        base->offset = entry.offset;
        return base;
    } else {
        return NULL;
    }
}
```
获取到一个迭代器的指针之后，就可以将其作为参数传递给```quicklistNext```方法逐个遍历值
``` C
/*
 * 获取快速链表的下一个节点
 *
 * 参数列表
 *      1. iter: 链表迭代器，可以通过quicklistGetIterator()函数获得
 *      2. entry: 出参，如果获取到下一个节点则设置属性到该工具型结构体中
 *
 * 返回值
 *
 */
int quicklistNext(quicklistIter *iter, quicklistEntry *entry) {
    // 重置出参entry的属性值
    initEntry(entry);

    // 如果迭代器无效则返回
    if (!iter) {
        D("Returning because no iter!");
        return 0;
    }

    // 当前遍历的链表是肯定不变的
    entry->quicklist = iter->quicklist;
    // 当前遍历的快速链表节点也大概率不会改变
    entry->node = iter->current;

    // 当前已遍历完毕
    if (!iter->current) {
        D("Returning because current node is NULL")
        return 0;
    }

    unsigned char *(*nextFn)(unsigned char *, unsigned char *) = NULL;
    int offset_update = 0;

    if (!iter->zi) {
        // 如果没有还未获取到ziplist的具体数据节点则使用偏移址获取
        // 发生在两个快速链表节点切换时，也就是换到下一个ziplist时
        /* If !zi, use current index. */
        // 首先需要将新的ziplist解压
        quicklistDecompressNodeForUse(iter->current);
        // 之后获取到到指定真实数据节点
        iter->zi = ziplistIndex(iter->current->zl, iter->offset);
    } else {
        /* else, use existing iterator offset and get prev/next as necessary. */
        // 如果没有切换ziplist那就在现有的ziplist中通过ziplist节点特性寻找下一个数据节点
        // ziplist中的节点记录了上一个节点的长度和当前节点的长度所以既可以往前遍历也可以往后遍历
        if (iter->direction == AL_START_HEAD) {
            nextFn = ziplistNext;
            offset_update = 1;
        } else if (iter->direction == AL_START_TAIL) {
            nextFn = ziplistPrev;
            offset_update = -1;
        }
        iter->zi = nextFn(iter->current->zl, iter->zi);
        iter->offset += offset_update;
    }

    entry->zi = iter->zi;
    entry->offset = iter->offset;

    if (iter->zi) {
        /* Populate value from existing ziplist position */
        // 如果当前ziplist有效(还有数据)则直接取当前ziplist下一个值即可
        ziplistGet(entry->zi, &entry->value, &entry->sz, &entry->longval);
        return 1;
    } else {
        /* We ran out of ziplist entries.
         * Pick next node, update offset, then re-run retrieval. */
        // 当前ziplist无效(其数据节点已遍历完)则获取下一个quicklistNode中的ziplist
        quicklistCompress(iter->quicklist, iter->current);
        if (iter->direction == AL_START_HEAD) {
            // 从前往后遍历
            D("Jumping to start of next node");
            // 获取下一个quicklistNode并将迭代器指向的当前ziplist置空
            iter->current = iter->current->next;
            iter->offset = 0;
        } else if (iter->direction == AL_START_TAIL) {
            // 从后往前遍历
            D("Jumping to end of previous node");
            iter->current = iter->current->prev;
            iter->offset = -1;
        }
        // 将迭代器当前有效的ziplist置空以便递归调用时知道是要重新从quicklistNode中取出ziplist
        iter->zi = NULL;
        return quicklistNext(iter, entry);
    }
}
```

快速链表获取值的方式还有从尾部弹出、从首部弹出等，其核心思想都是先找到指定的```ziplist```并将其中的真实数据解压出来返回。

### 小结
双向链表很好理解，压缩列表则比较繁琐，希望对大家读Redis4.0源码有所帮助，我觉得重要的还是自己去看和调试，当然如果源码中带有中文注释看着肯定事半功倍，所以大家可以**clone**文章顶部的仓库，随时更新。

线性表list是Redis中非常重要的数据结构，不论是Reids内部还是暴露给客户的数据结构中都有使用到，和Redis的动态字符串一样，这几种list可以单独使用，将其源文件拷贝以及依赖的几个源文件拷贝出来就可以非常的方便的再自己的项目中直接使用（使用时记得查看开源协议规范）。