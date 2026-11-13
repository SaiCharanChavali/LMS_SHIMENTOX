// One portal shell; navigation and pages depend on the authenticated server role.
let adminState={stats:{},candidates:[],courses:[],events:[]};
let editingCourse=null,resetCandidate=null,adminMessage='',provisionedCredentials=null,recordPreview=null,kekaSyncResult=null;
// Manage Courses: the open tab, catalogue and assignment filters, the unsent assignment form, and the course just published.
let courseTab='catalog',catalogFilters={q:'',status:'all',category:''},assignDraft=null,reminderFilters={course:'',status:''},publishedCourse=null,builderDirty=false;
function resetCourseManagement(){courseTab='catalog';catalogFilters={q:'',status:'all',category:''};assignDraft=null;assignRecords={tab:'assignments',q:'',course:'',status:'',requirement:'',page:1};reminderFilters={course:'',status:''};publishedCourse=null;builderDirty=false;}

const LEARNER_NAV=[['dashboard','grid','My Dashboard'],['courses','play','My Learning'],['catalog','book','Courses'],['calendar','calendar','Training Calendar'],['certificates','award','My Certificates'],['account','user','My Profile']];
const ROLE_NAV={
  admin:[['dashboard','grid','Admin Dashboard'],['compliance','clock','Training Compliance'],['courses','play','My Learning'],['catalog','book','Courses'],['admin-courses','file','Manage Courses'],['admin-users','users','Users & Teams'],['onboarding','path','Onboarding'],['assessments','check','Assessments'],['calendar','calendar','Training Calendar'],['cert-records','award','Certificates'],['reports','chart','Reports & Analytics'],['learning-activity','path','Learning Activity'],['admin-audit','clock','Activity Log'],['account','user','My Profile']],
  hr:[['dashboard','grid','Dashboard'],['compliance','clock','Training Compliance'],['courses','play','My Learning'],['catalog','book','Courses'],['admin-courses','file','Manage Courses'],['admin-users','users','Users & Teams'],['onboarding','path','Onboarding'],['assessments','check','Assessments'],['calendar','calendar','Training Calendar'],['cert-records','award','Certificates'],['reports','chart','Reports & Analytics'],['learning-activity','path','Learning Activity'],['account','user','My Profile']],
  trainer:[...LEARNER_NAV,['MANAGE'],['admin-courses','file','Manage Courses'],['assessments','check','Assessments'],['reports','chart','Reports & Analytics']],
  manager:[['dashboard','users','Manager View'],...LEARNER_NAV.slice(1),['MY TEAM'],['compliance','clock','Team Compliance'],['onboarding','path','Team Onboarding'],['reports','chart','Team Reports'],['learning-activity','path','Team Activity']],
  // Employees open on My Learning, so it also leads their sidebar.
  employee:[LEARNER_NAV[1],LEARNER_NAV[2],LEARNER_NAV[0],...LEARNER_NAV.slice(3)],
};
const EXTRA_PAGES=['course','history','assessments','course-preview'];

// The first page after sign-in: My Learning for employees; the Admin Dashboard or Manager View for admins and managers.
function homePage(){return currentUser?.role==='employee'?'courses':'dashboard';}
function resolvePage(route){
  if(firstAdminSetup)return 'admin-setup';
  if(!currentUser)return 'login';
  if(currentUser.mustChangePassword)return 'password-setup';
  if(['home','login','logout',''].includes(route))return homePage();
  const allowed=portalNavigation().map(([href])=>href).concat(EXTRA_PAGES,['account','certificates','courses','catalog']);
  if(route==='course-preview'&&!can('courses.manage'))return homePage();
  return allowed.includes(route)?route:homePage();
}
function portalNavigation(){return (ROLE_NAV[currentUser.role]||LEARNER_NAV).filter(item=>item.length===3);}
function navigationGroups(){return ROLE_NAV[currentUser.role]||LEARNER_NAV;}
async function loadAdminState(){
  if(!currentUser||currentUser.role==='employee')return;
  const get=(allowed,path,fallback)=>allowed?api(path):Promise.resolve(fallback);
  const [overview,users,courses,audit]=await Promise.all([get(can('users.manage'),'admin/overview',{stats:{}}),get(can('users.manage'),'admin/candidates',{candidates:[]}),get(can('courses.manage'),'admin/courses',{courses:[]}),get(can('audit.view'),'admin/audit',{events:[]})]);
  adminState={stats:overview.stats,candidates:users.candidates,courses:courses.courses,events:audit.events};
}
function smallStats(items){return `<div class="stats">${items.map(([i,n,label])=>`<div class="stat"><div class="stat-icon">${icon(i)}</div><div><strong>${n}</strong><small>${label}</small></div></div>`).join('')}</div>`;}
// Learning areas group the configured course categories on the Courses page. A course's area follows from its
// category, so courses in new categories are placed automatically; anything unmatched is professional development.
const LEARNING_AREAS=[
  {id:'technical',filter:'Technical',badge:'Technical',title:'Technical',about:'Build skills in technology, software, AI and digital tools.'},
  {id:'professional',filter:'Non-Technical',badge:'Professional Development',title:'Non-Technical & Professional Development',about:'Build essential workplace and professional skills.'},
  {id:'recruitment',filter:'Recruitment & HR',badge:'Recruitment & HR',title:'Recruitment & HR',about:'Develop recruitment, talent and people-related skills.'},
  {id:'management',filter:'Management & Leadership',badge:'Management & Leadership',title:'Management & Leadership',about:'Develop leadership and management capabilities.'},
  {id:'compliance',filter:'Compliance & Security',badge:'Compliance & Security',title:'Compliance & Security',about:'Complete essential company policies, security and data protection training.'}];
// Checked in order: "Professional Development" is not technical, and "Time Management" is a professional skill.
const AREA_RULES=[['compliance',/complian|secur|privacy|protection|polic|posh|legal|safety|ethic/i],['recruitment',/recruit|talent|hiring|interview|onboard|human resources|\bhr\b/i],
  ['professional',/professional|communication|presentation|productivity|time management|problem.solving|agile|scrum|soft skill/i],['management',/manag|leader|strateg|conflict/i],
  ['technical',/technical|technology|development|software|engineer|program|coding|\bai\b|artificial|automation|machine learning|data|analytics|cloud|devops|digital/i]];
function learningArea(category){const id=(AREA_RULES.find(([,re])=>re.test(category||''))||['professional'])[0];return LEARNING_AREAS.find(a=>a.id===id);}
function catalogCard(item){
  const progress=item.completed?100:currentCourseInfo.id===item.id?pct():item.progress||0,a=item.assignment,area=learningArea(item.category);
  return `<article class="catalog-card" data-course-card="${esc((item.title+' '+item.category+' '+area.badge).toLowerCase())}"><div class="catalog-art">${icon('book')}<span>SHIMENTO X LEARNING</span></div><div class="catalog-body"><div class="tile-tags"><span class="tag" title="${esc(item.category)}">${esc(area.badge)}</span>${a?.mandatory?'<span class="tag warn">MANDATORY</span>':a?'<span class="tag gray">OPTIONAL</span>':''}${item.completed?'<span class="tag success">COMPLETED</span>':''}</div><h3>${esc(item.title)}</h3><p class="catalog-description">${esc(item.description)}</p><div class="catalog-footer"><div class="meta">${esc(capital(item.difficulty||'beginner'))} &middot; ${esc(fmtDuration(item.durationMinutes))} &middot; ${item.format==='lessons'?`${item.lessonCount||0} lesson${item.lessonCount===1?'':'s'}`:'3 modules &middot; 6 videos &middot; 3 exams'}</div>${deadlineBlock(item.deadline)}${a?.assignedBy?`<div class="meta">Assigned by ${esc(a.assignedBy)}</div>`:''}<div class="progress-label"><span>Course progress</span><b>${progress}%</b></div><div class="progress"><span style="width:${progress}%"></span></div><button class="btn" data-open-course="${esc(item.id)}">${item.completed?'Review course':progress?'Continue learning':'Start learning'} ${icon('arrow')}</button></div></div></article>`;
}
// My Learning lists the employee's assigned courses and those they have started or completed, nearest deadline first; the Courses page is the full catalog.
function myLearningPage(){
  const mine=courseCatalog.filter(c=>c.started||c.completed||c.assignment).sort((a,b)=>Number(a.completed)-Number(b.completed)||(a.deadline?.at||'9').localeCompare(b.deadline?.at||'9')||(b.lastActivity||'').localeCompare(a.lastActivity||''));
  const started=mine.filter(c=>c.started||c.completed).length,assigned=mine.length-started;
  return `${typeof onboardingSection==='function'?onboardingSection(false):''}<div class="intro"><div><h1>My Learning</h1><p>Your assigned courses, and the courses you have started or completed. Find new courses on the Courses page.</p></div><span class="tag">${started} STARTED${assigned?` · ${assigned} ASSIGNED`:''}</span></div><div class="filter-row"><input class="search" id="search" aria-label="Search my courses" placeholder="Search my courses..."><a class="btn secondary" href="#catalog">Browse all courses</a><a class="btn secondary" href="#history">Learning history</a></div><div class="course-grid">${mine.length?mine.map(catalogTile).join(''):'<div class="panel"><h3>You have not started a course yet</h3><p class="muted">Open a course from the Courses page, and it will appear here so you can continue where you left off.</p><a class="btn" href="#catalog">Browse courses</a></div>'}</div>`;
}
// ---------------------------------------------------------------- Courses page (company learning catalogue)
// Courses have no cover images, so each learning area has its own illustration in the ShimentoX palette (inline SVG:
// no image files, no external requests). Every card in an area looks alike, which keeps the grid consistent.
const COURSE_ART={
  technical:'<rect width="400" height="200" fill="#fff6dc"/><circle cx="345" cy="38" r="70" fill="#fdeaa8"/><circle cx="42" cy="178" r="46" fill="#fbe7b0"/><rect x="104" y="34" width="192" height="128" rx="12" fill="#263238"/><rect x="104" y="34" width="192" height="24" rx="12" fill="#37474f"/><rect x="104" y="48" width="192" height="10" fill="#37474f"/><circle cx="122" cy="46" r="4" fill="#fbc02d"/><circle cx="136" cy="46" r="4" fill="#f6e3a6"/><circle cx="150" cy="46" r="4" fill="#90a4ae"/><rect x="124" y="74" width="54" height="8" rx="4" fill="#fbc02d"/><rect x="186" y="74" width="70" height="8" rx="4" fill="#90a4ae"/><rect x="140" y="92" width="90" height="8" rx="4" fill="#f6e3a6"/><rect x="140" y="110" width="60" height="8" rx="4" fill="#fbc02d"/><rect x="208" y="110" width="44" height="8" rx="4" fill="#90a4ae"/><rect x="124" y="128" width="40" height="8" rx="4" fill="#f6e3a6"/><path d="M80 92l-16 16 16 16M320 92l16 16-16 16" fill="none" stroke="#e0a800" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
  professional:'<rect width="400" height="200" fill="#fff6dc"/><circle cx="60" cy="34" r="60" fill="#fdeaa8"/><circle cx="360" cy="180" r="56" fill="#fbe7b0"/><rect x="96" y="40" width="130" height="64" rx="16" fill="#263238"/><path d="M128 104l-6 20 24-20z" fill="#263238"/><rect x="114" y="60" width="80" height="8" rx="4" fill="#fbc02d"/><rect x="114" y="78" width="54" height="8" rx="4" fill="#90a4ae"/><rect x="188" y="88" width="124" height="60" rx="16" fill="#fbc02d"/><path d="M286 148l8 20-26-20z" fill="#fbc02d"/><rect x="206" y="106" width="72" height="8" rx="4" fill="#263238"/><rect x="206" y="124" width="50" height="8" rx="4" fill="#795600"/><circle cx="70" cy="140" r="16" fill="#795600"/><rect x="50" y="160" width="40" height="30" rx="14" fill="#795600"/><circle cx="334" cy="62" r="14" fill="#263238"/><rect x="316" y="80" width="36" height="26" rx="12" fill="#263238"/>',
  recruitment:'<rect width="400" height="200" fill="#fff6dc"/><circle cx="350" cy="40" r="64" fill="#fdeaa8"/><circle cx="40" cy="170" r="50" fill="#fbe7b0"/><rect x="118" y="36" width="164" height="124" rx="14" fill="#fff" stroke="#263238" stroke-width="5"/><rect x="180" y="24" width="40" height="20" rx="6" fill="#263238"/><circle cx="168" cy="92" r="22" fill="#fbc02d"/><circle cx="168" cy="85" r="9" fill="#795600"/><path d="M152 108a16 12 0 0 1 32 0z" fill="#795600"/><rect x="202" y="76" width="60" height="8" rx="4" fill="#263238"/><rect x="202" y="94" width="44" height="8" rx="4" fill="#90a4ae"/><rect x="146" y="128" width="116" height="8" rx="4" fill="#f6e3a6"/><circle cx="292" cy="148" r="24" fill="#2d7a4b"/><path d="M281 148l8 8 15-16" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
  management:'<rect width="400" height="200" fill="#fff6dc"/><circle cx="56" cy="40" r="62" fill="#fdeaa8"/><circle cx="356" cy="176" r="52" fill="#fbe7b0"/><path d="M96 162h216" stroke="#263238" stroke-width="5" stroke-linecap="round"/><rect x="116" y="118" width="30" height="42" rx="6" fill="#90a4ae"/><rect x="160" y="96" width="30" height="64" rx="6" fill="#f6e3a6"/><rect x="204" y="74" width="30" height="86" rx="6" fill="#fbc02d"/><rect x="248" y="50" width="30" height="110" rx="6" fill="#263238"/><path d="M118 104l46-26 42-6 54-36" fill="none" stroke="#795600" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M250 30l14 4-6 13" fill="none" stroke="#795600" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M318 44v62" stroke="#263238" stroke-width="5" stroke-linecap="round"/><path d="M320 46h36l-10 12 10 12h-36z" fill="#e0a800"/>',
  compliance:'<rect width="400" height="200" fill="#fff6dc"/><circle cx="348" cy="44" r="66" fill="#fdeaa8"/><circle cx="46" cy="170" r="52" fill="#fbe7b0"/><path d="M200 26l70 26v44c0 40-30 66-70 80-40-14-70-40-70-80V52z" fill="#263238"/><path d="M200 42l54 20v34c0 30-22 50-54 62-32-12-54-32-54-62V62z" fill="#fbc02d"/><rect x="178" y="92" width="44" height="36" rx="7" fill="#263238"/><path d="M188 92v-10a12 12 0 0 1 24 0v10" fill="none" stroke="#263238" stroke-width="6"/><circle cx="200" cy="108" r="5" fill="#fbc02d"/><rect x="198" y="110" width="4" height="10" rx="2" fill="#fbc02d"/><circle cx="96" cy="70" r="8" fill="#e0a800"/><circle cx="306" cy="150" r="6" fill="#795600"/>',
};
const DIFFICULTY_ORDER=['beginner','intermediate','advanced','expert'];
function courseFacts(item){
  const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
  return [['chart',capital(item.difficulty||'beginner')],['clock',fmtDuration(item.durationMinutes)],['book',item.format==='lessons'?plural(item.lessonCount||0,'lesson'):'3 modules'],item.assessmentCount?['check',plural(item.assessmentCount,'assessment')]:null]
    .filter(Boolean).map(([name,text])=>`<li>${icon(name)}<span>${esc(text)}</span></li>`).join('');
}
// One course on the Courses page: illustration, category, facts, the employee's own progress and the next step.
function catalogTile(item){
  const progress=item.completed?100:currentCourseInfo.id===item.id?pct():item.progress||0,a=item.assignment,area=learningArea(item.category);
  const action=item.completed?'Review course':(progress||item.started||item.status==='in_progress')?'Continue learning':'Start learning';
  const search=(item.title+' '+item.category+' '+area.badge+' '+(item.difficulty||'')).toLowerCase();
  return `<article class="course-card area-${area.id}" data-course-card="${esc(search)}"><div class="course-cover"><button type="button" class="course-cover-art" data-open-course="${esc(item.id)}" tabindex="-1" aria-hidden="true"><svg viewBox="0 0 400 200" preserveAspectRatio="xMidYMid slice" focusable="false">${COURSE_ART[area.id]||COURSE_ART.professional}</svg></button><span class="course-badge" title="${esc(item.category)}">${esc(area.badge)}</span>${a?.mandatory?'<span class="course-flag mandatory">Mandatory</span>':a?'<span class="course-flag">Optional</span>':''}</div><div class="course-card-body"><h3>${esc(item.title)}</h3><p class="course-card-desc">${esc(item.description)}</p><ul class="course-facts">${courseFacts(item)}</ul>${deadlineBlock(item.deadline)}${a?.assignedBy?`<div class="meta course-assigned">Assigned by ${esc(a.assignedBy)}</div>`:''}<div class="course-card-progress"><div class="progress-label">${statusTag(item.status)}<b>${progress}%</b></div><div class="progress" role="img" aria-label="Course progress ${progress}%"><span style="width:${progress}%"></span></div></div><button class="btn course-card-action" data-open-course="${esc(item.id)}">${action} ${icon('arrow')}</button></div></article>`;
}
function candidateCourses(){
  const filters=[['all','All'],['assigned','Assigned to me'],['in_progress','In progress'],['not_started','Not started'],['completed','Completed'],['overdue','Overdue']];
  const byStatus=c=>courseFilter==='all'||(courseFilter==='assigned'?Boolean(c.assignment):c.status===courseFilter);
  const inArea=(c,id)=>id==='all'||learningArea(c.category).id===id;
  const byLevel=c=>courseDifficulty==='all'||(c.difficulty||'beginner')===courseDifficulty;
  const shown=courseCatalog.filter(c=>byStatus(c)&&inArea(c,courseArea)&&byLevel(c));
  // Each row's counts follow the other selections, so the numbers always match what a click will show.
  const chip=(act,value,label,count,active)=>`<button class="${active?'active':''}" data-act="${act}" data-value="${value}" aria-pressed="${active}">${label} <span>${count}</span></button>`;
  const areas=[{id:'all',filter:'All Courses'},...LEARNING_AREAS].map(a=>chip('course-area',a.id,a.filter,courseCatalog.filter(c=>byStatus(c)&&byLevel(c)&&inArea(c,a.id)).length,courseArea===a.id)).join('');
  const statuses=filters.map(([value,label])=>chip('course-filter',value,label,courseCatalog.filter(c=>inArea(c,courseArea)&&byLevel(c)&&(value==='all'||(value==='assigned'?c.assignment:c.status===value))).length,courseFilter===value)).join('');
  const levels=DIFFICULTY_ORDER.filter(level=>courseCatalog.some(c=>(c.difficulty||'beginner')===level));
  const sections=LEARNING_AREAS.map(a=>[a,shown.filter(c=>learningArea(c.category).id===a.id)]).filter(([,list])=>list.length)
    .map(([a,list])=>`<section class="catalog-section" data-course-section><div class="catalog-section-head"><h2>${esc(a.title)}</h2><p>${esc(a.about)}</p></div><div class="course-grid">${list.map(catalogTile).join('')}</div></section>`).join('');
  const empty=courseCatalog.length?'<div class="panel"><h3>No courses in this view</h3><p class="muted">Choose another category or filter to see more courses.</p></div>':'<div class="panel"><h3>Your next course is on its way</h3><p class="muted">Published courses will appear here when HR or a trainer makes them available.</p></div>';
  const toolbar=`<div class="course-toolbar"><input class="search" id="search" data-remember-search aria-label="Search courses" placeholder="Search courses..." value="${esc(courseSearch)}"><select class="course-level" data-change="course-difficulty" aria-label="Difficulty">${options([['all','All levels'],...levels.map(l=>[l,capital(l)])],courseDifficulty)}</select><a class="btn secondary" href="#assessments">${icon('check')} Assessments</a><a class="btn secondary" href="#history">${icon('clock')} Learning history</a></div>`;
  return `<div class="intro course-intro"><div><h1>Courses &amp; Programs</h1><p>Explore company learning resources and develop your skills.</p></div><span class="tag">${courseCatalog.length} AVAILABLE</span></div><div class="segmented area-filter" role="group" aria-label="Course categories">${areas}</div><div class="segmented" role="group" aria-label="Filter courses by status">${statuses}</div>${toolbar}${sections||empty}${sections?'<div class="panel hidden" id="search-empty"><h3>No courses match your search</h3><p class="muted">Try another search, or choose another category.</p></div>':''}`;
}
function candidateDashboard(){return currentUser.role==='manager'?managerView():employeeDashboard();}
function adminDashboard(){return orgDashboard();}
function adminNotice(){return `${adminMessage?`<div class="notice success" role="status">${esc(adminMessage)}</div>`:''}${provisionedCredentials?`<div class="notice"><strong>Share these credentials with the employee</strong><p>Email: <b>${esc(provisionedCredentials.email)}</b><br>Temporary password: <code>${esc(provisionedCredentials.password)}</code></p><p>The password is shown only in this confirmation. They must change it on first login.</p><button class="auth-link" id="dismiss-credentials">Dismiss credentials</button></div>`:''}`;}
// Employee and Manager can be assigned; an existing account also lists the role it already has so editing never changes it.
function roleOptions(selected){return options(Object.entries(ROLE_LABELS).filter(([role])=>['employee','manager'].includes(role)||role===selected),selected);}
function accountTable(group){
  const isAdmin=group==='admin',accounts=adminState.candidates.filter(user=>(user.role==='admin')===isAdmin),heading=isAdmin?'Administrators':'Employees';
  return `<section class="panel"><div class="section-heading"><h2>${heading}</h2><span class="tag">${accounts.length} TOTAL</span></div><div class="admin-table-scroll"><table class="admin-table" id="${isAdmin?'admin':'user'}-accounts-table" aria-label="${heading}"><thead><tr><th>${isAdmin?'Administrator':'Employee'}</th><th>Role & team</th><th>Status</th><th>${isAdmin?'Last sign-in':'Achievements & training hours'}</th><th>Actions</th></tr></thead><tbody>${accounts.map(user=>`<tr data-user-row="${esc((user.name+' '+user.email+' '+(user.department||'')+' '+(user.jobRole||'')).toLowerCase())}"><td><strong>${esc(user.name)}</strong>${user.source==='keka'?` <span class="tag" title="Details come from Keka">KEKA${user.kekaEmployeeNumber?' · '+esc(user.kekaEmployeeNumber):''}</span>`:''}<small>${esc(user.email)}</small></td><td>${esc(ROLE_LABELS[user.role]||user.role)}<small>${esc([user.jobTitle||user.jobRole,user.department].filter(Boolean).join(' · ')||'No department')}${user.manager?' · Reports to '+esc(user.manager):''}</small></td><td><span class="tag ${user.active?'':'gray'}">${!user.active?'DISABLED':'ACTIVE'}</span>${user.active&&user.mustChangePassword?'<small>Password change required</small>':''}</td><td>${isAdmin?(user.lastLoginAt?esc(new Date(user.lastLoginAt).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})):'Not signed in yet'):`${user.certificates} certificates<small>${user.courseRuns} course runs</small>${trainingBar(user.training)}${user.active?trainingTargetForm('user:'+user.id,user.training?.targetHours):''}`}</td><td><div class="table-actions">${!isAdmin?`<button data-user-records="${user.id}">View records</button>`:''}${user.role!=='admin'||currentUser.role==='admin'?`<button data-act="user-edit" data-id="${user.id}">Edit</button>`:''}${user.id!==currentUser.id&&(user.role!=='admin'||currentUser.role==='admin')?`<button data-reset-user="${user.id}">Reset password</button><button data-toggle-user="${user.id}" data-enable="${!user.active}">${user.active?'Disable':'Enable'}</button>`:user.id===currentUser.id?'<span class="muted">Your account</span>':''}</div></td></tr>`).join('')||`<tr><td colspan="5" class="muted">${isAdmin?'No administrators found.':'No employees added yet.'}</td></tr>`}</tbody></table></div></section>`;
}
function orgFields(prefix,values={}){
  const org=orgData(),joining=values.joiningDate||(prefix==='new-candidate'?new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'}):'');
  return `<label for="${prefix}-joining">Joining date</label><input id="${prefix}-joining" type="date" name="joiningDate" value="${esc(joining)}"><label for="${prefix}-department">Department</label><select id="${prefix}-department" name="departmentId">${options(org.departments.map(d=>[d.id,d.name]),values.departmentId,'No department')}</select><label for="${prefix}-jobrole">Job role</label><select id="${prefix}-jobrole" name="jobRoleId">${options(org.jobRoles.map(j=>[j.id,j.name]),values.jobRoleId,'No job role')}</select><label for="${prefix}-manager">Manager</label><select id="${prefix}-manager" name="managerId">${options(adminState.candidates.filter(u=>u.active&&u.id!==values.id&&['manager','hr','admin'].includes(u.role)).map(u=>[u.id,`${u.name} · ${ROLE_LABELS[u.role]}`]),values.managerId,'No manager')}</select><label for="${prefix}-title">Job title</label><input id="${prefix}-title" name="jobTitle" maxlength="100" value="${esc(values.jobTitle||'')}">`;
}
// Keka is the source of employee records: one click brings every Keka employee in and refreshes their details.
function kekaSyncPanel(){
  const r=kekaSyncResult;
  return `<section class="panel admin-form"><div class="section-heading"><h2>Keka employees</h2><button class="btn" type="button" data-act="keka-sync">Sync from Keka</button></div><p class="muted">Creates an account for every Keka employee who does not have one yet, updates names, job titles, employee numbers and reporting managers from Keka, and disables employees marked Relieved. Learning records, certificates and training targets are kept. Employees sign in with the "Sign in with Keka account" button on the login page.</p>${r?`<p class="notice success" role="status">Synced ${r.employees} Keka employees: ${r.created} new, ${r.updated} updated, ${r.deactivated} relieved and disabled${r.skipped?`, ${r.skipped} skipped (no work email, or relieved without an LMS account)`:''}.</p>`:''}</section>`;
}
function trainingTargetPanel(){
  const employees=adminState.candidates.filter(u=>u.active&&u.role!=='admin'),org=orgData(),year=employees[0]?.training?.year||new Date().getFullYear();
  const choices=`<label for="tt-scope">Apply to</label><select id="tt-scope" name="target"><option value="all">All employees (${employees.length})</option>${org.departments.map(d=>`<option value="dept:${esc(d.id)}">Department: ${esc(d.name)}</option>`).join('')}</select>`;
  return `<section class="panel admin-form"><div class="section-heading"><h2>Yearly training target ${year}</h2></div><p class="muted">Set how many hours of training employees should complete this year: here for all employees or a whole department, or in each employee's row in the Employees table below. Each employee sees a progress bar on their dashboard, and their hours appear below and in their learning records. Leave the hours blank and save to remove a target.</p>${trainingTargetForm('',null,choices)}</section>`;
}
function userEditor(){
  const user=adminState.candidates.find(u=>u.id===editUserId);if(!user)return '';
  return `<section class="panel form-inner admin-form"><h3>Edit ${esc(user.name)}</h3><form data-form="user-profile" data-id="${user.id}"><label for="edit-name">Full name</label><input id="edit-name" name="name" value="${esc(user.name)}" minlength="2" maxlength="100" required><label for="edit-role">Role</label><select id="edit-role" name="role" ${user.id===currentUser.id?'disabled':''}>${roleOptions(user.role)}</select>${user.id===currentUser.id?`<input type="hidden" name="role" value="${esc(user.role)}">`:''}${orgFields('edit',user)}<div class="admin-actions"><button class="btn" type="submit">Save profile</button><button class="btn secondary" type="button" data-act="user-edit-cancel">Cancel</button></div><p class="form-status" role="status"></p></form></section>`;
}
function organisationSettings(){
  if(!can('org.manage'))return '';
  const entry=orgEntry();if(!entry.data)return stateBlock(entry,'organisation settings','org');
  const org=entry.data;
  const list=(kind,items,label)=>items.map(item=>`<div class="admin-list-row"><div><strong>${esc(label(item))}</strong>${item.employees!=null?`<small>${item.employees} employees</small>`:item.department?`<small>${esc(item.department)}</small>`:''}</div><button class="auth-link" data-act="org-delete" data-kind="${kind}" data-id="${esc(item.id||'')}" data-name="${esc(item.name||item)}">Delete</button></div>`).join('')||'<p class="muted">None yet.</p>';
  return `<div class="org-grid">${panel('Departments',`${list('departments',org.departments,d=>d.name)}<form class="inline-form" data-form="org-save" data-kind="departments"><input name="name" minlength="2" maxlength="80" required placeholder="New department" aria-label="New department"><button class="btn secondary" type="submit">Add</button><p class="form-status" role="status"></p></form>`)}${panel('Job roles',`${list('job-roles',org.jobRoles,j=>j.name)}<form class="inline-form" data-form="org-save" data-kind="job-roles"><input name="name" minlength="2" maxlength="80" required placeholder="New job role" aria-label="New job role"><select name="departmentId" aria-label="Job role department">${options(org.departments.map(d=>[d.id,d.name]),'','Any department')}</select><button class="btn secondary" type="submit">Add</button><p class="form-status" role="status"></p></form>`)}${panel('Course categories',`${list('categories',org.categories.map(name=>({name})),c=>c.name)}<form class="inline-form" data-form="org-save" data-kind="categories"><input name="name" minlength="2" maxlength="80" required placeholder="New category" aria-label="New category"><button class="btn secondary" type="submit">Add</button><p class="form-status" role="status"></p></form>`)}</div>`;
}
function userManager(){return `${adminNotice()}<div class="admin-split"><section class="panel form-inner admin-form"><span class="tag">ACCOUNT PROVISIONING</span><h2>Add employee</h2><form id="create-candidate-form"><label for="new-candidate-name">Full name</label><input id="new-candidate-name" type="text" minlength="2" maxlength="100" required><label for="new-candidate-email">Work email</label><input id="new-candidate-email" type="email" maxlength="254" required><label for="new-candidate-role">Role</label><select id="new-candidate-role">${roleOptions('employee')}</select>${orgFields('new-candidate')}<label for="new-candidate-target">Yearly training target in hours (optional)</label><input id="new-candidate-target" type="number" min="1" max="2000" step="1" placeholder="For example, 30"><label for="new-candidate-password">Temporary password</label><input id="new-candidate-password" type="text" autocomplete="off" minlength="8" maxlength="128" required><button type="button" class="auth-link" id="generate-password">Generate a password</button><p class="muted">A new password is required at the first sign-in. Existing passwords cannot be viewed.</p><button class="btn" type="submit">Add employee</button><p class="form-status" id="candidate-form-status" role="status"></p></form></section><div class="account-tables"><input class="search" id="user-search" aria-label="Search accounts" placeholder="Search by name, email, department or role...">${userEditor()}${kekaSyncPanel()}${trainingTargetPanel()}${accountTable('admin')}${accountTable('employee')}</div></div>${resetCandidate?`<section class="panel form-inner admin-form"><h3>Reset password for ${esc(resetCandidate.name)}</h3><form id="reset-candidate-form"><label for="reset-temporary-password">New temporary password</label><input id="reset-temporary-password" type="text" minlength="8" maxlength="128" autocomplete="off" required><p class="muted">This signs the employee out of all sessions and requires a password change.</p><button class="btn">Reset password</button> <button type="button" class="btn secondary" id="cancel-reset">Cancel</button><p class="form-status" id="reset-form-status" role="status"></p></form></section>`:''}${recordPreview?`<section class="panel"><div class="section-heading"><h2>Learning records: ${esc(recordPreview.user.name)}</h2><button class="btn secondary" id="close-records">Close</button></div>${recordPreview.training?`<h3 class="sub-heading">Training hours ${recordPreview.training.year}</h3>${trainingBar(recordPreview.training)}`:''}<p class="muted">${recordPreview.runs.length} runs &middot; ${recordPreview.video_progress.length} video records &middot; ${recordPreview.exercise_attempts.length} practice submissions &middot; ${recordPreview.exam_attempts.length} exams &middot; ${recordPreview.assessment_attempts?.length||0} assessments &middot; ${recordPreview.certificates.length} certificates</p><pre class="records-json">${esc(JSON.stringify(recordPreview,null,2))}</pre></section>`:''}<h2 class="page-section-title">Organisation</h2>${organisationSettings()}`;}
function workflowSteps(course){
  const steps=[['Create course',Boolean(course)],['Add lessons',Boolean(course)],['Add assessments',Boolean(course?.postAssessmentId)],['Preview',false],['Save draft',Boolean(course)],['Publish',course?.status==='published']];
  return `<ol class="workflow">${steps.map(([label,done],i)=>`<li class="${done?'done':''}"><span>${done?'✓':i+1}</span>${label}</li>`).join('')}</ol>`;
}
// ---------------------------------------------------------------- Manage Courses → Reminders (settings, history)
const REMINDER_STATUS_TONES={sent:'success',failed:'danger'};
const reminderTypeLabel=type=>REMINDER_TYPES[type]||String(type).replace(/^before_(\d+)d$/,(_,n)=>`${n} day${n==='1'?'':'s'} before`);
function reminderManagement(){
  if(!['admin','hr'].includes(currentUser.role))return '';
  const entry=loadData('reminder-settings','manage/reminders/settings');
  if(!entry.data)return stateBlock(entry,'reminder settings','reminder-settings');
  const c=entry.data.settings,last=c.lastRun,f=reminderFilters,key='reminder-history:'+(f.course||'all'),history=loadData(key,'manage/reminders/history'+qs({courseId:f.course}));
  const list=(history.data?.history||[]).filter(h=>!f.status||h.status===f.status);
  const rows=list.map(h=>`<tr><td><strong>${esc(h.employee)}</strong></td><td>${esc(h.course||'Removed course')}</td><td>${esc(reminderTypeLabel(h.type))}</td><td>${esc(fmtDateTime(h.scheduledAt))}</td><td>${h.sentAt?esc(fmtDateTime(h.sentAt)):'—'}</td><td>${tagText(h.status,REMINDER_STATUS_TONES[h.status]||'gray')}${h.failureReason?`<small>${esc(h.failureReason)}</small>`:''}</td></tr>`).join('');
  const settings=panel('Reminder settings',`<form class="admin-form" data-form="reminder-settings"><div class="editor-fields"><div><label for="reminder-days">Send reminders this many days before the deadline</label><input id="reminder-days" name="intervalDays" value="${esc(c.intervalDays.join(', '))}" placeholder="7, 3, 1"></div><div><label for="reminder-soon">Show Due Soon within (days)</label><input id="reminder-soon" name="dueSoonDays" type="number" min="1" max="90" value="${c.dueSoonDays}" required></div></div><label class="check-label"><input type="checkbox" name="deadlineDay" ${c.deadlineDay?'checked':''}> On the deadline day</label><label class="check-label"><input type="checkbox" name="overdue" ${c.overdue?'checked':''}> When the course becomes overdue</label><div class="admin-actions"><button class="btn" type="submit">Save schedule</button><button class="btn secondary" type="button" data-act="reminders-run">Run reminders now</button></div><p class="form-status" role="status"></p></form><p class="muted">Employees are always told when a course is assigned or its deadline changes. Reminders already past when a short deadline is set are skipped. Reminders run automatically in the background${c.lastRunAt?`; last run ${esc(fmtDateTime(c.lastRunAt))}${last?`: ${last.sent} sent, ${last.failed} failed`:''}`:''}.</p>`);
  const filters=`<div class="table-filters"><label>Course<select data-change="reminder-course">${options(adminState.courses.map(k=>[k.id,k.title]),f.course,'All courses')}</select></label><label>Delivery<select data-change="reminder-status">${options([['sent','Sent'],['pending','Pending'],['failed','Failed'],['cancelled','Cancelled']],f.status,'All')}</select></label></div>`;
  const table=history.data?(rows?`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Course</th><th>Reminder</th><th>Scheduled</th><th>Sent</th><th>Delivery</th></tr></thead><tbody>${rows}</tbody></table></div>`:`<p class="muted">${f.course||f.status?'No reminders match these filters.':'No reminders have been sent yet.'}</p>`):stateBlock(history,'reminder history',key);
  return settings+panel('Reminder history',`${filters}${table}<p class="muted">The latest 100 reminders${f.course?' for this course':''}. Reminders also appear under Assign a Course → Reminder History.</p>`);
}
// ---------------------------------------------------------------- Manage Courses → Assign a Course
// The form assigns one published course; the summary beside it follows every change. Assigning a course to a target that
// already has it updates that assignment (the server keeps one per course and target). Assignment types are the ones the
// server supports: employee, department and job role.
const ASSIGN_TYPES=[['employee','Individual employee'],['department','Department'],['job_role','Job role']];
const TARGET_NOUNS={employee:'employee',department:'department',job_role:'job role'};
const SOURCE_LABELS={employee:'Individual',department:'Department',job_role:'Job role'};
const newAssignDraft=()=>({targetType:'employee',targetId:'',targetText:'',deadline:'',mandatory:false,note:''});
const rowHidden=(text,q)=>Boolean(q&&q.trim())&&!text.includes(q.trim().toLowerCase());
const RECORDS_PAGE_SIZE=10;
const RECORD_STATUSES={
  assignments:[['active','Active'],['overdue','Overdue'],['completed','Completed']],
  deadlines:[['not_started','Not started'],['in_progress','In progress'],['overdue','Overdue'],['completed','Completed']],
  reminders:[['sent','Sent'],['pending','Pending'],['failed','Failed'],['cancelled','Cancelled']]};
const employeeLabel=p=>`${p.name} (${p.email})`;
const assignCourses=()=>adminState.courses.filter(c=>c.status==='published');
const assignCourse=()=>{const list=assignCourses();return list.find(c=>c.id===deadlineCourseId)||list[0]||null;};
function assignChoices(type){
  const org=orgData(),count=item=>item.employees!=null?` · ${item.employees} employee${item.employees===1?'':'s'}`:'';
  if(type==='department')return org.departments.map(d=>[d.id,d.name+count(d)]);
  if(type==='job_role')return org.jobRoles.map(j=>[j.id,j.name+count(j)]);
  return peopleData().map(p=>[p.id,employeeLabel(p)]);
}
// The chosen target's display name, or '' while nothing valid is chosen.
function assignTargetName(a){
  if(!a.targetId)return '';
  if(a.targetType==='employee'){const p=peopleData().find(x=>x.id===a.targetId);return p?employeeLabel(p):'';}
  return (a.targetType==='department'?orgData().departments:orgData().jobRoles).find(x=>x.id===a.targetId)?.name||'';
}
// "2026-11-20T17:30" (the form's IST value) shown as 20-11-2026 17:30.
const formDeadline=value=>{const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})/.exec(value||'');return m?`${m[3]}-${m[2]}-${m[1]} ${m[4]}`:'';};
function assignSummaryRows(){
  const a=assignDraft||newAssignDraft(),course=assignCourse(),none='<span class="muted">Not selected</span>';
  const rows=[['book','Course',course?esc(course.title):none],['users','Assignment type',esc(ASSIGN_TYPES.find(([t])=>t===a.targetType)?.[1]||'')],
    ['user',capital(TARGET_NOUNS[a.targetType]),assignTargetName(a)?esc(assignTargetName(a)):none],['calendar','Deadline (IST)',a.deadline?esc(formDeadline(a.deadline)):(a.mandatory?'<span class="warn-text">Required for mandatory training</span>':'<span class="muted">No deadline</span>')],
    ['target','Requirement',a.mandatory?'<span class="tag warn">MANDATORY</span>':'<span class="tag requirement-optional">OPTIONAL</span>']];
  return rows.map(([name,label,value])=>`<div class="summary-row">${icon(name)}<dt>${label}</dt><dd>${value}</dd></div>`).join('');
}
function updateAssignSummary(){const box=document.getElementById('assign-summary');if(box)box.innerHTML=assignSummaryRows();}
function assignField(id,label,control,{required=false,hint='',wide=false,extra=''}={}){return `<div class="assign-field ${wide?'wide':''}"><label for="${id}">${label}${required?' <span class="req" aria-hidden="true">*</span>':''}${extra}</label>${control}${hint?`<small class="muted">${hint}</small>`:''}</div>`;}
function assignForm(courses,selected){
  const a=assignDraft||(assignDraft=newAssignDraft()),managerOnly=currentUser.role==='manager',types=managerOnly?ASSIGN_TYPES.slice(0,1):ASSIGN_TYPES,noun=TARGET_NOUNS[a.targetType];
  const target=a.targetType==='employee'
    ?`<input id="assign-target" type="search" name="targetText" list="assign-people" value="${esc(a.targetText||assignTargetName(a))}" placeholder="Search by name or email" autocomplete="off" required><datalist id="assign-people">${peopleData().map(p=>`<option value="${esc(employeeLabel(p))}">${esc(p.department||'No department')}${p.jobRole?' · '+esc(p.jobRole):''}</option>`).join('')}</datalist>`
    :`<select id="assign-target" name="targetId" required>${options(assignChoices(a.targetType),a.targetId,`Select a ${noun}…`)}</select>`;
  const card=(value,title,text,checked,id='')=>`<label class="choice-card"><input ${id?`id="${id}"`:''} type="radio" name="requirement" value="${value}" ${checked?'checked':''}><span><strong>${title}</strong><small>${text}</small></span></label>`;
  return `<form class="panel assign-card" id="assign-form" data-form="course-assign" data-course="${esc(selected.id)}" novalidate>
  <section class="assign-section"><h2><span class="assign-num">1</span>Course and Audience</h2><div class="assign-grid">
  ${assignField('assign-course','Published course',`<select id="assign-course" data-change="deadline-course">${options(courses.map(c=>[c.id,c.title]),selected.id)}</select>`,{required:true})}
  ${assignField('assign-type','Assignment type',`<select id="assign-type" name="targetType" data-change="assign-type">${options(types,a.targetType)}</select>`,{required:true,hint:managerOnly?'Managers assign training to their direct reports.':''})}
  ${assignField('assign-target',`Select ${noun}`,target,{required:true,wide:true,hint:a.targetType==='employee'?'Type to search, then choose an employee from the list.':`Everyone in this ${noun} gets the course, including employees who join it later.`})}</div></section>
  <section class="assign-section"><h2><span class="assign-num">2</span>Deadline and Requirement</h2><div class="assign-grid">
  ${assignField('assign-deadline','Deadline date and time (IST)',`<input id="assign-deadline" type="datetime-local" name="deadline" value="${esc(a.deadline)}">`,{extra:' <span class="req req-if-mandatory" aria-hidden="true">*</span>'})}
  <div class="assign-field"><span class="field-label" id="assign-requirement-label">Training requirement <span class="req" aria-hidden="true">*</span></span><div class="choice-cards" role="radiogroup" aria-labelledby="assign-requirement-label">${managerOnly?'':card('mandatory','Mandatory','Requires a deadline',a.mandatory,'assign-mandatory')}${card('optional','Optional','Deadline optional',!a.mandatory)}</div></div></div></section>
  <section class="assign-section"><h2><span class="assign-num">3</span>Additional Information</h2>
  ${assignField('assign-note','Note (optional)',`<textarea id="assign-note" name="note" maxlength="500" rows="3" placeholder="Add instructions or context for the assigned learners…">${esc(a.note)}</textarea>`,{wide:true})}</section>
  <div class="assign-actions"><p class="form-status" role="status"></p><button type="button" class="btn secondary" data-act="assign-clear">Clear</button><button class="btn" type="submit">Assign Course ${icon('arrow')}</button></div></form>`;
}
// Rules the server already enforces (development.create_assignment and the deadline rules); nothing here is new policy.
function assignRules(){
  const rules=['Only published courses can be assigned.','Mandatory training requires a deadline, and a new deadline cannot be in the past.',
    'If the target already has this course, the assignment is updated, not duplicated.','An individual deadline replaces a department or job-role deadline, but optional training never replaces mandatory training.',
    'Overdue courses remain open, and late completion is recorded.'];
  if(currentUser.role==='manager')rules.unshift('Managers can assign optional training to their direct reports only.');
  return `<section class="panel side-card"><div class="side-card-head"><span class="side-icon">${icon('check')}</span><h3>Assignment Rules</h3></div><ul class="rules-list">${rules.map(r=>`<li>${esc(r)}</li>`).join('')}</ul></section>`;
}
function assignSummary(){
  return `<section class="panel side-card summary-card"><div class="side-card-head"><span class="side-icon">${icon('file')}</span><div><h3>Assignment Summary</h3><p class="muted">Review the assignment details before proceeding.</p></div></div><dl id="assign-summary" aria-live="polite">${assignSummaryRows()}</dl></section>`;
}
// ---------------------------------------------------------------- Assign a Course → records (assignments, deadlines, reminders)
let assignRecords={tab:'assignments',q:'',course:'',status:'',requirement:'',page:1};
function recordsPager(page,pages,total){
  if(!total)return '';
  const from=(page-1)*RECORDS_PAGE_SIZE+1,to=Math.min(total,page*RECORDS_PAGE_SIZE);
  return `<div class="records-pager"><span class="muted">Showing ${from}–${to} of ${total}</span><div class="table-actions"><button type="button" data-act="records-page" data-page="${page-1}" ${page<=1?'disabled':''}>Previous</button><span class="muted">Page ${page} of ${pages}</span><button type="button" data-act="records-page" data-page="${page+1}" ${page>=pages?'disabled':''}>Next</button></div></div>`;
}
function pageSlice(list){const pages=Math.max(1,Math.ceil(list.length/RECORDS_PAGE_SIZE)),page=Math.min(Math.max(1,assignRecords.page),pages);return {rows:list.slice((page-1)*RECORDS_PAGE_SIZE,page*RECORDS_PAGE_SIZE),page,pages,total:list.length};}
const assignRecordsTable=(head,rows,empty)=>rows?`<div class="admin-table-scroll"><table class="admin-table records-table"><thead><tr>${head.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`:`<p class="muted records-empty">${empty}</p>`;
const assignTargetStatus=a=>a.employees&&a.completed>=a.employees?'completed':a.deadlineAt&&Date.parse(a.deadlineAt)<Date.now()+serverClockOffset?'overdue':'active';
function deadlineForm(courseId,type,target,value,mandatory,note,label){
  return `<form data-form="deadline-save" data-course="${esc(courseId)}" data-type="${esc(type)}" data-target="${esc(target)}">${note!=null?`<input type="hidden" name="note" value="${esc(note)}">`:''}<label>Deadline (IST)<input type="datetime-local" name="deadline" value="${esc(value||'')}" ${type==='employee'?'required':''} aria-label="${esc(label)}"></label><label class="check-label"><input type="checkbox" name="mandatory" ${mandatory?'checked':''}> Mandatory</label><button class="btn secondary" type="submit">Save</button><p class="form-status" role="status"></p></form>`;
}
function assignmentRecords(){
  const r=assignRecords,entry=loadData('assign-list','manage/assignments');
  if(!entry.data)return stateBlock(entry,'assignments','assign-list');
  const q=r.q.trim().toLowerCase();
  const list=entry.data.assignments.filter(a=>(!r.course||a.courseId===r.course)&&(!r.requirement||(r.requirement==='mandatory')===a.mandatory)&&(!r.status||assignTargetStatus(a)===r.status)&&(!q||[a.target,a.course,SOURCE_LABELS[a.targetType]].join(' ').toLowerCase().includes(q)));
  const view=pageSlice(list),tones={active:'',overdue:'danger',completed:'success'},labels={active:'Active',overdue:'Overdue',completed:'Completed'};
  const rows=view.rows.map(a=>{const pct=a.employees?Math.round(a.completed/a.employees*100):0,state=assignTargetStatus(a);
    return `<tr><td><strong>${esc(a.target)}</strong><small>${esc(SOURCE_LABELS[a.targetType]||a.targetType)} · ${a.employees} employee${a.employees===1?'':'s'}</small></td><td>${esc(a.course)}</td><td>${esc(fmtDateTime(a.assignedAt))}${a.assignedBy?`<small>by ${esc(a.assignedBy)}</small>`:''}</td><td>${a.deadlineDisplay?esc(a.deadlineDisplay):'No deadline'}${a.originalDisplay?`<small>Originally ${esc(a.originalDisplay)}</small>`:''}</td><td>${a.mandatory?tagText('Mandatory','warn'):tagText('Optional','gray')}</td><td>${meter(pct,a.target+' completion')}<small>${a.completed} of ${a.employees} completed</small></td><td>${tagText(labels[state],tones[state])}</td><td><div class="table-actions record-actions"><details class="deadline-override"><summary>Update</summary>${deadlineForm(a.courseId,a.targetType,a.targetId,a.deadlineInput,a.mandatory,a.note||'',`Deadline for ${a.target}`)}</details>${a.canRemove?`<button type="button" class="danger-link" data-act="assignment-delete" data-id="${esc(a.id)}">Remove</button>`:''}</div></td></tr>`;}).join('');
  return assignRecordsTable(['Assigned to','Course','Assigned','Deadline','Requirement','Progress','Status','Actions'],rows,entry.data.assignments.length?'No assignments match these filters.':'No courses have been assigned yet.')+recordsPager(view.page,view.pages,view.total);
}
// Employee deadlines come from Training Compliance, which filters and pages on the server.
function deadlineRecords(){
  const r=assignRecords,path='manage/compliance'+qs({q:r.q.trim(),course:r.course,status:r.status,type:r.requirement,page:r.page,size:RECORDS_PAGE_SIZE}),key='compliance:assign:'+path,entry=loadData(key,path);
  if(!entry.data)return stateBlock(entry,'employee deadlines',key);
  const t=entry.data.table;
  const rows=t.rows.map(e=>`<tr><td><strong>${esc(e.employee)}</strong><small>${esc(e.email)} · ${esc(e.department)}</small></td><td>${esc(e.course)}</td><td>${e.deadlineDisplay?esc(e.deadlineDisplay):'No deadline'}${e.originalDeadlineDisplay&&e.originalDeadlineAt!==e.deadlineAt?`<small>Originally ${esc(e.originalDeadlineDisplay)}</small>`:''}</td><td>${esc(SOURCE_LABELS[e.source]||'—')}<small>${e.mandatory?'Mandatory':'Optional'}</small></td><td>${meter(e.progress,e.employee+' progress')}</td><td>${tagText(e.dueSoon?'Due soon':e.statusLabel,e.dueSoon?'due-soon':DEADLINE_TONES[e.status])}${e.completedDisplay?`<small>Completed ${esc(e.completedDisplay)}</small>`:e.overdueBy?`<small>Overdue by ${esc(e.overdueBy)}</small>`:''}</td><td><details class="deadline-override"><summary>Change</summary>${deadlineForm(e.courseId,'employee',e.employeeId,e.deadlineInput,e.mandatory,null,`Deadline for ${e.employee}`)}</details></td></tr>`).join('');
  return assignRecordsTable(['Employee','Course','Deadline','Assignment type','Progress','Status','Actions'],rows,'No employee deadlines match these filters.')+recordsPager(t.page,t.pages,t.total);
}
function reminderRecords(){
  const r=assignRecords,key='reminder-history:'+(r.course||'all'),entry=loadData(key,'manage/reminders/history'+qs({courseId:r.course}));
  if(!entry.data)return stateBlock(entry,'reminder history',key);
  const q=r.q.trim().toLowerCase(),list=entry.data.history.filter(h=>(!r.status||h.status===r.status)&&(!q||[h.employee,h.course||''].join(' ').toLowerCase().includes(q))),view=pageSlice(list);
  const rows=view.rows.map(h=>`<tr><td><strong>${esc(h.employee)}</strong></td><td>${esc(h.course||'Removed course')}</td><td>${esc(reminderTypeLabel(h.type))}</td><td>${esc(fmtDateTime(h.scheduledAt))}</td><td>${h.sentAt?esc(fmtDateTime(h.sentAt)):'—'}</td><td>${tagText(h.status,REMINDER_STATUS_TONES[h.status]||'gray')}${h.failureReason?`<small>${esc(h.failureReason)}</small>`:''}</td></tr>`).join('');
  return assignRecordsTable(['Employee','Course','Reminder','Scheduled','Sent','Delivery'],rows,entry.data.history.length?'No reminders match these filters.':'No reminders have been sent yet.')+recordsPager(view.page,view.pages,view.total)+'<p class="muted">The latest 100 reminders. Reminder settings are under Manage Courses → Reminders.</p>';
}
function assignRecordsPanel(courses){
  const r=assignRecords,staff=['admin','hr'].includes(currentUser.role);
  const tabs=[['assignments','users','Assignments'],['deadlines','calendar','Employee Deadlines'],...(staff?[['reminders','bell','Reminder History']]:[])];
  if(!tabs.some(([id])=>id===r.tab))r.tab='assignments';
  const select=(field,label,items,blank)=>`<label class="records-select"><span>${label}:</span><select data-change="records-filter" data-field="${field}" aria-label="${label}">${options(items,r[field],blank)}</select></label>`;
  const filters=`<div class="records-filters"><div class="records-search">${icon('filter')}<input type="search" id="records-search" data-records-search value="${esc(r.q)}" placeholder="Search by employee or course…" aria-label="Search records"></div>${select('course','Course',courses.map(c=>[c.id,c.title]),'All courses')}${select('status','Status',RECORD_STATUSES[r.tab],'All statuses')}${r.tab!=='reminders'?select('requirement','Requirement',[['mandatory','Mandatory'],['optional','Optional']],'All'):''}</div>`;
  const body=r.tab==='deadlines'?deadlineRecords():r.tab==='reminders'?reminderRecords():assignmentRecords();
  return `<section class="panel records-panel"><div class="records-tabs" role="tablist" aria-label="Assignment records">${tabs.map(([id,name,label])=>`<button type="button" role="tab" aria-selected="${r.tab===id}" class="${r.tab===id?'active':''}" data-act="records-tab" data-tab="${id}">${icon(name)}${label}</button>`).join('')}</div>${filters}${body}</section>`;
}
function courseDeadlineSettings(){
  if(!can('courses.assign'))return '';
  const courses=assignCourses(),selected=assignCourse();
  if(!selected)return panel('Assign a course','<p class="muted">Only published courses can be assigned. Publish a course from Manage Courses, then assign it here.</p>');
  return `<div class="assign-layout">${assignForm(courses,selected)}<aside class="assign-side">${assignSummary()}${assignRules()}</aside></div>${assignRecordsPanel(courses)}`;
}
function courseResources(course){
  return panel('Learning materials',`${(course.resources||[]).map(r=>`<div class="admin-list-row"><div><strong>${esc(r.title)}</strong><small>${esc(capital(r.kind))}${r.module_index!=null?' · Module '+(r.module_index+1):''}</small></div><div class="table-actions"><a class="tag" href="${esc(r.url)}" target="_blank" rel="noopener">OPEN</a><button data-act="resource-delete" data-id="${r.id}">Remove</button></div></div>`).join('')||'<p class="muted">Add documents, presentations, videos or links for employees.</p>'}<form class="admin-form" data-form="resource-save" data-id="${esc(course.id)}"><label for="resource-title">Title</label><input id="resource-title" name="title" minlength="2" maxlength="150" required><div class="editor-fields"><div><label for="resource-kind">Type</label><select id="resource-kind" name="kind">${options([['document','Document'],['presentation','Presentation'],['video','Video'],['link','Link']],'document')}</select></div><div><label for="resource-module">Module</label><select id="resource-module" name="moduleIndex">${options([[0,'Module 1'],[1,'Module 2'],[2,'Module 3']],'','Whole course')}</select></div></div><label for="resource-file">Upload file (PDF, Office, video, image; up to 50 MB)</label><input id="resource-file" type="file" accept=".pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.txt,.csv,.mp4,.webm,.vtt,.png,.jpg,.jpeg"><label for="resource-url">…or link (HTTPS)</label><input id="resource-url" name="url" type="url" maxlength="2000" placeholder="https://"><button class="btn" type="submit">Add material</button><p class="form-status" role="status"></p></form><p class="muted">Uploaded files are stored privately and are visible to employees only while the course is published.</p>`);
}
// ---------------------------------------------------------------- Manage Courses → Courses (catalogue)
const COURSE_STATUS_TONES={published:'success',draft:'gray',archived:'warn'};
const CATALOG_STATUSES=[['all','All'],['published','Published'],['draft','Draft'],['archived','Archived']];
function courseMetrics(courses){
  const count=s=>courses.filter(c=>c.status===s).length;
  return `<div class="stats course-metrics">${kpi('file',courses.length,'Total courses')}${kpi('check',count('published'),'Published')}${kpi('clock',count('draft'),'Drafts')}${kpi('book',count('archived'),'Archived')}${kpi('users',courses.reduce((n,c)=>n+(c.assignments||0),0),'Assignments')}${kpi('chart',courses.reduce((n,c)=>n+(c.learners||0),0),'Enrolled learners')}</div>`;
}
function courseRow(item){
  const published=item.status==='published',search=[item.title,item.category,item.department||'All departments',item.description,item.status].join(' ').toLowerCase();
  const assign=can('courses.assign')?`<button data-act="course-assign" data-id="${esc(item.id)}" ${published?'':'disabled title="Publish the course before assigning it"'}>Assign</button>`:'';
  const more=`<details class="row-menu"><summary aria-label="More actions for ${esc(item.title)}">More</summary><div class="row-menu-list">${item.status!=='archived'?`<button type="button" data-act="course-archive" data-id="${esc(item.id)}">Archive</button>`:''}<button type="button" class="danger-link" data-act="course-delete" data-id="${esc(item.id)}">Delete</button></div></details>`;
  return `<tr data-search-row="courses" data-search="${esc(search)}" ${rowHidden(search,catalogFilters.q)?'hidden':''}><td><strong>${esc(item.title)}</strong><small class="clamp">${esc(item.description)}</small>${item.source?`<small>Imported from ${esc(item.source.platform)}${item.source.importStatus==='reference'?' (reference)':''}</small>`:''}</td><td>${esc(item.category)}<small>${esc(item.department||'All departments')}${item.visibility==='department'?' only':''}</small></td><td>${esc(capital(item.difficulty))}<small>${esc(fmtDuration(item.durationMinutes))} · ${item.format==='lessons'?'Lesson-based':'3-module'}</small></td><td>${tagText(item.status,COURSE_STATUS_TONES[item.status]||'gray')}<small>${item.assignments||0} assignment${item.assignments===1?'':'s'} · ${item.learners||0} learner${item.learners===1?'':'s'}</small></td><td><div class="table-actions course-actions"><button data-edit-course="${esc(item.id)}">Edit</button><button data-act="course-preview" data-id="${esc(item.id)}">Preview</button>${assign}${more}</div></td></tr>`;
}
function courseCatalogTable(){
  const courses=adminState.courses,f=catalogFilters,categories=[...new Set(courses.map(c=>c.category))].sort();
  const shown=courses.filter(c=>(f.status==='all'||c.status===f.status)&&(!f.category||c.category===f.category));
  const chips=CATALOG_STATUSES.map(([value,label])=>`<button type="button" class="${f.status===value?'active':''}" data-act="catalog-status" data-value="${value}" aria-pressed="${f.status===value}">${label} <span>${value==='all'?courses.length:courses.filter(c=>c.status===value).length}</span></button>`).join('');
  return `${courseMetrics(courses)}<section class="panel admin-table-scroll"><div class="section-heading"><h2>Course catalogue</h2><button class="btn" data-import="choose">+ Create course</button></div>
  <div class="table-filters"><input class="search" id="catalog-search" type="search" data-row-search="courses" value="${esc(f.q)}" placeholder="Search by title, category or department" aria-label="Search courses"><label>Category<select id="catalog-category" data-change="catalog-category">${options(categories.map(c=>[c,c]),f.category,'All categories')}</select></label></div>
  <div class="status-chips" role="group" aria-label="Filter by status">${chips}</div>
  <table class="admin-table course-table"><thead><tr><th>Course</th><th>Category</th><th>Level &amp; duration</th><th>Status</th><th>Actions</th></tr></thead><tbody>${shown.map(courseRow).join('')||`<tr><td colspan="5" class="muted">${courses.length?'No courses match these filters.':'No courses yet. Choose Create course to add your first course.'}</td></tr>`}</tbody></table>
  <p class="muted">Only published courses can be assigned. Archived courses are hidden from employees; their progress and certificates are kept.</p></section>`;
}
// Existing 3-module courses keep their original curriculum editor.
function legacyCourseManager(){
  const course=editingCourse?adminState.courses.find(c=>c.id===editingCourse):null,org=orgData();
  const content=course?.content||adminState.courses[0]?.content||{sets:[],lessons:[]};
  const categories=[...new Set([...(org.categories.length?org.categories:['Technical Skills']),...(course?[course.category]:[])])];
  const posts=(pageCache['m-assess']?.data?.assessments||[]).filter(a=>a.kind==='post');
  if(can('assessments.manage'))loadData('m-assess','manage/assessments');
  return `
  <section class="panel admin-form course-editor"><span class="tag">${course?'EDIT COURSE':'NEW COURSE'}</span><h2>${course?'Edit course':'Create a learning opportunity'}</h2>${workflowSteps(course)}<form id="course-editor-form"><div class="editor-fields"><div><label for="course-title">Course name</label><input id="course-title" value="${esc(course?.title||'')}" minlength="2" maxlength="150" required></div><div><label for="course-category">Category</label><select id="course-category" required>${options(categories.map(c=>[c,c]),course?.category||categories[0])}</select></div><div><label for="course-status">Visibility</label><select id="course-status">${['draft','published','archived'].map(status=>`<option value="${status}" ${status===(course?.status||'draft')?'selected':''}>${capital(status)}</option>`).join('')}</select></div></div><label for="course-description">Description</label><textarea id="course-description" rows="3" maxlength="2000" required>${esc(course?.description||'')}</textarea>
  <div class="editor-fields"><div><label for="course-difficulty">Difficulty</label><select id="course-difficulty">${options([['beginner','Beginner'],['intermediate','Intermediate'],['advanced','Advanced'],['expert','Expert']],course?.difficulty||'beginner')}</select></div><div><label for="course-duration">Estimated duration (minutes)</label><input id="course-duration" type="number" min="0" max="100000" value="${esc(course?.durationMinutes??60)}"></div><div><label for="course-department">Department</label><select id="course-department">${options(org.departments.map(d=>[d.id,d.name]),course?.departmentId,'All departments')}</select></div></div>
  <div class="editor-fields"><div><label for="course-pass">Module exam pass mark</label><select id="course-pass">${options([[25,'25% (1 of 4)'],[50,'50% (2 of 4)'],[75,'75% (3 of 4)'],[100,'100% (4 of 4)']],course?.passPercent||75)}</select></div><div><label for="course-attempts">Exam attempts per module</label><select id="course-attempts">${options([[1,'1 attempt'],[2,'2 attempts'],[3,'3 attempts']],course?.maxAttempts||3)}</select></div><div><label for="course-post">Post-training assessment</label><select id="course-post">${options(posts.map(a=>[a.id,a.title+(a.status!=='published'?' ('+a.status+')':'')]),course?.postAssessmentId,'Not required')}</select></div></div>${currentUser.role!=='trainer'?`<label for="course-trainer">Course owner / trainer</label><select id="course-trainer">${options(org.trainers.map(t=>[t.id,`${t.name} · ${ROLE_LABELS[t.role]}`]),course?.trainerId,'Not assigned')}</select>`:''}
  <p class="muted">Completion criteria: all videos watched, all exercises passed, every module exam passed at the pass mark${posts.length?', and the post-training assessment passed when one is selected':''}. Certificates are issued only when these are met.</p><details class="content-authoring"><summary>Lessons, exercises and module exams</summary><p class="muted">Each course has 3 modules, 6 video lessons, 2 exercises per module, and a 4-question exam per module. Lesson videos use an assets/ path, an uploaded material (api/materials/…) or an HTTPS URL, a duration in seconds, and optional captions. Questions use [prompt, options, correct option index, exercise explanation]; answer indices start at 0. Courses with learner history keep their original content; create a new course version to change lessons or questions.</p><label for="course-content">Curriculum JSON</label><textarea id="course-content" class="curriculum-json" rows="22" spellcheck="false" required>${esc(JSON.stringify(content,null,2))}</textarea></details><div class="admin-actions"><button class="btn" type="submit">Save course</button>${course?`<button class="btn secondary" type="button" data-act="course-preview" data-id="${course.id}">Preview</button><button class="btn secondary" type="button" id="cancel-course-edit">Cancel editing</button>`:''}</div><p class="form-status" id="course-form-status" role="status"></p></form></section>${course?courseResources(course):''}`;
}
// ---------------------------------------------------------------- lesson-based course builder (Manage Courses)
// Links to official learning sites only; administrators choose and can edit each link. Nothing is copied from these sites.
const OFFICIAL_SOURCES=[['Microsoft — Generative AI for Beginners','https://github.com/microsoft/generative-ai-for-beginners'],['Hugging Face Learn','https://huggingface.co/learn'],['Google — Machine Learning Crash Course','https://developers.google.com/machine-learning/crash-course'],['Databricks documentation','https://docs.databricks.com/'],['Databricks training','https://www.databricks.com/learn/training'],['AWS Skill Builder — AI & ML training','https://skillbuilder.aws/']];
const BUILDER_STEPS=['Course basics','Learning materials','Assessment','Review & publish'];
let courseDraft=null,builderStep=1,builderBusy=false,builderStatus='',builderUploads={},draftKey=0;
const newLesson=()=>({key:'l'+(++draftKey),id:null,title:'',description:'',videoUrl:'',documentUrl:'',documentName:'',resources:[],content:'',exercise:'',durationMinutes:15,captionsUrl:'',videoSeconds:0,completionPercent:90,hasProgress:false,moduleTitle:''});
const newQuestion=coding=>({prompt:'',code:'',coding:Boolean(coding),options:['',''],correct:0,explanation:''});
const newAssessment=()=>({title:'',passPercent:70,maxAttempts:3,timeLimitMinutes:15,locked:false,questions:[newQuestion(false)]});
function newCourseDraft(){const org=orgData(),first=newLesson();return {id:null,title:'',category:org.categories[0]||'Technical Skills',description:'',difficulty:'beginner',durationMinutes:60,departmentId:'',visibility:'everyone',status:'draft',savedStatus:null,trainerId:'',lessons:[first],assessment:null,openLesson:first.key};}
function draftFromBuilder(data,openIndex=0){
  const c=data.course,a=data.assessment,lessonsList=data.lessons.map(l=>({...l,key:'l'+(++draftKey),resources:l.resources.map(r=>({...r}))}));
  return {id:c.id,source:c.source||null,importReport:c.importReport||null,title:c.title,category:c.category,description:c.description,difficulty:c.difficulty,durationMinutes:c.durationMinutes,departmentId:c.departmentId||'',visibility:c.visibility||'everyone',status:c.status,savedStatus:c.status,trainerId:c.trainerId||'',
    lessons:lessonsList,openLesson:lessonsList[Math.min(openIndex,lessonsList.length-1)]?.key||null,
    assessment:a?{title:a.title,passPercent:a.passPercent,maxAttempts:a.maxAttempts,timeLimitMinutes:a.timeLimitMinutes,bankDraw:a.questionCount<a.questions.length?a.questionCount:null,locked:a.locked,questions:a.questions.map(q=>({prompt:q[0],options:[...q[1]],correct:q[2],explanation:q[3]||'',code:q[4]||'',coding:Boolean(q[4])}))}:null};
}
async function openCourseBuilder(id,step=1){
  editingCourse=id;courseDraft=null;courseAddMode=null;publishedCourse=null;builderDirty=false;builderStep=step;builderStatus='';adminMessage='';render();
  try{courseDraft=draftFromBuilder(await api(`manage/courses/${encodeURIComponent(id)}/builder`));}catch(error){builderStatus=error.message;}
  render();
}
function startNewCourse(){courseAddMode=null;editingCourse=null;publishedCourse=null;builderDirty=false;courseDraft=newCourseDraft();builderStep=1;builderStatus='';adminMessage='';builderUploads={};render();}
// Leave the editor (or the publish confirmation) and return to the Course Management tabs.
function closeCourseEditor(){editingCourse=null;courseDraft=null;courseAddMode=null;generateState=null;publishedCourse=null;builderStatus='';builderDirty=false;builderStep=1;}
// A lesson the author added but never filled in is left out of a saved draft rather than failing validation.
const blankLesson=l=>!l.id&&!l.title.trim()&&!l.description.trim()&&!l.exercise.trim()&&!lessonHasMaterial(l);
function lessonHasMaterial(l){return Boolean(l.videoUrl||l.documentUrl||l.content.trim()||l.resources.some(r=>r.url));}
function publishProblems(){
  const d=courseDraft,problems=[];
  if(d.title.trim().length<2)problems.push('Add a course name (Step 1).');
  if(!d.description.trim())problems.push('Add a course description (Step 1).');
  if(d.visibility==='department'&&!d.departmentId)problems.push('Choose a department for department-only visibility (Step 1).');
  if(!d.lessons.length)problems.push('Add at least one lesson (Step 2).');
  d.lessons.forEach((l,i)=>{if(l.title.trim().length<2)problems.push(`Lesson ${i+1} needs a title (Step 2).`);else if(!lessonHasMaterial(l))problems.push(`Lesson ${i+1} “${l.title}” needs a video, document, resource link, or learning content (Step 2).`);});
  if(d.assessment)d.assessment.questions.forEach((q,i)=>{if(!q.prompt.trim())problems.push(`Assessment question ${i+1} needs question text (Step 3).`);if(q.options.filter(o=>o.trim()).length!==q.options.length)problems.push(`Assessment question ${i+1} has an empty answer option (Step 3).`);});
  if(d.assessment&&!d.assessment.questions.length)problems.push('Add questions to the assessment or remove it (Step 3).');
  return problems;
}
function builderPayload(status){
  const d=courseDraft,a=d.assessment;
  return {...(d.id?{id:d.id}:{}),format:'lessons',title:d.title,category:d.category,description:d.description,status,difficulty:d.difficulty,durationMinutes:Number(d.durationMinutes)||0,departmentId:d.departmentId||null,visibility:d.visibility,
    ...(currentUser.role!=='trainer'?{trainerId:d.trainerId||null}:{}),
    lessons:d.lessons.filter(l=>!blankLesson(l)).map(l=>({...(l.id?{id:l.id}:{}),moduleTitle:(l.moduleTitle||'').trim(),title:l.title,description:l.description,videoUrl:l.videoUrl,documentUrl:l.documentUrl,documentName:l.documentName,resources:l.resources.filter(r=>r.title.trim()||r.url.trim()),content:l.content,exercise:l.exercise,durationMinutes:Number(l.durationMinutes)||0,captionsUrl:l.captionsUrl||'',videoSeconds:Number(l.videoSeconds)||0,completionPercent:Number(l.completionPercent)||90})),
    assessment:a?{title:a.title,passPercent:Number(a.passPercent),maxAttempts:Number(a.maxAttempts),timeLimitMinutes:Number(a.timeLimitMinutes),...(a.bankDraw?{questionCount:Math.min(a.bankDraw,a.questions.length)}:{}),questions:a.questions.map(q=>({prompt:q.prompt,options:q.options,correct:Number(q.correct),explanation:q.explanation,...(q.coding&&q.code.trim()?{code:q.code}:{})}))}:null};
}
async function saveCourseBuilder(targetStatus){
  const d=courseDraft,status=targetStatus||d.savedStatus||'draft',wasPublished=d.savedStatus==='published';
  if(builderBusy)return;
  if(status==='published'){
    if(publishProblems().length){builderStep=4;builderStatus='Resolve the items below before publishing.';render();return;}
    if(!wasPublished&&!confirm(`Publish “${d.title}”? It becomes available to ${d.visibility==='department'?'employees in the selected department':'all employees'} in the course catalog.`))return;
  }
  builderBusy=true;builderStatus='';render();
  try{
    const openIndex=Math.max(0,d.lessons.findIndex(l=>l.key===d.openLesson));
    const result=await api('admin/courses',builderPayload(status));
    editingCourse=result.course.id;
    courseDraft=draftFromBuilder(await api(`manage/courses/${encodeURIComponent(result.course.id)}/builder`),openIndex);
    builderDirty=false;
    await loadAdminState();courseCatalog=(await api('courses')).courses;refreshData('org','dash','me-dash','m-assess');
    if(status==='published'&&!wasPublished){publishedCourse={id:result.course.id,title:result.course.title,visibility:courseDraft.visibility};adminMessage='';}
    else adminMessage=status==='published'?`Changes to “${result.course.title}” are saved and visible to employees.`:status==='archived'?`“${result.course.title}” is saved. It stays archived.`:`“${result.course.title}” is saved as a draft. Only course managers can see it.`;
  }catch(error){builderStatus=error.message;}
  finally{builderBusy=false;render();}
}
// A step is ticked once nothing on it blocks publishing; the assessment is optional, so Step 3 is ticked only when one is added.
function stepDone(n){
  if(n===4)return courseDraft.savedStatus==='published';
  if(n===3&&!courseDraft.assessment)return false;
  return !publishProblems().some(p=>p.includes(`(Step ${n})`));
}
function builderSteps(){return `<ol class="builder-steps">${BUILDER_STEPS.map((label,i)=>{const n=i+1,done=stepDone(n),active=builderStep===n;return `<li><button type="button" class="${active?'active':''} ${done?'done':''}" data-builder="step" data-step="${n}" ${active?'aria-current="step"':''}><span>${done&&!active?'✓':n}</span>${esc(label)}</button></li>`;}).join('')}</ol>`;}
function builderField(label,id,control){return `<div><label for="${id}">${label}</label>${control}</div>`;}
function builderStepCourse(){
  const d=courseDraft,org=orgData(),categories=[...new Set([...(org.categories.length?org.categories:['Technical Skills']),d.category])];
  return `<h3 class="sub-heading">Course basics</h3><div class="editor-fields">${builderField('Course name','b-title',`<input id="b-title" data-d="title" value="${esc(d.title)}" maxlength="150" required>`)}${builderField('Category','b-category',`<select id="b-category" data-d="category">${options(categories.map(c=>[c,c]),d.category)}</select>`)}${builderField('Difficulty','b-difficulty',`<select id="b-difficulty" data-d="difficulty">${options([['beginner','Beginner'],['intermediate','Intermediate'],['advanced','Advanced'],['expert','Expert']],d.difficulty)}</select>`)}</div>
  <label for="b-description">Description</label><textarea id="b-description" data-d="description" rows="3" maxlength="2000">${esc(d.description)}</textarea>
  <div class="editor-fields">${builderField('Estimated duration (minutes)','b-duration',`<input id="b-duration" type="number" min="0" max="100000" data-d="durationMinutes" value="${esc(d.durationMinutes)}">`)}${builderField('Department','b-department',`<select id="b-department" data-d="departmentId">${options(org.departments.map(x=>[x.id,x.name]),d.departmentId,'All departments')}</select>`)}${builderField('Visibility','b-visibility',`<select id="b-visibility" data-d="visibility">${options([['everyone','All employees'],['department','Selected department only']],d.visibility)}</select>`)}</div>
  ${currentUser.role!=='trainer'?`<label for="b-trainer">Course owner / trainer</label><select id="b-trainer" data-d="trainerId">${options(org.trainers.map(t=>[t.id,`${t.name} · ${ROLE_LABELS[t.role]}`]),d.trainerId,'Not assigned')}</select>`:''}
  <p class="muted">Department-only courses are also visible to employees you assign them to. Lessons and materials come next; the assessment, its passing score and attempts are set in Step 3.</p>`;
}
function lessonSummary(l){const parts=[fmtDuration(Number(l.durationMinutes)||0)];if(l.videoUrl)parts.push('Video');if(l.documentUrl)parts.push('Document');if(l.resources.length)parts.push(`${l.resources.length} link${l.resources.length===1?'':'s'}`);if(l.content.trim())parts.push('Text');if(l.exercise.trim())parts.push('Exercise');return parts.join(' · ');}
function lessonEditor(l,i){
  const upload=builderUploads[l.key]||{};
  return `<div class="lesson-editor" id="lesson-editor-${l.key}"><div class="editor-fields">${builderField('Lesson title',`l-title-${l.key}`,`<input id="l-title-${l.key}" data-l="${l.key}" data-f="title" value="${esc(l.title)}" maxlength="150">`)}${builderField('Lesson duration (minutes)',`l-dur-${l.key}`,`<input id="l-dur-${l.key}" type="number" min="0" max="1000" data-l="${l.key}" data-f="durationMinutes" value="${esc(l.durationMinutes)}">`)}${builderField('Module (optional)',`l-mod-${l.key}`,`<input id="l-mod-${l.key}" list="module-names" data-l="${l.key}" data-f="moduleTitle" value="${esc(l.moduleTitle||'')}" maxlength="150" placeholder="e.g. Module 1: Foundations">`)}</div>
  <label for="l-desc-${l.key}">Lesson description</label><textarea id="l-desc-${l.key}" rows="2" maxlength="2000" data-l="${l.key}" data-f="description">${esc(l.description)}</textarea>
  <div class="material-grid"><div><label for="l-video-${l.key}">Video URL</label><input id="l-video-${l.key}" type="url" data-l="${l.key}" data-f="videoUrl" value="${esc(l.videoUrl)}" placeholder="YouTube or Vimeo link, or a direct .mp4 link"><label class="file-label" for="l-vfile-${l.key}">…or upload a video file (MP4/WebM, up to 50 MB)</label><input id="l-vfile-${l.key}" type="file" accept=".mp4,.webm" data-upload="video" data-l="${l.key}">${upload.video?`<p class="upload-state ${upload.video.error?'error':''}" role="status">${esc(upload.video.text)}</p>`:''}<div class="editor-fields video-settings">${builderField('Video length (seconds)',`l-vsec-${l.key}`,`<input id="l-vsec-${l.key}" type="number" min="0" max="36000" step="0.1" data-l="${l.key}" data-f="videoSeconds" value="${esc(l.videoSeconds||0)}">`)}${builderField('Complete at (% watched)',`l-vpct-${l.key}`,`<input id="l-vpct-${l.key}" type="number" min="50" max="100" data-l="${l.key}" data-f="completionPercent" value="${esc(l.completionPercent||90)}">`)}</div><label class="file-label" for="l-cap-${l.key}">Captions (.vtt) link, optional</label><input id="l-cap-${l.key}" data-l="${l.key}" data-f="captionsUrl" value="${esc(l.captionsUrl||'')}" placeholder="https://...vtt"><p class="muted">Watch tracking applies to uploaded video files with a length set. YouTube and Vimeo lessons are marked complete by the employee.</p>${l.hasActivity?'<p class="notice">This lesson includes a scored practical exercise. It is kept when you save.</p>':''}</div>
  <div><span class="field-label">PDF or document</span>${l.documentUrl?`<p class="attached"><a href="${esc(l.documentUrl)}" target="_blank" rel="noopener">${icon('file')} ${esc(l.documentName||'Attached document')}</a> <button type="button" class="auth-link" data-builder="document-remove" data-l="${l.key}">Remove</button></p>`:'<p class="muted">No document attached.</p>'}<label class="file-label" for="l-dfile-${l.key}">${l.documentUrl?'Replace':'Upload'} a PDF, Word, PowerPoint or Excel file (up to 50 MB)</label><input id="l-dfile-${l.key}" type="file" accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv" data-upload="document" data-l="${l.key}">${upload.document?`<p class="upload-state ${upload.document.error?'error':''}" role="status">${esc(upload.document.text)}</p>`:''}</div></div>
  <span class="field-label">External learning resources</span>${l.resources.map((r,j)=>`<div class="resource-row"><input aria-label="Resource ${j+1} title" placeholder="Title" data-l="${l.key}" data-r="${j}" data-f="title" value="${esc(r.title)}" maxlength="150"><input aria-label="Resource ${j+1} link" type="url" placeholder="https://" data-l="${l.key}" data-r="${j}" data-f="url" value="${esc(r.url)}" maxlength="2000"><button type="button" class="auth-link" data-builder="resource-remove" data-l="${l.key}" data-index="${j}" aria-label="Remove resource ${j+1}">Remove</button></div>`).join('')||'<p class="muted">No external resources yet.</p>'}
  <div class="inline-field"><button type="button" class="btn secondary" data-builder="resource-add" data-l="${l.key}">Add resource link</button><select aria-label="Add an official learning source" data-source="${l.key}">${options(OFFICIAL_SOURCES.map(([title],k)=>[k,title]),'','Add an official learning source…')}</select></div>
  <p class="muted">Link to the source; don't paste copyrighted material from other platforms into lessons.</p>
  <label for="l-content-${l.key}">Text-based learning content</label><p class="muted">Formatting: ## heading, ### subheading, - bullet (indent two spaces to nest), 1. numbered step, | table | rows |, &#96;&#96;&#96; code block &#96;&#96;&#96;, **bold**, &#96;code&#96;. Headings named "Learning objectives" and "Key takeaways" are highlighted.</p><textarea id="l-content-${l.key}" rows="6" maxlength="100000" data-l="${l.key}" data-f="content">${esc(l.content)}</textarea>
  <label for="l-ex-${l.key}">Practical exercise (optional)</label><textarea id="l-ex-${l.key}" rows="3" maxlength="5000" data-l="${l.key}" data-f="exercise" placeholder="Describe a task. Employees submit a written response to complete the lesson.">${esc(l.exercise)}</textarea></div>`;
}
function lessonRow(l,i){
  const d=courseDraft,open=d.openLesson===l.key;
  return `<li class="lesson-row ${open?'open':''}"><div class="lesson-row-head"><span class="lesson-num">${i+1}</span><div class="lesson-row-title"><strong>${esc(l.title||'Untitled lesson')}</strong><small>${esc(lessonSummary(l))}${l.hasProgress?' · Employees have completed this lesson':''}</small></div><div class="table-actions"><button type="button" data-builder="lesson-move" data-l="${l.key}" data-dir="-1" ${i===0?'disabled':''} aria-label="Move lesson ${i+1} up">↑</button><button type="button" data-builder="lesson-move" data-l="${l.key}" data-dir="1" ${i===d.lessons.length-1?'disabled':''} aria-label="Move lesson ${i+1} down">↓</button><button type="button" data-builder="lesson-open" data-l="${l.key}" aria-expanded="${open}">${open?'Close':'Edit'}</button><button type="button" data-builder="lesson-delete" data-l="${l.key}" ${l.hasProgress?'disabled title="Employees have completed this lesson"':''}>Delete</button></div></div>${open?lessonEditor(l,i):''}</li>`;
}
// Consecutive lessons with the same module name are shown, saved and played as one module.
function builderStepLessons(){
  const d=courseDraft,modules=[...new Set(d.lessons.map(l=>(l.moduleTitle||'').trim()).filter(Boolean))];let previous=null;
  const rows=d.lessons.map((l,i)=>{const name=(l.moduleTitle||'').trim(),head=name&&name!==previous?`<li class="module-heading">${icon('book')}<span>${esc(name)}</span></li>`:'';previous=name||null;return head+lessonRow(l,i);}).join('');
  return `<h3 class="sub-heading">Learning materials</h3><p class="muted">Organise lessons into modules, in the order employees should take them. Each lesson can combine written content, a PDF or document, external links and a practical exercise.</p><datalist id="module-names">${modules.map(m=>`<option value="${esc(m)}">`).join('')}</datalist><ol class="lesson-list">${rows||'<li class="muted">No lessons yet.</li>'}</ol><div class="admin-actions"><button type="button" class="btn" data-builder="lesson-add">+ Add lesson</button><button type="button" class="btn secondary" data-builder="module-add">+ Add module</button></div>`;
}
function builderStepAssessment(){
  const a=courseDraft.assessment;
  if(!a)return `<div class="empty-state"><h3>No assessment yet</h3><p class="muted">Add multiple-choice and coding questions. When added, employees must pass it to earn the course certificate. Practical assignments are set per lesson in Step 2.</p><button type="button" class="btn" data-builder="assessment-add">Add an assessment</button></div>`;
  const lock=a.locked?'disabled':'';
  return `${a.locked?'<div class="notice">Employees have attempted this assessment, so its questions are locked to preserve their results. You can still change the pass mark, attempts and time limit.</div>':''}<div class="editor-fields">${builderField('Assessment title','a-title',`<input id="a-title" data-a="title" value="${esc(a.title)}" maxlength="150" placeholder="${esc((courseDraft.title||'Course')+' assessment')}">`)}${builderField('Passing score (%)','a-pass',`<input id="a-pass" type="number" min="1" max="100" data-a="passPercent" value="${esc(a.passPercent)}">`)}${builderField('Attempts allowed','a-attempts',`<input id="a-attempts" type="number" min="1" max="3" data-a="maxAttempts" value="${esc(a.maxAttempts)}">`)}</div><div class="editor-fields">${builderField('Time limit (minutes)','a-time',`<input id="a-time" type="number" min="1" max="240" data-a="timeLimitMinutes" value="${esc(a.timeLimitMinutes)}">`)}</div>
  <ol class="question-list">${a.questions.map((q,i)=>`<li class="question-card"><div class="section-heading"><h3>Question ${i+1} ${q.coding?'<span class="tag gray">CODING</span>':''}</h3>${a.locked?'':`<button type="button" class="auth-link" data-builder="question-remove" data-index="${i}">Remove question</button>`}</div><label for="q-${i}">Question</label><textarea id="q-${i}" rows="2" maxlength="2000" data-q="${i}" data-f="prompt" ${lock}>${esc(q.prompt)}</textarea>${q.coding?`<label for="qc-${i}">Code snippet</label><textarea id="qc-${i}" class="curriculum-json" rows="4" maxlength="5000" spellcheck="false" data-q="${i}" data-f="code" ${lock}>${esc(q.code)}</textarea>`:''}<fieldset class="option-list"><legend>Answer options (select the correct answer)</legend>${q.options.map((o,j)=>`<div class="option-row"><input type="radio" name="correct-${i}" aria-label="Option ${j+1} is correct" data-q="${i}" data-correct="${j}" ${Number(q.correct)===j?'checked':''} ${lock}><input aria-label="Option ${j+1}" data-q="${i}" data-o="${j}" value="${esc(o)}" maxlength="1000" ${lock}>${!a.locked&&q.options.length>2?`<button type="button" class="auth-link" data-builder="option-remove" data-index="${i}" data-option="${j}" aria-label="Remove option ${j+1}">Remove</button>`:''}</div>`).join('')}</fieldset>${!a.locked&&q.options.length<6?`<button type="button" class="auth-link" data-builder="option-add" data-index="${i}">+ Add option</button>`:''}<label for="qe-${i}">Explanation shown after submission</label><input id="qe-${i}" data-q="${i}" data-f="explanation" value="${esc(q.explanation)}" maxlength="2000" ${lock}></li>`).join('')}</ol>
  ${a.locked?'':'<div class="admin-actions"><button type="button" class="btn secondary" data-builder="question-add">+ Multiple-choice question</button><button type="button" class="btn secondary" data-builder="question-add" data-coding="1">+ Coding question</button><button type="button" class="auth-link" data-builder="assessment-remove">Remove assessment</button></div>'}<p class="muted">Each attempt shows the questions in random order and is scored on the server. Employees see whether each answer was right and the explanation, never the answer key.</p>`;
}
function builderStepPreview(){
  const d=courseDraft,a=d.assessment;
  return `<div class="notice">This is how employees will see the course${d.id&&d.savedStatus?'':' once saved'}. Unsaved changes are included in this preview.</div><div class="preview-head"><span class="tag">${esc(d.category)}</span><h2>${esc(d.title||'Untitled course')}</h2><p class="muted">${esc(d.description)}</p><p class="muted">${esc(capital(d.difficulty))} · ${esc(fmtDuration(Number(d.durationMinutes)||0))} · ${d.lessons.length} lesson${d.lessons.length===1?'':'s'}${a?` · Assessment pass mark ${a.passPercent}%`:''}</p></div><div class="course-player builder-preview">${d.lessons.map((l,i)=>`<article class="panel lesson-content module-view preview-lesson">${lessonHeader(l,{unit:'Lesson',index:i,total:d.lessons.length})}${lessonBody(l)}</article>`).join('')||'<p class="muted">No lessons yet.</p>'}${a?`<section class="panel lesson-content"><span class="tag">ASSESSMENT</span><h2>${esc(a.title||(d.title||'Course')+' assessment')}</h2><p class="muted">${a.questions.length} questions · ${a.timeLimitMinutes} minutes · pass mark ${a.passPercent}% · ${a.maxAttempts} attempt${Number(a.maxAttempts)===1?'':'s'}</p>${a.questions.map((q,i)=>`<fieldset class="question"><legend><span>${i+1}.</span> ${esc(q.prompt)}</legend>${q.coding&&q.code?`<pre><code>${esc(q.code)}</code></pre>`:''}${q.options.map((o,j)=>`<label class="answer"><input type="radio" disabled><span class="answer-letter" aria-hidden="true">${String.fromCharCode(65+j)}</span><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}</section>`:''}</div>`;
}
function builderStepReview(){
  const d=courseDraft,a=d.assessment,problems=publishProblems(),dept=orgData().departments.find(x=>x.id===d.departmentId);
  const lessons=d.lessons.filter(l=>!blankLesson(l)),modules=new Set(lessons.map(l=>(l.moduleTitle||'').trim()).filter(Boolean)).size;
  const checklist=[[1,'Course basics'],[2,'Learning materials'],[3,'Assessment']].map(([n,label])=>{const list=problems.filter(p=>p.includes(`(Step ${n})`));
    return list.length?list.map(p=>`<li class="todo">${esc(p.replace(` (Step ${n})`,''))} <button type="button" class="auth-link" data-builder="step" data-step="${n}">Go to step ${n}</button></li>`).join(''):`<li class="done">${label}${n===3&&!a?': no assessment added (optional)':' complete'}</li>`;}).join('');
  const summary=[[modules,'Modules'],[lessons.length,'Lessons'],[lessons.filter(l=>l.documentUrl).length,'Documents'],[lessons.reduce((n,l)=>n+l.resources.length,0),'Resource links'],[a?a.questions.length:0,'Assessment questions']].map(([n,label])=>`<div><strong>${n}</strong><span>${label}</span></div>`).join('');
  const state=d.savedStatus==='published'?`<div class="notice success">This course is published. Use Save changes to update what employees see.</div><button type="button" class="btn secondary" data-builder="save-draft" ${builderBusy?'disabled':''}>Unpublish (move to draft)</button>`
    :d.savedStatus==='archived'?'<div class="notice">This course is archived and hidden from employees. Publish it to make it available again.</div>'
    :`<p class="muted">Save a draft to continue later: drafts are visible only to course managers and reopen from the catalogue. Publish when the checklist is complete.</p>`;
  return `<h3 class="sub-heading">Publishing checklist</h3><ul class="checklist">${checklist}</ul><div class="save-summary review-summary">${summary}</div><p class="muted">Available to: <b>${d.visibility==='department'?esc(dept?.name||'the selected department')+' only, plus employees assigned this course':'all employees'}</b>. Published courses appear on the Courses page, and in My Learning for the employees they are assigned to.</p>${state}<h3 class="sub-heading">Course preview</h3>${builderStepPreview()}`;
}
function courseBuilder(){
  if(!courseDraft)return builderStatus?`<div class="notice" role="alert">${esc(builderStatus)} <button class="auth-link" data-builder="reload">Try again</button></div>`:stateBlock({loading:true},'course','builder');
  const d=courseDraft,views=[builderStepCourse,builderStepLessons,builderStepAssessment,builderStepReview],saved=d.savedStatus||'draft',last=builderStep===BUILDER_STEPS.length;
  const saveLabel=builderBusy?'Saving…':saved==='published'?'Save changes':saved==='archived'?'Save':'Save draft';
  const forward=!last?`<button type="button" class="btn" data-builder="step" data-step="${builderStep+1}">Next: ${esc(BUILDER_STEPS[builderStep])} ${icon('arrow')}</button>`
    :saved==='published'?'':`<button type="button" class="btn" data-builder="publish" ${publishProblems().length||builderBusy?'disabled':''}>${builderBusy?'Publishing…':'Publish course'}</button>`;
  return `<section class="panel admin-form course-editor" id="course-builder"><div class="section-heading"><div><span class="tag">${d.id?'EDIT COURSE':'NEW COURSE'} · ${esc((d.savedStatus||'not saved').toUpperCase())}</span><h2>${d.id?esc(d.title||'Edit course'):'Create a learning opportunity'}</h2></div><span class="muted step-count">Step ${builderStep} of ${BUILDER_STEPS.length}</span></div>${builderSteps()}${importReportPanel(d)}${builderStatus?`<div class="notice" role="alert">${esc(builderStatus)}</div>`:''}<div class="builder-body">${views[builderStep-1]()}</div><div class="builder-footer"><button type="button" class="btn secondary" data-builder="step" data-step="${builderStep-1}" ${builderStep===1?'disabled':''}>Back</button><button type="button" class="btn secondary" data-builder="save" ${builderBusy?'disabled':''}>${saveLabel}</button>${forward}</div></section>`;
}
// Shown once a course is first published: assign it now, or return to the catalogue and assign it later.
function publishedPanel(){
  const p=publishedCourse,assign=can('courses.assign');
  return `<section class="panel publish-done" role="status"><span class="tag success">PUBLISHED</span><h2>“${esc(p.title)}” is published</h2><p class="muted">Employees ${p.visibility==='department'?'in its department':''} can now find it on the Courses page. Assigned courses also appear in each employee's My Learning with the deadline you set.</p><div class="admin-actions">${assign?'<button type="button" class="btn" data-act="published-assign">Assign this course now</button>':''}<button type="button" class="btn secondary" data-act="course-close">Back to Course Management</button><button type="button" class="auth-link" data-act="published-edit">Keep editing</button></div>${assign?'<p class="muted">To assign it later, use Assign next to the course in the catalogue.</p>':''}</section>`;
}
const COURSE_FLOW=['Course Management','Create Course','Learning Materials','Assessment','Review & Publish','Course Assignment','Progress Tracking'];
function courseFlow(){
  const editing=Boolean(courseDraft)&&!publishedCourse,steps=can('courses.assign')?COURSE_FLOW:COURSE_FLOW.slice(0,5);
  const current=publishedCourse?[4]:editing?[builderStep]:courseTab==='assignments'?[5,6]:courseTab==='reminders'?[]:[0];
  return `<ol class="workflow course-flow" aria-label="Course workflow">${steps.map((label,i)=>`<li class="${current.includes(i)?'current':''}" ${current.includes(i)?'aria-current="step"':''}><span>${i+1}</span>${label}</li>`).join('')}</ol>`;
}
function courseManagerTabs(){
  const tabs=[['catalog','Courses'],...(can('courses.assign')?[['assignments','Assign a Course']]:[]),...(['admin','hr'].includes(currentUser.role)?[['reminders','Reminders']]:[])];
  if(tabs.length<2)return '';
  return `<div class="compliance-tabs course-tabs" role="tablist" aria-label="Course management">${tabs.map(([id,label])=>`<button type="button" role="tab" aria-selected="${courseTab===id}" class="${courseTab===id?'active':''}" data-act="course-tab" data-tab="${id}">${esc(label)}</button>`).join('')}</div>`;
}
// Assign a Course has its own header (breadcrumb back to Manage Courses) in place of the page intro and tabs.
const assignPageOpen=()=>courseTab==='assignments'&&can('courses.assign')&&!publishedCourse&&!courseDraft&&!editingCourse&&!(courseAddMode==='generate'&&generateState);
function assignPageHeader(){return `<nav class="breadcrumb" aria-label="Breadcrumb"><button type="button" class="auth-link" data-act="course-tab" data-tab="catalog">Manage Courses</button><span aria-hidden="true">›</span><span aria-current="page">Assign a Course</span></nav><div class="intro assign-intro"><div><h1>Assign a Course</h1><p>Assign training to employees and manage completion deadlines.</p></div></div>`;}
// Course Management → Create Course (4-step wizard) → Review & Publish → Assign → Track progress.
// The wizard, the AI generator and the 3-module editor each replace the tabs while open.
function courseManager(){
  const course=editingCourse?adminState.courses.find(c=>c.id===editingCourse):null,back='<button type="button" class="auth-link back-link" data-act="course-close">← Back to Course Management</button>';
  if(courseTab==='assignments'&&!can('courses.assign')||courseTab==='reminders'&&!['admin','hr'].includes(currentUser.role))courseTab='catalog';
  if(publishedCourse)return `${courseFlow()}${adminNotice()}${publishedPanel()}`;
  if(course&&course.format!=='lessons')return `${back}${adminNotice()}${legacyCourseManager()}`;
  if(courseAddMode==='generate'&&generateState)return `${back}${adminNotice()}${courseGenerator()}`;
  if(courseDraft||editingCourse)return `${courseFlow()}${back}${adminNotice()}${courseBuilder()}${course&&courseDraft?courseResources(course):''}`;
  if(courseTab==='assignments')return assignPageHeader()+adminNotice()+courseDeadlineSettings();
  const view=courseTab==='reminders'?reminderManagement():`${courseAddMode==='choose'?addCourseChooser():''}${courseCatalogTable()}`;
  return `${courseFlow()}${courseManagerTabs()}${adminNotice()}${view}`;
}
const findLesson=key=>courseDraft?.lessons.find(l=>l.key===key);
const BUILDER_ACTIONS={
  step:el=>{const n=Number(el.dataset.step);if(n>=1&&n<=BUILDER_STEPS.length){builderStep=n;builderStatus='';}},
  'lesson-add':()=>{const l=newLesson();l.moduleTitle=courseDraft.lessons.at(-1)?.moduleTitle||'';courseDraft.lessons.push(l);courseDraft.openLesson=l.key;},
  'module-add':()=>{const count=new Set(courseDraft.lessons.map(l=>(l.moduleTitle||'').trim()).filter(Boolean)).size,l=newLesson();l.moduleTitle=`Module ${count+1}`;courseDraft.lessons.push(l);courseDraft.openLesson=l.key;},
  'lesson-open':el=>{courseDraft.openLesson=courseDraft.openLesson===el.dataset.l?null:el.dataset.l;},
  'lesson-move':el=>{const list=courseDraft.lessons,i=list.findIndex(l=>l.key===el.dataset.l),j=i+Number(el.dataset.dir);if(j>=0&&j<list.length)[list[i],list[j]]=[list[j],list[i]];},
  'lesson-delete':el=>{const l=findLesson(el.dataset.l);if(l&&!l.hasProgress&&confirm(`Delete lesson “${l.title||'Untitled lesson'}”? This takes effect when you save.`))courseDraft.lessons=courseDraft.lessons.filter(x=>x!==l);},
  'resource-add':el=>{findLesson(el.dataset.l).resources.push({title:'',url:''});},
  'resource-remove':el=>{findLesson(el.dataset.l).resources.splice(Number(el.dataset.index),1);},
  'document-remove':el=>{const l=findLesson(el.dataset.l);l.documentUrl='';l.documentName='';},
  'assessment-add':()=>{courseDraft.assessment=newAssessment();},
  'assessment-remove':()=>{if(confirm('Remove the assessment? Employees will no longer need to pass it for the certificate once you save.'))courseDraft.assessment=null;},
  'question-add':el=>{courseDraft.assessment.questions.push(newQuestion(el.dataset.coding==='1'));},
  'question-remove':el=>{courseDraft.assessment.questions.splice(Number(el.dataset.index),1);},
  'option-add':el=>{courseDraft.assessment.questions[Number(el.dataset.index)].options.push('');},
  'option-remove':el=>{const q=courseDraft.assessment.questions[Number(el.dataset.index)],j=Number(el.dataset.option);q.options.splice(j,1);if(Number(q.correct)>=q.options.length||Number(q.correct)===j)q.correct=0;},
  save:()=>saveCourseBuilder(),
  'save-draft':()=>saveCourseBuilder('draft'),
  publish:()=>saveCourseBuilder('published'),
  close:()=>{closeCourseEditor();},
  reload:()=>openCourseBuilder(editingCourse,builderStep),
};
document.addEventListener('click',event=>{
  const el=event.target.closest?.('[data-builder]');if(!el||!courseDraft&&!['reload'].includes(el.dataset.builder)||el.disabled)return;
  const action=BUILDER_ACTIONS[el.dataset.builder];if(!action)return;
  event.preventDefault();
  if(!['step','lesson-open','close','reload','save','save-draft','publish'].includes(el.dataset.builder))builderDirty=true;
  const result=action(el);
  if(!(result instanceof Promise))render();
});
function builderInput(el){
  if(!courseDraft||!el.closest?.('#course-builder'))return;
  builderDirty=true;
  const d=courseDraft,value=el.type==='checkbox'?el.checked:el.value;
  if(el.dataset.d){d[el.dataset.d]=value;if(el.dataset.d==='status'||el.dataset.d==='visibility')render();}
  else if(el.dataset.a){d.assessment[el.dataset.a]=value;}
  else if(el.dataset.l&&el.dataset.r!==undefined){findLesson(el.dataset.l).resources[Number(el.dataset.r)][el.dataset.f]=value;}
  else if(el.dataset.l&&el.dataset.f){findLesson(el.dataset.l)[el.dataset.f]=value;}
  else if(el.dataset.q!==undefined){const q=d.assessment.questions[Number(el.dataset.q)];if(el.dataset.correct!==undefined)q.correct=Number(el.dataset.correct);else if(el.dataset.o!==undefined)q.options[Number(el.dataset.o)]=value;else q[el.dataset.f]=value;}
}
async function builderUpload(el){
  const l=findLesson(el.dataset.l),file=el.files?.[0],kind=el.dataset.upload;if(!l||!file)return;
  builderUploads[l.key]={...builderUploads[l.key],[kind]:{text:`Uploading ${file.name}…`}};render();
  try{
    const material=await uploadMaterial(file);
    if(kind==='video')l.videoUrl=material.url;else{l.documentUrl=material.url;l.documentName=material.name;}
    builderUploads[l.key][kind]={text:`Uploaded ${material.name} (${Math.max(1,Math.round(material.size/1024))} KB). Save the course to keep it in this lesson.`};
  }catch(error){builderUploads[l.key][kind]={text:error.message,error:true};}
  render();
}
document.addEventListener('input',event=>builderInput(event.target));
document.addEventListener('change',event=>{
  const el=event.target;
  if(el.dataset?.upload&&el.closest?.('#course-builder'))return builderUpload(el);
  if(el.dataset?.source&&courseDraft){const source=OFFICIAL_SOURCES[Number(el.value)];if(source){findLesson(el.dataset.source).resources.push({title:source[0],url:source[1]});render();}return;}
  builderInput(el);
});
function adminPage(page){
  const names={'admin-users':['Users & teams','Add employees, organise departments and job roles, and manage access.'],'admin-courses':['Course management','Create courses, publish them, assign them and track employee progress.'],'admin-audit':['Activity log','A history of administrative actions.']};
  if(!names[page])return '';
  const header=page==='admin-courses'&&assignPageOpen()?'':`<div class="intro"><div><h1>${names[page][0]}</h1><p>${names[page][1]}</p></div><span class="tag">${page==='admin-audit'?'ADMIN ONLY':'AUTHORISED STAFF'}</span></div>`;
  return `${header}${page==='admin-users'?userManager():page==='admin-courses'?courseManager():`<section class="panel admin-table-scroll"><table class="admin-table"><thead><tr><th>Administrator</th><th>Action</th><th>Details</th><th>When</th></tr></thead><tbody>${adminState.events.map(event=>`<tr><td>${esc(event.admin_name)}</td><td>${esc(event.action.replaceAll('_',' ').replace('candidate','employee'))}</td><td>${esc(event.detail||event.target_id)}</td><td>${esc(new Date(event.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}))}</td></tr>`).join('')||'<tr><td colspan="4">No administrator actions yet.</td></tr>'}</tbody></table></section>`}`;
}
function bindAdmin(){
  if(!currentUser||currentUser.role==='employee'||currentUser.mustChangePassword)return;
  const dismiss=document.getElementById('dismiss-credentials');if(dismiss)dismiss.onclick=()=>{provisionedCredentials=null;render();};
  const generator=document.getElementById('generate-password');if(generator)generator.onclick=()=>{const chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#';document.getElementById('new-candidate-password').value=Array.from(crypto.getRandomValues(new Uint8Array(18)),n=>chars[n%chars.length]).join('');};
  const field=id=>document.getElementById(id)?.value||null;
  const create=document.getElementById('create-candidate-form');if(create)create.onsubmit=async event=>{event.preventDefault();const button=create.querySelector('button[type="submit"]');if(button.disabled)return;button.disabled=true;const password=document.getElementById('new-candidate-password').value,email=document.getElementById('new-candidate-email').value;const target=document.getElementById('new-candidate-target')?.value||'';try{const created=await api('admin/candidates',{name:document.getElementById('new-candidate-name').value,email,password,role:document.getElementById('new-candidate-role').value,departmentId:field('new-candidate-department'),jobRoleId:field('new-candidate-jobrole'),managerId:field('new-candidate-manager'),jobTitle:field('new-candidate-title')||'',joiningDate:field('new-candidate-joining')});let targetNote=target?` with a yearly training target of ${target} hours`:'';if(target){try{await api('manage/training-targets',{employeeIds:[created.candidate.id],hours:Number(target)});}catch(error){targetNote=`, but the training target was not saved (${error.message}) — set it in their row below`;}}await loadAdminState();refreshData('people','org','dash','onb');provisionedCredentials={email,password};adminMessage=`Employee added${targetNote}. A password change is required at first login.${created.onboarding?.message?' '+created.onboarding.message:''}`;render();}catch(error){document.getElementById('candidate-form-status').textContent=error.message;button.disabled=false;}};
  const search=document.getElementById('user-search');if(search)search.oninput=()=>document.querySelectorAll('[data-user-row]').forEach(row=>row.classList.toggle('hidden',!row.dataset.userRow.includes(search.value.toLowerCase().trim())));
  document.querySelectorAll('[data-reset-user]').forEach(button=>button.onclick=()=>{resetCandidate=adminState.candidates.find(u=>u.id===button.dataset.resetUser);provisionedCredentials=null;render();});
  const cancel=document.getElementById('cancel-reset');if(cancel)cancel.onclick=()=>{resetCandidate=null;render();};
  const reset=document.getElementById('reset-candidate-form');if(reset)reset.onsubmit=async event=>{event.preventDefault();const password=document.getElementById('reset-temporary-password').value;const button=reset.querySelector('button');button.disabled=true;try{await api('admin/candidates/'+resetCandidate.id+'/reset-password',{password});provisionedCredentials={email:resetCandidate.email,password};resetCandidate=null;adminMessage='Temporary password reset. Previous sessions have been signed out.';await loadAdminState();render();}catch(error){document.getElementById('reset-form-status').textContent=error.message;button.disabled=false;}};
  document.querySelectorAll('[data-toggle-user]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await api('admin/candidates/'+button.dataset.toggleUser+'/status',{active:button.dataset.enable==='true'});await loadAdminState();refreshData('people','dash');adminMessage='Account access updated.';render();}catch(error){toast(error.message);button.disabled=false;}});
  document.querySelectorAll('[data-user-records]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{recordPreview=await api('admin/candidates/'+button.dataset.userRecords+'/records');render();}catch(error){toast(error.message);button.disabled=false;}});
  const close=document.getElementById('close-records');if(close)close.onclick=()=>{recordPreview=null;render();};
  const fresh=document.getElementById('new-course');if(fresh)fresh.onclick=startNewCourse;
  const stop=document.getElementById('cancel-course-edit');if(stop)stop.onclick=()=>{editingCourse=null;courseDraft=null;render();};
  // Lesson-based courses reopen in the step-by-step builder; 3-module courses keep their curriculum editor.
  document.querySelectorAll('[data-edit-course]').forEach(button=>button.onclick=()=>{const course=adminState.courses.find(c=>c.id===button.dataset.editCourse);if(course?.format==='lessons')return openCourseBuilder(course.id);editingCourse=button.dataset.editCourse;courseDraft=null;adminMessage='';render();});
  const editor=document.getElementById('course-editor-form');if(editor)editor.onsubmit=async event=>{event.preventDefault();const button=editor.querySelector('button[type="submit"]');button.disabled=true;try{let content;try{content=JSON.parse(document.getElementById('course-content').value);}catch{throw new Error('The curriculum JSON is invalid. Please check its syntax.');}
    const number=id=>document.getElementById(id)?Number(document.getElementById(id).value):undefined;
    const metadata={difficulty:field('course-difficulty')||undefined,durationMinutes:number('course-duration'),departmentId:field('course-department'),passPercent:number('course-pass'),maxAttempts:number('course-attempts'),postAssessmentId:field('course-post'),...(document.getElementById('course-trainer')?{trainerId:field('course-trainer')}:{})};
    Object.keys(metadata).forEach(key=>metadata[key]===undefined&&delete metadata[key]);
    const result=await api('admin/courses',{...(editingCourse?{id:editingCourse}:{}),title:document.getElementById('course-title').value,category:document.getElementById('course-category').value,description:document.getElementById('course-description').value,status:document.getElementById('course-status').value,content,...metadata});editingCourse=result.course.id;await loadAdminState();courseCatalog=(await api('courses')).courses;refreshData('org','dash','me-dash');adminMessage='Course saved. '+(result.course.status==='published'?'Employees can now access it.':'Only course managers can see this course.');render();}catch(error){document.getElementById('course-form-status').textContent=error.message;button.disabled=false;}};
}

// ---------------------------------------------------------------- Manage Courses: assignment form and row search
function openAssignment(courseId){
  closeCourseEditor();deadlineCourseId=courseId;courseTab='assignments';assignDraft=newAssignDraft();adminMessage='';
  if(location.hash!=='#admin-courses')location.hash='admin-courses';
  render();window.scrollTo?.(0,0);
}
// The assignment form keeps what has been entered when the page re-renders (for example, after choosing another course).
function assignInput(el){
  if(!assignDraft||!el.closest?.('#assign-form'))return;
  if(el.name==='requirement')assignDraft.mandatory=el.value==='mandatory';
  else if(el.name==='targetText'){const text=el.value.trim(),match=peopleData().find(p=>employeeLabel(p)===text);assignDraft.targetText=el.value;assignDraft.targetId=match?.id||'';}
  else if(['targetId','deadline','note'].includes(el.name))assignDraft[el.name]=el.value;
  else return;
  updateAssignSummary();
}
document.addEventListener('input',event=>assignInput(event.target));
document.addEventListener('change',event=>assignInput(event.target));
// Search boxes filter table rows in place, so typing never re-renders the page; the text is kept for the next render.
const ROW_SEARCH={courses:value=>{catalogFilters.q=value;}};
document.addEventListener('input',event=>{
  const el=event.target,kind=el.dataset?.rowSearch;if(!ROW_SEARCH[kind])return;
  ROW_SEARCH[kind](el.value);
  document.querySelectorAll(`[data-search-row="${kind}"]`).forEach(row=>{row.hidden=rowHidden(row.dataset.search||'',el.value);});
});

// Record search: wait for a pause in typing, reload the first page, and keep the cursor in the box.
let recordsSearchTimer=null;
document.addEventListener('input',event=>{
  const el=event.target;if(!el.dataset||el.dataset.recordsSearch===undefined)return;
  assignRecords.q=el.value;assignRecords.page=1;clearTimeout(recordsSearchTimer);
  recordsSearchTimer=setTimeout(()=>{render();const box=document.getElementById('records-search');if(box&&box.focus){box.focus();const end=box.value.length;box.setSelectionRange?.(end,end);}},350);
});
