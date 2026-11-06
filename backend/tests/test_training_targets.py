"""Yearly training-hours targets: set by an admin or the employee's manager, shown on the employee dashboard, in admin records and in the Manager View."""
from datetime import date

from test_portal import PortalFixture
import test_role_architecture as roles

COURSE = 'agile-and-scrum'


class TrainingTargetTests(PortalFixture):
    account = roles.RoleArchitectureTests.account

    def complete_first_lesson(self, client):
        self.assertEqual(client.request('learning/enroll', {'courseId': COURSE})[0], 200)
        lesson = client.request('learning?courseId=' + COURSE)[1]['courseLessons'][0]
        self.assertEqual(client.action('lesson', lessonId=lesson['id'])[0], 200)
        return lesson

    def test_admin_sets_a_target_and_the_employee_sees_completed_hours(self):
        employee = self.account('employee', 'Target Learner')
        before = employee.request('me/dashboard')[1]['training']
        self.assertEqual((before['year'], before['targetHours'], before['completedHours'], before['percent']), (date.today().year, None, 0, None))
        saved = self.admin.request('manage/training-targets', {'employeeIds': [employee.id], 'hours': 30})
        self.assertEqual(saved[0], 200, saved[1])
        lesson = self.complete_first_lesson(employee)
        mine = employee.request('me/dashboard')[1]['training']
        hours = round(lesson['durationMinutes'] / 60, 1)
        self.assertEqual((mine['targetHours'], mine['completedHours'], mine['percent']), (30, hours, round(hours / 30 * 100)), 'Completed lessons count toward the year.')
        # The same progress appears in the admin's employee list and the employee's learning records.
        listed = next(u for u in self.admin.request('admin/candidates')[1]['candidates'] if u['id'] == employee.id)
        self.assertEqual(listed['training'], mine)
        self.assertEqual(self.admin.request(f'admin/candidates/{employee.id}/records')[1]['training'], mine)
        # A blank target removes it.
        self.assertEqual(self.admin.request('manage/training-targets', {'employeeIds': [employee.id], 'hours': None})[0], 200)
        self.assertIsNone(employee.request('me/dashboard')[1]['training']['targetHours'])

    def test_manager_sets_targets_only_for_direct_reports(self):
        manager = self.account('manager', 'Target Manager')
        report = self.account('employee', 'Direct Report', manager.id)
        other = self.account('employee', 'Someone Else')
        self.assertEqual(manager.request('manage/training-targets', {'employeeIds': [report.id], 'hours': 40})[0], 200)
        self.assertEqual(manager.request('manage/training-targets', {'employeeIds': [report.id, other.id], 'hours': 40})[0], 403)
        view = manager.request('manage/dashboard')[1]['training']
        self.assertEqual([(r['name'], r['targetHours']) for r in view], [('Direct Report', 40)], 'The Manager View lists only direct reports.')
        self.assertEqual(manager.request(f'admin/candidates/{report.id}/records')[1]['training']['targetHours'], 40)
        self.assertIsNone(other.request('me/dashboard')[1]['training']['targetHours'])

    def test_employees_cannot_set_targets_and_values_are_validated(self):
        employee = self.account('employee', 'No Access')
        self.assertEqual(employee.request('manage/training-targets', {'employeeIds': [employee.id], 'hours': 30})[0], 403)
        for hours in (0, 2001, 2.5, '30'):
            self.assertEqual(self.admin.request('manage/training-targets', {'employeeIds': [employee.id], 'hours': hours})[0], 400, hours)
        self.assertEqual(self.admin.request('manage/training-targets', {'employeeIds': [], 'hours': 30})[0], 400)
        self.assertEqual(self.admin.request('manage/training-targets', {'employeeIds': ['missing'], 'hours': 30})[0], 404)
        # Admin accounts have no target.
        admin_id = next(u['id'] for u in self.admin.request('admin/candidates')[1]['candidates'] if u['role'] == 'admin')
        self.assertEqual(self.admin.request('manage/training-targets', {'employeeIds': [admin_id], 'hours': 30})[0], 404)

    def test_one_save_sets_the_target_for_many_employees(self):
        people = [self.account('employee', f'Bulk {n}') for n in range(3)]
        saved = self.admin.request('manage/training-targets', {'employeeIds': [p.id for p in people], 'hours': 25})
        self.assertEqual(saved[0], 200, saved[1])
        self.assertEqual({t['targetHours'] for t in saved[1]['training'].values()}, {25})
