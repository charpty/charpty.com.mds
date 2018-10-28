# -*- coding: utf-8 -*-

import sys

reload(sys)
sys.setdefaultencoding('utf-8')

RED = 0;
BLACK = 1;


# 我们就用一个key存整数这样简单点
class Node:
    def __init__(self, key, value, color, parent):
        self.key = key
        self.value = value
        self.left = None
        self.right = None
        self.parent = parent
        self.color = color


def get_color(node):
    # 在红黑树里末端还有一个NIL节点，也就是None节点，为黑色
    if node is None:
        return BLACK
    else:
        return node.color


def set_color(node, color):
    if node is not None:
        node.color = color


def get_parent(node):
    if node is not None:
        return node.parent


def get_grandparent(node):
    return get_parent(get_parent(node))


def right_child(node):
    # None节点的左右孩子都为None
    if node is None:
        return None
    else:
        return node.right


def left_child(node):
    # None节点的左右孩子都为None
    if node is None:
        return None
    else:
        return node.left


# node成为node的右孩子的左孩子，node的右孩子的左孩子成为node的右孩子
def rotate_left(node, tree):
    if node is None:
        return

    rn = node.right
    node.right = rn.left
    if rn.left is not None:
        rn.left.parent = node
    rn.parent = node.parent
    if node.parent is None:
        tree.root = rn
    elif node.parent.left == node:
        node.parent.left = rn
    else:
        node.parent.right = rn

    rn.left = node
    node.parent = rn


def rotate_right(node, tree):
    if node is None:
        return
    ln = node.left
    node.left = ln.right
    if ln.right is not None:
        ln.right.parent = node

    ln.parent = node.parent
    if node.parent is None:
        tree.root = ln
    elif node.parent.right == node:

        node.parent.right = ln
    else:
        node.parent.left = ln

    ln.right = node
    node.parent = ln


def get_successor(node):
    if node is None:
        return None
    if node.right is not None:
        right = node.right
        # 找比node大的最小node
        while right.left is not None:
            right = right.left
        return right
    # 没有右子树，向上找到它为其他树左节点的情况
    p = node.parent
    while p is not None and p is left_child(p):
        node = p
        p = get_parent(p)
    return p


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


def get_one_child(node):
    if left_child(node) is not None:
        return left_child(node)
    else:
        return right_child(node)


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

    def _delete_leaf(self, x):
        if get_parent(x) is None:
            # 根节点
            self.root = None
            return
        # 叶子节点
        if get_color(x) is BLACK:
            fix_delete(x, self)

        if x is left_child(get_parent(x)):
            get_parent(x).left = None
        if x is right_child(get_parent(x)):
            get_parent(x).right = None
        x.parent = None

    def _get_node(self, key):
        t = self.root
        while t is not None:
            # 约定了key是整数，直接比就行
            if key > t.key:
                t = t.right
            elif key < t.key:
                t = t.left
            else:
                return t


# **********************************TEST CODE*********************************************************

def list_node(tree):
    result = []
    _list_node(tree.root, result)
    return result


def _list_node(node, result):
    if node is None:
        return
    _list_node(left_child(node), result)
    result.append(node)
    _list_node(right_child(node), result)


def print_node_list(node_list):
    for n in node_list:
        color = None
        if n.color == RED:
            color = "红"
        if n.color == BLACK:
            color = "黑"
        print "%d:%s:%s" % (n.key, n.value, color)


def print_tree(tree):
    node_list = list_node(tree)
    print_node_list(node_list)


def test_insert(tree):
    tree.insert(1, "a")
    tree.insert(9, "i")
    tree.insert(2, "b")
    tree.insert(7, "g")
    tree.insert(3, "c")
    tree.insert(4, "d")
    tree.insert(8, "h")
    tree.insert(6, "f")
    tree.insert(5, "e")
    tree.insert(10, "j")
    tree.insert(11, "k")
    tree.insert(12, "l")
    tree.insert(13, "m")
    tree.insert(14, "n")
    tree.insert(15, "o")
    tree.insert(16, "p")
    tree.insert(1, "new-a")
    tree.insert(8, "new-h")

    print_tree(tree)


def test_delete(tree):
    tree.delete(16)
    print_tree(tree)
    print_hr()

    tree.delete(8)
    print_tree(tree)
    print_hr()

    tree.delete(10)
    print_tree(tree)


def print_hr():
    print "*********************************"


def main():
    tree = RBTree()
    test_insert(tree)
    print_hr()
    print_hr()
    test_delete(tree)


if __name__ == '__main__':
    main()
