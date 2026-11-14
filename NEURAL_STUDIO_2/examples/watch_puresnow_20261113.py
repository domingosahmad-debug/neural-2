"""Read-only SSE completion watch; saves full status, no dispatch/replay."""
import json,time,socket
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/puresnow-20261113'
pid=json.loads((OUT/'project.json').read_text())['id']
base=json.loads((ROOT/'.desktop-service.json').read_text())['url']
with urlopen(base+'api/workspace',timeout=10) as r:w=json.load(r)
def post(route,body):
    q=Request(base+'api/'+route,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':w['token']})
    with urlopen(q,timeout=20) as r:return json.load(r)['result']
def snapshot():
    state=post('control',{'action':'status','project':pid});run=state.get('production') or {}
    (OUT/'control-latest.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    jobs=[{'id':j['id'],'status':j['status'],'model':j['model'],'error':j.get('error')} for s in state.get('stations',[]) for j in s.get('jobs',[])]
    compact={'run':{k:run.get(k) for k in ('id','state','phase','error','jobId','question')},'jobs':jobs}
    return compact
before=snapshot();print(json.dumps(before),flush=True)
deadline=time.monotonic()+55
try:
    with urlopen(base+'api/events',timeout=60) as stream:
        for line in stream:
            if line.startswith(b'data:'):
                after=snapshot()
                if after!=before:print(json.dumps(after),flush=True);break
            if time.monotonic()>=deadline:break
except (TimeoutError,socket.timeout):pass
print('Completion watch returned; no work dispatched.',flush=True)
