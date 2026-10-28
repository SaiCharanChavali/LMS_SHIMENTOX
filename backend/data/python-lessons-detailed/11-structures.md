## Choose a structure from required operations
A data structure organizes values to support particular operations. A Python list is a resizable array of references: indexing is constant time and appending is amortized constant time. Inserting or removing at the front shifts other entries and takes linear time. This difference matters when processing thousands of requests.

A linked list stores nodes connected by references. Finding a position requires traversal. Inserting after an already-known node can be constant time, but finding that node may take linear time. Include lookup cost when comparing approaches rather than quoting only the final reference change.

## Stack and queue express removal policies
A stack removes the most recently added item first: last in, first out. Undo history and pending nested work naturally use this order. append and pop at the end of a Python list implement a stack efficiently.

A queue removes the oldest item first: first in, first out. Training requests waiting for processing commonly need this policy. collections.deque supports efficient append and popleft. Repeated list.pop(0) works but shifts all remaining entries.

## Worked example: the same arrivals, different policies
```
from collections import deque

arrivals = ["request-A", "request-B", "request-C"]
stack = list(arrivals)
reversed_requests = []
while stack:
    reversed_requests.append(stack.pop())

queue = deque(arrivals)
processed = []
while queue:
    processed.append(queue.popleft())

print(reversed_requests)
print(processed)
print(arrivals)
```

The first output is ['request-C', 'request-B', 'request-A']. The second and third are ['request-A', 'request-B', 'request-C']. Copying input into a stack leaves arrivals unchanged. The containers start with the same values but implement different processing orders.

## Linked-list changes need boundary handling
For deletion, track previous and current nodes. Removing the head changes the head reference. Removing an interior node reconnects its predecessor to the following node. Removing the final node may require updating a maintained tail. Define a consistent result for an absent value.

An empty list and a one-node list expose assumptions hidden by larger examples. Draw references before and after an operation. A detached node should no longer be reachable through the list's head. Losing the reference to the remaining chain is a different error from merely returning the wrong value.

## Coding workshop and complexity discussion
Implement reverse_items using a stack and return a new list. Test empty input, one item and repeated values. Save a copy of input and verify it is unchanged. Do not sort: reversal uses positions, while sorting orders values.

Extend the project with linked-list append, find and delete. Test head, middle, tail and absent deletion. State time and additional memory costs for your reversal. Explain why arrival-order processing does not automatically provide thread safety or durability; those are separate requirements of a production queue.
