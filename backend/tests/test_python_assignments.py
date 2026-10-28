"""Exercise real checkpoint APIs, grading, interruptions, access boundaries and certificate gates."""
import concurrent.futures
import json
from contextlib import closing

import test_genai_course as genai
from test_portal import Client, PortalFixture
from database import connect

COURSE = 'shimento-python-developer'


class PythonAssignmentTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee
    fetch = genai.GenerativeAICourseTests.fetch

    def enrolled(self):
        learner = self.employee('Assignment Learner')
        self.assertEqual(learner.request('learning/enroll', {'courseId': COURSE})[0], 200)
        data = learner.request('learning?courseId=' + COURSE)[1]
        return learner, data['courseLessons'], data['learning']['run']['checkpoints']

    def watch(self, learner, number):
        with closing(connect(self.db_path)) as db:
            lesson = db.execute('SELECT * FROM course_lessons WHERE course_id=? AND position=?', (COURSE, number - 1)).fetchone()
        answers = [q[2] for q in json.loads(lesson['quiz_json'])]
        response = learner.action('lesson-quiz', lessonId=lesson['id'], answers=answers)
        self.assertEqual(response[0], 200, response[1])
        return response[1]

    def first_group(self, learner):
        for number in range(1, 4):
            self.watch(learner, number)

    def start(self, learner, checkpoint):
        result = learner.action('checkpoint-start', checkpointId=checkpoint['id'])
        self.assertEqual(result[0], 200, result[1])
        self.assertNotIn('"correct"', json.dumps(result[1]))
        self.assertNotIn('questions_json', json.dumps(result[1]))
        return result[1]['attempt']

    def answers(self, attempt):
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT questions_json FROM checkpoint_attempts WHERE id=?', (attempt['id'],)).fetchone()
        return [q['correct'] for q in json.loads(row[0])]

    def test_six_checkpoints_and_locked_material_are_public_without_keys(self):
        learner, lessons, checkpoints = self.enrolled()
        self.assertEqual([c['afterLesson'] for c in checkpoints], [3, 6, 9, 12, 15, 18])
        self.assertTrue(all((c['questionCount'], c['passPercent'], c['maxAttempts'], c['timeLimitSeconds']) == (8, 75, 3, 600) for c in checkpoints))
        self.assertTrue(all(not c['ready'] for c in checkpoints))
        self.assertFalse(lessons[2]['locked'])
        self.assertTrue(lessons[3]['locked'])
        self.assertEqual(lessons[3]['content'], '')
        self.assertEqual(lessons[3]['videoUrl'], '')
        public = json.dumps(learner.request('learning?courseId=' + COURSE)[1])
        self.assertNotIn('"correct"', public)
        self.assertNotIn('questions_json', public)
        for suffix in ('mp4', 'vtt', 'jpg'):
            self.assertEqual(self.fetch(learner, f'api/videos/{COURSE}/lesson-04.{suffix}')[0], 404)
        self.assertEqual(self.fetch(Client(self.base), f'api/videos/{COURSE}/lesson-01.mp4')[0], 401)

    def test_prerequisites_grading_replay_and_next_group_unlock(self):
        learner, lessons, checkpoints = self.enrolled()
        self.assertEqual(learner.action('checkpoint-start', checkpointId=checkpoints[0]['id'])[0], 403)
        self.watch(learner, 1)
        self.watch(learner, 2)
        self.assertEqual(learner.action('checkpoint-start', checkpointId=checkpoints[0]['id'])[0], 403)
        self.assertEqual(learner.action('lesson-video', lessonId=lessons[3]['id'], position=100, watched=100)[0], 403)
        self.watch(learner, 3)
        attempt = self.start(learner, checkpoints[0])
        self.assertEqual(learner.action('lesson', lessonId=lessons[0]['id'])[0], 409)
        self.assertEqual(learner.action('checkpoint-finish', attemptId=attempt['id'], answers=[True] * 8)[0], 400)
        wrong = [(a + 1) % 4 for a in self.answers(attempt)]
        failed = learner.action('checkpoint-finish', attemptId=attempt['id'], answers=wrong, score=100, passed=True)[1]
        self.assertEqual((failed['attempt']['status'], failed['attempt']['score']), ('failed', 0))
        replay = learner.action('checkpoint-finish', attemptId=attempt['id'], answers=self.answers(attempt))[1]
        self.assertEqual(replay['attempt']['status'], 'failed')
        attempt = self.start(learner, checkpoints[0])
        answers = self.answers(attempt)
        answers[-2:] = [(a + 1) % 4 for a in answers[-2:]]
        passed = learner.action('checkpoint-finish', attemptId=attempt['id'], answers=answers)[1]
        self.assertEqual((passed['attempt']['status'], passed['attempt']['percent']), ('passed', 75))
        unlocked = learner.request('learning?courseId=' + COURSE)[1]['courseLessons']
        self.assertFalse(unlocked[3]['locked'])
        self.assertTrue(unlocked[6]['locked'])
        self.assertTrue(unlocked[3]['practice'])
        self.assertEqual(unlocked[3]['videoUrl'], '')
        self.assertEqual(learner.action('checkpoint-start', checkpointId=checkpoints[0]['id'])[0], 409)
        self.assertEqual(learner.action('checkpoint-start', checkpointId=checkpoints[1]['id'])[0], 403)

    def test_reload_deadline_termination_limits_and_new_run(self):
        learner, _, checkpoints = self.enrolled()
        self.first_group(learner)
        first = self.start(learner, checkpoints[0])
        resumed = learner.action('resume')[1]
        self.assertEqual(resumed['learning']['run']['checkpoints'][0]['attempts'][0]['status'], 'terminated')
        replay = learner.action('checkpoint-finish', attemptId=first['id'], answers=self.answers(first))[1]
        self.assertEqual(replay['attempt']['status'], 'terminated')
        second = self.start(learner, checkpoints[0])
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE checkpoint_attempts SET deadline=0 WHERE id=?', (second['id'],))
        expired = learner.action('checkpoint-finish', attemptId=second['id'], answers=self.answers(second))[1]
        self.assertEqual(expired['attempt']['status'], 'terminated')
        self.assertIn('Time expired', expired['attempt']['reason'])
        third = self.start(learner, checkpoints[0])
        ended = learner.action('checkpoint-finish', attemptId=third['id'], terminate=True, reason='Switched tabs')[1]
        self.assertEqual(ended['attempt']['reason'], 'Switched tabs')
        self.assertEqual(learner.action('checkpoint-start', checkpointId=checkpoints[0]['id'])[0], 409)
        old_run = learner.run
        reset = learner.action('restart')[1]['learning']['run']
        self.assertNotEqual(reset['id'], old_run)
        self.assertEqual(reset['checkpoints'][0]['attempts'], [])
        self.assertFalse(reset['checkpoints'][0]['ready'])
        history = learner.request('records')[1]['assignment_attempts']
        self.assertEqual(len(history), 3)
        self.assertNotIn('questions_json', json.dumps(history))

    def test_ownership_csrf_and_concurrent_start(self):
        learner, _, checkpoints = self.enrolled()
        other, _, _ = self.enrolled()
        self.first_group(learner)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            starts = list(pool.map(lambda _: learner.action('checkpoint-start', checkpointId=checkpoints[0]['id']), range(2)))
        self.assertEqual(sorted(r[0] for r in starts), [200, 409])
        attempt = next(r[1]['attempt'] for r in starts if r[0] == 200)
        self.assertEqual(other.action('checkpoint-finish', attemptId=attempt['id'], terminate=True)[0], 404)
        self.assertEqual(other.request('learning/checkpoint-finish', {'runId': learner.run, 'attemptId': attempt['id'], 'terminate': True})[0], 409)
        self.assertEqual(learner.request('learning/checkpoint-finish', {'runId': learner.run, 'attemptId': attempt['id'], 'terminate': True}, {'X-CSRF-Token': 'wrong'})[0], 403)
        saved = learner.action('checkpoint-finish', attemptId=attempt['id'], answers=self.answers(attempt))[1]
        self.assertEqual(saved['attempt']['status'], 'passed')

    def test_six_passes_are_required_for_certificate_and_progress(self):
        learner, _, checkpoints = self.enrolled()
        for group, checkpoint in enumerate(checkpoints):
            for number in range(group * 3 + 1, group * 3 + 4):
                state = self.watch(learner, number)
            self.assertIsNone(state['learning']['run']['completedAt'])
            self.assertEqual(len(state['learning']['certificates']), 0)
            attempt = self.start(learner, checkpoint)
            state = learner.action('checkpoint-finish', attemptId=attempt['id'], answers=self.answers(attempt))[1]
        self.assertIsNotNone(state['learning']['run']['completedAt'])
        self.assertEqual(len(state['learning']['certificates']), 1)
        catalog = next(c for c in learner.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual(catalog['progress'], 100)
        self.assertTrue(catalog['completed'])
        reset = learner.action('restart')[1]
        self.assertEqual(len(reset['learning']['certificates']), 1)
        self.assertTrue(all(not c['passed'] for c in reset['learning']['run']['checkpoints']))
