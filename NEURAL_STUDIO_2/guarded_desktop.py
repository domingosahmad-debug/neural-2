"""Guarded, provider-neutral desktop observation and input.

Observation captures one allowlisted window by exact executable identity, even
when it is not frontmost, and saves a timestamped, hashed PNG. Input is only
sent to a target that allows it, only against a fresh observation of the same
window, and every action is logged before and after. After Effects is
observe-only: the single native writer stays the only thing that drives it.
An interrupted action is recorded UNKNOWN and is never replayed.
"""
import base64, ctypes, hashlib, json, os, time, uuid
from ctypes import wintypes
from pathlib import Path

import maintenance

FRESH_SECONDS = 15
MAX_SIDE = 1600
KEYS = {'enter': 0x0D, 'tab': 0x09, 'escape': 0x1B}
INPUT_ACTIONS = ('click', 'type', 'key')


def targets(root):
    root = Path(root).resolve()
    return {'neural-studio-2': {'exe': str(root / 'runtime' / 'electron.exe').lower(), 'input': True},
            'after-effects': {'name': 'afterfx.exe', 'input': False}}


class Win:
    """Thin Win32 layer; replaced by a fake in tests."""
    def __init__(self):
        self.u = ctypes.windll.user32; self.k = ctypes.windll.kernel32; self.g = ctypes.windll.gdi32
        try: self.u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError): pass
        # Explicit 64-bit signatures: a handle must never be truncated or overflow as a C int.
        H, I, V = wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p
        for function, result, arguments in (
                (self.u.GetAncestor, H, (H, wintypes.UINT)), (self.u.WindowFromPoint, H, (wintypes.POINT,)), (self.u.GetForegroundWindow, H, ()),
                (self.u.SetForegroundWindow, wintypes.BOOL, (H,)), (self.u.GetDC, H, (H,)), (self.u.ReleaseDC, I, (H, H)),
                (self.u.PrintWindow, wintypes.BOOL, (H, H, wintypes.UINT)), (self.u.GetWindowRect, wintypes.BOOL, (H, V)), (self.u.ShowWindow, wintypes.BOOL, (H, I)),
                (self.u.IsIconic, wintypes.BOOL, (H,)), (self.u.IsWindowVisible, wintypes.BOOL, (H,)), (self.u.GetWindowTextW, I, (H, wintypes.LPWSTR, I)),
                (self.u.GetWindowThreadProcessId, wintypes.DWORD, (H, V)), (self.u.GetWindow, H, (H, wintypes.UINT)), (self.u.IsWindow, wintypes.BOOL, (H,)), (self.u.IsWindowEnabled, wintypes.BOOL, (H,)), (self.u.GetWindowLongW, wintypes.LONG, (H, I)), (self.u.GetClassNameW, I, (H, wintypes.LPWSTR, I)), (self.u.EnumChildWindows, wintypes.BOOL, (H, V, wintypes.LPARAM)), (self.u.SendMessageTimeoutW, V, (H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, V)),
                (self.g.CreateCompatibleDC, H, (H,)), (self.g.CreateCompatibleBitmap, H, (H, I, I)), (self.g.SelectObject, H, (H, H)),
                (self.g.DeleteObject, wintypes.BOOL, (H,)), (self.g.DeleteDC, wintypes.BOOL, (H,)), (self.g.GetDIBits, I, (H, H, wintypes.UINT, wintypes.UINT, V, V, wintypes.UINT)),
                (self.k.OpenProcess, H, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)), (self.k.CloseHandle, wintypes.BOOL, (H,)),
                (self.k.QueryFullProcessImageNameW, wintypes.BOOL, (H, wintypes.DWORD, wintypes.LPWSTR, V))):
            function.restype = result; function.argtypes = arguments

    def exe(self, pid):
        handle = self.k.OpenProcess(0x1000, False, pid)
        if not handle: return ''
        try:
            size = wintypes.DWORD(1024); buffer = ctypes.create_unicode_buffer(1024)
            return buffer.value if self.k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) else ''
        finally: self.k.CloseHandle(handle)

    def rect(self, hwnd):
        r = wintypes.RECT(); self.u.GetWindowRect(hwnd, ctypes.byref(r)); return [r.left, r.top, r.right, r.bottom]

    def windows(self):
        rows = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            if self.u.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(512); self.u.GetWindowTextW(hwnd, title, 512)
                pid = wintypes.DWORD(); self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                rows.append({'hwnd': int(hwnd), 'pid': pid.value, 'title': title.value, 'exe': self.exe(pid.value), 'rect': self.rect(hwnd), 'minimized': bool(self.u.IsIconic(hwnd))})
            return True
        self.u.EnumWindows(each, 0); return rows

    def show_inactive(self, hwnd): self.u.ShowWindow(hwnd, 4); time.sleep(.4)

    def capture(self, hwnd):
        from PIL import Image
        left, top, right, bottom = self.rect(hwnd); w, h = right - left, bottom - top
        if w <= 0 or h <= 0 or w * h > 40_000_000: raise ValueError('Window has no capturable area.')
        screen = self.u.GetDC(None); dc = self.g.CreateCompatibleDC(screen); bitmap = self.g.CreateCompatibleBitmap(screen, w, h)
        try:
            self.g.SelectObject(dc, bitmap)
            if not self.u.PrintWindow(hwnd, dc, 2): raise ValueError('The window refused to draw itself for capture.')
            info = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-h).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
            pixels = ctypes.create_string_buffer(w * h * 4)
            if self.g.GetDIBits(dc, bitmap, 0, h, pixels, ctypes.byref(info), 0) != h: raise ValueError('Window pixels could not be read.')
            return Image.frombuffer('RGB', (w, h), pixels.raw, 'raw', 'BGRX', 0, 1)
        finally:
            self.g.DeleteObject(bitmap); self.g.DeleteDC(dc); self.u.ReleaseDC(None, screen)

    def foreground(self, hwnd):
        self.u.SetForegroundWindow(hwnd); time.sleep(.35)
        return int(self.u.GetForegroundWindow() or 0) == hwnd

    def dialog_windows(self):
        rows = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            if self.u.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(128); self.u.GetClassNameW(hwnd, cls, 128)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(512); self.u.GetWindowTextW(hwnd, title, 512)
                    pid = wintypes.DWORD(); self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    texts, ok_list = [], []
                    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    def each_child(chwnd, __):
                        ccls = ctypes.create_unicode_buffer(128); self.u.GetClassNameW(chwnd, ccls, 128)
                        ctext = ctypes.create_unicode_buffer(512); self.u.GetWindowTextW(chwnd, ctext, 512)
                        val = ctext.value.strip()
                        if val: texts.append(val)
                        if ccls.value.lower() == 'button' and val.replace('&', '').lower() == 'ok' and not ok_list:
                            ok_list.append(int(chwnd))
                        return True
                    self.u.EnumChildWindows(hwnd, each_child, 0)
                    rows.append({'hwnd': int(hwnd), 'pid': pid.value, 'class': cls.value, 'title': title.value, 'exe': self.exe(pid.value), 'rect': self.rect(hwnd), 'texts': texts, 'ok_hwnd': ok_list[0] if ok_list else None})
            return True
        self.u.EnumWindows(each, 0); return rows

    def app_windows(self, name, pid=None):
        """Visible top-level windows of one executable name, with modal evidence: class, enabled, owner, Win32 buttons and texts."""
        rows = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            if not self.u.IsWindowVisible(hwnd): return True
            owner = wintypes.DWORD(); self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if pid is not None and owner.value != pid: return True
            exe = self.exe(owner.value)
            if Path(exe.lower()).name != name: return True
            cls = ctypes.create_unicode_buffer(128); self.u.GetClassNameW(hwnd, cls, 128)
            title = ctypes.create_unicode_buffer(512); self.u.GetWindowTextW(hwnd, title, 512)
            texts, buttons, other = [], [], []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def each_child(chwnd, __):
                if not self.u.IsWindowVisible(chwnd): return True
                ccls = ctypes.create_unicode_buffer(128); self.u.GetClassNameW(chwnd, ccls, 128)
                ctext = ctypes.create_unicode_buffer(1024); self.u.GetWindowTextW(chwnd, ctext, 1024)
                val = ctext.value.strip()
                if ccls.value.lower() == 'button':
                    kind = self.u.GetWindowLongW(chwnd, -16) & 0xF
                    if kind in (0, 1, 0xB): buttons.append({'hwnd': int(chwnd), 'text': val, 'enabled': bool(self.u.IsWindowEnabled(chwnd))})
                    elif kind != 7: other.append(val or ccls.value)  # checkbox/radio: a choice, not a notification
                elif ccls.value.lower() in ('edit', 'combobox', 'listbox', 'syslistview32', 'systreeview32', 'directuihwnd'): other.append(ccls.value)
                if val: texts.append(val)
                return True
            self.u.EnumChildWindows(hwnd, each_child, 0)
            rows.append({'hwnd': int(hwnd), 'pid': owner.value, 'exe': exe, 'class': cls.value, 'title': title.value, 'rect': self.rect(hwnd), 'enabled': bool(self.u.IsWindowEnabled(hwnd)),
                         'owned': bool(self.u.GetWindow(hwnd, 4)), 'texts': texts, 'buttons': buttons, 'inputs': other})
            return True
        self.u.EnumWindows(each, 0); return rows

    def gone(self, hwnd, seconds=2.0):
        """True once a window no longer exists or is hidden."""
        end = time.monotonic() + seconds
        while True:
            if not self.u.IsWindow(hwnd) or not self.u.IsWindowVisible(hwnd): return True
            if time.monotonic() >= end: return False
            time.sleep(.05)

    def click_dialog_ok(self, dlg_hwnd, ok_hwnd):
        # BM_CLICK is silently ignored when the dialog is not its thread's active window (another
        # application in front), so the command of this exact button is sent to its parent instead.
        # Never a blind IDOK. BM_CLICK is only the fallback for a button without a control id.
        H = wintypes.HWND; send = self.u.SendMessageTimeoutW; result = ctypes.c_size_t(0)
        send.restype = ctypes.c_ssize_t; send.argtypes = (H, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t))
        self.u.GetDlgCtrlID.restype = ctypes.c_int; self.u.GetDlgCtrlID.argtypes = (H,); self.u.GetParent.restype = H; self.u.GetParent.argtypes = (H,)
        ident = self.u.GetDlgCtrlID(ok_hwnd) & 0xFFFF
        if ident: ok = send(self.u.GetParent(ok_hwnd) or dlg_hwnd, 0x0111, ident, ok_hwnd, 0x0002, 2000, ctypes.byref(result))
        else: ok = send(ok_hwnd, 0x00F5, 0, 0, 0x0002, 2000, ctypes.byref(result))
        return bool(ok)

    def root_at(self, x, y):
        return int(self.u.GetAncestor(self.u.WindowFromPoint(wintypes.POINT(x, y)), 2) or 0)

    def click(self, x, y):
        self.u.SetCursorPos(x, y); time.sleep(.05); self.u.mouse_event(2, 0, 0, 0, 0); time.sleep(.04); self.u.mouse_event(4, 0, 0, 0, 0)

    def key(self, code):
        self.u.keybd_event(code, 0, 0, 0); time.sleep(.03); self.u.keybd_event(code, 0, 2, 0)

    def text(self, value):
        class KI(ctypes.Structure): _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_void_p)]
        class U(ctypes.Union): _fields_ = [('ki', KI), ('pad', ctypes.c_byte * 32)]
        class INPUT(ctypes.Structure): _fields_ = [('type', wintypes.DWORD), ('u', U)]
        raw = value.encode('utf-16-le')
        for unit in [int.from_bytes(raw[i:i + 2], 'little') for i in range(0, len(raw), 2)]:
            for flags in (4, 4 | 2):
                item = INPUT(1, U(ki=KI(0, unit, flags, 0, None))); self.u.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))
            time.sleep(.004)


class GuardedDesktop:
    def __init__(self, root, win=None, clock=time.time):
        self.root = Path(root).resolve(); self.folder = self.root / 'data' / 'desktop-observations'; self.folder.mkdir(parents=True, exist_ok=True)
        self.log = self.folder / 'ACTIONS.jsonl'; self._win = win; self.clock = clock

    @property
    def win(self):
        if self._win is None:
            if os.name != 'nt': raise ValueError('Desktop observation is only available on the Windows target PC.')
            self._win = Win()
        return self._win

    def _find(self, target):
        spec = targets(self.root).get(target)
        if not spec: raise ValueError('Unknown desktop target. Allowed: ' + ', '.join(sorted(targets(self.root))))
        def match(row):
            exe = (row.get('exe') or '').lower()
            return exe == spec['exe'] if 'exe' in spec else Path(exe).name == spec['name']
        rows = [r for r in self.win.windows() if match(r) and r['title'].strip()]
        if not rows: raise ValueError(f'No visible {target} window is open. Nothing was launched or focused.')
        area = lambda r: max(0, r['rect'][2] - r['rect'][0]) * max(0, r['rect'][3] - r['rect'][1])
        return spec, max(rows, key=area)

    def observe(self, target='neural-studio-2'):
        """Fresh pixels of one allowlisted window. Never launches, focuses or sends input."""
        spec, row = self._find(target)
        if row['minimized']:
            if not spec['input']: raise ValueError(f'The {target} window is minimized; it is observe-only and was not restored.')
            self.win.show_inactive(row['hwnd']); spec, row = self._find(target)
            if row['minimized']: raise ValueError(f'The {target} window stayed minimized; no fresh pixels exist.')
        image = self.win.capture(row['hwnd'])
        low, high = image.convert('L').getextrema()
        if low == high: raise ValueError('The capture is a single flat colour; it is not accepted as an observation.')
        scale = min(1.0, MAX_SIDE / max(image.size))
        if scale < 1: image = image.resize((round(image.width * scale), round(image.height * scale)))
        identity = uuid.uuid4().hex; path = self.folder / f'{identity}.png'; image.save(path, 'PNG')
        record = {'schema': 'neural.desktop-observation.v1', 'id': identity, 'target': target, 'at': self.clock(), 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  'hwnd': row['hwnd'], 'pid': row['pid'], 'exe': row['exe'], 'title': row['title'][:200], 'rect': row['rect'], 'size': list(image.size), 'scale': scale,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'path': str(path), 'inputAllowed': bool(spec['input'])}
        (self.folder / f'{identity}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        return record

    def image(self, record):
        return {'kind': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(Path(record['path']).read_bytes()).decode(), **{k: record[k] for k in ('id', 'target', 'time', 'title', 'size', 'sha256', 'inputAllowed')}}

    def _logged(self, request_id):
        if not self.log.is_file(): return None
        found = None
        for line in self.log.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row.get('requestId') == request_id: found = row
        return found

    def _append(self, row):
        with self.log.open('a', encoding='utf-8') as handle: handle.write(json.dumps(row) + '\n'); handle.flush(); os.fsync(handle.fileno())

    def act(self, request, blockers=lambda: []):
        """One guarded input against a fresh observation. Same requestId never sends twice."""
        rid = request.get('requestId'); kind = request.get('kind')
        if not isinstance(rid, str) or not 8 <= len(rid) <= 120: raise ValueError('A requestId of 8 to 120 characters is required.')
        earlier = self._logged(rid)
        if earlier: return {'action': earlier, 'replayed': False, 'note': 'This request was already recorded; nothing was sent again.'}
        if kind not in INPUT_ACTIONS: raise ValueError('Input kind must be click, type or key.')
        try: record = json.loads((self.folder / (str(request.get('observation')) + '.json')).read_text(encoding='utf-8'))
        except (OSError, ValueError): raise ValueError('An existing observation id is required.')
        if not targets(self.root).get(record['target'], {}).get('input'): raise ValueError(f"{record['target']} is observe-only; no input was sent.")
        if self.clock() - record['at'] > FRESH_SECONDS: raise ValueError('The observation is stale; observe again before acting.')
        if kind == 'click':
            x, y = request.get('x'), request.get('y')
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (x, y)) or not (0 <= x < record['size'][0] and 0 <= y < record['size'][1]): raise ValueError('Click must be inside the observed image.')
        elif kind == 'type':
            if not isinstance(request.get('text'), str) or not 1 <= len(request['text']) <= 500 or any(ord(c) < 32 for c in request['text']): raise ValueError('Text of 1 to 500 printable characters is required.')
        elif request.get('key') not in KEYS: raise ValueError('Key must be one of: ' + ', '.join(sorted(KEYS)))
        with maintenance.admission(self.root, 'desktop-input'):
            busy = list(blockers())
            if busy: raise ValueError('Input refused: ' + '; '.join(busy[:4]))
            spec, row = self._find(record['target'])
            if (row['hwnd'], row['pid'], row['rect']) != (record['hwnd'], record['pid'], record['rect']): raise ValueError('The window changed since the observation; observe again.')
            entry = {'requestId': rid, 'observation': record['id'], 'target': record['target'], 'kind': kind, 'at': self.clock(), 'state': 'INTENT',
                     'detail': {k: request[k] for k in ('x', 'y', 'key') if k in request} | ({'textLength': len(request['text'])} if kind == 'type' else {})}
            if not self.win.foreground(row['hwnd']):
                entry['state'] = 'REFUSED'; entry['reason'] = 'window could not be brought to the front; nothing was sent'; self._append(entry); raise ValueError(entry['reason'])
            if kind == 'click':
                sx = row['rect'][0] + round(request['x'] / record['scale']); sy = row['rect'][1] + round(request['y'] / record['scale'])
                if self.win.root_at(sx, sy) != row['hwnd']:
                    entry['state'] = 'REFUSED'; entry['reason'] = 'another window covers that point; nothing was sent'; self._append(entry); raise ValueError(entry['reason'])
            self._append(entry)
            try:
                if kind == 'click': self.win.click(sx, sy)
                elif kind == 'type': self.win.text(request['text'])
                else: self.win.key(KEYS[request['key']])
            except BaseException as error:
                self._append(entry | {'state': 'UNKNOWN', 'reason': type(error).__name__, 'at': self.clock()}); raise
            done = entry | {'state': 'DONE', 'at': self.clock()}; self._append(done)
        time.sleep(.6)
        return {'action': done, 'after': self.observe(record['target'])}

    def dismiss_ae_warning(self):
        """Dismiss modal After Effects warning dialogs (#32770 with OK) while keeping AE UI observe-only."""
        if not hasattr(self.win, 'dialog_windows'):
            return None
        for row in self.win.dialog_windows():
            exe = Path((row.get('exe') or '').lower()).name
            title = str(row.get('title') or '').strip()
            rect = row.get('rect') or [0, 0, 0, 0]
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            text = ' '.join(str(t) for t in row.get('texts', []))
            lower = text.lower()
            ok_hwnd = row.get('ok_hwnd')
            if exe != 'afterfx.exe' or not title.startswith('After Effects') or not (0 < w <= 900 and 0 < h <= 600):
                continue
            if not any(k in lower for k in ('after effects warning', 'undo group mismatch')) or not ok_hwnd:
                continue
            entry = {'requestId': 'ae-warning-' + uuid.uuid4().hex[:12], 'target': 'after-effects-warning', 'kind': 'dialog_ok', 'hwnd': row['hwnd'], 'okHwnd': ok_hwnd, 'title': title[:120], 'text': text[:300], 'at': self.clock(), 'state': 'INTENT'}
            self._append(entry)
            sent = self.win.click_dialog_ok(row['hwnd'], ok_hwnd)
            done = entry | {'state': 'DONE' if sent else 'UNKNOWN', 'at': self.clock()}
            self._append(done)
            return {'dismissed': bool(sent), 'title': title, 'text': text}
        return None

    SAFE_LABELS = ('ok', 'continue', 'close', 'dismiss', 'got it')
    KNOWN_OK_TEXT = ('after effects warning', 'undo group mismatch')

    def ae_dialogs(self, process=None, pid=None):
        """Modal evidence for After Effects from Win32 state alone: standard dialogs, and a disabled main frame with its enabled owned windows."""
        process = process or targets(self.root)['after-effects']['name']
        rows = self.win.app_windows(process, pid)
        dialogs = [r for r in rows if r['class'] == '#32770']
        frames = [r for r in rows if r['class'] != '#32770' and not r['owned']]
        if any(not r['enabled'] for r in frames):
            drawn = [r for r in rows if r['class'] != '#32770' and r['owned'] and r['enabled']]
            # An application-drawn modal exposes no Win32 controls; a disabled frame with no visible modal is reported on the frame itself.
            dialogs += drawn or ([] if dialogs else [dict(r, hiddenModal=True) for r in frames if not r['enabled']][:1])
        return dialogs

    def _evidence(self, row):
        try:
            image = self.win.capture(row['hwnd']); identity = 'dialog-' + uuid.uuid4().hex; path = self.folder / f'{identity}.png'; image.save(path, 'PNG'); return str(path)
        except Exception: return None

    def handle_ae_dialogs(self, process=None, pid=None, known=None, limit=5):
        """Deterministic modal handling for the single native writer.

        A standard dialog whose only push button carries a plain acknowledgement
        label is acknowledged, logged INTENT then DONE, and verified closed. A
        dialog with a second button is a choice whatever its text says. Anything that
        offers a choice, takes input, is application-drawn or does not close is
        never pressed blind: it is returned as an unhandled blocker with its
        title, text, buttons and a screenshot. Returns None when no modal exists.
        """
        if not hasattr(self.win, 'app_windows'): return None
        dismissed = []
        label = lambda b: b['text'].replace('&', '').strip().lower()
        def stop(row, reason):
            title = str(row.get('title') or '').strip(); text = ' '.join(str(t) for t in row.get('texts', []))
            blocker = {'handled': False, 'hwnd': row['hwnd'], 'class': row['class'], 'title': title[:200], 'text': text[:1200], 'buttons': [b['text'] for b in row.get('buttons', [])], 'reason': reason, 'dismissed': dismissed, 'at': self.clock()}
            if known != row['hwnd']:
                blocker['screenshot'] = self._evidence(row)
                self._append({'requestId': 'ae-dialog-' + uuid.uuid4().hex[:12], 'target': 'after-effects-dialog', 'kind': 'dialog_blocker', 'state': 'BLOCKED', **{k: blocker[k] for k in ('hwnd', 'class', 'title', 'text', 'buttons', 'reason', 'screenshot', 'at')}})
            return blocker
        for _ in range(limit):
            dialogs = self.ae_dialogs(process, pid)
            if not dialogs: break
            row = dialogs[0]; title = str(row.get('title') or '').strip(); text = ' '.join(str(t) for t in row.get('texts', []))
            every = row.get('buttons', []); buttons = [b for b in every if b['enabled']]
            target = None; reason = None
            if row['class'] != '#32770': reason = 'After Effects is blocked by a modal it draws itself; its buttons cannot be read, so nothing was pressed.'
            elif row.get('inputs'): reason = 'The dialog asks for input or a choice; nothing was pressed.'
            elif len(every) == 1 and len(buttons) == 1 and label(buttons[0]) in self.SAFE_LABELS: target = buttons[0]
            else: reason = 'The dialog offers ' + (', '.join(b['text'] or '?' for b in every) or 'no readable button') + '; choosing is not a notification acknowledgement, so nothing was pressed.'
            if target:
                entry = {'requestId': 'ae-dialog-' + uuid.uuid4().hex[:12], 'target': 'after-effects-dialog', 'kind': 'dialog_ok', 'hwnd': row['hwnd'], 'okHwnd': target['hwnd'], 'button': target['text'], 'title': title[:120], 'text': text[:600], 'at': self.clock(), 'state': 'INTENT'}
                self._append(entry)
                try: sent = self.win.click_dialog_ok(row['hwnd'], target['hwnd']); closed = bool(sent) and self.win.gone(row['hwnd'])
                except BaseException as error:
                    self._append(entry | {'state': 'UNKNOWN', 'reason': type(error).__name__, 'at': self.clock()}); raise
                self._append(entry | {'state': 'DONE' if closed else 'UNKNOWN', 'at': self.clock()})
                if closed:
                    dismissed.append({'title': title[:120], 'text': text[:600], 'button': target['text'], 'at': self.clock()}); continue
                reason = 'The acknowledgement was sent but the dialog did not close; it was not pressed again.'
            return stop(row, reason)
        else:
            # The allowance is spent. Only a dialog that is actually still open is a blocker.
            dialogs = self.ae_dialogs(process, pid)
            if dialogs: return stop(dialogs[0], 'After Effects keeps raising dialogs; the acknowledgement allowance for this command is spent, so nothing more was pressed.')
        return {'handled': True, 'dismissed': dismissed} if dismissed else None
