# Neural Studio 2 — every host/model

Read CURRENT_STATE.md first. The app is standalone; launch Launch-Neural-2.cmd.
Never modify the original ../NEURAL_STUDIO or submit AE commands while its production owns the writer.
Model catalog entries are suggestions, not proof of an executable authenticated route.
Local Qwen answers, Kokoro speech and Whisper dictation are connected. Real bounded Claude/Codex/free OpenCode text adapters and saved completion events are commissioned for supervised AE work; see PRODUCTION_READINESS.md for actual quota and capability limits. Unattended automatic production is not commissioned.

Use station_cli.py projects and station_cli.py packet PROJECT STATION for current portable task context.
Return the exact result template with station_cli.py result FILE. Results require human evidence approval.
Do not invent footage clocks, curve measurements, render evidence or artistic acceptance.

Completion is event driven. Do not schedule model turns every N minutes to check a job.
Use station_cli.py events --recipient Director, or station_cli.py wait --recipient Director --timeout 60.
wait blocks on the app event stream without model inference; a timeout is not job failure and must not trigger replay.
Read the saved result before station_cli.py acknowledge EVENT_ID. Acknowledgement persists across restart.
Every job has one persistent completion event. Duplicate delivery is possible until acknowledged; never duplicate the underlying work.
An interrupted/UNKNOWN native action must never be retried automatically.

Current concurrency: Qwen/Kokoro assistant and editor export share one admission gate; export also takes the deterministic media execution lock. Dictation is separate. Two CPU codec threads/one filter thread, low priority. This is not a machine-wide guarantee.
Dependent tasks must use the actual predecessor result. Do not launch multiple native writers or assume heavy-work concurrency is commissioned.
Dictation polls only maintain the microphone lease and collect text, never wake a model or auto-send the draft.
Local models unload after their answer. Failures remain visible and do not automatically retry.


Manual Edit is implemented: read EDITOR_WORKFLOW.md before changing timelines. Save/reopen/trim/split/reorder/music/captions and verified MP4 export work; no AE conversion, motion/keyframe engine or AI edit execution is claimed. Preserve revision guards and registered source fingerprints. Technical proof is not artistic acceptance.

Executive Director is an OPTIONAL one-pass planning station outside production and OFF by default. Read EXECUTIVE_WORKFLOW.md. Enable only on explicit human request or manual node action. It allocates work and advises Director; it never edits media, launches workers, polls, or stays running. Any host can use its portable packet/custom model name, but names do not prove executable routes or quota. Check actual capabilities/availability or report UNVERIFIED. Apply requires approved current result; it creates station handoffs and dependency guards, not provider executions. Original Neural remains separate and protected.

## Current production entry — 11 November
Read PRODUCTION_READINESS.md; current Codex Director owns cooperative native lease02e7c09771f645399996beb633c2f575. Original Neural is disabled; never restart it automatically. Manual Edit is human-only. Actual CA02 continuation is authorized and resumed; read CURRENT_STATE.md and CONTINUE_PRODUCTION.md.
Production crew displays actual jobs; assignment alone does not mean working. station_cli.py production-status and dispatch PROJECT STATION --route claude|codex|opencode --effort medium --request-id PERSISTENT_ID operate real workers. Use default effort for OpenCode, low/medium only for Fable. Completed provider output is not automatically approved station evidence. Cloud adapters are supplied-text-only; do not assign perceptual/tool/native work to them.
Use local_ops.py capabilities/submit/job/artifact/cancel for mechanical work in the running Neural2 lane. It rejects native/assembly/publication operations. Full reply output: place --out PATH before the subcommand. One local heavy lane, two bounded cloud text slots; actual evidence before dependent work. GLM and MiMo isolated tool-less routes returned HTTP429; other models and desktop availability remain independent. No repeat refusal loop or paid fallback. Haiku/Terra/Fable have actual terminal proofs. Preserve sessions and UNKNOWN evidence.
