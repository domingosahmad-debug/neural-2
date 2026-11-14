"""Persistent per-robot/provider/model/workflow conversations; no inference.

Station and project are deliberately NOT identity: a robot carries its own
conversation between assignments. Different robots and providers never share a
mutable provider session. An unresolved owner is never silently discarded.
"""
import hashlib
import json
import re
import threading
from pathlib import Path

_lock = threading.RLock()


def neural_claude_worker_running():
    """True when a Neural-launched Claude worker process may still exist (or that cannot be proven false)."""
    import os
    import subprocess
    try:
        if os.name == 'nt':
            command = ['powershell', '-NoProfile', '-NonInteractive', '-Command',
                       "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'claude|node' } | ForEach-Object { 'P ' + $_.CommandLine }"]
            flags = {'creationflags': 0x08000000}
        else:
            command, flags = ['ps', '-eo', 'args'], {}  # header line keeps stdout non-empty
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, **flags)
        if result.returncode != 0 or not result.stdout.strip():
            return True
        return 'You are a bounded Neural' in result.stdout
    except (OSError, subprocess.SubprocessError):
        return True


class WorkerConversations:
    version = '2026-10-24.1'

    def __init__(self, root):
        self.root = Path(root)
        self.base = self.root / 'data/conversations/workers'

    def identity(self, agent, task):
        workflow = task.get('workflow') or {}
        value = {'agent_id': agent['id'], 'provider': agent['provider'],
                 'model': agent.get('model') or '',
                 'workflow': workflow.get('id', 'tuf')}
        key = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return key, value

    def _path(self, key):
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            raise ValueError('Invalid worker conversation key')
        return self.base / key / 'SESSION.json'

    def _read(self, key):
        from operations import load
        path = self._path(key)
        return load(path) if path.is_file() else {}

    def acquire(self, agent, task, job):
        from operations import save, stamp
        key, identity = self.identity(agent, task)
        with _lock:
            row = self._read(key)
            if (not row.get('owner') and row.get('needs_reconciliation') and self._claude_fork_only(row)):
                # Legacy flag (before 8 Nov 2026): Claude CLI forks --resume to a new ID; the original conversation
                # is intact and its process had stopped. Resume the preserved original ID instead of blocking.
                row['needs_reconciliation'] = False
                row.setdefault('auto_reconciled', []).append({'at': stamp(), 'reason': 'claude-resume-fork', 'kept': row.get('session_id')})
            if row.get('owner') and self._interrupted_owner_stopped(row):
                # 10 Nov 2026: a server restart marks the owner job INTERRUPTED without finish(), so the lock never
                # cleared and every later Claude worker was refused. The job is terminal and no Neural-launched
                # Claude worker process survives: release the lock and keep the saved conversation.
                row.setdefault('auto_reconciled', []).append({'at': stamp(), 'reason': 'interrupted-owner-process-stopped',
                                                              'owner': row.get('owner'), 'kept': row.get('session_id')})
                row.update(owner=None, last_job=row.get('owner'), last_status='INTERRUPTED', updated_at=stamp())
            if row.get('owner') or row.get('needs_reconciliation'):
                raise ValueError('Saved worker conversation needs reconciliation before reuse: '
                                 + str(self._path(key)) + '. No blank replacement was started.')
            row.update(version=self.version, key=key, identity=identity,
                       owner=job['id'], acquired_at=stamp(),
                       current_task=task['id'], current_project=task.get('project_id'),
                       current_workflow_sha256=(task.get('workflow') or {}).get('sha256'))
            work = self._path(key).parent / 'workspace'
            work.mkdir(parents=True, exist_ok=True)
            row['workspace'] = str(work.resolve())
            save(self._path(key), row)
            return {'key': key, 'session_id': row.get('session_id'),
                    'workspace': row['workspace'], 'mode': 'resume' if row.get('session_id') else 'first-use',
                    'record': str(self._path(key).resolve()), 'version': self.version}

    def finish(self, job):
        from operations import save, stamp
        link = job.get('conversation')
        if not link:
            return
        with _lock:
            row = self._read(link['key'])
            if row.get('owner') != job['id']:
                raise ValueError('Worker conversation ownership changed; reconcile before reuse')
            prior, actual = row.get('session_id'), job.get('session_id')
            mismatch = bool(prior and actual and prior != actual)
            # Claude CLI `-p --resume` may return a forked session ID that carries the prior history. When the
            # local process is known stopped and idle, adopt it (keeping the prior ID on record) instead of
            # blocking every later job on a human reconciliation.
            stopped = job.get('process_stopped') is True and job.get('idle_inference') is False
            if mismatch and stopped and row.get('identity', {}).get('provider') == 'claude':
                row.setdefault('previous_session_ids', []).append(prior)
                row['session_id'] = prior = None
                mismatch = False
            missing = bool(prior and any(t in str(job.get('error','')).lower() for t in
                           ('no conversation found', 'session not found', 'no session found', 'could not find session')))
            if actual and not mismatch:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', str(actual)):
                    raise ValueError('Invalid provider session ID')
                row['session_id'] = actual
            # A local process exit alone cannot prove a hosted agent is idle.
            known = not job.get('provider_launch_attempted') or (job.get('process_stopped') is True and job.get('idle_inference') is False)
            row.update(last_job=job['id'], last_status=job.get('status'),
                       last_error=job.get('error'), updated_at=stamp())
            row['needs_reconciliation'] = bool(mismatch or missing or not known or (job.get('provider_launch_attempted') and not row.get('session_id')))
            if mismatch:
                row['last_error'] = 'Provider returned a different conversation ID while resuming; original ID preserved.'
            if known:
                row['owner'] = None
            save(self._path(link['key']), row)
            job['conversation'].update(session_id=row.get('session_id'),
                                       needs_reconciliation=row['needs_reconciliation'],
                                       detail=row.get('last_error') if row['needs_reconciliation'] else None)

    def _interrupted_owner_stopped(self, row):
        if row.get('identity', {}).get('provider') != 'claude' or row.get('needs_reconciliation'):
            return False
        owner = str(row.get('owner') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', owner):
            return False
        try:
            job = json.loads((self.root / 'data/jobs' / owner / 'JOB.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        if job.get('status') != 'INTERRUPTED' or not str(job.get('error') or '').startswith('Server restarted'):
            return False
        return not neural_claude_worker_running()

    @staticmethod
    def _claude_fork_only(row):
        return (row.get('identity', {}).get('provider') == 'claude' and bool(row.get('session_id'))
                and str(row.get('last_error') or '').startswith('Provider returned a different conversation ID while resuming'))

    @staticmethod
    def prompt_note(job):
        return ('\nCONVERSATION CONTINUITY: This robot keeps its own saved provider conversation. '
                'History supplies knowledge, not authorization to repeat earlier work. '
                'Only the CURRENT supplied task, station, project/revision, director and frozen '
                'instructions authorize this turn. Old assignments/results are historical. '
                'Do not copy prior outputs into a new task or claim unperformed work.\n')
