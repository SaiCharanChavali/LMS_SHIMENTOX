## Introduction to exceptions
An **exception** is an event that disrupts the normal flow of a program: a missing file, invalid input, a network timeout or a bug such as dividing by zero. Java represents these events as objects. When something goes wrong, the code **throws** an exception, and the JVM unwinds the call stack until it finds code that **catches** it. If nobody catches it, the thread stops and the stack trace is printed.

### The exception hierarchy

```
Throwable
├── Error                  (serious JVM problems: OutOfMemoryError, StackOverflowError)
└── Exception
    ├── IOException, SQLException ...        (checked)
    └── RuntimeException                       (unchecked)
        ├── NullPointerException
        ├── ArithmeticException
        ├── IllegalArgumentException
        └── ArrayIndexOutOfBoundsException
```

| Type | Must you handle or declare it? | Typical cause | Examples |
| --- | --- | --- | --- |
| Checked | Yes - the compiler enforces it | External conditions the program should anticipate | `IOException`, `SQLException` |
| Unchecked (`RuntimeException`) | No | Programming errors or broken method contracts | `NullPointerException`, `IllegalArgumentException` |
| `Error` | No - do not catch normally | JVM/resource failure | `OutOfMemoryError` |

## The try-catch block
Put code that may fail inside `try`, and handle specific exceptions in `catch` blocks.

```java
public class SafeDivide {
    public static void main(String[] args) {
        try {
            int total = Integer.parseInt(args[0]);
            int parts = Integer.parseInt(args[1]);
            System.out.println("Each part: " + total / parts);
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("Usage: java SafeDivide <total> <parts>");
        } catch (NumberFormatException e) {
            System.out.println("Please enter whole numbers: " + e.getMessage());
        } catch (ArithmeticException e) {
            System.out.println("Parts cannot be zero");
        }
        System.out.println("Program continues");
    }
}
```

`java SafeDivide 10 0` prints:

```
Parts cannot be zero
Program continues
```

Rules:
- Order catch blocks from **most specific to most general**; a `catch (Exception e)` before `catch (NumberFormatException e)` will not compile.
- Use **multi-catch** when the handling is identical: `catch (NumberFormatException | ArithmeticException e)`.
- Keep the `try` block small so you know exactly which operation failed.

## final, finally and finalize
These three look alike but are unrelated.

| Keyword | What it is | Example |
| --- | --- | --- |
| `final` | Modifier: variable cannot be reassigned, method cannot be overridden, class cannot be extended | `final int MAX = 3;` |
| `finally` | Block that runs after `try`/`catch` whether or not an exception occurred | closing a resource, releasing a lock |
| `finalize()` | Old `Object` method the GC might call before reclaiming an object - deprecated, unreliable, do not use | - |

```java
Scanner in = null;
try {
    in = new Scanner(new File("data.txt"));
    System.out.println(in.nextLine());
} catch (FileNotFoundException e) {
    System.out.println("File missing");
} finally {
    if (in != null) in.close();   // always runs
    System.out.println("Cleanup done");
}
```

### try-with-resources (preferred)
Any object implementing `AutoCloseable` can be declared in the `try` header; Java closes it automatically, even when an exception is thrown.

```java
try (Scanner in = new Scanner(new File("data.txt"))) {
    System.out.println(in.nextLine());
} catch (FileNotFoundException e) {
    System.out.println("File missing");
}
```

This is shorter and safer than a manual `finally`. Use it for files, streams, JDBC connections and statements.

## throw and throws
- **`throw`** actually raises an exception object: `throw new IllegalArgumentException("Age must be positive");`
- **`throws`** in a method signature declares that the method may pass a checked exception to its caller.

```java
import java.io.*;
import java.nio.file.*;

public class ConfigReader {
    // declares the checked exception; the caller decides how to handle it
    static String readFirstLine(String path) throws IOException {
        return Files.readAllLines(Path.of(path)).get(0);
    }

    static void setAge(int age) {
        if (age < 0) throw new IllegalArgumentException("Age cannot be negative: " + age);
        System.out.println("Age set to " + age);
    }

    public static void main(String[] args) {
        try {
            System.out.println(readFirstLine("app.conf"));
        } catch (IOException e) {
            System.out.println("Could not read config: " + e.getMessage());
        }
        setAge(30);    // Age set to 30
        setAge(-1);    // throws IllegalArgumentException, program stops here
    }
}
```

## Custom exceptions
Create your own exception class when callers need to recognise a specific business failure.

```java
public class InsufficientBalanceException extends Exception {
    public InsufficientBalanceException(double needed) {
        super("Insufficient balance, need " + needed + " more");
    }
}

class Account {
    private double balance = 100;
    void withdraw(double amount) throws InsufficientBalanceException {
        if (amount > balance) throw new InsufficientBalanceException(amount - balance);
        balance -= amount;
    }
}
```

Extend `Exception` for a checked exception or `RuntimeException` for an unchecked one. Spring applications usually use unchecked business exceptions and map them to HTTP responses (Module 28).

## Best practices
- Catch only what you can handle meaningfully; otherwise let it propagate.
- Never swallow exceptions with an empty `catch {}` - at minimum log them.
- Preserve the cause when wrapping: `throw new ServiceException("Import failed", e);`
- Do not use exceptions for normal control flow (for example, to end a loop).
- Do not show stack traces or secrets to end users; log details, show a friendly message.
- Release resources with try-with-resources.

## Common mistakes
- `catch (Exception e) {}` hiding real bugs.
- Catching a general exception before a specific one (compile error).
- Thinking `finally` is skipped when `return` appears in `try` - it still runs.
- Confusing `throw` (an action) with `throws` (a declaration).

## Practice exercise
1. Write a method `int parseAge(String text)` that throws `IllegalArgumentException` for non-numeric text or ages outside 0-120.
2. Create a checked `InvalidMarksException` and throw it from `double percentage(int obtained, int total)` when `total <= 0` or `obtained > total`.
3. Read numbers from `marks.txt` using try-with-resources; for each bad line, print the line number and continue.
4. Print a summary: lines read, valid lines, invalid lines.

## Key takeaways
- Checked exceptions must be caught or declared; unchecked exceptions signal programming errors.
- Order catch blocks from specific to general; keep `try` blocks small.
- `finally` always runs; try-with-resources is the modern way to close resources.
- `throw` raises an exception; `throws` declares one.
- Custom exceptions make business failures explicit.
