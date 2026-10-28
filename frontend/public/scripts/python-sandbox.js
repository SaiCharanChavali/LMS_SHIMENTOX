// Opaque-origin iframe + module worker: learner code never runs in the portal window or backend.
const runtimeURL=new URL('../assets/python-runtime/pyodide.mjs',document.currentScript.src).href;
const workerSource=`
let count=0;
function output(text){if(count<24000){self.postMessage({type:'output',text:String(text).slice(0,24000-count)});count+=String(text).length;}}
const ready=(async()=>{const {loadPyodide}=await import(${JSON.stringify(runtimeURL)});return loadPyodide({indexURL:${JSON.stringify(new URL('.',runtimeURL).href)},stdout:output,stderr:output});})();
ready.then(()=>self.postMessage({type:'ready'})).catch(e=>self.postMessage({type:'error',text:String(e)}));
self.onmessage=async event=>{
 const {code,tests}=event.data;
 let globals;
 try{
  const py=await ready;count=0;globals=py.runPython('dict()');
  await py.runPythonAsync(code,{globals});
  const results=[];
  for(const test of tests){try{await py.runPythonAsync(test.code,{globals});results.push({label:test.label,passed:true});}catch(e){results.push({label:test.label,passed:false,error:String(e).slice(-1500)});}}
  self.postMessage({type:'result',results});
 }catch(e){self.postMessage({type:'error',text:String(e).slice(-4000)});}
 finally{globals?.destroy();}
};`;
let worker=null,nonce='',job=null,timer=null,workerURL=null;
function send(data){parent.postMessage({shimentoPython:true,nonce,...data},'*');}
function stop(){clearTimeout(timer);worker?.terminate();if(workerURL)URL.revokeObjectURL(workerURL);workerURL=null;worker=null;job=null;}
function boot(){
 workerURL=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'}));
 // Module-worker entry points fail for opaque sandbox origins in Chromium. A classic
 // entry point dynamically imports the ES modules; importScripts is never used.
 worker=new Worker(workerURL,{credentials:'omit'});
 timer=setTimeout(()=>{send({type:'error',text:'Python could not load in time. Please retry.'});stop();},45000);
 worker.onerror=event=>{const details=JSON.stringify({type:event.type,file:event.filename,line:event.lineno,column:event.colno,error:String(event.error)});send({type:'error',text:event.message||('Python worker initialization failed: '+details)});stop();};
 worker.onmessage=event=>{
  const data=event.data;
  if(data.type==='ready'){
   clearTimeout(timer);send({type:'running'});
   timer=setTimeout(()=>{send({type:'error',text:'Execution stopped after 5 seconds. Check for an infinite loop.'});stop();},5000);
   worker.postMessage(job);
  }else if(data.type==='result'||data.type==='error'){clearTimeout(timer);send(data);stop();}
  else send(data);
 };
}
window.addEventListener('message',event=>{
 if(event.source!==parent||!event.data?.shimentoPython)return;
 const data=event.data;
 if(data.type==='stop'){stop();return;}
 if(data.type!=='run'||typeof data.code!=='string'||data.code.length>20000||!Array.isArray(data.tests)||data.tests.length>10)return;
 stop();nonce=data.nonce;job={code:data.code,tests:data.tests};send({type:'loading'});boot();
});
