from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from vision_engine import candidate_motion_metadata  # noqa: E402


class VisionEnergyMatchingTests(unittest.TestCase):
    def _write_clip(self, path: Path, moving: bool) -> None:
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 180))
        self.assertTrue(writer.isOpened())
        for frame_index in range(90):
            frame = np.full((180, 320, 3), (28, 42, 68), np.uint8)
            x = 40 + (frame_index * 5 % 220 if moving else 80)
            cv2.rectangle(frame, (x, 46), (min(319, x + 58), 142), (235, 210, 110), -1)
            if moving and frame_index % 5 == 0:
                frame[:] = np.clip(frame.astype(np.int16) + 45, 0, 255).astype(np.uint8)
            writer.write(frame)
        writer.release()

    def test_action_sample_scores_higher_than_static_sample(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tonyfx-energy-test-") as value:
            root = Path(value)
            calm = root / "calm.mp4"
            action = root / "action.mp4"
            self._write_clip(calm, False)
            self._write_clip(action, True)
            calm_meta = candidate_motion_metadata(calm, 1.5, 0.0, 3.0)
            action_meta = candidate_motion_metadata(action, 1.5, 0.0, 3.0)
            self.assertTrue(calm_meta["available"])
            self.assertTrue(action_meta["available"])
            self.assertGreater(action_meta["motionScore"], calm_meta["motionScore"] + 0.18)
            self.assertIn(action_meta["shotScale"], {"close_up", "medium", "wide_or_detail"})


if __name__ == "__main__":
    unittest.main()
