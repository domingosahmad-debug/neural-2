"""Contact sheet of a source at given times: tsheet.py src out t1 t2 ..."""
import sys, subprocess
from PIL import Image, ImageDraw
src,out=sys.argv[1],sys.argv[2]; ts=[float(x) for x in sys.argv[3:]]
W,H=384,216; cols=6; rows=(len(ts)+cols-1)//cols
im=Image.new('RGB',(W*cols,H*rows))
for i,t in enumerate(ts):
    p=subprocess.run(["ffmpeg","-loglevel","error","-ss",str(t),"-i",src,"-frames:v","1","-vf",f"scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
    if len(p)==W*H*3:
        f=Image.frombytes('RGB',(W,H),p); ImageDraw.Draw(f).text((4,4),str(t),fill=(255,255,0)); im.paste(f,((i%cols)*W,(i//cols)*H))
im.save(out,quality=80)
