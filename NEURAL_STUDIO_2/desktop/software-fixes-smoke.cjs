// Read-only desktop verification. Uses the existing service; never starts a
// production service, provider, media job or native writer. Mutations below are
// confined to an isolated hidden renderer and restored before it is destroyed.
const {app, BrowserWindow} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
app.setPath('userData', path.join(root, 'data', 'software-smoke-profile'));
app.whenReady().then(async () => {
  let win, exitCode=0;
  try {
    const {url} = JSON.parse(fs.readFileSync(path.join(root,'.desktop-service.json'),'utf8'));
    if (!/^http:\/\/127\.0\.0\.1:\d+\/$/.test(url)) throw Error('Expected existing loopback Neural service');
    win = new BrowserWindow({show:false,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
    await win.loadURL(url);
    const proof = await win.webContents.executeJavaScript(`(async () => {
      const assert = (value,message) => { if (!value) throw Error(message); };
      // Startup GET/SSE callbacks may still be settling after DOM load.
      // Wait for their data without issuing extra status requests.
      for (let attempt=0;attempt<50 && (!controlState || controlState.project !== projectId);attempt++) await new Promise(resolve=>setTimeout(resolve,100));
      const live = controlState;
      assert(live && live.project === projectId, 'Live project status unavailable');
      const saved = controlState, savedRender = render, savedApi = api, savedRefresh = refreshControl, savedCall = controlCall;
      const result = {project:projectId,livePaused:live.paused,checks:[]};
      try {
        controlState = {...saved,paused:false,activity:{state:'blocked',label:'Production blocked',reason:'Fixture guard mismatch'}};
        window.neuralControlRender();
        assert(el('control-badge').textContent === 'Production blocked','False ready badge');
        assert(el('control-project-reason').textContent === 'Fixture guard mismatch','Blocker reason missing');
        result.checks.push('blocked state and exact reason visible');
        controlState = {...saved,paused:false,activity:{state:'needs_input',label:'Your answer is needed',reason:'Intro length?'},
          production:{id:'fixture-run',revision:project().revision,state:'WAIT_HUMAN',question:{id:'fixture-question',text:'Intro length?',choices:['30 seconds','48 seconds']}}};
        window.neuralControlRender();
        assert(!decisionPanel.hidden && el('decision-question').textContent === 'Intro length?', 'Question missing');
        assert(el('decision-choices').options.length === 3, 'Question choices missing');
        result.checks.push('persistent question and choices visible');
        let received, submitted = 0;
        controlCall = async (action,fields) => { assert(action === 'answer-question','Unexpected action'); received=fields; submitted++; return {}; };
        api=async()=>{};refreshControl=async()=>{};render=()=>{};
        el('decision-choices').value='30 seconds';
        const button=el('decision-form').querySelector('button');
        await el('decision-form').onsubmit({preventDefault(){},submitter:button});
        assert(submitted === 1 && received.questionId === 'fixture-question' && received.runId === 'fixture-run' && received.answer === '30 seconds' && received.revision === project().revision, 'Answer identity mismatch');
        assert(!button.disabled,'Answer button stuck');
        result.checks.push('answer submits exact project decision identity');
        controlState={...controlState,paused:true,activity:{state:'paused',label:'Paused',reason:'Human editing'}};
        window.neuralControlRender();
        assert(decisionPanel.hidden, 'Paused edit exposes resume decision');
        result.checks.push('paused edit hides decision continuation');
      } finally {
        controlState=saved;render=savedRender;api=savedApi;refreshControl=savedRefresh;controlCall=savedCall;
        render();
      }
      const oldService=service;
      try {
        service=async action => { assert(action === 'status','Local test attempted mutation');return {
          jobs:[{id:'local-fixture',project:projectId,model:'Kokoro',status:'completed',task:'Saved speech'}],
          media:{jobs:[{id:'active-fixture',project:projectId,title:'Extract review evidence',status:'RUNNING'},
                       {id:'saved-fixture',project:projectId,title:'Saved measurements',status:'COMPLETED'},
                       {id:'foreign-fixture',project:'foreign',title:'Foreign project must stay hidden',status:'RUNNING'}]},
          events:[{eventId:1,project:projectId,recipient:'Director',status:'COMPLETED',title:'First'},
                  {eventId:2,project:projectId,recipient:'Director',status:'COMPLETED',title:'Second'},
                  {eventId:3,project:'foreign',recipient:'Director',status:'FAILED',title:'Foreign event'}],
          speech:{engines:[],selected:''}}; };
        await refreshServices();
        assert(toolsButton.textContent === 'Local tools · 1 active','Active tool count incorrect');
        assert(document.querySelectorAll('.local-tool-node').length === 2,'Tool nodes missing');
        assert(!el('local-jobs').textContent.includes('Foreign project'),'Cross-project media leak');
        assert(el('completion-inbox').children.length === 1 && el('completion-inbox').firstChild.tagName === 'DETAILS','Completion events not grouped');
        assert(!el('completion-inbox').textContent.includes('Foreign event'),'Cross-project inbox leak');
        result.checks.push('local tool nodes, actual active count, grouped history and project isolation');
      } finally { service=oldService; }
      const oldReview=window.neuralReviewRefresh;
      try {
        let refreshed=0;window.neuralReviewRefresh=async()=>{refreshed++;};
        await relayCommand('Open review');
        assert(view === 'review' && refreshed === 1,'Relay did not open saved review library');
        result.checks.push('Relay opens saved Review workspace');
      } finally { window.neuralReviewRefresh=oldReview; }
      return {...result,passed:true,providerOrNativeSubmissions:0};
    })()`);
    fs.writeFileSync(path.join(root,'data','SOFTWARE_FIX_DESKTOP_PROOF.json'),JSON.stringify(proof,null,2));
    console.log(JSON.stringify(proof));
  } catch(error) {
    console.error(error.stack || error.message); exitCode=1;
  } finally { win?.destroy();app.exit(exitCode); }
});
