"""Local voice for the studio helper: accurate listening (Whisper) and natural speech (Kokoro).

Workers start only while the helper is on, and stop when it turns off or sits idle, so the GPU/RAM go
back to After Effects. Nothing here calls a language model; transcripts go to the helper like typed text.
"""
import base64, json, os, subprocess, sys, threading, time, uuid, wave, io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
VOICES = [
    {'id': 'bm_george', 'label': 'George · British, calm (Jarvis-like)'},
    {'id': 'bm_fable', 'label': 'Fable · British, warm'},
    {'id': 'af_heart', 'label': 'Heart · American, most natural'},
    {'id': 'af_bella', 'label': 'Bella · American, bright'},
    {'id': 'bf_emma', 'label': 'Emma · British'},
    {'id': 'am_michael', 'label': 'Michael · American'},
]
MAX_AUDIO_BYTES = 2_900_000      # ~90 s of 16 kHz mono PCM
MAX_TTS_CHARS = 600              # one or two sentences per request; the UI streams sentence by sentence
IDLE_STOP_SECONDS = 600


class Worker:
    def __init__(self, mode, timeout):
        self.mode, self.timeout = mode, timeout
        self.proc = None
        self.info = {}
        self.lock = threading.Lock()
        self.last_used = 0.0
        self.error = None

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self.alive():
            return self.info
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if sys.platform == 'win32' else 0
        self.proc = subprocess.Popen([sys.executable, '-u', str(ROOT / 'app' / 'voice_worker.py'), self.mode],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding='utf-8', creationflags=flags, cwd=str(ROOT))
        first = self._readline(90)
        info = json.loads(first) if first else {'ready': False, 'error': 'Voice worker did not start'}
        if not info.get('ready'):
            self.error = info.get('error')
            self.stop()
            raise ValueError(f'{self.mode.upper()} unavailable: {self.error}')
        self.info, self.error = info, None
        self.last_used = time.monotonic()
        return info

    def _readline(self, timeout):
        result = []
        reader = threading.Thread(target=lambda: result.append(self.proc.stdout.readline()), daemon=True)
        reader.start(); reader.join(timeout)
        if reader.is_alive():
            self.stop()
            raise ValueError(f'{self.mode.upper()} worker timed out; it was stopped and will restart on the next request')
        return result[0] if result else ''

    def request(self, payload):
        with self.lock:
            self.start()
            payload = {'id': uuid.uuid4().hex, **payload}
            self.proc.stdin.write(json.dumps(payload) + '\n'); self.proc.stdin.flush()
            line = self._readline(self.timeout)
            if not line:
                self.stop()
                raise ValueError(f'{self.mode.upper()} worker stopped unexpectedly')
            out = json.loads(line)
            self.last_used = time.monotonic()
            if out.get('error'):
                raise ValueError(out['error'])
            return out

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.stdin.close()
            except OSError:
                pass
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()


class VoiceEngine:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.audio_dir = self.root / 'data' / 'helper' / 'audio'
        self.stt = Worker('stt', 45)
        self.tts = Worker('tts', 45)
        self.closed = False
        threading.Thread(target=self._idle_reaper, daemon=True, name='voice-idle').start()

    # ---------- capability, no processes started ----------
    def whisper_installed(self):
        deps = PROJECT / '.caption_deps' / 'faster_whisper'
        model = any((p / 'model.bin').is_file() for p in [self.root / '.models' / 'faster-whisper-small.en', PROJECT / 'models' / 'faster-whisper-small.en'])
        return deps.is_dir() and model

    def kokoro_installed(self):
        k = self.root / '.models' / 'kokoro'
        return (self.root / '.tools' / 'voice-python' / 'kokoro_onnx').is_dir() and (k / 'kokoro-v1.0.onnx').is_file() and (k / 'voices-v1.0.bin').is_file()

    def state(self):
        return {'listening': {'engine': 'Whisper small.en (local GPU, CPU fallback)', 'installed': self.whisper_installed(),
                              'running': self.stt.alive(), 'device': self.stt.info.get('device'), 'error': self.stt.error},
                'speaking': {'engine': 'Kokoro-82M neural voices (local)', 'installed': self.kokoro_installed(),
                             'running': self.tts.alive(), 'error': self.tts.error,
                             'setup': 'Double-click Setup-Voice.cmd in the NEURAL_STUDIO folder once (about 350 MB).'},
                'voices': VOICES, 'model_calls': 0}

    # ---------- actions ----------
    def warm(self, data=None):
        """Load workers ahead of the first sentence. Called when the helper is switched on."""
        started = {}
        for name, worker, ok in [('listening', self.stt, self.whisper_installed()), ('speaking', self.tts, self.kokoro_installed())]:
            if not ok:
                continue
            try:
                worker.start(); started[name] = True
            except ValueError as e:
                started[name] = str(e)
        return {**self.state(), 'warmed': started}

    def transcribe(self, data):
        if not self.whisper_installed():
            raise ValueError('Whisper is not installed; using Windows recognition instead')
        raw = base64.b64decode(str(data.get('audio', '')), validate=True)
        if not 1000 < len(raw) <= MAX_AUDIO_BYTES or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
            raise ValueError('Expected a short WAV recording')
        with wave.open(io.BytesIO(raw)) as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2 or not 8000 <= w.getframerate() <= 48000:
                raise ValueError('Expected 16-bit mono audio')
            seconds = w.getnframes() / w.getframerate()
        if seconds < .25:
            return {'text': '', 'seconds': seconds}
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        path = self.audio_dir / (uuid.uuid4().hex + '.wav')
        try:
            path.write_bytes(raw)
            out = self.stt.request({'path': str(path)})
        finally:
            path.unlink(missing_ok=True)   # audio is never kept
        text = out.get('text', '').strip()
        # Whisper's common silence hallucinations are dropped rather than sent to the helper.
        if text.lower().strip(' .!?') in {'', 'you', 'thank you', 'thanks for watching', 'bye'} and seconds < 2.5:
            text = ''
        return {'text': text, 'seconds': round(seconds, 2), 'avg_logprob': out.get('avg_logprob'), 'device': out.get('device'), 'ms': out.get('ms')}

    def speak(self, data):
        if not self.kokoro_installed():
            raise ValueError('Natural voice is not installed; using the Windows voice')
        text = ' '.join(str(data.get('text', '')).split())[:MAX_TTS_CHARS]
        if not text:
            raise ValueError('Nothing to say')
        voice = data.get('voice') or 'bm_george'
        if voice not in {v['id'] for v in VOICES}:
            voice = 'bm_george'
        speed = min(1.3, max(.75, float(data.get('speed') or 1.0)))
        out = self.tts.request({'text': text, 'voice': voice, 'speed': speed})
        return {'audio': out['wav'], 'seconds': out.get('seconds'), 'ms': out.get('ms'), 'voice': voice}

    def stop(self, data=None):
        self.stt.stop(); self.tts.stop()
        return self.state()

    def _idle_reaper(self):
        while not self.closed:
            time.sleep(30)
            for w in (self.stt, self.tts):
                if w.alive() and time.monotonic() - w.last_used > IDLE_STOP_SECONDS and not w.lock.locked():
                    w.stop()

    def shutdown(self):
        self.closed = True
        self.stop()
