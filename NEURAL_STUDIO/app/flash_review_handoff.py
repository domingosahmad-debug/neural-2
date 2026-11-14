"""One user-authorized completion handoff; local waits never call a model."""
import json, os, sys, time, urllib.request, urllib.error
from pathlib import Path
from operations import load,save
ROOT=Path(__file__).resolve().parents[1];STATUS=ROOT/'.runtime/flash-review-handoff.json';BASE='http://127.0.0.1:8767'
def api(path,data=None,token=None):
    request=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'X-Studio-Token':token} if token else {})})
    with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
def record(status,**values):save(STATUS,{'status':status,'pid':os.getpid(),'time':time.time(),**values})
def run():
    if STATUS.is_file() and load(STATUS).get('status') in ['sent','sending','uncertain']:return
    delegation=load(ROOT/'.runtime/flash-review-delegation.json');record('waiting',job_id=delegation['job_id'])
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        try:
            job=api('/api/job/'+delegation['job_id'])
            if job['status'] in ['FAILED','CANCELLED','UNKNOWN','TIMED_OUT']:record('worker_blocked',job_id=job['id'],error=job.get('error'));return
            if job['status'] in ['REVIEW_REQUIRED','APPROVED','COMPLETED']:
                leader=load(ROOT/'data/command/STATE.json')['leader']
                if leader['status']=='error':record('leader_unavailable',job_id=job['id']);return
                if leader['status']=='idle':
                    message=('Relay of the human\'s explicit delegation-first instruction from the supervising chat: use available Flash/local workers for routine preparation and checks; Codex supervises and handles difficult native integration. Read shared/LEADER_CONTEXT.md delegation policy. Flash has completed one independent R02 evidence audit in Neural: station review-delivery, task '+delegation['task_id']+', job '+delegation['job_id']+'. Its artifact is '+str(Path(delegation['folder'])/'outputs/review_delivery_report.json')+'. Validate the returned evidence and inspect this compact artifact. Do not redo its whole analysis, probes or media processing. Correct only specific blocking findings within the already-authorized edit, preserve artistic/listening/motion limitations, and report who did what briefly. Do not dispatch another audit or rerender solely to acknowledge this result. End your turn when supervision is complete. The relay starts no further follow-up.')
                    token=api('/api/config')['token'];record('sending',job_id=job['id'])
                    try:api('/api/command/send',{'message':message},token)
                    except urllib.error.HTTPError as failure:
                        if failure.code==400:
                            error=json.loads(failure.read()).get('error','')
                            if 'already working' in error:record('waiting',job_id=job['id']);time.sleep(2);continue
                        record('not_sent',job_id=job['id'],error=str(failure));return
                    except (OSError,ValueError) as failure:record('uncertain',job_id=job['id'],error=str(failure));return
                    record('sent',job_id=job['id']);return
        except (OSError,ValueError,KeyError) as failure:record('waiting_for_local_state',job_id=delegation['job_id'],error=type(failure).__name__)
        time.sleep(2)
    record('expired',job_id=delegation['job_id'])
if __name__=='__main__':run()
