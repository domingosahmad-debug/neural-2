# Final review handoff and Claude usage — 2026-10-21

The R4 edit and original action sound were already built and fully rendered. The board mixed completed sound construction with unsupported listening, then classified final human playback/listening as production blocks. The human requested a single end-of-edit review.

`awaiting_review` now preserves unverified perceptual checks without stopping actionable production. It requires all construction finished plus this project's registered full review of the same revision, with file-integrity validation. Technical tasks cannot use this state. Explicit human checkboxes are required before final acceptance; numeric evidence never becomes listening or motion approval. Actual unfinished work, real failures and UNKNOWN native operations retain the existing recovery/alert/ownership guards. A stopped text turn with a real waiting worker watch leaves continuation to that exact watch.

Current R4 board: 7 verified, 0 production tasks left, 3 final human checks (motion, listening, acceptance), preview6966f4aeff8b48d5b5f04e11f5929cde. No media/project changes or new inference were needed. Original checkpoint history remains archived by the normal board update.

Native Claude consumption uses its actual `backup_usage`, including cache read/creation, rather than stale Codex usage. Cards distinguish consumed tokens from remaining allowance. Official CLI `rate_limit_event` windows are captured when naturally emitted; valid utilization is converted to remaining percent. Missing utilization remains unknown even when status is allowed/rejected. No extra model call, private endpoint, credential reading or fabricated quota.

Validation: 12 production, 10 supervisor, 2 native quota and 6 Claude transport Python tests pass; usage-observatory, production UI and command UI fixtures pass. Frontend rebuilt. Live loopback confirms ready_for_review=true and native Claude consumption present; director stayed idle with no active local execution. Physical sound/mic and desktop visual appearance were not tested in this release. Reload Neural once to load the new frontend.
