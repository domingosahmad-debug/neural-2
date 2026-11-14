# Shared local video matte workflow — Tony's direction, 26 October 2026

## Current authority

Tony rejected computer-use/mouse-driven Roto Brush automation. Use a local, scriptable video segmentation/matting pipeline. Claude remains director in the existing session. Do not stop his ongoing edit to install/test a replacement. Do not use TonyFX uiStroke/uiClick or a GUI painting loop for roto. This supersedes the earlier native-UI experiment as the preferred matte method; it does not revoke ordinary guarded JSX editing.

## Recommendation and actual availability

Use **SAM 2.1 video tracking with saved correction prompts**, lossless matte sequences, and a separately validated edge-refinement pass when the shot needs it. This is the recommended practical workflow for this RTX 4060 Laptop GPU (8 GB VRAM); it is not a claim of a universally best model or perfect automatic masks.

Available NOW: the existing pinned SAM2.1-small environment and Claude's script at `data/bleach-bankai-two-edits-20261025/sam2_video.py`. Its 80-frame hands report records 48.2 seconds. This is one measured shot, not a promised speed for other clips. It has already produced external mattes; it is not native Roto Brush. The script is project-specific and hardcodes the episode/FPS, so do not pass another project's footage without generalizing its input contract.

Pinned available source: `facebookresearch/sam2@2b90b9f5ceec907a1c18123530e92e794ad901a4` in that project's vendor folder. Cached small checkpoint: `models/sam2/sam2.1_hiera_small.pt`, SHA256 `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`. Python: `tools/sam2env/Scripts/python.exe` inside that project. Cache checks must precede inference; no implicit network downloads.

Candidate upgrade for anime: **Zarxrax/SAM2Anime**, a Base+ fine-tune, model card revision `23cd2dae74d161be3c920245d716c84ec33a8976`, declared Apache-2.0. The author explicitly warns it can outperform or underperform standard SAM2 depending on the anime, and crossing multiple objects can jumble parts. Test one subject per pass and compare with the existing standard checkpoint; do not automatically promote it because it is anime-specific. It is NOT installed or validated here yet.

Candidate edge refiner: **ViTMatte small**, HUST's image+trimap model. Code MIT; published `hustvl/vitmatte-small-composition-1k` weights Apache-2.0. Use corrected SAM masks to define known foreground/background and a narrow unknown edge band. Preserve the corrected core. It is an IMAGE matting model, not a temporal tracker; temporal flicker still requires video review and correction. It is NOT installed or tested here yet. Missing fingers or wrong subject selection must be repaired in tracking, not hidden with blur or a matting claim.

## Why not simply pick the newest model

| Option | Fit and constraint | Current decision |
| --- | --- | --- |
| SAM2.1 + optional ViTMatte | General subjects; APIs; permissive published code/weight licenses; tracker and soft-edge roles are distinct | Practical default architecture; keep validated cached tracker until upgrades pass |
| Sammie-Roto 2 | Free desktop application combining SAM2, anime checkpoint, matting, deduplication and export | Useful reference and optional human-facing app; do not automate its GUI or install the whole bundle just to access scriptable models |
| MatAnyone 2 | Human video matting from an initial mask; soft details; S-Lab non-commercial terms | Optional non-commercial candidate, not a blanket default for paid work or arbitrary anime/objects |
| SAM2Matting | New generalized video matting; authors explicitly show anime/objects; checkpoints/inference released | Strong non-commercial candidate; README and LICENSE disagree on NC vs NC-SA, but both restrict commercial use. No local validation yet |
| VideoMaMa | Fine matte refinement using a video generative prior; heavier; code CC BY-NC and additional checkpoint terms | Do not make this 8 GB laptop's automatic default. Published Sammie tests use about 12 GB at 720p; different GPU/clip, not a measurement here |
| SAM3/3.1 | Text prompting and tracking; larger, gated weights/custom license | Not needed to unblock this workflow; no automatic gated downloads |

## Repeatable production procedure

1. Use local_ops capabilities first for supported probing, extraction and evidence. The installed local engine has no segmentation/matting operation; do not pretend it does. Run model inference explicitly in its isolated environment, under one owned bounded process, while no competing GPU-heavy job is active.
2. Work one continuous source shot at a time. Save source content hash, exact source-frame range, rational FPS, dimensions, object IDs, checkpoint hash and correction prompts. Extract matching frames through supported local operations. Never track through a cut or assume 24 fps when the source is 24000/1001.
3. Select each character/part with independent object IDs or passes. Record positive points for missing areas, negative points for unwanted areas, and correction-frame indices at pose/occlusion changes. Inputs are file coordinates, not Windows mouse input.
4. Propagate forward/backward from the chosen annotated frames and inspect drift. Preserve raw masks separately. Avoid blanket hole-filling: real gaps between fingers, sleeves and weapons must remain. Avoid blanket island removal that erases thin details. Duplicate-mask reuse is allowed only when source content has been checked unchanged; camera motion invalidates naive reuse.
5. Use edge refinement only after subject selection is correct. Full-frame or cropped/tiling inference must preserve dimensions and coordinate transforms. Do not load tracker and refiner simultaneously if that crowds AE out of VRAM. No unbounded GPU-to-system-memory fallback loops or silent auto-retry.
6. Deliver per-object grayscale PNG alpha sequences, or straight-alpha RGBA PNGs, with source-frame manifest. Keep the original RGB footage for color work. Use the matching FPS/source offset in AE and exactly the same precomp/remap/transforms for matte and picture. These are generated alpha/luma mattes, never native strokes.
7. Verify every output frame exists, dimensions match and alpha is nonempty when the subject is visible. Inspect start/middle/end, all correction frames and major motion/occlusion changes, plus full-speed playback on black, white and contrasting backgrounds. Numeric coverage checks flag suspicious frames; they do not prove correctness. Review fingers, hair, blades, black fabric, frame edges, halos, flicker and subject swaps.
8. Only then replace the exact failed matte in a NEW guarded edit revision through the designated TonyFX writer. Preserve user layers and prior matte media. Register the actual before/after proof; no artistic acceptance from technical PASS.

## Deferred validation, without delaying Claude

When Neural's current work reaches a completed milestone and its native/GPU lanes are free: generalize the shared script input contract; test standard SAM2 vs SAM2Anime on representative hands, dark clothing and motion/occlusion; test ViTMatte only on problematic edges. Cache downloads with pinned metadata/checksum and finite timeout outside inference, then run a short proof. Promote only what actually improves inspected frames and motion. This is a footage-specific suitability test, not an open-ended model benchmark or new editing/director task.

## Sources checked

- Meta SAM2 code/API/checkpoint license: https://github.com/facebookresearch/sam2
- Anime checkpoint/card: https://huggingface.co/Zarxrax/SAM2Anime
- Sammie developer documentation: https://github.com/Zarxrax/Sammie-Roto-2/wiki
- ViTMatte: https://github.com/hustvl/ViTMatte and https://huggingface.co/hustvl/vitmatte-small-composition-1k
- MatAnyone2: https://github.com/pq-yang/MatAnyone2 and its LICENSE.txt
- SAM2Matting: https://github.com/FudanCVL/SAM2Matting and its LICENSE
- VideoMaMa: https://github.com/cvlab-kaist/VideoMaMa

## Native experiment disposition

The installed TonyFX native UI experiment is not the selected roto workflow. One actual foreground stroke, tool shortcut and double-click were tested on a scratch clip. Subtraction, refinement, propagation and freeze were NOT validated. Scratch folder541/footage542/comp543/layer555 were removed by an exact guarded cleanup. A3E comp7/time0/selected540,538/tool9012 were restored, without saving over or discarding the dirty production project. Evidence: `.maintenance/20261026-tonyfx-native-ui/RESTORED_A3E_CONTEXT.json`. Do not resume UI testing from that handoff.
