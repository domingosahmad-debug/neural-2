# Neural team: shared goal, shared knowledge, separate accountable workers

The current human goal and revision-bound plan are the team's authority. All members work toward that goal through named, bounded assignments. Shared knowledge lives in Neural, survives model/chat restarts, and is delivered to each member. A model's private reasoning, tools and provider conversation are its own; the team shares public decisions, evidence, mistakes and corrections.

## Before working

Read the exact assigned task, current team delivery, frozen workflow, relevant station skills and corrections. `TEAM_CONTEXT.json` in a job is the latest dispatch snapshot; TASK.json also retains the creation snapshot. Manual kits contain `TEAM_CONTEXT_CURRENT.json` generated at export. This states the shared goal, current scope, peer ownership, open recovery handoffs and relevant earlier project records. The host records the delivered context hash; existing skill-read receipts remain required. Delivery is not a claim that understanding or artistic quality was proven.

No assigned task means idle. An orientation packet is not permission to resume an old edit. Human Stop/pause wins over all older tasks, memories and automatic completion callbacks.

## Work as a team

- The director selects workers by actual tool/modality capability, availability, task depth and relevant recorded results. `neural_staffing` is advice, not a model-quality guarantee. Any connected model may enter any station; the robot/station name does not grant tools.
- Read `neural_team` action=status, or GET /api/team, for the common goal and owners. Never duplicate a teammate's task or overwrite its result. Parallel independent bounded work is permitted under the app's limits; the native editor and heavy media pipeline retain their serialization guards.
- Share concise findings, decisions, corrections and help through `neural_team` action=note or POST /api/team/note with `{project_id,kind,text,station?,source?}`. Evidence paths must exist inside Neural. Model notes are reported knowledge, not human approval. Validated task reviews are also saved into project memory. Role outputs and errors are recorded automatically; text-only workers return their findings/help needs in their normal result rather than launching peers.
- A confirmed worker failure/rejection creates a recovery handoff. The director checks the exact error and partial output, then chooses a capable alternate or does the hard integration. Create a NEW scoped task and dispatch with `recovery_of` = prior job ID plus `assignment_reason` explaining what changes. Never resend the old task or pass UNKNOWN execution to a second worker. Prior execution must be confirmed stopped. Only one active/unreviewed replacement may own a failure; after two direct replacement attempts, diagnose rather than cycle models.
- App-owned workers tagged to the active director direction receive one terminal completion handoff even if a provider forgot to register its watch. Only the current authorized direction qualifies; paused/historical work cannot wake a director. Explicit watches remain idempotent and parallel completions are batched. This creates a decision point, not a blind retry.
- A local/native/tool failure is not automatically a model failure. Reconcile exact command/result, fix the specific cause in a new guarded operation and continue supported work. A missing modality cannot be supplied by changing the text model's name. Complete construction and deliver one full review before final human playback/listening and artistic acceptance.

## Remember earlier edits

`data/team/<workflow>/projects/` preserves project goals, revision/checkpoint records, worker outcomes, feedback and recovery provenance. The append-only event journal references original tasks and artifacts. Existing real metadata is imported once; historical failures are archived, not revived. No finished scene, matte or outro becomes source footage merely because its project is remembered.

`neural_team` action=recall (query/station) or GET /api/team/recall?q=... retrieves bounded relevant records. Models receive useful prior context, not the whole transcript on every request. Reusable artistic corrections remain in the selected workflow's mistake ledger/rules; other workflows' creative memory is excluded. Past worker reports and structural approvals are labeled distinctly from actual human acceptance. A future Grok/Composer/other model receives the same role, shared history and source boundaries once a supported connection or manual task kit is configured. No new provider connection, paid API or model training is implied.

Saving, reading, searching and displaying this team memory use local scripts and no model calls. Active creative turns still consume their normal allowance. Status screens do not keep models thinking in the background.


## Visible common room and help protocol — 2026-10-21

The world has a clickable TEAM CHANNEL board and topbar Team channel button. These show real attributed messages, recipients, timestamps, task/evidence paths and replies. They are local persistent records, not simulated banter. No conversation existed merely because a historical job failed. Never invent messages from a peer.

- Read GET /api/team/channel or neural_team action=channel. New task deliveries contain bounded messages and unresolved help. The full channel remains locally recallable. Messages are project/workflow isolated.
- Directors: use neural_team action=message with message {project_id,kind,to,text,reply_to?,source?}; native file/shell directors use POST /api/command/team-message while their turn is active. Sender comes from the host. Allowed kind: finding/help/reply/decision. Recipient: Director, team, Lumen, or an exact station ID. A decision records an instruction/diagnosis, not proof it was executed.
- Text-only workers: include team_messages in the final response, max4 {kind,to,text,reply_to}. These arrive WITH the result. They cannot live-chat via tools that their adapter lacks. For a consultation, use reply_to with the actual question ID. The host attributes the message to the real assigned worker; never fabricate a colleague's answer.
- File/tool-capable station workers may POST /api/team/worker-message with job_id, exact task_sha256, kind/to/text/reply_to?/source? during their RUNNING job. Host resolves sender, station, project and workflow from that owner. This local token/hash receipt is ownership attribution, not provider cryptographic identity. External manual workers must use their connected task ownership or put messages in their terminal RESULT.json.
- A stuck worker must report attempted approach, exact missing fact/capability or failure, safe partial outputs, evidence and a specific request for help. BLOCKED/FAILED owned jobs automatically expose a help request to Director and the existing terminal completion wake. Never label an unsolved requirement COMPLETED or hide it in vague prose.
- The director reads the request, reconciles execution, records the response/decision, then assigns a NEW bounded consultation to a capable peer when useful. The brief names the original message ID, evidence and question. After the actual reply, integrate only verified usable advice; the original owner remains accountable. A reply is not a solved checkpoint.
- Help does not authorize duplicate writers, new unrequested work, blind retry, bypassing UNKNOWN, reactivation of paused edits or unsupported listening. Native operations remain serialized. If all adapters lack the required perception, disclose this at final review; do not rotate models indefinitely.
- No automatic background debate or model polling. Reading/writing/painting messages uses zero model calls. Actual reasoning/replies use the selected model's normal allowance. Existing owned worker completion wakes coordinate authorized continuation once; human pause still wins.

Relay is the studio voice concierge; Tony is the human. Relay checks local role/capability records, current revision/pause, accepted lessons and team facts before answering studio questions. Lumen's saved lessons do not grant it autonomous editing or media perception.

- Worker output rule (7 Nov 2026): for validation-only work apply knowledge/skills/verify-and-stop/SKILL.md; run noisy commands through python tools/token_shell.py --filter FILTER -- EXECUTABLE ARGS; keep prose replies compact, but never compress code, commands, guards, source clocks, identifiers or evidence. See shared/CURRENT_WORKFLOW_20261107.md.
