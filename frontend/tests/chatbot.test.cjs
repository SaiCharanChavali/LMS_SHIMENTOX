// LMS assistant: intent detection, answers from (mocked) LMS APIs per role, course actions and the conversation panel.
// The portal's real scripts are loaded; only the HTTP API is mocked, and every request is recorded so tests can check
// that answers come from the right endpoint and that out-of-role questions never reach the server.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const SCRIPTS = ['auth.js', 'app.js', 'admin.js', 'development.js', 'live-training.js', 'onboarding.js', 'activity.js', 'course-import.js', 'python-practice.js', 'learning.js',
  'chatbot-config.js', 'chatbot-intents.js', 'chatbot-data.js', 'chatbot-responses.js', 'chatbot.js'];
const inDays = days => new Date(Date.now() + days * 86400000).toISOString();

// ---- fixtures: what the real endpoints return (shapes taken from backend/src)
const COURSES = [
  { id: 'sec', title: 'Information Security <b>Basics</b>', category: 'Compliance & Security', description: 'Protect company data.', difficulty: 'beginner', durationMinutes: 45, lessonCount: 4, assessmentCount: 2, format: 'lessons',
    progress: 40, started: true, completed: false, status: 'in_progress', assignment: { mandatory: true }, deadline: { at: inDays(5), display: '25 November 2026, 6:00 PM', timezone: 'IST', status: 'due_soon', label: 'Due Soon' } },
  { id: 'py', title: 'Python Programming', category: 'Technical Skills', description: 'Learn Python.', difficulty: 'intermediate', durationMinutes: 300, lessonCount: 18, assessmentCount: 3, format: 'lessons',
    progress: 0, started: false, completed: false, status: 'not_started', assignment: { mandatory: false }, deadline: { at: inDays(20), display: '10 December 2026, 6:00 PM', timezone: 'IST', status: 'not_started', label: 'Not Started' } },
  { id: 'posh', title: 'POSH Awareness', category: 'Compliance & Security', description: 'Workplace conduct.', difficulty: 'beginner', durationMinutes: 60, lessonCount: 5, assessmentCount: 1, format: 'lessons',
    progress: 70, started: true, completed: false, status: 'overdue', assignment: { mandatory: true }, deadline: { at: inDays(-3), display: '17 November 2026, 6:00 PM', timezone: 'IST', status: 'overdue', label: 'Overdue' } },
  { id: 'agile', title: 'Agile and Scrum', category: 'Professional Development', description: 'Agile basics.', difficulty: 'beginner', durationMinutes: 90, lessonCount: 6, assessmentCount: 1, format: 'lessons',
    progress: 100, started: true, completed: true, status: 'completed', assignment: null, deadline: null },
  { id: 'genai', title: 'Generative AI Foundations', category: 'Generative AI & Automation', description: 'Prompting.', difficulty: 'beginner', durationMinutes: 120, lessonCount: 8, assessmentCount: 2, format: 'lessons',
    progress: 0, started: false, completed: false, status: 'not_started', assignment: null, deadline: null },
];
const ASSESSMENTS = [
  { id: 'a1', title: 'Security final assessment', kind: 'post', course: 'Information Security Basics', courseId: 'sec', passPercent: 70, maxAttempts: 3, questionCount: 10, timeLimitMinutes: 15, attempts: [{ status: 'failed', percent: 50 }], passed: false, best: 50, attemptsLeft: 2 },
  { id: 'a2', title: 'Agile check', kind: 'knowledge', course: 'Agile and Scrum', courseId: 'agile', passPercent: 60, maxAttempts: 3, questionCount: 5, timeLimitMinutes: 10, attempts: [{ status: 'passed', percent: 80 }], passed: true, best: 80, attemptsLeft: 2 },
];
const complianceRow = (employee, course, status, extra = {}) => ({ employeeId: employee.toLowerCase(), employee, email: `${employee.toLowerCase()}@shimentox.com`, department: 'Finance', courseId: course.toLowerCase(), course,
  mandatory: true, deadlineAt: inDays(-2), deadlineDisplay: '18 November 2026, 6:00 PM', progress: 20, status, statusLabel: { overdue: 'Overdue', in_progress: 'In Progress', not_started: 'Not Started', completed_on_time: 'Completed On Time' }[status], overdueBy: status === 'overdue' ? '2 days' : null, ...extra });

function makeServer() {
  const requests = [];
  const server = { user: null, requests, compliance: null };
  server.fetch = async (url, options) => {
    const path = url.replace(/^\/?api\//, '');  // '/api/x' here, 'api/x' when the LMS is served under /lms.
    requests.push(path);
    let result, status = 200;
    const team = server.user?.role === 'manager' ? 'team' : 'organisation';
    if (path === 'session') result = { user: server.user, csrfToken: 'csrf', setupRequired: false, setupAllowed: true, apiVersion: 15 };
    else if (path === 'courses') result = { courses: COURSES };
    else if (path === 'certificates') result = { certificates: [{ id: 'c1', courseTitle: 'Agile and Scrum', courseId: 'agile', completedAt: '2026-11-01T10:00:00Z' }] };
    else if (path === 'me/assessments') result = { assessments: ASSESSMENTS };
    else if (path === 'me/calendar') result = { sessions: [{ id: 's1', title: 'Secure coding workshop', startsAt: inDays(3), trainer: 'Ravi', course: 'Information Security Basics', seatsLeft: 4 }], past: [] };
    else if (path.startsWith('manage/compliance')) {
      if (!['manager', 'hr', 'admin'].includes(server.user.role)) { status = 403; result = { error: 'You do not have permission to view training compliance.' }; }
      else {
        const all = server.compliance || [complianceRow('Asha', 'Security', 'overdue'), complianceRow('Ravi', 'Security', 'in_progress', { deadlineAt: inDays(4) }), complianceRow('Meena', 'POSH', 'not_started', { deadlineAt: inDays(9) }), complianceRow('Asha', 'POSH', 'completed_on_time')];
        const params = new URLSearchParams(path.split('?')[1] || ''), q = (params.get('q') || '').toLowerCase(), st = params.get('status');
        const rows = all.filter(r => (!st || r.status === st || (st === 'completed' && r.status.startsWith('completed'))) && (!q || r.employee.toLowerCase().includes(q)));
        const count = s => rows.filter(r => r.status === s).length;
        result = { scope: team, updatedDisplay: '20 November 2026, 10:00 AM', summary: { total: rows.length, completed: rows.filter(r => r.status.startsWith('completed')).length, completedOnTime: count('completed_on_time'), completedLate: 0, inProgress: count('in_progress'), notStarted: count('not_started'), overdue: count('overdue'), completionRate: rows.length ? Math.round(rows.filter(r => r.status.startsWith('completed')).length / rows.length * 100) : 0 },
          departments: [{ department: 'Finance', total: rows.length, completed: 1, pending: 2, overdue: count('overdue'), completionRate: 25 }], table: { rows, total: rows.length, page: 1, pages: 1 }, overdue: { rows: rows.filter(r => r.status === 'overdue'), mandatory: count('overdue') } };
      }
    } else if (path === 'admin/courses') result = { courses: [{ id: 'py', title: 'Python Programming', status: 'published', learners: 4, resources: [{}], assignments: 2 }, { id: 'draft', title: 'Draft course', status: 'draft', learners: 0, resources: [], assignments: 0 }] };
    else if (path === 'manage/assignments') result = { assignments: [{ id: 'x', mandatory: true, deadlineAt: inDays(-1), employees: 3, completed: 1 }, { id: 'y', mandatory: false, deadlineAt: null, employees: 1, completed: 0 }] };
    else if (path.startsWith('manage/reports')) result = { total: 2, rows: [{ employee: 'Asha', course: 'Python Programming', department: 'Finance', progress: 60, status: 'In progress', dueDate: '' }, { employee: 'Ravi', course: 'Python Programming', department: 'Sales', progress: 100, status: 'Completed', dueDate: '' }] };
    else if (path.startsWith('learning/enroll')) result = { learning: { run: { id: 'r1', lessons: {} }, certificates: [] } };
    else if (path.startsWith('learning?')) result = { course: [], lessons: [], courseInfo: { id: 'sec', title: 'Information Security Basics', format: 'lessons' }, learning: { run: { id: 'r1', lessons: {} }, certificates: [] }, resources: [], assessments: [], courseLessons: [] };
    else if (path.startsWith('learning/resume')) result = { learning: { run: { id: 'r1', lessons: {} }, certificates: [] } };
    else if (path.startsWith('me/') || path.startsWith('manage/')) result = {};
    else throw Error('Unexpected API request: ' + path);
    return { ok: status < 400, status, json: async () => JSON.parse(JSON.stringify(result)) };
  };
  return server;
}

function makeContext(server) {
  const store = new Map();
  const classes = () => ({ add() {}, remove() {}, toggle() {}, contains: () => false });
  const app = { innerHTML: '' }, elements = {};
  const context = {
    document: { getElementById: id => (id === 'app' ? app : !app.innerHTML.includes(`id="${id}"`) ? null : (elements[id] ||= { id, innerHTML: '', textContent: '', value: '', style: {}, dataset: {}, classList: classes(), addEventListener() {}, querySelector: () => null, focus() {} })), querySelector: () => null, querySelectorAll: () => [], body: { classList: classes() }, addEventListener() {}, documentElement: {}, title: '' },
    location: { hash: '#dashboard', search: '', pathname: '/' }, window: { addEventListener() {}, scrollTo() {}, matchMedia: () => ({ matches: false }) },
    sessionStorage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k), key: i => [...store.keys()][i] },
    localStorage: { getItem: () => null, setItem() {} }, fetch: server.fetch, Intl, Date, URL, URLSearchParams, setTimeout, clearTimeout, setInterval: () => 1, performance: { now: () => 0 },
  };
  Object.defineProperty(context.sessionStorage, 'length', { get: () => store.size });
  context.sessionStorage[Symbol.iterator] = undefined;
  vm.createContext(context);
  // Object.keys(sessionStorage) in the panel lists stored conversations; mirror the Map's keys onto the object.
  context.__store = store;
  for (const file of SCRIPTS) vm.runInContext(fs.readFileSync(__dirname + '/../public/scripts/' + file, 'utf8'), context, { filename: file });
  return { context, run: code => vm.runInContext(code, context), app, store };
}

async function signIn(env, server, role) {
  await new Promise(resolve => setTimeout(resolve, 30));  // Let the portal's own start-up (session check) finish first.
  server.user = { id: `${role}-1`, name: `Test ${role[0].toUpperCase()}${role.slice(1)}`, email: `${role}@shimentox.com`, role, mustChangePassword: false };
  env.run(`currentUser=${JSON.stringify(server.user)};csrfToken='csrf';portalReady=true;firstAdminSetup=false;courseCatalog=[];`);
  server.requests.length = 0;
}
const settle = () => new Promise(resolve => setTimeout(resolve, 450));
const lastBot = env => env.run('JSON.stringify([...chatbot.state.messages].reverse().find(m=>m.from==="bot"))');
const reply = env => JSON.parse(lastBot(env));
const ask = async (env, text) => { await env.run(`chatHandleText(${JSON.stringify(text)})`); await settle(); return reply(env); };
const press = async (env, label) => {
  const m = reply(env), option = [...(m.options || []), ...(m.more ? [m.more] : [])].find(o => o.label === label) || (m.items || []).map(i => ({ label: i.actionLabel, action: i.action })).find(o => o.label === label);
  assert.ok(option, `Button "${label}" in: ${[...(m.options || [])].map(o => o.label).join(' | ')}`);
  await env.run(`chatPerform(${JSON.stringify(option.action)},${JSON.stringify(option.label)})`); await settle(); return reply(env);
};

async function main() {
  // ---------------------------------------------------------------- intent detection
  {
    const server = makeServer(), env = makeContext(server);
    const detect = (role, text, courses = COURSES) => JSON.parse(env.run(`JSON.stringify(detectIntent(${JSON.stringify(text)},{role:${JSON.stringify(role)},courses:${JSON.stringify(courses)}}))`));
    const expect = [
      ['employee', 'Show my pending courses', 'MY_PENDING_COURSES'], ['employee', 'what courses are still pending for me?', 'MY_PENDING_COURSES'], ['employee', 'show my pendng cources', 'MY_PENDING_COURSES'],
      ['employee', 'Where can I find my certificates?', 'NAVIGATE_TO_CERTIFICATES'], ['employee', 'my certificates', 'MY_CERTIFICATES'], ['employee', 'which courses are assigned to me', 'MY_ASSIGNED_COURSES'],
      ['employee', 'when is my deadline', 'MY_UPCOMING_DEADLINES'], ['employee', 'any overdue training?', 'MY_OVERDUE_TRAINING'], ['employee', 'how am I doing', 'MY_LEARNING_PROGRESS'],
      ['employee', 'what have I completed', 'MY_COMPLETED_COURSES'], ['employee', 'show my completed courses', 'MY_COMPLETED_COURSES'], ['employee', 'Help me find courses', 'FIND_COURSE'],
      ['employee', 'show me compliance courses', 'FIND_COURSE'], ['employee', 'did i pass my exam', 'ASSESSMENT_STATUS'], ['employee', 'when is my assessment due', 'ASSESSMENT_DEADLINE'],
      ['employee', 'open assessments', 'NAVIGATE_TO_ASSESSMENTS'], ['employee', 'any workshops coming up?', 'FIND_TRAINING'], ['employee', 'mandatory training', 'MY_MANDATORY'],
      ['employee', 'I want to practise', 'PRACTICE_QUESTIONS'], ['employee', 'hello', 'HELP'], ['employee', 'thanks!', 'THANKS'], ['employee', 'what is the weather today', 'OUT_OF_SCOPE'],
      ['employee', 'apply for leave', 'OUT_OF_SCOPE'], ['employee', 'what is this portal about', 'LMS_OVERVIEW'], ['employee', 'training policies', 'TRAINING_POLICIES'],
      ['manager', 'Which employees have overdue training?', 'TEAM_OVERDUE_TRAINING'], ['manager', "my team's learning progress", 'TEAM_LEARNING_PROGRESS'], ['manager', 'my pending courses', 'MY_PENDING_COURSES'],
      ['manager', 'what training does my team need to complete', 'TEAM_COURSE_ASSIGNMENTS'], ['hr', 'show training compliance', 'TRAINING_COMPLIANCE'], ['hr', 'training for Asha Rao', 'EMPLOYEE_TRAINING'],
      ['hr', 'training by department', 'DEPARTMENT_TRAINING'], ['hr', 'how do I assign a course', 'TRAINING_ASSIGNMENTS'], ['admin', 'how do i create a course', 'COURSE_MANAGEMENT'],
      ['admin', 'export reports', 'TRAINING_REPORTS'], ['trainer', 'courses I teach', 'TRAINER_COURSES'], ['trainer', 'learner progress', 'TRAINER_LEARNERS'],
    ];
    for (const [role, text, intent] of expect) { const r = detect(role, text); assert.equal(r.type === 'intent' ? r.intent : JSON.stringify(r), intent, `${role}: "${text}"`); }
    // A course is recognised from the user's own course list, not a fixed list.
    let r = detect('employee', 'how long is python programming');
    assert.equal(r.intent, 'COURSE_DURATION'); assert.equal(r.course.id, 'py');
    r = detect('employee', 'what lessons are in generative ai foundations'); assert.equal(r.intent, 'COURSE_CONTENT'); assert.equal(r.course.id, 'genai');
    r = detect('employee', 'Python Programming'); assert.equal(r.intent, 'COURSE_DETAILS', 'A course name on its own asks for its details.');
    r = detect('employee', 'how long is python programming', []); assert.equal(r.course, null, 'No course list, no course match.');
    // Ambiguity: a manager's "pending courses" could be theirs or their team's.
    r = detect('manager', 'pending courses'); assert.deepEqual([r.type, r.choices], ['clarify', ['MY_PENDING_COURSES', 'TEAM_PENDING_TRAINING']]);
    r = detect('employee', 'pending courses'); assert.equal(r.intent, 'MY_PENDING_COURSES', 'Employees have no team, so there is nothing to clarify.');
    // Unknown and generic input never matches by accident.
    for (const text of ['asdf qwer', 'in', 'my', 'do', 'the', 'banana bread recipe']) assert.equal(detect('employee', text).type, 'unknown', text);
    // An employee asking about other people's records gets the team intent, which their role cannot use (answered below).
    assert.equal(detect('employee', 'who has overdue training').intent, 'TEAM_OVERDUE_TRAINING');
    // Every intent in the configuration has an answer, and every suggestion is a real intent.
    const missing = JSON.parse(env.run('JSON.stringify(CHAT_INTENTS.filter(i=>!CHAT_HANDLERS[i.id]).map(i=>i.id))'));
    assert.deepEqual(missing, []);
    assert.equal(env.run('Object.values(CHAT_SUGGESTIONS).flat().every(id=>chatIntent(id)&&CHAT_HANDLERS[id])'), true);
    console.log(`PASS assistant intent detection: ${expect.length} phrasings, misspellings, course names, ambiguity, unknown input`);
  }

  // ---------------------------------------------------------------- employee: real data, flows and buttons
  {
    const server = makeServer(), env = makeContext(server);
    await signIn(env, server, 'employee');
    let m = await ask(env, 'Show my pending courses');
    assert.equal(m.text, 'Sure! Would you like to see all pending courses or only mandatory training?');
    assert.deepEqual(m.options.map(o => o.label), ['All Pending Courses', 'Mandatory Training', 'Upcoming Deadlines']);
    m = await press(env, 'All Pending Courses');
    assert.deepEqual(m.items.map(i => i.title), ['POSH Awareness', 'Information Security <b>Basics</b>', 'Python Programming'], 'Pending, nearest deadline first, from the API.');
    assert.ok(m.items[1].meta.includes('Due 25 November 2026, 6:00 PM IST') && m.items[1].meta.includes('40% complete') && m.items[1].meta.includes('Mandatory'));
    assert.deepEqual(m.items[1].action, { kind: 'course', id: 'sec' });
    assert.ok(server.requests.includes('courses'));
    m = await ask(env, 'show my mandatory training');
    assert.deepEqual(m.items.map(i => i.title), ['POSH Awareness', 'Information Security <b>Basics</b>']);
    m = await ask(env, 'upcoming deadlines');
    assert.deepEqual(m.items.map(i => i.title), ['Information Security <b>Basics</b>', 'Python Programming']); assert.ok(m.text.includes('1 overdue course'));
    m = await ask(env, 'anything overdue?'); assert.deepEqual(m.items.map(i => i.title), ['POSH Awareness']);
    m = await ask(env, 'my learning progress'); assert.ok(m.text.startsWith('Your learning: 1 of 4 courses completed, 2 in progress, 1 overdue. Average progress 53%.'), m.text);
    m = await ask(env, 'completed courses'); assert.deepEqual(m.items.map(i => i.title), ['Agile and Scrum']);
    m = await ask(env, 'my certificates'); assert.ok(m.text.includes('1 certificate') && m.items[0].title === 'Agile and Scrum');
    m = await ask(env, 'Where can I find my certificates?');
    assert.ok(m.text.startsWith('You can access your certificates from the Certificates section.')); assert.ok(m.options.some(o => o.label === 'Open Certificates'));
    m = await press(env, 'Open Certificates'); assert.equal(env.context.location.hash, 'certificates', 'The button opens the page.');
    m = await ask(env, 'Help me find courses');
    assert.equal(m.text, 'What type of course are you looking for?');
    assert.ok(m.options.some(o => o.label === 'Compliance & Security (2)') && m.options.some(o => o.label === 'Browse all courses'));
    m = await press(env, 'Compliance & Security (2)');
    assert.deepEqual(m.items.map(i => i.title).sort(), ['Information Security <b>Basics</b>', 'POSH Awareness']);
    m = await ask(env, 'how long is python programming'); assert.equal(m.text, '“Python Programming” takes about 5 h across 18 lessons.');
    m = await ask(env, 'what level is the generative ai foundations course'); assert.ok(m.text.includes('Beginner level'));
    m = await ask(env, 'how long does it take');  // No course named and none open: ask which one.
    assert.ok(m.text.startsWith('Which course do you mean?')); assert.equal(env.run('chatbot.state.expect.type'), 'course');
    m = await ask(env, 'POSH Awareness'); assert.equal(m.text, '“POSH Awareness” takes about 1 h across 5 lessons.');
    m = await ask(env, 'did i pass my exam'); assert.ok(m.text.includes('1 passed out of 2 assessments attempted'));
    m = await ask(env, 'when is my assessment due'); assert.ok(m.text.includes('do not have deadlines of their own') && m.items[0].title === 'Security final assessment');
    m = await ask(env, 'any workshops?'); assert.equal(m.items[0].title, 'Secure coding workshop');
    m = await ask(env, 'training policies'); assert.ok(m.text.includes("doesn't keep a separate policy library") && m.items.length === 2);
    // Out-of-role questions are refused without asking the server for other people's records.
    server.requests.length = 0;
    m = await ask(env, 'who has overdue training');
    assert.ok(m.text.startsWith('Team overdue training is available to managers, HR and administrators.')); assert.deepEqual(m.options.map(o => o.label), ['My overdue training']);
    assert.ok(!server.requests.some(p => p.startsWith('manage/')), 'No team request is made for an employee.');
    m = await ask(env, 'training compliance'); assert.ok(m.text.includes('available to managers, HR and administrators'));
    // Unknown questions: the fallback text and buttons from the specification.
    m = await ask(env, 'banana bread recipe');
    assert.equal(m.text, "I'm sorry, I couldn't understand that question. You can choose one of the options below or try asking differently.");
    assert.deepEqual(m.options.map(o => o.label), ['My Courses', 'Learning Progress', 'Training Deadlines', 'Help']);
    m = await press(env, 'Learning Progress'); assert.ok(m.text.startsWith('Your learning:'));
    m = await ask(env, 'what is my salary'); assert.ok(m.text.startsWith("That's outside what I can help with."));
    // A server failure becomes a plain message with a retry button, not a crash.
    const original = server.fetch; server.fetch = async () => ({ ok: false, status: 500, json: async () => ({ error: 'Database is busy' }) }); env.context.fetch = server.fetch;
    m = await ask(env, 'my certificates'); assert.ok(m.text.includes("couldn't load that just now") && m.text.includes('Database is busy') && m.options[0].label === 'Try again');
    server.fetch = original; env.context.fetch = original;
    console.log('PASS assistant for employees: pending flow, mandatory, deadlines, progress, certificates, course facts, refusals and fallback');
  }

  // ---------------------------------------------------------------- manager, HR, admin and trainer
  {
    const server = makeServer(), env = makeContext(server);
    await signIn(env, server, 'manager');
    let m = await ask(env, 'Which employees have overdue training?');
    assert.ok(server.requests.some(p => p.startsWith('manage/compliance?') && p.includes('status=overdue')));
    assert.ok(m.text.startsWith('1 assigned course is overdue for your team'), m.text); assert.equal(m.items[0].title, 'Asha — Security'); assert.ok(m.items[0].meta.includes('Overdue by 2 days'));
    m = await ask(env, 'pending courses'); assert.equal(m.text, "Do you mean your own learning or your team's?");
    m = await press(env, 'Team pending courses'); assert.ok(m.text.startsWith('2 assigned courses are pending for your team (1 in progress, 1 not started)'), m.text);
    m = await ask(env, "my team's progress"); assert.ok(m.text.includes('1 of 4 assigned courses completed (25%)') && m.items.some(i => i.title === 'Asha'));
    m = await ask(env, 'what training does my team need'); assert.ok(m.text.startsWith('Training required for your team') && m.items.some(i => i.title === 'Security'));
    m = await ask(env, 'my pending courses'); assert.equal(m.text, 'Sure! Would you like to see all pending courses or only mandatory training?', 'Managers still see their own learning.');

    await signIn(env, server, 'hr'); env.run('chatNewConversation(false)');
    m = await ask(env, 'show training compliance'); assert.ok(m.text.startsWith('Training compliance for the organisation') && m.text.includes('25% complete'));
    m = await ask(env, 'training for Asha'); assert.ok(server.requests.some(p => p.includes('q=asha'))); assert.ok(m.text.startsWith('Training for Asha: 1 of 2 courses completed.'));
    m = await ask(env, 'training for someone'); m = await ask(env, 'nobody-by-this-name');
    assert.ok(m.text.includes('couldn\'t find assigned training for “nobody-by-this-name”'));
    m = await ask(env, 'training by department'); assert.equal(m.items[0].title, 'Finance');
    m = await ask(env, 'how do I assign a course'); assert.ok(m.text.includes('2 course assignments (1 mandatory, 1 past their deadline') && m.text.includes('To assign a course:'));
    m = await press(env, 'Assign a course'); assert.equal(env.context.location.hash, 'admin-courses'); assert.equal(env.run('courseTab'), 'assignments');

    await signIn(env, server, 'admin'); env.run('chatNewConversation(false)');
    m = await ask(env, 'how do i create a course'); assert.ok(m.text.startsWith('The LMS has 2 courses: 1 published, 1 draft, 0 archived.') && m.text.includes('To create a course:'));
    m = await press(env, 'Create a course'); assert.equal(env.context.location.hash, 'admin-courses'); assert.ok(env.run('courseDraft!==null'), 'The course wizard opens.');
    m = await ask(env, 'reports'); assert.ok(m.text.includes('4 assignments in the organisation') && m.options.some(o => o.label === 'Open Reports & Analytics'));
    m = await ask(env, 'how do I use the LMS?'); assert.ok(m.options.some(o => o.label === 'Deadline reminders'));
    m = await press(env, 'Deadline reminders'); assert.ok(m.text.startsWith('Deadline reminders:\n1. Open Manage Courses → Reminders.'));

    await signIn(env, server, 'trainer'); env.run('chatNewConversation(false)');
    m = await ask(env, 'courses I teach'); assert.ok(m.text.includes('trainer or owner of 2 courses') && m.items[0].meta.includes('4 learners'));
    m = await ask(env, 'learner progress'); assert.ok(server.requests.some(p => p.startsWith('manage/reports?type=enrollments'))); assert.equal(m.items.length, 2);
    server.requests.length = 0;
    m = await ask(env, 'training compliance'); assert.ok(m.text.includes('not') || m.text.includes('available to'), m.text); assert.ok(!server.requests.some(p => p.startsWith('manage/compliance')), 'Trainers do not query Training Compliance.');
    console.log('PASS assistant for managers, HR, admins and trainers: team scope, clarification, compliance, search, guidance and actions');
  }

  // ---------------------------------------------------------------- course page actions (summarise, explain, practice, revision)
  {
    const server = makeServer(), env = makeContext(server);
    await signIn(env, server, 'employee');
    const extras = { resources: [{ id: 'r1', title: 'Security handbook', kind: 'document' }], requiredAssessmentId: 'a1',
      assessments: [{ id: 'a1', title: 'Security final assessment', kind: 'post', passPercent: 70, attemptsLeft: 2, best: 50, passed: false }, { id: 'k1', title: 'Phishing check', kind: 'knowledge', passPercent: 60, attemptsLeft: 3, best: null, passed: false }],
      courseLessons: [
        { id: 'l1', title: 'Phishing', moduleTitle: 'Module 1: Threats', content: '## Learning objectives\n- Spot a phishing email\n- Report it quickly\n\n## Details\nPhishing is a fake message that tricks you into sharing passwords. Always check the sender.', assessmentId: 'k1', quiz: [{}, {}], resources: [], documentUrl: 'api/materials/x', documentName: 'Phishing guide.pdf' },
        { id: 'l2', title: 'Passwords', moduleTitle: 'Module 1: Threats', content: 'Use a password manager. Multi-factor authentication adds a second check.', assessmentId: null, quiz: [], resources: [{ title: 'NCSC advice', url: 'https://x' }], exercise: 'Set up MFA.' },
        { id: 'l3', title: 'Incident response', moduleTitle: 'Module 2: Response', content: '', locked: true, quiz: [], resources: [] }] };
    env.run(`currentCourseInfo={id:'sec',title:'Information Security Basics',format:'lessons'};currentCourseExtras=${JSON.stringify(extras)};learning={run:{id:'r1',lessons:{l1:{completed:true}},attempts:[]},certificates:[]};location.hash='#course';selectedLessonId=null;`);
    env.run("chatbotOpen('summarize')"); await settle();
    let m = reply(env);
    assert.ok(m.text.startsWith('“Information Security Basics”: Protect company data.') && m.text.includes('3 lessons') && m.text.includes('2 modules: Module 1: Threats; Module 2: Response.'), m.text);
    assert.ok(m.options.some(o => o.label === 'Summarise: Phishing') && !m.options.some(o => o.label === 'Summarise: Incident response'), 'Locked lessons are not offered.');
    m = await press(env, 'Summarise: Phishing'); assert.equal(m.text, 'Summary of “Phishing” (Module 1: Threats):\n• Spot a phishing email\n• Report it quickly');
    m = await press(env, 'Explain a concept'); assert.ok(m.text.startsWith('Which concept'));
    m = await ask(env, 'multi-factor authentication');
    assert.equal(m.items[0].title, 'Passwords'); assert.ok(m.items[0].meta.includes('Multi-factor authentication adds a second check.')); assert.deepEqual(m.items[0].action, { kind: 'course', id: 'sec', lesson: 'l2' });
    m = await ask(env, 'explain incident escalation'); assert.ok(m.text.includes("couldn't find “incident escalation”"), 'Locked lesson text is never searched.');
    env.run("chatbotOpen('practice')"); await settle(); m = reply(env);
    assert.deepEqual(m.items.map(i => i.title), ['Phishing', 'Passwords', 'Security final assessment', 'Phishing check']);
    assert.ok(m.items[0].meta.includes('2 quiz questions') && m.items[1].meta.includes('practical exercise'));
    env.run("chatbotOpen('revision')"); await settle(); m = reply(env);
    assert.equal(m.items[0].title, 'Security final assessment'); assert.ok(m.items[0].meta.includes('best 50%, pass mark 70%'));
    assert.ok(m.items.some(i => i.title === 'Passwords' && i.tag === 'Not done') && !m.items.some(i => i.title === 'Phishing' && i.tag === 'Not done'));
    m = await ask(env, 'learning materials'); assert.deepEqual(m.items.map(i => i.title), ['Security handbook', 'Phishing guide.pdf', 'NCSC advice']);
    // Opening a lesson from a button selects it on the course page; a locked one is refused.
    await env.run(`chatPerform({kind:'course',id:'sec',lesson:'l2'},'Open lesson')`); await settle();
    assert.equal(env.run('selectedLessonId'), 'l2'); assert.equal(env.context.location.hash, 'course');
    await env.run(`chatPerform({kind:'course',id:'sec',lesson:'l3'},'Open lesson')`); await settle(); assert.ok(reply(env).text.includes('still locked'));
    // Off the course page, course actions explain how to use them instead of guessing.
    env.run("location.hash='#courses'"); env.run("chatbotOpen('summarize')"); await settle(); assert.ok(reply(env).text.startsWith('Open a course first'));
    console.log('PASS course assistant actions: summary from lesson objectives, explain from lesson text, practice, revision, materials, locked lessons');
  }

  // ---------------------------------------------------------------- panel and conversation
  {
    const server = makeServer(), env = makeContext(server);
    await signIn(env, server, 'employee');
    env.run('chatbotOpen()'); await settle();
    let m = reply(env);
    assert.ok(m.text.startsWith('Hi Test!')); assert.ok(m.options.some(o => o.label === 'My pending courses'));
    // Buttons are shown only on the newest answer; text is escaped.
    await ask(env, 'my pending courses'); await press(env, 'All Pending Courses');
    let html = env.run('chatLogHTML()');
    assert.ok(html.includes('Information Security &lt;b&gt;Basics&lt;/b&gt;') && !html.includes('<b>Basics</b>'), 'Course titles are escaped.');
    assert.equal((html.match(/All Pending Courses<\/button>/g) || []).length, 0, 'Buttons of earlier answers are gone.');
    assert.ok(html.includes('class="chatbot-avatar user"') && html.includes('class="chatbot-avatar bot"'));
    // Kept for the browser session, per user, and cleared at sign-out.
    const key = 'shimentox-lms-chat:employee-1';
    assert.ok(JSON.parse(env.store.get(key)).messages.length >= 4);
    env.run('chatbot.userId=null;chatbot.state={messages:[],expect:null,nextId:1};chatbotSync()');
    assert.ok(env.run('chatbot.state.messages.length') >= 4, 'The conversation is restored after a reload.');
    env.run('chatNewConversation(false)'); assert.equal(env.run('chatbot.state.messages.length'), 0);
    html = env.run('chatLogHTML()'); assert.ok(html.includes('How can I help?') && html.includes('My assigned courses'), 'Cleared: suggestions are shown.');
    await ask(env, 'hello');
    env.run('resetChatbot()'); assert.equal(env.store.has(key), false, 'Sign-out clears stored conversations.');
    // New Chat while an answer is loading drops the stale answer.
    await signIn(env, server, 'employee');
    env.run('chatHandleText("my certificates")'); env.run('chatNewConversation(false)'); await settle();
    assert.equal(env.run('chatbot.state.messages.length'), 0);
    // Not available during an exam or before the password is changed.
    env.run('activeExam={id:"x"}'); assert.equal(env.run('chatbotAvailable()'), false); env.run('activeExam=null');
    env.run('currentUser.mustChangePassword=true'); assert.equal(env.run('chatbotAvailable()'), false); env.run('currentUser.mustChangePassword=false');
    assert.equal(env.run('chatbotAvailable()'), true);
    // Pages the role cannot open are never offered as buttons.
    assert.equal(env.run('chatNavOpt("admin-courses","x")'), null); assert.ok(env.run('chatNavOpt("certificates","x")'));
    console.log('PASS assistant panel: greeting, escaped output, latest buttons only, session history, clear, sign-out, exams');
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
