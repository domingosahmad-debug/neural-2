# Worker lifecycle and evidence protocol

1. Read tasks/<id>/START_HERE.md, TASK.json, the project brief, CURRENT_RULES.md, station handoff and required relevant skill files/references. Check source availability and modality/tool access.
2. Before work, write ACCEPTANCE.json with task_id, worker, capabilities, skills_read (bundle-relative SKILL.md paths), accepted_at and the exact TASK.json SHA-256. An optional provider_job_id is worker reported, not independently verified by this prototype. Missing inputs/capabilities require a BLOCKED result, not invented measurements. This prototype does not authenticate external worker identity.
3. Work only the assigned bounded task. Put all result files under this task's outputs/. Do not write another station, private project, bridge or original media.
4. Write the role's primary output JSON with all fields in its station CONTRACT.json; use empty arrays/objects plus explicit limitations when blocked. No fake PASS. Evidence files must be stable and task-local. Write RESULT.json last.
5. RESULT.json fields: task_id, task_sha256, status (COMPLETED / BLOCKED / FAILED), summary, primary_output (outputs/<role-file>.json), checks (array of {name,result,evidence}), evidence (array of {path,sha256}), limitations (array of strings). Allowed check results: PASS, FAIL, NOT TESTED. Every COMPLETED primary output needs a matching evidence entry. The app verifies file existence, hash and required role fields; this is structural validation, not perceptual QA.
6. Write terminal result atomically (temporary file then rename). Stop all model requests/reasoning/status loops. Idle means zero continuing inference. No self-scheduled hourly supervision.
7. The user/director refreshes the inbox. A structurally valid COMPLETED result becomes REVIEW_REQUIRED. Approval is written separately by the app, bound to the result and evidence digests. Changed evidence invalidates prior approval. A failed check cannot be approved silently. BLOCKED/FAILED results remain visible. Revisions create a new task with an explicit parent task ID; never overwrite an accepted result.

## Context-fed desktop adapters

For Codex/Gemini/OpenCode with provider filesystem tools disabled, the local host supplies actual station/rule/skill contents and explicit small text evidence. The model reports the exact skills it read in its structured response. The host validates and persists this receipt at completion, not before inference. RUNNING is process status only. This receipt remains worker-reported; the host does not claim independent semantic proof. External filesystem workers still write their own receipt before work.


## Team messages
Optional RESULT.json `team_messages`: at most4 objects {kind: finding|help|reply, to: Director|team|station ID|Lumen, text: max1600 characters, reply_to: existing message ID or empty}. Text-only adapter response schemas also include this array. Host binds sender/project/station to task ownership. Report real uncertainty and what was attempted; do not pretend a teammate answered. A BLOCKED/FAILED result raises a director help request automatically. Reading, messaging, consultation and recovery rules: shared/TEAMWORK_PROTOCOL.md. A tool-less worker sends these with its final response, not as a live tool call.
