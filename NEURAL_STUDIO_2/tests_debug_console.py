"""Isolated Debug workspace: own jobs/conversation, bounded context, staged repairs only."""
import json, shutil, tempfile, threading, unittest
from pathlib import Path

import maintenance as m
from debug_console import DebugConsole

MODEL = {'route': 'claude', 'model': 'opus', 'label': 'Opus', 'efforts': ['medium'], 'available': True}


class Transport:
    def __init__(self, text='Plain diagnosis.', block=False):
        self.text = text; self.calls = []; self.block = block; self.release = threading.Event()
    def run(self, row, packet, folder, session, cancel):
        self.calls.append(packet)
        if self.block:
            while not self.release.wait(.01):
                if cancel.is_set(): return {'status': 'CANCELLED', 'session_id': session, 'text': ''}
        return {'status': 'COMPLETED', 'session_id': 'debug-session', 'text': self.text(packet) if callable(self.text) else self.text}


class Providers:
    def __init__(self, rows=()): self.rows = list(rows)
    def status(self): return self.rows


class Control:
    def __init__(self, rows=()): self.providers = Providers(rows)
    def capabilities(self): return [MODEL, {'route': 'gemini', 'model': 'g', 'label': 'G', 'efforts': ['high'], 'available': False}]
    def status(self, project): return {'paused': True, 'pauseSettled': True, 'activity': {'state': 'paused'}, 'stations': [{'station': 'Edit', 'state': 'idle', 'model': 'x', 'reason': 'r', 'task': 'SECRET-TASK'}], 'production': {'id': 'run', 'state': 'BLOCKED', 'task': 'SECRET-TASK'}}


class DebugTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.done = threading.Event(); self.consoles = []
        (self.root / 'a.py').write_bytes(b'A = 1\n'); (self.root / 'b.js').write_bytes(b'let b=1;\n'); (self.root / 'big.py').write_bytes(b'#' * 100001)
        (self.root / 'bootstrap.py').write_bytes(b'x=1\n'); (self.root / 'desktop-service.log').write_text('start TOKEN123 end', encoding='utf-8')
    def tearDown(self):
        for c in self.consoles: c.shutdown()
        self.tmp.cleanup()
    def console(self, transport, control=None):
        c = DebugConsole(self.root, control or Control(), transport=transport, secrets=('TOKEN123',))
        c.jobs.on_terminal = lambda row: self.done.set(); self.consoles.append(c); return c
    def ask(self, c, rid='request-0001', **kw):
        self.done.clear()
        state = c.ask({'requestId': rid, 'question': 'Why is it stuck?', 'route': 'claude', 'model': 'opus', 'effort': 'medium', 'project': 'p1', **kw})
        self.assertTrue(self.done.wait(5)); return state
    def proposal(self, changes): return lambda packet: json.dumps({'summary': 'fix', 'diagnosis': 'd', 'changes': changes})

    def test_bounded_context_durable_turn_and_isolated_jobs(self):
        t = Transport(); c = self.console(t); self.ask(c, files=['a.py'])
        packet = t.calls[0]
        self.assertEqual(packet['sources'], [{'path': 'a.py', 'sha256': m.sha(b'A = 1\n'), 'bytes': 6, 'content': 'A = 1\n'}])
        self.assertEqual(packet['requiredCapabilities'], ['text'])
        text = json.dumps(packet); self.assertNotIn('TOKEN123', text); self.assertNotIn('SECRET-TASK', text); self.assertIn('[redacted]', text)
        self.assertTrue((self.root / 'data/debug-runtime/data/provider-jobs').is_dir()); self.assertFalse((self.root / 'data/provider-jobs').exists())
        turn = c.state()['turns'][0]; self.assertEqual((turn['status'], turn['reply']), ('COMPLETED', 'Plain diagnosis.'))
        # Same request ID: same turn, no second invocation, even from a fresh console (restart).
        c.ask({'requestId': 'request-0001'}); c2 = self.console(t); c2.ask({'requestId': 'request-0001'})
        self.assertEqual(len(t.calls), 1); self.assertEqual(len(c2.state()['turns']), 1)

    def test_model_effort_files_and_size_are_enforced(self):
        t = Transport(); c = self.console(t)
        for bad in ({'effort': 'high'}, {'route': 'gemini', 'model': 'g', 'effort': 'high'}, {'files': ['bootstrap.py']}, {'files': ['../x.py']}, {'files': ['big.py']}, {'files': ['a.py', 'a.py']}, {'question': ''}):
            with self.assertRaises(ValueError, msg=bad): c.ask({'requestId': 'request-bad1', 'question': 'q', 'route': 'claude', 'model': 'opus', 'effort': 'medium', **bad})
        self.assertEqual(t.calls, []); self.assertEqual(c.state()['turns'], [])
        self.assertEqual([r['model'] for r in c.state()['capabilities']], ['opus'])
        self.assertNotIn('bootstrap.py', [s['path'] for s in c.state()['sources']])

    def test_one_invocation_at_a_time_and_apply_blocked_while_running(self):
        t = Transport(block=True); c = self.console(t)
        c.ask({'requestId': 'request-0001', 'question': 'q', 'route': 'claude', 'model': 'opus', 'effort': 'medium'})
        with self.assertRaises(ValueError): c.ask({'requestId': 'request-0002', 'question': 'q', 'route': 'claude', 'model': 'opus', 'effort': 'medium'})
        self.assertIn('a Debug invocation is running', c.blockers())
        self.done.clear(); t.release.set(); self.assertTrue(self.done.wait(5)); self.assertEqual(c.blockers(), [])

    def test_stage_checks_show_diff_apply_and_never_execute(self):
        change = [{'path': 'a.py', 'beforeSha256': m.sha(b'A = 1\n'), 'content': 'import os\nA = 2\n'}]
        c = self.console(Transport(self.proposal(change))); turn = self.ask(c, files=['a.py'])['turns'][0]
        state = c.stage({'turn': turn['id']}); repair = state['repairs'][0]
        self.assertEqual((repair['state'], repair['checks']), ('STAGED', {'a.py': 'python syntax parsed'}))
        self.assertEqual((self.root / 'a.py').read_bytes(), b'A = 1\n')                       # staging writes no source
        diff = c.diff({'repair': repair['id']})['diff']; self.assertIn('-A = 1', diff); self.assertIn('+A = 2', diff)
        c.control = Control([{'id': 'j', 'status': 'RUNNING'}])
        with self.assertRaises(m.Refused): c.apply({'repair': repair['id']})
        self.assertEqual((self.root / 'a.py').read_bytes(), b'A = 1\n'); self.assertIsNone(m.reservation(self.root))
        c.control = Control([{'id': 'j', 'status': 'UNKNOWN'}])
        with self.assertRaises(m.Refused): c.apply({'repair': repair['id']})
        c.control = Control(); state = c.apply({'repair': repair['id']})
        self.assertEqual((self.root / 'a.py').read_bytes(), b'import os\nA = 2\n')
        self.assertEqual(state['maintenance']['reservation']['state'], 'RESTART_REQUIRED')
        with self.assertRaises(m.Refused): self.ask(c, rid='request-0002')                    # nothing new until restart

    def test_bad_proposals_are_refused_before_staging(self):
        sha = m.sha(b'A = 1\n')
        cases = [('Plain prose only.', 'no structured'), (self.proposal([{'path': 'a.py', 'beforeSha256': sha, 'content': 'def ('}]), 'syntax'),
                 (self.proposal([{'path': 'bootstrap.py', 'beforeSha256': m.sha(b'x=1\n'), 'content': 'x=2\n'}]), 'Protected'),
                 (self.proposal([{'path': '../evil.py', 'beforeSha256': None, 'content': 'x=2\n'}]), 'rejected'),
                 (self.proposal([{'path': 'a.py', 'beforeSha256': '0' * 64, 'content': 'A = 3\n'}]), 'hash')]
        if shutil.which('node'): cases.append((self.proposal([{'path': 'b.js', 'beforeSha256': m.sha(b'let b=1;\n'), 'content': 'let b = ;'}]), 'JavaScript'))
        for index, (reply, expect) in enumerate(cases):
            c = self.console(Transport(reply)); turn = self.ask(c, rid=f'request-{index:04d}')['turns'][-1]
            with self.assertRaises(ValueError) as caught: c.stage({'turn': turn['id']})
            self.assertIn(expect.lower(), str(caught.exception).lower())
        self.assertEqual(m.manifests(self.root), []); self.assertEqual((self.root / 'a.py').read_bytes(), b'A = 1\n')

    def test_fenced_json_reply_is_parsed_and_discard_works(self):
        body = json.dumps({'summary': 's', 'changes': [{'path': 'a.py', 'beforeSha256': m.sha(b'A = 1\n'), 'content': 'A = 5\n'}]})
        c = self.console(Transport('Here is the fix:\n```json\n' + body + '\n```\n')); turn = self.ask(c)['turns'][0]
        repair = c.stage({'turn': turn['id']})['repairs'][0]
        self.assertEqual(c.discard({'repair': repair['id']})['repairs'], [])
        with self.assertRaises(m.Refused): c.apply({'repair': repair['id']})


if __name__ == '__main__': unittest.main()
