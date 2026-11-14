from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import replica_lab_bridge  # noqa: E402


class ReplicaLabBridgeTests(unittest.TestCase):
    def test_provider_order_is_explicit_and_sequential(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tonyfx-replica-bridge-") as value:
            root = Path(value)
            executable = root / "tfx-replica.exe"
            registry = root / "installed-stack.json"
            executable.touch()
            registry.write_text("{}", encoding="utf-8")
            calls: list[str] = []

            def fake_run(_executable: Path, arguments: list[str], *, cwd: Path) -> dict:
                calls.append(arguments[0])
                command = arguments[0]
                if command == "doctor":
                    return {"passed": True, "checks": []}
                output = Path(arguments[-1])
                if command == "assemble-reference":
                    output = Path(arguments[2])
                    output.write_text(json.dumps({"schema": "tfx.reference-analysis.v1", "ambiguities": []}), encoding="utf-8")
                elif output.suffix == ".json":
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text("{}", encoding="utf-8")
                return {"ok": True}

            with patch.object(replica_lab_bridge, "locate_replica_lab", return_value={"available": True, "root": root, "executable": executable, "registry": registry}), patch.object(replica_lab_bridge, "_run", side_effect=fake_run):
                result = replica_lab_bridge.run_reference_stack(Path("reference.mp4"), root / "out", "60/1", has_audio=True)

            self.assertTrue(result["available"])
            self.assertEqual(calls, ["doctor", "analyze-audio", "analyze-visual", "analyze-transnet", "cut-consensus", "detect-repeats", "fit-curves", "assemble-reference"])
            self.assertEqual([item["provider"] for item in result["providerTrace"][:4]], ["doctor", "Beat This", "OpenCV native-frame metrics", "TransNetV2"])


if __name__ == "__main__":
    unittest.main()

