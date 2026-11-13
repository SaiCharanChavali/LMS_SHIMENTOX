// Live training and webinars: the Training Calendar for employees, and session tools for HR, administrators and trainers.
// Everything comes from /api/me/calendar and /api/manage/sessions. The server sends meeting links and recordings only to
// registered participants and staff, and enforces every permission; this file only decides what to show.
const SESSION_KINDS=[['session','Training session'],['workshop','Workshop'],['webinar','Webinar']];
const SESSION_DELIVERY=[['in_person','In person'],['online','Online'],['hybrid','Hybrid (room and online)']];
const MEETING_PLATFORMS=[['zoom','Zoom'],['meet','Google Meet'],['teams','Microsoft Teams'],['other','Other video platform']];
const SESSION_FILTERS=[['upcoming','Upcoming'],['past','Past'],['cancelled','Cancelled'],['all','All']];
let qaSessionId=null,qaTimer=null,feedbackReportId=null,sessionFilter='upcoming';
function resetLiveTraining(){stopQaPolling();qaSessionId=feedbackReportId=null;sessionFilter='upcoming';}
const timeOf=v=>new Date(v).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'});
const stars=n=>`<span class="stars" aria-label="${n} out of 5 stars">${'★'.repeat(Math.round(n))}${'☆'.repeat(5-Math.round(n))}</span>`;

function calendarPage(){
  const staff=can('sessions.manage');
  return intro('Training calendar','Live training sessions, workshops and webinars: register, join online, ask questions and share feedback.',staff?'SCHEDULE & REGISTER':'MY CALENDAR')
    +devNotice()+(qaSessionId?qaPanel():'')+(isLearner()?myCalendar():'')+(staff?manageSessions():'');
}

// ---------------------------------------------------------------- employee view: session cards

function sessionTags(s){
  const where=s.online?(s.delivery==='hybrid'?'Hybrid · ':'')+(s.providerLabel||'Online'):'In person';
  return `<span class="tag">${esc(s.kind.toUpperCase())}</span><span class="tag gray">${esc(where.toUpperCase())}</span>${s.live?'<span class="tag danger">LIVE NOW</span>':''}${s.status==='cancelled'?'<span class="tag danger">CANCELLED</span>':''}${s.myStatus==='registered'?'<span class="tag success">REGISTERED</span>':''}${s.myStatus==='attended'?'<span class="tag success">ATTENDED</span>':''}`;
}
function joinControl(s){
  if(!s.online||!s.meetingUrl||s.ended||s.status==='cancelled')return '';
  if(s.canJoin)return `<a class="btn" href="${esc(s.meetingUrl)}" target="_blank" rel="noopener">${icon('play')} Join on ${esc(s.providerLabel||'the meeting')}</a>`;
  const opens=new Date(s.joinOpensAt).toDateString()===new Date().toDateString()?timeOf(s.joinOpensAt):fmtDateTime(s.joinOpensAt);
  return `<button class="btn" type="button" disabled title="Joining opens 15 minutes before the session starts">Join opens ${esc(opens)}</button>`;
}
function calendarMenu(s){
  if(!s.calendarLinks||s.ended||s.status==='cancelled')return '';
  return `<details class="export-menu"><summary class="btn secondary">${icon('calendar')} Add to calendar</summary><div class="export-options"><a href="${esc(s.calendarLinks.google)}" target="_blank" rel="noopener">Google Calendar</a><a href="${esc(s.calendarLinks.outlook)}" target="_blank" rel="noopener">Outlook / Microsoft 365</a><button type="button" data-act="session-ics" data-id="${esc(s.id)}">Download .ics file</button></div></details>`;
}
function sessionFollowUps(s){
  const parts=[];
  if(s.recordingUrl)parts.push(`<a class="btn secondary" href="${esc(s.recordingUrl)}" target="_blank" rel="noopener">${icon('play')} Watch recording</a>`);
  if(s.assessment?.open)parts.push(s.assessment.passed?`<span class="tag success">${esc(s.assessment.title.toUpperCase())} PASSED</span>`:`<a class="btn secondary" href="#assessments">${icon('check')} Take the post-session assessment</a>`);
  return parts.join('');
}
function feedbackForm(s){
  if(!s.canGiveFeedback)return '';
  const f=s.myFeedback,choices=[5,4,3,2,1].map(n=>`<input type="radio" id="fb-${esc(s.id)}-${n}" name="rating" value="${n}" ${f?.rating===n?'checked':''} required><label for="fb-${esc(s.id)}-${n}" title="${n} star${n===1?'':'s'}">★</label>`).join('');
  return `<details class="session-feedback"><summary>${f?`Your rating ${stars(f.rating)} · Edit feedback`:'Rate this session'}</summary><form data-form="session-feedback" data-id="${esc(s.id)}"><fieldset class="star-rating"><legend>How useful was this session?</legend><div class="star-choices">${choices}</div></fieldset><label for="fb-comment-${esc(s.id)}">What worked well, and what could be better? (optional)</label><textarea id="fb-comment-${esc(s.id)}" name="comment" rows="2" maxlength="2000">${esc(f?.comment||'')}</textarea><button class="btn" type="submit">${f?'Update feedback':'Send feedback'}</button><p class="form-status" role="status"></p></form></details>`;
}
function sessionCard(s){
  const participant=['registered','attended'].includes(s.myStatus),full=s.seatsLeft<=0&&!participant;
  const register=s.ended||s.status==='cancelled'||s.myStatus==='attended'?'':s.myStatus==='registered'?(s.live?'':`<button class="btn secondary" data-act="session-cancel" data-id="${esc(s.id)}">Cancel registration</button>`)
    :s.live?'<span class="muted">Registration has closed.</span>':`<button class="btn" data-act="session-register" data-id="${esc(s.id)}" ${full?'disabled':''}>${full?'Session full':'Register'}</button>`;
  const qa=participant&&s.qaEnabled&&s.status!=='cancelled'?`<button class="btn secondary" data-act="qa-open" data-id="${esc(s.id)}">${s.qaOpen?(s.live?'Live Q&amp;A':'Ask a question'):'Q&amp;A answers'}</button>`:'';
  const date=new Date(s.startsAt);
  return `<article class="session-card ${s.live?'is-live':''}"><div class="session-date"><strong>${esc(date.toLocaleDateString('en-IN',{day:'numeric'}))}</strong><span>${esc(date.toLocaleDateString('en-IN',{month:'short'}).toUpperCase())}</span></div><div class="session-body"><div class="tile-tags">${sessionTags(s)}</div><h3>${esc(s.title)}</h3><p class="muted">${esc(fmtDateTime(s.startsAt))} – ${esc(timeOf(s.endsAt))}${s.location?' · '+esc(s.location):''}${s.trainer?' · Trainer: '+esc(s.trainer):''}</p>${s.description?`<p class="muted">${esc(s.description)}</p>`:''}${s.ended?'':`<p class="muted"><b>${s.seatsLeft}</b> of ${s.capacity} seats available${s.course?' · Linked course: '+esc(s.course):''}</p>`}${!s.meetingUrl&&s.online&&!s.ended&&s.status!=='cancelled'?`<p class="muted">The ${esc(s.providerLabel||'meeting')} link appears here once you register.</p>`:''}<div class="session-actions">${joinControl(s)}${register}${calendarMenu(s)}${qa}${sessionFollowUps(s)}</div>${feedbackForm(s)}</div></article>`;
}
function myCalendar(){
  const entry=loadData('me-cal','me/calendar');
  if(!entry.data)return stateBlock(entry,'training sessions','me-cal');
  const d=entry.data,registered=d.sessions.some(s=>s.myStatus==='registered');
  const download=registered?`<button class="btn secondary" data-act="calendar-ics">${icon('download')} Download my sessions (.ics)</button>`:'';
  return panel('Upcoming sessions',d.sessions.length?`<div class="session-list">${d.sessions.map(sessionCard).join('')}</div>`:emptyState('No sessions scheduled','Instructor-led sessions, workshops and webinars will appear here when they are scheduled.'),download)
    +(d.past.length?panel('Past sessions',`<p class="muted">Watch recordings, rate the sessions you took part in and take their post-session assessments.</p><div class="session-list">${d.past.map(sessionCard).join('')}</div>`):'');
}

// ---------------------------------------------------------------- live Q&A (participants and staff)

function qaPanel(){
  const key='qa:'+qaSessionId,entry=loadData(key,`me/sessions/${qaSessionId}/questions`);
  if(!entry.data)return stateBlock(entry,'questions',key);
  const d=entry.data;startQaPolling();
  const ask=d.open?`<form class="qa-ask" data-form="qa-ask"><label for="qa-body">Your question</label><textarea id="qa-body" name="body" rows="2" minlength="2" maxlength="500" required placeholder="Ask the trainer something about this session"></textarea><div class="admin-actions"><label class="check-label"><input type="checkbox" name="anonymous"> Ask anonymously (the trainer still sees your name)</label><button class="btn" type="submit">Ask question</button></div><p class="form-status" role="status"></p></form>`:'<p class="muted">Questions for this session have closed. Answers stay here.</p>';
  return `<section class="panel qa-panel" id="qa-panel"><div class="section-heading"><div><span class="tag ${d.session.live?'danger':''}">${d.session.live?'LIVE Q&amp;A':'Q&amp;A'}</span><h2>${esc(d.session.title)}</h2></div><button class="btn secondary" data-act="qa-close">Close</button></div>${ask}<div id="qa-list">${qaList(d)}</div><p class="muted">The list refreshes every 10 seconds. ${d.canModerate?'Write an answer, mark a question answered once you cover it live, or dismiss it.':'Upvote the questions you most want answered.'}</p></section>`;
}
function qaList(d){
  if(!d.questions.length)return emptyState('No questions yet','Questions asked before or during the session appear here, most upvoted first.');
  const tone={open:'',answered:'success',dismissed:'gray'};
  return `<ol class="qa-list">${d.questions.map(q=>`<li class="qa-item ${q.status}"><button class="qa-vote ${q.voted?'voted':''}" data-act="qa-vote" data-id="${esc(q.id)}" ${q.status!=='open'&&!q.voted?'disabled':''} aria-pressed="${q.voted}" aria-label="${q.voted?'Remove upvote':'Upvote'}: ${q.votes} vote${q.votes===1?'':'s'}">▲<b>${q.votes}</b></button><div class="qa-body"><p>${esc(q.body)}</p><small>${esc(q.asker)}${q.mine?' (you)':''} · ${esc(fmtDateTime(q.createdAt))} ${tagText(q.status,tone[q.status])}</small>${q.status==='answered'?`<div class="qa-answer"><strong>${esc(q.answeredBy||'Trainer')}</strong> ${q.answer?esc(q.answer):'<span class="muted">Answered live in the session.</span>'}</div>`:''}${d.canModerate?`<form class="qa-moderate" data-form="qa-answer" data-id="${esc(q.id)}"><label class="visually-hidden" for="qa-a-${esc(q.id)}">Answer</label><textarea id="qa-a-${esc(q.id)}" name="answer" rows="1" maxlength="2000" placeholder="Written answer (optional if you answer live)">${esc(q.answer||'')}</textarea><div class="table-actions"><button type="submit">${q.status==='answered'?'Update answer':'Mark answered'}</button>${q.status==='dismissed'?`<button type="button" data-act="qa-status" data-id="${esc(q.id)}" data-status="open">Reopen</button>`:`<button type="button" data-act="qa-status" data-id="${esc(q.id)}" data-status="dismissed">Dismiss</button>`}</div></form>`:''}</div></li>`).join('')}</ol>`;
}
// Only the list is redrawn, so a question or answer being typed is never lost.
function startQaPolling(){
  if(qaTimer)return;
  qaTimer=setInterval(async()=>{
    if(!qaSessionId||location.hash!=='#calendar'){stopQaPolling();return;}
    if(document.hidden||document.activeElement?.closest?.('#qa-list'))return;
    try{const data=await api(`me/sessions/${qaSessionId}/questions`);pageCache['qa:'+qaSessionId]={data};const list=document.getElementById('qa-list');if(list)list.innerHTML=qaList(data);}catch{/* The next poll tries again. */}
  },10000);
}
function stopQaPolling(){if(qaTimer)clearInterval(qaTimer);qaTimer=null;}

// ---------------------------------------------------------------- staff: sessions, roster, feedback and trainers

function sessionEngagement(s){
  return `${s.averageRating!=null?`${stars(s.averageRating)} ${s.averageRating}<small>${s.feedbackCount} rating${s.feedbackCount===1?'':'s'}</small>`:'<span class="muted">No ratings</span>'}${s.qaEnabled&&s.openQuestions?`<small>${s.openQuestions} open question${s.openQuestions===1?'':'s'}</small>`:''}`;
}
function manageSessions(){
  const entry=loadData('m-sessions','manage/sessions');
  if(!entry.data)return stateBlock(entry,'scheduled sessions','m-sessions');
  const sessions=entry.data.sessions;
  const match={upcoming:s=>s.status==='scheduled'&&!s.ended,past:s=>s.status==='scheduled'&&s.ended,cancelled:s=>s.status==='cancelled',all:()=>true};
  const shown=sessions.filter(match[sessionFilter]);if(sessionFilter==='past')shown.reverse();
  const chips=`<div class="status-chips" role="group" aria-label="Filter sessions">${SESSION_FILTERS.map(([v,label])=>`<button type="button" class="${sessionFilter===v?'active':''}" data-act="session-filter" data-value="${v}" aria-pressed="${sessionFilter===v}">${label} <span>${sessions.filter(match[v]).length}</span></button>`).join('')}</div>`;
  const row=s=>`<tr><td><strong>${esc(s.title)}</strong><small>${esc(capital(s.kind))} · ${esc(s.online?(s.delivery==='hybrid'?'Hybrid · ':'')+s.providerLabel:'In person')}${s.trainer?' · '+esc(s.trainer):' · No trainer'}${s.location?' · '+esc(s.location):''}</small>${s.recordingUrl?'<small>Recording added</small>':''}${s.assessment?`<small>Assessment: ${esc(s.assessment.title)}</small>`:''}</td><td>${esc(fmtDateTime(s.startsAt))}<small>to ${esc(timeOf(s.endsAt))}</small>${s.live?'<span class="tag danger">LIVE</span>':''}</td><td>${s.registered}/${s.capacity}<small>${s.attended} attended</small></td><td>${sessionEngagement(s)}</td><td>${tagText(s.status,s.status==='cancelled'?'danger':'')}</td><td><div class="table-actions">${s.canEdit?`<button data-act="session-edit" data-id="${esc(s.id)}">Edit</button>`:''}<button data-act="session-roster" data-id="${esc(s.id)}">Registrations</button>${s.qaEnabled?`<button data-act="qa-open" data-id="${esc(s.id)}">Q&amp;A${s.openQuestions?` (${s.openQuestions})`:''}</button>`:''}${s.canEdit&&s.feedbackEnabled?`<button data-act="session-feedback-report" data-id="${esc(s.id)}">Feedback</button>`:''}${s.canEdit&&s.online&&s.meetingUrl&&!s.ended&&s.status==='scheduled'?`<a class="tag" href="${esc(s.meetingUrl)}" target="_blank" rel="noopener">START</a>`:''}</div></td></tr>`;
  const table=`${chips}<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Session</th><th>When</th><th>Seats</th><th>Feedback &amp; Q&amp;A</th><th>Status</th><th>Actions</th></tr></thead><tbody>${shown.map(row).join('')||`<tr><td colspan="6" class="muted">${sessions.length?'No sessions in this view.':'No sessions scheduled yet.'}</td></tr>`}</tbody></table></div>`;
  const editing=sessionEditor?sessionForm(sessionEditor):'';
  const roster=sessionRoster?rosterPanel(sessions.find(x=>x.id===sessionRoster)):'';
  const feedback=feedbackReportId?feedbackPanel(sessions.find(x=>x.id===feedbackReportId)):'';
  return panel('Manage sessions',table,'<button class="btn" data-act="session-new">Schedule session</button>')+editing+roster+feedback+trainersPanel();
}
function sessionForm(s){
  const org=orgData(),assessments=(loadData('m-assess','manage/assessments').data?.assessments||[]).filter(a=>a.status==='published'||a.id===s.assessmentId);
  const field=(id,label,control,hint='')=>`<div><label for="${id}">${label}</label>${control}${hint?`<small class="muted">${hint}</small>`:''}</div>`;
  const check=(name,label,on)=>`<label class="check-label"><input type="checkbox" name="${name}" ${on?'checked':''}> ${label}</label>`;
  return `<section class="panel admin-form"><span class="tag">${s.id?'EDIT SESSION':'NEW SESSION'}</span><h2>${s.id?'Edit session':'Schedule a session'}</h2><form data-form="session-save" data-id="${esc(s.id||'')}">
  <label for="session-title">Title</label><input id="session-title" name="title" value="${esc(s.title||'')}" minlength="2" maxlength="150" required>
  <label for="session-description">Description</label><textarea id="session-description" name="description" rows="2" maxlength="2000">${esc(s.description||'')}</textarea>
  <div class="editor-fields">${field('session-kind','Type',`<select id="session-kind" name="kind">${options(SESSION_KINDS,s.kind||'session')}</select>`)}${field('session-capacity','Participant limit',`<input id="session-capacity" name="capacity" type="number" min="1" max="10000" value="${esc(s.capacity||20)}" required>`,'Registration closes when every seat is taken.')}${field('session-status','Status',`<select id="session-status" name="status">${options([['scheduled','Scheduled'],['cancelled','Cancelled']],s.status||'scheduled')}</select>`)}</div>
  <div class="editor-fields">${field('session-start','Starts',`<input id="session-start" name="startsAt" type="datetime-local" value="${esc(s.startsAt||'')}" required>`)}${field('session-end','Ends',`<input id="session-end" name="endsAt" type="datetime-local" value="${esc(s.endsAt||'')}" required>`)}${currentUser.role!=='trainer'?field('session-trainer','Trainer',`<select id="session-trainer" name="trainerId">${options(org.trainers.map(t=>[t.id,`${t.name} · ${ROLE_LABELS[t.role]||t.role}`]),s.trainerId,'Not assigned')}</select>`,'A trainer cannot be booked into two sessions at once.'):''}</div>
  <h3 class="sub-heading">Where it happens</h3>
  <div class="editor-fields">${field('session-delivery','Delivery',`<select id="session-delivery" name="delivery">${options(SESSION_DELIVERY,s.delivery||'in_person')}</select>`)}${field('session-location','Room or address',`<input id="session-location" name="location" value="${esc(s.location||'')}" maxlength="200">`,'For in-person and hybrid sessions.')}${field('session-platform','Online platform',`<select id="session-platform" name="meetingProvider">${options(MEETING_PLATFORMS,s.meetingProvider||'','Detect from the link')}</select>`)}</div>
  ${field('session-meeting','Meeting link',`<input id="session-meeting" name="meetingUrl" type="url" maxlength="2000" value="${esc(s.meetingUrl||'')}" placeholder="https://zoom.us/j/… · https://meet.google.com/… · https://teams.microsoft.com/l/meetup-join/…">`,'Required for online and hybrid sessions. Create the meeting in Zoom, Google Meet or Microsoft Teams and paste its link. Only registered employees see it, and they can join from 15 minutes before the start.')}
  <h3 class="sub-heading">After the session</h3>
  <div class="editor-fields">${field('session-recording','Recording link',`<input id="session-recording" name="recordingUrl" maxlength="2000" value="${esc(s.recordingUrl||'')}" placeholder="https://… or upload below">`,'Shared with registered employees, who are notified when it is added.')}${field('session-recording-file','…or upload the recording (MP4/WebM, up to 50 MB)',`<input id="session-recording-file" type="file" accept=".mp4,.webm" data-change="session-recording-upload"><small class="muted upload-state" id="session-recording-state" role="status"></small>`)}${field('session-assessment','Post-session assessment',`<select id="session-assessment" name="assessmentId">${options(assessments.map(a=>[a.id,a.title]),s.assessmentId,'None')}</select>`,'Published assessments only. Participants are asked to take it once the session ends.')}</div>
  <div class="editor-fields">${field('session-course','Linked course (optional)',`<select id="session-course" name="courseId">${options(org.courses.map(c=>[c.id,c.title]),s.courseId,'None')}</select>`)}</div>
  <div class="check-row">${check('qaEnabled','Live Q&amp;A: participants can ask and upvote questions',s.qaEnabled!==false)}${check('feedbackEnabled','Collect feedback (1–5 stars and a comment) after the session starts',s.feedbackEnabled!==false)}</div>
  <p class="muted">Times use the server's local time zone. Registered employees get reminders 24 hours, 1 hour and 15 minutes before the start, and are told when a session is cancelled, rescheduled or given a new link.</p>
  <div class="admin-actions"><button class="btn" type="submit">Save session</button><button class="btn secondary" type="button" data-act="session-editor-close">Cancel</button></div><p class="form-status" role="status"></p></form></section>`;
}
function rosterPanel(session){
  if(!session)return '';
  const key='roster:'+session.id,entry=loadData(key,`manage/sessions/${session.id}/registrations`);
  if(!entry.data)return stateBlock(entry,'registrations',key);
  const regs=entry.data.registrations,active=regs.filter(r=>r.status!=='cancelled'),attended=active.filter(r=>r.status==='attended').length,started=session.live||session.ended;
  const pending=active.length-attended,rate=active.length?Math.round(attended/active.length*100):0;
  const result=r=>!session.assessment?'':r.assessment?`${r.assessment.passed?tagText('Passed','success'):tagText('Not passed','warn')}<small>Best ${r.assessment.best??'—'}%</small>`:'<span class="muted">Not taken</span>';
  const rows=regs.map(r=>`<tr><td><strong>${esc(r.name)}</strong><small>${esc(r.email||'')}</small></td><td>${esc(r.department||'—')}</td><td>${esc(capital(r.status))}</td><td>${r.status==='cancelled'?'—':started&&session.canEdit?`<label class="check-label"><input type="checkbox" data-change="attendance" data-session="${esc(session.id)}" data-employee="${esc(r.employeeId)}" ${r.status==='attended'?'checked':''}> Attended</label>`:'<span class="muted">After start</span>'}</td><td>${r.rating?stars(r.rating):'—'}</td>${session.assessment?`<td>${result(r)}</td>`:''}</tr>`).join('');
  const actions=`<div class="table-actions">${started&&session.canEdit&&pending?`<button data-act="attendance-all" data-session="${esc(session.id)}">Mark all ${pending} present</button>`:''}${regs.length?`<button data-act="roster-export" data-session="${esc(session.id)}">Export CSV</button>`:''}<button data-act="session-roster-close">Close</button></div>`;
  return panel(`Registrations: ${session.title}`,`<div class="summary-chips"><span><b>${active.length}</b> registered of ${session.capacity}</span><span><b>${attended}</b> attended</span><span><b>${rate}%</b> attendance</span></div><div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Employee</th><th>Department</th><th>Status</th><th>Attendance</th><th>Rating</th>${session.assessment?'<th>Post-session assessment</th>':''}</tr></thead><tbody>${rows||`<tr><td colspan="${session.assessment?6:5}" class="muted">No registrations yet.</td></tr>`}</tbody></table></div>`,actions);
}
function feedbackPanel(session){
  if(!session)return '';
  const key='session-feedback:'+session.id,entry=loadData(key,`manage/sessions/${session.id}/feedback`);
  if(!entry.data)return stateBlock(entry,'feedback',key);
  const {summary:s,items}=entry.data;
  const bars=[5,4,3,2,1].map(n=>`<div class="chart-row"><span class="chart-label">${n} star${n===1?'':'s'}<small>${s.distribution[n]} response${s.distribution[n]===1?'':'s'}</small></span>${meter(s.responses?Math.round(s.distribution[n]/s.responses*100):0,`${n} stars`)}</div>`).join('');
  const comments=items.filter(i=>i.comment).map(i=>`<div class="activity"><span class="bubble">${icon('user')}</span><p>${stars(i.rating)} ${esc(i.comment)}<br><small>${esc(i.name)} · ${esc(fmtDateTime(i.at))}</small></p></div>`).join('');
  return panel(`Feedback: ${session.title}`,s.responses?`<div class="summary-chips"><span><b>${s.averageRating}</b> average ${stars(s.averageRating)}</span><span><b>${s.responses}</b> response${s.responses===1?'':'s'}</span><span><b>${s.responseRate}%</b> of ${s.participants} participants</span></div>${bars}<h3 class="sub-heading">Comments</h3>${comments||'<p class="muted">No written comments yet.</p>'}`:emptyState('No feedback yet','Participants can rate the session from the Training Calendar once it starts, and are reminded when it ends.'),'<button class="btn secondary" data-act="session-feedback-close">Close</button>');
}
function trainersPanel(){
  const entry=loadData('trainers','manage/trainers');
  if(!entry.data)return stateBlock(entry,'trainers','trainers');
  const rows=entry.data.trainers.map(t=>`<tr><td><strong>${esc(t.name)}</strong><small>${esc(ROLE_LABELS[t.role]||t.role)} · ${esc(t.email)}</small></td><td>${t.upcoming}</td><td>${t.delivered}<small>${t.hoursDelivered} hours</small></td><td>${t.attendees}</td><td>${t.averageRating!=null?`${stars(t.averageRating)} ${t.averageRating}<small>${t.ratings} rating${t.ratings===1?'':'s'}</small>`:'<span class="muted">No ratings</span>'}</td><td>${t.next?`${esc(t.next.title)}<small>${esc(fmtDateTime(t.next.startsAt))}</small>`:'<span class="muted">Nothing scheduled</span>'}</td></tr>`).join('');
  const mine=currentUser.role==='trainer';
  return panel(mine?'My training load':'Trainers',`<div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>Trainer</th><th>Upcoming</th><th>Delivered</th><th>Participants trained</th><th>Average rating</th><th>Next session</th></tr></thead><tbody>${rows||'<tr><td colspan="6" class="muted">No trainers yet. Choose a trainer when you schedule a session, and their workload and ratings appear here.</td></tr>'}</tbody></table></div><p class="muted">${mine?'Sessions you run, with attendance and participant ratings.':'Accounts with the Trainer role, plus administrators and HR who run sessions. Choose the trainer when scheduling a session; nobody can be booked into two sessions at once.'}</p>`);
}

// ---------------------------------------------------------------- downloads

async function downloadCalendar(path){
  const response=await fetch('/api/'+path,{credentials:'same-origin',headers:{'X-Portal-Request':'1'}});
  if(!response.ok)throw new Error((await response.json().catch(()=>({}))).error||'The calendar file could not be downloaded.');
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download=(/filename="([^"]+)"/.exec(response.headers.get('Content-Disposition')||'')||[])[1]||'shimentox-training.ics';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('Calendar file downloaded. Open it to add the session to your calendar.');
}
function exportRoster(sessionId){
  const session=pageCache['m-sessions']?.data?.sessions.find(s=>s.id===sessionId),regs=pageCache['roster:'+sessionId]?.data?.registrations||[];
  const columns=[{key:'name',label:'Employee'},{key:'email',label:'Email'},{key:'department',label:'Department'},{key:'status',label:'Status'},{key:'rating',label:'Rating'},{key:'assessment',label:'Post-session assessment'}];
  const rows=regs.map(r=>({...r,assessment:r.assessment?`${r.assessment.passed?'Passed':'Not passed'} (best ${r.assessment.best??'-'}%)`:''}));
  download(`shimentox-session-${(session?.title||'roster').toLowerCase().replace(/[^a-z0-9]+/g,'-')}.csv`,toCSV(columns,rows),'text/csv;charset=utf-8');
}

// ---------------------------------------------------------------- handlers

const refreshSessions=()=>refreshData('m-sessions','me-cal','me-dash','trainers','dash','mgr-dash');
Object.assign(ACTIONS,{
  'session-register':async el=>{const data=await api(`me/sessions/${el.dataset.id}/register`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='You are registered. The joining details and calendar options are on the session card.';render();},
  'session-cancel':async el=>{if(!confirm('Cancel your registration for this session?'))return;const data=await api(`me/sessions/${el.dataset.id}/cancel`,{});pageCache['me-cal']={data};refreshData('m-sessions','me-dash');devMessage='Your registration was cancelled.';render();},
  'session-new':()=>{sessionEditor={};render();document.querySelector('[data-form="session-save"]')?.scrollIntoView({behavior:'smooth'});},
  'session-edit':el=>{sessionEditor={...pageCache['m-sessions'].data.sessions.find(s=>s.id===el.dataset.id)};render();document.querySelector('[data-form="session-save"]')?.scrollIntoView({behavior:'smooth'});},
  'session-editor-close':()=>{sessionEditor=null;render();},
  'session-roster':el=>{sessionRoster=el.dataset.id;delete pageCache['roster:'+el.dataset.id];render();},
  'session-roster-close':()=>{sessionRoster=null;render();},
  'session-filter':el=>{sessionFilter=el.dataset.value;render();},
  'session-feedback-report':el=>{feedbackReportId=el.dataset.id;delete pageCache['session-feedback:'+el.dataset.id];render();},
  'session-feedback-close':()=>{feedbackReportId=null;render();},
  'session-ics':el=>downloadCalendar(`me/sessions/${encodeURIComponent(el.dataset.id)}/calendar.ics`),
  'calendar-ics':()=>downloadCalendar('me/calendar.ics'),
  'attendance-all':async el=>{if(!confirm('Mark everyone who is still registered as attended?'))return;const data=await api(`manage/sessions/${el.dataset.session}/attendance`,{all:true});pageCache['roster:'+el.dataset.session]={data};refreshData('m-sessions','trainers');render();},
  'roster-export':el=>exportRoster(el.dataset.session),
  'qa-open':el=>{qaSessionId=el.dataset.id;delete pageCache['qa:'+qaSessionId];render();document.getElementById('qa-panel')?.scrollIntoView({behavior:'smooth'});},
  'qa-close':()=>{stopQaPolling();qaSessionId=null;refreshData('m-sessions');render();},
  'qa-vote':async el=>{const data=await api(`me/sessions/${qaSessionId}/questions/${el.dataset.id}/vote`,{});pageCache['qa:'+qaSessionId]={data};render();},
  'qa-status':async el=>{const data=await api(`manage/sessions/${qaSessionId}/questions/${el.dataset.id}`,{status:el.dataset.status});pageCache['qa:'+qaSessionId]={data};render();},
});
Object.assign(SUBMITS,{
  'session-save':form=>submitForm(form,async()=>{const v=formValues(form);
    const data=await api('manage/sessions',{id:form.dataset.id||null,title:v.title,description:v.description,kind:v.kind,status:v.status,capacity:Number(v.capacity),startsAt:v.startsAt,endsAt:v.endsAt,location:v.location||'',
      courseId:v.courseId||null,...('trainerId' in v?{trainerId:v.trainerId||null}:{}),delivery:v.delivery,meetingProvider:v.meetingProvider||'',meetingUrl:v.meetingUrl||'',recordingUrl:v.recordingUrl||'',
      assessmentId:v.assessmentId||null,qaEnabled:v.qaEnabled==='on',feedbackEnabled:v.feedbackEnabled==='on'});
    refreshSessions();pageCache['m-sessions']={data};sessionEditor=null;devMessage='Session saved.';render();}),
  'session-feedback':form=>submitForm(form,async()=>{const v=formValues(form);await api(`me/sessions/${form.dataset.id}/feedback`,{rating:Number(v.rating),comment:v.comment||''});refreshData('me-cal');devMessage='Thank you. Your feedback was sent to the trainer.';render();}),
  'qa-ask':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api(`me/sessions/${qaSessionId}/questions`,{body:v.body,anonymous:v.anonymous==='on'});pageCache['qa:'+qaSessionId]={data};render();}),
  'qa-answer':form=>submitForm(form,async()=>{const v=formValues(form);const data=await api(`manage/sessions/${qaSessionId}/questions/${form.dataset.id}`,{status:'answered',answer:v.answer||''});pageCache['qa:'+qaSessionId]={data};render();}),
});
Object.assign(CHANGES,{
  attendance:async el=>{try{const data=await api(`manage/sessions/${el.dataset.session}/attendance`,{employeeId:el.dataset.employee,attended:el.checked});pageCache['roster:'+el.dataset.session]={data};refreshData('m-sessions','trainers');render();}catch(error){toast(error.message);el.checked=!el.checked;}},
  // The recording is uploaded straight away; its link fills the field and is kept when the session is saved.
  'session-recording-upload':async el=>{const file=el.files?.[0],state=document.getElementById('session-recording-state');if(!file)return;
    if(state)state.textContent=`Uploading ${file.name}…`;
    try{const material=await uploadMaterial(file);const input=document.getElementById('session-recording');if(input)input.value=material.url;if(sessionEditor)sessionEditor.recordingUrl=material.url;if(state)state.textContent=`Uploaded ${material.name}. Save the session to share it.`;}
    catch(error){if(state)state.textContent=error.message;}},
});
