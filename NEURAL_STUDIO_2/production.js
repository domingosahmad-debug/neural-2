'use strict';
let productionJobs = [];
let productionRefresh = 0;
let productionSelectedAssignment = '';
async function production(action, fields = {}) {
  const response = await fetch('/api/production', {method:'POST',headers:{'Content-Type':'application/json','X-Neural-Token':token},body:JSON.stringify({action,...fields})});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Production request failed.');
  return data.result;
}
window.neuralProductionStatus = row => {
  const job = productionJobs.find(j => j.assignmentId === row.assignmentId);
  return job ? job.model + ' · ' + job.status : undefined;
};
const productionButton = item('Production crew', 'button');
el('relay-open').before(productionButton);
const productionPanel = document.createElement('dialog');
productionPanel.innerHTML = `<div class="dialog-top"><h2>Production crew</h2><button id="production-close">Close ×</button></div><p id="production-readiness"></p><p id="production-native"></p><p>Connected specialists receive the exact saved text packet. They cannot use After Effects or perceive video/audio. The Director keeps the single TonyFX writer.</p><h3>Run the selected station task</h3><label>Saved task <select id="production-assignment"></select></label><p id="production-selection"></p><label>Connection <select id="production-route"><option value="claude">Claude subscription</option><option value="codex">Codex subscription</option><option value="gemini">Gemini · Antigravity subscription</option><option value="opencode">OpenCode · free models only</option></select></label><label>Effort <select id="production-effort"><option value="medium">Medium</option><option value="low">Low</option><option value="high">High · unavailable for Fable</option></select></label><button id="production-run">Run saved task once</button><p id="production-error" role="status"></p><h3>Actual jobs</h3><div id="production-jobs"></div>`;
document.body.append(productionPanel);
el('production-effort').append(new Option('Default (OpenCode)', 'default'));
function updateProductionEffort() {
  const route=el('production-route').value, effort=el('production-effort');
  const model=project()?.assignments[el('production-assignment').value]?.model;
  const mediumOnly=['opus','gpt-6.1-sol','gpt-6-sol'].includes(model);
  const previousWasDefault=effort.value==='default';
  for(const option of effort.options) option.disabled=mediumOnly ? option.value!=='medium' : route==='gemini' ? option.value!=='high' : route==='opencode' ? option.value!=='default' : option.value==='default' || (route==='claude' && option.value==='high');
  effort.disabled=route==='opencode';
  if(mediumOnly) effort.value='medium';
  else if(route==='gemini') effort.value='high';
  else if(route==='opencode') effort.value='default';
  else if(previousWasDefault || (route==='claude' && effort.value==='high')) effort.value='medium';
}
function updateProductionSelection(forceRoute=false) {
  const choice=el('production-assignment'), selected=project()?.assignments[choice.value];
  el('production-selection').textContent=selected ? selected.station+' · '+selected.model+' — '+selected.task : 'Select a station and prepare its task under Model routing.';
  if(forceRoute || productionSelectedAssignment!==choice.value) {
    const model=selected?.model || '';
    if(model.startsWith('opencode/')) el('production-route').value='opencode';
    else if(model.startsWith('gemini-')) el('production-route').value='gemini';
    else if(model.startsWith('gpt-')) el('production-route').value='codex';
    else if(model.startsWith('claude-') || ['opus','sonnet','haiku'].includes(model)) el('production-route').value='claude';
  }
  productionSelectedAssignment=choice.value;
  updateProductionEffort();
}
el('production-assignment').onchange=()=>updateProductionSelection(true);
el('production-route').onchange=updateProductionEffort;
el('production-close').onclick = () => productionPanel.close();
productionButton.onclick = async () => { productionPanel.showModal(); await refreshProduction().catch(e=>{el('production-error').textContent=e.message;}); };
let dispatching = false;
el('production-run').onclick = async () => {
  if (dispatching) return;
  const row = project()?.assignments[el('production-assignment').value];
  if (!row || row.status !== 'external handoff') { el('production-error').textContent='Prepare a current station task first.'; return; }
  dispatching=true; el('production-run').disabled=true;
  try {
    await production('dispatch',{project:projectId,assignmentId:row.assignmentId,route:el('production-route').value,model:row.model,effort:el('production-effort').value,requestId:crypto.randomUUID()});
    el('production-error').textContent='Task admitted. Completion arrives through the saved event inbox.';
    await refreshProduction();
  } catch(e) { el('production-error').textContent=e.message; }
  finally { dispatching=false; el('production-run').disabled=false; }
};
async function refreshProduction() {
  if (!token) return;
  const seq=++productionRefresh, state=await production('status');
  // Jobs may be assigned by a different AI host. Reload saved metadata too;
  // status alone leaves every node permanently Unassigned in an open window.
  await api();
  if (seq!==productionRefresh) return;
  productionJobs=state.jobs;
  el('production-readiness').textContent=state.readiness;
  const native=state.native;
  el('production-native').textContent='AE writer: '+(native.owner?.owner || 'Unclaimed')+(native.unresolved ? ' · command outcome unresolved; reconcile before writing.' : ' · no unresolved command observed.');
  const choice=el('production-assignment'); const previous=choice.value;
  choice.replaceChildren(...Object.values(project()?.assignments || {}).filter(r=>r.revision===project().revision && r.status==='external handoff').map(r=>new Option(r.station+' · '+r.model,r.assignmentId)));
  if([...choice.options].some(o=>o.value===previous)) choice.value=previous;
  updateProductionSelection();
  const holder=el('production-jobs'); holder.replaceChildren();
  const rows=productionJobs.filter(j=>j.project===projectId);
  for (const job of rows) {
    const card=item('','article');
    card.append(item(job.station+' · '+job.model+' · '+job.status,'strong'),item(job.task || 'See saved station packet','p'));
    if(job.taskTruncated) card.append(item('Task preview truncated. Full saved packet: '+(job.packet_path || 'See the saved station packet.'),'p'));
    if(job.error) card.append(item(job.error,'p'));
    if(job.result?.text) {
      const detail=document.createElement('details'), output=item(job.result.text,'pre');
      detail.append(item(job.resultTruncated ? 'Read returned evidence (truncated preview)' : 'Read returned evidence','summary'),output);
      if(job.resultTruncated) {
        const label=item('Result preview truncated. Full saved result: '+(job.result_path || 'Use the button below.'),'p');
        const full=item('Fetch full saved result','button');
        full.onclick=async()=>{
          full.disabled=true;
          try {
            const result=await production('result',{id:job.id});
            output.textContent=typeof result.text==='string' ? result.text : JSON.stringify(result,null,2);
            label.textContent='Full saved result loaded.';
            full.remove();
          } catch(e) {el('production-error').textContent=e.message;full.disabled=false;}
        };
        detail.append(label,full);
      }
      card.append(detail);
    }
    if(['QUEUED','RUNNING','CANCELLING'].includes(job.status)) {const cancel=item('Cancel job','button');cancel.onclick=async()=>{try {await production('cancel',{id:job.id});await refreshProduction();} catch(e){el('production-error').textContent=e.message;}};card.append(cancel);}
    holder.append(card);
  }
  if(!rows.length) holder.append(item('No connected jobs for this project. Assignments alone do not mean a model is working.','p'));
  render();
  const activeJobs=rows.filter(j=>['QUEUED','RUNNING','CANCELLING'].includes(j.status));
  if(activeJobs.length && !window.neuralControlRender) {
    el('crew-summary').textContent=activeJobs.length+' connected job'+(activeJobs.length===1?'':'s')+' active';
    el('crew-detail').textContent=activeJobs.map(j=>j.model+' — '+j.station+': '+j.status+' — '+j.task).join(' / ');
  }
}
window.addEventListener('neural-ready',()=>refreshProduction().catch(e=>notice(e.message)));
eventStream.addEventListener('message',()=>refreshProduction().catch(e=>notice(e.message)));
