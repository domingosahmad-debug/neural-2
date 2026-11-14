"""Reference-driven, offline color matching for TonyFX.

The solver deliberately separates an editable After Effects approximation from
the higher precision residual transform.  The former is expressed as Lumetri
controls; the latter is written as a standard .cube LUT and can be rendered by
FFmpeg without changing the source media.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
EPSILON = 1.0e-6
_FACE_DETECTORS: dict[tuple[str, int, int], Any] = {}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _resize_for_analysis(frame: np.ndarray, max_side: int = 720) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(1.0, float(max_side) / max(height, width))
    if scale >= 0.999:
        return frame
    return cv2.resize(frame, (max(2, int(round(width * scale))), max(2, int(round(height * scale)))), interpolation=cv2.INTER_AREA)


def _video_metadata(path: Path) -> dict[str, float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open media: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    width = float(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0.0)
    height = float(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0.0)
    capture.release()
    return {"fps": fps, "frames": frames, "duration": frames / fps if fps > 0 else 0.0, "width": width, "height": height}


def _sample_times(duration: float, start: float, span: float, count: int) -> list[float]:
    count = max(1, min(15, int(count)))
    start = max(0.0, float(start))
    available = max(0.0, duration - start)
    span = min(available, float(span) if span > 0 else available)
    if span <= 0.02:
        return [min(max(0.0, start), max(0.0, duration - 0.001))]
    if count == 1:
        return [start + span * 0.5]
    margin = min(span * 0.08, 0.25)
    return np.linspace(start + margin, start + span - margin, count).astype(float).tolist()


def read_media_samples(path: Path, start: float, duration: float, count: int) -> tuple[list[np.ndarray], dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() in IMAGE_SUFFIXES:
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError(f"Could not decode image: {path}")
        frame = _resize_for_analysis(frame)
        return [frame], {"kind": "image", "duration": 0.0, "times": [0.0], "width": frame.shape[1], "height": frame.shape[0]}

    metadata = _video_metadata(path)
    times = _sample_times(metadata["duration"], start, duration, count)
    capture = cv2.VideoCapture(str(path))
    frames: list[np.ndarray] = []
    decoded_times: list[float] = []
    for timestamp in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(_resize_for_analysis(frame))
            decoded_times.append(timestamp)
    capture.release()
    if not frames:
        raise RuntimeError(f"Could not decode sampled frames from: {path}")
    return frames, {"kind": "video", **metadata, "times": decoded_times}


def _detect_faces(frame: np.ndarray, model_path: Path | None) -> list[tuple[int, int, int, int]]:
    if not model_path or not model_path.exists():
        return []
    try:
        height, width = frame.shape[:2]
        cache_key = (str(model_path), width, height)
        detector = _FACE_DETECTORS.get(cache_key)
        if detector is None:
            detector = cv2.FaceDetectorYN_create(str(model_path), "", (width, height), 0.55, 0.3, 5000)
            detector.setInputSize((width, height))
            _FACE_DETECTORS[cache_key] = detector
        _status, faces = detector.detect(frame)
        if faces is None:
            return []
        result = []
        for face in faces:
            x, y, w, h = [int(round(value)) for value in face[:4]]
            x, y = max(0, x), max(0, y)
            result.append((x, y, min(width - x, w), min(height - y, h)))
        return sorted(result, key=lambda item: item[2] * item[3], reverse=True)
    except Exception:
        return []


def _frame_weights(frame: np.ndarray, faces: list[tuple[int, int, int, int]]) -> tuple[np.ndarray, np.ndarray]:
    height, width = frame.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    nx = (xx - width * 0.5) / max(1.0, width * 0.5)
    ny = (yy - height * 0.48) / max(1.0, height * 0.5)
    weights = 0.55 + 0.45 * np.exp(-(nx * nx + ny * ny) * 1.7)
    face_mask = np.zeros((height, width), dtype=np.float32)
    skin_seed = np.zeros((height, width), dtype=np.uint8)
    for x, y, w, h in faces:
        if w <= 0 or h <= 0:
            continue
        pad_x, pad_y = int(w * 0.18), int(h * 0.16)
        left, top = max(0, x - pad_x), max(0, y - pad_y)
        right, bottom = min(width, x + w + pad_x), min(height, y + h + pad_y)
        cv2.ellipse(face_mask, ((left + right) // 2, (top + bottom) // 2), (max(1, (right - left) // 2), max(1, (bottom - top) // 2)), 0, 0, 360, 1.0, -1)
        cv2.ellipse(skin_seed, (int(x + w * 0.5), int(y + h * 0.58)), (max(1, int(w * 0.25)), max(1, int(h * 0.27))), 0, 0, 360, 255, -1)
    if np.max(face_mask) > 0:
        # Extend protection from the detected face to exposed skin that shares
        # its chroma (neck, shoulders, arms). This avoids a protected face
        # floating above globally over-graded skin.
        rgb = _rgb_float(frame)
        lab = _rgb_to_lab(rgb)
        seed_pixels = lab[skin_seed > 0]
        if seed_pixels.size:
            seed_ab = np.median(seed_pixels[:, 1:3], axis=0)
            seed_l = float(np.median(seed_pixels[:, 0]))
            chroma_distance = np.linalg.norm(lab[..., 1:3] - seed_ab, axis=2)
            luma_distance = np.abs(lab[..., 0] - seed_l)
            skin = ((chroma_distance < 18.0) & (luma_distance < 42.0)).astype(np.uint8) * 255
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, kernel)
            skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, kernel, iterations=2)
            face_mask = np.maximum(face_mask, skin.astype(np.float32) / 255.0 * 0.9)
        sigma = max(3.0, min(height, width) * 0.018)
        face_mask = cv2.GaussianBlur(face_mask, (0, 0), sigma)
        # The global look must come from wardrobe, set, and lighting rather
        # than attempting to turn one person's complexion into another's.
        # Faces are measured separately and protected during application.
        weights *= 1.0 - face_mask * 0.72
    return weights.astype(np.float32), np.clip(face_mask, 0.0, 1.0)


def _rgb_float(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ordered_values = values[order]
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    if cumulative.size == 0 or cumulative[-1] <= EPSILON:
        return np.quantile(values, quantiles)
    cumulative /= cumulative[-1]
    return np.interp(quantiles, cumulative, ordered_values)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    normalized = weights / max(EPSILON, float(np.sum(weights)))
    return np.sum(values * normalized[:, None], axis=0)


def _weighted_cov(values: np.ndarray, weights: np.ndarray, mean: np.ndarray) -> np.ndarray:
    centered = values - mean
    normalized = weights / max(EPSILON, float(np.sum(weights)))
    covariance = (centered * normalized[:, None]).T @ centered
    return covariance + np.eye(values.shape[1], dtype=np.float64) * 1.0e-4


def _matrix_sqrt(matrix: np.ndarray, inverse: bool = False) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    values = np.maximum(values, 1.0e-5)
    diagonal = np.diag(1.0 / np.sqrt(values) if inverse else np.sqrt(values))
    return vectors @ diagonal @ vectors.T


def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    shaped = np.asarray(rgb, dtype=np.float32)
    original = shaped.shape
    converted = cv2.cvtColor(shaped.reshape((-1, 1, 3)), cv2.COLOR_RGB2LAB)
    return converted.reshape(original)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    shaped = np.asarray(lab, dtype=np.float32)
    original = shaped.shape
    converted = cv2.cvtColor(shaped.reshape((-1, 1, 3)), cv2.COLOR_LAB2RGB)
    return np.clip(converted.reshape(original), 0.0, 1.0)


def _collect_pixels(frames: list[np.ndarray], model_path: Path | None, max_pixels: int = 260000) -> dict[str, Any]:
    rgb_parts: list[np.ndarray] = []
    weight_parts: list[np.ndarray] = []
    face_parts: list[np.ndarray] = []
    face_weight_parts: list[np.ndarray] = []
    faces_per_frame: list[list[tuple[int, int, int, int]]] = []
    per_frame_luma: list[float] = []
    per_frame_lab: list[list[float]] = []
    per_frame_limit = max(4000, max_pixels // max(1, len(frames)))
    for frame in frames:
        faces = _detect_faces(frame, model_path)
        faces_per_frame.append(faces)
        rgb = _rgb_float(frame)
        weights, face_mask = _frame_weights(frame, faces)
        luma = _luminance(rgb)
        valid = (luma > 0.012) & (luma < 0.992)
        indices = np.flatnonzero(valid)
        if indices.size > per_frame_limit:
            stride = max(1, indices.size // per_frame_limit)
            indices = indices[::stride][:per_frame_limit]
        flat_rgb = rgb.reshape((-1, 3))[indices]
        flat_weights = weights.reshape(-1)[indices]
        rgb_parts.append(flat_rgb)
        weight_parts.append(flat_weights)
        face_indices = np.flatnonzero((face_mask > 0.12) & valid)
        if face_indices.size:
            if face_indices.size > per_frame_limit // 2:
                stride = max(1, face_indices.size // (per_frame_limit // 2))
                face_indices = face_indices[::stride][:(per_frame_limit // 2)]
            face_parts.append(rgb.reshape((-1, 3))[face_indices])
            face_weight_parts.append(face_mask.reshape(-1)[face_indices])
        per_frame_luma.append(float(np.median(luma[valid])) if np.any(valid) else float(np.median(luma)))
        frame_lab = _rgb_to_lab(flat_rgb)
        per_frame_lab.append(_weighted_mean(frame_lab, flat_weights).astype(float).tolist())
    return {
        "rgb": np.concatenate(rgb_parts, axis=0),
        "weights": np.concatenate(weight_parts, axis=0),
        "faceRgb": np.concatenate(face_parts, axis=0) if face_parts else np.empty((0, 3), dtype=np.float32),
        "faceWeights": np.concatenate(face_weight_parts, axis=0) if face_weight_parts else np.empty((0,), dtype=np.float32),
        "faces": faces_per_frame,
        "perFrameLuma": per_frame_luma,
        "perFrameLab": per_frame_lab,
    }


def _tone_pixels(rgb: np.ndarray, source_knots: np.ndarray, reference_knots: np.ndarray) -> np.ndarray:
    luma = _luminance(rgb)
    mapped = np.interp(luma, source_knots, reference_knots)
    ratio = mapped / np.maximum(luma, 0.008)
    ratio = np.clip(ratio, 0.2, 5.0)
    return np.clip(rgb * ratio[..., None], 0.0, 1.0)


def solve_recipe(source: dict[str, Any], reference: dict[str, Any], strength: float, mode: str, match_tone: bool, match_color: bool, protect_skin: bool) -> dict[str, Any]:
    quantile_positions = np.asarray([0.01, 0.05, 0.18, 0.50, 0.82, 0.95, 0.99], dtype=np.float64)
    source_luma = _luminance(source["rgb"])
    reference_luma = _luminance(reference["rgb"])
    source_knots = _weighted_quantile(source_luma, source["weights"], quantile_positions)
    reference_knots = _weighted_quantile(reference_luma, reference["weights"], quantile_positions)
    source_knots = np.maximum.accumulate(source_knots)
    reference_knots = np.maximum.accumulate(reference_knots)
    if not match_tone:
        reference_knots = source_knots.copy()
    else:
        # Shot matching should transfer the reference's photographic character,
        # not force unrelated sets and wardrobe into the same histogram. Bound
        # every tonal region before interpolation so bright walls or dark sets
        # cannot crush a subject or blow out skin.
        tone_limits = {
            "continuity": np.asarray([0.035, 0.055, 0.09, 0.14, 0.12, 0.09, 0.055]),
            "look": np.asarray([0.05, 0.075, 0.12, 0.18, 0.16, 0.12, 0.075]),
            "skin": np.asarray([0.025, 0.04, 0.07, 0.11, 0.09, 0.07, 0.04]),
        }
        limits = tone_limits.get(mode, tone_limits["continuity"])
        reference_knots = source_knots + np.clip(reference_knots - source_knots, -limits, limits)
        reference_knots = np.clip(np.maximum.accumulate(reference_knots), 0.0, 1.0)

    toned_source = _tone_pixels(source["rgb"], source_knots, reference_knots)
    source_lab = _rgb_to_lab(toned_source)
    reference_lab = _rgb_to_lab(reference["rgb"])
    source_mean = _weighted_mean(source_lab, source["weights"])
    reference_mean = _weighted_mean(reference_lab, reference["weights"])
    source_cov = _weighted_cov(source_lab, source["weights"], source_mean)
    reference_cov = _weighted_cov(reference_lab, reference["weights"], reference_mean)
    # A full covariance transfer is mathematically attractive but unsafe for
    # unrelated footage: a single saturated prop can produce extreme channel
    # coupling. Use robust, bounded Lab chroma scales and offsets instead.
    source_std = np.sqrt(np.maximum(np.diag(source_cov), 1.0e-4))
    reference_std = np.sqrt(np.maximum(np.diag(reference_cov), 1.0e-4))
    raw_scale = reference_std / np.maximum(source_std, 1.0e-4)
    scale_bounds = {
        "continuity": (0.88, 1.14),
        "look": (0.80, 1.22),
        "skin": (0.92, 1.10),
    }
    offset_limits = {"continuity": 4.5, "look": 7.0, "skin": 3.0}
    low_scale, high_scale = scale_bounds.get(mode, scale_bounds["continuity"])
    color_matrix = np.eye(3, dtype=np.float64)
    color_matrix[1, 1] = _clamp(raw_scale[1], low_scale, high_scale)
    color_matrix[2, 2] = _clamp(raw_scale[2], low_scale, high_scale)
    safe_reference_mean = source_mean.copy()
    chroma_delta = np.clip(reference_mean[1:3] - source_mean[1:3], -offset_limits.get(mode, 4.5), offset_limits.get(mode, 4.5))
    safe_reference_mean[1:3] += chroma_delta
    reference_mean = safe_reference_mean
    if not match_color:
        color_matrix = np.eye(3)
        reference_mean = source_mean.copy()

    face_delta = np.zeros(3, dtype=np.float64)
    if source["faceRgb"].size and reference["faceRgb"].size:
        source_face = _tone_pixels(source["faceRgb"], source_knots, reference_knots)
        source_face_lab = _rgb_to_lab(source_face)
        reference_face_lab = _rgb_to_lab(reference["faceRgb"])
        source_face_mean = _weighted_mean(source_face_lab, source["faceWeights"])
        reference_face_mean = _weighted_mean(reference_face_lab, reference["faceWeights"])
        face_delta = reference_face_mean - source_face_mean
        face_delta[0] = 0.0
        face_delta[1:] = np.clip(face_delta[1:] * 0.35, -4.0, 4.0)

    src_median, ref_median = max(EPSILON, source_knots[3]), max(EPSILON, reference_knots[3])
    src_range = max(EPSILON, source_knots[5] - source_knots[1])
    ref_range = max(EPSILON, reference_knots[5] - reference_knots[1])
    src_chroma = np.linalg.norm(source_lab[:, 1:], axis=1)
    ref_chroma = np.linalg.norm(reference_lab[:, 1:], axis=1)
    saturation_ratio = float(np.median(ref_chroma) / max(EPSILON, np.median(src_chroma)))
    saturation_bounds = {"continuity": (0.88, 1.16), "look": (0.80, 1.28), "skin": (0.92, 1.10)}
    sat_low, sat_high = saturation_bounds.get(mode, saturation_bounds["continuity"])
    saturation_ratio = _clamp(saturation_ratio, sat_low, sat_high)
    lumetri = {
        "temperature": round(_clamp((reference_mean[2] - source_mean[2]) * 2.2, -100, 100), 2),
        "tint": round(_clamp((reference_mean[1] - source_mean[1]) * 2.0, -100, 100), 2),
        "exposure": round(_clamp(math.log(ref_median / src_median, 2), -1.25, 1.25), 3),
        "contrast": round(_clamp((ref_range / src_range - 1.0) * 65.0, -45, 45), 2),
        "highlights": round(_clamp((reference_knots[5] - source_knots[5]) * 140.0, -55, 55), 2),
        "shadows": round(_clamp((reference_knots[1] - source_knots[1]) * 180.0, -55, 55), 2),
        "whites": round(_clamp((reference_knots[6] - source_knots[6]) * 130.0, -45, 45), 2),
        "blacks": round(_clamp((reference_knots[0] - source_knots[0]) * 180.0, -45, 45), 2),
        "saturation": round(_clamp(saturation_ratio * 100.0, 0, 200), 2),
        "vibrance": round(_clamp((saturation_ratio - 1.0) * 55.0, -100, 100), 2),
        "creativeSaturation": 100.0,
    }
    lumetri_strength = _clamp(strength, 0.0, 1.0)
    for control in ("temperature", "tint", "exposure", "contrast", "highlights", "shadows", "whites", "blacks", "vibrance"):
        lumetri[control] = round(float(lumetri[control]) * lumetri_strength, 3)
    lumetri["saturation"] = round(100.0 + (float(lumetri["saturation"]) - 100.0) * lumetri_strength, 3)
    return {
        "sourceKnots": source_knots.astype(float).tolist(),
        "referenceKnots": reference_knots.astype(float).tolist(),
        "sourceMean": source_mean.astype(float).tolist(),
        "referenceMean": reference_mean.astype(float).tolist(),
        "matrix": color_matrix.astype(float).tolist(),
        "faceDelta": face_delta.astype(float).tolist(),
        "strength": _clamp(strength, 0.0, 1.0),
        "protectSkin": bool(protect_skin),
        "mode": mode,
        "lumetri": lumetri,
    }


def apply_recipe_rgb(rgb: np.ndarray, recipe: dict[str, Any], face_mask: np.ndarray | None = None, include_face: bool = True) -> np.ndarray:
    source_knots = np.asarray(recipe["sourceKnots"], dtype=np.float64)
    reference_knots = np.asarray(recipe["referenceKnots"], dtype=np.float64)
    toned = _tone_pixels(np.asarray(rgb, dtype=np.float32), source_knots, reference_knots)
    lab = _rgb_to_lab(toned)
    source_mean = np.asarray(recipe["sourceMean"], dtype=np.float64)
    reference_mean = np.asarray(recipe["referenceMean"], dtype=np.float64)
    matrix = np.asarray(recipe["matrix"], dtype=np.float64)
    transformed_lab = (lab - source_mean) @ matrix.T + reference_mean
    transformed = _lab_to_rgb(transformed_lab)
    strength = float(recipe["strength"])
    result = np.clip(np.asarray(rgb, dtype=np.float32) * (1.0 - strength) + transformed * strength, 0.0, 1.0)
    if include_face and recipe.get("protectSkin") and face_mask is not None and np.max(face_mask) > 0:
        face_delta = np.asarray(recipe.get("faceDelta", [0, 0, 0]), dtype=np.float64)
        mode = str(recipe.get("mode") or "continuity")
        tone_amount = 0.20 if mode == "continuity" else (0.30 if mode == "look" else 0.15)
        protected = np.clip(np.asarray(rgb, dtype=np.float32) * (1.0 - tone_amount) + toned * tone_amount, 0.0, 1.0)
        if mode == "skin" and np.linalg.norm(face_delta[1:]) > 0.01:
            face_lab = _rgb_to_lab(protected) + face_delta
            face_rgb = _lab_to_rgb(face_lab)
            protected = protected * 0.68 + face_rgb * 0.32
        blend = np.clip(face_mask[..., None] * 0.96, 0.0, 1.0)
        result = result * (1.0 - blend) + protected * blend
    return np.clip(result, 0.0, 1.0)


def _match_error(rgb: np.ndarray, weights: np.ndarray, reference: dict[str, Any]) -> float:
    luma = _luminance(rgb)
    ref_luma = _luminance(reference["rgb"])
    positions = np.asarray([0.05, 0.18, 0.5, 0.82, 0.95])
    lhs = _weighted_quantile(luma, weights, positions)
    rhs = _weighted_quantile(ref_luma, reference["weights"], positions)
    tone_error = float(np.mean(np.abs(lhs - rhs)))
    lab = _rgb_to_lab(rgb)
    ref_lab = _rgb_to_lab(reference["rgb"])
    lhs_mean = _weighted_mean(lab, weights)
    rhs_mean = _weighted_mean(ref_lab, reference["weights"])
    color_error = float(np.linalg.norm((lhs_mean - rhs_mean) / np.asarray([100.0, 45.0, 45.0])))
    lhs_chroma = float(np.median(np.linalg.norm(lab[:, 1:], axis=1)))
    rhs_chroma = float(np.median(np.linalg.norm(ref_lab[:, 1:], axis=1)))
    chroma_error = abs(lhs_chroma - rhs_chroma) / 80.0
    return tone_error * 1.8 + color_error * 0.75 + chroma_error * 0.35


def _safety_metrics(source_rgb: np.ndarray, matched_rgb: np.ndarray, skin_mask: np.ndarray | None) -> dict[str, Any]:
    source = np.clip(np.asarray(source_rgb, dtype=np.float32), 0.0, 1.0)
    matched = np.clip(np.asarray(matched_rgb, dtype=np.float32), 0.0, 1.0)
    source_luma = _luminance(source)
    matched_luma = _luminance(matched)
    source_high = float(np.mean(np.max(source, axis=2) >= 0.995))
    matched_high = float(np.mean(np.max(matched, axis=2) >= 0.995))
    source_low = float(np.mean(source_luma <= 0.012))
    matched_low = float(np.mean(matched_luma <= 0.012))
    source_chroma = np.max(source, axis=2) - np.min(source, axis=2)
    matched_chroma = np.max(matched, axis=2) - np.min(matched, axis=2)
    source_sat_clip = float(np.mean(source_chroma >= 0.94))
    matched_sat_clip = float(np.mean(matched_chroma >= 0.94))

    skin_delta = 0.0
    skin_luma_delta = 0.0
    skin_pixels = 0
    if skin_mask is not None and np.max(skin_mask) > 0:
        valid_skin = skin_mask > 0.28
        skin_pixels = int(np.count_nonzero(valid_skin))
        if skin_pixels:
            source_lab = _rgb_to_lab(source)[valid_skin]
            matched_lab = _rgb_to_lab(matched)[valid_skin]
            skin_delta = float(np.median(np.linalg.norm(matched_lab - source_lab, axis=1)))
            skin_luma_delta = float(abs(np.median(matched_lab[:, 0]) - np.median(source_lab[:, 0])))

    warnings: list[str] = []
    if matched_high > max(0.045, source_high + 0.018):
        warnings.append("Highlight clipping increased beyond the safe limit.")
    if matched_low > max(0.16, source_low + 0.045):
        warnings.append("Shadow crushing increased beyond the safe limit.")
    if matched_sat_clip > max(0.035, source_sat_clip + 0.018):
        warnings.append("Color saturation is clipping.")
    if skin_pixels and skin_delta > 7.0:
        warnings.append("Skin color changed beyond the protected limit.")
    if skin_pixels and skin_luma_delta > 5.5:
        warnings.append("Skin exposure changed beyond the protected limit.")
    return {
        "safe": not warnings,
        "warnings": warnings,
        "sourceHighlightClipping": round(source_high * 100.0, 3),
        "matchedHighlightClipping": round(matched_high * 100.0, 3),
        "sourceShadowCrushing": round(source_low * 100.0, 3),
        "matchedShadowCrushing": round(matched_low * 100.0, 3),
        "sourceSaturationClipping": round(source_sat_clip * 100.0, 3),
        "matchedSaturationClipping": round(matched_sat_clip * 100.0, 3),
        "skinDeltaE": round(skin_delta, 3),
        "skinLumaDelta": round(skin_luma_delta, 3),
        "skinPixels": skin_pixels,
    }


def _draw_label(image: np.ndarray, text: str) -> None:
    cv2.rectangle(image, (0, 0), (image.shape[1], 34), (10, 12, 16), -1)
    cv2.putText(image, text, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)


def write_comparison(source: np.ndarray, reference: np.ndarray, matched: np.ndarray, output: Path) -> None:
    height = 420
    panels = []
    for frame, label in ((source, "SOURCE"), (reference, "REFERENCE"), (matched, "MATCHED")):
        scale = height / frame.shape[0]
        panel = cv2.resize(frame, (max(2, int(frame.shape[1] * scale)), height), interpolation=cv2.INTER_AREA)
        _draw_label(panel, label)
        panels.append(panel)
    cv2.imwrite(str(output), np.concatenate(panels, axis=1))


def write_scopes(source_rgb: np.ndarray, reference_rgb: np.ndarray, matched_rgb: np.ndarray, output: Path) -> None:
    canvas = np.full((620, 960, 3), 11, dtype=np.uint8)
    cv2.putText(canvas, "TONYFX COLOR MATCH SCOPES", (22, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (220, 220, 220), 1, cv2.LINE_AA)
    colors = ((80, 130, 255), (90, 225, 130), (245, 180, 65))
    labels = ("SOURCE", "REFERENCE", "MATCHED")
    datasets = (source_rgb, reference_rgb, matched_rgb)
    # Luma histograms.
    cv2.rectangle(canvas, (20, 50), (470, 295), (35, 39, 45), 1)
    cv2.putText(canvas, "LUMA DISTRIBUTION", (32, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 185, 190), 1, cv2.LINE_AA)
    for data, color in zip(datasets, colors):
        hist, _ = np.histogram(_luminance(data), bins=128, range=(0, 1), density=True)
        hist = hist / max(EPSILON, float(np.max(hist)))
        points = np.asarray([[24 + index * 3.43, 286 - value * 190] for index, value in enumerate(hist)], dtype=np.int32)
        cv2.polylines(canvas, [points], False, color, 2, cv2.LINE_AA)
    # RGB parade means across luminance bins.
    cv2.rectangle(canvas, (490, 50), (940, 295), (35, 39, 45), 1)
    cv2.putText(canvas, "RGB PARADE", (502, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 185, 190), 1, cv2.LINE_AA)
    matched = matched_rgb.reshape((-1, 3))
    for channel, color in enumerate(((65, 65, 245), (70, 220, 70), (245, 105, 55))):
        values = matched[:, channel]
        hist, _ = np.histogram(values, bins=128, range=(0, 1), density=True)
        hist = hist / max(EPSILON, float(np.max(hist)))
        offset = channel * 148
        points = np.asarray([[500 + offset + index * 1.1, 286 - value * 180] for index, value in enumerate(hist)], dtype=np.int32)
        cv2.polylines(canvas, [points], False, color, 2, cv2.LINE_AA)
    # Vectorscope scatter.
    center = (265, 450)
    cv2.circle(canvas, center, 130, (50, 55, 62), 1)
    cv2.line(canvas, (135, 450), (395, 450), (42, 46, 52), 1)
    cv2.line(canvas, (265, 320), (265, 580), (42, 46, 52), 1)
    for data, color in zip(datasets, colors):
        sample = data.reshape((-1, 3))[::max(1, data.size // 25000)]
        yuv = cv2.cvtColor(sample.reshape((-1, 1, 3)).astype(np.float32), cv2.COLOR_RGB2YUV).reshape((-1, 3))
        points = np.column_stack((center[0] + (yuv[:, 1] - 0.5) * 245, center[1] - (yuv[:, 2] - 0.5) * 245)).astype(np.int32)
        for point in points[::2]:
            if 130 <= point[0] < 400 and 315 <= point[1] < 585:
                cv2.circle(canvas, tuple(point), 1, color, -1)
    for index, (label, color) in enumerate(zip(labels, colors)):
        cv2.rectangle(canvas, (525, 355 + index * 54), (548, 378 + index * 54), color, -1)
        cv2.putText(canvas, label, (560, 374 + index * 54), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.imwrite(str(output), canvas)


def write_cube(recipe: dict[str, Any], output: Path, size: int = 33) -> None:
    size = max(17, min(65, int(size)))
    with output.open("w", encoding="ascii", newline="\n") as handle:
        handle.write('TITLE "TonyFX Reference Color Match"\n')
        handle.write(f"LUT_3D_SIZE {size}\n")
        handle.write("DOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        batch: list[list[float]] = []
        for blue in range(size):
            for green in range(size):
                for red in range(size):
                    batch.append([red / (size - 1), green / (size - 1), blue / (size - 1)])
                    if len(batch) >= 8192:
                        values = apply_recipe_rgb(np.asarray(batch, dtype=np.float32), recipe, include_face=False)
                        for value in values:
                            handle.write(f"{value[0]:.7f} {value[1]:.7f} {value[2]:.7f}\n")
                        batch = []
        if batch:
            values = apply_recipe_rgb(np.asarray(batch, dtype=np.float32), recipe, include_face=False)
            for value in values:
                handle.write(f"{value[0]:.7f} {value[1]:.7f} {value[2]:.7f}\n")


def render_with_lut(input_path: Path, output_path: Path, lut_path: Path, ffmpeg: str, start: float, duration: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_path = str(lut_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    command = [ffmpeg, "-y"]
    if start > 0:
        command += ["-ss", f"{start:.6f}"]
    command += ["-i", str(input_path)]
    if duration > 0:
        command += ["-t", f"{duration:.6f}"]
    command += ["-vf", f"lut3d=file='{filter_path}':interp=tetrahedral"]
    if output_path.suffix.lower() == ".mov":
        command += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le"]
    else:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k"]
    command += [str(output_path)]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError("FFmpeg color render failed: " + completed.stderr[-800:])


def render_spatial_match(
    input_path: Path,
    output_path: Path,
    recipe: dict[str, Any],
    face_model: Path | None,
    ffmpeg: str,
    start: float,
    duration: float,
    progress: Callable[[float, str], None] | None = None,
) -> None:
    metadata = _video_metadata(input_path)
    fps = float(metadata["fps"] or 30.0)
    width, height = int(metadata["width"]), int(metadata["height"])
    if width < 2 or height < 2:
        raise RuntimeError("Could not determine source dimensions for the precision render.")
    start = max(0.0, float(start))
    available = max(0.0, float(metadata["duration"]) - start)
    span = min(available, float(duration)) if duration > 0 else available
    if span <= 0:
        raise RuntimeError("The selected target range is empty.")
    frame_count = max(1, int(round(span * fps)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.8f}",
        "-i",
        "pipe:0",
    ]
    if start > 0:
        command += ["-ss", f"{start:.6f}"]
    command += ["-i", str(input_path), "-t", f"{span:.6f}", "-map", "0:v:0", "-map", "1:a:0?"]
    if output_path.suffix.lower() == ".mov":
        command += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le"]
    else:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k"]
    command += ["-shortest", str(output_path)]

    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags)
    capture = cv2.VideoCapture(str(input_path))
    capture.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
    written = 0
    try:
        while written < frame_count:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            faces = _detect_faces(frame, face_model)
            _weights, skin_mask = _frame_weights(frame, faces)
            matched_rgb = apply_recipe_rgb(_rgb_float(frame), recipe, skin_mask)
            matched_bgr = cv2.cvtColor((matched_rgb * 255.0 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)
            if process.stdin is None:
                raise RuntimeError("FFmpeg precision render input closed unexpectedly.")
            process.stdin.write(matched_bgr.tobytes())
            written += 1
            if progress and (written == 1 or written % max(1, frame_count // 20) == 0):
                progress(82.0 + 16.0 * written / frame_count, f"Precision matching frame {written}/{frame_count}")
    except BrokenPipeError as error:
        raise RuntimeError("FFmpeg stopped during the precision color render.") from error
    finally:
        capture.release()
        if process.stdin:
            process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code != 0 or written == 0 or not output_path.exists():
        raise RuntimeError("FFmpeg precision color render failed: " + stderr[-1200:])


def run_color_match(args: Any, *, emit: Callable[..., None], progress: Callable[[float, str], None], engine_root: Path, ffmpeg: str | None) -> None:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = Path(args.target).resolve()
    reference_path = Path(args.reference).resolve()
    face_model = engine_root / "models" / "analysis" / "face_detection_yunet_2023mar.onnx"
    progress(5, "Sampling target frames")
    target_frames, target_meta = read_media_samples(target_path, args.target_start, args.target_duration, args.samples)
    progress(16, "Sampling reference frames")
    reference_frames, reference_meta = read_media_samples(reference_path, args.reference_start, args.reference_duration, args.samples)
    progress(28, "Detecting subjects and measuring color")
    target_pixels = _collect_pixels(target_frames, face_model if face_model.exists() else None)
    reference_pixels = _collect_pixels(reference_frames, face_model if face_model.exists() else None)
    progress(42, "Solving tone and chroma transform")
    recipe = solve_recipe(target_pixels, reference_pixels, args.strength / 100.0, args.mode, args.match_tone, args.match_color, args.protect_skin)

    representative_target = target_frames[len(target_frames) // 2]
    representative_reference = reference_frames[len(reference_frames) // 2]
    target_rgb = _rgb_float(representative_target)
    _weights, target_face_mask = _frame_weights(representative_target, _detect_faces(representative_target, face_model if face_model.exists() else None))
    matched_rgb = apply_recipe_rgb(target_rgb, recipe, target_face_mask)
    matched_bgr = cv2.cvtColor((matched_rgb * 255.0 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)

    progress(58, "Writing comparison previews")
    source_preview = output_dir / "target.png"
    reference_preview = output_dir / "reference.png"
    matched_preview = output_dir / "matched.png"
    comparison_preview = output_dir / "comparison.png"
    scopes_preview = output_dir / "scopes.png"
    cv2.imwrite(str(source_preview), representative_target)
    cv2.imwrite(str(reference_preview), representative_reference)
    cv2.imwrite(str(matched_preview), matched_bgr)
    write_comparison(representative_target, representative_reference, matched_bgr, comparison_preview)

    matched_sample = apply_recipe_rgb(target_pixels["rgb"], recipe, include_face=False)
    write_scopes(target_pixels["rgb"], reference_pixels["rgb"], matched_sample, scopes_preview)
    before_error = _match_error(target_pixels["rgb"], target_pixels["weights"], reference_pixels)
    after_error = _match_error(matched_sample, target_pixels["weights"], reference_pixels)
    improvement = (before_error - after_error) / max(EPSILON, before_error) * 100.0
    safety = _safety_metrics(target_rgb, matched_rgb, target_face_mask)
    confidence = _clamp(38.0 + improvement * 0.36 + min(len(target_frames), len(reference_frames)) * 1.8, 0.0, 95.0)
    if target_pixels["faceRgb"].size and reference_pixels["faceRgb"].size:
        confidence = min(95.0, confidence + 4.0)
    if not safety["safe"]:
        confidence = min(confidence, 42.0)
    if improvement < 5.0:
        confidence = min(confidence, 35.0)

    progress(72, "Building precision 3D LUT")
    cube_path = output_dir / "TonyFX_Color_Match.cube"
    write_cube(recipe, cube_path, args.lut_size)
    recipe_path = output_dir / "color_match_recipe.json"
    result = {
        "ok": True,
        "target": str(target_path),
        "reference": str(reference_path),
        "targetMetadata": target_meta,
        "referenceMetadata": reference_meta,
        "previews": {
            "target": str(source_preview),
            "reference": str(reference_preview),
            "matched": str(matched_preview),
            "comparison": str(comparison_preview),
            "scopes": str(scopes_preview),
        },
        "lut": str(cube_path),
        "recipe": recipe,
        "recipePath": str(recipe_path),
        "safe": bool(safety["safe"]),
        "warnings": safety["warnings"],
        "safety": safety,
        "metrics": {
            "beforeError": round(before_error, 5),
            "afterError": round(after_error, 5),
            "improvementPercent": round(improvement, 2),
            "confidence": round(confidence, 1),
            "targetFaces": int(sum(len(item) for item in target_pixels["faces"])),
            "referenceFaces": int(sum(len(item) for item in reference_pixels["faces"])),
            "targetTemporalLumaSpread": round(float(np.std(target_pixels["perFrameLuma"])), 5),
            "referenceTemporalLumaSpread": round(float(np.std(reference_pixels["perFrameLuma"])), 5),
        },
    }
    recipe_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.render_output:
        if not safety["safe"]:
            raise RuntimeError("Color match was not rendered because safety validation failed: " + " ".join(safety["warnings"]))
        progress(82, "Rendering non-destructive matched media")
        render_output = Path(args.render_output).resolve()
        if target_path.suffix.lower() in IMAGE_SUFFIXES:
            cv2.imwrite(str(render_output), matched_bgr)
        else:
            if not ffmpeg:
                raise RuntimeError("FFmpeg is required to render matched video.")
            render_spatial_match(
                target_path,
                render_output,
                recipe,
                face_model if face_model.exists() else None,
                ffmpeg,
                args.target_start,
                args.target_duration,
                progress,
            )
        result["renderOutput"] = str(render_output)
        recipe_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    progress(100, "Color match complete")
    emit("result", **result)
