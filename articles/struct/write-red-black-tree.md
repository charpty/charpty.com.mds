> 笔者博客地址：https://charpty.com

我记得面试的时候，经常问问别人```hashmap```实现，说着说着就免不了讲讲红黑树，平常都是用现成的，考察别人红黑树也只是看下是否喜欢专研、有学习劲。

有一次有个同学告诉我他讲不清楚但是可以写一下，很惭愧，全忘了，一下子让我写一个，伪代码都够呛了，跑起来更不行。

我给自己想了个简单的记法，父红叔红就变色，父红叔黑靠旋转，删黑两孩很麻烦，叔黑孩最很简单。

--

## 红黑树
红黑树是AVL树的进一步加强，正是二叉平衡查找树有问题才引出了红黑树，和典型数据结构一样，在适当的场景使用红黑树可以很大程度的提高性能。

红黑树首先是一棵二叉查找树，节点的左孩子都比节点小，节点的右孩子都比节点大，与AVL平衡树期望带到的效果一样，都想左右子树的深度相差不要太大，尽量平衡，以便提供平均查找效率。

先记住一下红黑树的以下几个特性，不用急着回忆，后面代码写着写着自然就想起来了。

1. 节点要么是黑色要么是红色，根节点固定为黑色，叶子节点也固定为黑色（不关键特性3合一）
2. 子节点和父节点不能同时为红色，子父不连红。
3. 从一个节点到其通向到所有叶子节点路径中，所包含的黑色节点数目相同。保证树平衡的关键。

前面两点都很好理解，第2点是用来修改树时判断树是否还是红黑树的主要条件。  
第3点不直观，但是可以这样想，插入或删除一个节点，影响的只是它周边那几个节点（之外的节点本来就是“平衡”的），所以这句话可以翻译成说，要在修改节点后，要把上、左、右这几个位置上的黑色节点数量控制住，所以此时只要把周边几个节点挪一挪，就又恢复平衡了。   
 
所以在红黑树实现中，一般不直接判断第3点（一层层遍历下去效率太低），而仅仅是把周围几个节点通过变色和旋转来达到平衡。


对于红黑树的理论讲解，网上非常多，但是我想实在点，直接一起写吧，写本文之前，我也是照着算法伪代码直接开写，很多忘了的都想起来了。

### 插入节点Z
和业务代码一样，红黑树也无非是增、删、改、查，其它三个都包含着查，增和删对树结构变化最大，我们就看这两个即可理解红黑树了，先来看插入节点的伪代码（网上找了个，不太对我改了下）。

```
// 在插入节点（二叉查找树的插入）完成后，如果破坏了红黑树特性，则对红黑树进行修复
// T表示当前红黑树，z表示当前插入的节点，->p表示父节点，->right表示右孩子，类推
RB-INSERT-FIXUP(T, z)
// 为了不与“特性3”冲突，所以插入的z是红色，这样黑色节点的数目肯定是不会变化的
// 如果z的父节点为红那就与“特性2：子父节点不同时为红”冲突，此时要分几种情况调整
while z->p->color = RED; do
	 // 如果z的父节点为爷爷节点的左孩子
	if z->p = z->p->p->left then
 			y ← z->p->p->right
 			// 叔叔节点为红色或黑色，分为两种情况处理
 			if y->color = RED then
				// 如果叔叔是红色，爷爷节点是黑色，这种情况比较简单，此时无论父节点是爷爷节点的左还是右节点
				// 都是将父节点设置为黑色，叔叔节点设置为黑色，祖父节点设置为红色
				// 这样一来，子父为红-红的情况自然是不存在了，父节点和叔叔节点由红-红变成了黑-黑
				// 经过这两个节点的到根节点路径黑色节点数没变，都是增加了一个黑色节点
				// 经过爷爷节点到根路径的黑色节点数量则无变化，爷爷节点变成了红色，但是它的两个孩子不论选哪条路都加1了
				z->p->color ← BLACK
				y->color ← BLACK
				z->p->p->color ← RED
				// 爷爷节点设置为红色之后，继续向上判断它和其父节点是否冲突
				z ← z->p->p
 			else 
 				// 如果叔叔节点是黑色就需要旋转树了，如果x为父节点的左孩子，先要额外进行一次进行左旋
 				if z = z->p->right then	
 					z ← z->p
 					LEFT-ROTATE(T, z)
 				// 先假设x为父节点的左节点，这样比较简单，弄清楚了加一层左旋一样的道理
 				z->p->color ← BLACK
 				z->p->p->color ← RED
 				// 上面两行代码已解决了"子父节点不能同为红色"的问题，这样经过爷爷节点走左边的话黑色节点计数还是不变的
                // 但是原本通过爷爷节点走右边的话有两个黑节点的，现在只有一个了，此时只有一个了
                // 关键来了，在节点为红-黑-红-黑（顶上为红）的情况下，右旋使得旋转节点的右孩子路径上黑色节点数加1
 				RIGHT-ROTATE(T, z->p->p)
 	// 如果z的父亲为爷爷节点的右孩子，叔叔节点为红色的逻辑是一样的，只是叔叔为黑时逻辑“相反”
	else (same as then clause with "right" and "left" exchanged)
 T->root->color ← BLACK
```

为了写的更清楚，特地将Java的TreeMap又看了一遍，其中的fixAfterInsertion()函数正是这个逻辑。

到底干了啥呢，其实就当两种情况来理解的话，就没那么绕了。只是外面套了一层父节点是爷爷节点的左还是右节点，导致2*2变成4条逻辑线了。 

1. 叔叔节点为红色，太简单了，变个色即可
2. 叔叔节点是红色，那就要进行左右旋了，先理解单纯的各种假设条件下的一次右旋，即可理解其他


#### 情况一：叔叔节点是红色 

![叔叔节点是红色](/images/struct/rb-tree-insert1.png)

这个好理解的，接下来看下叔叔节点是黑色


#### 情况二：叔叔节点是黑色，Z的父节点为爷爷节点的左孩子，Z也为父节点左孩子

![叔叔节点是黑色1](/images/struct/rb-tree-insert2.png)

原来的逻辑是先涂色，再右旋，但是不能很好的体现左旋的作用，不管是左旋还是右旋，逻辑都是将红色节点向根节点靠拢，最后将红色节点涂黑。

也就是以下流程

![叔叔节点是黑色2](/images/struct/rb-tree-insert3.png)

#### 情况三：叔叔节点是黑色，Z的父节点为爷爷节点的左孩子，Z也为父节点右孩子
此时就比较麻烦了，处理的思路是将情况三转换为情况二，这需要额外的一次左旋。

![叔叔节点是黑色3](/images/struct/rb-tree-insert4.png)


可以看到，情况三是先把问题转化为情况二，再利用已知的处理方式调整

还有另外一个逻辑和情况二、三相反，就不重复叙述了。

### 删除节点X
和插入的逻辑类似，插入时是先按照二叉查找树的方式先插入再调整，删除时也是先按照二叉查找树的方式先删除，然后再调整。

要提醒的是，二叉查找树的删除，不论删除哪个节点，最终都是删除“最边上”的节点，要么是叶子节点，要么是有一个孩子的节点，度最大为1。因为即使删除中间的某个节点，也得选它左子树中最大的节点补上去（选左右都一样），那左子树最大的节点肯定是在左子树右边“最边上”了。

和二叉查找树稍有不同的是，红黑树是带颜色的，为了保证“上边”的树结构满足红黑树特性，所以补上节点时，仅仅是把节点的值拷贝过去，颜色不拷贝。

所以接下来我们讨论的都是删除这个“最边上”节点的种种情况，称之为X节点。

删除操作的伪代码


```
// 在删除节点操作完成后对红黑树进行修复
RB-DELETE-FIXUP(T, x)
// 删root没啥好处理的，删红色节点也无需理会（后续有讲解为何）
while x ≠ root[T] and color[x] = BLACK  do
	// 在写伪代码以及操作解释时都仅说明x为父节点左孩子的情况，右孩子情况是对称的
	if x = left[p[x]] then  
		// 关注的是x的兄弟节点和其孩子节点的情况 
		w ← right[p[x]]  
		// 兄弟节点是红色，则将其转换为"兄弟节点是黑色"的情况
		if color[w] = RED  then 
			color[w] ← BLACK                         
			color[p[x]] ← RED                         
			LEFT-ROTATE(T, p[x])                      
			w ← right[p[x]]                           
		if color[left[w]] = BLACK and color[right[w]] = BLACK  then 
			// 兄弟节点及其孩子节点均为黑色的情况下，则将其转换为"兄弟节点为红色"
			color[w] ← RED                            
			x ← p[x]                                  
		else 
			if color[right[w]] = BLACK then
				// 直接转换为"兄弟节点右孩子为红色"情况
				color[left[w]] ← BLACK            
				color[w] ← RED                   
				RIGHT-ROTATE(T, w)                
				w ← right[p[x]]
			// 兄弟节点右孩子为红色的情况可以一步到位达到平衡                   
			color[w] ← color[p[x]]                   
			color[p[x]] ← BLACK                      
			color[right[w]] ← BLACK                  
			LEFT-ROTATE(T, p[x])                   
			x ← root[T]                             
	else (same as then clause with "right" and "left" exchanged)  
color[x] ← BLACK  
```

这里容易混淆的是，比如以A为中心左旋时，A成为A的右孩子的左孩子，A的右孩子的左孩子B成为A的右孩子，注意B在成为A的右孩子时，是将B以及B下面整棵子树娜过来了。

#### 比较简单的几种情况

**删除的节点X是红色**    
如果删除的节点X是红色，那么首先说明原来上下都是黑色的，删了X节点一不违背“子父节点不同时为红”的特性，二不违背“各节点到叶节点路径上黑色节点数目相同”的特性，所以无需处理。

**接替X的节点W是红色**    
X被删了，它自己是一个黑色，它的子节点有且仅有一个，颜色是红色。   
接替它的节点W是红色，那么直接用W接替X的位置，再把W涂黑即可。

**X为根节点的情况**   
如果X为黑色，W也是黑色，那就比较麻烦了，分很多情况，其中最特殊的就是X是根节点，此时删除X之后啥也不用做，删除根节点唯一要考虑的仅仅是“红-红”冲突而已。


另外的情况比较复杂，每种情况的处理方式都不同，我们仅举X是其父节点的左孩子的情况，和插入一下，为右孩子时，操作是对称的。  
 
值得注意的是如果X是黑色且没有任何子节点，那么也是通过旋转等复杂操作来重新平衡的，这时我们就假设替代的节点是个黑色节点（虚拟的）就行，主要看的是X的兄弟以及X的侄子的颜色情况。

#### 情况一：X、W是黑色，X的兄弟节点Y是黑色，Y的右孩子是红色
前面3个条件的处理的都是最简单的情况，我们当然希望要删除的都是红色，这样啥也不用干了，但是接下来4种情况都是比较绕的。

虽然复杂，但是记住一个原则，后面的情况二、情况四、情况五所做的动作，都是想最终转化为情况一或上述3种简单情况而已。也就是说，情况一和上面的3种情况是与红黑树平衡最接近的场景，只需一步操作即可恢复平衡了，而其他情况则需要先转换为这些情况。

做法也还是涂色加旋转，先把兄弟节点Y染成当X的父节点的颜色，再把X节点父节点染成黑色，Y节点右孩子子染成黑色，最后再以X节点的父节点为中心进行左旋。

![Y的右孩子为红色](/images/struct/rb-tree-delete1.png)

为了和后面的情况统一风格，我们认定情况一的处理办法为：    

```
情况一  ->  最终平衡
```

#### 情况二：X、W是黑色，X的兄弟点Y是黑色，Y的右孩子为黑色，Y的左孩子为红色

此时我们要做的事将该场景转换为情况一，然后我们再使用情况一的解决办法即可。

做法是将兄弟节点Y涂红，Y节点左孩子涂黑，之后再以兄弟节点Y为中心右旋。

![Y的右孩子为黑色1](/images/struct/rb-tree-delete2.png)

这种情况的处理办法为

```
情况二  ->  情况一  ->  最终平衡
```

#### 情况三：X、W是黑色，X的兄弟Y为红色
此时X的父节点以及Y的孩子均为黑色，处理原则是将X的兄弟节点变为黑色（当然是在不能破坏目前的红黑树已有性质前提下）。

具体处理办法是以X的父节点为中心进行左旋。左旋之后X的新兄弟节点必然为黑色，此时又回到了兄弟节点为黑色的几种情况上。

![Y的右孩子为黑色1](/images/struct/rb-tree-delete4.png)

这种情况的处理办法为

```
情况三  -> （情况一、情况二）
```


#### 情况四：X、W是黑色，X的父亲、Y及其孩子均为黑色
这种情况下，左边X的路径上因为删除少了一个黑色节点，此时我们将Y节点涂红，这样经过Y和经过W（替代X后）的黑色节点数达到一致了。

但问题是经过原X的父节点的路径的黑色节点数少1了，但此时整个结构又回到了情况四（右边路径上黑色数目不同了但不影响），所以我们又可以按照情况四继续往下走。

![Y的右孩子为黑色1](/images/struct/rb-tree-delete5.png)

这种情况的处理办法为

```
情况四  -> 情况三
```

## 红黑树实现

想了想还是用Python写吧，人生苦短。

完整的代码：[请下载](/codes/struct/write_rb_tree_example.py)



定义一个class表示红黑树吧，只要存一个root节点就够了。

``` python
class RBTree:
    def __init__(self):
        self.root = None

    def insert(self, key, value):
        if self.root is None:
            self.root = Node(key, value, BLACK, None)
            return
        parent = None
        t = self._get_node(key)
        if t is not None:
            t.value = value
            return
        node = Node(key, value, RED, parent)
        if parent.key < node.key:
            parent.right = node
        else:
            parent.left = node

        fix_insert(node, self)

    def delete(self, key):
        x = self._get_node(key)
        if x is None:
            return
        if left_child(x) is not None and right_child(x) is not None:
            real_delete = get_successor(x)
            x.key = real_delete.key
            x.value = real_delete.value
            x = real_delete
        # 到此，x最多也就一个孩子了
        successor = get_one_child(x)
        if successor is None:
            self._delete_leaf(x)
            return

        if get_parent(x) is None:
            self.root = None
        elif x is left_child(get_parent(x)):
            get_parent(x).left = successor
        else:
            get_parent(x).right = successor

        if get_color(x) is BLACK:
            fix_delete(successor, self)
```

插入修复

``` python
def fix_insert(node, tree):
    z = node
    while z is not None and z is not tree.root and get_color(get_parent(z)) is RED:
        if get_parent(z) is left_child(get_grandparent(z)):
            uncle = right_child(get_grandparent(z))
            if get_color(uncle) is RED:
                # 叔叔是红色，此时将父亲和叔叔设置为黑色，爷爷设置为红色即可
                # 不管父节点是左孩子还是右孩子都一样
                set_color(get_parent(z), BLACK)
                set_color(uncle, BLACK)
                set_color(get_grandparent(z), RED)
                # 爷爷节点涂红之后，继续向上同样方式判断
                z = get_parent(z)
            else:
                # 如果z为父节点的右孩子，先要把它变成左孩子形式（实质上父子对掉了）
                if z is right_child(get_parent(z)):
                    z = get_parent(z)
                    rotate_left(z, tree)
                # 此时z为父节点的左孩子，将父节点涂黑，爷爷节点涂红，在以爷爷节点为中心右旋
                set_color(get_parent(z), BLACK)
                set_color(get_grandparent(z), RED)
                rotate_right(get_grandparent(z), tree)
        else:
            uncle = left_child(get_grandparent(z))
            if get_color(uncle) is RED:
                set_color(get_parent(z), BLACK)
                set_color(uncle, BLACK)
                set_color(get_grandparent(z), RED)
                z = get_parent(z)
            else:
                if z is left_child(get_parent(z)):
                    z = get_parent(z)
                    rotate_right(z, tree)
                set_color(get_parent(z), BLACK)
                set_color(get_grandparent(z), RED)
                rotate_left(get_grandparent(z), tree)

```

删除修复

``` python
def fix_delete(node, tree):
    x = node
    while x is not tree.root and get_color(x) is BLACK:
        if x is left_child(get_parent(x)):
            brother = right_child(get_parent(x))
            if get_color(brother) is RED:
                # 兄弟节点是红色，则将其转换为"兄弟节点是黑色"的情况
                set_color(brother, BLACK);
                set_color(get_parent(x), RED);
                rotate_left(get_parent(x));
                brother = right_child(get_parent(x));
            if get_color(left_child(brother)) is BLACK and get_color(right_child(brother)) is BLACK:
                # 兄弟节点及其孩子节点均为黑色的情况下，则将其转换为"兄弟节点为红色"
                set_color(brother, RED)
                x = get_parent(x)
            else:
                if get_color(right_child(brother)) is BLACK:
                    # 直接转换为"兄弟节点右孩子为红色"情况
                    set_color(left_child(brother), BLACK)
                    set_color(brother, RED)
                    rotate_right(brother, tree)
                    brother = right_child(get_parent(x))
                # 这里仅一步即可达到平衡
                set_color(brother, get_color(get_parent(x)))
                set_color(get_parent(x), BLACK)
                set_color(right_child(brother), BLACK)
                rotate_left(get_parent(x), tree)
                x = tree.root
        else:
            brother = left_child(get_parent(x))
            if get_color(brother) is RED:
                set_color(brother, BLACK);
                set_color(get_parent(x), RED);
                rotate_right(get_parent(x));
                brother = left_child(get_parent(x));
            if get_color(right_child(brother)) is BLACK and get_color(left_child(brother)) is BLACK:
                set_color(brother, RED)
                x = get_parent(x)
            else:
                if get_color(left_child(brother)) is BLACK:
                    set_color(right_child(brother), BLACK)
                    set_color(brother, RED)
                    rotate_left(brother, tree)
                    brother = left_child(get_parent(x))
                set_color(brother, get_color(get_parent(x)))
                set_color(get_parent(x), BLACK)
                set_color(left_child(brother), BLACK)
                rotate_right(get_parent(x), tree)
                x = tree.root

```