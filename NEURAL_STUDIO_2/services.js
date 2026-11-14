'use strict';
let service = async (action, data = {}) => {
  const response = await fetch('/api/services', {method:'POST', headers:{'Content-Type':'application/json', 'X-Neural-Token':token}, body:JSON.stringify({action, ...data})});
  const payload = await response.json();
  if (!response.ok) throw Error(payload.error || 'Local service failed.');
  return payload.result;
};
const toolsButton = document.createElement('button');
toolsButton.textContent = 'Local tools';
el('relay-open').before(toolsButton);
const toolsPanel = document.createElement('dialog');
const mediaProgress = document.createElement('section');
mediaProgress.className = 'crew-panel';
mediaProgress.setAttribute('aria-live', 'polite');
mediaProgress.hidden = true;
el('crew-detail').parentElement.after(mediaProgress);
toolsPanel.id = 'local-tools';
toolsPanel.innerHTML = `<div class="dialog-top"><p class="eyebrow">On this PC · separate from original production</p><button id="tools-close">Close ×</button></div><h2>Local crew & tools</h2><p>CPU processing. Jobs save their real results here. Nothing controls After Effects.</p><form id="probe-form"><label>Inspect a media file <input id="probe-path" placeholder="Full local file path" required></label><button>Measure file</button></form><h3>Recent work</h3><div id="local-jobs"></div>`;
document.body.append(toolsPanel);
let dictationTimer, dictationSession, dictationSeq = 0;
let lastReply = '';
const originalRelaySay = relaySay;
relaySay = (text, operator = false) => { if (!operator) lastReply = String(text); return originalRelaySay(text,operator); };
let dictationGeneration = 0;
let dictationStarting = false;
const completedShown = new Set();
let refreshSequence = 0;
async function refreshServices() {
  const sequence = ++refreshSequence;
  const state = await service('status');
  if (sequence !== refreshSequence) return state;
  const mediaRows = (state.media.jobs || []).filter(j => j.project === projectId);
  const mediaActive = mediaRows.filter(j => ['QUEUED','RUNNING','CANCELLING'].includes(j.status));
  mediaProgress.hidden = !mediaActive.length && !mediaRows.some(j => j.status === 'FAILED');
  mediaProgress.replaceChildren(item(mediaActive.length ? 'Local footage processing is running' : 'Local footage processing · saved results', 'strong'),
    ...mediaRows.slice(0,3).map(j => item(j.title + ' — ' + j.status + (j.current_step ? ' — ' + j.current_step : ''), 'p')));
  const localRows = state.jobs.filter(j => !j.project || j.project === projectId);
  const localActive = localRows.filter(j => ['queued','running','cancelling'].includes(j.status));
  const relevantEvents = state.events.filter(e => e.project === projectId || !e.project);
  toolsButton.textContent = 'Local tools' + (mediaActive.length + localActive.length ? ' · ' + (mediaActive.length + localActive.length) + ' active' : ' · idle');
  const holder = el('local-jobs'); holder.replaceChildren();
  const history = document.createElement('details');
  history.append(item('Saved job history', 'summary'));
  const toolGroups = new Map();
  function toolCard(name, active) {
    if (!toolGroups.has(name)) {
      const card = document.createElement('article'); card.className = 'local-tool-node';
      card.append(item(name, 'strong'), item(active ? 'Working' : 'Idle · saved results below', 'p'));
      holder.append(card); toolGroups.set(name,card);
    } else if (active) toolGroups.get(name).children[1].textContent = 'Working';
    return toolGroups.get(name);
  }
  for (const row of localRows) {
    const card = document.createElement('article');
    card.append(item(row.model + ' · ' + row.status, 'strong'), item(row.task, 'p'));
    if (row.error) card.append(item(row.error, 'p'));
    if (row.result?.text) card.append(item(row.result.text, 'p'));
    if (row.result?.audio) { const audio = document.createElement('audio'); audio.controls = true; audio.src = row.result.audio; card.append(audio); }
    const working = ['queued','running','cancelling'].includes(row.status);
    const tool = toolCard(row.model || 'Local assistant', working);
    if (working || ['failed','interrupted'].includes(row.status)) tool.append(card); else history.append(card);
    if (row.status === 'completed' && pendingReplies.has(row.id) && !completedShown.has(row.id)) {
      completedShown.add(row.id); pendingReplies.delete(row.id);
      if (row.result?.text) { lastReply = row.result.text; relaySay(lastReply); }
      else if (row.result?.audio) {
        relaySay('Kokoro speech is ready.');
        const audio = document.createElement('audio'); audio.controls = true; audio.src = row.result.audio;
        el('relay-messages').append(audio);
        audio.play().catch(() => { el('voice-state').textContent = 'Speech ready. Press Play in Relay to listen.'; });
      }
    }
    if (['failed','interrupted'].includes(row.status) && pendingReplies.has(row.id)) {
      pendingReplies.delete(row.id); relaySay(row.model + ': ' + (row.error || row.status) + ' No retry was started.');
    }
  }
  for (const row of mediaRows) {
    const card = document.createElement('article');
    card.append(item(row.title + ' · ' + row.status + (row.error ? ' · ' + row.error : ''), 'p'));
    if (row.status === 'COMPLETED') {
      const button = item('Show measurements', 'button');
      button.onclick = async () => {
        try { const result = await service('media-result', {id:row.id}); const details = item(JSON.stringify(result, null, 2), 'pre'); card.append(details); button.disabled = true; }
        catch(e) { notice(e.message); }
      };
      card.append(button);
    }
    const tool = toolCard('Media preparation', mediaActive.some(j => j.id === row.id));
    if (['QUEUED','RUNNING','CANCELLING','FAILED'].includes(row.status)) tool.append(card); else history.append(card);
  }
  if (!holder.children.length) holder.append(item('No local jobs yet.', 'p'));
  if (history.children.length > 1) holder.append(history);
  const inbox = el('completion-inbox'); inbox.replaceChildren();
  const groupedEvents = new Map();
  for (const event of relevantEvents) {
    const key = (event.recipient || 'Director') + ' · ' + event.status;
    if (!groupedEvents.has(key)) groupedEvents.set(key, []);
    groupedEvents.get(key).push(event);
  }
  for (const [key, events] of groupedEvents) {
    const group = document.createElement('details');
    group.open = events.some(e => ['FAILED','INTERRUPTED'].includes(String(e.status).toUpperCase()));
    group.append(item(key + ' · ' + events.length + ' saved result' + (events.length === 1 ? '' : 's'), 'summary'));
    for (const event of events) {
    const card = document.createElement('article');
    card.append(item(event.recipient + ' · ' + event.status, 'strong'), item(event.title, 'p'));
    const ack = item('Acknowledge result', 'button');
    ack.onclick = async () => { try { await service('acknowledge', {eventId:event.eventId}); await refreshServices(); } catch(e) { notice(e.message); } };
    card.append(ack); group.append(card);
    }
    inbox.append(group);
  }
  if (!inbox.children.length) inbox.append(item('No unread completion events.', 'p'));
  if (!el('dictation-engine').options.length) {
    for (const engine of state.speech.engines) {
      const option = new Option(engine.label + (engine.available ? '' : ' · unavailable'), engine.id);
      option.disabled = !engine.available; el('dictation-engine').add(option);
    }
    el('dictation-engine').value = state.speech.selected;
  }
  return state;
}
const pendingReplies = new Set();
toolsButton.onclick = () => { toolsPanel.showModal(); refreshServices().catch(e => notice(e.message)); };
el('tools-close').onclick = () => toolsPanel.close();
el('probe-form').onsubmit = async event => {
  event.preventDefault();
  try { await service('probe', {path:el('probe-path').value}); await refreshServices(); }
  catch(e) { notice(e.message); }
};
const controls = document.createElement('div');
controls.className = 'relay-suggestions';
controls.innerHTML = '<select id="dictation-engine" aria-label="Offline dictation engine"></select><button id="dictate-start" type="button">Dictate</button><button id="dictate-stop" type="button" disabled>Stop mic</button><button id="relay-speak" type="button">Speak reply</button><p id="voice-state" aria-live="polite">Offline voice · microphone starts only when you press Dictate</p>';
el('relay-form').before(controls);
document.querySelector('.relay-connection').textContent = 'Local commands · Qwen CPU assistant · Kokoro speech · offline dictation';
const previousRelayCommand = relayCommand;
relayCommand = async text => {
  if (/\b(happening|status|working|progress|tasks|director|plan|edit|review|deliver|screen|cut|video|knowledge|workflow|curve|graph|method|new project)\b/i.test(text)) return previousRelayCommand(text);
  relaySay(text, true);
  const facts = JSON.stringify({name:project()?.name, revision:project()?.revision, tasks:active().map(r => ({station:r.station, model:r.model, task:r.task, status:r.status}))});
  try {
    const row = await service('relay', {project:projectId, recipient:'Relay', text:'Workspace facts: ' + facts + '\nHuman request: ' + text});
    pendingReplies.add(row.id); relaySay('Qwen is answering locally on the CPU. It can advise; workspace actions use the explicit commands above.'); await refreshServices();
  } catch(e) { relaySay(e.message); }
};
el('relay-speak').onclick = async () => {
  try { if (!lastReply) throw Error('Ask Relay a question first to generate a reply.'); const row = await service('speech', {text:lastReply}); pendingReplies.add(row.id); await refreshServices(); }
  catch(e) { relaySay(e.message); }
};
async function pollDictation(generation) {
  if (generation !== dictationGeneration) return;
  try {
    const state = await service('dictate-poll', {session:dictationSession, since:dictationSeq});
    if (generation !== dictationGeneration) return;
    dictationSeq = state.seq;
    el('voice-state').textContent = state.error?.message || state.error || state.status;
    for (const event of state.events || []) if (event.type === 'final' && event.text) el('relay-input').value += (el('relay-input').value ? ' ' : '') + event.text;
    if (['starting','listening','stopping'].includes(state.status)) dictationTimer = setTimeout(() => pollDictation(generation), 750);
    else { el('dictate-start').disabled = false; el('dictate-stop').disabled = true; }
  } catch(e) { el('voice-state').textContent = e.message; el('dictate-start').disabled = false; el('dictate-stop').disabled = false; }
}
el('dictate-start').onclick = async () => {
  if (dictationStarting || el('dictate-start').disabled) return;
  dictationStarting = true; el('dictate-start').disabled = true;
  const generation = ++dictationGeneration;
  try { await refreshServices(); const state = await service('dictate-start', {engine:el('dictation-engine').value}); dictationSession = state.session; dictationSeq = 0; el('dictate-stop').disabled = false; pollDictation(generation); }
  catch(e) { el('voice-state').textContent = e.message; el('dictate-start').disabled = false; }
  finally { dictationStarting = false; }
};
el('dictate-stop').onclick = async () => { clearTimeout(dictationTimer); const generation = ++dictationGeneration; try { await service('dictate-stop', {session:dictationSession}); await pollDictation(generation); } catch(e) { el('voice-state').textContent = e.message; } };
const inboxHeading = item('Completion inbox', 'h3');
const completionInbox = document.createElement('div'); completionInbox.id = 'completion-inbox';
toolsPanel.append(inboxHeading, completionInbox);
const eventStream = new EventSource('/api/events');
window.addEventListener('neural-ready', () => refreshServices().catch(e => notice(e.message)));
eventStream.onmessage = () => { if (token) refreshServices().catch(e => notice(e.message)); };
eventStream.onerror = () => { el('voice-state').textContent = 'Live job notifications disconnected. The app will reconnect; saved jobs are retained.'; };
