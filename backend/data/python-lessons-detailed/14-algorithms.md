## Check algorithm preconditions
Linear search checks candidates in sequence and works without sorting. Binary search halves a sorted interval. Its logarithmic comparison count is useful only when data is ordered and indexed access is efficient. Sorting a list solely for one lookup can cost more than a linear scan.

Define the result: this workshop returns a matching index or -1. With duplicates, any matching index is acceptable. Returning the first occurrence requires an adjusted algorithm; stopping at an equal midpoint does not guarantee it.

## Maintain a shrinking interval
Use inclusive bounds lo and hi. While lo is at most hi, inspect the midpoint. A smaller midpoint value eliminates that position and everything below it: set lo to mid + 1. A larger value sets hi to mid - 1. Excluding the checked midpoint ensures progress with even one or two candidates.

Empty input starts with hi equal to -1, so the loop never runs. This handles the boundary without indexing an empty list. Trace bounds on small inputs to find off-by-one errors before measuring performance.

## Worked example: present and absent values
```
def locate(values, target):
    lo, hi = 0, len(values) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if values[mid] == target:
            return mid
        if values[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

scores = [2, 5, 8, 12]
print(locate(scores, 8))
print(locate(scores, 7))
print(locate([], 7))
```

The output is 2, -1 and -1. Searching for seven inspects five, then eight. The remaining interval becomes empty, proving absence under the sorted-input precondition.

## Compare sorting strategies and growth
Selection sort repeatedly chooses the smallest remaining value and uses quadratic comparisons. Merge sort divides and merges sorted halves, typically using O(n log n) time and additional storage. Quicksort partitions around a pivot: typical performance is O(n log n), but poor partitions can produce quadratic work.

Big O describes growth rather than exact seconds. Constants and data distribution still matter. Use sorted or list.sort for ordinary application code. sorted returns a new list; list.sort mutates the list and returns None.

## Related numeric and validation algorithms
Bisection narrows an interval containing a root of a continuous function. Check the bracket and stop with a tolerance or iteration limit instead of expecting exact floating equality. A Luhn checksum is a separate validation task: double alternating digits from the right, starting with the second-to-last digit, and subtract nine from doubled results above nine. It detects some transcription errors, not identity or authorization.

## Coding workshop and acceptance checks
Implement binary_find. Test empty input, first and last positions, absent targets and duplicates. Trace bound changes on a two-item input to demonstrate termination. Extend with selection sort and merge sort, comparing results with sorted for repeated and negative values. Document whether your sort mutates its input and assert that behavior.
