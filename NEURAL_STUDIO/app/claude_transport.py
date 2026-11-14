"""Official Claude Code subscription transport. No Desktop cookies or private chat APIs.

Stations receive supplied evidence only. This adapter grants no tools or native editor
ownership; the existing director/TonyFX lane remains separate.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
from provider_runtime import CommandSpec, clean_environment, process_options, _safe

MODELS = {'opus', 'sonnet', 'haiku'}
# A long production turn (analysis, scripts, builds) needs hundreds of tool steps; the 30-minute
# process timeout and human Stop remain the real bounds. Hitting it only pauses the session.
DIRECTOR_MAX_TURNS = 400
DIRECTOR_TOOLS = 'Read,Write,Edit,Glob,Grep,Bash,PowerShell,WebFetch,WebSearch'
# B1 (7 Nov 2026) oversight mode: the director reads, plans and assigns; it never applies work. Its only mutating
# channel is the narrow wrapper (reads the token itself). No Write/Edit/PowerShell/WebFetch/WebSearch/general shell.
OVERSIGHT_TOOLS = 'Read,Glob,Grep,Bash'
OVERSIGHT_ALLOWED = ['Read', 'Glob', 'Grep']  # H3: no Bash allow rule; oversight_bash_guard.py's explicit allow is the only way Bash runs
HOOK_TIMEOUT = 30
OVERSIGHT_MAX_TURNS = 60
OVERSIGHT_SYSTEM = ("You are the oversight DIRECTOR in Neural. You plan, assign exact bounded tasks, review evidence and accept or reject. "
    "You never apply work yourself: you have no Write, Edit, PowerShell, web or general shell tools. Read, Glob and Grep inspect files. "
    "Your only action channel is `python tools/neural_cli.py` (status, assign, dispatch, watch, accept, reject); it holds the token, you never see it. "
    "Register a watch after every dispatch and END your turn; a real completion or failure event wakes you. Never poll, never replay an UNKNOWN or pending native command, "
    "never edit app code, change billing or providers, or start a second editor. Only one TonyFX native writer exists and it is an executor, not you. "
    "Keep replies compact. Preserve unrelated work and the current human pause; old handoffs are not new tasks.")


def find_claude(home=None):
    found = shutil.which('claude')
    if found:
        return Path(found)
    home = Path(home) if home else Path.home()
    candidates = [home/'.local/bin/claude.exe']
    for base in (home/'AppData/Roaming/Claude',
                 home/'AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc',
                 home/'AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude'):
        candidates.extend(base.glob('claude-code/*/*/claude.exe'))
    candidates = [p for p in candidates if p.is_file()]
    return max(candidates, key=lambda p:p.stat().st_mtime) if candidates else None


def environment():
    env = clean_environment()
    for key in list(env):
        if key.startswith(('ANTHROPIC_', 'CLAUDE_CODE_USE_', 'AWS_', 'AZURE_')):
            env.pop(key, None)
    env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] = '1'
    # Tony's explicit native-Claude policy; scoped to the child, never a global env edit.
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'medium'
    # Scoped to Neural's child process. Earlier native compaction preserves the
    # saved conversation; it does not reset sessions or lower reasoning effort.
    env['CLAUDE_CODE_AUTO_COMPACT_WINDOW'] = '200000'
    env['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'] = '80'
    env['CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION'] = 'false'
    env['CLAUDE_CODE_GOAL_CHECKIN_MINUTES'] = '0'
    return env


def connection(run=subprocess.run):
    cli = find_claude()
    row = {'installed':bool(cli), 'authenticated':False, 'available':False,
           'path':str(cli) if cli else None, 'models':sorted(MODELS),
           'quota':{'supported':False, 'remaining':None,
                    'reason':'Claude Code exposes call usage; remaining subscription allowance is not reported by this adapter.'},
           'setup':'Use Connect Claude → subscription sign-in, then recheck. Desktop chat sign-in is separate. No API keys or paid API fallback.'}
    if not cli:
        return {**row, 'auth':'Claude Code runtime not installed.'}
    try:
        result = run([str(cli), 'auth', 'status'], capture_output=True, text=True,
                     encoding='utf-8', errors='replace', timeout=12, env=environment(), **process_options())
        data = json.loads(result.stdout)
        ready = result.returncode == 0 and data.get('loggedIn') is True and data.get('authMethod') == 'claude.ai' and data.get('apiProvider') == 'firstParty'
        row.update(authenticated=ready, available=ready,
                   auth='Claude subscription signed in.' if ready else 'Claude Code subscription sign-in required; Desktop sign-in does not connect this runtime.')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        row['auth'] = 'Claude subscription status check failed; no inference was started.'
    return row


def build(model, work, *, resume=None, persistent=False):
    if model not in MODELS:
        raise ValueError('Choose Claude subscription alias opus, sonnet or haiku; no provider model fallback.')
    cli = find_claude()
    if not cli:
        raise ValueError('Claude Code runtime is not installed.')
    work = Path(work).resolve();work.mkdir(parents=True, exist_ok=True)
    args = [str(cli), '-p', '--output-format', 'stream-json', '--verbose',
            '--model', model, '--effort', 'medium', '--max-turns', '1', '--no-session-persistence',
            '--tools', '', '--disable-slash-commands', '--setting-sources', '',
            '--settings', json.dumps({'disableAllHooks':True, 'autoMemoryEnabled':False,
                                      'effortLevel':'medium', 'outputStyle':'Concise'}),
            '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--system-prompt', 'You are a bounded Neural station specialist. Follow the supplied task and response contract. You have no tools. Never claim unperformed perception or native work.']
    if persistent:
        args.remove('--no-session-persistence')
        if resume:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', str(resume)):
                raise ValueError('Invalid Claude worker session id')
            args += ['--resume', resume]
    elif resume:
        raise ValueError('Resume requires a persistent worker session')
    return CommandSpec('claude', args, environment(), work, model, True, 'all tools, hooks, MCP and inherited project settings disabled')


def project_read_dirs(root, project_id=None):
    """BF9: per-project read roots (project folder + parents of its asset files), resolved from PROJECT.json; no scan of other projects."""
    root = Path(root)
    if not project_id:
        try:
            project_id = (json.loads((root/'data/production/CURRENT.json').read_text(encoding='utf-8')) or {}).get('project_id')
        except (OSError, ValueError):
            project_id = None
    if not isinstance(project_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', project_id):
        return []
    folder = root/'data/projects'/project_id
    dirs = [folder] if folder.is_dir() else []
    try:
        project = json.loads((folder/'PROJECT.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return dirs
    for asset in project.get('assets', []) if isinstance(project, dict) else []:
        parent = Path(str(asset.get('path', ''))).parent if isinstance(asset, dict) else None
        if parent and parent.is_absolute() and parent.is_dir() and parent not in dirs:
            dirs.append(parent)
    return dirs


def build_director(model, work, resume=None, extra_dirs=(), oversight=False, project_dirs=()):
    """Separate human-authorized director lane; never enabled for ordinary station jobs.

    Like the Codex director thread, the Claude director keeps one continuing session:
    pass the previous session id as `resume`. Claude Code compacts long sessions itself.
    `extra_dirs` grants file tools access outside the project (the TonyFX bridge folder)."""
    spec=build(model,work)
    args=spec.argv
    approved_hook = Path.home()/'.local/bin/rtk/rtk_auto_hook.py'
    if approved_hook.is_file():
        import sys
        settings_index = args.index('--settings')+1
        settings = json.loads(args[settings_index])
        settings.update(disableAllHooks=False, hooks={'PreToolUse':[{
            'matcher':'Bash' if oversight else 'Bash|PowerShell', 'hooks':[{'type':'command',
            'command':sys.executable.replace('\\','/')+' '+approved_hook.as_posix()+' --agent claude', 'timeout':HOOK_TIMEOUT}]}]})
        args[settings_index] = json.dumps(settings)
    if oversight:
        # BF8: --allowedTools alone let `whoami` and `neural_cli ... ; whoami` run in a live probe; this extra deny-only hook closes it.
        import sys
        guard = Path(__file__).resolve().parents[1]/'tools'/'oversight_bash_guard.py'
        settings_index = args.index('--settings')+1
        settings = json.loads(args[settings_index])
        hooks = settings.setdefault('hooks', {}).setdefault('PreToolUse', [])
        hooks.append({'matcher':'Bash', 'hooks':[{'type':'command', 'command':'"'+sys.executable.replace('\\','/')+'" "'+guard.as_posix()+'"', 'timeout':HOOK_TIMEOUT}]})
        settings['disableAllHooks'] = False
        args[settings_index] = json.dumps(settings)
    args.remove('--no-session-persistence')
    args[args.index('--max-turns')+1]=str(OVERSIGHT_MAX_TURNS if oversight else DIRECTOR_MAX_TURNS)
    args[args.index('--tools')+1]=OVERSIGHT_TOOLS if oversight else DIRECTOR_TOOLS
    args[args.index('--system-prompt')+1]='You are the authorized director in Neural. Tony owns this local Neural app, its workflow files and supplied projects. His assignment authorizes routine inspection, reading, writing, debugging and general-assistant help (engineering, research, scripting, file/shell/web tasks) as well as video production using the installed tools; inspecting his own app files is permitted when requested. Preserve unrelated work and the current human pause; never treat old handoffs as a new task. Read shared/AE2024_MIGRATION_20261022.md when present before AE work, and inspect the actual host/project. Use one serialized TonyFX editor, never replay unknown execution. Keep state and register event watches before ending a waiting turn. Ask only for a real missing input, unsupported capability or action outside the authorized scope. Never expose credentials, bypass provider safeguards, or change provider/billing configuration.'
    if oversight:
        # Default permission mode: anything outside --allowedTools is denied in headless -p mode (no acceptEdits).
        args[args.index('--system-prompt')+1]=OVERSIGHT_SYSTEM
        args += ['--permission-mode','dontAsk','--allowedTools',*OVERSIGHT_ALLOWED,'--disallowedTools','Write','Edit','NotebookEdit','PowerShell']
    else:
        args += ['--permission-mode','acceptEdits','--allowedTools',DIRECTOR_TOOLS]
    policy=Path(work).resolve()/'shared'/'USAGE_EFFICIENT_WORKFLOW_20261102.md'
    if policy.is_file() and not oversight:  # oversight: shared/CURRENT_WORKFLOW_20261107.md replaces the re-sent note
        note=policy.read_text(encoding='utf-8').strip()
        if len(note)>8000:
            raise ValueError('Usage workflow policy exceeds its bounded director context')
        if note:args += ['--append-system-prompt',note]
    if resume:
        if not isinstance(resume,str) or not re.fullmatch(r'[A-Za-z0-9-]{8,80}',resume):
            raise ValueError('Invalid Claude director session id.')
        args += ['--resume',resume]
    for folder in [*extra_dirs, *project_dirs]:
        folder=Path(folder)
        if folder.is_dir() and str(folder.resolve()) not in args:args += ['--add-dir',str(folder.resolve())]
    env=dict(spec.env)
    if not oversight:env.update(CLAUDE_CODE_USE_POWERSHELL_TOOL='1',CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY='1')
    return CommandSpec('claude',args,env,spec.cwd,model,True,'oversight director: Read/Glob/Grep + neural_cli wrapper only' if oversight else 'human-authorized director tools; approved selective RTK hook only; no MCP, subagents or inherited settings')


EXECUTOR_MODELS = {'opus', 'sonnet', 'haiku'}  # Tony 2026-11-08: Lumen editor on Opus
EXECUTOR_MAX_TURNS = 120
APP_ROOT = Path(__file__).resolve().parents[1]
# BF3: paths an executor must never write. Relative to the app root, plus the TonyFX bridge folder.
EXECUTOR_DENY_DIRS = ('app', 'desktop', 'web', 'tests', 'tools', 'shared', 'knowledge', 'data/command')
EXECUTOR_SYSTEM = ("You are a bounded Neural EXECUTOR for one owned trial/task. You apply the assigned work with Read/Write/Edit/Glob/Grep and an allowlisted Bash inside the project work folder only. "
    "You are never the director. Use only the single serialized native TonyFX editor lease you were given, and only through the guarded tools/local_ops.py path; never replay an UNKNOWN or pending native command, never start a second editor, "
    "change providers or billing, or reveal credentials. Bash: one plain command, no $, backticks, pipes or chaining, and double-quote any path containing spaces; media rendering only through local_ops operations. Report exact results and IDs; keep replies compact except code, commands, guards and evidence.")


def _slash(path):
    return str(path).replace('\\', '/')


def _claude_abs(path):
    """Claude Code absolute-path rule syntax on Windows: //c/Users/... (documented form; NOT verified live here)."""
    p = _slash(Path(path).resolve())
    if len(p) > 2 and p[1] == ':':
        p = '/' + p[0].lower() + p[2:]
    return '/' + p


def executor_bash_allow(app_root=None, python=None, which=shutil.which):
    """BF3: Bash allowlist by absolute path. Only these prefixes can run; everything else is denied in headless mode."""
    app_root = Path(app_root or APP_ROOT).resolve()
    import sys
    py = _slash(python or sys.executable)
    allowed = []
    # H3: kept for reference/tests only; build_executor no longer passes Bash allow rules (the guard hook is the sole allow).
    for script in ('tools/local_ops.py',):
        if (app_root/script).is_file():
            allowed.append('Bash(' + py + ' ' + _slash(app_root/script) + ':*)')
    found = which('ffprobe')
    if found:
        allowed.append('Bash(' + _slash(Path(found).resolve()) + ':*)')
    return allowed


def executor_deny(app_root=None, bridge=None, skill_dirs=()):
    """BF3: Edit/Write deny rules (deny wins over allow). Rule syntax is documented, not live-verified.

    skill_dirs: director-approved knowledge/skills/<name> promotion targets. Deny rules cannot carve exceptions, so the
    blanket knowledge/** rule is replaced by rules for every other knowledge child (and every other skill)."""
    app_root = Path(app_root or APP_ROOT).resolve()
    bridge = Path(bridge) if bridge else Path.home()/'Documents/ae-mcp-bridge'
    knowledge = app_root/'knowledge'
    keep = {Path(d).resolve() for d in skill_dirs if Path(d).resolve().parent == (knowledge/'skills').resolve()}
    targets = [app_root/d for d in EXECUTOR_DENY_DIRS if not (keep and d == 'knowledge')] + [bridge]
    rules = []
    if keep:
        for child in knowledge.iterdir():
            if child.name == 'skills':
                targets += [s for s in child.iterdir() if s.is_dir() and s.resolve() not in keep]
                rules += ['Edit(' + _claude_abs(child) + '/*)', 'Write(' + _claude_abs(child) + '/*)']
            elif child.is_dir():
                targets.append(child)
        rules += ['Edit(' + _claude_abs(knowledge) + '/*)', 'Write(' + _claude_abs(knowledge) + '/*)']
    for target in targets:
        pattern = _claude_abs(target) + '/**'
        rules += ['Edit(' + pattern + ')', 'Write(' + pattern + ')']
    return rules


def build_executor(model, work, resume=None, read_dirs=(), app_root=None, bridge=None, write_dirs=(), guard_path=None, extra_tools=()):
    """B2/BF3: tool-equipped Claude executor (Sonnet/Haiku) with its own persistent session.

    The work folder must be a project/trial folder, never the app root (or a parent of it). Bash is an allowlist of
    absolute-path prefixes (local_ops, ffprobe by grammar guard; raw ffmpeg and token_shell are excluded); Edit/Write are denied on app code, tests, shared
    rules, data/command and the bridge folder. Rules are passed on the argv; this adapter cannot prove the CLI enforces them
    without a live run, and acceptEdits may still auto-approve some filesystem shell commands inside the working folders.
    Native AE ownership is decided by LumenEditor (EDITOR_LOCK/owns_editor), never by this adapter."""
    if model not in EXECUTOR_MODELS:
        raise ValueError('Executor needs Claude alias opus, sonnet or haiku; no provider substitution.')
    app_root = Path(app_root or APP_ROOT).resolve()
    work_path = Path(work).resolve()
    if work_path == app_root or app_root.is_relative_to(work_path):
        raise ValueError('Executor work folder must be a project folder, never the Neural app root.')
    spec = build(model, work)
    args = spec.argv
    hook = Path.home()/'.local/bin/rtk/rtk_auto_hook.py'
    if hook.is_file():
        import sys
        i = args.index('--settings')+1
        settings = json.loads(args[i])
        settings.update(disableAllHooks=False, hooks={'PreToolUse':[{'matcher':'Bash', 'hooks':[{'type':'command',
            'command':sys.executable.replace('\\','/')+' '+hook.as_posix()+' --agent claude', 'timeout':HOOK_TIMEOUT}]}]})
        args[i] = json.dumps(settings)
    # E1: live probe showed --allowedTools let `whoami` run and refused the allowlisted tool; a guard hook now decides Bash and Write/Edit.
    import sys, base64
    # H2: raw ffmpeg and token_shell are not allowlisted; media rendering goes through local_ops ops. ffprobe has a fixed flag set.
    prefixes = [[_slash(sys.executable), _slash(app_root/s)] for s in ('tools/local_ops.py', *extra_tools) if (app_root/s).is_file()]
    prefixes += [[_slash(Path(f).resolve())] for f in (shutil.which('ffprobe'),) if f]
    cfg = base64.b64encode(json.dumps({'work': [_slash(work_path)] + [_slash(Path(d).resolve()) for d in write_dirs],
                                       'read': [_slash(Path(d).resolve()) for d in read_dirs if Path(d).is_dir()], 'bash': prefixes}).encode()).decode()
    i = args.index('--settings')+1
    settings = json.loads(args[i])
    guard_script = guard_path or (app_root/'tools/executor_guard.py')
    settings.setdefault('hooks', {}).setdefault('PreToolUse', []).append({'matcher':'Bash|Write|Edit|NotebookEdit', 'hooks':[{'type':'command',
        'command':'"'+sys.executable.replace('\\','/')+'" "'+Path(guard_script).as_posix()+'" '+cfg, 'timeout':HOOK_TIMEOUT}]})
    settings['disableAllHooks'] = False
    args[i] = json.dumps(settings)
    args.remove('--no-session-persistence')
    args[args.index('--max-turns')+1] = str(EXECUTOR_MAX_TURNS)
    args[args.index('--tools')+1] = 'Read,Write,Edit,Glob,Grep,Bash'
    args[args.index('--system-prompt')+1] = EXECUTOR_SYSTEM
    # H3: dontAsk denies anything not pre-approved; Bash has NO allow rule, so only the guard hook's explicit allow lets a command run.
    # Read/Glob/Grep stay allowed; Write/Edit are allowed by rule but the guard hook denies outside the work roots (and a broken hook cannot widen Bash).
    args += ['--permission-mode', 'dontAsk', '--allowedTools', 'Read', 'Glob', 'Grep', 'Write', 'Edit']
    args += ['--disallowedTools', *executor_deny(app_root, bridge, skill_dirs=write_dirs)]
    if resume:
        if not isinstance(resume, str) or not re.fullmatch(r'[A-Za-z0-9-]{8,80}', resume):
            raise ValueError('Invalid Claude executor session id.')
        args += ['--resume', resume]
    added = set()
    for folder in list(read_dirs) + list(write_dirs):
        folder = Path(folder)
        if folder.is_dir() and folder.resolve() not in added:
            added.add(folder.resolve())
            args += ['--add-dir', str(folder.resolve())]
    return CommandSpec('claude', args, dict(spec.env), spec.cwd, model, True, 'executor tools Read/Write/Edit/Glob/Grep + allowlisted Bash by grammar guard (local_ops, ffprobe; no raw ffmpeg, no token_shell); Edit/Write denied on app code, tests, shared, data/command and bridge; selective RTK hook; no MCP, web or PowerShell')

def event(raw):
    base = {'provider':'claude', 'actual':True, 'session_id':raw.get('session_id')}
    if raw.get('type') == 'rate_limit_event':
        from claude_usage import windows
        return {**base,'kind':'quota','quota_windows':windows(raw)}
    if raw.get('type') == 'system' and raw.get('subtype') == 'init':
        return {**base, 'kind':'progress', 'phase':'init', 'model':raw.get('model')}
    if raw.get('type') == 'assistant':
        blocks=raw.get('message',{}).get('content',[])
        tools=[{'name':b.get('name'),'id':b.get('id'),'input':_safe(b.get('input'))} for b in blocks if b.get('type')=='tool_use']
        if tools:return {**base,'kind':'tool','tools':tools}
        text = ''.join(str(b.get('text','')) for b in blocks if b.get('type') == 'text')
        return {**base, 'kind':'text', 'text':_safe(text)} if text else None
    if raw.get('type') == 'result':
        if raw.get('is_error') or raw.get('subtype') != 'success':
            return {**base, 'kind':'error', 'error':_safe(raw.get('errors') or raw.get('result') or raw.get('subtype')), 'subtype':raw.get('subtype')}
        return {**base, 'kind':'usage', 'usage':raw.get('usage') or {}, 'quota_remaining':None}
    return None
