"""Find a seamless 'return to HONORABLE' jump in S2 (Claude). Candidate jump: play S2 0->X, then continue from Y, where Y is a beat 0..12 beats
before the 29.002 drop (pickup) and X a beat in [70,100]. Score = cosine similarity of beat-synchronous chroma+MFCC over the 4 beats BEFORE X vs
the 4 beats before Y (context match) and the 4 beats from X vs from Y (continuation match). Also reports the crossfade-free sample offset.
Writes analysis/song/RETURN_CANDIDATES.json."""
import json, sys
from pathlib import Path
import numpy as np, librosa
sys.stdout.reconfigure(encoding='utf-8')
H = Path(__file__).resolve().parent
S = json.load(open(H / 'analysis/song/SONGS.json', encoding='utf-8'))['S2']
y, sr = librosa.load(S['file'], sr=22050, mono=True)
b = np.array(S['beats']); bf = librosa.time_to_frames(b, sr=sr, hop_length=512)
C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512); M = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, hop_length=512)
M = (M - M.mean(1, keepdims=True)) / (M.std(1, keepdims=True) + 1e-9)
F = np.vstack([librosa.util.sync(C, bf, aggregate=np.median), 0.5 * librosa.util.sync(M, bf, aggregate=np.mean)])  # per beat
F = F / (np.linalg.norm(F, axis=0, keepdims=True) + 1e-9)
def sim(i, j, n):  # mean cosine over n beats starting at beat i vs j
    return float(np.mean([F[:, i + k] @ F[:, j + k] for k in range(n)]))
i29 = int(np.argmin(abs(b - 29.002))); out = []
for py in range(0, 13):
    jy = i29 - py
    for jx in range(int(np.searchsorted(b, float(sys.argv[1]) if len(sys.argv) > 1 else 70)), int(np.searchsorted(b, float(sys.argv[2]) if len(sys.argv) > 2 else 100))):
        ctx = sim(jx - 4, jy - 4, 4); cont = sim(jx, jy, 4)
        out.append({'X': round(float(b[jx]), 3), 'Y': round(float(b[jy]), 3), 'pickup_beats': py, 'ctx': round(ctx, 3), 'cont': round(cont, 3), 'score': round(0.6 * ctx + 0.4 * cont, 3)})
out.sort(key=lambda r: -r['score'])
json.dump(out[:60], open(H / ('analysis/song/RETURN_CANDIDATES_%s_%s.json' % tuple(sys.argv[1:3]) if len(sys.argv) > 2 else 'analysis/song/RETURN_CANDIDATES.json'), 'w'), indent=0)
for r in out[:15]: print(r)

