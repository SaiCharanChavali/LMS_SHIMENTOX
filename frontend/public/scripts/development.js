// Employee learning & development pages. Every figure is loaded from the authenticated API; nothing here is sample data.
// The backend enforces all permissions; PERMS below only decides which controls to show.
const ROLE_LABELS={admin:'Administrator',hr:'HR / L&D Admin',trainer:'Trainer',manager:'Manager',employee:'Employee'};
const LEVEL_LABELS=['Not assessed','Beginner','Intermediate','Advanced','Expert'];
const PERMS={'users.manage':['admin','hr'],'org.manage':['admin','hr'],'courses.manage':['admin','hr','trainer'],'courses.assign':['admin','hr','manager'],'paths.manage':['admin','hr','trainer'],'skills.manage':['admin','hr'],'competencies.manage':['admin','hr','manager'],'skills.record':['admin','hr','manager'],'assessments.manage':['admin','hr','trainer'],'sessions.manage':['admin','hr','trainer'],'reports.view':['admin','hr','manager','trainer'],'audit.view':['admin']};
const KIND_LABELS={pre:'Pre-training',post:'Post-training',knowledge:'Knowledge check',skill:'Skill assessment'};
const STATUS_TAGS={completed:['Completed','success'],overdue:['Overdue','danger'],in_progress:['In progress',''],not_started:['Not started','gray'],locked:['Locked','gray'],unavailable:['Unavailable','gray']};
const can=permission=>Boolean(currentUser&&PERMS[permission]?.includes(currentUser.role));
const isLearner=()=>Boolean(currentUser&&currentUser.role!=='admin');
let pageCache={},devMessage='',devFilters={dashboard:{},report:{type:'enrollments',page:1}},notificationState={items:[],unread:0,open:false};
let pathEditor=null,pathAssign=null,pathProgressId=null,sessionEditor=null,sessionRoster=null,assessmentEditor=null,assessmentAttemptsId=null,activeAssessment=null,assessmentResult=null,editUserId=null,previewCourseId=null,competencyRole='',historyPage=1,courseFilter='all',assistantAnswer=null;

function resetDevelopment(){selectedLessonId=null;inlineAttempt=null;inlineResult=null;if(typeof courseDraft!=='undefined'){courseDraft=null;builderStep=1;}pageCache={};devMessage='';devFilters={dashboard:{},report:{type:'enrollments',page:1}};notificationState={items:[],unread:0,open:false};pathEditor=pathAssign=pathProgressId=sessionEditor=sessionRoster=assessmentEditor=assessmentAttemptsId=activeAssessment=assessmentResult=editUserId=previewCourseId=assistantAnswer=null;competencyRole='';historyPage=1;courseFilter='all';}
function loadData(key,path){
  if(pageCache[key])return pageCache[key];
  pageCache[key]={loading:true};
  api(path).then(data=>{pageCache[key]={data};render();}).catch(error=>{pageCache[key]={error:error.message};render();});
  return pageCache[key];
}
// Page data is refetched on navigation so dashboards reflect learning done elsewhere; reference lists stay cached.
function refreshOnNavigate(){for(const key of Object.keys(pageCache))if(!['org','people','assistant'].includes(key))delete pageCache[key];}
function refreshData(...prefixes){for(const key of Object.keys(pageCache))if(prefixes.some(p=>key===p||key.startsWith(p+':')))delete pageCache[key];}
function outdatedServerNotice(){
  if(!serverOutdated||!currentUser)return '';
  return currentUser.role==='admin'
    ?'<div class="notice" role="alert"><strong>The server is running an older version of the portal.</strong><p>The browser loaded the updated pages, but the backend process was started before the update, so new features return “Endpoint was not found”. Stop the server (Ctrl+C in its terminal) and run <code>npm start</code> again. Back up <code>backend/data/lms.sqlite3</code> first; it is upgraded automatically on start.</p></div>'
    :'<div class="notice" role="alert">Some features are temporarily unavailable while the portal is being updated. Please try again later or contact your administrator.</div>';
}
function stateBlock(entry,label,key){
  if(entry.error)return `<div class="notice" role="alert">${esc(entry.error)} <button class="auth-link" data-act="retry" data-key="${esc(key)}">Try again</button></div>`;
  return `<div class="panel state-panel" role="status"><span class="spinner" aria-hidden="true"></span>Loading ${esc(label)}…</div>`;
}
const emptyState=(title,text,action='')=>`<div class="empty-state"><h3>${esc(title)}</h3><p class="muted">${esc(text)}</p>${action}</div>`;
const qs=params=>{const parts=Object.entries(params).filter(([,v])=>v!==undefined&&v!==null&&v!=='').map(([k,v])=>`${encodeURIComponent(k)}=${encodeURIComponent(v)}`);return parts.length?'?'+parts.join('&'):'';};
const fmtDate=v=>v?new Date(v.length===10?v+'T00:00:00':v).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}):'—';
const fmtDateTime=v=>v?new Date(v).toLocaleString('en-IN',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
const fmtDuration=m=>m?(m>=60?`${Math.floor(m/60)} h${m%60?` ${m%60} min`:''}`:`${m} min`):'Duration not set';
const capital=s=>s?String(s).charAt(0).toUpperCase()+String(s).slice(1):'';
const statusTag=s=>{const [label,tone]=STATUS_TAGS[s]||[capital(s),''];return `<span class="tag ${tone}">${esc(label.toUpperCase())}</span>`;};
const tagText=(text,tone='')=>`<span class="tag ${tone}">${esc(String(text).toUpperCase())}</span>`;
const levelTag=l=>`<span class="level level-${Number(l)||0}">${esc(LEVEL_LABELS[l]||LEVEL_LABELS[0])}</span>`;
const meter=(value,label)=>`<div class="meter-row"><div class="meter" role="img" aria-label="${esc(label||'')} ${value}%"><span style="width:${Math.max(0,Math.min(100,Number(value)||0))}%"></span></div><b>${Number(value)||0}%</b></div>`;
const intro=(title,text,tag)=>`<div class="intro"><div><h1>${esc(title)}</h1><p>${esc(text)}</p></div>${tag?`<span class="tag">${esc(tag)}</span>`:''}</div>`;
const panel=(title,body,extra='')=>`<section class="panel"><div class="section-heading"><h2>${esc(title)}</h2>${extra}</div>${body}</section>`;
const kpi=(name,value,label,hint)=>`<div class="stat"><div class="stat-icon">${icon(name)}</div><div><strong>${esc(value)}</strong><small>${esc(label)}</small>${hint?`<small class="stat-hint">${esc(hint)}</small>`:''}</div></div>`;
const options=(items,selected,blank)=>`${blank!==undefined?`<option value="">${esc(blank)}</option>`:''}${items.map(([value,label])=>`<option value="${esc(value)}" ${String(value)===String(selected??'')?'selected':''}>${esc(label)}</option>`).join('')}`;
const devNotice=()=>devMessage?`<div class="notice success" role="status">${esc(devMessage)}</div>`:'';
const orgEntry=()=>currentUser.role!=='employee'?loadData('org','manage/org'):{data:null};
const orgData=()=>orgEntry().data||{departments:[],jobRoles:[],categories:[],skills:[],courses:[],trainers:[],managers:[],levels:[]};
const peopleData=()=>(currentUser.role!=='employee'?loadData('people','manage/people').data?.people:null)||[];
const levelOptions=(selected,blank)=>options([1,2,3,4].map(l=>[l,LEVEL_LABELS[l]]),selected,blank);
const targetChoices=type=>type==='department'?orgData().departments.map(d=>[d.id,d.name]):type==='job_role'?orgData().jobRoles.map(j=>[j.id,j.name]):peopleData().map(p=>[p.id,`${p.name} · ${p.department||'No department'}`]);
function targetFields(prefix,managerOnly){
  const types=managerOnly?[['employee','Employee']]:[['employee','Employee'],['department','Department'],['job_role','Job role']];
  return `<label for="${prefix}-type">Assign to</label><select id="${prefix}-type" name="targetType" data-change="target-type" data-target="${prefix}-target">${options(types,'employee')}</select><label for="${prefix}-target">Target</label><select id="${prefix}-target" name="targetId" required>${options(targetChoices('employee'),'','Select…')}</select>`;
}

// ---------------------------------------------------------------- notifications

async function refreshNotifications(){
  if(!currentUser||currentUser.mustChangePassword)return;
  try{const data=await api('me/notifications');notificationState.items=data.notifications;notificationState.unread=data.unread;render();}catch{/* Notifications are optional; the page keeps working. */}
}
function notificationPanel(){
  if(!notificationState.open)return '';
  const items=notificationState.items;
  const composer=['admin','hr'].includes(currentUser.role)?`<details class="announcement-composer"><summary>Post an announcement</summary><form data-form="announcement-send"><label for="announcement-title">Title</label><input id="announcement-title" name="title" minlength="2" maxlength="200" required><label for="announcement-body">Message</label><textarea id="announcement-body" name="body" minlength="2" maxlength="500" rows="3" required></textarea><button class="btn" type="submit">Publish to everyone</button><p class="form-status" role="status"></p></form></details>`:'';
  return `<div class="notification-panel" role="dialog" aria-label="Notifications"><div class="section-heading"><h3>Notifications</h3>${notificationState.unread?'<button class="auth-link" data-act="notifications-read-all">Mark all read</button>':''}</div>${composer}${items.length?items.map(n=>`<button class="notification ${n.readAt?'':'unread'}" data-act="notification-open" data-id="${n.id}" data-link="${esc(n.link)}"><small class="notification-kind">${esc(n.kind)}</small><strong>${esc(n.title)}</strong><span>${esc(n.body)}</span><small>${esc(fmtDateTime(n.createdAt))}</small></button>`).join(''):'<p class="muted">You are all caught up. Assignments, deadlines, results and certificates will appear here.</p>'}</div>`;
}

// ---------------------------------------------------------------- organisation dashboard (admin, HR, team scope)

function quickActions(){
  return [can('courses.manage')&&`<a class="btn" href="#admin-courses">Create course ${icon('arrow')}</a>`,can('users.manage')&&'<a class="btn secondary" href="#admin-users">Add employee</a>',can('reports.view')&&'<a class="btn secondary" href="#reports">View analytics</a>'].filter(Boolean).join('');
}
function orgDashboard(){
  const filters=devFilters.dashboard,key=`dash:${filters.from||''}:${filters.to||''}`,entry=loadData(key,'manage/dashboard'+qs(filters));
  const head=`<div class="intro"><div><h1>Your people. Their potential.</h1><p>Welcome, ${esc(state.name)}. Employee learning and development across ShimentoX.</p></div><span class="tag">${currentUser.role==='admin'?'ADMINISTRATOR WORKSPACE':'L&D WORKSPACE'}</span></div><div class="admin-actions quick-actions">${quickActions()}</div>`;
  if(!entry.data)return head+stateBlock(entry,'learning metrics',key);
  const d=entry.data,k=d.kpis;
  return head+`<div class="stats">${kpi('users',k.totalEmployees,'Total employees')}${kpi('play',k.activeLearners,'Active learners','Learning activity in the last 30 days')}${kpi('book',k.publishedCourses,'Published courses')}${kpi('check',k.completionRate+'%','Course completion rate',`${k.completions} of ${k.enrollments} enrollments`)}</div>
  <div class="stats">${kpi('award',k.certificatesEarned,'Certificates earned')}${kpi('clock',k.trainingHours,'Training hours completed','Verified video time + attended sessions')}${kpi('bell',k.pendingMandatory,'Pending mandatory training')}${kpi('path',k.employeesWithPlans,'Employees with learning plans','Assigned paths or active goals')}</div>
  <div class="dash-grid"><div class="dash-main">${progressPanel(d.progress)}${departmentPanel(d)}</div><div class="dash-side">${activityPanel(d.recent)}${upcomingPanel(d.upcoming)}</div></div>`;
}
function progressPanel(p){
  const tiles=[['Actively learning',p.activelyLearning,'Have a course in progress'],['Completed assigned courses',p.completedAssigned,'Every assigned course finished'],['Not started',p.notStarted,'No learning activity yet'],['Overdue',p.overdue,'At least one overdue assignment']];
  return panel('Employee learning progress',`<div class="mini-stats">${tiles.map(([label,value,hint],i)=>`<div class="mini-stat ${i===3&&value?'warn':''}"><strong>${value}</strong><span>${esc(label)}</span><small>${esc(hint)}</small></div>`).join('')}</div>${p.overdueEmployees.length?`<h3 class="sub-heading">Overdue learning</h3>${p.overdueEmployees.map(o=>`<div class="admin-list-row"><div><strong>${esc(o.name)}</strong><small>${esc(o.department||'No department')}</small></div><span class="tag danger">${o.overdue} OVERDUE</span></div>`).join('')}`:''}`,can('reports.view')?'<a href="#reports" data-act="report-preset" data-type="compliance">Compliance report &rarr;</a>':'');
}
function departmentPanel(d){
  const f=devFilters.dashboard;
  const form=`<form class="filter-row" data-form="dash-period"><label>From <input type="date" name="from" value="${esc(f.from||'')}"></label><label>To <input type="date" name="to" value="${esc(f.to||'')}"></label><button class="btn secondary" type="submit">Apply</button>${f.from||f.to?'<button class="auth-link" type="button" data-act="dash-period-clear">Clear dates</button>':''}</form>`;
  const rows=d.departments.map(r=>`<tr><td><strong>${esc(r.department)}</strong><small>${r.employees} employees</small></td><td>${meter(r.participationRate,'Participation')}<small>${r.participants} active learners</small></td><td>${meter(r.completionRate,'Completion')}<small>${r.completionsInPeriod} completions${f.from||f.to?' in period':''}</small></td><td>${r.averageScore==null?'—':r.averageScore+'%'}</td><td>${r.trainingHours}</td></tr>`).join('');
  return panel('Department-wise training',`${form}<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Department</th><th>Participation</th><th>Completion rate</th><th>Avg. assessment</th><th>Training hours</th></tr></thead><tbody>${rows||'<tr><td colspan="5" class="muted">Add employees to departments to compare training.</td></tr>'}</tbody></table></div><p class="muted">Participation counts employees with learning activity in the selected period. Completion rate covers all enrolled and assigned courses.</p>`);
}
function activityPanel(items){
  const icons={completion:'award',assessment:'check',course:'book',assignment:'bell'};
  return panel('Recent learning activity',items.length?items.map(e=>`<div class="activity"><span class="bubble">${icon(icons[e.type]||'clock')}</span><p>${esc(e.text)}<br><small>${esc(fmtDateTime(e.at))}</small></p></div>`).join(''):'<p class="muted">Course completions, assessment results, new assignments and published courses will appear here.</p>');
}
function upcomingPanel(u){
  const sessions=u.sessions.map(s=>`<div class="admin-list-row"><div><strong>${esc(s.title)}</strong><small>${esc(capital(s.kind))} · ${esc(fmtDateTime(s.starts_at))}${s.location?' · '+esc(s.location):''}</small></div><span class="tag gray">${s.registered}/${s.capacity} SEATS</span></div>`).join('');
  const deadlines=u.deadlines.map(x=>`<div class="admin-list-row"><div><strong>${esc(x.course)}</strong><small>Due ${esc(fmtDate(x.dueDate))} · ${x.pending} employee${x.pending===1?'':'s'} pending</small></div>${x.overdue?'<span class="tag danger">OVERDUE</span>':'<span class="tag">MANDATORY</span>'}</div>`).join('');
  const pending=u.pendingAssessments.map(x=>`<div class="admin-list-row"><div><strong>${esc(x.course)}</strong><small>${x.employees} employee${x.employees===1?'':'s'} awaiting the post-training assessment</small></div></div>`).join('');
  return panel('Upcoming training',`<h3 class="sub-heading">Training sessions & workshops</h3>${sessions||'<p class="muted">No sessions scheduled in the next 60 days.</p>'}<h3 class="sub-heading">Mandatory deadlines (30 days)</h3>${deadlines||'<p class="muted">No mandatory deadlines in the next 30 days.</p>'}<h3 class="sub-heading">Pending assessments</h3>${pending||'<p class="muted">No pending post-training assessments.</p>'}`,can('sessions.manage')?'<a href="#calendar">Manage &rarr;</a>':'');
}

// ---------------------------------------------------------------- employee dashboard

function courseTile(c){
  const a=c.assignment,progress=c.completed?100:c.progress||0;
  return `<article class="course-tile"><div class="tile-tags"><span class="tag">${esc(c.category)}</span>${a?.mandatory?'<span class="tag warn">MANDATORY</span>':''}${c.status==='overdue'?'<span class="tag danger">OVERDUE</span>':''}</div><h3>${esc(c.title)}</h3><p class="muted">${esc(capital(c.difficulty))} · ${esc(fmtDuration(c.durationMinutes))}${a?.dueDate?` · Due ${esc(fmtDate(a.dueDate))}`:''}</p><div class="progress-label"><span>Progress</span><b>${progress}%</b></div><div class="progress"><span style="width:${progress}%"></span></div><button class="btn secondary" data-open-course="${esc(c.id)}">${c.completed?'Review course':progress?'Continue':'Start'} ${icon('arrow')}</button></article>`;
}
function recommendationCard(r){
  return `<article class="recommendation"><div class="tile-tags"><span class="tag">${esc(r.category)}</span><span class="tag gray">${esc(capital(r.difficulty).toUpperCase())}</span></div><h3>${esc(r.title)}</h3><p class="muted">${esc(r.description)}</p><p class="muted">${esc(fmtDuration(r.durationMinutes))}${r.skills.length?' · Skills: '+esc(r.skills.filter(Boolean).join(', ')):''}</p><ul class="reasons">${r.reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><button class="btn secondary" data-open-course="${esc(r.id)}">View course ${icon('arrow')}</button></article>`;
}
function employeeDashboard(){
  const first=esc(state.name.split(' ')[0]),entry=loadData('me-dash','me/dashboard');
  const head=`<div class="intro"><div><h1>Welcome back, ${first}</h1><p>A little progress every day adds up to something great.</p></div><span class="tag">${esc((ROLE_LABELS[currentUser.role]||'Employee').toUpperCase())} WORKSPACE</span></div>`;
  if(!entry.data)return head+stateBlock(entry,'your learning',`me-dash`);
  const d=entry.data,p=d.profile;
  const profile=`<p class="profile-line">${esc([p.job_title||p.job_role,p.department,p.manager&&'Manager: '+p.manager].filter(Boolean).join(' · ')||'Ask HR to add your department and job role to receive role-based training.')}</p>`;
  const team=currentUser.role==='manager'?teamPanel():'';
  return head+profile+`<div class="stats">${kpi('book',d.stats.assigned,'Assigned courses',d.stats.overdue?`${d.stats.overdue} overdue`:'')}${kpi('play',d.stats.inProgress,'Courses in progress')}${kpi('award',d.stats.certificates,'Certificates earned')}${kpi('target',d.stats.skillGaps,'Skill gaps to close')}</div>
  ${team}<div class="dash-grid"><div class="dash-main">
  ${panel('Assigned to me',d.assigned.length?`<div class="tile-grid">${d.assigned.map(courseTile).join('')}</div>`:emptyState('No assigned training','Courses assigned by HR or your manager will appear here with their deadlines.','<a class="btn secondary" href="#courses">Browse all courses</a>'),'<a href="#courses">My Learning &rarr;</a>')}
  ${d.continue.filter(c=>!c.assignment).length?panel('Continue learning',`<div class="tile-grid">${d.continue.filter(c=>!c.assignment).map(courseTile).join('')}</div>`):''}
  ${panel('Recommended for you',d.recommendations.length?`<div class="tile-grid">${d.recommendations.map(recommendationCard).join('')}</div>`:emptyState('No recommendations yet','Recommendations use your job role targets, goals, assessment results and learning paths. Add a goal to get started.','<a class="btn secondary" href="#skills">Set a learning goal</a>'))}
  </div><div class="dash-side">
  ${panel('Learning paths',d.paths.length?d.paths.map(path=>`<div class="path-summary"><strong>${esc(path.title)}</strong>${meter(path.progress,path.title)}<small>${path.completed} of ${path.total} courses${path.dueDate?' · Target '+esc(fmtDate(path.dueDate)):''}</small></div>`).join(''):'<p class="muted">No learning paths assigned yet.</p>','<a href="#paths">View &rarr;</a>')}
  ${panel('Pending assessments',d.pendingAssessments.length?d.pendingAssessments.map(a=>`<div class="admin-list-row"><div><strong>${esc(a.title)}</strong><small>${esc(a.reason)} · ${a.attemptsLeft} attempt${a.attemptsLeft===1?'':'s'} left</small></div><a class="tag" href="#assessments">START</a></div>`).join(''):'<p class="muted">Nothing pending right now.</p>')}
  ${panel('Upcoming training',d.sessions.length?d.sessions.map(s=>`<div class="admin-list-row"><div><strong>${esc(s.title)}</strong><small>${esc(fmtDateTime(s.startsAt))} · ${s.seatsLeft} seats left</small></div>${s.myStatus==='registered'?'<span class="tag success">REGISTERED</span>':''}</div>`).join(''):'<p class="muted">No upcoming sessions.</p>','<a href="#calendar">Calendar &rarr;</a>')}
  ${panel('My goals',d.goals.length?d.goals.map(g=>`<div class="admin-list-row"><div><strong>${esc(g.title)}</strong><small>${g.targetDate?'Target '+esc(fmtDate(g.targetDate)):'No target date'}</small></div></div>`).join(''):'<p class="muted">Set a personal learning goal to focus your development.</p>','<a href="#skills">Manage &rarr;</a>')}
  ${panel('Learning history',d.history.length?d.history.map(h=>`<div class="activity"><span class="bubble">${icon('check')}</span><p>${esc(h.text)}<br><small>${esc(fmtDate(h.at))}</small></p></div>`).join(''):'<p class="muted">Your completed activities will appear here.</p>','<a href="#history">All history &rarr;</a>')}
  </div></div>`;
}
function teamPanel(){
  const entry=loadData('dash::','manage/dashboard');
  if(!entry.data)return stateBlock(entry,'team progress','dash::');
  const k=entry.data.kpis,p=entry.data.progress;
  return panel('My team',`<div class="mini-stats">${[['Direct reports',k.totalEmployees],['Completion rate',k.completionRate+'%'],['Pending mandatory',k.pendingMandatory],['Overdue',p.overdue]].map(([l,v])=>`<div class="mini-stat"><strong>${esc(v)}</strong><span>${esc(l)}</span></div>`).join('')}</div>`,'<a href="#reports">Team reports &rarr;</a>');
}

// ---------------------------------------------------------------- learning paths

function pathsPage(){
  const manage=can('paths.manage')||can('courses.assign');
  return intro('Learning paths',currentUser.role==='admin'?'Structured sequences of courses for roles, teams and programmes.':'Follow structured sequences of courses and track your milestones.',manage?'MANAGE & LEARN':'MY PATHS')+devNotice()+(isLearner()?myPaths():'')+(manage?managePaths():'');
}
function myPaths(){
  const entry=loadData('me-paths','me/paths');
  if(!entry.data)return stateBlock(entry,'your learning paths','me-paths');
  if(!entry.data.paths.length)return panel('My learning paths',emptyState('No learning paths assigned','HR, trainers or your manager can assign a learning path to you, your department or your job role.'));
  return entry.data.paths.map(p=>`<section class="panel path-card-full"><div class="section-heading"><div><h2>${esc(p.title)}</h2><p class="muted">${esc(p.description)}</p></div><span class="tag">${p.completed}/${p.total} COMPLETED</span></div>${meter(p.progress,p.title)}<p class="muted">${p.sequential?'Complete the courses in order; each course unlocks the next.':'Courses can be completed in any order.'}${p.dueDate?' Target date: '+esc(fmtDate(p.dueDate))+'.':''}</p><ol class="path-steps">${p.courses.map(c=>`<li class="step ${c.status} ${c.id===p.nextCourseId?'next':''}"><div><strong>${esc(c.title)}</strong><small>${esc(capital(c.difficulty))} · ${esc(fmtDuration(c.durationMinutes))}${c.id===p.nextCourseId?' · Next recommended activity':''}${c.completedAt?' · Completed '+esc(fmtDate(c.completedAt)):''}</small></div><div class="step-actions">${statusTag(c.status)}${['in_progress','not_started','completed'].includes(c.status)?`<button class="btn secondary" data-open-course="${esc(c.id)}">${c.status==='completed'?'Review':c.status==='in_progress'?'Continue':'Start'}</button>`:''}</div></li>`).join('')}</ol>${p.milestones.length?`<h3 class="sub-heading">Milestones achieved</h3><ul class="milestones">${p.milestones.map(m=>`<li>${icon('award')} ${esc(m.title)} <small>${esc(fmtDate(m.completedAt))}</small></li>`).join('')}</ul>`:''}</section>`).join('');
}
function managePaths(){
  const entry=loadData('m-paths','manage/paths');
  if(!entry.data)return stateBlock(entry,'learning paths','m-paths');
  const paths=entry.data.paths;
  const table=`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Path</th><th>Status</th><th>Courses</th><th>Assigned</th><th>Actions</th></tr></thead><tbody>${paths.map(p=>`<tr><td><strong>${esc(p.title)}</strong><small>${esc(p.description||'')}</small></td><td>${tagText(p.status,p.status==='published'?'success':'gray')}</td><td>${p.courses.map((c,i)=>`${i+1}. ${esc(c.title)}`).join('<br>')}</td><td>${p.assignedEmployees} employees<small>${p.completedEmployees} completed · ${p.assignments.map(a=>esc(a.target)).join(', ')||'Not assigned'}</small></td><td><div class="table-actions">${p.canEdit?`<button data-act="path-edit" data-id="${p.id}">Edit</button>`:''}${can('courses.assign')&&p.status==='published'?`<button data-act="path-assign" data-id="${p.id}">Assign</button>`:''}<button data-act="path-progress" data-id="${p.id}">Progress</button></div></td></tr>`).join('')||'<tr><td colspan="5" class="muted">No learning paths yet.</td></tr>'}</tbody></table></div>`;
  const assignPath=pathAssign&&paths.find(p=>p.id===pathAssign);
  return panel('Manage learning paths',table,can('paths.manage')?'<button class="btn" data-act="path-new">New learning path</button>':'')+(pathEditor?pathEditorForm():'')+(assignPath?`<section class="panel admin-form"><h2>Assign “${esc(assignPath.title)}”</h2><form data-form="path-assign" data-id="${assignPath.id}">${targetFields('path-assign',currentUser.role==='manager')}<label for="path-due">Target date (optional)</label><input id="path-due" type="date" name="dueDate"><div class="admin-actions"><button class="btn" type="submit">Assign path</button><button class="btn secondary" type="button" data-act="path-assign-cancel">Cancel</button></div><p class="form-status" role="status"></p></form>${assignPath.assignments.length?`<h3 class="sub-heading">Current assignments</h3>${assignPath.assignments.map(a=>`<div class="admin-list-row"><div><strong>${esc(a.target)}</strong><small>${esc(capital(a.targetType.replace('_',' ')))}${a.dueDate?' · Target '+esc(fmtDate(a.dueDate)):''}</small></div>${a.canRemove?`<button class="auth-link" data-act="path-unassign" data-id="${a.id}">Remove</button>`:''}</div>`).join('')}`:''}</section>`:'')+(pathProgressId?pathProgressPanel():'');
}
function pathEditorForm(){
  const courses=orgData().courses,draft=pathEditor,chosen=draft.courseIds.map(id=>courses.find(c=>c.id===id)).filter(Boolean);
  return `<section class="panel admin-form"><span class="tag">${draft.id?'EDIT PATH':'NEW PATH'}</span><h2>${draft.id?'Edit learning path':'Create a learning path'}</h2><form data-form="path-save" id="path-form"><label for="path-title">Path name</label><input id="path-title" name="title" value="${esc(draft.title)}" minlength="2" maxlength="150" required><label for="path-description">Description</label><textarea id="path-description" name="description" rows="2" maxlength="2000">${esc(draft.description)}</textarea><div class="editor-fields"><div><label for="path-status">Status</label><select id="path-status" name="status">${options([['draft','Draft'],['published','Published'],['archived','Archived']],draft.status)}</select></div><div><label class="check-label"><input type="checkbox" name="sequential" ${draft.sequential?'checked':''}> Courses unlock in sequence</label></div></div><h3 class="sub-heading">Course sequence</h3><ol class="sequence">${chosen.map((c,i)=>`<li><span>${esc(c.title)} ${c.status!=='published'?'<span class="tag gray">'+esc(c.status.toUpperCase())+'</span>':''}</span><span class="table-actions"><button type="button" data-act="path-move" data-index="${i}" data-dir="-1" ${i===0?'disabled':''} aria-label="Move up">↑</button><button type="button" data-act="path-move" data-index="${i}" data-dir="1" ${i===chosen.length-1?'disabled':''} aria-label="Move down">↓</button><button type="button" data-act="path-remove-course" data-index="${i}">Remove</button></span></li>`).join('')||'<li class="muted">Add at least one course.</li>'}</ol><label for="path-add-course">Add course</label><div class="inline-field"><select id="path-add-course">${options(courses.filter(c=>!draft.courseIds.includes(c.id)).map(c=>[c.id,`${c.title}${c.status!=='published'?' ('+c.status+')':''}`]),'','Select a course…')}</select><button class="btn secondary" type="button" data-act="path-add-course">Add</button></div><p class="muted">Every course must be published before the path can be published. Progress updates automatically as employees complete courses.</p><div class="admin-actions"><button class="btn" type="submit">Save path</button><button class="btn secondary" type="button" data-act="path-cancel">Cancel</button></div><p class="form-status" role="status"></p></form></section>`;
}
function capturePathForm(){const form=document.getElementById('path-form');if(!form||!pathEditor)return;const v=new FormData(form);pathEditor.title=v.get('title')||'';pathEditor.description=v.get('description')||'';pathEditor.status=v.get('status')||'draft';pathEditor.sequential=v.get('sequential')==='on';}
function pathProgressPanel(){
  const key='path-progress:'+pathProgressId,entry=loadData(key,`manage/paths/${pathProgressId}/progress`);
  if(!entry.data)return stateBlock(entry,'path progress',key);
  return panel('Path progress',`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Department</th><th>Progress</th><th>Next course</th></tr></thead><tbody>${entry.data.employees.map(r=>`<tr><td>${esc(r.employee)}</td><td>${esc(r.department)}</td><td>${meter(r.progress,r.employee)}<small>${r.completed}/${r.total} courses</small></td><td>${esc(r.next||'Completed')}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No employees are assigned to this path yet.</td></tr>'}</tbody></table></div>`,'<button class="btn secondary" data-act="path-progress-close">Close</button>');
}

// ---------------------------------------------------------------- skills, competencies and goals

function skillsPage(){
  const staff=currentUser.role!=='employee';
  return intro(currentUser.role==='admin'?'Skills & competencies':'Skills & goals',isLearner()?'Your proficiency levels come from assessments and manager-recorded evidence, not course completion alone.':'Define skills, role competencies and proficiency evidence.',staff?'COMPETENCY FRAMEWORK':'MY DEVELOPMENT')+devNotice()+(isLearner()?mySkills():'')+(staff?manageSkills():'');
}
function mySkills(){
  const entry=loadData('me-skills','me/skills');
  if(!entry.data)return stateBlock(entry,'your skills','me-skills');
  const d=entry.data;
  const rows=d.skills.map(s=>`<tr><td><strong>${esc(s.name)}</strong><small>${esc(s.category||'')}</small></td><td>${levelTag(s.current)}</td><td>${s.target?levelTag(s.target):'<span class="muted">No role target</span>'}</td><td>${s.gap?`<span class="tag warn">${s.gap} LEVEL${s.gap>1?'S':''}</span>`:s.target?'<span class="tag success">MEETS TARGET</span>':'—'}</td><td>${s.evidence[0]?`${esc(s.evidence[0].source==='assessment'?'Assessment':'Recorded by '+(s.evidence[0].recordedBy||'manager'))}<small>${esc(s.evidence[0].note)} · ${esc(fmtDate(s.evidence[0].recordedAt))}</small>`:'<span class="muted">No evidence yet</span>'}</td></tr>`).join('');
  const assessments=d.assessments.map(a=>`<div class="admin-list-row"><div><strong>${esc(a.title)}</strong><small>${esc(a.skill||'')} · validates ${esc(a.skillLevel)} · pass mark ${a.passPercent}% · ${a.attemptsLeft} attempts left</small></div>${a.passed?'<span class="tag success">PASSED</span>':a.attemptsLeft?`<a class="tag" href="#assessments">TAKE</a>`:'<span class="tag gray">NO ATTEMPTS LEFT</span>'}</div>`).join('');
  const goals=d.goals.map(g=>`<div class="admin-list-row"><div><strong>${esc(g.title)}</strong><small>${g.skill?esc(g.skill)+(g.targetLevel?' → '+esc(LEVEL_LABELS[g.targetLevel]):''):'Personal goal'}${g.targetDate?' · Target '+esc(fmtDate(g.targetDate)):''}</small></div><div class="table-actions">${tagText(g.status,g.status==='completed'?'success':g.status==='active'?'':'gray')}${g.status==='active'?`<button data-act="goal-status" data-id="${g.id}" data-status="completed">Mark done</button><button data-act="goal-status" data-id="${g.id}" data-status="cancelled">Cancel</button>`:''}<button data-act="goal-delete" data-id="${g.id}">Delete</button></div></div>`).join('');
  return `<div class="dash-grid"><div class="dash-main">${panel('My skills',`<p class="muted">Job role: <b>${esc(d.profile.jobRole||'Not set')}</b>${d.profile.department?' · '+esc(d.profile.department):''}</p><div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Skill</th><th>Current</th><th>Role target</th><th>Gap</th><th>Latest evidence</th></tr></thead><tbody>${rows||'<tr><td colspan="5" class="muted">No skills tracked yet. Role targets, goals and assessments will add skills here.</td></tr>'}</tbody></table></div>`)}${panel('Courses to close your gaps',d.recommendations.length?`<div class="tile-grid">${d.recommendations.map(recommendationCard).join('')}</div>`:'<p class="muted">No course recommendations right now.</p>')}</div><div class="dash-side">${panel('Skill assessments',assessments||'<p class="muted">No skill assessments are published yet.</p>')}${panel('Learning goals',`${goals||'<p class="muted">No goals yet.</p>'}<form class="admin-form compact-form" data-form="goal-save"><h3 class="sub-heading">Add a goal</h3><label for="goal-title">Goal</label><input id="goal-title" name="title" minlength="2" maxlength="150" required placeholder="e.g. Lead a sprint retrospective"><label for="goal-skill">Related skill (optional)</label><select id="goal-skill" name="skillId">${options(d.allSkills.map(s=>[s.id,s.name]),'','No specific skill')}</select><label for="goal-level">Target level (optional)</label><select id="goal-level" name="targetLevel">${levelOptions('','No target level')}</select><label for="goal-date">Target date (optional)</label><input id="goal-date" type="date" name="targetDate"><button class="btn" type="submit">Add goal</button><p class="form-status" role="status"></p></form>`)}</div></div>`;
}
function manageSkills(){
  const entry=loadData('m-skills','manage/skills'),org=orgData();
  if(!entry.data)return stateBlock(entry,'skills framework','m-skills');
  const d=entry.data,names=Object.fromEntries(d.skills.map(s=>[s.id,s.name]));
  const library=`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Skill</th><th>Category</th><th>Courses</th><th>Employees assessed</th>${d.canManageSkills?'<th>Actions</th>':''}</tr></thead><tbody>${d.skills.map(s=>`<tr><td><strong>${esc(s.name)}</strong><small>${esc(s.description)}</small></td><td>${esc(s.category||'—')}</td><td>${s.courses}</td><td>${s.assessed}</td>${d.canManageSkills?`<td><div class="table-actions"><button data-act="skill-delete" data-id="${s.id}">Delete</button></div></td>`:''}</tr>`).join('')||'<tr><td colspan="5" class="muted">Define skills such as Python, SQL, Communication or Leadership.</td></tr>'}</tbody></table></div>${d.canManageSkills?`<form class="admin-form inline-form" data-form="skill-save"><input name="name" placeholder="Skill name" minlength="2" maxlength="80" required aria-label="Skill name"><input name="category" placeholder="Category (e.g. Technical)" maxlength="80" aria-label="Skill category"><input name="description" placeholder="Short description" maxlength="1000" aria-label="Skill description"><button class="btn" type="submit">Add skill</button><p class="form-status" role="status"></p></form>`:''}`;
  const roles=org.jobRoles.filter(r=>d.editableRoles.includes(r.id)||currentUser.role!=='manager');
  const selected=competencyRole||roles[0]?.id||'';
  const targets=Object.fromEntries(d.competencies.filter(c=>c.jobRoleId===selected).map(c=>[c.skillId,c.targetLevel]));
  const editable=d.editableRoles.includes(selected);
  const matrix=roles.length?`<label for="competency-role">Job role</label><select id="competency-role" data-change="competency-role">${options(roles.map(r=>[r.id,r.name+(r.department?' · '+r.department:'')]),selected)}</select><div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Skill</th><th>Required level</th></tr></thead><tbody>${d.skills.map(s=>`<tr><td>${esc(s.name)}</td><td>${editable?`<select data-change="competency-level" data-role="${esc(selected)}" data-skill="${s.id}" aria-label="Required ${esc(s.name)} level">${options([[0,'Not required'],...[1,2,3,4].map(l=>[l,LEVEL_LABELS[l]])],targets[s.id]||0)}</select>`:levelTag(targets[s.id]||0)}</td></tr>`).join('')||'<tr><td colspan="2" class="muted">Add skills first.</td></tr>'}</tbody></table></div>${!editable?'<p class="muted">You can view this role. Managers can edit roles in their department or held by their direct reports.</p>':''}`:'<p class="muted">Create job roles in Users & Teams to define role competencies.</p>';
  const evidence=d.canRecord?panel('Record skill evidence',`<form class="admin-form" data-form="evidence-save"><label for="evidence-employee">Employee</label><select id="evidence-employee" name="employeeId" required>${options(peopleData().filter(p=>p.id!==currentUser.id).map(p=>[p.id,`${p.name} · ${p.department||'No department'}`]),'','Select…')}</select><label for="evidence-skill">Skill</label><select id="evidence-skill" name="skillId" required>${options(d.skills.map(s=>[s.id,s.name]),'','Select…')}</select><label for="evidence-level">Demonstrated level</label><select id="evidence-level" name="level" required>${levelOptions(2)}</select><label for="evidence-note">Evidence</label><textarea id="evidence-note" name="note" rows="2" minlength="3" maxlength="500" required placeholder="e.g. Led the Q3 data migration review"></textarea><button class="btn" type="submit">Record evidence</button><p class="form-status" role="status"></p></form><p class="muted">Use observed work or verified results. Skill levels are never raised automatically by course completion.</p>`):'';
  return `<div class="dash-grid"><div class="dash-main">${panel('Skill library',library)}${panel('Role competencies',matrix)}</div><div class="dash-side">${evidence}${panel('Skill gaps',`<p class="muted">Compare current and required levels for every employee.</p><a class="btn secondary" href="#reports" data-act="report-preset" data-type="skills">Open skill-gap report</a>`)}</div></div>`;
}

// ---------------------------------------------------------------- training calendar

function calendarPage(){
  return intro('Training calendar','Instructor-led sessions and workshops, with seats and registration status.',can('sessions.manage')?'SCHEDULE & REGISTER':'MY CALENDAR')+devNotice()+(isLearner()?myCalendar():'')+(can('sessions.manage')?manageSessions():'');
}
function sessionCard(s){
  const full=s.seatsLeft<=0&&s.myStatus!=='registered';
  return `<article class="session-card"><div class="session-date"><strong>${esc(new Date(s.startsAt).toLocaleDateString('en-IN',{day:'numeric'}))}</strong><span>${esc(new Date(s.startsAt).toLocaleDateString('en-IN',{month:'short'}).toUpperCase())}</span></div><div class="session-body"><div class="tile-tags"><span class="tag">${esc(s.kind.toUpperCase())}</span>${s.myStatus==='registered'?'<span class="tag success">REGISTERED</span>':''}${s.myStatus==='attended'?'<span class="tag success">ATTENDED</span>':''}</div><h3>${esc(s.title)}</h3><p class="muted">${esc(fmtDateTime(s.startsAt))} – ${esc(new Date(s.endsAt).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'}))}${s.location?' · '+esc(s.location):''}${s.trainer?' · '+esc(s.trainer):''}</p>${s.description?`<p class="muted">${esc(s.description)}</p>`:''}<p class="muted"><b>${s.seatsLeft}</b> of ${s.capacity} seats available${s.course?' · Linked course: '+esc(s.course):''}</p>${s.myStatus==='registered'?`<button class="btn secondary" data-act="session-cancel" data-id="${s.id}">Cancel registration</button>`:s.myStatus==='attended'?'':`<button class="btn" data-act="session-register" data-id="${s.id}" ${full?'disabled':''}>${full?'Session full':'Register'}</button>`}</div></article>`;
}
function myCalendar(){
  const entry=loadData('me-cal','me/calendar');
  if(!entry.data)return stateBlock(entry,'training sessions','me-cal');
  const d=entry.data;
  return panel('Upcoming sessions',d.sessions.length?`<div class="session-list">${d.sessions.map(sessionCard).join('')}</div>`:emptyState('No sessions scheduled','Instructor-led sessions and workshops will appear here when they are scheduled.'))+(d.past.length?panel('Past sessions',d.past.map(p=>`<div class="admin-list-row"><div><strong>${esc(p.title)}</strong><small>${esc(fmtDateTime(p.startsAt))}</small></div><span class="tag ${p.status==='attended'?'success':'gray'}">${esc(p.status.toUpperCase())}</span></div>`).join('')):'');
}
function manageSessions(){
  const entry=loadData('m-sessions','manage/sessions');
  if(!entry.data)return stateBlock(entry,'scheduled sessions','m-sessions');
  const sessions=entry.data.sessions,org=orgData();
  const table=`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Session</th><th>When</th><th>Seats</th><th>Status</th><th>Actions</th></tr></thead><tbody>${sessions.map(s=>`<tr><td><strong>${esc(s.title)}</strong><small>${esc(capital(s.kind))}${s.trainer?' · '+esc(s.trainer):''}${s.location?' · '+esc(s.location):''}</small></td><td>${esc(fmtDateTime(s.startsAt))}</td><td>${s.registered}/${s.capacity}</td><td><span class="tag ${s.status==='cancelled'?'danger':''}">${esc(s.status.toUpperCase())}</span></td><td><div class="table-actions">${s.canEdit?`<button data-act="session-edit" data-id="${s.id}">Edit</button>`:''}<button data-act="session-roster" data-id="${s.id}">Registrations</button></div></td></tr>`).join('')||'<tr><td colspan="5" class="muted">No sessions scheduled yet.</td></tr>'}</tbody></table></div>`;
  const s=sessionEditor;
  const form=s?`<section class="panel admin-form"><span class="tag">${s.id?'EDIT SESSION':'NEW SESSION'}</span><h2>${s.id?'Edit session':'Schedule a session'}</h2><form data-form="session-save" data-id="${esc(s.id||'')}"><label for="session-title">Title</label><input id="session-title" name="title" value="${esc(s.title||'')}" minlength="2" maxlength="150" required><label for="session-description">Description</label><textarea id="session-description" name="description" rows="2" maxlength="2000">${esc(s.description||'')}</textarea><div class="editor-fields"><div><label for="session-kind">Type</label><select id="session-kind" name="kind">${options([['session','Training session'],['workshop','Workshop']],s.kind||'session')}</select></div><div><label for="session-capacity">Seats</label><input id="session-capacity" name="capacity" type="number" min="1" max="10000" value="${esc(s.capacity||20)}" required></div><div><label for="session-status">Status</label><select id="session-status" name="status">${options([['scheduled','Scheduled'],['cancelled','Cancelled']],s.status||'scheduled')}</select></div></div><div class="editor-fields"><div><label for="session-start">Starts</label><input id="session-start" name="startsAt" type="datetime-local" value="${esc(s.startsAt||'')}" required></div><div><label for="session-end">Ends</label><input id="session-end" name="endsAt" type="datetime-local" value="${esc(s.endsAt||'')}" required></div><div><label for="session-location">Location or link</label><input id="session-location" name="location" value="${esc(s.location||'')}" maxlength="200"></div></div><div class="editor-fields"><div><label for="session-course">Linked course (optional)</label><select id="session-course" name="courseId">${options(org.courses.map(c=>[c.id,c.title]),s.courseId,'None')}</select></div>${currentUser.role!=='trainer'?`<div><label for="session-trainer">Trainer</label><select id="session-trainer" name="trainerId">${options(org.trainers.map(t=>[t.id,t.name]),s.trainerId,'Not assigned')}</select></div>`:''}</div><p class="muted">Times use the server's local time zone. Registered employees are notified when a session is cancelled or rescheduled.</p><div class="admin-actions"><button class="btn" type="submit">Save session</button><button class="btn secondary" type="button" data-act="session-editor-close">Cancel</button></div><p class="form-status" role="status"></p></form></section>`:'';
  return panel('Manage sessions',table,'<button class="btn" data-act="session-new">Schedule session</button>')+form+(sessionRoster?rosterPanel(sessions.find(x=>x.id===sessionRoster)):'');
}
function rosterPanel(session){
  if(!session)return '';
  const key='roster:'+session.id,entry=loadData(key,`manage/sessions/${session.id}/registrations`);
  if(!entry.data)return stateBlock(entry,'registrations',key);
  const started=session.startsAt<=new Date().toISOString().slice(0,16);
  return panel(`Registrations: ${session.title}`,`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Department</th><th>Status</th><th>Attendance</th></tr></thead><tbody>${entry.data.registrations.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.department||'—')}</td><td>${esc(capital(r.status))}</td><td>${r.status==='cancelled'?'—':started?`<label class="check-label"><input type="checkbox" data-change="attendance" data-session="${session.id}" data-employee="${r.employeeId}" ${r.status==='attended'?'checked':''}> Attended</label>`:'<span class="muted">After start</span>'}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No registrations yet.</td></tr>'}</tbody></table></div>`,'<button class="btn secondary" data-act="session-roster-close">Close</button>');
}

// ---------------------------------------------------------------- assessments

function assessmentsPage(){
  if(activeAssessment)return assessmentRunner();
  return intro('Assessments','Pre- and post-training checks, knowledge checks and skill assessments with server-side scoring.',can('assessments.manage')?'QUESTION BANKS':'MY ASSESSMENTS')+devNotice()+(assessmentResult?resultPanel():'')+(isLearner()?myAssessments():'')+(can('assessments.manage')?manageAssessments():'');
}
function myAssessments(){
  const entry=loadData('me-assess','me/assessments');
  if(!entry.data)return stateBlock(entry,'assessments','me-assess');
  const items=entry.data.assessments;
  return panel('Available to me',items.length?`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Assessment</th><th>Type</th><th>Rules</th><th>My result</th><th></th></tr></thead><tbody>${items.map(a=>`<tr><td><strong>${esc(a.title)}</strong><small>${esc(a.course||a.skill||'')}</small></td><td>${esc(KIND_LABELS[a.kind])}</td><td>${a.questionCount} questions · ${a.timeLimitMinutes} min<small>Pass ${a.passPercent}% · ${a.maxAttempts} attempt${a.maxAttempts===1?'':'s'}</small></td><td>${a.passed?'<span class="tag success">PASSED</span>':a.attempts.length?'<span class="tag warn">NOT PASSED</span>':'<span class="tag gray">NOT TAKEN</span>'}<small>${a.best!=null?'Best '+a.best+'% · ':''}${a.attempts.length} attempt${a.attempts.length===1?'':'s'} used</small></td><td>${a.active?`<button class="btn" data-act="assessment-start" data-id="${a.id}">Resume</button>`:a.attemptsLeft&&!(a.kind==='skill'&&a.passed)?`<button class="btn secondary" data-act="assessment-start" data-id="${a.id}">${a.attempts.length?'Retake':'Start'}</button>`:''}</td></tr>`).join('')}</tbody></table></div>`:emptyState('No assessments yet','Published assessments for your courses and skills will appear here.'));
}
function assessmentRunner(){
  const a=activeAssessment;
  return `<div class="exam-focus"><div class="exam-top"><div><span class="tag">ASSESSMENT · ATTEMPT ${a.attempt.attemptNumber}</span><h1>${esc(a.title)}</h1></div><div class="exam-timer" role="timer" id="assessment-timer">--:--</div></div><div class="notice">Your answers are scored on the server. The timer keeps running if you leave; unanswered attempts expire at the deadline.</div><form class="panel" data-form="assessment-submit">${a.attempt.questions.map((q,i)=>`<fieldset class="question"><legend><span>${i+1}.</span> ${esc(q.prompt)}</legend>${q.options.map((o,j)=>`<label class="answer"><input type="radio" name="q${i}" value="${j}" required><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}<button class="btn" type="submit">Submit assessment ${icon('check')}</button> <button class="btn secondary" type="button" data-act="assessment-leave">Leave for now</button><p class="form-status" role="status"></p></form></div>`;
}
function updateAssessmentTimer(){
  if(!activeAssessment)return;
  const timer=document.getElementById('assessment-timer');const seconds=Math.max(0,Math.ceil((activeAssessment.attempt.deadline-Date.now())/1000));
  if(timer)timer.textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
  if(!seconds){activeAssessment=null;assessmentResult={status:'expired',details:[]};refreshData('me-assess');render();}
}
function resultPanel(){
  const r=assessmentResult;
  if(r.status==='expired')return '<div class="notice" role="status">Time expired. The attempt ended without a score and counts toward your attempt limit.</div>';
  return `<section class="panel"><div class="section-heading"><h2>${r.status==='passed'?'Assessment passed':'Assessment not passed'}</h2><button class="auth-link" data-act="assessment-result-close">Dismiss</button></div><p><b>${r.score}/${r.total} correct (${r.percent}%)</b> · Pass mark ${r.passPercent}%</p><ol class="result-list">${r.details.map(d=>`<li class="${d.correct?'correct':'incorrect'}">${d.correct?'Correct.':`Incorrect. Correct answer: ${esc(d.answer||'')}.`} ${esc(d.explanation||'')}</li>`).join('')}</ol></section>`;
}
const QUESTION_TEMPLATE='[\n  ["Question text", ["Option A", "Option B", "Option C"], 0, "Why the correct option is right"]\n]';
function manageAssessments(){
  const entry=loadData('m-assess','manage/assessments'),org=orgData();
  if(!entry.data)return stateBlock(entry,'question banks','m-assess');
  const list=entry.data.assessments,courseNames=Object.fromEntries(org.courses.map(c=>[c.id,c.title])),skillNames=Object.fromEntries(org.skills.map(s=>[s.id,s.name]));
  const table=`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Assessment</th><th>Type</th><th>Question bank</th><th>Rules</th><th>Results</th><th>Actions</th></tr></thead><tbody>${list.map(a=>`<tr><td><strong>${esc(a.title)}</strong><small>${esc(courseNames[a.courseId]||skillNames[a.skillId]||'')} · ${esc(a.status)}</small></td><td>${esc(KIND_LABELS[a.kind])}</td><td>${a.questions.length} in bank<small>${a.questionCount} drawn at random</small></td><td>Pass ${a.passPercent}%<small>${a.maxAttempts} attempts · ${a.timeLimitMinutes} min</small></td><td>${a.attempts} attempts<small>${a.passRate==null?'No results yet':`${a.passRate}% pass rate · avg ${a.averageScore}%`}</small></td><td><div class="table-actions"><button data-act="assessment-edit" data-id="${a.id}">Edit</button><button data-act="assessment-attempts" data-id="${a.id}">Attempts</button></div></td></tr>`).join('')||'<tr><td colspan="6" class="muted">No assessments yet.</td></tr>'}</tbody></table></div>`;
  const a=assessmentEditor;
  const form=a?`<section class="panel admin-form"><span class="tag">${a.id?'EDIT ASSESSMENT':'NEW ASSESSMENT'}</span><h2>${a.id?'Edit assessment':'Create an assessment'}</h2>${a.locked?'<div class="notice">Employees have attempted this assessment. Rules, status and title can change; the question bank and type are locked to preserve attempt history.</div>':''}<form data-form="assessment-save" data-id="${esc(a.id||'')}"><label for="assessment-title">Title</label><input id="assessment-title" name="title" value="${esc(a.title||'')}" minlength="2" maxlength="150" required><label for="assessment-description">Description</label><textarea id="assessment-description" name="description" rows="2" maxlength="2000">${esc(a.description||'')}</textarea><div class="editor-fields"><div><label for="assessment-kind">Type</label><select id="assessment-kind" name="kind">${options(Object.entries(KIND_LABELS),a.kind||'knowledge')}</select></div><div><label for="assessment-course">Course (required for pre/post)</label><select id="assessment-course" name="courseId">${options(org.courses.map(c=>[c.id,c.title]),a.courseId,'None')}</select></div><div><label for="assessment-status">Status</label><select id="assessment-status" name="status">${options([['draft','Draft'],['published','Published'],['archived','Archived']],a.status||'draft')}</select></div></div><div class="editor-fields"><div><label for="assessment-skill">Skill (required for skill assessments)</label><select id="assessment-skill" name="skillId">${options(org.skills.map(s=>[s.id,s.name]),a.skillId,'None')}</select></div><div><label for="assessment-skill-level">Level validated when passed</label><select id="assessment-skill-level" name="skillLevel">${levelOptions(a.skillLevel||2)}</select></div><div><label for="assessment-pass">Passing score %</label><input id="assessment-pass" name="passPercent" type="number" min="1" max="100" value="${esc(a.passPercent||70)}" required></div></div><div class="editor-fields"><div><label for="assessment-attempts">Attempts allowed</label><input id="assessment-attempts" name="maxAttempts" type="number" min="1" max="10" value="${esc(a.maxAttempts||3)}" required></div><div><label for="assessment-count">Questions per attempt</label><input id="assessment-count" name="questionCount" type="number" min="1" max="100" value="${esc(a.questionCount||5)}" required></div><div><label for="assessment-time">Time limit (minutes)</label><input id="assessment-time" name="timeLimitMinutes" type="number" min="1" max="240" value="${esc(a.timeLimitMinutes||15)}" required></div></div><label for="assessment-questions">Question bank (JSON)</label><p class="muted">Each question is [prompt, options, correct option index starting at 0, explanation]. Each attempt draws the configured number of questions at random. Answer keys never reach employees.</p><textarea id="assessment-questions" name="questions" class="curriculum-json" rows="12" spellcheck="false" ${a.locked?'readonly':''} required>${esc(a.questions?JSON.stringify(a.questions,null,2):QUESTION_TEMPLATE)}</textarea><div class="admin-actions"><button class="btn" type="submit">Save assessment</button><button class="btn secondary" type="button" data-act="assessment-editor-close">Cancel</button></div><p class="form-status" role="status"></p></form><p class="muted">To require a post-training assessment for a certificate, select it in the course's completion requirements under Manage Courses.</p></section>`:'';
  return panel('Question banks',table,'<button class="btn" data-act="assessment-new">New assessment</button>')+form+(assessmentAttemptsId?attemptsPanel():'');
}
function attemptsPanel(){
  const key='attempts:'+assessmentAttemptsId,entry=loadData(key,`manage/assessments/${assessmentAttemptsId}/attempts`);
  if(!entry.data)return stateBlock(entry,'attempt history',key);
  const d=entry.data;
  return panel(`Attempt history: ${d.assessment.title}`,`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Department</th><th>Attempt</th><th>Score</th><th>Result</th><th>Date</th></tr></thead><tbody>${d.items.map(t=>`<tr><td>${esc(t.employee)}</td><td>${esc(t.department||'—')}</td><td>${t.attempt_number}</td><td>${t.percent==null?'—':`${t.score}/${t.total} (${t.percent}%)`}</td><td>${esc(capital(t.status))}</td><td>${esc(fmtDateTime(t.finished_at||t.started_at))}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No attempts yet.</td></tr>'}</tbody></table></div><p class="muted">${d.total} attempts · page ${d.page} of ${d.pages}</p>`,'<button class="btn secondary" data-act="assessment-attempts-close">Close</button>');
}

// ---------------------------------------------------------------- reports & analytics

const REPORT_TYPES=[['enrollments','Course enrollment & completion'],['employees','Employee learning progress'],['departments','Department training statistics'],['assessments','Assessment performance'],['skills','Skill-gap summary'],['compliance','Mandatory training compliance'],['certificates','Certificate records']];
function reportsPage(fixedType){
  const f=devFilters.report,type=fixedType||f.type;
  const types=currentUser.role==='trainer'?REPORT_TYPES.filter(([t])=>['enrollments','assessments','certificates'].includes(t)):REPORT_TYPES;
  const query={type,department:f.department,employee:f.employee,course:f.course,from:f.from,to:f.to,page:f.page},key='report:'+qs(query),entry=loadData(key,'manage/reports'+qs(query)),org=orgData();
  const title=fixedType?'Certificates':currentUser.role==='manager'?'Team reports':'Reports & analytics';
  const filters=`<form class="report-filters panel" data-form="report-filters">${fixedType?'':`<div><label for="report-type">Report</label><select id="report-type" name="type">${options(types,type)}</select></div>`}${currentUser.role!=='trainer'?`<div><label for="report-department">Department</label><select id="report-department" name="department">${options(org.departments.map(d=>[d.id,d.name]),f.department,'All departments')}</select></div><div><label for="report-employee">Employee</label><select id="report-employee" name="employee">${options(peopleData().map(p=>[p.id,p.name]),f.employee,'All employees')}</select></div>`:''}<div><label for="report-course">Course</label><select id="report-course" name="course">${options(org.courses.map(c=>[c.id,c.title]),f.course,'All courses')}</select></div><div><label for="report-from">From</label><input id="report-from" type="date" name="from" value="${esc(f.from||'')}"></div><div><label for="report-to">To</label><input id="report-to" type="date" name="to" value="${esc(f.to||'')}"></div><div class="filter-actions"><button class="btn" type="submit">Apply filters</button><button class="btn secondary" type="button" data-act="report-reset">Reset</button></div></form>`;
  const head=intro(title,currentUser.role==='manager'?'Learning records for your direct reports only.':currentUser.role==='trainer'?'Course-level results for the courses you own.':'Filter learning records by department, employee, course and date range.','AUTHORISED VIEW')+filters;
  if(!entry.data)return head+stateBlock(entry,'report',key);
  const d=entry.data;
  return head+`<section class="panel"><div class="section-heading"><h2>${esc(d.title)}</h2><button class="btn secondary" data-act="report-export" data-query="${esc(qs({...query,page:undefined,export:1}))}">Export CSV</button></div><div class="summary-chips">${Object.entries(d.summary).map(([k,v])=>`<span><b>${esc(v)}</b> ${esc(k)}</span>`).join('')}</div><div class="admin-table-scroll"><table class="admin-table report-table"><thead><tr>${d.columns.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${d.rows.map(r=>`<tr>${d.columns.map(c=>`<td>${esc(r[c.key]??'')}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${d.columns.length}" class="muted">No records match these filters.</td></tr>`}</tbody></table></div><div class="pager"><span class="muted">${d.total} records · page ${d.page} of ${d.pages}</span><span class="table-actions"><button data-act="report-page" data-page="${d.page-1}" ${d.page<=1?'disabled':''}>Previous</button><button data-act="report-page" data-page="${d.page+1}" ${d.page>=d.pages?'disabled':''}>Next</button></span></div></section>`;
}
function toCSV(columns,rows){
  // Prefix spreadsheet formula characters so exported names cannot execute as formulas.
  const cell=value=>{let s=value==null?'':String(value);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return /[",\r\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s;};
  return [columns.map(c=>cell(c.label)).join(','),...rows.map(r=>columns.map(c=>cell(r[c.key])).join(','))].join('\r\n');
}
function download(name,text,type){const url=URL.createObjectURL(new Blob(['﻿'+text],{type}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

// ---------------------------------------------------------------- learning history

function historyPageView(){
  const key='me-history:'+historyPage,entry=loadData(key,'me/history'+qs({page:historyPage}));
  const head=intro('Learning history','Completions, results, attended sessions and your professional development records.','MY RECORDS')+devNotice();
  if(!entry.data)return head+stateBlock(entry,'learning history',key);
  const d=entry.data;
  return head+`<div class="dash-grid"><div class="dash-main">${panel('Activity',d.items.length?d.items.map(h=>`<div class="activity"><span class="bubble">${icon(h.type==='session'?'calendar':h.type==='record'?'file':'check')}</span><p>${esc(h.text)}<br><small>${esc(fmtDate(h.at))}</small></p></div>`).join('')+`<div class="pager"><span class="muted">Page ${d.page} of ${d.pages}</span><span class="table-actions"><button data-act="history-page" data-page="${d.page-1}" ${d.page<=1?'disabled':''}>Previous</button><button data-act="history-page" data-page="${d.page+1}" ${d.page>=d.pages?'disabled':''}>Next</button></span></div>`:emptyState('No learning history yet','Completed courses, assessment results and attended sessions are recorded here.'))}</div><div class="dash-side">${panel('Professional development records',`${d.records.map(r=>`<div class="admin-list-row"><div><strong>${esc(r.title)}</strong><small>${esc(r.provider||'Self-reported')} · ${esc(fmtDate(r.completedOn))} · ${r.hours} h</small></div><button class="auth-link" data-act="record-delete" data-id="${r.id}">Delete</button></div>`).join('')||'<p class="muted">Record external courses, conferences or certifications.</p>'}<form class="admin-form compact-form" data-form="record-save"><label for="record-title">Title</label><input id="record-title" name="title" minlength="2" maxlength="150" required><label for="record-provider">Provider</label><input id="record-provider" name="provider" maxlength="150"><label for="record-date">Completed on</label><input id="record-date" type="date" name="completedOn" required><label for="record-hours">Hours</label><input id="record-hours" type="number" name="hours" min="0" max="1000" step="0.5" value="1"><button class="btn" type="submit">Add record</button><p class="form-status" role="status"></p></form><p class="muted">Self-reported records are shown separately from verified internal training.</p>`)}</div></div>`;
}

// ---------------------------------------------------------------- course preview, resources and assistant

function coursePreviewPage(){
  if(!previewCourseId)return emptyState('Choose a course to preview','Open Manage Courses and select Preview.','<a class="btn" href="#admin-courses">Manage Courses</a>');
  const key='preview:'+previewCourseId,entry=loadData(key,`manage/courses/${previewCourseId}/preview`);
  if(!entry.data)return stateBlock(entry,'course preview',key);
  const d=entry.data,c=d.courseInfo;
  return `<div class="intro"><div><div class="eyebrow">PREVIEW · ${esc(c.status.toUpperCase())}</div><h1>${esc(c.title)}</h1><p>${esc(c.description)}</p></div><a class="btn secondary" href="#admin-courses">Back to Manage Courses</a></div><div class="notice">This is how employees will see the course content. Answer keys are hidden, and progress is not recorded in preview.</div><p class="muted">${esc(c.category)} · ${esc(capital(c.difficulty))} · ${esc(fmtDuration(c.durationMinutes))} · Pass mark ${c.passPercent}% · ${c.maxAttempts} exam attempts per module${c.skills?.length?' · Skills: '+esc(c.skills.map(s=>s.name+' ('+LEVEL_LABELS[s.level]+')').join(', ')):''}</p>${d.course.map((m,s)=>`<section class="panel lesson-content"><span class="tag">MODULE ${s+1} OF 3</span><h2>${esc(m.title)}</h2><p>${esc(m.summary)}</p>${m.videos.map(i=>`<h3>Lesson ${i+1}: ${esc(d.lessons[i].title)}</h3><video class="course-video" controls preload="none"><source src="${esc(d.lessons[i].src)}"></video><p>${esc(d.lessons[i].body)}</p><pre><code>${esc(d.lessons[i].code)}</code></pre>`).join('')}<h3>Exercises</h3>${m.exercises.map((e,i)=>`<p><b>${i+1}. ${esc(e.title)}</b> — ${e.questions.length} questions</p>`).join('')}<h3>Module exam</h3><ol>${m.exam.map(q=>`<li>${esc(q[0])}</li>`).join('')}</ol></section>`).join('')}${resourceList(d.resources)}`;
}
function resourceList(resources){
  if(!resources?.length)return '';
  return panel('Learning materials',resources.map(r=>`<div class="admin-list-row"><div><strong>${esc(r.title)}</strong><small>${esc(capital(r.kind))}${r.moduleIndex!=null?' · Module '+(r.moduleIndex+1):''}</small></div><a class="tag" href="${esc(r.url)}" target="_blank" rel="noopener">OPEN</a></div>`).join(''));
}
function courseExtras(){
  // Rendered below the course player for employees.
  const extras=currentCourseExtras||{resources:[],assessments:[]};
  // Lesson-based courses show their knowledge checks and final assessment inline in the lesson player.
  const assessments=extras.assessments.length&&currentCourseInfo.format!=='lessons'?panel('Course assessments',extras.assessments.map(a=>`<div class="admin-list-row"><div><strong>${esc(a.title)}</strong><small>${esc(KIND_LABELS[a.kind])} · pass ${a.passPercent}%${a.id===extras.requiredAssessmentId?' · Required for your certificate':''}${a.best!=null?' · Best '+a.best+'%':''}</small></div>${a.passed?'<span class="tag success">PASSED</span>':a.attemptsLeft?'<a class="tag" href="#assessments">TAKE</a>':'<span class="tag gray">NO ATTEMPTS LEFT</span>'}</div>`).join('')):'';
  return `<div class="course-extras">${resourceList(extras.resources)}${assessments}${assistantPanel()}</div>`;
}
function assistantPanel(){
  const entry=loadData('assistant','me/assistant');
  if(!entry.data)return entry.error?'':stateBlock(entry,'learning assistant','assistant');
  if(!entry.data.enabled)return panel('AI learning assistant',`<p class="muted">${esc(entry.data.reason)} When enabled, it answers questions using this course's approved lessons, summarises lessons, explains concepts, writes practice questions and suggests revision topics.</p>`);
  const answer=assistantAnswer&&assistantAnswer.courseId===currentCourseInfo.id?`<div class="assistant-answer" role="status">${esc(assistantAnswer.text)}</div>`:'';
  return panel('AI learning assistant',`<form class="admin-form" data-form="assistant"><div class="editor-fields"><div><label for="assistant-mode">I want to…</label><select id="assistant-mode" name="mode">${options([['ask','Ask a question'],['summarize','Summarise a lesson'],['explain','Explain a concept'],['practice','Generate practice questions'],['revision','Get revision suggestions']],'ask')}</select></div>${currentCourseInfo.format==='lessons'?'':`<div><label for="assistant-lesson">Lesson (optional)</label><select id="assistant-lesson" name="lessonIndex">${options(lessons.map((l,i)=>[i,`${i+1}. ${l.title}`]),'','Whole course')}</select></div>`}</div><label for="assistant-question">Your question</label><textarea id="assistant-question" name="question" rows="3" maxlength="2000" placeholder="Answers are based on this course's approved materials."></textarea><button class="btn" type="submit">Ask the assistant</button><p class="form-status" role="status"></p></form>${answer}<p class="muted">AI answers can be wrong. Check important details against the lesson or ask your trainer. Limit: ${entry.data.hourlyLimit} requests per hour.</p>`);
}
let currentCourseExtras=null,selectedLessonId=null;
// Shared by the employee player and the Manage Courses preview, so the preview shows exactly what employees see.
const EMBED=/^https:\/\/(www\.youtube-nocookie\.com\/embed|player\.vimeo\.com\/video)\//;
const hostOf=url=>{try{return new URL(url).hostname.replace(/^www\./,'');}catch{return '';}};
// Mirrors the server's embed conversion so unsaved YouTube/Vimeo links preview exactly as employees will see them after saving.
function embedUrl(url){
  try{
    const u=new URL(url),host=u.hostname.toLowerCase(),parts=u.pathname.split('/').filter(Boolean);
    if(['youtu.be','youtube.com','www.youtube.com','m.youtube.com','www.youtube-nocookie.com'].includes(host)){
      const id=host==='youtu.be'?parts[0]:u.pathname==='/watch'?u.searchParams.get('v'):['embed','shorts','live'].includes(parts[0])?parts[1]:'';
      return /^[A-Za-z0-9_-]{6,20}$/.test(id||'')?`https://www.youtube-nocookie.com/embed/${id}`:url;
    }
    if(['vimeo.com','www.vimeo.com','player.vimeo.com'].includes(host)){const id=[...parts].reverse().find(p=>/^\d+$/.test(p));return id?`https://player.vimeo.com/video/${id}`:url;}
  }catch{/* Relative paths (uploads, assets/) are used as they are. */}
  return url;
}
const clock=s=>{s=Math.max(0,Math.floor(Number(s)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;};
function lessonVideo(url,title,lesson={}){
  if(!url)return '';
  url=embedUrl(url);
  if(EMBED.test(url))return `<div class="video-embed"><iframe src="${esc(url)}" title="${esc(title||'Lesson')} video" loading="lazy" allow="fullscreen; picture-in-picture; encrypted-media" allowfullscreen referrerpolicy="strict-origin-when-cross-origin" sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"></iframe></div>`;
  const type=/\.webm$/i.test(url)?'video/webm':'video/mp4';
  return `<video ${lesson.tracked&&lesson.id?`id="lesson-video" data-lesson="${esc(lesson.id)}"`:''} class="course-video" controls preload="metadata" playsinline controlslist="nodownload" aria-label="${esc(title||'Lesson')} video"><source src="${esc(url)}" type="${type}">${lesson.captionsUrl?`<track kind="captions" src="${esc(lesson.captionsUrl)}" srclang="en" label="English" default>`:''}Your browser cannot play this video. The lesson content below covers the same material.</video>`;
}
// Extended Markdown for article-style courses and imported lessons: ::: blocks, nested lists, links and heading anchors.
// Links are limited to http(s) URLs and open in a new tab; everything else is escaped first.
function inlineMarkdown(text){return esc(text).replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1 ↗</a>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/(^|[\s(])\*([^*\s][^*]*)\*/g,'$1<em>$2</em>');}
// Heading ids for in-page navigation; the same slugger is used by markdownOutline so ids always match.
function headingSlugger(){const seen={};return title=>{const base='sec-'+(String(title).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'section');seen[base]=(seen[base]||0)+1;return seen[base]>1?`${base}-${seen[base]}`:base;};}
// Sections (##) and subsections (###) of a lesson, skipping code blocks and ::: blocks.
function markdownOutline(source){
  const slug=headingSlugger(),groups=[];let fence=false,block=false;
  for(const line of String(source||'').replace(/\r/g,'').split('\n')){
    const t=line.trim();
    if(t.startsWith('```')){fence=!fence;continue;}
    if(fence)continue;
    if(/^:::(acronym|flow|example|note)\b/.test(t)){block=true;continue;}
    if(t===':::'){block=false;continue;}
    if(block)continue;
    if(t.startsWith('## '))groups.push({title:t.slice(3),id:slug(t.slice(3)),children:[]});
    else if(t.startsWith('### ')&&groups.length)groups[groups.length-1].children.push({title:t.slice(4),id:slug(t.slice(4))});
  }
  return groups;
}
const DIAGRAM_TONES=['green','yellow','blue'];
// ::: blocks: an acronym card, a left-to-right flow with arrows, example/note asides and named slots (e.g. the knowledge check).
function markdownBlock(kind,arg,body){
  const rows=body.map(l=>l.split('|').map(c=>c.trim()));
  if(kind==='acronym'){const [title,sub]=arg.split('|').map(s=>s.trim());
    return `<figure class="rag-card" aria-label="${esc(title)}"><div class="rag-card-frame"><figcaption class="rag-card-title">${inlineMarkdown(title)}</figcaption>${sub?`<p class="rag-card-sub">${inlineMarkdown(sub)}</p>`:''}<ol class="rag-card-rows">${rows.map((r,n)=>`<li class="tone-${DIAGRAM_TONES[n%3]}"><span class="rag-letter" aria-hidden="true">${esc(r[0])}</span><strong>${inlineMarkdown(r[1]||'')}</strong><span class="rag-desc">${inlineMarkdown(r[2]||'')}</span></li>`).join('')}</ol></div></figure>`;}
  if(kind==='flow')return `<figure class="rag-flow" aria-label="${esc(arg)}"><figcaption>${inlineMarkdown(arg)}</figcaption><ol class="rag-flow-steps">${rows.map((r,n)=>`<li class="rag-flow-step tone-${DIAGRAM_TONES[Math.floor(n/2)%3]}"><span class="rag-flow-num">${n+1}</span><strong>${inlineMarkdown(r[0])}</strong>${r[1]?`<small>${inlineMarkdown(r[1])}</small>`:''}</li>`).join('')}</ol></figure>`;
  if(kind==='example'||kind==='note')return `<aside class="lesson-${kind}">${arg?`<strong class="lesson-aside-title">${inlineMarkdown(arg)}</strong>`:''}${renderMarkdown(body.join('\n')).replace(/^<div class="lesson-markdown">|<\/div>$/g,'')}</aside>`;
  return '';
}
// Bullet and numbered list lines; two spaces of indentation per nesting level.
const LIST_LINE=/^( *)([-*•]|\d+[.)])\s+(.*)$/;
function listHtml(items,from,to){
  let out='',k=from;
  while(k<to){
    const {depth,ordered,number}=items[k];
    out+=ordered?`<ol${number>1?` start="${number}"`:''}>`:'<ul>';
    while(k<to&&items[k].depth===depth&&items[k].ordered===ordered){
      let end=k+1;while(end<to&&items[end].depth>depth)end++;
      out+=`<li>${inlineMarkdown(items[k].text)}${end>k+1?listHtml(items,k+1,end):''}</li>`;k=end;
    }
    out+=ordered?'</ol>':'</ul>';
  }
  return out;
}
function renderMarkdown(source){
  const lines=String(source||'').replace(/\r/g,'').split('\n'),out=[],slug=headingSlugger();let i=0,callout=false;
  const close=()=>{if(callout){out.push('</section>');callout=false;}};
  // Cells are separated by | ; a \| inside a cell is a literal pipe.
  const cells=row=>row.trim().replace(/^\||\|$/g,'').split(/(?<!\\)\|/).map(c=>c.trim().replace(/\\\|/g,'|'));
  while(i<lines.length){
    const line=lines[i],trimmed=line.trim();
    if(!trimmed){i++;continue;}
    if(trimmed.startsWith('```')){const lang=trimmed.slice(3).trim().toLowerCase(),code=[];i++;while(i<lines.length&&!lines[i].trim().startsWith('```'))code.push(lines[i++]);i++;out.push(codeBlock(code,lang));continue;}
    const block=trimmed.match(/^:::(acronym|flow|example|note|slot)\s*(.*)$/);
    if(block){close();i++;
      if(block[1]==='slot'){out.push(`<div class="lesson-slot" data-lesson-slot="${esc(block[2].trim())}"></div>`);continue;}
      const body=[];while(i<lines.length&&lines[i].trim()!==':::')body.push(lines[i++]);i++;
      out.push(markdownBlock(block[1],block[2].trim(),block[1]==='example'||block[1]==='note'?body:body.filter(l=>l.trim())));continue;}
    if(trimmed.startsWith('## ')){close();const title=trimmed.slice(3);const kind=(SECTION_KINDS.find(([re])=>re.test(title))||[])[1];
      const id=slug(title);
      if(kind){out.push(`<section class="lesson-callout lesson-section kind-${kind}"><h3 id="${id}">${inlineMarkdown(title)}</h3>`);callout=true;}else out.push(`<h3 class="lesson-heading" id="${id}">${inlineMarkdown(title)}</h3>`);i++;continue;}
    if(trimmed.startsWith('### ')){out.push(`<h4 class="lesson-subheading" id="${slug(trimmed.slice(4))}">${inlineMarkdown(trimmed.slice(4))}</h4>`);i++;continue;}
    if(trimmed.startsWith('#### ')){out.push(`<h5 class="lesson-minor-heading">${inlineMarkdown(trimmed.slice(5))}</h5>`);i++;continue;}
    if(trimmed.startsWith('|')&&/^\|?\s*:?-{3,}/.test((lines[i+1]||'').trim())){
      const head=cells(trimmed),rows=[];i+=2;while(i<lines.length&&lines[i].trim().startsWith('|'))rows.push(cells(lines[i++]));
      out.push(`<div class="lesson-table-wrap"><table class="lesson-table"><thead><tr>${head.map(c=>`<th>${inlineMarkdown(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${inlineMarkdown(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);continue;}
    if(LIST_LINE.test(line.trimEnd())){const items=[];let m;
      while(i<lines.length&&(m=lines[i].trimEnd().match(LIST_LINE)))items.push({depth:Math.floor(m[1].length/2),ordered:/\d/.test(m[2]),number:parseInt(m[2],10)||1,text:m[3]}),i++;
      out.push(listHtml(items,0,items.length));continue;}
    const paragraph=[];while(i<lines.length&&lines[i].trim()&&!/^(```|#{2,4} |:::|\||[-*•]\s|\d+[.)]\s)/.test(lines[i].trim()))paragraph.push(lines[i++].trim());
    if(paragraph.length)out.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`);else i++;
  }
  close();
  return `<div class="lesson-markdown">${out.join('')}</div>`;
}
// Lesson text for every course: everything is escaped first, then a safe Markdown subset is applied.
// Inline: `code`, **bold** and *italic* (never inside code). Blocks: ## sections, ### subheadings, lists, tables and fenced code.
function lessonInline(text){
  // Code spans become placeholders first so their contents are never formatted, yet bold can still wrap them.
  const codes=[];
  const marked=esc(String(text).replace(/`([^`]+)`/g,(_,code)=>`\u0000${codes.push(code)-1}\u0000`));
  return marked.replace(/\*\*(\S[^*]*?\S|\S)\*\*/g,'<strong>$1</strong>').replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:!?)]|$)/g,'$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1 ↗</a>')
    .replace(/\u0000(\d+)\u0000/g,(_,i)=>`<code>${esc(codes[i])}</code>`);
}
const CODE_LABELS={java:'Java',bash:'Terminal',sql:'SQL',javascript:'JavaScript',js:'JavaScript',jsx:'React (JSX)',html:'HTML',css:'CSS',json:'JSON',yaml:'YAML',groovy:'Gradle',properties:'Properties',dockerfile:'Dockerfile',nginx:'Nginx',ini:'Config',python:'Python'};
// Section headings that get a themed callout in lesson text.
const SECTION_KINDS=[[/^learning objectives$/i,'objectives'],[/^common mistakes$/i,'mistakes'],[/^(practice exercise|guided lab)$/i,'practice'],[/^(key takeaways|review before moving on)$/i,'takeaways']];
const MARKDOWN_BLOCK=/^(#{2,3} |```|[-*•] |\d+\.\s|\|)/m;
function codeBlock(lines,lang){return `<div class="code-block"><div class="code-head"><span>${esc(CODE_LABELS[lang]||lang||'Text')}</span><button type="button" class="code-copy" data-act="copy-code">Copy</button></div><pre class="lesson-code"><code>${esc(lines.join('\n'))}</code></pre></div>`;}
function renderLessonContent(content){
  content=String(content||'').replace(/\r/g,'');
  // Plain text without any Markdown keeps its line breaks.
  if(!MARKDOWN_BLOCK.test(content))return `<div class="structured-lesson"><div class="lesson-text">${esc(content)}</div></div>`;
  const parts=[],sections=[],lines=content.split('\n');let paragraph=[],code=[],inCode=false,list=null,lang='';
  const flush=()=>{if(paragraph.length){parts.push(`<p>${lessonInline(paragraph.join(' '))}</p>`);paragraph=[];}};
  const closeList=()=>{if(list){parts.push(`</${list}>`);list=null;}};
  const openList=tag=>{flush();if(list!==tag){closeList();parts.push(`<${tag}>`);list=tag;}};
  const cells=row=>row.trim().replace(/^\||\|$/g,'').split(/(?<!\\)\|/).map(c=>c.trim().replace(/\\\|/g,'|'));
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(line.trimStart().startsWith('```')){flush();closeList();if(inCode){parts.push(codeBlock(code,lang));code=[];}else lang=line.trim().slice(3).trim().toLowerCase();inCode=!inCode;continue;}
    if(inCode){code.push(line);continue;}
    const trimmed=line.trim();
    if(trimmed.startsWith('## ')){
      flush();closeList();const title=trimmed.slice(3),id='lesson-section-'+sections.length,kind=(SECTION_KINDS.find(([re])=>re.test(title))||[])[1]||'topic';
      parts.push(`${sections.length?'</section>':''}<section class="lesson-section kind-${kind}"><h3 id="${id}" tabindex="-1">${esc(title)}</h3>`);sections.push({id,title});}
    else if(trimmed.startsWith('### ')){flush();closeList();parts.push(`<h4 class="lesson-subheading">${lessonInline(trimmed.slice(4))}</h4>`);}
    else if(trimmed.startsWith('|')&&/^\|?\s*:?-{3,}/.test((lines[i+1]||'').trim())){
      flush();closeList();const head=cells(trimmed),rows=[];i+=2;while(i<lines.length&&lines[i].trim().startsWith('|'))rows.push(cells(lines[i++]));i--;
      parts.push(`<div class="lesson-table-wrap"><table class="lesson-table"><thead><tr>${head.map(c=>`<th>${lessonInline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${lessonInline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);}
    else if(/^[-*•]\s/.test(trimmed)){openList('ul');parts.push(`<li>${lessonInline(trimmed.replace(/^[-*•]\s+/,''))}</li>`);}
    else if(/^\d+\.\s/.test(trimmed)){openList('ol');parts.push(`<li>${lessonInline(trimmed.replace(/^\d+\.\s+/,''))}</li>`);}
    else if(!trimmed){flush();closeList();}
    else{closeList();paragraph.push(trimmed);}
  }
  flush();closeList();if(code.length)parts.push(codeBlock(code,lang));if(sections.length)parts.push('</section>');
  // The jump list helps only in longer lessons.
  const outline=sections.length<3?'':`<details class="lesson-outline"><summary>On this page · ${sections.length} sections</summary><nav aria-label="Lesson sections">${sections.map((s,i)=>`<button type="button" class="auth-link" data-act="lesson-section" data-id="${s.id}"><span class="outline-index">${i+1}</span>${esc(s.title)}</button>`).join('')}</nav></details>`;
  return `<div class="structured-lesson">${outline}${parts.join('')}</div>`;
}
// ::: blocks, #### headings and indented (nested) lists need the extended renderer.
const RICH_MARKDOWN=/^\s*:::|^#### |^ {2,}([-*•]|\d+[.)])\s/m;
function richLessonContent(content){
  const groups=markdownOutline(content);
  const outline=groups.length<3?'':`<details class="lesson-outline"><summary>On this page · ${groups.length} sections</summary><nav aria-label="Lesson sections">${groups.map((g,i)=>`<button type="button" class="auth-link" data-act="lesson-section" data-id="${g.id}"><span class="outline-index">${i+1}</span>${inlineMarkdown(g.title)}</button>`).join('')}</nav></details>`;
  return `<div class="structured-lesson rich-lesson">${outline}${renderMarkdown(content)}</div>`;
}
const lessonText=content=>RICH_MARKDOWN.test(content)?richLessonContent(content):renderLessonContent(content);
function lessonBody(l){
  return `${l.description?`<div class="lesson-overview"><span>Overview</span><p>${esc(l.description)}</p></div>`:''}${lessonVideo(l.videoUrl,l.title,l)}${l.content?lessonText(l.content):''}${l.documentUrl?`<p><a class="material-link" href="${esc(l.documentUrl)}" target="_blank" rel="noopener">${icon('file')} ${esc(l.documentName||'Lesson document')}</a></p>`:''}${l.resources?.length?`<h3 class="sub-heading">Learning resources</h3><ul class="resource-links">${l.resources.filter(r=>r.url).map(r=>`<li><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title||r.url)} ↗</a><small>${esc(hostOf(r.url))}</small></li>`).join('')}</ul>`:''}${l.exercise?`<div class="exercise-box"><h3>Practical exercise</h3><p>${esc(l.exercise)}</p></div>`:''}`;
}
// A lesson video counts toward completion only when it is a tracked file (uploaded or packaged) with a known length.
const tracksVideo=l=>Boolean(l.videoUrl&&l.videoSeconds&&!EMBED.test(embedUrl(l.videoUrl)));
function videoStatus(lesson){
  const done=learning.run.lessons?.[lesson.id],watch=learning.run.watch?.[lesson.id]||{},seconds=lesson.videoSeconds||0;
  if(!tracksVideo(lesson))return '';
  const percent=Math.min(100,Math.round((watch.watched||0)/seconds*100));
  const rule=lesson.activity?'Watch the video, then complete the exercise below.':lesson.exercise?`Watch at least ${lesson.completionPercent}% of the video, then submit your response.`:`Completes automatically at ${lesson.completionPercent}% watched.`;
  return `<div class="video-status" id="lesson-video-status" role="status"><span>${icon('play')} ${clock(seconds)}</span><span data-watch-percent>${done?'✓ Lesson completed':`Watched ${percent}%`}</span><span>${done?'You can rewatch any time.':rule}</span>${!done&&(watch.position||0)>5?`<span>Resumes at ${clock(watch.position)}</span>`:''}</div>`;
}
function lessonExercisePanel(lesson){
  const activity=lesson.activity,state=learning.run.activity?.[lesson.id],done=learning.run.lessons?.[lesson.id];
  const results=Object.fromEntries((state?.results||[]).map(r=>[r.id,r]));
  return `<section class="activity-box" aria-labelledby="activity-title"><div class="section-heading"><h3 id="activity-title">Practical exercise</h3><span class="tag ${done?'success':''}">${done?`PASSED · BEST ${state?.bestScore??done.score}%`:`PASS MARK ${activity.passPercent}%`}</span></div><p class="muted">Write a prompt for each task. Each prompt is checked against a short rubric; you then see what you covered, tips, and a model answer. ${state?`Attempts: ${state.attempts} · Latest score: ${state.lastScore}% · Best: ${state.bestScore}%.`:'You can resubmit as many times as you like.'}</p>
  <form data-form="lesson-activity" data-lesson="${esc(lesson.id)}">${activity.tasks.map((task,i)=>{const r=results[task.id];return `<div class="activity-task"><h4>Task ${i+1}: ${esc(task.title)}</h4><p>${esc(task.instructions)}</p><p class="criteria-hint">A strong prompt: ${task.criteria.map(esc).join(' · ')}</p><label for="answer-${i}">Your prompt</label><textarea id="answer-${i}" name="answer-${i}" rows="6" maxlength="3000" required>${esc(state?.answers?.[i]||'')}</textarea>${r?`<div class="task-feedback ${r.score>=activity.passPercent?'good':''}"><strong>Score: ${r.score}%</strong>${r.tooShort?'<p>This prompt is too short to cover the rubric. Aim for at least a couple of sentences.</p>':''}<ul>${r.criteria.map(c=>`<li class="${c.met?'met':'missed'}">${c.met?'✓':'✗'} ${esc(c.label)}${c.met?'':` — ${esc(c.tip)}`}</li>`).join('')}</ul><details><summary>Sample answer and explanation</summary><pre>${esc(r.modelAnswer)}</pre>${r.explanation?`<p class="model-why"><b>Why it works:</b> ${esc(r.explanation)}</p>`:''}</details></div>`:''}</div>`;}).join('')}<button class="btn" type="submit">${state?'Resubmit prompts':'Submit prompts'} ${icon('check')}</button><p class="form-status" role="status"></p></form><p class="muted">The rubric looks for the elements of a strong prompt; compare your wording with the model answer to judge the rest.</p></section>`;
}
let inlineAttempt=null,inlineResult=null;
// Knowledge checks and the final assessment run inline on the lesson page, using the standard assessment engine.
function inlineResultView(r){
  if(r.status==='expired')return '<div class="notice" role="status">Time expired. The attempt ended without a score and counts toward your attempts.</div>';
  return `<div class="inline-result ${r.status==='passed'?'good':''}" role="status"><strong>${r.status==='passed'?'Passed':'Not passed yet'}: ${r.score}/${r.total} correct (${r.percent}%) · pass mark ${r.passPercent}%</strong><ol>${r.details.map(d=>`<li class="${d.correct?'met':'missed'}">${d.correct?'✓ Correct.':`✗ Incorrect. Correct answer: <b>${esc(d.answer||'')}</b>.`} ${esc(d.explanation||'')}</li>`).join('')}</ol></div>`;
}
function inlineAssessmentPanel(id,heading){
  const info=(currentCourseExtras?.assessments||[]).find(a=>a.id===id);
  if(!info)return '';
  const attempt=inlineAttempt?.assessmentId===id?inlineAttempt.attempt:null,result=inlineResult?.assessmentId===id?inlineResult.result:null;
  const status=info.passed?`<span class="tag success">PASSED · BEST ${info.best}%</span>`:info.best!=null?`<span class="tag warn">BEST ${info.best}%</span>`:'<span class="tag gray">NOT TAKEN</span>';
  const body=attempt?`<form data-form="inline-assessment" data-id="${esc(id)}">${attempt.questions.map((q,i)=>`<fieldset class="question"><legend><span>${i+1}.</span> ${esc(q.prompt)}</legend>${q.code?codeBlock([q.code],''):''}${q.options.map((o,j)=>`<label class="answer"><input type="radio" name="q${i}" value="${j}" required><span class="answer-letter" aria-hidden="true">${String.fromCharCode(65+j)}</span><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}<button class="btn" type="submit">Submit answers ${icon('check')}</button><p class="form-status" role="status"></p></form>`
    :`${result?inlineResultView(result):''}${info.attemptsLeft?`<button class="btn ${result||info.passed?'secondary':''}" data-act="inline-start" data-id="${esc(id)}">${info.best!=null?'Retake':'Start'} ${esc(heading.toLowerCase())} ${icon('arrow')}</button>`:'<p class="muted">No attempts left.</p>'}`;
  return `<section class="knowledge-check knowledge-card" aria-label="${esc(heading)}"><div class="knowledge-head"><span class="knowledge-icon">${icon('check')}</span><div><h3>${esc(heading)}</h3><p>Pass mark ${info.passPercent}% · ${info.attemptsLeft} attempt${info.attemptsLeft===1?'':'s'} left · answer order is shuffled on every attempt.</p></div>${status}</div>${body}</section>`;
}
async function refreshCourseExtras(){
  const data=await api('learning?courseId='+encodeURIComponent(currentCourseInfo.id));
  currentCourseExtras.assessments=data.assessments||[];applyLearning(data.learning);
}
// Imported courses keep their source's modules; a heading starts each module in the lesson list.
function moduleHeading(list,i){
  const l=list[i];
  return l.moduleIndex!=null&&(i===0||list[i-1].moduleIndex!==l.moduleIndex)?`<div class="curriculum-module">${esc(l.moduleTitle)}</div>`:'';
}
function sourceCredit(course){
  const s=course?.source;
  return s?`<p class="source-credit">${s.importStatus==='reference'?'Lessons are on':'Content from'} <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.platform)} ↗</a>. Each lesson links to its original page.</p>`:'';
}
// Packaged modules carry a "Section N · Name." prefix in their description; courses without one show a single list.
function moduleSection(lesson){
  const match=/^Section (\d+) · ([^.]+)\.\s*/.exec(lesson.description||'');
  return match?{number:Number(match[1]),name:match[2],summary:lesson.description.slice(match[0].length)}:{number:0,name:'',summary:lesson.description||''};
}
const playerPager=(attrs,label,title,dir)=>`<button class="pager ${dir}" ${attrs}><small>${label}</small><span>${dir==='prev'?'← ':''}${esc(title)}${dir==='next'?' →':''}</span></button>`;
// Title block shared by the course player and the course builder preview.
function lessonHeader(lesson,{unit,index,total,section,completed,meta=[]}){
  const pills=[`${icon('clock')} ${esc(fmtDuration(Number(lesson.durationMinutes)||0))}`,lesson.videoSeconds?`${icon('play')} Video ${clock(lesson.videoSeconds)}`:'',...meta].filter(Boolean).map(m=>`<span>${m}</span>`).join('');
  return `<header class="module-header"><div class="module-crumbs"><span class="tag">${unit.toUpperCase()} ${index+1} OF ${total}</span>${section?.name?`<span class="crumb">Section ${section.number} · ${esc(section.name)}</span>`:''}${completed?'<span class="tag success">✓ Completed</span>':''}</div><h2>${esc(lesson.title||'Untitled lesson')}</h2><div class="module-meta">${pills}</div></header>`;
}
// Topics (## headings) and sub-topics of a lesson, with the ids its rendered headings carry.
function lessonTopics(lesson){
  const content=String(lesson.content||'');
  if(RICH_MARKDOWN.test(content))return markdownOutline(content);
  if(!MARKDOWN_BLOCK.test(content))return [];
  const topics=[];let fence=false;
  for(const line of content.replace(/\r/g,'').split('\n')){
    if(line.trimStart().startsWith('```')){fence=!fence;continue;}
    if(!fence&&line.trim().startsWith('## '))topics.push({title:line.trim().slice(3),id:'lesson-section-'+topics.length,children:[]});
  }
  return topics;
}
// The open lesson lists every topic under it in the sidebar; each link jumps to that part of the lesson.
function topicList(lesson){
  const topics=lessonTopics(lesson);
  if(topics.length<2)return '';
  const link=(t,sub)=>`<button type="button" class="topic-link${sub?' sub':''}" data-act="lesson-section" data-id="${esc(t.id)}">${inlineMarkdown(t.title)}</button>`;
  return `<nav class="topic-list" aria-label="Topics in this ${esc(lesson.title)}">${topics.map(t=>link(t,false)+t.children.map(c=>link(c,true)).join('')).join('')}</nav>`;
}
// One player for every lesson-based course: packaged courses and courses built in Manage Courses.
function lessonCoursePlayer(){
  const list=currentCourseExtras?.courseLessons||[],done=learning.run.lessons||{},checkpoints=learning.run.checkpoints||[];
  const courseCheck=(currentCourseExtras?.assessments||[]).find(a=>a.id===currentCourseExtras.requiredAssessmentId);
  // When a lesson shows the required assessment inline (single-lesson courses such as RAG), it is not a separate final step.
  const inlineRequired=Boolean(courseCheck&&list.some(l=>l.assessmentId===courseCheck.id)),required=inlineRequired?null:courseCheck;
  const unit=checkpoints.length||list.some(l=>l.practice||l.quiz?.length)?'Module':'Lesson',lower=unit.toLowerCase(),units=lower+'s';
  const count=list.filter(l=>done[l.id]).length,passed=checkpoints.filter(c=>c.passed).length;
  const progress=checkpoints.length?courseProgress():list.length?Math.round(count/list.length*100):0;
  const upNext=list.find(l=>!l.locked&&!done[l.id])||checkpoints.find(c=>c.ready&&!c.passed)||(required&&!required.passed?required:null);
  const stat=(value,label)=>`<div class="hero-stat"><b>${value}</b><span>${label}</span></div>`;
  const stats=stat(`${count}<small>/${list.length}</small>`,`${unit}s completed`)
    +(checkpoints.length?stat(`${passed}<small>/${checkpoints.length}</small>`,'Assessments passed'):courseCheck?stat(courseCheck.passed?'Passed':'Not yet',`${inlineRequired?'Knowledge check':'Final assessment'} · pass ${courseCheck.passPercent}%`):'')
    +stat(learning.run.completedAt?'Done':upNext?esc(upNext.title):'Review','Up next');
  const head=`<section class="player-hero"><div class="player-hero-main"><div class="eyebrow">Course run ${learning.run.runNumber} · ${esc(capital(currentCourseInfo.difficulty||'beginner'))} · ${esc(fmtDuration(currentCourseInfo.durationMinutes))}</div><h1>${esc(currentCourseInfo.title)}</h1><div class="hero-stats">${stats}</div>${sourceCredit(currentCourseInfo)}</div><div class="player-hero-side"><div class="progress-ring" style="--p:${progress}" role="img" aria-label="Course progress ${progress}%"><b>${progress}%</b><span>complete</span></div><button class="btn secondary" id="restart-course">Start new course run</button></div></section><div id="restart-confirm" class="notice hidden"><p>Start again from the first ${lower}? Your current progress resets for this run. Earned certificates stay available.</p><button class="btn" id="confirm-restart">Yes, start a new run</button> <button class="btn secondary" id="cancel-restart">Keep current run</button></div>`;
  if(!list.length)return `<div class="course-player">${head}${emptyState('No lessons yet','This course has no lessons. Please check back later.')}</div>`;
  const showFinal=selectedLessonId==='final'&&required&&!checkpoints.length;
  // Resume: the lesson chosen now, else the last one opened, else the first unlocked one not yet completed.
  const current=showFinal?null:[list.find(l=>l.id===selectedLessonId),list.find(l=>l.id===learning.run.lastLessonId),list.find(l=>!l.locked&&!done[l.id])].find(l=>l&&!l.locked)||list[0];
  const index=current?list.indexOf(current):list.length;
  const checkpoint=checkpoints.find(c=>c.id===selectedCheckpointId)||(!selectedLessonId?checkpoints.find(c=>c.ready&&!c.passed):null);
  if(checkpoint)selectedCheckpointId=checkpoint.id;
  let body;
  if(checkpoint)body=checkpointOverview(checkpoint);
  else if(showFinal){
    const fact=(value,label)=>`<div class="assessment-fact"><b>${value}</b><span>${label}</span></div>`;
    const last=list[list.length-1];
    body=`<article class="panel lesson-content assessment-view"><header class="module-header"><div class="module-crumbs"><span class="tag">FINAL ASSESSMENT</span>${required.passed?'<span class="tag success">✓ Passed</span>':''}</div><h2>${esc(required.title)}</h2><p class="assessment-intro">Questions are drawn at random from the whole course. Pass it, and complete every ${lower}, to earn your certificate.${count<list.length?` You have completed ${count} of ${list.length} ${units}; finishing them first is recommended.`:''}</p></header><div class="assessment-facts">${required.questionCount?fact(required.questionCount,'Questions'):''}${required.timeLimitMinutes?fact(`${required.timeLimitMinutes} min`,'Time limit'):''}${fact(`${required.passPercent}%`,'Pass mark')}${fact(required.attemptsLeft,'Attempts left')}${required.best!=null?fact(`${required.best}%`,'Best score'):''}</div>${inlineAssessmentPanel(required.id,'Final assessment')}<nav class="lesson-nav module-pager" aria-label="${unit} navigation">${playerPager(`data-act="lesson-select" data-id="${esc(last.id)}"`,`Back to the last ${lower}`,last.title,'prev')}</nav></article>`;
  }else{
    const state=done[current.id],section=moduleSection(current),nextCheckpoint=checkpoints.find(c=>c.afterLesson===index+1);
    let completion='';
    if(current.quiz?.length)completion=lessonKnowledgePanel(current);
    else if(current.activity)completion=lessonExercisePanel(current);
    else if(state)completion=`<div class="notice success">✓ ${unit} completed ${esc(fmtDate(state.completedAt))}.${state.response?`<br><b>Your response:</b> ${esc(state.response)}`:''}</div>`;
    else if(tracksVideo(current)&&!current.exercise)completion='';
    else completion=`<form class="lesson-complete" data-form="lesson-complete" data-lesson="${esc(current.id)}">${current.exercise?`<label for="lesson-response">Your response to the practical exercise</label><textarea id="lesson-response" name="response" rows="4" minlength="10" maxlength="5000" required></textarea>`:''}<button class="btn" type="submit">Mark ${lower} complete ${icon('check')}</button><p class="form-status" role="status"></p></form>`;
    const prev=list[index-1]?playerPager(`data-act="lesson-select" data-id="${esc(list[index-1].id)}"`,`Previous ${lower}`,list[index-1].title,'prev'):'<span></span>';
    const next=nextCheckpoint&&!nextCheckpoint.passed?playerPager(`data-checkpoint-select="${esc(nextCheckpoint.id)}"`,'Up next',nextCheckpoint.title,'next')
      :list[index+1]?playerPager(`data-act="lesson-select" data-id="${esc(list[index+1].id)}" ${list[index+1].locked?'disabled':''}`,list[index+1].locked?'Locked':`Next ${lower}`,list[index+1].title,'next')
      :required&&!checkpoints.length?playerPager('data-act="lesson-select" data-id="final"','Up next','Final assessment','next'):'';
    const check=current.assessmentId?inlineAssessmentPanel(current.assessmentId,'Knowledge check'):'',slot='<div class="lesson-slot" data-lesson-slot="knowledge-check"></div>';
    const lessonHtml=lessonBody({...current,description:section.summary,tracked:true}),placed=Boolean(check)&&lessonHtml.includes(slot);
    const slotted=placed?lessonHtml.replace(slot,()=>check):lessonHtml;
    const meta=[current.quiz?.length?`${icon('check')} ${current.quiz.length}-question knowledge check`:'',current.assessmentId?`${icon('check')} Knowledge check`:'',current.exercise||current.activity?`${icon('file')} Practical exercise`:'',nextCheckpoint?`${icon('target')} Followed by an assessment`:''];
    body=`<article class="panel lesson-content module-view">${lessonHeader(current,{unit,index,total:list.length,section,completed:state,meta})}${current.moduleTitle?`<p class="lesson-module">${esc(current.moduleTitle)}</p>`:''}${slotted}${videoStatus(current)}${current.practice?pythonPracticePanel(current):''}${placed?'':check}${completion}<nav class="lesson-nav module-pager" aria-label="${unit} navigation">${prev}${next}</nav></article>`;
  }
  // Sidebar: course order, each module followed by its assessment, grouped by section when sections exist.
  const activeId=checkpoint?.id||(showFinal?'final':current.id),groups=[];
  list.forEach((l,i)=>{const s=moduleSection(l);let g=groups[groups.length-1];if(!g||g.number!==s.number){g={...s,items:[]};groups.push(g);}g.items.push({lesson:l,index:i,checkpoints:checkpoints.filter(c=>c.afterLesson===i+1)});});
  const row=({lesson:l,index:i,checkpoints:cs})=>{const selected=l.id===activeId,status=l.locked?'locked':done[l.id]?'done':selected?'current':'open';
    return `${moduleHeading(list,i)}<button class="lesson-item module-row is-${status} ${selected?'selected':''}" data-act="lesson-select" data-id="${esc(l.id)}" ${l.locked?'disabled':''} ${selected?'aria-current="step"':''}><span class="module-badge" aria-hidden="true">${status==='done'?'✓':status==='locked'?'🔒':i+1}</span><span class="module-text">${esc(l.title)}<small>${status==='done'?'Completed':status==='locked'?'Locked':esc(fmtDuration(l.durationMinutes))}</small></span></button>${selected?topicList(l):''}${cs.map(checkpointSidebarItem).join('')}`;};
  const groupHtml=g=>{if(!g.name)return g.items.map(row).join('');const finished=g.items.filter(x=>done[x.lesson.id]).length,open=g.items.some(x=>x.lesson.id===activeId||x.checkpoints.some(c=>c.id===activeId));
    return `<details class="curriculum-group ${finished===g.items.length?'is-done':''}" ${open?'open':''}><summary><span class="group-index">${finished===g.items.length?'✓':g.number}</span><span class="group-title">${esc(g.name)}<small>${finished}/${g.items.length} ${g.items.length===1?lower:units}</small></span></summary><div class="group-items">${g.items.map(row).join('')}</div></details>`;};
  const finalRow=!required?'':checkpoints.length
    ?`<a class="lesson-item checkpoint-item ${required.passed?'is-done':'is-ready'}" href="#assessments"><span class="module-badge" aria-hidden="true">${required.passed?'✓':'★'}</span><span class="module-text">${esc(required.title)}<small>Course assessment · pass ${required.passPercent}%</small></span></a>`
    :`<button class="lesson-item checkpoint-item final-row ${required.passed?'is-done':'is-ready'} ${showFinal?'selected':''}" data-act="lesson-select" data-id="final" ${showFinal?'aria-current="step"':''}><span class="module-badge" aria-hidden="true">${required.passed?'✓':'★'}</span><span class="module-text">Final assessment<small>${required.passed?'Passed':`Pass mark ${required.passPercent}%`}</small></span></button>`;
  const sidebar=`<aside class="panel curriculum"><div class="curriculum-head"><h3>Course content</h3><p class="muted">${count} of ${list.length} ${units}${checkpoints.length?` · ${passed}/${checkpoints.length} assessments passed`:''}</p><div class="progress"><span style="width:${progress}%"></span></div></div><div class="curriculum-list">${groups.map(groupHtml).join('')}${finalRow}</div>${learning.run.completedAt?`<a class="btn certificate-link" href="#certificates">${icon('award')} View your certificate</a>`:''}${count===list.length&&required&&!required.passed?`<p class="muted curriculum-note">All ${units} done. Pass the final assessment to earn your certificate.</p>`:''}</aside>`;
  return `<div class="course-player">${head}<div class="lesson-layout">${body}${sidebar}</div></div>`;
}
// Records resume position and continuous viewing; seeking ahead does not add watched time.
let lessonRenderPending=false;
function wireLessonVideo(){
  const video=document.getElementById('lesson-video');
  if(!video||video.dataset.wired||!learning.run.id)return;
  video.dataset.wired='1';
  const lessonId=video.dataset.lesson,lesson=(currentCourseExtras?.courseLessons||[]).find(l=>l.id===lessonId);if(!lesson)return;
  const saved=learning.run.watch?.[lessonId]||{};
  let watched=saved.watched||0,last=0,lastTime=performance.now(),lastSaved=0;
  const length=()=>lesson.videoSeconds||video.duration||0;
  const status=()=>{const el=document.querySelector('[data-watch-percent]');if(el&&!learning.run.lessons?.[lessonId]&&length())el.textContent=`Watched ${Math.min(100,Math.round(watched/length()*100))}%`;};
  const save=force=>{
    const now=performance.now();if(!force&&now-lastSaved<5000)return;lastSaved=now;
    learningRequest('lesson-video',{lessonId,position:Math.round(video.currentTime*10)/10,watched:Math.min(length()||watched,Math.round(watched*10)/10)}).then(result=>{
      if(result.lessonCompleted===lessonId){
        toast('Lesson completed. Nice work!');const el=document.querySelector('[data-watch-percent]');if(el)el.textContent='✓ Lesson completed';
        // Re-render now if playback has stopped; otherwise wait so the video is not interrupted.
        if(video.paused||video.ended||!video.isConnected)render();else lessonRenderPending=true;
      }
    }).catch(()=>{});
  };
  const resume=()=>{if((saved.position||0)>5&&saved.position<video.duration-3)video.currentTime=saved.position;last=video.currentTime;lastTime=performance.now();};
  // A cached video may already have its metadata before this runs.
  if(video.readyState>=1)resume();else video.addEventListener('loadedmetadata',resume,{once:true});
  video.addEventListener('seeking',()=>{last=video.currentTime;lastTime=performance.now();});
  video.addEventListener('play',()=>{last=video.currentTime;lastTime=performance.now();});
  video.addEventListener('timeupdate',()=>{
    const now=performance.now(),delta=video.currentTime-last,elapsed=(now-lastTime)/1000;
    if(!video.paused&&delta>0&&delta<=elapsed*Math.max(1,video.playbackRate)+0.75&&last<=watched+1)watched=Math.max(watched,video.currentTime);
    last=video.currentTime;lastTime=now;status();save(false);
  });
  const settle=()=>{save(true);if(lessonRenderPending){lessonRenderPending=false;setTimeout(render,400);}};
  video.addEventListener('pause',settle);
  video.addEventListener('ended',settle);
}

// ---------------------------------------------------------------- event handling (delegated so re-renders keep working)

function formValues(form){const values={};new FormData(form).forEach((v,k)=>{values[k]=typeof v==='string'?v.trim():v;});return values;}
const intOrNull=v=>v===''||v==null?null:Number(v);
async function submitForm(form,task){
  const button=form.querySelector('button[type="submit"]'),status=form.querySelector('.form-status');
  if(button?.disabled)return;if(button)button.disabled=true;
  try{await task();}catch(error){if(status)status.textContent=error.message;else toast(error.message);if(button)button.disabled=false;}
}
const ACTIONS={
  retry:el=>{delete pageCache[el.dataset.key];render();},
  'notifications-read-all':async()=>{const data=await api('me/notifications/read',{all:true});notificationState.items=data.notifications;notificationState.unread=data.unread;render();},
  'notification-open':async el=>{const data=await api('me/notifications/read',{ids:[Number(el.dataset.id)]});notificationState={items:data.notifications,unread:data.unread,open:false};if(el.dataset.link)location.hash=el.dataset.link;render();},
  'dash-period-clear':()=>{devFilters.dashboard={};render();},
  'course-filter':el=>{courseFilter=el.dataset.value;render();},
  'report-preset':el=>{devFilters.report={type:el.dataset.type,page:1};},
  'report-reset':()=>{devFilters.report={type:devFilters.report.type,page:1};render();},
  'report-page':el=>{devFilters.report.page=Number(el.dataset.page);render();},
  'report-export':async el=>{const data=await api('manage/reports'+el.dataset.query);download(`shimentox-${data.type}-report.csv`,toCSV(data.columns,data.rows),'text/csv;charset=utf-8');toast(`Exported ${data.rows.length} records.`);},
  'history-page':el=>{historyPage=Number(el.dataset.page);render();},
  'record-delete':async el=>{await api('me/records',{id:el.dataset.id,delete:true});refreshData('me-history');render();},
  'path-new':()=>{pathEditor={title:'',description:'',status:'draft',sequential:true,courseIds:[]};render();},
  'path-edit':el=>{const p=pageCache['m-paths'].data.paths.find(x=>x.id===el.dataset.id);pathEditor={id:p.id,title:p.title,description:p.description,status:p.status,sequential:p.sequential,courseIds:p.courses.map(c=>c.id)};render();},
  'path-cancel':()=>{pathEditor=null;render();},
  'path-add-course':()=>{capturePathForm();const select=document.getElementById('path-add-course');if(select?.value){pathEditor.courseIds.push(select.value);render();}},
  'path-remove-course':el=>{capturePathForm();pathEditor.courseIds.splice(Number(el.dataset.index),1);render();},
  'path-move':el=>{capturePathForm();const i=Number(el.dataset.index),j=i+Number(el.dataset.dir),ids=pathEditor.courseIds;[ids[i],ids[j]]=[ids[j],ids[i]];render();},
  'path-assign':el=>{pathAssign=el.dataset.id;render();},
  'path-assign-cancel':()=>{pathAssign=null;render();},
  'path-unassign':async el=>{const data=await api(`manage/path-assignments/${el.dataset.id}/delete`,{});pageCache['m-paths']={data};refreshData('me-paths');render();},
  'path-progress':el=>{pathProgressId=el.dataset.id;delete pageCache['path-progress:'+el.dataset.id];render();},
  'path-progress-close':()=>{pathProgressId=null;render();},
  'skill-delete':async el=>{const data=await api('manage/skills',{id:el.dataset.id,delete:true});pageCache['m-skills']={data};refreshData('org');render();},
  'goal-status':async el=>{const goal=pageCache['me-skills'].data.goals.find(g=>g.id===el.dataset.id);const data=await api('me/goals',{id:goal.id,title:goal.title,skillId:goal.skillId,targetLevel:goal.targetLevel,targetDate:goal.targetDate,status:el.dataset.status});pageCache['me-skills']={data};refreshData('me-dash');render();},
  'goal-delete':async el=>{const data=await api('me/goals',{id:el.dataset.id,delete:true});pageCache['me-skills']={data};refreshData('me-dash');render();},
  'session-register':async el=>{const data=await api(`me/sessions/${el.dataset.id}/register`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='You are registered for the session.';render();},
  'session-cancel':async el=>{const data=await api(`me/sessions/${el.dataset.id}/cancel`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='Your registration was cancelled.';render();},
  'session-new':()=>{sessionEditor={};render();},
  'session-edit':el=>{sessionEditor={...pageCache['m-sessions'].data.sessions.find(s=>s.id===el.dataset.id)};render();},
  'session-editor-close':()=>{sessionEditor=null;render();},
  'session-roster':el=>{sessionRoster=el.dataset.id;delete pageCache['roster:'+el.dataset.id];render();},
  'session-roster-close':()=>{sessionRoster=null;render();},
  'assessment-start':async el=>{const item=pageCache['me-assess'].data.assessments.find(a=>a.id===el.dataset.id);const data=await api(`me/assessments/${item.id}/start`,{});activeAssessment={id:item.id,title:item.title,attempt:data.attempt};assessmentResult=null;render();updateAssessmentTimer();},
  'assessment-leave':()=>{activeAssessment=null;refreshData('me-assess');render();},
  'assessment-result-close':()=>{assessmentResult=null;render();},
  'assessment-new':()=>{assessmentEditor={};render();},
  'assessment-edit':el=>{assessmentEditor={...pageCache['m-assess'].data.assessments.find(a=>a.id===el.dataset.id)};render();},
  'assessment-editor-close':()=>{assessmentEditor=null;render();},
  'assessment-attempts':el=>{assessmentAttemptsId=el.dataset.id;delete pageCache['attempts:'+el.dataset.id];render();},
  'assessment-attempts-close':()=>{assessmentAttemptsId=null;render();},
  'user-edit':el=>{editUserId=el.dataset.id;render();},
  'user-edit-cancel':()=>{editUserId=null;render();},
  'org-delete':async el=>{if(!confirm(`Delete ${el.dataset.name}? Employees and courses keep their records; related assignments are removed.`))return;const data=await api('manage/'+el.dataset.kind,el.dataset.kind==='categories'?{name:el.dataset.name,delete:true}:{id:el.dataset.id,delete:true});pageCache.org={data};await loadAdminState();render();},
  // Unused courses are deleted permanently; courses with learner records can only be archived, which keeps them.
  'course-delete':async el=>{
    const course=adminState.courses.find(c=>c.id===el.dataset.id);if(!course)return;
    if(course.learners){
      if(course.status==='archived'){toast(`“${course.title}” is archived. ${course.learners} employee${course.learners===1?' has':'s have'} records in it, so it is kept for their history.`);return;}
      if(!confirm(`${course.learners} employee${course.learners===1?' has':'s have'} started “${course.title}”, so it cannot be deleted without losing their progress and certificates.\n\nArchive it instead? It disappears from catalogs and learning paths; records are kept.`))return;
      await api(`admin/courses/${encodeURIComponent(course.id)}/archive`,{});await loadAdminState();render();toast(`“${course.title}” archived.`);return;
    }
    if(!confirm(`Delete “${course.title}” permanently?\n\nIts lessons, assessments, assignments and learning-path entries are removed. This cannot be undone.`))return;
    await api(`admin/courses/${encodeURIComponent(course.id)}/delete`,{});
    if(editingCourse===course.id)editingCourse=null;
    await loadAdminState();render();toast(`“${course.title}” deleted.`);
  },
  'course-preview':el=>{const course=adminState.courses.find(c=>c.id===el.dataset.id);if(course?.format==='lessons'){if(location.hash!=='#admin-courses')location.hash='admin-courses';return openCourseBuilder(course.id,4);}previewCourseId=el.dataset.id;delete pageCache['preview:'+el.dataset.id];location.hash='course-preview';},
  'copy-code':async el=>{const code=el.closest('.code-block')?.querySelector('code')?.textContent||'';await navigator.clipboard.writeText(code);el.textContent='Copied ✓';setTimeout(()=>{el.textContent='Copy';},1600);},
  'lesson-section':el=>{const heading=document.getElementById(el.dataset.id);if(heading){heading.scrollIntoView({behavior:'smooth',block:'start'});heading.focus({preventScroll:true});}},
  'lesson-select':el=>{if(activeExam||examStarting||examFinishing)return;const target=currentCourseExtras?.courseLessons?.find(l=>l.id===el.dataset.id);if(target?.locked)return;selectedCheckpointId=null;selectedLessonId=el.dataset.id;inlineAttempt=null;examNotice='';render();window.scrollTo?.(0,0);if(el.dataset.id!=='final'&&learning.run.id)learningRequest('lesson-open',{lessonId:el.dataset.id}).catch(()=>{});},
  'inline-start':async el=>{const data=await api(`me/assessments/${el.dataset.id}/start`,{});inlineAttempt={assessmentId:el.dataset.id,attempt:data.attempt};inlineResult=null;render();},
  'resource-delete':async el=>{await api(`manage/resources/${el.dataset.id}/delete`,{});await loadAdminState();render();},
  'assignment-delete':async el=>{await api(`manage/assignments/${el.dataset.id}/delete`,{});refreshData('assignments');render();},
};
const SUBMITS={
  'announcement-send':form=>submitForm(form,async()=>{await api('manage/announcements',formValues(form));await refreshNotifications();toast('Announcement published.');}),
  'dash-period':form=>{const v=formValues(form);devFilters.dashboard={from:v.from,to:v.to};render();},
  'report-filters':form=>{const v=formValues(form);devFilters.report={type:v.type||devFilters.report.type,department:v.department,employee:v.employee,course:v.course,from:v.from,to:v.to,page:1};render();},
  'path-save':form=>submitForm(form,async()=>{capturePathForm();const data=await api('manage/paths',{...pathEditor});pageCache['m-paths']={data};pathEditor=null;refreshData('me-paths');devMessage='Learning path saved.';render();}),
  'path-assign':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api(`manage/paths/${form.dataset.id}/assign`,{targetType:v.targetType,targetId:v.targetId,dueDate:v.dueDate||null});pageCache['m-paths']={data};pathAssign=null;devMessage='Learning path assigned. Employees have been notified.';render();}),
  'skill-save':form=>submitForm(form,async()=>{const data=await api('manage/skills',formValues(form));pageCache['m-skills']={data};refreshData('org');render();}),
  'evidence-save':form=>submitForm(form,async()=>{const v=formValues(form);await api('manage/skill-evidence',{...v,level:Number(v.level)});devMessage='Skill evidence recorded.';refreshData('m-skills');render();}),
  'goal-save':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('me/goals',{title:v.title,skillId:v.skillId||null,targetLevel:intOrNull(v.targetLevel),targetDate:v.targetDate||null});pageCache['me-skills']={data};refreshData('me-dash');render();}),
  'session-save':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('manage/sessions',{...v,id:form.dataset.id||null,capacity:Number(v.capacity),courseId:v.courseId||null,trainerId:v.trainerId||null});pageCache['m-sessions']={data};sessionEditor=null;refreshData('me-cal');devMessage='Session saved.';render();}),
  'assessment-submit':form=>submitForm(form,async()=>{const a=activeAssessment,answers=a.attempt.questions.map((_,i)=>{const value=new FormData(form).get('q'+i);return value===null?null:Number(value);});if(answers.includes(null))throw new Error('Answer every question before submitting.');const data=await api(`me/assessments/${a.id}/submit`,{attemptId:a.attempt.id,answers});activeAssessment=null;assessmentResult=data.result;refreshData('me-assess','me-skills','me-dash');refreshNotifications();if(data.result.status==='passed'){try{learning.certificates=(await api('certificates')).certificates;}catch{/* The list refreshes on the next page load. */}}render();}),
  'assessment-save':form=>submitForm(form,async()=>{const v=formValues(form);let questions;try{questions=JSON.parse(v.questions);}catch{throw new Error('The question bank JSON is invalid. Check its syntax.');}const data=await api('manage/assessments',{id:form.dataset.id||null,title:v.title,description:v.description,kind:v.kind,courseId:v.courseId||null,skillId:v.skillId||null,skillLevel:Number(v.skillLevel),passPercent:Number(v.passPercent),maxAttempts:Number(v.maxAttempts),questionCount:Number(v.questionCount),timeLimitMinutes:Number(v.timeLimitMinutes),status:v.status,questions});pageCache['m-assess']={data:{assessments:data.assessments}};assessmentEditor=null;refreshData('me-assess');devMessage='Assessment saved.';render();}),
  'record-save':form=>submitForm(form,async()=>{const v=formValues(form);await api('me/records',{title:v.title,provider:v.provider,completedOn:v.completedOn,hours:Number(v.hours||0)});refreshData('me-history');historyPage=1;render();}),
  'user-profile':form=>submitForm(form,async()=>{const v=formValues(form);await api(`admin/candidates/${form.dataset.id}/profile`,{name:v.name,role:v.role,departmentId:v.departmentId||null,jobRoleId:v.jobRoleId||null,managerId:v.managerId||null,jobTitle:v.jobTitle});editUserId=null;adminMessage='Employee profile updated.';await loadAdminState();refreshData('people','org');render();}),
  'org-save':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('manage/'+form.dataset.kind,{name:v.name,departmentId:v.departmentId||null});pageCache.org={data};render();}),
  'resource-save':form=>submitForm(form,async()=>{const v=formValues(form);let url=v.url;const file=form.querySelector('input[type="file"]')?.files?.[0];if(file){url=(await uploadMaterial(file)).url;}if(!url)throw new Error('Choose a file to upload or enter a link.');await api(`manage/courses/${form.dataset.id}/resources`,{title:v.title,kind:v.kind,url,moduleIndex:intOrNull(v.moduleIndex)});await loadAdminState();adminMessage='Learning material added.';render();}),
  'assignment-save':form=>submitForm(form,async()=>{const v=formValues(form);await api('manage/assignments',{courseId:form.dataset.id,targetType:v.targetType,targetId:v.targetId,mandatory:v.mandatory==='on',dueDate:v.dueDate||null,note:v.note});refreshData('assignments','me-dash');adminMessage='Course assigned. Employees have been notified.';render();}),
  'lesson-activity':form=>submitForm(form,async()=>{const lesson=currentCourseExtras.courseLessons.find(l=>l.id===form.dataset.lesson),answers=lesson.activity.tasks.map((_,i)=>(form.querySelector(`#answer-${i}`)?.value||'').trim());if(answers.some(a=>!a))throw new Error('Write a prompt for every task before submitting.');const result=await learningRequest('lesson-activity',{lessonId:lesson.id,answers});const r=result.activityResult;refreshData('me-dash','me-paths');toast(r.passed?`Passed with ${r.score}%. Review the feedback and model answers.`:`You scored ${r.score}%. You need ${r.passPercent}% — use the tips and try again.`);render();document.getElementById('activity-title')?.scrollIntoView?.({behavior:'smooth',block:'start'});}),
  'inline-assessment':form=>submitForm(form,async()=>{const id=form.dataset.id,questions=inlineAttempt.attempt.questions,values=new FormData(form),answers=questions.map((_,i)=>values.get('q'+i)===null?null:Number(values.get('q'+i)));if(answers.includes(null))throw new Error('Answer every question before submitting.');const data=await api(`me/assessments/${id}/submit`,{attemptId:inlineAttempt.attempt.id,answers});inlineResult={assessmentId:id,result:data.result};inlineAttempt=null;await refreshCourseExtras();refreshData('me-assess','me-dash');refreshNotifications();toast(data.result.status==='passed'?`Passed with ${data.result.percent}%.`:data.result.status==='expired'?'Time expired.':`You scored ${data.result.percent}%. Review the explanations and try again.`);render();}),
  'lesson-complete':form=>submitForm(form,async()=>{const v=formValues(form),list=currentCourseExtras.courseLessons,i=list.findIndex(l=>l.id===form.dataset.lesson);await learningRequest('lesson',{lessonId:form.dataset.lesson,response:v.response||''});selectedLessonId=list[i+1]?.id||form.dataset.lesson;refreshData('me-dash','me-paths');toast(list[i+1]?'Lesson completed. On to the next one.':'Lesson completed.');render();}),
  assistant:form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('me/assistant',{courseId:currentCourseInfo.id,mode:v.mode,lessonIndex:intOrNull(v.lessonIndex),question:v.question});assistantAnswer={courseId:currentCourseInfo.id,text:data.answer+(data.truncated?'\n\n(The answer was cut short.)':'')};render();}),
};
const CHANGES={
  'target-type':el=>{const target=document.getElementById(el.dataset.target);if(target)target.innerHTML=options(targetChoices(el.value),'','Select…');},
  'competency-role':el=>{competencyRole=el.value;render();},
  'competency-level':async el=>{try{const data=await api('manage/competencies',{jobRoleId:el.dataset.role,skillId:el.dataset.skill,targetLevel:Number(el.value)});pageCache['m-skills']={data};toast('Role competency updated.');}catch(error){toast(error.message);render();}},
  attendance:async el=>{try{const data=await api(`manage/sessions/${el.dataset.session}/attendance`,{employeeId:el.dataset.employee,attended:el.checked});pageCache['roster:'+el.dataset.session]={data};render();}catch(error){toast(error.message);el.checked=!el.checked;}},
};
async function uploadMaterial(file){
  if(file.size>50*1024*1024)throw new Error('Files must be 50 MB or smaller.');
  let response;
  try{response=await fetch('/api/manage/materials',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream','X-Portal-Request':'1','X-CSRF-Token':csrfToken,'X-File-Name':encodeURIComponent(file.name)},body:file});}
  catch{throw new Error('Could not upload the file. Check your connection and try again.');}
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.error||'The file could not be uploaded.');
  return data.material;
}
document.addEventListener('click',event=>{
  const el=event.target.closest?.('[data-act]');if(!el||!ACTIONS[el.dataset.act]||el.disabled)return;
  if(el.tagName!=='A')event.preventDefault();
  if(el.dataset.act!=='notification-open')devMessage='';
  Promise.resolve(ACTIONS[el.dataset.act](el,event)).catch(error=>toast(error.message));
});
document.addEventListener('submit',event=>{const form=event.target.closest?.('[data-form]');if(!form||!SUBMITS[form.dataset.form])return;event.preventDefault();devMessage='';SUBMITS[form.dataset.form](form);});
document.addEventListener('change',event=>{const el=event.target.closest?.('[data-change]');if(el&&CHANGES[el.dataset.change])CHANGES[el.dataset.change](el);});
setInterval(updateAssessmentTimer,1000);
