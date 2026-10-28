"""SQLite schema initialization, curriculum seed, and transactional connections."""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
COURSE_ID = 'python-programming'
# Columns added after a table first shipped (versions 4-6); added only where missing.
ADDED_COLUMNS = [
    ('courses', 'format', "TEXT NOT NULL DEFAULT 'modules' CHECK(format IN ('modules','lessons'))"),
    ('courses', 'visibility', "TEXT NOT NULL DEFAULT 'everyone' CHECK(visibility IN ('everyone','department'))"),
    ('assessment_bank', 'code', "TEXT NOT NULL DEFAULT ''"),
    ('course_lessons', 'captions_url', "TEXT NOT NULL DEFAULT ''"),
    ('course_lessons', 'video_seconds', "REAL NOT NULL DEFAULT 0 CHECK(video_seconds BETWEEN 0 AND 36000)"),
    ('course_lessons', 'completion_percent', "INTEGER NOT NULL DEFAULT 90 CHECK(completion_percent BETWEEN 50 AND 100)"),
    ('course_lessons', 'activity_json', "TEXT NOT NULL DEFAULT ''"),
    ('lesson_progress', 'score', "INTEGER CHECK(score BETWEEN 0 AND 100)"),
    # Version 6: lesson knowledge checks, resume-at-last-lesson, and shuffled answer positions per attempt.
    ('course_lessons', 'assessment_id', "TEXT REFERENCES assessments(id) ON DELETE SET NULL"),
    ('course_runs', 'last_lesson_id', "TEXT"),
    ('assessment_attempts', 'option_orders_json', "TEXT NOT NULL DEFAULT ''"),
    # Interactive Python path: in-browser coding practice and per-module quizzes.
    ('course_lessons', 'practice_json', "TEXT NOT NULL DEFAULT ''"),
    ('course_lessons', 'quiz_json', "TEXT NOT NULL DEFAULT ''"),
    # Article-style lesson page (section navigation on the left) for packaged reading courses such as RAG.
    ('courses', 'page_layout', "TEXT NOT NULL DEFAULT 'standard' CHECK(page_layout IN ('standard','article'))"),
    # Courses imported from a URL: original source and attribution, import outcome, and each lesson's original module.
    ('courses', 'source_url', "TEXT NOT NULL DEFAULT ''"),
    ('courses', 'source_platform', "TEXT NOT NULL DEFAULT ''"),
    ('courses', 'import_status', "TEXT NOT NULL DEFAULT '' CHECK(import_status IN ('','complete','partial','reference'))"),
    ('courses', 'import_report_json', "TEXT NOT NULL DEFAULT ''"),
    ('course_lessons', 'module_index', "INTEGER CHECK(module_index IS NULL OR module_index >= 0)"),
    ('course_lessons', 'module_title', "TEXT NOT NULL DEFAULT ''"),
    ('course_lessons', 'source_url', "TEXT NOT NULL DEFAULT ''"),
]
GENAI_COURSE = BACKEND / 'data/generative-ai-course.json'
RAG_COURSE = BACKEND / 'data/rag-course.json'
POSH_COURSE = BACKEND / 'data/posh-course.json'
ADMIN_SEED = BACKEND / 'data/admin-seed.json'
# Exam security rule for every scored attempt: no more than three attempts (module exams, assignments, knowledge checks and assessments).
MAX_EXAM_ATTEMPTS = 3
PYTHON_PATH = BACKEND / 'data/shimento-python-course.json'
JAVA_PATH = BACKEND / 'data/java-full-stack-course.json'
VIDEO_ROOT = BACKEND / 'videos'
DEFAULT_DEPARTMENTS =['Engineering', 'Human Resources', 'Sales', 'Marketing', 'Finance']
DEFAULT_CATEGORIES = ['Technical Skills', 'Generative AI & Automation', 'Data Analytics', 'Communication & Presentation', 'Leadership & Management', 'Cybersecurity Awareness', 'Policies & Compliance', 'Professional Development']
CURRICULUM = json.loads((BACKEND / 'data/python-course.json').read_text(encoding='utf-8'))
LESSONS = json.loads((BACKEND / 'data/python-lessons.json').read_text(encoding='utf-8'))


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    return db


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2, 3, 4, 5, 6):
            raise RuntimeError('Unsupported database schema version')
        if version == 1:
            db.executescript((BACKEND / 'database/migrations/002_roles_and_courses.sql').read_text(encoding='utf-8'))
        if version in (1, 2):
            db.executescript((BACKEND / 'database/migrations/003_employee_development.sql').read_text(encoding='utf-8'))
        db.executescript((BACKEND / 'database/schema.sql').read_text(encoding='utf-8'))
        upgrade_assessment_attempts(db)
        # Fresh and upgraded databases converge on the same columns without losing rows.
        for table, column, definition in ADDED_COLUMNS:
            if column not in {r[1] for r in db.execute(f'PRAGMA table_info({table})')}:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        # Indexes on columns added by migration 003 are created here so the base schema stays valid for older tables.
        db.executescript('CREATE INDEX IF NOT EXISTS candidates_department ON candidates(department_id);CREATE INDEX IF NOT EXISTS candidates_manager ON candidates(manager_id);CREATE INDEX IF NOT EXISTS course_runs_course ON course_runs(course_id);CREATE INDEX IF NOT EXISTS courses_source ON courses(source_url) WHERE length(source_url)>0;')
        stamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        # Configurable defaults are seeded once, only into empty tables, so admin deletions are respected.
        if db.execute('SELECT 1 FROM departments').fetchone() is None:
            for name in DEFAULT_DEPARTMENTS:
                db.execute('INSERT INTO departments VALUES (?,?,?)', (str(uuid.uuid4()), name, stamp))
        db.execute('INSERT OR IGNORE INTO courses(id,title,version) VALUES (?,?,?)', (COURSE_ID, 'PYTHON PROGRAMMING', 1))
        if db.execute('SELECT 1 FROM course_categories').fetchone() is None:
            for name in DEFAULT_CATEGORIES + [r[0] for r in db.execute('SELECT DISTINCT category FROM courses')]:
                db.execute('INSERT OR IGNORE INTO course_categories VALUES (?,?)', (name, stamp))
        db.execute("UPDATE courses SET lessons_json=?,sets_json=?,description='Build a strong foundation in Python, one lesson at a time.' WHERE id=? AND lessons_json='[]'", (json.dumps(LESSONS),json.dumps(CURRICULUM),COURSE_ID))
        for s, item in enumerate(CURRICULUM):
            db.execute('INSERT OR IGNORE INTO course_sets VALUES (?,?,?)', (COURSE_ID, s, item['title']))
            for video in item['videos']:
                db.execute('INSERT OR IGNORE INTO videos VALUES (?,?,?,48)', (COURSE_ID, video, s))
            groups = [('exam', -1, item['exam'])] + [('exercise', e, exercise['questions']) for e, exercise in enumerate(item['exercises'])]
            for kind, exercise, questions in groups:
                for i, q in enumerate(questions):
                    db.execute('INSERT OR IGNORE INTO assessment_questions VALUES (?,?,?,?,?,?,?,?,?)',
                               (COURSE_ID, s, kind, exercise, i, q[0], json.dumps(q[1]), q[2], q[3] if len(q) > 3 else ''))
        seed_lesson_course(db, GENAI_COURSE, stamp)
        seed_lesson_course(db, RAG_COURSE, stamp)
        seed_lesson_course(db, POSH_COURSE, stamp)
        seed_lesson_course(db, PYTHON_PATH, stamp)
        # Rename the packaged course in existing installs without changing its ID or learner history.
        db.execute('UPDATE courses SET title=? WHERE id=? AND title=?',
                   ('Python Programming Senior', 'shimento-python-developer', 'Python Developer — Shimento'))
        seed_checkpoints(db, PYTHON_PATH)
        upgrade_python_interactive(db, PYTHON_PATH, stamp)
        upgrade_python_lessons(db, PYTHON_PATH, stamp)
        seed_lesson_course(db, JAVA_PATH, stamp)
        # Retire the earlier Java modules before seeding, so the new assessments can take their positions.
        restructure_java_course(db, JAVA_PATH, stamp)
        seed_checkpoints(db, JAVA_PATH)
        # Assessments saved before the three-attempt rule keep their history but allow no more than three attempts.
        db.execute('UPDATE assessments SET max_attempts=? WHERE max_attempts>?', (MAX_EXAM_ATTEMPTS, MAX_EXAM_ATTEMPTS))
        db.commit()
    finally:
        db.close()


def upgrade_assessment_attempts(db):
    """Allow 'terminated' assessment attempts (left full screen, switched tabs, navigated away) with the reason they ended.

    SQLite cannot change a CHECK constraint in place, so an older table is rebuilt once with every row kept.
    """
    sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='assessment_attempts'").fetchone()[0]
    if "'terminated'" in sql:
        return
    # SQLite's documented table rebuild: foreign keys are paused so existing history is copied exactly as stored.
    db.executescript('''
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE assessment_attempts_upgraded (
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
        INSERT INTO assessment_attempts_upgraded(id,assessment_id,employee_id,attempt_number,question_ids_json,status,started_at,deadline,finished_at,score,total,percent,answers_json,option_orders_json)
            SELECT id,assessment_id,employee_id,attempt_number,question_ids_json,status,started_at,deadline,finished_at,score,total,percent,answers_json,option_orders_json FROM assessment_attempts;
        DROP TABLE assessment_attempts;
        ALTER TABLE assessment_attempts_upgraded RENAME TO assessment_attempts;
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_assessment ON assessment_attempts(assessment_id, employee_id) WHERE status='in-progress';
        CREATE INDEX IF NOT EXISTS assessment_attempts_employee ON assessment_attempts(employee_id);
        COMMIT;
        PRAGMA foreign_keys=ON;
    ''')


def seed_admin(path, source=ADMIN_SEED):
    """Create the packaged administrator when the database has none, so a fresh clone opens on the login page.

    The seed file holds a salted scrypt hash, never the password. An existing account with the same email is left unchanged.
    """
    if not source.exists():
        return
    admin = json.loads(source.read_text(encoding='utf-8'))
    db = connect(path)
    try:
        with db:
            if db.execute("SELECT 1 FROM candidates WHERE role='admin'").fetchone() or db.execute('SELECT 1 FROM candidates WHERE email=?', (admin['email'].casefold(),)).fetchone():
                return
            stamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role,must_change_password) VALUES (?,?,?,?,?,?,'admin',0)",
                       (admin['id'], admin['name'], admin['email'].casefold(), admin['passwordHash'], stamp, stamp))
            db.execute('INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at) VALUES (?,?,?,1,?)', (str(uuid.uuid4()), admin['id'], COURSE_ID, stamp))
            db.execute('INSERT INTO admin_events(admin_id,action,target_id,detail,created_at) VALUES (?,?,?,?,?)',
                       (admin['id'], 'admin_setup', admin['id'], 'Packaged administrator created from admin-seed.json', stamp))
    finally:
        db.close()


def course_deleted(db, course_id):
    """A course removed in Manage Courses; packaged courses are then not re-created."""
    return db.execute('SELECT 1 FROM deleted_courses WHERE course_id=?', (course_id,)).fetchone() is not None


def seed_assessment(db, identity, course_id, kind, title, description, settings, questions, stamp):
    """Create or refresh a packaged assessment. Banks that employees have already attempted are left unchanged."""
    if db.execute('SELECT 1 FROM assessment_attempts WHERE assessment_id=?', (identity,)).fetchone():
        return
    values = (title, description, kind, course_id, settings['passPercent'], min(settings['maxAttempts'], MAX_EXAM_ATTEMPTS),settings.get('questionCount', len(questions)), settings['timeLimitMinutes'])
    if db.execute('SELECT 1 FROM assessments WHERE id=?', (identity,)).fetchone():
        db.execute("UPDATE assessments SET title=?,description=?,kind=?,course_id=?,pass_percent=?,max_attempts=?,question_count=?,time_limit_minutes=?,status='published',updated_at=? WHERE id=?", (*values, stamp, identity))
    else:
        db.execute("INSERT INTO assessments(id,title,description,kind,course_id,pass_percent,max_attempts,question_count,time_limit_minutes,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'published',?,?)", (identity, *values, stamp, stamp))
    db.execute('DELETE FROM assessment_bank WHERE assessment_id=?', (identity,))
    for position, (prompt, options, correct, explanation) in enumerate(questions):
        db.execute('INSERT INTO assessment_bank(id,assessment_id,position,prompt,options_json,correct_option,explanation,code) VALUES (?,?,?,?,?,?,?,?)',
                   (f'{identity}-q{position + 1:02d}', identity, position, prompt, json.dumps(options), correct, explanation, ''))


def course_fingerprint(db, course_id):
    """SHA-256 of the editable course content: course title, category, description and each lesson's text fields."""
    course = db.execute('SELECT title,category,description FROM courses WHERE id=?', (course_id,)).fetchone()
    lessons = db.execute('SELECT title,description,content,document_url,resources_json,activity_json FROM course_lessons WHERE course_id=? ORDER BY position', (course_id,)).fetchall()
    return hashlib.sha256(json.dumps([list(course), [list(l) for l in lessons]], ensure_ascii=False).encode()).hexdigest()


def seed_lesson_course(db, source, stamp):
    """Add a packaged lesson-based course, or upgrade an older packaged version.

    A course that an administrator has edited in Manage Courses is never overwritten. A course that was saved
    without changes still matches the fingerprint of an earlier packaged version, so it is upgraded. Lesson ids
    are stable, so employee progress stays attached to the same lessons across upgrades.
    """
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    if 'finalAssessment' not in course:
        return seed_native_lesson_course(db, source, stamp)
    existing = db.execute('SELECT version FROM courses WHERE id=?', (course['id'],)).fetchone()
    if existing and existing['version'] >= course['version']:
        return
    saved = existing and db.execute("SELECT 1 FROM admin_events WHERE action='course_saved' AND target_id=?", (course['id'],)).fetchone()
    if saved and course_fingerprint(db, course['id']) not in course.get('unchangedFingerprints', []):
        return
    db.execute('INSERT OR IGNORE INTO course_categories VALUES (?,?)', (course['category'], stamp))
    fields = (course['title'], course['category'], course['description'], course['status'], course['difficulty'], course['durationMinutes'], course['visibility'], course['version'], course.get('pageLayout', 'standard'))
    if existing:
        db.execute("UPDATE courses SET title=?,category=?,description=?,status=?,difficulty=?,duration_minutes=?,visibility=?,version=?,page_layout=?,format='lessons',updated_at=? WHERE id=?", (*fields, stamp, course['id']))
    else:
        db.execute("INSERT INTO courses(id,title,category,description,status,difficulty,duration_minutes,visibility,version,page_layout,format,sets_json,lessons_json,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,'lessons','[]','[]',?)",
                   (course['id'], *fields, stamp))
    # The final assessment, when the course has one, is required for the certificate.
    final = course.get('finalAssessment')
    if final:
        seed_assessment(db, final['id'], course['id'], 'post', final['title'], final['description'], final, final['questions'], stamp)
        db.execute('UPDATE courses SET post_assessment_id=? WHERE id=?', (final['id'], course['id']))
    kept = []
    for position, lesson in enumerate(course['lessons']):
        lesson_id = f"{course['id']}-{lesson['slug']}"
        kept.append(lesson_id)
        # A lesson can show the final assessment inline as its knowledge check (single-lesson courses such as RAG).
        check_id = final['id'] if final and lesson.get('usesFinalAssessment') else None
        if lesson.get('knowledgeCheck'):
            check_id = f"{course['id']}-check-{position + 1}"
            seed_assessment(db, check_id, course['id'], 'knowledge', f"Knowledge check: {lesson['title']}", 'A short check of this lesson. Answers are explained after you submit.',
                            course['knowledgeCheck'], lesson['knowledgeCheck'], stamp)
        values = (position, lesson['title'], lesson['description'], lesson['content'], lesson['durationMinutes'], json.dumps(lesson['activity']) if lesson.get('activity') else '', check_id)
        # Text-based lessons: no video, captions or video length.
        db.execute('''INSERT INTO course_lessons(id,course_id,position,title,description,content,duration_minutes,activity_json,assessment_id,video_url,captions_url,video_seconds,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,'','',0,?,?)
            ON CONFLICT(id) DO UPDATE SET position=excluded.position,title=excluded.title,description=excluded.description,content=excluded.content,duration_minutes=excluded.duration_minutes,
                activity_json=excluded.activity_json,assessment_id=excluded.assessment_id,video_url='',captions_url='',video_seconds=0,updated_at=excluded.updated_at''', (lesson_id, course['id'], *values, stamp, stamp))
    placeholders = ','.join('?' * len(kept))
    # Video watch records from an earlier packaged version no longer apply to these text lessons.
    db.execute(f'DELETE FROM lesson_watch WHERE lesson_id IN ({placeholders})', kept)


def seed_native_lesson_course(db, source, stamp):
    """Add a packaged lesson-based course once. Later edits in Manage Courses are never overwritten."""
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    manifest_path = VIDEO_ROOT / course['id'] / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() and course.get('videoEnabled', True) else {}
    if db.execute('SELECT 1 FROM courses WHERE id=?', (course['id'],)).fetchone() is None:
        db.execute('INSERT OR IGNORE INTO course_categories VALUES (?,?)', (course['category'], stamp))
        db.execute("INSERT INTO courses(id,title,version,category,description,status,sets_json,lessons_json,updated_at,difficulty,duration_minutes,format,visibility) VALUES (?,?,1,?,?,?,'[]','[]',?,?,?,'lessons',?)",
                   (course['id'], course['title'], course['category'], course['description'], course['status'], stamp, course['difficulty'], course['durationMinutes'], course['visibility']))
        for position, lesson in enumerate(course['lessons']):
            media = f"api/videos/{course['id']}/{lesson['slug']}"
            video = course.get('videoEnabled', True)
            db.execute('''INSERT INTO course_lessons(id,course_id,position,title,description,video_url,content,duration_minutes,created_at,updated_at,captions_url,video_seconds,completion_percent,activity_json,practice_json,quiz_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (f"{course['id']}-{lesson['slug']}", course['id'], position, lesson['title'], lesson['description'], media + '.mp4' if video else '', lesson['content'],
                                                       lesson['durationMinutes'], stamp, stamp, media + '.vtt' if video else '', manifest.get(lesson['slug'], {}).get('seconds', 0), lesson['completionPercent'],
                                                       json.dumps(lesson['activity']) if lesson.get('activity') else '', json.dumps(lesson['practice']) if lesson.get('practice') else '',
                                                       json.dumps(lesson['quiz']) if lesson.get('quiz') else ''))
    # Videos rendered after the course was first seeded: record their length so the watch threshold applies.
    for slug, info in manifest.items():
        db.execute('UPDATE course_lessons SET video_seconds=? WHERE id=? AND video_seconds=0', (info['seconds'], f"{course['id']}-{slug}"))


def upgrade_python_interactive(db, source, stamp):
    """One-time, authorized conversion of the packaged Python course; keep learner records intact."""
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    revision = 'interactive-v1'
    if not course.get('interactive') or db.execute('SELECT 1 FROM course_content_updates WHERE course_id=? AND revision=?', (course['id'], revision)).fetchone():
        return
    for lesson in course['lessons']:
        db.execute('''UPDATE course_lessons SET content=?,practice_json=?,quiz_json=?,video_url='',captions_url='',video_seconds=0,updated_at=?
            WHERE id=? AND course_id=?''', (lesson['content'], json.dumps(lesson['practice']), json.dumps(lesson['quiz']), stamp,
                                          f"{course['id']}-{lesson['slug']}", course['id']))
    db.execute('UPDATE courses SET description=?,updated_at=? WHERE id=?', (course['description'], stamp, course['id']))
    db.execute('INSERT INTO course_content_updates VALUES (?,?,?)', (course['id'], revision, stamp))


def upgrade_python_lessons(db, source, stamp):
    """Expand the packaged Python summaries once without resetting learning or overwriting trainer edits."""
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    revision = course.get('contentRevision')
    if not revision or db.execute('SELECT 1 FROM course_content_updates WHERE course_id=? AND revision=?', (course['id'], revision)).fetchone():
        return
    for lesson in course['lessons']:
        identity = f"{course['id']}-{lesson['slug']}"
        current = db.execute('SELECT content FROM course_lessons WHERE id=? AND course_id=?', (identity, course['id'])).fetchone()
        if current and hashlib.sha256(current['content'].encode('utf-8')).hexdigest() == lesson.get('legacyContentHash'):
            db.execute('UPDATE course_lessons SET content=?,updated_at=? WHERE id=?', (lesson['content'], stamp, identity))
    db.execute('INSERT INTO course_content_updates VALUES (?,?,?)', (course['id'], revision, stamp))


def restructure_java_course(db, source, stamp):
    """Move an installed Java course to the packaged module structure once.

    Modules and assignments from an earlier structure move, with every learner record attached to them, to an
    archived copy of the course. Earned certificates are unaffected. Current runs continue on the new modules; an
    assignment attempt left open on a retired assignment is ended. Later initialization never repeats this, so
    subsequent trainer edits are kept.
    """
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    revision = course.get('contentRevision')
    if not revision or db.execute('SELECT 1 FROM course_content_updates WHERE course_id=? AND revision=?', (course['id'], revision)).fetchone():
        return
    lesson_ids = [f"{course['id']}-{lesson['slug']}" for lesson in course['lessons']]
    checkpoint_ids = [item['id'] for item in course['assignments']]
    stale_lessons = [r[0] for r in db.execute(f"SELECT id FROM course_lessons WHERE course_id=? AND id NOT IN ({','.join('?' * len(lesson_ids))})", (course['id'], *lesson_ids))]
    stale_checkpoints = [r[0] for r in db.execute(f"SELECT id FROM course_checkpoints WHERE course_id=? AND id NOT IN ({','.join('?' * len(checkpoint_ids))})", (course['id'], *checkpoint_ids))]
    if stale_lessons or stale_checkpoints:
        archive = f"{course['id']}-previous-edition"
        old = db.execute('SELECT * FROM courses WHERE id=?', (course['id'],)).fetchone()
        db.execute("""INSERT OR IGNORE INTO courses(id,title,version,category,description,status,sets_json,lessons_json,updated_at,difficulty,duration_minutes,format,visibility)
            VALUES (?,?,1,?,?,'archived','[]','[]',?,?,?,'lessons',?)""",
                   (archive, old['title'] + ' (previous edition)', old['category'], old['description'], stamp, old['difficulty'], old['duration_minutes'], old['visibility']))
        if stale_checkpoints:
            placeholders = ','.join('?' * len(stale_checkpoints))
            db.execute(f"UPDATE checkpoint_attempts SET status='terminated',reason=?,finished_at=? WHERE status='in-progress' AND checkpoint_id IN ({placeholders})",
                       ('This assignment was retired when the course was restructured.', stamp, *stale_checkpoints))
            db.execute(f'UPDATE course_checkpoints SET course_id=? WHERE id IN ({placeholders})', (archive, *stale_checkpoints))
        if stale_lessons:
            placeholders = ','.join('?' * len(stale_lessons))
            db.execute(f'UPDATE course_lessons SET course_id=? WHERE id IN ({placeholders})', (archive, *stale_lessons))
            db.execute(f'UPDATE course_runs SET last_lesson_id=NULL WHERE course_id=? AND last_lesson_id IN ({placeholders})', (course['id'], *stale_lessons))
        db.execute('UPDATE courses SET description=?,duration_minutes=?,updated_at=? WHERE id=?', (course['description'], course['durationMinutes'], stamp, course['id']))
    for position, lesson in enumerate(course['lessons']):
        db.execute('''INSERT INTO course_lessons(id,course_id,position,title,description,video_url,content,duration_minutes,created_at,updated_at,captions_url,video_seconds,completion_percent,quiz_json)
            VALUES (?,?,?,?,?,'',?,?,?,?,'',0,?,?)
            ON CONFLICT(id) DO UPDATE SET position=excluded.position,title=excluded.title,description=excluded.description,content=excluded.content,
                duration_minutes=excluded.duration_minutes,completion_percent=excluded.completion_percent,quiz_json=excluded.quiz_json,updated_at=excluded.updated_at''',
                   (lesson_ids[position], course['id'], position, lesson['title'], lesson['description'], lesson['content'], lesson['durationMinutes'],
                    stamp, stamp, lesson['completionPercent'], json.dumps(lesson['quiz'])))
    db.execute('INSERT INTO course_content_updates VALUES (?,?,?)', (course['id'], revision, stamp))


def seed_checkpoints(db, source):
    """Add newly packaged assignments to existing courses without changing learner records."""
    if not source.exists():
        return
    course = json.loads(source.read_text(encoding='utf-8'))
    if course_deleted(db, course['id']):
        return
    for item in course.get('assignments', []):
        db.execute('''INSERT OR IGNORE INTO course_checkpoints
            (id,course_id,after_lesson,title,instructions,lesson_ids_json,questions_json,pass_percent,max_attempts,time_limit_seconds)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (item['id'], course['id'], item['afterLesson'], item['title'], item['instructions'], json.dumps(item['lessonIds']), json.dumps(item['questions']),
             item.get('passPercent', 75), item.get('maxAttempts', 3), item.get('timeLimitSeconds', 600)))


def public_curriculum(db, course_id=COURSE_ID):
    row = db.execute('SELECT sets_json FROM courses WHERE id=?', (course_id,)).fetchone()
    result = json.loads(row['sets_json'])
    targets = {}
    for s, item in enumerate(result):
        for kind, e, target in [('exam', -1, item['exam'])] + [('exercise', i, ex['questions']) for i, ex in enumerate(item['exercises'])]:
            target.clear()
            targets[(s,kind,e)]=target
    for question in db.execute('SELECT set_index,kind,exercise_index,prompt,options_json FROM assessment_questions WHERE course_id=? ORDER BY set_index,kind,exercise_index,question_index', (course_id,)):
        target=targets.get((question['set_index'],question['kind'],question['exercise_index']))
        if target is not None:
            target.append([question['prompt'],json.loads(question['options_json'])])
    return result
