# TonyFX

## v0.60.0 Narrative-accurate Replica Builder

TonyFX 0.60 closes the gap between finding the correct candidate layer and using the correct moment inside that layer.

- Analyzer V6 maps hook, setup, first highlight, escalation, climax, and resolution from measured visual motion, shot duration, audio energy, onsets, and drops.
- First-highlight and climax slots carry explicit high-motion obligations. Calm, scenic, or low-action candidates cannot pass Exact Replica merely because their colors resemble the reference.
- The local footage index now measures candidate motion, optical-flow travel, pixel change, luma, contrast, subject area, and shot scale at every indexed sample.
- Vision search ranks the source moment—not only the footage file—using visual similarity plus energy, lighting, contrast, and scale evidence.
- Offline Builder trims each scene to the winning vision-matched source time. Repeat/reverse motifs reuse the same source window instead of drifting to another moment in the same file.
- Exact preflight refuses missing matched windows, short native-speed ranges, and underpowered footage in certified music-peak slots before mutating After Effects.
- Built layers and assignments record source time, match confidence, candidate motion, narrative phase, and editorial function. First-highlight and climax markers are explicit.
- Finished-edit comparison adds an independent peak-energy gate, so a high aggregate similarity score cannot hide weak footage at the reference's musical highlights.
- Dialogue visual policy is carried in the contract: visible mouth movement without aligned dialogue and speaker-incoherent shot choices are never treated as acceptable automatic substitutions.

See `docs/EXACT_REPLICA_CONTRACT_V060.md` for the execution contract.

## v0.59.0 Exact Replica contract

TonyFX 0.59 replaces the creative gap between Analyze and Offline Builder with a refusal-capable, frame-native contract.

- Deep Analyze routes the reference through the canonical Replica Lab stack in a fixed sequence: provider doctor/hash verification, Beat This, native-frame OpenCV, TransNetV2, detector consensus, repeat topology, and per-event curve fitting.
- Analyzer preserves half-open frame ranges, exact rational FPS, transition ownership, measured curves, forward/reverse topology, audio events, provider trace, and unresolved ambiguity in `tonyfx.replica-builder-contract.v1`.
- Exact Replica is the default build mode and remains unavailable when its build gate has unresolved blockers. Missing graphs, unsupported effect families, failed provider stages, and unsafe source assignments are never replaced with generic effects.
- Builder applies scene zoom only where the reference measured one. It no longer zooms every shot, and a transition-owned zoom is no longer suppressed merely because BlurMoCurves is enabled elsewhere.
- Every repeat consumes its measured playback direction. TonyFX no longer alternates reverse playback by occurrence.
- Exact source footage stays at 100% speed. Sources that are too short, internally cut, unable to reverse, or outside the evidence-ranked match set are refused before AE mutation.
- Copied layers are identified by object identity instead of assuming the new layer is always layer 1.
- Structural QA now recognizes TonyFX's real prefixed adjustment-layer names, verifies measured scene-zoom count, checks zoom overlap ownership, frame boundaries, source speed, repeat topology, audio leaks, gaps, overlaps, and transition duration.
- Finished-edit comparison exposes independent format, cut, transition, curve, duration, framing, and repeat-topology gates. An aggregate score cannot authorize a pass.

See `docs/EXACT_REPLICA_CONTRACT_V059.md` for the execution contract and refusal rules.

## v0.58.0 Offline Director

TonyFX 0.58 replaces the one-pass Offline Builder controls with a local Offline Director. It compiles plain-language revision requests into deterministic edit policy, plans the complete shot sequence globally, and builds every revision into a new composition while preserving the original source comp.

- Exact Replica, Clean Balanced, and Creative Remix modes.
- Seeded, repeatable planning with fidelity, transition strength, transition density, and repeat-window controls.
- Prompt revisions can replace repeated clips, bias a subject, change selected shot numbers or time ranges, preserve clips while changing transitions, disable transition families, alter zoom direction or strength, and request bounded creative accents.
- Re-edit uses the original source comp plus the previous assignment map instead of treating the generated edit as fresh source footage.
- Base `AUTO SCENE` layers stay mutually exclusive and muted. Only named transition duplicates may overlap a cut, and their total lifetime is capped at 12 frames.
- Automatic post-build QA detects base-scene overlaps, gaps, source-audio leaks, oversized transition duplicates, and transition effects placed directly on protected base footage. A bounded repair pass runs before the result is accepted.
- `Audit Active Edit` exposes the same structural QA independently of building.
- Slides and whips honor the Director intensity control while retaining the measured reference direction, duration, and fitted curve.

The prompt compiler and planner are fully local and consume no Codex plan usage. TonyFX still cannot recover proprietary plugin metadata from a flattened reference; uncertain or unsupported transition families remain visible review markers rather than being silently replaced.

## v0.56.3 visible Analyze controls and frame-safe offline builds

- Styled Analyze and Finished Edit QA controls explicitly so usable buttons never render as washed-out native controls.
- Unavailable actions remain visible and clickable with prerequisite feedback.
- Clamped offline-build work areas to AE's frame-quantized legal range, preventing `workAreaDuration` out-of-range errors.

## v0.56.2 always-responsive Analyze controls

- Removed native HTML locks from Report, AE Markers, Compare Edit, Repair Plan, Apply Safe Repair, and Build Offline Edit.
- Unavailable actions now remain clickable and explain the exact prerequisite in the footer.
- Successful analysis no longer re-disables Compare Edit while waiting for a rendered edit.

## v0.56.1 reliable Analyze actions and offline builder

- Analyze report, AE marker, safe-repair, and offline-build commands now use file-backed payloads instead of oversized inline CEP strings.
- Every Analyze/QA action remains clickable and reports its missing prerequisite instead of silently doing nothing.
- Local report and repair-plan files open through Windows Explorer with visible success or error feedback.

## v0.56.0 offline editing, paired text motion, and reference Color Match

TonyFX 0.56 adds a timeline text composer with matched native-AE entry and exit animation, longer visible motion presets, signed graph tangents for decreasing zoom properties, and an upgraded offline edit builder. The builder uses Analyze shot matches when available, avoids immediate repeats, mutes all source audio, preserves user framing, applies Motion Tile, prefers full-scene BlurMoCurves zooms with the approved speed-ramp curve, and expands measured compound transitions into native AE effect stacks.

### Reference Color Match

- Offline temporal sampling from video or still references.
- Bounded face-aware tone and chroma matching with measurable before/after QA.
- Dedicated, removable editable Lumetri application for selected AE layers.
- Skin-drift, highlight-clipping, shadow-crushing, and saturation safety gates block unsafe matches.
- Precision frame-aware ProRes render preserves protected skin and source audio; a conservative 33-point `.cube` LUT is also exported.
- Batch application preserves existing Lumetri effects and keeps all Lumetri effects above Motion Tile.

## v0.54.4 identity-safe generation and text verification

- Verifies all 20 text-motion presets and all 12 auto-caption animations live in After Effects.
- Adds reference-identity restoration before strict YuNet geometry and SFace identity validation.
- Rejects warped, frozen, scene-changing, or identity-lost outputs before AE import.
- Installs both face-analysis models automatically with the local video runtime.

## v0.54.3 text impact and generation stability

- Preserves every text preset's own duration and motion amount instead of flattening them through shared controls.
- Makes all 20 text motions and all 12 caption animation variants visibly distinct and removes stale TonyFX animators when switching presets.
- Uses a memory-safe 8-bit T5 encoder for LTX on 8 GB GPUs while keeping the video transformer and decoder at full FP16 quality.
- Adds strict face-geometry and SFace identity validation so warped generations are rejected before import.
- Returns the real ExtendScript error and line through the TonyFX bridge instead of a generic script failure.

- Text cards preserve their own distance and duration instead of inheriting the shared 120 px motion control. The twenty text recipes now use clearly visible position, scale, blur, tracking, rotation, wipe, flicker, and settle treatments built with native AE Text Animators and Range Selectors.
- Auto Caption animations use the same preset-specific engine and finish their entrance quickly enough for the caption to remain readable.
- Video prompts no longer receive a hardcoded wide walking shot or contradictory locked/subtle directions. The requested action is authoritative and only non-conflicting UI direction is appended.
- Balanced Local LTX is the supported default on the current RTX 4060 / 16 GB RAM machine. FramePack remains an explicit experimental option and stops immediately with a hardware explanation below 24 GB RAM instead of paging for many minutes.
- Identity Safe generation requires a detectable reference face. Small reference images are enlarged for YuNet detection, and generated videos are rejected for frozen optical flow, accidental cuts, or unstable facial geometry before AE import.

## v0.53.0 text motion reliability

- Text motion buttons now create distinct AE animator recipes instead of sharing one generic fade.
- Applying another TonyFX text motion replaces the prior TonyFX motion while preserving text styling and Text FX.
- Auto Captions uses the same preset-specific engine for word, letter, wipe, blur, pop, 3D, tracking, and wave reveals.
- Added a live AE matrix test for all manual and caption animation presets.

## v0.52.0 captions, audio, graphs, and offline builder

Caption phrases now preserve Whisper word timestamps into AE, Graph Lab includes an editable and saveable cubic-Bezier surface, Audio Lab includes validated enhancement controls, and Analyze can create a separate muted first-pass edit from selected source layers without changing the source composition.

## v0.51.0 generation safety

- Video references are aspect-preserving and face-aware instead of stretched into the selected canvas.
- Face / Identity Safe mode uses denser native temporal sampling and a minimum useful inference budget.
- LTX receives its recommended frame-rate and timestep-aware VAE decode values.
- Generated clips are rejected before AE import when faces disappear, geometry jumps, or an unrequested scene cut appears.
- Portrait, square, and landscape reference images automatically select the nearest output aspect in the panel.

## TonyFX 0.50 Deep Transition Forensics

- TransNetV2 neural shot boundaries supplement TonyFX's established scene/effect separation.
- RAFT Small measures dense flow direction, coherence, residual motion, and per-frame trajectories.
- LightGlue with ALIKED estimates reliable same-shot translation, zoom, rotation, and perspective motion.
- Video Depth Anything Small measures temporal depth on the highest-priority Deep events.
- Transition DNA ranks measured fingerprints, stores user-approved corrections, and produces evidence-backed AE recipes.
- Deep evidence remains advisory below its confidence threshold, preventing uncertain geometry from changing correct base classifications or adding speculative effects.
- Analyze writes the `tonyfx.reference-analysis.v4` JSON blueprint, HTML report, and evidence contact sheet locally.

## TonyFX 0.49 Local Video Studio

- Local text-to-video and first-frame image-to-video generation through the official LTX-Video Diffusers pipeline.
- Structured shot prompts combine the editor's idea with explicit camera, motion, lens, lighting, framing, and creative-recipe controls.
- RTX 8 GB mode uses sequential CPU offload, VAE tiling, attention slicing, TF32, and reduced base-frame sampling.
- Draft, Fast, Balanced, and Maximum Quality profiles control denoising steps independently of output duration.
- Base motion is reconstructed to 24/25/30 fps, encoded as full-duration H.264, validated before import, and accompanied by reproducibility metadata.
- Generation supports progress, cancellation, local model caching, full panel preview, deterministic seeds, and optional automatic AE import.

Private CEP panel for Adobe After Effects 2023 through 2026. It combines zero-credit local actions with an in-panel Codex chat that uses the machine's existing ChatGPT-authenticated Codex CLI.

The Effects library includes preview-first beat effects and paired cut transitions. Select an effect to watch its original two-scene preview, then apply it explicitly. Paired transitions require exactly two adjacent scene layers and build separate outgoing and incoming treatments around their cut.

## Modes

- Quick Actions execute directly in After Effects and consume no Codex credits.
- Ask Codex starts or resumes a Codex CLI session and uses the current Codex plan.
- Full editing tasks use the existing command-file format, serviced directly by this panel.
- The header usage meter reads local Codex rate-limit telemetry, shows the lowest remaining active allowance, and refreshes after tasks or when clicked.

## TonyFX 0.30

TonyFX 0.30 adds five new visual themes, a Guided workspace for new users, a real-footage effect preview, expanded Text and Motion libraries, editable text styling, an AE vector icon browser, and fully local English/Arabic captions powered by Faster Whisper.

## TonyFX 0.31

TonyFX 0.31 expands Create Studio with 13 editable text treatments, including layered shadows, dual glow, neon, bevel styling, highlight sweeps, blur/tracking reveals, and genuine per-character X/Y/Z text animation. Offline Captions can apply the same appearance and treatment system while generating editable English or Arabic caption layers.

## TonyFX 0.47 Reference Intelligence V3 + Local Vision

The Analyze page measures flattened reference edits locally without uploading media or consuming Codex usage. V3 preserves the canonical V2 cut detector and adds multi-frame rendered transition hypotheses, optimized duration/strength scoring, fitted cubic Bezier curves, subject framing QA, searchable semantic shot requirements, bar/drop/reverb audio structure, installed AE effect inventory checks, a persistent correction library, and finished-edit comparison with a frame-specific repair plan. TonyFX 0.47 also inventories the actual AE project footage, builds a FAISS similarity index, ranks shot candidates with OpenCLIP and DINOv2, detects and frames people with YOLO11n, measures depth with Depth Anything V2, segments subjects with SAM 2.1, and measures temporal travel with CoTracker 3. References with unreliable timestamps are normalized to a deterministic CFR proxy before analysis.

The Analyzer writes an editable V3 JSON blueprint, an enriched HTML report, and a proof contact sheet. It can render disposable transition candidates in real After Effects, score them against the reference, apply cut/effect and optional beat markers with an intro offset, compare a finished render, and create a non-destructive Safe Repair duplicate. The protected source composition is never used as the repair target.

Flattened video cannot reveal proprietary plugin metadata. TonyFX therefore labels effect stacks as measured inferences and preserves confidence/evidence instead of claiming false certainty.

## TonyFX 0.48 Enhance Integrity + Transition Contracts

TonyFX 0.48 validates every enhanced frame sequence and final media stream before import. The bundled Real-ESRGAN x4plus model now runs only at its native 4x inference scale, preventing the mosaic corruption caused by forced 2x Vulkan output; TonyFX then downsamples cleanly to the requested delivery size. Unsafe GPU output is rejected and retried or completed through the safe FFmpeg restoration path. ProRes masters receive a separate full-duration H.264/AAC panel proxy, so preview playback no longer depends on CEP decoding ProRes.

Effects now use explicit animation contracts. One-way impact effects use two keys and a clean fast-start decay. Neutral-to-peak-to-neutral cut pulses retain three keys only when the return to neutral is genuinely required. Transient adjustment layers are trimmed to their first and last effect keys, while static looks span only the selected scene; paired transitions span only their measured cut interval.

## Color Studio

TonyFX 0.9 adds a dedicated Color page backed by the native After Effects Lumetri Color effect. It can read, apply, live-preview, or reset Basic Correction, Creative, Color Wheels where exposed by the installed AE build, and Vignette controls. Grades target selected inner footage, skip protected layers, and keep Lumetri above Motion Tile.

Included grades: Clean Bright, Warm Romance, Cool Steel, Night Lift, Neutral, Teal + Orange, Film Print Warm, Bleach Bypass, Cyber Neon, Golden Hour, Pastel Airy, Moody Green, Sunset Magenta, Contrast Mono, and Luxury Skin Pop.

## Graph Lab

TonyFX 0.10 adds a separate Graph Lab with drawn easing curves and names beneath each graph. The Text and Motion modes include local previews: type custom text or use the graphic stage, choose an animation, preview it without touching AE, then apply the selected preset deliberately to AE.

## Trend Lab

TonyFX includes original, editable native-AE tools informed by current short-form editing patterns:

- Text: Blur Reveal and Tracking Reveal.
- Motion impact: Ghost Zoom, Echo Trails, Radial Zoom Blur, Flash + Shake, and Fast Whip Left/Right.
- Optical polish: Optical Ripple, Lens Glimmer, and Soft Halation.
- Rhythm: Clean Black Hit.
- Current impact tools: Punch Flicker, RGB Pulse, Camera Snap, and Zoom Stutter.

## Designs

- Classic: restrained brass and wine studio styling.
- Titan: graphite and cyan industrial styling.
- Volt: black and yellow technical linework with responsive angled rails and controls.
- Gears: the Classic interface filled with a high-resolution reference-matched antique machinery master, compass drafting, geometric proofs, and mathematical equations, with sharp coordinated crops carried through its controls.

Local presets consume no Codex usage. Select the intended non-protected layer, place the playhead at the impact or transition, set Duration and Amount, then click a preset. TonyFX adds clearly named effects and one After Effects undo step reverses the operation. Zoom, shake, and whip presets use effect-level Transform controls so existing layer Position and Scale keys remain intact.

## Safety

- The panel never launches or closes After Effects.
- Do not open the old MCP Bridge Auto panel at the same time; Command Center owns the bridge while it is open.
- Layers marked `[TUF_PROTECTED]`, locked layers, and recognized intro layers are skipped by local mutating actions.
- Motion Tile is applied to inner footage layers at 200x200 with Mirror Edges and ordered below Lumetri.
- The approved opacity action creates a full-scene `45 -> 100 -> 45` arch.
- Codex commands always request inspection first and preservation of unrelated manual adjustments.

## Development Source

`C:\Users\TUF\Documents\New project\tuf-ae-command-center`

## Open in After Effects

After installation, close any already-open TonyFX panel and use:

`Window > Extensions > TonyFX`

Run `install.cmd` again after future local updates.

The installer mirrors the current package and clears only TonyFX's disposable CEP web caches. Saved panel settings in Local Storage are preserved.
