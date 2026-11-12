# Learning activity history

The portal records meaningful learning events in `learning_activity_logs` (schema version 11). Every event is written by the
server inside the learning workflow it describes. The server sets the timestamp, and logging never blocks the learning action
itself. Employees see their own timeline on **Learning history**. HR and admins see **Learning Activity**, and managers see
**Team Activity** for their active direct reports.

## Events

| Type | Recorded when |
| --- | --- |
| `course_started` | The employee first opens a course run |
| `course_resumed` | The employee opens an incomplete run that already has progress |
| `course_opened` | Any other open, such as an untouched run or a completed course being reviewed |
| `course_completed` | The run is completed (the existing completion rules, unchanged) |
| `lesson_started` / `lesson_opened` | First open of a lesson in a run / later opens |
| `lesson_completed` | A lesson's progress row is first created, or a module video is first completed |
| `assessment_started` | A module exam, course assignment or standalone assessment attempt starts |
| `assessment_submitted` + `assessment_passed` / `assessment_failed` | An attempt is submitted and scored (knowledge checks included). Terminated and expired attempts were not submitted. |
| `certificate_generated` | A certificate is issued |
| `resource_accessed` | A course learning material is opened from the course page |

Bookmarking does not exist in the portal, so it is not tracked.

## Reliability

- **No duplicates:** `UNIQUE(employee_id, dedupe_key)` stores each event once. Retried requests, replayed submissions and backfill
  reruns add nothing.
- **Repeated opens:** opening the same course or lesson again within 10 minutes counts as one visit. A repeated resource click
  within 1 minute counts as one access.
- **Failures never block learning:** each write runs in a savepoint. A failure is rolled back on its own, and the lesson,
  assessment or completion still saves.
- **History is never lost:** rows are never updated or deleted by learning workflows. If a course, lesson or assessment is
  removed, its link becomes NULL and the metadata keeps the titles in force at the time.
- **Privacy:** answers, answer keys, dwell time and keystrokes are never stored.

## Upgrade

Upgrading to version 11 copies earlier learning records into the log once, marked `backfilled`. That covers runs with
progress, completions, certificates, lesson and video completions, and exam, assignment, assessment and knowledge-check
attempts. Opens and resumes were never recorded before version 11, so they cannot be reconstructed.

## API

| Endpoint | Who | Purpose |
| --- | --- | --- |
| `GET /api/me/history?course&type&from&to&page` | Signed-in employee | Own timeline (20 per page), attended sessions, self-reported records |
| `POST /api/me/resources/{id}/open` | Signed-in employee | Records a material access and returns its URL |
| `GET /api/manage/activity?q&employee&department&jobRole&course&type&from&to&page` | Admin, HR, manager (team) | Summary metrics and activity table (25 per page) |
| `GET /api/manage/activity/employees/{id}` | Admin, HR, the employee's manager | One employee's timeline |
| `GET /api/manage/activity/analytics?from&to&department&inactiveDays` | Admin, HR, manager (team) | Aggregated analytics, default last 90 days |
| `POST /api/learning/enroll` with `open: true` | Signed-in employee | Existing route; the flag marks a user-initiated course open |

`type` accepts a single event type or a group: `course`, `lesson`, `assessment` or `other`. Dates are whole UTC days, and both
ends are included. Trainers and employees get 403 from the staff routes. A manager who asks for an employee outside their team
also gets 403.

## Analytics definitions

- **Access** means a course was opened, started or resumed. It is not counted as learning.
- **Abandonment** means the learner started the course in the period, has not completed it, and has had no activity in it for the
  inactivity threshold (30 days by default). It is shown as a share of the learners who started.
- **Attempt rate** is, of the learners who accessed a course in the period, the share who started or submitted one of its
  assessments.
- **Pass rate** is passed attempts divided by submitted attempts.
- **Engagement** is the share of active employees with at least one activity in the period. It is not a productivity, attendance
  or working-time measure.
