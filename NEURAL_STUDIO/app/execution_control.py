"""Deterministic human pause handling and native-host crash circuit breaker."""
import re
from pathlib import Path

STOP = re.compile(
    r'^(?:please\s+)?(?:stop|pause|cancel|halt)'
    r'(?:\s+(?:all\s+(?:work|jobs|tasks|renders|rendering)|everything|work|working|execution|editing|rendering|the\s+(?:task|edit|work)))?'
    r'(?:\s+(?:for now|right now|now|immediately))?(?:\s+until\s+.+)?[.!\s]*$', re.I)


def stop_direction(text):
    return bool(STOP.fullmatch(str(text).strip()))


def native_crash_hold(service, ready):
    """At most one diagnostic continuation after an interrupted AE host.

    Only native crash/interruption evidence is counted. Ordinary JSX errors are
    not crashes. Aliases for one local/native command count as the same incident.
    """
    from operations import load, stamp
    history=service.saved.setdefault('native_host_failures', [])
    direction=service.saved.get('production_direction')
    for key, watch in ready:
        if watch.get('kind') not in ('native','local') or watch.get('job_status') not in ('FAILED','INTERRUPTED'):
            continue
        detail=str(watch.get('detail',''))
        if not re.search(r'interrupted AE command|After Effects.{0,30}crash|AfterFX.{0,30}crash|connection.{0,15}forcibly closed',detail,re.I):
            continue
        incident=watch.get('command_id')
        if watch.get('kind')=='local':
            try:
                job=service.runtime.local_ops.job(watch['job_id'])
                for step in job.get('steps',[]):
                    path=service.root/'data/local-ops/jobs'/job['id']/step['id']/'request.json'
                    if path.is_file():incident=load(path).get('id') or incident
                    if not incident:incident=(step.get('report') or {}).get('command_id')
            except (OSError,ValueError,KeyError):pass
        incident=incident or key
        if not any(r['incident']==incident and r.get('direction')==direction for r in history):
            history.append({'incident':incident,'direction':direction,'at':stamp(),'detail':detail[:800]})
    service.saved['native_host_failures']=history[-40:]
    failures=[r for r in history if r.get('direction')==direction]
    if len(failures)<2:return False
    from production_guard import notify
    service.saved['continuation_authorized']=False
    service.saved['backup_suppressed']=True
    service.backup_cancel.set()
    service.saved['production_pause']={'at':stamp(),'reason':'Repeated native AE host interruption/crash; automatic retries stopped. Inspect crash evidence before a new human direction.'}
    for _,watch in ready:watch['status']='held'
    notify(service,'native-crash:'+str(direction),'After Effects repeatedly crashed — automatic work paused',
           'Two distinct native-host failures were observed. No additional model recovery or render was launched. '
           'Inspect Windows crash reports and the exact scripts/results; a diagnostic change and explicit human resume are required.')
    return True


def require_native_ready(root):
    from operations import load
    path=Path(root)/'data/command/NATIVE_SAFETY_HOLD.json'
    try:hold=load(path)
    except FileNotFoundError:return
    if hold.get('active'):
        raise ValueError('Native rendering/building is held for AE crash diagnosis: '+str(hold.get('reason','Inspect saved incident evidence before release.')))
