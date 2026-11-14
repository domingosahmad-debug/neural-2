---
name: tfx-export-delivery
description: Prepare verified AE masters and social delivery exports, including Topaz and Media Encoder handoff. Use only when exporting, collecting a portable project or assessing delivery quality.
---


# Export and delivery

1. Confirm final revision, comp, work area versus full duration, dimensions, exact rational FPS, audio and destination. A queued job may reference an older comp or partial work area.
2. Preserve a high-quality intermediate (e.g. suitable ProRes HQ; alpha variant only when needed) before optional Topaz. Upscaling cannot restore missing real detail. Inspect faces, line art, motion and grain for oversharpening/temporal artifacts.
3. For delivery choose appropriate H.264 MP4 profile/level, dimensions/rate, Rec.709 for an SDR workflow, and sufficient content-dependent bitrate. Do not change color metadata to HDR or resolution tags as a quality hack. Check actual input/output color interpretation.
4. Maximum Render Quality primarily matters for scaling; maximum depth is not a universal cure. Frame duplication does not create genuine60fps motion. Preserve cadence unless deliberate validated interpolation is requested.
5. Decode the entire output, verify frame count, duration, audio streams, no corrupt frames and no accidental black tail. Compare delivered file to the approved revision. TikTok recompression cannot be eliminated or guaranteed by one bitrate preset.
6. For a project collection, include only needed dependencies, retain editable comps, relink to package-local media, verify hashes, fonts/plugin requirements and reopen/render proof when authorized. Do not distribute licensed font/plugin binaries. Avoid reopening an old example over ongoing work.

Exact platform recommendations and current Adobe/Topaz settings change; consult current official documentation if asked for specific fresh settings. Do not interrupt a user who says export already finished. Distinguish review resolution from delivery master and state portability limitations.
