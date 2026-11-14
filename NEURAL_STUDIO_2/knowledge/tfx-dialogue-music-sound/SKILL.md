---
name: tfx-dialogue-music-sound
description: Prepare clean music and complete character dialogue, synchronize captions, shape ducks and optional sound design. Use for wrong song sections, truncated words, anime-score leakage or poorly motivated SFX.
---


# Dialogue, music and sound

1. Identify the exact song version and section; record source offset/rate/pauses. Use the reference's measured segment when requested. Keep music, voice and optional effects independently editable.
2. Select an actual performance by the intended character and requested language. Tone must fit the scene. Calm Surrender was rejected; pitch/tempo changes cannot reliably turn a calm reading into anger. Do not invent shouted lines that the source does not contain.
3. Use ASR to locate candidates, then inspect/listen to the whole original phrase when supported. Boundaries need onset consonants, final phonemes and natural tail. ASR recognizing a clipped word does not prove it sounds complete. Preserve native pitch/speed unless directed otherwise.
4. Separate speech from anime backing music using the available local separator. Inspect alternate stems if speech is missing or damaged. Keep provenance and a clean source window; do not simply mute the whole clip and lose dialogue. If source isolation is poor, choose another genuine line or state the limitation.
5. Match AE layer out-point to the complete prepared audio duration, including useful tail. Align caption phrases with actual utterance. A later requested full sentence supersedes an earlier one-or-two-word constraint.
6. Duck music gently around dialogue with entry/exit room; keep intelligibility without a distracting volume pump. Use waveform and level checks plus listening, not numbers alone. WAV exports avoid lossy delay when practical; account for actual AAC timestamp/priming (often1024samples) rather than adding a universal offset.
7. Add SFX only if requested or motivated by visible action/reference. Choose matching blade/impact/air/reaction sounds, not generic whooshes on every cut. If the user removes SFX, remove them and don't restore on the next pass. Authentic stand-up laughter/applause follows its own brief.
8. Check beginning/end clicks, full words, unintended anime music, clipping and final tail at normal speed. In FFmpeg place input trim options correctly: an output -t may chop reverb/tail created by filters. Reinspect actual output duration.

Gate: correct source/language/speaker, complete performance, no silent-talking mismatch, no unwanted score, clean fades, meaningful mix and caption sync. If audio cannot be heard through available tools, report signal/ASR checks separately and leave listening acceptance unresolved.
