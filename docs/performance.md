# Performance changes

These changes preserve the rendered UI, API field values, role scope, and learning rules. No password-hashing parameters, exam safeguards, course records, or authentication checks were removed. No cross-user response cache was introduced.

## Changes

| Path | Previous work | Current work |
| --- | --- | --- |
| Admin course lists | One course query plus five lookups per course | Four batched queries, regardless of course count; indexed existence check for learner history |
| Public curriculum | Course metadata plus nine question queries | Course metadata plus one ordered question query; fills public lists directly without copying answer keys |
| Recommendations | A skills query per eligible course, repeated scans of unrelated goals, and a full Python ranking sort | One streamed course/skills query, goals indexed by skill, and bounded top-K ranking |
| Activity history | Materialize SQLite rows, then build timestamp lists | Iterate cursors directly into the required result lists |
| Frontend course resume | Filter/copy enrolled courses and sort to choose one | Single pass; preserves the original locale comparison and tie order |

For C courses and K returned recommendations, Python ranking changes from O(C log C) time and O(C) candidate storage to O(C log K) time and O(K) candidate storage. K is currently six. Skill and goal lookup structures and SQL sorting remain separate costs. Selecting the course to resume changes from O(C log C) time/O(C) temporary storage to O(C) time/O(1) temporary storage.

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

All four before/after output checksums matched. Peak Python allocations do not measure SQLite's internal native buffers, total server memory, database disk usage, or browser memory.

Regression tests compare batched course metadata against individual course views for admin, HR, and trainer scopes; verify question ordering and removal of answer keys; cover recommendation filters, stable ties, top-K limits, and query budgets; and check streamed activity filters. The existing HTTP/SQLite and frontend suites continue to cover permissions, login, assessments, reports, certificates, and other features.
