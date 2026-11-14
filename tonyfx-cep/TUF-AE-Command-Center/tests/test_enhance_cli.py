from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import importlib.util
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "python" / "local_engine.py"
ENGINE_ROOT = Path.home() / "Documents" / "TonyFX Local Engine"


def load_worker_module():
    spec = importlib.util.spec_from_file_location("tonyfx_local_engine", WORKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORKER), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def assert_reaches_worker(result: subprocess.CompletedProcess[str], label: str) -> None:
    combined = result.stdout + result.stderr
    assert "unrecognized arguments" not in combined, f"{label} rejected engine-root ordering: {combined}"
    assert "Input media does not exist" in combined, f"{label} did not reach enhancement validation: {combined}"


def test_enhance_accepts_current_panel_order() -> None:
    result = invoke([
        "--engine-root", str(ENGINE_ROOT), "enhance",
        "--input", "missing-input.mp4", "--output", "missing-output.mp4",
    ])
    assert_reaches_worker(result, "current panel")


def test_enhance_accepts_cached_panel_order() -> None:
    result = invoke([
        "enhance", "--engine-root", str(ENGINE_ROOT),
        "--input", "missing-input.mp4", "--output", "missing-output.mp4",
    ])
    assert_reaches_worker(result, "cached panel")


def test_frame_process_reports_real_progress() -> None:
    worker = load_worker_module()
    with tempfile.TemporaryDirectory(prefix="tonyfx-progress-test-") as value:
        output = Path(value)
        producer = (
            "from pathlib import Path;import sys,time;"
            "p=Path(sys.argv[1]);"
            "[(p/f'frame_{i:08d}.png').write_bytes(b'x') and time.sleep(.9) for i in range(1,4)]"
        )
        worker.run_frame_process(
            [sys.executable, "-c", producer, str(output)],
            output,
            3,
            24,
            70,
            "Restored",
        )
        assert len(list(output.glob("*.png"))) == 3


def test_frame_sequence_rejects_missing_tiles() -> None:
    worker = load_worker_module()
    with tempfile.TemporaryDirectory(prefix="tonyfx-integrity-test-") as value:
        root = Path(value)
        inputs, outputs = root / "input", root / "output"
        inputs.mkdir(); outputs.mkdir()
        for index in range(1, 4):
            (inputs / f"frame_{index:08d}.png").write_bytes(b"frame")
        for index in range(1, 3):
            (outputs / f"frame_{index:08d}.png").write_bytes(b"frame")
        valid, reason = worker.validate_frame_sequence(inputs, outputs, 3, 2)
        assert not valid and "2/3" in reason


def test_preview_proxy_is_full_duration() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    worker = load_worker_module()
    with tempfile.TemporaryDirectory(prefix="tonyfx-preview-test-") as value:
        source = Path(value) / "master.mov"
        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "prores_ks", "-profile:v", "3", "-c:a", "pcm_s24le", str(source),
        ], check=True)
        preview = worker.create_preview_proxy(source)
        meta = worker.ffprobe(preview)
        assert meta["width"] <= 1080
        assert meta["duration"] >= 1.8


if __name__ == "__main__":
    test_enhance_accepts_current_panel_order()
    test_enhance_accepts_cached_panel_order()
    test_frame_process_reports_real_progress()
    test_frame_sequence_rejects_missing_tiles()
    test_preview_proxy_is_full_duration()
    print("Enhance CLI compatibility checks passed.")
