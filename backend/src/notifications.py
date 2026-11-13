"""Notification events and scoped reminders. No email or external delivery."""
from services import notify, now, text, check, uid


def observers(db, employee, course=None):
    """Only administrators, HR, and the employee's direct manager receive records."""
    # Two indexed lookups (by role, then the employee's manager) instead of scanning every account.
    return [r[0] for r in db.execute("""SELECT id FROM candidates WHERE role IN ('admin','hr') AND is_active=1 AND id<>?
        UNION SELECT m.id FROM candidates e JOIN candidates m ON m.id=e.manager_id WHERE e.id=? AND m.role='manager' AND m.is_active=1 AND m.id<>?""", (employee, employee, employee))]


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
    # Module exams exist only in 3-module courses (lesson courses cannot record videos, exercises or exams), so only those
    # runs are checked, with their exam, video and exercise records read in three queries instead of several per module.
    runs = db.execute("SELECT r.*,c.title,c.max_attempts FROM course_runs r JOIN courses c ON c.id=r.course_id WHERE r.candidate_id=? AND r.archived_at IS NULL AND c.status='published' AND c.format='modules'", (employee,)).fetchall()
    if runs:
        ids = [run['id'] for run in runs]
        marks = ','.join('?' * len(ids))
        exams, videos, exercises = {}, {}, {}
        for attempt in db.execute(f'SELECT * FROM exam_attempts WHERE run_id IN ({marks}) ORDER BY run_id,set_index,attempt_number', ids):
            exams.setdefault((attempt['run_id'], attempt['set_index']), []).append(attempt)
        for r in db.execute(f'SELECT run_id,video_index FROM video_progress WHERE run_id IN ({marks}) AND completed_at IS NOT NULL', ids):
            videos[(r[0], r[1] // 2)] = videos.get((r[0], r[1] // 2), 0) + (r[1] < 6)
        for r in db.execute(f'SELECT run_id,set_index,COUNT(DISTINCT exercise_index) FROM exercise_attempts WHERE run_id IN ({marks}) AND passed=1 GROUP BY run_id,set_index', ids):
            exercises[(r[0], r[1])] = r[2]
        # Same rules as services.ready, services.passed and services.unlocked.
        is_ready = lambda run_id, s: videos.get((run_id, s), 0) == 2 and exercises.get((run_id, s), 0) == 2
        is_passed = lambda run_id, s: any(x['status'] == 'passed' for x in exams.get((run_id, s), ()))
        is_unlocked = lambda run_id, s: s == 0 or (is_ready(run_id, s - 1) and is_passed(run_id, s - 1))
        name = None
        for run in runs:
            for s in range(3):
                attempts = exams.get((run['id'], s), [])
                if is_ready(run['id'], s) and is_unlocked(run['id'], s) and not attempts:
                    notify(db, [employee], 'exam', f'Module {s+1} exam unlocked', f'{run["title"]}: your videos and exercises are complete. Your exam is ready.', 'courses', f'unlocked:{run["id"]}:{s}')
                if attempts and not is_passed(run['id'], s) and attempts[-1]['status'] != 'in-progress':
                    left = max(0, run['max_attempts'] - len(attempts))
                    notify(db, [employee], 'exam', f'{left} exam attempts remaining', f'{run["title"]}, Module {s+1}: last attempt {attempts[-1]["status"]}.', 'courses', f'attempts:{attempts[-1]["id"]}')
                    if not left:
                        name = name or db.execute('SELECT full_name FROM candidates WHERE id=?', (employee,)).fetchone()[0]
                        staff_event(db, employee, f'Exam attempts exhausted: {name}', f'{run["title"]}, Module {s+1}.', f'exhausted:{run["id"]}:{s}')
    # Session reminders (24 hours, 1 hour and 15 minutes before) are sent by live_training.process.


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
