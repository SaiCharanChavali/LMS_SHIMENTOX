## Why Java 8 changed everything
Java 8 (2014) introduced functional programming features that every modern Java code base - including Spring Boot - relies on: lambdas, streams, `Optional`, the new Date/Time API and interface default methods. This module teaches each one with examples you will reuse in later modules.

## Lambda expressions
A **lambda** is an anonymous function: a short block of code you can pass around as a value.

Syntax: `(parameters) -> expression` or `(parameters) -> { statements; }`

```java
// Before Java 8: anonymous inner class
Comparator<String> byLength = new Comparator<String>() {
    public int compare(String a, String b) { return a.length() - b.length(); }
};

// With a lambda
Comparator<String> byLength2 = (a, b) -> a.length() - b.length();

List<String> names = new ArrayList<>(List.of("Ravi", "Mei", "Alexander"));
names.sort(byLength2);
System.out.println(names);   // [Mei, Ravi, Alexander]
```

Rules: parameter types are usually inferred; parentheses are optional for a single parameter (`x -> x * 2`); braces and `return` are needed for multiple statements. A lambda can use local variables from the enclosing scope only if they are **effectively final** (never reassigned).

## Functional interfaces
A lambda needs a target type: a **functional interface**, which has exactly one abstract method. Mark your own with `@FunctionalInterface` so the compiler enforces that.

```java
@FunctionalInterface
interface Discount {
    double apply(double price);
}
Discount festive = p -> p * 0.9;
System.out.println(festive.apply(1000));   // 900.0
```

The `java.util.function` package provides the common shapes:

| Interface | Method | Shape | Example |
| --- | --- | --- | --- |
| `Predicate<T>` | `test(T)` | T → boolean | `s -> s.isEmpty()` |
| `Function<T,R>` | `apply(T)` | T → R | `s -> s.length()` |
| `Consumer<T>` | `accept(T)` | T → nothing | `s -> System.out.println(s)` |
| `Supplier<T>` | `get()` | nothing → T | `() -> new ArrayList<>()` |
| `UnaryOperator<T>` | `apply(T)` | T → T | `s -> s.trim()` |
| `BinaryOperator<T>` | `apply(T,T)` | (T,T) → T | `(a, b) -> a + b` |

They can be combined: `isLong.and(startsWithA)`, `trim.andThen(upper)`.

## Method references
When a lambda only calls an existing method, a **method reference** (`::`) is shorter.

| Kind | Syntax | Equivalent lambda |
| --- | --- | --- |
| Static method | `Integer::parseInt` | `s -> Integer.parseInt(s)` |
| Instance method of a particular object | `System.out::println` | `x -> System.out.println(x)` |
| Instance method of an arbitrary object | `String::toUpperCase` | `s -> s.toUpperCase()` |
| Constructor | `ArrayList::new` | `() -> new ArrayList<>()` |

```java
List.of("a", "b").forEach(System.out::println);
```

## Streams API
A **stream** is a pipeline that processes a sequence of elements declaratively: *what* you want, not *how* to loop. A pipeline has a **source**, zero or more **intermediate operations** (lazy) and one **terminal operation** (triggers execution).

```java
record Employee(String name, String dept, double salary) { }

List<Employee> staff = List.of(
    new Employee("Asha", "Engineering", 90000),
    new Employee("Ravi", "Sales", 50000),
    new Employee("Mei", "Engineering", 120000),
    new Employee("Omar", "Sales", 65000));

List<String> highEarners = staff.stream()
    .filter(e -> e.salary() > 60000)        // intermediate
    .map(Employee::name)                    // intermediate
    .sorted()                               // intermediate
    .toList();                              // terminal (Java 16+)
System.out.println(highEarners);   // [Asha, Mei, Omar]
```

Common operations:
- Intermediate: `filter`, `map`, `flatMap`, `distinct`, `sorted`, `limit`, `skip`, `peek`
- Terminal: `forEach`, `collect`, `toList`, `count`, `sum` (on number streams), `min`/`max`, `reduce`, `anyMatch`/`allMatch`/`noneMatch`, `findFirst`

### Collectors
```java
Map<String, List<Employee>> byDept = staff.stream()
    .collect(Collectors.groupingBy(Employee::dept));

Map<String, Double> avgSalary = staff.stream()
    .collect(Collectors.groupingBy(Employee::dept, Collectors.averagingDouble(Employee::salary)));
System.out.println(avgSalary);   // {Engineering=105000.0, Sales=57500.0}

double total = staff.stream().mapToDouble(Employee::salary).sum();      // 325000.0
String names = staff.stream().map(Employee::name).collect(Collectors.joining(", "));
```

Stream rules: a stream can be consumed only once; operations should not modify the source; keep lambdas free of side effects. `parallelStream()` can help CPU-heavy work on large data but adds overhead and must never write to shared non-thread-safe state.

## Optional class
`Optional<T>` is a container that may or may not hold a value. It makes "no result" explicit in a method's return type instead of returning `null`.

```java
Optional<Employee> top = staff.stream()
    .max(Comparator.comparingDouble(Employee::salary));

System.out.println(top.map(Employee::name).orElse("nobody"));   // Mei

Optional<String> missing = Optional.empty();
missing.ifPresent(System.out::println);           // does nothing
String v = missing.orElseGet(() -> "default");     // lazily computed fallback
// missing.orElseThrow(() -> new IllegalStateException("Not found"));
```

Prefer `map`, `filter`, `orElse`, `orElseThrow` and `ifPresent` over calling `get()` (which throws if empty). Use `Optional` for return values, not for fields or method parameters.

## Date and Time API
The `java.time` package replaces the old mutable `Date` and `Calendar`. Its classes are **immutable** and thread-safe.

| Class | Represents | Example |
| --- | --- | --- |
| `LocalDate` | A date without time or zone | 2026-10-27 |
| `LocalTime` | A time without date | 14:30 |
| `LocalDateTime` | Date and time, no zone | 2026-10-27T14:30 |
| `ZonedDateTime` | Date, time and time zone | 2026-10-27T14:30+05:30[Asia/Kolkata] |
| `Instant` | A point on the UTC timeline | for timestamps and logs |
| `Duration` / `Period` | Time-based / date-based amount | `Duration.ofMinutes(90)`, `Period.ofDays(7)` |

```java
LocalDate joined = LocalDate.of(2024, 3, 15);
LocalDate review = joined.plusMonths(6);
System.out.println(review);                                  // 2024-09-15
System.out.println(ChronoUnit.DAYS.between(joined, review)); // 184

DateTimeFormatter fmt = DateTimeFormatter.ofPattern("dd MMM yyyy");
System.out.println(review.format(fmt));                      // 15 Sep 2024
LocalDate parsed = LocalDate.parse("2026-01-31");
```

Store timestamps as `Instant` (UTC) and convert to a user's zone only for display.

## Default and static methods in interfaces
Before Java 8, adding a method to an interface broke every implementing class. A **default method** has a body, so existing implementations inherit it automatically. A **static method** in an interface is a helper called on the interface itself.

```java
interface Greeter {
    String name();

    default String greet() {                 // inherited by all implementations
        return "Hello, " + name() + "!";
    }

    static Greeter of(String n) {            // factory helper
        return () -> n;
    }
}

System.out.println(Greeter.of("Asha").greet());   // Hello, Asha!
```

If a class implements two interfaces with the same default method, it must override the method and may pick one with `InterfaceName.super.method()`.

## Common mistakes
- Reassigning a local variable used inside a lambda (must be effectively final).
- Reusing a consumed stream (`IllegalStateException`).
- Forgetting a terminal operation, so nothing executes.
- Calling `Optional.get()` without checking.
- Using `LocalDateTime` for global timestamps instead of `Instant`.

## Practice exercise
Given a `List<Order>` where `Order(String customer, String category, double amount, LocalDate date)`:
1. Print the total revenue.
2. Find the top three orders by amount.
3. Group revenue by category with `Collectors.groupingBy` and `summingDouble`.
4. Find the first order above 10,000 as an `Optional` and print "none" if absent.
5. List distinct customers who ordered in the last 30 days, sorted alphabetically.
6. Write a functional interface `TaxRule` and two lambda implementations.

## Key takeaways
- Lambdas implement functional interfaces concisely; method references are even shorter.
- Streams express data processing as filter/map/collect pipelines.
- `Optional` makes absence explicit - avoid bare `get()`.
- `java.time` types are immutable; pick the one that matches the meaning of your data.
- Default methods let interfaces evolve without breaking implementations.
