"""Live training and webinars over real HTTP: meeting links, calendar invites, recordings, Q&A, feedback,
reminders, post-session assessments, trainer workload and the webinar upgrade of older databases."""
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3
import tempfile
import unittest
import urllib.request
import uuid
from pathlib import Path

from test_portal import PortalFixture, Client
from database import BACKEND, connect, initialize
import live_training


def at(minutes):
    return (datetime.now() + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M')


ZOOM = 'https://us02web.zoom.us/j/81234567890?pwd=abc'


class LiveTrainingTests(PortalFixture):
    def account(self, role='employee', name='Webinar Member'):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!'})
        self.assertEqual(result[0], 200, result[1])
        client.id = result[1]['candidate']['id']
        if role != 'employee':
            with closing(connect(self.db_path)) as db, db:
                db.execute('UPDATE candidates SET role=? WHERE id=?', (role, client.id))
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})[0], 200)
        return client

    def session(self, title, **fields):
        body = {'title': title, 'kind': 'webinar', 'startsAt': at(3 * 24 * 60), 'endsAt': at(3 * 24 * 60 + 60), 'capacity': 5,
                'delivery': 'online', 'meetingProvider': 'zoom', 'meetingUrl': ZOOM, **fields}
        status, data = self.admin.request('manage/sessions', body)[:2]
        self.assertEqual(status, 200, data)
        return next(s for s in data['sessions'] if s['title'] == title)

    def move(self, session_id, starts, ends):
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE training_sessions SET starts_at=?,ends_at=? WHERE id=?', (starts, ends, session_id))

    def titles(self, client):
        return [n['title'] for n in client.request('me/notifications')[1]['notifications']]

    def test_meeting_links_are_validated_and_shown_only_to_participants(self):
        bad = self.admin.request('manage/sessions', {'title': 'Wrong platform', 'startsAt': at(600), 'endsAt': at(660), 'capacity': 3, 'delivery': 'online', 'meetingProvider': 'teams', 'meetingUrl': ZOOM})
        self.assertEqual(bad[0], 400)
        self.assertIn('Microsoft Teams', bad[1]['error'])
        self.assertEqual(self.admin.request('manage/sessions', {'title': 'No link', 'startsAt': at(600), 'endsAt': at(660), 'capacity': 3, 'delivery': 'online'})[0], 400)
        self.assertEqual(self.admin.request('manage/sessions', {'title': 'Plain http', 'startsAt': at(600), 'endsAt': at(660), 'capacity': 3, 'delivery': 'online', 'meetingUrl': 'http://meet.google.com/abc-defg-hij'})[0], 400)
        meet = self.session('Meet webinar', meetingProvider='', meetingUrl='https://meet.google.com/abc-defg-hij')
        self.assertEqual(meet['meetingProvider'], 'meet')
        teams = self.session('Teams webinar', meetingProvider='teams', meetingUrl='https://teams.microsoft.com/l/meetup-join/19%3ameeting')
        self.assertEqual(teams['providerLabel'], 'Microsoft Teams')
        zoom = self.session('Zoom webinar')
        self.assertEqual((zoom['kind'], zoom['meetingProvider']), ('webinar', 'zoom'))

        learner = self.account(name='Link Learner')
        listed = next(s for s in learner.request('me/calendar')[1]['sessions'] if s['id'] == zoom['id'])
        self.assertNotIn('meetingUrl', listed, 'The joining link is hidden until the employee registers.')
        registered = next(s for s in learner.request(f'me/sessions/{zoom["id"]}/register', {})[1]['sessions'] if s['id'] == zoom['id'])
        self.assertEqual(registered['meetingUrl'], ZOOM)
        self.assertFalse(registered['canJoin'], 'Joining opens 15 minutes before the start.')
        self.assertIn('calendar.google.com', registered['calendarLinks']['google'])
        self.assertIn('outlook.office.com', registered['calendarLinks']['outlook'])
        self.move(zoom['id'], at(10), at(70))
        self.assertTrue(next(s for s in learner.request('me/calendar')[1]['sessions'] if s['id'] == zoom['id'])['canJoin'])

        # A changed link is sent to everyone registered.
        self.assertEqual(self.admin.request('manage/sessions', {**{k: zoom[k] for k in ('id', 'title', 'kind', 'capacity')}, 'startsAt': at(10), 'endsAt': at(70),
                                                                 'delivery': 'online', 'meetingProvider': 'zoom', 'meetingUrl': 'https://zoom.us/j/99999999999'})[0], 200)
        self.assertIn('New joining link: Zoom webinar', self.titles(learner))

    def test_calendar_files_for_one_session_and_the_whole_calendar(self):
        session = self.session('Calendar webinar', description='Bring questions, please; thanks')
        learner = self.account(name='Calendar Learner')
        learner.request(f'me/sessions/{session["id"]}/register', {})
        for path, name in ((f'me/sessions/{session["id"]}/calendar.ics', 'shimentox-session.ics'), ('me/calendar.ics', 'shimentox-training-calendar.ics')):
            with learner.opener.open(self.base + '/api/' + path, timeout=15) as response:
                body = response.read().decode('utf-8')
                self.assertTrue(response.headers['Content-Type'].startswith('text/calendar'))
                self.assertIn(name, response.headers['Content-Disposition'])
            self.assertTrue(body.startswith('BEGIN:VCALENDAR\r\n') and body.endswith('END:VCALENDAR\r\n'))
            self.assertIn(f'UID:{session["id"]}@shimentox-lms', body)
            self.assertIn('Bring questions\\, please\\; thanks', body)
            self.assertIn('zoom.us', body.replace('\r\n ', ''))
            self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in body.split('\r\n')))

    def test_trainer_double_booking_is_refused(self):
        trainer = self.account('trainer', 'Busy Trainer')
        first = self.session('Morning webinar', trainerId=trainer.id)
        clash = self.admin.request('manage/sessions', {'title': 'Overlapping webinar', 'startsAt': first['startsAt'], 'endsAt': first['endsAt'], 'capacity': 3, 'trainerId': trainer.id, 'location': 'Room 2'})
        self.assertEqual(clash[0], 409)
        self.assertIn('Morning webinar', clash[1]['error'])
        self.assertEqual(self.admin.request('manage/sessions', {'title': 'Cancelled overlap', 'status': 'cancelled', 'startsAt': first['startsAt'], 'endsAt': first['endsAt'], 'capacity': 3, 'trainerId': trainer.id})[0], 200)
        workload = trainer.request('manage/trainers')[1]['trainers']
        self.assertEqual([t['name'] for t in workload], ['Busy Trainer'], 'Trainers see only their own workload.')
        self.assertEqual(workload[0]['upcoming'], 1)
        self.assertIn('Busy Trainer', [t['name'] for t in self.admin.request('manage/trainers')[1]['trainers']])
        self.assertEqual(self.account(name='Not Staff').request('manage/trainers')[0], 403)

    def test_live_qa_feedback_recording_and_post_session_assessment(self):
        assessment = self.admin.request('manage/assessments', {'title': 'Webinar check', 'kind': 'knowledge', 'passPercent': 50, 'maxAttempts': 3, 'questionCount': 1, 'timeLimitMinutes': 10,
                                                                 'status': 'draft', 'questions': [['Two plus two?', ['4', '5'], 0, 'Arithmetic']]})[1]
        draft = next(a for a in assessment['assessments'] if a['title'] == 'Webinar check')
        self.assertEqual(self.admin.request('manage/sessions', {'title': 'Draft linked', 'startsAt': at(600), 'endsAt': at(660), 'capacity': 3, 'location': 'Room 1', 'assessmentId': draft['id']})[0], 400)
        self.admin.request('manage/assessments', {**{k: draft[k] for k in ('id', 'title', 'kind', 'passPercent', 'maxAttempts', 'questionCount', 'timeLimitMinutes', 'questions')}, 'status': 'published'})
        session = self.session('Q&A webinar', assessmentId=draft['id'])
        asker, voter, outsider = self.account(name='Asker'), self.account(name='Voter'), self.account(name='Outsider')
        for person in (asker, voter):
            self.assertEqual(person.request(f'me/sessions/{session["id"]}/register', {})[0], 200)

        self.assertEqual(outsider.request(f'me/sessions/{session["id"]}/questions')[0], 403)
        self.assertEqual(asker.request(f'me/sessions/{session["id"]}/questions', {'body': 'x'})[0], 400)
        named = asker.request(f'me/sessions/{session["id"]}/questions', {'body': 'Will the slides be shared?'})[1]['questions'][0]
        hidden = asker.request(f'me/sessions/{session["id"]}/questions', {'body': 'Is this recorded?', 'anonymous': True})[1]['questions']
        anonymous = next(q for q in hidden if q['body'] == 'Is this recorded?')
        seen = {q['body']: q for q in voter.request(f'me/sessions/{session["id"]}/questions')[1]['questions']}
        self.assertEqual(seen['Will the slides be shared?']['asker'], 'Asker')
        self.assertEqual(seen['Is this recorded?']['asker'], 'Anonymous')
        self.assertEqual(self.admin.request(f'me/sessions/{session["id"]}/questions')[1]['questions'][-1]['asker'], 'Asker', 'Trainers see who asked.')
        ranked = voter.request(f'me/sessions/{session["id"]}/questions/{anonymous["id"]}/vote', {})[1]['questions']
        self.assertEqual(ranked[0]['id'], anonymous['id'], 'Upvoted questions rise to the top.')
        self.assertTrue(ranked[0]['voted'])
        self.assertEqual(voter.request(f'manage/sessions/{session["id"]}/questions/{named["id"]}', {'status': 'answered', 'answer': 'Yes'})[0], 403)
        answered = self.admin.request(f'manage/sessions/{session["id"]}/questions/{named["id"]}', {'status': 'answered', 'answer': 'Yes, after the session.'})[1]['questions']
        self.assertEqual(next(q for q in answered if q['id'] == named['id'])['status'], 'answered')
        self.assertIn('Your question was answered: Q&A webinar', self.titles(asker))
        self.admin.request(f'manage/sessions/{session["id"]}/questions/{anonymous["id"]}', {'status': 'dismissed'})
        self.assertNotIn(anonymous['id'], [q['id'] for q in voter.request(f'me/sessions/{session["id"]}/questions')[1]['questions']])

        self.assertEqual(asker.request(f'me/sessions/{session["id"]}/feedback', {'rating': 5})[0], 409, 'Feedback opens when the session starts.')
        self.move(session['id'], at(-120), at(-60))
        self.assertEqual(outsider.request(f'me/sessions/{session["id"]}/feedback', {'rating': 5})[0], 403)
        self.assertEqual(asker.request(f'me/sessions/{session["id"]}/feedback', {'rating': 6})[0], 400)
        self.assertEqual(asker.request(f'me/sessions/{session["id"]}/feedback', {'rating': 4, 'comment': 'Clear examples'})[0], 200)
        self.assertEqual(asker.request(f'me/sessions/{session["id"]}/feedback', {'rating': 5, 'comment': 'Clear examples'})[0], 200)
        report = self.admin.request(f'manage/sessions/{session["id"]}/feedback')[1]
        self.assertEqual((report['summary']['responses'], report['summary']['averageRating'], report['summary']['responseRate']), (1, 5, 50))
        self.assertEqual(voter.request(f'manage/sessions/{session["id"]}/feedback')[0], 403)

        self.assertEqual(self.admin.request(f'manage/sessions/{session["id"]}/attendance', {'all': True})[0], 200)
        roster = self.admin.request(f'manage/sessions/{session["id"]}/registrations')[1]['registrations']
        self.assertEqual({r['status'] for r in roster}, {'attended'})
        self.assertEqual(next(r for r in roster if r['name'] == 'Asker')['rating'], 5)

        voter_titles = self.titles(voter)
        self.assertIn('How was Q&A webinar?', voter_titles)
        self.assertIn('Post-session assessment: Webinar check', voter_titles)
        past = next(s for s in voter.request('me/calendar')[1]['past'] if s['id'] == session['id'])
        self.assertTrue(past['assessment']['open'])
        self.assertTrue(past['canGiveFeedback'])
        self.assertEqual(voter.request(f'me/sessions/{session["id"]}/questions', {'body': 'Too late?'})[0], 409, 'Q&A closes 30 minutes after the session.')

        base = {k: session[k] for k in ('id', 'title', 'kind', 'capacity')}
        self.assertEqual(self.admin.request('manage/sessions', {**base, 'startsAt': at(-120), 'endsAt': at(-60), 'recordingUrl': 'ftp://example.com/rec.mp4'})[0], 400)
        self.assertEqual(self.admin.request('manage/sessions', {**base, 'startsAt': at(-120), 'endsAt': at(-60), 'recordingUrl': 'https://example.com/recording.mp4'})[0], 200)
        self.assertIn('Recording available: Q&A webinar', self.titles(voter))
        self.assertEqual(next(s for s in voter.request('me/calendar')[1]['past'] if s['id'] == session['id'])['recordingUrl'], 'https://example.com/recording.mp4')
        self.assertNotIn('recordingUrl', next(s for s in outsider.request('me/calendar')[1]['past'] if s['id'] == session['id']) if any(
            s['id'] == session['id'] for s in outsider.request('me/calendar')[1]['past']) else {}, 'Recordings are for participants only.')

    def test_scheduled_reminders_send_the_most_urgent_one_once(self):
        session = self.session('Reminder webinar')
        learner = self.account(name='Reminder Learner')
        learner.request(f'me/sessions/{session["id"]}/register', {})
        start = datetime.strptime(session['startsAt'], '%Y-%m-%dT%H:%M')
        with closing(connect(self.db_path)) as db, db:
            live_training.process(db, start - timedelta(hours=30))
            live_training.process(db, start - timedelta(hours=20))
            live_training.process(db, start - timedelta(hours=20))
            live_training.process(db, start - timedelta(minutes=50))
            live_training.process(db, start - timedelta(minutes=10))
        titles = self.titles(learner)
        self.assertEqual(titles.count('Reminder webinar starts tomorrow.'), 1)
        self.assertIn('Reminder webinar starts in 1 hour.', titles)
        self.assertIn('Reminder webinar starts in 15 minutes. You can join now.', titles)

    def test_older_database_gains_webinar_type_and_live_training_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.sqlite3'
            sql = (BACKEND / 'database/schema.sql').read_text(encoding='utf-8').replace("CHECK(kind IN ('session','workshop','webinar'))", "CHECK(kind IN ('session','workshop'))")
            initialize(path)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('PRAGMA foreign_keys=OFF')
                db.execute('DROP TABLE training_sessions')
                start = sql.index('CREATE TABLE IF NOT EXISTS training_sessions')
                db.executescript(sql[start:sql.index(');', start) + 2])
                db.execute("INSERT INTO training_sessions(id,title,kind,starts_at,ends_at,capacity,created_at) VALUES ('old','Old workshop','workshop','2030-01-01T10:00','2030-01-01T11:00',5,'2029-01-01')")
                db.execute('PRAGMA user_version=12')
            initialize(path)
            with closing(connect(path)) as db:
                row = db.execute("SELECT * FROM training_sessions WHERE id='old'").fetchone()
                self.assertEqual((row['title'], row['delivery'], row['qa_enabled']), ('Old workshop', 'in_person', 1))
                self.assertIn("'webinar'", db.execute("SELECT sql FROM sqlite_master WHERE name='training_sessions'").fetchone()[0])
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()
