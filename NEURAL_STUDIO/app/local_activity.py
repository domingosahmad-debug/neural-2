"""Bounded local activity views; full JOB/report evidence is unchanged.

Kept outside local_engine's media algorithm identity so presentation-only
changes do not invalidate existing deterministic media caches.
"""
from local_engine import LocalEngine, ACTIVE, VERSION
from operations import load, save

VIEW_VERSION = 2


def studio_activity(runtime):
    """Small current activity packet; no transcripts, quota probes or inference."""
    import copy
    command=getattr(runtime,'command',None)
    if command:
        with command.lock:
            saved=command.saved
            leader={k:copy.deepcopy(saved.get('leader',{}).get(k)) for k in ('status','provider','model','error')}
            authorized=bool(saved.get('continuation_authorized'))
            watches=[dict(id=key,**{k:copy.deepcopy(w.get(k)) for k in ('kind','status','command_id','script','job_status','detail','deadline','job_id')})
                     for key,w in saved.get('watches',{}).items() if w.get('status') in ('waiting','ready')][-12:]
            pause=copy.deepcopy(saved.get('production_pause'))
    else:leader={'status':'offline'};authorized=False;watches=[];pause=None
    try:plan=load(runtime.root/'data/production/CURRENT.json')
    except (OSError,ValueError):plan={}
    # Read the existing TonyFX record; never submit/repair/replay it here.
    native=None
    if command:
        try:
            request=load(command.native_bridge/'ae_command.json')
            try:result=load(command.native_bridge/'ae_mcp_result.json')
            except (OSError,ValueError):result={}
            pending=str(request.get('status','')).lower() in ('pending','running','executing')
            terminal=result.get('_commandId')==request.get('id') and type(result.get('ok')) is bool
            if pending and not terminal:
                native={'id':request.get('id'),'status':'running' if authorized else 'unresolved',
                        'script':str((request.get('args') or {}).get('scriptPath',''))[-1200:],
                        'detail':'Existing TonyFX request; request status alone is not proof AE is responding.'}
        except (OSError,ValueError):pass
    return {'version':'2026-10-23.1','leader':leader,'continuation_authorized':authorized,'pause':pause,
            'project':{k:plan.get(k) for k in ('project_id','title','revision')},'watches':watches,'native':native,
            'local':runtime.local_ops.snapshot(),'model_calls':0}


def short(value, limit=640):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + '… [full evidence in report]'
    return '[structured evidence; open the full report]'


def compact_job(job):
    result = {k: short(job[k], 3000 if k == 'error' else 640) for k in (
        'id', 'title', 'status', 'created_at', 'updated_at', 'owner_pid',
        'current_step', 'error', 'model_calls', 'cache_hits', 'finished_at') if k in job}
    result['steps'] = []
    for step in job.get('steps', []):
        row = {k: short(step[k], 2000 if k == 'error' else 640) for k in (
            'id', 'operation', 'status', 'cached', 'started_at', 'finished_at', 'error') if k in step}
        outputs = step.get('outputs', [])
        row['sources']=[str(p).replace('\\','/').rsplit('/',1)[-1][:180] for p in list((step.get('inputs') or {}).keys())[:4]]
        row['output_count'] = len(outputs)
        row['outputs'] = sorted(outputs, key=lambda n: (not (n.startswith('contact-') or n.endswith('.json')), n))[:24]
        report = step.get('report') or {}
        view = {k: short(report[k]) for k in ('summary', 'peak', 'lag_seconds', 'correlation', 'model_calls') if k in report}
        checks = report.get('checks') or []
        # Failed gates must never disappear behind a list of passing checks.
        visible = sorted(enumerate(checks), key=lambda pair: (pair[1].get('status') != 'FAIL', pair[0]))[:24]
        view['checks'] = [{k: short(check[k], 360) for k in ('name', 'id', 'status', 'detail') if k in check} for _, check in visible]
        view['check_count'] = len(checks)
        view['checks_truncated'] = len(checks) > len(visible)
        row['report'] = view
        result['steps'].append(row)
    return result


class LocalActivityEngine(LocalEngine):
    def _status_path(self, key):
        return self.folder(key) / 'STATUS.json'

    def _save_status(self, job):
        source = self.folder(job['id']) / 'JOB.json'
        stat = source.stat()
        record = {'version': VIEW_VERSION, 'signature': [stat.st_mtime_ns, stat.st_size], 'job': compact_job(job)}
        save(self._status_path(job['id']), record)
        return record['job']

    def _save(self, job):
        super()._save(job)
        try:
            self._save_status(job)
        except (OSError, ValueError):
            pass  # Presentation caching cannot fail a successful media operation.

    def activity_job(self, key):
        source = self.folder(key) / 'JOB.json'
        stat = source.stat()
        signature = [stat.st_mtime_ns, stat.st_size]
        try:
            view = load(self._status_path(key))
            if view.get('version') == VIEW_VERSION and view.get('signature') == signature:
                return view['job']
        except (OSError, ValueError, KeyError):
            pass
        # Legacy or externally updated jobs are compacted once. The signature
        # ensures a concurrent writer is observed again on the next status read.
        job = self.job(key)
        record = {'version': VIEW_VERSION, 'signature': signature, 'job': compact_job(job)}
        try:
            save(self._status_path(key), record)
        except OSError:
            pass
        return record['job']

    def snapshot(self):
        index = load(self.base / 'INDEX.json')
        index.sort(key=lambda row: row.get('created_at', ''), reverse=True)
        chosen = [j for j in index if j['status'] in ACTIVE] + [j for j in index if j['status'] not in ACTIVE][:20]
        jobs = []
        for row in chosen:
            try:
                jobs.append(self.activity_job(row['id']))
            except (OSError, ValueError, KeyError):
                pass
        active = [j for j in jobs if j['status'] in ACTIVE]
        recent = [j for j in jobs if j['status'] not in ACTIVE][:20]
        return {'model_calls': 0, 'active': active, 'jobs': active + recent,
                'capabilities': self.capabilities()['capabilities'], 'version': VERSION,
                'status_view_version': VIEW_VERSION, 'evidence': 'Bounded status view; full job and report files remain authoritative.'}
