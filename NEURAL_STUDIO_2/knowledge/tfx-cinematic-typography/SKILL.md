---
name: tfx-cinematic-typography
description: Design editable cinematic captions, hero words, floor-integrated and character-occluded 3D type, plus restrained animated outros. Use for reference typography, quote synchronization or poor text placement and animation.
---


# Cinematic typography

1. Verify actual spoken wording, language and timing. Choose a hierarchy: readable phrase, one emphasized word, optional small context. Do not invent a quote or force English word timings onto a differently ordered foreign performance.
2. Study reference letterforms, contrast, spacing, scale and depth. Approved Honorable pairs Impact with BodoniMTCondensed-Italic; that is a verified example, not a mandatory font pair for every brief. Confirm fonts exist and no substitution occurs.
3. Design around shot negative space and action. A hero word may be very large behind the subject, but keep enough visible to read. Review the whole animation at zoom extremes; sourceRectAtTime alone does not prove screen safety.
4. Place floor text on the actual perspective plane using vanishing lines, orientation, tracking, contact shadow and scene lighting. A frontal drop-shadow title near the floor is not ground integration. Use character mattes for real occlusion, not approximate text cropping.
5. Keep native TextDocument/text animators or separately editable letters. Animate staggered per-letter depth/position/rotation/opacity into a coherent word, sustained restrained movement with the music, and a deliberate exit. Entry fades alone do not recreate continuously animated reference type. Avoid rapid wobble, random spin and exaggerated bounce.
6. Parent type and scene elements coherently; choose intentionally between scene-attached and screen-space captions. AE 3D planes are not automatically extruded geometry. State what was actually built.
7. For user-style propagation, copy their exact approved font/effect stack and preserve timing/placement unless asked to improve those. Validate text document keys, real newlines and local time conversion.

Outros are a separate design problem: balanced spacing, restrained light and precise letter animation. In the FreyaEdits example the user rejected thick cartoon butterfly lines and excessive neon; preferred thin, elegant geometry inspired by Shinobu's hair ornament. That specific branding is optional, not a default end card on every edit.

Gate: all phrases correct, no clipped glyphs or offscreen letters, readable behind mattes, no duplicated text, synced emphasis, native editability, and visual review at entry/middle/exit plus camera extremes.

## Quinn caption correction — 12 November 2026

Neural r2 revealed every caption in 9.6 f with a ~4 f glow flash; Tony called the text bad and fixed it. Use his measured treatment in `../tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.md`: Scale 112% + Blur 10 character animator, 18–41 f reveals (9.6 f only for short punch lines), glow 0.95→0.55 over ~27 f, Echo on emphasis lines, 6–9 f overlap between neighbouring captions, centred at 540,720 on a 1080 square, censorship kept.
