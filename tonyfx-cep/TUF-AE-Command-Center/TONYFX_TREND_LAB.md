# TonyFX Trend Lab 0.9

## 0.9 Additions

- Punch Flicker: a short exposure cadence for musical micro-accents.
- RGB Pulse: animated channel blur that returns cleanly to zero.
- Camera Snap: effect-level scale and rotation arrival with shutter blur.
- Zoom Stutter: a five-frame effect-level scale cadence for velocity accents.

These are native, editable building blocks rather than copies of proprietary preset packages. Use them selectively at a cut or beat; a transition should support the footage rather than sit on every cut.

This library recreates useful short-form editing behaviors with original implementations built from native After Effects controls. It does not copy third-party plugin code, assets, or proprietary presets.

## Recommended Timing

Use 4-8 frames for impacts and transitions. Use 8-14 frames for text reveals. The panel Duration control sets the timing; Amount controls motion or blur strength where relevant.

## Effects

- Ghost Zoom: short Transform scale punch with temporal echo. Best on a beat cut or close-up.
- Echo Trails: five decaying frame echoes without changing source timing.
- Radial Zoom Blur: centered radial blur with a sharp rise and fall.
- Optical Ripple: soft Magnify and Bulge refraction. Place the playhead on an up-close face or impact.
- Soft Halation: two restrained glow passes for highlight bloom.
- Flash + Shake: exposure flash plus an effect-level four-frame position shake.
- Clean Black Hit: short exposure dip with sharp start and end curves.
- Lens Glimmer: animated native lens flare, intended for bright highlights.
- Fast Whip Left/Right: select exactly two adjacent scene layers; TonyFX builds coordinated outgoing and incoming horizontal motion with matching blur.

## Text

- Blur Reveal: word-based blur and opacity reveal for lyrics or captions.
- Tracking Reveal: character-based tracking and opacity reveal for cinematic titles.

## Safety

- Existing layer Position and Scale animation is not cleared by Trend Lab effects.
- Protected, locked, intro, and user-area layers are skipped.
- Every click is wrapped in one After Effects undo group.
- Effects are named `TonyFX - ...` for quick inspection or removal.
