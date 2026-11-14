"""Real HTTP/SQLite/event flow with a controlled text transport; never runs AI or AE."""
import json
from pathlib import Path
import shutil
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4
from unittest.mock import patch
import studio, services, editor, providers

ROOT=Path(__file__).resolve().parent
fixture=ROOT/'data/commissioning-fixtures'/uuid4().hex
fixture.mkdir(parents=True)
shutil.copyfile(ROOT/'model_catalog.json',fixture/'model_catalog.json')
studio.ROOT=services.ROOT=editor.ROOT=fixture
proof={}; server_box=[]; owners=[]
started=threading.Event(); allow=threading.Event()
class TextTransport:
    def __init__(self): self.calls=[]
    def run(self,row,packet,folder,session,cancel):
        self.calls.append({'packet':packet,'session':session});started.set()
        if row['station']=='Plan':
            while not allow.wait(.05):
                if cancel.is_set():return {'status':'CANCELLED','text':'','session_id':session}
        return {'status':'COMPLETED','text':'Controlled fixture evidence.','session_id':session or 'fixture-session-'+row['station']}
transport=TextTransport()
real_jobs=providers.ProviderJobs
def jobs(*args,**kwargs):
    result=real_jobs(*args,transport=transport,**kwargs);owners.append(result);return result
real_server=studio.ThreadingHTTPServer
def create_server(*args,**kwargs):
    server=real_server(*args,**kwargs);server_box.append(server);return server
def wait_for(test):
    deadline=time.monotonic()+5
    while not test():
        if time.monotonic()>deadline:raise AssertionError('Fixture event did not arrive')
        threading.Event().wait(.02)
def request(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=Request(base+path,data=data,headers={'Content-Type':'application/json','X-Neural-Token':token} if data else {})
    with urlopen(req,timeout=5) as response:return json.load(response)
def workspace(action,**kwargs):return request('workspace',dict(action=action,project=pid,**kwargs))['result']
def rejected(fn):
    try:fn();return False
    except HTTPError as error:
        error.read();return error.code==400

with patch('providers.ProviderJobs',jobs),patch.object(studio,'ThreadingHTTPServer',create_server):
    thread=threading.Thread(target=studio.serve,args=(fixture/'workspace.sqlite3',0),daemon=True);thread.start()
    wait_for(lambda:server_box)
    base=f'http://127.0.0.1:{server_box[0].server_port}/api/'
    token=request('workspace')['token']
    p=request('workspace',{'action':'project','name':'Production contract fixture','brief':'Synthetic contract checks. No media or native editing.'})['result'];pid=p['id']
    workspace('executive-enable',enabled=True)
    def executive():
        packet=workspace('assign',station='Executive Director',revision=1,model='claude-fable-5-2',task='Synthetic allocation fixture, no provider call.')
        plan=[{'station':'Plan','model':'gpt-6.1-terra','task':'Produce fixture evidence.','acceptance':'Marker saved.','dependsOn':[],'availabilityEvidence':'Controlled transport only.'},{'station':'Review','model':'gpt-6.1-terra','task':'Review actual predecessor.','acceptance':'Marker received.','dependsOn':['Plan'],'availabilityEvidence':'Controlled transport only.'}]
        workspace('result',**{k:v for k,v in dict(packet['resultTemplate'],summary='Fixture plan.',allocationPlan=plan).items() if k!='project'})
        workspace('approve',assignmentId=packet['assignmentId'])
        return packet
    first=executive();packets=workspace('executive-apply',assignmentId=first['assignmentId'])['packets'];a,b=packets
    second=executive()
    def dispatch(row,rid):return request('production',{'action':'dispatch','project':pid,'assignmentId':row['assignmentId'],'route':'codex','model':row['model'],'effort':'medium','requestId':rid})['result']
    proof['dependencyRejectedBeforeInference']=rejected(lambda:dispatch(b,'too-early')) and not transport.calls
    job=dispatch(a,'one-plan-attempt');assert started.wait(5)
    before=request('workspace')['projects'][pid]
    proof['executiveApplyCannotInvalidateActiveWorker']=rejected(lambda:workspace('executive-apply',assignmentId=second['assignmentId'])) and request('workspace')['projects'][pid]==before
    proof['briefCannotInvalidateActiveWorker']=rejected(lambda:workspace('brief',revision=1,brief='Invalid late revision'))
    proof['independentStationCanBePreparedDuringWork']=bool(workspace('assign',station='Edit',revision=1,model='haiku',task='Independent text inventory; never edit AE.')['assignmentId'])
    proof['activeStationCannotBeReplaced']=rejected(lambda:workspace('assign',station='Plan',revision=1,model='haiku',task='Invalid replacement'))
    proof['duplicateRequestIsSameJob']=dispatch(a,'one-plan-attempt')['id']==job['id'] and len(transport.calls)==1
    allow.set();wait_for(lambda:owners[0].status()[0]['status']=='COMPLETED')
    result=dict(a['resultTemplate'],summary='UNIQUE_PREDECESSOR_MARKER_R1')
    workspace('result',**{k:v for k,v in result.items() if k!='project'});workspace('approve',assignmentId=a['assignmentId'])
    dispatch(b,'one-review-attempt');wait_for(lambda:len(transport.calls)==2)
    frozen=transport.calls[-1]['packet']
    proof['dependentPacketContainsApprovedIdentityAndEvidence']=frozen['predecessorEvidence'][0]['assignmentId']==a['assignmentId'] and frozen['approvedEvidence']['Plan']=='UNIQUE_PREDECESSOR_MARKER_R1'
    wait_for(lambda:all(j['status']=='COMPLETED' for j in owners[0].status()))
    wait_for(lambda:len(request('services',{'action':'status'})['result']['events'])>=3)
    events=request('services',{'action':'status'})['result']['events']
    proof['terminalJobsReachDirectorInbox']=all(any(e['job']==j['id'] and e['recipient']=='Director' for e in events) for j in owners[0].status())
    event_id=next(e['eventId'] for e in events if e['job']==job['id'])
    proof['acknowledgementPersists']=request('services',{'action':'acknowledge','eventId':event_id})['result']['acknowledged']
    server_box[0].shutdown();thread.join(5)
    server_box.clear();thread=threading.Thread(target=studio.serve,args=(fixture/'workspace.sqlite3',0),daemon=True);thread.start();wait_for(lambda:server_box)
    base=f'http://127.0.0.1:{server_box[0].server_port}/api/';token=request('workspace')['token']
    proof['restartDoesNotRunModels']=len(transport.calls)==2 and len(owners[-1].status())==2
    events=request('services',{'action':'status'})['result']['events']
    proof['restartKeepsAcknowledgement']=not any(e['job']==job['id'] for e in events)
    proof['restartReconcilesWithoutDuplicateNotifications']=len({e['job'] for e in events})==len(events)
    server_box[0].shutdown();thread.join(5)
proof['fixtureRoot']=str(fixture)
(ROOT/'PRODUCTION_CONTRACT_PROOF.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
assert all(v for k,v in proof.items() if k!='fixtureRoot')
