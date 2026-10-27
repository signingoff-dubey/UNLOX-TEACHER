"""A deterministic layout for diagrams with nodes and arrows (a "network" scene). The model only lists the nodes and which node points to
which; where everything goes is computed here, the same way every time, so a 7B model's idea of coordinates never decides how a picture
looks. Layers run left to right: a node sits one step to the right of the furthest node that points to it. Inside a layer the order is
improved by sweeping back and forth (barycentre), which keeps arrows from crossing in the common cases."""
from __future__ import annotations


def _acyclic(n: int, edges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The edges without the ones that close a cycle (found by a depth-first walk in node order), so layering always ends."""
    out: dict[int, list[int]] = {i: [] for i in range(n)}
    for a, b in edges:
        out[a].append(b)
    state = [0] * n                      # 0 new, 1 on the current path, 2 done
    keep: list[tuple[int, int]] = []
    for root in range(n):
        if state[root]:
            continue
        stack = [(root, iter(out[root]))]
        state[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
                continue
            if state[nxt] == 1:          # back edge: it would close a cycle
                continue
            keep.append((node, nxt))
            if state[nxt] == 0:
                state[nxt] = 1
                stack.append((nxt, iter(out[nxt])))
    return keep


def layers_of(n: int, edges: list[tuple[int, int]]) -> list[int]:
    """The layer (0, 1, 2...) of every node."""
    dag = _acyclic(n, edges)
    layer = [0] * n
    for _ in range(n):                   # longest path, relaxed until nothing changes (at most n passes on a DAG)
        changed = False
        for a, b in dag:
            if layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    return layer


def layered(n: int, edges: list[tuple[int, int]], width: float = 1000, height: float = 420, pad_x: float = 100, pad_y: float = 50) -> list[list[float]]:
    """[x, y] for every node, inside width x height."""
    if n == 0:
        return []
    layer = layers_of(n, edges)
    depth = max(layer) + 1
    rows: list[list[int]] = [[i for i in range(n) if layer[i] == d] for d in range(depth)]
    dag = _acyclic(n, edges)
    preds = {i: [a for a, b in dag if b == i] for i in range(n)}
    succs = {i: [b for a, b in dag if a == i] for i in range(n)}
    pos = {i: k for row in rows for k, i in enumerate(row)}

    def sweep(order: range, neighbours: dict[int, list[int]]) -> None:
        for d in order:
            def bary(i: int) -> float:
                ns = [pos[j] for j in neighbours[i]]
                return sum(ns) / len(ns) if ns else pos[i]
            rows[d].sort(key=lambda i: (bary(i), i))
            for k, i in enumerate(rows[d]):
                pos[i] = k
    for _ in range(2):
        sweep(range(1, depth), preds)
        sweep(range(depth - 2, -1, -1), succs)

    out = [[0.0, 0.0] for _ in range(n)]
    for d, row in enumerate(rows):
        x = width / 2 if depth == 1 else pad_x + (width - 2 * pad_x) * d / (depth - 1)
        for k, i in enumerate(row):
            y = height / 2 if len(row) == 1 else pad_y + (height - 2 * pad_y) * k / (len(row) - 1)
            out[i] = [round(x, 1), round(y, 1)]
    return out
