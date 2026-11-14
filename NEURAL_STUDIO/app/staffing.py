"""Local capability/availability routing advice. Never a model benchmark or dispatch."""
from operations import load
CAPABILITIES = {'text', 'images', 'listening', 'playback', 'native_ae'}

def native_claude_exhausted(state):
    """Honor the director's actual refusal for all native Claude workers.

    A passed reset makes the refusal stale, not proof of replenishment.
    """
    refusal = state.get('native_claude_exhausted') or {}
    import time
    reset=refusal.get('reset_at')
    if isinstance(reset,(int,float)) and reset <= time.time():return False
    if refusal.get('shared_confirmed') is True:return True
    reason = str(refusal.get('reason') or '').lower()
    # Transient rate limits, model-specific limits and billing errors do not
    # prove that Sonnet shares an exhausted subscription allowance.
    if any(term in reason for term in ('sonnet', 'opus', 'rate limit', 'insufficient credits')):
        return False
    return any(term in reason for term in ('usage limit', 'quota exhausted', 'hit your session limit',
                                            'hit your limit', 'out of extra usage',
                                            'limit reached'))


def capabilities(agent):
    # These describe installed adapters, not the model's theoretical API ability.
    provider = agent['provider']
    if provider == 'local':return set()
    if provider == 'manual':return set()  # External access must be commissioned.
    return {'text', 'images'} if provider == 'codex' else {'text'}


def eligible_stations(agent, stations):
    return ['media'] if agent['provider'] == 'local' else list(stations)


def requirements(raw):
    if not isinstance(raw, list) or not raw or len(raw) > 5 or any(c not in CAPABILITIES for c in raw):
        raise ValueError('Required capabilities must be text/images/listening/playback/native_ae')
    return set(raw)


def roster(runtime, station, required=None, difficulty='standard'):
    if station not in runtime.store.stations:raise ValueError('Unknown station')
    if difficulty not in ('routine', 'standard', 'complex'):raise ValueError('Choose routine, standard or complex work')
    needed = requirements(required if required is not None else ['text'])
    jobs = runtime.jobs()
    try:state = load(runtime.root/'data/command/STATE.json')
    except (OSError, ValueError):state = {}
    rows = []
    from future_delegation import policy, lumen_profile, lumen_issue, LUMEN_HELPER
    delegation=policy(runtime.root)
    profiles=list(runtime.agents())
    helper=lumen_profile(runtime) if delegation['enabled'] else None
    if helper:profiles.append(helper)
    for a in profiles:
        reasons = []
        caps = capabilities(a)
        issue = runtime.profile_issue(a)
        if issue:reasons.append(issue)
        if a['id']==LUMEN_HELPER:
            issue=lumen_issue(runtime,station)
            if issue:reasons.append(issue)
        if a['provider'] in ('manual', 'local'):reasons.append('Use the external task kit or deterministic local engine; not a hosted specialist')
        if needed-caps:reasons.append('Adapter lacks: '+', '.join(sorted(needed-caps)))
        own = [j for j in jobs if j.get('agent_id') == a['id']]
        if any(j['status'] in runtime.active_states for j in own):reasons.append('Already working')
        if any(j.get('idle_inference') == 'unknown' for j in own):reasons.append('Previous execution needs reconciliation')
        quota = state.get('usage', {}).get(a['provider'], {})
        if a['provider']=='codex':
            from types import SimpleNamespace
            from usage_routing import codex_exhausted
            if codex_exhausted(SimpleNamespace(root=runtime.root,saved=state)):
                reasons.append('Codex reported exhausted allowance; its specialists share that account')
        if a['provider'] == 'claude':
            from claude_usage import snapshot
            quota = snapshot(runtime.root)
            if native_claude_exhausted(state):
                reasons.append('Native Claude reported exhausted allowance; shared Claude workers are unavailable')
        # Ignore quota windows whose reset passed; those are stale, not proof of refill.
        import time
        windows = quota.get('windows', [])
        relevant = windows
        if a['provider'] == 'antigravity':
            connection = getattr(runtime, 'providers', {}).get('antigravity', {})
            if connection.get('quota'):
                try:
                    runtime._require_antigravity_worker(a.get('model',''), connection)
                except ValueError as exc:
                    reasons.append(str(exc))
            relevant = []  # The current adapter report is authoritative for Antigravity.
        for w in relevant:
            reset = w.get('reset_at')
            if isinstance(reset,(int,float)) and reset <= time.time():continue
            remaining = w.get('remaining_percent')
            if isinstance(remaining,(int,float)) and remaining <= 1:reasons.append('Reported account allowance at/below 1%; do not probe or buy extra usage')
        model = a.get('model', '').lower()
        tier = 'complex' if any(n in model for n in ('opus','sol','argon')) else 'routine' if any(n in model for n in ('haiku','flash','mimo','muse')) else 'standard'
        # Starting preferences only. Record actual assignment quality; never assert "best" from brand.
        score = 30 if tier == difficulty else 15 if difficulty == 'standard' else 5
        terra_fallback = (a['provider']=='codex' and model=='gpt-6.1-terra' and
                          native_claude_exhausted(state) and difficulty != 'complex' and
                          needed <= {'text','images'})
        if terra_fallback:score += 25
        history = [j for j in own if j.get('station') == station][:12]
        counts = {s: sum(j['status']==s for j in history) for s in ('APPROVED','CHANGES_REQUESTED','FAILED')}
        score += min(6,counts['APPROVED'])-min(6,counts['CHANGES_REQUESTED'])
        rows.append({'agent_id':a['id'], 'name':a['name'], 'provider':a['provider'], 'model':a.get('model'),
                     'context_modes':['persistent','fresh_review'] if a['provider'] in ('codex','claude','opencode','antigravity') else ['persistent'] if a['provider'] not in ('local','manual') else [],
                     'home_stations':a.get('stations',[]), 'eligible_stations':eligible_stations(a,runtime.store.stations),
                     'capabilities':sorted(caps), 'available':not reasons, 'reasons':reasons,
                     'preference_score':score, 'fit_basis':('Bounded supplied text/still candidate when native Claude is exhausted; verify task depth and Codex allowance' if terra_fallback else 'Task-depth preference and recent structural reviews, not measured artistic superiority'),
                     'recorded_station_outcomes':counts, 'quota_status':quota.get('status','unknown')})
    rows.sort(key=lambda r:(not r['available'], -r['preference_score'], r['name']))
    editor=getattr(runtime,'lumen_editor',None)
    if station=='editing' and editor:
        state=editor.snapshot();caps={'text','native_ae'}
        rows.append({'agent_id':'lumen-editor','name':'Lumen · trial editor','provider':state.get('configured_provider','antigravity'),'model':(state.get('job') or {}).get('model') or state.get('configured_model','Configured Lumen Flash model'),
          'home_stations':['editing'],'eligible_stations':['editing'],'capabilities':sorted(caps),'available':state.get('adapter_supported',False) and state['status'] not in ('QUEUED','RUNNING','WAITING_LOCAL','UNKNOWN','PAUSED') and not needed-caps,
          'reasons':['Separate explicit trial role; queue through neural_lumen_editor, not neural_dispatch. Editor ownership and account checks happen before inference.'],
          'preference_score':0,'fit_basis':'Trial role; quality is experimental, not assumed superior from lesson count','recorded_station_outcomes':{},'quota_status':'shared Gemini allowance; checked at execution','assignment_api':'/api/apprentice/editor/start',
          'executor_route':state.get('route'),'supported_executors':{'antigravity':'gemini-3.8-flash-*','claude':['opus','sonnet','haiku']},'persistent_session':True,'single_native_writer':'EDITOR_LOCK/owns_editor'})
    return {'station':station, 'required_capabilities':sorted(needed), 'difficulty':difficulty,
            'fresh_review':{'policy':'goldfish-fresh-review-2026-11-03.1','providers':['codex','claude','opencode','antigravity'],'critic_panel':{'max_critics':2,'recheck':1,'aggregator':'critic_panel.aggregate (deterministic)','approval':'never','image_modality':'codex only; others NOT RUN','opencode':'exact opencode/*-free ids, cost 0','antigravity':'gemini-* plan mode'},
                'task_context_mode':'fresh_review','requires':'Explicit bounded target, exact evidence hash, constraints, safety, project/revision; one initial plus one changed-blocker recheck',
                'tools':False,'ordinary_session_reuse':False,'automatic_dispatch':False},
            'candidates':rows, 'model_calls':0, 'future_project_delegation':delegation,
            'policy':'Any connected AI can enter any station. Capability and task evidence decide suitability. '
                     'Home stations are display defaults. Unknown quota is not free/unlimited. '
                     'Sound planning is text work; actual listening requires a listening-capable adapter. '
                     'Native integration stays with the single authorized director/editor. No automatic dispatch.'}
