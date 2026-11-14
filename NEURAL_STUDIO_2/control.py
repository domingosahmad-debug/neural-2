"""Durable station control. Assignment, invocation and native work are distinct."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
import copy
import json
import sqlite3
from activity_status import project_activity

STATIONS=('Director','Plan','Edit','Review','Deliver','Executive Director')
ACTIVE={'QUEUED','RUNNING','CANCELLING','UNKNOWN'}

def now(): return datetime.now(timezone.utc).isoformat()

class ClosedConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

class Control:
    def __init__(self, root, db, providers, native, on_change=None):
        self.root,self.db,self.providers,self.native=Path(root),Path(db),providers,native
        self.lock=RLock();self.on_change=on_change or (lambda:None)
        self.production=None
        # Final start reservation and pause commit share one linearization gate.
        # The provider releases it before inference; callbacks never hold it.
        self.providers.admission_lock=self.lock
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS control_steps (id TEXT PRIMARY KEY, project TEXT NOT NULL, request TEXT UNIQUE NOT NULL, body TEXT NOT NULL)')

    def connection(self): return sqlite3.connect(self.db,timeout=15,factory=ClosedConnection)

    def projects(self, db):
        return json.loads(db.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])

    def save_projects(self,db,projects): db.execute('UPDATE workspace SET body=? WHERE id=1',(json.dumps(projects),))

    def step_save(self,db,step):
        db.execute('INSERT INTO control_steps VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                   (step['id'],step['project'],step['requestId'],json.dumps(step)))

    def steps(self, project):
        with closing(self.connection()) as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM control_steps WHERE project=? ORDER BY rowid',(project,))]

    def capabilities(self):
        rows=[]
        catalog=json.loads((self.root/'model_catalog.json').read_text(encoding='utf-8'))['models']
        from providers_engine.transport import executable, validate
        for r in catalog:
            route,model=r['provider'],r['model']
            effort='default' if route=='opencode' else 'high' if route=='gemini' else 'medium'
            try: validate(route,model,effort);executable(route);available=True;reason='Installed adapter; scoped tools require a server-issued production task. Quota checked by actual outcome.'
            except (ValueError,OSError) as e: available=False;reason=str(e)
            rows.append({'route':route,'model':model,'label':r.get('label',model),'efforts':['medium'] if model in ('opus','gpt-6.1-sol','gpt-6-sol') else ['default'] if route=='opencode' else (['high'] if 'gemini' in model else ['low','medium'] if route=='claude' else ['low','medium','high']),
                         'capabilities':(['supplied_text','neural_tools'] if getattr(self,'production',None) else ['supplied_text']) if available else [],'available':available,'reason':reason})
        return rows

    def status(self,pid):
        with closing(self.connection()) as db: p=self.projects(db).get(pid)
        if not p: raise ValueError('Project not found.')
        ctl=p.get('productionControl',{}); jobs=[j for j in self.providers.status() if j.get('project')==pid]
        rows=[]
        for station in STATIONS:
            assignments=[r for r in p['assignments'].values() if r['station']==station]
            current=[r for r in assignments if r['revision']==p['revision'] and r['status']!='superseded']
            task=current[-1] if current else None
            relevant=[j for j in jobs if j.get('station')==station and (not task or j.get('assignmentId')==task['assignmentId'])]
            job=max(relevant,key=lambda j:j.get('created',0),default=None)
            running=[j for j in jobs if j.get('station')==station and j['status'] in ACTIVE]
            if running: job=max(running,key=lambda j:j.get('created',0))
            reason='No invocation is active.';state='idle'
            if job:
                state={'RUNNING':'running','QUEUED':'queued','UNKNOWN':'unknown','FAILED':'blocked','COMPLETED':'completed','CANCELLED':'blocked','CANCELLING':'stopping'}.get(job['status'],'unknown')
                reason=job.get('error') or ('Provider invocation active; this is not proof of AE activity.' if state=='running' else 'Saved provider outcome.')
            elif task: state='ready';reason='Task assigned; no provider has started.'
            if task and task['status']=='needs review' and not running:
                # Production consumes these results through its own review gates.
                # Do not advertise an obsolete manual approval stop for them.
                state='completed' if task.get('productionRun') and job and job['status']=='COMPLETED' else 'needs_review'
                if state=='completed': reason='Saved result; production coordinates the next gate automatically.'
            if ctl.get('paused') and state not in ('running','unknown','stopping'): state='paused';reason=ctl.get('pauseReason','Paused by user.')
            rows.append({'station':station,'state':state,'model':job['model'] if job else task['model'] if task else None,
                         'task':job.get('task') if job else task.get('task') if task else '', 'jobId':job.get('id') if job else None,
                         'updated':job.get('finished') or job.get('started') or job.get('created') if job else ctl.get('pausedAt'),
                         'reason':reason,'history':[{k:r.get(k) for k in ('assignmentId','revision','station','model','task','status','summary','continuedFrom')} for r in assignments],
                         'jobs':[{k:j.get(k) for k in ('id','assignmentId','model','status','created','started','finished','error','session_id','result_path')} for j in jobs if j.get('station')==station]})
        steps=self.steps(pid)
        production=self.production.status(pid) if self.production else None
        if production and production.get('revision') != p['revision']: production=None
        settled=bool(ctl.get('paused')) and not any(j['status'] in ACTIVE for j in jobs) and not self.native.status()['unresolved']
        return {'project':pid,'paused':bool(ctl.get('paused')),'pauseReason':ctl.get('pauseReason',''),'pauseSettled':bool(ctl.get('paused')) and not any(j['status'] in ACTIVE for j in jobs) and not self.native.status()['unresolved'],
                'stations':rows,'checkpoints':[{k:s.get(k) for k in ('id','station','model','state','created','finished','jobId','resultPath','sessionId','error','fallbackBlocked','resultImportError','resultImported')} for s in steps],
                'routing':ctl.get('routing',{}),'capabilities':self.capabilities(),
                'production':production,
                'activity':project_activity(bool(ctl.get('paused')),settled,ctl.get('pauseReason',''),rows,production),
                'autonomousNativeReady':bool(self.production and self.production.configured()),'autonomyReason':'Guarded production tools and completion-event coordination available.' if self.production and self.production.configured() else 'Live native production commissioning has not yet passed.'}

    def admitted(self,row):
        """Called immediately before a queued invocation starts, not only at HTTP admission."""
        with closing(self.connection()) as db:
            p=self.projects(db).get(row.get('project'))
        if not p: return False
        ctl=p.get('productionControl',{})
        if ctl.get('paused') or p['revision']!=row['revision']: return False
        assignment=p.get('assignments',{}).get(row.get('assignmentId'))
        if not assignment or assignment.get('status')=='superseded' or assignment.get('model')!=row.get('model'):return False
        packet_path=Path(row.get('packet_path',''))
        packet=json.loads(packet_path.read_text(encoding='utf-8')) if packet_path.is_file() else {}
        return packet.get('controlGeneration',ctl.get('generation',0))==ctl.get('generation',0)

    def pause(self,pid,reason):
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000: raise ValueError('Provide a pause reason.')
        with self.lock, self.connection() as db:
            if self.production:self.production.invalidate(pid)
            db.execute('BEGIN IMMEDIATE');projects=self.projects(db);p=projects.get(pid)
            if not p: raise ValueError('Project not found.')
            ctl=p.setdefault('productionControl',{});ctl.update(paused=True,pauseReason=reason,pausedAt=now(),generation=ctl.get('generation',0)+1)
            p['messages'].append({'role':'operator','revision':p['revision'],'text':'PAUSED: '+reason})
            self.save_projects(db,projects)
        # Do not kill active/native actions. Their completion evidence remains visible.
        self.on_change();return self.status(pid)

    def routing(self,pid,station,candidates,automatic):
        from providers_engine.transport import validate
        if station not in STATIONS or type(automatic) is not bool or not isinstance(candidates,list) or not 1<=len(candidates)<=8: raise ValueError('Choose a station and 1Ã¢â‚¬â€œ8 fallback models.')
        seen=set()
        for c in candidates:
            if 'gemini' in str(c.get('model','')) and c.get('effort')!='high': raise ValueError('Gemini requires high effort.')
            validate(c.get('route'),c.get('model'),c.get('effort'))
            key=(c['route'],c['model'])
            if key in seen: raise ValueError('A fallback model may appear only once.')
            seen.add(key)
        with self.lock,self.connection() as db:
            db.execute('BEGIN IMMEDIATE');projects=self.projects(db);p=projects.get(pid)
            if not p: raise ValueError('Project not found.')
            p.setdefault('productionControl',{}).setdefault('routing',{})[station]={'candidates':candidates,'automatic':automatic}
            self.save_projects(db,projects)
        return self.status(pid)

    def continue_task(self,request):
        """Commit intent before dispatch; a lost reply reuses exactly that intent."""
        pid,station,rid=request.get('project'),request.get('station'),request.get('requestId')
        if station not in STATIONS or not isinstance(rid,str) or not 1<=len(rid)<=200: raise ValueError('Select a station and persistent request ID.')
        from providers_engine.transport import validate
        route,model,effort=request.get('route'),request.get('model'),request.get('effort')
        validate(route,model,effort)
        with self.lock,self.connection() as db:
            db.execute('BEGIN IMMEDIATE');projects=self.projects(db);p=projects.get(pid)
            if not p: raise ValueError('Project not found.')
            ctl=p.setdefault('productionControl',{})
            if ctl.get('paused'): raise ValueError('This edit is paused by the user. It will not resume through Continue. Create the new edit after app repairs.')
            expected=request.get('expectedTask')
            if expected:
                if p['revision']!=expected['revision'] or ctl.get('generation',0)!=expected['generation']:
                    raise ValueError('Exhausted task was superseded; no fallback admitted.')
                current=[r for r in p['assignments'].values() if r['station']==station and r['revision']==p['revision'] and r['status']!='superseded']
                if len(current)!=1 or current[0]['assignmentId']!=expected['assignmentId']:
                    raise ValueError('Exhausted assignment is no longer current; no fallback admitted.')
            old=db.execute('SELECT body FROM control_steps WHERE request=?',(rid,)).fetchone()
            if old:
                step=json.loads(old[0])
                if (step['project'],step['station'],step['model'],step['route'],step['effort'])!=(pid,station,model,route,effort): raise ValueError('Request ID already belongs to a different immutable continuation.')
            else:
                jobs=[j for j in self.providers.status() if j.get('project')==pid and j.get('station')==station]
                if any(j['status'] in ACTIVE or j.get('conversation_blocked') for j in jobs): raise ValueError('Active or UNKNOWN station execution must be reconciled; no duplicate continuation was started.')
                if self.native.status()['unresolved']: raise ValueError('Native outcome unresolved; no continuation admitted.')
                if station in ('Director','Edit') and not self.production: raise ValueError('This station requires a tool-enabled AE runner. The installed supplied-text connection cannot continue native editing. No worker started.')
                records=[r for r in p['assignments'].values() if r['station']==station and r['revision']==p['revision'] and r['status']!='superseded']
                if not records: raise ValueError('No saved task at this station. Describe the new project first.')
                prior=records[-1]
                if station in ('Director','Edit') and prior.get('toolMode')!='production':raise ValueError('This saved task has no production run. Start a new production project; no text worker can edit AE.')
                if prior.get('summary') or prior['status']!='external handoff': raise ValueError('The saved task already has a result. Review it and set the next task; completed work is not replayed.')
                if any(j['status']=='COMPLETED' for j in jobs if j.get('assignmentId')==prior['assignmentId']): raise ValueError('Saved result awaits import/review; no duplicate work started.')
                if station=='Executive Director' and not p.get('executiveEnabled'): raise ValueError('Executive Director is off.')
                for dep in prior.get('dependsOnAssignments',[]):
                    if p['assignments'].get(dep,{}).get('status')!='approved': raise ValueError('Required predecessor result is not approved.')
                packet=copy.deepcopy(prior);aid=uuid4().hex
                packet.update(assignmentId=aid,model=model,continuedFrom=prior['assignmentId'],logicalTaskId=prior.get('logicalTaskId',prior['assignmentId']),controlGeneration=ctl.get('generation',0))
                packet['resultTemplate']['assignmentId']=aid
                packet['continuationEvidence']=[{'assignmentId':r['assignmentId'],'station':r['station'],'model':r['model'],'summary':r.get('summary'),'status':r['status']} for r in p['assignments'].values() if r.get('summary')]
                # Rebind immutable, unstarted descendants to the new attempt.
                # Otherwise every successor would wait forever on the superseded ID.
                affected={prior['assignmentId']}
                while True:
                    expanded=affected|{r['assignmentId'] for r in p['assignments'].values() if r['revision']==p['revision'] and r['status']!='superseded' and affected.intersection(r.get('dependsOnAssignments',[]))}
                    if expanded==affected:break
                    affected=expanded
                all_jobs=self.providers.status()
                for dep in affected-{prior['assignmentId']}:
                    old=p['assignments'][dep]
                    if old['status']!='external handoff' or old.get('summary') or any(j.get('project')==pid and j.get('assignmentId')==dep for j in all_jobs):
                        raise ValueError('A dependent task already has execution evidence. Preserve it and reconcile before continuation.')
                identities={old:(aid if old==prior['assignmentId'] else uuid4().hex) for old in affected}
                for dep in affected-{prior['assignmentId']}:
                    old=p['assignments'][dep];new=copy.deepcopy(old)
                    new.update(assignmentId=identities[dep],continuedFrom=dep,controlGeneration=ctl.get('generation',0))
                    new['resultTemplate']['assignmentId']=new['assignmentId']
                    new['dependsOnAssignments']=[identities.get(d,d) for d in new.get('dependsOnAssignments',[])]
                    old.update(status='superseded',supersededBy=new['assignmentId'])
                    p['assignments'][new['assignmentId']]=new
                prior.update(status='superseded',supersededBy=aid)
                p['assignments'][aid]=copy.deepcopy(packet)
                step={'id':uuid4().hex,'requestId':rid,'project':pid,'revision':p['revision'],'station':station,'model':model,'route':route,'effort':effort,'state':'INTENT','created':now(),'packet':packet,'generation':ctl.get('generation',0)}
                self.step_save(db,step);self.save_projects(db,projects)
        return self.dispatch_intent(step)

    def dispatch_intent(self,step):
        with self.lock:
            existing=next((j for j in self.providers.status() if j.get('request_id')==step['requestId']),None)
            if existing: job=existing
            else:
                if step.get('jobId') or step['state']!='INTENT':
                    raise ValueError('Durable execution checkpoint exists but provider registry is missing. Reconcile exact job; never replay.')
                with closing(self.connection()) as db: p=self.projects(db).get(step['project'])
                ctl=(p or {}).get('productionControl',{})
                if not p or ctl.get('paused') or ctl.get('generation',0)!=step['generation'] or p['revision']!=step['revision']: raise ValueError('Continuation intent was paused or superseded before dispatch.')
                job=self.providers.submit(step['packet'],step['route'],step['model'],step['effort'],step['requestId'])
            step.update(jobId=job['id'],state=job['status'])
            with self.connection() as db:
                saved=db.execute('SELECT body FROM control_steps WHERE id=?',(step['id'],)).fetchone()
                latest=json.loads(saved[0]) if saved else step
                # A fast worker's terminal callback may already have persisted
                # result import. Never overwrite it with the queued snapshot.
                if latest.get('state') not in ('COMPLETED','FAILED','UNKNOWN','CANCELLED'):
                    latest.update(jobId=job['id'],state=job['status'])
                self.step_save(db,latest)
        self.on_change();return {'stepId':step['id'],'jobId':job['id'],'status':job['status'],'requestId':step['requestId'],'dispatched':True}

    @staticmethod
    def exhausted(row):
        outcome=row.get('result') or {}
        # A generic 429, network/auth error or arbitrary exception is not exhaustion.
        return row.get('status')=='FAILED' and not row.get('conversation_blocked') and outcome.get('failure_kind')=='subscription_exhausted' and bool(outcome.get('exhaustion_evidence'))

    def reconcile(self):
        """Recover missed checkpoint notifications, never resume inference on startup."""
        for row in self.providers.status():
            if row.get('status') not in ACTIVE:
                self.terminal(row,allow_fallback=False)

    def terminal(self,row,*,allow_fallback=True,production_boundary=False):
        pid=row.get('project')
        with self.lock,self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            saved=db.execute('SELECT body FROM control_steps WHERE request=?',(row.get('request_id'),)).fetchone()
            if not saved:return
            step=json.loads(saved[0]);step.update(state=row['status'],jobId=row['id'],finished=step.get('finished') or now(),resultPath=row.get('result_path'),sessionId=row.get('session_id'),error=row.get('error'))
            if row['status']=='COMPLETED' and not step.get('resultImported'):
                from station_results import attach,decode
                try:
                    projects=self.projects(db);project=projects[pid]
                    if (row.get('assignmentId'),row.get('station'),row.get('revision'))!=(step['packet']['assignmentId'],step['station'],step['revision']):
                        raise ValueError('Provider outcome identity does not match the saved continuation.')
                    outcome=self.providers.result(row['id'])
                    if outcome.get('status')!='COMPLETED':raise ValueError('Saved provider result is not terminal COMPLETED.')
                    assignment=attach(project,decode(outcome))
                    assignment['providerEvidence']={'jobId':row['id'],'resultPath':row.get('result_path'),'sessionId':row.get('session_id')}
                    self.save_projects(db,projects)
                    step['resultImported']=True
                    step.pop('resultImportError',None)
                except (ValueError,KeyError,OSError,AttributeError) as e:
                    step['resultImportError']=str(e)
            self.step_save(db,step)
        # Native/autonomous phase advancement is deliberately not inferred from text.
        if not allow_fallback or not self.exhausted(row) or step.get('fallbackAttempt'):return
        if step['packet'].get('toolMode')=='production':
            # Only the coordinator may route production after matching gateway receipts settle.
            if not production_boundary or not self.production:return
            run=self.production.status(pid)
            if not run or run.get('assignmentId')!=row.get('assignmentId'):return
            self.production.settled_native_boundary(run)
        with closing(self.connection()) as db:p=self.projects(db).get(pid)
        if not p or p.get('productionControl',{}).get('paused') or self.native.status()['unresolved']:return
        routing=p.get('productionControl',{}).get('routing',{}).get(row['station'],{})
        if not routing.get('automatic'):return
        used={(s['route'],s['model']) for s in self.steps(pid) if s['packet'].get('logicalTaskId')==step['packet'].get('logicalTaskId')}
        candidates=routing.get('candidates',[])
        # A ChatGPT-plan Codex refusal is account-wide: skip sibling Codex models.
        if row.get('route')=='codex':candidates=[c for c in candidates if c['route']!=row['route']]
        if step['packet'].get('toolMode')=='production':
            candidates=self.production.review_candidates(run,run['phase'],candidates)
        candidate=next((c for c in candidates if (c['route'],c['model']) not in used),None)
        if not candidate:return
        # Persist the decision before dispatch. A duplicate completion notification
        # cannot skip a failed successor and consume another provider's quota.
        with self.lock,self.connection() as db:
            saved=db.execute('SELECT body FROM control_steps WHERE request=?',(row.get('request_id'),)).fetchone()
            current=json.loads(saved[0])
            if current.get('fallbackAttempt'):return
            step=current
            step['fallbackAttempt']={'candidate':candidate,'requestId':'fallback:'+step['id'],'at':now()}
            self.step_save(db,step)
        try:self.continue_task(dict(candidate,project=pid,station=row['station'],requestId='fallback:'+step['id'],
                                   expectedTask={'assignmentId':step['packet']['assignmentId'],'revision':step['revision'],'generation':step['generation']}))
        except (ValueError,OSError) as e:
            step['fallbackBlocked']=str(e)
            with self.connection() as db:self.step_save(db,step)

    def action(self,r):
        if r.get('action') in ('status','pause','routing'):return self._action(r)
        import maintenance
        with maintenance.admission(self.root,'production'):
            return self._action(r)

    def _action(self,r):
        action=r.get('action');pid=r.get('project')
        if action=='steer':
            if not self.production:raise ValueError('Production coordinator unavailable.')
            return self.production.steer(r)
        if action=='status':return self.status(pid)
        if action=='pause':return self.pause(pid,r.get('reason'))
        if action=='continue':return self.continue_task(r)
        if action=='routing':return self.routing(pid,r.get('station'),r.get('candidates'),r.get('automatic'))
        if action=='start-production' and self.production:return self.production.start(r)
        if action=='retry-production' and self.production:return self.production.retry(r)
        if action=='answer-question' and self.production:return self.production.answer_question(r)
        raise ValueError('Unknown station-control action.')
