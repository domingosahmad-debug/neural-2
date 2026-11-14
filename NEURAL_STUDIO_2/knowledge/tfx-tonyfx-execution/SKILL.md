---
name: tfx-tonyfx-execution
description: Execute guarded After Effects JSX through the existing TonyFX file bridge. Use for inspecting AE, submitting scripts, matching results, handling busy or timed-out commands, and preserving user state.
---


# TonyFX execution

Read [protocol](references/protocol.md) before dispatch. Included scripts/bridge.py supports status, dry-run and dispatch; scripts/inspect_active.jsx is read-only, but still consumes the shared AE command channel. Packaging or learning alone must not dispatch it.

1. Verify the installed bridge implementation and path, current command and ownership. TonyFX is the only bridge owner while open. Never start MCP Bridge Auto, extra AE instances or file dialogs as a workaround.
2. Inspect project path, AE version, active comp ID/name/dimensions/rate, selected layers and target source/effect inventories. Never infer live identity from a handoff. Save a property snapshot before edits.
3. Use absolute JSX and report paths. Guard mutation by project path, comp ID AND name, and expected structural signature. Stable layer IDs beat indices/repeated names. Abort on mismatch.
4. Small operation, undo group, try/finally cleanup, explicit outcome report. Preserve all unrelated keys, easing, expressions, sources, transforms, text and manual grades. Do not global-rebuild a locally adjusted edit.
5. Submit one new ID; accept only matching _commandId. A host transport success must also be followed by the JSX's own completion report and actual state checks.
6. Wait for terminal status and native work to finish. Never replay a timeout blindly or delete locks. Read-only inspection also must wait its turn. Check outputs and live state before deciding a corrected new command is needed.

Common ExtendScript hazards: JSON may be unavailable; use a small serializer or known tested implementation. File.exists is a property: (new File(path)).exists. copyToComp does not guarantee layer 1: identify added layer IDs. Adding/moving effects can invalidate property references: reacquire them. Changing startTime can shift keyframes. saveFrameToPng may finish asynchronously: wait for all stable readable files before restoring preview resolution. Use new WAV filenames and relink to avoid file locks.

Prefer native copying of user-authored effects with opaque Curves/Lumetri data. Do not invent numeric serialization for properties the API cannot read.

Time Remap: deleting its last key disables timeRemapEnabled and hides the property. Set desired keys first, then prune only obsolete key times; verify enabled state, exact times and values. Do not use a generic remove-all-keys helper for remapping. AVLayer.frameBlending is read-only; use frameBlendingType when a change is needed and verify the result. Static script review alone does not prove native API behavior.

Neural2 save/copy verification: ExtendScript File metadata can be stale after save/copy. Reconstruct each File from its fsName after the write before reading exists/length. Verify both fresh file objects and native property readback. Preserve the actual open AEP path separately from any delivery copy. A failed verification after a write is partial execution: reconcile the matching report, file hashes and read-only current state before considering a new operation; never replay the mutation based on the verification error alone.
