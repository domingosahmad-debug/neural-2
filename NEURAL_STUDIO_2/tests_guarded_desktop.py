"""Guarded desktop: allowlisted observation, fresh-observation input, observe-only AE, no replay."""
import json, tempfile, unittest
from pathlib import Path

from PIL import Image

import maintenance as m
from guarded_desktop import GuardedDesktop
from station_tools import StationTools, TOOLS


class FakeWin:
    def __init__(self, root):
        self.rows = [
            {'hwnd': 11, 'pid': 100, 'title': 'Neural Studio 2', 'exe': str(Path(root).resolve() / 'runtime' / 'electron.exe'), 'rect': [100, 50, 900, 650], 'minimized': False},
            {'hwnd': 22, 'pid': 200, 'title': 'Adobe After Effects', 'exe': r'C:\Program Files\Adobe\AfterFX.exe', 'rect': [0, 0, 400, 300], 'minimized': False},
            {'hwnd': 33, 'pid': 300, 'title': 'Neural Studio', 'exe': r'C:\other\NEURAL_STUDIO\runtime\electron.exe', 'rect': [0, 0, 3000, 2000], 'minimized': False}]
        self.sent = []; self.dialogs = []; self.flat = False; self.front = True; self.cover = None; self.fail = False
    def windows(self): return [dict(r) for r in self.rows]
    def dialog_windows(self): return [dict(d) for d in self.dialogs]
    def click_dialog_ok(self, dlg_hwnd, ok_hwnd): self.sent.append(('dialog_ok', dlg_hwnd, ok_hwnd)); return True
    def show_inactive(self, hwnd): self.rows[0]['minimized'] = False
    def capture(self, hwnd):
        row = next(r for r in self.rows if r['hwnd'] == hwnd); size = (row['rect'][2] - row['rect'][0], row['rect'][3] - row['rect'][1])
        image = Image.new('RGB', size, (10, 10, 10))
        if not self.flat: image.putpixel((1, 1), (250, 250, 250))
        return image
    def foreground(self, hwnd): return self.front
    def root_at(self, x, y): return self.cover or 11
    def click(self, x, y):
        if self.fail: raise RuntimeError('lost')
        self.sent.append(('click', x, y))
    def key(self, code): self.sent.append(('key', code))
    def text(self, value): self.sent.append(('type', value))


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.now = [1000.0]
        self.win = FakeWin(self.root); self.desk = GuardedDesktop(self.root, self.win, clock=lambda: self.now[0])
    def tearDown(self): self.tmp.cleanup()
    def click(self, observation, rid='request-0001', **kw): return self.desk.act({'requestId': rid, 'observation': observation['id'], 'kind': 'click', 'x': 40, 'y': 30, **kw})

    def test_observation_is_exact_target_hashed_and_never_the_original_app(self):
        record = self.desk.observe('neural-studio-2')
        self.assertEqual((record['hwnd'], record['size'], record['inputAllowed']), (11, [800, 600], True))
        self.assertTrue(Path(record['path']).is_file()); self.assertEqual(len(record['sha256']), 64)
        self.assertEqual(self.desk.image(record)['kind'], 'image')
        self.assertEqual(self.desk.observe('after-effects')['inputAllowed'], False)
        with self.assertRaises(ValueError): self.desk.observe('desktop')
        self.win.rows.pop(0)
        with self.assertRaises(ValueError): self.desk.observe('neural-studio-2')      # original Neural is never a match
        self.assertEqual(self.win.sent, [])

    def test_blank_and_minimized_observe_only_windows_are_not_evidence(self):
        self.win.flat = True
        with self.assertRaises(ValueError): self.desk.observe('neural-studio-2')
        self.win.flat = False; self.win.rows[1]['minimized'] = True
        with self.assertRaises(ValueError): self.desk.observe('after-effects')
        self.win.rows[0]['minimized'] = True; self.assertEqual(self.desk.observe('neural-studio-2')['hwnd'], 11)

    def test_click_maps_to_the_window_logs_and_returns_fresh_observation(self):
        first = self.desk.observe(); out = self.click(first)
        self.assertEqual(self.win.sent, [('click', 140, 80)]); self.assertEqual(out['action']['state'], 'DONE'); self.assertNotEqual(out['after']['id'], first['id'])
        states = [json.loads(line)['state'] for line in self.desk.log.read_text().splitlines()]; self.assertEqual(states, ['INTENT', 'DONE'])
        again = self.click(first); self.assertEqual(again['replayed'], False); self.assertEqual(len(self.win.sent), 1)   # same request never sends twice

    def test_after_effects_stale_moved_covered_and_background_are_refused(self):
        ae = self.desk.observe('after-effects')
        with self.assertRaises(ValueError): self.click(ae)
        first = self.desk.observe(); self.now[0] += 16
        with self.assertRaises(ValueError): self.click(first, 'request-0002')
        first = self.desk.observe(); self.win.rows[0]['rect'] = [0, 0, 800, 600]
        with self.assertRaises(ValueError): self.click(first, 'request-0003')
        first = self.desk.observe(); self.win.cover = 99
        with self.assertRaises(ValueError): self.click(first, 'request-0004')
        self.win.cover = None; self.win.front = False
        with self.assertRaises(ValueError): self.click(first, 'request-0005')
        self.win.front = True
        for bad in ({'x': 900}, {'kind': 'key', 'key': 'delete'}, {'kind': 'type', 'text': 'a\nb'}, {'kind': 'drag'}):
            with self.assertRaises(ValueError): self.click(first, 'request-0006', **bad)
        with self.assertRaises(ValueError): self.desk.act({'requestId': 'request-0007', 'observation': first['id'], 'kind': 'click', 'x': 1, 'y': 1}, lambda: ['unresolved native bridge command'])
        self.assertEqual(self.win.sent, [])

    def test_interrupted_input_is_unknown_and_not_replayed(self):
        first = self.desk.observe(); self.win.fail = True
        with self.assertRaises(RuntimeError): self.click(first)
        self.win.fail = False; out = self.click(first)
        self.assertEqual(out['action']['state'], 'UNKNOWN'); self.assertEqual(self.win.sent, [])

    def test_input_waits_out_source_maintenance_and_models_only_get_observe(self):
        first = self.desk.observe(); m.durable(m.folder(self.root) / 'RESERVATION.json', {'state': 'APPLYING', 'pid': 1})
        with self.assertRaises(m.Refused): self.click(first)
        self.assertEqual(self.win.sent, []); self.assertFalse(self.desk.log.exists())
        names = [name for name, _, _ in TOOLS]
        self.assertIn('desktop_observe', names); self.assertFalse([n for n in names if n.startswith('desktop_') and n != 'desktop_observe'])
        self.assertIn('desktop_observe', StationTools(None, read_only=True).names())


    def test_dismiss_ae_warning_only_clicks_ok_on_matching_ae_warning_dialogs(self):
        self.win.dialogs = [
            {'hwnd': 44, 'pid': 200, 'class': '#32770', 'title': 'Save Changes?', 'exe': r'C:\Program Files\Adobe\AfterFX.exe', 'rect': [100, 100, 500, 300], 'texts': ['Save changes before closing?'], 'ok_hwnd': 45},
            {'hwnd': 55, 'pid': 200, 'class': '#32770', 'title': 'After Effects', 'exe': r'C:\Program Files\Adobe\AfterFX.exe', 'rect': [200, 200, 620, 380], 'texts': ['After Effects warning: Undo group mismatch, will attempt to fix.', 'OK'], 'ok_hwnd': 56},
        ]
        out = self.desk.dismiss_ae_warning()
        self.assertEqual(out['dismissed'], True)
        self.assertEqual(self.win.sent, [('dialog_ok', 55, 56)])
        states = [json.loads(line)['state'] for line in self.desk.log.read_text().splitlines()]
        self.assertEqual(states, ['INTENT', 'DONE'])

if __name__ == '__main__': unittest.main()


class DialogWin:
    """Win32 stand-in for handle_ae_dialogs: a queue of dialogs; pressing the only button closes the front one."""
    def __init__(self, dialogs, reopen=False): self.dialogs = list(dialogs); self.sent = []; self.reopen = reopen
    def app_windows(self, process, pid=None): return [dict(d) for d in self.dialogs[:1]]
    def click_dialog_ok(self, dlg, ok):
        self.sent.append((dlg, ok))
        if not self.reopen: self.dialogs.pop(0)
        return True
    def gone(self, hwnd): return True
    def capture(self, hwnd): return Image.new('RGB', (4, 4), (9, 9, 9))


def box(hwnd, text, *labels, title='After Effects'):
    return {'hwnd': hwnd, 'pid': 200, 'class': '#32770', 'title': title, 'texts': [text], 'inputs': [], 'owned': True, 'enabled': True, 'rect': [0, 0, 4, 4],
            'buttons': [{'hwnd': hwnd * 10 + i, 'text': label, 'enabled': True} for i, label in enumerate(labels)]}


class DialogHandlingTests(unittest.TestCase):
    def desk(self, dialogs, **kw):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.win = DialogWin(dialogs, **kw); return GuardedDesktop(Path(self.tmp.name), self.win, clock=lambda: 1.0)

    def test_single_ok_is_acknowledged(self):
        out = self.desk([box(5, 'After Effects warning: 3 files are missing.', 'OK')]).handle_ae_dialogs(process='afterfx.exe')
        self.assertEqual(self.win.sent, [(5, 50)]); self.assertTrue(out['handled']); self.assertEqual(len(out['dismissed']), 1)

    def test_known_warning_text_with_a_second_button_is_never_pressed(self):
        for labels in (('OK', 'Cancel'), ('&Yes', '&No'), ('OK', 'Help')):
            out = self.desk([box(6, 'After Effects warning: Undo group mismatch, will attempt to fix.', *labels)]).handle_ae_dialogs(process='afterfx.exe')
            self.assertEqual(self.win.sent, []); self.assertFalse(out['handled']); self.assertIn('nothing was pressed', out['reason'])

    def test_single_unsafe_button_is_not_pressed(self):
        out = self.desk([box(7, 'Delete all cached frames', 'Delete')]).handle_ae_dialogs(process='afterfx.exe')
        self.assertEqual(self.win.sent, []); self.assertFalse(out['handled'])

    def test_reappearing_dialog_stops_at_the_limit_with_a_blocker(self):
        out = self.desk([box(8, 'After Effects error', 'OK')], reopen=True).handle_ae_dialogs(process='afterfx.exe', limit=3)
        self.assertEqual(len(self.win.sent), 3); self.assertFalse(out['handled']); self.assertEqual(out['hwnd'], 8); self.assertIn('allowance', out['reason'])

    def test_spent_allowance_with_no_dialog_open_is_not_a_blocker(self):
        self.assertIsNone(self.desk([]).handle_ae_dialogs(process='afterfx.exe', limit=0))
        out = self.desk([box(9, 'After Effects error', 'OK')]).handle_ae_dialogs(process='afterfx.exe', limit=0)
        self.assertEqual(self.win.sent, []); self.assertFalse(out['handled'])
