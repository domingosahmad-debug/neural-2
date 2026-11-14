"""Cached-local speech engine discovery and honest device planning (no downloads, no inference).

Enumerates only model folders that already exist on this PC. Paths are matched by structure
(``model.bin``), never printed with credentials, and nothing is fetched. Whether a model's
runtime loads is verified when a session starts, not claimed here.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

# Rough working-set needs for planning only (MiB of free VRAM required before choosing the GPU).
VRAM_NEED_MB = {'large-v3': 4500, 'small': 1800, 'small.en': 1800, 'base': 900, 'tiny.en': 600}

ENGINE_SPECS = [
    # id, label, size key, language, accuracy rank (higher = more accurate), latency note
    ('whisper-large-v3', 'Whisper large-v3 · best accuracy', 'large-v3', None, 4, 'highest latency; GPU strongly recommended, CPU fallback is slow'),
    ('whisper-small', 'Whisper small (multilingual)', 'small', None, 2, 'medium latency; fine on CPU'),
    ('whisper-small-en', 'Whisper small.en · fast English', 'small.en', 'en', 3, 'low latency on CPU or GPU'),
    ('whisper-base', 'Whisper base · quick draft', 'base', None, 1, 'very low latency, lower accuracy'),
    ('whisper-tiny-en', 'Whisper tiny.en · instant draft', 'tiny.en', 'en', 0, 'lowest latency, lowest accuracy'),
]


def project_roots(root: Path = ROOT) -> list[Path]:
    """Folders that may hold speech dependencies: env override, the app root and its ancestors."""
    roots = []
    override = os.environ.get('NEURAL_SPEECH_ROOT')
    if override:
        roots.append(Path(override))
    roots.append(root)
    roots.extend(list(root.resolve().parents)[:4])
    seen, out = set(), []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def find_deps(root: Path = ROOT) -> Path | None:
    """faster-whisper python dependencies shared with the caption tools (read only)."""
    for r in project_roots(root):
        p = r / '.caption_deps'
        if (p / 'faster_whisper').is_dir():
            return p
    return None


def _model_dirs(root: Path) -> dict[str, Path]:
    """size key -> existing folder containing model.bin."""
    found: dict[str, Path] = {}
    names = {'faster-whisper-large-v3': 'large-v3', 'faster-whisper-small': 'small', 'faster-whisper-small.en': 'small.en',
             'faster-whisper-base': 'base', 'faster-whisper-tiny.en': 'tiny.en'}
    bases = []
    for r in project_roots(root):
        bases += [r / '.models', r / 'models']
    for base in bases:
        for folder, key in names.items():
            p = base / folder
            if key not in found and (p / 'model.bin').is_file():
                found[key] = p
    hub = Path(os.environ.get('HF_HOME') or (Path.home() / '.cache' / 'huggingface')) / 'hub'
    for repo, key in (('models--Systran--faster-whisper-large-v3', 'large-v3'), ('models--Systran--faster-whisper-small', 'small'),
                      ('models--Systran--faster-whisper-small.en', 'small.en'), ('models--Systran--faster-whisper-base', 'base'),
                      ('models--Systran--faster-whisper-tiny.en', 'tiny.en')):
        if key in found:
            continue
        snaps = hub / repo / 'snapshots'
        try:
            for snap in sorted(snaps.iterdir(), reverse=True):
                if (snap / 'model.bin').is_file():
                    found[key] = snap
                    break
        except OSError:
            continue
    return found


def gpu_free_mb(timeout: float = 4.0) -> int | None:
    """Free VRAM on the first NVIDIA GPU via the read-only nvidia-smi query; None when unknown."""
    exe = shutil.which('nvidia-smi')
    if not exe:
        return None
    try:
        out = subprocess.run([exe, '--query-gpu=memory.free', '--format=csv,noheader,nounits'], capture_output=True, text=True,
                             timeout=timeout, creationflags=CREATE_NO_WINDOW)
        if out.returncode:
            return None
        return int(out.stdout.strip().splitlines()[0])
    except (OSError, ValueError, subprocess.SubprocessError, IndexError):
        return None


def device_plan(size_key: str, busy_reason: str | None = None, free_mb=gpu_free_mb) -> dict:
    """Pick cuda only with verified headroom and no active media/GPU owner; otherwise CPU int8.

    Never frees or unloads memory owned by another process: it only declines the GPU.
    """
    forced = os.environ.get('NEURAL_DICTATION_DEVICE', 'auto').lower()
    cpu = {'device': 'cpu', 'compute_type': 'int8', 'cpu_threads': max(1, min(4, os.cpu_count() or 2))}
    if forced == 'cpu':
        return {**cpu, 'reason': 'CPU forced by NEURAL_DICTATION_DEVICE.'}
    if busy_reason:
        return {**cpu, 'reason': 'CPU because the GPU/media lane is busy (' + busy_reason + '); no other model is unloaded.'}
    free = free_mb()
    need = VRAM_NEED_MB.get(size_key, 2000)
    if free is None:
        return {**cpu, 'reason': 'CPU because GPU memory could not be verified.'}
    if free < need:
        return {**cpu, 'reason': f'CPU because only {free} MiB of GPU memory is free (needs about {need} MiB); another worker\'s model is left untouched.'}
    return {'device': 'cuda', 'compute_type': 'float16', 'cpu_threads': 0, 'reason': f'GPU: {free} MiB free (needs about {need} MiB).'}


def whisper_engines(root: Path = ROOT, busy_reason: str | None = None, free_mb=gpu_free_mb) -> list[dict]:
    deps = find_deps(root)
    models = _model_dirs(root)
    rows = []
    for eid, label, key, language, rank, latency in ENGINE_SPECS:
        have_model = key in models
        if deps and have_model:
            plan = device_plan(key, busy_reason, free_mb)
            detail = f'Cached local model · {latency} · {plan["reason"]} Offline; no download; mic audio stays in RAM (never saved).'
        elif not deps:
            plan = None
            detail = 'faster-whisper dependencies were not found; nothing is downloaded automatically.'
        else:
            plan = None
            detail = 'No cached ' + key + ' model folder was found; nothing is downloaded automatically.'
        rows.append({'id': eid, 'label': label, 'available': bool(deps and have_model), 'detail': detail, 'kind': 'whisper', 'capture': 'local-mic',
                     'supports_audio_upload': True, 'accuracy_rank': rank, 'size': key, 'language': language or 'auto', 'device_plan': plan,
                     'path_known': have_model, 'verified_at_start_only': True})
    return rows


def default_whisper(engines: list[dict]) -> str | None:
    """Prefer large-v3 only when its plan is GPU; otherwise the most accurate fast model that is cached."""
    by = {e['id']: e for e in engines if e['available']}
    large = by.get('whisper-large-v3')
    if large and large['device_plan'] and large['device_plan']['device'] == 'cuda':
        return large['id']
    for eid in ('whisper-small-en', 'whisper-small', 'whisper-base', 'whisper-tiny-en', 'whisper-large-v3'):
        if eid in by:
            return eid
    return None


def model_path(engine_id: str, root: Path = ROOT) -> tuple[Path, dict]:
    for spec in ENGINE_SPECS:
        if spec[0] == engine_id:
            models = _model_dirs(root)
            if spec[2] not in models:
                raise ValueError('The ' + spec[2] + ' model is not cached on this PC; nothing was downloaded.')
            return models[spec[2]], {'size': spec[2], 'language': spec[3]}
    raise ValueError('Unknown dictation engine')
