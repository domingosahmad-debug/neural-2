---
name: tfx-reference-analysis
description: Measure reference cuts, music offset, zooms, transitions, repeat topology and narrative peaks outside AE. Use when reproducing a reference or preparing a frame-native edit specification.
---


# Reference analysis

Use [measurement contract](references/measurements.md). Start with ffprobe metadata and SHA-256 hashes; preserve exact rational FPS. Scripts/media_probe.py provides a lightweight metadata/hash report, not a complete analyzer.

1. Watch the whole reference when the interface supports it. Record hook, setup, first highlight, escalation, climax, resolution, caption/lyric placement and sound intent. Dense frames supplement playback; they cannot establish full-speed flow or sound quality.
2. Locate the supplied clean-song segment by multi-window waveform correlation. Check offset, speed, pauses, repeats, fades, dialogue ducks and audio priming. Do not choose an approximate verse from filename/BPM alone.
3. Reconcile TransNetV2 and OpenCV cut candidates on native frames. Flashes, blur and occlusions can cause false cuts. Label disagreements and inspect them.
4. Map Beat This beats/downbeats plus independent onsets/transients. Distinguish musical boundaries from scene cuts and transition apexes. Use confidence and manual evidence.
5. Measure each camera/transition event separately: interval, center, target, scale/rotation, opacity, blur, easing, source-camera contribution. No generic curve replacing missing measurement. Detect exact repeated source windows and forward/reverse order.
6. Index sources and select finalists using footage-story-flow. Retrieval models propose candidates; inspect them before assigning identities or narrative meaning.
7. Export shots, transitions, audio events, repeats, source assignment and unresolved ambiguities. Exact mode must block unsupported requirements; creative mode can make an explicitly documented interpretation.

Existing local lab: C:/Users/TUF/Documents/New project/TFX_REPLICA_LAB; .venv/Scripts/tfx-replica.exe; profiles/installed-stack.json. Inspect CLI help and run doctor --registry profiles/installed-stack.json --verify-hashes before relying on the stack. Reuse hash-matching caches. Do not silently install packages or substitute providers and still call the result certified.

Native-frame cuts + motion fitting + human/visual verification matter more than consuming every available model. Do not run expensive providers for a narrow caption correction. Missing model/audio access is an evidence limitation, not a license to invent measurements.

## Local mechanical execution

Inside Neural and ordinary editing chats, route supported mechanical media work through [neural-local-ops](<C:/Users/TUF/.codex/skills/neural-local-ops/SKILL.md>) and the [shared local engine contract](<C:/Users/TUF/Documents/New project/NEURAL_STUDIO/shared/LOCAL_OPS_WORKFLOW.md>). Query its CLI capabilities before preparing a bounded plan. Use scripts for repeated measurements/extraction/audio transforms/validation and inspect saved evidence; models interpret creative intent and ambiguous results. Keep technical PASS separate from playback/listening and human artistic approval. Preserve existing TonyFX authorization, exact live identity and single-writer safeguards for native work.
