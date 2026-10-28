# ShimentoX LMS

The catalog also includes **Java Full Stack Development**: 30 structured modules,
local guided labs, 90 knowledge-check questions and ten secured assignments.
See the [Java course guide](docs/java-full-stack-course.md) for the learning sequence.

The catalog includes **Python Programming Senior**: 18 original Python lessons
with an in-browser Python editor, coding workshops, labs, knowledge checks and six
required timed assignments (one after every three modules). See the
[Python learning path](docs/python-learning-path.md) for scope and regeneration.

The catalog includes **POSH**: six text lessons on the Sexual Harassment of Women
at Workplace (Prevention, Prohibition and Redressal) Act, 2013, each with a knowledge
check, plus a 10-question final assessment. It is based on the
[ISTM PoSH guidebook](https://www.istm.gov.in/home/posh_act).

ShimentoX's internal employee learning & development portal. It brings together course and training management, assignments and mandatory deadlines, learning paths, skills and competencies, assessments with question banks, instructor-led sessions, notifications, certificates, and learning analytics. Accounts and progress are stored in SQLite. See [learning & development](docs/learning-and-development.md) for roles, metric definitions, and the API.

## Run locally

From the project directory:

```powershell
cd C:\Users\DELL\Desktop\shimento_LMS\shimentox-lms
npm start
```

`npm start` opens **http://localhost:5173** in your default browser automatically once the server is ready. Stop the server with **Ctrl+C**. Use `npm run start:server` to start without opening a browser.

Without npm, run `python backend/server.py` from this directory. The same server serves both the frontend and the API. Stop any previous static server on port 5173 before starting it. Opening the HTML directly or using a static-only server will not provide login or database access.

If `backend/data/admin-seed.json` is present, a new database starts with that administrator, so a fresh clone opens on the login page. Create or refresh it with `python backend/tools/export_admin.py`, which saves the local admin's name, email and salted password hash (never the password). Otherwise, if no administrator exists, the browser opens a one-time **Set up your admin account** form automatically. Enter your full name, email, and password there. If the email already has an account, enter its current password to preserve and promote it. Setup is available only on the local server computer and closes permanently once an admin exists. No terminal account-creation command is required.

Roles are **Administrator, HR / L&D Admin, Trainer, Manager, and Employee**. Employees see **My Dashboard, My Learning, Learning Paths, Skills & Goals, Training Calendar, My Certificates, and My Profile**. Administrators see **Dashboard, Manage Courses, Learning Paths, Skills & Competencies, Users & Teams, Assessments, Training Calendar, Certificates, Reports & Analytics, Activity Log, and My Profile**. HR, trainers and managers see their own learning plus the management pages their role allows. Backend permissions protect every API, not just sidebar visibility.

In **Users & Teams**, an admin or HR assigns a full name, work email, role, department, job role, manager, and temporary password. Share those credentials with the employee. Public registration is disabled. First sign-in requires a different personal password before accessing courses or records. Admins can reset temporary passwords, disable/enable access, and review learning history. **My profile** supports later password changes.

In **Manage courses**, create a draft, enter metadata, edit the curriculum JSON template, then publish. Each course has three sets, two videos and exercises per set, and one exam per set. Only published courses appear for candidates. Each course has independent progress and attempts. Create a new version to change assessments after learners have enrolled. See [admin guide](docs/admin-guide.md).

The optional AI learning assistant is off unless configured on the server; see [AI assistant](docs/ai-assistant.md). No other environment variables are required.

SQLite is created automatically at `backend/data/lms.sqlite3`. Schema version 3 upgrades existing databases automatically, keeping all accounts and learning records; former candidate accounts become employees. Uploaded learning materials are stored privately in `backend/data/materials/`, which is excluded from version control; back it up together with the database. No database installation or npm dependency installation is needed. Back up this file to retain candidate data. Use `npm run db:init` to initialize the schema without starting the server.

## Project layout

```text
shimentox-lms/
├── frontend/
│   ├── public/                  # Browser-served frontend; no build step
│   │   ├── index.html           # Portal entry page
│   │   ├── styles/
│   │   │   ├── main.css         # Shared layout and responsive styles
│   │   │   ├── branding.css     # Logo and company colors
│   │   │   ├── certificate.css  # Certificate and PDF print styles
│   │   │   ├── learning.css     # Course, exercise, and exam styles
│   │   │   └── auth.css         # Login, registration, and account styles
│   │   ├── scripts/
│   │   │   ├── auth.js          # Assigned login, first-password setup, and API client
│   │   │   ├── admin.js         # Role-based navigation and management pages
│   │   │   ├── app.js           # Shared UI and routing
│   │   │   └── learning.js      # Course content and learning workflow
│   │   └── assets/
│   │       ├── images/          # Browser-ready company logo
│   │       └── videos/          # Six videos and English caption files
│   ├── tests/
│   │   ├── check.cjs            # Direct test entry point
│   │   └── learning.test.cjs    # Workflow and asset checks
│   ├── tools/
│   │   └── generate_videos.py   # Development-only video generation
│   └── README.md
├── backend/
│   ├── server.py               # Start frontend + API on the same origin
│   ├── src/                    # HTTP routes, services, database, security
│   ├── database/schema.sql     # Tables, relationships, constraints, indexes
│   ├── data/                   # Private curriculum and ignored SQLite file
│   ├── tests/                  # Real HTTP and SQLite integration tests
│   └── README.md               # API and configuration documentation
├── docs/
│   ├── learning-workflow.md    # Course rules, behavior, and limitations
│   └── branding/               # Original supplied company logo
├── .openai/
│   └── hosting.json            # Static hosting serves frontend/public
├── .gitignore
├── package.json               # Start, test, and syntax-check commands
└── README.md
```

## Checks

Performance measurements and algorithm changes are documented in [performance notes](docs/performance.md). Run `npm run benchmark` for an isolated synthetic benchmark that does not touch candidate records.

```powershell
npm test
npm run check
```

No npm packages need to be installed. Running the server needs Python; running checks needs Node.js. Video regeneration additionally needs the Python packages and Windows fonts listed in the workflow documentation.

## Candidate data and backend

SQLite records candidate roles, mandatory password changes, hashed sessions, account activity, administrator actions, course content, all learning runs, video progress, exercise submissions, exams, and certificates. Exam scoring and certificate eligibility are enforced on the server. Schema version 2 upgrades existing version 1 databases automatically without deleting progress or promoting accounts.

Passwords are salted and hashed with scrypt. Sessions use HttpOnly cookies; writes require a session-specific CSRF token. Every learning query is scoped to the candidate in that session. Shared prototype localStorage records are not imported because their candidate ownership cannot be established.

This is a local server intended for development and evaluation. Production requires a supported HTTP server, HTTPS, persistent database storage/backups, and an email verification/recovery process. SQLite must live on persistent storage; static-only hosting does not run this backend. See [backend documentation](backend/README.md), [database schema](docs/database-schema.md), and [course workflow](docs/learning-workflow.md).



Admin Username: Admin   
Admin Password: Admin123
Admin Email   : Admin@shimento.com
