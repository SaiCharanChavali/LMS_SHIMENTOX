## Identify repeated subproblems
Dynamic programming stores results of overlapping subproblems for reuse. Fibonacci is a small example: F(n) depends on F(n-1) and F(n-2), and naive recursion repeatedly computes the same values. Identify the state, recurrence, base cases and dependency order before choosing an implementation.

Not every recursive algorithm benefits from caching, and not every loop is dynamic programming. Without repeated subproblems, a cache may only add overhead. Its key must capture everything affecting the answer; omitting part of the state can produce incorrect reuse.

## Memoization and tabulation
Memoization starts with the requested problem and caches results during recursive evaluation. It computes only reached states but retains stack costs. Tabulation starts at base cases and fills later results in dependency order. Both should agree under the same contract.

For Fibonacci, F(0) is zero and F(1) is one. When only the final value matters, keep the previous two values instead of the whole sequence. Retaining a table is appropriate when callers need intermediate values too.

## Worked example: two running values
```
def fibonacci(n):
    if type(n) is not int or n < 0:
        raise ValueError("Use a nonnegative integer")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print(fibonacci(0))
print(fibonacci(1))
print(fibonacci(10))
print(fibonacci(25))
```

The output is 0, 1, 55 and 75025. Before each iteration, a and b hold consecutive values. Simultaneous assignment evaluates both expressions using the old values. Setting a = b and then b = a + b separately would use the updated a and produce an incorrect sequence.

## State complexity assumptions precisely
There are n iterations and a constant number of integer variables. This is linear arithmetic operations and constant auxiliary slots. However, Python integers grow with the result: bit storage and addition cost are not constant for arbitrarily large n. Explain the model behind a complexity claim.

Naive recursive Fibonacci creates an exponentially growing call tree. Memoization reduces repeated states to a linear number for this recurrence, while retaining cache and stack storage. Use a fresh cache for independent experiments to avoid misleading warm-cache timings.

## Coding workshop and investigation
Complete fib using two running values. Test zero and one before larger values; off-by-one loops may accidentally pass one sample. Compare results for zero through twenty with a memoized implementation.

Instrument naive and memoized recursion for a small input. Report answers and evaluation counts, distinguishing actual uncached computations from wrapper calls. Extend with a bottom-up minimum-coin solver and an explicit unreachable state. Explain its state and recurrence instead of mechanically copying the Fibonacci loop.
