"""Advanced offline intelligence for TonyFX reference replication.

This module deliberately works from rendered pixels and audio. It improves the
quality of inferences without claiming access to an original AE project.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


CURVE_PRESETS = {
    "sharp_start": (0.10, 0.75, 0.25, 1.00),
    "sharp_end": (0.75, 0.00, 0.95, 0.25),
    "speed_ramp": (0.09, 0.72, 0.94, 0.27),
    "smooth_in_out": (0.33, 0.00, 0.67, 1.00),
    "linear": (0.33, 0.33, 0.67, 0.67),
}


def _bezier(value: np.ndarray, a: float, b: float) -> np.ndarray:
    inverse = 1.0 - value
    return 3.0 * inverse * inverse * value * a + 3.0 * inverse * value * value * b + value ** 3


def _bezier_y_at_x(x: np.ndarray, curve: tuple[float, float, float, float]) -> np.ndarray:
    x1, y1, x2, y2 = curve
    t = x.copy()
    for _ in range(10):
        estimated = _bezier(t, x1, x2)
        derivative = 3 * (1 - t) ** 2 * x1 + 6 * (1 - t) * t * (x2 - x1) + 3 * t ** 2 * (1 - x2)
        t = np.clip(t - (estimated - x) / np.maximum(np.abs(derivative), 1e-5), 0.0, 1.0)
    return _bezier(t, y1, y2)


def fit_temporal_curve(samples: list[float]) -> dict[str, Any]:
    """Fit a usable cubic Bezier and rank it against TonyFX graph presets."""
    values = np.asarray(samples, dtype=np.float64)
    if len(values) < 4 or float(np.ptp(values)) < 1e-6:
        curve = CURVE_PRESETS["linear"]
        return {"name": "linear", "curve": _curve_text(curve), "controls": list(curve), "fitError": 0.0, "confidence": 0.45}
    direction = 1.0 if values[-1] >= values[0] else -1.0
    progress = (values - values[0]) * direction
    progress = np.maximum.accumulate(progress)
    progress /= max(float(progress[-1]), float(progress.max()), 1e-8)
    x = np.linspace(0.0, 1.0, len(progress))
    ranked = []
    for name, curve in CURVE_PRESETS.items():
        predicted = _bezier_y_at_x(x, curve)
        error = float(np.mean((predicted - progress) ** 2))
        ranked.append((error, name, curve))
    error, name, curve = min(ranked)
    # Refine around the winning preset. A small deterministic grid is more
    # dependable than making scipy a hard runtime requirement.
    best = (error, curve)
    for dx1 in (-0.08, -0.04, 0.0, 0.04, 0.08):
        for dy1 in (-0.12, -0.06, 0.0, 0.06, 0.12):
            for dx2 in (-0.08, -0.04, 0.0, 0.04, 0.08):
                for dy2 in (-0.12, -0.06, 0.0, 0.06, 0.12):
                    candidate = (
                        float(np.clip(curve[0] + dx1, 0.01, 0.99)),
                        float(np.clip(curve[1] + dy1, -0.25, 1.25)),
                        float(np.clip(curve[2] + dx2, 0.01, 0.99)),
                        float(np.clip(curve[3] + dy2, -0.25, 1.25)),
                    )
                    candidate_error = float(np.mean((_bezier_y_at_x(x, candidate) - progress) ** 2))
                    if candidate_error < best[0]:
                        best = (candidate_error, candidate)
    return {
        "name": name, "curve": _curve_text(best[1]), "controls": [round(value, 4) for value in best[1]],
        "fitError": round(best[0], 6), "confidence": round(float(np.clip(1.0 - best[0] * 8.0, 0.35, 0.99)), 3),
        "direction": "increasing" if direction > 0 else "decreasing",
        "presetRanking": [{"name": item[1], "error": round(item[0], 6)} for item in sorted(ranked)[:5]],
    }


def _curve_text(curve: tuple[float, float, float, float]) -> str:
    return ", ".join(f"{value:.2f}" for value in curve)


def _center_crop(image: np.ndarray, width: int, height: int) -> np.ndarray:
    y = max(0, (image.shape[0] - height) // 2)
    x = max(0, (image.shape[1] - width) // 2)
    return image[y:y + height, x:x + width]


def _translate(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    return cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def _zoom(image: np.ndarray, ratio: float) -> np.ndarray:
    height, width = image.shape[:2]
    resized = cv2.resize(image, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_LINEAR)
    if ratio >= 1.0:
        return _center_crop(resized, width, height)
    canvas = cv2.copyMakeBorder(resized, 0, max(0, height - resized.shape[0]), 0, max(0, width - resized.shape[1]), cv2.BORDER_REFLECT_101)
    return cv2.resize(canvas[:height, :width], (width, height))


def _score_frame(observed: np.ndarray, candidate: np.ndarray) -> float:
    left = cv2.resize(observed, (192, 108), interpolation=cv2.INTER_AREA)
    right = cv2.resize(candidate, (192, 108), interpolation=cv2.INTER_AREA)
    pixel = 1.0 - float(np.mean(cv2.absdiff(left, right))) / 255.0
    edge_left = cv2.Canny(left, 70, 150)
    edge_right = cv2.Canny(right, 70, 150)
    edge = 1.0 - float(np.mean(cv2.absdiff(edge_left, edge_right))) / 255.0
    histogram_left = cv2.calcHist([left], [0], None, [32], [0, 256]); cv2.normalize(histogram_left, histogram_left)
    histogram_right = cv2.calcHist([right], [0], None, [32], [0, 256]); cv2.normalize(histogram_right, histogram_right)
    histogram = 1.0 - float(cv2.compareHist(histogram_left, histogram_right, cv2.HISTCMP_BHATTACHARYYA))
    return float(np.clip(pixel * 0.52 + edge * 0.28 + histogram * 0.20, 0.0, 1.0))


def render_and_score_candidates(gray_frames: list[np.ndarray], event: dict[str, Any], fps: float) -> dict[str, Any]:
    """Render small transition hypotheses and optimize duration/strength."""
    boundary = int(event["frame"])
    if not gray_frames or boundary <= 0 or boundary >= len(gray_frames) - 1:
        return {"winner": "hard_cut", "confidence": 0.0, "candidates": []}
    base_radius = max(2, int(round(fps * 0.10)))
    before = gray_frames[max(0, boundary - base_radius)]
    after = gray_frames[min(len(gray_frames) - 1, boundary + base_radius)]
    observed_indices = list(range(max(0, boundary - base_radius), min(len(gray_frames), boundary + base_radius + 1)))
    families = ["hard_cut", "crossfade", "black_dip", "white_flash", "slide_left", "slide_right", "slide_up", "slide_down", "zoom_in", "zoom_out", "zoom_blur"]
    results = []
    for family in families:
        best = (-1.0, {})
        for duration in sorted({max(2, base_radius), max(3, base_radius * 2), max(4, int(round(fps * 0.16)))}):
            strengths = [0.72, 1.0] if family.startswith("slide") else ([1.12, 1.22, 1.34] if family.startswith("zoom") else [1.0])
            for strength in strengths:
                scores = []
                for index in observed_indices:
                    progress = float(np.clip((index - (boundary - duration / 2)) / max(duration, 1), 0.0, 1.0))
                    if family == "hard_cut":
                        candidate = before if progress < 0.5 else after
                    elif family == "crossfade":
                        candidate = cv2.addWeighted(before, 1.0 - progress, after, progress, 0)
                    elif family == "black_dip":
                        source = before if progress < 0.5 else after
                        candidate = np.uint8(np.clip(source.astype(np.float32) * abs(progress - 0.5) * 2.0, 0, 255))
                    elif family == "white_flash":
                        source = before if progress < 0.5 else after
                        amount = 1.0 - abs(progress - 0.5) * 2.0
                        candidate = cv2.addWeighted(source, 1.0 - amount, np.full_like(source, 255), amount, 0)
                    elif family.startswith("slide"):
                        source_a, source_b = before, after
                        distance = (1.0 - progress) * (before.shape[1] if family.endswith(("left", "right")) else before.shape[0]) * strength
                        if family == "slide_left": candidate = cv2.addWeighted(_translate(source_a, -progress * before.shape[1] * strength, 0), 1 - progress, _translate(source_b, distance, 0), progress, 0)
                        elif family == "slide_right": candidate = cv2.addWeighted(_translate(source_a, progress * before.shape[1] * strength, 0), 1 - progress, _translate(source_b, -distance, 0), progress, 0)
                        elif family == "slide_up": candidate = cv2.addWeighted(_translate(source_a, 0, -progress * before.shape[0] * strength), 1 - progress, _translate(source_b, 0, distance), progress, 0)
                        else: candidate = cv2.addWeighted(_translate(source_a, 0, progress * before.shape[0] * strength), 1 - progress, _translate(source_b, 0, -distance), progress, 0)
                    else:
                        source = before if progress < 0.5 else after
                        local = progress if progress < 0.5 else 1.0 - progress
                        ratio = 1.0 + local * 2.0 * (strength - 1.0)
                        if family == "zoom_out": ratio = max(0.72, 1.0 / ratio)
                        candidate = _zoom(source, ratio)
                        if family == "zoom_blur": candidate = cv2.GaussianBlur(candidate, (0, 0), max(0.5, local * 8.0))
                    scores.append(_score_frame(gray_frames[index], candidate))
                score = float(np.mean(scores)) if scores else 0.0
                if score > best[0]: best = (score, {"durationFrames": duration, "strength": strength})
        results.append({"family": family, "score": round(best[0], 4), **best[1]})
    results.sort(key=lambda item: item["score"], reverse=True)
    margin = results[0]["score"] - results[1]["score"] if len(results) > 1 else results[0]["score"]
    return {"winner": results[0]["family"], "confidence": round(float(np.clip(0.5 + margin * 3.0, 0.5, 0.99)), 3), "margin": round(margin, 4), "candidates": results[:7], "method": "multi-frame rendered hypothesis optimization"}


EFFECT_FINGERPRINTS = {
    "whip": {"translation": 0.92, "zoom": 0.12, "blur": 0.78, "flash": 0.04, "rgb": 0.10},
    "slide": {"translation": 0.82, "zoom": 0.08, "blur": 0.34, "flash": 0.02, "rgb": 0.05},
    "zoom_blur": {"translation": 0.12, "zoom": 0.94, "blur": 0.82, "flash": 0.05, "rgb": 0.08},
    "hard_zoom": {"translation": 0.08, "zoom": 0.96, "blur": 0.24, "flash": 0.03, "rgb": 0.05},
    "white_flash": {"translation": 0.04, "zoom": 0.04, "blur": 0.18, "flash": 0.98, "rgb": 0.12},
    "black_dip": {"translation": 0.03, "zoom": 0.03, "blur": 0.10, "flash": -0.92, "rgb": 0.03},
    "rgb_whip": {"translation": 0.84, "zoom": 0.10, "blur": 0.62, "flash": 0.08, "rgb": 0.96},
    "impact_shake": {"translation": 0.68, "zoom": 0.28, "blur": 0.42, "flash": 0.16, "rgb": 0.10},
    "crossfade": {"translation": 0.05, "zoom": 0.04, "blur": 0.05, "flash": 0.02, "rgb": 0.02},
}


def match_effect_fingerprint(event: dict[str, Any]) -> dict[str, Any]:
    translation = math.hypot(float(event.get("dx") or 0), float(event.get("dy") or 0))
    observed = np.asarray([
        min(1.0, translation / 80.0),
        min(1.0, abs(math.log(max(float(event.get("zoomRatio") or 1.0), 1e-6))) / 0.28),
        min(1.0, float(event.get("blurStrength") or 0) / 80.0),
        float(np.clip((float(event.get("lumaDelta") or 0)) / 180.0, -1.0, 1.0)),
        min(1.0, float(event.get("rgbSplit") or 0) / 15.0),
    ], dtype=np.float32)
    ranked = []
    for name, values in EFFECT_FINGERPRINTS.items():
        target = np.asarray([values[key] for key in ("translation", "zoom", "blur", "flash", "rgb")], dtype=np.float32)
        distance = float(np.sqrt(np.mean((observed - target) ** 2)))
        ranked.append({"name": name, "score": round(float(np.clip(1.0 - distance, 0.0, 1.0)), 3)})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"winner": ranked[0]["name"], "confidence": ranked[0]["score"], "ranking": ranked[:6], "observed": [round(float(value), 4) for value in observed], "libraryVersion": 1}


def _salient_subject_box(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find the dominant foreground region when a frontal face is unavailable."""
    blurred = cv2.GaussianBlur(frame, (0, 0), max(3.0, min(frame.shape[:2]) / 24.0))
    detail = cv2.absdiff(frame, blurred)
    threshold = max(12.0, float(np.percentile(detail, 82)))
    mask = np.uint8(detail >= threshold) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    height, width = frame.shape[:2]
    candidates = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = box_width * box_height
        if area < width * height * 0.012:
            continue
        center_x = (x + box_width / 2) / width
        center_y = (y + box_height / 2) / height
        center_weight = 1.0 - min(0.8, math.hypot(center_x - 0.5, center_y - 0.48))
        candidates.append((area * center_weight, (x, y, box_width, box_height)))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def subject_framing(gray_frames: list[np.ndarray], shots: list[dict[str, Any]], face_model_path: Path | None = None) -> list[dict[str, Any]]:
    detector = None
    cascade_type = getattr(cv2, "CascadeClassifier", None)
    cascade_data = getattr(cv2, "data", None)
    if cascade_type and cascade_data and getattr(cascade_data, "haarcascades", ""):
        cascade_path = Path(cascade_data.haarcascades) / "haarcascade_frontalface_default.xml"
        candidate = cascade_type(str(cascade_path))
        if not candidate.empty(): detector = candidate
    yunet = None
    if face_model_path and face_model_path.exists() and hasattr(cv2, "FaceDetectorYN_create"):
        try:
            yunet = cv2.FaceDetectorYN_create(str(face_model_path), "", (320, 320), 0.74, 0.3, 5000)
        except Exception:
            yunet = None
    results = []
    for shot in shots:
        indices = np.linspace(int(shot["startFrame"]), int(shot["endFrame"]), min(7, max(2, int(shot["durationFrames"])))).astype(int)
        centers, areas, sources = [], [], []
        for index in indices:
            frame = gray_frames[min(len(gray_frames) - 1, max(0, index))]
            faces = []
            if yunet is not None:
                try:
                    yunet.setInputSize((frame.shape[1], frame.shape[0]))
                    _, detections = yunet.detect(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
                    if detections is not None:
                        faces = [tuple(map(int, row[:4])) for row in detections]
                except Exception:
                    faces = []
            elif detector is not None:
                faces = detector.detectMultiScale(frame, scaleFactor=1.12, minNeighbors=4, minSize=(24, 24))
            if len(faces):
                x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
                centers.append(((x + width / 2) / frame.shape[1], (y + height / 2) / frame.shape[0]))
                areas.append((width * height) / (frame.shape[0] * frame.shape[1]))
                sources.append("face")
            else:
                box = _salient_subject_box(frame)
                if box:
                    x, y, width, height = box
                    centers.append(((x + width / 2) / frame.shape[1], (y + height / 2) / frame.shape[0]))
                    areas.append((width * height) / (frame.shape[0] * frame.shape[1]))
                    sources.append("saliency")
        if centers:
            center_x, center_y = np.median(np.asarray(centers), axis=0)
            violations = sum(1 for x, y in centers if not 0.20 <= x <= 0.80 or not 0.14 <= y <= 0.86)
            status = "safe" if violations == 0 else ("review" if violations <= len(centers) // 2 else "unsafe")
            face_detected = sources.count("face") >= max(1, len(sources) // 2)
            result = {"shot": shot["index"], "faceDetected": face_detected, "subjectDetected": True, "detectionSource": "face" if face_detected else "saliency", "center": {"x": round(float(center_x), 3), "y": round(float(center_y), 3)}, "faceArea": round(float(np.median(areas)), 4) if face_detected else 0.0, "subjectArea": round(float(np.median(areas)), 4), "safeFrameStatus": status, "sampleCount": len(centers), "violations": violations, "suggestedPositionOffsetNormalized": {"x": round(0.5 - float(center_x), 3), "y": round(0.46 - float(center_y), 3)}}
        else:
            result = {"shot": shot["index"], "faceDetected": False, "safeFrameStatus": "review", "sampleCount": 0, "violations": 0, "note": "No stable frontal face detected; preserve user framing and visually inspect."}
        results.append(result)
        shot["framing"] = result
    return results


def semantic_shot_requirements(gray_frames: list[np.ndarray], shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create searchable shot roles without downloading a cloud model."""
    requirements = []
    for shot in shots:
        start, end = int(shot["startFrame"]), int(shot["endFrame"])
        sample = gray_frames[min(len(gray_frames) - 1, (start + end) // 2)]
        motion = math.hypot(float(shot["translationPx"]["x"]), float(shot["translationPx"]["y"])) / max(1, shot["durationFrames"])
        luma = float(sample.mean())
        contrast = float(sample.std())
        face = shot.get("framing", {})
        face_area = float(face.get("faceArea", 0.0))
        scale = "close_up" if face_area >= 0.085 else ("medium" if face_area >= 0.025 else "wide_or_detail")
        energy = "high_action" if motion > 2.0 or abs(math.log(max(float(shot["zoomRatio"]), 1e-6))) > 0.08 else "calm"
        lighting = "dark" if luma < 62 else ("bright" if luma > 175 else "balanced")
        role = "reaction_close_up" if scale == "close_up" and energy == "calm" else ("action_beat" if energy == "high_action" else "story_bridge")
        keywords = [scale, energy, lighting, role, shot.get("zoomDirection", "none") + "_zoom"]
        item = {"shot": shot["index"], "role": role, "keywords": keywords, "visual": {"luma": round(luma, 2), "contrast": round(contrast, 2), "shotScale": scale, "energy": energy, "lighting": lighting}, "searchInstruction": "Find unused footage matching: " + ", ".join(keywords) + ". Keep the primary subject centered and use one continuous camera angle."}
        requirements.append(item)
        shot["semantic"] = item
    return requirements


def _robust_unit(values: list[float]) -> list[float]:
    if not values:
        return []
    data = np.asarray(values, dtype=np.float64)
    low = float(np.percentile(data, 10))
    high = float(np.percentile(data, 90))
    if high - low < 1e-8:
        return [0.5 if float(value) > 0 else 0.0 for value in data]
    return [round(float(np.clip((value - low) / (high - low), 0.0, 1.0)), 4) for value in data]


def narrative_flow_map(
    shots: list[dict[str, Any]],
    events: list[dict[str, Any]],
    audio: dict[str, Any],
    duration: float,
    fps: float,
) -> dict[str, Any]:
    """Map editorial function and peak obligations without inventing story facts.

    The map is deliberately evidence based: shot motion/duration, measured audio
    energy, drops, and temporal position. Character or speaker identity remains an
    explicit external requirement when it cannot be recovered from flattened media.
    """
    if not shots:
        return {"available": False, "shots": [], "reason": "No canonical shots were detected."}

    duration = max(float(duration or 0), float(shots[-1].get("endTime") or 0), 1.0 / max(fps, 1.0))
    energy_curve = audio.get("energyCurve") or []
    onsets = [float(value) for value in audio.get("onsets") or []]
    drops = sorted(float(value) for value in audio.get("drops") or [] if 0 <= float(value) <= duration)
    dialogue_segments = audio.get("dialogueSegments") or audio.get("dialogue") or []
    transition_frames = [int(item.get("frame") or 0) for item in events if item.get("kind") == "cut_transition"]

    visual_raw: list[float] = []
    audio_raw: list[float] = []
    for shot in shots:
        start = float(shot.get("startTime") or 0)
        end = max(start + 1.0 / max(fps, 1.0), float(shot.get("endTime") or start))
        frames = max(1, int(shot.get("durationFrames") or round((end - start) * fps)))
        translation = shot.get("translationPx") or {}
        travel_per_frame = math.hypot(float(translation.get("x") or 0), float(translation.get("y") or 0)) / frames
        zoom_travel = abs(math.log(max(float(shot.get("zoomRatio") or 1), 1e-6)))
        cut_pressure = min(1.0, 8.0 / frames)
        visual_raw.append(travel_per_frame + zoom_travel * 8.0 + cut_pressure * 0.55)

        local_energy = [float(item.get("energy") or 0) for item in energy_curve if start <= float(item.get("time") or 0) < end]
        onset_density = sum(start <= value < end for value in onsets) / max(end - start, 0.1)
        audio_raw.append((max(local_energy, default=0.0) * 0.65) + (float(np.mean(local_energy)) if local_energy else 0.0) * 0.25 + min(1.0, onset_density / 5.0) * 0.10)

    visual_scores = _robust_unit(visual_raw)
    audio_scores = _robust_unit(audio_raw) if energy_curve or onsets else [0.0 for _ in shots]
    combined = [round(visual * (0.68 if energy_curve or onsets else 1.0) + audio_value * (0.32 if energy_curve or onsets else 0.0), 4) for visual, audio_value in zip(visual_scores, audio_scores)]

    def shot_for_time(value: float) -> int:
        for index, shot in enumerate(shots):
            if float(shot.get("startTime") or 0) <= value < float(shot.get("endTime") or duration + 1):
                return index
        return max(0, min(len(shots) - 1, int(round((value / duration) * (len(shots) - 1)))))

    eligible_drops = [value for value in drops if duration * 0.10 <= value <= duration * 0.62]
    if eligible_drops:
        first_highlight = shot_for_time(eligible_drops[0])
    else:
        early = [index for index, shot in enumerate(shots) if duration * 0.10 <= float(shot.get("startTime") or 0) <= duration * 0.62]
        first_highlight = max(early or list(range(len(shots))), key=lambda index: combined[index])

    climax_candidates = [index for index, shot in enumerate(shots) if float(shot.get("startTime") or 0) >= max(duration * 0.42, float(shots[first_highlight].get("endTime") or 0)) and float(shot.get("startTime") or 0) <= duration * 0.96]
    climax = max(climax_candidates or list(range(first_highlight, len(shots))) or [first_highlight], key=lambda index: (combined[index], visual_scores[index]))
    if len(shots) > 2 and climax == first_highlight:
        later = [index for index in range(first_highlight + 1, len(shots)) if float(shots[index].get("startTime") or 0) <= duration * 0.96]
        if later:
            climax = max(later, key=lambda index: (combined[index], visual_scores[index]))

    shot_map: list[dict[str, Any]] = []
    for index, shot in enumerate(shots):
        start = float(shot.get("startTime") or 0)
        end = float(shot.get("endTime") or start)
        semantic = shot.get("semantic") or {}
        scale = str((semantic.get("visual") or {}).get("shotScale") or "wide_or_detail")
        dialogue_here = [item for item in dialogue_segments if float(item.get("start") or 0) < end and float(item.get("end") or 0) > start]
        if index == first_highlight:
            phase, function, priority = "first_highlight", "action_peak", 2
        elif index == climax:
            phase, function, priority = "climax", "climax_action", 3
        elif start < duration * 0.10:
            phase, function, priority = "hook", ("visual_hook" if combined[index] >= 0.45 else "establishing"), 0
        elif index < first_highlight:
            phase, function, priority = "setup", ("dialogue_reaction_hold" if scale == "close_up" and visual_scores[index] < 0.45 else "story_setup"), 0
        elif index < climax:
            phase, function, priority = "escalation", ("action_escalation" if visual_scores[index] >= 0.45 else "tension_bridge"), 1
        else:
            phase, function, priority = "resolution", ("emotional_resolution" if visual_scores[index] < 0.62 else "aftermath_impact"), 0
        flashy = priority >= 2
        minimum_motion = 0.62 if priority == 3 else (0.48 if priority == 2 else 0.0)
        mouth_policy = "dialogue_visual_must_match_speaker" if dialogue_here else "avoid_visible_speech_without_aligned_dialogue"
        item = {
            "shot": index + 1,
            "phase": phase,
            "editorialFunction": function,
            "visualEnergyScore": visual_scores[index],
            "audioEnergyScore": audio_scores[index],
            "energyScore": combined[index],
            "peakPriority": priority,
            "flashyRequired": flashy,
            "minimumCandidateMotion": minimum_motion,
            "cutRhythm": "rapid" if int(shot.get("durationFrames") or 0) <= max(2, round(fps * 0.65)) else ("hold" if int(shot.get("durationFrames") or 0) >= round(fps * 2.4) else "medium"),
            "dialogueActive": bool(dialogue_here),
            "mouthMotionPolicy": mouth_policy,
            "speaker": str(dialogue_here[0].get("speaker") or "") if dialogue_here else "",
        }
        semantic.update(item)
        semantic["keywords"] = list(dict.fromkeys((semantic.get("keywords") or []) + [phase, function, "flashy_action" if flashy else "controlled_energy"]))
        semantic["searchInstruction"] = "Find unused footage matching " + function.replace("_", " ") + f" at {combined[index]:.0%} energy." + (" Require clearly readable high-motion action at this music peak." if flashy else " Preserve one continuous camera angle and the reference shot scale.")
        shot["semantic"] = semantic
        shot_map.append(item)

    return {
        "available": True,
        "version": 1,
        "firstHighlightShot": first_highlight + 1,
        "firstHighlightFrame": int(shots[first_highlight].get("startFrame") or 0),
        "climaxShot": climax + 1,
        "climaxFrame": int(shots[climax].get("startFrame") or 0),
        "resolutionStartsShot": min(len(shots), climax + 2),
        "cutFrames": transition_frames,
        "shots": shot_map,
        "rules": {
            "peakSlotsRequireHighMotionEvidence": True,
            "dialogueVisualsMustIdentifyTheSpeaker": True,
            "avoidMouthMovementWithoutMatchingDialogue": True,
            "doNotReplacePeakActionWithCalmOrScenicFootage": True,
        },
    }


def apply_effect_inventory(events: list[dict[str, Any]], inventory: list[dict[str, Any]] | list[str]) -> dict[str, Any]:
    names = set()
    for item in inventory or []:
        if isinstance(item, str): names.add(item.lower())
        elif isinstance(item, dict): names.update(str(item.get(key, "")).lower() for key in ("displayName", "matchName", "name"))
    substitutions = {"blurmocurves": ["blurmocurves"], "radial blur": ["adbe radial blur", "radial blur"], "directional blur": ["adbe motion blur", "directional blur"], "channel blur": ["adbe channel blur", "channel blur"], "exposure": ["adbe exposure2", "exposure"], "motion tile": ["adbe tile", "motion tile"]}
    missing = set()
    for event in events:
        for step in event.get("aeRecipe", []):
            effect = str(step.get("effect", ""))
            if not effect: continue
            available = not names or any(alias in names for alias in substitutions.get(effect.lower(), [effect.lower()]))
            step["available"] = available
            if not available:
                missing.add(effect)
                if effect == "BlurMoCurves": step["fallback"] = "Transform Scale with TonyFX fitted Bezier plus CC Force Motion Blur"
                elif effect == "Motion Tile": step["fallback"] = "Scale footage enough to cover the complete transition travel"
                else: step["fallback"] = "Use the closest installed AE-native equivalent and visually compare"
    return {"count": len(inventory or []), "missing": sorted(missing), "checked": bool(inventory)}


def advanced_audio_structure(audio: dict[str, Any], duration: float) -> dict[str, Any]:
    beats = np.asarray(audio.get("beats") or [], dtype=float)
    onsets = np.asarray(audio.get("onsets") or [], dtype=float)
    drops = np.asarray(audio.get("drops") or [], dtype=float)
    if not len(beats): return {"available": False, "phrases": [], "sections": []}
    intervals = np.diff(beats)
    median = float(np.median(intervals)) if len(intervals) else 0.5
    bars = []
    for index in range(0, len(beats), 4):
        start = float(beats[index]); end = float(beats[min(len(beats) - 1, index + 4)]) if index + 4 < len(beats) else min(duration, start + median * 4)
        bars.append({"start": round(start, 4), "end": round(end, 4), "beats": [round(float(value), 4) for value in beats[index:index + 4]]})
    sections = []
    for bar in bars:
        onset_count = int(np.sum((onsets >= bar["start"]) & (onsets < bar["end"])))
        drop = bool(np.any(np.abs(drops - bar["start"]) <= max(0.12, median * 0.35)))
        density = onset_count / max(bar["end"] - bar["start"], 0.1)
        sections.append({**bar, "onsetDensity": round(density, 3), "dropStart": drop, "recommendedPacing": "rapid" if density >= 3.6 else ("medium" if density >= 2.0 else "hold")})
    return {"available": True, "beatInterval": round(median, 6), "barCount": len(bars), "sections": sections, "strongDrops": [round(float(value), 4) for value in drops], "reverbSuggestions": [{"time": round(float(value), 4), "preRollSeconds": round(min(0.65, median * 1.5), 3), "instruction": "Place reverb on a separate removable audio layer ending exactly at this drop."} for value in drops[:12]]}


def load_feedback(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists(): return {"version": 1, "corrections": [], "approvedCurves": {}, "familyBias": {}}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {"version": 1, "corrections": [], "approvedCurves": {}, "familyBias": {}}


def apply_feedback(events: list[dict[str, Any]], feedback: dict[str, Any]) -> dict[str, Any]:
    bias = feedback.get("familyBias") or {}
    approved = feedback.get("approvedCurves") or {}
    changed = 0
    for event in events:
        ranked = event.get("renderedCandidates", {}).get("candidates", [])
        for item in ranked: item["feedbackAdjustedScore"] = round(float(item["score"]) + float(bias.get(item["family"], 0.0)), 4)
        if ranked:
            adjusted = max(ranked, key=lambda item: item["feedbackAdjustedScore"])
            event["feedbackWinner"] = adjusted["family"]
        curve = approved.get(event.get("graph"))
        if curve:
            event["curve"] = str(curve); event["curveSource"] = "approved TonyFX feedback library"; changed += 1
    return {"correctionCount": len(feedback.get("corrections") or []), "curveOverrides": changed, "familyBias": bias}


def build_repair_plan(reference: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    checks = []
    for shot in reference.get("shots", []):
        framing = shot.get("framing", {})
        if framing.get("safeFrameStatus") in {"unsafe", "review"}:
            checks.append({"severity": "warning", "time": shot["startTime"], "category": "framing", "action": framing.get("note") or "Center the subject using the suggested normalized offset, then inspect both zoom extremes."})
    for event in reference.get("events", []):
        rendered = event.get("renderedCandidates", {})
        if float(rendered.get("confidence", 0)) < 0.58:
            checks.append({"severity": "review", "time": event["time"], "category": "transition", "action": "Candidate family is ambiguous. Render the top two hypotheses and compare the full transition span."})
    if candidate:
        checks.extend(candidate.get("mismatches", []))
    return {"version": 1, "checks": checks, "blockingCount": sum(item["severity"] == "error" for item in checks), "workflow": ["Build from canonical cut frames", "Render the edit at reference resolution and fps", "Run compare-edit", "Apply only high-confidence repairs", "Re-render and require all timing errors <= 1 frame"]}


def compare_analysis_reports(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare two analyzer reports and produce frame-specific repair actions."""
    reference_fps = float(reference.get("media", {}).get("fps") or 30.0)
    candidate_fps = float(candidate.get("media", {}).get("fps") or reference_fps)
    reference_cuts = [float(item["time"]) for item in reference.get("cutEvents", [])]
    candidate_cuts = [float(item["time"]) for item in candidate.get("cutEvents", [])]
    matched, missing, extra, timing_errors = [], [], list(candidate_cuts), []
    tolerance = max(1.0 / reference_fps, 0.04)
    for time_value in reference_cuts:
        if not extra:
            missing.append(time_value); continue
        nearest = min(extra, key=lambda value: abs(value - time_value))
        delta = nearest - time_value
        if abs(delta) <= max(tolerance, 2.0 / reference_fps):
            matched.append({"reference": round(time_value, 6), "candidate": round(nearest, 6), "deltaFrames": round(delta * reference_fps, 2)})
            timing_errors.append(abs(delta * reference_fps)); extra.remove(nearest)
        else:
            missing.append(time_value)
    transition_mismatches, curve_mismatches = [], []
    candidate_events = candidate.get("events", [])
    for event in reference.get("events", []):
        if not candidate_events:
            transition_mismatches.append({"time": event["time"], "expected": event.get("renderedCandidateFamily") or event.get("family"), "actual": "missing", "referenceSpan": [event.get("startFrame"), event.get("endFrame")], "referenceCurve": event.get("curve")})
            continue
        nearest = min(candidate_events, key=lambda item: abs(float(item["time"]) - float(event["time"])))
        if abs(float(nearest["time"]) - float(event["time"])) <= 3.0 / reference_fps:
            reference_family = event.get("renderedCandidateFamily") or event.get("family")
            candidate_family = nearest.get("renderedCandidateFamily") or nearest.get("family")
            if reference_family != candidate_family:
                transition_mismatches.append({"time": event["time"], "expected": reference_family, "actual": candidate_family, "referenceSpan": [event.get("startFrame"), event.get("endFrame")], "referenceCurve": event.get("curve")})
            reference_controls = (event.get("advancedCurve") or {}).get("controls") or []
            candidate_controls = (nearest.get("advancedCurve") or {}).get("controls") or []
            if len(reference_controls) == 4 and len(candidate_controls) == 4:
                curve_error = float(np.mean(np.abs(np.asarray(reference_controls) - np.asarray(candidate_controls))))
                if curve_error > 0.09:
                    curve_mismatches.append({"time": event["time"], "error": round(curve_error, 4), "expected": reference_controls, "actual": candidate_controls})
        else:
            transition_mismatches.append({"time": event["time"], "expected": event.get("renderedCandidateFamily") or event.get("family"), "actual": "missing", "referenceSpan": [event.get("startFrame"), event.get("endFrame")], "referenceCurve": event.get("curve")})
    reference_shots = reference.get("shots", []); candidate_shots = candidate.get("shots", [])
    duration_mismatches = []
    for index in range(min(len(reference_shots), len(candidate_shots))):
        delta = int(candidate_shots[index]["durationFrames"]) - int(reference_shots[index]["durationFrames"])
        if abs(delta) > 1:
            duration_mismatches.append({"shot": index + 1, "deltaFrames": delta, "expectedFrames": reference_shots[index]["durationFrames"], "actualFrames": candidate_shots[index]["durationFrames"]})
    mismatches = []
    for time_value in missing:
        mismatches.append({"severity": "error", "time": round(time_value, 6), "category": "missing_cut", "action": "Add the missing scene boundary at this exact reference time."})
    for time_value in extra:
        mismatches.append({"severity": "error", "time": round(time_value, 6), "category": "extra_cut", "action": "Remove this extra boundary; keep one continuous camera angle for the reference shot."})
    for item in transition_mismatches:
        mismatches.append({"severity": "warning", "time": item["time"], "category": "transition", "action": f"Replace {item['actual']} with {item['expected']} across frames {item['referenceSpan'][0]}-{item['referenceSpan'][1]} using curve {item['referenceCurve']}."})
    for item in duration_mismatches:
        mismatches.append({"severity": "warning", "time": reference_shots[item["shot"] - 1]["startTime"], "category": "shot_duration", "action": f"Retiming shot {item['shot']} by {-item['deltaFrames']} frame(s) to match {item['expectedFrames']} frames."})
    for item in curve_mismatches:
        mismatches.append({"severity": "warning", "time": item["time"], "category": "curve", "action": f"Replace the transition interpolation with fitted Bezier {item['expected']}; current curve differs by {item['error']:.3f}."})
    framing_mismatches = []
    for index in range(min(len(reference_shots), len(candidate_shots))):
        expected = reference_shots[index].get("visionSubject") or reference_shots[index].get("framing") or {}
        actual = candidate_shots[index].get("visionSubject") or candidate_shots[index].get("framing") or {}
        if expected.get("center") and actual.get("center"):
            offset = math.hypot(float(expected["center"]["x"]) - float(actual["center"]["x"]), float(expected["center"]["y"]) - float(actual["center"]["y"]))
            if offset > 0.12 or actual.get("safeFrameStatus") == "unsafe":
                item = {"shot": index + 1, "offset": round(offset, 4), "expected": expected["center"], "actual": actual["center"]}
                framing_mismatches.append(item)
                mismatches.append({"severity": "warning", "time": reference_shots[index]["startTime"], "category": "framing", "action": f"Recenter shot {index + 1}; normalized subject-center error is {offset:.3f}. Preserve the user's framing at both zoom extremes."})
    narrative = reference.get("narrativeMap") or (reference.get("editBlueprint") or {}).get("narrativeMap") or {}
    peak_indices = []
    for shot_number in (narrative.get("firstHighlightShot"), narrative.get("climaxShot")):
        if shot_number and int(shot_number) - 1 not in peak_indices:
            peak_indices.append(int(shot_number) - 1)
    if not peak_indices:
        peak_indices = [index for index, shot in enumerate(reference_shots) if int((shot.get("semantic") or {}).get("peakPriority") or 0) >= 2]
    candidate_visual = [float((shot.get("semantic") or {}).get("visualEnergyScore") or 0) for shot in candidate_shots]
    peak_energy_mismatches = []
    for index in peak_indices:
        if index < 0 or index >= len(reference_shots) or index >= len(candidate_shots):
            peak_energy_mismatches.append({"shot": index + 1, "reason": "missing candidate peak slot"})
            continue
        priority = int((reference_shots[index].get("semantic") or {}).get("peakPriority") or (3 if index + 1 == narrative.get("climaxShot") else 2))
        actual_energy = candidate_visual[index]
        percentile = float(np.mean(np.asarray(candidate_visual) <= actual_energy)) if candidate_visual else 0.0
        minimum = 0.58 if priority >= 3 else 0.44
        minimum_percentile = 0.72 if priority >= 3 else 0.60
        if actual_energy + 1e-6 < minimum or percentile + 1e-6 < minimum_percentile:
            item = {"shot": index + 1, "priority": priority, "actualVisualEnergy": round(actual_energy, 4), "candidatePercentile": round(percentile, 4), "minimum": minimum, "minimumPercentile": minimum_percentile}
            peak_energy_mismatches.append(item)
            mismatches.append({"severity": "error", "time": reference_shots[index]["startTime"], "category": "peak_energy", "action": f"Replace shot {index + 1} with clearly readable high-motion footage. This reference peak cannot be filled by a calm, scenic, or low-action shot."})
    mean_timing = float(np.mean(timing_errors)) if timing_errors else (99.0 if reference_cuts else 0.0)
    cut_recall = len(matched) / max(1, len(reference_cuts))
    cut_precision = len(matched) / max(1, len(candidate_cuts))
    transition_accuracy = 1.0 - len(transition_mismatches) / max(1, len(reference.get("events", [])))
    curve_accuracy = 1.0 - len(curve_mismatches) / max(1, len(reference.get("events", [])))
    framing_accuracy = 1.0 - len(framing_mismatches) / max(1, len(reference_shots))
    peak_accuracy = 1.0 - len(peak_energy_mismatches) / max(1, len(peak_indices)) if peak_indices else 1.0
    score = float(np.clip((cut_recall * 0.30 + cut_precision * 0.18 + transition_accuracy * 0.22 + curve_accuracy * 0.10 + framing_accuracy * 0.08 + max(0.0, 1.0 - mean_timing / 3.0) * 0.12) * (0.90 + 0.10 * peak_accuracy), 0.0, 1.0))
    reference_media, candidate_media = reference.get("media", {}), candidate.get("media", {})
    format_mismatches = []
    for field in ("width", "height", "frames"):
        if reference_media.get(field) is not None and candidate_media.get(field) is not None and int(reference_media[field]) != int(candidate_media[field]):
            format_mismatches.append({"field": field, "expected": reference_media[field], "actual": candidate_media[field]})
    if abs(candidate_fps - reference_fps) > 1e-6:
        format_mismatches.append({"field": "fps", "expected": reference_fps, "actual": candidate_fps})
    def topology(value: dict[str, Any]) -> list[tuple[int, int, str]]:
        return sorted((int(item.get("shot") or 0), int(item.get("matchesShot") or 0), str(item.get("kind") or "repeat")) for item in value.get("repeats", []) if item.get("shot") and item.get("matchesShot"))
    reference_topology, candidate_topology = topology(reference), topology(candidate)
    repeat_mismatches = [] if reference_topology == candidate_topology else [{"expected": reference_topology, "actual": candidate_topology}]
    gates = {
        "format": {"passed": not format_mismatches, "mismatches": format_mismatches},
        "cuts": {"passed": not missing and not extra and mean_timing <= 1.0, "meanAbsoluteErrorFrames": round(mean_timing, 3)},
        "transitions": {"passed": not transition_mismatches, "count": len(transition_mismatches)},
        "curves": {"passed": not curve_mismatches, "count": len(curve_mismatches)},
        "durations": {"passed": not duration_mismatches and len(reference_shots) == len(candidate_shots), "count": len(duration_mismatches)},
        "framing": {"passed": not framing_mismatches, "count": len(framing_mismatches)},
        "peakEnergy": {"passed": not peak_energy_mismatches, "count": len(peak_energy_mismatches), "peakShots": [index + 1 for index in peak_indices]},
        "repeatTopology": {"passed": not repeat_mismatches, "mismatches": repeat_mismatches},
    }
    passed = all(item["passed"] for item in gates.values())
    return {"schema": "tonyfx.finished-edit-comparison.v4", "score": round(score, 4), "passed": passed, "aggregateScoreAuthorizesPass": False, "gates": gates, "timing": {"meanAbsoluteErrorFrames": round(mean_timing, 3), "matched": matched, "missing": [round(value, 6) for value in missing], "extra": [round(value, 6) for value in extra]}, "transitionMismatches": transition_mismatches, "curveMismatches": curve_mismatches, "framingMismatches": framing_mismatches, "peakEnergyMismatches": peak_energy_mismatches, "durationMismatches": duration_mismatches, "repeatMismatches": repeat_mismatches, "formatMismatches": format_mismatches, "mismatches": mismatches}
