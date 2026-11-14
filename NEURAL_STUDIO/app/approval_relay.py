"""Temporary no-inference bridge for an already-running, pre-policy backend.

Uses the existing loopback approval API. Never restarts an active Leader/worker,
never sends prompts, and exits when the upgraded backend takes over.
"""
import json, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8767'
POLICY=ROOT/'data/command/EXECUTION_POLICY.json'
STATUS=ROOT/'.runtime/approval-relay.json'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def api(path,data=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['X-Studio-Token']=token
    request=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
    with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
def record(**values):
    values.update(pid=os.getpid(),time=time.time())
    temp=STATUS.with_suffix('.tmp');temp.write_text(json.dumps(values,indent=2),encoding='utf-8');os.replace(temp,STATUS)

def run():
    accepted=0;quiet_since=None;errors=0
    token=api('/api/config')['token'];backend_pid=read(ROOT/'.runtime/server.json')['pid']
    record(status='running',accepted=accepted,backend_pid=backend_pid)
    while True:
        try:
            if read(POLICY).get('local_execution')!='unattended':record(status='disabled',accepted=accepted);return
            state=api('/api/command/state')
            if state.get('execution_policy',{}).get('local_execution')=='unattended':record(status='replaced_by_native_policy',accepted=accepted);return
            if read(ROOT/'.runtime/server.json')['pid']!=backend_pid:record(status='backend_changed',accepted=accepted);return
            for approval in state.get('approvals',[]):
                if approval.get('title') not in ('Allow local command?','Allow file changes?'):continue
                try:api('/api/command/approval',{'id':approval['id'],'decision':'accept'},token)
                except urllib.error.HTTPError as failure:
                    if failure.code!=400:raise
                    continue # Already answered; never replay a tool or message.
                accepted+=1;record(status='running',accepted=accepted,backend_pid=backend_pid,last_request=approval['id'])
            # Upgrade only after the permanent implementation has passed its tests,
            # and the real session and all real workers are quiet for five seconds.
            ready=ROOT/'.runtime/approval-upgrade-ready.json'
            busy=state['leader']['status'] in ('starting','working','awaiting_approval','cancelling','uncertain')
            pending_wake=any(w.get('status') in ('waiting','ready') for w in state.get('watches',{}).values())
            if not busy and not pending_wake and ready.is_file():
                operations=api('/api/state');busy=any(j['status'] in ('QUEUED','RUNNING','CANCELLING') for j in operations.get('jobs',[]))
                quiet_since=(quiet_since or time.monotonic()) if not busy else None
                if quiet_since and time.monotonic()-quiet_since>=5:
                    api('/api/shutdown',{},token)
                    # A new server must not bind until the old one exits cleanly.
                    for _ in range(120):
                        try:api('/api/health')
                        except (OSError,ValueError):break
                        time.sleep(.25)
                    else:record(status='upgrade_wait_failed',accepted=accepted);return
                    with (ROOT/'.runtime/desktop-server.log').open('a',encoding='utf-8') as log:
                        child=subprocess.Popen([sys.executable,'-u',str(ROOT/'app/server.py'),'--port','8767'],cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    for _ in range(120):
                        try:
                            updated=api('/api/command/state')
                            if updated.get('execution_policy',{}).get('local_execution')=='unattended':record(status='upgraded',accepted=accepted,backend_pid=child.pid);return
                        except (OSError,ValueError):pass
                        time.sleep(.5)
                    record(status='upgrade_start_failed',accepted=accepted,backend_pid=child.pid);return
            else:quiet_since=None
            errors=0;time.sleep(.35)
        except (OSError,ValueError,KeyError) as failure:
            errors+=1;record(status='retrying_local_connection',accepted=accepted,error=type(failure).__name__)
            if errors>=20:return
            time.sleep(1)

if __name__=='__main__':run()
