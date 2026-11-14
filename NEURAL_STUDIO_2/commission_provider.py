"""One explicit commissioning assignment; event wait never dispatches a repeat."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen

root=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--route',required=True);ap.add_argument('--model',required=True);ap.add_argument('--effort',default='medium');ap.add_argument('--station',default='Plan');ap.add_argument('--task-file',type=Path,required=True);ap.add_argument('--request-id',required=True)
args=ap.parse_args()
base=json.loads((root/'.desktop-service.json').read_text())['url']
with urlopen(base+'api/workspace',timeout=10) as response:workspace=json.load(response)
pid=json.loads((root/'data/commissioning-project.json').read_text())['id']
def post(route,body):
    req=Request(base+'api/'+route,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(req,timeout=15) as response:return json.load(response)['result']
job=next((j for j in post('production',{'action':'status'})['jobs'] if j['request_id']==args.request_id),None)
if job is None:
    packet=post('workspace',{'action':'assign','project':pid,'revision':workspace['projects'][pid]['revision'],'station':args.station,'model':args.model,'task':args.task_file.read_text(encoding='utf-8')})
    job=post('production',{'action':'dispatch','project':pid,'assignmentId':packet['assignmentId'],'route':args.route,'model':args.model,'effort':args.effort,'requestId':args.request_id})
proof=root/'data'/('commission-'+args.request_id+'.json')
proof.write_text(json.dumps(job,indent=2),encoding='utf-8');print(json.dumps({k:job.get(k) for k in ['id','status','model','effort']}),flush=True)
def terminal(row):return row['status'] not in ('QUEUED','RUNNING')
if not terminal(job):
    deadline=time.monotonic()+180
    with urlopen(base+'api/events',timeout=35) as stream:
        for line in stream:
            if line.startswith(b'data:'):
                job=next(j for j in post('production',{'action':'status'})['jobs'] if j['id']==job['id'])
                if terminal(job):break
            if time.monotonic()>deadline:break
proof.write_text(json.dumps(job,indent=2),encoding='utf-8')
print(json.dumps({k:job.get(k) for k in ['id','status','error','session_id','raw_evidence']}),flush=True)
print('Saved evidence: '+str(proof))
