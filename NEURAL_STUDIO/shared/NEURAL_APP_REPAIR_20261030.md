# Neural application repair — installed 30 October 2026

Tony explicitly resumed the paused APPLICATION update. No creative edit, production continuation, provider routing change, model download, or AE command was performed. Neural was closed throughout deployment. Reopen Neural normally to load the new desktop preload and application sources. Do not interpret this software update as a new edit brief.

## Fixed behavior
- Empty manual timelines load the current project's full registered review. Existing manual timelines are preserved. An imported review now has an actual playable media URL immediately, before Save. Metadata-aware seeking and visible decode/play errors replace silent failures.
- Native desktop Import video or audio opens the standard file chooser. The isolated preload exposes only this chooser; no Node/filesystem/process API enters the renderer. Chosen media is probed through the shared local engine and streamed through a project-owned opaque ID. No source media is moved or copied. Advanced source settings are collapsed in the desktop UI.
- Split/trim/reorder, undo/redo, notes, versioned save/reload, gain/fades, waveform evidence, preview volume/mute/meter and resizable preview/timeline panels are wired to real state. A review is flattened footage, not a reconstruction of its original AE layers. AE comp sources still need an appropriate preview. Guarded Apply creates the documented separate composition; it does not overwrite accepted/user work.
- Whisper dictation now captures the selected browser microphone, displays its input level, sends in-memory PCM WAV chunks to the existing cached offline helper, and inserts final text at the draft caret without sending the message. Stop releases the microphone and drains the final chunk. No implicit downloads and no paid transcription service. Native Windows speech remains an explicit alternative.
- Explicit Select & continue is treated as a human continuation after a pause. A stale uncertain owner can be reconciled ONLY from a matching session/model's terminal host receipt with process_stopped=true, idle_inference=false, and all native/local/worker/watch/editor lanes clear. Missing, unrelated or UNKNOWN results remain blocked. Provider sessions are preserved. Queued changes state that continuation still requires a safe explicit click. The UI separates selected profile from actual running model.

## Actual evidence
Isolated actual Electron 44.7.2 / Chromium 152, using existing Ichigo review footage and the current application code:
- H.264 video decoded at 1280px width and time advanced before Save; no page errors.
- AAC decoded byte count and nonzero WebAudio output RMS verified. Last recorded RMS: 0.18790682986659407.
- Split into two clips, undo, redo, add note, save and reload preserved clips and note.
- Real HTTP source streaming returned 206 for an exact byte range; an unowned source ID was rejected.
- Real isolated preload + IPC + file preparation/import passed. The OS chooser's selection was supplied by a test stub; a human clicking the native dialog has not been tested.
- Panel resizing via keyboard passed. Fresh offscreen Electron screenshot: .maintenance/neural-repair-20261030/EDITOR_CURRENT.png.
- Real browser microphone capture using a non-looping synthesized English WAV passed through the existing cached Whisper model on CPU and inserted exactly once: “Keep my manual changes. Open the screening room and trim the second clip by 10 frames.” Existing draft preserved; capture released, pending audio zero. This is NOT a test of Tony's real microphone/accent or a promise of Codex-equivalent transcription accuracy.
- 16 targeted Python checks passed (11 previous upgrade + 5 new director recovery/continuity checks); four JS regression suites passed. Syntax checks passed. These checks do not make artistic claims.

## Remaining limits
- Real microphone permission/device/accuracy with Tony's voice needs a short user test. Browser permission denial, no input, and helper failures are visible rather than silent.
- Actual AE Apply was NOT run against Tony's live project. Compiler/guard/dry-run/UNKNOWN protections passed in tests. Preserve one writer and inspect the proposed new composition before a real apply.
- Browser-unsupported media codecs still require a compatible review/proxy. This repair does not silently transcode all footage or claim a full Premiere replacement.
- No provider inference was spent verifying paid/quota-limited directors; takeover recovery was exercised against exact session receipts in isolated tests. Current live profile/session/policy remained unchanged.

## Preservation / recovery
Deployment and checks: .maintenance/neural-repair-20261030/DEPLOYMENT.json, ELECTRON_CHECK.json, DICTATION_ELECTRON.json and PRESERVATION.json. All six protected live production/state/policy/queue/handoff hashes match the pre-update snapshot. Original application sources are retained under rollback/. The guarded rollback_repair.py restores only these source files while the app is closed and refuses to overwrite later source changes. Do not replay the installer or restore production data from a source backup.

The old 29 October pause/rejection is historical and superseded for this application repair only. App updates do not resume the anime edit. The app-package ceiling is 10 GB, not a cap on editing footage, workflow knowledge, models or projects. A clean portable package is generated separately and is not published automatically.

## Installed-build storage regression repaired

The installed regression initially found that station task folders were being counted as application payload. `storage_policy.py` now excludes station `tasks`/`inbox` and development cache directories from the app payload estimate while retaining them as protected workflow data. A 120 MB station-media fixture explicitly verifies this. All 16 Python tests and all four JS suites subsequently passed against the installed sources. No workflow files were deleted. Twelve reviewed source/test files are recorded in DEPLOYMENT.json.

Revised portable build: `.maintenance/neural-repair-20261030/release/Neural-20261030-fixed.zip` — 175,720,952 compressed bytes; 406 MB unpacked. All 483 archive manifest entries verified against their hashes. The first unpublished ZIP is retained; the fixed ZIP supersedes it. The existing exporter carries 160 durable lessons and excludes credentials, provider sessions, source media, active productions and model weights. Setup/account linking is required on another PC. Not published.
