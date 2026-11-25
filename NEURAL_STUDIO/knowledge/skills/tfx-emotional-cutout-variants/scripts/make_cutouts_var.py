"""Per-version SAM2 cutouts. make_cutouts_var.py spec.json -> cutouts/<V>_cut<n>/<V>_cut<n>_####.png. Never touches cut1/cut2 (v4).
spec: {"V5A": {"1": {"src":..., "in":..., "nf":36, "box":[x0,y0,x1,y1] optional}, ...}, ...}"""
import json, os, subprocess, sys, tempfile, shutil, glob
from pathlib import Path
import cv2, numpy as np, torch
from PIL import Image
S = Path(r"C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
sys.path.insert(0, r"C:/Users/TUF/Documents/KINTAKI_STANDUP_CLAUDE_20261119/py")
from sam2_nohydra import build
from ultralytics import YOLO
spec = json.load(open(sys.argv[1]))
OUT = S / "cutouts"
def src(p): return str(S / p) if not os.path.isabs(p) else p
yolo = YOLO(r"C:/Users/TUF/Documents/TonyFX Vision Engine/models/yolo11n.pt")
pred = build("configs/sam2.1/sam2.1_hiera_s.yaml", r"C:/Users/TUF/Documents/TonyFX Vision Engine/models/sam2.1_hiera_small.pt")
qa = []
bgq = np.array(Image.open(OUT / "bg_B.png").convert("RGB"))
for V, cuts in spec.items():
    for n, c in cuts.items():
        nm = f"{V}_cut{n}"; d = OUT / nm
        assert nm not in ("cut1", "cut2")
        d.mkdir(exist_ok=True)
        for f in glob.glob(str(d / f"{nm}_*.png")): os.remove(f)
        tmp = tempfile.mkdtemp(prefix=f"jv{n}_")
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(c["in"]), "-i", src(c["src"]), "-vf", "fps=30,scale=1920:1080:flags=lanczos", "-frames:v", str(c["nf"]), "-q:v", "1", "-start_number", "0", str(Path(tmp) / "%05d.jpg")], check=True)
            nfr = len(glob.glob(str(Path(tmp) / "*.jpg")))
            im0 = cv2.imread(str(Path(tmp) / "00000.jpg")); h, w = im0.shape[:2]
            if c.get("box"):
                best = np.array(c["box"], float)
            else:
                boxes = yolo.predict(im0, classes=[0], conf=0.25, verbose=False)[0].boxes.xyxy.cpu().numpy()
                best = max(boxes, key=lambda b: ((b[2]-b[0])*(b[3]-b[1]))/(w*h) - 0.8*(((b[0]+b[2])/(2*w)-0.5)**2+((b[1]+b[3])/(2*h)-0.45)**2)**0.5)
            print(f"{nm}: {nfr} frames, box {best.round(1).tolist()}", flush=True)
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                st = pred.init_state(video_path=tmp, offload_video_to_cpu=True)
                pred.add_new_points_or_box(inference_state=st, frame_idx=0, obj_id=1, box=best)
                masks = {i: (lg[0, 0] > 0).float().cpu().numpy() for i, _, lg in pred.propagate_in_video(st)}
                pred.reset_state(st)
            cov = []
            for i in range(nfr):
                rgb = cv2.cvtColor(cv2.imread(str(Path(tmp) / f"{i:05d}.jpg")), cv2.COLOR_BGR2RGB)
                m = cv2.morphologyEx((masks[i] * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
                a = cv2.GaussianBlur(m, (5, 5), 1.2); cov.append(float((a > 128).mean()))
                Image.fromarray(np.dstack([rgb, a]), "RGBA").save(d / f"{nm}_{i:04d}.png")
                if i in (0, nfr//2, nfr-1):
                    af = a[..., None] / 255.0
                    t = Image.fromarray((rgb*af + bgq*(1-af)).astype(np.uint8)).resize((640, 360))
                    from PIL import ImageDraw; ImageDraw.Draw(t).text((6, 6), f"{nm} f{i}", fill=(255, 255, 0)); qa.append(t)
            print(f"{nm}: coverage min {min(cov):.3f} max {max(cov):.3f}", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
sheet = Image.new("RGB", (1920, 360 * ((len(qa)+2)//3)))
for i, t in enumerate(qa): sheet.paste(t, ((i % 3) * 640, (i // 3) * 360))
sheet.save(S / "cutouts/cutout_var_qa.jpg", quality=88); print("DONE")
