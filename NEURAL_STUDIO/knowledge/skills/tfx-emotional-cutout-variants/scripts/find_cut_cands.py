"""Find single-person centred close-up shots (>=1.8s) for per-version cutouts. Writes plan/r3/cut_cands.json + sheets."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO
S = Path(r"C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
inv = json.load(open(S / "index/inventory_s6.json"))
yolo = YOLO(r"C:/Users/TUF/Documents/TonyFX Vision Engine/models/yolo11n.pt")
W, H = 640, 360
out = []
def grab(src, t):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", src, "-frames:v", "1", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(p, np.uint8).reshape(H, W, 3) if len(p) == W*H*3 else None
for ep, v in inv.items():
    if "E06" in ep: continue
    for s in v["shots"]:
        a, b = s[2], s[3]
        if not (1.8 <= b - a <= 9): continue
        t = round(a + 0.3, 2)
        im = grab(v["path"], t)
        if im is None or im.mean() < 25: continue
        r = yolo.predict(im, classes=[0], conf=0.35, verbose=False)[0].boxes
        bx = r.xyxy.cpu().numpy()
        if len(bx) == 0: continue
        big = [x for x in bx if (x[3]-x[1]) > 0.75*H]
        if len(big) != 1: continue
        x = big[0]; cx = (x[0]+x[2])/2/W
        if not (0.3 < cx < 0.7) or (x[2]-x[0]) > 0.75*W: continue
        out.append(dict(ep=ep[19:22] if False else ep.split()[2], src=v["path"], a=a, b=b, t=t, cx=round(float(cx), 2), w=round(float((x[2]-x[0])/W), 2)))
        print(out[-1]["ep"], a, b, flush=True)
(S / "plan/r3").mkdir(parents=True, exist_ok=True)
json.dump(out, open(S / "plan/r3/cut_cands.json", "w"), indent=0)
cols = 6; tw, th = 320, 180
for pg in range(0, len(out), 48):
    chunk = out[pg:pg+48]; sh = Image.new("RGB", (tw*cols, th*((len(chunk)+cols-1)//cols)))
    for i, c in enumerate(chunk):
        im = Image.fromarray(grab(c["src"], c["t"] + 0.5)).resize((tw, th))
        ImageDraw.Draw(im).text((4, 4), f"{pg+i} {c['ep']} {c['a']}-{c['b']}", fill=(255, 255, 0))
        sh.paste(im, ((i % cols)*tw, (i//cols)*th))
    sh.save(S / f"plan/r3/cut_cands_{pg//48}.jpg", quality=80)
print("DONE", len(out))
