"""Account and learning rules. All candidate identifiers come from the session."""
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone

from database import COURSE_ID, public_curriculum
from security import password_hash, verify_password, token, token_hash


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def uid():
    return str(uuid.uuid4())


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def check(condition, message, status=400):
    if not condition:
        raise APIError(status, message)


def text(data, field, minimum=1, maximum=254):
    value = data.get(field)
    check(isinstance(value, str), f'{field} is required.')
    value = value.strip() if field != 'password' and field != 'currentPassword' else value
    check(minimum <= len(value) <= maximum, f'{field} must contain {minimum}–{maximum} characters.')
    return value


def index(data, key, maximum):
    value = data.get(key)
    check(type(value) is int and 0 <= value <= maximum, f'Invalid {key}.')
    return value


ROLES = ('admin', 'hr', 'trainer', 'manager', 'employee')
# Backend permission matrix. Managers and trainers are further scoped to their own team or courses.
PERMISSIONS = {
    'users.manage': {'admin', 'hr'},
    'org.manage': {'admin', 'hr'},
    'courses.manage': {'admin', 'hr', 'trainer'},
    'courses.assign': {'admin', 'hr', 'manager'},
    'paths.manage': {'admin', 'hr', 'trainer'},
    'skills.manage': {'admin', 'hr'},
    'competencies.manage': {'admin', 'hr', 'manager'},
    'skills.record': {'admin', 'hr', 'manager'},
    'assessments.manage': {'admin', 'hr', 'trainer'},
    'sessions.manage': {'admin', 'hr', 'trainer'},
    'reports.view': {'admin', 'hr', 'manager', 'trainer'},
    'audit.view': {'admin'},
}


def allowed(user, permission):
    return user['role'] in PERMISSIONS[permission]


def require(user, permission):
    check(allowed(user, permission), 'You do not have permission for this action.', 403)


def candidate_view(row):
    keys = row.keys()
    return {'id': row['id'], 'name': row['full_name'], 'email': row['email'], 'createdAt': row['created_at'], 'role': row['role'], 'mustChangePassword': bool(row['must_change_password']), 'active': bool(row['is_active']),
            'departmentId': row['department_id'] if 'department_id' in keys else None, 'jobRoleId': row['job_role_id'] if 'job_role_id' in keys else None,
            'managerId': row['manager_id'] if 'manager_id' in keys else None, 'jobTitle': row['job_title'] if 'job_title' in keys else ''}


def can_view_course(db, user, course):
    """Published courses are open to every employee unless limited to one department.
    Course managers, members of that department, and employees assigned the course always have access."""
    if course['status'] != 'published':
        return False
    if course['visibility'] != 'department' or not course['department_id']:
        return True
    if user['role'] in ('admin', 'hr') or user['id'] in (course['trainer_id'], course['created_by']) or user['department_id'] == course['department_id']:
        return True
    return db.execute("SELECT 1 FROM course_assignments WHERE course_id=? AND ((target_type='employee' AND target_id=?) OR (target_type='department' AND target_id=?) OR (target_type='job_role' AND target_id=?))",
                      (course['id'], user['id'], user['department_id'] or '', user['job_role_id'] or '')).fetchone() is not None


def notify(db, employees, kind, title, body, link, key):
    """Store one in-app notification per employee; the dedupe key makes repeat calls harmless."""
    for employee in employees:
        db.execute('INSERT OR IGNORE INTO notifications(employee_id,kind,title,body,link,dedupe_key,created_at) VALUES (?,?,?,?,?,?,?)', (employee, kind, title[:200], body[:500], link, key, now()))


def auth_event(db, candidate, email, event, ip):
    db.execute('INSERT INTO auth_events(candidate_id,email,event,ip_address,created_at,timestamp) VALUES (?,?,?,?,?,?)', (candidate, email, event, ip, now(), time.time()))


def create_run(db, candidate, course_id=COURSE_ID):
    number = db.execute('SELECT COALESCE(MAX(run_number),0)+1 FROM course_runs WHERE candidate_id=? AND course_id=?', (candidate, course_id)).fetchone()[0]
    run = uid()
    db.execute('INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at) VALUES (?,?,?,?,?)', (run, candidate, course_id, number, now()))
    return run


def current_run(db, candidate, expected=None, course_id=COURSE_ID):
    if expected is not None:
        row=db.execute('SELECT * FROM course_runs WHERE id=? AND candidate_id=? AND archived_at IS NULL',(expected,candidate)).fetchone()
        check(row is not None,'The course run changed or is unavailable. Reload before continuing.',409)
    else:
        row=db.execute('SELECT * FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL',(candidate,course_id)).fetchone()
        check(row is not None,'Course enrollment was not found.',404)
    return row


def authenticate(db, data, ip, register=False):
    check(not register, 'Accounts are created by an administrator. Contact your admin for login details.', 403)
    email = text(data, 'email').casefold()
    password = text(data, 'password', 8 if register else 1, 128)
    check(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) is not None, 'Enter a valid email address.')
    failures = db.execute("SELECT COUNT(*) FROM auth_events WHERE event='login_failed' AND timestamp>? AND (ip_address=? OR email=?)", (time.time() - 900, ip, email)).fetchone()[0]
    check(failures < 10, 'Too many sign-in attempts. Please try again in 15 minutes.', 429)
    row = db.execute('SELECT * FROM candidates WHERE email=?', (email,)).fetchone()
    valid = verify_password(password, row['password_hash']) if row else verify_password(password, DUMMY_HASH)
    if not valid or not row['is_active']:
        auth_event(db, row['id'] if row else None, email, 'login_failed', ip)
        db.commit()
        raise APIError(401, 'Email or password is incorrect or the account is unavailable.')
    if not row['last_login_at']:
        from notifications import staff_event
        staff_event(db, row['id'], f'First sign-in: {row["full_name"]}', 'This user signed in for the first time.', f'first-login:{row["id"]}')
    db.execute('UPDATE candidates SET last_login_at=? WHERE id=?', (now(), row['id']))
    auth_event(db, row['id'], email, 'login', ip)
    raw, csrf = token(), token()
    lifetime = 30 * 86400 if data.get('remember') is True else 8 * 3600
    db.execute('DELETE FROM sessions WHERE expires_at<=?', (time.time(),))
    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (token_hash(raw), row['id'], csrf, now(), time.time() + lifetime))
    return {'user': candidate_view(row), 'csrfToken': csrf}, raw, lifetime


def ready(db, run, s):
    videos = db.execute('SELECT COUNT(*) FROM video_progress WHERE run_id=? AND video_index IN (?,?) AND completed_at IS NOT NULL', (run, s * 2, s * 2 + 1)).fetchone()[0]
    exercises = db.execute('SELECT COUNT(DISTINCT exercise_index) FROM exercise_attempts WHERE run_id=? AND set_index=? AND passed=1', (run, s)).fetchone()[0]
    return videos == 2 and exercises == 2


def passed(db, run, s):
    return db.execute("SELECT 1 FROM exam_attempts WHERE run_id=? AND set_index=? AND status='passed'", (run, s)).fetchone() is not None


def unlocked(db, run, s):
    return s == 0 or (ready(db, run, s - 1) and passed(db, run, s - 1))


def expire_exams(db, run, reason=None):
    from checkpoints import expire
    expire(db, run, reason)
    if reason:
        db.execute("UPDATE exam_attempts SET status='terminated',reason=?,finished_at=? WHERE run_id=? AND status='in-progress'", (reason, now(), run))
    else:
        db.execute("UPDATE exam_attempts SET status='terminated',reason='Time expired. This attempt has ended.',finished_at=? WHERE run_id=? AND status='in-progress' AND deadline<=?", (now(), run, time.time()))


def attempt_view(row):
    return {'id': row['id'], 'status': row['status'], 'startedAt': row['started_at'], 'deadline': row['deadline'] * 1000, 'finishedAt': row['finished_at'], 'score': row['score'], 'reason': row['reason'], 'attemptNumber': row['attempt_number']}


def candidate_certificates(db, candidate):
    return [{'id':r['id'],'runId':r['run_id'],'name':r['candidate_name'],'courseTitle':r['course_title'],'courseId':r['course_id'],'completedAt':r['issued_at']} for r in db.execute('SELECT c.*,r.course_id FROM certificates c JOIN course_runs r ON r.id=c.run_id WHERE r.candidate_id=? ORDER BY c.issued_at,c.id',(candidate,))]


def bundle(db, candidate, course_id=COURSE_ID):
    from checkpoints import views
    run = current_run(db, candidate, course_id=course_id)
    expire_exams(db, run['id'])
    videos = {str(r['video_index']): {'watched': r['watched_seconds'], 'complete': r['completed_at'] is not None} for r in db.execute('SELECT * FROM video_progress WHERE run_id=?', (run['id'],))}
    exercises = {f"{r['set_index']}-{r['exercise_index']}": True for r in db.execute('SELECT DISTINCT set_index,exercise_index FROM exercise_attempts WHERE run_id=? AND passed=1', (run['id'],))}
    attempts = [[], [], []]
    for row in db.execute('SELECT * FROM exam_attempts WHERE run_id=? ORDER BY set_index,attempt_number', (run['id'],)):
        attempts[row['set_index']].append(attempt_view(row))
    awards = candidate_certificates(db,candidate)
    course = db.execute('SELECT format,(SELECT COUNT(*) FROM course_lessons WHERE course_id=?) FROM courses WHERE id=?', (run['course_id'], run['course_id'])).fetchone()
    lessons = {r['lesson_id']: {'completed': True, 'completedAt': r['completed_at'], 'response': r['response'], 'score': r['score']} for r in db.execute('SELECT * FROM lesson_progress WHERE run_id=?', (run['id'],))}
    watch = {r['lesson_id']: {'position': r['position_seconds'], 'watched': r['watched_seconds']} for r in db.execute('SELECT * FROM lesson_watch WHERE run_id=?', (run['id'],))}
    return {'version': 3, 'run': {'id': run['id'], 'courseId':run['course_id'], 'runNumber': run['run_number'], 'videos': videos, 'exercises': exercises, 'attempts': attempts, 'completedAt': run['completed_at'],
                                  'format': course[0], 'lessons': lessons, 'lessonTotal': course[1], 'watch': watch, 'activity': activity_state(db, run['id']),
                                  'checkpoints': views(db, run['id'], course_id),
                                  'codeDrafts': {r['lesson_id']: r['code'] for r in db.execute('SELECT lesson_id,code FROM lesson_code_drafts WHERE run_id=?', (run['id'],))},
                                  'lastLessonId': run['last_lesson_id']}, 'certificates': awards}


def activity_state(db, run_id):
    """Attempts, best score and feedback for the latest submission of each interactive exercise in a run."""
    from development import score_activity  # Local import: development builds on this module.
    state = {}
    for row in db.execute('''SELECT a.lesson_id,a.answers_json,a.score,a.passed,a.submitted_at,l.activity_json,
            (SELECT COUNT(*) FROM lesson_activity_attempts b WHERE b.run_id=a.run_id AND b.lesson_id=a.lesson_id) AS attempts,
            (SELECT MAX(score) FROM lesson_activity_attempts b WHERE b.run_id=a.run_id AND b.lesson_id=a.lesson_id) AS best
        FROM lesson_activity_attempts a JOIN course_lessons l ON l.id=a.lesson_id WHERE a.run_id=?
        AND a.rowid=(SELECT MAX(b.rowid) FROM lesson_activity_attempts b WHERE b.run_id=a.run_id AND b.lesson_id=a.lesson_id)''', (run_id,)):
        answers = json.loads(row['answers_json'])
        _, results = score_activity(json.loads(row['activity_json']), answers)
        state[row['lesson_id']] = {'attempts': row['attempts'], 'bestScore': row['best'], 'lastScore': row['score'], 'passed': bool(row['passed']),
                                   'submittedAt': row['submitted_at'], 'answers': answers, 'results': results}
    return state


def post_assessment_passed(db, candidate, run):
    """A published post-training assessment linked to the course must be passed during this run."""
    row = db.execute("SELECT a.id FROM course_runs r JOIN courses c ON c.id=r.course_id JOIN assessments a ON a.id=c.post_assessment_id AND a.status='published' WHERE r.id=?", (run,)).fetchone()
    if row is None:
        return True
    started = db.execute('SELECT started_at FROM course_runs WHERE id=?', (run,)).fetchone()[0]
    return db.execute("SELECT 1 FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status='passed' AND finished_at>=?", (row['id'], candidate, started)).fetchone() is not None


def threshold_met(db, run_id, lesson):
    row = db.execute('SELECT watched_seconds FROM lesson_watch WHERE run_id=? AND lesson_id=?', (run_id, lesson['id'])).fetchone()
    return row is not None and row[0] >= lesson['video_seconds'] * lesson['completion_percent'] / 100 - 0.5


def learning_complete(db, run):
    from checkpoints import all_passed
    course = db.execute('''SELECT k.format,(SELECT COUNT(*) FROM course_lessons l WHERE l.course_id=k.id) AS total,
        (SELECT COUNT(*) FROM lesson_progress p JOIN course_lessons l ON l.id=p.lesson_id WHERE p.run_id=? AND l.course_id=k.id) AS done
        FROM course_runs r JOIN courses k ON k.id=r.course_id WHERE r.id=?''', (run, run)).fetchone()
    if course['format'] == 'lessons':
        return course['total'] > 0 and course['done'] >= course['total'] and all_passed(db, run)
    return all(ready(db, run, s) and passed(db, run, s) for s in range(3))


def issue_certificate(db, candidate, run):
    if learning_complete(db, run) and post_assessment_passed(db, candidate, run):
        name = db.execute('SELECT full_name FROM candidates WHERE id=?', (candidate,)).fetchone()[0]
        timestamp = now()
        title = db.execute('SELECT title FROM courses WHERE id=(SELECT course_id FROM course_runs WHERE id=?)',(run,)).fetchone()[0]
        db.execute('UPDATE course_runs SET completed_at=COALESCE(completed_at,?) WHERE id=?', (timestamp, run))
        # One certificate per qualifying run (UNIQUE run_id); notify only when a new one is created.
        if db.execute('INSERT OR IGNORE INTO certificates VALUES (?,?,?,?,?)', (uid(), run, name, title, timestamp)).rowcount:
            from notifications import staff_event
            staff_event(db, candidate, f'Course completed: {name}', f'{title}: a completion certificate was earned.', f'team-certificate:{run}')
            notify(db, [candidate], 'certificate', f'Certificate earned: {title}', 'Your completion certificate is ready to view and print.', 'certificates', f'certificate:{run}')


def grade(db, s, kind, e, answers, course_id=COURSE_ID):
    questions = db.execute('SELECT * FROM assessment_questions WHERE course_id=? AND set_index=? AND kind=? AND exercise_index=? ORDER BY question_index', (course_id, s, kind, e)).fetchall()
    check(isinstance(answers, list) and len(answers) == len(questions), 'Answer every question before submitting.')
    check(all(type(a) is int and 0 <= a < len(json.loads(q['options_json'])) for a, q in zip(answers, questions)), 'Invalid answer selection.')
    details = [{'correct': answer == question['correct_option'], 'explanation': question['explanation']} for answer, question in zip(answers, questions)]
    return sum(d['correct'] for d in details), details


def learning_action(db, candidate, action, data):
    import checkpoints
    check(isinstance(data.get('runId'), str), 'Course run ID is required.')
    run = current_run(db, candidate, data.get('runId'))
    run_id = run['id']
    if action not in ('exam-finish', 'checkpoint-finish'):
        check(db.execute('SELECT status FROM courses WHERE id=?',(run['course_id'],)).fetchone()[0]=='published','This course is not currently published.',403)
    expire_exams(db, run_id)
    course_format = db.execute('SELECT format FROM courses WHERE id=?', (run['course_id'],)).fetchone()[0]
    check(course_format == 'modules' or action in ('resume', 'restart', 'lesson', 'lesson-open', 'lesson-video', 'lesson-activity', 'lesson-draft', 'lesson-quiz', 'checkpoint-start', 'checkpoint-finish'), 'This activity does not apply to lesson-based courses.', 409)
    if action not in ('checkpoint-finish', 'resume', 'restart', 'lesson-open'):
        check(db.execute("SELECT 1 FROM checkpoint_attempts WHERE run_id=? AND status='in-progress'", (run_id,)).fetchone() is None,
              'Finish the active assignment before continuing lessons.', 409)
    extra = {}
    lesson = None
    if action in ('lesson', 'lesson-open', 'lesson-video', 'lesson-activity', 'lesson-draft', 'lesson-quiz'):
        check(course_format == 'lessons', 'Lessons in this course are completed through its modules.', 409)
        lesson = db.execute('SELECT * FROM course_lessons WHERE id=? AND course_id=?', (data.get('lessonId'), run['course_id'])).fetchone()
        check(lesson is not None, 'Lesson was not found.', 404)
        check(checkpoints.lesson_unlocked(db, run_id, run['course_id'], lesson['id']), 'Pass the previous assignment to unlock this module.', 403)
    if action == 'lesson-open':
        # Remember the lesson the employee is reading so the course reopens there.
        db.execute('UPDATE course_runs SET last_lesson_id=? WHERE id=?', (lesson['id'], run_id))
    elif action == 'checkpoint-start':
        check(course_format == 'lessons', 'This course has no lesson assignments.', 409)
        extra = checkpoints.start(db, run, data)
    elif action == 'checkpoint-finish':
        extra = checkpoints.finish(db, run, data)
    elif action == 'lesson-draft':
        check(bool(lesson['practice_json']), 'This lesson has no coding practice.', 409)
        code = data.get('code')
        check(isinstance(code, str) and len(code) <= 20000, 'Code must contain at most 20,000 characters.')
        db.execute('''INSERT INTO lesson_code_drafts VALUES (?,?,?,?) ON CONFLICT(run_id,lesson_id)
            DO UPDATE SET code=excluded.code,updated_at=excluded.updated_at''', (run_id, lesson['id'], code, now()))
    elif action == 'lesson-quiz':
        questions = json.loads(lesson['quiz_json']) if lesson['quiz_json'] else []
        check(bool(questions), 'This lesson has no knowledge check.', 409)
        answers = data.get('answers')
        check(isinstance(answers, list) and len(answers) == len(questions), 'Answer every knowledge-check question.')
        check(all(type(a) is int and 0 <= a < len(q[1]) for a, q in zip(answers, questions)), 'Invalid knowledge-check answer.')
        correct = [a == q[2] for a, q in zip(answers, questions)]
        score = sum(correct)
        db.execute('INSERT INTO lesson_quiz_attempts VALUES (?,?,?,?,?,?)', (uid(), run_id, lesson['id'], json.dumps(answers), score, now()))
        if all(correct):
            db.execute('''INSERT INTO lesson_progress(run_id,lesson_id,completed_at,score) VALUES (?,?,?,100)
                ON CONFLICT(run_id,lesson_id) DO UPDATE SET score=100''', (run_id, lesson['id'], now()))
        extra['quizResult'] = {'score': score, 'total': len(questions), 'passed': all(correct), 'correct': correct}
    elif action == 'lesson-video':
        check(not lesson['quiz_json'], 'Complete this module through its knowledge check.', 409)
        # Watch reports come from the browser; watched time is capped at the video length and never decreases.
        position, watched = data.get('position'), data.get('watched')
        check(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (position, watched)), 'Invalid video progress.')
        limit = lesson['video_seconds'] or 36000
        db.execute('''INSERT INTO lesson_watch(run_id,lesson_id,position_seconds,watched_seconds,updated_at) VALUES (?,?,?,?,?)
            ON CONFLICT(run_id,lesson_id) DO UPDATE SET position_seconds=excluded.position_seconds,watched_seconds=MAX(watched_seconds,excluded.watched_seconds),updated_at=excluded.updated_at''',
                   (run_id, lesson['id'], min(position, limit), min(watched, limit), now()))
        if lesson['video_seconds'] and not lesson['activity_json'] and not lesson['exercise'] and threshold_met(db, run_id, lesson):
            if db.execute('INSERT OR IGNORE INTO lesson_progress(run_id,lesson_id,completed_at) VALUES (?,?,?)', (run_id, lesson['id'], now())).rowcount:
                extra['lessonCompleted'] = lesson['id']
    elif action == 'lesson-activity':
        from development import score_activity  # Local import: development builds on this module.
        check(bool(lesson['activity_json']), 'This lesson has no interactive exercise.', 409)
        activity = json.loads(lesson['activity_json'])
        answers = data.get('answers')
        check(isinstance(answers, list) and len(answers) == len(activity['tasks']) and all(isinstance(a, str) and 1 <= len(a.strip()) <= 3000 for a in answers),
              'Write a prompt for every task (up to 3000 characters each).')
        answers = [a.strip() for a in answers]
        score, results = score_activity(activity, answers)
        activity_passed = score >= activity['passPercent']
        db.execute('INSERT INTO lesson_activity_attempts(id,run_id,lesson_id,answers_json,score,passed,submitted_at) VALUES (?,?,?,?,?,?,?)', (uid(), run_id, lesson['id'], json.dumps(answers), score, int(activity_passed), now()))
        if activity_passed:
            # The completion keeps the best passing score; a later lower score never reduces it.
            db.execute('''INSERT INTO lesson_progress(run_id,lesson_id,completed_at,score) VALUES (?,?,?,?)
                ON CONFLICT(run_id,lesson_id) DO UPDATE SET score=MAX(COALESCE(score,0),excluded.score)''', (run_id, lesson['id'], now(), score))
        extra['activityResult'] = {'score': score, 'passed': activity_passed, 'passPercent': activity['passPercent'], 'results': results}
    elif action == 'lesson':
        from development import video_available
        check(not lesson['activity_json'], 'Submit the exercise to complete this lesson.', 409)
        check(not lesson['quiz_json'], 'Pass the knowledge check to complete this module.', 409)
        required = lesson['video_seconds'] and video_available(lesson['video_url'])
        check(not required or threshold_met(db, run_id, lesson), 'Watch at least %d%% of the video to complete this lesson.' % lesson['completion_percent'], 409)
        response = data.get('response') or ''
        check(isinstance(response, str) and len(response.strip()) <= 5000, 'Your exercise response must contain at most 5000 characters.')
        check(not lesson['exercise'] or len(response.strip()) >= 10, 'Write your response to the practical exercise (at least 10 characters) to complete this lesson.')
        db.execute('INSERT INTO lesson_progress(run_id,lesson_id,completed_at,response) VALUES (?,?,?,?) ON CONFLICT(run_id,lesson_id) DO UPDATE SET response=excluded.response',
                   (run_id, lesson['id'], now(), response.strip()))
    elif action == 'resume':
        expire_exams(db, run_id, 'The exam page was closed, reloaded, or opened in another tab.')
    elif action == 'restart':
        expire_exams(db, run_id, 'A new course run was started.')
        db.execute('UPDATE course_runs SET archived_at=? WHERE id=?', (now(), run_id))
        create_run(db, candidate, run['course_id'])
    elif action == 'video':
        i = index(data, 'videoIndex', 5)
        check(unlocked(db, run_id, i // 2), 'Complete the previous set first.', 403)
        watched = data.get('watched')
        duration=db.execute('SELECT duration_seconds FROM videos WHERE course_id=? AND video_index=?',(run['course_id'],i)).fetchone()[0]
        check(type(watched) in (int,float) and math.isfinite(watched) and 0 <= watched <= duration,'Invalid watched duration.')
        completed = now() if data.get('complete') is True and watched >= duration * 0.9 else None
        db.execute('INSERT INTO video_progress VALUES (?,?,?,?,?) ON CONFLICT(run_id,video_index) DO UPDATE SET watched_seconds=MAX(watched_seconds,excluded.watched_seconds),completed_at=COALESCE(completed_at,excluded.completed_at),updated_at=excluded.updated_at', (run_id, i, watched, completed, now()))
    elif action == 'exercise':
        s, e = index(data, 'setIndex', 2), index(data, 'exerciseIndex', 1)
        check(unlocked(db, run_id, s), 'Complete the previous set first.', 403)
        answers = data.get('answers')
        score, details = grade(db, s, 'exercise', e, answers, run['course_id'])
        db.execute('INSERT INTO exercise_attempts VALUES (?,?,?,?,?,?,?,?)', (uid(), run_id, s, e, json.dumps(answers), score, int(score == 2), now()))
        extra = {'feedback': {'score': score, 'answers': answers, 'details': details}}
    elif action == 'exam-start':
        s = index(data, 'setIndex', 2)
        check(unlocked(db, run_id, s) and ready(db, run_id, s), 'Complete both videos and both exercises before the exam.', 403)
        check(not passed(db, run_id, s), 'This exam has already been passed.', 409)
        check(db.execute("SELECT 1 FROM exam_attempts WHERE run_id=? AND status='in-progress'", (run_id,)).fetchone() is None, 'An examination is already active. Reload to end the interrupted attempt.', 409)
        number = db.execute('SELECT COUNT(*)+1 FROM exam_attempts WHERE run_id=? AND set_index=?', (run_id, s)).fetchone()[0]
        limit = db.execute('SELECT max_attempts FROM courses WHERE id=?', (run['course_id'],)).fetchone()[0]
        check(number <= limit, f'All {limit} exam attempts have been used. Start a new course run to try again.', 409)
        identity = uid()
        db.execute('INSERT INTO exam_attempts(id,run_id,set_index,attempt_number,status,started_at,deadline) VALUES (?,?,?,?,?,?,?)', (identity, run_id, s, number, 'in-progress', now(), time.time() + 600))
        extra['attempt'] = attempt_view(db.execute('SELECT * FROM exam_attempts WHERE id=?', (identity,)).fetchone())
    elif action == 'exam-finish':
        identity = data.get('attemptId')
        check(isinstance(identity, str), 'Attempt ID is required.')
        attempt = db.execute('SELECT * FROM exam_attempts WHERE id=? AND run_id=?', (identity, run_id)).fetchone()
        check(attempt is not None, 'Attempt was not found.', 404)
        if attempt['status'] == 'in-progress':
            if data.get('terminate') is True:
                reason = str(data.get('reason') or 'The examination was ended.')[:300]
                db.execute("UPDATE exam_attempts SET status='terminated',reason=?,finished_at=? WHERE id=?", (reason, now(), identity))
            else:
                answers = data.get('answers')
                score, _ = grade(db, attempt['set_index'], 'exam', -1, answers, run['course_id'])
                course = db.execute('SELECT title,pass_percent FROM courses WHERE id=?', (run['course_id'],)).fetchone()
                result = 'passed' if score * 25 >= course['pass_percent'] else 'failed'
                db.execute('UPDATE exam_attempts SET status=?,score=?,answers_json=?,finished_at=? WHERE id=?', (result, score, json.dumps(answers), now(), identity))
                notify(db, [candidate], 'assessment', f"Module {attempt['set_index'] + 1} exam {'passed' if result == 'passed' else 'not passed'}: {course['title']}", f"You scored {score * 25}% (pass mark {course['pass_percent']}%).", 'courses', f'exam:{identity}')
        extra['attempt'] = attempt_view(db.execute('SELECT * FROM exam_attempts WHERE id=?', (identity,)).fetchone())
    else:
        raise APIError(404, 'Endpoint was not found.')
    from notifications import refresh
    if action != 'video' or data.get('complete') is True:
        refresh(db, {'id': candidate})
    issue_certificate(db, candidate, current_run(db, candidate, course_id=run['course_id'])['id'])
    return {'learning': bundle(db, candidate,run['course_id']), **extra}


def records(db, candidate):
    result = {'runs': [dict(r) for r in db.execute('SELECT * FROM course_runs WHERE candidate_id=? ORDER BY run_number', (candidate,))]}
    for table in ('video_progress', 'exercise_attempts', 'exam_attempts', 'certificates'):
        result[table] = [dict(r) for r in db.execute(f'SELECT t.* FROM {table} t JOIN course_runs r ON r.id=t.run_id WHERE r.candidate_id=?', (candidate,))]
    result['assignment_attempts'] = [dict(r) for r in db.execute('''SELECT a.id,a.run_id,a.checkpoint_id,a.attempt_number,a.status,a.started_at,a.deadline,a.finished_at,a.score,a.total,a.reason
        FROM checkpoint_attempts a JOIN course_runs r ON r.id=a.run_id WHERE r.candidate_id=? ORDER BY a.started_at''', (candidate,))]
    result['assessment_attempts'] = [dict(r) for r in db.execute('SELECT id,assessment_id,attempt_number,status,started_at,finished_at,score,total,percent FROM assessment_attempts WHERE employee_id=? ORDER BY started_at', (candidate,))]
    result['skill_evidence'] = [dict(r) for r in db.execute('SELECT skill_id,level,source,note,recorded_at FROM skill_evidence WHERE employee_id=? ORDER BY id', (candidate,))]
    result['learning_goals'] = [dict(r) for r in db.execute('SELECT * FROM learning_goals WHERE employee_id=? ORDER BY created_at', (candidate,))]
    result['session_registrations'] = [dict(r) for r in db.execute('SELECT * FROM session_registrations WHERE employee_id=?', (candidate,))]
    result['development_records'] = [dict(r) for r in db.execute('SELECT * FROM development_records WHERE employee_id=? ORDER BY completed_on', (candidate,))]
    result['account_events'] = [dict(r) for r in db.execute('SELECT event,created_at FROM auth_events WHERE candidate_id=? ORDER BY id', (candidate,))]
    return result


DUMMY_HASH = password_hash('not-a-real-candidate-password')
