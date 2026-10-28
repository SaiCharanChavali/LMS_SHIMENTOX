## How to use the project modules
Projects turn knowledge into skill and give you a portfolio. Each of the three project modules lists real-world projects with requirements, a suggested data model and API, and milestones. **Choose at least one project per level and build it end to end** with React, Spring Boot and MySQL, following the practices from earlier modules.

For every project, deliver:
- A GitHub repository with a clear `README.md` (features, architecture diagram, setup, test instructions, screenshots).
- Backend: layered Spring Boot (controller → service → repository), DTOs, validation, global error handling, tests.
- Frontend: React with routing, loading/empty/error states and form validation.
- Security where users own data: registration, login, BCrypt, ownership checks.
- A CI workflow running the tests, and optionally a deployment.

## The standard beginner stack and workflow
```
React (Vite, React Router, Axios) ──> Spring Boot REST API ──> MySQL (JPA/Hibernate, Flyway)
```

Recommended workflow for every project:
1. Write user stories and acceptance criteria.
2. Design the database (ER diagram, Module 9) and REST API (Module 28).
3. Build the backend feature by feature with tests.
4. Build the frontend screens against the API.
5. Add authentication and ownership rules.
6. Test the negative cases, polish, document and deploy.

## Project 1: Task Management Application
**Goal:** users manage their personal tasks with statuses and due dates.

Features:
- Register/login; each user sees only their own tasks.
- Create, edit, delete tasks with title, description, priority (LOW/MEDIUM/HIGH), status (TODO/IN_PROGRESS/DONE) and due date.
- Filter by status/priority, search by title, sort by due date; paginate.
- Highlight overdue tasks; a dashboard with counts per status.

Data model:

```sql
users(id, name, email UNIQUE, password_hash, created_at)
tasks(id, user_id FK, title NOT NULL, description, priority, status, due_date, created_at, updated_at)
```

API:

```
POST   /api/auth/register         POST /api/auth/login
GET    /api/tasks?status=&priority=&q=&page=&size=&sort=dueDate
POST   /api/tasks                 GET  /api/tasks/{id}
PUT    /api/tasks/{id}            PATCH /api/tasks/{id}/status
DELETE /api/tasks/{id}            GET  /api/tasks/summary
```

Key lessons: the server sets `user_id` from the authenticated user (never from the request), validates status transitions and returns 404 (not someone else's task) for other users' IDs.

## Project 2: Personal Expense Tracker
**Goal:** record income and expenses and understand spending.

Features:
- Transactions with amount, type (INCOME/EXPENSE), category, date, note.
- Custom categories per user; monthly budget per category with warnings at 80% and 100%.
- Monthly summary: totals, balance, spending by category (pie chart) and trend over months (line chart, e.g. Recharts).
- Export transactions to CSV; import from CSV with per-line error reporting (Module 8).

Data model:

```sql
categories(id, user_id FK, name, type)
transactions(id, user_id FK, category_id FK, amount DECIMAL(12,2) CHECK (amount > 0), type, txn_date, note)
budgets(id, user_id FK, category_id FK, month CHAR(7), limit_amount DECIMAL(12,2), UNIQUE(user_id, category_id, month))
```

Key lessons: use `BigDecimal`/`DECIMAL` for money, aggregate with `GROUP BY` queries or JPQL projections, and test month boundaries and time zones.

## Project 3: URL Shortener
**Goal:** convert long URLs into short links and redirect visitors.

Features:
- `POST /api/links` with a long URL returns a short code (e.g. `abc123`); optional custom alias and expiry date.
- `GET /{code}` redirects with HTTP 302 (or 301) to the original URL; returns 404 for unknown or expired codes.
- Click analytics: total clicks, clicks per day, referrer and browser.
- Logged-in users see and delete their links.

Design notes:

```java
// Base62 encoding of the database id → short, unique codes
private static final String ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
static String encode(long id) {
    StringBuilder sb = new StringBuilder();
    do { sb.append(ALPHABET.charAt((int) (id % 62))); id /= 62; } while (id > 0);
    return sb.reverse().toString();
}
```

Key lessons: validate URLs (only `http`/`https`, reject `javascript:`), add a unique index on the code, cache hot redirects (Redis, Module 34), rate-limit link creation and record clicks asynchronously so redirects stay fast.

## Project 4: Appointment Booking System
**Goal:** customers book time slots with providers (doctors, trainers, salons).

Features:
- Roles: CUSTOMER, PROVIDER, ADMIN.
- Providers define weekly availability and slot length; customers see free slots and book.
- Cancel/reschedule with rules (e.g. not within 2 hours of the appointment).
- Email confirmation and a reminder the day before (`@Scheduled`, Module 28).
- Provider dashboard of today's appointments.

Data model:

```sql
providers(id, user_id FK, specialty, slot_minutes)
availability(id, provider_id FK, day_of_week, start_time, end_time)
appointments(id, provider_id FK, customer_id FK, start_at, end_at, status,
             UNIQUE(provider_id, start_at))          -- prevents double booking
```

Key lessons: **concurrency** - two customers may book the same slot at once; the unique constraint (or a locking strategy) guarantees only one succeeds and the other gets HTTP 409. Store times in UTC (`Instant`) and display in the user's time zone.

## Project 5: Personal Finance Dashboard
**Goal:** a visual overview of a user's financial health.

Features:
- Accounts (bank, cash, card) with balances; transfers between accounts as one **transaction** (debit + credit, Module 13).
- Net-worth over time, income vs expense charts, top spending categories.
- Savings goals with progress bars.
- Responsive dashboard layout (CSS Grid/Bootstrap, Modules 15-16) with filters by date range.

Key lessons: atomic transfers with `@Transactional`, aggregate queries for charts returned as small DTOs, and frontend data visualisation with clear empty states.

## Milestones and evaluation checklist
Suggested milestones for any beginner project:
1. **Week 1** - requirements, ER diagram, API design, project skeletons (Spring Initializr + Vite), CI.
2. **Week 2** - backend CRUD with validation, error handling, unit and `@WebMvcTest` tests.
3. **Week 3** - React screens, routing, forms; connect to the API.
4. **Week 4** - authentication, ownership, polish, README, deployment.

Before you call it done, verify:
- A fresh clone runs with the README instructions.
- Invalid input returns 400 with field errors; missing items return 404.
- A user cannot read or change another user's data (test it by changing IDs).
- Loading, empty and error states are visible in the UI.
- Tests pass in CI; no secrets are committed.

## Key takeaways
- Build at least one complete beginner project end to end with React, Spring Boot and MySQL.
- Start with requirements, data model and API contract before coding.
- Enforce ownership on the server and validate every input.
- Handle concurrency (bookings), money (`DECIMAL`) and time zones deliberately.
- A project is finished when it is tested, documented and reproducible - not when the happy path works once.
