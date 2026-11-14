from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from replica_contract import compile_builder_contract, validate_builder_contract  # noqa: E402


def base_report() -> dict:
    return {
        "media": {"path": "reference.mp4", "width": 1920, "height": 1080, "fps": 60.0, "fpsRational": "60000/1000", "frames": 120},
        "summary": {"decodedFrameCount": 120},
        "audio": {"beats": [0.0, 0.5, 1.0]},
        "replicaLab": {"available": True, "bundle": {"ambiguities": []}},
        "shots": [
            {"index": 1, "startFrame": 0, "endFrame": 59, "durationFrames": 60, "zoomDirection": "in", "zoomRatio": 1.10, "curve": "0.12,0.72,0.88,0.30", "translationPx": {"x": 20, "y": 0}},
            {"index": 2, "startFrame": 60, "endFrame": 119, "durationFrames": 60, "zoomDirection": "none", "zoomRatio": 1.0, "curve": "0.33,0.33,0.67,0.67", "translationPx": {"x": 0, "y": 0}},
        ],
        "events": [
            {"frame": 60, "startFrame": 56, "endFrame": 63, "kind": "cut_transition", "family": "whip_left", "componentFamilies": ["whip_left", "white_flash"], "confidence": 0.94, "curve": "0.08,0.78,0.90,0.22", "aeRecipe": []},
        ],
        "repeats": [],
    }


class ReplicaContractTests(unittest.TestCase):
    def test_exact_contract_is_frame_native_and_refusal_capable(self) -> None:
        contract = compile_builder_contract(base_report())
        self.assertEqual(contract["schema"], "tonyfx.replica-builder-contract.v1")
        self.assertEqual(contract["reference"]["fps"], "60")
        self.assertEqual(contract["shots"][0]["compFrames"], [0, 60])
        self.assertEqual(contract["transitions"][0]["frames"], [56, 64])
        self.assertTrue(contract["buildGate"]["exactReady"])
        self.assertFalse(contract["buildGate"]["genericEffectFallbackAllowed"])
        self.assertEqual(validate_builder_contract(contract), [])

    def test_provider_failure_blocks_exact_without_erasing_analysis(self) -> None:
        report = base_report()
        report["replicaLab"] = {"available": False, "reason": "doctor failed"}
        contract = compile_builder_contract(report)
        self.assertFalse(contract["buildGate"]["exactReady"])
        self.assertIn("provider.replica_lab_unavailable", contract["buildGate"]["blockingCodes"])
        self.assertEqual(len(contract["shots"]), 2)

    def test_unknown_transition_never_becomes_generic_blur(self) -> None:
        report = base_report()
        report["events"][0]["family"] = "effect_pulse"
        report["events"][0]["componentFamilies"] = ["effect_pulse"]
        contract = compile_builder_contract(report)
        self.assertFalse(contract["buildGate"]["exactReady"])
        self.assertIn("transition.unsupported_family", contract["buildGate"]["blockingCodes"])

    def test_peak_slot_refuses_underpowered_indexed_candidates(self) -> None:
        report = base_report()
        report["narrativeMap"] = {"available": True, "firstHighlightShot": 1, "climaxShot": 2}
        report["shots"][0]["semantic"] = {"phase": "first_highlight", "editorialFunction": "action_peak", "flashyRequired": True, "peakPriority": 2, "minimumCandidateMotion": 0.48}
        report["shots"][0]["footageMatches"] = [{"layerName": "calm-shot", "confidence": 0.91, "time": 3.2, "sourceStart": 0, "sourceDuration": 8, "motionScore": 0.12}]
        contract = compile_builder_contract(report)
        self.assertFalse(contract["buildGate"]["exactReady"])
        self.assertIn("shot.peak_energy_candidate_missing", contract["buildGate"]["blockingCodes"])
        self.assertTrue(contract["shots"][0]["sourceRequirements"]["matchedSourceWindowRequired"])
        self.assertEqual(contract["shots"][0]["sourceRequirements"]["minimumMotionScore"], 0.48)


if __name__ == "__main__":
    unittest.main()
