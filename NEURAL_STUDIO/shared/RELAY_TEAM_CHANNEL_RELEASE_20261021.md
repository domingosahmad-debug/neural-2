# Relay + visible team communication — 2026-10-21

Implementation and tests complete. Backend activation is PENDING a normal Neural close/reopen: automatic approval review rejected the guarded companion restart with only `blocked by policy`. No alternate restart method was attempted. The running companion remains PID16840; the edit is still paused, Leader idle, continuation_authorized=false, preserved native Claude session08d743a0-6ab0-4d99-b662-ee5c1567d9d2. The rejected command did not execute its proposed state-baseline write or shutdown.

## Voice concierge

Jarvis/Signal is now **Relay**; the human is **Tony**. Visible dock/panel, local welcome, core label, screening prompt and local-worker descriptions use Relay. Existing storage keys, event IDs and aliases remain compatible. Mic still defaults OFF; default assistant ON, explicit mic consent, interruption and power-off persistence are preserved.

`app/helper_facts.py` checks local learning configuration/ledger, current revision/checkpoints/pause and compact team evidence. Identity, learner capability/status, production-progress and team-communication questions have checked local answers with source paths and timestamps, without a model call. Saved lessons are instructions, not model training or autonomous editing access. Lumen cannot independently execute a complete native edit in its learning role. Lesson-summary questions still use dated accepted records. The old broad `learn` routing and broad preview-question trigger are fixed. General reasoning uses the explicitly selected helper brain with checked context; hosted reasoning consumes its normal allowance, and a tiny local model is not guaranteed to answer every question correctly. The obsolete hardcoded Argon-first director succession was removed from its brief.

## Common room

Clickable TEAM CHANNEL world board + topbar Team channel. Actual sender → recipient, kind, timestamp, evidence path, related worker and reply-to. Empty means no conversation recorded: no seeded fake dialogue or retroactive conversion of old jobs to chat. Reply recorded is separate from issue solved. Canvas updates only on changed records, hides background reads when the window is hidden; panel inspection reduces world rendering frequency. No new continuous robot animations or model chatter.

Persistent per-project/workflow messages in existing team records + journal. GET `/api/team/channel`; `neural_team` channel/message actions. Director messages are host-attributed; native director uses `/api/command/team-message` only during an active turn. Human `/api/team/message` is attributed Tony. In-progress file/tool worker `/api/team/worker-message` requires a RUNNING owned job, exact original task hash, matching unchanged TASK.json; sender/project/station/workflow come from host ownership. This is local task attribution, not cryptographic provider authentication.

Tool-less specialist response schemas accept max4 `team_messages` and persist them with RESULT.json. They arrive at completion, not as imaginary live tool calls. Confirmed failed/blocked outcomes expose a help request even if the model omitted one. Existing owned terminal wakes notify the authorized director once. Fresh dispatches include addressed messages/help; director instructions require visible diagnosis/reply and a bounded capable consultation or NEW changed recovery when useful. Peer messages cannot start workers themselves, bypass a pause, grant missing media perception or replay UNKNOWN.

## Verification and limits

114 Python tests passed across helper, team, operations, command, continuity/staffing, native director and apprentice. Five offline JavaScript fixtures passed: Team world (actual Three geometry/canvas fixture), Team room, voice controls/privacy, lifecycle announcements and Atelier. Python/JS syntax, rebuilt frontend and knowledge integrity pass. No real provider inference, edit turn, native write or model-to-model consultation was launched. Actual physical voice, desktop appearance, live provider compliance/artistic quality and new backend HTTP endpoints remain untested until activation. No promise that prompting makes every model perfectly detect its own mistakes.

To activate: close Neural normally using its window close button, then reopen its desktop shortcut after the window exits. The desktop host already shuts down a quiescent companion on normal close; active jobs are guarded. Ctrl+R alone cannot reload Python backend changes. Recheck `/api/helper/state` identity.name=Relay, `/api/team/channel`, paused production and unchanged native Claude session afterward. Do not resume the edit merely to test this release.

Portable FINAL ZIP, website, saved edit revisions and deferred AE replica untouched.
