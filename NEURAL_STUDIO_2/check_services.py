import json,time,wave
from services import Services,ROOT
s=Services()
results={}
try:
 for kind,text in [('relay','Tony needs a concise checklist to review repeated footage and an abrupt music jump. Give three practical checks. No tasks have run yet.'),('speech','Open the screening room and trim the second clip by ten frames.')]:
  row=s.submit(kind,text)
  while True:
   row=next(r for r in s.jobs() if r['id']==row['id'])
   if row['status'] not in ('running','queued'):break
   time.sleep(.25)
  results[kind]=row
  print(kind,row['status'],flush=True)
 if results['speech']['status']=='completed':
  audio=s.folder/results['speech']['id']/'speech.wav'
  with wave.open(str(audio)) as w:results['wav']={'frames':w.getnframes(),'rate':w.getframerate(),'channels':w.getnchannels()}
  results['media']=s.engine.submit({'version':1,'title':'Inspect commissioned Kokoro speech','steps':[{'id':'probe','operation':'probe','args':{'input':str(audio)}}]},background=False)
 (ROOT/'SERVICE_PROOF.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps({k:v.get('status',v) for k,v in results.items()}))
finally:s.shutdown()
