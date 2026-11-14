---
name: tfx-ae-editable-assembly
description: Assemble frame-accurate, editable After Effects scenes from an approved shot plan. Use for precomps, source offsets, beat cuts, hierarchy, effect ownership, protecting user work and preserving media links.
---


# Editable AE assembly

Use tfx-tonyfx-execution for all dispatch. Read [timing and preservation](references/timing.md) before retiming or modifying an existing comp.

1. Inspect the actual project and named target. Snapshot protected work. Duplicate the comp for a broad rebuild unless the user explicitly chose the current comp. Shared nested comps must also be isolated if changing them would alter the original.
2. Use the requested/reference dimensions and rational FPS. Never force square, 30 or 60 because of an old default. Map every boundary from integer frames.
3. Make one scene per continuous camera angle with true source in/out and adequate handles. Inner scene time begins at zero; scene duration is its intended visible span. Keep source footage editable and source-audio muted except selected dialogue/reactions.
4. Separate scene footage, background grade, character matte/grade, rim, text and local atmosphere. One outer motion owner moves related components together. Transitions, captions, music, dialogue and optional SFX remain independent layers.
5. Adjustment layers sit above affected footage and cover only the intended range. Use short muted transition duplicates where overlap is required; do not extend base scenes and create hidden repeated footage.
6. Use descriptive layer/comp names, source-time comments and beat/phase markers. Avoid undocumented expressions and flattened whole-edit video. Bake only necessary intermediates (e.g. separated voice/mattes), retain provenance and their controls.
7. Validate missing media, fonts and effect matchNames. Built-in alternatives need visual proof; they are not automatically equivalent to Sapphire/BCC/Twixtor.
8. Reinspect scene frame ranges, zero gaps/unintended overlaps, source mapping, audio flags and ownership. Save the intended project. Do not call unsaved in-memory changes a delivered file.
