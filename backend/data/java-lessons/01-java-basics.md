## Introduction to Java
Java is a general-purpose, statically typed, object-oriented language. You write source code in `.java` files, the compiler turns it into **bytecode** (`.class` files), and the Java Virtual Machine runs that bytecode on any operating system that has a JVM. This "write once, run anywhere" model is why Java powers backend services, Android apps, banking systems and big-data tools.

Key characteristics you will rely on throughout this course:
- **Statically typed:** every variable has a declared type that the compiler checks before the program runs.
- **Object-oriented:** programs are built from classes and objects (Module 2).
- **Garbage collected:** the JVM frees memory that is no longer reachable, so you do not call `free` yourself.
- **Huge standard library:** collections, I/O, networking, concurrency and date/time come built in.

## Setting up: JDK, IDE and the JVM
### Install the JDK
Download a current LTS JDK (Java 21 is a good choice) from a vendor such as Oracle, Eclipse Temurin or Microsoft. After installing, open a new terminal and check both tools:

```bash
java --version
javac --version
```

If `javac` is "not recognized", the JDK `bin` folder is missing from your `PATH`, or only a runtime is installed.

### Install IntelliJ IDEA or Eclipse
An IDE gives you code completion, refactoring and a debugger. IntelliJ IDEA Community Edition and Eclipse are both free. Create a new Java project, pick the JDK you installed as the "Project SDK", and the IDE will compile and run for you. Still learn the terminal commands: build servers and Docker images do not have an IDE.

### JDK vs JRE vs JVM

| Component | What it contains | Who needs it |
| --- | --- | --- |
| JVM (Java Virtual Machine) | The engine that loads and executes bytecode, manages memory and garbage collection | Every machine that runs Java |
| JRE (Java Runtime Environment) | JVM + core class libraries needed to run programs | Users who only run Java apps |
| JDK (Java Development Kit) | JRE + developer tools: `javac`, `jar`, `javadoc`, `jshell`, debugger | Developers |

In short: **JDK ⊃ JRE ⊃ JVM**. Modern JDK distributions no longer ship a separate JRE download, but the concept still explains what each layer does.

## Your first Java program
Create a file named `Hello.java`. The file name must match the public class name.

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, Java!");
    }
}
```

```bash
javac Hello.java     # creates Hello.class (bytecode)
java Hello           # runs it - note: no .class extension
```

Output:

```
Hello, Java!
```

Line by line: `public class Hello` declares a class; `public static void main(String[] args)` is the entry point the JVM looks for; `System.out.println` prints a line to standard output.

## Variables, data types and operators
### Variables
A variable is a named storage location with a type: `int age = 25;`. Since Java 10 you can use `var` for local variables when the type is obvious from the right-hand side: `var name = "Asha";` (still statically typed as `String`).

### Primitive data types

| Type | Size | Example | Use for |
| --- | --- | --- | --- |
| `byte` | 8 bit | `byte b = 100;` | raw binary data |
| `short` | 16 bit | `short s = 3000;` | rarely used |
| `int` | 32 bit | `int count = 42;` | whole numbers (default choice) |
| `long` | 64 bit | `long views = 9_000_000_000L;` | large whole numbers, timestamps |
| `float` | 32 bit | `float f = 3.14f;` | rarely used |
| `double` | 64 bit | `double price = 19.99;` | fractional numbers (default choice) |
| `char` | 16 bit | `char grade = 'A';` | a single UTF-16 character |
| `boolean` | true/false | `boolean active = true;` | conditions |

Everything else (such as `String`, arrays and your own classes) is a **reference type**: the variable holds a reference to an object on the heap.

### Operators
- Arithmetic: `+ - * / %` (`%` is remainder)
- Comparison: `== != < > <= >=`
- Logical: `&&` (and), `||` (or), `!` (not) - `&&` and `||` short-circuit
- Assignment: `= += -= *= /=`; increment/decrement: `++ --`
- Ternary: `condition ? valueIfTrue : valueIfFalse`

Watch integer division: `7 / 2` is `3` because both operands are `int`. Write `7 / 2.0` or `(double) 7 / 2` to get `3.5`.

```java
int a = 7, b = 2;
System.out.println(a / b);          // 3
System.out.println(a % b);          // 1
System.out.println((double) a / b); // 3.5
String result = a > b ? "a wins" : "b wins";
System.out.println(result);         // a wins
```

## Input and output
### Output
`System.out.println` prints with a newline, `System.out.print` without one, and `System.out.printf` formats: `System.out.printf("Total: %.2f%n", 12.5);` prints `Total: 12.50`.

### Command-line arguments
Values typed after the class name arrive in the `args` array.

```java
public class Greet {
    public static void main(String[] args) {
        if (args.length == 0) {
            System.out.println("Usage: java Greet <name>");
            return;
        }
        System.out.println("Hello, " + args[0]);
    }
}
```

Running `java Greet Ravi` prints `Hello, Ravi`. Always check `args.length` before indexing.

### The Scanner class
`Scanner` reads typed input from the keyboard (or a file).

```java
import java.util.Scanner;

public class AddTwo {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        System.out.print("First number: ");
        int x = in.nextInt();
        System.out.print("Second number: ");
        int y = in.nextInt();
        System.out.println("Sum = " + (x + y));
    }
}
```

Note: after `nextInt()`, the newline is still in the buffer, so a following `nextLine()` returns an empty string. Call an extra `in.nextLine()` to consume it.

## Control flow and methods
### Conditions and loops
```java
int score = 82;
if (score >= 90) System.out.println("A");
else if (score >= 75) System.out.println("B");   // prints B
else System.out.println("C");

for (int i = 1; i <= 3; i++) System.out.print(i + " ");   // 1 2 3
int n = 3;
while (n > 0) { n--; }                                    // runs 3 times
```

Java also has `do-while` (runs at least once), `switch` (including the modern arrow form `case 1 -> ...`), `break` and `continue`.

### Methods
A method is a named, reusable block with parameters and a return type.

```java
static int square(int x) {
    return x * x;
}

static double average(int[] values) {
    if (values.length == 0) return 0;
    int sum = 0;
    for (int v : values) sum += v;
    return (double) sum / values.length;
}
```

Java is **pass-by-value**: a method receives a copy of each argument. For objects the copy is a copy of the reference, so the method can change the object's contents but cannot make the caller's variable point to a different object. Methods can be **overloaded**: same name, different parameter lists.

## Arrays, strings and wrapper classes
### Arrays
An array has a fixed length and zero-based indexes.

```java
int[] marks = {70, 85, 92};
System.out.println(marks.length);   // 3
System.out.println(marks[0]);       // 70
// marks[3] throws ArrayIndexOutOfBoundsException
int[][] grid = new int[2][3];       // 2 rows, 3 columns, all 0
```

Use `java.util.Arrays` helpers: `Arrays.sort(marks)`, `Arrays.toString(marks)`.

### Strings
`String` objects are **immutable**: methods return new strings.

```java
String s = "  Java Full Stack ";
System.out.println(s.trim());                 // "Java Full Stack"
System.out.println(s.trim().toUpperCase());   // "JAVA FULL STACK"
System.out.println("java".equals("JAVA"));    // false
System.out.println("java".equalsIgnoreCase("JAVA")); // true
```

Compare text with `equals`, never `==` (which compares references). For building strings in loops, use `StringBuilder`:

```java
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 3; i++) sb.append(i).append(',');
System.out.println(sb);   // 0,1,2,
```

### Wrapper classes
Each primitive has a wrapper class: `int` → `Integer`, `double` → `Double`, `char` → `Character`, `boolean` → `Boolean`, and so on. Collections can only hold objects, so Java converts automatically (**autoboxing** and **unboxing**):

```java
List<Integer> nums = new ArrayList<>();
nums.add(5);                         // autoboxing int -> Integer
int first = nums.get(0);             // unboxing Integer -> int
int parsed = Integer.parseInt("42"); // String -> int
```

Beware: unboxing a `null` wrapper throws `NullPointerException`, and comparing two `Integer` objects with `==` compares references - use `equals`.

## Common mistakes
- File name does not match the public class name, so `javac` reports an error.
- Running `java Hello.class` instead of `java Hello`.
- Integer division silently dropping the fraction.
- Comparing strings with `==`.
- Accessing `args[0]` or `array[length]` without checking the length.

## Practice exercise
1. Write `GradeCalculator.java` that reads five marks with `Scanner`, stores them in an array and prints the total, the average with two decimals, and the highest mark.
2. Print a letter grade using `if/else if` (A ≥ 90, B ≥ 75, C ≥ 50, otherwise F).
3. Move the average calculation into a method `static double average(int[] marks)` and reject an empty array.
4. Accept the student name as a command-line argument and print a formatted report using `printf`.

## Key takeaways
- The JDK compiles (`javac`), the JVM runs bytecode (`java`).
- Choose `int`/`long` for whole numbers and `double` for fractions; watch integer division.
- Strings are immutable - compare with `equals`, build with `StringBuilder`.
- Arrays have fixed length and zero-based indexes.
- Wrapper classes let primitives live in collections through autoboxing.
