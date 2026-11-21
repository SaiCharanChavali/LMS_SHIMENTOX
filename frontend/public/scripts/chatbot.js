// ---------------------------------------------------------------- LMS assistant: panel (LMSChatbot) and conversation (conversationService)
// A floating, rule-based assistant on every signed-in page, built like the Timesheet assistant: a launcher, a panel with
// header, message log, suggested questions and an input, and replies with buttons that carry out real actions.
// It lives outside #app, so the portal's own render never wipes it; the portal's render only tells it to sync.
// It is hidden during exams and assessments, so it can never be used while one is in progress.

const chatbot = { open: false, minimized: false, typing: false, epoch: 0, userId: null, root: null, actions: [], state: { messages: [], expect: null, nextId: 1 }, timer: null };
const CHAT_STORE_PREFIX = 'shimentox-lms-chat:';

// ---- conversationService: the current conversation, kept for this browser session only (cleared at sign-out).
// Nothing is stored on the server: the answers are always re-read from live data, so old answers are a convenience only.
const conversationService = {
  key: () => CHAT_STORE_PREFIX + (currentUser?.id || 'anonymous'),
  load() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(this.key()) || 'null');
      if (saved && Array.isArray(saved.messages)) return { messages: saved.messages.slice(-CHAT_HISTORY_LIMIT), expect: saved.expect || null, nextId: Number(saved.nextId) || saved.messages.length + 1 };
    } catch { /* Private mode or a corrupt entry: start a fresh conversation. */ }
    return { messages: [], expect: null, nextId: 1 };
  },
  save(state) { try { sessionStorage.setItem(this.key(), JSON.stringify({ ...state, messages: state.messages.slice(-CHAT_HISTORY_LIMIT) })); } catch { /* Storage full or blocked: the panel still works. */ } },
  clearAll() {
    try { for (let i = sessionStorage.length - 1; i >= 0; i--) { const key = sessionStorage.key(i); if (key?.startsWith(CHAT_STORE_PREFIX)) sessionStorage.removeItem(key); } } catch { /* Nothing stored. */ }
  },
};

const chatOnPage = page => String(location.hash || '').replace(/^#/, '') === page;
/** @returns {ChatbotUserContext} who is asking and which course page (if any) is open; the server still decides access. */
function chatbotContext() {
  const onCourse = chatOnPage('course') && currentCourseInfo?.id && !(typeof examActive === 'function' && examActive());
  return { role: currentUser?.role || 'employee', name: currentUser?.name || '', course: onCourse ? { id: currentCourseInfo.id, title: currentCourseInfo.title } : null, lessonId: onCourse ? (selectedLessonId || null) : null };
}
function chatbotAvailable() {
  return Boolean(typeof portalReady !== 'undefined' && portalReady && currentUser && !currentUser.mustChangePassword && !(typeof examActive === 'function' && examActive()));
}

// ---------------------------------------------------------------- conversation

function chatPush(from, text, extra = {}) {
  const message = { id: chatbot.state.nextId++, from, text: String(text || ''), ...extra };
  chatbot.state.messages.push(message);
  if (chatbot.state.messages.length > CHAT_HISTORY_LIMIT) chatbot.state.messages.splice(0, chatbot.state.messages.length - CHAT_HISTORY_LIMIT);
  conversationService.save(chatbot.state);
  chatPaint();
  return message;
}

/** Show the typing indicator, wait for the answer (and a short pause), then post it unless the chat was reset meanwhile. */
async function chatAnswer(produce) {
  const epoch = chatbot.epoch;
  chatbot.typing = true; chatPaint();
  const [reply] = await Promise.all([Promise.resolve().then(produce).catch(error => ({ text: `Something went wrong: ${error.message}.`, options: [chatMenuOpt()], error: true })), new Promise(resolve => setTimeout(resolve, CHAT_TYPING_MS))]);
  if (epoch !== chatbot.epoch) return;
  chatbot.typing = false;
  chatbot.state.expect = reply.expect || null;
  chatPush('bot', reply.text, { items: reply.items || [], options: reply.options || [], more: reply.more || null, error: Boolean(reply.error) });
}

const chatCtx = (extra = {}) => ({ ...chatbotContext(), context: chatbotContext(), text: '', ...extra });
const CHAT_COURSE_ARG_INTENTS = [...CHAT_COURSE_INTENTS, 'LEARNING_MATERIALS'];

function chatRunIntent(intent, extra = {}) {
  return chatAnswer(async () => {
    let courseArg = extra.courseArg || null;
    if (!courseArg && extra.arg && CHAT_COURSE_ARG_INTENTS.includes(intent)) courseArg = (await chatbotDataService.courses()).find(c => c.id === extra.arg) || null;
    return chatbotResponseService.reply(intent, chatCtx({ ...extra, courseArg }));
  });
}

/** Typed text: the expected answer to a question just asked, a reset word, or a new question. */
async function chatHandleText(raw) {
  const text = String(raw || '').trim().slice(0, CHAT_INPUT_LIMIT);
  if (!text || chatbot.typing) return;
  chatPush('user', text);
  if (/^(menu|main menu|start over|restart|reset|cancel|stop|back)$/i.test(text)) { chatbot.state.expect = null; return chatRunIntent('HELP'); }
  const role = chatbotContext().role, expect = chatbot.state.expect, epoch = chatbot.epoch;
  let courses = courseCatalog;
  if (!courses?.length) { try { courses = await chatbotDataService.courses(); } catch { courses = []; } }
  if (epoch !== chatbot.epoch) return;  // New chat (or sign-out) while the course list was loading.
  const found = detectIntent(text, { role, courses, courseContext: Boolean(chatbotContext().course) });
  // An answer to the question just asked, unless the message is plainly a different question.
  const different = found.type === 'intent' && found.intent !== 'COURSE_DETAILS' && found.intent !== expect?.intent && found.intent !== 'EXPLAIN_TERM';
  if (expect?.type === 'term' && !different) return chatAnswer(() => chatbotResponseService.courseAction('explain', chatCtx({ text }), chatExtractTerm(text) || text));
  if (expect?.type === 'employee' && !different) return chatRunIntent(expect.intent || 'EMPLOYEE_TRAINING', { text, arg: chatExtractPerson(text) || text });
  if (expect?.type === 'course' && !different) {
    if (found.course) return chatRunIntent(expect.intent, { text, courseArg: found.course });
    return chatAnswer(async () => ({ ...(await chatAskCourse(expect.intent, `I couldn't find a course called “${text}”. Choose one of yours, or browse the catalogue.`)) }));
  }
  if (found.type === 'clarify') return chatAnswer(() => chatbotResponseService.clarify(found.choices, found.reason));
  if (found.type === 'unknown') return chatAnswer(() => chatbotResponseService.fallback());
  return chatRunIntent(found.intent, { text: chatNormalize(text), courseArg: found.course });
}

/** Carry out a button's action. Every button does something real: run an intent, open a page or course, or act on the open course. */
async function chatPerform(action, label) {
  if (!action || chatbot.typing) return;
  chatPush('user', label);
  chatbot.state.expect = null;
  if (action.kind === 'intent') return chatRunIntent(action.intent, { arg: action.arg });
  if (action.kind === 'course-action') return chatAnswer(() => chatbotResponseService.courseAction(action.action, chatCtx(), action.lesson));
  if (action.kind === 'nav') {
    if (!chatbotPermissions.page(action.page)) return chatAnswer(() => ({ text: 'That page is not available to your role.', options: [chatMenuOpt()] }));
    location.hash = action.page; render(); chatStepAside();
    return chatAnswer(() => ({ text: `Opened ${label.replace(/^(Open|View|See all|Take me there)\s*/i, '') || 'the page'}. Anything else?`, options: chatSuggestionOptions(chatbotContext().role, chatbotContext()).slice(0, 4) }));
  }
  if (action.kind === 'course') {
    try {
      if (currentCourseInfo.id !== action.id || !chatOnPage('course')) await loadCourse(action.id);
      if (action.lesson) {
        const lesson = currentCourseExtras?.courseLessons?.find(l => l.id === action.lesson);
        if (lesson?.locked) return chatAnswer(() => ({ text: `“${lesson.title}” is still locked. Finish the earlier lessons and checks first.`, options: [chatOpt('What to revise', { kind: 'course-action', action: 'revision' })] }));
        selectedLessonId = action.lesson; selectedCheckpointId = null;
      }
      if (action.set != null && typeof selectedSet !== 'undefined') { selectedSet = Number(action.set); selectedActivity = 'overview'; }
      location.hash = 'course'; render(); window.scrollTo?.(0, 0); chatStepAside();
      return chatAnswer(() => ({ text: `Opened “${currentCourseInfo.title}”. I can help with this course:`, options: CHAT_COURSE_ACTIONS.map(([a, l]) => chatOpt(l, { kind: 'course-action', action: a })) }));
    } catch (error) {
      return chatAnswer(() => ({ text: `I couldn't open that course: ${error.message}.`, options: [chatMenuOpt()], error: true }));
    }
  }
  if (action.kind === 'assign') {
    if (!chatbotPermissions.page('admin-courses')) return chatAnswer(() => ({ text: 'Assigning courses is done by HR and administrators in Manage Courses.', options: [chatMenuOpt()] }));
    if (action.courseId && typeof openAssignment === 'function') openAssignment(action.courseId);
    else { if (typeof closeCourseEditor === 'function') closeCourseEditor(); courseTab = 'assignments'; location.hash = 'admin-courses'; render(); }
    chatStepAside();
    return chatAnswer(() => ({ text: 'Opened Assign a Course. Choose the course, who it is for, and the deadline.', options: [chatMenuOpt()] }));
  }
  if (action.kind === 'create-course') {
    location.hash = 'admin-courses'; if (typeof startNewCourse === 'function') startNewCourse(); else render(); chatStepAside();
    return chatAnswer(() => ({ text: 'Opened the course wizard. Start with Course basics; you can save a draft at any step.', options: [chatMenuOpt()] }));
  }
}

/** On small screens the panel covers the page, so it gets out of the way after opening something. */
function chatStepAside() { if (window.matchMedia?.('(max-width: 640px)').matches) { chatbot.open = false; chatPaint(); } }

function chatNewConversation(greet = true) {
  chatbot.epoch++; chatbot.typing = false; chatbot.state = { messages: [], expect: null, nextId: 1 };
  conversationService.save(chatbot.state); chatPaint();
  if (greet) chatRunIntent('HELP');
}

/** Open the panel, optionally straight into a course action (used by the course page's assistant buttons). */
function chatbotOpen(courseAction) {
  if (!chatbotAvailable()) return;
  chatbot.open = true; chatbot.minimized = false; chatPaint();
  if (courseAction) { const label = (CHAT_COURSE_ACTIONS.find(([a]) => a === courseAction) || [, 'Help'])[1]; return chatPerform({ kind: 'course-action', action: courseAction }, label); }
  if (!chatbot.state.messages.length && !chatbot.typing) chatRunIntent('HELP');
  setTimeout(() => { if (window.matchMedia?.('(pointer: fine)').matches) chatbot.root?.querySelector('#chatbot-input')?.focus({ preventScroll: true }); }, 0);
}
function chatbotClose() { chatbot.open = false; chatPaint(); chatbot.root?.querySelector('.chatbot-launcher')?.focus(); }

/** Sign-out: forget every conversation kept in this browser session. */
function resetChatbot() { chatbot.epoch++; chatbot.open = false; chatbot.minimized = false; chatbot.typing = false; chatbot.userId = null; chatbot.state = { messages: [], expect: null, nextId: 1 }; conversationService.clearAll(); chatPaint(); }

// ---------------------------------------------------------------- rendering (pure HTML builders, then one paint)

const CHAT_BOT_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="7" width="16" height="12" rx="4"/><path d="M12 3v4M8.5 12.5h.01M15.5 12.5h.01M9 16h6"/></svg>';
const CHAT_ICONS = {
  chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>', close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg>', restart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11a8 8 0 1 1 2.3 5.7M4 18v-6h6"/></svg>',
  clear: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/></svg>', send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12 20 4l-6 16-3-7z"/></svg>',
};
const chatInitials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('') || '?';

/** Register an action for a button and return its data attribute. */
function chatActionAttr(action, label) { chatbot.actions.push({ action, label }); return `data-chat-action="${chatbot.actions.length - 1}"`; }

function chatItemsHTML(items) {
  if (!items?.length) return '';
  return `<ul class="chatbot-items">${items.map(item => `<li><div class="chatbot-item-text"><strong>${esc(item.title)}</strong>${item.meta ? `<small>${esc(item.meta)}</small>` : ''}</div><div class="chatbot-item-side">${item.tag ? `<span class="tag ${esc(item.tone || '')}">${esc(String(item.tag).toUpperCase())}</span>` : ''}${item.action ? `<button type="button" class="chatbot-item-btn" ${chatActionAttr(item.action, `${item.actionLabel || 'Open'}: ${item.title}`)}>${esc(item.actionLabel || 'Open')}</button>` : ''}</div></li>`).join('')}</ul>`;
}
function chatOptionsHTML(options) {
  const list = (options || []).filter(Boolean);
  return list.length ? `<div class="chatbot-options" role="group" aria-label="Suggested replies">${list.map(o => `<button type="button" class="chatbot-chip" ${chatActionAttr(o.action, o.label)}>${esc(o.label)}</button>`).join('')}</div>` : '';
}
function chatMessageHTML(m, last) {
  if (m.from === 'user') return `<div class="chatbot-msg user"><p class="chatbot-bubble">${esc(m.text)}</p><span class="chatbot-avatar user" aria-hidden="true">${esc(chatInitials(currentUser?.name))}</span></div>`;
  return `<div class="chatbot-msg bot${m.error ? ' error' : ''}"><span class="chatbot-avatar bot" aria-hidden="true">${CHAT_BOT_ICON}</span><div class="chatbot-msg-body"><p class="chatbot-bubble">${esc(m.text)}</p>${chatItemsHTML(m.items)}${last ? `${m.more ? chatOptionsHTML([m.more]) : ''}${chatOptionsHTML(m.options)}` : ''}</div></div>`;
}
/** The message log: messages, typing indicator, or the empty state with suggested questions. */
function chatLogHTML() {
  chatbot.actions = [];
  const messages = chatbot.state.messages, lastBot = [...messages].reverse().find(m => m.from === 'bot');
  if (!messages.length && !chatbot.typing) {
    const ctx = chatbotContext();
    return `<div class="chatbot-empty"><span class="chatbot-avatar bot large" aria-hidden="true">${CHAT_BOT_ICON}</span><h3>How can I help?</h3><p>Ask about your courses, deadlines, assessments and certificates. I answer from the LMS's own records.</p>${chatOptionsHTML(chatSuggestionOptions(ctx.role, ctx))}</div>`;
  }
  return messages.map(m => chatMessageHTML(m, m === lastBot && !chatbot.typing)).join('')
    + (chatbot.typing ? `<div class="chatbot-msg bot" aria-label="The assistant is typing"><span class="chatbot-avatar bot" aria-hidden="true">${CHAT_BOT_ICON}</span><p class="chatbot-bubble chatbot-typing"><span></span><span></span><span></span></p></div>` : '');
}
function chatShellHTML() {
  return `<button type="button" class="chatbot-launcher" aria-label="Open the learning assistant" aria-expanded="false">${CHAT_ICONS.chat}</button>
  <section class="chatbot-panel" role="dialog" aria-label="ShimentoX learning assistant" hidden>
    <header class="chatbot-header"><span class="chatbot-avatar bot head" aria-hidden="true">${CHAT_BOT_ICON}</span><button type="button" class="chatbot-title" data-chat-ui="restore"><strong>Learning Assistant</strong><small class="chatbot-subtitle"></small></button>
      <div class="chatbot-tools"><button type="button" data-chat-ui="new" title="New chat" aria-label="New chat">${CHAT_ICONS.restart}</button><button type="button" data-chat-ui="clear" title="Clear chat" aria-label="Clear chat">${CHAT_ICONS.clear}</button><button type="button" data-chat-ui="minimize" title="Minimise" aria-label="Minimise">${CHAT_ICONS.minus}</button><button type="button" data-chat-ui="close" title="Close" aria-label="Close">${CHAT_ICONS.close}</button></div></header>
    <div class="chatbot-log" role="log" aria-live="polite"></div>
    <form class="chatbot-form" autocomplete="off"><label class="visually-hidden" for="chatbot-input">Message the assistant</label><input id="chatbot-input" maxlength="${CHAT_INPUT_LIMIT}" placeholder='Try "my pending courses" or "deadlines"'><button type="submit" class="chatbot-send" aria-label="Send">${CHAT_ICONS.send}</button></form>
  </section>`;
}

function chatEnsureRoot() {
  if (chatbot.root || typeof document.createElement !== 'function' || !document.body?.appendChild) return chatbot.root;
  const root = document.createElement('div');
  root.id = 'chatbot-root'; root.className = 'chatbot'; root.innerHTML = chatShellHTML();
  document.body.appendChild(root);
  root.addEventListener('click', event => {
    const target = event.target.closest?.('[data-chat-action],[data-chat-ui],.chatbot-launcher');
    if (!target || target.disabled) return;
    if (target.classList.contains('chatbot-launcher')) return chatbot.open && !chatbot.minimized ? chatbotClose() : chatbotOpen();
    const ui = target.dataset.chatUi;
    if (ui === 'close') return chatbotClose();
    if (ui === 'minimize') { chatbot.minimized = true; return chatPaint(); }
    if (ui === 'restore') { chatbot.minimized = false; return chatPaint(); }
    if (ui === 'new') return chatNewConversation(true);
    if (ui === 'clear') return chatNewConversation(false);
    const entry = chatbot.actions[Number(target.dataset.chatAction)];
    if (entry) chatPerform(entry.action, entry.label);
  });
  root.addEventListener('submit', event => {
    event.preventDefault();
    const input = root.querySelector('#chatbot-input'), text = input.value;
    if (!text.trim() || chatbot.typing) return;
    input.value = ''; chatHandleText(text);
  });
  root.addEventListener('keydown', event => { if (event.key === 'Escape' && chatbot.open) { event.stopPropagation(); chatbotClose(); } });
  chatbot.root = root;
  return root;
}

function chatPaint() {
  const root = chatbot.root;
  if (!root) return;
  const available = chatbotAvailable(), panel = root.querySelector('.chatbot-panel'), launcher = root.querySelector('.chatbot-launcher');
  root.hidden = !available;
  if (!available) return;
  const visible = chatbot.open;
  panel.hidden = !visible;
  panel.classList.toggle('minimized', visible && chatbot.minimized);
  launcher.hidden = visible;  // A minimised panel stays as a header bar; clicking its title restores it.
  launcher.setAttribute('aria-expanded', String(visible));
  const ctx = chatbotContext();
  root.querySelector('.chatbot-subtitle').textContent = ctx.course ? `On: ${ctx.course.title}` : 'Answers from your LMS data';
  if (!visible || chatbot.minimized) return;
  const log = root.querySelector('.chatbot-log');
  log.innerHTML = chatLogHTML();
  root.querySelector('.chatbot-send').disabled = chatbot.typing;
  log.scrollTop = log.scrollHeight;
}

/** Called after every portal render: follow sign-in, sign-out, exams and course pages. */
function chatbotSync() {
  if (!chatbotAvailable()) {
    // Signed out, a password change pending, or an exam in progress: the panel closes and the launcher hides.
    if (!currentUser && chatbot.userId) resetChatbot();
    chatbot.open = false;
  } else if (chatbot.userId !== currentUser.id) {
    // A different person signed in (or the page was reloaded): load their conversation for this browser session.
    chatbot.epoch++; chatbot.userId = currentUser.id; chatbot.typing = false; chatbot.state = conversationService.load();
  }
  chatEnsureRoot();
  chatPaint();
}

// Course page: the assistant buttons open this panel with the course already in context.
document.addEventListener('click', event => {
  const button = event.target.closest?.('[data-chatbot-open]');
  if (!button) return;
  event.preventDefault();
  chatbotOpen(button.dataset.chatbotOpen || null);
});

// Follow the portal's own renders (as learning.js does) without changing them.
const chatbotBaseRender = render;
render = function() { chatbotBaseRender(); chatbotSync(); };
