---
name: ae-reference-replica
description: Analyze reference videos, songs, and footage to reproduce their timing, effects, transitions, graphs, repeats, framing, and emotional flow in After Effects while using different source shots. Use when the user asks to study, copy, replicate, map, or match a reference edit.
---

# AE Reference Replica

Build an evidence-based, frame-native replica specification before changing After Effects. Treat exact replication as a measurable structural contract. Never allow an aggregate similarity score to hide a failed cut, transition, curve, repeat, crop, or black edge.

## Safety and execution policy

- Read the TFX master context when the trigger or workspace rules require it.
- Inspect the active AE project through TonyFX before assuming the active composition.
- Do not run MCP Bridge Auto while TonyFX is open.
- Warn the user and wait for readiness before dense footage decoding, model downloads, GPU inference, optical flow, large proxy renders, or other high-RAM/VRAM stages.
- Keep analysis standalone. TonyFX is an optional AE inspection/execution bridge, not the sole analysis engine.
- Use only free/local analysis dependencies unless the user explicitly changes that requirement. Paid AE effects already licensed by the user may be optional render targets, never mandatory analysis dependencies.

## Canonical analysis system

Use `C:\Users\TUF\Documents\New project\TFX_REPLICA_LAB` as the canonical Replica Lab. Its build spec and strict validator supersede the legacy prose-heavy manifest for exact-reference work.

1. Inventory media through Replica Lab and record immutable paths plus hashes.
2. Probe every reference and source with exact rational FPS, dimensions, duration, frame count, audio properties, and hashes.
3. Preserve the reference rate exactly, including 50, 59.94 (`60000/1001`), 60, or higher rates. Never downsample or default to 24/25/30.
4. Analyze cuts and source-shot boundaries frame by frame. Store intervals as half-open `[in,out)` frame ranges.
5. Analyze audio independently: alignment, beats, downbeats, onsets, sections, and salient transients in reference frames.
6. Store structured transitions with exact range, cut frame, family, direction, owners, measured curve controls, and parameters. Prose may explain evidence but cannot replace structure.
7. Detect deliberate loops and store exact source range plus ordered forward/reverse topology. A requested normal/normal/reverse/reverse loop must validate in that exact order.
8. Index source footage densely. Preserve exact source path, source frame range, continuous-shot ID, motion evidence, semantic evidence, quality evidence, subject visibility, and crop-safe margins.
9. Resolve ambiguity before building. Any unresolved blocking ambiguity prevents AE payload generation.

## Required provider routing

Do not merely keep the local analyzers installed; use them in this order for every reference-replica job. A provider may be skipped only when the input lacks its modality or the provider fails. Record the skip, failure, fallback, and affected confidence in the proof artifact—never skip silently.

1. Run `tfx-replica doctor --registry profiles/installed-stack.json --verify-hashes` before analysis.
2. Use FFprobe/FFmpeg for exact media metadata, hashes, native-frame decoding, and lossless audio extraction.
3. Run Beat This on the extracted reference audio for beats and downbeats; preserve other onset evidence separately.
4. Run TransNetV2 and the OpenCV native-frame detector on the reference and source media, then reconcile them with `cut-consensus`. Keep detector disagreements as explicit ambiguities.
5. Run `detect-repeats` on reference scenes and preserve the ordered forward/reverse topology and exact source interval.
6. Run `fit-curves` per measured transition or zoom event. Never substitute one reusable graph for event-specific evidence.
7. Run `index-footage` over all candidate source media using TransNetV2, OpenCV, and SigLIP2. Cache the dense index by media hash.
8. Run Qwen3-VL through `adjudicate-candidates` on finalists and ambiguous shots. Treat high crop risk, tight framing, obscured subjects, and low wide-shot suitability as vetoes when the slot requires a wide or zoom-safe shot. Qwen is a finalist gate, not a wasteful every-frame pass.
9. Run SEA-RAFT on finalist source ranges and transition windows to verify movement magnitude and separate camera motion from subject motion. SEA-RAFT is a motion gate on selected ranges, not a full-video default.
10. Use the OR-Tools CP-SAT planner for global shot assignment under duration, uniqueness, framing, movement, and repeat constraints.
11. Run the strict validator and generate the certificate-bound AE payload. Do not enter AE while blocking ambiguities remain.
12. After the proof render, run VMAF plus the independent structural gates in this skill. VMAF cannot waive timing, topology, framing, black-edge, or ownership failures.

## Shot assignment rules

- Match reference structure and emotional function while choosing the user's requested character and footage.
- Enforce continuous shots with no hidden internal cuts.
- Enforce adequate movement when requested and prefer wide/medium-wide shots when animated zooms would crop a close-up.
- Do not repeat a source shot unless the reference repeat topology requires it.
- Bind every repeat group to one exact source range and explicit playback direction per event.
- Keep the main subject inside the delivery safe area at every animated scale/position value.
- Reject any candidate with black-edge risk, subtitle exposure, insufficient duration, or inadequate crop margin.

## Motion and effect ownership

- Exactly one layer/system owns each zoom event: scene, transition, or none.
- Never stack two motion-blur zoom layers or combine a transition-owned zoom with a scene-owned zoom at the same event.
- Fit curves per measured event. Do not reuse a universal speed graph or force the legacy `approved_rising_speed_ramp` shape.
- Match transition family, direction, duration, peak, blur, opacity, and layering independently.
- Do not add flashes, shakes, or other impacts that are absent from the reference.
- If a licensed AE plugin is unavailable, use a native/free implementation that preserves the measured motion family; document the fallback.

## Required gates before After Effects

Run the Replica Lab strict validator. AE payload generation must remain blocked unless all of these pass independently:

- exact reference/composition rational FPS, dimensions, and total frames;
- contiguous timeline coverage with protected ranges explicitly declared;
- exact cut frames and structured transition ownership;
- valid per-event curve controls and transition direction;
- exact repeat source ranges and forward/reverse topology;
- no internal source cuts;
- movement and wide-shot constraints;
- no duplicate zoom ownership;
- no black-edge or unsafe-crop risk;
- frame-aligned audio events;
- no unresolved blocking ambiguity.

The deterministic AE payload must include a validation certificate bound to the canonical spec SHA-256. AE may implement the payload but must not invent creative decisions or round timing.

## Proof and repair

1. Render a disposable proof at the exact reference frame rate and dimensions.
2. Compare cut precision/recall, frame error, transition family/direction/duration, curve distance, repeat topology, framing, black edges, and duplicate zooms as separate gates.
3. Produce a proof report with failed regions and evidence. Never rely on one blended score.
4. Repair only failed regions in a duplicate composition unless the user explicitly authorizes direct modification.
5. Re-render and re-run every gate. Call the replica complete only when all required gates pass or the user explicitly accepts documented deviations.

## Legacy manifests

Use Replica Lab migration only to preserve available data and rescale frame coordinates exactly. Migration must not invent transitions, curves, loop topology, framing, or motion evidence. Missing structure remains a blocking ambiguity until re-analysis resolves it.
