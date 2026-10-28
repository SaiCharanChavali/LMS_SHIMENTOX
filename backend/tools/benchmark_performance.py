"""Repeatable in-memory performance fixture; never touches candidate databases."""
import argparse
import hashlib
import json
import sqlite3
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import BACKEND, CURRICULUM, LESSONS, public_curriculum
from admin import admin_action
from analytics import recommendations, activity_times


def fixture(count):
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript((BACKEND/'database/schema.sql').read_text(encoding='utf-8'))
    stamp='2026-01-01T00:00:00Z'
    for identity,role in [('admin','admin'),('employee','employee')]:
        db.execute('INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES (?,?,?,?,?,?,?)',(identity,identity,identity+'@example.com','unused-benchmark-hash',stamp,stamp,role))
    db.execute("INSERT INTO skills VALUES ('skill','Python','Technical','',?)",(stamp,))
    db.execute("INSERT INTO learning_goals(id,employee_id,title,skill_id,target_level,status,created_at,updated_at) VALUES ('goal','employee','Learn Python','skill',2,'active',?,?)",(stamp,stamp))
    for i in range(count):
        identity=f'course-{i:04}'
        db.execute('INSERT INTO courses(id,title,version,status,lessons_json,sets_json,created_by) VALUES (?,?,1,?,?,?,?)',(identity,f'Course {i:04}','published',json.dumps(LESSONS),json.dumps(CURRICULUM),'admin'))
        db.execute("INSERT INTO course_skills VALUES (?,'skill',2)",(identity,))
        for s,item in enumerate(CURRICULUM):
            db.execute('INSERT INTO course_sets VALUES (?,?,?)',(identity,s,item['title']))
            for kind,e,questions in [('exam',-1,item['exam'])]+[('exercise',e,x['questions']) for e,x in enumerate(item['exercises'])]:
                for j,q in enumerate(questions):db.execute('INSERT INTO assessment_questions VALUES (?,?,?,?,?,?,?,?,?)',(identity,s,kind,e,j,q[0],json.dumps(q[1]),q[2],q[3] if len(q)>3 else ''))
        for n in range(10):
            run=f'{identity}-run-{n}'
            db.execute('INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at,archived_at) VALUES (?,?,?,?,?,?)',(run,'employee',identity,n+1,stamp,stamp if n<9 else None))
            for video in range(6):db.execute('INSERT INTO video_progress VALUES (?,?,40,NULL,?)',(run,video,stamp))
    db.commit();return db


def measure(db,fn,repeats):
    fn()  # Warm SQLite statement caches before recording.
    queries=[]
    db.set_trace_callback(lambda sql:queries.append(None) if sql.lstrip().upper().startswith('SELECT') else None)
    tracemalloc.start();result=fn();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();db.set_trace_callback(None)
    elapsed=[]
    for _ in range(repeats):
        start=time.perf_counter();fn();elapsed.append((time.perf_counter()-start)*1000)
    return {'queries':len(queries),'median_ms':round(statistics.median(elapsed),3),'peak_kib':round(peak/1024,1),'output_sha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--courses',type=int,default=100);parser.add_argument('--repeats',type=int,default=7);args=parser.parse_args()
    db=fixture(args.courses)
    try:
        actor=db.execute("SELECT * FROM candidates WHERE id='admin'").fetchone()
        employee=dict(db.execute("SELECT * FROM candidates WHERE id='employee'").fetchone());employee['department']=None
        result={'courses':args.courses,'curriculum':measure(db,lambda:public_curriculum(db,'course-0000'),args.repeats),'admin_courses':measure(db,lambda:admin_action(db,actor,'GET','courses',{}),args.repeats),'recommendations':measure(db,lambda:recommendations(db,employee,{}, {},[]),args.repeats),'activity':measure(db,lambda:activity_times(db),args.repeats)}
        print(json.dumps(result,indent=2))
    finally:db.close()


if __name__=='__main__':main()
