// ---------------------------------------------------------------- LMS assistant: answers (chatbotResponseService)
// Each intent has a handler that reads real data through chatbotDataService and returns {text, items, options}.
// Buttons are actions the panel can carry out: open a page or course, run another intent, or a course action.
// Nothing here is a canned figure: an empty result says so plainly.

const chatOpt = (label, action) => ({ id: `${action.kind}:${action.intent || action.page || action.id || action.action || ''}:${action.arg || action.lesson || action.set || ''}`, label, action });
const chatIntentOpt = (intent, label, arg) => chatOpt(label || chatIntent(intent)?.label || intent, { kind: 'intent', intent, ...(arg !== undefined ? { arg } : {}) });
// A page button is offered only when the user's own sidebar allows that page.
const chatNavOpt = (page, label) => chatbotPermissions.page(page) ? chatOpt(label, { kind: 'nav', page }) : null;
const chatMenuOpt = () => chatIntentOpt('HELP', 'Main menu');
const chatOptions = (...list) => list.flat().filter(Boolean);
const chatFirstName = () => String(currentUser?.name || '').split(' ')[0] || 'there';
const chatScopeName = data => data?.scope === 'team' ? 'your team' : 'the organisation';
const chatToday = () => new Date(Date.now() + (typeof serverClockOffset === 'number' ? serverClockOffset : 0));

/** Up to CHAT_LIST_LIMIT rows, with a button to the full page when there are more. */
function chatList(text, items, morePage, moreLabel) {
  const shown = items.slice(0, CHAT_LIST_LIMIT), hidden = items.length - shown.length;
  return { text: hidden > 0 ? `${text}\nShowing ${shown.length} of ${items.length}.` : text, items: shown, more: hidden > 0 && morePage ? chatNavOpt(morePage, moreLabel || 'See all') : null };
}

function chatSuggestionOptions(role, context) {
  const list = (CHAT_SUGGESTIONS[role] || CHAT_SUGGESTIONS.employee).filter(id => chatAllowed(chatIntent(id), role)).map(id => chatIntentOpt(id, CHAT_SUGGESTION_LABELS[id]));
  const course = context?.course ? CHAT_COURSE_ACTIONS.map(([action, label]) => chatOpt(label, { kind: 'course-action', action })) : [];
  return [...course, ...list];
}

// ---------------------------------------------------------------- course resolution

async function chatResolveCourse(ctx) {
  if (ctx.courseArg) return ctx.courseArg;
  const id = ctx.context?.course?.id;
  if (!id) return null;
  const courses = await chatbotDataService.courses();
  return courses.find(c => c.id === id) || null;
}

/** Ask which course, offering the user's own courses first. The next typed message is read as a course name. */
async function chatAskCourse(intent, question) {
  const courses = await chatbotDataService.courses();
  const mine = courses.filter(c => c.assignment || c.started).concat(courses.filter(c => !(c.assignment || c.started)));
  return { text: question || 'Which course do you mean? Choose one or type its name.', expect: { type: 'course', intent },
    options: chatOptions(mine.slice(0, 6).map(c => chatOpt(c.title, { kind: 'intent', intent, arg: c.id })), chatNavOpt('catalog', 'Browse all courses')) };
}

// ---------------------------------------------------------------- the open course's own lessons (course actions)

const chatPlainText = md => String(md || '').replace(/```[\s\S]*?```/g, ' ').replace(/`([^`]*)`/g, '$1').replace(/\*\*([^*]*)\*\*/g, '$1').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
  .replace(/^\s*\|.*\|\s*$/gm, ' ').replace(/^#{1,6}\s*/gm, '').replace(/^\s*[-*]\s+/gm, '').replace(/[ \t]+/g, ' ');

/** Lessons of the course open on the page, in order, with locked lessons kept empty exactly as the server sent them. */
function chatCourseLessons() {
  if (currentCourseExtras?.courseLessons?.length) {
    const done = learning?.run?.lessons || {};
    return currentCourseExtras.courseLessons.map((l, i) => ({ id: l.id, index: i, title: l.title, module: l.moduleTitle || '', content: [l.description, l.content, l.exercise].filter(Boolean).join('\n\n'),
      locked: Boolean(l.locked), assessmentId: l.assessmentId || null, quiz: (l.quiz || []).length, practice: Boolean(l.practice), exercise: Boolean(l.exercise || l.activity), completed: Boolean(done[l.id]?.completed) }));
  }
  // Three-module courses: lessons belong to the module whose videos list them.
  const sets = typeof courseSets !== 'undefined' ? courseSets : [];
  return (typeof lessons !== 'undefined' ? lessons : []).map((l, i) => {
    const set = sets.findIndex(s => (s.videos || []).includes(i));
    return { id: null, index: i, set, title: l.title, module: set >= 0 ? `Module ${set + 1}: ${sets[set].title}` : '', content: [l.body, l.task].filter(Boolean).join('\n\n'), locked: false, assessmentId: null, quiz: 0, practice: false, exercise: false, completed: false };
  });
}

const chatLessonAction = (courseId, lesson) => lesson.id ? { kind: 'course', id: courseId, lesson: lesson.id } : { kind: 'course', id: courseId, ...(lesson.set >= 0 ? { set: lesson.set } : {}) };

/** Bullet points under "Learning objectives", "Key takeaways" or "Summary" headings, as the lesson author wrote them. */
function chatLessonPoints(content) {
  const lines = String(content || '').split('\n'), points = [];
  let inside = false;
  for (const line of lines) {
    const heading = /^#{1,6}\s*(.*)$/.exec(line.trim());
    if (heading) { inside = /learning objectives|objectives|key takeaways|takeaways|summary|in short|what you('|’)ll learn/i.test(heading[1]); continue; }
    const bullet = /^\s*(?:[-*]|\d+\.)\s+(.*)$/.exec(line);
    if (inside && bullet) points.push(chatPlainText(bullet[1]).trim());
  }
  return points.filter(Boolean).slice(0, 6);
}

function chatSummarizeLesson(course, lesson) {
  if (lesson.locked) return { text: `“${lesson.title}” is still locked. Finish the earlier lessons and checks to open it.`, options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
  const points = chatLessonPoints(lesson.content);
  const headings = (String(lesson.content).match(/^#{2,3}\s+.+$/gm) || []).map(h => chatPlainText(h).trim()).filter(h => !/objectives|takeaways|summary/i.test(h)).slice(0, 6);
  const first = chatPlainText(lesson.content).split(/\n\s*\n/).map(p => p.trim()).find(p => p.length > 40) || '';
  const text = [`Summary of “${lesson.title}”${lesson.module ? ` (${lesson.module})` : ''}:`, points.length ? points.map(p => `• ${p}`).join('\n') : first.slice(0, 320) + (first.length > 320 ? '…' : ''),
    !points.length && headings.length ? `It covers: ${headings.join(', ')}.` : ''].filter(Boolean).join('\n');
  return { text, options: chatOptions(chatOpt('Open this lesson', chatLessonAction(course.id, lesson)), chatOpt('Explain a concept', { kind: 'course-action', action: 'explain' }), chatOpt('Practice', { kind: 'course-action', action: 'practice' })) };
}

function chatCourseOutline(list) {
  const modules = [...new Set(list.map(l => l.module).filter(Boolean))];
  return modules.length ? `${chatPlural(modules.length, 'module')}: ${modules.slice(0, 6).join('; ')}${modules.length > 6 ? '; …' : ''}.` : '';
}

/** Course actions kept from the course assistant: summarise, explain, practice and revision, from the course's own lessons. */
async function chatCourseAction(action, ctx, value) {
  const open = ctx.context?.course;
  if (!open || currentCourseInfo.id !== open.id) return { text: 'Open a course first, then I can summarise it, find where a concept is explained, list its practice activities and suggest what to revise.', options: chatOptions(chatIntentOpt('MY_PENDING_COURSES', 'My pending courses'), chatNavOpt('courses', 'Open My Learning')) };
  const course = { id: open.id, title: open.title }, list = chatCourseLessons(), unlocked = list.filter(l => !l.locked);
  if (action === 'summarize') {
    const lesson = list.find(l => l.id && l.id === (value || ctx.context.lessonId)) || (value != null && list.find(l => String(l.index) === String(value)));
    if (lesson) return chatSummarizeLesson(course, lesson);
    const info = (await chatbotDataService.courses()).find(c => c.id === course.id) || {};
    const text = [`“${course.title}”: ${info.description || 'no description has been added.'}`, `${chatPlural(list.length, 'lesson')}${info.durationMinutes ? `, about ${fmtDuration(info.durationMinutes)}` : ''}${info.assessmentCount ? `, ${chatPlural(info.assessmentCount, 'assessment')}` : ''}. ${chatCourseOutline(list)}`,
      info.started || info.completed ? `Your progress: ${chatPct(info.completed ? 100 : info.progress)}.` : ''].filter(Boolean).join('\n');
    return { text, options: chatOptions(unlocked.slice(0, 6).map(l => chatOpt(`Summarise: ${l.title}`, { kind: 'course-action', action: 'summarize', lesson: l.id ?? String(l.index) })), chatOpt('What to revise', { kind: 'course-action', action: 'revision' })) };
  }
  if (action === 'explain') {
    const term = String(value || '').trim();
    if (!term) return { text: 'Which concept would you like explained? Type a word or phrase from this course, for example a term from the lesson.', expect: { type: 'term' } };
    const pattern = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i'), hits = [];
    for (const lesson of unlocked) {
      const paragraphs = chatPlainText(lesson.content).split(/\n\s*\n|\n(?=[A-Z])/).map(p => p.trim()).filter(p => pattern.test(p));
      for (const paragraph of paragraphs) {
        const sentences = paragraph.split(/(?<=[.!?])\s+/), at = sentences.findIndex(s => pattern.test(s));
        const snippet = sentences.slice(Math.max(0, at), at + 2).join(' ');
        hits.push({ lesson, snippet: snippet.length > 280 ? snippet.slice(0, 277) + '…' : snippet, weight: pattern.test(lesson.title) ? 2 : 1 });
      }
    }
    hits.sort((a, b) => b.weight - a.weight);
    if (!hits.length) return { text: `I couldn't find “${term}” in the lessons of “${course.title}” that are open to you. Try another word, or browse the lessons.`, expect: { type: 'term' },
      options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
    const seen = new Set(), unique = hits.filter(h => !seen.has(h.lesson.index) && seen.add(h.lesson.index)).slice(0, 3);
    return { text: `Here is where “${term}” is explained in this course:`, items: unique.map(h => ({ title: h.lesson.title, meta: h.snippet, action: chatLessonAction(course.id, h.lesson), actionLabel: 'Open lesson' })),
      options: [chatOpt('Explain another concept', { kind: 'course-action', action: 'explain' }), chatOpt('Practice', { kind: 'course-action', action: 'practice' })] };
  }
  if (action === 'practice') {
    const checks = (currentCourseExtras?.assessments || []).map(a => ({ title: a.title, meta: `${KIND_LABELS[a.kind] || 'Assessment'} · pass mark ${a.passPercent}% · ${a.passed ? 'passed' : a.best != null ? `best ${a.best}%` : 'not attempted'} · ${chatPlural(a.attemptsLeft, 'attempt')} left`,
      tag: a.passed ? 'Passed' : 'To do', tone: a.passed ? 'success' : 'gray', action: chatLessonAction(course.id, list.find(l => l.assessmentId === a.id) || {}), actionLabel: 'Open' }));
    const activities = unlocked.filter(l => l.quiz || l.practice || l.exercise).map(l => ({ title: l.title, meta: [l.quiz ? `${chatPlural(l.quiz, 'quiz question')}` : '', l.practice ? 'coding practice' : '', l.exercise ? 'practical exercise' : ''].filter(Boolean).join(' · '),
      tag: l.completed ? 'Done' : '', tone: 'success', action: chatLessonAction(course.id, l), actionLabel: 'Practise' }));
    const sets = typeof courseSets !== 'undefined' && !currentCourseExtras?.courseLessons?.length ? courseSets.map((s, i) => ({ title: `Module ${i + 1}: ${s.title}`, meta: `${chatPlural((s.exercises || []).length, 'practice exercise')} and a module exam`, action: { kind: 'course', id: course.id, set: i }, actionLabel: 'Open' })) : [];
    const items = [...activities, ...sets, ...checks];
    if (!items.length) return { text: `“${course.title}” has no practice activities or knowledge checks yet.`, options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
    return { ...chatList(`Practice in “${course.title}” — the course's own exercises and checks, marked by the portal:`, items), options: [chatOpt('What to revise', { kind: 'course-action', action: 'revision' })] };
  }
  // revision: failed checks first, then lessons not yet completed, from the user's own results.
  const failed = (currentCourseExtras?.assessments || []).filter(a => !a.passed && a.best != null).map(a => {
    const lesson = list.find(l => l.assessmentId === a.id);
    return { title: lesson ? lesson.title : a.title, meta: `${a.title}: best ${a.best}%, pass mark ${a.passPercent}% · ${chatPlural(a.attemptsLeft, 'attempt')} left`, tag: 'Revise', tone: 'danger', action: chatLessonAction(course.id, lesson || {}), actionLabel: 'Revise' };
  });
  const attempts = learning?.run?.attempts || [];
  const modules = !currentCourseExtras?.courseLessons?.length ? (typeof courseSets !== 'undefined' ? courseSets : []).map((s, i) => ({ s, i, tries: attempts[i] || [] }))
    .filter(m => m.tries.length && !m.tries.some(t => t.status === 'passed')).map(m => ({ title: `Module ${m.i + 1}: ${m.s.title}`, meta: `Module exam not passed yet (${chatPlural(m.tries.length, 'attempt')} used)`, tag: 'Revise', tone: 'danger', action: { kind: 'course', id: course.id, set: m.i }, actionLabel: 'Revise' })) : [];
  const unfinished = unlocked.filter(l => l.id && !l.completed).slice(0, 4).map(l => ({ title: l.title, meta: l.module || 'Not completed yet', tag: 'Not done', tone: 'gray', action: chatLessonAction(course.id, l), actionLabel: 'Open' }));
  const items = [...failed, ...modules, ...unfinished];
  if (!items.length) return { text: `Nothing to revise in “${course.title}” right now: you have no failed checks or unfinished lessons. Summaries of each lesson are a good way to refresh.`, options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
  return { ...chatList(`Based on your results in “${course.title}”, revise these first:`, items), options: [chatOpt('Practice', { kind: 'course-action', action: 'practice' })] };
}

// ---------------------------------------------------------------- step-by-step guidance (navigation help, not data)

const CHAT_GUIDES = [
  { id: 'create-course', label: 'Create a course', roles: CHAT_COURSE_STAFF, page: 'admin-courses', match: /\b(create|add|build|new)\b.*\bcourses?\b/,
    steps: ['Open Manage Courses and choose “+ Create course”.', 'Pick “Create manually” (or “Create from a link with AI”, if your administrator enabled it).', 'Fill in the four steps: Course basics, Learning materials, Assessment, Review & publish.', 'Save a draft at any step; publish when the checklist is complete.'] },
  { id: 'assign', label: 'Assign a course', roles: CHAT_STAFF_ROLES, page: 'admin-courses', match: /\bassign/,
    steps: ['Open Manage Courses and choose Assign next to a published course (or the “Assign a Course” tab).', 'Choose the assignment type: individual employee, department or job role.', 'Set the deadline (IST) and choose Mandatory or Optional.', 'Select Assign Course. Employees are notified and see it in My Learning.'] },
  { id: 'reminders', label: 'Deadline reminders', roles: CHAT_STAFF_ROLES, page: 'admin-courses', match: /\breminders?\b/,
    steps: ['Open Manage Courses → Reminders.', 'Set how many days before a deadline reminders go out, and the Due Soon window.', 'Reminder history shows each delivery and its status.'] },
  { id: 'users', label: 'Add or edit users', roles: CHAT_STAFF_ROLES, page: 'admin-users', match: /\b(users?|accounts?|employees?|add (an )?employee|teams?)\b/,
    steps: ['Open Users & Teams.', 'Add an account, or sync employees from Keka.', 'Edit a person to set their department, job role and manager.'] },
  { id: 'onboarding', label: 'Onboarding', roles: CHAT_STAFF_ROLES, page: 'onboarding', match: /\bonboarding\b/,
    steps: ['Open Onboarding.', 'Create or edit a template with milestones and courses.', 'Assign it to new joiners and follow their progress there.'] },
  { id: 'password', label: 'Change my password', roles: CHAT_ALL, page: 'account', match: /\b(password|profile|account)\b/,
    steps: ['Open My Profile from the sidebar.', 'Use the password section to set a new password.'] },
  { id: 'theme', label: 'Dark mode', roles: CHAT_ALL, page: null, match: /\b(dark mode|theme|light mode)\b/,
    steps: ['Use the theme switch at the top of the page to change between light and dark.'] },
];
const chatGuideAllowed = (g, role) => g.roles === CHAT_ALL || g.roles.includes(role);

// ---------------------------------------------------------------- intent handlers

const CHAT_NAV_INFO = { dashboard: 'Your overview and key figures', compliance: 'Assigned training, deadlines and overdue courses', courses: 'Your assigned and started courses', catalog: 'Every course available to you',
  'admin-courses': 'Create, publish and assign courses', 'admin-users': 'Accounts, departments and job roles', onboarding: 'Onboarding journeys for new joiners', assessments: 'Assessments you can take or manage',
  calendar: 'Training sessions and workshops', 'cert-records': 'Certificates issued across the organisation', reports: 'Reports and CSV exports', 'learning-activity': 'Learning activity history',
  'admin-audit': 'Administrative actions', account: 'Your profile and password', certificates: 'Certificates you have earned' };

const chatAreaFrom = text => {
  const t = String(text || '');
  for (const [re, id] of [[/\b(technical|ai|data|software|coding|programming|tech)\b/, 'technical'], [/\b(compliance|security|policy|privacy|safety)\b/, 'compliance'], [/\b(leadership|management|manager)\b/, 'management'],
    [/\b(recruitment|hiring|hr|talent)\b/, 'recruitment'], [/\b(business|soft skills?|professional|communication)\b/, 'professional']]) if (re.test(t)) return id;
  return null;
};

async function chatCompliance(params) { return chatbotDataService.compliance(params); }
const chatComplianceItem = r => ({ title: `${r.employee} — ${r.course}`, meta: [r.department, r.mandatory ? 'Mandatory' : 'Optional', r.deadlineDisplay ? `Due ${r.deadlineDisplay}` : 'No deadline', r.overdueBy ? `Overdue by ${r.overdueBy}` : `${chatPct(r.progress)} complete`].filter(Boolean).join(' · '),
  tag: r.statusLabel, tone: chatStatusTone(r.status), action: { kind: 'nav', page: 'compliance' }, actionLabel: 'View' });

const CHAT_HANDLERS = {
  HELP: async ctx => ({ text: `Hi ${chatFirstName()}! I can answer questions about your learning${chatbotPermissions.team() ? ' and the training records you look after' : ''}, using the LMS's own data. Choose a question below or type your own.${ctx.context?.course ? `\nYou're on “${ctx.context.course.title}”, so the course actions are at the top.` : ''}`,
    options: chatSuggestionOptions(ctx.role, ctx.context) }),
  THANKS: async ctx => ({ text: "You're welcome! Anything else I can help with?", options: chatSuggestionOptions(ctx.role, ctx.context).slice(0, 6) }),
  LMS_OVERVIEW: async () => {
    const nav = (typeof portalNavigation === 'function' ? portalNavigation() : []).filter(([page]) => CHAT_NAV_INFO[page]);
    return { text: 'Here is what your LMS gives you. Pick a section to open it:', items: nav.map(([page, , label]) => ({ title: label, meta: CHAT_NAV_INFO[page], action: { kind: 'nav', page }, actionLabel: 'Open' })), options: [chatMenuOpt()] };
  },
  FIND_COURSE: async ctx => {
    const courses = await chatbotDataService.courses(), area = ctx.arg || chatAreaFrom(ctx.text);
    if (!courses.length) return { text: 'No courses are published for you yet.', options: [chatMenuOpt()] };
    if (!area) {
      const counts = LEARNING_AREAS.map(a => [a, courses.filter(c => learningArea(c.category).id === a.id).length]).filter(([, n]) => n);
      return { text: 'What type of course are you looking for?', options: chatOptions(counts.map(([a, n]) => chatIntentOpt('FIND_COURSE', `${a.filter} (${n})`, a.id)), chatNavOpt('catalog', 'Browse all courses')) };
    }
    const info = LEARNING_AREAS.find(a => a.id === area), list = courses.filter(c => learningArea(c.category).id === area).sort((a, b) => Number(a.completed) - Number(b.completed) || a.title.localeCompare(b.title));
    if (!list.length) return { text: `There are no ${info.title} courses available to you right now.`, options: chatOptions(chatIntentOpt('FIND_COURSE', 'Other course types'), chatNavOpt('catalog', 'Browse all courses')) };
    return { ...chatList(`${info.title} courses available to you:`, list.map(c => chatCourseItem(c, `${capital(c.difficulty || 'beginner')} · ${fmtDuration(c.durationMinutes)}`)), 'catalog', 'Browse all courses'), options: chatOptions(chatIntentOpt('FIND_COURSE', 'Other course types'), chatNavOpt('catalog', 'Browse all courses')) };
  },
  FIND_TRAINING: async () => {
    const data = await chatbotDataService.calendar(), sessions = data.sessions || [];
    const items = sessions.map(s => ({ title: s.title, meta: [fmtDateTime(s.startsAt), s.course, s.trainer ? `with ${s.trainer}` : '', s.seatsLeft != null ? `${chatPlural(s.seatsLeft, 'seat')} left` : ''].filter(Boolean).join(' · '), action: { kind: 'nav', page: 'calendar' }, actionLabel: 'View' }));
    if (!items.length) return { text: 'No training sessions are scheduled at the moment.', options: chatOptions(chatNavOpt('calendar', 'Open Training Calendar'), chatIntentOpt('FIND_COURSE', 'Find a course')) };
    return { ...chatList('Upcoming training sessions:', items, 'calendar', 'Open Training Calendar'), options: chatOptions(chatNavOpt('calendar', 'Open Training Calendar')) };
  },
  NAVIGATE_TO_ASSESSMENTS: async () => {
    const list = await chatbotDataService.assessments(), open = list.filter(a => !a.passed && a.attemptsLeft > 0).length;
    return { text: `Your assessments are on the Assessments page. ${list.length ? `You have ${chatPlural(list.length, 'assessment')}, ${open} still to pass.` : 'None are available to you yet.'}`, options: chatOptions(chatNavOpt('assessments', 'Open Assessments'), chatIntentOpt('ASSESSMENT_STATUS', 'My results')) };
  },
  NAVIGATE_TO_CERTIFICATES: async () => {
    const certs = await chatbotDataService.certificates();
    return { text: `You can access your certificates from the Certificates section. ${certs.length ? `You have ${chatPlural(certs.length, 'certificate')}.` : "You haven't earned one yet — certificates are issued when you complete a course."}`, options: chatOptions(chatNavOpt('certificates', 'Open Certificates'), certs.length ? chatIntentOpt('MY_CERTIFICATES', 'List my certificates') : null) };
  },
  MY_ASSIGNED_COURSES: async () => {
    const list = (await chatbotDataService.courses()).filter(c => c.assignment).sort((a, b) => Number(a.completed) - Number(b.completed) || (chatDeadlineAt(a) || '9').localeCompare(chatDeadlineAt(b) || '9'));
    if (!list.length) return { text: 'No courses are assigned to you right now.', options: chatOptions(chatIntentOpt('FIND_COURSE', 'Find a course'), chatMenuOpt()) };
    const mandatory = list.filter(c => c.assignment.mandatory).length, done = list.filter(c => c.completed).length;
    return { ...chatList(`You have ${chatPlural(list.length, 'assigned course')} (${mandatory} mandatory, ${done} completed):`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(chatIntentOpt('MY_PENDING_COURSES', 'Pending courses'), chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming deadlines')) };
  },
  MY_PENDING_COURSES: async () => ({ text: 'Sure! Would you like to see all pending courses or only mandatory training?',
    options: [chatIntentOpt('MY_PENDING_ALL', 'All Pending Courses'), chatIntentOpt('MY_MANDATORY', 'Mandatory Training'), chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming Deadlines')] }),
  MY_PENDING_ALL: async () => {
    const list = (await chatbotDataService.courses()).filter(chatIsPending).sort((a, b) => (chatDeadlineAt(a) || '9').localeCompare(chatDeadlineAt(b) || '9'));
    if (!list.length) return { text: 'You have no pending courses. 🎉', options: chatOptions(chatIntentOpt('MY_COMPLETED_COURSES', 'Completed courses'), chatIntentOpt('FIND_COURSE', 'Find a course')) };
    return { ...chatList(`You have ${chatPlural(list.length, 'pending course')}, nearest deadline first:`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(chatIntentOpt('MY_MANDATORY', 'Mandatory only'), chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming deadlines')) };
  },
  MY_MANDATORY: async () => {
    const all = (await chatbotDataService.courses()).filter(c => c.assignment?.mandatory), list = all.filter(c => !c.completed).sort((a, b) => (chatDeadlineAt(a) || '9').localeCompare(chatDeadlineAt(b) || '9'));
    if (!all.length) return { text: 'You have no mandatory training assigned.', options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'All pending courses')) };
    if (!list.length) return { text: `You have completed all ${chatPlural(all.length, 'mandatory course')}. 🎉`, options: chatOptions(chatIntentOpt('MY_CERTIFICATES', 'My certificates')) };
    return { ...chatList(`${chatPlural(list.length, 'mandatory course')} still to complete:`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming deadlines'), chatIntentOpt('MY_PENDING_ALL', 'All pending courses')) };
  },
  MY_COMPLETED_COURSES: async () => {
    const list = (await chatbotDataService.courses()).filter(c => c.completed);
    if (!list.length) return { text: "You haven't completed a course yet.", options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'My pending courses')) };
    return { ...chatList(`You have completed ${chatPlural(list.length, 'course')}:`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(chatIntentOpt('MY_CERTIFICATES', 'My certificates')) };
  },
  MY_LEARNING_PROGRESS: async () => {
    const courses = await chatbotDataService.courses(), mine = courses.filter(c => c.assignment || c.started || c.completed);
    if (!mine.length) return { text: "You haven't started any courses yet, and none are assigned to you.", options: chatOptions(chatIntentOpt('FIND_COURSE', 'Find a course')) };
    const done = mine.filter(c => c.completed).length, active = mine.filter(c => !c.completed && c.started), overdue = mine.filter(c => c.status === 'overdue').length;
    const average = Math.round(mine.reduce((n, c) => n + (c.completed ? 100 : Number(c.progress) || 0), 0) / mine.length);
    return { ...chatList(`Your learning: ${done} of ${chatPlural(mine.length, 'course')} completed, ${active.length} in progress${overdue ? `, ${overdue} overdue` : ''}. Average progress ${average}%.${active.length ? '\nIn progress:' : ''}`, active.sort((a, b) => b.progress - a.progress).map(c => chatCourseItem(c)), 'courses', 'Open My Learning'),
      options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'Pending courses'), chatIntentOpt('MY_UPCOMING_DEADLINES', 'Deadlines'), chatIntentOpt('MY_CERTIFICATES', 'Certificates')) };
  },
  MY_UPCOMING_DEADLINES: async () => {
    const now = chatToday().toISOString(), courses = await chatbotDataService.courses();
    const list = courses.filter(c => !c.completed && chatDeadlineAt(c) && chatDeadlineAt(c) >= now).sort((a, b) => chatDeadlineAt(a).localeCompare(chatDeadlineAt(b)));
    const overdue = courses.filter(c => !c.completed && c.status === 'overdue').length;
    const extra = overdue ? `\nYou also have ${chatPlural(overdue, 'overdue course')}.` : '';
    if (!list.length) return { text: `You have no upcoming deadlines.${extra}`, options: chatOptions(overdue ? chatIntentOpt('MY_OVERDUE_TRAINING', 'Show overdue') : null, chatIntentOpt('MY_PENDING_ALL', 'Pending courses')) };
    return { ...chatList(`Your upcoming deadlines:${extra}`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(overdue ? chatIntentOpt('MY_OVERDUE_TRAINING', 'Show overdue') : null, chatIntentOpt('MY_MANDATORY', 'Mandatory training')) };
  },
  MY_OVERDUE_TRAINING: async () => {
    const list = (await chatbotDataService.courses()).filter(c => !c.completed && c.status === 'overdue');
    if (!list.length) return { text: 'Nothing is overdue. 👍', options: chatOptions(chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming deadlines')) };
    return { ...chatList(`${chatPlural(list.length, 'course is', 'courses are')} overdue. Overdue courses stay open, and late completion is recorded:`, list.map(c => chatCourseItem(c)), 'courses', 'Open My Learning'), options: chatOptions(chatIntentOpt('MY_UPCOMING_DEADLINES', 'Upcoming deadlines')) };
  },
  MY_CERTIFICATES: async () => {
    const certs = await chatbotDataService.certificates();
    if (!certs.length) return { text: "You haven't earned a certificate yet. Certificates are issued when you complete a course.", options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'My pending courses'), chatNavOpt('certificates', 'Open Certificates')) };
    return { ...chatList(`You have ${chatPlural(certs.length, 'certificate')}:`, certs.map(c => ({ title: c.courseTitle, meta: `Issued ${fmtDate(c.completedAt)}`, tag: 'Certified', tone: 'success', action: { kind: 'nav', page: 'certificates' }, actionLabel: 'View' })), 'certificates', 'Open Certificates'),
      options: chatOptions(chatNavOpt('certificates', 'Open Certificates')) };
  },
  LEARNING_MATERIALS: async ctx => {
    const open = ctx.context?.course;
    if (open && currentCourseInfo.id === open.id) {
      const resources = (currentCourseExtras?.resources || []).map(r => ({ title: r.title, meta: capital(r.kind || 'material'), action: { kind: 'course', id: open.id }, actionLabel: 'Open course' }));
      const docs = chatCourseLessons().filter(l => !l.locked && l.id).flatMap(l => {
        const lesson = currentCourseExtras.courseLessons.find(x => x.id === l.id);
        return [...(lesson.documentUrl ? [{ title: lesson.documentName || 'Lesson document', meta: `In “${l.title}”`, action: chatLessonAction(open.id, l), actionLabel: 'Open lesson' }] : []),
          ...(lesson.resources || []).map(r => ({ title: r.title, meta: `Link in “${l.title}”`, action: chatLessonAction(open.id, l), actionLabel: 'Open lesson' }))];
      });
      const items = [...resources, ...docs];
      if (!items.length) return { text: `“${open.title}” has no separate materials; everything is in its lessons.`, options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
      return chatList(`Learning materials in “${open.title}”:`, items);
    }
    if (ctx.courseArg) return { text: `Open “${ctx.courseArg.title}” to see its documents and links; they are listed on the course page.`, options: [chatOpt(`Open ${ctx.courseArg.title}`, { kind: 'course', id: ctx.courseArg.id })] };
    return chatAskCourse('LEARNING_MATERIALS', 'Materials belong to a course. Which course do you want materials for?');
  },
  EXPLAIN_TERM: async ctx => chatCourseAction('explain', ctx, chatExtractTerm(ctx.text)),
  COURSE_DETAILS: async ctx => {
    const c = await chatResolveCourse(ctx);
    if (!c) return chatAskCourse('COURSE_DETAILS');
    const mine = c.completed ? 'You have completed it.' : c.started ? `You are ${chatPct(c.progress)} through it.` : c.assignment ? 'It is assigned to you.' : 'You have not started it yet.';
    return { text: `“${c.title}”\n${c.description || ''}\n${[c.category, capital(c.difficulty || 'beginner'), fmtDuration(c.durationMinutes), c.lessonCount ? chatPlural(c.lessonCount, 'lesson') : '', c.assessmentCount ? chatPlural(c.assessmentCount, 'assessment') : ''].filter(Boolean).join(' · ')}\n${mine}${c.deadline?.display && !c.completed ? ` Deadline: ${c.deadline.display} ${c.deadline.timezone || ''}.` : ''}`,
      options: chatOptions(chatOpt(c.completed ? 'Review course' : c.started ? 'Continue course' : 'Open course', { kind: 'course', id: c.id }), chatIntentOpt('COURSE_CONTENT', 'What it covers', c.id)) };
  },
  COURSE_DURATION: async ctx => {
    const c = await chatResolveCourse(ctx);
    if (!c) return chatAskCourse('COURSE_DURATION');
    return { text: c.durationMinutes ? `“${c.title}” takes about ${fmtDuration(c.durationMinutes)}${c.lessonCount ? ` across ${chatPlural(c.lessonCount, 'lesson')}` : ''}.` : `No estimated duration has been set for “${c.title}”${c.lessonCount ? `; it has ${chatPlural(c.lessonCount, 'lesson')}` : ''}.`, options: [chatOpt('Open course', { kind: 'course', id: c.id }), chatIntentOpt('COURSE_DETAILS', 'Course details', c.id)] };
  },
  COURSE_CATEGORY: async ctx => {
    const c = await chatResolveCourse(ctx);
    if (!c) return chatAskCourse('COURSE_CATEGORY');
    const area = learningArea(c.category);
    return { text: `“${c.title}” is in the ${c.category} category (${area.title}).`, options: [chatIntentOpt('FIND_COURSE', `More ${area.filter} courses`, area.id), chatOpt('Open course', { kind: 'course', id: c.id })] };
  },
  COURSE_LEVEL: async ctx => {
    const c = await chatResolveCourse(ctx);
    if (!c) return chatAskCourse('COURSE_LEVEL');
    return { text: `“${c.title}” is a ${capital(c.difficulty || 'beginner')} level course.`, options: [chatOpt('Open course', { kind: 'course', id: c.id }), chatIntentOpt('COURSE_DETAILS', 'Course details', c.id)] };
  },
  COURSE_CONTENT: async ctx => {
    const c = await chatResolveCourse(ctx);
    if (!c) return chatAskCourse('COURSE_CONTENT');
    if (currentCourseInfo.id === c.id) {
      const list = chatCourseLessons();
      return { ...chatList(`“${c.title}” has ${chatPlural(list.length, 'lesson')}. ${chatCourseOutline(list)}`, list.map(l => ({ title: l.title, meta: [l.module, l.locked ? 'Locked' : l.completed ? 'Completed' : ''].filter(Boolean).join(' · '), action: chatLessonAction(c.id, l), actionLabel: 'Open' }))),
        options: [chatOpt('Summarise the course', { kind: 'course-action', action: 'summarize' })] };
    }
    return { text: `“${c.title}” has ${chatPlural(c.lessonCount || 0, 'lesson')}${c.assessmentCount ? ` and ${chatPlural(c.assessmentCount, 'assessment')}` : ''}${c.durationMinutes ? `, about ${fmtDuration(c.durationMinutes)} in total` : ''}. Open it to see every lesson; I can then summarise them for you.`, options: [chatOpt('Open course', { kind: 'course', id: c.id })] };
  },
  ASSESSMENT_INFORMATION: async () => {
    const list = await chatbotDataService.assessments();
    if (!list.length) return { text: 'No assessments are available to you right now.', options: chatOptions(chatNavOpt('assessments', 'Open Assessments')) };
    const items = list.map(a => ({ title: a.title, meta: [a.course, `${a.questionCount} questions`, `${a.timeLimitMinutes} min`, `pass mark ${a.passPercent}%`, `${chatPlural(a.attemptsLeft, 'attempt')} left`].filter(Boolean).join(' · '),
      tag: a.passed ? 'Passed' : a.best != null ? `Best ${a.best}%` : 'Not attempted', tone: a.passed ? 'success' : a.best != null ? 'danger' : 'gray', action: { kind: 'nav', page: 'assessments' }, actionLabel: 'Open' }));
    return { ...chatList(`You have ${chatPlural(list.length, 'assessment')}:`, items, 'assessments', 'Open Assessments'), options: chatOptions(chatIntentOpt('ASSESSMENT_STATUS', 'My results'), chatNavOpt('assessments', 'Open Assessments')) };
  },
  ASSESSMENT_DEADLINE: async () => {
    const [list, courses] = await Promise.all([chatbotDataService.assessments(), chatbotDataService.courses()]), byId = Object.fromEntries(courses.map(c => [c.id, c]));
    const due = list.filter(a => !a.passed && byId[a.courseId]?.deadline?.at && !byId[a.courseId].completed).sort((a, b) => byId[a.courseId].deadline.at.localeCompare(byId[b.courseId].deadline.at));
    const intro = 'Assessments do not have deadlines of their own; the deadline of the course they belong to applies.';
    if (!due.length) return { text: `${intro} None of your unpassed assessments belong to a course with a deadline.`, options: chatOptions(chatIntentOpt('ASSESSMENT_INFORMATION', 'My assessments')) };
    return { ...chatList(`${intro} These are due with their course:`, due.map(a => ({ title: a.title, meta: `${a.course} · due ${byId[a.courseId].deadline.display} ${byId[a.courseId].deadline.timezone || ''}`, tag: byId[a.courseId].deadline.label, tone: chatStatusTone(byId[a.courseId].deadline.status), action: { kind: 'course', id: a.courseId }, actionLabel: 'Open course' }))),
      options: chatOptions(chatIntentOpt('ASSESSMENT_STATUS', 'My results')) };
  },
  ASSESSMENT_STATUS: async () => {
    const list = (await chatbotDataService.assessments()).filter(a => a.attempts.length);
    if (!list.length) return { text: "You haven't attempted any assessments yet.", options: chatOptions(chatIntentOpt('ASSESSMENT_INFORMATION', 'Available assessments')) };
    const passed = list.filter(a => a.passed).length;
    return { ...chatList(`Your results: ${passed} passed out of ${chatPlural(list.length, 'assessment')} attempted.`, list.map(a => ({ title: a.title, meta: `${a.course ? a.course + ' · ' : ''}best ${a.best ?? '—'}% · pass mark ${a.passPercent}% · ${chatPlural(a.attemptsLeft, 'attempt')} left`, tag: a.passed ? 'Passed' : 'Not passed', tone: a.passed ? 'success' : 'danger', action: { kind: 'nav', page: 'assessments' }, actionLabel: 'View' })), 'assessments', 'Open Assessments'),
      options: chatOptions(chatIntentOpt('PRACTICE_QUESTIONS', 'Practice')) };
  },
  PRACTICE_QUESTIONS: async ctx => {
    if (ctx.context?.course && currentCourseInfo.id === ctx.context.course.id) return chatCourseAction(/revis/.test(ctx.text || '') ? 'revision' : 'practice', ctx);
    const list = (await chatbotDataService.assessments()).filter(a => a.kind === 'knowledge' && !a.passed);
    const text = 'Practice activities belong to courses: open a course and choose Practice to see its exercises, quizzes and knowledge checks.';
    if (!list.length) return { text, options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'My pending courses')) };
    return { ...chatList(`${text}\nKnowledge checks you haven't passed yet:`, list.map(a => ({ title: a.title, meta: a.course, action: a.courseId ? { kind: 'course', id: a.courseId } : { kind: 'nav', page: 'assessments' }, actionLabel: 'Open' }))), options: chatOptions(chatIntentOpt('MY_PENDING_ALL', 'My pending courses')) };
  },
  TEAM_LEARNING_PROGRESS: async () => {
    const data = await chatCompliance({}), s = data.summary;
    if (!s.total) return { text: `No training is assigned to ${chatScopeName(data)} yet.`, options: chatOptions(chatNavOpt('compliance', 'Open Training Compliance')) };
    const people = {};
    for (const r of data.table.rows) (people[r.employeeId] ||= { name: r.employee, department: r.department, total: 0, done: 0, overdue: 0 }), people[r.employeeId].total++, people[r.employeeId].done += r.status.startsWith('completed') ? 1 : 0, people[r.employeeId].overdue += r.status === 'overdue' ? 1 : 0;
    const items = Object.values(people).sort((a, b) => b.overdue - a.overdue || a.done / a.total - b.done / b.total).map(p => ({ title: p.name, meta: `${p.department} · ${p.done} of ${chatPlural(p.total, 'course')} completed${p.overdue ? ` · ${p.overdue} overdue` : ''}`, tag: p.overdue ? 'Overdue' : p.done === p.total ? 'Complete' : 'On track', tone: p.overdue ? 'danger' : p.done === p.total ? 'success' : '', action: { kind: 'nav', page: 'compliance' }, actionLabel: 'View' }));
    return { ...chatList(`Training for ${chatScopeName(data)}: ${s.completed} of ${s.total} assigned courses completed (${s.completionRate}%), ${s.inProgress} in progress, ${s.notStarted} not started, ${s.overdue} overdue.`, items, 'compliance', 'Open Training Compliance'),
      options: chatOptions(chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training'), chatIntentOpt('TEAM_PENDING_TRAINING', 'Pending training'), chatNavOpt('compliance', 'Open Training Compliance')) };
  },
  TEAM_PENDING_TRAINING: async () => {
    const [started, notStarted] = await Promise.all([chatCompliance({ status: 'in_progress', sort: 'deadline' }), chatCompliance({ status: 'not_started', sort: 'deadline' })]);
    const rows = [...started.table.rows, ...notStarted.table.rows].sort((a, b) => (a.deadlineAt || '9').localeCompare(b.deadlineAt || '9')), total = started.table.total + notStarted.table.total;
    if (!total) return { text: `Nothing is pending for ${chatScopeName(started)}. 🎉`, options: chatOptions(chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training')) };
    return { ...chatList(`${chatPlural(total, 'assigned course is', 'assigned courses are')} pending for ${chatScopeName(started)} (${started.table.total} in progress, ${notStarted.table.total} not started), nearest deadline first:`, rows.map(chatComplianceItem), 'compliance', 'Open Training Compliance'),
      options: chatOptions(chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training'), chatNavOpt('compliance', 'Open Training Compliance')) };
  },
  TEAM_OVERDUE_TRAINING: async () => {
    const data = await chatCompliance({ status: 'overdue', sort: 'deadline' }), rows = data.overdue?.rows?.length ? data.overdue.rows : data.table.rows, total = data.table.total;
    if (!total) return { text: `No overdue training for ${chatScopeName(data)}. 👍`, options: chatOptions(chatIntentOpt('TEAM_PENDING_TRAINING', 'Pending training')) };
    const mandatory = data.overdue?.mandatory ?? rows.filter(r => r.mandatory).length;
    return { ...chatList(`${chatPlural(total, 'assigned course is', 'assigned courses are')} overdue for ${chatScopeName(data)} (${mandatory} mandatory), mandatory and longest overdue first:`, rows.map(chatComplianceItem), 'compliance', 'Open Training Compliance'),
      options: chatOptions(chatNavOpt('compliance', 'Open Training Compliance'), chatIntentOpt('TEAM_LEARNING_PROGRESS', 'Overall progress')) };
  },
  TEAM_COURSE_ASSIGNMENTS: async () => {
    const data = await chatCompliance({}), courses = {};
    for (const r of data.table.rows) (courses[r.courseId] ||= { title: r.course, total: 0, done: 0, mandatory: false, overdue: 0 }), courses[r.courseId].total++, courses[r.courseId].done += r.status.startsWith('completed') ? 1 : 0, courses[r.courseId].mandatory ||= r.mandatory, courses[r.courseId].overdue += r.status === 'overdue' ? 1 : 0;
    const items = Object.values(courses).sort((a, b) => Number(b.mandatory) - Number(a.mandatory) || b.total - a.total).map(c => ({ title: c.title, meta: `${chatPlural(c.total, 'person', 'people')} assigned · ${c.done} completed${c.overdue ? ` · ${c.overdue} overdue` : ''}`, tag: c.mandatory ? 'Mandatory' : 'Optional', tone: c.mandatory ? 'warn' : 'gray', action: { kind: 'nav', page: 'compliance' }, actionLabel: 'View' }));
    if (!items.length) return { text: `No training is assigned to ${chatScopeName(data)} yet.`, options: chatOptions(chatbotPermissions.staff() ? chatOpt('Assign a course', { kind: 'assign' }) : null) };
    return { ...chatList(`Training required for ${chatScopeName(data)}:`, items, 'compliance', 'Open Training Compliance'), options: chatOptions(chatbotPermissions.staff() ? chatOpt('Assign a course', { kind: 'assign' }) : null, chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training')) };
  },
  TRAINING_COMPLIANCE: async () => {
    const data = await chatCompliance({}), s = data.summary, worst = (data.departments || []).filter(d => d.overdue).sort((a, b) => b.overdue - a.overdue).slice(0, 3);
    if (!s.total) return { text: `No training is assigned to ${chatScopeName(data)} yet, so there is nothing to measure.`, options: chatOptions(chatNavOpt('compliance', 'Open Training Compliance')) };
    return { text: `Training compliance for ${chatScopeName(data)} (${data.updatedDisplay || 'now'}): ${s.completionRate}% complete — ${s.completed} of ${s.total} assignments completed (${s.completedLate} late), ${s.inProgress} in progress, ${s.notStarted} not started, ${s.overdue} overdue.${worst.length ? `\nMost overdue: ${worst.map(d => `${d.department} (${d.overdue})`).join(', ')}.` : ''}`,
      options: chatOptions(chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training'), chatIntentOpt('DEPARTMENT_TRAINING', 'By department'), chatNavOpt('compliance', 'Open Training Compliance')) };
  },
  DEPARTMENT_TRAINING: async () => {
    const data = await chatCompliance({}), list = data.departments || [];
    if (!list.length) return { text: `No training is assigned to ${chatScopeName(data)} yet.`, options: chatOptions(chatNavOpt('compliance', 'Open Training Compliance')) };
    return { ...chatList(`Training by department for ${chatScopeName(data)}:`, list.map(d => ({ title: d.department, meta: `${d.completed} of ${d.total} completed · ${d.pending} pending · ${d.overdue} overdue`, tag: `${d.completionRate}%`, tone: d.overdue ? 'danger' : d.completionRate === 100 ? 'success' : '', action: { kind: 'nav', page: 'compliance' }, actionLabel: 'View' })), 'compliance', 'Open Training Compliance'),
      options: chatOptions(chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training')) };
  },
  EMPLOYEE_TRAINING: async ctx => {
    const name = ctx.arg !== undefined ? String(ctx.arg).trim() : chatExtractPerson(ctx.text || '');
    if (!name || name.length < 2) return { text: 'Whose training would you like to see? Type their name or email.', expect: { type: 'employee', intent: 'EMPLOYEE_TRAINING' } };
    const data = await chatCompliance({ q: name }), rows = data.table.rows;
    if (!rows.length) return { text: `I couldn't find assigned training for “${name}” in ${chatScopeName(data)}. Check the spelling, or try their email.`, expect: { type: 'employee', intent: 'EMPLOYEE_TRAINING' } };
    const people = [...new Set(rows.map(r => r.employee))];
    return { ...chatList(people.length === 1 ? `Training for ${people[0]}: ${rows.filter(r => r.status.startsWith('completed')).length} of ${chatPlural(data.table.total, 'course')} completed.` : `${people.length} people match “${name}”:`, rows.map(chatComplianceItem), 'compliance', 'Open Training Compliance'),
      options: chatOptions(chatIntentOpt('EMPLOYEE_TRAINING', 'Look up someone else', '')) };
  },
  TRAINING_POLICIES: async ctx => {
    const courses = (await chatbotDataService.courses()).filter(c => learningArea(c.category).id === 'compliance');
    const text = "The LMS doesn't keep a separate policy library, so I can't quote company policies. Policy training is delivered as compliance courses.";
    const rules = chatbotPermissions.staff() ? '\nHow the LMS applies training rules: mandatory training needs a deadline; overdue courses stay open and late completion is recorded; certificates are issued only on completion.' : '';
    if (!courses.length) return { text: `${text}${rules}\nNo compliance courses are published for you yet.`, options: chatOptions(chatbotPermissions.team() ? chatIntentOpt('TRAINING_COMPLIANCE', 'Training compliance') : null, chatNavOpt('catalog', 'Browse courses')) };
    return { ...chatList(`${text}${rules}\nCompliance and policy courses available to you:`, courses.map(c => chatCourseItem(c))), options: chatOptions(chatbotPermissions.team() ? chatIntentOpt('TRAINING_COMPLIANCE', 'Training compliance') : null) };
  },
  COURSE_MANAGEMENT: async ctx => {
    const guide = CHAT_GUIDES.find(g => g.id === 'create-course' && g.match.test(ctx.text || '') && chatGuideAllowed(g, ctx.role));
    const courses = await chatbotDataService.managedCourses(), count = s => courses.filter(c => c.status === s).length;
    const mine = ctx.role === 'trainer' ? 'You manage' : 'The LMS has';
    return { text: `${mine} ${chatPlural(courses.length, 'course')}: ${count('published')} published, ${count('draft')} draft, ${count('archived')} archived.${guide ? `\nTo create a course:\n${guide.steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}` : ''}`,
      options: chatOptions(chatbotPermissions.page('admin-courses') ? chatOpt('Create a course', { kind: 'create-course' }) : null, chatNavOpt('admin-courses', 'Open Manage Courses'), chatbotPermissions.staff() ? chatOpt('Assign a course', { kind: 'assign' }) : null) };
  },
  TRAINING_ASSIGNMENTS: async ctx => {
    if (!chatbotPermissions.staff()) return CHAT_HANDLERS.TEAM_COURSE_ASSIGNMENTS(ctx);
    const list = await chatbotDataService.assignments(), mandatory = list.filter(a => a.mandatory).length, now = chatToday().toISOString();
    const late = list.filter(a => a.deadlineAt && a.deadlineAt < now && a.completed < a.employees).length;
    const guide = CHAT_GUIDES.find(g => g.id === 'assign');
    return { text: `There are ${chatPlural(list.length, 'course assignment')} (${mandatory} mandatory${late ? `, ${late} past their deadline with people still to finish` : ''}).${/\bhow\b/.test(ctx.text || '') ? `\nTo assign a course:\n${guide.steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}` : ''}`,
      options: chatOptions(chatOpt('Assign a course', { kind: 'assign' }), chatIntentOpt('TEAM_OVERDUE_TRAINING', 'Overdue training'), chatNavOpt('compliance', 'Open Training Compliance')) };
  },
  TRAINING_REPORTS: async ctx => {
    let figure = '';
    if (ctx.role === 'trainer') { const data = await chatbotDataService.enrollments(); figure = ` ${chatPlural(data.total, 'enrolment')} in your courses.`; }
    else if (chatbotPermissions.team()) { const data = await chatCompliance({}); figure = ` ${data.summary.total} assignments in ${chatScopeName(data)}, ${data.summary.completionRate}% complete.`; }
    return { text: `Reports & Analytics has enrolment, employee, department, assessment, compliance and certificate reports, each filterable and exportable to CSV.${figure}`, options: chatOptions(chatNavOpt('reports', 'Open Reports & Analytics'), chatbotPermissions.team() ? chatIntentOpt('TRAINING_COMPLIANCE', 'Training compliance') : null) };
  },
  LMS_USER_GUIDANCE: async ctx => {
    const guides = CHAT_GUIDES.filter(g => chatGuideAllowed(g, ctx.role)), guide = guides.find(g => g.id === ctx.arg) || guides.find(g => g.match.test(ctx.text || ''));
    if (!guide) return { text: 'What would you like help with?', options: chatOptions(guides.map(g => chatIntentOpt('LMS_USER_GUIDANCE', g.label, g.id)), chatIntentOpt('LMS_OVERVIEW', 'Tour of the LMS')) };
    return { text: `${guide.label}:\n${guide.steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}`, options: chatOptions(guide.page ? chatNavOpt(guide.page, 'Take me there') : null, chatIntentOpt('LMS_USER_GUIDANCE', 'Other topics')) };
  },
  TRAINER_COURSES: async () => {
    const courses = await chatbotDataService.managedCourses();
    if (!courses.length) return { text: 'You are not the trainer or owner of any course yet.', options: chatOptions(chatNavOpt('admin-courses', 'Open Manage Courses')) };
    return { ...chatList(`You are the trainer or owner of ${chatPlural(courses.length, 'course')}:`, courses.map(c => ({ title: c.title, meta: `${capital(c.status)} · ${chatPlural(c.learners || 0, 'learner')} · ${chatPlural((c.resources || []).length, 'material')}`, tag: capital(c.status), tone: c.status === 'published' ? 'success' : 'gray', action: { kind: 'nav', page: 'admin-courses' }, actionLabel: 'Manage' })), 'admin-courses', 'Open Manage Courses'),
      options: chatOptions(chatIntentOpt('TRAINER_LEARNERS', "My learners' progress")) };
  },
  TRAINER_LEARNERS: async () => {
    const data = await chatbotDataService.enrollments(), rows = data.rows || [];
    if (!rows.length) return { text: 'No learners are enrolled in your courses yet.', options: chatOptions(chatNavOpt('reports', 'Open Reports & Analytics')) };
    return { ...chatList(`${chatPlural(data.total, 'enrolment')} in the courses you can report on:`, rows.map(r => ({ title: `${r.employee} — ${r.course}`, meta: `${r.department} · ${r.progress}% complete${r.dueDate ? ` · due ${r.dueDate}` : ''}`, tag: r.status, tone: r.status === 'Completed' ? 'success' : r.status === 'Overdue' ? 'danger' : '', action: { kind: 'nav', page: 'reports' }, actionLabel: 'View' })), 'reports', 'Open Reports & Analytics'),
      options: chatOptions(chatNavOpt('reports', 'Open Reports & Analytics')) };
  },
  OUT_OF_SCOPE: async ctx => ({ text: `That's outside what I can help with. I answer questions about learning in the LMS: courses, deadlines, assessments and certificates${chatbotPermissions.team() ? ', and the training records you look after' : ''}. Leave, timesheets and attendance are in the Timesheet app, and pay questions go to HR.`,
    options: chatSuggestionOptions(ctx.role, ctx.context).slice(0, 4) }),
};

/** Answer for an intent the role may not use: say so, and offer the closest thing they can see. */
function chatNotAllowed(intent, role) {
  const mine = CHAT_INTENTS.find(i => i.twin === intent.id);
  const who = intent.roles === CHAT_ALL ? '' : intent.roles.map(r => ({ admin: 'administrators', hr: 'HR', manager: 'managers', trainer: 'trainers', employee: 'employees' }[r])).join(', ').replace(/, ([^,]*)$/, ' and $1');
  return { text: `${intent.label} is available to ${who}. ${mine ? 'I can show your own learning instead:' : 'Here is what I can help you with:'}`, options: mine ? [chatIntentOpt(mine.id)] : chatSuggestionOptions(role).slice(0, 4) };
}

const chatbotResponseService = {
  /** Answer an intent for the signed-in user. Errors from the server (403, network) become a plain message. */
  async reply(intentId, ctx) {
    const intent = chatIntent(intentId);
    if (!intent || !CHAT_HANDLERS[intentId]) return { text: CHAT_FALLBACK_TEXT, options: CHAT_FALLBACK_OPTIONS.map(([id, label]) => chatIntentOpt(id, label)) };
    if (!chatAllowed(intent, ctx.role)) return chatNotAllowed(intent, ctx.role);
    try {
      return await CHAT_HANDLERS[intentId](ctx);
    } catch (error) {
      return { text: `I couldn't load that just now: ${error.message || 'the server did not respond'}. Please try again.`, options: [chatIntentOpt(intentId, 'Try again', ctx.arg), chatMenuOpt()], error: true };
    }
  },
  courseAction: (action, ctx, value) => chatCourseAction(action, ctx, value).catch(error => ({ text: `I couldn't load the course just now: ${error.message}.`, options: [chatMenuOpt()], error: true })),
  clarify(choices, reason) {
    return { text: reason === 'scope' ? 'Do you mean your own learning or your team\'s?' : 'I can help with a few things that match. Which one did you mean?', options: choices.map(id => chatIntentOpt(id, CHAT_SUGGESTION_LABELS[id] || chatIntent(id).label)) };
  },
  fallback() { return { text: CHAT_FALLBACK_TEXT, options: CHAT_FALLBACK_OPTIONS.map(([id, label]) => chatIntentOpt(id, label)) }; },
};
