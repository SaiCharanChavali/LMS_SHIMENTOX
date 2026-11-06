"""Course deadline time rules: UTC storage, portal-timezone display, and deadline status.

Timestamps are stored as UTC ISO strings ('2026-11-08T12:30:00.000Z'), the same format as services.now(), and are
always compared on the server. This module uses only the standard library so database.py can import it.
"""
import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = 'Asia/Kolkata'
# Windows has no system timezone database, and the portal must not require the optional tzdata package.
IST = timezone(timedelta(hours=5, minutes=30), 'IST')
STATUS_LABELS = {'not_started': 'Not Started', 'in_progress': 'In Progress', 'due_soon': 'Due Soon', 'overdue': 'Overdue',
                 'completed_on_time': 'Completed On Time', 'completed_late': 'Completed Late'}


def portal_timezone():
    """Deadlines are entered and displayed in one portal timezone, set by LMS_TIMEZONE."""
    name = os.environ.get('LMS_TIMEZONE', '').strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:
        if name != DEFAULT_TIMEZONE:
            raise ValueError(f'LMS_TIMEZONE is not a known timezone: {name}')
        return IST


def timezone_label(at=None):
    return (at or datetime.now(timezone.utc)).astimezone(portal_timezone()).tzname()


def utc_iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def parse_utc(value):
    """Parse a stored or submitted timestamp. A timestamp with no offset is read in the portal timezone."""
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=portal_timezone())


def end_of_day(due_date):
    """A date-only deadline lasts until the end of that day in the portal timezone."""
    return utc_iso(datetime.combine(date.fromisoformat(due_date), time(23, 59, 59), portal_timezone()))


def local_date(deadline_at):
    return parse_utc(deadline_at).astimezone(portal_timezone()).date().isoformat()


def local_input(deadline_at):
    """The value for a datetime-local field, in the portal timezone."""
    return parse_utc(deadline_at).astimezone(portal_timezone()).strftime('%Y-%m-%dT%H:%M') if deadline_at else ''


def format_deadline(deadline_at, joiner=', '):
    """'8 November 2026, 6:00 PM'; built by hand because strftime has no portable unpadded day or hour."""
    local = parse_utc(deadline_at).astimezone(portal_timezone())
    hour = local.hour % 12 or 12
    return f'{local.day} {local.strftime("%B %Y")}{joiner}{hour}:{local.minute:02d} {"AM" if local.hour < 12 else "PM"}'


def format_span(seconds):
    """'2 days, 4 hours'. Only the two largest units are shown."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return 'less than a minute'
    days, hours, minutes = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    parts = [(days, 'day'), (hours, 'hour')] if days else [(hours, 'hour'), (minutes, 'minute')] if hours else [(minutes, 'minute'), (0, '')]
    return ', '.join(f'{n} {unit}{"" if n == 1 else "s"}' for n, unit in parts if n)


def deadline_status(progress, assignment, due_soon_seconds, at=None):
    """Status of one employee-course pair. `at` is server time; the browser's clock never decides this."""
    at = at or datetime.now(timezone.utc)
    deadline = (assignment or {}).get('deadlineAt')
    if progress and progress['completed']:
        # The deadline in force at completion is the record. Extending a deadline later does not rewrite it.
        reference = progress.get('deadlineAtCompletion') or deadline
        late = reference and progress['completedAt'] and parse_utc(progress['completedAt']) > parse_utc(reference)
        return 'completed_late' if late else 'completed_on_time'
    if deadline:
        remaining = (parse_utc(deadline) - at).total_seconds()
        if remaining <= 0:
            return 'overdue'
        if remaining <= due_soon_seconds:
            return 'due_soon'
    return 'in_progress' if progress and progress['started'] else 'not_started'


def deadline_view(progress, assignment, due_soon_seconds, at=None):
    """Read-only deadline details for the browser; None when the course has no deadline for this employee."""
    deadline = (assignment or {}).get('deadlineAt')
    if not deadline:
        return None
    at = at or datetime.now(timezone.utc)
    status = deadline_status(progress, assignment, due_soon_seconds, at)
    completed = progress.get('completedAt') if progress and progress['completed'] else None
    return {'at': deadline, 'display': format_deadline(deadline), 'timezone': timezone_label(at), 'status': status, 'label': STATUS_LABELS[status],
            'remainingSeconds': int((parse_utc(deadline) - at).total_seconds()), 'dueSoonSeconds': due_soon_seconds, 'started': bool(progress and progress['started']),
            'completedAt': completed, 'completedDisplay': format_deadline(completed) if completed else None}
