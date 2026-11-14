#target aftereffects
/* BUILD_TYPE_PROOF (Claude) — W7 M1: NEW TYPE_PROOF_W7_AE24.aep with comp HERO_TYPE_PROOF (10 s): BAN / KAI / GETSUGA / TENSHŌ in Brave Gates
   over real EP05 shots, "impact title" system: per-character slam-in (scale/blur/opacity stagger), layer overshoot + rotation settle,
   decaying shake expression, RGB split hit (S_DistortRGB), Sapphire S_Glow (fire), living energy edges (Turbulent Displace), light sweep, dark backing.
   Live project saved to recovery first if dirty. Dumps Sapphire property names for later builds. Report TYPE_PROOF_RESULT.json. */
(function () {
 var ROOT = File($.fileName).parent.fsName.replace(/\\/g, '/'), FPS = 24000 / 1001, FR = 1 / FPS, r = { ok: false, warn: [], props: {} }, undo = false;
 function done() { var f = new File(ROOT + '/TYPE_PROOF_RESULT.json'); f.encoding = 'UTF-8'; f.open('w'); f.write(r.toSource()); f.close(); return r.ok ? 'ok' : 'fail'; }
 function keys(p, a) { while (p.numKeys) p.removeKey(p.numKeys); for (var i = 0; i < a.length; i++) p.setValueAtTime(a[i][0], a[i][1]); }
 function easeAll(p, inf) { for (var k = 1; k <= p.numKeys; k++) { try { var v = p.keyValue(k), n = (v instanceof Array && !p.isSpatial) ? v.length : 1, e = []; for (var j = 0; j < n; j++) e.push(new KeyframeEase(0, inf)); p.setTemporalEaseAtKey(k, e, e); } catch (x) {} } }
 function T(l) { return l.property('ADBE Transform Group'); }
 function dumpProps(fx, key) { if (r.props[key]) return; var a = []; for (var i = 1; i <= fx.numProperties; i++) { var p = fx.property(i); if (p) a.push(p.name); } r.props[key] = a; }
 function setP(fx, names, v) { for (var i = 0; i < names.length; i++) { try { var p = fx.property(names[i]); if (p) { p.setValue(v); return names[i]; } } catch (x) {} } r.warn.push('no prop ' + names.join('/')); return null; }
 function keyP(fx, names, kk) { for (var i = 0; i < names.length; i++) { try { var p = fx.property(names[i]); if (p) { keys(p, kk); return p; } } catch (x) {} } r.warn.push('no keyprop ' + names.join('/')); return null; }
 try {
  if (parseInt(app.version, 10) !== 24) throw Error('AE24 required');
  var dest = new File(ROOT + '/TYPE_PROOF_W7_AE24.aep'); if (dest.exists) throw Error('Output exists');
  r.previousLive = app.project && app.project.file ? app.project.file.fsName : null; r.previousDirty = app.project ? app.project.dirty : null;
  if (app.project && app.project.dirty) { var rec = new File(ROOT + '/LIVE_DIRTY_BEFORE_TYPEPROOF_' + (new Date()).getTime() + '_AE24.aep'); app.project.save(rec); r.recovery = rec.fsName; }
  app.newProject(); var pr = app.project; pr.save(dest);
  var ep5 = pr.importFile(new ImportOptions(new File('C:/Users/TUF/Videos/Clips for edits/Bleach/Bleach TYBW - Ep 05 - DEFEND YOU (RAW No Subs).mp4')));
  var c = pr.items.addComp('HERO_TYPE_PROOF', 1920, 1080, 1, Math.round(10 * FPS) / FPS, FPS); c.bgColor = [0, 0, 0];
  app.beginUndoGroup('TYPE_PROOF'); undo = true;
  var SEG = [ { w: 'BAN', src: 836.70, col: [1, 1, 1], glow: [1, 0.25, 0.08] }, { w: 'KAI', src: 840.00, col: [1, 1, 1], glow: [1, 0.25, 0.08] },
              { w: 'GETSUGA', src: 1191.25, col: [1, 1, 1], glow: [1, 0.15, 0.1] }, { w: 'TENSHŌ', src: 1195.00, col: [0.95, 0.1, 0.12], glow: [1, 0.45, 0.1] } ];
  var D = 2.5;
  for (var i = 0; i < SEG.length; i++) { var s = SEG[i], a = i * D, b = a + D;
   var F = c.layers.add(ep5); F.startTime = a - s.src; F.inPoint = a; F.outPoint = b; F.audioEnabled = false; T(F).property('ADBE Scale').setValue([100, 100]);
   // dark radial backing for legibility
   var bk = c.layers.addSolid([0, 0, 0], 'BACKING ' + s.w, 1920, 1080, 1, c.duration); bk.inPoint = a; bk.outPoint = b;
   var m = bk.property('ADBE Mask Parade').addProperty('ADBE Mask Atom'), sh = new Shape(); sh.vertices = [[260, 340], [1660, 340], [1660, 720], [260, 720]]; sh.closed = true; m.property('ADBE Mask Shape').setValue(sh); m.property('ADBE Mask Feather').setValue([260, 200]);
   keys(T(bk).property('ADBE Opacity'), [[a, 0], [a + 3 * FR, 55], [b - 4 * FR, 55], [b, 0]]);
   // text
   var t = c.layers.addText(s.w), td = t.property('ADBE Text Properties').property('ADBE Text Document'), d = td.value;
   d.font = 'BraveGatesPersonalUseOnly-Reg'; d.fontSize = 300; d.fillColor = s.col; d.applyFill = true; d.applyStroke = false; d.tracking = 40; try { d.justification = ParagraphJustification.CENTER_JUSTIFY; } catch (x) {} td.setValue(d);
   r['font_' + i] = t.property('ADBE Text Properties').property('ADBE Text Document').value.font;
   t.name = 'HERO | ' + s.w; t.inPoint = a; t.outPoint = b;
   var bx = t.sourceRectAtTime(a + 0.5, false); T(t).property('ADBE Anchor Point').setValue([bx.left + bx.width / 2, bx.top + bx.height / 2]); T(t).property('ADBE Position').setValue([960, 540]);
   var bs = Math.min(100, 100 * 1500 / Math.max(1, bx.width));
   // per-character slam-in
   var an = t.property('ADBE Text Properties').property('ADBE Text Animators'); an.addProperty('ADBE Text Animator').name = 'SLAM';
   var ap = an.property('SLAM').property('ADBE Text Animator Properties');
   ap.addProperty('ADBE Text Scale 3D').setValue([380, 380, 100]); ap.addProperty('ADBE Text Opacity').setValue(0); ap.addProperty('ADBE Text Blur').setValue([30, 30]); ap.addProperty('ADBE Text Rotation').setValue(-18);
   an.property('SLAM').property('ADBE Text Selectors').addProperty('ADBE Text Selector');
   var sel = an.property('SLAM').property('ADBE Text Selectors').property(1); sel.property('ADBE Text Range Advanced').property('ADBE Text Range Units').setValue(2);
   var n = s.w.length; sel = an.property('SLAM').property('ADBE Text Selectors').property(1); sel.property('ADBE Text Index End').setValue(n);
   sel = an.property('SLAM').property('ADBE Text Selectors').property(1); keys(sel.property('ADBE Text Index Start'), [[a, 0], [a + Math.max(3, n) * FR, n]]);
   // layer overshoot + settle, rotation
   keys(T(t).property('ADBE Scale'), [[a, [bs * 1.35, bs * 1.35]], [a + (n + 2) * FR, [bs * 0.96, bs * 0.96]], [a + (n + 6) * FR, [bs, bs]], [b, [bs * 1.06, bs * 1.06]]]); easeAll(T(t).property('ADBE Scale'), 80);
   keys(T(t).property('ADBE Rotate Z'), [[a, -4], [a + (n + 6) * FR, 0]]); easeAll(T(t).property('ADBE Rotate Z'), 70);
   T(t).property('ADBE Position').expression = 'var h=inPoint+' + ((n + 1) * FR).toFixed(3) + '; var k=Math.max(0,1-(time-h)/0.55); (time>h)? value+wiggle(28,26*k)-value : value';
   keys(T(t).property('ADBE Opacity'), [[b - 3 * FR, 100], [b, 0]]);
   // effects
   var fxp = t.property('ADBE Effect Parade');
   try { var td2 = fxp.addProperty('ADBE Turbulent Displace'); td2.name = 'ENERGY EDGE'; td2.property('Amount').setValue(14); td2.property('Size').setValue(22); td2.property('Evolution').expression = 'time*540'; } catch (x) { r.warn.push('turb ' + x); }
   try { var rgb = fxp.addProperty('S_DistortRGB'); rgb.name = 'RGB HIT'; dumpProps(rgb, 'S_DistortRGB'); keyP(rgb, ['Amp Red', 'Red Amp', 'Amplitude', 'Amp'], [[a + n * FR, 0.6], [a + (n + 8) * FR, 0]]); } catch (x) { r.warn.push('rgb ' + x); }
   try { var sg = fxp.addProperty('S_Glow'); sg.name = 'FIRE GLOW'; dumpProps(sg, 'S_Glow'); setP(sg, ['Color', 'Glow Color'], s.glow); setP(sg, ['Width X', 'Width', 'Glow Width'], 0.6); keyP(sg, ['Brightness', 'Glow Brightness'], [[a + n * FR, 3.5], [a + (n + 10) * FR, 1.4]]); } catch (x) { r.warn.push('sglow ' + x); }
   try { var ls = fxp.addProperty('CC Light Sweep'); ls.name = 'SWEEP'; keys(ls.property('Center'), [[a + (n + 2) * FR, [bx.left - 200, 0]], [a + (n + 14) * FR, [bx.left + bx.width + 200, 0]]]); ls.property('Sweep Intensity').setValue(70); } catch (x) { r.warn.push('sweep ' + x); }
   // impact shake on the footage too
   try { var ad = c.layers.addSolid([0, 0, 0], 'SHAKE ' + s.w, 1920, 1080, 1, c.duration); ad.adjustmentLayer = true; ad.inPoint = a; ad.outPoint = a + 0.8; ad.moveAfter(t);
    var shk = ad.property('ADBE Effect Parade').addProperty('S_Shake'); dumpProps(shk, 'S_Shake'); keyP(shk, ['Amplitude', 'Amp', 'Shake Amp'], [[a + n * FR, 0.6], [a + 0.8, 0]]); } catch (x) { r.warn.push('shake ' + x); }
  }
  app.endUndoGroup(); undo = false; pr.save(); r.saved = pr.file.fsName; r.compId = c.id; r.ok = true;
 } catch (e) { r.error = String(e) + ' line ' + e.line; if (undo) try { app.endUndoGroup(); } catch (x) {} }
 return done();
})();

