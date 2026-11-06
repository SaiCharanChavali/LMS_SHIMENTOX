"""Training Compliance & Deadline Monitoring: one read-only view over assignments, progress and deadlines.

Nothing is stored here. The assignment in force, progress, deadline status and manager scope all come from the same
functions the Course Deadline Settings page and the reminder process use, so these figures cannot disagree with them.

The summary cards must add up to the total, but deadline_status also reports Due Soon. Due Soon is a warning about an
open course rather than a stage of it, so here such a course counts as In Progress or Not Started and carries a flag.
"""
import csv
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

from admin import audit
from analytics import PAGE_SIZE, assignment_index, course_rows, employee_rows, progress_index, query_date, scope
from deadlines import STATUS_LABELS, deadline_status, format_deadline, format_span, local_date, parse_utc, portal_timezone, timezone_label, utc_iso
import reminders
from services import check

OVERDUE_PAGE_SIZE = 10  # Short, so the department comparison below it stays within reach.
NONE = '__none__'  # The filter value for employees with no department or job role.
COMPLETED = ('completed_on_time', 'completed_late')
STATUS_FILTERS = {'completed': COMPLETED, **{s: (s,) for s in (*COMPLETED, 'in_progress', 'not_started', 'overdue')}}
STATUS_ORDER = ('overdue', 'not_started', 'in_progress', 'completed_late', 'completed_on_time')  # Most in need of attention first.
SORTS = {'employee': lambda r: r['employee'].casefold(), 'employeeId': lambda r: r['employeeId'], 'department': lambda r: r['department'].casefold(), 'jobRole': lambda r: r['jobRole'].casefold(),
         'course': lambda r: r['course'].casefold(), 'type': lambda r: not r['mandatory'], 'assigned': lambda r: r['assignedAt'], 'deadline': lambda r: r['deadlineAt'], 'completed': lambda r: r['completedAt'],
         'progress': lambda r: r['progress'], 'status': lambda r: STATUS_ORDER.index(r['status'])}
PAGE_SIZES = (10, 25, 50)
FORMATS = {'csv': 'text/csv; charset=utf-8', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


def display(stamp):
    return format_deadline(stamp) if stamp else None


def portal_day(stamp):
    return local_date(stamp) if stamp else None


def records(db, user):
    """Every employee-course assignment the user may see, one row per pair."""
    check(user['role'] in ('admin', 'hr', 'manager'), 'You do not have permission to view training compliance.', 403)
    employees = scope(db, user)[0]
    people = {p['id']: p for p in employee_rows(db, employees)}
    courses = course_rows(db, published_only=True)
    progress = progress_index(db, employees)
    soon = reminders.settings(db)['dueSoonDays'] * 86400
    at = datetime.now(timezone.utc)
    rows = []
    for pair, a in assignment_index(db, employees).items():
        person, course = people.get(pair[0]), courses.get(pair[1])
        if not person or not course:  # Administrators are not learners here; assignment_index covers only published courses.
            continue
        p = progress.get(pair)
        status = deadline_status(p, a, soon, at)
        due_soon = status == 'due_soon'
        if due_soon:
            status = 'in_progress' if p and p['started'] else 'not_started'
        completed_at = p['completedAt'] if p and p['completed'] else None
        last_activity = (p or {}).get('lastActivity') or completed_at
        overdue_seconds = int((at - parse_utc(a['deadlineAt'])).total_seconds()) if status == 'overdue' else None
        rows.append({'employeeId': person['id'], 'employee': person['name'], 'email': person['email'], 'department': person['department'] or 'Unassigned', 'departmentId': person['department_id'] or NONE,
                     'jobRole': person['job_role'] or 'Unassigned', 'jobRoleId': person['job_role_id'] or NONE, 'courseId': course['id'], 'course': course['title'], 'mandatory': a['mandatory'],
                     'assignedAt': a['assignedAt'], 'assignedDate': portal_day(a['assignedAt']), 'assignedDisplay': display(a['assignedAt']), 'deadlineAt': a['deadlineAt'], 'deadlineDate': portal_day(a['deadlineAt']), 'deadlineDisplay': display(a['deadlineAt']),
                     'originalDeadlineAt': a['originalDeadlineAt'], 'originalDeadlineDisplay': display(a['originalDeadlineAt']), 'completedAt': completed_at, 'completedDate': portal_day(completed_at), 'completedDisplay': display(completed_at),
                     'progress': 100 if completed_at else (p or {}).get('progress', 0), 'status': status, 'statusLabel': STATUS_LABELS[status], 'dueSoon': due_soon,
                     'lastActivity': last_activity, 'lastActivityDisplay': display(last_activity), 'overdueSeconds': overdue_seconds, 'overdueBy': format_span(overdue_seconds) if overdue_seconds is not None else None})
    return sorted(rows, key=lambda r: (r['employee'].casefold(), r['employeeId'], r['course'].casefold()))


def read_filters(query):
    values = {key: query.get(key, [''])[0].strip() for key in ('q', 'employee', 'department', 'course', 'jobRole', 'type', 'status')}
    check(values['type'] in ('', 'mandatory', 'optional'), 'Choose mandatory or optional.')
    check(not values['status'] or values['status'] in STATUS_FILTERS, 'Unknown status.')
    values['from'], values['to'] = query_date(query, 'from'), query_date(query, 'to')
    check(not (values['from'] and values['to'] and values['from'] > values['to']), 'The deadline range must start on or before its end.')
    return values


def matches(row, f):
    """All filters apply together. Deadline dates are portal-timezone dates; a course with no deadline is outside any range."""
    if f['from'] or f['to']:
        day = local_date(row['deadlineAt']) if row['deadlineAt'] else None
        if not day or (f['from'] and day < f['from']) or (f['to'] and day > f['to']):
            return False
    search = f['q'].casefold()
    return ((not f['employee'] or row['employeeId'] == f['employee']) and (not f['department'] or row['departmentId'] == f['department'])
            and (not f['course'] or row['courseId'] == f['course']) and (not f['jobRole'] or row['jobRoleId'] == f['jobRole'])
            and (not f['type'] or row['mandatory'] == (f['type'] == 'mandatory')) and (not f['status'] or row['status'] in STATUS_FILTERS[f['status']])
            and (not search or any(search in row[k].casefold() for k in ('employee', 'email', 'employeeId', 'course', 'department', 'jobRole'))))


def rate(part, whole):
    return round(part / whole * 100) if whole else 0


def summary(rows):
    count = lambda *statuses: sum(1 for r in rows if r['status'] in statuses)
    return {'total': len(rows), 'completed': count(*COMPLETED), 'completedOnTime': count('completed_on_time'), 'completedLate': count('completed_late'), 'inProgress': count('in_progress'), 'notStarted': count('not_started'),
            'overdue': count('overdue'), 'completionRate': rate(count(*COMPLETED), len(rows))}


def departments(rows):
    """Pending is assigned, not completed and not yet overdue, so completed + pending + overdue = total."""
    groups = {}
    for r in rows:
        groups.setdefault(r['department'], []).append(r['status'])
    result = []
    for name in sorted(groups, key=lambda n: (n == 'Unassigned', n.casefold())):
        statuses = groups[name]
        completed, overdue = sum(s in COMPLETED for s in statuses), statuses.count('overdue')
        result.append({'department': name, 'total': len(statuses), 'completed': completed, 'pending': len(statuses) - completed - overdue, 'overdue': overdue, 'completionRate': rate(completed, len(statuses))})
    return result


def sort_rows(rows, query):
    """Rows stay in name order within equal values, and a blank date goes last in either direction."""
    key, direction = query.get('sort', [''])[0], query.get('dir', ['asc'])[0]
    if not key:
        return rows
    check(key in SORTS and direction in ('asc', 'desc'), 'Unknown sort order.')
    present = [r for r in rows if SORTS[key](r) is not None]
    return sorted(present, key=SORTS[key], reverse=direction == 'desc') + [r for r in rows if SORTS[key](r) is None]


def page_size(query):
    try:
        size = int(query.get('size', [PAGE_SIZE])[0])
    except ValueError:
        size = None
    check(size in PAGE_SIZES, 'Choose 10, 25 or 50 rows per page.')
    return size


def page_of(items, query, field, size=PAGE_SIZE):
    pages = max(1, -(-len(items) // size))
    try:
        page = min(max(1, int(query.get(field, ['1'])[0])), pages)
    except ValueError:
        page = 1
    return {'rows': items[(page - 1) * size:page * size], 'total': len(items), 'page': page, 'pages': pages}


def choices(rows, key, label):
    """Filter choices come from the rows the user may see, so a manager's menus name nobody outside their team."""
    found = {r[key]: r[label] for r in rows}
    return sorted(([k, v] for k, v in found.items()), key=lambda item: (item[0] == NONE, item[1].casefold()))


def monitoring(db, user, query):
    f = read_filters(query)
    everything = records(db, user)
    rows = sort_rows([r for r in everything if matches(r, f)], query)
    # Mandatory first, then whoever has been overdue longest.
    overdue = sorted((r for r in rows if r['status'] == 'overdue'), key=lambda r: (not r['mandatory'], -r['overdueSeconds']))
    return {'scope': 'team' if user['role'] == 'manager' else 'organisation', 'timezone': timezone_label(), 'updatedDisplay': format_deadline(utc_iso(datetime.now(timezone.utc))), 'filters': f, 'summary': summary(rows), 'departments': departments(rows),
            'table': page_of(rows, query, 'page', page_size(query)), 'overdue': {**page_of(overdue, query, 'overduePage', OVERDUE_PAGE_SIZE), 'mandatory': sum(r['mandatory'] for r in overdue)},
            'options': {'employees': choices(everything, 'employeeId', 'employee'), 'departments': choices(everything, 'departmentId', 'department'),
                        'courses': choices(everything, 'courseId', 'course'), 'jobRoles': choices(everything, 'jobRoleId', 'jobRole')}}


# ---------------------------------------------------------------- export

def stamp(value):
    """A portal-timezone value that sorts correctly in a spreadsheet."""
    return parse_utc(value).astimezone(portal_timezone()).strftime('%Y-%m-%d %H:%M') if value else ''


def export_table(rows):
    zone = timezone_label()
    columns = ['Employee Name', 'Employee ID', 'Department', 'Job Role', 'Course Name', 'Mandatory/Optional', f'Assignment Date ({zone})', f'Deadline ({zone})', f'Original Deadline ({zone})',
               f'Completion Date ({zone})', 'Progress %', 'Current Status', 'Overdue By', f'Last Activity ({zone})']
    return columns, [[r['employee'], r['employeeId'], r['department'], r['jobRole'], r['course'], 'Mandatory' if r['mandatory'] else 'Optional', stamp(r['assignedAt']), stamp(r['deadlineAt']),
                      stamp(r['originalDeadlineAt']), stamp(r['completedAt']), r['progress'], r['statusLabel'] + (' (Due Soon)' if r['dueSoon'] else ''), r['overdueBy'] or '', stamp(r['lastActivity'])] for r in rows]


def to_csv(columns, rows):
    def cell(value):
        # A name such as =HYPERLINK(...) must not run as a formula when the file is opened.
        return "'" + value if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r') else value
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\r\n')
    writer.writerow(columns)
    writer.writerows([cell(v) for v in row] for row in rows)
    return ('﻿' + out.getvalue()).encode('utf-8')  # The byte order mark tells Excel the file is UTF-8.


def column_name(index):
    name = ''
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def to_xlsx(columns, rows):
    """A minimal real .xlsx, written with the standard library so the portal needs no extra package.

    Text is stored as inline strings, which spreadsheets never evaluate, so it needs no formula guard.
    """
    def cell(ref, value, style=''):
        if isinstance(value, (int, float)):
            return f'<c r="{ref}"><v>{value}</v></c>'
        clean = re.sub('[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]', '', str(value))
        return f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(clean)}</t></is></c>'
    def row_xml(number, values, style=''):
        return f'<row r="{number}">' + ''.join(cell(f'{column_name(i)}{number}', v, style) for i, v in enumerate(values)) + '</row>'
    last = column_name(len(columns) - 1)
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             f'<cols><col min="1" max="{len(columns)}" width="22" customWidth="1"/></cols><sheetData>' + row_xml(1, columns, ' s="1"')
             + ''.join(row_xml(i, row) for i, row in enumerate(rows, 2)) + f'</sheetData><autoFilter ref="A1:{last}{len(rows) + 1}"/></worksheet>')
    parts = {
        '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Training Compliance" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        'xl/worksheets/sheet1.xml': sheet,
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, content in parts.items():
            package.writestr(name, content)
    return out.getvalue()


def export(db, user, query):
    """(file body, content type, file name) for every row matching the filters, with no page limit."""
    kind = query.get('format', ['csv'])[0]
    check(kind in FORMATS, 'Choose CSV or Excel.')
    f = read_filters(query)
    rows = sort_rows([r for r in records(db, user) if matches(r, f)], query)
    columns, values = export_table(rows)
    # Named employee records are leaving the portal, so the Activity Log records who took them.
    audit(db, user['id'], 'training_compliance_exported', 'training_compliance', json.dumps({'format': kind, 'rows': len(rows), 'filters': {k: v for k, v in f.items() if v}}))
    return (to_csv if kind == 'csv' else to_xlsx)(columns, values), FORMATS[kind], f'shimentox-training-compliance-{date.today().isoformat()}.{kind}'
