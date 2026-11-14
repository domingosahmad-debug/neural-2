# How Neural 2.0 works

## Moving parts

```
Electron desktop (NEURAL_STUDIO_2/desktop/main.cjs)
   └─ spawns  python -u bootstrap.py --port 0     → local HTTP service on 127.0.0.1 (random port, session token)
        ├─ web UI  index.html + *.js / *.css        → stations, notebook, review player
        ├─ production.py / production_gateway.py   → phase pipeline, routing, fallback, critique loop
        ├─ providers.py / providers_engine/*       → runs Claude, Codex, OpenCode and Antigravity CLIs as station workers
        ├─ native_lane.py                          → the single guarded writer into After Effects
        ├─ station_cli.py                          → command-line door for AI workers (events, results, wait)
        ├─ maintenance.py / local_ops.py           → health checks, locks, cleanup, local tasks
        └─ data/  (SQLite workspace, projects, logs, renders; git-ignored)
After Effects + TonyFX CEP panel  ⇄  Documents/ae-mcp-bridge/{ae_command.json, ae_mcp_result.json}
```

The service binds only to localhost. It protects every API call with a per-launch token, which it writes to `.desktop-service.json`. Never share that file.

## Stations (what you see)

| Station | Role |
|---|---|
| **Director** | Owns the edit: brief, creative plan and final decisions. Usually your strongest model (Opus, GPT Sol or Gemini high) |
| **Plan** | Scouts the footage and music, and reviews the director's plan |
| **Edit** | Builds the prototype and the full AE composition through TonyFX, and applies repairs |
| **Review** | Harsh frame-by-frame review plus a fresh-eyes "Goldfish" review |
| **Deliver** | Renders and exports |
| Relay | Local assistant (Qwen on your CPU) for quick questions and voice |
| Screening | Watch renders, leave timestamped notes |
| Debug | Service, provider and lock health |
| Manual Edit | Human-only. AIs never act here |
| Executive Director | Optional supervising seat, off by default |
| Director notebook | The director's running log and decisions |

## Phase pipeline (one revision)

`scout → plan → plan_review → prototype → prototype_review → build → render → harsh_review → goldfish_review → HUMAN_REVIEW`

Any review can send the work to **repair**, which loops back to Edit. Which station runs each phase:
- scout and plan_review run in **Plan**; plan runs in **Director**.
- prototype, build and repair run in **Edit**.
- prototype_review, harsh_review and goldfish_review run in **Review**.
- render runs in **Deliver**.

The supervisor phases are plan, plan_review, prototype_review, harsh_review and goldfish_review. These are where the director judges the work. The run ends at **HUMAN_REVIEW**: you watch it, then accept it or write notes for revision 2.

Run states you will see:
- WORKING, WAIT_MEDIA (waiting on an AE or render job) and QUESTION (needs you).
- BLOCKED, PAUSED and HUMAN_REVIEW.

## Model routing and fallback

`model_catalog.json` lists every seat: provider, model and effort. For each station you pick an ordered list in the UI. When a seat is unavailable, out of quota or failing, the gateway moves to the next one at a safe boundary. It never moves in the middle of an AE command.
- **Reserved director models:** opus, gpt-6.1-sol, gpt-6-sol and astra.
- **Recommended worker order:** free OpenCode models first, then Sonnet and Haiku, then Codex last.
- **No paid fallback:** Neural never switches you to a paid API or changes billing.

## Events (how AIs wait without burning tokens)

Workers and the director never poll in a loop. They call
`python station_cli.py wait --recipient Director` (or `events`), which blocks until a real completion event arrives. They read the result, then acknowledge it. This is the main cost-saving rule.

## The native AE lane (TonyFX)

- **One writer.** Exactly one station holds the AE lease at a time. The `tfx_skill_client.lock` file enforces this.
- **Guarded commands.** Each command is written to `ae_command.json`. The panel executes it in AE and writes `ae_mcp_result.json`, which includes `_servicedBy: "TonyFX"`.
- **Never replay UNKNOWN.** If a result is missing or ambiguous, the lane stops and inspects AE state. It never re-sends a command, because that could double-apply edits.
- **Editable output.** The build stays editable in AE: precomps, labelled layers and keyframes, not baked renders. You can always take over by hand.

## API (for tools and debugging, all localhost and token-protected)

`/api/workspace`, `/api/services`, `/api/editor`, `/api/production`, `/api/control`, `/api/debug`, `/api/events`, `/api/review`, `/api/review-media`, `/api/editor-media`.

## Knowledge and rules

- `NEURAL_STUDIO/knowledge/skills/*/SKILL.md` holds the editing skills: workflow direction, footage story flow, motion and transitions, typography, dialogue, music and sound, review and repair, export, AE editable assembly, TonyFX execution, and the accepted live-action and AMV pipelines.
- `NEURAL_STUDIO/shared/CURRENT_RULES.md` and `CURRENT_WORKFLOW_*.md` hold the current house rules.
- The other dated files in `shared/` are history from the source machine. Newer files override older ones.
