"""Dictation transcription worker: one process, one cached model, JSON lines on stdin/stdout.

Supports both:
1. Live host microphone capture in RAM via sounddevice (16 kHz mono float32, never saved to disk),
   emitting level, speech_start, interim, and final events.
2. Chunked base64 16-bit mono WAV requests on stdin ({id, audio}), decoded in RAM and returned
   as {type: 'chunk_result', id, text, ...}.

No network access and no model download: HF_HUB_OFFLINE is forced. Exiting closes the mic stream
immediately and releases the cached model memory.
"""
from collections import deque
import base64
import io
import json
import math
import os
import sys
import threading
import time
import wave

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
VOCAB = ('Neural, Signal, Lumen, Leader, Codex, Sol, Argon, Gemini, Flash, Opus, Sonnet, Antigravity, TonyFX, After Effects, '
         'AE, comp, keyframe, matte, captions, storyboard, render, screening, director.')
SILENCE_HALLUCINATIONS = {'', 'you', 'thank you', 'thanks for watching', 'bye'}

WRITE_LOCK = threading.Lock()
MODEL_LOCK = threading.Lock()


def emit(obj):
    line = json.dumps(obj, ensure_ascii=False) + '\n'
    with WRITE_LOCK:
        sys.stdout.write(line)
        sys.stdout.flush()


def decode(wav_bytes):
    import numpy as np
    with wave.open(io.BytesIO(wav_bytes)) as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError('Expected 16-bit mono audio')
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype('float32') / 32768.0
    if rate != 16000 and len(pcm):
        n = int(round(len(pcm) * 16000 / rate))
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype('float32')
    return pcm


def transcribe_pcm(model, pcm, language, device):
    start = time.monotonic()
    with MODEL_LOCK:
        segments, info = model.transcribe(
            pcm,
            language=language,
            beam_size=5,
            temperature=0,
            vad_filter=True,
            vad_parameters={'min_silence_duration_ms': 400},
            condition_on_previous_text=False,
            initial_prompt=VOCAB,
            no_speech_threshold=0.6,
        )
        segments = list(segments)
    text = ' '.join(s.text.strip() for s in segments).strip()
    conf = (sum(s.avg_logprob for s in segments) / len(segments)) if segments else None
    seconds = len(pcm) / 16000.0
    if text.lower().strip(' .!?') in SILENCE_HALLUCINATIONS and seconds < 2.5:
        text = ''
    return {
        'text': text,
        'avg_logprob': None if conf is None else round(conf, 3),
        'device': device,
        'language': getattr(info, 'language', None),
        'ms': round((time.monotonic() - start) * 1000),
    }


def mic_capture_loop(model, cfg, device, stop_event: threading.Event):
    import numpy as np
    try:
        import sounddevice as sd
    except Exception as exc:
        emit({'type': 'error', 'code': 'no-audio-backend', 'message': 'Local microphone library unavailable: ' + str(exc)[:240]})
        stop_event.set()
        return

    max_seconds = float(cfg.get('max_seconds') or 300)
    language = cfg.get('language')
    q_blocks = deque(maxlen=400)
    block_ready = threading.Event()

    def callback(indata, frames, time_info, status):
        if stop_event.is_set():
            return
        q_blocks.append(indata[:, 0].copy())
        block_ready.set()

    preroll = deque(maxlen=3)  # 300ms pre-roll at 100ms/block
    utterance = []
    speaking = False
    silence_blocks = 0
    last_level_emit = 0.0
    started_at = time.monotonic()

    try:
        with sd.InputStream(samplerate=16000, channels=1, dtype='float32', blocksize=1600, callback=callback):
            while not stop_event.is_set():
                if time.monotonic() - started_at >= max_seconds:
                    emit({'type': 'stopped', 'reason': 'time-limit'})
                    stop_event.set()
                    break
                if not q_blocks:
                    block_ready.wait(0.1)
                    block_ready.clear()
                    continue
                block = q_blocks.popleft()
                rms = float(math.sqrt(float(np.mean(block * block)))) if len(block) else 0.0
                now = time.monotonic()
                if now - last_level_emit >= 0.18:
                    last_level_emit = now
                    emit({'type': 'level', 'level': max(0, min(100, int(round(rms * 420))))})

                if not speaking:
                    if rms >= 0.012:
                        speaking = True
                        silence_blocks = 0
                        utterance = list(preroll) + [block]
                        emit({'type': 'speech_start'})
                        emit({'type': 'interim', 'text': 'Listening…'})
                    else:
                        preroll.append(block)
                else:
                    utterance.append(block)
                    if rms < 0.009:
                        silence_blocks += 1
                    else:
                        silence_blocks = 0
                    # Flush after ~650ms of trailing silence or 14s continuous speech
                    if silence_blocks >= 7 or len(utterance) >= 140:
                        pcm = np.concatenate(utterance).astype('float32')
                        utterance = []
                        speaking = False
                        silence_blocks = 0
                        if len(pcm) >= 5600:  # >= 0.35s
                            emit({'type': 'interim', 'text': 'Transcribing…'})
                            try:
                                res = transcribe_pcm(model, pcm, language, device)
                                if res['text']:
                                    emit({'type': 'final', 'text': res['text'], 'confidence': res['avg_logprob'], 'device': device})
                                else:
                                    emit({'type': 'interim', 'text': ''})
                            except Exception as exc:
                                emit({'type': 'error', 'code': 'recognizer', 'message': str(exc)[:300]})
                        else:
                            emit({'type': 'interim', 'text': ''})
    except Exception as exc:
        emit({'type': 'error', 'code': 'no-microphone', 'message': 'Could not open default microphone: ' + str(exc)[:260]})
        stop_event.set()
        return

    # InputStream is now closed (microphone released). Transcribe any trailing phrase >= 0.35s.
    if utterance:
        pcm = np.concatenate(utterance).astype('float32')
        if len(pcm) >= 5600:
            try:
                res = transcribe_pcm(model, pcm, language, device)
                if res['text']:
                    emit({'type': 'final', 'text': res['text'], 'confidence': res['avg_logprob'], 'device': device})
            except Exception:
                pass


def main():
    cfg = json.loads(sys.argv[1])
    if cfg.get('deps'):
        sys.path.insert(0, cfg['deps'])
    from faster_whisper import WhisperModel
    device = cfg['device']
    try:
        model = WhisperModel(cfg['model_path'], device=device, compute_type=cfg['compute_type'], cpu_threads=cfg.get('cpu_threads', 0))
    except Exception:
        if device == 'cpu':
            raise
        # The GPU became unavailable between planning and loading: use CPU, never touch another worker's memory.
        device = 'cpu'
        model = WhisperModel(cfg['model_path'], device='cpu', compute_type='int8', cpu_threads=max(1, min(4, os.cpu_count() or 2)))

    stop_event = threading.Event()
    mic_thread = None
    capture_mic = bool(cfg.get('capture_mic')) and os.environ.get('NEURAL_DICTATION_NO_MIC') != '1'
    emit({'type': 'ready', 'ready': True, 'device': device, 'engine': cfg.get('label'), 'size': cfg.get('size'), 'capture_mic': capture_mic})
    if capture_mic:
        mic_thread = threading.Thread(target=mic_capture_loop, args=(model, cfg, device, stop_event), daemon=True, name='whisper-mic')
        mic_thread.start()

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line or line == 'stop':
                break
            try:
                req = json.loads(line)
            except ValueError:
                break
            if req.get('cmd') == 'stop':
                break
            try:
                pcm = decode(base64.b64decode(req['audio'], validate=True))
                res = transcribe_pcm(model, pcm, cfg.get('language'), device)
                emit({'type': 'chunk_result', 'id': req.get('id'), **res})
            except Exception as e:
                emit({'type': 'chunk_result', 'id': req.get('id'), 'error': str(e)[:400]})
    finally:
        stop_event.set()
        if mic_thread is not None:
            mic_thread.join(timeout=4.0)
        emit({'type': 'stopped', 'reason': 'stopped'})


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        emit({'type': 'ready', 'ready': False, 'error': str(e)[:500]})
        sys.exit(1)
