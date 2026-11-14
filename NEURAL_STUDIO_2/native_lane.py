"""Cooperative AE ownership record; never launches AE or submits a native command.

TonyFX remains the final receiver. Unrelated producers cannot be fenced by this
record: the human-authorized director must retain exclusive bridge ownership.
"""
from contextlib import closing
import json
import socket
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4


class NativeLane:
    def __init__(self, root, bridge=None):
        self.db = Path(root) / 'data/native-ownership.sqlite3'
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.bridge = Path(bridge or Path.home() / 'Documents/ae-mcp-bridge')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS owner (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')

    def status(self):
        state = {}
        for key, name in [('command','ae_command.json'),('result','ae_mcp_result.json')]:
            path = self.bridge / name
            try: state[key] = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else None
            except (OSError, ValueError): state[key] = {'unreadable': True}
        c, r = state['command'] or {}, state['result'] or {}
        state['unresolved'] = bool(c.get('unreadable') or r.get('unreadable') or c.get('status') in ('pending','running') or (c.get('id') and r.get('_commandId') != c['id']))
        with closing(sqlite3.connect(self.db)) as db, db:
            row = db.execute('SELECT body FROM owner WHERE id=1').fetchone()
        state['owner'] = json.loads(row[0]) if row else None
        state['integration'] = 'External TonyFX writer; cooperative exclusive ownership. No automatic native dispatch or lease expiry.'
        return state

    def claim(self, owner, project, old_disabled):
        if not all(isinstance(x,str) and x.strip() and len(x)<=200 for x in (owner,project)):
            raise ValueError('Provide owner and exact production project identity.')
        if old_disabled is not True: raise ValueError('Original Neural must be confirmed stopped before claiming AE.')
        # An open port proves the old scheduler may still be alive; refuse it.
        with socket.socket() as probe:
            probe.settimeout(.3)
            if probe.connect_ex(('127.0.0.1',8767)) == 0: raise ValueError('Original Neural service is still running.')
        if self.status()['unresolved']: raise ValueError('Native outcome unresolved. Reconcile existing command; never replay it.')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM owner').fetchone(): raise ValueError('AE already has an owner; explicit safe release is required.')
            row = {'id':uuid4().hex,'owner':owner,'project':project,'claimed':datetime.now(timezone.utc).isoformat()}
            db.execute('INSERT INTO owner VALUES(1,?)',(json.dumps(row),))
        return row

    def release(self, identity):
        if self.status()['unresolved']: raise ValueError('Cannot release unresolved native execution.')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM owner WHERE id=1').fetchone()
            if not row or json.loads(row[0])['id'] != identity: raise ValueError('Exact writer ownership ID required.')
            db.execute('DELETE FROM owner WHERE id=1')
        return {'released':True}
