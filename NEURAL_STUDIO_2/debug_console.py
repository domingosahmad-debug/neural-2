"""Isolated Debug workspace: its own provider jobs, conversation and repair staging.

Text only. It cannot own After Effects, submit media work or change edit state.
Model output is data: it is parsed, checked and shown, never executed. Source is
replaced only through maintenance.apply and never restarts the app.
"""
import ctypes
import ast, difflib, json, re, subprocess, threading, time, uuid
from contextlib import closing
from pathlib import Path

import maintenance
from providers import ProviderJobs

BUSY = ('QUEUED', 'RUNNING', 'CANCELLING')
SETTLED_RUNS = ('BLOCKED', 'HUMAN_REVIEW', 'COMPLETED', 'CANCELLED', 'FAILED')
INSTRUCTIONS = (
    'You are the Neural Studio 2 Debug assistant. Diagnose the software problem from the supplied question, '
    'diagnostics and source files only. You cannot run tools, see the screen, control After Effects or change an edit. '
    'Say plainly what the evidence does not show. Answer in prose, or, only if you propose a source repair, answer with '
    'one JSON object and nothing else: {"summary":str,"diagnosis":str,"changes":[{"path":str,"beforeSha256":str,"content":str}]}. '
    'Each change replaces one supplied file completely: path and beforeSha256 exactly as supplied, content the full new file. '
    'At most 6 files. Never include shell commands; nothing you write is executed.')


def tail(path, limit=6000):
    try:
        with open(path, 'rb') as stream:
            stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size - limit))
            return {'file': Path(path).name, 'bytes': size, 'tailBytes': min(size, limit), 'text': stream.read().decode('utf-8', 'replace')}
    except OSError:
        return None


class DebugConsole:
    def __init__(self, root, control=None, services=None, editor=None, production=None, native=None, *, transport=None, on_change=None, secrets=()):
        self.root = Path(root).resolve(); self.base = self.root / 'data' / 'debug-runtime'
        (self.base / 'turns').mkdir(parents=True, exist_ok=True)
        self.control, self.services, self.editor, self.production, self.native = control, services, editor, production, native
        self.secrets = [s for s in secrets if s]
        self.lock = threading.RLock()
        # Separate root: separate job folder, session store and completion callbacks.
        self.jobs = ProviderJobs(self.base, on_change=on_change, transport=transport, max_workers=1)

    # ---- context -----------------------------------------------------
    def sources(self):
        rows = []
        for folder in maintenance.SOURCE_DIRS:
            for path in sorted((self.root / folder).glob('*')):
                relative = path.relative_to(self.root).as_posix()
                try: maintenance.allowed_source(self.root, relative)
                except maintenance.Refused: continue
                if path.is_file(): rows.append({'path': relative, 'bytes': path.stat().st_size})
        return rows

    def capabilities(self):
        return [r for r in (self.control.capabilities() if self.control else []) if r.get('available')]

    def diagnostics(self, project):
        out = {'at': time.time(), 'maintenance': maintenance.inspect(self.root), 'nativeUnresolved': None, 'project': None, 'failedJobs': []}
        if self.native: out['nativeUnresolved'] = bool(self.native.status()['unresolved'])
        if self.control:
            if project:
                s = self.control.status(project); run = s.get('production') or {}
                out['project'] = {'id': project, 'paused': s['paused'], 'pauseSettled': s['pauseSettled'], 'activity': s.get('activity'),
                                  'stations': [{k: str(r.get(k) or '')[:300] for k in ('station', 'state', 'model', 'reason')} for r in s['stations']],
                                  'production': {k: (str(run.get(k))[:600] if run.get(k) is not None else None) for k in ('id', 'state', 'phase', 'error', 'revision')}}
            failed = [j for j in self.control.providers.status() if j['status'] in ('FAILED', 'UNKNOWN') and (not project or j.get('project') == project)][:8]
            out['failedJobs'] = [{k: str(j.get(k) or '')[:300] for k in ('id', 'station', 'model', 'status', 'error')} for j in failed]
        log = tail(self.root / 'desktop-service.log')
        if log:
            for secret in self.secrets: log['text'] = log['text'].replace(secret, '[redacted]')
            out['serviceLogTail'] = log
        return out

    # ---- conversation ------------------------------------------------
    def turns(self):
        rows = []
        for path in self.base.glob('turns/*.json'):
            try: rows.append(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError): pass
        return sorted(rows, key=lambda r: r['created'])

    def _job(self, job_id):
        return next((j for j in self.jobs.status() if j['id'] == job_id), None)

    def _text(self, job_id):
        result = self.jobs.result(job_id)
        return str(result.get('text') or (result.get('result') or {}).get('text') or '')

    def state(self):
        turns = []
        for turn in self.turns()[-30:]:
            job = self._job(turn.get('jobId')) if turn.get('jobId') else None
            row = {k: turn.get(k) for k in ('id', 'requestId', 'question', 'route', 'model', 'effort', 'project', 'files', 'created', 'jobId', 'context')}
            row['status'] = job['status'] if job else 'NOT_SUBMITTED'; row['error'] = job.get('error') if job else turn.get('error')
            if job and job['status'] == 'COMPLETED':
                try: row['reply'] = self._text(job['id'])
                except (ValueError, OSError) as error: row['error'] = str(error)
            turns.append(row)
        repairs = [{k: m.get(k) for k in ('id', 'state', 'created', 'origin', 'files', 'error', 'checks')} for m in maintenance.manifests(self.root) if m.get('state') != 'DISCARDED'][-10:]
        return {'capabilities': self.capabilities(), 'sources': self.sources(), 'turns': turns, 'repairs': repairs,
                'busy': any(j['status'] in BUSY for j in self.jobs.status()), 'maintenance': maintenance.inspect(self.root),
                'limits': {'files': 6, 'sourceBytes': 100000, 'question': 4000}}

    def ask(self, request):
        rid, question = request.get('requestId'), request.get('question')
        if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{8,120}', rid): raise ValueError('A persistent requestId is required.')
        with self.lock:
            turn = next((t for t in self.turns() if t['requestId'] == rid), None)
            if not turn:
                if not isinstance(question, str) or not 0 < len(question.strip()) <= 4000: raise ValueError('Ask a question of 1 to 4000 characters.')
                if any(j['status'] in BUSY for j in self.jobs.status()): raise ValueError('A Debug invocation is already running; wait for it to finish.')
                route, model, effort = request.get('route'), request.get('model'), request.get('effort')
                choice = next((c for c in self.capabilities() if c['route'] == route and c['model'] == model), None)
                if not choice or effort not in choice['efforts']: raise ValueError('Choose an installed model and one of its allowed efforts.')
                names = request.get('files') or []
                if not isinstance(names, list) or len(names) > 6 or len(set(names)) != len(names): raise ValueError('Select at most 6 distinct source files.')
                files = []; total = 0
                for name in names:
                    path = maintenance.allowed_source(self.root, name)
                    if not path.is_file(): raise ValueError('Source file not found: ' + str(name))
                    data = path.read_bytes(); total += len(data)
                    files.append({'path': name, 'sha256': maintenance.sha(data), 'bytes': len(data), 'content': data.decode('utf-8')})
                if total > 100000: raise ValueError(f'Selected source is {total} bytes; the limit is 100000. Select fewer or smaller files (nothing is truncated).')
                project = request.get('project') or None
                diagnostics = self.diagnostics(project)
                identity = uuid.uuid4().hex
                packet = {'project': 'neural2-debug', 'station': 'Debug', 'assignmentId': identity, 'revision': 1, 'model': model,
                          'requiredCapabilities': ['text'], 'task': INSTRUCTIONS, 'question': question.strip(), 'diagnostics': diagnostics, 'sources': files}
                turn = {'id': identity, 'requestId': rid, 'question': question.strip(), 'route': route, 'model': model, 'effort': effort, 'project': project,
                        'files': [{k: f[k] for k in ('path', 'sha256', 'bytes')} for f in files], 'created': time.time(), 'jobId': None,
                        'context': {'diagnostics': [k for k, v in diagnostics.items() if v], 'sourceBytes': total}, 'packet': packet}
                maintenance.durable(self.base / 'turns' / (identity + '.json'), turn)
            if not turn.get('jobId'):
                # Same request ID and frozen packet: the provider store returns the same admitted attempt.
                with maintenance.admission(self.root, 'debug'):
                    job = self.jobs.submit(turn['packet'], turn['route'], turn['model'], turn['effort'], 'debug:' + rid)
                turn['jobId'] = job['id']; maintenance.durable(self.base / 'turns' / (turn['id'] + '.json'), turn)
        return self.state()

    def cancel(self, request):
        turn = next((t for t in self.turns() if t['id'] == request.get('turn')), None)
        if not turn or not turn.get('jobId'): raise ValueError('Unknown Debug turn.')
        self.jobs.cancel(turn['jobId'])
        return self.state()

    # ---- repair staging ----------------------------------------------
    @staticmethod
    def proposal(text):
        candidates = [text.strip()] + [m.group(1) for m in re.finditer(r'```(?:json)?\s*\n(.*?)\n```', text, re.S)]
        for candidate in candidates:
            try: value = json.loads(candidate)
            except ValueError: continue
            if isinstance(value, dict) and isinstance(value.get('changes'), list): return value
        raise ValueError('This reply contains no structured repair proposal.')

    def check(self, path, content):
        if path.endswith('.py'):
            try: ast.parse(content, filename=path)
            except SyntaxError as error: raise ValueError(f'Python syntax error in {path}: line {error.lineno}: {error.msg}')
            return 'python syntax parsed'
        if path.endswith('.json'):
            try: json.loads(content)
            except ValueError as error: raise ValueError(f'Invalid JSON in {path}: {error}')
            return 'json parsed'
        if path.endswith('.js'):
            scratch = self.base / 'syntax'; scratch.mkdir(exist_ok=True)
            probe = scratch / (uuid.uuid4().hex + '.js'); probe.write_text(content, encoding='utf-8')
            try:
                # Parses only; node --check never runs the file.
                done = subprocess.run(['node', '--check', str(probe)], capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except (OSError, subprocess.TimeoutExpired) as error: raise ValueError(f'JavaScript syntax could not be checked for {path}: {error}')
            finally:
                try: probe.unlink()
                except OSError: pass
            if done.returncode: raise ValueError(f'JavaScript syntax error in {path}: ' + done.stderr.replace(str(probe), path)[:400])
            return 'javascript syntax parsed'
        return 'no syntax check for this file type'

    def stage(self, request):
        with self.lock:
            turn = next((t for t in self.turns() if t['id'] == request.get('turn')), None)
            job = self._job(turn['jobId']) if turn and turn.get('jobId') else None
            if not job or job['status'] != 'COMPLETED': raise ValueError('Only a saved completed Debug reply can be staged.')
            proposal = self.proposal(self._text(job['id']))
            changes = proposal['changes']; checks = {}
            if not 1 <= len(changes) <= 6 or any(not isinstance(c, dict) or not isinstance(c.get('path'), str) or not isinstance(c.get('content'), str) for c in changes):
                raise ValueError('A repair proposal needs 1 to 6 {path, beforeSha256, content} changes.')
            diff = []
            for change in changes:
                target = maintenance.allowed_source(self.root, change['path'])
                checks[change['path']] = self.check(change['path'], change['content'])
                before = target.read_text(encoding='utf-8') if target.is_file() else ''
                diff += difflib.unified_diff(before.splitlines(), change['content'].splitlines(), 'a/' + change['path'], 'b/' + change['path'], lineterm='')
            manifest = maintenance.stage(self.root, changes, origin={'turn': turn['id'], 'job': job['id'], 'model': turn['model'], 'summary': str(proposal.get('summary') or '')[:600]})
            folder = maintenance.folder(self.root) / 'repairs' / manifest['id']
            (folder / 'CHANGES.diff').write_text('\n'.join(diff), encoding='utf-8')
            manifest['checks'] = checks; maintenance.durable(folder / 'MANIFEST.json', manifest)
        return self.state()

    def diff(self, request):
        path = maintenance.manifest_path(self.root, request.get('repair')).parent / 'CHANGES.diff'
        return {'repair': request.get('repair'), 'diff': path.read_text(encoding='utf-8') if path.is_file() else ''}

    def blockers(self):
        """Actual busy/uncertain state that forbids replacing source."""
        out = []
        if any(j['status'] in BUSY for j in self.jobs.status()): out.append('a Debug invocation is running')
        if self.control:
            jobs = [j for j in self.control.providers.status() if j['status'] in BUSY + ('UNKNOWN',)]
            if jobs: out.append(f'{len(jobs)} provider job(s) active or UNKNOWN')
        if self.services:
            if any(j['status'] in ('queued', 'running') for j in self.services.jobs()): out.append('local assistant job active')
            dictation = getattr(self.services, 'dictation', None)
            if dictation and dictation.snapshot().get('status') not in ('idle', 'error'): out.append('dictation session active')
            try:
                index = json.loads((Path(self.services.engine.base) / 'INDEX.json').read_text(encoding='utf-8'))
                if any(j.get('status') in BUSY for j in index): out.append('local media job active')
            except FileNotFoundError: pass
            except (OSError, ValueError, AttributeError): out.append('local media job state unreadable')
        if self.editor:
            for path in Path(self.editor.root).glob('exports/*/job.json'):
                try:
                    if json.loads(path.read_text(encoding='utf-8')).get('status') in ('queued', 'running'): out.append('editor export active'); break
                except (OSError, ValueError): out.append('editor export state unreadable'); break
        if self.native and self.native.status()['unresolved']: out.append('unresolved native bridge command')
        if self.production and self.control:
            from production_gateway import unresolved
            with closing(self.control.connection()) as db: projects = self.control.projects(db)
            for run in self.production.rows():
                paused = bool(projects.get(run['project'], {}).get('productionControl', {}).get('paused'))
                if not paused and run.get('state') not in SETTLED_RUNS: out.append(f"production run {run['id'][:8]} is {run.get('state')} and not paused")
                try:
                    if run.get('projectRoot') and Path(run['projectRoot']).is_dir() and unresolved(run['projectRoot']): out.append(f"unsettled gateway request for run {run['id'][:8]}")
                except (OSError, ValueError, KeyError): out.append(f"gateway state unreadable for run {run['id'][:8]}")
        return out

    def apply(self, request):
        with self.lock:
            maintenance.apply(self.root, request.get('repair'), self.blockers)
        return self.state()

    def discard(self, request):
        maintenance.discard(self.root, request.get('repair'))
        return self.state()

    # ---- guarded desktop: operator-only; models get observation through the scoped gateway, never input ----
    def desktop(self):
        from guarded_desktop import GuardedDesktop
        return GuardedDesktop(self.root)

    def desktop_observe(self, request):
        desktop = self.desktop()
        try: record = desktop.observe(request.get('target') or 'neural-studio-2')
        except (OSError, ctypes.ArgumentError) as error: raise ValueError('Capture failed; no observation was recorded: ' + str(error))
        return {'observation': record, 'image': desktop.image(record)['data'] if request.get('image') else None}

    def desktop_act(self, request):
        # Input never competes with a native command or an uncertain job.
        busy = lambda: [b for b in self.blockers() if 'native' in b or 'UNKNOWN' in b or 'gateway' in b]
        return self.desktop().act(request, busy)

    def action(self, request):
        handler = {'state': lambda r: self.state(), 'ask': self.ask, 'cancel': self.cancel, 'stage': self.stage, 'diff': self.diff,
                   'apply': self.apply, 'discard': self.discard, 'blockers': lambda r: {'blockers': self.blockers()},
                   'desktop-observe': self.desktop_observe, 'desktop-act': self.desktop_act}.get(request.get('action'))
        if not handler: raise ValueError('Unknown Debug action.')
        return handler(request)

    def shutdown(self):
        self.jobs.shutdown()
