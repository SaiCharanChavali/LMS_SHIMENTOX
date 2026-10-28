"""Exercise real HTTP endpoints, session cookies, and an isolated SQLite database."""
import concurrent.futures
from contextlib import closing
import http.cookiejar
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import initialize, connect, CURRICULUM
from server import PortalServer, PortalHandler
from security import password_hash
from services import uid, now, create_run


class Client:
    def __init__(self, base):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf = ''
        self.run = None

    def request(self, route, data=None, headers=None):
        values = {'Content-Type': 'application/json', 'X-Portal-Request': '1', 'X-CSRF-Token': self.csrf, 'Origin': self.base}
        values.update(headers or {})
        req = urllib.request.Request(self.base + '/api/' + route, None if data is None else json.dumps(data).encode(), values)
        try:
            response = self.opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        payload = json.loads(response.read())
        status, response_headers = response.status, response.headers
        response.close()
        if 'csrfToken' in payload:
            self.csrf = payload['csrfToken'] or ''
        if 'learning' in payload:
            self.run = payload['learning']['run']['id']
        return status, payload, response_headers

    def register(self, name='Sai Charan', email=None):
        self.email = email or f'{uuid.uuid4().hex}@shimentox.com'
        result=self.admin.request('admin/candidates',{'name':name,'email':self.email,'password':'Temporary123!','role':'candidate'})
        if result[0]!=200:return result
        login=self.request('auth/login',{'email':self.email,'password':'Temporary123!','remember':True})
        changed=self.request('auth/password',{'currentPassword':'Temporary123!','password':'Learning123!'})
        return 201,changed[1],login[2]

    def action(self, name, **data):
        return self.request('learning/' + name, {'runId': self.run, **data})


class PortalFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['LMS_QUIET'] = '1'
        cls.temp = tempfile.TemporaryDirectory(prefix='shimentox-tests-')
        cls.db_path = Path(cls.temp.name) / 'test.sqlite3'
        initialize(cls.db_path)
        cls.server = PortalServer(('127.0.0.1', 0), PortalHandler, cls.db_path)
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        with closing(connect(cls.db_path)) as db, db:
            identity=uid()
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES (?,?,?,?,?,?,'admin')",(identity,'Portal Admin','owner@shimentox.com',password_hash('AdminSetup123!'),now(),now()))
            create_run(db,identity)
        cls.admin=Client(cls.base)
        cls.admin.request('auth/login',{'email':'owner@shimentox.com','password':'AdminSetup123!'})
        Client.admin=cls.admin

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def candidate(self, name='Sai Charan'):
        client = Client(self.base)
        status, user, headers = client.register(name)
        self.assertEqual(status, 201, user)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', headers['Set-Cookie'])
        status, _, _ = client.request('learning')
        self.assertEqual(status, 200)
        return client

    def prepare(self, client, s):
        for i in CURRICULUM[s]['videos']:
            self.assertEqual(client.action('video', videoIndex=i, watched=48, complete=True)[0], 200)
        for e, exercise in enumerate(CURRICULUM[s]['exercises']):
            result = client.action('exercise', setIndex=s, exerciseIndex=e, answers=[q[2] for q in exercise['questions']])
            self.assertEqual(result[0], 200, result[1])
            self.assertEqual(result[1]['feedback']['score'], 2)

class PortalTests(PortalFixture):
    def test_registration_login_logout_and_password_hash(self):
        client = self.candidate()
        with closing(connect(self.db_path)) as db, db:
            row = db.execute('SELECT * FROM candidates WHERE email=?', (client.email,)).fetchone()
            self.assertTrue(row['password_hash'].startswith('scrypt$'))
            self.assertNotIn('Learning123!', row['password_hash'])
            token_row = db.execute('SELECT token_hash FROM sessions WHERE candidate_id=?', (row['id'],)).fetchone()
            self.assertEqual(len(token_row['token_hash']), 64)
        self.assertEqual(client.request('session')[1]['user']['name'], 'Sai Charan')
        self.assertEqual(client.request('auth/logout', {})[0], 200)
        self.assertIsNone(client.request('session')[1]['user'])
        self.assertEqual(client.request('learning')[0], 401)
        self.assertEqual(client.request('auth/login', {'email': client.email, 'password': 'wrong-password'})[0], 401)
        self.assertEqual(client.request('auth/login', {'email': client.email.upper(), 'password': 'Learning123!'})[0], 200)
        self.assertEqual(client.request('learning')[0], 200)

    def test_validation_csrf_and_static_boundaries(self):
        client = self.candidate()
        self.assertEqual(client.request('auth/register', {'name': 'New User', 'email': client.email, 'password': 'Learning123!'})[0], 403)
        self.assertEqual(Client(self.base).request('auth/register', {'name': 'A', 'email': 'invalid', 'password': '123'})[0], 403)
        self.assertEqual(client.request('auth/logout', {}, {'X-CSRF-Token': ''})[0], 403)
        self.assertEqual(client.request('auth/logout', {}, {'Origin': 'https://elsewhere.example'})[0], 403)
        self.assertEqual(Client(self.base).request('records')[0], 401)
        for asset in ('/', '/scripts/auth.js', '/scripts/app.js', '/scripts/learning.js', '/assets/videos/lesson-1.webm', '/styles/auth.css'):
            with urllib.request.urlopen(self.base + asset) as response:
                self.assertEqual(response.status, 200)
        for private in ('/backend/data/lms.sqlite3', '/backend/database/schema.sql', '/.openai/hosting.json'):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(self.base + private)
            raised.exception.close()

    def test_candidate_isolation_and_durable_progress(self):
        a, b = self.candidate('Candidate One'), self.candidate('Candidate Two')
        a.action('video', videoIndex=0, watched=22.5, complete=False)
        self.assertEqual(b.request('learning')[1]['learning']['run']['videos'], {})
        self.assertEqual(b.action('video', runId=a.run, videoIndex=0, watched=48, complete=True)[0], 409)
        a.request('auth/logout', {})
        fresh = Client(self.base)
        fresh.request('auth/login', {'email': a.email, 'password': 'Learning123!'})
        data = fresh.request('learning')[1]
        self.assertEqual(data['learning']['run']['videos']['0']['watched'], 22.5)
        self.assertFalse(data['learning']['run']['videos']['0']['complete'])
        # Re-running initialization is non-destructive.
        initialize(self.db_path)
        self.assertEqual(fresh.request('learning')[1]['learning']['run']['videos']['0']['watched'], 22.5)
        self.assertEqual(len(b.request('records')[1]['runs']), 1)

    def test_prerequisites_grading_and_attempt_limits(self):
        client = self.candidate()
        public = client.request('learning')[1]['course']
        self.assertTrue(all(len(q) == 2 for group in public for q in group['exam']))
        self.assertEqual(client.action('exam-start', setIndex=0)[0], 403)
        self.assertEqual(client.action('video', videoIndex=2, watched=48, complete=True)[0], 403)
        self.assertEqual(client.action('video', videoIndex=0, watched=1, complete=True)[1]['learning']['run']['videos']['0']['complete'], False)
        for _ in range(5):
            self.assertEqual(client.action('exercise', setIndex=0, exerciseIndex=0, answers=[1, 0])[1]['feedback']['score'], 0)
        self.prepare(client, 0)
        for number in range(1, 4):
            start = client.action('exam-start', setIndex=0)
            self.assertEqual(start[0], 200, start[1])
            attempt = start[1]['attempt']['id']
            self.assertEqual(start[1]['attempt']['attemptNumber'], number)
            self.assertEqual(client.action('exam-start', setIndex=0)[0], 409)
            result = client.action('exam-finish', attemptId=attempt, answers=[1, 0, 0, 0], score=4, status='passed')
            self.assertEqual(result[1]['attempt']['status'], 'failed')
            self.assertEqual(result[1]['attempt']['score'], 0)
            again = client.action('exam-finish', attemptId=attempt, answers=[0, 1, 2, 1])
            self.assertEqual(again[1]['attempt']['status'], 'failed')
        self.assertEqual(client.action('exam-start', setIndex=0)[0], 409)
        old_run = client.run
        self.assertEqual(client.action('restart')[0], 200)
        self.assertNotEqual(client.run, old_run)
        result = client.request('records')[1]
        self.assertEqual(len(result['exam_attempts']), 3)
        self.assertEqual(len(result['exercise_attempts']), 7)
        self.assertEqual(len(result['runs']), 2)

    def test_reload_timeout_and_attempt_ownership(self):
        client, other = self.candidate(), self.candidate()
        self.prepare(client, 0)
        start = client.action('exam-start', setIndex=0)[1]['attempt']
        self.assertEqual(other.action('exam-finish', attemptId=start['id'], terminate=True)[0], 404)
        resumed = client.action('resume')[1]['learning']['run']['attempts'][0]
        self.assertEqual(resumed[0]['status'], 'terminated')
        start = client.action('exam-start', setIndex=0)[1]['attempt']
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE exam_attempts SET deadline=? WHERE id=?', (time.time() - 1, start['id']))
        result = client.action('exam-finish', attemptId=start['id'], answers=[0, 1, 2, 1])
        self.assertEqual(result[1]['attempt']['status'], 'terminated')
        self.assertIn('Time expired', result[1]['attempt']['reason'])

    def test_full_course_certificate_restart_and_export(self):
        client = self.candidate()
        for s in range(3):
            self.prepare(client, s)
            attempt = client.action('exam-start', setIndex=s)[1]['attempt']
            answers = [q[2] for q in CURRICULUM[s]['exam']]
            answers[0] = (answers[0] + 1) % 3
            result = client.action('exam-finish', attemptId=attempt['id'], answers=answers)[1]
            self.assertEqual(result['attempt']['status'], 'passed')
            self.assertEqual(result['attempt']['score'], 3)
        award = result['learning']['certificates'][0]
        self.assertEqual(award['name'], 'Sai Charan')
        self.assertTrue(result['learning']['run']['completedAt'])
        client.action('restart')
        result = client.request('learning')[1]['learning']
        self.assertEqual(result['run']['runNumber'], 2)
        self.assertEqual(result['run']['videos'], {})
        self.assertEqual(result['certificates'][0], award)
        exported = client.request('records')[1]
        self.assertEqual(len(exported['video_progress']), 6)
        self.assertEqual(len(exported['exercise_attempts']), 6)
        self.assertEqual(len(exported['exam_attempts']), 3)
        self.assertEqual(len(exported['certificates']), 1)
        self.assertNotIn('password_hash', json.dumps(exported))

    def test_password_change_and_session_revocation(self):
        client = self.candidate()
        second = Client(self.base)
        second.request('auth/login', {'email': client.email, 'password': 'Learning123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'incorrect', 'password': 'Replacement123!'})[0], 400)
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Learning123!', 'password': 'Replacement123!'})[0], 200)
        self.assertEqual(second.request('learning')[0], 401)
        self.assertEqual(client.request('learning')[0], 200)
        client.request('auth/logout', {})
        self.assertEqual(client.request('auth/login', {'email': client.email, 'password': 'Learning123!'})[0], 401)
        self.assertEqual(client.request('auth/login', {'email': client.email, 'password': 'Replacement123!'})[0], 200)

    def test_concurrent_exam_starts_are_atomic(self):
        owner = self.candidate()
        self.prepare(owner, 0)
        cookies = '; '.join(f'{c.name}={c.value}' for c in owner.cookies)
        def start(_):
            client = Client(self.base)
            return client.request('learning/exam-start', {'runId': owner.run, 'setIndex': 0}, {'Cookie': cookies, 'X-CSRF-Token': owner.csrf})[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            statuses = list(pool.map(start, range(3)))
        self.assertEqual(sorted(statuses), [200, 409, 409])
        self.assertEqual(len(owner.request('learning')[1]['learning']['run']['attempts'][0]), 1)

    def test_expired_session_is_rejected(self):
        client = self.candidate()
        identity = client.request('session')[1]['user']['id']
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE sessions SET expires_at=0 WHERE candidate_id=?', (identity,))
        self.assertIsNone(client.request('session')[1]['user'])
        self.assertEqual(client.request('records')[0], 401)

    def test_login_rate_limit_is_persisted(self):
        client = self.candidate()
        with closing(connect(self.db_path)) as db, db:
            for _ in range(10):
                db.execute("INSERT INTO auth_events(email,event,ip_address,created_at,timestamp) VALUES (?,'login_failed','198.51.100.1','test',?)", (client.email, time.time()))
        result = client.request('auth/login', {'email': client.email, 'password': 'Learning123!'})
        self.assertEqual(result[0], 429)


if __name__ == '__main__':
    unittest.main()
