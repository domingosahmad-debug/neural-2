# Neural Studio 2 checkpoint — 11 November 2026

## Current human contract
Build a standalone desktop app, separate from original Neural. Preserve the original production and AE writer. User wants professional node/work detail, visible Relay, real local tools/voice, portable access for any AI, event-driven completion and useful safe concurrency. No claim of flawless/full production readiness.

## Implemented this increment
- R2 professional light/dark desktop layout, connected station cards, expandable task/history records and result details. Existing accepted motion/graph methods retained in portable station packets.
- Relay drawer with real deterministic workspace commands and offline Qwen3 0.6B advisory answers. Qwen is a small helper, not a creative director. One bounded CPU response then model unload.
- Kokoro 82M speech (Chime crew function), explicit CPU provider/two inference threads, saved/playable WAV. Whisper cached-local dictation into Relay draft only. Start/stop, microphone lease, engine choices, readable errors, single polling generation. No auto-send.
- Independent copied local-engine code and own data/cache. Safe exposed media operation currently probe; measurements remain accessible after completion. Native operations never exposed or called.
- Saved job completion inbox with unique job ID, recipient, status and explicit acknowledgement. Recovery reconciles terminal jobs without rerunning them. Acknowledgements survive restart. Imported station results now also notify Director and reconcile on startup (syntax checked; this last imported-result addition has not had endpoint commissioning).
- SSE app event stream wakes UI on state changes. Removed job-status timers. SSE heartbeat is deterministic network maintenance, no model call. Dictation polling is solely microphone lease/text collection.
- station_cli.py events/wait/acknowledge works for tool-enabled AI hosts. wait blocks on SSE; repeated delivery until explicit acknowledgement, no job replay.
- Concurrency: one assistant queue (8 outstanding cap), independently one deterministic media execution lane. CPU only; no GPU and no native AE writer in this app. Parallel heavy model/render scheduling and dependency DAG are NOT commissioned.
- AGENTS.md gives every entering AI current entry commands and protected ownership.

## Actual verification
SERVICE_PROOF.json: real Qwen useful answer, Kokoro WAV 4.71s/24kHz/mono, real media probe COMPLETED.
DICTATION_PROOF.json: Kokoro test phrase -> cached Whisper small.en CPU -> correct words, final event, Stop -> idle. Human microphone accuracy/listening NOT TESTED.
KOKORO_CPU_PROOF.json: current explicit CPU/two-thread speech code generated a second valid welcome WAV successfully.
DESKTOP_SMOKE.json: project/model dropdown/custom Fable input, theme/library/review, station expansion/history/details, actual counts, Relay navigation; mocked rapid double-click yields one dictation start/one final append and readable privacy error. No mic starts in smoke.
EVENT_PROOF.json: one notification/job, duplicate completion suppressed, first ack true/second false, results+ack survive new service instance; overlapping assistant/media job lifecycles. Overlap probe was a cache hit: NOT proof of simultaneous heavy computation.
NOTIFICATION_HTTP_PROOF.json: actual SSE signal delivered by live app with no model call.
LIVE_COMPLETION_PROOF.json: actual desktop service probe completed and woke event stream; saved duration/streams retrieved.
SOURCE_PROTECTION_PROOF.json: all 10 imported original source hashes unchanged; no native commands submitted.
Python compile and JS syntax pass. Native UI observed current Local tools/results badge and completion inbox. Desktop app launched; original Neural/AE left open.

## Independent review
Bounded fresh Goldfish service review found media contract/result access, dictation duplicate-start race and hidden error text. All fixed. One targeted recheck: no_supported_blocker_found for those fixes and changed notification integration. Reviewer did not run models/mic or approve artistic work. No full swarm.

## Remaining required work
External provider execution (Codex/Claude/Gemini/OpenCode/Fable), real director wake/continuation and quota-aware handoff remain UNCONNECTED. Catalog suggestions do not imply execution. No Codex provider inference attempt was completed. No automatic reference analysis, actual full editing pipeline or AE native writing commissioned in new app. Relay cannot yet carry out every arbitrary user action. Tool UI currently commissions probe only, not all migrated engine recipes. Local models share original cached asset locations read-only; not an independently portable installation. Abrupt-owner-death assistant guard installed but crash-kill proof not run. Voice output generated/playable, human listening/mic quality untested.

Next owner: this chat. Human update: Tony will notify us when the original Neural edit finishes before we finish Neural 2.0 and release it. No GitHub upload now. Private sharing with two or three friends requires portable app setup, canonical AI entry instructions, accepted workflow/tools and a separate exact heavy-download manifest; avoid a distribution above approximately 10 GB. See RELEASE_PLAN.md. Local documentation preparation is complete; resume implementation when Tony requests it. Do not equate UI or notification readiness with finished Neural 2.


## 11 November: real Edit and optional Executive Director
Current human scope now authorizes adding the Edit workspace immediately, then optional above-Director planning. Original Neural/AE still protected; no native commands or changes to original app in this increment. No GitHub upload authorized yet.
Implemented EDITOR_WORKFLOW.md: native media picker, registered source identity, project-isolated sequential timeline, trim/split/reorder/remove, undo/redo, one music track with offsets/gain, timed manual captions, revision-bound SQLite saving, FFmpeg CPU MP4 export, byte-range playback, native Save video and event-driven export notifications. Desktop running with Edit verification project loaded; synthetic media is explicitly labelled, not a real Dexter edit. Source preview differs from rendered continuous playback; no full effects engine, BlurMoCurves, automatic captions, AI timeline execution, multitrack video or AE replacement is claimed.
EDITOR_PROOF.json actual 60-frame export verifies shot color, mixed aspect/rate padding, caption time range, audio components, stale-save and trim guards, same-size/timestamp source mutation. EDITOR_DESKTOP_PROOF.json 16 checks pass (add/trim/split/undo/redo/reorder/music/caption/save/reopen/source/render playback, export, Range). Native picker opened and successfully imported on desktop; no listening or broad codec/performance acceptance. EDITOR_ADMISSION_PROOF.json simulated work verifies actual admission code in both enqueue orders and interrupted export reconciliation. Assistant/export now share resource_gate, export also takes media execution.lock. Dictation remains separate; old production scheduler unchanged. Goldfish initial GF01-03 addressed; one targeted reviewer recheck returned no_supported_blocker_found, with limits recorded in EDITOR_PLAN.md.
Optional Executive Director: OFF by default, outside five-stage workflow. Manual enable/custom model/catalog/one-pass packet/result approval/one-shot station allocation and Director note. Result dependency/cycle/stale/late-disable guards; no timers or automatic provider calls. EXECUTIVE_WORKFLOW.md is canonical entry, station_cli.py supports enable/disable/task/packet/result. EXECUTIVE_PROOF.json 10 backend guards and EXECUTIVE_DESKTOP_PROOF.json 10 actual desktop-flow checks pass. Test plans synthetic; no premium provider called. Real provider quota discovery and external execution remain unfinished, clearly UNKNOWN in packets. User's real project remains off. The Executive station is an optional planning harness, not an autonomous dispatcher.
Next: human can try the manual editor. Continue full production integration/motion engine separately against explicit render math. Private GitHub packaging still waits for the user's release timing and portability gates.

Final focused check: EDITOR_REIMPORT_PROOF.json verifies duplicate import stays one identity and changed same-path source receives a new identity. EDITOR_FINAL_CHECK.json confirms current desktop service/routes, both desktop proof sets pass and Executive is off for all remaining projects. Repeated synthetic test projects archived into data/test-fixture-workspace-backup.json; one clearly labelled Editor verification project retained. App restarted to load latest backend. Computer-use session ended after native import proof; no further desktop control was needed.
