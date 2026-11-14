#!/usr/bin/env python3
"""Local vision services used by TonyFX reference forensics.

All heavyweight models are loaded lazily. The CEP panel can therefore probe the
installation instantly while semantic indexing, tracking, segmentation, and
depth inference only consume GPU memory during an analysis task.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np


Progress = Callable[[float, str], None]
VISION_ROOT = Path.home() / "Documents" / "TonyFX Vision Engine"
MODELS = VISION_ROOT / "models"
PACKAGES = VISION_ROOT / "packages"
MODEL_PATHS = {
    "sam2": MODELS / "sam2.1_hiera_small.pt",
    "cotracker": MODELS / "cotracker3_scaled_offline.pth",
    "depth": MODELS / "depth_anything_v2_vits.pth",
    "openclip": MODELS / "open_clip_vit_b32_laion2b.safetensors",
    "dinov2": MODELS / "dinov2_vits14_pretrain.pth",
    "yolo": MODELS / "yolo11n.pt",
}


def _emit_progress(callback: Progress | None, value: float, message: str) -> None:
    if callback:
        callback(value, message)


def _add_package(name: str) -> Path:
    path = PACKAGES / name
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return path


def probe() -> dict[str, Any]:
    modules = {}
    for name in ("torch", "open_clip", "faiss", "sam2", "cotracker", "ultralytics"):
        try:
            __import__(name)
            modules[name] = True
        except Exception:
            modules[name] = False
    models = {name: {"ready": path.exists(), "path": str(path), "bytes": path.stat().st_size if path.exists() else 0} for name, path in MODEL_PATHS.items()}
    cuda = False
    gpu = "CPU"
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        if cuda:
            gpu = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "ready": all(item["ready"] for item in models.values()),
        "cuda": cuda,
        "gpu": gpu,
        "root": str(VISION_ROOT),
        "models": models,
        "modules": modules,
        "capabilities": {
            "semanticSearch": models["openclip"]["ready"] and modules.get("faiss", False),
            "visualSimilarity": models["dinov2"]["ready"],
            "personDetection": models["yolo"]["ready"],
            "segmentation": models["sam2"]["ready"],
            "tracking": models["cotracker"]["ready"],
            "depth": models["depth"]["ready"],
            "normalization": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        },
    }


def _probe_media(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required for reference normalization.")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, creationflags=flags,
    )
    raw = json.loads(result.stdout or "{}")
    video = next((item for item in raw.get("streams", []) if item.get("codec_type") == "video"), {})
    def ratio(value: Any) -> float:
        try:
            a, b = str(value or "0/1").split("/", 1)
            return float(a) / max(float(b), 1e-9)
        except Exception:
            return 0.0
    duration = float((raw.get("format") or {}).get("duration") or video.get("duration") or 0)
    return {
        "duration": duration,
        "fps": ratio(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "nominalFps": ratio(video.get("r_frame_rate")),
        "frames": int(video.get("nb_frames") or 0),
        "startTime": float(video.get("start_time") or 0),
        "codec": str(video.get("codec_name") or ""),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
    }


def _opencv_decode_health(source: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Probe distributed frames because valid metadata can hide decoder failure."""
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        return {"healthy": False, "opened": False, "samples": 0, "readable": 0}
    duration = max(0.0, float(meta.get("duration") or 0))
    sample_times = np.linspace(0.0, max(0.0, duration - 0.04), 14) if duration > 0.2 else np.asarray([0.0])
    readable = 0
    for time_value in sample_times:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(time_value) * 1000.0)
        ok, frame = capture.read()
        if ok and frame is not None and frame.size:
            readable += 1
    capture.release()
    ratio = readable / max(1, len(sample_times))
    return {"healthy": ratio >= 0.86, "opened": True, "samples": len(sample_times), "readable": readable, "ratio": round(ratio, 4)}


def prepare_analysis_source(source: Path, output_dir: Path, progress: Progress | None = None, *, force_proxy: bool = False) -> tuple[Path, dict[str, Any]]:
    """Create a frame-accurate CFR proxy when timestamps or decoding are unreliable."""
    meta = _probe_media(source)
    expected = meta["duration"] * meta["fps"]
    frame_mismatch = bool(meta["frames"] and expected and abs(meta["frames"] - expected) / max(expected, 1) > 0.04)
    rate_mismatch = bool(meta["fps"] and meta["nominalFps"] and abs(meta["fps"] - meta["nominalFps"]) > 0.02)
    unusual_start = abs(meta["startTime"]) > 0.02
    decode_health = _opencv_decode_health(source, meta)
    needs_proxy = frame_mismatch or rate_mismatch or unusual_start or not decode_health["healthy"] or force_proxy
    evidence = {**meta, "normalized": needs_proxy, "reasons": [], "decodeHealth": decode_health}
    if frame_mismatch: evidence["reasons"].append("frame_count_mismatch")
    if rate_mismatch: evidence["reasons"].append("variable_frame_rate")
    if unusual_start: evidence["reasons"].append("nonzero_start_timestamp")
    if not decode_health["healthy"]: evidence["reasons"].append("unreliable_video_decoder")
    if force_proxy: evidence["reasons"].append("deep_analysis_cfr_proxy")
    if not needs_proxy:
        return source, evidence
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "reference-normalized-cfr.mp4"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return source, {**evidence, "normalized": False, "error": "ffmpeg_missing"}
    fps = max(1.0, min(120.0, meta["fps"] or meta["nominalFps"] or 30.0))
    _emit_progress(progress, 2, "Normalizing unreliable reference timestamps")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run([
        ffmpeg, "-y", "-fflags", "+genpts+discardcorrupt", "-err_detect", "ignore_err", "-i", str(source), "-map", "0:v:0", "-map", "0:a?",
        "-vf", f"fps={fps:.6f}", "-vsync", "cfr", "-c:v", "libx264", "-preset", "fast",
        "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", str(target),
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, creationflags=flags)

    # Corrupt social downloads can contain invalid packets after the last
    # displayable frame. FFmpeg may still write a complete repaired proxy while
    # returning code 69, so validate the proxy before declaring failure.
    proxy_meta: dict[str, Any] = {}
    try:
        if target.exists() and target.stat().st_size > 0:
            proxy_meta = _probe_media(target)
    except Exception:
        proxy_meta = {}
    minimum_duration = max(0.1, meta["duration"] * 0.90)
    proxy_complete = bool(
        proxy_meta.get("duration", 0) >= minimum_duration
        and proxy_meta.get("width", 0) > 0
        and proxy_meta.get("height", 0) > 0
        and (proxy_meta.get("frames", 0) > 0 or proxy_meta.get("fps", 0) > 0)
    )
    if completed.returncode != 0 and not proxy_complete:
        detail = (completed.stderr or "").strip()
        raise RuntimeError(f"Reference normalization failed ({completed.returncode}). {detail[-1000:]}")
    if completed.returncode != 0:
        evidence["reasons"].append("recoverable_decode_errors")
        evidence["normalizationWarning"] = "Damaged source packets were skipped after a complete CFR proxy was recovered."
        evidence["ffmpegExitCode"] = completed.returncode
    evidence["proxy"] = str(target)
    evidence["proxyMedia"] = proxy_meta
    return target, evidence


def _read_frame(path: Path, time_value: float) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_value) * 1000.0)
    ok, frame = capture.read()
    capture.release()
    return frame if ok else None


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


_MODEL_CACHE: dict[str, Any] = {}


def _openclip_bundle() -> tuple[Any, Any]:
    if "openclip" not in _MODEL_CACHE:
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained=str(MODEL_PATHS["openclip"]), device=_device()
        )
        model.eval()
        _MODEL_CACHE["openclip"] = (model, preprocess)
    return _MODEL_CACHE["openclip"]


def _dinov2_model() -> Any:
    if "dinov2" not in _MODEL_CACHE:
        _add_package("dinov2")
        import torch
        from dinov2.models.vision_transformer import vit_small
        model = vit_small(patch_size=14, img_size=518, init_values=1.0, block_chunks=0)
        model.load_state_dict(torch.load(MODEL_PATHS["dinov2"], map_location="cpu"))
        _MODEL_CACHE["dinov2"] = model.to(_device()).eval()
    return _MODEL_CACHE["dinov2"]


def encode_frame(frame: np.ndarray, include_dino: bool = True) -> np.ndarray:
    import torch
    from PIL import Image
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    clip_model, preprocess = _openclip_bundle()
    with torch.inference_mode():
        clip = clip_model.encode_image(preprocess(Image.fromarray(rgb)).unsqueeze(0).to(_device())).float()
        clip = torch.nn.functional.normalize(clip, dim=-1)
        parts = [clip]
        if include_dino and MODEL_PATHS["dinov2"].exists():
            resized = cv2.resize(rgb, (518, 518), interpolation=cv2.INTER_AREA)
            tensor = torch.from_numpy(resized).permute(2, 0, 1).float().div_(255.0)
            mean = torch.tensor([0.485, 0.456, 0.406])[:, None, None]
            std = torch.tensor([0.229, 0.224, 0.225])[:, None, None]
            tensor = ((tensor - mean) / std).unsqueeze(0).to(_device())
            dino = _dinov2_model()(tensor).float()
            dino = torch.nn.functional.normalize(dino, dim=-1)
            parts.append(dino)
        feature = torch.cat(parts, dim=-1)
        feature = torch.nn.functional.normalize(feature, dim=-1)
    return feature[0].cpu().numpy().astype(np.float32)


def candidate_motion_metadata(path: Path, time_value: float, range_start: float, range_duration: float) -> dict[str, Any]:
    """Measure whether a candidate moment is calm, moving, or peak-action footage."""
    range_end = max(range_start, range_start + max(0.04, range_duration))
    delta = min(0.18, max(0.06, range_duration * 0.035))
    before_time = max(range_start, min(range_end, time_value - delta))
    after_time = max(range_start, min(range_end, time_value + delta))
    center = _read_frame(path, time_value)
    before = _read_frame(path, before_time)
    after = _read_frame(path, after_time)
    if center is None:
        return {"available": False, "motionScore": 0.0}
    gray_center = cv2.cvtColor(cv2.resize(center, (256, 144), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    luma = float(gray_center.mean())
    contrast = float(gray_center.std())
    motion_score = 0.0
    flow_p90 = 0.0
    pixel_change = 0.0
    if before is not None and after is not None and after_time > before_time + 1e-5:
        gray_before = cv2.cvtColor(cv2.resize(before, (256, 144), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        gray_after = cv2.cvtColor(cv2.resize(after, (256, 144), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        pixel_change = float(np.mean(cv2.absdiff(gray_before, gray_after)))
        flow = cv2.calcOpticalFlowFarneback(gray_before, gray_after, None, 0.5, 3, 17, 3, 5, 1.1, 0)
        magnitudes = np.linalg.norm(flow, axis=2)
        flow_p90 = float(np.percentile(magnitudes, 90))
        motion_score = float(np.clip(0.48 * math.tanh(pixel_change / 24.0) + 0.52 * math.tanh(flow_p90 / 7.0), 0.0, 1.0))
    blurred = cv2.GaussianBlur(gray_center, (0, 0), 6.0)
    detail = cv2.absdiff(gray_center, blurred)
    threshold = max(10.0, float(np.percentile(detail, 84)))
    mask = np.uint8(detail >= threshold) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    subject_area = 0.0
    if contours:
        x, y, width, height = cv2.boundingRect(max(contours, key=cv2.contourArea))
        subject_area = float(width * height / max(1, gray_center.shape[0] * gray_center.shape[1]))
    shot_scale = "close_up" if subject_area >= 0.22 else ("medium" if subject_area >= 0.07 else "wide_or_detail")
    return {
        "available": True,
        "motionScore": round(motion_score, 4),
        "flowP90": round(flow_p90, 3),
        "pixelChange": round(pixel_change, 3),
        "luma": round(luma, 2),
        "contrast": round(contrast, 2),
        "subjectArea": round(subject_area, 4),
        "shotScale": shot_scale,
    }


def build_footage_index(catalog_path: Path, output_dir: Path, progress: Progress | None = None) -> dict[str, Any]:
    import faiss
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    items = catalog.get("items", catalog) if isinstance(catalog, dict) else catalog
    output_dir.mkdir(parents=True, exist_ok=True)
    vectors: list[np.ndarray] = []
    metadata: list[dict[str, Any]] = []
    valid = [item for item in items if item.get("path") and Path(item["path"]).exists()]
    for index, item in enumerate(valid):
        duration = max(0.04, float(item.get("sourceDuration") or item.get("duration") or 0))
        start = max(0.0, float(item.get("sourceStart") or 0))
        samples = 1 if duration < 0.7 else min(5, max(2, int(math.ceil(duration / 2.5))))
        for sample_index, offset in enumerate(np.linspace(0.08, 0.92, samples)):
            time_value = start + duration * float(offset)
            frame = _read_frame(Path(item["path"]), time_value)
            if frame is None:
                continue
            vectors.append(encode_frame(frame))
            metadata.append({
                "path": item["path"], "layerName": item.get("layerName") or item.get("name") or Path(item["path"]).name,
                "compName": item.get("compName", ""), "time": round(time_value, 4), "sourceStart": start,
                "sourceDuration": duration, "sample": sample_index, "catalogIndex": index,
                **candidate_motion_metadata(Path(item["path"]), time_value, start, duration),
            })
        _emit_progress(progress, 72 + 13 * (index + 1) / max(1, len(valid)), f"Indexing AE footage {index + 1}/{len(valid)}")
    if not vectors:
        return {"ready": False, "count": 0, "error": "No readable project footage was found."}
    matrix = np.vstack(vectors).astype(np.float32)
    faiss.normalize_L2(matrix)
    faiss_index = faiss.IndexFlatIP(matrix.shape[1])
    faiss_index.add(matrix)
    index_path = output_dir / "footage.faiss"
    meta_path = output_dir / "footage-metadata.json"
    faiss.write_index(faiss_index, str(index_path))
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ready": True, "count": len(metadata), "files": len(valid), "index": str(index_path), "metadata": str(meta_path), "dimensions": int(matrix.shape[1])}


def search_index(frame: np.ndarray, index_info: dict[str, Any], limit: int = 6, requirements: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    import faiss
    if not index_info.get("ready"):
        return []
    index = faiss.read_index(str(index_info["index"]))
    metadata = json.loads(Path(index_info["metadata"]).read_text(encoding="utf-8"))
    query = encode_frame(frame).reshape(1, -1).astype(np.float32)
    faiss.normalize_L2(query)
    scores, indices = index.search(query, min(max(1, limit * 5), len(metadata)))
    requirements = requirements or {}
    semantic = requirements.get("semantic") or requirements
    visual = semantic.get("visual") or {}
    target_motion = float(semantic.get("visualEnergyScore") if semantic.get("visualEnergyScore") is not None else semantic.get("energyScore") or 0.5)
    minimum_motion = float(semantic.get("minimumCandidateMotion") or 0.0)
    flashy = bool(semantic.get("flashyRequired"))
    target_luma = float(visual.get("luma") or 128.0)
    target_contrast = float(visual.get("contrast") or 48.0)
    target_scale = str(visual.get("shotScale") or "")
    results = []
    for score, index_value in zip(scores[0], indices[0]):
        if index_value < 0:
            continue
        item = dict(metadata[int(index_value)])
        embedding_score = float(np.clip((float(score) + 1.0) / 2.0, 0.0, 1.0))
        motion_score = float(item.get("motionScore") or 0.0)
        energy_fit = 1.0 - min(1.0, abs(motion_score - target_motion))
        luma_fit = 1.0 - min(1.0, abs(float(item.get("luma") or 128.0) - target_luma) / 150.0)
        contrast_fit = 1.0 - min(1.0, abs(float(item.get("contrast") or 48.0) - target_contrast) / 90.0)
        scale_fit = 1.0 if not target_scale or str(item.get("shotScale") or "") == target_scale else 0.45
        adjusted = embedding_score * 0.68 + energy_fit * 0.18 + luma_fit * 0.05 + contrast_fit * 0.04 + scale_fit * 0.05
        if flashy and motion_score < minimum_motion:
            adjusted -= min(0.34, (minimum_motion - motion_score) * 0.75 + 0.08)
        item["embeddingScore"] = round(embedding_score, 4)
        item["score"] = round(float(np.clip(adjusted, 0.0, 1.0)), 4)
        item["confidence"] = round(float(np.clip((adjusted - 0.30) / 0.62, 0.0, 1.0)), 3)
        item["selectionEvidence"] = {
            "targetMotion": round(target_motion, 4), "motionScore": round(motion_score, 4),
            "energyFit": round(energy_fit, 4), "lumaFit": round(luma_fit, 4),
            "contrastFit": round(contrast_fit, 4), "scaleFit": round(scale_fit, 4),
            "flashyRequirementPassed": not flashy or motion_score >= minimum_motion,
        }
        results.append(item)
    results.sort(key=lambda item: (float(item.get("score") or 0), float(item.get("motionScore") or 0) if flashy else float(item.get("embeddingScore") or 0)), reverse=True)
    unique, used = [], set()
    for item in results:
        identity = (item["path"], item.get("layerName"))
        if identity in used:
            continue
        used.add(identity)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _yolo_subject(frame: np.ndarray) -> dict[str, Any]:
    if not MODEL_PATHS["yolo"].exists():
        return {"detected": False}
    from ultralytics import YOLO
    if "yolo" not in _MODEL_CACHE:
        _MODEL_CACHE["yolo"] = YOLO(str(MODEL_PATHS["yolo"]))
    results = _MODEL_CACHE["yolo"].predict(frame, classes=[0], imgsz=640, conf=0.30, verbose=False, device=0 if _device() == "cuda" else "cpu")
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return {"detected": False}
    values = boxes.xyxy.detach().cpu().numpy()
    confidences = boxes.conf.detach().cpu().numpy()
    best = int(np.argmax((values[:, 2] - values[:, 0]) * (values[:, 3] - values[:, 1]) * confidences))
    x1, y1, x2, y2 = map(float, values[best])
    height, width = frame.shape[:2]
    center_x, center_y = (x1 + x2) / (2 * width), (y1 + y2) / (2 * height)
    return {
        "detected": True, "confidence": round(float(confidences[best]), 3),
        "box": [round(x1), round(y1), round(x2), round(y2)],
        "center": {"x": round(center_x, 3), "y": round(center_y, 3)},
        "area": round((x2 - x1) * (y2 - y1) / (width * height), 4),
        "safeFrameStatus": "safe" if 0.20 <= center_x <= 0.80 and 0.14 <= center_y <= 0.86 else "unsafe",
        "suggestedOffsetNormalized": {"x": round(0.5 - center_x, 3), "y": round(0.46 - center_y, 3)},
    }


def _depth_evidence(frame: np.ndarray, subject: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_PATHS["depth"].exists():
        return {"available": False}
    _add_package("Depth-Anything-V2")
    import torch
    from depth_anything_v2.dpt import DepthAnythingV2
    if "depth" not in _MODEL_CACHE:
        model = DepthAnythingV2(encoder="vits", features=64, out_channels=[48, 96, 192, 384])
        model.load_state_dict(torch.load(MODEL_PATHS["depth"], map_location="cpu"))
        _MODEL_CACHE["depth"] = model.to(_device()).eval()
    depth = _MODEL_CACHE["depth"].infer_image(frame)
    overall = float(np.median(depth))
    foreground = overall
    if subject.get("box"):
        x1, y1, x2, y2 = map(int, subject["box"])
        region = depth[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
        if region.size:
            foreground = float(np.median(region))
    spread = float(np.percentile(depth, 90) - np.percentile(depth, 10))
    return {"available": True, "subjectDepth": round(foreground, 4), "sceneDepth": round(overall, 4), "depthSpread": round(spread, 4), "separation": round(abs(foreground - overall) / max(spread, 1e-6), 4)}


def _segment_subject(frame: np.ndarray, subject: dict[str, Any]) -> dict[str, Any]:
    if not subject.get("box") or not MODEL_PATHS["sam2"].exists():
        return {"available": False}
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    if "sam2_predictor" not in _MODEL_CACHE:
        model = build_sam2("configs/sam2.1/sam2.1_hiera_s.yaml", str(MODEL_PATHS["sam2"]), device=_device())
        _MODEL_CACHE["sam2_predictor"] = SAM2ImagePredictor(model)
    predictor = _MODEL_CACHE["sam2_predictor"]
    predictor.set_image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=_device() == "cuda"):
        masks, scores, _ = predictor.predict(box=np.asarray(subject["box"], dtype=np.float32), multimask_output=False)
    mask = masks[0].astype(bool)
    ys, xs = np.where(mask)
    if not len(xs):
        return {"available": False}
    height, width = frame.shape[:2]
    return {
        "available": True, "confidence": round(float(scores[0]), 3), "coverage": round(float(mask.mean()), 4),
        "maskBox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "edgeRisk": bool(xs.min() <= width * 0.015 or xs.max() >= width * 0.985 or ys.min() <= height * 0.015 or ys.max() >= height * 0.985),
    }


def _tracking_evidence(source: Path, shot: dict[str, Any], fps: float) -> dict[str, Any]:
    if not MODEL_PATHS["cotracker"].exists() or int(shot.get("durationFrames") or 0) < 4:
        return {"available": False}
    import torch
    from cotracker.predictor import CoTrackerPredictor
    if "cotracker" not in _MODEL_CACHE:
        _MODEL_CACHE["cotracker"] = CoTrackerPredictor(checkpoint=str(MODEL_PATHS["cotracker"])).to(_device()).eval()
    start, end = float(shot.get("startTime") or 0), float(shot.get("endTime") or 0)
    count = min(24, max(6, int(shot.get("durationFrames") or 6)))
    frames = []
    for time_value in np.linspace(start, max(start, end - 1 / max(fps, 1)), count):
        frame = _read_frame(source, float(time_value))
        if frame is not None:
            frames.append(cv2.resize(frame, (384, 256), interpolation=cv2.INTER_AREA))
    if len(frames) < 4:
        return {"available": False}
    video = torch.from_numpy(np.asarray(frames)).permute(0, 3, 1, 2).float().unsqueeze(0).to(_device())
    with torch.inference_mode():
        tracks, visibility = _MODEL_CACHE["cotracker"](video, grid_size=10)
    track_values = tracks[0].detach().cpu().numpy()
    visible = visibility[0].detach().cpu().numpy().astype(bool)
    displacements = np.linalg.norm(track_values[-1] - track_values[0], axis=-1)
    return {
        "available": True, "samples": len(frames), "points": int(track_values.shape[1]),
        "visibleRatio": round(float(visible.mean()), 3), "medianTravelPx": round(float(np.median(displacements)), 3),
        "p90TravelPx": round(float(np.percentile(displacements, 90)), 3),
    }


def enrich_analysis(report: dict[str, Any], source: Path, output_dir: Path, catalog_path: Path | None = None, progress: Progress | None = None) -> dict[str, Any]:
    status = probe()
    report["visionEngine"] = {"version": 1, **status}
    index_info: dict[str, Any] = {"ready": False, "count": 0}
    if catalog_path and catalog_path.exists() and status["capabilities"]["semanticSearch"]:
        _emit_progress(progress, 70, "Building semantic AE footage index")
        index_info = build_footage_index(catalog_path, output_dir / "semantic-index", progress)
    report["footageIndex"] = index_info
    shots = report.get("shots", [])
    fps = float(report.get("media", {}).get("fps") or 30)
    summaries = []
    for shot_index, shot in enumerate(shots):
        middle = (float(shot.get("startTime") or 0) + float(shot.get("endTime") or 0)) / 2
        frame = _read_frame(source, middle)
        if frame is None:
            continue
        subject = _yolo_subject(frame)
        shot["visionSubject"] = subject
        if index_info.get("ready"):
            shot["footageMatches"] = search_index(frame, index_info, 8, shot)
            semantic = shot.get("semantic") or {}
            semantic["rankedProjectMatches"] = shot["footageMatches"]
            semantic["searchMethod"] = "OpenCLIP plus DINOv2 cosine similarity over AE project footage"
            shot["semantic"] = semantic
        if shot_index < 12:
            shot["depthEvidence"] = _depth_evidence(frame, subject)
        if shot_index < 6:
            shot["segmentationEvidence"] = _segment_subject(frame, subject)
        if shot_index < 8:
            shot["trackingEvidence"] = _tracking_evidence(source, shot, fps)
        summaries.append({"shot": shot.get("index", shot_index + 1), "subject": subject, "matches": shot.get("footageMatches", [])[:3]})
        _emit_progress(progress, 86 + 10 * (shot_index + 1) / max(1, len(shots)), f"Vision QA shot {shot_index + 1}/{len(shots)}")
    report["visionShotQA"] = summaries
    report["semanticShotRequirements"] = [shot.get("semantic") for shot in shots if shot.get("semantic")]
    report.setdefault("settings", {})["visionEngine"] = True
    report["settings"]["semanticFootageSearch"] = bool(index_info.get("ready"))
    return report


def _motion_signature(path: Path, start: float = 0.0, duration: float = 0.0, sample_count: int = 21) -> np.ndarray:
    capture = cv2.VideoCapture(str(path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30)
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    media_duration = total / max(fps, 1e-6)
    end = min(media_duration, start + duration) if duration > 0 else media_duration
    times = np.linspace(max(0.0, start), max(start, end - 1 / max(fps, 1)), sample_count)
    frames = []
    for time_value in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, float(time_value) * 1000)
        ok, frame = capture.read()
        if ok:
            frames.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (256, 144), interpolation=cv2.INTER_AREA))
    capture.release()
    if len(frames) < 3:
        return np.zeros((sample_count - 1, 6), dtype=np.float32)
    values = []
    for previous, current in zip(frames, frames[1:]):
        points = cv2.goodFeaturesToTrack(previous, 180, 0.01, 5)
        dx = dy = rotation = 0.0
        scale = 1.0
        if points is not None and len(points) >= 8:
            moved, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points, None)
            left = points[status.reshape(-1) == 1].reshape(-1, 2)
            right = moved[status.reshape(-1) == 1].reshape(-1, 2)
            if len(left) >= 8:
                matrix, _ = cv2.estimateAffinePartial2D(left, right, method=cv2.RANSAC)
                if matrix is not None:
                    dx, dy = float(matrix[0, 2]), float(matrix[1, 2])
                    scale = math.sqrt(float(matrix[0, 0] ** 2 + matrix[0, 1] ** 2))
                    rotation = math.atan2(float(matrix[1, 0]), float(matrix[0, 0]))
        luma = float(current.mean() - previous.mean()) / 64.0
        blur = math.log1p(float(cv2.Laplacian(current, cv2.CV_32F).var())) / 10.0
        values.append([dx / 40.0, dy / 40.0, math.log(max(scale, 1e-6)) / 0.18, rotation / 0.35, luma, blur])
    signature = np.asarray(values, dtype=np.float32)
    x = np.linspace(0, 1, len(signature)); target_x = np.linspace(0, 1, sample_count - 1)
    return np.stack([np.interp(target_x, x, signature[:, column]) for column in range(signature.shape[1])], axis=1).astype(np.float32)


def score_ae_candidates(reference: Path, event_time: float, duration_seconds: float, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    span = max(0.18, float(duration_seconds) * 2.4)
    reference_signature = _motion_signature(reference, max(0.0, event_time - span / 2), span)
    ranked = []
    scales = np.asarray([1.0, 1.0, 1.35, 0.75, 0.85, 0.35], dtype=np.float32)
    for candidate in candidates:
        path = Path(candidate["path"])
        signature = _motion_signature(path)
        error = float(np.mean(np.abs((signature - reference_signature) * scales)))
        temporal = float(np.mean([np.corrcoef(signature[:, column], reference_signature[:, column])[0, 1] if np.std(signature[:, column]) > 1e-5 and np.std(reference_signature[:, column]) > 1e-5 else 0.0 for column in range(signature.shape[1])]))
        score = float(np.clip(math.exp(-error * 1.8) * 0.72 + max(0.0, temporal) * 0.28, 0.0, 1.0))
        ranked.append({**candidate, "score": round(score, 4), "signatureError": round(error, 5), "temporalCorrelation": round(temporal, 4)})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"winner": ranked[0] if ranked else None, "candidates": ranked, "method": "real AE render motion-signature comparison", "referenceSpan": [round(max(0.0, event_time - span / 2), 4), round(event_time + span / 2, 4)]}
