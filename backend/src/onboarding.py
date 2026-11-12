"""Automatic employee onboarding: templates of published courses by department and job role, started when HR adds an employee.

A template lists published courses, each due at a milestone ("Day 1", "Day 30"). Starting onboarding creates ordinary
course assignments for the employee, so deadlines, reminders, Training Compliance and My Learning treat them like any other
assignment. A course the employee already has through any assignment is linked, never assigned twice.

Each onboarding keeps a snapshot of its courses and milestones, so editing or archiving a template never rewrites an
employee's plan or its history. Progress and completion are worked out from course records when they are read.
Onboarding is complete when every mandatory course is complete; optional courses are reported separately.
"""
from datetime import date, datetime, timedelta, timezone

from admin import audit
from analytics import assignment_index, employee_rows, progress_index, scope
from compliance import FORMATS, to_csv, to_xlsx
from deadlines import STATUS_LABELS as DEADLINE_LABELS, deadline_status, end_of_day, format_deadline, local_date, parse_utc, portal_timezone
import reminders
from services import APIError, allowed, check, notify, now, require, uid

STATUSES = ('draft', 'active', 'inactive', 'archived')
# Archive is reachable from every state; an archived template is restored as inactive.
TRANSITIONS = {'draft': ('active', 'archived'), 'active': ('inactive', 'archived'), 'inactive': ('active', 'archived'), 'archived': ('inactive',)}
MAX_MILESTONES, MAX_COURSES, MAX_DAY = 12, 40, 365
PAGE_SIZE = 25
PLAN_STATUSES = {'not_started': 'Not started', 'in_progress': 'In progress', 'overdue': 'Overdue', 'completed': 'Completed', 'no_courses': 'No courses'}
NOT_STARTED_MESSAGES = {
    'no_template': 'No active onboarding template matches this employee\'s department and job role, so no courses were assigned. '
                   'Set one up in Onboarding → Templates, then start their onboarding from the Needs onboarding tab.',
    'ambiguous': 'More than one active onboarding template matches this employee equally, so no courses were assigned. '
                 'Choose one in Onboarding → Needs onboarding.',
}


def today():
    return datetime.now(timezone.utc).astimezone(portal_timezone()).date()


def date_value(value, label):
    """A YYYY-MM-DD date from a request, or None when blank."""
    if value in (None, ''):
        return None
    check(isinstance(value, str), f'{label} must be a date.')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        check(False, f'{label} must be a date in YYYY-MM-DD format.')
    check(date(2000, 1, 1) <= parsed <= date(2100, 12, 31), f'{label} must be between 2000 and 2100.')
    return parsed.isoformat()


def milestone_date(start_date, day):
    """Day 1 is the start date itself."""
    return (date.fromisoformat(start_date) + timedelta(days=day - 1)).isoformat()


def plan_deadline(start_date, day, floor):
    """End of the milestone day in the portal timezone, never earlier than `floor` (the end of the day onboarding began).
    A joining date already past when onboarding starts must not make a course overdue the moment it is assigned."""
    return max(end_of_day(milestone_date(start_date, day)), floor)


def start_floor(started_at):
    return end_of_day(local_date(started_at))


# ---------------------------------------------------------------- templates

def template_input(db, data):
    name = data.get('name')
    check(isinstance(name, str) and 2 <= len(name.strip()) <= 120, 'Give the template a name of 2 to 120 characters.')
    description = data.get('description') or ''
    check(isinstance(description, str) and len(description) <= 1000, 'The description must contain at most 1000 characters.')
    department = data.get('departmentId') or None
    check(department is None or (isinstance(department, str) and db.execute('SELECT 1 FROM departments WHERE id=?', (department,)).fetchone() is not None), 'Select a valid department.')
    roles = data.get('jobRoleIds') or []
    check(isinstance(roles, list) and len(roles) <= 100 and all(isinstance(r, str) for r in roles), 'Select valid job roles.')
    roles = list(dict.fromkeys(roles))
    for role in roles:
        check(db.execute('SELECT 1 FROM job_roles WHERE id=?', (role,)).fetchone() is not None, 'Select valid job roles.')
    milestones = data.get('milestones')
    check(isinstance(milestones, list) and 1 <= len(milestones) <= MAX_MILESTONES, f'Add 1 to {MAX_MILESTONES} milestones.')
    days = {}
    for m in milestones:
        check(isinstance(m, dict) and type(m.get('day')) is int and 1 <= m['day'] <= MAX_DAY, f'Each milestone needs a day from 1 to {MAX_DAY}.')
        title = m.get('title') or ''
        check(isinstance(title, str) and len(title.strip()) <= 80, 'Milestone names must contain at most 80 characters.')
        check(m['day'] not in days, f'Day {m["day"]} is listed twice.')
        days[m['day']] = title.strip() or f'Day {m["day"]}'
    courses = data.get('courses')
    check(isinstance(courses, list) and 1 <= len(courses) <= MAX_COURSES, f'Add 1 to {MAX_COURSES} courses.')
    seen, rows = set(), []
    for c in courses:
        check(isinstance(c, dict) and isinstance(c.get('courseId'), str), 'Select a course in every course row.')
        course = db.execute('SELECT id,title,status FROM courses WHERE id=?', (c['courseId'],)).fetchone()
        check(course is not None, 'A selected course no longer exists.', 404)
        check(course['status'] == 'published', f'"{course["title"]}" is not published. Templates can use published courses only.')
        check(course['id'] not in seen, f'"{course["title"]}" is listed twice.')
        check(type(c.get('day')) is int and c['day'] in days, f'Choose a milestone for "{course["title"]}".')
        check(type(c.get('mandatory')) is bool, f'Mark "{course["title"]}" as mandatory or optional.')
        seen.add(course['id'])
        rows.append((course['id'], c['day'], c['mandatory']))
    check(any(mandatory for _, _, mandatory in rows), 'Mark at least one course as mandatory: onboarding is complete when every mandatory course is.')
    # A milestone with no courses yet is allowed (HR may lay out Day 1/7/30/60/90 first); employee plans leave it out.
    return name.strip(), description.strip(), department, roles, days, rows


def template_roles(db, template_id):
    return {r[0] for r in db.execute('SELECT job_role_id FROM onboarding_template_roles WHERE template_id=?', (template_id,))}


def conflict(db, template_id, department, roles):
    """Another active template with the same scope, which would make matching ambiguous; None if there is none."""
    for other in db.execute("SELECT id,name,department_id FROM onboarding_templates WHERE status='active' AND id<>?", (template_id,)).fetchall():
        if other['department_id'] != department:
            continue
        theirs = template_roles(db, other['id'])
        if (not theirs and not roles) or (theirs & set(roles)):
            return other['name']
    return None


def stored_template(db, identity):
    row = db.execute('SELECT * FROM onboarding_templates WHERE id=?', (identity,)).fetchone() if isinstance(identity, str) else None
    check(row is not None, 'Onboarding template was not found.', 404)
    return row


def save_template(db, user, data):
    """Create a template (as a draft or active) or edit one. Editing never changes onboardings that already started."""
    require(user, 'onboarding.manage')
    existing = stored_template(db, data['id']) if data.get('id') is not None else None
    check(existing is None or existing['status'] != 'archived', 'Archived templates cannot be edited. Restore it first.', 409)
    name, description, department, roles, days, courses = template_input(db, data)
    status = existing['status'] if existing else (data.get('status') or 'draft')
    check(status in STATUSES and (existing or status in ('draft', 'active')), 'A new template starts as a draft or active.')
    identity = existing['id'] if existing else uid()
    if status == 'active':
        other = conflict(db, identity, department, roles)
        check(other is None, f'The active template "{other}" already covers this department and these job roles. Deactivate it first, or choose different job roles.', 409)
    stamp = now()
    if existing:
        db.execute('UPDATE onboarding_templates SET name=?,description=?,department_id=?,updated_by=?,updated_at=? WHERE id=?', (name, description, department, user['id'], stamp, identity))
        for table in ('onboarding_template_roles', 'onboarding_template_milestones', 'onboarding_template_courses'):
            db.execute(f'DELETE FROM {table} WHERE template_id=?', (identity,))
    else:
        db.execute('INSERT INTO onboarding_templates(id,name,description,department_id,status,created_by,created_at,updated_by,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                   (identity, name, description, department, status, user['id'], stamp, user['id'], stamp))
    db.executemany('INSERT INTO onboarding_template_roles(template_id,job_role_id) VALUES (?,?)', [(identity, r) for r in roles])
    db.executemany('INSERT INTO onboarding_template_milestones(template_id,day,title) VALUES (?,?,?)', [(identity, d, t) for d, t in sorted(days.items())])
    db.executemany('INSERT INTO onboarding_template_courses(template_id,course_id,day,mandatory,position) VALUES (?,?,?,?,?)',
                   [(identity, c, d, int(m), i) for i, (c, d, m) in enumerate(courses)])
    audit(db, user['id'], 'onboarding_template_updated' if existing else 'onboarding_template_created', identity,
          f'{name}: {len(courses)} courses ({sum(m for _, _, m in courses)} mandatory), {len(days)} milestones, {status}')
    return {'templateId': identity, **templates_payload(db, user)}


def set_status(db, user, identity, data):
    require(user, 'onboarding.manage')
    row = stored_template(db, identity)
    status = data.get('status')
    check(status in TRANSITIONS.get(row['status'], ()), f'A {row["status"]} template cannot become {status}.', 409)
    if status == 'active':
        courses = db.execute('SELECT k.title,k.status,t.mandatory FROM onboarding_template_courses t JOIN courses k ON k.id=t.course_id WHERE t.template_id=?', (identity,)).fetchall()
        check(courses, 'Add at least one course before activating this template.', 409)
        unpublished = [c['title'] for c in courses if c['status'] != 'published']
        check(not unpublished, f'"{unpublished[0] if unpublished else ""}" is no longer published. Remove it from the template before activating.', 409)
        check(any(c['mandatory'] for c in courses if c['status'] == 'published'), 'Mark at least one course as mandatory before activating.', 409)
        other = conflict(db, identity, row['department_id'], template_roles(db, identity))
        check(other is None, f'The active template "{other}" already covers this department and these job roles. Deactivate it first.', 409)
    db.execute('UPDATE onboarding_templates SET status=?,updated_by=?,updated_at=? WHERE id=?', (status, user['id'], now(), identity))
    audit(db, user['id'], 'onboarding_template_status', identity, f'{row["name"]}: {row["status"]} to {status}')
    return templates_payload(db, user)


def templates_payload(db, user):
    require(user, 'onboarding.manage')
    departments = {r['id']: r['name'] for r in db.execute('SELECT id,name FROM departments')}
    roles = {r['id']: r['name'] for r in db.execute('SELECT id,name FROM job_roles')}
    courses = {r['id']: dict(r) for r in db.execute('SELECT id,title,status,category,duration_minutes FROM courses')}
    usage = {r[0]: (r[1], r[2]) for r in db.execute("SELECT template_id,SUM(status='active'),COUNT(*) FROM employee_onboarding WHERE template_id IS NOT NULL GROUP BY template_id")}
    order = {'active': 0, 'draft': 1, 'inactive': 2, 'archived': 3}
    items = []
    for t in sorted(db.execute('SELECT t.*,u.full_name AS updated_by_name FROM onboarding_templates t LEFT JOIN candidates u ON u.id=t.updated_by').fetchall(),
                    key=lambda t: (order[t['status']], t['name'].casefold())):
        role_ids = sorted(template_roles(db, t['id']), key=lambda r: roles.get(r, '').casefold())
        milestones = [{'day': r['day'], 'title': r['title']} for r in db.execute('SELECT day,title FROM onboarding_template_milestones WHERE template_id=? ORDER BY day', (t['id'],))]
        rows = db.execute('SELECT course_id,day,mandatory FROM onboarding_template_courses WHERE template_id=? ORDER BY day,position', (t['id'],)).fetchall()
        course_items = [{'courseId': r['course_id'], 'title': courses[r['course_id']]['title'], 'day': r['day'], 'mandatory': bool(r['mandatory']),
                         'published': courses[r['course_id']]['status'] == 'published'} for r in rows if r['course_id'] in courses]
        warnings = []
        if t['department_id'] and t['department_id'] not in departments:
            warnings.append('Its department was removed, so this template matches nobody.')
        if role_ids and not any(r in roles for r in role_ids):
            warnings.append('All its job roles were removed, so this template matches nobody.')
        warnings += [f'"{c["title"]}" is not published, so it will be skipped.' for c in course_items if not c['published']]
        active_count, total = usage.get(t['id'], (0, 0))
        items.append({'id': t['id'], 'name': t['name'], 'description': t['description'], 'status': t['status'], 'departmentId': t['department_id'],
                      'department': departments.get(t['department_id'], 'Removed department') if t['department_id'] else 'All departments',
                      'jobRoleIds': role_ids, 'jobRoles': [roles.get(r, 'Removed job role') for r in role_ids], 'milestones': milestones, 'courses': course_items,
                      'mandatoryCount': sum(c['mandatory'] for c in course_items), 'onboardingsActive': active_count or 0, 'onboardingsTotal': total,
                      'updatedAt': t['updated_at'], 'updatedBy': t['updated_by_name'] or '', 'warnings': warnings})
    return {'templates': items, 'options': {'departments': sorted(([k, v] for k, v in departments.items()), key=lambda x: x[1].casefold()),
                                            'jobRoles': sorted(([k, v] for k, v in roles.items()), key=lambda x: x[1].casefold()),
                                            'courses': sorted(([c['id'], c['title']] for c in courses.values() if c['status'] == 'published'), key=lambda x: x[1].casefold())}}


# ---------------------------------------------------------------- matching and starting

def active_templates(db):
    """Active templates with their job roles, read in two queries whatever the number of templates."""
    templates = db.execute("SELECT * FROM onboarding_templates WHERE status='active'").fetchall()
    roles = {}
    for template_id, role in db.execute("SELECT r.template_id,r.job_role_id FROM onboarding_template_roles r JOIN onboarding_templates t ON t.id=r.template_id WHERE t.status='active'"):
        roles.setdefault(template_id, set()).add(role)
    return [(t, roles.get(t['id'], set())) for t in templates]


def matching(db, employee, templates=None):
    """(template, None) for the most specific active template, or (None, 'no_template' | 'ambiguous').
    A template naming job roles is more specific than one naming only a department, which beats one for everyone.
    Pass `templates` from active_templates() to match many employees without re-reading them."""
    found = []
    for t, roles in active_templates(db) if templates is None else templates:
        if t['department_id'] and t['department_id'] != employee['department_id']:
            continue
        if roles and employee['job_role_id'] not in roles:
            continue
        found.append((2 * bool(roles) + bool(t['department_id']), t))
    if not found:
        return None, 'no_template'
    best = max(score for score, _ in found)
    winners = [t for score, t in found if score == best]
    return (winners[0], None) if len(winners) == 1 else (None, 'ambiguous')


def default_start_date(employee):
    """Milestones count from the joining date; a past or missing one starts the plan today."""
    joined, current = employee['joining_date'], today().isoformat()
    return joined if joined and joined > current else current


def start(db, actor_id, employee_id, template_id, source, start_date=None):
    """Assign a template's courses to one employee. Courses already assigned to them are linked instead."""
    employee = db.execute('SELECT * FROM candidates WHERE id=?', (employee_id,)).fetchone() if isinstance(employee_id, str) else None
    check(employee is not None, 'Employee was not found.', 404)
    check(employee['is_active'] and employee['role'] != 'admin', 'Onboarding is for active employees, not administrators.', 409)
    check(db.execute("SELECT 1 FROM employee_onboarding WHERE employee_id=? AND status='active'", (employee_id,)).fetchone() is None,
          f'{employee["full_name"]} already has onboarding in progress.', 409)
    template = stored_template(db, template_id)
    check(template['status'] == 'active', 'Only active templates can be used to start onboarding.', 409)
    start_date = start_date or employee['joining_date'] or today().isoformat()
    titles = {r['day']: r['title'] for r in db.execute('SELECT day,title FROM onboarding_template_milestones WHERE template_id=?', (template_id,))}
    courses = db.execute('''SELECT t.course_id,t.day,t.mandatory,k.title,k.status FROM onboarding_template_courses t JOIN courses k ON k.id=t.course_id
        WHERE t.template_id=? ORDER BY t.day,t.position''', (template_id,)).fetchall()
    assigned = assignment_index(db, [employee_id])
    identity, stamp = uid(), now()
    floor = start_floor(stamp)
    db.execute('INSERT INTO employee_onboarding(id,employee_id,template_id,template_name,start_date,joining_date,source,started_by,started_at) VALUES (?,?,?,?,?,?,?,?,?)',
               (identity, employee_id, template_id, template['name'], start_date, employee['joining_date'], source, actor_id, stamp))
    created = []
    for position, c in enumerate(courses):
        deadline = plan_deadline(start_date, c['day'], floor) if c['mandatory'] else None
        pair, assignment, note = (employee_id, c['course_id']), None, ''
        if c['status'] != 'published':
            link, note, deadline = 'skipped', 'The course is not published.', None
        elif pair in assigned:
            # Already assigned individually, by department or by job role: that assignment and its deadline stay in force.
            link, assignment, note = 'existing', assigned[pair]['assignmentId'], 'Already assigned'
        else:
            link, assignment = 'created', uid()
            db.execute('''INSERT INTO course_assignments(id,course_id,target_type,target_id,mandatory,due_date,deadline_at,original_deadline_at,note,assigned_by,assigned_at)
                VALUES (?,?,'employee',?,?,?,?,?,?,?,?)''', (assignment, c['course_id'], employee_id, c['mandatory'], local_date(deadline) if deadline else None,
                                                              deadline, deadline, f'Onboarding: {template["name"]}'[:500], actor_id, stamp))
            created.append(c['course_id'])
        db.execute('''INSERT INTO employee_onboarding_courses(onboarding_id,course_id,course_title,day,milestone_title,mandatory,deadline_at,assignment_id,link,note,position)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (identity, c['course_id'], c['title'], c['day'], titles.get(c['day'], f'Day {c["day"]}'), c['mandatory'], deadline, assignment, link, note, position))
    usable = [c for c in courses if c['status'] == 'published']
    first = next((c for c in usable if c['mandatory']), None)
    body = (f'{len(usable)} course{"s" if len(usable) != 1 else ""} ({sum(c["mandatory"] for c in usable)} mandatory) have been added to My Learning.'
            + (f' First milestone: {titles.get(first["day"], "Day 1")}, due {format_deadline(plan_deadline(start_date, first["day"], floor), " at ")}.' if first else ''))
    notify(db, [employee_id], 'assignment', f'Your onboarding plan: {template["name"]}', body, 'courses', f'onboarding:{identity}:started')
    notification = db.execute('SELECT id FROM notifications WHERE employee_id=? AND dedupe_key=?', (employee_id, f'onboarding:{identity}:started')).fetchone()[0]
    # One plan notice announces every new course, so the reminder pass does not send a separate "assigned" notice for each.
    in_force = assignment_index(db, [employee_id], created) if created else {}
    for course in created:
        reminders.record_announcement(db, employee_id, course, in_force[(employee_id, course)], notification)
    audit(db, actor_id, 'onboarding_started', employee_id,
          f'{template["name"]} ({source}), start {start_date}: {len(created)} assigned, {sum(1 for c in courses if c["status"] == "published") - len(created)} already assigned, '
          f'{sum(1 for c in courses if c["status"] != "published")} skipped')
    return {'onboardingId': identity, 'template': template['name'], 'assigned': len(created), 'linked': len(usable) - len(created), 'skipped': len(courses) - len(usable)}


def auto_start(db, actor, employee_id):
    """Called when HR adds an employee. Never blocks creating the account: problems come back as a message for HR."""
    employee = db.execute('SELECT * FROM candidates WHERE id=?', (employee_id,)).fetchone()
    if employee is None or employee['role'] == 'admin':
        return None
    template, reason = matching(db, employee)
    if template is None:
        audit(db, actor['id'], 'onboarding_not_started', employee_id, reason)
        return {'status': reason, 'message': NOT_STARTED_MESSAGES[reason]}
    db.execute('SAVEPOINT onboarding_start')
    try:
        result = start(db, actor['id'], employee_id, template['id'], 'automatic')
    except APIError as error:
        db.execute('ROLLBACK TO onboarding_start')
        db.execute('RELEASE onboarding_start')
        return {'status': 'failed', 'message': f'Onboarding was not started: {error.message}'}
    db.execute('RELEASE onboarding_start')
    parts = [f'{result["assigned"]} course{"s" if result["assigned"] != 1 else ""} assigned']
    if result['linked']:
        parts.append(f'{result["linked"]} already assigned')
    if result['skipped']:
        parts.append(f'{result["skipped"]} skipped because they are no longer published')
    return {'status': 'started', **result, 'message': f'Onboarding "{result["template"]}" started: {", ".join(parts)}.'}


def start_manual(db, user, data):
    """HR starts onboarding for an existing employee, with the matching template or one they choose."""
    require(user, 'onboarding.manage')
    employee_id = data.get('employeeId')
    employee = db.execute('SELECT * FROM candidates WHERE id=?', (employee_id,)).fetchone() if isinstance(employee_id, str) else None
    check(employee is not None, 'Employee was not found.', 404)
    template_id = data.get('templateId') or None
    if template_id is None:
        template, reason = matching(db, employee)
        check(template is not None, NOT_STARTED_MESSAGES.get(reason, ''), 409)
        template_id = template['id']
    start_date = date_value(data.get('startDate'), 'Start date') or default_start_date(employee)
    result = start(db, user['id'], employee_id, template_id, 'manual', start_date)
    return {**result, 'message': f'Onboarding "{result["template"]}" started for {employee["full_name"]}.'}


def cancel(db, user, identity):
    """Stop an onboarding. Its assignments for courses not yet completed are removed; completed records stay."""
    require(user, 'onboarding.manage')
    row = db.execute("SELECT o.*,c.full_name FROM employee_onboarding o JOIN candidates c ON c.id=o.employee_id WHERE o.id=?", (identity,)).fetchone() if isinstance(identity, str) else None
    check(row is not None, 'Onboarding was not found.', 404)
    check(row['status'] == 'active', 'This onboarding has already been cancelled.', 409)
    created = [r['assignment_id'] for r in db.execute("SELECT assignment_id FROM employee_onboarding_courses WHERE onboarding_id=? AND link='created'", (identity,))]
    progress = progress_index(db, [row['employee_id']])
    removed = 0
    for assignment in created:
        a = db.execute('SELECT course_id FROM course_assignments WHERE id=?', (assignment,)).fetchone()
        if a and not (progress.get((row['employee_id'], a['course_id'])) or {}).get('completed'):
            db.execute('DELETE FROM course_assignments WHERE id=?', (assignment,))
            removed += 1
    db.execute("UPDATE employee_onboarding SET status='cancelled',cancelled_by=?,cancelled_at=? WHERE id=?", (user['id'], now(), identity))
    audit(db, user['id'], 'onboarding_cancelled', row['employee_id'], f'{row["template_name"]} for {row["full_name"]}: {removed} open assignments removed')
    return {'message': f'Onboarding cancelled for {row["full_name"]}. {removed} unfinished course assignment{"s" if removed != 1 else ""} removed.'}


# ---------------------------------------------------------------- progress

def plan_view(onboarding, items, progress, assigned, soon, at, current_titles, results=None):
    """One onboarding with its courses, milestones and completion, from the snapshot and the employee's course records."""
    employee = onboarding['employee_id']
    floor = start_floor(onboarding['started_at'])
    courses = []
    for item in items:
        pair = (employee, item['course_id'])
        p, a = progress.get(pair), assigned.get(pair)
        view = {'courseId': item['course_id'], 'title': current_titles.get(item['course_id'], item['course_title']), 'day': item['day'], 'milestone': item['milestone_title'],
                'mandatory': bool(item['mandatory']), 'link': item['link'], 'note': item['note'], 'progress': 0, 'completedAt': None, 'dueSoon': False,
                'assessment': (results or {}).get(item['course_id'])}
        if item['link'] == 'skipped':
            view.update(status='skipped', statusLabel='Skipped', deadlineAt=None)
        elif item['course_id'] not in current_titles:
            view.update(status='removed', statusLabel='Course removed', deadlineAt=None)
        else:
            # The assignment in force decides the deadline, as it does for reminders and compliance.
            source = a if a else {'deadlineAt': item['deadline_at']}
            status = deadline_status(p, source, soon, at)
            completed = bool(p and p['completed'])
            view.update(deadlineAt=source.get('deadlineAt'), progress=100 if completed else (p or {}).get('progress', 0), completedAt=p['completedAt'] if completed else None,
                        dueSoon=status == 'due_soon', started=bool(p and p['started']))
            if status == 'due_soon':
                status = 'in_progress' if p and p['started'] else 'not_started'
            view.update(status=status, statusLabel=DEADLINE_LABELS[status])
        view['deadlineDisplay'] = format_deadline(view['deadlineAt']) if view['deadlineAt'] else None
        view['completed'] = view['status'] in ('completed_on_time', 'completed_late')
        courses.append(view)
    counted = [c for c in courses if c['status'] not in ('skipped', 'removed')]
    mandatory, optional = [c for c in counted if c['mandatory']], [c for c in counted if not c['mandatory']]
    done = sum(c['completed'] for c in mandatory)
    overdue = sum(c['status'] == 'overdue' for c in mandatory)
    if not mandatory:
        status = 'no_courses'
    elif done == len(mandatory):
        status = 'completed'
    elif overdue:
        status = 'overdue'
    elif any(c['completed'] or c.get('started') for c in counted):
        status = 'in_progress'
    else:
        status = 'not_started'
    milestones = []
    for day in sorted({c['day'] for c in courses}):
        group = [c for c in counted if c['day'] == day]
        required = [c for c in group if c['mandatory']]
        deadline = plan_deadline(onboarding['start_date'], day, floor)
        complete = bool(group) and all(c['completed'] for c in (required or group))
        state = 'completed' if complete else 'overdue' if required and at >= parse_utc(deadline) else 'upcoming'
        milestones.append({'day': day, 'title': next((c['milestone'] for c in courses if c['day'] == day), f'Day {day}'), 'date': milestone_date(onboarding['start_date'], day),
                           'deadlineAt': deadline, 'deadlineDisplay': format_deadline(deadline), 'state': state, 'courses': len(group),
                           'mandatoryTotal': len(required), 'mandatoryDone': sum(c['completed'] for c in required)})
    upcoming = next((m for m in milestones if m['state'] != 'completed' and m['mandatoryTotal']), None)
    completed_at = max(c['completedAt'] for c in mandatory) if status == 'completed' else None
    return {'id': onboarding['id'], 'employeeId': employee, 'template': onboarding['template_name'], 'templateId': onboarding['template_id'], 'source': onboarding['source'],
            'startDate': onboarding['start_date'], 'joiningDate': onboarding['joining_date'], 'startedAt': onboarding['started_at'], 'state': onboarding['status'],
            'status': status, 'statusLabel': PLAN_STATUSES[status], 'percent': round(done / len(mandatory) * 100) if mandatory else 0,
            'mandatoryDone': done, 'mandatoryTotal': len(mandatory), 'overdueMandatory': overdue, 'pendingMandatory': len(mandatory) - done,
            'optionalDone': sum(c['completed'] for c in optional), 'optionalTotal': len(optional), 'completedAt': completed_at,
            'completedDisplay': format_deadline(completed_at) if completed_at else None, 'nextMilestone': upcoming, 'milestones': milestones, 'courses': courses}


def assessment_results(db, employee, course_ids):
    """Best final-assessment result per course: the course assessment, or module exams passed for 3-module courses."""
    results = {}
    for course in db.execute(f"SELECT id,format,post_assessment_id FROM courses WHERE id IN ({','.join('?' * len(course_ids))})", list(course_ids)).fetchall() if course_ids else []:
        if course['post_assessment_id']:
            r = db.execute("SELECT MAX(percent),MAX(status='passed'),COUNT(*) FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status IN ('passed','failed')",
                           (course['post_assessment_id'], employee)).fetchone()
            if r[2]:
                results[course['id']] = {'label': f'Best score {r[0]}%', 'percent': r[0], 'passed': bool(r[1]), 'attempts': r[2]}
        elif course['format'] != 'lessons':
            passed = db.execute("""SELECT COUNT(DISTINCT x.set_index) FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id
                WHERE r.candidate_id=? AND r.course_id=? AND x.status='passed'""", (employee, course['id'])).fetchone()[0]
            attempted = db.execute("""SELECT COUNT(*) FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id WHERE r.candidate_id=? AND r.course_id=? AND x.status IN ('passed','failed')""",
                                   (employee, course['id'])).fetchone()[0]
            if attempted:
                results[course['id']] = {'label': f'{passed} of 3 module exams passed', 'percent': None, 'passed': passed == 3, 'attempts': attempted}
    return results


def views_for(db, rows, detailed=False, at=None):
    """Plan views for several onboardings, with course records read once."""
    at = at or datetime.now(timezone.utc)
    employees = sorted({r['employee_id'] for r in rows})
    if not employees:
        return {}
    progress, assigned = progress_index(db, employees), assignment_index(db, employees)
    soon = reminders.due_soon_seconds(db)
    titles = {r[0]: r[1] for r in db.execute('SELECT id,title FROM courses')}
    items = {}
    ids = [r['id'] for r in rows]
    for chunk in range(0, len(ids), 500):
        part = ids[chunk:chunk + 500]
        for item in db.execute(f"SELECT * FROM employee_onboarding_courses WHERE onboarding_id IN ({','.join('?' * len(part))}) ORDER BY day,position", part):
            items.setdefault(item['onboarding_id'], []).append(item)
    views = {}
    for row in rows:
        own = items.get(row['id'], [])
        results = assessment_results(db, row['employee_id'], [i['course_id'] for i in own]) if detailed else None
        views[row['id']] = plan_view(row, own, progress, assigned, soon, at, titles, results)
    return views


def my_onboarding(db, user):
    row = db.execute("SELECT * FROM employee_onboarding WHERE employee_id=? AND status='active'", (user['id'],)).fetchone()
    return {'onboarding': views_for(db, [row], detailed=True)[row['id']] if row else None}


def detail(db, user, identity):
    row = db.execute('SELECT * FROM employee_onboarding WHERE id=?', (identity,)).fetchone() if isinstance(identity, str) else None
    check(row is not None, 'Onboarding was not found.', 404)
    employees = visible_employees(db, user)
    check(employees is None or row['employee_id'] in employees, 'You can view onboarding only for employees you manage.', 403)
    person = db.execute('SELECT c.full_name,c.email,d.name AS department,j.name AS job_role,m.full_name AS manager FROM candidates c LEFT JOIN departments d ON d.id=c.department_id '
                        'LEFT JOIN job_roles j ON j.id=c.job_role_id LEFT JOIN candidates m ON m.id=c.manager_id WHERE c.id=?', (row['employee_id'],)).fetchone()
    return {'onboarding': {**views_for(db, [row], detailed=True)[row['id']], 'employee': person['full_name'], 'email': person['email'],
                           'department': person['department'] or 'Unassigned', 'jobRole': person['job_role'] or 'Unassigned', 'manager': person['manager'] or ''}}


def visible_employees(db, user):
    """None for the whole organisation; a set of employee ids for managers. Others are refused."""
    check(user['role'] in ('admin', 'hr', 'manager'), 'You do not have permission to view onboarding.', 403)
    ids = scope(db, user)[0]
    return None if ids is None else set(ids)


# ---------------------------------------------------------------- reminders

def _note(db, employee, key, title, body, link='courses'):
    """One notification per key; returns 1 when it is new."""
    if db.execute('SELECT 1 FROM notifications WHERE employee_id=? AND dedupe_key=?', (employee, key)).fetchone():
        return 0
    notify(db, [employee], 'onboarding', title, body, link, key)
    return 1


def milestone_reminders(db, employee, at, progress, assigned):
    """Called from the reminder pass for one active employee. Course deadlines already have their own reminders, so this adds
    one summary when a milestone is coming up with mandatory courses unfinished, one when it is missed (also to the manager),
    and one when onboarding is complete. Notification keys make every one of them happen once."""
    person = db.execute('SELECT full_name,is_active,manager_id FROM candidates WHERE id=?', (employee,)).fetchone()
    if not person or not person['is_active']:
        return 0
    manager = db.execute('SELECT id FROM candidates WHERE id=? AND is_active=1', (person['manager_id'],)).fetchone() if person['manager_id'] else None
    rows = db.execute("SELECT * FROM employee_onboarding WHERE employee_id=? AND status='active'", (employee,)).fetchall()
    if not rows:
        return 0
    soon = reminders.due_soon_seconds(db)
    titles = {r[0]: r[1] for r in db.execute('SELECT id,title FROM courses')}
    sent = 0
    for row in rows:
        items = db.execute('SELECT * FROM employee_onboarding_courses WHERE onboarding_id=? ORDER BY day,position', (row['id'],)).fetchall()
        view = plan_view(row, items, progress, assigned, soon, at, titles)
        base = f'onboarding:{row["id"]}'
        if view['status'] == 'completed':
            sent += _note(db, employee, f'{base}:completed', 'Onboarding complete', f'You have completed every mandatory course in "{row["template_name"]}". Well done.')
            if manager:
                sent += _note(db, manager['id'], f'{base}:completed:manager', f'{person["full_name"]} completed onboarding', f'All mandatory courses in "{row["template_name"]}" are complete.', 'onboarding')
            continue
        for m in view['milestones']:
            left = m['mandatoryTotal'] - m['mandatoryDone']
            if not left or m['state'] == 'completed':
                continue
            deadline = parse_utc(m['deadlineAt'])
            courses = f'{left} mandatory course{"s" if left != 1 else ""}'
            if at >= deadline:
                sent += _note(db, employee, f'{base}:day{m["day"]}:missed', f'Onboarding milestone missed: {m["title"]}',
                              f'{courses} from "{m["title"]}" in your onboarding plan {"are" if left != 1 else "is"} not complete. They are still open: please finish them as soon as possible.')
                if manager:
                    sent += _note(db, manager['id'], f'{base}:day{m["day"]}:missed:manager', f'{person["full_name"]} missed an onboarding milestone',
                                  f'{courses} from "{m["title"]}" in "{row["template_name"]}" {"are" if left != 1 else "is"} not complete.', 'onboarding')
            elif (deadline - at).total_seconds() <= soon and deadline - timedelta(seconds=soon) > parse_utc(row['started_at']):
                # As with course reminders, a milestone already inside the window when onboarding began gets no "coming up" notice.
                sent += _note(db, employee, f'{base}:day{m["day"]}:upcoming', f'Onboarding milestone coming up: {m["title"]}',
                              f'{courses} from "{m["title"]}" {"are" if left != 1 else "is"} due by {m["deadlineDisplay"]}.')
    return sent


# ---------------------------------------------------------------- HR and manager reporting

def read_filters(query):
    get = lambda key: query.get(key, [''])[0].strip()
    values = {key: get(key) for key in ('q', 'department', 'jobRole', 'status')}
    check(not values['status'] or values['status'] in PLAN_STATUSES, 'Unknown onboarding status.')
    values['from'], values['to'] = date_value(get('from'), 'From date'), date_value(get('to'), 'To date')
    check(not (values['from'] and values['to'] and values['from'] > values['to']), 'The joining date range must start on or before its end.')
    return values


def _matches(person, joined, f):
    search = f['q'].casefold()
    return ((not f['department'] or (person['department_id'] or '__none__') == f['department']) and (not f['jobRole'] or (person['job_role_id'] or '__none__') == f['jobRole'])
            and (not f['from'] or (joined and joined >= f['from'])) and (not f['to'] or (joined and joined <= f['to']))
            and (not search or any(search in (person[k] or '').casefold() for k in ('name', 'email'))))


def _page(items, query, field):
    pages = max(1, -(-len(items) // PAGE_SIZE))
    try:
        page = min(max(1, int(query.get(field, ['1'])[0])), pages)
    except ValueError:
        page = 1
    return {'rows': items[(page - 1) * PAGE_SIZE:page * PAGE_SIZE], 'total': len(items), 'page': page, 'pages': pages}


def _groups(rows, key, label):
    found = {}
    for r in rows:
        found.setdefault((r[key], r[label]), []).append(r)
    return [{'id': k[0], 'name': k[1], 'employees': len(g), 'completed': sum(r['status'] == 'completed' for r in g), 'overdue': sum(r['status'] == 'overdue' for r in g),
             'averagePercent': round(sum(r['percent'] for r in g) / len(g))} for k, g in sorted(found.items(), key=lambda item: (item[0][1] == 'Unassigned', item[0][1].casefold()))]


def report_rows(db, user, query):
    f = read_filters(query)
    employees = visible_employees(db, user)
    people = {p['id']: p for p in employee_rows(db, None if employees is None else sorted(employees))}
    onboardings = [r for r in db.execute("SELECT * FROM employee_onboarding WHERE status='active' ORDER BY started_at DESC").fetchall() if r['employee_id'] in people]
    views = views_for(db, onboardings)
    rows = []
    for o in onboardings:
        person, v = people[o['employee_id']], views[o['id']]
        joined = o['joining_date'] or o['start_date']
        if not _matches(person, joined, f) or (f['status'] and v['status'] != f['status']):
            continue
        nxt = v['nextMilestone']
        rows.append({'onboardingId': o['id'], 'employeeId': person['id'], 'employee': person['name'], 'email': person['email'], 'department': person['department'] or 'Unassigned',
                     'departmentId': person['department_id'] or '__none__', 'jobRole': person['job_role'] or 'Unassigned', 'jobRoleId': person['job_role_id'] or '__none__',
                     'template': v['template'], 'joiningDate': o['joining_date'], 'startDate': o['start_date'], 'source': o['source'], 'status': v['status'], 'statusLabel': v['statusLabel'],
                     'percent': v['percent'], 'mandatoryDone': v['mandatoryDone'], 'mandatoryTotal': v['mandatoryTotal'], 'overdueMandatory': v['overdueMandatory'],
                     'pendingMandatory': v['pendingMandatory'], 'optionalDone': v['optionalDone'], 'optionalTotal': v['optionalTotal'],
                     'nextMilestone': {'title': nxt['title'], 'date': nxt['date'], 'state': nxt['state']} if nxt else None, 'completedAt': v['completedAt']})
    rows.sort(key=lambda r: ({'overdue': 0, 'not_started': 1, 'in_progress': 2, 'no_courses': 3, 'completed': 4}[r['status']], r['employee'].casefold()))
    return f, people, onboardings, rows


def monitoring(db, user, query):
    f, people, onboardings, rows = report_rows(db, user, query)
    open_rows = [r for r in rows if r['status'] != 'completed']
    payload = {'scope': 'team' if user['role'] == 'manager' else 'organisation', 'filters': f,
               'summary': {'onboarding': len(open_rows), 'completed': len(rows) - len(open_rows), 'pendingEmployees': sum(r['pendingMandatory'] > 0 for r in rows),
                           'overdueMandatory': sum(r['overdueMandatory'] for r in rows), 'overdueEmployees': sum(r['status'] == 'overdue' for r in rows),
                           'averagePercent': round(sum(r['percent'] for r in rows) / len(rows)) if rows else 0},
               'departments': _groups(rows, 'departmentId', 'department'), 'jobRoles': _groups(rows, 'jobRoleId', 'jobRole'), 'table': _page(rows, query, 'page'),
               'options': {'departments': sorted({(p['department_id'] or '__none__', p['department'] or 'Unassigned') for p in people.values()}, key=lambda x: (x[0] == '__none__', x[1].casefold())),
                           'jobRoles': sorted({(p['job_role_id'] or '__none__', p['job_role'] or 'Unassigned') for p in people.values()}, key=lambda x: (x[0] == '__none__', x[1].casefold()))},
               'canManage': allowed(user, 'onboarding.manage')}
    if payload['canManage']:
        # Active employees with no onboarding in progress or finished: what HR still has to start, and why it did not start itself.
        started = {o['employee_id'] for o in onboardings}
        waiting = []
        # Joining dates and templates are read once; the best template depends only on department and job role.
        joining = {r[0]: r[1] for r in db.execute('SELECT id,joining_date FROM candidates WHERE is_active=1')}
        templates, best = active_templates(db), {}
        for p in people.values():
            if p['id'] in started or p['role'] == 'admin':
                continue
            joined = joining.get(p['id'])
            if not _matches(p, joined, f):
                continue
            key = (p['department_id'], p['job_role_id'])
            if key not in best:
                best[key] = matching(db, {'department_id': key[0], 'job_role_id': key[1]}, templates)
            template, reason = best[key]
            waiting.append({'employeeId': p['id'], 'employee': p['name'], 'email': p['email'], 'department': p['department'] or 'Unassigned', 'jobRole': p['job_role'] or 'Unassigned',
                            'joiningDate': joined, 'defaultStartDate': default_start_date({'joining_date': joined}), 'templateId': template['id'] if template else None,
                            'template': template['name'] if template else None, 'reason': reason})
        waiting.sort(key=lambda r: (r['joiningDate'] or '', r['employee'].casefold()), reverse=True)
        payload['needsOnboarding'] = _page(waiting, query, 'waitingPage')
        payload['templates'] = [[t['id'], t['name']] for t in db.execute("SELECT id,name FROM onboarding_templates WHERE status='active' ORDER BY name")]
    return payload


def export(db, user, query):
    kind = query.get('format', ['csv'])[0]
    check(kind in FORMATS, 'Choose CSV or Excel.')
    f, _, _, rows = report_rows(db, user, query)
    columns = ['Employee Name', 'Email', 'Department', 'Job Role', 'Onboarding Template', 'Joining Date', 'Start Date', 'Status', 'Completion %', 'Mandatory Completed',
               'Mandatory Total', 'Overdue Mandatory', 'Optional Completed', 'Optional Total', 'Next Milestone', 'Next Milestone Date', 'Completed On']
    values = [[r['employee'], r['email'], r['department'], r['jobRole'], r['template'], r['joiningDate'] or '', r['startDate'], r['statusLabel'], r['percent'], r['mandatoryDone'],
               r['mandatoryTotal'], r['overdueMandatory'], r['optionalDone'], r['optionalTotal'], (r['nextMilestone'] or {}).get('title', ''), (r['nextMilestone'] or {}).get('date', ''),
               local_date(r['completedAt']) if r['completedAt'] else ''] for r in rows]
    audit(db, user['id'], 'onboarding_report_exported', 'onboarding', f'{kind}; {len(rows)} rows')
    return (to_csv if kind == 'csv' else to_xlsx)(columns, values), FORMATS[kind], f'shimentox-onboarding-{today().isoformat()}.{kind}'
