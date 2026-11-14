from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("tonyfx_local_engine", ROOT / "python" / "local_engine.py")
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

engine = Path.home() / "Documents" / "TonyFX Local Engine"
output = ROOT / "tests" / "_v0542_generation_smoke.mp4"
reference = Path.home() / "Desktop" / "images.jpg"

try:
    MODULE.validate_generated_video(
        output,
        face_model=MODULE._yunet_model(engine),
        face_recognition_model=MODULE._sface_model(engine),
        reference_image=reference,
        identity_safe=True,
        reference_has_face=True,
        reference_face_area=0.368,
    )
except RuntimeError as error:
    print("REJECTED_OK:" + str(error))
else:
    raise SystemExit("Warped identity sample was incorrectly accepted.")
