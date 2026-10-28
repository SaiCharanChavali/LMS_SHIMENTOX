BEGIN IMMEDIATE;
ALTER TABLE candidates ADD COLUMN role TEXT NOT NULL DEFAULT 'candidate' CHECK(role IN ('admin','candidate'));
ALTER TABLE candidates ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0,1));
ALTER TABLE candidates ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1));
ALTER TABLE candidates ADD COLUMN created_by TEXT REFERENCES candidates(id);
ALTER TABLE courses ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE courses ADD COLUMN category TEXT NOT NULL DEFAULT 'Development';
ALTER TABLE courses ADD COLUMN status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('draft','published','archived'));
ALTER TABLE courses ADD COLUMN lessons_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE courses ADD COLUMN sets_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE courses ADD COLUMN created_by TEXT REFERENCES candidates(id);
ALTER TABLE courses ADD COLUMN updated_at TEXT;
ALTER TABLE video_progress RENAME TO video_progress_v1;
CREATE TABLE video_progress (
 run_id TEXT NOT NULL REFERENCES course_runs(id), video_index INTEGER NOT NULL CHECK(video_index BETWEEN 0 AND 5),
 watched_seconds REAL NOT NULL DEFAULT 0 CHECK(watched_seconds>=0), completed_at TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(run_id,video_index)
);
INSERT INTO video_progress SELECT * FROM video_progress_v1;
DROP TABLE video_progress_v1;
CREATE TABLE admin_events (
 id INTEGER PRIMARY KEY, admin_id TEXT NOT NULL REFERENCES candidates(id), action TEXT NOT NULL,
 target_id TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
PRAGMA user_version=2;
COMMIT;
