## What makes a project intermediate
Intermediate projects add the challenges real products face: **multiple roles, transactions, real-time updates, file handling, external APIs, search, caching and payments (simulated)**. Pick at least one and build it to production quality: tests at every level, Docker Compose for local setup, CI/CD and a deployment.

Recurring building blocks you will reuse:
- **Role-based access** with Spring Security and method security (Module 30).
- **Pagination, filtering and search** with Specifications (Module 29).
- **File uploads** to S3 or local storage (Modules 28, 37).
- **Async work** with events or a queue (Modules 26, 35).
- **Caching** with Redis for hot reads (Module 34).
- **AI APIs** called from the backend - never from the browser, so API keys stay secret.

## Project 1: AI-Powered Notes Application
**Goal:** a notes app where AI summarises notes, suggests tags and answers questions about them.

Features:
- Rich-text notes organised in notebooks with tags and full-text search.
- "Summarise", "Suggest tags" and "Ask a question" actions using an LLM API called by Spring Boot.
- Share a notebook with another user as viewer or editor.

Design notes:

```java
@Service
public class NoteAiService {
    private final RestClient ai;                     // configured with base URL and API key from env/secrets
    public NoteAiService(RestClient.Builder builder, @Value("${ai.api-key}") String key) {
        this.ai = builder.baseUrl("https://api.example-ai.com").defaultHeader("Authorization", "Bearer " + key).build();
    }
    public String summarise(String noteText) {
        String input = noteText.length() > 8000 ? noteText.substring(0, 8000) : noteText;   // bound cost
        return ai.post().uri("/v1/summarise").body(Map.of("text", input)).retrieve().body(String.class);
    }
}
```

Key lessons: keep the API key on the server; set timeouts and handle failures gracefully; limit input size and per-user usage (cost control); treat AI output as untrusted text when rendering; enforce sharing permissions on every note request.

## Project 2: Smart Expense Management System
**Goal:** a team/company expense tool with approvals.

Features:
- Employees submit expense claims with receipt images (upload to S3).
- Approval workflow: SUBMITTED → MANAGER_APPROVED → FINANCE_APPROVED → PAID, or REJECTED with a reason.
- Policy rules (category limits, receipt required above an amount) implemented as **Strategy** classes (Module 33).
- Optional OCR/AI extraction of amount and date from receipts.
- Reports by department, category and month; CSV export.

Key lessons: model the workflow as an explicit state machine (reject invalid transitions with 409), audit who changed what (Spring Data auditing), authorisation by role **and** relationship (only the employee's manager approves), and pre-signed URLs for private receipts.

## Project 3: Real-Time Chat Application
**Goal:** one-to-one and group chat with live updates.

Features:
- Conversations, group membership, message history with pagination ("load older").
- Real-time delivery with **WebSockets** (Spring WebSocket + STOMP, or plain WebSocket).
- Online presence, typing indicators and unread counts.
- Image attachments.

```java
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {
    public void registerStompEndpoints(StompEndpointRegistry r) {
        r.addEndpoint("/ws").setAllowedOrigins("https://chat.example.com");
    }
    public void configureMessageBroker(MessageBrokerRegistry r) {
        r.enableSimpleBroker("/topic");                // use RabbitMQ/Redis relay when scaling out
        r.setApplicationDestinationPrefixes("/app");
    }
}

@Controller
public class ChatController {
    @MessageMapping("/rooms/{roomId}/send")
    @SendTo("/topic/rooms/{roomId}")
    public ChatMessage send(@DestinationVariable Long roomId, ChatMessage msg, Principal user) {
        // verify membership, persist, then broadcast
        return chatService.save(roomId, user.getName(), msg.text());
    }
}
```

Key lessons: authenticate the WebSocket connection, check room membership on every message, persist before broadcasting, escape message text in React, and use a shared broker so multiple server instances deliver to all clients.

## Project 4: Job Portal
**Goal:** connect recruiters and candidates.

Features:
- Roles: CANDIDATE, RECRUITER, ADMIN.
- Recruiters post jobs (title, skills, location, salary range, remote flag) for their company.
- Candidates build profiles, upload resumes (PDF), search jobs with filters (skills, location, salary, remote) and apply.
- Application pipeline per job: APPLIED → SHORTLISTED → INTERVIEW → OFFER / REJECTED with notifications.
- Saved jobs and job alerts by email.

Key lessons: dynamic search with Specifications and indexes; many-to-many skills; privacy - recruiters see only applicants to **their** jobs; idempotent "apply" (one application per candidate per job, unique constraint).

## Project 5: E-Commerce Platform
**Goal:** an online store with a full purchase flow.

Features:
- Product catalogue with categories, images, search, filters, sorting and pagination.
- Cart (persisted for logged-in users), checkout, orders and order history.
- **Simulated** payment gateway behind an interface (Adapter, Module 33) - never handle real card numbers yourself.
- Inventory management and an admin dashboard (products, orders, sales reports).

Critical rules:
- Prices and totals are calculated on the **server** from the database - never trust prices sent by the client.
- Order lines store a **snapshot** of name and price at purchase time.
- Stock decrement must be safe under concurrency (`UPDATE product SET stock = stock - ? WHERE id = ? AND stock >= ?` and check the row count, or optimistic locking with `@Version`).
- Checkout must be **idempotent** (an idempotency key prevents double orders on retry).

## Project 6: Food Ordering and Delivery Platform
**Goal:** customers order from restaurants; delivery partners deliver.

Features:
- Roles: CUSTOMER, RESTAURANT_OWNER, DELIVERY_PARTNER, ADMIN.
- Restaurant menus with availability and opening hours; location-based restaurant listing.
- Order lifecycle: PLACED → ACCEPTED → PREPARING → OUT_FOR_DELIVERY → DELIVERED (or CANCELLED).
- Live order tracking via WebSockets or server-sent events.
- Ratings and reviews after delivery.

Key lessons: a strict state machine with role checks for each transition (only the restaurant accepts, only the assigned partner delivers), real-time updates, and geographic queries (distance calculation or spatial indexes).

## Project 7: AI Resume Analyzer
**Goal:** analyse a resume against a job description.

Features:
- Upload a resume (PDF/DOCX); extract text (Apache PDFBox / Apache Tika).
- Paste a job description; compute a match score and missing skills.
- AI-generated suggestions to improve the resume, with clear disclaimers.
- History of analyses per user.

Key lessons: validate file type and size; process extraction and AI calls **asynchronously** (return 202 Accepted with a job ID, then poll or push the result); store only what is necessary and let users delete their data; protect against prompt injection by treating document text as data.

## Milestones and quality bar
Suggested plan (5-6 weeks):
1. Requirements, roles/permission matrix, ER diagram, API contract (OpenAPI).
2. Core domain and workflows with unit tests.
3. Persistence with Flyway migrations; integration tests with Testcontainers.
4. Frontend with routing, forms, real-time or file features.
5. Security hardening, Docker Compose, CI/CD, deployment.

Quality bar:
- Permission matrix tested for every role (anonymous, wrong role, wrong owner, correct user).
- Concurrency and retry scenarios tested (double submit, two buyers, duplicate application).
- External services (AI, email, payment) behind interfaces with timeouts and test doubles.
- Observability: structured logs with request IDs, health endpoints.

## Key takeaways
- Intermediate projects combine roles, workflows, real-time features, files and external APIs.
- Keep secrets and AI keys on the server; set timeouts and cost limits.
- Model workflows as explicit state machines with role-checked transitions.
- The server owns prices, permissions and stock; use transactions, constraints and idempotency.
- Test permission matrices, concurrency and failure paths - not just the happy path.
