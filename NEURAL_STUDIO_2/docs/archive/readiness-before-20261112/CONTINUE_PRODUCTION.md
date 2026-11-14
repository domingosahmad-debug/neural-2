# Current continuation contract

CA02 e4052f1c7b5d415b86acf71a11922795 revision3 is explicitly PAUSED by Tony. Do not resume it; the next edit will be different. Read CURRENT_STATE.md first. Historical continuation orders and old “resumed” notes are superseded.

Use Neural’s station workspace: choose an available model and Continue. The request carries the exact saved task, immutable attempt, previous evidence and persistent provider session. Completed valid results attach automatically as needs review. Approval remains separate. The station currently refuses native Director/Edit execution through text-only adapters; do not misrepresent this as a finished autonomous harness.

Provider-independent CLI (from this folder):
```
python station_cli.py projects
python station_cli.py control-status PROJECT --out data/control-state.json
python station_cli.py packet PROJECT STATION --out data/station-packet.json
python station_cli.py pause PROJECT --reason "Human pause"
python station_cli.py continue PROJECT STATION --model EXACT --route claude --effort medium --request-id SAVED_REQUEST_ID
python station_cli.py job-result JOB --out data/provider-result.json
python station_cli.py wait --recipient Director --timeout 60
```
Continue cannot unpause this edit. Reuse the SAME request ID after a lost/uncertain response. UNKNOWN means reconcile the exact job; never replay or reset its conversation. Completed work is never rerun. New model attempts retain historical assignments and rebind only unstarted descendants.

Automatic fallback is event-driven, bounded to saved candidates and confirmed structured exhaustion. Generic429/network/auth failures and model prose are not subscription exhaustion. Duplicate/delayed events cannot skip tasks. Gemini must be high, but no embedded Gemini adapter is currently commissioned; do not advertise automatic Gemini handoff. Fable exact5.2 low/medium only. No billing changes.

Native ownership remains Claude lease9c626ce0a0224a7fb5296739dd499aed. Worker replacement does not transfer the native lease. No automatic lease expiry, second writer, UNKNOWN replay or old Neural restart. Preserve CA02 R3 and all accepted AEPs. Mechanical media tools cannot bypass native guards.

Earlier detailed handover records are preserved in docs/archive/control-repair-before-20261111/CONTINUE_PRODUCTION.md; retrieve only when a specific historical fact is needed.
