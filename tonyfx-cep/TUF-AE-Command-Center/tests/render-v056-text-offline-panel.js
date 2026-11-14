const fs = require("fs");
const path = require("path");
const {spawn} = require("child_process");

const chrome = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = 9357;
const profile = path.join(process.env.TEMP,"tonyfx-v056-text-offline-profile");
const child = spawn(chrome,["--headless=new",`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,"--allow-file-access-from-files","--window-size=1180,940","about:blank"],{stdio:"ignore"});
const sleep = (ms) => new Promise((resolve)=>setTimeout(resolve,ms));

async function endpoint(){for(let i=0;i<60;i++){try{const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();const page=pages.find((item)=>item.type==="page");if(page)return page.webSocketDebuggerUrl;}catch(_){}await sleep(100);}throw new Error("Chrome did not expose a DevTools endpoint.");}

(async()=>{
  const socket=new WebSocket(await endpoint());
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let id=0;const pending=new Map(),errors=[];
  socket.onmessage=(event)=>{const message=JSON.parse(event.data);if(message.method==="Runtime.exceptionThrown")errors.push(message.params.exceptionDetails.exception.description);if(message.id&&pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);message.error?item.reject(new Error(message.error.message)):item.resolve(message.result);}};
  const send=(method,params={})=>new Promise((resolve,reject)=>{const command=++id;pending.set(command,{resolve,reject});socket.send(JSON.stringify({id:command,method,params}));});
  const evaluate=async(expression)=>{const result=await send("Runtime.evaluate",{expression,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception.description);return result.result.value;};
  await send("Page.enable");await send("Runtime.enable");
  const url=encodeURI(`file:///${path.resolve(__dirname,"../index.html").replace(/\\/g,"/")}`);await send("Page.navigate",{url});
  for(let i=0;i<60;i++){if(await evaluate("document.readyState==='complete' && !!window.TonyFXCore"))break;await sleep(100);}
  const state=await evaluate(`(()=>{document.querySelector('[data-tab="create"]').click();const composer=document.querySelector('.text-composer');const rect=composer.getBoundingClientRect();const textOk=['textComposeValue','textComposeAnimation','textComposePlacement','textComposeDuration','textComposeEntry','textComposeExit','textComposeMatchedExit','createStyledText'].every(id=>!!document.getElementById(id));document.querySelector('[data-tab="analyze"]').click();const offline=document.querySelector('.offline-builder-card');offline.scrollIntoView();const offRect=offline.getBoundingClientRect();const offlineOk=['offlineBlurMo','offlineFullStack','buildOfflineEdit'].every(id=>!!document.getElementById(id));return{textOk,offlineOk,textWidth:rect.width,offlineWidth:offRect.width,overflow:document.documentElement.scrollWidth-innerWidth,version:document.querySelector('.version').textContent};})()`);
  if(!state.textOk||!state.offlineOk||state.textWidth<400||state.offlineWidth<320||state.overflow>1||state.version!=="v0.56.0")throw new Error(`TonyFX v0.56 UI failed: ${JSON.stringify(state)}`);
  const shot=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});fs.writeFileSync(path.resolve(__dirname,"tonyfx-v056-text-offline.png"),Buffer.from(shot.data,"base64"));
  await send("Emulation.setDeviceMetricsOverride",{width:430,height:780,deviceScaleFactor:1,mobile:false});await send("Page.reload",{ignoreCache:true});await sleep(700);
  const narrow=await evaluate(`(()=>{document.querySelector('[data-tab="create"]').click();return{overflow:document.documentElement.scrollWidth-innerWidth,columns:getComputedStyle(document.querySelector('.text-composer-grid')).gridTemplateColumns};})()`);
  if(narrow.overflow>1)throw new Error(`Narrow TonyFX v0.56 overflow: ${JSON.stringify(narrow)}`);
  if(errors.length)throw new Error(errors.join(" | "));
  socket.close();child.kill();console.log("TonyFX v0.56.0 text and offline-builder visual checks passed.");
})().catch((error)=>{child.kill();console.error(error);process.exit(1);});
