"""Revision games: answers are released only for passed lessons, never for final assessments or during an exam."""
import json
import uuid
from contextlib import closing

import test_genai_course as genai
import test_java_course as java
import test_rag_course as rag
from test_portal import PortalFixture, Client
from database import connect

GENAI = genai.COURSE
FINAL_PROMPTS = {q[0] for q in genai.DATA['finalAssessment']['questions']}


class RevisionGameTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee

    def take(self, learner, assessment_id, correct=True):
        # Answers come from that lesson's own bank: some prompts recur in the final assessment with other answers.
        position = int(assessment_id.rsplit('-', 1)[1]) - 1
        answers = {q[0]: q[1][q[2]] for q in genai.DATA['lessons'][position]['knowledgeCheck']}
        attempt = learner.request(f'me/assessments/{assessment_id}/start', {})[1]['attempt']
        picks = [q['options'].index(answers[q['prompt']]) if correct else next(i for i, o in enumerate(q['options']) if o != answers[q['prompt']])
                 for q in attempt['questions']]
        result = learner.request(f'me/assessments/{assessment_id}/submit', {'attemptId': attempt['id'], 'answers': picks})
        self.assertEqual(result[0], 200, result[1])

    def enrolled(self, course=GENAI):
        learner = self.employee('Game Player')
        self.assertEqual(learner.request('learning/enroll', {'courseId': course})[0], 200)
        return learner, learner.request('learning?courseId=' + course)[1]

    def games(self, learner, course=GENAI):
        return learner.request('me/games?courseId=' + course)[:2]

    def test_locked_until_the_lesson_knowledge_check_is_passed(self):
        learner, data = self.enrolled()
        status, body = self.games(learner)
        self.assertEqual((status, body['lessons']), (200, []), 'Nothing is released before any knowledge check is passed.')
        first = data['courseLessons'][0]
        self.take(learner, first['assessmentId'], correct=False)
        self.assertEqual(self.games(learner)[1]['lessons'], [], 'A failed attempt does not unlock games.')
        self.take(learner, first['assessmentId'])
        lessons = self.games(learner)[1]['lessons']
        self.assertEqual([l['id'] for l in lessons], [first['id']], 'Only the passed lesson is playable.')
        expected = genai.DATA['lessons'][0]['knowledgeCheck']
        self.assertEqual([(q['prompt'], q['options'][q['answer']], q['explanation']) for q in lessons[0]['questions']],
                         [(q[0], q[1][q[2]], q[3]) for q in expected])

    def test_final_assessment_questions_stay_locked_until_the_final_is_passed(self):
        learner, data = self.enrolled()
        for lesson in data['courseLessons']:
            if lesson['assessmentId']:
                self.take(learner, lesson['assessmentId'])
        released = {(q['prompt'], q['options'][q['answer']]) for l in self.games(learner)[1]['lessons'] for q in l['questions']}
        lesson_pairs = {(q[0], q[1][q[2]]) for l in genai.DATA['lessons'] for q in l.get('knowledgeCheck', [])}
        final_pairs = {(q[0], q[1][q[2]]) for q in genai.DATA['finalAssessment']['questions']}
        self.assertEqual(released, lesson_pairs, 'Every passed lesson is playable, with its own answers.')
        self.assertFalse(released & (final_pairs - lesson_pairs), 'No final-assessment answer key is released.')

    def test_blocked_while_an_assessment_is_in_progress(self):
        learner, data = self.enrolled()
        first, second = data['courseLessons'][:2]
        self.take(learner, first['assessmentId'])
        self.assertEqual(learner.request(f'me/assessments/{second["assessmentId"]}/start', {})[0], 200)
        status, body = self.games(learner)
        self.assertEqual(status, 409, body)
        self.assertNotIn('lessons', body)

    def test_requires_enrollment_and_a_session(self):
        learner = self.employee('Not Enrolled')
        self.assertEqual(self.games(learner)[0], 404)
        self.assertEqual(Client(self.base).request('me/games?courseId=' + GENAI)[0], 401)
        self.assertEqual(self.games(learner, 'no-such-course')[0], 404)

    def test_inline_quiz_lessons_unlock_after_passing(self):
        learner, data = self.enrolled(java.COURSE)
        self.assertEqual(self.games(learner, java.COURSE)[1]['lessons'], [])
        lesson = java.DATA['lessons'][0]
        result = learner.action('lesson-quiz', lessonId=f'{java.COURSE}-{lesson["slug"]}', answers=[q[2] for q in lesson['quiz']])
        self.assertTrue(result[1]['quizResult']['passed'], result[1])
        lessons = self.games(learner, java.COURSE)[1]['lessons']
        self.assertEqual(len(lessons), 1)
        self.assertEqual([q['answer'] for q in lessons[0]['questions']], [q[2] for q in lesson['quiz']])
        self.assertTrue(all(q['explanation'] == '' or isinstance(q['explanation'], str) for q in lessons[0]['questions']))
        json.dumps(lessons)

    def test_final_assessment_unlocks_once_passed(self):
        # RAG's only lesson uses the final assessment as its check: its games open after that pass.
        learner, data = self.enrolled(rag.COURSE)
        self.assertEqual(self.games(learner, rag.COURSE)[1]['lessons'], [])
        rag.RAGCourseTests.take(self, learner, 6)
        [lesson] = self.games(learner, rag.COURSE)[1]['lessons']
        self.assertEqual(lesson['id'], data['courseLessons'][0]['id'])
        self.assertEqual({(q['prompt'], q['options'][q['answer']]) for q in lesson['questions']},
                         {(q[0], q[1][q[2]]) for q in rag.DATA['finalAssessment']['questions']})

    def pass_everything(self, learner, course):
        """Mark every question source of a course as passed, straight in the database."""
        with closing(connect(self.db_path)) as db, db:
            run = db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL', (learner.id, course)).fetchone()[0]
            checks = {r[0] for r in db.execute('SELECT assessment_id FROM course_lessons WHERE course_id=? AND assessment_id IS NOT NULL', (course,))}
            checks |= {r[0] for r in db.execute('SELECT post_assessment_id FROM courses WHERE id=? AND post_assessment_id IS NOT NULL', (course,))}
            for check in checks:
                db.execute("INSERT INTO assessment_attempts(id,assessment_id,employee_id,attempt_number,question_ids_json,status,started_at,deadline,total) VALUES (?,?,?,1,'[]','passed','2026-01-01',0,1)",
                           (uuid.uuid4().hex, check, learner.id))
            for (lesson,) in db.execute("SELECT id FROM course_lessons WHERE course_id=? AND quiz_json<>''", (course,)).fetchall():
                db.execute('INSERT OR IGNORE INTO lesson_progress(run_id,lesson_id,completed_at,score) VALUES (?,?,?,100)', (run, lesson, '2026-01-01'))

    def test_every_published_course_offers_games(self):
        with closing(connect(self.db_path)) as db:
            courses = [r[0] for r in db.execute("SELECT id FROM courses WHERE status='published' AND format='lessons'")]
        self.assertGreaterEqual(len(courses), 7)
        for course in courses:
            with self.subTest(course=course):
                learner, _ = self.enrolled(course)
                self.pass_everything(learner, course)
                lessons = self.games(learner, course)[1]['lessons']
                questions = [q for l in lessons for q in l['questions']]
                self.assertGreaterEqual(len(questions), 4, 'Enough questions for every game.')
                self.assertEqual(len({(q['prompt'], q['options'][q['answer']]) for q in questions}), len(questions), 'No duplicates.')

    def test_final_questions_join_the_mix_after_the_final_is_passed(self):
        learner, data = self.enrolled()
        self.pass_everything(learner, GENAI)
        lessons = self.games(learner)[1]['lessons']
        self.assertEqual(lessons[-1]['id'], 'final')
        final_only = {(q[0], q[1][q[2]]) for q in genai.DATA['finalAssessment']['questions']} -             {(q[0], q[1][q[2]]) for l in genai.DATA['lessons'] for q in l.get('knowledgeCheck', [])}
        self.assertEqual({(q['prompt'], q['options'][q['answer']]) for q in lessons[-1]['questions']}, final_only)


    def test_completing_the_course_opens_every_game(self):
        # Lesson checks are optional for this course: a learner can finish it without passing them all.
        learner, data = self.enrolled()
        self.take(learner, data['courseLessons'][0]['assessmentId'])
        self.assertEqual(len(self.games(learner)[1]['lessons']), 1)
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE course_runs SET completed_at='2026-11-12T05:17:24Z' WHERE candidate_id=? AND course_id=? AND archived_at IS NULL", (learner.id, GENAI))
        ids = [l['id'] for l in self.games(learner)[1]['lessons']]
        self.assertEqual(ids, [l['id'] for l in data['courseLessons'] if l['assessmentId']] + ['final'])
