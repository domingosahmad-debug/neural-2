# Entering the Neural team — any provider/model

1. Read the current human-authorized task's START_HERE.md/TASK.json. No task means remain idle.
2. Read TEAMWORK_PROTOCOL.md, STATION_ROUTING_AND_MEMORY.md and the station START_HERE/HANDOFF/CONTRACT. The selected workflow and current human corrections override historical artistic recipes.
3. Read the supplied current team snapshot and relevant skill contents. Understand the common goal, your bounded part, other owners, existing results and previous failed approaches before acting. Request additional earlier-edit memory from the director if required; do not ask the human to reteach available knowledge.
4. Report actual tools and missing capabilities. The director can assign you to any station but cannot give your adapter unsupported listening, playback or native tools. A manual kit is portable instructions/data, not a provider connection.
5. Preserve teammates' work, original sources and all paused projects. Return the station's required output, evidence, uncertainty and help needs. Stop inference at a terminal result. The director routes any replacement through a fresh, scoped handoff after confirming execution ended.

Read-only shared state/recall: GET /api/team and /api/team/recall. Provider-independent orientation: GET /api/team/bootstrap?station=analysis. With authorized local file access, read data/team/<workflow>/projects and the scoped mistake ledger. Prior outputs are memory/evidence, not reusable edited scenes. Future assignments reuse this knowledge even if your provider starts a fresh chat.

Without the app running, use `python tools/team.py status`, `python tools/team.py recall "quote timing" --station sound-design`, or `python tools/team.py bootstrap --station analysis`. These read the same persistent memory and never start a model/job. Execution status is a recorded snapshot, not proof a remote worker stopped. When the app is available, findings go through its single-writer /api/team/note endpoint; do not race other agents by rewriting shared records directly.
