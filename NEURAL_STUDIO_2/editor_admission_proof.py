"""Exercise actual gate/recovery paths with simulated work, without loading a model."""
import json
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from editor import Editor
from services import Services
from operations import save

root=Path(tempfile.mkdtemp(prefix='neural-editor-admission-'))
terminal=threading.Event();rows=[]
def complete(row):rows.append(dict(row));terminal.set()
s=SimpleNamespace(resource_gate=threading.Lock(),engine=SimpleNamespace(base=root/'media'),signal=lambda:None,complete=complete,closed=False)
editor=Editor(s,root);source=Path(__file__).parent/'EDITOR_PROOF.json';fixture=json.loads(source.read_text());original=Editor(s,Path(fixture['fixtureRoot'])).document('proof');original['id']='gate';original['revision']=0;editor.store(original,0)
assistantEntered=threading.Event();assistantRelease=threading.Event();renderEntered=threading.Event();renderRelease=threading.Event()
def assistant(row):assistantEntered.set();assert assistantRelease.wait(5)
terminal.clear();rows.clear()
s.run_admitted=assistant
def fakeCommand(*args):renderEntered.set();assert renderRelease.wait(5);raise ValueError('Simulated export stops after admission; no FFmpeg work requested.')
editor.command=fakeCommand
proof={'workload':'simulated assistant and render steps; actual Services.run and Editor.render admission'}
worker=threading.Thread(target=Services.run,args=(s,{}));worker.start();assert assistantEntered.wait(2)
editor.action({'action':'export','project':'gate','revision':1});proof['assistantFirstExcludesRender']=not renderEntered.wait(.1)
assistantRelease.set();assert renderEntered.wait(2);renderRelease.set();assert terminal.wait(3);worker.join()
terminal.clear();assistantEntered.clear();assistantRelease.clear();renderEntered.clear();renderRelease.clear()
editor.action({'action':'export','project':'gate','revision':1});assert renderEntered.wait(2)
worker=threading.Thread(target=Services.run,args=(s,{}));worker.start();proof['renderFirstExcludesAssistant']=not assistantEntered.wait(.1)
renderRelease.set();assert terminal.wait(3);assert assistantEntered.wait(2);assistantRelease.set();worker.join()
editor.shutdown()
pending=editor.root/'exports'/('a'*32);pending.mkdir();save(pending/'job.json',{'id':'a'*32,'status':'running','title':'Interrupted fixture','created':time.time(),'project':'gate'})
rows.clear();reopened=Editor(s,root);interrupted=next(r for r in rows if r['id']=='a'*32);proof['restartNoReplay']=interrupted['status']=='interrupted';reopened.shutdown()
(Path(__file__).parent/'EDITOR_ADMISSION_PROOF.json').write_text(json.dumps(proof,indent=2))
assert all(v for k,v in proof.items() if k!='workload')
print(json.dumps(proof))
