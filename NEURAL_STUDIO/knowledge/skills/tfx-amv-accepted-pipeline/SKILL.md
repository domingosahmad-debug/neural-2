---
name: tfx-amv-accepted-pipeline
description: Tony-approved end-to-end method for a cinematic anime AMV (accepted 2026-10-28 on BLEACH | WE ON GO W10H, "the most perfect one yet"). Use when planning, building, repairing or QA-ing a story-driven AMV in After Effects - song arrangement and seamless returns, clean cuts, zoom-flow transitions, impact hero typography, iris-only eye glows, SAM2 depth cut-outs, original action audio, mix clip control and honest delivery gates.
---

# Accepted AMV pipeline (WE ON GO / Honorable)

Case record with exact files and parameters: [references/WE_ON_GO_CASE.md](references/WE_ON_GO_CASE.md).
For the final accepted W9/W10 implementation, failure-to-fix lessons, branding and script/evidence map, read [references/FINAL_METHODS_AND_REUSE.md](references/FINAL_METHODS_AND_REUSE.md). This distinguishes final methods from the earlier prototypes below. Parameters and story order are case examples, not defaults for every anime.
Scripts in `scripts/` are proven reference implementations from that edit (paths inside are project-specific: adapt, do not run blind).
Execute AE writes only through tfx-tonyfx-execution (one writer, guarded NEW AEP per revision, recovery save of dirty live state first).

## 1. Story, source and voices
- Story arc Tony accepted: setup -> threat -> response (real Bankai cry) -> real technique (EP05 Getsuga with its own shouted call) -> "hero dies" -> illusion reveal (Kyoka Suigetsu) + explanation -> song returns to the hook on the big technique (Hado #99, full setup/release/impact/aftermath) -> final technique -> payoff -> cut to black on the music's stop. The human may reorder chronology; his order wins.
- Find techniques by shot sheets AND Demucs vocals + whisper with word timestamps. Whisper mishears shouted calls ("…つが 転生" = Getsuga Tensho, "挽回" = 卍解); confirm with frames. Verify the speaker on screen (Kenpachi/Ichigo confusion must never recur). Never truncate a sentence; drop a fragment instead and say so.
- Captions start at the measured speech onset (stem RMS 50 ms), never earlier; an unheard word never appears in a caption.

## 2. Cuts and pacing
- No foreign split-second shots anywhere: snap every shot window to real source cuts (hist-diff detector) and require >= 12 frames per visible segment. Run `scripts/short_shot_audit.py` on EVERY full render and look at each flagged segment: foreign fragment = defect; same-shot strobe = source animation (disclose).
- Sample-frame QA must cover every second of the opening and every changed join; a collapsed layer once blacked out 0-8 s while sampled frames passed.
- AE quirk: writing inPoint can move outPoint. Always set out, then in, then re-check both (a layer with out < in is invisible).

## 3. Transitions and camera (Tony's zoom-flow)
- Zoom-flow pair across a cut ONLY where the same subject carries from wide to close: outgoing S_BlurMoCurves Z Dist 1 -> 0.16, ease out-influence ~8 %, in-influence ~10 % (accelerates into the cut); incoming 0.16 -> 1 with out-influence 0.4 % / high speed and in-influence ~57 % (explodes out, long settle); centres on the subject in each shot; BCC Directional Blur spike (10 -> 56 -> 10, angle 65) on the cut frame. Reuse Tony's own layers by duplicate + stretch + re-centre so the graph shape is preserved.
- Measured reference study (`scripts/ref_transitions.py`, 1,046 cuts) shows the same accelerate-in / explode-out profile. Action exchanges use whips/punches on beats. No zoom without motivation; audit for duplicate zoom owners and micro-kicks.
- Motivated narrative transitions (e.g. Kyoka "illusion breaks": turbulent displace peak on the cut + short exposure flash + shimmer whoosh).

## 4. Hero typography
- Brave Gates (PostScript `BraveGatesPersonalUseOnly-Reg`, has macrons; personal-use licence - disclose) for technique/hero words; Montserrat-Bold 58 px captions.
- Impact system (`scripts/BUILD_TYPE_PROOF.jsx`): per-character slam (scale 380 %, blur 30, rotation -18 -> 0 via index selector), layer overshoot <= 1.12 (wide words must stay inside the frame through the whole envelope), decaying wiggle shake, S_DistortRGB `Amount` keyed 0 -> 0.5 -> 0 (default Amount is 1 = permanent distortion!), S_Glow fire colour, Turbulent Displace energy edges, CC Light Sweep.
- Keep faces and eyes clear through reveals, overshoot, holds and exits (place in negative space or behind a matte).

## 5. Eyes, mattes, depth
- Eye glow = IRIS/pupil core only, tracked for the whole shot, sclera/lids/blinks intact, small core + controlled halo. Scene-specific exceptions (Tony kept the g1 Getsuga close-up whole-eye glow) never generalise.
- SAM2.1-small via `scripts/sam2_video_src.py`; resolve its actual environment/model paths from the case, not a new project's relative tools/sam2env. Prompts: positive on iris centre, negatives on sclera/lids/skin. Inspect the matte outline on frames, not coverage numbers. Tiny irises (~10 px): test an enlarged crop; if SAM2 returns the whole eye opening, use verified source-space tracking and iris shapes. Final accepted W9/W10 glows duplicate actual footage, track iris-ring masks with subtractive pupil exclusions, and add controlled exposure/halo while retaining source texture. Earlier opaque glowing solids in FIX_W7E/FIX_W8B are historical prototypes, not the accepted general eye recipe. See final-method reference before implementation.
- Depth cut-out: duplicate footage + luma track matte from SAM2 masks (matte copies footage scale keys), background adjustment (Exposure/saturation down), smoke between. Never use glow to hide matte edges: a warm edge glow turned Aizen's hair red over the EP08 grade - diagnose with `scripts/DIAG_DEPTH_FRAMES.jsx` (saveFrameToPng per toggled state).

## 6. Music, sound and mix
- Song return: `scripts/song_return.py` loop search (beat-synchronous chroma+MFCC) for a phrase-end jump with pickup; the jump must not land on a scene cut. The client's manual music repair is the authority: probe it (`scripts/PROBE_TONY_MUSICFIX.jsx`), preserve layers/offsets byte-for-byte, change levels only.
- Original action audio: isolate source action sound aligned to shot offsets (`scripts/SOL_W9_*`); vocals-only stems are not action audio and dialogue-free shots are not "silent". Stock SFX only where motivated; mute superseded stock hits.
- Big-impact samples with long pre-swells must not cover a shout. Duck music under every voice window including after the drop.
- Clipping: reproduce the window offline with `scripts/mix_window_sum.py` and pick the smallest balanced trim (a +8 dB client slice and 0 dB sub-bass stacked to 2.18). Gate: decoded peak <= 0.98, 0 clipped samples, true peak <= -1 dBTP on delivery.
- Deliver a genuine native 32-bit float master (AE audio-only AIFF 32-bit render) and remux; never upcast 16-bit (`scripts/SOL_W10H_PACKAGE_FLOAT_DELIVERY.py`).

## 7. Honesty and gates
- In this case the agent demonstrated technical and sampled-picture checks, not actual hearing/full-speed perception. Future agents must check their real tools rather than assume either ability or permanent inability. Keep those gates separate; never fake a PASS. Tony's recorded approval of W10H is the accepted artistic reference; the app's human gate still requires Tony's own acceptance action. No agent should rewrite that UI gate to fabricate a click.
