"""Guard output compatibility, role scope, and bounded query counts."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from benchmark_performance import fixture
from admin import admin_action,course_view,owns_course
from analytics import recommendations,activity_times
from database import CURRICULUM,public_curriculum


class PerformanceTests(unittest.TestCase):
    def setUp(self):self.db=fixture(12)
    def tearDown(self):self.db.close()

    def measured(self,callback):
        statements=[]
        self.db.set_trace_callback(lambda sql:statements.append(sql) if sql.lstrip().upper().startswith('SELECT') else None)
        try:result=callback()
        finally:self.db.set_trace_callback(None)
        return result,len(statements)

    def test_course_lists_preserve_metadata_order_and_role_scope(self):
        db=self.db;stamp='2026-01-01T00:00:00Z'
        db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES ('trainer','Trainer','trainer@example.com','unused',?,?,'trainer')",(stamp,stamp))
        db.execute("INSERT INTO departments VALUES ('department','Engineering',?)",(stamp,))
        db.execute("UPDATE courses SET trainer_id='trainer',department_id='department' WHERE id IN ('course-0002','course-0004')")
        db.execute("INSERT INTO skills VALUES ('second','Automation','Technical','',?)",(stamp,))
        db.execute("INSERT INTO course_skills VALUES ('course-0002','second',3)")
        for identity in ('resource-z','resource-a'):
            db.execute("INSERT INTO course_resources(id,course_id,title,kind,url,created_at) VALUES (?,'course-0002',?,'link','https://example.com',?)",(identity,identity,stamp))
        db.execute("INSERT INTO course_assignments(id,course_id,target_type,target_id,assigned_at) VALUES ('assignment','course-0002','employee','employee',?)",(stamp,))
        for role in ('admin','hr','trainer'):
            actor=dict(db.execute("SELECT * FROM candidates WHERE id=?",('trainer' if role=='trainer' else 'admin',)).fetchone());actor['role']=role
            expected=[course_view(row,True,db) for row in db.execute('SELECT * FROM courses ORDER BY title') if owns_course(actor,row)]
            actual,count=self.measured(lambda:admin_action(db,actor,'GET','courses',{})['courses'])
            self.assertEqual(actual,expected)
            self.assertEqual(count,4)
            if role=='trainer':self.assertEqual([c['id'] for c in actual],['course-0002','course-0004'])

    def test_curriculum_reads_database_questions_without_answer_keys(self):
        expected=copy.deepcopy(CURRICULUM)
        for item in expected:
            item['exam']=[q[:2] for q in item['exam']]
            for ex in item['exercises']:ex['questions']=[q[:2] for q in ex['questions']]
        actual,count=self.measured(lambda:public_curriculum(self.db,'course-0000'))
        self.assertEqual(actual,expected);self.assertEqual(count,2)
        self.db.execute("UPDATE assessment_questions SET prompt='Updated prompt' WHERE course_id='course-0000' AND set_index=0 AND kind='exam' AND question_index=0")
        self.db.execute("DELETE FROM assessment_questions WHERE course_id='course-0000' AND set_index=2 AND kind='exercise' AND exercise_index=1")
        actual=public_curriculum(self.db,'course-0000')
        self.assertEqual(actual[0]['exam'][0][0],'Updated prompt')
        self.assertEqual(actual[2]['exercises'][1]['questions'],[])

    def test_recommendation_ranking_ties_filters_and_query_budget(self):
        self.db.execute("UPDATE courses SET title='A first' WHERE id IN ('course-0002','course-0004','course-0009')")
        self.db.execute("DELETE FROM course_skills WHERE course_id='course-0003'")
        employee=dict(self.db.execute("SELECT * FROM candidates WHERE id='employee'").fetchone());employee['department']=None
        progress={('employee','course-0001'):{'completed':False,'started':True}}
        assigned={('employee','course-0000'):{}}
        paths=[{'nextCourseId':'course-0004','title':'Fast track'}]
        actual,count=self.measured(lambda:recommendations(self.db,employee,progress,assigned,paths))
        self.assertEqual([r['id'] for r in actual],['course-0004','course-0002','course-0009','course-0005','course-0006','course-0007'])
        self.assertEqual(count,7)
        self.assertEqual(actual[0]['score'],7)
        self.assertEqual(actual[0]['reasons'],['Next step in your learning path "Fast track".','Supports your goal "Learn Python".'])
        all_results=recommendations(self.db,employee,progress,assigned,paths,limit=None)
        for limit in (0,1,3,6,100,-1):self.assertEqual(recommendations(self.db,employee,progress,assigned,paths,limit=limit),all_results[:limit])

    def test_activity_stream_preserves_events_and_filters(self):
        stamp='2026-01-01T00:00:00Z'
        self.assertEqual(activity_times(self.db),{'employee':[stamp]*720})
        self.assertEqual(activity_times(self.db,['course-0000']),{'employee':[stamp]*60})
        self.assertEqual(activity_times(self.db,[]),{})


if __name__=='__main__':unittest.main()
