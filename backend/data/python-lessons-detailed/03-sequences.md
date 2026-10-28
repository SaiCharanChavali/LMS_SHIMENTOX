## Sequences represent ordered values
A sequence has a defined positional order. Lists, tuples and strings are common examples, but they do not have identical mutation behavior. A list can add, remove or replace elements. A tuple cannot replace its positions, although an object stored inside a tuple may itself be mutable. A string's characters cannot be changed in place; string operations create new strings.

Choose the structure from the responsibility. A list suits an editable set of score readings, while a tuple can communicate a fixed group of values. Do not assume that an assignment such as backup = scores makes an independent list: both names refer to the same object. A shallow copy creates a new outer list, but nested mutable objects remain shared unless copied deliberately.

## Indexing and slicing have different boundary behavior
Index zero selects the first item and -1 selects the last item. An empty list has neither, so direct access can raise IndexError. For values = [10, 20, 30, 40], values[1:3] returns [20, 30]: a slice includes its start and excludes its stop. A slice can be empty or safely stop at a boundary, while a single invalid index is an error.

The optional slice step controls which positions are visited. Do not use a compact slice you cannot explain; readability matters in shared automation code. Keep the distinction between an item's value and its index visible, especially when a displayed row number starts at one while list indexes start at zero.

## Loops need a clear iteration contract
A for loop visits the items of an iterable. range(4) supplies 0, 1, 2 and 3; it excludes its stop. enumerate can pair each item with a count, and start=1 is useful for human-readable numbering. The count is not automatically the item's underlying zero-based index.

A while loop repeats while its condition is true. Ensure each relevant path changes the state toward termination or exits deliberately. break exits the loop; continue skips the rest of the current iteration. Indentation determines which lines belong to that iteration.

Avoid removing elements from a list while an ordinary loop is traversing that same list: shifting positions can skip values or produce confusing behavior. Construct a filtered result when the operation's contract is to return a selected subset without changing the original.

## Worked filtering example
Run this code and compare the original list with the result.

```
scores = [48, 75, 92, 60]
eligible = [score for score in scores if score >= 75]
for number, score in enumerate(eligible, start=1):
    print(number, score)
print(scores)
print(scores[1:3])
```

The numbered lines are 1 75 and 2 92. The original list remains [48, 75, 92, 60], and the slice is [75, 92]. The comprehension is equivalent to creating an empty result and appending each matching score. Here its elements are integers, so retaining references to the same immutable values is safe for the intended operation.

## Guided browser practice
- Complete passing_scores using the workshop's threshold of 70, not the worked example's threshold of 75.
- Retain matching scores in their original order and return a new list.
- Check empty input, exactly 70, all-failing scores and repeated passing scores.
- Verify that calling the helper does not modify the caller's source list.

## Review and common mistakes
Do not assign result = values.append(x): append mutates the list and returns None. Do not confuse a final list length with its last valid index. Explain why filtering preserves duplicates unless a separate business rule asks for uniqueness. Completion requires understanding the loop or comprehension, its stop boundaries and its mutation contract, not only matching one sample output.
