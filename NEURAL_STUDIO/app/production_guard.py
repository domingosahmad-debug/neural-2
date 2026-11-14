"""Turn-end requirement reconciliation, triggered by actual director completion.

One recovery per unchanged work state; real worker completions remain unlimited.
No status read, startup, timer, or alert acknowledgment can start inference.
"""
import hashlib
import json
import re
import threading
from attention import AttentionStore
from production import ProductionBoard


def notify(service, key, title, detail, kind='needs_attention'):
    row = AttentionStore(service.root).publish(key, title, detail, kind)
    service.saved['production_outcome'] = {'status': kind, 'title': title, 'detail': detail, 'alert_id': row['id']}
    service._persist()

AUTO_RETRY_FAILED_SENDS = False  # failed sends must never auto-retry
ANNOUNCED_LIMIT = 4
_ANNOUNCE = re.compile(r"\b(next,? i(?:'|\u2019)ll|next i will|i(?:'|\u2019)ll now|now i(?:'|\u2019)ll|i(?:'|\u2019)m going to (?:build|render|apply|run|fix|start|continue|make)|next step|next up|then i(?:'|\u2019)ll)\b", re.I)


def work_fingerprint(plan, direction):
    # Wording, todo/working toggles and blocker rewrites are not new work.
    pending = sorted(s['id'] for s in plan['steps']
                     if s['status'] not in ('verified', 'awaiting_review') and s['gate'] != 'human')
    return hashlib.sha256(json.dumps({'direction': direction, 'revision': plan['revision'],
        'project_id': plan.get('project_id'), 'pending': pending}, sort_keys=True).encode()).hexdigest()[:32]


def _announced_continue(service, direction):
    """A COMPLETED turn ended by announcing its next action while nothing runs or is watched.
    Queue one bounded continuation instead of idling. Caller holds service.lock."""
    if not direction:
        return False
    msgs = service.saved['leader'].get('messages') or []
    last = next((m for m in reversed(msgs) if m.get('role') == 'assistant'), None)
    if not last or not _ANNOUNCE.search(str(last.get('text', ''))[-1500:]):
        return False
    jobs = service.runtime.jobs()
    local = getattr(service.runtime, 'local_ops', None)
    if any(j['status'] in service.runtime.active_states for j in jobs) or (local and local.snapshot()['active']):
        return False  # the existing unwatched-work alert handles running work
    if hasattr(service, '_handoff_native_pending') and service._handoff_native_pending():
        return False
    plan = ProductionBoard(service.root).snapshot().get('plan')
    if plan and plan.get('direction_id') == direction and not plan.get('needs_update'):
        fingerprint = work_fingerprint(plan, direction)
        recovered = service.saved.setdefault('production_recoveries', [])
        if fingerprint in recovered:
            return False  # finished() reports the shared stalled state below.
        service.saved['production_recoveries'] = (recovered + [fingerprint])[-40:]
    counts = service.saved.setdefault('announced_continuations', {})
    used = counts.get(direction, 0)
    if used >= ANNOUNCED_LIMIT:
        notify(service, 'announced-stalled:'+str(direction), 'Director keeps stopping mid-task',
               'The director ended its turn announcing a next step '+str(used+1)+' times without doing it. Automatic continuation stopped; send a direction to resume.')
        return False
    counts[direction] = used + 1
    key = 'announced:'+hashlib.sha256((str(direction)+str(last.get('id'))).encode()).hexdigest()[:24]
    service.saved['watches'][key] = {'status': 'ready', 'kind': 'production', 'job_status': 'ANNOUNCED_NEXT_STEP',
        'detail': 'You ended your turn announcing a next step ("'+str(last.get('text', ''))[-300:].strip()+'") with no running job and no registered watch. Do that step now and keep working on the same authorized human task. End a turn only when a real job runs with its completion watch registered, a human decision truly blocks all other work, or the edit is finished and registered.'}
    service.saved['production_outcome'] = {'status': 'recovering', 'title': 'Continuing the announced next step', 'detail': service.saved['watches'][key]['detail']}
    service._persist()
    return True


def _timeout_checkpoint_recovery(service, direction, timeout):
    """One event-bound reconciliation of the current brief, never the old plan.

    Called only after a confirmed stopped timeout, not by status reads. The
    preserved conversation decides whether the latest direction is a task or a
    question; no historical project/acceptance is adopted here.
    """
    if not direction:
        notify(service, 'timeout-no-direction', 'Claude checkpoint needs reconciliation',
               'The stopped timeout has no current human direction. Saved session is preserved; no historical task was resumed.')
        return False
    if any(j['status'] in service.runtime.active_states for j in service.runtime.jobs()) or (getattr(service.runtime, 'local_ops', None) and service.runtime.local_ops.snapshot()['active']):
        notify(service, 'timeout-unwatched:'+direction, 'Running work needs a completion handoff',
               'Claude stopped before binding current checkpoints. An existing worker/local job is active; reconcile its ownership and exact completion watch. No second worker was started.')
        return False
    native = service._handoff_native_pending() if hasattr(service, '_handoff_native_pending') else None
    if native:
        notify(service, 'timeout-native:'+str(native), 'Native execution needs reconciliation',
               'Existing TonyFX command '+str(native)+' is still unresolved. No command or competing editor was launched.')
        return False
    attempts = service.saved.setdefault('checkpoint_timeout_recoveries', [])
    if direction in attempts:
        notify(service, 'timeout-checkpoint-stalled:'+direction, 'Claude has not bound the current task checkpoints',
               'One same-session checkpoint reconciliation already ran. The current board is still missing/stale; technical help is required instead of another usage-consuming loop. '+timeout['folder']+'/RESULT.json')
        return False
    service.saved['checkpoint_timeout_recoveries'] = (attempts+[direction])[-40:]
    key = 'timeout-checkpoint:'+direction
    service.saved['watches'][key] = {'status':'ready', 'kind':'production', 'job_status':'CURRENT_DIRECTION_CHECKPOINT_REQUIRED',
        'detail': 'The previous Claude process is confirmed stopped after a local time/inactivity limit, NOT an allowance refusal. Continue the SAME saved Claude conversation. Read '+timeout['folder']+'/RESULT.json, shared/LATEST_DIRECTOR_DIRECTION.md and the current task STATE/design/analysis outputs. The production board still belongs to an older direction or is missing; do not resume that old project or copy its approval. First reconcile the latest human scope: if it is a production task, bind its actual project and unfinished checkpoints via /api/production/update before further expensive work; if it was only a question, answer it without reviving historical edits. Reuse completed analysis and preserve partial native state. Inspect exact current command/results; never replay a command. Work on one bounded milestone, save STATE/checkpoints, and end inference while a registered real completion watch owns waiting.'}
    service.saved['production_outcome'] = {'status':'recovering','title':'Reconciling current task checkpoints','detail':service.saved['watches'][key]['detail']}
    service._persist()
    return True


IDLE_WAKE_LIMIT = 2  # consecutive wakes with no job-state change before a stall notice
IDLE_GRACE_SECONDS = 90  # debounce: a human message or new work during this window cancels the wake


def _idle_watchdog(service, plan, direction):
    """Turn ended authorized with no watch (caller holds service.lock; Tony 8 Nov 2026: no silent stalls).

    Running worker jobs nobody watches are adopted so their real completion wakes the director.
    With nothing running and no current production plan to reconcile, the director is woken to
    continue or name a true external blocker, at most IDLE_WAKE_LIMIT times per unchanged job state."""
    if plan and direction and plan.get('direction_id') == direction and not plan.get('needs_update'):
        return False  # The production-plan reconciler below owns this case.
    if not direction or (service.saved.get('production_outcome') or {}).get('status') == 'review_ready':
        return False  # No active human production direction: nothing to keep alive.
    last = next((m for m in reversed(service.saved['leader'].get('messages') or []) if m.get('role') == 'assistant'), None)
    if last and re.match(r'\s*(?:[*_#>]+\s*)?(?:\[[^\]]*\]\s*)?(?:[*_#>]+\s*)?(DELIVERED|BLOCKED)\s*[*_]*\s*:', str(last.get('text') or ''), re.I):
        return False  # Director explicitly declared delivery or a true external blocker.
    jobs = service.runtime.jobs()
    active = [j for j in jobs if j.get('status') in service.runtime.active_states and j.get('agent_id') != 'lumen-editor']
    if active:
        for j in active:
            service.saved['watches'].setdefault(j['id'], {'status': 'waiting', 'kind': 'adopted',
                'detail': 'Adopted by the idle watchdog: this job was running without a completion watch.'})
        service._persist()
        return True
    local = getattr(service.runtime, 'local_ops', None)
    if (local and local.snapshot()['active']) or (hasattr(service, '_handoff_native_pending') and service._handoff_native_pending()):
        return False  # Existing guarded notices handle local/native work.
    fp = _jobs_fingerprint(jobs)
    marker = (fp, len(service.saved['leader'].get('messages') or []))
    timer = threading.Timer(IDLE_GRACE_SECONDS, _fire_idle_wake, args=(service, direction, marker))
    timer.daemon = True
    timer.start()
    return True


def _jobs_fingerprint(jobs):
    return hashlib.sha256(json.dumps(sorted((j.get('id'), j.get('status')) for j in jobs)).encode()).hexdigest()[:24]


def _fire_idle_wake(service, direction, marker):
    """Debounced idle wake: fires only if nothing at all happened during the grace period, so a human
    message, a new job or a registered watch always wins and nothing races the human."""
    with service.lock:
        saved = service.saved
        if service.closed or not saved.get('continuation_authorized') or saved.get('production_pause') or saved.get('production_direction') != direction:
            return
        if saved['leader'].get('status') in service.active or any(w.get('status') in ('waiting', 'ready') for w in saved.get('watches', {}).values()):
            return
        jobs = service.runtime.jobs()
        fp = _jobs_fingerprint(jobs)
        if (fp, len(saved['leader'].get('messages') or [])) != marker or any(j.get('status') in service.runtime.active_states for j in jobs):
            return
        state = saved.get('idle_watchdog') or {}
        count = state.get('count', 0) + 1 if state.get('fp') == fp else 1
        if count > IDLE_WAKE_LIMIT:
            notify(service, 'idle-stalled:'+fp, 'Director stopped with no work running',
                   'The director was woken '+str(IDLE_WAKE_LIMIT)+' times with no job or task progress and nothing running. No further automatic prompt is sent until real work changes.')
            return
        saved['idle_watchdog'] = {'fp': fp, 'count': count}
        saved['watches']['idle-watchdog:'+fp+':'+str(count)] = {'status': 'ready', 'kind': 'production', 'job_status': 'IDLE_NO_WORK',
            'detail': 'Your turn ended with no job running and no completion watch, so nothing would ever wake you. Continue the authorized task now: read status, dispatch the next task (or a NEW recovery task for a failure) and register watch --job for it, then end the turn. If the edit is fully delivered or a true external blocker remains, start your reply with DELIVERED: or BLOCKED: (and the reason); then nothing wakes you again. Do not ask Tony to continue. Idle wake '+str(count)+' of '+str(IDLE_WAKE_LIMIT)+'.'}
        service._persist()
    service._drain_wakes()


def refresh_claude_reset(service, now=None):
    """A native Claude refusal saved without reset_at never cleared (8 Nov 2026: 'resets 8:10am (Africa/Cairo)').
    Re-parse the provider's own words against the report time. Passed reset: the stale flag is cleared.
    Future reset: returns it so a no-inference wake is registered. No provider call, no fabricated time."""
    import time
    from datetime import datetime
    from usage_routing import reset_from_text
    now = time.time() if now is None else now
    with service.lock:
        ex = service.saved.get('native_claude_exhausted')
        if not ex:
            return None
        reset = ex.get('reset_at')
        if not isinstance(reset, (int, float)):
            try:
                reported = datetime.fromisoformat(ex['reported_at']).timestamp() if ex.get('reported_at') else None
            except (TypeError, ValueError):
                reported = None
            reset = reset_from_text(ex.get('reason', ''), now=reported) if reported else None
            if not reset:
                return None
            ex['reset_at'] = reset
        if reset <= now:
            service.saved.pop('native_claude_exhausted', None)
            service._record('director', 'Claude allowance reset passed', 'Stale refusal cleared at startup from the provider-reported reset time; no inference ran.', 'completed')
            service._persist()
            return None
        service._persist()
        return reset


def startup_resume(service):
    """Studio (re)start with an authorized direction, an idle director and nothing watched: re-arm the
    same debounced idle watchdog so a restart never leaves the director silently stalled. An interrupted
    or uncertain turn is never resumed or replayed; the IDLE_WAKE_LIMIT cap and grace re-checks still apply."""
    reset_at = refresh_claude_reset(service)
    if reset_at:
        service.register_reset_wake('claude', reset_at)  # usage-limit stop resumes itself at the reported reset
        return False
    with service.lock:
        saved = service.saved
        if service.closed or not saved.get('continuation_authorized') or saved.get('production_pause') or saved.get('backup_suppressed'):
            return False
        leader = saved['leader']
        # At startup no turn thread exists, so a thread-owned Claude/Antigravity 'error' is provably stale
        # (same rule as _send_direction). 'uncertain' is never touched.
        if leader.get('status') == 'error' and leader.get('provider') in ('claude', 'antigravity'):
            leader.update(status='idle', error=None)
            service._persist()
        if leader.get('status') not in ('idle', 'completed'):
            return False
        watches = saved.get('watches', {}).values()
        ready = any(w.get('status') == 'ready' for w in watches)
        if not ready and any(w.get('status') == 'waiting' for w in watches):
            return False  # A real completion event still owns the wake.
        if not ready:
            return _idle_watchdog(service, ProductionBoard(service.root).snapshot()['plan'], saved.get('production_direction'))
    # A real completion that landed just before shutdown is delivered now (never a replayed turn).
    threading.Thread(target=service._drain_wakes, daemon=True).start()
    return True


def finished(service, status):
    with service.lock:
        if service.closed or not service.saved.get('continuation_authorized') or service.saved.get('production_pause') or service.saved.get('backup_suppressed'):
            return
        leader = service.saved['leader']
        if leader.get('status') in service.active and leader.get('status') != 'uncertain':
            return
        if leader.get('status') != 'uncertain' and any(w.get('status') in ('waiting', 'ready') for w in service.saved.get('watches', {}).values()):
            return  # A stopped text turn (including CLI turn cap) can leave real
                    # watched local work progressing. Its terminal event resumes.
        direction = service.saved.get('production_direction')
        from native_director import confirmed_timeout
        timeout = confirmed_timeout(service) if status in ('TIMED_OUT', 'FAILED') else None
        if status not in ('completed', 'COMPLETED') and not timeout:
            if service.saved.get('codex_quota_exhausted') and leader.get('provider', 'codex') == 'codex' and service.director_policy().get('enabled'):
                return
            # Never auto-recover an unknown outcome, an unconfirmed/older timeout, or a pending native command: that would erase the guard and permit replay.
            unsafe = leader.get('status') == 'uncertain' or status == 'TIMED_OUT' or bool(service._handoff_native_pending() if hasattr(service, '_handoff_native_pending') else None)
            # A failed/interrupted director send is never retried automatically (human rule; test_failed_send_has_no_automatic_retry).
            # The former auto-recovery re-sent up to 10 continuation turns after a failed send; it is disabled, the attention event below is the only action.
            if AUTO_RETRY_FAILED_SENDS and service.saved.get('continuation_authorized') and not unsafe:
                retries = service.saved.setdefault('transient_error_retries', 0)
                if retries < 10:
                    service.saved['transient_error_retries'] = retries + 1
                    err_txt = str(leader.get('error') or 'Director transient error')
                    key = 'auto-transient:' + str(direction)
                    service.saved['watches'][key] = {
                        'status': 'ready',
                        'kind': 'production',
                        'job_status': 'RETRY_TRANSIENT_ERROR',
                        'detail': 'Auto-recovering after transient director error (' + err_txt + '). Continuing authorized task without human intervention.'
                    }
                    service.saved['leader']['status'] = 'idle'
                    service.saved['leader']['error'] = None
                    service._persist()
                    threading.Thread(target=service._drain_wakes, daemon=True).start()
                    return
            notify(service, 'director-error:'+str(direction)+':'+str(leader.get('error')),
                   'Director needs attention', str(leader.get('error') or 'The director ended without a confirmed completion. Reconcile actual execution before resuming; no unknown command will be replayed.'))
            return
        if status in ('completed', 'COMPLETED'):
            service.saved['transient_error_retries'] = 0
        if any(w.get('status') in ('waiting', 'ready') for w in service.saved.get('watches', {}).values()):
            return  # Existing exact completion watch owns continuation.
        if _announced_continue(service, direction):
            # Deliver after this lock is released (the drain takes the same lock).
            threading.Thread(target=service._drain_wakes, daemon=True).start()
            return
        plan = ProductionBoard(service.root).snapshot()['plan']
        if status in ('completed', 'COMPLETED') and _idle_watchdog(service, plan, direction):
            return
        if not plan or not direction or plan.get('direction_id') != direction or plan.get('needs_update'):
            if timeout and _timeout_checkpoint_recovery(service, direction, timeout):
                threading.Thread(target=service._drain_wakes, daemon=True).start()
            return  # Only the timeout event may reconcile; never adopt an old plan.
        pending = [s for s in plan['steps'] if s['status'] not in ('verified','awaiting_review') and s['gate'] != 'human']
        fingerprint = work_fingerprint(plan, direction)
        jobs = service.runtime.jobs()
        local = getattr(service.runtime, 'local_ops', None)
        if any(j['status'] in service.runtime.active_states for j in jobs) or (local and local.snapshot()['active']):
            notify(service, 'unwatched:'+fingerprint, 'Work is running without a completion handoff',
                   'A real worker/local job is still active, but the director ended without a registered completion watch. No duplicate worker was started. Reconcile ownership and register the exact existing job.')
            return
        native = service._handoff_native_pending() if hasattr(service, '_handoff_native_pending') else None
        if native:
            notify(service, 'native-unwatched:'+str(native), 'Native execution needs reconciliation',
                   'TonyFX command '+str(native)+' is still pending/running without a registered completion watch. No competing editor or retry was launched.')
            return
        if not pending:
            if any(s['status']=='awaiting_review' for s in plan['steps']) and not plan.get('ready_for_review'):
                notify(service,'review-invalid:'+fingerprint,'Full review needs repair',plan.get('review_error') or 'Final review cannot be verified for this revision.')
                return
            notify(service, 'review:'+direction+':'+plan['revision'], 'Review ready for your decision',
                   plan['revision']+': production work is finished and the full review is ready. Final human motion/listening checks and artistic acceptance remain unverified.', 'review_ready')
            return
        actionable = [s for s in pending if (s.get('blocker') or {}).get('kind') not in ('capability', 'human_input', 'native_unknown', 'quota')]
        from production_workbench import RecoveryDesk
        for step in pending:
            block=step.get('blocker') or {}
            RecoveryDesk(service.root).record({'id':hashlib.sha256((str(direction)+plan['revision']+step['id']).encode()).hexdigest()[:32],
                'project_id':plan['project_id'],'revision':plan['revision'],'kind':block.get('kind','recoverable'),
                'diagnosis':block.get('reason') or 'Director ended with required checkpoint unfinished: '+step['title'],
                'next_action':block.get('next_action') or 'Inspect current evidence, diagnose the cause, then correct only this checkpoint or request a capable scoped consultation.',
                'source':'data/production/CURRENT.json','station':step.get('station'),'required_capabilities':step.get('required_capabilities',['text'])})
        if not actionable:
            notify(service, 'blocked:'+fingerprint, 'Production needs your attention',
                   '\n'.join(s['title']+': '+s['blocker']['reason']+' Next: '+s['blocker']['next_action'] for s in pending))
            return
        recovered = service.saved.setdefault('production_recoveries', [])
        if fingerprint in recovered:
            if timeout:
                notify(service, 'timeout-stalled:'+fingerprint, 'Claude recovery needs technical help',
                       'One scoped recovery already ran without verified checkpoint progress. No repeated prompt was sent. '+timeout['folder']+'/RESULT.json')
                return
            notify(service, 'stalled:'+fingerprint, 'Director left required work unfinished',
                   'One scoped recovery was already delivered, but the same required work remains with no active worker/watch: '+', '.join(s['title'] for s in actionable)+'. This is an orchestration failure, not successful completion. No repeated model prompt was sent.')
            return
        # A timer expiration is not proof of script failure or permission to replay.
        # One recovery per verified milestone prevents consecutive timeout loops,
        # even if the provider rewrites notes or flips working/todo statuses.
        if timeout:
            milestone=hashlib.sha256(json.dumps({'direction':direction,'revision':plan['revision'],
                'verified':sorted(s['id'] for s in plan['steps'] if s['status']=='verified')},sort_keys=True).encode()).hexdigest()[:32]
            attempts=service.saved.setdefault('director_timeout_recoveries',[])
            if milestone in attempts:
                notify(service,'timeout-stalled:'+milestone,'Claude recovery needs technical help',
                       'Claude timed out again without another verified checkpoint. No repeated continuation was sent. Saved process is stopped; reconcile the current partial script/native report. '+timeout['folder']+'/RESULT.json')
                return
            service.saved['director_timeout_recoveries']=(attempts+[milestone])[-40:]
        service.saved['production_recoveries'] = (recovered+[fingerprint])[-40:]
        key = 'production:'+fingerprint
        service.saved['watches'][key] = {'status': 'ready', 'kind': 'production', 'job_status': 'INCOMPLETE_REQUIREMENTS',
            'detail': (('The previous Claude worker reached its time cap and is confirmed stopped, NOT a quota refusal. Read '+timeout['folder']+'/RESULT.json and latest project STATE/script-specific partial reports. Preserve dirty state and inspect exact current TonyFX result before a NEW corrected operation. Do not replay the last command or rebuild from the original brief. Use a bounded milestone, inspect AE property limits/types, and request one capable Sol read-only technical consultation if needed. Save evidence and END inference while a watched local/native job runs. ' if timeout else '')+
            'The director ended with actionable required checkpoints still open: '+', '.join(s['title'] for s in actionable)+
            '. Continue the already authorized task. Read neural_workbench recovery tickets or GET /api/workbench. Inspect actual failure/capabilities and correct scoped work; do not ask for continue. A suitable peer can diagnose a bounded failure via consult_recovery with ticket id and an available capable agent_id; finish inference until its real completion. Resolve the ticket only after new verified result evidence, not dispatch. Missing sound is unfinished work, not a blocker by itself. If a real capability/input/quota/unknown-native blocker remains, record blocker.kind, reason, attempted diagnosis and next_action on that checkpoint; the app will alert the human. Never claim playback/listening you cannot perform.')}
        service.saved['production_outcome'] = {'status': 'recovering', 'title': 'Continuing unfinished requirements', 'detail': service.saved['watches'][key]['detail']}
        service._persist()
    service._drain_wakes()
