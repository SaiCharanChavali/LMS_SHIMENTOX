## Spring introduction
The **Spring Framework** is the most widely used framework for enterprise Java. Its core idea is that a **container** creates your objects and wires them together, so your classes stay small, testable and loosely coupled. On top of that core, Spring provides modules for web applications (MVC), data access, transactions, security, messaging and more. **Spring Boot** (Module 28) adds auto-configuration and an embedded server on top of the framework.

Main modules: Core Container (beans, context, SpEL), AOP, Data Access (JDBC, transactions, ORM), Web (Spring MVC, WebFlux) and Test.

## IoC container and dependency injection
### Inversion of Control (IoC)
Without Spring, a class creates its own dependencies:

```java
public class CourseService {
    private final CourseRepository repo = new MySqlCourseRepository();   // tightly coupled
}
```

The service is hard-wired to MySQL and hard to test. With **Inversion of Control**, the class receives its dependencies from outside; the Spring **IoC container** (`ApplicationContext`) creates the objects and supplies them. This is **Dependency Injection (DI)**.

```java
public interface CourseRepository { List<String> findAllTitles(); }

@Repository
public class InMemoryCourseRepository implements CourseRepository {
    public List<String> findAllTitles() { return List.of("Java", "Spring"); }
}

@Service
public class CourseService {
    private final CourseRepository repo;

    public CourseService(CourseRepository repo) {   // constructor injection
        this.repo = repo;
    }
    public int count() { return repo.findAllTitles().size(); }
}
```

### Types of injection
| Type | How | When |
| --- | --- | --- |
| **Constructor** | Dependencies are constructor parameters | **Preferred**: required dependencies, `final` fields, easy to test |
| Setter | `@Autowired` on a setter | Optional dependencies |
| Field | `@Autowired` on a field | Avoid: hidden dependencies, hard to test |

With a single constructor, `@Autowired` is optional. In a unit test you simply call `new CourseService(fakeRepo)` - no Spring needed.

When several beans implement the same interface, choose one with `@Primary` on a bean or `@Qualifier("beanName")` at the injection point.

## Beans
A **bean** is an object created and managed by the Spring container. There are two main ways to declare beans:

```java
// 1. Component scanning: annotate the class
@Component   // or the specialised @Service, @Repository, @Controller
public class EmailNotifier implements Notifier { /* ... */ }

// 2. Java configuration: a @Bean method, useful for third-party classes
@Configuration
public class AppConfig {
    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
```

Starting a container without Boot:

```java
@Configuration
@ComponentScan("com.shimento.lms")
public class AppConfig { }

try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
    CourseService service = ctx.getBean(CourseService.class);
    System.out.println(service.count());   // 2
}
```

## Bean lifecycle
The container manages each bean through these stages:
1. **Instantiate** - call the constructor.
2. **Populate** - inject dependencies.
3. **Aware callbacks** - for example `BeanNameAware`, `ApplicationContextAware` (rarely needed).
4. **BeanPostProcessor before-init** - framework hooks (this is where proxies for AOP/transactions are prepared).
5. **Initialise** - `@PostConstruct` method, `InitializingBean.afterPropertiesSet()`, or `@Bean(initMethod=...)`.
6. **BeanPostProcessor after-init** - the bean may be wrapped in a proxy.
7. **In use**.
8. **Destroy** on shutdown - `@PreDestroy`, `DisposableBean.destroy()` or `@Bean(destroyMethod=...)`.

```java
@Component
public class CacheWarmer {
    @PostConstruct
    void init() { System.out.println("Loading cache..."); }

    @PreDestroy
    void shutdown() { System.out.println("Releasing cache..."); }
}
```

## Bean scopes
| Scope | Instances | Use |
| --- | --- | --- |
| `singleton` (default) | One per container | Stateless services, repositories, controllers |
| `prototype` | New instance each time it is requested | Stateful helper objects |
| `request` | One per HTTP request | Request-specific data (web apps) |
| `session` | One per HTTP session | User session data |
| `application` | One per ServletContext | App-wide web data |

```java
@Component
@Scope("prototype")
public class ReportBuilder { /* holds per-report state */ }
```

Because singletons are shared by all requests and threads, **never store per-user mutable data in a singleton's fields**.

## Spring configuration and annotations
Configuration styles evolved from XML to annotations and Java config; modern projects use annotations plus `@Configuration` classes.

| Annotation | Purpose |
| --- | --- |
| `@Component` | Generic Spring-managed bean |
| `@Service` | Business-logic bean |
| `@Repository` | Data-access bean; translates persistence exceptions |
| `@Controller` / `@RestController` | Web controllers (MVC) |
| `@Configuration` | Class containing `@Bean` methods |
| `@Bean` | Method whose return value becomes a bean |
| `@Autowired` | Inject a dependency |
| `@Qualifier` / `@Primary` | Choose among several candidates |
| `@Value("${app.page-size:20}")` | Inject a property value (default 20) |
| `@ComponentScan` | Packages to scan for components |
| `@PropertySource` | Load a properties file |
| `@Profile("dev")` | Register a bean only for a profile |
| `@Lazy` | Create the bean on first use |

```java
@Service
public class PagingService {
    private final int pageSize;
    public PagingService(@Value("${app.page-size:20}") int pageSize) {
        this.pageSize = pageSize;
    }
}
```

## Spring Expression Language (SpEL)
**SpEL** evaluates expressions at runtime inside `#{ ... }`. It can reference beans, call methods, do arithmetic and conditionals.

```java
@Value("#{2 * 60 * 60}")                         // arithmetic
private int sessionSeconds;                      // 7200

@Value("#{systemProperties['user.timezone']}")
private String timezone;

@Value("#{courseService.count() > 0 ? 'open' : 'empty'}")
private String catalogueStatus;

@Value("#{'${app.admins}'.split(',')}")          // combine property placeholder and SpEL
private List<String> admins;
```

`${...}` is a **property placeholder**; `#{...}` is a **SpEL expression**. SpEL is also used in Spring Security (`@PreAuthorize("hasRole('ADMIN')")`) and caching annotations.

## Spring events
Spring's **event mechanism** lets beans communicate without direct dependencies (Observer pattern).

```java
public record EnrollmentCreated(long employeeId, long courseId) { }

@Service
public class EnrollmentService {
    private final ApplicationEventPublisher events;
    public EnrollmentService(ApplicationEventPublisher events) { this.events = events; }

    public void enroll(long employeeId, long courseId) {
        // ... save enrollment ...
        events.publishEvent(new EnrollmentCreated(employeeId, courseId));
    }
}

@Component
public class WelcomeEmailListener {
    @EventListener
    public void on(EnrollmentCreated event) {
        System.out.println("Send welcome email for course " + event.courseId());
    }
}
```

Listeners run synchronously in the same thread by default; add `@Async` (with `@EnableAsync`) for background handling, or `@TransactionalEventListener` to run only after the transaction commits. Built-in events include `ContextRefreshedEvent` and `ApplicationReadyEvent`.

## Spring MVC
**Spring MVC** is the web framework built on the Servlet API using the **Model-View-Controller** pattern.

Request flow:
1. The **DispatcherServlet** (front controller) receives every HTTP request.
2. **HandlerMapping** finds the controller method matching the URL and HTTP method.
3. The controller runs, calling services, and returns data or a view name with a model.
4. A **ViewResolver** renders a template (Thymeleaf, JSP) - or, for `@RestController`, an **HttpMessageConverter** writes JSON.
5. The response is sent back.

```java
@Controller
public class CoursePageController {
    private final CourseService service;
    public CoursePageController(CourseService service) { this.service = service; }

    @GetMapping("/courses")
    public String list(Model model) {
        model.addAttribute("count", service.count());
        return "courses";              // resolved to templates/courses.html
    }
}

@RestController
@RequestMapping("/api/courses")
public class CourseApiController {
    @GetMapping("/{id}")
    public CourseDto get(@PathVariable long id, @RequestParam(defaultValue = "false") boolean details) {
        return new CourseDto(id, "Java Basics");      // serialised to JSON
    }
}
```

## Spring AOP
**Aspect-Oriented Programming** separates **cross-cutting concerns** - logging, timing, security, transactions - from business code.

| Term | Meaning |
| --- | --- |
| Aspect | A class containing cross-cutting logic (`@Aspect`) |
| Join point | A point in execution - in Spring, a method call |
| Advice | The action: `@Before`, `@After`, `@AfterReturning`, `@AfterThrowing`, `@Around` |
| Pointcut | An expression selecting join points |
| Weaving | Applying aspects; Spring does it at runtime with **proxies** |

```java
@Aspect
@Component
public class TimingAspect {
    @Around("execution(* com.shimento.lms.service..*(..))")
    public Object time(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.nanoTime();
        try {
            return pjp.proceed();                       // call the real method
        } finally {
            long ms = (System.nanoTime() - start) / 1_000_000;
            System.out.println(pjp.getSignature().toShortString() + " took " + ms + " ms");
        }
    }
}
```

`@Transactional` and `@PreAuthorize` are implemented with AOP proxies. Because proxies wrap the bean, **a method calling another method on `this` bypasses the proxy** - the inner call is not advised (a common surprise with `@Transactional`).

## Common mistakes
- Using `new` for beans, so Spring cannot inject or proxy them.
- Field injection everywhere, making dependencies hidden and tests awkward.
- Storing request or user data in singleton fields.
- Two beans of the same type without `@Primary`/`@Qualifier` (startup error).
- Expecting AOP advice on self-invocation.

## Practice exercise
Without Spring Boot (plain Spring context):
1. Create `Notifier` with `EmailNotifier` and `SmsNotifier` implementations; inject one into `EnrollmentService` with `@Qualifier`.
2. Add a `@Configuration` class with a `@Bean` for `java.time.Clock`.
3. Add `@PostConstruct` and `@PreDestroy` logs and observe the lifecycle on context close.
4. Create a prototype-scoped bean and prove two lookups return different instances.
5. Publish an `EnrollmentCreated` event and handle it in a listener.
6. Write a timing aspect for all service methods.

## Key takeaways
- The IoC container creates and wires beans; prefer constructor injection.
- Declare beans with stereotypes (`@Service`, `@Repository`) or `@Bean` methods.
- Beans follow a lifecycle with init/destroy hooks; singleton is the default scope.
- SpEL evaluates expressions; Spring events decouple publishers from listeners.
- Spring MVC routes requests through the DispatcherServlet; AOP adds cross-cutting behaviour through proxies.
