// ---------------------------------------------------------------- Manage Courses → Add a course → Import from URL
// The server retrieves and extracts the source; this page shows the preserved structure for review, then saves
// it as a draft or publishes it. Imported courses open in the regular course builder for further editing.
let courseAddMode=null,importState=null;
const IMPORT_STATUS={imported:['success','IMPORTED'],inaccessible:['warn','NOT RETRIEVED'],reference:['gray','REFERENCE']};
function newImportState(){const org=orgData();return {url:'',title:'',category:org.categories[0]||'Technical Skills',difficulty:'beginner',departmentId:'',durationMinutes:'',visibility:'everyone',description:'',busy:false,error:'',result:null,token:null,duplicate:null,mode:'full',rights:false,openLesson:null};}
function importLessons(result){return result.items.flatMap((item,m)=>item.type==='module'?item.lessons.map((l,j)=>({...l,key:`${m}-${j}`,module:item.title})):[{...item,key:`${m}`,module:''}]);}
const lessonMinutes=l=>l.status==='imported'?Math.ceil((l.words||0)/200):0;
function addCourseChooser(){
  return `<section class="panel admin-form add-course-choice" id="add-course-choice"><div class="section-heading"><h2>Add a course</h2><button type="button" class="auth-link" data-import="close">Cancel</button></div><div class="choice-grid"><button type="button" class="choice-card" id="new-course"><strong>Create manually</strong><span>Build the course lesson by lesson with videos, documents, written content and an assessment.</span></button><button type="button" class="choice-card" data-import="open"><strong>Import from URL</strong><span>Paste a link to a course or article on a public learning website. Review the original modules, lessons and sections before saving.</span></button></div></section>`;
}
function importLessonRow(l,n){
  const [tone,label]=IMPORT_STATUS[l.status]||IMPORT_STATUS.inaccessible,open=importState.openLesson===l.key;
  const facts=l.status==='imported'?[`${l.words} words`,l.sections.length&&`${l.sections.length} section${l.sections.length===1?'':'s'}`,l.codeBlocks&&`${l.codeBlocks} code`,l.tables&&`${l.tables} table${l.tables===1?'':'s'}`,l.figures&&`${l.figures} figure link${l.figures===1?'':'s'}`].filter(Boolean).join(' · '):'';
  const outline=l.sections.length?`<ul class="import-outline">${l.sections.map(s=>`<li class="level-${s.level}">${esc(s.title)}</li>`).join('')}</ul>`:'';
  return `<li class="import-lesson"><div class="import-lesson-head"><span class="lesson-num">${n}</span><div class="lesson-row-title"><strong>${esc(l.title)}</strong><small>${facts?esc(facts)+' · ':''}${l.url?`<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(hostOf(l.url))} ↗</a>`:''}</small>${l.reason?`<small class="import-reason">${esc(l.reason)}</small>`:''}${l.description&&l.status==='reference'?`<small>${esc(l.description)}</small>`:''}</div><span class="tag ${tone}">${label}</span>${l.content?`<button type="button" class="auth-link" data-import="lesson" data-key="${esc(l.key)}" aria-expanded="${open}">${open?'Hide':'Preview'}</button>`:''}</div>${open?`<div class="import-lesson-body">${outline}<div class="lesson-content">${renderMarkdown(l.content)}</div></div>`:''}</li>`;
}
function importStructure(result){
  let n=0;
  return `<ol class="import-tree">${result.items.map((item,m)=>item.type==='module'?`<li class="import-module"><div class="import-module-title"><span class="tag gray">MODULE</span><strong>${esc(item.title)}</strong><small>${item.lessons.length} lesson${item.lessons.length===1?'':'s'}</small></div><ol>${item.lessons.map((l,j)=>importLessonRow({...l,key:`${m}-${j}`},++n)).join('')}</ol></li>`:importLessonRow({...item,key:`${m}`},++n)).join('')||'<li class="muted">No lessons were found. The course can be saved as a reference to the original page.</li>'}</ol>`;
}
function importPreview(){
  const s=importState,r=s.result,st=r.stats,full=r.policy.fullContent&&st.imported>0;
  const licence=r.license?`Licence: ${r.license.url?`<a href="${esc(r.license.url)}" target="_blank" rel="noopener noreferrer">${esc(r.license.name)} ↗</a>`:esc(r.license.name)}`:'No licence is stated on the source page';
  const counts=[[st.modules,'Modules'],[st.lessons,'Lessons'],[st.imported,'Imported'],[st.inaccessible,'Not retrieved']].map(([v,l])=>`<div><strong>${v}</strong><span>${l}</span></div>`).join('');
  const modes=`<fieldset class="import-modes"><legend>What to save</legend><label class="check-label"><input type="radio" name="import-mode" value="full" data-i="mode" ${s.mode==='full'?'checked':''} ${full?'':'disabled'}> Import the lesson content shown above${full?'':' (not available for this source)'}</label><label class="check-label"><input type="radio" name="import-mode" value="reference" data-i="mode" ${s.mode==='reference'?'checked':''}> Save as a course reference: titles, structure and links to the original, without copying content</label></fieldset>`;
  const rights=s.mode==='full'?`<label class="check-label import-rights"><input type="checkbox" data-i="rights" ${s.rights?'checked':''}> I confirm ShimentoX is permitted to reuse this content (for example under its licence or an agreement with the publisher). Attribution and links to the original are kept on every lesson.</label>`:'';
  return `<section class="import-preview" aria-label="Import preview"><div class="preview-head"><span class="tag">PREVIEW · ${esc(r.platform.name.toUpperCase())}</span><h2>${esc(r.title||'Untitled source')}</h2><p class="muted">${esc(r.strategy)} · <a href="${esc(r.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(r.sourceUrl)} ↗</a></p><p class="muted">${licence}${r.provider?` · Offered by ${esc(r.provider)}`:''}</p></div>
  ${s.duplicate?`<div class="notice" role="alert">This source was already imported as <b>${esc(s.duplicate.title)}</b> (${esc(s.duplicate.status)}). Edit that course instead, or archive it before importing again.</div>`:''}
  ${r.policy.note?`<div class="notice">${esc(r.policy.note)}</div>`:''}
  <div class="save-summary">${counts}</div>${r.notes.length?`<ul class="import-notes">${r.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>`:''}
  <h3 class="sub-heading">Course structure</h3><p class="muted">Modules, lessons and sections keep the source's names and order. Select Preview to read a lesson as employees will see it.</p>${importStructure(r)}
  <h3 class="sub-heading">Save</h3>${modes}${rights}<label for="imp-description">Course description</label><textarea id="imp-description" rows="3" maxlength="2000" data-i="description">${esc(s.description)}</textarea>
  <p class="muted">Imported courses are saved as drafts unless you publish them. After saving, the course opens in the course builder so you can review lessons and add an assessment.</p>
  <div class="admin-actions"><button type="button" class="btn" data-import="save" data-status="draft" ${s.busy||s.duplicate?'disabled':''}>${s.busy?'Saving…':'Save as draft'}</button><button type="button" class="btn secondary" data-import="save" data-status="published" ${s.busy||s.duplicate?'disabled':''}>Publish</button><button type="button" class="auth-link" data-import="reset">Import a different URL</button></div></section>`;
}
function courseImporter(){
  const s=importState,org=orgData(),categories=[...new Set([...(org.categories.length?org.categories:['Technical Skills']),s.category])];
  return `<section class="panel admin-form course-editor" id="course-importer"><div class="section-heading"><div><span class="tag">ADD A COURSE · IMPORT FROM URL</span><h2>Import a course from a learning website</h2></div><button type="button" class="btn secondary" data-import="close">Close</button></div>
  <form id="import-form"><label for="imp-url">Course URL</label><div class="inline-field"><input id="imp-url" type="url" data-i="url" value="${esc(s.url)}" maxlength="2000" required placeholder="https://learn.microsoft.com/training/modules/…" ${s.busy?'disabled':''}><button class="btn" type="submit" ${s.busy?'disabled':''}>${s.busy&&!s.result?'Importing…':'Import'}</button></div>
  <p class="muted">The importer identifies the website, reads its publicly accessible pages, and keeps the original modules, lessons, sections, lists, tables and code. It does not sign in, bypass paywalls or CAPTCHAs, or download videos. Nothing is saved until you review the preview.${s.busy&&!s.result?' Retrieving and analysing the source can take up to a minute for multi-page courses.':''}</p>
  <div class="editor-fields">${builderField('Course title','imp-title',`<input id="imp-title" data-i="title" value="${esc(s.title)}" maxlength="150" placeholder="Detected from the source">`)}${builderField('Category','imp-category',`<select id="imp-category" data-i="category">${options(categories.map(c=>[c,c]),s.category)}</select>`)}${builderField('Difficulty level','imp-difficulty',`<select id="imp-difficulty" data-i="difficulty">${options([['beginner','Beginner'],['intermediate','Intermediate'],['advanced','Advanced'],['expert','Expert']],s.difficulty)}</select>`)}</div>
  <div class="editor-fields">${builderField('Estimated duration (minutes)','imp-duration',`<input id="imp-duration" type="number" min="0" max="100000" data-i="durationMinutes" value="${esc(s.durationMinutes)}" placeholder="Estimated from the content">`)}${builderField('Department','imp-department',`<select id="imp-department" data-i="departmentId">${options(org.departments.map(x=>[x.id,x.name]),s.departmentId,'All departments')}</select>`)}${builderField('Visibility','imp-visibility',`<select id="imp-visibility" data-i="visibility">${options([['everyone','All employees'],['department','Selected department only']],s.visibility)}</select>`)}</div></form>
  ${s.error?`<div class="notice" role="alert">${esc(s.error)}</div>`:''}${s.result?importPreview():''}</section>`;
}
async function runCourseImport(){
  const s=importState;if(!s||s.busy)return;
  if(!s.url.trim()){s.error='Paste the address of a course or article.';render();return;}
  Object.assign(s,{busy:true,error:'',result:null,token:null,duplicate:null,openLesson:null});render();
  try{
    const data=await api('manage/import/preview',{url:s.url.trim()}),r=data.preview;
    Object.assign(s,{result:r,token:data.token,duplicate:data.duplicate,rights:false,mode:r.policy.fullContent&&r.stats.imported?'full':'reference'});
    if(!s.title.trim())s.title=r.title||'';
    if(!s.description.trim())s.description=r.description||'';
    if(s.durationMinutes==='')s.durationMinutes=String(importLessons(r).reduce((n,l)=>n+lessonMinutes(l),0));
  }catch(error){s.error=error.message;}
  finally{s.busy=false;render();}
}
async function saveCourseImport(status){
  const s=importState;if(!s||s.busy||!s.token)return;
  const problem=s.title.trim().length<2?'Enter a course title of at least 2 characters.':s.visibility==='department'&&!s.departmentId?'Choose a department for department-only visibility.':s.mode==='full'&&!s.rights?'Confirm that ShimentoX may reuse this content, or choose to save a course reference.':'';
  if(problem){s.error=problem;render();return;}
  if(status==='published'&&!confirm(`Publish “${s.title}”? It becomes available to ${s.visibility==='department'?'employees in the selected department':'all employees'}.`))return;
  s.busy=true;s.error='';render();
  try{
    const result=await api('manage/import/save',{token:s.token,mode:s.mode,rightsConfirmed:s.mode==='full'&&s.rights,status,title:s.title.trim(),category:s.category,difficulty:s.difficulty,durationMinutes:Number(s.durationMinutes)||0,departmentId:s.departmentId||null,visibility:s.visibility,description:s.description});
    importState=null;courseAddMode=null;
    await loadAdminState();courseCatalog=(await api('courses')).courses;refreshData('org','dash','me-dash','m-paths','m-assess');
    const opening=openCourseBuilder(result.course.id,2);
    adminMessage=`“${result.course.title}” was imported ${status==='published'?'and published':'as a draft'}. Review its lessons below.`;
    await opening;
  }catch(error){s.error=error.message;s.busy=false;render();}
}
const IMPORT_ACTIONS={
  choose:()=>{courseAddMode='choose';},
  close:()=>{courseAddMode=null;importState=null;},
  open:()=>{courseAddMode='import';importState=newImportState();editingCourse=null;courseDraft=null;adminMessage='';},
  lesson:el=>{importState.openLesson=importState.openLesson===el.dataset.key?null:el.dataset.key;},
  reset:()=>{Object.assign(importState,{result:null,token:null,duplicate:null,error:'',openLesson:null});},
  save:el=>saveCourseImport(el.dataset.status),
};
document.addEventListener('click',event=>{
  const el=event.target.closest?.('[data-import]');if(!el||el.disabled)return;
  const action=IMPORT_ACTIONS[el.dataset.import];if(!action||(el.dataset.import!=='choose'&&el.dataset.import!=='open'&&el.dataset.import!=='close'&&!importState))return;
  event.preventDefault();
  const result=action(el);
  if(!(result instanceof Promise))render();
});
document.addEventListener('submit',event=>{if(event.target.id!=='import-form')return;event.preventDefault();runCourseImport();});
function importInput(el){
  if(!importState||!el.dataset?.i||!el.closest?.('#course-importer'))return;
  const field=el.dataset.i;
  if(field==='rights')importState.rights=el.checked;
  else importState[field]=el.value;
  if(field==='mode'){importState.error='';render();}
}
document.addEventListener('input',event=>importInput(event.target));
document.addEventListener('change',event=>importInput(event.target));
// Where an imported course came from, shown in the builder.
function importReportPanel(d){
  const report=d.importReport;if(!d.source||!report)return '';
  const counts={imported:0,inaccessible:0,reference:0};report.lessons.forEach(l=>counts[l.status]=(counts[l.status]||0)+1);
  return `<details class="import-report"><summary>Imported from ${esc(d.source.platform)} · ${report.mode==='reference'?'saved as a reference':`${counts.imported} lesson${counts.imported===1?'':'s'} imported${counts.inaccessible?`, ${counts.inaccessible} not retrieved`:''}`}</summary><p class="muted"><a href="${esc(report.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(report.sourceUrl)} ↗</a> · ${esc(report.strategy)} · ${esc(fmtDate(report.importedAt))}${report.license?` · ${esc(report.license.name)}`:''}</p><ol class="import-report-list">${report.lessons.map(l=>{const [tone,label]=IMPORT_STATUS[l.status]||IMPORT_STATUS.inaccessible;return `<li><span class="tag ${tone}">${label}</span> ${esc(l.title)}${l.reason?` <small>${esc(l.reason)}</small>`:''}</li>`;}).join('')}</ol></details>`;
}
