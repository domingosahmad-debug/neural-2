"""Tile single frames: args = out.jpg then src|t|label ... (src: P=Pilot, E2=S1E02, or pack clip id)."""
import sys, subprocess, io
from pathlib import Path
from PIL import Image, ImageDraw
S = Path(r"C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
PK = Path(r"C:/Users/TUF/Desktop/The Mentalist 2008 Season 6 Complete 720p AMZN WEBRip x264 [i_c]/short scene packs")
def path(k):
    if k == "P": return S / "src/The Mentalist S01E01 Pilot.mp4"
    if k == "E2": return next((S / "src").glob("*S01E02*.mp4"))
    return PK / f"{k}.mp4"
out = sys.argv[1]; items = [a.split("|") for a in sys.argv[2:]]
TW, TH, C = 480, 270, 4
sheet = Image.new("RGB", (C * TW, ((len(items) + C - 1) // C) * (TH + 16)))
d = ImageDraw.Draw(sheet)
for i, (k, t, lab) in enumerate(items):
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", t, "-i", str(path(k)), "-frames:v", "1", "-vf", f"scale={TW}:{TH}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    x, y = (i % C) * TW, (i // C) * (TH + 16)
    if b: sheet.paste(Image.open(io.BytesIO(b)).convert("RGB"), (x, y + 16))
    d.text((x + 3, y + 2), f"{lab} {k}@{t}", fill=(255, 255, 0))
sheet.save(out, quality=85)
