---
name: tfx-state-handoff
description: Record current editing state, evidence, reusable feedback and a truthful continuation handoff. Use before pausing, after significant revisions, or when transferring work to another agent or model.
---


# State, feedback and handoff

Write a short current-state document rather than making the next model reread huge transcripts.

- Latest request, authorized scope, mode, completed work and immediate next step.
- Current absolute project path, saved/in-memory status, comp ID/name, dimensions/rate, source/song hashes and offsets.
- Protected manual layers/ranges, snapshot paths, desired treatment and WHY it improves the shot.
- Current plan/scripts/assets, their revision, command ID/status and pending native work. No secrets or private reasoning.
- Latest review file and exactly which modifications it includes. Mark older previews stale.
- Acceptance gates with evidence; missing listening/visual review remains NOT TESTED. User approval quotes need date/artifact identity; FINAL filenames do not count.
- Rejected approaches and reasons, distinguishing reusable lessons from project-specific choices.
- Dependencies/capabilities that were actually tested versus historical inventory.

When learning from feedback: identify trigger → failed behavior → user correction → verified method → boundaries of reuse. Preserve the user example as evidence. Promote a lesson into a skill only when the procedure is repeatable and its limits are clear; a one-off color/curve is a recipe, not a global rule.

Resumption starts with read-only state reconciliation through the authorized route. Never automatically execute an old script just because it appears in a handoff. A model switch does not grant the new runtime Codex-only tools; capability mapping comes first.
