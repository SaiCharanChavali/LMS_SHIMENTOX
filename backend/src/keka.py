"""Keka integration: "Sign in with Keka account" and employee records synced from Keka.

Sign-in uses Keka as the OpenID Connect identity provider (authorization code flow). The LMS never sees Keka
passwords: Keka verifies the person, and the LMS reads who they are from Keka's userinfo endpoint. Employee
details (name, work email, job title, employee number, reporting manager, working or relieved) come from the
Keka HRIS API, so LMS records always carry the Keka details.

Configuration comes from environment variables, usually in backend/.env (never committed; see backend/.env.example):
  KEKA_COMPANY             your Keka subdomain: <company>.keka.com (required)
  KEKA_ENVIRONMENT         keka (default) or kekademo for Keka's sandbox
  KEKA_SSO_CLIENT_ID       SSO client ID from Keka Support (required for sign-in)
  KEKA_SSO_CLIENT_SECRET   SSO client secret, when Keka issues one
  KEKA_SSO_REDIRECT_URI    optional; defaults to <LMS_PUBLIC_BASE_URL>/api/auth/keka/callback
  KEKA_API_CLIENT_ID, KEKA_API_CLIENT_SECRET, KEKA_API_KEY   Keka HRIS API credentials (profiles and sync)
  KEKA_SSO_AUTHORITY, KEKA_API_BASE_URL   optional overrides of the Keka hosts (sandbox, proxies, tests)
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from admin import audit
from services import APIError, allowed, check, create_run, now, start_session, uid

# Keka-created accounts have no LMS password: this marker never matches any password, so they sign in only through Keka.
NO_PASSWORD = '!keka-sign-in-only'
WORKING, RELIEVED = 0, 1
_token_cache = {}
_token_lock = threading.Lock()


class SignInError(Exception):
    """A Keka sign-in that cannot continue. The code is shown on the login page as a fixed message."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def settings():
    env = lambda name, default='': os.environ.get(name, default).strip()
    company, environment = env('KEKA_COMPANY').lower(), env('KEKA_ENVIRONMENT', 'keka').lower()
    return {
        'company': company,
        'authority': env('KEKA_SSO_AUTHORITY').rstrip('/') or f'https://login.{environment}.com',
        'api_base': env('KEKA_API_BASE_URL').rstrip('/') or (f'https://{company}.{environment}.com/api/v1' if company else ''),
        'sso_client_id': env('KEKA_SSO_CLIENT_ID'), 'sso_client_secret': env('KEKA_SSO_CLIENT_SECRET'),
        'sso_scope': env('KEKA_SSO_SCOPE', 'openid'), 'redirect_uri': env('KEKA_SSO_REDIRECT_URI'),
        'api_client_id': env('KEKA_API_CLIENT_ID'), 'api_client_secret': env('KEKA_API_CLIENT_SECRET'), 'api_key': env('KEKA_API_KEY'),
        'api_grant_type': env('KEKA_API_GRANT_TYPE', 'kekaapi'),
    }


def sso_ready(config=None):
    config = config or settings()
    return bool(config['company'] and config['sso_client_id'])


def api_ready(config=None):
    config = config or settings()
    return bool(config['company'] and config['api_client_id'] and config['api_client_secret'] and config['api_key'])


# ---------------------------------------------------------------- HTTP

def _call(url, form=None, bearer=None):
    """GET (or POST a form) to Keka and return the JSON body. Any failure becomes SignInError('keka-unreachable')."""
    headers = {'Accept': 'application/json'}
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=20) as response:
            return json.loads(response.read() or b'{}')
    except (urllib.error.URLError, OSError, ValueError):
        raise SignInError('keka-unreachable')


def _api_token(config):
    """Access token for the Keka HRIS API (client credentials), reused until shortly before it expires."""
    key = (config['authority'], config['api_client_id'])
    with _token_lock:
        cached = _token_cache.get(key)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        result = _call(f"{config['authority']}/connect/token", {
            'grant_type': config['api_grant_type'], 'scope': 'kekaapi', 'client_id': config['api_client_id'],
            'client_secret': config['api_client_secret'], 'api_key': config['api_key']})
        access = result.get('access_token')
        if not access:
            raise SignInError('keka-unreachable')
        _token_cache[key] = (access, time.time() + float(result.get('expires_in') or 3600))
        return access


def employees(config=None, **filters):
    """Every Keka employee matching the filters, following Keka's pages (up to 200 per page)."""
    config = config or settings()
    found, page = [], 1
    while page <= 500:
        query = urllib.parse.urlencode({**filters, 'pageNumber': page, 'pageSize': 200})
        result = _call(f"{config['api_base']}/hris/employees?{query}", bearer=_api_token(config))
        found += [e for e in result.get('data') or [] if isinstance(e, dict)]
        if page >= int(result.get('totalPages') or 1) or not result.get('data'):
            return found
        page += 1
    return found


def find_employee(email, config=None):
    matches = [e for e in employees(config, searchKey=email) if (e.get('email') or '').strip().casefold() == email]
    return matches[0] if matches else None


# ---------------------------------------------------------------- Keka employee -> LMS account

def is_working(employee):
    status = employee.get('employmentStatus')
    return status == WORKING or str(status).strip().lower() == 'working'


def full_name(employee, email):
    name = (employee.get('displayName') or ' '.join(filter(None, [employee.get('firstName'), employee.get('lastName')])) or '').strip()
    if len(name) < 2:
        # Fall back to the work email: "sai.charan@company.com" becomes "Sai Charan".
        name = ' '.join(part.capitalize() for part in re.split(r'[._-]+', email.split('@')[0]) if part) or email
    return name[:100]


def job_title(employee):
    title = employee.get('jobTitle')
    return ((title.get('title') if isinstance(title, dict) else title) or '').strip()[:150]


def _account(db, keka_id='', email=''):
    if keka_id:
        row = db.execute('SELECT * FROM candidates WHERE keka_employee_id=?', (keka_id,)).fetchone()
        if row:
            return row
    return db.execute('SELECT * FROM candidates WHERE email=?', (email,)).fetchone() if email else None


def upsert_employee(db, employee, actor_id=None):
    """Create or update the LMS account for one Keka employee.
    Returns (account id, 'created' | 'updated' | 'deactivated' | 'skipped').

    The LMS record takes the Keka details; LMS role, learning history, targets and certificates are kept.
    Relieved employees are disabled, except administrators.
    """
    email = (employee.get('email') or '').strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return None, 'skipped'
    keka_id, stamp, working = str(employee.get('id') or ''), now(), is_working(employee)
    name, title, number = full_name(employee, email), job_title(employee), str(employee.get('employeeNumber') or '')[:60]
    row = _account(db, keka_id, email)
    if row is None:
        if not working:
            return None, 'skipped'
        identity = uid()
        db.execute('''INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role,must_change_password,created_by,job_title,
            auth_source,keka_employee_id,keka_employee_number,keka_synced_at) VALUES (?,?,?,?,?,?,'employee',0,?,?,'keka',?,?,?)''',
                   (identity, name, email, NO_PASSWORD, stamp, stamp, actor_id, title, keka_id, number, stamp))
        create_run(db, identity)
        status = 'created'
    else:
        identity, status = row['id'], 'updated'
        # Keep the email from Keka unless another LMS account already uses it.
        if email != row['email'] and db.execute('SELECT 1 FROM candidates WHERE email=? AND id<>?', (email, identity)).fetchone():
            email = row['email']
        active = row['is_active'] if working or row['role'] == 'admin' else 0
        db.execute('''UPDATE candidates SET full_name=?,email=?,job_title=?,auth_source='keka',keka_employee_id=?,keka_employee_number=?,keka_synced_at=?,
            is_active=?,updated_at=? WHERE id=?''', (name, email, title or row['job_title'], keka_id, number, stamp, active, stamp, identity))
        if not active:
            db.execute('DELETE FROM sessions WHERE candidate_id=?', (identity,))
            if row['is_active']:
                status = 'deactivated'
    _link_manager(db, identity, employee.get('reportsTo'))
    return identity, status


def _link_manager(db, identity, manager):
    """Point the account at its Keka reporting manager, and give that person the Manager role (employees only)."""
    if not isinstance(manager, dict):
        return
    row = _account(db, str(manager.get('id') or ''), (manager.get('email') or '').strip().casefold())
    if row is None or row['id'] == identity:
        return
    db.execute('UPDATE candidates SET manager_id=? WHERE id=?', (row['id'], identity))
    if row['role'] == 'employee':
        db.execute("UPDATE candidates SET role='manager',updated_at=? WHERE id=?", (now(), row['id']))


def sync_all(db, actor):
    """Bring every Keka employee into the LMS: create new accounts, update details, disable relieved employees."""
    check(allowed(actor, 'users.manage'), 'You do not have permission to sync employees from Keka.', 403)
    config = settings()
    check(api_ready(config), 'Keka is not connected yet. Add the Keka API settings on the server (see backend/.env.example).', 409)
    try:
        people = employees(config)  # Everything is fetched before anything is written.
    except SignInError:
        raise APIError(502, 'Keka could not be reached. Check the Keka API settings and try again.')
    counts = {'created': 0, 'updated': 0, 'skipped': 0, 'deactivated': 0}
    for employee in people:
        counts[upsert_employee(db, employee, actor['id'])[1]] += 1
    # Managers created later in the list are linked on this second pass.
    for employee in people:
        row = _account(db, str(employee.get('id') or ''), (employee.get('email') or '').strip().casefold())
        if row:
            _link_manager(db, row['id'], employee.get('reportsTo'))
    audit(db, actor['id'], 'keka_sync', '', f"{len(people)} Keka employees: {counts['created']} created, {counts['updated']} updated, {counts['deactivated']} relieved")
    return {'keka': {'employees': len(people), **counts}}


# ---------------------------------------------------------------- Sign in with Keka

def redirect_uri(base_url):
    return settings()['redirect_uri'] or f'{base_url}/api/auth/keka/callback'


def authorize_url(state, nonce, callback):
    config = settings()
    return f"{config['authority']}/connect/authorize?" + urllib.parse.urlencode({
        'response_type': 'code', 'client_id': config['sso_client_id'], 'redirect_uri': callback,
        'scope': config['sso_scope'], 'state': state, 'nonce': nonce})


def sign_in(db, code, ip, callback):
    """Finish a Keka sign-in: exchange the code, identify the person, sync their Keka details and start a session."""
    config = settings()
    if not sso_ready(config):
        raise SignInError('keka-not-configured')
    if not code:
        raise SignInError('keka-failed')
    form = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': callback, 'client_id': config['sso_client_id']}
    if config['sso_client_secret']:
        form['client_secret'] = config['sso_client_secret']
    access = _call(f"{config['authority']}/connect/token", form).get('access_token')
    if not access:
        raise SignInError('keka-failed')
    info = _call(f"{config['authority']}/connect/userinfo", bearer=access)
    # Only people from this company's Keka account may sign in.
    if (info.get('subdomain') or '').strip().lower() != config['company']:
        raise SignInError('keka-other-company')
    email = (info.get('email') or '').strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise SignInError('keka-failed')
    keka_user = str(info.get('sub') or info.get('user_id') or '')
    if api_ready(config):
        employee = find_employee(email, config)
        if employee is None:
            raise SignInError('keka-not-employee')
        if not is_working(employee):
            raise SignInError('keka-inactive')
        identity, _ = upsert_employee(db, employee)
    else:
        # Without API access the LMS knows only the Keka email: an existing account is linked, or a new one is created.
        row = db.execute('SELECT * FROM candidates WHERE keka_user_id=? AND keka_user_id<>?', (keka_user, '')).fetchone() or _account(db, '', email)
        identity = row['id'] if row else None
        if identity is None:
            identity, stamp = uid(), now()
            db.execute('''INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role,must_change_password,auth_source,keka_synced_at)
                VALUES (?,?,?,?,?,?,'employee',0,'keka',?)''', (identity, full_name({}, email), email, NO_PASSWORD, stamp, stamp, stamp))
            create_run(db, identity)
    db.execute('UPDATE candidates SET keka_user_id=? WHERE id=?', (keka_user, identity))
    row = db.execute('SELECT * FROM candidates WHERE id=?', (identity,)).fetchone()
    if not row['is_active']:
        raise SignInError('keka-inactive')
    return start_session(db, row, ip)
