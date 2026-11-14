# Joey Quinn "Res 2" — Tony's finished edit vs Neural r2 (12 November 2026)

Tony rejected Neural's r2 build (choppy intro, overlapping/misplaced scenes, glitchy, bad text), fixed it himself in the same composition and uploaded it. His version is the **correct way**. Use it as the reusable template for comparable live-action character edits. A new brief still needs new footage, song and caption decisions; reuse the structure, layer stack, graphs and timings below, retuned to the new material.

Exact per-shot, per-key data: `quinn-res2-accepted-20261112.json` (same folder).
Evidence (project snapshot, both extracts, full diff, parser tools): `data/reference-edits/quinn-res2-accepted-20261112/`.
Final upload: `C:\Users\TUF\Desktop\Dexter res 2 joey quinn edit hq tryxtazfx.mp4` — 2160x2160, 23.976 fps, 999 frames (41.67 s).
Composition: `Joey Quinn Door Intro 30s + Curated Body - Neural2 r2`. Measured offline from a copied .aep; After Effects was not touched. Technical measurement only; no playback/listening review was made by the measuring agent.

## What Neural got wrong (do not repeat)

1. **Intro too long.** 718 frames with three opening caption lines that added nothing. Tony deleted the first 151 frames (C01–C03 and their footage). Intro = 567 f, body starts at 567.
2. **Sliding reframes.** Neural used one long layer per intro source with keyframed Position to chase the speaker. It reads as drifting, wrong positions and overlaps. Tony **split the source at each framing change** and gave each piece a **static Position** (e.g. 739.5 → 248.5 → 654.5 → 284.5 x, scale 135%, last piece 120% with Motion Tile). Cut and reframe; never slide.
3. **No cut transitions in the body.** 29 hard cuts looked choppy. Tony added a directional-blur hit on 27 of 28 cuts.
4. **Zoom centre and crops not aimed at the subject.** Neural left BlurMoCurves Center XY at one default (0.5, 0.2148) on every shot. Tony re-centred shots 1–3 and repositioned the footage on 12 of 29 shots so the face/subject sits where the zoom lands.
5. **Harsh captions.** Every caption revealed in 9.6 f with a ~4 f glow flash. Tony slowed reveals to 18–41 f on five of seven captions, stretched the glow decay to ~27 f, added Echo and overlapped neighbours 6–9 f.
6. **Ungraded intro.** Tony added Sharpen, Unsharp Mask, Exposure, CS Vignette, Brightness & Contrast (Curves / Hue-Saturation on some pieces).
7. **Music level.** Tony's bed: −22 dB under dialogue → −12 dB four frames before the body → 0 dB at the body start, rising over the last 36 f of the intro.

## What Tony kept from Neural (this part was right)

All 29 body shot choices, order and source ranges; 14/15-frame beat cuts on one continuous song section; the BlurMoCurves Z Dist curves and eases; caption wording, font, position and censorship (SH*T, F**KING) for C04–C10; the 4-frame flash adjustment at the body start.

## Body shot stack (top to bottom, per shot)

1. `Blur transition N` — adjustment layer, **BCC Directional Blur**, 8 frames centred on the cut.
2. Unnamed shot-bounded adjustment — **S_BlurMoCurves**: keyframed Z Dist is the zoom. Wrap X/Y = 3.
3. Footage layer from the clips comp — Motion Tile (mirror edges) for coverage; layer Scale constant (~102%); Position only picks the crop.

## Zoom = BlurMoCurves Z Dist, never Scale keyframes

Two keys per shot, first frame to last frame of the shot (14 or 15 f), alternating:

| Shot | Z Dist | Key 1 out (speed / influence) | Key 2 in (speed / influence) |
|---|---|---|---|
| odd (A) | 1.0 → 0.52 | −2.4545 / 21.92% | −2.024 / 26.77% |
| even (B) | 0.52 → 1.0 | 1.5696 / 31.25% | 1.9687 / 27.84% |
| shot 6 | 0.52 → 1.11 | 1.7137 / 31.29% | as B |
| final shot 29 | 1.0 → 0.7 over 25 f | −0.5 / 50% | −0.5 / 50% (slow settle) |

Speeds are Z-Dist units per second. When the range or duration changes, scale speed by (new range / reference range) ÷ (new duration / reference duration) and keep the influences. Aim Center XY at the subject (0–1 of the frame): Tony's shot 1 = 0.7901, 0.2997; shot 2 = 0.5401, 0.2738; shot 3 = 0.2901, 0.1912.

## Cut transition = 8-frame directional blur

Own adjustment layer above the zoom adjustment, from 4 f before the cut to 4 f after. Angle 140, Spread 38, Point 1 0.5, 0.5, Point 2 0.95, 0.95. Blur Amount:

| Frame vs cut | Value | In (speed / influence) | Out (speed / influence) |
|---|---|---|---|
| −4 | 0 | — | 1183.55 / 5.99% |
| 0 (the cut) | 44 | 1591.92 / 6.78% | −599.86 / 19.8% |
| +4 | 0 | −909.13 / 11.24% | — |

Sharp attack into the cut, softer release. One per cut; Tony left one cut (frame 842) clean.

## Intro

Authentic dialogue, song quiet underneath. Split at framing changes, static position per piece, grade stack above. Captions sit at 540, 720 (centre-low) on a 1080 square master.

## Captions

Font SitkaSmall, native editable text, per-character animator **Scale 112% + Blur 10** with range Start 0 → 100. Reveal 18–41 f for normal lines; 9.6 f only for short punch lines ("GET OVER HERE.", "YEAH."). Glow threshold 39.2, radius 13, intensity 0.95 → 0.55 over ~27 f. Echo (time 0.4667 s, decay 0.45) on emphasis lines. Drop Shadow 130 / 180 / 18. Opacity in 1 f, out 5 f eased. Let the outgoing caption overlap the incoming one by 6–9 f. Tony's timings (frames): C04 77–129, C05 194–252, C06 243–298, C07 289–324, C08 404–449, C09 446–502, C10 523–555.

## How to reuse for a new edit

1. Plan: dialogue intro (trim dead lines) → one continuous song section → body cut on mapped beats.
2. Build each body shot with the three-layer stack; choose curve A/B alternately; aim centre and crop at the subject on every shot.
3. Add the 8 f directional-blur transition on each cut.
4. Captions with the slower reveal, long glow decay and overlaps.
5. Check crops at zoom extremes; full-speed human review is still required. Tony's acceptance covers his own upload only.
