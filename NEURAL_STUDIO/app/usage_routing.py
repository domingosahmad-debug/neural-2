"""One-shot succession after a confirmed subscription quota refusal.

Never polls, probes a provider, replays a turn, or changes a conversation ID.
Only terminal provider events and existing completion callbacks call this module.
"""
import time
from datetime import datetime, timezone
from operations import load

def enabled(service):
    try:p=load(service.root/'data/command/USAGE_ROUTING_POLICY.json')
    except (OSError,ValueError):return False
    return (p.get('version') == 1 and p.get('enabled') is True and p.get('authorized_by') == 'Tony'
            and p.get('auto_failover_on_confirmed_quota') is True and p.get('allow_paid_fallback') is False)

def fresh(service, row):
    try:
        policy=load(service.root/'data/command/USAGE_ROUTING_POLICY.json')
        checked=datetime.fromisoformat(str(row['checked_at']).replace('Z','+00:00'))
        if checked.tzinfo is None:checked=checked.replace(tzinfo=timezone.utc)
        age=time.time()-checked.timestamp()
        return 0 <= age <= int(policy.get('quota_metadata_max_age_seconds',900))
    except (OSError,ValueError,KeyError,TypeError):return False

def codex_exhausted(service):
    """Shared Codex allowance gate, identical for director and workers."""
    state=service.saved
    row=state.get('usage',{}).get('codex',{})
    windows=row.get('windows',[])
    if enabled(service) and not fresh(service,row):windows=[]
    try:
        policy=service.director_policy() if callable(getattr(service,'director_policy',None)) else load(service.root/'data/command/DIRECTOR_POLICY.json')
        reserve=policy.get('primary_reserve_percent',0)
    except (OSError,ValueError):reserve=0
    if state.get('codex_quota_exhausted') and windows and all(isinstance(w.get('reset_at'),(int,float)) and w['reset_at']<=time.time() for w in windows):
        # The exhaustion flag has no reset of its own; once every reported window has reset it is stale.
        state.pop('codex_quota_exhausted',None);state['codex_quota_exhausted_cleared_at']=time.time()
    return bool(state.get('codex_quota_exhausted')) or any(
        isinstance(w.get('remaining_percent'),(float,int)) and w['remaining_percent']<=reserve and
        isinstance(w.get('reset_at'),(int,float)) and w['reset_at']>time.time() for w in windows)

def confirmed_quota(detail):
    text = str(detail).lower()
    return any(x in text for x in ('usagelimitexceeded', 'usage limit', 'hit your limit', 'hit your session limit',
                                   'quota exhausted', 'out of extra usage', 'limit reached'))

def reset_from_text(detail, now=None):
    """Parse a provider-reported reset such as 'resets Nov 7, 10pm (Africa/Cairo)' to epoch seconds. None if not reported or unparseable."""
    import re
    m=re.search(r'resets?\s+(?:at\s+)?([A-Za-z]{3,9})\s+(\d{1,2})(?:,)?\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)(?:\s*\(([A-Za-z_/+\-0-9]+)\))?',str(detail),re.I)
    if not m:
        # Time-only form, e.g. "resets 8:10am (Africa/Cairo)": the next occurrence of that wall time.
        t=re.search(r'resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)(?:\s*\(([A-Za-z_/+\-0-9]+)\))?',str(detail),re.I)
        if not t:return None
        try:
            from zoneinfo import ZoneInfo
            from datetime import timedelta
            tz=ZoneInfo(t.group(4)) if t.group(4) else None
            now=now if now is not None else time.time()
            base=datetime.fromtimestamp(now,tz) if tz else datetime.fromtimestamp(now).astimezone()
            hour=int(t.group(1))%12+(12 if t.group(3).lower()=='pm' else 0)
            when=base.replace(hour=hour,minute=int(t.group(2) or 0),second=0,microsecond=0)
            if when.timestamp()<=now-60:when=when+timedelta(days=1)
            return when.timestamp()
        except Exception:return None
    try:
        from zoneinfo import ZoneInfo
        tz=ZoneInfo(m.group(6)) if m.group(6) else None
        if m.group(6) and tz is None:return None
        now=now if now is not None else time.time()
        base=datetime.fromtimestamp(now,tz) if tz else datetime.fromtimestamp(now).astimezone()
        hour=int(m.group(3))%12+(12 if m.group(5).lower()=='pm' else 0)
        month=datetime.strptime(m.group(1)[:3].title(),'%b').month
        when=base.replace(month=month,day=int(m.group(2)),hour=hour,minute=int(m.group(4) or 0),second=0,microsecond=0)
        if when.timestamp()<now-86400*30:when=when.replace(year=when.year+1)
        return when.timestamp()
    except Exception:return None

def request(service, provider, event_id):
    """Record exactly one succession request per terminal refusal."""
    with service.lock:
        if not enabled(service):return
        seen = service.saved.setdefault('quota_failover_events', {})
        key = provider + ':' + str(event_id)
        if key in seen:return
        direction=service.saved.get('production_direction')
        chained=any(e.get('direction_id') == direction and e.get('status') == 'started' for e in seen.values())
        human_pending=bool(service.selector.state.get('pending'))
        seen[key] = {'provider':provider, 'status':'blocked' if chained else 'cancelled' if human_pending else 'waiting', 'event_id':str(event_id), 'direction_id':direction,
                     'human_selection_generation':service.selector.state.get('human_selection_generation',0),
                     **({'detail':'Both attempts ended in quota refusal; no further automatic provider retry.'} if chained else
                        {'detail':'A human director selection is already queued.'} if human_pending else {})}
        if chained:service.saved['leader'].update(status='error',error=seen[key]['detail'])
        service._record('director', 'Quota succession pending', key, 'waiting')
        service._persist()
    service._spawn(service._drain_wakes)

def reconcile(service):
    """Consume a pending event once at the existing full safe boundary."""
    from lumen_editor import EDITOR_LOCK
    from director_profiles import BY_ID, CONTINUE_TEXT
    from claude_usage import snapshot
    with EDITOR_LOCK, service.lock, service.selector.lock:
        if not enabled(service):return False
        events = service.saved.get('quota_failover_events', {})
        item = next(((k,v) for k,v in events.items() if v.get('status') == 'waiting'), None)
        if not item:return False
        key, event = item
        if service.closed or not service.saved.get('continuation_authorized'):
            event['status']='cancelled';service._persist();return False
        if event.get('direction_id') != service.saved.get('production_direction'):
            event['status']='cancelled';event['detail']='A newer human direction replaced this request.';service._persist();return False
        if event.get('human_selection_generation') != service.selector.state.get('human_selection_generation',0):
            event['status']='cancelled';event['detail']='A newer human director choice replaced this request.';service._persist();return False
        if service.saved.get('pending_image_input'):
            event.update(status='blocked',detail='Pending image inputs need an explicit evidence handoff; no blind continuation was started.')
            service.saved['leader'].update(status='error',error=event['detail']);service._persist();return False
        # Never override a queued human selection.
        if service.selector.state.get('pending'):return False
        # Target comes from Tony's policy; a null/absent entry means no director failover (e.g. Codex out of usage).
        try:fallbacks=load(service.root/'data/command/USAGE_ROUTING_POLICY.json').get('director_fallbacks') or {}
        except (OSError,ValueError):fallbacks={}
        target = fallbacks.get('claude-opus' if event['provider']=='claude' else 'sol-high')
        if target not in ('sol-high', 'claude-opus'):
            event.update(status='blocked',detail='No director fallback is enabled in USAGE_ROUTING_POLICY; waiting for the selected director allowance to reset. No provider call was made.')
            service.saved['leader'].update(status='error',error=event['detail'])
            service._record('director','Quota succession disabled',event['detail'],'failed');service._persist();return False
        if any(w.get('status') == 'ready' and w.get('job_status') in ('NEEDS_ATTENTION','UNKNOWN')
               for w in service.saved.get('watches',{}).values()):
            event['detail']='A completion watch needs reconciliation; no director started.'
            service._persist();return False
        kind, reason = service.selector.boundary(target)
        if kind:
            event['detail']=reason;service._persist();return False
        leader=service.saved['leader']
        if target=='sol-high':
            quota=service.saved.get('usage',{}).get('codex',{})
            rows=quota.get('windows',[]) if fresh(service,quota) else []
            current=[w for w in rows if isinstance(w.get('reset_at'),(int,float)) and w['reset_at']>time.time()]
            # The ordinary Codex engine resumes a saved thread, or commissions
            # one with the current dynamic tools when none is attached. A missing
            # thread (e.g. after a toolset migration) is not a quota refusal.
            # Never replace an existing thread or skip the safe boundary here.
            available = (not service._codex_exhausted() and
                         all(not isinstance(w.get('remaining_percent'),(int,float)) or w['remaining_percent']>0 for w in current))
        else:
            quota=snapshot(service.root)
            rows=quota.get('windows', []) if fresh(service,quota) else []
            current=[w for w in rows if isinstance(w.get('reset_at'),(int,float)) and w['reset_at']>time.time() and w.get('limit_id') != 'seven_day_sonnet']
            ex=service.saved.get('native_claude_exhausted') or {}
            active_ex=bool(ex) and not (isinstance(ex.get('reset_at'),(int,float)) and ex['reset_at']<=time.time())
            opus_session=(service.selector.state.get('sessions',{}).get('claude:opus') or
                          (leader.get('claude_session_id') if service.selector.state.get('claude_active_model')=='opus' else None))
            available=(not active_ex and bool(opus_session) and
                       all(not isinstance(w.get('remaining_percent'),(int,float)) or w['remaining_percent']>0 for w in current))
        if not available:
            event.update(status='blocked',detail='Target allowance or saved conversation is not verified available; no provider call was made.')
            leader.update(status='error',error=event['detail'])
            service._record('director','Quota succession blocked',event['detail'],'failed');service._persist();return False
        service.selector._apply(target, 'automatic-quota-failover')
        event.update(status='started',target=target)
        service._persist()
        try:
            service.send('Continue the latest authorized production from shared/ACTIVE_DIRECTOR_HANDOFF.md and current project STATE.md. The previous provider reached its confirmed allowance; inspect its terminal result and reconcile native commands, results and partial work before any mutation. This is a continuation, not a replay of the original brief.',internal=True)
        except Exception as exc:
            event.update(status='blocked',detail='Continuation did not start: '+str(exc)[:500])
            service._record('director','Quota succession blocked',event['detail'],'failed');service._persist()
    return True
