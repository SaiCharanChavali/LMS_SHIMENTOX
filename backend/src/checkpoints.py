"""Required, timed assignment checkpoints. All authorization and grading run on the server."""
import json
import secrets
import time

from services import check, now, uid


def expire(db, run_id, reason=None):
    clause, params = ('', []) if reason else (' AND deadline<=?', [time.time()])
    db.execute("UPDATE checkpoint_attempts SET status='terminated',reason=?,finished_at=? WHERE run_id=? AND status='in-progress'" + clause,
               [reason or 'Time expired. This assignment attempt has ended.', now(), run_id] + params)


def has_passed(db, run_id, checkpoint_id):
    return db.execute("SELECT 1 FROM checkpoint_attempts WHERE run_id=? AND checkpoint_id=? AND status='passed'", (run_id, checkpoint_id)).fetchone() is not None


def all_passed(db, run_id):
    return db.execute('''SELECT 1 FROM course_checkpoints c JOIN course_runs r ON r.course_id=c.course_id
        WHERE r.id=? AND NOT EXISTS(SELECT 1 FROM checkpoint_attempts a WHERE a.run_id=r.id AND a.checkpoint_id=c.id AND a.status='passed')''', (run_id,)).fetchone() is None


def lesson_unlocked(db, run_id, course_id, lesson_id):
    row = db.execute('SELECT position FROM course_lessons WHERE id=? AND course_id=?', (lesson_id, course_id)).fetchone()
    if row is None:
        return False
    return db.execute('''SELECT 1 FROM course_checkpoints c WHERE c.course_id=? AND c.after_lesson<=?
        AND NOT EXISTS(SELECT 1 FROM checkpoint_attempts a WHERE a.run_id=? AND a.checkpoint_id=c.id AND a.status='passed')''',
                      (course_id, row['position'], run_id)).fetchone() is None


def ready(db, run_id, checkpoint):
    lesson_ids = json.loads(checkpoint['lesson_ids_json'])
    completed = {r[0] for r in db.execute('SELECT lesson_id FROM lesson_progress WHERE run_id=?', (run_id,))}
    previous = db.execute('''SELECT 1 FROM course_checkpoints c WHERE c.course_id=? AND c.after_lesson<?
        AND NOT EXISTS(SELECT 1 FROM checkpoint_attempts a WHERE a.run_id=? AND a.checkpoint_id=c.id AND a.status='passed')''',
                          (checkpoint['course_id'], checkpoint['after_lesson'], run_id)).fetchone()
    return previous is None and bool(lesson_ids) and all(identity in completed for identity in lesson_ids)


def attempt_view(row):
    return {**{key: row[column] for key, column in (
        ('id', 'id'), ('status', 'status'), ('startedAt', 'started_at'), ('finishedAt', 'finished_at'),
        ('score', 'score'), ('total', 'total'), ('reason', 'reason'), ('attemptNumber', 'attempt_number'))},
        'deadline': row['deadline'] * 1000,
        'percent': round(row['score'] / row['total'] * 100) if row['score'] is not None else None}


def views(db, run_id, course_id):
    result = []
    for c in db.execute('SELECT * FROM course_checkpoints WHERE course_id=? ORDER BY after_lesson', (course_id,)):
        attempts = [attempt_view(a) for a in db.execute('SELECT * FROM checkpoint_attempts WHERE run_id=? AND checkpoint_id=? ORDER BY attempt_number', (run_id, c['id']))] if run_id else []
        result.append({'id': c['id'], 'title': c['title'], 'instructions': c['instructions'], 'afterLesson': c['after_lesson'],
                       'firstLesson': c['after_lesson'] - max(len(json.loads(c['lesson_ids_json'])), 1) + 1,
                       'passPercent': c['pass_percent'], 'maxAttempts': c['max_attempts'], 'timeLimitSeconds': c['time_limit_seconds'],
                       'questionCount': len(json.loads(c['questions_json'])), 'passed': any(a['status'] == 'passed' for a in attempts),
                       'ready': ready(db, run_id, c) if run_id else False, 'attempts': attempts})
    return result


def start(db, run, data):
    c = db.execute('SELECT * FROM course_checkpoints WHERE id=? AND course_id=?', (data.get('checkpointId'), run['course_id'])).fetchone()
    check(c is not None, 'Assignment was not found.', 404)
    check(ready(db, run['id'], c), 'Complete the related modules and pass earlier assignments first.', 403)
    check(not has_passed(db, run['id'], c['id']), 'This assignment is already passed.', 409)
    check(db.execute("SELECT 1 FROM checkpoint_attempts WHERE run_id=? AND status='in-progress'", (run['id'],)).fetchone() is None,
          'An assignment is already active. Reopen the course to end the interrupted attempt.', 409)
    number = db.execute('SELECT COUNT(*)+1 FROM checkpoint_attempts WHERE run_id=? AND checkpoint_id=?', (run['id'], c['id'])).fetchone()[0]
    check(number <= c['max_attempts'], 'All assignment attempts have been used. Start a new course run to try again.', 409)
    # Store the shuffled questions and keys as an immutable server-side snapshot for this attempt.
    questions = json.loads(c['questions_json'])
    rng = secrets.SystemRandom()
    rng.shuffle(questions)
    for q in questions:
        order = list(range(len(q['options'])))
        rng.shuffle(order)
        q['correct'] = order.index(q['correct'])
        q['options'] = [q['options'][i] for i in order]
    identity = uid()
    db.execute('''INSERT INTO checkpoint_attempts(id,run_id,checkpoint_id,attempt_number,status,started_at,deadline,total,questions_json)
        VALUES (?,?,?,?,'in-progress',?,?,?,?)''',
        (identity, run['id'], c['id'], number, now(), time.time() + c['time_limit_seconds'], len(questions), json.dumps(questions)))
    attempt = attempt_view(db.execute('SELECT * FROM checkpoint_attempts WHERE id=?', (identity,)).fetchone())
    public = [{k: q[k] for k in ('prompt', 'code', 'options') if k in q} for q in questions]
    return {'attempt': attempt, 'questions': public}


def finish(db, run, data):
    a = db.execute('SELECT * FROM checkpoint_attempts WHERE id=? AND run_id=?', (data.get('attemptId'), run['id'])).fetchone()
    check(a is not None, 'Assignment attempt was not found.', 404)
    if a['status'] == 'in-progress':
        if data.get('terminate') is True:
            reason = str(data.get('reason') or 'The assignment attempt was ended.')[:300]
            db.execute("UPDATE checkpoint_attempts SET status='terminated',reason=?,finished_at=? WHERE id=?", (reason, now(), a['id']))
        else:
            questions, answers = json.loads(a['questions_json']), data.get('answers')
            check(isinstance(answers, list) and len(answers) == len(questions), 'Answer every assignment question.')
            check(all(type(answer) is int and 0 <= answer < len(q['options']) for answer, q in zip(answers, questions)), 'Invalid assignment answer.')
            score = sum(answer == q['correct'] for answer, q in zip(answers, questions))
            threshold = db.execute('SELECT pass_percent FROM course_checkpoints WHERE id=?', (a['checkpoint_id'],)).fetchone()[0]
            status = 'passed' if score * 100 >= threshold * a['total'] else 'failed'
            db.execute('UPDATE checkpoint_attempts SET status=?,score=?,answers_json=?,finished_at=? WHERE id=?', (status, score, json.dumps(answers), now(), a['id']))
    # Finished submissions are idempotent: replaying cannot change a mark or revive a terminated attempt.
    return {'attempt': attempt_view(db.execute('SELECT * FROM checkpoint_attempts WHERE id=?', (a['id'],)).fetchone())}
