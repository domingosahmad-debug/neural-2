"""Independent, CPU-only services. No AE transport or automatic provider retries."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
MEDIA_OPERATIONS = frozenset(('transcribe_audio','subtitle_extract','music_locate','scout_frames','probe','ingest','assets','frames','frame_range','detect_events',
    'audio_extract','audio_measure','audio_mix','audio_alignment','validate_plan','compare_snapshot',
    'evidence_pack','verify_render','review_copy','batch_inventory','detect_beats','transcript_search','analysis_proxy'))
sys.path.insert(0, str(ROOT / 'engine'))
from dictation import DictationService
from local_engine import LocalEngine, ChildLifetime
from operations import save, load


class Services:
    def __init__(self):
        self.folder = ROOT / 'data' / 'assistant-jobs'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.resource_gate = threading.Lock()
        self.busy = False
        self.outstanding = 0
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='local-assistant')
        self.closed = False
        self.proc = None
        self.events_db = ROOT / 'data' / 'completion-events.sqlite3'
        self.changed = threading.Condition()
        self.version = 0
        with sqlite3.connect(self.events_db) as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, job TEXT UNIQUE, recipient TEXT, body TEXT, acknowledged INTEGER DEFAULT 0)')
        self.engine = LocalEngine(ROOT, on_terminal=self.complete)
        self.dictation = DictationService(runtime_dir=ROOT / 'data/dictation',
            speech_root=ROOT.parent / 'NEURAL_STUDIO', free_mb=lambda: 0,
            busy_check=lambda: 'Original production remains protected; CPU only')
        for file in self.folder.glob('*/job.json'):
            row = load(file)
            if row['status'] in ('running', 'queued'):
                row.update(status='interrupted', error='App closed during execution. Not retried.')
                self.save(row)
        # Reconcile terminal records after a crash between saving a result and notifying.
        for row in self.jobs():
            if row['status'] not in ('queued', 'running'): self.complete(row)
        for row in self.engine.snapshot()['jobs']:
            if row['status'] not in ('QUEUED','RUNNING','CANCELLING'): self.complete(row)

    def signal(self):
        with self.changed:
            self.version += 1
            self.changed.notify_all()

    def complete(self, row):
        body = {'job':row['id'], 'status':row['status'], 'title':row.get('title') or row.get('task'),
                'model':row.get('model', 'Local media engine'), 'recipient':row.get('recipient', 'Director'),
                'project':row.get('project') or row.get('project_id') or row.get('notification_project'), 'error':row.get('error')}
        with sqlite3.connect(self.events_db) as db:
            db.execute('INSERT OR IGNORE INTO events(job,recipient,body) VALUES(?,?,?)',
                       (row['id'], body['recipient'], json.dumps(body)))
        self.signal()

    def inbox(self):
        with sqlite3.connect(self.events_db) as db:
            return [dict(json.loads(body), eventId=key) for key, body in db.execute('SELECT id,body FROM events WHERE acknowledged=0 ORDER BY id')]

    def save(self, row):
        path = self.folder / row['id'] / 'job.json'
        path.parent.mkdir(exist_ok=True)
        save(path, row)
        self.signal()

    def jobs(self):
        return sorted([load(p) for p in self.folder.glob('*/job.json')],
                      key=lambda r: r['created'], reverse=True)

    def submit(self, kind, text, project=None, recipient='Director'):
        import maintenance
        with maintenance.admission(ROOT,'local-assistant'):
            return self._submit(kind, text, project, recipient)

    def _submit(self, kind, text, project=None, recipient='Director'):
        if kind not in ('relay', 'speech') or not isinstance(text, str) or not 0 < len(text.strip()) <= (3500 if kind == 'relay' else 500):
            raise ValueError('Choose Relay (up to 3500 characters) or speech (up to 500 characters).')
        with self.lock:
            if self.closed: raise ValueError('The app is shutting down.')
            if self.outstanding >= 8:
                raise ValueError('The local assistant queue has 8 jobs. Finish existing work before adding more.')
            self.outstanding += 1
        row = dict(id=uuid4().hex, kind=kind, task=text, status='queued', created=time.time(),
                   project=project, recipient=recipient, model='Qwen3 0.6B · CPU' if kind == 'relay' else 'Kokoro 82M · CPU')
        self.save(row)
        try:
            self.executor.submit(self.run, row)
        except Exception:
            with self.lock: self.outstanding -= 1
            raise
        return row

    def run(self, row):
        with self.resource_gate:
            if self.closed:
                row.update(status='interrupted', error='App closed before execution.')
                self.save(row); self.complete(row)
                with self.lock: self.outstanding -= 1
                return
            self.run_admitted(row)

    def run_admitted(self, row):
        proc = None
        lifetime = None
        try:
            row.update(status='running', started=time.time()); self.save(row)
            speech = row['kind'] == 'speech'
            command = [sys.executable, '-u', str(ROOT / 'engine' / ('voice_worker.py' if speech else 'local_voice_worker.py'))]
            if speech: command.append('tts')
            payload = {'id': row['id'], 'text': row['task'], 'voice': 'bm_george'} if speech else {'prompt': row['task']}
            env = dict(os.environ, OMP_NUM_THREADS='2', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            lifetime = ChildLifetime()
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
            lifetime.attach(proc)
            with self.lock:
                self.proc = proc
                if self.closed: proc.kill()
            output, errors = proc.communicate(json.dumps(payload) + '\n', timeout=100)
            folder = self.folder / row['id']
            (folder / 'stderr.txt').write_text(errors, encoding='utf-8')
            replies = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
            if proc.returncode or not replies or replies[-1].get('error'):
                raise ValueError(replies[-1].get('error', 'Worker failed; see saved stderr.') if replies else 'Worker failed; see saved stderr.')
            result = replies[-1]
            if speech:
                (folder / 'speech.wav').write_bytes(base64.b64decode(result.pop('wav')))
                result['audio'] = '/api/audio/' + row['id']
            row.update(status='completed', result=result, finished=time.time())
        except Exception as error:
            if proc and proc.poll() is None:
                proc.kill(); proc.communicate()
            row.update(status='failed', error=str(error), finished=time.time())
        finally:
            if lifetime: lifetime.close()
            self.save(row)
            self.complete(row)
            with self.lock:
                self.busy = False
                self.outstanding -= 1
                self.proc = None

    def action(self, request):
        action = request.get('action')
        if action == 'status':
            media = self.engine.snapshot()
            media['capabilities'] = sorted(MEDIA_OPERATIONS)
            return {'jobs': self.jobs(), 'media': media, 'events':self.inbox(),
                    'concurrency':{'assistantSlots':1, 'mediaSlots':1, 'independentQueues':True, 'nativeWriters':0}, 'dictation': self.dictation.snapshot(),
                    'speech': self.dictation.capabilities()}
        if action == 'acknowledge':
            with sqlite3.connect(self.events_db) as db:
                changed = db.execute('UPDATE events SET acknowledged=1 WHERE id=? AND acknowledged=0', (int(request['eventId']),)).rowcount
            self.signal()
            return {'acknowledged':bool(changed)}
        if action in ('relay', 'speech'): return self.submit(action, request.get('text'), request.get('project'), request.get('recipient', 'Director'))
        if action == 'dictate-start':
            import maintenance
            with maintenance.admission(ROOT,'dictation'): return self.dictation.start(engine_id=request.get('engine'))
        if action == 'dictate-poll': return self.dictation.poll(int(request.get('since', 0)), request.get('session'))
        if action == 'dictate-stop': return self.dictation.stop(request.get('session'))
        if action == 'media-capabilities':
            result = self.engine.capabilities()
            result['operations'] = {k:v for k,v in result['operations'].items() if k in MEDIA_OPERATIONS}
            result['capabilities'] = sorted(MEDIA_OPERATIONS)
            result['recipes'] = {}
            result['limitations'].append('Native dispatch, assembly and preview publication are excluded from this endpoint.')
            return result
        if action == 'media-submit':
            plan = self.engine.validate(request.get('plan'))
            if plan.get('project_id'):
                raise ValueError('Use the request project field; old workbench project linkage is not exposed.')
            plan['notification_project'] = request.get('project')
            if any(s['operation'] not in MEDIA_OPERATIONS for s in plan['steps']):
                raise ValueError('This endpoint accepts mechanical preparation only; native operations are forbidden.')
            # The engine owns all output paths; caller input paths are never output targets.
            import maintenance
            with maintenance.admission(ROOT,'local-media'):
                return self.engine.submit(plan)
        if action == 'media-job': return self.engine.job(request.get('id'))
        if action == 'media-cancel': return self.engine.cancel(request.get('id'))
        if action == 'media-artifact':
            path = self.engine.artifact(request.get('id'), request.get('step'), request.get('filename'))
            if path.suffix.lower() != '.json':
                return {'path':str(path), 'bytes':path.stat().st_size, 'format':'file'}
            if path.stat().st_size > 2_000_000:
                return {'path':str(path), 'bytes':path.stat().st_size, 'format':'json', 'inline':False}
            return {'path':str(path), 'format':'json', 'data':load(path), 'inline':True}
        if action == 'media-result':
            folder = self.engine.folder(request.get('id'))
            job = self.engine.job(request.get('id'))
            if job.get('status') != 'COMPLETED' or any(s['operation'] != 'probe' for s in job['steps']):
                raise ValueError('Completed probe measurements are not available.')
            return load(folder / 'probe' / 'probe.json')
        if action == 'probe':
            path = Path(request.get('path', '')).resolve()
            if not path.is_file(): raise ValueError('Select an existing media file.')
            return self.engine.submit({'version':1, 'title':'Inspect ' + path.name,
                'steps':[{'id':'probe', 'operation':'probe', 'args':{'input':str(path)}}]})
        raise ValueError('Unsupported service action.')

    def shutdown(self):
        with self.lock:
            self.closed = True
            if self.proc and self.proc.poll() is None: self.proc.kill()
        self.dictation.shutdown()
        self.engine.shutdown()
        self.executor.shutdown(wait=False, cancel_futures=True)
