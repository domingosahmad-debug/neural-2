/* Optional one-pass planning station. Never schedules a provider or a model timer. */
(() => {
  const node=document.createElement('section');node.className='executive-node';node.setAttribute('aria-label','Optional Executive Director station');
  node.innerHTML='<div><span class="eyebrow">Optional · above Director</span><h2>Executive Director</h2><p id="executive-node-status">Off · no usage</p></div><button id="executive-open">Open station ↗</button>';
  document.querySelector('.production .canvas').before(node);
  const dialog=document.createElement('dialog');dialog.id='executive-dialog';dialog.setAttribute('aria-labelledby','executive-title');
  dialog.innerHTML=`<div class="dialog-top"><p class="eyebrow">One planning pass · outside the normal pipeline</p><button id="executive-close">Close ×</button></div><h2 id="executive-title">Executive Director</h2><p>Read the request, choose a capable crew, and give Director a clear plan. This station does no editing and never runs continuously.</p><div class="executive-switch"><strong id="executive-enabled-state"></strong><button id="executive-toggle">Enable station</button></div><p class="field-help">Enabling opens the station. It does not start a model. Any AI host can read the downloaded task or use station_cli.py.</p><form id="executive-form"><label>Planning model<select id="executive-picker" aria-label="Executive model list"></select><input id="executive-model" maxlength="100" placeholder="Or type any model, e.g. Fable or Astra" required></label><label>Planning request<textarea id="executive-task" maxlength="12000" rows="4" required placeholder="Check this brief, verify capabilities and quota, choose the models/stations, define dependencies and acceptance checks. Return one plan and stop."></textarea></label><button id="executive-create">Create and download planning task</button></form><p id="executive-status" role="status"></p><section id="executive-result"></section><label>Return the planning result<input id="executive-file" type="file" accept=".json,application/json"></label><p class="field-help">Live provider quotas are not connected here. The planner must check its host or label availability unverified. Applying an approved plan creates station handoffs; it does not launch external AIs.</p>`;
  document.body.append(dialog);
  const $=id=>document.getElementById('executive-'+id);
  const row=()=>Object.values(project()?.assignments||{}).reverse().find(r=>r.station==='Executive Director'&&r.revision===project().revision&&r.status!=='superseded');
  const say=(text)=>{$('status').textContent=text;};
  let pending=false;
  async function action(name,fields={}){if(pending)return;pending=true;try{const result=await api(name,fields);render();paint();return result;}catch(e){say(e.message);}finally{pending=false;}}
  function paint(){
    const p=project();if(!p){if(dialog.open)dialog.close();return;}
    const enabled=!!p.executiveEnabled,r=row();$('node-status').textContent=enabled ? (r?`${r.model} · ${r.status}${r.applied?' · handed off':''}`:'Enabled · awaiting explicit assignment'):'Off · no usage';
    $('enabled-state').textContent=enabled?'Station enabled':'Station off';$('toggle').textContent=enabled?'Disable station':'Enable station';
    for(const field of $('form').elements)field.disabled=!enabled;
    $('file').disabled=!enabled||!r||r.status!=='external handoff';
    const value=$('model').value;$('picker').replaceChildren(new Option('Choose a registered model…',''),...modelCatalog.map(m=>new Option(m.label+' · '+m.provider,m.model)));$('picker').value=value;
    const result=$('result');result.replaceChildren();
    if(!r){result.append(item('No task has been assigned. This station stays idle.','p'));return;}
    result.append(item(r.model+' · '+r.status,'strong'),item(r.task,'p'));
    if(r.status==='external handoff'){const b=item('Download current task','button');b.onclick=()=>download(r);result.append(b);}
    if(r.summary){result.append(item(r.summary,'p'));const list=document.createElement('ol');for(const a of r.allocationPlan||[]){const li=item(`${a.station} → ${a.model}: ${a.task}`);li.append(item('Acceptance: '+a.acceptance,'p'),item('Availability: '+a.availabilityEvidence,'small'));list.append(li);}result.append(list);}
    if(r.status==='needs review'){const b=item('Approve plan evidence','button');b.onclick=()=>action('approve',{assignmentId:r.assignmentId});result.append(b);}
    if(r.status==='approved'&&!r.applied){const b=item('Apply plan · replace matching station handoffs','button');b.disabled=!enabled;b.onclick=async()=>{const out=await action('executive-apply',{assignmentId:r.assignmentId});if(out){for(const packet of out.packets){const b=item('Download '+packet.station+' task','button');b.onclick=()=>download(packet);result.append(b);}say('Director note and station packets saved. External models have not been started.');}};result.append(b);}
    if(r.applied){result.append(item('Plan handed off. Executive Director is idle. Download each task from its station’s Routing panel.','p'));}
  }
  $('open').onclick=()=>{say('');paint();dialog.showModal();};$('close').onclick=()=>dialog.close();
  $('toggle').onclick=()=>action('executive-enable',{enabled:!project().executiveEnabled});
  $('picker').onchange=()=>{$('model').value=$('picker').value;};
  $('form').onsubmit=async e=>{e.preventDefault();const out=await action('assign',{station:'Executive Director',revision:project().revision,model:$('model').value,task:$('task').value});if(out){download(out);say('Planning task prepared. Give it to the selected AI; no provider was started automatically.');}};
  $('file').onchange=async()=>{const file=$('file').files[0];if(!file)return;try{if(file.size>65536)throw new Error('Use a result JSON under 64 KB.');const data=JSON.parse(await file.text());if(data.station!=='Executive Director'||data.project!==projectId)throw new Error('Result belongs to a different station or project.');const fields={};for(const key of ['schema','project','revision','station','assignmentId','summary','allocationPlan'])fields[key]=data[key];await action('result',fields);}catch(e){say(e.message);}finally{$('file').value='';}};
  window.addEventListener('neural-edit-view',paint);paint();
})();
