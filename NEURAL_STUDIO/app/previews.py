"""Explicit local review renders, served by opaque ID rather than arbitrary path."""
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


class PreviewCatalog:
    _lock = threading.RLock()

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = (self.root / 'data').resolve()
        self.file = self.base / 'PREVIEWS.json'

    def _read(self):
        try:
            rows = json.loads(self.file.read_text(encoding='utf-8'))
            return rows if isinstance(rows, list) else []
        except (OSError, ValueError):
            return []

    def _path(self, raw):
        p = Path(raw)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        if not p.is_relative_to(self.base) or p.suffix.lower() != '.mp4':
            raise ValueError('Preview must be an MP4 inside the studio data folder')
        if not p.is_file() or p.stat().st_size < 32:
            raise ValueError('Preview video is unavailable or empty')
        return p

    def _kind(self, data, row=None):
        raw = str(data.get('kind', '') or (row or {}).get('kind', '')).strip().lower()
        if raw in ('full', 'proof'):
            return raw
        hay = ' '.join(str(x or '') for x in [
            data.get('title'), data.get('revision'), data.get('path'),
            (row or {}).get('title'), (row or {}).get('revision'), (row or {}).get('path'),
        ]).lower()
        if any(w in hay for w in ('full', 'delivery', '60s', 'master')) and 'proof' not in hay:
            return 'full'
        return 'proof'

    def register(self, data):
        p = self._path(str(data.get('path', '')))
        title = str(data.get('title', '')).strip()[:180]
        revision = str(data.get('revision', '')).strip()[:80]
        if not title or not revision:
            raise ValueError('Preview needs a title and revision')
        # Registration advertises a review artifact, never invents a QA/artistic pass.
        with self._lock:
            rows = self._read()
            row = next((r for r in rows if r.get('path') == str(p.relative_to(self.root))), None)
            if row is None:
                row = {'id': uuid.uuid4().hex}
                rows.append(row)
            project = str(data.get('project_id', ''))[:80]
            kind = self._kind(data, row)
            if data.get('current') is True:
                for other in rows:
                    if other.get('project_id') == project and self._kind({}, other) == kind:
                        other['current'] = False
            row.update(path=str(p.relative_to(self.root)), title=title, revision=revision,
                       kind=kind,
                       note=str(data.get('note', 'Awaiting human review.'))[:1200],
                       project_id=project, current=data.get('current') is True,
                       bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns,
                       registered_at=datetime.now(timezone.utc).isoformat())
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix('.tmp')
            tmp.write_text(json.dumps(rows, indent=2), encoding='utf-8')
            tmp.replace(self.file)
            return self._public(row)

    def _public(self, row):
        kind = self._kind({}, row)
        return {k: v for k, v in row.items() if k not in ('path', 'mtime_ns')} | {
            'kind': kind,
            'kind_label': 'FULL EDIT REVIEW' if kind == 'full' else 'SHORT PROOF',
            'url': '/api/preview-media?id=' + row['id']}

    def media(self, ident):
        if not re.fullmatch(r'[a-f0-9]{32}', ident):
            raise ValueError('Unknown preview')
        with self._lock:
            row = next((r for r in self._read() if r.get('id') == ident), None)
            if not row:
                raise ValueError('Unknown preview')
            p = self._path(row['path'])
            stat = p.stat()
            if stat.st_size != row['bytes'] or stat.st_mtime_ns != row['mtime_ns']:
                raise ValueError('Preview changed since registration; register the completed revision again')
            return p

    def listing(self):
        with self._lock:
            items = []
            for row in reversed(self._read()):
                try:
                    self.media(row['id'])
                    items.append(self._public(row))
                except (OSError, ValueError, KeyError):
                    continue
            return {'previews': items, 'note': 'Review renders only. New revisions appear after rendering and registration.'}
