from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tonyfx_local_engine", ROOT / "python" / "local_engine.py")
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


def test_prompt_compiler_never_invents_walking_or_wide_shot() -> None:
    prompt = ENGINE.compile_video_prompt(
        "The camera pushes rapidly into the woman's blue eye", "identity", True, "portrait"
    )
    lowered = prompt.lower()
    assert "walking gait" not in lowered
    assert "wide shot" not in lowered
    assert "pushes rapidly" in lowered
    assert "execute only the requested" in lowered


def test_small_reference_face_is_detected() -> None:
    import cv2

    source = Path(r"C:\Users\TUF\Desktop\images.jpg")
    model = Path(r"C:\Users\TUF\Documents\TonyFX Local Engine\models\analysis\face_detection_yunet_2023mar.onnx")
    if not source.exists() or not model.exists():
        return
    image = cv2.imread(str(source))
    faces = ENGINE.detect_faces_bgr(image, model)
    assert faces, "TonyFX did not detect the face in the user's small portrait reference."
    assert faces[0]["height"] > 40


if __name__ == "__main__":
    test_prompt_compiler_never_invents_walking_or_wide_shot()
    test_small_reference_face_is_detected()
    print("TonyFX generation guardrail tests passed.")
