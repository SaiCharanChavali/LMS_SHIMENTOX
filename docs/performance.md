# Performance changes

These changes preserve the rendered UI, API field values, role scope, and learning rules. No password-hashing parameters, exam safeguards, course records, or authentication checks were removed. No cross-user response cache was introduced.

## Changes

| Path | Previous work | Current work |
| --- | --- | --- |
| Admin course lists | One course query plus five lookups per course | Three batched queries, regardless of course count; indexed existence check for learner history |
| Public curriculum | Course metadata plus nine question queries | Course metadata plus one ordered question query; fills public lists directly without copying answer keys |
| Recommendations | A skills query per eligible course, repeated scans of unrelated goals, and a full Python ranking sort | One completed-categories query, one streamed course query, and bounded top-K ranking |
| Activity history | Materialize SQLite rows, then build timestamp lists | Iterate cursors directly into the required result lists |
| Frontend course resume | Filter/copy enrolled courses and sort to choose one | Single pass; preserves the original locale comparison and tie order |

For C courses and K returned recommendations, Python ranking changes from O(C log C) time and O(C) candidate storage to O(C log K) time and O(K) candidate storage. K is currently six. SQL sorting remains a separate cost. Selecting the course to resume changes from O(C log C) time/O(C) temporary storage to O(C) time/O(1) temporary storage.

Activity results still require O(A) storage for A returned events. The change removes the extra O(A) intermediate SQLite-row buffer rather than pretending the output can be constant-space. Course-list output likewise still contains every requested curriculum; its unavoidable output memory remains proportional to the catalog.

## Reproducible measurements

Run from the project root:

```powershell
npm run benchmark
```

The benchmark uses an isolated in-memory SQLite fixture: 100 courses, 1,000 historical/current runs, and 6,000 video-progress records. It never reads or writes the live candidate database. It records SELECT counts, median warmed execution time, peak Python allocations using tracemalloc, and an output checksum. Timings vary with the computer and concurrent workload; these are synthetic measurements, not a production latency guarantee.

Recorded before/after on the same fixture:

| Path | SELECTs before → after | Peak Python KiB before → after |
| --- | --- | --- |
| Admin courses | 501 → 4 | 2,122.2 → 2,109.6 |
| Curriculum | 10 → 2 | 15.4 → 13.3 |
| Recommendations | 107 → 7 | 87.4 → 11.1 |
| Activity history | 2 → 2 | 1,279.7 → 410.0 |

All four before/after output checksums matched.

**12 November 2026:** skills, goals and learning paths were removed from the portal. Admin course lists now use three queries (no skill-tag lookup) and recommendations two (completed categories, then courses). The measurements above are from before that change. Peak Python allocations do not measure SQLite's internal native buffers, total server memory, database disk usage, or browser memory.

Regression tests compare batched course metadata against individual course views for admin, HR, and trainer scopes; verify question ordering and removal of answer keys; cover recommendation filters, stable ties, top-K limits, and query budgets; and check streamed activity filters. The existing HTTP/SQLite and frontend suites continue to cover permissions, login, assessments, reports, certificates, and other features.

## Query batching pass (12 November 2026)

Every main endpoint was profiled at 10 and 60 employees, counting SQL statements per request. Work that ran one or more queries per row (per employee, assessment, lesson, assignment or checkpoint) now reads each kind of record once and groups it in memory, with the same output. No endpoint's query count grows with the number of employees any more.

| Endpoint | Queries before (60 employees) | After |
| --- | --- | --- |
| Admin onboarding monitoring | 126 (grew ~2 per employee) | 7 |
| Admin assessments (question banks) | 106 (3 per assessment) | 5 |
| Employee assessments | 77 (2 per assessment) | 6 |
| Employee notifications | 100 (module-exam checks on every run) | 25 |
| Course page (Generative AI) | 44 | 28 |
| Course page (Java, 40 checkpoints) | ~120 (3 per checkpoint) | 30 |
| Employee dashboard | 46 | 34 |
| Course catalog | 18 (department per course) | 9 |
| Admin assignments list | up to 4 per assignment | 7 |
| Revision games | 14 (bank per lesson) | 9 |

Other changes:

- Checkpoint readiness and lesson locks use one linear pass over checkpoints sorted by position (was quadratic in checkpoints, plus queries per lesson).
- Staff notifications find their recipients with two indexed lookups instead of scanning every account; new indexes `candidates(role)` and `development_records(employee_id, completed_on)`.
- Frontend: the lesson sidebar and onboarding plan group checkpoints and courses in one pass instead of filtering the whole list per row.

Remaining per-item statements are output-proportional: each in-app reminder or notification is one indexed `INSERT OR IGNORE`, and organisation-wide reports read every relevant row once. The reminder scheduler still handles each employee in its own short transaction on purpose, so its write lock stays brief.
