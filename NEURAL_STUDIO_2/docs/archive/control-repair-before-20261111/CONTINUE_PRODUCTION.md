# Continue production from any AI host

Read CURRENT_STATE.md first, then use the running independent Neural2 service. Old Neural stays disabled. Manual Edit is human-only. Production uses After Effects. A host/model change does not restart the edit or invalidate completed evidence.

Current CA02 project: `e4052f1c7b5d415b86acf71a11922795`, revision 1. Codex is Director and sole native writer. Fable `claude-fable-5-2` low is the authorized one-pass Executive. Read the live project before using these timestamped facts.

From this folder:

```
python station_cli.py projects
python station_cli.py production-status
python station_cli.py packet PROJECT STATION
python station_cli.py job-result JOB --out data/saved-result.json
python station_cli.py events --recipient Director
```

On confirmed exhaustion, another tool-enabled host (Claude, Gemini, Codex or another capable host) can take over supervision using these same APIs and files. Do not recreate the project or rerun completed jobs. Inspect the exact failed job and approved predecessors. For a terminal failed worker with work remaining:

```
python station_cli.py replace-worker PROJECT STATION --model EXACT_MODEL_ID
python station_cli.py packet PROJECT STATION
python station_cli.py dispatch PROJECT STATION --route claude --effort medium --request-id NEW_SAVED_ID
```

Use route `codex` for installed Codex workers, `claude` for installed Claude workers, `opencode` with effort `default` for validated free OpenCode workers. Gemini or any other external host can consume the portable packet and return its exact result template with `station_cli.py result FILE`; no embedded Gemini adapter is claimed. Save packet/output to files rather than printing full context. The new assignment preserves the task; read its frozen context and dependencies. Replacement does not dispatch automatically. Do not replace an already completed approved task. The service refuses replacing an active or UNKNOWN job; reconcile UNKNOWN execution first. Never silently substitute models or change billing. One real useful attempt establishes that exact route's availability; a model-specific failure says nothing about other models.

Fable stays low/medium, never high. Supplied-text adapters cannot see images, listen, use tools or operate AE. Assign visual/native work only to a host with those actual capabilities. The Director reviews and imports valid results; approval is distinct from generation. Worker completion events persist in Neural; use `wait --recipient Director --timeout 60` without inference during the wait, not timed model wakeups.

Director/native ownership transfer is separate from worker replacement. Reconcile the current command/result ID and live AE state; UNKNOWN native work must never be replayed. The outgoing owner releases the cooperative lease only at a verified safe boundary; the incoming capable host claims its own lease before writing. Do not clear an existing lease merely because a subscription expired. Preserve manual changes, exact guards and protected AEPs; create a new variant.

This is a portable recovery path, not proof that an exhausted desktop host automatically wakes a different application. If all capable routes refuse, persist the exact blocker and stop inference rather than looping.

## Handover 2026-11-11 00:57Z — Codex quota exhausted (Tony's instruction)
Codex (Sol/Terra) stopped before handing over. On CA02 project e4052f1c7b5d415b86acf71a11922795 revision 3: Director text seat -> opus (assignment 0058618f17c148f884334eb8794b0935, job eb36659536c84624b4260e4032af1222 COMPLETED); Review -> haiku replacing MiMo HTTP429 (assignment 73d2c6bdbba948b4a635b705d94fca2b, job ed594e4b8ad94339bfc04d72fff3912f COMPLETED). Raw results: data/ca02-continuation/opus-director-result.json, haiku-review-result.json; not yet approved. Local evidence job 8950396fee4648cbb3f771bea031bf47 COMPLETED (3 frame sets, 8 audio extract/measure pairs). Future Plan seat (was Terra): use opus or sonnet. Edit=sonnet and Deliver=haiku unchanged. Do not dispatch Codex routes until quota returns; no automatic switch-back.
Lease transfer 2026-11-11T00:58:03Z (Tony approved in chat): last native command tfx-bd287eecb20c4e47b80f890cef9c210e completed with matching result, unresolved false; Codex lease 02e7c09771f645399996beb633c2f575 released with its exact ID; Claude Director (tool-enabled Claude Code host) claimed 9c626ce0a0224a7fb5296739dd499aed for tony-editing-workspace / CA02 stage1c. No native command sent yet. Reinspect live AE project/comp before any write; new variant only.
