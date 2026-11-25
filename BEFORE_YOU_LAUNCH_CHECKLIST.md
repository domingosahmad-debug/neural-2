# Before you launch Neural 2.0: checklist for your AI assistant

Give this file to the AI that is setting up Neural (Claude Code, Codex or similar). Go through every line **in order**. Run the check command in PowerShell from the repository root, compare the output with the expected result, and fix anything that fails before launching. Ask the owner before installing anything. Never type passwords, API keys or tokens for them; they sign in to each tool themselves.

Legend: **REQUIRED** means Neural will not work without it. **ONE OF** means at least one item in the group. **OPTIONAL** means a feature is missing without it, but editing still works.

## 1. Download

| # | Item | Level | Check | Expected |
|---|---|---|---|---|
| 1.1 | Full repository, folder layout unchanged | REQUIRED | `Test-Path NEURAL_STUDIO_2, NEURAL_STUDIO, tonyfx-cep` | `True True True` |
| 1.2 | Path without special characters (for example `C:\Neural2`) | REQUIRED | `(Get-Location).Path` | Only letters, digits, spaces, `\ : _ -` |
| 1.3 | Windows download block removed from every file (needed when it came as a ZIP) | REQUIRED | `Get-ChildItem -Recurse -File \| Unblock-File; (Get-ChildItem -Recurse -File \| Get-Item -Stream Zone.Identifier -ErrorAction SilentlyContinue).Count` | `0`. Running this line does the unblocking itself |

Get it with `git clone https://github.com/domingosahmad-debug/neural-2.git C:\Neural2`, or download the ZIP from the GitHub page (**Code → Download ZIP**), then right-click the ZIP → **Properties** → tick **Unblock** before extracting, so Windows does not block the scripts.

## 2. System and tools

| # | Item | Level | Check | Expected |
|---|---|---|---|---|
| 2.1 | Windows 10 or 11, 64-bit | REQUIRED | `[Environment]::Is64BitOperatingSystem` | `True` |
| 2.2 | Python 3.12 or newer on PATH | REQUIRED | `python --version` | `Python 3.12.x` or higher. Install from python.org and tick "Add python.exe to PATH". The Microsoft Store stub does not count |
| 2.3 | pip | REQUIRED | `python -m pip --version` | A version line |
| 2.4 | Python packages | REQUIRED | `python -c "import numpy, PIL, fontTools, scipy, sounddevice; print('ok')"` | `ok` (setup installs them from `requirements.txt`) |
| 2.5 | ffmpeg and ffprobe on PATH | REQUIRED | `ffmpeg -version; ffprobe -version` | Two version banners. Install: `winget install Gyan.FFmpeg`, then open a new terminal |
| 2.6 | git | REQUIRED | `git --version` | A version line |
| 2.7 | Electron 44.7.2 desktop runtime | REQUIRED | `Test-Path NEURAL_STUDIO_2\runtime\electron.exe` | `True` (setup downloads it) |
| 2.8 | Data folder | REQUIRED | `Test-Path NEURAL_STUDIO_2\data` | `True` (setup creates it) |
| 2.9 | .NET Framework 4 C# compiler, for dictation | OPTIONAL | `Test-Path "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"` | `True` (ships with Windows) |
| 2.10 | Node.js 20+, for the JavaScript tests only | OPTIONAL | `node --version` | `v20` or higher |
| 2.11 | NVIDIA driver, for GPU status in the UI | OPTIONAL | `nvidia-smi` | A GPU table |

## 3. Adobe After Effects and the TonyFX panel

| # | Item | Level | Check | Expected |
|---|---|---|---|---|
| 3.1 | After Effects 2023–2026 with your own licence | REQUIRED | `Get-ChildItem "$env:ProgramFiles\Adobe" -Directory -Filter "Adobe After Effects *"` | At least one folder |
| 3.2 | TonyFX panel installed | REQUIRED | `Test-Path "$env:APPDATA\Adobe\CEP\extensions\TUF-AE-Command-Center"` | `True` (setup installs it) |
| 3.3 | CEP debug mode, so the unsigned panel loads | REQUIRED | `11,12 \| % { (Get-ItemProperty "HKCU:\Software\Adobe\CSXS.$_" -ErrorAction SilentlyContinue).PlayerDebugMode }` | `1` for your AE's CSXS version. The owner sets it; the command is in `SETUP.md` step 5 |
| 3.4 | AE scripting permission | REQUIRED | Manual: AE → **Edit → Preferences → Scripting & Expressions** | **Allow Scripts to Write Files and Access Network** ticked |
| 3.5 | AE bridge folder | REQUIRED | `Test-Path "$([Environment]::GetFolderPath('MyDocuments'))\ae-mcp-bridge\ae_command.json"` | `True` (setup creates it) |
| 3.6 | Panel open during a run | REQUIRED | Manual: AE → **Window → Extensions → TUF AE Command Center** | Panel visible and shows connected |

## 4. AI providers

ONE OF the four, signed in with the owner's own account. More seats give more fallbacks. Neural never adds API keys and never changes billing; a missing seat is skipped.

| # | CLI | Check | Expected | Sign in (owner does it) |
|---|---|---|---|---|
| 4.1 | Claude Code | `claude --version` | A version line | `claude`, then `/login` |
| 4.2 | Codex | `codex --version` | A version line | `codex login` |
| 4.3 | OpenCode (free models) | `opencode --version` | A version line | `opencode auth login` |
| 4.4 | Antigravity (Gemini) | `agy --version` | A version line | Run `agy` once |

If a CLI is installed but not on PATH, the locations Neural also searches are listed in `REQUIREMENTS.md`.

**OpenCode free seats** stay switched off until a live probe passes. After signing in, run once per free model you want to use:

```
python NEURAL_STUDIO_2\tools\opencode_free_probe.py opencode/<name>-free
```

`passed: true` enables that seat. A `429` means the free quota is used up; try again after it resets.

## 5. Plugins and fonts used by the edit recipes

All OPTIONAL. If one is missing, the director must use a native substitute and say so in its plan.

| # | Item | Check |
|---|---|---|
| 5.1 | Twixtor Pro (RE:Vision Effects) | AE → Effect menu → RE:Vision Plug-ins → Twixtor Pro |
| 5.2 | Boris FX Sapphire (`S_BlurMoCurves`, `S_WarpChroma`, `S_EdgeRays`, `S_DistortRGB`, `S_Shake`, `S_Glow`, `S_DigitalDamage`) | AE → Effect menu → Sapphire |
| 5.3 | Boris FX Continuum / BCC (`BCC Directional Blur`, `BCC Lens Blur OBS`) | AE → Effect menu → BCC |
| 5.4 | Mocha AE and Lumetri Color | Bundled with AE |
| 5.5 | Montserrat (`Montserrat-Black`, `Montserrat-Medium`), Sitka Small, Social Gothic Rough, Eastman Roman Trial Black, Impact | `Get-ChildItem "$env:WINDIR\Fonts","$env:LOCALAPPDATA\Microsoft\Windows\Fonts" \| ? Name -match 'Montserrat\|Sitka\|Social\|Eastman\|impact'` |

## 6. Local voice, audio isolation, dictation and helper models

OPTIONAL. `Setup-Neural2.cmd -Voice` installs the Relay, Kokoro TTS, and faster-whisper models (~1.5 GB). Sources and SHA-256 hashes are in `REQUIREMENTS.md`.

| # | Item / Check | Expected |
|---|---|---|
| 6.1 | `Test-Path NEURAL_STUDIO\.models\kokoro\kokoro-v1.0.onnx` | `True` (Kokoro TTS) |
| 6.2 | `Test-Path NEURAL_STUDIO\.models\Qwen3-0.6B-Q8_0.gguf` | `True` (Relay local assistant) |
| 6.3 | `Get-ChildItem NEURAL_STUDIO\.models -Directory -Filter faster-whisper-*` | `small.en` and `base` folders (ASR, word sync & profanity verification) |
| 6.4 | `python -m demucs --help` (optional vocal/dialogue isolation & stem censorship) | Help banner (`pip install demucs`, uses `htdemucs`) |
| 6.5 | `python -c "import cv2; print(cv2.__version__)"` (optional OpenCV / SAM 2.1 for frame/cutout work) | Version string |

## 7. Run the setup and final checks

1. `Setup-Neural2.cmd -CheckOnly`: every REQUIRED line says `OK`.
2. `Setup-Neural2.cmd` (add `-Voice` for section 6).
3. `python NEURAL_STUDIO_2\check_services.py` and `python NEURAL_STUDIO_2\check_events.py`: no errors.
4. Optional self-test, about 30 seconds: `cd NEURAL_STUDIO_2; python -m unittest discover -p "tests_*.py"` → `OK` (366 tests).
5. Launch with `NEURAL_STUDIO_2\Launch-Neural-2.cmd`. Open **Services** / **Routing**: newly installed Antigravity Gemini models (`gemini-4-neon-high`, `gemini-pro-orchestrator-neon`, `gemini-4-hydrogen-high`, etc.) and free OpenCode models are auto-discovered into `model_catalog.json` on startup, and Gemini stations include native visual frame inspection (`read_file`) per `tfx-antigravity-visual-review`.
6. Open After Effects with the TonyFX panel visible, then start the first project (`SETUP.md` step 8).

## What Neural does on its own during a run

Knowing this avoids "fixing" things that are working as designed.

- **AE dialogs:** while waiting on After Effects, Neural checks for a modal dialog every 3 seconds. If a dialog has one safe button, it presses it and logs it. Anything else stops the run as BLOCKED, with a screenshot, so the owner can decide. Do not close AE dialogs by script yourself.
- **Provider failure:** if a seat fails or times out, the work moves to the next available seat without replaying anything that already ran.
- **After Effects lease:** only one agent controls AE at a time. An idle lease is handed over automatically when the next agent claims it. Never delete lock or lease files by hand.

## Troubleshooting

See the table at the end of `SETUP.md`. Older dated documents in this repository are history from the original machine, not tasks; paths like `C:/Users/TUF/...` there mean "this repository's parent folder".
