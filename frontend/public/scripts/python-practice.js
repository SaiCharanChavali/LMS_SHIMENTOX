// Original lesson practice, rendered inside Shimento. Execution reports are practice feedback, never assignment grades.
const pythonPracticeState=new Map();
const lessonKnowledgeState=new Map();
let pythonExecution=null;
function practiceState(lesson){
 if(!pythonPracticeState.has(lesson.id))pythonPracticeState.set(lesson.id,{code:learning.run.codeDrafts?.[lesson.id]??lesson.practice.starter,output:'',results:[],message:'Ready to run Python.',busy:false});
 return pythonPracticeState.get(lesson.id);
}
function pythonPracticePanel(lesson){
 const s=practiceState(lesson);
 return `<section class="python-workshop" aria-labelledby="python-practice-title"><div class="section-heading"><h3 id="python-practice-title">Code workshop</h3><span class="tag">PYTHON · IN YOUR BROWSER</span></div><p>${esc(lesson.practice.instructions)}</p><label for="python-editor">Your Python code</label><textarea id="python-editor" data-lesson-id="${esc(lesson.id)}" spellcheck="false" autocapitalize="off" autocomplete="off" rows="13" maxlength="20000">${esc(s.code)}</textarea><div class="python-actions"><button class="btn" id="python-run" ${s.busy?'disabled':''}>Run & check ${icon('play')}</button><button class="btn secondary" id="python-save" ${s.busy?'disabled':''}>Save code</button><button class="btn secondary" id="python-reset" ${s.busy?'disabled':''}>Reset starter</button>${s.busy?'<button class="btn secondary" id="python-stop">Stop execution</button>':''}</div><p id="python-status" class="muted" role="status">${esc(s.message)}</p><h4>Output</h4><pre id="python-output" tabindex="0" aria-label="Python output">${esc(s.output||'Run your code to see its output here.')}</pre><ul id="python-results" class="python-checks">${pythonResults(s.results)}</ul><p class="muted">Coding checks help you practice. Pass the knowledge check below to record module completion.</p></section>`;
}
function pythonResults(results){return results.map(r=>`<li class="${r.passed?'passed':'failed'}">${r.passed?'✓':'✗'} ${esc(r.label)}${r.error?`<pre>${esc(r.error)}</pre>`:''}</li>`).join('');}
function lessonKnowledgePanel(lesson){
 const feedback=lessonKnowledgeState.get(lesson.id);
 const completed=learning.run.lessons?.[lesson.id];
 return `<section class="python-knowledge knowledge-card"><div class="knowledge-head"><span class="knowledge-icon">${icon('check')}</span><div><h3>Knowledge check</h3><p>Answer all ${lesson.quiz.length} questions correctly to complete this module. You can retry as often as you like.</p></div>${completed?'<span class="tag success">✓ Completed</span>':''}</div>${feedback?`<div class="notice ${feedback.passed?'success':''}" role="status">${feedback.score}/${feedback.total} correct. ${feedback.passed?'Module completed.':'Review the questions marked for another try.'}</div>`:''}<form id="lesson-quiz-form" data-lesson-id="${esc(lesson.id)}">${lesson.quiz.map((q,i)=>`<fieldset class="question ${feedback?feedback.correct[i]?'is-correct':'is-wrong':''}"><legend><span>${i+1}.</span> ${esc(q.prompt)}${feedback?` <em class="question-verdict">${feedback.correct[i]?'✓ Correct':'✗ Try again'}</em>`:''}</legend>${q.options.map((o,j)=>`<label class="answer"><input type="radio" name="lesson-quiz-${i}" value="${j}" required ${feedback?.answers?.[i]===j?'checked':''}><span class="answer-letter" aria-hidden="true">${String.fromCharCode(65+j)}</span><span>${esc(o)}</span></label>`).join('')}</fieldset>`).join('')}<button class="btn" type="submit">Check answers ${icon('check')}</button><p class="form-status" role="status"></p></form></section>`;
}
function updatePythonOutput(lesson){
 const s=practiceState(lesson),status=document.getElementById('python-status'),output=document.getElementById('python-output'),results=document.getElementById('python-results');
 if(status)status.textContent=s.message;if(output)output.textContent=s.output||'No printed output.';if(results)results.innerHTML=pythonResults(s.results);
}
function stopPythonExecution(message='Execution stopped.'){
 if(!pythonExecution)return;
 const {lesson,frame,timer}=pythonExecution;clearTimeout(timer);frame.remove();const s=practiceState(lesson);s.busy=false;s.message=message;pythonExecution=null;
}
function startPythonExecution(lesson){
 stopPythonExecution();
 const s=practiceState(lesson);s.output='';s.results=[];s.busy=true;s.message='Loading Python…';
 render();
 const frame=document.createElement('iframe');frame.hidden=true;frame.sandbox='allow-scripts';frame.title='Isolated Python runner';
 const nonce=crypto.randomUUID();
 frame.onload=()=>frame.contentWindow.postMessage({shimentoPython:true,type:'run',nonce,code:s.code,tests:lesson.practice.tests},'*');
 const timer=setTimeout(()=>{stopPythonExecution('Python could not start. Please retry.');render();},60000);
 pythonExecution={frame,lesson,nonce,timer};frame.src='python-sandbox.html';document.body.appendChild(frame);
}
window.addEventListener('message',event=>{
 const current=pythonExecution,data=event.data;
 if(!current||event.source!==current.frame.contentWindow||!data?.shimentoPython||data.nonce!==current.nonce)return;
 const s=practiceState(current.lesson);
 if(data.type==='output')s.output=(s.output+String(data.text)+'\n').slice(0,24000);
 else if(data.type==='loading')s.message='Loading Python…';
 else if(data.type==='running')s.message='Running code and checking your work…';
 else if(data.type==='result'){s.results=Array.isArray(data.results)?data.results:[];stopPythonExecution(s.results.every(r=>r.passed)?'All coding checks passed.': 'Some checks need another try.');render();}
 else if(data.type==='error'){s.output+=String(data.text);stopPythonExecution('Execution ended. Review the output and try again.');render();}
 updatePythonOutput(current.lesson);
});
function wirePythonPractice(){
 const editor=document.getElementById('python-editor');
 if(!editor){if(pythonExecution)stopPythonExecution();return;}
 const lesson=currentCourseExtras.courseLessons.find(l=>l.id===editor.dataset.lessonId);
 if(!lesson)return;
 if(pythonExecution&&pythonExecution.lesson.id!==lesson.id)stopPythonExecution();
 const s=practiceState(lesson);editor.oninput=()=>{s.code=editor.value;};
 editor.onkeydown=event=>{if(event.key==='Tab'){event.preventDefault();const start=editor.selectionStart,end=editor.selectionEnd;editor.setRangeText('    ',start,end,'end');s.code=editor.value;}};
 const save=async()=>{s.code=editor.value;await learningRequest('lesson-draft',{lessonId:lesson.id,code:s.code});s.message='Code saved to your course run.';updatePythonOutput(lesson);};
 document.getElementById('python-save').onclick=()=>save().catch(e=>{s.message=e.message;updatePythonOutput(lesson);});
 document.getElementById('python-run').onclick=async()=>{try{await save();startPythonExecution(lesson);}catch(e){s.message=e.message;updatePythonOutput(lesson);}};
 document.getElementById('python-reset').onclick=()=>{s.code=lesson.practice.starter;s.output='';s.results=[];s.message='Starter code restored. Save it to keep this reset.';render();};
 const stop=document.getElementById('python-stop');if(stop)stop.onclick=()=>{stopPythonExecution();render();};
}
function wireLessonKnowledge(){
 const form=document.getElementById('lesson-quiz-form');if(!form)return;
 const lesson=currentCourseExtras?.courseLessons?.find(l=>l.id===form.dataset.lessonId);if(!lesson)return;
 form.onsubmit=event=>{event.preventDefault();submitForm(form,async()=>{
  const values=new FormData(form),raw=lesson.quiz.map((_,i)=>values.get('lesson-quiz-'+i));
  if(raw.some(v=>v===null))throw new Error('Answer every knowledge-check question.');
  const answers=raw.map(Number),result=await learningRequest('lesson-quiz',{lessonId:lesson.id,answers});
  lessonKnowledgeState.set(lesson.id,{...result.quizResult,answers});render();
 });};
}
window.addEventListener('pagehide',()=>stopPythonExecution());
