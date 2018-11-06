最近想切到```redis cluster```上去，第一次接触```redis cluster```是在16年做一个内网应用的时候，给我的第一印象是不那么靠谱，时刻近3年，```redis cluster```已经有了很大的改变。


--

Redis Cluster Specification
===

Welcome to the **Redis Cluster Specification**. Here you'll find information
about algorithms and design rationales of Redis Cluster. This document is a work
in progress as it is continuously synchronized with the actual implementation
of Redis.


欢迎查看Redis集群规范。本文描述了Redis集群的设计理念和算法。由于实际实现的代码不停在变化，本文也会随之更新。

Main properties and rationales of the design
===

Redis Cluster goals
---

Redis Cluster is a distributed implementation of Redis with the following goals, in order of importance in the design:

* High performance and linear scalability up to 1000 nodes. There are no proxies, asynchronous replication is used, and no merge operations are performed on values.
* Acceptable degree of write safety: the system tries (in a best-effort way) to retain all the writes originating from clients connected with the majority of the master nodes. Usually there are small windows where acknowledged writes can be lost. Windows to lose acknowledged writes are larger when clients are in a minority partition.
* Availability: Redis Cluster is able to survive partitions where the majority of the master nodes are reachable and there is at least one reachable slave for every master node that is no longer reachable. Moreover using *replicas migration*, masters no longer replicated by any slave will receive one from a master which is covered by multiple slaves.

What is described in this document is implemented in Redis 3.0 or greater.

Redis集群设计主要原理
===

Redis集群设计目标
---

Redis集群是一个分布式系统，设计时期望达到以下几个目标（按重要性排序）

* 高性能和线性扩展，Redis集群能支持1000个节点以下性能线性扩展（几乎）。集群使用异步复制方法保持同步，节点不为其它节点提供代理服务，没有对冲突键的值合并操作。
* 可接受的最低写安全：集群尽最大努力保留对master节点的写操作。那些与大多数节点相连的客户端实现的写操作会被尽量保存，但是还是会有一个时间窗口导致数据丢失。反之如果客户端只连接了少数客户端则比较容易丢失数据。
* 可用性：集群在大多数master节点可用且至少带有一个slave情况下可正常工作并保持高可用，master节点之间会尽可能平衡slave个数。

本文描述的是Redis最新的集群实现策略。

Implemented subset
---

Redis Cluster implements all the single key commands available in the
non-distributed version of Redis. Commands performing complex multi-key
operations like Set type unions or intersections are implemented as well
as long as the keys all belong to the same node.

Redis Cluster implements a concept called **hash tags** that can be used
in order to force certain keys to be stored in the same node. However during
manual reshardings, multi-key operations may become unavailable for some time
while single key operations are always available.

Redis Cluster does not support multiple databases like the stand alone version
of Redis. There is just database 0 and the `SELECT` command is not allowed.

实现的功能
---

Redis集群实现了单机模式下对单key操作的所有命令。其他同时对多个key进行操作的命令在被操作的keys落在同一个节点的情况下也能正确执行，比如求并集、交集。


Redis集群实现了一个被称为**hash tags**（哈希标签）的策略，它使得某个key总是落在同一个节点上。不论是否发生集群迁移，单key操作总是能正确执行，而多key操作则可能会失败。


Clients and Servers roles in the Redis Cluster protocol
---

In Redis Cluster nodes are responsible for holding the data,
and taking the state of the cluster, including mapping keys to the right nodes.
Cluster nodes are also able to auto-discover other nodes, detect non-working
nodes, and promote slave nodes to master when needed in order
to continue to operate when a failure occurs.

To perform their tasks all the cluster nodes are connected using a
TCP bus and a binary protocol, called the **Redis Cluster Bus**.
Every node is connected to every other node in the cluster using the cluster
bus. Nodes use a gossip protocol to propagate information about the cluster
in order to discover new nodes, to send ping packets to make sure all the
other nodes are working properly, and to send cluster messages needed to
signal specific conditions. The cluster bus is also used in order to
propagate Pub/Sub messages across the cluster and to orchestrate manual
failovers when requested by users (manual failovers are failovers which
are not initiated by the Redis Cluster failure detector, but by the
system administrator directly).

Since cluster nodes are not able to proxy requests, clients may be redirected
to other nodes using redirection errors `-MOVED` and `-ASK`.
The client is in theory free to send requests to all the nodes in the cluster,
getting redirected if needed, so the client is not required to hold the
state of the cluster. However clients that are able to cache the map between
keys and nodes can improve the performance in a sensible way.

在集群协议中客户端与服务器的角色
---

在Redis集群中，所有节点都要负责存储数据、存储集群状态信息（key与节点映射关系）。节点也具备自动检测其他节点存活情况的能力。发现master节点失活后，提升其对应slave节点为master节点来继续对外提供服务。

为了能完成上述工作，所有节点都通过TCP连接，通过一个二进制协议通信，称之为**Redis Cluster Bus**（Redis集群总线）。节点与节点之间都通过集群总线相连，节点之间使用gossip协议来传播信息，以便能够发现新节点，发送心跳消息确定其他节点可用，以及传播其他集群特定消息。集群总线同时也用于传播集群版本的发布/订阅消息，也用于传播由管理手动发起的故障转移命令。

由于节点无法代理其它节点，客户端的请求可能会被重定向，通过返回`-MOVED` 和 `-ASK`告知客户端数据在其它节点上。理论上来说客户端可以向集群中任意节点发送消息，通过重定向最终都会知道数据落在哪个节点，客户端不强制记录集群的节点信息和槽分布情况，但是如果记录了在请求数据时能提供性能。


Write safety
---

Redis Cluster uses asynchronous replication between nodes, and **last failover wins** implicit merge function. This means that the last elected master dataset eventually replaces all the other replicas. There is always a window of time when it is possible to lose writes during partitions. However these windows are very different in the case of a client that is connected to the majority of masters, and a client that is connected to the minority of masters.

Redis Cluster tries harder to retain writes that are performed by clients connected to the majority of masters, compared to writes performed in the minority side.
The following are examples of scenarios that lead to loss of acknowledged
writes received in the majority partitions during failures:

1. A write may reach a master, but while the master may be able to reply to the client, the write may not be propagated to slaves via the asynchronous replication used between master and slave nodes. If the master dies without the write reaching the slaves, the write is lost forever if the master is unreachable for a long enough period that one of its slaves is promoted. This is usually hard to observe in the case of a total, sudden failure of a master node since masters try to reply to clients (with the acknowledge of the write) and slaves (propagating the write) at about the same time. However it is a real world failure mode.

2. Another theoretically possible failure mode where writes are lost is the following:

* A master is unreachable because of a partition.
* It gets failed over by one of its slaves.
* After some time it may be reachable again.
* A client with an out-of-date routing table may write to the old master before it is converted into a slave (of the new master) by the cluster.

The second failure mode is unlikely to happen because master nodes unable to communicate with the majority of the other masters for enough time to be failed over will no longer accept writes, and when the partition is fixed writes are still refused for a small amount of time to allow other nodes to inform about configuration changes. This failure mode also requires that the client's routing table has not yet been updated.

Writes targeting the minority side of a partition have a larger window in which to get lost. For example, Redis Cluster loses a non-trivial number of writes on partitions where there is a minority of masters and at least one or more clients, since all the writes sent to the masters may potentially get lost if the masters are failed over in the majority side.

Specifically, for a master to be failed over it must be unreachable by the majority of masters for at least `NODE_TIMEOUT`, so if the partition is fixed before that time, no writes are lost. When the partition lasts for more than `NODE_TIMEOUT`, all the writes performed in the minority side up to that point may be lost. However the minority side of a Redis Cluster will start refusing writes as soon as `NODE_TIMEOUT` time has elapsed without contact with the majority, so there is a maximum window after which the minority becomes no longer available. Hence, no writes are accepted or lost after that time.

写安全
--

Redis集群使用异步副本实现冗余备份，。数据总是由最终选上master的节点决定。在分区失败时总是存在一个时间窗口其写入操作会被丢弃。如果客户端连接了大多数集群节点，那么这个窗口会小的多，反之则时间窗口会大得多。

相比连接了少数节点的客户端而言，Redis集群尽全力保存那些连接了大多数节点的客户端的写操作。
以下几种场景是集群故障恢复过程中可能丢失已写入数据的情况。

1. 如果一个写操作已经在master节点上完成，正回复给客户端时，该master节点崩溃了，此时该master还没来得及将数据复制给slave节点，那么将发生写丢失。如果master节点在数据同步给slave前崩溃，slave节点未收到数据并在一段时时间后将被提升为master节点，那么这个写操作将永久丢失。这种情况很难发现和保住数据，master节点的回复客户端操作和同步数据操作同时发生，这种情况在现实场景时有发生。

2. 另外一种可能导致写丢失的步骤如下

* 由于分区操作或网络抖动导致一个master节点不可达
* 随后发生故障转移，其slave提升为master节点
* 过了一会该master又恢复可用了
* 一个没有更新节点信息的客户端依然认为该master可用，从而写入数据，导致写丢失

实际上第二种情况发生的概率非常小，因为Redis对这种情况有应对机制，当一个master发现自己与大多数节点失去联系时，它就会拒绝写操作，同时当一个master节点从故障中恢复时，也仍会等待一小段时间，以便其它节点知道自己已从故障中恢复，各节点都更新完信息后再开始接受写请求。同时第二种情况都发生还有个前提就是，客户端未能及时更新节点信息。

只连接少数节点来进行写操作，丢失数据的时间窗口更大。举例来说，当一个客户端只连接少数几个节点时，Redis集群可能会丢失相当多的数据，因为所有的写操作都集中在少数几个master节点上，而一旦这些出现问题那后果很严重。

具体的说，判定一个master节点是否已失效（与大多数节点失联）需要经过`NODE_TIMEOUT`长时间，如果master节点在这段时间内又恢复正常，那么不会发生数据丢失（恢复后又会把数据同步给slave）。如果故障持续的时间大于`NODE_TIMEOUT`，那么在连接少数节点的客户端对于某些master的写操作将可能丢失。当这些少数节点在经过`NODE_TIMEOUT`时间无法与集群大多数节点联系后，它们都将进入不可服务状态，此后以后也不会有写丢失。

Availability
---

Redis Cluster is not available in the minority side of the partition. In the majority side of the partition assuming that there are at least the majority of masters and a slave for every unreachable master, the cluster becomes available again after `NODE_TIMEOUT` time plus a few more seconds required for a slave to get elected and failover its master (failovers are usually executed in a matter of 1 or 2 seconds).

This means that Redis Cluster is designed to survive failures of a few nodes in the cluster, but it is not a suitable solution for applications that require availability in the event of large net splits.

In the example of a cluster composed of N master nodes where every node has a single slave, the majority side of the cluster will remain available as long as a single node is partitioned away, and will remain available with a probability of `1-(1/(N*2-1))` when two nodes are partitioned away (after the first node fails we are left with `N*2-1` nodes in total, and the probability of the only master without a replica to fail is `1/(N*2-1))`.

For example, in a cluster with 5 nodes and a single slave per node, there is a `1/(5*2-1) = 11.11%` probability that after two nodes are partitioned away from the majority, the cluster will no longer be available.

Thanks to a Redis Cluster feature called **replicas migration** the Cluster
availability is improved in many real world scenarios by the fact that
replicas migrate to orphaned masters (masters no longer having replicas).
So at every successful failure event, the cluster may reconfigure the slaves
layout in order to better resist the next failure.

可用性
---

Redis集群无法在仅存少部分节点的情况下正常工作（即使少部分节点成功组成集群）。对于大多数节点组成的节点，集群假设各master节点都有一个可用的从节点，在master节点发生故障`NODE_TIMEOUT`时间后，其slave节点通过一个短时间的选举操作，将被提升为master节点，接替其原master的工作，接替工作耗时在1-2秒钟左右。

也就是说，Redis集群被设计为能在大多数节点可用时正常工作，对于那些有大规模网络分区的情况的场景则不适用。

假如一个集群有N个master节点，对应每个master有一个slave节点，这种情况下，如果集群丢失两个节点，那么还有`1-(1/(N*2-1))`的概率能够正常工作。计算过程是，当集群失去一个节点时，总会有一个slave补上，还剩共`N*2-1`个节点，此时再随机坏一个，当且仅当坏的是刚才补上的、唯一没有备份节点的slave，整个集群才会变得不可用，所以概率是`1-(1/(N*2-1))`。

再说个实际的例子，一共有10个节点的集群，5个master和5个slave节点。这种情况下如果丢失两个节点，那么有`1/(5*2-1) = 11.11%`的概率导致整个集群不可用。


Performance
---

In Redis Cluster nodes don't proxy commands to the right node in charge for a given key, but instead they redirect clients to the right nodes serving a given portion of the key space.

Eventually clients obtain an up-to-date representation of the cluster and which node serves which subset of keys, so during normal operations clients directly contact the right nodes in order to send a given command.

Because of the use of asynchronous replication, nodes do not wait for other nodes' acknowledgment of writes (if not explicitly requested using the `WAIT` command).

Also, because multi-key commands are only limited to *near* keys, data is never moved between nodes except when resharding.

Normal operations are handled exactly as in the case of a single Redis instance. This means that in a Redis Cluster with N master nodes you can expect the same performance as a single Redis instance multiplied by N as the design scales linearly. At the same time the query is usually performed in a single round trip, since clients usually retain persistent connections with the nodes, so latency figures are also the same as the single standalone Redis node case.

Very high performance and scalability while preserving weak but
reasonable forms of data safety and availability is the main goal of
Redis Cluster.


性能
---

Redis集群中的节点不代理本该其它完成的服务，而是通过命令重定向的方式告诉客户端到该key所在的节点再访问一次。

最终，客户端会获得一个最新的key与节点的映射关系，能够知道哪些key落在哪些节点，从而直接与正确的节点联系。

由于是异步副本冗余，节点无需等待slave的数据复制确认而是在本节点写完成后就直接返回成功。（除非强制指定来`WAIT`命令）

另外，由于对多个key的操作命令只能对在同一节点上的key执行，所以key几乎固定在某一个节点上，仅在需要resharding时才会移动。

普通的操作在单实例Redis中可以被正确处理，同样的，在有个N个master节点Redis集群中它们也可以被正确处理，并且其性能可以做到水平扩展，即该集群的性能是N*单实例Redis性能。通常情况下，同时仅有一次请求，也是与集群中某一个节点一来一回，客户端可以与各节点保持长连接，所以网络延迟开销也是和单实例情况下相同的。

非常高的性能和线性扩展能力，同时保留一定的数据安全性以及可用性，这是Redis集群的主要目标。


Why merge operations are avoided
---

Redis Cluster design avoids conflicting versions of the same key-value pair in multiple nodes as in the case of the Redis data model this is not always desirable. Values in Redis are often very large; it is common to see lists or sorted sets with millions of elements. Also data types are semantically complex. Transferring and merging these kind of values can be a major bottleneck and/or may require the non-trivial involvement of application-side logic, additional memory to store meta-data, and so forth.

There are no strict technological limits here. CRDTs or synchronously replicated
state machines can model complex data types similar to Redis. However, the
actual run time behavior of such systems would not be similar to Redis Cluster.
Redis Cluster was designed in order to cover the exact use cases of the
non-clustered Redis version.

为何禁用值合并操作
---

Redis集群不会合并在不同节点上的但Key相同的数据，当然这种设计并不是在所有场景都可取的，而是因为Redis的特殊情况而定下了这个策略。Redis中的数据值可能是一个非常大的，比如说list、set这样的集合，可以包含上百万个元素。除此之外，数据结构也比较复杂。传输并合并这些K-V，可能成为集群的主要瓶颈，甚至需要应用方有复杂的配合逻辑，以及更多的存储空间来存放这些迁移K-V的元数据等等。

当然Redis的这种设计不是什么完美的技术标准。CRDTs或同步状态机也有类似数据结构、数据大小的情况，但是它们选择了不同的策略。Redis集群的这种设计也是为了照顾非集群环境下的使用场景。


Overview of Redis Cluster main components
===

Keys distribution model
---

The key space is split into 16384 slots, effectively setting an upper limit
for the cluster size of 16384 master nodes (however the suggested max size of
nodes is in the order of ~ 1000 nodes).

Each master node in a cluster handles a subset of the 16384 hash slots.
The cluster is **stable** when there is no cluster reconfiguration in
progress (i.e. where hash slots are being moved from one node to another).
When the cluster is stable, a single hash slot will be served by a single node
(however the serving node can have one or more slaves that will replace it in the case of net splits or failures,
and that can be used in order to scale read operations where reading stale data is acceptable).

The base algorithm used to map keys to hash slots is the following
(read the next paragraph for the hash tag exception to this rule):

    HASH_SLOT = CRC16(key) mod 16384

The CRC16 is specified as follows:

* Name: XMODEM (also known as ZMODEM or CRC-16/ACORN)
* Width: 16 bit
* Poly: 1021 (That is actually x^16 + x^12 + x^5 + 1)
* Initialization: 0000
* Reflect Input byte: False
* Reflect Output CRC: False
* Xor constant to output CRC: 0000
* Output for "123456789": 31C3

14 out of 16 CRC16 output bits are used (this is why there is
a modulo 16384 operation in the formula above).

In our tests CRC16 behaved remarkably well in distributing different kinds of
keys evenly across the 16384 slots.

**Note**: A reference implementation of the CRC16 algorithm used is available in the Appendix A of this document.

Redis集群主要组件概要
===

Key分布策略
---

Key的存储空间被划分为16384个槽，事实上集群最大允许的master节点数量也是16384个，只是官方建议的最大节点个数是1000个。

集群中的每个master节点负责存储16384个槽中的一小部分。集群槽未出现需重分配的情况下（指哈希槽从一个节点迁移到另一个节点），集群是稳定的。当一个集群是稳定的，意味着指定的hash槽总是由某个固定的master节点提供读写服务（当然，这个master节点可以有slave节点，用于在发生网络分裂或系统故障时接替它的工作，同时也可以在对实时性要求不高的场景下，为master节点分担一部分的读请求）。

从key到存储槽（slot）的映射本质上就是通过以下这个函数（当然也存在不完全用key计算哈希标签的情况，在下一章节详述）：

	HASH_SLOT = CRC16(key) mod 16384

其中CRC16()函数实现策略如下：

* 名称：XMODEM协议（也称作ZMODEM或CRC-16/ACORN）
* 结果长度：16位
* 多项式简记值：1021（等于x^16 + x^12 + x^5 + 1）
* 初始值：0000
* 反射输入数组：否
* 反射输出校验码：否
* 字符串"123456789"的校验结果：31C3

CRC16()函数输出结果16位中的14位会被使用，当作取模计算的输入（这也是为什么计算哈希标签的公式是对16384取模（2^14）。

经过测试，CRC16()对于各种种类的key都有很好的散列性，能将各个key均匀的分布到16384个槽中。

CRC16的实现算法在本文档的附录A中。

Keys hash tags
---

There is an exception for the computation of the hash slot that is used in order
to implement **hash tags**. Hash tags are a way to ensure that multiple keys
are allocated in the same hash slot. This is used in order to implement
multi-key operations in Redis Cluster.

In order to implement hash tags, the hash slot for a key is computed in a
slightly different way in certain conditions.
If the key contains a "{...}" pattern only the substring between
`{` and `}` is hashed in order to obtain the hash slot. However since it is
possible that there are multiple occurrences of `{` or `}` the algorithm is
well specified by the following rules:

* IF the key contains a `{` character.
* AND IF there is a `}` character to the right of `{`
* AND IF there are one or more characters between the first occurrence of `{` and the first occurrence of `}`.

Then instead of hashing the key, only what is between the first occurrence of `{` and the following first occurrence of `}` is hashed.

Examples:

* The two keys `{user1000}.following` and `{user1000}.followers` will hash to the same hash slot since only the substring `user1000` will be hashed in order to compute the hash slot.
* For the key `foo{}{bar}` the whole key will be hashed as usually since the first occurrence of `{` is followed by `}` on the right without characters in the middle.
* For the key `foo{{bar}}zap` the substring `{bar` will be hashed, because it is the substring between the first occurrence of `{` and the first occurrence of `}` on its right.
* For the key `foo{bar}{zap}` the substring `bar` will be hashed, since the algorithm stops at the first valid or invalid (without bytes inside) match of `{` and `}`.
* What follows from the algorithm is that if the key starts with `{}`, it is guaranteed to be hashed as a whole. This is useful when using binary data as key names.

Adding the hash tags exception, the following is an implementation of the `HASH_SLOT` function in Ruby and C language.

Ruby example code:

    def HASH_SLOT(key)
        s = key.index "{"
        if s
            e = key.index "}",s+1
            if e && e != s+1
                key = key[s+1..e-1]
            end
        end
        crc16(key) % 16384
    end

C example code:

    unsigned int HASH_SLOT(char *key, int keylen) {
        int s, e; /* start-end indexes of { and } */

        /* Search the first occurrence of '{'. */
        for (s = 0; s < keylen; s++)
            if (key[s] == '{') break;

        /* No '{' ? Hash the whole key. This is the base case. */
        if (s == keylen) return crc16(key,keylen) & 16383;

        /* '{' found? Check if we have the corresponding '}'. */
        for (e = s+1; e < keylen; e++)
            if (key[e] == '}') break;

        /* No '}' or nothing between {} ? Hash the whole key. */
        if (e == keylen || e == s+1) return crc16(key,keylen) & 16383;

        /* If we are here there is both a { and a } on its right. Hash
         * what is in the middle between { and }. */
        return crc16(key+s+1,e-s-1) & 16383;
    }


key与哈希标签
---

之前说的使用key进行计算并得到哈希槽的算法也存在特殊情况。我们可以通过一种策略将某些key映射在相同的哈希槽中。这种策略对需要在集群中实现多key操作的场景非常有用。

为了实现哈希标签的这种特性，在某些情况下计算哈希槽的方式有所不同。  
如果一个key包括一个花括号"{...}"，那么仅有花括号内的字符串才参与哈希槽的计算。当然也可能存在有多个不工整的左、右花括号，情况复杂，总结定义这种场景如下：

* 从左向右检查字符串，如果发现key有一个左花括号'{'
* 而且这个左花括号的右边还有一个右花括号'}'
* 而且花括号内的有且不止一个字符

符合上述情况时，key里这唯一一个花括号（只计算最左出现的完整花括号）内的字符串才会参与哈希槽的计算。

举例来说：

* `{user1000}.following` 和 `{user1000}.followers`这两个键会被映射到同一个哈希槽，因为只有花括号内的`user1000`参与哈希槽计算。
* `foo{}{bar}`这个key会整个字符串参与哈希槽计算，因为第一个花括号内没有值，是一个无效的花括号（策略只管第一个碰到的花括号）
* `foo{{bar}}zap`这个key仅有`{bar`参与哈希槽计算，策略只管第一个碰到的左花括号，和第一个碰到的右花括号之间的字符串。
* `foo{bar}{zap}`这个key仅有`bar`会参与哈希槽计算，因为策略只管第一个碰到的花括号内的值。
* 如果字符串以`{}`开头，那么肯定会以整个key当作哈希槽的计算依据。这在以字节数据当作key的场景非常有用（因为字节流转换为字符串可能出现各种各样的字符，恰好出现花括号就麻烦了）。

加入了上述的特殊情况之后，之前说的计算哈希槽的函数可以改为用以下代码表达。


Ruby代码示例:

    def HASH_SLOT(key)
        s = key.index "{"
        if s
            e = key.index "}",s+1
            if e && e != s+1
                key = key[s+1..e-1]
            end
        end
        crc16(key) % 16384
    end

C example code:

    unsigned int HASH_SLOT(char *key, int keylen) {
        // 纪录第一个花括号的起始和结束
        int s, e;

        // 查找第一个左花括号
        for (s = 0; s < keylen; s++)
            if (key[s] == '{') break;

        // 如果未找到花括号，那就直接以整个key作为计算依据
        if (s == keylen) return crc16(key,keylen) & 16383;

        // 找到左花括号之后开始找在这之后出现的右花括号
        for (e = s+1; e < keylen; e++)
            if (key[e] == '}') break;

        // 如果没找到右花括号或者找到了右花括号单花括号内没有值，则以整个key当作计算依据
        if (e == keylen || e == s+1) return crc16(key,keylen) & 16383;

        // 走到这说明存在花括号且花括号内有子字符串，这以该子字符串作为计算依据
        return crc16(key+s+1,e-s-1) & 16383;
    }



Cluster nodes attributes
---

Every node has a unique name in the cluster. The node name is the
hex representation of a 160 bit random number, obtained the first time a
node is started (usually using /dev/urandom).
The node will save its ID in the node configuration file, and will use the
same ID forever, or at least as long as the node configuration file is not
deleted by the system administrator, or a *hard reset* is requested
via the `CLUSTER RESET` command.

The node ID is used to identify every node across the whole cluster.
It is possible for a given node to change its IP address without any need
to also change the node ID. The cluster is also able to detect the change
in IP/port and reconfigure using the gossip protocol running over the cluster
bus.

The node ID is not the only information associated with each node, but is
the only one that is always globally consistent. Every node has also the
following set of information associated. Some information is about the
cluster configuration detail of this specific node, and is eventually
consistent across the cluster. Some other information, like the last time
a node was pinged, is instead local to each node.

Every node maintains the following information about other nodes that it is
aware of in the cluster: The node ID, IP and port of the node, a set of
flags, what is the master of the node if it is flagged as `slave`, last time
the node was pinged and the last time the pong was received, the current
*configuration epoch* of the node (explained later in this specification),
the link state and finally the set of hash slots served.

A detailed [explanation of all the node fields](http://redis.io/commands/cluster-nodes) is described in the `CLUSTER NODES` documentation.

The `CLUSTER NODES` command can be sent to any node in the cluster and provides the state of the cluster and the information for each node according to the local view the queried node has of the cluster.

The following is sample output of the `CLUSTER NODES` command sent to a master
node in a small cluster of three nodes.

    $ redis-cli cluster nodes
    d1861060fe6a534d42d8a19aeb36600e18785e04 127.0.0.1:6379 myself - 0 1318428930 1 connected 0-1364
    3886e65cc906bfd9b1f7e7bde468726a052d1dae 127.0.0.1:6380 master - 1318428930 1318428931 2 connected 1365-2729
    d289c575dcbc4bdd2931585fd4339089e461a27d 127.0.0.1:6381 master - 1318428931 1318428931 3 connected 2730-4095

In the above listing the different fields are in order: node id, address:port, flags, last ping sent, last pong received, configuration epoch, link state, slots. Details about the above fields will be covered as soon as we talk of specific parts of Redis Cluster.

集群节点属性
---

在集群中，每个节点都有一个唯一的名字。节点名称是一个160比特的随机数字串，在节点启动时随机获取的（一般通过/dev/urandom获取）。    
节点会将它的ID保存到其配置文件中，并且在之后会一直使用这个固定的ID，除非其配置文件被系统管理员删除或者通过`CLUSTER RESET`命令强制重置了集群。

节点ID用于在集群中唯一标示一个节点。一个节点可以改变其IP地址而无需改变其节点ID。集群会通过集群总线上的```gossip```协议得知集群中各节点的IP、端口等配置信息的改变。

节点ID不是节点的唯一配置信息，但却是节点信息中唯一的全局变量。每个节点都还包含其他配置信息。一部分信息是该节点在集群中的配置信息，该信息需要最终在整个集群保持一致。另外一部分信息则是节点私有的状态信息，比如节点最后一次被ping的时间，这些信息存储在各个节点本地。

每个节点都维护了关于其他节点的以下信息：节点ID，节点的IP和端口、节点的各种的标记信息、slave节点的master节点信息、节点最后被ping的时间以及最后一次收到pong的时间、节点当前的配置版本号（后续章节再详细解释）、节点的连接状态以及属于该节点管辖范围的哈希槽。

详细解释节点各个配置属性的内容在这篇名为`CLUSTER NODES`的文章里[explanation of all the node fields](http://redis.io/commands/cluster-nodes)。

命令`CLUSTER NODES`可以在集群中任何节点执行，都会返回集群的状态信息以及在该节点眼中其他节点的状态信息。

下面的例子展示了在一个只有3个节点的小集群里，在其中一个master节点上执行`CLUSTER NODES`命令得到的输出结果。

    $ redis-cli cluster nodes
    d1861060fe6a534d42d8a19aeb36600e18785e04 127.0.0.1:6379 myself - 0 1318428930 1 connected 0-1364
    3886e65cc906bfd9b1f7e7bde468726a052d1dae 127.0.0.1:6380 master - 1318428930 1318428931 2 connected 1365-2729
    d289c575dcbc4bdd2931585fd4339089e461a27d 127.0.0.1:6381 master - 1318428931 1318428931 3 connected 2730-4095
    
上述内容罗列了节点的各类属性值：节点ID、IP地址和端口、标记位、最后被ping的时间、最后收到pong的时间、配置版本号、连接状态、槽。这些属性会在谈到集群指定组件时再做详细介绍。


The Cluster bus
---

Every Redis Cluster node has an additional TCP port for receiving
incoming connections from other Redis Cluster nodes. This port is at a fixed
offset from the normal TCP port used to receive incoming connections
from clients. To obtain the Redis Cluster port, 10000 should be added to
the normal commands port. For example, if a Redis node is listening for
client connections on port 6379, the Cluster bus port 16379 will also be
opened.

Node-to-node communication happens exclusively using the Cluster bus and
the Cluster bus protocol: a binary protocol composed of frames
of different types and sizes. The Cluster bus binary protocol is not
publicly documented since it is not intended for external software devices
to talk with Redis Cluster nodes using this protocol. However you can
obtain more details about the Cluster bus protocol by reading the
`cluster.h` and `cluster.c` files in the Redis Cluster source code.

集群总线
---

每个集群中的节点都额外监听了一个端口，用于接受集群内其他节点的连接。这个端口号和Redis对外的服务端口号（接受客户端请求的端口）保持了一定的距离。对外服务端口号加上1000即可得到这个端口号。举个例子，比如说为客户端提供服务的端口号是6379，那么集群总线端口号则是16379.

Cluster topology
---

Redis Cluster is a full mesh where every node is connected with every other node using a TCP connection.

In a cluster of N nodes, every node has N-1 outgoing TCP connections, and N-1 incoming connections.

These TCP connections are kept alive all the time and are not created on demand.
When a node expects a pong reply in response to a ping in the cluster bus, before waiting long enough to mark the node as unreachable, it will try to
refresh the connection with the node by reconnecting from scratch.

While Redis Cluster nodes form a full mesh, **nodes use a gossip protocol and
a configuration update mechanism in order to avoid exchanging too many
messages between nodes during normal conditions**, so the number of messages
exchanged is not exponential.

集群拓扑
---

Redis集群是一个完全网格化的系统，每个节点都通过TCP连接与其他节点相连。

在一个由N个节点的集群中，每个节点则有N-1个连接其他节点的TCP连接，同时还有N-1个其他节点连接它的TCP连接。

这些TCP连接是持久保活的的，并且是从头到尾一直存在的。当一个节点期望通过集群总线收到ping请求响应结果pong时，如果一定时间没收到响应，在判断对方节点失活前，它会尝试刷新连接，也就是与对方重新建立连接。

虽然Redis集群是完全网格型的系统，但节点间通信会使用gossip协议和有效的配置更新机制，能够有效的防止节点之间频繁的交换消息，所以消息交换的次数不是指数增长的。

Nodes handshake
---

Nodes always accept connections on the cluster bus port, and even reply to
pings when received, even if the pinging node is not trusted.
However, all other packets will be discarded by the receiving node if the
sending node is not considered part of the cluster.

A node will accept another node as part of the cluster only in two ways:

* If a node presents itself with a `MEET` message. A meet message is exactly
like a `PING` message, but forces the receiver to accept the node as part of
the cluster. Nodes will send `MEET` messages to other nodes **only if** the system administrator requests this via the following command:

    CLUSTER MEET ip port

* A node will also register another node as part of the cluster if a node that is already trusted will gossip about this other node. So if A knows B, and B knows C, eventually B will send gossip messages to A about C. When this happens, A will register C as part of the network, and will try to connect with C.

This means that as long as we join nodes in any connected graph, they'll eventually form a fully connected graph automatically. This means that the cluster is able to auto-discover other nodes, but only if there is a trusted relationship that was forced by the system administrator.

This mechanism makes the cluster more robust but prevents different Redis clusters from accidentally mixing after change of IP addresses or other network related events.

节点握手
---

节点接受在集群总线端口上的任何连接，甚至对于没有认证的ping请求也会给予响应。  
当然除了ping以外的其他请求则需要发送者是集群中的一份子，否则这些请求包会被丢弃。

让一个节点接受其他服务器成为集群中的一份子有两种方式：

* 新的节点通过发送`MEET`消息向已有节点注册自己。一个`MEET`消息和`PING`类似，但是使得接收方将自己加入到集群中。只有系统管理员可以手动在新的节点上执行命令来向集群中的节点发送`MEET`消息，命令如下：    

    CLUSTER MEET ip port

* 已在集群中节点也会接受已被集群中其他节点接受的新节点，新节点消息将通过gossip消息送到给它。也就是说如果A节点认同了B节点，并且B节点认同了C节点，那么最终B节点会通过gossip消息将C节点介绍给A节点。当这个消息送到，A节点也会认同C节点是集群中的一部分，并且会尝试与C节点建立连接。

Redirection and resharding
===

MOVED Redirection
---

A Redis client is free to send queries to every node in the cluster, including
slave nodes. The node will analyze the query, and if it is acceptable
(that is, only a single key is mentioned in the query, or the multiple keys
mentioned are all to the same hash slot) it will lookup what
node is responsible for the hash slot where the key or keys belong.

If the hash slot is served by the node, the query is simply processed, otherwise
the node will check its internal hash slot to node map, and will reply
to the client with a MOVED error, like in the following example:

    GET x
    -MOVED 3999 127.0.0.1:6381

The error includes the hash slot of the key (3999) and the ip:port of the
instance that can serve the query. The client needs to reissue the query
to the specified node's IP address and port.
Note that even if the client waits a long time before reissuing the query,
and in the meantime the cluster configuration changed, the destination node
will reply again with a MOVED error if the hash slot 3999 is now served by
another node. The same happens if the contacted node had no updated information.

So while from the point of view of the cluster nodes are identified by
IDs we try to simplify our interface with the client just exposing a map
between hash slots and Redis nodes identified by IP:port pairs.

The client is not required to, but should try to memorize that hash slot
3999 is served by 127.0.0.1:6381. This way once a new command needs to
be issued it can compute the hash slot of the target key and have a
greater chance of choosing the right node.

An alternative is to just refresh the whole client-side cluster layout
using the `CLUSTER NODES` or `CLUSTER SLOTS` commands
when a MOVED redirection is received. When a redirection is encountered, it
is likely multiple slots were reconfigured rather than just one, so updating
the client configuration as soon as possible is often the best strategy.

Note that when the Cluster is stable (no ongoing changes in the configuration),
eventually all the clients will obtain a map of hash slots -> nodes, making
the cluster efficient, with clients directly addressing the right nodes
without redirections, proxies or other single point of failure entities.

A client **must be also able to handle -ASK redirections** that are described
later in this document, otherwise it is not a complete Redis Cluster client.

重定向与重分配
===

MOVED重定向
---

一个Redis客户端可以向集群中任何节点发送请求，包括slave节点。接收到请求的节点会分析这个请求，如果是可处理的（要么是一个单key请求，或者是一个全部落在相同槽的多key请求），那么它会找到哪个节点可以负责处理这个请求，也就是这些key的哈希槽属于哪个节点管辖。

如果这些key的哈希槽正是由本节点负责处理的，那么请求就会被直接处理了，否则的话，节点会查看它存储的哈希槽分布图，并返回一个重定向错误，如以下例子：

    GET x
    -MOVED 3999 127.0.0.1:6381
    
重定向错误信息包括了key具体落在了哪个哈希槽中以及管辖该哈希槽的节点的IP与端口信息。客户端则需要对这个IP和端口重新发起一次请求。  
假设说再次客户端在再次发起请求前停留了足够长的时间，长到集群哈希槽分配策略又发生了一次改变，3999这个哈希槽又被分配到另外的节点管辖，那么再次请求目标节点时还是会收到重定向错误。在客户端未能及时收到集群配置变更信息时，就可能发生这种情况。

所以我们想简化集群配置的表述，以节点ID唯一表示一个节点，以哈希槽+节点IP和端口来表示哈希槽与节点之间的映射关系。

不强制要求客户端必须知道3999这个哈希槽时属于127.0.0.1:6381节点管辖的，但是客户端应该尝试尽快记住这些哈希槽与节点的映射关系。这样的话，当客户端想指定一个新的命令时，它就可以提前计算好key的哈希槽属于哪个节点管辖，从而更有可能连接到正确的节点上，一次性完成请求。

当收到重定向错误时，另外一个选择就是通过`CLUSTER NODES` 或 `CLUSTER SLOTS`命令直接刷新本地关于哈希槽与节点映射关系的纪录。当收到某个key请求的重定向错误，大多数情况下不仅仅是这一个key的哈希槽与节点映射关系发生了改变，往往是很多的哈希槽与节点的映射关系都发生了改变，所以通常在这种情况下直接更新整个集群的哈希槽映射关系是最好的策略。

其实大多数情况下集群都是稳定的（集群配置信息没有改动），这样所有客户端最终都会得到一份正确的哈希槽映射配置信息，这样集群的服务效率很高，客户端总是直接与正确的节点相连，没有重定向，没有代理以及其它单体故障。

一个Redis客户端还必须能够正确处理-ASK重定向（具体细节后续章节描述），否则它就不是一个完整的Redis客户端。

Cluster live reconfiguration
---

Redis Cluster supports the ability to add and remove nodes while the cluster
is running. Adding or removing a node is abstracted into the same
operation: moving a hash slot from one node to another. This means
that the same basic mechanism can be used in order to rebalance the cluster, add
or remove nodes, and so forth.

* To add a new node to the cluster an empty node is added to the cluster and some set of hash slots are moved from existing nodes to the new node.
* To remove a node from the cluster the hash slots assigned to that node are moved to other existing nodes.
* To rebalance the cluster a given set of hash slots are moved between nodes.

The core of the implementation is the ability to move hash slots around.
From a practical point of view a hash slot is just a set of keys, so
what Redis Cluster really does during *resharding* is to move keys from
an instance to another instance. Moving a hash slot means moving all the keys
that happen to hash into this hash slot.

To understand how this works we need to show the `CLUSTER` subcommands
that are used to manipulate the slots translation table in a Redis Cluster node.

The following subcommands are available (among others not useful in this case):

* `CLUSTER ADDSLOTS` slot1 [slot2] ... [slotN]
* `CLUSTER DELSLOTS` slot1 [slot2] ... [slotN]
* `CLUSTER SETSLOT` slot NODE node
* `CLUSTER SETSLOT` slot MIGRATING node
* `CLUSTER SETSLOT` slot IMPORTING node

The first two commands, `ADDSLOTS` and `DELSLOTS`, are simply used to assign
(or remove) slots to a Redis node. Assigning a slot means to tell a given
master node that it will be in charge of storing and serving content for
the specified hash slot.

After the hash slots are assigned they will propagate across the cluster
using the gossip protocol, as specified later in the
*configuration propagation* section.

The `ADDSLOTS` command is usually used when a new cluster is created
from scratch to assign each master node a subset of all the 16384 hash
slots available.

The `DELSLOTS` is mainly used for manual modification of a cluster configuration
or for debugging tasks: in practice it is rarely used.

The `SETSLOT` subcommand is used to assign a slot to a specific node ID if
the `SETSLOT <slot> NODE` form is used. Otherwise the slot can be set in the
two special states `MIGRATING` and `IMPORTING`. Those two special states
are used in order to migrate a hash slot from one node to another.

* When a slot is set as MIGRATING, the node will accept all queries that
are about this hash slot, but only if the key in question
exists, otherwise the query is forwarded using a `-ASK` redirection to the
node that is target of the migration.
* When a slot is set as IMPORTING, the node will accept all queries that
are about this hash slot, but only if the request is
preceded by an `ASKING` command. If the `ASKING` command was not given
by the client, the query is redirected to the real hash slot owner via
a `-MOVED` redirection error, as would happen normally.

Let's make this clearer with an example of hash slot migration.
Assume that we have two Redis master nodes, called A and B.
We want to move hash slot 8 from A to B, so we issue commands like this:

* We send B: CLUSTER SETSLOT 8 IMPORTING A
* We send A: CLUSTER SETSLOT 8 MIGRATING B

All the other nodes will continue to point clients to node "A" every time
they are queried with a key that belongs to hash slot 8, so what happens
is that:

* All queries about existing keys are processed by "A".
* All queries about non-existing keys in A are processed by "B", because "A" will redirect clients to "B".
    
This way we no longer create new keys in "A".
In the meantime, a special program called `redis-trib` used during reshardings
and Redis Cluster configuration will migrate existing keys in
hash slot 8 from A to B.
This is performed using the following command:

    CLUSTER GETKEYSINSLOT slot count

The above command will return `count` keys in the specified hash slot.
For every key returned, `redis-trib` sends node "A" a `MIGRATE` command, that
will migrate the specified key from A to B in an atomic way (both instances
are locked for the time (usually very small time) needed to migrate a key so
there are no race conditions). This is how `MIGRATE` works:

    MIGRATE target_host target_port key target_database id timeout

`MIGRATE` will connect to the target instance, send a serialized version of
the key, and once an OK code is received, the old key from its own dataset
will be deleted. From the point of view of an external client a key exists
either in A or B at any given time.

In Redis Cluster there is no need to specify a database other than 0, but
`MIGRATE` is a general command that can be used for other tasks not
involving Redis Cluster.
`MIGRATE` is optimized to be as fast as possible even when moving complex
keys such as long lists, but in Redis Cluster reconfiguring the
cluster where big keys are present is not considered a wise procedure if
there are latency constraints in the application using the database.

When the migration process is finally finished, the `SETSLOT <slot> NODE <node-id>` command is sent to the two nodes involved in the migration in order to
set the slots to their normal state again. The same command is usually
sent to all other nodes to avoid waiting for the natural
propagation of the new configuration across the cluster.

在线修改集群配置
---

Redis集群支持在运行期间动态增删节点。增加和删除节点的方法被抽象为一个统一的操作：为节点分配哈希槽或移走哈希槽。也就是说一些基本的操作可以完成用来平衡集群、增加或删除节点，等等事情。

* 向集群中增加一个节点，本质上就是在集群中增加一个空节点，随后将已有的节点管辖的部分哈希槽分配给新节点管辖。
* 删除集群中的一个节点，也就是将这个节点管辖的哈希槽全部拿走，分配给其它节点。
* 平衡集群节点的负载情况，调整各个节点管辖的哈希槽数量，使落在节点上的请求均匀分配

所以这些操作的核心实现就是如何移动哈希槽。哈希槽这是个虚拟逻辑，实际上移动哈希槽就是对一堆key的移动，所以Redis集群在重分配期间所做的事情就是将一堆key从一个节点移动到另一个节点。移动一个哈希槽就意味着移动这个槽内所有的key。

为了更好的理解这些工作原理，我们可以查看下关于操作哈希槽的几个集群子命令。

以下这个命令是比较有效的（其他命令不能很好的说明问题）：

* `CLUSTER ADDSLOTS` slot1 [slot2] ... [slotN]
* `CLUSTER DELSLOTS` slot1 [slot2] ... [slotN]
* `CLUSTER SETSLOT` slot NODE node
* `CLUSTER SETSLOT` slot MIGRATING node
* `CLUSTER SETSLOT` slot IMPORTING node

前两个命令，`ADDSLOTS` 和 `DELSLOTS`是一对，分别用于分配与移除节点管辖的哈希槽。将哈希槽分配给某个节点意味着从此这个节点负责存储属于这些哈希槽的key和key对应的值数据，以及为落在这些key上的请求提供服务。

当哈希槽重分配成功，节点会通过gossip协议传播这次配置变更信息，后续会有专门一个章节*configuration propagation*来描述这种行为。

命令`ADDSLOTS`用于在刚创建一个集群时，将16384个可用的哈希槽分配给每个master节点。

命令`DELSLOTS`多用于手动修改集群配置或者用于调试，在实际环境中它很少被使用。

通过传入哈希槽与节点ID，命令`SETSLOT`可以用于将某个哈希槽分配给指定ID的节点。或者命令`SETSLOT`还可以将某些哈希槽设置为`MIGRATING`及`IMPORTING`状态。这两个哈希槽状态是为后面的哈希槽迁移操作做准备。

* 当一个哈希槽被设置为MIGRATING状态，之前管辖该哈希槽的节点仍会处理所有的请求，但仅当指定key还在该节点上时才处理，否则请求会直接返回`-ASK`重定向到当前实际存储该key的节点上。
* 当一个哈希槽被设置为IMPORTING状态，当前节点会接受所有关于该哈希槽点请求，但仅允许请求是被 `ASKING`命令重定向过来的。如果客户端没有带上`ASKING`特征，请求会返回重定向错误，重定向到哈希槽原来的节点。

为了表达的更清楚，我们举一个哈希槽迁移的例子。  
假设我们有两个master节点，分别称之为A和B。  
我们想将哈希槽8从节点A移动到节点B，我们按以下流程执行迁移：

* 向节点B发送命令：CLUSTER SETSLOT 8 IMPORTING A
* 向节点A发送命令：CLUSTER SETSLOT 8 MIGRATING B

此时集群中其它节点包括客户端，都还认为哈希槽8还属于节点A，并会重定向所有关于哈希槽8的请求到节点A，所以会发生如下情况：

* 还未完成迁移（还在A上）的key还继续由A处理
* 其他已经完成迁移的请求则由B处理，因为A会把已经不在它上面的key都重定向到B节点上。

这种方式使得我们不需要在A节点上创建一个新key。  
与此同时，Redis提供了一个特殊的工具 `redis-trib`，也是一个集群配置程序，它可以保证把哈希槽8已有的key从节点A移动到节点B。   
可以使用以下命令实现该功能： 

    CLUSTER GETKEYSINSLOT slot count
    
上述命令会返回指定槽中`count`个key。对于每个返回的key，`redis-trib`对节点A发送一个`MIGRATE`命令，这样会将该key从节点A迁移至节点B，迁移的动作是原子的，节点A和B都会被锁住（通常锁住的时间不会太长），避免迁移一个key的过程中出现竞态条件。如下是`MIGRATE`命令的工作原理：  

    MIGRATE target_host target_port key target_database id timeout

命令`MIGRATE`会连接目标节点（B），把序列化后的key发送过去，一旦收到成功响应，在当前的节点（A）中的key会被删除。从外界来看，在任意时刻，这个key要么在A中，要么在B中。

在Redis集群中没有必要指定数据库序号，统一使用0号数据库，但是`MIGRATE`是一个通用命令，也可以用于被执行其它任务。   
命令`MIGRATE`被特别优化过，及时移动复杂的key（比如长列表）也会尽可能的快，不过当拥有大量复杂key时，重分配哈希槽则会造成一定影响，对于使用该集群的应用会有一定的延时。

当迁移过程完成，会发送`SETSLOT <slot> NODE <node-id>`命令给两个节点，使其哈希槽状态再度恢复正常。同样的命令也会发送给集群其它节点，可以让其它节点快速知晓更新后的哈希槽分配情况，而不用等待这两个节点慢慢的把消息传播到整个集群。

ASK redirection
---

In the previous section we briefly talked about ASK redirection. Why can't
we simply use MOVED redirection? Because while MOVED means that
we think the hash slot is permanently served by a different node and the
next queries should be tried against the specified node, ASK means to
send only the next query to the specified node.

This is needed because the next query about hash slot 8 can be about a
key that is still in A, so we always want the client to try A and
then B if needed. Since this happens only for one hash slot out of 16384
available, the performance hit on the cluster is acceptable.

We need to force that client behavior, so to make sure
that clients will only try node B after A was tried, node B will only
accept queries of a slot that is set as IMPORTING if the client sends the
ASKING command before sending the query.

Basically the ASKING command sets a one-time flag on the client that forces
a node to serve a query about an IMPORTING slot.

The full semantics of ASK redirection from the point of view of the client is as follows:

* If ASK redirection is received, send only the query that was redirected to the specified node but continue sending subsequent queries to the old node.
* Start the redirected query with the ASKING command.
* Don't yet update local client tables to map hash slot 8 to B.

Once hash slot 8 migration is completed, A will send a MOVED message and
the client may permanently map hash slot 8 to the new IP and port pair.
Note that if a buggy client performs the map earlier this is not
a problem since it will not send the ASKING command before issuing the query,
so B will redirect the client to A using a MOVED redirection error.

Slots migration is explained in similar terms but with different wording
(for the sake of redundancy in the documentation) in the `CLUSTER SETSLOT`
command documentation.

ASK重定向
---

在之前的章节，我们简要的介绍了ASK重定向。为什么不能直接使用`MOVED`错误表示重定向呢？这是因为`MOVED`表示哈希槽已被永久迁移到另外一个节点，之后的所有请求都应该发送到新的节点上。而ASK表示仅仅下一次请求发送到指定节点。

ASK是很有必要的，因为稍后来的其他关于哈希槽8的key可能依旧在A节点上，所以总是先请求A节点，A节点发现需要重定向时再去请求B节点。由于迁移仅涉及16384个槽的其中一个，所以两次请求带来的性能损失时可以接受。

对于迁移过程中的哈希槽，我们必须确保客户端在向B节点发起请求前已经向A节点发过请求（通过ASK重定向到B），同时，如果客户端向B节点发送了ASKING命令，下一次请求的key所属的哈希槽必须是处于IMPORTING状态。

简单点说，客户端通过发送一个ASKING命令，使得对应节点只能为属于IMPORTING状态的哈希槽提供服务。

从客户端的角度来看，ASK的语义如下：

* 如果接收到一个ASK重定向，仅把这一个被重定向请求发送给新的节点，其他关于这个哈希槽的请求还是发送给老的节点。
* 首先发送一个ASKING命令到新的节点上，之后再执行数据请求
* 关于哈希槽8的请求依旧发送到节点A上

一旦哈希槽8的迁移动作完成，客户端再请求该哈希槽时，节点A会返回一个MOVED重定向消息，此时客户端就可以认为哈希槽从此以后都由节点B管辖了。  
即使有出现问题的客户端过早的认为哈希槽已经迁移到新的节点上了，也不是什么大问题，因为错误的客户端不会先发送一个ASKING命令，这样的话，新节点只要返回一个MOVED重定向错误，告诉客户端该哈希槽还在老节点上即可。

哈希槽迁移的说明也在命令`CLUSTER SETSLOT`的解释文档中提到（为了文档冗余，两处都可方便查看），但是语境不同。


Clients first connection and handling of redirections
---

While it is possible to have a Redis Cluster client implementation that does not
remember the slots configuration (the map between slot numbers and addresses of
nodes serving it) in memory and only works by contacting random nodes waiting to
be redirected, such a client would be very inefficient.

Redis Cluster clients should try to be smart enough to memorize the slots
configuration. However this configuration is not *required* to be up to date.
Since contacting the wrong node will simply result in a redirection, that
should trigger an update of the client view.

Clients usually need to fetch a complete list of slots and mapped node
addresses in two different situations:

* At startup in order to populate the initial slots configuration.
* When a `MOVED` redirection is received.

Note that a client may handle the `MOVED` redirection by updating just the
moved slot in its table, however this is usually not efficient since often
the configuration of multiple slots is modified at once (for example if a
slave is promoted to master, all the slots served by the old master will
be remapped). It is much simpler to react to a `MOVED` redirection by
fetching the full map of slots to nodes from scratch.

In order to retrieve the slots configuration Redis Cluster offers
an alternative to the `CLUSTER NODES` command that does not
require parsing, and only provides the information strictly needed to clients.

The new command is called `CLUSTER SLOTS` and provides an array of slots
ranges, and the associated master and slave nodes serving the specified range.

The following is an example of output of `CLUSTER SLOTS`:

```
127.0.0.1:7000> cluster slots
1) 1) (integer) 5461
   2) (integer) 10922
   3) 1) "127.0.0.1"
      2) (integer) 7001
   4) 1) "127.0.0.1"
      2) (integer) 7004
2) 1) (integer) 0
   2) (integer) 5460
   3) 1) "127.0.0.1"
      2) (integer) 7000
   4) 1) "127.0.0.1"
      2) (integer) 7003
3) 1) (integer) 10923
   2) (integer) 16383
   3) 1) "127.0.0.1"
      2) (integer) 7002
   4) 1) "127.0.0.1"
      2) (integer) 7005
```

The first two sub-elements of every element of the returned array are the
start-end slots of the range. The additional elements represent address-port
pairs. The first address-port pair is the master serving the slot, and the
additional address-port pairs are all the slaves serving the same slot
that are not in an error condition (i.e. the FAIL flag is not set).

For example the first element of the output says that slots from 5461 to 10922
(start and end included) are served by 127.0.0.1:7001, and it is possible
to scale read-only load contacting the slave at 127.0.0.1:7004.

`CLUSTER SLOTS` is not guaranteed to return ranges that cover the full
16384 slots if the cluster is misconfigured, so clients should initialize the
slots configuration map filling the target nodes with NULL objects, and
report an error if the user tries to execute commands about keys
that belong to unassigned slots.

Before returning an error to the caller when a slot is found to
be unassigned, the client should try to fetch the slots configuration
again to check if the cluster is now configured properly.

客户端首次连接与处理重定向
---

有可能存在这样的客户端，它不存储集群中哈希槽的分配关系记录（哈希槽与其集群节点的映射关系），仅仅是随机性的连接集群中的某些节点，然后等待着被重定向，从而能够访问到正确的节点，这样的客户端效率是非常低下的。

Redis集群的客户端应该尽可能的智能化，认真记录下集群中哈希槽的分配关系。当然不强制要求记录的映射关系是最新版本的。由于连接到一个错误的客户端会被返回一个重定向错误，此时应该借机更新下客户端中的集群哈希槽分配关系记录。

在下面两种场景下，客户端总是需要抓取一个完整的哈希槽分配关系记录以及节点地址信息：

* 客户端刚启动时，需要获取集群哈希槽的初始信息
* 当服务器返回一个重定向错误时

某些客户端在收到重定向错误时，仅仅更新了被重定向的哈希槽的映射关系，往往这种做法是低效的，因为大多数情况下总是多个哈希槽映射关系一起发生改变（比如一个slave节点被提升为master节点后，原master节点管辖的所有哈希槽都将被重新分配）。在收到重定向错误时就更新整个集群的哈希槽映射关系记录，这是一种更加简单有效的办法。

为了能检索哈希槽的配置关系，Redis集群提供了`CLUSTER NODES`命令，该命令不需要对各哈希槽逐个分析，并且能向客户端返回严格的配置关系记录。

另一个新增的命令 `CLUSTER SLOTS`可以提供一组关于哈希槽以及其管辖它的master和其slave节点的信息。

下面是`CLUSTER SLOTS`命令的示例：

```
127.0.0.1:7000> cluster slots
1) 1) (integer) 5461
   2) (integer) 10922
   3) 1) "127.0.0.1"
      2) (integer) 7001
   4) 1) "127.0.0.1"
      2) (integer) 7004
2) 1) (integer) 0
   2) (integer) 5460
   3) 1) "127.0.0.1"
      2) (integer) 7000
   4) 1) "127.0.0.1"
      2) (integer) 7003
3) 1) (integer) 10923
   2) (integer) 16383
   3) 1) "127.0.0.1"
      2) (integer) 7002
   4) 1) "127.0.0.1"
      2) (integer) 7005
```
每个返回数组中的前两个元素分别代表哈希槽的起始、结束位置。接下来的信息表示服务器的IP地址和端口信息。第一个IP、端口信息是管辖该哈希槽的master节点的地址信息，后续的IP、端口信息则是该master的slave节点信息，处于失败状态的slave节点不会在这里显示（slave的FAIL标记为被设置为true）。

比如说，第一个数组表示哈希槽5461到10922（包含起始和结尾）被节点127.0.0.1:7001管辖并提供服务，客户端也可以连接只读实例127.0.0.1:7004。

命令`CLUSTER SLOTS`不保证返回的哈希槽包含集群所有的16384个哈希槽，因为存在漏配的的情况，所以客户端因为记录好哪些哈希槽是未分配的，如果用户试图访问一个属于未被分配的哈希槽的key时，则应返还一个错误。

在向调用者返回该key所属哈希槽未被分配的错误前，Redis客户端应该尝试重新获取集群哈希槽分配关系记录，检查该哈希槽此时是否已经被分配了。


Multiple keys operations
---

Using hash tags, clients are free to use multi-key operations.
For example the following operation is valid:

    MSET {user:1000}.name Angela {user:1000}.surname White

Multi-key operations may become unavailable when a resharding of the
hash slot the keys belong to is in progress.

More specifically, even during a resharding the multi-key operations
targeting keys that all exist and are all still in the same node (either
the source or destination node) are still available.

Operations on keys that don't exist or are - during the resharding - split
between the source and destination nodes, will generate a `-TRYAGAIN` error.
The client can try the operation after some time, or report back the error.

As soon as migration of the specified hash slot has terminated, all
multi-key operations are available again for that hash slot.

多key操作
---

利用哈希标签，客户端可以进行多key操作，比如下面的多key操作是合法的：

    MSET {user:1000}.name Angela {user:1000}.surname White

在集群哈希槽迁移的过程中，多key操作可能会变得不可用。

特别的，即使在重新分配哈希槽的过程中，如果指定的一群key仍然还存在同一个节点中（都在老节点中或者都在新节点中），那么多key操作仍然可用。

如果多个key不在同在同一个节点中（一部分在老节点上，一部分在新节点上），此时对他们的多key操作将会收到一个`-TRYAGAIN`错误。客户端可以在稍后重试或者选择返回错误给调用者。

当指定哈希槽的迁移完成，所以对该哈希槽的多key操作又将变得可用。

Scaling reads using slave nodes
---

Normally slave nodes will redirect clients to the authoritative master for
the hash slot involved in a given command, however clients can use slaves
in order to scale reads using the `READONLY` command.

`READONLY` tells a Redis Cluster slave node that the client is ok reading
possibly stale data and is not interested in running write queries.

When the connection is in readonly mode, the cluster will send a redirection
to the client only if the operation involves keys not served
by the slave's master node. This may happen because:

1. The client sent a command about hash slots never served by the master of this slave.
2. The cluster was reconfigured (for example resharded) and the slave is no longer able to serve commands for a given hash slot.

When this happens the client should update its hashslot map as explained in
the previous sections.

The readonly state of the connection can be cleared using the `READWRITE` command.

使用slave节点分担读请求
---

通常来说，指定的命令都会被slave重定向给master节点，但是客户端可以利用slave节点来完成只读请求，从而提高读性能。

接受只读请求意味着slave节点可以读取本地可能过期的数据返回给客户端，但是对客户端的写操作不感兴趣。

当一个连接被设置为只读模式，slave节点仅仅在要服务的key不在其master节点的管辖范围时，才向客户端发送一个重定向错误。这种情况是有可能发生的，因为：

1. 客户端发送了一个key，该key所属的哈希槽不在其master节点的管辖范围
2. 集群处于重配置过程中（比如重分配哈希槽）并且slave节点无法为指定哈希槽提供服务了。

这种情况下，客户端应该及时更新哈希槽映射关系记录，这块内容之前章节已经阐述过了。

连接的只读状态可以通过`READWRITE`命令去除。

Fault Tolerance
===

Heartbeat and gossip messages
---

Redis Cluster nodes continuously exchange ping and pong packets. Those two kind of packets have the same structure, and both carry important configuration information. The only actual difference is the message type field. We'll refer to the sum of ping and pong packets as *heartbeat packets*.

Usually nodes send ping packets that will trigger the receivers to reply with pong packets. However this is not necessarily true. It is possible for nodes to just send pong packets to send information to other nodes about their configuration, without triggering a reply. This is useful, for example, in order to broadcast a new configuration as soon as possible.

Usually a node will ping a few random nodes every second so that the total number of ping packets sent (and pong packets received) by each node is a constant amount regardless of the number of nodes in the cluster.

However every node makes sure to ping every other node that hasn't sent a ping or received a pong for longer than half the `NODE_TIMEOUT` time. Before `NODE_TIMEOUT` has elapsed, nodes also try to reconnect the TCP link with another node to make sure nodes are not believed to be unreachable only because there is a problem in the current TCP connection.

The number of messages globally exchanged can be sizable if `NODE_TIMEOUT` is set to a small figure and the number of nodes (N) is very large, since every node will try to ping every other node for which they don't have fresh information every half the `NODE_TIMEOUT` time.

For example in a 100 node cluster with a node timeout set to 60 seconds, every node will try to send 99 pings every 30 seconds, with a total amount of pings of 3.3 per second. Multiplied by 100 nodes, this is 330 pings per second in the total cluster.

There are ways to lower the number of messages, however there have been no
reported issues with the bandwidth currently used by Redis Cluster failure
detection, so for now the obvious and direct design is used. Note that even
in the above example, the 330 packets per second exchanged are evenly
divided among 100 different nodes, so the traffic each node receives
is acceptable.

集群容错
===

心跳与gossip消息
---

Redis集群中的节点不断的交换ping和pong包。两种包拥有相同的结构，并且两个包里都包含了相当重要的信息。两个包唯一的不同仅仅是消息类型而已。我们将这两种包都统称为**心跳包**。

通常节点发送向另一个节点发送ping包，会使得接收者返回pong包响应。当然并不总是这样。节点也可以主动发送pong包来告诉其他节点它的配置信息，此时其它节点无需回复。这个特性非常有用，比如用来尽快向集群广播配置文件的更新信息。

通常来说，一个节点会每秒随机的ping集群中一小部分节点，所以每个节点发出的ping包（以及收到pong包）的总数都会保持不变，这个总数和集群共有多少个节点无关。

每个节点都监测着对其它节点的ping消息在`NODE_TIMEOUT/2`时间内是否成功返回pong消息。未收到pong消息的话，在`NODE_TIMEOUT`长时间前，节点也会尝试TCP重连该节点，确保未收到pong响应不是因为TCP连接问题。

如果将`NODE_TIMEOUT`设置得比较小，集群拥有的节点数量较多，那么信息交换的总次数是非常多的，因为每个节点都会尝试ping那些未在`NODE_TIMEOUT/2`时间内上报配置信息的节点（也就是说在这个时间内必须通过pong推送配置信息）。

比如一个有100个节点的集群，`NODE_TIMEOUT`被设置为60秒，此时每隔30秒每个节点都会发送99个ping包，也就是3.3个ping包每秒。乘以100个节点，也就是集群中每秒发生330个ping包交换。

其实也有办法降低集群中的配置信息交换次数，但是目前这种量级的交换次数情况下并未收到任何关于带宽问题的故障报告，所以目前还是使用这种直接了当的信息交换方式。注意上面的例子中，330个ping包其实是由100个节点分担的，所以对单个节点来说这种流量是可以接受的。

Heartbeat packet content
---

Ping and pong packets contain a header that is common to all types of packets (for instance packets to request a failover vote), and a special Gossip Section that is specific of Ping and Pong packets.

The common header has the following information:

* Node ID, a 160 bit pseudorandom string that is assigned the first time a node is created and remains the same for all the life of a Redis Cluster node.
* The `currentEpoch` and `configEpoch` fields of the sending node that are used to mount the distributed algorithms used by Redis Cluster (this is explained in detail in the next sections). If the node is a slave the `configEpoch` is the last known `configEpoch` of its master.
* The node flags, indicating if the node is a slave, a master, and other single-bit node information.
* A bitmap of the hash slots served by the sending node, or if the node is a slave, a bitmap of the slots served by its master.
* The sender TCP base port (that is, the port used by Redis to accept client commands; add 10000 to this to obtain the cluster bus port).
* The state of the cluster from the point of view of the sender (down or ok).
* The master node ID of the sending node, if it is a slave.

Ping and pong packets also contain a gossip section. This section offers to the receiver a view of what the sender node thinks about other nodes in the cluster. The gossip section only contains information about a few random nodes among the set of nodes known to the sender. The number of nodes mentioned in a gossip section is proportional to the cluster size.

For every node added in the gossip section the following fields are reported:

* Node ID.
* IP and port of the node.
* Node flags.

Gossip sections allow receiving nodes to get information about the state of other nodes from the point of view of the sender. This is useful both for failure detection and to discover other nodes in the cluster.

心跳包内容
---

ping包和pong包和其他所有包一样，都包含了一个同样的数据头（例如请求故障转移时master投票的包），以及一个专门针对ping和pong包的gossip信息段。

同样数据头中包含以下部分信息：

* 节点ID，一个160位的随机字符串，在节点启动时随机分配，在节点的整个生命周期中，该ID都是其在集群中的唯一标示。
* 发送节点的`当前配置版本号`和`配置版本号`属性，这是Redis集群分布式管理算法关键元素（会在下一章节描述）。如果节点是一个slave节点，那么它的`配置版本号`就是它最后一次得知的其master节点的版本号。
* 节点标记位，表明节点是一个master还是一个slave，以及其他可能的单bit就能标示的节点信息。
* 发送节点管辖的哈希槽的位图，如果发送节点是一个slave节点，则是其master节点管辖的哈希槽的位图。
* 发送节点对外提供服务的端口（也就是接收客户端连接的端口；加上1000则得到集群总线端口）
* 发送节点认为的服务器的状态
* 其master节点的节点ID（如果发送节点是个slave节点）

ping包和pong包也包含一个gossip段。这个段记录了在发送者的视角里，目前集群中其它节点的状态。这个gossip段仅仅包含一部分其它节点的信息（随机的）。gossip段包含了其它节点的信息的个数取决于集群的大小。

gossip段中每个节点信息都包含以下属性：
* 节点ID
* 节点的IP地址和端口
* 节点标记位

Gossip段使得消息接收者能够知晓在发送者眼里其它节点的状态。这对发现失活的节点以及新加入的节点都非常有用。

Failure detection
---

Redis Cluster failure detection is used to recognize when a master or slave node is no longer reachable by the majority of nodes and then respond by promoting a slave to the role of master. When slave promotion is not possible the cluster is put in an error state to stop receiving queries from clients.

As already mentioned, every node takes a list of flags associated with other known nodes. There are two flags that are used for failure detection that are called `PFAIL` and `FAIL`. `PFAIL` means *Possible failure*, and is a non-acknowledged failure type. `FAIL` means that a node is failing and that this condition was confirmed by a majority of masters within a fixed amount of time.

**PFAIL flag:**

A node flags another node with the `PFAIL` flag when the node is not reachable for more than `NODE_TIMEOUT` time. Both master and slave nodes can flag another node as `PFAIL`, regardless of its type.

The concept of non-reachability for a Redis Cluster node is that we have an **active ping** (a ping that we sent for which we have yet to get a reply) pending for longer than `NODE_TIMEOUT`. For this mechanism to work the `NODE_TIMEOUT` must be large compared to the network round trip time. In order to add reliability during normal operations, nodes will try to reconnect with other nodes in the cluster as soon as half of the `NODE_TIMEOUT` has elapsed without a reply to a ping. This mechanism ensures that connections are kept alive so broken connections usually won't result in false failure reports between nodes.

**FAIL flag:**

The `PFAIL` flag alone is just local information every node has about other nodes, but it is not sufficient to trigger a slave promotion. For a node to be considered down the `PFAIL` condition needs to be escalated to a `FAIL` condition.

As outlined in the node heartbeats section of this document, every node sends gossip messages to every other node including the state of a few random known nodes. Every node eventually receives a set of node flags for every other node. This way every node has a mechanism to signal other nodes about failure conditions they have detected.

A `PFAIL` condition is escalated to a `FAIL` condition when the following set of conditions are met:

* Some node, that we'll call A, has another node B flagged as `PFAIL`.
* Node A collected, via gossip sections, information about the state of B from the point of view of the majority of masters in the cluster.
* The majority of masters signaled the `PFAIL` or `FAIL` condition within `NODE_TIMEOUT * FAIL_REPORT_VALIDITY_MULT` time. (The validity factor is set to 2 in the current implementation, so this is just two times the `NODE_TIMEOUT` time).

If all the above conditions are true, Node A will:

* Mark the node as `FAIL`.
* Send a `FAIL` message to all the reachable nodes.

The `FAIL` message will force every receiving node to mark the node in `FAIL` state, whether or not it already flagged the node in `PFAIL` state.

Note that *the FAIL flag is mostly one way*. That is, a node can go from `PFAIL` to `FAIL`, but a `FAIL` flag can only be cleared in the following situations:

* The node is already reachable and is a slave. In this case the `FAIL` flag can be cleared as slaves are not failed over.
* The node is already reachable and is a master not serving any slot. In this case the `FAIL` flag can be cleared as masters without slots do not really participate in the cluster and are waiting to be configured in order to join the cluster.
* The node is already reachable and is a master, but a long time (N times the `NODE_TIMEOUT`) has elapsed without any detectable slave promotion. It's better for it to rejoin the cluster and continue in this case.

It is useful to note that while the `PFAIL` -> `FAIL` transition uses a form of agreement, the agreement used is weak:

1. Nodes collect views of other nodes over some time period, so even if the majority of master nodes need to "agree", actually this is just state that we collected from different nodes at different times and we are not sure, nor we require, that at a given moment the majority of masters agreed. However we discard failure reports which are old, so the failure was signaled by the majority of masters within a window of time.
2. While every node detecting the `FAIL` condition will force that condition on other nodes in the cluster using the `FAIL` message, there is no way to ensure the message will reach all the nodes. For instance a node may detect the `FAIL` condition and because of a partition will not be able to reach any other node.

However the Redis Cluster failure detection has a liveness requirement: eventually all the nodes should agree about the state of a given node. There are two cases that can originate from split brain conditions. Either some minority of nodes believe the node is in `FAIL` state, or a minority of nodes believe the node is not in `FAIL` state. In both the cases eventually the cluster will have a single view of the state of a given node:

**Case 1**: If a majority of masters have flagged a node as `FAIL`, because of failure detection and the *chain effect* it generates, every other node will eventually flag the master as `FAIL`, since in the specified window of time enough failures will be reported.

**Case 2**: When only a minority of masters have flagged a node as `FAIL`, the slave promotion will not happen (as it uses a more formal algorithm that makes sure everybody knows about the promotion eventually) and every node will clear the `FAIL` state as per the `FAIL` state clearing rules above (i.e. no promotion after N times the `NODE_TIMEOUT` has elapsed).

**The `FAIL` flag is only used as a trigger to run the safe part of the algorithm** for the slave promotion. In theory a slave may act independently and start a slave promotion when its master is not reachable, and wait for the masters to refuse to provide the acknowledgment if the master is actually reachable by the majority. However the added complexity of the `PFAIL -> FAIL` state, the weak agreement, and the `FAIL` message forcing the propagation of the state in the shortest amount of time in the reachable part of the cluster, have practical advantages. Because of these mechanisms, usually all the nodes will stop accepting writes at about the same time if the cluster is in an error state. This is a desirable feature from the point of view of applications using Redis Cluster. Also erroneous election attempts initiated by slaves that can't reach its master due to local problems (the master is otherwise reachable by the majority of other master nodes) are avoided.

失活检测
---

Redis集群失活检测用于识别集群中那些与大多数节点都失联的master或slave节点，随后提升相应的slave节点为master节点。当发生故障时若无法将slave提升为master，那么整个集群将转为不可用状态，无法为客户端提供服务。

之前已经提到，每个节点都存有其他节点的标记位信息列表。其中有两个标记位称为`PFAIL` 和 `FAIL`，专用于失活检测的。`PFAIL`表示可能失活了，是一个不完全确定的状态类型。`FAIL`则代表则一个节点已经失活，这个结果已经在指定时间内被集群中大多数节点所认同。

**标记位PFAIL:**

当一个节点发现另一个节点在`NODE_TIMEOUT`时间内都无法联系到时，它会标记该节点为`PFAIL`状态。master节点和slave节点都可以将其他节点标记为`PFAIL`状态，不管对方是master还是slave节点。

在Redis集群中，与某个节点失联的概念是向该节点发送的**活跃ping包**（一个还没有收到响应的ping包）等待了超过`NODE_TIMEOUT`长时间还没收到回复。为了使这种机制能正常工作，设置的`NODE_TIMEOUT`必须比一次网络请求往返花费的时间长。为了增加实际操作时的可靠性，当一个节点在`NODE_TIMEOUT/2`未收到某节点响应时就会尝试与该节点重新建立TCP连接。这个技巧保证了网络连接的问题不会导致出现节点失活的状况。

**标记位FAIL**

标记位`PFAIL`相当于各节点自身对其他节点状态的看法，并不会导致集群进行一次slave提升过程。一个节点从`PFAIL`状态到实际被判定为离线，需要从状态`PFAIL`转换到`FAIL`。

正如本文“节点心跳”章节描述的一样，每个节点都会随机向其它节点发送包含状态的gossip消息。每个节点也会从各个其他节点那里收到各个节点标记位信息。这种机制使得各个节点都有手段通知其他节点关于它所发现的某些节点失活的情况。

一个`PFAIL`状态在满足以下情况下会转换为`FAIL`状态：

* 首先我们有两个节点，A节点认为B节点失活，并将其标记为`PFAIL`
* 节点A通过gosssip段信息收集了集群中大多数master节点对于B节点的看法
* 大多数节点都在`NODE_TIMEOUT * FAIL_REPORT_VALIDITY_MULT` 时间内将B标记为 `PFAIL` 或 `FAIL`状态。（这个时间有效系数暂被设置为2，所以也就是2倍的`NODE_TIMEOUT`时间内）

如果上述所有的条件都满足了，节点会做以下事情：

* 标记B节点为`FAIL`状态
* 向集群中其它可达的节点发送B节点离线的消息

这个`FAIL`消息会强制的让每个接收到该消息的节点都将B节点标记为`FAIL`状态，不管目前它是否已经将B节点标记为`PFAIL`状态。

注意*FAIL状态可以认为是单向*。也就是说，一个节点可以从`PFAIL`状态转换到`FAIL`状态，但是`FAIL`只能通过以下几种情况才能被清除：

* 该节点再次变得可达并且是一个slave节点。在这种情况下其`FAIL`标记将被清除，因为slave节点不需要故障恢复。
* 该节点再次变得可达并且是一个master节点，但不管辖任何哈希槽。在这种情况下`FAIL`标记将被清除，因为不管辖哈希槽的master节点并并没有实际参与集群的服务工作，它只能等待管理员重新为其分配哈希槽才能真正融入集群。

* 该节点再次变得可达并且是一个master节点，但是经过很长时间（N个`NODE_TIMEOUT`时间）都没有可用的slave节点能提升为master节点来代替它。这种情况下最好是把这个节点从集群中移除再重新加入。

可以发现，从`PFAIL` 到 `FAIL`的转换使用了一个协议，这个协议是一个弱协议：

1. 节点在指定时间周期内收集其它节点关于集群节点状态的视图信息，所以即使我们发现集群中的大多数集群都表示“同意观点”，但是这也仅仅是我们在不同时间内，不同节点上收集的信息，我们无法确定是否在某一个时刻集群中的大多数节点都表示“同意观点”。我们接收到的状态报告其实有可能已经是陈旧的了，从开始失活到大多数节点发现该节点失活有一个时间窗口。
2. 检测到故障的节点会向其它发送`FAIL`消息来强制其它节点将该节点标记为离线，但是无法确定节点都收到了这个消息。比如一个节点就算发现了集群中的故障，但也可能由于网络分区`FAIL`传输不到任何其它节点上。

这样设计是因为Redis集群对失活检测有一个活性要求：   
最终所有的节点都必须就指定节点的状态达成一致。当集群出现脑裂情况将导致节点分为两种状态。一部分节点认为指定节点是`FAIL`状态，另一部分节点则认为指定没有失活。这两类节点最终都会对指定的节点的状态达成一致。

**情况1**：如果大多数节点都将该节点标记为`FAIL`状态，由于`FAIL`链式传播并且强制执行的，其它节点最终都会将该节点标记为`FAIL`，因为在指定窗口时间内足够产生够多的失活统计。

**情况2**：只有一小部分节点将该节点标记为`FAIL`状态时，不会发生slave提升过程（它使用一个更加正规的算法，保证集群中每个节点都最终知道提升事件），各个节点会根据之前提到的规则来清除`FAIL`状态（也就是在N各`NODE_TIMEOUT`时间后仍然没有slave提升则会清除状态）。

**这个`FAIL`标记仅仅是触发slave安全提升算法的一个触发器而已**。理论上来说，一个slave节点可以在发现主节点不可用时独立的完成slave提升过程，之后如果主节点仍然对于集群大多数节点来说是可用的，那么主节点将拒绝认可这次提升事件。然而通过增加稍复杂的`PFAIL -> FAIL`转换过程，弱的一致性协议，以及`FAIL`消息，使得节点状态信息在最短的时间内在集群可达节点中传播开来，虽然增加了复杂性却有实际好处。由于这些机制，集群中的节点几乎在同一时间就会因为集群不可用而停止写服务（写快速失败）。这从Redis的角度来看，是一个很理想的特性。同时也避免了那些无法到达其master节点的slave节点试图发起不必要的slave提升的情况（其实该master在集群大多数节点眼中还是可用的）。

Configuration handling, propagation, and failovers
===

Cluster current epoch
---

Redis Cluster uses a concept similar to the Raft algorithm "term". In Redis Cluster the term is called epoch instead, and it is used in order to give incremental versioning to events. When multiple nodes provide conflicting information, it becomes possible for another node to understand which state is the most up to date.

The `currentEpoch` is a 64 bit unsigned number.

At node creation every Redis Cluster node, both slaves and master nodes, set the `currentEpoch` to 0.

Every time a packet is received from another node, if the epoch of the sender (part of the cluster bus messages header) is greater than the local node epoch, the `currentEpoch` is updated to the sender epoch.

Because of these semantics, eventually all the nodes will agree to the greatest `configEpoch` in the cluster.

This information is used when the state of the cluster is changed and a node seeks agreement in order to perform some action.

Currently this happens only during slave promotion, as described in the next section. Basically the epoch is a logical clock for the cluster and dictates that given information wins over one with a smaller epoch.

配置处理、传播及故障处理
===

集群配置当前版本号
---

Redis集群使用了和Raft协议的“term”（学期）很像的一个概念。在Redis集群中使用一个叫做“版本号”（可以称之为纪元，但用熟悉的版本号更好理解，一个版本号类似一个阶段）的术语，他用于配置信息的增量控制。当多个节点提供了冲突性的配置信息时，各节点可以使用版本号来判定哪个配置信息是最新的。

这个`集群状态版本号`是一个64位的无符号整型。

当集群节点创建时，每个节点，不管master还是slave，都将`集群状态版本号`设置为0.

当节点收到一个消息包，如果其中发生者的版本号（在集群总线消息的通用数据头中）比当前节点的版本号大，那么`集群状态版本号`会被更新为发送者的版本号。

这种情况发生在集群状态发生了一些改变，某个节点尝试执行一些操作。

目前这种情况仅仅发生在slave提升的过程中，将在下一章节描述。大致来说，版本号是一个集群的逻辑时钟，它表示版本号更大的状态信息是最新的。

Configuration epoch
---

Every master always advertises its `configEpoch` in ping and pong packets along with a bitmap advertising the set of slots it serves.

The `configEpoch` is set to zero in masters when a new node is created.

A new `configEpoch` is created during slave election. Slaves trying to replace
failing masters increment their epoch and try to get authorization from
a majority of masters. When a slave is authorized, a new unique `configEpoch`
is created and the slave turns into a master using the new `configEpoch`.

As explained in the next sections the `configEpoch` helps to resolve conflicts when different nodes claim divergent configurations (a condition that may happen because of network partitions and node failures).

Slave nodes also advertise the `configEpoch` field in ping and pong packets, but in the case of slaves the field represents the `configEpoch` of its master as of the last time they exchanged packets. This allows other instances to detect when a slave has an old configuration that needs to be updated (master nodes will not grant votes to slaves with an old configuration).

Every time the `configEpoch` changes for some known node, it is permanently stored in the nodes.conf file by all the nodes that receive this information. The same also happens for the `currentEpoch` value. These two variables are guaranteed to be saved and `fsync-ed` to disk when updated before a node continues its operations.

The `configEpoch` values generated using a simple algorithm during failovers
are guaranteed to be new, incremental, and unique.

配置版本号
---

每个master节点总是将它的版本号信息和管辖的哈希槽一起放入ping包和pong包中。

这个`配置版本号`在新节点创建时总是初设置为0。

在slave选举时会产生一个新的`配置版本号`。slave节点尝试替代失活的master节点的工作，提升它们的版本号，并征得集群中大多数master节点的授权。当slave被成功授权，会转变为master节点并会产生一个新的唯一`配置纪元`。

下个章节会解释`配置`纪元如何解决不同节点声明不同配置时的冲突问题（可能是网络分区引发的节点失败）。

从节点也会在ping包pong包带上`配置版本号`信息，但是这个`配置版本号`只是它与其master交换时获得的最新一个`配置版本号`。这使得其它节点可以很快的发现slave节点的配置是否需要更新（master节点不会给是旧`配置版本号`的slave节点投票）。

每当节点的`配置版本号`被更新，都会存储在其nodes.conf文件中。`集群状态版本号`版本号也是一样。一旦更新，节点保证在执行其它操作之前，将这两个变量同步写入到本地磁盘中。

当一个节点重故障中恢复，其生成`配置版本号`的是目前集群中最新的。

Slave election and promotion
---

Slave election and promotion is handled by slave nodes, with the help of master nodes that vote for the slave to promote.
A slave election happens when a master is in `FAIL` state from the point of view of at least one of its slaves that has the prerequisites in order to become a master.

In order for a slave to promote itself to master, it needs to start an election and win it. All the slaves for a given master can start an election if the master is in `FAIL` state, however only one slave will win the election and promote itself to master.

A slave starts an election when the following conditions are met:

* The slave's master is in `FAIL` state.
* The master was serving a non-zero number of slots.
* The slave replication link was disconnected from the master for no longer than a given amount of time, in order to ensure the promoted slave's data is reasonably fresh. This time is user configurable.

In order to be elected, the first step for a slave is to increment its `currentEpoch` counter, and request votes from master instances.

Votes are requested by the slave by broadcasting a `FAILOVER_AUTH_REQUEST` packet to every master node of the cluster. Then it waits for a maximum time of two times the `NODE_TIMEOUT` for replies to arrive (but always for at least 2 seconds).

Once a master has voted for a given slave, replying positively with a `FAILOVER_AUTH_ACK`, it can no longer vote for another slave of the same master for a period of `NODE_TIMEOUT * 2`. In this period it will not be able to reply to other authorization requests for the same master. This is not needed to guarantee safety, but useful for preventing multiple slaves from getting elected (even if with a different `configEpoch`) at around the same time, which is usually not wanted.

A slave discards any `AUTH_ACK` replies with an epoch that is less than the `currentEpoch` at the time the vote request was sent. This ensures it doesn't count votes intended for a previous election.

Once the slave receives ACKs from the majority of masters, it wins the election.
Otherwise if the majority is not reached within the period of two times `NODE_TIMEOUT` (but always at least 2 seconds), the election is aborted and a new one will be tried again after `NODE_TIMEOUT * 4` (and always at least 4 seconds).

Slave rank
---

As soon as a master is in `FAIL` state, a slave waits a short period of time before trying to get elected. That delay is computed as follows:

    DELAY = 500 milliseconds + random delay between 0 and 500 milliseconds +
            SLAVE_RANK * 1000 milliseconds.

The fixed delay ensures that we wait for the `FAIL` state to propagate across the cluster, otherwise the slave may try to get elected while the masters are still unaware of the `FAIL` state, refusing to grant their vote.

The random delay is used to desynchronize slaves so they're unlikely to start an election at the same time.

The `SLAVE_RANK` is the rank of this slave regarding the amount of replication data it has processed from the master.
Slaves exchange messages when the master is failing in order to establish a (best effort) rank:
the slave with the most updated replication offset is at rank 0, the second most updated at rank 1, and so forth.
In this way the most updated slaves try to get elected before others.

Rank order is not strictly enforced; if a slave of higher rank fails to be
elected, the others will try shortly.

Once a slave wins the election, it obtains a new unique and incremental `configEpoch` which is higher than that of any other existing master. It starts advertising itself as master in ping and pong packets, providing the set of served slots with a `configEpoch` that will win over the past ones.

In order to speedup the reconfiguration of other nodes, a pong packet is broadcast to all the nodes of the cluster. Currently unreachable nodes will eventually be reconfigured when they receive a ping or pong packet from another node or will receive an `UPDATE` packet from another node if the information it publishes via heartbeat packets are detected to be out of date.

The other nodes will detect that there is a new master serving the same slots served by the old master but with a greater `configEpoch`, and will upgrade their configuration. Slaves of the old master (or the failed over master if it rejoins the cluster) will not just upgrade the configuration but will also reconfigure to replicate from the new master. How nodes rejoining the cluster are configured is explained in the next sections.

Masters reply to slave vote request
---

In the previous section it was discussed how slaves try to get elected. This section explains what happens from the point of view of a master that is requested to vote for a given slave.

Masters receive requests for votes in form of `FAILOVER_AUTH_REQUEST` requests from slaves.

For a vote to be granted the following conditions need to be met:

1. A master only votes a single time for a given epoch, and refuses to vote for older epochs: every master has a lastVoteEpoch field and will refuse to vote again as long as the `currentEpoch` in the auth request packet is not greater than the lastVoteEpoch. When a master replies positively to a vote request, the lastVoteEpoch is updated accordingly, and safely stored on disk.
2. A master votes for a slave only if the slave's master is flagged as `FAIL`.
3. Auth requests with a `currentEpoch` that is less than the master `currentEpoch` are ignored. Because of this the master reply will always have the same `currentEpoch` as the auth request. If the same slave asks again to be voted, incrementing the `currentEpoch`, it is guaranteed that an old delayed reply from the master can not be accepted for the new vote.

Example of the issue caused by not using rule number 3:

Master `currentEpoch` is 5, lastVoteEpoch is 1 (this may happen after a few failed elections)

* Slave `currentEpoch` is 3.
* Slave tries to be elected with epoch 4 (3+1), master replies with an ok with `currentEpoch` 5, however the reply is delayed.
* Slave will try to be elected again, at a later time, with epoch 5 (4+1), the delayed reply reaches the slave with `currentEpoch` 5, and is accepted as valid.

4. Masters don't vote for a slave of the same master before `NODE_TIMEOUT * 2` has elapsed if a slave of that master was already voted for. This is not strictly required as it is not possible for two slaves to win the election in the same epoch. However, in practical terms it ensures that when a slave is elected it has plenty of time to inform the other slaves and avoid the possibility that another slave will win a new election, performing an unnecessary second failover.
5. Masters make no effort to select the best slave in any way. If the slave's master is in `FAIL` state and the master did not vote in the current term, a positive vote is granted. The best slave is the most likely to start an election and win it before the other slaves, since it will usually be able to start the voting process earlier because of its *higher rank* as explained in the previous section.
6. When a master refuses to vote for a given slave there is no negative response, the request is simply ignored.
7. Masters don't vote for slaves sending a `configEpoch` that is less than any `configEpoch` in the master table for the slots claimed by the slave. Remember that the slave sends the `configEpoch` of its master, and the bitmap of the slots served by its master. This means that the slave requesting the vote must have a configuration for the slots it wants to failover that is newer or equal the one of the master granting the vote.

Practical example of configuration epoch usefulness during partitions
---

This section illustrates how the epoch concept is used to make the slave promotion process more resistant to partitions.

* A master is no longer reachable indefinitely. The master has three slaves A, B, C.
* Slave A wins the election and is promoted to master.
* A network partition makes A not available for the majority of the cluster.
* Slave B wins the election and is promoted as master.
* A partition makes B not available for the majority of the cluster.
* The previous partition is fixed, and A is available again.

At this point B is down and A is available again with a role of master (actually `UPDATE` messages would reconfigure it promptly, but here we assume all `UPDATE` messages were lost). At the same time, slave C will try to get elected in order to fail over B. This is what happens:

1. C will try to get elected and will succeed, since for the majority of masters its master is actually down. It will obtain a new incremental `configEpoch`.
2. A will not be able to claim to be the master for its hash slots, because the other nodes already have the same hash slots associated with a higher configuration epoch (the one of B) compared to the one published by A.
3. So, all the nodes will upgrade their table to assign the hash slots to C, and the cluster will continue its operations.

As you'll see in the next sections, a stale node rejoining a cluster
will usually get notified as soon as possible about the configuration change
because as soon as it pings any other node, the receiver will detect it
has stale information and will send an `UPDATE` message.

Hash slots configuration propagation
---

An important part of Redis Cluster is the mechanism used to propagate the information about which cluster node is serving a given set of hash slots. This is vital to both the startup of a fresh cluster and the ability to upgrade the configuration after a slave was promoted to serve the slots of its failing master.

The same mechanism allows nodes partitioned away for an indefinite amount of
time to rejoin the cluster in a sensible way.

There are two ways hash slot configurations are propagated:

1. Heartbeat messages. The sender of a ping or pong packet always adds information about the set of hash slots it (or its master, if it is a slave) serves.
2. `UPDATE` messages. Since in every heartbeat packet there is information about the sender `configEpoch` and set of hash slots served, if a receiver of a heartbeat packet finds the sender information is stale, it will send a packet with new information, forcing the stale node to update its info.

The receiver of a heartbeat or `UPDATE` message uses certain simple rules in
order to update its table mapping hash slots to nodes. When a new Redis Cluster node is created, its local hash slot table is simply initialized to `NULL` entries so that each hash slot is not bound or linked to any node. This looks similar to the following:

```
0 -> NULL
1 -> NULL
2 -> NULL
...
16383 -> NULL
```

The first rule followed by a node in order to update its hash slot table is the following:

**Rule 1**: If a hash slot is unassigned (set to `NULL`), and a known node claims it, I'll modify my hash slot table and associate the claimed hash slots to it.

So if we receive a heartbeat from node A claiming to serve hash slots 1 and 2 with a configuration epoch value of 3, the table will be modified to:

```
0 -> NULL
1 -> A [3]
2 -> A [3]
...
16383 -> NULL
```

When a new cluster is created, a system administrator needs to manually assign (using the `CLUSTER ADDSLOTS` command, via the redis-trib command line tool, or by any other means) the slots served by each master node only to the node itself, and the information will rapidly propagate across the cluster.

However this rule is not enough. We know that hash slot mapping can change
during two events:

1. A slave replaces its master during a failover.
2. A slot is resharded from a node to a different one.

For now let's focus on failovers. When a slave fails over its master, it obtains
a configuration epoch which is guaranteed to be greater than the one of its
master (and more generally greater than any other configuration epoch
generated previously). For example node B, which is a slave of A, may failover
B with configuration epoch of 4. It will start to send heartbeat packets
(the first time mass-broadcasting cluster-wide) and because of the following
second rule, receivers will update their hash slot tables:

**Rule 2**: If a hash slot is already assigned, and a known node is advertising it using a `configEpoch` that is greater than the `configEpoch` of the master currently associated with the slot, I'll rebind the hash slot to the new node.

So after receiving messages from B that claim to serve hash slots 1 and 2 with configuration epoch of 4, the receivers will update their table in the following way:

```
0 -> NULL
1 -> B [4]
2 -> B [4]
...
16383 -> NULL
```

Liveness property: because of the second rule, eventually all nodes in the cluster will agree that the owner of a slot is the one with the greatest `configEpoch` among the nodes advertising it.

This mechanism in Redis Cluster is called **last failover wins**.

The same happens during reshardings. When a node importing a hash slot
completes the import operation, its configuration epoch is incremented to make
sure the change will be propagated throughout the cluster.

UPDATE messages, a closer look
---

With the previous section in mind, it is easier to see how update messages
work. Node A may rejoin the cluster after some time. It will send heartbeat
packets where it claims it serves hash slots 1 and 2 with configuration epoch
of 3. All the receivers with updated information will instead see that
the same hash slots are associated with node B having an higher configuration
epoch. Because of this they'll send an `UPDATE` message to A with the new
configuration for the slots. A will update its configuration because of the
**rule 2** above.

How nodes rejoin the cluster
---

The same basic mechanism is used when a node rejoins a cluster.
Continuing with the example above, node A will be notified
that hash slots 1 and 2 are now served by B. Assuming that these two were
the only hash slots served by A, the count of hash slots served by A will
drop to 0! So A will **reconfigure to be a slave of the new master**.

The actual rule followed is a bit more complex than this. In general it may
happen that A rejoins after a lot of time, in the meantime it may happen that
hash slots originally served by A are served by multiple nodes, for example
hash slot 1 may be served by B, and hash slot 2 by C.

So the actual *Redis Cluster node role switch rule* is: **A master node will change its configuration to replicate (be a slave of) the node that stole its last hash slot**.

During reconfiguration, eventually the number of served hash slots will drop to zero, and the node will reconfigure accordingly. Note that in the base case this just means that the old master will be a slave of the slave that replaced it after a failover. However in the general form the rule covers all possible cases.

Slaves do exactly the same: they reconfigure to replicate the node that
stole the last hash slot of its former master.

Replica migration
---

Redis Cluster implements a concept called *replica migration* in order to
improve the availability of the system. The idea is that in a cluster with
a master-slave setup, if the map between slaves and masters is fixed
availability is limited over time if multiple independent failures of single
nodes happen.

For example in a cluster where every master has a single slave, the cluster
can continue operations as long as either the master or the slave fail, but not
if both fail the same time. However there is a class of failures that are
the independent failures of single nodes caused by hardware or software issues
that can accumulate over time. For example:

* Master A has a single slave A1.
* Master A fails. A1 is promoted as new master.
* Three hours later A1 fails in an independent manner (unrelated to the failure of A). No other slave is available for promotion since node A is still down. The cluster cannot continue normal operations.

If the map between masters and slaves is fixed, the only way to make the cluster
more resistant to the above scenario is to add slaves to every master, however
this is costly as it requires more instances of Redis to be executed, more
memory, and so forth.

An alternative is to create an asymmetry in the cluster, and let the cluster
layout automatically change over time. For example the cluster may have three
masters A, B, C. A and B have a single slave each, A1 and B1. However the master
C is different and has two slaves: C1 and C2.

Replica migration is the process of automatic reconfiguration of a slave
in order to *migrate* to a master that has no longer coverage (no working
slaves). With replica migration the scenario mentioned above turns into the
following:

* Master A fails. A1 is promoted.
* C2 migrates as slave of A1, that is otherwise not backed by any slave.
* Three hours later A1 fails as well.
* C2 is promoted as new master to replace A1.
* The cluster can continue the operations.

Replica migration algorithm
---

The migration algorithm does not use any form of agreement since the slave
layout in a Redis Cluster is not part of the cluster configuration that needs
to be consistent and/or versioned with config epochs. Instead it uses an
algorithm to avoid mass-migration of slaves when a master is not backed.
The algorithm guarantees that eventually (once the cluster configuration is
stable) every master will be backed by at least one slave.

This is how the algorithm works. To start we need to define what is a
*good slave* in this context: a good slave is a slave not in `FAIL` state
from the point of view of a given node.

The execution of the algorithm is triggered in every slave that detects that
there is at least a single master without good slaves. However among all the
slaves detecting this condition, only a subset should act. This subset is
actually often a single slave unless different slaves have in a given moment
a slightly different view of the failure state of other nodes.

The *acting slave* is the slave among the masters with the maximum number
of attached slaves, that is not in FAIL state and has the smallest node ID.

So for example if there are 10 masters with 1 slave each, and 2 masters with
5 slaves each, the slave that will try to migrate is - among the 2 masters
having 5 slaves - the one with the lowest node ID. Given that no agreement
is used, it is possible that when the cluster configuration is not stable,
a race condition occurs where multiple slaves believe themselves to be
the non-failing slave with the lower node ID (it is unlikely for this to happen
in practice). If this happens, the result is multiple slaves migrating to the
same master, which is harmless. If the race happens in a way that will leave
the ceding master without slaves, as soon as the cluster is stable again
the algorithm will be re-executed again and will migrate a slave back to
the original master.

Eventually every master will be backed by at least one slave. However,
the normal behavior is that a single slave migrates from a master with
multiple slaves to an orphaned master.

The algorithm is controlled by a user-configurable parameter called
`cluster-migration-barrier`: the number of good slaves a master
must be left with before a slave can migrate away. For example, if this
parameter is set to 2, a slave can try to migrate only if its master remains
with two working slaves.

configEpoch conflicts resolution algorithm
---

When new `configEpoch` values are created via slave promotion during
failovers, they are guaranteed to be unique.

However there are two distinct events where new configEpoch values are
created in an unsafe way, just incrementing the local `currentEpoch` of
the local node and hoping there are no conflicts at the same time.
Both the events are system-administrator triggered:

1. `CLUSTER FAILOVER` command with `TAKEOVER` option is able to manually promote a slave node into a master *without the majority of masters being available*. This is useful, for example, in multi data center setups.
2. Migration of slots for cluster rebalancing also generates new configuration epochs inside the local node without agreement for performance reasons.

Specifically, during manual reshardings, when a hash slot is migrated from
a node A to a node B, the resharding program will force B to upgrade
its configuration to an epoch which is the greatest found in the cluster,
plus 1 (unless the node is already the one with the greatest configuration
epoch), without requiring agreement from other nodes.
Usually a real world resharding involves moving several hundred hash slots
(especially in small clusters). Requiring an agreement to generate new
configuration epochs during reshardings, for each hash slot moved, is
inefficient. Moreover it requires an fsync in each of the cluster nodes
every time in order to store the new configuration. Because of the way it is
performed instead, we only need a new config epoch when the first hash slot is moved,
making it much more efficient in production environments.

However because of the two cases above, it is possible (though unlikely) to end
with multiple nodes having the same configuration epoch. A resharding operation
performed by the system administrator, and a failover happening at the same
time (plus a lot of bad luck) could cause `currentEpoch` collisions if
they are not propagated fast enough.

Moreover, software bugs and filesystem corruptions can also contribute
to multiple nodes having the same configuration epoch.

When masters serving different hash slots have the same `configEpoch`, there
are no issues. It is more important that slaves failing over a master have
unique configuration epochs.

That said, manual interventions or reshardings may change the cluster
configuration in different ways. The Redis Cluster main liveness property
requires that slot configurations always converge, so under every circumstance
we really want all the master nodes to have a different `configEpoch`.

In order to enforce this, **a conflict resolution algorithm** is used in the
event that two nodes end up with the same `configEpoch`.

* IF a master node detects another master node is advertising itself with
the same `configEpoch`.
* AND IF the node has a lexicographically smaller Node ID compared to the other node claiming the same `configEpoch`.
* THEN it increments its `currentEpoch` by 1, and uses it as the new `configEpoch`.

If there are any set of nodes with the same `configEpoch`, all the nodes but the one with the greatest Node ID will move forward, guaranteeing that, eventually, every node will pick a unique configEpoch regardless of what happened.

This mechanism also guarantees that after a fresh cluster is created, all
nodes start with a different `configEpoch` (even if this is not actually
used) since `redis-trib` makes sure to use `CONFIG SET-CONFIG-EPOCH` at startup.
However if for some reason a node is left misconfigured, it will update
its configuration to a different configuration epoch automatically.

Node resets
---

Nodes can be software reset (without restarting them) in order to be reused
in a different role or in a different cluster. This is useful in normal
operations, in testing, and in cloud environments where a given node can
be reprovisioned to join a different set of nodes to enlarge or create a new
cluster.

In Redis Cluster nodes are reset using the `CLUSTER RESET` command. The
command is provided in two variants:

* `CLUSTER RESET SOFT`
* `CLUSTER RESET HARD`

The command must be sent directly to the node to reset. If no reset type is
provided, a soft reset is performed.

The following is a list of operations performed by a reset:

1. Soft and hard reset: If the node is a slave, it is turned into a master, and its dataset is discarded. If the node is a master and contains keys the reset operation is aborted.
2. Soft and hard reset: All the slots are released, and the manual failover state is reset.
3. Soft and hard reset: All the other nodes in the nodes table are removed, so the node no longer knows any other node.
4. Hard reset only: `currentEpoch`, `configEpoch`, and `lastVoteEpoch` are set to 0.
5. Hard reset only: the Node ID is changed to a new random ID.

Master nodes with non-empty data sets can't be reset (since normally you want to reshard data to the other nodes). However, under special conditions when this is appropriate (e.g. when a cluster is totally destroyed with the intent of creating a new one), `FLUSHALL` must be executed before proceeding with the reset.

Removing nodes from a cluster
---

It is possible to practically remove a node from an existing cluster by
resharding all its data to other nodes (if it is a master node) and
shutting it down. However, the other nodes will still remember its node
ID and address, and will attempt to connect with it.

For this reason, when a node is removed we want to also remove its entry
from all the other nodes tables. This is accomplished by using the
`CLUSTER FORGET <node-id>` command.

The command does two things:

1. It removes the node with the specified node ID from the nodes table.
2. It sets a 60 second ban which prevents a node with the same node ID from being re-added.

The second operation is needed because Redis Cluster uses gossip in order to auto-discover nodes, so removing the node X from node A, could result in node B gossiping about node X to A again. Because of the 60 second ban, the Redis Cluster administration tools have 60 seconds in order to remove the node from all the nodes, preventing the re-addition of the node due to auto discovery.

Further information is available in the `CLUSTER FORGET` documentation.

Publish/Subscribe
===

In a Redis Cluster clients can subscribe to every node, and can also
publish to every other node. The cluster will make sure that published
messages are forwarded as needed.

The current implementation will simply broadcast each published message
to all other nodes, but at some point this will be optimized either
using Bloom filters or other algorithms.

Appendix
===

Appendix A: CRC16 reference implementation in ANSI C
---

    /*
     * Copyright 2001-2010 Georges Menie (www.menie.org)
     * Copyright 2010 Salvatore Sanfilippo (adapted to Redis coding style)
     * All rights reserved.
     * Redistribution and use in source and binary forms, with or without
     * modification, are permitted provided that the following conditions are met:
     *
     *     * Redistributions of source code must retain the above copyright
     *       notice, this list of conditions and the following disclaimer.
     *     * Redistributions in binary form must reproduce the above copyright
     *       notice, this list of conditions and the following disclaimer in the
     *       documentation and/or other materials provided with the distribution.
     *     * Neither the name of the University of California, Berkeley nor the
     *       names of its contributors may be used to endorse or promote products
     *       derived from this software without specific prior written permission.
     *
     * THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
     * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
     * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
     * DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
     * DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
     * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
     * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
     * ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
     * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
     * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
     */

    /* CRC16 implementation according to CCITT standards.
     *
     * Note by @antirez: this is actually the XMODEM CRC 16 algorithm, using the
     * following parameters:
     *
     * Name                       : "XMODEM", also known as "ZMODEM", "CRC-16/ACORN"
     * Width                      : 16 bit
     * Poly                       : 1021 (That is actually x^16 + x^12 + x^5 + 1)
     * Initialization             : 0000
     * Reflect Input byte         : False
     * Reflect Output CRC         : False
     * Xor constant to output CRC : 0000
     * Output for "123456789"     : 31C3
     */

    static const uint16_t crc16tab[256]= {
        0x0000,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,
        0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef,
        0x1231,0x0210,0x3273,0x2252,0x52b5,0x4294,0x72f7,0x62d6,
        0x9339,0x8318,0xb37b,0xa35a,0xd3bd,0xc39c,0xf3ff,0xe3de,
        0x2462,0x3443,0x0420,0x1401,0x64e6,0x74c7,0x44a4,0x5485,
        0xa56a,0xb54b,0x8528,0x9509,0xe5ee,0xf5cf,0xc5ac,0xd58d,
        0x3653,0x2672,0x1611,0x0630,0x76d7,0x66f6,0x5695,0x46b4,
        0xb75b,0xa77a,0x9719,0x8738,0xf7df,0xe7fe,0xd79d,0xc7bc,
        0x48c4,0x58e5,0x6886,0x78a7,0x0840,0x1861,0x2802,0x3823,
        0xc9cc,0xd9ed,0xe98e,0xf9af,0x8948,0x9969,0xa90a,0xb92b,
        0x5af5,0x4ad4,0x7ab7,0x6a96,0x1a71,0x0a50,0x3a33,0x2a12,
        0xdbfd,0xcbdc,0xfbbf,0xeb9e,0x9b79,0x8b58,0xbb3b,0xab1a,
        0x6ca6,0x7c87,0x4ce4,0x5cc5,0x2c22,0x3c03,0x0c60,0x1c41,
        0xedae,0xfd8f,0xcdec,0xddcd,0xad2a,0xbd0b,0x8d68,0x9d49,
        0x7e97,0x6eb6,0x5ed5,0x4ef4,0x3e13,0x2e32,0x1e51,0x0e70,
        0xff9f,0xefbe,0xdfdd,0xcffc,0xbf1b,0xaf3a,0x9f59,0x8f78,
        0x9188,0x81a9,0xb1ca,0xa1eb,0xd10c,0xc12d,0xf14e,0xe16f,
        0x1080,0x00a1,0x30c2,0x20e3,0x5004,0x4025,0x7046,0x6067,
        0x83b9,0x9398,0xa3fb,0xb3da,0xc33d,0xd31c,0xe37f,0xf35e,
        0x02b1,0x1290,0x22f3,0x32d2,0x4235,0x5214,0x6277,0x7256,
        0xb5ea,0xa5cb,0x95a8,0x8589,0xf56e,0xe54f,0xd52c,0xc50d,
        0x34e2,0x24c3,0x14a0,0x0481,0x7466,0x6447,0x5424,0x4405,
        0xa7db,0xb7fa,0x8799,0x97b8,0xe75f,0xf77e,0xc71d,0xd73c,
        0x26d3,0x36f2,0x0691,0x16b0,0x6657,0x7676,0x4615,0x5634,
        0xd94c,0xc96d,0xf90e,0xe92f,0x99c8,0x89e9,0xb98a,0xa9ab,
        0x5844,0x4865,0x7806,0x6827,0x18c0,0x08e1,0x3882,0x28a3,
        0xcb7d,0xdb5c,0xeb3f,0xfb1e,0x8bf9,0x9bd8,0xabbb,0xbb9a,
        0x4a75,0x5a54,0x6a37,0x7a16,0x0af1,0x1ad0,0x2ab3,0x3a92,
        0xfd2e,0xed0f,0xdd6c,0xcd4d,0xbdaa,0xad8b,0x9de8,0x8dc9,
        0x7c26,0x6c07,0x5c64,0x4c45,0x3ca2,0x2c83,0x1ce0,0x0cc1,
        0xef1f,0xff3e,0xcf5d,0xdf7c,0xaf9b,0xbfba,0x8fd9,0x9ff8,
        0x6e17,0x7e36,0x4e55,0x5e74,0x2e93,0x3eb2,0x0ed1,0x1ef0
    };

    uint16_t crc16(const char *buf, int len) {
        int counter;
        uint16_t crc = 0;
        for (counter = 0; counter < len; counter++)
                crc = (crc<<8) ^ crc16tab[((crc>>8) ^ *buf++)&0x00FF];
        return crc;
    }
