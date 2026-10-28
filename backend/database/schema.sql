PRAGMA foreign_keys = ON;

-- The accounts table keeps its historical name (candidates); every account is a ShimentoX employee.
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 2 AND 80),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 2 AND 80),
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL CHECK(length(full_name) BETWEEN 2 AND 100),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT,
    role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('admin','hr','trainer','manager','employee')),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0,1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_by TEXT REFERENCES candidates(id),
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    job_role_id TEXT REFERENCES job_roles(id) ON DELETE SET NULL,
    manager_id TEXT REFERENCES candidates(id) ON DELETE SET NULL,
    job_title TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_candidate ON sessions(candidate_id);
CREATE TABLE IF NOT EXISTS auth_events (
    id INTEGER PRIMARY KEY,
    candidate_id TEXT REFERENCES candidates(id) ON DELETE SET NULL,
    email TEXT NOT NULL,
    event TEXT NOT NULL CHECK(event IN ('registered','login','login_failed','logout','password_changed')),
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_events_rate ON auth_events(event, timestamp, ip_address, email);
CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'Development',
    status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('draft','published','archived')),
    lessons_json TEXT NOT NULL DEFAULT '[]',
    sets_json TEXT NOT NULL DEFAULT '[]',
    created_by TEXT REFERENCES candidates(id),
    updated_at TEXT,
    difficulty TEXT NOT NULL DEFAULT 'beginner' CHECK(difficulty IN ('beginner','intermediate','advanced','expert')),
    duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK(duration_minutes BETWEEN 0 AND 100000),
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    trainer_id TEXT REFERENCES candidates(id) ON DELETE SET NULL,
    pass_percent INTEGER NOT NULL DEFAULT 75 CHECK(pass_percent BETWEEN 25 AND 100),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 3),
    post_assessment_id TEXT,
    format TEXT NOT NULL DEFAULT 'modules' CHECK(format IN ('modules','lessons')),
    visibility TEXT NOT NULL DEFAULT 'everyone' CHECK(visibility IN ('everyone','department')),
    page_layout TEXT NOT NULL DEFAULT 'standard' CHECK(page_layout IN ('standard','article')),
    -- Set for courses imported from a URL: normalised original address, platform name, outcome and per-lesson report.
    source_url TEXT NOT NULL DEFAULT '',
    source_platform TEXT NOT NULL DEFAULT '',
    import_status TEXT NOT NULL DEFAULT '' CHECK(import_status IN ('','complete','partial','reference')),
    import_report_json TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS course_sets (
    course_id TEXT NOT NULL REFERENCES courses(id),
    set_index INTEGER NOT NULL CHECK(set_index BETWEEN 0 AND 2),
    title TEXT NOT NULL,
    PRIMARY KEY(course_id, set_index)
);
CREATE TABLE IF NOT EXISTS videos (
    course_id TEXT NOT NULL REFERENCES courses(id),
    video_index INTEGER NOT NULL CHECK(video_index BETWEEN 0 AND 5),
    set_index INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    PRIMARY KEY(course_id, video_index),
    FOREIGN KEY(course_id, set_index) REFERENCES course_sets(course_id, set_index)
);
CREATE TABLE IF NOT EXISTS assessment_questions (
    course_id TEXT NOT NULL,
    set_index INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('exercise','exam')),
    exercise_index INTEGER NOT NULL CHECK(exercise_index BETWEEN -1 AND 1),
    question_index INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_option INTEGER NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(course_id,set_index,kind,exercise_index,question_index),
    FOREIGN KEY(course_id,set_index) REFERENCES course_sets(course_id,set_index)
);
CREATE TABLE IF NOT EXISTS course_runs (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    course_id TEXT NOT NULL REFERENCES courses(id),
    run_number INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    archived_at TEXT,
    last_lesson_id TEXT,
    UNIQUE(candidate_id,course_id,run_number)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_current_run ON course_runs(candidate_id,course_id) WHERE archived_at IS NULL;
CREATE TABLE IF NOT EXISTS video_progress (
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    video_index INTEGER NOT NULL CHECK(video_index BETWEEN 0 AND 5),
    watched_seconds REAL NOT NULL DEFAULT 0 CHECK(watched_seconds>=0),
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(run_id,video_index)
);
CREATE TABLE IF NOT EXISTS exercise_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    set_index INTEGER NOT NULL CHECK(set_index BETWEEN 0 AND 2),
    exercise_index INTEGER NOT NULL CHECK(exercise_index BETWEEN 0 AND 1),
    answers_json TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 2),
    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
    submitted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS exercise_attempts_run ON exercise_attempts(run_id,set_index,exercise_index);
CREATE TABLE IF NOT EXISTS exam_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    set_index INTEGER NOT NULL CHECK(set_index BETWEEN 0 AND 2),
    attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
    status TEXT NOT NULL CHECK(status IN ('in-progress','passed','failed','terminated')),
    started_at TEXT NOT NULL,
    deadline REAL NOT NULL,
    finished_at TEXT,
    score INTEGER CHECK(score BETWEEN 0 AND 4),
    answers_json TEXT,
    reason TEXT,
    UNIQUE(run_id,set_index,attempt_number)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_exam ON exam_attempts(run_id) WHERE status='in-progress';
-- Required assignments between groups of native lessons. Answer keys stay on the server.
CREATE TABLE IF NOT EXISTS course_checkpoints (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id),
    after_lesson INTEGER NOT NULL CHECK(after_lesson > 0),
    title TEXT NOT NULL,
    instructions TEXT NOT NULL,
    lesson_ids_json TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    pass_percent INTEGER NOT NULL DEFAULT 75 CHECK(pass_percent BETWEEN 1 AND 100),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 3),
    time_limit_seconds INTEGER NOT NULL DEFAULT 600 CHECK(time_limit_seconds BETWEEN 60 AND 14400),
    UNIQUE(course_id,after_lesson)
);
CREATE TABLE IF NOT EXISTS checkpoint_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    checkpoint_id TEXT NOT NULL REFERENCES course_checkpoints(id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
    status TEXT NOT NULL CHECK(status IN ('in-progress','passed','failed','terminated')),
    started_at TEXT NOT NULL,
    deadline REAL NOT NULL,
    finished_at TEXT,
    score INTEGER,
    total INTEGER NOT NULL,
    questions_json TEXT NOT NULL,
    answers_json TEXT,
    reason TEXT,
    UNIQUE(run_id,checkpoint_id,attempt_number)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_checkpoint ON checkpoint_attempts(run_id) WHERE status='in-progress';
CREATE TABLE IF NOT EXISTS course_content_updates (
    course_id TEXT NOT NULL REFERENCES courses(id),
    revision TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    PRIMARY KEY(course_id,revision)
);
CREATE TABLE IF NOT EXISTS lesson_code_drafts (
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    lesson_id TEXT NOT NULL REFERENCES course_lessons(id),
    code TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(run_id,lesson_id)
);
CREATE TABLE IF NOT EXISTS lesson_quiz_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    lesson_id TEXT NOT NULL REFERENCES course_lessons(id),
    answers_json TEXT NOT NULL,
    score INTEGER NOT NULL,
    submitted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES course_runs(id),
    candidate_name TEXT NOT NULL,
    course_title TEXT NOT NULL,
    issued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_events (
    id INTEGER PRIMARY KEY,
    admin_id TEXT NOT NULL REFERENCES candidates(id),
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS course_categories (
    name TEXT PRIMARY KEY COLLATE NOCASE CHECK(length(name) BETWEEN 2 AND 80),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 2 AND 80),
    category TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS course_skills (
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 4),
    PRIMARY KEY(course_id, skill_id)
);
CREATE TABLE IF NOT EXISTS role_competencies (
    job_role_id TEXT NOT NULL REFERENCES job_roles(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    target_level INTEGER NOT NULL CHECK(target_level BETWEEN 1 AND 4),
    updated_by TEXT REFERENCES candidates(id),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(job_role_id, skill_id)
);
-- Skill levels come only from passed skill assessments or manager-recorded evidence, never from course completion.
CREATE TABLE IF NOT EXISTS skill_evidence (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 4),
    source TEXT NOT NULL CHECK(source IN ('assessment','manager')),
    reference_id TEXT,
    note TEXT NOT NULL DEFAULT '',
    recorded_by TEXT REFERENCES candidates(id),
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS skill_evidence_employee ON skill_evidence(employee_id, skill_id);
CREATE TABLE IF NOT EXISTS learning_goals (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    skill_id TEXT REFERENCES skills(id) ON DELETE SET NULL,
    target_level INTEGER CHECK(target_level BETWEEN 1 AND 4),
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS learning_goals_employee ON learning_goals(employee_id);
CREATE TABLE IF NOT EXISTS course_assignments (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK(target_type IN ('employee','department','job_role')),
    target_id TEXT NOT NULL,
    mandatory INTEGER NOT NULL DEFAULT 0 CHECK(mandatory IN (0,1)),
    due_date TEXT,
    note TEXT NOT NULL DEFAULT '',
    assigned_by TEXT REFERENCES candidates(id),
    assigned_at TEXT NOT NULL,
    UNIQUE(course_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS course_assignments_target ON course_assignments(target_type, target_id);
CREATE TABLE IF NOT EXISTS learning_paths (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
    sequential INTEGER NOT NULL DEFAULT 1 CHECK(sequential IN (0,1)),
    created_by TEXT REFERENCES candidates(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_path_courses (
    path_id TEXT NOT NULL REFERENCES learning_paths(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK(position >= 0),
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    PRIMARY KEY(path_id, position),
    UNIQUE(path_id, course_id)
);
CREATE TABLE IF NOT EXISTS path_assignments (
    id TEXT PRIMARY KEY,
    path_id TEXT NOT NULL REFERENCES learning_paths(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK(target_type IN ('employee','department','job_role')),
    target_id TEXT NOT NULL,
    due_date TEXT,
    assigned_by TEXT REFERENCES candidates(id),
    assigned_at TEXT NOT NULL,
    UNIQUE(path_id, target_type, target_id)
);
CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    description TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK(kind IN ('pre','post','knowledge','skill')),
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    skill_id TEXT REFERENCES skills(id) ON DELETE SET NULL,
    skill_level INTEGER CHECK(skill_level BETWEEN 1 AND 4),
    pass_percent INTEGER NOT NULL DEFAULT 70 CHECK(pass_percent BETWEEN 1 AND 100),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 3),
    question_count INTEGER NOT NULL CHECK(question_count BETWEEN 1 AND 100),
    time_limit_minutes INTEGER NOT NULL DEFAULT 15 CHECK(time_limit_minutes BETWEEN 1 AND 240),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
    created_by TEXT REFERENCES candidates(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assessment_bank (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_option INTEGER NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS assessment_bank_assessment ON assessment_bank(assessment_id, position);
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    employee_id TEXT NOT NULL REFERENCES candidates(id),
    attempt_number INTEGER NOT NULL,
    question_ids_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('in-progress','passed','failed','expired','terminated')),
    started_at TEXT NOT NULL,
    deadline REAL NOT NULL,
    finished_at TEXT,
    score INTEGER,
    total INTEGER NOT NULL,
    percent INTEGER,
    answers_json TEXT,
    option_orders_json TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    UNIQUE(assessment_id, employee_id, attempt_number)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_assessment ON assessment_attempts(assessment_id, employee_id) WHERE status='in-progress';
CREATE INDEX IF NOT EXISTS assessment_attempts_employee ON assessment_attempts(employee_id);
CREATE TABLE IF NOT EXISTS training_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    description TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'session' CHECK(kind IN ('session','workshop')),
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    trainer_id TEXT REFERENCES candidates(id) ON DELETE SET NULL,
    location TEXT NOT NULL DEFAULT '',
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 10000),
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','cancelled')),
    created_by TEXT REFERENCES candidates(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_registrations (
    session_id TEXT NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('registered','cancelled','attended')),
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(session_id, employee_id)
);
-- dedupe_key prevents the same reminder or result notice being stored twice for an employee.
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT,
    UNIQUE(employee_id, dedupe_key)
);
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    uploaded_by TEXT REFERENCES candidates(id),
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS course_resources (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    module_index INTEGER CHECK(module_index BETWEEN 0 AND 2),
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    kind TEXT NOT NULL CHECK(kind IN ('document','presentation','video','link')),
    url TEXT NOT NULL,
    created_by TEXT REFERENCES candidates(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS development_records (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    provider TEXT NOT NULL DEFAULT '',
    completed_on TEXT NOT NULL,
    hours REAL NOT NULL DEFAULT 0 CHECK(hours BETWEEN 0 AND 1000),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_usage (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL
);
-- Lesson-based courses (format='lessons'): any number of ordered lessons built in Manage Courses.
CREATE TABLE IF NOT EXISTS course_lessons (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK(position >= 0),
    title TEXT NOT NULL CHECK(length(title) BETWEEN 2 AND 150),
    description TEXT NOT NULL DEFAULT '',
    video_url TEXT NOT NULL DEFAULT '',
    document_url TEXT NOT NULL DEFAULT '',
    document_name TEXT NOT NULL DEFAULT '',
    resources_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '',
    exercise TEXT NOT NULL DEFAULT '',
    duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK(duration_minutes BETWEEN 0 AND 1000),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    captions_url TEXT NOT NULL DEFAULT '',
    video_seconds REAL NOT NULL DEFAULT 0 CHECK(video_seconds BETWEEN 0 AND 36000),
    completion_percent INTEGER NOT NULL DEFAULT 90 CHECK(completion_percent BETWEEN 50 AND 100),
    activity_json TEXT NOT NULL DEFAULT '',
    assessment_id TEXT REFERENCES assessments(id) ON DELETE SET NULL,
    -- Imported courses: the original module a lesson belongs to (lessons with the same index form one module) and its source page.
    module_index INTEGER CHECK(module_index IS NULL OR module_index >= 0),
    module_title TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS course_lessons_course ON course_lessons(course_id, position);
-- One row per completed lesson in a course run (the run identifies the employee and course).
CREATE TABLE IF NOT EXISTS lesson_progress (
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    lesson_id TEXT NOT NULL REFERENCES course_lessons(id),
    completed_at TEXT NOT NULL,
    response TEXT NOT NULL DEFAULT '',
    score INTEGER CHECK(score BETWEEN 0 AND 100),
    PRIMARY KEY(run_id, lesson_id)
);
-- Video resume position and verified watch time per lesson and course run.
CREATE TABLE IF NOT EXISTS lesson_watch (
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    lesson_id TEXT NOT NULL REFERENCES course_lessons(id),
    position_seconds REAL NOT NULL DEFAULT 0 CHECK(position_seconds >= 0),
    watched_seconds REAL NOT NULL DEFAULT 0 CHECK(watched_seconds >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(run_id, lesson_id)
);
-- Every interactive-exercise submission with its rubric score.
CREATE TABLE IF NOT EXISTS lesson_activity_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES course_runs(id),
    lesson_id TEXT NOT NULL REFERENCES course_lessons(id),
    answers_json TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
    submitted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lesson_activity_attempts_run ON lesson_activity_attempts(run_id, lesson_id);
PRAGMA user_version = 6;
-- Courses removed in Manage Courses; packaged courses listed here are not re-created at startup.
CREATE TABLE IF NOT EXISTS deleted_courses (
    course_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    deleted_by TEXT,
    deleted_at TEXT NOT NULL
);
