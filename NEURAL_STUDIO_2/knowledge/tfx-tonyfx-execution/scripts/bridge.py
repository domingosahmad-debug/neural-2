"""Single-client TonyFX dispatcher. No AE launch, retry, lock deletion or UI automation."""
import argparse,json,os,time,uuid
from pathlib import Path
from datetime import datetime,timezone

BUSY={'pending','running'}
def read_json(p):
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else None
def status(root):
    return {'command':read_json(root/'ae_command.json'),'result':read_json(root/'ae_mcp_result.json')}
def prepare(script):
    script=script.resolve(strict=True)
    if not script.is_file() or script.suffix.lower()!='.jsx':raise ValueError('Expected an existing JSX file')
    return {'id':'tfx-'+uuid.uuid4().hex,'command':'runScriptFile','args':{'scriptPath':str(script)},'timestamp':datetime.now(timezone.utc).isoformat(),'status':'pending'}
def submit(root,script,dry_run=False):
    if not root.is_dir():raise ValueError('Bridge directory does not exist; this tool never provisions a host')
    request=prepare(script);current=read_json(root/'ae_command.json')
    if current and current.get('status') in BUSY:raise RuntimeError('Bridge busy; do not overwrite or retry')
    if dry_run:return {'dry_run':True,'request':request}
    # This lock coordinates our helper only. TonyFX still owns the actual execution lock.
    lock=root/'tfx_skill_client.lock'
    fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    tmp=root/('ae_command.'+request['id']+'.tmp')
    try:
        os.write(fd,request['id'].encode());os.close(fd);fd=None
        again=read_json(root/'ae_command.json')
        if again!=current or (again and again.get('status') in BUSY):raise RuntimeError('Bridge changed during preparation; no request written')
        tmp.write_text(json.dumps(request,indent=2),encoding='utf-8')
        os.replace(tmp,root/'ae_command.json')
    finally:
        if fd is not None:os.close(fd)
        if tmp.exists():tmp.unlink()
        lock.unlink() # only the lock this invocation created
    return request
def wait(root,command_id,seconds):
    deadline=time.monotonic()+seconds
    while True:
        try:s=status(root)
        except (json.JSONDecodeError,PermissionError):s={'command':None,'result':None}
        c=s['command'] or {};r=s['result'] or {}
        if r.get('_commandId')==command_id and c.get('id')==command_id and c.get('status') not in BUSY:
            return {'completion':'matching_terminal_response','state':s,'note':'Inspect result and script-specific report; this is not visual QA'}
        if c.get('id')==command_id and c.get('status') in {'error','failed','interrupted','timeout'}:
            return {'completion':'terminal_error','state':s}
        if c.get('id') and c.get('id')!=command_id:
            return {'completion':'ownership_changed','state':s,'note':'Reconcile; do not resubmit'}
        if time.monotonic()>=deadline:return {'completion':'unknown_timeout','command_id':command_id,'note':'Native work may still be running. Do not resubmit.'}
        time.sleep(min(.25,max(0,deadline-time.monotonic())))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['status','dispatch','wait']);ap.add_argument('script',nargs='?');ap.add_argument('--bridge-dir',type=Path,required=True);ap.add_argument('--dry-run',action='store_true');ap.add_argument('--wait-seconds',type=float,default=0);ap.add_argument('--command-id');a=ap.parse_args()
    if not 0<=a.wait_seconds<=60:ap.error('Wait must be0..60 seconds; keep the session responsive')
    if a.action=='status':out=status(a.bridge_dir)
    elif a.action=='wait':
        if not a.command_id:ap.error('--command-id required')
        out=wait(a.bridge_dir,a.command_id,a.wait_seconds)
    else:
        if not a.script:ap.error('script required')
        out=submit(a.bridge_dir,Path(a.script),a.dry_run)
        # Print ID immediately, even if a later wait times out.
        print(json.dumps(out,indent=2),flush=True)
        if not a.dry_run and a.wait_seconds:out=wait(a.bridge_dir,out['id'],a.wait_seconds)
        else:return
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
