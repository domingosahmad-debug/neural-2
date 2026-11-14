"""Offline song identification and timeline alignment for TonyFX Analyze.

The reference can contain dialogue, sound effects, or only a short excerpt of
the supplied song.  We compare several clean windows instead of assuming that
the reference starts with music, then return the source-time relationship that
After Effects needs for a frame-aligned audio layer.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np


Progress = Callable[[float, str], None]
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".mp4", ".mov", ".mkv", ".webm"}


def _media_candidates(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in AUDIO_EXTENSIONS else []
    if not source.is_dir():
        return []
    items = [item for item in source.rglob("*") if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS]
    return sorted(items, key=lambda item: (len(item.parts), item.name.lower()))[:80]


def _extract_audio(source: Path, target: Path, ffmpeg: str) -> None:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-err_detect", "ignore_err", "-i", str(source),
         "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(target)],
        check=False, capture_output=True, text=True, creationflags=flags,
    )
    if completed.returncode != 0 or not target.exists() or target.stat().st_size < 2048:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Could not decode audio from {source.name}. {detail[-500:]}")


def _features(wav: Path) -> dict[str, Any]:
    try:
        import librosa
    except ModuleNotFoundError:
        # TonyFX and Replica Lab intentionally share the pinned local analysis
        # stack.  The panel worker may be launched by a lean Python runtime, so
        # expose the canonical 3.12 environment before giving up on exact song
        # alignment.
        candidates = [
            Path.home() / "Documents" / "New project" / "TFX_REPLICA_LAB" / ".venv" / "Lib" / "site-packages",
            Path(__file__).resolve().parents[2] / "TFX_REPLICA_LAB" / ".venv" / "Lib" / "site-packages",
        ]
        for candidate in candidates:
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
        import librosa

    y, sr = librosa.load(str(wav), sr=22050, mono=True)
    if y.size < sr:
        raise RuntimeError("Audio is too short to identify reliably.")
    peak = float(np.max(np.abs(y)))
    if peak > 1e-7:
        y = y / peak
    hop = 2048
    harmonic, percussive = librosa.effects.hpss(y)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr, hop_length=hop)
    onset = librosa.onset.onset_strength(y=percussive, sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    count = min(chroma.shape[1], onset.size, rms.size)
    chroma = chroma[:, :count].astype(np.float32)
    onset = onset[:count].astype(np.float32)
    rms = rms[:count].astype(np.float32)
    chroma /= np.maximum(np.linalg.norm(chroma, axis=0, keepdims=True), 1e-6)
    onset = (onset - float(np.median(onset))) / max(float(np.std(onset)), 1e-6)
    onset = np.clip(onset, -2.5, 5.0)
    duration = float(y.size / sr)
    try:
        tempo_value, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
        tempo = float(np.asarray(tempo_value).reshape(-1)[0])
    except Exception:
        tempo = 0.0
    return {"chroma": chroma, "onset": onset, "rms": rms, "duration": duration, "secondsPerFrame": hop / sr, "tempo": tempo}


def _resample_feature(values: np.ndarray, ratio: float) -> np.ndarray:
    length = max(8, int(round(values.shape[-1] / max(ratio, 1e-6))))
    source_x = np.linspace(0.0, 1.0, values.shape[-1], dtype=np.float32)
    target_x = np.linspace(0.0, 1.0, length, dtype=np.float32)
    if values.ndim == 1:
        return np.interp(target_x, source_x, values).astype(np.float32)
    return np.vstack([np.interp(target_x, source_x, row) for row in values]).astype(np.float32)


def _window_score(reference: dict[str, Any], candidate: dict[str, Any], ref_start: int, ref_length: int, ratio: float) -> tuple[float, int, int]:
    ref_chroma = _resample_feature(reference["chroma"][:, ref_start:ref_start + ref_length], ratio)
    ref_onset = _resample_feature(reference["onset"][ref_start:ref_start + ref_length], ratio)
    candidate_chroma = candidate["chroma"]
    candidate_onset = candidate["onset"]
    length = min(ref_chroma.shape[1], candidate_chroma.shape[1])
    if length < 24:
        return -1.0, 0, length
    ref_chroma = ref_chroma[:, :length]
    ref_onset = ref_onset[:length]
    maximum = candidate_chroma.shape[1] - length
    if maximum < 0:
        return -1.0, 0, length
    # Exact same-song excerpts produce a stable chroma diagonal even with
    # dialogue and SFX mixed over them.  Onsets break ties between song sections.
    best_score, best_offset = -1.0, 0
    ref_onset_norm = ref_onset / max(float(np.linalg.norm(ref_onset)), 1e-6)
    for offset in range(maximum + 1):
        cand = candidate_chroma[:, offset:offset + length]
        chroma_score = float(np.mean(np.sum(ref_chroma * cand, axis=0)))
        cand_onset = candidate_onset[offset:offset + length]
        cand_onset_norm = cand_onset / max(float(np.linalg.norm(cand_onset)), 1e-6)
        onset_score = float(np.dot(ref_onset_norm, cand_onset_norm))
        score = chroma_score * 0.78 + onset_score * 0.22
        if score > best_score:
            best_score, best_offset = score, offset
    return best_score, best_offset, length


def _match_pair(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    seconds_per_frame = float(reference["secondsPerFrame"])
    window_seconds = min(16.0, max(8.0, reference["duration"] * 0.42))
    window_frames = max(48, int(round(window_seconds / seconds_per_frame)))
    maximum_start = max(0, reference["chroma"].shape[1] - window_frames)
    starts = sorted(set(int(round(value)) for value in np.linspace(0, maximum_start, min(12, max(3, maximum_start // max(1, window_frames // 3) + 1)))))
    ratios = (0.94, 0.97, 1.0, 1.03, 1.06)
    results: list[dict[str, Any]] = []
    for start in starts:
        energy = float(np.mean(reference["rms"][start:start + window_frames]))
        if energy < float(np.percentile(reference["rms"], 25)) * 0.65:
            continue
        for ratio in ratios:
            score, offset, used = _window_score(reference, candidate, start, window_frames, ratio)
            if score >= 0:
                results.append({"score": score, "referenceFrame": start, "songFrame": offset, "frames": used, "speedRatio": ratio})
    if not results:
        return {"score": -1.0}
    results.sort(key=lambda item: item["score"], reverse=True)
    best = results[0]
    runner_up = next((item for item in results[1:] if abs(item["songFrame"] - best["songFrame"]) > best["frames"] // 2), results[min(1, len(results) - 1)])
    margin = max(0.0, best["score"] - runner_up["score"])
    confidence = float(np.clip((best["score"] - 0.20) / 0.58 + margin * 0.7, 0.0, 0.995))
    return {**best, "confidence": confidence, "runnerUpScore": runner_up["score"]}


def match_song_source(reference_media: Path, song_source: Path, output_dir: Path, ffmpeg: str, progress: Progress | None = None) -> dict[str, Any]:
    progress = progress or (lambda _percent, _message: None)
    candidates = _media_candidates(song_source.resolve())
    if not candidates:
        return {"available": False, "reason": "No supported song files were found in the selected file or folder.", "source": str(song_source)}
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tonyfx-song-match-", dir=str(output_dir)) as temporary:
        temp = Path(temporary)
        reference_wav = temp / "reference.wav"
        progress(1, "Decoding reference audio for song matching")
        _extract_audio(reference_media, reference_wav, ffmpeg)
        reference = _features(reference_wav)
        ranked: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for index, candidate_path in enumerate(candidates):
            progress(5 + 90 * index / max(1, len(candidates)), f"Matching song {index + 1}/{len(candidates)}: {candidate_path.name}")
            try:
                candidate_wav = temp / f"candidate-{index:03d}.wav"
                _extract_audio(candidate_path, candidate_wav, ffmpeg)
                candidate = _features(candidate_wav)
                match = _match_pair(reference, candidate)
                if match.get("score", -1) < 0:
                    continue
                ref_start = float(match["referenceFrame"] * reference["secondsPerFrame"])
                song_start = float(match["songFrame"] * candidate["secondsPerFrame"])
                speed_ratio = float(match["speedRatio"])
                ranked.append({
                    "songPath": str(candidate_path.resolve()), "songName": candidate_path.name,
                    "referenceStart": round(ref_start, 6), "songStart": round(song_start, 6),
                    "timelineLayerStart": round(ref_start - song_start / max(speed_ratio, 1e-6), 6),
                    "speedRatio": round(speed_ratio, 5), "stretchPercent": round(100.0 / max(speed_ratio, 1e-6), 5),
                    "score": round(float(match["score"]), 6), "confidence": round(float(match["confidence"]), 4),
                    "referenceTempo": round(float(reference.get("tempo") or 0), 3), "songTempo": round(float(candidate.get("tempo") or 0), 3),
                    "songDuration": round(float(candidate["duration"]), 6), "matchedDuration": round(float(match["frames"] * reference["secondsPerFrame"]), 6),
                    "method": "multi-window chroma plus onset alignment",
                })
            except Exception as error:
                failures.append({"path": str(candidate_path), "error": str(error)})
        if not ranked:
            return {"available": False, "reason": "None of the supplied files could be matched to the reference audio.", "source": str(song_source), "failures": failures}
        ranked.sort(key=lambda item: (item["confidence"], item["score"]), reverse=True)
        best = ranked[0]
        accepted = best["confidence"] >= 0.52
        return {
            "available": True, "accepted": accepted, **best,
            "candidateCount": len(candidates), "alternatives": ranked[1:6], "failures": failures,
            "warning": "" if accepted else "The selected song resembles the reference, but confidence is too low for automatic timeline placement.",
        }
