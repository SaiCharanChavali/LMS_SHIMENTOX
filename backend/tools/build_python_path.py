"""Build original Shimento teaching material following the public Python v9 topic sequence.

No freeCodeCamp lesson text, exercises, solutions, exam questions or videos are copied.
Run this after editing data/python-lessons-detailed; videos are disabled.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = [
    ('Python basics',
     'Use variables, strings, numbers, conditions and functions to turn a small requirement into a program.',
     'Python executes statements in order. Assignment binds a name to a value; it does not print that value. Text uses quotation marks, while numbers support arithmetic. A boolean records True or False. Use an if statement to choose a branch and a function to name a calculation. Indentation defines the body of both. A function returns a result to its caller; print displays that result. Keep calculations separate from display so you can reuse them. Division with / produces a float. Round only for display when intermediate precision matters.',
     'def price_after_discount(price, percent):\n    if not 0 <= percent <= 100:\n        raise ValueError("Invalid discount")\n    return price * (1 - percent / 100)\n\nprice = price_after_discount(120, 15)\nprint(f"Amount due: {price:.2f}")\n# Amount due: 102.00',
     'Build an employee profile formatter, a shared bill calculator and a shift cipher. For the calculator, accept a bill, a tip percentage and a positive number of people. Reject zero people. For the cipher, wrap letters within the alphabet and preserve spaces. Test a discount of 0, 15 and 100 percent.',
     'The example validates the percentage before calculating. A 15 percent discount leaves 85 percent of 120, giving 102. The f-string displays two decimal places.'),
    ('Python installation',
     'Prepare an interpreter, an editor and an isolated environment for local practice.',
     'An interpreter runs Python source files. An editor helps you write those files; a terminal starts programs and shows their output. Install Python from python.org, then check its version before installing packages. On Windows use py; on many Unix systems use python3. An interactive prompt is useful for a quick expression, while a .py file keeps a repeatable program. A virtual environment isolates dependencies for one project. Run commands below in a terminal, not inside the Python prompt. Activation differs by shell; calling the environment interpreter directly also works.',
     '# Windows terminal commands\npy --version\npy -m venv .venv\n.venv\\Scripts\\python.exe -m pip --version\n\n# Save this in greeting.py:\nprint("Welcome to Shimento")\n# Then run: py greeting.py',
     'Create a practice directory, create a virtual environment and run greeting.py. Change the message and rerun the file. On macOS or Linux use python3 -m venv .venv and .venv/bin/python. Record the interpreter version you used.',
     'The virtual environment creates a separate interpreter entry point. A terminal command such as py greeting.py runs a file; print belongs inside that Python file.'),
    ('Loops and sequences',
     'Process strings, lists and tuples with indexing, slicing and iteration.',
     'A sequence keeps items in order. Index zero selects its first item; negative one selects its last. A slice excludes its stop index. Lists can change, while tuples and strings are immutable. A for loop visits items; enumerate supplies an index alongside each item. Use a while loop when repetition depends on a condition, and ensure the condition can eventually become false. Comprehensions build a new collection from existing values. Avoid removing items from a list while iterating over it; construct a filtered list instead.',
     'readings = [18, 24, 21, 30]\ncomfortable = [n for n in readings if n < 25]\nfor day, value in enumerate(comfortable, start=1):\n    print(day, value)\nprint(readings[1:3])  # [24, 21]',
     'Extract the last digit of each code in a list and join the digits into a PIN. Then build a number-pattern function that returns numbers from 1 through n separated by spaces. Test n=1 and decide how invalid inputs should be handled.',
     'The comprehension retains values below 25. Enumerate starts the display count at one. The slice includes positions one and two, but excludes position three.'),
    ('Dictionaries, sets and modules',
     'Represent named fields, remove duplicates and reuse library functions.',
     'A dictionary maps unique keys to values. Use square brackets when a key must exist, and get when absence is expected. Iterating over items yields key-value pairs. A set keeps unique hashable values and supports union, intersection and difference; it does not promise an application-level display order. Import a module to access reusable definitions without rewriting them. Validate the shape and types of incoming records before processing them. Use isinstance for type checks, remembering that bool is a subclass of int when strict numeric input matters.',
     'import math\nprofile = {"name": "Mira", "skills": ["Python", "SQL"]}\nprofile["active"] = True\nunique = set(profile["skills"] + ["Python"])\nprint(sorted(unique))  # [\'Python\', \'SQL\']\nprint(math.sqrt(81))   # 9.0',
     'Write a record validator requiring a name string and a nonempty list of skills. Report missing fields without crashing. Compare two employees\' skill sets to find shared skills. Keep your validation helper in a separate module and import it.',
     'A dictionary groups named fields. Converting a list to a set removes repeated skills. Sorting produces predictable output. The math module supplies square root.'),
    ('Project: configuration manager',
     'Combine dictionary operations and functions into a small settings manager.',
     'A configuration manager has a small contract: add a setting only when absent, update only when present, delete existing keys and display current settings consistently. Decide whether keys are case sensitive, and apply that decision at every boundary. Return a result rather than print inside every helper. This keeps the logic reusable and makes behavior easy to check. Work on one dictionary shared by the operations. Test empty settings, duplicate insertion, a missing key and a successful update. Do not store secrets in a classroom example.',
     'def add_setting(settings, key, value):\n    key = key.strip().lower()\n    if key in settings:\n        return False\n    settings[key] = value\n    return True\n\nsettings = {}\nprint(add_setting(settings, "Theme", "dark"))  # True\nprint(add_setting(settings, "theme", "light")) # False',
     'Implement update_setting, delete_setting and view_settings. Sort keys for display. Write six assertions covering duplicate keys, missing keys, whitespace normalization and an empty dictionary. This is a Shimento practice project, evaluated through your own local checks.',
     'Normalization happens before the membership check. Theme and theme become the same key, so the second insertion fails without replacing the first value.'),
    ('Error handling',
     'Distinguish invalid input from programming errors and recover deliberately.',
     'An exception interrupts normal control flow. Catch the specific exception you can handle rather than hiding every error with a bare except. Code in else runs when the try block succeeds; finally runs for cleanup. Raise ValueError when an argument has the wrong value. Keep a try block narrow so unrelated errors do not look like user mistakes. Validation still matters: successful integer conversion does not guarantee a value is positive. When calculating an ISBN check digit, validate length and allowed characters before computing the weighted sum.',
     'def positive_count(text):\n    try:\n        count = int(text)\n    except ValueError:\n        return "Enter a whole number"\n    if count <= 0:\n        return "Enter a positive number"\n    return count\n\nprint(positive_count("bad"))',
     'Build an ISBN-10 validator using the weighted sum rule: multiply the first digit by 10, the next by 9, down to 1; the sum must be divisible by 11. Permit X only as the final digit, representing 10. Test malformed input and both valid and invalid checksums.',
     'The conversion can fail with ValueError, which is handled explicitly. A separate condition rejects zero and negative values after conversion succeeds.'),
    ('Classes and objects',
     'Bundle state and behavior into instances with clear responsibilities.',
     'A class defines a kind of object. Calling the class creates an instance, and __init__ initializes its state. The self parameter refers to the instance receiving a method call. Store per-object mutable values on self rather than as shared class attributes. Methods can validate changes to that state. A useful __str__ produces a human-readable representation. Keep a class focused on one responsibility. Two inventory objects should maintain independent quantities; testing both instances helps reveal accidental shared state.',
     'class StockItem:\n    def __init__(self, name, count=0):\n        self.name = name\n        self.count = count\n\n    def receive(self, amount):\n        if amount <= 0:\n            raise ValueError("Positive amount required")\n        self.count += amount\n\nitem = StockItem("Keyboard", 2)\nitem.receive(3)\nprint(item.count)  # 5',
     'Create a Planet class with a name, radius and a description method. Then model an email message with sender, recipient, subject and a read flag. Verify that marking one message as read leaves another unchanged.',
     'The constructor initializes one stock item. Receive validates the change before increasing that instance\'s count. The example moves from two keyboards to five.'),
    ('Project: budget ledger',
     'Model deposits, withdrawals, transfers and a readable spending summary.',
     'A ledger records transactions rather than only a running total. Each entry contains an amount and a description. Deposits are positive; withdrawals are negative. Compute the balance from entries so a transaction can be traced. For money, use integer cents to avoid binary floating-point surprises. A transfer must check funds before changing either account. Failed transfers must leave both ledgers unchanged. Spending percentages count withdrawals rather than deposits. Define how transfers affect spending before you calculate a chart.',
     'class Budget:\n    def __init__(self):\n        self.entries = []\n\n    def deposit(self, cents, note=""):\n        if cents <= 0:\n            raise ValueError("Positive deposit required")\n        self.entries.append((cents, note))\n\n    def balance(self):\n        return sum(c for c, _ in self.entries)',
     'Add withdraw and transfer methods that return False for insufficient funds. Build a text spending chart for three categories. Test that a failed transfer changes neither balance and that two budget instances have separate ledgers.',
     'Each budget creates its own list. A deposit adds a positive transaction in cents. Balance is derived by summing recorded amounts, preserving the transaction history.'),
    ('Object-oriented programming',
     'Apply encapsulation, inheritance, polymorphism and abstraction.',
     'Encapsulation puts state changes behind a clear interface. A property can validate access without exposing storage details. Inheritance specializes an existing type; super lets a child reuse parent initialization. Polymorphism lets different objects respond to the same operation. An abstract base class specifies required methods and prevents incomplete implementations from being instantiated. Prefer a small interface that callers need. An underscore marks an internal implementation detail by convention; it does not secure a value. Do not use inheritance merely to avoid a few repeated lines when the objects do not share a meaningful contract.',
     'from abc import ABC, abstractmethod\n\nclass Media(ABC):\n    @abstractmethod\n    def duration(self):\n        pass\n\nclass Clip(Media):\n    def duration(self):\n        return 45\n\nprint(Clip().duration())  # 45',
     'Create a salary tracker with a property rejecting negative pay. Build a catalogue containing audio and video classes that implement the same duration method. Add an abstract player interface and verify that incomplete subclasses cannot be instantiated.',
     'Media declares a required duration method. Clip implements that contract, so it can be instantiated. Callers can request duration without knowing the concrete media type.'),
    ('Project: polygon area calculator',
     'Use related shape classes while preserving valid dimensions.',
     'A rectangle can provide area, perimeter and diagonal calculations. A square has the extra invariant that both dimensions are equal. If you inherit a square from a rectangle, every dimension-changing method must preserve that invariant. Otherwise a square can silently turn into a rectangle. Composition is another valid design. Require positive dimensions and document the units. To count how many axis-aligned smaller rectangles fit without rotation, multiply the whole-number fit across each dimension; comparing area alone is insufficient.',
     'class Rectangle:\n    def __init__(self, width, height):\n        if width <= 0 or height <= 0:\n            raise ValueError("Positive dimensions required")\n        self.width, self.height = width, height\n\n    def area(self):\n        return self.width * self.height\n\nprint(Rectangle(8, 3).area())  # 24',
     'Add perimeter and diagonal methods. Implement a Square class and a side setter that preserves equal dimensions. Check that a 2 by 2 rectangle fits four times into an 8 by 3 rectangle when rotation is disallowed. Explain why an area ratio alone gives a different answer.',
     'Area multiplies width by height. The constructor rejects invalid dimensions. Fitting shapes requires whole counts along each dimension, rather than simply dividing their areas.'),
    ('Linear data structures',
     'Compare arrays, linked lists, stacks and queues.',
     'A Python list supports fast access by index but inserting at its front shifts existing elements. A linked list connects nodes through references and traverses them in order. A stack is last-in, first-out; a queue is first-in, first-out. Use append and pop at the end of a Python list for a stack. Use collections.deque for efficient queue operations at both ends. When deleting a linked-list node, reconnect its predecessor and handle deletion of the head separately. Always test an empty structure and a single-item structure.',
     'from collections import deque\n\nstack = []\nstack.append("first")\nstack.append("second")\nprint(stack.pop())  # second\n\nqueue = deque(["first", "second"])\nprint(queue.popleft())  # first',
     'Build a linked list with append, find and delete. Test deleting the head, tail and an absent value. Use a stack to reverse a sequence, then use a queue to process tasks in arrival order. Explain the different removal orders.',
     'The stack removes the newest item, second. The queue removes the oldest item, first. Choosing the structure expresses which task should be handled next.'),
    ('Project: hash table',
     'Store key-value pairs using hashing and collision handling.',
     'A hash table maps a key to a bucket. Different keys can select the same bucket, which is a collision. Separate chaining stores a collection of key-value entries in each bucket. An insertion must update an existing key rather than creating duplicates. Lookup compares keys inside the bucket; a matching hash alone is not enough. Average lookup can be near constant time, but a bucket with many collisions takes longer. Python already supplies dict for practical programs; implementing a table here explains its underlying idea. A classroom character-sum hash is unsuitable for security.',
     'def bucket_index(key, size):\n    return sum(ord(c) for c in key) % size\n\nbuckets = [[] for _ in range(5)]\nkey, value = "team", "learning"\nindex = bucket_index(key, len(buckets))\nbuckets[index].append((key, value))\nprint(buckets[index])',
     'Implement put, get and remove using separate chaining. Find two strings that collide in a five-bucket table. Insert both, update one and remove the other, verifying the surviving value. Raise KeyError for missing keys.',
     'The character sum chooses a bucket. Each bucket owns a separate list of entries. Collisions require comparing the original keys within that list.'),
    ('Recursion and the call stack',
     'Solve smaller versions of a problem and identify a stopping condition.',
     'A recursive function calls itself. It needs a base case that stops and a recursive case that makes progress toward that base case. Each call stores its own parameters and waits for the nested result on the call stack. Deep recursion can hit Python\'s recursion limit; an iterative solution is often better for long linear sequences. Trace a tiny input by hand before running a large one. Distinguish the order in which calls are made from the order in which results return.',
     'def total_to(n):\n    if n < 0:\n        raise ValueError("Nonnegative n required")\n    if n == 0:\n        return 0\n    return n + total_to(n - 1)\n\nprint(total_to(4))  # 10',
     'Write a recursive inclusive range builder and test equal endpoints. Trace total_to(3), showing the pending additions on the stack. Rewrite total_to with a loop and compare the memory needs of the two versions.',
     'Zero is the stopping case. Each call reduces n by one. Returning from the nested calls combines four, three, two and one into ten.'),
    ('Searching and sorting algorithms',
     'Choose an algorithm based on input order and the work it performs.',
     'Linear search checks items in sequence. Binary search discards half a sorted search interval each time; it requires sorted data. Merge sort divides a sequence and merges sorted halves. Quicksort partitions around a pivot, while selection sort repeatedly selects the smallest remaining item. Binary search takes logarithmic comparisons; selection sort takes quadratic work. Big O describes growth as input size increases, not exact runtime. Bisection similarly narrows a numeric interval, but requires a continuous function with a root bracketed by the interval endpoints. Test duplicates, empty lists and missing targets.',
     'def locate(values, target):\n    lo, hi = 0, len(values) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if values[mid] == target:\n            return mid\n        if values[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1',
     'Test locate on [2, 5, 8, 12] for 8 and 7. Implement merge sort and selection sort, checking results against sorted on sample data. Implement a Luhn checksum validator: double alternating digits from the right and subtract nine when a doubled digit exceeds nine.',
     'Binary search starts with the whole sorted interval. Each comparison either finds the target or removes half the remaining candidates. An empty interval means the target is absent.'),
    ('Project: Tower of Hanoi',
     'Express a constrained puzzle using a recursive strategy.',
     'The puzzle has three pegs and differently sized disks. Move one disk at a time, and never put a larger disk on a smaller one. To move n disks, first move n minus one to the spare peg, move the largest to the destination, then move the smaller stack onto it. Moving zero disks is the base case. The minimum number of moves is two to the power n minus one. Generating moves and applying them are separate responsibilities, making illegal-move checks easier to test. Runtime grows exponentially, so start with a small disk count.',
     'def hanoi(n, source, target, spare):\n    if n < 0:\n        raise ValueError("Nonnegative n required")\n    if n == 0:\n        return []\n    return (hanoi(n - 1, source, spare, target)\n            + [(source, target)]\n            + hanoi(n - 1, spare, target, source))\n\nprint(hanoi(2, "A", "C", "B"))',
     'Simulate the moves for three disks using a list for each peg. Reject illegal moves. Assert that the final destination contains all disks in order and that the move count is seven. Explain why swapping the spare and target arguments matters.',
     'The first recursive call clears the largest disk. One move sends that disk to the target. The final call rebuilds the smaller stack above it.'),
    ('Graphs and trees',
     'Represent connections and traverse them without revisiting nodes.',
     'A graph contains vertices and edges. An adjacency list stores neighbors for each vertex; a matrix stores a grid indicating connections. Breadth-first search explores by distance in edges using a queue, and finds shortest paths in an unweighted graph. Depth-first search follows one branch before returning. A visited set prevents cycles from causing endless repetition. A tree is an acyclic connected undirected graph; rooted trees add parent-child relationships. Weighted shortest paths need an appropriate algorithm such as Dijkstra for nonnegative weights. Backtracking explores candidate choices and undoes a choice when it violates constraints.',
     'from collections import deque\ngraph = {"A": ["B", "C"], "B": ["C"], "C": []}\nqueue, seen = deque(["A"]), {"A"}\nwhile queue:\n    node = queue.popleft()\n    print(node)\n    for neighbor in graph[node]:\n        if neighbor not in seen:\n            seen.add(neighbor)\n            queue.append(neighbor)',
     'Convert an adjacency list to a matrix using a fixed vertex order. Implement depth-first traversal and compare its order to breadth-first traversal. Extend breadth-first search to record parents and reconstruct a path. For an additional challenge, solve a four-queens board using backtracking.',
     'The queue explores neighbors in layers. Nodes enter the visited set when enqueued, preventing duplicate entries. This traversal prints A, B and C once each.'),
    ('Dynamic programming',
     'Reuse overlapping subproblem results with memoization or tabulation.',
     'Some recursive problems repeat the same work. Dynamic programming stores subproblem results and reuses them. Memoization adds a cache to a top-down solution; tabulation fills results from the smallest cases upward. A Fibonacci recurrence depends on its two predecessors, so only two previous values need storage when the sequence itself is not required. Define base cases and input constraints first. Dynamic programming is useful when subproblems overlap; merely writing a loop does not establish that property. Compare the repeated calls of naive recursion to the single pass of an iterative implementation.',
     'def fibonacci(n):\n    if n < 0:\n        raise ValueError("Nonnegative n required")\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n\nprint(fibonacci(8))  # 21',
     'Implement a memoized Fibonacci function and compare its outputs with the iterative version for n from 0 through 20. Count the calls made by naive recursion and by memoization. State which values are cached and why the iterative version needs only two running values.',
     'The pair begins with Fibonacci zero and one. Each iteration advances the pair using the previous two values. Eight advances leave 21 in a.'),
    ('Python review and capstone',
     'Connect the course topics in a small, testable Python application.',
     'Review the entire path: values, functions, collections, error handling, classes, data structures, recursion, algorithms, graphs and dynamic programming. Design a small application with a clear input and output before coding. Separate validation, core logic and presentation. Use a dictionary for lookup, a class only when state and behavior belong together, and a queue when order of processing matters. Write checks for normal input, empty input and invalid input. Explain your algorithm choices in terms of input size and constraints. This Shimento learning path has its own completion tracking; it does not award an external certification or administer an external certification exam.',
     'def skill_counts(records):\n    counts = {}\n    for record in records:\n        for skill in set(record["skills"]):\n            counts[skill] = counts.get(skill, 0) + 1\n    return counts\n\nassert skill_counts([]) == {}\nassert skill_counts([{\n    "skills": ["Python", "Python"]\n}]) == {"Python": 1}',
     'Build a learning catalogue that stores employee profiles, validates skill lists, searches sorted course titles and processes enrollment requests in a queue. Supply at least eight assertions, including missing fields and duplicate skills. Write a short explanation of the data structures you chose and demonstrate the program locally.',
     'The capstone helper counts employees per skill. A set avoids counting a repeated skill twice within one record. Assertions document the expected empty-input and duplicate behavior.'),
]


def build(detailed=True):
    lessons = []
    for number, (title, summary, explanation, code, practice, walkthrough) in enumerate(TOPICS, 1):
        lessons.append({
            'slug': f'lesson-{number:02d}', 'title': title, 'description': summary,
            'durationMinutes': 35 if title.startswith('Project:') else 25,
            'completionPercent': 90,
            'content': f'{title.upper()}\n\n{explanation}\n\nWORKED EXAMPLE\n\n{code}\n\nWALKTHROUGH\n\n{walkthrough}\n\nEXTEND YOUR SKILLS\n\n{practice}',
        })
    for number, lesson in enumerate(lessons, 1):
        lesson['legacyContentHash'] = hashlib.sha256(lesson['content'].encode('utf-8')).hexdigest()
        if detailed:
            matches = list((ROOT / 'data/python-lessons-detailed').glob(f'{number:02d}-*.md'))
            if len(matches) != 1:
                raise ValueError(f'Expected one detailed module for {number}')
            lesson['content'] = matches[0].read_text(encoding='utf-8').strip()
    course = {'id': 'shimento-python-developer', 'title': 'Python Programming Senior',
              'contentRevision': 'python-detailed-v2' if detailed else '',
              'category': 'Technical Skills', 'difficulty': 'beginner',
              'durationMinutes': sum(l['durationMinutes'] for l in lessons),
              'visibility': 'everyone', 'status': 'published', 'interactive': True, 'videoEnabled': False,
              'description': 'Learn Python through interactive Shimento lessons, an in-browser code editor, coding workshops, labs and knowledge checks. Follow the Python syllabus from foundations to object-oriented programming, algorithms, graphs and dynamic programming. Six secured assignments assess each group of three modules.',
              'source': {'syllabusReference': 'https://www.freecodecamp.org/learn/python-v9/',
                         'scope': 'Original Shimento teaching material following the public topic sequence. No source lesson text, tests, videos or certification exam are reproduced.'},
              'lessons': lessons}
    practices = json.loads((ROOT / 'data/python-practice.json').read_text(encoding='utf-8'))
    assert len(practices) == len(lessons)
    for lesson, practice in zip(lessons, practices):
        lesson['quiz'] = practice['quiz']
        lesson['practice'] = {k: practice[k] for k in ('instructions', 'starter', 'tests', 'solution')}
    assignments = json.loads((ROOT / 'data/python-assignments.json').read_text(encoding='utf-8'))
    for number, assignment in enumerate(assignments, 1):
        assignment['id'] = f"{course['id']}-assignment-{number:02d}"
        assignment['afterLesson'] = number * 3
        assignment['lessonIds'] = [f"{course['id']}-{lesson['slug']}" for lesson in lessons[(number - 1) * 3:number * 3]]
    course['assignments'] = assignments
    return course


def main():
    course = build()
    path = ROOT / 'data/shimento-python-course.json'
    path.write_text(json.dumps(course, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Built {len(course['lessons'])} original lessons: {path}")


if __name__ == '__main__':
    main()
