## Redis跳表与有序集合实现

在```Redis```中提供了有序集合，从它的命令之多就可以知道它的功能是比较强大的，当然实现也是比较复杂的，```ZSET```底层使用跳表```SKIP LIST```实现，在Java中也有跳表主要用于实现并发访问。

--

### 跳表
虽然这不是我们的主题，但是你需要有一些跳表这种常用数据结构有一定的认识，否则很难理解后面的排序输出，范围查找等功能。

跳表本质上是一种查询结构，它解决的问题是能够更加快速的查询到想找的元素，相对与红黑树和其他平衡树查找与插入的逻辑，跳表是非常好上手的。

借助跳表结构提出者```William Pugh```给的一张图，可以生动形象表示跳表的基本思想

[跳表图](/images/redis/struct/skiplist-1-william-pugh.png)

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
			-- 如果产生了高于目前已有最高层的情况
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

// TODO 总结

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

