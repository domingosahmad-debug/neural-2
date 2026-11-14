#target aftereffects
/* FIX_W8B_IRIS (Claude) — on open EDIT_WOG_W8_AE24.aep. Tony N4/N5: iris-only glows. p1 whole-eye matte -> p1_iris mask (tighter halo);
   new amber iris glows on d3 (Aizen eye close-up, comp 69.48-70.882 = src 996.36-997.76) and h2 (hand close-up, 85.413-87.415). g1 glow UNTOUCHED (Tony exception).
   Report FIX_W8B_RESULT.json. */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), FPS = 24000 / 1001, r = { ok: false, did: [], warn: [] }, c = null;
 function Lp(pre) { for (var i = 1; i <= c.numLayers; i++) if (c.layer(i).name.indexOf(pre) === 0) return c.layer(i); r.warn.push('no ' + pre); return null; }
 function setIO(l, a, b) { l.outPoint = b; l.inPoint = a; if (Math.abs(l.outPoint - b) > 0.002) l.outPoint = b; }
 function seq(tag, f0) { var io = new ImportOptions(new File(ROOT + '/matte_seq/' + tag + '/mask/' + f0 + '.png')); io.sequence = true; var it = app.project.importFile(io); it.mainSource.conformFrameRate = FPS; it.name = 'MATTE ' + tag; return it; }
 function copyScale(F, M) { var fs = F.property('ADBE Transform Group').property('ADBE Scale'), ms = M.property('ADBE Transform Group').property('ADBE Scale'); while (ms.numKeys) ms.removeKey(ms.numKeys);
  if (fs.numKeys) for (var k = 1; k <= fs.numKeys; k++) ms.setValueAtTime(fs.keyTime(k), fs.keyValue(k)); else ms.setValue(fs.value); M.property('ADBE Transform Group').property('ADBE Position').setValue(F.property('ADBE Transform Group').property('ADBE Position').value); }
 function glowSet(G, rad, inten) { var gl = G.property('ADBE Effect Parade').property('EYE GLOW'); if (!gl) { gl = G.property('ADBE Effect Parade').addProperty('ADBE Glo2'); gl.name = 'EYE GLOW'; }
  try { gl.property('Glow Threshold').setValue(20); gl.property('Glow Radius').setValue(rad); gl.property('Glow Intensity').setValue(inten); } catch (x) { r.warn.push('glow ' + x); } }
 function addIris(tag, f0, shotPre, a, b, col, op) { var F = Lp(shotPre); if (!F) return;
  var G = c.layers.addSolid(col, 'IRIS GLOW | ' + tag, 1920, 1080, 1, c.duration); setIO(G, a, b); G.blendingMode = BlendingMode.ADD; G.property('ADBE Transform Group').property('ADBE Opacity').setValue(op); glowSet(G, 16, 1.6);
  var M = c.layers.add(seq(tag, f0)); M.name = 'IRIS MATTE | ' + tag; M.startTime = F.startTime + f0 / FPS; setIO(M, a, b); copyScale(F, M);
  G.moveBefore(F); M.moveBefore(G); try { G.setTrackMatte(M, TrackMatteType.LUMA); } catch (x) { r.warn.push('matte ' + x); }
  r.did.push(tag + ' ' + a.toFixed(3) + '-' + b.toFixed(3) + ' matte st ' + M.startTime.toFixed(3)); }
 try { var pr = app.project; if (!pr.file || pr.file.fsName.indexOf('EDIT_WOG_W8_AE24.aep') < 0) throw Error('open project is not W8');
  for (var i = 1; i <= pr.numItems; i++) if (pr.item(i) instanceof CompItem && pr.item(i).name === 'WOG_MAIN') c = pr.item(i);
  app.beginUndoGroup('FIX_W8B_IRIS');
  var pm = Lp('EYE MATTE | p1_eyes'), pg = Lp('EYE GLOW | p1_eyes');
  if (pm && pg) { pm.replaceSource(seq('p1_iris', 25024), false); pm.name = 'EYE MATTE | p1_iris'; pg.name = 'EYE GLOW | p1_iris'; glowSet(pg, 16, 1.6); r.did.push('p1 -> iris-only matte'); }
  addIris('d3_iris2', 23889, 'd3 |', 69.48, 70.882, [1, 0.7, 0.2], 85);
  addIris('h2_iris', 20606, 'h2 |', 85.413, 87.415, [1, 0.7, 0.2], 85);
  var g1 = Lp('EYE GLOW | g1_eyes'); r.g1_untouched = g1 ? (g1.enabled + ' ' + g1.inPoint.toFixed(3)) : 'missing';
  app.endUndoGroup(); pr.save(); r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; }
 var f = new File(ROOT + '/FIX_W8B_RESULT.json'); f.encoding = 'UTF-8'; f.open('w'); f.write(r.toSource()); f.close();
})();
