"""W9 bounded CPU source-SFX preparation, not an acoustic approval or universal separator.
Shared local engine already extracted/probed every raw input. Advanced scene-aware mask/warp unsupported there.
No model/download. At most ~1chunk stereoSTFT memory; finite12buckets. Complete dialogue owners untouched.
"""
from pathlib import Path
import json,time,sys,numpy as np,soundfile as sf
from scipy import signal,ndimage
ROOT=Path(__file__).resolve().parent;STUDIO=ROOT.parents[1];OUT=ROOT/'audio_w9/v2';OUT.mkdir(parents=True,exist_ok=True)
META=json.loads((ROOT/'SOL_W9C_PROOF_REVIEW_AND_ACTION_PLAN.json').read_text(encoding='utf-8'))
SRCJOB=STUDIO/'data/local-ops/jobs/5afcb7cf9a434186953061f18b3b0924'
assert SRCJOB.exists(),str(SRCJOB)
buckets=META['source_events']+[{'tag':'shatter_stab','ep':'EP08','source_in':920.8,'source_out':929.8}]
STEMS=json.loads((ROOT/'voices/STEMS.json').read_text(encoding='utf-8'))
quote_cache={k:v for k,v in STEMS.items()}
reports=[];cache={};sr=48000

def load_part(file,a,b):
 with sf.SoundFile(file) as f:
  fs=f.samplerate;f.seek(max(0,int(round(a*fs))));x=f.read(max(0,int(round((b-a)*fs))),dtype='float32',always_2d=True)
 if fs!=sr:x=signal.resample_poly(x,sr//np.gcd(sr,fs),fs//np.gcd(sr,fs),axis=0)
 return x

def transient_filter(x):
 out=np.zeros_like(x);span=8*sr;guard=19200
 for a in range(0,len(x),span):
  b=min(len(x),a+span);la=max(0,a-guard);lb=min(len(x),b+guard)
  f,tt,Z=signal.stft(x[la:lb].T,fs=sr,nperseg=2048,noverlap=1792,boundary='zeros',padded=True)
  mag=np.mean(np.abs(Z),axis=0);h=ndimage.median_filter(mag,size=(1,65),mode='nearest');p=ndimage.median_filter(mag,size=(31,1),mode='nearest')
  mask=.035+.965*(p*p)/(p*p+2.5*h*h+1e-12);mask*=np.minimum(1,(f/85)**2)[:,None]
  _,y=signal.istft(Z*mask[None,:,:],fs=sr,nperseg=2048,noverlap=1792,boundary=True);out[a:b]=y.T[a-la:b-la]
 return out

for B in buckets:
 tag=B['tag'];raw=SRCJOB/tag/'audio.wav'
 if tag=='shatter_stab':raw=STUDIO/'data/local-ops/jobs/8af77944f9474b6bb9729f10fd4e651e/shatter_stab/audio.wav'
 dest=OUT/(tag+'_TRANSIENT_FLOAT.wav');rf=OUT/(tag+'_REPORT.json')
 if dest.exists() and rf.exists():
  reports.append(json.loads(rf.read_text(encoding='utf-8')));print('REUSE',tag,flush=True);continue
 t=time.time();x=load_part(raw,0,B['source_out']-B['source_in']);original=x.copy();patch=[]
 # Only source origins documented in STEMS.json are used. Unknown ep8_*cache origins are not guessed.
 for q,V in quote_cache.items():
  if V['ep']!=B['ep']:continue
  a=max(B['source_in'],V['a']);b=min(B['source_out'],V['b']);nv=ROOT/'voices/tmp/sep/htdemucs'/q/'no_vocals.wav'
  if b-a<.03 or not nv.exists():continue
  y=load_part(nv,a-V['a'],b-V['a']);i=round((a-B['source_in'])*sr);n=min(len(y),len(x)-i,round((b-a)*sr))
  if n<=0:continue
  w=np.ones(n,np.float32);fade=min(round(.02*sr),n//2);w[:fade]=np.linspace(0,1,fade);w[-fade:]=np.linspace(1,0,fade)
  x[i:i+n]=x[i:i+n]*(1-w[:,None])+y[:n]*w[:,None];patch.append({'quote':q,'source_in':a,'source_out':b,'nonvocal_file':str(nv),'origin_provenance':'STEMS.json original quote range; no raw-music substitution'})
 # EP05 long chapter cache1014 origin was documented and the complete Getsuga performance verified previously.
 if tag=='ep05_getsuga':
  nv=ROOT/'voices/tmp/sep/htdemucs/ep5_1014_end/no_vocals.wav'
  if nv.exists():
   y=load_part(nv,B['source_in']-1014,B['source_out']-1014);n=min(len(y),len(x));x[:n]=y[:n];patch.append({'chapter':'ep5_1014_end','source_origin':1014,'nonvocal_file':str(nv),'origin_provenance':'STATE W7 full source exchange preparation; same verified chapter start'})
 y=transient_filter(x);sf.write(dest,y,sr,subtype='FLOAT');cache[tag]=y
 rep={'tag':tag,'episode':B['ep'],'original_source_in':B['source_in'],'original_source_out':B['source_out'],'raw':str(raw),'output':str(dest),'samples':len(y),'sample_rate':sr,'candidate_peak':float(np.max(np.abs(y))),'rms_raw':float(np.sqrt(np.mean(original*original))),'rms_candidate':float(np.sqrt(np.mean(y*y))),'cached_nonvocal_patches':patch,'method':'Documented-source Demucs no_vocals where available, then common-stereo harmonic/percussive STFT2048/hop256,median65temporal/31frequency,H2.5,floor.035,HP85Hz;8sCPU chunks with400mscontext','quality':'CANDIDATE. Listening NOT TESTED; BGMpercussion/fricatives may remain and pitchedSFX may be attenuated. No model download or stock replacement.','elapsed_seconds':round(time.time()-t,3)}
 rf.write_text(json.dumps(rep,indent=2),encoding='utf-8');reports.append(rep);print('BUILT',tag,round(rep['elapsed_seconds'],2),round(rep['candidate_peak'],3),flush=True)

# Exact source-to-picture map for each intended audible event, retaining current native cuts and all voice/music.
base=json.loads((ROOT/'SOL_W9D_AFTER_SNAPSHOT.json').read_text(encoding='utf-8'))['compositions'][0]
rows=json.loads((ROOT/'SOL_W9_BASE_PICTURE_LEDGER.json').read_text(encoding='utf-8'))
skip={'s01','s02','s03','c4','d1','d2','d3','p1'} # speaking/reaction stills retain existing complete voice; avoid arbitrary added speech/fricatives.
events=[]
# Actual continuous source relationships are preserved; no generic stock event call-outs invented.
for L in sorted(rows,key=lambda z:z['in']):
 tag=L['name'].split(' |')[0]
 if tag in skip:continue
 a=L['in'];b=L['out']
 if tag=='s06':b=min(b,17.4954537871205) # s05 is upper visible picture owner in overlap.
 if tag=='s05':b=min(b,20.002002002002)
 n=round((b-a)*sr)
 if n<1:continue
 tt=a+np.arange(n,dtype=np.float64)/sr
 if tag=='s05':
  # Captured native Bezier keys: zero speed/33.333% influence -> smoothstep time/source curve.
  k0,k1=L['remap']['keys'][1:3];u=np.clip((tt-k0['time'])/(k1['time']-k0['time']),0,1);src=k0['value']+(k1['value']-k0['value'])*(3*u*u-2*u*u*u)
  method='Native captured zero-speed33.333%Bezier smoothstep; samples baked once, no second retime owner'
 else:src=(tt-L['start'])*100/L['stretch'];method='Exact current native startTime/stretch source map; samplewise bake, pitch/time of complete dialogue stems unchanged'
 ep='EP05' if 'Ep 05' in L['source'] else 'EP08';B=next((z for z in buckets if z['ep']==ep and z['source_in']<=src[0]+.001 and z['source_out']>=src[-1]-.001),None)
 if B is None:raise ValueError('No exact source bucket '+tag+' '+str((src[0],src[-1])))
 f=OUT/(B['tag']+'_TRANSIENT_FLOAT.wav');y,fs=sf.read(f,dtype='float32',always_2d=True);pos=(src-B['source_in'])*sr
 assert fs==sr and pos.min()>=-.5 and pos.max()<len(y)+1
 idx=np.arange(len(y));z=np.column_stack([np.interp(pos,idx,y[:,c]) for c in range(2)]).astype('float32')
 # Short source-boundary click protection; no voiced phrase is being trimmed/retimed here.
 fade=min(round(.004*sr),n//2);z[:fade]*=np.linspace(0,1,fade)[:,None];z[-fade:]*=np.linspace(1,0,fade)[:,None]
 out=OUT/(tag+'_NATIVE_ALIGNED_FLOAT.wav');sf.write(out,z,sr,subtype='FLOAT')
 events.append({'shot':tag,'picture_layer_id':L['id'],'timeline_in':a,'timeline_out':b,'timeline_frames_24000_1001':[round(a*24000/1001),round(b*24000/1001)],'episode':ep,'source_in':float(src[0]),'source_out_exclusive':float(src[-1]+(src[-1]-src[-2] if n>1 else 1/sr)),'source_bucket':B['tag'],'separation_report':str(OUT/(B['tag']+'_REPORT.json')),'output':str(out),'samples':n,'sample_rate':sr,'peak':float(np.max(np.abs(z))),'mapping':method,'quality':'Source provenance/alignment built; score leakage and timbre listening NOT TESTED.'})
(OUT/'BUCKET_REPORTS.json').write_text(json.dumps(reports,indent=2),encoding='utf-8');(OUT/'EVENTS.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
print('COMPLETE',len(events),'aligned original action events',flush=True)
