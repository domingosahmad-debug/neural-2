$ErrorActionPreference = "Continue"

$python = "C:\Users\TUF\Documents\TonyFX Local Engine\.venv\Scripts\python.exe"
$engine = "C:\Users\TUF\Documents\TonyFX Local Engine"
$root = "C:\Users\TUF\Documents\New project\tuf-ae-command-center"
$output = Join-Path $root "tests\_v0544_generation_smoke.mp4"
$log = Join-Path $root "tests\_v0544_generation_smoke.log"

Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ($output + ".json") -Force -ErrorAction SilentlyContinue

& $python (Join-Path $root "python\local_engine.py") generate-video `
    --engine-root $engine `
    --backend ltx `
    --model "Lightricks/LTX-Video" `
    --input-image "C:\Users\TUF\Desktop\images.jpg" `
    --prompt "The same man remains clearly recognizable, blinks once naturally, then shifts his eyes gently toward the camera, subtle breathing, locked camera, stable face and clothing, realistic daylight portrait" `
    --negative-prompt "warped face, deformed eyes, asymmetrical features, morphing identity, duplicate person, extra limbs, melted skin, text, subtitles, logos, frozen frame, static image, camera shake, scene change" `
    --output $output `
    --width 320 --height 320 --duration 1 --frames 25 --fps 24 --base-fps 16 `
    --profile identity --reference-fit face --quality fast --steps 24 --guidance 3 --seed 12254 `
    *> $log

exit $LASTEXITCODE
