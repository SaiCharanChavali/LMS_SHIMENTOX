"""Learning activity history: an append-only record of meaningful learning events.

Events are written by the server inside the learning workflows (never from browser-supplied timestamps). Logging is
best effort: a failure is rolled back to a savepoint and never blocks the lesson, assessment or completion it describes.
Each event has a dedupe key, so a retried request or a replayed submission is stored once. Opening events (course and
lesson opened or resumed) are additionally collapsed when repeated within a short window.

What is NOT recorded: answers, answer keys, scores of individual questions, page dwell time, keystrokes or anything
else that would amount to monitoring. An opened course is access, not proof of learning, and analytics say so.
"""
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

# Activity type -> (label shown to people, group used by filters and analytics).
TYPES = {
    'course_opened': ('Course opened', 'course'),
    'course_started': ('Course started', 'course'),
    'course_resumed': ('Course resumed', 'course'),
    'course_completed': ('Course completed', 'course'),
    'lesson_opened': ('Lesson opened', 'lesson'),
    'lesson_started': ('Lesson started', 'lesson'),
    'lesson_completed': ('Lesson completed', 'lesson'),
    'assessment_started': ('Assessment started', 'assessment'),
    'assessment_submitted': ('Assessment submitted', 'assessment'),
    'assessment_passed': ('Assessment passed', 'assessment'),
    'assessment_failed': ('Assessment failed', 'assessment'),
    'certificate_generated': ('Certificate generated', 'other'),
    'resource_accessed': ('Learning resource accessed', 'other'),
}
ACCESS_TYPES = ('course_opened', 'course_started', 'course_resumed')
ATTEMPT_TYPES = ('assessment_started', 'assessment_submitted')
RESULT_TYPES = ('assessment_passed', 'assessment_failed')
# Kinds of scored attempt that are reported as assessments.
ATTEMPT_KINDS = {'exam': 'Module exam', 'assignment': 'Course assignment', 'assessment': 'Assessment', 'quiz': 'Knowledge check'}
# Repeated opens of the same course or lesson within this window are one visit.
OPEN_WINDOW_SECONDS = 600
# Metadata is limited to these keys and to short scalar values.
META_KEYS = {'courseTitle', 'lessonTitle', 'assessmentTitle', 'resourceTitle', 'resourceKind', 'kind', 'attempt', 'attemptNumber',
             'score', 'total', 'percent', 'passPercent', 'result', 'certificateNumber', 'videoIndex', 'runNumber', 'backfilled'}
PAGE_SIZE = 20
STAFF_PAGE_SIZE = 25


def _check(condition, message, status=400):
    if not condition:
        # Raised as the portal's APIError so the server answers with the right status code.
        from services import APIError
        raise APIError(status, message)


def stamp(moment=None):
    moment = moment or datetime.now(timezone.utc)
    return moment.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _clean(metadata):
    result = {}
    for key, value in (metadata or {}).items():
        if key not in META_KEYS or value is None:
            continue
        if isinstance(value, str):
            value = value[:200]
        elif not isinstance(value, (bool, int, float)):
            continue
        result[key] = value
    return result


# ---------------------------------------------------------------- writing

def record(db, employee, kind, key, *, course=None, lesson=None, assessment=None, run=None, metadata=None, at=None, window=None):
    """Store one activity event; returns True when a new row was written.

    `key` identifies the event for de-duplication (per employee). `window` (seconds) skips the event when an event of
    the same family for the same course and lesson was recorded that recently. Never raises for a logging failure.
    """
    if kind not in TYPES:
        raise ValueError(f'Unknown learning activity type: {kind}')
    try:
        db.execute('SAVEPOINT learning_activity')
    except sqlite3.Error:
        return False
    try:
        moment = at or stamp()
        if window:
            family = ACCESS_TYPES if kind in ACCESS_TYPES else (kind,) if kind != 'lesson_opened' else ('lesson_opened', 'lesson_started')
            since = stamp(datetime.now(timezone.utc) - timedelta(seconds=window))
            recent = db.execute(f'''SELECT 1 FROM learning_activity_logs WHERE employee_id=? AND activity_type IN ({','.join('?' * len(family))})
                AND COALESCE(course_id,'')=? AND COALESCE(lesson_id,'')=? AND activity_timestamp>=? LIMIT 1''',
                                (employee, *family, course or '', lesson or '', since)).fetchone()
            if recent:
                db.execute('RELEASE SAVEPOINT learning_activity')
                return False
        details = _clean(metadata)
        # Titles are kept with the event so history still reads correctly after a course or lesson is renamed or removed.
        if course and 'courseTitle' not in details:
            row = db.execute('SELECT title FROM courses WHERE id=?', (course,)).fetchone()
            if row:
                details['courseTitle'] = row[0]
        if lesson and 'lessonTitle' not in details:
            row = db.execute('SELECT title FROM course_lessons WHERE id=?', (lesson,)).fetchone()
            if row:
                details['lessonTitle'] = row[0]
        if assessment and 'assessmentTitle' not in details:
            row = db.execute('SELECT title FROM assessments WHERE id=?', (assessment,)).fetchone()
            if row:
                details['assessmentTitle'] = row[0]
        # Links to rows that no longer exist are dropped rather than failing the foreign key.
        if course and db.execute('SELECT 1 FROM courses WHERE id=?', (course,)).fetchone() is None:
            course = None
        if lesson and db.execute('SELECT 1 FROM course_lessons WHERE id=?', (lesson,)).fetchone() is None:
            lesson = None
        if assessment and db.execute('SELECT 1 FROM assessments WHERE id=?', (assessment,)).fetchone() is None:
            assessment = None
        if run and db.execute('SELECT 1 FROM course_runs WHERE id=?', (run,)).fetchone() is None:
            run = None
        created = db.execute('''INSERT OR IGNORE INTO learning_activity_logs(id,employee_id,course_id,lesson_id,assessment_id,run_id,activity_type,
            activity_timestamp,metadata,dedupe_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                             (str(uuid.uuid4()), employee, course, lesson, assessment, run, kind, moment, json.dumps(details, separators=(',', ':')),
                              key or f'{kind}:{uuid.uuid4()}', stamp())).rowcount
        db.execute('RELEASE SAVEPOINT learning_activity')
        return bool(created)
    except sqlite3.Error:
        # Optional analytics must never undo the learning action that is being recorded.
        try:
            db.execute('ROLLBACK TO SAVEPOINT learning_activity')
            db.execute('RELEASE SAVEPOINT learning_activity')
        except sqlite3.Error:
            pass
        return False


def run_has_progress(db, run_id):
    return any(db.execute(f'SELECT 1 FROM {table} WHERE run_id=? LIMIT 1', (run_id,)).fetchone() for table in (
        'lesson_progress', 'lesson_watch', 'video_progress', 'exercise_attempts', 'exam_attempts', 'checkpoint_attempts',
        'lesson_quiz_attempts', 'lesson_activity_attempts'))


def course_opened(db, employee, run):
    """An employee opened a course page: the first open of a run starts it; later opens resume it or revisit it."""
    if db.execute("SELECT 1 FROM learning_activity_logs WHERE employee_id=? AND dedupe_key=?", (employee, f'course_started:{run["id"]}')).fetchone() is None:
        return record(db, employee, 'course_started', f'course_started:{run["id"]}', course=run['course_id'], run=run['id'], metadata={'runNumber': run['run_number']})
    kind = 'course_resumed' if run['completed_at'] is None and run_has_progress(db, run['id']) else 'course_opened'
    return record(db, employee, kind, None, course=run['course_id'], run=run['id'], window=OPEN_WINDOW_SECONDS)


def lesson_opened(db, employee, run, lesson):
    key = f'lesson_started:{run["id"]}:{lesson["id"]}'
    if db.execute('SELECT 1 FROM learning_activity_logs WHERE employee_id=? AND dedupe_key=?', (employee, key)).fetchone() is None:
        return record(db, employee, 'lesson_started', key, course=run['course_id'], lesson=lesson['id'], run=run['id'])
    return record(db, employee, 'lesson_opened', None, course=run['course_id'], lesson=lesson['id'], run=run['id'], window=OPEN_WINDOW_SECONDS)


def lesson_completed(db, employee, run, lesson_id=None, video_index=None, title=None, at=None):
    target = lesson_id if lesson_id else f'video{video_index}'
    return record(db, employee, 'lesson_completed', f'lesson_completed:{run["id"]}:{target}', course=run['course_id'], lesson=lesson_id,
                  run=run['id'], metadata={'lessonTitle': title, 'videoIndex': video_index}, at=at)


def attempt_started(db, employee, kind, attempt_id, *, course=None, run=None, lesson=None, assessment=None, title=None, number=None, at=None, backfilled=None):
    return record(db, employee, 'assessment_started', f'assessment_started:{kind}:{attempt_id}', course=course, run=run, lesson=lesson, assessment=assessment,
                  metadata={'kind': kind, 'attempt': f'{kind}:{attempt_id}', 'assessmentTitle': title, 'attemptNumber': number, 'backfilled': backfilled}, at=at)


def attempt_finished(db, employee, kind, attempt_id, status, *, score=None, total=None, percent=None, pass_percent=None,
                     course=None, run=None, lesson=None, assessment=None, title=None, number=None, at=None, backfilled=None):
    """A submitted attempt: one 'submitted' event and one 'passed' or 'failed' event. Terminated or expired attempts were not submitted."""
    if status not in ('passed', 'failed'):
        return False
    details = {'kind': kind, 'attempt': f'{kind}:{attempt_id}', 'assessmentTitle': title, 'attemptNumber': number, 'score': score,
               'total': total, 'percent': percent, 'passPercent': pass_percent, 'result': status, 'backfilled': backfilled}
    refs = dict(course=course, run=run, lesson=lesson, assessment=assessment, at=at)
    submitted = record(db, employee, 'assessment_submitted', f'assessment_submitted:{kind}:{attempt_id}', metadata=details, **refs)
    record(db, employee, f'assessment_{status}', f'assessment_result:{kind}:{attempt_id}', metadata=details, **refs)
    return submitted


def course_completed(db, employee, run_id, at=None):
    run = db.execute('SELECT * FROM course_runs WHERE id=?', (run_id,)).fetchone()
    if run is None or not run['completed_at']:
        return False
    return record(db, employee, 'course_completed', f'course_completed:{run_id}', course=run['course_id'], run=run_id,
                  metadata={'runNumber': run['run_number']}, at=at or run['completed_at'])


def certificate_generated(db, employee, run_id):
    row = db.execute('SELECT c.certificate_number,c.issued_at,c.course_title,r.course_id FROM certificates c JOIN course_runs r ON r.id=c.run_id WHERE c.run_id=?', (run_id,)).fetchone()
    if row is None:
        return False
    return record(db, employee, 'certificate_generated', f'certificate:{run_id}', course=row['course_id'], run=run_id,
                  metadata={'certificateNumber': row['certificate_number'], 'courseTitle': row['course_title']}, at=row['issued_at'])


def resource_accessed(db, employee, resource):
    return record(db, employee, 'resource_accessed', None, course=resource['course_id'],
                  metadata={'resourceTitle': resource['title'], 'resourceKind': resource['kind']}, window=60)


# ---------------------------------------------------------------- history from before activity logging existed

def backfill(db):
    """Create events for learning recorded before this log existed (marked as backfilled). Opens and resumes were never
    recorded, so they cannot be reconstructed. Safe to repeat: every event uses the same dedupe key as live logging."""
    meta = {'backfilled': True}
    progressed = '''EXISTS(SELECT 1 FROM lesson_progress WHERE run_id=r.id) OR EXISTS(SELECT 1 FROM video_progress WHERE run_id=r.id)
        OR EXISTS(SELECT 1 FROM exercise_attempts WHERE run_id=r.id) OR EXISTS(SELECT 1 FROM exam_attempts WHERE run_id=r.id)
        OR EXISTS(SELECT 1 FROM checkpoint_attempts WHERE run_id=r.id) OR EXISTS(SELECT 1 FROM lesson_watch WHERE run_id=r.id)
        OR EXISTS(SELECT 1 FROM lesson_quiz_attempts WHERE run_id=r.id) OR r.completed_at IS NOT NULL'''
    for r in db.execute(f'SELECT r.* FROM course_runs r WHERE {progressed}').fetchall():
        record(db, r['candidate_id'], 'course_started', f'course_started:{r["id"]}', course=r['course_id'], run=r['id'],
               metadata={**meta, 'runNumber': r['run_number']}, at=r['started_at'])
        if r['completed_at']:
            record(db, r['candidate_id'], 'course_completed', f'course_completed:{r["id"]}', course=r['course_id'], run=r['id'],
                   metadata={**meta, 'runNumber': r['run_number']}, at=r['completed_at'])
    for r in db.execute('SELECT c.*,r.candidate_id,r.course_id FROM certificates c JOIN course_runs r ON r.id=c.run_id').fetchall():
        record(db, r['candidate_id'], 'certificate_generated', f'certificate:{r["run_id"]}', course=r['course_id'], run=r['run_id'],
               metadata={**meta, 'certificateNumber': r['certificate_number'], 'courseTitle': r['course_title']}, at=r['issued_at'])
    for r in db.execute('SELECT p.*,r.candidate_id,r.course_id FROM lesson_progress p JOIN course_runs r ON r.id=p.run_id').fetchall():
        record(db, r['candidate_id'], 'lesson_completed', f'lesson_completed:{r["run_id"]}:{r["lesson_id"]}', course=r['course_id'],
               lesson=r['lesson_id'], run=r['run_id'], metadata=meta, at=r['completed_at'])
    titles = {}
    for r in db.execute('SELECT v.*,r.candidate_id,r.course_id FROM video_progress v JOIN course_runs r ON r.id=v.run_id WHERE v.completed_at IS NOT NULL').fetchall():
        if r['course_id'] not in titles:
            row = db.execute('SELECT lessons_json FROM courses WHERE id=?', (r['course_id'],)).fetchone()
            try:
                titles[r['course_id']] = [item.get('title') for item in json.loads(row[0])] if row else []
            except (ValueError, AttributeError):
                titles[r['course_id']] = []
        names = titles[r['course_id']]
        title = names[r['video_index']] if r['video_index'] < len(names) else None
        record(db, r['candidate_id'], 'lesson_completed', f'lesson_completed:{r["run_id"]}:video{r["video_index"]}', course=r['course_id'],
               run=r['run_id'], metadata={**meta, 'lessonTitle': title, 'videoIndex': r['video_index']}, at=r['completed_at'])
    for r in db.execute('''SELECT x.*,r.candidate_id,r.course_id,k.pass_percent FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id
            JOIN courses k ON k.id=r.course_id''').fetchall():
        title = f'Module {r["set_index"] + 1} exam'
        refs = dict(course=r['course_id'], run=r['run_id'], title=title, number=r['attempt_number'])
        attempt_started(db, r['candidate_id'], 'exam', r['id'], at=r['started_at'], backfilled=True, **refs)
        if r['status'] in ('passed', 'failed') and r['score'] is not None:
            attempt_finished(db, r['candidate_id'], 'exam', r['id'], r['status'], score=r['score'], total=4, percent=r['score'] * 25,
                             pass_percent=r['pass_percent'], at=r['finished_at'], backfilled=True, **refs)
    for r in db.execute('''SELECT a.*,r.candidate_id,r.course_id,c.title,c.pass_percent FROM checkpoint_attempts a JOIN course_runs r ON r.id=a.run_id
            JOIN course_checkpoints c ON c.id=a.checkpoint_id''').fetchall():
        refs = dict(course=r['course_id'], run=r['run_id'], title=r['title'], number=r['attempt_number'])
        attempt_started(db, r['candidate_id'], 'assignment', r['id'], at=r['started_at'], backfilled=True, **refs)
        if r['status'] in ('passed', 'failed') and r['score'] is not None:
            attempt_finished(db, r['candidate_id'], 'assignment', r['id'], r['status'], score=r['score'], total=r['total'],
                             percent=round(r['score'] * 100 / r['total']) if r['total'] else None, pass_percent=r['pass_percent'], at=r['finished_at'], backfilled=True, **refs)
    for r in db.execute('''SELECT t.*,a.title,a.course_id,a.pass_percent FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id''').fetchall():
        refs = dict(course=r['course_id'], assessment=r['assessment_id'], title=r['title'], number=r['attempt_number'])
        attempt_started(db, r['employee_id'], 'assessment', r['id'], at=r['started_at'], backfilled=True, **refs)
        if r['status'] in ('passed', 'failed'):
            attempt_finished(db, r['employee_id'], 'assessment', r['id'], r['status'], score=r['score'], total=r['total'], percent=r['percent'],
                             pass_percent=r['pass_percent'], at=r['finished_at'], backfilled=True, **refs)
    for r in db.execute('''SELECT q.*,r.candidate_id,r.course_id,l.title,l.quiz_json FROM lesson_quiz_attempts q JOIN course_runs r ON r.id=q.run_id
            JOIN course_lessons l ON l.id=q.lesson_id''').fetchall():
        try:
            total = len(json.loads(r['quiz_json'])) if r['quiz_json'] else 0
        except ValueError:
            total = 0
        if total:
            attempt_finished(db, r['candidate_id'], 'quiz', r['id'], 'passed' if r['score'] >= total else 'failed', score=r['score'], total=total,
                             percent=round(r['score'] * 100 / total), pass_percent=100, course=r['course_id'], run=r['run_id'], lesson=r['lesson_id'],
                             title=f'{r["title"]} knowledge check', at=r['submitted_at'], backfilled=True)


# ---------------------------------------------------------------- reading

def _one(query, field, maximum=100):
    value = (query.get(field, [''])[0] or '').strip()
    _check(len(value) <= maximum, f'{field} is too long.')
    return value or None


def _date(query, field):
    value = _one(query, field, 10)
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        _check(False, f'{field} must be a date in YYYY-MM-DD format.')


def _page(query):
    try:
        return max(1, min(100000, int(query.get('page', ['1'])[0])))
    except ValueError:
        _check(False, 'page must be a whole number.')


def filters(query):
    """Validated history filters shared by the employee and staff views."""
    kind = _one(query, 'type', 40)
    _check(kind is None or kind in TYPES or kind in ('course', 'lesson', 'assessment', 'other'), 'Unknown activity type.')
    start, end = _date(query, 'from'), _date(query, 'to')
    _check(not (start and end) or start <= end, 'The start date must be on or before the end date.')
    return {'course': _one(query, 'course'), 'type': kind, 'from': start, 'to': end, 'page': _page(query)}


def _where(f, alias='l'):
    clauses, params = [], []
    if f.get('course'):
        clauses.append(f'{alias}.course_id=?')
        params.append(f['course'])
    if f.get('type') in TYPES:
        clauses.append(f'{alias}.activity_type=?')
        params.append(f['type'])
    elif f.get('type'):
        kinds = [k for k, (_, group) in TYPES.items() if group == f['type']]
        clauses.append(f"{alias}.activity_type IN ({','.join('?' * len(kinds))})")
        params += kinds
    if f.get('from'):
        clauses.append(f'{alias}.activity_timestamp>=?')
        params.append(f['from'])
    if f.get('to'):
        # Dates are whole UTC days; the end date is inclusive.
        clauses.append(f'substr({alias}.activity_timestamp,1,10)<=?')
        params.append(f['to'])
    return clauses, params


def view(row):
    """One event as shown in timelines and tables. Removed courses or lessons fall back to the titles stored with the event."""
    meta = json.loads(row['metadata'] or '{}')
    kind = row['activity_type']
    course = row['course_title'] if 'course_title' in row.keys() and row['course_title'] else meta.get('courseTitle')
    lesson = row['lesson_title'] if 'lesson_title' in row.keys() and row['lesson_title'] else meta.get('lessonTitle')
    subject = meta.get('assessmentTitle') or meta.get('resourceTitle') or lesson or course or 'Removed course'
    status, detail = None, ''
    if kind in RESULT_TYPES:
        status = 'passed' if kind == 'assessment_passed' else 'failed'
        if meta.get('percent') is not None:
            detail = f"{meta['percent']}%" + (f" · pass mark {meta['passPercent']}%" if meta.get('passPercent') is not None else '')
    elif kind == 'assessment_submitted':
        status = 'submitted'
        detail = f"Attempt {meta['attemptNumber']}" if meta.get('attemptNumber') else ''
    elif kind == 'assessment_started':
        status = 'started'
        detail = f"Attempt {meta['attemptNumber']}" if meta.get('attemptNumber') else ''
    elif kind in ('course_completed', 'lesson_completed'):
        status = 'completed'
    elif kind == 'certificate_generated':
        status = 'issued'
        detail = f"Certificate {meta['certificateNumber']}" if meta.get('certificateNumber') else ''
    elif kind == 'resource_accessed':
        detail = (meta.get('resourceKind') or '').capitalize()
    elif kind in ('course_started', 'lesson_started', 'course_resumed'):
        status = 'in_progress'
    if meta.get('kind') in ATTEMPT_KINDS and kind in ATTEMPT_TYPES + RESULT_TYPES:
        detail = ATTEMPT_KINDS[meta['kind']] + (f' · {detail}' if detail else '')
    return {'id': row['id'], 'type': kind, 'label': TYPES[kind][0], 'group': TYPES[kind][1], 'at': row['activity_timestamp'],
            'courseId': row['course_id'], 'course': course or 'Removed course', 'lesson': lesson, 'subject': subject, 'status': status,
            'detail': detail, 'percent': meta.get('percent'), 'backfilled': bool(meta.get('backfilled'))}


SELECT_EVENT = '''SELECT l.*,k.title AS course_title,cl.title AS lesson_title FROM learning_activity_logs l
    LEFT JOIN courses k ON k.id=l.course_id LEFT JOIN course_lessons cl ON cl.id=l.lesson_id'''


def timeline(db, employee, query, size=PAGE_SIZE):
    f = filters(query)
    clauses, params = _where(f)
    where = ' AND '.join(['l.employee_id=?'] + clauses)
    total = db.execute(f'SELECT COUNT(*) FROM learning_activity_logs l WHERE {where}', [employee] + params).fetchone()[0]
    pages = max(1, -(-total // size))
    page = min(f['page'], pages)
    rows = db.execute(f'{SELECT_EVENT} WHERE {where} ORDER BY l.activity_timestamp DESC,l.created_at DESC LIMIT ? OFFSET ?',
                      [employee] + params + [size, (page - 1) * size]).fetchall()
    courses = [{'id': r[0], 'title': r[1] or 'Removed course'} for r in db.execute('''SELECT l.course_id,COALESCE(k.title,json_extract(MAX(l.metadata),'$.courseTitle'))
        FROM learning_activity_logs l LEFT JOIN courses k ON k.id=l.course_id WHERE l.employee_id=? AND l.course_id IS NOT NULL GROUP BY l.course_id ORDER BY 2''', (employee,))]
    return {'items': [view(r) for r in rows], 'page': page, 'pages': pages, 'total': total,
            'filters': {k: f[k] for k in ('course', 'type', 'from', 'to')}, 'courses': courses,
            'types': [[k, label] for k, (label, _) in TYPES.items()]}


def my_activity(db, user, query):
    """The signed-in employee's own history. The employee comes from the session; no employee parameter is accepted."""
    return timeline(db, user['id'], query)


# ---------------------------------------------------------------- HR, admin and manager views

def activity_scope(db, user):
    """Employee ids the user may see (None = everyone). HR and admins see the organisation; managers their active direct reports."""
    if user['role'] in ('admin', 'hr'):
        return None
    _check(user['role'] == 'manager', 'You do not have permission to view learning activity.', 403)
    return [r[0] for r in db.execute('SELECT id FROM candidates WHERE manager_id=? AND is_active=1', (user['id'],))]


def _people_clause(scope, department=None, job_role=None, employee=None, active_only=False):
    clauses, params = ["c.role<>'admin'"], []
    if scope is not None:
        clauses.append(f"c.id IN ({','.join('?' * len(scope))})" if scope else '0=1')
        params += scope
    if active_only:
        clauses.append('c.is_active=1')
    for column, value in (('c.department_id', department), ('c.job_role_id', job_role), ('c.id', employee)):
        if value:
            clauses.append(f'{column}=?')
            params.append(value)
    return clauses, params


def _staff_filters(db, user, query):
    scope = activity_scope(db, user)
    f = filters(query)
    f.update(employee=_one(query, 'employee'), department=_one(query, 'department'), jobRole=_one(query, 'jobRole'), q=_one(query, 'q', 80))
    if f['employee'] and scope is not None:
        _check(f['employee'] in scope, 'You can view learning activity only for employees you manage.', 403)
    return scope, f


def _options(db, scope):
    clauses, params = _people_clause(scope)
    people = [{'id': r[0], 'name': r[1]} for r in db.execute(f'SELECT c.id,c.full_name FROM candidates c WHERE {" AND ".join(clauses)} ORDER BY c.full_name', params)]
    courses = [{'id': r[0], 'title': r[1]} for r in db.execute('SELECT id,title FROM courses ORDER BY title')]
    return {'employees': people, 'courses': courses, 'types': [[k, label] for k, (label, _) in TYPES.items()],
            'departments': [{'id': r[0], 'name': r[1]} for r in db.execute('SELECT id,name FROM departments ORDER BY name')],
            'jobRoles': [{'id': r[0], 'name': r[1]} for r in db.execute('SELECT id,name FROM job_roles ORDER BY name')]}


def staff_activity(db, user, query):
    """Organisation (or team) activity table with summary metrics; every figure is counted from activity rows."""
    from analytics import progress_index
    scope, f = _staff_filters(db, user, query)
    people, people_params = _people_clause(scope, f['department'], f['jobRole'], f['employee'])
    if f['q']:
        # Employee name search; LIKE wildcards typed by the user are matched literally.
        people.append("c.full_name LIKE ? ESCAPE '!'")
        people_params.append('%' + f['q'].replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%')
    clauses, params = _where(f)
    where = ' AND '.join(people + clauses)
    all_params = people_params + params
    base = f'FROM learning_activity_logs l JOIN candidates c ON c.id=l.employee_id WHERE {where}'
    s = db.execute(f'''SELECT COUNT(*) AS total,COUNT(DISTINCT l.employee_id) AS learners,
        COUNT(DISTINCT CASE WHEN l.activity_type IN ('course_opened','course_started','course_resumed') THEN l.course_id END) AS courses,
        SUM(l.activity_type='lesson_completed') AS lessons,
        COUNT(DISTINCT CASE WHEN l.activity_type IN ('assessment_started','assessment_submitted') THEN json_extract(l.metadata,'$.attempt') END) AS attempts,
        SUM(l.activity_type='course_completed') AS completions {base}''', all_params).fetchone()
    summary = {'totalActivities': s['total'], 'activeLearners': s['learners'], 'coursesAccessed': s['courses'], 'lessonsCompleted': s['lessons'] or 0,
               'assessmentsAttempted': s['attempts'], 'coursesCompleted': s['completions'] or 0}
    pages = max(1, -(-s['total'] // STAFF_PAGE_SIZE))
    page = min(f['page'], pages)
    rows = db.execute(f'''SELECT l.*,k.title AS course_title,cl.title AS lesson_title,c.full_name,c.keka_employee_number,d.name AS department,j.name AS job_role
        FROM learning_activity_logs l JOIN candidates c ON c.id=l.employee_id LEFT JOIN courses k ON k.id=l.course_id LEFT JOIN course_lessons cl ON cl.id=l.lesson_id
        LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id
        WHERE {where} ORDER BY l.activity_timestamp DESC,l.created_at DESC LIMIT ? OFFSET ?''', all_params + [STAFF_PAGE_SIZE, (page - 1) * STAFF_PAGE_SIZE]).fetchall()
    progress = progress_index(db, list({r['employee_id'] for r in rows}), list({r['course_id'] for r in rows if r['course_id']})) if rows else {}
    items = []
    for r in rows:
        item = view(r)
        p = progress.get((r['employee_id'], r['course_id']))
        item.update(employeeId=r['employee_id'], employeeNumber=r['keka_employee_number'] or '', employee=r['full_name'],
                    department=r['department'] or '', jobRole=r['job_role'] or '',
                    progress=(100 if p['completed'] else p['progress']) if p else None)
        items.append(item)
    return {'summary': summary, 'items': items, 'page': page, 'pages': pages, 'total': s['total'], 'scope': 'organisation' if scope is None else 'team',
            'filters': {k: f[k] for k in ('course', 'type', 'from', 'to', 'employee', 'department', 'jobRole', 'q')}, 'options': _options(db, scope)}


def employee_activity(db, user, employee_id, query):
    """One employee's full history for HR, admins, or that employee's manager."""
    scope = activity_scope(db, user)
    _check(scope is None or employee_id in scope, 'You can view learning activity only for employees you manage.', 403)
    row = db.execute('''SELECT c.id,c.full_name,c.keka_employee_number,c.role,d.name AS department,j.name AS job_role FROM candidates c
        LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id WHERE c.id=?''', (employee_id,)).fetchone()
    _check(row is not None and row['role'] != 'admin', 'Employee was not found.', 404)
    return {'employee': {'id': row['id'], 'name': row['full_name'], 'employeeNumber': row['keka_employee_number'] or '',
                         'department': row['department'] or '', 'jobRole': row['job_role'] or ''}, **timeline(db, employee_id, query)}


def _rate(part, whole):
    return round(part * 100 / whole) if whole else None


def analytics(db, user, query):
    """Aggregates over recorded events in a stated period. Access is counted separately from completion; nothing here
    measures study time, productivity or attendance."""
    scope = activity_scope(db, user)
    today = datetime.now(timezone.utc).date()
    end = _date(query, 'to') or today.isoformat()
    start = _date(query, 'from') or (date.fromisoformat(end) - timedelta(days=89)).isoformat()
    _check(start <= end, 'The start date must be on or before the end date.')
    try:
        inactive_days = int(query.get('inactiveDays', ['30'])[0])
    except ValueError:
        inactive_days = 0
    _check(7 <= inactive_days <= 365, 'inactiveDays must be between 7 and 365.')
    department = _one(query, 'department')
    people, people_params = _people_clause(scope, department)
    period = 'l.activity_timestamp>=? AND substr(l.activity_timestamp,1,10)<=?'
    where = ' AND '.join(people + [period])
    params = people_params + [start, end]
    joined = f'FROM learning_activity_logs l JOIN candidates c ON c.id=l.employee_id LEFT JOIN courses k ON k.id=l.course_id WHERE {where}'
    title = "COALESCE(k.title,json_extract(MAX(l.metadata),'$.courseTitle'),'Removed course')"

    accessed = [{'courseId': r[0], 'course': r[1], 'learners': r[2], 'visits': r[3]} for r in db.execute(f'''SELECT l.course_id,{title},
        COUNT(DISTINCT l.employee_id),COUNT(*) {joined} AND l.activity_type IN ('course_opened','course_started','course_resumed') AND l.course_id IS NOT NULL
        GROUP BY l.course_id ORDER BY 3 DESC,4 DESC LIMIT 10''', params)]
    completed = [{'courseId': r[0], 'course': r[1], 'learners': r[2]} for r in db.execute(f'''SELECT l.course_id,{title},COUNT(DISTINCT l.employee_id)
        {joined} AND l.activity_type='course_completed' AND l.course_id IS NOT NULL GROUP BY l.course_id ORDER BY 3 DESC LIMIT 10''', params)]

    # Abandonment: of the learners who started a course in the period, those who have not completed it and have had no
    # activity in that course for `inactive_days`. Starters still active recently are counted as in progress, not abandoned.
    cutoff = stamp(datetime.now(timezone.utc) - timedelta(days=inactive_days))
    abandonment = []
    for r in db.execute(f'''SELECT l.course_id,{title} AS title,COUNT(DISTINCT l.employee_id) AS starters,
        COUNT(DISTINCT CASE WHEN NOT EXISTS(SELECT 1 FROM learning_activity_logs x WHERE x.employee_id=l.employee_id AND x.course_id=l.course_id AND x.activity_type='course_completed')
            AND NOT EXISTS(SELECT 1 FROM learning_activity_logs y WHERE y.employee_id=l.employee_id AND y.course_id=l.course_id AND y.activity_timestamp>=?) THEN l.employee_id END) AS abandoned,
        COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM learning_activity_logs x WHERE x.employee_id=l.employee_id AND x.course_id=l.course_id AND x.activity_type='course_completed') THEN l.employee_id END) AS done
        {joined} AND l.activity_type='course_started' AND l.course_id IS NOT NULL GROUP BY l.course_id''', [cutoff] + params):
        abandonment.append({'courseId': r['course_id'], 'course': r['title'], 'started': r['starters'], 'completed': r['done'], 'abandoned': r['abandoned'],
                            'inProgress': r['starters'] - r['done'] - r['abandoned'], 'rate': _rate(r['abandoned'], r['starters'])})
    abandonment.sort(key=lambda a: (-(a['rate'] or 0), -a['started']))

    lessons = [{'course': r[0], 'lesson': r[1] or 'Lesson', 'started': r[2], 'completed': r[3], 'rate': _rate(r[3], r[2]) if r[2] else None}
               for r in db.execute(f'''SELECT {title},COALESCE(MAX(cl.title),json_extract(MAX(l.metadata),'$.lessonTitle')),
        COUNT(DISTINCT CASE WHEN l.activity_type='lesson_started' THEN l.employee_id END),
        COUNT(DISTINCT CASE WHEN l.activity_type='lesson_completed' THEN l.employee_id END)
        FROM learning_activity_logs l JOIN candidates c ON c.id=l.employee_id LEFT JOIN courses k ON k.id=l.course_id LEFT JOIN course_lessons cl ON cl.id=l.lesson_id
        WHERE {where} AND l.activity_type IN ('lesson_started','lesson_completed')
        GROUP BY l.course_id,COALESCE(l.lesson_id,json_extract(l.metadata,'$.videoIndex')) ORDER BY 3 DESC,4 DESC LIMIT 15''', params)]
    weekdays = [0] * 7
    for r in db.execute(f"SELECT CAST(strftime('%w',l.activity_timestamp) AS INTEGER),COUNT(*) {joined} AND l.activity_type='lesson_completed' GROUP BY 1", params):
        weekdays[r[0]] = r[1]

    # Attempt rate per course: of the learners who accessed the course in the period, how many started or submitted one of its assessments.
    attempts = [{'courseId': r[0], 'course': r[1], 'accessed': r[2], 'attempted': r[3], 'rate': _rate(r[3], r[2])} for r in db.execute(f'''SELECT l.course_id,{title},
        COUNT(DISTINCT l.employee_id),
        COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM learning_activity_logs a WHERE a.employee_id=l.employee_id AND a.course_id=l.course_id
            AND a.activity_type IN ('assessment_started','assessment_submitted') AND a.activity_timestamp>=? AND substr(a.activity_timestamp,1,10)<=?) THEN l.employee_id END)
        {joined} AND l.activity_type IN ('course_opened','course_started','course_resumed') AND l.course_id IS NOT NULL GROUP BY l.course_id ORDER BY 3 DESC LIMIT 15''',
        [start, end] + params)]
    results = [{'assessment': r[0] or 'Assessment', 'kind': ATTEMPT_KINDS.get(r[1], 'Assessment'), 'course': r[2], 'passed': r[3], 'failed': r[4],
                'passRate': _rate(r[3], r[3] + r[4])} for r in db.execute(f'''SELECT json_extract(l.metadata,'$.assessmentTitle'),json_extract(l.metadata,'$.kind'),
        {title},SUM(l.activity_type='assessment_passed'),SUM(l.activity_type='assessment_failed')
        {joined} AND l.activity_type IN ('assessment_passed','assessment_failed')
        GROUP BY COALESCE(l.assessment_id,''),l.course_id,json_extract(l.metadata,'$.kind'),json_extract(l.metadata,'$.assessmentTitle') ORDER BY 4+5 DESC LIMIT 20''', params)]

    active_people, active_params = _people_clause(scope, department, active_only=True)
    quiet_cutoff = stamp(datetime.now(timezone.utc) - timedelta(days=inactive_days))
    quiet_rows = db.execute(f'''SELECT c.id,c.full_name,d.name,(SELECT MAX(activity_timestamp) FROM learning_activity_logs WHERE employee_id=c.id) AS last
        FROM candidates c LEFT JOIN departments d ON d.id=c.department_id WHERE {' AND '.join(active_people)} ORDER BY last IS NOT NULL,last,c.full_name''', active_params).fetchall()
    quiet = [{'employeeId': r[0], 'employee': r[1], 'department': r[2] or '', 'lastActivity': r[3]} for r in quiet_rows if not r[3] or r[3] < quiet_cutoff]

    departments = []
    for r in db.execute(f'''SELECT d.id,COALESCE(d.name,'No department') AS name,COUNT(*) AS people,
        SUM(EXISTS(SELECT 1 FROM learning_activity_logs l WHERE l.employee_id=c.id AND {period})) AS active,
        SUM((SELECT COUNT(*) FROM learning_activity_logs l WHERE l.employee_id=c.id AND l.activity_type='lesson_completed' AND {period})) AS lessons,
        SUM((SELECT COUNT(*) FROM learning_activity_logs l WHERE l.employee_id=c.id AND l.activity_type='course_completed' AND {period})) AS courses,
        SUM((SELECT COUNT(*) FROM learning_activity_logs l WHERE l.employee_id=c.id AND l.activity_type='assessment_submitted' AND {period})) AS assessments
        FROM candidates c LEFT JOIN departments d ON d.id=c.department_id WHERE {' AND '.join(active_people)} GROUP BY d.id ORDER BY name''',
                         [start, end] * 4 + active_params):
        departments.append({'department': r['name'], 'employees': r['people'], 'activeLearners': r['active'] or 0, 'engagementRate': _rate(r['active'] or 0, r['people']),
                            'lessonsCompleted': r['lessons'] or 0, 'coursesCompleted': r['courses'] or 0, 'assessmentsSubmitted': r['assessments'] or 0})
    return {'period': {'from': start, 'to': end, 'inactiveDays': inactive_days, 'department': department}, 'scope': 'organisation' if scope is None else 'team',
            'mostAccessed': accessed, 'mostCompleted': completed, 'abandonment': abandonment[:10], 'lessonPatterns': lessons, 'completionsByWeekday': weekdays,
            'attemptRates': attempts, 'assessmentResults': results, 'inactive': quiet[:50], 'inactiveTotal': len(quiet), 'departments': departments,
            'definitions': {
                'access': 'Course opened, started or resumed. Access is not evidence of learning.',
                'abandonment': f'Started in the period, not completed, and no activity in that course for {inactive_days} days. Share of learners who started.',
                'attemptRate': 'Of the learners who accessed a course in the period, the share who started or submitted one of its assessments.',
                'passRate': 'Passed attempts divided by submitted attempts. Terminated and expired attempts were not submitted and are excluded.',
                'engagement': 'Active employees with at least one recorded learning activity in the period. Activity volume is not a measure of productivity.',
                'dates': 'Dates are whole days in UTC; both ends of the period are included.'},
            'options': _options(db, scope)}
