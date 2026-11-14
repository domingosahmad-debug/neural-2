# Claude runtime lookup repair — 2026-10-22

The scheduled 02:15 Cairo direction was saved, but the native Claude director then failed before inference: `Claude Code runtime not installed.` The desktop app's data migration left `.user-data-left.claude_pzs8sxrjxfjjc` in its former packaged Roaming directory. Its official runtime exists under `AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc/claude-code/2.1.304/aed62990b91e/claude.exe`.

`app/claude_transport.py` now discovers that migrated runtime root alongside existing CLI/legacy roots. Added regression coverage for the migration marker and new location; all eight transport tests pass without model inference. Official CLI `auth status` confirmed the existing first-party Claude subscription login; no credentials were read or changed.

For the existing running companion, a directory junction at `AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude-code` points to `AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc/claude-code`. The legacy child did not exist. This restores its existing discovery function without copying executables, installing another CLI or restarting/reloading Neural. The target remains the official versioned runtime directory. Preserve this junction until the source finder patch is loaded normally; never recursively delete through it.

After verifying Claude's error state, no pending continuation watches and no active local job, sent exactly `continue` once through Neural. Same native Opus director and session `08d743a0-6ab0-4d99-b662-ee5c1567d9d2` retained. Immediate state starting; subsequent state working with no error. This verifies resumption, not edit completion or quota availability for the entire edit.

Claude Desktop was displaying the Code new-session view. Switched to the regular Claude view and dismissed its new-feature introduction. Existing recent chats, including Understanding Codex workflow and After Effects editing handoff template, became visible. No chat/profile data was reset or deleted. The UI was left in the regular chat view.

No edits to media/AE/current project, director provider selection, prior trial work or portable ZIP. Lumen's new backend still requires normal activation; this repair does not claim otherwise.
