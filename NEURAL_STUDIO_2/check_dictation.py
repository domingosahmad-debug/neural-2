import base64,json,time,os,threading
os.environ['NEURAL_DICTATION_DEVICE']='cpu'
from services import Services,ROOT
s=Services()
try:
 proof=json.loads((ROOT/'SERVICE_PROOF.json').read_text())
 audio=s.folder/proof['speech']['id']/'speech.wav'
 caps=s.dictation.capabilities()
 engine=next(e['id'] for e in caps['engines'] if e['available'] and e['id']=='whisper-small-en')
 state=s.dictation.start(engine_id=engine,capture='browser-audio')
 if state['status']=='error':raise ValueError(state['error'])
 done=threading.Event()
 def heartbeat():
  while not done.wait(1): s.dictation.poll(0,state['session'])
 threading.Thread(target=heartbeat,daemon=True).start()
 result=s.dictation.audio({'session':state['session'],'sequence':1,'audio':base64.b64encode(audio.read_bytes()).decode()})
 final=s.dictation.poll(0,state['session'])
 s.dictation.stop(state['session'])
 report={'engine':engine,'transcription':result,'final':final,'stopped':s.dictation.snapshot()['status'],'microphone_accuracy':'NOT TESTED; input was Kokoro synthetic speech'}
 (ROOT/'DICTATION_PROOF.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report))
finally:
 if 'done' in locals():done.set()
 print(json.dumps(s.dictation.snapshot()))
 s.shutdown()
