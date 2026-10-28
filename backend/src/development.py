"""Employee learning & development: organisation setup, assignments, learning paths, skills, assessments,
training sessions, notifications, goals, materials, and the employee-facing learning views.

Every route checks permissions on the server. Managers are limited to their direct reports and trainers to
the courses, assessments, and sessions they own.
"""
import json
import random
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from admin import audit, course_view, media_reference, owns_course
from analytics import (LEVELS, UNITS, assignment_index, dashboard, employee_paths, local_now, pair_status, pending_assessments,
                       progress_index, recommendations, report, role_targets, skill_levels, today)
from notifications import announce
import course_import
from database import BACKEND, VIDEO_ROOT, public_curriculum
from services import allowed, can_view_course, check, current_run, issue_certificate, notify, now, require, text, uid

VIDEO_TYPES = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.vtt': 'text/vtt; charset=utf-8', '.jpg': 'image/jpeg'}
MATERIALS = BACKEND / 'data/materials'
MATERIAL_TYPES = {'.pdf': 'application/pdf', '.ppt': 'application/vnd.ms-powerpoint', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                  '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                  '.xls': 'application/vnd.ms-excel', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                  '.txt': 'text/plain; charset=utf-8', '.csv': 'text/csv; charset=utf-8', '.mp4': 'video/mp4', '.webm': 'video/webm', '.vtt': 'text/vtt; charset=utf-8',
                  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
MAX_MATERIAL_BYTES = 50 * 1024 * 1024
TARGETS = {'employee': ('candidates', "AND is_active=1 AND role<>'admin'", 'id'), 'department': ('departments', '', 'department_id'), 'job_role': ('job_roles', '', 'job_role_id')}
KINDS = ('pre', 'post', 'knowledge', 'skill')


# ---------------------------------------------------------------- validation helpers

def opt_text(data, field, maximum, label=None):
    value = data.get(field) or ''
    check(isinstance(value, str) and len(value.strip()) <= maximum, f'{label or field} must contain at most {maximum} characters.')
    return value.strip()


def opt_date(data, field, label='Date'):
    value = data.get(field) or None
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        check(False, f'{label} must be a valid date.')


def date_time(data, field, label):
    try:
        return datetime.fromisoformat(data.get(field)).strftime('%Y-%m-%dT%H:%M')
    except (TypeError, ValueError):
        check(False, f'Enter a valid {label}.')


def integer(data, field, low, high, label, default=None):
    value = data.get(field, default)
    check(type(value) is int and low <= value <= high, f'{label} must be a whole number from {low} to {high}.')
    return value


def flag(data, field, default=False):
    value = data.get(field, default)
    check(type(value) is bool, f'{field} must be true or false.')
    return value


def choice(data, field, options, label, default=None):
    value = data.get(field, default)
    check(value in options, f'Select a valid {label}.')
    return value


def ref(db, data, field, table, label, condition='', required=False):
    value = data.get(field) or None
    if value is None:
        check(not required, f'Select a {label}.')
        return None
    check(isinstance(value, str) and db.execute(f'SELECT 1 FROM {table} WHERE id=? {condition}', (value,)).fetchone() is not None, f'Select a valid {label}.')
    return value


def pages(items, query, size=25):
    try:
        page = max(1, int(query.get('page', ['1'])[0]))
    except ValueError:
        page = 1
    count = max(1, -(-len(items) // size))
    page = min(page, count)
    return {'items': items[(page - 1) * size:page * size], 'page': page, 'pages': count, 'total': len(items)}


def me(db, user):
    row = db.execute('''SELECT c.id,c.full_name AS name,c.email,c.role,c.department_id,c.job_role_id,c.manager_id,c.job_title,d.name AS department,j.name AS job_role,m.full_name AS manager
        FROM candidates c LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id LEFT JOIN candidates m ON m.id=c.manager_id WHERE c.id=?''', (user['id'],)).fetchone()
    return dict(row)


def team(db, manager_id):
    return {r[0] for r in db.execute('SELECT id FROM candidates WHERE manager_id=? AND is_active=1', (manager_id,))}


def target_input(db, actor, data, mandatory=False):
    kind = choice(data, 'targetType', TARGETS, 'assignment target type')
    table, condition, _ = TARGETS[kind]
    target = ref(db, data, 'targetId', table, 'employee, department, or job role', condition, required=True)
    if actor['role'] == 'manager':
        check(kind == 'employee' and target in team(db, actor['id']), 'Managers can assign training only to their direct reports.', 403)
        check(not mandatory, 'Mandatory training is assigned by HR or administrators.', 403)
    return kind, target


def target_employees(db, kind, target):
    column = TARGETS[kind][2]
    return [r[0] for r in db.execute(f"SELECT id FROM candidates WHERE {column}=? AND is_active=1 AND role<>'admin'", (target,))]


def target_name(db, kind, target):
    row = db.execute({'employee': 'SELECT full_name FROM candidates WHERE id=?', 'department': 'SELECT name FROM departments WHERE id=?', 'job_role': 'SELECT name FROM job_roles WHERE id=?'}[kind], (target,)).fetchone()
    return row[0] if row else 'Removed'


def course_or_404(db, identity):
    row = db.execute('SELECT * FROM courses WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'Course was not found.', 404)
    return row


def questions_input(data):
    questions = data.get('questions')
    check(isinstance(questions, list) and 1 <= len(questions) <= 200, 'Add between 1 and 200 questions to the question bank.')
    clean = []
    for i, q in enumerate(questions):
        check(isinstance(q, list) and len(q) in (3, 4, 5), f'Question {i + 1}: use [prompt, options, correct option index, explanation, optional code].')
        check(isinstance(q[0], str) and 1 <= len(q[0].strip()) <= 2000, f'Question {i + 1}: question text is required.')
        check(isinstance(q[1], list) and 2 <= len(q[1]) <= 6 and all(isinstance(o, str) and 1 <= len(o.strip()) <= 1000 for o in q[1]), f'Question {i + 1}: provide 2-6 answer options.')
        check(type(q[2]) is int and 0 <= q[2] < len(q[1]), f'Question {i + 1}: invalid correct option index (indices start at 0).')
        explanation = q[3] if len(q) >= 4 else ''
        check(isinstance(explanation, str) and len(explanation) <= 2000, f'Question {i + 1}: explanation is too long.')
        code = q[4] if len(q) == 5 else ''
        check(isinstance(code, str) and len(code) <= 5000, f'Question {i + 1}: the code snippet must contain at most 5000 characters.')
        # A code snippet turns a multiple-choice item into a coding question; it is kept only when present.
        clean.append([q[0].strip(), [o.strip() for o in q[1]], q[2], explanation.strip()] + ([code.rstrip()] if code.strip() else []))
    return clean


# ---------------------------------------------------------------- organisation

def org(db, user):
    return {'departments': [dict(r) for r in db.execute("SELECT d.id,d.name,(SELECT COUNT(*) FROM candidates c WHERE c.department_id=d.id AND c.is_active=1) AS employees FROM departments d ORDER BY d.name")],
            'jobRoles': [dict(r) for r in db.execute('SELECT j.id,j.name,j.department_id AS departmentId,d.name AS department FROM job_roles j LEFT JOIN departments d ON d.id=j.department_id ORDER BY j.name')],
            'categories': [r[0] for r in db.execute('SELECT name FROM course_categories ORDER BY name')],
            'skills': [dict(r) for r in db.execute('SELECT id,name,category FROM skills ORDER BY name')],
            'courses': [dict(r) for r in db.execute('SELECT id,title,status,category FROM courses ORDER BY title')],
            'trainers': [dict(r) for r in db.execute("SELECT id,full_name AS name,role FROM candidates WHERE is_active=1 AND role IN ('admin','hr','trainer') ORDER BY full_name")],
            'managers': [dict(r) for r in db.execute("SELECT id,full_name AS name FROM candidates WHERE is_active=1 AND role IN ('manager','hr','admin') ORDER BY full_name")],
            'levels': [{'value': k, 'label': v} for k, v in LEVELS.items() if k]}


def save_org_item(db, user, kind, data):
    require(user, 'org.manage')
    if kind == 'categories':
        name = text(data, 'name', 2, 80)
        if data.get('delete') is True:
            check(db.execute('SELECT 1 FROM courses WHERE category=?', (name,)).fetchone() is None, 'This category is used by courses. Move those courses to another category first.', 409)
            db.execute('DELETE FROM course_categories WHERE name=?', (name,))
        else:
            db.execute('INSERT INTO course_categories VALUES (?,?)', (name, now()))
        audit(db, user['id'], 'category_deleted' if data.get('delete') is True else 'category_created', name, name)
        return org(db, user)
    table = 'departments' if kind == 'departments' else 'job_roles'
    identity = data.get('id') or None
    if identity is not None:
        check(isinstance(identity, str) and db.execute(f'SELECT 1 FROM {table} WHERE id=?', (identity,)).fetchone() is not None, 'Record was not found.', 404)
    if data.get('delete') is True:
        check(identity is not None, 'Record was not found.', 404)
        target_type = 'department' if kind == 'departments' else 'job_role'
        db.execute('DELETE FROM course_assignments WHERE target_type=? AND target_id=?', (target_type, identity))
        db.execute('DELETE FROM path_assignments WHERE target_type=? AND target_id=?', (target_type, identity))
        db.execute(f'DELETE FROM {table} WHERE id=?', (identity,))
        audit(db, user['id'], f'{target_type}_deleted', identity)
        return org(db, user)
    name = text(data, 'name', 2, 80)
    if kind == 'departments':
        if identity:
            db.execute('UPDATE departments SET name=? WHERE id=?', (name, identity))
        else:
            identity = uid()
            db.execute('INSERT INTO departments VALUES (?,?,?)', (identity, name, now()))
    else:
        department = ref(db, data, 'departmentId', 'departments', 'department')
        if identity:
            db.execute('UPDATE job_roles SET name=?,department_id=? WHERE id=?', (name, department, identity))
        else:
            identity = uid()
            db.execute('INSERT INTO job_roles VALUES (?,?,?,?)', (identity, name, department, now()))
    audit(db, user['id'], f'{kind[:-1].replace("-", "_")}_saved', identity, name)
    return org(db, user)


def people(db, user):
    if user['role'] == 'manager':
        ids = team(db, user['id'])
    else:
        ids = None
    rows = db.execute('''SELECT c.id,c.full_name AS name,c.email,c.role,c.department_id AS departmentId,c.job_role_id AS jobRoleId,c.manager_id AS managerId,d.name AS department,j.name AS jobRole
        FROM candidates c LEFT JOIN departments d ON d.id=c.department_id LEFT JOIN job_roles j ON j.id=c.job_role_id WHERE c.is_active=1 AND c.role<>'admin' ORDER BY c.full_name''')
    return {'people': [dict(r) for r in rows if ids is None or r['id'] in ids]}


# ---------------------------------------------------------------- assignments

def assignment_rows(db, user, course_id=None):
    rows = []
    sql = '''SELECT a.*,k.title AS course,m.full_name AS assigned_by_name FROM course_assignments a JOIN courses k ON k.id=a.course_id LEFT JOIN candidates m ON m.id=a.assigned_by'''
    params = ()
    if course_id:
        sql += ' WHERE a.course_id=?'
        params = (course_id,)
    reports = team(db, user['id']) if user['role'] == 'manager' else None
    for r in db.execute(sql + ' ORDER BY a.assigned_at DESC LIMIT 300', params).fetchall():
        if reports is not None and not (r['target_type'] == 'employee' and r['target_id'] in reports):
            continue
        employees = target_employees(db, r['target_type'], r['target_id'])
        progress = progress_index(db, employees, [r['course_id']])
        rows.append({'id': r['id'], 'courseId': r['course_id'], 'course': r['course'], 'targetType': r['target_type'], 'targetId': r['target_id'], 'target': target_name(db, r['target_type'], r['target_id']),
                     'mandatory': bool(r['mandatory']), 'dueDate': r['due_date'], 'note': r['note'], 'assignedBy': r['assigned_by_name'], 'assignedAt': r['assigned_at'],
                     'employees': len(employees), 'completed': sum(1 for p in progress.values() if p['completed']), 'canRemove': user['role'] != 'manager' or r['assigned_by'] == user['id']})
    return rows


def create_assignment(db, user, data):
    require(user, 'courses.assign')
    course = course_or_404(db, data.get('courseId') if isinstance(data.get('courseId'), str) else '')
    check(course['status'] == 'published', 'Only published courses can be assigned.', 409)
    mandatory = flag(data, 'mandatory')
    kind, target = target_input(db, user, data, mandatory)
    due = opt_date(data, 'dueDate', 'Due date')
    check(due is None or due >= today(), 'The completion deadline cannot be in the past.')
    check(not mandatory or due is not None, 'Mandatory training requires a completion deadline.')
    note = opt_text(data, 'note', 500, 'Note')
    existing = db.execute('SELECT * FROM course_assignments WHERE course_id=? AND target_type=? AND target_id=?', (course['id'], kind, target)).fetchone()
    if existing:
        check(user['role'] != 'manager' or not existing['mandatory'], 'This mandatory assignment is managed by HR.', 403)
        identity = existing['id']
        db.execute('UPDATE course_assignments SET mandatory=?,due_date=?,note=?,assigned_by=?,assigned_at=? WHERE id=?', (int(mandatory), due, note, user['id'], now(), identity))
    else:
        identity = uid()
        db.execute('INSERT INTO course_assignments VALUES (?,?,?,?,?,?,?,?,?)', (identity, course['id'], kind, target, int(mandatory), due, note, user['id'], now()))
    label = 'Mandatory training assigned' if mandatory else ('Training recommended by your manager' if user['role'] == 'manager' else 'New training assigned')
    notify(db, target_employees(db, kind, target), 'assignment', f'{label}: {course["title"]}', f'Complete by {due}.' if due else 'Open My Learning to start.', 'courses', f'assigned:{identity}:{due or ""}:{int(mandatory)}')
    audit(db, user['id'], 'course_assigned', identity, f'{course["title"]} -> {kind}:{target_name(db, kind, target)}{" (mandatory)" if mandatory else ""}')
    return {'assignments': assignment_rows(db, user, course['id'])}


def delete_assignment(db, user, identity):
    require(user, 'courses.assign')
    row = db.execute('SELECT * FROM course_assignments WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'Assignment was not found.', 404)
    check(user['role'] != 'manager' or row['assigned_by'] == user['id'], 'Managers can remove only the training they recommended.', 403)
    db.execute('DELETE FROM course_assignments WHERE id=?', (identity,))
    audit(db, user['id'], 'assignment_removed', identity, row['course_id'])
    return {'assignments': assignment_rows(db, user, row['course_id'])}


# ---------------------------------------------------------------- course preview, resources, materials

def owned_course(db, user, identity):
    require(user, 'courses.manage')
    course = course_or_404(db, identity)
    check(owns_course(user, course), 'Trainers can manage only the courses they own.', 403)
    return course


def course_resources(db, course_id):
    return [{'id': r['id'], 'moduleIndex': r['module_index'], 'title': r['title'], 'kind': r['kind'], 'url': r['url']}
            for r in db.execute('SELECT * FROM course_resources WHERE course_id=? ORDER BY module_index IS NULL,module_index,created_at', (course_id,))]


def preview(db, user, identity):
    course = owned_course(db, user, identity)
    return {'course': public_curriculum(db, identity), 'lessons': json.loads(course['lessons_json']), 'courseInfo': course_view(course, False, db), 'resources': course_resources(db, identity)}


def save_resource(db, user, course_id, data):
    owned_course(db, user, course_id)
    title = text(data, 'title', 2, 150)
    kind = choice(data, 'kind', ('document', 'presentation', 'video', 'link'), 'resource type')
    url = text(data, 'url', 1, 2000)
    check(media_reference(url), 'Resource location must be an uploaded material, an assets/ path, or an HTTPS URL.')
    material = re.fullmatch(r'api/materials/([0-9a-f-]{36})', url)
    check(material is None or db.execute('SELECT 1 FROM materials WHERE id=?', (material.group(1),)).fetchone() is not None, 'The uploaded material was not found.')
    module = data.get('moduleIndex')
    check(module is None or (type(module) is int and 0 <= module <= 2), 'Select a valid module.')
    identity = uid()
    db.execute('INSERT INTO course_resources VALUES (?,?,?,?,?,?,?,?)', (identity, course_id, module, title, kind, url, user['id'], now()))
    audit(db, user['id'], 'resource_added', course_id, title)
    if db.execute('SELECT status FROM courses WHERE id=?', (course_id,)).fetchone()[0] == 'published':
        from notifications import resource_added
        resource_added(db, course_id, title, identity)
    return {'resources': course_resources(db, course_id)}


def delete_resource(db, user, identity):
    row = db.execute('SELECT * FROM course_resources WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'Resource was not found.', 404)
    owned_course(db, user, row['course_id'])
    db.execute('DELETE FROM course_resources WHERE id=?', (identity,))
    audit(db, user['id'], 'resource_removed', row['course_id'], row['title'])
    return {'resources': course_resources(db, row['course_id'])}


def store_material(db, user, filename, body):
    require(user, 'courses.manage')
    name = Path(filename or '').name.strip()
    suffix = Path(name).suffix.lower()
    check(2 <= len(name) <= 200 and suffix in MATERIAL_TYPES, 'Upload a PDF, Office document, text, CSV, image, caption, or MP4/WebM video file.', 415)
    check(0 < len(body) <= MAX_MATERIAL_BYTES, 'Files must be between 1 byte and 50 MB.', 413)
    MATERIALS.mkdir(parents=True, exist_ok=True)
    identity = uid()
    stored = identity + suffix
    (MATERIALS / stored).write_bytes(body)
    db.execute('INSERT INTO materials VALUES (?,?,?,?,?,?,?)', (identity, name, MATERIAL_TYPES[suffix], len(body), stored, user['id'], now()))
    audit(db, user['id'], 'material_uploaded', identity, name)
    return {'material': {'id': identity, 'name': name, 'size': len(body), 'url': f'api/materials/{identity}'}}


def material_file(db, user, identity):
    """Materials live outside the public folder; employees may open only those used by published courses."""
    row = db.execute('SELECT * FROM materials WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'File was not found.', 404)
    url = f'api/materials/{identity}'
    if not allowed(user, 'courses.manage'):
        used = db.execute("SELECT 1 FROM course_resources r JOIN courses c ON c.id=r.course_id WHERE r.url=? AND c.status='published'", (url,)).fetchone() or \
            db.execute("SELECT 1 FROM courses WHERE status='published' AND instr(lessons_json,?)>0", (url,)).fetchone()
        check(used is not None, 'This file is not part of a published course.', 403)
    path = (MATERIALS / row['stored_name']).resolve()
    check(path.is_relative_to(MATERIALS.resolve()) and path.is_file(), 'File was not found.', 404)
    return path, row['content_type'], row['original_name']


# ---------------------------------------------------------------- learning paths

def path_courses(db, path_id):
    return [dict(r) for r in db.execute('SELECT k.id,k.title,k.status FROM learning_path_courses l JOIN courses k ON k.id=l.course_id WHERE l.path_id=? ORDER BY l.position', (path_id,))]


def path_list(db, user):
    check(allowed(user, 'paths.manage') or allowed(user, 'courses.assign'), 'You do not have permission to manage learning paths.', 403)
    reports = team(db, user['id']) if user['role'] == 'manager' else None
    result = []
    for p in db.execute('SELECT p.*,c.full_name AS author FROM learning_paths p LEFT JOIN candidates c ON c.id=p.created_by ORDER BY p.title').fetchall():
        courses = path_courses(db, p['id'])
        assignments, employees = [], set()
        for a in db.execute('SELECT * FROM path_assignments WHERE path_id=? ORDER BY assigned_at', (p['id'],)):
            members = set(target_employees(db, a['target_type'], a['target_id']))
            if reports is not None:
                members &= reports
                if a['target_type'] != 'employee' or a['target_id'] not in reports:
                    employees |= members
                    continue
            employees |= members
            assignments.append({'id': a['id'], 'targetType': a['target_type'], 'target': target_name(db, a['target_type'], a['target_id']), 'dueDate': a['due_date'],
                                'canRemove': user['role'] != 'manager' or a['assigned_by'] == user['id']})
        progress = progress_index(db, list(employees), [c['id'] for c in courses]) if employees and courses else {}
        finished = sum(1 for e in employees if courses and all(progress.get((e, c['id']), {}).get('completed') for c in courses))
        result.append({'id': p['id'], 'title': p['title'], 'description': p['description'], 'status': p['status'], 'sequential': bool(p['sequential']), 'author': p['author'],
                       'courses': courses, 'assignments': assignments, 'assignedEmployees': len(employees), 'completedEmployees': finished,
                       'canEdit': allowed(user, 'paths.manage') and (user['role'] != 'trainer' or p['created_by'] == user['id'])})
    return {'paths': result}


def save_path(db, user, data):
    require(user, 'paths.manage')
    identity = data.get('id') or None
    old = db.execute('SELECT * FROM learning_paths WHERE id=?', (identity,)).fetchone() if identity else None
    check(identity is None or old is not None, 'Learning path was not found.', 404)
    check(old is None or user['role'] != 'trainer' or old['created_by'] == user['id'], 'Trainers can edit only the learning paths they created.', 403)
    title, description = text(data, 'title', 2, 150), opt_text(data, 'description', 2000, 'Description')
    status = choice(data, 'status', ('draft', 'published', 'archived'), 'status', 'draft')
    sequential = flag(data, 'sequential', True)
    course_ids = data.get('courseIds')
    check(isinstance(course_ids, list) and 1 <= len(course_ids) <= 30 and len(set(course_ids)) == len(course_ids), 'Add between 1 and 30 different courses to the path.')
    statuses = []
    for c in course_ids:
        row = db.execute('SELECT status FROM courses WHERE id=?', (c,)).fetchone() if isinstance(c, str) else None
        check(row is not None, 'Select valid courses for the path.')
        statuses.append(row['status'])
    check(status != 'published' or all(s == 'published' for s in statuses), 'Publish every course in the path before publishing the path.', 409)
    if old:
        db.execute('UPDATE learning_paths SET title=?,description=?,status=?,sequential=?,updated_at=? WHERE id=?', (title, description, status, int(sequential), now(), identity))
    else:
        identity = uid()
        db.execute('INSERT INTO learning_paths VALUES (?,?,?,?,?,?,?,?)', (identity, title, description, status, int(sequential), user['id'], now(), now()))
    db.execute('DELETE FROM learning_path_courses WHERE path_id=?', (identity,))
    for position, c in enumerate(course_ids):
        db.execute('INSERT INTO learning_path_courses VALUES (?,?,?)', (identity, position, c))
    audit(db, user['id'], 'path_saved', identity, f'{status}: {title}')
    return path_list(db, user)


def assign_path(db, user, path_id, data):
    require(user, 'courses.assign')
    path = db.execute('SELECT * FROM learning_paths WHERE id=?', (path_id,)).fetchone()
    check(path is not None, 'Learning path was not found.', 404)
    check(path['status'] == 'published', 'Publish the learning path before assigning it.', 409)
    kind, target = target_input(db, user, data)
    due = opt_date(data, 'dueDate', 'Due date')
    check(due is None or due >= today(), 'The target date cannot be in the past.')
    existing = db.execute('SELECT id FROM path_assignments WHERE path_id=? AND target_type=? AND target_id=?', (path_id, kind, target)).fetchone()
    identity = existing['id'] if existing else uid()
    if existing:
        db.execute('UPDATE path_assignments SET due_date=?,assigned_by=?,assigned_at=? WHERE id=?', (due, user['id'], now(), identity))
    else:
        db.execute('INSERT INTO path_assignments VALUES (?,?,?,?,?,?,?)', (identity, path_id, kind, target, due, user['id'], now()))
    notify(db, target_employees(db, kind, target), 'assignment', f'Learning path assigned: {path["title"]}', f'Target date {due}.' if due else 'Open Learning Paths to begin.', 'paths', f'path:{identity}:{due or ""}')
    audit(db, user['id'], 'path_assigned', identity, f'{path["title"]} -> {kind}:{target_name(db, kind, target)}')
    return path_list(db, user)


def delete_path_assignment(db, user, identity):
    require(user, 'courses.assign')
    row = db.execute('SELECT * FROM path_assignments WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'Assignment was not found.', 404)
    check(user['role'] != 'manager' or row['assigned_by'] == user['id'], 'Managers can remove only the paths they assigned.', 403)
    db.execute('DELETE FROM path_assignments WHERE id=?', (identity,))
    audit(db, user['id'], 'path_assignment_removed', identity, row['path_id'])
    return path_list(db, user)


def path_progress(db, user, path_id):
    check(allowed(user, 'paths.manage') or allowed(user, 'courses.assign'), 'You do not have permission to view path progress.', 403)
    check(db.execute('SELECT 1 FROM learning_paths WHERE id=?', (path_id,)).fetchone() is not None, 'Learning path was not found.', 404)
    employees = set()
    for a in db.execute('SELECT * FROM path_assignments WHERE path_id=?', (path_id,)):
        employees |= set(target_employees(db, a['target_type'], a['target_id']))
    if user['role'] == 'manager':
        employees &= team(db, user['id'])
    rows = []
    for e in sorted(employees):
        person = me(db, {'id': e})
        progress = progress_index(db, [e])
        match = [p for p in employee_paths(db, person, progress) if p['id'] == path_id]
        if match:
            rows.append({'employee': person['name'], 'department': person['department'] or 'Unassigned', 'completed': match[0]['completed'], 'total': match[0]['total'], 'progress': match[0]['progress'],
                         'next': next((c['title'] for c in match[0]['courses'] if c['id'] == match[0]['nextCourseId']), '')})
    return {'employees': sorted(rows, key=lambda r: r['employee'])}


# ---------------------------------------------------------------- skills and competencies

def skills_overview(db, user):
    check(user['role'] != 'employee', 'You do not have permission to manage skills.', 403)
    return {'skills': [dict(r) for r in db.execute('''SELECT s.*,(SELECT COUNT(*) FROM course_skills k WHERE k.skill_id=s.id) AS courses,
                (SELECT COUNT(DISTINCT employee_id) FROM skill_evidence e WHERE e.skill_id=s.id) AS assessed FROM skills s ORDER BY s.name''')],
            'competencies': [{'jobRoleId': r[0], 'skillId': r[1], 'targetLevel': r[2]} for r in db.execute('SELECT job_role_id,skill_id,target_level FROM role_competencies')],
            'editableRoles': editable_roles(db, user),
            'canManageSkills': allowed(user, 'skills.manage'), 'canRecord': allowed(user, 'skills.record')}


def editable_roles(db, user):
    if not allowed(user, 'competencies.manage'):
        return []
    if user['role'] != 'manager':
        return [r[0] for r in db.execute('SELECT id FROM job_roles')]
    # Managers define competencies for job roles in their department or held by their direct reports.
    return [r[0] for r in db.execute('SELECT id FROM job_roles WHERE department_id=(SELECT department_id FROM candidates WHERE id=?) OR id IN (SELECT job_role_id FROM candidates WHERE manager_id=?)', (user['id'], user['id']))]


def save_skill(db, user, data):
    require(user, 'skills.manage')
    identity = data.get('id') or None
    if identity is not None:
        check(isinstance(identity, str) and db.execute('SELECT 1 FROM skills WHERE id=?', (identity,)).fetchone() is not None, 'Skill was not found.', 404)
    if data.get('delete') is True:
        check(identity is not None, 'Skill was not found.', 404)
        check(db.execute('SELECT 1 FROM skill_evidence WHERE skill_id=?', (identity,)).fetchone() is None, 'This skill has employee assessment records and cannot be deleted.', 409)
        db.execute('DELETE FROM skills WHERE id=?', (identity,))
        audit(db, user['id'], 'skill_deleted', identity)
        return skills_overview(db, user)
    name, category, description = text(data, 'name', 2, 80), opt_text(data, 'category', 80, 'Category'), opt_text(data, 'description', 1000, 'Description')
    if identity:
        db.execute('UPDATE skills SET name=?,category=?,description=? WHERE id=?', (name, category, description, identity))
    else:
        identity = uid()
        db.execute('INSERT INTO skills VALUES (?,?,?,?,?)', (identity, name, category, description, now()))
    audit(db, user['id'], 'skill_saved', identity, name)
    return skills_overview(db, user)


def save_competency(db, user, data):
    require(user, 'competencies.manage')
    role = ref(db, data, 'jobRoleId', 'job_roles', 'job role', required=True)
    skill = ref(db, data, 'skillId', 'skills', 'skill', required=True)
    check(role in editable_roles(db, user), 'You can define competencies only for job roles in your team or department.', 403)
    level = integer(data, 'targetLevel', 0, 4, 'Target level')
    if level == 0:
        db.execute('DELETE FROM role_competencies WHERE job_role_id=? AND skill_id=?', (role, skill))
    else:
        db.execute('INSERT INTO role_competencies VALUES (?,?,?,?,?) ON CONFLICT(job_role_id,skill_id) DO UPDATE SET target_level=excluded.target_level,updated_by=excluded.updated_by,updated_at=excluded.updated_at', (role, skill, level, user['id'], now()))
    audit(db, user['id'], 'competency_saved', role, f'{skill}: {level}')
    return skills_overview(db, user)


def record_evidence(db, employee, skill, level, source, reference, note, recorded_by):
    db.execute('INSERT INTO skill_evidence(employee_id,skill_id,level,source,reference_id,note,recorded_by,recorded_at) VALUES (?,?,?,?,?,?,?,?)', (employee, skill, level, source, reference, note, recorded_by, now()))
    # Goals tied to a skill complete only when evidence reaches the target level.
    db.execute("UPDATE learning_goals SET status='completed',updated_at=? WHERE employee_id=? AND skill_id=? AND status='active' AND target_level IS NOT NULL AND target_level<=?", (now(), employee, skill, level))


def save_evidence(db, user, data):
    require(user, 'skills.record')
    employee = ref(db, data, 'employeeId', 'candidates', 'employee', "AND is_active=1", required=True)
    check(employee != user['id'], 'Your own skill levels are recorded by assessments or your manager.', 403)
    check(user['role'] != 'manager' or employee in team(db, user['id']), 'Managers can record skill evidence only for their direct reports.', 403)
    skill = ref(db, data, 'skillId', 'skills', 'skill', required=True)
    level = integer(data, 'level', 1, 4, 'Proficiency level')
    note = text(data, 'note', 3, 500)
    record_evidence(db, employee, skill, level, 'manager', None, note, user['id'])
    notify(db, [employee], 'skill', 'Skill level recorded', f'{db.execute("SELECT name FROM skills WHERE id=?", (skill,)).fetchone()[0]}: {LEVELS[level]}.', 'skills', f'evidence:{employee}:{skill}:{now()}')
    audit(db, user['id'], 'skill_evidence', employee, f'{skill}: {level}')
    return {'ok': True}


# ---------------------------------------------------------------- assessments (question banks)

def owns_assessment(db, user, row):
    if user['role'] in ('admin', 'hr'):
        return True
    if row['created_by'] == user['id']:
        return True
    course = db.execute('SELECT * FROM courses WHERE id=?', (row['course_id'],)).fetchone() if row['course_id'] else None
    return course is not None and owns_course(user, course)


def assessment_view(db, row, private=False):
    stats = db.execute("SELECT COUNT(*),SUM(status='passed'),AVG(percent) FROM assessment_attempts WHERE assessment_id=? AND status<>'in-progress'", (row['id'],)).fetchone()
    result = {'id': row['id'], 'title': row['title'], 'description': row['description'], 'kind': row['kind'], 'courseId': row['course_id'], 'skillId': row['skill_id'], 'skillLevel': row['skill_level'],
              'passPercent': row['pass_percent'], 'maxAttempts': row['max_attempts'], 'questionCount': row['question_count'], 'timeLimitMinutes': row['time_limit_minutes'], 'status': row['status'],
              'attempts': stats[0], 'passRate': round((stats[1] or 0) / stats[0] * 100) if stats[0] else None, 'averageScore': round(stats[2]) if stats[2] is not None else None}
    if private:
        result['questions'] = [[q['prompt'], json.loads(q['options_json']), q['correct_option'], q['explanation']] + ([q['code']] if q['code'] else []) for q in db.execute('SELECT * FROM assessment_bank WHERE assessment_id=? ORDER BY position', (row['id'],))]
        result['locked'] = stats[0] > 0 or db.execute("SELECT 1 FROM assessment_attempts WHERE assessment_id=?", (row['id'],)).fetchone() is not None
    return result


def assessment_list(db, user):
    require(user, 'assessments.manage')
    return {'assessments': [assessment_view(db, r, True) for r in db.execute('SELECT * FROM assessments ORDER BY title') if owns_assessment(db, user, r)]}


def save_assessment(db, user, data):
    identity = store_assessment(db, user, data)
    return {'assessment': assessment_view(db, db.execute('SELECT * FROM assessments WHERE id=?', (identity,)).fetchone(), True), **assessment_list(db, user)}


def save_course_assessment(db, user, course_id, course_title, payload, course_status):
    """Save the assessment built inside Manage Courses as the course's required post-training assessment."""
    current = db.execute("SELECT a.* FROM courses c JOIN assessments a ON a.id=c.post_assessment_id AND a.kind='post' AND a.course_id=c.id WHERE c.id=?", (course_id,)).fetchone()
    if payload is None:
        if current:  # Archive rather than delete so attempt history is kept.
            db.execute("UPDATE assessments SET status='archived',updated_at=? WHERE id=?", (now(), current['id']))
        return None
    check(isinstance(payload, dict), 'The course assessment is invalid.')
    items = payload.get('questions')
    check(isinstance(items, list) and items, 'Add at least one question to the assessment, or remove the assessment.')
    questions = []
    for i, q in enumerate(items):
        check(isinstance(q, dict), f'Question {i + 1} is invalid.')
        questions.append([q.get('prompt'), q.get('options'), q.get('correct'), q.get('explanation') or '', q.get('code') or ''])
    status = {'published': 'published', 'archived': 'archived'}.get(course_status, 'draft')
    count = payload.get('questionCount') or len(items)
    return store_assessment(db, user, {'id': current['id'] if current else None, 'title': payload.get('title') or f'{course_title} assessment', 'description': payload.get('description') or '',
                                       'kind': 'post', 'courseId': course_id, 'passPercent': payload.get('passPercent'), 'maxAttempts': payload.get('maxAttempts'),
                                       'timeLimitMinutes': payload.get('timeLimitMinutes'), 'questionCount': count, 'status': status, 'questions': questions})


def store_assessment(db, user, data):
    require(user, 'assessments.manage')
    identity = data.get('id') or None
    old = db.execute('SELECT * FROM assessments WHERE id=?', (identity,)).fetchone() if identity else None
    check(identity is None or old is not None, 'Assessment was not found.', 404)
    check(old is None or owns_assessment(db, user, old), 'You can edit only the assessments you own.', 403)
    title, description = text(data, 'title', 2, 150), opt_text(data, 'description', 2000, 'Description')
    kind = choice(data, 'kind', KINDS, 'assessment type')
    course = ref(db, data, 'courseId', 'courses', 'course', required=kind in ('pre', 'post'))
    if course and user['role'] == 'trainer':
        check(owns_course(user, course_or_404(db, course)), 'Trainers can link assessments only to their own courses.', 403)
    skill = ref(db, data, 'skillId', 'skills', 'skill', required=kind == 'skill')
    skill_level = integer(data, 'skillLevel', 1, 4, 'Validated skill level') if kind == 'skill' else None
    pass_percent = integer(data, 'passPercent', 1, 100, 'Passing score')
    attempts = integer(data, 'maxAttempts', 1, 10, 'Attempts allowed')
    limit = integer(data, 'timeLimitMinutes', 1, 240, 'Time limit')
    status = choice(data, 'status', ('draft', 'published', 'archived'), 'status', 'draft')
    questions = questions_input(data)
    count = integer(data, 'questionCount', 1, len(questions), 'Questions per attempt')
    has_attempts = old is not None and db.execute('SELECT 1 FROM assessment_attempts WHERE assessment_id=?', (identity,)).fetchone() is not None
    if has_attempts:
        stored = assessment_view(db, old, True)['questions']
        check(stored == questions and old['kind'] == kind, 'Employees have attempted this assessment. Create a new assessment to change its questions or type.', 409)
    if old:
        db.execute('UPDATE assessments SET title=?,description=?,kind=?,course_id=?,skill_id=?,skill_level=?,pass_percent=?,max_attempts=?,question_count=?,time_limit_minutes=?,status=?,updated_at=? WHERE id=?',
                   (title, description, kind, course, skill, skill_level, pass_percent, attempts, count, limit, status, now(), identity))
    else:
        identity = uid()
        db.execute('INSERT INTO assessments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (identity, title, description, kind, course, skill, skill_level, pass_percent, attempts, count, limit, status, user['id'], now(), now()))
    if not has_attempts:
        db.execute('DELETE FROM assessment_bank WHERE assessment_id=?', (identity,))
        for position, q in enumerate(questions):
            db.execute('INSERT INTO assessment_bank(id,assessment_id,position,prompt,options_json,correct_option,explanation,code) VALUES (?,?,?,?,?,?,?,?)',
                       (uid(), identity, position, q[0], json.dumps(q[1]), q[2], q[3], q[4] if len(q) > 4 else ''))
    audit(db, user['id'], 'assessment_saved', identity, f'{status}: {title}')
    return identity


def assessment_attempts(db, user, identity, query):
    require(user, 'assessments.manage')
    row = db.execute('SELECT * FROM assessments WHERE id=?', (identity,)).fetchone()
    check(row is not None, 'Assessment was not found.', 404)
    check(owns_assessment(db, user, row), 'You can review only the assessments you own.', 403)
    items = [dict(r) for r in db.execute('''SELECT t.id,c.full_name AS employee,d.name AS department,t.attempt_number,t.status,t.score,t.total,t.percent,t.started_at,t.finished_at
        FROM assessment_attempts t JOIN candidates c ON c.id=t.employee_id LEFT JOIN departments d ON d.id=c.department_id WHERE t.assessment_id=? ORDER BY t.started_at DESC''', (identity,))]
    return {'assessment': assessment_view(db, row), **pages(items, query)}


def expire_assessments(db, employee):
    db.execute("UPDATE assessment_attempts SET status='expired',finished_at=? WHERE employee_id=? AND status='in-progress' AND deadline<?", (now(), employee, time.time()))


def visible_assessments(db):
    return db.execute("SELECT a.*,c.title AS course_title,s.name AS skill_name FROM assessments a LEFT JOIN courses c ON c.id=a.course_id LEFT JOIN skills s ON s.id=a.skill_id WHERE a.status='published' AND (a.course_id IS NULL OR c.status='published') ORDER BY a.kind,a.title").fetchall()


def attempt_questions(db, attempt):
    ids = json.loads(attempt['question_ids_json'])
    rows = {r['id']: r for r in db.execute(f"SELECT * FROM assessment_bank WHERE id IN ({','.join('?' * len(ids))})", ids)}
    return [rows[i] for i in ids]


def option_orders(attempt, questions):
    """Display order of each question's options for an attempt; attempts made before shuffling use the bank order."""
    stored = json.loads(attempt['option_orders_json'] or '[]')
    return stored if len(stored) == len(questions) else [list(range(len(json.loads(q['options_json'])))) for q in questions]


def active_attempt_view(db, attempt):
    questions = attempt_questions(db, attempt)
    orders = option_orders(attempt, questions)
    return {'id': attempt['id'], 'assessmentId': attempt['assessment_id'], 'attemptNumber': attempt['attempt_number'], 'deadline': attempt['deadline'] * 1000,
            'questions': [{'id': q['id'], 'prompt': q['prompt'], 'code': q['code'], 'options': [json.loads(q['options_json'])[i] for i in order]} for q, order in zip(questions, orders)]}


def my_assessments(db, user):
    expire_assessments(db, user['id'])
    result = []
    for a in visible_assessments(db):
        attempts = [dict(r) for r in db.execute('SELECT id,attempt_number,status,percent,started_at,finished_at FROM assessment_attempts WHERE assessment_id=? AND employee_id=? ORDER BY attempt_number', (a['id'], user['id']))]
        active = db.execute("SELECT * FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status='in-progress'", (a['id'], user['id'])).fetchone()
        result.append({'id': a['id'], 'title': a['title'], 'description': a['description'], 'kind': a['kind'], 'course': a['course_title'], 'courseId': a['course_id'],
                       'skill': a['skill_name'], 'skillLevel': LEVELS.get(a['skill_level'] or 0), 'passPercent': a['pass_percent'], 'maxAttempts': a['max_attempts'],
                       'questionCount': a['question_count'], 'timeLimitMinutes': a['time_limit_minutes'], 'attempts': attempts,
                       'passed': any(t['status'] == 'passed' for t in attempts), 'best': max([t['percent'] for t in attempts if t['percent'] is not None], default=None),
                       'attemptsLeft': max(0, a['max_attempts'] - len(attempts)), 'active': active_attempt_view(db, active) if active else None})
    return {'assessments': result}


def start_assessment(db, user, identity):
    expire_assessments(db, user['id'])
    a = next((r for r in visible_assessments(db) if r['id'] == identity), None)
    check(a is not None, 'This assessment is not available.', 404)
    active = db.execute("SELECT * FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status='in-progress'", (identity, user['id'])).fetchone()
    if active:
        return {'attempt': active_attempt_view(db, active)}
    used = db.execute('SELECT COUNT(*) FROM assessment_attempts WHERE assessment_id=? AND employee_id=?', (identity, user['id'])).fetchone()[0]
    check(used < a['max_attempts'], f'All {a["max_attempts"]} attempts have been used for this assessment.', 409)
    if a['kind'] == 'skill':
        # A passed skill assessment is already recorded as evidence; post-training checks may be retaken for a new course run.
        check(db.execute("SELECT 1 FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status='passed'", (identity, user['id'])).fetchone() is None, 'You have already passed this assessment.', 409)
    bank = [r[0] for r in db.execute('SELECT id FROM assessment_bank WHERE assessment_id=?', (identity,))]
    check(len(bank) >= a['question_count'], 'This assessment does not have enough questions yet. Contact the course owner.', 409)
    # Randomised selection from the question bank for every attempt.
    generator = random.SystemRandom()
    chosen = generator.sample(bank, a['question_count'])
    # Answer positions are shuffled too, so the correct option is not always in the same place.
    sizes = {r[0]: len(json.loads(r[1])) for r in db.execute(f"SELECT id,options_json FROM assessment_bank WHERE id IN ({','.join('?' * len(chosen))})", chosen)}
    orders = [generator.sample(range(sizes[q]), sizes[q]) for q in chosen]
    attempt = uid()
    db.execute('INSERT INTO assessment_attempts(id,assessment_id,employee_id,attempt_number,question_ids_json,option_orders_json,status,started_at,deadline,total) VALUES (?,?,?,?,?,?,?,?,?,?)',
               (attempt, identity, user['id'], used + 1, json.dumps(chosen), json.dumps(orders), 'in-progress', now(), time.time() + a['time_limit_minutes'] * 60, len(chosen)))
    return {'attempt': active_attempt_view(db, db.execute('SELECT * FROM assessment_attempts WHERE id=?', (attempt,)).fetchone())}


def submit_assessment(db, user, identity, data):
    attempt = db.execute('SELECT * FROM assessment_attempts WHERE id=? AND assessment_id=? AND employee_id=?', (data.get('attemptId'), identity, user['id'])).fetchone()
    check(attempt is not None, 'Attempt was not found.', 404)
    check(attempt['status'] == 'in-progress', 'This attempt has already ended.', 409)
    a = db.execute('SELECT * FROM assessments WHERE id=?', (identity,)).fetchone()
    if time.time() > attempt['deadline'] + 5:
        db.execute("UPDATE assessment_attempts SET status='expired',finished_at=? WHERE id=?", (now(), attempt['id']))
        notify(db, [user['id']], 'assessment', f'Assessment time expired: {a["title"]}', 'The attempt ended without a score.', 'assessments', f'assessment:{attempt["id"]}')
        return {'result': {'status': 'expired', 'percent': None, 'details': []}}
    questions = attempt_questions(db, attempt)
    answers = data.get('answers')
    check(isinstance(answers, list) and len(answers) == len(questions), 'Answer every question before submitting.')
    check(all(type(x) is int and 0 <= x < len(json.loads(q['options_json'])) for x, q in zip(answers, questions)), 'Invalid answer selection.')
    answers = [order[x] for x, order in zip(answers, option_orders(attempt, questions))]  # Displayed position -> bank option.
    details = [{'correct': x == q['correct_option'], 'explanation': q['explanation'], 'answer': json.loads(q['options_json'])[q['correct_option']]} for x, q in zip(answers, questions)]
    score = sum(d['correct'] for d in details)
    percent = round(score / len(questions) * 100)
    status = 'passed' if percent >= a['pass_percent'] else 'failed'
    db.execute('UPDATE assessment_attempts SET status=?,score=?,percent=?,answers_json=?,finished_at=? WHERE id=?', (status, score, percent, json.dumps(answers), now(), attempt['id']))
    if status == 'passed' and a['kind'] == 'skill' and a['skill_id'] and a['skill_level']:
        record_evidence(db, user['id'], a['skill_id'], a['skill_level'], 'assessment', attempt['id'], f'Passed {a["title"]} ({percent}%)', None)
    if status == 'passed' and a['kind'] == 'post' and a['course_id']:
        run = db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL', (user['id'], a['course_id'])).fetchone()
        if run:
            issue_certificate(db, user['id'], run['id'])
    notify(db, [user['id']], 'assessment', f'Assessment {"passed" if status == "passed" else "not passed"}: {a["title"]}', f'You scored {percent}% (pass mark {a["pass_percent"]}%).', 'assessments', f'assessment:{attempt["id"]}')
    return {'result': {'status': status, 'score': score, 'total': len(questions), 'percent': percent, 'passPercent': a['pass_percent'], 'details': details}}


# ---------------------------------------------------------------- training sessions

def session_rows(db, user=None, upcoming_only=False):
    sql = '''SELECT s.*,c.full_name AS trainer,k.title AS course,
        (SELECT COUNT(*) FROM session_registrations g WHERE g.session_id=s.id AND g.status IN ('registered','attended')) AS registered
        FROM training_sessions s LEFT JOIN candidates c ON c.id=s.trainer_id LEFT JOIN courses k ON k.id=s.course_id'''
    params = ()
    if upcoming_only:
        sql += " WHERE s.status='scheduled' AND s.ends_at>=?"
        params = (local_now(),)
    rows = []
    for r in db.execute(sql + ' ORDER BY s.starts_at', params):
        item = {'id': r['id'], 'title': r['title'], 'description': r['description'], 'kind': r['kind'], 'courseId': r['course_id'], 'course': r['course'], 'trainerId': r['trainer_id'], 'trainer': r['trainer'],
                'location': r['location'], 'startsAt': r['starts_at'], 'endsAt': r['ends_at'], 'capacity': r['capacity'], 'registered': r['registered'],
                'seatsLeft': max(0, r['capacity'] - r['registered']), 'status': r['status']}
        if user is not None:
            mine = db.execute('SELECT status FROM session_registrations WHERE session_id=? AND employee_id=?', (r['id'], user['id'])).fetchone()
            item['myStatus'] = mine[0] if mine else None
            item['canEdit'] = user['role'] in ('admin', 'hr') or user['id'] in (r['trainer_id'], r['created_by'])
        rows.append(item)
    return rows


def save_session(db, user, data):
    require(user, 'sessions.manage')
    identity = data.get('id') or None
    old = db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone() if identity else None
    check(identity is None or old is not None, 'Session was not found.', 404)
    check(old is None or user['role'] in ('admin', 'hr') or user['id'] in (old['trainer_id'], old['created_by']), 'Trainers can edit only their own sessions.', 403)
    title, description = text(data, 'title', 2, 150), opt_text(data, 'description', 2000, 'Description')
    kind = choice(data, 'kind', ('session', 'workshop'), 'session type', 'session')
    course = ref(db, data, 'courseId', 'courses', 'course')
    trainer = user['id'] if user['role'] == 'trainer' else ref(db, data, 'trainerId', 'candidates', 'trainer', "AND is_active=1 AND role IN ('admin','hr','trainer')")
    location = opt_text(data, 'location', 200, 'Location')
    starts, ends = date_time(data, 'startsAt', 'start date and time'), date_time(data, 'endsAt', 'end date and time')
    check(ends > starts, 'The session must end after it starts.')
    capacity = integer(data, 'capacity', 1, 10000, 'Capacity')
    status = choice(data, 'status', ('scheduled', 'cancelled'), 'status', 'scheduled')
    if old:
        registered = db.execute("SELECT COUNT(*) FROM session_registrations WHERE session_id=? AND status IN ('registered','attended')", (identity,)).fetchone()[0]
        check(capacity >= registered, f'{registered} employees are registered; capacity cannot be lower.', 409)
        db.execute('UPDATE training_sessions SET title=?,description=?,kind=?,course_id=?,trainer_id=?,location=?,starts_at=?,ends_at=?,capacity=?,status=? WHERE id=?',
                   (title, description, kind, course, trainer, location, starts, ends, capacity, status, identity))
        attendees = [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status='registered'", (identity,))]
        if status == 'cancelled' and old['status'] != 'cancelled':
            notify(db, attendees, 'session', f'Session cancelled: {title}', f'The session on {starts.replace("T", " ")} has been cancelled.', 'calendar', f'session-cancel:{identity}')
        elif status == 'scheduled' and (starts, ends, location) != (old['starts_at'], old['ends_at'], old['location']):
            notify(db, attendees, 'session', f'Session updated: {title}', f'Now {starts.replace("T", " ")} at {location or "the published location"}.', 'calendar', f'session-update:{identity}:{starts}:{location}')
    else:
        identity = uid()
        db.execute('INSERT INTO training_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (identity, title, description, kind, course, trainer, location, starts, ends, capacity, status, user['id'], now()))
    audit(db, user['id'], 'session_saved', identity, f'{status}: {title}')
    return {'sessions': session_rows(db, user)}


def session_registrations(db, user, identity):
    require(user, 'sessions.manage')
    session = db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone()
    check(session is not None, 'Session was not found.', 404)
    return {'registrations': [dict(r) for r in db.execute('''SELECT g.employee_id AS employeeId,c.full_name AS name,d.name AS department,g.status,g.registered_at AS registeredAt
        FROM session_registrations g JOIN candidates c ON c.id=g.employee_id LEFT JOIN departments d ON d.id=c.department_id WHERE g.session_id=? ORDER BY c.full_name''', (identity,))]}


def mark_attendance(db, user, identity, data):
    require(user, 'sessions.manage')
    session = db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone()
    check(session is not None, 'Session was not found.', 404)
    check(user['role'] in ('admin', 'hr') or user['id'] in (session['trainer_id'], session['created_by']), 'Only the session trainer or HR can record attendance.', 403)
    check(session['starts_at'] <= local_now(), 'Attendance can be recorded once the session has started.', 409)
    employee = data.get('employeeId')
    row = db.execute("SELECT status FROM session_registrations WHERE session_id=? AND employee_id=? AND status IN ('registered','attended')", (identity, employee)).fetchone()
    check(row is not None, 'This employee is not registered for the session.', 404)
    db.execute('UPDATE session_registrations SET status=?,updated_at=? WHERE session_id=? AND employee_id=?', ('attended' if flag(data, 'attended') else 'registered', now(), identity, employee))
    audit(db, user['id'], 'attendance_recorded', identity, f'{employee}: {data["attended"]}')
    return session_registrations(db, user, identity)


def register_session(db, user, identity, register):
    session = db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone()
    check(session is not None, 'Session was not found.', 404)
    current = db.execute('SELECT status FROM session_registrations WHERE session_id=? AND employee_id=?', (identity, user['id'])).fetchone()
    if register:
        check(session['status'] == 'scheduled' and session['starts_at'] > local_now(), 'Registration is closed for this session.', 409)
        if not (current and current[0] == 'registered'):
            taken = db.execute("SELECT COUNT(*) FROM session_registrations WHERE session_id=? AND status IN ('registered','attended')", (identity,)).fetchone()[0]
            check(taken < session['capacity'], 'This session is full.', 409)
            db.execute("INSERT INTO session_registrations VALUES (?,?,'registered',?,?) ON CONFLICT(session_id,employee_id) DO UPDATE SET status='registered',updated_at=excluded.updated_at", (identity, user['id'], now(), now()))
    else:
        check(current is not None and current[0] == 'registered', 'You are not registered for this session.', 409)
        db.execute("UPDATE session_registrations SET status='cancelled',updated_at=? WHERE session_id=? AND employee_id=?", (now(), identity, user['id']))
    return my_calendar(db, user)


def my_calendar(db, user):
    upcoming = session_rows(db, user, True)
    past = [dict(r) for r in db.execute("SELECT s.title,s.kind,s.starts_at AS startsAt,g.status FROM session_registrations g JOIN training_sessions s ON s.id=g.session_id WHERE g.employee_id=? AND s.ends_at<? ORDER BY s.starts_at DESC LIMIT 20", (user['id'], local_now()))]
    return {'sessions': upcoming, 'past': past}


# ---------------------------------------------------------------- notifications and reminders

def refresh_reminders(db, employee, progress, assigned):
    """Create deadline, inactivity, and session reminders; dedupe keys stop repeats."""
    titles = {r[0]: r[1] for r in db.execute('SELECT id,title FROM courses')}
    soon = (date.today() + timedelta(days=7)).isoformat()
    for pair, a in assigned.items():
        status = pair_status(progress.get(pair), a)
        if status == 'completed' or not a['dueDate']:
            continue
        title = titles.get(pair[1], 'Assigned course')
        if status == 'overdue':
            from notifications import staff_event
            staff_event(db, employee['id'], f'Overdue training: {employee["name"]}', f'{title} was due on {a["dueDate"]}.', f'team-overdue:{employee["id"]}:{pair[1]}:{a["dueDate"]}')
            notify(db, [employee['id']], 'deadline', f'Overdue: {title}', f'This training was due on {a["dueDate"]}.', 'courses', f'overdue:{pair[1]}:{a["dueDate"]}')
        elif a['dueDate'] <= soon:
            notify(db, [employee['id']], 'deadline', f'Due soon: {title}', f'Complete this training by {a["dueDate"]}.', 'courses', f'due-soon:{pair[1]}:{a["dueDate"]}')
    stale = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
    week = date.today().isocalendar()
    for (e, course), item in progress.items():
        if item['started'] and not item['completed'] and item['lastActivity'] and item['lastActivity'] < stale and course in titles:
            notify(db, [e], 'reminder', f'Continue {titles[course]}', f'You are {item["progress"]}% through this course.', 'courses', f'incomplete:{course}:{week[0]}-{week[1]}')
    limit = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
    for s in db.execute("SELECT s.id,s.title,s.starts_at FROM session_registrations g JOIN training_sessions s ON s.id=g.session_id WHERE g.employee_id=? AND g.status='registered' AND s.status='scheduled' AND s.starts_at BETWEEN ? AND ?", (employee['id'], local_now(), limit)):
        notify(db, [employee['id']], 'session', f'Upcoming: {s["title"]}', f'Starts {s["starts_at"].replace("T", " ")}.', 'calendar', f'session-soon:{s["id"]}:{s["starts_at"]}')


def my_notifications(db, user):
    employee = me(db, user)
    from notifications import refresh
    refresh(db, user)
    if user['role'] in ('admin', 'hr', 'manager'):
        from analytics import scope, employee_rows
        ids, _ = scope(db, user)
        team = employee_rows(db, ids)
        team_ids = [person['id'] for person in team]
        team_progress, team_assignments = progress_index(db, team_ids), assignment_index(db, team_ids)
        by_progress, by_assignment = {}, {}
        for key, value in team_progress.items(): by_progress.setdefault(key[0], {})[key] = value
        for key, value in team_assignments.items(): by_assignment.setdefault(key[0], {})[key] = value
        for person in team:
            refresh_reminders(db, person, by_progress.get(person['id'], {}), by_assignment.get(person['id'], {}))
    refresh_reminders(db, employee, progress_index(db, [user['id']]), assignment_index(db, [user['id']]))
    items = [dict(r) for r in db.execute('SELECT id,kind,title,body,link,created_at AS createdAt,read_at AS readAt FROM notifications WHERE employee_id=? ORDER BY id DESC LIMIT 50', (user['id'],))]
    return {'notifications': items, 'unread': db.execute('SELECT COUNT(*) FROM notifications WHERE employee_id=? AND read_at IS NULL', (user['id'],)).fetchone()[0]}


def read_notifications(db, user, data):
    if data.get('all') is True:
        db.execute('UPDATE notifications SET read_at=? WHERE employee_id=? AND read_at IS NULL', (now(), user['id']))
    else:
        ids = data.get('ids')
        check(isinstance(ids, list) and len(ids) <= 100 and all(type(i) is int for i in ids), 'Select notifications to mark as read.')
        for i in ids:
            db.execute('UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND employee_id=?', (now(), i, user['id']))
    return my_notifications(db, user)


# ---------------------------------------------------------------- employee views

def catalog(db, user):
    """Published catalog with the employee's own progress and assignment details."""
    progress, assigned = progress_index(db, [user['id']]), assignment_index(db, [user['id']])
    lesson_counts = {r[0]: r[1] for r in db.execute('SELECT course_id,COUNT(*) FROM course_lessons GROUP BY course_id')}
    items = []
    for row in db.execute("SELECT * FROM courses WHERE status='published' ORDER BY title"):
        p, a = progress.get((user['id'], row['id'])), assigned.get((user['id'], row['id']))
        if not (a or can_view_course(db, user, row)):
            continue
        item = course_view(row, False, db)
        item.update({'progress': p['progress'] if p else 0, 'enrolled': p is not None, 'completed': bool(p and p['completed']), 'lastActivity': p['lastActivity'] if p else '',
                     'assignment': a, 'status': pair_status(p, a), 'lessonCount': lesson_counts.get(row['id'], 0)})
        items.append(item)
    return items


def video_file(url):
    """Resolve an api/videos/<course>/<file> path inside the videos folder; None if it is not one or would escape it."""
    match = re.fullmatch(r'api/videos/([a-z0-9-]{1,100})/([a-z0-9-]{1,100}\.(mp4|webm|vtt|jpg))', url or '')
    if not match:
        return None
    path = (VIDEO_ROOT / match.group(1) / match.group(2)).resolve()
    return path if path.is_relative_to(VIDEO_ROOT.resolve()) else None


def video_available(url):
    path = video_file(url)
    return bool(url) and (path is None or path.is_file())


def public_activity(activity_json):
    """Exercise tasks for employees: instructions and criteria labels only (no rubric keywords or model answers)."""
    if not activity_json:
        return None
    activity = json.loads(activity_json)
    return {'passPercent': activity['passPercent'], 'tasks': [{'id': t['id'], 'title': t['title'], 'instructions': t['instructions'], 'criteria': [c['label'] for c in t['criteria']]} for t in activity['tasks']]}


def lesson_view(row, staff=False):
    view = {'id': row['id'], 'title': row['title'], 'description': row['description'], 'videoUrl': row['video_url'], 'documentUrl': row['document_url'], 'documentName': row['document_name'],
            'resources': json.loads(row['resources_json']), 'content': row['content'], 'exercise': row['exercise'], 'durationMinutes': row['duration_minutes'],
            'captionsUrl': row['captions_url'], 'videoSeconds': row['video_seconds'], 'completionPercent': row['completion_percent'], 'assessmentId': row['assessment_id'],
            'updatedAt': row['updated_at'], 'moduleIndex': row['module_index'], 'moduleTitle': row['module_title'], 'sourceUrl': row['source_url']}
    if staff:
        view['hasActivity'] = bool(row['activity_json'])
    else:
        view['activity'] = public_activity(row['activity_json'])
    practice = json.loads(row['practice_json']) if row['practice_json'] else None
    view['practice'] = {k: practice[k] for k in ('instructions', 'starter', 'tests')} if practice else None
    view['quiz'] = [{'prompt': q[0], 'options': q[1]} for q in json.loads(row['quiz_json'])] if row['quiz_json'] else []
    return view


def course_video(db, user, url):
    """Lesson videos, captions and posters, served only to employees who can open the course (or manage it)."""
    path = video_file(url)
    check(path is not None, 'File was not found.', 404)
    course = db.execute('SELECT * FROM courses WHERE id=?', (path.parent.name,)).fetchone()
    check(course is not None, 'File was not found.', 404)
    permitted = can_view_course(db, user, course) or (allowed(user, 'courses.manage') and owns_course(user, course)) or \
        db.execute('SELECT 1 FROM course_runs WHERE candidate_id=? AND course_id=?', (user['id'], course['id'])).fetchone() is not None
    check(permitted, 'This video is not available to you.', 403)
    if not (allowed(user, 'courses.manage') and owns_course(user, course)):
        from checkpoints import lesson_unlocked
        lesson = db.execute('SELECT id FROM course_lessons WHERE course_id=? AND video_url=?', (course['id'], re.sub(r'\.(vtt|jpg)$', '.mp4', url))).fetchone()
        run = db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL', (user['id'], course['id'])).fetchone()
        if lesson:
            check(lesson_unlocked(db, run['id'] if run else None, course['id'], lesson['id']), 'Pass the previous assignment to unlock this module.', 403)
    check(path.is_file(), 'This video has not been published yet.', 404)
    return path, VIDEO_TYPES[path.suffix], path.name


def score_activity(activity, answers):
    """Transparent rubric scoring: each criterion is met when the answer contains one of its key phrases."""
    results = []
    for task, answer in zip(activity['tasks'], answers):
        normalized = ' '.join(answer.lower().split())
        too_short = len(normalized) < 40
        criteria = [{'label': c['label'], 'met': not too_short and any(k in normalized for k in c['keywords']), 'tip': c['tip']} for c in task['criteria']]
        met = sum(c['met'] for c in criteria)
        results.append({'id': task['id'], 'title': task['title'], 'score': round(met / len(criteria) * 100), 'tooShort': too_short,
                        'criteria': [dict(c, tip='' if c['met'] else c['tip']) for c in criteria], 'modelAnswer': task['modelAnswer'], 'explanation': task.get('explanation', '')})
    return round(sum(r['score'] for r in results) / len(results)), results


def course_builder(db, user, identity):
    """Everything the Manage Courses builder needs to reopen a lesson-based course, including answer keys (staff only)."""
    course = owned_course(db, user, identity)
    check(course['format'] == 'lessons', 'This course uses the 3-module format. Edit it with the curriculum editor.', 409)
    completed = {r[0] for table in ('lesson_progress', 'lesson_watch', 'lesson_activity_attempts') for r in db.execute(f'SELECT DISTINCT p.lesson_id FROM {table} p JOIN course_lessons l ON l.id=p.lesson_id WHERE l.course_id=?', (identity,))}
    lessons = [dict(lesson_view(r, staff=True), hasProgress=r['id'] in completed) for r in db.execute('SELECT * FROM course_lessons WHERE course_id=? ORDER BY position', (identity,))]
    assessment = db.execute("SELECT * FROM assessments WHERE id=? AND kind='post' AND course_id=? AND status<>'archived'", (course['post_assessment_id'], identity)).fetchone()
    return {'course': course_view(course, True, db), 'lessons': lessons, 'assessment': assessment_view(db, assessment, True) if assessment else None}


def my_dashboard(db, user):
    employee = me(db, user)
    progress, assigned = progress_index(db, [user['id']]), assignment_index(db, [user['id']])
    refresh_reminders(db, employee, progress, assigned)
    courses = {c['id']: c for c in catalog(db, user)}
    assigned_items = sorted([courses[c] for (_, c) in assigned if c in courses], key=lambda c: ({'overdue': 0, 'in_progress': 1, 'not_started': 2, 'completed': 3}[c['status']], c['assignment']['dueDate'] or '9999'))
    continuing = sorted([c for c in courses.values() if progress.get((user['id'], c['id']), {}).get('started') and not c['completed']], key=lambda c: c['lastActivity'], reverse=True)[:4]
    paths = employee_paths(db, employee, progress)
    levels, targets = skill_levels(db, user['id']), role_targets(db, employee['job_role_id'])
    names = {r[0]: r[1] for r in db.execute('SELECT id,name FROM skills')}
    skills = [{'skill': names.get(s, ''), 'current': levels.get(s, 0), 'target': targets.get(s, 0)} for s in sorted(set(levels) | set(targets), key=lambda s: names.get(s, ''))]
    certificates = db.execute('SELECT COUNT(*) FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE r.candidate_id=?', (user['id'],)).fetchone()[0]
    return {'profile': {k: employee[k] for k in ('name', 'email', 'role', 'department', 'job_role', 'manager', 'job_title')},
            'stats': {'assigned': len(assigned_items), 'inProgress': sum(1 for c in courses.values() if c['status'] == 'in_progress'), 'completed': sum(1 for c in courses.values() if c['completed']),
                      'overdue': sum(1 for c in assigned_items if c['status'] == 'overdue'), 'certificates': certificates,
                      'skillGaps': sum(1 for s in skills if s['target'] and s['current'] < s['target'])},
            'assigned': assigned_items, 'continue': continuing, 'recommendations': recommendations(db, employee, progress, assigned, paths), 'paths': paths, 'skills': skills,
            'sessions': [s for s in session_rows(db, user, True)][:4], 'pendingAssessments': pending_assessments(db, employee, progress),
            'goals': [dict(r) for r in db.execute("SELECT id,title,target_date AS targetDate,status FROM learning_goals WHERE employee_id=? AND status='active' ORDER BY target_date IS NULL,target_date LIMIT 5", (user['id'],))],
            'history': history_items(db, user['id'])[:6]}


def my_paths(db, user):
    employee = me(db, user)
    return {'paths': employee_paths(db, employee, progress_index(db, [user['id']]))}


def my_skills(db, user):
    employee = me(db, user)
    levels, targets = skill_levels(db, user['id']), role_targets(db, employee['job_role_id'])
    goals = [dict(r) for r in db.execute('SELECT g.id,g.title,g.skill_id AS skillId,s.name AS skill,g.target_level AS targetLevel,g.target_date AS targetDate,g.status FROM learning_goals g LEFT JOIN skills s ON s.id=g.skill_id WHERE g.employee_id=? ORDER BY g.status,g.target_date IS NULL,g.target_date', (user['id'],))]
    goal_skills = {g['skillId'] for g in goals if g['skillId'] and g['status'] == 'active'}
    skills = {r['id']: dict(r) for r in db.execute('SELECT id,name,category,description FROM skills ORDER BY name')}
    rows = []
    for skill in sorted(set(levels) | set(targets) | goal_skills, key=lambda s: skills.get(s, {}).get('name', '')):
        if skill not in skills:
            continue
        evidence = [dict(r) for r in db.execute('SELECT e.level,e.source,e.note,e.recorded_at AS recordedAt,c.full_name AS recordedBy FROM skill_evidence e LEFT JOIN candidates c ON c.id=e.recorded_by WHERE e.employee_id=? AND e.skill_id=? ORDER BY e.id DESC LIMIT 5', (user['id'], skill))]
        current, target = levels.get(skill, 0), targets.get(skill, 0)
        rows.append({**skills[skill], 'current': current, 'target': target, 'gap': max(0, target - current), 'evidence': evidence})
    progress, assigned = progress_index(db, [user['id']]), assignment_index(db, [user['id']])
    return {'profile': {'jobRole': employee['job_role'], 'department': employee['department']}, 'skills': rows, 'allSkills': list(skills.values()), 'goals': goals,
            'recommendations': recommendations(db, employee, progress, assigned, employee_paths(db, employee, progress)),
            'assessments': [a for a in my_assessments(db, user)['assessments'] if a['kind'] == 'skill'], 'levels': [{'value': k, 'label': v} for k, v in LEVELS.items() if k]}


def save_goal(db, user, data):
    identity = data.get('id') or None
    if identity is not None:
        check(db.execute('SELECT 1 FROM learning_goals WHERE id=? AND employee_id=?', (identity, user['id'])).fetchone() is not None, 'Goal was not found.', 404)
    if data.get('delete') is True:
        db.execute('DELETE FROM learning_goals WHERE id=? AND employee_id=?', (identity, user['id']))
        return my_skills(db, user)
    title = text(data, 'title', 2, 150)
    skill = ref(db, data, 'skillId', 'skills', 'skill')
    level = data.get('targetLevel') or None
    check(level is None or (type(level) is int and 1 <= level <= 4 and skill is not None), 'A target level requires a skill and must be from 1 to 4.')
    target_date = opt_date(data, 'targetDate', 'Target date')
    status = choice(data, 'status', ('active', 'completed', 'cancelled'), 'goal status', 'active')
    if identity:
        db.execute('UPDATE learning_goals SET title=?,skill_id=?,target_level=?,target_date=?,status=?,updated_at=? WHERE id=?', (title, skill, level, target_date, status, now(), identity))
    else:
        check(db.execute("SELECT COUNT(*) FROM learning_goals WHERE employee_id=? AND status='active'", (user['id'],)).fetchone()[0] < 20, 'You can have up to 20 active goals.', 409)
        db.execute('INSERT INTO learning_goals VALUES (?,?,?,?,?,?,?,?,?)', (uid(), user['id'], title, skill, level, target_date, status, now(), now()))
    return my_skills(db, user)


def history_items(db, employee):
    items = []
    for r in db.execute('SELECT r.started_at,r.completed_at,r.run_number,k.title FROM course_runs r JOIN courses k ON k.id=r.course_id WHERE r.candidate_id=?', (employee,)):
        if r['completed_at']:
            items.append({'type': 'completion', 'at': r['completed_at'], 'text': f'Completed {r["title"]} and earned a certificate'})
    for r in db.execute("SELECT x.finished_at,x.score,x.status,x.set_index,k.title FROM exam_attempts x JOIN course_runs r ON r.id=x.run_id JOIN courses k ON k.id=r.course_id WHERE r.candidate_id=? AND x.status IN ('passed','failed')", (employee,)):
        items.append({'type': 'assessment', 'at': r['finished_at'], 'text': f'{"Passed" if r["status"] == "passed" else "Attempted"} Module {r["set_index"] + 1} exam in {r["title"]} ({r["score"] * 25}%)'})
    for r in db.execute("SELECT t.finished_at,t.percent,t.status,a.title FROM assessment_attempts t JOIN assessments a ON a.id=t.assessment_id WHERE t.employee_id=? AND t.status IN ('passed','failed')", (employee,)):
        items.append({'type': 'assessment', 'at': r['finished_at'], 'text': f'{"Passed" if r["status"] == "passed" else "Attempted"} {r["title"]} ({r["percent"]}%)'})
    for r in db.execute("SELECT s.title,s.starts_at FROM session_registrations g JOIN training_sessions s ON s.id=g.session_id WHERE g.employee_id=? AND g.status='attended'", (employee,)):
        items.append({'type': 'session', 'at': r['starts_at'], 'text': f'Attended {r["title"]}'})
    for r in db.execute('SELECT title,provider,completed_on,hours FROM development_records WHERE employee_id=?', (employee,)):
        items.append({'type': 'record', 'at': r['completed_on'], 'text': f'Recorded {r["title"]}{" with " + r["provider"] if r["provider"] else ""} ({r["hours"]:g} h)'})
    items.sort(key=lambda i: i['at'] or '', reverse=True)
    return items


def my_history(db, user, query):
    records = [dict(r) for r in db.execute('SELECT id,title,provider,completed_on AS completedOn,hours FROM development_records WHERE employee_id=? ORDER BY completed_on DESC', (user['id'],))]
    return {'records': records, **pages(history_items(db, user['id']), query, 20)}


def save_record(db, user, data):
    if data.get('delete') is True:
        db.execute('DELETE FROM development_records WHERE id=? AND employee_id=?', (data.get('id'), user['id']))
        return my_history(db, user, {})
    title, provider = text(data, 'title', 2, 150), opt_text(data, 'provider', 150, 'Provider')
    completed = opt_date(data, 'completedOn', 'Completion date')
    check(completed is not None and completed <= today(), 'Enter a completion date that is not in the future.')
    hours = data.get('hours', 0)
    check(type(hours) in (int, float) and 0 <= hours <= 1000, 'Hours must be between 0 and 1000.')
    db.execute('INSERT INTO development_records VALUES (?,?,?,?,?,?,?)', (uid(), user['id'], title, provider, completed, float(hours), now()))
    return my_history(db, user, {})


def course_extras(db, user, course_id):
    """Resources and linked pre/post assessments shown on the employee course page."""
    assessments = []
    for a in db.execute("SELECT id,title,kind,pass_percent,max_attempts FROM assessments WHERE course_id=? AND status='published' AND kind IN ('pre','post','knowledge') ORDER BY kind DESC", (course_id,)):
        attempts = db.execute("SELECT COUNT(*),MAX(percent),MAX(status='passed') FROM assessment_attempts WHERE assessment_id=? AND employee_id=?", (a['id'], user['id'])).fetchone()
        assessments.append({'id': a['id'], 'title': a['title'], 'kind': a['kind'], 'passPercent': a['pass_percent'], 'attemptsLeft': max(0, a['max_attempts'] - attempts[0]),
                            'best': attempts[1], 'passed': bool(attempts[2])})
    required = db.execute('SELECT post_assessment_id,format FROM courses WHERE id=?', (course_id,)).fetchone()
    lessons = [lesson_view(r) for r in db.execute('SELECT * FROM course_lessons WHERE course_id=? ORDER BY position', (course_id,))] if required and required['format'] == 'lessons' else []
    from checkpoints import lesson_unlocked
    run = db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL', (user['id'], course_id)).fetchone()
    for lesson in lessons:
        lesson['locked'] = not lesson_unlocked(db, run['id'] if run else None, course_id, lesson['id'])
        if lesson['locked']:
            for key in ('content', 'videoUrl', 'captionsUrl', 'posterUrl', 'documentUrl', 'exercise'):
                lesson[key] = ''
            lesson['resources'], lesson['activity'], lesson['practice'], lesson['quiz'] = [], None, None, []
    return {'resources': course_resources(db, course_id), 'assessments': assessments, 'requiredAssessmentId': required[0] if required else None, 'courseLessons': lessons}


# ---------------------------------------------------------------- routing

def development_action(db, user, method, route, query, data):
    parts = route.split('/')
    if parts[0] == 'me':
        return employee_action(db, user, method, parts[1:], query, data)
    check(parts[0] == 'manage', f'Endpoint was not found: {method} /api/{route}', 404)
    check(user['role'] != 'employee', 'You do not have permission for this area.', 403)
    p = parts[1:]
    key = (method, '/'.join(x if i == 0 or x in ('assign', 'progress', 'delete', 'attempts', 'registrations', 'attendance', 'preview', 'resources', 'builder', 'save') else '*' for i, x in enumerate(p)))
    handlers = {
        ('POST', 'announcements'): lambda: announce(db, user, data),
        ('GET', 'org'): lambda: org(db, user),
        ('POST', 'departments'): lambda: save_org_item(db, user, 'departments', data),
        ('POST', 'job-roles'): lambda: save_org_item(db, user, 'job-roles', data),
        ('POST', 'categories'): lambda: save_org_item(db, user, 'categories', data),
        ('GET', 'people'): lambda: people(db, user),
        ('GET', 'dashboard'): lambda: (require(user, 'reports.view'), dashboard(db, user, query))[1],
        ('GET', 'reports'): lambda: (require(user, 'reports.view'), report(db, user, query))[1],
        ('GET', 'assignments'): lambda: (check(allowed(user, 'courses.assign') or allowed(user, 'courses.manage'), 'You do not have permission to view assignments.', 403), {'assignments': assignment_rows(db, user, query.get('courseId', [None])[0])})[1],
        ('POST', 'assignments'): lambda: create_assignment(db, user, data),
        ('POST', 'assignments/*/delete'): lambda: delete_assignment(db, user, p[1]),
        ('GET', 'courses/*/preview'): lambda: preview(db, user, p[1]),
        ('GET', 'courses/*/builder'): lambda: course_builder(db, user, p[1]),
        ('POST', 'courses/*/resources'): lambda: save_resource(db, user, p[1], data),
        ('POST', 'import/preview'): lambda: course_import.preview(db, user, data),
        ('POST', 'import/save'): lambda: course_import.save(db, user, data),
        ('POST', 'resources/*/delete'): lambda: delete_resource(db, user, p[1]),
        ('GET', 'paths'): lambda: path_list(db, user),
        ('POST', 'paths'): lambda: save_path(db, user, data),
        ('POST', 'paths/*/assign'): lambda: assign_path(db, user, p[1], data),
        ('GET', 'paths/*/progress'): lambda: path_progress(db, user, p[1]),
        ('POST', 'path-assignments/*/delete'): lambda: delete_path_assignment(db, user, p[1]),
        ('GET', 'skills'): lambda: skills_overview(db, user),
        ('POST', 'skills'): lambda: save_skill(db, user, data),
        ('POST', 'competencies'): lambda: save_competency(db, user, data),
        ('POST', 'skill-evidence'): lambda: save_evidence(db, user, data),
        ('GET', 'assessments'): lambda: assessment_list(db, user),
        ('POST', 'assessments'): lambda: save_assessment(db, user, data),
        ('GET', 'assessments/*/attempts'): lambda: assessment_attempts(db, user, p[1], query),
        ('GET', 'sessions'): lambda: (require(user, 'sessions.manage'), {'sessions': session_rows(db, user)})[1],
        ('POST', 'sessions'): lambda: save_session(db, user, data),
        ('GET', 'sessions/*/registrations'): lambda: session_registrations(db, user, p[1]),
        ('POST', 'sessions/*/attendance'): lambda: mark_attendance(db, user, p[1], data),
    }
    check(key in handlers, f'Endpoint was not found: {method} /api/{route}', 404)
    return handlers[key]()


def employee_action(db, user, method, p, query, data):
    key = (method, '/'.join(x if i == 0 or x in ('register', 'cancel', 'start', 'submit', 'read') else '*' for i, x in enumerate(p)))
    handlers = {
        ('GET', 'dashboard'): lambda: my_dashboard(db, user),
        ('GET', 'paths'): lambda: my_paths(db, user),
        ('GET', 'skills'): lambda: my_skills(db, user),
        ('POST', 'goals'): lambda: save_goal(db, user, data),
        ('GET', 'calendar'): lambda: my_calendar(db, user),
        ('POST', 'sessions/*/register'): lambda: register_session(db, user, p[1], True),
        ('POST', 'sessions/*/cancel'): lambda: register_session(db, user, p[1], False),
        ('GET', 'assessments'): lambda: my_assessments(db, user),
        ('POST', 'assessments/*/start'): lambda: start_assessment(db, user, p[1]),
        ('POST', 'assessments/*/submit'): lambda: submit_assessment(db, user, p[1], data),
        ('GET', 'notifications'): lambda: my_notifications(db, user),
        ('POST', 'notifications/read'): lambda: read_notifications(db, user, data),
        ('GET', 'history'): lambda: my_history(db, user, query),
        ('POST', 'records'): lambda: save_record(db, user, data),
    }
    check(key in handlers, f'Endpoint was not found: {method} /api/me/{"/".join(p)}', 404)
    return handlers[key]()
