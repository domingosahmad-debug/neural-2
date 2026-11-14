from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from reference_analyzer import analyze_reference  # noqa: E402
from reference_intelligence import compare_analysis_reports, fit_temporal_curve  # noqa: E402


class ReferenceAnalyzerTest(unittest.TestCase):
    def build_reference(self, directory: Path) -> Path:
        output = directory / "synthetic-reference.mp4"
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
        self.assertTrue(writer.isOpened())
        for index in range(150):
            if index < 35:
                frame = np.full((240, 320, 3), (40, 75, 185), np.uint8)
                cv2.circle(frame, (90, 120), 45, (240, 240, 240), -1)
            elif index < 41:
                value = int(255 * abs(index - 38) / 3)
                frame = np.full((240, 320, 3), value, np.uint8)
            elif index < 80:
                frame = np.full((240, 320, 3), (180, 65, 40), np.uint8)
                cv2.rectangle(frame, (185, 65), (280, 185), (245, 245, 245), -1)
            elif index < 87:
                value = 255 - int(215 * abs(index - 83) / 4)
                frame = np.full((240, 320, 3), np.clip(value, 0, 255), np.uint8)
            else:
                frame = np.full((240, 320, 3), (45, 165, 75), np.uint8)
                x = 40 + min(180, (index - 87) * 5)
                cv2.rectangle(frame, (x, 80), (x + 70, 170), (250, 250, 250), -1)
            writer.write(frame)
        writer.release()
        return output

    def test_manifest_and_evidence_are_created(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tonyfx-analyzer-test-") as temp_value:
            temp = Path(temp_value)
            source = self.build_reference(temp)
            report = analyze_reference(source, temp / "report", width=320, analyze_audio=False, deep_flow=True)
            self.assertEqual(report["schema"], "tonyfx.reference-analysis.v6")
            self.assertEqual(report["analyzerVersion"], "0.60.0")
            self.assertGreaterEqual(len(report["events"]), 2)
            self.assertTrue(Path(report["manifest"]).exists())
            self.assertTrue(Path(report["htmlReport"]).exists())
            self.assertTrue(Path(report["contactSheet"]).exists())
            first = report["events"][0]
            self.assertIn("candidateScores", first)
            self.assertIn("aeRecipe", first)
            self.assertIn("kind", first)
            self.assertIn("components", first)
            self.assertIn(first["graph"], {"linear", "sharp_start", "sharp_end", "speed_ramp", "smooth_in_out"})
            self.assertIn("editBlueprint", report)
            self.assertEqual(report["editBlueprint"]["version"], 6)
            self.assertTrue(report["shots"])
            self.assertEqual(report["summary"]["shotCount"], len(report["shots"]))
            self.assertGreaterEqual(report["summary"]["candidatePeakCount"], report["summary"]["eventCount"])
            self.assertIn("never turn component peaks into extra cuts", report["editBlueprint"]["builderRule"])
            self.assertIn("renderedCandidates", first)
            self.assertIn("advancedCurve", first)
            self.assertIn("framingQA", report)
            self.assertIn("semanticShotRequirements", report)
            self.assertIn("audioStructure", report)
            self.assertIn("repairPlan", report)
            self.assertIn("transitionForensics", report)
            self.assertIn("forensics", first)
            self.assertIn("strictRecipe", first)
            self.assertIn("families", first["strictRecipe"])
            self.assertIn("curve", first["strictRecipe"])
            self.assertIn("replicaBuilderContract", report)
            self.assertEqual(report["replicaBuilderContract"]["schema"], "tonyfx.replica-builder-contract.v1")
            self.assertFalse(report["replicaBuilderContract"]["buildGate"]["genericCurveFallbackAllowed"])
            self.assertTrue(report["narrativeMap"]["available"])
            self.assertGreaterEqual(report["narrativeMap"]["firstHighlightShot"], 1)
            self.assertGreaterEqual(report["narrativeMap"]["climaxShot"], 1)
            self.assertTrue(any((shot.get("semantic") or {}).get("flashyRequired") for shot in report["shots"]))
            self.assertTrue(report["replicaBuilderContract"]["buildGate"]["peakEnergyMappingRequired"])

    def test_curve_solver_and_finished_edit_comparison(self) -> None:
        fitted = fit_temporal_curve([0, 1, 3, 7, 18, 45, 78, 100])
        self.assertIn(fitted["name"], {"sharp_start", "sharp_end", "speed_ramp", "smooth_in_out", "linear"})
        self.assertEqual(len(fitted["controls"]), 4)
        reference = {"media":{"fps":30},"cutEvents":[{"time":1.0},{"time":2.0}],"events":[{"time":1.0,"family":"whip_left","curve":"0.09, 0.72, 0.94, 0.27"}],"shots":[{"durationFrames":30,"startTime":0}]}
        candidate = {"media":{"fps":30},"cutEvents":[{"time":1.0},{"time":2.0}],"events":[{"time":1.0,"family":"whip_left"}],"shots":[{"durationFrames":30,"startTime":0}]}
        comparison = compare_analysis_reports(reference,candidate)
        self.assertTrue(comparison["passed"])
        self.assertGreaterEqual(comparison["score"],0.9)

    def test_local_engine_cli_protocol(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tonyfx-analyzer-cli-") as temp_value:
            temp = Path(temp_value)
            source = self.build_reference(temp)
            result = subprocess.run([
                sys.executable, str(ROOT / "python" / "local_engine.py"),
                "analyze-reference", "--input", str(source), "--output-dir", str(temp / "cli-report"),
                "--width", "300", "--no-audio", "--no-ocr", "--no-deep-flow",
            ], check=True, text=True, capture_output=True)
            payloads = []
            for line in result.stdout.splitlines():
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            completed = [item for item in payloads if item.get("type") == "result"]
            self.assertTrue(completed)
            self.assertTrue(completed[-1]["ok"])
            self.assertTrue(Path(completed[-1]["manifest"]).exists())

    def test_finished_edit_comparison_rejects_calm_climax(self) -> None:
        reference = {
            "media": {"fps": 30, "width": 1920, "height": 1080, "frames": 90},
            "cutEvents": [{"time": 1.0}, {"time": 2.0}], "events": [], "repeats": [],
            "narrativeMap": {"available": True, "firstHighlightShot": 2, "climaxShot": 3},
            "shots": [
                {"durationFrames": 30, "startTime": 0, "semantic": {"visualEnergyScore": 0.2, "peakPriority": 0}},
                {"durationFrames": 30, "startTime": 1, "semantic": {"visualEnergyScore": 0.8, "peakPriority": 2}},
                {"durationFrames": 30, "startTime": 2, "semantic": {"visualEnergyScore": 1.0, "peakPriority": 3}},
            ],
        }
        candidate = {
            "media": {"fps": 30, "width": 1920, "height": 1080, "frames": 90},
            "cutEvents": [{"time": 1.0}, {"time": 2.0}], "events": [], "repeats": [],
            "shots": [
                {"durationFrames": 30, "startTime": 0, "semantic": {"visualEnergyScore": 0.9}},
                {"durationFrames": 30, "startTime": 1, "semantic": {"visualEnergyScore": 0.2}},
                {"durationFrames": 30, "startTime": 2, "semantic": {"visualEnergyScore": 0.1}},
            ],
        }
        comparison = compare_analysis_reports(reference, candidate)
        self.assertFalse(comparison["gates"]["peakEnergy"]["passed"])
        self.assertFalse(comparison["passed"])
        self.assertEqual(len(comparison["peakEnergyMismatches"]), 2)

    def test_flash_dip_inside_one_shot_does_not_create_fake_cuts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tonyfx-analyzer-pulse-") as temp_value:
            temp = Path(temp_value)
            source = temp / "same-shot-pulse.mp4"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
            self.assertTrue(writer.isOpened())
            for index in range(96):
                frame = np.full((240, 320, 3), (52, 84, 142), np.uint8)
                cv2.circle(frame, (105 + index // 8, 118), 42, (225, 225, 225), -1)
                if index in {43, 47}:
                    frame[:] = 245
                elif index in {44, 46}:
                    frame[:] = 8
                elif index == 45:
                    frame[:] = 128
                writer.write(frame)
            writer.release()
            report = analyze_reference(source, temp / "report", width=320, accuracy="deep", analyze_audio=False)
            pulse_events = [event for event in report["events"] if 1.2 <= event["time"] <= 1.8]
            self.assertTrue(pulse_events)
            self.assertTrue(all(event["kind"] == "effect_only" for event in pulse_events))
            self.assertGreater(report["summary"]["collapsedPeakCount"], 0)


if __name__ == "__main__":
    unittest.main()
