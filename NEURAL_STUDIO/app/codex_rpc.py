"""Documented Codex app-server stdio transport; no inference on connect/read quotas."""
import json, os, queue, re, subprocess, threading, time
from pathlib import Path
from operations import find_tool, process_options, terminate


class CodexRPC:
    def __init__(self, root, on_event=None, on_request=None):
        self.root=Path(root);self.on_event=on_event or (lambda method,params:None)
        self.on_request=on_request or (lambda request:self.respond(request['id'],error={'code':-32601,'message':'Unsupported client request'}))
        self.lock=threading.RLock();self.start_lock=threading.RLock();self.write_lock=threading.Lock();self.pending={};self.counter=0;self.process=None;self.stderr=[];self.ready=False

    def start(self):
        with self.start_lock:
            try:self._start()
            except Exception:
                self.close();raise

    def _start(self):
        with self.lock:
            if self.ready and self.process and self.process.poll() is None:return
            executable=find_tool('codex')
            if not executable:raise ValueError('Codex runtime is not installed')
            args=[executable,'app-server','--listen','stdio://']
            from inference_usage import context_args
            args += context_args()
            # Disable configured third-party MCP servers for this app-owned runtime.
            try:
                import tomllib
                config=tomllib.loads((Path.home()/'.codex/config.toml').read_text(encoding='utf-8'))
                for name in config.get('mcp_servers',{}):
                    if not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise RuntimeError('A configured MCP name cannot be safely disabled by this runtime')
                    args+=['-c',f'mcp_servers.{name}.enabled=false']
            except (OSError,ValueError):pass
            args+=['-c','model_provider="openai"','-c','features.memories=false','-c','features.chronicle=false']
            env=os.environ.copy()
            for key in list(env):
                if any(part in key.upper() for part in ['API_KEY','ACCESS_TOKEN','CLIENT_SECRET']):env.pop(key,None)
            for key in ['OPENAI_BASE_URL','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_APPLICATION_CREDENTIALS']:env.pop(key,None)
            self.process=subprocess.Popen(args,cwd=self.root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',bufsize=1,**process_options())
            threading.Thread(target=self._read,daemon=True).start()
            threading.Thread(target=self._errors,daemon=True).start()
        self.call('initialize',{'clientInfo':{'name':'neural_posthouse','title':'Neural Posthouse','version':'0.7.0'},'capabilities':{'experimentalApi':True}},start=False)
        self.notify('initialized',{})
        account=self.call('account/read',{'refreshToken':False},start=False).get('account') or {}
        if account.get('type')!='chatgpt':
            self.close();raise ValueError('ChatGPT subscription sign-in is required. API-key billing is disabled.')
        self.ready=True

    def _send(self,message):
        with self.write_lock:
            if not self.process or self.process.poll() is not None:raise ValueError('Codex runtime is offline')
            self.process.stdin.write(json.dumps(message,ensure_ascii=False)+'\n');self.process.stdin.flush()

    def call(self,method,params=None,timeout=30,start=True):
        if start:self.start()
        with self.lock:
            self.counter+=1;request_id=self.counter;response=queue.Queue(maxsize=1);self.pending[request_id]=response
        try:
            self._send({'id':request_id,'method':method,'params':params or {}})
            try:message=response.get(timeout=timeout)
            except queue.Empty:raise TimeoutError(f'Codex {method} response timed out; no automatic replay')
            if message.get('error'):raise ValueError(str(message['error'].get('message','Codex request failed')))
            return message.get('result',{})
        finally:
            with self.lock:self.pending.pop(request_id,None)

    def notify(self,method,params):self._send({'method':method,'params':params})
    def respond(self,request_id,result=None,error=None):self._send({'id':request_id,**({'error':error} if error else {'result':result})})

    def _read(self):
        process=self.process
        try:
            for line in process.stdout:
                try:message=json.loads(line)
                except ValueError:continue
                if 'method' in message:
                    if 'id' in message:threading.Thread(target=self.on_request,args=(message,),daemon=True).start()
                    else:
                        try:self.on_event(message['method'],message.get('params') or {})
                        except Exception as e:self.stderr.append(str(e)[:300])
                elif 'id' in message:
                    with self.lock:waiting=self.pending.get(message['id'])
                    if waiting:waiting.put(message)
        finally:
            with self.lock:waiting=list(self.pending.values())
            for q in waiting:
                try:q.put_nowait({'error':{'message':'Codex connection closed; task state is unknown until reconciled'}})
                except queue.Full:pass
            self.on_event('neural/runtimeClosed',{})

    def _errors(self):
        for line in self.process.stderr:
            # Keep diagnostics in memory, never forward raw environment or credentials to UI.
            self.stderr.append(line.rstrip()[:500]);self.stderr=self.stderr[-20:]

    def close(self):
        process=self.process
        if process and process.poll() is None:
            try:process.stdin.close();process.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):terminate(process)
        self.process=None;self.ready=False


def quota_windows(payload):
    buckets=payload.get('rateLimitsByLimitId') or {'codex':payload.get('rateLimits')}
    rows=[]
    for key,bucket in buckets.items():
        if not isinstance(bucket,dict):continue
        for slot in ['primary','secondary']:
            window=bucket.get(slot)
            if not isinstance(window,dict) or window.get('usedPercent') is None:continue
            rows.append({'name':str(bucket.get('limitName') or key)+' / '+slot,'limit_id':key,'remaining_percent':max(0,min(100,100-float(window['usedPercent']))),'reset_at':window.get('resetsAt'),'window_minutes':window.get('windowDurationMins')})
    return rows
