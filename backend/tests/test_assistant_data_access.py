"""The LMS assistant reads only existing endpoints, so its permissions are those endpoints' permissions.

These tests pin that contract for every endpoint the assistant calls (frontend/public/scripts/chatbot-data.js):
an employee sees only their own records, a manager only their direct reports, HR and admins the organisation,
and a trainer only the courses they own. Identity always comes from the session, never from the request.
"""
from contextlib import closing
import uuid

from test_portal import PortalFixture, Client
from database import connect

COURSE = 'agile-and-scrum'


class AssistantDataAccessTests(PortalFixture):
    def account(self, role, name, manager_id=None):
        client = Client(self.base)
        email = f'{uuid.uuid4().hex}@shimentox.com'
        created = self.admin.request('admin/candidates', {'name': name, 'email': email, 'password': 'Temporary123!', 'role': 'manager' if role == 'manager' else 'employee', **({'managerId': manager_id} if manager_id else {})})
        self.assertEqual(created[0], 200, created[1])
        client.id = created[1]['candidate']['id']
        if role in ('hr', 'trainer'):
            with closing(connect(self.db_path)) as db, db:
                db.execute('UPDATE candidates SET role=? WHERE id=?', (role, client.id))
        client.request('auth/login', {'email': email, 'password': 'Temporary123!'})
        client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        return client

    def assign(self, employee_id):
        result = self.admin.request('manage/assignments', {'courseId': COURSE, 'targetType': 'employee', 'targetId': employee_id, 'mandatory': True, 'deadline': '2099-05-01T17:00'})
        self.assertEqual(result[0], 200, result[1])

    def setUp(self):
        super().setUp()
        self.manager = self.account('manager', 'Assistant Manager')
        self.report = self.account('employee', 'Asha Report', self.manager.id)
        self.outsider = self.account('employee', 'Omar Outsider')
        self.other_manager = self.account('manager', 'Other Manager')
        for person in (self.report, self.outsider):
            self.assign(person.id)

    def test_employee_sees_only_their_own_records(self):
        mine = next(c for c in self.report.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertTrue(mine['assignment']['mandatory'])
        self.assertEqual(mine['deadline']['display'], '1 May 2099, 5:00 PM')
        self.assertNotIn('Omar', str(self.report.request('courses')[1]), 'The course list never mentions other employees.')
        self.assertEqual(self.report.request('certificates')[0], 200)
        self.assertEqual(self.report.request('me/assessments')[0], 200)
        # Every staff endpoint the assistant uses refuses an employee, whatever the query asks for.
        for path in ('manage/compliance?size=50', f'manage/compliance?size=50&q=Omar&employee={self.outsider.id}', 'manage/assignments', 'manage/reports?type=enrollments', 'admin/courses'):
            self.assertEqual(self.report.request(path)[0], 403, path)

    def test_manager_sees_only_direct_reports(self):
        data = self.manager.request('manage/compliance?size=50')[1]
        self.assertEqual(data['scope'], 'team')
        self.assertEqual({r['employeeId'] for r in data['table']['rows']}, {self.report.id})
        # Naming someone outside the team, by search or by ID, returns nothing rather than their records.
        self.assertEqual(self.manager.request('manage/compliance?size=50&q=Omar')[1]['table']['rows'], [])
        self.assertEqual(self.manager.request(f'manage/compliance?size=50&employee={self.outsider.id}')[1]['table']['rows'], [])
        overdue_scope = self.manager.request('manage/compliance?size=50&status=overdue')[1]
        self.assertEqual(overdue_scope['scope'], 'team')
        # Another manager has no reports, so sees nobody.
        self.assertEqual(self.other_manager.request('manage/compliance?size=50')[1]['table']['rows'], [])

    def test_hr_and_admin_see_the_organisation(self):
        hr = self.account('hr', 'Helen HR')
        for client in (hr, self.admin):
            data = client.request('manage/compliance?size=50')[1]
            self.assertEqual(data['scope'], 'organisation')
            self.assertTrue({self.report.id, self.outsider.id} <= {r['employeeId'] for r in data['table']['rows']})
            self.assertEqual({r['employee'] for r in client.request('manage/compliance?size=50&q=omar')[1]['table']['rows']}, {'Omar Outsider'})
            self.assertEqual(client.request('manage/assignments')[0], 200)

    def test_trainer_sees_only_their_own_courses_learners(self):
        trainer = self.account('trainer', 'Tara Trainer')
        self.assertEqual(trainer.request('manage/compliance?size=50')[0], 403, 'Trainers do not see Training Compliance.')
        self.assertEqual(trainer.request('admin/courses')[1]['courses'], [], 'A trainer who owns no course manages none.')
        self.assertEqual(trainer.request('manage/reports?type=enrollments')[1]['rows'], [], 'and reports on no learners.')
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE courses SET trainer_id=? WHERE id=?', (trainer.id, COURSE))
        rows = trainer.request('manage/reports?type=enrollments')[1]['rows']
        self.assertTrue(rows and all(r['course'] == next(c['title'] for c in trainer.request('admin/courses')[1]['courses']) for r in rows))
        self.assertEqual([c['id'] for c in trainer.request('admin/courses')[1]['courses']], [COURSE])
