import urllib.request
import urllib.error
"""Generative AI Fundamentals: text-based lessons, inline knowledge checks, shuffled answers, final assessment, upgrade path."""
from contextlib import closing
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from test_portal import PortalFixture, Client
from database import BACKEND, GENAI_COURSE, connect, course_fingerprint, initialize, seed_lesson_course

COURSE = 'generative-ai-fundamentals'
DATA = json.loads(GENAI_COURSE.read_text(encoding='utf-8'))
ANSWERS = {q[0]: q[1][q[2]] for lesson in DATA['lessons'] for q in lesson.get('knowledgeCheck', [])}
ANSWERS.update({q[0]: q[1][q[2]] for q in DATA['finalAssessment']['questions']})


class GenerativeAICourseTests(PortalFixture):
    def employee(self, name='GenAI Learner'):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!', 'role': 'employee'})
        client.id = result[1]['candidate']['id']
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        return client

    def fetch(self, client, path, headers=None):
        """Raw GET returning (status, headers, body); shared with the Python path tests."""
        request = urllib.request.Request(self.base + '/' + path, headers=headers or {})
        try:
            with client.opener.open(request, timeout=15) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            error.close()
            return error.code, dict(error.headers), body

    def enrolled(self):
        client = self.employee()
        self.assertEqual(client.request('learning/enroll', {'courseId': COURSE})[0], 200)
        return client, client.request('learning?courseId=' + COURSE)[1]

    def take(self, client, assessment_id, correct=True):
        start = client.request(f'me/assessments/{assessment_id}/start', {})
        self.assertEqual(start[0], 200, start[1])
        attempt = start[1]['attempt']
        answers = [q['options'].index(ANSWERS[q['prompt']]) if correct else next(i for i, o in enumerate(q['options']) if o != ANSWERS[q['prompt']]) for q in attempt['questions']]
        result = client.request(f'me/assessments/{assessment_id}/submit', {'attemptId': attempt['id'], 'answers': answers})
        self.assertEqual(result[0], 200, result[1])
        return attempt, result[1]['result']

    def test_course_is_text_based_with_structured_lessons(self):
        client, data = self.enrolled()
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['title'], listed['category'], listed['difficulty'], listed['durationMinutes'], listed['visibility'], listed['lessonCount']),
                         ('Generative AI Fundamentals', 'Artificial Intelligence', 'beginner', 60, 'everyone', 6))
        self.assertEqual(listed['description'], DATA['description'])
        lessons = data['courseLessons']
        self.assertEqual([l['title'] for l in lessons], [l['title'] for l in DATA['lessons']])
        for lesson in lessons:
            self.assertEqual((lesson['videoUrl'], lesson['captionsUrl'], lesson['videoSeconds']), ('', '', 0), 'No video for this course.')
            for section in ('## Learning objectives', '## Key takeaways'):
                self.assertIn(section, lesson['content'])
        self.assertTrue(all('|---|' in l['content'] for l in lessons[:5]), 'Lessons 1-5 include a table.')
        self.assertIn('**Before**', lessons[2]['content'])
        self.assertIn('```', lessons[2]['content'])
        self.assertTrue(all(l['assessmentId'] for l in lessons[:5]) and lessons[5]['assessmentId'] is None)
        self.assertEqual(len(lessons[5]['activity']['tasks']), 4)
        self.assertNotIn('modelAnswer', json.dumps(lessons))
        self.assertNotIn('explanation', json.dumps(lessons[5]['activity']))
        kinds = {a['id']: a['kind'] for a in data['assessments']}
        self.assertEqual(kinds[DATA['finalAssessment']['id']], 'post')
        self.assertEqual(data['requiredAssessmentId'], DATA['finalAssessment']['id'])
        self.assertTrue(all(a['passPercent'] == 70 for a in data['assessments']))
        self.assertFalse((BACKEND / 'videos').exists(), 'No video storage folder for this course.')
        self.assertEqual(client.request('videos/generative-ai-fundamentals/lesson-01.mp4')[0], 404)

    def test_knowledge_check_shuffles_answers_scores_and_explains(self):
        bank = {q[0]: q[1] for lesson in DATA['lessons'] for q in lesson.get('knowledgeCheck', [])}
        moved = False
        for _ in range(3):
            client, data = self.enrolled()
            check = data['courseLessons'][0]['assessmentId']
            attempt, result = self.take(client, check, correct=False)
            self.assertEqual(len(attempt['questions']), 4)
            for q in attempt['questions']:
                self.assertEqual(sorted(q['options']), sorted(bank[q['prompt']]))
                self.assertEqual(set(q), {'id', 'prompt', 'code', 'options'}, 'No answer key is sent to employees.')
                moved = moved or q['options'] != bank[q['prompt']]
            self.assertEqual((result['status'], result['percent']), ('failed', 0))
            self.assertTrue(all(d['explanation'] and d['answer'] == ANSWERS[q['prompt']] for d, q in zip(result['details'], attempt['questions'])))
        self.assertTrue(moved, 'Answer positions are shuffled between attempts.')
        attempt, result = self.take(client, check)
        self.assertEqual((result['status'], result['percent'], result['passPercent']), ('passed', 100, 70))
        with closing(connect(self.db_path)) as db:
            rows = db.execute('SELECT status,percent FROM assessment_attempts WHERE assessment_id=? AND employee_id=? ORDER BY attempt_number', (check, client.id)).fetchall()
        self.assertEqual([tuple(r) for r in rows], [('failed', 0), ('passed', 100)])
        info = next(a for a in client.request('learning?courseId=' + COURSE)[1]['assessments'] if a['id'] == check)
        self.assertEqual((info['passed'], info['best'], info['attemptsLeft']), (True, 100, 1), 'Two of the three attempts are used.')

    def test_mark_complete_and_resume_at_last_lesson(self):
        client, data = self.enrolled()
        lessons = data['courseLessons']
        done = client.action('lesson', lessonId=lessons[0]['id'])
        self.assertEqual(done[0], 200, done[1])
        self.assertTrue(done[1]['learning']['run']['lessons'][lessons[0]['id']]['completed'])
        self.assertEqual(client.action('lesson-open', lessonId=lessons[2]['id'])[0], 200)
        again = client.request('learning?courseId=' + COURSE)[1]['learning']['run']
        self.assertEqual(again['lastLessonId'], lessons[2]['id'])
        self.assertEqual(client.action('lesson-open', lessonId='not-a-lesson')[0], 404)
        self.assertEqual(client.action('lesson', lessonId=lessons[5]['id'])[0], 409, 'Lesson 6 completes by passing the exercise.')

    def test_exercise_returns_sample_answers_and_explanations(self):
        client, data = self.enrolled()
        lesson = data['courseLessons'][5]
        tasks = DATA['lessons'][5]['activity']['tasks']
        weak = client.action('lesson-activity', lessonId=lesson['id'], answers=['Write about our product.'] * 4)[1]['activityResult']
        self.assertFalse(weak['passed'])
        self.assertEqual(weak['results'][3]['explanation'], tasks[3]['explanation'])
        strong = client.action('lesson-activity', lessonId=lesson['id'], answers=[t['modelAnswer'] for t in tasks])[1]
        self.assertEqual((strong['activityResult']['score'], strong['activityResult']['passPercent']), (100, 70))
        self.assertEqual(strong['learning']['run']['lessons'][lesson['id']]['score'], 100)

    def test_final_assessment_and_lessons_gate_a_single_certificate(self):
        client, data = self.enrolled()
        final = DATA['finalAssessment']['id']
        attempt, result = self.take(client, final)
        self.assertEqual((len(attempt['questions']), result['status']), (10, 'passed'))
        self.assertFalse(any(c['courseId'] == COURSE for c in client.request('certificates')[1]['certificates']), 'Lessons must also be completed.')
        lessons = data['courseLessons']
        for lesson in lessons[:5]:
            client.action('lesson', lessonId=lesson['id'])
        tasks = DATA['lessons'][5]['activity']['tasks']
        client.action('lesson-activity', lessonId=lessons[5]['id'], answers=[t['modelAnswer'] for t in tasks])
        self.assertEqual(len([c for c in client.request('certificates')[1]['certificates'] if c['courseId'] == COURSE]), 1)
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['progress'], listed['completed']), (100, True))

    def test_upgrade_from_video_version_keeps_progress_and_respects_admin_edits(self):
        folder = Path(tempfile.mkdtemp(prefix='genai-upgrade-'))
        try:
            path = folder / 'old.sqlite3'
            initialize(path)
            lesson_id = f'{COURSE}-lesson-01'
            with closing(connect(path)) as db, db:
                # Recreate the earlier packaged state: version 1 with video fields and a watch record.
                db.execute("UPDATE courses SET version=1,description='old' WHERE id=?", (COURSE,))
                db.execute("UPDATE course_lessons SET video_url='api/videos/x/lesson-01.mp4',captions_url='api/videos/x/lesson-01.vtt',video_seconds=120,content='old text' WHERE course_id=?", (COURSE,))
                db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at) VALUES ('e','Emp','e@x.com','h','t','t')")
                db.execute("INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at) VALUES ('r','e',?,1,'t')", (COURSE,))
                db.execute("INSERT INTO lesson_progress(run_id,lesson_id,completed_at) VALUES ('r',?,'t')", (lesson_id,))
                db.execute("INSERT INTO lesson_watch(run_id,lesson_id,position_seconds,watched_seconds,updated_at) VALUES ('r',?,10,10,'t')", (lesson_id,))
            initialize(path)
            with closing(connect(path)) as db:
                course = db.execute('SELECT version,description FROM courses WHERE id=?', (COURSE,)).fetchone()
                self.assertEqual((course['version'], course['description']), (2, DATA['description']))
                lesson = db.execute('SELECT video_url,captions_url,video_seconds,content FROM course_lessons WHERE id=?', (lesson_id,)).fetchone()
                self.assertEqual(tuple(lesson)[:3], ('', '', 0))
                self.assertIn('## Learning objectives', lesson['content'])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM lesson_progress WHERE lesson_id=?', (lesson_id,)).fetchone()[0], 1, 'Employee progress is kept.')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM lesson_watch WHERE lesson_id=?', (lesson_id,)).fetchone()[0], 0)
            with closing(connect(path)) as db, db:
                db.execute("UPDATE courses SET version=1,description='Edited by HR' WHERE id=?", (COURSE,))
                db.execute("INSERT INTO admin_events(admin_id,action,target_id,detail,created_at) VALUES ('e','course_saved',?,'published','t')", (COURSE,))
            initialize(path)
            with closing(connect(path)) as db:
                self.assertEqual(db.execute('SELECT description FROM courses WHERE id=?', (COURSE,)).fetchone()[0], 'Edited by HR', 'Administrator edits are never overwritten.')
            # A save that changed nothing still matches a packaged fingerprint, so that course is upgraded.
            with closing(connect(path)) as db:
                packaged = dict(DATA, unchangedFingerprints=[course_fingerprint(db, COURSE)])
            source = folder / 'course.json'
            source.write_text(json.dumps(packaged), encoding='utf-8')
            with closing(connect(path)) as db, db:
                seed_lesson_course(db, source, 't')
                self.assertEqual(db.execute('SELECT version,description FROM courses WHERE id=?', (COURSE,)).fetchone()[:], (2, DATA['description']))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_admin_edits_keep_knowledge_checks_and_exercise(self):
        builder = self.admin.request(f'manage/courses/{COURSE}/builder')[1]
        lessons = builder['lessons']
        payload = [{key: l[key] for key in ('id', 'title', 'description', 'videoUrl', 'documentUrl', 'documentName', 'resources', 'content', 'exercise', 'durationMinutes')} for l in lessons]
        course = builder['course']
        body = {'id': COURSE, 'title': course['title'], 'category': course['category'], 'description': course['description'], 'status': 'published', 'format': 'lessons', 'lessons': payload}
        self.assertEqual(self.admin.request('admin/courses', body)[0], 200)
        after = self.admin.request(f'manage/courses/{COURSE}/builder')[1]['lessons']
        self.assertEqual([l['assessmentId'] for l in after], [l['assessmentId'] for l in lessons])
        self.assertTrue(after[5]['hasActivity'])
