"""Create a course from a website link: reads the page, writes an original draft course, and applies the portal's assessment rules.

Claude and the website are both faked, so these tests make no network calls and cost nothing.
"""
from contextlib import closing
import json
import os
import time
from types import SimpleNamespace
from unittest import mock

import test_genai_course as genai
from test_portal import PortalFixture  # Puts backend/src on the import path.
import course_generator
from database import connect

URL = 'https://learn.example.com/guide'
SOURCE_TEXT = 'Teams plan their work in short cycles and review it often. ' * 40


def page(url=URL, content=SOURCE_TEXT, status='imported'):
    return {'platform': {'id': 'website', 'name': 'Website'}, 'strategy': 'Article', 'kind': 'article', 'requestedUrl': url, 'sourceUrl': url, 'title': 'Guide', 'description': '',
            'license': None, 'policy': {'fullContent': True, 'note': ''}, 'notes': [], 'stats': {'inaccessible': 0},
            'items': [{'type': 'lesson', 'title': 'Guide', 'url': url, 'status': status, 'content': content, 'words': len(content.split())}]}


def question(tag, n):
    return {'prompt': f'{tag} question {n}?', 'options': [f'{tag} {n} right', f'{tag} {n} wrong a', f'{tag} {n} wrong b', f'{tag} {n} wrong c'], 'correct': 0, 'explanation': f'Why {tag} {n} is right.'}


def lesson_body(n):
    words = ' '.join(f'word{i}' for i in range(120))
    return (f'## Learning objectives\n- Goal {n}\n\n## Teaching section\n{words} [the guide]({URL}) and [a standard](https://www.iso.org/standard)\n\n'
            f'## Key takeaways\n- Point {n}\n\n## Learning reference\n\n- [Source]({URL})')


def course(lessons=4, checks=4, final=15):
    return {'title': 'Working in Short Cycles', 'category': 'Professional Development', 'difficulty': 'beginner', 'description': 'A new course about short work cycles.',
            'lessons': [{'title': f'Lesson {n}', 'description': f'About part {n}.', 'durationMinutes': 10, 'content': lesson_body(n), 'knowledgeCheck': [question(f'L{n}', i) for i in range(checks)]} for n in range(1, lessons + 1)],
            'finalAssessment': [question('Final', i) for i in range(final)]}


class FakeClaude:
    """Stands in for the anthropic module: records the request and returns a prepared response."""
    class AuthenticationError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APIStatusError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    def __init__(self, reply=None, stop_reason='end_turn', error=None):
        self.reply, self.stop_reason, self.error, self.requests = reply if reply is not None else course(), stop_reason, error, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def Anthropic(self, **_):
        return self

    def stream(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error
        message = SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type='text', text=json.dumps(self.reply))])
        return mock.MagicMock(__enter__=lambda _: SimpleNamespace(get_final_message=lambda: message), __exit__=lambda *_: False)


class CourseGeneratorTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee
    urls = iter(range(1000))

    def setUp(self):
        self.url = f'https://learn.example.com/guide-{next(self.urls)}'
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(os.environ, {'LMS_AI_ENABLED': '1'}).start()
        self.claude = FakeClaude()
        mock.patch.object(course_generator.assistant, 'anthropic', self.claude).start()
        self.read = mock.patch.object(course_generator, 'run_import', side_effect=lambda url: page(url)).start()

    def create(self, client=None, **fields):
        started = (client or self.admin).request('manage/course-generator', {'url': self.url, **fields})
        self.assertEqual(started[0], 200, started[1])
        return self.finish(started[1]['job']['id'], client)

    def finish(self, identity, client=None):
        deadline = time.time() + 30
        while time.time() < deadline:
            job = (client or self.admin).request(f'manage/course-generator/{identity}')[1]['job']
            if job['status'] != 'running':
                return job
            time.sleep(0.05)
        self.fail('The course job did not finish.')

    def publish(self, identity):
        """Publish exactly as the course builder does."""
        builder = self.admin.request(f'manage/courses/{identity}/builder')[1]
        fields = ('id', 'title', 'description', 'videoUrl', 'documentUrl', 'documentName', 'resources', 'content', 'exercise', 'durationMinutes')
        c, a = builder['course'], builder['assessment']
        count = a['questionCount'] if a['questionCount'] < len(a['questions']) else None
        assessment = {'title': a['title'], 'passPercent': a['passPercent'], 'maxAttempts': a['maxAttempts'], 'timeLimitMinutes': a['timeLimitMinutes'], **({'questionCount': count} if count else {}),
                      'questions': [{'prompt': q[0], 'options': q[1], 'correct': q[2], 'explanation': q[3]} for q in a['questions']]}
        saved = self.admin.request('admin/courses', {'id': identity, 'title': c['title'], 'category': c['category'], 'description': c['description'], 'status': 'published', 'format': 'lessons',
                                                     'lessons': [{k: l[k] for k in fields} for l in builder['lessons']], 'assessment': assessment})
        self.assertEqual(saved[0], 200, saved[1])

    def test_link_becomes_a_draft_course_in_the_portal_structure(self):
        job = self.create(category='Technical Skills')
        self.assertEqual((job['status'], job['title'], job['error']), ('done', 'Working in Short Cycles', ''))
        request = self.claude.requests[0]
        self.assertEqual((request['model'], request['max_tokens'], request['fallbacks']), (course_generator.assistant.MODEL, 64000, 'default'))
        self.assertEqual(request['output_config']['format']['type'], 'json_schema')
        self.assertIn('own words', request['system'])
        prompt = request['messages'][0]['content']
        self.assertIn('<source>', prompt)
        self.assertIn(SOURCE_TEXT.strip(), prompt)
        self.assertIn('Course category: Technical Skills', prompt)
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT * FROM courses WHERE id=?', (job['courseId'],)).fetchone()
            self.assertEqual((row['status'], row['format'], row['category'], row['duration_minutes'], row['import_status']), ('draft', 'lessons', 'Technical Skills', 40, ''))
            lessons = db.execute('SELECT * FROM course_lessons WHERE course_id=? ORDER BY position', (job['courseId'],)).fetchall()
            self.assertEqual(len(lessons), 4)
            for lesson in lessons:
                self.assertTrue(lesson['content'].endswith('- Point ' + lesson['title'].split()[-1]), 'Lessons end at the key takeaways.')
                self.assertNotIn('Learning reference', lesson['content'])
                self.assertNotIn('learn.example.com', lesson['content'], 'No links back to the source.')
                self.assertIn('[a standard](https://www.iso.org/standard)', lesson['content'], 'Other links stay.')
                check = db.execute('SELECT * FROM assessments WHERE id=?', (lesson['assessment_id'],)).fetchone()
                self.assertEqual((check['kind'], check['pass_percent'], check['max_attempts'], check['question_count'], check['time_limit_minutes']), ('knowledge', 70, 3, 4, 10))
            final = db.execute('SELECT * FROM assessments WHERE id=?', (row['post_assessment_id'],)).fetchone()
            self.assertEqual((final['kind'], final['pass_percent'], final['max_attempts'], final['question_count'], final['time_limit_minutes']), ('post', 70, 3, 10, 20))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_bank WHERE assessment_id=?', (final['id'],)).fetchone()[0], 15)
        # A draft is hidden from employees until an administrator publishes it.
        client = self.employee('Draft Viewer')
        self.assertFalse(any(c['id'] == job['courseId'] for c in client.request('courses')[1]['courses']))
        self.assertFalse(any(a['courseId'] == job['courseId'] for a in client.request('me/assessments')[1]['assessments']))
        # Administrators see where it came from in the builder.
        builder = self.admin.request(f'manage/courses/{job["courseId"]}/builder')[1]['course']
        self.assertEqual((builder['source']['platform'], builder['importReport']['mode']), ('learn.example.com', 'generated'))

    def test_published_course_works_for_employees_through_to_the_certificate(self):
        job = self.create(title='Short Cycles for Teams')
        identity = job['courseId']
        self.assertEqual(job['title'], 'Short Cycles for Teams')
        self.publish(identity)
        client = self.employee('Generated Learner')
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == identity)
        self.assertEqual((listed['title'], listed['lessonCount'], listed['category']), ('Short Cycles for Teams', 4, 'Professional Development'))
        self.assertNotIn('source', listed, 'Employees do not see the source website.')
        self.assertEqual(client.request('learning/enroll', {'courseId': identity})[0], 200)
        data = client.request('learning?courseId=' + identity)[1]
        answer = lambda q: next(o for o in q['options'] if o.endswith('right'))
        # Each lesson keeps its 4-question knowledge check, with no answers sent to the employee.
        start = client.request(f'me/assessments/{data["courseLessons"][0]["assessmentId"]}/start', {})
        self.assertEqual(start[0], 200, start[1])
        self.assertEqual(len(start[1]['attempt']['questions']), 4)
        self.assertEqual(set(start[1]['attempt']['questions'][0]), {'id', 'prompt', 'code', 'options'})
        # The final draws 10 of 15 questions after publishing.
        final = data['requiredAssessmentId']
        attempt = client.request(f'me/assessments/{final}/start', {})[1]['attempt']
        self.assertEqual(len(attempt['questions']), 10)
        result = client.request(f'me/assessments/{final}/submit', {'attemptId': attempt['id'], 'answers': [q['options'].index(answer(q)) for q in attempt['questions']]})[1]['result']
        self.assertEqual((result['status'], result['passPercent']), ('passed', 70))
        for lesson in data['courseLessons']:
            self.assertEqual(client.action('lesson', lessonId=lesson['id'])[0], 200)
        self.assertEqual(len([c for c in client.request('certificates')[1]['certificates'] if c['courseId'] == identity]), 1)

    def test_problems_are_reported_and_create_nothing(self):
        cases = [
            ('short page', lambda: self.read.configure_mock(side_effect=lambda url: page(url, 'Please sign in.')), 'Not enough readable text'),
            ('unreadable page', lambda: self.read.configure_mock(side_effect=course_generator.FetchError('This address could not be reached.')), 'could not be reached'),
            ('refusal', lambda: setattr(self.claude, 'stop_reason', 'refusal'), 'declined'),
            ('too long', lambda: setattr(self.claude, 'stop_reason', 'max_tokens'), 'too large'),
            ('too few lessons', lambda: setattr(self.claude, 'reply', course(lessons=1)), 'number of lessons'),
            ('short knowledge check', lambda: setattr(self.claude, 'reply', course(checks=3)), 'knowledge-check'),
            ('small final', lambda: setattr(self.claude, 'reply', course(final=5)), 'final assessment'),
            ('API failure', lambda: setattr(self.claude, 'error', FakeClaude.APIConnectionError()), 'could not be reached'),
            ('bad key', lambda: setattr(self.claude, 'error', FakeClaude.AuthenticationError()), 'not configured correctly'),
        ]
        with closing(connect(self.db_path)) as db:
            before = db.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
        for name, arrange, message in cases:
            with self.subTest(name):
                self.claude.reply, self.claude.stop_reason, self.claude.error = course(), 'end_turn', None
                self.read.configure_mock(side_effect=lambda url: page(url))
                arrange()
                job = self.create()  # Each failure also frees the job slot for this next attempt.
                self.assertEqual((job['status'], job['courseId']), ('failed', None))
                self.assertIn(message, job['error'])
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], before)

    def test_requests_are_checked_before_anything_is_fetched(self):
        employee = self.employee('Not Allowed')
        self.assertEqual(employee.request('manage/course-generator', {'url': self.url})[0], 403)
        self.assertEqual(employee.request('manage/course-generator')[0], 403)
        for url in ('not a link', 'http://127.0.0.1/admin', 'file:///etc/passwd'):
            self.assertEqual(self.admin.request('manage/course-generator', {'url': url})[0], 400, url)
        self.assertEqual(self.admin.request('manage/course-generator', {'url': self.url, 'category': 'Not a category'})[0], 400)
        self.assertEqual(self.admin.request('manage/course-generator')[1], {'enabled': True})
        with mock.patch.dict(os.environ, {'LMS_AI_ENABLED': '0'}):
            self.assertFalse(self.admin.request('manage/course-generator')[1]['enabled'])
            self.assertEqual(self.admin.request('manage/course-generator', {'url': self.url})[0], 503)
        self.read.assert_not_called()
        self.assertEqual(self.claude.requests, [])

    def test_the_same_link_creates_one_course(self):
        self.assertEqual(self.create()['status'], 'done')
        repeat = self.admin.request('manage/course-generator', {'url': self.url})
        self.assertEqual(repeat[0], 409)
        self.assertIn('already created', repeat[1]['error'])

    def test_jobs_belong_to_the_administrator_who_started_them(self):
        job = self.create()
        hr = self.employee('Other Staff')
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE candidates SET role='hr' WHERE id=?", (hr.id,))
        self.assertEqual(hr.request(f'manage/course-generator/{job["id"]}')[0], 404)
        self.assertEqual(self.admin.request('manage/course-generator/missing')[0], 404)
