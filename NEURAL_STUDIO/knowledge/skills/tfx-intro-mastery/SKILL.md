---
name: tfx-intro-mastery
description: Standard operating workflow for cutting and finishing AAA narrative and dialogue intros for TFX edits (Dexter, Fight Club, etc.) using reference modeling, multi-agent critique (EGM), native audio retention, and approved Sitka-Small typography.
---

# TFX Intro Mastery Workflow

This skill codifies the verified AAA intro creation and finishing pipeline for After Effects edits in the TFX studio workspace, established and approved on the Dexter S02E02 *Pure Snow* production.

## 1. Scene Scouting & Selection Principles

1. **Protagonist Aura & Solitary Focus**:
   - The intro must highlight the protagonist in full control (e.g. solitary predator, Dark Passenger, lethal demeanor).
   - **Zero secondary distraction**: Eliminate random background people, unrelated dialogue, and blank cutaways (e.g. cars or street transitions).
   - **No Clip Reuse**: Never repeat an intro scene or dialogue clip previously used in an earlier project.
2. **Monologue & Dialogue Cadence**:
   - Choose dialogue with iconic, high-impact phrasing (e.g., *"My way. My rules. Just to remind me that I'm still me."*).
   - The scene must lead into an intense close-up or direct gaze right into the lens at the final fraction of a second before the beat drop.
3. **Exact Drop Handoff**:
   - The intro must end precisely on the beat drop frame (e.g. Frame 360 / `15.015s` for a 15-second intro).
   - Downstream body edits and master music tracks snap seamlessly to this exact timecode.

---

## 2. Audio Architecture

1. **Native Dialogue on Video Layer**:
   - **Never detach or remove audio from the main video layer**: Keep `audioEnabled = true` on the master footage layer.
   - Apply a clean **+3.0dB to +3.5dB dialogue boost** on the video layer (`ADBE Audio Levels = [3.5, 3.5]`) so voiceover cuts cleanly and legibly.
2. **Background Music Bed**:
   - Keep the song playing in the background at low/ducked volume during the dialogue or pre-drop phase, snapping to full volume (`0dB` to `-2dB`) at the drop cut.
   - Preserve any user-adjusted volume fades or stems.

---

## 3. Approved Typography Specification (Sitka Standard)

Adopted from TUF's approved character and effects specifications:

| Parameter | Setting | ExtendScript / AE Value |
| :--- | :--- | :--- |
| **Font Family** | `Cinzel` / `Sitka-Small` | `doc.font = "Cinzel";` (All-caps classical Roman editorial serif) |
| **Font Size** | `44 px – 45 px` | `doc.fontSize = 44;` |
| **Leading** | `78.2 px` | `doc.leading = 78.2` |
| **Tracking** | `18` | `doc.tracking = 18` |
| **Stroke Color** | Solid Black | `doc.applyStroke = true; doc.strokeColor = [0.0, 0.0, 0.0];` |
| **Stroke Width** | `1 px` | `doc.strokeWidth = 1.0` |
| **Stroke Order** | Stroke Over Fill | `doc.strokeOverFill = true;` |
| **Justification** | Center Justify | `doc.justification = ParagraphJustification.CENTER_JUSTIFY;` |
| **Blending Mode** | **NORMAL** | `layer.blendingMode = BlendingMode.NORMAL;` (Never use Overlay!) |
| **Two-Line Stagger** | Alternating Dual Tracks | Track 1 (Top) `Y = 718 px`, Track 2 (Bottom) `Y = 768 px` |

### Speaker Color Separation
- **Primary Speaker (Protagonist)**: Crisp solid white `[1.0, 1.0, 1.0]`.
- **Secondary Characters / Interlocutors** (e.g. precinct officer, Detective Wallace replying `"YES?"` / `"YES."`): **Vibrant Yellow** `[1.0, 0.88, 0.35]` (`#FFE059`). Placed on Track 2 underneath to establish clear conversational spatial hierarchy.
- **Hero Names & Major Peaks** (e.g. `I'M JOEY QUINN.`, `ANGEL BATISTA.`): Approved Dexter Gold `[1.0, 0.88, 0.44]`.
- **Location Identifiers** (e.g. `AT MIAMI METRO,`): Miami Cyan `[0.35, 0.88, 1.0]`.

---

## 4. Dual-Layer Deep Glow Architecture
To achieve the luminous, atmospheric film bloom of AAA references:
1. **Drop Shadow (`ADBE Drop Shadow`)**:
   - Shadow Color: Black `[0, 0, 0]`
   - Opacity: `60%` (`153.0 / 255`)
   - Direction: `180.0°`
   - Distance: `4.0`
   - Softness: `16.0`
2. **Core Crisp Glow (`ADBE Glo2 - REF Core Glow`)**:
   - Color Channels, Threshold `28.0%`, Radius `10.0`, Intensity `0.55`, Behind, Add, Original Colors.
   - Initial entrance punch: keyframe Intensity `0.95 -> 0.55` over 4 frames for a subtle flash reveal.
3. **Deep Atmospheric Bloom (`ADBE Glo2 - REF Deep Bloom`)**:
   - Color Channels, Threshold `18.0%`, Radius `48.0` (wide, dreamy halo), Intensity `0.40`, Behind, Add, Original Colors.

---

## 5. Letter-by-Letter Cinematic Flash Reveal Animator
Built using native After Effects vector text animators:
- **Animator Properties**:
  - `ADBE Text Opacity`: `0%`
  - `ADBE Text Blur`: `[10, 10]`
  - `ADBE Text Scale 3D`: `[112, 112]`
- **Range Selector**:
  - `ADBE Text Percent Start`: keyframed `0.0% -> 100.0%` across the spoken dialogue window.
  - Shape: `Ramp Up` (`2`) with `Ease High / Low: 75%`.
- As `Start` advances, each letter smoothly dissolves in from a soft blur and gentle scale overshoot into crisp white/gold focus, emitting a momentary burst of glow.
3. **Preserve User Timing Adjustments**:
   - When modifying text styles or effects, **never overwrite keyframe timestamps, layer inPoints, or outPoints** that the user has manually retimed.
   - Update values at existing keyframe indices via `tp.setValueAtKey(k, doc)`.

---

## 6. EGM & Multi-Agent Quality Gate

Before declaring an intro complete, run the automated verification suite:
1. **Margin Audit**: Measure bounding boxes of rendered frames to ensure bounds are strictly within `[54, 1026]`.
2. **Occlusion Check**: Ensure `Y_min >= 600` so character eyes are never covered.
3. **Audio Sanity Check**: Confirm `vidLayer.audioEnabled == true` and dialogue levels are audibly clear.
4. **Visual Contact Sheet**: Produce dense sRGB contact sheet of all cards for human sign-off.

---

## Dexter Moshcore Dual-Layer Crimson & Twixtor 3-Key Standard (2026-11-13)

Accepted reference standard extracted from `NEURAL_MASTER` for 1080x1080@23.976fps Dexter Moshcore edits (`0..15.015s` intro + `15.015..23.523s` body):

1. **Audio & Demucs Isolation (`AUD_Music` + `AUD_Dialogue` + `AUD_SFX_*`)**:
   - Extract intro segment WAV at 48kHz stereo and isolate dialogue with `demucs --two-stems=vocals` (`vocals.wav`) before aligning captions with `faster-whisper-large-v3` word timestamps.
   - `AUD_Music` volume envelope: `-22.0 dB` across dialogue (`0.000..13.514s`), ramp `-22.0 -> -12.0 dB` (`13.514..14.806s`), snap `-12.0 -> -2.5 dB` into drop (`14.848..14.973s`), tail `-2.5 -> -18.0 dB` (`23.065..23.482s`).
   - Mute (`audioEnabled = false`) all video layers, precomps, solids, and flashbacks except `AUD_Music`, `AUD_Dialogue`, and `AUD_SFX_*`.

2. **1-Second 3-Cut B&W Hook (`0.000..1.001s`)**:
   - Three rapid B&W solo Dexter cuts (~`8f` each: `0.000..0.334s`, `0.334..0.667s`, `0.667..1.001s`), middle cut optionally 50% inverted for flicker contrast.
   - Stack on each hook shot: `Motion Tile (250x250, Mirror Edges=1)` + `Black & White` + `Exposure (+0.35)` + `Brightness & Contrast (0, +24)` + `Unsharp Mask (75, 1.0, 0)`.
   - Top each cut with an ADD white optical flash (`Opacity 82..90% -> 0%` over 3-4 frames) and `AUD_SFX_*` (`Digital Camera Operation Sound Effect`, `stretch = 80.0%`).

3. **Intro Story Cuts, B&W Solo Flashbacks & Dual-Layer Typography (`1.001..15.015s`)**:
   - Use strictly episode/project-authentic dialogue clips where the speaker's mouth matches or off-screen reaction/cutaway is motivated; never stack competing speakers.
   - Insert rapid B&W solo flashbacks (stack identically to Hook, `ADD` white flash `85% -> 0%` at head) strictly **underneath** hero text and bloom layers (`FB` layers below `HERO_TEXT` + `_BLOOM`).
   - Typography architecture: `Montserrat-Black` (`48px` uppercase, `leading = 53`, white `#FFFFFF` with dark drop shadow) paired 1:1 with `_BLOOM` duplicate (`ADD`, `Fast Box Blur = 6`, `Opacity = 55%`). Climax/hero lines use `SocialGothic-Rough` / bold crimson (`#EB2A2A`) at `76px` (`leading = 80`) with crimson bloom (`56..60%`), censor asterisks where appropriate (e.g., `S*RIAL K*LLER.`), and Text Animator word/letter Hold keyframes timed to Whisper word onsets.
   - Apply `ADJ_Grade_Intro` (`1.001..15.015s`: `B&C -5/18`, `Tint 16% cool`, `Unsharp 40/1.2`, `Vignette 24/45`) and bridge the `15.015s` drop with `[TFX_FLASH_STROBE_4]` (`15.015..15.182s`, `ADD`, `Opacity 100 -> 0`).

4. **Body Cut Montage, Motion Tile Bounds, Twixtor 3-Key U-Curve & S_BlurMoCurves (`15.015..23.523s`)**:
   - Solo protagonist action/movement shots only (no bystanders, no unsynced moving mouths, zero clip reuse). Frame subject eyes around `y ≈ 300..440` with **zero vertical Motion Tile mirroring** (`top edge <= 0` and `bottom edge >= 1080`: `pos.y <= H*scale/200` and `pos.y >= 1080 - H*scale/200`).
   - Inside each `PC_body_XX` precomp: `[Motion Tile (250x250, Mirror Edges=1)] -> [Twixtor Pro (Twixtor 45)]`.
   - **MANDATORY TWIXTOR 3-KEYFRAME GRAPH (`Speed %`)**: Strictly **3 keyframes (`150.0% -> 35.0% -> 150.0%`)**, NEVER 4 keys and NEVER stopping 1 frame short.
     - `Key 1` at `t = 0.000s`: `150.0%` (Outgoing steep drop into midpoint).
     - `Key 2` at midpoint (`~50-53%` of layer duration): `35.0%` (Easy-Ease low-speed hold across center).
     - `Key 3` at exact clip end (`t = layer.outPoint`): `150.0%` (Incoming whip ramp back to full speed).
   - Above each body precomp, apply `ADJ_Z_body_XX` (`S_BlurMoCurves`, strictly **2 keyframes** `1.00 <-> 0.52` Easy-Ease speed ramp, `Wrap = 3`, `Center XY` locked directly to Dexter's eyes) and `ADJ_BlurCut_1..13` cut blurs + `ADJ_Grade_Body` (`B&C -4/24`, `Tint 24% cool`, `Unsharp 55/1.1`, `Vignette 26/45`).
