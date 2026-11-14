#!/usr/bin/env python3
"""Run Demucs with a Windows-safe WAV writer.

Recent Torchaudio releases route ``save`` through TorchCodec, whose Windows
wheel depends on separately discoverable FFmpeg DLLs. TonyFX already provides
FFmpeg and only needs deterministic WAV stems, so SoundFile is the smaller and
more reliable writer.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torchaudio


def save_wav(
    uri: str | Path,
    src,
    sample_rate: int,
    *,
    channels_first: bool = True,
    format: str | None = None,
    encoding: str | None = None,
    bits_per_sample: int | None = None,
    **_kwargs,
) -> None:
    audio = src.detach().cpu().float().numpy()
    if channels_first:
        audio = audio.T
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    subtype = "PCM_24" if bits_per_sample == 24 else "FLOAT"
    sf.write(str(uri), audio, int(sample_rate), format="WAV", subtype=subtype)


torchaudio.save = save_wav
sys.argv[0] = "demucs"
runpy.run_module("demucs", run_name="__main__")
