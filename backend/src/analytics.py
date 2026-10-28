"""Learning analytics computed from stored records: progress, assignments, paths, dashboards, reports, recommendations.

No figure here is hardcoded; every number is derived from SQLite rows at request time.
"""
import json
import heapq
from itertools import groupby,chain
from datetime import date, datetime, timedelta, timezone

from services import check

LEVELS = {0: 'Not assessed', 1: 'Beginner', 2: 'Intermediate', 3: 'Advanced', 4: 'Expert'}
UNITS = 15  # 6 videos + 6 exercises + 3 module exams per course run
STATUS_LABELS = {'completed': 'Completed', 'overdue': 'Overdue', 'in_progress': 'In progress', 'not_started': 'Not started'}
PAGE_SIZE = 25


def today():
    return date.today().isoformat()


def local_now():
    # Training session times are entered and compared in the server's local time.
    return datetime.now().strftime('%Y-%m-%dT%H:%M')


def ids_clause(ids, column):
    """SQL fragment restricting a column to a list of ids; None means unrestricted."""
    if ids is None:
        return '1=1', []
    if not ids:
        return '0=1', []
    return f"{column} IN ({','.join('?' * len(ids))})", list(ids)


def query_date(query, field):
    value = query.get(field, [''])[0]
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        check(False, f'{field} must be a date in YYYY-MM-DD format.')


def in_range(stamp, start, end):
    """ISO timestamps compare lexicographically; the end date is inclusive."""
    if not stamp:
        return False
    return (start is None or stamp >= start) and (end is None or stamp[:10] <= end)


# ---------------------------------------------------------------- scope and base data

def scope(db, user):
    """Return (employee_ids, course_ids) the user may analyse; None means all."""
    role = user['role']
    if role in ('admin', 'hr'):
        return None, None
    if role == 'manager':
        return [r[0] for r in db.execute('SELECT id FROM candidates WHERE manager_id=? AND is_active=1', (user['id'],))], None
    if role == 'trainer':
        return None, [r[0] for r in db.execute('SELECT id FROM courses WHERE trainer_id=? OR created_by=?', (user['id'], user['id']))]
    check(False, 'You do not have permission to view learning analytics.', 403)


def employee_rows(db, ids=None):
    where, params = ids_clause(ids, 'c.id')
    return [dict(r) for r in db.execute(f'''SELECT c.id,c.full_name AS name,c.email,c.role,c.department_id,c.job_role_id,c.manager_id,c.job_title,
        d.name AS department,j.name AS job_role FROM candidates c LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id
        WHERE c.is_active=1 AND c.role<>'admin' AND {where} ORDER BY c.full_name''', params)]


def course_rows(db, course_ids=None, published_only=False):
    where, params = ids_clause(course_ids, 'id')
    status = "AND status='published'" if published_only else ''
    return {r['id']: dict(r) for r in db.execute(f'SELECT id,title,description,category,status,difficulty,duration_minutes,department_id,post_assessment_id FROM courses WHERE {where} {status}', params)}


def progress_index(db, employee_ids=None, course_ids=None):
    """(employee, course) -> progress of the current run plus whether any run was completed."""
    w1, p1 = ids_clause(employee_ids, 'r.candidate_id')
    w2, p2 = ids_clause(course_ids, 'r.course_id')
    index = {}
    for r in db.execute(f'SELECT candidate_id,course_id,MIN(started_at) AS started_at,MIN(completed_at) AS completed_at FROM course_runs r WHERE {w1} AND {w2} GROUP BY candidate_id,course_id', p1 + p2):
        index[(r['candidate_id'], r['course_id'])] = {'units': 0, 'progress': 0, 'ready': False, 'completed': r['completed_at'] is not None, 'completedAt': r['completed_at'], 'startedAt': r['started_at'], 'started': False, 'lastActivity': ''}
    # Module courses have 15 units per run; lesson-based courses have one unit per lesson.
    for r in db.execute(f'''SELECT r.candidate_id,r.course_id,k.format,
        (SELECT COUNT(*) FROM video_progress v WHERE v.run_id=r.id AND v.completed_at IS NOT NULL)
        +(SELECT COUNT(DISTINCT e.set_index*2+e.exercise_index) FROM exercise_attempts e WHERE e.run_id=r.id AND e.passed=1)
        +(SELECT COUNT(DISTINCT x.set_index) FROM exam_attempts x WHERE x.run_id=r.id AND x.status='passed')
        +(SELECT COUNT(*) FROM lesson_progress l JOIN course_lessons cl ON cl.id=l.lesson_id WHERE l.run_id=r.id AND cl.course_id=r.course_id) AS units,
        (SELECT COUNT(*) FROM course_lessons cl WHERE cl.course_id=r.course_id) AS lesson_total,
        (SELECT COUNT(*) FROM course_checkpoints cp WHERE cp.course_id=r.course_id) AS checkpoint_total,
        (SELECT COUNT(DISTINCT ca.checkpoint_id) FROM checkpoint_attempts ca WHERE ca.run_id=r.id AND ca.status='passed') AS checkpoint_done,
        MAX(COALESCE((SELECT MAX(updated_at) FROM video_progress WHERE run_id=r.id),''),COALESCE((SELECT MAX(submitted_at) FROM exercise_attempts WHERE run_id=r.id),''),
            COALESCE((SELECT MAX(started_at) FROM exam_attempts WHERE run_id=r.id),''),COALESCE((SELECT MAX(completed_at) FROM lesson_progress WHERE run_id=r.id),''),
            COALESCE((SELECT MAX(started_at) FROM checkpoint_attempts WHERE run_id=r.id),'')) AS last_activity
        FROM course_runs r JOIN courses k ON k.id=r.course_id WHERE r.archived_at IS NULL AND {w1} AND {w2}''', p1 + p2):
        item = index[(r['candidate_id'], r['course_id'])]
        total = r['lesson_total'] + r['checkpoint_total'] if r['format'] == 'lessons' else UNITS
        units = r['units'] + r['checkpoint_done'] if r['format'] == 'lessons' else r['units']
        item.update({'units': units, 'progress': min(100, round(units / total * 100)) if total else 0, 'ready': total > 0 and units >= total,
                     'lastActivity': r['last_activity'], 'started': units > 0 or bool(r['last_activity'])})
    for item in index.values():
        item['started'] = item['started'] or item['completed']
    return index


def assignment_index(db, employee_ids=None, course_ids=None):
    """(employee, course) -> effective assignment, merging employee, department and job-role targets."""
    w1, p1 = ids_clause(employee_ids, 'c.id')
    w2, p2 = ids_clause(course_ids, 'a.course_id')
    index = {}
    for r in db.execute(f'''SELECT c.id AS employee_id,a.course_id,MAX(a.mandatory) AS mandatory,MIN(a.due_date) AS due_date,MIN(a.assigned_at) AS assigned_at,
        GROUP_CONCAT(DISTINCT m.full_name) AS assigned_by
        FROM candidates c JOIN course_assignments a ON (a.target_type='employee' AND a.target_id=c.id) OR (a.target_type='department' AND a.target_id=c.department_id) OR (a.target_type='job_role' AND a.target_id=c.job_role_id)
        JOIN courses k ON k.id=a.course_id AND k.status='published' LEFT JOIN candidates m ON m.id=a.assigned_by
        WHERE c.is_active=1 AND {w1} AND {w2} GROUP BY c.id,a.course_id''', p1 + p2):
        index[(r['employee_id'], r['course_id'])] = {'mandatory': bool(r['mandatory']), 'dueDate': r['due_date'], 'assignedAt': r['assigned_at'], 'assignedBy': r['assigned_by'] or ''}
    return index


def pair_status(progress, assignment):
    if progress and progress['completed']:
        return 'completed'
    if assignment and assignment['dueDate'] and assignment['dueDate'] < today():
        return 'overdue'
    if progress and progress['started']:
        return 'in_progress'
    return 'not_started'


def activity_times(db, course_ids=None):
    """Learning activity timestamps per employee (video, practice, exams, assessments)."""
    where, params = ids_clause(course_ids, 'r.course_id')
    rows = db.execute(f'''SELECT employee_id,t FROM (
        SELECT r.candidate_id AS employee_id,v.updated_at AS t,r.course_id FROM video_progress v JOIN course_runs r ON r.id=v.run_id WHERE {where}
        UNION ALL SELECT r.candidate_id,e.submitted_at,r.course_id FROM exercise_attempts e JOIN course_runs r ON r.id=e.run_id WHERE {where}
        UNION ALL SELECT r.candidate_id,x.started_at,r.course_id FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id WHERE {where}
        UNION ALL SELECT r.candidate_id,l.completed_at,r.course_id FROM lesson_progress l JOIN course_runs r ON r.id=l.run_id WHERE {where}
        UNION ALL SELECT r.candidate_id,w.updated_at,r.course_id FROM lesson_watch w JOIN course_runs r ON r.id=w.run_id WHERE {where}
        UNION ALL SELECT r.candidate_id,x.submitted_at,r.course_id FROM lesson_activity_attempts x JOIN course_runs r ON r.id=x.run_id WHERE {where})''', params * 6)
    times = {}
    for r in rows:
        times.setdefault(r['employee_id'], []).append(r['t'])
    if course_ids is None:
        for r in db.execute('SELECT employee_id,started_at AS t FROM assessment_attempts'):
            times.setdefault(r['employee_id'], []).append(r['t'])
    return times


def training_seconds(db, course_ids=None, start=None, end=None):
    """Seconds of verified video watching plus attended instructor-led sessions, per employee."""
    where, params = ids_clause(course_ids, 'r.course_id')
    totals = {}
    for r in db.execute(f'SELECT r.candidate_id,v.watched_seconds,v.updated_at FROM video_progress v JOIN course_runs r ON r.id=v.run_id WHERE {where}', params):
        if start is None and end is None or in_range(r['updated_at'], start, end):
            totals[r['candidate_id']] = totals.get(r['candidate_id'], 0) + r['watched_seconds']
    w2, p2 = ids_clause(course_ids, 's.course_id')
    for r in db.execute(f"SELECT g.employee_id,s.starts_at,(julianday(s.ends_at)-julianday(s.starts_at))*86400 AS seconds FROM session_registrations g JOIN training_sessions s ON s.id=g.session_id WHERE g.status='attended' AND {w2}", p2):
        if start is None and end is None or in_range(r['starts_at'], start, end):
            totals[r['employee_id']] = totals.get(r['employee_id'], 0) + max(0, r['seconds'] or 0)
    return totals


def assessment_scores(db, course_ids=None, start=None, end=None):
    """Percent scores of finished module exams and standalone assessments, per employee."""
    where, params = ids_clause(course_ids, 'r.course_id')
    scores = {}
    for r in db.execute(f"SELECT r.candidate_id AS employee_id,x.score*25 AS percent,x.finished_at FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id WHERE x.status IN ('passed','failed') AND {where}", params):
        if in_range(r['finished_at'], start, end):
            scores.setdefault(r['employee_id'], []).append(r['percent'])
    w2, p2 = ids_clause(course_ids, 'a.course_id')
    for r in db.execute(f"SELECT t.employee_id,t.percent,t.finished_at FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id WHERE t.status IN ('passed','failed') AND {w2}", p2):
        if in_range(r['finished_at'], start, end):
            scores.setdefault(r['employee_id'], []).append(r['percent'])
    return scores


def average(values):
    return round(sum(values) / len(values)) if values else None


def path_assignment_employees(db):
    rows = db.execute('''SELECT DISTINCT c.id FROM candidates c JOIN path_assignments a ON (a.target_type='employee' AND a.target_id=c.id) OR (a.target_type='department' AND a.target_id=c.department_id) OR (a.target_type='job_role' AND a.target_id=c.job_role_id)
        JOIN learning_paths p ON p.id=a.path_id AND p.status='published' WHERE c.is_active=1''')
    return {r[0] for r in rows}


# ---------------------------------------------------------------- skills, paths, recommendations

def skill_levels(db, employee_id):
    """Current level = highest level supported by assessment or manager evidence."""
    return {r[0]: r[1] for r in db.execute('SELECT skill_id,MAX(level) FROM skill_evidence WHERE employee_id=? GROUP BY skill_id', (employee_id,))}


def role_targets(db, job_role_id):
    return {r[0]: r[1] for r in db.execute('SELECT skill_id,target_level FROM role_competencies WHERE job_role_id=?', (job_role_id or '',))}


def employee_paths(db, employee, progress):
    rows = db.execute('''SELECT p.*,MIN(a.due_date) AS due_date FROM learning_paths p JOIN path_assignments a ON a.path_id=p.id
        WHERE p.status='published' AND ((a.target_type='employee' AND a.target_id=?) OR (a.target_type='department' AND a.target_id=?) OR (a.target_type='job_role' AND a.target_id=?))
        GROUP BY p.id ORDER BY p.title''', (employee['id'], employee['department_id'] or '', employee['job_role_id'] or '')).fetchall()
    paths = []
    for p in rows:
        courses, blocked, next_course = [], False, None
        for c in db.execute('SELECT k.id,k.title,k.description,k.status,k.difficulty,k.duration_minutes FROM learning_path_courses l JOIN courses k ON k.id=l.course_id WHERE l.path_id=? ORDER BY l.position', (p['id'],)):
            item = progress.get((employee['id'], c['id']))
            done = bool(item and item['completed'])
            status = 'completed' if done else 'unavailable' if c['status'] != 'published' else 'locked' if blocked and p['sequential'] else 'in_progress' if item and item['started'] else 'not_started'
            if not done and status in ('in_progress', 'not_started') and next_course is None:
                next_course = c['id']
            courses.append({'id': c['id'], 'title': c['title'], 'description': c['description'], 'difficulty': c['difficulty'], 'durationMinutes': c['duration_minutes'], 'status': status,
                            'progress': 100 if done else (item['progress'] if item else 0), 'completedAt': item['completedAt'] if item else None})
            blocked = blocked or not done
        completed = sum(1 for c in courses if c['status'] == 'completed')
        paths.append({'id': p['id'], 'title': p['title'], 'description': p['description'], 'sequential': bool(p['sequential']), 'dueDate': p['due_date'], 'courses': courses,
                      'completed': completed, 'total': len(courses), 'progress': round(completed / len(courses) * 100) if courses else 0, 'nextCourseId': next_course,
                      'milestones': [{'title': c['title'], 'completedAt': c['completedAt']} for c in courses if c['status'] == 'completed']})
    return paths


def recommendations(db, employee, progress, assigned, paths, limit=6):
    """Transparent rule-based recommendations; every item lists the rules that selected it."""
    levels, targets = skill_levels(db, employee['id']), role_targets(db, employee['job_role_id'])
    skill_names = {r[0]: r[1] for r in db.execute('SELECT id,name FROM skills')}
    goal_rows = db.execute("SELECT title,skill_id,target_level FROM learning_goals WHERE employee_id=? AND status='active' AND skill_id IS NOT NULL", (employee['id'],))
    goals_by_skill={}
    for goal in goal_rows:goals_by_skill.setdefault(goal['skill_id'],[]).append(dict(goal))
    revision = {}
    for r in db.execute('''SELECT a.title,a.skill_id,a.course_id,MAX(t.percent) AS best FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id
        WHERE t.employee_id=? AND t.status IN ('passed','failed') GROUP BY a.id HAVING MAX(CASE WHEN t.status='passed' THEN 1 ELSE 0 END)=0''', (employee['id'],)):
        if r['skill_id']:
            revision[r['skill_id']] = (r['title'], r['best'])
    path_next = {p['nextCourseId']: p['title'] for p in paths if p['nextCourseId']}
    completed_categories = {c['category'] for c in db.execute('SELECT DISTINCT k.category FROM course_runs r JOIN courses k ON k.id=r.course_id WHERE r.candidate_id=? AND r.completed_at IS NOT NULL', (employee['id'],))}
    department = employee.get('department')
    def candidates():
        # Department-only courses are recommended only inside that department.
        for _,group in groupby(db.execute("SELECT k.id,k.title,k.description,k.difficulty,k.duration_minutes,k.category,k.department_id,s.skill_id,s.level FROM courses k LEFT JOIN course_skills s ON s.course_id=k.id WHERE k.status='published' AND (k.visibility='everyone' OR k.department_id IS NULL OR k.department_id=?) ORDER BY k.title,k.rowid,s.skill_id",(employee.get('department_id') or '',)),key=lambda row:row['id']):
            course=next(group)
            skills=[{'skill_id':row['skill_id'],'level':row['level']} for row in chain((course,),group) if row['skill_id'] is not None]
            item = progress.get((employee['id'], course['id']))
            if (item and (item['completed'] or item['started'])) or (employee['id'], course['id']) in assigned:
                continue
            reasons, score = [], 0
            if course['id'] in path_next:
                reasons.append(f'Next step in your learning path "{path_next[course["id"]]}".'); score += 4
            for s in skills:
                name, current = skill_names.get(s['skill_id'], 'a skill'), levels.get(s['skill_id'], 0)
                target = targets.get(s['skill_id'], 0)
                if current < target and s['level'] > current:
                    reasons.append(f'Closes your {name} gap ({LEVELS[current]} now, {LEVELS[target]} required for your role).'); score += 3
                for goal in goals_by_skill.get(s['skill_id'],()):
                    if s['level'] > current:
                        reasons.append(f'Supports your goal "{goal["title"]}".'); score += 3
                if s['skill_id'] in revision:
                    title, best = revision[s['skill_id']]
                    reasons.append(f'Revision for {title} (best score {best}%).'); score += 2
            if department and course['department_id'] and course['department_id'] == employee['department_id']:
                reasons.append(f'Designed for the {department} department.'); score += 1
            if course['category'] in completed_categories:
                reasons.append(f'Builds on {course["category"]} courses you have completed.'); score += 1
            if score:
                yield {'id': course['id'], 'title': course['title'], 'description': course['description'], 'difficulty': course['difficulty'], 'durationMinutes': course['duration_minutes'],
                                'category': course['category'], 'skills': [skill_names.get(s['skill_id'], '') for s in skills], 'reasons': list(dict.fromkeys(reasons)), 'score': score}
    rank=lambda row:(-row['score'],row['title'])
    if limit is None or limit<0:
        return sorted(candidates(),key=rank)[:limit]
    return heapq.nsmallest(limit,candidates(),key=rank)


def pending_assessments(db, employee, progress):
    """Assessments the employee is expected to take next, with the reason and remaining attempts."""
    used = {r[0]: (r[1], r[2]) for r in db.execute("SELECT assessment_id,COUNT(*),MAX(CASE WHEN status='passed' THEN 1 ELSE 0 END) FROM assessment_attempts WHERE employee_id=? GROUP BY assessment_id", (employee['id'],))}
    levels, targets = skill_levels(db, employee['id']), role_targets(db, employee['job_role_id'])
    items = []
    for a in db.execute("SELECT a.*,c.title AS course_title,s.name AS skill_name FROM assessments a LEFT JOIN courses c ON c.id=a.course_id LEFT JOIN skills s ON s.id=a.skill_id WHERE a.status='published' ORDER BY a.title"):
        count, has_passed = used.get(a['id'], (0, 0))
        if count >= a['max_attempts']:
            continue
        item = progress.get((employee['id'], a['course_id'])) if a['course_id'] else None
        reason = None
        if a['kind'] == 'post' and item and item['ready'] and not item['completed'] and not has_passed:
            reason = f'Required to complete {a["course_title"]}.'
        elif a['kind'] == 'pre' and item and not item['completed'] and count == 0:
            reason = f'Pre-training check for {a["course_title"]}.'
        elif a['kind'] == 'skill' and a['skill_id'] and not has_passed:
            current, target = levels.get(a['skill_id'], 0), targets.get(a['skill_id'], 0)
            if current < (a['skill_level'] or 0) <= max(target, current + 1) and target > current:
                reason = f'Validates {a["skill_name"]} at {LEVELS[a["skill_level"]]} for your role.'
        if reason:
            items.append({'id': a['id'], 'title': a['title'], 'kind': a['kind'], 'reason': reason, 'attemptsLeft': a['max_attempts'] - count})
    return items


# ---------------------------------------------------------------- dashboard

def dashboard(db, user, query):
    employee_scope, course_scope = scope(db, user)
    start, end = query_date(query, 'from'), query_date(query, 'to')
    people = employee_rows(db, employee_scope)
    ids = [p['id'] for p in people]
    progress = progress_index(db, ids, course_scope)
    assignments = assignment_index(db, ids, course_scope)
    pairs = set(progress) | set(assignments)
    statuses = {pair: pair_status(progress.get(pair), assignments.get(pair)) for pair in pairs}
    times = activity_times(db, course_scope)
    id_set = set(ids)
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')
    active = {e for e in ids if any(t and t >= recent_cutoff for t in times.get(e, []))}
    hours = training_seconds(db, course_scope)
    w, p = ids_clause(course_scope, 'r.course_id')
    certificates = [r for r in db.execute(f'SELECT r.candidate_id,x.issued_at FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE {w}', p) if r['candidate_id'] in id_set]
    goal_owners = {r[0] for r in db.execute("SELECT DISTINCT employee_id FROM learning_goals WHERE status='active'")}
    plan_owners = (path_assignment_employees(db) | goal_owners) & id_set
    completed = sum(1 for s in statuses.values() if s == 'completed')
    by_employee = {}
    for (employee, course), status in statuses.items():
        by_employee.setdefault(employee, []).append((course, status))
    assigned_by_employee = {}
    for (employee, course) in assignments:
        assigned_by_employee.setdefault(employee, []).append(statuses[(employee, course)])
    courses = course_rows(db, course_scope)
    published = [c for c in courses.values() if c['status'] == 'published']
    overdue_people = [{'id': e['id'], 'name': e['name'], 'department': e['department'], 'overdue': sum(1 for _, s in by_employee.get(e['id'], []) if s == 'overdue')} for e in people]
    overdue_people = sorted([o for o in overdue_people if o['overdue']], key=lambda o: -o['overdue'])
    kpis = {
        'totalEmployees': len(people), 'activeLearners': len(active), 'publishedCourses': len(published),
        'completionRate': round(completed / len(pairs) * 100) if pairs else 0, 'enrollments': len(pairs), 'completions': completed,
        'certificatesEarned': len(certificates), 'trainingHours': round(sum(hours.get(e, 0) for e in ids) / 3600, 1),
        'pendingMandatory': sum(1 for pair, a in assignments.items() if a['mandatory'] and statuses[pair] != 'completed'),
        'employeesWithPlans': len(plan_owners),
    }
    progress_summary = {
        'activelyLearning': sum(1 for e in ids if any(s == 'in_progress' for _, s in by_employee.get(e, []))),
        'completedAssigned': sum(1 for e, items in assigned_by_employee.items() if items and all(s == 'completed' for s in items)),
        'notStarted': sum(1 for e in ids if not any(s in ('completed', 'in_progress') for _, s in by_employee.get(e, [])) and e not in times),
        'overdue': len(overdue_people), 'overdueEmployees': overdue_people[:8],
    }
    scores = assessment_scores(db, course_scope, start, end)
    period_hours = training_seconds(db, course_scope, start, end) if (start or end) else hours
    departments = {}
    for e in people:
        key = e['department'] or 'Unassigned'
        row = departments.setdefault(key, {'department': key, 'employees': 0, 'participants': 0, 'pairs': 0, 'completed': 0, 'completionsInPeriod': 0, 'scores': [], 'seconds': 0})
        row['employees'] += 1
        employee_times = times.get(e['id'], [])
        if any(in_range(t, start, end) for t in employee_times):
            row['participants'] += 1
        for course, status in by_employee.get(e['id'], []):
            row['pairs'] += 1
            row['completed'] += status == 'completed'
            if status == 'completed' and in_range(progress.get((e['id'], course), {}).get('completedAt'), start, end):
                row['completionsInPeriod'] += 1
        row['scores'] += scores.get(e['id'], [])
        row['seconds'] += period_hours.get(e['id'], 0)
    department_rows = []
    for row in sorted(departments.values(), key=lambda r: r['department']):
        department_rows.append({'department': row['department'], 'employees': row['employees'], 'participants': row['participants'],
                                'participationRate': round(row['participants'] / row['employees'] * 100) if row['employees'] else 0,
                                'completionRate': round(row['completed'] / row['pairs'] * 100) if row['pairs'] else 0, 'completionsInPeriod': row['completionsInPeriod'],
                                'averageScore': average(row['scores']), 'trainingHours': round(row['seconds'] / 3600, 1)})
    return {'scope': 'organisation' if employee_scope is None and course_scope is None else 'team' if employee_scope is not None else 'courses',
            'kpis': kpis, 'progress': progress_summary, 'departments': department_rows, 'period': {'from': start, 'to': end},
            'recent': recent_activity(db, id_set, course_scope, employee_scope is not None), 'upcoming': upcoming_training(db, people, progress, assignments, statuses, courses)}


def recent_activity(db, ids, course_scope, team_only, limit=12):
    events = []
    w, p = ids_clause(course_scope, 'r.course_id')
    for r in db.execute(f'SELECT c.full_name,k.title,x.issued_at,r.candidate_id FROM certificates x JOIN course_runs r ON r.id=x.run_id JOIN candidates c ON c.id=r.candidate_id JOIN courses k ON k.id=r.course_id WHERE {w} ORDER BY x.issued_at DESC LIMIT 40', p):
        if r['candidate_id'] in ids:
            events.append({'type': 'completion', 'at': r['issued_at'], 'text': f'{r["full_name"]} completed {r["title"]} and earned a certificate'})
    for r in db.execute(f"SELECT c.full_name,k.title,x.score,x.status,x.finished_at,x.set_index,r.candidate_id FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id JOIN candidates c ON c.id=r.candidate_id JOIN courses k ON k.id=r.course_id WHERE x.status IN ('passed','failed') AND {w} ORDER BY x.finished_at DESC LIMIT 40", p):
        if r['candidate_id'] in ids:
            events.append({'type': 'assessment', 'at': r['finished_at'], 'text': f'{r["full_name"]} {"passed" if r["status"] == "passed" else "did not pass"} the Module {r["set_index"] + 1} exam in {r["title"]} ({r["score"] * 25}%)'})
    w2, p2 = ids_clause(course_scope, 'a.course_id')
    for r in db.execute(f"SELECT c.full_name,a.title,t.percent,t.status,t.finished_at,t.employee_id FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id JOIN candidates c ON c.id=t.employee_id WHERE t.status IN ('passed','failed') AND {w2} ORDER BY t.finished_at DESC LIMIT 40", p2):
        if r['employee_id'] in ids:
            events.append({'type': 'assessment', 'at': r['finished_at'], 'text': f'{r["full_name"]} {"passed" if r["status"] == "passed" else "did not pass"} {r["title"]} ({r["percent"]}%)'})
    if not team_only:
        w3, p3 = ids_clause(course_scope, 'k.id')
        for r in db.execute(f"SELECT k.title,MIN(e.created_at) AS at FROM admin_events e JOIN courses k ON k.id=e.target_id WHERE e.action='course_saved' AND e.detail LIKE 'published:%' AND {w3} GROUP BY k.id ORDER BY at DESC LIMIT 20", p3):
            events.append({'type': 'course', 'at': r['at'], 'text': f'{r["title"]} was published'})
    for r in db.execute(f"SELECT a.target_type,a.target_id,a.mandatory,a.assigned_at,k.title,COALESCE(c.full_name,d.name,j.name) AS target FROM course_assignments a JOIN courses k ON k.id=a.course_id LEFT JOIN candidates c ON a.target_type='employee' AND c.id=a.target_id LEFT JOIN departments d ON a.target_type='department' AND d.id=a.target_id LEFT JOIN job_roles j ON a.target_type='job_role' AND j.id=a.target_id WHERE {w2.replace('a.course_id', 'k.id')} ORDER BY a.assigned_at DESC LIMIT 20", p2):
        if team_only and not (r['target_type'] == 'employee' and r['target_id'] in ids):
            continue
        events.append({'type': 'assignment', 'at': r['assigned_at'], 'text': f'{r["title"]} assigned to {r["target"] or "a removed target"}{" (mandatory)" if r["mandatory"] else ""}'})
    events.sort(key=lambda e: e['at'] or '', reverse=True)
    return events[:limit]


def upcoming_training(db, people, progress, assignments, statuses, courses):
    now_local, horizon = local_now(), (date.today() + timedelta(days=60)).isoformat()
    sessions = [dict(r) for r in db.execute("""SELECT s.id,s.title,s.kind,s.starts_at,s.ends_at,s.location,s.capacity,c.full_name AS trainer,
        (SELECT COUNT(*) FROM session_registrations g WHERE g.session_id=s.id AND g.status IN ('registered','attended')) AS registered
        FROM training_sessions s LEFT JOIN candidates c ON c.id=s.trainer_id WHERE s.status='scheduled' AND s.ends_at>=? AND s.starts_at<=? ORDER BY s.starts_at LIMIT 8""", (now_local, horizon + 'T23:59'))]
    deadline_limit = (date.today() + timedelta(days=30)).isoformat()
    deadlines = {}
    for pair, a in assignments.items():
        if a['mandatory'] and a['dueDate'] and statuses[pair] != 'completed' and a['dueDate'] <= deadline_limit:
            row = deadlines.setdefault((pair[1], a['dueDate']), {'courseId': pair[1], 'course': courses.get(pair[1], {}).get('title', ''), 'dueDate': a['dueDate'], 'pending': 0, 'overdue': a['dueDate'] < today()})
            row['pending'] += 1
    pending = {}
    for (employee, course), item in progress.items():
        c = courses.get(course)
        if c and c['post_assessment_id'] and item['ready'] and not item['completed']:
            pending.setdefault(course, {'course': c['title'], 'employees': 0})['employees'] += 1
    published_post = {r[0] for r in db.execute("SELECT id FROM assessments WHERE status='published' AND kind='post'")}
    pending_rows = [dict(v, courseId=k) for k, v in pending.items() if courses[k]['post_assessment_id'] in published_post]
    return {'sessions': sessions, 'deadlines': sorted(deadlines.values(), key=lambda d: d['dueDate'])[:10], 'pendingAssessments': pending_rows}


# ---------------------------------------------------------------- reports

REPORTS = {
    'enrollments': 'Course enrollment and completion', 'employees': 'Employee learning progress', 'departments': 'Department training statistics',
    'assessments': 'Assessment performance', 'skills': 'Skill-gap summary', 'compliance': 'Mandatory training compliance', 'certificates': 'Certificate records',
}
TRAINER_REPORTS = ('enrollments', 'assessments', 'certificates')


def report(db, user, query):
    employee_scope, course_scope = scope(db, user)
    kind = query.get('type', ['enrollments'])[0]
    check(kind in REPORTS, 'Unknown report type.')
    check(user['role'] != 'trainer' or kind in TRAINER_REPORTS, 'Trainers can view course-level reports only.', 403)
    start, end = query_date(query, 'from'), query_date(query, 'to')
    department, employee, course = (query.get(k, [''])[0] or None for k in ('department', 'employee', 'course'))
    people = [p for p in employee_rows(db, employee_scope) if (department is None or p['department_id'] == department) and (employee is None or p['id'] == employee)]
    ids = [p['id'] for p in people]
    courses_in_scope = course_scope if course is None else [c for c in (course_scope if course_scope is not None else [course]) if c == course]
    builder = {'enrollments': report_enrollments, 'employees': report_employees, 'departments': report_departments, 'assessments': report_assessments,
               'skills': report_skills, 'compliance': report_compliance, 'certificates': report_certificates}[kind]
    columns, rows, summary = builder(db, people, ids, courses_in_scope, start, end)
    total = len(rows)
    if query.get('export', [''])[0] == '1':
        page, pages, rows = 1, 1, rows[:10000]
    else:
        try:
            page = max(1, int(query.get('page', ['1'])[0]))
        except ValueError:
            page = 1
        pages = max(1, -(-total // PAGE_SIZE))
        page = min(page, pages)
        rows = rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
    return {'type': kind, 'title': REPORTS[kind], 'columns': [{'key': k, 'label': l} for k, l in columns], 'rows': rows, 'summary': summary, 'total': total, 'page': page, 'pages': pages,
            'filters': {'from': start, 'to': end, 'department': department, 'employee': employee, 'course': course}}


def report_enrollments(db, people, ids, course_ids, start, end):
    progress, assignments = progress_index(db, ids, course_ids), assignment_index(db, ids, course_ids)
    courses, by_id = course_rows(db, course_ids), {p['id']: p for p in people}
    rows = []
    for pair in sorted(set(progress) | set(assignments), key=lambda k: (by_id[k[0]]['name'] if k[0] in by_id else '', courses.get(k[1], {}).get('title', ''))):
        if pair[0] not in by_id or pair[1] not in courses:
            continue
        item, assignment = progress.get(pair), assignments.get(pair)
        if (start or end) and not any(in_range(t, start, end) for t in ((item or {}).get('startedAt'), (item or {}).get('completedAt'), (assignment or {}).get('assignedAt'))):
            continue
        person, c = by_id[pair[0]], courses[pair[1]]
        status = pair_status(item, assignment)
        rows.append({'employee': person['name'], 'email': person['email'], 'department': person['department'] or 'Unassigned', 'course': c['title'], 'category': c['category'],
                     'assigned': 'Yes' if assignment else 'No', 'mandatory': 'Yes' if assignment and assignment['mandatory'] else 'No', 'dueDate': (assignment or {}).get('dueDate') or '',
                     'progress': 100 if status == 'completed' else (item or {}).get('progress', 0), 'status': STATUS_LABELS[status], 'completedAt': ((item or {}).get('completedAt') or '')[:10]})
    done = sum(1 for r in rows if r['status'] == 'Completed')
    return ([('employee', 'Employee'), ('department', 'Department'), ('course', 'Course'), ('assigned', 'Assigned'), ('mandatory', 'Mandatory'), ('dueDate', 'Due'), ('progress', 'Progress %'), ('status', 'Status'), ('completedAt', 'Completed')],
            rows, {'Enrollments': len(rows), 'Completed': done, 'Completion rate': f'{round(done / len(rows) * 100) if rows else 0}%'})


def employee_summaries(db, people, ids, course_ids, start, end):
    progress, assignments = progress_index(db, ids, course_ids), assignment_index(db, ids, course_ids)
    seconds, scores = training_seconds(db, course_ids, start, end), assessment_scores(db, course_ids, start, end)
    w, p = ids_clause(course_ids, 'r.course_id')
    certificates = {}
    for r in db.execute(f'SELECT r.candidate_id,x.issued_at FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE {w}', p):
        if in_range(r['issued_at'], start, end):
            certificates[r['candidate_id']] = certificates.get(r['candidate_id'], 0) + 1
    summaries = {e: {'enrolled': 0, 'completed': 0, 'in_progress': 0, 'overdue': 0, 'not_started': 0} for e in ids}
    for pair in set(progress) | set(assignments):
        if pair[0] in summaries:
            status = pair_status(progress.get(pair), assignments.get(pair))
            summaries[pair[0]]['enrolled'] += 1
            summaries[pair[0]][status] += 1
    for e in ids:
        summaries[e].update({'hours': round(seconds.get(e, 0) / 3600, 1), 'certificates': certificates.get(e, 0), 'scores': scores.get(e, [])})
    return summaries


def report_employees(db, people, ids, course_ids, start, end):
    summaries = employee_summaries(db, people, ids, course_ids, start, end)
    rows = []
    for person in people:
        s = summaries[person['id']]
        rows.append({'employee': person['name'], 'email': person['email'], 'department': person['department'] or 'Unassigned', 'jobRole': person['job_role'] or '',
                     'enrolled': s['enrolled'], 'completed': s['completed'], 'inProgress': s['in_progress'], 'overdue': s['overdue'], 'hours': s['hours'],
                     'certificates': s['certificates'], 'averageScore': average(s['scores']) if s['scores'] else ''})
    return ([('employee', 'Employee'), ('department', 'Department'), ('jobRole', 'Job role'), ('enrolled', 'Enrolled'), ('completed', 'Completed'), ('inProgress', 'In progress'), ('overdue', 'Overdue'),
             ('hours', 'Training hours'), ('certificates', 'Certificates'), ('averageScore', 'Avg. score %')], rows,
            {'Employees': len(rows), 'Training hours': round(sum(r['hours'] for r in rows), 1), 'With overdue training': sum(1 for r in rows if r['overdue'])})


def report_departments(db, people, ids, course_ids, start, end):
    summaries = employee_summaries(db, people, ids, course_ids, start, end)
    times = activity_times(db, course_ids)
    groups = {}
    for person in people:
        key = person['department'] or 'Unassigned'
        g = groups.setdefault(key, {'department': key, 'employees': 0, 'participants': 0, 'enrolled': 0, 'completed': 0, 'overdue': 0, 'hours': 0, 'scores': [], 'certificates': 0})
        s = summaries[person['id']]
        g['employees'] += 1
        g['participants'] += any(in_range(t, start, end) for t in times.get(person['id'], []))
        for field in ('enrolled', 'completed', 'overdue', 'hours', 'certificates'):
            g[field] += s[field]
        g['scores'] += s['scores']
    rows = [{'department': g['department'], 'employees': g['employees'], 'participants': g['participants'], 'participation': round(g['participants'] / g['employees'] * 100) if g['employees'] else 0,
             'enrolled': g['enrolled'], 'completed': g['completed'], 'completionRate': round(g['completed'] / g['enrolled'] * 100) if g['enrolled'] else 0, 'overdue': g['overdue'],
             'hours': round(g['hours'], 1), 'certificates': g['certificates'], 'averageScore': average(g['scores']) if g['scores'] else ''} for g in sorted(groups.values(), key=lambda g: g['department'])]
    return ([('department', 'Department'), ('employees', 'Employees'), ('participants', 'Active learners'), ('participation', 'Participation %'), ('enrolled', 'Enrollments'), ('completed', 'Completed'),
             ('completionRate', 'Completion %'), ('overdue', 'Overdue'), ('hours', 'Training hours'), ('certificates', 'Certificates'), ('averageScore', 'Avg. score %')], rows, {'Departments': len(rows)})


def report_assessments(db, people, ids, course_ids, start, end):
    by_id = {p['id']: p for p in people}
    rows = []
    w, p = ids_clause(course_ids, 'r.course_id')
    for r in db.execute(f"SELECT r.candidate_id,k.title,x.set_index,x.attempt_number,x.score,x.status,x.finished_at,x.started_at FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id JOIN courses k ON k.id=r.course_id WHERE x.status<>'in-progress' AND {w}", p):
        if r['candidate_id'] in by_id and in_range(r['finished_at'] or r['started_at'], start, end):
            rows.append({'employee': by_id[r['candidate_id']]['name'], 'department': by_id[r['candidate_id']]['department'] or 'Unassigned', 'assessment': f'{r["title"]}: Module {r["set_index"] + 1} exam',
                         'type': 'Module exam', 'attempt': r['attempt_number'], 'score': '' if r['score'] is None else r['score'] * 25, 'result': r['status'].capitalize(), 'date': (r['finished_at'] or r['started_at'])[:10]})
    w2, p2 = ids_clause(course_ids, 'a.course_id')
    kinds = {'pre': 'Pre-training', 'post': 'Post-training', 'knowledge': 'Knowledge check', 'skill': 'Skill assessment'}
    for r in db.execute(f"SELECT t.employee_id,a.title,a.kind,t.attempt_number,t.percent,t.status,t.finished_at,t.started_at FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id WHERE t.status<>'in-progress' AND {w2}", p2):
        if r['employee_id'] in by_id and in_range(r['finished_at'] or r['started_at'], start, end):
            rows.append({'employee': by_id[r['employee_id']]['name'], 'department': by_id[r['employee_id']]['department'] or 'Unassigned', 'assessment': r['title'], 'type': kinds[r['kind']],
                         'attempt': r['attempt_number'], 'score': '' if r['percent'] is None else r['percent'], 'result': r['status'].capitalize(), 'date': (r['finished_at'] or r['started_at'])[:10]})
    rows.sort(key=lambda r: r['date'], reverse=True)
    graded = [r['score'] for r in rows if r['score'] != '']
    return ([('employee', 'Employee'), ('department', 'Department'), ('assessment', 'Assessment'), ('type', 'Type'), ('attempt', 'Attempt'), ('score', 'Score %'), ('result', 'Result'), ('date', 'Date')], rows,
            {'Attempts': len(rows), 'Pass rate': f'{round(sum(1 for r in rows if r["result"] == "Passed") / len(rows) * 100) if rows else 0}%', 'Average score': f'{average(graded) or 0}%'})


def report_skills(db, people, ids, course_ids, start, end):
    names = {r[0]: r[1] for r in db.execute('SELECT id,name FROM skills')}
    rows = []
    for person in people:
        levels, targets = skill_levels(db, person['id']), role_targets(db, person['job_role_id'])
        for skill in sorted(set(levels) | set(targets), key=lambda s: names.get(s, '')):
            current, target = levels.get(skill, 0), targets.get(skill)
            rows.append({'employee': person['name'], 'department': person['department'] or 'Unassigned', 'jobRole': person['job_role'] or '', 'skill': names.get(skill, ''),
                         'current': LEVELS[current], 'target': LEVELS[target] if target else '', 'gap': max(0, (target or 0) - current), 'status': 'Gap' if target and current < target else 'Meets target' if target else 'No role target'})
    return ([('employee', 'Employee'), ('department', 'Department'), ('jobRole', 'Job role'), ('skill', 'Skill'), ('current', 'Current level'), ('target', 'Role target'), ('gap', 'Gap (levels)'), ('status', 'Status')], rows,
            {'Skill records': len(rows), 'Open gaps': sum(1 for r in rows if r['status'] == 'Gap')})


def report_compliance(db, people, ids, course_ids, start, end):
    progress, assignments = progress_index(db, ids, course_ids), assignment_index(db, ids, course_ids)
    courses, by_id = course_rows(db, course_ids), {p['id']: p for p in people}
    rows = []
    for pair, a in assignments.items():
        if not a['mandatory'] or pair[0] not in by_id or ((start or end) and not in_range(a['dueDate'], start, end)):
            continue
        status, item = pair_status(progress.get(pair), a), progress.get(pair)
        rows.append({'employee': by_id[pair[0]]['name'], 'department': by_id[pair[0]]['department'] or 'Unassigned', 'course': courses[pair[1]]['title'], 'dueDate': a['dueDate'] or '',
                     'status': 'Compliant' if status == 'completed' else 'Overdue' if status == 'overdue' else 'Pending', 'progress': 100 if status == 'completed' else (item or {}).get('progress', 0),
                     'completedAt': ((item or {}).get('completedAt') or '')[:10]})
    rows.sort(key=lambda r: (r['status'] != 'Overdue', r['dueDate'] or '9999', r['employee']))
    compliant = sum(1 for r in rows if r['status'] == 'Compliant')
    return ([('employee', 'Employee'), ('department', 'Department'), ('course', 'Mandatory course'), ('dueDate', 'Due'), ('progress', 'Progress %'), ('status', 'Status'), ('completedAt', 'Completed')], rows,
            {'Mandatory assignments': len(rows), 'Compliance': f'{round(compliant / len(rows) * 100) if rows else 0}%', 'Overdue': sum(1 for r in rows if r['status'] == 'Overdue')})


def report_certificates(db, people, ids, course_ids, start, end):
    by_id = {p['id']: p for p in people}
    w, p = ids_clause(course_ids, 'r.course_id')
    rows = [{'employee': by_id[r['candidate_id']]['name'], 'department': by_id[r['candidate_id']]['department'] or 'Unassigned', 'course': r['course_title'], 'issuedAt': r['issued_at'][:10], 'certificate': r['id']}
            for r in db.execute(f'SELECT x.*,r.candidate_id FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE {w} ORDER BY x.issued_at DESC', p)
            if r['candidate_id'] in by_id and in_range(r['issued_at'], start, end)]
    return ([('employee', 'Employee'), ('department', 'Department'), ('course', 'Course'), ('issuedAt', 'Issued'), ('certificate', 'Certificate ID')], rows, {'Certificates': len(rows)})
