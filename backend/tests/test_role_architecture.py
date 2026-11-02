"""Role architecture: Admin -> Admin Dashboard + My Learning; Manager -> Manager View + My Learning; Employee -> My Learning."""
import uuid

from test_portal import PortalFixture, Client

COURSE = 'agile-and-scrum'


class RoleArchitectureTests(PortalFixture):
    def account(self, role, name, manager_id=None):
        client = Client(self.base)
        email = f'{uuid.uuid4().hex}@shimentox.com'
        body = {'name': name, 'email': email, 'password': 'Temporary123!', 'role': role, **({'managerId': manager_id} if manager_id else {})}
        created = self.admin.request('admin/candidates', body)
        self.assertEqual(created[0], 200, created[1])
        client.id = created[1]['candidate']['id']
        client.request('auth/login', {'email': email, 'password': 'Temporary123!'})
        client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        return client

    def test_admin_has_my_learning(self):
        self.assertEqual(self.admin.request('learning/enroll', {'courseId': COURSE})[0], 200)
        lesson = self.admin.request('learning?courseId=' + COURSE)[1]['courseLessons'][0]
        self.assertEqual(self.admin.action('lesson', lessonId=lesson['id'])[0], 200)
        listed = next(c for c in self.admin.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertTrue(listed['started'], 'The course appears in the admin\'s My Learning.')
        self.assertEqual(self.admin.request('me/assessments')[0], 200)

    def test_admin_creates_a_manager_whose_view_covers_only_their_team(self):
        manager = self.account('manager', 'Team Manager')
        self.account('employee', 'Report One', manager.id)
        self.account('employee', 'Not My Report')
        view = manager.request('manage/dashboard')
        self.assertEqual(view[0], 200, view[1])
        self.assertEqual(view[1]['kpis']['totalEmployees'], 1, 'The Manager View counts only direct reports.')
        # Managers learn too: My Learning works for them.
        self.assertEqual(manager.request('learning/enroll', {'courseId': COURSE})[0], 200)
        # The Manager View is not the admin workspace.
        self.assertEqual(manager.request('admin/candidates')[0], 403)

    def test_employee_has_my_learning_only(self):
        employee = self.account('employee', 'Plain Employee')
        self.assertEqual(employee.request('learning/enroll', {'courseId': COURSE})[0], 200)
        self.assertEqual(employee.request('manage/dashboard')[0], 403)
        self.assertEqual(employee.request('admin/candidates')[0], 403)
