// ---------------------------------------------------------------- LMS assistant: configuration (chatbotConfig)
// A rule-based assistant, built like the Timesheet assistant: typed text is matched to an intent with keywords and
// regular expressions, and every answer is read from the portal's own APIs. No AI service is involved.
// Intents, patterns and suggested questions live here so that detection (chatbot-intents.js), data access
// (chatbot-data.js), answers (chatbot-responses.js) and the panel (chatbot.js) stay separate.

/**
 * @typedef {'admin'|'hr'|'trainer'|'manager'|'employee'} ChatRole
 * @typedef {{id:string, label:string, roles:ChatRole[]|'*', priority:number, patterns:Array<[RegExp, number]>, twin?:string, scope?:'mine'|'team', internal?:boolean}} ChatIntent
 * @typedef {{kind:'intent', intent:string, arg?:string} | {kind:'nav', page:string} | {kind:'course', id:string, lesson?:string}
 *   | {kind:'course-action', action:'summarize'|'explain'|'practice'|'revision'} | {kind:'assign', courseId?:string} | {kind:'create-course'}} ChatAction
 * @typedef {{id:string, label:string, action:ChatAction}} ChatOption
 * @typedef {{title:string, meta?:string, tag?:string, tone?:string, action?:ChatAction, actionLabel?:string}} ChatItem
 * @typedef {{id:number, from:'bot'|'user', text:string, items?:ChatItem[], options?:ChatOption[], more?:ChatOption}} ChatMessage
 * @typedef {{role:ChatRole, name:string, course:{id:string, title:string}|null, lessonId:string|null}} ChatbotUserContext
 * @typedef {{messages:ChatMessage[], expect:null|{type:'term'|'course'|'employee', intent?:string}, nextId:number}} ConversationState
 */

const CHAT_ALL = '*';
const CHAT_TEAM_ROLES = ['manager', 'hr', 'admin'];
const CHAT_STAFF_ROLES = ['hr', 'admin'];
const CHAT_COURSE_STAFF = ['admin', 'hr', 'trainer'];
const CHAT_LIST_LIMIT = 8;            // Rows shown in one answer before "Show more".
const CHAT_TYPING_MS = 350;           // Short pause before a reply, so answers do not flash in.
const CHAT_HISTORY_LIMIT = 80;        // Messages kept for the current browser session.
const CHAT_INPUT_LIMIT = 300;

// Common misspellings, corrected before matching so patterns can stay strict (word boundaries, no fuzzy guessing).
const CHAT_SPELLING = [
  [/\b(cource|corse|coarse|cours|couse|coures)(s?)\b/g, 'course$2'],
  [/\b(certficate|certifcate|certificat|cirtificate|certificte|sertificate)(s?)\b/g, 'certificate$2'],
  [/\b(assesment|assessmnt|asessment|assessement|assesmnt)(s?)\b/g, 'assessment$2'],
  [/\b(progres|progess|prgress|progrss)\b/g, 'progress'],
  [/\b(deadine|dedline|deadlne|dealine|deadlie)(s?)\b/g, 'deadline$2'],
  [/\b(trainning|traning|trainig|trainng)\b/g, 'training'],
  [/\b(complaince|compliace|complience|compliance)\b/g, 'compliance'],
  [/\b(overdew|over due|overdu)\b/g, 'overdue'],
  [/\b(pendng|pening|pendig)\b/g, 'pending'],
  [/\b(compleated|completd|complted)\b/g, 'completed'],
  [/\b(lessson|leson)(s?)\b/g, 'lesson$2'],
  [/\b(modul)(s?)\b/g, 'module$2'],
  [/\bplz|pls\b/g, 'please'],
];

// Signals used to choose between a personal intent and its team twin ("my overdue" vs "my team's overdue").
const CHAT_MINE = /\b(my|me|mine|myself|i|i'm|im|i've)\b/;
const CHAT_TEAM = /\b(team|teams|my reports|direct reports|reportees|subordinates|employees|staff|members|people|everyone|organi[sz]ation|company)\b/;
// Words that make a message about other employees, never about the user's own learning.
const CHAT_WHO = /\b(who|which (employees|people|staff|members|learners))\b/;

const W = words => new RegExp(`\\b(${words})\\b`);
const COURSE_WORD = '(courses?|trainings?|learning|programs?|programmes?)';
const ASSESS_WORD = '(assessments?|exams?|quiz(zes)?|tests?|knowledge checks?)';

/** @type {ChatIntent[]} */
const CHAT_INTENTS = [
  // ---- general LMS navigation
  { id: 'HELP', label: 'Help', roles: CHAT_ALL, priority: 3, patterns: [
    [/^(hi+|hello|hey|hiya|good (morning|afternoon|evening)|namaste)\b/, 4], [/\b(help|what can you do|how (do|can) you help|options|menu|commands|get started)\b/, 4]] },
  { id: 'THANKS', label: 'Thanks', roles: CHAT_ALL, priority: 2, patterns: [[/^(thanks?|thank you|thx|ty|great|cool|awesome|perfect|ok(ay)?|got it)\W*$/, 6]] },
  { id: 'LMS_OVERVIEW', label: 'What is in the LMS', roles: CHAT_ALL, priority: 4, patterns: [
    [/\b(what is|what's|about|overview|tour|explain|introduce)\b.*\b(lms|portal|platform|this (site|app|system))\b/, 6], [/\b(lms|portal) (overview|features|sections)\b/, 6], [/\bwhat can i do here\b/, 6]] },
  { id: 'FIND_COURSE', label: 'Find a course', roles: CHAT_ALL, priority: 4, patterns: [
    [new RegExp(`\\b(find|search|browse|look(ing)? for|recommend\\w*|suggest\\w*|explore|discover|want to learn|interested in)\\b.*\\b${COURSE_WORD}`), 5],
    [/\b(course (catalog(ue)?|list)|catalog(ue)?|all courses|available courses|new courses|which courses)\b/, 5],
    [/\b(technical|ai|data|business|soft skills?|professional|leadership|management|recruitment|hr|security|compliance|policy)\b.*\bcourses?\b/, 8]] },
  { id: 'FIND_TRAINING', label: 'Training sessions', roles: CHAT_ALL, priority: 5, patterns: [
    [/\b(training sessions?|sessions?|workshops?|webinars?|live (training|class(es)?)|classroom|instructor[- ]led|training calendar|calendar|events?)\b/, 5]] },
  { id: 'NAVIGATE_TO_ASSESSMENTS', label: 'Open Assessments', roles: CHAT_ALL, priority: 7, patterns: [
    [new RegExp(`\\b(where|open|go to|navigate|take me|find|start|take|attempt)\\b.*\\b${ASSESS_WORD}`), 5], [/\bassessments? page\b/, 6]] },
  { id: 'NAVIGATE_TO_CERTIFICATES', label: 'Open Certificates', roles: CHAT_ALL, priority: 8, patterns: [
    [/\b(where|open|go to|navigate|take me|find|download|print|get|share|verify)\b.*\bcertificates?\b/, 5], [/\bcertificates? (page|section)\b/, 6]] },

  // ---- the user's own learning (every role learns, so every role has these)
  { id: 'MY_ASSIGNED_COURSES', label: 'My assigned courses', roles: CHAT_ALL, priority: 5, twin: 'TEAM_COURSE_ASSIGNMENTS', scope: 'mine', patterns: [
    [/\bassigned\b/, 4], [/\b(my )?(assignments?|required (courses?|training)|courses? (i|i have to|i need to) (take|do|complete))\b/, 3], [new RegExp(`\\bmy ${COURSE_WORD}\\b`), 2]] },
  { id: 'MY_PENDING_COURSES', label: 'My pending courses', roles: CHAT_ALL, priority: 6, twin: 'TEAM_PENDING_TRAINING', scope: 'mine', patterns: [
    [/\b(pending|remaining|incomplete|unfinished|outstanding|to ?do|not (yet )?(done|completed|finished|started)|yet to (do|complete|finish|start)|left to (do|complete))\b/, 5]] },
  { id: 'MY_PENDING_ALL', label: 'All pending courses', roles: CHAT_ALL, priority: 1, internal: true, patterns: [] },
  { id: 'MY_MANDATORY', label: 'Mandatory training', roles: CHAT_ALL, priority: 6, twin: 'TEAM_COURSE_ASSIGNMENTS', scope: 'mine', patterns: [[/\b(mandatory|compulsory|required)\b/, 5]] },
  { id: 'MY_COMPLETED_COURSES', label: 'My completed courses', roles: CHAT_ALL, priority: 6, twin: 'TEAM_LEARNING_PROGRESS', scope: 'mine', patterns: [
    [new RegExp(`\\b(completed|finished|done with|passed)\\b.*\\b${COURSE_WORD}|\\b${COURSE_WORD}\\b.*\\b(completed|finished)\\b|\\bhave i (completed|finished)\\b`), 6]] },
  { id: 'MY_LEARNING_PROGRESS', label: 'My learning progress', roles: CHAT_ALL, priority: 5, twin: 'TEAM_LEARNING_PROGRESS', scope: 'mine', patterns: [
    [/\b(progress|how (am i|far|much)|completion|completed so far|percent(age)?|how .*(doing|going))\b/, 5], [/\b(in progress|continue( learning)?|resume|where (did|was) i)\b/, 4]] },
  { id: 'MY_UPCOMING_DEADLINES', label: 'My upcoming deadlines', roles: CHAT_ALL, priority: 6, twin: 'TEAM_PENDING_TRAINING', scope: 'mine', patterns: [
    [/\b(deadlines?|due( dates?)?|due soon|upcoming|when (is|are) .*due|by when|time left)\b/, 5]] },
  { id: 'MY_OVERDUE_TRAINING', label: 'My overdue training', roles: CHAT_ALL, priority: 7, twin: 'TEAM_OVERDUE_TRAINING', scope: 'mine', patterns: [
    [/\b(overdue|past due|missed( (deadlines?|due dates?))?|late|behind schedule)\b/, 6]] },
  { id: 'MY_CERTIFICATES', label: 'My certificates', roles: CHAT_ALL, priority: 6, patterns: [[/\b(certificates?|certified|certification|credentials?)\b/, 5]] },
  { id: 'LEARNING_MATERIALS', label: 'Learning materials', roles: CHAT_ALL, priority: 5, patterns: [
    [/\b(materials?|resources?|documents?|pdfs?|slides?|handouts?|downloads?|reading|notes)\b/, 5]] },

  // ---- course information (a course is named, or the panel is open on a course page)
  { id: 'COURSE_DETAILS', label: 'Course details', roles: CHAT_ALL, priority: 4, patterns: [[/\b(about|details?|info(rmation)?|describe|description|tell me (about|more)|overview of)\b/, 3]] },
  { id: 'COURSE_DURATION', label: 'Course duration', roles: CHAT_ALL, priority: 6, patterns: [[/\b(how long|duration|how many (hours|minutes)|length of|time (does it take|to (complete|finish))|hours)\b/, 5]] },
  { id: 'COURSE_CATEGORY', label: 'Course category', roles: CHAT_ALL, priority: 6, patterns: [[/\b(categor(y|ies)|which area|what type of course|kind of course)\b/, 5]] },
  { id: 'COURSE_LEVEL', label: 'Course level', roles: CHAT_ALL, priority: 6, patterns: [[/\b(level|difficulty|difficult|beginner|intermediate|advanced|expert|hard|easy)\b/, 5]] },
  { id: 'COURSE_CONTENT', label: 'Course content', roles: CHAT_ALL, priority: 6, patterns: [[/\b(lessons?|modules?|syllabus|curriculum|topics?|contents?|chapters?|outline|what('s| is) (in|covered)|covers?)\b/, 5]] },

  // On a course page: where a concept is explained in the course's own lessons.
  { id: 'EXPLAIN_TERM', label: 'Explain a concept', roles: CHAT_ALL, priority: 4, patterns: [[/\b(explain|define|definition of|meaning of|what (is|are|does)( a| an| the)?)\b/, 4]] },

  // ---- assessments
  { id: 'ASSESSMENT_INFORMATION', label: 'My assessments', roles: CHAT_ALL, priority: 5, patterns: [
    [new RegExp(`\\b${ASSESS_WORD}`), 4], [/\b(pass(ing)? (mark|score|percentage)|attempts? (left|remaining|allowed)|time limit|how many questions)\b/, 5]] },
  { id: 'ASSESSMENT_DEADLINE', label: 'Assessment deadlines', roles: CHAT_ALL, priority: 7, patterns: [
    [new RegExp(`\\b${ASSESS_WORD}.*\\b(deadlines?|due|when)\\b|\\b(deadlines?|due|when)\\b.*\\b${ASSESS_WORD}`), 9]] },
  { id: 'ASSESSMENT_STATUS', label: 'Assessment results', roles: CHAT_ALL, priority: 7, patterns: [
    [new RegExp(`\\b${ASSESS_WORD}.*\\b(results?|scores?|status|passed|failed|marks?|grades?)\\b|\\b(results?|scores?|marks?|grades?)\\b.*\\b${ASSESS_WORD}`), 9], [/\b(did i pass|my (results?|scores?|marks?|grades?))\b/, 8]] },
  { id: 'PRACTICE_QUESTIONS', label: 'Practice questions', roles: CHAT_ALL, priority: 7, patterns: [
    [/\b(practi[cs]e|revis(e|ion)|mock|sample questions?|exercises?|prepare for|study for)\b/, 6]] },

  // ---- manager (and organisation-wide for HR and admins, from Training Compliance)
  { id: 'TEAM_LEARNING_PROGRESS', label: 'Team learning progress', roles: CHAT_TEAM_ROLES, priority: 7, scope: 'team', patterns: [
    [/\b(progress|status|completion|how .*(doing|going)|learning)\b/, 3]] },
  { id: 'TEAM_PENDING_TRAINING', label: 'Team pending training', roles: CHAT_TEAM_ROLES, priority: 7, scope: 'team', patterns: [
    [/\b(pending|remaining|incomplete|outstanding|not (yet )?(done|completed|started)|in progress)\b/, 3]] },
  { id: 'TEAM_OVERDUE_TRAINING', label: 'Team overdue training', roles: CHAT_TEAM_ROLES, priority: 8, scope: 'team', patterns: [
    [/\b(overdue|past due|missed|late|behind)\b/, 3]] },
  { id: 'TEAM_COURSE_ASSIGNMENTS', label: 'Team training requirements', roles: CHAT_TEAM_ROLES, priority: 7, scope: 'team', patterns: [
    [/\b(assigned|assignments?|requirements?|required|mandatory|needs?( to (do|complete|take))?)\b/, 3]] },

  // ---- HR and admin
  { id: 'TRAINING_COMPLIANCE', label: 'Training compliance', roles: CHAT_TEAM_ROLES, priority: 8, patterns: [[/\b(compliance|compliant|non[- ]?compliant|audit)\b/, 7]] },
  { id: 'DEPARTMENT_TRAINING', label: 'Training by department', roles: CHAT_TEAM_ROLES, priority: 8, patterns: [[/\b(departments?|by department|per department|department[- ]wise|teams? comparison)\b/, 7]] },
  { id: 'EMPLOYEE_TRAINING', label: 'One employee\'s training', roles: CHAT_TEAM_ROLES, priority: 8, patterns: [
    [/\b(training|courses?|progress|records?|status|learning) (of|for) (?!my\b|me\b|the team\b|team\b|all\b|everyone\b|each\b)[a-z]/, 7], [/\b(employee|staff member|person|learner)'?s? (training|records?|progress)\b/, 6]] },
  { id: 'TRAINING_POLICIES', label: 'Training policies', roles: CHAT_ALL, priority: 7, patterns: [[/\b(polic(y|ies)|guidelines?|code of conduct|rules for training|training rules)\b/, 7]] },
  { id: 'COURSE_MANAGEMENT', label: 'Course management', roles: CHAT_COURSE_STAFF, priority: 8, patterns: [
    [/\b(create|add|edit|update|publish|unpublish|archive|delete|build|upload|manage)\b.*\b(courses?|lessons?|content)\b/, 7], [/\bmanage courses\b/, 8]] },
  { id: 'TRAINING_ASSIGNMENTS', label: 'Course assignments', roles: ['manager', 'hr', 'admin'], priority: 8, patterns: [
    [/\b(assign|assigning|allocate|enrol+)\b.*\b(courses?|training|to)\b/, 7], [/\bhow (do|can) i assign\b/, 8], [/\bcourse assignments?\b/, 6]] },
  { id: 'TRAINING_REPORTS', label: 'Training reports', roles: ['admin', 'hr', 'manager', 'trainer'], priority: 7, patterns: [
    [/\b(reports?|analytics|statistics|stats|metrics|export|csv|excel)\b/, 6]] },
  { id: 'LMS_USER_GUIDANCE', label: 'How to use the LMS', roles: CHAT_ALL, priority: 3, patterns: [
    [/\b(how (do|can|to) i|how to|where (do|can) i|steps to|guide|walk me through|tutorial)\b/, 4], [/\b(use|using|navigate|navigating|get around)\b.*\b(lms|portal|site|app)\b/, 2],
    [/\b(reminders?|onboarding|users?|accounts?|password|profile|dark mode|theme)\b/, 2]] },

  // ---- trainer
  { id: 'TRAINER_COURSES', label: 'Courses I teach', roles: ['trainer'], priority: 8, patterns: [
    [/\b(courses? i (own|teach|train|created|manage|run)|my (own|trainer) courses|i (teach|train|own)|teaching|courses? assigned to me as (a )?trainer)\b/, 8]] },
  { id: 'TRAINER_LEARNERS', label: 'My learners\' progress', roles: ['trainer', 'hr', 'admin'], priority: 7, patterns: [
    [/\b(learners?|students?|participants?|trainees?|enrol+ments?|enrolled)\b/, 6]] },

  // ---- outside the assistant's scope: answered honestly instead of guessed
  { id: 'OUT_OF_SCOPE', label: 'Not supported', roles: CHAT_ALL, priority: 9, patterns: [
    [/\b(salary|payslip|payroll|leaves?|holidays?|vacation|time ?off|timesheets?|attendance|overtime|weather|news|jokes?|stock|cricket|movie)\b/, 8]] },
];

// Suggested questions per role. Each one is a real intent; course actions are added when a course page is open.
const CHAT_SUGGESTIONS = {
  employee: ['MY_ASSIGNED_COURSES', 'MY_PENDING_COURSES', 'MY_COMPLETED_COURSES', 'MY_LEARNING_PROGRESS', 'MY_UPCOMING_DEADLINES', 'MY_CERTIFICATES', 'LEARNING_MATERIALS', 'FIND_COURSE'],
  manager: ['TEAM_LEARNING_PROGRESS', 'TEAM_PENDING_TRAINING', 'TEAM_OVERDUE_TRAINING', 'TEAM_COURSE_ASSIGNMENTS', 'MY_PENDING_COURSES', 'MY_UPCOMING_DEADLINES'],
  hr: ['TRAINING_COMPLIANCE', 'EMPLOYEE_TRAINING', 'DEPARTMENT_TRAINING', 'TRAINING_ASSIGNMENTS', 'TRAINING_POLICIES', 'TEAM_OVERDUE_TRAINING'],
  admin: ['COURSE_MANAGEMENT', 'TRAINING_REPORTS', 'TRAINING_ASSIGNMENTS', 'TRAINING_COMPLIANCE', 'LMS_USER_GUIDANCE', 'TEAM_OVERDUE_TRAINING'],
  trainer: ['TRAINER_COURSES', 'TRAINER_LEARNERS', 'LEARNING_MATERIALS', 'TRAINING_REPORTS', 'MY_PENDING_COURSES'],
};
// Labels for suggestion chips, phrased as the user would ask.
const CHAT_SUGGESTION_LABELS = {
  MY_ASSIGNED_COURSES: 'My assigned courses', MY_PENDING_COURSES: 'My pending courses', MY_COMPLETED_COURSES: 'My completed courses',
  MY_LEARNING_PROGRESS: 'My learning progress', MY_UPCOMING_DEADLINES: 'My upcoming deadlines', MY_CERTIFICATES: 'My certificates',
  LEARNING_MATERIALS: 'Find learning materials', FIND_COURSE: 'Find a course', TEAM_LEARNING_PROGRESS: 'Team learning progress',
  TEAM_PENDING_TRAINING: 'Team pending courses', TEAM_OVERDUE_TRAINING: 'Overdue training', TEAM_COURSE_ASSIGNMENTS: 'Team training requirements',
  TRAINING_COMPLIANCE: 'Training compliance', EMPLOYEE_TRAINING: 'Employee training information', DEPARTMENT_TRAINING: 'Training by department',
  TRAINING_ASSIGNMENTS: 'Course assignments', TRAINING_POLICIES: 'Training policies', COURSE_MANAGEMENT: 'Course management',
  TRAINING_REPORTS: 'Training reports', LMS_USER_GUIDANCE: 'How do I use the LMS?', TRAINER_COURSES: 'Courses I teach', TRAINER_LEARNERS: 'My learners\' progress',
};
// Quick actions on a course page, kept from the course assistant this panel replaces.
const CHAT_COURSE_ACTIONS = [['summarize', 'Summarise'], ['explain', 'Explain a concept'], ['practice', 'Practice'], ['revision', 'What to revise']];
// Shown when nothing matches, as the specification asks.
const CHAT_FALLBACK_TEXT = "I'm sorry, I couldn't understand that question. You can choose one of the options below or try asking differently.";
const CHAT_FALLBACK_OPTIONS = [['MY_ASSIGNED_COURSES', 'My Courses'], ['MY_LEARNING_PROGRESS', 'Learning Progress'], ['MY_UPCOMING_DEADLINES', 'Training Deadlines'], ['HELP', 'Help']];
