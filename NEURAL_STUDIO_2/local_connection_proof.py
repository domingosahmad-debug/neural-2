"""Actual CPU measurement and safe adapter admission, no inference or AE."""
import json
import math
from pathlib import Path
import struct
import threading
from uuid import uuid4
import wave
import services

root=Path(__file__).resolve().parent
fixture=root/'data/commissioning-fixtures'/uuid4().hex
fixture.mkdir(parents=True)
services.ROOT=fixture
owner=services.Services()
proof={}
try:
    caps=owner.action({'action':'media-capabilities'})
    proof['nineteenMechanicalOperations']=len(caps['capabilities'])==19
    proof['noNativeOrAssemblyEndpoint']=not any(k.startswith('native') or k in ('compile_ae','rough_assembly','register_preview') for k in caps['capabilities'])
    try:
        owner.action({'action':'media-submit','plan':{'version':1,'title':'Forbidden','steps':[{'id':'native','operation':'native_snapshot','args':{}}]}})
        proof['nativeRejectedBeforeSubmission']=False
    except ValueError:proof['nativeRejectedBeforeSubmission']=not owner.engine.snapshot()['jobs']
    source=fixture/'tone.wav'
    with wave.open(str(source),'wb') as f:
        f.setparams((1,2,16000,0,'NONE','not compressed'))
        f.writeframes(b''.join(struct.pack('<h',int(8000*math.sin(2*math.pi*440*i/16000))) for i in range(16000)))
    done=threading.Event();original=owner.engine.on_terminal
    def terminal(row):original(row);done.set()
    owner.engine.on_terminal=terminal
    job=owner.action({'action':'media-submit','project':'commissioning-local','plan':{'version':1,'title':'Measure synthetic one-second tone','steps':[{'id':'measure','operation':'audio_measure','args':{'input':str(source)}}]}})
    assert done.wait(30),'Local completion event missing'
    job=owner.action({'action':'media-job','id':job['id']})
    proof['actualAudioMeasurementCompleted']=job['status']=='COMPLETED'
    artifact=owner.action({'action':'media-artifact','id':job['id'],'step':'measure','filename':'waveform.json'})
    proof['registeredMeasuredArtifactReturned']=artifact['inline'] and bool(artifact['data']['peaks'])
    proof['notificationKeepsProjectAndRecipient']=any(e['job']==job['id'] and e['project']=='commissioning-local' and e['recipient']=='Director' for e in owner.inbox())
    try:
        owner.action({'action':'media-artifact','id':job['id'],'step':'measure','filename':'../../tone.wav'})
        proof['unregisteredArtifactRejected']=False
    except ValueError:proof['unregisteredArtifactRejected']=True
finally:owner.shutdown()
proof['fixtureRoot']=str(fixture)
(root/'LOCAL_CONNECTION_PROOF.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
assert all(v for k,v in proof.items() if k!='fixtureRoot')
