"""Subscription-only bounded text workers. Construction never invokes a CLI."""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import threading
import time

from .lifetime import ChildLifetime
from .failures import classify_failure

CLAUDE_MODELS = {'opus', 'sonnet', 'haiku', 'claude-fable-5-2'}
CODEX_MODELS = {'gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-sol', 'gpt-6-luna'}
FREE_ID = re.compile(r'opencode/[a-z0-9][a-z0-9_.-]*-free')
DENY = {k: 'deny' for k in ('*','read','glob','grep','list','edit','write','patch','shell','bash','webfetch','websearch','subagent','task','browser','external_directory')}


def environment():
    env = dict(os.environ)
    for key in list(env):
        if any(s in key.upper() for s in ('API_KEY','ACCESS_TOKEN','CLIENT_SECRET','AUTHORIZATION','PASSWORD','CSRF_TOKEN')) or key.startswith(('ANTHROPIC_','CLAUDE_CODE_USE_','AWS_','AZURE_')):
            env.pop(key, None)
    for key in ('OPENAI_BASE_URL','GOOGLE_APPLICATION_CREDENTIALS','GOOGLE_GENAI_USE_VERTEXAI','OPENCODE_CONFIG_CONTENT'):
        env.pop(key, None)
    return env


def process_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}


def executable(route):
    if route == 'gemini':
        from .gemini import executable as gemini_executable
        return gemini_executable()[0]
    found = shutil.which(route)
    if found:
        return found
    home = Path.home()
    if route == 'claude':
        path = home / '.local/bin/claude.exe'
        if path.is_file(): return str(path)
        candidates=[]
        for base in (home/'AppData/Roaming/Claude',home/'AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc',home/'AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude'):
            candidates.extend(base.glob('claude-code/*/*/claude.exe'))
        if candidates:return str(max(candidates,key=lambda p:p.stat().st_mtime))
    if route == 'codex':
        candidates=list((home/'AppData/Local/OpenAI/Codex/bin').glob('*/codex.exe'))
        if candidates:return str(max(candidates,key=lambda p:p.stat().st_mtime))
    if route == 'opencode':
        found = sorted((home/'AppData/Roaming/ai.opencode.desktop/cli').glob('*/opencode-cli.exe'), key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in re.split(r'[.\-]',p.parent.name)))
        if found: return str(found[-1])
    raise ValueError(route + ' CLI is not installed')


def validate(route, model, effort):
    if route == 'gemini':
        from .gemini import validate as gemini_validate
        return gemini_validate(model, effort)
    if model in ('opus', 'gpt-6.1-sol', 'gpt-6-sol') and effort != 'medium':
        raise ValueError('Opus and Sol require medium effort in Neural.')
    if route == 'claude':
        if model not in CLAUDE_MODELS or effort not in ('low','medium'):
            raise ValueError('Claude requires an approved exact model and low/medium effort')
    elif route == 'codex':
        if model not in CODEX_MODELS or effort not in ('low','medium','high'):
            raise ValueError('Codex requires an exact Terra/Sol model and supported effort')
    elif route == 'opencode':
        if not FREE_ID.fullmatch(model) or effort not in (None,'','default'):
            raise ValueError('OpenCode requires an exact free model; reasoning effort is unsupported')
    else:
        raise ValueError('Unsupported bounded provider route')


class Transport:
    def __init__(self, timeout=600, popen=subprocess.Popen, lifetime_factory=ChildLifetime):
        self.timeout, self.popen, self.lifetime_factory = timeout, popen, lifetime_factory

    def _run(self, args, work, env, prompt, cancel, raw_path, timeout=None):
        """The lifetime guard owns metadata probes and inference children alike."""
        child = None
        attached=False
        lifetime = self.lifetime_factory()
        lines = queue.Queue()
        try:
            if cancel.is_set(): return 'CANCELLED', [], None
            child = self.popen(args, cwd=work, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **process_options())
            lifetime.attach(child)
            attached=True
            def reader():
                try:
                    for line in child.stdout: lines.put(line)
                finally: lines.put(None)
            def writer():
                try:
                    child.stdin.write(prompt)
                    child.stdin.close()
                except (OSError, BrokenPipeError): pass
            threading.Thread(target=reader,daemon=True).start()
            threading.Thread(target=writer,daemon=True).start()
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
            output = []
            with Path(raw_path).open('a',encoding='utf-8') as evidence:
                evidence.write(json.dumps({'transport_command':args,'at':time.time()})+'\n'); evidence.flush()
                while True:
                    if cancel.is_set(): return 'CANCELLED',output,None
                    if time.monotonic() > deadline: return 'UNKNOWN',output,'Child deadline exceeded; reconcile session before continuation'
                    try: line = lines.get(timeout=.1)
                    except queue.Empty: continue
                    if line is None: break
                    evidence.write(line); evidence.flush()
                    output.append(line)
                code = child.wait(timeout=5)
                evidence.write(json.dumps({'transport_exit_code':code})+'\n')
            return ('COMPLETED' if code == 0 else 'FAILED'), output, None if code == 0 else 'CLI exited with code '+str(code)
        finally:
            if child is not None and child.poll() is None:
                if os.name == 'nt':
                    if attached:lifetime.close()  # kill-on-close includes descendants
                    else:
                        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    os.killpg(child.pid,signal.SIGTERM)
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill();child.wait(timeout=5)
            lifetime.close()
            if child is not None:
                for stream in (child.stdin,child.stdout):
                    if stream:
                        try: stream.close()
                        except OSError: pass

    def run(self, row, packet, folder, session, cancel):
        route,model,effort = row['route'],row['model'],row['effort']
        validate(route,model,effort)
        cli = executable(route)
        env = environment()
        folder = Path(folder)
        raw = folder/'raw.log'
        # Every real invocation verifies existing auth/catalog; never signs in or changes billing.
        if route == 'claude':
            state,lines,error=self._run([cli,'auth','status'],folder,env,'',cancel,raw,timeout=15)
            try: auth=json.loads(''.join(lines))
            except ValueError: auth={}
            if state!='COMPLETED' or not(auth.get('loggedIn') is True and auth.get('authMethod')=='claude.ai' and auth.get('apiProvider')=='firstParty'):
                return {'status':state if state in ('CANCELLED','UNKNOWN') else 'FAILED','error':error or 'Claude first-party subscription sign-in is required','execution_started':False}
            env.update(CLAUDE_CODE_EFFORT_LEVEL=effort,CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION='false')
            args=[cli,'-p','--output-format','stream-json','--verbose','--model',model,'--effort',effort,'--max-turns','1','--tools','','--disable-slash-commands','--setting-sources','','--settings',json.dumps({'disableAllHooks':True,'autoMemoryEnabled':False,'effortLevel':effort}),'--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--system-prompt','You are a bounded Neural station specialist. Follow the supplied immutable task and result contract. You have no tools. Use supplied text only. Never claim unperformed perception, access, native work or approval. Return one result and stop.']
            if session: args+=['--resume',session]
        elif route == 'codex':
            state,lines,error=self._run([cli,'login','status'],folder,env,'',cancel,raw,timeout=15)
            if state!='COMPLETED' or 'chatgpt' not in ''.join(lines).lower():
                return {'status':state if state in ('CANCELLED','UNKNOWN') else 'FAILED','error':error or 'Codex ChatGPT subscription sign-in is required','execution_started':False}
            args=[cli,'exec','--skip-git-repo-check','--sandbox','read-only','-c','model_provider="openai"','-c','features.memories=false','-c','features.chronicle=false','-c','approval_policy="never"','-c','web_search="disabled"','-c','model_reasoning_effort='+json.dumps(effort),'--disable','shell_tool','--disable','unified_exec','--disable','apps','--disable','browser_use','--disable','computer_use','--json','--color','never','--cd',str(folder),'--model',model,'--output-last-message',str(folder/'final.txt')]
            config=Path.home()/'.codex/config.toml'
            if config.is_file():
                import tomllib
                for name in tomllib.loads(config.read_text(encoding='utf-8')).get('mcp_servers',{}):
                    if not re.fullmatch(r'[A-Za-z0-9_-]+',name): raise ValueError('Unsafe configured MCP name')
                    args+=['-c',f'mcp_servers.{name}.enabled=false']
            if session: args+=['resume',session]
            args+=['-']
        else:
            desktop=Path(cli).name=='opencode-cli.exe'
            discovery=[cli,'models','--standalone'] if desktop else [cli,'models','opencode','--pure']
            state,lines,error=self._run(discovery,folder,env,'',cancel,raw,timeout=15)
            if state!='COMPLETED' or model not in {s.strip() for s in lines}:
                return {'status':state if state in ('CANCELLED','UNKNOWN') else 'FAILED','error':error or 'Free OpenCode model is absent from the installed CLI catalog','execution_started':False}
            config=folder/'opencode-config';config.mkdir(exist_ok=True)
            (config/'opencode.json').write_text(json.dumps({'permission':DENY}),encoding='utf-8')
            # CLI 2.2.7 ignores OPENCODE_CONFIG_DIR and reads opencode.json from the working directory; keep the deny-all there too.
            (folder/'opencode.json').write_text(json.dumps({'permission':DENY}),encoding='utf-8')
            env.update(OPENCODE_CONFIG_DIR=str(config),OPENCODE_DISABLE_AUTOUPDATE='true',OPENCODE_DISABLE_PROJECT_CONFIG='true',OPENCODE_DISABLE_LSP_DOWNLOAD='true',OPENCODE_DISABLE_DEFAULT_PLUGINS='true')
            args=[cli,'run','--standalone' if desktop else '--pure','--format','json','--model',model,'--title','Neural2 bounded text station']
            if not desktop: args+=['--dir',str(folder)]
            if session: args+=['--session',session]
        prompt='You are a bounded text specialist. Use only supplied text evidence. Never claim playback, listening, raw-media perception, AE execution or artistic approval. No tools, subagents, credentials, billing or provider changes. Return the requested result once.\n'+json.dumps(packet,ensure_ascii=False)
        state,lines,error=self._run(args,folder,env,prompt,cancel,raw)
        result={'status':state,'error':error,'session_id':session,'text':'','usage':[],'execution_started':True,'requested_model':model,'cli_path':cli,'tool_policy':'supplied text only; all tools denied'}
        terminal=False
        provider_events=[]
        uncertain_execution=state in ('UNKNOWN','CANCELLED')
        for line in lines:
            try: event=json.loads(line)
            except ValueError: continue
            if not isinstance(event,dict): continue
            provider_events.append(event)
            if event.get('type') in ('tool_use','tool') or (isinstance(event.get('part'),dict) and event['part'].get('type')=='tool'):
                result.update(status='FAILED',error='Provider attempted tools in a supplied-text-only assignment')
            if route=='claude' and model=='claude-fable-5-2' and event.get('type')=='system' and event.get('subtype')=='init' and event.get('model')!=model:
                result.update(status='UNKNOWN',error='Exact Fable model was not confirmed by provider initialization')
            sid=event.get('session_id') or event.get('sessionID') or event.get('thread_id')
            if sid:
                if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',sid):
                    result.update(status='UNKNOWN',error='Provider returned an invalid durable session identifier')
                elif result['session_id'] and sid!=result['session_id']:
                    result.update(status='UNKNOWN',error='Provider session changed unexpectedly; no automatic reset')
                    result['unexpected_session_id']=sid
                else:result['session_id']=sid
            if route=='claude' and event.get('type')=='result':
                terminal=True
                result['text']=event.get('result') or ''
                result['usage'].append(event.get('usage') or {})
                if event.get('is_error') or event.get('subtype')!='success':result.update(status='FAILED',error=str(event.get('errors') or event.get('result') or event.get('subtype')))
            elif route=='codex':
                if event.get('type')=='turn.completed':terminal=True;result['usage'].append(event.get('usage') or {})
                if event.get('type')=='turn.failed':result.update(status='FAILED',error=str(event.get('error')))
            elif route=='opencode':
                part=event.get('part') or {}
                if event.get('type')=='text':result['text']+=str(part.get('text',''))
                if event.get('type')=='step_finish':
                    terminal=True;result['usage'].append(part.get('tokens') or {})
                    if (part.get('cost') or 0)>0:result.update(status='FAILED',error='Reported OpenCode cost exceeds free-only policy')
                if event.get('type')=='error':
                    provider_error=event.get('error')
                    result.update(status='FAILED',error=str(provider_error))
                    if isinstance(provider_error,dict) and provider_error.get('type')=='provider.free-limit':
                        result['availability_scope']='exact model through isolated deny-all CLI route; desktop and other models are not determined'
                        result['provider_error']=provider_error
                        result['error']='OpenCode rejected this exact isolated tool-less model route (HTTP 429). This does not establish desktop or global free-model unavailability. Provider report: '+str(provider_error)
            if result['status'] in ('UNKNOWN','CANCELLED'):uncertain_execution=True
        if route=='codex' and (folder/'final.txt').is_file():result['text']=(folder/'final.txt').read_text(encoding='utf-8')
        if result['status']=='FAILED' and not result['session_id'] and re.search(r'(unexpected argument|unknown (?:option|argument)|unrecognized (?:option|argument)|invalid option)', ''.join(lines),re.IGNORECASE):
            result['execution_started']=False
        if result['status']=='COMPLETED' and (not terminal or not result['text'] or not result['session_id']):result.update(status='UNKNOWN',error='Missing terminal result, response, or durable session; reconcile before continuation')
        if uncertain_execution:
            result['status']='CANCELLED' if state=='CANCELLED' else 'UNKNOWN'
        result.update(classify_failure(route,model,provider_events,result['status']))
        return result
