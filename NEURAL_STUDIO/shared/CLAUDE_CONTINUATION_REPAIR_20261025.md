# Claude continuation repair — 2026-10-25

Tony explicitly authorizes fixing Neural and resuming Claude on the two NEW Bleach Bankai edits in data/bleach-bankai-two-edits-20261025. Preserve the saved native Claude session 08d743a0-6ab0-4d99-b662-ee5c1567d9d2, old LUZ ROJA R13 and paused Blender work. No replacement director is authorized.

Diagnosis: the native director had an absolute 1800-second process timer, which killed a productive session. Its terminal stopped result was safe to reconcile, but the production board was still tied to an earlier LUZ ROJA direction; the guard silently returned without a current-task continuation.

Fix: native Claude now uses a 30-minute INACTIVITY budget refreshed only by actual tool/text events. Quota/init/diagnostic heartbeats do not reset it. Human Stop, owned process termination, step bounds, unknown-result stops and same-session preservation remain. Other worker providers retain absolute limits. Runtime metadata exposes the mode and last progress. One event-bound current-direction checkpoint reconciliation now handles missing/stale boards on confirmed stopped timeouts; repeated failure alerts instead of looping. New directions clear stale review-ready outcome labels.

Native prompt requires binding current project/direction checkpoints before expensive analysis and reusing completed source analysis. Tests cover activity beyond the wall budget, inactivity/metadata/Stop, stale/missing board recovery, pause, unknown ownership, older-direction results and same-session continuation. Targeted suites passed: provider runtime29, production guard16, native director18, command service48 (111 tests). No live model inference in tests.

Source backups: .maintenance/20261025-claude-continuation-fix. Normal idle Neural close/reopen activates the new modules. Never hot-inject modules or restart an active edit. Read STATE, DESIGN, REFERENCE_STUDY and completed analysis reports; do not rebuild/re-extract them merely due to the timeout.

Current resumed task must bind project36aac849241c4410b51124a167943c47 and its own checkpoint revision; do not inherit the old LUZ ROJA acceptance. Claude remains creative/native director. Helpers remain bounded and mechanical work uses local operations with real completion watches.
