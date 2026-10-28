# Java Full Stack Development

Published native Shimento course: `java-full-stack-development`.

The module sequence follows the [GeeksforGeeks Java Full Stack roadmap](https://www.geeksforgeeks.org/advance-java/java-full-stack/):
seven sections and one module per roadmap topic. Explanations, worked examples, exercises and
questions are original Shimento material. The course does not embed the external site, reproduce
its articles, or imply external certification.

## Learning sequence

| Section | Modules | Coverage |
| --- | --- | --- |
| 1. Programming Fundamentals | 1–8 | Java Basics, OOP, Exception Handling, Collections, Generics, Multithreading, Java 8 Features, File Handling |
| 2. Database Fundamentals | 9–13 | DBMS, SQL, MySQL, MongoDB, JDBC |
| 3. Frontend Development | 14–22 | HTML, CSS, Bootstrap, JavaScript Fundamentals, Modern JavaScript, Async JavaScript & Browser APIs, DOM & Advanced JavaScript, React.js, Advanced React.js |
| 4. Build Tools | 23 | Gradle |
| 5. Version Control | 24–25 | Git, GitHub |
| 6. Backend Development | 26–37 | Spring Framework, Hibernate, Spring Boot, Spring Data JPA, Spring Security, React + Spring Boot Integration, Testing, Design Patterns, System Design, Microservices, DevOps, Cloud Deployment |
| 7. Real-World Projects | 38–40 | Beginner, Intermediate and Advanced projects |

Each module contains learning objectives, explanations of every roadmap sub-topic with worked
examples and expected output, comparison tables, common mistakes, a practice exercise and key
takeaways (about 53,000 words in total). A three-question knowledge check completes the module.
All three answers must be correct; retries are unlimited.

Java, database, React and Spring labs run in the learner's local JDK/IDE and tools. The LMS does
not compile Java, run backend services or grade project source code.

## Assessments and certificate

A required, secured assessment follows **every** module:

- Modules 1–39: eight applied questions, 10 minutes, 75% pass mark (6/8), three attempts per run.
- Module 40: the **Final Course Assessment**, 20 questions across all seven sections, 30 minutes, 75%.
- Questions may include a code snippet (output prediction, finding the bug).

The checkpoint engine enforces module completion before an assessment starts, locks the next
module until the assessment is passed, shuffles questions and choices, grades on the server from
private per-attempt snapshots, and ends attempts on timeout, tab switch, navigation or reload.

When all 40 modules and all 40 assessments are passed, the run is completed and a printable
certificate of completion is issued (My Certificates → Print / Save PDF).

## Maintenance and validation

Teaching source: `backend/data/java-lessons/01-*.md` to `40-*.md`. Module metadata, knowledge
checks and assessment questions: `backend/tools/build_java_path.py`. Packaged course data:
`backend/data/java-full-stack-course.json`. Rebuild and initialize with:

```powershell
python backend/tools/build_java_path.py
npm run db:init
```

The `java-gfg-v3` content revision is applied once to existing databases. Modules and assignments
from the earlier 30-module edition move, with their learner records, to an archived course
`java-full-stack-development-previous-edition`. Earned certificates are kept. Current runs continue
on the new modules, and an assignment attempt left open on a retired assignment is ended. Later
initialization does not overwrite trainer edits.

Automated checks: `backend/tests/test_java_course.py` (structure, private keys, gating, grading,
ownership/CSRF, timeouts, attempt limits, certificate issue, seeding and the edition upgrade).
Real-browser check: `python backend/tools/check_java_browser.py` (requires Playwright and Edge).
