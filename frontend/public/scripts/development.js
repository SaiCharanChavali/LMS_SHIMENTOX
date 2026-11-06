// Employee learning & development pages. Every figure is loaded from the authenticated API; nothing here is sample data.
// The backend enforces all permissions; PERMS below only decides which controls to show.
const ROLE_LABELS={admin:'Administrator',hr:'HR / L&D Admin',trainer:'Trainer',manager:'Manager',employee:'Employee'};
const LEVEL_LABELS=['Not assessed','Beginner','Intermediate','Advanced','Expert'];
const PERMS={'users.manage':['admin','hr'],'org.manage':['admin','hr'],'courses.manage':['admin','hr','trainer'],'courses.assign':['admin','hr','manager'],'paths.manage':['admin','hr','trainer'],'skills.manage':['admin','hr'],'competencies.manage':['admin','hr','manager'],'skills.record':['admin','hr','manager'],'assessments.manage':['admin','hr','trainer'],'sessions.manage':['admin','hr','trainer'],'reports.view':['admin','hr','manager','trainer'],'audit.view':['admin']};
const KIND_LABELS={pre:'Pre-training',post:'Post-training',knowledge:'Knowledge check',skill:'Skill assessment'};
const STATUS_TAGS={completed:['Completed','success'],overdue:['Overdue','danger'],in_progress:['In progress',''],not_started:['Not started','gray'],locked:['Locked','gray'],unavailable:['Unavailable','gray']};
const DEADLINE_TONES={not_started:'gray',in_progress:'',due_soon:'due-soon',overdue:'danger',completed_on_time:'success',completed_late:'success'};
const DEADLINE_LABELS={not_started:'Not Started',in_progress:'In Progress',due_soon:'Due Soon',overdue:'Overdue'};
const REMINDER_TYPES={assigned:'Course assigned',deadline_changed:'Deadline changed',deadline_day:'Deadline day',overdue:'Overdue'};
let deadlineCourseId='',reminderPanelOpen=false;
const can=permission=>Boolean(currentUser&&PERMS[permission]?.includes(currentUser.role));
const isLearner=()=>Boolean(currentUser);
let pageCache={},devMessage='',devFilters={dashboard:{},report:{type:'enrollments',page:1}},notificationState={items:[],unread:0,open:false};
let sessionEditor=null,sessionRoster=null,assessmentEditor=null,assessmentAttemptsId=null,activeAssessment=null,assessmentResult=null,editUserId=null,previewCourseId=null,historyPage=1,courseFilter='all',courseArea='all',courseSearch='',assistantAnswer=null;

function resetDevelopment(){selectedLessonId=null;inlineAttempt=null;inlineResult=null;if(typeof courseDraft!=='undefined'){courseDraft=null;builderStep=1;}pageCache={};devMessage='';devFilters={dashboard:{},report:{type:'enrollments',page:1}};notificationState={items:[],unread:0,open:false};sessionEditor=sessionRoster=assessmentEditor=assessmentAttemptsId=activeAssessment=assessmentResult=editUserId=previewCourseId=assistantAnswer=null;deadlineCourseId='';reminderPanelOpen=false;compliance=COMPLIANCE_DEFAULTS();complianceOptions=null;historyPage=1;courseFilter='all';courseArea='all';courseSearch='';}
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
    :'<div class="notice" role="alert"><strong>The portal browser and server versions do not match.</strong><p>Some features will fail until an administrator stops the older server process currently using this address and restarts the updated portal.</p></div>';
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
// Yearly training hours against the target an admin or manager set: a bar with the hours completed.
function trainingBar(t){
  if(!t)return '';
  if(!t.targetHours)return `<div class="training-target"><small>${t.completedHours} hours completed in ${t.year} · No yearly target set</small></div>`;
  const left=Math.max(0,Math.round((t.targetHours-t.completedHours)*10)/10);
  return `<div class="training-target"><div class="meter-row"><div class="meter" role="img" aria-label="${t.completedHours} of ${t.targetHours} training hours completed in ${t.year}"><span style="width:${t.percent}%"></span></div><b>${t.percent}%</b></div><small>${t.completedHours} of ${t.targetHours} hours in ${t.year}${t.percent>=100?' · Target met':` · ${left} hours to go`}</small></div>`;
}
// One form for every place a target is set. "target" is all, dept:<id>, user:<id> or ids:<id,id,...>.
function trainingTargetForm(target,current,options=''){
  return `<form class="training-target-form" data-form="training-target">${options||`<input type="hidden" name="target" value="${esc(target)}">`}<label class="visually-hidden" for="tt-${esc(target)}">Yearly target in hours</label><input id="tt-${esc(target)}" name="hours" type="number" min="1" max="2000" step="1" value="${esc(current??'')}" placeholder="Hours / year" aria-label="Yearly training target in hours"><button class="btn secondary" type="submit">Save target</button><p class="form-status" role="status"></p></form>`;
}
function trainingTargetIds(target){
  const employees=(adminState.candidates||[]).filter(u=>u.active&&u.role!=='admin');
  if(target==='all')return employees.map(u=>u.id);
  if(target.startsWith('dept:'))return employees.filter(u=>u.departmentId===target.slice(5)).map(u=>u.id);
  if(target.startsWith('user:'))return [target.slice(5)];
  if(target.startsWith('ids:'))return target.slice(4).split(',').filter(Boolean);
  return [];
}
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

// ---------------------------------------------------------------- course deadlines

function formatSpan(seconds){
  const s=Math.max(0,Math.floor(seconds)),unit=(n,name)=>n?`${n} ${name}${n===1?'':'s'}`:'';
  const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);
  const parts=d?[unit(d,'day'),unit(h,'hour')]:h?[unit(h,'hour'),unit(m,'minute')]:m?[unit(m,'minute'),unit(s%60,'second')]:[unit(s,'second')||'0 seconds'];
  return parts.filter(Boolean).join(', ');
}
// Status and time left for an open course. The server is the record; this only keeps the page current between loads.
function deadlineState(at,dueSoonSeconds,started,nowMs=Date.now()+serverClockOffset){
  const left=(Date.parse(at)-nowMs)/1000,status=left<=0?'overdue':left<=dueSoonSeconds?'due_soon':started?'in_progress':'not_started';
  return {status,label:DEADLINE_LABELS[status],clock:left<=0?`Overdue by ${formatSpan(-left)}`:`Time remaining: ${formatSpan(left)}`};
}
function deadlineBlock(d){
  if(!d)return '';
  const live=d.completedAt?null:deadlineState(d.at,d.dueSoonSeconds,d.started),status=live?live.status:d.status,tone=DEADLINE_TONES[status];
  const attrs=live?`data-deadline-at="${esc(d.at)}" data-deadline-soon="${Number(d.dueSoonSeconds)}" data-deadline-started="${d.started?1:0}"`:'';
  return `<div class="deadline-box ${tone}" ${attrs}><span class="tag ${tone}" data-deadline-tag>${esc((live?live.label:d.label).toUpperCase())}</span><div class="deadline-line"><b>Deadline:</b> ${esc(d.display)} ${esc(d.timezone)}</div><div class="deadline-clock" role="timer" data-deadline-clock>${esc(live?live.clock:'Completed '+(d.completedDisplay||''))}</div></div>`;
}
function updateDeadlineClocks(){
  document.querySelectorAll('[data-deadline-at]').forEach(box=>{
    const live=deadlineState(box.dataset.deadlineAt,Number(box.dataset.deadlineSoon),box.dataset.deadlineStarted==='1'),tone=DEADLINE_TONES[live.status];
    box.className=`deadline-box ${tone}`;
    const tag=box.querySelector('[data-deadline-tag]');tag.className=`tag ${tone}`;tag.textContent=live.label.toUpperCase();
    box.querySelector('[data-deadline-clock]').textContent=live.clock;
  });
}
setInterval(updateDeadlineClocks,1000);

// ---------------------------------------------------------------- notifications

// Keeps the bell's count current. Only the badge is updated, so a page being read or a form being filled in is left alone.
async function pollNotifications(){
  if(!currentUser||currentUser.mustChangePassword||document.hidden)return;
  try{
    const {unread}=await api('me/notifications/unread');
    if(unread===notificationState.unread)return;
    notificationState.unread=unread;
    const bell=document.getElementById('notifications');if(!bell)return;
    bell.querySelector('.notification-count')?.remove();
    bell.setAttribute('aria-label',`Notifications${unread?`, ${unread} unread`:''}`);
    if(unread)bell.insertAdjacentHTML('beforeend',`<span class="notification-count">${unread>99?'99+':unread}</span>`);
  }catch{/* The next poll tries again. */}
}
setInterval(pollNotifications,60000);
async function refreshNotifications(){
  if(!currentUser||currentUser.mustChangePassword)return;
  try{const data=await api('me/notifications');notificationState.items=data.notifications;notificationState.unread=data.unread;render();}catch{/* Notifications are optional; the page keeps working. */}
}
function notificationPanel(){
  if(!notificationState.open)return '';
  const deadlineOnly=notificationState.filter==='deadline',unreadDeadlines=notificationState.items.filter(n=>n.kind==='deadline'&&!n.readAt);
  const items=deadlineOnly?unreadDeadlines:notificationState.items;
  const tabs=`<div class="notification-tabs"><button class="${deadlineOnly?'':'active'}" data-act="notification-filter" data-value="all" aria-pressed="${!deadlineOnly}">All</button><button class="${deadlineOnly?'active':''}" data-act="notification-filter" data-value="deadline" aria-pressed="${deadlineOnly}">Unread deadlines (${unreadDeadlines.length})</button></div>`;
  const composer=['admin','hr'].includes(currentUser.role)?`<details class="announcement-composer"><summary>Post an announcement</summary><form data-form="announcement-send"><label for="announcement-title">Title</label><input id="announcement-title" name="title" minlength="2" maxlength="200" required><label for="announcement-body">Message</label><textarea id="announcement-body" name="body" minlength="2" maxlength="500" rows="3" required></textarea><button class="btn" type="submit">Publish to everyone</button><p class="form-status" role="status"></p></form></details>`:'';
  return `<div class="notification-panel" role="dialog" aria-label="Notifications"><div class="section-heading"><h3>Notifications</h3>${notificationState.unread?'<button class="auth-link" data-act="notifications-read-all">Mark all read</button>':''}</div>${tabs}${composer}${items.length?items.map(n=>`<button class="notification ${n.readAt?'':'unread'}" data-act="notification-open" data-id="${n.id}" data-link="${esc(n.link)}"><small class="notification-kind">${esc(n.kind)}</small><strong>${esc(n.title)}</strong><span>${esc(n.body)}</span><small>${esc(fmtDateTime(n.createdAt))}</small></button>`).join(''):`<p class="muted">${deadlineOnly?'No unread deadline reminders.':'You are all caught up. Assignments, deadlines, results and certificates will appear here.'}</p>`}</div>`;
}

// ---------------------------------------------------------------- organisation dashboard (admin, HR, team scope)

function quickActions(){
  return [can('courses.manage')&&`<a class="btn" href="#admin-courses">Create course ${icon('arrow')}</a>`,can('users.manage')&&'<a class="btn secondary" href="#admin-users">Add employee</a>',['admin','hr'].includes(currentUser.role)&&'<a class="btn secondary" href="#compliance">Training compliance</a>',can('reports.view')&&'<a class="btn secondary" href="#reports">View analytics</a>'].filter(Boolean).join('');
}
function orgDashboard(){
  const filters=devFilters.dashboard,key=`dash:${filters.from||''}:${filters.to||''}`,entry=loadData(key,'manage/dashboard'+qs(filters));
  const head=`<div class="intro"><div><h1>Your people. Their potential.</h1><p>Welcome, ${esc(state.name)}. Employee learning and development across ShimentoX.</p></div><span class="tag">${currentUser.role==='admin'?'ADMINISTRATOR WORKSPACE':'L&D WORKSPACE'}</span></div><div class="admin-actions quick-actions">${quickActions()}</div>`;
  if(!entry.data)return head+stateBlock(entry,'learning metrics',key);
  const d=entry.data,k=d.kpis;
  return head+`<div class="stats">${kpi('users',k.totalEmployees,'Total employees')}${kpi('play',k.activeLearners,'Active learners','Learning activity in the last 30 days')}${kpi('book',k.publishedCourses,'Published courses')}${kpi('check',k.completionRate+'%','Course completion rate',`${k.completions} of ${k.enrollments} enrollments`)}</div>
  <div class="stats">${kpi('award',k.certificatesEarned,'Certificates earned')}${kpi('clock',k.trainingHours,'Training hours completed','Completed lessons, verified video time and attended sessions')}${kpi('bell',k.pendingMandatory,'Pending mandatory training')}</div>
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
  return `<article class="recommendation"><div class="tile-tags"><span class="tag">${esc(r.category)}</span><span class="tag gray">${esc(capital(r.difficulty).toUpperCase())}</span></div><h3>${esc(r.title)}</h3><p class="muted">${esc(r.description)}</p><p class="muted">${esc(fmtDuration(r.durationMinutes))}</p><ul class="reasons">${r.reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><button class="btn secondary" data-open-course="${esc(r.id)}">View course ${icon('arrow')}</button></article>`;
}
function employeeDashboard(){
  const first=esc(state.name.split(' ')[0]),entry=loadData('me-dash','me/dashboard');
  const head=`<div class="intro"><div><h1>Welcome back, ${first}</h1><p>A little progress every day adds up to something great.</p></div><span class="tag">${esc((ROLE_LABELS[currentUser.role]||'Employee').toUpperCase())} WORKSPACE</span></div>`;
  if(!entry.data)return head+stateBlock(entry,'your learning',`me-dash`);
  const d=entry.data,p=d.profile;
  const profile=`<p class="profile-line">${esc([p.job_title||p.job_role,p.department,p.manager&&'Manager: '+p.manager].filter(Boolean).join(' · ')||'Ask HR to add your department and job role to receive role-based training.')}</p>`;
  return head+profile+`<div class="stats">${kpi('book',d.stats.assigned,'Assigned courses',d.stats.overdue?`${d.stats.overdue} overdue`:'')}${kpi('play',d.stats.inProgress,'Courses in progress')}${kpi('award',d.stats.certificates,'Certificates earned')}</div>
  <div class="dash-grid"><div class="dash-main">
  ${d.training?panel(`Training hours ${d.training.year}`,`${trainingBar(d.training)}<p class="muted">Completed lessons, video learning and attended training sessions count toward your yearly target, which your manager or administrator sets.</p>`):''}
  ${panel('Assigned to me',d.assigned.length?`<div class="tile-grid">${d.assigned.map(courseTile).join('')}</div>`:emptyState('No assigned training','Courses assigned by HR or your manager will appear here with their deadlines.','<a class="btn secondary" href="#catalog">Browse all courses</a>'),'<a href="#courses">My Learning &rarr;</a>')}
  ${d.continue.filter(c=>!c.assignment).length?panel('Continue learning',`<div class="tile-grid">${d.continue.filter(c=>!c.assignment).map(courseTile).join('')}</div>`):''}
  ${panel('Recommended for you',d.recommendations.length?`<div class="tile-grid">${d.recommendations.map(recommendationCard).join('')}</div>`:emptyState('No recommendations yet','Recommendations use your job role and assessment results.'))}
  </div><div class="dash-side">
  ${panel('Pending assessments',d.pendingAssessments.length?d.pendingAssessments.map(a=>`<div class="admin-list-row"><div><strong>${esc(a.title)}</strong><small>${esc(a.reason)} · ${a.attemptsLeft} attempt${a.attemptsLeft===1?'':'s'} left</small></div><a class="tag" href="#assessments">START</a></div>`).join(''):'<p class="muted">Nothing pending right now.</p>')}
  ${panel('Upcoming training',d.sessions.length?d.sessions.map(s=>`<div class="admin-list-row"><div><strong>${esc(s.title)}</strong><small>${esc(fmtDateTime(s.startsAt))} · ${s.seatsLeft} seats left</small></div>${s.myStatus==='registered'?'<span class="tag success">REGISTERED</span>':''}</div>`).join(''):'<p class="muted">No upcoming sessions.</p>','<a href="#calendar">Calendar &rarr;</a>')}
  ${panel('Learning history',d.history.length?d.history.map(h=>`<div class="activity"><span class="bubble">${icon('check')}</span><p>${esc(h.text)}<br><small>${esc(fmtDate(h.at))}</small></p></div>`).join(''):'<p class="muted">Your completed activities will appear here.</p>','<a href="#history">All history &rarr;</a>')}
  </div></div>`;
}
function teamTrainingPanel(rows){
  const year=rows[0]?.year||new Date().getFullYear();
  const table=rows.length?`<div class="admin-table-scroll"><table class="admin-table" aria-label="Team training hours"><thead><tr><th>Employee</th><th>Training hours ${year}</th><th>Yearly target</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.name)}</strong><small>${esc(r.department||'No department')}</small></td><td>${trainingBar(r)}</td><td>${trainingTargetForm('user:'+r.id,r.targetHours)}</td></tr>`).join('')}</tbody></table></div><h3 class="sub-heading">Set the same target for the whole team</h3>${trainingTargetForm('ids:'+rows.map(r=>r.id).join(','),'')}`:'<p class="muted">Employees who report to you will appear here.</p>';
  return panel(`Team training hours ${year}`,`<p class="muted">Set how many hours of training each employee should complete this year. Leave the field blank and save to remove a target.</p>${table}`);
}
// Manager View: learning progress of the manager's direct reports; the server scopes the dashboard data to them.
function managerView(){
  const entry=loadData('mgr-dash','manage/dashboard');
  const head=`<div class="intro"><div><h1>Manager View</h1><p>How your team is learning: progress, overdue training and recent activity for your direct reports.</p></div><span class="tag">MANAGER WORKSPACE</span></div><div class="admin-actions quick-actions"><a class="btn" href="#reports">Team reports ${icon('arrow')}</a><a class="btn secondary" href="#compliance">Team compliance</a><a class="btn secondary" href="#courses">My Learning</a></div>`;
  if(!entry.data)return head+stateBlock(entry,'team progress','mgr-dash');
  const k=entry.data.kpis;
  return head+`<div class="stats">${kpi('users',k.totalEmployees,'Direct reports')}${kpi('play',k.activeLearners,'Active learners','Learning activity in the last 30 days')}${kpi('check',k.completionRate+'%','Course completion rate',`${k.completions} of ${k.enrollments} enrollments`)}${kpi('bell',k.pendingMandatory,'Pending mandatory training')}</div>
  <div class="dash-grid"><div class="dash-main">${teamTrainingPanel(entry.data.training||[])}${progressPanel(entry.data.progress)}</div><div class="dash-side">${activityPanel(entry.data.recent)}</div></div>`;
}

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
  return panel('Available to me',items.length?`<div class="exam-rules"><h3>Exam rules</h3><ul>${EXAM_RULE_ITEMS}</ul></div><div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Assessment</th><th>Type</th><th>Rules</th><th>My result</th><th></th></tr></thead><tbody>${items.map(a=>`<tr><td><strong>${esc(a.title)}</strong><small>${esc(a.course||a.skill||'')}</small></td><td>${esc(KIND_LABELS[a.kind])}</td><td>${a.questionCount} questions · ${a.timeLimitMinutes} min<small>Pass ${a.passPercent}% · ${a.maxAttempts} attempt${a.maxAttempts===1?'':'s'}</small></td><td>${a.passed?'<span class="tag success">PASSED</span>':a.attempts.length?'<span class="tag warn">NOT PASSED</span>':'<span class="tag gray">NOT TAKEN</span>'}<small>${a.best!=null?'Best '+a.best+'% · ':''}${a.attempts.length} attempt${a.attempts.length===1?'':'s'} used</small></td><td>${a.attemptsLeft&&!(a.kind==='skill'&&a.passed)?`<button class="btn secondary" data-act="assessment-start" data-id="${a.id}">${a.attempts.length?'Retake':'Start'}</button>`:''}</td></tr>`).join('')}</tbody></table></div>`:emptyState('No assessments yet','Published assessments for your courses and skills will appear here.'));
}
function assessmentRunner(){
  const a=activeAssessment;
  return `<div class="exam-focus"><div class="exam-top"><div><span class="tag">ASSESSMENT · ATTEMPT ${a.attempt.attemptNumber}</span><h1>${esc(a.title)}</h1></div><div class="exam-timer" role="timer" id="assessment-timer">--:--</div></div><div class="notice">${EXAM_ACTIVE_NOTICE}</div><form class="panel" data-form="assessment-submit">${a.attempt.questions.map((q,i)=>`<fieldset class="question"><legend><span>${i+1}.</span> ${esc(q.prompt)}</legend>${q.options.map((o,j)=>`<label class="answer"><input type="radio" name="q${i}" value="${j}" required><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}<button class="btn" type="submit">Submit assessment ${icon('check')}</button> <button class="btn secondary" type="button" data-act="assessment-end">End attempt</button><p class="form-status" role="status"></p></form></div>`;
}
function updateAssessmentTimer(){
  const current=activeAssessment||inlineAttempt;
  if(!current)return;
  const timer=document.getElementById('assessment-timer');const seconds=Math.max(0,Math.ceil((current.attempt.deadline-Date.now())/1000));
  if(timer)timer.textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
  if(seconds)return;
  const inline=!activeAssessment,result={status:'expired',details:[]};
  activeAssessment=null;inlineAttempt=null;exitExamFullscreen();
  if(inline){inlineResult={assessmentId:current.assessmentId,result};refreshCourseExtras().catch(()=>{}).finally(render);}else{assessmentResult=result;refreshData('me-assess');}
  render();
}
function resultPanel(){
  const r=assessmentResult;
  if(r.status==='expired')return '<div class="notice" role="status">Time expired. The attempt ended without a score and counts toward your attempt limit.</div>';
  if(r.status==='terminated')return `<div class="notice" role="status">${esc(r.reason||'The attempt was ended.')} It ended without a score and counts toward your attempt limit.</div>`;
  return `<section class="panel"><div class="section-heading"><h2>${r.status==='passed'?'Assessment passed':'Assessment not passed'}</h2><button class="auth-link" data-act="assessment-result-close">Dismiss</button></div><p><b>${r.score}/${r.total} correct (${r.percent}%)</b> · Pass mark ${r.passPercent}%</p><ol class="result-list">${r.details.map(d=>`<li class="${d.correct?'correct':'incorrect'}">${d.correct?'Correct.':`Incorrect. Correct answer: ${esc(d.answer||'')}.`} ${esc(d.explanation||'')}</li>`).join('')}</ol></section>`;
}
const QUESTION_TEMPLATE='[\n  ["Question text", ["Option A", "Option B", "Option C"], 0, "Why the correct option is right"]\n]';
function manageAssessments(){
  const entry=loadData('m-assess','manage/assessments'),org=orgData();
  if(!entry.data)return stateBlock(entry,'question banks','m-assess');
  const list=entry.data.assessments,courseNames=Object.fromEntries(org.courses.map(c=>[c.id,c.title])),skillNames=Object.fromEntries(org.skills.map(s=>[s.id,s.name]));
  const table=`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Assessment</th><th>Type</th><th>Question bank</th><th>Rules</th><th>Results</th><th>Actions</th></tr></thead><tbody>${list.map(a=>`<tr><td><strong>${esc(a.title)}</strong><small>${esc(courseNames[a.courseId]||skillNames[a.skillId]||'')} · ${esc(a.status)}</small></td><td>${esc(KIND_LABELS[a.kind])}</td><td>${a.questions.length} in bank<small>${a.questionCount} drawn at random</small></td><td>Pass ${a.passPercent}%<small>${a.maxAttempts} attempts · ${a.timeLimitMinutes} min</small></td><td>${a.attempts} attempts<small>${a.passRate==null?'No results yet':`${a.passRate}% pass rate · avg ${a.averageScore}%`}</small></td><td><div class="table-actions"><button data-act="assessment-edit" data-id="${a.id}">Edit</button><button data-act="assessment-attempts" data-id="${a.id}">Attempts</button></div></td></tr>`).join('')||'<tr><td colspan="6" class="muted">No assessments yet.</td></tr>'}</tbody></table></div>`;
  const a=assessmentEditor;
  const form=a?`<section class="panel admin-form"><span class="tag">${a.id?'EDIT ASSESSMENT':'NEW ASSESSMENT'}</span><h2>${a.id?'Edit assessment':'Create an assessment'}</h2>${a.locked?'<div class="notice">Employees have attempted this assessment. Rules, status and title can change; the question bank and type are locked to preserve attempt history.</div>':''}<form data-form="assessment-save" data-id="${esc(a.id||'')}"><label for="assessment-title">Title</label><input id="assessment-title" name="title" value="${esc(a.title||'')}" minlength="2" maxlength="150" required><label for="assessment-description">Description</label><textarea id="assessment-description" name="description" rows="2" maxlength="2000">${esc(a.description||'')}</textarea><div class="editor-fields"><div><label for="assessment-kind">Type</label><select id="assessment-kind" name="kind">${options(Object.entries(KIND_LABELS).filter(([kind])=>kind!=='skill'||a.kind==='skill'),a.kind||'knowledge')}</select></div><div><label for="assessment-course">Course (required for pre/post)</label><select id="assessment-course" name="courseId">${options(org.courses.map(c=>[c.id,c.title]),a.courseId,'None')}</select></div><div><label for="assessment-status">Status</label><select id="assessment-status" name="status">${options([['draft','Draft'],['published','Published'],['archived','Archived']],a.status||'draft')}</select></div></div><div class="editor-fields">${a.kind==='skill'?`<input type="hidden" name="skillId" value="${esc(a.skillId||'')}"><input type="hidden" name="skillLevel" value="${esc(a.skillLevel||2)}">`:''}<div><label for="assessment-pass">Passing score %</label><input id="assessment-pass" name="passPercent" type="number" min="1" max="100" value="${esc(a.passPercent||70)}" required></div></div><div class="editor-fields"><div><label for="assessment-attempts">Attempts allowed</label><input id="assessment-attempts" name="maxAttempts" type="number" min="1" max="3" value="${esc(a.maxAttempts||3)}" required></div><div><label for="assessment-count">Questions per attempt</label><input id="assessment-count" name="questionCount" type="number" min="1" max="100" value="${esc(a.questionCount||5)}" required></div><div><label for="assessment-time">Time limit (minutes)</label><input id="assessment-time" name="timeLimitMinutes" type="number" min="1" max="240" value="${esc(a.timeLimitMinutes||15)}" required></div></div><label for="assessment-questions">Question bank (JSON)</label><p class="muted">Each question is [prompt, options, correct option index starting at 0, explanation]. Each attempt draws the configured number of questions at random. Answer keys never reach employees.</p><textarea id="assessment-questions" name="questions" class="curriculum-json" rows="12" spellcheck="false" ${a.locked?'readonly':''} required>${esc(a.questions?JSON.stringify(a.questions,null,2):QUESTION_TEMPLATE)}</textarea><div class="admin-actions"><button class="btn" type="submit">Save assessment</button><button class="btn secondary" type="button" data-act="assessment-editor-close">Cancel</button></div><p class="form-status" role="status"></p></form><p class="muted">To require a post-training assessment for a certificate, select it in the course's completion requirements under Manage Courses.</p></section>`:'';
  return panel('Question banks',table,'<button class="btn" data-act="assessment-new">New assessment</button>')+form+(assessmentAttemptsId?attemptsPanel():'');
}
function attemptsPanel(){
  const key='attempts:'+assessmentAttemptsId,entry=loadData(key,`manage/assessments/${assessmentAttemptsId}/attempts`);
  if(!entry.data)return stateBlock(entry,'attempt history',key);
  const d=entry.data;
  return panel(`Attempt history: ${d.assessment.title}`,`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Department</th><th>Attempt</th><th>Score</th><th>Result</th><th>Date</th></tr></thead><tbody>${d.items.map(t=>`<tr><td>${esc(t.employee)}</td><td>${esc(t.department||'—')}</td><td>${t.attempt_number}</td><td>${t.percent==null?'—':`${t.score}/${t.total} (${t.percent}%)`}</td><td>${esc(capital(t.status))}</td><td>${esc(fmtDateTime(t.finished_at||t.started_at))}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No attempts yet.</td></tr>'}</tbody></table></div><p class="muted">${d.total} attempts · page ${d.page} of ${d.pages}</p>`,'<button class="btn secondary" data-act="assessment-attempts-close">Close</button>');
}

// ---------------------------------------------------------------- reports & analytics

const REPORT_TYPES=[['enrollments','Course enrollment & completion'],['employees','Employee learning progress'],['departments','Department training statistics'],['assessments','Assessment performance'],['compliance','Mandatory training compliance'],['certificates','Certificate records']];
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

// ---------------------------------------------------------------- training compliance & deadline monitoring

const COMPLIANCE_DEFAULTS=()=>({filters:{},pages:{page:1,overduePage:1},sort:{},size:10,tab:'overview',open:null});
let compliance=COMPLIANCE_DEFAULTS(),complianceOptions=null;
const COMPLIANCE_TABS=[['overview','Overview'],['employees','Employee Progress'],['departments','Department Compliance'],['overdue','Overdue Training'],['reports','Reports']];
const COMPLIANCE_STATUSES=[['completed','Completed'],['completed_on_time','Completed on time'],['completed_late','Completed late'],['in_progress','In progress'],['not_started','Not started'],['overdue','Overdue']];
// Chart colours are status colours in this fixed order, so neighbouring segments stay distinct for colour-blind readers.
const COMPLIANCE_SERIES=[['completedOnTime','Completed On Time','on-time'],['inProgress','In Progress','progress'],['completedLate','Completed Late','late'],['overdue','Overdue','overdue'],['notStarted','Not Started','waiting']];
const compliancePill=(text,tone='')=>`<span class="tag compliance-pill ${tone}">${esc(text)}</span>`;
const complianceStatus=r=>compliancePill(r.statusLabel,r.status==='completed_late'?'warn':DEADLINE_TONES[r.status])+(r.dueSoon?compliancePill('Due Soon','due-soon'):'');
const complianceType=mandatory=>mandatory?compliancePill('Mandatory','warn'):compliancePill('Optional','gray');
const complianceInitials=name=>esc(name.split(/\s+/).filter(Boolean).slice(0,2).map(part=>part[0]).join('').toUpperCase());
const complianceShortId=id=>`<span title="${esc(id)}">${esc(id.length>8?id.slice(0,8)+'…':id)}</span>`;
const complianceDate=(day,full,blank='—')=>day?`<span title="${esc(full||'')}">${esc(fmtDate(day))}</span>`:esc(blank);
const compliancePager=(t,field)=>t.pages>1?`<span class="table-actions"><button data-act="compliance-page" data-field="${field}" data-page="${t.page-1}" ${t.page<=1?'disabled':''}>Previous</button><button data-act="compliance-page" data-field="${field}" data-page="${t.page+1}" ${t.page>=t.pages?'disabled':''}>Next</button></span>`:'';
const complianceExportMenu=(label,primary)=>`<details class="export-menu"><summary class="btn ${primary?'':'secondary'}">${icon('download')} ${esc(label)}</summary><div class="export-options"><button data-act="compliance-export" data-format="csv">Export CSV</button><button data-act="compliance-export" data-format="xlsx">Export Excel</button></div></details>`;

function complianceChips(){
  const f=compliance.filters,o=complianceOptions||{},find=(list,value)=>(list||[]).find(([id])=>id===value)?.[1]||value;
  const chips=[f.q&&['q','Search',f.q],f.employee&&['employee','Employee',find(o.employees,f.employee)],f.department&&['department','Department',find(o.departments,f.department)],f.jobRole&&['jobRole','Job role',find(o.jobRoles,f.jobRole)],f.course&&['course','Course',find(o.courses,f.course)],f.type&&['type','Type',capital(f.type)],f.status&&['status','Status',find(COMPLIANCE_STATUSES,f.status)],f.from&&['from','Deadline from',fmtDate(f.from)],f.to&&['to','Deadline to',fmtDate(f.to)]].filter(Boolean);
  return chips.length?`<div class="filter-chips" aria-label="Active filters">${chips.map(([field,label,value])=>`<button type="button" class="filter-chip" data-act="compliance-clear" data-field="${field}" aria-label="Remove filter ${esc(label)}: ${esc(value)}">${esc(label)}: <b>${esc(value)}</b> <span aria-hidden="true">×</span></button>`).join('')}</div>`:'';
}
function complianceFilterForm(){
  const f=compliance.filters,o=complianceOptions||{employees:[],departments:[],courses:[],jobRoles:[]};
  const select=(name,label,items,blank)=>`<div><label for="compliance-${name}">${label}</label><select id="compliance-${name}" name="${name}">${options(items,f[name],blank)}</select></div>`;
  return `<form class="compliance-filters panel" data-form="compliance-filters"><div class="filters-head"><h2>${icon('filter')} Filters</h2><div class="filter-actions"><button class="btn secondary" type="button" data-act="compliance-reset">Reset</button><button class="btn" type="submit">Apply Filters</button></div></div><div class="filters-grid"><div class="filter-search"><label for="compliance-q">Search Employee</label><input id="compliance-q" name="q" type="search" maxlength="100" list="compliance-people" placeholder="Name, email or ID" value="${esc(f.q||'')}"><datalist id="compliance-people">${[...new Set(o.employees.map(([,name])=>name))].map(name=>`<option value="${esc(name)}"></option>`).join('')}</datalist></div>${select('department','Department',o.departments,'All departments')}${select('jobRole','Job Role',o.jobRoles,'All job roles')}${select('course','Course',o.courses,'All courses')}${select('type','Mandatory / Optional',[['mandatory','Mandatory'],['optional','Optional']],'All types')}${select('status','Training Status',COMPLIANCE_STATUSES,'All statuses')}<div class="filter-range"><span class="field-label" id="compliance-range">Deadline Range</span><div role="group" aria-labelledby="compliance-range"><input type="date" name="from" aria-label="Deadline from" value="${esc(f.from||'')}"><span aria-hidden="true">–</span><input type="date" name="to" aria-label="Deadline to" value="${esc(f.to||'')}"></div></div></div>${f.employee?`<input type="hidden" name="employee" value="${esc(f.employee)}">`:''}${complianceChips()}</form>`;
}
function complianceKpis(s){
  const card=(name,value,label,tone='',extra='')=>`<div class="stat compliance-kpi ${tone}"><div class="stat-icon">${icon(name)}</div><div class="kpi-body"><strong>${esc(value)}</strong><small>${esc(label)}</small>${extra}</div></div>`;
  return `<div class="compliance-kpis">${card('book',s.total,'Total Assignments')}${card('check',s.completed,'Completed')}${card('play',s.inProgress,'In Progress')}${card('bell',s.overdue,'Overdue',s.overdue?'alert':'')}${card('calendar',s.completedOnTime,'Completed On Time')}${card('clock',s.completedLate,'Completed Late')}${card('user',s.completionRate+'%','Overall Completion Rate','rate',`<div class="meter" role="img" aria-label="Overall completion ${s.completionRate}%"><span style="width:${s.completionRate}%"></span></div>`)}</div>`;
}
// One scale, 0–100%, so departments compare directly. More departments than fit as columns become rows, which have room for long names.
function departmentRates(departments,columns=4){
  if(!departments.length)return '<p class="muted">No assignments match these filters.</p>';
  const tipFor=d=>`${d.department}: ${d.completed} of ${d.total} completed (${d.completionRate}%)`;
  if(departments.length>columns)return departments.map(d=>`<div class="chart-row" tabindex="0" data-tip="${esc(tipFor(d))}"><span class="chart-label">${esc(d.department)}<small>${d.completed} of ${d.total} completed</small></span>${meter(d.completionRate,d.department+' completion')}</div>`).join('');
  const grid=[100,75,50,25,0].map(v=>`<i style="bottom:${v}%"><b>${v}%</b></i>`).join('');
  return `<div class="dept-chart"><div class="dept-plot">${grid}${departments.map(d=>`<div class="dept-col" tabindex="0" role="img" aria-label="${esc(tipFor(d))}" data-tip="${esc(tipFor(d))}"><span class="dept-bar" style="height:${d.completionRate}%"></span><b style="bottom:${d.completionRate}%">${d.completionRate}%</b></div>`).join('')}</div><div class="dept-names">${departments.map(d=>`<span>${esc(d.department)}<small>${d.completed} of ${d.total}</small></span>`).join('')}</div></div>`;
}
function statusDonut(s){
  let start=0;
  const total=s.total,present=COMPLIANCE_SERIES.filter(([key])=>s[key]),gap=present.length>1?.7:0;
  const arcs=present.map(([key,label,tone])=>{const share=s[key]/total*100,arc=`<circle class="donut-arc ${tone}" cx="70" cy="70" r="54" pathLength="100" stroke-dasharray="${Math.max(share-gap,.2)} ${100-Math.max(share-gap,.2)}" stroke-dashoffset="${-start}"><title>${esc(label)}: ${s[key]} (${Math.round(share)}%)</title></circle>`;start+=share;return arc;}).join('');
  const legend=COMPLIANCE_SERIES.map(([key,label,tone])=>`<li><i class="legend-mark ${tone}"></i><span>${esc(label)}</span><small>${total?Math.round(s[key]/total*100):0}%</small><b>${s[key]}</b></li>`).join('');
  return `<div class="donut-wrap"><svg class="donut" viewBox="0 0 140 140" role="img" aria-label="${total} assignments by status"><g transform="rotate(-90 70 70)"><circle class="donut-track" cx="70" cy="70" r="54"></circle>${arcs}</g><text x="70" y="68" class="donut-total">${total}</text><text x="70" y="85" class="donut-caption">Assignments</text></svg><ul class="donut-legend">${legend}</ul></div>`;
}
function overdueList(o){
  if(!o.total)return emptyState('No overdue courses','Everyone matching these filters is within their deadline or has finished.');
  return `<ul class="overdue-list">${o.rows.slice(0,4).map(r=>`<li class="${r.mandatory?'is-mandatory':''}"><span class="avatar">${complianceInitials(r.employee)}</span><div class="overdue-who"><strong>${esc(r.employee)}</strong><small>${complianceShortId(r.employeeId)} · ${esc(r.department)}</small><span class="overdue-course">${esc(r.course)}</span></div><div class="overdue-state">${compliancePill(r.overdueBy.split(', ')[0]+' overdue','danger')}${meter(r.progress,'Progress')}</div></li>`).join('')}</ul>`;
}
function complianceAnalytics(d){
  const viewAll=`<button class="link-action" data-act="compliance-tab" data-tab="overdue">View All ${icon('arrow')}</button>`;
  return `<div class="compliance-analytics">${panel('Department-wise Compliance',departmentRates(d.departments))}${panel('Training Status Distribution',statusDonut(d.summary))}${panel(`Overdue Courses (${d.overdue.total})`,overdueList(d.overdue),d.overdue.total?viewAll:'')}</div>`;
}
function recordDetails(r){
  const fact=(label,value)=>`<div><dt>${esc(label)}</dt><dd>${esc(value||'—')}</dd></div>`,manage=['admin','hr'].includes(currentUser.role);
  return `<tr class="record-details"><td colspan="12"><dl>${fact('Employee ID',r.employeeId)}${fact('Email',r.email)}${fact('Assigned',r.assignedDisplay)}${fact('Deadline in force',r.deadlineDisplay||'No deadline')}${fact('Original deadline',r.originalDeadlineDisplay)}${fact('Completed',r.completedDisplay)}${fact('Last activity',r.lastActivityDisplay||'No activity yet')}${r.overdueBy?fact('Overdue by',r.overdueBy):''}</dl><div class="table-actions"><button data-act="compliance-employee" data-id="${esc(r.employeeId)}">All records for ${esc(r.employee)}</button>${manage?`<a href="#admin-courses" data-act="compliance-manage" data-id="${esc(r.courseId)}">Manage deadline</a>`:''}</div></td></tr>`;
}
function recordsTable(t){
  if(!t.total)return panel('Employee Training Records',emptyState('No assignments match these filters','Change or reset the filters to see more records.'));
  const {key,dir}=compliance.sort;
  const head=(field,label)=>`<th aria-sort="${key===field?(dir==='desc'?'descending':'ascending'):'none'}"><button class="sort-head" data-act="compliance-sort" data-key="${field}">${esc(label)}<span aria-hidden="true">${key===field?(dir==='desc'?'▼':'▲'):'↕'}</span></button></th>`;
  const cell=(label,html,cls='')=>`<td data-label="${esc(label)}" class="${cls}">${html}</td>`;
  const row=r=>{const id=r.employeeId+'|'+r.courseId,open=compliance.open===id;return `<tr>${cell('Employee Name',`<strong>${esc(r.employee)}</strong>`)}${cell('Employee ID',complianceShortId(r.employeeId),'record-id')}${cell('Department',esc(r.department))}${cell('Job Role',esc(r.jobRole))}${cell('Course Name',esc(r.course))}${cell('Type',complianceType(r.mandatory))}${cell('Assigned',complianceDate(r.assignedDate,r.assignedDisplay),'record-date')}${cell('Deadline',complianceDate(r.deadlineDate,r.deadlineDisplay,'No deadline'),'record-date')}${cell('Completed',complianceDate(r.completedDate,r.completedDisplay),'record-date')}${cell('Progress',meter(r.progress,'Progress'))}${cell('Status',complianceStatus(r))}${cell('Actions',`<button class="icon-action" data-act="compliance-details" data-id="${esc(id)}" aria-expanded="${open}" aria-label="View details for ${esc(r.employee)}, ${esc(r.course)}" title="View details">${icon('eye')}</button>`)}</tr>${open?recordDetails(r):''}`;};
  return panel('Employee Training Records',`<div class="admin-table-scroll"><table class="admin-table records-table"><thead><tr>${head('employee','Employee Name')}${head('employeeId','Employee ID')}${head('department','Department')}${head('jobRole','Job Role')}${head('course','Course Name')}${head('type','Type')}${head('assigned','Assigned')}${head('deadline','Deadline')}${head('completed','Completed')}${head('progress','Progress')}${head('status','Status')}<th>Actions</th></tr></thead><tbody>${t.rows.map(row).join('')}</tbody></table></div><div class="pager"><span class="muted">${t.total} record${t.total===1?'':'s'} · page ${t.page} of ${t.pages}</span><label class="page-size">Rows per page <select data-change="compliance-size" aria-label="Rows per page">${options([[10,'10'],[25,'25'],[50,'50']],compliance.size)}</select></label>${compliancePager(t,'page')}</div>`,complianceExportMenu('Export',false));
}
function departmentTab(departments){
  if(!departments.length)return panel('Department Compliance','<p class="muted">No assignments match these filters.</p>');
  const largest=Math.max(...departments.map(d=>d.total));
  const stack=d=>{const tip=`${d.department}: ${d.completed} completed, ${d.pending} pending, ${d.overdue} overdue, ${d.total} assigned`;return `<div class="chart-row" tabindex="0" role="img" aria-label="${esc(tip)}" data-tip="${esc(tip)}"><span class="chart-label">${esc(d.department)}</span><div class="chart-track"><div class="chart-stack" style="width:${d.total/largest*100}%">${[['on-time',d.completed],['progress',d.pending],['overdue',d.overdue]].filter(([,n])=>n).map(([k,n])=>`<span class="chart-seg ${k}" style="flex-grow:${n}"></span>`).join('')}</div></div><b>${d.total}</b></div>`;};
  const legend=[['on-time','Completed'],['progress','Pending'],['overdue','Overdue']].map(([k,label])=>`<span><i class="legend-mark ${k}"></i>${label}</span>`).join('');
  const rows=departments.map(d=>`<tr><td><strong>${esc(d.department)}</strong></td><td>${d.total}</td><td>${d.completed}</td><td>${d.pending}</td><td>${d.overdue}</td><td>${meter(d.completionRate,d.department+' completion')}</td></tr>`).join('');
  return `<div class="compliance-pair">${panel('Completion rate',departmentRates(departments,6))}${panel('Assigned courses by status',`<div class="chart-legend">${legend}</div>${departments.map(stack).join('')}`)}</div>${panel('Department Compliance',`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Department</th><th>Assigned</th><th>Completed</th><th>Pending</th><th>Overdue</th><th>Completion</th></tr></thead><tbody>${rows}</tbody></table></div><p class="muted">Pending courses are assigned, not completed and not yet overdue.</p>`)}`;
}
function overdueTab(o){
  const row=r=>`<tr class="${r.mandatory?'overdue-mandatory':''}"><td><strong>${esc(r.employee)}</strong><small>${complianceShortId(r.employeeId)} · ${esc(r.department)} · ${esc(r.jobRole)}</small></td><td>${esc(r.course)}<small>${complianceType(r.mandatory)}</small></td><td>${esc(r.originalDeadlineDisplay)}${r.originalDeadlineAt!==r.deadlineAt?`<small>Changed to ${esc(r.deadlineDisplay)}</small>`:''}</td><td><strong>${esc(r.overdueBy)}</strong></td><td>${meter(r.progress,'Progress')}</td><td>${r.lastActivityDisplay?esc(r.lastActivityDisplay):'No activity yet'}</td></tr>`;
  const count=`<span class="tag ${o.total?'danger':'gray'}">${o.total} OVERDUE${o.mandatory?` · ${o.mandatory} MANDATORY`:''}</span>`;
  return panel('Overdue Training',o.total?`<div class="admin-table-scroll"><table class="admin-table overdue-table"><thead><tr><th>Employee</th><th>Course</th><th>Original deadline</th><th>Overdue by</th><th>Completion</th><th>Last activity</th></tr></thead><tbody>${o.rows.map(row).join('')}</tbody></table></div><div class="pager"><span class="muted">Overdue time runs from the deadline now in force. Mandatory courses are highlighted and listed first.</span>${compliancePager(o,'overduePage')}</div>`:emptyState('No overdue courses','Everyone matching these filters is within their deadline or has finished.'),count);
}
function reportsTab(d){
  const columns=['Employee Name','Employee ID','Department','Job Role','Course Name','Mandatory/Optional','Assignment Date','Deadline','Original Deadline','Completion Date','Progress %','Current Status','Overdue By','Last Activity'];
  return `<div class="compliance-pair">${panel('Training compliance report',`<p class="muted">Download all <b>${d.table.total}</b> record${d.table.total===1?'':'s'} matching the current filters, in the current sort order. Each export is recorded in the Activity Log.</p><div class="admin-actions">${d.table.total?'<button class="btn" data-act="compliance-export" data-format="csv">Export CSV</button><button class="btn secondary" data-act="compliance-export" data-format="xlsx">Export Excel</button>':'<span class="muted">Change the filters to include some records.</span>'}</div><h3 class="sub-heading">Included columns</h3><p class="muted">${columns.map(esc).join(' · ')}</p>`)}${panel('Other learning reports',`<p class="muted">Enrollment, assessment, certificate and mandatory-training reports stay in ${currentUser.role==='manager'?'Team Reports':'Reports &amp; Analytics'}, with their own date filters.</p><div class="admin-actions"><a class="btn secondary" href="#reports" data-act="report-preset" data-type="compliance">Mandatory training report ${icon('arrow')}</a><a class="btn secondary" href="#reports" data-act="report-preset" data-type="enrollments">Enrollment report</a></div>`)}</div>`;
}
function complianceFirstPage(){compliance.pages={page:1,overduePage:1};compliance.open=null;render();}
document.addEventListener('click',event=>document.querySelectorAll('.export-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
async function complianceExport(format){
  const {key,dir}=compliance.sort,response=await fetch('/api/manage/compliance/export'+qs({...compliance.filters,sort:key,dir,format}),{credentials:'same-origin',headers:{'X-Portal-Request':'1'}});
  if(!response.ok)throw new Error((await response.json().catch(()=>({}))).error||'The report could not be exported.');
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download=(/filename="([^"]+)"/.exec(response.headers.get('Content-Disposition')||'')||[])[1]||'shimentox-training-compliance.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('Report exported.');
}
function compliancePage(){
  const team=currentUser.role==='manager',{key:sort,dir}=compliance.sort,query={...compliance.filters,...compliance.pages,sort,dir,size:compliance.size},key='compliance:'+qs(query),entry=loadData(key,'manage/compliance'+qs(query));
  if(entry.data)complianceOptions=entry.data.options;
  const tabs=`<div class="compliance-tabs" role="tablist" aria-label="Training compliance views">${COMPLIANCE_TABS.map(([id,label])=>`<button role="tab" aria-selected="${compliance.tab===id}" class="${compliance.tab===id?'active':''}" data-act="compliance-tab" data-tab="${id}">${esc(label)}</button>`).join('')}</div>`;
  const updated=entry.data?`<button class="updated-at" data-act="compliance-refresh" title="Refresh">${icon('refresh')} Last updated: ${esc(entry.data.updatedDisplay)} ${esc(entry.data.timezone)}</button>`:'';
  const head=`<div class="compliance-head"><div><h1>Training Compliance &amp; Deadline Monitoring</h1><p>${team?'Monitor course assignments, completion status, deadlines and training compliance for your direct reports.':'Monitor course assignments, completion status, deadlines and employee training compliance across ShimentoX.'}</p></div><div class="compliance-head-actions">${updated}${complianceExportMenu('Export Report',true)}</div></div>${tabs}${complianceFilterForm()}`;
  if(!entry.data)return head+stateBlock(entry,'training compliance',key);
  const d=entry.data,views={overview:()=>complianceAnalytics(d)+recordsTable(d.table),employees:()=>recordsTable(d.table),departments:()=>departmentTab(d.departments),overdue:()=>overdueTab(d.overdue),reports:()=>reportsTab(d)};
  return `<div class="compliance-page">${head}${complianceKpis(d.summary)}${views[compliance.tab]()}</div>`;
}

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
  return `<div class="intro"><div><div class="eyebrow">PREVIEW · ${esc(c.status.toUpperCase())}</div><h1>${esc(c.title)}</h1><p>${esc(c.description)}</p></div><a class="btn secondary" href="#admin-courses">Back to Manage Courses</a></div><div class="notice">This is how employees will see the course content. Answer keys are hidden, and progress is not recorded in preview.</div><p class="muted">${esc(c.category)} · ${esc(capital(c.difficulty))} · ${esc(fmtDuration(c.durationMinutes))} · Pass mark ${c.passPercent}% · ${c.maxAttempts} exam attempts per module</p>${d.course.map((m,s)=>`<section class="panel lesson-content"><span class="tag">MODULE ${s+1} OF 3</span><h2>${esc(m.title)}</h2><p>${esc(m.summary)}</p>${m.videos.map(i=>`<h3>Lesson ${i+1}: ${esc(d.lessons[i].title)}</h3><video class="course-video" controls preload="none"><source src="${esc(d.lessons[i].src)}"></video><p>${esc(d.lessons[i].body)}</p><pre><code>${esc(d.lessons[i].code)}</code></pre>`).join('')}<h3>Exercises</h3>${m.exercises.map((e,i)=>`<p><b>${i+1}. ${esc(e.title)}</b> — ${e.questions.length} questions</p>`).join('')}<h3>Module exam</h3><ol>${m.exam.map(q=>`<li>${esc(q[0])}</li>`).join('')}</ol></section>`).join('')}${resourceList(d.resources)}`;
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
let inlineAttempt=null,inlineResult=null,assessmentStarting=false;
// Assessment attempts follow the shared exam rules in learning.js; breaking one ends the attempt on the server.
function assessmentInProgress(){return Boolean(activeAssessment||inlineAttempt);}
function terminateAssessment(reason){
  const inline=Boolean(inlineAttempt),current=activeAssessment||inlineAttempt;
  if(!current)return;
  const id=current.id||current.assessmentId,result={status:'terminated',reason,details:[]};
  activeAssessment=null;inlineAttempt=null;exitExamFullscreen();
  if(inline)inlineResult={assessmentId:id,result};else assessmentResult=result;
  render();
  api(`me/assessments/${id}/terminate`,{attemptId:current.attempt.id,reason},{keepalive:true})
    .then(()=>inline?refreshCourseExtras():refreshData('me-assess','me-dash')).catch(()=>{}).finally(()=>{refreshNotifications();render();});
}
// Knowledge checks and the final assessment run inline on the lesson page, using the standard assessment engine.
function inlineResultView(r){
  if(r.status==='expired')return '<div class="notice" role="status">Time expired. The attempt ended without a score and counts toward your attempts.</div>';
  if(r.status==='terminated')return `<div class="notice" role="status">${esc(r.reason||'The attempt was ended.')} It ended without a score and counts toward your attempts.</div>`;
  return `<div class="inline-result ${r.status==='passed'?'good':''}" role="status"><strong>${r.status==='passed'?'Passed':'Not passed yet'}: ${r.score}/${r.total} correct (${r.percent}%) · pass mark ${r.passPercent}%</strong><ol>${r.details.map(d=>`<li class="${d.correct?'met':'missed'}">${d.correct?'✓ Correct.':`✗ Incorrect. Correct answer: <b>${esc(d.answer||'')}</b>.`} ${esc(d.explanation||'')}</li>`).join('')}</ol></div>`;
}
// While a knowledge check or final assessment is running, the course page is replaced by this exam-only view.
function inlineExamPanel(){
  const id=inlineAttempt.assessmentId,attempt=inlineAttempt.attempt,info=(currentCourseExtras?.assessments||[]).find(a=>a.id===id)||{};
  const form=`<form data-form="inline-assessment" data-id="${esc(id)}">${attempt.questions.map((q,i)=>`<fieldset class="question"><legend><span>${i+1}.</span> ${esc(q.prompt)}</legend>${q.code?codeBlock([q.code],''):''}${q.options.map((o,j)=>`<label class="answer"><input type="radio" name="q${i}" value="${j}" required><span class="answer-letter" aria-hidden="true">${String.fromCharCode(65+j)}</span><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}<div class="notice">${EXAM_ACTIVE_NOTICE}</div><button class="btn" type="submit">Submit answers ${icon('check')}</button> <button class="btn secondary" type="button" data-act="assessment-end">End attempt</button><p class="form-status" role="status"></p></form>`;
  return `<div class="exam-focus"><div class="exam-top"><div><span class="tag">${info.kind==='post'?'FINAL ASSESSMENT':'KNOWLEDGE CHECK'} · ATTEMPT ${attempt.attemptNumber}</span><h1>${esc(info.title||'Assessment')}</h1></div><div class="exam-timer" role="timer" aria-label="Time remaining" id="assessment-timer">--:--</div></div><div class="panel">${form}</div></div>`;
}
function inlineAssessmentPanel(id,heading){
  const info=(currentCourseExtras?.assessments||[]).find(a=>a.id===id);
  if(!info)return '';
  const attempt=inlineAttempt?.assessmentId===id?inlineAttempt.attempt:null,result=inlineResult?.assessmentId===id?inlineResult.result:null;
  const status=info.passed?`<span class="tag success">PASSED · BEST ${info.best}%</span>`:info.best!=null?`<span class="tag warn">BEST ${info.best}%</span>`:'<span class="tag gray">NOT TAKEN</span>';
  const body=attempt?''
    :`${result?inlineResultView(result):''}${info.attemptsLeft?`<button class="btn ${result||info.passed?'secondary':''}" data-act="inline-start" data-id="${esc(id)}">${info.best!=null?'Retake':'Start'} ${esc(heading.toLowerCase())} ${icon('arrow')}</button>`:'<p class="muted">No attempts left.</p>'}`;
  return `<section class="knowledge-check knowledge-card" aria-label="${esc(heading)}"><div class="knowledge-head"><span class="knowledge-icon">${icon('check')}</span><div><h3>${esc(heading)}</h3><p>Pass mark ${info.passPercent}% · ${info.attemptsLeft} attempt${info.attemptsLeft===1?'':'s'} left · answer order is shuffled on every attempt.</p>${attempt?'':`<ul class="exam-rule-list">${EXAM_RULE_ITEMS}</ul>`}</div>${status}</div>${body}</section>`;
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
  'keka-sync':async el=>{el.disabled=true;try{kekaSyncResult=(await api('manage/keka/sync',{})).keka;await loadAdminState();refreshData('people','org','dash','mgr-dash');}catch(error){toast(error.message);}finally{el.disabled=false;render();}},
  'notifications-read-all':async()=>{const data=await api('me/notifications/read',{all:true});notificationState.items=data.notifications;notificationState.unread=data.unread;render();},
  'notification-open':async el=>{const data=await api('me/notifications/read',{ids:[Number(el.dataset.id)]});notificationState={items:data.notifications,unread:data.unread,open:false};const link=el.dataset.link||'';if(link.startsWith('course:'))await loadCourse(link.slice(7));else if(link)location.hash=link;render();},
  'reminder-panel':()=>{reminderPanelOpen=!reminderPanelOpen;render();},
  'notification-filter':el=>{notificationState.filter=el.dataset.value;render();},
  'reminders-run':async()=>{const data=await api('manage/reminders/run',{});pageCache['reminder-settings']={data:{settings:data.settings}};refreshData('reminder-history','deadlines');toast(`Reminders processed: ${data.summary.sent} sent, ${data.summary.failed} failed.`);render();},
  'dash-period-clear':()=>{devFilters.dashboard={};render();},
  'course-filter':el=>{courseFilter=el.dataset.value;render();},
  'course-area':el=>{courseArea=el.dataset.value;render();},
  'compliance-reset':()=>{compliance.filters={};complianceFirstPage();},
  'compliance-page':el=>{compliance.pages[el.dataset.field]=Number(el.dataset.page);render();},
  'compliance-export':el=>{const menu=el.closest('details');if(menu)menu.open=false;return complianceExport(el.dataset.format);},
  'compliance-tab':el=>{compliance.tab=el.dataset.tab;render();},
  'compliance-clear':el=>{delete compliance.filters[el.dataset.field];complianceFirstPage();},
  'compliance-sort':el=>{const k=el.dataset.key,s=compliance.sort;compliance.sort={key:k,dir:s.key===k&&s.dir==='asc'?'desc':'asc'};complianceFirstPage();},
  'compliance-details':el=>{compliance.open=compliance.open===el.dataset.id?null:el.dataset.id;render();},
  'compliance-employee':el=>{compliance.filters={employee:el.dataset.id};compliance.tab='employees';complianceFirstPage();},
  'compliance-manage':el=>{deadlineCourseId=el.dataset.id;},
  'compliance-refresh':()=>{refreshData('compliance');render();},
  'report-preset':el=>{devFilters.report={type:el.dataset.type,page:1};},
  'report-reset':()=>{devFilters.report={type:devFilters.report.type,page:1};render();},
  'report-page':el=>{devFilters.report.page=Number(el.dataset.page);render();},
  'report-export':async el=>{const data=await api('manage/reports'+el.dataset.query);download(`shimentox-${data.type}-report.csv`,toCSV(data.columns,data.rows),'text/csv;charset=utf-8');toast(`Exported ${data.rows.length} records.`);},
  'history-page':el=>{historyPage=Number(el.dataset.page);render();},
  'record-delete':async el=>{await api('me/records',{id:el.dataset.id,delete:true});refreshData('me-history');render();},
  'session-register':async el=>{const data=await api(`me/sessions/${el.dataset.id}/register`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='You are registered for the session.';render();},
  'session-cancel':async el=>{const data=await api(`me/sessions/${el.dataset.id}/cancel`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='Your registration was cancelled.';render();},
  'session-new':()=>{sessionEditor={};render();},
  'session-edit':el=>{sessionEditor={...pageCache['m-sessions'].data.sessions.find(s=>s.id===el.dataset.id)};render();},
  'session-editor-close':()=>{sessionEditor=null;render();},
  'session-roster':el=>{sessionRoster=el.dataset.id;delete pageCache['roster:'+el.dataset.id];render();},
  'session-roster-close':()=>{sessionRoster=null;render();},
  'assessment-start':async el=>{const item=pageCache['me-assess'].data.assessments.find(a=>a.id===el.dataset.id);if(assessmentStarting||examActive())return;assessmentStarting=true;
    try{if(!await enterExamFullscreen())return toast(FULLSCREEN_REQUIRED);const data=await api(`me/assessments/${item.id}/start`,{});activeAssessment={id:item.id,title:item.title,attempt:data.attempt};assessmentResult=null;render();updateAssessmentTimer();}
    catch(error){exitExamFullscreen();throw error;}finally{assessmentStarting=false;}},
  'assessment-end':()=>terminateAssessment('You ended this attempt before submission.'),
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
      if(!confirm(`${course.learners} employee${course.learners===1?' has':'s have'} started “${course.title}”, so it cannot be deleted without losing their progress and certificates.\n\nArchive it instead? It disappears from catalogs; records are kept.`))return;
      await api(`admin/courses/${encodeURIComponent(course.id)}/archive`,{});await loadAdminState();render();toast(`“${course.title}” archived.`);return;
    }
    if(!confirm(`Delete “${course.title}” permanently?\n\nIts lessons, assessments and assignments are removed. This cannot be undone.`))return;
    await api(`admin/courses/${encodeURIComponent(course.id)}/delete`,{});
    if(editingCourse===course.id)editingCourse=null;
    await loadAdminState();render();toast(`“${course.title}” deleted.`);
  },
  'course-preview':el=>{const course=adminState.courses.find(c=>c.id===el.dataset.id);if(course?.format==='lessons'){if(location.hash!=='#admin-courses')location.hash='admin-courses';return openCourseBuilder(course.id,4);}previewCourseId=el.dataset.id;delete pageCache['preview:'+el.dataset.id];location.hash='course-preview';},
  'copy-code':async el=>{const code=el.closest('.code-block')?.querySelector('code')?.textContent||'';await navigator.clipboard.writeText(code);el.textContent='Copied ✓';setTimeout(()=>{el.textContent='Copy';},1600);},
  'lesson-section':el=>{const heading=document.getElementById(el.dataset.id);if(heading){heading.scrollIntoView({behavior:'smooth',block:'start'});heading.focus({preventScroll:true});}},
  'lesson-select':el=>{if(activeExam||examStarting||examFinishing)return;const target=currentCourseExtras?.courseLessons?.find(l=>l.id===el.dataset.id);if(target?.locked)return;selectedCheckpointId=null;selectedLessonId=el.dataset.id;inlineAttempt=null;examNotice='';render();window.scrollTo?.(0,0);if(el.dataset.id!=='final'&&learning.run.id)learningRequest('lesson-open',{lessonId:el.dataset.id}).catch(()=>{});},
  'inline-start':async el=>{if(assessmentStarting||examActive())return;assessmentStarting=true;
    try{if(!await enterExamFullscreen())return toast(FULLSCREEN_REQUIRED);const data=await api(`me/assessments/${el.dataset.id}/start`,{});inlineAttempt={assessmentId:el.dataset.id,attempt:data.attempt};inlineResult=null;render();window.scrollTo?.(0,0);updateAssessmentTimer();}
    catch(error){exitExamFullscreen();throw error;}finally{assessmentStarting=false;}},
  'resource-delete':async el=>{await api(`manage/resources/${el.dataset.id}/delete`,{});await loadAdminState();render();},
  'assignment-delete':async el=>{await api(`manage/assignments/${el.dataset.id}/delete`,{});refreshData('deadlines');courseCatalog=(await api('courses')).courses;render();},
};
const SUBMITS={
  'announcement-send':form=>submitForm(form,async()=>{await api('manage/announcements',formValues(form));await refreshNotifications();toast('Announcement published.');}),
  'dash-period':form=>{const v=formValues(form);devFilters.dashboard={from:v.from,to:v.to};render();},
  'compliance-filters':form=>{compliance.filters=Object.fromEntries(Object.entries(formValues(form)).filter(([,v])=>v));complianceFirstPage();},
  'report-filters':form=>{const v=formValues(form);devFilters.report={type:v.type||devFilters.report.type,department:v.department,employee:v.employee,course:v.course,from:v.from,to:v.to,page:1};render();},
  'session-save':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('manage/sessions',{...v,id:form.dataset.id||null,capacity:Number(v.capacity),courseId:v.courseId||null,trainerId:v.trainerId||null});pageCache['m-sessions']={data};sessionEditor=null;refreshData('me-cal');devMessage='Session saved.';render();}),
  'assessment-submit':form=>submitForm(form,async()=>{const a=activeAssessment,answers=a.attempt.questions.map((_,i)=>{const value=new FormData(form).get('q'+i);return value===null?null:Number(value);});if(answers.includes(null))throw new Error('Answer every question before submitting.');const data=await api(`me/assessments/${a.id}/submit`,{attemptId:a.attempt.id,answers});activeAssessment=null;exitExamFullscreen();assessmentResult=data.result;refreshData('me-assess','me-skills','me-dash');refreshNotifications();if(data.result.status==='passed'){try{learning.certificates=(await api('certificates')).certificates;}catch{/* The list refreshes on the next page load. */}}render();}),
  'assessment-save':form=>submitForm(form,async()=>{const v=formValues(form);let questions;try{questions=JSON.parse(v.questions);}catch{throw new Error('The question bank JSON is invalid. Check its syntax.');}const data=await api('manage/assessments',{id:form.dataset.id||null,title:v.title,description:v.description,kind:v.kind,courseId:v.courseId||null,skillId:v.skillId||null,skillLevel:Number(v.skillLevel),passPercent:Number(v.passPercent),maxAttempts:Number(v.maxAttempts),questionCount:Number(v.questionCount),timeLimitMinutes:Number(v.timeLimitMinutes),status:v.status,questions});pageCache['m-assess']={data:{assessments:data.assessments}};assessmentEditor=null;refreshData('me-assess');devMessage='Assessment saved.';render();}),
  'record-save':form=>submitForm(form,async()=>{const v=formValues(form);await api('me/records',{title:v.title,provider:v.provider,completedOn:v.completedOn,hours:Number(v.hours||0)});refreshData('me-history');historyPage=1;render();}),
  'training-target':form=>submitForm(form,async()=>{const v=formValues(form),ids=trainingTargetIds(v.target||'');if(!ids.length)throw new Error('No employees match this choice.');
    const data=await api('manage/training-targets',{employeeIds:ids,hours:v.hours===''?null:Number(v.hours)});
    for(const user of adminState.candidates||[])if(data.training[user.id])user.training=data.training[user.id];
    if(recordPreview&&data.training[recordPreview.user.id])recordPreview.training=data.training[recordPreview.user.id];
    refreshData('mgr-dash','me-dash');toast(v.hours===''?'Training target removed.':`Training target saved: ${v.hours} hours for ${ids.length} employee${ids.length===1?'':'s'}.`);render();}),
  'user-profile':form=>submitForm(form,async()=>{const v=formValues(form);await api(`admin/candidates/${form.dataset.id}/profile`,{name:v.name,role:v.role,departmentId:v.departmentId||null,jobRoleId:v.jobRoleId||null,managerId:v.managerId||null,jobTitle:v.jobTitle});editUserId=null;adminMessage='Employee profile updated.';await loadAdminState();refreshData('people','org');render();}),
  'org-save':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('manage/'+form.dataset.kind,{name:v.name,departmentId:v.departmentId||null});pageCache.org={data};render();}),
  'resource-save':form=>submitForm(form,async()=>{const v=formValues(form);let url=v.url;const file=form.querySelector('input[type="file"]')?.files?.[0];if(file){url=(await uploadMaterial(file)).url;}if(!url)throw new Error('Choose a file to upload or enter a link.');await api(`manage/courses/${form.dataset.id}/resources`,{title:v.title,kind:v.kind,url,moduleIndex:intOrNull(v.moduleIndex)});await loadAdminState();adminMessage='Learning material added.';render();}),
  'deadline-save':form=>submitForm(form,async()=>{const v=formValues(form),target=form.dataset.target;await api('manage/assignments',{courseId:form.dataset.course,targetType:target?form.dataset.type:v.targetType,targetId:target||v.targetId,mandatory:v.mandatory==='on',deadline:v.deadline||null,note:v.note||''});refreshData('deadlines','reminder-history','me-dash');courseCatalog=(await api('courses')).courses;adminMessage='Deadline saved. Employees have been notified.';render();}),
  'reminder-settings':form=>submitForm(form,async()=>{const v=formValues(form),intervalDays=String(v.intervalDays||'').split(',').map(x=>x.trim()).filter(Boolean).map(Number);const data=await api('manage/reminders/settings',{intervalDays,dueSoonDays:Number(v.dueSoonDays),deadlineDay:v.deadlineDay==='on',overdue:v.overdue==='on'});pageCache['reminder-settings']={data};refreshData('deadlines');courseCatalog=(await api('courses')).courses;toast('Reminder schedule saved.');render();}),
  'lesson-activity':form=>submitForm(form,async()=>{const lesson=currentCourseExtras.courseLessons.find(l=>l.id===form.dataset.lesson),answers=lesson.activity.tasks.map((_,i)=>(form.querySelector(`#answer-${i}`)?.value||'').trim());if(answers.some(a=>!a))throw new Error('Write a prompt for every task before submitting.');const result=await learningRequest('lesson-activity',{lessonId:lesson.id,answers});const r=result.activityResult;refreshData('me-dash','me-paths');toast(r.passed?`Passed with ${r.score}%. Review the feedback and model answers.`:`You scored ${r.score}%. You need ${r.passPercent}% — use the tips and try again.`);render();document.getElementById('activity-title')?.scrollIntoView?.({behavior:'smooth',block:'start'});}),
  'inline-assessment':form=>submitForm(form,async()=>{const id=form.dataset.id,questions=inlineAttempt.attempt.questions,values=new FormData(form),answers=questions.map((_,i)=>values.get('q'+i)===null?null:Number(values.get('q'+i)));if(answers.includes(null))throw new Error('Answer every question before submitting.');const data=await api(`me/assessments/${id}/submit`,{attemptId:inlineAttempt.attempt.id,answers});inlineResult={assessmentId:id,result:data.result};inlineAttempt=null;exitExamFullscreen();await refreshCourseExtras();refreshData('me-assess','me-dash');refreshNotifications();toast(data.result.status==='passed'?`Passed with ${data.result.percent}%.`:data.result.status==='expired'?'Time expired.':`You scored ${data.result.percent}%. Review the explanations and try again.`);render();}),
  'lesson-complete':form=>submitForm(form,async()=>{const v=formValues(form),list=currentCourseExtras.courseLessons,i=list.findIndex(l=>l.id===form.dataset.lesson);await learningRequest('lesson',{lessonId:form.dataset.lesson,response:v.response||''});selectedLessonId=list[i+1]?.id||form.dataset.lesson;refreshData('me-dash','me-paths');toast(list[i+1]?'Lesson completed. On to the next one.':'Lesson completed.');render();}),
  assistant:form=>submitForm(form,async()=>{const v=formValues(form);const data=await api('me/assistant',{courseId:currentCourseInfo.id,mode:v.mode,lessonIndex:intOrNull(v.lessonIndex),question:v.question});assistantAnswer={courseId:currentCourseInfo.id,text:data.answer+(data.truncated?'\n\n(The answer was cut short.)':'')};render();}),
};
const CHANGES={
  'deadline-course':el=>{deadlineCourseId=el.value;render();},
  'compliance-size':el=>{compliance.size=Number(el.value);complianceFirstPage();},
  'target-type':el=>{const target=document.getElementById(el.dataset.target);if(target)target.innerHTML=options(targetChoices(el.value),'','Select…');},
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
