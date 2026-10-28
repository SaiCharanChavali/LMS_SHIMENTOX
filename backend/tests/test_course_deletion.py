"""Removing courses in Manage Courses: permanent deletion of unused courses, archiving when learners have records."""
from contextlib import closing
import tempfile
from pathlib import Path

import test_course_builder as builder
from test_portal import PortalFixture
from database import connect, initialize
from admin import delete_course


class CourseDeletionTests(PortalFixture):
    # Course-builder helpers, without running that class's tests again here.
    account, upload, course = builder.CourseBuilderTests.account, builder.CourseBuilderTests.upload, builder.CourseBuilderTests.course

    def rows(self, sql, *params):
        with closing(connect(self.db_path)) as db:
            return db.execute(sql, params).fetchall()

    def test_unused_course_and_its_content_are_deleted(self):
        identity, _ = self.course(status='published')
        employee = self.account('Assigned Employee')
        self.assertEqual(self.admin.request('manage/assignments', {'courseId': identity, 'targetType': 'employee', 'targetId': employee.id})[0], 200)
        assessment = self.rows('SELECT post_assessment_id FROM courses WHERE id=?', identity)[0][0]
        self.assertIsNotNone(assessment)
        result = self.admin.request(f'admin/courses/{identity}/delete', {})
        self.assertEqual(result[0], 200, result[1])
        self.assertNotIn(identity, [c['id'] for c in self.admin.request('admin/courses')[1]['courses']])
        self.assertNotIn(identity, [c['id'] for c in employee.request('courses')[1]['courses']])
        for table in ('courses', 'course_lessons', 'course_assignments'):
            column = 'id' if table == 'courses' else 'course_id'
            self.assertEqual(self.rows(f'SELECT COUNT(*) FROM {table} WHERE {column}=?', identity)[0][0], 0, table)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM assessments WHERE id=?', assessment)[0][0], 0)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM assessment_bank WHERE assessment_id=?', assessment)[0][0], 0)
        self.assertEqual(self.rows("SELECT action FROM admin_events WHERE target_id=? ORDER BY id DESC", identity)[0][0], 'course_deleted')
        self.assertEqual(self.admin.request(f'admin/courses/{identity}/delete', {})[0], 404)

    def test_course_with_learner_records_is_archived_not_deleted(self):
        identity, _ = self.course(status='published')
        employee = self.account('Enrolled Employee')
        self.assertEqual(employee.request('learning/enroll', {'courseId': identity})[0], 200)
        listed = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == identity)
        self.assertEqual(listed['learners'], 1)
        refused = self.admin.request(f'admin/courses/{identity}/delete', {})
        self.assertEqual(refused[0], 409)
        self.assertIn('Archive it instead', refused[1]['error'])
        self.assertEqual(self.admin.request(f'admin/courses/{identity}/archive', {})[0], 200)
        self.assertEqual(self.rows('SELECT status FROM courses WHERE id=?', identity)[0][0], 'archived')
        self.assertEqual(self.rows('SELECT COUNT(*) FROM course_runs WHERE course_id=?', identity)[0][0], 1)
        self.assertNotIn(identity, [c['id'] for c in employee.request('courses')[1]['courses'] if c.get('status') == 'published'])

    def test_starter_course_and_other_trainers_courses_are_protected(self):
        self.assertEqual(self.admin.request('admin/courses/python-programming/delete', {})[0], 409)
        identity, _ = self.course()
        trainer = self.account('Course Trainer')
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE candidates SET role='trainer' WHERE id=?", (trainer.id,))
        self.assertEqual(trainer.request(f'admin/courses/{identity}/delete', {})[0], 403)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM courses WHERE id=?', identity)[0][0], 1)

    def test_deleted_packaged_course_is_not_recreated_on_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'deleted.sqlite3'
            initialize(path)
            with closing(connect(path)) as db, db:
                admin = {'id': 'admin-1', 'role': 'admin'}
                db.execute("INSERT INTO candidates(id,full_name,email,password_hash,role,created_at,updated_at) VALUES ('admin-1','Admin','a@x.com','x','admin','2026-01-01','2026-01-01')")
                for course in ('java-full-stack-development', 'generative-ai-fundamentals'):
                    delete_course(db, admin, course)
            initialize(path)
            with closing(connect(path)) as db:
                for course in ('java-full-stack-development', 'generative-ai-fundamentals'):
                    self.assertIsNone(db.execute('SELECT 1 FROM courses WHERE id=?', (course,)).fetchone())
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM course_lessons WHERE course_id=?', (course,)).fetchone()[0], 0)
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM course_checkpoints WHERE course_id=?', (course,)).fetchone()[0], 0)
                self.assertIsNotNone(db.execute("SELECT 1 FROM courses WHERE id='shimento-python-developer'").fetchone())

