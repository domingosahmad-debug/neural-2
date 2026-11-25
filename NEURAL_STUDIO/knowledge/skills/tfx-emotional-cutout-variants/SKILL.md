---
name: tfx-emotional-cutout-variants
description: Build Tony's sad/emotional character TikTok edits in After Effects: a matted hero cutout over many spin-blurred background scenes, story dialogue intros, censored cinematic captions, several distinct versions per song. Worked, accepted example: Mentalist "Jane!" V5A/V5B/V6A/V6B (20 Nov 2026).
---

# Emotional cutout edit variants

Use this skill for a sad or emotional live-action character edit, of the kind people post to TikTok: one character, one song, and one or more versions.

The method was proven on The Mentalist / Patrick Jane, to "Jane! (Hoodtrap) - TheGoodVibe", in four versions (section 9). Every command and technique here was actually used on that edit.

Related skills in this folder:
- `../tfx-tonyfx-execution/`: the AE bridge and the guarded template.
- `../tfx-character-mattes-color/`, `../tfx-cinematic-typography/`, `../tfx-dialogue-music-sound/`, `../tfx-review-repair/`.

Scripts live in `scripts/` next to this file. In the worked example they ran from the session folder `<SESSION>/scripts/` (section 10).

---

## 1. Tony's rules for this style (keep them exactly)

**Look**
- One hero cutout of the character (person matted out, alpha PNG sequence) sits over many background scenes. The scenes are spin-blurred, change every 2–3 frames, and are chosen to fit the version's emotion.
- No black bars (no letterbox).
- Each version has its own main edit: different cutout shots, different hero scenes, different background scenes. Tony: "I can't have all the edits we're doing look like each other." Use at most 1–2 shots from any reference edit. Don't copy the reference's shots.
- Story versions open with dialogue intros: real lines from the show, complete sentences, with room for each line to finish. The song plays quietly underneath and rises into the body.
- Lengths: no-dialogue versions 20–30 s. Dialogue versions 30–60 s (never more than 1 minute).
- Flashbacks must match the words. Example: "my wife Angela" shows the wife (or her room); "my daughter Charlotte" shows the daughter (or the smiley in the room).

**Captions**
- Censor with a stylized internal asterisk: k*lled, s*rial k*ller, m*rder, k*ll. Keep the original transcripts separately. Never alter the audio.
- Accepted caption identity (r5):
  - Lyrics: BarlowCondensed-Medium 80, tracking 120, white, DIFFERENCE blend.
  - Motion: the whole sentence animates as one block. It rises in 12 px with blur 12→0 and scale 94→100, holds readable, then drifts up with blur→10 and scale→102. Eased, with no spin.
  - Underlay: a faint soft black copy (Fill black, Box Blur 9, 42 %) below each caption, for bright frames.
  - Subtitles for dialogue: BarlowCondensed-Regular 52 at y=950, with a soft shadow.
- If Tony asks to keep an older style on one version, keep it. V6B keeps Arial-BoldMT 46 subtitles with a plain fade.

**Glitches Tony rejected (never ship these)**
- 1-frame inserts or flicker. A menace image (the smiley) is a subtle ghost overlay instead: MULTIPLY blend, 34–40 % peak, with 14-frame ramps.
- Background rotation too fast. For a calm or memory version, use the "steady" style: scenes every 4–5 frames, a slow −3°→+3° drift, radial blur 3.
- Choppy intros. Use 8–10-frame crossfades.
- **Source-cut leaks.** A few frames of a foreign shot appear at the start or end of a clip, often inside a crossfade's pre-roll. Before using any range, check it for source cuts (section 7). This was the most common defect.

**Process rules**
- One native AE writer at a time.
- Every JSX goes through the bridge, using the guarded template. Never re-send a command whose result is UNKNOWN. Never delete locks.
- Never close or modify another project. The reset only closes its own AEP, and only if it is clean.
- No paid installs or billing changes. Downloads need Tony's permission. Never `rm` with a variable path.
- Tony renders the finals himself. Hand over the AEPs plus `HANDOFF_FOR_TONY.md`.
- Before any handoff: a harsh frame-by-frame review, then one independent fresh reviewer, then at most one targeted recheck.

---

## 2. Project structure (inside each AEP)

Each version is built from nothing by one generated JSX into an empty, untitled project, which then saves itself as `<SESSION>/<PROJECT>_<V>.aep`.

- **Comp:** `JANE_<V>` (in general `<NAME>_<V>`), 1920×1080, 30 fps, black background, motion blur on (shutter 360, phase −180).
- **Folder:** `<NAME>_<V>_SOURCES` holds the imported episodes, the song, and the cutout and strobe PNG sequences.

Layer stack, from bottom to top:
1. **SONG.** Placed so the song's chosen first beat lands on frame M, where M is the frame the body starts. Volume keys run like this: about −9 dB under dialogue, ramping to 0 dB at the body, then fading out at the end.
2. **Base main edit.** A beat-timed shot plan (`plan/shot_plan.json`), offset by M. Each version replaces slots with its own scenes (`main`). Uses plain footage layers only.
3. **Cutout slots.** The example has two: CUT1 at about 1.2 s (36 frames) and CUT2 at about 1.6 s (49 frames, after a few frames of plain footage). Each slot holds:
   - `BG<n> …` scene layers. Each changes every 2–3 frames (or 4–5 in the steady style) and cycles through 16 emotion-matched scenes. Each scene layer gets:
     - scale ×1.3
     - rotation ±7°→∓2.8° over its life (steady style: a global −3→+3° drift)
     - a scale push ×1.06→1 (steady style: ×1.02)
     - layer motion blur
     - `look()`: −35 % saturation and auto-gamma to target luma T (78 normally, 58 for menace)
   - `SPIN BLUR <n>`: an adjustment layer with Radial Blur, Type Zoom, center 960,540. Amount is keyed 12 on each scene start, then 5 (steady style: a constant 3).
   - `CUT<n>`: the cutout sequence on top.
4. **Extras.** Hooks, the intro montage, dialogue clips (with their audio on, +2/+3 dB, 2-frame ramps), flashbacks (an opacity envelope to about 80–88 %), ghosts and the outro. Options per clip:
   - `xf`/`xo` crossfades (these pull pre-roll and post-roll from the source)
   - `speed`
   - `zoom` (slow push)
   - `look`
   - `T`
   - `blend`
   - `op` (opacity keys)
   - `audio`, `audio_out`
5. **Per-slot grade adjustments** (Hue/Sat + Levels gamma) from `plan/grade_v3.json`.
6. **Version grade:** `REDGRADE` (menace), `TEALGRADE` (guilt), `SOFTGRADE` (grief) or sepia looks (memory). Then a `VIGNETTE` (inverted elliptical mask, feather 420, 80 %) and a `GRADE adj` (Sharpen 18, Contrast 20).
7. **Captions** (song lyrics, from the shot plan), plus `FLASH` / `FADE WHITE` solids on the base edit's beat flashes.
8. **FX:**
   - `GLOW` on the cutout slots
   - `SHAKE` (Transform jitter plus directional blur on beat hits, used for menace)
   - `GRAIN` (Noise)
   - `LEAK` (orange ADD ellipses drifting for 10 frames, used for memory and grief)
9. **Subtitles:** `SUB …` layers.

**Cutout method:**
- Video propagation with SAM2.1 hiera-small, prompted by a person box from YOLO11n (class 0, the largest and most central box), or by a manual `box`.
- Frames are extracted with ffmpeg at 30 fps, 1920×1080, for `nf` frames starting at the source time.
- Output goes to `cutouts/<V>_cut<n>/<V>_cut<n>_0000.png…`, imported as a sequence (conformFrameRate 30, straight alpha).
- Choose a single person, centered, in a close or medium shot with low motion. Hair edges come out rough; this is a known limit.

---

## 3. Picking footage by emotion

1. **Index the sources.** `scripts/index_sources.py` / `scripts/index_s6.py` produce shot contact sheets (`index/*_shots_####.jpg`) and Whisper transcripts (`index/*.transcript.json`). Read the transcripts to find lines and the sheets to find shots.
2. **Rank cutout candidates** with `scripts/find_cut_cands.py` + `scripts/cand_sheet.py`. Inspect every candidate's full range with `scripts/probe_frames.py` / `scripts/tsheet.py`, not just one thumbnail.
3. **Cut dialogue on the speech envelope.** `scripts/env.py <src> t0 t1` prints dB every 0.1 s. End a clip only after the level falls, so the sentence finishes.
4. **Find source cuts** with ffmpeg scene detection. This is what caught every leak:
   ```bash
   ffmpeg -hide_banner -ss T0 -t DUR -i SRC -vf "select='gt(scene,0.25)',showinfo" -an -f null - 2>&1 | grep -o "pts_time:[0-9.]*"
   ```
   Add T0 to each time printed. A clip uses source time `[in - xf/30*speed, in + (len + xo)/30*speed]`, and that whole span must sit between two cuts. If it doesn't fit, slow the clip (speed 0.75) or shorten the fades.
5. **Build one background list per emotion.** Example lists:
   - Memory or love lost: wedding, rings, kiss, the wife smiling, the house at night, the hero at windows.
   - Menace: the villain's symbol, the painted smile, explosions, bodies, police lights, a figure in a hallway.
   - Grief or climax: only the climax location (approach, kill, body, colleagues, running).
   - Guilt: the note, deleted files, interrogation, phone calls, the press conference.

---

## 4. The generator: `scripts/gen_variant_jsx.py`

Run `python scripts/gen_variant_jsx.py <V> <AEP currently open in AE>`. It writes `jsx/<V>_build.jsx` and `jsx/<V>_reset.jsx`, and dumps every version config to `plan/variants.json`.

Building blocks, in Python:

```python
FPS = 30
def C(src, f0, f1, inS, **o): d = {"src": src, "f": [f0, f1], "in": inS}; d.update(o); return d
def seq(specs, start=0):          # place clips back to back; returns (clips, next frame)
    out, f = [], start
    for src, t0, t1, o in specs:
        n = int(round((t1 - t0) * FPS)); out.append(C(src, f, f + n - 1, t0, **o)); f += n
    return out, f
def at(clip, t): return int(round(clip["f"][0] + (t - clip["in"]) * FPS))   # source sec -> comp frame
def subs_for(clip, lines):        # [(t0,t1,text)] in source sec -> comp-frame subtitles clamped to the clip
    f0, inS = clip["f"][0], clip["in"]
    return [[int(round(f0 + (max(t0, inS) - inS) * FPS)), min(int(round(f0 + (t1 - inS) * FPS)) + 2, clip["f"][1]), tx] for t0, t1, tx in lines]
```

Version dict keys:
- `M`, `total`
- `extras` (a list of `C`)
- `main` = `{base slot frame: Mn(src, in, name, speed=…)}`
- `bg` = `{1: [16×Bg(src, in, name)], 2: […]}`
- `drop`, `shift`
- `grade`, `grain`, `glow`, `leaks`, `vignette`, `shake`, `ghost`
- `bgstyle` ("steady" or default), `bgT`
- `capstyle` ("r5"), `subs`, `subst`, `song_vol`
- Cutout sources come from `plan/r5/cutspec.json`: `{V: {"1": {src, in, nf, name}}}`.

The dialogue-intro pattern, with flashbacks timed to the words (from V6A):

```python
(s1, s3, s4, s5, s6, s7), X = seq([
    (E8, 2312.7, 2321.9, dict(audio=3, T=70, name="DLG let me live")),
    (E8, 2335.3, 2340.6, dict(audio=3, T=62, name="DLG blink")),
    (E8, 2341.9, 2349.4, dict(audio=3, T=62, name="DLG are you sorry")),
    (E8, 2356.5, 2360.7, dict(audio=3, T=62, name="DLG good good")),
    (E8, 2362.3, 2364.6, dict(audio=3, T=62, name="DLG afraid to die")),
    (E8, 2367.9, 2371.0, dict(audio=3, T=62, name="DLG good"))])
M = X + 4                                         # song body starts 4 frames after the last line
fbw0, fbw1 = at(s4, 2344.5), at(s4, 2346.4)       # "...my wife, Angela"      -> the room: hallway to the bedroom door (Pilot 1872.4)
fbd0, fbd1 = at(s4, 2347.8), s4["f"][1]           # "...my daughter, Charlotte" -> smiley in the room (Pilot 1877.0)
# each flashback: op=[[f0,0],[f0+7,88],[f1-7,88],[f1,0]], desaturated, T=95
```

JSX helpers the generator emits (reuse them):
- `foot(item,f0,f1,inS,speed,…)`: places source time `inS` at frame `f0`; stretch = 100/speed; audio off.
- `bgL(…,zf)`: background scene layer.
- `look(l,{desat,gamma,exposure,contrast})`
- `glow`, `vign`, `ell`, `adj`, `solid`, `vol(layer,[[frame,dB]…])`
- `ez(prop)`: ease 70 on every key.
- `tanim(t,g0,g1,ein,eout,blurIn,blurOut,dy,s0,s1,cx,cy)`: the caption motion.
- `fxp`/`setFx`/`keyFx`: set effect parameters by display name, falling back to the matchName. Missing parameters go to `R.warn`.
- `auto_gamma(src,t0,dur,T)` (Python): ffmpeg mean luma, cached in `plan/luma_cache.json`, returns a gamma clamped to 0.6–2.3. This keeps dark scenes readable.

Hard rule: **the generated JSX contains no backslashes.** All text goes through `js_str()` → `String.fromCharCode`, all paths use forward slashes, and the generator asserts this.

---

## 5. Commands

**Build one version** (AE holds an empty untitled project, or that version's own AEP, clean):
```bash
bash scripts/r5_build_one.sh V6B MENTALIST_JANE_V6B.aep
```
The script runs these steps and stops on any failure, with no replay:
1. gen
2. reset dispatch → `jsx/<V>_reset_report.txt` must be newer than the dispatch and start with `ok`
3. build dispatch → `jsx/<V>_build_report.json` must be fresh
4. print `build ok True layers N … warn []`

To build several versions, chain the calls, passing the previously built AEP as the "open" name for the next.

**The bridge** (Antigravity copy: `../tfx-tonyfx-execution/scripts/bridge.py`):
```bash
python bridge.py --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge --wait-seconds 60 dispatch <ABSOLUTE .jsx path>
```
- `--wait-seconds` must be 0–60.
- UNKNOWN or timeout → do NOT re-send. Read the JSX's own report file and AE's state first.
- Build guard at the top of every build JSX:
  `if(!(p && p.file===null && p.numItems===0 && !p.dirty && !p.renderQueue.rendering)){R.err='GUARD…';…}`
- Without a bridge, use File → Scripts → Run Script File on `jsx/<V>_build.jsx` in an empty project. It still saves itself and writes its report.

**Proof render** (for review only; Tony renders the finals):
```bash
S="<SESSION>"; V=V6B
mv -f "$S/proof/proof_${V}_r5.mp4" "$S/proof/proof_${V}_old.mp4"     # an existing/locked output makes aerender fail
"/c/Program Files/Adobe/Adobe After Effects 2024/Support Files/aerender.exe" \
  -project "$(cygpath -w "$S/MENTALIST_JANE_$V.aep")" -comp "JANE_$V" \
  -OMtemplate "H.264 - Match Render Settings - 15 Mbps" -output "$(cygpath -w "$S/proof/proof_${V}_r5.mp4")"
```
- Use ABSOLUTE paths. A relative `-project` resolves inside aerender's `Support Files` folder and fails with "Path is not valid".
- Render times on this PC: about 6 min for 26 s, about 14 min for 58 s. Run it in the background and wait for the completion event; do not poll with a model.
- Ignore the zero-byte `.m4v` temp files it leaves.

**Cutouts** (GPU):
```bash
"C:/Users/TUF/Documents/TonyFX Local Engine/.venv/Scripts/python.exe" scripts/make_cutouts_var.py plan/r5/cutspec.json
```

---

## 6. Version recipes (worked example: these four are accepted)

| Version | Emotion / idea | M | Total | Length | Recipe |
|---|---|---|---|---|---|
| V5A Flashback | memory, love lost | 29 | 767 | 25.6 s | Note hook 28 f → sepia 5-clip montage (Angela smile, TV, car, house night, grey suit), 8–10 f crossfades; steady bg; grain 7, glow, leaks |
| V5B Red John | menace | 29 | 767 | 25.6 s | Smiley hook → slow close-up (speed 0.75); 2 MULTIPLY ghost smileys (34 %/40 %); red grade, desat −70; shake hits; bgT 58; smiley push outro |
| V6A It's Over | grief / climax | 952 | 1692 | 56.4 s | 6 E08 park lines → "It's over" with Lisbon under the song; word-matched flashbacks (the room hallway, smiley); soft grade; last 24 s kept |
| V6B Sorry | guilt | 1052 | 1762 | 58.7 s | Press "ten years ago" → continuous diner confession with 3 word-matched flashbacks → 2 E07 lines → "Being sorry…" into the body; teal grade; old caption style |

The full configs are in `scripts/gen_variant_jsx.py` (dict `V`).

---

## 7. Review loop ("done" means all of these)

1. The build report reads `ok True`, `warn []`.
2. A proof is rendered.
3. **Automatic checks:**
   - `python scripts/scan_r3.py proof.mp4 <M>`: dark and bar-like frames. Expect no bars.
   - `python scripts/cuts.py proof.mp4 <secs>`: hard cuts, plus gaps of 3 frames or less. A short gap inside an intro means a leak.
   - `python scripts/tsheet.py proof.mp4 out.jpg t1 t2 …`: a contact sheet at chosen times.
4. **Harsh frame check:** every intro join, crossfade pre-roll and post-roll, caption entry and exit on bright frames, and flashback-versus-words timing. Run source-cut detection for every clip with `xf`/`xo` or `speed`.
5. **ONE fresh independent reviewer** with a written target (`plan/r5/REVIEW_TARGET_r5.md`). The target lists Tony's notes, the standing rules, the "known, intended" items, the sheets, and the request for blocker/major/minor findings with timestamps. Fix what it finds. At most one targeted recheck.
6. **Handoff:**
   - `HANDOFF_FOR_TONY.md` covering AEPs, comps, lengths, what changed per note, backups, and what is not verified.
   - Rename the old note `_r<N>`.
   - Back up the AEPs as `_r<N>` / `_r5pre` before every rebuild.
7. Stills and scans don't prove motion feel or audio balance. Say so; Tony watches and listens.

---

## 8. Pitfalls and fixes

| Problem | Fix |
|---|---|
| A foreign shot flashes for 2–4 frames at a clip edge or crossfade | Scene-detect the full source span (section 3.4); move `in`, slow the clip, or shorten the fades |
| aerender "Path is not valid" | Absolute `cygpath -w` paths |
| Render fails because the output is locked or exists | Rename the old proof first |
| A sentence is cut off | Use `env.py`; end the clip after the level drops |
| A 1-frame insert reads as a glitch | MULTIPLY ghost at 34–40 % with 14 f ramps |
| Background spin too fast | Steady style |
| Choppy intro | 8–10 f crossfades |
| DIFFERENCE captions vanish on bright frames | Add the soft black underlay copy (a Fill + Box Blur 9 duplicate at 42 %, below the caption, normal blend). A drop shadow on a difference layer does nothing |
| Flashback doesn't match the words | Time with `at(clip, word_time)`; show the person who is named, or their place if the sources never show them. Check the actual frame: a scene label can be wrong ("angela smile" was Jane laughing) |
| Muddy dark backgrounds | Per-scene `auto_gamma` toward T |
| JSX broken by backslashes | `js_str()` plus the assert |
| Wrong or dirty project built into | Guard plus a reset that names its own AEP |
| A stale report read as the result | Check the report mtime against the dispatch time |
| Versions look alike | Distinct cutspec, `main` and `bg` per version |
| Font missing | Install Barlow Condensed (OFL); the build reports `font` in warn |

---

## 9. Accepted example files (Mentalist Jane, 20 Nov 2026)

Session: `C:/Users/TUF/Documents/TFX_ANTIGRAVITY_STUDIO/sessions/MENTALIST_JANE_SAD_20261120/`

| Version | AEP | Comp | Proof | Backups |
|---|---|---|---|---|
| V5A | `MENTALIST_JANE_V5A.aep` | `JANE_V5A` | `proof/proof_V5A_r5.mp4` | `_r5pre`, `_r4`, `_r3`… |
| V5B | `MENTALIST_JANE_V5B.aep` | `JANE_V5B` | `proof/proof_V5B_r5.mp4` | `_r5pre`, `_r4`… |
| V6A | `MENTALIST_JANE_V6A.aep` | `JANE_V6A` | `proof/proof_V6A_r5.mp4` | `_r5pre`, `_r4`… |
| V6B | `MENTALIST_JANE_V6B.aep` | `JANE_V6B` | `proof/proof_V6B_r5.mp4` | `_r5a`, `_r4`… |
| v4 base edit | `MENTALIST_JANE_SAD_v4.aep` | see `HANDOFF_FOR_TONY_v4.md` | | |

Other session files:
- Notes: `HANDOFF_FOR_TONY.md` (r5), `CURRENT_STATE.md`.
- Plans: `plan/shot_plan.json`, `plan/grade_v3.json`, `plan/variants.json`, `plan/r5/cutspec.json` (also in `scripts/`), `plan/r5/REVIEW_TARGET_r5.md`.
- Sources: `src/` (S01E01, S01E02, S06E01–E08).
- Song: `C:/Users/TUF/Desktop/mentalist JANE/Jane! (Hoodtrap) - TheGoodVibe.mp3`, first beat at song time 0.9531 s.

---

## 10. Using this on another PC or for a new edit

**Machine-specific paths.** Edit these before running anything:
- `S = …` at the top of `gen_variant_jsx.py`, `make_cutouts_var.py`, `r5_build_one.sh`, `r5_render.sh`: the session folder.
- `B = …` in `r5_build_one.sh`: the bridge scripts folder. On Antigravity use `<STUDIO>/.agents/skills/tfx-tonyfx-execution/scripts`.
- The bridge dir `C:/Users/TUF/Documents/ae-mcp-bridge`. The AE-side bridge listener must also be installed in that PC's AE.
- The aerender path (AE 2024; change it for another AE version).
- The song path in `plan/shot_plan.json` → `audio.song`.
- Cutout tools:
  - `C:/Users/TUF/Documents/TonyFX Local Engine/.venv/` (Python with torch+CUDA, ultralytics, opencv)
  - `C:/Users/TUF/Documents/TonyFX Vision Engine/models/yolo11n.pt` and `sam2.1_hiera_small.pt`
  - `C:/Users/TUF/Documents/KINTAKI_STANDUP_CLAUDE_20261119/py/sam2_nohydra.py`

**To copy:**
1. Just to open and render the Jane edits: the AEPs, `src/` (5.9 GB), `cutouts/`, and the song. Relink in AE if the drive path differs. Install Barlow Condensed Medium and Regular.
2. To rebuild from scripts: the whole session folder plus this skill's `scripts/`. You also need Python 3 + numpy, ffmpeg/ffprobe on PATH, Git Bash (for `.sh` and `cygpath`), and the bridge (or Run Script File by hand).
3. To make new cutouts: the venv, the models and the SAM2 loader above (GPU recommended).

**New edit in this style** (new character or song):
1. Make a new session folder with the same layout (`src/ index/ plan/ cutouts/ jsx/ proof/ scripts/`).
2. Index the sources.
3. Write a beat-timed base `shot_plan.json` for the song, with two cutout slots.
4. Pick each version's emotion, then its cutouts, main scenes and background list.
5. Write the dialogue intros with `seq`/`at`/`subs_for`, checking `env.py` and the scene cuts.
6. Build → proof → review (section 7) → hand off.

Use new footage decisions for every new edit. Never reuse the Jane timeline as source.
