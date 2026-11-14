"""Read live paused-workspace proof; denied writes must not create provider jobs."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent
PID = 'e4052f1c7b5d415b86acf71a11922795'

def main():
    base = json.loads((ROOT/'.desktop-service.json').read_text())['url']
    def get(path, **headers):
        with urlopen(Request(base+path, headers=headers), timeout=15) as r:
            return r.status, r.read(), dict(r.headers)
    workspace = json.loads(get('api/workspace')[1])
    token = workspace['token']
    def post(path, body):
        req = Request(base+path, data=json.dumps(body).encode(), headers={'Content-Type':'application/json','X-Neural-Token':token})
        try:
            with urlopen(req, timeout=15) as r: return r.status, json.load(r)
        except HTTPError as e: return e.code, json.load(e)
    before = post('api/production', {'action':'status'})[1]['result']['jobs']
    status = post('api/control', {'action':'status','project':PID})[1]['result']
    assert status['paused'] and status['pauseSettled'], 'Pause has not settled'
    denied = []
    for path, body in [
        ('api/control',dict(action='continue',project=PID,station='Director',route='claude',model='opus',effort='medium',requestId='paused-http-proof')),
        ('api/production',dict(action='dispatch',project=PID,assignmentId='paused-http-proof',route='claude',model='opus',effort='medium',requestId='paused-http-proof')),
        ('api/services',dict(action='media-submit',project=PID)),
    ]:
        code, response = post(path, body)
        assert code == 400 and 'paus' in response.get('error','').lower(), response
        denied.append({'endpoint':path,'status':code,'reason':response['error']})
    after = post('api/production', {'action':'status'})[1]['result']['jobs']
    assert {j['id'] for j in before} == {j['id'] for j in after}
    review = json.loads(get('api/review?project='+PID)[1])['result']
    assert review['latest'] and review['versions']
    code, data, headers = get('api/review-media?project='+PID+'&version='+review['latest'], Range='bytes=0-31')
    assert code == 206 and len(data) == 32 and headers['Content-Range'].startswith('bytes 0-31/')
    try:
        get('api/review-media?project=wrong-project&version='+review['latest'])
        raise AssertionError('Cross-project media was served')
    except HTTPError as e: assert e.code == 404
    proof = {'project':PID,'revision':workspace['projects'][PID]['revision'],
             'paused':status['paused'],'pauseSettled':status['pauseSettled'],
             'stations':[{k:s[k] for k in ('station','state','model','jobId')} for s in status['stations']],
             'denied':denied,'providerJobCountUnchanged':len(after),
             'review':review,'rangeStatus':code,'rangeBytes':len(data),'crossProjectStatus':404,
             'autonomousNativeReady':status['autonomousNativeReady']}
    (ROOT/'data/control-http-proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps({'paused':True,'settled':True,'deniedWrites':len(denied),'renders':len(review['versions']),'range':206,'crossProject':404,'jobCountUnchanged':len(after)}))

if __name__ == '__main__': main()
