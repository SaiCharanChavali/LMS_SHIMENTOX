// Learning activity history: the employee's own timeline (Learning history page) and, for HR, admins and managers, the
// Learning Activity dashboard with its table, analytics and per-employee history. Every figure comes from the server's
// activity records; filters and pagination run on the server, which also decides whose activity each user may see.

const ACTIVITY_GROUP_ICONS={course:'book',lesson:'play',assessment:'check',other:'award'};
const ACTIVITY_STATUS={passed:['PASSED','success'],failed:['FAILED','danger'],completed:['COMPLETED','success'],issued:['ISSUED','success'],submitted:['SUBMITTED','gray'],started:['STARTED',''],in_progress:['IN PROGRESS','']};
const ACTIVITY_GROUPS=[['course','All course activity'],['lesson','All lesson activity'],['assessment','All assessment activity'],['other','Certificates and resources']];
const WEEKDAYS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const activityDefaults=()=>({tab:'activity',filters:{},page:1,employee:null,employeeFilters:{},employeePage:1,analytics:{}});
let myHistory={filters:{},page:1},actv=activityDefaults(),actvOptions=null;
function resetActivity(){myHistory={filters:{},page:1};actv=activityDefaults();actvOptions=null;}

function activityIcon(item){return item.type==='resource_accessed'?'file':item.type==='certificate_generated'?'award':ACTIVITY_GROUP_ICONS[item.group]||'book';}
function activityStatus(item){
  const [label,tone]=ACTIVITY_STATUS[item.status]||[];
  return `${label?`<span class="tag ${tone}">${label}</span>`:''}${item.detail?`<small>${esc(item.detail)}</small>`:''}`;
}
// One event per row: what happened, to which course or lesson, when, and the result where there is one.
function activityTimeline(items,withEmployee=false){
  if(!items.length)return '';
  return `<ol class="activity-timeline">${items.map(item=>`<li class="activity-event group-${esc(item.group)}"><span class="activity-dot" aria-hidden="true">${icon(activityIcon(item))}</span><div class="activity-event-body"><div class="activity-event-head"><strong>${esc(item.label)}</strong><time datetime="${esc(item.at)}">${esc(fmtDateTime(item.at))}</time></div><p>${withEmployee?`<b>${esc(item.employee)}</b> · `:''}${esc(item.subject)}${item.subject!==item.course?` <span class="muted">in ${esc(item.course)}</span>`:''}</p><div class="activity-event-status">${activityStatus(item)}${item.backfilled?'<small class="muted" title="Recorded from learning records kept before activity history was introduced.">From earlier records</small>':''}</div></div></li>`).join('')}</ol>`;
}
function activityTypeOptions(types,selected){
  return `<option value="">All activity</option><optgroup label="Groups">${options(ACTIVITY_GROUPS,selected)}</optgroup><optgroup label="Activity">${options(types,selected)}</optgroup>`;
}
function activityPager(d,act){
  return d.pages>1?`<div class="pager"><span class="muted">${d.total} activit${d.total===1?'y':'ies'} · page ${d.page} of ${d.pages}</span><span class="table-actions"><button data-act="${act}" data-page="${d.page-1}" ${d.page<=1?'disabled':''}>Previous</button><button data-act="${act}" data-page="${d.page+1}" ${d.page>=d.pages?'disabled':''}>Next</button></span></div>`:`<p class="muted activity-count">${d.total} activit${d.total===1?'y':'ies'}</p>`;
}
// Course, activity type and date range; shared by the employee's own history and an employee's history seen by staff.
function timelineFilters(form,d,f){
  return `<form class="report-filters panel activity-filters" data-form="${form}"><div><label for="${form}-course">Course</label><select id="${form}-course" name="course">${options(d.courses.map(c=>[c.id,c.title]),f.course,'All courses')}</select></div><div><label for="${form}-type">Activity type</label><select id="${form}-type" name="type">${activityTypeOptions(d.types,f.type)}</select></div><div><label for="${form}-from">From</label><input id="${form}-from" type="date" name="from" value="${esc(f.from||'')}"></div><div><label for="${form}-to">To</label><input id="${form}-to" type="date" name="to" value="${esc(f.to||'')}"></div><div class="filter-actions"><button class="btn" type="submit">Apply filters</button><button class="btn secondary" type="button" data-act="${form}-reset">Reset</button></div></form>`;
}

// ---------------------------------------------------------------- employee: Learning history

function historyPageView(){
  const query={...myHistory.filters,page:myHistory.page},key='me-history:'+qs(query),entry=loadData(key,'me/history'+qs(query));
  const head=intro('Learning history','Your learning activity: courses you opened and completed, lessons, assessment attempts and results, and certificates.','MY RECORDS')+devNotice();
  if(!entry.data)return head+stateBlock(entry,'learning history',key);
  const d=entry.data,filtered=Object.values(myHistory.filters).some(Boolean);
  const timeline=d.items.length?activityTimeline(d.items)+activityPager(d,'history-page'):emptyState(filtered?'No activity matches these filters':'No learning activity yet',filtered?'Change or reset the filters to see more of your history.':'Open a course from My Learning. Lessons, assessments and completions will appear here.',filtered?'':'<a class="btn" href="#courses">Go to My Learning</a>');
  const sessions=d.sessions?.length?panel('Attended sessions',d.sessions.map(s=>`<div class="admin-list-row"><div><strong>${esc(s.title)}</strong><small>${esc(fmtDateTime(s.at))}</small></div><span class="tag success">ATTENDED</span></div>`).join('')):'';
  return head+timelineFilters('history-filters',d,myHistory.filters)+`<div class="dash-grid"><div class="dash-main">${panel('Activity timeline',timeline)}</div><div class="dash-side">${sessions}${panel('Professional development records',`${d.records.map(r=>`<div class="admin-list-row"><div><strong>${esc(r.title)}</strong><small>${esc(r.provider||'Self-reported')} · ${esc(fmtDate(r.completedOn))} · ${r.hours} h</small></div><button class="auth-link" data-act="record-delete" data-id="${r.id}">Delete</button></div>`).join('')||'<p class="muted">Record external courses, conferences or certifications.</p>'}<form class="admin-form compact-form" data-form="record-save"><label for="record-title">Title</label><input id="record-title" name="title" minlength="2" maxlength="150" required><label for="record-provider">Provider</label><input id="record-provider" name="provider" maxlength="150"><label for="record-date">Completed on</label><input id="record-date" type="date" name="completedOn" required><label for="record-hours">Hours</label><input id="record-hours" type="number" name="hours" min="0" max="1000" step="0.5" value="1"><button class="btn" type="submit">Add record</button><p class="form-status" role="status"></p></form><p class="muted">Self-reported records are shown separately from verified internal training.</p>`)}</div></div>`;
}

// ---------------------------------------------------------------- HR, admin and manager: Learning Activity

function learningActivityPage(){
  const team=currentUser.role==='manager';
  const head=intro(team?'Team activity':'Learning activity',team?'Learning activity of your direct reports. You can see only employees who report to you.':'Recorded learning activity across the organisation: what was accessed, completed and attempted.','AUTHORISED VIEW');
  const tabs=`<div class="compliance-tabs" role="tablist" aria-label="Learning activity views">${[['activity','Activity'],['analytics','Analytics']].map(([id,label])=>`<button role="tab" aria-selected="${actv.tab===id&&!actv.employee}" class="${actv.tab===id&&!actv.employee?'active':''}" data-act="actv-tab" data-tab="${id}">${label}</button>`).join('')}</div>`;
  const note='<p class="muted activity-note">Activity records show access, completion and results. Opening a course is not proof of learning, and activity volume is not a measure of productivity or working time.</p>';
  if(actv.employee)return head+tabs+employeeActivityView();
  return head+tabs+(actv.tab==='analytics'?activityAnalyticsView():staffActivityView())+note;
}
function staffFilters(o,f){
  const people=o?o.employees.map(p=>[p.id,p.name]):[],courses=o?o.courses.map(c=>[c.id,c.title]):[];
  return `<form class="report-filters panel activity-filters" data-form="actv-filters"><div><label for="actv-q">Search employee</label><input id="actv-q" type="search" name="q" maxlength="80" placeholder="Employee name" value="${esc(f.q||'')}"></div><div><label for="actv-employee">Employee</label><select id="actv-employee" name="employee">${options(people,f.employee,'All employees')}</select></div>${o?`<div><label for="actv-department">Department</label><select id="actv-department" name="department">${options(o.departments.map(d=>[d.id,d.name]),f.department,'All departments')}</select></div><div><label for="actv-role">Job role</label><select id="actv-role" name="jobRole">${options(o.jobRoles.map(j=>[j.id,j.name]),f.jobRole,'All job roles')}</select></div>`:''}<div><label for="actv-course">Course</label><select id="actv-course" name="course">${options(courses,f.course,'All courses')}</select></div><div><label for="actv-type">Activity type</label><select id="actv-type" name="type">${activityTypeOptions(o?o.types:[],f.type)}</select></div><div><label for="actv-from">From</label><input id="actv-from" type="date" name="from" value="${esc(f.from||'')}"></div><div><label for="actv-to">To</label><input id="actv-to" type="date" name="to" value="${esc(f.to||'')}"></div><div class="filter-actions"><button class="btn" type="submit">Apply filters</button><button class="btn secondary" type="button" data-act="actv-reset">Reset</button></div></form>`;
}
function staffActivityView(){
  const query={...actv.filters,page:actv.page},key='actv:'+qs(query),entry=loadData(key,'manage/activity'+qs(query));
  if(entry.data)actvOptions=entry.data.options;
  const filters=staffFilters(actvOptions,actv.filters);
  if(!entry.data)return filters+stateBlock(entry,'learning activity',key);
  const d=entry.data,s=d.summary;
  const stats=`<div class="activity-stats">${kpi('chart',s.totalActivities,'Learning activities')}${kpi('users',s.activeLearners,'Active learners','With at least one activity')}${kpi('book',s.coursesAccessed,'Courses accessed','Opened, started or resumed')}${kpi('play',s.lessonsCompleted,'Lessons completed')}${kpi('check',s.assessmentsAttempted,'Assessments attempted','Attempts started or submitted')}${kpi('award',s.coursesCompleted,'Courses completed')}</div>`;
  const rows=d.items.map(i=>`<tr><td><button class="link-button" data-act="actv-employee" data-id="${esc(i.employeeId)}">${esc(i.employee)}</button><small>${esc(i.employeeNumber||i.employeeId.slice(0,8))}</small></td><td>${esc(i.department||'—')}</td><td>${esc(i.jobRole||'—')}</td><td>${esc(i.course)}</td><td><strong>${esc(i.label)}</strong>${i.subject!==i.course?`<small>${esc(i.subject)}</small>`:''}</td><td>${esc(fmtDateTime(i.at))}</td><td>${i.progress==null?'—':`<div class="activity-progress"><div class="progress" role="img" aria-label="Course progress ${i.progress}%"><span style="width:${i.progress}%"></span></div><small>${i.progress}%</small></div>`}</td><td>${i.group==='assessment'?activityStatus(i)||'—':'—'}</td></tr>`).join('');
  const table=`<div class="admin-table-scroll"><table class="admin-table activity-table"><thead><tr><th>Employee</th><th>Department</th><th>Job role</th><th>Course</th><th>Activity</th><th>Date and time</th><th>Course progress</th><th>Assessment result</th></tr></thead><tbody>${rows||'<tr><td colspan="8" class="muted">No learning activity matches these filters.</td></tr>'}</tbody></table></div>${activityPager(d,'actv-page')}`;
  return filters+stats+`<div class="dash-grid"><div class="dash-main">${panel('Activity records',table)}</div><div class="dash-side">${panel('Latest activity',d.items.length?activityTimeline(d.items.slice(0,8),true):'<p class="muted">Nothing recorded for these filters.</p>')}</div></div>`;
}
function employeeActivityView(){
  const query={...actv.employeeFilters,page:actv.employeePage},key=`actv-emp:${actv.employee}:${qs(query)}`,entry=loadData(key,`manage/activity/employees/${encodeURIComponent(actv.employee)}`+qs(query));
  const back='<button class="btn secondary" data-act="actv-back">Back to all activity</button>';
  if(!entry.data)return `<div class="admin-actions">${back}</div>`+stateBlock(entry,'employee activity',key);
  const d=entry.data,e=d.employee;
  return `<section class="panel activity-person"><div><span class="tag">EMPLOYEE HISTORY</span><h2>${esc(e.name)}</h2><p class="muted">${[e.employeeNumber,e.department,e.jobRole].filter(Boolean).map(esc).join(' · ')||'No department or job role recorded'}</p></div>${back}</section>`+timelineFilters('actv-emp-filters',d,actv.employeeFilters)+panel('Activity timeline',d.items.length?activityTimeline(d.items)+activityPager(d,'actv-emp-page'):emptyState('No activity recorded','Nothing matches these filters for this employee.'));
}

// ---------------------------------------------------------------- analytics

function miniTable(headers,rows,emptyText){
  return `<div class="admin-table-scroll"><table class="admin-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}" class="muted">${esc(emptyText)}</td></tr>`}</tbody></table></div>`;
}
function rateBar(value){return value==null?'—':`<div class="activity-progress"><div class="progress"><span style="width:${Math.min(100,value)}%"></span></div><small>${value}%</small></div>`;}
function activityAnalyticsView(){
  const a=actv.analytics,query={from:a.from,to:a.to,department:a.department,inactiveDays:a.inactiveDays},key='actv-analytics:'+qs(query),entry=loadData(key,'manage/activity/analytics'+qs(query));
  const d=entry.data,period=d?.period||{},o=d?.options||actvOptions;
  const form=`<form class="report-filters panel activity-filters" data-form="actv-analytics"><div><label for="ana-from">From</label><input id="ana-from" type="date" name="from" value="${esc(a.from||period.from||'')}"></div><div><label for="ana-to">To</label><input id="ana-to" type="date" name="to" value="${esc(a.to||period.to||'')}"></div>${o?`<div><label for="ana-department">Department</label><select id="ana-department" name="department">${options(o.departments.map(x=>[x.id,x.name]),a.department,'All departments')}</select></div>`:''}<div><label for="ana-inactive">No activity for</label><select id="ana-inactive" name="inactiveDays">${options([[14,'14 days'],[30,'30 days'],[60,'60 days'],[90,'90 days']],a.inactiveDays||period.inactiveDays||30)}</select></div><div class="filter-actions"><button class="btn" type="submit">Update</button><button class="btn secondary" type="button" data-act="actv-analytics-reset">Last 90 days</button></div></form>`;
  if(!d)return form+stateBlock(entry,'activity analytics',key);
  const defs=d.definitions,max=Math.max(1,...d.completionsByWeekday);
  const weekdays=`<div class="weekday-bars" role="img" aria-label="Lesson completions by weekday">${d.completionsByWeekday.map((n,i)=>`<div><span style="height:${Math.round(n/max*100)}%" title="${n}"></span><b>${n}</b><small>${WEEKDAYS[i]}</small></div>`).join('')}</div>`;
  const period_=`<p class="muted">Period: <b>${esc(fmtDate(period.from))}</b> to <b>${esc(fmtDate(period.to))}</b> (UTC days, both included).</p>`;
  return form+period_+`<div class="activity-analytics">
  ${panel('Most accessed courses',miniTable(['Course','Learners','Visits'],d.mostAccessed.map(c=>[esc(c.course),c.learners,c.visits]),'No course was opened in this period.')+`<p class="muted">${esc(defs.access)}</p>`)}
  ${panel('Most completed courses',miniTable(['Course','Learners completed'],d.mostCompleted.map(c=>[esc(c.course),c.learners]),'No course was completed in this period.'))}
  ${panel('Courses with high abandonment',miniTable(['Course','Started','Completed','In progress','Abandoned','Rate'],d.abandonment.map(c=>[esc(c.course),c.started,c.completed,c.inProgress,c.abandoned,rateBar(c.rate)]),'No course was started in this period.')+`<p class="muted">${esc(defs.abandonment)}</p>`)}
  ${panel('Lesson completion patterns',miniTable(['Course','Lesson','Learners started','Learners completed','Completion'],d.lessonPatterns.map(l=>[esc(l.course),esc(l.lesson),l.started,l.completed,rateBar(l.rate)]),'No lesson activity in this period.')+`<h3 class="sub-heading">Lesson completions by weekday (UTC)</h3>`+weekdays)}
  ${panel('Assessment attempt rates',miniTable(['Course','Learners accessed','Learners attempted','Attempt rate'],d.attemptRates.map(c=>[esc(c.course),c.accessed,c.attempted,rateBar(c.rate)]),'No course was accessed in this period.')+`<p class="muted">${esc(defs.attemptRate)}</p>`)}
  ${panel('Assessment pass and failure rates',miniTable(['Assessment','Type','Course','Passed','Failed','Pass rate'],d.assessmentResults.map(r=>[esc(r.assessment),esc(r.kind),esc(r.course),r.passed,r.failed,rateBar(r.passRate)]),'No assessment was submitted in this period.')+`<p class="muted">${esc(defs.passRate)}</p>`)}
  ${panel(`No learning activity for ${period.inactiveDays} days`,`<p class="muted"><b>${d.inactiveTotal}</b> active employee${d.inactiveTotal===1?'':'s'} with no recorded activity in the last ${period.inactiveDays} days. This is a prompt for a supportive conversation, not a performance measure.</p>`+miniTable(['Employee','Department','Last activity'],d.inactive.map(p=>[`<button class="link-button" data-act="actv-employee" data-id="${esc(p.employeeId)}">${esc(p.employee)}</button>`,esc(p.department||'—'),p.lastActivity?esc(fmtDate(p.lastActivity)):'Never']),'Everyone has recent learning activity.'))}
  ${panel('Department engagement',miniTable(['Department','Employees','Active learners','Engagement','Lessons completed','Courses completed','Assessments submitted'],d.departments.map(r=>[esc(r.department),r.employees,r.activeLearners,rateBar(r.engagementRate),r.lessonsCompleted,r.coursesCompleted,r.assessmentsSubmitted]),'No employees in scope.')+`<p class="muted">${esc(defs.engagement)}</p>`)}
  </div>`;
}

// ---------------------------------------------------------------- interactions

const nonEmpty=values=>Object.fromEntries(Object.entries(values).filter(([,v])=>v!==''&&v!=null));
Object.assign(ACTIONS,{
  'history-page':el=>{myHistory.page=Number(el.dataset.page);render();},
  'history-filters-reset':()=>{myHistory={filters:{},page:1};render();},
  'actv-tab':el=>{actv.tab=el.dataset.tab;actv.employee=null;render();},
  'actv-page':el=>{actv.page=Number(el.dataset.page);render();},
  'actv-reset':()=>{actv.filters={};actv.page=1;render();},
  'actv-employee':el=>{actv.employee=el.dataset.id;actv.employeeFilters={};actv.employeePage=1;render();window.scrollTo?.(0,0);},
  'actv-back':()=>{actv.employee=null;render();},
  'actv-emp-page':el=>{actv.employeePage=Number(el.dataset.page);render();},
  'actv-emp-filters-reset':()=>{actv.employeeFilters={};actv.employeePage=1;render();},
  'actv-analytics-reset':()=>{actv.analytics={};render();},
});
Object.assign(SUBMITS,{
  'history-filters':form=>{myHistory={filters:nonEmpty(formValues(form)),page:1};render();},
  'actv-filters':form=>{actv.filters=nonEmpty(formValues(form));actv.page=1;render();},
  'actv-emp-filters':form=>{actv.employeeFilters=nonEmpty(formValues(form));actv.employeePage=1;render();},
  'actv-analytics':form=>{actv.analytics=nonEmpty(formValues(form));render();},
});
// Opening a course learning material is recorded by the server; the link itself opens normally.
document.addEventListener('click',event=>{
  const link=event.target.closest?.('[data-resource-open]');
  if(link&&currentUser)api(`me/resources/${encodeURIComponent(link.dataset.resourceOpen)}/open`,{}).catch(()=>{});
});
