```juc```包中的```AbstractQueuedSynchronizer```几乎是所有JDK阻塞类的底层构件，例如```ReentrantLock```、```S emaphore```、```CountDownLatch```、```FutureTask```等等，我们通过实际的例子来看下这些同步类是如何使用```AQS```来构建各自的功能的。

## 基础知识
想必看到```AQS```系列的同学，对于JDK中的基本并发知识已经有了一定的了解，这些锁、信号量、栅栏等都通过```AQS```来实现，那么	```AQS```为它们做了哪些事情？我们先了解几个概念。

### 条件队列