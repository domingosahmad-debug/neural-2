> Expanded by shared/ALL_PROVIDER_CONVERSATION_CONTINUITY_20261024.md: persistent station adapters and provider switch-back guards are now source-tested too. Activation remains pending; historical limitations below describe the earlier audit, not the expanded source implementation.

# Director session continuity repair — 2026-10-24

Status: SOURCE TESTED; ACTIVATION PENDING. The running companion has NOT been restarted, injected or hot-reloaded. The active Sol LUZ ROJA R04 edit remains its sole editor. Do not interrupt it, send duplicate directions, or touch AE to activate this maintenance.

## Verified fault
`CommandService._bound_context()` replaced the Codex thread whenever its previous input exceeded 48,000 tokens, on human directions AND internal local/native completion wakes. It saved the prior full app transcript/checkpoint but passed only three truncated human directions, three short assistant notes, three assignments and shared continuity files to a new backend conversation. That was not the persistent conversation Tony requested. Archives show six automatic replacements between 10:35:59 and 10:49:54 UTC during R04; the 10:32:59 entry was the new revision direction. This can weaken continuity and adds repeated orientation; this audit does not prove it caused every artistic failure.

## Source change
Input size no longer clears thread_id, token usage or connection state. Human turns, event continuations, reconnects and normal restart resume the same provider conversation within the selected workflow. Provider-native context management/compaction handles finite context; no compaction/status model loop is added. Local evidence/checkpoints supplement history. Snapshot usage_guard now advertises persistent_provider_thread and no arbitrary 48k context reset.

Workflow isolation and incompatible dynamic-tool-schema migration are preserved and still recorded separately. Old archive/checkpoint files remain intact. We have not merged old histories into a fabricated new history or selected an older thread over the active writer.

## Validation
69 tests passed: command lifecycle 41; continuity/staffing 4; local-ops integration 6; native director 18. Python syntax passes. Regression coverage verifies same thread for high-input human and internal turns, normal-restart resume, and inference-free state reads. Provider execution is mocked: live compaction, desktop sidebar behavior and active-session continuity AFTER activation are not newly verified.

## Safe activation
After the current edit's director/local/native/completion work safely hands off, close Neural normally and reopen it. Leave After Effects and saved/manual work intact. A frontend refresh alone does not load Python. Prior programmatic companion restart was rejected by automatic approval review; do not try an alternate reload/injection. No pause/resume/model change or restart was performed by this audit. On normal reopen, check the current thread is retained, then verify one naturally authorized continuation keeps it. Do not launch a test model turn just to prove it.

## Other models — honest scope
Native Claude DIRECTOR already uses its saved official CLI session (--resume). Lumen trial editor also retains its provider session for its trial. Ordinary text-only station workers currently run separate bounded task sessions, including Claude's --no-session-persistence. They receive frozen station/workflow/peer/correction memory and results, but that is NOT a persistent personal provider conversation across jobs. This patch does not claim to have implemented all-provider worker sessions. Provider/workflow/role isolation, concurrent ownership and frozen assignment authority must be retained when extending those workers; never blindly reuse a single session for parallel unrelated jobs. Shared files do not create identical minds or retrain weights.

## Files
app/command_service.py; tests/test_command_service.py; shared/STATION_ROUTING_AND_MEMORY.md.
Backup: .maintenance/20261024-director-session-continuity-before.
