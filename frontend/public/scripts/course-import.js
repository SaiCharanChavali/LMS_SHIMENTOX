// ---------------------------------------------------------------- Manage Courses → Add a course
// Choose manual creation or Create from a link with AI. Courses imported by earlier versions still show their import report in the builder.
let courseAddMode=null,generateState=null;
const IMPORT_STATUS={imported:['success','IMPORTED'],inaccessible:['warn','NOT RETRIEVED'],reference:['gray','REFERENCE'],generated:['success','WRITTEN']};
function addCourseChooser(){
  return `<section class="panel admin-form add-course-choice" id="add-course-choice"><div class="section-heading"><h2>Add a course</h2><button type="button" class="auth-link" data-import="close">Cancel</button></div><div class="choice-grid"><button type="button" class="choice-card" id="new-course"><strong>Create manually</strong><span>Build the course lesson by lesson with videos, documents, written content and an assessment.</span></button><button type="button" class="choice-card" data-import="generate-open"><strong>Create from a link with AI</strong><span>Paste a link to a website. AI uses it as a reference and writes a new course in our format, with lessons, knowledge checks and a final assessment.</span></button></div></section>`;
}
// ---------------------------------------------------------------- Manage Courses → Add a course → Create from a link with AI
// The server reads the link and writes an original draft course as a background job; this page follows its progress.
const GENERATE_STAGES=[['reading','Reading the website'],['writing','Writing the lessons and assessments. This usually takes a few minutes.'],['saving','Saving the draft course']];
function newGenerateState(){return {url:'',title:'',category:'',busy:false,stage:'',error:'',jobId:null,failures:0};}
function generateProgress(s){
  const current=GENERATE_STAGES.findIndex(([stage])=>stage===s.stage);
  return `<ol class="generate-stages" role="status" aria-live="polite">${GENERATE_STAGES.map(([stage,label],i)=>`<li class="${i<current?'done':i===current?'active':''}">${i<current?'✓ ':''}${esc(label)}</li>`).join('')}</ol><p class="muted">Stay on this page and the course opens when it is ready. If you leave, it still appears as a draft in the course catalog.</p>`;
}
function courseGenerator(){
  const s=generateState,org=orgData(),entry=loadData('gen-status','manage/course-generator'),off=entry.data&&!entry.data.enabled;
  const categories=org.categories.length?org.categories:['Technical Skills'];
  return `<section class="panel admin-form course-editor" id="course-generator"><div class="section-heading"><div><span class="tag">ADD A COURSE · CREATE FROM A LINK</span><h2>Create a course from a website link</h2></div><button type="button" class="btn secondary" data-import="close">Close</button></div>
  ${off?`<div class="notice" role="alert">${esc(entry.data.reason)}</div>`:''}
  <form id="generate-form"><label for="gen-url">Website link</label><input id="gen-url" type="url" data-g="url" value="${esc(s.url)}" maxlength="2000" required placeholder="https://www.example.com/guide-to-the-topic" ${s.busy?'disabled':''}>
  <div class="editor-fields">${builderField('Course title (optional)','gen-title',`<input id="gen-title" data-g="title" value="${esc(s.title)}" maxlength="150" placeholder="Chosen by AI" ${s.busy?'disabled':''}>`)}${builderField('Category','gen-category',`<select id="gen-category" data-g="category" ${s.busy?'disabled':''}>${options(categories.map(c=>[c,c]),s.category,'Choose automatically')}</select>`)}</div>
  <p class="muted">The link is used only as a reference. AI writes new lessons, examples and questions in our course format, with a knowledge check after each lesson and a final assessment (70% pass mark, 3 attempts, full-screen exam rules, certificate on completion). The course is saved as a draft for you to review and publish. AI can make mistakes, so please check it before publishing. Only publicly readable pages can be used.</p>
  ${s.error?`<div class="notice" role="alert">${esc(s.error)}</div>`:''}${s.busy?generateProgress(s):`<button class="btn" type="submit" ${off?'disabled':''}>Create course</button>`}</form></section>`;
}
async function runCourseGenerator(){
  const s=generateState;if(!s||s.busy)return;
  if(!s.url.trim()){s.error='Paste the address of a website.';render();return;}
  Object.assign(s,{busy:true,error:'',stage:'reading',failures:0});render();
  try{
    const data=await api('manage/course-generator',{url:s.url.trim(),title:s.title.trim(),category:s.category});
    s.jobId=data.job.id;
    while(generateState===s&&s.busy){
      await new Promise(resolve=>setTimeout(resolve,3000));
      if(generateState!==s)return;
      let job;
      try{job=(await api('manage/course-generator/'+s.jobId)).job;s.failures=0;}
      catch(error){if(++s.failures>=5)throw error;continue;}
      await handleCourseJob(s,job);
    }
  }catch(error){s.busy=false;s.error=error.message;render();}
}
async function handleCourseJob(s,job){
  if(job.status==='failed'){Object.assign(s,{busy:false,error:job.error});render();return;}
  if(job.status!=='done'){if(job.stage!==s.stage){s.stage=job.stage;render();}return;}
  generateState=null;courseAddMode=null;
  await loadAdminState();courseCatalog=(await api('courses')).courses;refreshData('org','dash','me-dash','m-assess');
  const opening=openCourseBuilder(job.courseId,4);
  adminMessage=`“${job.title}” was created as a draft. Review it below, then publish it.${job.notes.length?' '+job.notes.join(' '):''}`;
  await opening;
}
const IMPORT_ACTIONS={
  choose:()=>{courseAddMode='choose';},
  close:()=>{courseAddMode=null;generateState=null;},
  'generate-open':()=>{courseAddMode='generate';generateState=newGenerateState();editingCourse=null;courseDraft=null;adminMessage='';},
};
document.addEventListener('click',event=>{
  const el=event.target.closest?.('[data-import]');if(!el||el.disabled)return;
  const action=IMPORT_ACTIONS[el.dataset.import];if(!action)return;
  event.preventDefault();
  const result=action(el);
  if(!(result instanceof Promise))render();
});
document.addEventListener('submit',event=>{if(event.target.id==='generate-form'){event.preventDefault();runCourseGenerator();}});
function importInput(el){
  if(generateState&&el.dataset?.g&&el.closest?.('#course-generator'))generateState[el.dataset.g]=el.value;
}
document.addEventListener('input',event=>importInput(event.target));
document.addEventListener('change',event=>importInput(event.target));
// Where an imported course came from, shown in the builder.
function importReportPanel(d){
  const report=d.importReport;if(!d.source||!report)return '';
  const counts={imported:0,inaccessible:0,reference:0};report.lessons.forEach(l=>counts[l.status]=(counts[l.status]||0)+1);
  return `<details class="import-report"><summary>${report.mode==='generated'?`Written by AI using ${esc(d.source.platform)} as a reference (employees do not see this)`:`Imported from ${esc(d.source.platform)}`} · ${report.mode==='generated'?`${report.lessons.length} lessons`:report.mode==='reference'?'saved as a reference':`${counts.imported} lesson${counts.imported===1?'':'s'} imported${counts.inaccessible?`, ${counts.inaccessible} not retrieved`:''}`}</summary><p class="muted"><a href="${esc(report.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(report.sourceUrl)} ↗</a> · ${esc(report.strategy)} · ${esc(fmtDate(report.importedAt))}${report.license?` · ${esc(report.license.name)}`:''}</p><ol class="import-report-list">${report.lessons.map(l=>{const [tone,label]=IMPORT_STATUS[l.status]||IMPORT_STATUS.inaccessible;return `<li><span class="tag ${tone}">${label}</span> ${esc(l.title)}${l.reason?` <small>${esc(l.reason)}</small>`:''}</li>`;}).join('')}</ol></details>`;
}
