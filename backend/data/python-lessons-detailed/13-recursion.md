## Define a smaller version of the problem
A recursive function calls itself on a smaller input. It needs a base case that returns without recursion and a recursive case that progresses toward the base. Name both cases before coding so termination is an argument you can explain.

For summing a sequence, the empty sequence has sum zero. A nonempty sequence has its first value plus the sum of its remainder. For summing integers from zero to n, the next input can be n minus one. Reject negative n if the stopping condition is n equals zero; otherwise calls move away from the base case.

## The call stack stores unfinished work
Each call has its own parameters and local names. When total_to(3) requests total_to(2), it waits to add three to the nested result. Calls descend toward zero, then results return outward. Call order and return order differ.

Trace the pending expression as 3 + (2 + (1 + 0)). Returning zero resolves the innermost call, followed by one, three and six. A print before the recursive call observes descent; a print afterwards observes unwinding.

## Worked example: progress and a stopping case
```
def total_to(n):
    if type(n) is not int or n < 0:
        raise ValueError("Use a nonnegative integer")
    if n == 0:
        return 0
    return n + total_to(n - 1)

print(total_to(0))
print(total_to(3))
print(total_to(4))
```

The output is 0, 6 and 10. Every valid recursive call decreases n until zero. Removing the base case or calling total_to(n) again prevents the termination argument from holding.

## Recognize implementation costs
The workshop uses recursive_sum(values[1:]). This closely follows the definition, but each slice copies references into a new list. Across calls, those copies add quadratic copying work for a linear-length input. An index-based recursive helper avoids slicing but still creates one stack frame per element.

Python limits recursive depth and does not generally eliminate tail calls. Raising the limit is not a substitute for a suitable algorithm. For long linear sums, a loop or built-in sum avoids stack growth. Recursion is often more natural when data branches, such as a tree.

## Coding workshop and debugging exercise
Implement recursive_sum with zero for an empty list and first-plus-rest otherwise. Test [], [5], [2, -3, 7] and repeated zeros. Negative values inside the list do not threaten termination: its length, rather than its numeric contents, decreases.

Trace recursive_sum([2, 4, 6]) with a row per call and a row per return. Write an iterative version and compare answers. Extend the project with an inclusive recursive range builder, defining equal and reversed endpoints. State which input measure decreases on each call and compare memory needs with iteration.
