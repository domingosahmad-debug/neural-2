#!/usr/bin/env python3
"""Install or repair TonyFX local processing backends.

Heavy packages live in ``Documents/TonyFX Local Engine`` instead of the CEP
extension folder. Extension upgrades therefore never delete models or runtimes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile
from pathlib import Path
from typing import Any


REALESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
RIFE_URL = "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
FRAMEPACK_REPO = "https://github.com/lllyasviel/FramePack.git"
VISION_ROOT = Path.home() / "Documents" / "TonyFX Vision Engine"
VISION_REPOSITORIES = {
    "sam2": "https://github.com/facebookresearch/sam2.git",
    "co-tracker": "https://github.com/facebookresearch/co-tracker.git",
    "Depth-Anything-V2": "https://github.com/DepthAnything/Depth-Anything-V2.git",
    "dinov2": "https://github.com/facebookresearch/dinov2.git",
    "LightGlue": "https://github.com/cvg/LightGlue.git",
    "TransNetV2": "https://github.com/soCzech/TransNetV2.git",
    "Video-Depth-Anything": "https://github.com/DepthAnything/Video-Depth-Anything.git",
}
VISION_MODELS = {
    "sam2.1_hiera_small.pt": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
    "cotracker3_scaled_offline.pth": "https://huggingface.co/facebook/cotracker3/resolve/main/scaled_offline.pth",
    "depth_anything_v2_vits.pth": "https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth",
    "open_clip_vit_b32_laion2b.safetensors": "https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K/resolve/main/open_clip_model.safetensors",
    "dinov2_vits14_pretrain.pth": "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth",
    "yolo11n.pt": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt",
    "video_depth_anything_vits.pth": "https://huggingface.co/depth-anything/Video-Depth-Anything-Small/resolve/main/video_depth_anything_vits.pth",
}


def emit(kind: str, **payload: Any) -> None:
    print(json.dumps({"type": kind, **payload}, ensure_ascii=False), flush=True)


def progress(percent: int, message: str) -> None:
    emit("progress", percent=max(0, min(100, percent)), message=message)
    print(f"PROGRESS {max(0, min(100, percent))}", flush=True)


def root_path(value: str | None) -> Path:
    root = Path(value) if value else Path.home() / "Documents" / "TonyFX Local Engine"
    root.mkdir(parents=True, exist_ok=True)
    return root


def hidden_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        [str(item) for item in command],
        cwd=str(cwd) if cwd else None,
        check=True,
        env=env,
        creationflags=hidden_flags(),
    )


def download(url: str, destination: Path, start: int, end: int, label: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "TonyFX-Local-Engine/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            copied = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                copied += len(chunk)
                if total:
                    percent = start + int((end - start) * copied / total)
                    progress(percent, f"Downloading {label} ({copied // 1048576} / {total // 1048576} MB)")
    except Exception:
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not curl:
            raise
        run([curl, "-L", "--fail", "--retry", "3", "-C", "-", "-o", str(destination), url])


def install_archive(root: Path, name: str, url: str, executable: str, start: int, end: int) -> Path:
    destination = root / "bin" / name
    existing = list(destination.rglob(executable)) if destination.exists() else []
    if existing:
        progress(end, f"{name} is already installed")
        return existing[0]
    cache = root / "downloads"
    archive = cache / f"{name}.zip"
    if not archive.exists() or archive.stat().st_size < 1024:
        download(url, archive, start, max(start + 1, end - 4), name)
    progress(max(start + 1, end - 3), f"Installing {name}")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as bundle:
        bundle.extractall(destination)
    matches = list(destination.rglob(executable))
    if not matches:
        raise RuntimeError(f"{executable} was not found after extracting {name}.")
    progress(end, f"{name} installed")
    return matches[0]


def venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv(root: Path) -> Path:
    python = venv_python(root)
    if not python.exists():
        progress(18, "Creating isolated TonyFX AI runtime")
        venv.EnvBuilder(with_pip=True, clear=False).create(root / ".venv")
    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    return python


def ensure_torch(python: Path, root: Path) -> None:
    marker = root / "runtime" / "torch.ready"
    if marker.exists():
        return
    progress(30, "Installing the CUDA AI runtime (one-time setup)")
    run([str(python), "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu128"])
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ready\n", encoding="ascii")


def ensure_face_models(root: Path, start: int = 78, end: int = 86) -> None:
    models = root / "models" / "analysis"
    models.mkdir(parents=True, exist_ok=True)
    face_detector = models / "face_detection_yunet_2023mar.onnx"
    face_recognizer = models / "face_recognition_sface_2021dec.onnx"
    midpoint = start + max(1, (end - start) // 2)
    if not face_detector.exists() or face_detector.stat().st_size < 100_000:
        download(YUNET_URL, face_detector, start, midpoint, "YuNet face framing model")
    if not face_recognizer.exists() or face_recognizer.stat().st_size < 1_000_000:
        download(SFACE_URL, face_recognizer, midpoint, end, "SFace identity model")


def install_audio(root: Path) -> Path:
    python = ensure_venv(root)
    ensure_torch(python, root)
    progress(58, "Installing offline background removal and stem separation")
    # DeepFilterNet's Windows source package requires a separate Rust toolchain.
    # TonyFX does not call it for separation, so keep this runtime lean and
    # deterministic instead of failing the whole installer on an unused extra.
    run([str(python), "-m", "pip", "install", "demucs==4.0.1", "soundfile", "librosa"])
    (root / "models" / "audio").mkdir(parents=True, exist_ok=True)
    progress(82, "Background remover installed; the selected model downloads once on first use")
    return python


def install_generation(root: Path, include_video: bool) -> Path:
    python = ensure_venv(root)
    ensure_torch(python, root)
    progress(56, "Installing local diffusion runtime")
    # Main is used because current LTX pipelines can land ahead of PyPI releases.
    run([
        str(python), "-m", "pip", "install", "--upgrade",
        "git+https://github.com/huggingface/diffusers.git",
        "transformers", "accelerate", "safetensors", "huggingface_hub",
        "sentencepiece", "protobuf", "peft", "imageio[ffmpeg]", "bitsandbytes",
        "certifi", "truststore", "pip-system-certs",
    ])
    (root / "models" / "image").mkdir(parents=True, exist_ok=True)
    if include_video:
        (root / "models" / "video").mkdir(parents=True, exist_ok=True)
        ensure_face_models(root, 84, 90)
    progress(84, "Generation runtime installed; chosen models download on first use")
    return python


def install_framepack(root: Path) -> Path:
    """Install FramePack separately so its pinned stack cannot break LTX."""
    backend = root / "backends" / "FramePack"
    git = shutil.which("git")
    if not (backend / "demo_gradio.py").exists():
        if not git:
            raise RuntimeError("Git is required once to install FramePack Identity Quality.")
        backend.parent.mkdir(parents=True, exist_ok=True)
        progress(58, "Downloading the official FramePack backend")
        run([git, "clone", "--depth", "1", FRAMEPACK_REPO, str(backend)])
    elif git and (backend / ".git").exists():
        progress(59, "Updating the official FramePack backend")
        run([git, "pull", "--ff-only"], cwd=backend)

    # FramePack's 13B text encoder is unstable under the machine's Python
    # 3.12 torch_cpu runtime. Keep it in a dedicated Python 3.10 environment;
    # all other TonyFX engines retain their established environments.
    quality_venv = backend / ".venv-quality"
    framepack_python = quality_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not framepack_python.exists():
        uv_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        progress(61, "Creating the isolated FramePack Python 3.10 runtime")
        if uv_python.exists():
            run([str(uv_python), "-m", "pip", "install", "uv"])
            environment = dict(os.environ); environment["UV_SYSTEM_CERTS"] = "true"
            run([str(uv_python), "-m", "uv", "python", "install", "3.10"], env=environment)
            run([str(uv_python), "-m", "uv", "venv", "--python", "3.10", str(quality_venv)], env=environment)
        else:
            raise RuntimeError("TonyFX requires its base local runtime before installing FramePack.")
    marker = quality_venv / "tonyfx-framepack.ready"
    if not marker.exists():
        progress(64, "Installing FramePack CUDA dependencies")
        uv_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        environment = dict(os.environ); environment["UV_SYSTEM_CERTS"] = "true"
        run([
            str(uv_python), "-m", "uv", "pip", "install", "--python", str(framepack_python),
            "torch==2.6.0+cu126", "torchvision==0.21.0+cu126", "torchaudio==2.6.0+cu126",
            "accelerate==1.6.0", "diffusers==0.33.1", "transformers==4.46.2",
            "sentencepiece==0.2.0", "pillow==11.1.0", "av==12.1.0",
            "numpy==1.26.2", "scipy==1.12.0", "requests==2.31.0",
            "torchsde==0.2.6", "einops", "opencv-contrib-python==4.11.0.86", "safetensors",
            "certifi", "truststore", "pip-system-certs", "hf_xet",
            "--default-index", "https://pypi.org/simple", "--index", "https://download.pytorch.org/whl/cu126",
            "--index-strategy", "unsafe-best-match",
        ], env=environment)
        marker.write_text("ready\n", encoding="ascii")
    progress(86, "FramePack Identity Quality runtime installed")
    return framepack_python


def install_analysis(root: Path) -> Path:
    python = ensure_venv(root)
    ensure_torch(python, root)
    progress(46, "Installing offline reference forensics")
    run([
        str(python), "-m", "pip", "install", "--upgrade",
        "opencv-python-headless", "scenedetect", "scikit-image", "librosa", "soundfile",
        "lpips", "kornia", "open_clip_torch", "faiss-cpu", "rapidocr_onnxruntime",
        "tensorflow-cpu==2.20.0", "ffmpeg-python", "decord", "einops", "easydict", "scipy",
    ])
    ensure_face_models(root, 78, 86)
    install_vision_engine(python)
    progress(96, "Reference analyzer and local vision engine are ready")
    return python


def install_vision_engine(python: Path) -> None:
    packages = VISION_ROOT / "packages"; models = VISION_ROOT / "models"
    packages.mkdir(parents=True, exist_ok=True); models.mkdir(parents=True, exist_ok=True)
    progress(84, "Checking TonyFX vision repositories")
    git = shutil.which("git")
    for name, url in VISION_REPOSITORIES.items():
        target = packages / name
        if target.exists():
            continue
        if not git:
            raise RuntimeError("Git is required once to install the TonyFX vision repositories.")
        run([git, "clone", "--depth", "1", url, str(target)])
    progress(87, "Installing tracking, segmentation, and subject detection")
    environment = dict(os.environ); environment["SAM2_BUILD_CUDA"] = "0"
    run([str(python), "-m", "pip", "install", "hydra-core", "iopath", "av", "ultralytics", "nvidia-ml-py", "polars", "ultralytics-thop", "matplotlib", "psutil", "py-cpuinfo"], env=environment)
    run([str(python), "-m", "pip", "install", "--no-build-isolation", "-e", str(packages / "sam2")], env=environment)
    run([str(python), "-m", "pip", "install", "--no-build-isolation", "-e", str(packages / "co-tracker")], env=environment)
    run([str(python), "-m", "pip", "install", "--no-build-isolation", "-e", str(packages / "LightGlue")], env=environment)
    for index, (name, url) in enumerate(VISION_MODELS.items()):
        target = models / name
        if target.exists() and target.stat().st_size > 1_000_000:
            continue
        download(url, target, 89 + index, 90 + index, name)


def manifest(root: Path, profiles: list[str], python: Path | None) -> None:
    manifest_path = root / "engine.json"
    previous_profiles: list[str] = []
    if manifest_path.exists():
        try:
            previous_profiles = list(json.loads(manifest_path.read_text(encoding="utf-8")).get("profiles") or [])
        except Exception:
            previous_profiles = []
    merged_profiles = sorted(set(previous_profiles + profiles))
    payload = {
        "version": 1,
        "profiles": merged_profiles,
        "python": str(python) if python else "",
        "realEsrgan": [str(path) for path in root.rglob("realesrgan-ncnn-vulkan.exe")],
        "rife": [str(path) for path in root.rglob("rife-ncnn-vulkan.exe")],
        "modelPolicy": "Models are downloaded once on first use and then run fully offline.",
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install TonyFX local engines")
    parser.add_argument("--engine-root", default="")
    parser.add_argument("--profile", choices=("enhance", "audio", "analysis", "image", "video", "all"), default="all")
    args = parser.parse_args()
    root = root_path(args.engine_root)
    profiles: list[str] = []
    python: Path | None = None
    try:
        progress(2, "Checking TonyFX local engine")
        if args.profile in {"enhance", "all"}:
            install_archive(root, "Real-ESRGAN", REALESRGAN_URL, "realesrgan-ncnn-vulkan.exe", 4, 22)
            install_archive(root, "RIFE", RIFE_URL, "rife-ncnn-vulkan.exe", 22, 36)
            profiles.append("enhance")
        if args.profile in {"audio", "all"}:
            python = install_audio(root)
            profiles.append("audio")
        if args.profile in {"analysis", "all"}:
            python = install_analysis(root)
            profiles.append("analysis")
        if args.profile in {"image", "video", "all"}:
            python = install_generation(root, args.profile in {"video", "all"})
            profiles.append("image")
            if args.profile in {"video", "all"}:
                install_framepack(root)
                profiles.append("video")
                profiles.append("video-framepack")
        manifest(root, profiles, python)
        progress(100, "TonyFX local engine is ready")
        emit("result", ok=True, engineRoot=str(root), python=str(python or sys.executable), profiles=profiles)
    except subprocess.CalledProcessError as error:
        emit("error", message=f"Installer command failed with exit code {error.returncode}.")
        raise SystemExit(error.returncode)
    except Exception as error:
        emit("error", message=f"{type(error).__name__}: {error}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
