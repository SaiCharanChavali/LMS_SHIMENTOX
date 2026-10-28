"""Retrieval-Augmented Generation (RAG): article-layout text lesson, inline 6-question knowledge check, completion."""
from contextlib import closing
import json

import test_genai_course as genai
from test_portal import PortalFixture
from database import RAG_COURSE, connect

COURSE = 'retrieval-augmented-generation'
DATA = json.loads(RAG_COURSE.read_text(encoding='utf-8'))
CHECK = DATA['finalAssessment']['id']
ANSWERS = {q[0]: q[1][q[2]] for q in DATA['finalAssessment']['questions']}


class RAGCourseTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee

    def enrolled(self):
        client = self.employee('RAG Learner')
        self.assertEqual(client.request('learning/enroll', {'courseId': COURSE})[0], 200)
        return client, client.request('learning?courseId=' + COURSE)[1]

    def take(self, client, correct_count):
        start = client.request(f'me/assessments/{CHECK}/start', {})
        self.assertEqual(start[0], 200, start[1])
        attempt = start[1]['attempt']
        answers = []
        for n, q in enumerate(attempt['questions']):
            right = q['options'].index(ANSWERS[q['prompt']])
            answers.append(right if n < correct_count else (right + 1) % len(q['options']))
        result = client.request(f'me/assessments/{CHECK}/submit', {'attemptId': attempt['id'], 'answers': answers})
        self.assertEqual(result[0], 200, result[1])
        return attempt, result[1]['result']

    def test_course_is_an_article_layout_text_lesson(self):
        client, data = self.enrolled()
        listed = {c['id']: c for c in client.request('courses')[1]['courses']}
        course = listed[COURSE]
        self.assertEqual((course['title'], course['category'], course['difficulty'], course['durationMinutes'], course['layout'], course['lessonCount']),
                         ('Retrieval-Augmented Generation (RAG)', 'Artificial Intelligence', 'beginner', 30, 'article', 1))
        self.assertEqual(listed['generative-ai-fundamentals']['layout'], 'standard', 'Other courses keep the standard lesson page.')
        [lesson] = data['courseLessons']
        self.assertEqual(lesson['title'], 'What is Retrieval-Augmented Generation (RAG)')
        self.assertEqual((lesson['videoUrl'], lesson['captionsUrl'], lesson['videoSeconds']), ('', '', 0))
        self.assertTrue(lesson['updatedAt'])
        content = lesson['content']
        for heading in ('## Understanding RAG in plain language', '## Components of RAG architecture', '### The role of Dense Passage Retrieval (DPR)',
                        '## How RAG works', '## RAG architecture illustration', '## FiD vs. FiE', '## Advantages of RAG',
                        '## Practical example: a company knowledge assistant', '## Knowledge check'):
            self.assertIn(heading, content)
        for step in ('Query processing', 'Embedding generation', 'Vector database retrieval', 'Retrieved context selection', 'LLM response generation', 'Final response'):
            self.assertIn(step, content)
        self.assertEqual(content.count('- **Role in the workflow:**'), 6, 'Every workflow step explains its role.')
        self.assertIn(':::flow', content)
        self.assertIn(':::slot knowledge-check', content)
        self.assertIn('does not remove it', content)
        # The source article is kept in the course data for attribution, not shown on the lesson page.
        self.assertNotIn('## Learning reference', content)
        self.assertNotIn('geeksforgeeks.org', content)
        self.assertEqual(DATA['source']['url'], 'https://www.geeksforgeeks.org/nlp/rag-architecture/')
        self.assertEqual(lesson['assessmentId'], CHECK)
        self.assertEqual(data['requiredAssessmentId'], CHECK)

    def test_knowledge_check_shuffles_scores_explains_and_saves(self):
        bank = {q[0]: q[1] for q in DATA['finalAssessment']['questions']}
        client, _ = self.enrolled()
        attempt, result = self.take(client, 4)
        self.assertEqual(len(attempt['questions']), 6)
        for q in attempt['questions']:
            self.assertEqual(len(q['options']), 4)
            self.assertEqual(sorted(q['options']), sorted(bank[q['prompt']]))
            self.assertEqual(set(q), {'id', 'prompt', 'code', 'options'}, 'No answer key is sent to employees.')
        # 4 of 6 is 67%, below the 70% pass mark.
        self.assertEqual((result['status'], result['score'], result['total'], result['percent'], result['passPercent']), ('failed', 4, 6, 67, 70))
        self.assertTrue(all(d['explanation'] and d['answer'] == ANSWERS[q['prompt']] for d, q in zip(result['details'], attempt['questions'])))
        orders = [attempt['questions']]
        for _ in range(3):
            orders.append(self.take(client, 0)[0]['questions'])
        self.assertTrue(any(q['options'] != bank[q['prompt']] for questions in orders for q in questions), 'Answer positions are shuffled.')
        attempt, result = self.take(client, 5)
        self.assertEqual((result['status'], result['percent']), ('passed', 83))
        with closing(connect(self.db_path)) as db:
            rows = db.execute('SELECT status,percent FROM assessment_attempts WHERE assessment_id=? AND employee_id=? ORDER BY attempt_number', (CHECK, client.id)).fetchall()
        self.assertEqual([tuple(r) for r in rows], [('failed', 67), ('failed', 0), ('failed', 0), ('failed', 0), ('passed', 83)])

    def test_mark_complete_and_pass_issue_one_certificate(self):
        client, data = self.enrolled()
        lesson = data['courseLessons'][0]
        done = client.action('lesson', lessonId=lesson['id'])
        self.assertEqual(done[0], 200, done[1])
        self.assertTrue(done[1]['learning']['run']['lessons'][lesson['id']]['completed'])
        self.assertFalse(any(c['courseId'] == COURSE for c in client.request('certificates')[1]['certificates']), 'The knowledge check must be passed too.')
        self.take(client, 6)
        self.assertEqual(len([c for c in client.request('certificates')[1]['certificates'] if c['courseId'] == COURSE]), 1)
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['progress'], listed['completed']), (100, True))
