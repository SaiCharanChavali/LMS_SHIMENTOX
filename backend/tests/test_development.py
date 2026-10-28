"""Employee L&D features over real HTTP: roles, assignments, paths, skills, assessments, certificates, analytics."""
from contextlib import closing
import copy
import json
import os
import urllib.error
import urllib.request
import uuid

from test_portal import PortalFixture, Client
from database import connect, CURRICULUM
from server import PortalServer, PortalHandler


class DevelopmentTests(PortalFixture):
    def test_notification_events_announcements_and_privacy(self):
        manager = self.account('manager', 'Notification Manager')
        learner = self.account(name='Notification Learner', managerId=manager.id)
        outsider = self.account('manager', 'Other Manager')
        self.assertEqual(learner.request('manage/announcements', {'title': 'Forbidden', 'body': 'No permission'})[0], 403)
        self.assertEqual(self.admin.request('manage/announcements', {'title': 'Learning week', 'body': 'Explore something new.'})[0], 200)
        course = self.course('Notification course')
        learner.request('learning/enroll', {'courseId': course})
        self.assertEqual(self.admin.request(f'manage/courses/{course}/resources', {'title': 'Practice guide', 'kind': 'link', 'url': 'https://example.com/guide'})[0], 200)
        self.prepare(learner, 0)
        first = learner.request('me/notifications')[1]
        titles = [n['title'] for n in first['notifications']]
        self.assertIn('Learning week', titles)
        self.assertIn('Password changed successfully', titles)
        self.assertIn('New learning material', titles)
        self.assertIn('Module 1 exam unlocked', titles)
        self.assertIn('New course available: Notification course', titles)
        self.assertEqual(first, learner.request('me/notifications')[1])
        for i in range(3):
            attempt = learner.action('exam-start', setIndex=0)[1]['attempt']
            self.assertEqual(learner.action('exam-finish', attemptId=attempt['id'], terminate=True)[0], 200)
        titles = [n['title'] for n in learner.request('me/notifications')[1]['notifications']]
        self.assertIn('0 exam attempts remaining', titles)
        team_titles = [n['title'] for n in manager.request('me/notifications')[1]['notifications']]
        other_titles = [n['title'] for n in outsider.request('me/notifications')[1]['notifications']]
        self.assertIn('First sign-in: Notification Learner', team_titles)
        self.assertIn('Exam attempts exhausted: Notification Learner', team_titles)
        self.assertNotIn('Exam attempts exhausted: Notification Learner', other_titles)
        note = first['notifications'][0]['id']
        outsider.request('me/notifications/read', {'ids': [note]})
        self.assertIsNone(next(n for n in learner.request('me/notifications')[1]['notifications'] if n['id']==note)['readAt'])
        self.assertEqual(learner.request('me/notifications/read', {'all': True})[1]['unread'], 0)

    def account(self, role='employee', name='Team Member', **org):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!', 'role': role, **org})
        self.assertEqual(result[0], 200, result[1])
        client.id = result[1]['candidate']['id']
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})[0], 200)
        return client

    def org(self):
        return self.admin.request('manage/org')[1]

    def department(self, name):
        return next(d['id'] for d in self.org()['departments'] if d['name'] == name)

    def course(self, title, **extra):
        source = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == 'python-programming')
        saved = self.admin.request('admin/courses', {'title': title, 'description': f'{title} course.', 'category': 'Technical Skills', 'status': 'published', 'content': copy.deepcopy(source['content']), **extra})
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['course']['id']

    def complete(self, client, course_id):
        client.request('learning/enroll', {'courseId': course_id})
        for s in range(3):
            self.prepare(client, s)
            attempt = client.action('exam-start', setIndex=s)[1]['attempt']
            result = client.action('exam-finish', attemptId=attempt['id'], answers=[q[2] for q in CURRICULUM[s]['exam']])
            self.assertEqual(result[1]['attempt']['status'], 'passed', result[1])
        return result[1]['learning']

    def assessment(self, **fields):
        body = {'title': 'Check', 'kind': 'knowledge', 'passPercent': 60, 'maxAttempts': 2, 'questionCount': 3, 'timeLimitMinutes': 10, 'status': 'published',
                'questions': [[f'Question {i}?', ['Right', 'Wrong'], 0, 'Right is right.'] for i in range(5)]}
        body.update(fields)
        saved = self.admin.request('manage/assessments', body)
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['assessment']['id']

    def take(self, client, identity, correct=True):
        start = client.request(f'me/assessments/{identity}/start', {})
        self.assertEqual(start[0], 200, start[1])
        attempt = start[1]['attempt']
        self.assertTrue(all('correct' not in json.dumps(q) for q in attempt['questions']))
        # Answer positions are shuffled per attempt, so choose by option text.
        answers = [q['options'].index('Right' if correct else 'Wrong') for q in attempt['questions']]
        return client.request(f'me/assessments/{identity}/submit', {'attemptId': attempt['id'], 'answers': answers})

    def test_second_server_cannot_share_the_port(self):
        # A stale server silently sharing the port made browsers reach old code; a duplicate start must fail.
        with self.assertRaises(OSError):
            PortalServer(('127.0.0.1', self.server.server_port), PortalHandler, self.db_path).server_close()

    def test_session_reports_api_version_and_unknown_endpoints_are_named(self):
        self.assertEqual(Client(self.base).request('session')[1]['apiVersion'], 9)
        employee = self.account(name='Route Checker')
        for route, expected in (('manage/unknown', 'GET /api/manage/unknown'), ('me/unknown', 'GET /api/me/unknown'), ('nothing-here', 'GET /api/nothing-here')):
            status, payload, _ = (self.admin if route.startswith('manage') else employee).request(route)
            self.assertEqual(status, 404, route)
            self.assertIn(expected, payload['error'])
        self.assertEqual(self.admin.request('manage/paths')[0], 200)

    def test_role_permissions_are_enforced_on_the_server(self):
        employee = self.account()
        for route in ('manage/org', 'manage/dashboard', 'manage/reports', 'manage/assessments', 'admin/candidates', 'admin/courses'):
            self.assertEqual(employee.request(route)[0], 403, route)
        self.assertEqual(employee.request('manage/assignments', {'courseId': 'python-programming', 'targetType': 'employee', 'targetId': employee.id})[0], 403)
        hr = self.account('hr', 'HR Partner')
        self.assertEqual(hr.request('admin/candidates')[0], 200)
        self.assertEqual(hr.request('admin/candidates', {'name': 'Escalate', 'email': f'{uuid.uuid4().hex}@x.com', 'password': 'Temporary123!', 'role': 'admin'})[0], 403)
        admin_id = self.admin.request('session')[1]['user']['id']
        self.assertEqual(hr.request(f'admin/candidates/{admin_id}/reset-password', {'password': 'Takeover123!'})[0], 403)
        self.assertEqual(hr.request('admin/audit')[0], 403)
        trainer = self.account('trainer', 'Course Trainer')
        self.assertEqual(trainer.request('admin/courses')[1]['courses'], [])
        python = {'id': 'python-programming', 'title': 'Hijack', 'description': 'x', 'category': 'Development', 'status': 'archived'}
        self.assertEqual(trainer.request('admin/courses', python)[0], 403)
        self.assertEqual(trainer.request('manage/reports?type=employees')[0], 403)
        self.assertEqual(trainer.request('manage/reports?type=enrollments')[0], 200)
        self.assertEqual(employee.request('admin/candidates', {'name': 'x', 'email': 'y@z.com', 'password': 'Temporary123!'})[0], 403)

    def test_manager_scope_assignments_and_reports(self):
        manager = self.account('manager', 'Line Manager')
        report = self.account(name='Direct Report', managerId=manager.id)
        other = self.account(name='Other Employee')
        self.assertEqual({p['id'] for p in manager.request('manage/people')[1]['people']}, {report.id})
        recommend = {'courseId': 'python-programming', 'targetType': 'employee', 'targetId': report.id, 'mandatory': False}
        self.assertEqual(manager.request('manage/assignments', recommend)[0], 200)
        self.assertEqual(manager.request('manage/assignments', {**recommend, 'targetId': other.id})[0], 403)
        self.assertEqual(manager.request('manage/assignments', {**recommend, 'mandatory': True, 'dueDate': '2099-01-01'})[0], 403)
        self.assertEqual(manager.request(f'admin/candidates/{report.id}/records')[0], 200)
        self.assertEqual(manager.request(f'admin/candidates/{other.id}/records')[0], 403)
        rows = manager.request('manage/reports?type=employees&export=1')[1]['rows']
        self.assertEqual([r['employee'] for r in rows], ['Direct Report'])
        self.assertEqual(manager.request('manage/dashboard')[1]['kpis']['totalEmployees'], 1)
        notes = report.request('me/notifications')[1]['notifications']
        self.assertTrue(any('recommended by your manager' in n['title'] for n in notes))

    def test_mandatory_assignment_deadlines_dashboard_and_notification_dedupe(self):
        engineering = self.department('Engineering')
        learner = self.account(name='Deadline Learner', departmentId=engineering)
        missing_due = self.admin.request('manage/assignments', {'courseId': 'python-programming', 'targetType': 'department', 'targetId': engineering, 'mandatory': True})
        self.assertEqual(missing_due[0], 400)
        self.assertEqual(self.admin.request('manage/assignments', {'courseId': 'python-programming', 'targetType': 'department', 'targetId': engineering, 'mandatory': True, 'dueDate': '2020-01-01'})[0], 400)
        created = self.admin.request('manage/assignments', {'courseId': 'python-programming', 'targetType': 'department', 'targetId': engineering, 'mandatory': True, 'dueDate': '2099-12-31'})
        self.assertEqual(created[0], 200, created[1])
        dashboard = learner.request('me/dashboard')[1]
        self.assertEqual([c['id'] for c in dashboard['assigned']], ['python-programming'])
        self.assertTrue(dashboard['assigned'][0]['assignment']['mandatory'])
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE course_assignments SET due_date='2020-01-01' WHERE target_id=?", (engineering,))
        first = learner.request('me/notifications')[1]
        second = learner.request('me/notifications')[1]
        self.assertEqual(len(first['notifications']), len(second['notifications']))
        self.assertTrue(any(n['title'].startswith('Overdue') for n in second['notifications']))
        self.assertEqual(learner.request('me/dashboard')[1]['assigned'][0]['status'], 'overdue')
        self.assertEqual(learner.request('me/notifications/read', {'all': True})[1]['unread'], 0)
        compliance = self.admin.request('manage/reports?type=compliance&export=1')[1]
        self.assertTrue(any(r['employee'] == 'Deadline Learner' and r['status'] == 'Overdue' for r in compliance['rows']))

    def test_dashboard_matches_stored_records(self):
        learner = self.account(name='Dashboard Learner')
        self.complete(learner, 'python-programming')
        data = self.admin.request('manage/dashboard')[1]
        with closing(connect(self.db_path)) as db:
            employees = db.execute("SELECT COUNT(*) FROM candidates WHERE role<>'admin' AND is_active=1").fetchone()[0]
            published = db.execute("SELECT COUNT(*) FROM courses WHERE status='published'").fetchone()[0]
            certificates = db.execute("SELECT COUNT(*) FROM certificates x JOIN course_runs r ON r.id=x.run_id JOIN candidates c ON c.id=r.candidate_id WHERE c.role<>'admin' AND c.is_active=1").fetchone()[0]
            seconds = db.execute("SELECT SUM(v.watched_seconds) FROM video_progress v JOIN course_runs r ON r.id=v.run_id JOIN candidates c ON c.id=r.candidate_id WHERE c.role<>'admin' AND c.is_active=1").fetchone()[0]
        self.assertEqual(data['kpis']['totalEmployees'], employees)
        self.assertEqual(data['kpis']['publishedCourses'], published)
        self.assertEqual(data['kpis']['certificatesEarned'], certificates)
        self.assertEqual(data['kpis']['trainingHours'], round(seconds / 3600, 1))
        self.assertGreaterEqual(data['kpis']['activeLearners'], 1)
        self.assertTrue(any('Dashboard Learner completed' in e['text'] for e in data['recent']))
        self.assertTrue(data['departments'])
        csv_rows = self.admin.request('manage/reports?type=certificates&export=1')[1]['rows']
        self.assertEqual(len(csv_rows), certificates)

    def test_learning_path_progress_and_sequence(self):
        second = self.course('Path Course Two')
        draft = self.admin.request('manage/paths', {'title': 'Generative AI Path', 'status': 'draft', 'sequential': True, 'courseIds': ['python-programming', second]})
        self.assertEqual(draft[0], 200, draft[1])
        path = next(p for p in draft[1]['paths'] if p['title'] == 'Generative AI Path')
        learner = self.account(name='Path Learner')
        self.assertEqual(self.admin.request(f'manage/paths/{path["id"]}/assign', {'targetType': 'employee', 'targetId': learner.id})[0], 409)
        self.admin.request('manage/paths', {'id': path['id'], 'title': 'Generative AI Path', 'status': 'published', 'sequential': True, 'courseIds': ['python-programming', second]})
        self.assertEqual(self.admin.request(f'manage/paths/{path["id"]}/assign', {'targetType': 'employee', 'targetId': learner.id})[0], 200)
        mine = learner.request('me/paths')[1]['paths'][0]
        self.assertEqual([c['status'] for c in mine['courses']], ['not_started', 'locked'])
        self.assertEqual(mine['nextCourseId'], 'python-programming')
        self.complete(learner, 'python-programming')
        mine = learner.request('me/paths')[1]['paths'][0]
        self.assertEqual((mine['completed'], mine['progress'], mine['nextCourseId']), (1, 50, second))
        self.assertEqual(mine['milestones'][0]['title'], 'PYTHON PROGRAMMING')
        progress = self.admin.request(f'manage/paths/{path["id"]}/progress')[1]['employees']
        self.assertEqual(progress[0]['progress'], 50)
        recs = learner.request('me/dashboard')[1]['recommendations']
        self.assertTrue(any(r['id'] == second and any('learning path' in reason for reason in r['reasons']) for r in recs))

    def test_skills_gap_evidence_and_recommendations(self):
        role = self.admin.request('manage/job-roles', {'name': f'Analyst {uuid.uuid4().hex[:6]}'})[1]['jobRoles'][-1]
        name = f'SQL {uuid.uuid4().hex[:6]}'
        skill_id = next(s['id'] for s in self.admin.request('manage/skills', {'name': name, 'category': 'Data'})[1]['skills'] if s['name'] == name)
        self.assertEqual(self.admin.request('manage/competencies', {'jobRoleId': role['id'], 'skillId': skill_id, 'targetLevel': 2})[0], 200)
        course = self.course('SQL Foundations', skills=[{'skillId': skill_id, 'level': 2}])
        learner = self.account(name='Skill Learner', jobRoleId=role['id'])
        skills = learner.request('me/skills')[1]
        row = next(s for s in skills['skills'] if s['id'] == skill_id)
        self.assertEqual((row['current'], row['target'], row['gap']), (0, 2, 2))
        self.assertTrue(any(r['id'] == course and 'gap' in ' '.join(r['reasons']) for r in skills['recommendations']))
        self.complete(learner, course)
        row = next(s for s in learner.request('me/skills')[1]['skills'] if s['id'] == skill_id)
        self.assertEqual(row['current'], 0, 'Course completion alone must not raise a skill level.')
        check = self.assessment(title='SQL level 2', kind='skill', skillId=skill_id, skillLevel=2)
        self.assertEqual(self.take(learner, check, correct=False)[1]['result']['status'], 'failed')
        self.assertEqual(self.take(learner, check)[1]['result']['status'], 'passed')
        row = next(s for s in learner.request('me/skills')[1]['skills'] if s['id'] == skill_id)
        self.assertEqual((row['current'], row['gap'], row['evidence'][0]['source']), (2, 0, 'assessment'))
        gaps = self.admin.request('manage/reports?type=skills&export=1')[1]['rows']
        self.assertTrue(any(r['employee'] == 'Skill Learner' and r['status'] == 'Meets target' for r in gaps))

    def test_question_bank_randomisation_and_retake_policy(self):
        identity = self.assessment(title='Policy check')
        learner = self.account(name='Assessment Learner')
        listed = next(a for a in learner.request('me/assessments')[1]['assessments'] if a['id'] == identity)
        self.assertEqual((listed['questionCount'], listed['attemptsLeft']), (3, 2))
        result = self.take(learner, identity, correct=False)[1]['result']
        self.assertEqual((result['status'], result['total'], result['percent']), ('failed', 3, 0))
        self.assertEqual(self.take(learner, identity)[1]['result']['percent'], 100)
        self.assertEqual(learner.request(f'me/assessments/{identity}/start', {})[0], 409)
        locked = self.admin.request('manage/assessments', {'id': identity, 'title': 'Policy check', 'kind': 'knowledge', 'passPercent': 60, 'maxAttempts': 2, 'questionCount': 3, 'timeLimitMinutes': 10,
                                                            'status': 'published', 'questions': [['Changed?', ['A', 'B'], 0, '']] * 3})
        self.assertEqual(locked[0], 409)
        history = self.admin.request(f'manage/assessments/{identity}/attempts')[1]
        self.assertEqual(history['total'], 2)

    def test_post_assessment_and_configured_pass_mark_gate_certificates(self):
        strict = self.course('Strict Course', passPercent=100, maxAttempts=1)
        learner = self.account(name='Strict Learner')
        learner.request('learning/enroll', {'courseId': strict})
        self.prepare(learner, 0)
        attempt = learner.action('exam-start', setIndex=0)[1]['attempt']
        answers = [q[2] for q in CURRICULUM[0]['exam']]
        answers[0] = (answers[0] + 1) % 3
        self.assertEqual(learner.action('exam-finish', attemptId=attempt['id'], answers=answers)[1]['attempt']['status'], 'failed')
        self.assertEqual(learner.action('exam-start', setIndex=0)[0], 409)
        gated = self.course('Gated Course')
        post = self.assessment(title='Gated post-check', kind='post', courseId=gated, maxAttempts=3)
        source = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == gated)
        self.assertEqual(self.admin.request('admin/courses', {'id': gated, 'title': 'Gated Course', 'description': 'x', 'category': 'Technical Skills', 'status': 'published', 'content': source['content'], 'postAssessmentId': post})[0], 200)
        learner = self.account(name='Gated Learner')
        learning = self.complete(learner, gated)
        self.assertFalse(any(c['courseId'] == gated for c in learning['certificates']))
        pending = learner.request('me/dashboard')[1]['pendingAssessments']
        self.assertTrue(any(p['id'] == post for p in pending))
        self.assertEqual(self.take(learner, post)[1]['result']['status'], 'passed')
        certificates = [c for c in learner.request('certificates')[1]['certificates'] if c['courseId'] == gated]
        self.assertEqual(len(certificates), 1)
        self.take(learner, post)
        self.assertEqual(len([c for c in learner.request('certificates')[1]['certificates'] if c['courseId'] == gated]), 1)
        self.assertTrue(any(n['kind'] == 'certificate' for n in learner.request('me/notifications')[1]['notifications']))

    def test_training_sessions_capacity_registration_and_attendance(self):
        saved = self.admin.request('manage/sessions', {'title': 'Prompt Engineering Workshop', 'kind': 'workshop', 'startsAt': '2099-05-01T10:00', 'endsAt': '2099-05-01T12:00', 'capacity': 1, 'location': 'Room 4'})
        self.assertEqual(saved[0], 200, saved[1])
        session = next(s for s in saved[1]['sessions'] if s['title'] == 'Prompt Engineering Workshop')
        self.assertEqual(self.admin.request('manage/sessions', {'title': 'Bad', 'startsAt': '2099-05-01T10:00', 'endsAt': '2099-05-01T09:00', 'capacity': 3})[0], 400)
        first, second = self.account(name='Seat One'), self.account(name='Seat Two')
        mine = first.request(f'me/sessions/{session["id"]}/register', {})[1]['sessions']
        self.assertEqual(next(s for s in mine if s['id'] == session['id'])['myStatus'], 'registered')
        self.assertEqual(second.request(f'me/sessions/{session["id"]}/register', {})[0], 409)
        self.assertEqual(self.admin.request(f'manage/sessions/{session["id"]}/attendance', {'employeeId': first.id, 'attended': True})[0], 409)
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE training_sessions SET starts_at='2020-05-01T10:00',ends_at='2020-05-01T12:00' WHERE id=?", (session['id'],))
        self.assertEqual(self.admin.request(f'manage/sessions/{session["id"]}/attendance', {'employeeId': first.id, 'attended': True})[0], 200)
        rows = self.admin.request('manage/reports?type=employees&export=1')[1]['rows']
        self.assertEqual(next(r for r in rows if r['employee'] == 'Seat One')['hours'], 2.0)

    def upload(self, client, name, body):
        req = urllib.request.Request(self.base + '/api/manage/materials', body, {'Content-Type': 'application/octet-stream', 'X-File-Name': name, 'X-Portal-Request': '1', 'X-CSRF-Token': client.csrf, 'Origin': self.base})
        try:
            response = client.opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        payload = json.loads(response.read())
        response.close()
        return response.status, payload

    def fetch(self, client, url):
        try:
            with client.opener.open(self.base + '/' + url, timeout=15) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, b''

    def test_materials_are_private_until_attached_to_a_published_course(self):
        employee = self.account(name='Material Reader')
        self.assertEqual(self.upload(employee, 'notes.pdf', b'%PDF-1.4 test')[0], 403)
        self.assertEqual(self.upload(self.admin, 'script.exe', b'MZ')[0], 415)
        status, payload = self.upload(self.admin, 'handbook.pdf', b'%PDF-1.4 handbook')
        self.assertEqual(status, 200, payload)
        url = payload['material']['url']
        self.assertEqual(self.fetch(employee, url)[0], 403)
        self.assertEqual(self.admin.request('manage/courses/python-programming/resources', {'title': 'Handbook', 'kind': 'document', 'url': url})[0], 200)
        self.assertEqual(self.fetch(employee, url), (200, b'%PDF-1.4 handbook'))
        self.assertEqual(self.fetch(Client(self.base), url)[0], 401)
        extras = employee.request('learning?courseId=python-programming')[1]
        self.assertTrue(any(r['url'] == url for r in extras['resources']))
        self.assertEqual(self.admin.request('manage/courses/python-programming/resources', {'title': 'Bad', 'kind': 'link', 'url': 'javascript:alert(1)'})[0], 400)

    def test_goals_history_records_and_assistant_without_credentials(self):
        learner = self.account(name='Goal Setter')
        saved = learner.request('me/goals', {'title': 'Lead a team retro', 'targetDate': '2099-01-01'})
        self.assertEqual(saved[0], 200, saved[1])
        goal = saved[1]['goals'][0]
        self.assertEqual(learner.request('me/goals', {'id': goal['id'], 'title': 'x'})[0], 400)
        other = self.account(name='Goal Intruder')
        self.assertEqual(other.request('me/goals', {'id': goal['id'], 'title': 'Taken over'})[0], 404)
        self.assertEqual(learner.request('me/records', {'title': 'External workshop', 'completedOn': '2099-01-01'})[0], 400)
        history = learner.request('me/records', {'title': 'External workshop', 'provider': 'Conference', 'completedOn': '2026-01-15', 'hours': 3})[1]
        self.assertEqual(history['records'][0]['title'], 'External workshop')
        self.assertTrue(any('External workshop' in item['text'] for item in history['items']))
        os.environ.pop('LMS_AI_ENABLED', None)
        self.assertFalse(learner.request('me/assistant')[1]['enabled'])
        self.assertEqual(learner.request('me/assistant', {'courseId': 'python-programming', 'mode': 'summarize'})[0], 503)


if __name__ == '__main__':
    import unittest
    unittest.main()
