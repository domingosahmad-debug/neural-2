# Dexter "Mankind" aura edit — Tony's direction, 8 November 2026

Director: Claude Opus (direction, assignment, acceptance only). Workers do all analysis, editing and rendering. Everything runs inside Neural; Tony has closed the chat apps. Never ask Tony to do anything Neural can do. Report back only the finished, critic-approved edit or a true external blocker.

## Inputs (read-only sources; never modify or move)
- Song: `C:\Users\TUF\Desktop\New edit\song\ilysam - mankind - slowed.mp3` (113.7s). Same file also in `C:\Users\TUF\Downloads\New edit - dex\song\`.
- Song reference edit (same song, the edit to match or beat): `C:\Users\TUF\Desktop\New edit\song reference video\ssstik.io_1794098424153.mp4` (27.4s). Secondary candidate: `C:\Users\TUF\Downloads\New edit - dex\reference\ssstik.io_1793818123059.mp4` (28.8s). Confirm by audio match which one uses this song, and which song section. Use the Desktop one if both match.
- Text/typography references (two, copy the STYLE, not the words): `C:\Users\TUF\Desktop\New edit\text reference video\ssstik.io_1794075863639.mp4` (16.5s) and `...\ssstik.io_1794100193473.mp4` (68.2s).
- Footage: Dexter: Resurrection S02E01 `C:\Users\TUF\Desktop\DEXTER - RES\dexter.resurrection.s02e01.1080p.web.h264-cakes[EZTVx.to].mkv` and S02E02 `C:\Users\TUF\Desktop\dexter.resurrection.s02e02.1080p.web.h264-cakes[EZTVx.to].mkv`. New footage decisions; do not reuse completed scenes from earlier Dexter edits.

## What Tony wants
1. **Music section:** use exactly the same part of the song as the song reference edit (verify source clocks by audio alignment, not by guessing).
2. **Edit:** match the reference edit's weight and editing exactly, or beat it: same kinds of effects and transitions, the same graph-eased zoom velocities, scene timing locked to the beat. Measure the reference (cut times, zoom/scale curves, shakes, flashes, speed ramps) before planning. Flawless.
3. **Subject:** a Dexter aura edit. The intro may be Dexter with someone else; the edit body is Dexter only, his best epic moments.
4. **TikTok safe:** nothing too violent, no heavy blood, no knives or kill close-ups.
5. **Intro dialogue:** a voice-only scene. Remove the scene's own music so only the characters' voices remain. Censor swearing lightly in captions with a star (for example `f*ck`), never a blur or bleep.
6. **Song from frame 1:** during the intro it plays low and reverbed in the background. When the edit body starts, bring it to full volume or un-reverb it in a stylish way, landing on the beat.
7. **Text:** do NOT copy the song reference's text. Replicate and improve the typography of the two text references: word-by-word animation exactly on the spoken or sung words; one line beginning while the previous one is still ending (tasteful overlaps); polished effects. Better fonts and motion than the references.
8. **Quality gate:** the Goldfish (EGM) review and the harsh critics must be genuinely wowed, and judge ours clearly better than the reference. Do not fabricate approval.

## How to run it (low usage)
- Follow `shared/OVERSIGHT_DIRECTOR_GUIDE.md` and the skill `knowledge/skills/tfx-live-action-accepted-pipeline/SKILL.md` (Tony's accepted Dexter method), plus `tfx-reference-analysis`, `tfx-cinematic-typography`, `tfx-motion-transitions`, `tfx-dialogue-music-sound`, `tfx-tonyfx-execution` and `tfx-export-delivery`.
- Local tools first: beat, cut and scene detection, audio alignment, frame sheets and loudness, through local_ops. Then free OpenCode workers (Scout MiMo, Echo DeepSeek) for text and planning, then Haiku, then Sonnet. Sonnet or Haiku executor for the single native TonyFX/AE writer lease.
- **Codex (Sol, Terra) is out of usage: never use it.** Gemini only via Antigravity when needed.
- Batch independent assignments in one turn. Register watches and end the turn. Never poll.
- Checkpoints, each with one Goldfish review plus at most 2 harsh critics (Sonnet Goldfish; harsh critic from free OpenCode, Haiku or Antigravity Gemini):
  - the reference measurement and shot plan
  - a representative proof
  - the final render
- Repair and re-review until approved.
- Deliver a native-editable AEP, a full-quality render and a TikTok 1080x1920 export. Save the review evidence.
- Unchanged rules:
  - one native AE writer
  - no UNKNOWN replay
  - no paid fallback or credential copying
  - PS01 PURESNOW stays paused
  - leave stale job f74c1110 alone
  - earlier Dexter deliverables are protected
  - Stage C card promotion is paused; this edit has priority

## Done means
The final edit is approved by Goldfish and the critics, checked technically (decode, no audio clipping, loudness) and at full-speed motion. The deliverable paths and a short receipt go in the project STATE.md and the team channel for Tony.
