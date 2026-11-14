// Isolated Electron/HTTP fixture. Never connects to the production backend or providers.
const {app,BrowserWindow} = require('electron');
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const ROOT=path.resolve(__dirname,'..');
const out=path.join(ROOT,'data','control-ui-fixture-proof.json');
app.setPath('userData',path.join(ROOT,'data','control-ui-fixture-profile'));
const history={assignmentId:'fixture-history',revision:1,station:'Plan',model:'gpt-6.1-terra',task:'Saved task with exact source clocks 12.300–14.700',status:'approved',summary:'Saved reviewed evidence.'};
const task={assignmentId:'fixture-task',revision:2,station:'Plan',model:'gpt-6.1-terra',task:'Inspect current shot plan without running AE.\n'+'Exact preserved source-clock evidence 12.300–14.700. '.repeat(40),status:'external handoff'};
const p={id:'fixture-project',name:'Isolated interface proof',revision:2,assignments:{'fixture-history':history,'fixture-task':task},notes:[],messages:[],activity:[],executiveEnabled:false};
const projects={'fixture-project':p};
let paused=true, mode='empty', lostOnce=false;
const requests=[];
const capabilities=[{model:'gpt-6.1-terra',label:'Terra',route:'codex',efforts:['low','medium','high'],capabilities:['supplied_text'],available:true},{model:'claude-fable-5-2',label:'Fable',route:'claude',efforts:['low','medium'],capabilities:['supplied_text'],available:true}];
const status=()=>({project:p.id,paused,pauseSettled:true,pauseReason:paused?'Old edit paused by human.':'',stations:['Director','Plan','Edit','Review','Deliver','Executive Director'].map(station=>({station,state:paused?'paused':station==='Plan'?'ready':'idle',model:station==='Plan'?'gpt-6.1-terra':null,task:station==='Plan'?task.task:'',updated:'2026-11-11T12:00:00Z',reason:paused?'Old edit paused by human.':'No invocation active.'})),capabilities,checkpoints:[{station:'Plan',title:'Saved checkpoint',summary:'Exact saved current evidence'}],routing:{},autonomyReason:'Text workers cannot edit AE.'});
const library=()=>({project:p.id,versions:mode==='empty'?[]:[{id:'fixture-cut',label:'Saved review MOV',path:'fixture.mov',needsProxy:true}],latest:mode==='empty'?null:'fixture-cut',emptyReason:'No saved cuts for fixture project.'});
const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1');
  const json=(data,code=200)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
  if(url.pathname==='/api/events'){res.writeHead(200,{'Content-Type':'text/event-stream'});res.write(': fixture only\n\n');return;}
  let body={}; if(req.method==='POST'){let bytes='';for await(const part of req)bytes+=part;body=JSON.parse(bytes);requests.push({path:url.pathname,...body});}
  if(url.pathname==='/api/workspace')return json({projects,token:'fixture-token',models:capabilities.map(r=>({...r,provider:r.route}))});
  if(url.pathname==='/api/production')return json({result:{jobs:[],native:{owner:null,integration:'TonyFX'},readiness:'Fixture only'}});
  if(url.pathname==='/api/services')return json({result:{media:{jobs:[]},jobs:[],events:[],speech:{engines:[],selected:''}}});
  if(url.pathname==='/api/review')return json(library());
  if(url.pathname==='/api/review-media'){res.writeHead(415);res.end('Fixture media not encoded');return;}
  if(url.pathname==='/api/control'){
    if(body.action==='status')return json({result:status()});
    if(body.action==='pause'){paused=true;return json({result:status()});}
    if(body.action==='continue'){
      if(!lostOnce){lostOnce=true;return json({error:'Fixture unresolved outcome; reconnect required.'},503);}
      return json({error:'Fixture route unsupported; no worker started.'},400);
    }
    if(body.action==='routing')return json({result:status()});
  }
  const rel=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
  if(!['index.html','workflow.css','editor.css','stations.js','studio.js','services.js','editor.js','executive.js','production.js','control.js'].includes(rel)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',rel.endsWith('.js')?'text/javascript':rel.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(ROOT,rel)));
});
app.whenReady().then(()=>new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))).then(async()=>{
  const win=new BrowserWindow({width:1440,height:1000,show:false,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
  const errors=[];win.webContents.on('console-message',(_event,...args)=>{const text=args.map(String).join(' ');if(/Uncaught|ReferenceError|TypeError/.test(text))errors.push(text);});
  const run=code=>win.webContents.executeJavaScript(code,true);
  const until=async expr=>{const deadline=Date.now()+8000;while(!await run(expr)){if(Date.now()>deadline)throw Error('Fixture deadline: '+expr);await new Promise(resolve=>setTimeout(resolve,30));}};
  const proof={fixtureOnly:true};
  try{
    await win.loadURL('http://127.0.0.1:'+server.address().port+'/');
    await until("!!controlState && !!el('nodes').children.length");
    await run("el('relay-close').click();el('nodes').querySelector('[data-stage=plan]').click()");
    proof.dedicatedStation=await run("expandedStation && getComputedStyle(document.querySelector('.graph-body')).display === 'none' && !el('station-work').hidden");
    proof.savedTaskNodes=await run("el('work-nodes').children.length===2 && el('work-nodes').textContent.includes('12.300')");
    proof.currentEvidence=await run("el('control-evidence').textContent.includes('Exact saved current evidence')");
    proof.compactSixStationCards=await run("getComputedStyle(el('crew-detail')).display==='grid' && el('crew-detail').querySelectorAll('.crew-station').length===6 && !el('crew-detail').textContent.includes('Old edit paused by human') && [...el('crew-detail').querySelectorAll('.crew-station-task')].every(n=>n.textContent.length<=130)");
    proof.compactPipelineTask=await run("el('nodes').querySelector('[data-stage=plan] .node-purpose').textContent.length<=130 && !el('nodes').querySelector('[data-stage=plan]').textContent.includes('Exact preserved')");
    proof.completeStationTask=await run("el('control-task-full').textContent.length>1800 && el('control-task-full').textContent.includes('12.300–14.700') && el('task').textContent.length<=130");
    proof.executivePauseSynced=await run("el('executive-node-status').textContent.startsWith('Paused')");
    await run("window.scrollTo(0,0);new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
    await win.webContents.capturePage().then(image=>fs.writeFileSync(path.join(ROOT,'data','control-ui-activity-fixture.png'),image.toPNG()));
    await run("el('work-nodes').querySelector('button').click()");
    proof.completeTaskRecord=await run("el('task-dialog-brief').textContent.length>1800");
    await run("el('close-task').click()");
    proof.pausedAndContinueDisabled=await run("el('control-project-state').textContent==='Project paused' && el('control-continue').disabled && el('control-pause').disabled");
    proof.currentTaskAndCapabilities=await run("el('control-task').textContent.includes('Inspect current shot plan') && el('control-owner').textContent.includes('gpt-6.1-terra') && el('control-capabilities').textContent.includes('Saved text only')");
    proof.noAutomaticExecution=requests.every(r=>!['continue','dispatch','pause'].includes(r.action));
    await run("el('control-model').value='claude-fable-5-2';el('control-model').dispatchEvent(new Event('change'))");
    proof.fableEffortGuard=await run("el('control-route').value==='claude' && [...el('control-effort').options].find(o=>o.value==='high').disabled");
    await run("el('collapse-work').click()");
    proof.backToPipeline=await run("!expandedStation && getComputedStyle(document.querySelector('.graph-body')).display!=='none'");
    await run("el('review-tab').click()");
    await until("el('review-library-state').textContent.includes('No saved cuts')");
    proof.emptyReviewHonest=await run("el('versions').disabled && !player.getAttribute('src')");
    mode='saved';await run("window.neuralReviewRefresh()");
    proof.automaticSavedReview=await run("versions.length===1 && chosen().id==='fixture-cut' && player.getAttribute('src').includes('/api/review-media?')");
    proof.proxyStatus=await run("el('versions').textContent.includes('proxy needed') && /proxy|could not be played/.test(el('review-library-state').textContent)");
    paused=false;await run("el('workflow-tab').click();el('nodes').querySelector('[data-stage=plan]').click();refreshControl()");
    await run("el('control-model').value='gpt-6.1-terra';el('control-model').dispatchEvent(new Event('change'));el('control-continue').click()");
    await until("!controlBusy && !!pendingRequest()");
    proof.unknownRequestRetained=await run("!!pendingRequest()?.requestId && el('control-feedback').textContent.includes('unresolved')");
    await run("el('control-continue').click()");await until("!controlBusy && !pendingRequest()");
    const continues=requests.filter(r=>r.action==='continue');
    proof.sameRequestReconciled=continues.length===2&&continues[0].requestId===continues[1].requestId;
    proof.rejectionVisible=await run("el('control-feedback').textContent.includes('unsupported')");
    await run("el('control-pause').click()");await until("!controlBusy && controlState.paused");
    proof.pauseWorks=paused&&await run("el('control-project-state').textContent==='Project paused'");
    proof.manualEditorUntouched=await run("view!=='edit' && !project().executiveEnabled");
    proof.consoleErrors=errors;
    proof.passed=Object.entries(proof).every(([key,value])=>key==='consoleErrors'?value.length===0:value===true);
    await run("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
    await win.webContents.capturePage().then(image=>fs.writeFileSync(path.join(ROOT,'data','control-ui-fixture.png'),image.toPNG()));
  }catch(error){proof.error=error.stack;proof.consoleErrors=errors;proof.requests=requests;proof.ui=await run("({notice:el('notice').textContent,feedback:el('control-feedback').textContent,disabled:el('control-continue').disabled,state:controlState,busy:controlBusy,pending:pendingRequest()})");proof.passed=false;}
  fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(proof,null,2));
  console.log(JSON.stringify(proof));win.destroy();server.closeAllConnections();server.close();app.exit(proof.passed?0:1);
}).catch(error=>{console.error(error);app.exit(1);});
