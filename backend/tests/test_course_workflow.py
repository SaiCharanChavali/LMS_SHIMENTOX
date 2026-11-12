"""Manage Courses workflow end to end: wizard draft, modules, publish, assignment, employee visibility and progress tracking."""
from contextlib import closing

from test_portal import PortalFixture
import test_course_builder  # Helpers only; importing the class by name would run its tests twice.
from database import connect


class CourseWorkflowTests(PortalFixture):
    account = test_course_builder.CourseBuilderTests.account
    upload = test_course_builder.CourseBuilderTests.upload
    course = test_course_builder.CourseBuilderTests.course
    builder = test_course_builder.CourseBuilderTests.builder

    def department(self, name='Finance'):
        return next(d['id'] for d in self.admin.request('manage/org')[1]['departments'] if d['name'] == name)

    def save(self, body, expected=200):
        result = self.admin.request('admin/courses', body)
        self.assertEqual(result[0], expected, result[1])
        return result[1]

    def test_lesson_modules_are_saved_in_order_and_kept_when_not_sent(self):
        identity, body = self.course()
        lessons = [dict(l, moduleTitle=m) for l, m in zip(body['lessons'], ['Module 1: Basics', 'Module 1: Basics', 'Module 2: Practice'])]
        self.save({**body, 'id': identity, 'lessons': lessons})
        saved = self.builder(identity)['lessons']
        self.assertEqual([(l['moduleIndex'], l['moduleTitle']) for l in saved], [(0, 'Module 1: Basics'), (0, 'Module 1: Basics'), (1, 'Module 2: Practice')])
        # A lesson without a module name sits outside any module; the next named module continues the numbering.
        mixed = [dict(saved[0], moduleTitle=''), dict(saved[1], moduleTitle='Prompting'), dict(saved[2], moduleTitle='Prompting')]
        self.save({**body, 'id': identity, 'lessons': mixed})
        self.assertEqual([(l['moduleIndex'], l['moduleTitle']) for l in self.builder(identity)['lessons']], [(None, ''), (0, 'Prompting'), (0, 'Prompting')])
        # Requests that do not send module names (older pages, other tools) keep the stored modules.
        plain = [{k: v for k, v in l.items() if k not in ('moduleTitle', 'moduleIndex')} for l in self.builder(identity)['lessons']]
        self.save({**body, 'id': identity, 'lessons': plain})
        self.assertEqual([l['moduleTitle'] for l in self.builder(identity)['lessons']], ['', 'Prompting', 'Prompting'])
        employee_view = self.account()
        self.save({**body, 'id': identity, 'status': 'published', 'lessons': plain})
        employee_view.request('learning/enroll', {'courseId': identity})
        loaded = employee_view.request('learning?courseId=' + identity)[1]['courseLessons']
        self.assertEqual([l['moduleTitle'] for l in loaded], ['', 'Prompting', 'Prompting'])

    def test_create_publish_assign_and_track_progress(self):
        finance = self.department()
        learner, other = self.account(departmentId=finance), self.account()
        # Step 1 only: a draft with basics and no lessons saves, stays hidden, and cannot be assigned.
        draft = self.save({'title': 'Data Handling Basics', 'category': 'Generative AI & Automation', 'description': 'Handle company data safely.', 'status': 'draft',
                           'format': 'lessons', 'difficulty': 'beginner', 'durationMinutes': 45, 'visibility': 'everyone', 'lessons': [], 'assessment': None})['course']
        identity = draft['id']
        self.assertEqual(draft['status'], 'draft')
        self.assertEqual(self.builder(identity)['lessons'], [])
        self.assertFalse(any(c['id'] == identity for c in learner.request('courses')[1]['courses']))
        refused = self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'department', 'targetId': finance, 'mandatory': False})
        self.assertEqual(refused[:2], (409, {'error': 'Only published courses can be assigned.'}))
        self.save({'id': identity, 'title': 'Data Handling Basics', 'category': 'Generative AI & Automation', 'description': 'Handle company data safely.', 'status': 'published', 'format': 'lessons', 'lessons': []}, expected=400)
        # Steps 2-4: lessons in a module, the assessment, then publish.
        body = {'id': identity, 'title': 'Data Handling Basics', 'category': 'Generative AI & Automation', 'description': 'Handle company data safely.', 'format': 'lessons', 'difficulty': 'beginner',
                'durationMinutes': 45, 'visibility': 'everyone',
                'lessons': [{'title': 'Classify data', 'content': 'Public, internal, confidential.', 'moduleTitle': 'Module 1', 'durationMinutes': 15},
                            {'title': 'Share safely', 'content': 'Use approved tools.', 'moduleTitle': 'Module 1', 'durationMinutes': 15}],
                'assessment': {'passPercent': 50, 'maxAttempts': 2, 'timeLimitMinutes': 10, 'questions': [{'prompt': 'Which label fits payroll data?', 'options': ['Public', 'Confidential'], 'correct': 1}]}}
        self.save({**body, 'status': 'draft'})
        self.assertEqual(self.save({**body, 'status': 'published'})['course']['status'], 'published')
        listed = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == identity)
        self.assertEqual((listed['status'], listed['assignments']), ('published', 0))
        # Course Assignment: a department, mandatory, with an IST deadline.
        assigned = self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'department', 'targetId': finance, 'mandatory': True, 'deadline': '2099-03-01T17:30', 'note': 'Annual'})
        self.assertEqual(assigned[0], 200, assigned[1])
        self.assertEqual([(a['targetType'], a['target'], a['mandatory'], a['deadlineDisplay']) for a in assigned[1]['assignments']], [('department', 'Finance', True, '1 March 2099, 5:30 PM')])
        card = next(c for c in learner.request('courses')[1]['courses'] if c['id'] == identity)
        self.assertTrue(card['assignment']['mandatory'])
        self.assertEqual(card['deadline']['display'], '1 March 2099, 5:30 PM')
        self.assertIsNone(next(c for c in other.request('courses')[1]['courses'] if c['id'] == identity).get('assignment'), 'Employees outside the department are not assigned.')
        # Assigning the same course to the same target again updates it: still one record.
        again = self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'department', 'targetId': finance, 'mandatory': True, 'deadline': '2099-04-01T09:00'})
        self.assertEqual(again[0], 200, again[1])
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM course_assignments WHERE course_id=?', (identity,)).fetchone()[0], 1)
        self.assertEqual(next(c for c in learner.request('courses')[1]['courses'] if c['id'] == identity)['deadline']['display'], '1 April 2099, 9:00 AM')
        # Employee Progress Tracking: the employee's lesson shows up on the assignment view.
        before = {e['employeeId']: e for e in self.admin.request(f'manage/deadlines?courseId={identity}')[1]['employees']}
        self.assertEqual((before[learner.id]['status'], before[learner.id]['progress'], before[learner.id]['source']), ('not_started', 0, 'department'))
        learner.request('learning/enroll', {'courseId': identity})
        lessons = learner.request('learning?courseId=' + identity)[1]['courseLessons']
        self.assertEqual(learner.action('lesson', lessonId=lessons[0]['id'])[0], 200)
        after = {e['employeeId']: e for e in self.admin.request(f'manage/deadlines?courseId={identity}')[1]['employees']}
        self.assertEqual(after[learner.id]['status'], 'in_progress')
        self.assertGreater(after[learner.id]['progress'], 0)
        self.assertNotIn(other.id, after)
        # Reminders for the course are listed per course for HR.
        self.assertEqual(self.admin.request(f'manage/reminders/history?courseId={identity}')[0], 200)
        # Archive from the catalogue keeps the learner's run and blocks new assignments.
        self.assertEqual(self.admin.request(f'admin/courses/{identity}/archive', {})[0], 200)
        self.assertEqual(self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'employee', 'targetId': other.id, 'mandatory': False})[0], 409)
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM course_runs WHERE course_id=? AND candidate_id=?', (identity, learner.id)).fetchone()[0], 1)

    def test_employees_cannot_manage_assign_or_see_reminders(self):
        identity, body = self.course()
        self.save({**body, 'id': identity, 'status': 'published'})
        employee = self.account()
        self.assertEqual(employee.request('admin/courses', {**body, 'id': identity, 'title': 'Changed'})[0], 403)
        self.assertEqual(employee.request('manage/assignments', {'courseId': identity, 'targetType': 'employee', 'targetId': employee.id})[0], 403)
        self.assertEqual(employee.request(f'manage/deadlines?courseId={identity}')[0], 403)
        self.assertEqual(employee.request('manage/reminders/settings')[0], 403)
        self.assertEqual(employee.request(f'admin/courses/{identity}/archive', {})[0], 403)
