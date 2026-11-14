"""Provider-independent station client for a tool-enabled local assistant."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

service = Path(__file__).resolve().parent / '.desktop-service.json'
BASE = (json.loads(service.read_text())['url'] if service.exists() else 'http://127.0.0.1:8872/') + 'api/workspace'
parser = argparse.ArgumentParser(description=__doc__)
commands = parser.add_subparsers(dest='command', required=True)
commands.add_parser('projects')
commands.add_parser('production-status')
control_status = commands.add_parser('control-status', help='Read actual station state and durable continuation checkpoints.')
control_status.add_argument('project')
control_status.add_argument('--out', type=Path, help='Save the complete raw control status; stdout remains compact.')
pause = commands.add_parser('pause', help='Pause future project work; active work reaches its safe boundary.')
pause.add_argument('project')
pause.add_argument('--reason', required=True)
continue_task = commands.add_parser('continue', help='Continue one permitted saved station task through the same control API as the UI. Never unpauses an edit.')
continue_task.add_argument('project')
continue_task.add_argument('station')
continue_task.add_argument('--model', required=True, help='Exact model identifier; no silent substitution.')
continue_task.add_argument('--route', required=True)
continue_task.add_argument('--effort', required=True)
continue_task.add_argument('--request-id', required=True, help='Persist and reuse this exact ID after an uncertain response. Never generate a replacement ID to retry.')

replace = commands.add_parser('replace-worker', help='Create a new station assignment preserving the exact current task; never replays a job.')
replace.add_argument('project')
replace.add_argument('station')
replace.add_argument('--model', required=True)
replace.add_argument('--reason',default='Replace the unavailable worker without resetting the workflow or replaying completed work.')
dispatch = commands.add_parser('dispatch')
dispatch.add_argument('project')
dispatch.add_argument('station')
dispatch.add_argument('--route',choices=['claude','codex','opencode'],required=True)
dispatch.add_argument('--effort',default='medium')
dispatch.add_argument('--request-id',required=True,help='Persist and reuse this ID; do not generate another after an uncertain response.')
cancel = commands.add_parser('cancel-job')
cancel.add_argument('job')
job_result = commands.add_parser('job-result')
job_result.add_argument('job')
job_result.add_argument('--out',type=Path,required=True)
for name in ('executive-enable','executive-disable'):
    commands.add_parser(name).add_argument('project')
executive = commands.add_parser('executive-task')
executive.add_argument('project')
executive.add_argument('--model',required=True)
executive.add_argument('--task',required=True)
events = commands.add_parser('events')
events.add_argument('--recipient', default='Director')
wait = commands.add_parser('wait')
wait.add_argument('--recipient', default='Director')
wait.add_argument('--timeout', type=int, default=60)
ack = commands.add_parser('acknowledge')
ack.add_argument('event_id', type=int)
packet = commands.add_parser('packet')
packet.add_argument('project')
packet.add_argument('station')
packet.add_argument('--out', type=Path, help='Save the complete packet instead of printing it.')
result = commands.add_parser('result')
result.add_argument('file', type=Path)
args = parser.parse_args()
with urlopen(BASE, timeout=10) as response:
    workspace = json.load(response)
projects = workspace['projects']
def services(data):
    request = Request(BASE.replace('/api/workspace', '/api/services'), json.dumps(data).encode(), headers={
        'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(request, timeout=10) as response: return json.load(response)['result']

def production(data):
    request = Request(BASE.replace('/api/workspace','/api/production'),json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(request,timeout=15) as response: return json.load(response)['result']

def control(data):
    request = Request(BASE.replace('/api/workspace', '/api/control'), json.dumps(data).encode(), headers={
        'Content-Type':'application/json', 'X-Neural-Token':workspace['token']})
    try:
        with urlopen(request, timeout=15) as response: return json.load(response)['result']
    except HTTPError as error:
        raw = error.read().decode('utf-8', errors='replace')
        try: message = json.loads(raw).get('error') or raw
        except ValueError: message = raw
        output = {'error':message, 'httpStatus':error.code}
        if data.get('requestId'):
            output.update(requestId=data['requestId'], outcome='unknown' if error.code >= 500 or any(word in message.lower() for word in ('unknown','unresolved')) else 'rejected', retryInstruction='Reconcile using this same request ID; never create a replacement to retry.')
        parser.exit(1, json.dumps(output, ensure_ascii=True, indent=2) + '\n')
    except (URLError, TimeoutError, ValueError, KeyError, OSError) as error:
        output = {'error':str(error), 'outcome':'unknown'}
        if data.get('requestId'):
            output.update(requestId=data['requestId'], retryInstruction='Response was not confirmed. Reconcile using this same request ID; never create a replacement to retry.')
        parser.exit(1, json.dumps(output, ensure_ascii=True, indent=2) + '\n')

def compact_control(state):
    output = {key:state.get(key) for key in ('project','paused','pauseSettled','pauseReason','autonomousNativeReady','autonomyReason')}
    output['stations'] = []
    for station in state.get('stations', []):
        row = {key:station.get(key) for key in ('station','state','model','jobId','updated','reason')}
        row['savedTaskCount'] = len(station.get('history', []))
        row['jobs'] = [{key:job.get(key) for key in ('id','assignmentId','model','status','session_id','result_path','error')} for job in station.get('jobs', [])]
        output['stations'].append(row)
    output['checkpoints'] = [{key:checkpoint.get(key) for key in ('id','station','model','state','created','finished','jobId','resultPath','sessionId','error','fallbackBlocked')} for checkpoint in state.get('checkpoints', [])]
    return output

if args.command in ('control-status', 'pause', 'continue'):
    body = {'action':{'control-status':'status','pause':'pause','continue':'continue'}[args.command], 'project':args.project}
    if args.command == 'pause': body['reason'] = args.reason
    if args.command == 'continue':
        station = next((name for name in ('Director','Plan','Edit','Review','Deliver','Executive Director') if name.casefold() == args.station.casefold()), args.station)
        body.update(station=station, model=args.model, route=args.route, effort=args.effort, requestId=args.request_id)
    state = control(body)
    output = compact_control(state) if args.command != 'continue' else state
    if args.command == 'control-status' and args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        output['rawEvidencePath'] = str(args.out.resolve())
elif args.command == 'replace-worker':
    project=projects.get(args.project)
    if not project: parser.error('Project not found.')
    rows=[r for r in project['assignments'].values() if r['station'].casefold()==args.station.casefold() and r['revision']==project['revision'] and r['status']!='superseded']
    if len(rows)!=1: parser.error('Select exactly one current station task; completed or ambiguous work must be reconciled.')
    row=rows[0]
    snapshot=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    body={'action':'replace-worker','project':args.project,'revision':project['revision'],'station':row['station'],'assignmentId':row['assignmentId'],'expectedModel':row['model'],'expectedSnapshot':snapshot,'model':args.model,'reason':args.reason}
    request=Request(BASE,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(request,timeout=10) as response: replacement=json.load(response)['result']
    packet=replacement['packet']
    output={key:packet.get(key) for key in ('project','revision','station','assignmentId','model')}
    output['dispatched']=False
    output['replacedAssignmentId']=packet['replacementOf']
    output['dependentAssignmentsRebound']=[p['assignmentId'] for p in replacement['dependentPackets']]
    output['nativeLeaseTransferred']=False
elif args.command == 'production-status':
    output=production({'action':'status'})
elif args.command == 'cancel-job':
    output=production({'action':'cancel','id':args.job})
elif args.command == 'job-result':
    result=production({'action':'result','id':args.job})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    output={'saved':str(args.out.resolve()),'status':result.get('status')}
elif args.command == 'dispatch':
    project=projects.get(args.project)
    if not project: parser.error('Project not found.')
    row=next((r for r in project['assignments'].values() if r['station'].casefold()==args.station.casefold() and r['revision']==project['revision'] and r['status']=='external handoff'),None)
    if not row: parser.error('No current station packet.')
    output=production({'action':'dispatch','project':args.project,'assignmentId':row['assignmentId'],'route':args.route,'model':row['model'],'effort':args.effort,'requestId':args.request_id})
elif args.command in ('events', 'wait'):
    def pending():
        return [e for e in services({'action':'status'})['events'] if e['recipient'].casefold() == args.recipient.casefold()]
    output = pending()
    if not output and args.command == 'wait':
        deadline = time.monotonic() + min(max(args.timeout, 1), 3600)
        # Blocks on app completion events; does not wake a model or schedule status turns.
        with urlopen(BASE.replace('/api/workspace', '/api/events'), timeout=30) as stream:
            for raw in stream:
                if raw.startswith(b'data:'):
                    output = pending()
                    if output: break
                if time.monotonic() >= deadline: break
    output = {'recipient':args.recipient, 'events':output, 'acknowledged':False}
elif args.command == 'acknowledge':
    output = services({'action':'acknowledge','eventId':args.event_id})
elif args.command == 'projects':
    output = [{key: row[key] for key in ('id', 'name', 'revision')} for row in projects.values()]
elif args.command.startswith('executive-'):
    project = projects.get(args.project)
    if not project: parser.error('Project not found.')
    body={'project':args.project}
    if args.command == 'executive-task': body.update(action='assign',station='Executive Director',revision=project['revision'],model=args.model,task=args.task)
    else: body.update(action='executive-enable',enabled=args.command=='executive-enable')
    request=Request(BASE,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(request,timeout=10) as response: output=json.load(response)['result']
    if args.command in ('executive-enable','executive-disable'):
        output={key:output.get(key) for key in ('id','name','revision','executiveEnabled')}
elif args.command == 'packet':
    project = projects.get(args.project)
    if not project:
        parser.error('Project not found.')
    output = next((row for row in project['assignments'].values()
                   if row['station'].casefold() == args.station.casefold()
                   and row['revision'] == project['revision'] and row['status'] == 'external handoff'), None)
    if not output:
        parser.error('No current external assignment at that station.')
    output.pop('status')
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        output = {'saved':str(args.out.resolve()), 'assignmentId':output['assignmentId']}
else:
    if args.file.stat().st_size > 65536:
        parser.error('Use a result JSON under 64 KB.')
    data = json.loads(args.file.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or data.get('schema') != 'neural.station-result.v2':
        parser.error('Use a Neural station result.')
    body = {key: data.get(key) for key in ('schema', 'project', 'revision', 'station', 'assignmentId', 'summary')}
    if data.get('station') == 'Executive Director': body['allocationPlan'] = data.get('allocationPlan')
    body['action'] = 'result'
    request = Request(BASE, json.dumps(body).encode(), headers={
        'Content-Type': 'application/json', 'X-Neural-Token': workspace['token']})
    with urlopen(request, timeout=10) as response:
        json.load(response)
    output = {'status': 'needs review', 'assignmentId': body['assignmentId']}
print(json.dumps(output, ensure_ascii=True, indent=2))

