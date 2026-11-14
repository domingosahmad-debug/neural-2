"""Whole-render micro-cut audit (from the accepted WE ON GO edit).
Usage: python -I short_shot_audit.py <render.mp4> [min_frames=12] [out.json]
Detects hard cuts (32-bin luma histogram distance > 0.30, local maxima) on a 320x180 decode and lists every segment shorter
than min_frames. Each listed segment must then be LOOKED AT: a foreign shot fragment is a defect (remove/rebuild the window on
real source cuts); a same-shot strobe/energy flash is source animation (disclose, trim around it if it still reads as a glitch).
Tony's rule: no split-second foreign scenes anywhere in the edit."""
import json, subprocess, sys
import numpy as np, cv2
src = sys.argv[1]; minf = int(sys.argv[2]) if len(sys.argv) > 2 else 12; out = sys.argv[3] if len(sys.argv) > 3 else None
fps_s = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout.strip()
n, d = fps_s.split('/'); fps = float(n) / float(d)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vf', 'scale=320:180', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
F = np.frombuffer(raw, np.uint8).reshape(-1, 180, 320)
h = [cv2.calcHist([f], [0], None, [32], [0, 256]).ravel() / 57600 for f in F]
dd = np.array([0] + [0.5 * np.abs(h[i] - h[i - 1]).sum() for i in range(1, len(h))])
cuts = [i for i in range(1, len(dd)) if dd[i] > 0.30 and dd[i] >= dd[i - 1] and (i + 1 >= len(dd) or dd[i] >= dd[i + 1])]
seg = list(zip([0] + cuts, cuts + [len(F)]))
short = [{'t0': round(a / fps, 3), 't1': round(b / fps, 3), 'frames': b - a} for a, b in seg if b - a < minf]
print('frames', len(F), 'cuts', len(cuts), 'short(<%d f)' % minf, len(short))
for s in short: print(s)
if out: json.dump({'src': src, 'fps': fps, 'cuts': [round(c / fps, 3) for c in cuts], 'short': short}, open(out, 'w'), indent=1)
