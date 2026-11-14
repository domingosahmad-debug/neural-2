"""Bounded storage policy and honest measurement. This module NEVER deletes or moves anything.

* Default application/package ceiling: 10,000,000,000 bytes (decimal), configurable.
* Reports logical size, managed (cache/scratch) vs protected (projects, media, notes, sessions, referenced or
  active/UNKNOWN/pending jobs, recent renders) bytes separately. Logical size is not physical freeable space:
  hardlinks, compression and dedupe may differ; an optional allocation estimate is labelled with its source.
* Editing scratch, cache, sources and renders are NOT capped by the application package limit.
  This module measures existing data and offers no deletion endpoint.
* Changing a root only records the preference; existing media is never silently relocated.
"""
from __future__ import annotations
import ctypes
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

DEFAULT_BUDGET = 10_000_000_000
SMALL_ALLOWANCE = 32_000_000        # tiny essential artifacts are never refused for being over budget
MEASURE_SECONDS = 20                # bounded walk per refresh; partial results are labelled
ACTIVE_JOB_STATES = {'QUEUED', 'RUNNING', 'CANCELLING', 'UNKNOWN', 'NEEDS_ATTENTION', 'WAITING', 'PENDING', 'WAITING_LOCAL', 'PAUSED'}
HEX32 = re.compile(r'[a-f0-9]{32}')
# Folders (relative to app root) that hold cache/scratch the budget manages.
MANAGED = [
    ('local-ops-jobs', 'Local-ops jobs and scratch', 'data/local-ops/jobs'),
    ('local-ops-cache', 'Local-ops cache', 'data/local-ops/cache'),
    ('screenshots', 'Director screenshots', 'data/command/images'),
    ('director-runs', 'Director run logs', 'data/command/director-runs'),
    ('tool-results', 'Saved tool results', 'data/command/tool-results'),
    ('helper-audio', 'Helper audio scratch', 'data/helper'),
    ('provider-cache', 'Provider metadata cache', 'data/provider-cache'),
    ('cutroom-proxies', 'Cut-room proxies', 'data/cutroom/proxies'),
    ('runtime', 'Runtime scratch', '.runtime'),
    ('qa', 'QA scratch', '.qa'),
]
# Everything else under data/ plus these are retained, never auto-managed.
PROTECTED_NAMES = ['data/projects', 'data/jobs', 'data/team', 'data/production', 'data/command/STATE.json', 'data/lumen-editor', 'data/workflow-apprentice',
                   'data/cutroom/documents', 'knowledge', 'shared', 'stations']


def _alloc_size(path: str) -> int | None:
    if os.name != 'nt':
        return None
    try:
        high = ctypes.c_ulong(0)
        low = ctypes.windll.kernel32.GetCompressedFileSizeW(ctypes.c_wchar_p(path), ctypes.byref(high))
        if low == 0xFFFFFFFF and ctypes.GetLastError() != 0:
            return None
        return (high.value << 32) + low
    except Exception:
        return None


def walk_size(path: Path, deadline: float, seen: set | None = None, allocation: bool = True, legacy: dict | None = None, root: Path | None = None, exclude_dirs: set | None = None) -> dict:
    """Logical (and optional allocated) bytes under path without following links. Bounded by deadline."""
    seen = seen if seen is not None else set()
    logical = alloc = files = legacy_bytes = 0
    partial = False
    stack = [str(path)]
    while stack:
        if time.monotonic() > deadline:
            partial = True
            break
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                for e in it:
                    try:
                        if e.is_symlink() or (hasattr(e, 'is_junction') and e.is_junction()):
                            continue
                        if e.is_dir(follow_symlinks=False):
                            if exclude_dirs and e.name in exclude_dirs:
                                continue
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat(follow_symlinks=False)
                            key = (st.st_dev, st.st_ino)
                            files += 1
                            logical += st.st_size
                            if legacy is not None and root is not None:
                                old = legacy.get(Path(e.path).relative_to(root).as_posix())
                                if old == [st.st_size, st.st_mtime_ns, st.st_ino]:
                                    legacy_bytes += st.st_size
                            if st.st_ino and key in seen:
                                continue          # hardlink already counted for allocation
                            if st.st_ino:
                                seen.add(key)
                            if allocation:
                                a = _alloc_size(e.path)
                                alloc += a if a is not None else st.st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return {'logical_bytes': logical, 'allocated_bytes': alloc if allocation else None, 'files': files, 'partial': partial,
            'legacy_bytes': legacy_bytes, 'budgeted_bytes': logical - legacy_bytes}


class StoragePolicy:
    def __init__(self, root, clock=time.time):
        self.root = Path(root).resolve()
        self.base = self.root / 'data' / 'storage'
        self.policy_path = self.base / 'POLICY.json'
        self.measure_path = self.base / 'MEASURE.json'
        self.clock = clock
        self.lock = threading.RLock()
        self.refreshing = False

    # ---------------------------------------------------------------- policy
    def policy(self) -> dict:
        try:
            value = json.loads(self.policy_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            value = {}
        return {'budget_bytes': int(value.get('budget_bytes') or DEFAULT_BUDGET), 'cache_root': value.get('cache_root'), 'project_root': value.get('project_root'),
                'retention_days': int(value.get('retention_days') or 30), 'updated_at': value.get('updated_at'),
                'previous_roots': value.get('previous_roots', []), 'default_budget_bytes': DEFAULT_BUDGET,
                'relocation': 'Root fields are saved preferences only; automatic relocation and alternate-root writers are not implemented. All current data stays at its original path.'}

    def set_policy(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise ValueError('Expected an object')
        unknown = set(data) - {'budget_bytes', 'cache_root', 'project_root', 'retention_days'}
        if unknown:
            raise ValueError('Unknown storage policy field: ' + ', '.join(sorted(unknown)))
        current = self.policy()
        new = {k: current[k] for k in ('budget_bytes', 'cache_root', 'project_root', 'retention_days')}
        if 'budget_bytes' in data:
            b = data['budget_bytes']
            if type(b) is not int or not 100_000_000 <= b <= 10_000_000_000_000:
                raise ValueError('budget_bytes must be an integer between 100000000 and 10000000000000')
            new['budget_bytes'] = b
        if 'retention_days' in data:
            d = data['retention_days']
            if type(d) is not int or not 1 <= d <= 3650:
                raise ValueError('retention_days must be an integer from 1 to 3650')
            new['retention_days'] = d
        previous = list(current['previous_roots'])
        for key in ('cache_root', 'project_root'):
            if key in data:
                v = data[key]
                if v is None or v == '':
                    new[key] = None
                    continue
                if not isinstance(v, str) or len(v) > 600 or '\x00' in v:
                    raise ValueError(key + ' must be a path string')
                p = Path(v)
                if not p.is_absolute():
                    raise ValueError(key + ' must be an absolute folder path')
                resolved = p.resolve()
                for protected in ('knowledge', 'shared', 'stations', 'app', 'web'):
                    if resolved.is_relative_to((self.root / protected).resolve()):
                        raise ValueError(key + ' cannot be inside the application source/knowledge folders')
                if resolved.exists() and not resolved.is_dir():
                    raise ValueError(key + ' must be a folder')
                if current[key] and current[key] != str(resolved):
                    previous.append({'key': key, 'path': current[key], 'replaced_at': time.strftime('%Y-%m-%dT%H:%M:%S')})
                new[key] = str(resolved)
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.policy_path.with_name(self.policy_path.name + '.' + uuid.uuid4().hex + '.tmp')
        tmp.write_text(json.dumps({**new, 'previous_roots': previous[-20:], 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S')}, indent=2), encoding='utf-8')
        tmp.replace(self.policy_path)
        return self.status()

    # ------------------------------------------------------------ references
    def live_references(self) -> dict[str, str]:
        """32-hex IDs that active state still points at (job watches, production plans, pending commands)."""
        refs: dict[str, str] = {}

        def scan(path: Path, why: str):
            try:
                if path.is_file() and path.stat().st_size < 8_000_000:
                    for m in HEX32.findall(path.read_text(encoding='utf-8', errors='ignore')):
                        refs.setdefault(m, why)
            except OSError:
                pass
        scan(self.root / 'data/command/STATE.json', 'director watch/session state')
        scan(self.root / 'data/production/CURRENT.json', 'current production plan')
        scan(self.root / 'data/lumen-editor/STATE.json', 'Lumen editor state')
        for p in sorted((self.root / 'data/jobs').glob('*/JOB.json'))[-80:]:
            scan(p, 'station job record')
        for p in sorted((self.root / 'data/cutroom/documents').glob('*.json'))[:50]:
            scan(p, 'cutroom timeline document')
        for p in sorted((self.root / 'data/cutroom/apply').glob('*.json'))[:50]:
            scan(p, 'cutroom apply record')
        return refs

    def job_protection(self, job_dir: Path, refs: dict, cutoff: float) -> str | None:
        """Reason this local-ops job must not be a cleanup candidate, or None."""
        status = None
        for name in ('JOB.json', 'job.json', 'SUMMARY.json'):
            try:
                status = json.loads((job_dir / name).read_text(encoding='utf-8')).get('status')
                break
            except (OSError, ValueError):
                continue
        if status is None:
            return 'state unreadable: treated as UNKNOWN'
        if str(status).upper() in ACTIVE_JOB_STATES:
            return 'active/UNKNOWN/pending: ' + str(status)
        if job_dir.name in refs:
            return 'referenced by ' + refs[job_dir.name]
        try:
            if job_dir.stat().st_mtime >= cutoff:
                return 'inside the retention window (last-month renders and results)'
        except OSError:
            return 'state unreadable: treated as UNKNOWN'
        return None

    # ------------------------------------------------------------ measurement
    def measure(self, max_seconds: float = MEASURE_SECONDS, allocation: bool = True) -> dict:
        deadline = time.monotonic() + max_seconds
        pol = self.policy()
        cutoff = self.clock() - pol['retention_days'] * 86400
        refs = self.live_references()
        legacy = {}
        groups = []
        managed_paths = set()
        seen: set = set()
        for gid, label, rel in MANAGED:
            folder = self.root / rel
            managed_paths.add(folder.resolve())
            if not folder.exists():
                continue
            protected = 0
            candidates = []
            if gid == 'local-ops-jobs':
                total = {'logical_bytes': 0, 'allocated_bytes': 0, 'files': 0, 'partial': False, 'legacy_bytes': 0, 'budgeted_bytes': 0}
                for job in sorted(p for p in folder.iterdir() if p.is_dir()):
                    m = walk_size(job, deadline, seen, allocation, legacy, self.root)
                    for k in ('logical_bytes', 'files', 'legacy_bytes', 'budgeted_bytes'):
                        total[k] += m[k]
                    total['allocated_bytes'] += m['allocated_bytes'] or 0
                    total['partial'] = total['partial'] or m['partial']
                    reason = self.job_protection(job, refs, cutoff)
                    if reason:
                        protected += m['logical_bytes']
                    else:
                        candidates.append({'id': job.name, 'bytes': m['logical_bytes'], 'age_days': round((self.clock() - job.stat().st_mtime) / 86400, 1)})
                total['allocated_bytes'] = total['allocated_bytes'] if allocation else None
                m = total
                candidates.sort(key=lambda c: c['bytes'], reverse=True)
            else:
                m = walk_size(folder, deadline, seen, allocation, legacy, self.root)
                if gid in ('screenshots',):
                    protected = m['logical_bytes']   # referenced by director history; never auto-cleaned
            is_prot = bool(protected and protected >= m['logical_bytes'] and m['logical_bytes'] > 0)
            groups.append({'id': gid, 'label': label, 'path': rel, 'managed': True, 'protected': is_prot,
                           'kind': 'protected' if is_prot else 'managed', 'bytes': m['logical_bytes'],
                           'logical_bytes': m['logical_bytes'], 'allocated_bytes': m['allocated_bytes'],
                           'legacy_bytes': m['legacy_bytes'], 'budgeted_bytes': m['budgeted_bytes'],
                           'files': m['files'], 'protected_bytes': protected, 'reclaimable_bytes': max(0, m['logical_bytes'] - protected),
                           'cleanup_candidates': candidates[:20], 'partial': m['partial']})
        # Retained project/media/state: everything else under data/.
        retained = 0
        retained_files = 0
        partial = False
        data = self.root / 'data'
        if data.is_dir():
            for child in sorted(data.iterdir()):
                if not child.is_dir() or child.resolve() in managed_paths:
                    continue
                if child.name in ('local-ops', 'command', 'cutroom'):
                    for sub in sorted(child.iterdir()):
                        if sub.resolve() in managed_paths:
                            continue
                        m = walk_size(sub, deadline, seen, False) if sub.is_dir() else {'logical_bytes': sub.stat().st_size, 'files': 1, 'partial': False}
                        retained += m['logical_bytes']
                        retained_files += m['files']
                        partial = partial or m['partial']
                    continue
                m = walk_size(child, deadline, seen, False)
                retained += m['logical_bytes']
                retained_files += m['files']
                partial = partial or m['partial']
        groups.append({'id': 'retained-projects-media', 'label': 'Retained projects, media, notes and sessions', 'path': 'data/*', 'managed': False,
                       'protected': True, 'kind': 'protected', 'bytes': retained, 'logical_bytes': retained,
                       'allocated_bytes': None, 'files': retained_files, 'protected_bytes': retained, 'reclaimable_bytes': 0, 'cleanup_candidates': [], 'partial': partial})
        app_bytes = 0
        for rel in ('app', 'web', 'tools', 'desktop', 'knowledge', 'shared', 'stations'):
            f = self.root / rel
            if f.is_dir():
                # The portable exporter includes station instructions, never their
                # production tasks/inboxes. These remain protected workflow data.
                excluded = {'tasks', 'inbox'} if rel == 'stations' else {'__pycache__', 'node_modules', '.git', '.runtime', '.qa', '.history', '.venv'}
                m = walk_size(f, deadline, seen, False, exclude_dirs=excluded)
                app_bytes += m['logical_bytes']
                partial = partial or m['partial']
        # The installed Electron folder can be a junction into the shared runtime.
        # Inspect this exact required runtime separately, excluding its duplicate dev exe.
        runtime = self.root / '.tools/node_modules/electron/dist'
        if runtime.is_dir():
            omit_dev = (runtime / 'Neural Posthouse.exe').is_file()
            for p in runtime.rglob('*'):
                if time.monotonic() > deadline:
                    partial = True; break
                if p.is_file() and not (omit_dev and p.name == 'electron.exe'):
                    app_bytes += p.stat().st_size
        groups.append({'id': 'application', 'label': 'Application code and knowledge', 'path': 'app, web, tools, knowledge, ...', 'managed': False,
                       'protected': True, 'kind': 'protected', 'bytes': app_bytes, 'logical_bytes': app_bytes,
                       'allocated_bytes': None, 'files': None, 'protected_bytes': app_bytes, 'reclaimable_bytes': 0, 'cleanup_candidates': [], 'partial': partial})
        result = {'measured_at': self.clock(), 'groups': groups, 'partial': any(g['partial'] for g in groups), 'refs_considered': len(refs),
                  'allocation': {'source': 'GetCompressedFileSizeW with hardlink de-duplication' if os.name == 'nt' else 'not measured on this OS',
                                 'confidence': 'medium: reflects compression/sparse files, not NTFS dedupe, reparse points or shadow copies'}}
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.measure_path.with_name(self.measure_path.name + '.' + uuid.uuid4().hex + '.tmp')
        tmp.write_text(json.dumps(result), encoding='utf-8')
        tmp.replace(self.measure_path)
        return result

    def refresh_async(self):
        with self.lock:
            if self.refreshing:
                return False
            self.refreshing = True

        def run():
            try:
                self.measure()
            except Exception:
                pass
            finally:
                with self.lock:
                    self.refreshing = False
        threading.Thread(target=run, daemon=True, name='storage-measure').start()
        return True

    def status(self, fresh: bool = False) -> dict:
        pol = self.policy()
        if fresh:
            measured = self.measure()
        else:
            try:
                measured = json.loads(self.measure_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                measured = None
            if measured is None:
                measured = self.measure(max_seconds=2.0)
                if measured.get('partial'):
                    self.refresh_async()
            elif self.clock() - measured.get('measured_at', 0) > 900:
                self.refresh_async()
        if measured is None:
            return {'budget_bytes': pol['budget_bytes'], 'managed_bytes': None, 'protected_bytes': None, 'total_logical_bytes': None, 'over_budget': None, 'policy': pol,
                    'groups': [], 'measuring': True, 'detail': 'First measurement is running in the background; no files are changed. Poll again shortly.'}
        groups = measured['groups']
        managed = sum(g['logical_bytes'] for g in groups if g['managed'])
        budgeted = sum(g.get('budgeted_bytes', g['logical_bytes']) for g in groups if g['managed'])
        legacy = sum(g.get('legacy_bytes', 0) for g in groups if g['managed'])
        managed_protected = sum(g['protected_bytes'] for g in groups if g['managed'])
        protected = sum(g['protected_bytes'] for g in groups)
        total = sum(g['logical_bytes'] for g in groups)
        app_bytes = next((g['logical_bytes'] for g in groups if g['id'] == 'application'), 0)
        over = app_bytes > pol['budget_bytes']
        detail = ('Sizes are LOGICAL bytes, not physical freeable space (hardlinks/compression may differ). Nothing is deleted automatically. ')
        detail += 'The 10 GB ceiling applies ONLY to the downloadable application and bundled runtimes. Footage, renders, sessions, cache and workflow data are separate and are never limited by this policy. No cleanup has been performed. '
        if over:
            detail += 'Application payload exceeds the configured package ceiling. Trim release packaging, not editing assets. '
        if measured.get('partial'):
            detail += ' The last measurement hit its time bound and is partial.'
        confidence = 'partial_time_bounded' if measured.get('partial') else 'logical_walk_verified'
        return {'budget_bytes': pol['budget_bytes'], 'managed_bytes': managed, 'budgeted_bytes': app_bytes, 'application_bytes': app_bytes, 'budget_scope': 'application_package_only', 'protected_bytes': protected, 'protected_managed_bytes': managed_protected,
                'total_logical_bytes': total, 'over_budget': over, 'confidence': confidence, 'policy': pol, 'groups': groups,
                'measured_at': measured['measured_at'], 'partial': measured.get('partial', False),
                'allocation': measured.get('allocation'), 'detail': detail, 'measuring': self.refreshing}

    # ------------------------------------------------------------------ guard
    def guard_new_scratch(self, requested_bytes: int, label: str, essential: bool = False) -> dict:
        """Compatibility only: Tony explicitly excludes editing jobs from the app-size ceiling."""
        return {'allowed': True, 'scope': 'application_package_only'}

    def guard_package(self, package_bytes: int):
        if package_bytes > self.policy()['budget_bytes']:
            raise BudgetRefusal('Application package exceeds its size ceiling. Exclude project/media/cache data and optional development assets; do not delete workflow files.', [])
        return {'allowed': True}


class BudgetRefusal(ValueError):
    def __init__(self, message, choices):
        super().__init__(message)
        self.choices = choices
