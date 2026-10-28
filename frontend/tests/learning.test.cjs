// UI-to-API contract checks. Real HTTP/SQLite rules are tested in backend/tests.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const curriculum = JSON.parse(fs.readFileSync(__dirname + '/../../backend/data/python-course.json', 'utf8'));
const copy = value => JSON.parse(JSON.stringify(value));
const fixtureLessons=JSON.parse(fs.readFileSync(__dirname+'/../../backend/data/python-lessons.json','utf8'));
const courseInfo={id:'python-programming',title:'PYTHON PROGRAMMING',category:'Development',description:'Python basics',status:'published',progress:0,enrolled:true,completed:false,difficulty:'beginner',durationMinutes:90,skills:[{id:'s1',name:'Python',level:1}],passPercent:75,maxAttempts:3,assignment:{mandatory:true,dueDate:'2099-01-31',assignedBy:'HR Partner'}};
const employeeDashboard={profile:{name:'Sai Charan',email:'sai@shimentox.com',role:'employee',department:'Engineering',job_role:'Data Analyst',manager:'Line Manager',job_title:''},stats:{assigned:1,inProgress:0,completed:0,overdue:0,certificates:0,skillGaps:1},assigned:[{...courseInfo,status:'not_started'}],continue:[],recommendations:[{id:'sql',title:'SQL Foundations',description:'Query data.',difficulty:'beginner',durationMinutes:60,category:'Data Analytics',skills:['SQL'],reasons:['Closes your SQL gap (Not assessed now, Intermediate required for your role).']}],paths:[{id:'p1',title:'Generative AI Path',progress:50,completed:1,total:2,dueDate:null}],skills:[],sessions:[],pendingAssessments:[],goals:[],history:[]};
const orgDashboardData={scope:'organisation',kpis:{totalEmployees:12,activeLearners:7,publishedCourses:3,completionRate:42,enrollments:19,completions:8,certificatesEarned:8,trainingHours:15.5,pendingMandatory:4,employeesWithPlans:5},progress:{activelyLearning:6,completedAssigned:3,notStarted:2,overdue:1,overdueEmployees:[{id:'e1',name:'Late Learner',department:'Sales',overdue:1}]},departments:[{department:'Engineering',employees:5,participants:4,participationRate:80,completionRate:50,completionsInPeriod:3,averageScore:82,trainingHours:9.2}],period:{from:null,to:null},recent:[{type:'completion',at:'2026-10-20T10:00:00Z',text:'Asha completed SQL Foundations and earned a certificate'}],upcoming:{sessions:[],deadlines:[{courseId:'c1',course:'Security Awareness',dueDate:'2099-01-01',pending:4,overdue:false}],pendingAssessments:[]}};
const safeCourse = copy(curriculum);
for (const set of safeCourse) { set.exam = set.exam.map(q => q.slice(0, 2)); for (const ex of set.exercises) ex.questions = ex.questions.map(q => q.slice(0, 2)); }
const empty = () => ({ version: 3, run: { id: 'run-one', runNumber: 1, videos: {}, exercises: {}, attempts: [[], [], []], completedAt: null }, certificates: [] });

async function main() {
  const events = {}, docEvents = {}, elements = {}, requests = [];
  const server = { user: null, learning: empty(), failLogin: false,setupRequired:false };
  const classes = () => ({ add() {}, remove() {}, toggle() {} });
  const app = { innerHTML: '' }, toast = { textContent: '', classList: classes() };
  function element(id) {
    if (id === 'app') return app;
    if (id === 'toast') return toast;
    if (!app.innerHTML.includes(`id="${id}"`)) return null;
    return elements[id] ||= { innerHTML: '', textContent: '', value: '', checked: false, disabled: false, dataset: {}, classList: classes(), handlers: {}, addEventListener(n, fn) { this.handlers[n] = fn; }, querySelector() { return element(id + '-submit') || (elements[id + '-submit'] ||= { disabled: false }); }, reset() {} };
  }
  async function fetch(url, options) {
    const path = url.replace('/api/', ''), data = options.body ? JSON.parse(options.body) : {};
    requests.push({ path, data, options });
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers['X-Portal-Request'], '1');
    let status = 200, result;
    if (path === 'session') result = { user: server.user, csrfToken: server.user ? 'csrf-test' : null,setupRequired:server.setupRequired,setupAllowed:true,apiVersion:server.apiVersion===undefined?9:server.apiVersion };
    else if(path==='setup/admin'){server.user={id:'owner',name:data.name,email:data.email,role:'admin',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z'};server.setupRequired=false;result={user:server.user,csrfToken:'csrf-test'};}
    else if (path === 'auth/login') {
      if (server.failLogin) { status = 401; result = { error: 'Email or password is incorrect.' }; }
      else { server.user = { id: 'candidate-one', name: data.name || 'Sai Charan', email: data.email, createdAt: '2026-10-22T00:00:00Z',role:'employee',mustChangePassword:true }; result = { user: server.user, csrfToken: 'csrf-test' }; }
    } else if(path==='auth/password'){server.user.mustChangePassword=false;result={ok:true,user:server.user};} else if (path === 'auth/logout') { server.user = null; result = { ok: true }; }
    else if(path==='courses')result={courses:[courseInfo]};
    else if(path==='learning/enroll')result={learning:server.learning};
    else if (path.startsWith('learning?')) result = { course: safeCourse, learning: server.learning,lessons:fixtureLessons,courseInfo,resources:[{id:'r1',title:'Handbook',kind:'document',url:'api/materials/x',moduleIndex:null}],assessments:[],requiredAssessmentId:null,courseLessons:server.courseLessons||[] };
    else if(path==='me/notifications')result={notifications:[{id:1,kind:'assignment',title:'Mandatory training assigned: PYTHON PROGRAMMING',body:'Complete by 2099-01-31.',link:'courses',createdAt:'2026-10-22T00:00:00Z',readAt:null}],unread:1};
    else if(path==='me/dashboard')result=employeeDashboard;
    else if(path==='me/assistant')result={enabled:false,reason:'The AI learning assistant has not been enabled by your administrator.'};
    else if(path.startsWith('manage/dashboard'))result=orgDashboardData;
    else if(path==='manage/org')result={departments:[{id:'d1',name:'Engineering',employees:5}],jobRoles:[],categories:['Technical Skills'],skills:[{id:'s1',name:'Python'}],courses:[{id:'python-programming',title:'PYTHON PROGRAMMING',status:'published'}],trainers:[],managers:[],levels:[]};
    else if(path==='manage/people')result={people:[]};
    else if(path==='manage/assessments')result={assessments:[]};
    else if(path.startsWith('manage/reports'))result={type:'enrollments',title:'Course enrollment and completion',columns:[{key:'employee',label:'Employee'},{key:'status',label:'Status'}],rows:[{employee:'=HYPERLINK("x")',status:'Completed'}],summary:{Enrollments:1},total:1,page:1,pages:1};
    else if(path==='admin/overview')result={stats:{candidates:1,courses:1,certificates:0,exams:0}};
    else if(path==='admin/candidates')result=options.body?{candidate:{id:'new-account'}}:{candidates:[server.user]};
    else if(path==='admin/courses')result={courses:[{...courseInfo,content:{sets:curriculum,lessons:fixtureLessons}}]};
    else if(path==='admin/audit')result={events:[]};
    else if(path==='manage/import/preview')result={token:'preview-token',duplicate:null,preview:{platform:{id:'microsoft-learn',name:'Microsoft Learn'},strategy:'Microsoft Learn module (units)',kind:'course',sourceUrl:data.url,requestedUrl:data.url,title:'Organize data',description:'Lists and dictionaries.',license:null,policy:{fullContent:true,note:''},notes:[],
      items:[{type:'module',title:'Collections',url:data.url,lessons:[{title:'Store data with lists',url:data.url+'2-lists',status:'imported',reason:'',description:'',content:'## Creating a list\n\n- one\n  - nested\n\n```python\nx = [1]\n```',sections:[{level:1,title:'Creating a list'}],words:400,codeBlocks:1,tables:0,figures:0},
        {title:'Module assessment',url:data.url+'3-check',status:'inaccessible',reason:'No readable lesson text was found on this page.',description:'',content:'',sections:[],words:0,codeBlocks:0,tables:0,figures:0}]}],
      stats:{modules:1,lessons:2,imported:1,inaccessible:1,reference:0}}};
    else if (path === 'learning/resume') result = { learning: server.learning };
    else if(path==='learning/checkpoint-start'){
      const c=server.learning.run.checkpoints.find(c=>c.id===data.checkpointId),attempt={id:'cp-'+(c.attempts.length+1),status:'in-progress',attemptNumber:c.attempts.length+1,deadline:Date.now()+600000,startedAt:new Date().toISOString()};
      c.attempts.push(attempt);result={learning:server.learning,attempt,questions:server.checkpointQuestions};
    }
    else if(path==='learning/checkpoint-finish'){
      const c=server.learning.run.checkpoints[0],attempt=c.attempts.find(a=>a.id===data.attemptId);
      Object.assign(attempt,data.terminate?{status:'terminated',reason:data.reason}:{status:'passed',score:8,total:8,percent:100});
      c.passed=attempt.status==='passed';if(c.passed)server.courseLessons.slice(3,6).forEach(l=>l.locked=false);
      result={learning:server.learning,attempt};
    }
    else if (path === 'learning/video') { server.learning.run.videos[data.videoIndex] = { watched: data.watched, complete: data.complete }; result = { learning: server.learning }; }
    else if (path === 'learning/exercise') {
      const questions = curriculum[data.setIndex].exercises[data.exerciseIndex].questions;
      const details = questions.map((q, i) => ({ correct: data.answers[i] === q[2], explanation: q[3] }));
      const score = details.filter(d => d.correct).length;
      if (score === 2) server.learning.run.exercises[`${data.setIndex}-${data.exerciseIndex}`] = true;
      result = { learning: server.learning, feedback: { score, answers: data.answers, details } };
    } else if (path === 'learning/exam-start') {
      const attempt = { id: 'attempt-one', status: 'in-progress', startedAt: new Date().toISOString(), deadline: Date.now() + 600000 };
      server.learning.run.attempts[data.setIndex].push(attempt); result = { learning: server.learning, attempt };
    } else if (path === 'learning/exam-finish') {
      const attempt = server.learning.run.attempts.flat().find(a => a.id === data.attemptId);
      attempt.status = 'terminated'; attempt.reason = data.reason; result = { learning: server.learning, attempt };
    } else if (path === 'learning/restart') { server.learning = empty(); server.learning.run.id = 'run-two'; server.learning.run.runNumber = 2; result = { learning: server.learning }; }
    else throw Error('Unexpected API request: ' + path);
    return { ok: status < 400, status, json: async () => copy(result) };
  }
  const context = {
    document: { getElementById: element, querySelectorAll: () => [], body: { classList: classes() }, hidden: false, addEventListener: (n, fn) => (docEvents[n] ||= []).push(fn), title: '' },
    location: { hash: '#dashboard' }, window: { addEventListener: (n, fn) => (events[n] ||= []).push(fn), scrollTo() {}, print() {} },
    fetch, Intl, Date, URL, performance: { time: 0, now() { return this.time; } }, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    FormData: class { constructor(form) { this.form = form; } get(key) { return this.form.answers[key] ?? null; } }
  };
  vm.createContext(context);
  const run = code => vm.runInContext(code, context);
  for (const file of ['auth.js', 'app.js', 'admin.js', 'development.js', 'course-import.js', 'python-practice.js', 'learning.js']) vm.runInContext(fs.readFileSync(__dirname + '/../public/scripts/' + file, 'utf8'), context, { filename: file });
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(app.innerHTML.includes('id="login-form"'));
  assert.ok(!app.innerHTML.includes('class="shell"'));
  assert.ok(!app.innerHTML.includes('toggle-auth'));
  element('email').value='sai@shimentox.com';element('password').value='Temporary123!';
  await element('login-form').onsubmit({preventDefault(){}});
  assert.equal(run('currentUser.mustChangePassword'),true);
  assert.ok(app.innerHTML.includes('id="first-password-form"'));
  assert.ok(!app.innerHTML.includes('class="shell"'));
  context.location.hash='#admin-users';run('render()');
  assert.ok(app.innerHTML.includes('id="first-password-form"'));
  element('temporary-password').value='Temporary123!';element('first-new-password').value='Personal123!';element('first-confirm-password').value='different';
  await element('first-password-form').onsubmit({preventDefault(){}});
  assert.ok(element('auth-error').textContent.includes('do not match'));
  element('first-confirm-password').value='Personal123!';
  await element('first-password-form').onsubmit({preventDefault(){}});
  assert.equal(run('currentUser.mustChangePassword'),false);
  assert.equal(run('currentUser.name'),'Sai Charan');
  // Employees open on My Learning, which also leads their sidebar.
  assert.equal(context.location.hash,'courses');
  assert.equal(context.document.title,'My Learning • ShimentoX');
  assert.ok(!app.innerHTML.includes('href="#admin-users"'));
  assert.ok(app.innerHTML.includes('My Profile'));
  assert.equal(run('portalNavigation().length'),7);
  assert.equal(run('JSON.stringify(portalNavigation().map(n=>n[2]))'),JSON.stringify(['My Learning','My Dashboard','Learning Paths','Skills & Goals','Training Calendar','My Certificates','My Profile']));
  context.location.hash='';run('render()');assert.equal(context.document.title,'My Learning • ShimentoX');
  context.location.hash='#dashboard';run('render()');assert.ok(app.innerHTML.includes('Welcome back, Sai'),'The dashboard is still one click away.');
  context.location.hash='#admin-courses';run('render()');
  assert.ok(!app.innerHTML.includes('id="course-editor-form"'));
  console.log('PASS assigned-credential login, mandatory password change, candidate navigation and route protection');

  for (const page of ['dashboard', 'home', 'courses', 'course', 'certificates', 'account']) {
    context.location.hash = '#' + page; run('render()'); assert.ok(app.innerHTML.includes('class="shell"'));
  }
  context.location.hash = '#course'; run('selectedActivity="video-0";render()');
  const video = elements['course-video']; Object.assign(video, { duration: 48, currentTime: 30, playbackRate: 1, paused: false });
  video.handlers.seeking(); assert.equal(video.currentTime, 0);
  for (let tick = 0; tick < 96; tick++) { context.performance.time += 500; video.currentTime += 0.5; video.handlers.timeupdate(); }
  await video.handlers.ended(); await run('operationQueue');
  assert.equal(run('videoDone(0)'), true);
  assert.ok(requests.some(r => r.path === 'learning/video' && r.data.complete));
  run('selectedActivity="exercise-0";render()');
  const form = elements['exercise-form']; form.dataset.exercise = '0'; form.answers = { 'practice-0': '0', 'practice-1': '1' };
  await form.onsubmit({ preventDefault() {} });
  assert.equal(run('exerciseDone(0,0)'), true);
  assert.ok(app.innerHTML.includes('2/2 correct'));
  assert.equal(requests.filter(r => r.path === 'learning/exercise').length, 1);
  console.log('PASS authenticated routes, video tracking API, server exercise feedback');

  server.learning.run.videos[1] = { watched: 48, complete: true }; server.learning.run.exercises['0-1'] = true;
  await run('loadCandidate()'); context.location.hash = '#course'; run('render()');
  assert.equal(await run('startExam(0)'), true);
  context.document.hidden = true;
  docEvents.visibilitychange[0]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(run('activeExam'), null);
  const termination = requests.find(r => r.path === 'learning/exam-finish');
  assert.equal(termination.data.terminate, true);
  assert.equal(termination.options.keepalive, true);
  assert.equal(run('learning.run.attempts[0][0].status'), 'terminated');
  assert.ok(!requests.some(r => 'score' in r.data || 'certificates' in r.data));
  console.log('PASS persisted exam start, tab-switch keepalive termination, no client-supplied grading');

  context.document.hidden = false;
  const testAdmin={id:'admin-one',name:'Portal Admin',email:'admin@shimentox.com',role:'admin',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z',certificates:0,courseRuns:0,active:true};
  server.user=testAdmin;context.testAdmin=testAdmin;run('currentUser=testAdmin');await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');assert.ok(app.innerHTML.includes('ADMINISTRATOR WORKSPACE'));
  context.location.hash='#admin-users';run('render()');assert.ok(app.innerHTML.includes('id="create-candidate-form"'));
  element('new-candidate-name').value='New Learner';element('new-candidate-email').value='learner@shimentox.com';element('new-candidate-role').value='employee';element('new-candidate-password').value='Assigned123!';
  await element('create-candidate-form').onsubmit({preventDefault(){}});
  assert.ok(requests.some(r=>r.path==='admin/candidates'&&r.data.email==='learner@shimentox.com'&&r.data.role==='employee'));
  assert.ok(app.innerHTML.includes('Share these credentials'));
  context.location.hash='#admin-courses';run('render()');
  // New courses open the step-by-step builder; existing 3-module courses keep the curriculum editor.
  assert.ok(app.innerHTML.includes('id="course-builder"')&&app.innerHTML.includes('Learning materials')&&app.innerHTML.includes('Publication status'));
  run('builderStep=2;render()');assert.ok(app.innerHTML.includes('+ Add lesson')&&app.innerHTML.includes('Add an official learning source'));
  run(`courseDraft.title='GenAI Foundations';courseDraft.description='Intro';courseDraft.lessons[0].title='What is GenAI?'`);
  assert.ok(run('publishProblems().some(p=>p.includes("needs a video, document"))'),'Publishing requires lesson material');
  run(`courseDraft.lessons[0].videoUrl='https://youtu.be/dQw4w9WgXcQ';courseDraft.lessons.push(newLesson());courseDraft.lessons[1].title='Prompting';courseDraft.lessons[1].content='Be specific.';courseDraft.assessment=newAssessment();Object.assign(courseDraft.assessment.questions[0],{prompt:'Pick one',options:['A','B'],correct:1});`);
  assert.equal(run('publishProblems().length'),0);
  const payload=JSON.parse(run(`JSON.stringify(builderPayload('draft'))`));
  assert.equal(payload.format,'lessons');assert.equal(payload.status,'draft');
  assert.deepEqual(payload.lessons.map(l=>l.title),['What is GenAI?','Prompting']);
  assert.deepEqual(payload.assessment.questions[0],{prompt:'Pick one',options:['A','B'],correct:1,explanation:''});
  run('builderStep=4;render()');assert.ok(app.innerHTML.includes('LESSON 1 OF 2')&&app.innerHTML.includes('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'));
  run(`editingCourse='python-programming';courseDraft=null;render()`);assert.ok(app.innerHTML.includes('id="course-editor-form"'));
  run('editingCourse=null;courseDraft=null');
  // Add a course → Import from URL: manual creation stays available; the preview keeps modules, lessons and statuses.
  run(`IMPORT_ACTIONS.choose();render()`);assert.ok(app.innerHTML.includes('Create manually')&&app.innerHTML.includes('Import from URL'));
  run(`IMPORT_ACTIONS.open();render()`);assert.ok(app.innerHTML.includes('id="import-form"')&&app.innerHTML.includes('Difficulty level')&&!app.innerHTML.includes('id="course-builder"'));
  run(`importState.url='https://learn.microsoft.com/en-us/training/modules/organize-data/'`);await run('runCourseImport()');
  assert.ok(requests.some(r=>r.path==='manage/import/preview'&&r.data.url.includes('organize-data')));
  assert.equal(run('importState.title'),'Organize data');assert.equal(run('importState.durationMinutes'),'2');
  assert.ok(app.innerHTML.includes('Collections')&&app.innerHTML.includes('NOT RETRIEVED')&&app.innerHTML.includes('No readable lesson text'));
  run(`importState.openLesson='0-0';render()`);assert.ok(app.innerHTML.includes('<ul><li>one<ul><li>nested</li></ul></li></ul>')&&app.innerHTML.includes('lesson-code'));
  await run(`saveCourseImport('draft')`);assert.ok(run('importState.error').includes('may reuse this content'),run('importState.error'));assert.ok(!requests.some(r=>r.path==='manage/import/save'),'Saving full content requires the rights confirmation');
  run(`IMPORT_ACTIONS.close();render()`);assert.ok(app.innerHTML.includes('id="course-builder"'));
  context.location.hash='#admin-audit';run('render()');assert.ok(app.innerHTML.includes('Activity log'));
  console.log('PASS admin dashboard, candidate provisioning, course editor and audit pages');
  await run('logoutPortal()');
  assert.equal(run('currentUser'), null);
  assert.equal(run('learning.run.id'), null);
  assert.ok(app.innerHTML.includes('id="login-form"'));
  server.failLogin = true; element('email').value = 'sai@shimentox.com'; element('password').value = 'incorrect';
  await element('login-form').onsubmit({ preventDefault() {} });
  assert.ok(element('auth-error').textContent.includes('incorrect'));
  assert.equal(run('currentUser'), null);
  assert.ok(!requests.some(r=>r.path==='auth/register'));
  console.log('PASS logout clears candidate data, invalid credentials, and no public registration');
  server.setupRequired=true;server.failLogin=false;
  await run('initializePortal()');
  assert.ok(app.innerHTML.includes('id="admin-setup-form"'));
  element('setup-name').value='First Owner';element('setup-email').value='owner@shimentox.com';element('setup-password').value='Owner123!';element('setup-confirm').value='different';
  await element('admin-setup-form').onsubmit({preventDefault(){}});
  assert.ok(element('auth-error').textContent.includes('do not match'));
  element('setup-confirm').value='Owner123!';
  await element('admin-setup-form').onsubmit({preventDefault(){}});
  assert.equal(run('currentUser.role'),'admin');assert.equal(run('firstAdminSetup'),false);
  assert.ok(app.innerHTML.includes('href="#admin-users"'));
  assert.ok(app.innerHTML.includes('>Users &amp; Teams</a>'));
  console.log('PASS browser first-admin setup, password confirmation, and Users navigation');

  // Employee L&D views render real API shapes, keep roles separated, and escape exported data.
  server.user={id:'employee-one',name:'Sai Charan',email:'sai@shimentox.com',role:'employee',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z'};
  run('currentUser=null');context.serverUser=server.user;run('currentUser=serverUser');await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Assigned to me')&&app.innerHTML.includes('MANDATORY'));
  assert.ok(app.innerHTML.includes('SQL Foundations')&&app.innerHTML.includes('Closes your SQL gap'));
  assert.ok(app.innerHTML.includes('Engineering · Manager: Line Manager')||app.innerHTML.includes('Data Analyst · Engineering'));
  assert.ok(!app.innerHTML.includes('href="#admin-users"')&&!app.innerHTML.includes('href="#reports"'));
  assert.equal(run('notificationState.unread'),1);assert.ok(app.innerHTML.includes('class="notification-count"'));
  context.location.hash='#course';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Learning materials')&&app.innerHTML.includes('has not been enabled'));
  assert.ok(app.innerHTML.includes('MODULE 1'));
  context.location.hash='#reports';run('render()');assert.ok(!app.innerHTML.includes('Export CSV'));
  console.log('PASS employee dashboard, assignments, recommendations, notifications, course resources, assistant state');
  for(const [role,expected] of [['manager','Team Reports'],['trainer','Manage Courses'],['hr','Users & Teams']]){context.roleUser={...server.user,role};run('currentUser=roleUser');assert.ok(run('portalNavigation().map(n=>n[2])').includes(expected),role);}
  run('currentUser=roleUser;currentUser.role="trainer"');assert.ok(!run('portalNavigation().map(n=>n[0])').includes('admin-users'));
  context.adminUser={...testAdmin};run('currentUser=adminUser');await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Total employees')&&app.innerHTML.includes('>12<')&&app.innerHTML.includes('42%'));
  assert.ok(app.innerHTML.includes('Department-wise training')&&app.innerHTML.includes('Late Learner')&&app.innerHTML.includes('Security Awareness'));
  context.location.hash='#reports';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Export CSV')&&app.innerHTML.includes('=HYPERLINK(&quot;x&quot;)'));
  const csv=run(`toCSV([{key:'a',label:'Name'},{key:'b',label:'Note'}],[{a:'=SUM(A1)',b:'Hello, "team"'}])`);
  assert.equal(csv.split('\r\n')[1],`'=SUM(A1),"Hello, ""team"""`);
  console.log('PASS role navigation, organisation dashboard metrics, reports and safe CSV export');
  // A backend process started before an update reports an older (or no) API version: admins get restart guidance, employees a neutral message.
  server.apiVersion=null;server.user={...testAdmin};server.setupRequired=false;await run('initializePortal()');
  assert.equal(run('serverOutdated'),true);
  context.location.hash='#paths';run('render()');assert.ok(app.innerHTML.includes('older version of the portal')&&app.innerHTML.includes('npm start'));
  context.empUser={id:'employee-one',name:'Sai Charan',email:'sai@shimentox.com',role:'employee',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z'};run('currentUser=empUser');run('render()');
  assert.ok(app.innerHTML.includes('temporarily unavailable')&&!app.innerHTML.includes('npm start'));
  server.apiVersion=9;await run('initializePortal()');assert.equal(run('serverOutdated'),false);assert.ok(!app.innerHTML.includes('older version of the portal'));
  console.log('PASS outdated-server detection with role-appropriate guidance');
  for (let i = 1; i <= 6; i++) {
    assert.ok(fs.statSync(__dirname + `/../public/assets/videos/lesson-${i}.webm`).size > 1000);
    assert.ok(fs.readFileSync(__dirname + `/../public/assets/videos/lesson-${i}.vtt`, 'utf8').startsWith('WEBVTT'));
  }
  console.log('PASS video and caption assets');

  // Native Python assignments use the same interruption hooks as module exams.
  const original=JSON.parse(fs.readFileSync(__dirname+'/../../backend/data/shimento-python-course.json','utf8'));
  server.learning=empty();Object.assign(server.learning.run,{format:'lessons',courseId:original.id,lessonTotal:18,lessons:{},checkpoints:original.assignments.map(a=>({id:a.id,title:a.title,instructions:a.instructions,afterLesson:a.afterLesson,passPercent:75,maxAttempts:3,timeLimitSeconds:600,questionCount:8,ready:a.afterLesson===3,passed:false,attempts:[]}))});
  server.courseLessons=original.lessons.map((l,i)=>({id:original.id+'-'+l.slug,title:l.title,description:l.description,content:l.content,durationMinutes:25,locked:i>=3}));
  server.courseLessons.slice(0,3).forEach(l=>server.learning.run.lessons[l.id]={completed:true});
  server.checkpointQuestions=original.assignments[0].questions.map(({correct,...q})=>q);
  context.assignmentState=copy(server.learning);context.assignmentLessons=copy(server.courseLessons);context.assignmentInfo={id:original.id,title:original.title,format:'lessons',difficulty:'beginner',durationMinutes:500};
  run('currentUser=empUser;learning=assignmentState;currentCourseInfo=assignmentInfo;currentCourseExtras={courseLessons:assignmentLessons,assessments:[]};selectedLessonId=null;selectedCheckpointId=null');
  context.location.hash='#course';run('render()');
  assert.ok(app.innerHTML.includes('Assignment 1: Build a training-score report'));
  const sidebar=app.innerHTML.slice(app.innerHTML.indexOf('<aside class="panel curriculum">'));
  assert.ok(sidebar.indexOf('lesson-03')<sidebar.indexOf('data-checkpoint-select='));
  assert.ok(sidebar.indexOf('data-checkpoint-select=')<sidebar.indexOf('lesson-04'));
  assert.ok(app.innerHTML.includes('8 applied questions')&&app.innerHTML.includes('75%'));
  assert.equal(run('courseProgress()'),13);
  await run('startCheckpoint(learning.run.checkpoints[0].id)');
  assert.equal(run('activeExam.kind'),'checkpoint');assert.ok(app.innerHTML.includes('id="checkpoint-form"'));
  context.document.hidden=true;docEvents.visibilitychange[0]();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(run('activeExam'),null);
  const checkpointTermination=requests.filter(r=>r.path==='learning/checkpoint-finish').at(-1);
  assert.equal(checkpointTermination.data.terminate,true);assert.equal(checkpointTermination.options.keepalive,true);
  assert.equal(run('learning.run.checkpoints[0].attempts[0].status'),'terminated');
  context.document.hidden=false;await run('startCheckpoint(learning.run.checkpoints[0].id)');
  await run('finishCheckpoint(null,[0,0,0,0,0,0,0,0])');
  assert.equal(run('learning.run.checkpoints[0].passed'),true);
  assert.equal(run('currentCourseExtras.courseLessons[3].locked'),false);
  assert.equal(run('courseProgress()'),17);
  assert.ok(!requests.filter(r=>r.path.startsWith('learning/checkpoint')).some(r=>'score' in r.data||'passed' in r.data));
  assert.ok(app.innerHTML.includes('Assignment passed: 8/8'));
  console.log('PASS Python assignment placement, timed focus view, tab-switch termination, grading contract and next-group unlock');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
