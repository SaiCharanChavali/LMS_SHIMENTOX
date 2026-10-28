"""POSH (PoSH Act, 2013): six text lessons with knowledge checks, a final assessment and a single certificate."""
import json

import test_genai_course as genai
from test_portal import PortalFixture
from database import POSH_COURSE

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
