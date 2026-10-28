"""Save the local administrator to backend/data/admin-seed.json so fresh clones start with that admin.

Only the salted password hash is written, never the password. Usage: python backend/tools/export_admin.py [email]
"""
import json
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import ADMIN_SEED, BACKEND, connect


def main():
    with closing(connect(BACKEND / 'data/lms.sqlite3')) as db:
        query = "SELECT id,full_name,email,password_hash FROM candidates WHERE role='admin' AND is_active=1"
        rows = db.execute(query + (' AND email=?' if len(sys.argv) > 1 else '') + ' ORDER BY created_at', tuple(a.casefold() for a in sys.argv[1:2])).fetchall()
    if not rows:
        sys.exit('No active administrator found in backend/data/lms.sqlite3.')
    admin = rows[0]
    ADMIN_SEED.write_text(json.dumps({'id': admin['id'], 'name': admin['full_name'], 'email': admin['email'], 'passwordHash': admin['password_hash']}, indent=2) + '\n', encoding='utf-8')
    print(f'Saved administrator {admin["email"]} to {ADMIN_SEED}')


if __name__ == '__main__':
    main()
