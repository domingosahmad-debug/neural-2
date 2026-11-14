"""Future-project staffing contract. Reads never dispatch, probe quota or resume work."""
import functools
import json
import re
from pathlib import Path

VERSION = '2026-10-22.1'
LUMEN_HELPER = 'lumen-station-helper'


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def adopt_new_project(root):
    """A child project made by an existing legacy edit keeps that edit's team."""
    root=Path(root)
    plan=read(root/'data/production/CURRENT.json', {})
    state=read(root/'data/command/STATE.json', {})
    if plan.get('project_id') and state.get('continuation_authorized') and not plan.get('ready_for_review'):
        same_direction=(not plan.get('direction_id') or not state.get('production_direction') or
                        plan['direction_id']==state['production_direction'])
        if same_direction and not policy(root,plan['project_id'])['enabled']:
            return False
    return True


def policy(root, project_id=None):
    root = Path(root)
    if project_id is None:
        project_id = read(root/'data/production/CURRENT.json', {}).get('project_id')
    project = {}
    if isinstance(project_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', project_id):
        project = read(root/'data/projects'/project_id/'PROJECT.json', {})
    enabled = project.get('delegation_policy_version') == VERSION
    value = {'version': VERSION, 'project_id': project_id, 'enabled': enabled,
             'read_first': 'shared/FUTURE_PROJECT_DELEGATION.md', 'model_calls': 0}
    if not enabled:
        value['instruction'] = ('New delegation policy is NOT adopted for this existing project. '
                                'Preserve its current owner, models, team and continuation; '
                                'do not add workers because of this upgrade.')
        return value
    value.update(
        instruction=('Director must split the plan before expensive work: local mechanical operations first; '
                     'delegate useful independent bounded text work to an available capable helper, '
                     'or record a concrete reason no helper fits. Keep story, shot sequencing, '
                     'ambiguous creative decisions, native integration and final review with the director. '
                     'Do not dispatch extra workers just to fill stations.'),
        routes={'mechanical': 'Shared local engine; no model',
                'bounded_text': 'Available allowed OpenCode free model, Lumen helper, Flash or Haiku; choose by task/access/evidence',
                'creative_owner': 'Existing authorized director; never switch it for this policy'},
        handoff=('Provide supplied evidence, exact scope, output fields and acceptance checks; '
                 'record assignment_reason. Use neural_assign then neural_dispatch and an owned completion watch; '
                 'end inference while waiting. Review returned evidence once, integrate only passing work. '
                 'For confirmed failure use one changed scoped recovery; no duplicate or UNKNOWN replay.'),
        lumen={'agent_id': LUMEN_HELPER, 'role': 'bounded station specialist, not director or exclusive trial editor',
               'tasks': ['check supplied quote/caption ownership', 'summarize source/shot ledgers',
                         'check supplied parameters against approved methods', 'summarize verified review evidence'],
               'limits': 'Text evidence only; no story decisions, listening, playback, native writes or assumed smarter weights. '
                         'Receives workflow-scoped learned corrections; shares Gemini subscription allowance.'})
    return value


def lumen_profile(runtime):
    learner = getattr(runtime, 'apprentice', None)
    state = getattr(learner, 'saved', None)
    if not isinstance(state, dict):
        state = read(Path(runtime.root)/'data/workflow-apprentice/STATE.json', {})
    if not state:
        return None
    provider = state.get('provider', 'antigravity')
    model = state.get('model', 'gemini-3.8-flash-high')
    # This adapter is commissioned only for the learner's configured Flash route.
    if provider != 'antigravity' or not isinstance(model,str) or not model.startswith('gemini-') or 'flash' not in model:
        return None
    return {'id': LUMEN_HELPER, 'name': 'Lumen · learned station helper', 'provider': provider,
            'model': model, 'stations': ['analysis', 'sound-design', 'review-delivery'],
            'app_owned_role': 'bounded_lumen_helper'}


def helper_busy(runtime):
    return any(j.get('agent_id') == LUMEN_HELPER and
               (j.get('status') in runtime.active_states or j.get('status') in ('UNKNOWN','INTERRUPTED') or j.get('idle_inference') == 'unknown')
               for j in getattr(runtime, 'jobs', lambda: [])())


def lumen_issue(runtime, station):
    learner = getattr(runtime, 'apprentice', None)
    state = getattr(learner, 'saved', None)
    if not isinstance(state, dict):
        state = read(Path(runtime.root)/'data/workflow-apprentice/STATE.json', {})
    if state.get('enabled') is False:
        return 'Lumen is disabled'
    if state.get('status') == 'learning' or state.get('execution_unknown'):
        return 'Lumen learning call must finish or be reconciled'
    editor = getattr(runtime, 'lumen_editor', None)
    if editor and editor.owns_editor():
        return 'Lumen trial owns the editing lane'
    if helper_busy(runtime):
        return 'Lumen helper is working or its execution needs reconciliation'
    if station == 'story':
        return 'Story direction and sequencing remain with the director'
    return None


def helper_lane(fn):
    """Atomically reserve a queued helper before the reflection loop can start."""
    @functools.wraps(fn)
    def wrapped(runtime, payload):
        if payload.get('agent_id') != LUMEN_HELPER:
            return fn(runtime, payload)
        from lumen_editor import EDITOR_LOCK
        with EDITOR_LOCK:
            return fn(runtime, payload)
    return wrapped


def resolve_helper(runtime, task):
    if not task.get('project_id') or not policy(runtime.root, task['project_id'])['enabled']:
        raise ValueError('Lumen helper is available only to newly opted-in projects; existing edit team preserved')
    profile = lumen_profile(runtime)
    if not profile:
        raise ValueError('Lumen helper requires the configured supported Gemini Flash adapter')
    issue = lumen_issue(runtime, task['station'])
    if issue:
        raise ValueError(issue)
    return profile


def helper_context(root, task):
    from continuity import corrections
    return {'role': 'Lumen bounded station helper', 'project_id': task.get('project_id'),
            'workflow_id': task.get('workflow', {}).get('id', 'tuf'),
            'learned_rules': corrections(root, task.get('workflow', {}).get('id', 'tuf'), task['station']),
            'limits': 'Supplied task only. Report discrepancies/help; do not redesign the story, '
                      'claim media perception or start tools. Lessons are retrieved memory, not model training.'}
