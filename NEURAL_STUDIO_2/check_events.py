# Event delivery proof: one completion event per job, acknowledged once.
import json,time
from services import Services,ROOT
s=Services(); result={}
try:
 proof=json.loads((ROOT/'SERVICE_PROOF.json').read_text()); audio=s.folder/proof['speech']['id']/'speech.wav'
 row=s.submit('relay','Explain in two sentences why a completed job should notify its owner instead of repeatedly waking an AI to check progress. Do not claim any unconnected provider is active.',recipient='Director')
 media=s.action({'action':'probe','path':str(audio)})
 while True:
  assistant=next(r for r in s.jobs() if r['id']==row['id']); measured=s.engine.job(media['id'])
  if assistant['status'] not in ('queued','running') and measured['status'] not in ('QUEUED','RUNNING'):break
  time.sleep(.15)
 result={'assistant':assistant,'media':measured,'measurements':s.action({'action':'media-result','id':media['id']})}
 events=s.inbox(); before=len([e for e in events if e['job']==row['id']]);s.complete(assistant)
 result['oneEventPerJob']=before==1 and len([e for e in s.inbox() if e['job']==row['id']])==1
 event=next(e for e in s.inbox() if e['job']==row['id'])
 result['ackFirst']=s.action({'action':'acknowledge','eventId':event['eventId']})
 result['ackSecond']=s.action({'action':'acknowledge','eventId':event['eventId']})
 result['overlap']=measured['steps'][0]['started_at'] < measured['updated_at'] and assistant['started'] <= assistant['finished']
finally:s.shutdown()
s2=Services()
try:
 result['resultSurvivesRestart']=next(r for r in s2.jobs() if r['id']==row['id'])['status']=='completed'
 result['ackSurvivesRestart']=not any(e['job']==row['id'] for e in s2.inbox())
finally:s2.shutdown()
(ROOT/'EVENT_PROOF.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('assistant','media','measurements')}))
