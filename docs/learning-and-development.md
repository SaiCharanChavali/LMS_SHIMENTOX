# Employee learning & development

ShimentoX Learning is an internal employee portal. Every account is an employee. Roles decide what each person can manage, and the server enforces them on every request. Hiding a button in the UI is not the protection.

## Roles

| Capability | Admin | HR / L&D | Trainer | Manager | Employee |
| --- | --- | --- | --- | --- | --- |
| Own learning, paths, skills & goals, calendar, certificates | Preview only | ✓ | ✓ | ✓ | ✓ |
| Users & Teams, departments, job roles, categories | ✓ | ✓ (not admin accounts) | | | |
| Create, edit, publish and archive courses | ✓ | ✓ | Own courses | | |
| Assign courses and learning paths | ✓ | ✓ | | Direct reports, optional only | |
| Create learning paths | ✓ | ✓ | Own paths | | |
| Define skills | ✓ | ✓ | | | |
| Role competencies (target levels) | ✓ | ✓ | | Roles in own department or held by reports | |
| Record skill evidence | ✓ | ✓ | | Direct reports | |
| Assessments and question banks | ✓ | ✓ | Own / own courses | | |
| Training sessions and attendance | ✓ | ✓ | Own sessions | | |
| Dashboard and reports | Organisation | Organisation | Own courses | Direct reports | |
| Activity log | ✓ | | | | |

HR cannot create, edit, reset or disable administrator accounts. Managers see records only for employees whose manager is set to them.

## How the numbers are calculated

All figures come from stored records at request time. Nothing is hardcoded.

- **Total employees:** active accounts, excluding administrators.
- **Active learners:** employees with video, exercise, exam or assessment activity in the last 30 days.
- **Course completion rate:** completed employee–course pairs divided by all pairs. A pair exists when the employee has enrolled in the course or it is assigned to them (directly, by department, or by job role). A course is complete once any run of it has been completed.
- **Training hours:** verified video watch time plus attended instructor-led sessions.
- **Pending mandatory training:** mandatory assignments that are not yet completed.
- **Employees with learning plans:** employees with an assigned learning path or an active goal.
- **Status of a course for an employee:** Completed, then Overdue (past the due date), then In progress (any activity), then Not started.

## Learning workflow

1. **Create course → add lessons → add assessment → preview → save draft → publish** (Manage Courses). Courses have a category, difficulty, estimated duration, department, trainer, skill tags, module-exam pass mark (25–100%), retake limit (1–3 attempts per module), optional post-training assessment, and learning materials. Materials can be uploaded files (up to 50 MB) or HTTPS links.
2. **Assign** a published course to an employee, department or job role. It can be mandatory (a deadline is required) or optional. Employees are notified once per assignment.
3. **Learning paths** order several published courses. When a path is sequential, each course unlocks after the previous one is completed. Progress, the next recommended course and milestones update automatically from course completions.
4. **Certificates** are issued only when every video, exercise and module exam is complete at the configured pass mark, and the selected post-training assessment has been passed during that course run. Each qualifying run gets exactly one certificate.

## Building lesson-based courses (Manage Courses)

New courses are built in six steps on the Manage Courses page, without leaving it:

1. **Create course:** name, category, description, difficulty, duration, department, visibility (all employees or one department), publication status, assessment pass mark and attempts, owner, skills.
2. **Learning materials:** add any number of lessons; reorder, edit or delete them before publishing. Each lesson can have a title, description, duration, a video (YouTube or Vimeo link, uploaded MP4/WebM, or direct HTTPS video file), an uploaded PDF or Office document (stored privately on the server), external resource links (with quick-add links to official sources such as Microsoft Generative AI for Beginners, Hugging Face Learn, Google's ML Crash Course, Databricks and AWS Skill Builder), text content, and a practical exercise.
3. **Assessment:** multiple-choice and coding questions (a code snippet plus options), correct answers, explanations, pass mark, attempts and time limit. When present it is the course's required post-training assessment.
4. **Preview:** the course exactly as employees will see it, including unsaved changes.
5. **Save draft:** stores the course, lessons, materials and assessment; drafts stay hidden from employees and reopen from the catalog.
6. **Publish:** runs the publishing checklist, asks for confirmation, then makes the course available according to its visibility. The server repeats every check.

Lessons that employees have completed cannot be deleted (edit them, or create a new course version). Department-only courses are also available to anyone who is assigned them, and employees who already started a course keep access if its visibility later narrows. External sites are only linked, never copied.

## Generative AI Fundamentals (packaged course)

A published, beginner, text-based course (Artificial Intelligence, 60 minutes, visible to all employees). It has no video. Its content lives in `backend/data/generative-ai-course.json` and is loaded into the existing tables the first time the server starts:

| Content | Stored in |
|---|---|
| Course details, description, required final assessment | `courses` |
| Lesson title, overview (`description`), structured content (objectives, explanation, examples, tables, code, takeaways), duration | `course_lessons` |
| Lesson knowledge checks (4 questions each, lessons 1-5) and the final assessment (10 of 15 questions) | `assessments` and `assessment_bank`, linked through `course_lessons.assessment_id` and `courses.post_assessment_id` |
| Lesson 6 prompt-writing exercise (4 scenarios, rubric, sample answers, explanations) | `course_lessons.activity_json` |
| Lesson completion and exercise score | `lesson_progress` |
| Knowledge-check and final-assessment attempts, scores, answer order | `assessment_attempts` |
| Exercise submissions | `lesson_activity_attempts` |
| Last lesson opened (resume) | `course_runs.last_lesson_id` |

**Lesson page.** An overview, then structured content written in a safe Markdown subset (`## headings`, `- bullets`, `1. steps`, `| tables |`, fenced code blocks, `**bold**`, `` `code` ``). Sections named "Learning objectives" and "Key takeaways" are highlighted. Each page has an inline knowledge check, a **Mark as complete** button, previous/next navigation, and the lesson list with overall progress. The course reopens at the last lesson the employee viewed.

**Assessment.** Knowledge checks and the final assessment use the standard assessment engine: questions are drawn at random, answer positions are shuffled on every attempt, scoring happens on the server, and the correct answer and an explanation are shown for every question after submission. Every attempt is saved. The pass mark is 70%. Knowledge checks allow 5 attempts and the final assessment allows 3. The certificate requires all six lessons completed and the final assessment passed. Lesson 6 completes when the exercise scores 70% or more.

**Updates.** The course data carries a version number. When a newer version ships, the next server start upgrades the seeded course in place, keeping lesson IDs so employee progress stays attached. A course that an administrator has edited in Manage Courses is never overwritten. A save that changed nothing is detected by comparing a SHA-256 fingerprint of the course and lesson text with the fingerprints of earlier packaged versions (`unchangedFingerprints` in the course data), and such a course is still upgraded. Version 2 replaced the earlier video-based version: its video files, the course-video endpoint and the video generator were removed, and the lessons' video fields were cleared.

## Retrieval-Augmented Generation (packaged course)

A single text lesson, *What is Retrieval-Augmented Generation (RAG)*, in Artificial Intelligence (beginner, 30 minutes, everyone, published). Its concepts and structure follow the GeeksforGeeks article [RAG Architecture](https://www.geeksforgeeks.org/nlp/rag-architecture/), which the lesson credits in its *Learning reference* section; the wording, examples, diagrams and questions are original.

| What | Where |
|---|---|
| Course, lesson text, questions | `backend/data/rag-course.json`, seeded by `seed_lesson_course` into `courses`, `course_lessons`, `assessments` and `assessment_bank` |
| Page layout | `courses.page_layout = 'article'` (other courses use `'standard'`) |
| Knowledge check | The course's required assessment (`retrieval-augmented-generation-check`): 6 questions, 4 options, answers shuffled per attempt, explanations after submitting, pass mark 70% (at least 5 of 6), 5 attempts. It is shown inline in the lesson (`usesFinalAssessment`). |
| Progress | `lesson_progress` (Mark as complete) and `assessment_attempts`; the certificate is issued once the lesson is complete and the check is passed. |

**Course page.** The course uses the same course page as every other lesson-based course: progress header, lesson title block, an *On this page* list of its sections, themed callouts and code boxes, and the *Course content* sidebar. `page_layout` is still stored but no longer changes the page. Because the lesson's knowledge check is the course's required assessment, it is shown in the lesson rather than as a separate final step.

**Lesson text blocks** (in addition to the formatting described for course builders): `[text](https://…)` links; `:::acronym Title | subtitle` with `Letter | Word | description` rows; `:::flow Title` with `Step | caption` rows, drawn as boxes with arrows that stack vertically on narrow screens; `:::example Title` and `:::note Title` asides; and `:::slot knowledge-check`, where the inline knowledge check appears (*Mark as complete* stays at the end of the lesson).

## Skills and competencies

Skill levels are Beginner, Intermediate, Advanced and Expert. An employee's current level is the highest level supported by evidence: a passed skill assessment, or manager- or HR-recorded evidence with a note. **Completing a course never raises a skill level by itself.** A gap is the role target minus the current level. Goals tied to a skill and level complete automatically once evidence reaches that level.

## Assessments

There are four types: pre-training, post-training, knowledge check, and skill assessment. Each has a question bank. Every attempt draws the configured number of questions at random. Scoring, the time limit and the attempt limit are enforced on the server. Employees see whether each answer was right, with the explanation, but not the answer key. Once an assessment has attempts, its question bank and type are locked; create a new assessment to change them.

## Recommendations

Recommendations are rule-based and transparent. Each one lists the reasons it was chosen:

- the next course in an assigned learning path,
- closes a gap between the employee's level and their job role's target,
- supports an active goal,
- revision after a failed skill assessment,
- designed for the employee's department,
- builds on a category the employee has already completed.

Courses already completed, started or assigned are not recommended.

## Notifications

In-app notifications cover:

- new course and path assignments,
- reminders for training due within 7 days or overdue,
- weekly reminders for courses with no activity for 7 days,
- reminders for sessions starting within 2 days,
- session cancellations and changes,
- assessment results,
- certificates earned.

Each notification has a unique key per employee, so the same reminder is never stored twice. Email delivery is not included.

## API (all JSON, authenticated, CSRF-protected writes)

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/me/dashboard` | Profile, assigned and in-progress courses, recommendations, paths, skills, sessions, pending assessments, goals, history |
| GET | `/api/me/paths` | Assigned learning paths with progress and milestones |
| GET | `/api/me/skills` · POST `/api/me/goals` | Skills, gaps, evidence, skill assessments, goals |
| GET | `/api/me/calendar` · POST `/api/me/sessions/{id}/register` and `/cancel` | Sessions, seats and registration |
| GET | `/api/me/assessments` · POST `/api/me/assessments/{id}/start` and `/submit` | Assessments and attempts |
| GET | `/api/me/notifications` · POST `/api/me/notifications/read` | Notifications |
| GET | `/api/me/history` · POST `/api/me/records` | Learning history and self-reported development records |
| GET / POST | `/api/me/assistant` | AI assistant status and requests (see [ai-assistant.md](ai-assistant.md)) |
| GET | `/api/manage/dashboard?from=&to=` | Dashboard metrics for the caller's scope |
| GET | `/api/manage/reports?type=&department=&employee=&course=&from=&to=&page=&export=1` | Reports (`enrollments`, `employees`, `departments`, `assessments`, `skills`, `compliance`, `certificates`); 25 rows per page; `export=1` returns up to 10,000 rows for CSV |
| GET | `/api/manage/org` · `/api/manage/people` | Reference data and employees in scope |
| POST | `/api/manage/departments`, `/job-roles`, `/categories` | Organisation setup |
| GET / POST | `/api/manage/assignments` · POST `/api/manage/assignments/{id}/delete` | Course assignments |
| GET | `/api/manage/courses/{id}/preview` | Draft-safe course preview |
| POST | `/api/manage/courses/{id}/resources` · `/api/manage/resources/{id}/delete` | Learning materials |
| POST | `/api/manage/materials` (binary body, `X-File-Name` header) · GET `/api/materials/{id}` | Private file upload and download |
| GET / POST | `/api/manage/paths` · POST `/paths/{id}/assign` · GET `/paths/{id}/progress` · POST `/path-assignments/{id}/delete` | Learning paths |
| GET / POST | `/api/manage/skills` · POST `/competencies` · POST `/skill-evidence` | Skills framework |
| GET / POST | `/api/manage/assessments` · GET `/assessments/{id}/attempts` | Question banks and attempt history |
| GET / POST | `/api/manage/sessions` · GET `/sessions/{id}/registrations` · POST `/sessions/{id}/attendance` | Instructor-led training |
| POST | `/api/admin/candidates/{id}/profile` | Edit an employee's name, role, department, job role, manager and title |

## Known limitations

- Existing courses keep the original 3-module format (and its curriculum editor). New courses use the lesson-based builder; a course cannot switch format after creation.
- Lessons with a tracked video file complete automatically at the watch threshold; YouTube/Vimeo lessons and lessons without video are marked complete by the employee. Watch reports come from the browser, as with module-course videos, so they are not tamper-proof.
- Practical exercise responses are stored with the employee's learning records but are not graded; the course assessment is multiple choice (including coding questions with a code snippet).
- Learning-path order guides employees in the UI. The server does not block opening a later course directly, because published courses stay open to every employee.
- Uploaded videos are served whole, without HTTP range requests, so seeking in long uploaded videos may be limited. Use hosted HTTPS video for long recordings.
- Session times use the server's local time zone.
- Notifications are in-app only. There is no email or chat delivery.
- An employee's existing completion counts toward a new assignment of the same course; there is no recertification cycle.
