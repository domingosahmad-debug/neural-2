import subprocess,sys,numpy as np
src,t1=sys.argv[1],float(sys.argv[2])
w,h=96,54
raw=subprocess.run(['ffmpeg','-v','error','-t',str(t1),'-i',src,'-vf',f'scale={w}:{h},format=gray','-f','rawvideo','-'],capture_output=True).stdout
F=np.frombuffer(raw,np.uint8).reshape(-1,h,w).astype(float)
d=np.abs(np.diff(F,axis=0)).mean(axis=(1,2))
cuts=[i+1 for i,v in enumerate(d) if v>18]
gaps=[(a,b-a) for a,b in zip(cuts,cuts[1:]) if b-a<=3]
print(src.split('/')[-1],'cuts',cuts,'short(<=3f)',gaps)
