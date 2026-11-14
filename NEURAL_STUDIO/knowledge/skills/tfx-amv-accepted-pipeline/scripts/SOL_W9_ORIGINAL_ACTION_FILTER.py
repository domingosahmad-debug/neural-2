"""Bounded source-aware action candidate. No ML/download; shared engine prepared exact raw input.
Stereo shared spectral mask suppresses stable tonal energy; retains broadband/transient source material.
This cannot identify all anime score/percussion vs SFX. Listening/artifact/leakage gate remains NOT TESTED.
"""
from pathlib import Path
import json,time,numpy as np,soundfile as sf
from scipy import signal,ndimage
ROOT=Path(__file__).resolve().parent
INPUT=ROOT.parent/'local-ops/jobs/5afcb7cf9a434186953061f18b3b0924/hado_dragons/audio.wav'
OUT=ROOT/'audio_w9';OUT.mkdir(exist_ok=True)
t=time.time();x,sr=sf.read(INPUT,dtype='float32',always_2d=True)
assert sr==48000 and len(x)<sr*30 and x.shape[1]==2
# 42.7ms STFT,5.33ms hop. Common stereo mask preserves inter-channel relationships.
f,tt,Z=signal.stft(x.T,fs=sr,nperseg=2048,noverlap=1792,boundary='zeros',padded=True)
mag=np.mean(np.abs(Z),axis=0)
h=ndimage.median_filter(mag,size=(1,65),mode='nearest')
p=ndimage.median_filter(mag,size=(31,1),mode='nearest')
m=(p*p)/(p*p+2.5*h*h+1e-12)
# Keep limited noise tail while suppressing stable score. No fabricated replacements.
m=.035+.965*m
m*=np.minimum(1,(f/85)**2)[:,None]
_,y=signal.istft(Z*m[None,:,:],fs=sr,nperseg=2048,noverlap=1792,boundary=True)
y=y.T[:len(x)].astype('float32')
# Preserve sample span/duration. Short click-prevention fades only.
fi=int(.006*sr);fo=int(.035*sr);y[:fi]*=np.linspace(0,1,fi)[:,None];y[-fo:]*=np.linspace(1,0,fo)[:,None]
sf.write(OUT/'HADO_SOURCE_TRANSIENT_CANDIDATE_FLOAT.wav',y,sr,subtype='FLOAT')
sf.write(OUT/'HADO_REMOVED_TONAL_REFERENCE_FLOAT.wav',x-y,sr,subtype='FLOAT')
rep={'input':str(INPUT),'original_episode':'EP08','original_source_in':857.30,'original_source_out':885.05,'original_channels':'stereoJapaneseAAC; no discreteFX','method':'common-stereo harmonic/percussive median mask; temporal65STFTsteps,frequency31bins,power2,Hfactor2.5,floor.035,HP85Hz','model':'none; no download','samples':len(y),'rate':sr,'source_alignment':'No source-time shift, duration/sample count retained. Native shot gap/retime mapping required before mix.','peak':float(np.max(np.abs(y))),'rms_before':float(np.sqrt(np.mean(x*x))),'rms_candidate':float(np.sqrt(np.mean(y*y))),'seconds':round(time.time()-t,3),'quality':'NOT TESTED by listening; stable score suppressed mathematically, BGMpercussion and voicefricatives may remain; sustained pitchedSFX may be attenuated. Candidate only, not approved/restored finalaudio.'}
(OUT/'HADO_CANDIDATE_REPORT.json').write_text(json.dumps(rep,indent=2),encoding='utf-8');print(json.dumps(rep))
