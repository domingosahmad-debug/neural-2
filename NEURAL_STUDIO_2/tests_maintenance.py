"""GF-D01 reservation races and GF-D02 crash recovery for source repair."""
import os;os.environ['NEURAL_AE_DIALOGS']='0'  # fixtures never probe or touch the real desktop
import json, subprocess, sys, tempfile, threading, unittest
from pathlib import Path

import maintenance as m

HERE = Path(__file__).resolve().parent


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / 'a.py').write_text('A = 1\n', encoding='utf-8'); (self.root / 'b.js').write_text('let b=1;\n', encoding='utf-8')
    def tearDown(self): self.tmp.cleanup()
    def staged(self):
        return m.stage(self.root, [{'path': n, 'beforeSha256': m.file_sha(self.root / n), 'content': c} for n, c in (('a.py', 'A = 2\n'), ('b.js', 'let b=2;\n'))])
    def reserve(self): m.durable(m.folder(self.root) / 'RESERVATION.json', {'state': 'RESERVED', 'repair': 'x'})
    def text(self, name): return (self.root / name).read_text(encoding='utf-8')


class Paths(Base):
    def test_protected_traversal_and_non_source_paths_rejected(self):
        for bad in ('bootstrap.py', 'maintenance.py', '../x.py', 'desktop/main.cjs', 'data/x.py', 'a/b/c.py', 'C:/x.py', 'x\\y.py', '.env', 'notes.md', 'runtime/x.py', ''):
            with self.assertRaises(m.Refused, msg=bad): m.allowed_source(self.root, bad)
        self.assertEqual(m.allowed_source(self.root, 'a.py'), self.root.resolve() / 'a.py')
    def test_stage_requires_current_hash_and_a_real_change(self):
        with self.assertRaises(m.Refused): m.stage(self.root, [{'path': 'a.py', 'beforeSha256': '0' * 64, 'content': 'A = 2\n'}])
        with self.assertRaises(m.Refused): m.stage(self.root, [{'path': 'a.py', 'beforeSha256': m.file_sha(self.root / 'a.py'), 'content': (self.root / 'a.py').read_bytes().decode()}])


class Reservation(Base):
    def test_apply_completes_then_blocks_admission_until_restart(self):
        r = self.staged(); done = m.apply(self.root, r['id'], lambda: [])
        self.assertEqual(done['state'], 'COMPLETED'); self.assertEqual(self.text('a.py'), 'A = 2\n')
        self.assertEqual((m.folder(self.root) / 'repairs' / r['id'] / 'backup' / 'a.py').read_text(encoding='utf-8'), 'A = 1\n')
        with self.assertRaises(m.Refused):
            with m.admission(self.root, 'provider'): self.fail('admitted during RESTART_REQUIRED')
        with self.assertRaises(m.Refused): m.apply(self.root, r['id'], lambda: [])       # never twice
        self.assertFalse(m.inspect(self.root)['clean'])
        self.assertTrue(m.inspect(self.root, startup=True)['clean'])                      # restart on the completed tree
        with m.admission(self.root, 'provider'): pass
    def test_work_admitted_first_makes_apply_refuse_without_writing(self):
        r = self.staged(); inside = threading.Event(); release = threading.Event()
        def work():
            with m.admission(self.root, 'editor'): inside.set(); release.wait(5)
        t = threading.Thread(target=work); t.start(); self.assertTrue(inside.wait(2))
        try:
            with self.assertRaises(m.Refused): m.apply(self.root, r['id'], lambda: [], settle=0.3)
        finally: release.set(); t.join()
        self.assertEqual(self.text('a.py'), 'A = 1\n'); self.assertIsNone(m.reservation(self.root))
        self.assertEqual(m.read(m.manifest_path(self.root, r['id']))['state'], 'STAGED')
    def test_apply_reserved_first_makes_work_refuse_without_starting(self):
        r = self.staged(); started = []; calls = []; entered = threading.Event(); release = threading.Event(); out = []
        def idle():
            calls.append(1)
            if len(calls) == 2: entered.set(); release.wait(5)      # holding the reservation, before any write
            return []
        t = threading.Thread(target=lambda: out.append(m.apply(self.root, r['id'], idle))); t.start()
        self.assertTrue(entered.wait(3))
        with self.assertRaises(m.Refused):
            with m.admission(self.root, 'production'): started.append(1)
        self.assertEqual(self.text('a.py'), 'A = 1\n')
        release.set(); t.join(); self.assertEqual(started, []); self.assertEqual(out[0]['state'], 'COMPLETED')
    def test_busy_idle_check_refuses_and_releases(self):
        r = self.staged()
        with self.assertRaises(m.Refused): m.apply(self.root, r['id'], lambda: ['provider job active'])
        self.assertIsNone(m.reservation(self.root)); self.assertEqual(self.text('a.py'), 'A = 1\n')
    def test_source_changed_after_staging_refuses(self):
        r = self.staged(); (self.root / 'b.js').write_text('let b=9;\n', encoding='utf-8')
        with self.assertRaises(m.Refused): m.apply(self.root, r['id'], lambda: [])
        self.assertEqual(self.text('a.py'), 'A = 1\n'); self.assertIsNone(m.reservation(self.root))


class AdmissionPaths(Base):
    """Each real admission entry point refuses under a reservation before reaching its own work."""
    def refused(self, call):
        with self.assertRaises(m.Refused): call()
    def test_provider_submit(self):
        from providers import ProviderJobs
        calls = []; owner = ProviderJobs(self.root, transport=type('T', (), {'run': lambda *a: calls.append(a)})())
        try:
            self.reserve()
            self.refused(lambda: owner.submit({'project': 'p', 'station': 'Edit', 'assignmentId': 'a', 'revision': 1}, 'claude', 'claude-fable-5-2', 'low', 'request-1'))
            self.assertEqual(owner.status(), []); self.assertEqual(calls, [])
        finally: owner.shutdown()
    def test_control_action_but_status_and_pause_still_pass(self):
        from control import Control
        c = object.__new__(Control); c.root = self.root; seen = []; c._action = lambda r: seen.append(r['action'])
        self.reserve()
        self.refused(lambda: c.action({'action': 'start'})); c.action({'action': 'status'}); c.action({'action': 'pause'})
        self.assertEqual(seen, ['status', 'pause'])
    def test_editor_action(self):
        from editor import Editor
        e = object.__new__(Editor); e.app_root = self.root; seen = []; e._action = lambda r: seen.append(r['action'])
        self.reserve()
        self.refused(lambda: e.action({'action': 'export'})); self.refused(lambda: e.action({'action': 'save'})); e.action({'action': 'load'})
        self.assertEqual(seen, ['load'])
    def test_native_gateway_admission(self):
        from production_gateway import ProductionGateway
        g = object.__new__(ProductionGateway); g.root = self.root; seen = []; g._admit = lambda *a: seen.append(a)
        self.reserve(); self.refused(lambda: g._new('r', 'k', {})); self.assertEqual(seen, [])
    def test_local_assistant_and_media_submit(self):
        import services
        s = object.__new__(services.Services); seen = []; s._submit = lambda *a: seen.append(a)
        old = services.ROOT; services.ROOT = self.root
        try:
            self.reserve(); self.refused(lambda: s.submit('think', 'x'))
            source = Path(services.__file__).read_text(encoding='utf-8')
            self.assertIn("with maintenance.admission(ROOT,'local-media'):\n                return self.engine.submit(plan)", source.replace('\r\n', '\n'))
        finally: services.ROOT = old
        self.assertEqual(seen, [])

    def test_dictation_start_and_native_claim_are_gated(self):
        import services
        s = object.__new__(services.Services); seen = []
        s.dictation = type('D', (), {'start': lambda self, **k: seen.append(k)})()
        old = services.ROOT; services.ROOT = self.root
        try:
            self.reserve(); self.refused(lambda: s.action({'action': 'dictate-start'}))
        finally: services.ROOT = old
        self.assertEqual(seen, [])
        source = (HERE / 'studio.py').read_text(encoding='utf-8').replace(chr(13), '')
        self.assertIn("with maintenance.admission(ROOT,'native-claim'): return self.json({'result':native.claim(", source)
    def test_second_launch_never_releases_a_live_process_reservation(self):
        r = self.staged(); m.apply(self.root, r['id'], lambda: [])
        other = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            held = m.reservation(self.root); held['pid'] = other.pid; m.durable(m.folder(self.root) / 'RESERVATION.json', held)
            self.assertFalse(m.inspect(self.root, startup=True)['clean']); self.assertIsNotNone(m.reservation(self.root))
        finally: other.kill(); other.wait()
        self.assertTrue(m.inspect(self.root, startup=True)['clean'])


class Recovery(Base):
    def crash(self):
        r = self.staged()
        def fault(index): raise KeyboardInterrupt()          # process dies after the first replacement
        with self.assertRaises(KeyboardInterrupt): m.apply(self.root, r['id'], lambda: [], fault=fault)
        return r['id']
    def test_fault_after_first_replacement_leaves_detectable_mixed_tree(self):
        rid = self.crash()
        self.assertEqual((self.text('a.py'), self.text('b.js')), ('A = 2\n', 'let b=1;\n'))
        state = m.inspect(self.root, startup=True)             # startup never clears or replays it
        self.assertFalse(state['clean']); self.assertEqual((state['pending'][0]['state'], state['pending'][0]['tree']), ('APPLYING', 'mixed'))
        with self.assertRaises(m.Refused):
            with m.admission(self.root, 'production'): self.fail('production admitted during recovery')
        with self.assertRaises(m.Refused): m.reconcile(self.root, rid)   # mixed cannot be accepted
        with self.assertRaises(m.Refused): m.apply(self.root, rid, lambda: [])
        self.assertTrue((m.folder(self.root) / 'repairs' / rid / 'backup' / 'b.js').is_file())
        m.restore(self.root, rid)
        self.assertEqual((self.text('a.py'), self.text('b.js')), ('A = 1\n', 'let b=1;\n'))
        self.assertTrue(m.inspect(self.root)['clean']); self.assertEqual(m.read(m.manifest_path(self.root, rid))['state'], 'RESTORED')
        self.assertTrue((m.folder(self.root) / 'repairs' / rid / 'backup' / 'a.py').is_file())   # backups preserved
    def test_write_error_is_unknown_partial_and_tampered_backup_blocks_restore(self):
        r = self.staged()
        def fault(index): raise OSError('disk')
        with self.assertRaises(m.Refused): m.apply(self.root, r['id'], lambda: [], fault=fault)
        self.assertEqual(m.inspect(self.root)['pending'][0]['state'], 'UNKNOWN_PARTIAL')
        (m.folder(self.root) / 'repairs' / r['id'] / 'backup' / 'a.py').write_text('evil', encoding='utf-8')
        with self.assertRaises(m.Refused): m.restore(self.root, r['id'])
        self.assertEqual(self.text('a.py'), 'A = 2\n')
    def test_fully_applied_crash_can_be_reconciled_explicitly_only(self):
        r = self.staged()
        def fault(index):
            if index == 1: raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): m.apply(self.root, r['id'], lambda: [], fault=fault)
        self.assertFalse(m.inspect(self.root, startup=True)['clean'])
        self.assertEqual(m.reconcile(self.root, r['id'])['state'], 'RECONCILED_APPLIED'); self.assertTrue(m.inspect(self.root)['clean'])
    def test_bootstrap_enters_recovery_before_importing_the_app(self):
        """A copy of the real bootstrap with a mixed tree serves recovery and never runs studio.py."""
        for name in ('bootstrap.py', 'maintenance.py'): (self.root / name).write_bytes((HERE / name).read_bytes())
        (self.root / 'studio.py').write_text("open('STARTED','w').close()\n", encoding='utf-8')
        self.crash()
        probe = ("import sys,json;import bootstrap;seen=[];"
                 "bootstrap.recovery_server=lambda port:seen.append(port);bootstrap.main(['--port','0']);"
                 "print(json.dumps({'recovery':seen,'modules':[n for n in ('studio','providers','production','control','services','editor') if n in sys.modules]}))")
        done = subprocess.run([sys.executable, '-c', probe], cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {'recovery': [0], 'modules': []}); self.assertFalse((self.root / 'STARTED').exists())
        status = subprocess.run([sys.executable, 'bootstrap.py', '--recover', 'status'], cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertFalse(json.loads(status.stdout)['clean'])
    def test_bootstrap_starts_the_app_when_clean(self):
        for name in ('bootstrap.py', 'maintenance.py'): (self.root / name).write_bytes((HERE / name).read_bytes())
        (self.root / 'studio.py').write_text("import sys;open('STARTED','w').write(' '.join(sys.argv[1:]))\n", encoding='utf-8')
        subprocess.run([sys.executable, 'bootstrap.py', '--port', '0'], cwd=self.root, check=True, timeout=60)
        self.assertEqual((self.root / 'STARTED').read_text(), '--port 0')


if __name__ == '__main__': unittest.main()
