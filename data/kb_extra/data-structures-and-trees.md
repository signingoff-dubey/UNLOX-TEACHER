# Data structures and trees

## Big-O: how the cost of an algorithm grows

Big-O notation describes how the running time of an algorithm grows with the input size n, ignoring constant factors. O(1) is constant time: it does not grow. O(log n) grows very slowly, because doubling n adds only one step. O(n) grows in step with n. O(n log n) is the cost of good sorting. O(n^2) grows with the square of n, so doubling n makes it four times slower.

For n equal to one million, an O(log n) search needs about 20 steps, an O(n) search needs up to a million steps, and an O(n^2) algorithm needs about a trillion. Worst case, average case and best case are different questions: a data structure can be fast on average and slow in its worst case.

## Arrays, linked lists, stacks and queues

An array stores items next to each other in memory, so reading the item at index i takes O(1) time. Inserting or deleting in the middle takes O(n) because the items after it must be shifted.

A linked list stores each item in a node that holds a value and a pointer to the next node. Inserting or deleting at the head takes O(1), but finding an item takes O(n) because the list must be walked from the start. In C, a node is struct Node { int data; struct Node *next; };. A doubly linked list also keeps a pointer to the previous node.

A stack is last in, first out (LIFO): push adds an item on top, pop removes the top item, and both take O(1). Stacks are used for undo, for the function call stack, for matching brackets and for depth-first search.

A queue is first in, first out (FIFO): enqueue adds at the back and dequeue removes from the front, both in O(1). Queues are used for scheduling, buffering and breadth-first search.

## Hash tables

A hash table stores key and value pairs. A hash function turns the key into an index in an array, so lookup, insert and delete take O(1) time on average. Two keys can land on the same index, which is called a collision. Chaining keeps a small list at each index; open addressing looks for the next free slot. With many collisions the worst case degrades to O(n), so tables are resized when they become too full.

## Binary trees

A tree is a hierarchy of nodes: one root at the top, and every other node has exactly one parent. A node with no children is a leaf. A binary tree allows each node at most two children, called left and right. The height of a tree is the number of edges on the longest path from the root to a leaf, so a single node has height 0. The depth of a node is its distance from the root.

There are four ways to visit every node. Inorder visits left, node, right. Preorder visits node, left, right. Postorder visits left, right, node. Level-order visits the nodes level by level using a queue.

## Binary search trees

A binary search tree (BST) keeps its keys ordered: for every node, all keys in its left subtree are smaller and all keys in its right subtree are larger. Because of that rule, an inorder traversal prints the keys in sorted order.

To search, compare the key with the current node and go left if it is smaller or right if it is larger, until the key is found or a missing child is reached. Insert works the same way and places the new key where the search ended. Search, insert and delete each take time proportional to the height of the tree.

If keys arrive in random order the height is about log n, so the operations are O(log n). If keys arrive already sorted, such as 10, 20, 30, 40, every new key goes to the right and the tree becomes a chain of height n - 1. Then search, insert and delete degrade to O(n), no better than a linked list. This is the problem that self-balancing trees solve.

## AVL trees

An AVL tree is a self-balancing binary search tree, invented in 1962 by the Soviet mathematicians Georgy Adelson-Velsky and Evgenii Landis; the name AVL comes from their initials. It is the oldest self-balancing binary search tree. After every insertion or deletion it restores balance with rotations, so the height always stays about log n.

The balance factor of a node is the height of its left subtree minus the height of its right subtree. The AVL rule is that the balance factor of every node must be -1, 0 or +1. If it becomes +2 or -2 the tree is rebalanced at that node. A node with balance factor +1 is left-heavy, -1 is right-heavy, and 0 is balanced. In code, many programs store the height of a leaf as 1 and the height of an empty tree (NULL) as 0.

The rule keeps the tree short. The smallest number of nodes N(h) that an AVL tree of height h can have follows N(h) = N(h - 1) + N(h - 2) + 1, which is a Fibonacci-like growth: N(0) = 1, N(1) = 2, N(2) = 4, N(3) = 7, N(4) = 12, N(5) = 20. So the height of an AVL tree with n nodes is less than about 1.44 times log2(n + 2). Search, insert and delete are therefore O(log n) in the worst case, and a tree of one million keys is at most about 28 levels high.

## AVL rotations

A rotation is a local rearrangement of a few nodes that changes the shape of the tree but keeps the binary search tree order. A rotation takes O(1) time.

A right rotation at node z, whose left child is y, makes y the root of the subtree, moves y's old right subtree to become z's left subtree, and makes z the right child of y. A left rotation is the mirror image: at node z with right child y, y becomes the root of the subtree, y's old left subtree becomes z's right subtree, and z becomes the left child of y.

There are four imbalance cases, named by where the new key went relative to the unbalanced node z:

Left-Left (LL): z has balance +2 and its left child is left-heavy or balanced. One right rotation at z fixes it.
Right-Right (RR): z has balance -2 and its right child is right-heavy or balanced. One left rotation at z fixes it.
Left-Right (LR): z has balance +2 but its left child is right-heavy (balance -1). First a left rotation at the left child, then a right rotation at z. This is a double rotation.
Right-Left (RL): z has balance -2 but its right child is left-heavy (balance +1). First a right rotation at the right child, then a left rotation at z.

Worked example: insert 10, then 20, then 30 into an empty AVL tree. After 10 and 20 the tree is a root 10 with right child 20, and node 10 has balance -1, which is allowed. After 30 is added below 20, node 10 has balance -2 and its right child 20 has balance -1: a Right-Right case. A left rotation at 10 makes 20 the root, with 10 as its left child and 30 as its right child. All balance factors are now 0.

Second example: insert 30, then 10, then 20. Node 30 has balance +2 and its left child 10 is right-heavy: a Left-Right case. Rotate left at 10, which makes 20 the left child of 30 with 10 below it, then rotate right at 30. The result is the same balanced tree with 20 at the root.

## AVL insertion and deletion

To insert a key, first insert it like in an ordinary binary search tree. Then walk back up from the new node to the root. At each ancestor, update its height, compute its balance factor and, if the balance factor is +2 or -2, apply the matching rotation. For insertion, one rotation (single or double) always restores balance for the whole tree.

To delete a key, first delete it like in an ordinary binary search tree: a leaf is simply removed, a node with one child is replaced by that child, and a node with two children is replaced by its inorder successor (the smallest key in its right subtree), which is then removed from where it was. Then walk back up to the root, updating heights and rebalancing. Unlike insertion, a deletion can need a rotation at several ancestors on the way up, up to O(log n) rotations in total. If the heavy child has balance 0 after a deletion, a single rotation is used.

## AVL tree in C

A node and the height helper:
struct Node { int key; struct Node *left, *right; int height; };
int height(struct Node *n) { return n ? n->height : 0; }

A right rotation:
struct Node *rightRotate(struct Node *y) { struct Node *x = y->left; struct Node *t2 = x->right; x->right = y; y->left = t2; y->height = 1 + max(height(y->left), height(y->right)); x->height = 1 + max(height(x->left), height(x->right)); return x; }

The left rotation is the mirror image. The balance factor is int balance(struct Node *n) { return n ? height(n->left) - height(n->right) : 0; }.

Insert, with the four cases after the recursive call:
struct Node *insert(struct Node *node, int key) { if (node == NULL) return newNode(key); if (key < node->key) node->left = insert(node->left, key); else if (key > node->key) node->right = insert(node->right, key); else return node; node->height = 1 + max(height(node->left), height(node->right)); int b = balance(node); if (b > 1 && key < node->left->key) return rightRotate(node); if (b < -1 && key > node->right->key) return leftRotate(node); if (b > 1 && key > node->left->key) { node->left = leftRotate(node->left); return rightRotate(node); } if (b < -1 && key < node->right->key) { node->right = rightRotate(node->right); return leftRotate(node); } return node; }

## AVL trees compared with other trees

A plain binary search tree is simpler but can degrade to O(n). An AVL tree is more strictly balanced than a red-black tree, so lookups are slightly faster, but it may perform more rotations on insertion and deletion. Red-black trees allow a little more imbalance and rotate less often; they are used in the C++ standard library map and set and in Java TreeMap. AVL trees are a good choice when there are many more searches than updates, such as in databases and indexes held in memory. A B-tree is a many-way balanced tree used for disk-based indexes.

## Heaps and priority queues

A binary heap is a complete binary tree stored in an array in which every parent is smaller than or equal to its children (a min-heap) or larger than or equal to them (a max-heap). The smallest item of a min-heap is always at the root. Insert and extract-min each take O(log n) because an item moves up or down at most the height of the tree. Building a heap from n items takes O(n). A heap implements a priority queue and is used in heap sort and in Dijkstra's algorithm.

## Sorting algorithms

Bubble sort repeatedly swaps neighbouring items that are in the wrong order and takes O(n^2) time. Insertion sort grows a sorted part one item at a time: O(n^2) in the worst case but fast on nearly sorted data. Merge sort splits the list in half, sorts each half and merges them; it takes O(n log n) time in every case, is stable, and needs O(n) extra space. Quick sort picks a pivot and partitions the items into smaller and larger ones; it takes O(n log n) on average and O(n^2) in the worst case, and sorts in place.

## Graphs

A graph is a set of vertices connected by edges; edges may be directed and may carry weights. A graph is stored as an adjacency matrix or as an adjacency list. Breadth-first search (BFS) visits vertices level by level using a queue and finds the fewest-edges path in an unweighted graph. Depth-first search (DFS) goes as deep as possible first using a stack or recursion. Both take O(V + E) time. Dijkstra's algorithm finds the shortest paths from one vertex in a graph with non-negative weights; with a min-heap it takes O((V + E) log V).

## Common mistakes with data structures

Thinking that a binary search tree is always fast: sorted input turns it into a chain.

Confusing the height of a tree (edges) with the number of levels or nodes.

Forgetting that an AVL balance factor of +2 or -2 is fixed by a rotation at the lowest unbalanced node, not at the root.

Using a single rotation for a Left-Right or Right-Left case: the zig-zag shape needs a double rotation.

Forgetting to update the heights after a rotation, which makes later balance factors wrong.

Believing that rotations change the sorted order of the keys: they never do.
