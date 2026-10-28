## Why object-oriented programming
Object-oriented programming (OOP) organises code around **objects** that bundle data (fields) with the behaviour (methods) that keeps that data valid. Instead of passing loose variables between functions, you model the domain - `Employee`, `Course`, `Order` - and let each object protect its own rules. The four pillars are **encapsulation, inheritance, polymorphism and abstraction**.

## Classes, objects and constructors
### Classes and objects
A **class** is a blueprint; an **object** is an instance created from it with `new`.

```java
public class Course {
    String title;
    int durationHours;

    void describe() {
        System.out.println(title + " (" + durationHours + "h)");
    }
}

Course java = new Course();
java.title = "Java Basics";
java.durationHours = 12;
java.describe();   // Java Basics (12h)
```

Each object has its own copy of instance fields.

### Constructors
A constructor runs when an object is created. It has the class name and no return type. Use it to guarantee a valid starting state.

```java
public class Course {
    private final String title;
    private int durationHours;

    public Course(String title, int durationHours) {
        if (title == null || title.isBlank()) throw new IllegalArgumentException("Title required");
        this.title = title;
        this.durationHours = durationHours;
    }

    public Course(String title) {      // overloaded constructor
        this(title, 1);                // calls the other constructor
    }
}
```

If you write no constructor, Java supplies a no-argument default. Once you write any constructor, the default disappears.

## The this, static and final keywords
- **`this`** refers to the current object. Use it to tell a field from a parameter with the same name (`this.title = title`) or to call another constructor (`this(...)`).
- **`static`** members belong to the class, not to any object. `Math.max` and a shared counter are static. A static method cannot use `this` or instance fields directly.
- **`final`** means "cannot change": a final variable is assigned once, a final method cannot be overridden, a final class cannot be extended (`String` is final).

```java
public class Employee {
    private static int created = 0;        // shared by all employees
    private final int id;                  // fixed after construction
    private String name;

    public Employee(String name) {
        this.name = name;
        this.id = ++created;
    }
    public static int count() { return created; }
}

new Employee("Asha");
new Employee("Ravi");
System.out.println(Employee.count());   // 2
```

Do not store per-user data (such as a shopping cart) in a static field - every user would share it.

## Encapsulation and access modifiers
**Encapsulation** hides internal state and exposes controlled operations. Make fields `private` and provide methods that enforce the rules.

```java
public class BankAccount {
    private double balance;

    public void deposit(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Amount must be positive");
        balance += amount;
    }
    public void withdraw(double amount) {
        if (amount > balance) throw new IllegalStateException("Insufficient funds");
        balance -= amount;
    }
    public double getBalance() { return balance; }
}
```

Nobody can set `balance = -500` from outside; every change goes through validation.

### Access modifiers

| Modifier | Same class | Same package | Subclass (other package) | Everywhere |
| --- | --- | --- | --- | --- |
| `private` | yes | no | no | no |
| (default / package-private) | yes | yes | no | no |
| `protected` | yes | yes | yes | no |
| `public` | yes | yes | yes | yes |

Start with the most restrictive modifier and open up only when needed.

## Inheritance and polymorphism
### Inheritance
A subclass **extends** a parent class and inherits its non-private members. Use inheritance for a true "is-a" relationship.

```java
class Employee {
    protected String name;
    Employee(String name) { this.name = name; }
    double monthlyPay() { return 30000; }
}

class Manager extends Employee {
    private double bonus;
    Manager(String name, double bonus) {
        super(name);                 // call the parent constructor first
        this.bonus = bonus;
    }
    @Override
    double monthlyPay() { return super.monthlyPay() + bonus; }
}
```

Java supports single class inheritance (one parent class) but a class can implement many interfaces. Every class ultimately extends `Object`, which provides `toString`, `equals` and `hashCode`.

### Polymorphism
"Many forms": one reference type, different runtime behaviour.
- **Compile-time polymorphism** - method overloading (same name, different parameters).
- **Runtime polymorphism** - method overriding; the JVM picks the method of the actual object.

```java
List<Employee> staff = List.of(new Employee("Asha"), new Manager("Ravi", 10000));
for (Employee e : staff) {
    System.out.println(e.name + ": " + e.monthlyPay());
}
// Asha: 30000.0
// Ravi: 40000.0
```

The loop is written once against `Employee`, yet each object answers with its own version of `monthlyPay`.

## Abstraction: abstract classes and interfaces
**Abstraction** exposes *what* an object does and hides *how*.

### Abstract classes
An abstract class cannot be instantiated. It can hold state, constructors and concrete methods, plus abstract methods that subclasses must implement.

```java
abstract class Shape {
    abstract double area();
    void print() { System.out.printf("Area: %.2f%n", area()); }
}
class Circle extends Shape {
    private final double r;
    Circle(double r) { this.r = r; }
    double area() { return Math.PI * r * r; }
}
new Circle(2).print();   // Area: 12.57
```

### Interfaces
An interface is a contract: a set of method signatures. A class can implement many interfaces. Since Java 8 interfaces may also have `default` and `static` methods.

```java
interface Notifier {
    void send(String to, String message);
}
class EmailNotifier implements Notifier {
    public void send(String to, String message) {
        System.out.println("Email to " + to + ": " + message);
    }
}
class SmsNotifier implements Notifier {
    public void send(String to, String message) {
        System.out.println("SMS to " + to + ": " + message);
    }
}
```

Code that depends on `Notifier` works with either implementation - this is the basis of dependency injection in Spring.

| Abstract class | Interface |
| --- | --- |
| Can have fields with state and constructors | Only constants (no instance state) |
| A class extends only one | A class implements many |
| Use for closely related classes sharing code | Use for a capability shared by unrelated classes |

## Packages
A **package** groups related classes and prevents name clashes. The package matches the folder structure.

```java
// file: src/com/shimento/lms/model/Course.java
package com.shimento.lms.model;

public class Course { /* ... */ }

// another file
import com.shimento.lms.model.Course;
```

Convention: reverse domain name, all lowercase (`com.company.project.layer`).

## Common mistakes
- Public fields that let callers bypass validation.
- Using inheritance for code reuse when the relationship is "has-a" - prefer composition (a field of the other type).
- Forgetting `super(...)` when the parent has no no-argument constructor.
- Overloading when you meant overriding (a different parameter type creates a new method). Always add `@Override`.
- Static mutable state shared accidentally between users or threads.

## Practice exercise
1. Create an abstract class `Employee` with `name`, `id` and an abstract `double monthlyPay()`.
2. Add `FullTimeEmployee` (fixed salary) and `Contractor` (hourly rate × hours).
3. Create an interface `Taxable` with `double tax()` and implement it in both classes.
4. Put the classes in a package `com.yourname.payroll` and print a payroll report for a mixed `List<Employee>`.
5. Make all fields private, validate constructor arguments and use `final` where a value never changes.

## Key takeaways
- A class is a blueprint, an object is an instance; constructors establish a valid state.
- `this` refers to the current object, `static` belongs to the class, `final` prevents change.
- Encapsulation = private fields + validating methods.
- Inheritance models "is-a"; polymorphism lets one call site run different implementations.
- Abstract classes share code among related types; interfaces define contracts for any type.
