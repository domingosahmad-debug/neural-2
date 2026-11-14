"""Durable, event-driven native production. No model polling or implicit approval.

Only validated current completion events advance a run. Technical proof, model
criticism and human acceptance are separate records. Unknown execution blocks.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Event
from uuid import uuid4
import copy
import hashlib
import json
import time

from control import now
from providers import save

PHASES = ('scout', 'plan', 'plan_review', 'prototype', 'prototype_review', 'build', 'render', 'harsh_review', 'goldfish_review')
STATIONS = dict(scout='Plan', plan='Director', plan_review='Plan', prototype='Edit', prototype_review='Review', build='Edit', render='Deliver',
                harsh_review='Review', goldfish_review='Review', repair='Edit')
CRITERIA = ('reference_fidelity', 'shot_variety', 'motion_flow', 'typography',
            'dialogue_timing', 'music_continuity', 'framing', 'ending')
SUPERVISOR_PHASES = ('plan','plan_review','prototype_review','harsh_review','goldfish_review')
RESERVED_DIRECTORS = ('opus','gpt-6.1-sol','gpt-6-sol','astra')

def director_only(model):
    value=model.lower()
    return value in RESERVED_DIRECTORS or 'opus' in value or 'astra' in value

TASKS = {
    'scout': 'Use subtitle_extract for embedded text dialogue and music_locate for reference-to-full-song offset search (verify two separated windows). audio_alignment is a near-synchronous exact-waveform verification tool, not a full-song search; a failed unmatched waveform comparison is diagnostic, never proof the song is wrong. Existing accepted source clocks remain valid evidence. Do not repeat identical failed comparisons. Prepare bounded real source/reference/song evidence for the director, using media tools and existing caches. Read the accepted reference record in the brief. Probe actual source clocks, extract useful timestamped stills, prepare dialogue/subtitle and song-range evidence. Write a scout manifest with actual artifact paths and verification limits. Do not invent shots, words, measurements, playback or listening. Do not mutate AE or build. Long media work: return waiting with exact waitMedia IDs and stop inference; completion events continue this phase. Return complete with artifacts once evidence is ready for the director.',
    'plan': 'When a worker returns completed preparation, YOU must inspect the actual images and lock source ranges and picture coverage. Do not send the worker an unresolved director selection. Use the existing dense scout manifests rather than request another whole sweep. If specific mechanical evidence is genuinely missing, outcome repair with handoffTo scout, actual artifact paths and exact bounded instructions transfers preparation to a worker automatically. Word-level refinements/native font bounds remain worker checks with a feasible method; no invented listening required. Read the current brief and installed workflow. Inspect real source/reference evidence using local media tools. Write a revision-bound blueprint JSON with exact source clocks, quote/speaker/caption links, measured reference curves/music range, distinct shot decisions, native effects ownership and ending. Do not invent measurements. Return production.expect {width,height,frames,fps,audio:true}, production.blueprint (artifact path), artifacts, and outcome complete only when the blueprint is ready for independent critique.',
    'plan_review': 'Fresh Goldfish plan review. Read the actual blueprint and source/reference evidence. Criticize repetition, wrong music clocks, incomplete dialogue, invented graphs, unreadable or misplaced type and unsupported execution methods. Return outcome complete only with evidence-backed PASS; otherwise repair and actionable issues. Do not edit AE or rubber-stamp the plan. Review feasibility at this stage: the render does not exist yet. Explicitly assigned build checks (font readback, real caption bounds, speaker verification, per-word alignment and frame-based crop refinement) and post-render checks (crossfade, last-frame picture, decode) are downstream acceptance gates, not missing finished-plan evidence. A plan can pass with these checks still pending if it specifies a feasible method, owner, evidence and failure response; this never marks those checks passed or waives final verification. Block only on a concrete planning defect or unresolved human decision that prevents a valid build. Use the current recorded human decisions and applicable accepted workflow; do not invent additional approval requirements for routine authorized saves or established caption policy.',
    'prototype': 'If saved completed preparation requires director selections, return outcome repair, handoffTo plan, artifacts and concrete issues; the coordinator dispatches the director. Do not return blocked for an internal director task. Complete any already submitted native/media work first. Downstream quote/crop/font refinement belongs to the worker when a feasible approved method exists; list unavailable listening honestly. Build only a representative editable passage in the fresh scoped AEP from the reviewed blueprint, before scaling to the whole edit. Include the intro retention treatment and hero/support caption proof plus 2-3 new-episode body shots and a difficult motion transition. Use exactly two Z Dist keys with measured native easing, one zoom owner and nested retiming. Render a bounded playable proof, extract timestamped actual frames and native property evidence, and write a manifest linking those assets. Do not build the entire edit yet. Return complete with production.aep, compId, compName, production.render (the actual bounded playable proof) and artifacts including actual rendered frame PNGs, only with matching saved native receipts. Pending render/media work: return waiting with exact identities and stop inference.',
    'prototype_review': 'Fresh read-only Goldfish representative-proof review BEFORE full build. Read the reviewed blueprint, accepted method record, actual proof images, native curve/type/source evidence and proof manifest. Challenge face centering, shot choice, blur duration, two-key zoom easing, caption hierarchy/animation and intro hook against the human brief. Review only the representative passages declared in this proof manifest. Absent full-edit scenes, the final ending and censorship when the selected quote contains no profanity are downstream full-build/final-review checks, not prototype repair triggers. Record them as pending without marking them passed or waiving final verification. Reuse matching unchanged proof; for a repaired passage check the diagnosed changed region and affected dependencies rather than demand another unchanged whole prototype. Do not accept paths without seeing available images or invent playback/listening. Return complete with evidence only when the representative method is ready to scale; return repair with specific evidence-backed defects in the scoped prototype. Unavailable listening/playback remains explicitly unperformed, never an automatic repair trigger. No native or media work.',
    'build': 'Build the complete editable After Effects project from the reviewed blueprint using only guarded Neural native tools and installed TFX methods. Preserve source clocks, one music section, full dialogue, measured curves, scene variety and editable type. Bootstrap a new scoped AEP if needed; never reuse the paused edit. Inspect first, exact live guards on every mutation. Save the new AEP under the project root. Return production.artifacts, production.aep (the saved AEP path), production.compId and production.compName, and complete only with matching native command/report evidence.',
    'render': 'Render the entire current edit using guarded native tools. Use an installed output template and preserve render-queue state. Create a playable MP4 review copy through media tools if master is MOV. Return production.render (absolute final MP4), expect {width,height,frames,fps,audio:true}, artifacts, and native result evidence. Never pass an old render as current. Long work: return waiting plus waitNative/waitMedia, then stop inference; completion events resume you.',
    'harsh_review': 'Fresh independent harsh review of this exact complete render and technical evidence. Use the supplied actual frame evidence, native state, quote/music ledgers and measured reports. Critique all required criteria individually. Read images through read_artifact; do not claim playback/listening when unavailable. Return production.criteria mapping each required name to {pass:boolean,evidence:[actual artifact paths],notes:string}; outcome repair for an evidence-backed defect or missing machine-checkable required evidence, complete only if ready for the human. Record unavailable normal-speed playback/listening as unperformed for human review, never as an automatic repair trigger. Do not edit AE.',
    'goldfish_review': 'Fresh independent Goldfish/EGM review of the exact full render; do not read or copy the harsh reviewer verdict. Challenge the source/clock/scene/type/motion/ending decisions against the human brief. Inspect actual provided evidence. Same criteria contract; Any evidence-backed defect or missing machine-checkable required evidence means repair. Record unavailable normal-speed playback/listening as unperformed for human review, never as an automatic repair trigger. No native mutations.',
    'repair': 'Repair ONLY the diagnosed failed regions in the current project. Preserve successful work and exact source/quote/music clocks. Read the saved issue list, real evidence and native snapshot first. Guard every native mutation and save the pinned project.aep in place through the gateway; each save has its own gateway report, and a separate AEP file is neither required nor possible. Missing listening, word-level alignment or full-speed playback tools are verification limits to list in issues, not blockers: once the diagnosed regions are repaired and saved, return complete with native result/report evidence; next step is a new full render and independent reviews.'}


def validate_phase_candidates(phase_candidates):
    from providers_engine.transport import validate
    if phase_candidates is not None:
        if not isinstance(phase_candidates,dict) or set(phase_candidates)!=set(PHASES)|{'repair'}:
            raise ValueError('Explicit role routing requires every production phase, including repair.')
        for phase, choices in phase_candidates.items():
            if not isinstance(choices,list) or not 1<=len(choices)<=8:
                raise ValueError('Each phase needs 1 to 8 explicit candidates.')
            identities=set()
            for choice in choices:
                validate(choice.get('route'),choice.get('model'),choice.get('effort'))
                identity=(choice['route'],choice['model'])
                if identity in identities:raise ValueError('Duplicate phase candidate.')
                identities.add(identity)
                if phase not in SUPERVISOR_PHASES and director_only(choice['model']):
                    raise ValueError('Reserved directors cannot build, render, repair or prepare media.')
        phase_candidates=copy.deepcopy(phase_candidates)
    return phase_candidates


class Production:
    def __init__(self, control, services):
        self.control, self.services = control, services
        self.root = control.root.resolve()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='production-events')
        self.watchers = ThreadPoolExecutor(max_workers=2, thread_name_prefix='production-completion-watch')
        self.closed = Event()
        self.service_url = self.service_token = None
        with control.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS production_runs(id TEXT PRIMARY KEY,project TEXT,body TEXT NOT NULL)')

    def rows(self, project=None):
        with self.control.connection() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM production_runs' + (' WHERE project=?' if project else '') + ' ORDER BY rowid', (project,) if project else ())]

    def persist(self, db, run):
        db.execute('INSERT INTO production_runs VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (run['id'], run['project'], json.dumps(run)))

    def status(self, project):
        rows = self.rows(project)
        return rows[-1] if rows else None

    def configured(self):
        path = self.root/'data/production-commission.json'
        try:
            proof = json.loads(path.read_text(encoding='utf-8'))
            return proof.get('passed') is True and proof.get('nativeGateway') is True and proof.get('toolHost') is True and proof.get('eventRecovery') is True
        except (OSError, ValueError): return False

    def start(self, request):
        pid, candidates = request.get('project'), request.get('candidates')
        from providers_engine.transport import validate
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 8:
            raise ValueError('Choose a director and bounded fallback candidates.')
        for c in candidates: validate(c.get('route'), c.get('model'), c.get('effort'))
        reviewers = request.get('reviewers') or [candidates[-1], candidates[0]]
        if len(reviewers) != 2 or (reviewers[0]['route'], reviewers[0]['model']) == (reviewers[1]['route'], reviewers[1]['model']):
            raise ValueError('Choose two distinct capable review models; Goldfish is independent.')
        for c in reviewers: validate(c.get('route'), c.get('model'), c.get('effort'))
        phase_candidates=validate_phase_candidates(request.get('phaseCandidates'))
        commissioning = request.get('commissioning') is True
        if not self.configured() and not commissioning:
            raise ValueError('The installed production route has not passed live commissioning yet.')
        target = self.root/'data/projects'/str(pid)
        if not target.resolve().is_relative_to(self.root/'data/projects'): raise ValueError('Invalid project root.')
        with self.control.lock, self.control.connection() as db:
            db.execute('BEGIN IMMEDIATE'); projects = self.control.projects(db); p = projects.get(pid)
            if not p or p.get('productionControl', {}).get('paused'): raise ValueError('Select a NEW, unpaused production project.')
            if self.status(pid): raise ValueError('This project already has a durable production run. Continue its saved task.')
            if any(j['status'] in ('QUEUED','RUNNING','UNKNOWN','CANCELLING') for j in self.control.providers.status()):
                raise ValueError('Reconcile active or uncertain work before admitting native production.')
            native = self.control.native.status(); owner = native.get('owner')
            if native['unresolved'] or not owner or owner['id'] != request.get('nativeLeaseId') or owner['project'] != pid:
                raise ValueError('An exact settled native lease for this project is required.')
            run = dict(id=uuid4().hex, project=pid, revision=p['revision'], generation=p.get('productionControl',{}).get('generation',0),
                       state='READY', phase='scout' if phase_candidates else 'plan', phaseCandidates=phase_candidates, created=now(), candidates=candidates, reviewers=reviewers, nativeLeaseId=owner['id'],
                       projectRoot=str(target.resolve()), history=[], issues=[], repairs=0, maxRepairs=3, commissioning=commissioning,
                       aeProjectPath=str((target/'project.aep').resolve()), compId=None, compName='NEURAL_MASTER',
                       artifactRoots=request.get('artifactRoots',[]), consumedEvents=[])
            target.mkdir(parents=True, exist_ok=True)
            self.persist(db,run)
        self.dispatch(run['id'])
        return self.status(pid)

    def _load(self, identity, db):
        row = db.execute('SELECT body FROM production_runs WHERE id=?',(identity,)).fetchone()
        if not row: raise ValueError('Unknown production run.')
        return json.loads(row[0])

    def _current(self, run, db):
        p = self.control.projects(db).get(run['project'])
        if not p or p['revision'] != run['revision'] or p.get('productionControl',{}).get('generation',0) != run['generation'] or p.get('productionControl',{}).get('paused'):
            raise ValueError('Production paused or superseded; no next action admitted.')
        return p

    @staticmethod
    def review_candidates(run, phase, candidates):
        if phase != 'goldfish_review':return candidates
        harsh=next((h for h in reversed(run['history']) if h.get('phase')=='harsh_review' and h.get('result',{}).get('outcome')=='complete'),None)
        if not harsh:return candidates
        # Model identity, not merely a fresh session, preserves independent reviewers.
        return [c for c in candidates if c['model']!=harsh.get('model')]

    def dispatch(self, identity):
        with self.control.lock, self.control.connection() as db:
            db.execute('BEGIN IMMEDIATE'); run=self._load(identity,db); p=self._current(run,db)
            if run['state'] != 'READY': return
            phase=run['phase']; explicit=run.get('phaseCandidates')
            if explicit:
                choices=self.review_candidates(run,phase,explicit[phase])
                if phase not in SUPERVISOR_PHASES and any(director_only(c['model']) for c in choices):
                    raise ValueError('Reserved director found in worker routing; nothing dispatched.')
                candidate=choices[0] if choices else None
                review_candidates=choices
            else:
                candidate=run['reviewers'][0 if phase=='harsh_review' else 1] if phase in ('harsh_review','goldfish_review','plan_review') else run['candidates'][0]
                review_candidates=self.review_candidates(run,phase,[candidate]+[c for c in run['candidates'] if c!=candidate])
            if not review_candidates:
                run.update(state='BLOCKED',error='No distinct independent Goldfish reviewer is available.',updated=now());self.persist(db,run);return
            if phase=='goldfish_review':candidate=review_candidates[0]
            aid=uuid4().hex; station=STATIONS[phase]
            template=dict(schema='neural.station-result.v2',project=p['id'],revision=p['revision'],station=station,assignmentId=aid,summary='')
            previous=[r for r in run['history'] if r.get('result') and not (phase=='goldfish_review' and r['phase']=='harsh_review')]
            task=TASKS[phase]+('\nROLE: supervisor. Direct and review only. Read prepared artifacts and actual images; write the blueprint/verdict. Delegate mechanical preparation to the scout phase; media submission and native mutation are disabled.' if explicit and phase in SUPERVISOR_PHASES else '')+'\nRequired criteria: '+', '.join(CRITERIA)+('\nproduction.criteria is mandatory for every outcome, repair included: one {pass,evidence,notes} entry per required name (pass true with a note when a criterion does not apply). evidence is a list of file paths you read (or one sentence describing them). Normal-speed playback and listening are reserved for the human review that follows; record them as not performed, never as a defect or a reason for repair.' if phase in ('harsh_review','goldfish_review') else '')
            if run.get('continuationContext'):
                task += '\nContinuation checkpoint (reuse settled evidence; never replay unknown native work):\n'+run['continuationContext']
            packet=dict(schema='neural.station-task.v2',project=p['id'],projectName=p.get('name'),revision=p['revision'],station=station,assignmentId=aid,
                        model=candidate['model'],task=task,brief=p['brief'],status='external handoff',resultTemplate=template,
                        requiredCapabilities=['neural_tools'],toolMode='production',productionRun=run['id'],productionPhase=phase,
                        controlGeneration=run['generation'],logicalTaskId=aid,contextMode='fresh_review' if phase in SUPERVISOR_PHASES and phase!='plan' else 'ordinary',
                        checkpoint={'history':previous,'issues':run['issues'],'expect':run.get('expect'),'blueprint':run.get('blueprint'),'render':run.get('render'),'prototypeRender':run.get('prototypeRender'),'technical':run.get('technical')},
                        workflowRoot=str(self.root/'knowledge'),projectRoot=run['projectRoot'],sourceLinks=p.get('links',[]),
                        productionContract={'phase':phase,'handoffTo':'For settled internal prerequisites use outcome repair, handoffTo plan (scout/prototype only) or scout (plan only), concrete issues and existing evidence. Coordinator dispatches that owner; never waive review/native gates.', 'outcomes':['complete','repair','blocked','waiting','needs_input'],'criteria':list(CRITERIA),'artifacts':'Existing absolute or project-relative files; no invented evidence.',
                                            'humanDecision':'Only when the human brief leaves a necessary choice unresolved, return outcome needs_input and question {text,choices:[2Ã¢â‚¬â€œ6 distinct short answers]}. Explain the actual choice, not a technical error. Read previous recorded answers first. Finish/reconcile submitted native actions before asking; do not ask permission for routine authorized work.'})
            for r in p['assignments'].values():
                if r['station']==station and r['revision']==p['revision'] and r['status']!='superseded': r['status']='superseded'
            p['assignments'][aid]=packet
            rid='production:'+run['id']+':'+aid
            step=dict(id=uuid4().hex,requestId=rid,project=p['id'],revision=p['revision'],station=station,model=candidate['model'],route=candidate['route'],effort=candidate['effort'],state='INTENT',created=now(),packet=copy.deepcopy(packet),generation=run['generation'])
            run.update(state='DISPATCHING',assignmentId=aid,requestId=rid,station=station,updated=now())
            base=review_candidates if explicit or phase in SUPERVISOR_PHASES else run['candidates']
            listed={(c['route'],c['model']) for c in base}
            # Human-configured extra fallbacks for this station survive dispatch; run order stays first.
            extra=[] if explicit else [c for c in p.get('productionControl',{}).get('routing',{}).get(station,{}).get('candidates',[]) if (c.get('route'),c.get('model')) not in listed]
            p.setdefault('productionControl',{}).setdefault('routing',{})[station]={'automatic':True,'candidates':(base+extra)[:8]}
            self.control.step_save(db,step);self.control.save_projects(db,{**self.control.projects(db),p['id']:p});self.persist(db,run)
        try: self.control.dispatch_intent(step)
        except Exception as e: self.block(identity,str(e))

    def invalidate(self, project=None):
        """Revoke every outstanding per-job native authority BEFORE pause/revision/lease changes."""
        for path in (self.root/'data/projects').glob('*/.authority/*.json'):
            try:
                row=json.loads(path.read_text(encoding='utf-8'))
                if project is None or row.get('project')==project:
                    row['paused']=True;save(path,row)
            except (OSError,ValueError): raise ValueError('Cannot safely revoke native authority: '+str(path))

    def prepare(self, row, packet, folder):
        if packet.get('toolMode')!='production': return packet
        with self.control.lock, self.control.connection() as db:
            run=self._load(packet['productionRun'],db);p=self._current(run,db)
            assignment=p['assignments'].get(row['assignmentId'])
            if not assignment or assignment.get('status')=='superseded' or assignment['model']!=row['model']: raise ValueError('Production task is no longer current.')
            owner=self.control.native.status().get('owner') or {}
            if owner.get('id')!=run['nativeLeaseId'] or owner.get('project')!=p['id']: raise ValueError('Native lease changed; no tool host started.')
            role='supervisor' if packet['productionPhase'] in SUPERVISOR_PHASES else 'worker'
            if run.get('phaseCandidates') and role=='worker' and director_only(row['model']):
                raise ValueError('Reserved director cannot receive worker tools.')
            mutation=packet['productionPhase'] in ('prototype','build','render','repair')
            authority=dict(project=p['id'],revision=p['revision'],generation=run['generation'],paused=False,nativeLeaseId=owner['id'],nativeProject=owner['project'],jobId=row['id'],assignmentId=row['assignmentId'])
            authority_path=Path(run['projectRoot'])/'.authority'/(row['id']+'.json')
            scope=dict(schema='neural.production-scope.v1',root=str(self.root),db=str(self.control.db.resolve()),**authority,
                       model=row['model'],station=row['station'],projectRoot=run['projectRoot'],artifactRoots=run['artifactRoots']+[str(self.root/'knowledge')],
                       productionRole=role if run.get('phaseCandidates') else 'legacy',allowMutation=mutation,allowBootstrap=mutation and run['phase'] in ('prototype','build'),productionCommissioned=self.configured() or run['commissioning'],
                       aeProjectPath=run['aeProjectPath'],compId=run.get('compId'),compName=run.get('compName'),
                       authorityPath=str(authority_path.resolve()),serviceURL=self.service_url,serviceToken=self.service_token)
            if run.get('technicalJob'):scope['artifactRoots'].append(str(self.root/'data/local-ops/jobs'/run['technicalJob']))
            save(authority_path,authority);save(folder/'scope.json',scope)
            packet=copy.deepcopy(packet);packet['productionScope']=str((folder/'scope.json').resolve())
            packet['productionCommissioned']=scope['productionCommissioned']
            run.update(state='WORKING',jobId=row['id'],assignmentId=row['assignmentId'],model=row['model'],error=None,updated=now());self.persist(db,run)
        return packet

    def notify(self, row):
        if not self.closed.is_set():self.pool.submit(self.terminal,copy.deepcopy(row))

    def steer(self, request):
        """Fence old work now; replan once its exact execution boundary settles."""
        text=request.get('text');rid=request.get('requestId');pid=request.get('project')
        if not isinstance(text,str) or not text.strip() or len(text)>12000 or not isinstance(rid,str) or not 1<=len(rid)<=200:
            raise ValueError('Provide the new direction and a persistent request ID.')
        phase_candidates=validate_phase_candidates(request.get('phaseCandidates'))
        with self.control.lock,self.control.connection() as db:
            db.execute('BEGIN IMMEDIATE');run=self.status(pid)
            if not run:raise ValueError('No production run exists. Save a notebook note or start a new project.')
            p=self._current(run,db)
            if request.get('revision')!=p['revision']:raise ValueError('Direction belongs to a different project revision.')
            previous=next((s for s in run.get('steeringHistory',[]) if s['requestId']==rid),None)
            if previous:
                if previous['text']!=text or previous.get('phaseCandidates')!=phase_candidates:raise ValueError('Request ID already belongs to a different direction or routing policy.')
                return run
            self.invalidate(pid)
            ctl=p.setdefault('productionControl',{});ctl['generation']=ctl.get('generation',0)+1
            scopes=set(run.get('steering',{}).get('scopes',[]))
            if run.get('waitScope'):scopes.add(run['waitScope'])
            for job in self.control.providers.status():
                if job.get('project')==pid and job.get('revision')==p['revision']:
                    scope=self.root/'data/provider-jobs'/job['id']/'scope.json'
                    if scope.is_file():scopes.add(str(scope.resolve()))
            entry=dict(requestId=rid,text=text,created=now(),generation=ctl['generation'],previousPhase=run['phase'],previousState=run['state'],phaseCandidates=phase_candidates)
            run.setdefault('steeringHistory',[]).append(copy.deepcopy(entry))
            run['history'].append(dict(phase=run['phase'],steeringCheckpoint={k:copy.deepcopy(run.get(k)) for k in ('assignmentId','jobId','blueprint','render','technical','expect','waitNative','waitMedia')},at=now()))
            run.update(state='STEERING',generation=ctl['generation'],steering=dict(entry,scopes=sorted(scopes)),error='Applying your direction; waiting for prior provider/native work to settle.',updated=now())
            run['continuationContext']=run.get('continuationContext','')+'\nNEW OPERATOR DIRECTION (overrides conflicting older plan; reuse completed evidence, do not replay native actions):\n'+text
            p['messages'].append(dict(role='operator',revision=p['revision'],text=text,requestId=rid))
            for assignment in p['assignments'].values():
                if assignment.get('revision')==p['revision'] and assignment.get('status')!='superseded':assignment.update(status='superseded',supersededReason='New operator direction '+rid)
            self.control.save_projects(db,{**self.control.projects(db),pid:p});self.persist(db,run)
        self.services.signal();self.watchers.submit(self.steer_boundary,run['id'],rid)
        return run

    def settle_steering(self, identity, rid):
        """One deterministic boundary check. False means a real job is pending."""
        with self.control.lock,self.control.connection() as db:
            run=self._load(identity,db);self._current(run,db)
            if run['state']!='STEERING' or run.get('steering',{}).get('requestId')!=rid:return True
            jobs=[j for j in self.control.providers.status() if j.get('project')==run['project']]
            if any(j['status']=='UNKNOWN' or j.get('conversation_blocked') for j in jobs):raise ValueError('Direction saved, but a prior provider outcome requires exact reconciliation; nothing replayed.')
            if any(j['status'] in ('QUEUED','RUNNING','CANCELLING') for j in jobs):return False
            if self.control.native.status()['unresolved']:return False
            from production_gateway import reconcile_scopes
            receipts=reconcile_scopes(run['steering']['scopes'])
            self.settled_native_boundary(run)
            if hasattr(self.services,'engine'):
                if any(j.get('project')==run['project'] and j['status'] in ('QUEUED','RUNNING','CANCELLING') for j in self.services.engine.snapshot()['jobs']):return False
            run['history'].append(dict(phase=run['phase'],steeringApplied=rid,boundaryEvidence=receipts,repairAttempts=copy.deepcopy(run.get('repairAttempts',{})),totalRepairs=run.get('repairs',0),prerequisiteHandoffs=run.pop('prerequisiteHandoffs',[]),at=now()))
            run['repairAttempts']={}  # Settled operator direction is new evidence: handoff budget restarts, history keeps the old ledger.
            for field in ('assignmentId','jobId','blueprint','render','technical','technicalJob','expect','waitNative','waitMedia','waitScope','question','state_before_block'):
                run.pop(field,None)
            if run['steering'].get('phaseCandidates') is not None:run['phaseCandidates']=copy.deepcopy(run['steering']['phaseCandidates'])
            run['steering']['appliedAt']=now();run.update(phase='scout' if run.get('phaseCandidates') else 'plan',state='READY',error=None,updated=now());self.persist(db,run)
        self.services.signal();self.dispatch(identity);return True

    def steer_boundary(self, identity, rid):
        """Local watcher only; never schedules a model while any old job is active."""
        try:
            deadline=time.monotonic()+65*60
            while not self.closed.is_set():
                try:
                    if self.settle_steering(identity,rid):return
                except ValueError as error:
                    with self.control.connection() as db:
                        run=self._load(identity,db)
                        try:self._current(run,db)
                        except ValueError:return  # Human pause/supersession wins.
                    raise error
                if time.monotonic()>deadline:raise ValueError('Direction saved; safe boundary did not settle. Reconcile exact pending work; no replay.')
                self.closed.wait(.5)
        except Exception as error:
            with self.control.lock,self.control.connection() as db:
                run=self._load(identity,db)
                try:self._current(run,db)
                except ValueError:return
                if run['state']!='STEERING' or run.get('steering',{}).get('requestId')!=rid:return
                run.update(state='BLOCKED',error=str(error),updated=now());self.persist(db,run)
            self.services.signal()

    def block(self, identity, error):
        with self.control.lock,self.control.connection() as db:
            run=self._load(identity,db)
            if run['state']!='BLOCKED':run['state_before_block']=run['state']
            run.update(state='BLOCKED',error=str(error),updated=now());self.persist(db,run)
        self.services.signal()

    def settled_native_boundary(self, run):
        """Bridge completion alone cannot settle a gateway command without its report."""
        native=self.control.native.status();owner=native.get('owner') or {}
        if native['unresolved'] or owner.get('id')!=run['nativeLeaseId'] or owner.get('project')!=run['project']:
            raise ValueError('An exact settled native lease for this project is required.')
        registry=Path(run['projectRoot'])/'.neural-gateway'/'registry.json'
        from production_gateway import unresolved
        if registry.is_file() and unresolved(run['projectRoot']):
            raise ValueError('An unsettled native gateway request exists; reconcile its exact result before continuing.')

    def artifact(self, run, value):
        if not isinstance(value,str):raise ValueError('Artifact path required.')
        path=Path(value);path=path if path.is_absolute() else Path(run['projectRoot'])/path
        path=path.resolve()
        roots=[Path(run['projectRoot']).resolve()]
        if run.get('technicalJob'):roots.append((self.root/'data/local-ops/jobs'/run['technicalJob']).resolve())
        # Evidence a reviewer produced with its own mechanical job counts when that job belongs to this project.
        jobs=(self.root/'data/local-ops/jobs').resolve()
        if path.is_relative_to(jobs) and len(path.relative_to(jobs).parts)>1:
            job=jobs/path.relative_to(jobs).parts[0]
            try:
                if json.loads((job/'JOB.json').read_text(encoding='utf-8')).get('project')==run['project']:roots.append(job)
            except (OSError,ValueError):pass
        if not any(path.is_relative_to(r) for r in roots) or not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing or out-of-scope production evidence: '+str(path))
        return path

    def known_pending_native(self, row, run):
        """Recover an omitted waiting result only from this job's exact live receipt.

        UNKNOWN, changed commands and missing scopes are never inferred as pending.
        No submission or replay occurs here.
        """
        scope=self.root/'data/provider-jobs'/row['id']/'scope.json'
        registry=Path(run['projectRoot'])/'.neural-gateway'/'registry.json'
        if not scope.is_file() or not registry.is_file():return None
        from production_gateway import ProductionGateway, connect
        gateway=ProductionGateway(scope,reconciliation_only=True)
        with connect(gateway.database) as db:
            pending=[json.loads(raw) for raw, in db.execute('SELECT body FROM requests')]
        pending=[r for r in pending if r.get('jobId')==row['id'] and r.get('scope')==gateway.scope_hash and r.get('kind')!='media' and r.get('state')=='SUBMITTED']
        if len(pending)!=1:return None
        result=gateway.ae_status(pending[0]['requestId'])
        return result['requestId'] if result['state']=='SUBMITTED' else None

    def terminal(self,row):
        matches=[r for r in self.rows(row.get('project')) if r.get('assignmentId')==row.get('assignmentId') or r.get('technicalJob')==row.get('id')]
        if not matches:return
        run=matches[-1]
        if run['state']=='STEERING':
            self.watchers.submit(self.steer_boundary,run['id'],run['steering']['requestId']);return
        try:
            with self.control.lock,self.control.connection() as db:
                run=self._load(run['id'],db);self._current(run,db)
                if run['state']=='STEERING':return  # A direction may fence this event while it waits for the lock.
                if row['id'] in run['consumedEvents']:return
                if row['id']==run.get('technicalJob'):
                    if run['state']!='WAIT_TECHNICAL':return
                    if row['status']!='COMPLETED':
                        decode=next((s for s in row.get('steps',[]) if s['id']=='decode'),{})
                        audio=next((s.get('report',{}) for s in row.get('steps',[]) if s['id']=='audio'),{})
                        if row['status']!='FAILED' or decode.get('status')!='COMPLETED' or audio.get('clipped_samples',0)<=0 or run.get('technicalRecoveries',0)>=2:
                            raise ValueError('Full-render technical verification failed: '+str(row.get('error')))
                        run['technicalRecoveries']=run.get('technicalRecoveries',0)+1
                        run.setdefault('technicalFailures',[]).append(copy.deepcopy(row))
                        run['continuationContext']=run.get('continuationContext','')+'\nTECHNICAL AUDIO RECOVERY: Exact full-render decode/geometry/frame count/cadence passed; audio_measure found '+str(audio['clipped_samples'])+' PCM ceiling samples. Read technical job '+row['id']+' actual reports. Use media review_copy with audio_gain_db=-2 (or further measured headroom on the second bounded correction), same dimensions/cadence/frame_limit and original completed native master if available; never rerender AE for delivery headroom. Do not claim gain repairs baked-in source distortion or listening. Return corrected render with exact provenance; full technical gates and independent critique must run again. No gates waived.'
                        run.update(phase='render',state='READY',error=None)
                    else:
                        audio=next(s['report'] for s in row['steps'] if s['id']=='audio')
                        if audio.get('rms',0)<=0 or audio.get('clipped_samples',0)>0:raise ValueError('Full render is silent or clipped.')
                        run.update(technical=row,phase='harsh_review',state='READY')
                    run['consumedEvents'].append(row['id']);self.persist(db,run)
                    advance=True
                else:
                    if row['status']=='FAILED' and self.control.exhausted(row):
                        # The quota event may arrive while a native command is
                        # still finishing. Resume routing at that settled boundary;
                        # never leave a dead provider labelled WORKING forever.
                        run.update(state='WAIT_QUOTA_BOUNDARY',error='Provider subscription exhausted; reconciling native boundary before fallback.',updated=now())
                        self.persist(db,run)
                        self.watchers.submit(self.quota_boundary,run['id'],copy.deepcopy(row))
                        return
                    if row['status']!='COMPLETED':raise ValueError('Provider did not complete: '+str(row.get('error') or row['status']))
                    from station_results import decode
                    data=decode(self.control.providers.result(row['id']));result=data.get('production')
                    if not isinstance(result,dict) or result.get('phase')!=run['phase']:raise ValueError('Missing exact production phase result.')
                    outcome=result.get('outcome')
                    if outcome in ('complete','repair','blocked'):
                        pending=self.known_pending_native(row,run)
                        if pending:
                            # Preserve the worker's report; it is not completion proof.
                            result=copy.deepcopy(result)
                            result['deferredOutcome']=outcome
                            result.update(outcome='waiting',waitNative=pending)
                            outcome='waiting'

                    if outcome=='needs_input':
                        question=result.get('question')
                        if not isinstance(question,dict):raise ValueError('Human input requires a structured question.')
                        text=question.get('text');choices=question.get('choices')
                        if not isinstance(text,str) or not text.strip() or len(text)>2000 or not isinstance(choices,list) or not 2<=len(choices)<=6 or any(not isinstance(c,str) or not c.strip() or len(c)>300 for c in choices) or len(set(choices))!=len(choices):
                            raise ValueError('Human input requires a clear question and 2Ã¢â‚¬â€œ6 distinct bounded choices.')
                        self.settled_native_boundary(run)
                        run.update(state='WAIT_HUMAN',question=dict(id=uuid4().hex,text=text,choices=choices,created=now(),phase=run['phase'],jobId=row['id']),error=None)
                        run['history'].append(dict(phase=run['phase'],jobId=row['id'],result=result,at=now()))
                        run['consumedEvents'].append(row['id']);self.persist(db,run)
                        db.commit()  # Subscribers must observe the committed question.
                        self.services.signal();return
                    if outcome=='waiting':
                        native_id=result.get('waitNative');media_ids=result.get('waitMedia',[])
                        if not native_id and not media_ids:raise ValueError('Waiting result must name actual submitted native/media work.')
                        if native_id is not None and not isinstance(native_id,str) or not isinstance(media_ids,list) or any(not isinstance(i,str) for i in media_ids):raise ValueError('Invalid pending-work identity.')
                        scope_path=self.root/'data/provider-jobs'/row['id']/'scope.json'
                        run.update(state='WAIT_NATIVE' if native_id else 'WAIT_MEDIA',waitScope=str(scope_path),waitNative=native_id,waitMedia=media_ids,waitStarted=time.time())
                        run['history'].append(dict(phase=run['phase'],jobId=row['id'],result=result,at=now()))
                        run['consumedEvents'].append(row['id']);self.persist(db,run)
                        db.commit()  # Watchers must see the durable waiting identity.
                        self.watchers.submit(self.watch,run['id']);self.services.signal();return
                    if outcome not in ('complete','repair'):raise ValueError('Worker blocked: '+str(result.get('issues') or data.get('summary')))
                    artifacts=[str(self.artifact(run,a)) for a in result.get('artifacts',[])]
                    if not artifacts:raise ValueError('No actual phase evidence was supplied.')
                    phase=run['phase'];run['history'].append(dict(phase=phase,jobId=row['id'],assignmentId=row['assignmentId'],model=row['model'],result=result,artifacts=artifacts,at=now()))
                    run['consumedEvents'].append(row['id'])
                    if phase in ('harsh_review','goldfish_review'):
                        criteria=result.get('criteria',{})
                        if not criteria and outcome=='repair' and result.get('issues'):criteria={}
                        elif set(criteria)!=set(CRITERIA):raise ValueError('Review omitted required criteria.')
                        for c in criteria.values():
                            if type(c.get('pass')) is not bool or not c.get('evidence'):raise ValueError('Review criterion lacks a verdict or evidence.')
                            for path in ([] if isinstance(c['evidence'],str) else c['evidence']):
                                # A sentence describing evidence is accepted; anything that is or claims to be a file is checked.
                                prose=isinstance(path,str) and ' ' in path.strip() and not Path(path).is_absolute() and not (Path(run['projectRoot'])/path).exists() if isinstance(path,str) and not any(ch in path for ch in '<>|?*"') else isinstance(path,str)
                                if not prose:self.artifact(run,path)
                        if any(not c['pass'] for c in criteria.values()):outcome='repair'
                    if outcome=='repair' and result.get('handoffTo') and phase in ('plan_review','prototype_review','harsh_review','goldfish_review'):
                        # Reviews cannot reroute ownership; their repair verdict still enters the normal repair -> re-review loop.
                        result=dict(result,ignoredHandoffTo=result['handoffTo']);result.pop('handoffTo')
                    if outcome=='repair' and result.get('handoffTo'):
                        target=result['handoffTo']
                        if target not in {'scout':('plan',),'plan':('scout',),'prototype':('plan',)}.get(phase,()):
                            raise ValueError('Invalid prerequisite owner handoff; no review gate bypass allowed.')
                        self.settled_native_boundary(run)
                        if hasattr(self.services,'engine') and any(j.get('project')==run['project'] and j['status'] in ('QUEUED','RUNNING','CANCELLING') for j in self.services.engine.snapshot()['jobs']):
                            raise ValueError('Prerequisite handoff requires settled media work; return waiting with exact IDs.')
                        issues=result.get('issues')
                        if not isinstance(issues,list) or not issues or any(not isinstance(i,str) or not i.strip() for i in issues):
                            raise ValueError('Prerequisite handoff needs concrete owner instructions.')
                        import hashlib
                        identity=hashlib.sha256(json.dumps([phase,target,issues,[(a,hashlib.sha256(Path(a).read_bytes()).hexdigest()) for a in artifacts]],sort_keys=True).encode()).hexdigest()
                        handoffs=run.setdefault('prerequisiteHandoffs',[])
                        if any(h['identity']==identity for h in handoffs) or len(handoffs)>=6:
                            raise ValueError('Repeated prerequisite handoff without new evidence; diagnose the exact unresolved owner task.')
                        handoffs.append(dict(identity=identity,source=phase,target=target,artifacts=artifacts,issues=issues,jobId=row['id'],at=now()))
                        run['continuationContext']=run.get('continuationContext','')+'\nINTERNAL OWNER HANDOFF from '+phase+' to '+target+': '+json.dumps(issues)+' Evidence: '+json.dumps(artifacts)+'. Reuse completed work. Complete the assigned decisions/preparation and return normally; subsequent plan/prototype reviews remain mandatory.'
                        run.update(phase=target,state='READY',error=None)
                    elif outcome=='repair':
                        run['issues']+=result.get('issues') or ['Required phase/review gate failed; read its saved criterion evidence.']
                        run['repairs']+=1  # Lifetime telemetry; not a shared budget across unrelated gates.
                        attempts=run.setdefault('repairAttempts',{})
                        attempts[phase]=attempts.get(phase,0)+1
                        if attempts[phase]>run['maxRepairs']:raise ValueError('Repair budget exhausted for '+phase+'; preserved evidence and precise issues require a new diagnosed action, not a loop.')
                        run['phase']='plan' if phase=='plan_review' else 'prototype' if phase in ('prototype','prototype_review') else 'repair'
                    elif phase=='plan':
                        run['blueprint']=str(self.artifact(run,result.get('blueprint')));run['expect']=self.expect(result.get('expect'));run['phase']='plan_review'
                    elif phase in ('prototype','build','repair'):
                        if phase=='prototype':
                            run['prototypeRender']=str(self.artifact(run,result.get('render')))
                            if not any(Path(a).suffix.lower() in ('.png','.jpg','.jpeg','.webp') for a in artifacts):
                                raise ValueError('Representative proof requires actual rendered frame artifacts before review.')
                        proven=self.native_proof(row,run)
                        # A worker that omits the identity fields is completed from the gateway's own report, never guessed.
                        aep=self.artifact(run,result.get('aep') or proven.get('projectPath'));run['aepArtifact']=str(aep)
                        # A saved delivery copy does not change the gateway-pinned
                        # live project that remains open in AE.
                        run['aeProjectPath']=proven.get('projectPath') or run['aeProjectPath']
                        compId=result.get('compId') if isinstance(result.get('compId'),int) else proven.get('compId');compName=result.get('compName') if isinstance(result.get('compName'),str) else proven.get('compName')
                        if not isinstance(compId,int) or not isinstance(compName,str):raise ValueError('Build must identify the saved live comp.')
                        run.update(compId=compId,compName=compName,phase='prototype_review' if phase=='prototype' else 'render')
                    elif phase=='render':
                        self.native_proof(row,run)
                        run['render']=str(self.artifact(run,result.get('render')));run['expect']=self.expect(result.get('expect'))
                        run.update(state='VERIFY_INTENT');self.persist(db,run);advance=False
                    elif phase=='goldfish_review':run.update(state='HUMAN_REVIEW',finished=now());advance=False
                    elif phase=='plan_review':run['phase']='prototype' if run.get('phaseCandidates') else 'build'
                    else:run['phase']=PHASES[PHASES.index(phase)+1]
                    if outcome=='complete':run.setdefault('repairAttempts',{}).pop(phase,None)
                    if phase!='render' and run['state']!='HUMAN_REVIEW':run['state']='READY';advance=True
                    self.persist(db,run)
            if run['state']=='VERIFY_INTENT':self.verify_render(run)
            elif advance:self.dispatch(run['id'])
            self.services.signal()
        except Exception as e:self.block(run['id'],str(e))

    @staticmethod
    def expect(value):
        from fractions import Fraction
        if not isinstance(value,dict) or not all(type(value.get(k)) is int and value[k]>0 for k in ('width','height','frames')) or value.get('audio') is not True:
            raise ValueError('Exact full-render width/height/frame count/FPS and audio=true are required.')
        if Fraction(str(value.get('fps',0)))<=0:raise ValueError('Exact positive FPS required.')
        return value

    def native_proof(self,row,run):
        # A provider sentence is not proof of native execution. The gateway's
        # exact ledger and matching wrapper report must show this job's mutation.
        from production_gateway import receipts
        # Only this contiguous phase attempt may supply predecessor proof. Earlier
        # repair cycles are separated by render/review history and cannot satisfy it.
        lineage=[]
        for h in reversed(run['history']):
            if h.get('phase')!=run['phase']:break
            if h.get('jobId') or h.get('retryOf'):lineage.append(h.get('jobId') or h.get('retryOf'))
        jobs=list(dict.fromkeys(list(reversed(lineage))+[row['id']]))
        # No gateway registry means no native command was ever submitted.
        if not (Path(run['projectRoot'])/'.neural-gateway'/'registry.json').is_file() or not any(receipts(run['projectRoot'],job) for job in jobs):raise ValueError('No matching completed native mutation/report exists for this production phase.')
        # Latest authenticated mutation report: the gateway-proven saved project/comp identity.
        mutations=[r['report'] for job in jobs for r in receipts(run['projectRoot'],job) if r['kind']=='mutate']
        return mutations[-1] if mutations else {}

    def quota_boundary(self, identity, row):
        """Wait locally for settled native work, then make one bounded routing decision."""
        try:
            deadline=time.monotonic()+65*60
            while not self.closed.is_set():
                with self.control.connection() as db:
                    run=self._load(identity,db);self._current(run,db)
                if run['state']!='WAIT_QUOTA_BOUNDARY' or run.get('jobId')!=row['id']:return
                if not self.control.native.status()['unresolved']:break
                if time.monotonic()>deadline:raise ValueError('Quota fallback awaits UNKNOWN native execution; no command replayed.')
                self.closed.wait(.5)
            if self.closed.is_set():return
            self.settled_native_boundary(run)
            with self.control.lock,self.control.connection() as db:
                latest=self._load(identity,db);self._current(latest,db)
                if latest.get('jobId')!=row['id'] or latest['state']!='WAIT_QUOTA_BOUNDARY':return
                if not any(h.get('quotaPredecessor')==row['id'] for h in latest['history']):
                    latest['history'].append(dict(phase=latest['phase'],jobId=row['id'],quotaPredecessor=row['id'],at=now()));self.persist(db,latest)
            self.control.terminal(row,production_boundary=True)
            successors=[j for j in self.control.providers.status() if j.get('project')==row['project'] and j.get('assignmentId')!=row['assignmentId'] and j.get('station')==row['station'] and j.get('status') in ('QUEUED','RUNNING')]
            if not successors:raise ValueError('Subscription exhausted; no eligible fallback started. Configure an available provider and continue the saved task.')
        except Exception as e:self.block(identity,str(e))

    def completion_gateway(self, scope):
        """Reconcile persisted waits against this trusted service instance.

        Scope authority, project, generation and ledger identities remain pinned;
        only the coordinator's local HTTP binding rotates across app restarts.
        """
        from production_gateway import ProductionGateway
        gateway=ProductionGateway(scope)
        if self.service_url and self.service_token:
            gateway.scope.update(serviceURL=self.service_url,serviceToken=self.service_token)
        return gateway

    def resume_failed_media(self, identity, *, blocked=False):
        """Return known mechanical failures to their owner, never replay a job.

        Cancellation, interruption, unknown native/media execution and repeated
        failed plans remain blockers. This does not pass a failed quality gate.
        """
        with self.control.lock, self.control.connection() as db:
            run=self._load(identity,db);self._current(run,db)
            if run.get('steering') and not run['steering'].get('appliedAt'):
                raise ValueError('A saved direction awaits safe-boundary reconciliation; do not correct the obsolete phase.')
            eligible=run['state']=='WAIT_MEDIA' or (blocked and run['state']=='BLOCKED' and run.get('state_before_block')=='WAIT_MEDIA')
            if not eligible or run.get('waitNative') or not run.get('waitMedia'):
                raise ValueError('Only settled mechanical-only waits can return to their owner.')
            self.settled_native_boundary(run)
            if any(j.get('project')==run['project'] and j['status'] in ('QUEUED','RUNNING','UNKNOWN','CANCELLING') for j in self.control.providers.status()):
                raise ValueError('Prior provider work must settle before mechanical correction.')
            gateway=self.completion_gateway(run['waitScope'])
            results=[gateway.media_status(key) for key in run['waitMedia']]
            if any(r['status'] in ('QUEUED','RUNNING','CANCELLING') for r in results):return False
            if any(r['status'] not in ('COMPLETED','FAILED') for r in results):
                raise ValueError('Interrupted, cancelled or unknown media work requires reconciliation; no automatic correction.')
            failed=[r for r in results if r['status']=='FAILED']
            if not failed:raise ValueError('No terminal mechanical failure to correct.')
            signatures=[]; roots=[]
            for key,result in zip(run['waitMedia'],results):
                if not isinstance(key,str) or len(key)!=32 or not key.isalnum():raise ValueError('Invalid mechanical job identity.')
                root=self.root/'data/local-ops/jobs'/key
                job=json.loads((root/'JOB.json').read_text(encoding='utf-8'))
                if job.get('project')!=run['project']:raise ValueError('Mechanical evidence belongs to another project.')
                roots.append(str(root.resolve()))
                if result['status']=='FAILED':
                    plan=json.loads((root/'PLAN.json').read_text(encoding='utf-8'))
                    failed_ids={s['id'] for s in result.get('steps',[]) if s.get('status')=='FAILED'}
                    steps=[s for s in plan['steps'] if not failed_ids or s['id'] in failed_ids]
                    signatures.append([dict(operation=s['operation'],args=s.get('args',{})) for s in steps])
            fingerprint=hashlib.sha256(json.dumps(dict(phase=run['phase'],failures=signatures),sort_keys=True).encode()).hexdigest()
            prior=run.get('mediaCorrections',[])
            def category(rows):
                errors=' '.join(str(r.get('error','')) for r in rows).lower()
                if 'timed out' in errors:return 'timeout'
                if 'outside supported range' in errors:return 'invalid_arguments'
                if 'failed gate' in errors:return 'quality_gate'
                return 'other'
            kind=category(failed)
            kinds=[]
            for previous in prior:
                if previous.get('category'):kinds.append(previous['category'])
                elif previous.get('evidence'):
                    old=json.loads(Path(previous['evidence']).read_text(encoding='utf-8'))
                    kinds.append(category(old['jobs']))
                else:kinds.append('other')
            if len(prior)>=8 or kinds.count(kind)>=3 or any(p['fingerprint']==fingerprint for p in prior):
                raise ValueError('Mechanical correction budget exhausted or identical failed work repeated; inspect the saved evidence.')
            evidence=Path(run['projectRoot'])/('media-failure-'+fingerprint+'.json')
            save(evidence,dict(project=run['project'],revision=run['revision'],phase=run['phase'],jobs=results,signatures=signatures))
            entry=dict(fingerprint=fingerprint,category=kind,jobs=list(run['waitMedia']),evidence=str(evidence),phase=run['phase'],at=now())
            run.setdefault('mediaCorrections',[]).append(entry)
            run['history'].append(dict(phase=run['phase'],mechanicalFailure=entry))
            run['artifactRoots']=list(dict.fromkeys(run['artifactRoots']+roots))
            run['continuationContext']=run.get('continuationContext','')+'\nKNOWN TERMINAL MECHANICAL FAILURE: Read '+str(evidence)+'. All listed jobs settled; failures remain FAILED. Own the correction in this phase. Reuse valid outputs; skipped steps never ran. Do not resubmit identical failed work or rerun unrelated successful steps. During source scouting, input audio clipping/font alternatives are diagnostic observations, not proof the final deliverable failed: isolate them from independent source/frame preparation. Select verified installed fonts; retain source clipping evidence, plan measured gain/headroom, and keep final-render audio gates strict. Gain cannot repair baked-in distortion; listening remains separate. For sparse scouting of long video packs use media operation scout_frames: timestamp seeks, measured source PTS, no invented frame ordinals. Inspect media_capabilities for limits. Exact frames remains a sequential source-ordinal operation and can time out on long packs. Reuse all COMPLETED steps; submit only corrected failed and previously skipped work. Change the diagnosed plan or report a concrete unsupported capability. Never fabricate PASS, skip final QA, or replay native commands.'
            for field in ('waitMedia','waitNative','waitScope','waitStarted','state_before_block'):
                run.pop(field,None)
            run.update(state='READY',error=None,updated=now());self.persist(db,run)
        self.dispatch(identity)
        return True

    def watch(self, identity):
        """Deterministic native/local watcher; no model turns while work is pending."""
        last_dialog_check = 0.0
        try:
            while not self.closed.is_set():
                with self.control.connection() as db:run=self._load(identity,db);self._current(run,db)
                if run['state'] not in ('WAIT_NATIVE','WAIT_MEDIA'):return
                if run.get('waitNative') and time.time()-run['waitStarted']>65*60:raise ValueError('Native/media completion deadline ended UNKNOWN; no action was replayed.')
                gateway=self.completion_gateway(run['waitScope']);pending=False;completed=[];failed=False
                if run.get('waitNative'):
                    now_m = time.monotonic()
                    if now_m - last_dialog_check >= 3.0:
                        last_dialog_check = now_m
                        try:
                            from guarded_desktop import GuardedDesktop
                            GuardedDesktop(self.root).dismiss_ae_warning()
                        except Exception:
                            pass
                    result=gateway.ae_status(run['waitNative'])
                    if result['state']=='FAILED':raise ValueError('Native command failed: '+str(result.get('error')))
                    if result['state']!='COMPLETED':pending=True
                    else:completed.append(result)
                for key in run.get('waitMedia',[]):
                    result=gateway.media_status(key)
                    if result['status']=='FAILED':failed=True
                    elif result['status'] in ('CANCELLED','INTERRUPTED','UNKNOWN'):raise ValueError('Mechanical job requires reconciliation: '+str(result.get('error')))
                    elif result['status'] in ('QUEUED','RUNNING','CANCELLING'):pending=True
                    elif result['status']!='COMPLETED':raise ValueError('Unknown mechanical state; reconcile exact work before continuing.')
                    else:completed.append(result)
                if not pending:
                    if failed:
                        self.resume_failed_media(identity);return
                    with self.control.lock,self.control.connection() as db:
                        latest=self._load(identity,db);self._current(latest,db)
                        if latest['state'] not in ('WAIT_NATIVE','WAIT_MEDIA'):return
                        latest['history'].append(dict(phase=latest['phase'],completionEvidence=completed,at=now()))
                        latest.update(state='READY');self.persist(db,latest)
                    self.dispatch(identity);return
                self.closed.wait(.5)
        except Exception as e:self.block(identity,str(e))

    def verify_render(self,run):
        expected=run['expect'];count=expected['frames']
        plan={'version':1,'title':'Full native render independent technical gates','steps':[
            {'id':'decode','operation':'verify_render','args':{'input':run['render'],'expect':expected}},
            {'id':'audio','operation':'audio_measure','args':{'input':run['render']}},
            {'id':'frames','operation':'frames','args':{'input':run['render'],'frames':sorted(set([0,count//4,count//2,3*count//4,count-1])),'width':720,'columns':3}}]}
        # Commit intent first: a lost submit response is UNKNOWN, never replayed.
        try:
            job=self.services.action(dict(action='media-submit',project=run['project'],plan=plan))
            with self.control.lock,self.control.connection() as db:
                latest=self._load(run['id'],db);self._current(latest,db);latest.update(technicalJob=job['id'],state='WAIT_TECHNICAL');self.persist(db,latest)
            # A very fast job may have finished before its ID was saved.
            actual=self.services.engine.job(job['id'])
            if actual['status'] not in ('QUEUED','RUNNING'):self.notify(actual)
        except Exception as e:self.block(run['id'],'Technical submit outcome requires reconciliation: '+str(e))

    def retry(self, request):
        """Re-dispatch a BLOCKED phase as a fresh task once its cause is fixed.
        Refused when the blocked job reached the native gateway: that outcome
        must be reconciled, never replayed."""
        current=self.status(request.get('project'))
        if current and current['state']=='BLOCKED' and current.get('state_before_block')=='WAIT_MEDIA':
            if not self.resume_failed_media(current['id'],blocked=True):raise ValueError('Mechanical work is still pending; nothing restarted.')
            return self.status(current['project'])
        with self.control.lock, self.control.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM production_runs WHERE project=? ORDER BY rowid',(request.get('project'),))]
            if not rows or rows[-1]['state']!='BLOCKED':raise ValueError('Only a blocked production run can be retried.')
            run=rows[-1];self._current(run,db)
            if run.get('steering') and not run['steering'].get('appliedAt'):
                raise ValueError('A saved direction awaits safe-boundary reconciliation. Apply a new direction after resolving the exact blocker; do not retry the obsolete phase.')
            jobs=self.control.providers.status()
            if any(str(j['status']).upper() in ('QUEUED','RUNNING','UNKNOWN','CANCELLING') and j.get('project')==run['project'] for j in jobs):
                raise ValueError('Reconcile active or uncertain work before retrying production.')
            blocked=next((j['id'] for j in jobs if j.get('assignmentId')==run.get('assignmentId')),None) or run.get('jobId')
            owner=self.control.native.status().get('owner') or {}
            if self.control.native.status()['unresolved'] or owner.get('id')!=run['nativeLeaseId'] or owner.get('project')!=run['project']:
                raise ValueError('An exact settled native lease for this project is required.')
            registry=Path(run['projectRoot'])/'.neural-gateway'/'registry.json'
            from production_gateway import unresolved
            if registry.is_file() and unresolved(run['projectRoot']):
                raise ValueError('An unsettled native gateway request exists; reconcile its exact result instead of retrying.')
            if run.get('state_before_block') in ('VERIFY_INTENT','WAIT_TECHNICAL','WAIT_NATIVE','WAIT_MEDIA'):raise ValueError('Pending work outcome must be reconciled, not retried.')
            run['history'].append(dict(phase=run['phase'],retryOf=blocked,blockedError=run.get('error'),at=now()))
            run.pop('jobId',None);run.pop('state_before_block',None)
            run.update(state='READY',error=None,updated=now());self.persist(db,run)
        self.dispatch(run['id'])
        return self.status(run['project'])

    def answer_question(self, request):
        """Persist a revision-bound human answer, then dispatch once at a safe boundary."""
        answer=request.get('answer')
        if not isinstance(answer,str) or not answer.strip() or len(answer)>4000:raise ValueError('Provide an answer of 1Ã¢â‚¬â€œ4000 characters.')
        with self.control.lock,self.control.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            run=self._load(request.get('runId'),db);p=self._current(run,db)
            if run['project']!=request.get('project') or run['revision']!=request.get('revision'):raise ValueError('Decision belongs to a different project revision.')
            previous=next((q for q in run.get('decisions',[]) if q['id']==request.get('questionId')),None)
            if previous:
                if previous['answer']!=answer.strip():raise ValueError('This decision was already answered differently; steer the task explicitly instead.')
                return run
            question=run.get('question')
            if run['state']!='WAIT_HUMAN' or not question or question['id']!=request.get('questionId'):raise ValueError('This question is no longer current.')
            self.settled_native_boundary(run)
            if any(j.get('project')==run['project'] and j['status'] in ('RUNNING','QUEUED','UNKNOWN','CANCELLING') for j in self.control.providers.status()):
                raise ValueError('Work has not reached a settled boundary; the answer was not applied.')
            decision=dict(question,answer=answer.strip(),answered=now())
            run.setdefault('decisions',[]).append(decision)
            run['continuationContext']=run.get('continuationContext','')+'\nRECORDED HUMAN DECISION: '+question['text']+'\nANSWER: '+answer.strip()+'\nContinue the current phase using existing evidence. Do not ask the same resolved question again.'
            p.setdefault('messages',[]).append(dict(role='operator',revision=p['revision'],text='Decision: '+question['text']+'\n'+answer.strip()))
            run.update(state='READY',question=None,error=None,updated=now())
            self.control.save_projects(db,{**self.control.projects(db),p['id']:p});self.persist(db,run)
        self.services.signal();self.dispatch(run['id'])
        return self.status(run['project'])

    def recover(self):
        """Startup reconciliation of in-flight runs. Reads durable state only:
        re-attaches read-only watchers and missed terminal events. Never
        resubmits native/provider/media work whose outcome is uncertain."""
        latest={}
        for run in self.rows():latest[run['project']]=run
        jobs={j['id']:j for j in self.control.providers.status()}
        for run in latest.values():
            try:
                state=run.get('state')
                if state in ('BLOCKED','HUMAN_REVIEW','WAIT_HUMAN'):continue
                try:
                    with self.control.connection() as db:self._current(run,db)
                except ValueError:continue  # paused/superseded runs stay untouched
                if state=='STEERING':self.watchers.submit(self.steer_boundary,run['id'],run['steering']['requestId'])
                elif state=='READY':self.pool.submit(self.dispatch,run['id'])
                elif state in ('WAIT_NATIVE','WAIT_MEDIA'):self.watchers.submit(self.watch,run['id'])
                elif state=='WAIT_QUOTA_BOUNDARY':
                    job=jobs.get(run.get('jobId'))
                    if job:self.watchers.submit(self.quota_boundary,run['id'],job)
                    else:self.block(run['id'],'Missing exhausted provider identity; no fallback replayed.')
                elif state=='WAIT_TECHNICAL':
                    actual=self.services.engine.job(run['technicalJob'])
                    if actual['status'] not in ('QUEUED','RUNNING'):self.notify(actual)
                elif state=='VERIFY_INTENT':self.block(run['id'],'Technical submit outcome requires reconciliation after restart; nothing was replayed.')
                elif state in ('DISPATCHING','WORKING'):
                    job=jobs.get(run.get('jobId')) or next((j for j in jobs.values() if j.get('request_id')==run.get('requestId')),None)
                    if not job:self.block(run['id'],'Provider dispatch outcome is unknown after restart; nothing was replayed.')
                    elif str(job.get('status')).upper() not in ('QUEUED','RUNNING','CANCELLING'):self.notify(job)
            except Exception as e:self.block(run['id'],'Restart recovery failed: '+str(e))

    def shutdown(self):
        self.closed.set();self.watchers.shutdown(wait=True,cancel_futures=False);self.pool.shutdown(wait=True,cancel_futures=False)
