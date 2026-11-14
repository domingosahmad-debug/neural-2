/* Runs inside the actual desktop renderer, with short synthetic media only. */
(async () => {
  const report={};
  const wait=async test=>{for(let n=0;n<150;n++){if(test())return;await new Promise(r=>setTimeout(r,40));}throw new Error('Editor UI state did not arrive');};
  const post=async (route,body)=>{const r=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json','X-Neural-Token':token},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw new Error(j.error);return j;};
  await wait(()=>typeof token==='string'&&Object.keys(workspace).length>0);
  report.nativeImportBridge=typeof window.neuralDesktop?.selectMedia==='function';
  const created=await post('workspace',{action:'project',name:'Editor verification · synthetic media',brief:'Automated short cut proof. Synthetic media only, independent of active AE work.'});
  workspace=created.projects;selectProject(created.result.id);
  const fixture=JSON.parse(FIXTURE_JSON);
  await post('editor',{action:'import',project:projectId,revision:0,paths:[fixture+'/red.mp4',fixture+'/blue.mp4',fixture+'/music.wav']});
  document.querySelector('#edit-tab').click();await wait(()=>document.querySelectorAll('.edit-media').length===3);
  report.tabWorks=!document.querySelector('#edit-view').hidden;
  const q=id=>document.querySelector('#ed-'+id);
  document.querySelectorAll('.edit-media')[0].querySelector('button').click();
  document.querySelectorAll('.edit-media')[1].querySelector('button').click();
  report.addClips=q('clips').children.length===2;
  q('clips').children[0].click();q('out').value='1';q('trim').click();
  report.trim=q('clips').children[0].querySelector('small').textContent==='1.00s';
  q('seek').value='0.5';q('seek').dispatchEvent(new Event('input'));q('split').click();
  report.split=q('clips').children.length===3;
  q('undo').click();report.undo=q('clips').children.length===2;
  q('redo').click();report.redo=q('clips').children.length===3;
  q('right').click();report.reorder=q('clips').lastElementChild.getAttribute('aria-pressed')==='true';
  document.querySelectorAll('.edit-media')[2].querySelector('button').click();report.music=q('music-track').children.length===1;
  q('cap-text').value='Desktop proof';q('cap-start').value='0.1';q('cap-end').value='0.4';q('cap-save').click();report.caption=q('caps').children.length===1;
  q('format').value='1920x1080';q('format').dispatchEvent(new Event('change'));
  // Render at a small fixture canvas through the same validated persistence API.
  q('save').click();await wait(()=>q('saved').textContent.startsWith('Saved'));
  let doc=(await post('editor',{action:'load',project:projectId})).result.document;
  report.saved=doc.clips.length===3&&doc.captions.length===1&&!!doc.music;
  doc.width=320;doc.height=180;await post('editor',{action:'save',project:projectId,revision:doc.revision,document:doc});
  document.querySelector('#workflow-tab').click();
  // Force reload by selecting another project and returning through normal UI state.
  const testProject=projectId,other=Object.keys(workspace).find(id=>id!==testProject);selectProject(other);document.querySelector('#edit-tab').click();await wait(()=>q('media').children.length===0);selectProject(testProject);document.querySelector('#edit-tab').click();await wait(()=>q('media').children.length===3);
  report.reopened=q('clips').children.length===3&&q('caps').children.length===1;
  q('play').click();await wait(()=>document.querySelector('#ed-video').currentTime>.12);report.sourcePlayback=true;q('play').click();
  q('export').click();await wait(()=>q('exports').textContent.includes('completed'));
  report.exportCompleted=true;q('exports').querySelector('button').click();await wait(()=>q('output').readyState>=2);q('output').pause();report.renderPlayback=q('output').videoWidth===320;
  const m=(await post('editor',{action:'load',project:testProject})).result.document.media[0];
  const range=await fetch('/api/editor-media?project='+testProject+'&id='+m.id,{headers:{Range:'bytes=0-31'}});report.byteRange=range.status===206&&(await range.arrayBuffer()).byteLength===32;
  return report;
})()
