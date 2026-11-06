# Course deadlines and reminders

## For administrators

**Manage Courses → Course Deadline Settings** lists each published course's assignments and every employee's effective deadline, status, progress and reminders. From there, administrators and HR can:

- Assign a course to an employee, department or job role, with a deadline date and time.
- Mark it mandatory (a deadline is then required) or optional.
- Update a deadline. The original is kept and shown, the change is recorded in the Activity Log, and affected employees are told at once.
- Give one employee a different deadline with **Change** on their row.

When several assignments reach one employee, one applies, chosen in this order: mandatory before optional, a deadline before none, individual before department or job role, then the earliest deadline. A manager's optional recommendation therefore cannot weaken mandatory training, and an individual mandatory deadline can extend a department's.

**Reminder schedule and history**, in the same section, sets the reminder intervals and the Due Soon window, and shows recent deliveries. **Run reminders now** runs a pass immediately.

## Training Compliance & Deadline Monitoring

**Training Compliance**, directly under the Admin Dashboard in the sidebar, shows every assigned course in one place. All figures are worked out from current assignment and progress records when the page loads; the page stores nothing and changes nothing.

| Tab | Shows |
| --- | --- |
| Overview | Department chart, status distribution, the most urgent overdue courses and employee records |
| Employee Progress | Employee records on their own, with sorting, paging and row details |
| Department Compliance | Completion rate, courses by status and a table for each department |
| Overdue Training | Every overdue course |
| Reports | CSV and Excel exports, and links to the other learning reports |

Filters (search, department, job role, course, mandatory/optional, status, deadline date range) work together and apply to every tab and to exports. Each active filter is listed under the form and can be removed on its own. **All records for** in a row's details shows one employee.

- **One row per employee and course.** If several assignments reach an employee, the one in force applies, as described above.
- **Summary cards add up to the total.** A Due Soon course counts as In Progress or Not Started and carries a Due Soon label.
- **Completed** is completed on time plus completed late. The status chart shows those two separately, so its segments add up to the total.
- **Overall completion rate** is completed on time plus completed late, divided by all assignments shown.
- **Pending**, in the department figures, means assigned, not completed and not yet overdue.
- **Overdue time** runs from the deadline now in force. The original deadline is shown, with the new one if it changed. Mandatory courses are highlighted and listed first.
- **Deadline date filters** use the portal timezone. A course with no deadline falls outside any date range.
- **Courses and accounts counted:** published courses and active non-administrator employees, as on Course Deadline Settings.

**Export CSV** and **Export Excel** download every record matching the filters, in the current sort order, not only the current page. Dates are in the portal timezone, and each export is recorded in the Activity Log.

| Role | Access |
| --- | --- |
| Administrator, HR | The whole organisation |
| Manager | Direct reports only, including filter choices and exports |
| Trainer, Employee | None; the server refuses with 403 |

Employee ID is the account's ID in the portal, because accounts have no separate HR employee number. Tables show its first 8 characters; a row's details and exports show all of it, and search matches any part of it.

## Rules

Deadlines are stored in UTC. They are entered and displayed in one portal timezone, `Asia/Kolkata` unless `LMS_TIMEZONE` says otherwise; there is no per-employee timezone. The server's clock decides status; the browser's countdown only keeps the page current between loads.

| Status | Condition |
| --- | --- |
| Not Started | Not started, and the deadline is outside the Due Soon window |
| In Progress | Started, and the deadline is outside the Due Soon window |
| Due Soon | Not completed, and the deadline is within the window (default 7 days) |
| Overdue | Not completed, and the deadline has passed |
| Completed On Time | Completed at or before the deadline in force at that moment |
| Completed Late | Completed after the deadline in force at that moment |

- Only admin, HR and managers (for optional training of direct reports) can change deadlines, enforced on the server.
- Completion is set only by the server, after the existing lesson and assessment requirements are met.
- Overdue courses stay open so that employees can finish them.
- A late completion stays late if the deadline is extended afterwards.
- A course completed before it was assigned counts as completed on time, and no reminders are sent for it.
- A date-only deadline from before this feature lasts until 23:59:59 on that date in the portal timezone.

## Reminders

| Trigger | Sent |
| --- | --- |
| Course assigned | Immediately; new members of a department or job role on the next pass |
| Deadline changed | Immediately |
| 7, 3 and 1 days before (configurable) | At that time |
| Deadline day (can be turned off) | 9:00 AM portal time, or midnight if the deadline is before 9:00 AM |
| Overdue (can be turned off) | The first pass after the deadline |

Reminders are in-app, through the notification bell. No email service is configured, so none is sent; the `channel` column of `deadline_reminders` leaves room for one.

- **Short deadlines:** a reminder whose time had already passed when the deadline was set is skipped.
- **Downtime:** only the most recent reminder that is due is sent, not a backlog.
- **Completed courses:** no further reminders.
- **Duplicates:** every delivery has a unique idempotency key in `deadline_reminders`, committed in the same transaction as its notification. Passes can repeat or overlap safely.
- **Deadline changes:** the key includes the deadline, so reminders fall due again for the new one, and undelivered reminders for the old one are cancelled.
- **Failures:** the reason is recorded and delivery is retried with increasing delay, up to 5 attempts.

## Running the reminder process

The backend is a long-running Python server with SQLite on local disk, so it runs reminders itself on a background thread, every 5 minutes by default (`LMS_REMINDER_INTERVAL_SECONDS`; 0 turns it off). This needs no one to have the portal open, but it does need the server process to be running.

To run reminders when the server may not be running, schedule the command on the same machine. It is safe to use alongside the thread.

```powershell
npm run reminders                                          # send what is due now
python backend/tools/process_reminders.py --dry-run        # list what is due, sending nothing
python backend/tools/process_reminders.py --dry-run --now 2026-11-08T12:30:00Z
```

```powershell
# Windows Task Scheduler, every 15 minutes
schtasks /Create /SC MINUTE /MO 15 /TN "ShimentoX Reminders" /TR "python C:\path\to\backend\tools\process_reminders.py"
```

```text
# cron
*/15 * * * * cd /path/to/project && python backend/tools/process_reminders.py
```

Set `LMS_DB_PATH` for the scheduled task if the database is not in its default location. The exit code is 1 if any reminder failed.

**Serverless or static hosting:** this backend cannot run there. It needs a persistent process and persistent disk for SQLite, and `.openai/hosting.json` serves only the static frontend. Deploy to a host that runs `python backend/server.py` with a persistent disk; the thread then works with no further setup.

## Upgrading

The database upgrades itself to schema version 9 the next time the server starts, adding columns and tables and keeping all existing records. Back up `backend/data/lms.sqlite3` first, then restart the server.
