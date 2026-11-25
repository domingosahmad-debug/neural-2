# Neural 2.0

> **AI assistant setting this up: open [BEFORE_YOU_LAUNCH_CHECKLIST.md](BEFORE_YOU_LAUNCH_CHECKLIST.md) and work through it top to bottom.** It covers unblocking the download, every tool to install, the sign-ins, setup and the final checks. The person you are helping only needs to sign in to their own accounts and approve installs.

Neural 2.0 is a local AI editing studio for Adobe After Effects. You give it a creative brief and your footage and music. A crew of AI models then plans, prototypes, builds, visually reviews, and renders the edit inside your own After Effects. Every AE command goes through one guarded native bridge, called TonyFX (`tonyfx-cep/`). You approve the final result.

- **Website:** https://domingosahmad-debug.github.io/neural-2/
- **Repository & ZIP:** https://github.com/domingosahmad-debug/neural-2

It runs entirely on your PC. The AI models are the CLIs you install and sign in to with **your own** accounts: Antigravity (for Gemini 4 Neon, Orchestrator, Hydrogen, Carbon, Flash), Codex, OpenCode (free models), and Claude Code. Neural automatically discovers newly installed Antigravity and OpenCode models into `model_catalog.json` on startup, and never stores or shares keys.

## What's included in the updated Neural 2.0 package
- **22 editing & QA skills** (`NEURAL_STUDIO_2/knowledge/` & `NEURAL_STUDIO/knowledge/skills/`), including `tfx-antigravity-visual-review` (pixel-by-pixel inspection of contact sheets, 8-frame source strips, and renders via native `read_file`), `tfx-intro-mastery`, `tfx-emotional-cutout-variants`, `tfx-character-mattes-color`, `tfx-approved-example-study`, `tfx-event-montage`, `standup-montage`, and `accepted-workflow-updates-20261124.md`.
- **Automatic model discovery** (`NEURAL_STUDIO_2/model_discovery.py`) so Gemini 4 Neon, Orchestrator Neon/Carbon/Argon, Hydrogen, and free OpenCode models appear automatically.
- **Native visual pixel review** inside Neural stations (`Director`, `Plan`, `Review`, `Edit`) for Gemini models via scoped `read_file`.
- **Bundled TonyFX CEP bridge** (`tonyfx-cep/`) installed automatically by `Setup-Neural2.cmd`.

## Download

On https://github.com/domingosahmad-debug/neural-2 click **Code → Download ZIP** (or `git clone https://github.com/domingosahmad-debug/neural-2.git C:\Neural2`). Before extracting the ZIP, right-click it → **Properties** → **Unblock**.

**Using an AI to set it up?** Give it [BEFORE_YOU_LAUNCH_CHECKLIST.md](BEFORE_YOU_LAUNCH_CHECKLIST.md). It lists every requirement with a check command and the expected result.

## Quick start (Windows 10/11)

1. Install the third-party tools in [REQUIREMENTS.md](REQUIREMENTS.md). At minimum you need Python 3.12+, After Effects and one AI CLI.
2. Double-click `Setup-Neural2.cmd`. It installs the Python packages, downloads the Electron runtime, creates the AE bridge folder, installs the TonyFX AE panel and adds a **Neural 2.0** desktop shortcut.
   - Add `-Voice` to also get the local voice, dictation and Relay models (about 1.5 GB): `Setup-Neural2.cmd -Voice`.
   - `Setup-Neural2.cmd -CheckOnly` only reports what is missing.
3. Turn on CEP debug mode (see [SETUP.md](SETUP.md), step 5). Open After Effects, then go to **Window → Extensions → TUF AE Command Center**.
4. Sign in to each AI CLI once in a terminal: `claude`, `codex login`, `opencode auth login`, `agy`.
5. Open **Neural 2.0** from the desktop. Go to **Services** and check that your providers show as ready. Then go to **Director**, describe your edit and start it.

## Where to go next

| Read | For |
|---|---|
| [BEFORE_YOU_LAUNCH_CHECKLIST.md](BEFORE_YOU_LAUNCH_CHECKLIST.md) | Every requirement with a check command, for your AI to verify before launch |
| [SETUP.md](SETUP.md) | Step-by-step install and troubleshooting |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Every external tool, model and plugin, with versions, links and hashes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the stations, phases, routing, events and the AE bridge work |
| [WORKFLOW_RULES.md](WORKFLOW_RULES.md) | The house rules that make the edits work |
| [AI_START_HERE.md](AI_START_HERE.md) | Read order for your AI assistant |
| `site/index.html` | The Neural 2.0 overview website (open it in a browser) |

## What is in this repository

```
NEURAL_STUDIO_2/      The Neural 2.0 app (Python service + Electron desktop + web UI)
NEURAL_STUDIO/        Shared runtime modules, rules (shared/) and editing skills (knowledge/)
tonyfx-cep/           TonyFX After Effects CEP panel (native bridge into AE)
Setup-Neural2.ps1     One-shot installer (.cmd wrapper alongside)
requirements.txt      Python packages for the service
*_MASTER_*.md         Long-form editing context and accepted recipes
```

Excluded on purpose:
- The Electron binary and the local models. They are too large, and they are third-party, so Setup downloads them.
- All runtime data, databases, logs, session tokens and media.
- The source machine's footage and AE projects.
