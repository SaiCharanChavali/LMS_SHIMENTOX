"""Automatic employee onboarding, over real HTTP and an isolated SQLite database. One test class per delivery phase."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import csv
import io
import urllib.error
import urllib.parse
import urllib.request
import uuid

from test_deadlines import DeadlineFixture, utc_now
from test_portal import Client
from database import connect
from deadlines import end_of_day, utc_iso
import onboarding as onboarding_module


def url(route, **query):
    return route + ('?' + urllib.parse.urlencode(query) if query else '')


class OnboardingFixture(DeadlineFixture):
    def sql(self, statement, *params):
        with closing(connect(self.db_path)) as db, db:
            return db.execute(statement, params).fetchall()

    def department(self, name):
        return self.sql('SELECT id FROM departments WHERE name=?', name)[0][0]

    def job_role(self, name, department=None):
        identity = uuid.uuid4().hex
        self.sql('INSERT INTO job_roles(id,name,department_id,created_at) VALUES (?,?,?,?)', identity, name, department, '2026-01-01T00:00:00.000Z')
        return identity

    def staff(self, role, name=None):
        client = self.account(name or f'{role.title()} Person')
        self.sql('UPDATE candidates SET role=? WHERE id=?', role, client.id)
        return client

    def hire(self, name='New Hire', client=None, **profile):
        """Create an employee through Users & Teams, as HR does; returns (client id, onboarding outcome)."""
        email = f'{uuid.uuid4().hex}@shimentox.com'
        result = (client or self.admin).request('admin/candidates', {'name': name, 'email': email, 'password': 'Temporary123!', **profile})
        self.assertEqual(result[0], 200, result[1])
        return result[1]['candidate']['id'], result[1]['onboarding']

    def sign_in(self, employee_id):
        email = self.sql('SELECT email FROM candidates WHERE id=?', employee_id)[0][0]
        client = Client(self.base)
        client.request('auth/login', {'email': email, 'password': 'Temporary123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})[0], 200)
        client.id = employee_id
        return client

    def template(self, name, courses, department=None, roles=(), status='active', milestones=((1, 'Day 1'), (7, 'Week 1'), (30, 'Day 30')), client=None, expected=200):
        payload = {'name': name, 'description': f'{name} onboarding', 'departmentId': department, 'jobRoleIds': list(roles), 'status': status,
                   'milestones': [{'day': d, 'title': t} for d, t in milestones], 'courses': [{'courseId': c, 'day': d, 'mandatory': m} for c, d, m in courses]}
        result = (client or self.admin).request('manage/onboarding/templates', payload)
        self.assertEqual(result[0], expected, result[1])
        return result[1].get('templateId'), result[1]

    def plan(self, employee_id):
        return self.sql("SELECT * FROM employee_onboarding WHERE employee_id=? AND status='active'", employee_id)

    def employee_assignments(self, employee_id):
        return {r['course_id']: dict(r) for r in self.sql("SELECT * FROM course_assignments WHERE target_type='employee' AND target_id=?", employee_id)}

    def today(self):
        return onboarding_module.today()

    def expected_deadline(self, joining, day):
        return end_of_day((date.fromisoformat(joining) + timedelta(days=day - 1)).isoformat())


# ---------------------------------------------------------------- phase 1: templates

class OnboardingTemplateTests(OnboardingFixture):
    def test_hr_creates_lists_and_edits_a_template(self):
        hr = self.staff('hr')
        finance = self.department('Finance')
        analyst = self.job_role('Template Analyst', finance)
        first, second = self.course('Welcome to ShimentoX'), self.course('Code of Conduct')
        identity, payload = self.template('Finance analysts', [(first, 1, True), (second, 7, False)], finance, [analyst], status='draft', client=hr)
        listed = next(t for t in payload['templates'] if t['id'] == identity)
        self.assertEqual((listed['status'], listed['department'], listed['jobRoles'], listed['mandatoryCount']), ('draft', 'Finance', ['Template Analyst'], 1))
        self.assertEqual([(c['title'], c['day'], c['mandatory']) for c in listed['courses']], [('Welcome to ShimentoX', 1, True), ('Code of Conduct', 7, False)])
        self.assertEqual([m['day'] for m in listed['milestones']], [1, 7, 30])
        self.assertIn([first, 'Welcome to ShimentoX'], payload['options']['courses'])
        # Edit: rename and make the second course mandatory at day 30.
        edited = hr.request('manage/onboarding/templates', {'id': identity, 'name': 'Finance analysts v2', 'description': '', 'departmentId': finance, 'jobRoleIds': [analyst],
                                                             'milestones': [{'day': 1, 'title': 'First day'}, {'day': 30, 'title': ''}],
                                                             'courses': [{'courseId': first, 'day': 1, 'mandatory': True}, {'courseId': second, 'day': 30, 'mandatory': True}]})
        self.assertEqual(edited[0], 200, edited[1])
        listed = next(t for t in edited[1]['templates'] if t['id'] == identity)
        self.assertEqual((listed['name'], listed['mandatoryCount'], [m['title'] for m in listed['milestones']]), ('Finance analysts v2', 2, ['First day', 'Day 30']))
        actions = [r[0] for r in self.sql("SELECT action FROM admin_events WHERE target_id=? ORDER BY id", identity)]
        self.assertEqual(actions, ['onboarding_template_created', 'onboarding_template_updated'])

    def test_templates_use_published_courses_and_need_a_mandatory_course(self):
        course, draft = self.course(), self.course()
        self.sql("UPDATE courses SET status='draft' WHERE id=?", draft)
        cases = [
            ([(draft, 1, True)], 'not published'),
            ([(course, 1, False)], 'at least one course as mandatory'),
            ([(course, 1, True), (course, 1, False)], 'listed twice'),
            ([(course, 5, True)], 'Choose a milestone'),
            ([], 'Add 1 to'),
        ]
        for courses, message in cases:
            _, body = self.template('Invalid', courses, expected=400 if courses else 400)
            self.assertIn(message, body['error'], courses)
        # An empty milestone is kept on the template and left out of employee plans.
        identity, body = self.template('Empty milestone', [(course, 1, True)], milestones=((1, 'Day 1'), (90, 'Day 90')), status='draft')
        self.assertEqual([m['day'] for m in next(t for t in body['templates'] if t['id'] == identity)['milestones']], [1, 90])
        _, body = self.template('Bad day', [(course, 1, True)], milestones=((1, ''), (1, 'Again')), expected=400)
        self.assertIn('listed twice', body['error'])
        bad = self.admin.request('manage/onboarding/templates', {'name': 'Bad department', 'departmentId': 'nope', 'milestones': [{'day': 1}], 'courses': [{'courseId': course, 'day': 1, 'mandatory': True}]})
        self.assertEqual(bad[0], 400)

    def test_status_changes_and_conflicting_active_templates(self):
        sales = self.department('Sales')
        rep, lead = self.job_role('Sales Rep', sales), self.job_role('Sales Lead', sales)
        course = self.course()
        first, _ = self.template('Sales reps', [(course, 1, True)], sales, [rep])
        # Same department and an overlapping job role would make matching ambiguous.
        _, body = self.template('Sales reps again', [(course, 1, True)], sales, [rep, lead], expected=409)
        self.assertIn('Sales reps', body['error'])
        # A different job role, or the whole department, is a different scope.
        leads, _ = self.template('Sales leads', [(course, 1, True)], sales, [lead])
        whole, _ = self.template('All of sales', [(course, 1, True)], sales)
        status = lambda identity, value: self.admin.request(f'manage/onboarding/templates/{identity}/status', {'status': value})
        self.assertEqual(status(first, 'inactive')[0], 200)
        self.assertEqual(status(first, 'draft')[0], 409)
        self.assertEqual(status(first, 'archived')[0], 200)
        edit = self.admin.request('manage/onboarding/templates', {'id': first, 'name': 'Archived edit', 'milestones': [{'day': 1}], 'courses': [{'courseId': course, 'day': 1, 'mandatory': True}]})
        self.assertEqual(edit[0], 409)
        self.assertEqual(status(first, 'active')[0], 409, 'Archived templates are restored as inactive first.')
        self.assertEqual(status(first, 'inactive')[0], 200)
        # Reactivating would clash with nothing now that "Sales reps again" was never created.
        self.assertEqual(status(first, 'active')[0], 200)
        # A course unpublished after saving blocks activation.
        self.assertEqual(status(leads, 'inactive')[0], 200)
        self.sql("UPDATE courses SET status='draft' WHERE id=?", course)
        refused = status(leads, 'active')
        self.assertEqual(refused[0], 409)
        self.assertIn('no longer published', refused[1]['error'])
        warnings = next(t for t in self.admin.request('manage/onboarding/templates')[1]['templates'] if t['id'] == whole)['warnings']
        self.assertTrue(any('not published' in w for w in warnings))

    def test_only_hr_and_admin_manage_templates(self):
        course = self.course()
        for role in ('employee', 'manager', 'trainer'):
            client = self.staff(role) if role != 'employee' else self.account()
            self.assertEqual(client.request('manage/onboarding/templates')[0], 403, role)
            self.template('Not allowed', [(course, 1, True)], client=client, expected=403)
            self.assertEqual(client.request('manage/onboarding/start', {'employeeId': client.id})[0], 403, role)


# ---------------------------------------------------------------- phase 2: automatic assignment

class OnboardingAssignmentTests(OnboardingFixture):
    built = False

    def setUp(self):
        cls = type(self)
        if cls.built:
            return
        cls.engineering = self.department('Engineering')
        cls.developer = self.job_role('Developer', cls.engineering)
        cls.tester = self.job_role('Tester', cls.engineering)
        cls.welcome, cls.security, cls.tools, cls.extra, cls.general = (self.course(t) for t in ('Welcome', 'Security Basics', 'Developer Tools', 'Optional Reading', 'Company Basics'))
        cls.dev_template, _ = self.template('Engineering developers', [(cls.welcome, 1, True), (cls.security, 7, True), (cls.tools, 30, True), (cls.extra, 30, False)],
                                           cls.engineering, [cls.developer])
        cls.dept_template, _ = self.template('Engineering', [(cls.welcome, 1, True), (cls.security, 7, True)], cls.engineering)
        cls.general_template, _ = self.template('Everyone', [(cls.general, 1, True)], milestones=((1, 'Day 1'),))
        cls.built = True

    def test_new_employee_gets_the_most_specific_template_with_deadlines_from_joining(self):
        joining = (self.today() + timedelta(days=3)).isoformat()
        employee, outcome = self.hire('Asha Developer', departmentId=self.engineering, jobRoleId=self.developer, joiningDate=joining)
        self.assertEqual((outcome['status'], outcome['template'], outcome['assigned'], outcome['linked'], outcome['skipped']), ('started', 'Engineering developers', 4, 0, 0))
        rows = self.employee_assignments(employee)
        self.assertEqual(set(rows), {self.welcome, self.security, self.tools, self.extra})
        self.assertEqual(rows[self.welcome]['deadline_at'], self.expected_deadline(joining, 1))
        self.assertEqual(rows[self.security]['deadline_at'], self.expected_deadline(joining, 7))
        self.assertEqual(rows[self.tools]['deadline_at'], self.expected_deadline(joining, 30))
        self.assertEqual(rows[self.tools]['original_deadline_at'], rows[self.tools]['deadline_at'])
        self.assertEqual((rows[self.extra]['mandatory'], rows[self.extra]['deadline_at']), (0, None), 'Optional courses have a target milestone but no deadline.')
        self.assertTrue(all(r['note'] == 'Onboarding: Engineering developers' for r in rows.values()))
        plan = self.plan(employee)[0]
        self.assertEqual((plan['template_id'], plan['source'], plan['start_date'], plan['joining_date']), (self.dev_template, 'automatic', joining, joining))
        snapshot = self.sql('SELECT course_id,day,mandatory,link,assignment_id FROM employee_onboarding_courses WHERE onboarding_id=? ORDER BY position', plan['id'])
        self.assertEqual([(r['course_id'], r['day'], r['mandatory'], r['link']) for r in snapshot],
                         [(self.welcome, 1, 1, 'created'), (self.security, 7, 1, 'created'), (self.tools, 30, 1, 'created'), (self.extra, 30, 0, 'created')])
        # The employee sees the courses, with their deadlines, in My Learning.
        learner = self.sign_in(employee)
        cards = {c['id']: c for c in learner.request('courses')[1]['courses']}
        self.assertTrue(cards[self.welcome]['assignment']['mandatory'])
        self.assertEqual(cards[self.tools]['deadline']['at'], self.expected_deadline(joining, 30))
        # One plan notice, not one per course; the reminder pass does not repeat the announcements.
        notes = self.sql("SELECT title FROM notifications WHERE employee_id=? AND kind<>'account'", employee)
        self.assertEqual([n[0] for n in notes], ['Your onboarding plan: Engineering developers'])
        self.process(employee, utc_now())
        self.assertEqual(len(self.sql("SELECT 1 FROM notifications WHERE employee_id=? AND kind='assignment'", employee)), 1)
        self.assertEqual(len(self.sql("SELECT 1 FROM deadline_reminders WHERE employee_id=? AND reminder_type='assigned' AND status='sent'", employee)), 4)
        event = self.sql("SELECT detail FROM admin_events WHERE action='onboarding_started' AND target_id=?", employee)[0][0]
        self.assertIn('Engineering developers (automatic)', event)

    def test_department_and_general_templates_and_no_match(self):
        tester, outcome = self.hire('Tara Tester', departmentId=self.engineering, jobRoleId=self.tester)
        self.assertEqual(outcome['template'], 'Engineering', 'A tester is not a developer: the department template applies.')
        nobody, outcome = self.hire('Nora Elsewhere', departmentId=self.department('Marketing'))
        self.assertEqual(outcome['template'], 'Everyone')
        self.sql("UPDATE onboarding_templates SET status='inactive' WHERE id=?", self.general_template)
        try:
            lone, outcome = self.hire('Lena Unmatched', departmentId=self.department('Marketing'))
            self.assertEqual(outcome['status'], 'no_template')
            self.assertIn('Onboarding → Templates', outcome['message'])
            self.assertEqual(self.employee_assignments(lone), {}, 'No template means no courses at all.')
            self.assertEqual(self.plan(lone), [])
            waiting = self.admin.request('manage/onboarding')[1]['needsOnboarding']['rows']
            self.assertEqual(next(r for r in waiting if r['employeeId'] == lone)['reason'], 'no_template')
        finally:
            self.sql("UPDATE onboarding_templates SET status='active' WHERE id=?", self.general_template)

    def test_existing_assignments_are_linked_not_duplicated_and_starting_twice_is_refused(self):
        employee, outcome = self.hire('Dev Existing', departmentId=self.engineering, jobRoleId=self.developer, joiningDate=None)
        plan = self.plan(employee)[0]
        # Cancel, then give them a department-wide mandatory assignment for one course before restarting.
        self.assertEqual(self.admin.request(f'manage/onboarding/{plan["id"]}/cancel', {})[0], 200)
        self.assertEqual(self.employee_assignments(employee), {}, 'Cancelling removes the open assignments it created.')
        self.assign(self.security, self.engineering, self.in_days(60), target_type='department')
        before = len(self.sql('SELECT 1 FROM course_assignments'))
        started = self.admin.request('manage/onboarding/start', {'employeeId': employee})
        self.assertEqual(started[0], 200, started[1])
        self.assertEqual((started[1]['assigned'], started[1]['linked']), (3, 1))
        self.assertEqual(len(self.sql('SELECT 1 FROM course_assignments')), before + 3)
        self.assertNotIn(self.security, self.employee_assignments(employee), 'The department assignment stays in force; no individual copy.')
        linked = self.sql("SELECT link,note FROM employee_onboarding_courses WHERE onboarding_id=(SELECT id FROM employee_onboarding WHERE employee_id=? AND status='active') AND course_id=?",
                          employee, self.security)[0]
        self.assertEqual(tuple(linked), ('existing', 'Already assigned'))
        again = self.admin.request('manage/onboarding/start', {'employeeId': employee})
        self.assertEqual(again[0], 409)
        self.assertIn('already has onboarding in progress', again[1]['error'])
        self.assertEqual(len(self.sql('SELECT 1 FROM course_assignments')), before + 3, 'A refused start writes nothing.')
        self.sql('DELETE FROM course_assignments WHERE course_id=? AND target_type=?', self.security, 'department')

    def test_past_joining_date_never_makes_a_course_overdue_on_day_one(self):
        joining = (self.today() - timedelta(days=20)).isoformat()
        employee, outcome = self.hire('Late Entry', departmentId=self.engineering, jobRoleId=self.developer, joiningDate=joining)
        rows = self.employee_assignments(employee)
        floor = end_of_day(self.today().isoformat())
        self.assertEqual(rows[self.welcome]['deadline_at'], floor, 'Day 1 was 20 days ago: due by the end of today instead.')
        self.assertEqual(rows[self.security]['deadline_at'], floor)
        self.assertEqual(rows[self.tools]['deadline_at'], self.expected_deadline(joining, 30), 'Day 30 is still ahead and keeps its date.')
        self.assertEqual(self.plan(employee)[0]['start_date'], joining)

    def test_manual_start_for_an_existing_employee(self):
        employee = self.account('Long Serving', departmentId=self.engineering).id  # department template
        self.sql("DELETE FROM course_assignments WHERE target_id=?", employee)
        self.sql("DELETE FROM employee_onboarding WHERE employee_id=?", employee)
        self.sql("UPDATE candidates SET joining_date='2020-01-15' WHERE id=?", employee)
        waiting = {r['employeeId']: r for r in self.admin.request('manage/onboarding')[1]['needsOnboarding']['rows']}
        self.assertEqual((waiting[employee]['template'], waiting[employee]['defaultStartDate']), ('Engineering', self.today().isoformat()),
                         'An old joining date starts the plan today, not years ago.')
        start = (self.today() + timedelta(days=10)).isoformat()
        result = self.admin.request('manage/onboarding/start', {'employeeId': employee, 'templateId': self.general_template, 'startDate': start})
        self.assertEqual(result[0], 200, result[1])
        plan = self.plan(employee)[0]
        self.assertEqual((plan['template_name'], plan['source'], plan['start_date']), ('Everyone', 'manual', start))
        self.assertEqual(self.employee_assignments(employee)[self.general]['deadline_at'], self.expected_deadline(start, 1))
        self.assertEqual(self.admin.request('manage/onboarding/start', {'employeeId': employee, 'startDate': '15/01/2020'})[0], 400)

    def test_template_changes_do_not_rewrite_started_onboarding(self):
        employee, _ = self.hire('Snapshot Sam', departmentId=self.engineering, jobRoleId=self.tester)
        plan = self.plan(employee)[0]
        before = self.sql('SELECT course_id,day,milestone_title FROM employee_onboarding_courses WHERE onboarding_id=? ORDER BY position', plan['id'])
        edit = self.admin.request('manage/onboarding/templates', {'id': self.dept_template, 'name': 'Engineering (renamed)', 'departmentId': self.engineering,
                                                                  'milestones': [{'day': 60, 'title': 'Day 60'}], 'courses': [{'courseId': self.general, 'day': 60, 'mandatory': True}]})
        self.assertEqual(edit[0], 200, edit[1])
        try:
            after = self.sql('SELECT course_id,day,milestone_title FROM employee_onboarding_courses WHERE onboarding_id=? ORDER BY position', plan['id'])
            self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after])
            self.assertEqual(self.plan(employee)[0]['template_name'], 'Engineering')
            self.assertEqual(set(self.employee_assignments(employee)), {self.welcome, self.security})
        finally:
            self.admin.request('manage/onboarding/templates', {'id': self.dept_template, 'name': 'Engineering', 'departmentId': self.engineering,
                                                               'milestones': [{'day': 1, 'title': 'Day 1'}, {'day': 7, 'title': 'Week 1'}],
                                                               'courses': [{'courseId': self.welcome, 'day': 1, 'mandatory': True}, {'courseId': self.security, 'day': 7, 'mandatory': True}]})

    def test_unpublished_courses_are_skipped_and_failures_never_block_the_account(self):
        lone = self.course('Retired Course')
        marketing = self.department('Marketing')
        writer = self.job_role('Writer', marketing)
        template, _ = self.template('Writers', [(lone, 1, True), (self.general, 1, True)], marketing, [writer])
        self.sql("UPDATE courses SET status='draft' WHERE id=?", lone)
        employee, outcome = self.hire('Will Writer', departmentId=marketing, jobRoleId=writer)
        self.assertEqual((outcome['assigned'], outcome['skipped']), (1, 1))
        self.assertIn('skipped', outcome['message'])
        self.assertNotIn(lone, self.employee_assignments(employee))
        # Admins are never onboarded; creating the account still works when something goes wrong.
        self.sql("UPDATE onboarding_templates SET status='inactive' WHERE id=?", template)

    def test_only_hr_and_admin_start_or_cancel(self):
        manager = self.staff('manager')
        employee, _ = self.hire('Scoped Person', departmentId=self.engineering, jobRoleId=self.tester, managerId=manager.id)
        plan = self.plan(employee)[0]
        self.assertEqual(manager.request(f'manage/onboarding/{plan["id"]}/cancel', {})[0], 403)
        self.assertEqual(manager.request('manage/onboarding/start', {'employeeId': employee})[0], 403)
        learner = self.sign_in(employee)
        self.assertEqual(learner.request(f'manage/onboarding/{plan["id"]}')[0], 403)


# ---------------------------------------------------------------- phase 3: the employee's onboarding view

class OnboardingEmployeeViewTests(OnboardingFixture):
    def test_progress_milestones_assessments_and_completion(self):
        sales = self.department('Sales')
        first, second, optional = self.course('Sales Welcome'), self.course('Sales Process'), self.course('Sales Extras')
        self.template('Sales', [(first, 1, True), (second, 7, True), (optional, 7, False)], sales)
        joining = (self.today() + timedelta(days=1)).isoformat()
        employee, _ = self.hire('Sam Seller', departmentId=sales, joiningDate=joining)
        learner = self.sign_in(employee)
        view = learner.request('me/onboarding')[1]['onboarding']
        self.assertEqual((view['template'], view['status'], view['percent'], view['mandatoryTotal'], view['optionalTotal']), ('Sales', 'not_started', 0, 2, 1))
        self.assertEqual([(m['day'], m['title'], m['state'], m['mandatoryTotal']) for m in view['milestones']], [(1, 'Day 1', 'upcoming', 1), (7, 'Week 1', 'upcoming', 1)])
        self.assertEqual(view['milestones'][0]['date'], joining)
        self.assertEqual(view['nextMilestone']['day'], 1)
        # Finishing the optional course does not count towards completion.
        self.complete(learner, optional)
        view = learner.request('me/onboarding')[1]['onboarding']
        self.assertEqual((view['percent'], view['optionalDone'], view['status']), (0, 1, 'in_progress'))
        self.complete(learner, first)
        view = learner.request('me/onboarding')[1]['onboarding']
        courses = {c['courseId']: c for c in view['courses']}
        self.assertEqual((view['percent'], courses[first]['status'], courses[first]['progress']), (50, 'completed_on_time', 100))
        self.assertEqual(courses[first]['assessment']['label'], '3 of 3 module exams passed')
        self.assertEqual(view['milestones'][0]['state'], 'completed')
        self.assertEqual(view['nextMilestone']['day'], 7)
        self.complete(learner, second)
        view = learner.request('me/onboarding')[1]['onboarding']
        self.assertEqual((view['status'], view['percent']), ('completed', 100))
        self.assertTrue(view['completedAt'])
        # No new certificate rule: only the existing per-course certificates exist.
        certificates = self.sql('SELECT COUNT(*) FROM certificates x JOIN course_runs r ON r.id=x.run_id WHERE r.candidate_id=?', employee)[0][0]
        self.assertEqual(certificates, 3)

    def test_overdue_and_employees_without_onboarding(self):
        hr_only = self.account('No Plan')
        self.assertIsNone(hr_only.request('me/onboarding')[1]['onboarding'])
        finance = self.department('Finance')
        course = self.course('Finance Welcome')
        self.template('Finance', [(course, 1, True)], finance)
        employee, _ = self.hire('Fay Finance', departmentId=finance)
        self.backdate(course, utc_iso(utc_now() - timedelta(days=2)))
        view = self.sign_in(employee).request('me/onboarding')[1]['onboarding']
        self.assertEqual((view['status'], view['overdueMandatory'], view['milestones'][0]['state']), ('overdue', 1, 'upcoming'),
                         'The course deadline moved, so the course is overdue; the milestone date is the plan\'s own.')


# ---------------------------------------------------------------- phase 4: reminders

class OnboardingReminderTests(OnboardingFixture):
    def test_milestone_reminders_once_each_to_the_right_people(self):
        hr_dept = self.department('Human Resources')
        first, second = self.course('HR Welcome'), self.course('HR Policies')
        self.template('HR', [(first, 1, True), (second, 30, True)], hr_dept)
        manager = self.staff('manager', 'Mia Manager')
        joining = self.today().isoformat()
        employee, _ = self.hire('Hal Hire', departmentId=hr_dept, managerId=manager.id, joiningDate=joining)
        titles = lambda person: [r[0] for r in self.sql("SELECT title FROM notifications WHERE employee_id=? AND kind='onboarding' ORDER BY id", person)]
        now = utc_now()
        self.process(employee, now)
        self.assertEqual(titles(employee), [], 'Day 1 was already inside the window when onboarding began: no "coming up" notice.')
        # Five days before Day 30: one "coming up" notice, however many passes run.
        day30 = datetime.fromisoformat(self.expected_deadline(joining, 30).replace('Z', '+00:00'))
        for _ in range(3):
            self.process(employee, day30 - timedelta(days=5))
        self.assertEqual(titles(employee).count('Onboarding milestone coming up: Day 30'), 1)
        # Day 1 missed: the employee and their manager are told, once.
        day1 = datetime.fromisoformat(self.expected_deadline(joining, 1).replace('Z', '+00:00'))
        for _ in range(2):
            self.process(employee, day1 + timedelta(hours=2))
        self.assertEqual(titles(employee).count('Onboarding milestone missed: Day 1'), 1)
        self.assertEqual(titles(manager.id), ['Hal Hire missed an onboarding milestone'])
        # Completing everything sends one completion notice to each.
        learner = self.sign_in(employee)
        self.complete(learner, first)
        self.complete(learner, second)
        for _ in range(2):
            self.process(employee, utc_now())
        self.assertEqual(titles(employee).count('Onboarding complete'), 1)
        self.assertEqual(titles(manager.id).count('Hal Hire completed onboarding'), 1)
        # Completed courses get no further course reminders either.
        self.process(employee, day30 + timedelta(days=1))
        self.assertNotIn('Onboarding milestone missed: Day 30', titles(employee))

    def test_disabled_employees_get_no_onboarding_reminders(self):
        it = self.department('Engineering')
        course = self.course('IT Welcome')
        self.template('IT', [(course, 1, True)], it)
        employee, _ = self.hire('Ivy Inactive', departmentId=it)
        self.sql('UPDATE candidates SET is_active=0 WHERE id=?', employee)
        self.process(employee, utc_now() + timedelta(days=5))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications WHERE employee_id=? AND kind='onboarding'", employee)[0][0], 0)


# ---------------------------------------------------------------- phase 5: HR and manager reporting

class OnboardingReportingTests(OnboardingFixture):
    built = False

    def setUp(self):
        cls = type(self)
        if cls.built:
            return
        cls.finance, cls.sales = self.department('Finance'), self.department('Sales')
        cls.analyst = self.job_role('Report Analyst', cls.finance)
        cls.a, cls.b = self.course('Report Course A'), self.course('Report Course B')
        self.template('Finance', [(cls.a, 1, True), (cls.b, 30, False)], cls.finance)
        self.template('Sales', [(cls.a, 1, True), (cls.b, 7, True)], cls.sales)
        cls.manager = self.staff('manager', 'Rita Reports')
        cls.done, _ = self.hire('Dana Done', departmentId=cls.finance, jobRoleId=cls.analyst, managerId=cls.manager.id, joiningDate='2026-01-10')
        cls.late, _ = self.hire('Leo Late', departmentId=cls.sales, managerId=cls.manager.id, joiningDate='2026-02-10')
        cls.fresh, _ = self.hire('Fred Fresh', departmentId=cls.sales, joiningDate='2026-03-10')
        self.complete(self.sign_in(cls.done), cls.a)
        self.sql("UPDATE course_assignments SET deadline_at=? WHERE target_id=? AND course_id=?", utc_iso(utc_now() - timedelta(days=1)), cls.late, cls.a)
        cls.built = True

    def test_summary_groups_and_filters(self):
        data = self.admin.request('manage/onboarding')[1]
        mine = {r['employee']: r for r in data['table']['rows'] if r['employee'] in ('Dana Done', 'Leo Late', 'Fred Fresh')}
        self.assertEqual((mine['Dana Done']['status'], mine['Dana Done']['percent'], mine['Dana Done']['optionalTotal']), ('completed', 100, 1))
        self.assertEqual((mine['Leo Late']['status'], mine['Leo Late']['overdueMandatory'], mine['Leo Late']['pendingMandatory']), ('overdue', 1, 2))
        self.assertEqual((mine['Fred Fresh']['status'], mine['Fred Fresh']['percent']), ('not_started', 0))
        s = data['summary']
        self.assertEqual((s['onboarding'], s['completed'], s['pendingEmployees'], s['overdueEmployees'], s['overdueMandatory']), (2, 1, 2, 1, 1))
        self.assertEqual(s['averagePercent'], round(100 / 3))
        groups = {g['name']: g for g in data['departments']}
        self.assertEqual((groups['Sales']['employees'], groups['Sales']['overdue'], groups['Finance']['completed']), (2, 1, 1))
        self.assertEqual({g['name'] for g in data['jobRoles']}, {'Report Analyst', 'Unassigned'})
        names = lambda **q: sorted(r['employee'] for r in self.admin.request(url('manage/onboarding', **q))[1]['table']['rows'])
        self.assertEqual(names(department=self.sales), ['Fred Fresh', 'Leo Late'])
        self.assertEqual(names(jobRole=self.analyst), ['Dana Done'])
        self.assertEqual(names(status='overdue'), ['Leo Late'])
        self.assertEqual(names(**{'from': '2026-02-01', 'to': '2026-02-28'}), ['Leo Late'])
        self.assertEqual(names(q='fred'), ['Fred Fresh'])
        self.assertEqual(names(department=self.sales, status='not_started'), ['Fred Fresh'])
        for bad in ({'status': 'nonsense'}, {'from': 'yesterday'}, {'from': '2026-03-01', 'to': '2026-01-01'}):
            self.assertEqual(self.admin.request(url('manage/onboarding', **bad))[0], 400, bad)

    def test_individual_summary_and_export(self):
        plan = self.plan(self.late)[0]
        detail = self.admin.request(f'manage/onboarding/{plan["id"]}')[1]['onboarding']
        self.assertEqual((detail['employee'], detail['department'], detail['template'], detail['status']), ('Leo Late', 'Sales', 'Sales', 'overdue'))
        self.assertEqual(len(detail['courses']), 2)
        request = urllib.request.Request(self.base + '/api/' + url('manage/onboarding/export', format='csv', department=self.sales))
        with self.admin.opener.open(request, timeout=15) as response:
            body = response.read().decode('utf-8-sig')
            self.assertIn('attachment; filename="shimentox-onboarding-', response.headers['Content-Disposition'])
        rows = list(csv.DictReader(io.StringIO(body)))
        self.assertEqual(sorted(r['Employee Name'] for r in rows), ['Fred Fresh', 'Leo Late'])
        self.assertEqual(next(r for r in rows if r['Employee Name'] == 'Leo Late')['Overdue Mandatory'], '1')
        self.assertTrue(self.sql("SELECT 1 FROM admin_events WHERE action='onboarding_report_exported'"))

    def test_manager_sees_only_their_team_and_others_are_refused(self):
        data = self.manager.request('manage/onboarding')[1]
        self.assertEqual(sorted(r['employee'] for r in data['table']['rows']), ['Dana Done', 'Leo Late'])
        self.assertNotIn('needsOnboarding', data)
        self.assertFalse(data['canManage'])
        outsider = self.plan(self.fresh)[0]
        self.assertEqual(self.manager.request(f'manage/onboarding/{outsider["id"]}')[0], 403)
        self.assertEqual(self.manager.request(f'manage/onboarding/{self.plan(self.late)[0]["id"]}')[0], 200)
        trainer, learner = self.staff('trainer'), self.sign_in(self.fresh)
        for client in (trainer, learner):
            self.assertEqual(client.request('manage/onboarding')[0], 403)
        hr = self.staff('hr')
        self.assertTrue(hr.request('manage/onboarding')[1]['canManage'])
