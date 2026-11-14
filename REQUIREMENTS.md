# External requirements

None of these are in the repository. They belong to other vendors or are too large for Git. `Setup-Neural2.ps1` installs the ones marked **auto**. You install the rest yourself.

## Core (required)

| Item | Version | Get it | Notes |
|---|---|---|---|
| Windows | 10 or 11, x64 | | Paths and launchers are Windows-only |
| Python | 3.12+ on PATH | https://www.python.org/downloads/ | Tick "Add python.exe to PATH" |
| Python packages | numpy 2.5.1, Pillow 12.3.0, fonttools 4.63.0, scipy 1.18.1, sounddevice 0.5.5 | **auto** (`requirements.txt`) | |
| Electron runtime | 44.7.2 win32-x64 | **auto**: https://github.com/electron/electron/releases/download/v44.7.2/electron-v44.7.2-win32-x64.zip | Extracted to `NEURAL_STUDIO_2/runtime/` |
| Adobe After Effects | 2023–2026 (CEP hosts 23–27) | Adobe Creative Cloud | Your own licence |
| ffmpeg + ffprobe | any recent | `winget install Gyan.FFmpeg` | Used for media probing, previews and review frames |
| git | any | https://git-scm.com | |

## AI providers (install at least one; sign in with your own account)

| CLI | Used for | Get it | Found at |
|---|---|---|---|
| Claude Code (`claude`) | Director (Opus), workers (Sonnet, Haiku) | https://claude.com/claude-code | PATH or `~/.local/bin/claude.exe` |
| Codex (`codex`) | GPT Sol, Luna and Terra seats | https://developers.openai.com/codex | PATH or `%LOCALAPPDATA%/OpenAI/Codex/bin/*/codex.exe` |
| OpenCode (`opencode`) | Free models, the first-choice worker fallback | https://opencode.ai (Desktop or `npm i -g opencode-ai`) | PATH or `%APPDATA%/ai.opencode.desktop/cli/*/opencode-cli.exe` |
| Antigravity (`agy`) | Gemini seats | https://antigravity.google | PATH, `%LOCALAPPDATA%/agy/bin/agy.exe` or `NEURAL_STUDIO/.tools/agy/agy.exe` |

Neural uses each subscription CLI as it is. It never adds paid API keys or changes billing. Any seat you do not have is skipped by routing.

Optional: Node.js 20+ runs the JavaScript tests under `NEURAL_STUDIO_2/tests`.

## After Effects plugins and fonts (used by the accepted edit recipes)

| Item | Type | Notes |
|---|---|---|
| Twixtor Pro (RE:Vision Effects) | paid | Velocity and speed ramps |
| Boris FX Sapphire: S_BlurMoCurves, S_WarpChroma, S_DigitalDamage, S_Glow, S_EdgeDetect | paid | Transitions, glow, glitch |
| BCC Directional Blur | paid, optional | Recipes fall back to native blur |
| Mocha AE, Lumetri Color | bundled with AE | |
| Montserrat Black | free, Google Fonts | Captions |
| Social Gothic Rough | commercial font | Title cards; substitute if you do not own it |
| Impact | ships with Windows | |

If a plugin is missing, the director must use a native substitute and say so in the plan. It must never fake a plugin's look.

## Optional local models (`Setup-Neural2.cmd -Voice`, auto)

| Purpose | Package or model | Location | Source and SHA-256 |
|---|---|---|---|
| Relay local assistant | llama-cpp-python 0.3.36 (CPU) + Qwen3-0.6B-Q8_0.gguf (Apache-2.0, 639,446,688 B) | `NEURAL_STUDIO/.tools/helper-python`, `NEURAL_STUDIO/.models/` | https://huggingface.co/Qwen/Qwen3-0.6B-GGUF · `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031` |
| Voice (text-to-speech) | kokoro-onnx 0.6.1, onnxruntime, soundfile + kokoro-v1.0.onnx (325,505,369 B) and voices-v1.0.bin (28,214,398 B) | `NEURAL_STUDIO/.tools/voice-python`, `NEURAL_STUDIO/.models/kokoro/` | https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1 · onnx `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a` · bin `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d` |
| Dictation and captions (ASR) | faster-whisper 1.2.1 (pulls ctranslate2, av, tokenizers, huggingface_hub) + Systran faster-whisper `small.en` and `base` | `<repo>/.caption_deps`, `NEURAL_STUDIO/.models/faster-whisper-<size>/` | https://huggingface.co/Systran. Set `NEURAL_SPEECH_ROOT` to use another folder |

Without these, Neural still edits. Only Relay, spoken replies and dictation are unavailable.
