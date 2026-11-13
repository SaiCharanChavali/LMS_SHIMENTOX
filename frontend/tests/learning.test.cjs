// UI-to-API contract checks. Real HTTP/SQLite rules are tested in backend/tests.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const curriculum = JSON.parse(fs.readFileSync(__dirname + '/../../backend/data/python-course.json', 'utf8'));
const copy = value => JSON.parse(JSON.stringify(value));
const fixtureLessons=JSON.parse(fs.readFileSync(__dirname+'/../../backend/data/python-lessons.json','utf8'));
const courseInfo={id:'python-programming',title:'PYTHON PROGRAMMING',category:'Development',description:'Python basics',status:'published',progress:0,enrolled:true,completed:false,difficulty:'beginner',durationMinutes:90,passPercent:75,maxAttempts:3,assignment:{mandatory:true,dueDate:'2099-01-31',assignedBy:'HR Partner'}};
const employeeDashboard={training:{year:2026,targetHours:30,completedHours:12,percent:40},profile:{name:'Sai Charan',email:'sai@shimentox.com',role:'employee',department:'Engineering',job_role:'Data Analyst',manager:'Line Manager',job_title:''},stats:{assigned:1,inProgress:0,completed:0,overdue:0,certificates:0},assigned:[{...courseInfo,status:'not_started'}],continue:[],recommendations:[{id:'sql',title:'SQL Foundations',description:'Query data.',difficulty:'beginner',durationMinutes:60,category:'Data Analytics',reasons:['Builds on Data Analytics courses you have completed.']}],sessions:[],pendingAssessments:[],history:[]};
const orgDashboardData={training:[{id:'r1',name:'Team Report',department:'Engineering',year:2026,targetHours:20,completedHours:5,percent:25}],scope:'organisation',kpis:{totalEmployees:12,activeLearners:7,publishedCourses:3,completionRate:42,enrollments:19,completions:8,certificatesEarned:8,trainingHours:15.5,pendingMandatory:4},progress:{activelyLearning:6,completedAssigned:3,notStarted:2,overdue:1,overdueEmployees:[{id:'e1',name:'Late Learner',department:'Sales',overdue:1}]},departments:[{department:'Engineering',employees:5,participants:4,participationRate:80,completionRate:50,completionsInPeriod:3,averageScore:82,trainingHours:9.2}],period:{from:null,to:null},recent:[{type:'completion',at:'2026-10-20T10:00:00Z',text:'Asha completed SQL Foundations and earned a certificate'}],upcoming:{sessions:[],deadlines:[{courseId:'c1',course:'Security Awareness',dueDate:'2099-01-01',pending:4,overdue:false}],pendingAssessments:[]}};
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
    if (path === 'session') result = { user: server.user, csrfToken: server.user ? 'csrf-test' : null,setupRequired:server.setupRequired,setupAllowed:true,apiVersion:server.apiVersion===undefined?15:server.apiVersion };
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
    else if(path==='manage/org')result={departments:[{id:'d1',name:'Engineering',employees:5}],jobRoles:[],categories:['Technical Skills'],courses:[{id:'python-programming',title:'PYTHON PROGRAMMING',status:'published'}],trainers:[],managers:[],levels:[]};
    else if(path==='manage/people')result={people:server.people||[]};
    else if(path==='manage/assessments')result={assessments:[]};
    else if(path==='me/onboarding')result={onboarding:server.onboarding===undefined?null:server.onboarding};
    else if(path==='manage/onboarding/templates')result={templates:[{id:'t1',name:'Engineering <x>',description:'',status:'active',departmentId:'d1',department:'Engineering',jobRoleIds:[],jobRoles:[],milestones:[{day:1,title:'Day 1'},{day:30,title:'Day 30'}],courses:[{courseId:'c1',title:'Welcome',day:1,mandatory:true,published:true}],mandatoryCount:1,onboardingsActive:2,onboardingsTotal:3,updatedAt:'2026-11-01T00:00:00Z',updatedBy:'Admin',warnings:['"Old course" is not published, so it will be skipped.']}],options:{departments:[['d1','Engineering']],jobRoles:[['r1','Developer']],courses:[['c1','Welcome']]}};
    else if(path.startsWith('manage/onboarding/o1'))result={onboarding:{...server.plan,employee:'Asha',email:'asha@shimentox.com',department:'Engineering',jobRole:'Developer',manager:'Mani'}};
    else if(path.startsWith('manage/onboarding'))result={scope:'organisation',canManage:server.user?.role!=='manager',filters:{},summary:{onboarding:2,completed:1,pendingEmployees:2,overdueMandatory:1,overdueEmployees:1,averagePercent:58},
      departments:[{id:'d1',name:'Engineering',employees:3,completed:1,overdue:1,averagePercent:58}],jobRoles:[{id:'__none__',name:'Unassigned',employees:3,completed:1,overdue:1,averagePercent:58}],
      table:{rows:[{onboardingId:'o1',employeeId:'e1',employee:'Asha <b>',email:'asha@shimentox.com',department:'Engineering',jobRole:'Developer',template:'Engineering',joiningDate:'2026-11-01',startDate:'2026-11-01',status:'overdue',statusLabel:'Overdue',percent:50,mandatoryDone:1,mandatoryTotal:2,overdueMandatory:1,pendingMandatory:1,optionalDone:0,optionalTotal:1,nextMilestone:{title:'Day 30',date:'2026-11-30',state:'upcoming'},completedAt:null}],total:1,page:1,pages:1},
      options:{departments:[['d1','Engineering']],jobRoles:[['__none__','Unassigned']]},needsOnboarding:{rows:[{employeeId:'e9',employee:'Nora',email:'nora@shimentox.com',department:'Marketing',jobRole:'Unassigned',joiningDate:'2020-01-01',defaultStartDate:'2026-11-11',templateId:null,template:null,reason:'no_template'}],total:1,page:1,pages:1},templates:[['t1','Engineering']]};
    else if(path.startsWith('manage/compliance'))result={scope:server.user?.role==='manager'?'team':'organisation',timezone:'IST',updatedDisplay:'5 November 2026, 11:00 AM',filters:{},summary:{total:5,completed:1,completedOnTime:1,completedLate:0,inProgress:2,notStarted:1,overdue:1,completionRate:20},
      departments:[{department:'Finance',total:4,completed:1,pending:3,overdue:0,completionRate:25},{department:'Sales <b>',total:1,completed:0,pending:0,overdue:1,completionRate:0}],
      table:{rows:[{employee:'Asha <i>',employeeId:'11111111-2222-3333-4444-555555555555',email:'asha@shimentox.com',department:'Finance',jobRole:'Analyst',courseId:'c1',course:'Security',mandatory:true,assignedDate:'2026-05-01',assignedDisplay:'1 May 2026, 9:00 AM',deadlineDate:'2026-06-01',deadlineDisplay:'1 June 2026, 9:00 AM',originalDeadlineDisplay:'1 June 2026, 9:00 AM',completedDate:null,completedDisplay:null,lastActivityDisplay:null,progress:40,status:'in_progress',statusLabel:'In Progress',dueSoon:true}],total:5,page:1,pages:2},
      overdue:{rows:[{employee:'Esha Rao',employeeId:'emp-2',department:'Sales',jobRole:'Unassigned',course:'Privacy',mandatory:true,originalDeadlineAt:'a',deadlineAt:'b',originalDeadlineDisplay:'1 April 2026, 9:00 AM',deadlineDisplay:'1 May 2026, 9:00 AM',overdueBy:'3 days, 2 hours',progress:10,lastActivityDisplay:null,status:'overdue'}],total:1,page:1,pages:1,mandatory:1},
      options:{employees:[['emp-1','Asha'],['emp-2','Esha']],departments:[['d1','Finance']],courses:[['c1','Security']],jobRoles:[['__none__','Unassigned']]}};
    else if(path.startsWith('me/history')){const item=(id,type,label,group,extra={})=>({id,type,label,group,at:'2026-11-10T09:30:00.000Z',courseId:'c1',course:'Security <b>',lesson:null,subject:'Security <b>',status:null,detail:'',percent:null,backfilled:false,...extra});
      result={records:[],sessions:[{title:'Workshop',at:'2026-11-01T10:00:00Z'}],total:server.historyTotal??3,page:Number((path.match(/page=(\d+)/)||[])[1]||1),pages:server.historyTotal>20?2:1,filters:{},courses:[{id:'c1',title:'Security <b>'}],types:[['course_opened','Course opened'],['assessment_passed','Assessment passed']],
        items:server.historyTotal===0?[]:[item('a1','assessment_passed','Assessment passed','assessment',{subject:'Module 1 exam',status:'passed',detail:'Module exam · 100% · pass mark 75%',percent:100}),item('a2','lesson_completed','Lesson completed','lesson',{subject:'Phishing basics',lesson:'Phishing basics',status:'completed'}),item('a3','course_started','Course started','course',{status:'in_progress',backfilled:true})]};}
    else if(path.startsWith('manage/activity/analytics'))result={period:{from:'2026-08-14',to:'2026-11-11',inactiveDays:30,department:null},scope:'organisation',mostAccessed:[{courseId:'c1',course:'Security <b>',learners:4,visits:9}],mostCompleted:[{courseId:'c1',course:'Security <b>',learners:2}],
      abandonment:[{courseId:'c1',course:'Security <b>',started:4,completed:2,inProgress:1,abandoned:1,rate:25}],lessonPatterns:[{course:'Security <b>',lesson:'Intro',started:4,completed:3,rate:75}],completionsByWeekday:[0,3,1,0,2,0,0],
      attemptRates:[{courseId:'c1',course:'Security <b>',accessed:4,attempted:2,rate:50}],assessmentResults:[{assessment:'Module 1 exam',kind:'Module exam',course:'Security <b>',passed:3,failed:1,passRate:75}],
      inactive:[{employeeId:'e9',employee:'Nora <i>',department:'Sales',lastActivity:null}],inactiveTotal:1,departments:[{department:'Sales',employees:3,activeLearners:2,engagementRate:67,lessonsCompleted:5,coursesCompleted:1,assessmentsSubmitted:4}],
      definitions:{access:'Access is not evidence of learning.',abandonment:'Abandoned rule.',attemptRate:'Attempt rule.',passRate:'Pass rule.',engagement:'Activity volume is not a measure of productivity.',dates:'UTC'},options:{employees:[],courses:[],types:[],departments:[{id:'d1',name:'Sales'}],jobRoles:[]}};
    else if(path.startsWith('manage/activity/employees/'))result={employee:{id:'e1',name:'Asha <i>',employeeNumber:'EMP-7',department:'Finance',jobRole:'Analyst'},items:[{id:'x1',type:'course_completed',label:'Course completed',group:'course',at:'2026-11-09T08:00:00.000Z',courseId:'c1',course:'Security <b>',subject:'Security <b>',status:'completed',detail:''}],page:1,pages:1,total:1,filters:{},courses:[{id:'c1',title:'Security <b>'}],types:[['course_completed','Course completed']]};
    else if(path.startsWith('manage/activity'))result={scope:server.user?.role==='manager'?'team':'organisation',summary:{totalActivities:42,activeLearners:5,coursesAccessed:3,lessonsCompleted:12,assessmentsAttempted:7,coursesCompleted:2},page:1,pages:2,total:42,filters:{},
      items:[{id:'s1',type:'assessment_failed',label:'Assessment failed',group:'assessment',at:'2026-11-10T09:30:00.000Z',courseId:'c1',course:'Security <b>',subject:'Module 2 exam',status:'failed',detail:'Module exam · 25% · pass mark 75%',employeeId:'e1',employeeNumber:'EMP-7',employee:'Asha <i>',department:'Finance',jobRole:'Analyst',progress:40}],
      options:{employees:[{id:'e1',name:'Asha <i>'}],courses:[{id:'c1',title:'Security <b>'}],types:[['assessment_failed','Assessment failed']],departments:[{id:'d1',name:'Finance'}],jobRoles:[{id:'j1',name:'Analyst'}]}};
    else if(/^me\/resources\/[^/]+\/open$/.test(path))result={url:'api/materials/x'};
    else if(path.startsWith('manage/reports'))result={type:'enrollments',title:'Course enrollment and completion',columns:[{key:'employee',label:'Employee'},{key:'status',label:'Status'}],rows:[{employee:'=HYPERLINK("x")',status:'Completed'}],summary:{Enrollments:1},total:1,page:1,pages:1};
    else if(path==='admin/overview')result={stats:{candidates:1,courses:1,certificates:0,exams:0}};
    else if(path==='admin/candidates')result=options.body?{candidate:{id:'new-account'}}:{candidates:[server.user,{...server.user,id:'existing-one',name:'Existing Employee',email:'existing@shimentox.com',role:'employee',active:true,certificates:0,courseRuns:1,training:{year:2026,targetHours:null,completedHours:3,percent:null}}]};
    else if(path==='manage/course-generator')result={enabled:true};
    else if(path==='manage/training-targets')result={training:Object.fromEntries(data.employeeIds.map(id=>[id,{year:2026,targetHours:data.hours,completedHours:0,percent:0}]))};
    else if(path==='admin/courses'&&options.body){server.savedCourse={id:data.id||'new-course',title:data.title,status:data.status};result={course:{...server.savedCourse}};}
    else if(/^manage\/courses\/[^/]+\/builder$/.test(path)){const c=server.savedCourse;result={course:{id:c.id,title:c.title,category:'Technical Skills',description:'Stay safe',difficulty:'beginner',durationMinutes:60,visibility:'everyone',status:c.status},lessons:[{id:'l1',title:'Passwords',description:'',videoUrl:'',documentUrl:'',documentName:'',resources:[],content:'Use a manager.',exercise:'',durationMinutes:10,moduleTitle:'Module 1: Basics',moduleIndex:0,hasProgress:false}],assessment:null};}
    else if(/^admin\/courses\/[^/]+\/archive$/.test(path))result={ok:true};
    else if(path.startsWith('manage/deadlines'))result={courseId:'new-course',timezone:'IST',targets:[{id:'a1',courseId:'new-course',targetType:'department',targetId:'d1',target:'Engineering',mandatory:true,deadlineInput:'2099-01-31T18:00',deadlineDisplay:'31 January 2099, 6:00 PM',employees:5,completed:1,canRemove:true,note:''},{id:'a2',courseId:'new-course',targetType:'employee',targetId:'e2',target:'Ravi',mandatory:false,deadlineInput:'',deadlineDisplay:null,employees:1,completed:1,canRemove:true,note:''}],
      employees:[{employeeId:'e1',name:'Asha',email:'asha@shimentox.com',department:'Engineering',assignmentId:'a1',source:'department',mandatory:true,deadlineInput:'2099-01-31T18:00',deadlineDisplay:'31 January 2099, 6:00 PM',status:'overdue',statusLabel:'Overdue',progress:40,lastReminder:null,nextReminderAt:null},{employeeId:'e2',name:'Ravi',email:'ravi@shimentox.com',department:'Sales',assignmentId:'a2',source:'employee',mandatory:false,deadlineInput:'',deadlineDisplay:null,status:'completed_on_time',statusLabel:'Completed on time',progress:100,lastReminder:null,nextReminderAt:null}]};
    else if(path==='manage/reminders/settings')result={settings:{intervalDays:[7,3,1],dueSoonDays:7,deadlineDay:true,overdue:true,lastRunAt:null,lastRun:null}};
    else if(path.startsWith('manage/reminders/history'))result={history:[{id:1,employee:'Asha',course:'Security Basics',type:'before_3d',scheduledAt:'2026-11-01T00:00:00Z',sentAt:'2026-11-01T00:00:01Z',status:'sent'},{id:2,employee:'Ravi',course:'Security Basics',type:'overdue',scheduledAt:'2026-11-02T00:00:00Z',sentAt:null,status:'failed',failureReason:'Mailbox <full>'}]};
    else if(path==='manage/assignments')result={assignments:options.body?[]:[{id:'a1',courseId:'new-course',course:'Security Basics',targetType:'department',targetId:'d1',target:'Engineering',mandatory:true,deadlineAt:'2099-01-31T12:30:00Z',deadlineDisplay:'31 January 2099, 6:00 PM',deadlineInput:'2099-01-31T18:00',note:'',assignedBy:'Admin',assignedAt:'2026-11-01T09:00:00Z',employees:5,completed:1,canRemove:true},
      ...Array.from({length:12},(_,i)=>({id:'t'+i,courseId:'new-course',course:'Security Basics',targetType:'employee',targetId:'e'+i,target:'Team '+(i+1),mandatory:false,deadlineAt:null,deadlineDisplay:null,deadlineInput:'',note:'',assignedBy:'Admin',assignedAt:'2026-11-02T09:00:00Z',employees:1,completed:0,canRemove:true}))]};
    else if(path==='admin/courses')result={courses:[{...courseInfo,content:{sets:curriculum,lessons:fixtureLessons}},...(server.savedCourse?[{...courseInfo,...server.savedCourse,format:'lessons',assignments:2,learners:0}]:[])]};
    else if(path==='admin/audit')result={events:[]};
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
    document: { getElementById: element, querySelector: () => null, querySelectorAll: () => [], body: { classList: classes() }, hidden: false, addEventListener: (n, fn) => (docEvents[n] ||= []).push(fn), title: '',
      // Exams require full screen; tests can deny it with allowFullscreen=false.
      fullscreenElement: null, documentElement: { async requestFullscreen() { if (!context.allowFullscreen) throw Error('denied'); context.document.fullscreenElement = this; } }, async exitFullscreen() { context.document.fullscreenElement = null; } },
    allowFullscreen: true,
    location: { hash: '#dashboard' }, window: { addEventListener: (n, fn) => (events[n] ||= []).push(fn), scrollTo() {}, print() {} },
    fetch, Intl, Date, URL, performance: { time: 0, now() { return this.time; } }, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    FormData: class { constructor(form) { this.form = form; } get(key) { return this.form.answers[key] ?? null; } }
  };
  vm.createContext(context);
  const run = code => vm.runInContext(code, context);
  for (const file of ['auth.js', 'app.js', 'admin.js', 'development.js', 'live-training.js', 'onboarding.js', 'activity.js', 'course-import.js', 'python-practice.js', 'learning.js']) vm.runInContext(fs.readFileSync(__dirname + '/../public/scripts/' + file, 'utf8'), context, { filename: file });
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(app.innerHTML.includes('id="login-form"'));
  // Sign in with Keka account: a link to the server's Keka start route, and a clear message when Keka sign-in fails.
  assert.ok(app.innerHTML.includes('href="/api/auth/keka/start"')&&app.innerHTML.includes('Sign in with Keka account'));
  context.location.search='?signin_error=keka-inactive';context.location.pathname='/';run('render()');
  assert.ok(element('auth-error').textContent.includes('Your account is not active'));
  context.location.search='';
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
  assert.equal(run('portalNavigation().length'),6);
  for(const removed of ['#paths','#skills']){context.location.hash=removed;run('render()');assert.equal(context.document.title,'My Learning • ShimentoX','Learning Paths and Skills pages are removed.');}
  context.location.hash='#courses';run('render()');
  assert.equal(run('JSON.stringify(portalNavigation().map(n=>n[2]))'),JSON.stringify(['My Learning','Courses','My Dashboard','Training Calendar','My Certificates','My Profile']));
  context.location.hash='';run('render()');assert.equal(context.document.title,'My Learning • ShimentoX');
  // My Learning shows assigned, started or completed courses; the Courses page lists every published course.
  run(`courseCatalog=[{...courseCatalog[0],id:'started-course',title:'Started Course',started:true,completed:false},{...courseCatalog[0],id:'done-course',title:'Done Course',started:true,completed:true},{...courseCatalog[0],id:'new-course',title:'New Course',started:false,completed:false,status:'not_started',assignment:null}]`);
  context.location.hash='#courses';run('render()');
  assert.ok(app.innerHTML.includes('Started Course')&&app.innerHTML.includes('Done Course')&&!app.innerHTML.includes('New Course'));
  assert.ok(app.innerHTML.includes('2 STARTED'));
  // Deadlines: assigned courses are listed with their deadline, status and a countdown from server time.
  const hour=3600,day=86400,inFuture=seconds=>new Date(Date.now()+seconds*1000).toISOString();
  const savedCatalog=run('JSON.stringify(courseCatalog)');
  run(`courseCatalog=${JSON.stringify([
    {...courseInfo,id:'due-soon',title:'Due Soon Course',started:false,completed:false,assignment:{mandatory:true},deadline:{at:inFuture(2*day+4*hour+60),display:'8 November 2026, 6:00 PM',timezone:'IST',status:'due_soon',label:'Due Soon',dueSoonSeconds:7*day,started:false,completedAt:null}},
    {...courseInfo,id:'late',title:'Late Course',started:true,completed:false,assignment:{mandatory:false},deadline:{at:inFuture(-(day+3*hour+60)),display:'1 November 2026, 9:00 AM',timezone:'IST',status:'overdue',label:'Overdue',dueSoonSeconds:7*day,started:true,completedAt:null}},
    {...courseInfo,id:'on-time',title:'On Time Course',started:true,completed:true,assignment:{mandatory:true},deadline:{at:inFuture(-day),display:'2 November 2026, 9:00 AM',timezone:'IST',status:'completed_on_time',label:'Completed On Time',dueSoonSeconds:7*day,started:true,completedAt:'2026-11-01T00:00:00Z',completedDisplay:'1 November 2026, 5:30 AM'}},
    {...courseInfo,id:'done-late',title:'Finished Late Course',started:true,completed:true,assignment:{mandatory:true},deadline:{at:inFuture(-day),display:'2 November 2026, 9:00 AM',timezone:'IST',status:'completed_late',label:'Completed Late',dueSoonSeconds:7*day,started:true,completedAt:'2026-11-03T00:00:00Z',completedDisplay:'3 November 2026, 5:30 AM'}},
  ])}`);
  run('render()');
  assert.ok(app.innerHTML.includes('Due Soon Course'),'An assigned course appears before it is started.');
  assert.ok(app.innerHTML.includes('3 STARTED · 1 ASSIGNED'));
  assert.ok(app.innerHTML.includes('Deadline:</b> 8 November 2026, 6:00 PM IST'));
  assert.ok(app.innerHTML.includes('Time remaining: 2 days, 4 hours'));
  assert.ok(app.innerHTML.includes('Overdue by 1 day, 3 hours'));
  assert.ok(app.innerHTML.includes('deadline-box due-soon')&&app.innerHTML.includes('deadline-box danger')&&app.innerHTML.includes('deadline-box success'),'Yellow, red and green states.');
  // My Learning uses the Courses page tile, which flags assigned courses as Mandatory or Optional on the cover.
  assert.ok(app.innerHTML.includes('COMPLETED ON TIME')&&app.innerHTML.includes('COMPLETED LATE')&&app.innerHTML.includes('course-flag mandatory">Mandatory')&&app.innerHTML.includes('course-flag">Optional'));
  assert.ok(app.innerHTML.indexOf('Late Course')<app.innerHTML.indexOf('Due Soon Course'),'The nearest deadline comes first.');
  assert.ok(!app.innerHTML.includes('datetime-local'),'Employees get no way to edit a deadline.');
  assert.equal(run(`formatSpan(${2*day+4*hour+59})`),'2 days, 4 hours');
  assert.equal(run('formatSpan(61)'),'1 minute, 1 second');
  assert.equal(run('formatSpan(0)'),'0 seconds');
  const stateAt=(left,started)=>run(`deadlineState(new Date(1000000000000).toISOString(),604800,${started},${1000000000000-left*1000})`);
  assert.equal(stateAt(30*day,false).status,'not_started');assert.equal(stateAt(30*day,true).status,'in_progress');assert.equal(stateAt(7*day,false).status,'due_soon');assert.equal(stateAt(0,true).status,'overdue');
  // The countdown changes the card in place, without a page render, and turns red when the deadline passes.
  const fakeTag={},fakeClock={},box={dataset:{deadlineAt:inFuture(-5),deadlineSoon:String(7*day),deadlineStarted:'1'},className:'deadline-box',querySelector:s=>s==='[data-deadline-tag]'?fakeTag:fakeClock};
  const before=app.innerHTML;context.document.querySelectorAll=s=>s==='[data-deadline-at]'?[box]:[];
  run('updateDeadlineClocks()');
  assert.equal(box.className,'deadline-box danger');assert.equal(fakeTag.textContent,'OVERDUE');assert.ok(fakeClock.textContent.startsWith('Overdue by 5 second'));assert.equal(app.innerHTML,before);
  // A server clock ahead of the browser moves the countdown: the browser's clock does not decide.
  run(`serverClockOffset=${2*day*1000}`);box.dataset.deadlineAt=inFuture(day);run('updateDeadlineClocks()');run('serverClockOffset=0');
  context.document.querySelectorAll=()=>[];
  assert.equal(fakeTag.textContent,'OVERDUE');
  // The bell filters unread deadline reminders and links to the course.
  run(`notificationState={items:[{id:9,kind:'deadline',title:'Course Deadline Reminder',body:'Your assigned course must be completed.',link:'course:due-soon',createdAt:'2026-11-04T00:00:00Z',readAt:null},{id:8,kind:'announcement',title:'Learning week',body:'Hello',link:'dashboard',createdAt:'2026-11-03T00:00:00Z',readAt:null}],unread:2,open:true,filter:'deadline'};render()`);
  assert.ok(app.innerHTML.includes('Unread deadlines (1)')&&app.innerHTML.includes('data-link="course:due-soon"')&&!app.innerHTML.includes('Learning week'));
  run(`notificationState={items:[],unread:0,open:false};courseCatalog=${savedCatalog};render()`);
  context.location.hash='#catalog';run('render()');
  assert.equal(context.document.title,'Courses • ShimentoX');
  assert.ok(['Started Course','Done Course','New Course'].every(t=>app.innerHTML.includes(t)));
  // The Courses page groups courses into learning areas derived from each course's category, with live counts.
  run(`savedCatalog=courseCatalog;courseCatalog=[['generative-ai-fundamentals','Generative AI Fundamentals','Artificial Intelligence'],['retrieval-augmented-generation','Retrieval-Augmented Generation (RAG)','Artificial Intelligence'],['python-programming','Python Programming','Development'],['shimento-python-developer','Python Programming Senior','Technical Skills'],['java-full-stack-development','Java Full Stack Development','Technical Skills'],['agile-and-scrum','Agile and Scrum','Professional Development'],['data-privacy-protection','Data Privacy and Protection','Cybersecurity and Data Protection'],['posh-act-awareness','POSH','Policies & Compliance'],['phishing-cybersecurity-awareness','Phishing and CyberSecurity Awareness','Cybersecurity Awareness']].map(([id,title,category],i)=>({...savedCatalog[0],id,title,category,started:i===0,completed:false,progress:i===0?40:0,status:i===0?'in_progress':'not_started'}))`);
  const areaOf={'Artificial Intelligence':'technical','Development':'technical','Technical Skills':'technical','Generative AI & Automation':'technical','Data Analytics':'technical','Professional Development':'professional','Communication & Presentation':'professional','Time Management':'professional','Leadership & Management':'management','Project Management':'management','Talent Acquisition':'recruitment','HR Policies':'compliance','Recruitment & HR':'recruitment','Cybersecurity and Data Protection':'compliance','Cybersecurity Awareness':'compliance','Policies & Compliance':'compliance','Something New':'professional'};
  for(const [category,area] of Object.entries(areaOf))assert.equal(run(`learningArea(${JSON.stringify(category)}).id`),area,category);
  context.location.hash='#catalog';run(`courseArea='all';courseFilter='all';courseSearch=''`);run('render()');
  const count=(value,n)=>assert.ok(new RegExp(`data-value="${value}" aria-pressed="(true|false)">[^<]+ <span>${n}</span>`).test(app.innerHTML),`${value} count ${n}`);
  [['all',9],['technical',5],['professional',1],['recruitment',0],['management',0],['compliance',3]].forEach(([v,n])=>count(v,n));
  const headings=[...app.innerHTML.matchAll(/<div class="catalog-section-head"><h2>([^<]+)<\/h2>/g)].map(m=>m[1]);
  assert.deepEqual(headings,['Technical','Non-Technical &amp; Professional Development','Compliance &amp; Security'],'All Courses is grouped; empty categories are left out.');
  assert.ok(app.innerHTML.includes('title="Cybersecurity and Data Protection">Compliance &amp; Security</span>')&&app.innerHTML.includes('title="Professional Development">Professional Development</span>'),'Badges show the learning area.');
  assert.ok(app.innerHTML.includes('Continue learning')&&app.innerHTML.includes('data-open-course="data-privacy-protection"'),'Progress and Start/Continue buttons are kept.');
  // Corporate catalogue cards: area illustration, facts from the API, status, next step, and no marketplace content.
  assert.ok(app.innerHTML.includes('Courses &amp; Programs')&&app.innerHTML.includes('Explore company learning resources'));
  assert.ok(app.innerHTML.includes('class="course-card area-technical"')&&app.innerHTML.includes('<svg viewBox="0 0 400 200"'),'Each card has its area illustration.');
  assert.ok(['class="course-facts"','Beginner','data-change="course-difficulty"','href="#assessments"','href="#history"'].every(t=>app.innerHTML.includes(t)));
  assert.ok(!/\$\s?\d|₹|price|discount|buy now|add to cart|subscribe/i.test(app.innerHTML.replace(/\$\{/g,'')),'No pricing or purchase wording.');
  run(`CHANGES['course-difficulty']({value:'expert'})`);assert.ok(app.innerHTML.includes('No courses in this view'),'The difficulty filter narrows the catalogue.');
  run(`CHANGES['course-difficulty']({value:'all'})`);assert.ok(app.innerHTML.includes('data-course-card='));
  run(`ACTIONS['course-area']({dataset:{value:'technical'}})`);
  assert.ok(['Generative AI Fundamentals','Python Programming Senior','Java Full Stack Development'].every(t=>app.innerHTML.includes(t))&&!app.innerHTML.includes('>POSH<')&&!app.innerHTML.includes('>Agile and Scrum<'));
  run(`ACTIONS['course-filter']({dataset:{value:'in_progress'}})`);
  assert.equal([...app.innerHTML.matchAll(/data-course-card=/g)].length,1,'Category and status filters combine.');count('technical',1);count('compliance',0);
  run(`ACTIONS['course-area']({dataset:{value:'recruitment'}})`);assert.ok(app.innerHTML.includes('No courses in this view'));
  run(`courseArea='all';courseFilter='all';courseCatalog=savedCatalog`);
  run(`courseCatalog=courseCatalog.filter(c=>!c.started)`);context.location.hash='#courses';run('render()');
  assert.ok(app.innerHTML.includes('You have not started a course yet')&&app.innerHTML.includes('href="#catalog"'));
  await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');assert.ok(app.innerHTML.includes('Welcome back, Sai'),'The dashboard is still one click away.');
  context.location.hash='#admin-courses';run('render()');
  assert.ok(!app.innerHTML.includes('id="course-editor-form"'));
  console.log('PASS assigned-credential login, mandatory password change, candidate navigation and route protection');

  for (const page of ['dashboard', 'home', 'courses', 'course', 'certificates', 'account']) {
    context.location.hash = '#' + page; run('render()'); assert.ok(app.innerHTML.includes('class="shell"'));
    // Every signed-in page has the light/dark switch in its header.
    assert.ok(app.innerHTML.includes('id="theme-toggle"')&&app.innerHTML.includes('Switch to dark mode'));
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

  // Full screen is required: a blocked request uses no attempt, and leaving full screen ends the attempt.
  context.document.hidden = false;
  const starts = () => requests.filter(r => r.path === 'learning/exam-start').length, startsBefore = starts();
  context.allowFullscreen = false; assert.equal(await run('startExam(0)'), false);
  assert.equal(starts(), startsBefore, 'No attempt is used when full screen is blocked.');
  assert.ok(run('examNotice').includes('full screen'));
  context.allowFullscreen = true; assert.equal(await run('startExam(0)'), true);
  assert.ok(context.document.fullscreenElement && app.innerHTML.includes('Stay in full screen'));
  context.document.fullscreenElement = null; docEvents.fullscreenchange[0]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(run('activeExam'), null);
  assert.equal(requests.filter(r => r.path === 'learning/exam-finish').at(-1).data.reason, 'Attempt terminated: you exited full screen.');
  console.log('PASS exams require full screen and leaving it terminates the attempt');

  context.document.hidden = false;
  const testAdmin={id:'admin-one',name:'Portal Admin',email:'admin@shimentox.com',role:'admin',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z',certificates:0,courseRuns:0,active:true};
  server.user=testAdmin;context.testAdmin=testAdmin;run('currentUser=testAdmin');await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');assert.ok(app.innerHTML.includes('ADMINISTRATOR WORKSPACE'));
  // Architecture: the admin opens on the Admin Dashboard and also has My Learning and Courses.
  assert.equal(context.document.title,'Admin Dashboard • ShimentoX');
  assert.equal(run('JSON.stringify(portalNavigation().slice(0,4).map(n=>n[2]))'),JSON.stringify(['Admin Dashboard','Training Compliance','My Learning','Courses']));
  context.location.hash='#courses';run('render()');assert.equal(context.document.title,'My Learning • ShimentoX');
  context.location.hash='#dashboard';run('render()');
  context.location.hash='#admin-users';run('render()');assert.ok(app.innerHTML.includes('id="create-candidate-form"'));
  assert.ok(app.innerHTML.includes('data-act="keka-sync"')&&app.innerHTML.includes('Sync from Keka'),'Admins bring Keka employees in with one click.');
  assert.ok(app.innerHTML.includes('Yearly training target')&&app.innerHTML.includes('<option value="all">All employees'),'Admins set a yearly target for everyone, a department or one employee.');
  const roleSelect=app.innerHTML.match(/<select id="new-candidate-role">(.*?)<\/select>/)[1];assert.deepEqual([...roleSelect.matchAll(/<option value="([^"]*)"/g)].map(m=>m[1]),['manager','employee'],'Employee and Manager are the roles that can be assigned.');
  element('new-candidate-name').value='New Learner';element('new-candidate-email').value='learner@shimentox.com';element('new-candidate-role').value='employee';element('new-candidate-password').value='Assigned123!';element('new-candidate-target').value='30';
  // Existing employees get a target box in their own row; new employees can get one on the Add employee form.
  assert.ok(app.innerHTML.includes('value="user:existing-one"')&&app.innerHTML.includes('3 hours completed in 2026'));
  await element('create-candidate-form').onsubmit({preventDefault(){}});
  assert.ok(requests.some(r=>r.path==='manage/training-targets'&&r.data.employeeIds[0]==='new-account'&&r.data.hours===30));
  assert.ok(app.innerHTML.includes('with a yearly training target of 30 hours'));
  assert.ok(requests.some(r=>r.path==='admin/candidates'&&r.data.email==='learner@shimentox.com'&&r.data.role==='employee'));
  assert.ok(app.innerHTML.includes('Share these credentials'));
  // Create a course from a link: the choice, the form, live progress, and failures shown on the form.
  context.location.hash='#admin-courses';run("courseAddMode='choose';render()");
  assert.ok(app.innerHTML.includes('data-import="generate-open"')&&app.innerHTML.includes('Create from a link with AI'));
  run("courseAddMode='generate';generateState=newGenerateState();render()");await new Promise(resolve=>setImmediate(resolve));run('render()');
  assert.ok(app.innerHTML.includes('id="generate-form"')&&app.innerHTML.includes('Choose automatically')&&app.innerHTML.includes('>Create course<'));
  run("generateState.busy=true;generateState.stage='writing';render()");
  assert.ok(app.innerHTML.includes('Writing the lessons and assessments')&&!app.innerHTML.includes('>Create course<'));
  await run("handleCourseJob(generateState,{status:'failed',error:'Not enough readable text'})");
  assert.ok(app.innerHTML.includes('Not enough readable text')&&app.innerHTML.includes('>Create course<'));
  run("courseAddMode=null;generateState=null");
  // The builder keeps "10 questions drawn from a bank of 15" when a course is saved, and sends nothing extra otherwise.
  const builderDraft=(count,size)=>`courseDraft=draftFromBuilder({course:{id:'c',title:'T',category:'C',description:'D'},lessons:[],assessment:{title:'A',passPercent:70,maxAttempts:3,timeLimitMinutes:20,questionCount:${count},questions:Array.from({length:${size}},()=>['Q',['a','b'],0,''])}});builderPayload('draft').assessment.questionCount`;
  assert.equal(run(builderDraft(10,15)),10);
  assert.equal(run(builderDraft(15,15)),undefined);
  run('courseDraft=null');
  server.people=[{id:'emp-asha',name:'Asha Rao',email:'asha@shimentox.com',department:'Engineering',jobRole:'Developer'},{id:'emp-ravi',name:'Ravi Kumar',email:'ravi@shimentox.com',department:'Sales',jobRole:null}];delete context.pageCache;run("delete pageCache.people");
  context.confirm=()=>true;const settleUi=()=>new Promise(resolve=>setImmediate(resolve)),occurrences=text=>app.innerHTML.split(text).length-1;
  context.location.hash='#admin-courses';run('render()');await settleUi();run('render()');
  // Course Management opens on the catalogue: metrics, search, status filters, and Edit / Preview / Assign / More for each course.
  for(const text of ['Course catalogue','Total courses','Enrolled learners','data-row-search="courses"','data-act="catalog-status"','data-act="course-assign"','data-act="course-archive"','data-act="course-delete"','data-tab="assignments">Assign a Course<','>Reminders<','Course Management'])assert.ok(app.innerHTML.includes(text),text);
  assert.ok(!app.innerHTML.includes('id="course-builder"'),'The wizard opens only when a course is created or edited.');
  run(`catalogFilters.status='draft';render()`);assert.ok(app.innerHTML.includes('No courses match these filters.'));run(`catalogFilters.status='all'`);
  run(`adminState.courses.push({...adminState.courses[0],id:'draft-1',title:'Draft Course',status:'draft',format:'lessons'});render()`);
  assert.ok(app.innerHTML.includes('data-act="course-assign" data-id="draft-1" disabled'),'Only published courses can be assigned.');
  run(`ACTIONS['course-assign']({dataset:{id:'draft-1'}})`);assert.equal(run('courseTab'),'catalog');run('adminState.courses.pop()');
  // Create Course is a 4-step wizard that shows only the current step and keeps entered data between steps.
  run('startNewCourse()');
  assert.ok(app.innerHTML.includes('id="course-builder"')&&app.innerHTML.includes('Step 1 of 4')&&app.innerHTML.includes('id="b-title"')&&!app.innerHTML.includes('+ Add lesson')&&!app.innerHTML.includes('Publication status')&&!app.innerHTML.includes('Course catalogue'));
  for(const label of ['Course basics','Learning materials','Assessment','Review &amp; publish','b-trainer','b-visibility','b-department','b-duration','b-difficulty','b-category'])assert.ok(app.innerHTML.includes(label),label);
  run(`courseDraft.title='Security Basics';courseDraft.description='Stay safe';BUILDER_ACTIONS.step({dataset:{step:'2'}});render()`);
  assert.ok(app.innerHTML.includes('+ Add lesson')&&app.innerHTML.includes('+ Add module')&&app.innerHTML.includes('Add an official learning source')&&!app.innerHTML.includes('id="b-title"'));
  run(`courseDraft.lessons[0].title='Passwords';courseDraft.lessons[0].content='Use a manager.';courseDraft.lessons[0].moduleTitle='Module 1: Basics';BUILDER_ACTIONS['lesson-add']();BUILDER_ACTIONS['module-add']();render()`);
  assert.equal(run('courseDraft.lessons[1].moduleTitle'),'Module 1: Basics');assert.equal(run('courseDraft.lessons[2].moduleTitle'),'Module 2');
  assert.equal(occurrences('class="module-heading"'),2);
  run(`BUILDER_ACTIONS.step({dataset:{step:'1'}});render()`);assert.ok(app.innerHTML.includes('value="Security Basics"'),'Step 1 keeps what was entered.');
  // Lessons left empty are not sent with a draft; each lesson carries its module name.
  assert.deepEqual(JSON.parse(run(`JSON.stringify(builderPayload('draft'))`)).lessons.map(l=>[l.title,l.moduleTitle]),[['Passwords','Module 1: Basics']]);
  // Save draft works on any step and stays on it.
  run('builderStep=2');await run(`BUILDER_ACTIONS.save()`);
  assert.ok(requests.some(r=>r.path==='admin/courses'&&r.data.status==='draft'&&r.data.title==='Security Basics'));
  assert.equal(run('builderStep'),2);assert.ok(app.innerHTML.includes('is saved as a draft'));assert.equal(run('builderDirty'),false);
  // Review & publish: checklist, preview and Publish. Publishing then offers Assign now or a return to Course Management.
  run(`BUILDER_ACTIONS.step({dataset:{step:'4'}});render()`);
  assert.ok(app.innerHTML.includes('Publishing checklist')&&app.innerHTML.includes('Course preview')&&app.innerHTML.includes('data-builder="publish"')&&app.innerHTML.includes('LESSON 1 OF 1'));
  await run(`BUILDER_ACTIONS.publish()`);
  assert.ok(requests.some(r=>r.path==='admin/courses'&&r.data.status==='published'&&r.data.id==='new-course'));
  assert.ok(app.innerHTML.includes('is published')&&app.innerHTML.includes('data-act="published-assign"')&&app.innerHTML.includes('Back to Course Management'));
  // Assign now opens Assign a Course with the course selected: breadcrumb, form, live summary and rules, then the records.
  run(`ACTIONS['published-assign']()`);await settleUi();run('render()');
  assert.equal(run('courseTab'),'assignments');assert.equal(run('courseDraft'),null);
  for(const text of ['Manage Courses</button><span aria-hidden="true">›</span><span aria-current="page">Assign a Course','<h1>Assign a Course</h1>','Assign training to employees and manage completion deadlines.','Course and Audience','Deadline and Requirement','Additional Information','Assignment Summary','Assignment Rules','Only published courses can be assigned.','If the target already has this course, the assignment is updated, not duplicated.','data-act="assign-clear"','Deadline date and time (IST)','Requires a deadline','Deadline optional'])assert.ok(app.innerHTML.includes(text),text);
  assert.ok(!app.innerHTML.includes('<h1>Course management</h1>')&&!app.innerHTML.includes('class="workflow course-flow"'),'The assign page replaces the Manage Courses intro.');
  assert.ok(app.innerHTML.includes('<option value="new-course" selected>')&&!app.innerHTML.includes('<option value="draft-1"'),'Only published courses are offered.');
  // Individual employee: a searchable list of real people; the summary shows placeholders until something is chosen.
  assert.ok(app.innerHTML.includes('id="assign-target" type="search"')&&app.innerHTML.includes('<option value="Asha Rao (asha@shimentox.com)">Engineering · Developer</option>'));
  assert.equal(occurrences('Not selected'),1);
  const summary={innerHTML:''};const realGet=context.document.getElementById;context.document.getElementById=id=>id==='assign-summary'?summary:realGet(id);
  const typed=(name,value,type)=>({name,value,type,closest:()=>true});
  context.typed=typed;run(`assignInput(typed('targetText','Asha Rao (asha@shimentox.com)'))`);
  assert.equal(run('assignDraft.targetId'),'emp-asha');assert.ok(summary.innerHTML.includes('Asha Rao (asha@shimentox.com)'),'The summary updates without a re-render.');
  run(`assignInput(typed('deadline','2099-02-01T17:30'));assignInput(typed('requirement','mandatory'))`);
  assert.ok(summary.innerHTML.includes('01-02-2099 17:30')&&summary.innerHTML.includes('MANDATORY'));
  run(`assignInput(typed('targetText','Asha'))`);assert.equal(run('assignDraft.targetId'),'','Partial text is not a selection.');
  context.document.getElementById=realGet;
  // Clear resets the form without submitting.
  const sentBefore=requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').length;
  run(`ACTIONS['assign-clear']()`);assert.deepEqual(JSON.parse(run('JSON.stringify(assignDraft)')),{targetType:'employee',targetId:'',targetText:'',deadline:'',mandatory:false,note:''});
  assert.equal(requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').length,sentBefore);
  // Department: the selector changes with the type.
  run(`CHANGES['assign-type']({value:'department'})`);await settleUi();run('render()');
assert.ok(app.innerHTML.includes('Select a department…')&&app.innerHTML.includes('Engineering · 5 employees')&&app.innerHTML.includes('including employees who join it later')&&!app.innerHTML.includes('id="assign-target" type="search"'));
  // Mandatory training needs a deadline; assigning a target that already has the course updates it after confirmation.
  context.testForm={dataset:{course:'new-course'},querySelector:()=>null};
  run(`assignDraft.targetId='d1';assignDraft.mandatory=true;assignDraft.note='Annual refresher'`);
  await run(`SUBMITS['course-assign'](testForm)`);assert.ok(toast.textContent.includes('needs a deadline'));
  const assignCalls=requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').length;
  run(`assignDraft.deadline='2099-02-01T17:30'`);context.confirm=()=>false;await run(`SUBMITS['course-assign'](testForm)`);
  assert.equal(requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').length,assignCalls,'Cancelled: no request.');
  context.confirm=()=>true;await run(`SUBMITS['course-assign'](testForm)`);
  assert.deepEqual(requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').at(-1).data,{courseId:'new-course',targetType:'department',targetId:'d1',mandatory:true,deadline:'2099-02-01T17:30',note:'Annual refresher'});
  assert.ok(app.innerHTML.includes('assignment updated for Engineering'));assert.equal(run('assignDraft.targetId'),'');
  // Individual employee assignment sends the chosen person's ID.
  run(`assignDraft={...newAssignDraft(),targetText:'Ravi Kumar (ravi@shimentox.com)',targetId:'emp-ravi'}`);await run(`SUBMITS['course-assign'](testForm)`);
  assert.deepEqual(requests.filter(r=>r.path==='manage/assignments'&&r.options.method==='POST').at(-1).data,{courseId:'new-course',targetType:'employee',targetId:'emp-ravi',mandatory:false,deadline:null,note:''});
  assert.ok(app.innerHTML.includes('assigned to Ravi Kumar (ravi@shimentox.com)'));
  // Records, tab 1: real assignment records with Update and Remove, filters and pagination.
  await settleUi();run('render()');
  for(const text of ['Assignments</button>','Employee Deadlines</button>','Reminder History</button>','<th>Assigned to</th><th>Course</th><th>Assigned</th><th>Deadline</th><th>Requirement</th><th>Progress</th><th>Status</th><th>Actions</th>','data-act="assignment-delete"','<summary>Update</summary>','1 of 5 completed'])assert.ok(app.innerHTML.includes(text),text);
  assert.equal(occurrences('<summary>Update</summary>'),10,'Ten per page.');assert.ok(app.innerHTML.includes('Showing 1–10 of 13'));
  run(`ACTIONS['records-page']({dataset:{page:'2'}})`);assert.equal(occurrences('<summary>Update</summary>'),3);
  run(`CHANGES['records-filter']({dataset:{field:'requirement'},value:'mandatory'})`);assert.equal(occurrences('<summary>Update</summary>'),1);assert.equal(run('assignRecords.page'),1);
  run(`assignRecords.requirement='';assignRecords.q='team 1';render()`);assert.ok(app.innerHTML.includes('Team 12')&&!app.innerHTML.includes('Engineering</strong>'));run(`assignRecords.q=''`);
  // Tab 2: employee deadlines from Training Compliance, filtered and paged on the server.
  run(`ACTIONS['records-tab']({dataset:{tab:'deadlines'}})`);await settleUi();run('render()');
  assert.ok(requests.some(r=>r.path.startsWith('manage/compliance?')&&r.path.includes('page=1')&&r.path.includes('size=10')));
  assert.ok(app.innerHTML.includes('<th>Employee</th><th>Course</th><th>Deadline</th><th>Assignment type</th><th>Progress</th><th>Status</th><th>Actions</th>')&&app.innerHTML.includes('<summary>Change</summary>')&&app.innerHTML.includes('data-type="employee" data-target="11111111-2222-3333-4444-555555555555"'));
  run(`CHANGES['records-filter']({dataset:{field:'status'},value:'overdue'})`);await settleUi();assert.ok(requests.some(r=>r.path.startsWith('manage/compliance?')&&r.path.includes('status=overdue')));
  // Tab 3: reminder history with delivery status.
  run(`ACTIONS['records-tab']({dataset:{tab:'reminders'}})`);await settleUi();run('render()');
  assert.ok(app.innerHTML.includes('3 days before')&&app.innerHTML.includes('Mailbox &lt;full&gt;')&&!app.innerHTML.includes('data-field="requirement"'));
  run(`CHANGES['records-filter']({dataset:{field:'status'},value:'failed'})`);assert.ok(!app.innerHTML.includes('3 days before')&&app.innerHTML.includes('Mailbox'));
  run(`assignRecords={tab:'assignments',q:'',course:'',status:'',requirement:'',page:1}`);
  // Reminders: settings and history in their own Manage Courses tab, filtered by course and delivery status.
  run(`ACTIONS['course-tab']({dataset:{tab:'reminders'}})`);await settleUi();run('render()');
  assert.ok(app.innerHTML.includes('Reminder settings')&&app.innerHTML.includes('Reminder history')&&app.innerHTML.includes('3 days before')&&!app.innerHTML.includes('id="assign-form"'));
  run(`reminderFilters.status='failed';render()`);assert.ok(!app.innerHTML.includes('3 days before')&&app.innerHTML.includes('Mailbox'));
  run(`CHANGES['reminder-course']({value:'python-programming'})`);await settleUi();assert.ok(requests.some(r=>r.path==='manage/reminders/history?courseId=python-programming'));run(`reminderFilters={course:'',status:''}`);
  // More → Archive keeps records; the 3-module editor opens with a way back.
  run(`ACTIONS['course-tab']({dataset:{tab:'catalog'}})`);await run(`ACTIONS['course-archive']({dataset:{id:'new-course'}})`);assert.ok(requests.some(r=>r.path==='admin/courses/new-course/archive'));
  run(`editingCourse='python-programming';courseDraft=null;render()`);assert.ok(app.innerHTML.includes('id="course-editor-form"')&&app.innerHTML.includes('Back to Course Management'));
  run(`ACTIONS['course-close']()`);assert.ok(app.innerHTML.includes('Course catalogue')&&!app.innerHTML.includes('id="course-editor-form"'));
  // Add a course offers manual creation and Create from a link with AI; the old Import from URL option is gone.
  run(`IMPORT_ACTIONS.choose();render()`);assert.ok(app.innerHTML.includes('Create manually')&&app.innerHTML.includes('Create from a link with AI')&&!app.innerHTML.includes('Import from URL'));
  assert.equal(run("typeof courseImporter+typeof runCourseImport"),'undefinedundefined');
  run(`IMPORT_ACTIONS.close();render()`);assert.ok(!app.innerHTML.includes('id="course-builder"')&&app.innerHTML.includes('Course catalogue'));
  // Earlier builder rules still hold: publishing needs lesson material, and the preview embeds the lesson video.
  run(`startNewCourse();courseDraft.title='GenAI Foundations';courseDraft.description='Intro';courseDraft.lessons[0].title='What is GenAI?'`);
  assert.ok(run('publishProblems().some(p=>p.includes("needs a video, document"))'),'Publishing requires lesson material');
  run(`courseDraft.lessons[0].videoUrl='https://youtu.be/dQw4w9WgXcQ';courseDraft.lessons.push(newLesson());courseDraft.lessons[1].title='Prompting';courseDraft.lessons[1].content='Be specific.';courseDraft.assessment=newAssessment();Object.assign(courseDraft.assessment.questions[0],{prompt:'Pick one',options:['A','B'],correct:1});`);
  assert.equal(run('publishProblems().length'),0);
  const builderBody=JSON.parse(run(`JSON.stringify(builderPayload('draft'))`));
  assert.equal(builderBody.format,'lessons');assert.equal(builderBody.status,'draft');
  assert.deepEqual(builderBody.lessons.map(l=>l.title),['What is GenAI?','Prompting']);
  assert.deepEqual(builderBody.assessment.questions[0],{prompt:'Pick one',options:['A','B'],correct:1,explanation:''});
  run('builderStep=4;render()');assert.ok(app.innerHTML.includes('LESSON 1 OF 2')&&app.innerHTML.includes('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'));
  run('closeCourseEditor();resetCourseManagement()');server.savedCourse=null;server.people=null;run("delete pageCache.people");
  console.log('PASS Manage Courses workflow: catalogue, 4-step wizard, draft and publish, assignment, progress filters, reminders');
  // The extended lesson formatting keeps nested lists and code.
  assert.ok(run("renderMarkdown('- one\\n  - nested\\n\\n```python\\nx=1\\n```')").includes('<ul><li>one<ul><li>nested</li></ul></li></ul>'));
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
  assert.ok(app.innerHTML.includes('SQL Foundations')&&app.innerHTML.includes('Builds on Data Analytics courses you have completed.'));
  assert.ok(app.innerHTML.includes('Engineering · Manager: Line Manager')||app.innerHTML.includes('Data Analyst · Engineering'));
  assert.ok(!app.innerHTML.includes('href="#admin-users"')&&!app.innerHTML.includes('href="#reports"'));
  assert.equal(run('notificationState.unread'),1);assert.ok(app.innerHTML.includes('class="notification-count"'));
  context.location.hash='#course';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Learning materials')&&app.innerHTML.includes('has not been enabled'));
  assert.ok(app.innerHTML.includes('MODULE 1'));
  context.location.hash='#reports';run('render()');assert.ok(!app.innerHTML.includes('Export CSV'));
  context.location.hash='#dashboard';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Training hours 2026')&&app.innerHTML.includes('12 of 30 hours in 2026')&&app.innerHTML.includes('18 hours to go')&&app.innerHTML.includes('width:40%'),'The employee sees a bar of hours completed against the yearly target.');
  console.log('PASS employee dashboard, assignments, recommendations, notifications, course resources, assistant state');

  // A running knowledge check or final assessment replaces the course page: only the questions are shown in full screen.
  context.location.hash='#course';
  run(`currentCourseExtras.assessments=[{id:'check-1',title:'Knowledge check: Lesson one',kind:'knowledge',passPercent:70,attemptsLeft:2}];
    inlineAttempt={assessmentId:'check-1',attempt:{id:'attempt-1',attemptNumber:1,deadline:Date.now()+600000,questions:[{id:'q1',prompt:'Which rule applies?',code:'',options:['Full screen','None']}]}};render()`);
  assert.ok(app.innerHTML.includes('class="exam-focus"')&&app.innerHTML.includes('Which rule applies?')&&app.innerHTML.includes('KNOWLEDGE CHECK · ATTEMPT 1'));
  assert.ok(!app.innerHTML.includes('Learning materials')&&!app.innerHTML.includes('MODULE 1'),'No course content is shown during the attempt.');
  context.document.fullscreenElement=null;docEvents.fullscreenchange[0]();
  assert.equal(run('inlineAttempt'),null);
  assert.ok(app.innerHTML.includes('MODULE 1'),'The course page returns once the attempt ends.');
  await new Promise(resolve=>setImmediate(resolve));
  console.log('PASS knowledge checks open on their own in full screen, without the course content');
  for(const [role,expected] of [['manager','Team Reports'],['trainer','Manage Courses'],['hr','Users & Teams']]){context.roleUser={...server.user,role};run('currentUser=roleUser');assert.ok(run('portalNavigation().map(n=>n[2])').includes(expected),role);}
  run('currentUser=roleUser;currentUser.role="trainer"');assert.ok(!run('portalNavigation().map(n=>n[0])').includes('admin-users'));
  // Architecture: a manager opens on the Manager View (their team's progress) and also has My Learning.
  context.mgrUser={...server.user,role:'manager'};run('currentUser=mgrUser');
  assert.equal(run('JSON.stringify(portalNavigation().slice(0,2).map(n=>n[2]))'),JSON.stringify(['Manager View','My Learning']));
  assert.equal(run('homePage()'),'dashboard');
  context.location.hash='#dashboard';run('render()');await new Promise(resolve=>setImmediate(resolve));run('render()');
  assert.equal(context.document.title,'Manager View • ShimentoX');
  assert.ok(app.innerHTML.includes('MANAGER WORKSPACE')&&app.innerHTML.includes('Direct reports')&&!app.innerHTML.includes('Welcome back'));
  assert.ok(app.innerHTML.includes('Team training hours 2026')&&app.innerHTML.includes('Team Report')&&app.innerHTML.includes('5 of 20 hours in 2026')&&app.innerHTML.includes('data-form="training-target"'),'The manager sees and sets the yearly target for each report.');
  context.adminUser={...testAdmin};run('currentUser=adminUser');await run('loadCandidate()');
  context.location.hash='#dashboard';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Total employees')&&app.innerHTML.includes('>12<')&&app.innerHTML.includes('42%'));
  assert.ok(app.innerHTML.includes('Department-wise training')&&app.innerHTML.includes('Late Learner')&&app.innerHTML.includes('Security Awareness'));
  context.location.hash='#reports';run('render()');await new Promise(resolve=>setImmediate(resolve));
  assert.ok(app.innerHTML.includes('Export CSV')&&app.innerHTML.includes('=HYPERLINK(&quot;x&quot;)'));
  // Training compliance: figures come from the API, filters and sorting reach the server, values are escaped, and roles are kept apart.
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  context.location.hash='#compliance';run('render()');await settle();
  for(const text of ['Training Compliance &amp; Deadline Monitoring','Last updated: 5 November 2026, 11:00 AM IST','Export Report','Export CSV','Export Excel','Overview','Employee Progress','Department Compliance','Overdue Training','Total Assignments','Completed On Time','Completed Late','Overall Completion Rate','20%','Department-wise Compliance','Training Status Distribution','Overdue Courses (1)','3 days overdue','View All','Employee Training Records','Due Soon','data-act="compliance-sort"','data-act="compliance-details"','Rows per page'])assert.ok(app.innerHTML.includes(text),text);
  assert.ok(app.innerHTML.includes('Asha &lt;i&gt;')&&app.innerHTML.includes('Sales &lt;b&gt;')&&!app.innerHTML.includes('Sales <b>'));
  assert.ok(app.innerHTML.includes('11111111…'),'Long IDs are shortened in the table.');
  assert.equal(run('portalNavigation()[1][0]'),'compliance','Directly under the Admin Dashboard.');
  // Every tab shows real content and keeps the filters.
  for(const [tab,text] of [['employees','Employee Training Records'],['departments','Assigned courses by status'],['overdue','No activity yet'],['reports','Other learning reports'],['overview','Training Status Distribution']]){run(`compliance.tab='${tab}';render()`);assert.ok(app.innerHTML.includes(text),tab);assert.ok(app.innerHTML.includes('Apply Filters'),tab);}
  // Details open from the row.
  run(`compliance.open='11111111-2222-3333-4444-555555555555|c1';render()`);assert.ok(app.innerHTML.includes('asha@shimentox.com')&&app.innerHTML.includes('Manage deadline'));run('compliance.open=null');
  run(`compliance.filters={department:'d1',status:'overdue'};compliance.sort={key:'deadline',dir:'desc'};render()`);await settle();
  assert.ok(requests.some(r=>r.path.startsWith('manage/compliance?')&&['department=d1','status=overdue','sort=deadline','dir=desc','size=10'].every(part=>r.path.includes(part))));
  assert.ok(app.innerHTML.includes('<option value="d1" selected>Finance</option>'),'The chosen filter stays selected.');
  assert.ok(app.innerHTML.includes('Department: <b>Finance</b>')&&app.innerHTML.includes('Status: <b>Overdue</b>'),'Active filters are shown.');
  run('compliance=COMPLIANCE_DEFAULTS()');
  for(const [role,visible] of [['hr',true],['manager',true],['trainer',false],['employee',false]]){context.roleUser={...testAdmin,role};run('currentUser=roleUser');assert.equal(run("portalNavigation().some(n=>n[0]==='compliance')"),visible,role);assert.equal(run("resolvePage('compliance')")==='compliance',visible,role);}
  context.adminUser={...testAdmin};run('currentUser=adminUser');
  // Onboarding: the employee's plan in My Learning and on the dashboard, and the HR and manager pages.
  const plan={id:'o1',template:'Engineering',status:'in_progress',statusLabel:'In progress',percent:50,mandatoryDone:1,mandatoryTotal:2,optionalDone:0,optionalTotal:1,overdueMandatory:0,startDate:'2026-11-01',startedAt:'2026-11-01T05:00:00Z',source:'automatic',completedDisplay:null,
    nextMilestone:{day:30,title:'Day 30',date:'2026-11-30',state:'upcoming',mandatoryTotal:1,mandatoryDone:0},milestones:[{day:1,title:'Day 1',date:'2026-11-01',deadlineDisplay:'1 November 2026, 11:59 PM',state:'completed',mandatoryTotal:1,mandatoryDone:1},{day:30,title:'Day 30 <i>',date:'2026-11-30',deadlineDisplay:'30 November 2026, 11:59 PM',state:'upcoming',mandatoryTotal:1,mandatoryDone:0}],
    courses:[{courseId:'python-programming',title:'Welcome <s>',day:1,mandatory:true,link:'created',note:'',status:'completed_on_time',statusLabel:'Completed On Time',progress:100,completed:true,deadlineDisplay:'1 November 2026, 11:59 PM',dueSoon:false,assessment:{label:'3 of 3 module exams passed',passed:true}},
      {courseId:'c2',title:'Security',day:30,mandatory:true,link:'existing',note:'Already assigned',status:'in_progress',statusLabel:'In Progress',progress:40,completed:false,deadlineDisplay:'30 November 2026, 11:59 PM',dueSoon:true,assessment:null},
      {courseId:'c3',title:'Extras',day:30,mandatory:false,link:'created',note:'',status:'not_started',statusLabel:'Not Started',progress:0,completed:false,deadlineDisplay:null,dueSoon:false,assessment:null}]};
  server.plan=plan;server.onboarding=plan;
  context.learnerUser={...testAdmin,role:'employee'};run('currentUser=learnerUser;pageCache={}');
  context.location.hash='#courses';run('render()');await settle();
  for(const text of ['Your onboarding: Engineering','50%','1 of 2 mandatory courses','0 of 1 optional','Day 30 &lt;i&gt;','Welcome &lt;s&gt;','3 of 3 module exams passed','Already assigned to you','Due Soon','No deadline','data-open-course="python-programming"'])assert.ok(app.innerHTML.includes(text),text);
  assert.ok(!app.innerHTML.includes('Welcome <s>'));
  context.location.hash='#dashboard';run('pageCache={};render()');await settle();
  assert.ok(app.innerHTML.includes('Your onboarding: Engineering')&&app.innerHTML.includes('Open in My Learning'),'A compact plan on My Dashboard.');
  server.onboarding=null;run('pageCache={}');context.location.hash='#courses';run('render()');await settle();
  assert.ok(!app.innerHTML.includes('Your onboarding'),'Nothing is shown without onboarding.');
  run('currentUser=adminUser;pageCache={}');context.location.hash='#onboarding';run('render()');await settle();
  for(const text of ['Employee Onboarding','Currently onboarding','Overdue mandatory courses','58%','Progress by department','Asha &lt;b&gt;','1 of 2 mandatory','Day 30','Needs onboarding','Templates','data-act="onb-export"'])assert.ok(app.innerHTML.includes(text),text);
  run(`onb.open='o1';render()`);await settle();assert.ok(app.innerHTML.includes('Cancel onboarding')&&app.innerHTML.includes('Started automatically'));
  run(`onb.tab='waiting';onb.open=null;render()`);await settle();assert.ok(app.innerHTML.includes('No matching template')&&app.innerHTML.includes('value="2026-11-11"'));
  run(`onb.tab='templates';render()`);await settle();assert.ok(app.innerHTML.includes('Engineering &lt;x&gt;')&&app.innerHTML.includes('is not published')&&app.innerHTML.includes('+ New template'));
  run(`ACTIONS['onb-template-new']()`);assert.ok(app.innerHTML.includes('New onboarding template')&&app.innerHTML.includes('Save and activate'));
  run(`ACTIONS['onb-milestone-presets']()`);assert.ok(['Day 60','Day 90'].every(t=>app.innerHTML.includes(t)));
  run(`onb=onbDefaults()`);
  for(const [role,visible,label] of [['hr',true,'Onboarding'],['manager',true,'Team Onboarding'],['trainer',false],['employee',false]]){context.roleUser={...testAdmin,role};run('currentUser=roleUser');assert.equal(run("portalNavigation().some(n=>n[0]==='onboarding')"),visible,role);if(label)assert.equal(run("portalNavigation().find(n=>n[0]==='onboarding')[2]"),label);}
  context.roleUser={...testAdmin,role:'manager'};run('currentUser=roleUser;pageCache={}');context.location.hash='#onboarding';run('render()');await settle();
  assert.ok(app.innerHTML.includes('Team Onboarding')&&!app.innerHTML.includes('Needs onboarding')&&!app.innerHTML.includes('Cancel onboarding'));
  context.adminUser={...testAdmin};run('currentUser=adminUser;pageCache={}');
  const csv=run(`toCSV([{key:'a',label:'Name'},{key:'b',label:'Note'}],[{a:'=SUM(A1)',b:'Hello, "team"'}])`);
  assert.equal(csv.split('\r\n')[1],`'=SUM(A1),"Hello, ""team"""`);
  // Learning paths, skills and goals were removed from the admin screens as well.
  assert.ok(!run("REPORT_TYPES.some(([type])=>type==='skills')"),'No skill-gap report.');
  assert.ok(!run("Object.values(ROLE_NAV).flat().some(item=>['paths','skills'].includes(item[0]))"),'No role has Learning Paths or Skills in the sidebar.');
  assert.ok(!app.innerHTML.includes('learning plans')&&!app.innerHTML.includes('Skills developed'));
  console.log('PASS role navigation, organisation dashboard metrics, reports and safe CSV export');

  // Learning activity history: the employee timeline, and the staff dashboard, drill-down and analytics.
  context.employeeUser={...testAdmin,role:'employee'};run('currentUser=employeeUser;pageCache={};resetActivity()');context.location.hash='#history';run('render()');await settle();
  assert.equal(context.document.title,'Learning history • ShimentoX');
  assert.ok(app.innerHTML.includes('activity-timeline')&&app.innerHTML.includes('Assessment passed')&&app.innerHTML.includes('Module exam · 100% · pass mark 75%'));
  assert.ok(app.innerHTML.includes('Security &lt;b&gt;')&&!app.innerHTML.includes('Security <b>'),'Course names are escaped.');
  assert.ok(app.innerHTML.includes('From earlier records')&&app.innerHTML.includes('Attended sessions')&&app.innerHTML.includes('data-form="history-filters"'));
  requests.length=0;run(`myHistory={filters:nonEmpty({course:'c1',type:'assessment',from:'2026-11-01',to:''}),page:1};render()`);await settle();
  assert.ok(requests.some(r=>r.path==='me/history?course=c1&type=assessment&from=2026-11-01&page=1'),'Filters are sent to the server and empty ones are dropped.');
  server.historyTotal=25;run(`resetActivity();pageCache={};render()`);await settle();
  requests.length=0;run(`ACTIONS['history-page']({dataset:{page:'2'}})`);await settle();assert.ok(requests.some(r=>r.path==='me/history?page=2'));
  server.historyTotal=0;run(`resetActivity();pageCache={};render()`);await settle();assert.ok(app.innerHTML.includes('No learning activity yet'));delete server.historyTotal;
  assert.ok(!run("portalNavigation().some(n=>n[0]==='learning-activity')"),'Employees have no staff activity page.');
  context.location.hash='#learning-activity';run('render()');assert.equal(context.document.title,'My Learning • ShimentoX','Employees are sent home from the staff page.');
  for(const [role,label] of [['admin','Learning Activity'],['hr','Learning Activity'],['manager','Team Activity']]){context.roleUser={...testAdmin,role};run('currentUser=roleUser');assert.equal(run("portalNavigation().find(n=>n[0]==='learning-activity')?.[2]"),label);}
  for(const role of ['trainer','employee']){context.roleUser={...testAdmin,role};run('currentUser=roleUser');assert.ok(!run("portalNavigation().some(n=>n[0]==='learning-activity')"));}
  context.adminUser={...testAdmin};run('currentUser=adminUser;pageCache={};resetActivity()');context.location.hash='#learning-activity';run('render()');await settle();
  for(const text of ['Learning activities','Active learners','Courses accessed','Lessons completed','Assessments attempted','Courses completed','<th>Department</th>','<th>Job role</th>','<th>Course progress</th>','<th>Assessment result</th>','EMP-7','Analyst','FAILED','Latest activity','not a measure of productivity'])assert.ok(app.innerHTML.includes(text),text);
  assert.ok(app.innerHTML.includes('Asha &lt;i&gt;')&&!app.innerHTML.includes('Asha <i>'));
  requests.length=0;run(`actv.filters=nonEmpty({q:'as',employee:'',department:'d1',jobRole:'j1',course:'',type:'assessment_failed',from:'2026-11-01',to:'2026-11-10'});actv.page=1;render()`);await settle();
  assert.ok(requests.some(r=>r.path==='manage/activity?q=as&department=d1&jobRole=j1&type=assessment_failed&from=2026-11-01&to=2026-11-10&page=1'));
  run(`ACTIONS['actv-employee']({dataset:{id:'e1'}})`);await settle();
  assert.ok(app.innerHTML.includes('EMPLOYEE HISTORY')&&app.innerHTML.includes('Course completed')&&app.innerHTML.includes('Back to all activity'));
  run(`ACTIONS['actv-tab']({dataset:{tab:'analytics'}})`);await settle();
  for(const text of ['Most accessed courses','Most completed courses','Courses with high abandonment','Lesson completion patterns','Assessment attempt rates','Assessment pass and failure rates','No learning activity for 30 days','Department engagement','weekday-bars','Never','67%'])assert.ok(app.innerHTML.includes(text),text);
  // Opening a course material is reported to the server without blocking the link.
  requests.length=0;const link={closest:sel=>sel==='[data-resource-open]'?{dataset:{resourceOpen:'r1'}}:null};
  for(const handler of docEvents.click||[])try{handler({target:link,preventDefault(){}});}catch{}
  await settle();assert.ok(requests.some(r=>r.path==='me/resources/r1/open'));
  run('currentUser=adminUser;pageCache={};resetActivity()');
  console.log('PASS learning activity timeline, staff activity dashboard, drill-down, analytics and resource tracking');
  // A backend process started before an update reports an older (or no) API version: all users get a clear version-mismatch message.
  server.apiVersion=null;server.user={...testAdmin};server.setupRequired=false;await run('initializePortal()');
  assert.equal(run('serverOutdated'),true);
  context.location.hash='#calendar';run('render()');assert.ok(app.innerHTML.includes('older version of the portal')&&app.innerHTML.includes('npm start'));
  context.empUser={id:'employee-one',name:'Sai Charan',email:'sai@shimentox.com',role:'employee',mustChangePassword:false,createdAt:'2026-10-22T00:00:00Z'};run('currentUser=empUser');run('render()');
  assert.ok(app.innerHTML.includes('browser and server versions do not match')&&!app.innerHTML.includes('npm start'));
  server.apiVersion=15;await run('initializePortal()');assert.equal(run('serverOutdated'),false);assert.ok(!app.innerHTML.includes('older version of the portal'));
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
