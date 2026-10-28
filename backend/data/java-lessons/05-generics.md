## Introduction to generics
Before Java 5, collections stored plain `Object` references. You had to cast every element and a wrong type was discovered only at runtime:

```java
List list = new ArrayList();      // raw type - avoid
list.add("hello");
list.add(42);                     // compiles!
String s = (String) list.get(1);  // ClassCastException at runtime
```

**Generics** let you parameterise a type with other types, so the compiler checks them for you:

```java
List<String> names = new ArrayList<>();
names.add("hello");
// names.add(42);                 // compile error - caught early
String s = names.get(0);          // no cast needed
```

Benefits: **compile-time type safety, no casts, and reusable, self-documenting code**. The `<>` on the right side is the *diamond operator*; the compiler infers the type argument.

## Generic classes
Declare one or more **type parameters** in angle brackets after the class name. By convention they are single capital letters: `T` (type), `E` (element), `K`/`V` (key/value), `R` (result).

```java
public class Box<T> {
    private T value;

    public Box(T value) { this.value = value; }
    public T get() { return value; }
    public boolean isEmpty() { return value == null; }
}

Box<String> nameBox = new Box<>("Asha");
Box<Integer> ageBox = new Box<>(30);
String name = nameBox.get();          // no cast
int age = ageBox.get();               // auto-unboxed
```

A class can have several parameters:

```java
public record Pair<K, V>(K key, V value) { }

Pair<String, Double> price = new Pair<>("laptop", 55000.0);
System.out.println(price.key() + " = " + price.value());   // laptop = 55000.0
```

Type arguments must be reference types: write `Box<Integer>`, not `Box<int>`.

### Generic methods
A method can declare its own type parameter, placed before the return type, even inside a non-generic class.

```java
public class Utils {
    public static <T> T firstOrDefault(List<T> list, T fallback) {
        return list.isEmpty() ? fallback : list.get(0);
    }
}

String first = Utils.firstOrDefault(List.of("x", "y"), "none");   // "x"
Integer n = Utils.firstOrDefault(List.of(), 0);                   // 0
```

## Generic interfaces
Interfaces can be generic too. `Comparable<T>`, `List<E>` and `Map<K,V>` are all generic interfaces. A typical full-stack example is a repository contract:

```java
public interface Repository<T, ID> {
    void save(T entity);
    Optional<T> findById(ID id);
    List<T> findAll();
}

public class InMemoryCourseRepository implements Repository<Course, Long> {
    private final Map<Long, Course> store = new HashMap<>();
    public void save(Course c) { store.put(c.id(), c); }
    public Optional<Course> findById(Long id) { return Optional.ofNullable(store.get(id)); }
    public List<Course> findAll() { return new ArrayList<>(store.values()); }
}
```

You will meet exactly this pattern in Spring Data's `JpaRepository<Entity, ID>` (Module 29).

An implementing class can either fix the type (`implements Repository<Course, Long>`) or stay generic (`class MemoryRepo<T, ID> implements Repository<T, ID>`).

## Bounded type parameters
Sometimes the type must have certain capabilities. An **upper bound** restricts `T` to a type and its subtypes with `extends` (used for both classes and interfaces here).

```java
public static <T extends Number> double sum(List<T> values) {
    double total = 0;
    for (T v : values) total += v.doubleValue();   // allowed: T is a Number
    return total;
}

sum(List.of(1, 2, 3));          // 6.0
sum(List.of(1.5, 2.5));         // 4.0
// sum(List.of("a"));           // compile error
```

Multiple bounds use `&`, with the class first: `<T extends Number & Comparable<T>>`.

```java
public static <T extends Comparable<T>> T max(List<T> list) {
    T best = list.get(0);
    for (T item : list) if (item.compareTo(best) > 0) best = item;
    return best;
}
max(List.of(3, 9, 4));               // 9
max(List.of("pear", "apple"));       // pear
```

## Wildcards
The wildcard `?` means "some unknown type". It is used in parameters to make methods flexible.

Important: `List<Integer>` is **not** a subtype of `List<Number>`, even though `Integer` is a subtype of `Number`. Wildcards solve this.

| Wildcard | Meaning | You can | Example use |
| --- | --- | --- | --- |
| `<?>` | Any type | Read as `Object` | `printAll(List<?> list)` |
| `<? extends T>` | T or a subtype (upper bound) | Read as T; cannot add (except `null`) | A **producer** you read from |
| `<? super T>` | T or a supertype (lower bound) | Add T; read only as `Object` | A **consumer** you write to |

```java
static double total(List<? extends Number> nums) {   // accepts List<Integer>, List<Double>
    double t = 0;
    for (Number n : nums) t += n.doubleValue();
    return t;
}

static void addDefaults(List<? super Integer> target) { // accepts List<Integer>, List<Number>, List<Object>
    target.add(0);
    target.add(1);
}
```

Remember **PECS: Producer Extends, Consumer Super**. `Collections.copy(List<? super T> dest, List<? extends T> src)` follows exactly this rule.

## Type erasure
Generics exist only at compile time. The compiler checks types, inserts the necessary casts, then **erases** type parameters from the bytecode - `List<String>` and `List<Integer>` both become plain `List` at runtime (an unbounded `T` becomes `Object`; `T extends Number` becomes `Number`).

Consequences of erasure:
- You cannot write `new T()` or `new T[10]`.
- You cannot use `instanceof List<String>` (use `instanceof List<?>`).
- You cannot overload methods that differ only in type arguments: `void f(List<String>)` and `void f(List<Integer>)` clash.
- Static fields cannot use the class's type parameter.
- Primitive type arguments are not allowed.

```java
List<String> a = new ArrayList<>();
List<Integer> b = new ArrayList<>();
System.out.println(a.getClass() == b.getClass());   // true - both ArrayList
```

When you need the type at runtime, pass a `Class<T>` token: `<T> T fromJson(String json, Class<T> type)` - this is how JSON libraries such as Jackson work.

## Common mistakes
- Using raw types (`List list`) and losing all compile-time checks.
- Expecting `List<Object>` to accept a `List<String>` argument - use `List<?>`.
- Trying to `add` to a `List<? extends Number>`.
- Writing `new T()` inside a generic class.

## Practice exercise
1. Write a generic class `Cache<K, V>` with `put`, `get` returning `Optional<V>`, and `size`.
2. Add a generic method `static <T extends Comparable<T>> List<T> topN(List<T> items, int n)` that returns the n largest items.
3. Write `static double average(Collection<? extends Number> values)` and call it with a `List<Integer>` and a `Set<Double>`.
4. Write `static void fillWithZeros(List<? super Integer> list, int count)`; call it with a `List<Number>`.
5. Explain in two sentences why `Cache<String, int>` does not compile.

## Key takeaways
- Generics move type errors from runtime to compile time and remove casts.
- Generic classes and interfaces declare type parameters; generic methods declare their own.
- Bounds (`T extends X`) let you call methods of the bound type.
- Wildcards make APIs flexible: Producer Extends, Consumer Super.
- Type erasure removes type arguments at runtime, which explains generics' restrictions.
