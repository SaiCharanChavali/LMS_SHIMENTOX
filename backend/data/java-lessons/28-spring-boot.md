## Introduction to Spring Boot
**Spring Boot** makes it fast to build production-ready Spring applications. It provides:
- **Starters** - curated dependency bundles (`spring-boot-starter-web`, `-data-jpa`, `-security`, `-validation`, `-test`).
- **Auto-configuration** - sensible beans configured automatically from what is on the classpath.
- **Embedded server** - Tomcat by default, so the app runs as a plain `java -jar`.
- **Externalised configuration**, profiles, logging, metrics and health checks (Actuator).

## Spring Initializr and project structure
Create a project at **start.spring.io** (or from IntelliJ): choose Gradle, Java 21, a current Spring Boot 3.x version, packaging Jar, and dependencies: Spring Web, Spring Data JPA, Validation, MySQL Driver, Spring Boot DevTools, Actuator.

```
training-api/
├── build.gradle
├── src/main/java/com/shimento/training/
│   ├── TrainingApiApplication.java      # entry point
│   ├── course/
│   │   ├── Course.java                  # entity
│   │   ├── CourseRepository.java
│   │   ├── CourseService.java
│   │   ├── CourseController.java
│   │   └── dto/                         # request/response records
│   └── common/                          # exception handlers, config
├── src/main/resources/
│   ├── application.properties (or application.yml)
│   ├── static/                          # static web files
│   └── templates/                       # server-side templates (Thymeleaf)
└── src/test/java/...
```

Organising **by feature** (`course/`, `enrollment/`) scales better than by layer (`controllers/`, `services/`).

```java
@SpringBootApplication     // = @Configuration + @EnableAutoConfiguration + @ComponentScan
public class TrainingApiApplication {
    public static void main(String[] args) {
        SpringApplication.run(TrainingApiApplication.class, args);
    }
}
```

Run with `./gradlew bootRun`; the server starts on port 8080.

## Configuration: application.properties and YAML
```properties
# application.properties
server.port=8080
spring.application.name=training-api
spring.datasource.url=jdbc:mysql://localhost:3306/training_db
spring.datasource.username=${DB_USER}
spring.datasource.password=${DB_PASSWORD}
spring.jpa.hibernate.ddl-auto=validate
app.page.max-size=50
```

The same in YAML:

```yaml
server:
  port: 8080
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/training_db
    username: ${DB_USER}
    password: ${DB_PASSWORD}
app:
  page:
    max-size: 50
```

Bind a group of properties to a typed class:

```java
@ConfigurationProperties(prefix = "app.page")
public record PageProperties(int maxSize) { }

@SpringBootApplication
@ConfigurationPropertiesScan
public class TrainingApiApplication { /* ... */ }
```

Property sources have an order of precedence: command-line arguments override environment variables, which override `application.properties` inside the JAR. So one artifact can be configured per environment without rebuilding. Keep secrets in environment variables or a secrets manager, never in Git.

## Auto-configuration
At startup, Spring Boot evaluates auto-configuration classes guarded by **conditions**: `@ConditionalOnClass` (a library is on the classpath), `@ConditionalOnMissingBean` (you have not defined your own), `@ConditionalOnProperty`. For example, with `spring-boot-starter-data-jpa` and a datasource URL present, Boot creates a `DataSource` (HikariCP), an `EntityManagerFactory` and a transaction manager. Defining your own bean of the same type makes Boot back off.

Debug what was configured with `--debug` (the conditions report) or the Actuator `/actuator/conditions` endpoint.

## REST APIs and annotations
```java
public record CourseRequest(
        @NotBlank @Size(max = 150) String title,
        @NotBlank @Pattern(regexp = "[A-Z0-9]{3,20}") String code,
        @NotNull @PositiveOrZero BigDecimal fee) { }

public record CourseResponse(Long id, String code, String title, BigDecimal fee) { }

@RestController
@RequestMapping("/api/courses")
public class CourseController {
    private final CourseService service;
    public CourseController(CourseService service) { this.service = service; }

    @GetMapping
    public List<CourseResponse> list(@RequestParam(required = false) String q) {
        return service.search(q);
    }

    @GetMapping("/{id}")
    public CourseResponse get(@PathVariable Long id) {
        return service.get(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CourseResponse create(@Valid @RequestBody CourseRequest request) {
        return service.create(request);
    }

    @PutMapping("/{id}")
    public CourseResponse update(@PathVariable Long id, @Valid @RequestBody CourseRequest request) {
        return service.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        service.delete(id);
    }
}
```

| Annotation | Purpose |
| --- | --- |
| `@RestController` | `@Controller` + `@ResponseBody`: return values become JSON |
| `@RequestMapping` | Base path (class) or general mapping |
| `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, `@DeleteMapping` | Map HTTP methods |
| `@PathVariable` | Value from the URL path `/courses/{id}` |
| `@RequestParam` | Query parameter `?q=java` |
| `@RequestBody` | Deserialise the JSON body |
| `@ResponseStatus` | Set the success status code |
| `ResponseEntity<T>` | Full control of status, headers and body |

REST conventions: nouns for resources (`/api/courses/42/enrollments`), HTTP methods for actions, correct status codes (200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 500 Internal Server Error). Use **DTOs** (records) for requests and responses instead of exposing entities.

## Validation
Add `spring-boot-starter-validation`. Annotate DTO fields with Jakarta Bean Validation constraints (`@NotNull`, `@NotBlank`, `@Size`, `@Min`, `@Max`, `@Email`, `@Pattern`, `@Positive`, `@Past`, `@Future`) and trigger validation with `@Valid`. Invalid input produces a `MethodArgumentNotValidException` - handled in the next section. Validation is the first gate; business rules (such as "code must be unique") belong in the service and are backed by database constraints.

## Exception handling
A **global exception handler** turns exceptions into consistent JSON error responses.

```java
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) { super(message); }
}

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail notFound(ResourceNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail invalid(MethodArgumentNotValidException ex) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Validation failed");
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(e -> errors.put(e.getField(), e.getDefaultMessage()));
        pd.setProperty("errors", errors);
        return pd;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail unexpected(Exception ex) {
        log.error("Unexpected error", ex);                               // details in logs
        return ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Something went wrong"); // generic to client
    }
}
```

`ProblemDetail` follows the RFC 9457 "problem details" JSON format. Never return stack traces or SQL errors to clients.

## Logging
Spring Boot uses **SLF4J** with **Logback** by default.

```java
private static final Logger log = LoggerFactory.getLogger(CourseService.class);

log.info("Created course {} with id {}", course.getCode(), course.getId());   // {} placeholders
log.debug("Search query: {}", q);
log.warn("Course {} has no trainer", id);
log.error("Payment failed for order {}", orderId, exception);
```

```properties
logging.level.root=INFO
logging.level.com.shimento=DEBUG
logging.level.org.hibernate.SQL=DEBUG
logging.file.name=logs/training-api.log
```

Levels: TRACE < DEBUG < INFO < WARN < ERROR. Never log passwords, tokens or full personal data.

## Profiles
**Profiles** separate environment-specific configuration.

```
application.properties          # shared defaults
application-dev.properties      # local MySQL, verbose logging
application-test.properties     # test database
application-prod.properties     # production settings (secrets via environment variables)
```

Activate with `spring.profiles.active=dev`, the environment variable `SPRING_PROFILES_ACTIVE=prod`, or `--spring.profiles.active=prod`. Beans can be limited to profiles with `@Profile("dev")`.

## Swagger / OpenAPI
Add `org.springdoc:springdoc-openapi-starter-webmvc-ui` to generate interactive API documentation from your controllers:
- JSON spec at `/v3/api-docs`
- Swagger UI at `/swagger-ui.html`

```java
@Operation(summary = "Get a course by id")
@ApiResponse(responseCode = "404", description = "Course not found")
@GetMapping("/{id}")
public CourseResponse get(@PathVariable Long id) { ... }
```

Frontend developers can explore and try endpoints without reading Java code. Restrict or disable Swagger UI in production if the API is private.

## Actuator
`spring-boot-starter-actuator` adds operational endpoints:

| Endpoint | Shows |
| --- | --- |
| `/actuator/health` | Up/down status, including database and disk |
| `/actuator/info` | Build and app info |
| `/actuator/metrics` | JVM, HTTP and pool metrics (Micrometer) |
| `/actuator/prometheus` | Metrics for Prometheus (with the registry dependency) |
| `/actuator/loggers` | View/change log levels at runtime |

```properties
management.endpoints.web.exposure.include=health,info,metrics
management.endpoint.health.probes.enabled=true      # liveness/readiness for Kubernetes
```

Expose only what you need and secure the rest - some endpoints reveal sensitive details.

## File upload and download
```java
@PostMapping(value = "/{id}/materials", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public String upload(@PathVariable Long id, @RequestParam("file") MultipartFile file) throws IOException {
    if (file.isEmpty()) throw new IllegalArgumentException("Empty file");
    if (!List.of("application/pdf", "image/png").contains(file.getContentType()))
        throw new IllegalArgumentException("Only PDF or PNG allowed");
    String safeName = UUID.randomUUID() + ".pdf";          // never trust the client file name
    Path target = uploadDir.resolve(safeName).normalize();
    Files.copy(file.getInputStream(), target);
    return safeName;
}

@GetMapping("/materials/{name}")
public ResponseEntity<Resource> download(@PathVariable String name) throws MalformedURLException {
    Path path = uploadDir.resolve(name).normalize();
    if (!path.startsWith(uploadDir)) return ResponseEntity.badRequest().build();   // block ../ traversal
    Resource resource = new UrlResource(path.toUri());
    return ResponseEntity.ok()
        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + name + "\"")
        .contentType(MediaType.APPLICATION_OCTET_STREAM)
        .body(resource);
}
```

Limit sizes with `spring.servlet.multipart.max-file-size=5MB`. In the cloud, store files in object storage (S3) instead of the server's disk.

## Scheduling and caching
### Scheduling
```java
@SpringBootApplication
@EnableScheduling
public class TrainingApiApplication { }

@Component
public class ReminderJob {
    @Scheduled(cron = "0 0 9 * * MON-FRI", zone = "Asia/Kolkata")   // 09:00 on weekdays
    public void sendReminders() { /* ... */ }

    @Scheduled(fixedDelay = 60_000)                                   // 1 minute after the previous run ends
    public void cleanup() { /* ... */ }
}
```

With several app instances, every instance runs the job - use a lock (ShedLock) or a single worker.

### Caching
```java
@EnableCaching    // on a configuration class

@Cacheable(value = "courses", key = "#id")
public CourseResponse get(Long id) { ... }        // computed once, then served from cache

@CacheEvict(value = "courses", key = "#id")
public CourseResponse update(Long id, CourseRequest r) { ... }
```

The default cache is an in-memory map; plug in Caffeine (local) or Redis (shared, Module 34) for production.

## Testing, packaging and deployment
Spring Boot testing is covered in Module 32 (`@SpringBootTest`, `@WebMvcTest`, `@DataJpaTest`).

Packaging:

```bash
./gradlew bootJar                       # build/libs/training-api-1.0.0.jar (fat jar with dependencies)
java -jar build/libs/training-api-1.0.0.jar --spring.profiles.active=prod
./gradlew bootBuildImage                # build an OCI/Docker image with buildpacks
```

Deploy the JAR to a VM (systemd service), a container platform (Docker/Kubernetes, Module 36) or a PaaS such as Azure App Service (Module 37), supplying configuration through environment variables.

## Common mistakes
- Returning JPA entities from controllers.
- Missing `@Valid`, so constraints never run.
- Catching exceptions in every controller instead of a global handler.
- Committing real credentials in `application.properties`.
- Exposing all Actuator endpoints publicly.
- Trusting uploaded file names and content types.

## Practice exercise
Build `training-api` with Spring Boot:
1. CRUD REST endpoints for courses with request/response DTOs and validation.
2. A `@RestControllerAdvice` returning `ProblemDetail` for 400, 404 and 500.
3. `dev` and `prod` profiles; secrets from environment variables.
4. Swagger UI documentation and Actuator health/info endpoints.
5. A PDF upload/download endpoint for course materials with size and type limits.
6. A scheduled job logging the number of courses daily, and `@Cacheable` on `get`.
7. Package with `bootJar` and run it with the `prod` profile.

## Key takeaways
- Spring Boot = starters + auto-configuration + embedded server + externalised config.
- Structure by feature; configure with properties/YAML and typed `@ConfigurationProperties`.
- Build REST APIs with DTOs, `@Valid` validation and a global exception handler.
- Use SLF4J logging, profiles, OpenAPI docs and Actuator for operations.
- Boot supports uploads, scheduling, caching and packaging as an executable JAR or image.
