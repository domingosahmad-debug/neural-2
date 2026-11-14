"""Persistent deterministic pipelines. No provider clients, inference, or native retries.

The OS releases the execution lock on process death. A crashed job is recorded as
interrupted, never replayed. App and standalone CLI share this same lock/cache.
"""
from contextlib import contextmanager
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import sys

from operations import save, load, sha, stamp, bounded, ident, find_tool, process_options, terminate

ACTIVE = {'QUEUED', 'RUNNING', 'CANCELLING'}
VERSION = '1.0.0'
NAME = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')


class Cancelled(Exception): pass


class ChildLifetime:
    """Windows kills this local subprocess tree if its Python owner crashes."""
    def __init__(self):
        self.handle=None
        if os.name!='nt':return
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('processes',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[(n,ctypes.c_uint64) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Limits(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];self.kernel.CreateJobObjectW.restype=w.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        self.kernel.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.kernel.CreateJobObjectW(None,None)
        if not self.handle:raise OSError('Cannot create local tool lifetime guard')
        limits=Limits();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise OSError('Cannot configure local tool lifetime guard')

    def attach(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
            import ctypes
            error=ctypes.get_last_error()
            # A short probe may finish between Popen and job assignment.
            # Its normal return-code check still applies; no live child is exempt.
            if process.poll() is not None:return
            raise OSError(error,'Cannot attach local tool to its lifetime guard')

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


def alive(pid):
    if not isinstance(pid, int) or pid <= 0: return False
    if pid == os.getpid(): return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle: return ctypes.get_last_error() == 5  # access denied is not proof of death
        try:
            status = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(status)) or status.value == 259
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


@contextmanager
def execution_lock(path, check, timeout=3600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0: stream.write(b'0'); stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            check(); stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline: raise ValueError('Local execution slot is busy; nothing was replayed')
                time.sleep(.15)
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)


class LocalEngine:
    def __init__(self, root, on_terminal=None):
        self.root = Path(root).resolve()
        self.base = self.root/'data/local-ops'
        (self.base/'jobs').mkdir(parents=True, exist_ok=True)
        (self.base/'cache').mkdir(exist_ok=True)
        self.on_terminal = on_terminal
        self.closed = threading.Event()
        self.threads = {}
        self.lock = threading.RLock()
        self.tools = {n:find_tool(n) for n in ('ffmpeg', 'ffprobe')}
        self.tools['python']=sys.executable
        code=hashlib.sha256()
        for name in ('local_engine.py','local_ops_tasks.py','ae_json.jsxinc'):code.update((Path(__file__).parent/name).read_bytes())
        self.algorithm_id=code.hexdigest()
        if not (self.base/'INDEX.json').exists():
            with execution_lock(self.base/'index.lock',lambda:None,5):
                if not (self.base/'INDEX.json').exists():
                    rows=[]
                    for p in (self.base/'jobs').glob('*/JOB.json'):
                        try:rows.append(self._index_row(load(p)))
                        except (OSError,ValueError,KeyError):pass
                    save(self.base/'INDEX.json',rows)
        # Only recover records whose actual owning process is gone.
        for p in (self.base/'jobs').glob('*/JOB.json'):
            try:
                job = load(p)
                if job['status'] in ACTIVE and not alive(job.get('owner_pid')):
                    job.update(status='INTERRUPTED', error='Owning process ended. No operation was replayed; inspect outputs before a new plan.', updated_at=stamp())
                    for step in job.get('steps',[]):
                        if step.get('status')=='RUNNING':step.update(status='INTERRUPTED',error=job['error'])
                        elif step.get('status')=='QUEUED':step['status']='SKIPPED'
                    save(p, job);self._index(job)
            except (OSError, ValueError, KeyError): pass

    def capabilities(self):
        from local_ops_tasks import OPERATIONS, SCHEMAS
        outputs={'transcribe_audio':['transcript.json'],'subtitle_extract':['subtitles.srt','subtitles.json'],'music_locate':['music-location.json'],'probe':['probe.json'],'ingest':['probe.json','frames.json (video)','contact-001.jpg (video)','frame-*.jpg (video)'],'frames':['frames.json','contact-*.jpg','frame-*.jpg'],'assets':['assets.json'],'detect_events':['events.json'],'audio_extract':['audio.wav'],'audio_measure':['waveform.json'],'audio_mix':['mix.wav'],'audio_alignment':[],'validate_plan':['validated-plan.json'],'compare_snapshot':[],'evidence_pack':['context.json'],'verify_render':['probe.json'],'review_copy':['review.mp4'],'rough_assembly':['rough-cut.mp4','probe.json'],'register_preview':['preview.json'],'native_observe':['native-result.json'],'native_snapshot':['snapshot.json','native.jsx','request.json'],'native_render':['native.mov or native.mp4 or native.avi','render.json','probe.json','request.json'],'compile_ae':['assembly.jsx','compiled.json'],'native_submit':['assembly.aep','build-result.json','request.json'],'batch_inventory':['inventory.json'],'detect_beats':['audio_events.json'],'transcript_search':['search_results.json'],'analysis_proxy':['proxy.mp4'],'frame_range':['range_frames.json','contact.jpg','frame-*.jpg']}
        schemas={name:dict(value,outputs=outputs.get(name,[])+['report.json']) for name,value in SCHEMAS.items()}
        return {'version':VERSION, 'algorithm_id':self.algorithm_id, 'model_calls':0, 'operations':schemas,
                'capabilities':list(OPERATIONS), 'heavy_workers':1,
                'recipes':{'prepare':'input; optional frames/sample_count, events, audio','delivery':'input, expect; optional audio, reference, mobile, title/revision/kind/project_id/current'},
                'tools':{k:bool(v) for k,v in self.tools.items()},
                'limitations':['Semantic shot/dialogue matching and artistic approval require review.',
                               'Native mutations require explicit plan authorization; unknown native execution is never retried.']}

    def recipe(self,name,args):
        source=str(Path(args['input']).resolve())
        if name=='prepare':
            ingest={k:args[k] for k in ('frames','sample_count','columns','width') if k in args};ingest['input']=source
            steps=[{'id':'assets','operation':'assets','args':{'paths':[source]}},{'id':'media','operation':'ingest','args':ingest}]
            if args.get('events'):steps.append({'id':'events','operation':'detect_events','args':{'input':source}})
            if args.get('audio'):steps.append({'id':'audio','operation':'audio_measure','args':{'input':source}})
            return {'version':1,'title':str(args.get('title') or 'Prepare · '+Path(source).name)[:180],'steps':steps}
        if name=='delivery':
            steps=[{'id':'verify','operation':'verify_render','args':{'input':source,'expect':args.get('expect',{})}}]
            if args.get('audio'):steps.append({'id':'audio','operation':'audio_measure','args':{'input':source}})
            if args.get('reference'):steps.append({'id':'alignment','operation':'audio_alignment','args':{'input':source,'reference':str(Path(args['reference']).resolve())}})
            if args.get('mobile'):
                steps.append({'id':'mobile','operation':'review_copy','args':{'input':source,'width':1280}});preview='@mobile/review.mp4'
            else:preview=source
            if args.get('revision'):
                register={k:args[k] for k in ('title','revision','kind','project_id','current') if k in args}
                register['input']=preview
                steps.append({'id':'screen','operation':'register_preview','args':register})
            return {'version':1,'title':str(args.get('title') or 'Review checks · '+Path(source).name)[:180],'steps':steps}
        raise ValueError('Unknown recipe')

    def folder(self, key): return self.base/'jobs'/ident(key)
    def job(self, key): return load(self.folder(key)/'JOB.json')

    def snapshot(self):
        index=load(self.base/'INDEX.json');index.sort(key=lambda j:j.get('created_at',''),reverse=True)
        chosen=[j for j in index if j['status'] in ACTIVE]+[j for j in index if j['status'] not in ACTIVE][:20]
        jobs=[]
        for row in chosen:
            try:jobs.append(self.job(row['id']))
            except (OSError,ValueError):pass
        # Keep active older jobs visible as well as recent terminal jobs.
        def compact(job):
            job=copy.deepcopy(job)
            for row in job.get('steps',[]):
                value=row.get('report',{})
                row['report']={k:value[k] for k in ('summary','checks','peak','lag_seconds','correlation','model_calls','execution','preview') if k in value}
                outputs=row.get('outputs',[]); row['output_count']=len(outputs)
                row['outputs']=sorted(outputs,key=lambda n:(not (n.startswith('contact-') or n.endswith('.json')),n))[:24]
                row.pop('hashes',None);row.pop('inputs',None)
            return job
        active = [compact(j) for j in jobs if j['status'] in ACTIVE]
        recent = [compact(j) for j in jobs if j['status'] not in ACTIVE][:20]
        return {'model_calls':0, 'active':active, 'jobs':active+recent,
                'capabilities':self.capabilities()['capabilities'], 'version':VERSION}

    def validate(self, plan):
        from local_ops_tasks import OPERATIONS
        if not isinstance(plan,dict) or plan.get('version') != 1: raise ValueError('Expected plan version 1')
        if not isinstance(plan.get('title'),str) or not 1 <= len(plan['title']) <= 180: raise ValueError('Plan needs a title (1–180 characters)')
        steps = plan.get('steps')
        if not isinstance(steps,list) or not 1 <= len(steps) <= 64: raise ValueError('Plan needs 1–64 steps')
        seen = set()
        for step in steps:
            if not isinstance(step,dict) or not NAME.fullmatch(str(step.get('id',''))) or step['id'] in seen: raise ValueError('Unique lower-case step IDs required')
            if step.get('operation') not in OPERATIONS: raise ValueError('Unsupported local operation: '+str(step.get('operation')))
            if not isinstance(step.get('args',{}),dict): raise ValueError('Step args must be an object')
            deps = step.get('depends_on',[])
            if not isinstance(deps,list) or any(d not in seen for d in deps): raise ValueError('Dependencies must name earlier steps')
            def refs(value):
                if isinstance(value,str) and value.startswith('@'):
                    match = re.fullmatch(r'@([a-z][a-z0-9_-]{0,47})/([^/\\]+)',value)
                    if not match or match[1] not in seen or match[2] in ('.','..'): raise ValueError('Output references must name an earlier step and a filename')
                elif isinstance(value,dict):
                    for v in value.values(): refs(v)
                elif isinstance(value,list):
                    for v in value: refs(v)
            refs(step.get('args',{})); seen.add(step['id'])
        # JSON round trip rejects unserializable inputs; never execute arbitrary code.
        if len(json.dumps(plan,allow_nan=False)) > 100000: raise ValueError('Plan exceeds 100KB')
        return copy.deepcopy(plan)

    def submit(self, plan, background=True):
        if self.closed.is_set(): raise ValueError('Local engine is closed')
        plan = self.validate(plan)
        if plan.get('project_id'):
            from production_workbench import Blueprint,ident as project_ident
            project=project_ident(plan['project_id']);blueprint=Blueprint(self.root)
            project_record=load(self.root/'data/projects'/project/'PROJECT.json') if (self.root/'data/projects'/project/'PROJECT.json').is_file() else {}
            if blueprint.path(project).exists() or project_record.get('blueprint_required'):
                for step in plan['steps']:
                    if step['operation']=='compile_ae':
                        current=blueprint.require(project)
                        step['args'].update(blueprint_project_id=project,blueprint_hash=current['hash'])
        job = {'id':uuid.uuid4().hex, 'title':plan['title'], 'status':'QUEUED', 'created_at':stamp(),
               'updated_at':stamp(), 'project_id':plan.get('project_id'), 'project':plan.get('notification_project'), 'model_calls':0, 'cache_hits':0, 'owner_pid':os.getpid(),
               'current_step':None, 'error':None, 'steps':[dict(id=s['id'], operation=s['operation'],status='QUEUED',cached=False,outputs=[]) for s in plan['steps']]}
        folder = self.folder(job['id'])
        with execution_lock(self.base/'submission.lock',lambda:None,5):
            if len(self.snapshot()['active'])>=16:raise ValueError('Local queue is full (16 jobs); finish or cancel existing work')
            folder.mkdir();save(folder/'PLAN.json',plan);self._save(job)
        if background:
            thread = threading.Thread(target=self._worker,args=(job['id'],),daemon=True,name='local-ops-'+job['id'][:8])
            with self.lock: self.threads[job['id']] = thread
            thread.start()
            return self.job(job['id'])
        self._worker(job['id']); return self.job(job['id'])

    def cancel(self, key):
        job = self.job(key)
        if job['status'] not in ACTIVE: return job
        (self.folder(key)/'CANCEL').write_text('Requested '+stamp(),encoding='utf-8')
        # Worker owns JOB.json, including final state. Cancellation is not a native rollback.
        return dict(job,cancel_requested=True)

    def artifact(self, key, step, filename):
        job = self.job(key)
        row = next((s for s in job['steps'] if s['id']==step),None)
        if not row or filename not in row['outputs']: raise ValueError('Artifact is not registered evidence')
        p = bounded(self.folder(key),self.folder(key)/step/filename)
        if sha(p) != row.get('hashes',{}).get(filename): raise ValueError('Artifact changed; evidence invalid')
        return p

    def _worker(self, key):
        job = self.job(key); folder = self.folder(key); plan = load(folder/'PLAN.json')
        context = Context(self, job, folder)
        try:
            with execution_lock(self.base/'execution.lock',context.check):
                context.check(); job['status']='RUNNING'; self._save(job)
                from local_ops_tasks import OPERATIONS, NON_CACHEABLE
                for spec,row in zip(plan['steps'],job['steps']):
                    context.check(); job['current_step']=row['id']; row['status']='RUNNING'; row['started_at']=stamp(); self._save(job)
                    context.out = folder/row['id']; context.out.mkdir()
                    args = context.resolve(spec.get('args',{}))
                    fingerprints = context.fingerprints(args)
                    def content_args(v):
                        if isinstance(v,str) and Path(v).is_absolute() and str(Path(v).resolve()) in fingerprints:return {'sha256':fingerprints[str(Path(v).resolve())],'extension':Path(v).suffix.lower()}
                        if isinstance(v,dict):return {k:content_args(item) for k,item in v.items()}
                        if isinstance(v,list):return [content_args(item) for item in v]
                        return v
                    signature = hashlib.sha256(json.dumps({'engine':VERSION,'algorithm_id':self.algorithm_id,'op':row['operation'],'args':content_args(args),'tools':context.tool_identity()},sort_keys=True,allow_nan=False).encode()).hexdigest()
                    cache = self.base/'cache'/signature
                    hit = False
                    if row['operation'] not in NON_CACHEABLE and (cache/'CACHE.json').is_file():
                        try:
                            cached = load(cache/'CACHE.json')
                            if all(bounded(cache,cache/n).is_file() and sha(cache/n)==h for n,h in cached['hashes'].items()):
                                for name in cached['hashes']: shutil.copy2(cache/name,context.out/name)
                                report = cached['report']; hit = True
                        except (OSError,ValueError,KeyError,TypeError):pass  # damaged cache is recomputed, never trusted
                    if not hit: report = OPERATIONS[row['operation']](context,args)
                    context.check()
                    # Source contents must still match what this computation consumed.
                    if context.fingerprints(args,refresh=True) != fingerprints: raise ValueError('Input changed during processing; discard this evidence and submit a fresh plan')
                    save(context.out/'report.json',report)
                    outputs = sorted(p.name for p in context.out.iterdir() if p.is_file() and p.suffix!='.log')
                    hashes = {name:sha(context.out/name) for name in outputs}
                    row.update(report=report,outputs=outputs,hashes=hashes,inputs=fingerprints,cached=hit,finished_at=stamp(),
                               cache={'key':signature,'verified_outputs':hit,'reason':'Matching content, arguments, engine algorithm and tool versions; output hashes checked' if hit else 'Computed fresh; missing/ineligible/invalid cache',
                                      'origin_job':cached.get('origin_job') if hit else job['id'],'origin_step':cached.get('origin_step') if hit else row['id'],
                                      'origin_inputs':cached.get('inputs') if hit else fingerprints})
                    failed = any(c.get('status')=='FAIL' for c in report.get('checks',[]))
                    row['status'] = 'FAILED' if failed else 'COMPLETED'
                    if hit: job['cache_hits'] += 1
                    if not hit and not failed and row['operation'] not in NON_CACHEABLE:
                        cache.mkdir(exist_ok=True)
                        for name in outputs: shutil.copy2(context.out/name,cache/name)
                        save(cache/'CACHE.json',{'hashes':hashes,'report':report,'origin_job':job['id'],'origin_step':row['id'],'inputs':fingerprints})
                    self._save(job)
                    if failed: raise ValueError('Failed gate in '+row['id']+'; downstream steps were not executed')
                # Structural completion never claims artistic approval.
                job.update(status='COMPLETED',current_step=None)
        except Cancelled as e: job.update(status='CANCELLED',error=str(e))
        except (KeyboardInterrupt,SystemExit):job.update(status='INTERRUPTED',error='Local execution interrupted. Native work, if sent, is not confirmed cancelled. Nothing was replayed.')
        except Exception as e: job.update(status='FAILED',error=str(e)[:3000])
        finally:
            for row in job['steps']:
                if row['status']=='RUNNING': row.update(status='FAILED',error=job.get('error'))
                elif row['status']=='QUEUED': row['status']='SKIPPED'
            job['finished_at']=stamp(); self._save(job)
            # A small handoff replaces directory sweeps and giant model context.
            save(folder/'SUMMARY.json',{'id':key,'status':job['status'],'title':job['title'],'error':job.get('error'),
                'model_calls':0,'cache_hits':job['cache_hits'],'artistic_approval':'NOT TESTED',
                'steps':[{'id':s['id'],'status':s['status'],'summary':s.get('report',{}).get('summary'),
                          'checks':s.get('report',{}).get('checks',[]),'outputs':s['outputs']} for s in job['steps']]})
            with self.lock: self.threads.pop(key,None)
            if self.on_terminal:
                try: self.on_terminal(copy.deepcopy(job))
                except Exception: pass  # A completed computation must not be rerun for a callback error.

    def _save(self, job):
        job['updated_at']=stamp(); save(self.folder(job['id'])/'JOB.json',job)
        self._index(job)

    @staticmethod
    def _index_row(job):return {k:job.get(k) for k in ('id','title','status','created_at','updated_at','owner_pid')}

    def _index(self,job):
        with execution_lock(self.base/'index.lock',lambda:None,5):
            try:rows=load(self.base/'INDEX.json')
            except (OSError,ValueError):rows=[]
            rows=[r for r in rows if r['id']!=job['id']];rows.append(self._index_row(job))
            rows.sort(key=lambda r:r.get('created_at',''),reverse=True)
            # Full individual records remain inspectable by ID; the live index is bounded.
            save(self.base/'INDEX.json',[r for r in rows if r['status'] in ACTIVE]+[r for r in rows if r['status'] not in ACTIVE][:200])

    def shutdown(self):
        self.closed.set()
        with self.lock: workers = list(self.threads.values())
        for worker in workers:
            if worker is not threading.current_thread(): worker.join(timeout=5)


class Context:
    def __init__(self, engine, job, folder):
        self.engine,self.job,self.folder = engine,job,folder
        self.out=None; self.digest_cache={}

    def check(self):
        if self.engine.closed.is_set() or (self.folder/'CANCEL').exists(): raise Cancelled('Local work stopped. Native work, if submitted, must be reconciled separately; it was not cancelled or resent.')

    def resolve(self, value):
        if isinstance(value,str) and value.startswith('@'):
            step,name = value[1:].split('/',1)
            return str(self.engine.artifact(self.job['id'],step,name))
        if isinstance(value,dict): return {k:self.resolve(v) for k,v in value.items()}
        if isinstance(value,list): return [self.resolve(v) for v in value]
        return value

    def fingerprints(self, value, refresh=False):
        found={}
        def scan(v):
            if isinstance(v,str) and Path(v).is_absolute() and Path(v).is_file():
                p=Path(v).resolve(); stat=p.stat(); signature=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
                previous=self.digest_cache.get(str(p))
                if refresh or not previous or previous[0]!=signature:
                    digest=sha(p,self.cancelled)
                    if signature!=(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns): raise ValueError('Source changed while hashing')
                    self.digest_cache[str(p)]=(signature,digest)
                found[str(p)]=self.digest_cache[str(p)][1]
            elif isinstance(v,dict):
                for item in v.values(): scan(item)
            elif isinstance(v,list):
                for item in v: scan(item)
        scan(value); return found

    def cancelled(self): self.check(); return False

    def tool_identity(self):
        return {k:{'path':v,'size':Path(v).stat().st_size,'mtime':Path(v).stat().st_mtime_ns} if v else None for k,v in self.engine.tools.items()}

    def run(self, tool, args, timeout=1800):
        self.check()
        binary=self.engine.tools.get(tool)
        if not binary: raise ValueError(tool+' is unavailable')
        # Logs go to disk: never accumulate raw media or unbounded stderr in RAM.
        key=uuid.uuid4().hex[:8]; stdout=self.out/(key+'.stdout.log'); stderr=self.out/(key+'.stderr.log')
        with stdout.open('wb') as out,stderr.open('wb') as err:
            lifetime=ChildLifetime();process=None
            try:
                process=subprocess.Popen([binary,*map(str,args)],stdin=subprocess.DEVNULL,stdout=out,stderr=err,**process_options())
                lifetime.attach(process)
                save(self.folder/'PROCESS.json',{'pid':process.pid,'owner_pid':os.getpid(),'tool':tool,'started_at':stamp(),'lifetime_guard':'Windows kill-on-owner-close job' if os.name=='nt' else 'local process group'})
                deadline=time.monotonic()+timeout
                while process.poll() is None:
                    self.check()
                    if time.monotonic()>deadline: raise ValueError(tool+' timed out; local process stopped')
                    time.sleep(.1)
            finally:
                if process and process.poll() is None: terminate(process); process.wait(timeout=20)
                lifetime.close()
        if process.returncode:
            with stderr.open('rb') as stream:
                stream.seek(max(0,stderr.stat().st_size-4000)); detail=stream.read().decode('utf-8','replace')
            raise ValueError(tool+': '+detail)
        if stdout.stat().st_size>8*1024*1024: raise ValueError('Tool text result exceeds 8MB; narrow the requested range')
        return stdout.read_text(encoding='utf-8',errors='replace'),stderr
