# Optional Executive Director

This station is above Director visually and outside the five production stages. It is OFF by default per project. Enable it only on explicit human request or through the manual node button. Enabling merely opens the station; it never starts inference, schedules a timer, or changes provider ownership.

Role: one bounded planning pass. Read the exact human brief and accepted workflow; verify actual host capabilities/quota; allocate stations/models, task dependencies and acceptance conditions; advise Director, return one result, then stop. Do not edit media, run the other workers, perform native AE actions, repeat reviews or poll for progress. The normal Director handles production after this handoff. Any AI can consume the portable task; custom names do not require registration. A model name is not authentication or evidence that an executable route exists.

UI: Workflow -> Executive Director -> Enable station. Select a catalog suggestion or type any model. Enter the planning request and Create and download planning task. Return exact resultTemplate JSON with a summary and allocationPlan. Import, review, approve evidence, then Apply plan. Apply creates/REPLACES matching production station handoffs and a Director notebook entry; it does not launch external AIs. It works once per approved plan. Download each station task from Routing. Dependency assignment IDs are frozen; predecessor evidence must be approved before a dependent result can be accepted. Independent tasks may be handed off concurrently when the host/hardware permits. Completion events, not model timers, wake the next owner.

CLI (from this directory):

    python station_cli.py projects
    python station_cli.py executive-enable PROJECT_ID
    python station_cli.py executive-task PROJECT_ID --model "Any model" --task "Exact bounded planning request"
    python station_cli.py packet PROJECT_ID "Executive Director"
    python station_cli.py result RESULT.json
    python station_cli.py executive-disable PROJECT_ID

Only run executive-enable when the human explicitly wants it enabled. The human can inspect/apply through the UI. For JSON templates use the packet's exact IDs/revision/schema. allocationPlan must have 1–5 unique stations from Director, Plan, Edit, Review, Deliver in dependency order. Each row:

    {"station":"Director","model":"Actual chosen host/model",
     "task":"Bounded assignment","acceptance":"Evidence required",
     "dependsOn":[],"availabilityEvidence":"Actual quota/capability check, or explicitly UNVERIFIED"}

dependsOn uses earlier station names. Cycles/duplicate station allocations, stale/mismatched results and premature dependent results are rejected. Disabling invalidates pending Executive handoffs; late results cannot activate anything. Approved plan history remains accessible. Production does not wait on an unused Executive station.

The app currently has no live external quota API or provider-launch integration. Its catalog is a snapshot. Do not claim that Fable, Astra or any other model is available based on its typed name. Verify via that host's actual tools, use a known capable route, or clearly return an unverified suggestion for human review. Never run repeated refusal loops or automatically spend premium quota.

Evidence: EXECUTIVE_PROOF.json covers default-off, explicit enable, portable packet, cycle/approval/dependency guards, one-shot apply, disabling and late replies. EXECUTIVE_DESKTOP_PROOF.json covers actual desktop UI flow. These tests use synthetic plans and never invoke an external provider.
