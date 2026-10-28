"""POSH (PoSH Act, 2013): six text lessons with knowledge checks, a final assessment and a single certificate.

Also covers the exam rules shared by every assessment: ended attempts count, no resuming, and no more than three attempts.
"""
from contextlib import closing
import json
import sqlite3
from pathlib import Path

import test_genai_course as genai
from test_portal import PortalFixture
from database import POSH_COURSE, connect, initialize

COURSE = 'posh-act-awareness'
DATA = json.loads(POSH_COURSE.read_text(encoding='utf-8'))
FINAL = DATA['finalAssessment']['id']
ANSWERS = {q[0]: q[1][q[2]] for lesson in DATA['lessons'] for q in lesson['knowledgeCheck']}
ANSWERS.update({q[0]: q[1][q[2]] for q in DATA['finalAssessment']['questions']})


class POSHCourseTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee

    def enrolled(self):
        client = self.employee('POSH Learner')
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

    def test_course_is_listed_with_six_text_lessons(self):
        client, data = self.enrolled()
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['title'], listed['category'], listed['difficulty'], listed['durationMinutes'], listed['lessonCount']),
                         ('POSH', 'Policies & Compliance', 'beginner', 60, 6))
        lessons = data['courseLessons']
        self.assertEqual([l['title'] for l in lessons], [l['title'] for l in DATA['lessons']])
        for lesson in lessons:
            self.assertEqual((lesson['videoUrl'], lesson['videoSeconds']), ('', 0))
            for section in ('## Learning objectives', '## Key takeaways', '## Learning reference'):
                self.assertIn(section, lesson['content'])
            self.assertIn('(https://www.istm.gov.in/home/posh_act)', lesson['content'])
            self.assertTrue(lesson['assessmentId'])
        self.assertIn(':::flow Stages of complaints handling', lessons[3]['content'])
        self.assertEqual(data['requiredAssessmentId'], FINAL)

    def test_knowledge_check_scores_and_explains_without_leaking_answers(self):
        client, data = self.enrolled()
        check = data['courseLessons'][0]['assessmentId']
        attempt, result = self.take(client, check, correct=False)
        self.assertEqual(len(attempt['questions']), 4)
        self.assertTrue(all(set(q) == {'id', 'prompt', 'code', 'options'} for q in attempt['questions']), 'No answer key is sent to employees.')
        self.assertEqual((result['status'], result['percent']), ('failed', 0))
        self.assertTrue(all(d['explanation'] for d in result['details']))
        self.assertEqual(self.take(client, check)[1]['status'], 'passed')

    def test_lessons_and_final_assessment_issue_one_certificate(self):
        client, data = self.enrolled()
        attempt, result = self.take(client, FINAL)
        self.assertEqual((len(attempt['questions']), result['status'], result['passPercent']), (10, 'passed', 70))
        self.assertFalse(any(c['courseId'] == COURSE for c in client.request('certificates')[1]['certificates']), 'Lessons must also be completed.')
        for lesson in data['courseLessons']:
            self.assertEqual(client.action('lesson', lessonId=lesson['id'])[0], 200)
        self.assertEqual(len([c for c in client.request('certificates')[1]['certificates'] if c['courseId'] == COURSE]), 1)
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['progress'], listed['completed']), (100, True))

    def test_rule_breaks_terminate_the_attempt_and_three_attempts_is_the_limit(self):
        client, _ = self.enrolled()
        first = client.request(f'me/assessments/{FINAL}/start', {})[1]['attempt']
        ended = client.request(f'me/assessments/{FINAL}/terminate', {'attemptId': first['id'], 'reason': 'Attempt terminated: you exited full screen.'})
        self.assertEqual(ended[0], 200, ended[1])
        self.assertEqual((ended[1]['result']['status'], ended[1]['result']['reason']), ('terminated', 'Attempt terminated: you exited full screen.'))
        late = client.request(f'me/assessments/{FINAL}/submit', {'attemptId': first['id'], 'answers': [0] * 10})
        self.assertEqual(late[0], 409, 'A terminated attempt cannot be submitted.')
        # Starting again never resumes an open attempt: it ends, counts as used, and a new attempt begins.
        second = client.request(f'me/assessments/{FINAL}/start', {})[1]['attempt']
        third = client.request(f'me/assessments/{FINAL}/start', {})[1]['attempt']
        self.assertNotEqual(second['id'], third['id'])
        self.assertEqual(client.request(f'me/assessments/{FINAL}/start', {})[0], 409, 'No more than three attempts.')
        mine = next(a for a in client.request('me/assessments')[1]['assessments'] if a['id'] == FINAL)
        self.assertEqual([(a['status'], a['reason']) for a in mine['attempts']],
                         [('terminated', 'Attempt terminated: you exited full screen.'), ('terminated', 'The attempt was interrupted before it was submitted.'), ('in-progress', '')])
        self.assertEqual((mine['maxAttempts'], mine['attemptsLeft']), (3, 0))

    def test_every_assessment_allows_at_most_three_attempts(self):
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute('SELECT MAX(max_attempts) FROM assessments').fetchone()[0], 3)
        body = {'title': 'Future check', 'kind': 'knowledge', 'passPercent': 60, 'maxAttempts': 5, 'questionCount': 1, 'timeLimitMinutes': 5, 'status': 'published',
                'questions': [['Question?', ['Right', 'Wrong'], 0, 'Right is right.']]}
        self.assertEqual(self.admin.request('manage/assessments', body)[0], 400, 'New assessments cannot allow more than three attempts.')
        body['maxAttempts'] = 3
        self.assertEqual(self.admin.request('manage/assessments', body)[0], 200)

    def test_older_databases_gain_terminated_attempts_without_losing_history(self):
        path = Path(self.temp.name) / 'older-attempts.sqlite3'
        initialize(path)
        with closing(sqlite3.connect(path)) as db, db:
            # Recreate the attempts table as it was before the exam rules, with one finished attempt.
            db.executescript('''DROP TABLE assessment_attempts;
                CREATE TABLE assessment_attempts (id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, employee_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
                    question_ids_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('in-progress','passed','failed','expired')), started_at TEXT NOT NULL,
                    deadline REAL NOT NULL, finished_at TEXT, score INTEGER, total INTEGER NOT NULL, percent INTEGER, answers_json TEXT,
                    option_orders_json TEXT NOT NULL DEFAULT '', UNIQUE(assessment_id, employee_id, attempt_number));
                INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at) VALUES ('e','Emp','e@x.com','h','t','t');
                INSERT INTO assessment_attempts(id,assessment_id,employee_id,attempt_number,question_ids_json,status,started_at,deadline,total,percent)
                    VALUES ('old','posh-act-awareness-final','e',1,'[]','passed','t',0,10,90);''')
        initialize(path)
        with closing(connect(path)) as db, db:
            self.assertEqual(tuple(db.execute("SELECT status,percent,reason FROM assessment_attempts WHERE id='old'").fetchone()), ('passed', 90, ''))
            db.execute("UPDATE assessment_attempts SET status='terminated',reason='Left full screen' WHERE id='old'")
