# Frontend

`public/` contains all browser assets. There is no frontend build step or npm dependency installation; the Python backend serves this folder and the authenticated JSON API on the same origin.

- `public/index.html`: entry page; loads shared scripts before the learning workflow.
- `public/styles/`: shared, branding, certificate, and course styles.
- `public/scripts/`: `auth.js` handles sessions, assigned-credential login and first-password setup, API calls, and account controls; `app.js` renders shared UI and routing; `learning.js` renders the course workflow. `admin.js` supplies role-based navigation, admin management pages, and course catalogs. Load auth, app, admin, and learning scripts in that order.
- `public/assets/images/`: company logo used throughout the UI and certificates.
- `public/assets/videos/`: local WebM video lessons with matching VTT captions.
- `tests/`: simulated browser workflow checks, run with `npm test` at project root.
- `tools/`: development utilities, excluded from the browser's served directory.

Run `npm start` from the project root and open http://localhost:5173. Opening HTML directly or using a static-only server cannot authenticate or save progress. The backend serves `public/` as the browser root; database, answer keys, test files, and development tools remain outside that root. The frontend does not use localStorage for candidate records or session secrets.
