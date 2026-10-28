"""Original Python path: native enrollment, protected media and durable seed behavior."""
import json
import importlib.util
import io
import re
import tempfile
from contextlib import closing, redirect_stdout
from pathlib import Path

import test_genai_course as genai
from test_portal import PortalFixture
from database import PYTHON_PATH, VIDEO_ROOT, connect, initialize

COURSE = 'shimento-python-developer'
DATA = json.loads(PYTHON_PATH.read_text(encoding='utf-8'))


class PythonPathTests(PortalFixture):
    employee = genai.GenerativeAICourseTests.employee
    fetch = genai.GenerativeAICourseTests.fetch

    def test_detailed_examples_and_assessment_contracts(self):
        spec = importlib.util.spec_from_file_location('python_builder', PYTHON_PATH.parents[1] / 'tools/build_python_path.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        original = builder.build(detailed=False)
        self.assertEqual(DATA, builder.build())
        self.assertEqual(DATA['assignments'], original['assignments'])
        expected = [
            'Amount due: 102.00\n', 'cpython\n3\n',
            '1 75\n2 92\n[48, 75, 92, 60]\n[75, 92]\n',
            "['Python']\n['Git']\nUnassigned\n", "True\nFalse\n{'theme': 'dark'}\n",
            '12 12\n0 None\n-2 None\nmany None\n', '5\n0\n',
            'True\nFalse\n[5000, -1250]\n3750\n', '1920\n', '45\n28\n8\n',
            "['request-C', 'request-B', 'request-A']\n['request-A', 'request-B', 'request-C']\n['request-A', 'request-B', 'request-C']\n",
            "True\n[('ab', 15), ('ba', 20)]\n", '0\n6\n10\n', '2\n-1\n-1\n',
            "[('A', 'B'), ('A', 'C'), ('B', 'C')]\n7\n", "['A', 'B', 'C', 'D']\n",
            '0\n1\n55\n75025\n', 'Git 1\nPython 2\nSQL 1\n{}\n',
        ]
        for number, (lesson, old, output) in enumerate(zip(DATA['lessons'], original['lessons'], expected), 1):
            with self.subTest(module=number):
                self.assertEqual(lesson['practice'], old['practice'])
                self.assertEqual(lesson['quiz'], old['quiz'])
                blocks = re.findall(r'^```\n(.*?)^```', lesson['content'], re.M | re.S)
                if number == 2:
                    blocks = blocks[1:]  # The first block contains terminal commands.
                captured = io.StringIO()
                # Only execute trusted authored examples, never learner submissions.
                with redirect_stdout(captured):
                    for block in blocks:
                        exec(compile(block, f'module-{number}', 'exec'), {})
                self.assertEqual(captured.getvalue(), output)

    def test_detailed_upgrade_preserves_history_and_trainer_edits(self):
        learner = self.employee('Python Content Upgrade')
        learner.request('learning/enroll', {'courseId': COURSE})
        first = COURSE + '-lesson-01'
        learner.action('lesson-draft', lessonId=first, code='print("saved draft")')
        learner.action('lesson-quiz', lessonId=first, answers=[q[2] for q in DATA['lessons'][0]['quiz']])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'upgrade.sqlite3'
            with closing(connect(self.db_path)) as source, closing(connect(path)) as db:
                source.backup(db)
            with closing(connect(path)) as db:
                tables = ['course_runs', 'lesson_progress', 'lesson_code_drafts', 'checkpoint_attempts', 'course_checkpoints']
                before = {t: [tuple(r) for r in db.execute('SELECT * FROM ' + t)] for t in tables}
                assessment = [tuple(r) for r in db.execute('SELECT id,practice_json,quiz_json FROM course_lessons ORDER BY id')]
                db.execute('DELETE FROM course_content_updates WHERE course_id=? AND revision=?', (COURSE, DATA['contentRevision']))
                db.execute('UPDATE course_lessons SET content=? WHERE id=?', ('old stock summary', first))
                # Supply the matching hash to exercise the stock-content migration.
                import hashlib
                source_data = json.loads(json.dumps(DATA))
                source_data['lessons'][0]['legacyContentHash'] = hashlib.sha256(b'old stock summary').hexdigest()
                packaged = Path(folder) / 'course.json'
                packaged.write_text(json.dumps(source_data), encoding='utf-8')
                custom_id = COURSE + '-lesson-02'
                db.execute('UPDATE course_lessons SET content=? WHERE id=?', ('Trainer explanation', custom_id))
                from database import upgrade_python_lessons
                upgrade_python_lessons(db, packaged, 'content-upgrade')
                self.assertEqual(db.execute('SELECT content FROM course_lessons WHERE id=?', (first,)).fetchone()[0], DATA['lessons'][0]['content'])
                self.assertEqual(db.execute('SELECT content FROM course_lessons WHERE id=?', (custom_id,)).fetchone()[0], 'Trainer explanation')
                self.assertEqual(before, {t: [tuple(r) for r in db.execute('SELECT * FROM ' + t)] for t in tables})
                self.assertEqual(assessment, [tuple(r) for r in db.execute('SELECT id,practice_json,quiz_json FROM course_lessons ORDER BY id')])
                db.execute('UPDATE course_lessons SET content=? WHERE id=?', ('Later trainer edit', first))
                upgrade_python_lessons(db, packaged, 'second-initialization')
                self.assertEqual(db.execute('SELECT content FROM course_lessons WHERE id=?', (first,)).fetchone()[0], 'Later trainer edit')

    def test_catalog_enrollment_interactive_lessons_and_progress(self):
        learner = self.employee('Python Learner')
        listed = next(c for c in learner.request('courses')[1]['courses'] if c['id'] == COURSE)
        self.assertEqual(listed['lessonCount'], 18)
        self.assertEqual(listed['title'], DATA['title'])
        self.assertEqual(learner.request('learning/enroll', {'courseId': COURSE})[0], 200)
        lessons = learner.request('learning?courseId=' + COURSE)[1]['courseLessons']
        self.assertEqual([l['title'] for l in lessons], [l['title'] for l in DATA['lessons']])
        first = lessons[0]
        self.assertEqual(first['videoUrl'], '')
        self.assertEqual(first['videoSeconds'], 0)
        self.assertEqual(len(first['quiz']), 3)
        self.assertTrue(first['practice']['tests'])
        self.assertNotIn('"solution"', json.dumps(lessons))
        self.assertEqual(learner.action('lesson', lessonId=first['id'])[0], 409)
        self.assertEqual(learner.action('lesson-video', lessonId=first['id'], position=999, watched=999)[0], 409)
        answers = [q[2] for q in DATA['lessons'][0]['quiz']]
        wrong = learner.action('lesson-quiz', lessonId=first['id'], answers=[(a+1)%3 for a in answers])[1]
        self.assertFalse(wrong['quizResult']['passed'])
        self.assertNotIn(first['id'], wrong['learning']['run']['lessons'])
        done = learner.action('lesson-quiz', lessonId=first['id'], answers=answers)
        self.assertTrue(done[1]['quizResult']['passed'])
        resumed = learner.request('learning?courseId=' + COURSE)[1]
        self.assertTrue(resumed['learning']['run']['lessons'][first['id']]['completed'])
        draft = 'def discounted_price(price, percent):\n    return price\n'
        self.assertEqual(learner.action('lesson-draft', lessonId=first['id'], code=draft)[0], 200)
        self.assertEqual(learner.request('learning?courseId='+COURSE)[1]['learning']['run']['codeDrafts'][first['id']], draft)
        self.assertEqual(learner.action('lesson-draft', lessonId=lessons[3]['id'], code='print(1)')[0], 403)

    def test_reinitializing_preserves_admin_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.sqlite3'
            initialize(path)
            with closing(connect(path)) as db:
                db.execute('UPDATE courses SET title=? WHERE id=?', ('Custom Python title', COURSE))
                db.commit()
            initialize(path)
            with closing(connect(path)) as db:
                self.assertEqual(db.execute('SELECT title FROM courses WHERE id=?', (COURSE,)).fetchone()[0], 'Custom Python title')
                self.assertEqual(db.execute('SELECT count(*) FROM course_lessons WHERE course_id=?', (COURSE,)).fetchone()[0], 18)

    def test_original_labs_and_python_runtime_are_packaged(self):
        for lesson in DATA['lessons']:
            self.assertEqual(len(lesson['quiz']), 3)
            scope = {}
            exec(lesson['practice']['solution'], scope)
            for check in lesson['practice']['tests']:
                exec(check['code'], scope)
        runtime = PYTHON_PATH.parents[2] / 'frontend/public/assets/python-runtime'
        for name in ('pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'LICENSE'):
            self.assertGreater((runtime / name).stat().st_size, 100)
