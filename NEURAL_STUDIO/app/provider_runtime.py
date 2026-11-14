"""Headless provider transports, truthful events, and external result observation.

Nothing here starts inference on construction or on an idle status refresh.
OpenCode jobs are app-owned processes. Antigravity agentapi is a detached relay:
its subprocess ending does not prove that the remote agent stopped or finished.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import closing
from pathlib import Path
from typing import Any, Callable
import json
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import threading
import time
from urllib.parse import urlparse


FREE_OPENCODE_ID = re.compile(r'opencode/[a-z0-9][a-z0-9_.-]*-free')


# BF6 (7 Nov 2026): permission keys found in the installed OpenCode v2.2.5 binary (tool ids: shell, webfetch, websearch, edit, patch,
# write, read, grep, glob, subagent, external_directory). `bash` and `task` are the names older/upstream configs use; they are denied as
# well so a rename cannot silently re-enable them. Read tools stay available (denying them returns the free-tier 429, evidence/af1).
OPENCODE_DENY_KEYS = {k: 'deny' for k in ('edit', 'write', 'patch', 'shell', 'bash', 'webfetch', 'websearch', 'subagent', 'task', 'browser', 'external_directory')}


class FreeOpenCodeModels(frozenset):
    """Exact ``opencode/*-free`` IDs only. Seeded with IDs seen in the installed v2.2.5 catalog (7 Nov 2026); the live
    catalog (``ProviderRuntime.list_opencode_models``) is the authority. Membership never admits other providers or non-free IDs."""
    def __contains__(self, item):
        return isinstance(item, str) and FREE_OPENCODE_ID.fullmatch(item) is not None


FREE_OPENCODE_MODELS = FreeOpenCodeModels({
    'opencode/beam-free', 'opencode/crouton-alpha-free', 'opencode/deepseek-v4.1-flash-free', 'opencode/flint-40b-free',
    'opencode/glm-5.3-flash-free', 'opencode/iceman-free', 'opencode/inkling-2-small-free', 'opencode/mimo-v2.6-flash-free',
    'opencode/nemotron-3.5-lightning-free', 'opencode/nemotron-3.5-super-vl-free'})
ANTIGRAVITY_ROUTES = frozenset({'flash_lite', 'flash', 'pro'})
# Public defaults from the installed app.asar /dist/languageServer.js startup.
ANTIGRAVITY_CLOUD_ENDPOINT = 'https://daily-cloudcode-pa.googleapis.com'
ANTIGRAVITY_API_ENDPOINT = 'https://generativelanguage.googleapis.com'
QUOTA_UNKNOWN = {'supported': False, 'remaining': None,
                 'reason': 'No supported remaining-account-quota command is exposed by this transport.'}
_SECRET_KEYS = ('API_KEY', 'ACCESS_TOKEN', 'CSRF_TOKEN', 'CLIENT_SECRET', 'AUTHORIZATION', 'PASSWORD')


def process_options() -> dict:
    return {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}


def clean_environment() -> dict:
    """Remove billable fallback and inherited relay credentials, without logging values."""
    env = os.environ.copy()
    for key in list(env):
        if any(fragment in key.upper() for fragment in _SECRET_KEYS):
            env.pop(key, None)
    for key in ['GOOGLE_GENAI_USE_VERTEXAI', 'GOOGLE_APPLICATION_CREDENTIALS', 'OPENAI_BASE_URL']:
        env.pop(key, None)
    for key in ['AGY_ADC_AUTH', 'GOOGLE_CLOUD_QUOTA_PROJECT', 'GOOGLE_GEMINI_BASE_URL']:
        env.pop(key, None)
    return env


def _safe(value: Any, depth: int = 0) -> Any:
    """Bound and redact provider event payloads before persisting them in the UI."""
    if depth > 5:
        return '[nested payload omitted]'
    if isinstance(value, dict):
        return {str(k): '[redacted]' if any(x in str(k).upper() for x in _SECRET_KEYS) else _safe(v, depth + 1)
                for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [_safe(v, depth + 1) for v in value[:40]]
    if isinstance(value, str):
        value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[redacted]', value)
        return value[:12000]
    return value if value is None or isinstance(value, (int, float, bool)) else str(value)[:1000]


def _number(value: Any) -> int | float | None:
    return value if type(value) in (int, float) and value >= 0 else None


def normalize_opencode_event(event: dict) -> dict | None:
    """Normalize only observed events; never manufacture tool activity or usage."""
    kind = event.get('type')
    part = event.get('part') if isinstance(event.get('part'), dict) else {}
    base = {'provider': 'opencode', 'actual': True, 'session_id': event.get('sessionID'),
            'timestamp': event.get('timestamp')}
    if kind == 'text':
        return {**base, 'kind': 'text', 'text': _safe(part.get('text', ''))}
    if kind in ('tool_use', 'tool') or part.get('type') == 'tool':
        state = part.get('state') if isinstance(part.get('state'), dict) else {}
        return {**base, 'kind': 'tool', 'tool': part.get('tool') or part.get('name') or 'unknown',
                'tool_call_id': part.get('callID') or part.get('id'),
                'status': state.get('status', 'unknown'), 'input': _safe(state.get('input')),
                'output': _safe(state.get('output')), 'error': _safe(state.get('error'))}
    if kind == 'step_finish':
        tokens = part.get('tokens') if isinstance(part.get('tokens'), dict) else {}
        cache = tokens.get('cache') if isinstance(tokens.get('cache'), dict) else {}
        usage = {k: _number(tokens.get(k)) for k in ('total', 'input', 'output', 'reasoning')}
        usage.update(cache_read=_number(cache.get('read')), cache_write=_number(cache.get('write')),
                     cost=_number(part.get('cost')))
        return {**base, 'kind': 'usage', 'usage': usage, 'source': 'provider_event',
                'reason': part.get('reason'), 'quota_remaining': None}
    if kind == 'error':
        return {**base, 'kind': 'error', 'error': _safe(event.get('error') or part.get('error'))}
    if kind in ('step_start', 'start'):
        return {**base, 'kind': 'progress', 'phase': kind}
    # Internal reasoning/thoughts are not forwarded as a progress transcript.
    return None


def _agy_usage(raw: Any) -> dict | None:
    if not isinstance(raw, dict):return None
    mapping = {'input_tokens': 'input', 'output_tokens': 'output', 'thinking_tokens': 'reasoning',
               'cache_read_tokens': 'cache_read', 'total_tokens': 'total'}
    return {target: _number(raw.get(source)) for source, target in mapping.items()}


def normalize_agy_event(event: dict) -> dict | None:
    """Official agy NDJSON protocol; step usage and terminal totals stay distinct."""
    kind = event.get('event')
    if kind == 'init':
        data = event.get('init') or {}
        return {'provider': 'antigravity', 'kind': 'progress', 'actual': True, 'phase': 'init',
                'session_id': event.get('conversation_id'), 'model': data.get('model'),
                'permission_mode': data.get('permission_mode'), 'available_tools': _safe(data.get('tools'))}
    if kind == 'step_update':
        data = event.get('step_update') or {}
        base = {'provider': 'antigravity', 'actual': True, 'session_id': data.get('conversation_id'),
                'step_index': data.get('step_index'), 'status': data.get('state'),
                'usage': _agy_usage(data.get('usage')), 'usage_scope': 'step'}
        if data.get('step_type') == 'tool':
            tool = data.get('tool_info') or {}
            return {**base, 'kind': 'tool', 'tool': data.get('tool_name') or tool.get('name') or 'unknown',
                    'input': _safe(tool.get('parameters')), 'output': _safe(tool.get('output')),
                    'error': _safe(tool.get('error'))}
        if data.get('step_type') == 'agent_response':
            return {**base, 'kind': 'text', 'text': _safe(data.get('text_delta', ''))}
        if data.get('step_type') in ('checkpoint', 'user_input'):
            return {**base, 'kind': 'progress', 'phase': data['step_type']}
        return None
    if kind == 'result':
        data = event.get('result') or {}
        return {'provider': 'antigravity', 'kind': 'result', 'actual': True,
                'session_id': data.get('conversation_id'), 'status': data.get('status'),
                'text': _safe(data.get('response', '')), 'error': _safe(data.get('error')),
                'usage': _agy_usage(data.get('usage')), 'usage_scope': 'session_total'}
    return None


def parse_agy_quota_report(report: str) -> list[dict]:
    """Parse observed official TSV quota rows; never estimate unreported buckets."""
    buckets = []
    for line in report.splitlines():
        columns = line.split('\t')
        if len(columns) != 4:continue
        group, label, percent, resets = columns
        match = re.fullmatch(r'(\d+(?:\.\d+)?)%', percent.strip())
        if not match or not 0 <= float(match.group(1)) <= 100:continue
        if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z', resets.strip()):continue
        buckets.append({'group': group, 'label': label, 'remaining_percent': float(match.group(1)),
                        'resets_at': resets.strip(), 'source': 'official_agy_usage', 'account_shared': True})
    return buckets


@dataclass(frozen=True)
class CommandSpec:
    provider: str
    argv: list[str] = field(repr=False)
    env: dict = field(repr=False)
    cwd: Path
    model: str | None = None
    cancellable: bool = True
    tool_policy: str = 'not reported'

    def public(self) -> dict:
        return {'provider': self.provider, 'cwd': str(self.cwd), 'model': self.model,
                'hidden_process': True, 'cancellable': self.cancellable, 'tool_policy': self.tool_policy}


class ProviderRuntime:
    def __init__(self, root: str | Path, *, run: Callable = subprocess.run,
                 popen: Callable = subprocess.Popen, home: str | Path | None = None):
        self.root = Path(root).resolve()
        self.home = Path(home) if home else Path.home()
        self.run, self.popen = run, popen
        self.opencode = self.resolve_opencode()
        self.antigravity = self.home / 'AppData/Local/Programs/antigravity/resources/bin/language_server.exe'
        self.helper = self.home / 'Documents/TFX_ANTIGRAVITY_STUDIO/tools/antigravity_agentapi.ps1'
        self.agy: Path | None = None
        self._agy_access_verified = False
        self._agy_models: list[str] = []
        self._agy_quota: dict | None = None
        self._agy_auth_required = False
        self._agy_models_checked_at: float | None = None
        self._agy_cache_path = self.root/'data/provider-cache/antigravity.json'
        self._load_agy_cache()
        self.refresh_agy()
        self._owned_host = None
        self._host_log = None
        self._host_env: dict | None = None
        self._host_state = 'NOT_STARTED'
        self._headless_verified = False
        self._last_host_error = 'Standalone headless login is not yet verified; a GUI sign-in is not proof of headless access.'

    def _load_agy_cache(self) -> None:
        try:
            cached = json.loads(self._agy_cache_path.read_text(encoding='utf-8'))
            models = cached.get('models', [])
            if isinstance(models, list):
                self._agy_models = [m for m in models[:500] if isinstance(m, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*-[A-Za-z0-9_.-]+', m)]
            self._agy_models_checked_at = _number(cached.get('models_checked_at_unix'))
            quota = cached.get('quota')
            if isinstance(quota, dict) and isinstance(quota.get('windows'), list):
                self._agy_quota = {k: quota[k] for k in ('supported','remaining','source','buckets','windows','checked_at_unix','account_shared') if k in quota}
                self._agy_quota.update(cached=True, fresh=False)
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _save_agy_cache(self) -> None:
        # Only model IDs and quota windows. Never persist authentication material or diagnostics.
        quota = None if self._agy_quota is None else {k: self._agy_quota[k] for k in ('supported','remaining','source','buckets','windows','checked_at_unix','account_shared') if k in self._agy_quota}
        data = {'version': 1, 'models': list(self._agy_models),
                'models_checked_at_unix': self._agy_models_checked_at, 'quota': quota}
        self._agy_cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._agy_cache_path.with_suffix('.'+secrets.token_hex(4)+'.tmp')
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(self._agy_cache_path)

    def refresh_agy(self) -> Path | None:
        """Locate official CLI, including private install; no downloads or processes."""
        found = shutil.which('agy')
        candidates = [self.root/'.tools/agy/agy.exe', self.home/'AppData/Local/agy/bin/agy.exe',
                      self.home/'.local/bin/agy', self.home/'.local/bin/agy.exe']
        if found:candidates.append(Path(found))
        self.agy = next((p.resolve() for p in candidates if p.is_file()), None)
        return self.agy

    def snapshot(self) -> dict:
        """Filesystem/process state only: zero model calls, zero implicit launches."""
        alive = self._owned_host is not None and self._owned_host.poll() is None
        result = {
            'opencode': {'installed': self.opencode.is_file(), 'available': self.opencode.is_file(),
                         'headless': True, 'authentication': 'Verified by each job; no paid fallback',
                         'access_verified': False, 'models': sorted(FREE_OPENCODE_MODELS),
                         'exact_model_ids': True, 'idle_inference': False, 'quota': dict(QUOTA_UNKNOWN),
                         'capabilities': {'tool_events': True, 'job_usage': True, 'local_cancellation': True,
                                          'headless_server': True, 'model_listing': True, 'historical_statistics': True}},
            'antigravity': {'installed': self.antigravity.is_file(),
                            'available': bool(alive and self._headless_verified),
                            'headless_supported': True, 'headless_verified': self._headless_verified,
                            'transport_state': self._host_state,
                            'authentication': 'Not verified by metadata', 'access_verified': False,
                            'reason': self._last_host_error, 'route_aliases': sorted(ANTIGRAVITY_ROUTES),
                            'models': [], 'exact_model_ids': False, 'idle_inference': 'unknown',
                            'quota': dict(QUOTA_UNKNOWN),
                            'capabilities': {'dispatch_relay': True, 'metadata': True, 'task_file_results': True,
                                             'tool_events': False, 'job_usage': False, 'remote_cancellation': False,
                                             'model_listing': False}},
        }
        ag = result['antigravity']
        ag.update(official_cli_installed=bool(self.agy and self.agy.is_file()),
                  official_cli_path=str(self.agy) if self.agy else None,
                  official_cli_docs='https://www.antigravity.google/docs/cli/headless/')
        if ag['official_cli_installed']:
            ag.update(installed=True, available=True, headless_supported=True, transport='agy_headless',
                      authentication='Native shared keyring; verify with explicit read-only quota report',
                      reason='Official CLI installed; access verified by read-only model/quota checks and each explicit task.',
                      exact_model_ids=True, idle_inference=False,
                      quota={'supported': True, 'remaining': None, 'source': 'agy --print /usage', 'reason': 'Not checked'},
                      capabilities={'tool_events': True, 'job_usage': True, 'local_cancellation': True,
                                    'model_listing': True, 'quota_report': True, 'headless': True,
                                    'provider_tools': 'provider-managed; task-scoped by instructions only',
                                    'native_AE': False})
            ag.update(access_verified=self._agy_access_verified, models=list(self._agy_models))
            ag.update(models_checked_at_unix=self._agy_models_checked_at,
                      cached_metadata=bool((self._agy_quota or {}).get('cached') or self._agy_models and not self._agy_access_verified),
                      auth_state='required' if self._agy_auth_required else 'verified' if self._agy_access_verified else 'unknown')
            if self._agy_auth_required:
                ag.update(available=False, authentication='Headless account authorization required', reason='Official CLI explicitly reported authentication required')
            elif not self._agy_access_verified and (self._agy_models or self._agy_quota):
                ag['reason'] = 'Previously verified account metadata loaded from cache; fresh access check pending. Cached quota timestamps remain visible.'
            if self._agy_access_verified:
                ag['authentication'] = 'Native shared keyring verified by official read-only quota report'
                ag['reason'] = 'Official headless account access verified; no model inference was used for connection checks.'
            if self._agy_quota is not None:ag['quota'] = dict(self._agy_quota)
        else:
            ag['reason'] = 'Official agy CLI is not installed. Legacy native-host status: '+self._last_host_error
        return result

    def agy_discovery_commands(self) -> dict:
        if not self.agy or not self.agy.is_file():raise ValueError('Official Antigravity CLI is not installed')
        client = str(self.agy)
        return {'help': [client, '--help'], 'version': [client, '--version'], 'models': [client, 'models'],
                'model_report': [client, '--print', '/model'], 'quota': [client, '--print', '/usage']}

    def inspect_agy_local_session(self, session_id: str) -> dict:
        """Read the official CLI's local session index; never infer remote cancellation."""
        if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', str(session_id)):
            raise ValueError('Invalid Antigravity conversation ID')
        path = self.home/'.gemini/antigravity-cli/conversation_summaries.db'
        result = {'session_id': session_id, 'source': 'official_cli_local_conversation_index',
                  'checked_at_unix': time.time(), 'local_idle': False, 'inference_started': False}
        if not path.is_file():return {**result, 'detail': 'Local session index is unavailable'}
        try:
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=1)) as db:
                row = db.execute('SELECT status,not_fully_idle,killed,last_modified_time FROM conversation_summaries WHERE conversation_id=?', (session_id,)).fetchone()
            if not row:return {**result, 'detail': 'Conversation is not present in the local index'}
            status, busy, killed, modified = row
            return {**result, 'status': status, 'not_fully_idle': bool(busy), 'killed': bool(killed),
                    'last_modified_time': modified,
                    'local_idle': status == 'CASCADE_RUN_STATUS_IDLE' and busy == 0}
        except (OSError, sqlite3.Error) as exc:
            return {**result, 'detail': 'Local session status could not be verified: '+str(exc)[:200]}

    def query_agy(self, kind: str, *, timeout: float = 60) -> dict:
        """Explicit documented non-inference query; no TTY, browser, API-key or ADC fallback."""
        commands = self.agy_discovery_commands()
        if kind not in commands:raise ValueError('Unsupported read-only CLI query')
        try:
            result = self.run(commands[kind], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', env=clean_environment(), timeout=timeout,
                              **process_options())
            report = result.stdout
            diagnostics = result.stderr
            auth_required = any(x in (report+diagnostics).lower() for x in ['authentication required', 'not authenticated', 'please sign in', 'accounts.google.com/o/oauth2'])
            models = []
            if kind == 'models' and result.returncode == 0:
                for line in report.splitlines():
                    match = re.match(r'^\s*([A-Za-z][A-Za-z0-9_.-]*-[A-Za-z0-9_.-]+)\s', line+' ')
                    if match:models.append(match.group(1))
            if kind == 'models' and result.returncode == 0:
                self._agy_models = list(dict.fromkeys(models))
                self._agy_models_checked_at = time.time()
            quota = {'supported': True, 'remaining': None, 'source': 'official_cli_text_report',
                     'report': _safe(report) if kind == 'quota' and result.returncode == 0 and not auth_required else None,
                     'buckets': parse_agy_quota_report(report) if kind == 'quota' and result.returncode == 0 and not auth_required else [],
                     'checked_at_unix': time.time(), 'account_shared': True, 'cached': False, 'fresh': True}
            quota['windows'] = [{'name': b['group']+' · '+b['label'], 'remaining_percent': b['remaining_percent'],
                                 'reset_at': b['resets_at']} for b in quota['buckets']]
            if kind == 'quota' and result.returncode == 0 and not auth_required:
                self._agy_quota = quota
                self._agy_access_verified = True
            if auth_required:
                self._agy_access_verified = False
                self._agy_auth_required = True
                if self._agy_quota:self._agy_quota.update(cached=True, fresh=False)
            elif result.returncode == 0:
                self._agy_auth_required = False
                self._save_agy_cache()
            return {'kind': kind, 'status': 'AUTH_REQUIRED' if auth_required else 'OK' if result.returncode == 0 else 'FAILED',
                    'models': list(dict.fromkeys(models)), 'report': None if auth_required else _safe(report),
                    'error': 'Headless account authorization required; run agy interactively only when explicitly requested.' if auth_required else _safe(diagnostics) if result.returncode else None,
                    'inference_started': False, 'access_verified': kind in ('quota', 'model_report') and result.returncode == 0 and not auth_required,
                    'quota': quota}
        except (OSError, subprocess.TimeoutExpired) as failure:
            if self._agy_quota:self._agy_quota.update(cached=True, fresh=False)
            return {'kind': kind, 'status': 'UNAVAILABLE', 'inference_started': False,
                    'error': 'Read-only CLI metadata timed out' if isinstance(failure, subprocess.TimeoutExpired) else 'Read-only CLI metadata transport unavailable',
                    'failure_kind': 'timeout' if isinstance(failure, subprocess.TimeoutExpired) else 'transport',
                    'auth_state': 'required' if self._agy_auth_required else 'verified' if self._agy_access_verified else 'unknown',
                    'access_verified': self._agy_access_verified, 'authentication_required': self._agy_auth_required,
                    'models': list(self._agy_models), 'quota': dict(self._agy_quota) if self._agy_quota is not None else None}

    def build_agy(self, model: str, job_dir: str | Path, title: str = 'Neural bounded worker', *, timeout: int = 3600,
                  effort: str | None = None, schema: str | Path | None = None,
                  mode: str = 'plan', read_tools: bool = False, unattended: bool = False, conversation: str | None = None) -> CommandSpec:
        """Official CLI one-turn stream; closes stdin and exits after its terminal result."""
        if not self.agy or not self.agy.is_file():raise ValueError('Official Antigravity CLI is not installed')
        if model in ('auto', 'flash', 'flash_lite', 'pro') or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*-[A-Za-z0-9_.-]+', model):
            raise ValueError('Pin an exact slug returned by agy models; route aliases are not exact models')
        if type(timeout) is not int or not 1 <= timeout <= 7200:raise ValueError('Invalid worker timeout')
        if effort is not None and effort not in ('low', 'medium', 'high'):raise ValueError('Invalid reasoning effort')
        if mode not in ('plan', 'accept-edits'):raise ValueError('Unsupported bounded worker execution mode')
        settings = self.home/'.gemini/antigravity-cli/settings.json'
        if settings.is_file():
            config = json.loads(settings.read_text(encoding='utf-8'))
            if config.get('modelProvider'):
                raise ValueError('API-key/custom provider mode is disabled; official account/keyring authentication is required')
            if not unattended and (config.get('toolPermission') in ('always-proceed', 'proceed-in-sandbox') or config.get('permissions', {}).get('allow')):
                raise ValueError('Existing CLI auto-allow permissions need a scoped configuration before bounded worker dispatch')
        work = Path(job_dir).resolve()
        work.mkdir(parents=True, exist_ok=True)
        args = [str(self.agy), '--input-format', 'stream-json', '--output-format', 'stream-json',
                '--model', model, '--print-timeout', str(timeout)+'s', '--mode', mode]
        if effort:args += ['--effort', effort]
        if conversation:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',conversation):raise ValueError('Invalid provider conversation ID')
            args += ['--conversation',conversation]
        if schema is not None:args += ['--json-schema', str(schema)]
        if unattended:args += ['--dangerously-skip-permissions']
        policy = 'provider-managed; task-scoped by instructions only'
        if unattended:policy += '; human-authorized unattended execution for this child process'
        if not read_tools:policy += '; no tool use requested'
        return CommandSpec('antigravity', args, clean_environment(), work, model, True, policy)

    def resolve_opencode(self) -> Path:
        """Newest installed desktop opencode-cli.exe, else the project's .tools client."""
        found = sorted((self.home / 'AppData/Roaming/ai.opencode.desktop/cli').glob('*/opencode-cli.exe'),
                       key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in re.split(r'[.\-]', p.parent.name)))
        return found[-1] if found else self.root / '.tools/node_modules/opencode-windows-x64/bin/opencode.exe'

    @property
    def opencode_desktop(self) -> bool:
        return self.opencode.name == 'opencode-cli.exe'

    def discovery_commands(self) -> dict:
        """Supported read-only CLI commands; invoking these cannot start inference."""
        return {'opencode_models': [str(self.opencode), 'models', '--standalone'] if self.opencode_desktop else [str(self.opencode), 'models', 'opencode', '--pure'],
                'opencode_statistics': [str(self.opencode), 'stats', '--models', '--pure'],
                'opencode_serve_help': [str(self.opencode), 'serve', '--help'],
                'antigravity_help': [str(self.antigravity), 'agentapi', '--help'],
                'antigravity_host_help': [str(self.antigravity), '--help']}

    def list_opencode_models(self, timeout: float = 15) -> dict:
        if not self.opencode.is_file():
            return {'models': [], 'error': 'OpenCode client is not installed', 'quota': dict(QUOTA_UNKNOWN)}
        try:
            result = self.run(self.discovery_commands()['opencode_models'], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=timeout,
                              env=clean_environment(), **process_options())
            candidates = {line.strip() for line in result.stdout.splitlines()}
            return {'models': sorted(m for m in candidates if m in FREE_OPENCODE_MODELS), 'source': 'installed_cli_model_list',
                    'access_verified': False, 'error': None if result.returncode == 0 else 'Model listing failed',
                    'quota': dict(QUOTA_UNKNOWN)}
        except (OSError, subprocess.TimeoutExpired):
            return {'models': [], 'error': 'Model listing unavailable', 'quota': dict(QUOTA_UNKNOWN)}

    def build_opencode(self, model: str, job_dir: str | Path, title: str,
                       *, subscription_oauth: bool = False, read_tools: bool = False, conversation: str | None = None) -> CommandSpec:
        if model not in FREE_OPENCODE_MODELS and not (subscription_oauth and re.fullmatch(r'github-copilot/[A-Za-z0-9_.:/-]+', model)):
            raise ValueError('Choose an explicit allowed free model, or a verified GitHub Copilot OAuth model; no fallback.')
        if not self.opencode.is_file():
            raise ValueError('OpenCode client is not installed')
        work = Path(job_dir).resolve()
        work.mkdir(parents=True, exist_ok=True)
        isolated = work / 'opencode-config'
        isolated.mkdir(exist_ok=True)
        permission: dict = {'*': 'deny'}
        if read_tools:
            permission.update({'read': 'allow', 'glob': 'allow', 'grep': 'allow', 'list': 'allow', 'external_directory': 'deny'})
        # AF1 (7 Nov 2026): setting the OPENCODE_CONFIG_CONTENT env var (full block, and permission-only block) made the
        # same free model return provider.free-limit 429; the identical call without it returned OK, cost 0
        # (evidence/af1). In v2.2.5 OPENCODE_PERMISSION is NOT honored (a write succeeded), but an opencode.json in
        # OPENCODE_CONFIG_DIR is, so deny-all is written there. The model is pinned by --model and checked against the
        # exact free list. No credentials are copied: the user's own OpenCode identity is used in place.
        # v2.2.5 also returns the free-tier 429 when read tools or all tools are denied (evidence/af1), so the file denies
        # every mutating/outbound action and leaves read-only tools confined to the job folder (external_directory deny).
        (isolated / 'opencode.json').write_text(json.dumps({'$schema': 'https://opencode.ai/config.json', 'permission': {
            **OPENCODE_DENY_KEYS}}), encoding='utf-8')
        env = clean_environment()
        env.update({'OPENCODE_PERMISSION': json.dumps(permission), 'OPENCODE_DISABLE_AUTOUPDATE': 'true',
                    'OPENCODE_DISABLE_PROJECT_CONFIG': 'true', 'OPENCODE_DISABLE_LSP_DOWNLOAD': 'true',
                    'OPENCODE_DISABLE_DEFAULT_PLUGINS': 'true', 'OPENCODE_CONFIG_DIR': str(isolated)})
        args = ([str(self.opencode), 'run', '--standalone', '--format', 'json', '--model', model, '--title', title[:160]] if self.opencode_desktop else
                [str(self.opencode), 'run', '--pure', '--format', 'json', '--model', model, '--title', title[:160], '--dir', str(work)])
        if conversation:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', str(conversation)):
                raise ValueError('Invalid OpenCode worker session id')
            args += ['--session', conversation]
        return CommandSpec('opencode', args, env, work, model)

    def _stop_child(self, process) -> None:
        if process.poll() is not None:
            return
        if os.name == 'nt':
            self.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                     timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(process.pid, signal.SIGTERM)

    def build_readonly_codex(self, model, work):
        """Fresh no-tool observer, using the independently signed-in Codex CLI."""
        from operations import find_tool
        cli=find_tool('codex')
        if not cli:raise ValueError('Codex CLI is not installed on this PC')
        work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
        args=[cli,'exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
              '-c','model_provider="openai"','-c','features.memories=false','-c','features.chronicle=false',
              '-c','approval_policy="never"','--disable','shell_tool','--disable','unified_exec',
              '--disable','apps','--disable','browser_use','--disable','computer_use',
              '--json','--color','never','--cd',str(work),'--model',model,
              '--output-last-message',str(work/'response.json')]
        try:
            import tomllib
            config=tomllib.loads((self.home/'.codex/config.toml').read_text(encoding='utf-8'))
            for name in config.get('mcp_servers',{}):args+=['-c',f'mcp_servers.{name}.enabled=false']
        except (OSError,ValueError):pass
        args+=['-']
        return CommandSpec('codex',args,clean_environment(),work,model,True,'read-only; all tools disabled')

    def run_readonly_codex(self,spec,prompt,**kwargs):
        result=self.run_opencode(spec,prompt,_protocol='codex',**kwargs)
        path=spec.cwd/'response.json'
        if result['status']=='COMPLETED' and path.is_file():result['text']=path.read_text(encoding='utf-8')
        elif result['status']=='COMPLETED':result.update(status='FAILED',error='Codex returned no final observer response')
        return result

    def run_opencode(self, spec: CommandSpec, prompt: str, on_event: Callable[[dict], None] | None = None,
                     cancel_event: threading.Event | None = None, timeout: float = 3600,
                     *, _protocol: str = 'opencode', timeout_mode: str = 'wall') -> dict:
        if spec.provider != {'agy':'antigravity','opencode':'opencode','codex':'codex','claude':'claude'}.get(_protocol):
            raise ValueError('Command provider does not match the bounded process protocol')
        if timeout <= 0 or timeout > 7200:
            raise ValueError('Worker time limit must be between zero and 3600 seconds')
        if timeout_mode not in ('wall', 'activity') or (timeout_mode == 'activity' and _protocol not in ('claude', 'agy')):
            raise ValueError('Activity timeout is available only for the native Claude lane')
        emit = on_event or (lambda event: None)
        process = self.popen(spec.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', cwd=spec.cwd, env=spec.env, **process_options())
        messages: queue.Queue = queue.Queue()
        input_error: list[str] = []
        def writer():
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                input_error.append('Provider closed stdin before the prompt was delivered')
        def reader():
            try:
                for line in process.stdout:
                    messages.put(line)
            finally:
                messages.put(None)
        threading.Thread(target=writer, daemon=True).start()
        threading.Thread(target=reader, daemon=True).start()
        start = time.monotonic()
        last_activity = start
        state, session_id, error = 'COMPLETED', None, None
        actual_model=spec.model
        terminal_result = None
        text_parts, usages = [], []
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    state = 'CANCELLED'
                    self._stop_child(process)
                    break
                if time.monotonic() - (last_activity if timeout_mode == 'activity' else start) > timeout:
                    state, error = 'TIMED_OUT', ('Owned worker made no tool/text progress within its inactivity limit; reconcile saved work before continuation' if timeout_mode == 'activity' else 'Owned worker process exceeded its time limit; no automatic retry')
                    self._stop_child(process)
                    break
                try:
                    line = messages.get(timeout=.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                try:
                    raw = json.loads(line)
                except (ValueError, TypeError):
                    emit({'provider': spec.provider, 'kind': 'diagnostic', 'actual': True, 'text': _safe(line.rstrip())})
                    continue
                if not isinstance(raw, dict):
                    continue
                session_id = raw.get('sessionID') or raw.get('conversation_id') or raw.get('session_id') or session_id
                event = normalize_agy_event(raw) if _protocol == 'agy' else normalize_opencode_event(raw) if _protocol=='opencode' else {'provider':'codex','kind':'progress','actual':True,'phase':raw.get('type','event')}
                if _protocol == 'claude':
                    from claude_transport import event as claude_event
                    event=claude_event(raw)
                    if event and event.get('kind')=='quota':
                        from claude_usage import record
                        record(Path(__file__).resolve().parents[1],event)
                    if event and event.get('model'):actual_model=event['model']
                    if raw.get('type')=='result':terminal_result=raw
                if _protocol=='codex' and raw.get('type')=='turn.failed':state,error='FAILED',_safe(raw.get('error'))
                if _protocol=='codex' and raw.get('type')=='turn.completed':
                    usage=raw.get('usage') or {};usages.append({k:_number(v) for k,v in usage.items()})
                if _protocol == 'agy' and raw.get('event') == 'result':
                    terminal_result = raw.get('result') or {}
                    session_id = terminal_result.get('conversation_id') or session_id
                if event:
                    # Quota heartbeats, init and diagnostics do not prove useful work.
                    # Station workers retain their absolute cap; the persistent
                    # native director can keep making progress across that cap.
                    if event.get('kind') in ('tool', 'text'):
                        last_activity = time.monotonic()
                    emit(event)
                    if event['kind'] == 'text':
                        # Preserve the structured worker response separately from bounded UI previews.
                        text_parts.append(str(event.get('text','')) if _protocol=='claude' else str(raw.get('step_update', {}).get('text_delta', '')) if _protocol == 'agy' else str(raw.get('part', {}).get('text', '')))
                    elif event['kind'] == 'usage':
                        usages.append(event['usage'])
                        if _protocol == 'opencode' and (event['usage'].get('cost') or 0) > 0:
                            # Free-only guard: any reported cost rejects the result and stops the child.
                            state, error = 'FAILED', f"OpenCode reported cost {event['usage']['cost']}; free-only result rejected"
                            self._stop_child(process)
                            break
                    elif event['kind'] == 'error':
                        err_text = str(event.get('error', ''))
                        if len(text_parts) > 200 and any(s in err_text.lower() for s in ('stream idle timeout', 'context deadline exceeded', 'connection reset', 'closed connection')):
                            pass
                        else:
                            state, error = 'FAILED', err_text
            process.wait(timeout=10)
            if state == 'COMPLETED' and (process.returncode or input_error):
                if _protocol == 'agy' and len(text_parts) > 200:
                    pass
                else:
                    state, error = 'FAILED', input_error[0] if input_error else f'Client exited with code {process.returncode}'
            response_text = ''.join(text_parts)
            provider_text = response_text
            if _protocol == 'claude':
                if terminal_result is not None:
                    response_text=str(terminal_result.get('result') or response_text)
                    provider_text=response_text
                elif state=='COMPLETED':
                    state,error='UNKNOWN','Claude exited without a terminal result; no automatic retry.'
            if _protocol == 'agy' and terminal_result is not None:
                provider_state = terminal_result.get('status')
                if state == 'COMPLETED':
                    state = {'SUCCESS': 'COMPLETED', 'ERROR': 'FAILED', 'CANCELED': 'CANCELLED',
                             'INTERRUPTED': 'INTERRUPTED', 'INVALID': 'FAILED', 'WAITING': 'BLOCKED'}.get(provider_state, 'UNKNOWN')
                response_text = str(terminal_result.get('response', response_text))
                provider_text = response_text
                # Native agy may concatenate response/control text while returning a valid
                # schema result separately. Consumers must parse the schema payload, not that transcript.
                if terminal_result.get('structured_output') is not None:
                    response_text = json.dumps(terminal_result['structured_output'], ensure_ascii=False)
                error = terminal_result.get('error') or error
                usage = _agy_usage(terminal_result.get('usage'))
                usages = [usage] if usage is not None else []
            elif _protocol == 'agy' and state == 'COMPLETED':
                if len(response_text) > 200:
                    state = 'COMPLETED'
                    error = None
                else:
                    state, error = 'UNKNOWN', 'CLI exited without an official terminal result; no automatic retry'
            return {'status': state, 'session_id': session_id, 'model': actual_model, 'text': response_text,
                    'provider_text': provider_text,
                    'usage_events': usages, 'usage_known': any(any(v is not None for v in u.values()) for u in usages),
                    'quota': (dict(self._agy_quota) if self._agy_quota is not None else {'supported': True, 'remaining': None,
                               'source': 'agy --print /usage', 'reason': 'Not checked in this runtime'}) if _protocol == 'agy' else dict(QUOTA_UNKNOWN),
                    'error': error, 'process_stopped': process.poll() is not None,
                    'idle_inference': 'unknown' if _protocol == 'agy' and state == 'UNKNOWN' else False if process.poll() is not None else ('unknown' if _protocol == 'agy' and state in ('CANCELLED', 'TIMED_OUT', 'UNKNOWN') else False),
                    'structured_output': terminal_result.get('structured_output') if terminal_result else None,
                    'terminal_subtype': terminal_result.get('subtype') if _protocol == 'claude' and isinstance(terminal_result, dict) else None,
                    'capabilities': {'provider_tools': spec.tool_policy, 'native_AE': False,
                                     'raw_media_perception': False}}
        finally:
            if process.poll() is None:
                self._stop_child(process)
            for stream in [process.stdin, process.stdout]:
                if stream:
                    try: stream.close()
                    except (BrokenPipeError, OSError): pass

    def run_agy(self, spec: CommandSpec, prompt: str, on_event: Callable[[dict], None] | None = None,
                cancel_event: threading.Event | None = None, timeout: float = 3600) -> dict:
        if spec.provider != 'antigravity' or not spec.cancellable:
            raise ValueError('Expected an official agy bounded headless command, not an agentapi relay')
        message = json.dumps({'event': 'user', 'message': {'content': prompt}}, ensure_ascii=False)+'\n'
        return self.run_opencode(spec, message, on_event, cancel_event, timeout, _protocol='agy')

    def start_antigravity_host(self, *, cloud_code_endpoint: str | None = None,
                              startup_timeout: float = 35) -> dict:
        """Explicit hidden startup only. No dialogs, IDE launch, credential migration, or inference.

        Headless flags are supported by installed --help. A successful metadata
        probe confirms transport, NOT provider authentication/model entitlement.
        """
        if not self.antigravity.is_file():
            return {'available': False, 'error': 'Antigravity language-server binary is not installed'}
        if self._owned_host is not None and self._owned_host.poll() is None:
            return {'available': False, 'transport_ready': self._host_state == 'METADATA_READY',
                    'error': 'An app-owned host already exists; no duplicate launched'}
        cloud_code_endpoint = ANTIGRAVITY_CLOUD_ENDPOINT if cloud_code_endpoint is None else cloud_code_endpoint
        parsed = urlparse(cloud_code_endpoint)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            self._last_host_error = 'A verified HTTPS cloud_code_endpoint is required. No host launched.'
            return {'available': False, 'error': self._last_host_error}
        work = self.root / '.runtime/antigravity-headless'
        work.mkdir(parents=True, exist_ok=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        nonce = secrets.token_hex(32)
        args = [str(self.antigravity), '-headless=true', '-standalone=true', '-persistent_mode=true',
                '-exit_on_stdin_close=true', f'-https_server_port={port}', '-disable_telemetry=true',
                '-app_data_dir=antigravity', '-override_ide_name=antigravity', '-subclient_type=hub',
                '-override_user_agent_name=antigravity', '-use_ls_chrome_devtools_mcp=false',
                f'-api_server_url={ANTIGRAVITY_API_ENDPOINT}', f'-cloud_code_endpoint={cloud_code_endpoint}', f'-csrf_token={nonce}']
        self._host_log = (work / 'host.log').open('w', encoding='utf-8')
        self._owned_host = self.popen(args, stdin=subprocess.PIPE, stdout=self._host_log,
                                      stderr=subprocess.STDOUT, cwd=work, env=clean_environment(), **process_options())
        self._host_env = clean_environment()
        self._host_env.update({'ANTIGRAVITY_LS_ADDRESS': f'127.0.0.1:{port}', 'ANTIGRAVITY_CSRF_TOKEN': nonce})
        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            if self._owned_host.poll() is not None:
                self._host_state = 'FAILED'
                self._last_host_error = 'Headless host exited during startup; provider access not verified'
                self.stop_owned_host()
                return {'available': False, 'error': self._last_host_error}
            log_text = (work / 'host.log').read_text(encoding='utf-8', errors='replace')
            if 'accounts.google.com/o/oauth2/auth' in log_text or 'accounts.google.com/o/oauth2/v2/auth' in log_text:
                self._last_host_error = 'Separate headless OAuth authorization is required. Desktop sign-in was not reused; no browser or dialog was opened.'
                self.stop_owned_host()
                self._host_state = 'AUTH_REQUIRED'
                return {'available': False, 'transport_state': 'AUTH_REQUIRED', 'authentication_verified': False,
                        'error': self._last_host_error}
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.15):
                    if 'initialized server successfully' not in log_text:
                        time.sleep(.1)
                        continue
                    self._host_state = 'LISTENING_UNVERIFIED'
                    self._last_host_error = 'Native host is listening; metadata/authentication has not been verified'
                    return {'available': False, 'transport_listening': True, 'authentication_verified': False,
                            'error': self._last_host_error}
            except OSError:
                time.sleep(.1)
        self._last_host_error = 'Headless startup timed out; owned host stopped, no automatic retry'
        self.stop_owned_host()
        return {'available': False, 'error': self._last_host_error}

    def antigravity_metadata(self, conversation_id: str, project_id: str, timeout: float = 15) -> dict:
        if not self._host_env or not self._owned_host or self._owned_host.poll() is not None:
            return {'transport_ready': False, 'error': 'No app-owned headless host'}
        if not re.fullmatch(r'[0-9a-fA-F-]{36}', conversation_id) or not re.fullmatch(r'[0-9a-fA-F-]{36}', project_id):
            raise ValueError('Expected conversation/project UUIDs')
        env = {**self._host_env, 'ANTIGRAVITY_PROJECT_ID': project_id}
        try:
            result = self.run([str(self.antigravity), 'agentapi', 'get-conversation-metadata', conversation_id],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                              timeout=timeout, **process_options())
            body = json.loads(result.stdout)
            ready = result.returncode == 0 and isinstance(body.get('response', {}).get('conversationMetadata'), dict)
            self._host_state = 'METADATA_READY' if ready else 'METADATA_FAILED'
            self._headless_verified = ready
            if ready:self._last_host_error = 'Headless metadata verified; model entitlement and quota are verified only by an explicit task.'
            return {'transport_ready': ready, 'authentication_verified': False,
                    'conversation_id': conversation_id, 'error': None if ready else 'Metadata probe failed',
                    'quota': dict(QUOTA_UNKNOWN)}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'transport_ready': False, 'authentication_verified': False, 'error': 'Metadata probe failed or timed out'}

    def antigravity_relay(self, conversation_id: str, prompt_file: str | Path, title: str,
                          *, route: str | None = None, existing_host: bool = False,
                          project_id: str | None = None) -> CommandSpec:
        """Build relay only; an existing IDE host is optional and never launched here.

        The caller must explicitly choose existing_host. Without a verified
        standalone host the default refuses rather than secretly requiring UI.
        """
        prompt = Path(prompt_file).resolve()
        if not prompt.is_file():
            raise ValueError('Prompt file is missing')
        if route is not None and route not in ANTIGRAVITY_ROUTES:
            raise ValueError('Only documented route aliases flash_lite, flash, pro are accepted; exact model identity is unknown')
        if not existing_host:
            if not (self._headless_verified and self._host_env and self._owned_host and self._owned_host.poll() is None):
                raise ValueError('Authenticated Antigravity headless dispatch is not verified; no UI fallback or host auto-launch')
            if not project_id or not re.fullmatch(r'[0-9a-fA-F-]{36}', project_id):
                raise ValueError('An explicit Antigravity project UUID is required')
            content = prompt.read_text(encoding='utf-8')
            if len(content) > 16000:
                raise ValueError('Relay prompt exceeds safe Windows argv size; use a short task entrypoint instruction')
            env = {**self._host_env, 'ANTIGRAVITY_PROJECT_ID': project_id}
            if conversation_id:
                if not re.fullmatch(r'[0-9a-fA-F-]{36}', conversation_id):raise ValueError('Expected conversation UUID')
                if route is not None:raise ValueError('send-message cannot change an existing conversation model')
                args = [str(self.antigravity), 'agentapi', 'send-message', '--title='+title[:160], conversation_id, content]
            else:
                args = [str(self.antigravity), 'agentapi', 'new-conversation', '--model='+(route or 'flash'), '--title='+title[:160], content]
            return CommandSpec('antigravity', args, env, prompt.parent, None, False)
        if not self.helper.is_file():
            raise ValueError('The verified local Antigravity relay helper is missing')
        args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.helper),
                '-Action', 'send' if conversation_id else 'new', '-PromptFile', str(prompt), '-Title', title[:160]]
        if conversation_id:
            if not re.fullmatch(r'[0-9a-fA-F-]{36}', conversation_id):
                raise ValueError('Expected conversation UUID')
            args += ['-ConversationId', conversation_id]
            if route is not None:
                raise ValueError('send-message cannot change an existing conversation model')
        else:
            args += ['-Model', route or 'flash']
        return CommandSpec('antigravity', args, clean_environment(), prompt.parent, None, False)

    def run_antigravity_relay(self, spec: CommandSpec, timeout: float = 25) -> dict:
        """Explicit dispatch only. Acceptance never becomes a fabricated completion."""
        if spec.provider != 'antigravity' or spec.cancellable:
            raise ValueError('Expected a detached Antigravity relay command')
        try:
            result = self.run(spec.argv, cwd=spec.cwd, env=spec.env, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=timeout, **process_options())
            try:body = json.loads(result.stdout)
            except ValueError:body = {}
            accepted = result.returncode == 0 and isinstance(body.get('response'), dict) and bool(body['response']) and not body.get('error')
            return {'status': 'SUBMITTED' if accepted else 'UNKNOWN', 'accepted': bool(accepted),
                    'response': _safe(body) if accepted else None,
                    'error': None if accepted else _safe(result.stderr or result.stdout or 'Relay did not confirm acceptance'),
                    'remote_state': 'unknown', 'worker_stop_confirmed': False, 'usage': None,
                    'quota': dict(QUOTA_UNKNOWN), 'idle_inference': 'unknown', 'automatic_retry': False}
        except (OSError, subprocess.TimeoutExpired):
            return {'status': 'UNKNOWN', 'accepted': False, 'remote_state': 'unknown',
                    'error': 'Relay failed or timed out; delivery is unknown. Inspect the task before any explicit retry.',
                    'worker_stop_confirmed': False, 'usage': None, 'quota': dict(QUOTA_UNKNOWN),
                    'idle_inference': 'unknown', 'automatic_retry': False}

    def stop_owned_host(self) -> dict:
        """Only the child this instance created is affected; no desktop process lookup/kill."""
        process = self._owned_host
        if process is not None and process.poll() is None:
            try:
                if process.stdin: process.stdin.close()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self._stop_child(process)
        if self._host_log:
            self._host_log.close()
        self._owned_host, self._host_env, self._host_log = None, None, None
        self._host_state, self._headless_verified = 'STOPPED', False
        return {'stopped_owned_host': True, 'remote_agent_cancelled': False}


def watch_external_result(task_folder: str | Path, validator: Callable[[Path], dict],
                          *, timeout: float = 3600, cancel_event: threading.Event | None = None,
                          poll_seconds: float = .5) -> dict:
    """Observe local result files only. Timeout/cancel cannot stop a detached agent."""
    folder = Path(task_folder).resolve()
    deadline = time.monotonic() + timeout
    while True:
        if (folder / 'RESULT.json').is_file():
            try:
                checked = validator(folder)
            except (OSError, ValueError, TypeError) as error:
                return {'status': 'INVALID_OUTPUT', 'error': str(error), 'idle_inference': 'unknown'}
            state = checked.get('status')
            if state in ('REVIEW_REQUIRED', 'APPROVED', 'CHANGES_REQUESTED', 'BLOCKED', 'FAILED', 'INVALID_OUTPUT'):
                return {'status': state, 'validated_result': checked, 'idle_inference': 'unknown',
                        'worker_stop_confirmed': False, 'source': 'validated_task_result'}
        if cancel_event is not None and cancel_event.is_set():
            return {'status': 'UNKNOWN', 'reason': 'Local observation cancelled; remote cancellation unsupported',
                    'idle_inference': 'unknown', 'worker_stop_confirmed': False}
        if time.monotonic() >= deadline:
            return {'status': 'UNKNOWN', 'reason': 'No validated terminal result before deadline; no automatic resend',
                    'idle_inference': 'unknown', 'worker_stop_confirmed': False}
        time.sleep(max(.01, min(poll_seconds, max(0, deadline - time.monotonic()))))
