"""Read-only, project-scoped discovery of existing renders. No editor/provider calls."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path


CA02 = 'e4052f1c7b5d415b86acf71a11922795'
# Prior source proofs are reference evidence, not renders of this edit. Never
# import another project's proof list into a current production's Review tab.
LEGACY = {}
MIMES = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.m4v': 'video/mp4'}
SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')


def _inside(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


class ReviewLibrary:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.folder = self.root / 'data' / 'review-library'
        self._lock = threading.RLock()

    def _index(self, project_id):
        if not isinstance(project_id, str) or not SAFE_ID.fullmatch(project_id):
            raise ValueError('Invalid project identifier.')
        return self.folder / (project_id + '.json')

    @staticmethod
    def _read(path):
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            return {}

    def _scopes(self, project_id):
        scopes = [(self.root, project_id)]
        scopes.extend((self.root.parent / 'NEURAL_STUDIO', pid) for pid in LEGACY.get(project_id, ()))
        return scopes

    @staticmethod
    def _files(folder):
        """Never follow directory links/junctions out of the admitted subtree."""
        if not folder.is_dir():
            return
        anchor = folder.resolve()
        for current, dirs, files in os.walk(folder, followlinks=False):
            dirs[:] = [d for d in dirs if _inside((Path(current) / d).resolve(), anchor)]
            for name in files:
                p = Path(current) / name
                if p.suffix.lower() in MIMES and _inside(p.resolve(), anchor):
                    yield p

    def list(self, project_id, project):
        """Refresh registrations; newest existing file is first. project is workspace data."""
        with self._lock:
            index_path = self._index(project_id)
            if not isinstance(project, dict) or project.get('id', project_id) != project_id:
                raise ValueError('Select an existing workspace project.')
            old = self._read(index_path)
            metadata = {}
            candidates = {}
            scopes = self._scopes(project_id)

            def add(path, boundary, label='', source_project=project_id):
                try:
                    path, boundary = Path(path).resolve(), Path(boundary).resolve()
                    if not _inside(path, boundary) or not path.is_file() or path.suffix.lower() not in MIMES:
                        return
                    st = path.stat()
                    if st.st_size == 0:
                        return
                    key = str(path)
                    candidates[key] = dict(id=hashlib.sha256(key.encode()).hexdigest()[:24],
                        label=label or path.stem, path=key,
                        created=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                        bytes=st.st_size, project=project_id, sourceProject=source_project,
                        mime=MIMES[path.suffix.lower()], needsProxy=path.suffix.lower() == '.mov',
                        fingerprint={'size': st.st_size, 'mtime_ns': st.st_mtime_ns},
                        boundary=str(boundary))
                except OSError:
                    return

            for app, owner in scopes:
                project_root = app / 'data' / 'projects' / owner
                # Source footage and project work are deliberately excluded.
                for name in ('render', 'renders', 'reviews', 'exports', 'delivery', 'proof', 'work/renders', 'work/reviews', 'work/exports'):
                    folder = project_root / name
                    if not _inside(folder.resolve(), project_root.resolve()):
                        continue
                    for p in self._files(folder):
                        add(p, project_root, source_project=owner)

                editor_exports = app / 'data' / 'editor' / 'exports'
                for manifest in editor_exports.glob('*/job.json'):
                    if not _inside(manifest.resolve(), editor_exports.resolve()):
                        continue
                    export = self._read(manifest)
                    if export.get('project') == owner and export.get('status') == 'completed':
                        add(manifest.parent / 'output.mp4', manifest.parent,
                            export.get('title', 'Manual Edit export'), owner)

                # Read only job manifests, not every output tree. Persist a slim projection.
                jobs = app / 'data' / 'local-ops' / 'jobs'
                if not _inside(jobs.resolve(), app.resolve()):
                    continue
                for manifest in jobs.glob('*/JOB.json'):
                    if not _inside(manifest.resolve(), jobs.resolve()):
                        continue
                    try:
                        st = manifest.stat()
                    except OSError:
                        continue
                    stamp = [st.st_size, st.st_mtime_ns]
                    cached = metadata.get(str(manifest), old.get('metadata', {}).get(str(manifest), {}))
                    if cached.get('stamp') == stamp and cached.get('discoveryVersion') == 2:
                        entry = cached
                    else:
                        raw = self._read(manifest)
                        entry = {'stamp': stamp, 'discoveryVersion': 2,
                                 'owner': raw.get('project_id') or raw.get('project') or raw.get('notification_project'),
                                 'title': raw.get('title', ''), 'steps': [
                                     {'id': s.get('id'), 'operation': s.get('operation'), 'status': s.get('status'),
                                      'outputs': s.get('outputs', [])} for s in raw.get('steps', [])]}
                    metadata[str(manifest)] = entry
                    if entry.get('owner') != owner:
                        continue
                    for step in entry['steps']:
                        if step['status'] != 'COMPLETED' or step['operation'] not in ('native_render', 'review_copy', 'render', 'export'):
                            continue
                        sid = step.get('id')
                        if not isinstance(sid, str) or not SAFE_ID.fullmatch(sid):
                            continue
                        for output in step.get('outputs', []):
                            if isinstance(output, str):
                                add(manifest.parent / sid / output, manifest.parent,
                                    entry.get('title', '') + (' · native master' if step['operation'] == 'native_render' else ' · review'), owner)

            if project_id == CA02:
                continuation = self.root / 'data' / 'ca02-continuation'
                if _inside(continuation.resolve(), self.root):
                    for name in ('proof', 'renders', 'reviews', 'exports'):
                        for p in self._files(continuation / name):
                            add(p, continuation)

            # Explicit render links in workspace data are admitted only under project roots.
            for link in project.get('links', []):
                if not isinstance(link, dict) or link.get('kind', link.get('type')) not in ('render', 'review', 'export'):
                    continue
                value = link.get('path')
                if not isinstance(value, str):
                    continue
                p = Path(value)
                if not p.is_absolute():
                    p = self.root / p
                for app, owner in scopes:
                    add(p, app / 'data' / 'projects' / owner, link.get('label', ''), owner)

            rows = sorted(candidates.values(), key=lambda r: (r['created'], not r['needsProxy'], r['path']), reverse=True)
            # Keep native originals visible; the browser selects an existing playable review first.
            for row in rows:
                if row['needsProxy']:
                    row['label'] += ' · ProRes master (MP4 review copy plays here)'
                if row['sourceProject'] != project_id:
                    row['label'] += ' · previous source proof'
            selected = next((r['id'] for r in rows if not r['needsProxy']), rows[0]['id'] if rows else None)
            self.folder.mkdir(parents=True, exist_ok=True)
            payload = {'project': project_id, 'versions': rows, 'metadata': metadata}
            temporary = index_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            temporary.replace(index_path)
            return {'project': project_id, 'versions': [{k: v for k, v in r.items() if k not in ('boundary', 'fingerprint')} for r in rows],
                    'latest': selected, 'emptyReason': '' if rows else 'No rendered video is available for this project yet.'}

    def media_path(self, project_id, version_id):
        """Return an unchanged registered file only; never accept a client-supplied path."""
        with self._lock:
            index = self._read(self._index(project_id))
            if not isinstance(version_id, str) or not re.fullmatch(r'[a-f0-9]{24}', version_id):
                raise FileNotFoundError('Unknown render version.')
            row = next((r for r in index.get('versions', []) if r.get('id') == version_id and r.get('project') == project_id), None)
            if not row:
                raise FileNotFoundError('Unknown render version.')
            path, boundary = Path(row['path']), Path(row['boundary'])
            if not _inside(path.resolve(), boundary.resolve()) or path.resolve() != path or not path.is_file():
                raise FileNotFoundError('Render is no longer available.')
            st = path.stat()
            if row.get('fingerprint') != {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}:
                raise FileNotFoundError('Render changed; refresh the version list.')
            return path
