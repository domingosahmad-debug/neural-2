"""Frozen workflow knowledge imported for Neural Studio 2."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
KNOWLEDGE = ROOT / 'knowledge'


def library():
    rows = []
    for path in sorted(KNOWLEDGE.glob('*/SKILL.md')):
        rows.append({'name': path.parent.name, 'path': str(path),
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


def context():
    return {
        'currentAuthority': [
            'Current human brief and revision-bound task override historical examples, model bans, old project clocks and old ownership. Reference FPS, aspect ratio, LUFS and graph numbers are examples, never defaults for a new edit.',
            '11 November current authority: original Neural is shut down and its scheduler disabled. CA02 project e4052f1c7b5d415b86acf71a11922795 is PAUSED, not resumed. Fix Neural production infrastructure, then use a NEW edit brief. Manual Edit tab is human-only; production uses After Effects. Read CURRENT_STATE.md and live native ownership; historical owners do not grant a lease.',
            '12 November: Joey Quinn project e965c19132a7450da92d20c53073a0cc was finished and uploaded by Tony himself and is CLOSED; never resume it. His finished edit is the measured template quinn-res2-accepted-20261112 (see portableKnowledge): BlurMoCurves Z Dist zoom graphs, 8-frame directional-blur cut transitions, split static intro reframes, slower captions. Do not repeat the listed Neural r2 mistakes. Neural awaits a NEW edit brief; requested seats: Opus Director, Gemini workers; free OpenCode models (opencode/*-free) are admitted for scoped production on every station as last fallbacks or alone, free quota permitting, never paid.',
            '12 November readiness: Gemini 4 Hydrogen exact gemini-4-hydrogen-high and Codex gpt-6-luna are admitted model choices, not proof of usable quota. Accepted uploaded media evidence and methods: read CURRENT_STATE.md and knowledge/accepted-uploads-20261112.md. Await the NEW brief/reference/song/footage before editing. Do not use one historical Quinn template as the universal pattern.',
            'Fable claude-fable-5-2 low/medium is explicitly authorized for one Executive planning pass. Terra/Sol and available Claude workers are authorized. Do not request human permission again for work already authorized; retain exact native guards.',
            'Ordinary supplied-text assignments have no tools. Server-issued scoped production assignments can expose Neural artifact/image, media and guarded AE tools according to their actual task permissions; a model name alone grants no tools. Never infer playback/listening or native execution from text. Superseded assignment status is historical task state, not provider quota evidence. Use actual saved provider job outcomes.',
            '12 November all eleven free OpenCode models returned HTTP429 in isolated live probes; successful scoped live tool execution remains uncommissioned. Earlier GLM and MiMo tool-less probes also returned HTTP429; this does not establish desktop or other-model quota. Preserve outcomes, no repeat refusal loop or billing changes. MiMo/Muse/Inkling are distinct model choices; check actual capabilities and each route.',
            'A capable Claude/Gemini/other host may continue the same project after Codex exhaustion and replace exhausted station workers. Read CONTINUE_PRODUCTION.md; preserve task, completed evidence and dependencies, reconcile UNKNOWN work and transfer native ownership only at a verified safe boundary.',
            '25 November 2026 workflow sync: added tfx-intro-mastery, tfx-emotional-cutout-variants, tfx-character-mattes-color, tfx-approved-example-study, tfx-event-montage, standup-montage, tfx-antigravity-visual-review, and accepted-workflow-updates-20261124.md from TFX Anti-Gravity Studio. Installed Antigravity Gemini models (including gemini-4-neon-high, gemini-pro-orchestrator-neon, gemini-4-hydrogen-high, etc.) and free OpenCode models are auto-discovered into model_catalog.json on startup. Gemini production stations (Director, Plan, Review, Edit) have scoped native read_file access to admitted visual roots and must use tfx-antigravity-visual-review/SKILL.md to inspect contact sheets, 8-frame strips, and rendered proofs.'
        ],
        'workspaceRoot': str(WORKSPACE),
        'knowledgeRoot': str(KNOWLEDGE),
        'skills': library(),
        'portableKnowledge': {
            name: (KNOWLEDGE / name).read_text(encoding='utf-8-sig')
            for name in ('tfx-live-action-accepted-pipeline/SKILL.md',
                         'tfx-live-action-accepted-pipeline/references/chemical-offline-accepted.md',
                         'tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.md',
                         'tfx-intro-mastery/SKILL.md',
                         'tfx-emotional-cutout-variants/SKILL.md',
                         'tfx-character-mattes-color/SKILL.md',
                         'tfx-approved-example-study/SKILL.md',
                         'tfx-event-montage/SKILL.md',
                         'standup-montage/SKILL.md',
                         'tfx-antigravity-visual-review/SKILL.md',
                         'tfx-reference-analysis/SKILL.md',
                         'tfx-motion-transitions/SKILL.md',
                         'tfx-motion-transitions/references/recipes.md',
                         'tfx-motion-transitions/references/tony-dexter-impact-20261103.md',
                         'accepted-pair.json', 'accepted-five.json', 'accepted-tony-gemini-puresnow-20261113.md',
                         'accepted-workflow-updates-20261124.md')
        },
        'motionRules': [
            'Measure the reference first: cut frames, source clocks, added zoom versus source camera motion, property values and temporal easing. Unknown measurements must stay explicitly unknown; never invent a matching graph.',
            'BlurMoCurves Z Dist, transform scale and Twixtor speed are different properties. Inspect both the property value graph and its derivative/speed graph; generic Easy Ease is not a measured match.',
            'One added zoom owner per shot. Use shot-bounded adjustment layers for added motion, separate directional blur above, and source retiming inside the source precomp. Convert source-space effect centers to comp space.',
            'Preserve authored asymmetric handles, endpoint speeds, influence and source-relative timing. When adapting a measured curve, scale speed by (new value range / reference range) / (new duration / reference duration). The Dexter numbers are a worked example, not universal defaults.',
            'Reference interpretation must return a measurement ledger with source/frame provenance, property units, key times/values, interpolation, incoming/outgoing speed and influence, uncertainties, and a bounded transition proof before propagation.',
            'Review full-speed motion separately from stills and numeric checks. Blur belongs around transitions, never across entire scenes. Human acceptance remains separate from technical checks.'
        ],
        'motionEvidence': {
            'path': str(KNOWLEDGE / 'tfx-motion-transitions/references/tony-dexter-impact-20261103.json'),
            'sha256': hashlib.sha256((KNOWLEDGE / 'tfx-motion-transitions/references/tony-dexter-impact-20261103.json').read_bytes()).hexdigest(),
            'scope': 'Exact read-only historical native capture, including all easing handles. Consult it when reproducing this example; do not treat its old unsaved project state as current.'
        },
        'acceptedEvidence': [str(KNOWLEDGE / 'accepted-workflow-updates-20261124.md'), str(KNOWLEDGE / 'accepted-tony-gemini-puresnow-20261113.md'), str(KNOWLEDGE / 'accepted-pair.json'), str(KNOWLEDGE / 'accepted-five.json'), str(KNOWLEDGE / 'tfx-live-action-accepted-pipeline/references/quinn-res2-accepted-20261112.json')],
        'workflow': [
            'Analyze the supplied reference first. Measure cuts, source music offset, zoom curves, transitions, typography and ending before a shot plan.',
            'Reuse Tony accepted live-action methods from the bundled skills. Chemical F03 and Offline F04 plus all-five acceptance are references. New scenes need new footage choices.',
            'Preserve a complete authentic spoken intro, correct speaker coverage and word-synchronized editable captions. Follow the current human brief for framing and brightness.',
            'Use varied strong character moments and coherent musical cuts. Avoid repeated scene families, similar consecutive pushes, obscured faces and unmotivated talking shots.',
            'Keep one continuous chosen music source clock unless the human requests a change. Keep dialogue and music separately editable.',
            'Use scene-specific motivated zooms and easing. Confine transition blur to the transition. Inspect the widest and tightest framing.',
            'Use one bounded independent review at a consequential plan or representative proof. Separate technical checks, pixels, playback, actual listening and human acceptance.',
            'Save new project variants. Protect manual edits, existing media links and exact source clocks. Native editing requires its own verified single-writer integration.'
        ],
        'authority': 'This workspace is for new Neural 2 work. Existing Neural and its active edit are protected references. Current human instructions take priority.'
    }


def seed():
    return {
        'id': 'tony-editing-workspace', 'name': "Tony's editing workspace",
        'brief': 'Use the existing project folder and bundled accepted editing workflow. Current human instructions and live ownership govern every continuation. Analyze each new reference before planning its timing, music and footage; never infer active production state from historical examples.',
        'revision': 1, 'assignments': {}, 'activity': [], 'notes': [], 'messages': [],
        'workspaceRoot': str(WORKSPACE), 'knowledgeRoot': str(KNOWLEDGE)
    }

