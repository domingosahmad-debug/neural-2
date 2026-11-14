# Neural / compact studio upgrade — 2026-10-23

Tony clarified: preserve the existing cinematic blue-night editing identity; substantially upgrade it rather than changing the product's direction. This is a frontend-only redesign, not an edit or director assignment. Current Bleach/Claude pause and all saved media remain intact.

## Delivered
- Replaced the wide arc / cross-stage gantry with a single compact editorial pavilion. Six bay centers now span 26 world units instead of about 53, with a central director bay, distinct discipline props and carved consoles. The world remains open and wall-free.
- Rebuilt the main crew with colored mechanical chassis, camera optics, analysis prism, scout sensor, mastering ear modules, director armor and projector reels. Larger silhouettes keep the existing rig, gestures, actual task ownership and idle/working distinction.
- Eight local tools have smaller individual consoles and clickable displays, bounded to one per capability. Real tool/job activity remains in the existing observer; no synthetic work or model polling was added.
- Added a night-city backdrop, floor paths, planted edges, connected archive/idea/terrace balconies; retained usable destinations, common room, Usage Observatory, Relay and Lumen.
- Removed the gantry generator from the active scene. Static instancing is preserved through console batching: batchBoxes now excludes InstancedMesh, fixing scenery silently collapsing to one box.
- Protected the picture from foreground depth occlusion. Both review surfaces use the same video decoder, preserve aspect ratio, and restore station rendering state on close. Responsive screening camera measures the visible, loaded controls before framing. Panel cleanup happens before opening, preventing a stale Flow close callback from closing the review again. It reserves actual control/header space. Default camera fits the full projection below the navigation.

## Source and validation
`web/cutroom-world.js`, `cinema-world.js`, `atelier-world.js`, `local-workers-world.js`, `cinema-preview.js`, `studio-presence.js/css`, and `build_web.py`; rebuilt `web/index.html` and `web/world.mjs`.

Passed fixtures: cutroom layout + framing at 1466x942 / 900x650 / 900x942 + no scenery growth + actual batch integration; real WebGL foreground-rail occlusion pixel comparison; articulated crew/idle gestures/reduced motion; eight local rigs/mini benches + 1800 frames without mesh growth; preview mute/seek/pause/aspect/depth restoration; team-world picking, common-room UI, presence, chat scrolling. Three isolated activity/HTTP tests and built JavaScript syntax passed. These are graphics/contract checks, not AI model benchmarks. Live desktop showed 30 FPS Eco during overview inspection; simultaneous AE render stress performance was not tested. No new renderer, shadow pass or lighting rig was introduced.

Prior source copies are in `.maintenance/20261023-cutroom-before/`. No backend restart is required. Do not resume editing from this release note. The existing `shared/NEURAL_MAINTENANCE_AUDIT_20261023.md` remains the technical Claude/AE recovery handoff.

Live verification: opened the review via the 3D projection, sought the existing full B review to approximately 30 seconds while paused/muted, and inspected the decoded frame: all four picture edges clear, controls below. No playback/listening or artistic edit review was claimed. The overview retained about 30 FPS Eco. Current /api/activity still reports the explicit human pause, zero local jobs/watches/native command; same director untouched.
