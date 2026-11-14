#!/usr/bin/env python3
"""Headless TonyFX adapter for the official Apache-2.0 FramePack backend."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def emit(kind: str, **payload: object) -> None:
    print(json.dumps({"type": kind, **payload}, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-root", required=True)
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args()

    backend = Path(args.backend_root).resolve()
    demo = backend / "demo_gradio.py"
    if not demo.exists():
        raise RuntimeError(f"FramePack source is missing: {demo}")

    os.chdir(backend)
    os.environ.setdefault("HF_HOME", str(backend / "hf_download"))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass
    sys.path.insert(0, str(backend))

    import numpy as np
    from PIL import Image

    # Execute the official inference half of the demo without its Gradio UI.
    # FramePack's public process generator only needs gr.update, represented by
    # a tiny neutral object here; this avoids installing a web server in TonyFX.
    source = demo.read_text(encoding="utf-8")
    source = source.split("\nquick_prompts =", 1)[0]
    source = source.replace(
        "import gradio as gr",
        "class _TonyFxGradioStub:\n"
        "    @staticmethod\n"
        "    def update(**kwargs): return kwargs\n"
        "gr = _TonyFxGradioStub()",
    )
    # The official demo loads the multi-shard Hunyuan text encoder with the
    # Transformers default loader. On 16 GB Windows systems that briefly keeps
    # both the checkpoint and initialized module in committed memory and can
    # terminate torch_cpu.dll halfway through shard two. Accelerate is already
    # part of FramePack's pinned runtime, so force the supported low-memory
    # loader for every Transformers model before executing the official entry
    # point. This changes loading behavior only; weights and inference remain
    # the official FramePack implementation.
    source = source.replace(
        "torch_dtype=torch.float16).cpu()",
        "torch_dtype=torch.float16, low_cpu_mem_usage=True).cpu()",
    )
    original_argv = list(sys.argv)
    sys.argv = [str(demo), "--server", "127.0.0.1"]
    try:
        emit("progress", percent=4, message="Loading FramePack identity models")
        namespace = {"__name__": "tonyfx_framepack_backend", "__file__": str(demo)}
        exec(compile(source, str(demo), "exec"), namespace)
    finally:
        sys.argv = original_argv

    process = namespace.get("process")
    if not callable(process):
        raise RuntimeError("The official FramePack process entry point was not found.")

    input_image = np.asarray(Image.open(args.input_image).convert("RGB"))
    seconds = max(1, min(5, int(round(args.seconds))))
    steps = max(20, min(35, int(args.steps)))
    expected_frames = seconds * 30
    output_file = ""
    emit("progress", percent=14, message="FramePack models ready; building coherent motion")
    for state in process(
        input_image,
        args.prompt,
        args.negative_prompt,
        int(args.seed),
        seconds,
        9,
        steps,
        1.0,
        10.0,
        0.0,
        4.0,
        False,
        16,
    ):
        if not isinstance(state, tuple):
            continue
        if state and isinstance(state[0], str) and state[0]:
            output_file = state[0]
        description = state[2] if len(state) > 2 and isinstance(state[2], str) else ""
        match = re.search(r"Total generated frames:\s*(\d+)", description)
        if match:
            generated = int(match.group(1))
            percent = 16 + min(70, int(70 * generated / max(1, expected_frames)))
            emit("progress", percent=percent, message=f"FramePack coherent motion {generated}/{expected_frames} frames")

    if not output_file:
        raise RuntimeError("FramePack ended without producing a video. Check the backend log for the model error.")
    resolved = (backend / output_file).resolve() if not Path(output_file).is_absolute() else Path(output_file).resolve()
    if not resolved.exists() or resolved.stat().st_size < 4096:
        raise RuntimeError("FramePack returned an invalid output file.")
    emit("framepack_result", output=str(resolved))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        emit("error", message=f"{type(error).__name__}: {error}")
        raise
