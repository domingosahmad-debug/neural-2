# Final accepted methods and reuse boundaries

Authority: Tony's recorded approval of WE ON GO W10H on 28 October 2026. Read `shared/WE_ON_GO_ACCEPTED_20261028.md`. This is an accepted example to learn from, not permission to resume it or to copy its completed scenes into another project.

## Retrieve only the needed evidence

Project root: `C:/Users/TUF/Documents/New project/NEURAL_STUDIO/data/bleach-we-on-go-20261027`.
Read `STATE.md` final acceptance section, `QA_W10H_FINAL.json`, `W10_CURRENT_HANDOFF.md` and the relevant decision/script below. Older QA/handoff documents saying approval pending describe their earlier review-time boundary; final acceptance is recorded separately. Do not rewrite those historical reports as though agents performed the human review.

Accepted AEP `EDIT_WOG_W10H_REVIEW_MASTER_AE24.aep`; main comp7 WOG_MAIN, delivery comp580 WOG_W10_DELIVERY_MASTER. Accepted full review preview9a40c2133e304cbba10e26de672dcc71. Preserve final review, ProRes float master, native float AIFF, required sources/mattes/audio/font dependencies and scripts. MD summaries do not replace these assets.

## Trigger → failure → verified correction

- Audio-only opening → an inPoint assignment collapsed outPoint → set/recheck BOTH bounds and validate actual source mapping/visible coverage after every write, including every second of opening. Treat a successful JSX transport as insufficient. W8 repaired the missing layer; W10 further removed foreign source handles.
- Very brief foreign scene flashes → source ranges crossed internal anime cuts despite acceptable timeline shot duration → inspect native source boundary frames and use exclusive source out before the foreign cut. W10 `SOL_W10B_FLOW_DECISION.json` / `SOL_W10B_REPAIR_FOREIGN_HANDLES_PULSE.jsx` retimed only the safe continuous window, keeping timeline timing, captions and music. Same-action flashes are classified separately, not blindly removed by a cut detector.
- Tiny glitched zoom kick → a stale blade-catch impact pulse peaked before the actual collision → move the existing intended pulse to the true event; preserve good zoom-flow pairs. W10 decision gives the case-specific +0.425008s correction. Do not add a second camera owner or disable every zoom.
- Hero text obscures face/eyes → safe settled text bounds ignored per-letter overshoot and camera motion → place Bankai in side negative space and Goryu below the face; inspect entire animation, not one screenshot. W10 Bankai87-frame and Goryu53-frame audits are picture evidence. Motion remains a separate modality.
- Solid yellow eyes → masks included sclera and the glowing solid replaced source anatomy → duplicate original footage, add tracked iris-ring polygon masks and SUBTRACT pupil masks; use restrained exposure plus halo, retain texture. `SOL_W9D_BUILD_REFINED_EYES.jsx` is the source-detail implementation. The final update `SOL_W10G_BUILD_FINAL_IRIS_FLOW_ATMOS_MIX.jsx` / `SOL_W10G_PROOF_REVIEW_BUILD_DIRECTION.json` supplies per-shot accepted exposure/radius/intensity. Do not use early W7 whole-eye solids as the default. Tiny Aizen eyes need verified tracking; masks cannot be approved by area statistics alone. g1 Getsuga whole-eye glow is Tony's explicit shot-specific exception, not a universal style.
- Flat or invisible added FX → adjustment placed below affected footage → inspect actual stacking and effect ownership. `SOL_W9G_FIX_BANKAI_FX_OWNERSHIP.jsx` moved heat above the source clips and below the hero text, with an order-only protected-state comparison. Prove it visibly changes the intended scene without damaging faces/edges.
- Combat sounds missing → vocals-only separation discarded action sounds → retain original event windows, source/time-remap provenance and separate editable action owners. W9 built34 source-aligned events and muted18 superseded stock hits. `audio_w9/v2/NATIVE_EVENT_INTEGRATION.json`, `SOL_W9_BUILD_ACTION_EVENT_CANDIDATES.py`, `SOL_W9_ORIGINAL_ACTION_FILTER.py` and W9F/G guarded results describe actual integration. W10 b3/s07 retiming needed matching source-audio derivatives, not old audio stretched out of sync. HPSS/no_vocals can retain score percussion and damage tonal SFX: no automatic score-free or listening-quality claim. ASR silence is not absence of sound effects.
- Impact pre-swell masks technique call / master clips → overlapping source SFX, music and voice gains sum above headroom → reproduce exact failed mix windows and trim the actual overlapping owners, preserving user offsets. Duck complete voice intervals; validate whole final mix as well as individual clips. Numeric peaks cannot prove intelligibility or tasteful balance.
- Fake float master → converting a16-bit intermediate to float cannot restore precision → export genuine native AE32-bit audio-only AIFF, verify actual pcm_f32 codec/precision/alignment, then remux with copied ProRes picture. W10 `SOL_W10J_EXPORT_NATIVE_32BIT_AUDIO.jsx`, `SOL_W10H_PACKAGE_FLOAT_DELIVERY.py`, native result and delivery provenance document the accepted path. Picture packet hash equality justified carrying forward picture checks after audio-only repackaging.

## Intro/outro and brand integration

`SOL_W10C_BUILD_DIRECTION.json`, `SOL_W10C_BUILD_EDITABLE_BLEACH_ENDS.jsx`, subsequent W10F/G/H repairs and final snapshots describe the accepted result. Editable BLEACH intro occupies the existing opening; the outro adds48frames without shifting the repaired song bridge or existing voices/captions. Authorized DISCREET ADHD wordmark uses native editable text/vector elements: split hollow-ring/katana motif, restrained crimson trail, soul-ash motes, coordinated entry/hold/exit and a source-derived decaying audio tail. These are case-specific designs; different accounts/anime need appropriate new branding. Do not use unrelated found artwork or claim a newly designed mark was supplied by the user.

## Reuse procedure

1. Read the relevant method and its rejection history, then inspect new footage/song/branding and actual tool capability.
2. Reuse algorithms, graph shapes and validated diagnostic helpers. Retune timing, centres, colours, masks, typography and effects to the new source; avoid replaying old hardcoded IDs, paths, guards or layer indices. Do not clone old finished builds/mattes/outros as new original work.
3. Prove one difficult representative moment; check source-detail iris anatomy, text face safety, single motion owner, original-sound alignment and protected-state equality before extending.
4. Run technical and sampled-picture checks separately from actual full-speed motion, listening and human acceptance. The accepted case does not prove a new project already passes.
5. Keep compact project STATE/checkpoints and exact script/result/provenance pointers. Load full snapshots only for diagnosed uncertainty, not as the default context for every step.

All listed project scripts are historical evidence/reference implementations. Reading this skill does not authorize executing them against the accepted project. Shared engine handles supported mechanical preparation/QA; one guarded TonyFX writer owns native mutation.
