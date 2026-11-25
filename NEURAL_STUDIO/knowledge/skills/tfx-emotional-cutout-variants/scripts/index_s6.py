"""Remux S6 full episodes to src/*.mp4 and detect shots -> index/inventory_s6.json + shot sheets in index/s6/."""
import subprocess, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
S = Path("C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
D = Path("C:/Users/TUF/Desktop/The Mentalist 2008 Season 6 Complete 720p AMZN WEBRip x264 [i_c]")
W, H = 128, 72
inv = {}
for ep in sorted(D.glob("*.mkv")):
    o = S / "src" / f"{ep.stem}.mp4"
    if not o.exists():
        print("remux", ep.name, flush=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ep), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(o)], check=True)
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "json", str(o)], capture_output=True, text=True).stdout)
    n, d = j["streams"][0]["r_frame_rate"].split("/"); fps = float(n) / float(d)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(o), "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    F = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    hist = np.stack([np.concatenate([np.histogram(f[..., c], 16, (0, 255))[0] for c in range(3)]) for f in F]).astype(np.float32)
    hist /= hist.sum(1, keepdims=True)
    hd = 0.5 * np.abs(np.diff(hist, axis=0)).sum(1)
    dd = np.abs(np.diff(F.astype(np.int16), axis=0)).mean(axis=(1, 2, 3))
    cuts = [0] + [i + 1 for i in range(len(hd)) if hd[i] > 0.3 or (dd[i] > 25 and dd[i] > 3 * np.median(dd[max(0, i - 8): i + 8]))] + [len(F)]
    shots = [(a, b) for a, b in zip(cuts[:-1], cuts[1:]) if b - a >= 6]
    luma = F.mean(axis=(1, 2, 3))
    tag = ep.stem[:20].replace(" ", "_")
    inv[ep.stem] = {"path": str(o), "fps": fps, "frames": len(F), "shots": [[a, b, round(a / fps, 3), round(b / fps, 3), round(float(luma[a:b].mean()), 1)] for a, b in shots]}
    cols, rows = 10, 8
    for si in range(0, len(shots), cols * rows):
        sh = Image.new("RGB", (cols * W * 2, rows * (H * 2 + 14)))
        dr = ImageDraw.Draw(sh)
        for k, (a, b) in enumerate(shots[si: si + cols * rows]):
            m = (a + b) // 2
            x, y = (k % cols) * W * 2, (k // cols) * (H * 2 + 14)
            sh.paste(Image.fromarray(F[m]).resize((W * 2, H * 2)), (x, y + 14))
            dr.text((x + 2, y + 1), f"#{si+k} {a/fps:.1f}-{b/fps:.1f}s", fill=(255, 255, 0))
        sh.save(S / "index/s6" / f"{tag}_shots_{si:04d}.jpg", quality=80)
    print("done", ep.stem, len(shots), flush=True)
    del F
    json.dump(inv, open(S / "index/inventory_s6.json", "w"), indent=0)
print("ALL DONE")
