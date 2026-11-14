'use strict';
// Execution state comes only from the control service; assignments are history.
let controlState = null;
let controlError = '';
let controlSequence = 0;
let controlBusy = false;
let controlFeedback = '';
let controlSelection = '';
let controlRenderModel = '';
const stateNames = {running:'Running',queued:'Queued',paused:'Paused',blocked:'Blocked',needs_review:'Needs review',completed:'Completed',idle:'Idle',ready:'Ready',stopping:'Stopping safely',unknown:'Unknown'};
const controlPanel = document.createElement('section');
controlPanel.className = 'station-control';
controlPanel.innerHTML = `<div class="control-heading"><span id="control-state" class="state-chip">Unknown</span><button id="control-refresh">Refresh status</button></div><h3 id="control-task">Checking current work</h3><details id="control-task-details"><summary>Read complete current task</summary><pre id="control-task-full"></pre></details><p id="control-owner"></p><p id="control-reason"></p><div class="control-routing"><label>Model<select id="control-model" aria-label="Station model"></select></label><label>Connection<select id="control-route" aria-label="Model connection"><option value="claude">Claude subscription</option><option value="codex">Codex subscription</option><option value="opencode">OpenCode free</option><option value="external">External host</option></select></label><label>Effort<select id="control-effort"><option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option><option value="default">Default</option></select></label></div><p id="control-capabilities" class="field-help"></p><div class="control-actions"><button id="control-continue" class="primary-action">Continue</button><button id="control-pause">Pause project</button></div><p id="control-feedback" role="status" aria-live="polite"></p><details><summary>Automatic fallback routing</summary><p>Only these explicitly saved candidates may be used. Unsupported routes remain blocked.</p><label>Fallback model<select id="control-fallback"></select></label><button id="control-save-routing">Save automatic routing</button><p id="control-routing-summary"></p></details><section class="station-evidence"><h3>Current evidence & checkpoints</h3><div id="control-evidence"></div></section>`;
el('work-description').after(controlPanel);
const projectBar = document.createElement('section');
projectBar.className = 'project-control-bar';
projectBar.innerHTML = '<div><strong id="control-project-state">Checking project status</strong><p id="control-project-reason"></p></div><button id="control-pause-top">Pause project</button>';
document.querySelector('.overview').before(projectBar);
const decisionPanel = document.createElement('section');
decisionPanel.className = 'project-decision'; decisionPanel.hidden = true; decisionPanel.setAttribute('role','alert');
decisionPanel.innerHTML = '<p class="eyebrow">Action needed · saved project decision</p><h3 id="decision-question"></h3><form id="decision-form"><label>Choose an answer<select id="decision-choices"></select></label><label>Or give a different answer<textarea id="decision-answer" rows="2" maxlength="4000" placeholder="Optional custom answer"></textarea></label><button class="primary-action" type="submit">Save answer & continue</button></form><p id="decision-feedback" aria-live="polite"></p>';
projectBar.after(decisionPanel);
let decisionIdentity = '';
function stationState(name = station) { return controlState?.project === projectId ? controlState.stations?.find(row => row.station === name) : null; }
function controlLabel(row) { return stateNames[String(row?.state || 'unknown').toLowerCase()] || 'Unknown'; }
function controlCapabilities() { return Array.isArray(controlState?.capabilities) ? controlState.capabilities : []; }
function capabilityModel(row) { return typeof row === 'string' ? row : row.model; }
function capabilityFor(model) { return controlCapabilities().find(row => capabilityModel(row) === model); }
function selectedCandidate() { return {model:el('control-model').value,route:el('control-route').value,effort:el('control-effort').value}; }
function controlKey() { return 'neural2-control-request:' + projectId + ':' + station; }
function pendingRequest() { try { return JSON.parse(sessionStorage.getItem(controlKey()) || 'null'); } catch { return null; } }
function controlOptions() {
  const model = el('control-model'), previous = model.value, fallback = el('control-fallback'), oldFallback = fallback.value;
  const candidates = controlCapabilities().filter(row => capabilityModel(row));
  const routePicker = el('control-route');
  for (const row of candidates) if (row.route && ![...routePicker.options].some(option => option.value === row.route)) routePicker.add(new Option(row.route + ' · host route',row.route));
  // The service lists effective routes. The general catalog remains visible if no route is connected.
  const rows = candidates.length ? candidates : modelCatalog;
  model.replaceChildren(new Option('Choose model…',''), ...rows.map(row => new Option((row.label || capabilityModel(row)) + (row.available === false ? ' · unavailable' : ''), capabilityModel(row))));
  const selection = projectId + ':' + station;
  const preferred = controlSelection === selection ? previous : stationState()?.model || current()?.model;
  controlSelection = selection;
  if ([...model.options].some(option => option.value === preferred)) model.value = preferred;
  fallback.replaceChildren(new Option('No fallback',''), ...rows.map(row => new Option(row.label || capabilityModel(row),capabilityModel(row))));
  fallback.value = oldFallback;
}
function updateControlCapability(inferRoute = false) {
  const model = el('control-model').value, cap = capabilityFor(model);
  if (inferRoute) el('control-route').value = cap?.route || (model.startsWith('gpt-') ? 'codex' : model.startsWith('claude-') || ['opus','sonnet','haiku'].includes(model) ? 'claude' : model.startsWith('opencode/') ? 'opencode' : 'external');
  const allowed = cap?.efforts || (model.includes('fable') ? ['low','medium'] : el('control-route').value === 'opencode' ? ['default'] : ['low','medium','high']);
  for (const option of el('control-effort').options) option.disabled = !allowed.includes(option.value);
  if (!allowed.includes(el('control-effort').value)) el('control-effort').value = allowed.includes('medium') ? 'medium' : allowed[0];
  const abilities = cap?.capabilities || cap?.effectiveCapabilities;
  el('control-capabilities').textContent = cap ? (Array.isArray(abilities) ? abilities.map(value => ({supplied_text:'Saved text only · cannot inspect media or operate AE'}[value] || value)).join(' · ') : abilities || cap.description || 'Saved text worker; actual route admission is checked by the service.') + (cap.reason ? ' · ' + cap.reason : '') : 'Capabilities are unverified for this selection. Continue checks the actual route before starting work.';
}
function evidenceCard(record) {
  const article = item('', 'article');
  if (typeof record === 'string') { article.append(item(record,'p')); return article; }
  article.append(item(record.title || record.task || record.name || record.id || 'Saved checkpoint','strong'));
  const detail = document.createElement('details');
  detail.append(item('Read complete saved evidence','summary'),item(JSON.stringify(record,null,2),'pre'));
  article.append(detail);
  return article;
}
window.neuralControlRender = () => {
  const valid = controlState?.project === projectId, row = stationState();
  const projectActivity = valid ? controlState.activity : null;
  const state = valid ? projectActivity?.label || (controlState.paused ? 'Paused' : 'Status unavailable') : 'Status unavailable';
  el('control-badge').textContent = state;
  el('control-project-state').textContent = state;
  projectBar.dataset.state = projectActivity?.state || 'unknown';
  projectBar.setAttribute('role', ['blocked','unknown','human_review','needs_review','needs_input'].includes(projectActivity?.state) ? 'alert' : 'status');
  el('control-project-reason').textContent = valid ? projectActivity?.reason || controlState.pauseReason || 'Execution state unavailable. Refresh the app after the service update.' : controlError || 'Waiting for the control service.';
  const question = valid && !controlState.paused && controlState.production?.state === 'WAIT_HUMAN' ? controlState.production.question : null;
  decisionPanel.hidden = !question;
  if (question && decisionIdentity !== projectId + ':' + question.id) {
    decisionIdentity = projectId + ':' + question.id;
    el('decision-question').textContent = question.text;
    el('decision-choices').replaceChildren(new Option('Choose an answer…',''), ...question.choices.map(choice => new Option(choice,choice)));
    el('decision-answer').value = ''; el('decision-feedback').textContent = '';
    notice('Your answer is needed: ' + question.text);
  }
  for (const button of el('nodes').children) {
    const name = stations.find(([name]) => name.toLowerCase() === button.dataset.stage)?.[0];
    const actual = stationState(name);
    button.dataset.state = actual?.state || 'unknown';
    const footer = button.querySelector('.node-footer');
    footer.replaceChildren(item(controlLabel(actual),'small'),item(actual?.model || 'No active model','span'));
    footer.title = [controlLabel(actual),actual?.model].filter(Boolean).join(' · ');
    const purpose = button.querySelector('.node-purpose');
    if (actual?.task) purpose.textContent = taskPreview(actual.task);
    purpose.title = purpose.textContent;
  }
  const rows = valid ? controlState.stations || [] : [];
  const running = rows.filter(r => r.state === 'running'), queued = rows.filter(r => r.state === 'queued');
  el('assigned-count').textContent = valid ? String(running.length) : '—';
  el('handoff-count').textContent = valid ? String(queued.length) : '—';
  el('review-count').textContent = valid ? String(['needs_input','human_review'].includes(projectActivity?.state) ? 1 : rows.filter(r => r.state === 'needs_review').length) : '—';
  el('approved-count').textContent = valid ? String(rows.reduce((count,r) => count + (r.jobs || []).filter(j => j.status === 'COMPLETED').length,0)) : '—';
  el('crew-summary').textContent = running.length + ' running · ' + queued.length + ' queued' + (valid && controlState.paused ? ' · project paused' : '');
  const activity = el('crew-detail');
  if (valid) activity.replaceChildren(...rows.map(r => {
    const card = item('', 'button');
    card.className = 'crew-station'; card.dataset.state = r.state;
    const top = item('', 'span'); top.className = 'crew-station-top';
    top.append(item(r.station, 'strong'), item(controlLabel(r), 'small'));
    const model = item(capabilityFor(r.model)?.label || r.model || 'No active model', 'span');
    model.className = 'crew-station-model'; model.title = r.model || '';
    const task = item(taskPreview(r.task) || 'No current task', 'span'); task.className = 'crew-station-task';
    const when = r.updated ? new Date(typeof r.updated === 'number' ? r.updated * 1000 : r.updated) : null;
    const time = item(when && !Number.isNaN(when.getTime()) ? when.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : 'No result time reported', 'small');
    time.className = 'crew-station-time';
    card.append(top, model, task, time);
    card.onclick = () => {
      if (r.station === 'Executive Director') { el('executive-open')?.click(); return; }
      expandedStation = true; selectStation(r.station); el('station-work').scrollIntoView({block:'start'});
    };
    return card;
  }));
  else activity.replaceChildren(item(controlError || 'Current execution status unavailable. Saved task history remains available.', 'p'));
  const executive = stationState('Executive Director');
  if (el('executive-node-status') && executive) el('executive-node-status').textContent = controlState.paused ? 'Paused · ' + (project()?.executiveEnabled ? 'enabled' : 'off') + (executive.model ? ' · ' + (capabilityFor(executive.model)?.label || executive.model) : '') : controlLabel(executive) + (executive.model ? ' · ' + (capabilityFor(executive.model)?.label || executive.model) : '');
  el('station-status').textContent = controlLabel(row) + (row?.model ? ' · ' + row.model : '');
  el('next-action').textContent = row?.reason || (valid && controlState.paused ? 'This edit is paused. Create a new project after the app repairs.' : 'Enter a station to inspect current work and continue.');
  el('control-state').textContent = controlLabel(row);
  el('control-state').dataset.state = row?.state || 'unknown';
  el('control-task').textContent = taskPreview(row?.task) || 'No current task';
  el('control-task-full').textContent = row?.task || '';
  el('control-task-details').hidden = !row?.task;
  if (row?.task) el('task').textContent = taskPreview(row.task);
  el('control-owner').textContent = (row?.model || 'No active model') + ' · Last result/status: ' + (row?.updated ? (typeof row.updated === 'number' ? new Date(row.updated * 1000).toLocaleString() : String(row.updated)) : 'not reported') + (row?.jobId ? ' · Job ' + row.jobId : '');
  el('control-reason').textContent = [row?.reason || (valid && controlState.paused ? controlState.pauseReason || 'Project paused.' : ''), controlState?.autonomyReason].filter(Boolean).join(' ');
  el('control-feedback').textContent = controlError || controlFeedback || (pendingRequest() ? 'Previous request outcome is unresolved. Continue will reconcile the same request; it will not create a duplicate.' : '');
  controlOptions(); updateControlCapability(controlRenderModel !== el('control-model').value);
  controlRenderModel = el('control-model').value;
  const checkpoints = valid ? (controlState.checkpoints || []).filter(record => !record.station || record.station === station) : [];
  const evidence = [...(Array.isArray(row?.evidence) ? row.evidence : row?.evidence ? [row.evidence] : []), ...checkpoints];
  el('control-evidence').replaceChildren(...(evidence.length ? evidence.map(evidenceCard) : [item('No current evidence registered for this station. Saved task results appear below.','p')]));
  el('control-routing-summary').textContent = valid ? JSON.stringify(controlState.routing?.[station] || controlState.routing || {}) : 'Routing status unavailable.';
  el('control-continue').disabled = controlBusy || !valid || controlState?.paused || ['running','queued','unknown','stopping'].includes(row?.state);
  el('control-pause').disabled = controlBusy || !valid || controlState.paused;
  el('control-pause-top').disabled = el('control-pause').disabled;
};
async function controlCall(action, fields = {}) {
  let response;
  try { response = await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Neural-Token':token},body:JSON.stringify({action,project:projectId,...fields})}); }
  catch (error) { error.unresolved = true; throw error; }
  let data;
  try { data = await response.json(); } catch { const error = Error('Response could not be read. Request outcome is unknown; reconcile before another attempt.'); error.unresolved = true; throw error; }
  if (!response.ok) { const error = Error(data.error || 'Control request rejected.'); error.unresolved = response.status >= 500 || /unknown|unresolved/i.test(error.message); throw error; }
  return data.result;
}
async function refreshControl() {
  if (!token || !projectId) return;
  const sequence = ++controlSequence, expected = projectId;
  try { const result = await controlCall('status'); if (sequence !== controlSequence || projectId !== expected) return; controlState = result; controlError = ''; }
  catch (error) { if (sequence !== controlSequence) return; controlState = null; controlError = error.message; }
  window.neuralControlRender();
}
window.neuralSendDirection = async text => {
  const pid=projectId, revision=project().revision;
  const state=await controlCall('status');
  if(projectId!==pid || project().revision!==revision) throw Error('Project changed. Send the direction to the intended project.');
  if(state.paused || !state.production || state.production.revision!==revision) {
    await api('message',{text});render();
    return state.paused ? 'Saved in the director notebook. This edit remains paused; no worker was started.' : 'Saved in the director notebook for the next task.';
  }
  const key='neural-direction:'+pid+':'+revision;
  let pending=JSON.parse(sessionStorage.getItem(key) || 'null');
  if(pending && pending.text!==text) throw Error('The previous direction has an unresolved reply. Retry that exact direction before sending a different one.');
  if(!pending) { pending={requestId:crypto.randomUUID(),text};sessionStorage.setItem(key,JSON.stringify(pending)); }
  try {
    await controlCall('steer',{revision,...pending});sessionStorage.removeItem(key);
  } catch(error) { if(!error.unresolved) sessionStorage.removeItem(key);throw error; }
  await api();await refreshControl();render();
  return 'Direction saved. Obsolete work is fenced; Neural will replan after the current provider and native actions settle safely.';
};
async function runControl(action, fields) {
  if (controlBusy) return;
  controlBusy = true; controlError = ''; controlFeedback = ''; window.neuralControlRender();
  const expected = projectId, requestKey = controlKey();
  try {
    const result = await controlCall(action,fields);
    if (action === 'continue' && !['unknown','UNKNOWN'].includes(result?.state || result?.status)) sessionStorage.removeItem(requestKey);
    if (projectId !== expected) return;
    await api(); await refreshControl(); render();
    controlFeedback = result?.message || (action === 'pause' ? 'Project paused. Existing job outcomes remain visible.' : action === 'routing' ? 'Routing saved.' : 'Continue request accepted. Current state is shown above.');
  } catch (error) {
    if (action === 'continue' && !error.unresolved) sessionStorage.removeItem(requestKey);
    controlError = error.message + (error.unresolved ? ' Outcome unresolved; the same request ID is retained.' : '');
  } finally { controlBusy = false; window.neuralControlRender(); }
}
el('decision-form').onsubmit = async event => {
  event.preventDefault();
  const run = controlState?.production, question = run?.question;
  if (!question || controlState.project !== projectId || controlState.paused) return;
  const answer = el('decision-answer').value.trim() || el('decision-choices').value;
  if (!answer) { el('decision-feedback').textContent = 'Choose an answer or write your own.'; return; }
  const button = event.submitter; button.disabled = true;
  try {
    await controlCall('answer-question',{runId:run.id,revision:run.revision,questionId:question.id,answer});
    await api(); await refreshControl(); render();
  } catch (error) { el('decision-feedback').textContent = error.message; }
  finally { button.disabled = false; }
};
el('control-model').onchange = () => { controlRenderModel = el('control-model').value; updateControlCapability(true); };
el('control-route').onchange = () => updateControlCapability();
el('control-refresh').onclick = refreshControl;
el('control-continue').onclick = () => {
  const saved = pendingRequest(), candidate = selectedCandidate();
  if (!saved && !candidate.model) { controlError = 'Choose a model before continuing.'; window.neuralControlRender(); return; }
  const fields = saved || {...candidate,station,requestId:crypto.randomUUID()};
  sessionStorage.setItem(controlKey(),JSON.stringify(fields));
  runControl('continue',fields);
};
el('control-pause').onclick = el('control-pause-top').onclick = () => runControl('pause',{reason:'Paused by user in Neural Studio.'});
el('control-save-routing').onclick = () => {
  const primary = selectedCandidate(), fallback = el('control-fallback').value, candidates = [primary];
  if (!primary.model) { controlError = 'Choose a primary model before saving routing.'; window.neuralControlRender(); return; }
  if (fallback && fallback !== primary.model) {
    const cap = capabilityFor(fallback);
    if (!cap?.route) { controlError = 'Fallback route is unverified. Choose a model with an effective connected route.'; window.neuralControlRender(); return; }
    candidates.push({model:fallback,route:cap.route,effort:cap.efforts?.includes('medium') ? 'medium' : cap.efforts?.[0] || 'medium'});
  }
  runControl('routing',{station,candidates,automatic:true});
};
window.addEventListener('neural-ready',refreshControl);
window.addEventListener('neural-project-changed',() => { controlFeedback = ''; controlError = ''; controlState = null; refreshControl(); });
eventStream.addEventListener('message',refreshControl);
eventStream.addEventListener('open',refreshControl);
window.addEventListener('focus',refreshControl);
window.neuralCurrentActivity = async () => { await refreshControl(); return controlState?.project === projectId ? controlState : null; };

// The library binds saved review exports to the current project. No file picker is needed.
let reviewSequence = 0;
let reviewManual = false;
let reviewLoadedProject = '';
el('media').addEventListener('change', () => { reviewManual = true; });
window.neuralReviewRefresh = async () => {
  if (!projectId) return;
  const sequence = ++reviewSequence, expected = projectId;
  try {
    const response = await fetch('/api/review?project=' + encodeURIComponent(expected));
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Saved cut library unavailable.');
    if (sequence !== reviewSequence || projectId !== expected) return;
    const library = data.result || data;
    const rows = library.versions || [];
    if (reviewManual && reviewLoadedProject === expected) { el('review-library-state').textContent = 'Showing local files · ' + rows.length + ' saved project cuts available.'; return; }
    const previous = chosen()?.id;
    const unchanged = reviewLoadedProject === expected && versions.length === rows.length && versions.every((row,index) => row.id === rows[index].id);
    if (unchanged) return;
    versions.filter(row => row.url?.startsWith('blob:')).forEach(row => URL.revokeObjectURL(row.url));
    versions = rows.map(row => ({...row,url:'/api/review-media?project=' + encodeURIComponent(expected) + '&version=' + encodeURIComponent(row.id)}));
    reviewLoadedProject = expected;
    el('versions').replaceChildren(...versions.map((row,index) => new Option(row.label + (row.needsProxy ? ' · proxy needed' : ''),index)));
    el('versions').disabled = !versions.length;
    if (!versions.length) { player.removeAttribute('src'); player.load(); el('save-note').disabled = true; el('review-library-state').textContent = library.emptyReason || 'No saved review exports for this project yet.'; return; }
    const selected = versions.findIndex(row => row.id === previous || !previous && row.id === library.latest);
    el('versions').value = String(Math.max(0,selected));
    loadVersion();
  } catch (error) { if (sequence === reviewSequence) el('review-library-state').textContent = error.message + ' Saved files have not been changed.'; }
};
window.addEventListener('neural-ready',window.neuralReviewRefresh);
window.addEventListener('neural-project-changed',() => { reviewManual = false; reviewLoadedProject = ''; window.neuralReviewRefresh(); });
eventStream.addEventListener('message',window.neuralReviewRefresh);
// Workspace fetch can finish before this final script is parsed.
if (token && projectId) { refreshControl(); window.neuralReviewRefresh(); }
