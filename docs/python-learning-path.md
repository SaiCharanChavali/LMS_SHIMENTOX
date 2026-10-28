# Python Programming Senior

This native course is published as **Python Programming Senior** with ID
`shimento-python-developer`. It uses the existing Shimento logo, lesson player,
authenticated media delivery, enrollment and progress tracking. Restart the server
or run `npm run db:init` to seed it into an existing database. Existing courses,
learner histories and subsequent administrator edits are preserved.

The 18 original lessons follow the public topic sequence at
https://www.freecodecamp.org/learn/python-v9/: basics, installation, sequences,
dictionaries, configuration project, errors, classes, budget project, OOP,
polygon project, linear structures, hash tables, recursion, searching/sorting,
Hanoi, graphs/trees, dynamic programming and a final review/capstone.

These are new Shimento explanations, examples, practice instructions. Videos are disabled.
They are a syllabus-aligned adaptation, not an import of every freeCodeCamp
challenge. No freeCodeCamp lesson text, solutions, test harness, videos, logos or
certification exam are distributed. The upstream README distinguishes the BSD
software license from copyright on curriculum resources:
https://github.com/freeCodeCamp/freeCodeCamp#license.

Each module has original teaching text, a worked example, a coding workshop or lab,
starter code, visible practice tests, and a three-question knowledge check. The
editor runs Python locally in the browser using the packaged Pyodide 314.0.7
runtime. No third-party runtime request or Python execution on the LMS server is
needed. The Python videos, captions, posters and watch requirement have been removed
from this course. Other courses retain their existing videos.

Code runs in a disposable worker inside a sandboxed, opaque-origin iframe.
The runner cannot access the portal window, cookies or session API. Its CSP permits
runtime downloads only from the local runtime asset directory. Execution is stopped
after five seconds, and console output is limited to 24,000 characters. A separate
45-second startup limit handles loading failures. Chromium cannot initialize module
worker entry points in this opaque-origin context, so the worker uses a classic
entry point with dynamic ES-module imports, never importScripts.

Run & check saves the current code to the learner's own course run, executes it and
shows test feedback. Save code stores a draft without executing it. Reset starter
restores the initial code; Stop execution terminates the worker. Drafts are stored
in SQLite and reloaded when the learner reopens the course. Practice output and
feedback are temporary. Learner code is never executed by a backend endpoint.

Coding checks are for practice, not secure assessment grades. Module completion
requires all three knowledge-check answers to be correct; these are graded by the
server with unlimited retries. Existing lesson completions, assignments, attempts
and earned certificates are preserved during the one-time interactive conversion.
Course completion remains Shimento completion, not freeCodeCamp certification.

Six required assignments appear after modules 3, 6, 9, 12, 15 and 18. Each contains
eight automatically graded, scenario-based multiple-choice and code-reasoning
questions covering its three modules:

| Modules | Assignment |
| --- | --- |
| 1–3 | Build a training-score report |
| 4–6 | Validate an employee settings record |
| 7–9 | Review a budget and media model |
| 10–12 | Design a shape inventory and lookup table |
| 13–15 | Trace a search and recursive move planner |
| 16–18 | Plan routes and verify a learning catalogue |

The server requires completion of the related three modules and all earlier
assignments. Passing unlocks the next group. All six passes are required for a new
completion certificate, and assignments count toward course progress. Existing
earned certificates and learner records are retained.

Assignments use the existing exam policy: 10 minutes, 75% (6/8 correct), three
attempts per course run. Starting consumes an attempt. Tab hiding, window blur,
navigation, reload and page closing send a keepalive termination request; reopening
the course reconciles an interrupted attempt. Logout, password reset, disabling an
account and starting a new run also terminate active attempts. Server deadlines
apply even when the browser timer is disabled. Browser events are observations,
not device-level proctoring, and cannot detect every use of another device or app.

Questions and options are shuffled for each attempt and snapshotted privately.
Answer keys never appear in learner APIs or record exports. The server enforces
ownership, CSRF, prerequisite checks, atomic attempt limits and final grades.
Replaying a finished submission cannot change its result. Locked module text and
media are withheld from learners until the relevant assignment is passed.
Assignment history, scores and termination reasons are stored per course run.
Fresh runs reset attempts and requirements while preserving previous records.

Edit `backend/data/python-assignments.json` to maintain assignment source content,
then rebuild the Python path. Initialization inserts newly packaged assignments
into existing installations without replacing an already seeded assignment or its
history. It does not overwrite administrator edits to existing lesson content.

Edit `backend/tools/build_python_path.py` for explanations and examples, and
`backend/data/python-practice.json` for original workshop starters, tests, reference
solutions and knowledge checks. Reference solutions and quiz keys stay on the
server. Rebuild the packaged source with:

```powershell
python backend/tools/build_python_path.py
npm run db:init
```

Initialization applies the interactive conversion once (revision `interactive-v1`)
and preserves later administrator edits. A later source change needs an explicit
new content revision or an edit in Manage Courses; restarting does not overwrite
already-installed content.

Runtime files live in `frontend/public/assets/python-runtime` and retain Pyodide's
MPL 2.0 license. Upstream source: https://github.com/pyodide/pyodide/tree/314.0.7.
Only static runtime assets permit anonymous cross-origin reads for the opaque
runner. Authenticated API responses do not permit cross-origin reads.

Verification: `npm test` checks API and frontend behavior. With Playwright and Edge
installed, `python backend/tools/check_python_browser.py` checks actual browser
execution, saved drafts, server-graded completion, infinite-loop termination,
blocked access to the portal API, and the mobile layout using isolated test data.


## Detailed teaching revision

All 18 modules now load original, structured teaching from
`backend/data/python-lessons-detailed/`. Each includes conceptual explanations,
a runnable worked example with an output walkthrough, practical pitfalls and
guided acceptance checks. Sections appear in the existing module outline.
The installation module clearly distinguishes terminal commands from Python.

Rebuild with `python backend/tools/build_python_path.py`, then apply with
`npm run db:init` (or restart the server). Revision `python-detailed-v2` upgrades
unchanged packaged summaries by their legacy content hashes and preserves
trainer-edited lesson text. It changes no coding contracts, knowledge questions,
assignment banks, attempts, saved drafts or progress. Reinitializing does not
replace later trainer edits. The course remains original Shimento material.

The Python path tests execute all 18 trusted worked examples and assert their
outputs. They also check unchanged exercise/assessment contracts and migration
preservation. Learner-submitted Python continues to run only in the browser
sandbox, never through these backend example tests.
