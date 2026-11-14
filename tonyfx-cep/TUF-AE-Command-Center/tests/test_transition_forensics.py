from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from transition_forensics import decompose_transition, enrich_events, match_dna, probe  # noqa: E402


class TransitionForensicsTest(unittest.TestCase):
    def slide_frames(self) -> list[np.ndarray]:
        frames = []
        for index in range(8):
            frame = np.full((180, 260, 3), (28, 45, 72), np.uint8)
            cv2.rectangle(frame, (28 + index * 18, 45), (112 + index * 18, 145), (230, 195, 80), -1)
            cv2.circle(frame, (74 + index * 18, 78), 18, (245, 245, 245), -1)
            frames.append(frame)
        return frames

    def metrics(self, frames: list[np.ndarray]) -> list[dict[str, float]]:
        result = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            result.append({"luma": float(gray.mean()), "black": float(np.mean(gray < 18)), "white": float(np.mean(gray > 238)), "sharp": float(cv2.Laplacian(gray, cv2.CV_32F).var())})
        return result

    def test_transition_decomposition_has_measured_parameters(self) -> None:
        frames = self.slide_frames()
        event = {"frame": 4, "startFrame": 1, "endFrame": 6, "stableFrames": [0, 7], "durationFrames": 6}
        evidence = decompose_transition(frames, event, 30.0, self.metrics(frames), use_deep_flow=False)
        self.assertTrue(evidence["available"])
        self.assertIn("transform", evidence)
        self.assertIn("flowTrajectory", evidence)
        self.assertIn("dnaMatches", evidence)
        self.assertEqual(len(evidence["dnaVector"]), 11)
        self.assertGreater(evidence["transform"]["travelPx"], 20)
        self.assertTrue(any(item.startswith(("slide_", "whip_")) for item in evidence["measuredFamilies"]))
        self.assertTrue(any(item.get("effect") == "Motion Tile" for item in evidence["aeRecipe"]))

    def test_enrichment_is_non_destructive_and_dna_is_ranked(self) -> None:
        frames = self.slide_frames()
        events = [{"frame": 4, "startFrame": 1, "endFrame": 6, "stableFrames": [0, 7], "durationFrames": 6, "family": "hard_cut", "componentFamilies": ["hard_cut"], "aeRecipe": [], "candidateScores": []}]
        with tempfile.TemporaryDirectory(prefix="tonyfx-dna-") as temp_value:
            result = enrich_events(frames, events, 30.0, self.metrics(frames), accuracy="balanced", deep_flow=False, dna_path=Path(temp_value) / "dna.json")
        self.assertEqual(result["eventCount"], 1)
        self.assertIn("forensics", events[0])
        self.assertTrue(events[0]["candidateScores"])
        self.assertTrue(match_dna(events[0]["forensics"]))

    def test_backend_probe_is_fast_and_descriptive(self) -> None:
        state = probe()
        self.assertTrue(state["ready"])
        for key in ("raft", "lightGlue", "transNetV2", "videoDepthAnything", "transitionDNA"):
            self.assertIn(key, state)


if __name__ == "__main__":
    unittest.main()

