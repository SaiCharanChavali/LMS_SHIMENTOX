## Introduction to the Collections Framework
Arrays have a fixed size and few helper methods. The **Java Collections Framework** (package `java.util`) provides resizable data structures behind a small set of interfaces, so you can change the implementation without rewriting the code that uses it.

```
Iterable
└── Collection
    ├── List   (ordered, allows duplicates)   → ArrayList, LinkedList
    ├── Set    (no duplicates)                → HashSet, LinkedHashSet, TreeSet
    └── Queue  (processing order)             → ArrayDeque, PriorityQueue, LinkedList
Map (key → value, not a Collection)           → HashMap, LinkedHashMap, TreeMap
```

**Program to the interface:** declare `List<String> names = new ArrayList<>();` so you can swap in another `List` later.

## The List interface
A `List` keeps insertion order, allows duplicates and supports index access.

```java
List<String> skills = new ArrayList<>();
skills.add("Java");
skills.add("SQL");
skills.add("Java");               // duplicates allowed
skills.add(1, "React");           // insert at index 1
System.out.println(skills);       // [Java, React, SQL, Java]
System.out.println(skills.get(2)); // SQL
skills.remove("SQL");
System.out.println(skills.size()); // 3
System.out.println(skills.contains("React")); // true
```

| Implementation | Strength | Weakness |
| --- | --- | --- |
| `ArrayList` | Fast random access `get(i)` | Inserting/removing in the middle shifts elements |
| `LinkedList` | Fast insert/remove at the ends | Slow `get(i)`; more memory per element |

Use `ArrayList` by default. `List.of(...)` creates an **immutable** list - calling `add` on it throws `UnsupportedOperationException`.

## The Set interface
A `Set` stores unique elements.

```java
Set<String> tags = new HashSet<>(List.of("java", "spring", "java", "sql"));
System.out.println(tags.size());      // 3
System.out.println(tags.add("sql"));  // false - already present
```

| Implementation | Order | Typical use |
| --- | --- | --- |
| `HashSet` | No guaranteed order | Fast membership checks |
| `LinkedHashSet` | Insertion order | Unique items, predictable display |
| `TreeSet` | Sorted (natural or comparator) | Sorted unique items, range queries |

Hash-based sets rely on `equals` and `hashCode`. If you put your own objects in a `HashSet` or use them as `HashMap` keys, override **both** consistently: equal objects must have equal hash codes.

## The Queue interface
A `Queue` holds elements waiting to be processed.

```java
Queue<String> tickets = new ArrayDeque<>();
tickets.offer("T1");
tickets.offer("T2");
System.out.println(tickets.peek()); // T1 (look, do not remove)
System.out.println(tickets.poll()); // T1 (remove)
System.out.println(tickets);        // [T2]

Queue<Integer> pq = new PriorityQueue<>(List.of(5, 1, 3));
System.out.println(pq.poll());      // 1 - smallest first
```

- `ArrayDeque` works as a FIFO queue **and** as a stack (`push`/`pop`) - prefer it over the legacy `Stack` class.
- `PriorityQueue` always returns the smallest (or highest-priority) element first.
- `offer`/`poll`/`peek` return `false`/`null` on failure; `add`/`remove`/`element` throw exceptions.

## The Map interface
A `Map` associates unique keys with values.

```java
Map<String, Integer> stock = new HashMap<>();
stock.put("laptop", 5);
stock.put("mouse", 20);
stock.put("laptop", 7);                     // replaces the old value
System.out.println(stock.get("laptop"));    // 7
System.out.println(stock.getOrDefault("pen", 0)); // 0
stock.merge("mouse", 5, Integer::sum);      // 25

for (Map.Entry<String, Integer> e : stock.entrySet()) {
    System.out.println(e.getKey() + " -> " + e.getValue());
}
```

| Implementation | Order | Notes |
| --- | --- | --- |
| `HashMap` | None | Fastest general choice; allows one `null` key |
| `LinkedHashMap` | Insertion (or access) order | Useful for LRU caches |
| `TreeMap` | Sorted by key | `firstKey`, `headMap`, `ceilingKey` |

### Word-count example
```java
String text = "to be or not to be";
Map<String, Integer> counts = new TreeMap<>();
for (String w : text.split(" ")) counts.merge(w, 1, Integer::sum);
System.out.println(counts);   // {be=2, not=1, or=1, to=2}
```

## Cursors: Iterator, ListIterator and Enumeration
A **cursor** walks through a collection one element at a time.

```java
List<Integer> nums = new ArrayList<>(List.of(1, 2, 3, 4, 5));
Iterator<Integer> it = nums.iterator();
while (it.hasNext()) {
    if (it.next() % 2 == 0) it.remove();   // safe removal
}
System.out.println(nums);   // [1, 3, 5]
```

- `Iterator` - forward only, supports `remove()`; works with every collection.
- `ListIterator` - for lists; moves forward and backward, supports `add` and `set`.
- `Enumeration` - legacy cursor for `Vector`/`Hashtable`; read only.

Removing elements inside a for-each loop with `list.remove(x)` throws `ConcurrentModificationException`. Use `iterator.remove()` or `list.removeIf(n -> n % 2 == 0)`.

## Comparable and Comparator
### Comparable - natural ordering
A class implements `Comparable<T>` and its `compareTo` method to define its default order (negative = before, zero = equal, positive = after).

```java
record Student(String name, int marks) implements Comparable<Student> {
    public int compareTo(Student other) {
        return Integer.compare(this.marks, other.marks);
    }
}
List<Student> list = new ArrayList<>(List.of(
    new Student("Asha", 88), new Student("Ravi", 72), new Student("Mei", 95)));
Collections.sort(list);   // by marks ascending
```

### Comparator - external orderings
A `Comparator` defines an ordering outside the class, so you can have many.

```java
list.sort(Comparator.comparing(Student::name));                    // by name
list.sort(Comparator.comparingInt(Student::marks).reversed());     // highest marks first
list.sort(Comparator.comparing(Student::marks)
                    .thenComparing(Student::name));                // tie-break by name
```

| Comparable | Comparator |
| --- | --- |
| `java.lang`, method `compareTo(T o)` | `java.util`, method `compare(T a, T b)` |
| One natural order, inside the class | Many orders, outside the class |
| Changes the class | Works for classes you cannot modify |

## The Collections utility class
`java.util.Collections` (note the "s") holds static helpers:

```java
List<Integer> n = new ArrayList<>(List.of(4, 1, 3));
Collections.sort(n);                       // [1, 3, 4]
Collections.reverse(n);                    // [4, 3, 1]
Collections.shuffle(n);
System.out.println(Collections.max(n));    // 4
System.out.println(Collections.frequency(List.of("a","b","a"), "a")); // 2
List<Integer> ro = Collections.unmodifiableList(n);   // read-only view
```

## Common mistakes
- Using `List` when you need fast lookup by key - use a `Map`.
- Custom objects in a `HashSet` without `equals`/`hashCode`, leading to duplicates.
- Modifying a list inside a for-each loop.
- Calling `add` on `List.of(...)`.
- Assuming `HashMap` iteration order is stable.

## Practice exercise
1. Build a `Library` class with `Map<String, Book>` keyed by ISBN and a `Set<String>` of genres.
2. Keep a `Queue<String>` of members waiting for a borrowed book; serve them in FIFO order.
3. Implement `Comparable<Book>` by title, then print books sorted by year (descending) using a `Comparator`.
4. Remove all books older than 2000 using an `Iterator` and then using `removeIf` - compare the code.

## Key takeaways
- List = ordered with duplicates, Set = unique, Queue = processing order, Map = key/value lookup.
- Program to interfaces; pick `ArrayList`, `HashSet`, `HashMap`, `ArrayDeque` by default.
- Override `equals` and `hashCode` together for hash-based collections.
- Use `Iterator.remove` or `removeIf` to remove while iterating.
- `Comparable` = one natural order; `Comparator` = any number of custom orders.
