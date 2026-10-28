## Represent connections explicitly
A graph contains vertices and edges. Training prerequisites, rooms connected by corridors and service dependencies all form graphs. An adjacency list maps each vertex to its neighbors and suits sparse connections. An adjacency matrix uses a fixed vertex order and a grid, requiring quadratic space even when few pairs connect.

State whether edges are directed. A prerequisite from A to B does not imply the reverse. An undirected connection usually appears in both adjacency lists. The workshop guarantees that every referenced neighbor also has a graph entry.

## Breadth-first search explores layers
Breadth-first search uses a queue. Remove the oldest queued vertex and enqueue its unseen neighbors. Mark a vertex seen when enqueuing it, rather than waiting for removal. Otherwise two parents can queue the same vertex before either copy is processed.

The seen set prevents cycles from repeating forever. List-valued neighbors give predictable traversal order. Set-valued neighbors may produce different, equally valid orders; tests should match the promised contract.

## Worked example: learning-topic connections
```
from collections import deque

def traverse(graph, start):
    queue = deque([start])
    seen = {start}
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return order

graph = {"A": ["B", "C"], "B": ["D"],
         "C": ["D", "A"], "D": []}
print(traverse(graph, "A"))
```

The output is ['A', 'B', 'C', 'D']. D is discovered from B and not queued again from C. A is already seen when C references it. Unreachable vertices would not appear.

## Distinguish traversal, shortest paths and trees
Breadth-first search finds shortest paths by number of edges in an unweighted graph. Record each newly discovered vertex's parent to reconstruct a path. It does not minimize arbitrary edge costs. Dijkstra's algorithm handles nonnegative weighted edges; negative weights require other algorithms and reasoning.

Depth-first search follows a branch before returning, using recursion or a stack. A tree is a connected acyclic undirected graph; rooting it adds parent-child relationships. Binary search trees add an ordering invariant, beyond merely having at most two children.

## Coding workshop and extensions
Implement reachable using queue order and seen-on-enqueue. Test one vertex, a cycle, multiple routes to one vertex and an unreachable vertex. Return only vertices reachable from the start, not all dictionary keys.

Extend breadth-first search to reconstruct a shortest unweighted path. Compare depth-first order on the same graph. As a backtracking exercise, place four queens one row at a time, rejecting occupied columns and diagonals and undoing choices before alternatives. Explain how tracking visited graph vertices differs from undoing tentative placements.
