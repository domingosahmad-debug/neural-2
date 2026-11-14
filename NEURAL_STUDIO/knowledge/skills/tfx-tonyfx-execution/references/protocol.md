# Verified local bridge contract
Historical local bridge directory: C:/Users/TUF/Documents/ae-mcp-bridge.
Request ae_command.json; result ae_mcp_result.json. Recheck installed version rather than assuming archived TonyFX v0.60.0 or AE2023 is current.

Request schema:
```json
{"id":"unique-uuid","command":"runScriptFile","args":{"scriptPath":"C:/absolute/task.jsx"},"timestamp":"UTC ISO8601","status":"pending"}
```
Refuse an existing pending/running request. Publish the complete JSON by atomic replacement. TonyFX owns its own execution lock and processed-ID ledger. Our client lock coordinates only copies of this helper; it cannot guarantee exclusivity against unrelated producers. Exclusive human/agent ownership remains necessary.

Match result._commandId exactly. Inspect result.ok/error and the script's own report; absent or differently shaped success fields require interpretation of the installed contract, not assumed success. Do not read a previous command's output as this command's success.

Timeout is an UNKNOWN completion state, especially for native renders. Do not reset pending/running or delete lock files. A retry may duplicate side effects even with a fresh command ID. Reconcile first.

Local command examples (only in an authorized editing task):
```
python scripts/bridge.py status --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge
python scripts/bridge.py dispatch task.jsx --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge --dry-run
python scripts/bridge.py dispatch task.jsx --bridge-dir C:/Users/TUF/Documents/ae-mcp-bridge --wait-seconds 30
```
If the wait expires, use status and inspect the recorded ID; do not rerun dispatch. Existing authorizations do not justify touching another worker's busy bridge.
