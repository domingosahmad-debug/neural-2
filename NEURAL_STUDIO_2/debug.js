// Isolated Debug workspace UI. Text is always rendered with textContent; nothing a model writes is executed.
(() => {
  const root = el('debug-root');
  let state = null, pending = null, shownDiff = null, shot = null, message = '';
  const call = async body => {
    const r = await fetch('/api/debug', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Neural-Token': token}, body: JSON.stringify(body)});
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    return data.result;
  };
  const node = (tag, text, attrs = {}) => { const n = document.createElement(tag); if (text != null) n.textContent = text; Object.assign(n, attrs); return n; };
  const visible = () => !el('debug-view').hidden;
  const run = async (body, keep) => {
    try { const r = await call(body); if (!keep) state = r; message = ''; return r; }
    catch (e) { message = e.message; }
    finally { draw(); }
  };
  const refresh = () => visible() && run({action: 'state'});

  function draw() {
    if (!state) { root.replaceChildren(node('p', message || 'Loading…')); return; }
    const saved = {q: el('debug-question')?.value, model: el('debug-model')?.value, effort: el('debug-effort')?.value,
      files: [...root.querySelectorAll('input[data-file]:checked')].map(i => i.dataset.file)};
    const box = node('div');
    if (!state.maintenance.clean) box.append(node('p', state.maintenance.reservation?.state === 'RESTART_REQUIRED'
      ? 'A source repair was applied. Close and reopen Neural Studio 2 to load it. New work is not admitted until then.'
      : 'Source maintenance is in progress or needs reconciliation. New work is not admitted.', {className: 'page-description'}));
    if (message) box.append(node('p', message, {style: 'color:#8a2d2d'}));

    const form = node('div');
    const model = node('select', null, {id: 'debug-model'});
    for (const c of state.capabilities) model.append(new Option(c.label + ' · ' + c.route, c.route + '|' + c.model));
    if (saved.model) model.value = saved.model;
    const effort = node('select', null, {id: 'debug-effort'});
    const efforts = () => { const c = state.capabilities.find(c => c.route + '|' + c.model === model.value); effort.replaceChildren(...(c ? c.efforts : []).map(e => new Option(e, e))); };
    efforts(); if (saved.effort && [...effort.options].some(o => o.value === saved.effort)) effort.value = saved.effort;
    model.onchange = efforts;
    const question = node('textarea', null, {id: 'debug-question', rows: 4, maxLength: state.limits.question, placeholder: 'Describe the software problem…', style: 'width:100%;box-sizing:border-box'});
    question.value = saved.q || '';
    const files = node('details'); files.append(node('summary', `Source files to supply (up to ${state.limits.files}, ${state.limits.sourceBytes} bytes total)`));
    for (const s of state.sources) {
      const label = node('label', null, {style: 'display:block'}); const input = node('input', null, {type: 'checkbox'});
      input.dataset.file = s.path; input.checked = saved.files.includes(s.path);
      label.append(input, ' ' + s.path + ' (' + s.bytes + ' bytes)'); files.append(label);
    }
    const send = node('button', state.busy ? 'Debug model working…' : 'Ask', {disabled: state.busy || !state.capabilities.length});
    send.onclick = async () => {
      const [route, m] = model.value.split('|');
      pending = pending || {requestId: 'ui-' + crypto.randomUUID()};   // same ID on retry: never a second invocation for one question
      const r = await run({action: 'ask', requestId: pending.requestId, question: question.value, route, model: m, effort: effort.value,
        project: projectId || null, files: [...root.querySelectorAll('input[data-file]:checked')].map(i => i.dataset.file)});
      if (r) { pending = null; el('debug-question').value = ''; }
    };
    form.append(node('label', 'Model '), model, node('label', ' Effort '), effort, question, files, send);
    box.append(form, node('p', 'Diagnostics supplied with each question: paused/production state of the selected project, station states, recent failed job errors, native-bridge settled flag, maintenance state and the tail of the service log.', {className: 'page-description'}));

    for (const t of [...state.turns].reverse()) {
      const card = node('section', null, {style: 'border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0;background:var(--panel)'});
      card.append(node('p', `${new Date(t.created * 1000).toLocaleString()} · ${t.model} · ${t.effort} · ${t.status}`, {className: 'eyebrow'}), node('p', t.question, {style: 'white-space:pre-wrap;font-weight:600'}));
      if (t.files?.length) card.append(node('p', 'Supplied: ' + t.files.map(f => f.path).join(', '), {className: 'page-description'}));
      if (t.error) card.append(node('p', String(t.error), {style: 'color:#8a2d2d;white-space:pre-wrap'}));
      if (t.reply != null) {
        card.append(node('pre', t.reply, {style: 'white-space:pre-wrap;max-height:420px;overflow:auto'}));
        const stage = node('button', 'Stage proposed repair'); stage.onclick = () => run({action: 'stage', turn: t.id}); card.append(stage);
      }
      if (['QUEUED', 'RUNNING'].includes(t.status)) { const c = node('button', 'Cancel'); c.onclick = () => run({action: 'cancel', turn: t.id}); card.append(c); }
      box.append(card);
    }

    // Fresh window observation. Capture only: this panel never clicks or types.
    const shots = node('section', null, {style: 'border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0;background:var(--panel)'});
    shots.append(node('p', 'Fresh screenshot', {className: 'eyebrow'}));
    for (const [target, label] of [['neural-studio-2', 'Capture Neural Studio 2'], ['after-effects', 'Capture After Effects (view only)']]) {
      const b = node('button', label, {id: 'debug-observe-' + target});
      b.onclick = async () => { shot = await run({action: 'desktop-observe', target, image: true}, true) || shot; draw(); };
      shots.append(b);
    }
    if (shot) shots.append(node('p', `${shot.observation.title} · ${shot.observation.time} · ${shot.observation.size.join('×')} · sha256 ${shot.observation.sha256.slice(0, 12)}`, {className: 'page-description'}),
      node('img', null, {id: 'debug-shot', src: 'data:image/png;base64,' + shot.image, alt: 'Fresh capture of ' + shot.observation.target, style: 'max-width:100%;border:1px solid var(--line)'}));
    box.append(shots);

    if (state.repairs.length) box.append(node('h2', 'Staged repairs'));
    for (const r of [...state.repairs].reverse()) {
      const card = node('section', null, {style: 'border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0;background:var(--panel)'});
      card.append(node('p', `${r.id} · ${r.state}`, {className: 'eyebrow'}), node('p', r.origin?.summary || ''));
      for (const f of r.files || []) card.append(node('div', `${f.path} · ${(r.checks || {})[f.path] || ''}`));
      if (r.error) card.append(node('p', String(r.error), {style: 'color:#8a2d2d'}));
      const view = node('button', 'Show changes'); view.onclick = async () => { shownDiff = await run({action: 'diff', repair: r.id}, true) || null; draw(); }; card.append(view);
      if (r.state === 'STAGED') {
        const apply = node('button', 'Apply to source');
        apply.onclick = () => { if (confirm('Replace the listed source files? Backups are kept. Nothing restarts automatically; you must reopen Neural Studio 2 afterwards.')) run({action: 'apply', repair: r.id}); };
        const drop = node('button', 'Discard'); drop.onclick = () => run({action: 'discard', repair: r.id});
        card.append(apply, drop);
      }
      if (shownDiff?.repair === r.id) card.append(node('pre', shownDiff.diff || '(no textual difference)', {style: 'white-space:pre;max-height:480px;overflow:auto;background:var(--soft);padding:8px'}));
      box.append(card);
    }
    root.replaceChildren(box);
  }

  window.addEventListener('neural-debug-view', refresh);
  new EventSource('/api/events').onmessage = refresh;   // completion events only; no timer
})();
