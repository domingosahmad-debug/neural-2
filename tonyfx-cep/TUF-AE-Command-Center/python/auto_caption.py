#!/usr/bin/env python3
"""Offline multilingual caption worker for TonyFX.

The CEP panel invokes this script with a selected AE layer's visible source range.
It never uploads media and emits compact JSON for editable After Effects layers.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel


def progress(value: int) -> None:
    print(f"PROGRESS {max(0, min(100, int(value)))}", flush=True)


def extract_audio(source: Path, start: float, duration: float, destination: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for trimmed offline transcription")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ss",
        f"{max(0.0, start):.6f}",
        "-t",
        f"{max(0.1, duration):.6f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg audio extraction failed")


def load_model(model_path: str) -> tuple[WhisperModel, str]:
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return WhisperModel(model_path, device="cuda", compute_type="float16"), "cuda"
    except Exception:
        pass
    return WhisperModel(model_path, device="cpu", compute_type="int8"), "cpu"


def clean_word(value: str) -> str:
    return " ".join((value or "").strip().split())


def group_words(words: list[dict], maximum_words: int) -> list[dict]:
    captions: list[dict] = []
    current: list[dict] = []
    terminal = (".", "!", "?", "\u061f", "\u061b")

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = " ".join(item["text"] for item in current).strip()
        if text:
            captions.append(
                {
                    "start": round(float(current[0]["start"]), 4),
                    "end": round(float(current[-1]["end"]), 4),
                    "text": text,
                    "words": current,
                }
            )
        current = []

    for word in words:
        current.append(word)
        duration = float(current[-1]["end"]) - float(current[0]["start"])
        punctuation = word["text"].endswith(terminal)
        if len(current) >= maximum_words or duration >= 2.8 or (punctuation and len(current) >= 2):
            flush()
    flush()
    return captions


def normalize_word_timing(words: list[dict], duration: float) -> list[dict]:
    """Keep Whisper timestamps monotonic and inside the extracted audio range."""
    normalized: list[dict] = []
    previous_start = 0.0
    for item in sorted(words, key=lambda entry: (float(entry["start"]), float(entry["end"]))):
        start = max(previous_start, min(float(duration), float(item["start"])))
        if start >= float(duration):
            continue
        end = min(float(duration), max(start + 0.02, float(item["end"])))
        if end <= start:
            continue
        cleaned = dict(item)
        cleaned["start"] = round(start, 4)
        cleaned["end"] = round(end, 4)
        normalized.append(cleaned)
        previous_start = start
    return normalized


def transcribe_words(
    model: WhisperModel,
    audio_path: Path,
    language: str | None,
    duration: float,
) -> tuple[list[dict], object]:
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        best_of=5,
        temperature=0.0,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 280, "speech_pad_ms": 180},
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    words: list[dict] = []
    for segment in segments:
        for token in segment.words or []:
            text = clean_word(token.word)
            if not text:
                continue
            words.append(
                {
                    "start": round(max(0.0, float(token.start)), 4),
                    "end": round(max(float(token.start) + 0.02, float(token.end)), 4),
                    "text": text,
                    "probability": round(float(token.probability or 0.0), 4),
                }
            )
        progress(35 + int(min(1.0, float(segment.end) / duration) * 55))
    return words, info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--language", default="auto", choices=("auto", "en", "ar"))
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--words", type=int, default=4)
    args = parser.parse_args()

    source = Path(args.input)
    model_path = Path(args.model)
    output = Path(args.output)
    if not source.is_file():
        raise FileNotFoundError(f"Input media not found: {source}")
    if not model_path.exists():
        raise FileNotFoundError(f"Whisper model not found: {model_path}")

    progress(5)
    temporary = Path(tempfile.mkdtemp(prefix="tonyfx-caption-"))
    audio_path = temporary / "selection.wav"
    try:
        extract_audio(source, args.start, args.duration, audio_path)
        progress(14)
        model, device = load_model(str(model_path))
        progress(32)
        language = None if args.language == "auto" else args.language
        duration = max(0.1, float(args.duration))
        try:
            words, info = transcribe_words(model, audio_path, language, duration)
        except RuntimeError as error:
            gpu_runtime_missing = device == "cuda" and any(
                token in str(error).lower() for token in ("cuda", "cublas", "cudnn")
            )
            if not gpu_runtime_missing:
                raise
            del model
            gc.collect()
            progress(34)
            model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
            device = "cpu-fallback"
            words, info = transcribe_words(model, audio_path, language, duration)

        words = normalize_word_timing(words, duration)
        captions = group_words(words, max(1, min(10, int(args.words))))
        result = {
            "ok": True,
            "language": getattr(info, "language", None) or args.language,
            "languageProbability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
            "device": device,
            "source": str(source),
            "sourceStart": round(float(args.start), 4),
            "sourceDuration": round(float(args.duration), 4),
            "captions": captions,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        progress(100)
        return 0
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"TonyFX caption error: {error}", file=sys.stderr, flush=True)
        raise
