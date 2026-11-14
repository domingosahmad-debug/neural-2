# JerryFlow Behavioral Study

TonyFX was compared against the installed JerryFlow V2 extension only through its visible preview behavior. No JerryFlow code, presets, artwork, or preview media are included in TonyFX.

## Observed principles

- Most transitions concentrate motion in a short window around the cut.
- The outgoing scene accelerates into peak blur, flash, or displacement.
- The incoming scene begins at peak energy and clears quickly.
- Neutral frames before and after the transition remain readable.
- Zoom transitions combine scale with directional or radial blur instead of scale alone.
- Whips use enough travel to cross the frame and hide the cut.
- Flash effects peak at the scene change rather than sitting over the whole clip.
- Preview videos make effect choice faster than applying presets blindly.

## TonyFX implementation

- Added paired Flash Smear, Zoom Blur, Black Dip, and RGB Whip transitions.
- Kept paired left/right whips with stronger five-frame defaults.
- Added sharp outgoing and incoming temporal profiles around the cut.
- Strengthened single-layer glow, blur, exposure, chromatic, zoom, shake, black hit, glimmer, and RGB pulse values.
- Added a private, original two-scene video preview monitor with effect-specific playback treatments.
- Effect cards now preview first and require an explicit Apply action.

## Safety

- Paired transitions require exactly two selected adjacent scene layers.
- Protected or locked layers are rejected.
- Effects are named so a matching TonyFX effect can be replaced without deleting unrelated user effects.
- Original layer Transform keyframes are not rewritten by effect presets.
