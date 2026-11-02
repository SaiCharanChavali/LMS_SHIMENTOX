"""Data Privacy and Protection: seven text lessons with knowledge checks, a final assessment and a single certificate."""
from contextlib import closing
import json

import test_genai_course as genai
from test_portal import PortalFixture
from database import DATA_PRIVACY_COURSE, connect

COURSE = 'data-privacy-protection'
DATA = json.loads(DATA_PRIVACY_COURSE.read_text(encoding='utf-8'))
FINAL = DATA['finalAssessment']['id']
ANSWERS = {q[0]: q[1][q[2]] for lesson in DATA['lessons'] for q in lesson['knowledgeCheck']}
ANSWERS.update({q[0]: q[1][q[2]] for q in DATA['finalAssessment']['questions']})


class DataPrivacyCourseTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee

    def enrolled(self):
        client = self.employee('Privacy Learner')
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

    def test_course_data_is_complete_and_answers_are_spread(self):
        self.assertEqual(len(DATA['lessons']), 7)
        self.assertEqual(sum(l['durationMinutes'] for l in DATA['lessons']), 60)
        questions = [q for l in DATA['lessons'] for q in l['knowledgeCheck']] + DATA['finalAssessment']['questions']
        self.assertEqual(len(DATA['finalAssessment']['questions']), 10)
        self.assertTrue(all(len(q[1]) == 4 and q[3] for q in questions), 'Four options and an explanation per question.')
        self.assertEqual({q[2] for q in DATA['finalAssessment']['questions']}, {0, 1, 2, 3}, 'Correct answers are not always option A.')
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT title,category,status,difficulty,duration_minutes,visibility,department_id,format,post_assessment_id FROM courses WHERE id=?', (COURSE,)).fetchone()
            self.assertEqual(tuple(row), ('Data Privacy and Protection', 'Cybersecurity and Data Protection', 'published', 'beginner', 60, 'everyone', None, 'lessons', FINAL))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM course_lessons WHERE course_id=?', (COURSE,)).fetchone()[0], 7)
            self.assertEqual(db.execute('SELECT pass_percent,question_count FROM assessments WHERE id=?', (FINAL,)).fetchone()[:], (70, 10))
        managed = {c['id']: c for c in self.admin.request('admin/courses')[1]['courses']}
        self.assertEqual(managed[COURSE]['status'], 'published', 'Listed in Admin, Manage Courses.')

    def test_course_is_listed_with_seven_text_lessons(self):
        client, data = self.enrolled()
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['title'], listed['category'], listed['difficulty'], listed['durationMinutes'], listed['layout'], listed['lessonCount']),
                         ('Data Privacy and Protection', 'Cybersecurity and Data Protection', 'beginner', 60, 'standard', 7))
        lessons = data['courseLessons']
        self.assertEqual([l['title'] for l in lessons], [l['title'] for l in DATA['lessons']])
        for lesson in lessons:
            self.assertEqual((lesson['videoUrl'], lesson['videoSeconds']), ('', 0))
            self.assertTrue(lesson['description'])
            for section in ('## Learning objectives', '## Key takeaways', ':::example'):
                self.assertIn(section, lesson['content'])
            self.assertTrue(lesson['assessmentId'])
        self.assertEqual(data['requiredAssessmentId'], FINAL)
        self.assertTrue(all((a['passPercent'], a['attemptsLeft']) == (70, 3) for a in data['assessments']), 'Every check: 70% pass mark, three attempts.')

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
        certificates = [c for c in client.request('certificates')[1]['certificates'] if c['courseId'] == COURSE]
        self.assertEqual(len(certificates), 1)
        self.assertEqual(certificates[0]['courseTitle'], 'Data Privacy and Protection')
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['progress'], listed['completed']), (100, True))
