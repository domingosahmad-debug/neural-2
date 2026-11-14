# Workflow rules (the things that make the edits work)

These rules are distilled from the source studio's operating policy. Your own brief and corrections always override them.

## Safety: never break these

1. **One native AE writer.** Only the station holding the lease sends TonyFX commands. Never run two AE instances, and never use a second automation bridge.
2. **Never replay an UNKNOWN command.** If you are unsure whether a command ran, inspect AE first.
3. **Never delete locks by hand** while a run is live. Use Debug → maintenance.
4. **Manual Edit is human-only.**
5. **No billing or provider changes, and no paid fallback.** OpenCode seats stay on free models unless the owner says otherwise.
6. **Never print or commit secrets.** That covers `.desktop-service.json`, tokens, cookies and CLI credentials.
7. **Report AE crashes or hangs to the human immediately.**

## Working efficiently

- Read the current task, the station packet and the relevant skill first. Retrieve only the evidence needed for a specific uncertainty.
- Wait with `station_cli.py wait`, which uses real completion events. Never poll models on a timer or generate activity for its own sake.
- Use deterministic scripts for mechanical work. Save raw evidence (logs, frames, probes) to disk and quote only what decides the question. Never silently truncate decisive evidence.
- Reuse still-current proof. Do not repeat an unchanged review.
- Save a compact checkpoint at each milestone: objective, human decisions, exact project, run and job IDs, open defects, limits and next action.
- Use strong models for direction, architecture and hard diagnosis. Give bounded tasks to cheaper workers only when the result replaces director work.

## Review

- **Harsh review** checks frame by frame against the brief and the skills: timing on beats, caption legibility, transition cleanliness, colour continuity, no black or frozen frames, and audio levels.
- **Goldfish review** is one fresh, read-only reviewer with no prior context. It judges the representative proof as a first-time viewer would. Allow at most one targeted recheck of a changed blocker; do not loop on clean rounds.
- Technical tests, sampled pixels, full-speed playback, actual listening and **human acceptance** are separate gates. Only the human accepts.

## Creative defaults

- Live-action character and music edits (TV or film footage): follow `knowledge/skills/tfx-live-action-accepted-pipeline`. That means story-first footage flow, beat-locked cuts, Twixtor ramps on impact moments, stylized caption censorship, and restrained Sapphire glow and warp transitions.
- Anime AMVs: follow `knowledge/skills/tfx-amv-accepted-pipeline`. Keep anime methods separate from live-action ones.
- New projects make new footage decisions. Never reuse a completed edit's scenes as content.
- Keep the AE build editable and labelled so a human can take over at any layer.
- If a plugin or font is missing, substitute natively and state it in the plan.

## Verify and stop

For completion checks, use the smallest sufficient proof, report pass, fail or blocked honestly, and stop once the requested proof is complete (`knowledge/skills/verify-and-stop`).
