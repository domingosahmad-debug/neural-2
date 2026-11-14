#target aftereffects
/* PROBE_TONY_FX (Claude, READ-ONLY): all parameter values of every effect on Tony's 'Adjustment Layer 1' layers in WOG_MAIN (+ time remap of s05). */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), r = { ok: false, layers: [] };
 function ser(v) { if (v instanceof Array) { var o = []; for (var i = 0; i < v.length; i++) o.push(typeof v[i] === 'number' ? Math.round(v[i] * 1000) / 1000 : v[i]); return o; } return typeof v === 'number' ? Math.round(v * 1000) / 1000 : String(v); }
 try {
  var pr = app.project, c = null, i; r.file = pr.file ? pr.file.fsName : null;
  for (i = 1; i <= pr.numItems; i++) if (pr.item(i) instanceof CompItem && pr.item(i).name === 'WOG_MAIN') c = pr.item(i);
  for (i = 1; i <= c.numLayers; i++) { var L = c.layer(i); if (L.name.indexOf('Adjustment Layer') !== 0) continue;
   var row = { idx: i, name: L.name, inP: ser(L.inPoint), outP: ser(L.outPoint), fx: [] }, fx = L.property('ADBE Effect Parade');
   for (var e = 1; e <= fx.numProperties; e++) { var F = fx.property(e), ps = [];
    for (var k = 1; k <= F.numProperties; k++) { var p = F.property(k); if (!p || p.propertyType !== PropertyType.PROPERTY) continue; var v = null; try { v = ser(p.value); } catch (x) { v = 'n/a'; } ps.push([p.name, v, p.numKeys]); }
    row.fx.push({ name: F.name, mn: F.matchName, params: ps }); }
   r.layers.push(row); }
  r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; }
 var f = new File(ROOT + '/PROBE_TONY_FX_RESULT.json'); f.encoding = 'UTF-8'; f.open('w'); f.write(r.toSource()); f.close();
})();
