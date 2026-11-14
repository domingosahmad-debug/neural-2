"""Long-lived local speech worker. One process per mode, JSON lines over stdin/stdout.

stt: faster-whisper (already installed for captions in ../.caption_deps) on the GPU, CPU fallback.
tts: Kokoro-82M ONNX voices (installed by Setup-Voice.cmd into .tools/voice-python).
No network access, no model downloads, no inference unless the app sends a request.
"""
import base64, io, json, os, sys, time, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
# Names Whisper otherwise mishears; used as a light prompt, never as an instruction.
VOCAB = ('Neural, Signal, Lumen, Leader, Codex, Pip, Nova, Scout, Echo, Sage, Argon, Gemini, Flash, Opus, Sonnet, '
         'Antigravity, OpenCode, TonyFX, After Effects, AE, Twixtor, Lumetri, BlurMoCurves, Kintaki, Akaza, Tanjiro, '
         'storyboard, render, comp, keyframe, matte, captions, screening, director.')


def emit(obj):
    sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


def stt():
    sys.path.insert(0, str(PROJECT / '.caption_deps'))
    from faster_whisper import WhisperModel
    candidates = [ROOT / '.models' / 'faster-whisper-small.en', PROJECT / 'models' / 'faster-whisper-small.en']
    model_path = next((p for p in candidates if (p / 'model.bin').is_file()), None)
    if model_path is None:
        raise RuntimeError('faster-whisper small.en model folder was not found')
    prefer_cpu = os.environ.get('NEURAL_VOICE_CPU') == '1'
    model, device = None, None
    if not prefer_cpu:
        try:
            model, device = WhisperModel(str(model_path), device='cuda', compute_type='float16'), 'cuda'
        except Exception:
            model = None
    if model is None:
        model, device = WhisperModel(str(model_path), device='cpu', compute_type='int8', cpu_threads=4), 'cpu'
    emit({'ready': True, 'engine': 'faster-whisper small.en', 'device': device})
    for line in sys.stdin:
        req = json.loads(line)
        start = time.monotonic()
        try:
            segments, info = model.transcribe(req['path'], language='en', beam_size=5, temperature=0,
                                              vad_filter=True, vad_parameters={'min_silence_duration_ms': 400},
                                              condition_on_previous_text=False, initial_prompt=VOCAB,
                                              no_speech_threshold=.6)
            segments = list(segments)
            text = ' '.join(s.text.strip() for s in segments).strip()
            conf = (sum(s.avg_logprob for s in segments) / len(segments)) if segments else -9
            emit({'id': req['id'], 'text': text, 'avg_logprob': round(conf, 3), 'device': device,
                  'ms': round((time.monotonic() - start) * 1000)})
        except Exception as e:
            emit({'id': req['id'], 'error': str(e)[:400]})


def tts():
    sys.path.insert(0, str(ROOT / '.tools' / 'voice-python'))
    from kokoro_onnx import Kokoro
    import numpy as np
    folder = ROOT / '.models' / 'kokoro'
    kokoro = Kokoro(str(folder / 'kokoro-v1.0.onnx'), str(folder / 'voices-v1.0.bin'))
    voices = sorted(kokoro.get_voices()) if hasattr(kokoro, 'get_voices') else []
    emit({'ready': True, 'engine': 'Kokoro-82M', 'voices': voices})
    for line in sys.stdin:
        req = json.loads(line)
        start = time.monotonic()
        try:
            voice = req.get('voice') or 'bm_george'
            samples, rate = kokoro.create(req['text'], voice=voice, speed=float(req.get('speed') or 1.0),
                                          lang='en-gb' if voice.startswith('b') else 'en-us')
            pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(rate)); w.writeframes(pcm)
            emit({'id': req['id'], 'wav': base64.b64encode(buf.getvalue()).decode(), 'rate': int(rate),
                  'seconds': round(len(samples) / rate, 2), 'ms': round((time.monotonic() - start) * 1000)})
        except Exception as e:
            emit({'id': req['id'], 'error': str(e)[:400]})


if __name__ == '__main__':
    try:
        {'stt': stt, 'tts': tts}[sys.argv[1]]()
    except Exception as e:
        emit({'ready': False, 'error': str(e)[:500]})
        sys.exit(1)
