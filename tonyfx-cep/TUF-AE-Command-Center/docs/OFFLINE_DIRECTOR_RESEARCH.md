# TonyFX Offline Director V2

## Objective

Build and revise an After Effects edit locally from a TonyFX Analyze blueprint while preserving reference timing, the user's source framing, and Tony's approved graph/effect rules.

## Research translated into TonyFX

- PySceneDetect exposes multiple complementary detector families instead of one universal cut detector. TonyFX therefore keeps Analyze evidence and confidence per boundary instead of forcing every boundary through one generic transition rule: https://www.scenedetect.com/docs/latest/api/detectors.html
- OpenTimelineIO models editorial structure separately from media and effects. TonyFX follows the same separation: the Analyze blueprint is the edit contract, selected AE layers are the source pool, and every build or revision is a new composition: https://github.com/AcademySoftwareFoundation/OpenTimelineIO
- OR-Tools documents global assignment optimization rather than independent greedy choices. TonyFX uses a bounded beam planner across the complete shot sequence so repeat penalties, semantic matches, source duration, frozen shots, and prior assignments are evaluated together: https://developers.google.com/optimization/assignment
- llama.cpp grammars demonstrate that local instructions can be constrained into structured output. TonyFX uses a deterministic, offline prompt compiler with a small supported editing vocabulary instead of sending revision prompts to a cloud model: https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- FFmpeg's filter documentation reinforces explicit, composable media operations. TonyFX likewise expands measured compound transitions into named AE operations and refuses to disguise unsupported effects as a generic blur: https://www.ffmpeg.org/ffmpeg-filters.html

## Director controls

- `Exact Replica`: maximum blueprint fidelity and measured repeat behavior.
- `Clean Balanced`: reference-driven pacing with stronger repeat protection.
- `Creative Remix`: measured reference structure plus bounded, seeded accents.
- `Seed`: makes a source-plan and creative choices repeatable.
- `Fidelity`: weights Analyze's exact/semantic footage matches.
- `Transition strength`: scales effect magnitude without changing cut times.
- `Transition density`: reduces optional transition treatment outside Exact mode.
- `Repeat protection`: penalizes reuse inside the selected shot window.

## Supported revision language

The local compiler recognizes requests such as:

- `Replace repeated clips and use more Aniya shots.`
- `Change shots 4, 7 and 9. Keep everything else.`
- `From 8.2 seconds until 12 seconds, use new clips.`
- `Keep the clips. Remove slides and make directional blur stronger.`
- `Alternate zooms and make them less aggressive.`
- `Use the same cuts, add a few creative impact accents.`

Unsupported prose remains visible in the prompt field but cannot invent operations outside the structured policy.

## Safety invariants

1. One base scene per measured shot.
2. Base scene ranges never overlap and never extend across a cut.
3. Source audio is always disabled on base scenes and transition duplicates.
4. Only `TRANSITION IN/OUT` duplicates may overlap, capped to 12 frames total.
5. Per-shot adjustment layers match their scene range.
6. Every re-edit creates a new composition from the original source pool.
7. Unknown transition families receive review markers.
8. Auto QA must pass before a build is reported as structurally clean.

## Verification

- Static JS/HTML/ExtendScript contracts: `tests/test-offline-director-v2.js`.
- Panel structure and syntax: `tests/check-extension.js`.
- Browser-rendered panel QA: `tests/render-analyzer-panel.js`.
- Live AE structural regression: `tests/ae-v058-offline-director-regression.jsx`.
