#!/usr/bin/env python3
"""TonyFX local media engine.

The worker intentionally keeps heavyweight AI imports lazy. TonyFX can therefore
open quickly while enhancement, separation, and generation run in a child process.
Every command emits newline-delimited JSON so the CEP panel can show deterministic
progress and import the finished media back into After Effects.
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import inspect
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".m2ts"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}


def emit(kind: str, **payload: Any) -> None:
    data = {"type": kind, **payload}
    print(json.dumps(data, ensure_ascii=False), flush=True)


def progress(percent: float, message: str) -> None:
    value = max(0, min(100, int(round(percent))))
    emit("progress", percent=value, message=message)
    print(f"PROGRESS {value}", flush=True)


def fail(message: str, code: int = 2) -> None:
    emit("error", message=message)
    raise SystemExit(code)


def engine_root(value: str | None = None) -> Path:
    configured = value or os.environ.get("TONYFX_ENGINE_ROOT")
    root = Path(configured) if configured else Path.home() / "Documents" / "TonyFX Local Engine"
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_executable(name: str, root: Path) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct
    matches = list(root.rglob(name))
    return str(matches[0]) if matches else None


def module_ready(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def run(command: Iterable[str], *, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command_list = [str(item) for item in command]
    return subprocess.run(
        command_list,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def format_eta(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        return "calculating ETA"
    rounded = max(0, int(round(seconds)))
    minutes, remainder = divmod(rounded, 60)
    if minutes:
        return f"ETA {minutes}m {remainder:02d}s"
    return f"ETA {remainder}s"


def run_frame_process(
    command: Iterable[str],
    output_directory: Path,
    expected_frames: int,
    start_percent: float,
    end_percent: float,
    label: str,
    *,
    cwd: Path | None = None,
) -> None:
    command_list = [str(item) for item in command]
    expected = max(1, int(expected_frames))
    started = time.monotonic()
    last_count = -1
    last_update = 0.0
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
        child = subprocess.Popen(
            command_list,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        while child.poll() is None:
            count = len(list(output_directory.glob("*.png")))
            elapsed = max(0.001, time.monotonic() - started)
            if count != last_count or elapsed - last_update >= 8.0:
                ratio = min(1.0, count / expected)
                rate = count / elapsed
                eta = (expected - count) / rate if rate > 0 else math.inf
                progress(start_percent + (end_percent - start_percent) * ratio, f"{label} {count}/{expected} frames - {format_eta(eta)}")
                last_count = count
                last_update = elapsed
            time.sleep(0.75)
        if child.returncode != 0:
            log.seek(0)
            details = log.read()[-2000:].strip()
            raise subprocess.CalledProcessError(child.returncode, command_list, output=details)
    progress(end_percent, f"{label} {expected}/{expected} frames complete")


def ffprobe(path: Path) -> dict[str, Any]:
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        fail("FFprobe was not found. Install FFmpeg or set it on PATH.")
    result = run(
        [ffprobe_bin, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture=True,
    )
    data = json.loads(result.stdout or "{}")
    video = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), None)
    audio = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), None)
    duration = float((data.get("format") or {}).get("duration") or 0)
    fps = 0.0
    if video:
        raw_fps = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        numerator, denominator = (raw_fps.split("/") + ["1"])[:2]
        try:
            fps = float(numerator) / max(1.0, float(denominator))
        except ValueError:
            fps = 0.0
    return {
        "duration": duration,
        "video": video,
        "audio": audio,
        "width": int((video or {}).get("width") or 0),
        "height": int((video or {}).get("height") or 0),
        "fps": fps,
    }


def gpu_info() -> dict[str, Any]:
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return {"available": False, "name": "No NVIDIA GPU detected", "memoryMb": 0}
    try:
        result = run(
            [nvidia, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture=True,
        )
        line = (result.stdout or "").strip().splitlines()[0]
        name, total, free = [item.strip() for item in line.split(",", 2)]
        return {"available": True, "name": name, "memoryMb": int(total), "freeMemoryMb": int(free)}
    except Exception:
        return {"available": False, "name": "GPU query failed", "memoryMb": 0}


def probe(args: argparse.Namespace) -> None:
    root = engine_root(args.engine_root)
    ffmpeg_bin = shutil.which("ffmpeg")
    real_esrgan = resolve_executable("realesrgan-ncnn-vulkan.exe", root)
    rife = resolve_executable("rife-ncnn-vulkan.exe", root)
    vision = {}
    try:
        from vision_engine import probe as probe_vision
        vision = probe_vision()
    except Exception as error:
        vision = {"ready": False, "error": str(error)}
    try:
        from transition_forensics import probe as probe_forensics
        forensics = probe_forensics()
    except Exception as error:
        forensics = {"ready": False, "error": str(error)}
    payload = {
        "ok": True,
        "engineRoot": str(root),
        "ffmpeg": bool(ffmpeg_bin),
        "realEsrgan": bool(real_esrgan),
        "rife": bool(rife),
        "torch": module_ready("torch"),
        "demucs": module_ready("demucs"),
        "deepFilterNet": module_ready("df"),
        "diffusers": module_ready("diffusers"),
        "transformers": module_ready("transformers"),
        "referenceAnalyzer": all(module_ready(name) for name in ("cv2", "numpy", "librosa", "skimage")),
        "visionEngine": vision,
        "transitionForensics": forensics,
        "gpu": gpu_info(),
        "models": {
            "image": (root / "models" / "image").exists(),
            "video": (root / "models" / "video").exists(),
            "audio": (root / "models" / "audio").exists(),
        },
    }
    emit("result", **payload)


def target_size(meta: dict[str, Any], args: argparse.Namespace) -> tuple[int, int]:
    source_w = max(1, int(meta.get("width") or 1080))
    source_h = max(1, int(meta.get("height") or 1080))
    width = int(args.width or 0)
    height = int(args.height or 0)
    scale = max(1.0, float(args.scale or 1.0))
    if width and height:
        return width - width % 2, height - height % 2
    return int(source_w * scale) // 2 * 2, int(source_h * scale) // 2 * 2


def enhancement_filters(args: argparse.Namespace, width: int, height: int, *, interpolation: bool) -> str:
    denoise = max(0.0, min(100.0, float(args.denoise)))
    detail = max(0.0, min(100.0, float(args.detail)))
    sharpen = max(0.0, min(100.0, float(args.sharpen)))
    dehalo = max(0.0, min(100.0, float(args.dehalo)))
    deblur = max(0.0, min(100.0, float(args.deblur)))
    compression = max(0.0, min(100.0, float(args.compression)))
    grain = max(0.0, min(100.0, float(args.grain)))
    filters: list[str] = []
    if denoise > 0 or compression > 0:
        spatial = 0.6 + denoise * 0.035 + compression * 0.018
        temporal = 0.8 + denoise * 0.026
        filters.append(f"hqdn3d={spatial:.2f}:{spatial * 0.78:.2f}:{temporal:.2f}:{temporal * 0.72:.2f}")
    if compression > 8:
        threshold = 0.004 + compression * 0.00012
        filters.append(f"deband=1thr={threshold:.4f}:2thr={threshold:.4f}:3thr={threshold:.4f}:range=16:blur=1")
    if dehalo > 0:
        # A gentle negative edge pass suppresses halos without inventing texture.
        filters.append(f"unsharp=7:7:{-(dehalo / 260.0):.3f}:7:7:0")
    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos")
    filters.append(f"crop={width}:{height}")
    unsharp_amount = 0.15 + detail / 120.0 + sharpen / 85.0 + deblur / 170.0
    if unsharp_amount > 0.18:
        filters.append(f"unsharp=5:5:{min(2.25, unsharp_amount):.3f}:5:5:0")
    if interpolation and float(args.target_fps or 0) > 0:
        fps = max(12.0, min(120.0, float(args.target_fps)))
        filters.append(f"minterpolate=fps={fps:.3f}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    if grain > 0:
        filters.append(f"noise=alls={min(18.0, grain / 5.0):.2f}:allf=t")
    return ",".join(filters)


def enhance_with_ffmpeg(source: Path, output: Path, meta: dict[str, Any], args: argparse.Namespace) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail("FFmpeg was not found. Install FFmpeg before running Local Enhance.")
    width, height = target_size(meta, args)
    is_image = source.suffix.lower() in IMAGE_SUFFIXES
    filters = enhancement_filters(args, width, height, interpolation=not is_image and args.interpolate)
    command = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
    if float(args.start or 0) > 0:
        command += ["-ss", f"{float(args.start):.6f}"]
    if float(args.duration or 0) > 0:
        command += ["-t", f"{float(args.duration):.6f}"]
    command += ["-i", str(source), "-vf", filters]
    if is_image:
        command += ["-frames:v", "1", str(output)]
    else:
        if args.codec == "h264":
            command += ["-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(output)]
        else:
            command += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s24le", "-ar", "48000", str(output)]
    progress(18, "Restoring detail and scaling with the local quality pipeline")
    run(command)


def validate_frame_sequence(input_frames: Path, output_frames: Path, expected: int, scale: int) -> tuple[bool, str]:
    inputs = sorted(input_frames.glob("*.png"))
    outputs = sorted(output_frames.glob("*.png"))
    if len(outputs) != expected:
        return False, f"Real-ESRGAN returned {len(outputs)}/{expected} frames"
    try:
        import cv2
        import numpy as np
    except Exception:
        return True, "frame count verified"
    sample_indices = sorted(set((0, len(inputs) // 2, len(inputs) - 1)))
    scores: list[float] = []
    for index in sample_indices:
        before = cv2.imread(str(inputs[index]), cv2.IMREAD_COLOR)
        after = cv2.imread(str(outputs[index]), cv2.IMREAD_COLOR)
        if before is None or after is None:
            return False, "an enhanced sample frame could not be decoded"
        expected_width, expected_height = before.shape[1] * scale, before.shape[0] * scale
        if abs(after.shape[1] - expected_width) > 2 or abs(after.shape[0] - expected_height) > 2:
            return False, f"unexpected AI frame size {after.shape[1]}x{after.shape[0]}"
        reduced = cv2.resize(after, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_AREA)
        left = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
        right = cv2.cvtColor(reduced, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
        if float(left.std()) < 2.0:
            scores.append(1.0)
        else:
            correlation = float(np.corrcoef(left, right)[0, 1])
            scores.append(correlation if math.isfinite(correlation) else 0.0)
    score = min(scores) if scores else 1.0
    if score < 0.72:
        return False, f"enhanced frames failed visual integrity ({score:.3f})"
    return True, f"visual integrity {score:.3f}"


def validate_media_output(output: Path, width: int, height: int, expected_duration: float = 0) -> dict[str, Any]:
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("The enhancement worker did not create a media file.")
    meta = ffprobe(output)
    if meta.get("width") != width or meta.get("height") != height:
        raise RuntimeError(f"Enhanced output has the wrong size: {meta.get('width')}x{meta.get('height')} instead of {width}x{height}.")
    if expected_duration > 0 and float(meta.get("duration") or 0) < expected_duration * 0.9:
        raise RuntimeError(f"Enhanced output is incomplete: {meta.get('duration', 0):.2f}s of {expected_duration:.2f}s.")
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        run([ffmpeg_bin, "-v", "error", "-i", str(output), "-map", "0:v:0", "-f", "null", "-"])
    return meta


def create_preview_proxy(output: Path) -> Path:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin or output.suffix.lower() in IMAGE_SUFFIXES:
        return output
    preview = output.with_name(output.stem + "_preview.mp4")
    run([
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(output),
        "-vf", "scale='min(1080,iw)':-2:flags=lanczos",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(preview),
    ])
    preview_meta = ffprobe(preview)
    master_meta = ffprobe(output)
    if float(preview_meta.get("duration") or 0) < float(master_meta.get("duration") or 0) * 0.9:
        raise RuntimeError("The Enhance preview proxy is incomplete.")
    return preview


def validate_generated_video(
    output: Path,
    *,
    face_model: Path | None = None,
    face_recognition_model: Path | None = None,
    reference_image: Path | None = None,
    identity_safe: bool = False,
    reference_has_face: bool = False,
    reference_face_area: float = 0.0,
) -> dict[str, float]:
    """Reject blank, frozen, cut-heavy, or identity-unstable generations."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"luminance": -1.0, "detail": -1.0, "motion": -1.0}
    capture = cv2.VideoCapture(str(output))
    if not capture.isOpened():
        raise RuntimeError("Generated video could not be opened for visual validation.")
    count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
    indices = sorted(set(int(round(value)) for value in np.linspace(0, count - 1, min(16, count))))
    frames: list[Any] = []
    color_frames: list[Any] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if ok and frame is not None:
            color_frames.append(frame)
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()
    if len(frames) < 2:
        raise RuntimeError("Generated video did not contain enough decodable frames.")
    luminance = float(np.mean([np.mean(frame) for frame in frames]))
    detail = float(np.mean([np.std(frame) for frame in frames]))
    motion = float(np.mean([np.mean(cv2.absdiff(frames[index - 1], frames[index])) for index in range(1, len(frames))]))
    # Pixel differences mistake compression shimmer for animation. Dense
    # optical flow measures actual displacement, which lets TonyFX reject the
    # common failure where an I2V result is just the source image for 5 sec.
    flow_samples: list[float] = []
    flow_peaks: list[float] = []
    for index in range(1, len(frames)):
        previous_small = cv2.resize(frames[index - 1], (256, 256), interpolation=cv2.INTER_AREA)
        current_small = cv2.resize(frames[index], (256, 256), interpolation=cv2.INTER_AREA)
        flow = cv2.calcOpticalFlowFarneback(previous_small, current_small, None, 0.5, 3, 21, 3, 5, 1.2, 0)
        magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        flow_samples.append(float(np.percentile(magnitude, 65)))
        flow_peaks.append(float(np.percentile(magnitude, 95)))
    optical_motion = float(np.mean(flow_samples)) if flow_samples else 0.0
    optical_peak = float(max(flow_peaks)) if flow_peaks else 0.0
    luminance_jumps = [abs(float(np.mean(frames[index])) - float(np.mean(frames[index - 1]))) for index in range(1, len(frames))]
    flicker = float(np.percentile(luminance_jumps, 90)) if luminance_jumps else 0.0
    histogram_correlations: list[float] = []
    for index in range(1, len(color_frames)):
        previous = cv2.calcHist([color_frames[index - 1]], [0, 1], None, [24, 24], [0, 180, 0, 256])
        current = cv2.calcHist([color_frames[index]], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(previous, previous)
        cv2.normalize(current, current)
        histogram_correlations.append(float(cv2.compareHist(previous, current, cv2.HISTCMP_CORREL)))
    abrupt_cuts = sum(value < 0.18 for value in histogram_correlations)
    face_areas: list[float] = []
    face_centers: list[tuple[float, float]] = []
    face_confidences: list[float] = []
    face_details: list[float] = []
    face_geometries: list[list[float]] = []
    identity_scores: list[float] = []
    face_hits = 0
    recognizer = None
    reference_feature = None
    if identity_safe and reference_image and face_model and face_recognition_model and face_recognition_model.exists():
        try:
            reference_frame = cv2.imread(str(reference_image))
            reference_faces = detect_faces_bgr(reference_frame, face_model) if reference_frame is not None else []
            if reference_faces:
                recognizer = cv2.FaceRecognizerSF_create(str(face_recognition_model), "")
                reference_feature = face_feature_bgr(reference_frame, reference_faces[0], recognizer)
        except Exception:
            recognizer = None
            reference_feature = None
    if face_model:
        for frame in color_frames:
            faces = detect_faces_bgr(frame, face_model)
            if not faces:
                continue
            face_hits += 1
            face = faces[0]
            face_confidences.append(face["confidence"])
            frame_height, frame_width = frame.shape[:2]
            face_areas.append((face["width"] * face["height"]) / float(frame_width * frame_height))
            face_centers.append(((face["x"] + face["width"] * 0.5) / frame_width, (face["y"] + face["height"] * 0.5) / frame_height))
            x0 = max(0, int(face["x"])); y0 = max(0, int(face["y"]))
            x1 = min(frame_width, int(face["x"] + face["width"])); y1 = min(frame_height, int(face["y"] + face["height"]))
            face_crop = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            if face_crop.size:
                face_details.append(float(cv2.Laplacian(face_crop, cv2.CV_64F).var()))
            landmarks = face.get("landmarks") or []
            if len(landmarks) == 5 and face["width"] > 0 and face["height"] > 0:
                geometry: list[float] = []
                for point in landmarks:
                    geometry.extend([
                        (point[0] - face["x"]) / face["width"],
                        (point[1] - face["y"]) / face["height"],
                    ])
                face_geometries.append(geometry)
            if recognizer is not None and reference_feature is not None:
                feature = face_feature_bgr(frame, face, recognizer)
                if feature is not None:
                    identity_scores.append(float(recognizer.match(reference_feature, feature, cv2.FaceRecognizerSF_FR_COSINE)))
    face_ratio = face_hits / float(len(color_frames))
    face_confidence = float(np.mean(face_confidences)) if face_confidences else 0.0
    face_area_cv = float(np.std(face_areas) / max(1e-6, np.mean(face_areas))) if len(face_areas) > 1 else 0.0
    face_center_jump = 0.0
    if len(face_centers) > 1:
        face_center_jump = max(math.dist(face_centers[index - 1], face_centers[index]) for index in range(1, len(face_centers)))
    face_geometry_jump = 0.0
    if len(face_geometries) > 1:
        geometry_array = np.asarray(face_geometries, dtype=np.float32)
        median_geometry = np.median(geometry_array, axis=0)
        face_geometry_jump = float(np.max(np.sqrt(np.mean((geometry_array - median_geometry) ** 2, axis=1))))
    face_detail = float(np.median(face_details)) if face_details else 0.0
    identity_similarity = float(np.percentile(identity_scores, 10)) if identity_scores else 0.0
    if luminance < 2.0 or luminance > 253.0 or detail < 1.5:
        raise RuntimeError("Generated video was blank or visually invalid.")
    if motion < 0.08 or optical_motion < 0.12:
        raise RuntimeError(
            "Generated video was effectively frozen. Increase the requested action or camera movement and retry."
        )
    if abrupt_cuts > 1:
        raise RuntimeError("Generated video changed scenes unexpectedly instead of remaining one coherent shot.")
    face_policy = identity_face_policy(reference_face_area) if identity_safe and reference_has_face else "none"
    if face_policy == "portrait":
        if face_ratio < 0.82:
            raise RuntimeError("Face consistency check failed: the reference face disappeared or became unreadable.")
        if face_confidence < 0.78 or face_area_cv > 0.58 or face_center_jump > 0.38 or face_geometry_jump > 0.075 or face_detail < 18.0:
            raise RuntimeError("Face consistency check failed: facial geometry or position changed too abruptly.")
        if reference_feature is not None and (len(identity_scores) < max(2, int(len(color_frames) * 0.7)) or identity_similarity < 0.36):
            raise RuntimeError("Face consistency check failed: the generated person no longer matches the reference identity.")
    elif face_policy == "medium":
        # Medium shots naturally turn, cross profile, and briefly lose a clean
        # detector lock. Preserve identity without treating that as corruption.
        if face_ratio < 0.44:
            raise RuntimeError("Face consistency check failed: the subject became unreadable for most of the shot.")
        if face_confidence < 0.64 or face_area_cv > 0.95 or face_center_jump > 0.62 or face_geometry_jump > 0.15:
            raise RuntimeError("Face consistency check failed: the subject changed too abruptly.")
    return {
        "luminance": round(luminance, 3),
        "detail": round(detail, 3),
        "motion": round(motion, 3),
        "opticalMotion": round(optical_motion, 3),
        "opticalPeak": round(optical_peak, 3),
        "flicker": round(flicker, 3),
        "abruptCuts": float(abrupt_cuts),
        "faceCoverage": round(face_ratio, 3),
        "faceConfidence": round(face_confidence, 3),
        "faceAreaVariation": round(face_area_cv, 3),
        "faceCenterJump": round(face_center_jump, 3),
        "faceGeometryJump": round(face_geometry_jump, 3),
        "faceDetail": round(face_detail, 3),
        "identitySimilarity": round(identity_similarity, 3),
    }


def identity_face_policy(reference_face_area: float) -> str:
    """Choose identity QA appropriate to the reference shot scale.

    YuNet is reliable for close and medium faces. A face occupying less than
    roughly 1.2% of the frame is a wide/full-body composition, where requiring
    detection in every frame creates false failures during profile movement.
    """
    area = max(0.0, float(reference_face_area or 0.0))
    if area >= 0.035:
        return "portrait"
    if area >= 0.012:
        return "medium"
    return "wide"


def _sface_model(root: Path) -> Path | None:
    candidates = [
        root / "models" / "face_recognition_sface_2021dec.onnx",
        root / "models" / "analysis" / "face_recognition_sface_2021dec.onnx",
    ]
    return next((path for path in candidates if path.exists()), None)


def face_feature_bgr(image: Any, face: dict[str, Any], recognizer: Any) -> Any:
    """Align a YuNet face and return its normalized SFace embedding."""
    try:
        import numpy as np
        landmarks = face.get("landmarks") or []
        if len(landmarks) != 5:
            return None
        row = [face["x"], face["y"], face["width"], face["height"]]
        for point in landmarks:
            row.extend([point[0], point[1]])
        row.append(face.get("confidence", 1.0))
        aligned = recognizer.alignCrop(image, np.asarray(row, dtype=np.float32))
        if aligned is None or aligned.size == 0:
            return None
        return recognizer.feature(aligned)
    except Exception:
        return None


def restore_reference_identity_video(
    output: Path,
    reference_image: Path,
    face_model: Path | None,
) -> dict[str, Any]:
    """Stabilize a close reference face without freezing the generated shot.

    LTX conditions the first frame but does not expose a persistent identity
    lock. For TonyFX's explicit Identity Safe mode, align the real reference
    face to the generated landmarks on every readable frame, color-match it to
    the shot, and blend only the inner face region. Hair, body, background and
    all model-generated motion remain untouched.
    """
    if not face_model or not face_model.exists() or not reference_image.exists():
        return {"applied": False, "reason": "face models unavailable"}
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"applied": False, "reason": "OpenCV unavailable"}
    reference = cv2.imread(str(reference_image))
    reference_faces = detect_faces_bgr(reference, face_model) if reference is not None else []
    if not reference_faces:
        return {"applied": False, "reason": "reference face unavailable"}
    source_face = reference_faces[0]
    source_landmarks = np.asarray(source_face.get("landmarks") or [], dtype=np.float32)
    if source_landmarks.shape != (5, 2):
        return {"applied": False, "reason": "reference landmarks unavailable"}
    source_mask = np.zeros(reference.shape[:2], dtype=np.uint8)
    center = (
        int(round(source_face["x"] + source_face["width"] * 0.5)),
        int(round(source_face["y"] + source_face["height"] * 0.50)),
    )
    axes = (
        max(2, int(round(source_face["width"] * 0.43))),
        max(2, int(round(source_face["height"] * 0.47))),
    )
    cv2.ellipse(source_mask, center, axes, 0, 0, 360, 255, -1, cv2.LINE_AA)
    capture = cv2.VideoCapture(str(output))
    if not capture.isOpened():
        return {"applied": False, "reason": "video unavailable"}
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
    frames: list[Any] = []
    restored = 0
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        faces = detect_faces_bgr(frame, face_model)
        if faces:
            target = faces[0]
            target_landmarks = np.asarray(target.get("landmarks") or [], dtype=np.float32)
            if target_landmarks.shape == (5, 2):
                transform, _ = cv2.estimateAffinePartial2D(
                    source_landmarks,
                    target_landmarks,
                    method=cv2.LMEDS,
                )
                if transform is not None:
                    height, width = frame.shape[:2]
                    warped = cv2.warpAffine(reference, transform, (width, height), flags=cv2.INTER_LANCZOS4)
                    mask = cv2.warpAffine(source_mask, transform, (width, height), flags=cv2.INTER_LINEAR)
                    active = mask > 48
                    if int(np.count_nonzero(active)) > 128:
                        corrected = warped.astype(np.float32)
                        target_float = frame.astype(np.float32)
                        for channel in range(3):
                            source_values = corrected[:, :, channel][active]
                            target_values = target_float[:, :, channel][active]
                            source_mean = float(np.mean(source_values)); source_std = max(8.0, float(np.std(source_values)))
                            target_mean = float(np.mean(target_values)); target_std = max(8.0, float(np.std(target_values)))
                            corrected[:, :, channel] = (corrected[:, :, channel] - source_mean) * min(1.35, target_std / source_std) + target_mean
                        corrected = np.clip(corrected, 0, 255).astype(np.uint8)
                        bounds = cv2.boundingRect(mask)
                        clone_center = (bounds[0] + bounds[2] // 2, bounds[1] + bounds[3] // 2)
                        try:
                            frame = cv2.seamlessClone(corrected, frame, mask, clone_center, cv2.NORMAL_CLONE)
                        except cv2.error:
                            alpha = cv2.GaussianBlur(mask, (0, 0), 7).astype(np.float32)[:, :, None] / 255.0
                            frame = np.clip(corrected * alpha + frame * (1.0 - alpha), 0, 255).astype(np.uint8)
                        restored += 1
        frames.append(frame)
    capture.release()
    if not frames or restored < max(2, int(len(frames) * 0.65)):
        return {"applied": False, "reason": "insufficient tracking", "restoredFrames": restored, "totalFrames": len(frames)}
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return {"applied": False, "reason": "FFmpeg unavailable"}
    with tempfile.TemporaryDirectory(prefix="tonyfx-identity-") as temp_value:
        temp_dir = Path(temp_value)
        for index, frame in enumerate(frames):
            if not cv2.imwrite(str(temp_dir / f"frame-{index:06d}.png"), frame):
                raise RuntimeError("Identity restoration could not write a temporary frame.")
        restored_output = temp_dir / "identity-restored.mp4"
        run([
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", f"{fps:.6f}", "-i", str(temp_dir / "frame-%06d.png"),
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(restored_output),
        ])
        if not restored_output.exists() or restored_output.stat().st_size < 4096:
            raise RuntimeError("Identity restoration produced an empty result.")
        shutil.copy2(restored_output, output)
    return {
        "applied": True,
        "restoredFrames": restored,
        "totalFrames": len(frames),
        "coverage": round(restored / float(len(frames)), 3),
    }


def enhance_with_realesrgan(source: Path, output: Path, meta: dict[str, Any], args: argparse.Namespace, executable: str) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail("FFmpeg was not found.")
    width, height = target_size(meta, args)
    is_image = source.suffix.lower() in IMAGE_SUFFIXES
    model = args.model or "realesrgan-x4plus"
    # Run x4plus at its native scale. Forcing this NCNN model to -s 2 can
    # produce decoded but visibly tiled frames on Vulkan. The final FFmpeg
    # pass downsamples the clean native result to the requested dimensions.
    scale = 4 if "x4" in model.lower() else max(2, min(4, int(round(max(width / max(1, meta.get("width", 1)), height / max(1, meta.get("height", 1)))))))
    with tempfile.TemporaryDirectory(prefix="tonyfx-enhance-") as temp_value:
        temp = Path(temp_value)
        emit("workspace", path=str(temp))
        input_frames = temp / "input"
        output_frames = temp / "output"
        input_frames.mkdir()
        output_frames.mkdir()
        if is_image:
            input_file = input_frames / "frame_00000001.png"
            run([ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-frames:v", "1", str(input_file)])
        else:
            progress(8, "Extracting source frames")
            extract = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
            if float(args.start or 0) > 0:
                extract += ["-ss", f"{float(args.start):.6f}"]
            if float(args.duration or 0) > 0:
                extract += ["-t", f"{float(args.duration):.6f}"]
            extract += ["-i", str(source), str(input_frames / "frame_%08d.png")]
            run(extract)
        input_count = len(list(input_frames.glob("*.png")))
        if not input_count:
            fail("TonyFX could not extract any source frames.")
        requested_tile = max(64, min(128, int(args.tile)))
        tile_attempts = []
        for tile in (requested_tile, 128, 64):
            if tile not in tile_attempts:
                tile_attempts.append(tile)
        verified = False
        verification = ""
        for attempt, tile in enumerate(tile_attempts, 1):
            if output_frames.exists():
                shutil.rmtree(output_frames)
            output_frames.mkdir()
            progress(22, f"Real-ESRGAN pass {attempt}/{len(tile_attempts)} on {input_count} frames (tile {tile})")
            run_frame_process(
                [executable, "-i", str(input_frames), "-o", str(output_frames), "-n", model, "-s", str(scale), "-t", str(tile), "-g", "0", "-j", "2:2:2", "-f", "png"],
                output_frames,
                input_count,
                24,
                68,
                "Restored",
            )
            verified, verification = validate_frame_sequence(input_frames, output_frames, input_count, scale)
            if verified:
                emit("validation", ok=True, message=verification, tile=tile)
                break
            emit("warning", message=f"Unsafe Real-ESRGAN pass rejected: {verification}. Retrying with a safer tile.", tile=tile)
        if not verified:
            raise RuntimeError(f"Real-ESRGAN frame validation failed after safe retries: {verification}")
        encode_frames = output_frames
        encode_fps = float(meta.get("fps") or 30.0)
        rife = resolve_executable("rife-ncnn-vulkan.exe", engine_root(args.engine_root))
        if not is_image and args.interpolate and rife and float(args.target_fps or 0) > encode_fps + 0.01:
            source_frames = sorted(output_frames.glob("*.png"))
            if len(source_frames) > 1:
                rife_frames = temp / "rife"
                rife_frames.mkdir()
                target_fps = max(12.0, min(120.0, float(args.target_fps)))
                target_count = max(len(source_frames), int(round(len(source_frames) * target_fps / encode_fps)))
                progress(72, f"Interpolating {len(source_frames)} frames to {target_count} with RIFE")
                run_frame_process(
                    [
                        rife,
                        "-i", str(output_frames),
                        "-o", str(rife_frames),
                        "-n", str(target_count),
                        "-m", "rife-v4.6",
                        "-f", "frame_%08d.png",
                        "-j", "1:2:2",
                    ],
                    rife_frames,
                    target_count,
                    72,
                    80,
                    "Interpolated",
                    cwd=Path(rife).parent,
                )
                interpolated = sorted(rife_frames.glob("*.png"))
                if not interpolated:
                    fail("RIFE interpolation completed without output frames.")
                # Normalize names because RIFE releases differ between zero- and one-based output.
                normalized = temp / "rife-normalized"
                normalized.mkdir()
                for index, frame in enumerate(interpolated, 1):
                    shutil.move(str(frame), str(normalized / f"frame_{index:08d}.png"))
                encode_frames = normalized
                encode_fps = target_fps
        progress(82, "Finishing detail, color, and delivery encoding")
        rife_was_used = encode_frames != output_frames
        # RIFE owns temporal synthesis when available; FFmpeg remains a real fallback.
        filters = enhancement_filters(
            args,
            width,
            height,
            interpolation=not is_image and args.interpolate and not rife_was_used,
        )
        if is_image:
            processed = next(output_frames.glob("*.png"), None)
            if not processed:
                fail("Real-ESRGAN did not produce an output image.")
            run([ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(processed), "-vf", filters, "-frames:v", "1", str(output)])
            return
        command = [
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", f"{encode_fps:.6f}", "-start_number", "1", "-i", str(encode_frames / "frame_%08d.png"),
        ]
        source_start = max(0.0, float(args.start or 0))
        source_duration = max(0.0, float(args.duration or 0))
        if source_start > 0:
            command += ["-ss", f"{source_start:.6f}"]
        if source_duration > 0:
            command += ["-t", f"{source_duration:.6f}"]
        command += ["-i", str(source), "-vf", filters]
        if args.codec == "h264":
            command += ["-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        else:
            command += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
        video_duration = len(list(encode_frames.glob("*.png"))) / max(1.0, encode_fps)
        command += ["-map", "0:v:0", "-map", "1:a?", "-c:a", "pcm_s24le" if args.codec != "h264" else "aac", "-t", f"{video_duration:.6f}", str(output)]
        run(command)


def enhance(args: argparse.Namespace) -> None:
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        fail(f"Input media does not exist: {source}")
    root = engine_root(args.engine_root)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    progress(2, "Inspecting source media")
    meta = ffprobe(source)
    real_esrgan = resolve_executable("realesrgan-ncnn-vulkan.exe", root)
    rife = resolve_executable("rife-ncnn-vulkan.exe", root)
    if args.ai and real_esrgan:
        try:
            enhance_with_realesrgan(source, output, meta, args, real_esrgan)
            backend = "Real-ESRGAN GPU + RIFE + FFmpeg" if args.interpolate and rife else "Real-ESRGAN GPU + FFmpeg"
        except Exception as error:
            emit("warning", message=f"GPU enhancement was rejected ({error}). TonyFX is completing this item with the safe FFmpeg restoration path.")
            output.unlink(missing_ok=True)
            enhance_with_ffmpeg(source, output, meta, args)
            backend = "Validated FFmpeg fallback after rejected GPU output"
    else:
        enhance_with_ffmpeg(source, output, meta, args)
        backend = "FFmpeg restoration" if not args.ai else "FFmpeg restoration (AI engine not installed)"
    width, height = target_size(meta, args)
    expected_duration = 0 if source.suffix.lower() in IMAGE_SUFFIXES else (float(args.duration or 0) or float(meta.get("duration") or 0))
    output_meta = validate_media_output(output, width, height, expected_duration)
    progress(96, "Building full-duration panel preview")
    preview = create_preview_proxy(output)
    progress(100, "Enhanced media ready")
    emit("result", ok=True, output=str(output), preview=str(preview), outputs=[str(output)], backend=backend, meta=output_meta)


def cleanup_audio(source: Path, output: Path, args: argparse.Namespace) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail("FFmpeg was not found.")
    denoise = max(0.0, min(100.0, float(args.denoise)))
    dereverb = max(0.0, min(100.0, float(args.dereverb)))
    dehum = max(0.0, min(100.0, float(args.dehum)))
    presence = max(0.0, min(100.0, float(args.presence)))
    clarity = max(0.0, min(100.0, float(args.clarity)))
    compression = max(0.0, min(100.0, float(args.compression)))
    deess = max(0.0, min(100.0, float(args.deess)))
    highpass = max(20.0, min(180.0, float(args.highpass)))
    lowpass = max(8000.0, min(20000.0, float(args.lowpass)))
    filters = [f"highpass=f={highpass:.1f}", f"lowpass=f={lowpass:.1f}"]
    if dehum > 0:
        width = 1.2 + dehum / 35.0
        filters += [f"bandreject=f=50:width_type=h:width={width:.2f}", f"bandreject=f=100:width_type=h:width={width:.2f}"]
    if denoise > 0:
        filters.append(f"afftdn=nr={min(28.0, 4.0 + denoise * 0.24):.2f}:nf=-35:tn=1")
    if dereverb > 0:
        # Non-local-means suppresses low-level room tails while retaining transients.
        filters.append(f"anlmdn=s={min(0.012, 0.0015 + dereverb * 0.000085):.5f}:p=0.003:r=0.009:m=11")
    if presence > 0:
        filters.append(f"equalizer=f=1800:t=q:w=1.0:g={presence * 0.045:.2f}")
    if clarity > 0:
        filters.append(f"equalizer=f=3600:t=q:w=1.15:g={clarity * 0.038:.2f}")
    if deess > 0:
        filters.append(f"deesser=i={min(0.8, deess / 125.0):.3f}:m={min(0.9, 0.35 + deess / 200.0):.3f}:f=0.55")
    if compression > 0:
        ratio = 1.0 + compression * 0.045
        threshold = max(0.045, 0.22 - compression * 0.0015)
        makeup = min(2.0, 1.0 + compression * 0.008)
        filters.append(f"acompressor=threshold={threshold:.3f}:ratio={ratio:.2f}:attack=8:release=95:makeup={makeup:.2f}:knee=2.5:mix=1")
    if bool(args.normalize):
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=9")
    filters += ["alimiter=limit=0.97", "aresample=48000"]
    run([ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-af", ",".join(filters), "-c:a", "pcm_s24le", str(output)])


def approximate_separation(source: Path, output: Path, keep_voice: bool, args: argparse.Namespace) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail("FFmpeg was not found.")
    if keep_voice:
        pan = "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1,highpass=f=80,lowpass=f=14500"
    else:
        pan = "pan=stereo|c0=c0-c1|c1=c1-c0,highpass=f=45,lowpass=f=18000"
    run([ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-af", pan, "-ar", "48000", "-c:a", "pcm_s24le", str(output)])


def demucs_separate(source: Path, temp: Path, operation: str, args: argparse.Namespace) -> list[Path]:
    model = args.demucs_model or "htdemucs"
    # Hybrid Transformer Demucs was trained with a 7.8 second maximum segment.
    # Stay slightly below that limit so every official HTDemucs checkpoint works.
    runner = Path(__file__).with_name("demucs_runner.py")
    if not runner.exists():
        fail("TonyFX Demucs runner is missing. Reinstall the current TonyFX build.")
    command = [sys.executable, str(runner), "-n", model, "--segment", "7", "--float32", "-o", str(temp)]
    if operation in {"voice", "background", "vocals", "instrumental"}:
        command += ["--two-stems", "vocals"]
    command.append(str(source))
    progress(18, "Separating local audio stems with Demucs")
    run(command, capture=True)
    stem_dir = temp / model / source.stem
    if not stem_dir.exists():
        candidates = list(temp.rglob(source.stem))
        stem_dir = candidates[0] if candidates else stem_dir
    if operation in {"voice", "vocals"}:
        candidates = [stem_dir / "vocals.wav"]
    elif operation in {"background", "instrumental"}:
        candidates = [stem_dir / "no_vocals.wav"]
    else:
        candidates = [stem_dir / f"{name}.wav" for name in ("vocals", "drums", "bass", "other")]
    return [path for path in candidates if path.exists()]


def audio(args: argparse.Namespace) -> None:
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        fail(f"Input media does not exist: {source}")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    operation = "voice" if args.operation == "remove-background" else args.operation
    progress(3, "Inspecting audio source")
    outputs: list[Path] = []
    backend = "FFmpeg cleanup"
    with tempfile.TemporaryDirectory(prefix="tonyfx-audio-") as temp_value:
        temp = Path(temp_value)
        working_source = source
        if float(args.start or 0) > 0 or float(args.duration or 0) > 0:
            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                fail("FFmpeg was not found.")
            working_source = temp / f"{source.stem}_selection.wav"
            trim = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
            if float(args.start or 0) > 0:
                trim += ["-ss", f"{float(args.start):.6f}"]
            if float(args.duration or 0) > 0:
                trim += ["-t", f"{float(args.duration):.6f}"]
            trim += ["-i", str(source), "-vn", "-ar", "48000", "-c:a", "pcm_s24le", str(working_source)]
            run(trim)
        if operation == "cleanup":
            cleanup_audio(working_source, output, args)
            outputs = [output]
        elif module_ready("demucs"):
            separated = demucs_separate(working_source, temp, operation, args)
            if not separated:
                fail("Demucs finished without producing the requested stems.")
            backend = "Demucs local separation"
            for index, stem in enumerate(separated):
                suffix = stem.stem.replace("no_vocals", "instrumental")
                target = output if len(separated) == 1 else output.with_name(f"{output.stem}_{suffix}{output.suffix}")
                progress(62 + index * (25 / max(1, len(separated))), f"Cleaning {suffix} stem")
                cleanup_audio(stem, target, args)
                outputs.append(target)
        elif operation in {"voice", "vocals"}:
            fail("The precision background remover is not installed. Press Setup in TonyFX Audio Lab, then try again.")
        else:
            keep_voice = operation in {"voice", "vocals"}
            approximate_separation(working_source, output, keep_voice, args)
            outputs = [output]
            backend = "FFmpeg center-channel separation (install Demucs for precision)"
    valid = [item for item in outputs if item.exists() and item.stat().st_size > 0]
    if not valid:
        fail("The audio worker finished without a valid output.")
    progress(100, "Local audio processing complete")
    emit("result", ok=True, output=str(valid[0]), outputs=[str(item) for item in valid], backend=backend)


def load_generation_stack() -> tuple[Any, Any]:
    if not module_ready("torch") or not module_ready("diffusers"):
        fail("The local generation runtime is not installed. Use Setup Engine in TonyFX first.")
    import torch  # type: ignore
    import diffusers  # type: ignore
    return torch, diffusers


def generator_for(torch: Any, seed: int) -> Any:
    return torch.Generator(device="cpu").manual_seed(int(seed) & 0x7FFFFFFF)


def compile_video_prompt(
    prompt: str, profile: str = "identity", has_reference: bool = False, subject_scale: str = "portrait"
) -> str:
    """Turn a loose request into a literal single-shot instruction for LTX.

    The small local model follows short chronological descriptions more reliably
    than keyword piles. Keep the user's requested content first and add only
    constraints that reduce identity drift and accidental scene changes.
    """
    cleaned = " ".join(str(prompt or "").replace("\n", " ").split()).strip(" ,.;")
    if not cleaned:
        return ""
    profile = str(profile or "identity").lower()
    # Do not invent an action here. Previous builds injected "walking gait"
    # and "wide shot" into every identity request, including close-up eye
    # zooms. That fought the user prompt and made LTX freeze or morph.
    identity_contract = (
        "One continuous realistic shot. Execute only the requested subject action and camera move. "
        "Keep the same person, body proportions, facial structure, eyes, skin, hair, hands, clothing, "
        "and background consistent for the whole shot. Motion is physically natural and temporally coherent. "
        "No cuts, transformations, duplicate people, new objects, writing, logos, captions, or watermarks."
    )
    suffixes = {
        "identity": identity_contract,
        "realism": (
            "One continuous photorealistic shot with physically plausible movement, coherent depth, "
            "stable geometry, natural skin texture, and a detailed consistent environment. "
            "No cuts, transformations, writing, logos, or captions."
        ),
        "fast": (
            "One continuous shot with coherent motion and stable geometry. No cuts, writing, logos, or captions."
        ),
    }
    reference_note = " The supplied image is the exact first frame and identity reference." if has_reference else ""
    return f"{cleaned}. {suffixes.get(profile, suffixes['identity'])}{reference_note}"[:1800]


def _yunet_model(root: Path) -> Path | None:
    candidates = [
        root / "models" / "analysis" / "face_detection_yunet_2023mar.onnx",
        Path.home() / "Documents" / "TonyFX Local Engine" / "models" / "analysis" / "face_detection_yunet_2023mar.onnx",
    ]
    return next((item for item in candidates if item.exists()), None)


def detect_faces_bgr(image: Any, model_path: Path | None) -> list[dict[str, Any]]:
    if model_path is None:
        return []
    try:
        import cv2
        height, width = image.shape[:2]
        # Small social-profile references are common. Upscale only for
        # detection and map the result back so identity QA cannot silently
        # disable itself just because the input was 200-300 px wide.
        detect_scale = max(1.0, min(4.0, 640.0 / max(1.0, float(min(width, height)))))
        detect_image = image
        if detect_scale > 1.05:
            detect_image = cv2.resize(image, None, fx=detect_scale, fy=detect_scale, interpolation=cv2.INTER_CUBIC)
        detect_height, detect_width = detect_image.shape[:2]
        detector = cv2.FaceDetectorYN_create(str(model_path), "", (detect_width, detect_height), 0.55, 0.3, 5000)
        detector.setInputSize((detect_width, detect_height))
        _status, faces = detector.detect(detect_image)
        if faces is None:
            return []
        values = []
        for face in faces:
            x, y, w, h = [float(item) / detect_scale for item in face[:4]]
            raw_landmarks = [float(item) / detect_scale for item in face[4:14]]
            landmarks = [(raw_landmarks[index], raw_landmarks[index + 1]) for index in range(0, len(raw_landmarks), 2)]
            values.append({"x": x, "y": y, "width": w, "height": h, "confidence": float(face[-1]), "landmarks": landmarks})
        return sorted(values, key=lambda item: item["width"] * item["height"], reverse=True)
    except Exception:
        return []


def prepare_video_reference(
    input_path: Path, width: int, height: int, root: Path, fit_mode: str = "face"
) -> tuple[Any, dict[str, Any]]:
    """Prepare an I2V first frame without ever stretching its geometry."""
    from PIL import Image, ImageOps
    image = Image.open(input_path).convert("RGB")
    source_width, source_height = image.size
    target_ratio = width / float(height)
    source_ratio = source_width / float(source_height)
    fit_mode = str(fit_mode or "face").lower()
    face: dict[str, float] | None = None
    if fit_mode == "face":
        try:
            import cv2
            import numpy as np
            bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            faces = detect_faces_bgr(bgr, _yunet_model(root))
            face = faces[0] if faces else None
        except Exception:
            face = None

    if fit_mode == "contain":
        prepared = ImageOps.pad(image, (width, height), method=Image.Resampling.LANCZOS, color=(12, 12, 12), centering=(0.5, 0.5))
        crop = [0, 0, source_width, source_height]
    else:
        if source_ratio > target_ratio:
            crop_height = source_height
            crop_width = max(1, int(round(crop_height * target_ratio)))
        else:
            crop_width = source_width
            crop_height = max(1, int(round(crop_width / target_ratio)))
        focus_x = (face["x"] + face["width"] * 0.5) if face else source_width * 0.5
        # Keep eyes slightly above center; this leaves useful room below the face.
        focus_y = (face["y"] + face["height"] * 0.62) if face else source_height * 0.5
        left = int(round(max(0, min(source_width - crop_width, focus_x - crop_width * 0.5))))
        top = int(round(max(0, min(source_height - crop_height, focus_y - crop_height * 0.42))))
        crop = [left, top, left + crop_width, top + crop_height]
        prepared = image.crop(tuple(crop)).resize((width, height), Image.Resampling.LANCZOS)
    metadata = {
        "sourceSize": [source_width, source_height],
        "targetSize": [width, height],
        "fit": fit_mode,
        "crop": crop,
        "faceDetected": bool(face),
        "face": face,
        "preparedFaceArea": (
            (face["width"] * face["height"]) / float(max(1, crop_width * crop_height))
            if face and fit_mode != "contain"
            else (face["width"] * face["height"]) / float(max(1, source_width * source_height)) if face else 0.0
        ),
    }
    return prepared, metadata


def generate_image(args: argparse.Namespace) -> None:
    torch, diffusers = load_generation_stack()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = args.model or "Lykon/dreamshaper-8"
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    progress(4, "Loading the local image model")
    common = {"torch_dtype": dtype, "use_safetensors": True}
    input_image = Path(args.input_image).resolve() if args.input_image else None
    mask_image = Path(args.mask).resolve() if args.mask else None
    if input_image and mask_image:
        pipeline_class = getattr(diffusers, "AutoPipelineForInpainting")
    elif input_image:
        pipeline_class = getattr(diffusers, "AutoPipelineForImage2Image")
    else:
        pipeline_class = getattr(diffusers, "AutoPipelineForText2Image")
    pipeline = pipeline_class.from_pretrained(model, **common)
    if torch.cuda.is_available():
        pipeline.enable_model_cpu_offload()
    else:
        pipeline.to("cpu")
    try:
        pipeline.enable_attention_slicing()
        pipeline.enable_vae_slicing()
    except Exception:
        pass
    width = max(256, int(args.width) // 8 * 8)
    height = max(256, int(args.height) // 8 * 8)
    kwargs: dict[str, Any] = {
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt or None,
        "num_inference_steps": max(1, int(args.steps)),
        "guidance_scale": float(args.guidance),
        "generator": generator_for(torch, int(args.seed)),
    }
    if not input_image:
        kwargs.update(width=width, height=height)
    else:
        from PIL import Image
        image = Image.open(input_image).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        kwargs.update(image=image, strength=max(0.05, min(1.0, float(args.strength))))
        if mask_image:
            mask = Image.open(mask_image).convert("L").resize((width, height), Image.Resampling.LANCZOS)
            kwargs["mask_image"] = mask
    progress(18, "Generating locally on the GPU")
    result = pipeline(**kwargs)
    image = result.images[0]
    image.save(output)
    progress(100, "Generated image ready")
    emit("result", ok=True, output=str(output), outputs=[str(output)], backend=f"Diffusers | {model}", seed=int(args.seed))


def generate_video_framepack(args: argparse.Namespace) -> None:
    """Run the high-fidelity FramePack I2V backend in its isolated runtime."""
    root = engine_root(getattr(args, "engine_root", ""))
    backend = root / "backends" / "FramePack"
    runtime_name = ".venv-quality" if (backend / ".venv-quality").exists() else ".venv"
    backend_python = backend / runtime_name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    adapter = Path(__file__).with_name("framepack_cli.py")
    input_image = Path(args.input_image).expanduser().resolve() if args.input_image else None
    if input_image is None or not input_image.exists():
        fail("Identity Quality requires a reference image. Choose an image before generating.")
    if os.name == "nt":
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            memory = MemoryStatus(); memory.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
            physical_gb = memory.ullTotalPhys / float(1024 ** 3)
            if physical_gb < 24.0:
                fail(
                    f"Experimental FramePack needs at least 24 GB system RAM for a usable Windows run; "
                    f"this PC has {physical_gb:.1f} GB. Use Balanced Local (LTX). The downloaded FramePack "
                    "models are preserved for a future RAM upgrade."
                )
        except RuntimeError:
            raise
        except Exception:
            pass
    if not backend_python.exists() or not (backend / "demo_gradio.py").exists():
        fail("FramePack Identity Quality is not installed. Press Setup in Generate once, then retry.")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    width = max(320, int(args.width) // 2 * 2)
    height = max(320, int(args.height) // 2 * 2)
    target_fps = max(12, min(30, int(args.fps)))
    duration = max(1.0, min(5.0, float(getattr(args, "duration", 3.0))))
    profile = str(getattr(args, "profile", "identity") or "identity").lower()
    steps = max(20, min(35, int(args.steps or 25)))
    negative = str(args.negative_prompt or "").strip() or (
        "face morphing, changing identity, melted face, asymmetric eyes, distorted anatomy, extra limbs, "
        "flicker, jitter, scene cut, duplicate subject, blurry face, warped background, text, logo, watermark"
    )

    with tempfile.TemporaryDirectory(prefix="tonyfx-framepack-") as temp_value:
        temp = Path(temp_value)
        prepared, reference_metadata = prepare_video_reference(
            input_image, width, height, root, str(getattr(args, "reference_fit", "face"))
        )
        prepared_path = temp / "reference.png"
        prepared.save(prepared_path)
        subject_scale = identity_face_policy(float(reference_metadata.get("preparedFaceArea") or 0.0))
        prompt = compile_video_prompt(str(args.prompt), profile, True, subject_scale)
        command = [
            str(backend_python), str(adapter), "--backend-root", str(backend),
            "--input-image", str(prepared_path), "--prompt", prompt,
            "--negative-prompt", negative, "--seconds", str(duration),
            "--steps", str(steps), "--seed", str(int(args.seed)),
        ]
        started = time.monotonic()
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        raw_output: Path | None = None
        tail: list[str] = []
        assert child.stdout is not None
        for line in child.stdout:
            clean = line.strip()
            if not clean:
                continue
            tail.append(clean)
            tail = tail[-30:]
            try:
                event = json.loads(clean)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "progress":
                progress(float(event.get("percent") or 0), str(event.get("message") or "Generating with FramePack"))
            elif event.get("type") == "framepack_result":
                raw_output = Path(str(event.get("output") or "")).resolve()
            elif event.get("type") == "error":
                tail.append(str(event.get("message") or "FramePack failed"))
        return_code = child.wait()
        if return_code != 0 or raw_output is None or not raw_output.exists():
            raise RuntimeError("FramePack failed: " + " | ".join(tail[-6:]))

        progress(90, "Encoding and validating the identity-safe result")
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg is required to finish generated video.")
        run([
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw_output),
            "-vf", f"tpad=stop_mode=clone:stop_duration=1,fps={target_fps},trim=duration={duration:.6f},setpts=PTS-STARTPTS,scale={width}:{height}:flags=lanczos,format=yuv420p",
            "-t", f"{duration:.6f}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-movflags", "+faststart", str(output),
        ])
        output_meta = validate_media_output(output, width, height, duration)
        metrics = validate_generated_video(
            output,
            face_model=_yunet_model(root),
            face_recognition_model=_sface_model(root),
            reference_image=input_image,
            identity_safe=True,
            reference_has_face=bool(reference_metadata.get("faceDetected")),
            reference_face_area=float(reference_metadata.get("preparedFaceArea") or 0.0),
        )
        elapsed = time.monotonic() - started
        metadata_path = output.with_suffix(output.suffix + ".json")
        metadata_path.write_text(json.dumps({
            "engine": "TonyFX Local Video",
            "backend": "FramePack Identity Quality",
            "model": "lllyasviel/FramePackI2V_HY",
            "prompt": prompt,
            "negativePrompt": negative,
            "seed": int(args.seed),
            "steps": steps,
            "width": width,
            "height": height,
            "duration": duration,
            "fps": target_fps,
            "referencePreparation": reference_metadata,
            "elapsedSeconds": round(elapsed, 2),
            "validation": metrics,
        }, indent=2), encoding="utf-8")
        progress(100, "FramePack result validated and ready")
        emit(
            "result", ok=True, output=str(output), preview=str(output), outputs=[str(output)],
            backend="TonyFX FramePack Identity Quality", seed=int(args.seed), metadata=str(metadata_path),
            width=output_meta["width"], height=output_meta["height"], duration=output_meta["duration"],
            elapsed=round(elapsed, 2),
        )


def generate_video(args: argparse.Namespace) -> None:
    if str(getattr(args, "backend", "ltx") or "ltx").lower() == "framepack":
        generate_video_framepack(args)
        return
    torch, diffusers = load_generation_stack()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = args.model or "Lightricks/LTX-Video"
    root = engine_root(getattr(args, "engine_root", ""))
    model_cache = root / "models" / "video" / "huggingface"
    model_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(model_cache))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass
    # BitsAndBytes' Windows CUDA kernels emit FP16 activations. Keeping the
    # complete LTX pipeline on FP16 avoids mixed FP32/BF16 convolution inputs
    # while preserving Tensor Core acceleration on RTX laptop GPUs.
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    input_image = Path(args.input_image).resolve() if args.input_image else None
    if input_image and not input_image.exists():
        fail(f"Reference image was not found: {input_image}")
    progress(3, "Loading the local video model")
    if input_image:
        pipeline_class = getattr(diffusers, "LTXImageToVideoPipeline", None)
    else:
        pipeline_class = getattr(diffusers, "LTXPipeline", None)
    if pipeline_class is None:
        fail("This Diffusers build does not include LTX-Video. Run Setup Engine to update it.")
    repo_cache = model_cache / f"models--{model.replace('/', '--')}"
    cached_model = any(repo_cache.glob("snapshots/*/model_index.json"))
    pipeline_kwargs: dict[str, Any] = {
        "dtype": dtype,
        "cache_dir": str(model_cache),
        "local_files_only": cached_model,
        "low_cpu_mem_usage": True,
        "use_safetensors": True,
    }
    quantized_text_encoder = False
    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if vram_gb < 10:
            # T5-XXL is LTX's largest resident component. Quantizing only the
            # encoder prevents a 16 GB system-RAM stall without changing the
            # video transformer or decoder that determine visual quality.
            try:
                from transformers import BitsAndBytesConfig, T5EncoderModel

                quantization = BitsAndBytesConfig(load_in_8bit=True)
                text_encoder = T5EncoderModel.from_pretrained(
                    model,
                    subfolder="text_encoder",
                    quantization_config=quantization,
                    dtype=dtype,
                    cache_dir=str(model_cache),
                    local_files_only=cached_model,
                    low_cpu_mem_usage=True,
                    use_safetensors=True,
                )
                pipeline_kwargs["text_encoder"] = text_encoder
                quantized_text_encoder = True
                progress(8, "Loaded the memory-safe text encoder")
            except Exception as quantization_error:
                progress(7, f"8-bit text encoder unavailable; using standard loading ({quantization_error})")
    pipeline = pipeline_class.from_pretrained(model, **pipeline_kwargs)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        if vram_gb < 10:
            pipeline.enable_sequential_cpu_offload()
        else:
            pipeline.enable_model_cpu_offload()
    else:
        pipeline.to("cpu")
    try:
        pipeline.enable_vae_tiling()
        pipeline.enable_vae_slicing()
        pipeline.enable_attention_slicing()
    except Exception:
        pass
    width = max(320, int(args.width) // 32 * 32)
    height = max(320, int(args.height) // 32 * 32)
    target_fps = max(12, min(30, int(args.fps)))
    duration = max(1.0, min(5.0, float(getattr(args, "duration", 0) or (int(args.frames) / target_fps))))
    profile = str(getattr(args, "profile", "identity") or "identity").lower()
    base_fps = max(8, min(target_fps, int(getattr(args, "base_fps", 16))))
    if profile == "identity":
        base_fps = min(target_fps, max(16, base_fps))
    requested_base_frames = max(9, int(round(duration * base_fps)) + 1)
    frames = int(math.ceil((requested_base_frames - 1) / 8.0) * 8 + 1)
    quality = str(getattr(args, "quality", "balanced") or "balanced").lower()
    quality_steps = {"draft": 12, "fast": 20, "balanced": 30, "quality": 40}
    steps = max(4, min(40, int(args.steps or quality_steps.get(quality, 20))))
    if profile == "identity":
        steps = max(24, steps)
    elif profile == "realism":
        steps = max(20, steps)
    reference_metadata: dict[str, Any] = {"faceDetected": False, "preparedFaceArea": 0.0}
    prepared_reference = None
    if input_image:
        prepared_reference, reference_metadata = prepare_video_reference(
            input_image, width, height, root, str(getattr(args, "reference_fit", "face"))
        )
        if profile == "identity" and not reference_metadata.get("faceDetected"):
            fail(
                "Face / Identity Safe could not detect a usable face in the reference. Choose a clearer image "
                "with the face at least 80 pixels tall, use Smart Face Crop, or switch Generation Priority to Scene Realism."
            )
    subject_scale = identity_face_policy(float(reference_metadata.get("preparedFaceArea") or 0.0))
    prompt = compile_video_prompt(str(args.prompt), profile, bool(input_image), subject_scale)
    if not prompt:
        fail("A video prompt is required.")
    negative = str(args.negative_prompt or "").strip() or (
        "shaky camera, flicker, jitter, frozen motion, duplicated person, extra person, scene cut, "
        "morphing face, changing identity, asymmetric eyes, melted skin, deformed hands, extra fingers, "
        "distorted anatomy, warped background, stretched image, text, letters, watermark, logo, subtitles, "
        "compression artifacts, low detail, blurry, cartoon, illustration, CGI, plastic skin, worst quality"
    )
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative,
        "width": width,
        "height": height,
        "num_frames": frames,
        "num_inference_steps": steps,
        "guidance_scale": max(1.0, min(5.0, float(args.guidance))),
        "generator": generator_for(torch, int(args.seed)),
    }
    call_parameters = inspect.signature(pipeline.__call__).parameters
    if "frame_rate" in call_parameters:
        kwargs["frame_rate"] = base_fps
    if "decode_timestep" in call_parameters:
        kwargs["decode_timestep"] = 0.05
    if "decode_noise_scale" in call_parameters:
        kwargs["decode_noise_scale"] = 0.025
    if "guidance_rescale" in call_parameters:
        kwargs["guidance_rescale"] = 0.0
    if "max_sequence_length" in call_parameters:
        kwargs["max_sequence_length"] = 256
    if input_image:
        kwargs["image"] = prepared_reference
    def step_callback(_pipeline: Any, step_index: int, _timestep: Any, callback_kwargs: dict[str, Any]) -> dict[str, Any]:
        ratio = (step_index + 1) / max(1, steps)
        progress(15 + ratio * 64, f"Creating motion and detail - step {step_index + 1}/{steps}")
        return callback_kwargs

    kwargs["callback_on_step_end"] = step_callback
    kwargs["callback_on_step_end_tensor_inputs"] = ["latents"]
    progress(15, f"Generating {duration:g}s locally at {width}x{height}")
    started = time.monotonic()
    try:
        result = pipeline(**kwargs)
        video_frames = result.frames[0]
        export_to_video = getattr(importlib.import_module("diffusers.utils"), "export_to_video")
        with tempfile.TemporaryDirectory(prefix="tonyfx-video-") as temp_value:
            raw = Path(temp_value) / "generated-base.mp4"
            export_to_video(video_frames, str(raw), fps=base_fps)
            if not raw.exists() or raw.stat().st_size < 4096:
                raise RuntimeError("The video model returned an empty result.")
            progress(82, f"Finishing at {target_fps} fps")
            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                raise RuntimeError("FFmpeg is required to finish generated video.")
            # Identity-safe generation deliberately avoids FFmpeg's motion-
            # compensated interpolation. It can invent malformed in-between
            # faces and hands. LTX owns the motion; FFmpeg only retimes/duplicates
            # frames to the requested delivery rate.
            finish_tail = (
                f"trim=duration={duration:.6f},setpts=PTS-STARTPTS,"
                f"scale={width}:{height}:flags=lanczos,format=yuv420p"
            )
            interpolation = (
                "tpad=stop_mode=clone:stop_duration=1,"
                f"fps={target_fps}:round=near,"
                f"{finish_tail}"
            ) if target_fps > base_fps else (
                f"tpad=stop_mode=clone:stop_duration=1,fps={target_fps},{finish_tail}"
            )
            run([
                ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                "-vf", interpolation, "-t", f"{duration:.6f}", "-an", "-c:v", "libx264",
                "-preset", "medium", "-crf", "18", "-movflags", "+faststart", str(output),
            ])
        output_meta = validate_media_output(output, width, height, duration)
        if float(output_meta.get("duration") or 0) < duration - (1.0 / target_fps):
            raise RuntimeError(
                f"Generated video is short: {output_meta.get('duration', 0):.3f}s "
                f"of {duration:.3f}s."
            )
        identity_restoration: dict[str, Any] = {"applied": False, "reason": "not requested"}
        if profile == "identity" and input_image and subject_scale in {"portrait", "medium"}:
            progress(89, "Stabilizing reference identity")
            identity_restoration = restore_reference_identity_video(
                output,
                input_image,
                _yunet_model(root),
            )
            if subject_scale == "portrait" and not identity_restoration.get("applied"):
                raise RuntimeError(
                    "Identity restoration could not track enough frames. Use a clearer front-facing image, "
                    "reduce subject motion, or switch Generation Priority to Scene Realism."
                )
        visual_metrics = validate_generated_video(
            output,
            face_model=_yunet_model(root),
            face_recognition_model=_sface_model(root),
            reference_image=input_image,
            identity_safe=profile == "identity",
            reference_has_face=bool(reference_metadata.get("faceDetected")),
            reference_face_area=float(reference_metadata.get("preparedFaceArea") or 0.0),
        )
        elapsed = time.monotonic() - started
        metadata_path = output.with_suffix(output.suffix + ".json")
        metadata_path.write_text(json.dumps({
            "engine": "TonyFX Local Video",
            "backend": "Diffusers LTX-Video",
            "model": model,
            "quantizedTextEncoder": quantized_text_encoder,
            "prompt": prompt,
            "negativePrompt": negative,
            "seed": int(args.seed),
            "quality": quality,
            "steps": steps,
            "width": width,
            "height": height,
            "duration": duration,
            "fps": target_fps,
            "baseFps": base_fps,
            "generatedFrames": frames,
            "generationProfile": profile,
            "referencePreparation": reference_metadata,
            "identityRestoration": identity_restoration,
            "elapsedSeconds": round(elapsed, 2),
            "validation": visual_metrics,
        }, indent=2), encoding="utf-8")
        progress(100, "Generated video validated and ready")
        emit(
            "result", ok=True, output=str(output), preview=str(output), outputs=[str(output)],
            backend=f"TonyFX LTX-Video | {model}", seed=int(args.seed), metadata=str(metadata_path),
            width=output_meta["width"], height=output_meta["height"], duration=output_meta["duration"],
            elapsed=round(elapsed, 2),
        )
    finally:
        del pipeline
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def self_test(args: argparse.Namespace) -> None:
    root = engine_root(args.engine_root)
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        fail("FFmpeg is required for the self-test.")
    with tempfile.TemporaryDirectory(prefix="tonyfx-selftest-") as temp_value:
        temp = Path(temp_value)
        source = temp / "source.mp4"
        output = temp / "enhanced.mp4"
        run([
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=320x320:rate=12:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ])
        test_args = argparse.Namespace(**vars(args))
        test_args.input = str(source)
        test_args.output = str(output)
        test_args.start = 0
        test_args.duration = 0
        test_args.width = 384
        test_args.height = 384
        test_args.scale = 1.0
        test_args.denoise = 12
        test_args.detail = 18
        test_args.sharpen = 12
        test_args.dehalo = 0
        test_args.deblur = 5
        test_args.compression = 8
        test_args.grain = 0
        test_args.interpolate = False
        test_args.target_fps = 24
        test_args.codec = "h264"
        test_args.ai = False
        enhance_with_ffmpeg(source, output, ffprobe(source), test_args)
        if not output.exists() or output.stat().st_size < 1024:
            fail("Local engine self-test did not create a valid video.")
        emit("result", ok=True, message="TonyFX local engine self-test passed.", engineRoot=str(root), bytes=output.stat().st_size)


def analyze_reference_command(args: argparse.Namespace) -> None:
    from reference_analyzer import _write_html, analyze_reference
    from replica_contract import compile_builder_contract, validate_builder_contract
    from replica_lab_bridge import run_reference_stack
    from vision_engine import enrich_analysis, prepare_analysis_source

    source = Path(args.input).resolve()
    destination = Path(args.output_dir).resolve()
    analysis_source, normalization = prepare_analysis_source(
        source, destination / "normalized", progress, force_proxy=args.accuracy == "deep"
    )
    inventory = []
    if getattr(args, "effect_inventory", ""):
        inventory_path = Path(args.effect_inventory)
        if inventory_path.exists():
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    feedback_path = Path(args.feedback) if getattr(args, "feedback", "") else engine_root(getattr(args, "engine_root", "")) / "analysis" / "reference-feedback.json"
    report = analyze_reference(
        analysis_source,
        destination,
        width=max(240, int(args.width)),
        accuracy=args.accuracy,
        analyze_audio=bool(args.audio),
        ocr=bool(args.ocr),
        deep_flow=bool(args.deep_flow),
        effect_inventory=inventory,
        feedback_path=feedback_path,
        face_model_path=engine_root(getattr(args, "engine_root", "")) / "models" / "analysis" / "face_detection_yunet_2023mar.onnx",
        progress=lambda percent, message: progress(percent * 0.66, message),
    )
    expected_frames = int((report.get("media") or {}).get("frames") or 0)
    decoded_frames = int((report.get("summary") or {}).get("decodedFrameCount") or 0)
    if expected_frames > 12 and decoded_frames < expected_frames * 0.88 and analysis_source == source:
        progress(3, f"Decoder stopped at {decoded_frames}/{expected_frames} frames; retrying through a repaired CFR proxy")
        retry_source, retry_normalization = prepare_analysis_source(
            source, destination / "normalized-retry", progress, force_proxy=True
        )
        if retry_source != source:
            analysis_source, normalization = retry_source, retry_normalization
            report = analyze_reference(
                analysis_source,
                destination,
                width=max(240, int(args.width)),
                accuracy=args.accuracy,
                analyze_audio=bool(args.audio),
                ocr=bool(args.ocr),
                deep_flow=bool(args.deep_flow),
                effect_inventory=inventory,
                feedback_path=feedback_path,
                face_model_path=engine_root(getattr(args, "engine_root", "")) / "models" / "analysis" / "face_detection_yunet_2023mar.onnx",
                progress=lambda percent, message: progress(percent * 0.66, message),
            )
            report.setdefault("summary", {}).setdefault("warnings", []).append("The original decoder truncated the reference; TonyFX rebuilt and analyzed a repaired CFR proxy.")
    report["sourceMedia"] = {"original": str(source), "analyzed": str(analysis_source), "normalization": normalization}
    if bool(getattr(args, "replica_lab", False)):
        report["replicaLab"] = run_reference_stack(
            analysis_source,
            destination,
            str((report.get("media") or {}).get("fpsRational") or (report.get("media") or {}).get("fps") or 30),
            has_audio=bool((report.get("media") or {}).get("hasAudio")),
            progress=lambda percent, message: progress(66 + percent * 0.20, message),
        )
    else:
        report["replicaLab"] = {
            "available": False,
            "reason": "Replica Lab provider routing was not requested. Re-run Deep analysis before an Exact Replica build.",
            "providerTrace": [],
        }
    song_source = Path(args.song_source).resolve() if getattr(args, "song_source", "") else None
    if song_source:
        try:
            from song_match import match_song_source
            ffmpeg = resolve_executable("ffmpeg.exe" if os.name == "nt" else "ffmpeg", engine_root(getattr(args, "engine_root", "")))
            report["audioAlignment"] = match_song_source(
                analysis_source, song_source, destination / "song-alignment", ffmpeg,
                lambda percent, message: progress(68 + percent * 0.10, message),
            )
        except Exception as error:
            report["audioAlignment"] = {"available": False, "source": str(song_source), "reason": f"Song matching failed without stopping visual analysis: {error}"}
        report.setdefault("editBlueprint", {})["audioAlignment"] = report["audioAlignment"]
    if bool(getattr(args, "vision", True)):
        catalog_path = Path(args.footage_catalog).resolve() if getattr(args, "footage_catalog", "") else None
        try:
            report = enrich_analysis(
                report, analysis_source, destination, catalog_path,
                lambda percent, message: progress(86 + max(0, min(14, (percent - 70) * 14 / 26)), message),
            )
        except Exception as error:
            report["visionEngine"] = {"available": False, "error": str(error), "fallback": "Core OpenCV and audio analysis completed successfully."}
            report.setdefault("summary", {}).setdefault("warnings", []).append(f"Optional vision enrichment failed and was skipped: {error}")
    report["replicaBuilderContract"] = compile_builder_contract(report)
    contract_issues = validate_builder_contract(report["replicaBuilderContract"])
    if contract_issues:
        report["replicaBuilderContract"].setdefault("buildGate", {})["exactReady"] = False
        report["replicaBuilderContract"]["buildGate"]["contractIssues"] = contract_issues
    report.setdefault("editBlueprint", {})["replicaBuilderContract"] = report["replicaBuilderContract"]
    report["editBlueprint"]["version"] = 6
    manifest_path = Path(report["manifest"])
    manifest_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_html(report, Path(report["htmlReport"]))
    emit(
        "result",
        ok=True,
        output=str(report["manifest"]),
        manifest=str(report["manifest"]),
        htmlReport=str(report["htmlReport"]),
        contactSheet=str(report["contactSheet"]),
        media=report["media"],
        summary=report["summary"],
        events=report["events"],
        cutEvents=report.get("cutEvents", []),
        effectEvents=report.get("effectEvents", []),
        shots=report.get("shots", []),
        repeats=report.get("repeats", []),
        editBlueprint=report.get("editBlueprint", {}),
        repairPlan=report.get("repairPlan", {}),
        framingQA=report.get("framingQA", []),
        semanticShotRequirements=report.get("semanticShotRequirements", []),
        narrativeMap=report.get("narrativeMap", {}),
        effectInventory=report.get("effectInventory", {}),
        audioStructure=report.get("audioStructure", {}),
        visionEngine=report.get("visionEngine", {}),
        footageIndex=report.get("footageIndex", {}),
        visionShotQA=report.get("visionShotQA", []),
        transitionForensics=report.get("transitionForensics", {}),
        replicaLab=report.get("replicaLab", {}),
        replicaBuilderContract=report.get("replicaBuilderContract", {}),
        transNetV2=report.get("transNetV2", {}),
        sourceMedia=report.get("sourceMedia", {}),
        audio=report["audio"],
        audioAlignment=report.get("audioAlignment", {}),
    )


def compare_edit_command(args: argparse.Namespace) -> None:
    from reference_analyzer import analyze_reference
    from reference_intelligence import build_repair_plan, compare_analysis_reports

    reference_path = Path(args.reference_report).resolve()
    if not reference_path.exists():
        fail("The reference analysis report could not be found.")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    destination = Path(args.output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    progress(4, "Analyzing the finished edit")
    reference_settings = reference.get("settings", {})
    candidate = analyze_reference(
        Path(args.candidate).resolve(), destination / "candidate-analysis",
        width=max(240, int(reference_settings.get("width") or args.width)), accuracy=str(reference_settings.get("accuracy") or "deep"), analyze_audio=False,
        ocr=False, deep_flow=bool(reference_settings.get("deepFlow", True)),
        face_model_path=engine_root(getattr(args, "engine_root", "")) / "models" / "analysis" / "face_detection_yunet_2023mar.onnx",
        progress=lambda percent, message: progress(4 + percent * 0.82, message),
    )
    comparison = compare_analysis_reports(reference, candidate)
    comparison["repairPlan"] = build_repair_plan(reference, comparison)
    comparison["referenceReport"] = str(reference_path)
    comparison["candidateReport"] = str(candidate["manifest"])
    comparison["autoRepair"] = {
        "version": 1,
        "timelineOffset": float(getattr(args, "timeline_offset", 0) or 0),
        "shots": [{"index": item.get("index"), "startTime": item.get("startTime"), "endTime": item.get("endTime"), "durationFrames": item.get("durationFrames")} for item in reference.get("shots", [])],
        "events": [{"time": item.get("time"), "family": item.get("family"), "graph": item.get("graph"), "curve": item.get("curve"), "durationFrames": item.get("durationFrames")} for item in reference.get("events", [])],
        "muteSceneAudio": True,
        "nonDestructive": True,
    }
    output = destination / "finished-edit-comparison.json"
    output.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")
    progress(100, "Finished-edit comparison complete")
    emit("result", ok=True, output=str(output), comparison=comparison, repairPlan=comparison["repairPlan"])


def score_ae_candidates_command(args: argparse.Namespace) -> None:
    from vision_engine import score_ae_candidates
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8-sig"))
    result = score_ae_candidates(Path(args.reference).resolve(), float(args.event_time), float(args.duration), candidates)
    output = Path(args.output).resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    emit("result", ok=True, output=str(output), scoring=result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TonyFX local media engine")
    parser.add_argument("--engine-root", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--engine-root", default=argparse.SUPPRESS)

    enhance_parser = subparsers.add_parser("enhance")
    # Keep cached TonyFX panels compatible with the corrected global-option
    # ordering. Fresh panels place --engine-root before the subcommand.
    enhance_parser.add_argument("--engine-root", default=argparse.SUPPRESS)
    enhance_parser.add_argument("--input", required=True)
    enhance_parser.add_argument("--output", required=True)
    enhance_parser.add_argument("--start", type=float, default=0)
    enhance_parser.add_argument("--duration", type=float, default=0)
    enhance_parser.add_argument("--width", type=int, default=2160)
    enhance_parser.add_argument("--height", type=int, default=2160)
    enhance_parser.add_argument("--scale", type=float, default=2.0)
    enhance_parser.add_argument("--model", default="realesrgan-x4plus")
    enhance_parser.add_argument("--preset", default="ultra")
    enhance_parser.add_argument("--compression", type=float, default=45)
    enhance_parser.add_argument("--detail", type=float, default=42)
    enhance_parser.add_argument("--sharpen", type=float, default=28)
    enhance_parser.add_argument("--denoise", type=float, default=12)
    enhance_parser.add_argument("--dehalo", type=float, default=8)
    enhance_parser.add_argument("--deblur", type=float, default=32)
    enhance_parser.add_argument("--grain", type=float, default=0)
    enhance_parser.add_argument("--target-fps", type=float, default=30)
    enhance_parser.add_argument("--tile", type=int, default=256)
    enhance_parser.add_argument("--codec", choices=("prores", "h264"), default="prores")
    enhance_parser.add_argument("--ai", action=argparse.BooleanOptionalAction, default=True)
    enhance_parser.add_argument("--interpolate", action=argparse.BooleanOptionalAction, default=False)
    enhance_parser.add_argument("--stabilize", action=argparse.BooleanOptionalAction, default=False)

    audio_parser = subparsers.add_parser("audio")
    audio_parser.add_argument("--engine-root", default=argparse.SUPPRESS)
    audio_parser.add_argument("--input", required=True)
    audio_parser.add_argument("--output", required=True)
    audio_parser.add_argument("--start", type=float, default=0)
    audio_parser.add_argument("--duration", type=float, default=0)
    audio_parser.add_argument("--operation", choices=("remove-background", "voice", "background", "vocals", "instrumental", "stems", "cleanup"), default="remove-background")
    audio_parser.add_argument("--denoise", type=float, default=28)
    audio_parser.add_argument("--dereverb", type=float, default=15)
    audio_parser.add_argument("--dehum", type=float, default=10)
    audio_parser.add_argument("--presence", type=float, default=28)
    audio_parser.add_argument("--clarity", type=float, default=22)
    audio_parser.add_argument("--compression", type=float, default=24)
    audio_parser.add_argument("--deess", type=float, default=18)
    audio_parser.add_argument("--highpass", type=float, default=65)
    audio_parser.add_argument("--lowpass", type=float, default=17500)
    audio_parser.add_argument("--normalize", action=argparse.BooleanOptionalAction, default=True)
    audio_parser.add_argument("--demucs-model", default="htdemucs")

    image_parser = subparsers.add_parser("generate-image")
    image_parser.add_argument("--engine-root", default=argparse.SUPPRESS)
    image_parser.add_argument("--prompt", required=True)
    image_parser.add_argument("--negative-prompt", default="")
    image_parser.add_argument("--output", required=True)
    image_parser.add_argument("--model", default="Lykon/dreamshaper-8")
    image_parser.add_argument("--width", type=int, default=1024)
    image_parser.add_argument("--height", type=int, default=1024)
    image_parser.add_argument("--steps", type=int, default=28)
    image_parser.add_argument("--guidance", type=float, default=6.5)
    image_parser.add_argument("--seed", type=int, default=12345)
    image_parser.add_argument("--strength", type=float, default=0.72)
    image_parser.add_argument("--input-image", default="")
    image_parser.add_argument("--mask", default="")

    video_parser = subparsers.add_parser("generate-video")
    video_parser.add_argument("--engine-root", default=argparse.SUPPRESS)
    video_parser.add_argument("--prompt", required=True)
    video_parser.add_argument("--negative-prompt", default="")
    video_parser.add_argument("--output", required=True)
    video_parser.add_argument("--model", default="Lightricks/LTX-Video")
    video_parser.add_argument("--backend", choices=("ltx", "framepack"), default="ltx")
    video_parser.add_argument("--width", type=int, default=768)
    video_parser.add_argument("--height", type=int, default=512)
    video_parser.add_argument("--frames", type=int, default=49)
    video_parser.add_argument("--fps", type=int, default=24)
    video_parser.add_argument("--duration", type=float, default=3)
    video_parser.add_argument("--base-fps", type=int, default=16)
    video_parser.add_argument("--profile", choices=("identity", "realism", "fast"), default="identity")
    video_parser.add_argument("--reference-fit", choices=("face", "center", "contain"), default="face")
    video_parser.add_argument("--quality", choices=("draft", "fast", "balanced", "quality"), default="balanced")
    video_parser.add_argument("--steps", type=int, default=24)
    video_parser.add_argument("--guidance", type=float, default=3.0)
    video_parser.add_argument("--seed", type=int, default=12345)
    video_parser.add_argument("--input-image", default="")

    analyze_parser = subparsers.add_parser("analyze-reference")
    analyze_parser.add_argument("--input", required=True)
    analyze_parser.add_argument("--output-dir", required=True)
    analyze_parser.add_argument("--width", type=int, default=420)
    analyze_parser.add_argument("--accuracy", choices=("balanced", "deep"), default="balanced")
    analyze_parser.add_argument("--audio", action=argparse.BooleanOptionalAction, default=True)
    analyze_parser.add_argument("--ocr", action=argparse.BooleanOptionalAction, default=False)
    analyze_parser.add_argument("--deep-flow", action=argparse.BooleanOptionalAction, default=False)
    analyze_parser.add_argument("--effect-inventory", default="")
    analyze_parser.add_argument("--feedback", default="")
    analyze_parser.add_argument("--footage-catalog", default="")
    analyze_parser.add_argument("--vision", action=argparse.BooleanOptionalAction, default=False)
    analyze_parser.add_argument("--replica-lab", action=argparse.BooleanOptionalAction, default=False)
    analyze_parser.add_argument("--song-source", default="")

    vision_parser = subparsers.add_parser("vision-probe")
    vision_parser.add_argument("--engine-root", default=argparse.SUPPRESS)

    candidate_parser = subparsers.add_parser("score-ae-candidates")
    candidate_parser.add_argument("--reference", required=True)
    candidate_parser.add_argument("--event-time", type=float, required=True)
    candidate_parser.add_argument("--duration", type=float, required=True)
    candidate_parser.add_argument("--candidates", required=True)
    candidate_parser.add_argument("--output", required=True)

    compare_parser = subparsers.add_parser("compare-edit")
    compare_parser.add_argument("--reference-report", required=True)
    compare_parser.add_argument("--candidate", required=True)
    compare_parser.add_argument("--output-dir", required=True)
    compare_parser.add_argument("--width", type=int, default=420)
    compare_parser.add_argument("--timeline-offset", type=float, default=0)

    color_parser = subparsers.add_parser("color-match")
    color_parser.add_argument("--engine-root", default=argparse.SUPPRESS)
    color_parser.add_argument("--target", required=True)
    color_parser.add_argument("--reference", required=True)
    color_parser.add_argument("--output-dir", required=True)
    color_parser.add_argument("--target-start", type=float, default=0)
    color_parser.add_argument("--target-duration", type=float, default=0)
    color_parser.add_argument("--reference-start", type=float, default=0)
    color_parser.add_argument("--reference-duration", type=float, default=0)
    color_parser.add_argument("--samples", type=int, default=7)
    color_parser.add_argument("--strength", type=float, default=85)
    color_parser.add_argument("--mode", choices=("continuity", "look", "skin"), default="continuity")
    color_parser.add_argument("--lut-size", type=int, default=33)
    color_parser.add_argument("--match-tone", action=argparse.BooleanOptionalAction, default=True)
    color_parser.add_argument("--match-color", action=argparse.BooleanOptionalAction, default=True)
    color_parser.add_argument("--protect-skin", action=argparse.BooleanOptionalAction, default=True)
    color_parser.add_argument("--render-output", default="")

    subparsers.add_parser("self-test")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "probe":
            probe(args)
        elif args.command == "enhance":
            enhance(args)
        elif args.command == "audio":
            audio(args)
        elif args.command == "generate-image":
            generate_image(args)
        elif args.command == "generate-video":
            generate_video(args)
        elif args.command == "analyze-reference":
            analyze_reference_command(args)
        elif args.command == "compare-edit":
            compare_edit_command(args)
        elif args.command == "vision-probe":
            from vision_engine import probe as probe_vision
            emit("result", ok=True, **probe_vision())
        elif args.command == "score-ae-candidates":
            score_ae_candidates_command(args)
        elif args.command == "color-match":
            from color_match import run_color_match
            root = engine_root(getattr(args, "engine_root", ""))
            run_color_match(
                args,
                emit=emit,
                progress=progress,
                engine_root=root,
                ffmpeg=resolve_executable("ffmpeg.exe" if os.name == "nt" else "ffmpeg", root),
            )
        elif args.command == "self-test":
            self_test(args)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        fail(f"Local engine command failed ({error.returncode}). {detail[-1200:]}")
    except KeyboardInterrupt:
        fail("Local engine task cancelled.", 130)
    except Exception as error:
        fail(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
