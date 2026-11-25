---
name: tfx-antigravity-visual-review
description: Visual pixel-by-pixel inspection protocol for Neural Studio 2 stations (Director, Plan, Review, Edit) using native read_file on contact sheets, 8-frame source strips, screenshots, and rendered video proofs.
---

# Antigravity Visual Review & Source Gate Protocol

Use this protocol whenever reviewing candidate footage, contact sheets, 8-frame strips, AE screenshots, or rendered prototypes/masters inside Neural Studio 2.

## 1. Real Pixel Inspection Rule (Never Guess From Paths)
- **Use native `read_file` on actual `.png`, `.jpg`, or `.mp4` paths** inside the admitted visual roots (`projectRoot`, `data/local-ops`, `data/desktop-observations`, and `artifactRoots`).
- Do **NOT** rely on `mcp_neural_read_artifact` for image pixels when running as a Gemini station—use `mcp_neural_read_artifact` for JSON/text logs/ledgers, and use `read_file` to inspect actual visual pixels.
- Never claim to have inspected frames you did not open with `read_file`. Normal-speed audio playback/listening remains separate unless an actual listening/playback check was performed.

## 2. Pre-Build 8-Frame Source Gate (Plan & Director)
Before approving any intro cutaway or music-body shot into a blueprint or AE build, inspect dense 8-frame strips of every candidate window and reject any clip with:
- **Unsynchronized moving mouths** on cutaways or music-body shots (closed-mouth action/reaction only unless exact `0.00 f` spoken sync).
- **TV HUD bugs / overlays** (`LIVE`, channel logos, watermarks, subtitles burned into source).
- **Wrong-character dominance** or background extras stealing focus from the intended subject.
- **Stray flash cuts / source-cut crossings** inside the chosen window.
- **Accidental repeated source windows**, A-B-A looping, or chronological regressions.

## 3. Framing & TikTok Safe-Zone Audit (Prototype & Final Review)
Check start, middle, and end frames of every shot in the rendered contact sheets/strips:
- **Centering & Safe Margins:** For `1080x1080` square or vertical social edits, verify the subject's eyes/face stay balanced near dead-center (`[540, 540]` safe corridor), clear of right/bottom TikTok UI overlays.
- **Edge & Crop Integrity:** Reject black borders, Motion Tile edge glitches, over-zoomed clipped heads/chins, or unmotivated jump crops.

## 4. Typography & Occlusion Audit
Inspect every caption/hero-word frame:
- Exact spelling, censorship consistency (including mid-reveal frames), and readable contrast (`2.5 px` dark `TXT_*_CORE` stroke + separate `BLOOM`, `CORE` stacked above `BLOOM`).
- Clean line separation, no overlapping caption pairs, no character face/eyeline occlusion, and a readable solid hold (`>= 4.5 f`) before exit sweeps.

## 5. Motion, Transitions & Compliance Audit
- Transition blur (`Exposure` + `BCC Lens Blur OBS` / directional blur) must be confined to cut boundaries, never smeared across static holds.
- Retimed shots (Twixtor / optical flow) must have zero warped faces, melted hands, or frozen frames.
- Graphic/gore frames (bloody bodies, throat cuts, etc.) must stay `<= 4 frames`.

## 6. Evidence-Backed Output
For `prototype_review`, `harsh_review`, and `goldfish_review`:
- Cite the exact `.png` / `.jpg` / `.mp4` paths you inspected with `read_file` inside `production.criteria.<criterion>.evidence`.
- If a defect is found, return `outcome: "repair"` with exact shot/frame/timecode coordinates and concrete fix instructions so `Edit` repairs only failed regions.
