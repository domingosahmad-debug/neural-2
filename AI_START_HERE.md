# For the AI assistant setting up or running Neural 2.0

You are helping a new owner install and run Neural 2.0 on their own Windows PC with their own AI accounts.

## Read in this order

1. `README.md`: what Neural is and the quick start.
2. `BEFORE_YOU_LAUNCH_CHECKLIST.md`: go through every line, run each check and fix failures before launching. `REQUIREMENTS.md` has the versions, links and hashes behind it.
   Details in `REQUIREMENTS.md`: check each item on this machine. Install what is missing, with the user's consent. Never enter passwords or keys for them; they sign in to each CLI themselves.
3. `SETUP.md`: run `Setup-Neural2.cmd -CheckOnly`, then `Setup-Neural2.cmd` (add `-Voice` if they want local voice or dictation).
4. `ARCHITECTURE.md`: stations, phases, routing, events and the AE lane.
5. `WORKFLOW_RULES.md`: the non-negotiable safety rules and the efficiency rules.
6. When a run starts: `NEURAL_STUDIO_2/AGENTS.md`, `NEURAL_STUDIO_2/knowledge/accepted-workflow-updates-20261124.md`, `NEURAL_STUDIO_2/knowledge/tfx-antigravity-visual-review/SKILL.md`, `NEURAL_STUDIO/shared/CLAUDE_WORKFLOW_HANDOFF.md`, `NEURAL_STUDIO/shared/CURRENT_RULES.md`, and the station's skill in `NEURAL_STUDIO_2/knowledge/` / `NEURAL_STUDIO/knowledge/skills/`.

## Important context

- The dated files and the project names are a historical log from the source machine. That includes `NEURAL_STUDIO_2/CURRENT_STATE.md`, `NEURAL_STUDIO/shared/*_2026*.md` and the project names in `AGENTS.md` (Dexter, Quinn, CA02, Pure Snow and so on). They show how the studio was used and corrected; they are **not** tasks for you. The new owner's brief wins.
- Paths like `C:/Users/TUF/...` in older docs refer to the source machine. On this machine, the repository root replaces `C:/Users/TUF/Documents/New project`.
- `NEURAL_STUDIO_2/examples/` holds sample scripts from a real run. They show how to drive the API; do not run them unchanged.
- Neural Studio 2 automatically discovers newly installed Antigravity (`agy`) Gemini high/orchestrator models (such as `gemini-4-neon-high`, `gemini-pro-orchestrator-neon`, `gemini-4-hydrogen-high`) and free OpenCode models into `model_catalog.json` on startup (`model_discovery.py`). If a seat errors as unknown or out of quota, pick an available model in the UI rather than editing code.
- Gemini production stations have scoped native `read_file` access to project/media/artifact directories so they can inspect actual `.png`/`.jpg`/`.mp4` contact sheets and 8-frame strips directly (see `tfx-antigravity-visual-review/SKILL.md`).
- Do not rebuild an AE or TonyFX replica application. The TonyFX CEP panel in `tonyfx-cep/` is the only bridge.

## Health check after setup

```
python NEURAL_STUDIO_2\check_services.py
python NEURAL_STUDIO_2\check_events.py
```
Then launch the app, open **Services** and confirm each installed provider reports as ready.
