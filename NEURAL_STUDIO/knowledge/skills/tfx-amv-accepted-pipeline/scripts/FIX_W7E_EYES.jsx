#target aftereffects
/* FIX_W7E_EYES (Claude) — on open EDIT_WOG_W7_AE24.aep: sustained glowing eyes (whole clip) on g1 (EP08 Getsuga shout close) and p1 (final stare)
   from SAM2.1 masks matte_seq/<tag>/mask/<srcframe>.png. Per shot: [MATTE seq (luma, copies footage scale keys)] above [GLOW solid Add + Glow] above footage.
   Report FIX_W7E_RESULT.json. */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), FPS = 24000 / 1001, r = { ok: false, did: [], warn: [] }, c = null;
 function L(pre) { for (var i = 1; i <= c.numLayers; i++) if (c.layer(i).name.indexOf(pre) === 0) return c.layer(i); return null; }
 try { var pr = app.project; if (!pr.file || pr.file.fsName.indexOf('EDIT_WOG_W7_AE24.aep') < 0) throw Error('open project is not W7');
  for (var i = 1; i <= pr.numItems; i++) if (pr.item(i) instanceof CompItem && pr.item(i).name === 'WOG_MAIN') c = pr.item(i);
  app.beginUndoGroup('FIX_W7E_EYES');
  var JOBS = [ { tag: 'g1_eyes', shot: 'g1 |', f0: 22979, col: [1, 0.22, 0.04], op: 90 }, { tag: 'p1_eyes', shot: 'p1 |', f0: 25024, col: [1, 0.15, 0.05], op: 85 } ];
  for (var j = 0; j < JOBS.length; j++) { var J = JOBS[j], F = L(J.shot); if (!F) { r.warn.push('no ' + J.shot); continue; }
   var io = new ImportOptions(new File(ROOT + '/matte_seq/' + J.tag + '/mask/' + J.f0 + '.png')); io.sequence = true; var it = pr.importFile(io); it.mainSource.conformFrameRate = FPS; it.name = 'MATTE ' + J.tag;
   var G = c.layers.addSolid(J.col, 'EYE GLOW | ' + J.tag, 1920, 1080, 1, c.duration); G.inPoint = F.inPoint; G.outPoint = F.outPoint; G.blendingMode = BlendingMode.ADD; G.property('ADBE Transform Group').property('ADBE Opacity').setValue(J.op);
   var gl = G.property('ADBE Effect Parade').addProperty('ADBE Glo2'); gl.name = 'EYE GLOW'; try { gl.property('Glow Threshold').setValue(20); gl.property('Glow Radius').setValue(35); gl.property('Glow Intensity').setValue(2.2); } catch (x) { r.warn.push('glow ' + x); }
   var M = c.layers.add(it); M.name = 'EYE MATTE | ' + J.tag; M.startTime = F.startTime + J.f0 / FPS; M.inPoint = F.inPoint; M.outPoint = F.outPoint; if (Math.abs(M.outPoint - F.outPoint) > 0.002) M.outPoint = F.outPoint;
   var fs = F.property('ADBE Transform Group').property('ADBE Scale'), ms = M.property('ADBE Transform Group').property('ADBE Scale');
   if (fs.numKeys) for (var k = 1; k <= fs.numKeys; k++) ms.setValueAtTime(fs.keyTime(k), fs.keyValue(k)); else ms.setValue(fs.value);
   M.property('ADBE Transform Group').property('ADBE Position').setValue(F.property('ADBE Transform Group').property('ADBE Position').value);
   G.moveBefore(F); M.moveBefore(G);
   try { G.setTrackMatte(M, TrackMatteType.LUMA); } catch (x) { try { G.trackMatteType = TrackMatteType.LUMA; } catch (y) { r.warn.push('matte ' + y); } }
   r.did.push(J.tag + ' on ' + F.name + ' ' + F.inPoint.toFixed(3) + '-' + F.outPoint.toFixed(3) + ' matte st ' + M.startTime.toFixed(3)); }
  app.endUndoGroup(); pr.save(); r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; }
 var f = new File(ROOT + '/FIX_W7E_RESULT.json'); f.encoding = 'UTF-8'; f.open('w'); f.write(r.toSource()); f.close();
})();
