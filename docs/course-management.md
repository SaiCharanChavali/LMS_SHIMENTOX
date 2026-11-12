# Course management workflow

**Manage Courses** takes HR and administrators from a new course to tracking employee progress:

Course Management → Create Course → Learning Materials → Assessment → Review & Publish → Course Assignment → Progress Tracking.

A strip at the top of the page shows the current stage. The page has three tabs:

| Tab | Who | Contents |
| --- | --- | --- |
| **Courses** | Admin, HR, trainers (their own courses) | Summary metrics, search, category and status filters, and the course catalogue |
| **Assignments & progress** | Admin, HR | The assignment form, existing assignments and employee progress for one published course |
| **Reminders** | Admin, HR | Reminder settings and reminder history, filtered by course and delivery status |

## Courses (catalogue)

The metrics show total, published, draft and archived courses, assignments, and enrolled learners, all counted from the course list. Search matches title, category, department and description. Each course has:

- **Edit** opens the wizard. Courses in the older 3-module format open their curriculum editor instead.
- **Preview** opens the wizard at Review & publish, which shows the course as employees see it.
- **Assign** opens Assignments & progress with the course selected. Only published courses can be assigned: the button is disabled otherwise, and the server refuses with 409.
- **More** contains **Archive**, which hides the course and keeps all records, and **Delete**. A course that employees have started can only be archived.

## Create Course (wizard)

**+ Create course** offers **Create manually** (the wizard) or **Create from a link with AI**. Only the current step is shown. Entered data is kept when moving between steps, and **Save draft** works on every step.

1. **Course basics**: name, description, category, difficulty, estimated duration, department, visibility, course owner/trainer.
2. **Learning materials**: lessons grouped into modules, with text content, PDFs and documents, external links and practical exercises. **+ Add module** starts a new module, and **+ Add lesson** continues the current one. Consecutive lessons with the same module name form one module.
3. **Assessment**: questions, passing score, attempts allowed and time limit. Questions are locked once employees have attempted them.
4. **Review & publish**: a checklist that links back to any step needing attention, a summary, and a full preview. **Publish course** is enabled when the checklist is complete.

Steps with nothing blocking publication are ticked. Lessons added but never filled in are left out when a draft is saved. Leaving the wizard with unsaved changes asks for confirmation.

After a course is first published, the page offers **Assign this course now** or **Back to Course Management** (assign it later with **Assign** in the catalogue).

## Assignments & progress

The form follows the assignment workflow:

1. Published course.
2. Assignment type: individual employee, department or job role.
3. The target. The selector changes with the type, and department and job-role options show their employee counts.
4. Deadline date and time, in IST.
5. Mandatory or optional. Mandatory training requires a deadline.
6. Note (optional).
7. **Assign course**.

There is no "all employees" assignment type: assignments target an employee, a department or a job role. To reach everyone, assign each department.

The server keeps one assignment per course and target. Assigning a course to a target that already has it asks for confirmation, then updates that assignment rather than adding a second one. Employees are notified, and the course appears in their **My Learning** under the existing assignment rules.

**Existing assignments** can be filtered by target type and requirement. Each row keeps deadline updates, the mandatory switch and **Remove**.

**Employee progress** shows assigned, completed, due-soon and overdue counts. It lists every employee who has the course, with their deadline, its source, requirement, status, progress, and last and next reminder. It can be searched and filtered by status, requirement and department. **Change** sets an individual deadline. **Training Compliance** covers all courses at once.

## Reminders

Reminder settings (intervals, Due Soon window, deadline-day and overdue reminders, **Run reminders now**) and the latest 100 reminders, with course and delivery filters. Delivery logic is unchanged; see [course deadlines](course-deadlines.md).

## APIs used

The workflow uses the existing endpoints; none were added.

| Endpoint | Used for |
| --- | --- |
| `GET /api/admin/courses` | Catalogue and metrics |
| `POST /api/admin/courses` | Save draft, save changes, publish (wizard) |
| `GET /api/manage/courses/{id}/builder` | Load a course into the wizard |
| `POST /api/admin/courses/{id}/archive`, `.../delete` | More → Archive / Delete |
| `POST /api/manage/assignments`, `POST /api/manage/assignments/{id}/delete` | Assign, update, remove |
| `GET /api/manage/deadlines?courseId` | Existing assignments and employee progress |
| `GET/POST /api/manage/reminders/settings`, `GET /api/manage/reminders/history?courseId`, `POST /api/manage/reminders/run` | Reminders tab |

`POST /api/admin/courses` now also accepts an optional `moduleTitle` on each lesson of a lesson-based course. It is stored in the existing `course_lessons.module_title` and `module_index` columns, so no migration is needed. A lesson saved without `moduleTitle` keeps its stored module.
