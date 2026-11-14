'use strict';

const el = id => document.getElementById(id);
let workspace = {};
let token;
let knowledge;
let modelCatalog = [];
let projectId;
let station = 'Director';
let view = 'workflow';
let routing = false;
let expandedStation = false;
let versions = [];
const player = el('player');
const project = () => workspace[projectId];
const active = () => Object.values(project()?.assignments ?? {}).filter(row =>
  row.revision === project().revision && row.status !== 'superseded' && row.station !== 'Executive Director');
const current = () => active().find(row => row.station === station);
const chosen = () => versions[Number(el('versions').value)];
const iconPaths = [
  'M5 19V5h14v14H5Zm4-9h6M9 14h4M9 2v3M15 2v3',
  'M5 4h14v16H5zM9 8h6M9 12h6M9 16h3',
  'm4 4 16 16M4 20l7-7m3-3 6-6M7 7a3 3 0 1 1-3-3m3 13a3 3 0 1 1-3 3',
  'M3 5h18v14H3zM8 22h8M12 19v3m-2-14 5 3-5 3z',
  'M4 14v6h16v-6M12 3v12m-5-7 5-5 5 5'
];
function stationIcon(index) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(svg.namespaceURI, 'path');
  path.setAttribute('d', iconPaths[index]);
  svg.append(path);
  return svg;
}

function notice(message = '') {
  el('notice').textContent = message;
  el('notice').hidden = !message;
}

async function api(action, fields) {
  const options = action ? {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Neural-Token': token},
    body: JSON.stringify({project: projectId, action, ...fields}),
  } : undefined;
  const response = await fetch('/api/workspace', options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Workspace request failed.');
  workspace = data.projects;
  knowledge = data.knowledge ?? knowledge;
  modelCatalog = data.models ?? modelCatalog;
  token = data.token ?? token;
  return data.result;
}

function list(id, items, build) {
  el(id).replaceChildren(...items.map(build));
}

function item(text, tag = 'li') {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

const statusLabel = status => ({'external handoff':'Waiting for external result', 'needs review':'Result received · needs review', approved:'Evidence approved', superseded:'Replaced by a later task'}[status] ?? status);
const productionStatus = row => window.neuralProductionStatus?.(row) ?? statusLabel(row.status);
function taskPreview(value, limit = 130) {
  const line = String(value || '').split(/\r?\n/).map(text => text.trim()).find(Boolean) || '';
  const sentence = line.replace(/^#+\s*/, '').split(/(?<=[.!?])\s+/)[0];
  return sentence.length > limit ? sentence.slice(0, limit - 1).trimEnd() + '…' : sentence;
}

function renderStationWork(p) {
  el('station-work').hidden = !expandedStation;
  el('workflow-view').classList.toggle('station-open', expandedStation);
  el('work-title').textContent = station + ' / Tasks & history';
  const records = Object.values(p.assignments).filter(row => row.station === station).reverse();
  el('work-description').textContent = records.length ? 'Saved task nodes stay here across sessions. Open a node to read the complete brief and returned evidence.' : 'No saved task nodes yet. Continue uses the project context to prepare this station’s next permitted task.';
  const nodes = records.map((row, index) => {
    const card = item('', 'button');
    card.className = 'work-node';
    const historical = row.revision !== p.revision || row.status === 'superseded';
    if (historical) card.classList.add('historical');
    card.append(item((historical ? 'History' : 'Current revision') + ' · r' + row.revision, 'small'),
      item(row.model, 'strong'), item(taskPreview(row.task), 'p'), item(productionStatus(row), 'span'));
    card.onclick = () => {
      el('task-dialog-title').textContent = row.station + ' · ' + row.model;
      el('task-dialog-meta').textContent = productionStatus(row) + ' · Revision ' + row.revision + (historical ? ' · Historical record' : '');
      el('task-dialog-brief').textContent = row.task;
      el('task-dialog-result').textContent = row.summary || 'No result has been returned for this task. Assigning a model alone does not confirm it is running.';
      el('task-dialog').showModal();
    };
    return card;
  });
  if (!records.length) {
    const empty = item('', 'div');
    empty.className = 'work-empty';
    empty.append(item('No saved task nodes', 'strong'), item('Choose a model above and Continue when the project is ready.', 'p'));
    const assign = item('Choose model ↑', 'button');
    assign.onclick = () => { el('control-model')?.focus(); };
    empty.append(assign);
    nodes.push(empty);
  }
  el('work-nodes').replaceChildren(...nodes);
}

function render() {
  const picker = el('model-picker');
  picker.replaceChildren(new Option('Choose a registered model…', ''),
    ...modelCatalog.map(row => new Option(row.label + ' · ' + row.provider, row.model)));
  picker.value = el('model').value;
  const p = project();
  el('project-form').hidden = view !== 'new';
  el('workflow-view').hidden = !p || view !== 'workflow';
  el('review-view').hidden = !p || view !== 'review';
  el('edit-view').hidden = !p || view !== 'edit';
  window.dispatchEvent(new CustomEvent('neural-edit-view',{detail:{project:projectId,active:!!p && view==='edit'}}));
  el('library-view').hidden = view !== 'library';
  el('debug-view').hidden = view !== 'debug';
  for (const name of ['workflow', 'edit', 'review', 'library', 'debug']) el(name + '-tab').setAttribute('aria-pressed', view === name);
  const select = el('projects');
  select.replaceChildren(new Option('Select project', ''),
    ...Object.values(workspace).map(row => new Option(row.name, row.id)));
  select.value = projectId ?? '';
  const entries = [];
  if (knowledge) {
    const folder = item('', 'article');
    folder.append(item('Project folder', 'strong'), item(knowledge.workspaceRoot, 'p'));
    entries.push(folder);
    const methods = item('', 'article');
    methods.append(item('Accepted editing workflow', 'strong'),
      ...knowledge.workflow.map(text => item(text, 'p')));
    entries.push(methods);
    const motion = item('', 'article');
    motion.className = 'motion-guide';
    motion.append(item('Motion & graph standards', 'strong'),
      ...knowledge.motionRules.map(text => item(text, 'p')));
    const measured = document.createElement('details');
    measured.append(item('Measured Dexter curve example', 'summary'),
      item(knowledge.portableKnowledge['tfx-motion-transitions/references/tony-dexter-impact-20261103.md'], 'pre'));
    motion.append(measured);
    entries.push(motion);
    for (const skill of knowledge.skills) {
      const article = item('', 'article');
      article.append(item(skill.name, 'strong'), item(skill.path, 'p'));
      entries.push(article);
    }
  }
  el('knowledge-list').replaceChildren(...entries);
  if (!p) return;
  const assignment = current();
  const rows = active();
  const waiting = rows.filter(row => row.status === 'external handoff');
  el('crew-summary').textContent = rows.length ? rows.length + ' assigned · ' + waiting.length + ' waiting for results' : 'No models assigned';
  el('crew-detail').textContent = rows.length ? rows.map(row => row.model + ' — ' + row.station + ': ' + productionStatus(row)).join(' / ') : 'No execution feed is connected. Open a station to see its tasks, models and saved history.';
  renderStationWork(p);
  el('assigned-count').replaceChildren(document.createTextNode(rows.length + ' '), item('/ 5', 'small'));
  el('handoff-count').textContent = rows.filter(row => row.status === 'external handoff').length;
  el('review-count').textContent = rows.filter(row => row.status === 'needs review').length;
  el('approved-count').textContent = rows.filter(row => row.status === 'approved').length;
  el('station-number').textContent = String(stations.findIndex(([name]) => name === station) + 1).padStart(2, '0') + ' / 05';
  el('revision').textContent = p.name + ' / Revision ' + p.revision;
  el('station').textContent = station;
  el('station-status').textContent = assignment ? assignment.model + ' · ' + productionStatus(assignment) : 'Unassigned';
  el('task').textContent = taskPreview(assignment?.task || stations.find(([name]) => name === station)[1]);
  el('result').textContent = assignment?.summary ?? '';
  el('next-action').textContent = assignment ? assignment.status + ' · ' + station : 'Prepare a task under Routing';
  el('brief-panel').hidden = routing;
  el('route-panel').hidden = !routing;
  el('brief-tab').setAttribute('aria-pressed', !routing);
  el('route-tab').setAttribute('aria-pressed', routing);
  el('brief-form').hidden = station !== 'Director';
  el('message-form').hidden = station !== 'Director';
  el('download-again').hidden = !assignment || assignment.status !== 'external handoff';
  el('event-count').textContent = p.activity.length + ' events';
  list('messages', p.messages, row => item(row.text));
  list('activity', p.activity, row => item(new Date(row.at).toLocaleTimeString() + ' · ' + row.text));
  el('nodes').replaceChildren(...stations.map(([name], index) => {
    const row = active().find(entry => entry.station === name);
    const button = item('', 'button');
    button.className = 'node';
    button.dataset.stage = name.toLowerCase();
    button.setAttribute('aria-pressed', name === station);
    const top = item('', 'span');
    top.className = 'node-top';
    const icon = item('', 'span');
    icon.className = 'node-icon';
    icon.append(stationIcon(index));
    top.append(icon, item('0' + (index + 1), 'span'));
    const title = item(name, 'strong');
    const purpose = item(taskPreview(row?.task || ['Creative direction', 'Reference & shot planning', 'Assembly & motion', 'Independent critique', 'Quality & handoff'][index]), 'span');
    purpose.className = 'node-purpose';
    purpose.title = purpose.textContent;
    const footer = item('', 'span');
    footer.className = 'node-footer';
    footer.append(item(row ? productionStatus(row) : 'Unassigned', 'small'), item(row?.model ?? 'Choose model', 'span'));
    footer.title = row ? row.model + ' · ' + row.status : 'No model assigned';
    button.append(top, title, purpose, footer);
    button.onclick = () => { expandedStation = true; selectStation(name); notice(); el('station-work').scrollIntoView({block:'nearest'}); };
    return button;
  }));
  list('review-results', Object.values(p.assignments).filter(row => row.summary).reverse(), row => {
    const article = item('', 'article');
    const status = row.revision === p.revision ? row.status : 'historical';
    article.append(item(row.station + ' · ' + row.model + ' · r' + row.revision + ' · ' + status, 'strong'),
      item(row.summary, 'p'));
    if (status === 'needs review') {
      const approve = item('Approve evidence', 'button');
      approve.onclick = () => act('approve', {assignmentId: row.assignmentId}, 'Evidence approved.');
      article.append(approve);
    }
    return article;
  });
  renderNotes();
  window.neuralControlRender?.();
}

function selectStation(name) {
  station = name;
  routing = false;
  el('model').value = current()?.model ?? '';
  el('assignment-task').value = current()?.task ?? stations.find(([label]) => label === name)[1];
  render();
  el('nodes').querySelector('[aria-pressed=true]')?.focus();
}

function selectProject(id) {
  expandedStation = false;
  projectId = id;
  localStorage.setItem('neural2-project', id ?? '');
  el('brief-text').value = project()?.brief ?? '';
  el('note-text').value = '';
  el('message-text').value = '';
  clearMedia();
  view = id ? 'workflow' : 'new';
  selectStation('Director');
  window.dispatchEvent(new Event('neural-project-changed'));
}

async function act(action, fields, success) {
  try {
    const result = await api(action, fields);
    render();
    notice(success);
    return result;
  } catch (error) {
    notice(error.message);
  }
}

function submit(id, run) {
  el(id).onsubmit = async event => {
    event.preventDefault();
    const buttons = [...event.currentTarget.querySelectorAll('button')];
    buttons.forEach(button => { button.disabled = true; });
    try { await run(); }
    finally {
      buttons.forEach(button => { button.disabled = false; });
      el('save-note').disabled = !chosen() || !Number.isFinite(player.duration);
    }
  };
}

function download(packet) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(packet, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'neural-' + packet.station.toLowerCase() + '-task.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

submit('project-form', async () => {
  const created = await act('project', {name: el('project-name').value, brief: el('project-brief').value}, 'Project created.');
  if (created) { selectProject(created.id); el('project-form').reset(); }
});
submit('brief-form', () => act('brief', {revision: project().revision, brief: el('brief-text').value}, 'New brief revision saved.'));
submit('message-form', async () => {
  try {
    const message=await window.neuralSendDirection(el('message-text').value);
    el('message-form').reset();notice(message);
  } catch(error) { notice(error.message); }
});
submit('assign-form', async () => {
  if (current() && !confirm('Supersede the current station assignment?')) return;
  const packet = await act('assign', {station, revision: project().revision, model: el('model').value,
    task: el('assignment-task').value}, 'Portable task saved. Open Advanced to download it when needed.');
  if (packet) render();
});
el('download-again').onclick = () => {
  const {status, ...packet} = current();
  if (status === 'external handoff') download(packet);
};
el('file').onchange = async () => {
  const file = el('file').files[0];
  const expectedProject = projectId;
  el('file').value = '';
  if (!file) return;
  try {
    if (file.size > 65536) throw new Error('Use a result JSON under 64 KB.');
    const data = JSON.parse(await file.text());
    if (expectedProject !== projectId || data?.project !== projectId ||
        data.schema !== 'neural.station-result.v2') throw new Error('Select a result for this project.');
    const {schema, revision, station, assignmentId, summary} = data;
    await act('result', {schema, revision, station, assignmentId, summary}, 'Result imported. Open Review to inspect it.');
  } catch (error) { notice(error.message); }
};

function clearMedia() {
  player.removeAttribute('src');
  player.load();
  versions.forEach(row => URL.revokeObjectURL(row.url));
  versions = [];
  el('media').value = '';
  el('versions').replaceChildren();
  el('versions').disabled = true;
  el('save-note').disabled = true;
}

function timecode(seconds) {
  const minutes = Math.floor(seconds / 60);
  return String(minutes).padStart(2, '0') + ':' + (seconds % 60).toFixed(2).padStart(5, '0');
}

function renderNotes() {
  const selected = chosen();
  list('notes', project()?.notes ?? [], row => {
    const note = item(row.version + ' · ' + row.text);
    const seek = item(timecode(row.seconds), 'button');
    seek.disabled = row.version !== selected?.label || !Number.isFinite(player.duration);
    seek.onclick = () => { player.currentTime = Math.min(row.seconds, player.duration); };
    note.prepend(seek);
    return note;
  });
}

function loadVersion(position = 0) {
  if (!chosen()) return;
  player.src = chosen().url;
  if (el('review-library-state')) el('review-library-state').textContent = chosen().needsProxy ? 'This is the ProRes master file, which the built-in player cannot decode. Pick the MP4 review copy of this cut; Deliver creates it after the render.' : 'Saved cut: ' + chosen().label;
  el('save-note').disabled = true;
  player.onerror = () => { if (el('review-library-state')) el('review-library-state').textContent = 'This cut could not be played. Its format may need a browser-compatible proxy; the saved source is preserved.'; };
  player.onloadedmetadata = () => {
    player.currentTime = Math.min(position, player.duration);
    el('scrub').max = player.duration;
    el('save-note').disabled = false;
    renderNotes();
  };
}

el('media').onchange = () => {
  const files = Array.from(el('media').files);
  if (!files.length) return;
  clearMedia();
  versions = files.map(file => ({label: file.name + ' · ' + file.size + ' B', url: URL.createObjectURL(file)}));
  el('versions').replaceChildren(...versions.map((row, index) => new Option(row.label, index)));
  el('versions').disabled = false;
  loadVersion();
};
el('versions').onchange = () => loadVersion(player.currentTime);
player.ontimeupdate = () => {
  el('scrub').value = player.currentTime;
  el('time').textContent = timecode(player.currentTime);
};
el('scrub').oninput = () => { if (Number.isFinite(player.duration)) player.currentTime = Number(el('scrub').value); };
for (const [id, delta] of [['back', -1], ['forward', 1]]) {
  el(id).onclick = () => {
    if (Number.isFinite(player.duration)) player.currentTime = Math.max(0, Math.min(player.duration, player.currentTime + delta));
  };
}
submit('note-form', async () => {
  if (chosen() && Number.isFinite(player.duration) && await act('note',
    {version: chosen().label, seconds: player.currentTime, text: el('note-text').value}, 'Review note saved.')) {
    el('note-form').reset();
  }
});

el('projects').onchange = () => selectProject(el('projects').value);
el('new-project').onclick = () => { view = 'new'; render(); el('project-name').focus(); };
el('debug-tab').onclick = () => { view = 'debug'; player.pause(); render(); window.dispatchEvent(new Event('neural-debug-view')); };
for (const name of ['workflow', 'edit', 'review', 'library']) {
  el(name + '-tab').onclick = () => {
    if (project()) { view = name; if (view !== 'review') player.pause(); render(); if (view === 'review') window.neuralReviewRefresh?.(); }
  };
}
el('brief-tab').onclick = () => { routing = false; render(); };
el('route-tab').onclick = () => { routing = true; render(); };
el('collapse-work').onclick = () => { expandedStation = false; render(); };
el('close-task').onclick = () => el('task-dialog').close();
function relaySay(text, operator = false) {
  const message = item('', 'li');
  message.className = operator ? 'operator-message' : 'relay-message';
  message.append(item(operator ? 'You' : 'Relay', 'strong'), item(text, 'p'));
  el('relay-messages').append(message);
  message.scrollIntoView({block:'nearest'});
}
function openRelay() {
  el('relay-panel').hidden = false;
  el('relay-open').setAttribute('aria-expanded', 'true');
  if (!el('relay-messages').children.length) relaySay('Welcome back. I can show saved tasks, open stations and reviews, and save director instructions. General questions use the local Qwen assistant. Dictate adds words to your draft; Speak reply prepares Kokoro audio. Production crew shows connected worker jobs and saved results. Each model route has its own capability and quota limits.');
  el('relay-input').focus();
}
async function relayCommand(text) {
  relaySay(text, true);
  const command = text.trim().toLowerCase();
  const p = project();
  if (!p) return relaySay('Choose or create a project first.');
  const directorNote = text.match(/^(?:tell|message|instruct)\s+(?:the\s+)?director\s*:\s*([\s\S]+)/i);
  if (directorNote) {
    try { relaySay(await window.neuralSendDirection(directorNote[1])); }
    catch (error) { relaySay(error.message); }
    return;
  }
  if (/\b(happening|status|working|progress|tasks)\b/.test(command)) {
    if (window.neuralCurrentActivity) {
      const current = await window.neuralCurrentActivity();
      if (!current) return relaySay('Live execution status is unavailable. I cannot confirm anyone is working.');
      const working = current.stations.filter(row => ['running','queued','unknown','stopping'].includes(row.state));
      return relaySay(current.activity.label + '. ' + current.activity.reason + '\n' + (working.length ? working.map(row => row.station + ' · ' + row.model + ' · ' + row.state + '\n' + row.task).join('\n\n') : 'No models are running or queued. Saved task history is available inside each station.'));
    }
    const rows = active();
    return relaySay(rows.length ? rows.map(row => row.model + ' / ' + row.station + '\n' + row.task + '\n' + statusLabel(row.status)).join('\n\n') + '\n\nThese are saved task records. Open a station for the current execution state.' : 'No models have assignments in this project revision. Open a station for its current execution state.');
  }
  if (/\b(review|screen|cut|video)\b/.test(command) && !/\bstation\b/.test(command)) { view = 'review'; render(); await window.neuralReviewRefresh?.(); return relaySay('Opened Review with the saved cuts for this project. Select a version to inspect it and add timecoded notes.'); }
  const target = stations.find(([name]) => new RegExp('\\b' + name.toLowerCase() + '\\b').test(command));
  if (target) {
    view = 'workflow'; expandedStation = true; selectStation(target[0]);
    if (/\b(assign|routing|model)\b/.test(command)) { routing = true; render(); }
    relaySay('Opened ' + target[0] + ' with its saved tasks and history.' + (target[0] === 'Director' ? ' To save an instruction, write “tell director: …”.' : ''));
    return;
  }
  if (/\b(review|screen|cut|video)\b/.test(command)) { view = 'review'; render(); return relaySay('Opened the review workspace. Load a local cut to inspect it and add timecoded notes.'); }
  if (/\b(knowledge|workflow|curve|graph|method)\b/.test(command)) { view = 'library'; render(); return relaySay('Opened Editing knowledge, including the measured motion and graph standards.'); }
  if (/\b(new project)\b/.test(command)) { view = 'new'; render(); return relaySay('Opened the new project form. Add the project name and creative brief there.'); }
  relaySay('I can currently check saved task status, open a station or review, show editing knowledge, and save a director instruction with “tell director: …”. This request needs a connected AI model; I have not executed it.');
}
el('relay-open').onclick = openRelay;
el('relay-close').onclick = () => { el('relay-panel').hidden = true; el('relay-open').setAttribute('aria-expanded', 'false'); el('relay-open').focus(); };
el('relay-form').onsubmit = async event => { event.preventDefault(); const text = el('relay-input').value.trim(); if (text) { el('relay-input').value = ''; await relayCommand(text); } };
for (const button of document.querySelectorAll('[data-relay]')) button.onclick = () => relayCommand(button.dataset.relay);
el('model-picker').onchange = event => { if (event.target.value) el('model').value = event.target.value; };
el('model').oninput = () => { el('model-picker').value = el('model').value; };
function theme(dark) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  el('theme').setAttribute('aria-pressed', dark);
  localStorage.setItem('neural2-dark', dark ? '1' : '0');
}
el('theme').onclick = () => theme(el('theme').getAttribute('aria-pressed') !== 'true');
theme(localStorage.getItem('neural2-dark') === '1');

api().then(async () => {
  const previous = localStorage.getItem('neural2-project');
  let selected = workspace[previous] ? previous : (workspace['tony-editing-workspace'] ? 'tony-editing-workspace' : Object.keys(workspace)[0]);
  // An untouched empty seed workspace must not hide the actual production project.
  if (!Object.keys(workspace[selected]?.assignments ?? {}).length) {
    try {
      const response = await fetch('/api/production', {method:'POST', headers:{'Content-Type':'application/json','X-Neural-Token':token}, body:JSON.stringify({action:'status'})});
      if (!response.ok) throw Error('Production status unavailable');
      const state = (await response.json()).result;
      const latest = [...state.jobs].filter(j => workspace[j.project]).sort((a,b) => b.created-a.created)[0];
      if (latest) selected = latest.project;
    } catch { notice('Could not load production status. The saved workspace is shown.'); }
  }
  selectProject(selected);
  window.dispatchEvent(new Event('neural-ready'));
  if (!sessionStorage.getItem('neural2-relay-welcome')) { openRelay(); sessionStorage.setItem('neural2-relay-welcome', '1'); }
}).catch(() => notice('Open Neural 2.0 through Launch-Neural-2.cmd to connect to the local workspace.'));

