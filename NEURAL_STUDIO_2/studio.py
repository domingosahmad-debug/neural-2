"""Independent Neural 2 workspace. All durable data belongs to this directory."""
import argparse
import copy
import hashlib
import json
import secrets
import mimetypes
import re
from urllib.parse import urlparse, parse_qs
import sqlite3
import webbrowser
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4
from knowledge import context, seed

ROOT = Path(__file__).resolve().parent
STAGES = ('Director', 'Plan', 'Edit', 'Review', 'Deliver')
EXECUTIVE = 'Executive Director'
FILES = {'/': 'index.html', '/index.html': 'index.html', '/stations.js': 'stations.js',
         '/workflow.css': 'workflow.css',
         '/studio.js': 'studio.js', '/control.js':'control.js', '/services.js': 'services.js', '/editor.js':'editor.js', '/editor.css':'editor.css', '/executive.js':'executive.js', '/production.js':'production.js', '/debug.js':'debug.js'}


def required(data, field, limit):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{field} must contain 1 to {limit} characters.')
    return value.strip()


def event(project, text):
    project['activity'].insert(0, {'at': datetime.now(timezone.utc).isoformat(), 'text': text})


def assignment_snapshot(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def replace_worker(projects,data,jobs):
    """Replace a failed/unstarted text worker without replaying completed work.

    Current authorization permits Claude/Gemini/OpenCode hosts to replace exhausted
    Codex workers. This never transfers the separate native Director writer lease.
    """
    project=projects.get(data.get('project'))
    if not project or data.get('revision')!=project['revision']:
        raise ValueError('Reload the exact current project revision before replacing a worker.')
    original=project['assignments'].get(data.get('assignmentId'))
    if not original or original['revision']!=project['revision'] or original['station']!=data.get('station') or original['model']!=data.get('expectedModel') or assignment_snapshot(original)!=data.get('expectedSnapshot'):
        raise ValueError('Assignment identity or snapshot changed. Reload; no worker was replaced.')
    if original['status']!='external handoff' or original.get('summary'):
        raise ValueError('Completed, reviewed, approved or superseded work cannot be replayed by replacement.')
    if original['station']==EXECUTIVE and not project.get('executiveEnabled'):
        raise ValueError('Executive Director is off.')
    model=required(data,'model',100)
    if model==original['model']:raise ValueError('Choose a different exact worker model; replacement is not a retry.')
    reason=required(data,'reason',2000)
    affected={original['assignmentId']}
    while True:
        expanded=affected | {r['assignmentId'] for r in project['assignments'].values() if r['revision']==project['revision'] and r['status']!='superseded' and affected.intersection(r.get('dependsOnAssignments',[]))}
        if expanded==affected:break
        affected=expanded
    for assignment_id in affected:
        row=project['assignments'][assignment_id]
        if row['status']!='external handoff' or row.get('summary'):
            raise ValueError('A dependent task already has evidence; preserve it and reconcile dependencies explicitly.')
        attempts=[j for j in jobs if j.get('project')==project['id'] and j.get('assignmentId')==assignment_id]
        if any(str(j.get('status')).upper()!='FAILED' or j.get('conversation_blocked') for j in attempts):
            raise ValueError('Active, UNKNOWN, uncertain or completed provider work blocks replacement; reconcile exact outcomes first.')
        if assignment_id!=original['assignmentId'] and attempts:
            raise ValueError('A dependent assignment has already been attempted; preserve its evidence and reconcile explicitly.')
    # Validate everything before changing any saved assignment.
    identities={old:uuid4().hex for old in affected}
    packets=[]
    for old_id in sorted(affected):
        old=project['assignments'][old_id]
        frozen=copy.deepcopy(old)
        packet=copy.deepcopy(frozen)
        packet.update(assignmentId=identities[old_id],status='external handoff',replacementOf=old_id,replacementReason=reason)
        packet['resultTemplate']['assignmentId']=packet['assignmentId']
        if old_id==original['assignmentId']:packet['model']=model
        if 'dependsOnAssignments' in packet:packet['dependsOnAssignments']=[identities.get(dep,dep) for dep in packet['dependsOnAssignments']]
        packet['replacementAuthority']='Provider-independent text worker replacement is authorized. Claude/Gemini/OpenCode hosts may replace exhausted Codex workers without a workflow reset. Native Director lease transfer remains a separate guarded safe-boundary action.'
        old.update(status='superseded',supersededBy=packet['assignmentId'],supersededSnapshot=frozen)
        project['assignments'][packet['assignmentId']]=packet
        packets.append(copy.deepcopy(packet))
    event(project,f"{original['station']} worker replaced with {model}; task, evidence and dependencies retained; no jobs or native lease transfers started")
    return {'packet':next(p for p in packets if p['replacementOf']==original['assignmentId']),'dependentPackets':[p for p in packets if p['replacementOf']!=original['assignmentId']],'dispatched':False,'nativeLeaseTransferred':False}


def apply(projects, action, data, provider_jobs=None):
    if action=='replace-worker':
        if provider_jobs is None:raise ValueError('Replacement requires a current provider-job snapshot.')
        return replace_worker(projects,data,provider_jobs)
    if action == 'project':
        project_id = uuid4().hex
        project = {'id': project_id, 'name': required(data, 'name', 100),
                   'brief': required(data, 'brief', 12000), 'revision': 1,
                   'assignments': {}, 'activity': [], 'notes': [], 'messages': []}
        event(project, 'Project created')
        projects[project_id] = project
        return project
    project = projects.get(data.get('project'))
    if not project:
        raise ValueError('Select an existing project.')
    if action == 'executive-enable':
        if type(data.get('enabled')) is not bool: raise ValueError('Choose on or off.')
        project['executiveEnabled'] = data['enabled']
        if not data['enabled']:
            for row in project['assignments'].values():
                if row['station'] == EXECUTIVE and row['status'] == 'external handoff': row['status'] = 'superseded'
        event(project, 'Executive Director enabled manually' if data['enabled'] else 'Executive Director disabled; pending handoffs invalidated')
        return project
    if action == 'executive-apply':
        row = project['assignments'].get(data.get('assignmentId'))
        if not project.get('executiveEnabled') or not row or row['station'] != EXECUTIVE or row['status'] != 'approved' or row['revision'] != project['revision'] or row.get('applied'):
            raise ValueError('Enable the station and approve a current, unapplied plan first.')
        # This creates portable station packets only. No inference or provider dispatch.
        packets=[]; allocated={}
        for allocation in row['allocationPlan']:
            task = allocation['task'] + '\nAcceptance: ' + allocation['acceptance'] + '\nDependencies: ' + ', '.join(allocation.get('dependsOn',[])) + '\nAvailability evidence: ' + allocation['availabilityEvidence']
            if len(task) > 12000: raise ValueError('Combined task exceeds 12000 characters.')
            packet=apply(projects,'assign',{'project':project['id'],'revision':project['revision'],'station':allocation['station'],'model':allocation['model'],'task':task})
            packet['dependsOnAssignments']=[allocated[dep] for dep in allocation['dependsOn']]
            project['assignments'][packet['assignmentId']]['dependsOnAssignments']=packet['dependsOnAssignments']
            allocated[allocation['station']]=packet['assignmentId'];packets.append(packet)
        row['applied'] = True
        project['messages'].append({'role':'executive','revision':project['revision'],'text':row['summary']})
        event(project, 'Executive plan handed to Director and station packets; no models started')
        return {'packets':packets}
    if action == 'brief':
        if data.get('revision') != project['revision']:
            raise ValueError('The brief changed. Reload before editing it.')
        project['brief'] = required(data, 'brief', 12000)
        project['revision'] += 1
        event(project, f"Brief revised to r{project['revision']}. Existing results are retained as history.")
    elif action == 'assign':
        station = required(data, 'station', 30)
        if station not in (*STAGES,EXECUTIVE) or data.get('revision') != project['revision']:
            raise ValueError('Select a valid station and reload the current brief.')
        if station == EXECUTIVE and not project.get('executiveEnabled'): raise ValueError('Executive Director is off. Explicitly enable it first.')
        model = required(data, 'model', 100)
        task = required(data, 'task', 12000)
        assignment_id = uuid4().hex
        evidence = {row['station']: row['summary'] for row in project['assignments'].values()
                    if row['revision'] == project['revision'] and row['status'] == 'approved'}
        packet = {'schema': 'neural.station-task.v2', 'project': project['id'],
                  'projectName': project['name'], 'revision': project['revision'], 'station': station,
                  'assignmentId': assignment_id, 'model': model, 'task': task, 'brief': project['brief'],
                  'approvedEvidence': evidence, 'directorNotes': project['messages'], 'editingContext': context(), 'requiredCapabilities': ['read text', 'return JSON'],
                  'authority': 'Draft text evidence only. Return the result template with a summary.',
                  'resultTemplate': {'schema': 'neural.station-result.v2', 'project': project['id'],
                                     'revision': project['revision'], 'station': station,
                                     'assignmentId': assignment_id, 'summary': ''}}
        if station == EXECUTIVE:
            packet.update(authority='One planning pass only. Read the human brief and accepted workflow. Allocate tasks and advise Director. Do not edit media, call workers, poll jobs or continue automatically. Verify actual capabilities and quota through the current host; UNKNOWN is not available. Return one allocation plan then stop.',
                modelCatalog=json.loads((ROOT/'model_catalog.json').read_text(encoding='utf-8'))['models'],
                availability={'quota':'UNKNOWN; not measured by this application','capabilities':'Catalog suggestions only; verify with actual host tools before claiming availability'},
                currentAssignments=[{k:r[k] for k in ('station','model','task','status','revision')} for r in project['assignments'].values() if r['revision']==project['revision']],
                allocationContract={'stations':list(STAGES),'oneTaskPerStation':True,'required':['station','model','task','acceptance','dependsOn','availabilityEvidence'], 'characterLimits':{'model':100,'task':8000,'acceptance':2000,'availabilityEvidence':1000,'summary':12000}, 'dependencyRule':'Use earlier station names only; never launch dependent work before its evidence exists.'})
            packet['resultTemplate']['allocationPlan'] = []
        for row in project['assignments'].values():
            if row['station'] == station and row['revision'] == project['revision']:
                row['status'] = 'superseded'
        project['assignments'][assignment_id] = dict(packet, status='external handoff')
        event(project, f'{station} packet prepared for {model}')
        return packet
    elif action in ('result', 'approve'):
        row = project['assignments'].get(data.get('assignmentId'))
        expected = 'external handoff' if action == 'result' else 'needs review'
        if not row or row['revision'] != project['revision'] or row['status'] != expected:
            raise ValueError('Assignment is stale, superseded or already processed.')
        if action == 'result':
            for dependency in row.get('dependsOnAssignments',[]):
                prior=project['assignments'].get(dependency)
                if not prior or prior['status']!='approved' or prior['revision']!=project['revision']: raise ValueError('Required predecessor evidence is not approved. Do not redo or poll the task; wait for its completion event.')
            template = row['resultTemplate']
            if any(data.get(key) != template[key] for key in ('schema', 'project', 'revision', 'station', 'assignmentId')):
                raise ValueError('Result does not match the original packet.')
            if row['station'] == EXECUTIVE:
                if not project.get('executiveEnabled'): raise ValueError('Executive Director is disabled.')
                plan = data.get('allocationPlan')
                if not isinstance(plan,list) or not 1<=len(plan)<=5: raise ValueError('Return 1–5 station allocations.')
                seen=set()
                for part in plan:
                    if not isinstance(part,dict) or part.get('station') not in STAGES or part['station'] in seen: raise ValueError('Use each production station at most once.')
                    for field,limit in [('model',100),('task',8000),('acceptance',2000),('availabilityEvidence',1000)]: required(part,field,limit)
                    deps=part.get('dependsOn')
                    if not isinstance(deps,list) or any(d not in seen for d in deps): raise ValueError('Dependencies must reference earlier allocations, without cycles.')
                    seen.add(part['station'])
                row['allocationPlan']=plan
            row.update(summary=required(data, 'summary', 12000), status='needs review')
        else:
            row['status'] = 'approved'
        event(project, f"{row['station']} result {row['status']}")
    elif action == 'note':
        seconds = data.get('seconds')
        if type(seconds) not in (int, float) or not 0 <= seconds <= 86400:
            raise ValueError('Provide a valid playback time.')
        project['notes'].append({'version': required(data, 'version', 250),
                                 'seconds': seconds, 'text': required(data, 'text', 4000)})
        event(project, 'Timecoded review note added')
    elif action == 'message':
        project['messages'].append({'role': 'operator', 'revision': project['revision'], 'text': required(data, 'text', 12000)})
        event(project, 'Director note saved')
    else:
        raise ValueError('Unknown workspace action.')
    return project


def serve(db, port, open_browser=False):
    import maintenance
    if not maintenance.inspect(ROOT)['clean']:
        raise SystemExit('Source repair is unfinished or awaiting restart reconciliation; start through bootstrap.py.')
    from services import Services
    services = Services()
    from providers import ProviderJobs
    from native_lane import NativeLane
    providers = ProviderJobs(ROOT, on_terminal=services.complete, on_change=services.signal)
    native = NativeLane(ROOT)
    from editor import Editor
    editor = Editor(services)
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
        connection.execute("INSERT OR IGNORE INTO workspace VALUES (1, '{}')")
        projects = json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
        if 'tony-editing-workspace' not in projects:
            imported = seed()
            event(imported, 'Existing editing workspace linked and accepted workflow imported')
            projects[imported['id']] = imported
            connection.execute('UPDATE workspace SET body=? WHERE id=1', (json.dumps(projects),))
    from control import Control
    from review_library import ReviewLibrary
    control=Control(ROOT,db,providers,native,services.signal)
    from production import Production
    production=Production(control,services)
    control.production=production
    providers.prepare_packet=production.prepare
    reviews=ReviewLibrary(ROOT)
    providers.before_start=control.admitted
    terminal_callback=providers.on_terminal
    def controller_terminal(row):
        terminal_callback(row)
        control.terminal(row)
        production.notify(row)
    providers.on_terminal=controller_terminal
    control.reconcile()
    media_callback=services.engine.on_terminal
    def production_media_terminal(row):
        media_callback(row)
        production.notify(row)
    services.engine.on_terminal=production_media_terminal
    token = secrets.token_urlsafe(32)
    from debug_console import DebugConsole
    debug = DebugConsole(ROOT, control, services, editor, production, native, on_change=services.signal, secrets=(token,))
    def notify_result(project, row):
        services.complete({'id':row['assignmentId'], 'status':row['status'], 'task':row['task'],
                           'model':row['model'], 'recipient':'Director', 'project':project['id']})
    for project in projects.values():
        for row in project['assignments'].values():
            if row['status'] == 'needs review': notify_result(project, row)

    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, status, body, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def json(self, value, status=200):
            self.send_bytes(status, json.dumps(value).encode(), 'application/json')

        def trusted_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.trusted_host():
                return self.send_error(403)
            parsed = urlparse(self.path)
            if parsed.path == '/api/review':
                try:
                    pid=parse_qs(parsed.query).get('project',[''])[0]
                    with closing(sqlite3.connect(db)) as connection:
                        p=json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0]).get(pid)
                    if not p: raise ValueError('Project not found.')
                    return self.json({'result':reviews.list(pid,p)})
                except (ValueError,OSError,KeyError) as error: return self.json({'error':str(error)},400)
            if parsed.path == '/api/review-media':
                try:
                    q=parse_qs(parsed.query);path=reviews.media_path(q.get('project',[''])[0],q.get('version',[''])[0])
                    size=path.stat().st_size;start,end,status=0,size-1,200
                    if self.headers.get('Range'):
                        match=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers['Range'])
                        if not match or not any(match.groups()):return self.send_error(416)
                        a,b=match.groups()
                        if a:start,end=int(a),min(int(b),size-1) if b else size-1
                        else:start=max(0,size-int(b))
                        if start>end or start>=size:return self.send_error(416)
                        status=206
                    self.send_response(status);self.send_header('Content-Type',mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
                    self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
                    if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    with path.open('rb') as stream:
                        stream.seek(start);remaining=end-start+1
                        while remaining:
                            chunk=stream.read(min(1048576,remaining))
                            if not chunk:break
                            self.wfile.write(chunk);remaining-=len(chunk)
                    return
                except (BrokenPipeError,ConnectionError):return
                except (ValueError,OSError,KeyError):return self.send_error(404)
            if parsed.path in ('/api/editor-media','/api/editor-output'):
                try:
                    q = parse_qs(parsed.query)
                    path = editor.media_path(q.get('project',[''])[0], q.get('id',[''])[0]) if parsed.path.endswith('media') else editor.output_path(q.get('id',[''])[0])
                    size = path.stat().st_size
                    start, end, status = 0, size-1, 200
                    header = self.headers.get('Range')
                    if header:
                        match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
                        if not match or not any(match.groups()): return self.send_error(416)
                        a,b = match.groups()
                        if a: start, end = int(a), min(int(b),size-1) if b else size-1
                        else: start = max(0,size-int(b))
                        if start > end or start >= size: return self.send_error(416)
                        status = 206
                    self.send_response(status)
                    self.send_header('Content-Type',mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
                    self.send_header('Accept-Ranges','bytes')
                    self.send_header('Content-Length',str(end-start+1))
                    self.send_header('Cache-Control','no-store')
                    if status == 206: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    with path.open('rb') as stream:
                        stream.seek(start); remaining=end-start+1
                        while remaining:
                            chunk=stream.read(min(1024*1024,remaining))
                            if not chunk: break
                            self.wfile.write(chunk);remaining-=len(chunk)
                    return
                except (BrokenPipeError, ConnectionError): return
                except (ValueError, OSError, KeyError): return self.send_error(404)
            if self.path == '/api/events':
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                version = -1
                try:
                    while True:
                        with services.changed:
                            if version == services.version: services.changed.wait(timeout=25)
                            current = services.version
                        if current != version:
                            self.wfile.write(('data: ' + json.dumps({'version':current}) + '\n\n').encode())
                            version = current
                        else:
                            self.wfile.write(b': keepalive\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
            if self.path == '/api/workspace':
                with closing(sqlite3.connect(db)) as connection:
                    projects = json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
                models = json.loads((ROOT / 'model_catalog.json').read_text(encoding='utf-8'))
                return self.json({'application': 'neural-studio-2', 'token': token, 'projects': projects, 'knowledge': context(), 'models': models['models']})
            if self.path.startswith('/api/audio/'):
                key = self.path.removeprefix('/api/audio/')
                if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
                    return self.send_error(404)
                path = services.folder / key / 'speech.wav'
                if not path.is_file(): return self.send_error(404)
                return self.send_bytes(200, path.read_bytes(), 'audio/wav')
            filename = FILES.get(self.path)
            if not filename:
                return self.send_error(404)
            mime = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'}
            path = ROOT / filename
            self.send_bytes(200, path.read_bytes(), mime[path.suffix] + '; charset=utf-8')

        def do_POST(self):
            if not self.trusted_host() or self.headers.get('X-Neural-Token') != token:
                return self.send_error(403)
            if self.path not in ('/api/workspace', '/api/services', '/api/editor', '/api/production','/api/control','/api/debug'):
                return self.send_error(404)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= (1048576 if self.path == '/api/editor' else 65536):
                    raise ValueError('Invalid request size.')
                request = json.loads(self.rfile.read(size))
                if not isinstance(request, dict):
                    raise ValueError('Expected an object.')
                if self.path == '/api/debug':
                    return self.json({'result':debug.action(request)})
                if self.path == '/api/control':
                    return self.json({'result':control.action(request)})
                if self.path == '/api/services':
                    if request.get('action')=='media-submit':
                        if control.status(request.get('project'))['paused']:raise ValueError('Project paused; no new media work admitted.')
                    return self.json({'result': services.action(request)})
                if self.path == '/api/production':
                    action = request.get('action')
                    if action == 'status':
                        readiness_path=ROOT/'READINESS.json'
                        readiness=json.loads(readiness_path.read_text(encoding='utf-8')) if readiness_path.exists() else {}
                        return self.json({'result':{'jobs':providers.status(), 'native':native.status(), 'readiness':readiness.get('message','Commissioning; edit continuation is held until PRODUCTION_READINESS.md gates pass.')}})
                    if action == 'cancel': return self.json({'result':providers.cancel(request.get('id'))})
                    if action == 'result': return self.json({'result':providers.result(request.get('id'))})
                    if action == 'native-claim':
                        with control.lock:
                          with maintenance.admission(ROOT,'native-claim'): return self.json({'result':native.claim(request.get('owner'),request.get('project'),request.get('oldDisabled'),replace=production.lease_handover())})
                    if action == 'native-release':
                        with control.lock:
                            production.invalidate()
                            return self.json({'result':native.release(request.get('ownerId'))})
                    if action != 'dispatch': raise ValueError('Unsupported production action.')
                    with closing(sqlite3.connect(db)) as connection, connection:
                        connection.execute('BEGIN IMMEDIATE')
                        available=json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
                        p=available.get(request.get('project'))
                        if p and p.get('productionControl',{}).get('paused'):raise ValueError('Project paused by user; no provider dispatch admitted.')
                        row=p and p['assignments'].get(request.get('assignmentId'))
                        if not row or row['revision']!=p['revision'] or row['status']!='external handoff': raise ValueError('Assignment is stale or already processed.')
                        if row['station']==EXECUTIVE and not p.get('executiveEnabled'): raise ValueError('Executive Director is off.')
                        for dependency in row.get('dependsOnAssignments',[]):
                            prior=p['assignments'].get(dependency)
                            if not prior or prior['revision']!=p['revision'] or prior['status']!='approved': raise ValueError('Predecessor evidence must be approved before dispatch.')
                        if request.get('model')!=row['model']: raise ValueError('Exact assigned model required; no silent model substitution.')
                        packet=json.loads(json.dumps(row))
                        # Freeze actual approved predecessors at dispatch, not when the
                        # executive initially prepared downstream task placeholders.
                        packet['predecessorEvidence']=[{key:p['assignments'][dep].get(key) for key in ('assignmentId','station','revision','model','summary')} for dep in row.get('dependsOnAssignments',[])]
                        packet['approvedEvidence']={r['station']:r['summary'] for r in p['assignments'].values() if r['revision']==p['revision'] and r['status']=='approved'}
                        result=providers.submit(packet,request.get('route'),request.get('model'),request.get('effort'),request.get('requestId'))
                    return self.json({'result':result})
                if self.path == '/api/editor':
                    with closing(sqlite3.connect(db)) as connection:
                        available = json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
                    if request.get('project') not in available: raise ValueError('Select an existing workspace project.')
                    return self.json({'result':editor.action(request)})
                with closing(sqlite3.connect(db)) as connection, connection:
                    connection.execute('BEGIN IMMEDIATE')
                    projects = json.loads(connection.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
                    action = request.pop('action', None)
                    if action in ('brief','assign','executive-enable','executive-apply','result','approve'):
                        if action in ('brief','assign','executive-enable','executive-apply'):
                            production.invalidate(request.get('project'))
                        running=[j for j in providers.status() if j.get('project')==request.get('project') and str(j.get('status')).upper() in ('QUEUED','RUNNING','CANCELLING','UNKNOWN')]
                        if action in ('result','approve'):
                            running=[j for j in running if j.get('assignmentId')==request.get('assignmentId')]
                        elif action == 'assign':
                            running=[j for j in running if j.get('station')==request.get('station')]
                        elif action == 'executive-enable':
                            running=[j for j in running if j.get('station')==EXECUTIVE]
                        if running: raise ValueError('Finish or cancel active station work before changing its instructions or enable state.')
                    result = apply(projects, action, request, provider_jobs=providers.status() if action=='replace-worker' else None)
                    connection.execute('UPDATE workspace SET body=? WHERE id=1', (json.dumps(projects),))
                if action == 'result':
                    project = projects[request['project']]
                    notify_result(project, project['assignments'][request['assignmentId']])
                self.json({'result': result, 'projects': projects})
            except (ValueError, TypeError, KeyError, OSError) as error:
                self.json({'error': str(error)}, 400)

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        import model_discovery
        model_discovery.sync_catalog_async(ROOT)
        production.service_url=f'http://127.0.0.1:{server.server_port}/'
        production.service_token=token
        production.recover()
        print(f'Neural 2.0  http://127.0.0.1:{server.server_port}/', flush=True)
        if open_browser:
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/')
        try:
            server.serve_forever()
        finally:
            production.shutdown()
            debug.shutdown()
            providers.shutdown()
            editor.shutdown()
            services.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8872)
    parser.add_argument('--database', type=Path, default=ROOT / 'workspace.sqlite3')
    parser.add_argument('--open', action='store_true')
    options = parser.parse_args()
    serve(options.database, options.port, options.open)




