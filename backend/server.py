"""Start the local ShimentoX frontend and SQLite API on one origin."""
import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from database import BACKEND, initialize, seed_admin
from server import PortalServer, PortalHandler


def main():
    parser = argparse.ArgumentParser(description='ShimentoX LMS server')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '5173')))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--init-db', action='store_true')
    parser.add_argument('--open', action='store_true', help='Open the portal in the default browser after startup')
    args = parser.parse_args()
    path = Path(os.environ.get('LMS_DB_PATH', str(BACKEND / 'data/lms.sqlite3'))).resolve()
    initialize(path)
    seed_admin(path)
    if args.init_db:
        print(f'SQLite schema initialized: {path}')
        return
    try:
        server = PortalServer((args.host, args.port), PortalHandler, path)
    except OSError:
        print(f'Port {args.port} is already in use, probably by an earlier ShimentoX server that is still running.\n'
              f'Stop it (Ctrl+C in its terminal, or end the python.exe process) and run npm start again, or choose another port with --port.', file=sys.stderr, flush=True)
        sys.exit(1)
    browser_host = 'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host
    url = f'http://{browser_host}:{server.server_port}'
    print(f'ShimentoX LMS: {url}', flush=True)
    print(f'SQLite database: {path}', flush=True)
    if args.open:
        # The database and listening socket are ready; browser launch cannot block HTTP serving.
        def open_browser():
            try:
                if webbrowser.open(url, new=2):
                    return
            except OSError:
                pass
            print(f'Could not open the browser automatically. Open {url}', flush=True)
        threading.Thread(target=open_browser, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
