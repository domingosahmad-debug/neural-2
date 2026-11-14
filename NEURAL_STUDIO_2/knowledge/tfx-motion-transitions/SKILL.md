---
name: tfx-motion-transitions
description: Design scene-specific AE zooms, match transitions, easing, directional blur, retiming and impact effects. Use when flow feels unnatural, adapting a measured reference, or extending a user-authored motion treatment.
---


# Motion, transitions and effects

Read [learned recipes](references/recipes.md) for implementation examples, not mandatory presets.

1. Choose related outgoing/incoming shots. Determine subject/object focus, direction, framing and beat apex. Separate source-camera motion from added motion.
2. Assign exactly one added zoom owner: camera, scale, or BlurMoCurves. Never stack hidden competing zooms. Shared foreground/background/text travel must remain coherent.
3. Preserve readability, accelerate into the cut, reveal and settle. Set center, rotation and range from actual geometry. Rapid side-to-side wobble reads comedic; it is not the cinematic type/camera motion requested here.
4. Reconstruct measured or user-authored temporal easing. Recalculate tangents when value range/duration changes. Sample intermediate frames and the last visible outgoing frame; extreme keys at the exclusive out-point do not by themselves prove a glitch.
5. Use short directional blur only to support movement. Check the plugin's angle convention; Adobe Directional Blur 90 degrees is horizontal. Do not copy another plugin's number blindly. Preserve intentional non-neutral tails on user layers.
6. Grade/lighting, chromatic displacement, detailed edge echoes, blur and flashes need distinct motivated functions. Keep layers named and editable, no indiscriminate effect stack. Avoid exposed mirrored limbs/edges when extending coverage.
7. Use retiming only when requested or needed, with adequate source handles. Inspect motion vectors around swords, hair, faces, hands and occlusions. Do not label duplicate frames or damaged interpolation as smoother quality.

## Tony's adjustment-layer impact workflow — 3 November 2026

For Dexter and similar Tony-directed impact edits, place added BlurMoCurves/zoom motion on a named, shot-bounded adjustment layer above the scene. Put directional blur on a separate adjustment layer above that motion owner. Keep source retiming/Twixtor on the scene or its isolated source precomp, with one retime owner; keep grading and other source treatments independent. Do not combine retiming, grading and added zoom on the footage layer. An adjustment layer is the requested motion owner; a new precomp alone does not satisfy this instruction. Prevent an adjustment from unintentionally processing adjacent shots or captions.

Use Tony's measured speed-ramp-shaped temporal easing, with a forceful transition and a readable middle/settle; generic Easy Ease, linear slow drift and alternating canned zooms are not substitutes. Inspect both the actual value curve and derivative/speed behavior. Do not confuse BlurMoCurves Z-distance easing with the separate three-key Twixtor 150→35→150 value curve. Preserve measured endpoint speeds, influence, direction and relative timing; when changing amplitude or duration, rescale temporal speeds by (new value range / reference value range) / (new duration / reference duration). Keep asymmetric authored handles where present. Transfer the visual behavior to the adjustment's coordinate space; source-pixel centers cannot be copied unchanged into a comp-sized adjustment.

The measured Dexter example is documented in [Tony's impact reference](references/tony-dexter-impact-20261103.md). Read it when reconstructing this treatment. The screenshot and live example establish an approved direction, not blanket approval of the old edit or every numeric parameter. Strong scene selection and meaningful action still come first. Prove a bounded transition in motion before propagating it. Check the last visible outgoing frame, first incoming frame, intermediate settle, facial readability, edge coverage, blur decay and absence of competing nested zooms. Keep numeric, sampled-picture, motion and listening gates separate.

Gate: every cut's outgoing target connects to incoming target; readable settles; no black edges or duplicate limbs; no doubled zoom; no overblown flicker; narrative/beat boundaries preserved. Full-speed review is required to judge flow.

## Measured Quinn template — 12 November 2026

For beat-cut live-action bodies use the measured stack in `../tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.md`: footage layer (constant Scale, Position = crop) → shot-bounded adjustment with S_BlurMoCurves Z Dist keys (curve A 1.0→0.52, curve B 0.52→1.0, measured speed/influence handles) → separate 8-frame BCC Directional Blur adjustment centred on every cut (0→44→0, angle 140). Aim Center XY at the subject per shot. Reframe dialogue by cutting to a static position, never by sliding Position keys. Neural r2 omitted the cut transitions and left one default centre; Tony corrected both.
