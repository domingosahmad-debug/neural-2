#target aftereffects
/* PROBE_TONY_MUSICFIX (Claude, no content mutation): record the LIVE project identity + every audio layer (source file, in/out/start/stretch,
   enabled/audioEnabled, time remap keys, audio level keys) and all layers active 70-100 s in every comp named WOG_MAIN; then save the live state
   to a NEW recovery AEP (Tony's manual Nicki->HONORABLE repair). Report TONY_MUSICFIX_PROBE.json. */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), r = { ok: false, comps: [] };
 function ser(v) { if (v instanceof Array) { var o = []; for (var i = 0; i < v.length; i++) o.push(Math.round(v[i] * 1000) / 1000); return o; } return typeof v === 'number' ? Math.round(v * 1000) / 1000 : String(v); }
 function ks(p) { var a = []; if (!p) return a; for (var k = 1; k <= p.numKeys; k++) { var row = [ser(p.keyTime(k))]; try { row.push(ser(p.keyValue(k))); } catch (x) { row.push('ERR'); } try { row.push(p.keyInInterpolationType(k), p.keyOutInterpolationType(k)); } catch (x) {} a.push(row); } return a; }
 try {
  var pr = app.project; r.file = pr.file ? pr.file.fsName : null; r.dirty = pr.dirty; r.numItems = pr.numItems;
  for (var i = 1; i <= pr.numItems; i++) { var it = pr.item(i); if (!(it instanceof CompItem)) continue;
   var cr = { id: it.id, name: it.name, dur: ser(it.duration), n: it.numLayers, audio: [], mid: [] }; r.comps.push(cr);
   if (it.name !== 'WOG_MAIN' && it.numLayers > 200) continue;
   for (var j = 1; j <= it.numLayers; j++) { var L = it.layer(j), row = { idx: j, name: L.name, inP: ser(L.inPoint), outP: ser(L.outPoint), st: ser(L.startTime), str: ser(L.stretch), en: L.enabled };
    try { row.src = L.source ? (L.source.file ? L.source.file.fsName : L.source.name) : null; } catch (x) {}
    if (L.hasAudio) { row.aud = L.audioEnabled; try { row.tr = L.timeRemapEnabled; if (L.timeRemapEnabled) row.trk = ks(L.property('ADBE Time Remapping')); } catch (x) {}
     var lv = L.property('ADBE Audio Group') ? L.property('ADBE Audio Group').property('ADBE Audio Levels') : null; row.lvl = lv ? (lv.numKeys ? ks(lv) : ser(lv.value)) : null;
     try { var fx = L.property('ADBE Effect Parade'); row.fx = []; for (var e = 1; e <= fx.numProperties; e++) row.fx.push(fx.property(e).matchName); } catch (x) {}
     if (L.audioEnabled || /MUSIC|SONG|WE ON GO|BRIDGE|NICKI|HONOR/i.test(L.name + (row.src || ''))) cr.audio.push(row); }
    if (L.outPoint > 70 && L.inPoint < 100) cr.mid.push([j, L.name, ser(L.inPoint), ser(L.outPoint), ser(L.startTime), L.enabled, L.hasAudio && L.audioEnabled]); } }
  if (pr.dirty || true) { var rec = new File(ROOT + '/LIVE_TONY_MUSICFIX_' + (new Date()).getTime() + '_AE24.aep'); pr.save(rec); r.recovery = rec.fsName; }
  r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; }
 var f = new File(ROOT + '/TONY_MUSICFIX_PROBE.json'); f.encoding = 'UTF-8'; f.open('w'); f.write(r.toSource()); f.close();
})();
