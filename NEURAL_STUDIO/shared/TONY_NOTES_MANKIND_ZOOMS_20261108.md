# Tony's zoom/effects correction for Mankind R4 (8 Nov 2026, ~18:45Z). Overrides earlier fix4 effect instructions.

Tony REJECTS the scale zooms Lumen built. Scale-property zooms with the S-curve-plus-bump value graph are wrong and invented. They are not in our workflow and not in the reference. Do not use scale zooms for montage motion.

1. **Zooms = BlurMoCurves, as already written in our workflow.** See knowledge/skills/tfx-motion-transitions/SKILL.md, the section "Tony's adjustment-layer impact workflow — 3 November 2026", plus references/tony-dexter-impact-20261103.md, and tfx-live-action-accepted-pipeline rule 6.
   - Put BlurMoCurves on named, shot-bounded adjustment layers above each scene. This adjustment is the only zoom owner.
   - Directional blur goes on a separate upper adjustment.
   - Use Tony's measured speed-ramp temporal easing. No generic ease, no linear moves, and no alternating in/out canned zooms.
2. **Tony's own zooms are the model.** Tony hand-made cleaner zooms in MANKIND_R4_BUILD.aep, saved 8 Nov 19:54 local, and deleted some of Lumen's.
   - Read-only snapshot every keyframed property on those layers: effect/property matchNames, key times, values, temporal ease speed/influence (in and out), and interpolation types.
   - Write them to work/plan/TONY_MANUAL_ZOOMS.json.
   - Then reproduce the same pattern for the other montage cuts: the zoom carries the clip and flows into the next cut, instead of a plain zoom in then zoom out.
   - Preserve Tony's layers exactly. Do not modify or delete them.
3. **Impact shakes.** Add short impact shakes on heavy beats as part of the transitions. Keep them brief (a few frames) and beat-locked.
4. **Remove the noise filter** completely.
5. **No colour grading.** Remove any grade added to the footage. Tony will grade at the end. (The single B&W moment at B7a stays, used once.)

Everything else in TONY_NOTES_MANKIND_R4_FIX3_20261108.md still applies: framing, outro, audio, smaller word-by-word captions, and a real Goldfish critique on the exact render before Tony sees it.
