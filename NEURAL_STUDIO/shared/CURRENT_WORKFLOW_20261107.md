# Current Neural workflow (7 Nov 2026)

One concise entry. Older handoffs (AUTOMATIC_EFFICIENCY_POLICY_20261103, GOLDFISH_NEURAL_WORKFLOW_20261103) still apply; this adds what changed. Current human scope, pauses and live ownership always win.

## Roles
- **Director (oversight mode, default `oversight_mode: true` in data/command/DIRECTOR_POLICY.json).** Plans, assigns exact bounded tasks, reviews evidence, decides. Tools: Read/Glob/Grep and `python tools/neural_cli.py` only; commands are listed in shared/OVERSIGHT_DIRECTOR_GUIDE.md (status, assign, dispatch, watch, accept/reject, production, channel/recall, team-message). No Write/Edit/PowerShell/shell/web. Fewer turns per run. Full replies are saved under data/command/cli-replies/; the director sees compact JSON and reads the saved file only when a detail matters. After a resume the packet is compact; data/continuity/LATEST.json holds the full one.
- **Workers.** Opus is never a worker. Executors with tools: Claude Sonnet/Haiku via `assign --executor sonnet|haiku` (build_executor, runs in data/projects/<id>/work, absolute-path Bash allowlist, deny rules on app/tests/shared/data/command/bridge; rules are passed on the argv and have not been proven live). Gemini 3.8 Flash is NOT wired as a station executor (use the Lumen route). Each has its own persistent session. Only the owner of the single native AE lease (`EDITOR_LOCK`/`owns_editor`) touches After Effects; never replay UNKNOWN or pending native commands.
- **Gemini is available for bounded workers and reviews. Tony can explicitly select Gemini 3.8 Flash High as director. It is excluded from automatic succession.** See [current startup](START_HERE_NEURAL.md).

## Fresh review (Goldfish)
- Providers: Codex, native Claude, free OpenCode (exact `opencode/*-free`, cost 0), Gemini (plan mode). Review agents get no write or shell permission; this is enforced in the launch config and tested. Gemini plan mode is not a proven sandbox.
- `critic_panel`: at most 2 harsh critics (target `critic`: 1 or 2, distinct profiles, same target hash), then at most one changed-blocker recheck for the panel. `critic_panel.aggregate` is deterministic; it writes one compact report to data/critic-panels/. Disposition is changes_requested, incomplete or no_supported_blocker_found. Approval is always `never`. No finding is not approval.
- A modality a provider cannot verify (for example still images for non-Codex) is NOT RUN, not a text-only pass.
- Technical tests, sampled pixels, full-speed motion, actual listening and human acceptance stay separate.

## Efficiency
- Noisy tests/searches/builds: `python tools/token_shell.py --filter FILTER -- EXECUTABLE ARGS` (all tool-equipped lanes; the Claude lanes also use the selective RTK hook on Bash). Raw evidence and exit codes survive; failures stay raw.
- Completion checks and validation-only work: apply `knowledge/skills/verify-and-stop/SKILL.md` (smallest sufficient proof, reuse matching results, pass/fail/blocked, then stop).
- Compact replies: report results, IDs and decisions briefly. Never compress code, commands, guards, source clocks, identifiers, negations or evidence.
- End inference while a watched job runs; poll nothing with a model.
