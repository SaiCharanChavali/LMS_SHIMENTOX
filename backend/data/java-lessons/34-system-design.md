## How to approach system design
System design is planning how components fit together so an application meets its **functional requirements** (what it does) and **non-functional requirements**: scalability, availability, latency, consistency, security and cost. A practical approach:
1. Clarify requirements and estimate scale (users, requests per second, data size, read/write ratio).
2. Define APIs and the data model.
3. Draw a high-level design (clients, servers, databases, caches, queues).
4. Find bottlenecks and single points of failure; add scaling and redundancy where measurements justify it.
5. Discuss trade-offs explicitly.

Vocabulary: **latency** (time per request), **throughput** (requests per second), **availability** (uptime, e.g. 99.9% ≈ 8.8 hours of downtime per year), **vertical scaling** (bigger machine) vs **horizontal scaling** (more machines).

## Client-server architecture
In the **client-server** model, clients (browsers, mobile apps) send requests over a network to servers that process them and return responses.

```
Browser ──HTTP request──> DNS lookup ──> Server (Spring Boot) ──> Database
        <──HTTP response──────────────────
```

Steps of a web request: DNS resolves the domain to an IP, a TCP (and TLS for HTTPS) connection is opened, the HTTP request is sent, the server processes it and responds. Design servers to be **stateless** (no user session stored in server memory - keep it in a shared store or token), so any server instance can handle any request. Statelessness is what makes horizontal scaling easy.

## Load balancer
A **load balancer** distributes incoming traffic across multiple server instances.

```
                 ┌──> API instance 1
Clients ──> LB ──┼──> API instance 2
                 └──> API instance 3
```

- **Algorithms:** round robin, least connections, weighted, IP hash (sticky sessions).
- **Health checks** remove unhealthy instances automatically (Spring Boot Actuator `/actuator/health`).
- **Layer 4** (TCP) balancers are fast; **layer 7** (HTTP) balancers can route by path or header.
- Benefits: horizontal scaling, high availability, zero-downtime deployments.
- Examples: Nginx, HAProxy, AWS Application Load Balancer, Azure Load Balancer.
- The load balancer itself must be redundant to avoid a single point of failure.

## Proxies
A **forward proxy** sits in front of **clients** and makes requests on their behalf (corporate internet filters, anonymity). A **reverse proxy** sits in front of **servers** and receives requests on their behalf.

Reverse proxy duties: TLS termination, load balancing, caching static content, compression, rate limiting, hiding internal topology, routing `/api` to the backend and `/` to the frontend. Nginx is the most common reverse proxy (Module 36).

## Redis cache
A **cache** stores frequently read data in fast memory to reduce latency and database load. **Redis** is an in-memory key-value store used for caching, sessions, rate limiting, leaderboards and pub/sub.

**Cache-aside** (lazy loading) - the most common pattern:

```java
public CourseResponse get(Long id) {
    String key = "course:" + id;
    CourseResponse cached = redis.opsForValue().get(key);
    if (cached != null) return cached;                      // cache hit
    CourseResponse fresh = loadFromDatabase(id);            // cache miss
    redis.opsForValue().set(key, fresh, Duration.ofMinutes(10));   // TTL
    return fresh;
}
// On update: write the database, then delete the cache key (invalidate).
```

With Spring: `spring-boot-starter-data-redis` plus `@Cacheable`/`@CacheEvict` (Module 28).

Design questions for every cache: What is the **key**? What is the **TTL**? How is it **invalidated** on writes? How stale may data be? What is the **eviction policy** (LRU) when memory is full? Never cache user-specific or permission-dependent data under a shared key. Other strategies: write-through (write cache and DB together), write-behind (write cache, persist later).

## CDN
A **Content Delivery Network** caches static content (images, JS, CSS, videos) on edge servers around the world, close to users. Benefits: lower latency, less load on your servers, DDoS absorption. Examples: CloudFront, Azure Front Door, Cloudflare, Akamai.

Use long cache lifetimes with **fingerprinted file names** (`app.3f9a1c.js`, produced by Vite) so new deployments get new URLs. Private, user-specific API responses should not be cached publicly (`Cache-Control: private, no-store`).

## Message queue
A **message queue** lets services communicate **asynchronously**: a producer puts a message on the queue and continues; consumers process it later.

```
API ──"OrderPlaced"──> [ Queue ] ──> Email worker
                                  ──> Invoice worker
```

Benefits: decoupling, absorbing traffic spikes (buffering), retrying failed work, scaling consumers independently. Examples: RabbitMQ, Apache Kafka, AWS SQS, Azure Service Bus.

Design concerns:
- **Delivery guarantees** - most systems give *at-least-once* delivery, so a message can arrive twice. Consumers must be **idempotent** (processing twice has the same effect as once), e.g. by storing processed message IDs.
- **Dead-letter queue** - messages that keep failing go here for inspection.
- **Ordering** - only guaranteed within a queue/partition.

## Database scaling
Techniques, roughly in the order you should consider them:
1. **Optimise queries and add indexes** (Modules 10-11) - often the biggest win.
2. **Caching** to cut repeated reads.
3. **Vertical scaling** - more CPU/RAM.
4. **Read replicas** - the primary handles writes; replicas copy data and serve reads. Replication lag means reads may be slightly stale.
5. **Connection pooling** and limits so the database is not overwhelmed.
6. **Partitioning** - split a large table (e.g. by date) within one database.
7. **Sharding** - split data across multiple databases by a shard key (e.g. `customer_id % 4`). Greatly increases capacity but makes joins, transactions and re-sharding hard.
8. **Polyglot persistence** - use the right store for each need (SQL for orders, Redis for sessions, Elasticsearch for search).

## CAP theorem
In a distributed data store, when a **network partition (P)** occurs, the system must choose between:
- **Consistency (C)** - every read returns the most recent write (or an error).
- **Availability (A)** - every request receives a non-error response (possibly stale data).

Since partitions cannot be ruled out in real networks, the practical choice is **CP** (reject some requests to stay consistent - e.g. banking balances) or **AP** (stay available and reconcile later - e.g. social media likes, shopping cart). Many systems use **eventual consistency**: replicas converge over time. The PACELC extension adds: Else (no partition), trade **Latency** vs **Consistency**.

## Rate limiting
**Rate limiting** caps how many requests a client can make in a time window, protecting the system from abuse, brute-force login attempts and overload. Exceeded clients get **HTTP 429 Too Many Requests** with a `Retry-After` header.

Algorithms:
| Algorithm | Idea |
| --- | --- |
| Fixed window | Count requests per minute window; simple, bursty at edges |
| Sliding window | Smooths the window boundaries |
| Token bucket | Tokens refill at a steady rate; each request spends one; allows short bursts |
| Leaky bucket | Requests drain at a constant rate |

Implement at the API gateway or reverse proxy, or in the app with Bucket4j / Resilience4j RateLimiter, storing counters in Redis so all instances share them. Limit by user, API key or IP.

## API gateway
An **API gateway** is the single entry point for clients into a set of backend services (Module 35).

Responsibilities: request **routing** (`/api/courses/**` → course service), **authentication** (validate JWTs once), rate limiting, CORS, request/response transformation, aggregation of multiple calls, logging and metrics, TLS termination.

Examples: **Spring Cloud Gateway**, Kong, AWS API Gateway, Azure API Management. Keep business logic out of the gateway, and make it highly available - it is on every request's path.

## Putting it together
A scalable training portal:

```
Users ─> CDN (React static files)
      └> Load balancer ─> API gateway (auth, rate limit)
                            ├─> Course service ─┬─> Redis cache
                            │                   └─> MySQL primary ─> read replicas
                            └─> Enrollment service ─> Queue ─> Notification worker
```

## Common mistakes
- Adding microservices, caches and queues before measuring a bottleneck.
- Storing session state in server memory, preventing horizontal scaling.
- Caches without invalidation, or public caching of private data.
- Non-idempotent consumers processing duplicate messages twice.
- A single, non-redundant load balancer or database as a single point of failure.

## Practice exercise
Design a URL shortener or a course-catalogue platform for 1 million daily users (100:1 read/write):
1. Write functional and non-functional requirements and back-of-the-envelope estimates.
2. Define the REST API and data model.
3. Draw the architecture with load balancer, stateless API instances, cache, database replicas and CDN.
4. Specify cache keys, TTLs and invalidation; and a rate-limit policy for creation.
5. Add a queue for analytics events and describe idempotent consumption.
6. State your CAP choice for each data type and justify it.

## Key takeaways
- Start from requirements and measurements, not technologies.
- Stateless servers behind a load balancer scale horizontally; reverse proxies and gateways sit in front.
- Caches (Redis) and CDNs cut latency but need TTL and invalidation plans.
- Queues decouple work; consumers must be idempotent.
- Scale databases with indexes, caching, replicas and sharding; CAP forces a choice during partitions; rate limiting protects capacity.
