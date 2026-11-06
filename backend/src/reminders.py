"""Automated course deadline reminders, delivered through the in-app notifications table.

Every delivery has a row in deadline_reminders with a unique idempotency key, so repeated or overlapping passes cannot
send twice. Keys contain the deadline: changing a deadline makes its reminders due again and retires undelivered ones.
Upcoming reminders are worked out from the current deadline on each pass, not stored ahead of time, so they cannot go stale.

A pass is started by the server's background thread, tools/process_reminders.py, or an administrator. Opening the
notification bell also runs one for that employee as a fallback; nothing depends on it.
"""
import json
import sys
import threading
from contextlib import closing
from datetime import datetime, time, timedelta, timezone

from analytics import assignment_index, progress_index
from database import connect
from deadlines import format_deadline, format_span, parse_utc, portal_timezone, utc_iso
from services import check, notify, now

MAX_ATTEMPTS = 5
RETRY_MINUTES = 5
MAX_INTERVALS = 8
# Sent during the working day rather than at midnight; earlier only when the deadline itself comes first.
DEADLINE_DAY_HOUR = 9


# ---------------------------------------------------------------- settings

def settings(db):
    row = db.execute('SELECT * FROM reminder_settings WHERE id=1').fetchone()
    return {'intervalDays': json.loads(row['intervals_json']), 'deadlineDay': bool(row['deadline_day']), 'overdue': bool(row['overdue']), 'dueSoonDays': row['due_soon_days'],
            'updatedAt': row['updated_at'], 'lastRunAt': row['last_run_at'], 'lastRun': json.loads(row['last_run_json']) if row['last_run_json'] else None}


def due_soon_seconds(db):
    return db.execute('SELECT due_soon_days FROM reminder_settings WHERE id=1').fetchone()[0] * 86400


def save_settings(db, user, data):
    days = data.get('intervalDays')
    check(isinstance(days, list) and len(days) <= MAX_INTERVALS and all(type(d) is int and 1 <= d <= 365 for d in days),
          f'Enter up to {MAX_INTERVALS} reminder intervals, each from 1 to 365 days before the deadline.')
    soon = data.get('dueSoonDays')
    check(type(soon) is int and 1 <= soon <= 90, 'Due Soon must be from 1 to 90 days.')
    check(type(data.get('deadlineDay')) is bool and type(data.get('overdue')) is bool, 'Select whether to send deadline-day and overdue reminders.')
    db.execute('UPDATE reminder_settings SET intervals_json=?,deadline_day=?,overdue=?,due_soon_days=?,updated_by=?,updated_at=? WHERE id=1',
               (json.dumps(sorted(set(days), reverse=True)), int(data['deadlineDay']), int(data['overdue']), soon, user['id'], now()))
    return settings(db)


# ---------------------------------------------------------------- what is due

def deadline_day_at(deadline):
    """The reminder time on the deadline's own day, in the portal timezone."""
    zone = portal_timezone()
    day = deadline.astimezone(zone).date()
    morning = datetime.combine(day, time(DEADLINE_DAY_HOUR), zone)
    return morning if morning < deadline else datetime.combine(day, time(0), zone)


def schedule(deadline, config):
    """(type, scheduled time) for every reminder before a deadline, earliest first."""
    entries = [(f'before_{days}d', deadline - timedelta(days=days)) for days in config['intervalDays']]
    if config['deadlineDay']:
        entries.append(('deadline_day', deadline_day_at(deadline)))
    return sorted(entries, key=lambda entry: entry[1])


def idempotency_key(employee, course, kind, scope):
    return f'deadline:{employee}:{course}:{kind}:{scope}'


def due_reminder(assignment, config, at):
    """The one reminder a deadline calls for now, or None.

    Reminders scheduled before the employee could have received them (a short deadline, a deadline just changed) do not
    apply. After downtime only the latest one is sent, so an employee never receives a backlog.
    """
    deadline = parse_utc(assignment['deadlineAt'])
    if at >= deadline:
        return ('overdue', deadline) if config['overdue'] else None
    opened = max(parse_utc(value) for value in (assignment['assignedAt'], assignment.get('deadlineUpdatedAt') or assignment['assignedAt']))
    due = [entry for entry in schedule(deadline, config) if opened < entry[1] <= at]
    return due[-1] if due else None


def next_reminder(assignment, config, at):
    """When the next reminder falls, for the administrator's view."""
    deadline = parse_utc(assignment['deadlineAt'])
    if at >= deadline:
        return None
    upcoming = [entry[1] for entry in schedule(deadline, config) if entry[1] > at]
    return utc_iso(upcoming[0]) if upcoming else utc_iso(deadline) if config['overdue'] else None


# ---------------------------------------------------------------- messages

def message(kind, course, assignment, progress, at):
    """Notification title and body for one reminder."""
    percent = (progress or {}).get('progress', 0)
    if kind == 'assigned':
        by = f' Complete by {format_deadline(assignment["deadlineAt"], " at ")}.' if assignment['deadlineAt'] else ' Open My Learning to start.'
        label = 'Mandatory training assigned' if assignment['mandatory'] else 'New training assigned'
        return f'{label}: {course}', f'You have been assigned "{course}".{by}'
    due = format_deadline(assignment['deadlineAt'], ' at ')
    remaining = (parse_utc(assignment['deadlineAt']) - at).total_seconds()
    # A pass runs shortly after a reminder falls due: the 3-day reminder should say "3 days", not "2 days, 23 hours".
    if abs(remaining) >= 3600:
        remaining = round(remaining / 3600) * 3600
    if kind == 'overdue':
        return (f'Overdue: {course}', f'Your assigned course "{course}" was due on {due}.\nCurrent progress: {percent}%\nOverdue by {format_span(-remaining)}.\n'
                'The course is still open: please complete it as soon as possible. The late completion will be recorded.')
    title = 'Course Deadline Today' if kind == 'deadline_day' else 'Course Deadline Updated' if kind == 'deadline_changed' else 'Course Deadline Reminder'
    return (title, f'Your assigned course "{course}" must be completed by {due}.\nCurrent progress: {percent}%\nTime remaining: {format_span(remaining)}.\n'
            'Please complete the remaining lessons before the deadline.')


def deliver_in_app(db, employee, kind, title, body, course, key):
    """Create the notification and return its ID; separate so tests can make delivery fail."""
    notify(db, [employee], 'assignment' if kind == 'assigned' else 'deadline', title, body, f'course:{course}', key)
    return db.execute('SELECT id FROM notifications WHERE employee_id=? AND dedupe_key=?', (employee, key)).fetchone()[0]


# ---------------------------------------------------------------- delivery

def send(db, employee, course, assignment, kind, scheduled, title, body, at):
    """Deliver one reminder exactly once. Returns 'sent', 'failed', or 'skipped' (already handled or not yet due for retry)."""
    # An assignment is announced once per assignment; every other reminder belongs to one exact deadline.
    deadline_at = None if kind == 'assigned' else assignment['deadlineAt']
    key = idempotency_key(employee, course, kind, assignment['assignmentId'] if kind == 'assigned' else deadline_at)
    stamp = utc_iso(at)
    row = db.execute('SELECT * FROM deadline_reminders WHERE idempotency_key=?', (key,)).fetchone()
    if row is None:
        created = db.execute('''INSERT OR IGNORE INTO deadline_reminders(employee_id,assignment_id,course_id,reminder_type,deadline_at,scheduled_at,status,idempotency_key,created_at)
            VALUES (?,?,?,?,?,?,'pending',?,?)''', (employee, assignment['assignmentId'], course, kind, deadline_at, utc_iso(scheduled), key, stamp)).rowcount
        if not created:
            return 'skipped'
        attempts = 0
    else:
        retry_due = row['status'] == 'cancelled' or (row['status'] in ('failed', 'pending') and row['attempts'] < MAX_ATTEMPTS and (not row['next_attempt_at'] or parse_utc(row['next_attempt_at']) <= at))
        if not retry_due:
            return 'skipped'
        attempts = row['attempts']
    db.execute('SAVEPOINT reminder_delivery')
    try:
        notification = deliver_in_app(db, employee, kind, title, body, course, key)
        db.execute('RELEASE reminder_delivery')
    except Exception as error:
        db.execute('ROLLBACK TO reminder_delivery')
        db.execute('RELEASE reminder_delivery')
        attempts += 1
        retry = utc_iso(at + timedelta(minutes=RETRY_MINUTES * 2 ** attempts)) if attempts < MAX_ATTEMPTS else None
        db.execute("UPDATE deadline_reminders SET status='failed',attempts=?,next_attempt_at=?,failure_reason=? WHERE idempotency_key=?", (attempts, retry, str(error)[:500] or type(error).__name__, key))
        return 'failed'
    db.execute("UPDATE deadline_reminders SET status='sent',sent_at=?,attempts=?,next_attempt_at=NULL,failure_reason=NULL,notification_id=? WHERE idempotency_key=?", (stamp, attempts + 1, notification, key))
    return 'sent'


def retire_undelivered(db, employee, assigned, progress):
    """Undelivered reminders stop retrying once the course is finished or unassigned, or its deadline has changed."""
    for row in db.execute("SELECT id,course_id,reminder_type,deadline_at FROM deadline_reminders WHERE employee_id=? AND status IN ('pending','failed')", (employee,)).fetchall():
        pair = (employee, row['course_id'])
        a, p = assigned.get(pair), progress.get(pair)
        reason = 'Assignment removed' if a is None else 'Course completed' if p and p['completed'] else 'Deadline changed' if row['deadline_at'] and row['deadline_at'] != a['deadlineAt'] else None
        if reason:
            db.execute("UPDATE deadline_reminders SET status='cancelled',next_attempt_at=NULL,failure_reason=? WHERE id=?", (reason, row['id']))


def already_notified_of_assignment(db, employee, assignment_id):
    """Assignments made before the reminder ledger were announced under the older notification key."""
    return db.execute("SELECT 1 FROM notifications WHERE employee_id=? AND dedupe_key LIKE ?", (employee, f'assigned:{assignment_id}:%')).fetchone() is not None


def process_employee(db, employee, at=None):
    """Send everything due for one employee. The caller owns the transaction."""
    at = at or datetime.now(timezone.utc)
    config = settings(db)
    assigned, progress = assignment_index(db, [employee]), progress_index(db, [employee])
    retire_undelivered(db, employee, assigned, progress)
    counts = {'sent': 0, 'failed': 0, 'skipped': 0}
    titles = {r[0]: r[1] for r in db.execute('SELECT id,title FROM courses')}
    for pair, a in assigned.items():
        course, p = pair[1], progress.get(pair)
        if p and p['completed']:
            continue
        name = titles.get(course, 'Assigned course')
        if not already_notified_of_assignment(db, employee, a['assignmentId']):
            title, body = message('assigned', name, a, p, at)
            counts[send(db, employee, course, a, 'assigned', parse_utc(a['assignedAt']), title, body, at)] += 1
        if a['deadlineAt']:
            due = due_reminder(a, config, at)
            if due:
                title, body = message(due[0].split('_')[0] if due[0].startswith('before_') else due[0], name, a, p, at)
                counts[send(db, employee, course, a, due[0], due[1], title, body, at)] += 1
    return counts


def announce_assignment(db, employee, course, name, assignment, title, at=None):
    """Immediately tell an employee about a new assignment; the ledger stops the next pass repeating it."""
    at = at or datetime.now(timezone.utc)
    _, body = message('assigned', name, assignment, None, at)
    return send(db, employee, course, assignment, 'assigned', at, title, body, at)


def announce_change(db, employee, course, name, assignment, progress, at=None):
    """Immediately tell an employee their deadline changed."""
    at = at or datetime.now(timezone.utc)
    title, body = message('deadline_changed', name, assignment, progress, at)
    return send(db, employee, course, assignment, 'deadline_changed', at, title, body, at)


# ---------------------------------------------------------------- passes

def employees_to_process(db):
    """Active non-admin employees with an assignment, plus anyone with an undelivered reminder to retire."""
    active = {r[0] for r in db.execute("SELECT id FROM candidates WHERE is_active=1 AND role<>'admin'")}
    open_rows = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM deadline_reminders WHERE status IN ('pending','failed')")}
    return sorted(({pair[0] for pair in assignment_index(db)} & active) | open_rows)


def record_run(db, summary, at):
    db.execute('UPDATE reminder_settings SET last_run_at=?,last_run_json=? WHERE id=1', (utc_iso(at), json.dumps(summary)))


def process_all(db, at=None):
    """One pass inside the caller's transaction, for the authenticated administrator endpoint."""
    at = at or datetime.now(timezone.utc)
    summary = {'employees': 0, 'sent': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
    for employee in employees_to_process(db):
        counts = process_employee(db, employee, at)
        summary['employees'] += 1
        for field, value in counts.items():
            summary[field] += value
    record_run(db, summary, at)
    return summary


def run_pass(path, at=None):
    """One pass from the scheduler or command line. Each employee commits separately so the write lock is held briefly."""
    at = at or datetime.now(timezone.utc)
    summary = {'employees': 0, 'sent': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
    with closing(connect(path)) as db:
        for employee in employees_to_process(db):
            try:
                db.execute('BEGIN IMMEDIATE')
                counts = process_employee(db, employee, at)
                db.commit()
            except Exception as error:
                db.rollback()
                summary['errors'] += 1
                print(f'Reminder pass failed for one employee: {type(error).__name__}', file=sys.stderr, flush=True)
                continue
            summary['employees'] += 1
            for field, value in counts.items():
                summary[field] += value
        db.execute('BEGIN IMMEDIATE')
        record_run(db, summary, at)
        db.commit()
    return summary


def preview(path, at=None):
    """What a pass would send at a given time, writing nothing. Used by the command line's --dry-run."""
    at = at or datetime.now(timezone.utc)
    items = []
    with closing(connect(path)) as db:
        config = settings(db)
        titles = {r[0]: r[1] for r in db.execute('SELECT id,title FROM courses')}
        for employee in employees_to_process(db):
            assigned, progress = assignment_index(db, [employee]), progress_index(db, [employee])
            for pair, a in assigned.items():
                if (progress.get(pair) or {}).get('completed') or not a['deadlineAt']:
                    continue
                due = due_reminder(a, config, at)
                if not due:
                    continue
                sent = db.execute("SELECT 1 FROM deadline_reminders WHERE idempotency_key=? AND status='sent'", (idempotency_key(employee, pair[1], due[0], a['deadlineAt']),)).fetchone()
                if not sent:
                    items.append({'employeeId': employee, 'course': titles.get(pair[1], pair[1]), 'type': due[0], 'scheduledAt': utc_iso(due[1])})
    return items


def start_scheduler(path, interval_seconds):
    """Run passes on a daemon thread for as long as the server process lives. A failed pass never stops the loop."""
    stop = threading.Event()

    def loop():
        # A short delay lets the server finish starting; this first pass catches up on anything missed while it was down.
        delay = min(5, interval_seconds)
        while not stop.wait(delay):
            delay = interval_seconds
            try:
                run_pass(path)
            except Exception as error:
                print(f'Reminder pass could not run: {type(error).__name__}', file=sys.stderr, flush=True)

    threading.Thread(target=loop, name='deadline-reminders', daemon=True).start()
    return stop
