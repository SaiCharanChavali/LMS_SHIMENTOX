"""Public certificate rendering against a temporary SQLite backup only."""
from contextlib import closing
from html import escape
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import BACKEND, initialize
from server import PortalHandler, PortalServer


class PublicCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['LMS_QUIET'] = '1'
        cls.temp = tempfile.TemporaryDirectory(prefix='certificate-copy-')
        cls.path = Path(cls.temp.name) / 'copy.sqlite3'
        source = BACKEND / 'data/lms.sqlite3'
        if source.exists():
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(cls.path)) as copy:
                original.backup(copy)
        initialize(cls.path)
        cls.token = 'public_test_' + 'a' * 40
        cls.name = '<img src=x onerror=alert(1)> & "Learner"'
        cls.course = '<script>alert(2)</script> & Course'
        # Synthetic foreign keys keep this fixture independent of copied personal records.
        with closing(sqlite3.connect(cls.path)) as db, db:
            db.execute('INSERT INTO certificates(id,run_id,candidate_name,course_title,issued_at,certificate_number,public_token) VALUES(?,?,?,?,?,?,?)',
                       ('private-test-id', 'private-run-id', cls.name, cls.course, '2026-11-12T20:00:00Z', 'SX-TEST-<&"', cls.token))
        cls.server = PortalServer(('127.0.0.1', 0), PortalHandler, cls.path)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def test_public_design_privacy_metadata_and_revocation(self):
        url = self.base + '/certificates/' + self.token
        with urllib.request.urlopen(url) as response:
            body = response.read().decode()
            self.assertIn('noindex', response.headers['X-Robots-Tag'])
        for fragment in ('/styles/certificate.css', 'ShimentoX-Light-Logo.webp', 'certificate-header',
                         'Certificate of Completion', 'certificate-seal', 'certificate-note',
                         '>Valid</p>', '13 November 2026', 'name="viewport"', 'property="og:title"',
                         'property="og:description"', 'property="og:url"', 'property="og:image"',
                         escape(self.name, quote=True), escape(self.course, quote=True), escape('SX-TEST-<&"', quote=True)):
            self.assertIn(fragment, body)
        for fragment in ('<script', '<button', 'private-test-id', 'private-run-id', 'email', 'Print', 'Login', self.name, self.course):
            self.assertNotIn(fragment, body)
        for asset in ('/styles/certificate.css', '/assets/images/ShimentoX-Light-Logo.webp'):
            with urllib.request.urlopen(self.base + asset) as response:
                self.assertEqual(response.status, 200)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE certificates SET revoked_at=? WHERE public_token=?', ('2026-11-13T01:00:00Z', self.token))
        with urllib.request.urlopen(url) as response:
            revoked = response.read().decode()
            self.assertIn('certificate-status revoked">Revoked</p>', revoked)
            self.assertNotIn('>Valid</p>', revoked)
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD')) as response:
            self.assertEqual(response.read(), b'')
            self.assertIn('noindex', response.headers['X-Robots-Tag'])
