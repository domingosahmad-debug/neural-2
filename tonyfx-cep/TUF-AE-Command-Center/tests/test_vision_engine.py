from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from vision_engine import build_footage_index, prepare_analysis_source, probe, search_index  # noqa: E402


class VisionEngineTest(unittest.TestCase):
    def build_video(self, target: Path) -> None:
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"mp4v"), 12, (224, 224))
        self.assertTrue(writer.isOpened())
        for index in range(24):
            frame = np.full((224, 224, 3), (35, 70, 145), np.uint8)
            cv2.circle(frame, (70 + index * 3, 110), 42, (235, 210, 160), -1)
            cv2.rectangle(frame, (130, 45), (205, 190), (65, 185, 80), -1)
            writer.write(frame)
        writer.release()

    def test_probe_and_semantic_index(self) -> None:
        self.assertTrue(probe()["ready"])
        with tempfile.TemporaryDirectory(prefix="tonyfx-vision-") as temp_value:
            temp = Path(temp_value)
            source = temp / "source.mp4"
            self.build_video(source)
            prepared, evidence = prepare_analysis_source(source, temp / "normalized")
            self.assertEqual(prepared, source)
            self.assertFalse(evidence["normalized"])
            catalog = temp / "catalog.json"
            catalog.write_text(json.dumps({"items": [{"path": str(source), "layerName": "SELF TEST", "sourceStart": 0, "sourceDuration": 2}]}), encoding="utf-8")
            index = build_footage_index(catalog, temp / "index")
            self.assertTrue(index["ready"])
            capture = cv2.VideoCapture(str(source)); capture.set(cv2.CAP_PROP_POS_MSEC, 1000); ok, frame = capture.read(); capture.release()
            self.assertTrue(ok)
            matches = search_index(frame, index, 3)
            self.assertTrue(matches)
            self.assertEqual(matches[0]["layerName"], "SELF TEST")
            self.assertGreater(matches[0]["score"], 0.75)


if __name__ == "__main__":
    unittest.main()
