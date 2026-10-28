## Translate puzzle rules into constraints
Tower of Hanoi has three pegs and disks of different sizes. Move only the top disk, one disk at a time, and never place a larger disk on a smaller one. The goal is to move an ordered stack from source to target using the spare peg.

Separate a move generator from a simulator. The generator proposes source-target pairs. The simulator checks that the source is nonempty and the destination can accept the disk, then changes state. A correct move count alone does not prove the moves are legal.

## Derive the recursive strategy
To move n disks, move n minus one from source to spare, using target temporarily. Move the largest disk from source to target. Then move the smaller stack from spare to target, using source temporarily. Peg names change roles; argument positions describe those roles.

Zero disks require no moves. For two disks, the moves are A to B, A to C and B to C. Trace these before trying larger inputs. Swapping target and spare in the wrong recursive call can generate a convincing-looking but incorrect plan.

## Worked example: generate a small plan
```
def hanoi(n, source, target, spare):
    if type(n) is not int or n < 0:
        raise ValueError("Use a nonnegative integer")
    if n == 0:
        return []
    return (hanoi(n - 1, source, spare, target)
            + [(source, target)]
            + hanoi(n - 1, spare, target, source))

print(hanoi(2, "A", "C", "B"))
print(len(hanoi(3, "A", "C", "B")))
```

Output is [('A', 'B'), ('A', 'C'), ('B', 'C')] followed by 7. Both smaller plans are computed before the outer function returns its full list. Concatenation is convenient for this small demonstration but creates additional copying.

## Count without generating the plan
The recurrence is T(0) = 0 and T(n) = 2 * T(n - 1) + 1. Counts for zero through four disks are 0, 1, 3, 7 and 15. The closed form is 2**n - 1. A compact formula describes an exponentially growing number of actual moves.

The workshop's move_count makes one recursive call and doubles its result. That differs from generating two actual subplans. It still has recursion-depth limits. A generator can reduce plan storage but cannot remove the number of moves needed to execute it.

## Coding workshop and verification
Complete move_count for nonnegative integers. Test zero, one, three and four disks. Explain why adding one represents the largest disk's move. Do not use a base case of one without handling zero.

Build a simulator using a list per peg, with the largest disk first and top disk last. For three disks, assert every move is legal, source and spare finish empty, target contains [3, 2, 1] and seven moves occurred. Keep demonstrations small enough to remain responsive.
