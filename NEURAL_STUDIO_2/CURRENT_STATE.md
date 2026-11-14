# Neural Studio 2 � current checkpoint

Updated 13 November 2026 Cairo; readiness audit dated 12 November. Read this compact checkpoint before older history. Superseded exact documents: docs/archive/readiness-before-20261112/ (SHA-256 manifest included).

## Current human scope and protected work

Prepare Neural for a DIFFERENT edit after Tony supplies a new brief. No production or creative edit is authorized by this checkpoint. CA02 e4052f1c7b5d415b86acf71a11922795 r3 remains PAUSED. Rejected Quinn e965c19132a7450da92d20c53073a0cc r2 is CLOSED/paused; preserve its work, never resume it. Historical continuation orders are superseded. Manual Edit remains human-only.

Original ../NEURAL_STUDIO stays disabled/preserved; its existing supported Antigravity executable may be used by Neural2 without launching the original app. Do not restart the original app. The temporary read-only inspection lease was released; the native owner table was empty at this checkpoint. Reconcile LIVE ownership, project/comp identity and unresolved commands before any later authorized native work. No automatic lease expiry or transfer, second TonyFX writer, MCP Bridge Auto, or replay of UNKNOWN.

Tony's accepted, currently open AE work was inspected read-only and preserved. Inspection evidence is in ../.maintenance/neural2-readiness-20261112/{active_snapshot_1794520434827.json,target_snapshot_1794520722349.json,restaurant_snapshot_1794520801714.json}. Do not infer the active comp from these dated snapshots or overwrite accepted projects. CA02 R3 and Quinn artifacts remain protected.

## Implemented infrastructure and audit fixes

Real scoped Claude/Codex/free OpenCode production hosts and the Antigravity Gemini adapter are integrated. Stations receive revision-bound packets, accepted knowledge and scoped tools; tool access is not proof that a worker read every skill. Native gateway authority checks, persistent sessions, event-driven phase progression, questions, steering, bounded repair, native/media waiting and restart reconciliation exist. Completion is driven by actual terminal events; deterministic watchers stop model inference while jobs run.

This audit repaired premature quota fallback before gateway-report reconciliation, reuse of an earlier repair cycle's native receipts, and convergence of harsh/Goldfish reviewer identities. Waiting-continuation receipt lineage remains supported. Capability display now distinguishes installed routes from quota/authentication proof. Contradictory review instructions about unavailable playback/listening were removed. No general model listening capability is claimed.

Hydrogen High and Luna are integrated under exact IDs gemini-4-hydrogen-high and gpt-6-luna. Source changes were applied through maintenance repairs 9670485bcd614b029ccb5a10b06fe59a and 7df166a73c504477b39903e20b31d71f. Combined checks on the applied source passed 242 tests; this count includes inherited/shared fixture cases and is not 242 independent scenarios. Station regression evidence: .maintenance/neural2-readiness-20261112/station-candidate/evidence/ (current-before failures and candidate passes). Parent audit evidence and public Claude feature inventory: ../.maintenance/neural2-readiness-20261112/claude-inventory-report.md and claude-inventory.json.

## Readiness, routing and verification limits

Infrastructure and bounded supplied-text connections are ready for Tony's NEW brief. Hydrogen High Plan job 5923dfad48f94b73ac82b199e4e4d8a6 / session 144c237f-7988-426e-b088-4b4d98fb7c24 completed with provider SUCCESS and exact gemini-4-hydrogen-high init. Luna medium Review job afbb535ce1e540dbb0acfe891e864e02 / session 01a1d1c7-e43f-7f23-861c-127215ae5261 completed; its exact model is confirmed by the requested CLI command, not independent server-init evidence. Reports: ../.maintenance/neural2-readiness-20261112/live-hydrogen/report.json and live-luna/report.json. Both proofs are supplied-text only: no live scoped tools, media perception, native action, new edit, artistic acceptance or real session-resume attempt. Luna corrected Hydrogen's unsupported claims, typo and role mapping; this is not an approved crew allocation. Route/model presence proves neither usable quota nor full production capability. All 11 earlier free OpenCode probes returned HTTP429; no repeated refusal loops or paid fallback. Opus previously had confirmed structured exhaustion; current quota is UNKNOWN until a permitted real outcome. Do not repeatedly test it.

Planned seats: Sol or Opus medium Director; Terra review; Hydrogen High worker; Flash High fallback; Luna bounded work; optional Fable one pass. These are intended roles, not automatic launches, confirmed quotas, or changes to the current director. Gemini always high. Opus/Sol medium. Fable exact claude-fable-5-2 low/medium only. Preserve provider conversations and no automatic switch-back.

The earlier synthetic project 1afb0099cbb449c68b2fa9ccaabf901a / run ffe17f3780a449868f92c09ce507563f reached HUMAN_REVIEW with actual native build/render and a 320x320, 72-frame, 24-fps MP4. Operator code fixes and retries were needed. No later full native build-repair-rerender-review recovery is live-proven. Fixtures, sampled images, technical decode/audio measurements, full-speed viewing, actual listening and human artistic acceptance are separate evidence. No flawless or fully unattended completion promise.

Relay synthetic ASR and speech/playback evidence is distinct from real microphone dictation: the reported live microphone devices produced silence. Do not describe synthetic transcription as a successful live human-speech capture.

Accepted Quinn and other reference/template evidence remains available in knowledge/ and data/reference-edits/. New proposed review templates are provisional; they do not override established methods or human decisions. Reuse techniques, not completed scenes or source-clock assumptions.

Next owner/action: supervising chat completes the final fresh readiness review and waits for Tony's new brief. The bounded Hydrogen/Luna connection proofs are complete within their stated limits. Do not start a new edit, resume CA02/Quinn, change native ownership or overwrite accepted AE work from this checkpoint. See PRODUCTION_READINESS.md and CONTINUE_PRODUCTION.md.

## 13 Nov 2026 ~00:35 UTC — Pure Snow run unblocked (Claude, after Codex quota ended)

Project 0e92da233e1647e9a473b172f892490c r1, run e8e4edc5c41e48348813ffbef52595da. Cause: local job ec67e6d1 step s04-frames (exact `frames` over a long pack) timed out; the flat 3-correction budget BLOCKED the Director. Repairs applied via maintenance.stage/apply + restart: bd5ac670c34c424298156a71f198cea3 (categorised budget: 8 total / 3 per category / identical fingerprint; `scout_frames` timestamp scouting; 65-min deadline only for native waits) and 553554f15db8472980db65cd55affe4f (station routing extras survive dispatch: run candidates first, then configured extras, max 8). 266 tests pass in an isolated copy. Evidence: ../.maintenance/neural2-handoff-20261113/. All five stations route Hydrogen High, Sol, Flash High, Argon High, Opus, Sonnet, OpenCode deepseek/glm free, automatic. `retry-production` returned the timeout to the Director; state WORKING (Hydrogen High). Brief unchanged. Codex quota exhausted: Sol/Terra attempts are expected to fail over. No edit completion or human acceptance claimed.

## 13 Nov 2026 ~01:10 UTC — Pure Snow second stop fixed
- Cause: Gemini scoped production workers used the 600 s text child deadline; Director job 4ac06e56 (Hydrogen) ended UNKNOWN after 105 read_artifact / 21 media_submit calls, no native write.
- Repair 0d10c890d21648fb9190e32533a89645: `providers_engine/gemini.py` passes `timeout=2400` for tool runs (266 tests pass in isolated copy).
- Job 4ac06e56 reconciled as FAILED read-only timeout (proof `../.maintenance/neural2-handoff-20261113/timeout-reconciliation-4ac06e56.json`, original result kept beside job); continuation note added (reuse completed media, no large-artifact paging, check audio_alignment ranges). Brief unchanged.
- `retry-production` → run e8e4edc5 WORKING, plan/Director, job 6e77e290. UNKNOWN provider outcomes still block by design and need the same manual reconciliation.

## 13 Nov 2026 ~01:15 UTC — app exit at 01:01:46 UTC reconciled
- Neural 2 had been relaunched from Claude's tool shell; when that shell was recycled the app (and ffmpeg of local job ba0c8404, "Director prep 08") died with it. No crash record; nothing native.
- Job ba0c8404 INTERRUPTED → reconciled FAILED with app stopped (original kept as `original-interrupted-JOB.json`); `retry-production` returned it to the Director as a known mechanical failure.
- Launch rule for agents: start NS2 detached, e.g. `Invoke-CimMethod Win32_Process Create` on `Launch-Neural-2.cmd`, never `Start-Process` from an agent shell.

## 13 Nov 2026 ~01:55 UTC — Pure Snow fourth stop fixed (ae_bootstrap signature guard)

- Cause: `production_gateway._wrapper` embedded `cfg` with `ensure_ascii=False` in a BOM-less UTF-8 JSX; After Effects read it as ANSI, so a `©` in the expected structure never matched (`Exact structural signature guard failed`, bootstrap-build-r1-001). Nothing native changed.
- Repair 86726641dc2240bea5b0efaedbc8e2e6 applied: cfg is now ASCII-escaped (266 tests OK). Candidate: `..\.maintenance\neural2-handoff-20261113\candidate4\`.
- Run continuationContext: fresh inspect + new bootstrap request id; no audio synthesis op exists, so SFX is derived/authored natively or reported, not a blocker. Brief unchanged.
- Resumed via retry-production: build / Edit / gemini-4-hydrogen-high WORKING, job dafe7997…. Live bootstrap with the fix not yet observed.

## 13 Nov 2026 ~02:00 UTC — Pure Snow fifth stop reconciled (AE modal alert during build-probe-001)

- Repair 86726641… proven live: bootstrap-build-r1-002 COMPLETED; scoped `project.aep` / NEURAL_MASTER exists; `hook_shutter_sfx.wav` exists.
- build-probe-001 stalled ~3.5 min behind an AE alert ("BCC Vignette Wipe" outflags mismatch); the worker ended `needs_input` while the request was in flight, so the run blocked ("exact settled native lease").
- After the alert was dismissed the own report arrived (ok true). Settled with Neural's `reconcile_scopes` (receipt-only, no replay) → COMPLETED. Continuation note: no BCC probing, small submits, poll ae_status.
- Resumed: build / Edit / gemini-4-hydrogen-high WORKING, job 671220dd…. Open defect: a worker ending while its native request is in flight blocks instead of entering WAIT_NATIVE.

2026-11-13 03:05Z Claude operator: Pure Snow r1 master rendered (render/Dexter_PureSnow_r1_master.mov) + MP4 review copy (local-ops job a6c1af8c review-mp4/review.mp4). Repairs applied: c2ae5762 (station-result schema echo accepted; review label/message says ProRes master, MP4 plays), b54e8151 (verify_render fps 1e-6 tolerance; exact Fraction compare had falsely failed 24000/1001). Technical gates rerun as job 725676d2 COMPLETED; run e8e4edc5 now WORKING harsh_review. Pre-edit run body: data/run-e8e4-pre-techfix.json. Human acceptance still pending.

## 2026-11-13 ~07:40Z — repair 2 resumed (Claude operator)
- Maintenance repair aee59e60 applied: `audio_extract` optional `channel` (FC for 5.1 centre dialogue); production_host accepts `neural.station-result.v1` schema echo.
- Job f734381c (Hydrogen, blocked result) reconciled UNKNOWN→COMPLETED; originals in `*.pre-reconcile`. Run body backup: `data/run-e8e4-pre-repair2-reroute.json`.
- Run e8e4 Edit candidates reordered: Sol(codex, medium) → Opus(claude, medium) → Hydrogen → Flash. Reason: Antigravity hides image tool results from Gemini, so Gemini cannot inspect frames for shot_variety/framing.
- retry-production OK: WORKING / repair, job ed51bf09 (Sol). Remaining r2 failures: shot_variety, framing, dialogue_timing. repairs 2 of max 3. Not human-accepted.

## 2026-11-13 ~12:50Z — repair 2 blocked again, resumed
- Sol applied and saved the visual repairs (fb_02 f348, body_06 f428, body_09 f470 replacement, Twixtor input FPS fix) and FC dialogue, then returned `blocked` because the repair instruction demanded "a new AEP revision" (gateway only saves pinned project.aep in place) and it lacked listening/word-alignment tools.
- Maintenance repair 803ba59c applied to production.py line 31: in-place save is the contract; verification limits are issues, not blockers. retry-production OK (DISPATCHING / repair).

## 2026-11-13 ~12:55Z — repair 2 complete; render blocked, resumed
- Repair phase returned complete (job ef783208, Sol). Render blocked at 12:34Z: gateway scope hash is per job, so a continuation task could not ae_status the predecessor inspect or reuse its guard (inspect takes ~77 s, longer than the 60 s wait) → endless re-inspect loop.
- Maintenance repair 2e1c9848 applied to production_gateway.py: continuation tasks may read settled same-project native requests and reuse a completed same-project inspect guard (live signature check in JSX still enforced). retry-production OK (DISPATCHING / render).
