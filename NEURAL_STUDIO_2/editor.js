/* Manual cut editor. Persisted neural.edit.v1 timeline; no AE bridge access. */
(() => {
  const root = document.getElementById('edit-view');
  root.innerHTML = `
  <div class="edit-top"><div><p class="eyebrow">Production / Edit</p><h1>Your cutting room.</h1><p>Build a cut. Shape the dialogue. Keep every decision editable.</p></div><div class="edit-actions"><span id="ed-saved" class="edit-muted">No edit loaded</span><button id="ed-save">Save edit</button><button id="ed-export" class="edit-primary">Export MP4 ↗</button></div></div>
  <div class="edit-layout"><section class="edit-bin"><h2>Project media</h2><button id="ed-import">＋ Import media</button><div id="ed-media" class="edit-media-list"></div><p class="edit-project-note">Files stay on your PC. Imports record source fingerprints; changed sources stop export.</p></section>
  <section class="edit-monitor"><div class="edit-screen" id="ed-screen"><div id="ed-stage" style="position:relative;background:#000"><video id="ed-video" playsinline preload="metadata"></video><div id="ed-caption" class="edit-caption" hidden></div></div><span id="ed-empty" class="edit-empty">Import footage, then add it to the timeline.</span></div><div class="edit-controls"><button id="ed-prev" title="Previous frame">‹</button><button id="ed-play">▶ Play</button><button id="ed-next" title="Next frame">›</button><output id="ed-time" class="edit-time">00:00.00 / 00:00.00</output></div><audio id="ed-audio" preload="metadata"></audio><p id="ed-preview-note" class="edit-muted" style="text-align:center;margin:9px 0 0">Source preview · rendered export provides continuous playback.</p></section>
  <section class="edit-properties"><h2>Inspector</h2><div id="ed-inspector-empty" class="edit-muted">Select a clip to trim it or adjust its source audio.</div><div id="ed-inspector" hidden><strong id="ed-clip-name"></strong><div class="edit-pair"><label>Source in · seconds<input id="ed-in" type="number" min="0" step="0.001"></label><label>Source out · seconds<input id="ed-out" type="number" min="0" step="0.001"></label></div><label>Source audio<input id="ed-gain" type="range" min="0" max="1" step="0.01"></label><button id="ed-trim">Apply trim / audio</button></div>
  <h3>Music</h3><div id="ed-music-empty" class="edit-muted">Add audio from Project media.</div><div id="ed-music-form" hidden><span id="ed-music-name"></span><div class="edit-pair"><label>Source in<input id="ed-music-in" type="number" min="0" step="0.001"></label><label>Start in edit<input id="ed-music-start" type="number" min="0" step="0.001"></label></div><label>Music volume<input id="ed-music-gain" type="range" min="0" max="1" step="0.01"></label><button id="ed-music-apply">Apply</button> <button id="ed-music-remove">Remove</button></div>
  <h3>Caption</h3><input id="ed-cap-id" type="hidden"><label>Text<textarea id="ed-cap-text" rows="2" maxlength="300" placeholder="Write a caption…"></textarea></label><div class="edit-pair"><label>Start · seconds<input id="ed-cap-start" type="number" min="0" step="0.001" value="0"></label><label>End · seconds<input id="ed-cap-end" type="number" min="0" step="0.001" value="1"></label></div><button id="ed-cap-save">Add caption</button> <button id="ed-cap-new">New</button><button id="ed-cap-remove" hidden>Delete</button></section></div>
  <div class="edit-timeline"><div class="edit-toolbar"><strong>Timeline</strong><button id="ed-undo">↶ Undo</button><button id="ed-redo">↷ Redo</button><button id="ed-split">Split at playhead</button><button id="ed-left">← Move clip</button><button id="ed-right">Move clip →</button><button id="ed-remove">Remove clip</button><select id="ed-format" class="edit-format" aria-label="Canvas format"><option value="1080x1080">Square · 1080</option><option value="1920x1080">Landscape · 1080p</option><option value="1080x1920">Portrait · 1080p</option></select><select id="ed-fps" aria-label="Frames per second"><option>24</option><option>25</option><option selected>30</option><option>60</option></select></div><div class="edit-ruler"><span id="ed-duration">00:00.00</span><input id="ed-seek" type="range" min="0" max="0" step="0.0333333" value="0" aria-label="Edit playhead"></div><div class="edit-track"><span class="edit-track-label">V1 · Video</span><div id="ed-clips" class="edit-track-body"></div></div><div class="edit-track"><span class="edit-track-label">A1 · Music</span><div id="ed-music-track" class="edit-track-body"></div></div><div class="edit-track"><span class="edit-track-label">C1 · Captions</span><div id="ed-caps" class="edit-track-body"></div></div></div>
  <p id="ed-status" class="edit-status" role="status"></p><div class="edit-exports"><h2>Rendered exports</h2><div id="ed-exports"></div><video id="ed-output" class="edit-render-preview" controls hidden></video></div>`;
  const $ = id => document.getElementById('ed-'+id);
  let doc, pid, selected, position=0, playing=false, activeIndex=-1, loading=false, dirty=false, active=false, generation=0;
  let undo=[],redo=[], busy=false, eventVersion=0;
  const drafts=new Map();
  const video=$('video'), music=$('audio');
  const clone = v => structuredClone(v);
  const uid = () => crypto.randomUUID();
  const total = () => doc?.clips.reduce((sum,c)=>sum+c.out-c.in,0) || 0;
  const media = id => doc.media.find(m=>m.id===id);
  const time = n => `${String(Math.floor(n/60)).padStart(2,'0')}:${(n%60).toFixed(2).padStart(5,'0')}`;
  const url = id => `/api/editor-media?project=${encodeURIComponent(pid)}&id=${id}`;
  const status = (text,error=false) => { $('status').textContent=text; $('status').dataset.error=String(error); };
  async function api(action, data={}) {
    const response=await fetch('/api/editor',{method:'POST',headers:{'Content-Type':'application/json','X-Neural-Token':token},body:JSON.stringify({action,project:pid,...data})});
    const reply=await response.json(); if(!response.ok) throw new Error(reply.error || 'Editor request failed'); return reply.result;
  }
  async function guarded(fn) {
    if(busy || !doc) return;
    busy=true; root.setAttribute('aria-busy','true');document.getElementById('projects').disabled=true;document.getElementById('new-project').disabled=true;
    try { await fn(); } catch(e) {status(e.message,true);}
    finally {busy=false;root.removeAttribute('aria-busy');document.getElementById('projects').disabled=false;document.getElementById('new-project').disabled=false;}
  }
  function pause(){playing=false;video.pause();music.pause();$('play').textContent='▶ Play';}
  function changed(fn){
    if(busy || !doc) return;
    pause();undo.push(clone(doc));if(undo.length>60)undo.shift();redo=[];
    fn();dirty=true;activeIndex=-1;render();seek(Math.min(position,total()),false);
  }
  function button(text,fn,cls='') {const b=document.createElement('button');b.textContent=text;b.className=cls;b.onclick=fn;return b;}
  function locate(t){let start=0;for(let i=0;i<doc.clips.length;i++){const c=doc.clips[i],end=start+c.out-c.in;if(t<end-.00001 || i===doc.clips.length-1)return {i,c,start};start=end;}return null;}
  function musicSync(force=false){
    const m=doc.music;if(!m){music.pause();music.removeAttribute('src');return;}
    const path=url(m.mediaId);if(music.getAttribute('src')!==path){music.src=path;force=true;}
    music.volume=m.gain;const target=position-m.start+m.in;
    if(position<m.start || target>=media(m.mediaId).duration || !playing){music.pause();if(target>=0&&Number.isFinite(music.duration)&&target<music.duration)music.currentTime=target;return;}
    if(force || Math.abs(music.currentTime-target)>.18)music.currentTime=target;
    music.play().catch(e=>status('Music preview unavailable: '+e.message,true));
  }
  function overlay(){
    const caps=doc.captions.filter(c=>position>=c.start&&position<c.end);$('caption').textContent=caps.map(c=>c.text).join('\n');$('caption').hidden=!caps.length;
    $('time').textContent=time(position)+' / '+time(total());$('seek').value=position;
  }
  function sizeStage(){if(!doc)return;const box=$('screen'),ratio=doc.width/doc.height,w=Math.min(box.clientWidth,box.clientHeight*ratio);$('stage').style.width=w+'px';$('stage').style.height=w/ratio+'px';$('caption').style.fontSize=Math.round(doc.width*.045)*w/doc.width+'px';}
  new ResizeObserver(sizeStage).observe($('screen'));
  function seek(t, resume=playing){
    if(!doc)return;position=Math.max(0,Math.min(total(),Math.round(t*doc.fps)/doc.fps));
    const found=locate(position);if(!found){pause();video.removeAttribute('src');$('empty').hidden=false;overlay();return;}
    const {i,c,start}=found;const src=url(c.mediaId), target=Math.min(c.out-.001,c.in+position-start);
    activeIndex=i;video.volume=c.gain;$('empty').hidden=true;
    const set=()=>{video.currentTime=target;if(resume){playing=true;video.play().catch(e=>{pause();status('Source preview failed: '+e.message+'. Export still supports FFmpeg-readable media.',true);});}musicSync(true);};
    if(video.getAttribute('src')!==src){video.pause();video.src=src;video.onloadedmetadata=set;}else set();
    overlay();sizeStage();
  }
  function tick(){
    if(playing&&doc&&activeIndex>=0){let start=0;for(let i=0;i<activeIndex;i++)start+=doc.clips[i].out-doc.clips[i].in;const c=doc.clips[activeIndex];
      position=Math.min(total(),start+Math.max(0,video.currentTime-c.in));
      if(video.currentTime>=c.out-.012 || video.ended){const end=start+c.out-c.in;if(end>=total()-.001){position=total();pause();}else seek(end,true);}
      overlay();musicSync();
    }
    if(playing)requestAnimationFrame(tick);
  }
  video.onerror=()=>{pause();status('This source cannot be previewed in this desktop runtime. Use H.264 MP4 / AAC for source preview; FFmpeg export supports more codecs.',true);};
  function selectClip(id){pause();selected=id;let t=0;for(const c of doc.clips){if(c.id===id)break;t+=c.out-c.in;}renderInspector();renderTracks();seek(t,false);}
  function renderInspector(){
    const c=doc.clips.find(c=>c.id===selected);$('inspector').hidden=!c;$('inspector-empty').hidden=!!c;
    if(c){$('clip-name').textContent=media(c.mediaId).name;$('in').value=c.in.toFixed(3);$('out').value=c.out.toFixed(3);$('gain').value=c.gain;}
    const m=doc.music;$('music-form').hidden=!m;$('music-empty').hidden=!!m;
    if(m){$('music-name').textContent=media(m.mediaId).name;$('music-in').value=m.in;$('music-start').value=m.start;$('music-gain').value=m.gain;}
  }
  function renderTracks(){
    $('clips').replaceChildren();let start=0;
    for(const c of doc.clips){const b=button('',()=>selectClip(c.id),'edit-clip');b.textContent=media(c.mediaId).name;b.title=`${time(start)} — ${time(start+c.out-c.in)} · source ${c.in.toFixed(3)}–${c.out.toFixed(3)}s`;b.setAttribute('aria-pressed',String(selected===c.id));b.style.width=Math.max(90,(c.out-c.in)*36)+'px';const sm=document.createElement('small');sm.textContent=(c.out-c.in).toFixed(2)+'s';b.append(sm);$('clips').append(b);start+=c.out-c.in;}
    if(!doc.clips.length)$('clips').textContent='Add video from Project media to start your cut.';
    $('music-track').replaceChildren();if(doc.music){const b=button(media(doc.music.mediaId).name,()=>{$('music-in').focus();},'edit-clip edit-audio');b.title='Music at '+doc.music.start+'s';$('music-track').append(b);}
    $('caps').replaceChildren();for(const c of doc.captions){const b=button(`${time(c.start)} · ${c.text}`,()=>{ $('cap-id').value=c.id;$('cap-text').value=c.text;$('cap-start').value=c.start;$('cap-end').value=c.end;$('cap-save').textContent='Update caption';$('cap-remove').hidden=false;seek(c.start,false);},'edit-clip edit-subtitle');$('caps').append(b);}
    $('duration').textContent=time(total());$('seek').max=total();$('seek').step=1/doc.fps;
  }
  function render(){
    if(!doc)return;$('saved').textContent=dirty?'Unsaved changes':`Saved · revision ${doc.revision}`;
    $('undo').disabled=!undo.length;$('redo').disabled=!redo.length;
    const format=`${doc.width}x${doc.height}`;if(![...$('format').options].some(o=>o.value===format))$('format').append(new Option(`${doc.width} x ${doc.height}`,format));$('format').value=format;$('fps').value=doc.fps;
    $('media').replaceChildren();for(const m of doc.media){const box=document.createElement('div');box.className='edit-media';const name=document.createElement('strong');name.textContent=m.name;name.title=m.path;const meta=document.createElement('small');meta.textContent=`${m.video?`${m.width}×${m.height}`:'Audio'} · ${time(m.duration)}`;box.append(name,meta);
      if(m.video)box.append(button('＋ Video',()=>changed(()=>{const out=Math.floor(m.duration*doc.fps)/doc.fps;const c={id:uid(),mediaId:m.id,in:0,out,gain:1};doc.clips.push(c);selected=c.id;})));
      if(m.audio)box.append(button('＋ Music',()=>changed(()=>{doc.music={mediaId:m.id,in:0,start:0,gain:.35};})));
      $('media').append(box);
    }
    renderInspector();renderTracks();sizeStage();
  }
  async function save(){pause();const r=await api('save',{revision:doc.revision,document:doc});doc=r.document;dirty=false;drafts.delete(pid);render();status('Edit saved.');}
  async function exportsRefresh(){
    if(!pid||!active)return;const expected=pid;const {exports:jobs}=await api('load');if(pid!==expected)return;
    $('exports').replaceChildren();if(!jobs.length){$('exports').textContent='Exports appear here with progress and saved completion notices.';return;}
    for(const j of jobs.slice(0,12)){const row=document.createElement('div');row.className='edit-export-row';const label=document.createElement('span');label.textContent=`Revision ${j.revision} · ${j.status} · ${j.error||j.progress}`;row.append(label);if(j.status==='completed'){
      row.append(button('Play render',()=>{pause();$('output').src=`/api/editor-output?id=${j.id}`;$('output').hidden=false;$('output').play().catch(()=>{});}));
      row.append(button('Save video…',()=>guarded(async()=>{const dest=await window.neuralDesktop.saveExport(j.id);if(dest)status('Video saved to '+dest);})));}
      $('exports').append(row);
    }
  }
  $('import').onclick=()=>guarded(async()=>{if(!window.neuralDesktop)throw new Error('Open the Neural Studio 2 desktop app to use native media import.');if(dirty)await save();const paths=await window.neuralDesktop.selectMedia();if(!paths.length)return;status('Registering media and checking source fingerprints…');doc=(await api('import',{paths,revision:doc.revision})).document;undo=[];redo=[];render();status('Media imported. Add video or music from Project media.');});
  $('save').onclick=()=>guarded(save);
  $('export').onclick=()=>guarded(async()=>{await save();await api('export',{revision:doc.revision});await exportsRefresh();status('Export queued. You can leave this workspace; completion is saved in the inbox.');});
  $('play').onclick=()=>{if(!doc?.clips.length)return;if(playing){pause();return;}if(position>=total()-.001)position=0;playing=true;$('play').textContent='Ⅱ Pause';seek(position,true);requestAnimationFrame(tick);};
  $('prev').onclick=()=>{pause();seek(position-1/doc.fps,false);};$('next').onclick=()=>{pause();seek(position+1/doc.fps,false);};$('seek').oninput=()=>{pause();seek(Number($('seek').value),false);};
  $('trim').onclick=()=>{const c=doc.clips.find(c=>c.id===selected);if(!c)return;const a=Number($('in').value),b=Number($('out').value),gain=Number($('gain').value);if(!Number.isFinite(a)||!Number.isFinite(b)||a<0||b>media(c.mediaId).duration||b-a<1/doc.fps){status('Trim needs at least one frame within the source duration.',true);return;}changed(()=>{c.in=a;c.out=a+Math.floor((b-a)*doc.fps+.00001)/doc.fps;c.gain=gain;});};
  $('split').onclick=()=>{const loc=locate(position);if(!loc)return;const {c,start}=loc,offset=Math.round((position-start)*doc.fps)/doc.fps;if(offset<1/doc.fps-.00001||c.out-c.in-offset<1/doc.fps-.00001){status('Place the playhead inside a clip, at least one frame from each end.',true);return;}changed(()=>{const next={...c,id:uid(),in:c.in+offset};c.out=next.in;doc.clips.splice(loc.i+1,0,next);selected=next.id;});};
  for(const [name,delta] of [['left',-1],['right',1]])$(name).onclick=()=>{const i=doc.clips.findIndex(c=>c.id===selected),j=i+delta;if(i<0||j<0||j>=doc.clips.length)return;changed(()=>{[doc.clips[i],doc.clips[j]]=[doc.clips[j],doc.clips[i]];});};
  $('remove').onclick=()=>{if(selected)changed(()=>{doc.clips=doc.clips.filter(c=>c.id!==selected);selected=null;});};
  for(const [name,from,to] of [['undo',()=>undo,()=>redo],['redo',()=>redo,()=>undo]])$(name).onclick=()=>{if(busy||!from().length)return;pause();to().push(clone(doc));const revision=doc.revision,catalog=doc.media;doc=from().pop();doc.revision=revision;doc.media=catalog;dirty=true;activeIndex=-1;render();seek(Math.min(position,total()),false);};
  $('music-apply').onclick=()=>{const a=Number($('music-in').value),start=Number($('music-start').value);if(a<0||a>=media(doc.music.mediaId).duration||start<0||start>total()){status('Music source in and edit start must be inside their durations.',true);return;}changed(()=>Object.assign(doc.music,{in:a,start,gain:Number($('music-gain').value)}));};
  $('music-remove').onclick=()=>changed(()=>{doc.music=null;});
  function resetCaption(){$('cap-id').value='';$('cap-text').value='';$('cap-start').value=position.toFixed(3);$('cap-end').value=Math.min(total(),position+1).toFixed(3);$('cap-save').textContent='Add caption';$('cap-remove').hidden=true;}
  $('cap-new').onclick=resetCaption;
  $('cap-save').onclick=()=>{const start=Number($('cap-start').value),end=Number($('cap-end').value),text=$('cap-text').value.trim(),id=$('cap-id').value||uid();if(!text||start<0||end<=start||end>total()){status('Give the caption text and a start/end inside the edit.',true);return;}changed(()=>{doc.captions=doc.captions.filter(c=>c.id!==id);doc.captions.push({id,start,end,text});doc.captions.sort((a,b)=>a.start-b.start);});resetCaption();};
  $('cap-remove').onclick=()=>{const id=$('cap-id').value;changed(()=>{doc.captions=doc.captions.filter(c=>c.id!==id);});resetCaption();};
  $('format').onchange=()=>changed(()=>{[doc.width,doc.height]=$('format').value.split('x').map(Number);});
  $('fps').onchange=()=>{const fps=Number($('fps').value);changed(()=>{doc.fps=fps;for(const c of doc.clips)c.out=c.in+Math.max(1,Math.floor((c.out-c.in)*fps+.00001))/fps;});};
  async function activate(detail){
    active=detail.active;
    if(pid!==detail.project){
      generation++;
      if(doc && dirty)drafts.set(pid,{doc,dirty,undo,redo,selected,position});
      pid=detail.project;doc=null;dirty=false;undo=[];redo=[];selected=null;position=0;activeIndex=-1;
    }
    if(!active){pause();$('output').pause();return;}
    if(doc){sizeStage();exportsRefresh().catch(e=>status(e.message,true));return;}
    const current=++generation,target=pid;pause();loading=true;
    try{
      const cached=drafts.get(target);
      const result=cached ? null : await api('load');
      if(current!==generation || pid!==target)return;
      if(cached){({doc,dirty,undo,redo,selected,position}=cached);}
      else{doc=result.document;selected=null;position=0;undo=[];redo=[];dirty=false;}
      activeIndex=-1;video.removeAttribute('src');music.removeAttribute('src');$('output').pause();$('output').hidden=true;$('empty').hidden=!doc.clips.length;render();seek(position,false);resetCaption();await exportsRefresh();status('Manual editor - straight cuts, source audio, one music track and timed captions. Motion curves and automatic captions are not implemented yet.');
    }catch(e){status(e.message,true);}finally{loading=false;}
  }
  window.addEventListener('neural-edit-view',e=>activate(e.detail));
  const stream=new EventSource('/api/events');stream.onmessage=()=>{const v=++eventVersion;if(active&&doc)exportsRefresh().catch(e=>{if(v===eventVersion)status(e.message,true);});};
  window.addEventListener('beforeunload',e=>{if(dirty||[...drafts.values()].some(d=>d.dirty)){e.preventDefault();e.returnValue='';}});
})();
