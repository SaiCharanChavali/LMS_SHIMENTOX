// The session cookie is HttpOnly; authentication secrets never enter browser storage.
let currentUser = null;
let firstAdminSetup=false;
let csrfToken = '';
let courseCatalog=[];
let currentCourseInfo={id:null,title:'',category:'Development'};
let portalReady = false;
let operationQueue = Promise.resolve();
// Must match API_VERSION in backend/src/server.py. A mismatch means the server process predates these files.
const EXPECTED_API_VERSION = 9;
let serverOutdated = false;

async function api(path, body, options = {}) {
  let response;
  try {
    response = await fetch('/api/' + path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Portal-Request': '1', 'X-CSRF-Token': csrfToken },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }), keepalive: Boolean(options.keepalive)
    });
  } catch { throw new Error('Could not reach the server. Check your connection and try again.'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('Start the portal with npm start so the login server is available.'); }
  if (!response.ok) {
    // Technical details go to the developer console only; the page shows the server's user-facing message.
    if (typeof console !== 'undefined') console.warn(`[ShimentoX API] ${body === undefined ? 'GET' : 'POST'} /api/${path} -> ${response.status}`, data.error || '');
    if (response.status === 401 && !path.startsWith('auth/')) {
      currentUser = null; csrfToken = ''; activeExam = null; render();
    }
    const error = new Error(data.error || 'The request could not be completed.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function queueOperation(task) {
  const next = operationQueue.then(task);
  operationQueue = next.catch(() => {});
  return next;
}

function applyLearning(incoming) {
  if (learning.run.id === incoming.run.id) {
    for (const [id, saved] of Object.entries(incoming.run.videos)) {
      const local = learning.run.videos[id];
      if (local) { Object.assign(local, saved, { watched: Math.max(local.watched || 0, saved.watched) }); incoming.run.videos[id] = local; }
    }
  }
  learning = incoming;
  state.completed = lessons.map((_, i) => i).filter(videoDone);
  const catalogItem=courseCatalog.find(c=>c.id===(incoming.run.courseId||currentCourseInfo.id));
  if(catalogItem&&incoming.run.format==='lessons'){catalogItem.enrolled=true;catalogItem.progress=courseProgress();}
  else if(catalogItem){catalogItem.enrolled=true;catalogItem.progress=Math.round((Object.values(incoming.run.videos).filter(v=>v.complete).length+Object.keys(incoming.run.exercises).length+incoming.run.attempts.filter(list=>list.some(a=>a.status==='passed')).length)/15*100);}
}

function learningRequest(action, data = {}, options = {}) {
  const userId = currentUser?.id, runId = learning.run.id;
  return queueOperation(async () => {
    if (!currentUser || currentUser.id !== userId) throw new Error('Please sign in again.');
    const result = await api('learning/' + action, { runId, ...data }, options);
    if (currentUser?.id === userId) applyLearning(result.learning);
    return result;
  });
}

async function loadCandidate() {
  if(typeof stopPythonExecution==='function'){stopPythonExecution();pythonPracticeState.clear();lessonKnowledgeState.clear();}
  state.name=currentUser.name; activeExam=null; resetDevelopment();
  if(currentUser.mustChangePassword)return;
  courseCatalog=(await api('courses')).courses;
  refreshNotifications();
  if(currentUser.role!=='employee')await loadAdminState();
  if(currentUser.role==='admin'){learning=emptyLearning();courseSets=[];lessons=[];return;}
  // Resume the most recently active enrolled course; opening a course is the employee's choice, so none is auto-enrolled here.
  let resume;
  for(const course of courseCatalog)if(course.enrolled&&(!resume||(course.lastActivity||'').localeCompare(resume.lastActivity||'')>0))resume=course;
  if(resume)await loadCourse(resume.id,false);
  else {learning=emptyLearning();courseSets=[];lessons=[];currentCourseInfo={id:null,title:''};learning.certificates=(await api('certificates')).certificates;}
}
async function loadCourse(id,navigate=true) {
  if(typeof stopPythonExecution==='function'){stopPythonExecution();pythonPracticeState.clear();lessonKnowledgeState.clear();}
  if(activeExam)await finishExam('terminated','You changed courses during the examination.');
  await operationQueue;
  const enrolled=await api('learning/enroll',{courseId:id});
  applyLearning(enrolled.learning);
  const data=await api('learning?courseId='+encodeURIComponent(id));
  courseSets=data.course;lessons=data.lessons;currentCourseInfo=data.courseInfo;applyLearning(data.learning);
  currentCourseExtras={resources:data.resources||[],assessments:data.assessments||[],requiredAssessmentId:data.requiredAssessmentId||null,courseLessons:data.courseLessons||[]};assistantAnswer=null;selectedLessonId=null;
  const resumed=await api('learning/resume',{runId:learning.run.id});applyLearning(resumed.learning);
  selectedSet=0;selectedActivity='overview';selectedCheckpointId=null;exerciseFeedback=null;examNotice='';
  if(navigate){location.hash='course';render();}
}

async function initializePortal() {
  document.getElementById('app').innerHTML = '<div class="portal-loading" role="status">Loading your learning space…</div>';
  try {
    const session = await api('session');
    currentUser = session.user; csrfToken = session.csrfToken || '';
    serverOutdated = session.apiVersion !== EXPECTED_API_VERSION;
    if (serverOutdated && typeof console !== 'undefined') console.warn(`[ShimentoX API] Server reports API version ${session.apiVersion ?? 'none'}; this page expects ${EXPECTED_API_VERSION}. Restart the server to load the current backend.`);
    firstAdminSetup=Boolean(session.setupRequired&&session.setupAllowed);
    if (currentUser&&!firstAdminSetup) await loadCandidate();
    portalReady = true;
    render();
  } catch (error) {
    currentUser = null; portalReady = true;
    document.getElementById('app').innerHTML = `<div class="portal-loading"><h1>Let’s get you connected.</h1><p>${esc(error.message)}</p><p>Run <code>npm start</code> from the shimentox-lms folder, then open http://localhost:5173.</p><button class="btn" id="retry-connection">Try again</button></div>`;
    document.getElementById('retry-connection').onclick = initializePortal;
  }
}

const authIcons={mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',lock:'<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15" r="1"/>',eye:'<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',eyeOff:'<path d="M3 3l18 18M10.6 5.1A10.4 10.4 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.2M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.8 9.8 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'};
const authIcon=name=>`<svg class="auth-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${authIcons[name]}</svg>`;
const signInLabel=()=>`Sign In ${icon('arrow')}`;
function authPage() {
  return `<div class="login"><section class="login-visual">${brand()}<div><div class="eyebrow" style="color:#9bc6af">LEARN TODAY. LEAD TOMORROW.</div><h1>Give your curiosity<br>something to build.</h1><p>Explore an idea. Practice a skill.<br>See what you can create at ShimentoX.</p><div class="login-code-gallery" role="img" aria-label="Three illustrated coding windows: a Python editor, a terminal, and a learning project"><div class="login-code-card code-editor"><div class="code-card-bar"><span class="code-card-dots">&#9679; &#9679; &#9679;</span><span>possibilities.py</span></div><div class="code-card-content"><span class="code-note"># Start with a little curiosity</span><br><span class="code-keyword">def</span> build_something_new():<br>&nbsp; idea = <span class="code-string">"what if?"</span><br>&nbsp; <span class="code-keyword">return</span> learn(idea)</div></div><div class="login-code-card code-terminal"><div class="code-card-bar"><span class="code-card-dots">&#9679; &#9679; &#9679;</span><span>terminal</span></div><div class="code-card-content"><span class="code-string">$</span> python possibilities.py<br><span class="code-note">Discovering new skills...</span><br><span class="code-string">&#10003; A little more confident.</span><br><span class="code-terminal-prompt">&gt; ready_for_whats_next</span><span class="code-cursor">_</span></div></div><div class="login-code-card code-project"><div class="code-card-bar"><span class="code-card-dots">&#9679; &#9679; &#9679;</span><span>you.next</span></div><div class="code-card-content"><span class="code-keyword">const</span> nextChapter = {<br>&nbsp; curiosity: <span class="code-string">true</span>,<br>&nbsp; possibilities: <span class="code-string">Infinity</span><br>};</div></div><span class="code-gallery-spark" aria-hidden="true">&#10022;</span></div></div><small style="color:#8eafa0;font-size:10px">A little progress. Every single day.</small></section><section class="login-form"><div class="form-inner"><div class="eyebrow">WELCOME TO YOUR LEARNING SPACE</div><h1>Good to have you here.</h1><p>Sign in to keep moving forward.</p><div id="auth-error" class="notice hidden" role="alert"></div><form id="login-form" novalidate><label for="email">Assigned email</label><input type="email" id="email" name="email" autocomplete="username" placeholder="you@shimentox.com" maxlength="254" required aria-describedby="auth-error"><label for="password">Password</label><div class="password-wrap"><input type="password" id="password" name="password" autocomplete="current-password" placeholder="Enter your password" maxlength="128" required><button type="button" class="auth-reveal" id="show-password" aria-label="Show password" aria-pressed="false" aria-controls="password">${authIcon('eye')}</button></div><div class="form-options"><label><input type="checkbox" id="remember"> Keep me signed in</label><button type="button" class="auth-link" id="forgot-password" aria-expanded="false" aria-controls="forgot-help">Forgot password?</button></div><div id="forgot-help" class="auth-help hidden" role="status">Ask your ShimentoX administrator for a new temporary password. You will choose your own password at your next sign-in.</div><button class="btn auth-submit" id="auth-submit" type="submit">${signInLabel()}</button></form><p class="login-foot">Your growth, supported by ShimentoX.<br>Need an account? Contact your administrator.</p></div></section></div>`;
}

function initialAdminPage(){
  return `<div class="password-setup"><div class="panel form-inner">${brand()}<div class="eyebrow" style="margin-top:28px">WELCOME TO SHIMENTO X</div><h1>Set up your admin account.</h1><p>Create the first administrator here. After setup, use the Users page in your dashboard to add everyone else.</p><div id="auth-error" class="notice hidden" role="alert"></div><form id="admin-setup-form"><label for="setup-name">Full name</label><input id="setup-name" type="text" autocomplete="name" minlength="2" maxlength="100" required><label for="setup-email">Admin email</label><input id="setup-email" type="email" autocomplete="username" maxlength="254" required><label for="setup-password">Password</label><input id="setup-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required><label for="setup-confirm">Confirm password</label><input id="setup-confirm" type="password" autocomplete="new-password" minlength="8" maxlength="128" required><p class="muted">If this email already has an account, enter its current password. Existing progress is preserved.</p><button class="btn" id="setup-submit" type="submit">Create admin and open dashboard</button></form></div></div>`;
}
function bindInitialAdmin(){
  document.getElementById('admin-setup-form').onsubmit=async event=>{
    event.preventDefault();const password=document.getElementById('setup-password').value;
    if(password!==document.getElementById('setup-confirm').value)return authError('Your passwords do not match.');
    const button=document.getElementById('setup-submit');if(button.disabled)return;button.disabled=true;
    try{const result=await api('setup/admin',{name:document.getElementById('setup-name').value,email:document.getElementById('setup-email').value,password});currentUser=result.user;csrfToken=result.csrfToken;firstAdminSetup=false;await loadCandidate();location.hash='dashboard';render();}
    catch(error){authError(error.message);}finally{button.disabled=false;}
  };
}
function authError(message) {const box=document.getElementById('auth-error');if(box){box.textContent=message;box.classList.remove('hidden');}}
function bindAuthForm() {
  const reveal=document.getElementById('show-password');
  reveal.onclick=()=>{const input=document.getElementById('password'),shown=input.type==='password';input.type=shown?'text':'password';reveal.innerHTML=authIcon(shown?'eyeOff':'eye');reveal.setAttribute?.('aria-label',shown?'Hide password':'Show password');reveal.setAttribute?.('aria-pressed',String(shown));};
  const forgot=document.getElementById('forgot-password'),help=document.getElementById('forgot-help');
  if(forgot&&help)forgot.onclick=()=>{const open=help.classList.contains?.('hidden')??true;help.classList.toggle('hidden',!open);forgot.setAttribute?.('aria-expanded',String(open));};
  document.getElementById('login-form').onsubmit=async event=>{
    event.preventDefault();const button=document.getElementById('auth-submit');if(button.disabled)return;
    const email=document.getElementById('email').value.trim(),password=document.getElementById('password').value;
    // Client checks give quick feedback only; the server still validates and authenticates every request.
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))return authError('Enter a valid email address, for example you@shimentox.com.');
    if(!password)return authError('Enter your password.');
    document.getElementById('auth-error').classList.add('hidden');
    button.disabled=true;button.setAttribute?.('aria-busy','true');button.innerHTML='<span class="auth-spinner" aria-hidden="true"></span>Signing in…';
    try {
      const session=await api('auth/login',{email,password,remember:document.getElementById('remember').checked});
      currentUser=session.user;csrfToken=session.csrfToken;await loadCandidate();location.hash=homePage();render();
    }catch(error){authError(error.message);}finally{button.disabled=false;button.removeAttribute?.('aria-busy');button.innerHTML=signInLabel();}
  };
}
function passwordSetupPage() {
  return `<div class="password-setup"><div class="panel form-inner">${brand()}<div class="eyebrow" style="margin-top:28px">FIRST SIGN-IN</div><h1>Make your account yours.</h1><p>Hello ${esc(currentUser.name)}. Replace your administrator-provided temporary password before accessing the portal.</p><div id="auth-error" class="notice hidden" role="alert"></div><form id="first-password-form"><label for="temporary-password">Temporary password</label><input id="temporary-password" type="password" autocomplete="current-password" required maxlength="128"><label for="first-new-password">New password</label><input id="first-new-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required><label for="first-confirm-password">Confirm new password</label><input id="first-confirm-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required><p class="muted">At least 8 characters. Choose a different password from your temporary one.</p><button class="btn" type="submit" id="first-password-submit">Save password and continue</button></form><button class="auth-link" id="logout-button" style="margin-top:20px">Sign out</button></div></div>`;
}
function bindPasswordSetup() {
  document.getElementById('logout-button').onclick=logoutPortal;
  document.getElementById('first-password-form').onsubmit=async event=>{
    event.preventDefault();const password=document.getElementById('first-new-password').value;
    if(password!==document.getElementById('first-confirm-password').value)return authError('Your new passwords do not match.');
    const button=document.getElementById('first-password-submit');button.disabled=true;
    try {const result=await api('auth/password',{currentPassword:document.getElementById('temporary-password').value,password});currentUser=result.user;await loadCandidate();location.hash=homePage();render();}
    catch(error){authError(error.message);}finally{button.disabled=false;}
  };
}

async function logoutPortal() {
  const button = document.getElementById('logout-button'); if (button) button.disabled = true;
  try {
    if (activeExam) await finishExam('terminated', 'You signed out during the examination.');
    await operationQueue;
    await api('auth/logout', {});
    if(typeof stopPythonExecution==='function'){stopPythonExecution();pythonPracticeState.clear();lessonKnowledgeState.clear();}
    currentUser = null; csrfToken = ''; activeExam = null; state.name = ''; state.completed = [];
    adminState={stats:{},candidates:[],courses:[],events:[]};provisionedCredentials=null;resetCandidate=null;recordPreview=null;editingCourse=null;adminMessage='';resetDevelopment();currentCourseExtras=null;
    learning = emptyLearning(); courseSets = []; courseCatalog=[];currentCourseInfo={id:null,title:''}; location.hash = 'login'; render();
  } catch (error) { toast(error.message); if (button) button.disabled = false; }
}

function accountPage() { const profile=isLearner()?loadData('me-dash','me/dashboard').data?.profile:null; return `<div class="intro"><div><h1>My profile</h1><p>Your details and learning records, in one place.</p></div></div><div class="columns"><section class="panel account-details"><span class="tag">${esc((ROLE_LABELS[currentUser.role]||'Employee').toUpperCase())} PROFILE</span><h2>${esc(currentUser.name)}</h2><p>${esc(currentUser.email)}</p>${profile?`<p>${esc([profile.job_title||profile.job_role,profile.department].filter(Boolean).join(' · ')||'Department and job role not set')}${profile.manager?` · Manager: ${esc(profile.manager)}`:''}</p>`:''}${isLearner()?'<p><a class="auth-link" href="#history">View learning history and development records →</a></p>':''}<p>Joined ${esc(new Date(currentUser.createdAt).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }))}</p><p>Course run ${learning.run.runNumber} · ${learning.certificates.length} earned certificate${learning.certificates.length === 1 ? '' : 's'}</p><button class="btn secondary" id="download-records">Download my learning records</button><p class="muted">Includes previous course runs, video progress, all exercise submissions, exams, certificates, and account activity.</p></section><section class="panel form-inner account-password"><h3>Change password</h3><form id="password-form"><label for="current-password">Current password</label><input type="password" id="current-password" autocomplete="current-password" required maxlength="128"><label for="new-password">New password</label><input type="password" id="new-password" autocomplete="new-password" minlength="8" maxlength="128" required><label for="repeat-password">Confirm new password</label><input type="password" id="repeat-password" autocomplete="new-password" minlength="8" maxlength="128" required><button class="btn" type="submit" style="margin-top:20px">Update password</button><p id="password-status" role="status"></p></form></section></div>`; }

function bindAccount() {
  document.querySelectorAll('[data-open-course]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await loadCourse(button.dataset.openCourse);}catch(error){toast(error.message);button.disabled=false;}});
  const logout = document.getElementById('logout-button'); if (logout) logout.onclick = logoutPortal;
  const download = document.getElementById('download-records');
  if (download) download.onclick = async () => {
    download.disabled = true;
    try { const records = await api('records'); const url = URL.createObjectURL(new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'shimentox-learning-records.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    catch (error) { toast(error.message); } finally { download.disabled = false; }
  };
  const form = document.getElementById('password-form'); if (form) form.onsubmit = async event => {
    event.preventDefault(); const status = document.getElementById('password-status'), button = form.querySelector('button');
    const password = document.getElementById('new-password').value;
    if (password !== document.getElementById('repeat-password').value) { status.textContent = 'Your new passwords do not match.'; return; }
    button.disabled = true;
    try { const changed=await api('auth/password', { currentPassword: document.getElementById('current-password').value, password }); currentUser=changed.user; form.reset(); status.textContent = 'Password updated. Your other sessions have been signed out.'; }
    catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  };
}
