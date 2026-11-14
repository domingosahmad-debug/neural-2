"""Manual director profile selection (Sol, native Claude, Antigravity, Lumen).

Host-side policy only. Reading profiles/status never starts a model. Selecting a
profile never cancels or replaces an active turn: at a busy/native/local/unknown
boundary the selection is QUEUED or BLOCKED with an explanation, and a queued
choice is applied only after the boundary is actually clear. Every provider
keeps its own saved conversation; nothing is cleared to make a switch easy.
"""
from __future__ import annotations
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from operations import load, save, stamp
from capability_commissioning import adapter_commissioning

SELECTION_FILE = 'data/command/DIRECTOR_SELECTION.json'
MAX_IMAGES = 10
CONTINUE_TEXT = ('Continue the latest authorized production from shared/ACTIVE_DIRECTOR_HANDOFF.md and the current '
                 'project STATE.md. Reconcile native command/results and partial work before any mutation. This is a '
                 'director continuation requested by Tony after a manual director selection, not a replay of the initial brief.')

# kind decides which existing engine path executes the turn; none of them is a new competing worker.
PROFILE_DEFS = [
    {'id': 'sol-high', 'label': 'Sol High', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'high', 'kind': 'codex', 'role': 'director'},
    {'id': 'claude-opus', 'label': 'Claude Opus (native)', 'provider': 'claude', 'model': 'opus', 'kind': 'claude', 'role': 'director'},
    {'id': 'claude-sonnet', 'label': 'Claude Sonnet (native)', 'provider': 'claude', 'model': 'sonnet', 'kind': 'claude', 'role': 'director'},
    {'id': 'argon-high', 'label': 'Gemini Argon High (Antigravity)', 'provider': 'antigravity', 'model': 'gemini-4-argon-high', 'kind': 'antigravity', 'role': 'director'},
    {'id': 'agy-opus', 'label': 'Antigravity Opus', 'provider': 'antigravity', 'model': 'claude-opus-5-5-high', 'kind': 'antigravity', 'role': 'director'},
    {'id': 'agy-sonnet', 'label': 'Antigravity Sonnet', 'provider': 'antigravity', 'model': 'claude-sonnet-5-5-high', 'kind': 'antigravity', 'role': 'director'},
    {'id': 'gemini-flash-high', 'label': 'Gemini 3.8 Flash High (Antigravity)', 'provider': 'antigravity', 'model': 'gemini-3.8-flash-high', 'kind': 'antigravity', 'role': 'director'},
    {'id': 'lumen', 'label': 'Lumen (director profile)', 'provider': 'antigravity', 'model': 'gemini-3.8-flash-high', 'kind': 'antigravity', 'role': 'director-profile', 'lumen': True},
]
BY_ID = {p['id']: p for p in PROFILE_DEFS}
BUSY = {'starting', 'working', 'awaiting_approval', 'cancelling'}
UNKNOWN = {'uncertain'}


def _capabilities(profile, root=None, runtime=None):
    """Truthful, adapter-level capability map (commissioned locally, zero model inference)."""
    kind = profile['kind']
    comm = adapter_commissioning(kind, root=root, runtime=runtime)
    images_ok = True if kind in ('codex', 'claude') else bool(comm['vision'])
    images = {
        'supported': images_ok,
        'available': images_ok,
        'max_images': MAX_IMAGES if images_ok else 0,
        'detail': {
            'codex': 'Up to 10 individual screenshots delivered as native localImage inputs.',
            'claude': 'Up to 10 normalized local screenshot files opened with the CLI Read tool.',
            'antigravity': (
                'Up to 10 normalized local screenshot files opened with the Antigravity CLI read_file tool in accept-edits mode.'
                if images_ok else
                'Antigravity CLI adapter is not commissioned; screenshots are refused, never silently dropped.'
            ),
        }[kind],
    }
    file_shell = {
        'supported': True,
        'available': True,
        'detail': {
            'codex': 'Codex app-server shell/file tools under the app execution policy.',
            'claude': 'Claude Code Read/Write/Edit/Glob/Grep/Bash/PowerShell in accept-edits mode.',
            'antigravity': 'Antigravity CLI accept-edits read_file/write_file/edit_file/run_command tools (instruction-scoped).',
        }[kind],
    }
    net_ok = bool(comm['network'])
    network = {
        'codex': {
            'supported': True,
            'available': True,
            'status': 'supported',
            'detail': 'Sandbox policy allows network; web search items are surfaced by the runtime.',
        },
        'claude': {
            'supported': net_ok,
            'available': net_ok,
            'status': 'supported' if net_ok else 'shell_only',
            'detail': (
                'Claude Code WebFetch/WebSearch and local shell tools granted in director mode.'
                if net_ok else
                'Network only through allowed shell commands; WebFetch/WebSearch not enabled.'
            ),
        },
        'antigravity': {
            'supported': net_ok,
            'available': net_ok,
            'status': 'supported' if net_ok else 'unverified',
            'detail': (
                'Antigravity CLI search_web and shell tools available in accept-edits mode.'
                if net_ok else
                'Antigravity CLI is not verified on this host; do not assume network access.'
            ),
        },
    }[kind]
    local_ops = {
        'supported': True,
        'available': True,
        'detail': 'neural_local_ops dynamic tool.' if kind == 'codex' else 'Authenticated loopback API /api/local-ops/submit (documented in the director prompt).',
    }
    native = {
        'supported': True,
        'available': True,
        'status': 'single_writer',
        'detail': 'Single TonyFX writer lane; honors native hold, UNKNOWN-no-retry and Lumen ownership.',
    }
    audio = {
        'supported': True,
        'available': True,
        'status': 'local_host',
        'detail': 'Offline cached dictation & local audio analysis on host; director models read transcripts/metrics, not raw audio streams.',
    }
    listening = {
        'supported': False,
        'available': False,
        'status': 'unavailable',
        'detail': 'No director adapter listens to raw audio directly; use local speech/audio analysis evidence.',
    }
    general = {
        'supported': True,
        'available': True,
        'detail': 'Tony-authorized local assistant tasks (engineering, research, scripting, file/shell/web help) are permitted alongside video production.',
    }
    dispatch = {
        'supported': True,
        'available': True,
        'detail': 'neural_assign/neural_dispatch' if kind == 'codex' else 'POST /api/tasks and /api/dispatch with token',
    }
    return {
        'vision': bool(images_ok),
        'images': images,
        'file_shell': file_shell,
        'network': network,
        'network_browser': network,
        'local_ops': local_ops,
        'native_ae': native,
        'audio': audio,
        'listening': listening,
        'general_assistant': general,
        'general_assistant_tasks': general,
        'station_dispatch': dispatch,
    }


def tools_manifest(root=None, runtime=None):
    """Common manifest: every tool, with its status per profile. Missing support is labelled, never faked."""
    names = {
        'images': 'Screenshots (up to 10)',
        'file_shell': 'Files and shell',
        'network_browser': 'Network / web research',
        'local_ops': 'Shared local ops',
        'native_ae': 'Native After Effects (single writer)',
        'station_dispatch': 'Station specialists',
        'audio': 'Local audio / dictation (host)',
        'listening': 'Direct model audio listening',
        'general_assistant_tasks': 'General assistant + editorial',
    }
    out = []
    for key, label in names.items():
        per = {}
        for p in PROFILE_DEFS:
            cap = _capabilities(p, root=root, runtime=runtime)[key]
            status = cap.get('status') or ('supported' if cap['supported'] else 'unavailable')
            per[p['id']] = {'status': status, 'detail': cap['detail']}
        out.append({'id': key, 'label': label, 'profiles': per})
    return out


def _default_profile_id(leader):
    provider = leader.get('provider') or 'codex'
    model = str(leader.get('model') or '')
    if provider == 'claude':
        return 'claude-sonnet' if model == 'sonnet' else 'claude-opus'
    if provider == 'antigravity':
        for p in PROFILE_DEFS:
            if p['provider'] == 'antigravity' and p['model'] == model and not p.get('lumen'):
                return p['id']
    return 'sol-high'


def _window_reset_ok(reset_val, now):
    if isinstance(reset_val, (int, float)):
        return reset_val <= now
    return False


class DirectorSelector:
    def __init__(self, service):
        self.service = service
        self.path = Path(service.root) / SELECTION_FILE
        self.lock = threading.RLock()
        try:
            self.state = load(self.path)
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault('version', 1)
        self.state.setdefault('selected', None)
        self.state.setdefault('explicit', False)
        self.state.setdefault('pending', None)
        self.state.setdefault('sessions', {})
        self.state.setdefault('history', [])
        self.state.setdefault('human_selection_generation', 0)

    # ------------------------------------------------------------ persistence
    def _persist(self):
        self.state['history'] = self.state['history'][-60:]
        save(self.path, self.state)

    def explicit(self):
        return bool(self.state.get('explicit') and self.state.get('selected') in BY_ID)

    # --------------------------------------------------------------- profiles
    def _profile(self, profile_id):
        p = dict(BY_ID[profile_id])
        if profile_id == 'sol-high':
            policy = self.service.director_policy()
            p['model'] = policy.get('primary_model') or p['model']
            p['effort'] = policy.get('primary_effort') or p.get('effort')
        if p.get('lumen'):
            try:
                learner = load(Path(self.service.root) / 'data/workflow-apprentice/STATE.json')
                p['model'] = learner.get('model') or p['model']
                p['provider'] = learner.get('provider') or p['provider']
            except (OSError, ValueError):
                pass
        return p

    def selected_id(self):
        sel = self.state.get('selected')
        if sel in BY_ID:
            return sel
        return _default_profile_id(self.service.saved.get('leader', {}))

    def availability(self, profile):
        """Dated, honest status. Unknown allowance is reported as unknown, never zero."""
        svc = self.service
        saved = svc.saved
        now = time.time()
        kind = profile['kind']
        if kind == 'codex':
            row = saved.get('usage', {}).get('codex', {})
            windows = row.get('windows') or []
            percents = [w['remaining_percent'] for w in windows if isinstance(w.get('remaining_percent'), (int, float))]
            resets = [w.get('reset_at') for w in windows if w.get('reset_at') is not None]
            try:
                exhausted = svc._codex_exhausted()
            except Exception:
                exhausted = bool(saved.get('codex_quota_exhausted'))
            if exhausted:
                return {
                    'status': 'quota_exhausted',
                    'resting': True,
                    'quota': 'reported',
                    'remaining_percent': min(percents) if percents else 0,
                    'reset_at': resets[0] if resets else None,
                    'fresh': False,
                    'detail': 'Reported Codex allowance is exhausted until its reset.',
                    'checked_at': row.get('checked_at'),
                }
            if row.get('status') == 'reported' and windows:
                return {
                    'status': 'available',
                    'resting': False,
                    'quota': 'reported',
                    'remaining_percent': min(percents) if percents else None,
                    'reset_at': resets[0] if resets else None,
                    'fresh': True,
                    'detail': 'Allowance reported above reserve.',
                    'checked_at': row.get('checked_at'),
                }
            return {
                'status': 'unknown',
                'resting': False,
                'quota': 'unknown',
                'detail': 'Codex allowance has not been read; unknown is not zero.',
                'checked_at': row.get('checked_at'),
            }
        if kind == 'claude':
            try:
                from claude_transport import find_claude
                installed = bool(find_claude())
            except Exception:
                installed = False
            if not installed:
                return {
                    'status': 'unavailable',
                    'resting': False,
                    'quota': 'unknown',
                    'detail': 'Native Claude Code CLI was not found on this PC.',
                    'checked_at': None,
                }
            ex = saved.get('native_claude_exhausted')
            if ex and not _window_reset_ok(ex.get('reset_at'), now):
                return {
                    'status': 'quota_exhausted',
                    'resting': True,
                    'quota': 'reported',
                    'remaining_percent': 0,
                    'reset_at': ex.get('reset_at'),
                    'fresh': False,
                    'detail': 'Native Claude refused for allowance: ' + str(ex.get('reason', ''))[:300],
                    'checked_at': ex.get('reported_at'),
                }
            return {
                'status': 'unknown',
                'resting': False,
                'quota': 'unknown',
                'detail': 'Native Claude CLI installed; remaining allowance is not exposed unless the provider refuses (unknown is not zero).',
                'checked_at': None,
            }
        # antigravity
        headless = getattr(svc.runtime, 'headless', None)
        try:
            snap = (headless.snapshot() if headless else {}).get('antigravity', {})
        except Exception:
            snap = {}
        models = snap.get('models') or []
        if headless is None or not getattr(headless, 'agy', True):
            return {
                'status': 'unavailable',
                'resting': False,
                'quota': 'unknown',
                'detail': 'The Antigravity CLI adapter is not installed or not connected.',
                'checked_at': None,
            }
        if models and profile['model'] not in models:
            return {
                'status': 'unavailable',
                'resting': False,
                'quota': 'unknown',
                'detail': 'Exact model ID ' + profile['model'] + ' is not in the installed Antigravity model list.',
                'checked_at': None,
            }
        row = saved.get('usage', {}).get('antigravity') or {}
        windows = row.get('windows') or (snap.get('quota') or {}).get('windows') or []
        checked_at = row.get('checked_at') or (snap.get('quota') or {}).get('checked_at_unix')
        try:
            groups = svc._model_groups(profile['model'])
        except Exception:
            groups = set()
        matched = [w for w in windows if w.get('name', '').split(' · ')[0] in groups and isinstance(w.get('remaining_percent'), (int, float))]
        low = [w for w in matched if w['remaining_percent'] <= 1 and not _window_reset_ok(w.get('reset_at'), now)]
        min_rem = min((w['remaining_percent'] for w in matched), default=None)
        first_reset = next((w.get('reset_at') for w in (low or matched) if w.get('reset_at') is not None), None)
        if low:
            return {
                'status': 'quota_exhausted',
                'resting': True,
                'quota': row.get('status', 'cached'),
                'remaining_percent': min_rem,
                'reset_at': first_reset,
                'fresh': False,
                'detail': 'Reported account group allowance is at/below 1%. No probing or overage.',
                'checked_at': checked_at,
            }
        if models and windows:
            return {
                'status': 'available',
                'resting': False,
                'quota': row.get('status', 'cached'),
                'remaining_percent': min_rem,
                'reset_at': first_reset,
                'fresh': row.get('status') == 'reported',
                'detail': 'Model installed; last reported group allowance is dated, not a guarantee.',
                'checked_at': checked_at,
            }
        return {
            'status': 'unknown',
            'resting': False,
            'quota': 'unknown',
            'detail': 'Antigravity model list or allowance has not been verified yet.',
            'checked_at': checked_at,
        }

    def snapshot(self):
        self.reconcile()
        selected = self.selected_id()
        profiles = []
        for p in PROFILE_DEFS:
            full = self._profile(p['id'])
            conv = self._conversation(full)
            session_status = (
                'Saved thread ' + str(conv['id_prefix'])
                if conv['saved'] and conv.get('id_prefix')
                else ('Dedicated Lumen director thread + playbook' if full.get('lumen') else 'Durable profile session')
            )
            profiles.append({
                'id': full['id'],
                'label': full['label'],
                'provider': full['provider'],
                'model': full['model'],
                'role': full['role'],
                'availability': self.availability(full),
                'capabilities': _capabilities(full, root=self.service.root, runtime=self.service.runtime),
                'selected': full['id'] == selected,
                'conversation': conv,
                'has_session': conv['saved'],
                'thread_id': conv['id_prefix'],
                'session_status': session_status,
            })
        leader = self.service.saved.get('leader', {})
        pending = self.state.get('pending')
        if isinstance(pending, dict) and 'detail' not in pending:
            pending = {**pending, 'detail': pending.get('reason', '')}
        detail = ('Selection applies only at a safe boundary; a running or unknown turn is never cancelled or replaced.'
                  + (' Pending: ' + pending['profile_id'] + ' — ' + pending.get('reason', '') if pending else ''))
        return {
            'profiles': profiles,
            'selected': selected,
            'explicit': self.explicit(),
            'pending': pending,
            'tools': tools_manifest(root=self.service.root, runtime=self.service.runtime),
            'actual': {k: leader.get(k) for k in ('status', 'provider', 'model', 'turn_id')},
            'detail': detail,
            'model_calls': 0,
        }

    def _conversation(self, profile):
        """Which saved provider conversation this profile resumes (IDs shortened; never a credential)."""
        leader = self.service.saved.get('leader', {})
        sessions = self.state.get('sessions', {})
        if profile['kind'] == 'codex':
            sid = leader.get('thread_id')
        elif profile['kind'] == 'claude':
            sid = leader.get('claude_session_id') if self._claude_current_model() == profile['model'] else sessions.get('claude:' + profile['model'])
        else:
            key = self.agy_session_key(profile)
            sid = (self.service.saved.get('gemini_director_sessions', {}).get(key) or {}).get('session_id')
        return {'saved': bool(sid), 'id_prefix': str(sid)[:8] if sid else None}

    def _claude_current_model(self):
        return self.state.get('claude_active_model') or 'opus'

    def agy_session_key(self, profile):
        scope = str(self.service.saved.get('director_context_scope', 'tuf'))
        return ('lumen:' if profile.get('lumen') else '') + scope + ':' + profile['model']

    # --------------------------------------------------------------- boundary
    def boundary(self, target_id):
        """Return (kind, reason) where kind is None when switching is safe, 'queued' or 'blocked'."""
        svc = self.service
        leader = svc.saved['leader']
        status = leader.get('status')
        if status in UNKNOWN:
            return 'blocked', 'The current director turn has an unknown outcome. Reconcile its remote/native execution first; no second director may start.'
        editor = getattr(svc.runtime, 'lumen_editor', None)
        try:
            owns = bool(editor and editor.owns_editor() is True)
        except Exception:
            owns = True  # unreadable ownership is treated as owned
        if owns and target_id == 'lumen':
            return 'blocked', 'A Lumen trial editor owns the editing lane; Lumen as director would be a second writer.'
        if status in BUSY:
            return 'queued', 'A director turn is ' + status + '. It will not be cancelled or replaced; the choice applies after it finishes.'
        if owns:
            return 'queued', 'A Lumen trial owns the editing lane; the choice applies after it is released.'
        try:
            pending = svc._handoff_native_pending()
        except Exception:
            pending = 'unreadable-native-command'
        if pending == 'unreadable-native-command':
            return 'blocked', 'The native command record is unreadable; reconcile TonyFX before switching directors.'
        if pending:
            return 'queued', 'Native command ' + str(pending) + ' is unresolved; the choice applies after its exact result is recorded.'
        engine = getattr(svc.runtime, 'local_ops', None)
        try:
            if engine and engine.snapshot().get('active'):
                return 'queued', 'Local execution is active; the choice applies when it reaches a terminal state.'
        except Exception:
            return 'blocked', 'Local execution state could not be read.'
        try:
            if any(j.get('status') in svc.runtime.active_states for j in svc.runtime.jobs()):
                return 'queued', 'A station worker job is active; the choice applies when it finishes.'
        except Exception:
            return 'blocked', 'Station worker state could not be read.'
        if any(w.get('status') == 'waiting' for w in svc.saved.get('watches', {}).values()):
            return 'queued', 'A registered completion watch is waiting; the choice applies after the exact result arrives.'
        return None, ''

    # ------------------------------------------------------------------ select
    def _reconcile_stopped_owner(self):
        """Explicit switch only: recover stale restart state from a terminal host receipt.

        Never infer that an unknown remote operation stopped from a missing PID.
        An unverified result, active processing or pending native command stays blocked.
        """
        svc = self.service
        leader = svc.saved['leader']
        if leader.get('status') != 'uncertain' or leader.get('provider') not in ('antigravity', 'claude'):
            return False
        try:
            folder = Path(svc.saved.get('director_route', {}).get('run', '')).resolve()
            allowed = (Path(svc.root) / 'data/command/director-runs').resolve()
            if not folder.is_relative_to(allowed):
                return False
            result = load(folder / 'RESULT.json')
            if (result.get('status') not in ('FAILED', 'COMPLETED') or result.get('process_stopped') is not True
                    or result.get('idle_inference') is not False or result.get('model') != leader.get('model')):
                return False
            sessions = {r.get('session_id') for r in svc.saved.get('gemini_director_sessions', {}).values() if isinstance(r, dict)}
            sessions.update((leader.get('claude_session_id'), leader.get('backup_session_id')))
            if not result.get('session_id') or result['session_id'] not in sessions:
                return False
            if svc._handoff_native_pending():
                return False
            engine = getattr(svc.runtime, 'local_ops', None)
            if engine and engine.snapshot().get('active'):
                return False
            if any(j.get('status') in svc.runtime.active_states for j in svc.runtime.jobs()):
                return False
            if any(w.get('status') == 'waiting' for w in svc.saved.get('watches', {}).values()):
                return False
            editor = getattr(svc.runtime, 'lumen_editor', None)
            if editor and editor.owns_editor():
                return False
        except (OSError, ValueError, TypeError, AttributeError):
            return False
        leader.update(status='interrupted', turn_id=None,
                      error='Previous director ended; its terminal host result was reconciled before this explicit switch.')
        svc.saved['backup_suppressed'] = True
        svc.saved['continuation_authorized'] = False
        svc._record('director', 'Stopped director reconciled',
                    'Verified terminal ' + result['status'] + ' receipt. Conversations and job results preserved; nothing replayed.', 'completed')
        svc._persist()
        return True

    def select(self, data):
        from lumen_editor import EDITOR_LOCK
        profile_id = data.get('profile_id')
        if profile_id not in BY_ID:
            raise ValueError('Unknown director profile')
        want_continue = data.get('continue') is True
        if data.get('continue') not in (None, True, False):
            raise ValueError('continue must be true or false')
        expected = data.get('expected_turn_id')
        if expected is not None and not isinstance(expected, str):
            raise ValueError('expected_turn_id must be a string or null')
        with EDITOR_LOCK, self.service.lock, self.lock:
            leader = self.service.saved['leader']
            if expected is not None and expected != leader.get('turn_id'):
                return self._reply('blocked', 'The director turn changed since this screen was loaded; refresh before choosing.')
            # This is a human choice even when it queues or selects the same
            # profile. It supersedes any older automatic succession request.
            self.state['human_selection_generation'] = self.state.get('human_selection_generation', 0) + 1
            self._persist()
            self._reconcile_stopped_owner()
            if self.state.get('selected') == profile_id and self.state.get('explicit') and not self.state.get('pending'):
                return self._reply('selected', 'Already selected.', self._maybe_continue(want_continue, applied=False))
            kind, reason = self.boundary(profile_id)
            if kind == 'blocked':
                self._record_history(profile_id, 'blocked', reason)
                return self._reply('blocked', reason)
            if kind == 'queued':
                self.state['pending'] = {
                    'profile_id': profile_id,
                    'requested_at': stamp(),
                    'continue': want_continue,
                    'reason': reason,
                    'detail': reason,
                    'checkpoint': self._checkpoint('queued', profile_id),
                }
                self._record_history(profile_id, 'queued', reason)
                self.service._record('director', 'Director selection queued', profile_id + ' · ' + reason, 'waiting')
                self._persist(); self.service._persist()
                return self._reply('queued', reason)
            self._apply(profile_id, 'selected')
            note = self._maybe_continue(want_continue, applied=True)
            return self._reply('selected', 'Selected ' + profile_id + '.' + (' ' + note if note else ''))

    def _reply(self, status, detail, extra=''):
        return {'status': status, 'selected': self.selected_id(), 'pending': self.state.get('pending'), 'detail': (detail + ' ' + extra).strip()}

    def _maybe_continue(self, want, applied):
        if not want:
            return ''
        if (self.service.saved.get('production_pause') or {}).get('disposition') == 'manual_finish':
            return 'Selection saved. This revision was handed to Tony; send a new direction to start work.'
        # Continuation uses the existing director engine/session, never a competing worker.
        try:
            # This button is an explicit human resume, including after a prior pause.
            self.service.send(CONTINUE_TEXT, internal=False)
            return 'Continuation started through the existing director engine.'
        except ValueError as e:
            return 'Selection saved, but continuation was not started: ' + str(e)

    def _checkpoint(self, why, target_id):
        svc = self.service
        leader = svc.saved['leader']
        try:
            native = svc._handoff_native_pending()
        except Exception:
            native = 'unreadable'
        cp = {'at': stamp(), 'why': why, 'from': self.selected_id(), 'to': target_id,
              'leader': {k: leader.get(k) for k in ('status', 'provider', 'model', 'thread_id', 'turn_id', 'claude_session_id')},
              'sessions': self.state.get('sessions', {}), 'watches': json.loads(json.dumps(svc.saved.get('watches', {}), default=str)),
              'native_pending_command': native, 'production_direction': svc.saved.get('production_direction'),
              'rule': 'Pending exact jobs/watches stay attached to their IDs; nothing here is replayed.'}
        path = Path(svc.root) / 'data/command/checkpoints' / ('director-select-' + uuid.uuid4().hex + '.json')
        save(path, cp)
        return str(path)

    def _record_history(self, profile_id, outcome, detail):
        self.state['history'].append({'at': stamp(), 'profile_id': profile_id, 'outcome': outcome, 'detail': detail[:400]})
        self._persist()

    def _apply(self, profile_id, outcome):
        """Switch selection. Saves the outgoing conversation IDs and restores the target's; never clears any."""
        svc = self.service
        leader = svc.saved['leader']
        prev = self.selected_id()
        target = BY_ID[profile_id]
        cp = self._checkpoint('apply', profile_id)
        sessions = self.state.setdefault('sessions', {})
        active_claude = self._claude_current_model()
        if leader.get('claude_session_id') and 'claude:' + active_claude not in sessions:
            sessions['claude:' + active_claude] = leader['claude_session_id']
        # Keep each native Claude model's conversation separate (legacy ID belongs to Opus).
        if target['kind'] == 'claude':
            if leader.get('claude_session_id'):
                sessions['claude:' + active_claude] = leader['claude_session_id']
            incoming = sessions.get('claude:' + target['model'])
            if incoming:
                leader['claude_session_id'] = incoming
            else:
                leader.pop('claude_session_id', None)  # fresh model conversation; the saved ID stays in the map
            self.state['claude_active_model'] = target['model']
        self.state.update(selected=profile_id, explicit=True, pending=None)
        self._record_history(profile_id, outcome, 'from ' + prev + ' · checkpoint ' + Path(cp).name)
        svc._record('director', 'Director selected', profile_id + ' · saved conversations preserved; no model started', 'completed')
        svc._persist()
        self._persist()

    # --------------------------------------------------------------- reconcile
    def reconcile(self):
        """Apply a queued selection once its boundary has actually cleared. Never launches inference."""
        if not self.state.get('pending'):
            return False
        from lumen_editor import EDITOR_LOCK
        with EDITOR_LOCK, self.service.lock, self.lock:  # same order as select(): no lock inversion
            pending = self.state.get('pending')
            if not pending:
                return False
            kind, reason = self.boundary(pending['profile_id'])
            if kind == 'blocked':
                pending['reason'] = reason
                pending['detail'] = reason
                self._persist()
                return False
            if kind == 'queued':
                pending['reason'] = reason
                pending['detail'] = reason
                return False
            self._apply(pending['profile_id'], 'applied-from-queue')
            if pending.get('continue'):
                self.state['history'].append({'at': stamp(), 'profile_id': pending['profile_id'], 'outcome': 'continuation-needs-explicit-action',
                                              'detail': 'Continuation was requested before the boundary cleared; it is never auto-started.'})
                self._persist()
            return True

    # ----------------------------------------------------------------- routing
    def route(self):
        """Route for the next explicit send, or None to keep the legacy engine policy untouched."""
        self.reconcile()
        if not self.explicit():
            return None
        profile = self._profile(self.state['selected'])
        return profile

    def lumen_preface(self):
        """Lumen's real, current lessons/skills as retrieved instructions (not trained weights)."""
        root = Path(self.service.root)
        from workflows import WorkflowProfiles
        workflow = WorkflowProfiles(root).snapshot()
        wid = workflow['id']
        try:
            entries = [r for r in load(root / 'data/workflow-apprentice/MISTAKE_LEDGER.json').get('entries', []) if r.get('workflow_id', 'tuf') == wid]
        except (OSError, ValueError):
            entries = []
        lessons = [{k: str(v)[:500] for k, v in r.items() if k in ('id', 'category', 'mistake', 'correction', 'rule', 'fix', 'lesson')} for r in entries[-20:]]
        skills = []
        for p in sorted((root / 'knowledge/skills').glob('*/SKILL.md')):
            try:
                skills.append({'name': p.parent.name, 'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()[:16]})
            except OSError:
                continue
        value = {'role': 'Lumen director profile', 'workflow': {'id': wid, 'sha256': workflow.get('sha256')}, 'lessons_total': len(entries), 'lessons': lessons,
                 'skills': skills[:60], 'playbook': 'shared/APPRENTICE_PLAYBOOK.md',
                 'authority': 'Lessons and skills are retrieved instructions, not trained weights. Read each relevant SKILL.md before native work. '
                              'You are the director through the same single-writer tool lane; the separate Lumen trial editor must not run concurrently.'}
        text = json.dumps(value, ensure_ascii=False)
        while len(text) > 14000 and value['lessons']:
            value['lessons'].pop(0)
            text = json.dumps(value, ensure_ascii=False)
        return '\nLUMEN DIRECTOR PROFILE (current lessons/skills; context, not a new assignment):\n' + text + '\n\n', value


def run_manual_turn(service, profile, text, images):
    """Execute one explicitly selected director turn via the existing provider engines (no fallback)."""
    kind = profile['kind']
    caps = _capabilities(profile, root=service.root, runtime=service.runtime)
    if kind == 'claude':
        route = [{'provider': 'claude', 'model': profile['model'], 'manual': True, 'profile_id': profile['id']}]
        return service._native_director_turn(text, route, images=images)
    preface, value = ('', None)
    if profile.get('lumen'):
        preface, value = service.selector.lumen_preface()
    session_key = service.selector.agy_session_key(profile)
    return service._backup_turn(
        preface + text,
        models_override=[profile['model']],
        images=images,
        session_key=session_key,
        manual_profile={
            'id': profile['id'],
            'label': profile['label'],
            'lumen_lessons': (value or {}).get('lessons_total'),
            'vision_commissioned': bool(caps['vision']),
        },
    )
