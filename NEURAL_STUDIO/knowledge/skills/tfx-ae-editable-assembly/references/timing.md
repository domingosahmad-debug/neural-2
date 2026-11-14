# Timing and preservation
Record target project absolute path, comp ID/name, frame duration, expected layer IDs and protected ranges. Snapshot static properties and keyframe times/values/interpolation/eases, expressions, effect order, text documents, matte links and source IDs. Comparing evaluated values at different current times can falsely report changes; compare at the same time or compare keys.

Source mapping must distinguish film seconds, extracted-block offset, imported footage time, scene-local time and main time. Record stretch/time-remap explicitly. Never repair negative caption-local times by rerunning a global retimer. Diagnose the conversion and change only the wrong range.

Native copy is appropriate for opaque Curves and user grade stacks; use source layer identity and copy the intended properties, not all source timings. Reacquire effect references after structural edits. Identify copyToComp results by added IDs.

Moving a layer's startTime can move its keyframes: verify resulting local and main times. Test first, middle and last visible frames and transition +/-1 frames. Exclusive out-point keyframes may intentionally be extreme and never render.

Deep duplication is required when changing nested sources in a variant. A duplicated main comp that shares editable child comps does not protect the original. Preserve old variant and user media. Do not proliferate backups unless requested; use clear current-state records.
