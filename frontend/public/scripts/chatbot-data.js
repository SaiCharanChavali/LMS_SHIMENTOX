// ---------------------------------------------------------------- LMS assistant: data access (chatbotDataService, chatbotPermissions)
// Every figure the assistant shows comes from an existing portal API, called as the signed-in user. The server resolves
// who that is from the session and applies its own permissions (an employee sees their own records, a manager their
// direct reports, HR and admins the organisation), so nothing the browser sends can widen what comes back.
// The checks below only decide which answers to offer; they never replace the server's checks.

const chatbotPermissions = {
  team: () => CHAT_TEAM_ROLES.includes(currentUser?.role),          // Training Compliance (team for managers, all for HR/admin)
  staff: () => CHAT_STAFF_ROLES.includes(currentUser?.role),
  manageCourses: () => can('courses.manage'),                          // admin, HR, trainer (trainers: their own courses)
  assign: () => can('courses.assign'),
  reports: () => can('reports.view'),
  trainer: () => currentUser?.role === 'trainer',
  page: page => typeof resolvePage === 'function' && resolvePage(page) === page,  // the sidebar's own route rules
};

const chatbotDataService = {
  /** The user's course list: assignments, deadlines, status and progress, exactly as My Learning shows them. */
  async courses() { const data = await api('courses'); courseCatalog = data.courses; return data.courses; },
  async certificates() { return (await api('certificates')).certificates; },
  async assessments() { return (await api('me/assessments')).assessments; },
  async calendar() { return api('me/calendar'); },
  /** Training Compliance rows and totals. Scoped by the server: direct reports for managers, everyone for HR and admins. */
  async compliance(params = {}) { return api('manage/compliance' + qs({ size: 50, ...params })); },
  /** Courses the user manages: all for admin and HR, owned courses for trainers. */
  async managedCourses() { return (await api('admin/courses')).courses; },
  async assignments() { return (await api('manage/assignments')).assignments; },
  /** Enrolment report; trainers see only their own courses' learners. */
  async enrollments(params = {}) { return api('manage/reports' + qs({ type: 'enrollments', ...params })); },
};

// ---- small helpers shared by the answers

const chatDeadlineAt = c => c.deadline?.at || null;
const chatIsPending = c => !c.completed && (Boolean(c.assignment) || c.started);
const chatPct = value => `${Math.max(0, Math.min(100, Math.round(Number(value) || 0)))}%`;
const chatPlural = (n, word, many = word + 's') => `${n} ${n === 1 ? word : many}`;
const chatStatusTone = status => ({ completed: 'success', overdue: 'danger', in_progress: '', not_started: 'gray', due_soon: 'due-soon', completed_on_time: 'success', completed_late: 'success' }[status] ?? 'gray');
const CHAT_STATUS_LABELS = { completed: 'Completed', overdue: 'Overdue', in_progress: 'In progress', not_started: 'Not started' };

/** One course as a list row with an Open button. */
function chatCourseItem(c, extra = '') {
  const deadline = c.deadline?.display ? `Due ${c.deadline.display} ${c.deadline.timezone || ''}`.trim() : '';
  const status = c.deadline && !c.completed ? (c.deadline.label || CHAT_STATUS_LABELS[c.status]) : CHAT_STATUS_LABELS[c.status] || capital(c.status || '');
  const tone = c.deadline && !c.completed ? chatStatusTone(c.deadline.status) : chatStatusTone(c.status);
  return { title: c.title, meta: [c.assignment?.mandatory ? 'Mandatory' : c.assignment ? 'Assigned' : '', `${chatPct(c.completed ? 100 : c.progress)} complete`, deadline, extra].filter(Boolean).join(' · '),
    tag: status, tone, action: { kind: 'course', id: c.id }, actionLabel: c.completed ? 'Review' : c.started ? 'Continue' : 'Start' };
}
