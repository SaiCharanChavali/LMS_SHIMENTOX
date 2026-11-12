"""Learning activity history over real HTTP: event tracking, de-duplication, employee and staff views, access rules and analytics."""
from contextlib import closing
import copy
import json
import uuid

from test_portal import PortalFixture, Client
from database import connect, CURRICULUM
import activity

AGILE = 'agile-and-scrum'
JAVA = 'java-full-stack-development'


class LearningActivityTests(PortalFixture):
    # ---------------------------------------------------------------- helpers

    def account(self, role='employee', name='Activity Member', **org):
        client = Client(self.base)
        client.email = f'{uuid.uuid4().hex}@shimentox.com'
        result = self.admin.request('admin/candidates', {'name': name, 'email': client.email, 'password': 'Temporary123!', **org})
        self.assertEqual(result[0], 200, result[1])
        client.id = result[1]['candidate']['id']
        if role != 'employee':
            with closing(connect(self.db_path)) as db, db:
                db.execute('UPDATE candidates SET role=? WHERE id=?', (role, client.id))
        client.request('auth/login', {'email': client.email, 'password': 'Temporary123!'})
        self.assertEqual(client.request('auth/password', {'currentPassword': 'Temporary123!', 'password': 'Learning123!'})[0], 200)
        return client

    def module_course(self, title):
        source = next(c for c in self.admin.request('admin/courses')[1]['courses'] if c['id'] == 'python-programming')
        saved = self.admin.request('admin/courses', {'title': title, 'description': f'{title} course.', 'category': 'Technical Skills',
                                                     'status': 'published', 'content': copy.deepcopy(source['content'])})
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['course']['id']

    def open_course(self, client, course):
        status, body, _ = client.request('learning/enroll', {'courseId': course, 'open': True})
        self.assertEqual(status, 200, body)
        return body

    def complete_module_course(self, client, course):
        self.open_course(client, course)
        for s in range(3):
            self.prepare(client, s)
            attempt = client.action('exam-start', setIndex=s)[1]['attempt']
            result = client.action('exam-finish', attemptId=attempt['id'], answers=[q[2] for q in CURRICULUM[s]['exam']])
            self.assertEqual(result[1]['attempt']['status'], 'passed', result[1])
        return attempt

    def events(self, employee, kind=None, course=None):
        with closing(connect(self.db_path)) as db:
            sql, params = 'SELECT * FROM learning_activity_logs WHERE employee_id=?', [employee]
            if kind:
                sql += ' AND activity_type=?'
                params.append(kind)
            if course:
                sql += ' AND course_id=?'
                params.append(course)
            return [dict(r) for r in db.execute(sql + ' ORDER BY activity_timestamp,created_at', params)]

    def age_events(self, employee, seconds):
        """Move an employee's events into the past, as if time had passed since they happened."""
        with closing(connect(self.db_path)) as db, db:
            for row in db.execute('SELECT id,activity_timestamp FROM learning_activity_logs WHERE employee_id=?', (employee,)).fetchall():
                from datetime import datetime, timedelta
                moment = datetime.fromisoformat(row[1].replace('Z', '+00:00')) - timedelta(seconds=seconds)
                db.execute('UPDATE learning_activity_logs SET activity_timestamp=? WHERE id=?', (activity.stamp(moment), row[0]))

    def assessment(self, **fields):
        body = {'title': 'Activity check', 'kind': 'knowledge', 'passPercent': 60, 'maxAttempts': 3, 'questionCount': 3, 'timeLimitMinutes': 10,
                'status': 'published', 'questions': [[f'Question {i}?', ['Right', 'Wrong'], 0, 'Right is right.'] for i in range(5)]}
        body.update(fields)
        saved = self.admin.request('manage/assessments', body)
        self.assertEqual(saved[0], 200, saved[1])
        return saved[1]['assessment']['id']

    def take(self, client, identity, correct=True):
        attempt = client.request(f'me/assessments/{identity}/start', {})[1]['attempt']
        answers = [q['options'].index('Right' if correct else 'Wrong') for q in attempt['questions']]
        body = {'attemptId': attempt['id'], 'answers': answers}
        return attempt, client.request(f'me/assessments/{identity}/submit', body), body

    # ---------------------------------------------------------------- tracking

    def test_course_open_start_resume_and_duplicate_opens(self):
        learner = self.account(name='Open Learner')
        course = self.module_course('Activity open course')
        self.open_course(learner, course)
        self.assertEqual([e['activity_type'] for e in self.events(learner.id, course=course)], ['course_started'])
        # A repeated request (double click, retry, reload) inside the visit window is one visit.
        self.open_course(learner, course)
        self.open_course(learner, course)
        # Loading the course without the user opening it (background load at sign-in) is not an activity.
        learner.request('learning/enroll', {'courseId': course})
        learner.request(f'learning?courseId={course}')
        self.assertEqual(len(self.events(learner.id, course=course)), 1)
        # Coming back later without progress is a revisit; after progress it is a resume.
        self.age_events(learner.id, 3600)
        self.open_course(learner, course)
        self.assertEqual(self.events(learner.id, course=course)[-1]['activity_type'], 'course_opened')
        self.age_events(learner.id, 3600)
        self.assertEqual(learner.action('video', videoIndex=0, watched=48, complete=True)[0], 200)
        self.open_course(learner, course)
        kinds = [e['activity_type'] for e in self.events(learner.id, course=course)]
        self.assertEqual(kinds, ['course_started', 'course_opened', 'lesson_completed', 'course_resumed'])
        lesson = json.loads(self.events(learner.id, 'lesson_completed', course)[0]['metadata'])
        self.assertEqual((lesson['videoIndex'], bool(lesson['lessonTitle'])), (0, True))
        # Re-sending the same completed video does not record the lesson twice.
        learner.action('video', videoIndex=0, watched=48, complete=True)
        self.assertEqual(len(self.events(learner.id, 'lesson_completed', course)), 1)

    def test_module_course_exams_completion_and_certificate(self):
        learner = self.account(name='Module Learner')
        course = self.module_course('Activity module course')
        self.open_course(learner, course)
        self.prepare(learner, 0)
        failed = learner.action('exam-start', setIndex=0)[1]['attempt']
        wrong = [(q[2] + 1) % len(q[1]) for q in CURRICULUM[0]['exam']]
        self.assertEqual(learner.action('exam-finish', attemptId=failed['id'], answers=wrong)[1]['attempt']['status'], 'failed')
        # Replaying the finished submission changes nothing and records nothing new.
        before = len(self.events(learner.id))
        learner.action('exam-finish', attemptId=failed['id'], answers=[q[2] for q in CURRICULUM[0]['exam']])
        self.assertEqual(len(self.events(learner.id)), before)
        terminated = learner.action('exam-start', setIndex=0)[1]['attempt']
        learner.action('exam-finish', attemptId=terminated['id'], terminate=True)
        last = self.complete_module_course(learner, course)
        counts = {}
        for e in self.events(learner.id, course=course):
            counts[e['activity_type']] = counts.get(e['activity_type'], 0) + 1
        self.assertEqual(counts['course_started'], 1)
        self.assertEqual(counts['lesson_completed'], 6)
        self.assertEqual(counts['assessment_started'], 5, 'Failed, terminated and three passing attempts were started.')
        self.assertEqual(counts['assessment_submitted'], 4, 'A terminated attempt was never submitted.')
        self.assertEqual(counts['assessment_failed'], 1)
        self.assertEqual(counts['assessment_passed'], 3)
        self.assertEqual(counts['course_completed'], 1)
        self.assertEqual(counts['certificate_generated'], 1)
        result = json.loads(self.events(learner.id, 'assessment_failed', course)[0]['metadata'])
        self.assertEqual((result['kind'], result['result'], result['percent'] < result['passPercent']), ('exam', 'failed', True))
        # Activity logging did not change progress, scoring or the certificate rules.
        learning = learner.request(f'learning?courseId={course}')[1]['learning']
        self.assertIsNotNone(learning['run']['completedAt'])
        self.assertEqual([a['status'] for a in learning['run']['attempts'][0]], ['failed', 'terminated', 'passed'])
        self.assertEqual(learner.action('exam-finish', attemptId=last['id'])[1]['attempt']['status'], 'passed')
        self.assertEqual(self.events(learner.id, 'course_completed', course)[0]['activity_timestamp'], learning['run']['completedAt'])

    def test_lesson_course_lessons_quizzes_and_assignments(self):
        learner = self.account(name='Lesson Learner')
        self.open_course(learner, AGILE)
        first, second = f'{AGILE}-lesson-01', f'{AGILE}-lesson-02'
        learner.action('lesson-open', lessonId=first)
        learner.action('lesson-open', lessonId=first)
        self.assertEqual([e['activity_type'] for e in self.events(learner.id, course=AGILE) if e['lesson_id']], ['lesson_started'])
        self.age_events(learner.id, 3600)
        learner.action('lesson-open', lessonId=first)
        learner.action('lesson-open', lessonId=second)
        self.assertEqual(learner.action('lesson', lessonId=first)[0], 200)
        learner.action('lesson', lessonId=first)  # Saving the lesson again is not a second completion.
        kinds = [(e['activity_type'], e['lesson_id']) for e in self.events(learner.id, course=AGILE) if e['lesson_id']]
        self.assertEqual(kinds, [('lesson_started', first), ('lesson_opened', first), ('lesson_started', second), ('lesson_completed', first)])
        self.assertEqual(json.loads(self.events(learner.id, 'lesson_completed', AGILE)[0]['metadata'])['lessonTitle'], 'Introduction to Agile')

        # Knowledge checks (one submission each) and the assignment that follows the first Java module.
        self.open_course(learner, JAVA)
        lesson = f'{JAVA}-module-01'
        with closing(connect(self.db_path)) as db:
            quiz = json.loads(db.execute('SELECT quiz_json FROM course_lessons WHERE id=?', (lesson,)).fetchone()[0])
        wrong = [(q[2] + 1) % len(q[1]) for q in quiz]
        self.assertFalse(learner.action('lesson-quiz', lessonId=lesson, answers=wrong)[1]['quizResult']['passed'])
        self.assertTrue(learner.action('lesson-quiz', lessonId=lesson, answers=[q[2] for q in quiz])[1]['quizResult']['passed'])
        results = [e['activity_type'] for e in self.events(learner.id, course=JAVA) if e['activity_type'] in ('assessment_passed', 'assessment_failed', 'lesson_completed')]
        self.assertEqual(results, ['assessment_failed', 'assessment_passed', 'lesson_completed'])
        checkpoint = learner.request(f'learning?courseId={JAVA}')[1]['learning']['run']['checkpoints'][0]
        started = learner.action('checkpoint-start', checkpointId=checkpoint['id'])
        self.assertEqual(started[0], 200, started[1])
        with closing(connect(self.db_path)) as db:
            questions = json.loads(db.execute('SELECT questions_json FROM checkpoint_attempts WHERE id=?', (started[1]['attempt']['id'],)).fetchone()[0])
        finished = learner.action('checkpoint-finish', attemptId=started[1]['attempt']['id'], answers=[q['correct'] for q in questions])
        self.assertEqual(finished[1]['attempt']['status'], 'passed')
        assignment = [json.loads(e['metadata']) for e in self.events(learner.id, course=JAVA) if json.loads(e['metadata']).get('kind') == 'assignment']
        self.assertEqual([m.get('result') for m in assignment], [None, 'passed', 'passed'])
        for event in self.events(learner.id):
            self.assertNotIn('answers', event['metadata'])
            self.assertNotIn('correct', event['metadata'])

    def test_standalone_assessments_and_resources(self):
        learner = self.account(name='Assessment Learner')
        identity = self.assessment(title='Activity standalone check')
        attempt, passed, body = self.take(learner, identity)
        self.assertEqual(passed[1]['result']['status'], 'passed')
        # A retried submission is rejected and records nothing.
        self.assertEqual(learner.request(f'me/assessments/{identity}/submit', body)[0], 409)
        self.assertEqual(self.take(learner, identity, correct=False)[1][1]['result']['status'], 'failed')
        rows = [e for e in self.events(learner.id) if e['assessment_id'] == identity]
        self.assertEqual([e['activity_type'] for e in rows], ['assessment_started', 'assessment_submitted', 'assessment_passed',
                                                              'assessment_started', 'assessment_submitted', 'assessment_failed'])
        meta = json.loads(rows[2]['metadata'])
        self.assertEqual((meta['percent'], meta['passPercent'], meta['assessmentTitle']), (100, 60, 'Activity standalone check'))
        # Opening a learning material is recorded through the server, which returns the address to open.
        course = self.module_course('Activity resource course')
        self.assertEqual(self.admin.request(f'manage/courses/{course}/resources', {'title': 'Activity guide', 'kind': 'link', 'url': 'https://example.com/activity'})[0], 200)
        resource = self.open_course(learner, course) and learner.request(f'learning?courseId={course}')[1]['resources'][0]
        opened = learner.request(f'me/resources/{resource["id"]}/open', {})
        self.assertEqual(opened[1], {'url': 'https://example.com/activity'})
        learner.request(f'me/resources/{resource["id"]}/open', {})
        self.assertEqual(len(self.events(learner.id, 'resource_accessed')), 1, 'A repeated click is one access.')
        self.assertEqual(learner.request(f'me/resources/{uuid.uuid4()}/open', {})[0], 404)

    def test_logging_failure_never_blocks_learning(self):
        with closing(connect(self.db_path)) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT INTO development_records VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), next(iter(db.execute("SELECT id FROM candidates WHERE role='admin'")))[0], 'Kept record', '', '2026-01-01', 1, activity.stamp()))
            # An event for an unknown employee violates the foreign key; it is dropped, and the surrounding work survives.
            self.assertFalse(activity.record(db, 'missing-employee', 'course_opened', 'x'))
            with self.assertRaises(ValueError):
                activity.record(db, 'missing-employee', 'not_a_type', 'x')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM development_records WHERE title='Kept record'").fetchone()[0], 1)
            db.rollback()

    def test_backfill_copies_existing_history_once(self):
        learner = self.account(name='Backfill Learner')
        course = self.module_course('Activity backfill course')
        self.complete_module_course(learner, course)
        with closing(connect(self.db_path)) as db, db:
            live = db.execute('SELECT activity_type,dedupe_key,activity_timestamp FROM learning_activity_logs WHERE employee_id=? AND course_id=? ORDER BY dedupe_key', (learner.id, course)).fetchall()
            db.execute("DELETE FROM learning_activity_logs WHERE employee_id=? AND activity_type NOT IN ('course_opened','course_resumed','lesson_opened')", (learner.id,))
            activity.backfill(db)
            activity.backfill(db)
            copied = db.execute('SELECT activity_type,dedupe_key,activity_timestamp FROM learning_activity_logs WHERE employee_id=? AND course_id=? ORDER BY dedupe_key', (learner.id, course)).fetchall()
            self.assertEqual([tuple(r[:2]) for r in copied], [tuple(r[:2]) for r in live], 'Backfill rebuilds the same events, each once.')
            meta = [json.loads(r[0]) for r in db.execute("SELECT metadata FROM learning_activity_logs WHERE employee_id=? AND activity_type<>'course_opened'", (learner.id,))]
            self.assertTrue(meta and all(m.get('backfilled') for m in meta))

    # ---------------------------------------------------------------- employee view

    def test_employee_history_filters_pagination_privacy_and_persistence(self):
        learner = self.account(name='History Learner')
        other = self.account(name='History Other')
        course = self.module_course('Activity history course')
        self.complete_module_course(learner, course)
        identity = self.assessment(title='Activity history check')
        self.take(learner, identity)
        self.take(other, identity)
        status, history, _ = learner.request('me/history')
        self.assertEqual(status, 200)
        mine = len(self.events(learner.id))
        self.assertEqual(history['total'], mine)
        self.assertEqual(len(history['items']), 20)
        self.assertEqual(history['pages'], -(-mine // 20))
        self.assertEqual(history['items'][0]['label'], 'Assessment passed')
        second = learner.request('me/history?page=2')[1]
        self.assertEqual(len(second['items']), mine - 20)
        self.assertFalse({i['id'] for i in second['items']} & {i['id'] for i in history['items']})
        # Filters run on the server.
        passed = learner.request('me/history?type=assessment_passed')[1]
        self.assertEqual(passed['total'], 4)
        self.assertTrue(all(i['type'] == 'assessment_passed' and i['status'] == 'passed' for i in passed['items']))
        self.assertEqual(learner.request('me/history?type=lesson')[1]['total'], 6)
        self.assertEqual(learner.request(f'me/history?course={course}&type=assessment_started')[1]['total'], 3)
        self.assertEqual(learner.request('me/history?from=2099-01-01')[1]['total'], 0)
        today = history['items'][0]['at'][:10]
        self.assertEqual(learner.request(f'me/history?from={today}&to={today}')[1]['total'], mine)
        self.assertIn(course, [c['id'] for c in history['courses']])
        for bad in ('type=keystrokes', 'from=yesterday', 'from=2026-05-02&to=2026-05-01', 'page=x'):
            self.assertEqual(learner.request(f'me/history?{bad}')[0], 400, bad)
        # An employee sees only their own history, whatever they ask for.
        self.assertEqual(learner.request(f'me/history?employee={other.id}')[1]['total'], mine)
        self.assertEqual(learner.request('manage/activity')[0], 403)
        self.assertEqual(learner.request(f'manage/activity/employees/{other.id}')[0], 403)
        self.assertEqual(learner.request('manage/activity/analytics')[0], 403)
        # History is stored on the server, so it is the same after signing out and in again.
        self.assertEqual(learner.request('auth/logout', {})[0], 200)
        self.assertEqual(learner.request('me/history')[0], 401)
        learner.request('auth/login', {'email': learner.email, 'password': 'Learning123!'})
        self.assertEqual(learner.request('me/history')[1]['total'], mine)

    # ---------------------------------------------------------------- HR, admin and manager views

    def test_staff_activity_scope_filters_and_summary(self):
        org = self.admin.request('manage/org')[1]
        engineering = next(d['id'] for d in org['departments'] if d['name'] == 'Engineering')
        sales = next(d['id'] for d in org['departments'] if d['name'] == 'Sales')
        manager = self.account('manager', 'Activity Manager')
        member = self.account(name='Activity Team Member', managerId=manager.id, departmentId=engineering)
        outsider = self.account(name='Activity Outsider', departmentId=sales)
        hr = self.account('hr', 'Activity HR')
        course = self.module_course('Activity staff course')
        self.complete_module_course(member, course)
        self.open_course(outsider, course)

        # Managers see their direct reports only, enforced by the server.
        team = manager.request(f'manage/activity?course={course}')[1]
        self.assertEqual(team['scope'], 'team')
        self.assertEqual({i['employeeId'] for i in team['items']}, {member.id})
        self.assertNotIn(outsider.id, [p['id'] for p in team['options']['employees']])
        self.assertEqual(manager.request(f'manage/activity?employee={outsider.id}')[0], 403)
        self.assertEqual(manager.request(f'manage/activity/employees/{outsider.id}')[0], 403)
        detail = manager.request(f'manage/activity/employees/{member.id}')[1]
        self.assertEqual(detail['employee']['name'], 'Activity Team Member')
        self.assertEqual(detail['total'], len(self.events(member.id)))

        # HR and admins see the organisation; department and date filters narrow it.
        for staff in (hr, self.admin):
            everyone = staff.request(f'manage/activity?course={course}')[1]
            self.assertEqual(everyone['scope'], 'organisation')
            self.assertEqual({i['employeeId'] for i in everyone['items']}, {member.id, outsider.id})
        sales_rows = hr.request(f'manage/activity?course={course}&department={sales}')[1]
        self.assertEqual({i['employeeId'] for i in sales_rows['items']}, {outsider.id})
        self.assertEqual(hr.request(f'manage/activity?course={course}&from=2099-01-01')[1]['total'], 0)
        searched = hr.request(f'manage/activity?course={course}&q=outsid')[1]
        self.assertEqual({i['employeeId'] for i in searched['items']}, {outsider.id})
        self.assertEqual(hr.request(f'manage/activity?course={course}&q=%25')[1]['total'], 0, 'Wildcards in a search are matched literally.')
        self.assertEqual(manager.request(f'manage/activity?course={course}&q=outsid')[1]['total'], 0, 'Search never widens a manager\'s scope.')
        self.assertEqual(hr.request(f'manage/activity?course={course}&jobRole={uuid.uuid4()}')[1]['total'], 0)
        row = next(i for i in everyone['items'] if i['type'] == 'assessment_passed')
        self.assertEqual((row['employee'], row['department'], row['progress'], row['status']), ('Activity Team Member', 'Engineering', 100, 'passed'))
        self.assertEqual(self.account('trainer', 'Activity Trainer').request('manage/activity')[0], 403)

        # Summary metrics equal counts taken directly from the stored rows.
        summary = hr.request(f'manage/activity?course={course}')[1]['summary']
        with closing(connect(self.db_path)) as db:
            rows = db.execute('SELECT * FROM learning_activity_logs WHERE course_id=?', (course,)).fetchall()
        attempts = {json.loads(r['metadata'])['attempt'] for r in rows if r['activity_type'] in ('assessment_started', 'assessment_submitted')}
        self.assertEqual(summary, {'totalActivities': len(rows), 'activeLearners': len({r['employee_id'] for r in rows}), 'coursesAccessed': 1,
                                   'lessonsCompleted': sum(r['activity_type'] == 'lesson_completed' for r in rows), 'assessmentsAttempted': len(attempts),
                                   'coursesCompleted': sum(r['activity_type'] == 'course_completed' for r in rows)})
        self.assertEqual(summary['activeLearners'], 2)
        self.assertEqual(summary['coursesCompleted'], 1)

    def test_analytics_from_recorded_activity(self):
        org = self.admin.request('manage/org')[1]
        marketing = next(d['id'] for d in org['departments'] if d['name'] == 'Marketing')
        finisher = self.account(name='Analytics Finisher', departmentId=marketing)
        starter = self.account(name='Analytics Starter', departmentId=marketing)
        idle = self.account(name='Analytics Idle', departmentId=marketing)
        course = self.module_course('Activity analytics course')
        self.complete_module_course(finisher, course)
        self.open_course(starter, course)
        # The starter stopped long ago: older than the inactivity threshold, so the start counts as abandoned.
        self.age_events(starter.id, 45 * 86400)
        result = self.admin.request(f'manage/activity/analytics?department={marketing}')[1]
        accessed = next(c for c in result['mostAccessed'] if c['courseId'] == course)
        self.assertEqual(accessed['learners'], 2)
        self.assertEqual(next(c for c in result['mostCompleted'] if c['courseId'] == course)['learners'], 1)
        drop = next(c for c in result['abandonment'] if c['courseId'] == course)
        self.assertEqual((drop['started'], drop['completed'], drop['abandoned'], drop['rate']), (2, 1, 1, 50))
        exams = [r for r in result['assessmentResults'] if r['course'] == 'Activity analytics course']
        self.assertEqual(sum(r['passed'] for r in exams), 3)
        self.assertEqual({r['passRate'] for r in exams}, {100})
        rate = next(c for c in result['attemptRates'] if c['courseId'] == course)
        self.assertEqual((rate['accessed'], rate['attempted'], rate['rate']), (2, 1, 50))
        self.assertTrue(any(p['course'] == 'Activity analytics course' and p['completed'] == 1 for p in result['lessonPatterns']))
        self.assertEqual(sum(result['completionsByWeekday']), 6)
        inactive = {p['employeeId'] for p in result['inactive']}
        self.assertTrue({idle.id, starter.id} <= inactive)
        self.assertNotIn(finisher.id, inactive)
        department = next(d for d in result['departments'] if d['department'] == 'Marketing')
        # The starter's activity 45 days ago is inside the default 90-day period; the idle employee has none.
        self.assertEqual((department['employees'], department['activeLearners'], department['engagementRate'], department['coursesCompleted']), (3, 2, 67, 1))
        recent = self.admin.request(f'manage/activity/analytics?department={marketing}&from={result["period"]["to"]}')[1]
        self.assertEqual(next(d for d in recent['departments'] if d['department'] == 'Marketing')['activeLearners'], 1)
        self.assertEqual(result['period']['inactiveDays'], 30)
        self.assertIn('not a measure of productivity', result['definitions']['engagement'])
        self.assertEqual(self.admin.request('manage/activity/analytics?inactiveDays=1')[0], 400)
        self.assertEqual(self.admin.request('manage/activity/analytics?from=2026-05-02&to=2026-05-01')[0], 400)
