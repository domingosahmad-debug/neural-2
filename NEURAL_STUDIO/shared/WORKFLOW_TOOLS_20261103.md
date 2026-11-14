# Workflow tools — Tony's 3 November 2026 direction

Current authorized tools work is separate from the active Dexter native writer. Do not restart Neural, interrupt the director, replace saved provider sessions, or modify AE to activate these tools. This file records capability and routing, not artistic approval. Read `.maintenance/workflow-tools-20261103/RESULT.json` from the workspace for latest commissioning results.

## RTK: use compact displays with recoverable evidence

RTK OSS 1.1.0 is installed at `C:/Users/TUF/.local/bin/rtk/rtk.exe`; the official Windows release SHA256 matches GitHub's asset digest. The OSS command filters run locally. On Tony's explicit follow-up, selective user-global PreToolUse hooks were configured for Codex and Claude Code. They route simple rg/pytest/cargo-test/tsc/vitest calls through the evidence-preserving wrapper; protected, unsupported and compound commands pass through. Hook parsing and actual rewritten PowerShell execution passed for both adapters. Codex non-managed hook trust review may still be required; full live interception in this chat or the existing Neural process is NOT claimed. Do not restart/stop Neural for activation: existing work continues; use the wrapper directly until hooks load naturally. Full automatic-hook evidence: workspace `.maintenance/workflow-tools-20261103/automatic/`. No provider proxy, automatic model router, credential forwarding or background daemon is enabled.

For noisy supported shell commands, use `python tools/token_shell.py --filter FILTER -- EXECUTABLE ARGUMENTS` from the Neural root. Filters include `pytest`, `rg`, `git-status`, `git-log`, `git-diff`, `tsc`, `vitest`, `cargo-test`, `find`, and `log`. Supply argv directly; use a named shell only if the actual command requires one. Do not interpolate untrusted text into shell expressions.

The wrapper runs the original command ONCE, saves its complete combined stdout/stderr, then feeds the saved bytes to RTK's display filter. `data/token-shell/<id>/RESULT.json` carries raw/display paths, byte counts, exact command exit status and raw SHA256. Failure output is displayed unfiltered. Missing/broken/expanding filters fall back to raw output. Open the full raw log when diagnosing failure or when a compressed display omits decisive evidence. Do not filter instructions/skills, exact guard JSON, protected-state snapshots, native commands/results, shot/quote ledgers, source clocks or approval evidence. RTK is display compression, not a proof reader or history reset. Its reductions do not establish exact subscription savings.

Examples:

```powershell
python tools/token_shell.py --filter rg -- rg -n "pattern" app
python tools/token_shell.py --filter pytest -- python -m pytest tests/test_target.py -v
```

## GPT-6.1 Terra: bounded capable visual specialist

Registered in Neural as `Terra 6.1 - visual evidence (Medium)`, exact model `gpt-6.1-terra`, Codex subscription adapter. Agent ID is in the commissioning result. Account `model/list` confirms text/image input and availability. Existing Codex configuration is `model_reasoning_effort = "medium"`; station execution currently inherits that setting. The name is not an effort-control API. Recheck the effective configuration if it changes; never claim the label enforces effort.

Use Medium for scoped source/contact-sheet inspection, effect/property evidence review, typography placement, bounded technical diagnosis and precise text checks. Sol High remains director and handles difficult integration/creative decisions. Use local scripts for arithmetic, extraction and waiting. Terra's station adapter receives supplied text and stills, without shell/native AE/video-playback/audio-listening tools. Do not give it an unbounded plan or claim it listened to dialogue. Preserve its own durable per-profile/model/workflow conversation; do not reuse Sol's thread or change the active director. Do not dispatch an empty test solely to prove a model is active.

Official API prices differ from Codex subscription usage. Neither local availability nor API pricing proves a particular subscription saving or artistic quality. No paid API or new key is needed for this configured worker.

## Audio8: isolated on-demand CPU tool

Official source revision `1d64afcc2da5...` and model revision/file hashes are pinned in `.maintenance/workflow-tools-20261103/AUDIO8_SOURCE.json` and `AUDIO8_WEIGHTS.json`. This installation uses the 0.1B INT8 CPU ONNX runtime, not the 0.6B Realistic Air CUDA release. Its capabilities and quality must not be conflated. It has an isolated Python environment and does not occupy AE's GPU. No web service is started.

```powershell
python tools/audio8.py status
python tools/audio8.py synthesize --text "A short test sentence." --voice default
python tools/audio8.py register --reference-audio C:/media/reference.wav --reference-text "Exact spoken words." --name example
python tools/audio8.py synthesize --text "The new line." --voice example
```

Registration needs 0.5–30 seconds of suitable reference audio and its exact transcript. Generate short segments of at most150 characters. Keep synthetic takes separate from authentic quotes, captions and original dialogue; label them as synthetic in provenance. Do not automatically insert or replace dialogue in Dexter or another edit. Generated files and reports live under `data/audio8/jobs/<id>/`; no overwrite of source media. Waveform/format checks do not prove wording, delivery, voice similarity or artistic quality. A token-budget limit may truncate a line; inspect `reached_token_budget` and review completion before use. Local engine audio measurement/delivery checks remain the existing mechanical route after generation. Registration and synthesis are on demand, not an always-on AI worker.

## MatAnyone-E: not executable yet

Official repository currently contains presentation assets/README/license; inference code and checkpoints remain TODO. No functional adapter, replacement masker, or fabricated install is registered. The cited high-speed result uses an H200, not this RTX4060 Laptop8GB. The architecture is promising for source-space, frame-accurate alpha sequences, but needs released executable code/weights, license review and actual local quality/throughput checks before production adoption. Keep current approved roto/matte methods. No timed model monitor is added.

## NVIDIA Nemotron3.5 Transcribe: research only

Official model: `nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B`, approximately34B total/4.3B active including encoders; offline recordings,40 languages, optional word timestamps and speaker attribution. Reference serving profile requires H10080GB, so it is not installed on the8GB laptop. Input is audio plus text; output is TEXT with optional alignment metadata. Readable transcript cleanup is not waveform denoising, music removal or dialogue restoration.

The official Hugging Face demo is available for exploration. The checked OpenCode catalog lists other Nemotron models; it does not establish this exact Transcribe model's free API availability. Direct unauthenticated model-catalog retrieval returned403. Do not silently substitute Lightning/Super/Omni or buy a paid fallback. No API key/account, media upload, hosted request or model download is performed for this research. Hosted integration needs a verified exact endpoint, authenticated free allowance/terms, supported timestamps/error handling and an actual bounded transcription check. Preserve the existing local ASR/audio workflow meanwhile.

Primary sources:

- https://github.com/rtk-ai/rtk
- https://developers.openai.com/api/docs/models/gpt-6.1-terra
- https://github.com/Edge0-AI/Audio8_TTS
- https://github.com/Shuyun-Wang/MatAnyone-E
- https://docs.nvidia.com/nemotron/nightly/nemotron/transcribe35/README.html
- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B
- https://opencode.ai/v2/docs/console/models/
