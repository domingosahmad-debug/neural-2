#!/usr/bin/env python3
"""Cost-aware bridge from TonyFX Analyze to the canonical TFX Replica Lab.

TonyFX keeps its fast OpenCV/forensics pass because it is useful for panel
feedback.  Deep Analyze additionally runs the independent Replica Lab
providers and stores their disagreements instead of letting one detector
silently win.  The resulting bundle is evidence for the builder contract; it
is never treated as recovered After Effects metadata.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable


Progress = Callable[[float, str], None]


def _candidate_roots() -> list[Path]:
    values: list[Path] = []
    configured = os.environ.get("TONYFX_REPLICA_LAB_ROOT", "").strip()
    if configured:
        values.append(Path(configured))
    source_root = Path(__file__).resolve().parents[2]
    values.append(source_root / "TFX_REPLICA_LAB")
    values.append(Path.home() / "Documents" / "New project" / "TFX_REPLICA_LAB")
    unique: list[Path] = []
    for value in values:
        resolved = value.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def locate_replica_lab() -> dict[str, Any]:
    for root in _candidate_roots():
        executable = root / ".venv" / "Scripts" / "tfx-replica.exe"
        registry = root / "profiles" / "installed-stack.json"
        if executable.exists() and registry.exists():
            return {"available": True, "root": root, "executable": executable, "registry": registry}
    return {
        "available": False,
        "reason": "Canonical TFX_REPLICA_LAB executable or installed-stack registry was not found.",
        "searched": [str(path) for path in _candidate_roots()],
    }


def _run(executable: Path, arguments: list[str], *, cwd: Path) -> dict[str, Any]:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        creationflags=flags,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "unknown Replica Lab failure").strip()
        raise RuntimeError(f"{' '.join(arguments[:2])}: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"stdout": completed.stdout.strip()}


def run_reference_stack(
    media: Path,
    output_dir: Path,
    fps: str,
    *,
    has_audio: bool,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Run the canonical provider order and return its assembled evidence.

    All neural stages are sequential so the 8 GB laptop GPU is never asked to
    hold Beat This and TransNetV2 at the same time.  Footage indexing/Qwen and
    SEA-RAFT remain finalist-only stages and are not launched here.
    """

    progress = progress or (lambda _percent, _message: None)
    location = locate_replica_lab()
    if not location.get("available"):
        return location
    root: Path = location["root"]
    executable: Path = location["executable"]
    registry: Path = location["registry"]
    work = output_dir / "replica-lab"
    work.mkdir(parents=True, exist_ok=True)
    paths = {
        "audio": work / "audio.json",
        "visual": work / "visual.json",
        "transnet": work / "transnet.json",
        "consensus": work / "cut-consensus.json",
        "repeats": work / "repeats.json",
        "curves": work / "curves.json",
        "bundle": work / "reference-bundle.json",
    }
    stages: list[dict[str, Any]] = []
    try:
        progress(2, "Verifying the pinned exact-replica provider stack")
        doctor = _run(executable, ["doctor", "--registry", str(registry), "--verify-hashes"], cwd=root)
        if doctor.get("passed") is not True:
            raise RuntimeError("Replica Lab doctor did not pass every hash and provider check")
        stages.append({"provider": "doctor", "status": "used", "passed": True})

        if has_audio:
            progress(13, "Mapping beats and downbeats with Beat This")
            _run(executable, ["analyze-audio", str(media), str(fps), str(paths["audio"]), "--work-dir", str(work / "audio-work"), "--gpu", "cuda"], cwd=root)
            stages.append({"provider": "Beat This", "status": "used"})
        else:
            paths["audio"].write_text(json.dumps({"schema": "tfx.audio-analysis.v1", "provider": "none", "alignment_frame": 0, "events": []}, indent=2), encoding="utf-8")
            stages.append({"provider": "Beat This", "status": "skipped", "reason": "reference has no audio stream"})

        progress(31, "Measuring every native reference frame with OpenCV")
        _run(executable, ["analyze-visual", str(media), str(paths["visual"])], cwd=root)
        stages.append({"provider": "OpenCV native-frame metrics", "status": "used"})

        progress(49, "Running independent TransNetV2 boundary detection")
        _run(executable, ["analyze-transnet", str(media), str(paths["transnet"]), "--device", "cuda"], cwd=root)
        stages.append({"provider": "TransNetV2", "status": "used"})

        progress(65, "Preserving detector disagreements")
        _run(executable, ["cut-consensus", str(paths["visual"]), str(paths["transnet"]), str(paths["consensus"]), "--tolerance", "2"], cwd=root)
        stages.append({"provider": "cut-consensus", "status": "used"})

        progress(74, "Detecting exact forward and reverse repeat topology")
        _run(executable, ["detect-repeats", str(media), str(paths["transnet"]), str(paths["repeats"])], cwd=root)
        stages.append({"provider": "native-frame repeat topology", "status": "used"})

        progress(82, "Fitting a separate curve to every transition")
        _run(executable, ["fit-curves", str(paths["visual"]), str(paths["consensus"]), str(paths["curves"])], cwd=root)
        stages.append({"provider": "per-event curve fitter", "status": "used"})

        progress(91, "Assembling the frame-native reference contract")
        _run(
            executable,
            [
                "assemble-reference", str(media), str(paths["bundle"]),
                "--audio", str(paths["audio"]), "--visual", str(paths["visual"]),
                "--transnet", str(paths["transnet"]), "--consensus", str(paths["consensus"]),
                "--repeats", str(paths["repeats"]), "--curves", str(paths["curves"]),
            ],
            cwd=root,
        )
        bundle = json.loads(paths["bundle"].read_text(encoding="utf-8"))
        progress(100, "Replica Lab reference contract complete")
        return {
            "available": True,
            "schema": bundle.get("schema"),
            "root": str(root),
            "doctor": doctor,
            "providerTrace": stages,
            "bundlePath": str(paths["bundle"]),
            "bundle": bundle,
        }
    except Exception as error:
        return {
            "available": False,
            "root": str(root),
            "providerTrace": stages,
            "reason": str(error),
            "fallback": "TonyFX core forensics remain available, but Exact Replica build authorization is withheld.",
        }

