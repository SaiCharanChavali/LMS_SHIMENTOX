# In-app notifications

The bell shows an unread count, event category, message, timestamp, and a link to the relevant portal page. Opening a notification marks it read. Mark all read applies only to the signed-in account. The panel displays the latest 50 records; older records remain in SQLite.

Employees receive course/path assignments, upcoming and overdue deadlines, weekly reminders for courses inactive for seven days, unlocked module exams, exam results and terminations, remaining exam/assessment attempts, certificates, new resources for enrolled courses, new published courses, password changes, and session updates/reminders. Session reminders include the existing two-day notice and a notice within 30 minutes of the scheduled start. Session times follow the portal's existing server-local scheduling convention.

Administrators, HR, and direct managers receive first-login, course completion/certificate, overdue training, and exhausted-attempt alerts for the employees they oversee. Managers receive only their direct reports' events. Trainers receive reminders for sessions they lead. Administrators and HR can expand **Post an announcement** inside the notification panel and publish a title and message to active accounts.

Events are stored with unique per-account keys to prevent duplicate reminders. Deadline, inactivity, and session reminders refresh when notifications are fetched; this is in-app delivery and does not use a background scheduler, email, or browser push. Course-progress events are also generated as learning actions complete. No database reset or new migration is required.
