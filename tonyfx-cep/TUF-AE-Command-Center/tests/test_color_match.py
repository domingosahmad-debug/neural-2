from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def make_fixture(path: Path, warm: bool) -> None:
    height, width = 360, 540
    yy, xx = np.mgrid[0:height, 0:width]
    base = np.zeros((height, width, 3), dtype=np.float32)
    base[..., 0] = 0.10 + xx / width * 0.46
    base[..., 1] = 0.14 + yy / height * 0.52
    base[..., 2] = 0.18 + (xx + yy) / (width + height) * 0.50
    cv2.circle(base, (width // 2, height // 2), 95, (0.46, 0.58, 0.74), -1)
    if warm:
        base = np.clip(base ** 0.78, 0, 1)
        # BGR: reduce blue, raise red and a little green.
        base *= np.asarray([0.72, 1.06, 1.34], dtype=np.float32)
        base = np.clip((base - 0.5) * 1.16 + 0.5, 0, 1)
    cv2.imwrite(str(path), (base * 255.0 + 0.5).astype(np.uint8))


def main() -> None:
    work = ROOT / "tests" / ".color-match-smoke"
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source.png"
    reference = work / "reference.png"
    output = work / "output"
    make_fixture(source, False)
    make_fixture(reference, True)
    command = [
        sys.executable,
        str(ROOT / "python" / "local_engine.py"),
        "--engine-root",
        str(Path.home() / "Documents" / "TonyFX Local Engine"),
        "color-match",
        "--target",
        str(source),
        "--reference",
        str(reference),
        "--output-dir",
        str(output),
        "--samples",
        "3",
        "--strength",
        "100",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode:
        raise AssertionError(completed.stderr or completed.stdout)
    payloads = []
    for line in completed.stdout.splitlines():
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    result = next(item for item in reversed(payloads) if item.get("type") == "result")
    assert result["ok"] is True
    assert result["metrics"]["afterError"] < result["metrics"]["beforeError"]
    assert result["metrics"]["improvementPercent"] > 25
    assert result["safe"] is True
    assert result["safety"]["matchedHighlightClipping"] < 5
    assert Path(result["lut"]).stat().st_size > 250000
    for preview in result["previews"].values():
        assert Path(preview).stat().st_size > 1000
    assert result["recipe"]["lumetri"]["exposure"] != 0
    assert 80 <= result["recipe"]["lumetri"]["saturation"] <= 128
    matrix = np.asarray(result["recipe"]["matrix"], dtype=np.float64)
    assert np.max(np.abs(matrix - np.diag(np.diag(matrix)))) < 1.0e-9
    print(json.dumps({"ok": True, "metrics": result["metrics"], "lumetri": result["recipe"]["lumetri"]}, indent=2))


if __name__ == "__main__":
    main()
