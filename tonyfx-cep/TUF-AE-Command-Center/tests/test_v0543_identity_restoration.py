from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("tonyfx_local_engine", ROOT / "python" / "local_engine.py")
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

engine = Path.home() / "Documents" / "TonyFX Local Engine"
source = ROOT / "tests" / "_v0542_generation_smoke.mp4"
output = ROOT / "tests" / "_v0543_identity_restored.mp4"
reference = Path.home() / "Desktop" / "images.jpg"
shutil.copy2(source, output)

restoration = MODULE.restore_reference_identity_video(output, reference, MODULE._yunet_model(engine))
print("RESTORATION:" + str(restoration))
metrics = MODULE.validate_generated_video(
    output,
    face_model=MODULE._yunet_model(engine),
    face_recognition_model=MODULE._sface_model(engine),
    reference_image=reference,
    identity_safe=True,
    reference_has_face=True,
    reference_face_area=0.368,
)
print("VALIDATION:" + str(metrics))
