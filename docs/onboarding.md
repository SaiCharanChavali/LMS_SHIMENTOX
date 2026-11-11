# Automatic employee onboarding

When HR adds an employee in **Users & Teams**, the LMS assigns a structured onboarding plan from published courses, based on the employee's department, job role and joining date. Onboarding works without Keka.

Onboarding reuses what the portal already has:

- **Assignments:** onboarding courses are ordinary course assignments, so My Learning, deadlines, deadline reminders, Training Compliance and certificates treat them exactly like any other training.
- **Completion:** the existing lessons and assessments decide it.

No video is involved.

## Templates (Onboarding → Templates, HR and Admin)

A template has:

- a name and description;
- a department, or **All departments**;
- one or more job roles, or none for every job role in the department;
- milestones such as Day 1, 7, 30, 60 and 90 (the **Use Day 1, 7, 30, 60 and 90** button adds them);
- published courses, each at a milestone and marked mandatory or optional.

Rules:

- **Course deadlines:** each mandatory course is due at 11:59 PM, portal time, on its milestone day. Day 1 is the start date itself, so Day 30 is 29 days later. Optional courses have a target milestone but no deadline, so they never become overdue.
- **Mandatory courses:** a template needs at least one, because onboarding is complete when every mandatory course is complete.
- **Published courses only:** templates can use only published courses. If a course is unpublished later, activating the template is refused until it is removed, and onboarding started from it skips the course and says so.
- **Statuses:** Draft, Active, Inactive or Archived. Only active templates are used. An archived template is read-only until it is restored, as Inactive.
- **No overlaps:** two active templates cannot cover the same department and overlapping job roles, so matching is never ambiguous.
- **Editing is safe:** editing or archiving a template never changes onboarding that has already started. Each onboarding keeps a snapshot of its courses and milestones.

## Automatic assignment

When HR adds an employee:

1. The employee's department, job role and joining date (a new field on the Add employee form, defaulting to today) are read.
2. The most specific active template is chosen:
   1. one naming the employee's job role;
   2. then one for their department only;
   3. then one for all departments.
3. Each course is assigned to the employee individually. Mandatory deadlines are counted from the joining date.
4. The employee receives one notification, **Your onboarding plan**, listing the courses and the first milestone. They do not get a separate notice per course.
5. HR sees the outcome in the confirmation message, and the Activity Log records it.

**Edge cases**

| Situation | What happens |
| --- | --- |
| No template matches | Nothing is assigned. HR is told to set up a template, and the employee appears under **Needs onboarding** with the reason. |
| The employee already has a course (individually, by department or by job role) | That assignment and its deadline stay in force. Onboarding links to it ("Already assigned") and never creates a second assignment. |
| The joining date is in the past | No deadline is earlier than the end of the day onboarding starts. A course is never overdue the moment it is assigned. Later milestones keep their dates. |
| Joining date in the future | Deadlines follow it, so new hires can be set up before they join. |
| Starting twice | Refused. An employee can have only one onboarding in progress (enforced in the database). |
| Administrators | Never onboarded. |
| Keka-created accounts | Not onboarded automatically, because Keka sync was not changed. They appear under Needs onboarding. |

**Existing employees.** Under **Onboarding → Needs onboarding**, HR picks a template (the matching one is preselected) and a start date, then selects **Start**. The start date defaults to the joining date, or today when the joining date has passed.

**Cancelling.** Expand an employee on the Overview tab and select **Cancel onboarding**. Unfinished course assignments it created are removed; completed course records stay. A new onboarding can then be started.

## What employees see

When an employee has onboarding:

- **My Learning** opens with **Your onboarding**:
  - the completion percentage (mandatory courses only), with optional courses counted separately;
  - status, start date and next milestone;
  - milestone cards;
  - every course with mandatory or optional label, deadline, status (Not Started, In Progress, Due Soon, Overdue, Completed On Time or Late), progress, best assessment result, and a **Start / Continue / Review** button that opens the course.
- **My Dashboard** shows a compact version.

## Reminders

Course deadlines use the existing reminder schedule (Manage Courses → Reminder schedule): reminders before the deadline, on the deadline day, and when overdue. Onboarding adds, through the same background pass:

| Notice | Sent to | When |
| --- | --- | --- |
| Onboarding milestone coming up | Employee | Within the Due Soon window (default 7 days) of a milestone with mandatory courses unfinished. Not sent for milestones already that close when onboarding started. |
| Onboarding milestone missed | Employee and their manager | After a milestone passes with mandatory courses unfinished |
| Onboarding complete | Employee and their manager | When every mandatory course is complete |

Each notice is sent once (unique notification keys), never to disabled accounts, and never for completed milestones.

## Monitoring (Onboarding → Overview)

HR and Admin see the whole organisation; managers see **Team Onboarding** for their direct reports only. Filters: employee search, department, job role, onboarding status and joining-date range. They apply to every figure and to exports.

- **Summary cards:** currently onboarding, completed, employees with pending mandatory courses, overdue mandatory courses, average completion.
- **Progress by department and by job role.**
- **Employee table:** completion, status, next milestone. Expand a row for the individual summary: milestones, every course, assessment results, and when and how onboarding started.
- **Export** as CSV or Excel. Exports are recorded in the Activity Log.

**Statuses**

| Status | Meaning |
| --- | --- |
| Completed | Every mandatory course is complete |
| Overdue | A mandatory course is past its deadline |
| In progress | Any onboarding course started |
| Not started | Otherwise |

Completion is worked out from course records when the page loads, so it is always current. Certificates follow the existing course rules; onboarding issues none of its own.

## Permissions (enforced by the server)

| Role | Access |
| --- | --- |
| Employee | Their own plan (`GET /api/me/onboarding`) |
| Manager | Read-only monitoring and individual summaries for direct reports |
| HR, Admin | Templates, starting and cancelling onboarding, organisation-wide monitoring and exports |
| Trainer | None |

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/me/onboarding` | The signed-in employee's onboarding, or `null` |
| GET | `/api/manage/onboarding?q=&department=&jobRole=&status=&from=&to=&page=&waitingPage=` | Summary, groups, employees, and (HR/Admin) employees needing onboarding |
| GET | `/api/manage/onboarding/export?format=csv\|xlsx&…filters` | Download |
| GET | `/api/manage/onboarding/{id}` | One employee's onboarding summary |
| POST | `/api/manage/onboarding/{id}/cancel` | Cancel |
| POST | `/api/manage/onboarding/start` | `{employeeId, templateId?, startDate?}` |
| GET / POST | `/api/manage/onboarding/templates` | List, create or edit (`{id?, name, description, departmentId, jobRoleIds, milestones:[{day,title}], courses:[{courseId,day,mandatory}], status}`) |
| POST | `/api/manage/onboarding/templates/{id}/status` | `{status: active\|inactive\|archived}` |
| POST | `/api/admin/candidates` | Now accepts `joiningDate` and returns `onboarding` with the outcome |

## Database (schema version 10)

Added automatically on the next server start; existing records are untouched. Back up `backend/data/lms.sqlite3` first.

| Table or column | Purpose |
| --- | --- |
| `candidates.joining_date` | Joining date (YYYY-MM-DD) |
| `onboarding_templates` | Name, description, department, status, audit fields |
| `onboarding_template_roles` | Job roles a template applies to |
| `onboarding_template_milestones` | Milestone days and names |
| `onboarding_template_courses` | Course, milestone day, mandatory flag, order |
| `employee_onboarding` | One onboarding per employee: template and its name at the time, start and joining dates, automatic or manual, status. A unique index allows one in progress per employee |
| `employee_onboarding_courses` | Snapshot of each course: milestone, mandatory flag, deadline, and whether it was assigned, linked to an existing assignment, or skipped |

Template department and job-role references deliberately have no foreign key. If a department or job role is deleted, its templates stop matching anyone instead of matching everyone; the Templates tab shows a warning.

## Known limitations

- **Joining date changes:** changing an employee's department, job role or joining date after onboarding has started does not change it. Cancel and restart it if needed.
- **Keka accounts:** these are not onboarded automatically; start them from Needs onboarding.
- **In-app only:** notifications are in-app, as in the rest of the portal. There is no email.
