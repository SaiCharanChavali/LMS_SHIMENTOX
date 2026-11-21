// ---------------------------------------------------------------- LMS assistant: intent detection (intentDetector)
// Pure functions: text in, a decision out. Nothing here reads the page or calls the server.
//
// 1. normalise: lower case, straight quotes, common misspellings corrected, punctuation removed.
// 2. score: every pattern of every intent that matches adds its weight. Patterns use word boundaries, so short or
//    generic words ("in", "my", "do") never match on their own.
// 3. scope: a personal intent ("my overdue training") and its team twin ("my team's overdue training") share keywords.
//    Team words choose the team intent; for roles that can see a team, a message with neither "my" nor team words is
//    ambiguous and the user is asked which one they mean.
// 4. choose: below the threshold is unknown; otherwise the highest score wins, and near ties go to the intent with the
//    higher priority. Equal scores and equal priorities are ambiguous and the user is asked to pick.

const CHAT_THRESHOLD = 4;     // Lowest score accepted as an intent.
const CHAT_TEAM_BONUS = 4;    // Added to a team intent when the message is about other people.
const CHAT_COURSE_BONUS = 3;  // Added to course-information intents when a course is named or open.
const CHAT_COURSE_INTENTS = ['COURSE_DETAILS', 'COURSE_DURATION', 'COURSE_CATEGORY', 'COURSE_LEVEL', 'COURSE_CONTENT'];
const CHAT_STOPWORDS = new Set(['the', 'and', 'for', 'with', 'from', 'into', 'your', 'course', 'courses', 'training', 'introduction', 'intro', 'basics', 'fundamentals', 'essentials', 'awareness', 'program', 'programme', 'part', 'level']);

function chatNormalize(text) {
  let t = String(text || '').toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
  for (const [pattern, replacement] of CHAT_SPELLING) t = t.replace(pattern, replacement);
  return t.replace(/[^a-z0-9'&+#.\s-]/g, ' ').replace(/\s+/g, ' ').trim();
}

function chatIntent(id) { return CHAT_INTENTS.find(intent => intent.id === id) || null; }

function chatAllowed(intent, role) { return Boolean(intent) && (intent.roles === CHAT_ALL || intent.roles.includes(role)); }

/** Significant words of a course title, used to recognise the course in a message. */
function chatTitleWords(title) {
  return chatNormalize(title).split(' ').map(w => w.replace(/[^a-z0-9+#]/g, '')).filter(w => w.length >= 3 && !CHAT_STOPWORDS.has(w));
}

/** The course a message names, matched against the user's own course list (never a hard-coded list). */
function chatFindCourse(text, courses) {
  const t = chatNormalize(text), words = new Set(t.split(' ').map(w => w.replace(/[^a-z0-9+#]/g, '')));
  let best = null, bestScore = 0;
  for (const course of courses || []) {
    const title = chatNormalize(course.title);
    if (title.length >= 4 && t.includes(title)) return course;  // The full title wins outright.
    const sig = chatTitleWords(course.title);
    if (!sig.length) continue;
    const hits = sig.filter(w => words.has(w)), longHit = hits.some(w => w.length >= 4 || /[+#]/.test(w));
    const score = hits.length / sig.length;
    if (longHit && (score >= 0.6 || hits.length >= 2) && score > bestScore) { best = course; bestScore = score; }
  }
  return best;
}

/**
 * Score every intent for a message.
 * @param {string} text the user's message
 * @param {{role:string, courses?:Array<{id:string,title:string}>, courseContext?:boolean}} ctx
 * @returns {{text:string, scores:Array<{id:string,score:number,priority:number}>, course:object|null, mine:boolean, team:boolean}}
 */
function chatScore(text, ctx) {
  const t = chatNormalize(text), role = ctx.role;
  const team = CHAT_TEAM.test(t) || CHAT_WHO.test(t), mine = CHAT_MINE.test(t);
  const course = chatFindCourse(t, ctx.courses), courseRef = Boolean(course) || (ctx.courseContext && /\b(this|current) (course|lesson|module)\b|\bit\b/.test(t)) || Boolean(ctx.courseContext);
  const canTeam = CHAT_TEAM_ROLES.includes(role);
  const scores = [];
  for (const intent of CHAT_INTENTS) {
    if (intent.internal) continue;
    let score = 0;
    for (const [pattern, weight] of intent.patterns) if (pattern.test(t)) score += weight;
    if (!score) continue;
    if (intent.scope === 'team') {
      if (!team) continue;  // Team intents need a message about other people.
      score += CHAT_TEAM_BONUS;
    }
    if (intent.scope === 'mine' && team && canTeam && !/\b(my own|myself|for me)\b/.test(t)) score -= CHAT_TEAM_BONUS;
    if (CHAT_COURSE_INTENTS.includes(intent.id) && courseRef) score += CHAT_COURSE_BONUS;
    if (score > 0) scores.push({ id: intent.id, score, priority: intent.priority });
  }
  scores.sort((a, b) => b.score - a.score || b.priority - a.priority);
  return { text: t, scores, course, mine, team };
}

/**
 * Decide what a message means.
 * @returns {{type:'intent', intent:string, course:object|null}
 *   | {type:'clarify', choices:string[], reason:'scope'|'tie', course:object|null}
 *   | {type:'unknown', course:object|null}}
 */
function detectIntent(text, ctx) {
  const scored = chatScore(text, ctx), role = ctx.role;
  if (scored.text.length < 2) return { type: 'unknown', course: null };
  const found = scored.scores.filter(s => s.score >= CHAT_THRESHOLD);
  // Prefer what the role may use. An intent outside the role is kept only when it is clearly the stronger match,
  // so the answer can say plainly that it is not available (for example, team records asked for by an employee).
  const usable = found.filter(s => chatAllowed(chatIntent(s.id), role));
  const candidates = usable.length && !(found.length && found[0].score - usable[0].score >= 1 && !chatAllowed(chatIntent(found[0].id), role)) ? usable : found;
  // A course named on its own ("Python Programming") is a request for that course's details.
  if (!candidates.length) return scored.course ? { type: 'intent', intent: 'COURSE_DETAILS', course: scored.course } : { type: 'unknown', course: scored.course };
  // Near ties (within one point) go to the higher priority, e.g. "where are my certificates" opens the page.
  const near = candidates.filter(s => candidates[0].score - s.score <= 1).sort((a, b) => b.priority - a.priority || b.score - a.score);
  const top = near[0], intent = chatIntent(top.id);
  // "Pending courses" from a manager: their own, or their team's?
  if (intent.scope === 'mine' && intent.twin && !scored.mine && !scored.team && chatAllowed(chatIntent(intent.twin), role))
    return { type: 'clarify', choices: [top.id, intent.twin], reason: 'scope', course: scored.course };
  // Same score and same priority: genuinely ambiguous, so the user chooses.
  const ties = near.filter(s => s.id !== top.id && s.score === top.score && s.priority === top.priority && chatAllowed(chatIntent(s.id), role));
  if (ties.length && chatAllowed(intent, role)) return { type: 'clarify', choices: [top.id, ...ties.map(s => s.id)].slice(0, 3), reason: 'tie', course: scored.course };
  return { type: 'intent', intent: top.id, course: scored.course };
}

/** "Explain <term>": the term itself, without the request words around it. */
function chatExtractTerm(text) {
  return chatNormalize(text).replace(/^(please |can you |could you )?(explain|define|what is|what are|what's|tell me about|meaning of|describe)( the| a| an)?\s*/, '').replace(/\?+$/, '').trim().slice(0, 60);
}

/** "Training for Asha Rao" -> "asha rao": the name searched for in Training Compliance. */
function chatExtractPerson(text) {
  const t = chatNormalize(text), match = /\b(?:of|for|about)\s+([a-z][a-z .'-]{1,60})$/.exec(t);
  return (match ? match[1] : t).replace(/\b(training|courses?|progress|records?|status|learning|employee|please)\b/g, '').replace(/\s+/g, ' ').trim();
}
