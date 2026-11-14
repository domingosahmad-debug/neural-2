"""Offline clip diagnosis for one time window of an AE mix (from the accepted WE ON GO edit).
Usage: python -I mix_window_sum.py layers.json A B
layers.json: [{"name":..., "src": "<audio/video file>", "st": layer startTime, "inP": in, "outP": out,
               "lvl": dB  OR  [[comp_time, [dB, dB]], ...] (keys as read by a TonyFX probe), "group": "tony|voice|music|sfx"}]
Reproduces each enabled layer's contribution (source offset = comp - startTime, level keys linearly interpolated) and prints
per-layer peaks, the summed peak, and the summed peak for trial group trims. Use it to choose the SMALLEST balanced gain change
that removes a measured clip, instead of guessing and re-rendering. Manual client layers keep their timing; only levels change."""
import json, subprocess, sys, itertools
import numpy as np
SR = 48000
L = json.load(open(sys.argv[1], encoding='utf-8')); A, B = float(sys.argv[2]), float(sys.argv[3]); N = int((B - A) * SR)
def rd(p, ss, t):
    return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(max(0, ss)), '-t', str(t), '-i', p, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True).stdout, np.float32).reshape(-1, 2)
def lv(l, t):
    if not isinstance(l, list): return float(l)
    ks = [(k[0], k[1][0]) for k in l]
    if t <= ks[0][0]: return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t0 <= t <= t1: return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return ks[-1][1]
groups = {}
for a in L:
    if a['outP'] < A or a['inP'] > B: continue
    s0, s1 = max(A, a['inP']), min(B, a['outP']); x = rd(a['src'], s0 - a['st'], s1 - s0); t = np.arange(len(x)) / SR + s0
    g = np.repeat(np.array([10 ** (lv(a['lvl'], tt) / 20) for tt in t[::480]]), 480)[:len(x)]
    y = np.zeros((N, 2), np.float32); i0 = int((s0 - A) * SR); n = min(len(x), N - i0); y[i0:i0 + n] = x[:n] * g[:n, None]
    print('%-50s pk %.3f' % (a['name'][:50], float(np.abs(y).max())))
    groups[a.get('group', 'other')] = groups.get(a.get('group', 'other'), 0) + y
tot = sum(groups.values()); print('SUM peak %.3f' % float(np.abs(tot).max()))
names = list(groups); trims = [0, -3, -6, -10, -12]
for combo in itertools.product(trims, repeat=len(names)):
    pk = float(np.abs(sum(groups[k] * 10 ** (d / 20) for k, d in zip(names, combo))).max())
    if pk < 0.90: print(dict(zip(names, combo)), '-> %.3f' % pk); break
