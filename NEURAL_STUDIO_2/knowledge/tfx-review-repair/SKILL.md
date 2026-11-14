---
name: tfx-review-repair
description: Audit rendered edits and live AE state, then repair only failed regions while preserving manual work. Use for choppy flow, repeated footage, crop/matte/text/audio glitches or final acceptance checks.
---


# Review and scoped repair

1. Identify the current saved project, comp and review revision. A render produced before later fixes is stale. Do not diagnose current AE from an old MP4 without labeling the mismatch.
2. Snapshot all user-authored/protected state before repair. Compare stable IDs, keyframes/eases, text, effect order, masks, transforms and source mapping. Evaluate animated values at identical times.
3. Structural gates: frame count/rate/dimensions, source spans, gaps/overlaps, one zoom owner, effect coverage, missing media/fonts, complete dialogue exposure, no source-audio leak.
4. Content gates: chronology, lead-character focus, shot variety, meaningful pairings, earned peak action, no unmotivated talking or repeated footage. Stronger glow cannot pass a weak story.
5. Image gates: start/middle/end of each shot, significant pose changes, transition frame-1/frame/frame+1 and settling frames. Check masks for ALL characters, crop, black edges, duplicated limbs, optical-flow warps, exposure jumps, text readability and intended occlusion.
6. Motion and audio gates require normal-speed playback/listening where available. Contact sheets, ASR and numeric scores are supporting evidence, not substitutes. Explicitly state untested modalities.
7. Repair only failed layers/ranges/properties. Do not normalize protected user curves or reapply old builders. Recheck repaired boundaries plus affected neighboring shots and preservation diff.
8. When a review render is requested, decode it fully, verify expected frames/audio and inspect representative dense windows/full playback. When user explicitly says no render, stop at authorized AE/state/frame checks and disclose the remaining playback check.

Output a per-gate result: PASS, FAIL or NOT TESTED, with evidence filename, revision and remaining action. No aggregate number may hide a failed independent gate. A script success is not a visual pass; a technical pass is not user approval. Never say perfect on the strength of automated tests.

## Local mechanical execution

Inside Neural and ordinary editing chats, route supported mechanical media work through [neural-local-ops](<C:/Users/TUF/.codex/skills/neural-local-ops/SKILL.md>) and the [shared local engine contract](<C:/Users/TUF/Documents/New project/NEURAL_STUDIO/shared/LOCAL_OPS_WORKFLOW.md>). Query its CLI capabilities before preparing a bounded plan. Use scripts for repeated measurements/extraction/audio transforms/validation and inspect saved evidence; models interpret creative intent and ambiguous results. Keep technical PASS separate from playback/listening and human artistic approval. Preserve existing TonyFX authorization, exact live identity and single-writer safeguards for native work.
