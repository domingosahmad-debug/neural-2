# Local tools crew — October 21, 2026

Human scope: after the Neural website, make mechanical tools and local models visible as individual robots in the existing world. Show the real tool, task, source/evidence, progress and outcome. Preserve the current edit and provider ownership. No AE-replica project or portable ZIP rebuild.

## What shipped

Enter **Local crew** in the top navigation or the foreground crew dock. This visits eight fixed tool rigs in the existing Three.js renderer. Select a robot or its anchored label to inspect its work. The same panel is available through `window.NeuralLocalWorkers.open(workerId)` for app integrations; inspecting it is GET-only, never dispatches work or calls a provider.

| Robot | Actual tool / responsibility |
| --- | --- |
| Prism | FFprobe / FFmpeg metadata, exact frames, contact sheets, event candidates |
| Splice | FFmpeg video preparation, rough assembly, review encoding and decode checks |
| Wave | FFmpeg / Python audio extraction, mixing, peaks and alignment |
| Gauge | Python file/font, plan, preservation and evidence checks; review registration |
| Forge | Existing TonyFX / After Effects guarded native execution, rendering, observation and compilation |
| Whisper | Local Whisper small.en transcription requests from Signal |
| Chime | Local Kokoro synthesis or actual Windows speech events |
| Cipher | Signal's selected local Qwen / Ollama reasoning requests; excludes hosted brains |

All 21 advertised engine operations are mapped. Outside-Neural jobs submitted to the shared engine appear through its same persistent records. This is not an OS-wide scanner for independently launched models or tools. A single bot represents a tool capability, not a new process for each file. Worker status distinguishes executing, waiting, completed history, failure, idle and unavailable. No fabricated per-operation percentage: progress is the recorded completed-step count for the job, labeled as such. Older failures stay under history instead of displacing a newer successful job. Full source basenames and check evidence can be loaded explicitly, with registered artifact links. Technical evidence remains separate from artistic approval.

Voice instrumentation observes the existing requests. It does not switch Signal on, open the microphone, warm a model, change its brain, or poll helper lease/state endpoints. Speech-output generation is distinct from later audio playback. Loaded/idle models are not labeled as processing. Voice request errors/cancellation remain visible. Directories, accounts, edit masters, current provider assignment, and native command rules are preserved.

## Status performance repair

The old status path read and deep-copied around130MB of recent native JOB evidence on every request (one actual HTTP measurement:18.72s). `app/local_activity.py` subclasses the unchanged mechanical engine and stores bounded `STATUS.json` views beside original jobs, guarded by JOB mtime/size/version. A changed external record invalidates its view. Full JOB/report/snapshot bytes remain authoritative and untouched. FAIL checks are prioritized if the live view must truncate check details. Presentation caching never changes or reruns a media operation.

The runtime and standalone CLI select this subclass. The mechanical algorithm/cache identity remains identical to the original engine, so the presentation change does not discard existing media caches. Actual commissioning: first migration+load1.484s; warm local snapshot0.141s; live HTTP after reload0.047s,20jobs/0active. Measurements are observations on this PC, not a universal guarantee. Polling is bounded, visibility-aware, GET-only and never starts hosted inference. Per-frame world reads use a cached view rather than rebuilding job/task graphs.

## Validation and limits

- `tests/test_local_activity.py`:5PASS — bounded native views, failure visibility, unchanged full evidence, cached second read, external-writer invalidation, corrupt-view recovery, unchanged media identity.
- `tests/test_local_workers.mjs`:PASS —21operations; running/waiting/terminal and disconnected states; no skipped work invented; sources/checks; local speech events; fixed cached world state;8pickable robot rigs/41added mesh draws;1,800frames with no mesh growth; reduced motion; no provider/dispatch requests.
- Existing command UI, Atelier, operations18, studio-helper18, voice-engine4 suitesPASS. Generated world/module syntax/buildPASS.
- Real loopback app displayed eight distinctive foreground robots, camera travel, real completed production records and inspectable native-tool evidence. Backend reload used guarded shutdown only after local jobs/Leader were quiescent. Both existing completed watches survived and were delivered; the authorized edit director resumed its existing review without another editing prompt.
- Physical microphone, live local voice inference, performance during active AE rendering and human artistic acceptance are NOT TESTED in this upgrade. The rig tests and brief live render measurement are not a full PC benchmark. Extra browser renderers are closed after QA.
- Desktop reload input could not activate the existing native window through Computer Use after one recovery. Files and companion are deployed; **Ctrl+R or reopening Neural** loads the new UI in that window. No forced desktop-process kill was used. Production state remains in the companion.

## Source

`web/local-workers-model.js`, `web/local-workers.js/.css`, `web/local-workers-world.js`; hooks in `cinema-world.js`, `command-ui.js`, `voice-helper.js`, `build_web.py`; `app/local_activity.py` selected in `app/operations.py` and `tools/local_ops.py`. New JS uses the already-allowed `/vendor/studio/` asset route, with CSS in the existing bundle, requiring no static-route permission expansion. Before runtime selector changes, originals were saved in `.history/local-crew-before-20261021/`.

## Separate website

The Neural showcase is public at https://neural-posthouse.modesthippo512.chatgpt.site . Local source is `../NEURO_WEBSITE` relative to the studio's parent workspace. It has actual current screenshots, the original30s Google-generated concept ad, an interactive five-step beginner guide, motion/reduced-motion controls and separate full-download/Updates sections. The download points to the human's supplied Drive link. No separate update package is invented. Linked portable October20 ZIP is preserved and does not automatically include these new changes. Never silently replace it.
