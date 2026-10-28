## Introduction to microservices
A **microservices architecture** structures an application as a set of small, independently deployable services, each owning one business capability and its own data, communicating over the network (HTTP or messaging).

Characteristics:
- Organised around **business capabilities** (Courses, Enrollments, Payments, Notifications).
- **Database per service** - no other service reads its tables directly.
- **Independent deployment and scaling.**
- **Decentralised** technology choices and team ownership.
- Designed for **failure**: any remote call can be slow or fail.

## Monolithic vs microservices
| | Monolith | Microservices |
| --- | --- | --- |
| Deployment | One unit | Many independent units |
| Development | Simple to start, one codebase | Teams work independently |
| Scaling | Scale everything together | Scale hot services only |
| Data | One shared database, local transactions | Data per service, distributed consistency |
| Failures | A bug can take down everything | Failures can be isolated - if designed for |
| Operations | One app to monitor | Service discovery, tracing, many pipelines |
| Testing | Easier end-to-end | Contract and integration testing needed |

Microservices trade code complexity for **operational and distributed-systems complexity**. A well-structured **modular monolith** (clear module boundaries in one deployable) is often the right start; split a module out when there is a concrete reason - independent scaling, team autonomy or release cadence. Define service boundaries using domain-driven design (**bounded contexts**).

## Service discovery and Eureka
Service instances start, stop and move, so their addresses change. **Service discovery** lets services find each other by name.
- Each instance **registers** itself with a registry on startup and sends heartbeats.
- Clients **look up** healthy instances by service name and load-balance across them.

**Eureka** (Netflix OSS, part of Spring Cloud) is a popular registry.

### Eureka Server
```groovy
implementation 'org.springframework.cloud:spring-cloud-starter-netflix-eureka-server'
```

```java
@SpringBootApplication
@EnableEurekaServer
public class DiscoveryServerApplication {
    public static void main(String[] args) { SpringApplication.run(DiscoveryServerApplication.class, args); }
}
```

```properties
server.port=8761
eureka.client.register-with-eureka=false
eureka.client.fetch-registry=false
```

The dashboard at `http://localhost:8761` lists registered instances.

### Eureka Client
```groovy
implementation 'org.springframework.cloud:spring-cloud-starter-netflix-eureka-client'
```

```properties
spring.application.name=course-service
eureka.client.service-url.defaultZone=http://localhost:8761/eureka
```

The service registers as `COURSE-SERVICE`. Other services call `http://course-service/...` through a load-balanced client. On Kubernetes, built-in DNS-based service discovery often replaces Eureka.

## API gateway
The gateway is the single entry point (Module 34). With **Spring Cloud Gateway**:

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: courses
          uri: lb://course-service           # lb:// = resolve via discovery and load-balance
          predicates:
            - Path=/api/courses/**
        - id: enrollments
          uri: lb://enrollment-service
          predicates:
            - Path=/api/enrollments/**
          filters:
            - name: RequestRateLimiter
```

Typical gateway concerns: routing, JWT validation, rate limiting, CORS, request IDs for tracing.

## OpenFeign
**OpenFeign** is a declarative HTTP client: write an interface and Spring generates the implementation.

```groovy
implementation 'org.springframework.cloud:spring-cloud-starter-openfeign'
```

```java
@SpringBootApplication
@EnableFeignClients
public class EnrollmentServiceApplication { }

@FeignClient(name = "course-service")                     // resolved through discovery
public interface CourseClient {
    @GetMapping("/api/courses/{id}")
    CourseDto getCourse(@PathVariable Long id);
}

@Service
public class EnrollmentService {
    private final CourseClient courses;
    public EnrollmentService(CourseClient courses) { this.courses = courses; }

    public void enroll(Long employeeId, Long courseId) {
        CourseDto course = courses.getCourse(courseId);   // remote HTTP call
        // ...
    }
}
```

Always configure **timeouts** (`spring.cloud.openfeign.client.config.default.connect-timeout`/`read-timeout`). Spring's newer `RestClient` with HTTP interface clients (`@HttpExchange`) is an alternative.

## Resilience4j and the circuit breaker
Remote calls fail. Without protection, a slow dependency ties up threads and failures **cascade** across services. **Resilience4j** provides fault-tolerance patterns:

| Pattern | Purpose |
| --- | --- |
| **Timeout** (TimeLimiter) | Do not wait forever |
| **Retry** | Retry transient failures with backoff (only for idempotent operations) |
| **Circuit breaker** | Stop calling a failing service for a while |
| **Bulkhead** | Limit concurrent calls so one dependency cannot use all threads |
| **Rate limiter** | Cap call rate |
| **Fallback** | Return a default or cached response |

### Circuit breaker states
```
CLOSED ──(failure rate above threshold)──> OPEN ──(wait duration)──> HALF_OPEN
   ^                                                                  │
   └───────────(trial calls succeed)──────────────────────────────────┘
                (trial calls fail → back to OPEN)
```

- **Closed** - calls pass through; failures are counted.
- **Open** - calls fail immediately (fast failure) without hitting the dependency.
- **Half-open** - a few trial calls test whether the dependency recovered.

```java
@CircuitBreaker(name = "courseService", fallbackMethod = "courseFallback")
@Retry(name = "courseService")
public CourseDto getCourse(Long id) {
    return courseClient.getCourse(id);
}

private CourseDto courseFallback(Long id, Throwable ex) {
    return new CourseDto(id, "Course details temporarily unavailable", null);
}
```

```yaml
resilience4j:
  circuitbreaker:
    instances:
      courseService:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 30s
  retry:
    instances:
      courseService:
        max-attempts: 3
        wait-duration: 500ms
```

## Kafka and RabbitMQ
Asynchronous **event-driven** communication reduces coupling: the enrollment service publishes `EnrollmentCreated`; notification and analytics services react without the publisher knowing them.

| | Apache Kafka | RabbitMQ |
| --- | --- | --- |
| Model | Distributed, append-only **log** of events in topics/partitions | Message **broker** with exchanges and queues |
| Retention | Messages kept for a configured time; consumers can replay | Messages removed once acknowledged |
| Strengths | Very high throughput, event streaming, replay, ordering per partition | Flexible routing, task queues, simpler setup |
| Consumers | Consumer groups track their own offsets | Competing consumers on a queue |

Spring Kafka:

```java
// Producer
@Service
public class EnrollmentEvents {
    private final KafkaTemplate<String, EnrollmentCreated> kafka;
    public EnrollmentEvents(KafkaTemplate<String, EnrollmentCreated> kafka) { this.kafka = kafka; }
    public void publish(EnrollmentCreated e) {
        kafka.send("enrollments", e.enrollmentId().toString(), e);     // key keeps per-enrollment order
    }
}

// Consumer
@Component
public class NotificationListener {
    @KafkaListener(topics = "enrollments", groupId = "notification-service")
    public void on(EnrollmentCreated e) {
        if (alreadyProcessed(e.eventId())) return;    // idempotent consumer
        sendWelcomeEmail(e);
        markProcessed(e.eventId());
    }
}
```

Spring AMQP for RabbitMQ: `RabbitTemplate.convertAndSend(exchange, routingKey, message)` and `@RabbitListener(queues = "...")`.

**Consistency across services:** there is no distributed `@Transactional`. Use the **Saga** pattern (a sequence of local transactions with compensating actions, e.g. refund if seat reservation fails) and the **Transactional Outbox** pattern (save the business change and the event in the same local transaction; a relay publishes it) so data and events cannot diverge.

## Distributed tracing
One user request may pass through the gateway and five services. **Distributed tracing** follows it end to end:
- A **trace** = the whole request journey, identified by a **trace ID**.
- A **span** = one operation within it (an HTTP call, a DB query), with timing.
- IDs are propagated in headers (W3C `traceparent`) and added to every log line.

In Spring Boot 3, use **Micrometer Tracing** with an OpenTelemetry or Brave bridge and export to **Zipkin**, Jaeger or Grafana Tempo:

```groovy
implementation 'io.micrometer:micrometer-tracing-bridge-otel'
implementation 'io.opentelemetry:opentelemetry-exporter-zipkin'
```

```properties
management.tracing.sampling.probability=1.0     # 100% in dev; lower in production
logging.pattern.level=%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]
```

Combine traces with **centralised logs** (ELK/Loki) and **metrics** (Prometheus + Grafana) - the three pillars of observability.

## Common mistakes
- Splitting into microservices too early or along technical layers instead of business capabilities.
- Services sharing one database ("distributed monolith").
- Remote calls without timeouts, retries of non-idempotent operations.
- Expecting a local rollback to undo another service's completed work.
- No correlation/trace IDs, making failures impossible to follow.

## Practice exercise
Split the training platform into services:
1. Eureka server, `course-service` and `enrollment-service` (each with its own database), and a Spring Cloud Gateway.
2. `enrollment-service` calls `course-service` with OpenFeign; add timeouts, retry and a circuit breaker with a fallback. Stop `course-service` and observe the breaker open.
3. Publish `EnrollmentCreated` to Kafka (or RabbitMQ) and consume it in a `notification-service` idempotently.
4. Add Micrometer Tracing with Zipkin and follow one request across all services.
5. Write a paragraph comparing this design with a modular monolith for a team of four developers.

## Key takeaways
- Microservices are independently deployable services that own their data; they add operational complexity - start modular.
- Eureka provides service discovery; a gateway is the single entry point; OpenFeign simplifies HTTP calls.
- Resilience4j adds timeouts, retries and circuit breakers to stop cascading failures.
- Kafka and RabbitMQ enable event-driven communication; use idempotent consumers, sagas and outbox for consistency.
- Distributed tracing with trace IDs makes cross-service requests observable.
