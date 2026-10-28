# Backend

Python standard-library HTTP API and SQLite database. No third-party runtime packages are needed. Run `npm start` at project root, or `python backend/server.py`. The default address is http://localhost:5173, bound to the local computer.

## Files

- `server.py`: command-line entry point; supports `--port`, `--host`, and `--init-db`.
- `src/server.py`: HTTP routes, static serving, cookie sessions, CSRF/origin checks, JSON validation.
- `src/services.py`: accounts, enrollment, progress, exercise/exam grading, certificates, record exports.
- `src/course_import.py`: Import from URL workflow: preview tokens, saving as a draft or published course, duplicate checks.
- `src/importers/`: the course importer: `fetch.py` (SSRF-safe HTTP, robots.txt, limits), `dom.py` (HTML tree and metadata), `markdown.py` (structure-preserving conversion), `pipeline.py` (crawl, limits, preview structure), `platforms.py` (platform detection and extractors).
- `tools/import_smoke.py`: live check of the importer against real sites (needs internet).
- `src/security.py`: scrypt password hashing, constant-time verification, opaque session tokens.
- `src/database.py`: SQLite connections, schema initialization and curriculum seeding.
- `database/schema.sql`: version 2 normalized schema and indexes; safe to initialize repeatedly.
- `data/python-course.json`: private curriculum seed with answer keys; never served to the browser.
- `data/lms.sqlite3`: generated database, excluded from version control.
- `tests/test_portal.py`: integration tests using real HTTP requests and an isolated database.

## Account flow

Public registration is disabled. The local browser setup form creates or promotes the first admin when no admin exists. Admins provision accounts with full name, assigned email, role, and an 8-128 character temporary password. Provisioned users must change their temporary password before any learning or admin access. Existing version 1 accounts retain their password/progress and default to the candidate role. Email matching is case-insensitive and duplicates are rejected. Passwords remain salted and hashed with scrypt; failed logins are rate-limited.

Admin pages and endpoints require the admin role stored in SQLite. Password resets and disabling accounts revoke sessions and terminate active exams. Admin actions are recorded without passwords. See [admin guide](../docs/admin-guide.md).

Session tokens are random, stored hashed in SQLite, and delivered in HttpOnly, SameSite=Lax cookies. Default expiry is eight hours; Keep me signed in extends it to 30 days. Logout deletes the session. A password change verifies the old password and revokes other sessions. Writes require a custom request header and, after login, the session-specific CSRF token. API responses are not cached. No default candidate credentials are seeded.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/session` | Current candidate, CSRF token, and first-admin setup availability |
| POST | `/api/setup/admin` | First local admin setup only; returns 409 after setup |
| POST | `/api/auth/register` | Disabled; returns 403 |
| POST | `/api/auth/login` | Verify credentials and create session |
| POST | `/api/auth/logout` | End current session and active exam |
| POST | `/api/auth/password` | Change password; revoke other sessions |
| GET | `/api/learning` | Candidate's current progress, certificates, sanitized curriculum |
| POST | `/api/learning/resume` | Reconcile reload/open-tab interruption |
| POST | `/api/learning/video` | Save video watch position/completion |
| POST | `/api/learning/exercise` | Store answers and return graded practice feedback |
| POST | `/api/learning/exam-start` | Check prerequisites; atomically consume an attempt |
| POST | `/api/learning/exam-finish` | Grade or terminate an active attempt |
| POST | `/api/learning/restart` | Archive run and enroll in a fresh run |
| GET | `/api/records` | Export the signed-in candidate's complete learning history |

All learning POSTs except enrollment include `runId` and action-specific fields. Enrollment uses `courseId`; `GET /api/learning?courseId=...` selects a published, enrolled course. Candidate identity is always taken from the session, never a submitted candidate ID. A run owned by another candidate is rejected. Exam and certificate results supplied by clients are ignored; the server calculates them. Server time controls exam deadlines. Failed and terminated attempts count toward the limit of three per set per run. Writes use SQLite transactions to prevent parallel exam starts consuming inconsistent counters.

## Role and course APIs

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/courses` | Published catalog and own progress |
| POST | `/api/learning/enroll` | Enroll/open a published course |
| GET | `/api/certificates` | All owned certificates |
| GET | `/api/admin/overview` | Organization statistics |
| GET / POST | `/api/admin/candidates` | List/provision accounts |
| GET | `/api/admin/candidates/{id}/records` | Inspect a candidate's learning records |
| POST | `/api/admin/candidates/{id}/reset-password` | Set a temporary password and revoke sessions |
| POST | `/api/admin/candidates/{id}/status` | Enable/disable account access |
| GET / POST | `/api/admin/courses` | Private curriculum and course authoring |
| GET | `/api/admin/audit` | Last 100 administrator actions |
| POST | `/api/manage/import/preview` | Retrieve and extract a course URL for review (`{url}`); returns a preview token. Runs outside the write transaction |
| POST | `/api/manage/import/save` | Save a reviewed import (`{token, mode: full\|reference, rightsConfirmed, status: draft\|published, title, category, ...}`) |

`src/admin.py` implements administration. `POST /api/setup/admin` configures the first admin from a loopback browser request and permanently locks once an admin exists. `database/migrations/002_roles_and_courses.sql` preserves version 1 records while adding roles, first-login flags, course content, and audit records. Initialization is repeatable and never promotes an account automatically.

## Configuration and operation

Use PowerShell environment variables before `npm start` when needed:

```powershell
$env:PORT = '5173'
$env:LMS_DB_PATH = 'C:\path\to\persistent\lms.sqlite3'
```

The default database is `backend/data/lms.sqlite3`. `LMS_COOKIE_SECURE=1` enables the Secure cookie flag when served through HTTPS; leave it off for local HTTP. `.env` files are not loaded automatically. `LMS_QUIET=1` silences access logs. Logs never include request bodies, passwords, or session tokens.

Use `npm run db:init` to initialize. Back up the SQLite database with SQLite's backup API while running, or stop the server before copying it. Do not delete the database to update the app. Current initialization preserves existing records; future schema changes need versioned migrations. Integration tests use a separate temporary database and do not modify candidate records.

The included Python HTTP server is for local development, not public production hosting. Deployment needs a hardened application server or reverse proxy, HTTPS, durable disk storage, and backups. Self-service email verification and forgotten-password email recovery are not implemented. Browser tab events and video playback reports remain client observations, not secure proctoring.

Security references: [Python scrypt API](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt) and [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
