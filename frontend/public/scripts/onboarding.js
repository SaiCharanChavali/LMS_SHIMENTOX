// Automatic employee onboarding: the employee's plan, HR and manager monitoring, and onboarding templates.
// Every figure comes from /api/me/onboarding and /api/manage/onboarding; the server enforces who sees what.

const ONB_TONES={completed:'success',overdue:'danger',in_progress:'',not_started:'gray',no_courses:'gray'};
const ONB_STATUS_OPTIONS=[['not_started','Not started'],['in_progress','In progress'],['overdue','Overdue'],['completed','Completed']];
const ONB_TEMPLATE_TONES={active:'success',draft:'gray',inactive:'warn',archived:'gray'};
const ONB_PRESET_DAYS=[[1,'Day 1'],[7,'Day 7'],[30,'Day 30'],[60,'Day 60'],[90,'Day 90']];
const onbDefaults=()=>({tab:'overview',filters:{},pages:{page:1,waitingPage:1},open:null,draft:null,status:''});
let onb=onbDefaults();

// ---------------------------------------------------------------- the employee's plan (My Learning and My Dashboard)

function onbCourseStatus(c){
  if(c.status==='skipped'||c.status==='removed')return compliancePill(c.statusLabel,'gray');
  return compliancePill(c.statusLabel,c.status==='completed_late'?'warn':DEADLINE_TONES[c.status]||'')+(c.dueSoon?compliancePill('Due Soon','due-soon'):'');
}
function onbMilestones(v){
  return `<ol class="onb-milestones">${v.milestones.map(m=>`<li class="onb-milestone ${m.state}"><span class="onb-dot" aria-hidden="true">${m.state==='completed'?'✓':''}</span><div><strong>${esc(m.title)}</strong><small>${esc(fmtDate(m.date))}</small><small>${m.mandatoryTotal?`${m.mandatoryDone} of ${m.mandatoryTotal} mandatory`:'Optional only'}</small></div>${m.state==='overdue'?compliancePill('Overdue','danger'):m.state==='completed'?compliancePill('Done','success'):''}</li>`).join('')}</ol>`;
}
function onbCourseList(v,canOpen){
  const groups=v.milestones.map(m=>[m,v.courses.filter(c=>c.day===m.day)]);
  return groups.map(([m,list])=>`<div class="onb-group"><h4>${esc(m.title)} <small>by ${esc(m.deadlineDisplay)}</small></h4>${list.map(c=>`<div class="onb-course"><div class="onb-course-main"><strong>${esc(c.title)}</strong><small>${c.mandatory?compliancePill('Mandatory','warn'):compliancePill('Optional','gray')} ${c.deadlineDisplay?`Due ${esc(c.deadlineDisplay)}`:c.mandatory?'':'No deadline'}${c.link==='existing'?' · Already assigned to you':''}${c.note&&c.link==='skipped'?` · ${esc(c.note)}`:''}</small>${c.assessment?`<small>Assessment: ${esc(c.assessment.label)}${c.assessment.passed?' · Passed':''}</small>`:''}</div><div class="onb-course-state">${onbCourseStatus(c)}${meter(c.progress,'Progress')}</div>${canOpen&&!['skipped','removed'].includes(c.status)?`<button class="btn secondary onb-open" data-open-course="${esc(c.courseId)}">${c.completed?'Review':c.progress?'Continue':'Start'}</button>`:''}</div>`).join('')}</div>`).join('');
}
function onbPlanSummary(v){
  const next=v.nextMilestone;
  return `<div class="onb-summary"><div class="onb-percent"><strong>${v.percent}%</strong><span>onboarding complete</span>${meter(v.percent,'Onboarding completion')}<small>${v.mandatoryDone} of ${v.mandatoryTotal} mandatory courses${v.optionalTotal?` · ${v.optionalDone} of ${v.optionalTotal} optional`:''}</small></div><div class="onb-facts"><div><small>Status</small>${compliancePill(v.statusLabel,ONB_TONES[v.status])}</div><div><small>Started</small><b>${esc(fmtDate(v.startDate))}</b></div><div><small>${v.status==='completed'?'Completed':'Next milestone'}</small><b>${v.status==='completed'?esc(v.completedDisplay||''):next?`${esc(next.title)} · ${esc(fmtDate(next.date))}`:'—'}</b></div>${v.overdueMandatory?`<div><small>Overdue</small><b class="onb-overdue">${v.overdueMandatory} mandatory</b></div>`:''}</div></div>`;
}
// Shown at the top of My Learning and on My Dashboard when the employee has onboarding; nothing while loading or without one.
function onboardingSection(compact){
  if(!currentUser||currentUser.role==='admin')return '';
  const entry=loadData('me-onboarding','me/onboarding'),v=entry.data?.onboarding;
  if(!v)return '';
  const body=onbPlanSummary(v)+onbMilestones(v)+(compact?'':`<details class="onb-details" ${v.status!=='completed'?'open':''}><summary>Onboarding courses (${v.courses.length})</summary>${onbCourseList(v,true)}</details>`);
  return `<section class="panel onb-panel"><div class="section-heading"><h2>Your onboarding: ${esc(v.template)}</h2>${compact?'<a href="#courses">Open in My Learning &rarr;</a>':''}</div>${body}<p class="muted">Onboarding is complete when every mandatory course is complete. Optional courses are shown separately.</p></section>`;
}

// ---------------------------------------------------------------- HR and manager monitoring

function onbQuery(){return {...onb.filters,...onb.pages};}
function onbFilters(o){
  const f=onb.filters,select=(name,label,items,blank)=>`<div><label for="onb-${name}">${label}</label><select id="onb-${name}" name="${name}">${options(items,f[name],blank)}</select></div>`;
  return `<form class="compliance-filters panel" data-form="onb-filters"><div class="filters-head"><h2>${icon('filter')} Filters</h2><div class="filter-actions"><button class="btn secondary" type="button" data-act="onb-reset">Reset</button><button class="btn" type="submit">Apply Filters</button></div></div><div class="filters-grid onb-filters"><div><label for="onb-q">Search employee</label><input id="onb-q" name="q" type="search" maxlength="100" placeholder="Name or email" value="${esc(f.q||'')}"></div>${select('department','Department',o.departments,'All departments')}${select('jobRole','Job role',o.jobRoles,'All job roles')}${select('status','Onboarding status',ONB_STATUS_OPTIONS,'All statuses')}<div class="filter-range"><span class="field-label" id="onb-range">Joining date</span><div role="group" aria-labelledby="onb-range"><input type="date" name="from" aria-label="Joined from" value="${esc(f.from||'')}"><span aria-hidden="true">–</span><input type="date" name="to" aria-label="Joined to" value="${esc(f.to||'')}"></div></div></div></form>`;
}
function onbKpis(s){
  const card=(name,value,label,tone='')=>`<div class="stat compliance-kpi ${tone}"><div class="stat-icon">${icon(name)}</div><div class="kpi-body"><strong>${esc(value)}</strong><small>${esc(label)}</small></div></div>`;
  return `<div class="compliance-kpis onb-kpis">${card('path',s.onboarding,'Currently onboarding')}${card('check',s.completed,'Completed onboarding')}${card('file',s.pendingEmployees,'With pending courses')}${card('bell',s.overdueMandatory,'Overdue mandatory courses',s.overdueMandatory?'alert':'')}${card('chart',s.averagePercent+'%','Average completion')}</div>`;
}
function onbGroupTable(title,rows){
  return panel(title,rows.length?`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>${title.includes('job')?'Job role':'Department'}</th><th>Employees</th><th>Completed</th><th>Overdue</th><th>Average completion</th></tr></thead><tbody>${rows.map(g=>`<tr><td><strong>${esc(g.name)}</strong></td><td>${g.employees}</td><td>${g.completed}</td><td>${g.overdue?compliancePill(String(g.overdue),'danger'):'0'}</td><td>${meter(g.averagePercent,g.name)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="muted">No onboarding matches these filters.</p>');
}
function onbDetailRow(id,colspan){
  const entry=loadData('onb-detail:'+id,'manage/onboarding/'+encodeURIComponent(id));
  if(!entry.data)return `<tr class="record-details"><td colspan="${colspan}">${stateBlock(entry,'onboarding details','onb-detail:'+id)}</td></tr>`;
  const v=entry.data.onboarding;
  return `<tr class="record-details"><td colspan="${colspan}"><p class="muted">${esc(v.email)} · ${esc(v.department)} · ${esc(v.jobRole)}${v.manager?` · Manager: ${esc(v.manager)}`:''} · ${v.source==='automatic'?'Started automatically':'Started by HR'} on ${esc(fmtDate(v.startedAt))}</p>${onbPlanSummary(v)}${onbMilestones(v)}${onbCourseList(v,false)}${can('onboarding.manage')?`<div class="admin-actions"><button class="btn secondary" data-act="onb-cancel" data-id="${esc(v.id)}" data-name="${esc(v.employee)}">Cancel onboarding</button></div>`:''}</td></tr>`;
}
function onbPager(t,field){return t.pages>1?`<span class="table-actions"><button data-act="onb-page" data-field="${field}" data-page="${t.page-1}" ${t.page<=1?'disabled':''}>Previous</button><button data-act="onb-page" data-field="${field}" data-page="${t.page+1}" ${t.page>=t.pages?'disabled':''}>Next</button></span>`:'';}
function onbEmployeeTable(t){
  if(!t.total)return panel('Employees onboarding',emptyState('No onboarding matches these filters','Change the filters, or start onboarding from the Needs onboarding tab.'));
  const row=r=>{const open=onb.open===r.onboardingId;return `<tr><td><strong>${esc(r.employee)}</strong><small>${esc(r.email)}</small></td><td>${esc(r.department)}<small>${esc(r.jobRole)}</small></td><td>${esc(r.template)}</td><td>${r.joiningDate?esc(fmtDate(r.joiningDate)):'—'}<small>Start ${esc(fmtDate(r.startDate))}</small></td><td>${meter(r.percent,'Completion')}<small>${r.mandatoryDone} of ${r.mandatoryTotal} mandatory${r.optionalTotal?` · ${r.optionalDone}/${r.optionalTotal} optional`:''}</small></td><td>${compliancePill(r.statusLabel,ONB_TONES[r.status])}${r.overdueMandatory?`<small>${r.overdueMandatory} overdue</small>`:''}</td><td>${r.nextMilestone?`${esc(r.nextMilestone.title)}<small>${esc(fmtDate(r.nextMilestone.date))}</small>`:r.completedAt?`Completed<small>${esc(fmtDate(r.completedAt))}</small>`:'—'}</td><td><button class="icon-action" data-act="onb-open" data-id="${esc(r.onboardingId)}" aria-expanded="${open}" aria-label="View onboarding for ${esc(r.employee)}" title="View details">${icon('eye')}</button></td></tr>${open?onbDetailRow(r.onboardingId,8):''}`;};
  return panel('Employees onboarding',`<div class="admin-table-scroll"><table class="admin-table onb-table"><thead><tr><th>Employee</th><th>Department / job role</th><th>Template</th><th>Joined</th><th>Completion</th><th>Status</th><th>Next milestone</th><th>Details</th></tr></thead><tbody>${t.rows.map(row).join('')}</tbody></table></div><div class="pager"><span class="muted">${t.total} employee${t.total===1?'':'s'} · page ${t.page} of ${t.pages}</span>${onbPager(t,'page')}</div>`,complianceExportMenu('Export',false).replace(/compliance-export/g,'onb-export'));
}
function onbWaiting(d){
  const t=d.needsOnboarding,templates=d.templates;
  const reason=r=>r.template?`Matches <b>${esc(r.template)}</b>`:r.reason==='ambiguous'?'More than one template matches: choose one':'No matching template: create one, or choose one';
  const row=r=>`<tr><td><strong>${esc(r.employee)}</strong><small>${esc(r.email)}</small></td><td>${esc(r.department)}<small>${esc(r.jobRole)}</small></td><td>${r.joiningDate?esc(fmtDate(r.joiningDate)):'Not recorded'}</td><td><small class="onb-reason">${reason(r)}</small></td><td><form class="onb-start" data-form="onb-start" data-employee="${esc(r.employeeId)}"><select name="templateId" aria-label="Template for ${esc(r.employee)}" required>${options(templates,r.templateId||'','Choose a template')}</select><input type="date" name="startDate" aria-label="Start date for ${esc(r.employee)}" value="${esc(r.defaultStartDate)}" required><button class="btn" type="submit" ${templates.length?'':'disabled'}>Start</button><p class="form-status" role="status"></p></form></td></tr>`;
  const body=t.total?`<div class="admin-table-scroll"><table class="admin-table onb-table"><thead><tr><th>Employee</th><th>Department / job role</th><th>Joined</th><th>Template</th><th>Start onboarding</th></tr></thead><tbody>${t.rows.map(row).join('')}</tbody></table></div><div class="pager"><span class="muted">${t.total} employee${t.total===1?'':'s'} without onboarding</span>${onbPager(t,'waitingPage')}</div>`:emptyState('Everyone has onboarding','Active employees matching these filters all have onboarding in progress or completed.');
  return panel('Employees without onboarding',`${templates.length?'':'<div class="notice" role="status">There are no active onboarding templates. Create and activate one in the Templates tab first.</div>'}${body}<p class="muted">Milestones count from the start date. The start date defaults to the joining date, or today when the joining date has passed.</p>`);
}

// ---------------------------------------------------------------- templates

function onbTemplateCard(t){
  const action=(status,label)=>`<button data-act="onb-template-status" data-id="${esc(t.id)}" data-status="${status}">${label}</button>`;
  const actions={draft:[['active','Activate'],['archived','Archive']],active:[['inactive','Deactivate'],['archived','Archive']],inactive:[['active','Activate'],['archived','Archive']],archived:[['inactive','Restore']]}[t.status].map(([s,l])=>action(s,l)).join('');
  return `<article class="onb-template"><div class="section-heading"><div><h3>${esc(t.name)}</h3><small>${esc(t.department)} · ${t.jobRoles.length?esc(t.jobRoles.join(', ')):'All job roles'}</small></div>${tagText(t.status,ONB_TEMPLATE_TONES[t.status])}</div>${t.description?`<p class="muted">${esc(t.description)}</p>`:''}<p class="onb-template-meta">${t.courses.length} course${t.courses.length===1?'':'s'} (${t.mandatoryCount} mandatory) · ${t.milestones.map(m=>esc(m.title)).join(', ')}</p><p class="muted">${t.onboardingsActive} onboarding now · ${t.onboardingsTotal} started in total · updated ${esc(fmtDate(t.updatedAt))}${t.updatedBy?` by ${esc(t.updatedBy)}`:''}</p>${t.warnings.map(w=>`<p class="notice">${esc(w)}</p>`).join('')}<div class="table-actions">${t.status!=='archived'?`<button data-act="onb-template-edit" data-id="${esc(t.id)}">Edit</button>`:''}${actions}</div></article>`;
}
function onbNewDraft(){return {id:null,name:'',description:'',departmentId:'',jobRoleIds:[],status:'draft',milestones:ONB_PRESET_DAYS.slice(0,3).map(([day,title])=>({day,title})),courses:[{courseId:'',day:1,mandatory:true}]};}
function onbEditor(o){
  const d=onb.draft,days=d.milestones.map(m=>[m.day,m.title||`Day ${m.day}`]);
  const milestones=d.milestones.map((m,i)=>`<div class="onb-row"><label>Day<input type="number" min="1" max="365" value="${esc(m.day)}" data-onb="milestone-day" data-index="${i}" required></label><label>Name<input maxlength="80" value="${esc(m.title)}" placeholder="Day ${esc(m.day)}" data-onb="milestone-title" data-index="${i}"></label><button type="button" class="auth-link" data-act="onb-milestone-remove" data-index="${i}" ${d.milestones.length<2?'disabled':''}>Remove</button></div>`).join('');
  const courses=d.courses.map((c,i)=>`<div class="onb-row onb-course-row"><label>Course<select data-onb="course" data-index="${i}" required>${options(o.courses,c.courseId,'Select a published course…')}</select></label><label>Milestone<select data-onb="course-day" data-index="${i}">${options(days,c.day)}</select></label><label class="check-label"><input type="checkbox" data-onb="course-mandatory" data-index="${i}" ${c.mandatory?'checked':''}> Mandatory</label><button type="button" class="auth-link" data-act="onb-course-remove" data-index="${i}" ${d.courses.length<2?'disabled':''}>Remove</button></div>`).join('');
  const roles=o.jobRoles.length?o.jobRoles.map(([id,name])=>`<label class="check-label onb-role"><input type="checkbox" data-onb="role" value="${esc(id)}" ${d.jobRoleIds.includes(id)?'checked':''}> ${esc(name)}</label>`).join(''):'<p class="muted">No job roles yet. Add them in Users &amp; Teams → Organisation.</p>';
  return panel(d.id?'Edit onboarding template':'New onboarding template',`<form class="admin-form onb-editor" data-form="onb-template"><div class="editor-fields"><div><label for="onb-name">Template name</label><input id="onb-name" data-onb="name" value="${esc(d.name)}" minlength="2" maxlength="120" required></div><div><label for="onb-department">Department</label><select id="onb-department" data-onb="department">${options(o.departments,d.departmentId,'All departments')}</select></div></div><label for="onb-description">Description</label><textarea id="onb-description" data-onb="description" rows="2" maxlength="1000">${esc(d.description)}</textarea><span class="field-label">Job roles <small class="muted">(none selected = every job role in the department)</small></span><div class="onb-roles">${roles}</div><h3 class="sub-heading">Milestones</h3>${milestones}<div class="admin-actions"><button type="button" class="btn secondary" data-act="onb-milestone-add">+ Add milestone</button><button type="button" class="auth-link" data-act="onb-milestone-presets">Use Day 1, 7, 30, 60 and 90</button></div><h3 class="sub-heading">Courses</h3><p class="muted">Each course is due at the end of its milestone day, counted from the employee's joining date (Day 1 is the joining date). Optional courses have no deadline.</p>${courses}<button type="button" class="btn secondary" data-act="onb-course-add">+ Add course</button><div class="admin-actions onb-editor-actions"><button class="btn" type="submit" data-status="${d.id?'':'active'}">${d.id?'Save template':'Save and activate'}</button>${d.id?'':'<button class="btn secondary" type="submit" data-status="draft">Save as draft</button>'}<button class="btn secondary" type="button" data-act="onb-template-cancel">Cancel</button></div><p class="form-status" role="status"></p></form>`);
}
function onbTemplatesTab(){
  const entry=loadData('onb-templates','manage/onboarding/templates');
  if(!entry.data)return stateBlock(entry,'onboarding templates','onb-templates');
  const d=entry.data;
  if(onb.draft)return onbEditor(d.options);
  const shown=d.templates.filter(t=>onb.status?t.status===onb.status:t.status!=='archived');
  const chips=[['','Current'],['active','Active'],['draft','Draft'],['inactive','Inactive'],['archived','Archived']].map(([v,l])=>`<button class="${onb.status===v?'active':''}" data-act="onb-template-filter" data-value="${v}" aria-pressed="${onb.status===v}">${l}</button>`).join('');
  return `<div class="admin-actions onb-template-bar"><div class="segmented" role="group" aria-label="Template status">${chips}</div><button class="btn" data-act="onb-template-new">+ New template</button></div><p class="muted">When HR adds an employee, the most specific active template applies: one for their job role, then one for their department, then one for all departments. Editing a template never changes onboarding that has already started.</p>${shown.length?`<div class="onb-template-grid">${shown.map(onbTemplateCard).join('')}</div>`:emptyState('No templates here','Create a template with the published courses new employees should complete.')}`;
}

// ---------------------------------------------------------------- page

function onboardingPage(){
  const manage=can('onboarding.manage'),tabs=manage?[['overview','Overview'],['waiting','Needs onboarding'],['templates','Templates']]:[['overview','Overview']];
  if(!tabs.some(([id])=>id===onb.tab))onb.tab='overview';
  const head=`<div class="compliance-head"><div><h1>${manage?'Employee Onboarding':'Team Onboarding'}</h1><p>${manage?'Structured onboarding journeys assigned automatically from each new employee\'s department, job role and joining date.':'Onboarding progress for your direct reports.'}</p></div></div><div class="compliance-tabs" role="tablist" aria-label="Onboarding views">${tabs.map(([id,label])=>`<button role="tab" aria-selected="${onb.tab===id}" class="${onb.tab===id?'active':''}" data-act="onb-tab" data-tab="${id}">${esc(label)}</button>`).join('')}</div>${devNotice()}`;
  if(onb.tab==='templates')return `<div class="compliance-page">${head}${onbTemplatesTab()}</div>`;
  const key='onb:'+qs(onbQuery()),entry=loadData(key,'manage/onboarding'+qs(onbQuery()));
  if(!entry.data)return `<div class="compliance-page">${head}${stateBlock(entry,'onboarding',key)}</div>`;
  const d=entry.data,filters=onbFilters(d.options);
  if(onb.tab==='waiting')return `<div class="compliance-page">${head}${filters}${onbWaiting(d)}</div>`;
  return `<div class="compliance-page">${head}${filters}${onbKpis(d.summary)}<div class="compliance-pair">${onbGroupTable('Progress by department',d.departments)}${onbGroupTable('Progress by job role',d.jobRoles)}</div>${onbEmployeeTable(d.table)}</div>`;
}

async function onbExport(format){
  const response=await fetch('/api/manage/onboarding/export'+qs({...onb.filters,format}),{credentials:'same-origin',headers:{'X-Portal-Request':'1'}});
  if(!response.ok)throw new Error((await response.json().catch(()=>({}))).error||'The report could not be exported.');
  const link=document.createElement('a'),url=URL.createObjectURL(await response.blob());
  link.href=url;link.download=(/filename="([^"]+)"/.exec(response.headers.get('Content-Disposition')||'')||[])[1]||'shimentox-onboarding.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('Report exported.');
}
function onbRefresh(){refreshData('onb','onb-templates','onb-detail','me-onboarding');render();}
function onbFirstPage(){onb.pages={page:1,waitingPage:1};onb.open=null;render();}

Object.assign(ACTIONS,{
  'onb-tab':el=>{onb.tab=el.dataset.tab;onb.draft=null;render();},
  'onb-reset':()=>{onb.filters={};onbFirstPage();},
  'onb-page':el=>{onb.pages[el.dataset.field]=Number(el.dataset.page);render();},
  'onb-open':el=>{onb.open=onb.open===el.dataset.id?null:el.dataset.id;render();},
  'onb-export':el=>{const menu=el.closest('details');if(menu)menu.open=false;return onbExport(el.dataset.format);},
  'onb-cancel':async el=>{if(!confirm(`Cancel onboarding for ${el.dataset.name}? Their unfinished onboarding course assignments are removed; completed courses stay on record.`))return;const r=await api(`manage/onboarding/${encodeURIComponent(el.dataset.id)}/cancel`,{});onb.open=null;devMessage=r.message;onbRefresh();},
  'onb-template-filter':el=>{onb.status=el.dataset.value;render();},
  'onb-template-new':()=>{onb.draft=onbNewDraft();render();},
  'onb-template-edit':el=>{const t=pageCache['onb-templates']?.data?.templates.find(x=>x.id===el.dataset.id);if(!t)return;onb.draft={id:t.id,name:t.name,description:t.description,departmentId:t.departmentId||'',jobRoleIds:[...t.jobRoleIds],status:t.status,milestones:t.milestones.map(m=>({...m})),courses:t.courses.map(c=>({courseId:c.courseId,day:c.day,mandatory:c.mandatory}))};render();},
  'onb-template-cancel':()=>{onb.draft=null;render();},
  'onb-template-status':async el=>{const s=el.dataset.status;if(s==='archived'&&!confirm('Archive this template? It stops applying to new employees. Onboarding already started is not affected.'))return;await api(`manage/onboarding/templates/${encodeURIComponent(el.dataset.id)}/status`,{status:s});devMessage=`Template ${s==='active'?'activated':s==='inactive'?(el.textContent==='Restore'?'restored as inactive':'deactivated'):'archived'}.`;onbRefresh();},
  'onb-milestone-add':()=>{const used=new Set(onb.draft.milestones.map(m=>m.day)),day=[1,7,14,30,45,60,90,120,180].find(x=>!used.has(x))||Math.min(365,Math.max(...used)+1);onb.draft.milestones.push({day,title:''});onb.draft.milestones.sort((a,b)=>a.day-b.day);render();},
  'onb-milestone-remove':el=>{const m=onb.draft.milestones.splice(Number(el.dataset.index),1)[0];const first=onb.draft.milestones[0].day;onb.draft.courses.forEach(c=>{if(c.day===m.day)c.day=first;});render();},
  'onb-milestone-presets':()=>{const have=new Map(onb.draft.milestones.map(m=>[m.day,m]));ONB_PRESET_DAYS.forEach(([day,title])=>{if(!have.has(day))have.set(day,{day,title});});onb.draft.milestones=[...have.values()].sort((a,b)=>a.day-b.day);render();},
  'onb-course-add':()=>{onb.draft.courses.push({courseId:'',day:onb.draft.milestones[0].day,mandatory:true});render();},
  'onb-course-remove':el=>{onb.draft.courses.splice(Number(el.dataset.index),1);render();},
});
Object.assign(SUBMITS,{
  'onb-filters':form=>{onb.filters=Object.fromEntries(Object.entries(formValues(form)).filter(([,v])=>v));onbFirstPage();},
  'onb-start':form=>submitForm(form,async()=>{const v=formValues(form);const r=await api('manage/onboarding/start',{employeeId:form.dataset.employee,templateId:v.templateId,startDate:v.startDate});devMessage=r.message;onbRefresh();}),
  'onb-template':form=>submitForm(form,async()=>{const d=onb.draft,status=form.dataset.submitStatus||'';const payload={...(d.id?{id:d.id}:{status:status||'active'}),name:d.name,description:d.description,departmentId:d.departmentId||null,jobRoleIds:d.jobRoleIds,milestones:d.milestones.map(m=>({day:Number(m.day),title:m.title})),courses:d.courses.map(c=>({courseId:c.courseId,day:Number(c.day),mandatory:c.mandatory}))};await api('manage/onboarding/templates',payload);devMessage=d.id?'Template saved. Onboarding already started is not affected.':status==='draft'?'Template saved as a draft.':'Template saved and activated. It now applies to new employees who match it.';onb.draft=null;onbRefresh();}),
});
// The editor keeps its own draft so typing never waits for a re-render; only adding or removing rows redraws it.
document.addEventListener('input',event=>onbField(event.target,'input'));
document.addEventListener('change',event=>onbField(event.target,'change'));
// Remember which submit button was used: "Save and activate" or "Save as draft".
document.addEventListener('click',event=>{const b=event.target.closest?.('form[data-form="onb-template"] button[type="submit"]');if(b)b.form.dataset.submitStatus=b.dataset.status||'';});
function onbField(el,type){
  const kind=el?.dataset?.onb,d=onb.draft;if(!kind||!d)return;
  const i=Number(el.dataset.index);
  if(kind==='name')d.name=el.value;
  else if(kind==='description')d.description=el.value;
  else if(kind==='department')d.departmentId=el.value;
  else if(kind==='role'){d.jobRoleIds=d.jobRoleIds.filter(r=>r!==el.value);if(el.checked)d.jobRoleIds.push(el.value);}
  else if(kind==='milestone-title')d.milestones[i].title=el.value;
  else if(kind==='milestone-day'&&type==='change'){const old=d.milestones[i].day,day=Number(el.value);if(Number.isInteger(day)&&day>=1&&day<=365&&!d.milestones.some((m,j)=>j!==i&&m.day===day)){d.milestones[i].day=day;d.courses.forEach(c=>{if(c.day===old)c.day=day;});d.milestones.sort((a,b)=>a.day-b.day);render();}else{el.value=old;toast('Each milestone needs a different day from 1 to 365.');}}
  else if(kind==='course')d.courses[i].courseId=el.value;
  else if(kind==='course-day')d.courses[i].day=Number(el.value);
  else if(kind==='course-mandatory')d.courses[i].mandatory=el.checked;
}
