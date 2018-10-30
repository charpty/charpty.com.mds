> 原文：https://raft.github.io/raft.pdf

团队要用consul，想认真研究下，总不能以后出了问题搞不定，结果吧，这raft其实和paxos差不多，都是折磨人的小妖精，之前都是网上看着别人消化过的，这次看看原文。


-- 

> Abstract    
> Raft is a consensus algorithm for managing a replicated
log. It produces a result equivalent to (multi-)Paxos, and
it is as efficient as Paxos, but its structure is different
from Paxos; this makes Raft more understandable than
Paxos and also provides a better foundation for building
practical systems. In order to enhance understandability,
Raft separates the key elements of consensus, such as
leader election, log replication, and safety, and it enforces
a stronger degree of coherency to reduce the number of
states that must be considered. Results from a user study
demonstrate that Raft is easier for students to learn than
Paxos. Raft also includes a new mechanism for changing
the cluster membership, which uses overlapping majorities
to guarantee safety.