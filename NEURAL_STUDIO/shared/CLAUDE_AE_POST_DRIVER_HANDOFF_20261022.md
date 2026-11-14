# Tony's authorized handoff: post-driver-update AE diagnostic

Tony has updated his drivers and restarted the PC. He explicitly asks Claude in his existing chat to take over debugging because Sol's allowance is nearly exhausted. FIRST perform a controlled render stress check to see whether AE still crashes. If it crashes, continue evidence-led debugging. If it passes, report exactly what passed and its limits; do not silently resume the Bleach production edit. This new diagnostic authorization supersedes the previous no-render instruction ONLY for these bounded diagnostics.

## Current authority and preservation

- Bleach production remains paused. Preserve the existing native Claude Opus/session and all R04 projects/media/chunks. Do not switch director/provider, resume old watches, run a full edit, touch unrelated work or overwrite saved AEPs. No new paid API/model or installations.
- Neural companion was unavailable at handoff; Sol did not launch/restart it. Do not programmatically restart/inject/reload it. A normal user close/reopen is the supported activation path. Prior automatic review rejected programmatic companion restart; don't work around it.
- Native hold: data/command/NATIVE_SAFETY_HOLD.json. Keep this production hold active. This prompt authorizes isolated diagnostic renders, not clearing the general production hold. Prefer a controlled interactive AE diagnostic while the production engine remains paused. If using the shared engine, an explicit narrow diagnostic permission must bind only the scratch project/comp/range; do not globally disable safety checks. Use one native editor, actual current project/comp checks and exact command/result IDs. Never replay UNKNOWN commands or delete locks.
- Before touching AE inspect its actual current state, open project and unsaved work. Do not close unsaved user work. TonyFX is the bridge owner when open; never launch MCP Bridge Auto alongside it or a second AE instance.

## Evidence already established

- data/incidents/AE_CRASH_20261022/windows-crashes.json and dump-locations.json; last-native-command.json/result.json; project-state-before-safety.md. Do not resend old commands.
- Windows events reported AfterFX.exe 26.0.0.67, RuntimeInstaller.DLL 26.0.0.67, exception 0xc0000005, offset 0x10a7c3 at 21:54:59 and 22:10:05 Cairo Oct 22. There was also an Application Hang at 21:46. These identify a faulting module, not its underlying cause or the responsible actor/plugin.
- A blank normal startup subsequently showed the same visible crash with no Sol render dispatched. Tony's screenshot then confirmed SAFE MODE / Untitled Project.aep stayed open. Safe Mode success points to preferences/plugins/startup differences; it does not yet prove a specific culprit. No preferences, installed plugins, drivers, DLLs, Adobe installation or saved project was reset/replaced by Sol.
- Earlier director speculation that Codex computer use must be killing AE was unsupported. Do not repeat it as fact. A Not Responding UI does not establish external termination or a corrupted project. Do not attribute this to insufficient PC hardware without actual evidence.
- Prior native full render configuration was ordinary 1920x1080 /24 fps, Best Settings, H.264 Match Render Settings 15 Mbps, ~104 s. Not 4K/extreme export. R04 A has ~156 layers, B ~128. Direct aerender B ended at frame 1523 with connection forcibly closed. This is not a successful render.
- Claude created scripts/render_chunks.py outside the tracked engine with four retries/chunk. B's first two 480-frame chunks exist; neither full R04 review is delivered. Sol guarded that legacy script with Neural pause/hold and reduced retries to one. Do not run it as the diagnostic or resurrect that detached loop.

## First: bounded progressive post-update render check

1. Record the NEW boot/time, actual AE version, normal vs Safe Mode, current project/dirty state, and whether another renderer/editor is active. Get fresh Windows Application events for this boot. Do not assume driver updates fixed the problem.
2. Open normal AE if it is closed and no competing instance exists; allow a blank session to settle. A Safe Mode-only pass is insufficient for normal operation.
3. Create a NEW isolated diagnostic project under data/incidents/AE_CRASH_20261022/post-update/ (unique filenames). Start with a 5–10 second 1920x1080/24 fps/8-bit composition with moving shapes/text and a simple native effect. Use normal installed quality/templates, not oversized/high-bit-depth settings. Render ONCE to a new output; record templates, dimensions/FPS/frame count, elapsed time, process outcome and actual output decode. Do not change global rendering defaults or edit existing comps.
4. If baseline is stable, do ONE short representative effect/source-heavy proof (5–10 seconds) using a saved COPY of an R04 comp/project, with original sources/effect settings intact. Bind exact scratch project, comp and time range and output separately. Use a sensible review resolution if needed, label its actual dimensions, retain effects/audio/timing; do not disable effects and call the edit validated. This is a diagnostic, not final quality approval or a full 104-second render. A simple blank proof alone does not establish that Bleach is fixed.
5. A confirmed crash/timeout/hang stops that test immediately. Do not rerender the same failing job. Collect new crash time/module/exception/dump path, exact last frame, script's own report and matching native result; UNKNOWN is unresolved, never retried. No raw detached render loop, parallel AE instances or force-killing/relaunching AE repeatedly.

## If it still fails

Compare normal vs Safe Mode and the simplest vs effect-heavy case. Back up preferences before any reset, preserve custom workspaces/templates/scripts, and change one variable at a time. Isolate preferences, startup panels/scripts and third-party effects based on evidence. Do not delete caches/plugins en masse or replace DLLs. For a bounded changed test explain the hypothesis, exact change and actual result. If installer/driver repair requires human action, say precisely what is needed and why; don't rotate models or repeatedly consume reasoning on unchanged status. Report the first actionable crash and resolution visibly to Tony. Idle while real deterministic work runs.

If both tests pass, save a concise report with evidence and remaining limits; preserve the Bleach pause and ask Tony for the separate editing-resume direction. Do not claim complete AE stability or perceptual approval from one short render.

## Neural safety code status from Sol

New source: app/execution_control.py; changes in app/command_service.py, app/local_ops_tasks.py, web/command-ui.js and legacy render_chunks.py. Typed stop/pause routes locally, revokes continuation before cancellation, cancels unwatched local/parallel jobs, rejects late internal wakes, and repeated distinct native-host crash events trigger a persistent alert/hold instead of another recovery turn. Normal script errors are separate from host crashes; aliases of one local/native command count once. No model call for stop/status.

84 focused backend tests and the updated command UI fixture passed. Last tiny frontend stop/attachments adjustment passed the UI fixture but the generated frontend may need a fresh python build_web.py. Backend activation was not performed before the PC reboot; verify actual running version if/when Neural normally opens. Source readiness is not proof live code is loaded. Other workbench/future-delegation changes are documented in CURRENT_STATE.md and their releases; don't redo them or use them to change current Bleach staffing. No AE render was launched by Sol in the safety-fix test run.

## Read next, compactly

NEURAL_STUDIO/AGENTS.md; shared/CURRENT_RULES.md; shared/LOCAL_OPS_WORKFLOW.md; shared/PRODUCTION_WORKBENCH_WORKFLOW.md; data/bleach-aizen-yhwach/STATE.md; the relevant TonyFX execution skill/protocol. Run tools/local_ops.py capabilities before choosing mechanical operations. Inspect only relevant logs/regions, not the complete multi-megabyte director history.

Keep one concise HANDOFF_RESULT.md in this incident's post-update directory with actual tests/results, changes, blockers and next action. This is a diagnostic assignment, not permission to finish an edit or claim final artistic approval.
