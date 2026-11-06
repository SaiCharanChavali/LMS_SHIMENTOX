"""Strict course deadlines and automated reminders, over real HTTP and an isolated SQLite database."""
from contextlib import closing
import concurrent.futures
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest.mock
import uuid

from test_portal import PortalFixture, Client
from database import CURRICULUM, SCHEMA_VERSION, connect, initialize
from deadlines import format_deadline, format_span, parse_utc, utc_iso
import reminders

TOOL = Path(__file__).resolve().parents[1] / 'tools/process_reminders.py'


def utc_now():
    return datetime.now(timezone.utc)


class DeadlineFixture(PortalFixture):
    def account(self, name='Deadline Learner', **org):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!', **org})
        self.assertEqual(result[0], 200, result[1])
        client.id = result[1]['candidate']['id']
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})[0], 200)
        return client

    def course(self, title=None):
        source = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == 'python-programming')
        saved = self.admin.request('admin/courses', {'title': title or f'Course {uuid.uuid4().hex[:8]}', 'description': 'A course with a deadline.', 'category': 'Technical Skills', 'status': 'published', 'content': copy.deepcopy(source['content'])})
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['course']['id']

    def complete(self, client, course):
        client.request('learning/enroll', {'courseId': course})
        for s in range(3):
            self.prepare(client, s)
            attempt = client.action('exam-start', setIndex=s)[1]['attempt']
            result = client.action('exam-finish', attemptId=attempt['id'], answers=[q[2] for q in CURRICULUM[s]['exam']])
            self.assertEqual(result[1]['attempt']['status'], 'passed', result[1])

    def assign(self, course, employee, deadline, client=None, mandatory=True, target_type='employee', expected=200):
        result = (client or self.admin).request('manage/assignments', {'courseId': course, 'targetType': target_type, 'targetId': employee, 'mandatory': mandatory, 'deadline': deadline})
        self.assertEqual(result[0], expected, result[1])
        return result[1]

    def in_days(self, days, **more):
        return utc_iso(utc_now() + timedelta(days=days, **more))

    def card(self, client, course):
        return next(c for c in client.request('courses')[1]['courses'] if c['id'] == course)

    def backdate(self, course, deadline_at):
        """Move a deadline past 'now', which the API rightly refuses, to stand in for time passing."""
        with closing(connect(self.db_path)) as db, db:
            db.execute('UPDATE course_assignments SET deadline_at=?,due_date=? WHERE course_id=?', (deadline_at, deadline_at[:10], course))

    def process(self, employee, at):
        with closing(connect(self.db_path)) as db, db:
            return reminders.process_employee(db, employee, at)

    def ledger(self, employee, course):
        with closing(connect(self.db_path)) as db:
            return [dict(r) for r in db.execute('SELECT * FROM deadline_reminders WHERE employee_id=? AND course_id=? ORDER BY id', (employee, course))]

    def sent(self, employee, course):
        return [r['reminder_type'] for r in self.ledger(employee, course) if r['status'] == 'sent']

    def deadline_notes(self, employee):
        with closing(connect(self.db_path)) as db:
            return [dict(r) for r in db.execute("SELECT * FROM notifications WHERE employee_id=? AND kind='deadline' ORDER BY id", (employee,))]


class DeadlineManagementTests(DeadlineFixture):
    def test_admin_sets_exact_deadline_stored_in_utc_and_shown_in_ist(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, '2099-11-08T18:00')
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT * FROM course_assignments WHERE course_id=?', (course,)).fetchone()
        self.assertEqual(row['deadline_at'], '2099-11-08T12:30:00.000Z')
        self.assertEqual(row['original_deadline_at'], '2099-11-08T12:30:00.000Z')
        self.assertEqual(row['due_date'], '2099-11-08')
        card = self.card(learner, course)
        self.assertEqual(card['deadline']['display'], '8 November 2099, 6:00 PM')
        self.assertEqual(card['deadline']['timezone'], 'IST')
        self.assertEqual(card['deadline']['status'], 'not_started')
        self.assertGreater(card['deadline']['remainingSeconds'], 0)
        self.assertTrue(card['assignment']['mandatory'])

    def test_each_employee_can_have_a_different_deadline_and_departments_share_one(self):
        department = next(d['id'] for d in self.admin.request('manage/org')[1]['departments'] if d['name'] == 'Finance')
        common, individual, course = self.account(departmentId=department), self.account(departmentId=department), self.course()
        self.assign(course, department, '2099-06-01T17:00', target_type='department')
        self.assign(course, individual.id, '2099-07-01T09:30')
        self.assertEqual(self.card(common, course)['deadline']['display'], '1 June 2099, 5:00 PM')
        self.assertEqual(self.card(individual, course)['deadline']['display'], '1 July 2099, 9:30 AM')
        view = self.admin.request(f'manage/deadlines?courseId={course}')[1]
        people = {e['employeeId']: e for e in view['employees']}
        self.assertEqual(people[common.id]['source'], 'department')
        self.assertEqual(people[individual.id]['source'], 'employee')
        self.assertEqual(len(view['targets']), 2)

    def test_managers_recommendation_cannot_weaken_mandatory_training(self):
        with closing(connect(self.db_path)) as db:
            department = db.execute("SELECT id FROM departments WHERE name='Sales'").fetchone()[0]
        manager = self.account('Line Manager')
        with closing(connect(self.db_path)) as db, db:
            db.execute("UPDATE candidates SET role='manager' WHERE id=?", (manager.id,))
        report, course = self.account(departmentId=department, managerId=manager.id), self.course()
        self.assign(course, department, '2099-06-01T17:00', target_type='department')
        self.assign(course, report.id, '2099-12-01T17:00', client=manager, mandatory=False)
        card = self.card(report, course)
        self.assertEqual(card['deadline']['display'], '1 June 2099, 5:00 PM')
        self.assertTrue(card['assignment']['mandatory'])

    def test_updating_a_deadline_keeps_the_original_and_validates(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, '2099-01-01T10:00')
        self.assign(course, learner.id, '2099-03-01T10:00')
        with closing(connect(self.db_path)) as db:
            row = db.execute('SELECT * FROM course_assignments WHERE course_id=?', (course,)).fetchone()
            audit = db.execute("SELECT COUNT(*) FROM admin_events WHERE action='course_deadline_changed' AND target_id=?", (row['id'],)).fetchone()[0]
        self.assertEqual(row['original_deadline_at'], '2099-01-01T04:30:00.000Z')
        self.assertEqual(row['deadline_at'], '2099-03-01T04:30:00.000Z')
        self.assertEqual(row['deadline_updated_by'], self.admin.request('session')[1]['user']['id'])
        self.assertEqual(audit, 1)
        self.assertEqual(self.admin.request('manage/deadlines?courseId=' + course)[1]['employees'][0]['originalDisplay'], '1 January 2099, 10:00 AM')
        self.assign(course, learner.id, '2020-01-01T10:00', expected=400)
        self.assign(course, learner.id, 'not a date', expected=400)
        self.assign(course, learner.id, '0001-01-01T00:00', expected=400)
        self.assign(course, learner.id, None, expected=400)

    def test_optional_course_and_overdue_edit_keeps_its_deadline(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, '2099-01-01T10:00', mandatory=False)
        self.assertFalse(self.card(learner, course)['assignment']['mandatory'])
        past = utc_iso(utc_now() - timedelta(hours=1))
        self.backdate(course, past)
        self.assign(course, learner.id, past, mandatory=True)
        self.assertTrue(self.card(learner, course)['assignment']['mandatory'])

    def test_employee_cannot_change_or_read_others_deadlines(self):
        learner, other, course = self.account(), self.account(), self.course()
        self.assign(course, learner.id, '2099-01-01T10:00')
        before = self.card(learner, course)['deadline']['at']
        attempt = {'courseId': course, 'targetType': 'employee', 'targetId': learner.id, 'mandatory': False, 'deadline': '2099-12-31T10:00'}
        self.assertEqual(learner.request('manage/assignments', attempt)[0], 403)
        assignment = self.card(learner, course)['assignment']['assignmentId']
        self.assertEqual(learner.request(f'manage/assignments/{assignment}/delete', {})[0], 403)
        self.assertEqual(learner.request(f'manage/deadlines?courseId={course}')[0], 403)
        self.assertEqual(learner.request('manage/reminders/settings', {'intervalDays': [1], 'dueSoonDays': 1, 'deadlineDay': False, 'overdue': False})[0], 403)
        self.assertEqual(learner.request('manage/reminders/run', {})[0], 403)
        self.assertEqual(learner.request('manage/reminders/history')[0], 403)
        self.assertEqual(self.card(learner, course)['deadline']['at'], before)
        self.assertIsNone(self.card(other, course)['deadline'])

    def test_course_cannot_be_completed_by_a_request(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, '2099-01-01T10:00')
        learner.request('learning/enroll', {'courseId': course})
        for action in ('complete', 'finish', 'certificate'):
            self.assertIn(learner.action(action, completed=True, completedAt='2020-01-01T00:00:00Z')[0], (400, 403, 404))
        card = self.card(learner, course)
        self.assertFalse(card['completed'])
        self.assertIsNone(card['deadline']['completedAt'])

    def test_overdue_uses_server_time_and_course_stays_open(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, '2099-01-01T10:00')
        self.backdate(course, utc_iso(utc_now() - timedelta(minutes=1)))
        card = self.card(learner, course)
        self.assertEqual(card['deadline']['status'], 'overdue')
        self.assertEqual(card['status'], 'overdue')
        self.assertLess(card['deadline']['remainingSeconds'], 0)
        self.assertEqual(learner.request('learning/enroll', {'courseId': course})[0], 200)
        self.assertEqual(learner.request(f'learning?courseId={course}')[0], 200)
        self.prepare(learner, 0)
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'overdue')
        compliance = self.admin.request('manage/reports?type=compliance&export=1')[1]
        self.assertTrue(any(r['course'] == card['title'] and r['status'] == 'Overdue' for r in compliance['rows']))

    def test_status_follows_progress_and_the_approaching_deadline(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, self.in_days(30))
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'not_started')
        learner.request('learning/enroll', {'courseId': course})
        self.prepare(learner, 0)
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'in_progress')
        self.backdate(course, self.in_days(2))
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'due_soon')

    def test_completed_on_time_records_server_timestamp(self):
        learner, course = self.account(), self.course()
        deadline = self.in_days(5)
        self.assign(course, learner.id, deadline)
        started = utc_now()
        self.complete(learner, course)
        card = self.card(learner, course)
        self.assertEqual(card['deadline']['status'], 'completed_on_time')
        self.assertEqual(card['deadline']['label'], 'Completed On Time')
        self.assertLessEqual(abs((parse_utc(card['deadline']['completedAt']) - started).total_seconds()), 120)
        with closing(connect(self.db_path)) as db:
            run = db.execute('SELECT * FROM course_runs WHERE candidate_id=? AND course_id=?', (learner.id, course)).fetchone()
        self.assertEqual(run['completed_at'], card['deadline']['completedAt'])
        self.assertEqual(run['deadline_at_completion'], parse_utc(deadline).isoformat(timespec='milliseconds').replace('+00:00', 'Z'))

    def test_completed_late_stays_late_when_the_deadline_is_extended_afterwards(self):
        learner, course = self.account(), self.course()
        self.assign(course, learner.id, self.in_days(5))
        self.backdate(course, utc_iso(utc_now() - timedelta(days=1)))
        self.complete(learner, course)
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'completed_late')
        self.assign(course, learner.id, self.in_days(30))
        self.assertEqual(self.card(learner, course)['deadline']['status'], 'completed_late', 'Late completion is a permanent record.')
        people = self.admin.request(f'manage/deadlines?courseId={course}')[1]['employees']
        self.assertEqual(people[0]['status'], 'completed_late')
        self.assertIsNotNone(people[0]['completedDisplay'])

    def test_notification_read_flow_and_course_link(self):
        learner, course = self.account(), self.course('Data Privacy and Protection Test')
        deadline = utc_now() + timedelta(days=10)
        self.assign(course, learner.id, utc_iso(deadline))
        self.process(learner.id, deadline - timedelta(days=2))
        data = learner.request('me/notifications')[1]
        note = next(n for n in data['notifications'] if n['title'] == 'Course Deadline Reminder')
        self.assertEqual(note['link'], f'course:{course}')
        self.assertIn('"Data Privacy and Protection Test" must be completed by', note['body'])
        self.assertIn('Current progress: 0%', note['body'])
        self.assertIn('Time remaining: 2 days', note['body'])
        self.assertIn('Please complete the remaining lessons before the deadline.', note['body'])
        self.assertEqual(learner.request('me/notifications/unread')[1]['unread'], data['unread'])
        after = learner.request('me/notifications/read', {'ids': [note['id']]})[1]
        self.assertEqual(after['unread'], data['unread'] - 1)
        self.assertIsNotNone(next(n for n in after['notifications'] if n['id'] == note['id'])['readAt'])


class ReminderTests(DeadlineFixture):
    def setup_assignment(self, days=30):
        learner, course = self.account(), self.course()
        deadline = utc_now().replace(microsecond=0) + timedelta(days=days)
        self.assign(course, learner.id, utc_iso(deadline))
        return learner, course, deadline

    def test_course_assigned_notifies_immediately_and_once(self):
        learner, course, deadline = self.setup_assignment()
        self.assertEqual(self.sent(learner.id, course), ['assigned'])
        self.process(learner.id, utc_now())
        self.assertEqual(self.sent(learner.id, course), ['assigned'])
        titles = [n['title'] for n in learner.request('me/notifications')[1]['notifications']]
        self.assertEqual(sum(t.startswith('Mandatory training assigned') for t in titles), 1)

    def test_reminders_trigger_at_the_correct_times(self):
        learner, course, deadline = self.setup_assignment()
        day_of = reminders.deadline_day_at(deadline)
        expected = [(deadline - timedelta(days=7, minutes=1), []), (deadline - timedelta(days=7), ['before_7d']), (deadline - timedelta(days=3), ['before_3d']),
                    (deadline - timedelta(days=1), ['before_1d']), (day_of, ['deadline_day']), (deadline - timedelta(seconds=1), []), (deadline, ['overdue'])]
        seen = ['assigned']
        for at, new in expected:
            self.process(learner.id, at)
            seen += new
            self.assertEqual(self.sent(learner.id, course), seen, at)
        rows = {r['reminder_type']: r for r in self.ledger(learner.id, course)}
        self.assertEqual(rows['before_3d']['scheduled_at'], utc_iso(deadline - timedelta(days=3)))
        self.assertEqual(rows['overdue']['deadline_at'], utc_iso(deadline))
        self.assertEqual(rows['before_3d']['assignment_id'], self.card(learner, course)['assignment']['assignmentId'])
        self.assertIsNotNone(rows['before_3d']['sent_at'])
        self.assertIsNotNone(rows['before_3d']['notification_id'])
        notes = self.deadline_notes(learner.id)
        self.assertEqual([n['title'] for n in notes], ['Course Deadline Reminder'] * 3 + ['Course Deadline Today', f'Overdue: {self.card(learner, course)["title"]}'])
        self.assertIn('Overdue by', notes[-1]['body'])

    def test_deadline_day_reminder_time(self):
        evening = parse_utc('2026-11-08T18:00')
        early = parse_utc('2026-11-08T07:00')
        self.assertEqual(reminders.deadline_day_at(evening), parse_utc('2026-11-08T09:00'))
        self.assertEqual(reminders.deadline_day_at(early), parse_utc('2026-11-08T00:00'))

    def test_short_deadline_sends_only_applicable_reminders(self):
        learner, course, deadline = self.setup_assignment(days=2)
        self.process(learner.id, utc_now() + timedelta(minutes=1))
        self.assertEqual(self.sent(learner.id, course), ['assigned'], 'The 7-day and 3-day reminders never applied.')
        self.process(learner.id, deadline - timedelta(days=1))
        self.assertEqual(self.sent(learner.id, course), ['assigned', 'before_1d'])

    def test_downtime_sends_one_catch_up_not_a_backlog(self):
        learner, course, deadline = self.setup_assignment()
        self.process(learner.id, deadline - timedelta(hours=20))
        self.assertEqual(self.sent(learner.id, course), ['assigned', 'before_1d'])

    def test_completed_course_stops_reminders(self):
        learner, course, deadline = self.setup_assignment()
        self.complete(learner, course)
        for at in (deadline - timedelta(days=3), deadline - timedelta(days=1), deadline + timedelta(days=2)):
            self.process(learner.id, at)
        self.assertEqual(self.sent(learner.id, course), ['assigned'])
        self.assertEqual(self.deadline_notes(learner.id), [])

    def test_running_twice_creates_no_duplicates(self):
        learner, course, deadline = self.setup_assignment()
        at = deadline - timedelta(days=3)
        first = self.process(learner.id, at)
        second = self.process(learner.id, at)
        self.assertEqual(first['sent'], 1)
        self.assertEqual(second['sent'], 0)
        self.assertEqual(len(self.deadline_notes(learner.id)), 1)
        self.assertEqual(reminders.run_pass(self.db_path, at)['failed'], 0)
        self.assertEqual(len(self.deadline_notes(learner.id)), 1)

    def test_overlapping_passes_create_no_duplicates(self):
        learner, course, deadline = self.setup_assignment()
        at = deadline - timedelta(days=3)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            summaries = list(pool.map(lambda _: reminders.run_pass(self.db_path, at), range(4)))
        self.assertEqual(sum(s['errors'] for s in summaries), 0)
        self.assertEqual(len(self.deadline_notes(learner.id)), 1)

    def test_deadline_change_recalculates_future_reminders(self):
        learner, course, deadline = self.setup_assignment(days=10)
        self.process(learner.id, deadline - timedelta(days=7))
        self.assertEqual(self.sent(learner.id, course), ['assigned', 'before_7d'])
        moved = deadline + timedelta(days=20)
        self.assign(course, learner.id, utc_iso(moved))
        self.assertEqual(self.sent(learner.id, course)[-1], 'deadline_changed', 'The employee is told at once.')
        self.assertIn(format_deadline(utc_iso(moved), ' at '), self.deadline_notes(learner.id)[-1]['body'])
        self.process(learner.id, deadline - timedelta(days=3))
        self.assertEqual(self.sent(learner.id, course)[-1], 'deadline_changed', 'The old deadline no longer triggers anything.')
        self.process(learner.id, moved - timedelta(days=7))
        self.assertEqual(self.sent(learner.id, course)[-1], 'before_7d')
        self.assertEqual(self.ledger(learner.id, course)[-1]['deadline_at'], utc_iso(moved))

    def test_overdue_extension_allows_a_new_overdue_later(self):
        learner, course, deadline = self.setup_assignment(days=3)
        self.process(learner.id, deadline + timedelta(hours=1))
        self.assertEqual(self.sent(learner.id, course)[-1], 'overdue')
        extended = utc_now() + timedelta(days=4)
        self.assign(course, learner.id, utc_iso(extended))
        self.process(learner.id, extended + timedelta(hours=1))
        self.assertEqual(self.sent(learner.id, course).count('overdue'), 2)

    def test_failure_is_recorded_and_retried_without_duplicates(self):
        learner, course, deadline = self.setup_assignment()
        at = deadline - timedelta(days=3)
        with unittest.mock.patch('reminders.deliver_in_app', side_effect=RuntimeError('Delivery unavailable')):
            self.assertEqual(self.process(learner.id, at)['failed'], 1)
        row = self.ledger(learner.id, course)[-1]
        self.assertEqual((row['status'], row['failure_reason'], row['attempts']), ('failed', 'Delivery unavailable', 1))
        self.assertIsNone(row['sent_at'])
        self.assertEqual(self.deadline_notes(learner.id), [])
        self.assertEqual(self.process(learner.id, at + timedelta(minutes=1))['sent'], 0, 'Not retried before the backoff ends.')
        self.assertEqual(self.process(learner.id, parse_utc(row['next_attempt_at']))['sent'], 1)
        row = self.ledger(learner.id, course)[-1]
        self.assertEqual((row['status'], row['failure_reason'], row['attempts']), ('sent', None, 2))
        self.assertEqual(len(self.deadline_notes(learner.id)), 1)

    def test_retries_stop_after_the_limit_and_when_the_deadline_changes(self):
        learner, course, deadline = self.setup_assignment()
        at = deadline - timedelta(days=3)
        with unittest.mock.patch('reminders.deliver_in_app', side_effect=RuntimeError('Down')) as failing:
            for i in range(reminders.MAX_ATTEMPTS + 2):
                self.process(learner.id, at + timedelta(days=i % 3, hours=i * 6))
                row = next(r for r in self.ledger(learner.id, course) if r['reminder_type'] == 'before_3d')
                if row['next_attempt_at']:
                    at = parse_utc(row['next_attempt_at'])
            self.assertLessEqual(row['attempts'], reminders.MAX_ATTEMPTS)
            self.assertTrue(failing.called)
        moved = utc_now() + timedelta(days=60)
        self.assign(course, learner.id, utc_iso(moved))
        self.process(learner.id, utc_now())
        self.assertFalse([r for r in self.ledger(learner.id, course) if r['status'] in ('failed', 'pending') and r['deadline_at'] != utc_iso(moved)])

    def test_removed_assignment_and_inactive_employee_get_nothing(self):
        learner, course, deadline = self.setup_assignment()
        assignment = self.card(learner, course)['assignment']['assignmentId']
        self.assertEqual(self.admin.request(f'manage/assignments/{assignment}/delete', {})[0], 200)
        self.process(learner.id, deadline - timedelta(days=1))
        self.assertEqual(self.deadline_notes(learner.id), [])
        history = self.ledger(learner.id, course)
        self.assertEqual([r['reminder_type'] for r in history], ['assigned'], 'History remains after the assignment is removed.')

    def test_new_department_member_is_told_on_the_next_pass(self):
        department = next(d['id'] for d in self.admin.request('manage/org')[1]['departments'] if d['name'] == 'Marketing')
        course = self.course()
        self.assign(course, department, self.in_days(30), target_type='department')
        joiner = self.account(departmentId=department)
        self.assertEqual(self.sent(joiner.id, course), [])
        reminders.run_pass(self.db_path)
        self.assertEqual(self.sent(joiner.id, course), ['assigned'])

    def test_configurable_intervals(self):
        original = self.admin.request('manage/reminders/settings')[1]['settings']
        self.addCleanup(self.admin.request, 'manage/reminders/settings', {k: original[k] for k in ('intervalDays', 'dueSoonDays', 'deadlineDay', 'overdue')})
        self.assertEqual(original['intervalDays'], [7, 3, 1])
        for bad in ({'intervalDays': [0], 'dueSoonDays': 7, 'deadlineDay': True, 'overdue': True}, {'intervalDays': [1], 'dueSoonDays': 0, 'deadlineDay': True, 'overdue': True},
                    {'intervalDays': 'seven', 'dueSoonDays': 7, 'deadlineDay': True, 'overdue': True}, {'intervalDays': [1], 'dueSoonDays': 7, 'deadlineDay': 'yes', 'overdue': True}):
            self.assertEqual(self.admin.request('manage/reminders/settings', bad)[0], 400)
        saved = self.admin.request('manage/reminders/settings', {'intervalDays': [2, 14, 2], 'dueSoonDays': 2, 'deadlineDay': False, 'overdue': False})
        self.assertEqual(saved[1]['settings']['intervalDays'], [14, 2])
        learner, course, deadline = self.setup_assignment()
        self.assertEqual(self.card(learner, course)['deadline']['dueSoonSeconds'], 2 * 86400)
        for at in (deadline - timedelta(days=14), deadline - timedelta(days=7), deadline - timedelta(days=2), reminders.deadline_day_at(deadline), deadline + timedelta(days=1)):
            self.process(learner.id, at)
        self.assertEqual(self.sent(learner.id, course), ['assigned', 'before_14d', 'before_2d'])

    def test_administrator_can_run_a_pass_and_read_history(self):
        learner, course, deadline = self.setup_assignment()
        result = self.admin.request('manage/reminders/run', {})
        self.assertEqual(result[0], 200, result[1])
        self.assertIn('sent', result[1]['summary'])
        self.assertIsNotNone(result[1]['settings']['lastRunAt'])
        history = self.admin.request(f'manage/reminders/history?courseId={course}')[1]['history']
        self.assertEqual(history[0]['employeeId'], learner.id)
        self.assertEqual(history[0]['type'], 'assigned')
        self.assertEqual(history[0]['status'], 'sent')
        self.assertEqual(Client(self.base).request('manage/reminders/run', {})[0], 401)

    def test_scheduler_runs_with_no_browser_or_employee_activity(self):
        department = next(d['id'] for d in self.admin.request('manage/org')[1]['departments'] if d['name'] == 'Human Resources')
        course = self.course()
        self.assign(course, department, self.in_days(30), target_type='department')
        joiner = self.account(departmentId=department)
        stop = reminders.start_scheduler(self.db_path, 1)
        self.addCleanup(stop.set)
        limit = time.time() + 20
        while time.time() < limit and not self.sent(joiner.id, course):
            time.sleep(0.2)
        self.assertEqual(self.sent(joiner.id, course), ['assigned'])

    def test_time_text(self):
        self.assertEqual(format_span(2 * 86400), '2 days')
        self.assertEqual(format_span(2 * 86400 + 4 * 3600 + 120), '2 days, 4 hours')
        self.assertEqual(format_span(86400 + 3 * 3600), '1 day, 3 hours')
        self.assertEqual(format_span(3600 + 60), '1 hour, 1 minute')
        self.assertEqual(format_span(300), '5 minutes')
        self.assertEqual(format_span(10), 'less than a minute')
        self.assertEqual(format_deadline('2026-11-08T12:30:00.000Z'), '8 November 2026, 6:00 PM')


class ReminderCommandTests(DeadlineFixture):
    def run_tool(self, *args, path=None):
        env = {**os.environ, 'LMS_DB_PATH': str(path or self.db_path)}
        return subprocess.run([sys.executable, str(TOOL), *args], env=env, capture_output=True, text=True, timeout=120)

    def test_command_processes_previews_and_is_idempotent(self):
        learner, course = self.account(), self.course()
        deadline = utc_now() + timedelta(days=10)
        self.assign(course, learner.id, utc_iso(deadline))
        future = utc_iso(deadline - timedelta(days=3)).replace('.000', '')
        preview = self.run_tool('--dry-run', '--now', future)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('before_3d', [item['type'] for item in json.loads(preview.stdout)['due']])
        self.assertEqual(self.sent(learner.id, course), ['assigned'], 'A dry run writes nothing.')
        guarded = self.run_tool('--now', future)
        self.assertEqual(guarded.returncode, 2)
        self.assertIn('--now requires --dry-run', guarded.stderr)
        first, second = self.run_tool(), self.run_tool()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(second.stdout)['sent'], 0)


class DeadlineMigrationTests(DeadlineFixture):
    def test_version_8_database_upgrades_in_place_keeping_all_records(self):
        path = Path(self.temp.name) / f'{uuid.uuid4().hex}.sqlite3'
        initialize(path)
        with closing(connect(path)) as db, db:
            db.execute("INSERT INTO candidates(id,full_name,email,password_hash,created_at,updated_at,role) VALUES ('old','Old Learner','old@test.com','x','2026-01-01','2026-01-01','employee')")
            db.execute("INSERT INTO course_runs(id,candidate_id,course_id,run_number,started_at,completed_at) VALUES ('old-run','old','python-programming',1,'2026-01-01T00:00:00.000Z','2026-01-05T00:00:00.000Z')")
            db.execute("INSERT INTO notifications(employee_id,kind,title,dedupe_key,created_at) VALUES ('old','assignment','Assigned','assigned:old-assignment:2026-03-01:1','2026-01-01')")
            db.execute("INSERT INTO course_assignments(id,course_id,target_type,target_id,mandatory,due_date,assigned_at) VALUES ('old-assignment','python-programming','employee','old',1,'2026-03-01','2026-01-01T00:00:00.000Z')")
            db.execute('DROP TABLE deadline_reminders')
            db.execute('DROP TABLE reminder_settings')
            for table, column in (('course_assignments', 'deadline_at'), ('course_assignments', 'original_deadline_at'), ('course_assignments', 'deadline_updated_at'), ('course_assignments', 'deadline_updated_by'), ('course_runs', 'deadline_at_completion')):
                db.execute(f'ALTER TABLE {table} DROP COLUMN {column}')
            db.execute('PRAGMA user_version=8')
        backup = path.with_suffix('.backup')
        shutil.copy(path, backup)
        initialize(path)
        initialize(path)
        with closing(connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
            row = db.execute("SELECT * FROM course_assignments WHERE id='old-assignment'").fetchone()
            self.assertEqual(row['due_date'], '2026-03-01')
            # A date-only deadline became overdue the day after it, so it now ends at 23:59:59 IST on that date.
            self.assertEqual(row['deadline_at'], '2026-03-01T18:29:59.000Z')
            self.assertEqual(row['original_deadline_at'], row['deadline_at'])
            self.assertEqual(db.execute("SELECT completed_at FROM course_runs WHERE id='old-run'").fetchone()[0], '2026-01-05T00:00:00.000Z')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM candidates WHERE id='old'").fetchone()[0], 1)
            self.assertEqual(reminders.settings(db)['intervalDays'], [7, 3, 1])
            db.execute('BEGIN IMMEDIATE')
            counts = reminders.process_employee(db, 'old')
            db.commit()
            self.assertEqual(counts['sent'], 0, 'Completed before the upgrade, so no reminders are due.')
            db.execute("UPDATE course_runs SET completed_at=NULL WHERE id='old-run'")
            db.commit()
            db.execute('BEGIN IMMEDIATE')
            reminders.process_employee(db, 'old')
            db.commit()
            kinds = [r[0] for r in db.execute("SELECT reminder_type FROM deadline_reminders WHERE employee_id='old'")]
            self.assertEqual(kinds, ['overdue'], 'An employee already told about the assignment is not told again.')
