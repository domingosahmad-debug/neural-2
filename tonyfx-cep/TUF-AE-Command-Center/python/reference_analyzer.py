#!/usr/bin/env python3
"""Offline reference-video forensics for TonyFX.

The analyzer measures the rendered result. It never pretends a flattened video
contains the original editor's plugin names or keyframes; instead it reports
repeatable evidence, likely AE-native recipes, and a confidence score.
"""

from __future__ import annotations

import html
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from reference_intelligence import (
    advanced_audio_structure,
    apply_effect_inventory,
    apply_feedback,
    build_repair_plan,
    fit_temporal_curve,
    load_feedback,
    match_effect_fingerprint,
    narrative_flow_map,
    render_and_score_candidates,
    semantic_shot_requirements,
    subject_framing,
)
from transition_forensics import enrich_events as enrich_transition_forensics
from transition_forensics import transnet_boundaries
from replica_contract import compile_builder_contract


Progress = Callable[[float, str], None]


def _ratio(value: Any) -> float:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        a, b = str(value or "0/1").split("/", 1)
        return float(a) / max(float(b), 1e-9)
    except Exception:
        return 0.0


def probe_media(source: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required for reference analysis.")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
        check=True, text=True, capture_output=True, creationflags=flags,
    )
    raw = json.loads(result.stdout or "{}")
    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in raw.get("streams", []) if s.get("codec_type") == "audio"), {})
    fps_text = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    fps = _ratio(fps_text)
    duration = float((raw.get("format") or {}).get("duration") or video.get("duration") or 0)
    return {
        "path": str(source), "name": source.name, "duration": duration, "fps": fps, "fpsRational": fps_text,
        "width": int(video.get("width") or 0), "height": int(video.get("height") or 0),
        "frames": int(video.get("nb_frames") or round(duration * fps)),
        "videoCodec": video.get("codec_name", ""), "audioCodec": audio.get("codec_name", ""),
        "hasAudio": bool(audio),
    }


def _resize(frame: np.ndarray, width: int) -> np.ndarray:
    if frame.shape[1] <= width:
        return frame
    scale = width / frame.shape[1]
    return cv2.resize(frame, (width, max(2, int(round(frame.shape[0] * scale)))), interpolation=cv2.INTER_AREA)


def _frame_metrics(frame: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return {
        "luma": float(gray.mean()),
        "black": float(np.mean(gray < 18)),
        "white": float(np.mean(gray > 238)),
        "sat": float(hsv[:, :, 1].mean()),
        "sharp": float(cv2.Laplacian(gray, cv2.CV_32F).var()),
    }


def _motion(previous: np.ndarray, current: np.ndarray) -> dict[str, float]:
    a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    diff = float(np.mean(cv2.absdiff(a, b)))
    points = cv2.goodFeaturesToTrack(a, 220, 0.01, 5)
    if points is None or len(points) < 8:
        return {"diff": diff, "dx": 0.0, "dy": 0.0, "scale": 1.0, "rotation": 0.0, "residual": 0.0}
    moved, status, _ = cv2.calcOpticalFlowPyrLK(a, b, points, None, winSize=(21, 21), maxLevel=3)
    good_a = points[status.reshape(-1) == 1].reshape(-1, 2)
    good_b = moved[status.reshape(-1) == 1].reshape(-1, 2)
    if len(good_a) < 8:
        return {"diff": diff, "dx": 0.0, "dy": 0.0, "scale": 1.0, "rotation": 0.0, "residual": 0.0}
    matrix, inliers = cv2.estimateAffinePartial2D(good_a, good_b, method=cv2.RANSAC, ransacReprojThreshold=3)
    if matrix is None:
        delta = np.median(good_b - good_a, axis=0)
        return {"diff": diff, "dx": float(delta[0]), "dy": float(delta[1]), "scale": 1.0, "rotation": 0.0, "residual": 0.0}
    scale = math.sqrt(float(matrix[0, 0] ** 2 + matrix[0, 1] ** 2))
    rotation = math.degrees(math.atan2(float(matrix[1, 0]), float(matrix[0, 0])))
    if abs(float(matrix[0, 2])) > a.shape[1] or abs(float(matrix[1, 2])) > a.shape[0] or not 0.65 < scale < 1.45:
        delta = np.median(good_b - good_a, axis=0)
        return {"diff": diff, "dx": float(delta[0]), "dy": float(delta[1]), "scale": 1.0, "rotation": 0.0, "residual": 0.0}
    predicted = cv2.transform(good_a.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    residual = float(np.median(np.linalg.norm(predicted - good_b, axis=1)))
    return {"diff": diff, "dx": float(matrix[0, 2]), "dy": float(matrix[1, 2]), "scale": scale, "rotation": rotation, "residual": residual}


def _rgb_split(frame: np.ndarray) -> float:
    small = cv2.resize(frame, (max(16, frame.shape[1] // 2), max(16, frame.shape[0] // 2)))
    channels = cv2.split(small)
    shifts = []
    for channel in (channels[0], channels[2]):
        shift, _ = cv2.phaseCorrelate(np.float32(channels[1]), np.float32(channel))
        shifts.append(math.hypot(shift[0], shift[1]))
    return float(max(shifts))


def _peaks(values: list[float], floor: float, spacing: int, robust_factor: float = 3.2) -> list[int]:
    if not values:
        return []
    array = np.asarray(values, dtype=np.float32)
    threshold = max(floor, float(np.median(array) + robust_factor * np.median(np.abs(array - np.median(array)))))
    candidates = [i for i in range(1, len(values) - 1) if values[i] >= threshold and values[i] >= values[i - 1] and values[i] >= values[i + 1]]
    result: list[int] = []
    for candidate in sorted(candidates, key=lambda i: values[i], reverse=True):
        if all(abs(candidate - chosen) >= spacing for chosen in result):
            result.append(candidate)
    return sorted(result)


def _graph_name(samples: list[float]) -> tuple[str, str]:
    if len(samples) < 4:
        return "linear", "0.33, 0.33, 0.67, 0.67"
    values = np.asarray(samples, dtype=np.float32)
    values = np.abs(values - values[0])
    if float(values.max()) < 1e-5:
        return "linear", "0.33, 0.33, 0.67, 0.67"
    values /= values.max()
    first = float(values[min(len(values) - 1, max(1, len(values) // 4))])
    last = float(values[min(len(values) - 1, max(1, 3 * len(values) // 4))])
    if first > 0.6:
        return "sharp_start", "0.10, 0.75, 0.25, 1.00"
    if last < 0.4:
        return "sharp_end", "0.75, 0.00, 0.95, 0.25"
    if first < 0.28 and last > 0.72:
        return "speed_ramp", "0.09, 0.72, 0.94, 0.27"
    return "smooth_in_out", "0.33, 0.00, 0.67, 1.00"


def _effect_recipe(family: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    duration = int(data.get("durationFrames", 4))
    if family.startswith("slide") or family.startswith("whip"):
        direction = family.split("_", 1)[-1]
        angle = {"left": 0, "right": 180, "up": 90, "down": 270}.get(direction, 0)
        return [
            {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}},
            {"property": "Position", "settings": {"direction": direction, "distancePx": int(data.get("travelPx", 420))}},
            {"effect": "Directional Blur", "settings": {"Direction": angle, "Blur Length": int(data.get("blurStrength", 55))}},
        ]
    if family in {"zoom", "zoom_blur"}:
        return [
            {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}},
            {"effect": "BlurMoCurves", "settings": {"Zoom": round(float(data.get("zoomRatio", 1.18)), 3), "frames": duration}},
            {"effect": "Radial Blur", "settings": {"Type": "Zoom", "Amount": int(data.get("blurStrength", 35))}},
        ]
    if family == "black_dip":
        return [{"property": "Opacity", "settings": {"values": [65, 100, 65], "note": "TonyFX approved opacity arch"}}]
    if family == "white_flash":
        return [{"layer": "Adjustment Layer", "effect": "Exposure", "settings": {"Exposure": round(float(data.get("flashExposure", 1.8)), 2)}}]
    if family == "rgb_split":
        return [{"effect": "Channel Blur", "settings": {"Red Blurriness": 16, "Green Blurriness": 4, "Blue Blurriness": 16}}, {"blend": "Add", "durationFrames": duration}]
    if family == "crossfade":
        return [{"property": "Opacity", "settings": {"outgoing": [100, 0], "incoming": [0, 100]}}]
    if family == "spin_zoom":
        return [
            {"property": "Rotation", "settings": {"degrees": round(float(data.get("rotation", data.get("rotationDegrees", 12.0))), 2)}},
            {"property": "Scale", "settings": {"ratio": round(float(data.get("zoomRatio", 1.18)), 4)}},
            {"effect": "Directional Blur", "settings": {"Direction": int(data.get("smearAngle", 0)), "Blur Length": int(max(45, data.get("blurStrength", 65)))}}]
    if family == "perspective_push":
        return [{"effect": "Corner Pin", "settings": {"perspective": round(float(data.get("perspective", 0.12)), 4)}}, {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}}]
    if family == "mask_wipe":
        return [{"property": "Animated Mask", "settings": {"direction": data.get("wipeDirection", "horizontal"), "feather": round(float(data.get("wipeFeather", 28)), 2), "frames": duration}}]
    if family == "impact_shake":
        return [{"property": "Position", "settings": {"impactShakePx": round(float(data.get("shakeAmplitude", 48)), 2), "frames": duration, "settle": True}}]
    if family == "directional_smear":
        return [{"effect": "Directional Blur", "settings": {"Direction": int(data.get("smearAngle", 0)), "Blur Length": int(data.get("blurStrength", 55)), "note": "Keep this localized to the measured transition span."}}]
    if family == "effect_pulse":
        return [{"layer": "Adjustment Layer", "settings": {"durationFrames": duration, "note": "Review required: a visual pulse was measured without a confident named family."}}]
    return [{"transition": "Hard Cut", "settings": {"frameAccurate": True}}]


def _dedupe_recipe(recipe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in recipe:
        identity = str(item.get("effect") or item.get("property") or item.get("transition") or item.get("layer") or "")
        if identity == "Motion Tile" and identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def _candidate_scores(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return transparent, feature-based candidate rankings.

    These are deliberately not called recovered effects. They rank recipes by
    how well their expected visual signature matches the measured pixels.
    """
    black, white = float(event["blackRatio"]), float(event["whiteRatio"])
    travel = max(float(event["translationPx"]["x"]), float(event["translationPx"]["y"]))
    zoom = abs(math.log(max(float(event["zoomRatio"]), 1e-5)))
    rgb_value = float(event["rgbSplitPx"])
    blur = float(event["blurStrength"])
    raw = {
        "hard_cut": 0.45 + max(0.0, 0.3 - travel / 80 - zoom),
        "crossfade": 0.46 + max(0.0, 0.25 - travel / 100) + min(0.15, blur / 500),
        "black_dip": 0.25 + black * 0.75,
        "white_flash": 0.25 + white * 0.75,
        "slide_or_whip": 0.3 + min(0.65, travel / 30),
        "zoom_blur": 0.3 + min(0.45, zoom * 2.5) + min(0.2, blur / 300),
        "rgb_split": 0.25 + min(0.7, rgb_value / 8),
    }
    highest = max(raw.values()) or 1.0
    return [{"candidate": name, "score": round(min(0.99, value / highest), 3)} for name, value in sorted(raw.items(), key=lambda item: item[1], reverse=True)]


def _dense_flow(previous: np.ndarray, current: np.ndarray) -> dict[str, float]:
    a = cv2.resize(previous, (256, max(64, int(previous.shape[0] * 256 / previous.shape[1]))))
    b = cv2.resize(current, (a.shape[1], a.shape[0]))
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 21, 4, 7, 1.5, 0)
    dx, dy = flow[:, :, 0], flow[:, :, 1]
    magnitude = np.hypot(dx, dy)
    return {"medianX": round(float(np.median(dx)), 3), "medianY": round(float(np.median(dy)), 3), "p90Magnitude": round(float(np.percentile(magnitude, 90)), 3), "angle": round(float(math.degrees(math.atan2(float(np.median(dy)), float(np.median(dx))))), 2)}


def _classify_event(index: int, fps: float, metrics: list[dict[str, float]], motions: list[dict[str, float]], rgb: list[float]) -> dict[str, Any]:
    radius = max(2, int(round(fps * 0.16)))
    lo, hi = max(1, index - radius), min(len(metrics) - 1, index + radius)
    window_m = motions[max(0, lo - 1):hi]
    window_f = metrics[lo:hi + 1]
    center = metrics[min(index, len(metrics) - 1)]
    max_dx = max((abs(v["dx"]) for v in window_m), default=0.0)
    max_dy = max((abs(v["dy"]) for v in window_m), default=0.0)
    scale_values = [v["scale"] for v in window_m if 0.85 < v["scale"] < 1.18]
    zoom_ratio = float(np.clip(np.prod(scale_values), 0.60, 1.65)) if scale_values else 1.0
    blur_loss = max((max(0.0, metrics[max(0, index - 2)]["sharp"] - f["sharp"]) for f in window_f), default=0.0)
    black = max((f["black"] for f in window_f), default=0.0)
    white = max((f["white"] for f in window_f), default=0.0)
    rgb_peak = max(rgb[max(0, lo - 1):hi], default=0.0)
    family = "hard_cut"
    confidence = 0.62
    if black > 0.70:
        family, confidence = "black_dip", min(0.98, 0.70 + black * 0.25)
    elif white > 0.55 or center["luma"] > 225:
        family, confidence = "white_flash", min(0.97, 0.65 + white * 0.3)
    elif rgb_peak > 2.5:
        family, confidence = "rgb_split", min(0.94, 0.62 + rgb_peak / 30)
    elif max(max_dx, max_dy) > 8:
        dominant = max(window_m, key=lambda v: max(abs(v["dx"]), abs(v["dy"]))) if window_m else {"dx": 0, "dy": 0}
        if abs(dominant["dx"]) >= abs(dominant["dy"]):
            family = "whip_right" if dominant["dx"] > 0 else "whip_left"
        else:
            family = "whip_down" if dominant["dy"] > 0 else "whip_up"
        confidence = min(0.96, 0.68 + max(max_dx, max_dy) / 80)
    elif abs(math.log(max(zoom_ratio, 1e-4))) > 0.06:
        family, confidence = "zoom_blur" if blur_loss > 25 else "zoom", min(0.94, 0.70 + abs(math.log(zoom_ratio)))
    elif len(window_f) > 3 and np.mean([m["diff"] for m in window_m]) < motions[max(0, index - 1)]["diff"] * 0.8:
        family, confidence = "crossfade", 0.67
    duration = max(2, min(12, hi - lo + 1))
    movement = [math.hypot(m["dx"], m["dy"]) + abs(math.log(max(m["scale"], 1e-4))) * 100 for m in window_m]
    graph, curve = _graph_name(movement)
    direction = family.split("_", 1)[1] if family.startswith(("whip_", "slide_")) else ""
    data = {
        "frame": index, "time": round(index / fps, 6), "family": family,
        "direction": direction, "durationFrames": duration, "durationSeconds": round(duration / fps, 4),
        "zoomRatio": round(zoom_ratio, 4), "translationPx": {"x": round(max_dx, 2), "y": round(max_dy, 2)},
        "travelPx": round(max(max_dx, max_dy) * 5, 1), "blurStrength": round(min(100, blur_loss / 2 + max(max_dx, max_dy) * 2), 1),
        "rgbSplitPx": round(rgb_peak, 2), "blackRatio": round(black, 3), "whiteRatio": round(white, 3),
        "graph": graph, "curve": curve, "confidence": round(float(confidence), 3),
    }
    data["aeRecipe"] = _effect_recipe(family, data)
    data["candidateScores"] = _candidate_scores(data)
    return data


def _visual_candidate_scores(gray_frames: list[np.ndarray], event: dict[str, Any], fps: float) -> list[dict[str, Any]]:
    try:
        from skimage.metrics import structural_similarity
    except Exception:
        return event.get("candidateScores", [])
    index = int(event["frame"])
    radius = max(2, int(round(fps * 0.10)))
    before = gray_frames[max(0, index - radius)]
    observed = gray_frames[min(len(gray_frames) - 1, index)]
    after = gray_frames[min(len(gray_frames) - 1, index + radius)]
    height, width = observed.shape
    before = cv2.resize(before, (width, height)); after = cv2.resize(after, (width, height))
    candidates: dict[str, np.ndarray] = {
        "hard_cut": after,
        "crossfade": cv2.addWeighted(before, 0.5, after, 0.5, 0),
        "black_dip": np.zeros_like(observed),
        "white_flash": np.full_like(observed, 255),
    }
    half = width // 2
    candidates["slide_left"] = np.concatenate([before[:, half:], after[:, :half]], axis=1)
    candidates["slide_right"] = np.concatenate([after[:, half:], before[:, :half]], axis=1)
    half_y = height // 2
    candidates["slide_up"] = np.concatenate([before[half_y:, :], after[:half_y, :]], axis=0)
    candidates["slide_down"] = np.concatenate([after[half_y:, :], before[:half_y, :]], axis=0)
    zoomed = cv2.resize(after, None, fx=1.18, fy=1.18, interpolation=cv2.INTER_LINEAR)
    y = max(0, (zoomed.shape[0] - height) // 2); x = max(0, (zoomed.shape[1] - width) // 2)
    candidates["zoom_blur"] = cv2.GaussianBlur(zoomed[y:y + height, x:x + width], (0, 0), 3)
    raw = {name: max(0.0, float(structural_similarity(observed, candidate, data_range=255))) for name, candidate in candidates.items() if candidate.shape == observed.shape}
    top = max(raw.values()) if raw else 1.0
    return [{"candidate": name, "score": round(score, 3), "relative": round(score / max(top, 1e-6), 3), "method": "SSIM rendered-candidate"} for name, score in sorted(raw.items(), key=lambda item: item[1], reverse=True)]


def _transition_groups(events: list[dict[str, Any]], fps: float) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    gap = max(3, int(round(fps * 0.24)))
    for event in events:
        if not groups or int(event["frame"]) - int(groups[-1][-1]["frame"]) > gap:
            groups.append([event])
        else:
            groups[-1].append(event)
    return [{
        "startFrame": group[0]["frame"], "endFrame": group[-1]["frame"],
        "startTime": group[0]["time"], "endTime": group[-1]["time"],
        "components": [event["family"] for event in group],
        "primary": max(group, key=lambda event: event["confidence"])["family"],
        "confidence": round(float(np.mean([event["confidence"] for event in group])), 3),
    } for group in groups]


def _audio_analysis(source: Path, fps: float, progress: Progress) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"available": False, "reason": "FFmpeg unavailable"}
    try:
        import librosa
        import soundfile as sf
        with tempfile.TemporaryDirectory(prefix="tonyfx-reference-audio-") as temp:
            wav = Path(temp) / "analysis.wav"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "22050", str(wav)], check=True, creationflags=flags)
            y, sr = sf.read(wav, dtype="float32")
            if y.ndim > 1:
                y = y.mean(axis=1)
            progress(77, "Mapping beats, onsets, and drops")
            onset = librosa.onset.onset_strength(y=y, sr=sr)
            harmonic, percussive = librosa.effects.hpss(y)
            percussive_onset = librosa.onset.onset_strength(y=percussive, sr=sr)
            tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr)
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset, sr=sr, backtrack=False)
            rms = librosa.feature.rms(y=y)[0]
            beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()
            drops = []
            for i in range(1, len(rms)):
                rise = float(rms[i] - np.median(rms[max(0, i - 12):i]))
                if rise > max(0.015, float(np.std(rms) * 1.2)):
                    drops.append((rise, float(librosa.frames_to_time(i, sr=sr))))
            drops = [t for _, t in sorted(drops, reverse=True)[:20]]
            chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sr)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12)
            feature = np.vstack([librosa.util.normalize(chroma, axis=1), librosa.util.normalize(mfcc, axis=1)])
            recurrence = librosa.segment.recurrence_matrix(feature, mode="affinity", sym=True)
            lag = librosa.segment.recurrence_to_lag(recurrence, pad=False)
            novelty = np.mean(np.abs(np.diff(lag, axis=1)), axis=0) if lag.shape[1] > 1 else np.zeros(1)
            novelty_peaks = _peaks(novelty.tolist(), float(np.median(novelty) + np.std(novelty)), max(4, int(sr / 512 * 1.2)), 1.4)
            section_times = [round(float(librosa.frames_to_time(index, sr=sr)), 6) for index in novelty_peaks[:24]]
            beat_strengths = []
            for frame, time_value in zip(beat_frames, beat_times):
                beat_strengths.append({"time": round(float(time_value), 6), "strength": round(float(onset[min(len(onset)-1, int(frame))] / max(float(np.percentile(onset, 95)), 1e-6)), 3)})
            energy_limit = max(float(np.percentile(rms, 95)), 1e-6)
            onset_limit = max(float(np.percentile(onset, 95)), 1e-6)
            energy_curve = []
            for frame_index in range(0, len(rms), 4):
                time_value = float(librosa.frames_to_time(frame_index, sr=sr, hop_length=512))
                rms_value = float(np.clip(rms[frame_index] / energy_limit, 0.0, 1.0))
                onset_value = float(np.clip(onset[min(len(onset) - 1, frame_index)] / onset_limit, 0.0, 1.0))
                energy_curve.append({"time": round(time_value, 4), "energy": round(rms_value * 0.68 + onset_value * 0.32, 4)})
            return {
                "available": True, "engine": "librosa HPSS + recurrence + onset ensemble",
                "tempo": round(float(np.asarray(tempo).reshape(-1)[0]), 2),
                "beats": [round(t, 6) for t in beat_times], "beatStrengths": beat_strengths,
                "onsets": [round(t, 6) for t in onset_times], "drops": sorted(round(t, 6) for t in drops),
                "sections": section_times,
                "energyCurve": energy_curve,
                "percussiveEnergy": round(float(np.mean(percussive_onset)), 4),
                "harmonicRatio": round(float(np.mean(np.abs(harmonic)) / max(np.mean(np.abs(y)), 1e-8)), 4),
            }
    except Exception as error:
        return {"available": False, "reason": f"{type(error).__name__}: {error}"}


def _align_audio(events: list[dict[str, Any]], audio: dict[str, Any]) -> None:
    beats = audio.get("beats") or []
    onsets = audio.get("onsets") or []
    for event in events:
        time_value = event["time"]
        nearest_beat = min(beats, key=lambda value: abs(value - time_value)) if beats else None
        nearest_onset = min(onsets, key=lambda value: abs(value - time_value)) if onsets else None
        event["beatDistanceMs"] = round((time_value - nearest_beat) * 1000, 1) if nearest_beat is not None else None
        event["onsetDistanceMs"] = round((time_value - nearest_onset) * 1000, 1) if nearest_onset is not None else None


def _detect_repeats(gray_frames: list[np.ndarray], fps: float) -> list[dict[str, Any]]:
    hashes = [cv2.resize(frame, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32) for frame in gray_frames]
    repeats: list[dict[str, Any]] = []
    minimum_gap = max(2, int(round(fps * 0.08)))
    for i in range(len(hashes)):
        best = None
        for j in range(max(0, i - int(fps * 2)), i - minimum_gap):
            score = float(np.mean(np.abs(hashes[i] - hashes[j])))
            if best is None or score < best[0]:
                best = (score, j)
        if best and best[0] < 5.5:
            repeats.append({"frame": i, "time": round(i / fps, 6), "matchesFrame": best[1], "distance": round(best[0], 2), "kind": "repeat_or_freeze"})
    compact: list[dict[str, Any]] = []
    for item in repeats:
        if not compact or item["frame"] - compact[-1]["frame"] > 2:
            compact.append(item)
    return compact[:100]


def _gray_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Perceptual-ish distance used to separate a cut from an effect pulse."""
    height = 72
    width = max(72, int(round(a.shape[1] * height / max(a.shape[0], 1))))
    left = cv2.resize(a, (width, height), interpolation=cv2.INTER_AREA)
    right = cv2.resize(b, (width, height), interpolation=cv2.INTER_AREA)
    pixel = float(np.mean(cv2.absdiff(left, right))) / 255.0
    hist_a = cv2.calcHist([left], [0], None, [32], [0, 256]); cv2.normalize(hist_a, hist_a)
    hist_b = cv2.calcHist([right], [0], None, [32], [0, 256]); cv2.normalize(hist_b, hist_b)
    histogram = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA))
    edges_a = cv2.Canny(left, 70, 160); edges_b = cv2.Canny(right, 70, 160)
    edge = float(np.mean(cv2.absdiff(edges_a, edges_b))) / 255.0
    return float(np.clip(pixel * 0.48 + histogram * 0.37 + edge * 0.15, 0.0, 1.0))


def _candidate_boundaries(metrics: list[dict[str, float]], motions: list[dict[str, float]], gray_frames: list[np.ndarray], fps: float, accuracy: str) -> tuple[list[int], list[float]]:
    """Find permissive visual events. Canonicalization later decides which are cuts."""
    scores = [0.0]
    pair_distances = [0.0]
    motion_diffs = [0.0] + [float(item["diff"]) for item in motions]
    for index in range(1, len(gray_frames)):
        distance = _gray_distance(gray_frames[index - 1], gray_frames[index])
        pair_distances.append(distance)
        luma_jump = abs(metrics[index]["luma"] - metrics[index - 1]["luma"]) / 255.0
        sharp_ratio = abs(math.log((metrics[index]["sharp"] + 1.0) / (metrics[index - 1]["sharp"] + 1.0)))
        scores.append(distance * 72.0 + motion_diffs[index] * 0.72 + luma_jump * 24.0 + min(1.5, sharp_ratio) * 6.0)
    # Deep mode intentionally admits subtle same-shot resets/reverses. The
    # canonical pass rejects ordinary movement using temporal continuity.
    floor = 9.0 if accuracy == "deep" else 16.5
    spacing = max(2, int(round(fps * (0.065 if accuracy == "deep" else 0.085))))
    candidates = _peaks(scores, floor, spacing, 2.05 if accuracy == "deep" else 3.2)
    # Preserve strong hard cuts even when a nearby flash owns the composite peak.
    strong_pair = max(0.16 if accuracy == "deep" else 0.20, float(np.median(pair_distances) + 4.0 * np.median(np.abs(np.asarray(pair_distances) - np.median(pair_distances)))))
    for index in range(1, len(pair_distances) - 1):
        if pair_distances[index] >= strong_pair and pair_distances[index] >= pair_distances[index - 1] and pair_distances[index] >= pair_distances[index + 1]:
            if all(abs(index - existing) >= spacing for existing in candidates):
                candidates.append(index)
    return sorted(candidates), scores


def _cluster_indices(indices: list[int], fps: float) -> list[list[int]]:
    if not indices:
        return []
    # One rendered transition commonly creates several peaks over 2-8 frames.
    gap = max(2, int(round(fps * 0.13)))
    maximum_span = max(4, int(round(fps * 0.24)))
    clusters: list[list[int]] = [[indices[0]]]
    for index in indices[1:]:
        if index - clusters[-1][-1] <= gap and index - clusters[-1][0] <= maximum_span:
            clusters[-1].append(index)
        else:
            clusters.append([index])
    return clusters


def _stable_frame_index(start: int, end: int, scores: list[float], metrics: list[dict[str, float]], *, prefer_end: bool) -> int:
    """Choose an unaffected frame near a transition, avoiding flash/dip peak frames."""
    start = max(0, start)
    end = min(len(scores) - 1, end)
    if end <= start:
        return start
    candidates: list[tuple[float, int]] = []
    span = max(1, end - start)
    for index in range(start, end + 1):
        pulse = max(metrics[index]["black"], metrics[index]["white"])
        edge_bias = ((end - index) if prefer_end else (index - start)) / span
        cost = float(scores[index]) + pulse * 42.0 + edge_bias * 2.5
        candidates.append((cost, index))
    return min(candidates, key=lambda item: item[0])[1]


def _identity_metrics(before: np.ndarray, after: np.ndarray) -> dict[str, float]:
    """Estimate whether two stable frames belong to the same camera shot."""
    before_small = cv2.resize(before, (160, 160), interpolation=cv2.INTER_AREA)
    after_small = cv2.resize(after, (160, 160), interpolation=cv2.INTER_AREA)
    histogram_before = cv2.calcHist([before_small], [0], None, [48], [0, 256])
    histogram_after = cv2.calcHist([after_small], [0], None, [48], [0, 256])
    cv2.normalize(histogram_before, histogram_before)
    cv2.normalize(histogram_after, histogram_after)
    histogram_distance = float(cv2.compareHist(histogram_before, histogram_after, cv2.HISTCMP_BHATTACHARYYA))
    orb = cv2.ORB_create(320)
    key_before, descriptors_before = orb.detectAndCompute(before_small, None)
    key_after, descriptors_after = orb.detectAndCompute(after_small, None)
    match_ratio = 0.0
    if descriptors_before is not None and descriptors_after is not None and key_before and key_after:
        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors_before, descriptors_after, k=2)
        good = [first for first, second in pairs if first.distance < 0.76 * second.distance]
        match_ratio = len(good) / max(1, min(len(key_before), len(key_after)))
    return {"histogramDistance": round(histogram_distance, 4), "featureMatchRatio": round(float(match_ratio), 4)}


def _curve_from_progress(samples: list[float]) -> tuple[str, str, dict[str, float]]:
    """Fit graph character from cumulative temporal progress, not raw magnitude."""
    if len(samples) < 4:
        return "linear", "0.33, 0.33, 0.67, 0.67", {"q25": 0.25, "q50": 0.5, "q75": 0.75}
    values = np.asarray(samples, dtype=np.float32)
    delta = np.abs(np.diff(values, prepend=values[0]))
    total = float(delta.sum())
    if total < 1e-6:
        return "linear", "0.33, 0.33, 0.67, 0.67", {"q25": 0.25, "q50": 0.5, "q75": 0.75}
    progress = np.cumsum(delta) / total
    q25 = float(progress[min(len(progress) - 1, max(1, round((len(progress) - 1) * 0.25)))])
    q50 = float(progress[min(len(progress) - 1, max(1, round((len(progress) - 1) * 0.50)))])
    q75 = float(progress[min(len(progress) - 1, max(1, round((len(progress) - 1) * 0.75)))])
    if q25 >= 0.56:
        name, curve = "sharp_start", "0.10, 0.75, 0.25, 1.00"
    elif q75 <= 0.44:
        name, curve = "sharp_end", "0.75, 0.00, 0.95, 0.25"
    elif q25 <= 0.20 and q75 >= 0.80:
        name, curve = "speed_ramp", "0.09, 0.72, 0.94, 0.27"
    else:
        name, curve = "smooth_in_out", "0.33, 0.00, 0.67, 1.00"
    return name, curve, {"q25": round(q25, 3), "q50": round(q50, 3), "q75": round(q75, 3)}


def _canonical_transition(cluster: list[int], scores: list[float], fps: float, metrics: list[dict[str, float]], motions: list[dict[str, float]], rgb: list[float], gray_frames: list[np.ndarray], stable_bounds: tuple[int, int] | None = None) -> dict[str, Any]:
    frame_count = len(gray_frames)
    padding = max(2, int(round(fps * 0.10)))
    cluster_start, cluster_end = max(1, cluster[0]), min(frame_count - 2, cluster[-1])
    stable_left, stable_right = stable_bounds or (max(0, cluster_start - padding * 4), min(frame_count - 1, cluster_end + padding * 4))
    before_index = _stable_frame_index(stable_left, max(stable_left, cluster_start - 2), scores, metrics, prefer_end=True)
    after_index = _stable_frame_index(min(stable_right, cluster_end + 2), stable_right, scores, metrics, prefer_end=False)
    stable_change = _gray_distance(gray_frames[before_index], gray_frames[after_index])
    identity = _identity_metrics(gray_frames[before_index], gray_frames[after_index])

    # Pick the boundary that most strongly separates stable content on either side.
    search_start = max(1, cluster_start - padding)
    search_end = min(frame_count - 2, cluster_end + padding)
    boundary_scores: list[tuple[float, int]] = []
    look = max(1, int(round(fps * 0.065)))
    for frame in range(search_start, search_end + 1):
        left = max(0, frame - look); right = min(frame_count - 1, frame + look)
        separation = _gray_distance(gray_frames[left], gray_frames[right])
        pulse_penalty = max(metrics[frame]["black"], metrics[frame]["white"]) * 0.10
        boundary_scores.append((separation - pulse_penalty + scores[frame] / 500.0, frame))
    _, boundary = max(boundary_scores, key=lambda item: item[0])

    effect_padding = 1
    lo = max(1, cluster_start - effect_padding); hi = min(frame_count - 2, cluster_end + effect_padding)
    window_metrics = metrics[lo:hi + 1]
    window_motion = motions[max(0, lo - 1):min(len(motions), hi)]
    window_rgb = rgb[max(0, lo - 1):min(len(rgb), hi)]
    black = max((item["black"] for item in window_metrics), default=0.0)
    white = max((item["white"] for item in window_metrics), default=0.0)
    rgb_peak = max(window_rgb, default=0.0)
    baseline_sharp = float(np.median([metrics[before_index]["sharp"], metrics[after_index]["sharp"]]))
    minimum_sharp = min((item["sharp"] for item in window_metrics), default=baseline_sharp)
    blur_loss = max(0.0, baseline_sharp - minimum_sharp)
    dominant = max(window_motion, key=lambda item: math.hypot(item["dx"], item["dy"]), default={"dx": 0.0, "dy": 0.0})
    travel_x = max((abs(item["dx"]) for item in window_motion), default=0.0)
    travel_y = max((abs(item["dy"]) for item in window_motion), default=0.0)
    travel = max(travel_x, travel_y)
    valid_scales = [item["scale"] for item in window_motion if 0.82 < item["scale"] < 1.22]
    zoom_ratio = float(np.clip(np.prod(valid_scales), 0.65, 1.55)) if valid_scales else 1.0
    zoom_strength = abs(math.log(max(zoom_ratio, 1e-6)))

    components: list[dict[str, Any]] = []
    if black > 0.58:
        components.append({"family": "black_dip", "strength": round(black, 3)})
    if white > 0.42 or max((item["luma"] for item in window_metrics), default=0.0) > 228:
        components.append({"family": "white_flash", "strength": round(max(white, max(item["luma"] for item in window_metrics) / 255.0), 3)})
    if rgb_peak > 2.4:
        components.append({"family": "rgb_split", "strength": round(rgb_peak, 2)})
    motion_family = ""
    coherent_vectors = []
    dominant_length = max(math.hypot(dominant["dx"], dominant["dy"]), 1e-6)
    for item in window_motion:
        length = math.hypot(item["dx"], item["dy"])
        dot = (item["dx"] * dominant["dx"] + item["dy"] * dominant["dy"]) / max(length * dominant_length, 1e-6)
        if length > 4.0 and float(item.get("residual", 0.0)) < 5.5 and dot > 0.55:
            coherent_vectors.append(item)
    if travel > 6.0 and len(coherent_vectors) >= 2:
        if abs(dominant["dx"]) >= abs(dominant["dy"]):
            motion_family = "whip_right" if dominant["dx"] > 0 else "whip_left"
        else:
            motion_family = "whip_down" if dominant["dy"] > 0 else "whip_up"
        components.append({"family": motion_family, "strength": round(travel, 2)})
    if zoom_strength > 0.045:
        components.append({"family": "zoom_blur" if blur_loss > 20 else "zoom", "strength": round(zoom_strength, 4), "ratio": round(zoom_ratio, 4)})
    if blur_loss > 28 and not motion_family:
        components.append({"family": "directional_smear", "strength": round(blur_loss, 2)})

    pre_motion = _gray_distance(gray_frames[max(0, before_index - padding)], gray_frames[before_index]) if before_index > 0 else 0.0
    post_motion = _gray_distance(gray_frames[after_index], gray_frames[min(frame_count - 1, after_index + padding)]) if after_index < frame_count - 1 else 0.0
    local_baseline = float(np.median([pre_motion, post_motion]))
    content_novelty = max(0.0, stable_change - local_baseline * 0.55)
    pair_jump = _gray_distance(gray_frames[max(0, boundary - 1)], gray_frames[boundary])
    continuity_samples = []
    continuity_radius = max(3, int(round(fps * 0.18)))
    for sample in range(max(1, boundary - continuity_radius), min(frame_count, boundary + continuity_radius + 1)):
        if abs(sample - boundary) > 1:
            continuity_samples.append(_gray_distance(gray_frames[sample - 1], gray_frames[sample]))
    continuity_baseline = float(np.median(continuity_samples)) if continuity_samples else 0.0
    discontinuity_ratio = pair_jump / max(0.008, continuity_baseline)
    same_shot = identity["histogramDistance"] < 0.14 or identity["featureMatchRatio"] > 0.12 or (identity["histogramDistance"] < 0.34 and identity["featureMatchRatio"] > 0.045)
    different_shot = identity["histogramDistance"] > 0.24 and identity["featureMatchRatio"] < 0.085
    is_cut = stable_change >= max(0.16, local_baseline * 1.35 + 0.045) and not same_shot
    if different_shot and stable_change >= 0.12:
        is_cut = True
    # A repeated or reversed source segment may preserve identity while its
    # chronology jumps abruptly. Treat that reset as a real edit boundary.
    if same_shot and pair_jump >= 0.058 and discontinuity_ratio >= 2.15 and black < 0.55 and white < 0.42:
        is_cut = True
    if black > 0.40 and white > 0.50 and stable_change < 0.24:
        is_cut = False
    if stable_change >= 0.13 and black < 0.82 and not same_shot and (motion_family or zoom_strength > 0.055):
        is_cut = True
    if is_cut and not components:
        components.append({"family": "hard_cut", "strength": round(stable_change, 3)})
    if is_cut and len(cluster) > 1 and not motion_family and black < 0.58 and white < 0.42:
        spread = cluster_end - cluster_start + 1
        if spread >= max(3, int(round(fps * 0.10))):
            components.append({"family": "crossfade", "strength": round(stable_change, 3)})
    if not components:
        components.append({"family": "effect_pulse", "strength": round(max(scores[index] for index in cluster), 2)})

    priority = [item["family"] for item in components]
    primary = next((name for name in priority if name.startswith("whip_")), None)
    primary = primary or next((name for name in priority if name in {"zoom_blur", "zoom", "crossfade", "black_dip", "white_flash", "rgb_split", "directional_smear", "hard_cut"}), priority[0])
    strength_samples = []
    for frame in range(lo, hi + 1):
        motion = motions[min(max(0, frame - 1), len(motions) - 1)] if motions else {"dx": 0.0, "dy": 0.0, "scale": 1.0}
        strength_samples.append(math.hypot(motion["dx"], motion["dy"]) + abs(math.log(max(motion["scale"], 1e-6))) * 100 + metrics[frame]["black"] * 20 + metrics[frame]["white"] * 20)
    graph, curve, graph_fit = _curve_from_progress(strength_samples)
    confidence = float(np.clip(0.46 + stable_change * 0.95 + min(0.22, max(scores[index] for index in cluster) / 180.0), 0.35, 0.99))
    if not is_cut:
        confidence = float(np.clip(0.48 + max(black, white) * 0.30 + min(0.18, travel / 80.0), 0.35, 0.92))
    duration = hi - lo + 1
    event = {
        "frame": boundary, "time": round(boundary / fps, 6), "kind": "cut_transition" if is_cut else "effect_only",
        "family": primary, "components": components, "componentFamilies": [item["family"] for item in components],
        "startFrame": lo, "endFrame": hi, "startTime": round(lo / fps, 6), "endTime": round(hi / fps, 6),
        "durationFrames": duration, "durationSeconds": round(duration / fps, 4),
        "stableContentChange": round(stable_change, 4), "localMotionBaseline": round(local_baseline, 4), "contentNovelty": round(content_novelty, 4), "sourcePeaks": cluster,
        "stableFrames": [before_index, after_index], "histogramDistance": identity["histogramDistance"], "featureMatchRatio": identity["featureMatchRatio"],
        "pairJump": round(pair_jump, 4), "continuityBaseline": round(continuity_baseline, 4), "discontinuityRatio": round(discontinuity_ratio, 3),
        "zoomRatio": round(zoom_ratio, 4), "translationPx": {"x": round(travel_x, 2), "y": round(travel_y, 2)},
        "travelPx": round(travel, 2), "blurStrength": round(min(100.0, blur_loss / 2.0 + travel * 1.8), 1),
        "rgbSplitPx": round(rgb_peak, 2), "blackRatio": round(black, 3), "whiteRatio": round(white, 3),
        "graph": graph, "curve": curve, "graphFit": graph_fit, "confidence": round(confidence, 3),
    }
    event["aeRecipe"] = []
    for component in components:
        event["aeRecipe"].extend(_effect_recipe(component["family"], event))
    event["aeRecipe"] = _dedupe_recipe(event["aeRecipe"])
    event["candidateScores"] = _candidate_scores(event)
    return event


def _merge_nearby_events(events: list[dict[str, Any]], fps: float) -> list[dict[str, Any]]:
    """Merge duplicate canonical boundaries produced by adjacent effect peaks."""
    if not events:
        return []
    tolerance = max(1, int(round(fps * 0.067)))
    merged: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: (int(item["frame"]), int(item["startFrame"]))):
        if not merged or int(event["frame"]) - int(merged[-1]["frame"]) > tolerance:
            merged.append(event)
            continue
        target = merged[-1]
        winner = event if (event["kind"] == "cut_transition", event["confidence"]) > (target["kind"] == "cut_transition", target["confidence"]) else target
        loser = target if winner is event else event
        winner["kind"] = "cut_transition" if "cut_transition" in {target["kind"], event["kind"]} else "effect_only"
        winner["startFrame"] = min(int(target["startFrame"]), int(event["startFrame"]))
        winner["endFrame"] = max(int(target["endFrame"]), int(event["endFrame"]))
        winner["durationFrames"] = winner["endFrame"] - winner["startFrame"] + 1
        winner["durationSeconds"] = round(winner["durationFrames"] / fps, 4)
        winner["sourcePeaks"] = sorted(set(target.get("sourcePeaks", []) + event.get("sourcePeaks", [])))
        components = target.get("components", []) + event.get("components", [])
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for component in components:
            family = str(component.get("family", "effect_pulse"))
            if family not in seen:
                seen.add(family); unique.append(component)
        winner["components"] = unique
        winner["componentFamilies"] = [item["family"] for item in unique]
        winner["aeRecipe"] = _dedupe_recipe(target.get("aeRecipe", []) + event.get("aeRecipe", []))
        winner["mergedCanonicalEvents"] = int(target.get("mergedCanonicalEvents", 1)) + int(loser.get("mergedCanonicalEvents", 1))
        merged[-1] = winner
    return merged


def _build_shots(events: list[dict[str, Any]], fps: float, gray_frames: list[np.ndarray], motions: list[dict[str, float]]) -> list[dict[str, Any]]:
    cut_frames = sorted({int(event["frame"]) for event in events if event.get("kind") == "cut_transition" and 0 < int(event["frame"]) < len(gray_frames)})
    boundaries = [0] + cut_frames + [len(gray_frames)]
    shots: list[dict[str, Any]] = []
    for index in range(len(boundaries) - 1):
        start, end = boundaries[index], boundaries[index + 1]
        if end <= start:
            continue
        shot_motion = motions[start:max(start, end - 1)]
        cumulative_scale = [0.0]
        cumulative_x = [0.0]
        cumulative_y = [0.0]
        for item in shot_motion:
            cumulative_scale.append(cumulative_scale[-1] + math.log(max(item["scale"], 1e-6)))
            cumulative_x.append(cumulative_x[-1] + item["dx"])
            cumulative_y.append(cumulative_y[-1] + item["dy"])
        graph, curve, fit = _curve_from_progress(cumulative_scale if max(cumulative_scale, default=0) - min(cumulative_scale, default=0) > 0.025 else [math.hypot(x, y) for x, y in zip(cumulative_x, cumulative_y)])
        scale_delta = math.exp(cumulative_scale[-1]) if cumulative_scale else 1.0
        if scale_delta > 1.035:
            zoom_direction = "in"
        elif scale_delta < 0.966:
            zoom_direction = "out"
        else:
            zoom_direction = "none"
        shots.append({
            "index": index + 1, "startFrame": start, "endFrame": end - 1,
            "startTime": round(start / fps, 6), "endTime": round(end / fps, 6),
            "durationFrames": end - start, "durationSeconds": round((end - start) / fps, 4),
            "zoomDirection": zoom_direction, "zoomRatio": round(scale_delta, 4),
            "translationPx": {"x": round(cumulative_x[-1] if cumulative_x else 0.0, 2), "y": round(cumulative_y[-1] if cumulative_y else 0.0, 2)},
            "graph": graph, "curve": curve, "graphFit": fit,
        })
    return shots


def _resampled_shot(gray_frames: list[np.ndarray], shot: dict[str, Any], count: int = 10) -> list[np.ndarray]:
    start, end = int(shot["startFrame"]), int(shot["endFrame"])
    indices = np.linspace(start, max(start, end), count).astype(int)
    return [cv2.resize(gray_frames[min(len(gray_frames) - 1, index)], (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) for index in indices]


def _detect_shot_repeats(gray_frames: list[np.ndarray], shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sequences = [_resampled_shot(gray_frames, shot) for shot in shots]
    matches: list[dict[str, Any]] = []
    for current in range(1, len(shots)):
        best: tuple[float, int, str] | None = None
        for previous in range(current):
            forward = float(np.mean([np.mean(np.abs(a - b)) for a, b in zip(sequences[current], sequences[previous])]))
            reverse = float(np.mean([np.mean(np.abs(a - b)) for a, b in zip(sequences[current], reversed(sequences[previous]))]))
            candidate = (min(forward, reverse), previous, "reverse" if reverse + 0.35 < forward else "repeat")
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best and best[0] < 18.0:
            confidence = float(np.clip(1.0 - best[0] / 22.0, 0.35, 0.99))
            matches.append({"shot": current + 1, "matchesShot": best[1] + 1, "kind": best[2], "distance": round(best[0], 2), "confidence": round(confidence, 3), "time": shots[current]["startTime"]})
    return matches


def _suggest_edit_start(events: list[dict[str, Any]], shots: list[dict[str, Any]], audio: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    cuts = [event for event in events if event.get("kind") == "cut_transition"]
    if not cuts:
        return 0.0, []
    onsets = audio.get("onsets") or []
    drops = audio.get("drops") or []
    scored: list[dict[str, Any]] = []
    for event in cuts:
        time_value = float(event["time"])
        future = sum(1 for item in cuts if time_value <= float(item["time"]) <= time_value + 3.0)
        past = sum(1 for item in cuts if max(0.0, time_value - 3.0) <= float(item["time"]) < time_value)
        onset_bonus = max(0.0, 1.0 - min((abs(time_value - value) for value in onsets), default=1.0) / 0.18)
        drop_bonus = max(0.0, 1.0 - min((abs(time_value - value) for value in drops), default=1.0) / 0.28)
        density_gain = max(0, future - past)
        score = future * 0.8 + density_gain * 0.55 + onset_bonus * 1.2 + drop_bonus * 1.6
        scored.append({"time": round(time_value, 6), "score": round(score, 3), "futureCuts": future, "pastCuts": past, "onsetMatch": round(onset_bonus, 3), "dropMatch": round(drop_bonus, 3)})
    # A long opening shot followed by sustained cutting is stronger evidence than
    # an isolated audio peak. This prevents a late drop from winning merely
    # because it happens to align with several rapid cuts.
    structural: list[dict[str, Any]] = []
    previous_time = 0.0
    for item in sorted(scored, key=lambda value: value["time"]):
        lead_duration = float(item["time"]) - previous_time
        future_four = sum(1 for cut in cuts if float(item["time"]) <= float(cut["time"]) <= float(item["time"]) + 4.0)
        item["leadShotSeconds"] = round(lead_duration, 3)
        item["futureCuts4s"] = future_four
        if lead_duration >= 1.15 and future_four >= 3:
            structural.append(item)
        previous_time = float(item["time"])
    eligible = structural or [item for item in scored if item["futureCuts"] >= 3]
    if structural:
        chosen = min(structural, key=lambda item: item["time"])
    else:
        peak = max((item["score"] for item in eligible), default=0.0)
        near_peak = [item for item in eligible if item["score"] >= peak * 0.82]
        chosen = min(near_peak or eligible or scored, key=lambda item: item["time"])
    return float(chosen["time"]), sorted(scored, key=lambda item: item["score"], reverse=True)[:8]


def _strict_transition_recipe(event: dict[str, Any]) -> dict[str, Any]:
    forensic = event.get("forensics") or {}
    measured = forensic.get("measuredFamilies") or event.get("componentFamilies") or [event.get("family", "hard_cut")]
    return {
        "families": measured,
        "primary": measured[0] if measured else event.get("family", "hard_cut"),
        "durationFrames": event.get("durationFrames", 2),
        "curve": event.get("curve", "0.09,0.72,0.94,0.27"),
        "aeRecipe": forensic.get("aeRecipe") or event.get("aeRecipe", []),
        "confidence": max(float(event.get("confidence", 0)), float(forensic.get("confidence", 0))),
    }


def _build_edit_blueprint(events: list[dict[str, Any]], shots: list[dict[str, Any]], repeats: list[dict[str, Any]], edit_start: float, fps: float) -> dict[str, Any]:
    transitions = []
    for event in events:
        forensic = event.get("forensics") or {}
        measured = forensic.get("measuredFamilies") or event.get("componentFamilies") or [event.get("family", "hard_cut")]
        transitions.append({
            "frame": event["frame"], "time": event["time"], "kind": event["kind"], "span": [event["startFrame"], event["endFrame"]],
            "primary": event["family"], "components": event["componentFamilies"], "durationFrames": event["durationFrames"],
            "graph": event["graph"], "curve": event["curve"], "confidence": event["confidence"], "aeRecipe": event["aeRecipe"],
            "advancedCurve": event.get("advancedCurve", {}), "forensics": forensic,
            "measuredFamilies": measured, "candidateScores": event.get("candidateScores", []),
            "renderedCandidates": event.get("renderedCandidates", {}),
            "strictRecipe": event.get("strictRecipe") or _strict_transition_recipe(event),
        })
    return {
        "version": 4, "fps": round(fps, 6), "editStart": round(edit_start, 6),
        "cutFrames": [event["frame"] for event in events if event["kind"] == "cut_transition"],
        "cutTimes": [event["time"] for event in events if event["kind"] == "cut_transition"],
        "shots": shots, "transitions": transitions, "repeatInstructions": repeats,
        "builderRule": "Build one continuous camera-angle scene per shot. Use strictRecipe at the canonical boundary, never turn component peaks into extra cuts, and never replace an unrecognized effect silently.",
    }


def _contact_sheet(source: Path, output: Path, events: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the reference video. TonyFX should normalize this file before analysis.")
    tiles = []
    for event in events[:24]:
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(event["frame"])))
        ok, frame = capture.read()
        if not ok:
            continue
        frame = _resize(frame, 260)
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 35), (10, 10, 10), -1)
        stack = "+".join(event.get("componentFamilies") or [event["family"]])
        label = f'{event["time"]:.2f}s  {stack[:28]}  {event["confidence"]:.0%}'
        cv2.putText(frame, label, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (245, 220, 140), 1, cv2.LINE_AA)
        tiles.append(frame)
    capture.release()
    if not tiles:
        return
    width = max(tile.shape[1] for tile in tiles)
    height = max(tile.shape[0] for tile in tiles)
    cols, rows = 3, int(math.ceil(len(tiles) / 3))
    sheet = np.full((rows * height, cols * width, 3), 12, np.uint8)
    for index, tile in enumerate(tiles):
        y, x = divmod(index, cols)
        sheet[y * height:y * height + tile.shape[0], x * width:x * width + tile.shape[1]] = tile
    cv2.imwrite(str(output), sheet)


def _write_html(report: dict[str, Any], output: Path) -> None:
    events = report.get("events", [])
    rows = []
    for event in events:
        recipe = ", ".join(item.get("effect") or item.get("property") or item.get("transition") or item.get("layer", "") for item in event.get("aeRecipe", []))
        components = " + ".join(event.get("componentFamilies") or [event.get("family", "cut")])
        forensic = event.get("forensics") or {}
        transform = forensic.get("transform") or {}
        measured = " + ".join(forensic.get("measuredFamilies") or [])
        parameters = f"{measured}; travel {float(transform.get('travelPx',0)):.1f}px; scale {float(transform.get('scaleRatio',1)):.3f}x; rotation {float(transform.get('rotation',0)):.1f}deg" if forensic.get("available") else "fallback analysis"
        rows.append(f"<tr><td>{event['time']:.3f}s</td><td>{html.escape(event.get('kind','cut_transition'))}</td><td>{html.escape(components)}</td><td>{event['durationFrames']}f</td><td>{html.escape(event['graph'])}</td><td>{event['confidence']:.0%}</td><td>{html.escape(parameters)}</td><td>{html.escape(recipe)}</td></tr>")
    meta = report["media"]
    summary = report.get("summary", {})
    shots = report.get("shots", [])
    repeats = report.get("repeats", [])
    warning = "Measurements and recipes are evidence-based inferences from flattened video, not recovered project metadata."
    vision_rows = []
    for shot in shots:
        subject = shot.get("visionSubject") or shot.get("framing") or {}
        matches = shot.get("footageMatches") or []
        best = matches[0] if matches else {}
        vision_rows.append(f"<tr><td>{shot.get('index','')}</td><td>{html.escape(str(subject.get('safeFrameStatus','review')))}</td><td>{html.escape(str(best.get('layerName','No indexed match')))}</td><td>{float(best.get('confidence',0)):.0%}</td><td>{html.escape(str((shot.get('trackingEvidence') or {}).get('medianTravelPx','n/a')))}</td></tr>")
    vision_table = ""
    if report.get("visionEngine"):
        engine = report.get("visionEngine") or {}
        indexed = int((report.get("footageIndex") or {}).get("count") or 0)
        vision_table = f"<h2>Local vision and AE footage search</h2><p>GPU: <strong>{html.escape(str(engine.get('gpu','unknown')))}</strong>. Indexed footage samples: <strong>{indexed}</strong>.</p><table><thead><tr><th>Shot</th><th>Safe frame</th><th>Best AE footage match</th><th>Confidence</th><th>Tracked travel</th></tr></thead><tbody>{''.join(vision_rows)}</tbody></table>"
    contact_path = Path(report.get("contactSheet", "")) if report.get("contactSheet") else None
    contact_html = f"<img src='{html.escape(contact_path.name)}' alt='Transition evidence contact sheet'>" if contact_path and contact_path.exists() and contact_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ""
    document = f"""<!doctype html><html><head><meta charset='utf-8'><title>TonyFX Reference Analysis</title><style>
body{{background:#0b0d10;color:#e8e2d4;font:14px Segoe UI,Arial;margin:28px}}h1,h2{{color:#e0b55b}}.note{{border:1px solid #6d5425;padding:12px;background:#17140d}}.summary{{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:10px}}.summary div{{border:1px solid #30343a;background:#11151a;padding:12px}}.summary b{{display:block;color:#e0b55b;font-size:20px}}table{{border-collapse:collapse;width:100%;margin-top:14px}}th,td{{border:1px solid #30343a;padding:9px;text-align:left}}th{{color:#e0b55b;background:#14171c}}code{{color:#a8d8ff}}img{{max-width:100%;margin-top:20px;border:1px solid #333}}</style></head><body>
<h1>TonyFX Reference Forensics</h1><p>{html.escape(meta['name'])} | {meta['width']}x{meta['height']} | {meta['fps']:.3f} fps | {meta['duration']:.2f}s</p><p class='note'>{warning}</p>
<div class='summary'><div><b>{summary.get('cutCount',len(events))}</b>canonical cuts</div><div><b>{summary.get('effectOnlyCount',0)}</b>effect-only events</div><div><b>{len(shots)}</b>continuous shots</div><div><b>{len(repeats)}</b>repeat/reverse matches</div><div><b>{summary.get('collapsedPeakCount',0)}</b>duplicate peaks collapsed</div></div>
<p>Suggested main-edit start: <strong>{summary.get('suggestedEditStart',0):.3f}s</strong>. Audio tempo: <strong>{report.get('audio',{}).get('tempo','n/a')}</strong> BPM.</p>
<h2>Canonical transition blueprint</h2><table><thead><tr><th>Time</th><th>Boundary type</th><th>Effect stack</th><th>Span</th><th>Graph</th><th>Confidence</th><th>Measured parameters</th><th>Likely AE recipe</th></tr></thead><tbody>{''.join(rows)}</tbody></table>{vision_table}
{contact_html}</body></html>"""
    output.write_text(document, encoding="utf-8")


def analyze_reference(source: Path, output_dir: Path, *, width: int = 420, accuracy: str = "balanced", analyze_audio: bool = True, ocr: bool = False, deep_flow: bool = False, effect_inventory: list[dict[str, Any]] | list[str] | None = None, feedback_path: Path | None = None, face_model_path: Path | None = None, progress: Progress | None = None) -> dict[str, Any]:
    progress = progress or (lambda _percent, _message: None)
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = probe_media(source)
    fps = meta["fps"] or 30.0
    progress(3, "Reading reference metadata")
    capture = cv2.VideoCapture(str(source))
    metrics: list[dict[str, float]] = []
    motions: list[dict[str, float]] = []
    rgb: list[float] = []
    gray_frames: list[np.ndarray] = []
    forensic_frames: list[np.ndarray] = []
    previous = None
    total = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or meta["frames"] or 1))
    frame_index = 0
    while True:
        ok, raw = capture.read()
        if not ok:
            break
        frame = _resize(raw, max(240, int(width)))
        metrics.append(_frame_metrics(frame))
        gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        forensic_frames.append(frame.copy())
        if previous is not None:
            motions.append(_motion(previous, frame))
            rgb.append(_rgb_split(frame))
        previous = frame
        frame_index += 1
        if frame_index % max(15, int(fps)) == 0:
            progress(5 + 48 * frame_index / total, f"Measuring frame {frame_index}/{total}")
    capture.release()
    if len(metrics) < 3:
        raise RuntimeError("Reference has too few readable frames.")
    candidate_frames, boundary_scores = _candidate_boundaries(metrics, motions, gray_frames, fps, accuracy)
    progress(54, "Checking neural shot boundaries")
    transnet = transnet_boundaries(forensic_frames, threshold=0.48 if accuracy == "deep" else 0.55)
    for frame in transnet.get("frames", []):
        frame = int(frame)
        if 0 < frame < len(gray_frames) - 1:
            if all(abs(frame - existing) > 1 for existing in candidate_frames):
                candidate_frames.append(frame)
            boundary_scores[frame] = max(float(boundary_scores[frame]), 34.0 + 42.0 * float(transnet.get("scores", {}).get(str(frame), 0.5)))
    candidate_frames.sort()
    clusters = _cluster_indices(candidate_frames, fps)
    progress(57, "Separating scene cuts from transition components")
    events = []
    for cluster_index, cluster in enumerate(clusters):
        left = 0 if cluster_index == 0 else (clusters[cluster_index - 1][-1] + cluster[0]) // 2 + 1
        right = len(gray_frames) - 1 if cluster_index == len(clusters) - 1 else (cluster[-1] + clusters[cluster_index + 1][0]) // 2 - 1
        events.append(_canonical_transition(cluster, boundary_scores, fps, metrics, motions, rgb, gray_frames, (left, right)))
    events = _merge_nearby_events(events, fps)
    # Remove low-information pulses while preserving deliberate black/white/audio-aligned effects.
    events = [event for event in events if event["kind"] == "cut_transition" or event["confidence"] >= 0.58 or event["family"] in {"black_dip", "white_flash", "rgb_split"}]
    for event in events:
        event["visualCandidateScores"] = _visual_candidate_scores(gray_frames, event, fps)
        event["renderedCandidates"] = render_and_score_candidates(gray_frames, event, fps)
        event["effectFingerprint"] = match_effect_fingerprint(event)
        winner = event["renderedCandidates"].get("winner", "")
        if winner and float(event["renderedCandidates"].get("confidence", 0)) >= 0.63:
            event["renderedCandidateFamily"] = winner
            event["renderedCandidateAgreement"] = winner == event.get("family") or winner.replace("slide_", "whip_") == event.get("family")
        start = max(0, int(event.get("startFrame", event["frame"])) - 1)
        end = min(len(motions), int(event.get("endFrame", event["frame"])) + 1)
        strengths = [math.hypot(item["dx"], item["dy"]) + abs(math.log(max(item["scale"], 1e-6))) * 100 for item in motions[start:end]]
        event["advancedCurve"] = fit_temporal_curve(strengths)
        if event["advancedCurve"]["confidence"] >= 0.62:
            event["graph"] = event["advancedCurve"]["name"]
            event["curve"] = event["advancedCurve"]["curve"]
            event["curveSource"] = "fitted multi-frame motion progress"
    if deep_flow and events:
        progress(67, "Measuring dense transition flow")
        for event in events:
            frame = int(event["frame"])
            if 0 < frame < len(gray_frames):
                event["denseFlow"] = _dense_flow(gray_frames[frame - 1], gray_frames[frame])
                dense = event["denseFlow"]
                if event["family"].startswith("whip_") and dense["p90Magnitude"] > 4 and max(abs(dense["medianX"]), abs(dense["medianY"])) > 1:
                    if abs(dense["medianX"]) >= abs(dense["medianY"]):
                        event["family"] = "whip_right" if dense["medianX"] > 0 else "whip_left"
                    else:
                        event["family"] = "whip_down" if dense["medianY"] > 0 else "whip_up"
                    event["direction"] = event["family"].split("_", 1)[1]
                    for component in event.get("components", []):
                        if str(component.get("family", "")).startswith("whip_"):
                            component["family"] = event["family"]
                            break
                    event["componentFamilies"] = [component["family"] for component in event.get("components", [])]
                    event["aeRecipe"] = []
                    for component in event.get("components", []):
                        event["aeRecipe"].extend(_effect_recipe(component["family"], event))
                    event["aeRecipe"] = _dedupe_recipe(event["aeRecipe"])
                elif event["family"].startswith("whip_") and dense["p90Magnitude"] < 2.0:
                    # A hard cut between unrelated images can produce a false affine translation.
                    filtered = [component for component in event.get("components", []) if not str(component.get("family", "")).startswith("whip_")]
                    event["components"] = filtered or [{"family": "hard_cut", "strength": event.get("stableContentChange", 0.0)}]
                    event["componentFamilies"] = [component["family"] for component in event["components"]]
                    event["family"] = next((component["family"] for component in event["components"] if component["family"] in {"zoom_blur", "zoom", "crossfade", "black_dip", "white_flash", "rgb_split", "directional_smear", "hard_cut"}), event["componentFamilies"][0])
                    event["aeRecipe"] = []
                    for component in event["components"]:
                        event["aeRecipe"].extend(_effect_recipe(component["family"], event))
                    event["aeRecipe"] = _dedupe_recipe(event["aeRecipe"])
    progress(74, "Decomposing perspective, masks, depth, blur, and compound motion")
    forensic_summary = enrich_transition_forensics(
        forensic_frames, events, fps, metrics,
        accuracy=accuracy, deep_flow=deep_flow,
        dna_path=(feedback_path.parent / "transition-dna.json") if feedback_path else None,
    )
    for event in events:
        event["strictRecipe"] = _strict_transition_recipe(event)
    audio = _audio_analysis(source, fps, progress) if analyze_audio and meta["hasAudio"] else {"available": False, "reason": "No audio stream or audio analysis disabled"}
    _align_audio(events, audio)
    shots = _build_shots(events, fps, gray_frames, motions)
    for shot in shots:
        start = max(0, int(shot["startFrame"])); end = min(len(motions), int(shot["endFrame"]))
        cumulative = [0.0]
        for item in motions[start:end]:
            cumulative.append(cumulative[-1] + math.log(max(item["scale"], 1e-6)) + math.hypot(item["dx"], item["dy"]) / 100.0)
        shot["advancedCurve"] = fit_temporal_curve(cumulative)
        shot["graph"] = shot["advancedCurve"]["name"]
        shot["curve"] = shot["advancedCurve"]["curve"]
    progress(81, "Checking subject framing and searchable shot roles")
    framing = subject_framing(gray_frames, shots, face_model_path)
    semantic = semantic_shot_requirements(gray_frames, shots)
    narrative = narrative_flow_map(shots, events, audio, meta["duration"], fps)
    shot_repeats = _detect_shot_repeats(gray_frames, shots)
    frame_repeats = _detect_repeats(gray_frames, fps)
    repeats = shot_repeats
    text_hits: list[dict[str, Any]] = []
    if ocr:
        progress(84, "Checking sampled frames for burned-in text")
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            sample_step = max(1, int(round(fps)))
            for index in range(0, len(gray_frames), sample_step):
                result, _ = engine(gray_frames[index])
                if result:
                    text_hits.append({"frame": index, "time": round(index / fps, 4), "text": " | ".join(str(item[1]) for item in result[:5])})
        except Exception as error:
            text_hits.append({"error": f"OCR unavailable: {error}"})
    audio_structure = advanced_audio_structure(audio, meta["duration"])
    inventory_result = apply_effect_inventory(events, effect_inventory or [])
    feedback = load_feedback(feedback_path)
    feedback_result = apply_feedback(events, feedback)
    progress(90, "Writing candidate evidence and repair manifest")
    contact = output_dir / "transition-evidence.jpg"
    contact_error = ""
    try:
        _contact_sheet(source, contact, events, meta)
    except Exception as error:
        contact_error = str(error)
        (output_dir / "transition-evidence-unavailable.txt").write_text(f"Contact sheet generation failed without invalidating the analysis: {error}", encoding="utf-8")
    family_counts: dict[str, int] = {}
    for event in events:
        family_counts[event["family"]] = family_counts.get(event["family"], 0) + 1
    edit_start, edit_start_candidates = _suggest_edit_start(events, shots, audio)
    groups = _transition_groups(events, fps)
    blueprint = _build_edit_blueprint(events, shots, repeats, edit_start, fps)
    blueprint["shotRequirements"] = semantic
    blueprint["framingQA"] = framing
    blueprint["audioStructure"] = audio_structure
    blueprint["narrativeMap"] = narrative
    blueprint["effectInventory"] = inventory_result
    blueprint["instruction"] = "Choose footage by shotRequirements, then reproduce each fitted curve and transition span. Render once and run TonyFX Compare before approving the edit."
    cut_events = [event for event in events if event["kind"] == "cut_transition"]
    effect_events = [event for event in events if event["kind"] == "effect_only"]
    report: dict[str, Any] = {
        "schema": "tonyfx.reference-analysis.v6", "analyzerVersion": "0.60.0",
        "media": meta, "settings": {"width": width, "accuracy": accuracy, "audio": analyze_audio, "ocr": ocr, "deepFlow": deep_flow, "candidateRenderer": True, "subjectQA": True, "semanticShots": True, "transitionForensics": True},
        "summary": {
            "eventCount": len(events), "cutCount": len(cut_events), "effectOnlyCount": len(effect_events), "shotCount": len(shots), "decodedFrameCount": len(gray_frames),
            "transitionGroupCount": len(groups), "families": family_counts, "repeatCount": len(repeats),
            "suggestedEditStart": round(edit_start, 4), "candidatePeakCount": len(candidate_frames), "collapsedPeakCount": max(0, len(candidate_frames) - len(events)),
            "firstHighlightShot": narrative.get("firstHighlightShot"), "climaxShot": narrative.get("climaxShot"),
            "warning": "AE recipes are evidence-based measurements from rendered pixels, not recovered project metadata. V6 preserves strict per-boundary recipes, maps editorial energy and climax obligations, and requires vision-matched source moments instead of merely choosing a matching layer."
        },
        "events": events, "cutEvents": cut_events, "effectEvents": effect_events, "shots": shots,
        "transitionGroups": groups, "repeats": repeats, "frameRepeats": frame_repeats,
        "editStartCandidates": edit_start_candidates, "editBlueprint": blueprint,
        "audio": audio, "audioStructure": audio_structure, "burnedInText": text_hits,
        "framingQA": framing, "semanticShotRequirements": semantic,
        "narrativeMap": narrative,
        "effectInventory": inventory_result, "feedback": feedback_result,
        "transitionForensics": forensic_summary, "transNetV2": transnet,
        "contactSheet": str(contact) if contact.exists() else "",
        "contactSheetError": contact_error,
    }
    report["replicaBuilderContract"] = compile_builder_contract(report)
    report["editBlueprint"]["replicaBuilderContract"] = report["replicaBuilderContract"]
    report["editBlueprint"]["version"] = 6
    report["editBlueprint"]["builderRule"] = "Consume replicaBuilderContract frame-for-frame, use each vision-ranked source moment rather than the layer in-point, keep high-motion footage in first-highlight and climax slots, never turn component peaks into extra cuts, and refuse unresolved blocking ambiguity. Exact mode may not invent a curve, effect, zoom, repeat direction, source-speed change, speaker, or dialogue-to-shot relationship."
    report["repairPlan"] = build_repair_plan(report)
    manifest = output_dir / "reference-analysis.json"
    html_report = output_dir / "reference-analysis.html"
    report["manifest"] = str(manifest)
    report["htmlReport"] = str(html_report)
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_html(report, html_report)
    progress(100, "Reference analysis complete")
    return report
