"""Training Compliance & Deadline Monitoring, over real HTTP and an isolated SQLite database.

Expected figures are worked out by hand from the scenario below rather than from the code under test.
"""
from contextlib import closing
import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from test_deadlines import DeadlineFixture, utc_now
from database import connect
from deadlines import utc_iso
from datetime import timedelta
from services import now, uid

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def url(route, **query):
    return route + ('?' + urllib.parse.urlencode(query) if query else '')


class ComplianceFixture(DeadlineFixture):
    def view(self, client=None, **query):
        result = (client or self.admin).request(url('manage/compliance', **query))
        self.assertEqual(result[0], 200, result[1])
        return result[1]

    def raw_export(self, client=None, **query):
        request = urllib.request.Request(self.base + '/api/' + url('manage/compliance/export', **query))
        try:
            with (client or self.admin).opener.open(request, timeout=15) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def csv_rows(self, client=None, **query):
        status, body, _ = self.raw_export(client, format='csv', **query)
        self.assertEqual(status, 200, body)
        self.assertTrue(body.startswith(b'\xef\xbb\xbf'))
        return list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))

    def sql(self, statement, *params):
        with closing(connect(self.db_path)) as db, db:
            return db.execute(statement, params).fetchall()


class ComplianceScenarioTests(ComplianceFixture):
    """Finance: on time, late. Sales: in progress, not started, overdue (mandatory). No department: overdue (optional), due soon."""
    built = False

    def setUp(self):
        cls = type(self)
        if cls.built:
            return
        org = self.admin.request('manage/org')[1]
        cls.finance = next(d['id'] for d in org['departments'] if d['name'] == 'Finance')
        cls.sales = next(d['id'] for d in org['departments'] if d['name'] == 'Sales')
        role = self.admin.request('manage/job-roles', {'name': 'Compliance Analyst', 'departmentId': cls.finance})
        self.assertEqual(role[0], 200, role[1])
        cls.analyst = next(j['id'] for j in self.admin.request('manage/org')[1]['jobRoles'] if j['name'] == 'Compliance Analyst')
        cls.manager = self.account('Line Manager', role='manager')
        cls.other_manager = self.account('Other Manager', role='manager')
        cls.on_time = self.account('Asha OnTime', departmentId=cls.finance, jobRoleId=cls.analyst, managerId=cls.manager.id)
        cls.late = self.account('Bala Late', departmentId=cls.finance, managerId=cls.other_manager.id)
        cls.progressing = self.account('Chitra Progress', departmentId=cls.sales, managerId=cls.manager.id)
        cls.waiting = self.account('Dev Waiting', departmentId=cls.sales, managerId=cls.other_manager.id)
        cls.lapsed = self.account('Esha Lapsed', departmentId=cls.sales, managerId=cls.manager.id)
        cls.drifting = self.account('Farid Drifting')
        cls.soon = self.account('Gita Soon')
        cls.finished_course = self.course('Finished Course')
        cls.open_course = self.course('Open Course')
        cls.lapsed_course = self.course('Lapsed Course')
        cls.optional_lapsed_course = self.course('Optional Lapsed Course')
        cls.soon_course = self.course('Soon Course')
        # Both finish; Bala's finish is moved past the deadline in force at the time.
        self.assign(cls.finished_course, cls.on_time.id, '2099-06-01T17:00')
        self.assign(cls.finished_course, cls.late.id, '2099-06-01T17:00')
        self.complete(cls.on_time, cls.finished_course)
        self.complete(cls.late, cls.finished_course)
        self.sql("UPDATE course_runs SET completed_at='2099-07-01T00:00:00.000Z',deadline_at_completion='2099-06-01T11:30:00.000Z' WHERE candidate_id=? AND course_id=?", cls.late.id, cls.finished_course)
        # Chitra has started; Dev has not. Dev also has the same course through a department, which must not add a row.
        self.assign(cls.open_course, cls.sales, '2099-08-01T10:00', target_type='department')
        self.assign(cls.open_course, cls.waiting.id, '2099-09-01T10:00', mandatory=False)
        cls.progressing.request('learning/enroll', {'courseId': cls.open_course})
        self.assertEqual(cls.progressing.action('video', videoIndex=0, watched=48, complete=True)[0], 200)
        # Esha is in Sales, so the department assignment above also gives her Open Course.
        self.assign(cls.lapsed_course, cls.lapsed.id, '2099-03-01T10:00')
        self.assign(cls.optional_lapsed_course, cls.drifting.id, '2099-03-01T10:00', mandatory=False)
        self.assign(cls.soon_course, cls.soon.id, self.in_days(2))
        self.backdate(cls.lapsed_course, utc_iso(utc_now() - timedelta(days=3, hours=2)))
        self.backdate(cls.optional_lapsed_course, utc_iso(utc_now() - timedelta(days=9)))
        cls.built = True

    def row(self, payload, employee, course):
        return next(r for r in payload['table']['rows'] if r['employeeId'] == employee.id and r['courseId'] == course)

    def test_summary_counts_every_assignment_once_and_adds_up(self):
        # Finance 2; Sales: Open Course x3 (Chitra, Dev, Esha) + Lapsed; none: Optional Lapsed + Soon.
        s = self.view()['summary']
        self.assertEqual(s, {'total': 8, 'completed': 2, 'completedOnTime': 1, 'completedLate': 1, 'inProgress': 1, 'notStarted': 3, 'overdue': 2, 'completionRate': 25})
        self.assertEqual(s['completedOnTime'] + s['completedLate'] + s['inProgress'] + s['notStarted'] + s['overdue'], s['total'])

    def test_duplicate_routes_to_a_course_give_one_row_using_the_assignment_in_force(self):
        rows = [r for r in self.view(course=self.open_course)['table']['rows'] if r['employeeId'] == self.waiting.id]
        self.assertEqual(len(rows), 1)
        # A mandatory department assignment beats an optional individual one.
        self.assertTrue(rows[0]['mandatory'])
        self.assertEqual(rows[0]['deadlineDisplay'], '1 August 2099, 10:00 AM')

    def test_table_row_has_every_required_field(self):
        r = self.row(self.view(), self.on_time, self.finished_course)
        self.assertEqual((r['employee'], r['employeeId'], r['department'], r['jobRole'], r['course'], r['mandatory']), ('Asha OnTime', self.on_time.id, 'Finance', 'Compliance Analyst', 'Finished Course', True))
        self.assertEqual((r['status'], r['statusLabel'], r['progress']), ('completed_on_time', 'Completed On Time', 100))
        self.assertEqual(r['deadlineDisplay'], '1 June 2099, 5:00 PM')
        self.assertTrue(r['assignedDisplay'] and r['completedDisplay'] and r['lastActivityDisplay'])

    def test_statuses(self):
        payload = self.view()
        self.assertEqual(self.row(payload, self.late, self.finished_course)['status'], 'completed_late')
        started = self.row(payload, self.progressing, self.open_course)
        self.assertEqual(started['status'], 'in_progress')
        self.assertGreater(started['progress'], 0)
        self.assertLess(started['progress'], 100)
        self.assertTrue(started['lastActivityDisplay'])
        self.assertEqual(self.row(payload, self.waiting, self.open_course)['status'], 'not_started')
        self.assertIsNone(self.row(payload, self.waiting, self.open_course)['lastActivity'])

    def test_due_soon_stays_in_its_stage_with_a_flag(self):
        r = self.row(self.view(), self.soon, self.soon_course)
        self.assertEqual((r['status'], r['dueSoon']), ('not_started', True))
        exported = next(c for c in self.csv_rows() if c['Employee ID'] == self.soon.id)
        self.assertEqual(exported['Current Status'], 'Not Started (Due Soon)')

    def test_each_filter_narrows_the_results_and_they_combine(self):
        names = lambda **query: sorted({r['employee'] for r in self.view(**query)['table']['rows']})
        self.assertEqual(names(employee=self.lapsed.id), ['Esha Lapsed'])
        self.assertEqual(names(department=self.finance), ['Asha OnTime', 'Bala Late'])
        self.assertEqual(names(department='__none__'), ['Farid Drifting', 'Gita Soon'])
        self.assertEqual(names(jobRole=self.analyst), ['Asha OnTime'])
        self.assertEqual(names(course=self.lapsed_course), ['Esha Lapsed'])
        self.assertEqual(names(type='optional'), ['Farid Drifting'])
        self.assertEqual(names(status='completed'), ['Asha OnTime', 'Bala Late'])
        self.assertEqual(names(status='completed_late'), ['Bala Late'])
        self.assertEqual(names(status='in_progress'), ['Chitra Progress'])
        self.assertEqual(names(status='overdue'), ['Esha Lapsed', 'Farid Drifting'])
        self.assertEqual(names(status='not_started', department=self.sales), ['Dev Waiting', 'Esha Lapsed'])
        self.assertEqual(names(q='asha'), ['Asha OnTime'])
        self.assertEqual(names(q='optional lapsed'), ['Farid Drifting'])
        self.assertEqual(names(status='overdue', type='mandatory', department=self.sales, course=self.lapsed_course, employee=self.lapsed.id), ['Esha Lapsed'])
        self.assertEqual(names(status='overdue', department=self.finance), [])
        self.assertEqual(self.view(department=self.finance)['summary']['total'], 2)

    def test_sorting(self):
        ordered = lambda **query: [r['employee'] for r in self.view(**query)['table']['rows']]
        self.assertEqual(ordered(sort='employee', dir='desc')[0], 'Gita Soon')
        self.assertEqual(ordered(sort='employee')[0], 'Asha OnTime')
        by_status = [r['status'] for r in self.view(sort='status')['table']['rows']]
        self.assertEqual(by_status[:2], ['overdue', 'overdue'])
        self.assertEqual(by_status[-1], 'completed_on_time')
        # Courses with no completion date stay last in both directions.
        for direction in ('asc', 'desc'):
            completed = [r['completedAt'] for r in self.view(sort='completed', dir=direction)['table']['rows']]
            self.assertEqual(completed[2:], [None] * 6)
        self.assertEqual(self.view(sort='progress', dir='desc')['table']['rows'][0]['progress'], 100)
        self.assertEqual(self.admin.request(url('manage/compliance', sort='password'))[0], 400)
        self.assertEqual(self.admin.request(url('manage/compliance', sort='employee', dir='sideways'))[0], 400)
        self.assertEqual(self.csv_rows(sort='employee', dir='desc')[0]['Employee Name'], 'Gita Soon')

    def test_dates_for_the_table_are_portal_dates(self):
        learner, course = self.account('Tara Dates'), self.course()
        self.assign(course, learner.id, '2099-03-02T01:30')  # Still 1 March in UTC.
        row = self.view(course=course)
        self.assertRegex(row['updatedDisplay'], r'\d{4}, \d+:\d{2} [AP]M')
        self.assertEqual(row['table']['rows'][0]['deadlineDate'], '2099-03-02')
        self.sql('DELETE FROM course_assignments WHERE course_id=?', course)

    def test_filter_values_are_checked(self):
        for query in ({'status': 'nonsense'}, {'type': 'nonsense'}, {'from': 'not-a-date'}, {'from': '2099-02-01', 'to': '2099-01-01'}):
            self.assertEqual(self.admin.request(url('manage/compliance', **query))[0], 400, query)
        self.assertEqual(self.raw_export(format='pdf')[0], 400)

    def test_deadline_range_uses_portal_dates_and_excludes_no_deadline(self):
        learner, course = self.account('Zoya Zone'), self.course()
        # 1:30 AM on 2 March in IST is still 1 March in UTC.
        self.assign(course, learner.id, '2099-03-02T01:30')
        self.assertEqual(self.view(course=course, **{'from': '2099-03-02', 'to': '2099-03-02'})['summary']['total'], 1)
        self.assertEqual(self.view(course=course, to='2099-03-01')['summary']['total'], 0)
        self.assertEqual(self.view(course=course, **{'from': '2099-03-03'})['summary']['total'], 0)
        open_ended, optional = self.account('Yash Open'), self.course()
        self.assign(optional, open_ended.id, None, mandatory=False)
        self.assertEqual(self.view(course=optional)['summary']['total'], 1)
        self.assertEqual(self.view(course=optional)['table']['rows'][0]['deadlineDisplay'], None)
        self.assertEqual(self.view(course=optional, **{'from': '2000-01-01'})['summary']['total'], 0)
        self.sql('DELETE FROM course_assignments WHERE course_id IN (?,?)', course, optional)

    def test_overdue_section(self):
        overdue = self.view()['overdue']
        self.assertEqual((overdue['total'], overdue['mandatory']), (2, 1))
        # Mandatory comes first even though the optional course has been overdue for longer.
        self.assertEqual([r['employee'] for r in overdue['rows']], ['Esha Lapsed', 'Farid Drifting'])
        first = overdue['rows'][0]
        self.assertTrue(first['mandatory'])
        self.assertEqual(first['overdueBy'], '3 days, 2 hours')
        self.assertEqual(first['originalDeadlineDisplay'], '1 March 2099, 10:00 AM')
        self.assertEqual(first['progress'], 0)
        self.assertIsNone(first['lastActivity'])
        self.assertEqual(overdue['rows'][1]['overdueBy'], '9 days')
        self.assertFalse(any(r['status'].startswith('completed') for r in overdue['rows']))

    def test_extending_a_deadline_clears_overdue(self):
        learner, course = self.account('Hari Extended'), self.course()
        self.assign(course, learner.id, '2099-03-01T10:00')
        self.backdate(course, utc_iso(utc_now() - timedelta(days=1)))
        self.assertEqual(self.view(course=course)['summary']['overdue'], 1)
        self.assign(course, learner.id, '2099-05-01T10:00')
        self.assertEqual(self.view(course=course)['summary'], {'total': 1, 'completed': 0, 'completedOnTime': 0, 'completedLate': 0, 'inProgress': 0, 'notStarted': 1, 'overdue': 0, 'completionRate': 0})
        self.sql('DELETE FROM course_assignments WHERE course_id=?', course)

    def test_department_analytics(self):
        departments = {d['department']: d for d in self.view()['departments']}
        self.assertEqual(departments['Finance'], {'department': 'Finance', 'total': 2, 'completed': 2, 'pending': 0, 'overdue': 0, 'completionRate': 100})
        self.assertEqual(departments['Sales'], {'department': 'Sales', 'total': 4, 'completed': 0, 'pending': 3, 'overdue': 1, 'completionRate': 0})
        self.assertEqual(departments['Unassigned'], {'department': 'Unassigned', 'total': 2, 'completed': 0, 'pending': 1, 'overdue': 1, 'completionRate': 0})
        self.assertEqual([d['department'] for d in self.view(department=self.finance)['departments']], ['Finance'])

    def test_csv_export_matches_the_filter_and_guards_formulas(self):
        rows = self.csv_rows(department=self.sales)
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['Department'] for r in rows}, {'Sales'})
        self.assertEqual(list(rows[0])[:6], ['Employee Name', 'Employee ID', 'Department', 'Job Role', 'Course Name', 'Mandatory/Optional'])
        self.assertIn('Deadline (IST)', rows[0])
        esha = next(r for r in rows if r['Course Name'] == 'Lapsed Course')
        self.assertEqual((esha['Employee ID'], esha['Mandatory/Optional'], esha['Current Status'], esha['Progress %'], esha['Overdue By']), (self.lapsed.id, 'Mandatory', 'Overdue', '0', '3 days, 2 hours'))
        status, body, headers = self.raw_export(format='csv')
        self.assertIn('attachment; filename="shimentox-training-compliance-', headers['Content-Disposition'])
        self.assertIn('text/csv', headers['Content-Type'])

        danger, course = self.account('=HYPERLINK Danger'), self.course()
        self.assign(course, danger.id, '2099-06-01T10:00')
        self.assertEqual(self.csv_rows(course=course)[0]['Employee Name'], "'=HYPERLINK Danger")
        self.sql('DELETE FROM course_assignments WHERE course_id=?', course)

    def test_excel_export_is_a_workbook_with_the_same_rows(self):
        status, body, headers = self.raw_export(format='xlsx', department=self.sales)
        self.assertEqual(status, 200)
        self.assertIn('spreadsheetml.sheet', headers['Content-Type'])
        self.assertTrue(headers['Content-Disposition'].rstrip('"').endswith('.xlsx'))
        with zipfile.ZipFile(io.BytesIO(body)) as package:
            self.assertIsNone(package.testzip())
            for part in package.namelist():
                ET.fromstring(package.read(part))  # Every part is well-formed XML.
            sheet = ET.fromstring(package.read('xl/worksheets/sheet1.xml'))
        rows = sheet.findall('.//x:sheetData/x:row', NS)
        self.assertEqual(len(rows), 5)  # Header and four Sales assignments.
        values = lambda row: [c.findtext('x:v', namespaces=NS) if c.find('x:v', NS) is not None else c.findtext('x:is/x:t', namespaces=NS) for c in row.findall('x:c', NS)]
        self.assertEqual(values(rows[0])[0], 'Employee Name')
        expected = self.csv_rows(department=self.sales)
        # Text and numbers both survive, and progress is stored as a real number.
        self.assertEqual([values(r)[1] for r in rows[1:]], [r['Employee ID'] for r in expected])
        progress = rows[1].findall('x:c', NS)[10]
        self.assertIsNone(progress.get('t'))
        self.assertIsNotNone(progress.find('x:v', NS))

    def test_export_is_recorded_and_viewing_changes_nothing(self):
        before = [self.sql(f'SELECT COUNT(*) FROM {t}')[0][0] for t in ('course_assignments', 'course_runs', 'admin_events', 'notifications', 'deadline_reminders')]
        self.view()
        self.view(status='overdue')
        self.assertEqual([self.sql(f'SELECT COUNT(*) FROM {t}')[0][0] for t in ('course_assignments', 'course_runs', 'admin_events', 'notifications', 'deadline_reminders')], before)
        self.csv_rows(department=self.finance)
        event = self.sql("SELECT detail FROM admin_events WHERE action='training_compliance_exported' ORDER BY id DESC LIMIT 1")[0][0]
        detail = json.loads(event)
        self.assertEqual((detail['format'], detail['rows'], detail['filters']), ('csv', 2, {'department': self.finance}))

    def test_hr_sees_the_organisation(self):
        hr = self.account('HR Person')
        self.sql("UPDATE candidates SET role='hr' WHERE id=?", hr.id)
        self.assertEqual(self.view(hr)['scope'], 'organisation')
        self.assertEqual(self.view(hr, status='overdue')['overdue']['total'], 2)
        self.assertEqual(len(self.csv_rows(hr, department=self.sales)), 4)
        self.sql("UPDATE candidates SET is_active=0 WHERE id=?", hr.id)

    def test_manager_is_limited_to_direct_reports_everywhere(self):
        mine, theirs = {self.on_time.id, self.progressing.id, self.lapsed.id}, {self.late.id, self.waiting.id, self.drifting.id, self.soon.id}
        payload = self.view(self.manager)
        self.assertEqual(payload['scope'], 'team')
        self.assertEqual({r['employeeId'] for r in payload['table']['rows']}, mine)
        self.assertEqual(payload['summary']['total'], 4)  # Asha 1, Chitra 1, Esha 2.
        self.assertEqual({r['employeeId'] for r in payload['overdue']['rows']}, {self.lapsed.id})
        # The filter menus name nobody and nothing outside the team.
        self.assertEqual({e[0] for e in payload['options']['employees']}, mine)
        self.assertNotIn('Optional Lapsed Course', [c[1] for c in payload['options']['courses']])
        # Asking for someone else returns nothing rather than their record.
        self.assertEqual(self.view(self.manager, employee=self.late.id)['summary']['total'], 0)
        self.assertEqual(self.csv_rows(self.manager, employee=self.late.id), [])
        self.assertEqual(self.view(self.manager, q='Bala')['summary']['total'], 0)
        exported = {r['Employee ID'] for r in self.csv_rows(self.manager)}
        self.assertEqual(exported, mine)
        self.assertFalse(exported & theirs)
        self.assertEqual({d['department'] for d in payload['departments']}, {'Finance', 'Sales'})

    def test_manager_with_no_reports_sees_nothing(self):
        lonely = self.account('Lonely Manager', role='manager')
        self.assertEqual(self.view(lonely)['summary']['total'], 0)
        self.assertEqual(self.csv_rows(lonely), [])

    def test_employees_trainers_and_anonymous_visitors_are_refused(self):
        trainer = self.account('Course Trainer')
        self.sql("UPDATE candidates SET role='trainer' WHERE id=?", trainer.id)
        for client in (self.on_time, trainer):
            self.assertEqual(client.request('manage/compliance')[0], 403)
            self.assertEqual(client.request(url('manage/compliance', employee=self.late.id))[0], 403)
            status, body, _ = self.raw_export(client, format='csv')
            self.assertEqual(status, 403)
            self.assertNotIn(b'Bala', body)
        anonymous = type(self.admin)(self.base)
        self.assertEqual(anonymous.request('manage/compliance')[0], 401)
        self.assertEqual(self.raw_export(anonymous, format='csv')[0], 401)
        self.sql("UPDATE candidates SET is_active=0 WHERE id=?", trainer.id)

    def test_disabled_employees_and_unpublished_courses_leave_the_figures(self):
        learner, course = self.account('Ira Leaver'), self.course('Temporary Course')
        self.assign(course, learner.id, '2099-06-01T10:00')
        self.assertEqual(self.view(course=course)['summary']['total'], 1)
        self.sql("UPDATE courses SET status='draft' WHERE id=?", course)
        self.assertEqual(self.view(course=course)['summary']['total'], 0)
        self.sql("UPDATE courses SET status='published' WHERE id=?", course)
        self.sql('UPDATE candidates SET is_active=0 WHERE id=?', learner.id)
        self.assertEqual(self.view(course=course)['summary']['total'], 0)


class CompliancePagingAndActivityTests(ComplianceFixture):
    def test_table_pages_while_totals_and_exports_cover_everything(self):
        department = next(d['id'] for d in self.admin.request('manage/org')[1]['departments'] if d['name'] == 'Sales')
        with closing(connect(self.db_path)) as db, db:
            for i in range(30):
                db.execute('INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,department_id) VALUES (?,?,?,?,?,?,?)', (uid(), f'Person {i:02d}', f'p{i}@shimentox.com', 'x', now(), now(), department))
        course = self.course()
        self.assign(course, department, '2099-06-01T10:00', target_type='department')
        self.assertEqual(len(self.view(course=course, size=10)['table']['rows']), 10)
        self.assertEqual(self.view(course=course, size=10, page=3)['table']['pages'], 3)
        self.assertEqual(self.admin.request(url('manage/compliance', size=1000))[0], 400)
        first, second = self.view(course=course), self.view(course=course, page=2)
        self.assertEqual((first['table']['total'], first['table']['pages'], len(first['table']['rows'])), (30, 2, 25))
        self.assertEqual(len(second['table']['rows']), 5)
        self.assertEqual(second['summary']['total'], 30)
        self.assertFalse({r['employeeId'] for r in first['table']['rows']} & {r['employeeId'] for r in second['table']['rows']})
        self.assertEqual(self.view(course=course, page=99)['table']['page'], 2)
        self.assertEqual(self.view(course=course, page='x')['table']['page'], 1)
        self.assertEqual(len(self.csv_rows(course=course)), 30)

    def test_a_partly_watched_lesson_counts_as_started(self):
        lesson = {'title': 'Only lesson', 'description': '', 'videoUrl': '', 'documentUrl': '', 'documentName': '', 'resources': [], 'content': 'Read this.', 'exercise': '', 'durationMinutes': 5, 'captionsUrl': '', 'videoSeconds': 0, 'completionPercent': 90}
        saved = self.admin.request('admin/courses', {'format': 'lessons', 'title': 'Lesson Course', 'category': 'Technical Skills', 'description': 'A lesson course.', 'status': 'published', 'difficulty': 'beginner', 'durationMinutes': 5, 'departmentId': None, 'visibility': 'everyone', 'skills': [], 'lessons': [lesson], 'assessment': None})
        self.assertEqual(saved[0], 200, saved[1])
        course = saved[1]['course']['id']
        learner = self.account('Watcher')
        self.assign(course, learner.id, '2099-06-01T10:00')
        learner.request('learning/enroll', {'courseId': course})
        self.assertEqual(self.view(employee=learner.id)['table']['rows'][0]['status'], 'not_started')
        with closing(connect(self.db_path)) as db, db:
            lesson_id = db.execute('SELECT id FROM course_lessons WHERE course_id=?', (course,)).fetchone()[0]
            run = db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=?', (learner.id, course)).fetchone()[0]
            db.execute('INSERT INTO lesson_watch(run_id,lesson_id,position_seconds,watched_seconds,updated_at) VALUES (?,?,?,?,?)', (run, lesson_id, 30, 30, now()))
        row = self.view(employee=learner.id)['table']['rows'][0]
        self.assertEqual((row['status'], row['progress']), ('in_progress', 0))
        self.assertTrue(row['lastActivityDisplay'])
