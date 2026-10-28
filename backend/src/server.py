"""Same-origin JSON endpoints and static frontend serving (local development)."""
import hmac
import json
import os
import re
import sqlite3
import time
import ipaddress
import socket
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs

from database import BACKEND, connect, public_curriculum
from security import token_hash, password_hash, verify_password
from services import APIError, can_view_course, authenticate, auth_event, bundle, candidate_view, candidate_certificates, check, current_run, create_run, expire_exams, learning_action, records, text, now
from admin import admin_action, course_view, setup_initial_admin
from development import MAX_MATERIAL_BYTES, catalog, course_video, course_extras, development_action, material_file, store_material
import assistant

PUBLIC = BACKEND.parent / 'frontend/public'
COOKIE = 'shimentox_session'
# Reported by /api/session so the browser can detect a server still running older code.
API_VERSION = 9


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second server bind an occupied port, and requests keep reaching the
    # old process. Claim the port exclusively there so a duplicate start fails instead.
    allow_reuse_address = os.name != 'nt'

    def __init__(self, address, handler, db_path):
        self.db_path = db_path
        super().__init__(address, handler)

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class PortalHandler(SimpleHTTPRequestHandler):
    server_version = 'ShimentoX'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def end_headers(self):
        request_path = urlsplit(self.path).path
        sandbox = request_path == '/python-sandbox.html'
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN' if sandbox else 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        if sandbox:
            host = self.headers.get('Host', 'localhost:5173')
            host = host if re.fullmatch(r'[a-zA-Z0-9.\-\[\]:]+', host) else 'localhost:5173'
            runtime = f'http://{host}/assets/python-runtime/ https://{host}/assets/python-runtime/'
            self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'self' {runtime} 'wasm-unsafe-eval'; worker-src blob:; connect-src {runtime}; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox allow-scripts")
        else:
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; media-src 'self' https:; frame-src 'self' https://www.youtube-nocookie.com https://player.vimeo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if request_path.startswith('/assets/python-runtime/'):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=86400')
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def log_message(self, fmt, *args):
        # Do not log request bodies, passwords, cookies, or tokens.
        if os.environ.get('LMS_QUIET') != '1':
            super().log_message(fmt, *args)

    def json_response(self, status, payload, cookie=None):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        if cookie is not None:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(data)

    def cookie_value(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            return cookies[COOKIE].value if COOKIE in cookies else ''
        except Exception:
            return ''

    def session(self, db):
        raw = self.cookie_value()
        if not raw:
            return None
        return db.execute('SELECT c.*,s.csrf_token,s.token_hash FROM sessions s JOIN candidates c ON c.id=s.candidate_id WHERE s.token_hash=? AND s.expires_at>? AND c.is_active=1', (token_hash(raw), time.time())).fetchone()

    def session_cookie(self, raw, lifetime):
        secure = '; Secure' if os.environ.get('LMS_COOKIE_SECURE') == '1' else ''
        return f'{COOKIE}={raw}; Path=/; HttpOnly; SameSite=Lax; Max-Age={lifetime}{secure}'

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/'):
            return self.api('GET', path)
        resolved = (PUBLIC / unquote(path).lstrip('/')).resolve()
        if not resolved.is_relative_to(PUBLIC.resolve()) or any(part.startswith('.') for part in Path(unquote(path)).parts):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        self.api('POST', urlsplit(self.path).path)

    def do_HEAD(self):
        if urlsplit(self.path).path.startswith('/api/'):
            self.send_response(405)
            self.end_headers()
        else:
            super().do_HEAD()

    def file_response(self, file_path, content_type, name):
        """Stream a protected file, honouring a single HTTP byte range so browsers can seek in video."""
        size = file_path.stat().st_size
        start, end, status = 0, size - 1, 200
        requested = self.headers.get('Range', '')
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested.strip())
        if requested:
            if not match or (not match.group(1) and not match.group(2)):
                status = 416
            elif match.group(1):
                start, end = int(match.group(1)), min(int(match.group(2)) if match.group(2) else size - 1, size - 1)
                status = 206 if start <= end and start < size else 416
            else:
                start, status = max(0, size - int(match.group(2))), 206
        safe = ''.join(c for c in name if c.isalnum() or c in ' ._-')[:150] or 'material'
        if status == 416:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Disposition', f'inline; filename="{safe}"')
        self.end_headers()
        with open(file_path, 'rb') as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def api(self, method, path):
        db = connect(self.server.db_path)
        try:
            data = {}
            upload = None
            if method == 'POST':
                check(self.headers.get('X-Portal-Request') == '1', 'Invalid request origin.', 403)
                check(self.headers.get('Sec-Fetch-Site', 'same-origin') in ('same-origin', 'none'), 'Cross-site requests are not allowed.', 403)
                origin = self.headers.get('Origin')
                host = self.headers.get('Host', '')
                if origin:
                    parsed = urlsplit(origin)
                    check(parsed.netloc == host and parsed.scheme in ('http', 'https'), 'Invalid request origin.', 403)
                if path == '/api/manage/materials':
                    # Learning materials are uploaded as a raw body; the file name travels URL-encoded in a header.
                    check(self.headers.get('Content-Type', '').split(';')[0] == 'application/octet-stream', 'Upload the file as binary content.', 415)
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                    except ValueError:
                        length = 0
                    check(0 < length <= MAX_MATERIAL_BYTES, 'Files must be between 1 byte and 50 MB.', 413)
                    upload = (unquote(self.headers.get('X-File-Name', '')), self.rfile.read(length))
                else:
                    check(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'JSON content is required.', 415)
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                        check(0 < length <= 65536, 'Invalid request size.', 413)
                        data = json.loads(self.rfile.read(length))
                        check(isinstance(data, dict), 'A JSON object is required.')
                    except (ValueError, UnicodeError):
                        raise APIError(400, 'Invalid JSON request.')
                # A course import preview spends up to ~75 seconds on outbound requests and only reads the
                # database, so it must not hold the write lock that every other POST takes.
                if path != '/api/manage/import/preview':
                    db.execute('BEGIN IMMEDIATE')
            user = self.session(db)
            query = parse_qs(urlsplit(self.path).query)
            if method == 'GET' and path == '/api/session':
                payload = {'user': candidate_view(user) if user else None, 'csrfToken': user['csrf_token'] if user else None,'setupRequired':db.execute("SELECT 1 FROM candidates WHERE role='admin'").fetchone() is None,'setupAllowed':ipaddress.ip_address(self.client_address[0]).is_loopback,'apiVersion':API_VERSION}
            elif method=='POST' and path=='/api/setup/admin':
                check(ipaddress.ip_address(self.client_address[0]).is_loopback,'Initial setup must be completed on the server computer.',403)
                check(urlsplit('http://'+self.headers.get('Host','')).hostname in ('localhost','127.0.0.1','::1'),'Open the local portal address to complete setup.',403)
                setup_initial_admin(db,data)
                payload,raw,lifetime=authenticate(db,data,self.client_address[0])
                db.commit()
                return self.json_response(201,payload,self.session_cookie(raw,lifetime))
            elif method == 'POST' and path in ('/api/auth/login', '/api/auth/register'):
                payload, raw, lifetime = authenticate(db, data, self.client_address[0], path.endswith('register'))
                if user:
                    db.execute('DELETE FROM sessions WHERE token_hash=?', (user['token_hash'],))
                db.commit()
                return self.json_response(201 if path.endswith('register') else 200, payload, self.session_cookie(raw, lifetime))
            else:
                check(user is not None, 'Please sign in to continue.', 401)
                if method == 'POST':
                    check(hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), user['csrf_token']), 'Your session could not be verified. Reload and try again.', 403)
                candidate = user['id']
                check(not user['must_change_password'] or path in ('/api/auth/password','/api/auth/logout'), 'Change your temporary password before accessing the portal.',403)
                if path.startswith('/api/admin/'):
                    # Each admin route checks its own permission (admin, HR, trainer, or manager scope).
                    check(user['role']!='employee','Administrator access is required.',403)
                    payload=admin_action(db,user,method,path.removeprefix('/api/admin/'),data)
                    db.commit()
                    return self.json_response(200,payload)
                if upload is not None:
                    payload=store_material(db,user,*upload)
                    db.commit()
                    return self.json_response(200,payload)
                if method=='GET' and path.startswith('/api/videos/'):
                    return self.file_response(*course_video(db,user,path.removeprefix('/')))
                if method=='GET' and path.startswith('/api/materials/'):
                    return self.file_response(*material_file(db,user,path.removeprefix('/api/materials/')))
                if path=='/api/me/assistant':
                    payload=assistant.status() if method=='GET' else assistant.ask(db,user,data)
                    db.commit()
                    return self.json_response(200,payload)
                if path.startswith('/api/manage/') or path.startswith('/api/me/'):
                    payload=development_action(db,user,method,path.removeprefix('/api/'),query,data)
                    db.commit()
                    return self.json_response(200,payload)
                if method == 'POST' and path == '/api/auth/logout':
                    for run in db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND archived_at IS NULL',(candidate,)).fetchall():
                        expire_exams(db, run['id'], 'You signed out during the exam.')
                    db.execute('DELETE FROM sessions WHERE token_hash=?', (user['token_hash'],))
                    auth_event(db, candidate, user['email'], 'logout', self.client_address[0])
                    db.commit()
                    return self.json_response(200, {'ok': True}, self.session_cookie('', 0))
                if method == 'POST' and path == '/api/auth/password':
                    previous, replacement = text(data, 'currentPassword', 1, 128), text(data, 'password', 8, 128)
                    check(verify_password(previous, user['password_hash']), 'Current password is incorrect.', 400)
                    check(previous!=replacement,'Choose a new password different from the temporary or current password.')
                    db.execute('UPDATE candidates SET password_hash=?,updated_at=?,must_change_password=0 WHERE id=?', (password_hash(replacement), now(), candidate))
                    db.execute('DELETE FROM sessions WHERE candidate_id=? AND token_hash<>?', (candidate, user['token_hash']))
                    auth_event(db, candidate, user['email'], 'password_changed', self.client_address[0])
                    from services import notify
                    notify(db, [candidate], 'account', 'Password changed successfully', 'Your account password has been updated.', 'account', f'password:{now()}')
                    payload = {'ok': True,'user':candidate_view(db.execute('SELECT * FROM candidates WHERE id=?',(candidate,)).fetchone())}
                elif method=='GET' and path=='/api/courses':
                    payload={'courses':catalog(db,user)}
                elif method=='POST' and path=='/api/learning/enroll':
                    identity=text(data,'courseId',1,100)
                    course=db.execute("SELECT * FROM courses WHERE id=? AND status='published'",(identity,)).fetchone()
                    check(course is not None,'This course is not published or is unavailable.',404)
                    run=db.execute('SELECT id FROM course_runs WHERE candidate_id=? AND course_id=? AND archived_at IS NULL',(candidate,identity)).fetchone()
                    # Department-only courses: employees who already started keep access if visibility later changes.
                    check(run is not None or can_view_course(db,user,course),'This course is not published or is unavailable.',404)
                    if not run:create_run(db,candidate,identity)
                    payload={'learning':bundle(db,candidate,identity)}
                elif method == 'GET' and path == '/api/learning':
                    identity=parse_qs(urlsplit(self.path).query).get('courseId',['python-programming'])[0]
                    course=db.execute("SELECT * FROM courses WHERE id=? AND status='published'",(identity,)).fetchone()
                    check(course is not None,'This course is unavailable.',404)
                    check(can_view_course(db,user,course) or db.execute('SELECT 1 FROM course_runs WHERE candidate_id=? AND course_id=?',(candidate,identity)).fetchone() is not None,'This course is unavailable.',404)
                    payload = {'learning': bundle(db, candidate,identity), 'course': public_curriculum(db,identity),'lessons':json.loads(course['lessons_json']),'courseInfo':course_view(course,False,db),**course_extras(db,user,identity)}
                elif method == 'GET' and path == '/api/records':
                    payload = {'user': candidate_view(user), **records(db, candidate)}
                elif method=='GET' and path=='/api/certificates':
                    payload={'certificates':candidate_certificates(db,candidate)}
                elif method == 'POST' and path.startswith('/api/learning/'):
                    payload = learning_action(db, candidate, path.removeprefix('/api/learning/'), data)
                else:
                    raise APIError(404, f'Endpoint was not found: {method} {path}')
            db.commit()
            self.json_response(200, payload)
        except APIError as error:
            db.rollback()
            self.json_response(error.status, {'error': error.message})
        except sqlite3.IntegrityError:
            db.rollback()
            self.json_response(409, {'error': 'This record already exists or changed. Reload and try again.'})
        except (BrokenPipeError, ConnectionResetError):
            db.rollback()
        except Exception as error:
            db.rollback()
            self.log_error('Internal error: %s', type(error).__name__)
            self.json_response(500, {'error': 'The server could not complete your request. Please try again.'})
        finally:
            db.close()
