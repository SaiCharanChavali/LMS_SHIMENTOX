"""Agile and Scrum: six text lessons with knowledge checks, a final assessment and a single certificate."""
from contextlib import closing
import json
from pathlib import Path

import test_genai_course as genai
from test_portal import PortalFixture
from database import AGILE_COURSE, PHISHING_COURSE, POSH_COURSE, connect, initialize

COURSE = 'agile-and-scrum'
DATA = json.loads(AGILE_COURSE.read_text(encoding='utf-8'))
FINAL = DATA['finalAssessment']['id']
ANSWERS = {q[0]: q[1][q[2]] for lesson in DATA['lessons'] for q in lesson['knowledgeCheck']}
ANSWERS.update({q[0]: q[1][q[2]] for q in DATA['finalAssessment']['questions']})


class AgileScrumCourseTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee

    def enrolled(self):
        client = self.employee('Agile Learner')
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
        self.assertEqual((listed['title'], listed['category'], listed['difficulty'], listed['durationMinutes'], listed['layout'], listed['lessonCount']),
                         ('Agile and Scrum', 'Professional Development', 'beginner', 60, 'standard', 6))
        lessons = data['courseLessons']
        self.assertEqual([l['title'] for l in lessons], [l['title'] for l in DATA['lessons']])
        for lesson in lessons:
            self.assertEqual((lesson['videoUrl'], lesson['videoSeconds']), ('', 0))
            for section in ('## Learning objectives', '## Key takeaways'):
                self.assertIn(section, lesson['content'])
            # The source is kept in the course data for attribution, not shown on the lesson page.
            self.assertNotIn('Learning reference', lesson['content'])
            self.assertNotIn('https://www.atlassian.com/agile', lesson['content'])
            self.assertTrue(lesson['assessmentId'])
        self.assertIn(':::flow One sprint, from plan to improvement', lessons[3]['content'])
        self.assertEqual(data['requiredAssessmentId'], FINAL)
        self.assertEqual(DATA['source']['url'], 'https://www.atlassian.com/agile')
        kinds = {a['id']: a for a in data['assessments']}
        self.assertEqual(kinds[FINAL]['kind'], 'post')
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
        self.assertEqual(certificates[0]['courseTitle'], 'Agile and Scrum')
        listed = next(c for c in client.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual((listed['progress'], listed['completed']), (100, True))

    def test_older_installs_lose_the_learning_reference_section(self):
        path = Path(self.temp.name) / 'reference-upgrade.sqlite3'
        initialize(path)
        ids = [json.loads(source.read_text(encoding='utf-8'))['id'] for source in (POSH_COURSE, PHISHING_COURSE, AGILE_COURSE)]
        section = '\n\n## Learning reference\n\n- [Source](https://example.com)'
        with closing(connect(path)) as db, db:
            for course_id in ids:
                # Recreate version 1, where every lesson ended with a Learning reference section.
                db.execute('UPDATE courses SET version=1 WHERE id=?', (course_id,))
                db.execute('UPDATE course_lessons SET content=content||? WHERE course_id=?', (section, course_id))
        initialize(path)
        with closing(connect(path)) as db:
            for course_id in ids:
                self.assertEqual(db.execute('SELECT version FROM courses WHERE id=?', (course_id,)).fetchone()[0], 2)
                contents = [r[0] for r in db.execute('SELECT content FROM course_lessons WHERE course_id=?', (course_id,))]
                self.assertTrue(contents and not any('Learning reference' in c for c in contents))
