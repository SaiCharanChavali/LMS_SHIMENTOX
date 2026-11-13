# Course management workflow

**Manage Courses** takes HR and administrators from a new course to tracking employee progress:

Course Management → Create Course → Learning Materials → Assessment → Review & Publish → Course Assignment → Progress Tracking.

A strip at the top of the page shows the current stage. The page has three tabs:

| Tab | Who | Contents |
| --- | --- | --- |
| **Courses** | Admin, HR, trainers (their own courses) | Summary metrics, search, category and status filters, and the course catalogue |
| **Assign a Course** | Admin, HR | The assignment form with a live summary, then assignment, employee-deadline and reminder records |
| **Reminders** | Admin, HR | Reminder settings and reminder history, filtered by course and delivery status |

## Courses (catalogue)

The metrics show total, published, draft and archived courses, assignments, and enrolled learners, all counted from the course list. Search matches title, category, department and description. Each course has:

- **Edit** opens the wizard. Courses in the older 3-module format open their curriculum editor instead.
- **Preview** opens the wizard at Review & publish, which shows the course as employees see it.
- **Assign** opens Assign a Course with the course selected. Only published courses can be assigned: the button is disabled otherwise, and the server refuses with 409.
- **More** contains **Archive**, which hides the course and keeps all records, and **Delete**. A course that employees have started can only be archived.

## Create Course (wizard)

**+ Create course** offers **Create manually** (the wizard) or **Create from a link with AI**. Only the current step is shown. Entered data is kept when moving between steps, and **Save draft** works on every step.

1. **Course basics**: name, description, category, difficulty, estimated duration, department, visibility, course owner/trainer.
2. **Learning materials**: lessons grouped into modules, with text content, PDFs and documents, external links and practical exercises. **+ Add module** starts a new module, and **+ Add lesson** continues the current one. Consecutive lessons with the same module name form one module.
3. **Assessment**: questions, passing score, attempts allowed and time limit. Questions are locked once employees have attempted them.
4. **Review & publish**: a checklist that links back to any step needing attention, a summary, and a full preview. **Publish course** is enabled when the checklist is complete.

Steps with nothing blocking publication are ticked. Lessons added but never filled in are left out when a draft is saved. Leaving the wizard with unsaved changes asks for confirmation.

After a course is first published, the page offers **Assign this course now** or **Back to Course Management** (assign it later with **Assign** in the catalogue).

## Assign a Course

The page opens from **Assign** in the catalogue, from **Assign this course now** after publishing, or from the **Assign a Course** tab. Its breadcrumb (**Manage Courses › Assign a Course**) leads back to the catalogue. On wide screens the form is on the left and the summary on the right; on phones the summary moves below the form.

The form has three sections:

1. **Course and Audience**: published course, assignment type (individual employee, department or job role), and the target. For an individual employee, type part of a name or email and choose from the matching employees. Departments and job roles are picked from a list that shows their employee counts.
2. **Deadline and Requirement**: deadline date and time (IST), and **Mandatory** (requires a deadline) or **Optional** (deadline optional), chosen as option cards.
3. **Additional Information**: an optional note. **Clear** resets the form without sending anything; **Assign Course** saves it.

**Assignment Summary** shows the course, type, target, deadline and requirement, and updates as each field changes; anything not chosen yet shows *Not selected*. **Assignment Rules** lists the rules the server already enforces.

There is no "all employees" assignment type: assignments target an employee, a department or a job role. To reach everyone, assign each department.

The server keeps one assignment per course and target. Assigning a course to a target that already has it asks for confirmation, then updates that assignment rather than adding a second one. Employees are notified, and the course appears in their **My Learning** under the existing assignment rules.

Below the form, three tabs share a search box and Course, Status and Requirement filters, with 10 rows per page:

| Tab | Shows | Actions |
| --- | --- | --- |
| **Assignments** | Every assignment record: who it is assigned to (employee, department or job role), course, assigned date and by whom, deadline, requirement, completion progress and status (Active, Overdue, Completed) | **Update** (deadline, mandatory), **Remove** |
| **Employee Deadlines** | One row per employee and course, from Training Compliance (filtered and paged on the server): deadline, where the assignment comes from, progress and status | **Change** gives that employee an individual deadline |
| **Reminder History** | The latest 100 reminders with delivery status (admin and HR only) | — |

## Reminders

Reminder settings (intervals, Due Soon window, deadline-day and overdue reminders, **Run reminders now**) and the latest 100 reminders, with course and delivery filters. Delivery logic is unchanged; see [course deadlines](course-deadlines.md).

## APIs used

The workflow uses existing endpoints; none were added.

| Endpoint | Used for |
| --- | --- |
| `GET /api/admin/courses` | Catalogue and metrics |
| `POST /api/admin/courses` | Save draft, save changes, publish (wizard) |
| `GET /api/manage/courses/{id}/builder` | Load a course into the wizard |
| `POST /api/admin/courses/{id}/archive`, `.../delete` | More → Archive / Delete |
| `POST /api/manage/assignments`, `POST /api/manage/assignments/{id}/delete` | Assign, update, remove |
| `GET /api/manage/assignments` | Assign a Course → Assignments tab |
| `GET /api/manage/compliance?q&course&status&type&page&size` | Assign a Course → Employee Deadlines tab |
| `GET /api/manage/people`, `GET /api/manage/org` | Employee search, departments and job roles |
| `GET/POST /api/manage/reminders/settings`, `GET /api/manage/reminders/history?courseId`, `POST /api/manage/reminders/run` | Reminders tab |

Training Compliance rows now also include `source` (`employee`, `department` or `job_role`: where the employee's assignment comes from) and `deadlineInput` (the deadline as a form value in IST). Both are read-only additions.

`POST /api/admin/courses` now also accepts an optional `moduleTitle` on each lesson of a lesson-based course. It is stored in the existing `course_lessons.module_title` and `module_index` columns, so no migration is needed. A lesson saved without `moduleTitle` keeps its stored module.
