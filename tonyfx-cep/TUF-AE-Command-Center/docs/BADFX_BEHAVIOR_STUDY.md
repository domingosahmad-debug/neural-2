# BadFX behavior benchmark

This file records observable animation behavior only. TonyFX does not copy or redistribute BadFX code, presets, media, or assets.

## Local inventory

- 541 FFX presets, 160 MOGRT files, and 24 AEP templates were detected in the installed BadEdits packs.
- Motion families include Position Normal, Back, Bounce, Overshoot, Scale, Rotate, and mixed Position/Scale variants.
- Text families distinguish letters, words, and lines across Fade, Position, Rotate, and Scale variants.

## Measured behavior

- A disposable AE composition successfully applied 25 representative motion and text presets with zero failures.
- The presets favor large, readable movement instead of small transform drift.
- Many text presets expose separate In and Out controllers and distinguish character, word, and line sequencing.
- Bounce and overshoot are separate motion families rather than one generic animation.
- Preset timing is commonly much longer than a 4-10 frame transition and is designed to remain readable.

## TonyFX rules derived from the benchmark

- Motion presets must cross a meaningful portion of the composition or use a clearly visible scale range.
- Scale Impact uses the user's measured logo reference: 0% -> 215% -> 100% across 48 frames.
- Position presets begin beyond the composition edge and finish at the layer's original framing.
- Motion-tab presets use standard AE Easy Ease only. Custom velocity curves remain exclusive to Graphs.
- Text begins hidden, reveals once, and remains visible. Letter and word selectors are never mixed accidentally.
- Tests must reject weak motion ranges and reject custom easing in Motion-tab presets.
