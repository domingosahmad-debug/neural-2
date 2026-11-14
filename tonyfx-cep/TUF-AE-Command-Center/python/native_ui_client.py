"""Publish one native UI command to TonyFX; never operate Windows directly.

python native_ui_client.py uiSnapshot --out observation.json
python native_ui_client.py uiKey --observation observation.json --args '{"keys":"ALT+W"}'
"""
import argparse,json,os,time,uuid
from pathlib import Path
PUBLISHED_ID = None

def main():
    global PUBLISHED_ID
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['uiCapabilities','uiSnapshot','uiActivate','uiClick','uiDoubleClick','uiStroke','uiScroll','uiKey','uiText'])
    p.add_argument('--bridge',default=str(Path.home()/'Documents/ae-mcp-bridge'));p.add_argument('--observation');p.add_argument('--args',default='{}');p.add_argument('--args-file');p.add_argument('--out');p.add_argument('--wait',type=float,default=40)
    a=p.parse_args();root=Path(a.bridge).resolve();args=json.loads(Path(a.args_file).read_text(encoding='utf-8-sig') if a.args_file else a.args)
    if not isinstance(args,dict):raise ValueError('Arguments must be a JSON object')
    if a.command not in ('uiCapabilities','uiSnapshot'):
        if not a.observation:raise ValueError('Input requires --observation from the latest uiSnapshot')
        observed=json.loads(Path(a.observation).read_text(encoding='utf-8-sig'))
        args.update(observationId=observed['observationId'],expectedContext=observed['context'])
    command=root/'ae_command.json';result=root/'ae_mcp_result.json'
    if (root/'ae_command.json.tonyfx.lock').exists():raise RuntimeError('TonyFX owns an unfinished operation. Reconcile it; no UI command was published.')
    if command.exists():
        current=json.loads(command.read_text(encoding='utf-8-sig'))
        if current.get('status','').lower() in ('pending','running','executing'):raise RuntimeError('AE bridge busy; no UI command was published.')
    ident='tfx-ui-'+uuid.uuid4().hex;payload={'id':ident,'command':a.command,'args':args,'status':'pending','timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    temp=root/(ident+'.tmp');temp.write_text(json.dumps(payload),encoding='utf-8');os.replace(temp,command);PUBLISHED_ID=ident
    until=time.monotonic()+min(120,max(1,a.wait))
    while time.monotonic()<until:
        if result.exists():
            try:r=json.loads(result.read_text(encoding='utf-8-sig'))
            except (OSError,ValueError):r={}
            if r.get('_commandId')==ident:
                if a.out:Path(a.out).write_text(json.dumps(r,indent=2),encoding='utf-8')
                print(json.dumps(r,ensure_ascii=False));return 0 if r.get('ok') else 1
        time.sleep(.2)
    print(json.dumps({'ok':False,'unknown':True,'commandId':ident,'error':'No exact terminal result before deadline. Inspect this command; NEVER replay it.'}));return 2
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error),'published':PUBLISHED_ID is not None,'commandId':PUBLISHED_ID,'unknown':PUBLISHED_ID is not None,'noAutomaticRetry':True}));raise SystemExit(2 if PUBLISHED_ID else 1)
