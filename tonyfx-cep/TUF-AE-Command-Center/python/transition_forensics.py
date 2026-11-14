#!/usr/bin/env python3
"""Deep transition forensics for TonyFX.

The module intentionally treats a flattened reference as evidence, not source
metadata.  It decomposes short transition windows into measurable motion,
photometric, compositing, and depth signals and then ranks reproducible AE
stacks.  Heavy models are lazy and every backend has a deterministic OpenCV
fallback so Analyze never becomes unusable because one optional model failed.
"""

from __future__ import annotations

import json
import importlib.util
import math
import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


VISION_ROOT = Path.home() / "Documents" / "TonyFX Vision Engine"
PACKAGES = VISION_ROOT / "packages"
MODELS = VISION_ROOT / "models"
DNA_PATH = Path.home() / "Documents" / "TonyFX Local Engine" / "analysis" / "transition-dna.json"


def _add_package(name: str) -> Path:
    target = PACKAGES / name
    if target.exists() and str(target) not in sys.path:
        sys.path.insert(0, str(target))
    return target


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _normalize_frame(frame: np.ndarray, width: int = 384) -> np.ndarray:
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[1] > width:
        ratio = width / frame.shape[1]
        frame = cv2.resize(frame, (width, max(2, int(round(frame.shape[0] * ratio)))), interpolation=cv2.INTER_AREA)
    return frame


@lru_cache(maxsize=1)
def _torch_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@lru_cache(maxsize=1)
def _raft_model() -> tuple[Any, Any, str] | None:
    try:
        import torch
        from torchvision.models.optical_flow import Raft_Small_Weights, raft_small
        weights = Raft_Small_Weights.DEFAULT
        device = _torch_device()
        model = raft_small(weights=weights, progress=True).eval().to(device)
        return model, weights.transforms(), device
    except Exception:
        return None


@lru_cache(maxsize=1)
def _lightglue_models() -> tuple[Any, Any, str] | None:
    try:
        import torch
        _add_package("LightGlue")
        from lightglue import ALIKED, LightGlue
        device = _torch_device()
        # ALIKED is BSD licensed and avoids SuperPoint's restrictive weights.
        extractor = ALIKED(max_num_keypoints=1024).eval().to(device)
        matcher = LightGlue(features="aliked", depth_confidence=0.92, width_confidence=0.96).eval().to(device)
        return extractor, matcher, device
    except Exception:
        return None


@lru_cache(maxsize=1)
def _video_depth_model() -> tuple[Any, str] | None:
    checkpoint = MODELS / "video_depth_anything_vits.pth"
    package = _add_package("Video-Depth-Anything")
    if not checkpoint.exists() or not package.exists():
        return None
    try:
        import torch
        from video_depth_anything.video_depth import VideoDepthAnything
        device = _torch_device()
        model = VideoDepthAnything(encoder="vits", features=64, out_channels=[48, 96, 192, 384])
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model = model.eval().to(device)
        return model, device
    except Exception:
        return None


def probe() -> dict[str, Any]:
    transnet = PACKAGES / "TransNetV2" / "inference" / "transnetv2-weights" / "saved_model.pb"
    def available(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, AttributeError, ValueError):
            return False
    return {
        "ready": True,
        "device": _torch_device(),
        "raft": available("torchvision.models.optical_flow"),
        "lightGlue": available("lightglue") or (PACKAGES / "LightGlue").exists(),
        "transNetV2": transnet.exists(),
        "videoDepthAnything": (MODELS / "video_depth_anything_vits.pth").exists(),
        "transitionDNA": str(DNA_PATH),
    }


@lru_cache(maxsize=1)
def _transnet_model() -> Any | None:
    model_root = PACKAGES / "TransNetV2" / "inference"
    weights = model_root / "transnetv2-weights"
    if not weights.exists():
        return None
    try:
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        if str(model_root) not in sys.path:
            sys.path.insert(0, str(model_root))
        from transnetv2 import TransNetV2
        return TransNetV2(str(weights))
    except Exception:
        return None


def transnet_boundaries(frames: list[np.ndarray], threshold: float = 0.5) -> dict[str, Any]:
    """Return neural shot-boundary evidence using the official TransNetV2 model.

    TensorFlow is optional because it is a comparatively large dependency.  A
    missing runtime is reported explicitly and never blocks TonyFX's existing
    cut detector.
    """
    if not frames:
        return {"available": False, "frames": [], "reason": "TransNetV2 weights are unavailable"}
    try:
        model = _transnet_model()
        if model is None:
            return {"available": False, "frames": [], "reason": "TransNetV2 runtime is unavailable"}
        samples = []
        for frame in frames:
            normalized = _normalize_frame(frame, 160)
            samples.append(cv2.resize(normalized, (48, 27), interpolation=cv2.INTER_AREA))
        single, gradual = model.predict_frames(np.stack(samples).astype(np.uint8))
        probability = np.maximum(single, gradual)
        indices = np.where(probability >= float(threshold))[0].tolist()
        return {
            "available": True,
            "frames": indices,
            "scores": {str(index): round(float(probability[index]), 5) for index in indices},
            "threshold": threshold,
            "backend": "TransNetV2",
        }
    except Exception as error:
        return {"available": False, "frames": [], "reason": str(error)}


def _opencv_flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    left = cv2.cvtColor(_normalize_frame(a, 320), cv2.COLOR_BGR2GRAY)
    right = cv2.cvtColor(_normalize_frame(b, 320), cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(left, right, None, 0.5, 4, 21, 4, 7, 1.5, 0)


def _raft_flow(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, str]:
    backend = _raft_model()
    if backend is None:
        return _opencv_flow(a, b), "farneback"
    try:
        import torch
        model, transform, device = backend
        left, right = _normalize_frame(a, 384), _normalize_frame(b, 384)
        height = max(64, (left.shape[0] // 8) * 8)
        width = max(64, (left.shape[1] // 8) * 8)
        left = cv2.resize(left, (width, height), interpolation=cv2.INTER_AREA)
        right = cv2.resize(right, (width, height), interpolation=cv2.INTER_AREA)
        def tensor(frame: np.ndarray) -> Any:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float()
        first, second = transform(tensor(left), tensor(right))
        with torch.inference_mode(), torch.autocast(device_type="cuda", enabled=device == "cuda"):
            prediction = model(first.to(device), second.to(device))[-1][0]
        return prediction.detach().float().cpu().permute(1, 2, 0).numpy(), "raft-small"
    except Exception:
        return _opencv_flow(a, b), "farneback"


def _flow_features(flow: np.ndarray) -> dict[str, float]:
    x, y = flow[..., 0], flow[..., 1]
    magnitude = np.sqrt(x * x + y * y)
    median_x, median_y = float(np.median(x)), float(np.median(y))
    residual = np.sqrt((x - median_x) ** 2 + (y - median_y) ** 2)
    angles = np.arctan2(y, x)
    coherence = abs(np.mean(np.exp(1j * angles[magnitude > np.percentile(magnitude, 55)]))) if np.any(magnitude > np.percentile(magnitude, 55)) else 0.0
    return {
        "medianX": median_x,
        "medianY": median_y,
        "medianMagnitude": float(np.median(magnitude)),
        "p90Magnitude": float(np.percentile(magnitude, 90)),
        "p98Magnitude": float(np.percentile(magnitude, 98)),
        "residualP90": float(np.percentile(residual, 90)),
        "directionDegrees": float((math.degrees(math.atan2(median_y, median_x)) + 360.0) % 360.0),
        "coherence": float(coherence),
    }


def _opencv_homography(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray | None, int, float, str]:
    left = cv2.cvtColor(_normalize_frame(a, 480), cv2.COLOR_BGR2GRAY)
    right = cv2.cvtColor(_normalize_frame(b, 480), cv2.COLOR_BGR2GRAY)
    detector = cv2.SIFT_create(nfeatures=1600)
    ka, da = detector.detectAndCompute(left, None)
    kb, db = detector.detectAndCompute(right, None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return None, 0, 0.0, "sift"
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    good = [one for one, two in pairs if one.distance < 0.74 * two.distance]
    if len(good) < 8:
        return None, len(good), 0.0, "sift"
    pa = np.float32([ka[item.queryIdx].pt for item in good])
    pb = np.float32([kb[item.trainIdx].pt for item in good])
    matrix, mask = cv2.findHomography(pa, pb, cv2.USAC_MAGSAC, 2.5)
    ratio = float(mask.mean()) if mask is not None else 0.0
    return matrix, len(good), ratio, "sift"


def _lightglue_homography(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray | None, int, float, str]:
    backend = _lightglue_models()
    if backend is None:
        return _opencv_homography(a, b)
    try:
        import torch
        from lightglue.utils import rbd
        extractor, matcher, device = backend
        def tensor(frame: np.ndarray) -> Any:
            frame = _normalize_frame(frame, 640)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return torch.from_numpy(rgb).permute(2, 0, 1).float().div(255).to(device)
        with torch.inference_mode():
            fa = extractor.extract(tensor(a), resize=640)
            fb = extractor.extract(tensor(b), resize=640)
            matches = matcher({"image0": fa, "image1": fb})
        fa, fb, matches = [rbd(item) for item in (fa, fb, matches)]
        indices = matches["matches"].detach().cpu().numpy()
        if len(indices) < 8:
            return _opencv_homography(a, b)
        pa = fa["keypoints"][indices[:, 0]].detach().cpu().numpy().astype(np.float32)
        pb = fb["keypoints"][indices[:, 1]].detach().cpu().numpy().astype(np.float32)
        matrix, mask = cv2.findHomography(pa, pb, cv2.USAC_MAGSAC, 2.0)
        ratio = float(mask.mean()) if mask is not None else 0.0
        return matrix, len(indices), ratio, "lightglue-aliked"
    except Exception:
        return _opencv_homography(a, b)


def _decompose_homography(matrix: np.ndarray | None, width: int, height: int) -> dict[str, float]:
    if matrix is None or not np.all(np.isfinite(matrix)) or abs(matrix[2, 2]) < 1e-8:
        return {"x": 0.0, "y": 0.0, "scale": 1.0, "rotation": 0.0, "perspective": 0.0, "keystone": 0.0}
    h = matrix / matrix[2, 2]
    scale_x = math.hypot(float(h[0, 0]), float(h[1, 0]))
    scale_y = math.hypot(float(h[0, 1]), float(h[1, 1]))
    perspective = math.hypot(float(h[2, 0] * width), float(h[2, 1] * height))
    return {
        "x": float(h[0, 2]), "y": float(h[1, 2]),
        "scale": math.sqrt(max(1e-8, scale_x * scale_y)),
        "rotation": math.degrees(math.atan2(float(h[1, 0]), float(h[0, 0]))),
        "perspective": perspective,
        "keystone": abs(scale_x - scale_y),
    }


def _salient_centroid_translation(a: np.ndarray, b: np.ndarray) -> dict[str, float] | None:
    """Deterministic fallback for low-texture graphic/anime transition frames.

    SIFT can legitimately fail when a moving subject is surrounded by a flat
    field.  In that case, estimate the displacement of pixels that differ from
    their frame's border-color median.  This is deliberately marked as a
    fallback and is only trusted when both masks have useful, similar coverage.
    """
    normalized = [_normalize_frame(frame, 480) for frame in (a, b)]
    centers: list[tuple[float, float]] = []
    coverages: list[float] = []
    for frame in normalized:
        border = np.concatenate((frame[0], frame[-1], frame[:, 0], frame[:, -1]), axis=0).astype(np.float32)
        background = np.median(border, axis=0)
        distance = np.linalg.norm(frame.astype(np.float32) - background.reshape(1, 1, 3), axis=2)
        threshold = max(18.0, float(np.median(distance) + 2.5 * np.median(np.abs(distance - np.median(distance)))))
        mask = (distance >= threshold).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        coverage = float(mask.mean())
        moments = cv2.moments(mask)
        if moments["m00"] <= 0 or not 0.008 <= coverage <= 0.78:
            return None
        centers.append((float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])))
        coverages.append(coverage)
    if min(coverages) / max(max(coverages), 1e-6) < 0.55:
        return None
    return {"x": centers[1][0] - centers[0][0], "y": centers[1][1] - centers[0][1], "coverage": float(np.mean(coverages))}


def _blend_curve(frames: list[np.ndarray], before: np.ndarray, after: np.ndarray) -> tuple[list[float], float]:
    left = cv2.resize(before, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
    right = cv2.resize(after, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
    vector = (right - left).reshape(-1)
    denominator = float(np.dot(vector, vector)) + 1e-6
    values, errors = [], []
    for frame in frames:
        sample = cv2.resize(frame, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
        alpha = float(np.clip(np.dot((sample - left).reshape(-1), vector) / denominator, 0.0, 1.0))
        reconstruction = left * (1.0 - alpha) + right * alpha
        values.append(alpha)
        errors.append(float(np.mean(np.abs(sample - reconstruction))) / 255.0)
    confidence = float(np.clip(1.0 - np.median(errors) * 4.2, 0.0, 1.0))
    monotonic = float(np.mean(np.diff(values) >= -0.04)) if len(values) > 1 else 0.0
    return values, confidence * monotonic


def _wipe_signal(frames: list[np.ndarray], before: np.ndarray, after: np.ndarray) -> dict[str, float]:
    left = cv2.resize(before, (128, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
    right = cv2.resize(after, (128, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
    coverages, centroids = [], []
    for frame in frames:
        sample = cv2.resize(frame, (128, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
        mask = np.mean(np.abs(sample - right), axis=2) < np.mean(np.abs(sample - left), axis=2)
        coverages.append(float(mask.mean()))
        points = np.argwhere(mask)
        centroids.append((float(points[:, 1].mean() / 128), float(points[:, 0].mean() / 96)) if len(points) else (0.5, 0.5))
    coverage_span = max(coverages, default=0.0) - min(coverages, default=0.0)
    travel_x = max((item[0] for item in centroids), default=0.5) - min((item[0] for item in centroids), default=0.5)
    travel_y = max((item[1] for item in centroids), default=0.5) - min((item[1] for item in centroids), default=0.5)
    monotonic = max(float(np.mean(np.diff(coverages) >= -0.05)), float(np.mean(np.diff(coverages) <= 0.05))) if len(coverages) > 1 else 0.0
    return {"coverageSpan": coverage_span, "centroidTravelX": travel_x, "centroidTravelY": travel_y, "confidence": float(np.clip(coverage_span * monotonic, 0.0, 1.0))}


def _temporal_depth_signal(frames: list[np.ndarray], fps: float) -> dict[str, Any]:
    backend = _video_depth_model()
    if backend is None or len(frames) < 3:
        return {"available": False}
    try:
        import torch
        model, device = backend
        normalized = np.stack([cv2.cvtColor(_normalize_frame(frame, 308), cv2.COLOR_BGR2RGB) for frame in frames])
        depth, _ = model.infer_video_depth(normalized, target_fps=fps, input_size=308, device=device, fp32=False)
        center = depth[:, depth.shape[1] // 4:3 * depth.shape[1] // 4, depth.shape[2] // 4:3 * depth.shape[2] // 4]
        border = np.concatenate([depth[:, :depth.shape[1] // 5].reshape(len(depth), -1), depth[:, -depth.shape[1] // 5:].reshape(len(depth), -1)], axis=1)
        separation = np.median(center, axis=(1, 2)) - np.median(border, axis=1)
        temporal = float(np.median(np.abs(np.diff(depth, axis=0))))
        result = {"available": True, "foregroundBackgroundSeparation": float(np.median(np.abs(separation))), "temporalChange": temporal}
        del depth
        if device == "cuda":
            torch.cuda.empty_cache()
        return result
    except Exception as error:
        return {"available": False, "error": str(error)}


def _dna_vector(data: dict[str, Any]) -> list[float]:
    transform = data.get("transform", {})
    flow = data.get("flow", {})
    photo = data.get("photometric", {})
    return [
        _finite(transform.get("travelPx")) / 1000.0,
        abs(math.log(max(1e-5, _finite(transform.get("scaleRatio"), 1.0)))),
        abs(_finite(transform.get("rotationDegrees", transform.get("rotation")))) / 45.0,
        _finite(transform.get("perspective")) / 0.5,
        _finite(flow.get("coherence")),
        _finite(flow.get("residualP90")) / 30.0,
        _finite(photo.get("blackPeak")),
        _finite(photo.get("whitePeak")),
        _finite(data.get("blendConfidence")),
        _finite(data.get("wipe", {}).get("confidence")),
        _finite(data.get("shake", {}).get("amplitudePx")) / 30.0,
    ]


DEFAULT_DNA = [
    {"name": "hard_cut", "vector": [0, 0, 0, 0, .1, .8, 0, 0, 0, 0, 0]},
    {"name": "crossfade", "vector": [0, 0, 0, 0, .1, .3, 0, 0, .9, 0, 0]},
    {"name": "black_dip", "vector": [0, 0, 0, 0, .1, .2, .9, 0, .2, 0, 0]},
    {"name": "white_flash", "vector": [0, 0, 0, 0, .1, .2, 0, .9, .2, 0, 0]},
    {"name": "whip", "vector": [.8, .03, .05, .02, .9, .35, 0, 0, .1, 0, .15]},
    {"name": "slide", "vector": [.55, .02, .02, .02, .8, .18, 0, 0, .1, 0, .05]},
    {"name": "zoom_blur", "vector": [.08, .35, .02, .02, .55, .4, 0, .05, .1, 0, .1]},
    {"name": "spin_zoom", "vector": [.12, .25, .8, .1, .6, .45, 0, .05, .1, 0, .15]},
    {"name": "perspective_push", "vector": [.25, .12, .18, .8, .65, .35, 0, 0, .1, 0, .1]},
    {"name": "mask_wipe", "vector": [.15, .03, .02, .05, .45, .3, 0, 0, .2, .9, .05]},
    {"name": "impact_shake", "vector": [.08, .03, .08, .05, .3, .8, 0, .05, .1, 0, .85]},
]


def load_dna(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DNA_PATH
    entries = list(DEFAULT_DNA)
    if target.exists():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            entries.extend(item for item in payload.get("entries", []) if isinstance(item.get("vector"), list))
        except Exception:
            pass
    return entries


def match_dna(data: dict[str, Any], path: Path | None = None) -> list[dict[str, Any]]:
    vector = np.asarray(_dna_vector(data), dtype=np.float32)
    results = []
    for entry in load_dna(path):
        candidate = np.asarray(entry["vector"], dtype=np.float32)
        if candidate.shape != vector.shape:
            continue
        distance = float(np.sqrt(np.mean((np.clip(vector, 0, 2) - np.clip(candidate, 0, 2)) ** 2)))
        results.append({"family": entry["name"], "score": round(float(math.exp(-2.4 * distance)), 4), "source": entry.get("source", "TonyFX baseline")})
    return sorted(results, key=lambda item: item["score"], reverse=True)[:5]


def save_approved_dna(data: dict[str, Any], family: str, source: str, path: Path | None = None) -> Path:
    target = path or DNA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "entries": []}
    if target.exists():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            pass
    payload.setdefault("entries", []).append({"name": family, "source": source, "vector": _dna_vector(data)})
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def ae_recipe(data: dict[str, Any], families: Iterable[str]) -> list[dict[str, Any]]:
    recipe: list[dict[str, Any]] = []
    duration = int(data.get("durationFrames", 5))
    for family in families:
        if family.startswith(("whip_", "slide_")) or family in {"whip", "slide"}:
            direction = data.get("direction", "right")
            recipe.extend([
                {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}, "order": "below Lumetri"},
                {"property": "Position", "settings": {"direction": direction, "distancePx": round(data["transform"]["travelPx"], 1), "frames": duration}},
                {"effect": "Directional Blur", "settings": {"Direction": round(data["flow"]["directionDegrees"], 1), "Blur Length": round(max(35.0, data["flow"]["p90Magnitude"] * 6), 1), "frames": duration}},
            ])
        elif family in {"zoom", "zoom_blur"}:
            recipe.extend([
                {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}, "order": "below Lumetri"},
                {"effect": "BlurMoCurves", "settings": {"Zoom Ratio": round(data["transform"]["scaleRatio"], 4), "frames": duration}},
                {"effect": "Radial Blur", "settings": {"Type": "Zoom", "Amount": round(max(20.0, data["flow"]["residualP90"] * 3.5), 1)}},
            ])
        elif family == "spin_zoom":
            rotation = data["transform"].get("rotationDegrees", data["transform"].get("rotation", 0.0))
            recipe.extend([{"property": "Rotation", "settings": {"degrees": round(rotation, 2)}}, {"property": "Scale", "settings": {"ratio": round(data["transform"]["scaleRatio"], 4)}}, {"effect": "CC Force Motion Blur", "settings": {"Shutter Angle": 180}}])
        elif family == "perspective_push":
            recipe.extend([{"effect": "Corner Pin", "settings": {"perspective": round(data["transform"]["perspective"], 4)}}, {"effect": "Motion Tile", "settings": {"Output Width": 200, "Output Height": 200, "Mirror Edges": True}}])
        elif family == "mask_wipe":
            recipe.append({"property": "Animated Mask", "settings": {"direction": data.get("wipeDirection", "horizontal"), "feather": round(max(4.0, data["flow"]["residualP90"]), 1), "frames": duration}})
        elif family == "impact_shake":
            recipe.append({"property": "Position", "settings": {"impactShakePx": round(data["shake"]["amplitudePx"], 1), "frames": duration, "settle": True}})
    unique, seen = [], set()
    for item in recipe:
        key = str(item.get("effect") or item.get("property"))
        if key not in seen:
            seen.add(key); unique.append(item)
    return unique


def decompose_transition(
    frames: list[np.ndarray],
    event: dict[str, Any],
    fps: float,
    metrics: list[dict[str, float]],
    *,
    use_deep_flow: bool = True,
    use_temporal_depth: bool = False,
    dna_path: Path | None = None,
) -> dict[str, Any]:
    if not frames:
        return {"available": False, "reason": "No decoded frames"}
    start = max(0, int(event.get("startFrame", event.get("frame", 0))) - 2)
    end = min(len(frames) - 1, int(event.get("endFrame", event.get("frame", 0))) + 2)
    stable = event.get("stableFrames") or [start, end]
    before_index = max(0, min(len(frames) - 1, int(stable[0])))
    after_index = max(0, min(len(frames) - 1, int(stable[-1])))
    window = [_normalize_frame(frames[index], 384) for index in range(start, end + 1)]
    pair_features, backend_names = [], []
    for index in range(len(window) - 1):
        flow, backend = _raft_flow(window[index], window[index + 1]) if use_deep_flow else (_opencv_flow(window[index], window[index + 1]), "farneback")
        pair_features.append(_flow_features(flow)); backend_names.append(backend)
    matrix, matches, inlier_ratio, matcher_backend = _lightglue_homography(frames[before_index], frames[after_index])
    transform = _decompose_homography(matrix, frames[before_index].shape[1], frames[before_index].shape[0])
    transform_valid = bool(
        matrix is not None
        and matches >= 8
        and inlier_ratio >= 0.5
        and 0.45 <= transform.get("scale", 1.0) <= 2.2
        and abs(transform.get("perspective", 0.0)) <= 0.35
        and abs(transform.get("keystone", 0.0)) <= 0.25
    )
    if not transform_valid:
        fallback_translation = _salient_centroid_translation(frames[before_index], frames[after_index])
        if fallback_translation is not None:
            transform["x"] = fallback_translation["x"]
            transform["y"] = fallback_translation["y"]
            matches = max(matches, 1)
            inlier_ratio = max(inlier_ratio, 0.56)
            matcher_backend += "+salient-centroid"
            transform_valid = True
    transform["travelPx"] = math.hypot(transform["x"], transform["y"])
    transform["scaleRatio"] = transform.pop("scale")
    transform["rotationDegrees"] = transform.get("rotation", 0.0)
    median_flow = {key: float(np.median([item[key] for item in pair_features])) if pair_features else 0.0 for key in ("medianX", "medianY", "medianMagnitude", "p90Magnitude", "p98Magnitude", "residualP90", "directionDegrees", "coherence")}
    trajectory = np.asarray([[item["medianX"], item["medianY"]] for item in pair_features], dtype=np.float32)
    acceleration = np.diff(trajectory, axis=0) if len(trajectory) > 1 else np.zeros((1, 2), np.float32)
    shake_amplitude = float(np.percentile(np.linalg.norm(acceleration, axis=1), 90)) if len(acceleration) else 0.0
    blend, blend_confidence = _blend_curve(window, frames[before_index], frames[after_index])
    wipe = _wipe_signal(window, frames[before_index], frames[after_index])
    local_metrics = metrics[start:end + 1]
    photo = {
        "lumaCurve": [round(_finite(item.get("luma")), 3) for item in local_metrics],
        "blackPeak": max((_finite(item.get("black")) for item in local_metrics), default=0.0),
        "whitePeak": max((_finite(item.get("white")) for item in local_metrics), default=0.0),
        "sharpnessCurve": [round(_finite(item.get("sharp")), 3) for item in local_metrics],
    }
    result: dict[str, Any] = {
        "available": True,
        "frameRange": [start, end], "durationFrames": end - start + 1,
        "backends": {"flow": max(set(backend_names), key=backend_names.count) if backend_names else "none", "matcher": matcher_backend},
        "flow": {key: round(value, 4) for key, value in median_flow.items()},
        "flowTrajectory": [{"x": round(item["medianX"], 3), "y": round(item["medianY"], 3), "p90": round(item["p90Magnitude"], 3)} for item in pair_features],
        "transform": {key: round(value, 5) for key, value in transform.items()},
        "homography": {"matches": matches, "inlierRatio": round(inlier_ratio, 4), "valid": transform_valid, "matrix": matrix.tolist() if matrix is not None else None},
        "blendCurve": [round(value, 4) for value in blend], "blendConfidence": round(blend_confidence, 4),
        "wipe": {key: round(value, 4) for key, value in wipe.items()},
        "shake": {"amplitudePx": round(shake_amplitude, 4), "trajectory": trajectory.round(3).tolist()},
        "photometric": photo,
    }
    if use_temporal_depth:
        result["temporalDepth"] = _temporal_depth_signal(window, fps)
    candidates = match_dna(result, dna_path)
    result["dnaVector"] = [round(value, 6) for value in _dna_vector(result)]
    measured: list[str] = []
    hints = set(event.get("componentFamilies") or [])
    if event.get("family"):
        hints.add(event["family"])
    rendered_winner = (event.get("renderedCandidates") or {}).get("winner")
    fingerprint_winner = (event.get("effectFingerprint") or {}).get("winner")
    if rendered_winner:
        hints.add(rendered_winner)
    if fingerprint_winner:
        hints.add(fingerprint_winner)
    x, y = transform["x"], transform["y"]
    if transform_valid and transform["travelPx"] > max(18.0, frames[before_index].shape[1] * 0.045) and (median_flow["coherence"] > 0.44 or "salient-centroid" in matcher_backend):
        direction = "right" if abs(x) >= abs(y) and x > 0 else "left" if abs(x) >= abs(y) else "down" if y > 0 else "up"
        result["direction"] = direction
        measured.append(("whip_" if median_flow["p90Magnitude"] > 12 else "slide_") + direction)
    if transform_valid and abs(math.log(max(1e-6, transform["scaleRatio"]))) > 0.055:
        measured.append("zoom_blur" if median_flow["residualP90"] > 3 else "zoom")
    if transform_valid and abs(transform["rotation"]) > 3.0:
        measured.append("spin_zoom")
    if transform_valid and (transform["perspective"] > 0.09 or transform["keystone"] > 0.08):
        measured.append("perspective_push")
    intermediate_blend_frames = sum(1 for value in blend if 0.1 < value < 0.9)
    crossfade_measured = blend_confidence > 0.74 and intermediate_blend_frames >= 3 and transform["travelPx"] < frames[before_index].shape[1] * 0.09 and photo["blackPeak"] < 0.48 and photo["whitePeak"] < 0.48
    if ("crossfade" in hints and blend_confidence > 0.62 and intermediate_blend_frames >= 2) or crossfade_measured:
        measured.append("crossfade")
    wipe_travel = max(wipe["centroidTravelX"], wipe["centroidTravelY"])
    wipe_measured = wipe["confidence"] > 0.70 and wipe_travel > 0.16 and intermediate_blend_frames >= 2
    if ("mask_wipe" in hints and wipe["confidence"] > 0.55 and wipe_travel > 0.1 and intermediate_blend_frames >= 1) or wipe_measured:
        measured.append("mask_wipe")
        result["wipeDirection"] = "horizontal" if wipe["centroidTravelX"] >= wipe["centroidTravelY"] else "vertical"
    if ("impact_shake" in hints or transform_valid) and shake_amplitude > 4.0 and transform["travelPx"] < frames[before_index].shape[1] * 0.18:
        measured.append("impact_shake")
    if photo["blackPeak"] > 0.55:
        measured.append("black_dip")
    if photo["whitePeak"] > 0.55:
        measured.append("white_flash")
    result["measuredFamilies"] = list(dict.fromkeys(measured))
    result["dnaMatches"] = candidates
    result["aeRecipe"] = ae_recipe(result, result["measuredFamilies"])
    result["confidence"] = round(float(np.clip(max([item["score"] for item in candidates[:1]] + [0.35]) * (0.7 + 0.3 * max(inlier_ratio, median_flow["coherence"])), 0.0, 0.99)), 4)
    return result


def enrich_events(
    frames: list[np.ndarray],
    events: list[dict[str, Any]],
    fps: float,
    metrics: list[dict[str, float]],
    *,
    accuracy: str = "balanced",
    deep_flow: bool = False,
    dna_path: Path | None = None,
) -> dict[str, Any]:
    deep = deep_flow or accuracy == "deep"
    depth_budget = 2 if accuracy == "deep" and deep_flow else 0
    for index, event in enumerate(events):
        evidence = decompose_transition(frames, event, fps, metrics, use_deep_flow=deep, use_temporal_depth=index < depth_budget, dna_path=dna_path)
        event["forensics"] = evidence
        if not evidence.get("available"):
            continue
        measured = evidence.get("measuredFamilies") or []
        existing = list(event.get("componentFamilies") or [])
        strong = evidence.get("confidence", 0) >= 0.58
        for family in measured:
            if family not in existing and (strong or family in {"black_dip", "white_flash"}):
                existing.append(family)
        event["componentFamilies"] = existing
        if strong and measured and event.get("family") in {"hard_cut", "effect_pulse", "directional_smear"}:
            event["family"] = measured[0]
        if strong:
            event["aeRecipe"] = _dedupe_recipe(list(event.get("aeRecipe") or []) + list(evidence.get("aeRecipe") or []))
        event["candidateScores"] = _merge_candidates(event.get("candidateScores") or [], evidence.get("dnaMatches") or [])
    return {"probe": probe(), "eventCount": len(events), "deepFlow": deep, "temporalDepthEvents": min(depth_budget, len(events)), "dnaPath": str(dna_path or DNA_PATH)}


def _dedupe_recipe(recipe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result, seen = [], set()
    for item in recipe:
        identity = json.dumps([item.get("effect"), item.get("property"), item.get("transition"), item.get("layer")], sort_keys=True)
        if identity not in seen:
            seen.add(identity); result.append(item)
    return result


def _merge_candidates(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for item in list(first) + list(second):
        family = str(item.get("family") or "")
        if not family:
            continue
        if family not in scores or _finite(item.get("score")) > _finite(scores[family].get("score")):
            scores[family] = dict(item)
    return sorted(scores.values(), key=lambda item: _finite(item.get("score")), reverse=True)[:8]
