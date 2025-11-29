def value(l): return l[0] if l else None
def tail(l): return l[1:] if l else []


def cons(a, l): return [a]+l


isEmpty, Nil, nil = lambda l: not l, [], []


class node:
    def __init__(self, left, root, right):
        self.left = left
        self.right = right
        self.root = root


def left(t): return t.left
def right(t): return t.right


def root(t): return t.root


leaf = node(None, None, None)
def isLeaf(t): return t.left is None and t.right is None and t.root is None
