import sys, subprocess, numpy as np
f, M = sys.argv[1], int(sys.argv[2])
raw = subprocess.run(["ffmpeg","-v","error","-i",f,"-vf","scale=96:54,format=gray","-f","rawvideo","-"],capture_output=True).stdout
a = np.frombuffer(raw,np.uint8).reshape(-1,54,96).astype(float)
n=len(a); mean=a.mean((1,2)); top=a[:,:4].mean((1,2)); bot=a[:,-4:].mean((1,2))
dark=[i for i in range(n) if mean[i]<12]
bars=[i for i in range(n) if top[i]<6 and bot[i]<6 and mean[i]>25]
def runs(x):
    r=[];s=None
    for i in x:
        if s is None or i!=p+1:
            if s is not None: r.append((s,p))
            s=i
        p=i
    if s is not None: r.append((s,p))
    return [(a-M,b-M) for a,b in r]
print(f, "frames",n,"dark(rel M)",runs(dark),"barlike",runs(bars)[:10])
