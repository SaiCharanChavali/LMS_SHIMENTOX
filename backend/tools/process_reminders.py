"""Run one deadline reminder pass from the command line or an operating-system scheduler.

Local access to the database file is the authentication here: the command opens no network port.

    python backend/tools/process_reminders.py             Send everything that is due now
    python backend/tools/process_reminders.py --dry-run   List what is due, without sending
    python backend/tools/process_reminders.py --dry-run --now 2026-11-08T12:30:00Z   ...as of another time

Uses LMS_DB_PATH when set, otherwise backend/data/lms.sqlite3. Safe to run repeatedly or alongside the server.
The exit code is 1 when a reminder or an employee failed; failed reminders are retried on later passes.
"""
import argparse
import json
import os
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import BACKEND, SCHEMA_VERSION, connect, initialize
from deadlines import parse_utc
import reminders


def main():
    parser = argparse.ArgumentParser(description='Process ShimentoX course deadline reminders once.')
    parser.add_argument('--dry-run', action='store_true', help='List what is due without sending or recording anything')
    parser.add_argument('--now', help='With --dry-run: evaluate at this ISO timestamp instead of the current time')
    args = parser.parse_args()
    if args.now and not args.dry_run:
        parser.error('--now requires --dry-run, because real reminders must use the real time.')
    path = Path(os.environ.get('LMS_DB_PATH', str(BACKEND / 'data/lms.sqlite3'))).resolve()
    if not path.is_file():
        parser.error(f'Database not found: {path}')
    with closing(connect(path)) as db:
        current = db.execute('PRAGMA user_version').fetchone()[0]
    if current != SCHEMA_VERSION:
        initialize(path)
    if args.dry_run:
        at = parse_utc(args.now) if args.now else None
        print(json.dumps({'due': reminders.preview(path, at)}, indent=2))
        return 0
    summary = reminders.run_pass(path)
    print(json.dumps(summary))
    return 1 if summary['failed'] or summary['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
