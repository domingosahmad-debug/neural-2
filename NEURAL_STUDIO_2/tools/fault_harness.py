"""Whole-pipeline fault run: every phase, real coordinator code, injected faults, no human step.

Real: ProviderJobs, Control, Production, NativeLane, ProductionGateway, GuardedDesktop.
Stand-ins: the provider CLI (a scripted transport at the transport boundary), TonyFX/After
Effects (the synthetic ExtendScript host from tests_production_gateway, in a temp bridge),
the media engine, and one stand-in process that raises a real Win32 "After Effects" modal.
The real After Effects, the real bridge folder and the live Neural tree are never touched.

Usage: python tools/fault_harness.py OUTPUT_DIR
"""
import copy,json,os,shutil,sqlite3,subprocess,sys,threading,time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
HERE=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(HERE));os.chdir(HERE)
import tempfile
import tests_production_gateway as TG
import production_gateway as PG
import maintenance
from guarded_desktop import GuardedDesktop
from providers import ProviderJobs
from native_lane import NativeLane
from control import Control
from production import Production,CRITERIA,PHASES
from providers_engine.production_host import embedded_json
PG.DIALOG_HANDLING=True;PG.DIALOG_INTERVAL=1
REAL_BRIDGE=Path.home()/'Documents/ae-mcp-bridge'
CHILD=r'''
import ctypes,os,sys
print(os.getpid(),flush=True)
sys.exit(ctypes.windll.user32.MessageBoxW(0,'After Effects warning: 3 files are missing since you last saved this project. [Neural automated proof - do not click]','After Effects',0))
'''
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
T0=time.time();LOG=[];FAIL=[];LOCK=threading.Lock()
def log(scenario,event,**data):
    row=dict(t=round(time.time()-T0,2),scenario=scenario,event=event,**data)
    with LOCK:LOG.append(row);print(json.dumps(row,default=str),flush=True)
def check(scenario,name,ok,**data):
    log(scenario,('PASS ' if ok else 'FAIL ')+name,**data)
    if not ok:FAIL.append(scenario+': '+name)
def wait(predicate,seconds,step=.1):
    end=time.time()+seconds
    while time.time()<end:
        value=predicate()
        if value:return value
        time.sleep(step)
    return predicate()
def real_bridge_stamp():
    return {n:((REAL_BRIDGE/n).stat().st_mtime_ns,(REAL_BRIDGE/n).stat().st_size) for n in ('ae_command.json','ae_mcp_result.json') if (REAL_BRIDGE/n).exists()}

STANDIN={}  # pid/exe of the stand-in "After Effects" process; the only window Neural's dialog path may touch
PUBLISHED=[]  # every write of a pending command to the temp bridge
_atomic=PG.atomic
def counting_atomic(path,data,*a,**k):
    if Path(path).name=='ae_command.json' and isinstance(data,dict) and data.get('status')=='pending':PUBLISHED.append(data['id'])
    return _atomic(path,data,*a,**k)
PG.atomic=counting_atomic
PG.ProductionGateway._ae_processes=lambda self:None  # crash probe off: it would read the real AfterFX.exe process list
NO_TARGET=('neural-harness-no-such-process.exe',-1)
PG.DIALOG_TARGET=NO_TARGET  # production _dialog_probe runs unpatched; only its target is redirected so the real After Effects is never read or pressed

class Engine:
    def __init__(self):self.jobs={}
    def job(self,key):return copy.deepcopy(self.jobs[key])
    def snapshot(self):return {'jobs':[]}
class Services:
    def __init__(self,name):self.name=name;self.engine=Engine();self.submits=0;self.root=None
    def signal(self):pass
    def action(self,request):
        assert request['action']=='media-submit',request
        self.submits+=1;key=uuid4().hex
        if self.submits==1:
            row=dict(id=key,project=request['project'],status='FAILED',error='Failed gate in decode: frame count 99, expected 100',steps=[dict(id='decode',status='FAILED'),dict(id='audio',status='SKIPPED'),dict(id='frames',status='SKIPPED')])
        else:
            row=dict(id=key,project=request['project'],status='COMPLETED',steps=[dict(id='decode',status='COMPLETED'),dict(id='audio',status='COMPLETED',report=dict(rms=.12,clipped_samples=0)),dict(id='frames',status='COMPLETED')])
        folder=self.root/'data/local-ops/jobs'/key;folder.mkdir(parents=True);(folder/'JOB.json').write_text(json.dumps(dict(id=key,project=request['project'])))  # the real engine always creates the job folder
        self.engine.jobs[key]=row;log(self.name,'technical verification job',n=self.submits,status=row['status'],steps=[s['id'] for s in request['plan']['steps']]);return {'id':key}

class Scripted:
    """Stand-in for the provider CLI child. Per phase and attempt it behaves like a worker, or fails like one."""
    def __init__(self,h):self.h=h;self.calls={};self.rows=[]
    def supports(self,route,mode):return True
    def run(self,row,packet,folder,session,cancel):
        phase=packet['productionPhase'];n=self.calls[phase]=self.calls.get(phase,0)+1
        self.rows.append(dict(phase=phase,attempt=n,job=row['id'],route=row['route'],model=row['model']))
        log(self.h.name,'provider job started',phase=phase,attempt=n,route=row['route'],model=row['model'],job=row['id'])
        sid=session or uuid4().hex
        result=getattr(self.h,'do_'+phase)(n,row,packet,sid)
        if 'status' in result:
            log(self.h.name,'provider job ended without a result',phase=phase,attempt=n,status=result['status'],error=result.get('error'));return result
        suffix=result.pop('_suffix','')
        data=dict(packet['resultTemplate']);data.update(summary='Scripted '+phase+' attempt '+str(n),production=dict(result,phase=phase))
        text=json.dumps(data)+suffix
        return {'status':'COMPLETED','text':text,'structured_result':embedded_json(text),'session_id':sid}

class Harness:
    def __init__(self,name):
        self.name=name;self.temp=tempfile.TemporaryDirectory(prefix='neural-fault-');self.root=Path(self.temp.name).resolve()
        (self.root/'knowledge').mkdir();(self.root/'data/provider-jobs').mkdir(parents=True);(self.root/'model_catalog.json').write_text('{"models":[]}')
        self.bridge=self.root/'bridge';self.bridge.mkdir()
        self.project=self.root/'data/projects/alpha';self.project.mkdir(parents=True);(self.project/'project.aep').write_bytes(b'stand-in saved After Effects project')
        self.db=self.root/'workspace.sqlite3'
        with closing(sqlite3.connect(self.db)) as db,db:
            db.execute('CREATE TABLE workspace(id INTEGER PRIMARY KEY,body TEXT)')
            db.execute('INSERT INTO workspace VALUES(1,?)',(json.dumps({'alpha':{'id':'alpha','name':'Fault harness edit','brief':'Complete isolated edit with injected faults','revision':1,'assignments':{},'messages':[],'productionControl':{}}}),))
        self.services=Services(name);self.services.root=self.root;self.transport=Scripted(self)
        self.providers=ProviderJobs(self.root,on_change=self.services.signal,transport=self.transport)
        self.native=NativeLane(self.root,bridge=self.bridge)
        self.control=Control(self.root,self.db,self.providers,self.native,self.services.signal)
        self.production=Production(self.control,self.services);self.control.production=self.production
        def prepare(row,packet,folder):
            packet=self.production.prepare(row,packet,folder)
            scope_path=Path(folder)/'scope.json'
            if scope_path.exists():
                scope=json.loads(scope_path.read_text(encoding='utf-8'));scope['bridgePath']=str(self.bridge);_atomic(scope_path,scope)
            return packet
        self.providers.prepare_packet=prepare;self.providers.before_start=self.control.admitted
        self.providers.on_terminal=lambda row:(self.control.terminal(row),self.production.notify(row))
        self.control.reconcile()
        self.executed=[];self.threads=[]
    # --- stand-in TonyFX / After Effects -------------------------------------------------
    def gateway(self,packet):
        g=PG.ProductionGateway(packet['productionScope'])
        assert g.bridge==self.bridge.resolve(),'gateway must use the temp bridge'
        return g
    def tonyfx(self,g,public):
        row=g._row(public['requestId']);scope=g.scope
        result=subprocess.run(['node','-e',TG.NODE],input=json.dumps({'script':Path(row['scriptPath']).read_text(encoding='utf-8'),'authority':json.loads(Path(scope['authorityPath']).read_text(encoding='utf-8')),'authorityPath':scope['authorityPath'],'projectPath':scope['aeProjectPath'],'compName':'NEURAL_MASTER'}),text=True,capture_output=True,timeout=10)
        if result.returncode:raise RuntimeError('synthetic AE failed: '+result.stderr[-600:])
        for path,text in json.loads(result.stdout)['files'].items():Path(path).write_text(text,encoding='utf-8')
        _atomic(self.bridge/'ae_command.json',{'id':row['commandId'],'status':'completed'});_atomic(self.bridge/'ae_mcp_result.json',{'_commandId':row['commandId'],'ok':True,'_servicedBy':'TonyFX'})
        self.executed.append(row['commandId'])
    def inspect(self,g,rid):
        self.tonyfx(g,g.ae_inspect(rid));done=g.ae_status(rid)
        if done['state']!='COMPLETED':raise RuntimeError('inspect did not complete: '+json.dumps(done)[:400])
        return done['guard']
    def mutate(self,g,rid,guard,execute=True):
        public=g.ae_submit(rid,'return {applied:true};',guard)
        if execute:
            self.tonyfx(g,public);done=g.ae_status(rid)
            if done['state']!='COMPLETED':raise RuntimeError('mutation did not complete: '+json.dumps(done)[:400])
        return public
    def native_work(self,packet,tag):
        g=self.gateway(packet);self.mutate(g,tag+'-mutate',self.inspect(g,tag+'-inspect'));return g
    def file(self,name,data=b'{"actual":"evidence"}'):
        p=self.project/name;p.write_bytes(data);return str(p)
    def later(self,fn):
        t=threading.Thread(target=fn,daemon=True);t.start();self.threads.append(t)
    # --- ordinary phase behaviour ---------------------------------------------------------
    def do_scout(self,n,row,packet,sid):return dict(outcome='complete',artifacts=[self.file('scout.json')])
    def do_plan(self,n,row,packet,sid):
        b=self.file('blueprint.json');return dict(outcome='complete',artifacts=[b],blueprint=b,expect=dict(width=1920,height=1080,frames=100,fps=25,audio=True))
    def do_plan_review(self,n,row,packet,sid):return dict(outcome='complete',artifacts=[self.file('plan-review.json')])
    def do_prototype(self,n,row,packet,sid):
        self.native_work(packet,'prototype%d'%n)
        return dict(outcome='complete',artifacts=[self.file('proto.mp4',b'mp4'),self.file('proto.png',b'png')],render=str(self.project/'proto.mp4'),aep=str(self.project/'project.aep'))
    def do_prototype_review(self,n,row,packet,sid):return dict(outcome='complete',artifacts=[self.file('prototype-review.json')])
    def do_build(self,n,row,packet,sid):
        self.native_work(packet,'build%d'%n);return dict(outcome='complete',artifacts=[self.file('build.json')])
    def do_render(self,n,row,packet,sid):
        self.native_work(packet,'render%d'%n)
        return dict(outcome='complete',artifacts=[self.file('master.mp4',b'mp4')],render=str(self.project/'master.mp4'),expect=dict(width=1920,height=1080,frames=100,fps=25,audio=True))
    def review(self,fail=None):
        return dict(outcome='complete',artifacts=[self.file('review.json')],criteria={c:dict({'pass':c!=fail},evidence='Watched the full render at speed and checked this criterion.') for c in CRITERIA},**({'issues':['Fix '+fail+' at 00:04']} if fail else {}))
    def do_harsh_review(self,n,row,packet,sid):return self.review()
    def do_goldfish_review(self,n,row,packet,sid):return self.review()
    def do_repair(self,n,row,packet,sid):
        self.native_work(packet,'repair%d'%n);return dict(outcome='complete',artifacts=[self.file('repair.json')])
    # --- run control -----------------------------------------------------------------------
    def run(self):
        rows=self.production.rows('alpha');return rows[-1] if rows else None
    def claim(self,owner,project):
        with patch('socket.socket.connect_ex',return_value=1),self.control.lock:
            return self.native.claim(owner,project,True,replace=self.production.lease_handover())
    def start(self):
        worker=[dict(route='claude',model='sonnet',effort='medium'),dict(route='codex',model='gpt-6.1-terra',effort='medium')]
        supervisor=[dict(route='claude',model='opus',effort='medium'),dict(route='codex',model='gpt-6.1-sol',effort='medium')]
        from production import SUPERVISOR_PHASES
        lease=self.claim('fault harness','alpha')
        with patch('providers_engine.transport.executable',return_value='fake'):
            return self.production.start(dict(project='alpha',nativeLeaseId=lease['id'],commissioning=True,candidates=supervisor,phaseCandidates={p:(supervisor if p in SUPERVISOR_PHASES else worker) for p in list(PHASES)+['repair']}))
    def ledger(self):
        path=self.root/'data/production-gateway.sqlite3'
        if not path.exists():return []
        with closing(sqlite3.connect(path)) as db:return [json.loads(r[0]) for r in db.execute('SELECT body FROM requests ORDER BY rowid')]
    def actions(self):
        path=self.root/'data/desktop-observations/ACTIONS.jsonl'
        return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []
    def keep(self):
        target=out/self.name;target.mkdir(exist_ok=True)
        run=self.run() or {}
        (target/'run.json').write_text(json.dumps({k:v for k,v in run.items() if 'oken' not in k},indent=1,default=str),encoding='utf-8')
        (target/'gateway-ledger.json').write_text(json.dumps([{k:r.get(k) for k in ('requestId','jobId','kind','state','commandId','error','notSubmitted','staleLockSetAside','dialogsDismissed','submitted','finished')} for r in self.ledger()],indent=1,default=str),encoding='utf-8')
        (target/'provider-jobs.json').write_text(json.dumps([dict(next((t for t in self.transport.rows if t['job']==j['id']),{}),id=j['id'],station=j.get('station'),route=j.get('route'),model=j.get('model'),status=j.get('status'),error=j.get('error'),reconciled=j.get('reconciled')) for j in self.providers.status()],indent=1,default=str),encoding='utf-8')
        (target/'bridge-published.json').write_text(json.dumps(dict(published=PUBLISHED,executed=self.executed),indent=1),encoding='utf-8')
        folder=self.root/'data/desktop-observations'
        if folder.exists():
            for f in folder.iterdir():
                if f.is_file():shutil.copy2(f,target/f.name)
    def close(self):
        self.keep();self.production.closed.set()
        for name in ('shutdown',):
            for owner in (self.production,self.providers):
                try:getattr(owner,name)()
                except Exception:pass
        try:self.temp.cleanup()
        except Exception:pass

class FullRun(Harness):
    """Scenario A: all phases to HUMAN_REVIEW with every named fault injected on the way."""
    def do_scout(self,n,row,packet,sid):
        if n==1:  # FAULT provider quota exhaustion
            return {'status':'FAILED','error':'Usage limit reached for this subscription.','failure_kind':'subscription_exhausted','exhaustion_evidence':{'route':row['route'],'model':row['model'],'event':'simulated limit event'},'session_id':sid}
        return super().do_scout(n,row,packet,sid)
    def do_prototype(self,n,row,packet,sid):
        if n==1:  # FAULT provider process dies mid-turn -> UNKNOWN provider result
            g=self.gateway(packet);self.inspect(g,'prototype1-inspect');raise RuntimeError('simulated provider process crash after a completed inspect')
        return super().do_prototype(n,row,packet,sid)
    def do_build(self,n,row,packet,sid):
        if n==1:  # FAULT deadline overrun while a native command is still executing
            g=self.gateway(packet);public=self.mutate(g,'build1-mutate',self.inspect(g,'build1-inspect'),execute=False);self.build_command=public['commandId']
            def finish():
                time.sleep(4);self.tonyfx(g,public);self.build_native_done=time.time();log(self.name,'stand-in TonyFX finished the build mutation after the worker was gone')
            self.later(finish)
            return {'status':'UNKNOWN','error':'Child deadline exceeded; reconcile session before continuation'}
        self.build2_started=time.time()
        return dict(outcome='complete',artifacts=[self.file('build.json')])  # no new native command: the proven one is reused
    def do_render(self,n,row,packet,sid):
        if n==1:  # FAULT After Effects modal while the render command is pending
            g=self.gateway(packet);public=self.mutate(g,'render1-mutate',self.inspect(g,'render1-inspect'),execute=False)
            child=subprocess.Popen([sys.executable,'-c',CHILD],stdout=subprocess.PIPE,text=True);pid=int(child.stdout.readline());self.child=child
            desk=GuardedDesktop(self.root);exe=Path(desk.win.exe(pid).lower()).name
            self.modal_seen=wait(lambda:[{k:d[k] for k in ('class','title','texts')} for d in desk.ae_dialogs(exe,pid)],10)
            STANDIN.update(desk=desk,exe=exe,pid=pid);PG.DIALOG_TARGET=(exe,pid);log(self.name,'REAL modal raised by the stand-in After Effects process',pid=pid,dialogs=self.modal_seen)
            def finish():  # After Effects cannot finish a script while a modal is open
                while child.poll() is None:time.sleep(.2)
                time.sleep(.5);self.tonyfx(g,public);log(self.name,'stand-in TonyFX finished the render command after the modal closed',childExit=child.returncode)
            self.later(finish)
            return dict(outcome='waiting',waitNative='render1-mutate')
        if n in (2,3):  # after the native wait, and after the failed technical gate: export only, no new native command
            return dict(outcome='complete',artifacts=[self.file('master.mp4',b'mp4')],render=str(self.project/'master.mp4'),expect=dict(width=1920,height=1080,frames=100,fps=25,audio=True))
        return super().do_render(n,row,packet,sid)
    def do_harsh_review(self,n,row,packet,sid):return self.review('typography' if n==1 else None)  # FAULT review rejects once
    def do_goldfish_review(self,n,row,packet,sid):return dict(self.review(),_suffix='}')  # FAULT stray trailing brace (job 3614879f)

def scenario_full():
    s='A-full-run';before=real_bridge_stamp();h=FullRun(s)
    try:
        # FAULT stale lease of another, idle project (the state the live tree is in today)
        old=h.claim('abandoned earlier edit','older-project')
        # FAULT stale bridge helper lock left by a dead process
        lock=h.bridge/'tfx_skill_client.lock';lock.write_text('dead-holder');past=time.time()-900;os.utime(lock,(past,past))
        # FAULT stale in-flight admission marker of a dead process
        dead=subprocess.Popen([sys.executable,'-c','pass']);dead.wait();marker=h.root/'data/maintenance/inflight'/('%d-%s.json'%(dead.pid,uuid4().hex));marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text(json.dumps({'kind':'provider','at':time.time()-900}))
        run=h.start();log(s,'production started',run=run['id'],phase=run['phase'])
        owner=h.native.status()['owner']
        check(s,'stale idle lease handed over at claim, no hand deletion',owner['project']=='alpha' and owner.get('replaced',{}).get('id')==old['id'],owner={k:owner.get(k) for k in ('project','owner','replaced')})
        final=wait(lambda:(h.run() or {}).get('state') in ('HUMAN_REVIEW','BLOCKED') and h.run(),180,.25)
        run=h.run();log(s,'run settled',state=run['state'],phase=run['phase'],error=run.get('error'),seconds=round(time.time()-T0,1))
        check(s,'run reached HUMAN_REVIEW through every phase with zero human actions',bool(final) and run['state']=='HUMAN_REVIEW',state=run['state'],error=run.get('error'))
        done=[x['phase'] for x in run['history'] if x.get('result') and x['result'].get('outcome')=='complete' or x.get('artifacts')]
        check(s,'every phase produced a completed result',all(p in done for p in list(PHASES)+['repair']),order=done)
        calls=h.transport.calls;t=h.transport.rows
        # quota exhaustion
        scout=[r for r in t if r['phase']=='scout']
        check(s,'quota exhaustion: fell back to the other provider automatically',len(scout)==2 and (scout[0]['route'],scout[1]['route'])==('claude','codex'),scout=scout)
        # provider UNKNOWN
        proto=[r for r in t if r['phase']=='prototype'];jobs={j['id']:j for j in h.providers.status()}
        check(s,'provider UNKNOWN: re-routed to another route, UNKNOWN job settled without rerun',len(proto)==2 and proto[0]['route']!=proto[1]['route'] and jobs[proto[0]['job']]['status']=='FAILED' and bool(jobs[proto[0]['job']].get('reconciled')),proto=proto,job={k:jobs[proto[0]['job']].get(k) for k in ('status','reconciled')})
        # deadline overrun with live native command
        build=[r for r in t if r['phase']=='build']
        check(s,'deadline overrun: next worker started only after the pending native command finished',len(build)==2 and getattr(h,'build_native_done',0) and h.build2_started>=h.build_native_done,build=build,nativeDone=round(getattr(h,'build_native_done',0)-T0,2),build2=round(getattr(h,'build2_started',0)-T0,2))
        check(s,'deadline overrun: the pending native command was published once and never replayed',PUBLISHED.count(h.build_command)==1 and h.executed.count(h.build_command)==1)
        # modal
        acts=[a for a in h.actions() if a.get('kind')=='dialog_ok']
        check(s,'AE modal: a real #32770 dialog was open while the render command was pending',bool(h.modal_seen),dialogs=h.modal_seen)
        check(s,'AE modal: dismissed by Neural and logged INTENT then DONE',[a['state'] for a in acts]==['INTENT','DONE'],actions=acts)
        check(s,'AE modal: stand-in process saw IDOK (exit 1)',h.child.wait(5)==1,exit=h.child.returncode)
        row=next(r for r in h.ledger() if r['requestId']=='render1-mutate')
        check(s,'AE modal: ledger row COMPLETED and records the dismissal; run never BLOCKED',row['state']=='COMPLETED' and len(row.get('dialogsDismissed',[]))==1 and not any(x.get('blockedError') and not x.get('providerFailure') for x in run['history']),dismissed=row.get('dialogsDismissed'))
        # technical gate failure
        check(s,'failed technical gate: render re-dispatched, gate re-run, no native replay',h.services.submits==3 and calls['render']==4,submits=h.services.submits,renders=calls['render'])
        # review loop
        check(s,'review rejection: one repair, re-render, second harsh review passes',calls['harsh_review']==2 and calls['repair']==1,calls=calls)
        harsh=[r for r in t if r['phase']=='harsh_review'][-1];gold=[r for r in t if r['phase']=='goldfish_review'][-1]
        check(s,'goldfish reviewer is a different model from the harsh reviewer',harsh['model']!=gold['model'],harsh=harsh['model'],goldfish=gold['model'])
        check(s,'malformed JSON (stray trailing brace) accepted as the complete result',calls['goldfish_review']==1 and run['state']=='HUMAN_REVIEW')
        # locks
        aside=list(h.bridge.glob('tfx_skill_client.lock.stale-*'))
        check(s,'stale bridge lock set aside (kept, not deleted) and the first command still published',len(aside)==1 and aside[0].read_text()=='dead-holder' and not lock.exists() and any(r.get('staleLockSetAside') for r in h.ledger()),kept=[a.name for a in aside])
        check(s,'stale in-flight marker of a dead process did not hold the run and is pruned by the maintenance drain check',maintenance.inflight(h.root)==[] and not marker.exists())
        # global invariants
        ledger=h.ledger();native=[r for r in ledger if r.get('commandId') and r.get('kind')!='media']
        check(s,'every native command published exactly once and executed exactly once (no replay)',sorted(PUBLISHED)==sorted(set(PUBLISHED)) and sorted(h.executed)==sorted(set(h.executed)) and sorted(PUBLISHED)==sorted(h.executed)==sorted(r['commandId'] for r in native),published=len(PUBLISHED),executed=len(h.executed),ledger=len(native))
        check(s,'no native request left unsettled',all(r['state'] in ('COMPLETED','FAILED') for r in ledger),states=sorted(set(r['state'] for r in ledger)))
        check(s,'no provider job left UNKNOWN or running',all(j['status'] in ('COMPLETED','FAILED') for j in h.providers.status()),statuses=[j['status'] for j in h.providers.status()])
        check(s,'provider turns are bounded: 10 phases plus 7 fault recoveries',len(t)==sum(calls.values())==17,jobs=len(t),calls=calls)
        check(s,'real After Effects bridge untouched',real_bridge_stamp()==before)
    finally:
        STANDIN.clear();PG.DIALOG_TARGET=NO_TARGET
        if getattr(h,'child',None) and h.child.poll() is None:h.child.kill()
        h.close()

class NativeUnknown(Harness):
    """Scenario B: a native command whose outcome cannot be known must stop the run, visibly, with no replay."""
    def do_prototype(self,n,row,packet,sid):
        g=self.gateway(packet);public=self.mutate(g,'prototype1-mutate',self.inspect(g,'prototype1-inspect'),execute=False);self.command=public['commandId']
        _atomic(self.bridge/'ae_command.json',{'id':'foreign-'+uuid4().hex,'status':'completed'});log(self.name,'FAULT: a foreign command replaced ours on the bridge; our outcome is unknowable')
        return dict(outcome='waiting',waitNative='prototype1-mutate')

def scenario_unknown():
    s='B-native-unknown';before=real_bridge_stamp();mark=len(PUBLISHED);h=NativeUnknown(s)
    try:
        h.start();t=time.time()
        blocked=wait(lambda:(h.run() or {}).get('state')=='BLOCKED' and h.run(),60,.25)
        check(s,'run BLOCKED with a visible reason as soon as the outcome was unknowable',bool(blocked) and bool(blocked.get('error')),seconds=round(time.time()-t,1),error=(blocked or {}).get('error'))
        jobs=len(h.transport.rows);time.sleep(6)
        check(s,'inference stopped: no further provider job while blocked',len(h.transport.rows)==jobs and not [j for j in h.providers.status() if j['status'] in ('QUEUED','RUNNING')],jobs=jobs)
        row=next(r for r in h.ledger() if r['requestId']=='prototype1-mutate')
        check(s,'the command stays UNKNOWN and was published exactly once',row['state']=='UNKNOWN' and PUBLISHED[mark:].count(h.command)==1 and h.command not in h.executed,state=row['state'])
        # Retry on a blocked native wait is reconciliation only: the watcher re-reads the exact request and blocks again.
        try:h.production.retry(dict(project='alpha'));refused=None
        except Exception as error:refused=str(error)
        time.sleep(4);again=wait(lambda:(h.run() or {}).get('state')=='BLOCKED' and h.run(),20,.25)
        check(s,'Retry only re-reads the UNKNOWN command: blocked again, nothing replayed, no model turn',bool(again) and 'UNKNOWN' in str(again.get('error')) and PUBLISHED[mark:].count(h.command)==1 and h.command not in h.executed and len(h.transport.rows)==jobs,refusal=refused,error=(again or {}).get('error'))
        check(s,'the lease is not handed to another project while a native outcome is unknown',h.production.lease_handover() is None)
        check(s,'real After Effects bridge untouched',real_bridge_stamp()==before)
    finally:h.close()

for scenario in (scenario_full,scenario_unknown):
    try:scenario()
    except Exception as error:
        import traceback;FAIL.append(scenario.__name__+': '+repr(error));log(scenario.__name__,'EXCEPTION',trace=traceback.format_exc())
(out/'TIMELINE.jsonl').write_text('\n'.join(json.dumps(r,default=str) for r in LOG),encoding='utf-8')
print('RESULT','FAIL '+json.dumps(FAIL) if FAIL else 'PASS',len([r for r in LOG if r['event'].startswith('PASS')]),'checks passed',flush=True)
os._exit(1 if FAIL else 0)
