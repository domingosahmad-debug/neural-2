# TFX Canonical Master Context

## Current execution update — 2026-10-20

The user's editing workflow now uses the shared Neural local engine for repeatable mechanical work, inside Neural and ordinary editing chats. Before rewriting a preparation script or assigning a model to routine measurements, read `C:/Users/TUF/Documents/New project/NEURAL_STUDIO/shared/LOCAL_OPS_WORKFLOW.md` and run `python "C:/Users/TUF/Documents/New project/NEURAL_STUDIO/tools/local_ops.py" capabilities`. Built-in prepare/delivery recipes, exact frame/contact-sheet evidence, audio arithmetic/alignment, plan collision checks, protected-state comparisons, compact evidence, render QA and review packaging share a serialized queue and verified cache. The app does not need to be open for the standalone CLI.

Models retain creative/semantic interpretation and difficult native integration. Local mechanical stages make zero model calls; active director/creative/learning turns still consume their allowances. Use one final event wake, no inference polling. Native work retains TonyFX single-writer ownership, exact-state guards, no replay of unknown commands and separate artistic acceptance. Current compiler support is picture-only; unsupported captions/effects/audio construction remains with its relevant native workflow. Historical project states below do not authorize resuming paused work. Full release evidence and limitations: `NEURAL_STUDIO/shared/LOCAL_OPS_RELEASE.md`.

Last consolidated: 2026-08-23

## Purpose

This is the single canonical handoff for TUF's After Effects editing workflow, TonyFX extension, reference-replica method, local analysis tools, export preferences, communication rules, and known failure patterns. A fresh Codex task can read this file and continue the established workflow without loading the long historical chat.

This file captures all durable, actionable context available from the main TFX history, the prior master/context files, the stand-up montage handoff, the TonyFX source tree, and the latest verified fixes. It cannot contain hidden chain-of-thought, inaccessible internal model state, or a private verbatim system transcript. Those are neither transferable nor required. The concrete rules, paths, tested behavior, and project knowledge needed to work consistently are recorded here.

## Fresh Task Startup

Open the new Codex task with workspace folder:

`C:\Users\TUF\Documents\New project`

Then send:

`TFX. Read C:\Users\TUF\Documents\New project\TFX_MASTER_CONTEXT_2026-08-20.md completely. Inspect the active After Effects project through TonyFX before changing anything. [Describe the task.]`

For the stand-up montage, send:

`STANDUP. Read C:\Users\TUF\Documents\New project\TFX_MASTER_CONTEXT_2026-08-20.md and C:\Users\TUF\Documents\New project\STANDUP_MONTAGE_MASTER_HANDOFF.md completely. Inspect the active After Effects project through TonyFX before changing anything. [Describe the task.]`

Never assume the open project, active composition, selected layers, current time, or protected intro. Inspect first.

## Environment And Canonical Paths

- Main workspace: `C:\Users\TUF\Documents\New project`.
- Default After Effects version: Adobe After Effects 2023 unless the user explicitly says otherwise.
- TonyFX source: `C:\Users\TUF\Documents\New project\tuf-ae-command-center`.
- Installed TonyFX CEP extension: `C:\Users\TUF\AppData\Roaming\Adobe\CEP\extensions\TUF-AE-Command-Center`.
- Current source and installed release: TonyFX `v0.60.0`.
- TonyFX local engine: `C:\Users\TUF\Documents\TonyFX Local Engine`.
- TonyFX vision engine: `C:\Users\TUF\Documents\TonyFX Vision Engine`.
- TonyFX output root: normally `C:\Users\TUF\Videos\TonyFX Outputs`.
- AE command bridge: `C:\Users\TUF\Documents\ae-mcp-bridge`.
- Command file: `C:\Users\TUF\Documents\ae-mcp-bridge\ae_command.json`.
- Result file: `C:\Users\TUF\Documents\ae-mcp-bridge\ae_mcp_result.json`.
- TonyFX installer: `C:\Users\TUF\Documents\New project\tuf-ae-command-center\install.ps1`.
- Private Codex editing plugin/skills: `tuf-ae-editing` plus local `ae-build-edit`, `ae-audit-repair`, `ae-reference-replica`, `ae-captions-audio`, and `ae-export-quality` skills.
- Stand-up master: `C:\Users\TUF\Documents\New project\STANDUP_MONTAGE_MASTER_HANDOFF.md`.
- Historical detailed context archive: `C:\Users\TUF\Documents\New project\TFX_CONTEXT.md`.

## TonyFX Bridge Protocol

TonyFX is the preferred AE bridge host. Keep TonyFX open and do not open MCP Bridge Auto at the same time. MCP Bridge Auto is fallback-only when TonyFX is closed or unavailable. Never launch several AE instances or repeatedly close and reopen AE.

TonyFX `v0.58.1` repairs the command-loop problem:

- Every bridge command must have a new unique `id`, `status: "pending"`, a supported `command`, and its `args`.
- TonyFX takes an exclusive lock before executing. Two panels cannot execute the same command concurrently.
- TonyFX persists the last processed command ID. Rewriting the same ID to `pending` must not rerun it.
- TonyFX writes `_commandId` into the result. Accept a result only when `_commandId` matches the submitted command ID.
- TonyFX rereads and validates the command after acquiring the lock, deletes the prior result before a new run, and updates only the matching command record.
- A running command has a heartbeat and a 45-minute ceiling. Timeout produces an error; it does not retry automatically.
- If TonyFX restarts while a command is running, stale work is marked interrupted after recovery. It is not silently rerun.
- A failed, timed-out, or interrupted operation must be corrected and submitted with a new ID. Never loop the same command.
- Wait for completion before issuing another AE mutation. Inspection and rendering commands also use unique IDs.
- If a real blocker remains, report `HELP TONY: <exact blocker>` once and continue any independent work that is still possible.

The TonyFX panel owns normal creative command dispatch while open. Do not use Computer Use for routine AE work. Do not open file dialogs or multiple AE windows to work around a bridge problem.

## TonyFX v0.60.0 Narrative-Accurate Replica Contract

- Analyze writes `tonyfx.reference-analysis.v6` with blueprint version 6 and retains the `tonyfx.replica-builder-contract.v1` execution certificate.
- V6 maps hook, setup, first highlight, escalation, climax, and resolution from measured shot motion, duration, audio energy, onsets, drops, and temporal position.
- First-highlight and climax slots carry explicit high-motion requirements. Calm, scenic, or low-action indexed footage blocks Exact mode at those slots.
- The footage index measures the actual candidate moment: source time, optical-flow motion, pixel change, luma, contrast, subject area, and shot scale, in addition to OpenCLIP/DINO similarity.
- Builder uses the winning source time centered on the target shot duration. It no longer chooses the correct layer and then accidentally starts from that layer's in-point.
- Forward/reverse repeat motifs reuse the same source window. Exact preflight refuses short matched windows, missing matched moments, and underpowered peak footage before AE mutation.
- Scene assignments and layer comments record source time, confidence, motion score, narrative phase, and editorial function. First-highlight and climax composition markers remain explicit.
- Finished-edit comparison version 4 has an independent peak-energy gate; aggregate similarity cannot hide weak footage at the song's highlights.
- Dialogue visual policy is explicit: visible mouth movement without aligned dialogue and speaker-incoherent shot choices are not acceptable automatic substitutions.
- Live AE regression passed exact source-time centering, peak motion gates, first-highlight/climax markers, native speed, forward/reverse window reuse, zero gaps/overlaps/audio leaks, and backward-compatible Balanced/Creative/Exact builds.

## TonyFX v0.59.0 Exact Replica Contract

- Deep Analyze routes through the canonical Replica Lab provider order and writes `tonyfx.replica-builder-contract.v1` with frame-native shots, transitions, curves, repeat directions, audio events, provider evidence, ambiguity, and a certificate.
- Exact Replica is the default and refuses missing providers, unresolved blockers, generic curve/effect fallbacks, unsafe candidate assignments, unsupported reverse playback, short sources, and non-native source speed before AE mutation.
- Builder no longer applies a generic zoom to every shot, no longer suppresses measured transition zooms because BlurMoCurves is enabled, and no longer alternates repeat direction by occurrence.
- Copied AE layers are identified by object identity rather than assuming the copied layer becomes layer 1.
- Structural QA recognizes TonyFX's real prefixed adjustment names and verifies measured zoom count, ownership overlap, frame boundaries, native speed, explicit reverse-only time remap, transition limits, audio leaks, gaps, and overlaps.
- Finished-edit comparison has independent format, cut, transition, curve, duration, framing, and repeat-topology gates; its aggregate score cannot authorize a pass.
- Live AE regression passed Balanced build, Creative re-edit, and certified Exact build with measured scene zoom and forward/reverse topology while restoring the user's original project afterward.

## TonyFX v0.58.1 Verified Fixes

- The source and installed extension are byte-for-byte synchronized for `js\app.js`, `css\panel.css`, `index.html`, and `CSXS\manifest.xml`.
- TonyFX bridge execution is exactly-once per command ID, lock-protected, timeout-bounded, and stale-run safe.
- The Color page is one continuous vertical scroll document. Color Match no longer collapses or traps the Lumetri controls below it.
- The final Vignette control is reachable in both normal and narrow panel layouts.
- Passed checks: extension structure/JavaScript syntax, bridge regression contracts, Offline Director V2 static contracts, and Color page visual/scroll tests.
- After installation, close only the TonyFX panel and reopen `Window > Extensions > TonyFX` to load the new in-memory code. Do not restart AE unless actually needed.

## Core Editing Contract

- Preserve every user adjustment. Modify only the named composition, range, layers, and properties.
- Duplicate a composition before a broad rebuild or reference-rematch unless the user explicitly says to modify the current comp directly.
- Protect layers, ranges, and markers named `Intro`, `INTRO`, `USER AREA`, `DO NOT EDIT`, `PROTECTED`, or equivalent. Do not touch them unless the user explicitly requests intro treatment.
- One beat-cut layer equals one continuous shot from one camera angle. Never hide two camera angles or internal cuts inside one scene layer.
- Do not accidentally transition a scene into the same scene. Avoid overusing familiar footage; vary order between versions.
- Mute source-footage audio unless dialogue, laughter, applause, or a natural reaction was intentionally selected.
- Effect and adjustment layers must be above the footage they affect. A per-scene adjustment spans exactly its scene. A transition layer spans only its intended transition/key range.
- Do not extend base scene layers to manufacture transitions. Use short muted transition duplicates when overlap is required.
- Never stack two zoom systems on one scene. If BlurMoCurves controls the zoom, do not add outer Scale animation, a second BlurMoCurves layer, or another hidden zoom.
- Inner footage in every scene precomp starts at frame zero. The precomp is trimmed to the real visible footage span, not an overlong container.
- Verify start, midpoint, end, and one frame before/on/after every transition. A successful script response is not visual proof.

## Composition, Framing, And Edge Coverage

- Default social format is 1080x1080. Other requested formats include 1080x1350, 1080x1920, and 1920x1080. Use the project/reference format, not an assumed TikTok square.
- Use 24, 25, or 30 fps according to source/reference/song. Avoid 60 fps unless requested or required by the reference.
- Center the main subject or couple manually and check framing at the first, middle, and last frame plus zoom extremes.
- No black bars, side bars, top/bottom bars, duplicated blurred-background filler, split images, cropped faces, or badly cut bodies.
- For high-resolution footage, scale down enough to retain the character. For embedded subtitles, crop/scale them out at every zoom extreme.
- Motion Tile belongs directly on the layer that needs edge coverage, normally the inner footage layer of a precomp. Use Output Width 200, Output Height 200, and Mirror Edges enabled.
- Lumetri must be above Motion Tile in Effect Controls.
- Dark or unusable shots should be replaced when practical. If retained, lift them carefully without flattening skin or destroying highlights.

## Approved BlurMoCurves Zoom Standard

- Use BlurMoCurves for finished zooms instead of plain Transform Scale unless the reference clearly requires another system.
- Exactly one BlurMoCurves zoom controller per scene.
- Use two zoom keys, one on the first visible frame and one on the last visible frame. Keys span the complete shot, including long shots.
- Approved speed-ramp character: decisive start, controlled travel, decisive finish. Frequent Flow reference: `0.09, 0.72, 0.94, 0.27`.
- The animated value must remain monotonic between endpoints. Reject any hump, dip, bounce, reversal, sine curve, or sluggish inverse S-curve.
- Tangent speed sign follows the value delta: positive for increasing values and negative for decreasing values.
- Sample the generated curve across the shot. It must never cross outside the two endpoint values or change direction.
- Long scenes use the same approved graph stretched across their duration. They do not receive a different malformed graph.
- Zooms should be visible but controlled. The user commonly prefers approximately `0.750` rather than an unnecessarily aggressive `0.600`, unless the reference visibly demands more.
- Vary direction naturally. Two or three shots may move the same way before reversing; do not mechanically alternate every cut.
- For normal/reverse replay sections, choose footage with visible subject or camera motion so reverse movement reads cleanly.

## Twixtor And Time Treatment

- Precompose each Twixtor scene separately, move all attributes, trim the precomp to the selected scene span, and start inner footage at frame zero.
- Use exactly three Twixtor Speed keys: normally `150 - 35 - 150`; some established projects use `160 - 35 - 160` when explicitly requested.
- Use the approved U-shaped speed ramp. Do not use four keys.
- Do not Twixtor footage already rendered with Twixtor unless requested. Use time remapping only when required to match a measured reference replay or speed change.
- A repeated normal/reverse beat pattern must be built as actual short forward/reverse segments with correct timing, not one long clip with an effect placed over it.

## Fades, Transitions, Intro, And Outro

- Transitions occur at clip boundaries, not randomly inside a shot.
- Common approved tools: directional blur/smear, restrained glow or flash, brief position impact shake, fast slide/whip, zoom blur, opacity blend, black dip, white flash, RGB split, mask wipe, spin/perspective push, and optical ripple when supported by the reference.
- Position shake is brief, clearly felt, and returns to center. Blur, glow, exposure, and color offsets return to neutral.
- Directional blur must not linger and make the next scene sluggish.
- Glow supports impact without washing out faces unless explicitly requested.
- Opacity arches use the exact requested values, commonly `45 - 100 - 45` or `65 - 100 - 65`, with the approved smooth arch graph.
- Intro opening treatment commonly uses a strong but brief zoom-out with directional blur and glow, driven by a sharp-start graph.
- The end of an intro commonly gets a fast sharp-end impact transition into the edit. Do not alter intro content when only effects were requested.
- Endings often fade music over the last 2-3 seconds with a matching video/black fade. Preserve an existing user-made fade unless asked to replace it.

## Color Standard

- Use editable Lumetri rather than destructive baked color when possible.
- Lumetri effect order remains above Motion Tile.
- Match brightness and white balance between adjacent shots before applying a creative grade.
- Preserve skin tones and readable faces. Avoid crushed dark footage, clipped highlights, oversaturated orange skin, or a one-note color cast.
- TonyFX Color Studio contains editable presets and Reference Color Match. Color Match requires a genuinely different visual reference, not two frames from the same already-matched video.
- TonyFX AE 2023 scripting uses verified flat Lumetri properties. Color Wheels are an opaque custom data blob and must not be claimed as directly writable without a fresh live test or clearly labeled emulation.

## Captions, Lyrics, And Text

- Dialogue captions belong bottom-safe, compact, readable, usually bold/italic white with a clean downward shadow and no heavy stroke.
- Song lyrics normally sit centered, smaller and readable, with subtle shadow. Start lyrics only after dialogue ends and the lyric/edit section begins.
- Dialogue can reveal letter by letter. Lyrics reveal word by word in sync with the exact sung word.
- Do not show duplicate lyric lines or invent words not present in the audio.
- Emphasis normally uses one important word, a distinct font/scale/color, and a separate impact animation. Do not capitalize an entire sentence when one word should hit.
- Keep all text within delivery-safe bounds. Never let it overflow the comp or obscure the subject unnecessarily.
- TonyFX text motions should start at each text layer's in-point, remove stale TonyFX motion animators before applying a new preset, and preserve unrelated text style/effects.

## Audio And Sound Design

- Align cuts to the actual audio layer start, in-point, stretch, and time remapping. Marker time is not automatically raw source time.
- Use the same song section as the reference when making a replica.
- Reverb or reverse-tail treatment may lead into the edit/drop and should be on a separate removable layer.
- Sound design may include impacts, sub-drops, whooshes, risers, reverse cymbals, shutters, flash pops, glitches, swipes, scratches, tape stops, crowd accents, room tone, laughter, and applause.
- Every SFX event needs deliberate lead/on/trail timing, duration, level, stereo direction, filtering/pitch/reverb, and music ducking where needed.
- Sound must not bury intelligible dialogue or authentic audience reactions.

## Reference Replica Workflow

1. Inventory reference video, clean song, and candidate footage.
2. Normalize a damaged/VFR social download only when decoder health requires it; preserve valid duration and timing.
3. Analyze frame-by-frame boundaries, repeats, normal/reverse segments, speed changes, cut duration, zoom/slide direction, fitted curve, overlap, blur, flash, black dip, RGB, mask/perspective effects, shake, sound events, and emotional shot function.
4. Identify the exact reference song section and map it to the clean song using the real AE layer start, in-point, stretch, and time remap.
5. Catalog candidate footage by subject, action, emotion, camera angle, framing, brightness, motion, and used/unused state.
6. Reproduce reference function, timing, transition family, duration, direction, graph, and repeat/reverse language using the requested footage.
7. Do not settle for beat-synced sequencing. A replica without the visible transition/effect language is incomplete.
8. Unknown effects receive a visible `TONYFX REVIEW` marker; never silently substitute generic blur.
9. Render visual proof at shot thirds and transition boundary frames.
10. Audit gaps, overlaps, adjacent repeats, source-audio leaks, black tails, bars, crop, subtitles, effect order, duplicate zooms, and malformed graphs.
11. Save with a clear version name and state exactly what was verified.

When the reference repeats one source moment forward and reverse across several beats, preserve that temporal idea with a motion-rich candidate clip. Never replace it with one long scene.

## TonyFX Analyze And Offline Director

- Analyze runs locally and writes schema `tonyfx.reference-analysis.v6` with blueprint version 6.
- It can normalize unreliable references, analyze cuts/effect-only pulses, repeated/reversed shots, chronology resets, transition forensics, motion, depth, framing, semantic footage matches, beat/onset/drop structure, and song alignment.
- Integrated local tools include OpenCV, PySceneDetect, librosa, scikit-image, Kornia, LPIPS, OpenCLIP, FAISS, RapidOCR, SAM 2.1 Small, CoTracker 3, Depth Anything V2, DINOv2, YOLO11n, TransNetV2, RAFT Small, LightGlue/ALIKED, and Video Depth Anything.
- Analyze reports measured translation, scale, rotation, perspective, flow direction/coherence/residuals, blend/wipe/shake/photometric curves, temporal depth evidence, effect DNA matches, and evidence-backed AE recipes.
- Flattened video cannot expose proprietary plugin names or metadata. TonyFX infers visible behavior and must keep confidence/evidence attached.
- Offline Director modes: Exact Replica, Clean Balanced, and Creative Remix. Planning is deterministic by seed and revisions are built in new compositions from the original source comp.
- Local revision prompts can replace repeats, bias a subject, revise shot/time ranges, freeze clips/outside ranges, disable or strengthen transition families, alter transition speed, vary zooms, and add bounded accents.
- Base `AUTO SCENE` ranges are protected. Crossfades, wipes, and slides use short muted transition duplicates capped to adjacent shot lengths.
- Structural QA requires zero base-scene overlaps, zero base gaps, zero source-audio leaks, transition duplicates no longer than 12 frames, and no transition effects directly on base footage.
- Compare Edit and Safe Repair work on duplicate compositions and must not rewrite unrelated user work.
- Never claim Analyze/Offline Director is correct from UI or static tests alone. Validate the panel click, payload, host function, AE result, composition structure, and visible render.

## TonyFX Feature State

- Private local CEP extension; normal local tools do not consume Codex or OpenAI API usage.
- Themes: Classic, Titan, Volt, Gears, Prism, Ember, Studio, Blueprint, and Mono.
- Layouts: Pro and Guided. Guided presents Inspect, Build, Animate, Grade, Caption, and Finish.
- Create Studio: editable text input, appearance preview, fonts, fill, stroke, shadow, glow, vector icons, native-AE text treatments, and per-character 2D/3D reveals.
- Offline Captions: Faster Whisper plus FFmpeg, English/Arabic/auto language, editable AE text layers, frame-aligned timing, word/letter reveals, and CPU fallback.
- Effects catalog: adjustment-layer effects and cut effects including Glow Pulse, Directional Smear, Exposure Flash, Chromatic Hit, Clean VHS, Duotone, Ghost Zoom, Echo Trails, Radial Zoom Blur, Optical Ripple, Soft Halation, Flash + Shake, Clean Black Hit, Lens Glimmer, Punch Flicker, RGB Pulse, Flash Smear Cut, Zoom Blur Cut, Black Dip Cut, RGB Whip Cut, and Fast Whip.
- Layer tools: Pre-comp Separate, Pre-comp Together, Adjustment Layer, Null, opacity arch, inspection/protection, and Twixtor 150/35/150.
- Enhance: local Real-ESRGAN restoration/upscale, RIFE interpolation, FFmpeg output/audio preservation, batch or whole-composition input, progress/cancel, validation, preview proxy, and AE import/alignment.
- Audio: local Demucs background/vocal separation and speech cleanup where installed, with removable synchronized 48 kHz WAV output.
- Generate: local LTX-Video text-to-video/image-to-video on the RTX 4060 Laptop GPU. It is experimental and historically prone to warped faces, weak prompt adherence, or rejected results. Do not present it as cloud-model quality.
- Color: editable Lumetri presets plus Reference Color Match; Color controls are scrollable below Color Match in `v0.58.1`.
- Graph Lab: graph presets remain separate from motion presets. Basic motion uses Easy Ease unless the user explicitly applies a graph.

## Local AI And Hardware Reality

- Main GPU: NVIDIA GeForce RTX 4060 Laptop GPU with 8 GB VRAM; system has 16 GB RAM.
- Prefer the NVIDIA Studio Driver for AE, Media Encoder, Topaz, DaVinci, CUDA analysis, and TonyFX local engines. Studio replaces Game Ready; it is not an extra resident driver.
- Local generation/enhancement can take minutes. Do not confuse GPU processing time with a stuck AE bridge. Report real progress and ETA when available.
- LTX-Video 2B is hardware-limited. Face/Identity Safe validation can reject warped or frozen output but cannot make it equal to leading cloud generators.
- FramePack 13B is intentionally blocked below 24 GB physical RAM.
- Essentia is not installed because its Windows build path is unsuitable. The verified librosa pipeline is used instead.
- WhisperX is not installed because it attempted to disturb the working CUDA Torch stack. Faster Whisper remains the caption engine.

## Export And Delivery Baseline

- Prefer a high-quality intermediate from AE/Topaz, commonly ProRes 422 HQ, progressive, square pixels, source frame rate, with maximum depth/quality where relevant.
- Delivery H.264 should match the final dimensions and frame rate, use High profile and an appropriate level, hardware encoding when stable, and a sensible high bitrate rather than repeated unnecessary transcodes.
- For Instagram/TikTok, keep the master and create a separate delivery encode. Platform recompression cannot be prevented by metadata tricks.
- Sending through WhatsApp as a document preserves the uploaded file rather than the media-compressed path, subject to file-size limits.
- Stripping metadata does not make copied content original and generally does not improve algorithm distribution. Content/visual/audio matching matters more than metadata.

## Stand-Up Montage

The dedicated handoff is `C:\Users\TUF\Documents\New project\STANDUP_MONTAGE_MASTER_HANDOFF.md`. Read it whenever the user says `STANDUP` or requests the comedy montage.

Core stand-up priorities:

- The first 10 seconds need dense, deliberate sound design and an immediate performer/venue hook.
- Alternate comedian, audience, venue, applause, laughter, and community moments with clear emotional/comedic structure.
- Captions distinguish speakers, remain readable, and stay inside safe bounds.
- Preserve authentic dialogue/laughter/applause while using music and SFX to support rather than bury the show.
- Existing footage catalogs and semantic indexes should be used for discovery, followed by visual verification.

## Known Project Facts And Code Words

- `TFX`: load this master and begin the general AE/TonyFX workflow.
- `STANDUP`: load this master plus the stand-up handoff.
- `Topaz project`: local TonyFX enhancement/upscale plus offline background-audio remover/cleanup work.
- `ai generation`: TonyFX local generation work.
- `ANIYA PROJECT`: resume the identified Aniya edit repair/revision project after inspecting AE.
- `Aniyalator`: TonyFX reference shot color-match project.
- `Odyssey`: resume the Odyssey reference-style edit context after inspecting AE.
- `sienna`: resume the protected-intro Spider-Man/Sienna workflow after inspecting AE.

Recent Demon Slayer replica record:

- Project: `C:\Users\TUF\Documents\New project\DEMON_SLAYER_AQURR_EXACT_REPLICA_V2.aep`.
- Composition: `DEMON SLAYER - AQURR EXACT REPLICA V2`.
- Reference: `C:\Users\TUF\Downloads\ssstik.io_@aqurr_1787100041331.mp4`.
- Format: 1920x1080 at 60 fps.
- Protected intro remains intact; edit begins at frame 602 / `00:10:02`.
- Audit: `C:\Users\TUF\Documents\New project\DEMON_SLAYER_V2_STRICT_AUDIT.json`.
- Recent repair script: `C:\Users\TUF\Documents\New project\ae_refine_demonslayer_v2_motion_replays_and_replica.jsx`.
- Critical lesson: motion-rich forward/reverse replay shots, one BlurMoCurves zoom per scene, Motion Tile edge coverage, rich but controlled color, and no duplicate zoom stacks.

## Failure Patterns That Must Be Rejected

- Reversed, sluggish, hump/dip, sine, or non-monotonic BlurMoCurves graphs.
- Three zoom keys where the scene needs only two, or multiple BlurMoCurves/Scale zoom systems on one shot.
- Four-key Twixtor ramps.
- Zoom keys that stop before the last visible frame.
- Long clips receiving a malformed graph or two-stage zoom.
- Adjustment layers under footage, tiny accidental bars, or layers spanning unrelated scenes.
- Multiple camera angles inside one beat layer.
- Base footage overlaps, timeline gaps, black precomp tails, or 20+ simultaneous footage layers from stretched out-points.
- Repeating the same scene into itself accidentally.
- Choosing the correct footage layer but ignoring the vision-matched source time inside that layer.
- Filling a measured first highlight or climax with calm, scenic, low-motion, or narratively unrelated footage.
- Showing a character visibly speaking while another character's dialogue plays, or showing mouth movement during silence.
- Plain sequencing when the reference contains visible whip, reverse, replay, mask, flash, blur, opacity, or color language.
- Generic blur substituted for an unknown effect.
- Source audio leaking beneath the song.
- Bars, duplicated background filler, cropped subjects, embedded subtitles, or off-screen faces.
- TonyFX features declared fixed after CSS/syntax tests without a real panel-to-AE test.
- Repeatedly resubmitting one bridge command, waiting on an old result, or opening multiple bridge hosts.
- Polishing UI while host behavior remains broken.
- Overwriting unrelated user work.

## Communication And Work Style

- Be direct, concise, accountable, and proactive.
- Start when instructed. Do not repeatedly ask for confirmation when the needed information is locally discoverable.
- Give short progress updates while working.
- Do not loop silently. State the exact blocker once as `HELP TONY: ...`, then continue independent work.
- Never claim completion without stating what was tested and what remains unverified.
- The user values precision over broad promises. Match the requested graph, timing, framing, and effect behavior exactly.

## Completion Checklist

Before declaring AE editing complete:

- Correct comp/project and protected ranges confirmed.
- One continuous shot per scene layer.
- No unintended source audio.
- Cuts/replays/reverses match the requested timing.
- One zoom system per scene; graph sampled and monotonic.
- Twixtor has exactly three keys where used.
- Effects sit above the correct footage and end at neutral.
- Lumetri precedes Motion Tile; Motion Tile covers edges.
- Subjects remain centered at shot thirds and zoom extremes.
- No gaps, base overlaps, black tails, bars, subtitles, or accidental repeated scenes.
- Intro/outro and user changes preserved.
- Visual transition-boundary frames rendered or inspected.
- Project saved with a clear version name.

Before declaring TonyFX development complete:

- Source syntax and structure checks pass.
- Relevant focused regression tests pass.
- Panel interaction and payload path are tested.
- Host function executes in AE when the change affects AE.
- Visible output is inspected.
- Source and installed extension hashes match.
- TonyFX panel is reloaded once to pick up the installed code.

## Final Directive To Future Codex

Use TonyFX as the single bridge host, inspect before acting, preserve the user's work, and reproduce measured editing behavior rather than generic approximations. The approved graph and layer-organization rules are non-negotiable. When uncertainty remains, gather evidence from the project/reference instead of guessing or repeating commands.

## 2026-09-06 — User-authored object-match flow and detailed outline correction

New live-project learning reference: `C:\Users\TUF\Documents\New project\honorable_infinity_full_20260906\USER_FLOW_AND_OUTLINE_LESSONS_20260906.md`. Read it before continuing the Honorable full AMV or reusing this specific effect. Its companion `analysis\USER_AUTHORED_FLOW_GOLDEN.json` records all 13 protected user adjustment layers with exact keys/eases; the complete live snapshot and per-frame samples are beside it.

The user demonstrated a motivated match transition: wide Zenitsu gripping sword → sword close-up. A scene-specific S_BlurMoCurves target/rotation holds readability, accelerates late, then a short BCC directional smear carries motion over the cut and settles into the matching detail. Select the connected shots first; adapt geometry and beat timing, not blindly paste a generic centered zoom or the same numerical target. The live sword endpoint is at the exclusive layer out-point, so compare actual last-visible samples rather than assuming the endpoint itself is rendered. Preserve the user's graph and range choices even when older generic checklist defaults differ.

The requested outline is an expanding/fading **detailed RGB edge copy** (face and clothing included), NOT a binary-matte silhouette stroke. Earlier successful 2026-09-03 performer scripts duplicate actual footage, apply S_EdgeDetect Mono/saturation 0 → S_Glow → single-accent 4ColorGradient/Soft Light, composite Screen, and animate opacity 0→100→0 with duplicate scale up to 150%. Only the duplicate expands. A matte may isolate the RGB subject but must not replace the RGB input to edge detection. Exact old settings and evidence paths are in the new reference. Two current Honorable Zenitsu layers use the wrong silhouette input and remain to be repaired; do not claim they already match the learned tutorial.

This was a read-only AE inspection. It preserved the current project; no full render or effect replacement was performed. Current task state and an earlier ground-caption timing bug are documented in the full task's `CURRENT_STATE.md`. Do not rebuild from old scripts over the user's adjustments.

### Later on2026-09-06 — finishing pass completed

After the user authorized continuation, the two Honorable outlines were corrected to actual RGB character detail through tracked coverage, with S_EdgeDetect/S_Glow/4ColorGradient, Screen, eased100→150 expansion and fade. All13 user adjustment layers were preserved exactly. The ground-caption timing bug was fixed. A new user screenshot clarified that "center" means **higher behind Akaza's torso**, not his feet: primary floor text Position [960,648,0], X rotation50°, Z rotation0°. Text remains native/editable with linked support layers.

Finished full review: `C:\Users\TUF\Documents\New project\honorable_infinity_full_20260906\reviews\HONORABLE_INFINITY_CASTLE_FULL_REVIEW_1080P_FINAL.mp4`.48.4s,1920×1080,30fps. Full decode/coverage/text-expression/protected-layer checks passed; visual contacts inspected. Raw AE AAC had1024sample/21.333ms delay; FINAL preserves video bit-for-bit and packages correctly timestamped AAC from FULL_MIX. Final lag0samples. See that task's `FINISH_REVIEW_NOTES.md`, `CURRENT_STATE.md`, and `analysis\full_review_qa_FINAL\FINAL_QA_REPORT.json`. On resumption, reinspect live state and do not overwrite any new user adjustments.
