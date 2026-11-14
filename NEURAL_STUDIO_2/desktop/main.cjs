const {app, BrowserWindow, dialog, ipcMain} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const ROOT = path.resolve(__dirname, '..');
app.setName('Neural Studio 2');
app.setPath('userData', path.join(ROOT, '.desktop-profile'));
let child;
let window;
const locked = app.requestSingleInstanceLock();
if (!locked) app.quit();
app.on('second-instance', () => { if (window) { window.restore(); window.show(); window.focus(); } });
function get(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, {timeout: 1500}, response => {
      let text = '';
      response.on('data', part => text += part);
      response.on('end', () => {
        try { resolve(JSON.parse(text)); } catch (error) { reject(error); }
      });
    });
    request.on('error', reject);
    request.on('timeout', () => request.destroy(new Error('Service timeout')));
  });
}
app.whenReady().then(async () => {
  if (!locked) return;
  try {
    const log = fs.openSync(path.join(ROOT, 'desktop-service.log'), 'a');
    child = spawn('python', ['-u', path.join(ROOT, 'bootstrap.py'), '--port', '0'],
      {cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', log]});
    let output = '';
    const url = await new Promise((resolve, reject) => {
      child.stdout.on('data', data => {
        output += data;
        const match = output.split(' ').find(part => part.startsWith('http://127.0.0.1:'));
        const address = match && match.trim();
        if (address && address.endsWith('/')) resolve(address);
      });
      child.once('error', reject);
      child.once('exit', code => reject(new Error('Workspace service exited (' + code + ')')));
      setTimeout(() => reject(new Error('Workspace service took too long to start')), 20000).unref();
    });
    fs.writeFileSync(path.join(ROOT, '.desktop-service.json'), JSON.stringify({url}));
    const health = await get(url + 'api/workspace');
    if (health.application !== 'neural-studio-2') throw new Error('Unexpected workspace service');
    window = new BrowserWindow({width:1440, height:940, minWidth:760, minHeight:650,
      title:'Neural Studio 2', backgroundColor:'#f6f4f0', autoHideMenuBar:true,
      webPreferences:{nodeIntegration:false, contextIsolation:true, sandbox:true, preload:path.join(__dirname,'preload.cjs')}});
    const trusted = event => {
      if (event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !event.senderFrame.url.startsWith(url)) throw new Error('Untrusted editor request');
    };
    ipcMain.handle('editor:media', async event => {
      trusted(event);
      const result = await dialog.showOpenDialog(window,{title:'Import media into Edit',properties:['openFile','multiSelections'],filters:[{name:'Video and audio',extensions:['mp4','mov','webm','m4v','wav','mp3','m4a','aac','ogg']}]});
      return result.canceled ? [] : result.filePaths;
    });
    ipcMain.handle('editor:save-output', async (event,id) => {
      trusted(event);
      if (!/^[a-f0-9]{32}$/.test(id)) throw new Error('Invalid export');
      const folder = path.join(ROOT,'data','editor','exports',id);
      if (JSON.parse(fs.readFileSync(path.join(folder,'job.json'),'utf8')).status !== 'completed') throw new Error('Export is not complete');
      const result = await dialog.showSaveDialog(window,{title:'Save exported video',defaultPath:'Neural-edit.mp4',filters:[{name:'MP4 video',extensions:['mp4']}]});
      if (result.canceled) return null;
      await fs.promises.copyFile(path.join(folder,'output.mp4'),result.filePath);
      return result.filePath;
    });
    window.webContents.setWindowOpenHandler(() => ({action:'deny'}));
    window.webContents.on('will-navigate', (event, target) => {
      if (!target.startsWith(url)) event.preventDefault();
    });
    window.webContents.session.setPermissionRequestHandler((contents, permission, callback) => callback(false));
    await window.loadURL(url);
    if (process.argv.includes('--production-smoke-test')) {
      try {
        const result=await window.webContents.executeJavaScript(fs.readFileSync(path.join(__dirname,'production-smoke.cjs'),'utf8'));
        fs.writeFileSync(path.join(ROOT,'PRODUCTION_DESKTOP_PROOF.json'),JSON.stringify(result,null,2));
      } catch(error) {fs.writeFileSync(path.join(ROOT,'PRODUCTION_DESKTOP_PROOF.json'),JSON.stringify({error:error.stack||error.message}));}
    }
    if (process.argv.includes('--executive-smoke-test')) {
      try {
        const result=await window.webContents.executeJavaScript(fs.readFileSync(path.join(__dirname,'executive-smoke.cjs'),'utf8'));
        fs.writeFileSync(path.join(ROOT,'EXECUTIVE_DESKTOP_PROOF.json'),JSON.stringify(result,null,2));
      } catch(error) {fs.writeFileSync(path.join(ROOT,'EXECUTIVE_DESKTOP_PROOF.json'),JSON.stringify({error:error.stack||error.message}));}
    }
    if (process.argv.includes('--editor-smoke-test')) {
      try {
        const fixture = JSON.parse(fs.readFileSync(path.join(ROOT,'EDITOR_PROOF.json'),'utf8')).fixtureRoot;
        const source = fs.readFileSync(path.join(__dirname,'editor-smoke.cjs'),'utf8').replace('FIXTURE_JSON',JSON.stringify(JSON.stringify(fixture)));
        const result = await window.webContents.executeJavaScript(source);
        fs.writeFileSync(path.join(ROOT,'EDITOR_DESKTOP_PROOF.json'),JSON.stringify(result,null,2));
      } catch(error) { fs.writeFileSync(path.join(ROOT,'EDITOR_DESKTOP_PROOF.json'),JSON.stringify({error:error.stack||error.message})); }
    }
    if (process.argv.includes('--smoke-test')) {
      await new Promise(resolve => setTimeout(resolve, 1200));
      const report = await window.webContents.executeJavaScript(`(async () => {
        const result = {};
        result.projects = [...document.querySelector('#projects').options].map(o => o.text);
        document.querySelector('#theme').click();
        result.dark = document.documentElement.dataset.theme;
        document.querySelector('#theme').click();
        document.querySelector('#route-tab').click();
        result.routing = !document.querySelector('#route-panel').hidden;
        const picker = document.querySelector('#model-picker');
        result.modelChoices = picker.options.length - 1;
        picker.value = 'gpt-6.1-terra';
        picker.dispatchEvent(new Event('change'));
        result.modelSelected = document.querySelector('#model').value;
        document.querySelector('#model').value = 'Fable custom';
        document.querySelector('#model').dispatchEvent(new Event('input'));
        result.customModel = document.querySelector('#model').value;
        document.querySelector('#review-tab').click();
        result.review = !document.querySelector('#review-view').hidden;
        document.querySelector('#library-tab').click();
        result.knowledge = !document.querySelector('#library-view').hidden;
        result.motionGuide = document.querySelector('.motion-guide').textContent.includes('BlurMoCurves');
        document.querySelector('#workflow-tab').click();
        document.querySelector('#route-tab').click();
        document.querySelector('#model').value = '';
        result.nodes = document.querySelectorAll('.node').length;
        document.querySelector('.node[data-stage=plan]').click();
        result.stationExpansion = !document.querySelector('#station-work').hidden;
        result.emptyTaskState = document.querySelector('.work-empty')?.textContent.includes('No model assigned') ?? false;
        const savedWorkspace = workspace;
        try {
          workspace = JSON.parse(JSON.stringify(workspace));
          project().assignments = {
            a:{assignmentId:'a',station:'Plan',model:'Test model A',task:'Measure the reference music and zoom curves.',revision:project().revision,status:'external handoff'},
            b:{assignmentId:'b',station:'Review',model:'Test model B',task:'Review the bounded proof.',revision:project().revision,status:'needs review',summary:'Review evidence received.'},
            c:{assignmentId:'c',station:'Plan',model:'Earlier model',task:'Earlier plan retained as history.',revision:project().revision,status:'superseded',summary:'Earlier findings.'}
          };
          render();
          result.fixtureCounts = ['assigned-count','handoff-count','review-count'].map(id => document.getElementById(id).textContent.trim());
          result.taskHistory = document.querySelectorAll('.work-node').length === 2 && document.querySelectorAll('.work-node.historical').length === 1;
          document.querySelector('.work-node').click();
          result.taskDetails = document.querySelector('#task-dialog').open && document.querySelector('#task-dialog-brief').textContent.length > 0;
          document.querySelector('#task-dialog').close();
        } finally { workspace = savedWorkspace; expandedStation = false; selectStation('Director'); }
        openRelay();
        await relayCommand('What is happening?');
        result.relayStatus = document.querySelector('#relay-messages').textContent.includes('No models have assignments');
        await relayCommand('Show plan');
        result.relayNavigation = station === 'Plan' && !document.querySelector('#station-work').hidden;
        result.relayConnectionTruthful = document.querySelector('.relay-connection').textContent.includes('Qwen CPU assistant');
        const realService = service;
        const realRefresh = refreshServices;
        try {
          let starts = 0, polls = 0;
          refreshServices = async () => ({});
          service = async action => {
            if (action === 'dictate-start') { starts++; await new Promise(r => setTimeout(r, 25)); return {session:'fixture'}; }
            if (action === 'dictate-poll') { polls++; return {status:'idle',seq:1,events:[{type:'final',text:'fixture transcript'}]}; }
            return {};
          };
          document.querySelector('#relay-input').value = '';
          const start = document.querySelector('#dictate-start');
          start.click(); start.click();
          await new Promise(r => setTimeout(r, 80));
          result.dictationSingleStart = starts === 1 && polls === 1;
          result.dictationSingleAppend = document.querySelector('#relay-input').value === 'fixture transcript';
          service = async () => ({status:'error',seq:1,error:{code:'fixture',message:'Microphone privacy denied'},events:[]});
          await pollDictation(dictationGeneration);
          result.dictationErrorReadable = document.querySelector('#voice-state').textContent === 'Microphone privacy denied';
        } finally { service = realService; refreshServices = realRefresh; document.querySelector('#relay-input').value = ''; }
        document.querySelector('#relay-close').click();
        expandedStation = false; selectStation('Director');
        result.notice = document.querySelector('#notice').textContent;
        return result;
      })()`);
      fs.writeFileSync(path.join(ROOT, 'DESKTOP_SMOKE.json'), JSON.stringify(report, null, 2));
      // Visual proof is taken through the native desktop tool. A screenshot
      // failure must never close the workspace after successful control checks.
    }
  } catch(error) {
    fs.writeFileSync(path.join(ROOT, 'desktop-error.log'), error.stack || error.message);
    dialog.showErrorBox('Neural Studio 2', error.message); app.quit();
  }
});
app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => { if (child) child.kill(); });


