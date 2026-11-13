"""Live training and webinars: online meeting links (Zoom, Google Meet, Microsoft Teams), calendar invites,
session recordings, live Q&A, feedback, scheduled reminders, post-session assessments and trainer workload.

Scheduling, registration, seat limits and attendance live in development.py; this module adds to those sessions.
Session times are stored as server-local 'YYYY-MM-DDTHH:MM' strings, like the rest of the training calendar.
"""
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

from admin import audit, media_reference
from analytics import local_now
from database import connect
from services import check, notify, now, require, text, uid

PROVIDERS = {'zoom': 'Zoom', 'meet': 'Google Meet', 'teams': 'Microsoft Teams', 'other': 'Online meeting'}
PROVIDER_HOSTS = {'zoom': ('zoom.us', 'zoomgov.com'), 'meet': ('meet.google.com',), 'teams': ('teams.microsoft.com', 'teams.live.com')}
DELIVERY = ('in_person', 'online', 'hybrid')
JOIN_EARLY_MINUTES = 15
QA_GRACE_MINUTES = 30  # Questions stay open briefly after the session for follow-ups.
MAX_QUESTIONS_PER_PERSON = 20
# Checked tightest first, so only the most urgent reminder that is due is sent (a server that was down skips stale ones).
REMINDERS = ((JOIN_EARLY_MINUTES, 'join', 'starts in 15 minutes. You can join now.'), (60, '1h', 'starts in 1 hour.'), (24 * 60, '24h', 'starts tomorrow.'))
FOLLOW_UP_DAYS = 7


# ---------------------------------------------------------------- time and access helpers

def parse_local(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M')


def shift(value, minutes):
    return (parse_local(value) + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M')


def to_utc(value):
    # Session times are server-local; a naive datetime's astimezone() reads it in the server's time zone.
    return parse_local(value).astimezone(timezone.utc)


def session_or_404(db, identity):
    session = db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone()
    check(session is not None, 'Session was not found.', 404)
    return session


def is_staff(user, session):
    return user is not None and (user['role'] in ('admin', 'hr') or user['id'] in (session['trainer_id'], session['created_by']))


def my_status(db, session_id, user_id):
    row = db.execute('SELECT status FROM session_registrations WHERE session_id=? AND employee_id=?', (session_id, user_id)).fetchone()
    return row[0] if row else None


def participants(db, session_id):
    """Who took part: the attendance list once any attendance is recorded, otherwise everyone registered."""
    attended = [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status='attended'", (session_id,))]
    return attended or [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status='registered'", (session_id,))]


def detect_provider(url):
    host = (urlsplit(url).hostname or '').lower()
    for key, hosts in PROVIDER_HOSTS.items():
        if any(host == h or host.endswith('.' + h) for h in hosts):
            return key
    return 'other'


def https_link(value, label):
    value = value.strip()
    parts = urlsplit(value)
    check(parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password, f'The {label} must be an HTTPS link.')
    return value


# ---------------------------------------------------------------- session settings (called from save_session)

def session_fields(db, data, old):
    """Validated delivery, meeting, recording, assessment, Q&A and feedback settings. Missing fields keep stored values."""
    def keep(field, column, default):
        return data[field] if field in data else (old[column] if old else default)
    delivery = keep('delivery', 'delivery', 'in_person')
    check(delivery in DELIVERY, 'Select how the session is delivered: in person, online or hybrid.')
    url, provider = keep('meetingUrl', 'meeting_url', '') or '', ''
    check(isinstance(url, str) and len(url) <= 2000, 'The meeting link must contain at most 2000 characters.')
    if delivery == 'in_person':
        url = ''
    else:
        check(url.strip(), 'Add the Zoom, Google Meet or Microsoft Teams link for an online or hybrid session.')
        url = https_link(url, 'meeting link')
        provider = detect_provider(url)
        chosen = keep('meetingProvider', 'meeting_provider', '') or ''
        check(chosen in ('', *PROVIDERS), 'Select a valid meeting platform.')
        if chosen and chosen != 'other':
            check(provider == chosen, f'This is not a {PROVIDERS[chosen]} link. Check the meeting link, or choose the platform it belongs to.')
    recording = keep('recordingUrl', 'recording_url', '') or ''
    check(isinstance(recording, str) and len(recording) <= 2000, 'The recording link must contain at most 2000 characters.')
    recording = recording.strip()
    check(not recording or media_reference(recording), 'The recording must be an uploaded video or an HTTPS link.')
    if recording.startswith('api/materials/'):
        check(db.execute('SELECT 1 FROM materials WHERE id=?', (recording.removeprefix('api/materials/'),)).fetchone() is not None, 'The uploaded recording was not found. Upload it again.')
    assessment = keep('assessmentId', 'assessment_id', None) or None
    if assessment is not None:
        row = db.execute('SELECT status FROM assessments WHERE id=?', (assessment,)).fetchone() if isinstance(assessment, str) else None
        check(row is not None, 'Select a valid post-session assessment.')
        check(row['status'] == 'published', 'Publish the post-session assessment before linking it, so participants can take it.')
    toggles = []
    for field, column in (('qaEnabled', 'qa_enabled'), ('feedbackEnabled', 'feedback_enabled')):
        value = keep(field, column, True)
        check(type(value) in (bool, int), f'{field} must be true or false.')
        toggles.append(int(bool(value)))
    return {'delivery': delivery, 'meeting_provider': provider, 'meeting_url': url, 'recording_url': recording,
            'assessment_id': assessment, 'qa_enabled': toggles[0], 'feedback_enabled': toggles[1]}


def check_trainer_free(db, trainer, starts, ends, identity):
    """A trainer cannot run two scheduled sessions at the same time."""
    if not trainer:
        return
    row = db.execute("SELECT title,starts_at,ends_at FROM training_sessions WHERE trainer_id=? AND status='scheduled' AND id<>? AND starts_at<? AND ends_at>?",
                     (trainer, identity or '', ends, starts)).fetchone()
    check(row is None, f'The trainer is already running “{row["title"]}” from {row["starts_at"].replace("T", " ")} to {row["ends_at"][11:]}. Choose another time or trainer.' if row else '', 409)


def after_save(db, identity, title, old, fields):
    """Tell people about changes they act on: a new meeting link, or a recording becoming available."""
    if old is None:
        return
    if fields['meeting_url'] and fields['meeting_url'] != (old['meeting_url'] or ''):
        registered = [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status='registered'", (identity,))]
        notify(db, registered, 'session', f'New joining link: {title}', f'Join on {PROVIDERS[fields["meeting_provider"]]}. The link is on the Training Calendar.', 'calendar', f'session-link:{identity}:{fields["meeting_url"]}')
    if fields['recording_url'] and not old['recording_url']:
        people = [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status IN ('registered','attended')", (identity,))]
        notify(db, people, 'session', f'Recording available: {title}', 'Watch the session recording from the Training Calendar.', 'calendar', f'session-recording:{identity}')


# ---------------------------------------------------------------- what each person sees for a session

def calendar_links(row, include_link):
    start, end = to_utc(row['starts_at']), to_utc(row['ends_at'])
    details, location = row['description'] or '', row['location'] or ''
    if include_link and row['meeting_url']:
        details = (details + '\n\n' if details else '') + f'Join on {PROVIDERS.get(row["meeting_provider"], "the meeting link")}: {row["meeting_url"]}'
        location = location or row['meeting_url']
    stamp = lambda value: value.strftime('%Y%m%dT%H%M%SZ')
    iso = lambda value: value.strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'google': 'https://calendar.google.com/calendar/render?' + urlencode({'action': 'TEMPLATE', 'text': row['title'], 'dates': f'{stamp(start)}/{stamp(end)}', 'details': details, 'location': location}),
            'outlook': 'https://outlook.office.com/calendar/0/deeplink/compose?' + urlencode({'path': '/calendar/action/compose', 'rru': 'addevent', 'subject': row['title'], 'startdt': iso(start), 'enddt': iso(end), 'body': details, 'location': location})}


def row_extras(db, user, row, mine):
    """Fields added to every session in session_rows. Meeting links and recordings are shown only to participants and staff."""
    staff, current = is_staff(user, row), local_now()
    inside = staff or mine in ('registered', 'attended')
    scheduled = row['status'] == 'scheduled'
    item = {'delivery': row['delivery'], 'meetingProvider': row['meeting_provider'], 'providerLabel': PROVIDERS.get(row['meeting_provider'], ''),
            'online': row['delivery'] != 'in_person', 'joinOpensAt': shift(row['starts_at'], -JOIN_EARLY_MINUTES),
            'live': scheduled and row['starts_at'] <= current < row['ends_at'], 'ended': row['ends_at'] <= current,
            'qaEnabled': bool(row['qa_enabled']), 'qaOpen': bool(row['qa_enabled']) and scheduled and current < shift(row['ends_at'], QA_GRACE_MINUTES),
            'feedbackEnabled': bool(row['feedback_enabled']), 'hasRecording': bool(row['recording_url']), 'assessmentId': row['assessment_id']}
    if inside:
        item['calendarLinks'] = calendar_links(row, True)
        item['recordingUrl'] = row['recording_url']
        if item['online']:
            item['meetingUrl'] = row['meeting_url']
            item['canJoin'] = scheduled and (staff or item['joinOpensAt'] <= current) and current < row['ends_at']
    if row['assessment_id']:
        a = db.execute('SELECT id,title,status FROM assessments WHERE id=?', (row['assessment_id'],)).fetchone()
        if a:
            item['assessment'] = {'id': a['id'], 'title': a['title'], 'published': a['status'] == 'published'}
            if user is not None and mine:
                item['assessment']['passed'] = db.execute("SELECT 1 FROM assessment_attempts WHERE assessment_id=? AND employee_id=? AND status='passed'", (a['id'], user['id'])).fetchone() is not None
                item['assessment']['open'] = item['ended'] and a['status'] == 'published'
    if user is not None and mine:
        f = db.execute('SELECT rating,comment FROM session_feedback WHERE session_id=? AND employee_id=?', (row['id'], user['id'])).fetchone()
        item['myFeedback'] = {'rating': f['rating'], 'comment': f['comment']} if f else None
        item['canGiveFeedback'] = bool(row['feedback_enabled']) and row['starts_at'] <= current and mine in ('registered', 'attended')
    if staff:
        summary = db.execute('SELECT COUNT(*),AVG(rating) FROM session_feedback WHERE session_id=?', (row['id'],)).fetchone()
        item['feedbackCount'], item['averageRating'] = summary[0], round(summary[1], 1) if summary[1] is not None else None
        item['openQuestions'] = db.execute("SELECT COUNT(*) FROM session_questions WHERE session_id=? AND status='open'", (row['id'],)).fetchone()[0]
        item['attended'] = db.execute("SELECT COUNT(*) FROM session_registrations WHERE session_id=? AND status='attended'", (row['id'],)).fetchone()[0]
        item['meetingUrl'], item['recordingUrl'] = row['meeting_url'], row['recording_url']
    return item


def registration_extras(db, session, registrations):
    """Each participant's feedback rating and post-session assessment result, for the trainer's roster."""
    ratings = {r[0]: r[1] for r in db.execute('SELECT employee_id,rating FROM session_feedback WHERE session_id=?', (session['id'],))}
    results = {}
    if session['assessment_id']:
        for r in db.execute("SELECT employee_id,MAX(percent) AS best,MAX(status='passed') AS passed FROM assessment_attempts WHERE assessment_id=? AND status<>'in-progress' GROUP BY employee_id", (session['assessment_id'],)):
            results[r['employee_id']] = {'best': r['best'], 'passed': bool(r['passed'])}
    for item in registrations:
        item['rating'] = ratings.get(item['employeeId'])
        item['assessment'] = results.get(item['employeeId'])
    return registrations


# ---------------------------------------------------------------- calendar files (.ics)

def ics_text(value):
    return str(value).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r\n', '\\n').replace('\n', '\\n')


def ics_fold(line):
    # RFC 5545: lines longer than 75 octets continue on the next line after a space.
    out, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 74:
            out.append(current)
            current = ' '
        current += char
    out.append(current)
    return '\r\n'.join(out)


def vevent(row, include_link, stamp):
    description = row['description'] or ''
    location = row['location'] or ''
    if include_link and row['meeting_url']:
        description = (description + '\n\n' if description else '') + f'Join on {PROVIDERS.get(row["meeting_provider"], "the meeting link")}: {row["meeting_url"]}'
        location = location or row['meeting_url']
    lines = ['BEGIN:VEVENT', f'UID:{row["id"]}@shimentox-lms', f'DTSTAMP:{stamp}',
             f'DTSTART:{to_utc(row["starts_at"]):%Y%m%dT%H%M%SZ}', f'DTEND:{to_utc(row["ends_at"]):%Y%m%dT%H%M%SZ}',
             f'SUMMARY:{ics_text(row["title"])}', f'DESCRIPTION:{ics_text(description)}', f'LOCATION:{ics_text(location)}',
             f'STATUS:{"CANCELLED" if row["status"] == "cancelled" else "CONFIRMED"}']
    if include_link and row['meeting_url']:
        lines.append(f'URL:{row["meeting_url"]}')
    lines += ['BEGIN:VALARM', 'ACTION:DISPLAY', f'DESCRIPTION:{ics_text(row["title"])}', 'TRIGGER:-PT15M', 'END:VALARM', 'END:VEVENT']
    return lines


def calendar_file(db, user, path):
    """(body, content type, file name) for one session, or for every session the person is registered for or trains."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    parts = path.removeprefix('/api/me/').split('/')
    if parts[0] == 'sessions':
        row = session_or_404(db, parts[1])
        mine = my_status(db, row['id'], user['id'])
        check(is_staff(user, row) or row['status'] == 'scheduled' or mine, 'Session was not found.', 404)
        events, name = vevent(row, is_staff(user, row) or mine in ('registered', 'attended'), stamp), 'shimentox-session.ics'
    else:
        since = shift(local_now(), -30 * 24 * 60)
        rows = db.execute("""SELECT s.* FROM training_sessions s WHERE s.ends_at>=? AND (s.trainer_id=? OR EXISTS(SELECT 1 FROM session_registrations g
            WHERE g.session_id=s.id AND g.employee_id=? AND g.status IN ('registered','attended'))) ORDER BY s.starts_at""", (since, user['id'], user['id'])).fetchall()
        events, name = [line for row in rows for line in vevent(row, True, stamp)], 'shimentox-training-calendar.ics'
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//ShimentoX//Learning Portal//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:ShimentoX training', *events, 'END:VCALENDAR']
    return ('\r\n'.join(ics_fold(line) for line in lines) + '\r\n').encode('utf-8'), 'text/calendar; charset=utf-8', name


# ---------------------------------------------------------------- live Q&A

def qa_session(db, user, identity):
    session = session_or_404(db, identity)
    staff, mine = is_staff(user, session), my_status(db, identity, user['id'])
    check(staff or mine in ('registered', 'attended'), 'Register for this session to join its Q&A.', 403)
    check(staff or session['qa_enabled'], 'Q&A is turned off for this session.', 403)
    return session, staff


def questions(db, user, identity):
    session, staff = qa_session(db, user, identity)
    rows = db.execute('''SELECT q.*,c.full_name AS asker,a.full_name AS answerer,
        (SELECT COUNT(*) FROM session_question_votes v WHERE v.question_id=q.id) AS votes,
        EXISTS(SELECT 1 FROM session_question_votes v WHERE v.question_id=q.id AND v.employee_id=?) AS voted
        FROM session_questions q JOIN candidates c ON c.id=q.employee_id LEFT JOIN candidates a ON a.id=q.answered_by
        WHERE q.session_id=? ORDER BY CASE q.status WHEN 'open' THEN 0 WHEN 'answered' THEN 1 ELSE 2 END,votes DESC,q.created_at''', (user['id'], identity)).fetchall()
    items = []
    for r in rows:
        if r['status'] == 'dismissed' and not staff and r['employee_id'] != user['id']:
            continue
        own = r['employee_id'] == user['id']
        items.append({'id': r['id'], 'body': r['body'], 'status': r['status'], 'answer': r['answer'], 'answeredBy': r['answerer'], 'answeredAt': r['answered_at'],
                      'createdAt': r['created_at'], 'votes': r['votes'], 'voted': bool(r['voted']), 'mine': own, 'anonymous': bool(r['anonymous']),
                      'asker': r['asker'] if staff or own or not r['anonymous'] else 'Anonymous'})
    open_now = bool(session['qa_enabled']) and session['status'] == 'scheduled' and local_now() < shift(session['ends_at'], QA_GRACE_MINUTES)
    return {'session': {'id': session['id'], 'title': session['title'], 'live': session['starts_at'] <= local_now() < session['ends_at']},
            'questions': items, 'open': open_now, 'canModerate': staff}


def ask(db, user, identity, data):
    session, staff = qa_session(db, user, identity)
    check(bool(session['qa_enabled']) and session['status'] == 'scheduled' and local_now() < shift(session['ends_at'], QA_GRACE_MINUTES), 'Q&A for this session has closed.', 409)
    body = text(data, 'body', 2, 500)
    anonymous = data.get('anonymous', False)
    check(type(anonymous) is bool, 'anonymous must be true or false.')
    asked = db.execute('SELECT COUNT(*) FROM session_questions WHERE session_id=? AND employee_id=?', (identity, user['id'])).fetchone()[0]
    check(asked < MAX_QUESTIONS_PER_PERSON, f'You can ask up to {MAX_QUESTIONS_PER_PERSON} questions in one session.', 429)
    db.execute("INSERT INTO session_questions(id,session_id,employee_id,body,anonymous,status,answer,created_at) VALUES (?,?,?,?,?,'open','',?)",
               (uid(), identity, user['id'], body, int(anonymous), now()))
    return questions(db, user, identity)


def vote(db, user, identity, question_id):
    qa_session(db, user, identity)
    row = db.execute("SELECT status FROM session_questions WHERE id=? AND session_id=?", (question_id, identity)).fetchone()
    check(row is not None, 'Question was not found.', 404)
    if db.execute('SELECT 1 FROM session_question_votes WHERE question_id=? AND employee_id=?', (question_id, user['id'])).fetchone():
        db.execute('DELETE FROM session_question_votes WHERE question_id=? AND employee_id=?', (question_id, user['id']))
    else:
        check(row['status'] == 'open', 'Only open questions can be upvoted.', 409)
        db.execute('INSERT INTO session_question_votes VALUES (?,?,?)', (question_id, user['id'], now()))
    return questions(db, user, identity)


def moderate(db, user, identity, question_id, data):
    session = session_or_404(db, identity)
    check(is_staff(user, session), 'Only the session trainer or HR can answer questions.', 403)
    row = db.execute('SELECT * FROM session_questions WHERE id=? AND session_id=?', (question_id, identity)).fetchone()
    check(row is not None, 'Question was not found.', 404)
    status = data.get('status', 'answered')
    check(status in ('open', 'answered', 'dismissed'), 'Select a valid question status.')
    answer = data.get('answer', row['answer']) or ''
    check(isinstance(answer, str) and len(answer.strip()) <= 2000, 'The answer must contain at most 2000 characters.')
    answer = answer.strip()
    answered = status == 'answered'
    db.execute('UPDATE session_questions SET status=?,answer=?,answered_by=?,answered_at=? WHERE id=?',
               (status, answer, user['id'] if answered else None, now() if answered else None, question_id))
    if answered and row['status'] != 'answered' and row['employee_id'] != user['id']:
        notify(db, [row['employee_id']], 'session', f'Your question was answered: {session["title"]}', answer[:300] or 'The trainer answered it live in the session.', 'calendar', f'qa-answer:{question_id}')
    return questions(db, user, identity)


# ---------------------------------------------------------------- feedback

def submit_feedback(db, user, identity, data):
    session = session_or_404(db, identity)
    check(session['feedback_enabled'], 'Feedback is turned off for this session.', 403)
    check(my_status(db, identity, user['id']) in ('registered', 'attended'), 'Only participants can give feedback on this session.', 403)
    check(session['starts_at'] <= local_now(), 'Feedback opens when the session starts.', 409)
    rating = data.get('rating')
    check(type(rating) is int and 1 <= rating <= 5, 'Choose a rating from 1 to 5 stars.')
    comment = data.get('comment') or ''
    check(isinstance(comment, str) and len(comment.strip()) <= 2000, 'Comments must contain at most 2000 characters.')
    db.execute('''INSERT INTO session_feedback(session_id,employee_id,rating,comment,created_at,updated_at) VALUES (?,?,?,?,?,?)
        ON CONFLICT(session_id,employee_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment,updated_at=excluded.updated_at''',
               (identity, user['id'], rating, comment.strip(), now(), now()))
    return {'feedback': {'rating': rating, 'comment': comment.strip()}}


def feedback_report(db, user, identity):
    session = session_or_404(db, identity)
    check(is_staff(user, session), 'Only the session trainer or HR can read session feedback.', 403)
    items = [dict(r) for r in db.execute('''SELECT c.full_name AS name,f.rating,f.comment,f.updated_at AS at FROM session_feedback f
        JOIN candidates c ON c.id=f.employee_id WHERE f.session_id=? ORDER BY f.updated_at DESC''', (identity,))]
    count = len(items)
    people = len(participants(db, identity))
    return {'summary': {'responses': count, 'averageRating': round(sum(i['rating'] for i in items) / count, 1) if count else None,
                        'distribution': {str(n): sum(1 for i in items if i['rating'] == n) for n in range(1, 6)},
                        'participants': people, 'responseRate': round(count / people * 100) if people else 0},
            'items': items}


# ---------------------------------------------------------------- trainers

def trainers(db, user):
    require(user, 'sessions.manage')
    current = local_now()
    where, params = ("c.role IN ('admin','hr','trainer') AND c.is_active=1", ()) if user['role'] in ('admin', 'hr') else ('c.id=?', (user['id'],))
    result = []
    for c in db.execute(f'SELECT c.id,c.full_name,c.email,c.role FROM candidates c WHERE {where} ORDER BY c.full_name', params).fetchall():
        sessions = db.execute("SELECT id,title,starts_at,ends_at FROM training_sessions WHERE trainer_id=? AND status='scheduled' ORDER BY starts_at", (c['id'],)).fetchall()
        upcoming = [s for s in sessions if s['ends_at'] > current]
        delivered = [s for s in sessions if s['ends_at'] <= current]
        rating = db.execute('SELECT COUNT(*),AVG(f.rating) FROM session_feedback f JOIN training_sessions s ON s.id=f.session_id WHERE s.trainer_id=?', (c['id'],)).fetchone()
        attendees = db.execute("SELECT COUNT(*) FROM session_registrations g JOIN training_sessions s ON s.id=g.session_id WHERE s.trainer_id=? AND g.status='attended'", (c['id'],)).fetchone()[0]
        minutes = sum((parse_local(s['ends_at']) - parse_local(s['starts_at'])).total_seconds() / 60 for s in delivered)
        if not sessions and c['role'] != 'trainer' and user['role'] in ('admin', 'hr'):
            continue  # Admins and HR appear once they have sessions; dedicated trainers always appear.
        result.append({'id': c['id'], 'name': c['full_name'], 'email': c['email'], 'role': c['role'], 'upcoming': len(upcoming), 'delivered': len(delivered),
                       'hoursDelivered': round(minutes / 60, 1), 'attendees': attendees, 'ratings': rating[0],
                       'averageRating': round(rating[1], 1) if rating[1] is not None else None,
                       'next': {'id': upcoming[0]['id'], 'title': upcoming[0]['title'], 'startsAt': upcoming[0]['starts_at']} if upcoming else None})
    return {'trainers': result}


# ---------------------------------------------------------------- reminders and follow-ups

def process(db, at=None):
    """Send due session reminders and post-session follow-ups. Notification dedupe keys make repeat passes harmless."""
    current = at or datetime.now()
    text_now = current.strftime('%Y-%m-%dT%H:%M')
    horizon = (current + timedelta(minutes=REMINDERS[-1][0])).strftime('%Y-%m-%dT%H:%M')
    for s in db.execute("SELECT * FROM training_sessions WHERE status='scheduled' AND starts_at>? AND starts_at<=?", (text_now, horizon)).fetchall():
        minutes = (parse_local(s['starts_at']) - current).total_seconds() / 60
        due = next((r for r in REMINDERS if minutes <= r[0]), None)
        if not due:
            continue
        _, key, phrase = due
        people = [r[0] for r in db.execute("SELECT employee_id FROM session_registrations WHERE session_id=? AND status='registered'", (s['id'],))]
        if s['trainer_id']:
            people.append(s['trainer_id'])
        where = f'on {PROVIDERS.get(s["meeting_provider"], "the meeting link")}' if s['delivery'] != 'in_person' else f'at {s["location"] or "the published location"}'
        if s['delivery'] == 'hybrid' and s['location']:
            where = f'at {s["location"]} or {where}'
        notify(db, people, 'session', f'{s["title"]} {phrase}', f'{s["starts_at"].replace("T", " ")}, {where}.', 'calendar', f'session-reminder:{key}:{s["id"]}:{s["starts_at"]}')
    since = (current - timedelta(days=FOLLOW_UP_DAYS)).strftime('%Y-%m-%dT%H:%M')
    for s in db.execute("SELECT * FROM training_sessions WHERE status='scheduled' AND ends_at<=? AND ends_at>?", (text_now, since)).fetchall():
        people = participants(db, s['id'])
        if not people:
            continue
        if s['feedback_enabled']:
            notify(db, people, 'session', f'How was {s["title"]}?', 'Rate the session and share feedback for the trainer on the Training Calendar.', 'calendar', f'session-feedback:{s["id"]}')
        if s['assessment_id']:
            a = db.execute("SELECT title FROM assessments WHERE id=? AND status='published'", (s['assessment_id'],)).fetchone()
            if a:
                notify(db, people, 'assessment', f'Post-session assessment: {a["title"]}', f'Check what you learned in {s["title"]}.', 'assessments', f'session-assessment:{s["id"]}:{s["assessment_id"]}')


def run_pass(path):
    """One scheduler pass in its own short transaction."""
    with closing(connect(path)) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            process(db)
            db.commit()
        except Exception as error:
            db.rollback()
            print(f'Session reminder pass failed: {type(error).__name__}', file=sys.stderr, flush=True)

