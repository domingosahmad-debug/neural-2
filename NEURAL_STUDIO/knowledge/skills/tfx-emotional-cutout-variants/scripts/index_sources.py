"""Remux S1 episodes + S6 scene packs, transcribe (faster-whisper GPU), detect shots, make shot thumbnail sheets.
Also transcribe refB intro (dialogue check)."""
import subprocess, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

S = Path(r"C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
S1 = Path(r"C:/Users/TUF/Desktop/The Mentalist 2008 Season 1 Complete 720p AMZN WEBRip x264 [i_c]")
PACKS = Path(r"C:/Users/TUF/Desktop/The Mentalist 2008 Season 6 Complete 720p AMZN WEBRip x264 [i_c]/short scene packs")
RM = S / "src"; RM.mkdir(exist_ok=True)
IDX = S / "index"; IDX.mkdir(exist_ok=True)
W, H = 128, 72

def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    try:
        return float(r)
    except ValueError:
        return 0.0


srcs = []
for ep in sorted(S1.glob("*.mkv")):
    o = RM / f"{ep.stem}.mp4"
    if not o.exists() or abs(dur(o) - dur(ep)) > 1.0:
        print("remux", ep.name, flush=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ep), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(o)], check=True)
    srcs.append(o)
srcs += sorted(PACKS.glob("*.mp4"))


def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(p)], capture_output=True, text=True).stdout)
    st = j["streams"][0]; n, d = st["r_frame_rate"].split("/")
    return {"w": st["width"], "h": st["height"], "fps": float(n) / float(d), "dur": float(j["format"]["duration"])}


inv = {}
for p in srcs:
    tag = p.stem
    info = probe(p)
    print("shots", tag, info, flush=True)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    F = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    hist = np.stack([np.concatenate([np.histogram(f[..., c], 16, (0, 255))[0] for c in range(3)]) for f in F]).astype(np.float32)
    hist /= hist.sum(1, keepdims=True)
    hd = 0.5 * np.abs(np.diff(hist, axis=0)).sum(1)
    d = np.abs(np.diff(F.astype(np.int16), axis=0)).mean(axis=(1, 2, 3))
    cuts = [0] + [i + 1 for i in range(len(hd)) if hd[i] > 0.3 or (d[i] > 25 and d[i] > 3 * np.median(d[max(0, i - 8): i + 8]))] + [len(F)]
    shots = [(a, b) for a, b in zip(cuts[:-1], cuts[1:]) if b - a >= 6]
    luma = F.mean(axis=(1, 2, 3))
    inv[tag] = {"path": str(p), **info, "frames": len(F), "shots": [[a, b, round(a / info["fps"], 3), round(b / info["fps"], 3), round(float(luma[a:b].mean()), 1)] for a, b in shots]}
    # thumbnail sheets: middle frame of each shot, 10x8
    cols, rows = 10, 8
    for si in range(0, len(shots), cols * rows):
        sh = Image.new("RGB", (cols * W * 2, rows * (H * 2 + 14)))
        dr = ImageDraw.Draw(sh)
        for j, (a, b) in enumerate(shots[si: si + cols * rows]):
            m = (a + b) // 2
            x, y = (j % cols) * W * 2, (j // cols) * (H * 2 + 14)
            sh.paste(Image.fromarray(F[m]).resize((W * 2, H * 2)), (x, y + 14))
            dr.text((x + 2, y + 1), f"#{si+j} {a/info['fps']:.1f}-{b/info['fps']:.1f}s", fill=(255, 255, 0))
        sh.save(IDX / f"{tag[:40].replace(' ', '_')}_shots_{si:04d}.jpg", quality=82)
    del F
json.dump(inv, open(IDX / "inventory.json", "w"), indent=1)

from faster_whisper import WhisperModel
m = WhisperModel("medium.en", device="cuda", compute_type="float16")
targets = [p for p in srcs if p.parent == RM] + [S / "ref/refB.mp4", S / "ref/refA.mp4"]
for p in targets:
    o = IDX / f"{p.stem}.transcript.json"
    if o.exists():
        continue
    print("transcribe", p.name, flush=True)
    segs, _ = m.transcribe(str(p), word_timestamps=False, vad_filter=True, language="en")
    json.dump([[round(s.start, 2), round(s.end, 2), s.text.strip()] for s in segs], open(o, "w"), indent=0)
print("DONE")
