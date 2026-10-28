"""Notification events and scoped reminders. No email or external delivery."""
from datetime import datetime, timedelta

from services import notify, now, ready, passed, unlocked, text, check, uid


def observers(db, employee, course=None):
    """Only administrators, HR, and the employee's direct manager receive records."""
    return [r[0] for r in db.execute("SELECT id FROM candidates WHERE is_active=1 AND (role IN ('admin','hr') OR (role='manager' AND id=(SELECT manager_id FROM candidates WHERE id=?))) AND id<>?", (employee, employee))]


def staff_event(db, employee, title, body, key):
    notify(db, observers(db, employee), 'team', title, body, 'reports', key)


def refresh(db, user):
    employee = user['id']
    for a in db.execute("SELECT a.id,a.title,a.max_attempts,COUNT(t.id) AS used,MAX(t.finished_at) AS finished FROM assessments a JOIN assessment_attempts t ON t.assessment_id=a.id AND t.employee_id=? WHERE a.status='published' GROUP BY a.id HAVING SUM(t.status='passed')=0 AND SUM(t.status='in-progress')=0", (employee,)):
        left = max(0, a['max_attempts'] - a['used'])
        notify(db, [employee], 'assessment', f'{left} assessment attempts remaining', a['title'], 'assessments', f'assessment-left:{a["id"]}:{a["used"]}')
        if not left:
            name = db.execute('SELECT full_name FROM candidates WHERE id=?', (employee,)).fetchone()[0]
            staff_event(db, employee, f'Assessment attempts exhausted: {name}', a['title'], f'assessment-exhausted:{employee}:{a["id"]}:{a["used"]}')
    for run in db.execute('SELECT r.*,c.title,c.max_attempts FROM course_runs r JOIN courses c ON c.id=r.course_id WHERE r.candidate_id=? AND r.archived_at IS NULL AND c.status=\'published\'', (employee,)).fetchall():
        for s in range(3):
            attempts = db.execute('SELECT * FROM exam_attempts WHERE run_id=? AND set_index=? ORDER BY attempt_number', (run['id'], s)).fetchall()
            if ready(db, run['id'], s) and unlocked(db, run['id'], s) and not attempts:
                notify(db, [employee], 'exam', f'Module {s+1} exam unlocked', f'{run["title"]}: your videos and exercises are complete. Your exam is ready.', 'courses', f'unlocked:{run["id"]}:{s}')
            if attempts and not passed(db, run['id'], s) and attempts[-1]['status'] != 'in-progress':
                left = max(0, run['max_attempts'] - len(attempts))
                notify(db, [employee], 'exam', f'{left} exam attempts remaining', f'{run["title"]}, Module {s+1}: last attempt {attempts[-1]["status"]}.', 'courses', f'attempts:{attempts[-1]["id"]}')
                if not left:
                    name = db.execute('SELECT full_name FROM candidates WHERE id=?', (employee,)).fetchone()[0]
                    staff_event(db, employee, f'Exam attempts exhausted: {name}', f'{run["title"]}, Module {s+1}.', f'exhausted:{run["id"]}:{s}')
    # Short reminders complement the existing two-day session notice.
    start = datetime.now()
    for session in db.execute("SELECT s.* FROM training_sessions s WHERE s.status='scheduled' AND (s.trainer_id=? OR EXISTS(SELECT 1 FROM session_registrations g WHERE g.session_id=s.id AND g.employee_id=? AND g.status='registered')) AND s.starts_at BETWEEN ? AND ?", (employee, employee, start.strftime('%Y-%m-%dT%H:%M'), (start+timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M'))):
        notify(db, [employee], 'session', f'Starts within 30 minutes: {session["title"]}', f'{session["starts_at"].replace("T", " ")} — {session["location"] or "See session details"}.', 'calendar', f'session-30:{session["id"]}:{session["starts_at"]}')


def announce(db, actor, data):
    check(actor['role'] in ('admin', 'hr'), 'Only administrators and HR can publish announcements.', 403)
    title, body = text(data, 'title', 2, 200), text(data, 'body', 2, 500)
    key = f'announcement:{uid()}'
    notify(db, [r[0] for r in db.execute('SELECT id FROM candidates WHERE is_active=1')], 'announcement', title, body, 'dashboard', key)
    return {'ok': True}


def published(db, course, title):
    notify(db, [r[0] for r in db.execute('SELECT id FROM candidates WHERE is_active=1')], 'announcement', f'New course available: {title}', 'Explore the course catalog to start learning.', 'courses', f'published:{course}')


def resource_added(db, course, title, resource):
    notify(db, [r[0] for r in db.execute('SELECT DISTINCT candidate_id FROM course_runs WHERE course_id=? AND archived_at IS NULL', (course,))], 'material', 'New learning material', title, 'courses', f'resource:{resource}')
