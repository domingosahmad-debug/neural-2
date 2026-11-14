# Software design and implementation lens

Combine the useful EGM comprehension, design-critic and implementation-readiness questions in ONE bounded review, selected for the actual change:

- Can a new reader explain the requested user behavior and acceptance criteria without the author's unstated assumptions? Are unresolved decisions explicit?
- Does the plan match relevant real code and contracts, preserve data/session/ownership constraints, and reuse working features? Flag unsupported claims about tools, external systems and current behavior.
- Are the important failure cases and state transitions accounted for: concurrency, stale revisions, partial/unknown execution, cancellation/restart, persistence, identity, recovery and rollback? Review those relevant to the task, not a generic universal checklist.
- Can an implementer locate the affected call paths and verify the user-visible result? Do tests exercise the reported interaction and target container? For example a left-chat scroll test cannot establish stability of the right telemetry panel.
- Does the final evidence actually meet the plan? A focused implementation-versus-spec comparison can replace a new broad review. Build success, mock adapters and screenshots do not establish live editor/audio/native behavior.

For source-grounded definitions, the complete pinned upstream runtime is available at `C:/Users/TUF/.workflow-tools/project-goldfish/upstream/a119668d7dc5d558664ba711d4671d11fb7270a8/`. Useful selected sources: `agents/comprehension.md`, `agents/design_critic.md`, `agents/implementation_readiness.md`, `agents/codebase_details.md` and `resources/document_standards/implementation-readiness-standard.md`. Read only a relevant source when deeper rubric detail is needed. Do not activate the full orchestrator, copy all standards into every task or inherit its mandatory interactive gates.
