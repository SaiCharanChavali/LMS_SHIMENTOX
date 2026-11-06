"""Keka integration: "Sign in with Keka account" and employee sync, against a local fake of Keka's endpoints."""
from contextlib import closing
import http.client
import json
import os
import threading
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from test_portal import PortalFixture  # Puts backend/src on the import path.
import keka
from database import connect

COMPANY = 'shimentox'
EMPLOYEES = [
    {'id': 'k-mgr', 'employeeNumber': 'EMP002', 'displayName': 'Mani Iyer', 'email': 'mani@shimentox.com', 'jobTitle': {'title': 'Engineering Manager'}, 'employmentStatus': 0},
    {'id': 'k-asha', 'employeeNumber': 'EMP001', 'displayName': 'Asha Rao', 'email': 'Asha@ShimentoX.com', 'jobTitle': {'title': 'Software Engineer'},
     'employmentStatus': 0, 'reportsTo': {'id': 'k-mgr', 'firstName': 'Mani', 'lastName': 'Iyer', 'email': 'mani@shimentox.com'}},
    {'id': 'k-priya', 'employeeNumber': 'EMP003', 'firstName': 'Priya', 'lastName': 'Nair', 'email': 'priya@shimentox.com', 'jobTitle': {'title': 'Analyst'}, 'employmentStatus': 0,
     'reportsTo': {'id': 'k-mgr', 'email': 'mani@shimentox.com'}},
    {'id': 'k-ravi', 'employeeNumber': 'EMP004', 'displayName': 'Ravi Kumar', 'email': 'ravi@shimentox.com', 'jobTitle': {'title': 'Tester'}, 'employmentStatus': 1},
]
# Authorization codes Keka would issue after sign-in: code -> (email, Keka subdomain).
CODES = {'asha-code': ('asha@shimentox.com', COMPANY), 'ravi-code': ('ravi@shimentox.com', COMPANY),
         'stranger-code': ('stranger@shimentox.com', COMPANY), 'other-code': ('asha@shimentox.com', 'othercorp')}


class FakeKeka(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode()).items()}
        if self.path != '/connect/token':
            return self.reply(404, {})
        if form.get('grant_type') == 'kekaapi' and form.get('api_key') == 'api-key' and form.get('scope') == 'kekaapi':
            return self.reply(200, {'access_token': 'api-token', 'expires_in': 3600})
        if form.get('grant_type') == 'authorization_code' and form.get('client_id') == 'lms-client' and form.get('code') in CODES:
            return self.reply(200, {'access_token': 'sso:' + form['code'], 'id_token': 'x'})
        self.reply(400, {'error': 'invalid_grant'})

    def do_GET(self):
        url, auth = urlsplit(self.path), self.headers.get('Authorization', '')
        if url.path == '/connect/userinfo' and auth.startswith('Bearer sso:'):
            email, subdomain = CODES[auth.removeprefix('Bearer sso:')]
            return self.reply(200, {'sub': 'user-' + email, 'email': email, 'subdomain': subdomain})
        if url.path == '/api/v1/hris/employees' and auth == 'Bearer api-token':
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            rows = [e for e in EMPLOYEES if query.get('searchKey', '').casefold() in e['email'].casefold()]
            size, page = int(query.get('pageSize', 100)), int(query.get('pageNumber', 1))
            # Two employees per page, to exercise paging.
            size = min(size, 2)
            return self.reply(200, {'succeeded': True, 'data': rows[(page - 1) * size:page * size], 'pageNumber': page, 'totalPages': max(1, -(-len(rows) // size))})
        self.reply(401, {})


class KekaFixture(PortalFixture):
    """A portal plus a fake Keka; each test class gets its own database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.keka_server = ThreadingHTTPServer(('127.0.0.1', 0), FakeKeka)
        threading.Thread(target=cls.keka_server.serve_forever, daemon=True).start()
        cls.keka_url = f'http://127.0.0.1:{cls.keka_server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.keka_server.shutdown()
        cls.keka_server.server_close()
        super().tearDownClass()

    def setUp(self):
        keka._token_cache.clear()
        self.env = mock.patch.dict(os.environ, {
            'KEKA_COMPANY': COMPANY, 'KEKA_SSO_CLIENT_ID': 'lms-client', 'KEKA_SSO_AUTHORITY': self.keka_url,
            'KEKA_API_BASE_URL': self.keka_url + '/api/v1', 'KEKA_API_CLIENT_ID': 'api-client', 'KEKA_API_CLIENT_SECRET': 'api-secret', 'KEKA_API_KEY': 'api-key'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def get(self, path, cookie=''):
        host = urlsplit(self.base).netloc
        conn = http.client.HTTPConnection(host, timeout=20)
        conn.request('GET', path, headers={'Cookie': cookie} if cookie else {})
        response = conn.getresponse()
        response.read()
        cookies = SimpleCookie()
        for header in response.headers.get_all('Set-Cookie') or []:
            cookies.load(header)
        conn.close()
        return response.status, response.headers.get('Location', ''), {k: v.value for k, v in cookies.items()}

    def sign_in(self, code):
        """Leave for Keka, then come back with the code Keka issued."""
        status, location, cookies = self.get('/api/auth/keka/start')
        self.assertEqual(status, 302)
        state = parse_qs(urlsplit(location).query)['state'][0]
        return self.get(f'/api/auth/keka/callback?code={code}&state={state}', f'shimentox_keka={cookies["shimentox_keka"]}')

    def session(self, cookie):
        host = urlsplit(self.base).netloc
        conn = http.client.HTTPConnection(host, timeout=20)
        conn.request('GET', '/api/session', headers={'Cookie': f'shimentox_session={cookie}'})
        payload = json.loads(conn.getresponse().read())
        conn.close()
        return payload



class KekaSignInTests(KekaFixture):
    def test_login_page_option_redirects_to_keka(self):
        status, location, cookies = self.get('/api/auth/keka/start')
        self.assertEqual(status, 302)
        target = urlsplit(location)
        query = {k: v[0] for k, v in parse_qs(target.query).items()}
        self.assertEqual(f'{target.scheme}://{target.netloc}{target.path}', self.keka_url + '/connect/authorize')
        self.assertEqual((query['response_type'], query['client_id'], query['scope']), ('code', 'lms-client', 'openid'))
        self.assertEqual(query['redirect_uri'], self.base + '/api/auth/keka/callback')
        self.assertEqual(cookies['shimentox_keka'], query['state'], 'The state is remembered to check the return trip.')
        self.assertTrue(self.session('')['kekaSignIn'])

    def test_keka_sign_in_creates_the_account_from_keka_details(self):
        status, location, cookies = self.sign_in('asha-code')
        self.assertEqual((status, location), (302, '/'))
        user = self.session(cookies['shimentox_session'])['user']
        self.assertEqual((user['name'], user['email'], user['jobTitle'], user['source'], user['kekaEmployeeNumber'], user['role'], user['mustChangePassword']),
                         ('Asha Rao', 'asha@shimentox.com', 'Software Engineer', 'keka', 'EMP001', 'employee', False))
        # Keka accounts have no LMS password: they always sign in through Keka.
        self.assertEqual(self.admin.__class__(self.base).request('auth/login', {'email': 'asha@shimentox.com', 'password': 'anything'})[0], 401)
        # Signing in again uses the same LMS account and record.
        again = self.session(self.sign_in('asha-code')[2]['shimentox_session'])['user']
        self.assertEqual(again['id'], user['id'])
        listed = next(u for u in self.admin.request('admin/candidates')[1]['candidates'] if u['email'] == 'asha@shimentox.com')
        self.assertEqual((listed['source'], listed['kekaEmployeeNumber']), ('keka', 'EMP001'))

    def test_problems_return_to_the_login_page_with_a_message(self):
        for code, error in (('other-code', 'keka-other-company'), ('ravi-code', 'keka-inactive'), ('stranger-code', 'keka-not-employee'), ('bad-code', 'keka-unreachable')):
            status, location, cookies = self.sign_in(code)
            self.assertEqual((status, location), (302, f'/?signin_error={error}'), code)
            self.assertNotIn('shimentox_session', cookies)
        # A return trip without the matching state is refused.
        status, location, _ = self.get('/api/auth/keka/callback?code=asha-code&state=forged', 'shimentox_keka=real')
        self.assertEqual(location, '/?signin_error=keka-expired')
        self.assertEqual(self.get('/api/auth/keka/callback?error=access_denied&state=x', 'shimentox_keka=x')[1], '/?signin_error=keka-cancelled')
        with closing(connect(self.db_path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM candidates WHERE email IN ('ravi@shimentox.com','stranger@shimentox.com')").fetchone())

    def test_not_configured(self):
        with mock.patch.dict(os.environ, {'KEKA_SSO_CLIENT_ID': ''}):
            self.assertEqual(self.get('/api/auth/keka/start')[1], '/?signin_error=keka-not-configured')
            self.assertFalse(self.session('')['kekaSignIn'])
            with mock.patch.dict(os.environ, {'KEKA_API_KEY': ''}):
                self.assertEqual(self.admin.request('manage/keka/sync', {})[0], 409)



class KekaSyncTests(KekaFixture):
    def test_sync_brings_in_keka_employees_and_keeps_existing_records(self):
        # Priya already has an LMS account with learning history: sync links it instead of creating a duplicate.
        email = 'priya@shimentox.com'
        created = self.admin.request('admin/candidates', {'name': 'Priya (old)', 'email': email, 'password': 'Temporary123!', 'role': 'employee'})
        self.assertEqual(created[0], 200, created[1])
        priya = created[1]['candidate']['id']
        result = self.admin.request('manage/keka/sync', {})
        self.assertEqual(result[0], 200, result[1])
        counts = result[1]['keka']
        self.assertEqual((counts['employees'], counts['skipped']), (4, 1), 'Relieved employees without an account are not created.')
        with closing(connect(self.db_path)) as db:
            rows = {r['email']: r for r in db.execute("SELECT * FROM candidates WHERE email LIKE '%@shimentox.com' AND email<>'owner@shimentox.com'")}
            self.assertEqual(rows[email]['id'], priya)
            self.assertEqual((rows[email]['full_name'], rows[email]['job_title'], rows[email]['keka_employee_number'], rows[email]['auth_source']), ('Priya Nair', 'Analyst', 'EMP003', 'keka'))
            self.assertEqual(rows['mani@shimentox.com']['role'], 'manager', 'Keka reporting managers get the Manager View.')
            self.assertEqual({rows['asha@shimentox.com']['manager_id'], rows[email]['manager_id']}, {rows['mani@shimentox.com']['id']})
            self.assertNotIn('ravi@shimentox.com', rows)
        # Running it again changes nothing new.
        self.assertEqual(self.admin.request('manage/keka/sync', {})[1]['keka']['created'], 0)
        # Employees cannot run a sync.
        employee = self.admin.__class__(self.base)
        address = f'{uuid.uuid4().hex}@x.com'
        self.admin.request('admin/candidates', {'name': 'Plain', 'email': address, 'password': 'Temporary123!', 'role': 'employee'})
        employee.request('auth/login', {'email': address, 'password': 'Temporary123!'})
        employee.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})
        self.assertEqual(employee.request('manage/keka/sync', {})[0], 403)



class KekaRelievedTests(KekaFixture):
    def test_relieved_in_keka_disables_the_lms_account(self):
        with closing(connect(self.db_path)) as db, db:
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES ('ravi','Ravi Kumar','ravi@shimentox.com','x','t','t','employee')")
        self.assertEqual(self.admin.request('manage/keka/sync', {})[1]['keka']['deactivated'], 1)
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT is_active FROM candidates WHERE id='ravi'").fetchone()[0], 0)
