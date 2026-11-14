"""Record Tony's explicit pause while the desktop companion is stopped."""
import json, socket, sqlite3
from pathlib import Path
from datetime import datetime, timezone

root=Path(__file__).resolve().parent
service=json.loads((root/'.desktop-service.json').read_text())
from urllib.parse import urlparse
url=urlparse(service['url'])
with socket.socket() as sock:
    sock.settimeout(.3)
    if sock.connect_ex((url.hostname,url.port))==0:
        raise SystemExit('Service is running; use its pause API instead of offline mutation.')
now=datetime.now(timezone.utc).isoformat()
pid='e4052f1c7b5d415b86acf71a11922795'
folder=root/'data/production-pauses'/now.replace(':','-')
folder.mkdir(parents=True,exist_ok=False)
with sqlite3.connect(root/'workspace.sqlite3') as db:
    backup=sqlite3.connect(folder/'workspace.sqlite3');db.backup(backup);backup.close()
    db.execute('BEGIN IMMEDIATE')
    projects=json.loads(db.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
    project=projects[pid]
    control=project.setdefault('productionControl',{})
    reason='Tony explicitly paused this edit. Preserve Claude progress. Fix Neural first; next production is a DIFFERENT edit. Do not resume CA02 automatically.'
    control.update(paused=True,pauseReason=reason,pausedAt=now,automatic=False)
    project['messages'].append({'role':'operator','revision':project['revision'],'text':reason})
    project['activity'].append({'time':now,'text':reason})
    db.execute('UPDATE workspace SET body=? WHERE id=1',(json.dumps(projects),))
command=json.loads((Path.home()/'Documents/ae-mcp-bridge/ae_command.json').read_text())
result=json.loads((Path.home()/'Documents/ae-mcp-bridge/ae_mcp_result.json').read_text())
proof={'project':pid,'paused':True,'time':now,'desktopServiceStopped':True,'nativeCommand':command['id'],'nativeStatus':command['status'],'matchingTerminal':command['status']=='completed' and result.get('_commandId')==command['id'],'newNativeCommandsSent':0,'backup':str(folder),'claudeArtifactsPreserved':True}
(folder/'PAUSE.json').write_text(json.dumps(proof,indent=2))
(root/'data/PRODUCTION_PAUSED.json').write_text(json.dumps(proof,indent=2))
print(json.dumps(proof))
