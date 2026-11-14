const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9341;
const profile = path.join(process.env.TEMP, "tonyfx-analyzer-profile");
const child = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--allow-file-access-from-files", "--window-size=1180,900", "about:blank"], {stdio:"ignore"});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function endpoint() {
  for (let i=0;i<50;i++) {
    try { const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); const page = pages.find((item)=>item.type==="page"); if (page) return page.webSocketDebuggerUrl; } catch (_) {}
    await sleep(100);
  }
  throw new Error("Chrome did not expose a DevTools endpoint.");
}

(async()=>{
  const socket = new WebSocket(await endpoint());
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let id=0; const pending=new Map(); const errors=[];
  socket.onmessage=(event)=>{const message=JSON.parse(event.data);if(message.method==="Runtime.exceptionThrown")errors.push(message.params.exceptionDetails.exception.description);if(message.id&&pending.has(message.id)){const entry=pending.get(message.id);pending.delete(message.id);message.error?entry.reject(new Error(message.error.message)):entry.resolve(message.result);}};
  const send=(method,params={})=>new Promise((resolve,reject)=>{const command=++id;pending.set(command,{resolve,reject});socket.send(JSON.stringify({id:command,method,params}));});
  const evaluate=async(expression)=>{const result=await send("Runtime.evaluate",{expression,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception.description);return result.result.value;};
  await send("Page.enable"); await send("Runtime.enable");
  const url=encodeURI(`file:///${path.resolve(__dirname,"../index.html").replace(/\\/g,"/")}`);
  await send("Page.navigate",{url});
  for(let i=0;i<60;i++){if(await evaluate("document.readyState==='complete' && !!window.TonyFXCore"))break;await sleep(100);}
  const state=await evaluate(`(()=>{document.querySelector('[data-tab="analyze"]').click();const panel=document.getElementById('analyzeTab');const rect=panel.getBoundingClientRect();const ids=['openAnalyzeReport','applyAnalyzeMarkers','compareFinishedEdit','openRepairPlan','applySafeRepair','buildOfflineEdit','reeditOfflineEdit','auditOfflineEdit'];const buttons=ids.map(id=>{const el=document.getElementById(id);const style=getComputedStyle(el);return{id,disabled:el.disabled,color:style.color,background:style.backgroundColor,visible:el.getBoundingClientRect().height>0};});return{active:panel.classList.contains('active'),width:rect.width,run:!!document.getElementById('runAnalyze'),summary:document.querySelectorAll('#analyzeSummary>div').length,overflow:document.documentElement.scrollWidth-innerWidth,version:document.querySelector('.version').textContent,buttons};})()`);
  if(!state.active||!state.run||state.summary!==4||state.overflow>1||state.version!=="v0.58.0")throw new Error(`Analyzer panel failed: ${JSON.stringify(state)}`);
  for(const button of state.buttons){if(button.disabled||!button.visible||button.background==="rgba(0, 0, 0, 0)"||button.color==="rgba(0, 0, 0, 0)")throw new Error(`Analyzer action visibility failed: ${JSON.stringify(button)}`);}
  const shot=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});fs.writeFileSync(path.resolve(__dirname,"tonyfx-v058-analyzer.png"),Buffer.from(shot.data,"base64"));
  await send("Emulation.setDeviceMetricsOverride",{width:430,height:780,deviceScaleFactor:1,mobile:false});await send("Page.reload",{ignoreCache:true});await sleep(700);
  const narrow=await evaluate(`(()=>{document.querySelector('[data-tab="analyze"]').click();return{overflow:document.documentElement.scrollWidth-innerWidth,workspace:getComputedStyle(document.querySelector('.analyzer-workspace')).gridTemplateColumns};})()`);
  if(narrow.overflow>1)throw new Error(`Narrow analyzer overflow: ${JSON.stringify(narrow)}`);
  if(errors.length)throw new Error(errors.join(" | "));
  socket.close();child.kill();console.log("TonyFX v0.58.0 analyzer visual checks passed.");
})().catch((error)=>{child.kill();console.error(error);process.exit(1);});
