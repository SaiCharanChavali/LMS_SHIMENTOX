"""Lesson-based courses built in Manage Courses: drafts, lessons, materials, assessments, publishing, learner progress."""
from contextlib import closing
import json
import urllib.request
import uuid

from test_portal import PortalFixture, Client
from database import connect

QUESTIONS = [
    {'prompt': 'What does a prompt template help with?', 'options': ['Consistent instructions', 'Faster GPUs', 'Smaller models'], 'correct': 0, 'explanation': 'Templates keep instructions consistent.'},
    {'prompt': 'What does this code print?', 'code': 'print(len("token"))', 'options': ['4', '5', '6'], 'correct': 1, 'explanation': 'The string has five characters.'},
]


class CourseBuilderTests(PortalFixture):
    def account(self, name='Builder Learner', **org):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!', 'role': 'employee', **org})
        self.assertEqual(result[0], 200, result[1])
        client.id = result[1]['candidate']['id']
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        return client

    def upload(self, name, body):
        req = urllib.request.Request(self.base + '/api/manage/materials', body, {'Content-Type': 'application/octet-stream', 'X-File-Name': name, 'X-Portal-Request': '1', 'X-CSRF-Token': self.admin.csrf, 'Origin': self.base})
        with self.admin.opener.open(req, timeout=15) as response:
            return json.loads(response.read())['material']

    def course(self, **overrides):
        material = self.upload('prompting-guide.pdf', b'%PDF-1.4 prompting guide')
        body = {'title': f'GenAI Foundations {uuid.uuid4().hex[:5]}', 'category': 'Generative AI & Automation', 'description': 'Prompting and responsible use of generative AI.',
                'status': 'draft', 'format': 'lessons', 'difficulty': 'beginner', 'durationMinutes': 120,
                'lessons': [
                    {'title': 'What is generative AI?', 'description': 'Core ideas.', 'videoUrl': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'durationMinutes': 20,
                     'resources': [{'title': 'Microsoft Generative AI for Beginners', 'url': 'https://github.com/microsoft/generative-ai-for-beginners'}]},
                    {'title': 'Prompt engineering', 'content': 'Be specific, give context, and show an example of the output you want.', 'documentUrl': material['url'], 'documentName': material['name'], 'durationMinutes': 30},
                    {'title': 'Practice: write a prompt', 'content': 'Draft a prompt for summarising a policy.', 'exercise': 'Write a prompt that summarises the leave policy in five bullet points.', 'durationMinutes': 25},
                ],
                'assessment': {'passPercent': 50, 'maxAttempts': 3, 'timeLimitMinutes': 10, 'questions': QUESTIONS}}
        body.update(overrides)
        saved = self.admin.request('admin/courses', body)
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['course']['id'], body

    def builder(self, identity):
        result = self.admin.request(f'manage/courses/{identity}/builder')
        self.assertEqual(result[0], 200, result[1])
        return result[1]

    def test_draft_saves_and_reopens_with_lessons_materials_and_assessment(self):
        identity, body = self.course()
        data = self.builder(identity)
        self.assertEqual((data['course']['format'], data['course']['status']), ('lessons', 'draft'))
        self.assertEqual([l['title'] for l in data['lessons']], [l['title'] for l in body['lessons']])
        self.assertEqual(data['lessons'][0]['videoUrl'], 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')
        self.assertEqual(data['lessons'][0]['resources'][0]['url'], 'https://github.com/microsoft/generative-ai-for-beginners')
        self.assertTrue(data['lessons'][1]['documentUrl'].startswith('api/materials/'))
        self.assertEqual(data['lessons'][2]['exercise'], body['lessons'][2]['exercise'])
        self.assertEqual(data['assessment']['kind'], 'post')
        self.assertEqual(data['assessment']['passPercent'], 50)
        self.assertEqual(data['assessment']['questions'][1], ['What does this code print?', ['4', '5', '6'], 1, 'The string has five characters.', 'print(len("token"))'])
        self.assertEqual(data['course']['postAssessmentId'], data['assessment']['id'])
        employee = self.account()
        self.assertFalse(any(c['id'] == identity for c in employee.request('courses')[1]['courses']), 'Drafts must stay hidden from employees.')
        self.assertEqual(employee.request('learning/enroll', {'courseId': identity})[0], 404)

    def test_draft_edits_reorder_delete_and_keep_lesson_ids(self):
        identity, body = self.course()
        lessons = self.builder(identity)['lessons']
        reordered = [dict(lessons[2], title='Practice: refine a prompt'), lessons[0]]
        saved = self.admin.request('admin/courses', {**body, 'id': identity, 'lessons': reordered})
        self.assertEqual(saved[0], 200, saved[1])
        again = self.builder(identity)['lessons']
        self.assertEqual([l['title'] for l in again], ['Practice: refine a prompt', 'What is generative AI?'])
        self.assertEqual([l['id'] for l in again], [lessons[2]['id'], lessons[0]['id']])
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM course_lessons WHERE course_id=?', (identity,)).fetchone()[0], 2)

    def test_lesson_validation_and_video_rules(self):
        identity, body = self.course()
        bad = lambda lesson: self.admin.request('admin/courses', {**body, 'id': identity, 'lessons': [lesson]})
        self.assertEqual(bad({'title': 'x'})[0], 400)
        self.assertEqual(bad({'title': 'Unsafe link', 'resources': [{'title': 'Bad', 'url': 'javascript:alert(1)'}]})[0], 400)
        self.assertEqual(bad({'title': 'Web page as video', 'videoUrl': 'https://example.com/article'})[0], 400)
        self.assertEqual(bad({'title': 'Fake upload', 'documentUrl': 'api/materials/00000000-0000-0000-0000-000000000000'})[0], 400)
        vimeo = bad({'title': 'Vimeo lesson', 'videoUrl': 'https://vimeo.com/123456789'})
        self.assertEqual(vimeo[0], 200, vimeo[1])
        self.assertEqual(self.builder(identity)['lessons'][0]['videoUrl'], 'https://player.vimeo.com/video/123456789')

    def test_publish_requires_valid_content(self):
        identity, body = self.course(lessons=[{'title': 'Empty lesson'}], assessment=None)
        self.assertEqual(self.builder(identity)['assessment'], None)
        result = self.admin.request('admin/courses', {**body, 'id': identity, 'status': 'published'})
        self.assertEqual(result[0], 400)
        self.assertIn('needs a video, document, resource link, or learning content', result[1]['error'])
        self.assertEqual(self.builder(identity)['course']['status'], 'draft', 'A failed publish must not change the saved draft.')
        empty = self.admin.request('admin/courses', {**body, 'id': identity, 'status': 'draft', 'assessment': {'questions': []}})
        self.assertEqual(empty[0], 400)

    def test_published_course_learning_flow_progress_and_single_certificate(self):
        identity, body = self.course()
        self.assertEqual(self.admin.request('admin/courses', {**body, 'id': identity, 'status': 'published'})[0], 200)
        employee = self.account()
        listed = next(c for c in employee.request('courses')[1]['courses'] if c['id'] == identity)
        self.assertEqual((listed['format'], listed['lessonCount'], listed['progress']), ('lessons', 3, 0))
        self.assertEqual(employee.request('learning/enroll', {'courseId': identity})[0], 200)
        loaded = employee.request('learning?courseId=' + identity)[1]
        self.assertEqual([l['title'] for l in loaded['courseLessons']], [l['title'] for l in body['lessons']])
        self.assertNotIn('correct', json.dumps(loaded['courseLessons']))
        lessons = loaded['courseLessons']
        self.assertEqual(employee.action('video', videoIndex=0, watched=1, complete=False)[0], 409)
        first = employee.action('lesson', lessonId=lessons[0]['id'])
        self.assertTrue(first[1]['learning']['run']['lessons'][lessons[0]['id']]['completed'])
        self.assertEqual(employee.action('lesson', lessonId=lessons[2]['id'])[0], 400, 'A practical exercise needs a written response.')
        employee.action('lesson', lessonId=lessons[1]['id'])
        done = employee.action('lesson', lessonId=lessons[2]['id'], response='1. Eligibility 2. Accrual 3. Requests 4. Approval 5. Carry-over')
        self.assertEqual(done[0], 200, done[1])
        self.assertFalse(any(c['courseId'] == identity for c in done[1]['learning']['certificates']), 'The required assessment must be passed first.')
        listed = next(c for c in employee.request('courses')[1]['courses'] if c['id'] == identity)
        self.assertEqual(listed['progress'], 100)
        pending = employee.request('me/dashboard')[1]['pendingAssessments']
        assessment = next(p for p in pending if p['kind'] == 'post')
        start = employee.request(f'me/assessments/{assessment["id"]}/start', {})[1]['attempt']
        self.assertEqual(len(start['questions']), 2)
        self.assertNotIn('correct', json.dumps(start['questions']))
        code = next(q for q in start['questions'] if q['prompt'] == 'What does this code print?')
        # Answer positions are shuffled per attempt, so choose by option text.
        answers = [q['options'].index({'What does a prompt template help with?': 'Consistent instructions', 'What does this code print?': '5'}[q['prompt']]) for q in start['questions']]
        result = employee.request(f'me/assessments/{assessment["id"]}/submit', {'attemptId': start['id'], 'answers': answers})[1]['result']
        self.assertEqual(result['status'], 'passed')
        certificates = [c for c in employee.request('certificates')[1]['certificates'] if c['courseId'] == identity]
        self.assertEqual(len(certificates), 1)
        employee.action('lesson', lessonId=lessons[0]['id'])
        self.assertEqual(len([c for c in employee.request('certificates')[1]['certificates'] if c['courseId'] == identity]), 1)
        removal = self.admin.request('admin/courses', {**body, 'id': identity, 'status': 'published', 'lessons': self.builder(identity)['lessons'][1:]})
        self.assertEqual(removal[0], 409, 'Lessons with employee progress cannot be deleted.')
        report = self.admin.request('manage/reports?type=enrollments&export=1&course=' + identity)[1]['rows']
        self.assertEqual(report[0]['status'], 'Completed')

    def test_department_only_visibility(self):
        org = self.admin.request('manage/org')[1]
        engineering = next(d['id'] for d in org['departments'] if d['name'] == 'Engineering')
        sales = next(d['id'] for d in org['departments'] if d['name'] == 'Sales')
        self.assertEqual(self.admin.request('admin/courses', {'title': 'No department', 'category': 'Technical Skills', 'description': 'x', 'format': 'lessons', 'visibility': 'department', 'lessons': []})[0], 400)
        identity, body = self.course(visibility='department', departmentId=engineering, status='published')
        engineer, seller = self.account('Engineer', departmentId=engineering), self.account('Seller', departmentId=sales)
        self.assertTrue(any(c['id'] == identity for c in engineer.request('courses')[1]['courses']))
        self.assertFalse(any(c['id'] == identity for c in seller.request('courses')[1]['courses']))
        self.assertEqual(seller.request('learning/enroll', {'courseId': identity})[0], 404)
        self.assertEqual(self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'employee', 'targetId': seller.id, 'mandatory': False})[0], 200)
        self.assertTrue(any(c['id'] == identity for c in seller.request('courses')[1]['courses']), 'Assigned employees can open a department-only course.')
        self.assertEqual(seller.request('learning/enroll', {'courseId': identity})[0], 200)

    def test_module_courses_still_use_the_curriculum_editor(self):
        self.assertEqual(self.admin.request('manage/courses/python-programming/builder')[0], 409)
        source = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == 'python-programming')
        self.assertEqual(source['format'], 'modules')
        self.assertEqual(self.admin.request('admin/courses', {'id': 'python-programming', 'title': source['title'], 'category': source['category'], 'description': source['description'], 'status': 'published', 'format': 'lessons'})[0], 400)
