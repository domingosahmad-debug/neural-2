import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image


MODULE_PATH = Path(__file__).resolve().parents[1] / "python" / "local_engine.py"
SPEC = importlib.util.spec_from_file_location("tonyfx_local_engine", MODULE_PATH)
ENGINE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(ENGINE)


class VideoGenerationContractTests(unittest.TestCase):
    def test_panel_argument_order_accepts_engine_root(self):
        args = ENGINE.build_parser().parse_args([
            "generate-video", "--engine-root", r"C:\TonyFX Engine", "--prompt", "test shot", "--output", "test.mp4"
        ])
        self.assertEqual(args.command, "generate-video")
        self.assertEqual(args.engine_root, r"C:\TonyFX Engine")
        self.assertEqual(args.duration, 3)
        self.assertEqual(args.base_fps, 16)
        self.assertEqual(args.quality, "balanced")
        self.assertEqual(args.profile, "identity")
        self.assertEqual(args.reference_fit, "face")

    def test_prompt_compiler_keeps_request_and_adds_identity_contract(self):
        prompt = ENGINE.compile_video_prompt("A man walks down a wet city alley", "identity", True)
        self.assertTrue(prompt.startswith("A man walks down a wet city alley"))
        self.assertIn("same person remains clearly recognizable", prompt)
        self.assertIn("exact first frame", prompt)
        self.assertIn("No cuts", prompt)

    def test_wide_reference_uses_full_body_identity_contract(self):
        prompt = ENGINE.compile_video_prompt(
            "A man walks past a stone wall at night", "identity", True, "wide"
        )
        self.assertIn("consistent body proportions", prompt)
        self.assertIn("without forcing the camera into a close-up", prompt)
        self.assertNotIn("face remains clearly recognizable in every frame", prompt)

    def test_face_policy_is_scale_aware(self):
        self.assertEqual(ENGINE.identity_face_policy(0.06), "portrait")
        self.assertEqual(ENGINE.identity_face_policy(0.02), "medium")
        self.assertEqual(ENGINE.identity_face_policy(0.006), "wide")

    def test_reference_preparation_never_stretches_portrait_into_landscape(self):
        with tempfile.TemporaryDirectory(prefix="tonyfx-reference-test-") as value:
            source = Path(value) / "portrait.png"
            Image.new("RGB", (300, 600), (80, 120, 160)).save(source)
            prepared, metadata = ENGINE.prepare_video_reference(source, 736, 416, Path(value), "center")
            self.assertEqual(prepared.size, (736, 416))
            crop = metadata["crop"]
            crop_ratio = (crop[2] - crop[0]) / float(crop[3] - crop[1])
            self.assertAlmostEqual(crop_ratio, 736 / 416, places=2)
            self.assertEqual(metadata["sourceSize"], [300, 600])
            self.assertEqual(metadata["preparedFaceArea"], 0.0)

    def test_visual_validator_accepts_real_motion(self):
        with tempfile.TemporaryDirectory(prefix="tonyfx-generation-test-") as value:
            output = Path(value) / "motion.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                "testsrc2=size=320x320:rate=12:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
            ], check=True)
            metrics = ENGINE.validate_generated_video(output)
            self.assertGreater(metrics["detail"], 1.5)
            self.assertGreater(metrics["motion"], 0.02)
            self.assertIn("flicker", metrics)
            self.assertIn("faceCoverage", metrics)


if __name__ == "__main__":
    unittest.main()
