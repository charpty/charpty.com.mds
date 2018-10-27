# -*- coding: utf-8 -*-

import sys
import urllib

reload(sys)
sys.setdefaultencoding('utf-8')

RED = 0;
BLACK = 1;


# 我们就用一个key存下整数就行简单点
class Node:
    def __init__(self, key, color, parent):
        self.key = key
        self.left = None
        self.right = None
        self.p = parent
        self.color = color


# node成为node的右孩子的左孩子，node的右孩子的左孩子成为node的右孩子
def rotate_left(node, tree):
    if node is None:
        return

    rn = node.right;
    node.right = rn.left;
    if rn.left is not None:
        rn.left.parent = node;
    rn.parent = node.parent;
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


class RBTree:
    def __init__(self):
        self.root = None

    def insert(self, key):
        if self.root is None:
            self.root = Node(key, BLACK, None)
            return


def test_insert():
    pass


def test_delete():
    pass


def main():
    test_insert()
    test_delete()


if __name__ == '__main__':
    main()
