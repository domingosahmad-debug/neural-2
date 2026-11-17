# Setup

Keep the folder layout exactly as cloned. `NEURAL_STUDIO_2` finds `NEURAL_STUDIO` and `tonyfx-cep` as its siblings.

1. **Clone** the repository to a path without special characters, for example `C:\Neural2`:
   `git clone https://github.com/domingosahmad-debug/neural-2.git C:\Neural2`
   Or on the GitHub page click **Code → Download ZIP**, right-click the ZIP → **Properties** → **Unblock**, then extract it. Then work through [BEFORE_YOU_LAUNCH_CHECKLIST.md](BEFORE_YOU_LAUNCH_CHECKLIST.md).
2. **Install the prerequisites** in [REQUIREMENTS.md](REQUIREMENTS.md): Python 3.12+, After Effects, ffmpeg and at least one AI CLI.
3. **Run the setup:** double-click `Setup-Neural2.cmd`, or run `Setup-Neural2.cmd -Voice` for the local models as well. You can run it again at any time; it skips what is already installed.
4. **Check:** run `Setup-Neural2.cmd -CheckOnly`. Every core line should say `OK`.
5. **CEP debug mode** (one time, needed for the unsigned TonyFX panel). In a normal PowerShell, set the value for your CSXS version (AE 2024–2026 use CSXS.11 or CSXS.12):
   ```powershell
   foreach ($v in 11,12) { New-Item -Force "HKCU:\Software\Adobe\CSXS.$v" | Out-Null; Set-ItemProperty "HKCU:\Software\Adobe\CSXS.$v" PlayerDebugMode 1 }
   ```
   Then, in After Effects, go to **Edit → Preferences → Scripting & Expressions** and enable **Allow Scripts to Write Files and Access Network**. Restart AE and open **Window → Extensions → TUF AE Command Center**. The panel exchanges commands through `Documents\ae-mcp-bridge`.
6. **Sign in to the AI CLIs** in a terminal, once each, with your own accounts:
   ```
   claude
   codex login
   opencode auth login
   agy
   ```
7. **Launch** **Neural 2.0** from the desktop, or run `NEURAL_STUDIO_2\Launch-Neural-2.cmd`. Open **Services** and refresh. Each installed CLI should show as ready.
8. **First edit:**
   1. In **Director**, create a project.
   2. Attach your footage folder, music and any references.
   3. Write the brief: duration, aspect ratio, mood and must-have moments.
   4. Start production.
   5. Keep After Effects open with the TonyFX panel visible.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Window does not open | `NEURAL_STUDIO_2\runtime\electron.exe` is missing. Rerun setup |
| "Service failed to start" | Run `python NEURAL_STUDIO_2\bootstrap.py --port 0` in a terminal and read the error. Usually a missing pip package |
| Provider shows unavailable | The CLI is not on PATH or not signed in. Run it once in a terminal |
| AE commands time out | The TonyFX panel is not open, AE is showing a modal dialog, or `Documents\ae-mcp-bridge` is missing |
| Gemini seats skipped | Install Antigravity and run `agy` once |
| No voice or dictation | Run setup with `-Voice` |

Runtime data (projects, the database, logs, renders) lives in `NEURAL_STUDIO_2\data\`, which Git ignores. Back it up yourself if you need to.
