
let count=0;
function output(text){if(count<24000){self.postMessage({type:'output',text:String(text).slice(0,24000-count)});count+=String(text).length;}}
const ready=(async()=>{const {loadPyodide}=await import("http://localhost:5173/assets/python-runtime/pyodide.mjs");return loadPyodide({indexURL:"http://localhost:5173/assets/python-runtime/",stdout:output,stderr:output});})();
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
};