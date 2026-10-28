## What design patterns are
A **design pattern** is a proven, reusable solution to a common design problem, with a shared name that makes team discussions faster ("let's use a Strategy here"). The classic catalogue (the "Gang of Four" book) groups patterns into:

| Category | Concern | Patterns in this module |
| --- | --- | --- |
| Creational | How objects are created | Singleton, Factory, Builder, Prototype |
| Structural | How objects are composed | Adapter, Decorator, Facade |
| Behavioural | How objects interact | Strategy, Observer |
| Architectural | How an application is layered | MVC |

Use a pattern when it solves a real problem you have; unnecessary patterns add complexity. Spring already implements many of them for you.

## Singleton
**Intent:** ensure a class has exactly one instance and provide global access to it.

```java
public final class AppConfig {
    private AppConfig() { }                                 // no outside construction

    private static class Holder {                          // loaded lazily, thread-safe by the JVM
        private static final AppConfig INSTANCE = new AppConfig();
    }
    public static AppConfig getInstance() { return Holder.INSTANCE; }
}

// Simplest thread-safe singleton:
public enum IdGenerator {
    INSTANCE;
    private final AtomicLong next = new AtomicLong();
    public long nextId() { return next.incrementAndGet(); }
}
```

In Spring, beans are singletons by default, so you rarely hand-write this pattern. Cautions: singletons are global state, hard to mock in tests, and any mutable state inside must be thread-safe.

## Factory
**Intent:** centralise object creation so callers depend on an interface, not on concrete classes.

```java
public interface Notifier { void send(String to, String msg); }
class EmailNotifier implements Notifier { public void send(String to, String msg) { /* ... */ } }
class SmsNotifier implements Notifier { public void send(String to, String msg) { /* ... */ } }
class SlackNotifier implements Notifier { public void send(String to, String msg) { /* ... */ } }

public class NotifierFactory {
    public static Notifier create(String channel) {
        return switch (channel.toLowerCase()) {
            case "email" -> new EmailNotifier();
            case "sms" -> new SmsNotifier();
            case "slack" -> new SlackNotifier();
            default -> throw new IllegalArgumentException("Unknown channel: " + channel);
        };
    }
}

Notifier n = NotifierFactory.create("sms");
n.send("+91...", "Your course starts tomorrow");
```

Variants: **Factory Method** (subclasses decide which object to create) and **Abstract Factory** (create families of related objects). Examples in the JDK: `List.of`, `Calendar.getInstance()`, `DriverManager.getConnection`. Spring's `BeanFactory` is the ultimate factory.

## Builder
**Intent:** construct complex objects step by step with readable code, avoiding constructors with many parameters ("telescoping constructors").

```java
public final class Course {
    private final String title;          // required
    private final String code;           // required
    private final String level;          // optional
    private final int durationHours;     // optional
    private final List<String> tags;     // optional

    private Course(Builder b) {
        this.title = b.title; this.code = b.code; this.level = b.level;
        this.durationHours = b.durationHours; this.tags = List.copyOf(b.tags);
    }

    public static Builder builder(String title, String code) { return new Builder(title, code); }

    public static final class Builder {
        private final String title, code;
        private String level = "BEGINNER";
        private int durationHours;
        private final List<String> tags = new ArrayList<>();

        private Builder(String title, String code) { this.title = title; this.code = code; }
        public Builder level(String level) { this.level = level; return this; }
        public Builder durationHours(int h) { this.durationHours = h; return this; }
        public Builder tag(String tag) { this.tags.add(tag); return this; }
        public Course build() {
            if (durationHours < 0) throw new IllegalStateException("Duration must be >= 0");
            return new Course(this);
        }
    }
}

Course c = Course.builder("Spring Boot", "SPR201").level("INTERMEDIATE").durationHours(30).tag("java").build();
```

Examples: `StringBuilder`, `HttpRequest.newBuilder()`, `UriComponentsBuilder`, and Lombok's `@Builder` annotation which generates this code.

## Prototype
**Intent:** create new objects by **copying** an existing, configured instance instead of building from scratch - useful when creation is expensive or you need many similar objects.

```java
public class ReportTemplate {
    private String title;
    private List<String> sections;

    public ReportTemplate(String title, List<String> sections) {
        this.title = title;
        this.sections = new ArrayList<>(sections);
    }

    public ReportTemplate copy() {                          // copy constructor style
        return new ReportTemplate(this.title, this.sections); // deep copy of the list
    }
    public void setTitle(String t) { this.title = t; }
}

ReportTemplate base = new ReportTemplate("Monthly report", List.of("Summary", "Enrollments", "Scores"));
ReportTemplate march = base.copy();
march.setTitle("March report");     // base is unchanged
```

Prefer copy constructors or copy methods over `Cloneable`/`clone()`, which is error-prone. Watch **shallow vs deep copy**: a shallow copy shares mutable fields. Spring's `prototype` scope gives a new bean instance per request for a different reason (stateful beans).

## Strategy
**Intent:** define a family of interchangeable algorithms behind one interface and choose one at runtime - removing large `if/else` or `switch` blocks.

```java
public interface DiscountStrategy { BigDecimal apply(BigDecimal price); }

public class NoDiscount implements DiscountStrategy {
    public BigDecimal apply(BigDecimal p) { return p; }
}
public class PercentageDiscount implements DiscountStrategy {
    private final BigDecimal percent;
    public PercentageDiscount(int percent) { this.percent = BigDecimal.valueOf(percent); }
    public BigDecimal apply(BigDecimal p) {
        return p.subtract(p.multiply(percent).divide(BigDecimal.valueOf(100)));
    }
}

public class Checkout {
    private final DiscountStrategy discount;
    public Checkout(DiscountStrategy discount) { this.discount = discount; }
    public BigDecimal total(BigDecimal price) { return discount.apply(price); }
}

new Checkout(new PercentageDiscount(20)).total(new BigDecimal("1000"));   // 800
```

Because `DiscountStrategy` has one method, lambdas work too: `new Checkout(p -> p.subtract(new BigDecimal("100")))`. In Spring, inject all strategies as a `Map<String, DiscountStrategy>` and pick by key. `Comparator` is a strategy in the JDK.

## Observer
**Intent:** when one object (the subject) changes, all registered observers are notified automatically - publishers and subscribers stay decoupled.

```java
public interface EnrollmentListener { void onEnrolled(String employee, String course); }

public class EnrollmentService {
    private final List<EnrollmentListener> listeners = new CopyOnWriteArrayList<>();
    public void subscribe(EnrollmentListener l) { listeners.add(l); }

    public void enroll(String employee, String course) {
        // ... save enrollment ...
        listeners.forEach(l -> l.onEnrolled(employee, course));
    }
}

EnrollmentService service = new EnrollmentService();
service.subscribe((e, c) -> System.out.println("Email " + e + " about " + c));
service.subscribe((e, c) -> System.out.println("Update dashboard for " + c));
service.enroll("Asha", "Java Basics");
```

In Spring use `ApplicationEventPublisher` and `@EventListener` (Module 26). At system scale, message brokers like Kafka implement the same idea (Module 35). Define what happens when an observer fails or is slow.

## Adapter
**Intent:** convert the interface of an existing class into the interface clients expect - like a travel plug adapter.

```java
// Interface our application uses
public interface PaymentGateway { PaymentResult charge(String customerId, BigDecimal amount); }

// Third-party SDK with a different API (we cannot change it)
public class LegacyPayClient {
    public int makePayment(String accountRef, long amountInPaise) { /* returns status code */ return 0; }
}

// Adapter
public class LegacyPayAdapter implements PaymentGateway {
    private final LegacyPayClient client;
    public LegacyPayAdapter(LegacyPayClient client) { this.client = client; }

    public PaymentResult charge(String customerId, BigDecimal amount) {
        long paise = amount.movePointRight(2).longValueExact();
        int status = client.makePayment(customerId, paise);
        return status == 0 ? PaymentResult.success() : PaymentResult.failed("Code " + status);
    }
}
```

The rest of the application depends only on `PaymentGateway`; switching providers means writing a new adapter. JDK example: `Arrays.asList`, `InputStreamReader` (bytes → characters).

## Decorator
**Intent:** add responsibilities to an object dynamically by wrapping it in another object with the same interface - an alternative to subclassing for every combination.

```java
public interface Notifier { void send(String to, String msg); }

public class EmailNotifier implements Notifier {
    public void send(String to, String msg) { System.out.println("Email to " + to + ": " + msg); }
}

public abstract class NotifierDecorator implements Notifier {
    protected final Notifier inner;
    protected NotifierDecorator(Notifier inner) { this.inner = inner; }
}

public class LoggingNotifier extends NotifierDecorator {
    public LoggingNotifier(Notifier inner) { super(inner); }
    public void send(String to, String msg) {
        System.out.println("LOG: sending to " + to);
        inner.send(to, msg);
    }
}

public class RetryingNotifier extends NotifierDecorator {
    public RetryingNotifier(Notifier inner) { super(inner); }
    public void send(String to, String msg) {
        for (int attempt = 1; ; attempt++) {
            try { inner.send(to, msg); return; }
            catch (RuntimeException e) { if (attempt == 3) throw e; }
        }
    }
}

Notifier n = new LoggingNotifier(new RetryingNotifier(new EmailNotifier()));   // stack behaviours
```

JDK example: `new BufferedReader(new InputStreamReader(new FileInputStream(f)))`. Spring AOP proxies achieve a similar effect.

## Facade
**Intent:** provide a simple, unified interface to a complex subsystem.

```java
public class EnrollmentFacade {
    private final CourseService courses;
    private final PaymentGateway payments;
    private final EnrollmentRepository enrollments;
    private final Notifier notifier;

    // constructor injection ...

    @Transactional
    public EnrollmentResult enroll(Long employeeId, Long courseId) {
        Course course = courses.getOpenCourse(courseId);
        PaymentResult paid = payments.charge(employeeId.toString(), course.getFee());
        if (!paid.ok()) return EnrollmentResult.paymentFailed(paid.reason());
        Enrollment e = enrollments.save(new Enrollment(employeeId, courseId));
        notifier.send(employeeId.toString(), "Enrolled in " + course.getTitle());
        return EnrollmentResult.success(e.getId());
    }
}
```

The controller calls one method instead of orchestrating four services. Spring's `JdbcTemplate` and `RestClient` are facades over complex APIs. Avoid letting a facade become a "god class" with all logic.

## MVC pattern
**Model-View-Controller** separates an application into three roles:
- **Model** - data and business logic (entities, services).
- **View** - presentation (HTML template, or React consuming JSON).
- **Controller** - handles input, calls the model and selects the view/response.

```
User → Controller → Model (service/repository) → Controller → View → User
```

In Spring MVC, `@Controller` methods return a view name and fill a `Model`; `@RestController` returns data that a React "view" renders. A typical backend layering - **Controller → Service → Repository** - extends MVC so each layer has one responsibility and can be tested separately.

## Common mistakes
- Using patterns for their own sake (an interface and factory for something that never varies).
- Singletons holding mutable state without thread safety.
- Shallow copies in Prototype sharing mutable lists.
- Facades that grow into god classes.
- Observers with no error handling - one failing listener breaks the publisher.

## Practice exercise
In the training domain:
1. Replace an `if/else` fee calculation with a **Strategy** (regular, early-bird, corporate), selectable at runtime.
2. Create a `NotifierFactory` (**Factory**) and wrap notifiers with logging and retry **Decorators**.
3. Use a **Builder** for a `Course` with five optional fields and validation in `build()`.
4. Write an **Adapter** for a fake third-party SMS SDK.
5. Implement an **Observer** for enrollment events with two listeners.
6. Expose enrollment through a **Facade** used by a controller (MVC).
7. Write one paragraph explaining where a plain method would have been better than a pattern.

## Key takeaways
- Creational: Singleton (one instance), Factory (centralised creation), Builder (step-by-step), Prototype (copying).
- Structural: Adapter (convert interfaces), Decorator (wrap to add behaviour), Facade (simplify a subsystem).
- Behavioural: Strategy (swap algorithms), Observer (notify subscribers).
- MVC separates model, view and controller; Spring builds on it.
- Apply patterns to real problems; prefer the simplest design that stays testable.
