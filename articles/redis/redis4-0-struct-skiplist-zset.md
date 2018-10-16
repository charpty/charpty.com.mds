> 笔者博客地址： https://charpty.com


为了大家看整体源码方便，我将加上了完整注释的代码传到了我的github上供大家直接下载：
> https://github.com/charpty/redis4.0-source-reading


在```Redis```中提供了有序集合，从它的命令之多就可以知道它的功能是比较强大的，当然实现也是比较复杂的，```ZSET```底层使用跳表```SKIP LIST```实现，在Java中也有跳表主要用于实现并发访问。

-

### 跳表
虽然这不是我们的主题，但是你需要有一些跳表这种常用数据结构有一定的认识，否则很难理解后面的排序输出，范围查找等功能。

跳表本质上是一种查询结构，它解决的问题是能够更加快速的查询到想找的元素，相对与红黑树和其他平衡树查找与插入的逻辑，跳表是非常好上手的。

借助跳表结构提出者```William Pugh```给的一张图，可以生动形象表示跳表的基本思想。  

![跳表图](/images/redis/struct/skiplist-1-william-pugh.png)

比如咱们要查找数字16，当然没有，但咱看看要查几次才知道没有呢。

先看第a行，这就是一个普通的list，单向链表，想查找一个元素16，要沿着列表走6步，```3 -> 6 -> 7 -> 9 -> 12 -> 17```，才知道没有。

到了第b行，我们加了一层，将相隔2步的元素提到上一层，查元素的时候，我们先从高层查起，只需要4步，```6 -> 9 -> 17 -> 12```，每次查询跨的步子都大了，第一步就查了6，此时我们知道6左下层的元素不需要查了，每次跨的步子大了，查询的次数自然也就少了。

每层的元素个数都是下一层的一半，每多一层元素减少50%，相当于二分查找法，相比列表查找元素的时间复杂度从```O(n)```降低到```O(log n)```。  

跳表能否提升查询性能在于分层，过多的层会导致空间损失和插入性能损失，每一层能够跨的元素越多越好，那如何把哪几个元素提高一层能提供查询性能呢？很难衡量，二层来说可以通过计算元素间距离来得到，但是三层四层呢，这一层的结果影响下一层的提层，这层分的好可能导致下一层分的不好，反之亦然。
而且根据固定位置分层会导致每次插入元素都可能导致各元素层高变化，代价很高。

所以在```William Pugh```使用的一种随机层数策略，每一个元素插进来时，它的层数是随机生成的，这是跳表很重要的特性。那随机的性能如何呢？在原论文中有一章节```Analysis of expected search cost```专门讲随机层数模式下查询性能的问题。

查询的过程比较简单想必大家已经很清楚，作者用一段伪代码表示了插入的逻辑


```

-- 和lua语法注释一样
Insert(list, searchKey, newValue)
   -- Redis中的代码实现以及变量命名都和此很像
   -- update存储的是各个层级上新插入元素位置的前一个位置
	local update[1..MaxLevel]
	x := list→header
	-- 遍历每一层直到找到新元素的位置，并记录该位置的前一个元素
	for i := list→level downto 1 do
		while x→forward[i]→key < searchKey do
			x := x→forward[i]
		-- x→key < searchKey ≤ x→forward[i]→key
		update[i] := x
	x := x→forward[1]
	-- 存在相同key（相同排序依据分数）则替换那个位置，不允许有相同分数的元素
	if x→key = searchKey then x→value := newValue
	else
		lvl := randomLevel()
		if lvl > list→level then
			-- 如果出现新层级高于目前最高层级的情况
			for i := list→level + 1 to lvl do
				update[i] := list→header
			list→level := lvl
		x := makeNode(lvl, searchKey, value)
		-- 把元素插进到每一层（它指向前节点的下一个节点，再将前节点改为指向它）
		for i := 1 to level do
			x→forward[i] := update[i]→forward[i]
			update[i]→forward[i] := x
```

当然看一遍不可能理解的很透彻，但是大概有个概念，不要影响后续对有序集合的分析即可。

### Redis中的zskiplist
大多数对跳跃表的实现都会根据场景进行修改，Redis根据要支撑的有序集合```ZSET```的特性，对跳跃表进行一下节点修改。  

在```Redis```中用zskiplist和zskiplistNode分别表示跳表和跳表节点

```
/*
 * 跳表的具体节点
 */
typedef struct zskiplistNode {
    // 实际元素数据对应字符串，在存入跳表前会被编码为字符串
    // Redis还会将此ele作为key,分数存储在字典中方便统计
    sds ele;
    // 排序依据, 允许多个同分数不同元素存在
    double score;
    // 后节点指针，Redis的跳表第一层是一个双向链表
    struct zskiplistNode *backward;
    // 表示一个节点共有多少层, 是一个柔性数组，需要在创建节点时根据层高具体分配
    struct zskiplistLevel {
        // 前节点指针
        struct zskiplistNode *forward;                                                                                                                        
        // 该层一次元素跳跃一共跳过多少个第一层元素, 用于统计排名
        unsigned int span;
    } level[];
} zskiplistNode;

/*
 * Redis使用的跳表, 是有序集合zset的底层实现
 */
typedef struct zskiplist {
    // 头尾节点
    struct zskiplistNode *header, *tail;
    // 跳表共有元素个数
    unsigned long length;
    // 跳表目前最高的层数
    int level;
} zskiplist;

```

根据结构体```zskiplistNode```可以较好的理解```Redis```中跳表的实现，和标准跳跃表实现有几个小的区别。

1. 排序依据分数允许重复，相同分数根据元素数据ele字符串自然排序，但元素值不可重复
2. 第0层是一个双向链表，和列表一样，方便倒序取数据
3. 增加了统计类属性，方便排名与计数


### Redis中的跳表操作

对跳表本身无非是增删改查，我们就看一下插入即可，因为它包含了查找，插入的逻辑和前面标准跳表的伪代码几乎一致，只是细节上有区分，这样我们也可以对比下```Redis```跳表和标准跳表区别。

```
/*
* 将元素插入到跳表中
*
* 参数列表
*      1. zsl: 跳表结构体
*      2. score: 插入元素的分数
*      3. ele: 插入元素的实际数据
*
* 返回值
*      插入元素的对应节点
*/
zskiplistNode *zslInsert(zskiplist *zsl, double score, sds ele) {                                                                                                                                                                                                                                                                                                                                                                                                                         
  // 和标准跳表一样使用update数组记录每层待插入位置所在前一个元素
  zskiplistNode *update[ZSKIPLIST_MAXLEVEL], *x;
  // 记录前置节点与第一个节点之间的跨度,即元素在列表中的排名-1
  // 跨度指的都是跨过第0层多少个元素
  unsigned int rank[ZSKIPLIST_MAXLEVEL];
  int i, level;
   
  serverAssert(!isnan(score));
  x = zsl->header;
  // 从最高层开始遍历, 从粗到细，找到每一层待插入的位置
  for (i = zsl->level-1; i >= 0; i--) {
      /* store rank that is crossed to reach the insert position */
      rank[i] = i == (zsl->level-1) ? 0 : rank[i+1];
      // 直到找到第一个分数比该元素大的位置
      // 或者分数与该元素相同但数据字符串比该元素大的位置
      while (x->level[i].forward &&
              (x->level[i].forward->score < score ||
                  (x->level[i].forward->score == score &&
                  sdscmp(x->level[i].forward->ele,ele) < 0))) 
      {
          // 将已走过元素跨越元素进行计数，得出元素在列表中的排名
          // 也可以认为已搜寻的路径长度
          rank[i] += x->level[i].span;
          x = x->level[i].forward;
      }
      // 记录待插入位置
      update[i] = x; 
  }    
  // 随机产生一个层数，在1与MAXLEVEL之间，层数越高生成概率越低
  level = zslRandomLevel();
  if (level > zsl->level) {
      // 如果产生的层数大于现有最高层数，则超出层数都需要初始化
      for (i = zsl->level; i < level; i++) {
          rank[i] = 0; 
          // 该元素作为这些层的第一个节点，前节点就是header
          update[i] = zsl->header;
          // 初始化后这些层每层共两个元素, 走一步就是跨越所有元素
          update[i]->level[i].span = zsl->length;
      }
      zsl->level = level;
  }    
  // 创建节点，根据层高分配柔性数组内存
  x = zslCreateNode(level,score,ele);
  for (i = 0; i < level; i++) {
      // 将新节点插入到各层链表中
      x->level[i].forward = update[i]->level[i].forward;
      update[i]->level[i].forward = x; 
   
      // rank[0]是第0层的前置节点P1（也就是底层插入节点前面那个节点）与第一个节点的跨度
      // rank[i]是第i层的前置节点P2（这一层里在插入节点前面那个节点）与第一个节点的跨度
      // 插入节点X与后置节点Y的跨度f(X,Y)可由以下公式计算
      // 关键在于f(P1,0)-f(P2,0)+1等于新节点与P2的跨度，这是因为跨度呈梯子形向下延伸到最底层
      // 记录节点各层跨越元素情况span, 由层与层之间的跨越元素总和rank相减而得
      x->level[i].span = update[i]->level[i].span - (rank[0] - rank[i]);
      // 插入位置前一个节点的span在原基础上加1即可(新节点在rank[0]的后一个位置)
      update[i]->level[i].span = (rank[0] - rank[i]) + 1; 
  }    
   
  // header是个起始
  for (i = level; i < zsl->level; i++) {
      update[i]->level[i].span++;
  }    
   
!     // 第0层是双向链表, 便于redis常支持逆序类查找
  x->backward = (update[0] == zsl->header) ? NULL : update[0];
  if (x->level[0].forward)
      x->level[0].forward->backward = x; 
  else 
      zsl->tail = x; 
  zsl->length++;
  return x;
}

```

大家可以看到跳表的元素定位、插入都还是比较繁琐的，如果少量数据就使用跳表是得不偿失的。

### Redis中的ZSET实现
在```Redis```中有序集合的实现，不完全是使用跳表，在数据量少的情况下（128以下），```Redis```会使用压缩链表```ziplist```来实现，当数据量超过阈值才会使用跳表，```ziplist```相关的代码比较简单，仅一笔带过，接下来讨论跳表模式下的场景。

某些情况下，如获取某个元素的分数、求集合并集等情况，需要元素值与其分数的对应关系，简单的做法当然遍历一下跳表，找到这个元素node，自然得到它的分数。  
但```Redis```为了提高效率，直接将元素数据ele和其分数score的对应关系存在了哈希表中，便于快速查询，比如```ZSCORE```命令的实现概要如下：

```
/*                                                                                                                                     
* 获取指定元素的分数                                                                                                                  
*/                                                                                                                                    
int zsetScore(robj *zobj, sds member, double *score) {                                                                                 
  if (!zobj || !member) return C_ERR;                                                                                                
                                                                                                                                     
  // ziplist模式下直接找到该元素并设置分数结果                                                                                       
  if (zobj->encoding == OBJ_ENCODING_ZIPLIST) {                                                                                      
      if (zzlFind(zobj->ptr, member, score) == NULL) return C_ERR;                                                                   
  } else if (zobj->encoding == OBJ_ENCODING_SKIPLIST) {                                                                              
      zset *zs = zobj->ptr;                                                                                                          
      // 根据元素数据ele直接找到分数                                                                                                 
      dictEntry *de = dictFind(zs->dict, member);                                                                                    
      if (de == NULL) return C_ERR;                                                                                                  
      *score = *(double*)dictGetVal(de);                                                                                             
  } else {                                                                                                                           
      serverPanic("Unknown sorted set encoding");                                                                                    
  }                                                                                                                                  
  return C_OK;                                                                                                                       
}       
```
通过冗余一个哈希表，使得查找元素分数非常方便。

通过```ZSCORE```命令可以理解到```Redis```有序集合的实现概要，通过最常用的```ZRANGE```命令则可以理解元素的查找过程。 

```
/*
 * 获取指定范围的元素
 */
void zrangeGenericCommand(client *c, int reverse) {
    robj *key = c->argv[1];
    robj *zobj;
    // 是否同时展示元素的分数
    int withscores = 0;
    // 从哪个位置到哪个位置，尾可以负数表示倒数第几个
    long start;
    long end;
    int llen;
    int rangelen;

    ...获取传递的参数并赋值给本地变量

    // 没有这个zset或者key对应元素类型不是zset
    if ((zobj = lookupKeyReadOrReply(c,key,shared.emptymultibulk)) == NULL
         || checkType(c,zobj,OBJ_ZSET)) return;

    llen = zsetLength(zobj);
    if (start < 0) start = llen+start;
    if (end < 0) end = llen+end;
    // 转了一圈以上了，就认为从头开始
    if (start < 0) start = 0;

    // 严谨的index range check
    if (start > end || start >= llen) {
        addReply(c,shared.emptymultibulk);
        return;
    }
    if (end >= llen) end = llen-1;
    // 一个要输出多少个元素
    rangelen = (end-start)+1;

    addReplyMultiBulkLen(c, withscores ? (rangelen*2) : rangelen);

    // 在元素较少时，zset底层使用ziplist实现，之前已解析过ziplist，此场景可认为是普通链表
    if (zobj->encoding == OBJ_ENCODING_ZIPLIST) {
        unsigned char *zl = zobj->ptr;
        unsigned char *eptr, *sptr;
        unsigned char *vstr;
        unsigned int vlen;
        long long vlong;

        // 移动到指定下标位置，准备开始遍历
        if (reverse)
            eptr = ziplistIndex(zl,-2-(2*start));
        else
            eptr = ziplistIndex(zl,2*start);

        serverAssertWithInfo(c,zobj,eptr != NULL);
        sptr = ziplistNext(zl,eptr);

        // 一个个遍历，共遍历rangelen个元素输出即可
        while (rangelen--) {
            ...遍历输出
        }

    } else if (zobj->encoding == OBJ_ENCODING_SKIPLIST) {
        // 当元素到达一定数量才使用跳表, 默认域值为OBJ_ZSET_MAX_ZIPLIST_ENTRIES=128
        zset *zs = zobj->ptr;
        zskiplist *zsl = zs->zsl;
        zskiplistNode *ln;
        sds ele;

        if (reverse) {
            ln = zsl->tail;
            // start==0时就是从头或尾开始查找
            if (start > 0)
                ln = zslGetElementByRank(zsl,llen-start);
        } else {
            ln = zsl->header->level[0].forward;
            // 根据跨度span计数来找到排名为start+1的节点
            if (start > 0)
                ln = zslGetElementByRank(zsl,start+1);
        }

        // 从起始位置开始输出rangelen个节点
        while(rangelen--) {
            serverAssertWithInfo(c,zobj,ln != NULL);
            ele = ln->ele;
            addReplyBulkCBuffer(c,ele,sdslen(ele));
            if (withscores)
                addReplyDouble(c,ln->score);
            ln = reverse ? ln->backward : ln->level[0].forward;
        }
    } else {
        serverPanic("Unknown sorted set encoding");
    }
}

```

看完```Redis```的有序集合实现，当时我也有个疑惑，为什么不用平衡树实现（也疑惑```Redis```的哈希表在哈希冲突时为什么不用树实现D--），以下我自己的理解。

1. 跳表实现起来简单，这个很重要，也和Redis的宗旨符合，且性能相当
2. 跳表更适合范围查找

在实际环境中，使用```ZSET```完成排行榜模块是非常常见的，点赞量、阅读数量、播放量等等，它可以多维度满足排行需求且操作简单。

-
好啦，讲完，希望对你有所帮助。



