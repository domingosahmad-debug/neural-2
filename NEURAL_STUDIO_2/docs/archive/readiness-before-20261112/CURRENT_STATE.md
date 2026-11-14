# Neural Studio 2 — current checkpoint, 11 November 2026

## Current human scope
Tony explicitly PAUSED the existing CA02 edit. Preserve Claude progress; fix Neural first. The NEXT production will be a DIFFERENT edit. Do not resume CA02 automatically or treat historical “start now” text as current authorization. Manual Edit remains human-only. No AE command or creative edit was submitted during this repair. No GitHub upload.

Project: e4052f1c7b5d415b86acf71a11922795, live revision 3. Persistent productionControl.paused=true, automatic=false. Backup and pause evidence: data/production-pauses/2026-11-11T04-17-00.280404+00-00/workspace.sqlite3 and PAUSE.json; data/PRODUCTION_PAUSED.json. Latest live HTTP proof: data/control-http-proof.json (settled pause; zero active providers; 3 denied submissions; 12 existing provider jobs unchanged).

## Implemented repair
control.py joins actual provider invocations with assignments and history. Assigned does not mean running. Station clicks enter a dedicated 2D workspace with saved task history, full task/evidence and checkpoints; six readable activity cards show state/model/task/time. Queue/start reservations share a gate with pause; callbacks run outside provider/admission locks. UNKNOWN and missing durable job records never replay.

Choose model + Continue uses one persistent request ID, immutable new attempt, prior result pointers and durable provider conversations. Replacement rebinds unstarted descendants; executed descendants block replacement. Completed exact JSON results attach automatically as needs review, never as approved. Stale identities, invalid JSON or superseded tasks remain visible errors. Manual task download is Advanced, not the normal path. station_cli.py control-status/pause/continue exposes the same provider-independent contracts; --out retains full evidence.

Strict structured subscription exhaustion can trigger the explicitly saved bounded fallback chain. Generic429, network/auth errors, prose and UNKNOWN cannot. Duplicate terminal events do not advance a failed successor; delayed old-task events cannot launch newer tasks. Startup reconciles terminal checkpoints without inference. No automatic switch-back or billing changes. Gemini requires high; there is currently NO embedded Gemini adapter, so Gemini cannot honestly be marked a working automatic fallback. Fable exact claude-fable-5-2 low/medium only, never high.

Review auto-indexes current project registered exports plus explicitly mapped prior-source proofs; no Desktop-wide searching. Actual current library contains six P01/P02/P03 source proof files, not a finished CA02 full render. Latest playable source-proof version e2cad70c2bbaa9f5b9c08ac8. Project-scoped media checks fingerprints and serves byte ranges. Proof: tests_review_library.py and data/control-http-proof.json.

## Protected native state and models
Original ../NEURAL_STUDIO remains stopped/preserved. Its scheduled and offline continuations remain reversibly disabled; backups ../.maintenance/old-neural-disabled-20261111/. Do not restart it.
Native cooperative lease 9c626ce0a0224a7fb5296739dd499aed belongs to Claude Code host since00:58Z. Do not expire, clear or transfer it automatically. Last pause observation tfx-cmd-1794369750942 had a matching completed result, but was an unrelated TFX Joey Quinn proof. Reconcile LIVE identity before any later authorized native work; never infer active AE from old CA02 snapshots. One TonyFX writer; no MCP Bridge Auto. Root did not claim/write AE.
CA02 R3 artifacts remain in data/ca02-continuation/ (CA02_R3_BUILD.jsx, build-report.json, r3-plan.json, edit-r3-spec.json, phaseA-evidence-ledger.md, captions/crops/proofs). Preserve them; no artistic approval implied.

Claude/Codex subscription and exact free OpenCode transports remain bounded supplied-TEXT workers. Their labels are not tool or quota promises. Historical GLM and MiMo isolated CLI429 failures are route-specific; desktop MiMo availability is not disproved. Muse/Inkling not tested here. No credentials copied, paid fallback or provider-session reset.

## Verification and remaining work
59 focused backend tests passed (tests_control, tests_providers, tests_provider_failures, tests_review_library, tests_toolhost, tests_worker_replacement). UI fixture has22 passing checks; mocked CLI7. Actual desktop Review automatically displayed the prior proof, workflow displayed settled pause. Final desktop reload completed; six readable activity cards and dedicated Director task/history view observed. Computer-use JS session reset after the final check. Neural2 is left open; CA02 remains paused.

FULL unattended native editing is NOT commissioned. control.status.autonomousNativeReady=false. Director/Edit Continue refuses supplied-text runners instead of pretending to edit AE. providers_engine/toolhost.py is a fake-CLI-tested read-only Claude planning host, not integrated or live commissioned. Missing: guarded native tool gateway and provider-enabled production host, automatic validated phase advancement, actual full-render/audio/visual/harsh review recovery through first human review. No production_host.py exists. Do not enable native assembly through the mechanical-media endpoint as a shortcut. Existing compiler supports picture-only assembly, not full typography/effects/audio.

Next permitted action: finish the guarded production runner and event-driven phase coordinator in isolation, commission with matching native ownership and an explicitly scoped test project; do not resume paused CA02. Then run a new edit only on Tony’s new brief. See PRODUCTION_READINESS.md. Superseded checkpoint content preserved in docs/archive/control-repair-before-20261111/.

Instruction consistency: removed the stale AGENTS.md CA02 resumed order and misleading supervised-AE adapter claim. Persisted pause/current scope remains authoritative. No product code or native ownership changed in this documentation correction.

## Commissioning result — 11 November 2026 16:02Z (supersedes "NOT commissioned" above)
Test project 1afb0099cbb449c68b2fa9ccaabf901a, run ffe17f3780a449868f92c09ce507563f reached HUMAN_REVIEW through plan, plan_review, build, render, harsh_review, goldfish_review with real native AE work (TonyFX gateway, lease 223940e6d9794c9da848fdbeadf9d052). Render: data/projects/1afb0099.../renders/commission.mp4 (320x320, 72 f, 24 fps, 3.0 s). data/production-commission.json written. CA02 (e4052f1c...) stays PAUSED and untouched.

Fixes made during commissioning (all 10 test suites OK): production_gateway.py — media rows advertise no reportPath; UNKNOWN read-only inspect no longer blocks new native work; completed gateway reports readable project-wide; media_status readable by project (ledger or JOB.json) and returns readRoot; production.py — artifact() admits media jobs owned by the project; review task states criteria are mandatory and playback/listening belong to the human; repair verdict with issues but no criteria is accepted; criterion evidence may be a sentence, real paths are still scope-checked; station_tools.py media_status description.

Limits: nobody has watched or listened to the render. Each blocked phase was resumed by operator retry after a code fix; a build repair after a failed late review was not exercised live. Neural saved-and-closed a non-Neural AE project during bootstrap; copy at data/projects/1afb0099.../.neural-gateway/3d7f023c.../preserved-original.aep. Opening other projects in AE during a run causes guard failures/timeouts (timeout = UNKNOWN, never replayed).

Next: wait for Tony's new edit brief. Do not resume CA02.


## Active new human brief — Joey Quinn, 11 November
Supersedes the earlier wait-for-new-brief instruction. Tony authorized the new30s door-intro/curated-comp edit in the currently open AEP. Read data/quinn-new-20261111/CURRENT.md for exact project/run/lease/jobs and protected reference. New project e965c19132a7450da92d20c53073a0cc r2 is running via Neural-owned Opus; do not resume CA02 or commission a blank AEP. Reconcile live job state before intervention.
