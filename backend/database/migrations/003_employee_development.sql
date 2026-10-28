-- Version 2 -> 3: employee roles and organisation fields, course training metadata.
-- Existing accounts keep their passwords and history; former candidate accounts become employees.
-- New tables are created afterwards by schema.sql (CREATE TABLE IF NOT EXISTS).
PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;
CREATE TABLE candidates_v3 (
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
INSERT INTO candidates_v3(id,full_name,email,password_hash,created_at,updated_at,last_login_at,role,must_change_password,is_active,created_by)
SELECT id,full_name,email,password_hash,created_at,updated_at,last_login_at,CASE WHEN role='admin' THEN 'admin' ELSE 'employee' END,must_change_password,is_active,created_by FROM candidates;
DROP TABLE candidates;
ALTER TABLE candidates_v3 RENAME TO candidates;
ALTER TABLE courses ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'beginner' CHECK(difficulty IN ('beginner','intermediate','advanced','expert'));
ALTER TABLE courses ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK(duration_minutes BETWEEN 0 AND 100000);
ALTER TABLE courses ADD COLUMN department_id TEXT REFERENCES departments(id) ON DELETE SET NULL;
ALTER TABLE courses ADD COLUMN trainer_id TEXT REFERENCES candidates(id) ON DELETE SET NULL;
ALTER TABLE courses ADD COLUMN pass_percent INTEGER NOT NULL DEFAULT 75 CHECK(pass_percent BETWEEN 25 AND 100);
ALTER TABLE courses ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 3);
ALTER TABLE courses ADD COLUMN post_assessment_id TEXT;
PRAGMA user_version=3;
COMMIT;
PRAGMA foreign_keys=ON;
