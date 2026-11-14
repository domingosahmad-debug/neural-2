"""Read-only presentation of execution facts; never schedules or approves work."""

def project_activity(paused, settled, pause_reason, stations, production):
    def result(state, label, reason):
        return dict(state=state, label=label, reason=reason)

    if paused:
        return result('paused' if settled else 'stopping',
                      'Paused' if settled else 'Pausing safely',
                      pause_reason or 'Paused by the user.')
    if any(row['state'] == 'unknown' for row in stations):
        return result('unknown', 'Outcome unresolved', 'An invocation has an unknown outcome. Reconcile its saved evidence before continuing.')
    run = production or {}
    state, phase = run.get('state'), str(run.get('phase', '')).replace('_', ' ')
    if state == 'BLOCKED':
        return result('blocked', 'Production blocked', run.get('error') or 'Open production details for the failed step and recovery evidence.')
    if state == 'HUMAN_REVIEW':
        return result('human_review', 'Ready for your review', 'Automated production gates finished. Open Review to inspect the saved cut; human acceptance is still required.')
    if state == 'WAIT_HUMAN':
        return result('needs_input', 'Your answer is needed', (run.get('question') or {}).get('text') or 'Open the current project decision.')
    waits = {'STEERING':'Applying your new direction', 'WAIT_MEDIA': 'Local media tools', 'WAIT_NATIVE': 'After Effects',
             'WAIT_TECHNICAL': 'Technical verification', 'WAIT_QUOTA_BOUNDARY': 'Safe provider handoff',
             'VERIFY_INTENT': 'Verification admission'}
    if state in waits:
        return result('waiting', 'Waiting · ' + waits[state], run.get('error') or 'Completion events advance this step. No model polling is needed.')
    active = [r for r in stations if r['state'] in ('running', 'queued', 'stopping')]
    if active:
        return result('running', 'Work active', ' · '.join(r['station'] + ': ' + r['state'] for r in active))
    if state in ('READY', 'DISPATCHING'):
        return result('queued', 'Preparing ' + (phase or 'next step'), 'Production is preparing the next invocation; no model is running yet.')
    if state == 'WORKING':
        return result('waiting', 'Reconciling ' + (phase or 'production'), 'No active provider is reported. Waiting for the saved outcome to be reconciled; this is not proof of ongoing model work.')
    if any(r['state'] == 'blocked' for r in stations):
        return result('blocked', 'Station blocked', 'Open the blocked station to inspect its saved failure.')
    if any(r['state'] == 'needs_review' for r in stations):
        return result('needs_review', 'Result awaiting review', 'A saved station result has not been reviewed. This does not mean a model is running.')
    return result('idle', 'Idle', 'No provider invocation or production step is active.')
