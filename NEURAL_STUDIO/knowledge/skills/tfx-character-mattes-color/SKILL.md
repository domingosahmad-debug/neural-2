---
name: tfx-character-mattes-color
description: Separate all visible characters and transfer user-authored color treatment consistently in AE. Use for Roto Brush or tracked matte workflows, missing secondary characters, grade matching, rim lighting and matte repair.
---


# Character mattes and color

1. Respect the user's manual finishing preference: **do NOT add automated color correction, `Exposure`, `Curves`, `CC Vignette`, `Brightness & Contrast`, `Hue/Saturation`, or `Sharpen`/`Unsharp Mask` stacks** to general edits unless explicitly requested for a matte/composite or palette replica. Inspect the user's actual approved example and native effect order/settings at matching times when color isolation IS requested, without replacing it with a universal Lumetri or saturation preset.
2. Determine whether native Roto Brush or generated tracked luma/alpha media is appropriate and available. They are different techniques. Never call externally generated masks native Roto Brush strokes.
3. Prompt/track each visible character independently, using distinct object IDs and correctly scaled image coordinates. Include secondary/distant characters, hats, hair, sleeves and weapons when appropriate. A box over a character can still select the floor: inspect pixels.
4. Validate mask start/middle/end AND large motion/occlusion changes. Correct drift using additional frames/positive/negative points. Check black clothes becoming holes, missing hats, floor false positives and edge chatter. One good first frame does not validate propagation.
5. Foreground, matte, background and rim use exactly matching source time, FPS, transform, remap and outer motion. Keep raw mask and adjustment controls editable. Do not lag a matte by one frame.
6. Native-copy opaque user Curves and complete approved effect stacks. Keep original settings intact; perform shot-specific exposure/input balancing on a separately named layer before the look. Copying numbers alone cannot correct a wrong mask.
7. Match the requested palette across every shot while preserving intended skin, fabric, shadow and highlight distinctions. Violet Shinobu and amber RHYNO are project-specific looks, not contradictory global defaults.

Gate: every character receives intended treatment; no orange/ungraded secondary figure, halo, contaminated floor or disappearing detail. Compare before/after composites at matching times and both sides of cuts. Freeze/cache native roto only when appropriate for the actual workflow; do not assume a matte export completed before its files are stable.

See [approved palette recipes](references/approved-user-palettes.md) for the two explicitly approved Shinobu examples.
