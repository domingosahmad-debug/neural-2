# TFX Workflow Upgrades Synced from Antigravity Studio (15–24 Nov 2026)

Synced into Neural Studio 2 on 25 Nov 2026 from `C:\Users\TUF\Documents\TFX_ANTIGRAVITY_STUDIO\GEMINI.md` and `.agents/skills/`.

## 1. Pure Snow V1 & V2 User-Refined Workflow (15 Nov 2026)
- **No Automated CC / Exposure / Sharpen**: Do NOT add automated color correction, `Exposure`, `Curves`, `CC Vignette`, `Brightness & Contrast`, `Hue/Saturation`, `Sharpen`, or `Unsharp Mask` adjustment layers/stacks to footage unless explicitly requested. TUF adds final color/sharpening manually.
- **Restrained Alternating Zooms (`S_BlurMoCurves`)**: Use the 2-keyframe alternating `Z Dist` Speed Ramp graph (`1.00 <-> 0.78..0.80`, outro resolve `1.00 -> 0.70..0.80`) with proportional non-zero tangents (`outEase` inf `28.69%`, `inEase` inf `31.65%`).
- **Between-Cut Exposure + Lens Blur Transition Layer**: Add a `6f` adjustment layer over body cuts with `Exposure` (`0 -> 5.0 -> 0`) + `BCC Lens Blur OBS` `Iris Scale` (`0 -> 20.0 -> 0`). Standard cuts key `-3f / 0 / +3f`; short clips (<= 8f) compress the short side to `1f`.
- **Pixel-Measured Subject Centering**: Always measure actual face/eye `(x, y)` coordinates in the raw frame and verify `1080x1080` crop balance so `[540, 540]` stays centered on the character/action.
- **Fast Flashback & Shutter Cadence + Brief Gore**: Keep flashback bursts snappy (`4–7f` per shot, shutter click stretched to `60%–80%`), source prequel/canon clips when an episode lacks a referenced past beat, and cap graphic/gore frames at **<= 4 frames** for TikTok compliance.

## 2. Offset R4W (`CHROMATIC_VENOM` & `DARK_SOVEREIGN`) Rules (18 Nov 2026)
- **Audio & Underwater Low-Pass ("Reverb/Muffle") Recipe**:
  - `AUD_Dialogue` (`htdemucs` isolated): `ADBE Audio Levels` at `[+3.0, +3.0] dB` (`inPoint = 0`, `outPoint = dropT`).
  - `AUD_Music`: `[-15.0, -15.0] dB` through `drop_frame - 19`, ramping linearly over 19 frames up to `[0.0, 0.0] dB` at `drop_frame`, holding `[0.0, 0.0] dB` to `total_frames - 16`, then fading to `[-44.0, -44.0] dB` at `total_frames`.
  - Add two stacked `Bass & Treble` (`ADBE Aud BT`) effects on `AUD_Music`, each keyframing `Treble` (`ADBE Aud BT-0002`) from `-100` at `t = 0.000s` to `0` at `dropT`.
- **Resolution-Native Scale & Centering (`precomps = 0`)**: Match resolution-native scale (`100%` on `2592x1080`, `135%` on `1920x800`) so the vertical frame is never over-zoomed/cropped; verify start, middle, and end frames of every shot window (`precomps = 0`, direct full-source linking, zero glitches on quiet intro speaker switches).
- **Reference Typography & Non-Overlap Assertions**: Dual-layer `CORE` (2x Drop Shadow) + `ADD` `BLOOM` (`ADBE Box Blur2` radius `12–14`, iterations `3`) with red climax lines (`[1.0, 0.24, 0.30]`), `WordReveal` + `OutSweep`, and programmatic checks that `word_t[-1] < exit_t0 - 0.12` and `next_pair_t_in >= prev_pair_t_out`.
- **Signature Creative FX (`FX_*` layers)**: Layer `S_WarpChroma` + `S_Shake` (`CHROMATIC_VENOM`) or `S_EdgeRays` + `S_DistortRGB` (`DARK_SOVEREIGN`) on dedicated `FX_*` adjustment layers at hook, intro climax cuts, major body downbeats, and outro dissolve.

## 3. Reality TV & TikTok Center-Safe Fast-Path Workflow (22 Nov 2026)
- **TikTok Dead-Center Subject & Caption Safe Zone**: Pixel-measure face/eye center `(cx, cy)` on every shot (splitting multi-camera angles into separate layers when framing shifts) so characters and captions sit dead-center inside the middle safe zone of `1080x1080`, clear of TikTok UI buttons/captions.
- **Pre-Build 8-Frame Gate Before AE**: Inspect dense 8-frame strips of all candidate intro/body shots BEFORE launching AE builds to confirm `0` moving mouths on cutaways/body shots, `0` TV HUD bugs/`LIVE` labels, `0` non-target cast dominance, `0` stray flash cuts, and `0` source overlaps.
- **Exact `0.00 f` Spoken Sync & Non-Talking Cutaways**: On-camera talking intro clips align to isolated dialogue at `0.00 frames` drift; voiceover cutaways show closed-mouth reaction/action footage only.
- **Caption Hold & Core Stroke Assertions**: `0.08 s` per-word `WordReveal`, `>= 4.5 f` solid hold before `OutSweep`, `2.5 px` dark `TXT_*_CORE` stroke (`BLOOM` stroke-free), stacked `TXT_*_CORE` above `TXT_*_BLOOM` above FX/transitions.
- **Clean Audio & Stem Censorship**: Demucs vocal isolation (`true peak <= -1.5 dBTP`), and suppress song profanity via Demucs vocal/instrumental stem dips (`-36 dB` / `-14 dB`) verified with `faster-whisper`.

## 4. Stand-Up Comedy Promo PSD-to-AE & Headless Render Rule (22 Nov 2026)
- **Modular PSD Layer Exports**: Export every designer PSD element as an individual transparent PNG rather than flattened strips; preserve central footage placeholder precomps and bottom intro video/audio layers untouched.
- **Mandatory Headless `aerender.exe` Proof Rendering**: Never run long `app.project.renderQueue.render()` jobs inside the live interactive After Effects UI (it freezes mouse clicks, timeline scrubbing, and Purge Cache). Save the `.aep` cleanly and render verification MP4s via headless `aerender.exe`.
