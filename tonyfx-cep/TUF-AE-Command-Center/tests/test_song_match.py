from __future__ import annotations

import shutil
import tempfile
import unittest
import wave
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from song_match import _media_candidates, match_song_source  # noqa: E402


class SongMatchTest(unittest.TestCase):
    sample_rate = 22050

    def write_wav(self, path: Path, samples: np.ndarray) -> None:
        pcm = np.asarray(np.clip(samples, -0.98, 0.98) * 32767.0, dtype="<i2")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(pcm.tobytes())

    def musical_signal(self, seconds: float) -> np.ndarray:
        count = int(seconds * self.sample_rate)
        time = np.arange(count, dtype=np.float32) / self.sample_rate
        result = np.zeros(count, dtype=np.float32)
        for second in range(int(seconds)):
            start = second * self.sample_rate
            end = min(count, (second + 1) * self.sample_rate)
            local = time[start:end] - float(second)
            root = 96.0 + second * 4.37 + (second % 5) * 11.13
            result[start:end] += 0.28 * np.sin(2 * np.pi * root * local)
            result[start:end] += 0.18 * np.sin(2 * np.pi * root * 1.5 * local + 0.2 * second)
            result[start:end] += 0.12 * np.sin(2 * np.pi * root * 2.0 * local + 0.4)
            for beat in (0.0, 0.25, 0.5, 0.75):
                envelope = np.exp(-42.0 * np.maximum(0.0, local - beat)) * (local >= beat)
                result[start:end] += 0.16 * envelope * np.sin(2 * np.pi * (850 + 17 * second) * local)
        return result

    def test_folder_scan_and_exact_excerpt_alignment(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("FFmpeg is required for the song-alignment integration test.")
        with tempfile.TemporaryDirectory(prefix="tonyfx-song-match-test-") as value:
            temp = Path(value)
            songs = temp / "songs"
            songs.mkdir()
            song = self.musical_signal(36.0)
            song_path = songs / "clean-song.wav"
            self.write_wav(song_path, song)
            self.write_wav(songs / "wrong-song.wav", self.musical_signal(24.0)[::-1])

            intro_seconds = 3.0
            song_start_seconds = 9.0
            excerpt_seconds = 18.0
            intro = np.random.default_rng(19).normal(0.0, 0.015, int(intro_seconds * self.sample_rate)).astype(np.float32)
            first = int(song_start_seconds * self.sample_rate)
            last = first + int(excerpt_seconds * self.sample_rate)
            reference = np.concatenate([intro, song[first:last]])
            reference_path = temp / "reference.wav"
            self.write_wav(reference_path, reference)

            self.assertEqual({item.name for item in _media_candidates(songs)}, {"clean-song.wav", "wrong-song.wav"})
            result = match_song_source(reference_path, songs, temp / "analysis", ffmpeg)
            self.assertTrue(result["available"])
            self.assertTrue(result["accepted"])
            self.assertEqual(result["songName"], "clean-song.wav")
            self.assertGreaterEqual(result["confidence"], 0.52)
            expected_start = result["referenceStart"] - result["songStart"] / result["speedRatio"]
            self.assertAlmostEqual(result["timelineLayerStart"], expected_start, delta=0.02)
            self.assertAlmostEqual(result["timelineLayerStart"], intro_seconds - song_start_seconds, delta=1.2)


if __name__ == "__main__":
    unittest.main()
