# Production commissioning — 11 November 2026

**PASS for the supervised After Effects workflow. NOT commissioned for unattended autonomous production.** The actual edit remains paused for CA02 artifact/reference reconciliation. The human-only manual Edit tab is excluded. This is tested scope, not a promise of zero future defects or artistic acceptance.

Current Codex chat is Director and the sole TonyFX writer. Fable claude-fable-5-2 low/medium is the authorized optional one-pass Executive, never high. No additional blanket permission stop is required for already-authorized supervised edit work; exact native guards still apply.

| Gate | Actual evidence |
|---|---|
| Real worker execution | Haiku and Terra text tasks completed. Fable provider init confirmed exact claude-fable-5-2, low, tools[]. Full results/raw logs under data/provider-jobs/. |
| Provider continuity | PROVIDER_RESUME_PROOF.json: Haiku continued the same session after app restart. tests_providers.py:10 PASS for identity, dedupe, session recovery, cancellation/unknown and child lifetime attachment. |
| Dependency and recovery contracts | PRODUCTION_CONTRACT_PROOF.json:12 PASS using controlled text transport with real HTTP/SQLite/SSE; dependencies before dispatch, frozen actual predecessor identity/evidence, active instruction guards, independent station preparation, saved inbox/ack, no restart inference or duplicate notification. |
| Mechanical tools | LOCAL_CONNECTION_PROOF.json:7 PASS, nineteen explicitly allowed methods, native rejection before submit, actual CPU audio measurement, registered result and project/Director notification. local_ops.py uses running Neural2 service. |
| One AE writer | NATIVE_LANE_PROOF.json:7 PASS for cooperative ownership guards; NATIVE_OWNER_PROOF.json records current owner. NATIVE_LIVE_PROOF.json records matching read-only TonyFX response,35items,0missing,notrendering. No AE mutation/render during commissioning. Existing accepted guarded native workflow is reused. |
| Child cleanup | PROVIDER_LIFETIME_PROOF.json: actual harmless Windows child exited when owner died. No inference or AE involved. |
| Desktop | PRODUCTION_DESKTOP_PROOF.json:11 PASS, real endpoint/dialog, exact routes, free default effort, subscription effort restoration, writer/readiness display, no unrequested jobs. |
| Independent review | PRODUCTION_REVIEW.md: initial stale evidence/session loss/executive mutation blockers fixed; one targeted recheck found no supported remaining blocker in those changes and mechanical admission. |

## Known availability and boundaries
One actual opencode/glm-5.3-flash-free request failed HTTP429 FreeUsageLimitError. Do not repeat GLM, change billing or silently use paid fallback. A separately authorized useful opencode/mimo-v2.6-flash-free Review request b5e09e7335a74867b08fb2c0ab60ef7f also failed HTTP429 through the isolated deny-all CLI route; its native user identity data path matched the installed desktop. These are model-and-route-specific failures, not proof of a global free quota limit. Human evidence shows desktop MiMo working. Strict tool-less CLI compatibility remains uncommissioned; permissions were preserved. Inkling and Muse were not called. This does not block supervised work using completed subscription/local routes. Sonnet/Opus/Sol are supported by the same transports but not separately live-called; quota remains UNKNOWN. Gemini/other app models can use portable external-host packets; no embedded Gemini CLI adapter is claimed.

Cloud worker adapters receive supplied TEXT only. They do not access tools, perceive images/audio or edit AE. Visual/creative integration stays with the capable Director host; full-speed playback, actual listening and human acceptance remain separate. Cooperative ownership does not fence unrelated third-party bridge writers. Never launch a second native writer or replay UNKNOWN.

Qwen/Kokoro/Whisper and existing independent local engine proofs are reused. New admission covers nineteen methods; this increment ran audio_measure, not every operation/codec. Human mic/listening quality remains untested. Relay supports its existing explicit commands/advice, not arbitrary autonomous app control. Two text worker slots do not establish unrestricted heavy concurrency. Provider/system context overhead still exists; no usage-savings percentage is established.

The Fable planning response was saved and imported as **unapproved advisory evidence**, not automatically applied. One104-character local-tool label exceeded the100-character import contract; Director normalized that label in a separate reviewed file, retaining original raw output. Packet contracts now state character limits. Historical FPS/LUFS examples and redundant permission language were explicitly corrected in Director notes. A provider completion is distinct from a valid/approved station result.

## Entry and continuation
Launch Launch-Neural-2.cmd. Read AGENTS.md and CURRENT_STATE.md. Use Production crew for actual saved task execution/history, or station_cli.py dispatch with one persistent request ID. Use events/wait/acknowledge; no model timers. Unknown execution must be reconciled, not repeated. Read actual returned evidence before approving a dependent task.

Mechanical entry examples (from this folder):
```
python local_ops.py --out data/capabilities.json capabilities
python local_ops.py submit data/PLAN.json --project tony-editing-workspace
python local_ops.py job JOB_ID
python local_ops.py artifact JOB_ID STEP_ID waveform.json
```
Use station_cli.py wait --recipient Director --timeout 60 with a space between flag and value. Completion is durable; a wait timeout is not job failure. Native claim/release are authenticated /api/production actions, not AE dispatch. Exact current project/comp/structural guards remain mandatory through the installed TFX bridge helper.

Original Neural is disabled reversibly, including scheduled continuation and offline runtime auto-continuation suppression. Full state/task XML backups: ../.maintenance/old-neural-disabled-20261111/. Its source, media and AEP files are preserved. Do not restart it while this Director owns AE.

Next edit-specific gate: locate/reconcile latest CA02 stage1c R2/R3 artifacts and prior typography references, then live native snapshot/source clocks. No new edit has been made as part of these checks. GitHub release remains deferred.
