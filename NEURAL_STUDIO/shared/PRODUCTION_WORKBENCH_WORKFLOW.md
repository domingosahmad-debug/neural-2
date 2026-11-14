# Production workbench — shared contract for every director and station

Applies in Neural and in editing chats using tools/workbench.py. No model evaluations/benchmarks are enabled. Never resume a project from this document. Current human scope, actual ownership, frozen station task and live TonyFX guards win.

## One edit blueprint

Before a NEW build or scoped revision, director reads `neural_workbench {action:blueprint}` / GET `/api/workbench` and maintains a single project/revision contract. Use action `save_blueprint` with `data:{project_id,revision,expected_hash,contract}`. expected_hash is the current hash or null only for first adoption. A stale hash is rejected. Prior versions remain archived. Do not retroactively rewrite the current delivered edit just because this feature was added.

Contract:
- `edit` is the installed local engine validate_plan format: fps, duration_frames, sources (path/fps/frames), shots (id/start_frame/end_frame/source_id/source_in_frame/source_out_frame), dialogue and captions. Integer half-open frame ranges. Add shot `purpose`, `characters:[]`, optional action=true and `sound:{source: ORIGINAL_SOUND_OR_STEM_PATH, ...}`. Optional `technique_id` + `technique_phase:setup|action|payoff` identifies one complete ritual; separate technique occurrences need distinct justified IDs.
- Dialogue includes unique id, text, speaker, complete_phrase=true and shot_id or shot_ids for a quote spanning several cuts. Linked pictures must cover the entire phrase without a gap. A speaker absent from any linked shot's supplied character tags needs an explicit voiceover_reason. Never truncate a spoken phrase just to fit one shot.
- Captions include unique id, quote_id, speaker, text, frame range, and a `style_id` (approved method ID) or explicit `look` description. Timing/speaker must match the supplied quote. Text/identity correctness still needs real source review.
- `music:{end_frame:...}` normally covers the full picture; `ending:{end_frame:...}` accounts for the same final frame. An intentional earlier song cut needs ending.audio_source, audio_end_frame covering the picture and an explicit intent (for example the complete final spoken phrase). This is a planned ending, not proof the exported audio is audible. The render/audio gates remain required.
- `accents:[{shot_id,frame,type,intent,...}]` anchors beat accents/zooms to real frames with purpose. Deep face zooms also need target/source match evidence in their design notes; this validator does not invent facial correspondences.

The workbench reuses the installed `validate_edit` implementation for timeline/source bounds, duration, physical-file source reuse and collision checks. It adds supplied speaker/shot/caption links, technique setup-action-payoff, source-sound intent and ending coverage. PASS is structural consistency, NOT a semantic, motion, listening or typography approval. Source/frame metadata is supplied evidence and must still be probed/verified through local ops. Blueprint doesn't hash or decode all source media on each screen read.

Every new station TASK.json carries `production_context` plus PRODUCTION_CONTEXT.json with the frozen blueprint hash and approved-method pointers. Reread it before work. Dispatch rejects a changed blueprint rather than combining incompatible old instructions. Keep each station's normal required skills/capabilities. A managed compile_ae plan with project_id automatically binds a passing blueprint when adopted; compilation checks the exact shot ledger and native_submit rechecks its hash. Custom TonyFX scripts still follow the director protocol and explicit blueprint review; this is not a universal filesystem/native sandbox.

New projects created through Neural carry blueprint_required=true, so project-linked managed native compilation cannot skip adoption. Existing projects are preserved and opt in when their blueprint is adopted. Source preparation and planning do not require a finished blueprint.

Tool-less specialists also receive the actual `station_brief` content in their supplied TASK fields. Use `blueprint_shot_ids` for a bounded region and `recipe_ids` for selected approved methods. Whole quotes spanning those shots bring their linked shot chain. A packet above 12k characters is rejected before inference instead of silently truncating it or sending the whole history to every model. Portable task kits include frozen BLUEPRINT.json and TREATMENT_METHODS.json when applicable. Filesystem paths alone are never treated as tool access.

## Approved treatments, not stolen scenes

`neural_workbench` action recipes lists the workflow-scoped library. `propose_recipe` records name, station, intent, when_to_use, avoid, steps (1–24 editable method instructions), parameters, limits and source_project/source_revision. A proposal is NOT approved. Tony approves an exact recipe hash, evidence file(s) and scoped note from Production desk → Treatments. Changing instructions or proof invalidates reusable approval. No previously approved project is automatically converted into a recipe. Starter methods are explicitly drafts.

Skills are the execution contract; recipes supply a reusable creative method. Retune to the new footage/music. Never import completed scenes, builds, mattes/outros or timing as new original work. Final result review remains independent of recipe approval.

## Recovery that proves its result

Existing event continuation, native reconciliation, capability routing and sound/visual alerts remain active. Turn-end requirement reconciliation creates project/revision-linked recovery tickets; reading them starts no model. `save_recovery` requires kind recoverable|capability|human_input|native_unknown|quota, project_id, actual diagnosis, next_action and existing compact source evidence. Record owner/station/required_capabilities when known.

An active director can select an available capable worker through the existing staffing roster and call `consult_recovery {id,agent_id}`. This creates ONE bounded diagnostic station task and registers its completion watch; END inference while it runs. The peer diagnoses; it does not become a competing native editor. Consultation does not bypass task/provider limits or start benchmarks. Native UNKNOWN/quota/human-input tickets cannot dispatch consultations. A second consultation on the same ticket is rejected: inspect the first result and create a genuinely new scoped diagnosis if needed. Ordinary failure fixes use NEW guarded operations, never replay.

Resolve only with new compact result evidence and an explicit resolution; dispatch or a confident message is not a fix. Existing unchanged-state recovery budget prevents prompt loops. When blocked by a real unsupported capability/input/quota/unknown-native state, keep the ticket/checkpoint visible and notify Tony. Perceptual review stays at end of production, not a mid-edit stop for construction work the team can do.

## Usage and deterministic evidence

New director turns and station assignments record provider/model, project/revision, role/station, purpose and reported token consumption. Native records point to actual result files; Codex records use public turn/token events. Local processing is separate. Absent tokens/allowance mean unknown. Queue/assignment records are not proof inference occurred. This is a bounded ledger from activation onward, not a full historical bill; never convert tokens into guessed subscription percentages, money or exact savings. No extra inference to classify usage. Directors can tag an explicit stage in task/station choices; internal failed-completion wakes are marked recovery.

The EXISTING local engine cache still keys source content, arguments, algorithm and tool versions and verifies each output hash. Added cache provenance identifies the original job/step/inputs and why it was reused. Unsafe/live/native/validation/publication operations remain noncacheable. New project-linked jobs show actual contact sheets on stations; legacy unlinked jobs stay in Local evidence instead of being attributed to the wrong edit. Always submit local plans with project_id; the active director API/tool supplies the current project when omitted. Standalone scripts must provide it explicitly.

## UI and outside Neural

Production desk contains Stations, Blueprint, Treatments, Recovery, Usage ledger and Local evidence. Each station constellation also has Production artifacts. The 3D monitors display actual source sheets, supplied shot/quote/type plans, checkpoints and registered full-review references; decorative simulated waveform/timeline motion has been removed. Planned graphics are labeled and not fabricated render progress. Full review opens the exact registered preview paused, preserving existing playback controls. No new 3D geometry, model timer or shadow workload is required. Rendering updates only when evidence/image/status changes; hidden-window reads stop.

Use `python tools/workbench.py status`, `blueprint PROJECT`, or `action ACTION DATA.json` from this root. `consult_recovery` requires the running authenticated Neural API/director; the CLI cannot launch a second director. Approval is an explicit human UI action. Existing local_ops.py media work, source preservation, single TonyFX editor and final artistic review are unchanged.
