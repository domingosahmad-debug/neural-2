from pathlib import Path
import json,shutil,subprocess,hashlib
P=Path(__file__).resolve().parent;ROOT=P.parents[1];J=ROOT/'data/local-ops/jobs/250605129d81495d8cb21382864085ae';D=P/'delivery'
audio=D/'WOG_W10H_NATIVE_32BIT_MIX.aif';native=J/'native/native.mov';encoded=J/'encode/review.mp4'
probe=json.loads((ROOT/'data/local-ops/jobs/87c76ddbf77d4f32bf594506b5f72b1d/native32-probe/probe.json').read_text())
assert probe['streams'][0]['codec_name']=='pcm_f32be'
align=json.loads((ROOT/'data/local-ops/jobs/87c76ddbf77d4f32bf594506b5f72b1d/native32-align/report.json').read_text());assert align['lag_samples']==0 and align['correlation']>.999
outputs=[(native,D/'WOG_W10H_MASTER_PRORES_FLOAT.mov','pcm_f32le'),(encoded,D/'WOG_W10H_REVIEW.mp4','aac')]
assert not any(out.exists() for _,out,_ in outputs),'Delivery exists; inspect instead of replay'
ff=shutil.which('ffmpeg');report={'method':'Native float AIFF muxed with existing verified picture, copy video packets; no16bit upcast or picture re-render. Engine has no alternate-audio remux operation. Full decode/format/audio validation uses shared engine next.','outputs':[]}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
for src,out,codec in outputs:
 cmd=[ff,'-hide_banner','-nostats','-n','-i',str(src),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-map_metadata','0','-c:v','copy','-c:a',codec]
 if codec=='aac':cmd+=['-b:a','320k','-movflags','+faststart']
 cmd+=[str(out)];r=subprocess.run(cmd,capture_output=True,text=True);(D/(out.stem+'_MUX_LOG.txt')).write_text(r.stderr,encoding='utf-8');assert r.returncode==0,r.stderr[-1000:]
 def video_hash(p):
  r=subprocess.run([ff,'-v','error','-i',str(p),'-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-'],capture_output=True,text=True);assert r.returncode==0;return r.stdout.strip()
 vh=video_hash(src);assert video_hash(out)==vh
 report['outputs'].append({'path':str(out),'bytes':out.stat().st_size,'sha256':sha(out),'video_source':str(src),'video_packets_sha256':vh,'audio_source':str(audio),'audio_source_sha256':sha(audio),'audio_codec_requested':codec})
(D/'WOG_W10H_DELIVERY_PROVENANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
