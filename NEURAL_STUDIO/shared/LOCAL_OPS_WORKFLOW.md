# Local mechanical media workflow

Use this workflow for mechanical media work inside Neural and from other editing chats. Models make creative decisions and interpret selected evidence; scripts perform the repeatable measurements, extraction, arithmetic, mixing, validation, packaging and supported native compilation. Do not launch a station model to repeat a local result or poll progress.

The authoritative implementation is [app/local_engine.py](../app/local_engine.py); the standalone entrypoint is [tools/local_ops.py](../tools/local_ops.py). From `C:/Users/TUF/Documents/New project/NEURAL_STUDIO`:

```powershell
python tools/local_ops.py capabilities
python tools/local_ops.py run PLAN.json
python tools/local_ops.py status
python tools/local_ops.py status JOB_ID
python tools/local_ops.py prepare "C:/media/source.mp4" --frames 0,24,48 --audio
python tools/local_ops.py check-render "C:/media/render.mp4" --expect EXPECT.json --audio --mobile
```

For another application root, use the global `--root ROOT` option before the subcommand. `run` waits locally without a model. Reuse the app's `data/local-ops` store rather than making a parallel ad hoc queue. The worker is serialized. Capability output reports the currently implemented operation contracts and tools; missing tools are explicit blockers. Do not infer installed capability from this guide or a skill.

The two recipes remove routine plan writing. `prepare` probes/hashes the original and extracts exact frames/contact sheets; add `--events` for local scene/black/freeze candidates and `--audio` only when an audio stream is expected. `check-render` decodes the full video and checks the supplied EXPECT.json (for example `{"width":1920,"height":1080,"frames":1440,"fps":"24/1","duration":60,"audio":true}`). Add `--reference reference.wav` for measured audio alignment, or `--title TITLE --revision REV --kind full --project-id ID` to register the verified copy. `--mobile` creates a local smaller copy. These commands do not upload or publish anything.

Plans use version 1, a title, and ordered steps with unique IDs, an operation, an args object and dependencies. Paths refer to existing inputs; outputs are registered by the job. Reference an earlier step's output as `@step-id/filename`, with that step listed in `depends_on`:

```json
{
  "version": 1,
  "title": "Inspect selected source frames",
  "steps": [
    {"id": "probe", "operation": "probe", "args": {"input": "C:/media/source.mp4"}, "depends_on": []},
    {"id": "frames", "operation": "frames", "args": {"input": "C:/media/source.mp4", "frames": [0, 24, 48], "columns": 3, "width": 480}, "depends_on": ["probe"]}
  ]
}
```

Ask `capabilities` for current arguments and filenames before chaining outputs. Main operation families are metadata/hash probes, frame sheets, audio measurements/extraction/mixing, plan validation, snapshot comparison, render checks, review-copy creation and preview registration. Frame numbers are native integer indices. Ranges retain exact rational FPS and half-open timing. Cache reuse must match input content, operation configuration and tool version. A local technical FAIL stops downstream work; repair the precise cause in a new scoped plan. No automatic artistic approval follows technical PASS.

Neural exposes `GET /api/local-ops`, `GET /api/local-ops/job/JOB_ID`, `POST /api/local-ops/submit` with `{"plan": PLAN_OBJECT}` or `{"recipe":"prepare","args":{"input":"C:/media/source.mp4"}}`, and `POST /api/local-ops/cancel` with `{"job_id": "JOB_ID"}`. Use the app's normal authenticated same-origin write path. A local job has `model_calls: 0`. Durable records live at `data/local-ops/jobs/JOB_ID/JOB.json`; retain reports, outputs, cache evidence and failure details for handoff.

The Codex director calls `neural_local_ops` with `action:"submit"` and either the plan or recipe/args. It registers a final wake by default; finish the model turn while the pipeline runs. Backup directors submit through the API, then POST `/api/command/watch-local` with the returned `job_id` and finish their turn. API/standalone operations have no automatic model wake unless explicitly watched. Stop revokes watched continuation and requests local cancellation; it never asserts that an already submitted native render stopped.

Use `evidence_pack` to hand a compact JSON context to a creative worker. Supply items with input paths and optional JSON-pointer selections. It deduplicates identical inputs and fails if the requested evidence exceeds the budget rather than silently cutting off data. Retain the source reports; the director reads only unresolved gates. The existing Pip media station and rough renderer already route through the same cache/serialized engine.

Native compilation and observation are distinct from dispatch. Use only native operations advertised by the installed engine. A compiler produces inspectable JSX; it does not grant native-edit authorization. An actual native submission must preserve the designated editor, TonyFX single-writer lock, exact live project/comp guards, matching command ID, protected state and existing user authorization. `native_observe` watches an existing exact command and never dispatches or retries it. Unknown execution stops dependent native work until verified. Never start MCP Bridge Auto alongside TonyFX.

`native_snapshot` captures selected live comp/layer/property/keyframe state without editing. Unsupported native value types remain labeled, so preservation claims cover the captured fields only. `native_render` requires the exact project/comp, expected geometry/frame count/FPS and explicit installed render/output templates; it restores queue selections and chains full decode/format checks. `compile_ae` currently supports new picture-only assemblies, supplied linear retimes and explicit transform keys; it rejects unsupported captions/audio/effects instead of omitting them. `native_submit` accepts only an intact preceding compiler step from the same job and saves a fresh project. Advanced typography/effects still use the relevant native editing workflow. Native rendering and assembly have offline transport/guard tests; the live commissioning here tested read-only inspection only, not a new edit or render.

Heavy local work is serialized across desktop and standalone processes. The queue is capped at16, a bounded index serves status, and Windows job objects terminate owned FFmpeg children if their Python owner exits. Crashed jobs become INTERRUPTED and are not replayed. Cache entries are content/tool/config keyed and verified before reuse; failed gates, native operations, live plan/path/font checks and preview publication are not reused as successful mutations.

After scripts complete, inspect the generated evidence for the user's creative question, then review the current revision. Keep format/decode/audio flags and other technical checks separate from real playback/listening, identity/source-picture verification and human artistic approval. Unsupported gates remain NOT TESTED. Do not invent visual approval from hashes, ASR, metadata, or a successful script.

Lumen keeps its local observer alive. It accumulates distinct human directions, corrective reviews and failures, then batches routine reflection at roughly ten-minute intervals. Successful local bookkeeping and progress cause no reflection call. Direct questions bypass the batch delay; quota and uncertain-provider safeguards still apply. A raw tool failure alone is not a durable creative rule.

Render reliability (4November2026): the measured1080square756frame Twixtor proof legitimately took46min. Full native renders default to3600s observation; TonyFX panel wait is65min. Explicit short diagnostic waits stay valid. Do not infer progress from file-size ratios across different scenes, or treat timeout as cancellation. For proven memory pressure an explicit multi_frame_rendering=false temporarily scopes the next render; exactgeometry/fps/effects/outputquality stay unchanged and missing API fails before queue mutation. This override is a capability-guarded option, not a verified artistic/performance improvement. Prefer cached completed native outputs for mastering; no unchanged rerender.
