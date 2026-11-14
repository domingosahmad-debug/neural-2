# Tony's notes on Mankind R4-fix3 (8 Nov 2026, from the Screening Room)

R4-fix3 is NOT accepted. It was never critic-approved: Goldfish job 1c673241 FAILED its preflight ("No supplied evidence file matches the declared target SHA-256"), so no critique ran. Never put an edit in front of Tony as "current full edit review" until a real critique has passed.

Keep: the shot selection (the scenes are good), the 1080x1080 square, the caption colours (white top line, red-pink bottom line, glow), the intro structure, and the black-and-white moment at about 0:20 (B7a). Tony likes that B&W effect. Use it once only and do not repeat it.

## Fix all of these

1. **Framing.** At about 0:21 (around B7b, edit frames 500-513) Dexter is pushed to the right edge and not centred. Measure the face x on real frames for EVERY shot, and centre the subject (or follow it with a keyframed pan). Check every shot on a frame sheet before rendering.

2. **Outro title.** Remove the plain "DEXTER / RESURRECTION" outro text. Tony's rule: either do it properly in a Dexter style (the show's font look, blood dripping from or bleeding into the letters, matching the show's title card) or have no outro text at all. If a Dexter-accurate version can't be built and checked to a high standard, remove it.

3. **Intro audio.**
   - The dialogue is barely audible and the song is too loud.
   - Until the drop (edit frame 363, about 15.14 s), the song must sit in the background with heavy reverb (muffled, distant, roughly a low-pass around 800 Hz-1.2 kHz plus a large reverb, about 12-18 dB under the dialogue). At the drop it hits at full, dry level.
   - The dialogue must be clear and forward.
   - Remove any scene music or score from the dialogue: use the pure centre channel (c2 only) of the source MKVs, or isolate the voice, rather than the current `E02_dialogue_stereo.wav`, which mixes in 0.3 of the front L/R. The source MKVs are in PROJECT assets.
   - Keep a -1 dBTP ceiling and measure loudness, so Tony can actually hear it.

4. **Effects and transitions after the drop (the main problem).**
   - The zooms are sloppy linear-looking scale moves, and nothing matches the main reference `Desktop/New edit/song reference video/ssstik.io_1794098424153.mp4`.
   - Study that reference shot by shot at full frame rate: measure each zoom's scale curve (frame-by-frame scale or optical-flow estimate), velocity-graph shape, hold, direction, shake, flashes, blur, transition type and timing against the beat. Write a per-shot effect map from that evidence.
   - Rebuild the montage effects to match it: proper speed-graph eased zoom-in/out with sharp accelerate/decelerate curves (custom temporal ease or bezier influence, not default linear or mild ease), motion blur on fast moves, beat-locked impacts, and real transitions.
   - Replace the crude placeholders.

5. **Captions.**
   - Keep the style, but make them noticeably smaller, matching the measured size in the two TEXT references (`Desktop/New edit/text reference video/ssstik.io_1794075863639.mp4` and `ssstik.io_1794100193473.mp4`).
   - Animate word by word or letter by letter, exactly as those references do (measure which, per caption, and the per-word or per-letter timing). Not a whole sentence at once.
   - Use AE text animators (range selector by words or characters), synced to the spoken words.

## Process (Tony requires zero hiccups)

- Before dispatching Lumen, make sure no other watch is 'ready' or 'waiting' (a Lumen job deadlocks otherwise; see `lumen_editor.py:89` vs `command_service.py` ~950). Do not run parallel worker watches while Lumen holds the editor. Lumen's WAITING outcomes must list plain job ID strings.
- Fix failures yourself (new guarded script, never replay). Tony must not have to report a Neural or Lumen problem again.
- Before showing Tony anything: render, make a frame sheet compared side by side with the reference frames, run a real Goldfish critique on the exact rendered file (correct SHA-256 evidence), and fix every blocker it finds. Only then post the review.
- Work live in the open `MANKIND_R4_BUILD.aep` so Tony can watch in After Effects.
- The final output goes to `data/projects/999a017db0cf467a9d246ddac899b63d/work/render/`, at 1080x1080.
