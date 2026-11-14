"""Small deterministic export/identity/persistence proof. Never uses AE or production media."""
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from editor import Editor

ROOT = Path(__file__).resolve().parent
folder=Path(tempfile.mkdtemp(prefix='neural-editor-proof-'))
done=threading.Event(); events=[]
def complete(row):
    events.append(dict(row));done.set()
services=SimpleNamespace(resource_gate=threading.Lock(),engine=SimpleNamespace(base=folder/'media'),signal=lambda:None,complete=complete)
editor=Editor(services,folder)
proof={'fixtureRoot':str(folder)}
def ff(args):
    p=subprocess.run([editor.ffmpeg,'-v','error','-nostdin','-y',*args],capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr)
for name,color,tone in [('red','red',440),('blue','blue',660)]:
    size='180x320' if name=='blue' else '320x180'
    ff(['-f','lavfi','-i',f'color=c={color}:s={size}:r=25:d=2','-f','lavfi','-i',f'sine=frequency={tone}:duration=2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(folder/(name+'.mp4'))])
ff(['-f','lavfi','-i','sine=frequency=220:duration=3','-c:a','pcm_s16le',str(folder/'music.wav')])
d=editor.import_media('proof',[str(folder/'red.mp4'),str(folder/'blue.mp4'),str(folder/'music.wav')],0)
d.update(width=320,height=180,fps=30,clips=[{'id':'red','mediaId':d['media'][0]['id'],'in':.2,'out':1.2,'gain':.5},{'id':'blue','mediaId':d['media'][1]['id'],'in':.4,'out':1.4,'gain':.5}],music={'mediaId':d['media'][2]['id'],'in':.1,'start':.2,'gain':.25},captions=[{'id':'caption','start':.3,'end':.8,'text':'Neural proof'}])
d=editor.action({'action':'save','project':'proof','revision':1,'document':d})['document']
proof['persisted']=editor.document('proof')==d
try:editor.store(d,1);proof['staleRejected']=False
except ValueError:proof['staleRejected']=True
bad=json.loads(json.dumps(d));bad['clips'][0]['out']=.1
try:editor.validate(bad,d);proof['invalidTrimRejected']=False
except ValueError:proof['invalidTrimRejected']=True
job=editor.action({'action':'export','project':'proof','revision':d['revision']})['job']
if not done.wait(80):raise RuntimeError('Fixture export did not terminate')
proof['job']=events[-1]
if events[-1]['status']!='completed':
    (ROOT/'EDITOR_PROOF.json').write_text(json.dumps(proof,indent=2));raise RuntimeError(str(events[-1]))
out=editor.output_path(job['id'])
proof['frames']=events[-1]['frames']
pixels=[]
for t in (.1,.5,1.5):
    p=subprocess.run([editor.ffmpeg,'-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode())
    raw=p.stdout
    pixels.append({'time':t,'centerline':list(raw[(10*320+160)*3:(10*320+160)*3+3]),'corner':list(raw[(10*320+10)*3:(10*320+10)*3+3]),'captionBrightPixels':sum(all(v>170 for v in raw[i:i+3]) for y in range(140,160) for x in range(50,270) for i in [(y*320+x)*3])})
proof['pixels']=pixels
proof['cutCorrect']=pixels[0]['centerline'][0]>200 and pixels[2]['centerline'][2]>200
proof['mixedAspectPadded']=max(pixels[2]['corner'])<5
proof['captionVisibleOnlyDuringRange']=pixels[1]['captionBrightPixels']>30 and pixels[0]['captionBrightPixels']==0 and pixels[2]['captionBrightPixels']==0
m=d['media'][0];p=Path(m['path']);original=p.read_bytes();stat=p.stat();p.write_bytes(bytes([original[0]^1])+original[1:]);import os;os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
try:editor.verify_source(m);proof['sameSizeTimestampMutationRejected']=False
except ValueError:proof['sameSizeTimestampMutationRejected']=True
p.write_bytes(original);os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
editor.shutdown()
import array, math
pcm=subprocess.run([editor.ffmpeg,'-v','error','-ss','0.45','-i',str(out),'-t','0.2','-f','s16le','-ac','1','-ar','48000','-'],capture_output=True).stdout
samples=array.array('h',pcm)
def amplitude(hz):return abs(sum(x*complex(math.cos(2*math.pi*hz*i/48000),math.sin(2*math.pi*hz*i/48000)) for i,x in enumerate(samples)))/len(samples)
proof['audioComponents']={str(h):amplitude(h) for h in (220,440,900)}
proof['audioMixPresent']=amplitude(220)>100 and amplitude(440)>100 and amplitude(900)<50
(ROOT/'EDITOR_PROOF.json').write_text(json.dumps(proof,indent=2))
assert all(proof[k] for k in ('persisted','staleRejected','invalidTrimRejected','cutCorrect','captionVisibleOnlyDuringRange','sameSizeTimestampMutationRejected','mixedAspectPadded','audioMixPresent'))
assert proof['frames']==60
print(json.dumps({'result':'PASS','proof':str(ROOT/'EDITOR_PROOF.json'),'output':str(out),'frames':proof['frames']}))

