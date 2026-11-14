"""Director mechanical evidence; engine first, unsupported subtitle extraction recorded."""
import json,subprocess,shutil,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/puresnow-20261113'
pid=json.loads((OUT/'project.json').read_text())['id'];P=ROOT/'data/projects'/pid
base=json.loads((ROOT/'.desktop-service.json').read_text())['url']
with urlopen(base+'api/workspace',timeout=10) as r:w=json.load(r)
def post(route,body):
    q=Request(base+'api/'+route,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':w['token']})
    with urlopen(q,timeout=30) as r:return json.load(r)['result']
manifest=json.loads((P/'source-manifest.json').read_text());episode=manifest['files'][0]['path']
srt=P/'episode-english.srt'
if not srt.exists():
    cmd=[shutil.which('ffmpeg'),'-nostdin','-v','error','-i',episode,'-map','0:2','-c:s','srt',str(srt)]
    result=subprocess.run(cmd,capture_output=True)
    (P/'subtitle-extraction-result.json').write_text(json.dumps({'reason':'Embedded subtitle extraction absent from installed Neural mechanical operation contracts; director fallback writes only new project evidence.','argv':cmd,'exit_code':result.returncode,'stderr':result.stderr.decode(errors='replace'),'output':str(srt),'sha256':hashlib.sha256(srt.read_bytes()).hexdigest() if srt.exists() else None},indent=2),encoding='utf-8')
    result.check_returncode()
target=OUT/'audio-preparation-job.json'
if not target.exists():
    steps=[]
    for i,item in enumerate(manifest['files'][1:4]):
        steps.append({'id':('song' if i==0 else f'ref{i}'),'operation':'audio_extract','args':{'input':item['path'],'duration':149 if i==0 else 120,'sample_rate':16000}})
    # Explicit duration must not exceed a short reference, so use probed durations.
    prep=ROOT/'data/local-ops/jobs'/json.loads((OUT/'preparation-job.json').read_text())['id']
    for step in steps[1:]:step['args']['duration']=float(json.loads((prep/step['id']/'probe.json').read_text())['format']['duration'])
    job=post('services',{'action':'media-submit','project':pid,'plan':{'version':1,'title':'Pure Snow · exact song matching PCM evidence','steps':steps}})
    target.write_text(json.dumps(job,indent=2),encoding='utf-8')
    (P/'director-audio-job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
else:job=json.loads(target.read_text())
print(json.dumps({'subtitle':str(srt),'subtitle_bytes':srt.stat().st_size,'audio_job':job['id']},indent=2))
