"""Persistent, deduplicated local alerts. No model calls or automatic resends."""
import hashlib
import os
import threading
from pathlib import Path
from operations import load, save, stamp


class AttentionStore:
    lock = threading.RLock()

    def __init__(self, root):
        self.path = Path(root)/'data/attention/STATE.json'

    def snapshot(self):
        with self.lock:
            try:
                return load(self.path)
            except FileNotFoundError:
                return {'items': []}

    def publish(self, key, title, detail, kind='needs_attention'):
        with self.lock:
            state = self.snapshot()
            ident = hashlib.sha256(key.encode()).hexdigest()[:32]
            old = next((r for r in state['items'] if r['id'] == ident), None)
            if old:
                return old  # Reading/restarting/repeated completion is silent.
            row = {'id': ident, 'title': str(title)[:200], 'detail': str(detail)[:4000],
                   'kind': kind, 'created_at': stamp(), 'acknowledged_at': None,
                   'sound': 'not_attempted'}
            if os.name == 'nt' and (self.path.parents[2]/'.runtime/desktop-config.json').is_file():
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION if kind == 'needs_attention' else winsound.MB_OK)
                    row['sound'] = 'system_sound_requested'
                except (RuntimeError, OSError):
                    row['sound'] = 'unavailable'
            state['items'] = [row] + state['items'][:79]
            save(self.path, state)
            return row

    def acknowledge(self, ident):
        with self.lock:
            state = self.snapshot()
            row = next((r for r in state['items'] if r['id'] == ident), None)
            if not row:
                raise ValueError('Unknown alert')
            row['acknowledged_at'] = stamp()
            save(self.path, state)
            return state
