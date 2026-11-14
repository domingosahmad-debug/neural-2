---
name: tfx-workflow-director
description: Route TUF video work through the learned TFX workflow. Use when starting an edit, interpreting a reference brief, choosing analysis versus repair, or coordinating other TFX skills.
---


# TFX workflow director

Translate the user's intent into a specific visual and audio brief before building. This is a routing skill, not a generic effect preset.

1. Read current project STATE and the latest request. Establish task mode: original edit, creative reference adaptation, exact reference timing, scoped repair, or analysis only. Preserve explicit scope and authorization across turns.
2. Priority: current user instructions and live manual work > named approved example > measured reference > these curated rules > archived recipes. Old project names and scripts are evidence, never new assignments.
3. Confirm tools actually deliver image pixels and audio/video to the model. Text metadata, ASR, and a model's advertised modalities are not proof of visual or listening access. Record unsupported checks explicitly.
4. Inventory sources, clean song, target dimensions/rational frame rate, language, main character, protected intro, reference role and finish target. Infer routine choices from evidence; ask only for materially missing requirements. Do useful independent work while awaiting answers.
5. Run reference-analysis if matching a reference; otherwise map the music's hook, build, drop, escalation and ending. Use footage-story-flow to create the shot ledger before effects.
6. Use tonyfx-execution and ae-editable-assembly only when actual AE work is requested. Inspect live state before any mutation. This kit's installation/learning phase alone is NOT permission to alter AE.
7. Resolve motion-transitions, character-mattes-color, cinematic-typography and dialogue-music-sound per shot. Prove one representative difficult shot/transition before multiplying it across a whole edit.
8. Use review-repair for separate technical and perceptual gates; export-delivery only for requested deliverables. Save state-handoff after a meaningful pass.

Avoid recurring failures: overlong flashbacks, recycled shots, random foot/eye inserts, weak action at music peaks, silent talking, chopped words, uniform alternating zooms, excessive glow and missing secondary-character masks. More effects cannot repair weak selection.

Honor no-computer-use requests. No repeated permission questions for already authorized processing. Check actual resource contention before a GPU job; do not interrupt another editor's AE session. Never bypass a real platform restriction. Keep progress concise and name genuine limitations without claiming perfection.

Deliver: current project/comp identity, what changed, evidence inspected, unresolved issues, and next action. A successful render or a filename containing FINAL is not user approval.

## Local mechanical execution

Inside Neural and ordinary editing chats, route supported mechanical media work through [neural-local-ops](<C:/Users/TUF/.codex/skills/neural-local-ops/SKILL.md>) and the [shared local engine contract](<C:/Users/TUF/Documents/New project/NEURAL_STUDIO/shared/LOCAL_OPS_WORKFLOW.md>). Query its CLI capabilities before preparing a bounded plan. Use scripts for repeated measurements/extraction/audio transforms/validation and inspect saved evidence; models interpret creative intent and ambiguous results. Keep technical PASS separate from playback/listening and human artistic approval. Preserve existing TonyFX authorization, exact live identity and single-writer safeguards for native work.


## Production checkpoints and explicit repair acceptance — 2026-10-21
Read NEURAL_STUDIO/shared/PRODUCTION_CHECKPOINT_WORKFLOW.md (shared/PRODUCTION_CHECKPOINT_WORKFLOW.md from the studio root). Maintain revision-specific human requirements, evidence-backed checkpoints and honest remaining-time ranges, inside Neural or via tools/production.py outside it. Built/technical/sampled-picture/motion/listening/human gates are independent. Before construction run the shared plan validator including source-range reuse (aliases must not conceal repeats); inspect final nested/occluded ownership where plans lack it. A human rejection becomes an explicit acceptance test across picture/audio/text as applicable. Never erase pending sound/motion/listening gates merely because a render completed. Reuse measurements and stop inference while the single watched local pipeline runs.

For non-anime character/music edits, automatically load tfx-live-action-accepted-pipeline: Tony accepted Chemical F03 and Offline F04 on4November2026. It governs this live-action style; keep anime on its own pipeline. Use current actual footage/music decisions, not copied completed scenes.

## Quinn closed; reusable template — 12 November 2026

Joey Quinn project e965c19132a7450da92d20c53073a0cc is finished by Tony himself and closed; never resume or rebuild it. Before directing a comparable live-action edit read `../tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.md` (Neural's mistakes and Tony's corrections). Tony's requested default seats for new edits: Director Claude Opus (medium); Plan/Edit/Review/Deliver Gemini 3.8 Flash High (Gemini Argon High as an extra candidate once its quota returns); OpenCode free models (opencode/*-free) now have a scoped production tool host (12 November) and may be routed to any station as fallback or alone; they share one free quota (429 when exhausted, never a paid fallback) and their tool calling is unproven until `tools/opencode_free_probe.py` passes for the exact model. The human's current message overrides these seats.
