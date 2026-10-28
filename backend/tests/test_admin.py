"""Role boundaries, first-login enforcement, course publishing, and v1 migration."""
from contextlib import closing
import copy
import json
import re
import sqlite3
import unittest
import uuid
import threading
from pathlib import Path

from test_portal import PortalFixture, Client
from server import PortalServer, PortalHandler
from database import connect, initialize, seed_admin, BACKEND, CURRICULUM
from security import password_hash
from services import now


class AdminTests(PortalFixture):
    def test_browser_admin_setup(self):
        path=Path(self.temp.name)/'browser-setup.sqlite3'
        initialize(path)
        server=PortalServer(('127.0.0.1',0),PortalHandler,path)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=Client(f'http://127.0.0.1:{server.server_port}')
        try:
            session=client.request('session')[1]
            self.assertTrue(session['setupRequired']);self.assertTrue(session['setupAllowed'])
            self.assertEqual(client.request('setup/admin',{'name':'Owner','email':'owner@test.com','password':'123'})[0],400)
            created=client.request('setup/admin',{'name':'Owner','email':'owner@test.com','password':'Owner123!'})
            self.assertEqual(created[0],201,created[1])
            self.assertEqual(created[1]['user']['role'],'admin')
            self.assertFalse(created[1]['user']['mustChangePassword'])
            self.assertEqual(client.request('admin/candidates')[0],200)
            self.assertFalse(client.request('session')[1]['setupRequired'])
            other=Client(client.base)
            self.assertEqual(other.request('setup/admin',{'name':'Intruder','email':'intruder@test.com','password':'Intruder123!'})[0],409)
            user=client.request('admin/candidates',{'name':'New Learner','email':'learner@test.com','password':'Assigned123!','role':'candidate'})
            self.assertEqual(user[0],200)
            login=other.request('auth/login',{'email':'learner@test.com','password':'Assigned123!'})
            self.assertEqual(login[0],200)
            self.assertTrue(login[1]['user']['mustChangePassword'])
            self.assertEqual(other.request('admin/candidates')[0],403)
            with closing(connect(path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM candidates WHERE role='admin'").fetchone()[0],1)
        finally:server.shutdown();server.server_close();thread.join()

    def test_packaged_admin_skips_setup_on_a_fresh_database(self):
        path=Path(self.temp.name)/'seeded.sqlite3';initialize(path)
        seed=Path(self.temp.name)/'admin-seed.json'
        seed.write_text(json.dumps({'id':'seeded-admin','name':'Seeded Admin','email':'Seeded@Test.com','passwordHash':password_hash('Seeded123!')}),encoding='utf-8')
        seed_admin(path,seed);seed_admin(path,seed)
        with closing(connect(path)) as db:
            self.assertEqual([tuple(r) for r in db.execute("SELECT email,must_change_password FROM candidates WHERE role='admin'")],[('seeded@test.com',0)],'Seeded once, ready to sign in.')
        server=PortalServer(('127.0.0.1',0),PortalHandler,path)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=Client(f'http://127.0.0.1:{server.server_port}')
        try:
            self.assertFalse(client.request('session')[1]['setupRequired'],'The login page opens instead of admin setup.')
            login=client.request('auth/login',{'email':'seeded@test.com','password':'Seeded123!'})
            self.assertEqual(login[0],200,login[1]);self.assertEqual(login[1]['user']['role'],'admin')
        finally:server.shutdown();server.server_close();thread.join()
        # A database that already has an administrator is never changed.
        other=Path(self.temp.name)/'has-admin.sqlite3';initialize(other)
        with closing(connect(other)) as db, db:
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES ('own','Own','own@test.com','h','t','t','admin')")
        seed_admin(other,seed)
        with closing(connect(other)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0],1)

    def test_browser_setup_preserves_existing_account(self):
        path=Path(self.temp.name)/'browser-promote.sqlite3';initialize(path)
        with closing(connect(path)) as db,db:
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at) VALUES ('existing','Existing Owner','existing@test.com',?,?,?)",(password_hash('Existing123!'),now(),now()))
        server=PortalServer(('127.0.0.1',0),PortalHandler,path)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=Client(f'http://127.0.0.1:{server.server_port}')
        try:
            payload={'name':'Existing Owner','email':'existing@test.com','password':'Wrong123!'}
            self.assertEqual(client.request('setup/admin',payload)[0],403)
            payload['password']='Existing123!'
            response=client.request('setup/admin',payload)
            self.assertEqual(response[0],201,response[1]);self.assertEqual(response[1]['user']['id'],'existing')
            self.assertEqual(response[1]['user']['role'],'admin')
        finally:server.shutdown();server.server_close();thread.join()

    def test_first_login_and_candidate_permissions(self):
        email=f'{uuid.uuid4().hex}@shimentox.com'
        response=self.admin.request('admin/candidates',{'name':'New Candidate','email':email,'password':'Initial123!','role':'candidate'})
        self.assertEqual(response[0],200)
        identity=response[1]['candidate']['id']
        candidate=Client(self.base)
        login=candidate.request('auth/login',{'email':email,'password':'Initial123!'})
        self.assertTrue(login[1]['user']['mustChangePassword'])
        self.assertEqual(login[1]['user']['role'],'employee')  # legacy 'candidate' input maps to employee
        for route in ['learning','records','courses','admin/candidates','admin/courses']:
            self.assertEqual(candidate.request(route)[0],403,route)
        self.assertEqual(candidate.request('auth/password',{'currentPassword':'Initial123!','password':'Initial123!'})[0],400)
        self.assertEqual(candidate.request('auth/password',{'currentPassword':'bad-password','password':'Personal123!'})[0],400)
        changed=candidate.request('auth/password',{'currentPassword':'Initial123!','password':'Personal123!'})
        self.assertEqual(changed[0],200)
        self.assertFalse(changed[1]['user']['mustChangePassword'])
        self.assertEqual(candidate.request('learning')[0],200)
        for route in ['admin/overview','admin/candidates','admin/courses','admin/audit',f'admin/candidates/{identity}/records']:
            self.assertEqual(candidate.request(route)[0],403,route)
        self.assertEqual(candidate.request('admin/candidates',{'name':'Intruder','email':'role@test.com','password':'Change123!','role':'admin'})[0],403)
        self.assertEqual(candidate.request('admin/courses',{'title':'Forbidden'})[0],403)
        self.assertEqual(candidate.request('auth/register',{'role':'admin'})[0],403)
        exported=self.admin.request(f'admin/candidates/{identity}/records')
        self.assertEqual(exported[0],200)
        self.assertNotIn('password_hash',json.dumps(exported[1]))


    def test_admin_password_reset_and_disable(self):
        client=self.candidate()
        identity=client.request('session')[1]['user']['id']
        self.assertEqual(self.admin.request(f'admin/candidates/{identity}/reset-password',{'password':'Reset123!'})[0],200)
        self.assertEqual(client.request('learning')[0],401)
        self.assertEqual(client.request('auth/login',{'email':client.email,'password':'Learning123!'})[0],401)
        reset=client.request('auth/login',{'email':client.email,'password':'Reset123!'})
        self.assertTrue(reset[1]['user']['mustChangePassword'])
        self.assertEqual(self.admin.request(f'admin/candidates/{identity}/status',{'active':False})[0],200)
        self.assertIsNone(client.request('session')[1]['user'])
        self.assertEqual(client.request('auth/login',{'email':client.email,'password':'Reset123!'})[0],401)
        self.assertEqual(self.admin.request(f'admin/candidates/{identity}/status',{'active':True})[0],200)
        self.assertEqual(client.request('auth/login',{'email':client.email,'password':'Reset123!'})[0],200)
        admin_id=self.admin.request('session')[1]['user']['id']
        self.assertEqual(self.admin.request(f'admin/candidates/{admin_id}/status',{'active':False})[0],400)
        self.assertTrue(self.admin.request('admin/audit')[1]['events'])


    def test_course_authoring_publish_and_independent_progress(self):
        candidate=self.candidate()
        source=next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id']=='python-programming')
        content=copy.deepcopy(source['content'])
        content['sets'][0]['title']='Automation foundations'
        saved=self.admin.request('admin/courses',{'title':'Automation Essentials','description':'Practice automation concepts.','category':'Technical Skills','status':'draft','content':content})
        self.assertEqual(saved[0],200,saved[1])
        identity=saved[1]['course']['id']
        self.assertFalse(any(c['id']==identity for c in candidate.request('courses')[1]['courses']))
        self.assertEqual(candidate.request('learning/enroll',{'courseId':identity})[0],404)
        saved=self.admin.request('admin/courses',{'id':identity,'title':'Automation Essentials','description':'Practice automation concepts.','category':'Technical Skills','status':'published','content':content})
        self.assertEqual(saved[0],200,saved[1])
        self.assertTrue(any(c['id']==identity for c in candidate.request('courses')[1]['courses']))
        default_run=candidate.run
        self.assertEqual(candidate.request('learning/enroll',{'courseId':identity})[0],200)
        self.assertNotEqual(candidate.run,default_run)
        loaded=candidate.request('learning?courseId='+identity)
        self.assertEqual(loaded[0],200)
        self.assertEqual(loaded[1]['course'][0]['title'],'Automation foundations')
        self.assertEqual(loaded[1]['courseInfo']['title'],'Automation Essentials')
        for s in range(3):
            self.prepare(candidate,s)
            attempt=candidate.action('exam-start',setIndex=s)[1]['attempt']
            result=candidate.action('exam-finish',attemptId=attempt['id'],answers=[q[2] for q in content['sets'][s]['exam']])
            self.assertEqual(result[1]['attempt']['status'],'passed')
        certificate=result[1]['learning']['certificates'][-1]
        self.assertEqual(certificate['courseTitle'],'Automation Essentials')
        self.assertEqual(certificate['courseId'],identity)
        default=candidate.request('learning')[1]['learning']
        self.assertEqual(default['run']['videos'],{})
        self.assertEqual(candidate.request('certificates')[1]['certificates'][-1]['courseTitle'],'Automation Essentials')
        content['sets'][0]['exam'][0][0]='Modified after enrollment'
        self.assertEqual(self.admin.request('admin/courses',{'id':identity,'title':'Automation Essentials','description':'Course edit.','category':'Technical Skills','status':'published','content':content})[0],409)
        self.assertEqual(self.admin.request('admin/courses',{'title':'Invalid','description':'Invalid structure','category':'Test','status':'published','content':{'sets':[],'lessons':[]}})[0],400)


    def test_v1_migration_preserves_existing_candidate_and_progress(self):
        path=Path(self.temp.name)/'legacy.sqlite3'
        sql=(BACKEND/'database/schema.sql').read_text(encoding='utf-8')
        sql=re.sub(r'last_login_at TEXT,.*?\n\);','last_login_at TEXT\n);',sql,count=1,flags=re.S)
        sql=re.sub(r'version INTEGER NOT NULL,.*?\n\);','version INTEGER NOT NULL\n);',sql,count=1,flags=re.S)
        sql=re.sub(r'CREATE TABLE IF NOT EXISTS admin_events \(.*?\n\);','',sql,flags=re.S).replace('PRAGMA user_version = 6','PRAGMA user_version = 1')
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(sql)
            db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,NULL)',('legacy','Legacy User','legacy@test.com',password_hash('Legacy123!'),now(),now()))
            db.execute("INSERT INTO courses VALUES ('python-programming','PYTHON PROGRAMMING',1)")
            db.execute("INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at) VALUES ('old-run','legacy','python-programming',1,?)",(now(),))
            db.execute("INSERT INTO video_progress VALUES ('old-run',0,20,NULL,?)",(now(),))
        initialize(path)
        initialize(path)
        with closing(connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)
            row=db.execute("SELECT * FROM candidates WHERE id='legacy'").fetchone()
            self.assertEqual(row['role'],'employee')
            self.assertEqual(row['email'],'legacy@test.com')
            self.assertEqual(db.execute("SELECT watched_seconds FROM video_progress WHERE run_id='old-run'").fetchone()[0],20)
