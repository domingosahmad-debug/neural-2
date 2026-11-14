"""Measured transition study (Claude, CPU only). For every hard cut in all 13 WE ON GO references: per-frame similarity fit (ORB + estimateAffinePartial2D,
320x180 gray) for the 14 frames before and after the cut, sharpness (Laplacian var) and luma. Classifies each cut:
  zoom_in_out = scale accelerates INTO the cut (cum >= 1.12 over last 6 frames) AND content shrinks after (cum <= 0.90 over first 6) -> Tony's flow pair
  zoom_in = only into; zoom_out = only after; whip = blur collapse (sharpness < 35% of median) at cut +/-1 with translation; flash = luma spike; hard = none.
Writes analysis/refs/TRANSITIONS.json with per-cut curves + per-type mean log-scale velocity profiles (normalised to each cut's peak) so the
easing shape (where the speed peaks, how long it settles) is measured, not guessed."""
import json, subprocess, sys
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding='utf-8')
H = Path(__file__).resolve().parent
A = json.load(open(H.parents[1] / 'shared' / 'BLEACH_WE_ON_GO_ASSETS_20261027.json', encoding='utf-8-sig'))
W, Hh, N = 320, 180, 14
orb = cv2.ORB_create(600)
def fit(a, b):
    ka, da = orb.detectAndCompute(a, None); kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 12 or len(kb) < 12: return None
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(m) < 10: return None
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None or inl is None or inl.sum() < 8: return None
    s = float(np.hypot(M[0, 0], M[1, 0])); return [s, float(M[0, 2]), float(M[1, 2]), float(inl.mean())]
out = {'refs': [], 'method': __doc__}
prof = {}
for i, ref in enumerate(A['references']):
    p = ref['path']; rid = 'R%02d' % (i + 1)
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'json', p], capture_output=True, text=True).stdout)
    n, d = pr['streams'][0]['r_frame_rate'].split('/'); fps = float(n) / float(d)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-vf', 'scale=%d:%d' % (W, Hh), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    F = np.frombuffer(raw, np.uint8).reshape(-1, Hh, W)
    hist = np.array([cv2.calcHist([f], [0], None, [32], [0, 256]).ravel() / (W * Hh) for f in F])
    hd = np.r_[0, 0.5 * np.abs(np.diff(hist, axis=0)).sum(1)]
    sharp = np.array([cv2.Laplacian(f, cv2.CV_32F).var() for f in F]); luma = F.reshape(len(F), -1).mean(1) / 255
    cuts = [k for k in range(2, len(F) - 2) if hd[k] > 0.30 and hd[k] >= hd[k - 1] and hd[k] >= hd[k + 1]]
    cuts = [k for j, k in enumerate(cuts) if j == 0 or k - cuts[j - 1] > 3]
    med = float(np.median(sharp)) + 1e-6; rows = []
    for k in cuts:
        pre = [fit(F[j - 1], F[j]) for j in range(max(1, k - N), k)]          # motion within outgoing shot
        post = [fit(F[j], F[j + 1]) for j in range(k, min(len(F) - 1, k + N))]  # motion within incoming shot
        ps = [x[0] if x else 1.0 for x in pre]; qs = [x[0] if x else 1.0 for x in post]
        cin = float(np.prod(ps[-6:])); cout = float(np.prod(qs[:6]))
        blur = float(min(sharp[k - 1:k + 2]) / med); flash = float(luma[k - 1:k + 2].max() - np.median(luma[max(0, k - 8):k + 8]))
        trans = max([abs(x[1]) + abs(x[2]) for x in (pre[-2:] + post[:2]) if x] or [0])
        typ = 'zoom_in_out' if (cin >= 1.12 and cout <= 0.90) else 'zoom_in' if cin >= 1.12 else 'zoom_out' if cout <= 0.90 else 'whip' if (blur < 0.35 and trans > 6) else 'flash' if flash > 0.25 else 'hard'
        rows.append({'f': k, 't': round(k / fps, 3), 'type': typ, 'cin': round(cin, 3), 'cout': round(cout, 3), 'blur': round(blur, 2), 'flash': round(flash, 2),
                     'pre_scale': [round(x, 4) for x in ps], 'post_scale': [round(x, 4) for x in qs], 'pre_inl': [round(x[3], 2) if x else 0 for x in pre], 'post_inl': [round(x[3], 2) if x else 0 for x in post]})
        if typ in ('zoom_in_out', 'zoom_in', 'zoom_out'):
            v = np.r_[np.log(np.array(ps + [1.0] * (N - len(ps)))[:N]), np.log(np.array(qs + [1.0] * (N - len(qs)))[:N])]
            pk = np.abs(v).max() + 1e-9; prof.setdefault(typ, []).append((v / pk).tolist())
    cnt = {}
    for r in rows: cnt[r['type']] = cnt.get(r['type'], 0) + 1
    out['refs'].append({'ref': rid, 'file': Path(p).name, 'fps': round(fps, 3), 'frames': len(F), 'cuts': len(rows), 'counts': cnt, 'rows': rows})
    print(rid, round(fps, 2), len(F), 'cuts', len(rows), cnt, flush=True)
out['profiles'] = {k: {'n': len(v), 'mean_norm_logscale_velocity_pre_then_post': np.round(np.mean(v, 0), 3).tolist()} for k, v in prof.items()}
json.dump(out, open(H / 'analysis' / 'refs' / 'TRANSITIONS.json', 'w'), indent=0)
for k, v in out['profiles'].items(): print(k, v['n'], v['mean_norm_logscale_velocity_pre_then_post'])
