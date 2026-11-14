# TonyFX 0.59 exact-replica execution contract

## Analyzer

Deep Analyze runs the independent providers sequentially so the laptop GPU is not oversubscribed. Provider skips and failures remain visible. The Analyzer then emits `tonyfx.replica-builder-contract.v1` with:

- exact rational FPS, dimensions, total frames, and half-open shot ranges;
- one continuous shot slot per reference shot;
- measured scene zoom enabled only where supported by evidence;
- transition families, direction, exact frame span, per-event cubic Bezier controls, AE recipe, confidence, and zoom owner;
- exact forward/reverse repeat groups;
- frame-aligned audio events;
- blocking ambiguity records and a SHA-256 certificate.

The contract does not claim to recover proprietary plugin metadata from flattened pixels.

## Builder

Exact mode validates the contract and all source assignments before creating a composition. It refuses the build when:

- the provider/certificate/build gate is missing or blocked;
- a visible transition lacks measured curve controls or a supported implementation;
- a selected source is too short at native speed;
- a source is not one continuous shot;
- an evidence-ranked candidate is available but the assignment does not match it;
- a repeat source cannot reproduce the required reverse direction;
- an unmeasured repetition occurs inside the protected repeat window.

AE receives no permission to invent creative decisions. It may implement a measured family with a native fallback only when the motion family, timing, direction, and curve remain the same.

## Structural sign-off

An Exact build is returned only after all independent structural checks pass: shot count and frame boundaries, zero base gaps/overlaps, zero source-audio leaks, native source speed, explicit reverse-only time remapping, measured zoom count, non-overlapping zoom ownership, transition duplicates no longer than 12 frames, and no unsupported family.

Finished-render comparison reports separate gates for format, cuts, transitions, curves, durations, framing, and repeat topology. The displayed similarity score is informational and cannot override a failed gate.
