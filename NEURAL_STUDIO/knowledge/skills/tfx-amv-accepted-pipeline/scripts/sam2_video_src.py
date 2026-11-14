"""SAM2.1 video matte for one shot (Claude). Prompts (full-frame + crop-refine points) on a key frame, propagated both ways.
Usage: sam2_video.py <config.json>   config: {tag, ss, nframes, key_t, pos, neg, crop_pos, crop_neg}
Outputs matte_seq/<tag>/: src/<frame>.jpg, mask/<frame>.png, rgba/<tag>_<frame>.png (premultiplied-free RGBA cutout), QA_<tag>.jpg, REPORT.json"""
import sys, json, subprocess, math, time
from pathlib import Path
H = Path(r'C:/Users/TUF/Documents/New project/NEURAL_STUDIO/data/bleach-bankai-two-edits-20261025'); OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(H / 'vendor/sam2src/sam2-2b90b9f5ceec907a1c18123530e92e794ad901a4'))
import numpy as np, torch, cv2
from PIL import Image, ImageDraw
CK = H / 'models/sam2/sam2.1_hiera_small.pt'; assert CK.stat().st_size == 184416285
EP05 = r'C:/Users/TUF/Videos/Clips for edits/Bleach/Bleach TYBW - Ep 05 - DEFEND YOU (RAW No Subs).mp4'
C = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
D = OUT / 'matte_seq' / C['tag']; S = D / 'src'; M = D / 'mask'; R = D / 'rgba'
for p in (S, M, R): p.mkdir(parents=True, exist_ok=True)
fps = 24000 / 1001; f0 = math.ceil(C['ss'] * fps - 1e-6)
if not any(S.iterdir()):
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', f"{C['ss']:.4f}", '-i', C.get('src', EP05), '-frames:v', str(C['nframes']), '-q:v', '1', '-start_number', '0', str(S / '%05d.jpg')], check=True, timeout=300)
frames = sorted(S.glob('*.jpg')); n = len(frames)
key = int(round(C['key_t'] * fps)) - f0
from sam2.build_sam import build_sam2_video_predictor
t0 = time.time()
pr = build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_s.yaml', str(CK), device='cuda')
P = C['pos'] + C.get('crop_pos', []); N = C['neg'] + C.get('crop_neg', [])
pts = np.array(P + N, np.float32); lab = np.array([1] * len(P) + [0] * len(N), np.int32)
out = {}
with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
    st = pr.init_state(video_path=str(S), offload_video_to_cpu=True, offload_state_to_cpu=True)
    pr.add_new_points_or_box(st, frame_idx=key, obj_id=1, points=pts, labels=lab)
    for K in C.get('keys', []):   # extra keyframes: {"frame": src_frame, "pos": [...], "neg": [...]}
        pk = np.array(K['pos'] + K.get('neg', []), np.float32); lk = np.array([1] * len(K['pos']) + [0] * len(K.get('neg', [])), np.int32)
        pr.add_new_points_or_box(st, frame_idx=int(K['frame']) - f0, obj_id=1, points=pk, labels=lk)
    for rev in (False, True):
        for fi, ids, logits in pr.propagate_in_video(st, start_frame_idx=key, reverse=rev):
            out[fi] = (logits[0, 0] > 0).float().cpu().numpy()
def clean(m):
    m = (m > 0).astype(np.uint8) * 255
    inv = (m == 0).astype(np.uint8); k, lb, stt, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, k):
        x, y, w, h, a = stt[i]
        if a < 0.004 * m.size and x > 0 and y > 0 and x + w < m.shape[1] and y + h < m.shape[0]: m[lb == i] = 255
    k, lb, stt, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)   # drop tiny islands (specks)
    for i in range(1, k):
        if stt[i][4] < 0.0008 * m.size: m[lb == i] = 0
    return m
cov = []
for i, fp in enumerate(frames):
    m = clean(out[i]); Image.fromarray(m).save(M / f'{f0 + i}.png')
    im = Image.open(fp).convert('RGB'); rgba = im.copy(); rgba.putalpha(Image.fromarray(m)); rgba.save(R / f"{C['tag']}_{f0 + i:05d}.png")
    cov.append(round(float((m > 0).mean()), 4))
# QA sheet: 12 evenly spaced frames, green edge, hands crop
pick = [int(round(j * (n - 1) / 11)) for j in range(12)]; tiles = []
for i in pick:
    im = np.asarray(Image.open(frames[i]).convert('RGB')).copy(); m = np.asarray(Image.open(M / f'{f0 + i}.png'))
    e = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0; im[e] = [0, 255, 0]
    t = Image.fromarray(im).resize((640, 360)); ImageDraw.Draw(t).text((6, 4), f'src frame {f0 + i}  cov {cov[i]}', fill=(255, 255, 0)); tiles.append(t)
Q = Image.new('RGB', (640 * 3, 360 * 4))
for j, t in enumerate(tiles): Q.paste(t, ((j % 3) * 640, (j // 3) * 360))
Q.save(D / f"QA_{C['tag']}.jpg", quality=88)
rep = {'tag': C['tag'], 'first_src_frame': f0, 'n': n, 'key_index': key, 'coverage': cov, 'secs': round(time.time() - t0, 1),
       'model': 'sam2.1_hiera_small sha256 6d1aa6f3...', 'code': 'facebookresearch/sam2@2b90b9f', 'artistic_acceptance': 'NOT TESTED'}
(D / 'REPORT.json').write_text(json.dumps(rep, indent=1)); print(json.dumps({k: v for k, v in rep.items() if k != 'coverage'}), 'cov min/max', min(cov), max(cov))

