"""Source-maintenance reservation, guarded repair apply and crash recovery.

Standard library only. This file and bootstrap.py are protected: a repair can
never replace them, so the recovery path stays the code that was reviewed.

Contract
- Every production/provider/local/editor/native admission runs inside
  ``admission(root, kind)``. Under one cross-process mutex it refuses when a
  reservation exists, otherwise it leaves a visible in-flight marker until the
  admitted work has been persisted.
- ``apply`` reserves under the same mutex, waits for in-flight admissions to
  become visible, then runs idle checks, verifies hashes, backs up, writes a
  durable APPLYING manifest and only then replaces files one by one.
- Nothing here replays an uncertain repair. An APPLYING or UNKNOWN_PARTIAL
  manifest needs an explicit ``reconcile`` or ``restore``.
"""
import hashlib, json, os, shutil, threading, time, uuid
from contextlib import contextmanager
from pathlib import Path

PROTECTED = ('bootstrap.py', 'maintenance.py')
PROTECTED_DIRS = ('desktop', 'data', 'runtime', 'knowledge', 'docs', '__pycache__')
SOURCE_DIRS = ('', 'providers_engine', 'engine')
SOURCE_SUFFIXES = ('.py', '.js', '.css', '.html')
SOURCE_JSON = ('model_catalog.json',)
UNFINISHED = ('APPLYING', 'UNKNOWN_PARTIAL')
_local = threading.RLock()


class Refused(ValueError):
    """Admission or repair refused; nothing was started or written."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    path = Path(path)
    return sha(path.read_bytes()) if path.is_file() else None


def folder(root):
    path = Path(root) / 'data' / 'maintenance'
    (path / 'inflight').mkdir(parents=True, exist_ok=True)
    (path / 'repairs').mkdir(exist_ok=True)
    return path


def durable(path, value):
    """Write JSON through a same-directory temporary file and fsync it."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=1); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@contextmanager
def mutex(root, timeout=30):
    """Short cross-process critical section. Never held while taking app locks."""
    path = folder(root) / 'mutex.lock'
    with _local:
        stream = open(path, 'a+b')
        try:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    stream.seek(0)
                    if os.name == 'nt':
                        import msvcrt; msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl; fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() > deadline: raise Refused('Maintenance mutex is busy; nothing was started.')
                    time.sleep(0.02)
            try: yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt; msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl; fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def reservation(root):
    path = folder(root) / 'RESERVATION.json'
    if not path.exists(): return None
    try: return read(path)
    except (OSError, ValueError): return {'state': 'UNREADABLE'}


def alive(pid):
    if os.name != 'nt':
        try: os.kill(pid, 0); return True
        except ProcessLookupError: return False
        except OSError: return True
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle: return False
    code = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return bool(ok) and code.value == 259


def inflight(root):
    """Admissions between their reservation check and their visible record."""
    rows = []
    for path in (folder(root) / 'inflight').glob('*.json'):
        try: pid = int(path.name.split('-')[0])
        except ValueError: continue
        if alive(pid): rows.append(path.name)
        else:
            try: path.unlink()
            except OSError: pass
    return rows


@contextmanager
def admission(root, kind):
    """Admit work only while no source repair holds the reservation."""
    base = folder(root)
    marker = base / 'inflight' / f'{os.getpid()}-{uuid.uuid4().hex}.json'
    with mutex(root):
        held = reservation(root)
        if held:
            raise Refused('Source maintenance is ' + ('applied; restart Neural Studio 2 before starting new work.' if held.get('state') == 'RESTART_REQUIRED' else 'in progress; no new work was admitted.'))
        marker.write_text(json.dumps({'kind': kind, 'at': time.time()}), encoding='utf-8')
    try: yield
    finally:
        try: marker.unlink()
        except OSError: pass


def allowed_source(root, relative):
    """Resolved path of a repairable app source file, or Refused."""
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or len(relative) > 200 or '\\' in relative or ':' in relative:
        raise Refused('Source path must be a short relative forward-slash path.')
    parts = relative.split('/')
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts) or len(parts) > 2:
        raise Refused('Path traversal or hidden path rejected: ' + relative)
    parent, name = ('/'.join(parts[:-1]), parts[-1])
    if relative in PROTECTED or parts[0] in PROTECTED_DIRS:
        raise Refused('Protected or non-source path rejected: ' + relative)
    if parent not in SOURCE_DIRS or not (name.endswith(SOURCE_SUFFIXES) or (parent == '' and name in SOURCE_JSON)):
        raise Refused('Only app source files are allowed: ' + relative)
    path = root / relative
    for step in (path, path.parent):
        if step.is_symlink(): raise Refused('Symbolic links are rejected: ' + relative)
    if path.exists() and (not path.is_file() or path.resolve() != path):
        raise Refused('Source path does not resolve to a plain file inside the app: ' + relative)
    return path


def manifests(root):
    rows = []
    for path in sorted((folder(root) / 'repairs').glob('*/MANIFEST.json')):
        try: rows.append(read(path))
        except (OSError, ValueError): rows.append({'id': path.parent.name, 'state': 'UNKNOWN_PARTIAL', 'unreadable': True, 'files': []})
    return rows


def manifest_path(root, repair):
    if not isinstance(repair, str) or len(repair) != 32 or not repair.isalnum(): raise Refused('Unknown repair.')
    path = folder(root) / 'repairs' / repair / 'MANIFEST.json'
    if not path.is_file(): raise Refused('Unknown repair.')
    return path


def stage(root, changes, origin=None):
    """Save immutable proposed files. Callers perform syntax checks first."""
    root = Path(root).resolve()
    if not isinstance(changes, list) or not 1 <= len(changes) <= 6: raise Refused('A repair stages 1 to 6 files.')
    files = []; total = 0; seen = set()
    for change in changes:
        path = allowed_source(root, change.get('path'))
        if change['path'] in seen: raise Refused('Duplicate path in repair.')
        seen.add(change['path'])
        content = change.get('content')
        if not isinstance(content, str): raise Refused('Repair content must be text.')
        data = content.encode('utf-8'); total += len(data)
        before = file_sha(path)
        if change.get('beforeSha256') != before:
            raise Refused('Source changed or hash missing for ' + change['path'] + '; ask again with the current file.')
        if before == sha(data): raise Refused('Repair does not change ' + change['path'] + '.')
        files.append({'path': change['path'], 'before': before, 'after': sha(data), 'bytes': len(data), 'state': 'PENDING', '_data': data})
    if total > 524288: raise Refused('Repair exceeds 512 KB.')
    repair = uuid.uuid4().hex; base = folder(root) / 'repairs' / repair
    for row in files:
        target = base / 'staged' / row['path']; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(row.pop('_data'))
    manifest = {'id': repair, 'state': 'STAGED', 'created': time.time(), 'origin': origin, 'files': files}
    durable(base / 'MANIFEST.json', manifest)
    return manifest


def discard(root, repair):
    path = manifest_path(root, repair); manifest = read(path)
    if manifest['state'] != 'STAGED': raise Refused('Only a staged, unapplied repair can be discarded.')
    manifest.update(state='DISCARDED', finished=time.time()); durable(path, manifest)
    return manifest


def _release(root):
    with mutex(root):
        try: (folder(root) / 'RESERVATION.json').unlink()
        except OSError: pass


def apply(root, repair, idle_check, *, settle=10, fault=None):
    """Replace staged files under the shared reservation.

    idle_check() returns a list of blocking reasons from actual component state.
    fault(index) is a test hook called after each replacement.
    """
    root = Path(root).resolve(); path = manifest_path(root, repair); base = path.parent
    # Unreserved pre-check: a busy app is refused before any reservation can disturb running work.
    early = list(idle_check())
    if early: raise Refused('Not idle; nothing was written: ' + '; '.join(early[:6]))
    with mutex(root):
        if reservation(root): raise Refused('Another source maintenance reservation exists.')
        unfinished = [m['id'] for m in manifests(root) if m.get('state') in UNFINISHED]
        if unfinished: raise Refused('An earlier repair is unfinished or UNKNOWN; reconcile it first: ' + unfinished[0])
        manifest = read(path)
        if manifest['state'] != 'STAGED': raise Refused('Repair is ' + manifest['state'] + '; it is never applied twice.')
        durable(folder(root) / 'RESERVATION.json', {'state': 'RESERVED', 'repair': repair, 'pid': os.getpid(), 'created': time.time()})
    try:
        deadline = time.monotonic() + settle
        while inflight(root):
            if time.monotonic() > deadline: raise Refused('Work is being admitted right now; nothing was written.')
            time.sleep(0.05)
        blockers = list(idle_check())
        if blockers: raise Refused('Not idle; nothing was written: ' + '; '.join(blockers[:6]))
        staged = []
        for row in manifest['files']:
            target = allowed_source(root, row['path'])
            if file_sha(target) != row['before']: raise Refused('Source changed since staging: ' + row['path'] + '. Nothing was written.')
            data = (base / 'staged' / row['path']).read_bytes()
            if sha(data) != row['after']: raise Refused('Staged file changed after review: ' + row['path'] + '. Nothing was written.')
            staged.append((row, target, data))
        for row, target, data in staged:
            if row['before'] is None: continue
            copy = base / 'backup' / row['path']; copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, copy)
            if file_sha(copy) != row['before']: raise Refused('Backup verification failed: ' + row['path'] + '. Nothing was written.')
    except BaseException:
        _release(root); raise
    # Durable intent precedes the first replacement. From here the reservation
    # stays until an explicit outcome exists.
    manifest.update(state='APPLYING', started=time.time()); durable(path, manifest)
    try:
        for index, (row, target, data) in enumerate(staged):
            temporary = target.with_name(target.name + '.neural-repair.tmp')
            with open(temporary, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, target)
            row['state'] = 'REPLACED'; durable(path, manifest)
            if fault: fault(index)
        wrong = [row['path'] for row, target, _ in staged if file_sha(target) != row['after']]
        if wrong: raise OSError('Post-write hash mismatch: ' + wrong[0])
    except Exception as error:
        manifest.update(state='UNKNOWN_PARTIAL', error=str(error)[:300]); durable(path, manifest)
        raise Refused('Repair outcome is UNKNOWN/partial. Backups are preserved; reconcile explicitly, no automatic retry.')
    manifest.update(state='COMPLETED', finished=time.time()); durable(path, manifest)
    durable(folder(root) / 'RESERVATION.json', {'state': 'RESTART_REQUIRED', 'repair': repair, 'pid': os.getpid(), 'created': time.time()})
    return manifest


def classify(root, manifest):
    """Compare each file with its recorded before/after hash."""
    root = Path(root).resolve(); rows = []
    for row in manifest.get('files', []):
        current = file_sha(root / row['path'])
        rows.append({'path': row['path'], 'now': 'after' if current == row['after'] else 'before' if current == row['before'] else 'other'})
    kinds = {r['now'] for r in rows}
    return rows, ('after' if kinds == {'after'} else 'before' if kinds == {'before'} else 'mixed')


def inspect(root, startup=False):
    """Report recovery need. With startup=True, clear only provably benign leftovers."""
    root = Path(root).resolve(); pending = []
    for manifest in manifests(root):
        if manifest.get('state') in UNFINISHED:
            rows, tree = classify(root, manifest)
            pending.append({'id': manifest['id'], 'state': manifest['state'], 'tree': tree, 'files': rows, 'error': manifest.get('error'), 'unreadable': bool(manifest.get('unreadable'))})
    held = reservation(root)
    if startup and held and not pending:
        linked = next((m for m in manifests(root) if m['id'] == held.get('repair')), None)
        # RESERVED without an APPLYING manifest replaced nothing. COMPLETED with
        # every file at its recorded result is the restart this reservation awaited.
        benign = linked and ((held.get('state') == 'RESERVED' and linked['state'] in ('STAGED', 'DISCARDED')) or
                             (held.get('state') == 'RESTART_REQUIRED' and linked['state'] == 'COMPLETED' and classify(root, linked)[1] == 'after'))
        # A live reserving process still owns it: a second launch must not release it.
        if benign and (held.get('pid') == os.getpid() or not alive(int(held.get('pid') or 0))):
            _release(root); held = None
            for marker in (folder(root) / 'inflight').glob('*.json'):
                try:
                    if not alive(int(marker.name.split('-')[0])): marker.unlink()
                except (ValueError, OSError): pass
    return {'clean': not pending and not held, 'reservation': held, 'pending': pending}


def reconcile(root, repair):
    """Explicitly accept a uniform tree. A mixed tree can only be restored."""
    path = manifest_path(root, repair); manifest = read(path)
    if manifest['state'] not in UNFINISHED: raise Refused('Repair is not awaiting reconciliation.')
    tree = classify(root, manifest)[1]
    if tree == 'mixed': raise Refused('Source is mixed; restore the verified backups instead.')
    manifest.update(state='RECONCILED_APPLIED' if tree == 'after' else 'ABANDONED_NOT_APPLIED', reconciled=time.time()); durable(path, manifest)
    _release(root)
    return manifest


def restore(root, repair):
    """Put verified backups back. Refuses if any backup fails its hash."""
    root = Path(root).resolve(); path = manifest_path(root, repair); manifest = read(path); base = path.parent
    if manifest['state'] not in UNFINISHED: raise Refused('Repair is not awaiting recovery.')
    for row in manifest['files']:
        if row['before'] is not None and file_sha(base / 'backup' / row['path']) != row['before']:
            raise Refused('Backup hash mismatch for ' + row['path'] + '; nothing was restored.')
    for row in manifest['files']:
        target = root / row['path']
        if row['before'] is None:
            if target.is_file(): target.unlink()
            continue
        temporary = target.with_name(target.name + '.neural-restore.tmp')
        shutil.copyfile(base / 'backup' / row['path'], temporary); os.replace(temporary, target)
    if classify(root, manifest)[1] != 'before': raise Refused('Restore could not be verified; source left as is.')
    manifest.update(state='RESTORED', reconciled=time.time()); durable(path, manifest)
    _release(root)
    return manifest
