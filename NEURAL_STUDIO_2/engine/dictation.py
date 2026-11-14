"""Local, zero-token dictation for the director composer.

Supports both:
- Cached-local faster-whisper models (offline, GPU with headroom or CPU int8 fallback,
  in-memory default microphone capture via sounddevice OR chunked WAV via /api/dictation/audio).
- The Windows desktop speech recognizer (System.Speech, compiled locally from dictation_helper.cs).

Nothing is downloaded, no LLM or paid transcription service is called, and no audio is written
to disk. Recognized words are returned to the composer draft only; this service never sends a
director message or starts a model turn.
"""
from __future__ import annotations
from collections import deque
from pathlib import Path
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import uuid
import wave

import speech_engines

ROOT = Path(__file__).resolve().parents[1]
WHISPER_WORKER = Path(__file__).resolve().parent / 'dictation_whisper_worker.py'
WINDOWS_ENGINE_ID = 'windows-speech'
MAX_AUDIO_BYTES = 2_900_000          # one chunk: ~90 s of 16 kHz mono PCM
MAX_CHUNK_SECONDS = 95
WHISPER_SILENCE_HALLUCINATIONS = {'', 'you', 'thank you', 'thanks for watching', 'bye'}
HELPER_SOURCE = Path(__file__).resolve().parent / 'dictation_helper.cs'
ENGINE_LABEL = 'Windows desktop speech recognizer (System.Speech) · offline · on this PC'
WINDOWS_HINT = ('Alternative: Windows voice typing (Win+H) also types into the focused draft box; '
                'it follows your Windows speech/online-speech settings and may use Microsoft online services.')


def _csc() -> Path | None:
    windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
    for name in ('Framework64', 'Framework'):
        p = windir / 'Microsoft.NET' / name / 'v4.0.30319' / 'csc.exe'
        if p.is_file():
            return p
    return None


def _speech_reference() -> Path | None:
    windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
    gac = windir / 'Microsoft.NET' / 'assembly' / 'GAC_MSIL' / 'System.Speech'
    if gac.is_dir():
        for p in sorted(gac.glob('*/System.Speech.dll')):
            return p
    return None


def microphone_privacy() -> str:
    """Return 'deny' when Windows privacy settings block desktop microphone use.

    Read-only check of the documented consent store; it never changes settings.
    """
    if os.name != 'nt':
        return 'unknown'
    try:
        import winreg
        base = r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone'
        values = []
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (base, base + r'\NonPackaged'):
                try:
                    with winreg.OpenKey(hive, sub) as key:
                        values.append(str(winreg.QueryValueEx(key, 'Value')[0]).lower())
                except OSError:
                    pass
        return 'deny' if 'deny' in values else 'allow' if values else 'unknown'
    except Exception:
        return 'unknown'


class HelperBuildError(RuntimeError):
    pass


def build_helper(out_dir: Path) -> Path:
    """Compile the helper once per source revision (local compiler, no download)."""
    source = HELPER_SOURCE.read_bytes()
    tag = hashlib.sha256(source).hexdigest()[:12]
    exe = out_dir / f'NeuralDictation-{tag}.exe'
    if exe.is_file():
        return exe
    csc, ref = _csc(), _speech_reference()
    if not csc or not ref:
        raise HelperBuildError('The Windows .NET Framework speech components are not available on this PC.')
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f'NeuralDictation-{tag}.{uuid.uuid4().hex[:6]}.tmp.exe'
    result = subprocess.run([str(csc), '/nologo', '/target:exe', '/optimize+', f'/out:{tmp}', f'/r:{ref}', str(HELPER_SOURCE)],
                            capture_output=True, text=True, timeout=60,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode or not tmp.is_file():
        raise HelperBuildError('The local dictation helper could not be prepared: ' + (result.stdout or result.stderr).strip()[:300])
    try:
        tmp.replace(exe)
    except OSError:
        if not exe.is_file():
            raise
    for old in out_dir.glob('NeuralDictation-*.exe'):
        if old != exe:
            try:
                old.unlink()
            except OSError:
                pass
    return exe


def whisper_launcher(cfg: dict):
    """Start one cached-model transcription process. Exiting it releases the model; nothing is downloaded."""
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0
    env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    return subprocess.Popen([sys.executable, '-u', str(WHISPER_WORKER), json.dumps(cfg)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=flags, env=env)


def default_launcher(out_dir: Path):
    def launch(culture: str, max_seconds: int):
        if os.name != 'nt':
            raise HelperBuildError('Local dictation uses the Windows speech recognizer and is available on Windows only.')
        exe = build_helper(out_dir)
        args = [str(exe), '--max-seconds', str(int(max_seconds))]
        if culture:
            args += ['--culture', culture]
        return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding='utf-8', errors='replace', bufsize=1,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return launch


class DictationService:
    """One dictation session at a time, polled by the composer while listening."""
    ACTIVE = ('starting', 'listening', 'stopping')

    def __init__(self, runtime_dir: Path | None = None, launcher=None, privacy=microphone_privacy,
                 clock=time.monotonic, lease_seconds: float = 12.0, max_seconds: int = 300, watchdog: bool = True,
                 whisper_start=None, busy_check=None, speech_root: Path | None = None, free_mb=None):
        self.runtime_dir = Path(runtime_dir or ROOT / '.runtime' / 'dictation')
        self.launcher = launcher or default_launcher(self.runtime_dir)
        self.privacy = privacy
        self.clock = clock
        self.lease_seconds = lease_seconds
        self.max_seconds = max_seconds
        self.lock = threading.RLock()
        self.proc = None
        self.session = None
        self.status = 'idle'
        self.error = None
        self.engine = None
        self.level = 0
        self.seq = 0
        self.events: deque = deque(maxlen=200)
        self.interim = ''
        self.lease = 0.0
        self.started = 0.0
        self.closed = False
        self.whisper_start = whisper_start or whisper_launcher
        self.busy_check = busy_check
        self.speech_root = Path(speech_root or ROOT)
        self.free_mb = free_mb or speech_engines.gpu_free_mb
        self.engine_id = None
        self.capture = 'native-helper'
        self.ready = threading.Event()
        self.req_lock = threading.Lock()
        self.pending_chunks: dict = {}
        self.last_sequence = 0
        self.results: dict = {}
        self.audio_seconds = 0.0
        self.device = None
        if watchdog:
            threading.Thread(target=self._watch, daemon=True, name='dictation-watchdog').start()

    # ------------------------------------------------------------------ state
    def _event(self, kind: str, **data):
        self.seq += 1
        item = {'seq': self.seq, 'type': kind, **data}
        self.events.append(item)
        return item

    def _is_whisper(self) -> bool:
        return bool(self.engine_id and self.engine_id != WINDOWS_ENGINE_ID)

    def snapshot(self, since: int = 0) -> dict:
        with self.lock:
            # While a Whisper engine is still loading, never report the Windows recognizer's label for it.
            label = self.engine or (f'{self.engine_id} · offline · on this PC' if self._is_whisper() else ENGINE_LABEL)
            return {
                'status': self.status,
                'session': self.session,
                'engine': label,
                'engine_label': label,
                'offline': True,
                'network': False,
                'records_audio': False,
                'model_calls': 0,
                'error': self.error,
                'interim': self.interim,
                'level': self.level,
                'seq': self.seq,
                'events': [e for e in self.events if e['seq'] > since and e['type'] != 'interim'],
                'hint': WINDOWS_HINT,
                'max_seconds': self.max_seconds,
                'engine_id': self.engine_id or WINDOWS_ENGINE_ID,
                'capture': self.capture,
                'device': self.device,
                'audio': {
                    'endpoint': '/api/dictation/audio',
                    'format': 'wav-pcm16-mono',
                    'min_sample_rate': 8000,
                    'max_sample_rate': 48000,
                    'max_bytes': MAX_AUDIO_BYTES,
                    'max_chunk_seconds': MAX_CHUNK_SECONDS,
                    'next_sequence': self.last_sequence + 1,
                    'seconds_used': round(self.audio_seconds, 2),
                } if self._is_whisper() else None,
            }

    # ---------------------------------------------------------------- control
    def _busy_reason(self):
        try:
            return self.busy_check() if self.busy_check else None
        except Exception:
            return 'GPU ownership could not be verified'

    def capabilities(self) -> dict:
        """Local engines and truthful availability. Reading this loads nothing and starts no process."""
        whisper = speech_engines.whisper_engines(self.speech_root, self._busy_reason(), self.free_mb)
        windows_ok = os.name == 'nt' and bool(_csc()) and bool(_speech_reference())
        windows = {
            'id': WINDOWS_ENGINE_ID,
            'label': ENGINE_LABEL,
            'available': windows_ok,
            'kind': 'windows',
            'capture': 'native-helper',
            'accuracy_rank': -1,
            'detail': (
                'Lower accuracy, instant start; offline helper that listens to the default microphone.'
                if windows_ok else
                'Windows .NET speech components are not available.'
            ),
            'device_plan': None,
        }
        engines = whisper + [windows]
        selected = speech_engines.default_whisper(whisper) or (WINDOWS_ENGINE_ID if windows_ok else None)
        return {
            'engines': engines,
            'selected': selected,
            'offline': True,
            'network': False,
            'records_audio': False,
            'model_calls': 0,
            'note': 'Engines are only cached local models. Accuracy on Tony\'s microphone is untested until he uses it.',
        }

    def start(self, culture: str = '', engine_id: str | None = None, capture: str | None = None) -> dict:
        with self.lock:
            if self.closed:
                raise ValueError('Studio is shutting down')
            if self.status in self.ACTIVE and self.proc is not None:
                self.lease = self.clock()
                return self.snapshot()
            if engine_id is not None and not isinstance(engine_id, str):
                raise ValueError('engine_id must be a string')
            if capture is not None and not isinstance(capture, str):
                raise ValueError('capture must be a string')
            if engine_id and engine_id != WINDOWS_ENGINE_ID:
                return self._start_whisper(engine_id, capture=capture)
            self.engine_id = None
            self.capture = 'native-helper'
            self.device = None
            culture = culture if isinstance(culture, str) and len(culture) <= 20 else ''
            if self.proc is not None:
                # A previous helper that reported an error is still exiting; release it first.
                self._terminate(self.proc)
                self.proc = None
            self.error = None
            self.interim = ''
            self.level = 0
            self.engine = None
            self.events.clear()
            self.session = uuid.uuid4().hex[:12]
            if self.privacy() == 'deny':
                return self._fail('privacy', 'Windows privacy settings block desktop apps from using the microphone. '
                                  'Open Settings › Privacy & security › Microphone to allow it; Neural will not change this for you.')
            try:
                proc = self.launcher(culture, self.max_seconds)
            except (HelperBuildError, OSError, ValueError) as e:
                return self._fail('unavailable', str(e) or 'Local dictation is unavailable on this PC.')
            self.proc = proc
            self.status = 'starting'
            self.started = self.lease = self.clock()
            self._event('state', status='starting')
            session = self.session
        threading.Thread(target=self._read, args=(proc, session), daemon=True, name='dictation-reader').start()
        return self.snapshot()

    # ----------------------------------------------------------- whisper path
    def _start_whisper(self, engine_id: str, capture: str | None = None) -> dict:
        if capture in ('browser-audio', 'chunk-upload') or os.environ.get('NEURAL_DICTATION_NO_MIC') == '1':
            capture_mode = 'browser-audio'
            capture_mic = False
        elif capture in (None, '', 'local-mic', 'native-helper'):
            capture_mode = 'local-mic'
            capture_mic = True
        else:
            raise ValueError('Unsupported dictation capture mode')

        if self.proc is not None:
            self._terminate(self.proc)
            self.proc = None
        self.error = None
        self.interim = ''
        self.level = 0
        self.engine = None
        self.events.clear()
        self.session = uuid.uuid4().hex[:12]
        self.engine_id = engine_id
        self.capture = capture_mode
        self.device = None
        self.last_sequence = 0
        self.results = {}
        self.pending_chunks = {}
        self.audio_seconds = 0.0
        self.ready = threading.Event()

        if capture_mic and self.privacy() == 'deny':
            return self._fail('privacy', 'Windows privacy settings block desktop apps from using the microphone. '
                              'Open Settings › Privacy & security › Microphone to allow it; Neural will not change this for you.')

        row = next((e for e in speech_engines.whisper_engines(self.speech_root, self._busy_reason(), self.free_mb) if e['id'] == engine_id), None)
        if row is None:
            return self._fail('unknown-engine', 'Unknown dictation engine.')
        if not row['available']:
            return self._fail('unavailable', row['detail'])
        try:
            path, meta = speech_engines.model_path(engine_id, self.speech_root)
            plan = row['device_plan']
            cfg = {
                'deps': str(speech_engines.find_deps(self.speech_root)),
                'model_path': str(path),
                'device': plan['device'],
                'compute_type': plan['compute_type'],
                'cpu_threads': plan['cpu_threads'],
                'language': meta['language'],
                'label': row['label'],
                'size': meta['size'],
                'capture_mic': capture_mic,
                'max_seconds': self.max_seconds,
            }
            proc = self.whisper_start(cfg)
        except (OSError, ValueError) as e:
            return self._fail('unavailable', str(e) or 'The cached speech model could not be started.')
        self.proc = proc
        self.status = 'starting'
        self.started = self.lease = self.clock()
        self._event('state', status='starting', engine_id=engine_id, capture=capture_mode, plan=plan['reason'])
        session = self.session
        threading.Thread(target=self._read_whisper, args=(proc, session, row), daemon=True, name='dictation-whisper-reader').start()
        return self.snapshot()

    def _read_whisper(self, proc, session, row):
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    if 'ready' in msg or msg.get('type') == 'ready':
                        if session == self.session and self.proc is proc:
                            if msg.get('ready'):
                                self.device = msg.get('device')
                                self.engine = f"{row['label']} · {self.device} · offline · on this PC"
                                self.status = 'listening'
                                self._event('state', status='listening', engine=self.engine, device=self.device)
                            else:
                                self._fail('model-load', str(msg.get('error') or 'The cached speech model did not become ready.')[:300])
                                self._terminate(proc)
                                self.proc = None
                        self.ready.set()
                        continue
                    if msg.get('type') == 'chunk_result' or 'id' in msg:
                        slot = self.pending_chunks.get(msg.get('id'))
                        if slot:
                            slot[1]['out'] = msg
                            slot[0].set()
                        continue
                    if session != self.session:
                        break
                    self._handle(msg)
        except (OSError, ValueError):
            pass
        finally:
            self.ready.set()
            try:
                code = proc.wait(timeout=5)
            except Exception:
                code = None
            with self.lock:
                for ev, box in list(self.pending_chunks.values()):
                    box.setdefault('out', {'error': 'Speech worker stopped before completing transcription.'})
                    ev.set()
                self.pending_chunks.clear()
                if session == self.session and self.proc is proc:
                    self.proc = None
                    self.interim = ''
                    if self.status != 'error':
                        if code not in (0, None) and self.status != 'stopping' and not self.error:
                            self.status = 'error'
                            self.error = {'code': 'helper-exit', 'message': f'The speech worker stopped unexpectedly (exit {code}).'}
                            self._event('error', **self.error)
                        else:
                            self.status = 'idle'
                    self._event('state', status=self.status, release_microphone=(self.capture == 'browser-audio'))

    def audio(self, data: dict) -> dict:
        """One chunk of 16-bit mono WAV. The session owner and a rising sequence are required."""
        session = data.get('session')
        sequence = data.get('sequence')
        with self.lock:
            if self.closed:
                raise ValueError('Studio is shutting down')
            if not self._is_whisper() or not self.session or session != self.session or self.status not in ('starting', 'listening'):
                raise ValueError('No active dictation session owns this audio')
            if type(sequence) is not int or sequence < 1:
                raise ValueError('Audio chunks need an integer sequence of 1 or more')
            if sequence in self.results:
                return dict(self.results[sequence], duplicate=True)
            if sequence <= self.last_sequence:
                raise ValueError('Out-of-order audio chunk')
            self.lease = self.clock()
            ready = self.ready
        try:
            raw = base64.b64decode(str(data.get('audio', '')), validate=True)
        except (ValueError, TypeError):
            raise ValueError('Invalid audio encoding')
        if not 1000 < len(raw) <= MAX_AUDIO_BYTES or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
            raise ValueError('Expected a short WAV recording')
        try:
            with wave.open(io.BytesIO(raw)) as w:
                if w.getnchannels() != 1 or w.getsampwidth() != 2 or not 8000 <= w.getframerate() <= 48000:
                    raise ValueError('Expected 16-bit mono audio')
                seconds = w.getnframes() / w.getframerate()
        except (wave.Error, EOFError):
            raise ValueError('Audio is not a valid WAV file')
        if seconds > MAX_CHUNK_SECONDS:
            raise ValueError('Audio chunk is too long')
        with self.lock:
            if self.audio_seconds + seconds > self.max_seconds + MAX_CHUNK_SECONDS:
                raise ValueError('The dictation session audio limit was reached; stop and start a new session')
        if seconds < 0.25:
            with self.lock:
                self.last_sequence = max(self.last_sequence, sequence)
                result = {'accepted': True, 'sequence': sequence, 'text': '', 'seconds': round(seconds, 2), 'status': self.status, 'session': self.session, 'seq': self.seq}
                self.results[sequence] = result
            return result
        if not ready.wait(timeout=180):
            raise ValueError('The speech model is still loading; retry this chunk')

        req_id = uuid.uuid4().hex
        done_ev = threading.Event()
        box: dict = {}
        with self.req_lock:
            with self.lock:
                if session != self.session or self.status != 'listening' or self.proc is None:
                    raise ValueError('The dictation session ended before this audio was transcribed')
                if sequence <= self.last_sequence:
                    raise ValueError('Out-of-order audio chunk')
                proc = self.proc
                self.pending_chunks[req_id] = (done_ev, box)
            try:
                try:
                    proc.stdin.write(json.dumps({'id': req_id, 'audio': base64.b64encode(raw).decode()}) + '\n')
                    proc.stdin.flush()
                except (OSError, ValueError):
                    with self.lock:
                        self._fail('helper-exit', 'The speech worker stopped unexpectedly.')
                    raise ValueError('The speech worker stopped unexpectedly')
                if not done_ev.wait(timeout=120):
                    with self.lock:
                        self._fail('timeout', 'The speech worker did not answer in time and was stopped.')
                        self._terminate(proc)
                        self.proc = None
                    raise ValueError('The speech worker did not answer in time')
            finally:
                with self.lock:
                    self.pending_chunks.pop(req_id, None)

        out = box.get('out') or {}
        if out.get('error'):
            raise ValueError('Transcription failed: ' + str(out['error'])[:200])
        text = str(out.get('text') or '').strip()[:4000]
        if text.lower().strip(' .!?') in WHISPER_SILENCE_HALLUCINATIONS and seconds < 2.5:
            text = ''
        with self.lock:
            if session != self.session:
                return {'accepted': False, 'discarded': True, 'sequence': sequence}
            self.last_sequence = max(self.last_sequence, sequence)
            self.audio_seconds += seconds
            if text:
                self._event('final', text=text, confidence=out.get('avg_logprob'), sequence=sequence, device=out.get('device'))
            result = {
                'accepted': True,
                'sequence': sequence,
                'text': text,
                'seconds': round(seconds, 2),
                'avg_logprob': out.get('avg_logprob'),
                'device': out.get('device'),
                'ms': out.get('ms'),
                'status': self.status,
                'session': self.session,
                'seq': self.seq,
            }
            self.results[sequence] = result
            return result

    def _fail(self, code: str, message: str) -> dict:
        self.status = 'error'
        self.error = {'code': code, 'message': message}
        self._event('error', code=code, message=message)
        return self.snapshot()

    def stop(self, session: str | None = None, reason: str = 'user') -> dict:
        with self.lock:
            proc = self.proc
            if session and self.session and session != self.session:
                return self.snapshot()
            if proc is None:
                if self.status != 'error':
                    self.status = 'idle'
                self.interim = ''
                return self.snapshot()
            self.status = 'stopping'
            self._event('state', status='stopping', reason=reason)
            whisper = self._is_whisper()
            browser = self.capture == 'browser-audio'
        self._terminate(proc)
        if whisper:
            try:
                proc.wait(timeout=3.0)
            except Exception:
                pass
            with self.lock:
                if self.proc is proc:
                    self.proc = None
                    self.interim = ''
                    if self.status != 'error':
                        self.status = 'idle'
                    self._event('state', status=self.status, reason=reason, release_microphone=browser)
        return self.snapshot()

    def _terminate(self, proc):
        try:
            if proc.stdin:
                proc.stdin.write('stop\n')
                proc.stdin.flush()
                proc.stdin.close()
        except (OSError, ValueError):
            pass

        def reap():
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        threading.Thread(target=reap, daemon=True, name='dictation-reap').start()

    def poll(self, since: int = 0, session: str | None = None) -> dict:
        with self.lock:
            if not session or session == self.session:
                self.lease = self.clock()
            return self.snapshot(int(since or 0))

    def shutdown(self):
        with self.lock:
            self.closed = True
        self.stop(reason='shutdown')

    # --------------------------------------------------------------- helpers
    def _read(self, proc, session):
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    if session != self.session:
                        break
                    self._handle(msg)
        except (OSError, ValueError):
            pass
        finally:
            try:
                code = proc.wait(timeout=5)
            except Exception:
                code = None
            with self.lock:
                if session == self.session and self.proc is proc:
                    self.proc = None
                    self.interim = ''
                    if self.status != 'error':
                        if code not in (0, None) and not self.error:
                            self.status = 'error'
                            self.error = {'code': 'helper-exit', 'message': f'The dictation helper stopped unexpectedly (exit {code}).'}
                            self._event('error', **self.error)
                        else:
                            self.status = 'idle'
                    self._event('state', status=self.status)

    def _handle(self, msg: dict):
        kind = msg.get('type')
        if kind == 'listening':
            self.status = 'listening'
            self.engine = f"{msg.get('engine') or 'Windows speech recognizer'} · {msg.get('culture') or ''} · offline · on this PC".replace(' ·  ·', ' ·')
            self._event('state', status='listening', engine=self.engine)
        elif kind == 'interim':
            self.interim = str(msg.get('text') or '')[:2000]
        elif kind == 'speech_start':
            self._event('speech_start')
        elif kind == 'final':
            text = str(msg.get('text') or '').strip()[:4000]
            self.interim = ''
            if text:
                self._event('final', text=text, confidence=msg.get('confidence'), device=msg.get('device'))
        elif kind == 'level':
            try:
                self.level = max(0, min(100, int(msg.get('level') or 0)))
            except (TypeError, ValueError):
                self.level = 0
        elif kind == 'error':
            self.status = 'error'
            self.error = {'code': str(msg.get('code') or 'recognizer'), 'message': str(msg.get('message') or 'Speech recognition failed.')[:500]}
            self._event('error', **self.error)
        elif kind == 'stopped':
            self.interim = ''
            if msg.get('reason') == 'time-limit':
                self._event('state', status='stopping', reason='time-limit')

    def _watch(self):
        while True:
            time.sleep(1.0)
            self.check_lease()
            with self.lock:
                if self.closed and self.proc is None:
                    return

    def check_lease(self):
        """Stop a session whose composer stopped polling (closed, hidden or crashed window)."""
        with self.lock:
            expired = self.proc is not None and self.status in ('starting', 'listening') and (
                self.clock() - self.lease > self.lease_seconds
                or (self._is_whisper() and self.clock() - self.started > self.max_seconds + 60)
            )
            session = self.session
        if expired:
            self.stop(session, reason='lease-expired')
        return expired
