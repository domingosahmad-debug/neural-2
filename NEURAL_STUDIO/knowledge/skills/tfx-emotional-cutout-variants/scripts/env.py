import subprocess,sys,numpy as np
src,t0,t1=sys.argv[1],float(sys.argv[2]),float(sys.argv[3])
raw=subprocess.run(["ffmpeg","-v","error","-ss",str(t0),"-t",str(t1-t0),"-i",src,"-ac","1","-ar","8000","-af","highpass=f=200,lowpass=f=3500","-f","s16le","-"],capture_output=True).stdout
a=np.frombuffer(raw,np.int16).astype(float)
n=800 # 0.1s
for i in range(len(a)//n):
    r=np.sqrt((a[i*n:(i+1)*n]**2).mean()); db=20*np.log10(r+1)
    print(f"{t0+i*0.1:.1f}:{int(db)}",end=' ')
print()
