"""Contact sheet of source stills: args out.jpg then src@time[@gamma] ..."""
import sys, subprocess, io
from pathlib import Path
from PIL import Image, ImageDraw
S = Path("C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120")
SRC = {"P": S/"src/The Mentalist S01E01 Pilot.mp4", "E2": S/"src/The Mentalist S01E02 Red Hair and Silver Tape.mp4"}
PK = Path("C:/Users/TUF/Desktop/The Mentalist 2008 Season 6 Complete 720p AMZN WEBRip x264 [i_c]/short scene packs")
out, items = sys.argv[1], sys.argv[2:]
W, H = 480, 270
cols = 4
sheet = Image.new("RGB", (cols*W, ((len(items)+cols-1)//cols)*(H+18)))
d = ImageDraw.Draw(sheet)
for i, it in enumerate(items):
    parts = it.split("@"); k, t = parts[0], float(parts[1]); g = parts[2] if len(parts) > 2 else None
    p = SRC.get(k) or (PK / f"clip-{k}.mp4")
    vf = f"scale={W}:{H}" + (f",eq=gamma={g}" if g else "")
    b = subprocess.run(["ffmpeg","-v","error","-ss",str(t),"-i",str(p),"-frames:v","1","-vf",vf,"-f","image2pipe","-vcodec","png","-"],capture_output=True).stdout
    x, y = (i%cols)*W, (i//cols)*(H+18)
    if b: sheet.paste(Image.open(io.BytesIO(b)).convert("RGB"), (x, y+18))
    d.text((x+3, y+3), it, fill=(255,255,0))
sheet.save(S/out, quality=85); print("saved", out)
