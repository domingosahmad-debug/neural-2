"""Installation bootstrap only: restore the AE window under a live TonyFX JSX owner.

No clicks, keystrokes, strokes, project changes or desktop service. Used when
upgrading a minimized older TonyFX panel that does not yet expose uiActivate.
"""
import json,sys,time
from pathlib import Path
from datetime import datetime,timezone
from native_ui import Windows

def main():
    root=Path(sys.argv[1]).resolve();script=Path(sys.argv[2]).resolve()
    live=json.loads((root/'ae_command.json').read_text(encoding='utf-8-sig'))
    lock=json.loads((root/'ae_command.json.tonyfx.lock').read_text(encoding='utf-8-sig'))
    if live.get('command')!='runScriptFile' or live.get('status')!='running' or Path(live.get('args',{}).get('scriptPath','')).resolve()!=script or live.get('id')!=lock.get('commandId') or live.get('owner')!=lock.get('owner'):
        raise ValueError('Installation restore requires the exact live TonyFX script owner')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(lock['heartbeat'].replace('Z','+00:00'))).total_seconds()
    if not 0<=age<=15:raise ValueError('Installation owner heartbeat expired')
    backend=Windows();before=backend.select({});backend.activate(before)
    return {'ok':True,'commandId':live['id'],'window':backend.info(before['hwnd']),'operation':'restore-existing-AE-window-only'}

if __name__=='__main__':
    try:print(json.dumps(main()))
    except Exception as e:print(json.dumps({'ok':False,'error':str(e),'noAutomaticRetry':True}));sys.exit(1)
