#target aftereffects
/* DIAG_DEPTH_FRAMES (Claude): save PNG frames at 84.7 s of WOG_MAIN in 4 states (current / FG glow off / FG off / all DEPTH off), restore state, no save. */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), r = { ok: false, files: [], st: {} }, c = null;
 function L(pre) { for (var i = 1; i <= c.numLayers; i++) if (c.layer(i).name.indexOf(pre) === 0) return c.layer(i); return null; }
 try { var pr = app.project; for (var i = 1; i <= pr.numItems; i++) if (pr.item(i) instanceof CompItem && pr.item(i).name === 'WOG_MAIN') c = pr.item(i);
  var fg = L('DEPTH | h1 Aizen cutout'), dk = L('DEPTH | h1 bg darken'), sm = L('DEPTH | h1 smoke'), gl = fg.property('ADBE Effect Parade').property('EDGE GLOW');
  r.st.fgTrackMatte = fg.trackMatteType; r.st.fgEffects = []; for (i = 1; i <= fg.property('ADBE Effect Parade').numProperties; i++) r.st.fgEffects.push(fg.property('ADBE Effect Parade').property(i).name);
  var F = L('h1 |'); r.st.fEffects = []; for (i = 1; i <= F.property('ADBE Effect Parade').numProperties; i++) r.st.fEffects.push(F.property('ADBE Effect Parade').property(i).name);
  r.st.order = [fg.index, sm ? sm.index : -1, dk.index, F.index];
  function shot(nm) { var f = new File(ROOT + '/analysis/m4/diag_' + nm + '.png'); c.saveFrameToPng(84.7, f); r.files.push(f.fsName); }
  shot('a_current'); gl.enabled = false; shot('b_glowoff'); gl.enabled = true; fg.enabled = false; shot('c_fgoff'); dk.enabled = false; if (sm) sm.enabled = false; shot('d_alloff');
  fg.enabled = true; dk.enabled = true; if (sm) sm.enabled = true; r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; }
 var f2 = new File(ROOT + '/DIAG_DEPTH_RESULT.json'); f2.encoding = 'UTF-8'; f2.open('w'); f2.write(r.toSource()); f2.close();
})();
