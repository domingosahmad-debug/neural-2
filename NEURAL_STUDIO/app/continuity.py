"""Bounded shared memory, separate provider sessions, no inference or transcript sweep."""
import json
from pathlib import Path
from operations import load, save, stamp
from workflows import WorkflowProfiles


def scope_sessions(saved, workflow):
    """Keep each provider's conversation within its selected workflow version.

    Project changes do not erase reusable workflow knowledge. Workflow changes do
    not silently reuse another workflow's conversation. Providers never share IDs.
    """
    key = workflow['sha256']
    previous = saved.get('director_context_scope')
    leader = saved['leader']
    if previous and previous != key:
        saved.setdefault('director_sessions', {})[previous] = {
            **{k: leader.get(k) for k in ('thread_id', 'claude_session_id')},
            'toolset_signature':saved.get('toolset_signature')}
        target = saved.get('director_sessions', {}).get(key, {})
        leader.update(thread_id=target.get('thread_id') if target.get('toolset_signature')==saved.get('toolset_signature') else None,
                      claude_session_id=target.get('claude_session_id'),
                      turn_id=None, token_usage=None)
    elif not previous and workflow['id'] != 'tuf':
        # A legacy session has no trustworthy workflow attribution.
        saved.setdefault('legacy_sessions', []).append({
            'thread_id': leader.get('thread_id'),
            'claude_session_id': leader.get('claude_session_id'),
            'reason': 'Legacy workflow attribution unknown', 'at': stamp()})
        leader.update(thread_id=None, claude_session_id=None, token_usage=None)
    saved['director_context_scope'] = key
    return previous != key


def corrections(root, workflow_id, station=None):
    """Small pointers + actionable corrections, never another workflow's lessons."""
    try:
        rows = load(Path(root)/'data/workflow-apprentice/MISTAKE_LEDGER.json')['entries']
    except (OSError, ValueError, KeyError):
        rows = []
    scoped = [r for r in rows if r.get('workflow_id', 'tuf') == workflow_id]
    categories={'media':{'render_delivery','review_delivery'},
                'analysis':{'editing','review_workflow','motion_workflow'},
                'story':{'editing','review_workflow'},
                'sound-design':{'sound_design','typography'},
                'editing':{'ae_scripting','editing','motion_workflow','typography'},
                'review-delivery':{'review_workflow','render_delivery','review_delivery'}}
    if station:
        selected=[r for r in scoped if r.get('category')=='orchestration'][-2:]+[r for r in scoped if r.get('category') in categories.get(station,set())][-6:]
    else:selected=scoped[-8:]
    return [{k: str(v)[:650] for k, v in row.items()
             if k in ('id', 'category', 'trigger', 'mistake', 'correction', 'rule', 'fix', 'lesson', 'boundaries')}
            for row in selected]


def startup_state(saved, plan, native_pending=None):
    leader = saved.get('leader', {})
    return {
        'project': {k: plan.get(k) for k in ('project_id', 'revision', 'title', 'review_preview_id')},
        'direction_id': saved.get('production_direction'),
        'continuation_authorized': saved.get('continuation_authorized') is True,
        'pause': saved.get('production_pause'),
        'outcome': saved.get('production_outcome'),
        'director': {k: leader.get(k) for k in ('provider', 'model', 'status', 'turn_id')},
        'native_pending_command': native_pending,
        'watches': [
            {'id': key, **{k: row[k] for k in ('kind', 'job_id', 'command_id', 'status', 'result_path') if k in row}}
            for key, row in saved.get('watches', {}).items() if row.get('status') in ('waiting', 'ready')
        ],
        'start_here': 'shared/START_HERE_NEURAL.md',
        'latest_direction_file': 'shared/LATEST_DIRECTOR_DIRECTION.md',
    }


def packet(root, saved, workflow=None, oversight=False, native_pending=None):
    root = Path(root)
    workflow = workflow or WorkflowProfiles(root).snapshot()
    try:
        plan = load(root/'data/production/CURRENT.json')
    except (OSError, ValueError):
        plan = {}
    leader = saved.get('leader', {})
    value = {
        'workflow': {k: workflow[k] for k in ('id', 'sha256')},
        'read_first': (['shared/OVERSIGHT_DIRECTOR_GUIDE.md', 'shared/CURRENT_WORKFLOW_20261107.md'] if oversight else
                       ['shared/LEADER_CONTEXT.md', 'shared/STATION_ROUTING_AND_MEMORY.md',
                        'shared/CURRENT_RULES.md', 'shared/PRODUCTION_CHECKPOINT_WORKFLOW.md']),
        'startup': startup_state(saved, plan, native_pending),
        'workflow_instructions': workflow.get('instructions', '')[:2000],
        'shared_corrections': corrections(root, workflow['id']),
        'current_project': {k: plan.get(k) for k in ('project_id', 'revision', 'title', 'scope', 'review_preview_id')},
        'checkpoints': [{k: s.get(k) for k in ('id', 'status', 'gate')}
                        for s in plan.get('steps', [])[:32]],
        'last_director_provider': leader.get('provider'),
        'last_director_result': next((m.get('text', '')[-1400:] for m in reversed(leader.get('messages', []))
                                      if m.get('role') == 'assistant'), ''),
        'pause': saved.get('production_pause'),
        'authority': 'Memory is context, not a new task or approval. The latest human direction wins. '
                     'Reconcile current project/native evidence; never replay history. '
                     'Provider conversations are separate; files carry shared knowledge, not identical minds.',
    }
    from team_memory import TeamMemory
    value['shared_team']=TeamMemory(root).director_brief(plan.get('project_id'))
    from production_workbench import context
    value['production_workbench']=context(root,plan.get('project_id'))
    from future_delegation import policy
    value['project_delegation']=policy(root,plan.get('project_id'))
    # All fields have individual bounds. Full records stay at their original paths.
    text = json.dumps(value, ensure_ascii=False)
    while len(text)>14000 and len(value['shared_corrections'])>1:
        value['shared_corrections'].pop(0)
        text = json.dumps(value, ensure_ascii=False)
    if len(text)>14000:
        team=value['shared_team']
        value['shared_team']={k:team.get(k) for k in ('project_memory','paused','read_protocol')}
        value['shared_team']['omitted_detail']=('Run `python tools/neural_cli.py channel` / `recall` for current peer ownership and recovery details.' if oversight else 'Read neural_team /api/team for current peer ownership and recovery details.')
        text=json.dumps(value,ensure_ascii=False)
    if len(text)>14000:
        value['shared_corrections']=[]
        value['correction_memory']='data/workflow-apprentice/MISTAKE_LEDGER.json; retrieve relevant rules within this workflow.'
        text=json.dumps(value,ensure_ascii=False)
    if len(text) > 14000:
        raise ValueError('Continuity packet exceeds budget; prepare a smaller scoped handoff')
    return value


def compact_packet(value):
    """B1: a resumed oversight director already holds the rules; re-send only what changes per turn, with file pointers."""
    keep = {k: value.get(k) for k in ('workflow', 'current_project', 'checkpoints', 'last_director_provider', 'last_director_result', 'pause', 'authority', 'startup') if k in value}
    team = value.get('shared_team') or {}
    keep['shared_team'] = {k: team.get(k) for k in ('paused', 'read_protocol') if k in team}
    keep['full_context'] = 'data/continuity/LATEST.json (rules, corrections, team memory, workbench, delegation). Read only what the task needs.'
    return keep


def director_context(root, saved, compact=False, oversight=False, native_pending=None):
    value = packet(root, saved, oversight=oversight, native_pending=native_pending)
    save(Path(root)/'data/continuity/LATEST.json', value)
    if compact:value = compact_packet(value)
    return '\nNEURAL SHARED CONTINUATION (local evidence; not a new assignment):\n'+json.dumps(value, ensure_ascii=False)+'\n\n'


def station_memory(root, task):
    if isinstance(task.get('shared_memory'),dict):return json.dumps(task['shared_memory'],ensure_ascii=False)
    value = {'workflow': task.get('workflow', {}).get('id', 'tuf'),
             'station': task['station'], 'project_id': task.get('project_id'),
             'rules': corrections(root, task.get('workflow', {}).get('id', 'tuf'),task['station']),
             'authority': 'Current task only. Station skills, frozen workflow and current corrections '
                          'are shared across providers. Historical edits are not templates to steal. '
                          'Director chooses the worker; no permission or perception is inherited.'}
    return json.dumps(value, ensure_ascii=False)
