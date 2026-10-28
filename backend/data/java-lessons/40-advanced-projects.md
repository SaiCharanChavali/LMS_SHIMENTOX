## What makes a project advanced
Advanced projects demonstrate **architecture and operations** skills: multi-tenant SaaS design, microservices with event-driven communication, AI retrieval pipelines, real-time systems at scale, resilience, observability and automated cloud deployment. Choose one as your **capstone** and present it like a professional release: architecture diagram, decision records, tests, runbook and a live demo.

Capstone deliverables:
- Architecture diagram and short **Architecture Decision Records** (ADRs: context, decision, consequences).
- API and event contracts (OpenAPI, event schemas with versioning).
- Automated tests: unit, integration (Testcontainers), contract, and E2E for critical journeys.
- Docker Compose for local development; CI/CD to a cloud environment.
- Observability: logs with trace IDs, metrics dashboards, alerts.
- A runbook: deployment, rollback, backup/restore and incident steps.

## Project 1: AI Customer Support Platform
**Goal:** a helpdesk where AI assists agents and customers.

Features:
- Ticketing: customers open tickets via a web widget or email; agents work in queues with SLAs.
- AI suggests replies and categorises/prioritises tickets; an AI chatbot answers common questions from the knowledge base and **hands off to a human** when unsure.
- Agent dashboard with real-time updates; customer satisfaction ratings; SLA breach alerts.

Architecture highlights: ticket service, knowledge-base service, AI gateway service (central place for prompts, keys, rate limits, logging), notification service; events such as `TicketCreated` and `TicketEscalated` on Kafka.

Key lessons: human-in-the-loop design, audit trail of AI suggestions, PII redaction before sending data to AI providers, per-tenant usage limits.

## Project 2: AI-Powered Learning Management System
**Goal:** an LMS - like the one you are using - with AI features.

Features:
- Courses → modules → lessons; enrollments; quizzes and timed assessments; certificates on completion.
- Roles: LEARNER, TRAINER, ADMIN; organisation/department reports.
- AI tutor that answers questions grounded in course content; AI-generated practice questions reviewed by trainers before publishing.
- Progress analytics, reminders and leaderboards.

Design challenges:
- **Assessment integrity:** answers are graded on the server; correct answers never reach the browser; attempts are time-limited and recorded per attempt.
- **Certificates:** issued only when every requirement is met, with a unique, verifiable ID.
- **Content versioning:** updating a course must not erase learners' history.

## Project 3: Microservices E-Commerce Platform
**Goal:** evolve the intermediate e-commerce project into microservices.

Services (each with its own database):

```
API Gateway (Spring Cloud Gateway, JWT validation, rate limits)
├── catalog-service   (products, search - MySQL + Elasticsearch/Redis cache)
├── cart-service      (Redis)
├── order-service     (MySQL)
├── inventory-service (MySQL)
├── payment-service   (simulated provider)
└── notification-service
Eureka / Kubernetes DNS for discovery · Kafka for events · Zipkin for tracing
```

**Order saga** (choreography with events):

```
OrderCreated → inventory reserves stock → StockReserved → payment charges → PaymentSucceeded → order CONFIRMED
                                       ↘ StockUnavailable → order CANCELLED
                                                       PaymentFailed → inventory releases stock → order CANCELLED
```

Key lessons: no distributed transactions - use sagas with compensating actions; transactional outbox for reliable event publishing; idempotent consumers; Resilience4j around synchronous calls; contract tests between services.

## Project 4: Real-Time Notification System
**Goal:** a reusable platform that delivers notifications across channels.

Features:
- Producers publish notification requests (API or Kafka topic) with templates and user preferences.
- Channels: in-app (WebSocket/SSE), email, SMS, push - each as a pluggable **strategy/adapter**.
- User preferences (opt-out per channel), quiet hours, rate limits, batching/digests.
- Delivery status tracking, retries with exponential backoff and a dead-letter queue.

Key lessons: at-least-once delivery with deduplication keys, back-pressure under load, horizontal scaling of WebSocket servers with a shared broker (Redis pub/sub), and metrics on delivery latency and failure rate.

## Project 5: SaaS Project Management Platform
**Goal:** a multi-tenant tool like a simplified Jira/Trello.

Features:
- Organisations (tenants), workspaces, projects, boards, tasks, comments, attachments, activity feed.
- Roles per organisation (OWNER, ADMIN, MEMBER, GUEST) and per project.
- Real-time board updates; mentions and notifications; subscription plans with limits (seats, projects).
- Audit logs and data export.

Multi-tenancy strategies:

| Strategy | Isolation | Cost/complexity |
| --- | --- | --- |
| Shared tables with `tenant_id` column | Logical; every query must filter by tenant | Cheapest, most common |
| Schema per tenant | Stronger | Moderate; migrations per schema |
| Database per tenant | Strongest | Highest operational cost |

Key lessons: tenant ID derived from the authenticated user and applied to **every** query (Hibernate filters or a repository base class), tests proving tenant A can never see tenant B's data, plan limits enforced on the server.

## Project 6: Document Q&A / Enterprise Knowledge Assistant
**Goal:** employees ask questions in natural language and get answers grounded in company documents, with citations.

**Retrieval-Augmented Generation (RAG)** pipeline:

```
Ingestion:  upload PDF/DOCX → extract text → split into chunks → create embeddings → store in a vector database
Query:      question → embed → similarity search (top-k chunks the user is allowed to see) → prompt LLM with chunks → answer + citations
```

Implementation options: Spring AI or LangChain4j for embeddings and chat models; a vector store such as PostgreSQL with pgvector, Elasticsearch or a dedicated vector DB.

Key lessons: **permission-aware retrieval** (filter chunks by the user's access before they reach the model), citations to source documents, re-indexing when documents change, evaluation of answer quality with a test question set, and guarding against prompt injection hidden in documents.

## Project 7: Event-Driven Order Processing System
**Goal:** a high-throughput backend that processes orders through asynchronous stages.

Stages as independent consumers: validation → fraud check → inventory → payment → fulfilment → shipping notification, connected by Kafka topics.

Requirements to demonstrate:
- **Exactly-once effects** through idempotent consumers and stable event IDs (Kafka delivers at least once).
- **Ordering** per order via the partition key (`orderId`).
- **Retries** with backoff, a **dead-letter topic** and a replay tool.
- **Transactional outbox** so the database change and the event cannot diverge.
- **Observability:** trace one order across all stages; dashboards for lag, throughput and failures.
- **Load test** (k6 or Gatling) showing throughput and behaviour when a consumer is down and restarts.

## Presenting your capstone
A strong final presentation (15 minutes):
1. The problem and users; a live demo of the main journey.
2. Architecture diagram and two or three key decisions with their trade-offs (including something you chose **not** to build).
3. Evidence: tests, a failure demonstration (stop a service, show recovery), metrics and traces.
4. Security: authentication, authorisation, data protection and secrets handling.
5. Operations: CI/CD, rollback and backup/restore.
6. What you would do next.

## Course wrap-up
You have now covered the complete Java Full Stack roadmap:
- **Programming fundamentals** - Java, OOP, exceptions, collections, generics, multithreading, Java 8+, files.
- **Databases** - DBMS design, SQL, MySQL, MongoDB and JDBC.
- **Frontend** - HTML, CSS, Bootstrap, JavaScript (ES6+, async, DOM) and React.
- **Build tools and version control** - Gradle, Git and GitHub.
- **Backend** - Spring, Hibernate, Spring Boot, Spring Data JPA, Spring Security, integration, testing, design patterns, system design, microservices, DevOps and cloud.
- **Projects** - from beginner CRUD apps to advanced distributed systems.

Pass the **Final Course Assessment** after this module to complete the course and generate your certificate.

## Key takeaways
- Advanced projects prove architecture, resilience and operations skills, not just features.
- Microservices need sagas, outbox, idempotent consumers, resilience patterns and tracing.
- Multi-tenant SaaS must enforce tenant isolation on every query and test it.
- AI features need server-side keys, grounding (RAG), permission-aware retrieval and human oversight.
- Present your capstone with evidence: demos, tests, failure recovery, metrics and a runbook.
