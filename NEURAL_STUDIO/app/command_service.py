"""App-owned Leader session. Idle reads never invoke a model.

Only explicit sends and registered, terminal worker completions can start turns.
The supported Codex app-server owns execution; Neural persists public evidence.
"""
import copy, hashlib, json, re, threading, uuid, time, os
from pathlib import Path
from operations import load, save, stamp
from codex_rpc import CodexRPC, quota_windows
from director_backup import DirectorBackup
from workflows import WorkflowProfiles
from chat_images import ChatImages
from lumen_editor import director_guard


TOOLS={
 'neural_workbench':('Shared blueprint, approved treatment methods, recovery tickets and per-task usage evidence. consult_recovery starts one explicitly chosen capable bounded worker and registers its real completion watch; finish inference while waiting. No model evaluations. Recipes need separate human approval.',{'action':{'type':'string','enum':['status','blueprint','save_blueprint','recipes','propose_recipe','recovery','save_recovery','consult_recovery','usage']},'data':{'type':'object'}}),
 'neural_lumen_editor':('Lumen’s separate Gemini Flash trial-editor role. Status/history uses no model call. Assign a NEW trial with source_project_id and brief; it waits for the exclusive editing lane and preserves existing projects. Lumen is a worker, not a replacement director.',{'action':{'type':'string','enum':['status','assign','stop','reconcile','resume','release','feedback']},'brief':{'type':'string'},'title':{'type':'string'},'source_project_id':{'type':'string'},'assets':{'type':'array','items':{'type':'string'}},'text':{'type':'string'}}),
 'neural_team':('Shared goal, peers and visible team channel. message records an attributed Director message/help/reply with evidence; channel reads messages. Neither starts a model. Assign a scoped consultation separately if an answer requires reasoning; never fake a teammate reply.',{'action':{'type':'string','enum':['status','recall','note','channel','message']},'project_id':{'type':'string'},'query':{'type':'string'},'station':{'type':'string'},'note':{'type':'object'},'message':{'type':'object'}}),
 'neural_staffing':('Read capability-based station staffing advice without a model call. Any connected AI can enter any station; choose a capable available profile and record why. Task-depth preferences are not model benchmarks.',{'station':{'type':'string'},'required_capabilities':{'type':'array','items':{'type':'string'}},'difficulty':{'type':'string','enum':['routine','standard','complex']}}),
 'neural_local_ops':('Submit one deterministic local pipeline or built-in recipe, inspect compact status, or list capabilities. Stages chain locally with zero model calls; watched pipelines wake once at the terminal gate.',{'action':{'type':'string','enum':['capabilities','submit','status','cancel']},'plan':{'type':'object'},'recipe':{'type':'string','enum':['prepare','delivery']},'args':{'type':'object'},'job_id':{'type':'string'},'wake_on_completion':{'type':'boolean'}}),
 'neural_status':('Read current projects, bound workers and real jobs without inference.',{}),
 'neural_production':('Read or replace the revision-bound production checklist. Record concrete remaining work, evidence and independent quality gates; verified is not the same as built. Human acceptance cannot be set by the director. Read before updating to obtain expected_updated_at.',{'action':{'type':'string','enum':['status','update']},'plan':{'type':'object'}}),
 'neural_create_project':('Create a persistent local project from the human brief.',{'name':{'type':'string'},'brief':{'type':'string'},'mode':{'type':'string'},'assets':{'type':'array','items':{'type':'string'}}}),
 'neural_assign':('Write an explicit station assignment. Normal workers preserve conversations. For one independent Goldfish checkpoint set context_mode=fresh_review, project_revision and review DURING CREATION; review requires checkpoint_id,target_version,target_sha256,lens,objective,constraints,protected_work,acceptance_checks,safety_constraints. Supply actual bounded text/images; no private history or expected verdict. One changed-blocker recheck may set recheck_of and changed_blockers. This does not dispatch.',{'station':{'type':'string'},'title':{'type':'string'},'brief':{'type':'string'},'kind':{'type':'string'},'inputs':{'type':'array','items':{'type':'string'}},'project_id':{'type':'string'},'project_revision':{'type':'string'},'context_mode':{'type':'string','enum':['persistent','fresh_review']},'review':{'type':'object'},'blueprint_shot_ids':{'type':'array','items':{'type':'string'}},'recipe_ids':{'type':'array','items':{'type':'string'}},'required_capabilities':{'type':'array','items':{'type':'string'}}}),
 'neural_dispatch':('Start one bounded worker. Only supported free/subscription profiles are permitted. Optionally wake Leader once when terminal.',{'station':{'type':'string'},'task_id':{'type':'string'},'agent_id':{'type':'string'},'wake_on_completion':{'type':'boolean'},'required_capabilities':{'type':'array','items':{'type':'string'}},'assignment_reason':{'type':'string'},'recovery_of':{'type':'string'}}),
 'neural_result':('Validate a task and inspect its actual result and primary output.',{'station':{'type':'string'},'task_id':{'type':'string'}}),
 'neural_review':('Record a director structural review. Artistic approval belongs to the human.',{'station':{'type':'string'},'task_id':{'type':'string'},'decision':{'type':'string'},'note':{'type':'string'}}),
 'neural_cancel':('Cancel a real app-owned worker job.',{'job_id':{'type':'string'}}),
 'neural_render':('Render an explicitly requested FFmpeg rough assembly from original project-bin sources; no AE effects are implied.',{'project_id':{'type':'string'},'format':{'type':'string'},'shots':{'type':'array','items':{'type':'object'}},'music_id':{'type':'string'}}),
 'neural_watch_native':('Watch the exact current studio-owned TonyFX command locally. Finish your turn; one matching terminal result or bounded timeout wakes Leader once. This never executes or resends a command.',{'command_id':{'type':'string'},'timeout_seconds':{'type':'integer','minimum':5,'maximum':3600}}),
 'neural_register_preview':('Register a completed playable native MP4 under studio/data for the world screening room. Registration is not artistic approval.',{'path':{'type':'string'},'title':{'type':'string'},'revision':{'type':'string'},'kind':{'type':'string','enum':['full','proof']},'note':{'type':'string'},'current':{'type':'boolean'},'project_id':{'type':'string'}}),
}
REQUIRED={'neural_team':['action'],'neural_staffing':['station'],'neural_local_ops':['action'],'neural_create_project':['name','brief'],'neural_assign':['station','title','brief'],'neural_dispatch':['station','task_id','agent_id'],'neural_result':['station','task_id'],'neural_review':['station','task_id','decision'],'neural_cancel':['job_id'],'neural_render':['project_id','shots'],'neural_watch_native':['command_id'],'neural_register_preview':['path','title','revision']}

def tool_specs():
 return [{'type':'function','name':name,'description':desc,'inputSchema':{'type':'object','properties':props,'required':REQUIRED.get(name,[]),'additionalProperties':False}} for name,(desc,props) in TOOLS.items()]


class CommandService(DirectorBackup):
 active={'starting','working','awaiting_approval','cancelling','uncertain'}
 def __init__(self,runtime,rpc_factory=CodexRPC,native_bridge=None):
  self.runtime=runtime;self.root=runtime.root;self.path=self.root/'data/command/STATE.json'
  self.lock=threading.RLock();self.closed=False;self.connected=False;self.pending_requests={};self.drain_scheduled=False;self.usage_refresh_running=False;self._bg_threads=[];self.reset_timers={}
  self.native_bridge=Path(native_bridge or os.environ.get('NEURAL_TONYFX_BRIDGE') or (Path.home()/'Documents'/'ae-mcp-bridge'));self.native_watch_stops={}
  self.backup_cancel=threading.Event()
  try:self.saved=load(self.path)
  except (OSError,ValueError):self.saved={}
  self.saved.setdefault('leader',{'status':'idle','thread_id':None,'turn_id':None,'model':None,'messages':[],'error':None})
  self.saved.setdefault('events',[]);self.saved.setdefault('usage',{});self.saved.setdefault('watches',{})
  self.saved.setdefault('created_at',stamp());self.saved.setdefault('continuation_authorized',False);self.saved.setdefault('completion_wakes',0)
  from continuity import scope_sessions
  scope_sessions(self.saved,WorkflowProfiles(self.root).snapshot())
  if self.saved['leader']['status'] in self.active:
   if self.saved['leader'].get('provider') in ('antigravity','claude'):self.saved['leader'].update(status='uncertain',error='Studio restarted during a backup director turn. Its process and native execution must be reconciled before any new director.',turn_id=None)
   else:self.saved['leader'].update(status='interrupted',error='Studio restarted during a turn. No prompt was replayed. Resume with a new direction after checking evidence.',turn_id=None)
  # Retain authorized event subscriptions, never replay an interrupted model turn.
  self.saved['approvals']=[]
  signature=hashlib.sha256(json.dumps(tool_specs(),sort_keys=True).encode()).hexdigest()
  if self.saved.get('toolset_signature')!=signature and self.saved['leader'].get('thread_id') and (self.saved['leader']['status'] in ['idle','completed'] or self.saved['leader'].get('provider') in ('claude','antigravity')):
   # The installed protocol cannot replace dynamicTools on thread/resume.
   # Preserve the transcript/checkpoint and start the upgraded toolset only on
   # the NEXT authorized direction, without a migration model call.
   checkpoint=self.path.parent/'checkpoints'/('toolset-'+uuid.uuid4().hex+'.json');save(checkpoint,self.saved)
   old=self.saved['leader']['thread_id'];self.saved.setdefault('archived_threads',[]).append({'thread_id':old,'checkpoint':str(checkpoint),'time':stamp(),'reason':'Dynamic tool schema upgraded'})
   self.saved['toolset_handoff']='Local execution tools were upgraded. The visible conversation is preserved; prior backend context is archived at '+str(checkpoint)+'. Read shared/LEADER_CONTEXT.md and the latest ACTIVE_DIRECTOR_HANDOFF section for current scope. Do not replay historical tasks. Read only a needed checkpoint section if an unresolved fact is missing.\n\n'
   self.saved['leader'].update(thread_id=None,token_usage=None)
   if self.saved['leader'].get('provider','codex')=='codex':self.saved['leader']['turn_id']=None
  self.saved['toolset_signature']=signature
  self.rpc=rpc_factory(self.root,self._event,self._request)
  from production_workbench import UsageLedger
  UsageLedger(self.root).restarted()
  from director_profiles import DirectorSelector
  self.selector=DirectorSelector(self)
  self._persist()

 def _spawn(self,target,*args,**kwargs):
  t=threading.Thread(target=target,args=args,kwargs=kwargs,daemon=True)
  with self.lock:
   self._bg_threads=[x for x in self._bg_threads if x.is_alive()]+[t]
  t.start()
  return t

 def _persist(self,force=False):
  if self.closed and not force:return
  self.saved['events']=self.saved['events'][-160:];self.saved['leader']['messages']=self.saved['leader']['messages'][-160:]
  save(self.path,self.saved)

 def _record(self,kind,title,detail='',status='completed',**extra):
  row={'id':uuid.uuid4().hex,'kind':kind,'actor':'Leader','title':title,'detail':str(detail)[:16000],'status':status,'time':stamp(),**extra}
  self.saved['events'].append(row)
  if kind in ['direction','review','native','error'] and status in ['completed','failed','COMPLETED','FAILED','APPROVED','CHANGES_REQUESTED']:
   apprentice=getattr(self.runtime,'apprentice',None)
   if apprentice:apprentice.notify_event(kind,status)
  return row

 def snapshot(self):
  with self.lock:
   data=copy.deepcopy(self.saved)
  data['execution_policy']=self.execution_policy()
  data['director_policy']=self.director_policy();data['director_route']=copy.deepcopy(self.saved.get('director_route',{}))
  apprentice=getattr(self.runtime,'apprentice',None)
  if apprentice:data['apprentice']=apprentice.snapshot()
  data['conversation_policy_version']='2026-10-24.1';data['attachment_limits']=ChatImages.limits()
  data['usage_guard']={'context_input_limit':None,'session_policy':'persistent_provider_thread','context_management':'provider_runtime','tool_reply_chars_limit':10000,'automatic_provider_retry':False,'retry_after':data['leader'].get('retry_after',0)}
  jobs=self.runtime.jobs();workers=[]
  robots={'media':'pip','analysis':'nova','story':'scout','sound-design':'echo','editing':'codex','review-delivery':'sage'}
  lprov=data['leader'].get('provider','codex');lactive=data['leader']['status'] in {'starting','working','awaiting_approval','cancelling'}
  workers.append({'id':'leader','robot':'codex','name':'Leader · '+({'antigravity':'Antigravity','claude':'Claude'}.get(lprov,'Codex')),'provider':lprov,'configured_provider':lprov,'configured_model':data['leader'].get('model'),'active_model':data['leader'].get('model') if lactive else None,'model':data['leader'].get('model') or 'Reported on first connection','status':data['leader']['status'],'station':'editing'})
  for a in self.runtime.agents():
   assigned=[j for j in jobs if j.get('agent_id')==a['id']]
   job=next((j for j in assigned if j['status'] in self.runtime.active_states),None)
   latest=job or next(iter(assigned),{})
   station=job['station'] if job else (a.get('stations') or [''])[0]
   issue=self.runtime.profile_issue(a) if hasattr(self.runtime,'profile_issue') else None
   provider=self.runtime.providers.get(a['provider'],{}) if hasattr(self.runtime,'providers') else {}
   if a['provider']=='antigravity' and not provider.get('authenticated'):issue=provider.get('auth') or 'Background connection has not been verified yet.'
   if latest.get('idle_inference')=='unknown':issue='Client stopped, but remote execution is unverified. Reconcile before sending another task.'
   res_summary=None
   if latest.get('station') and latest.get('task_id'):
    try:res_summary=str(load(self.runtime.store.task_folder(latest['station'],latest['task_id'])/'RESULT.json').get('summary') or '')[:240] or None
    except Exception:res_summary=None
   workers.append({'id':a['id'],'robot':robots.get(station),'name':a['name'],'provider':a['provider'],'configured_provider':a['provider'],'configured_model':a.get('model'),'active_model':job.get('model') if job else None,'model':(job.get('model') if job else None) or a.get('model') or 'Provider default (when active)','station':station,'status':job['status'] if job else ('unavailable' if issue else 'idle'),'job_id':job['id'] if job else None,'active_job':{k:job.get(k) for k in ('id','task_id','station','title','status','model','started_at')} if job else None,'latest_job':{k:latest.get(k) for k in ('id','task_id','station','title','status','model','assignment_reason','finished_at','created_at','error')} if latest else None,'last_job_id':latest.get('id'),'last_model':latest.get('model'),'last_status':latest.get('status'),'last_activity':latest.get('finished_at') or latest.get('started_at') or latest.get('created_at'),'assignment_reason':(job or latest).get('assignment_reason'),'result_summary':res_summary,'usage':latest.get('usage'),'detail':issue})
  data['workers']=workers
  for worker in workers:
   if worker['id']!='leader':worker['stations']=next((a.get('stations',[]) for a in self.runtime.agents() if a['id']==worker['id']),[])
  for provider in ['codex','claude','opencode','antigravity','gemini']:
   data['usage'].setdefault(provider,{'status':'unavailable','windows':[],'detail':'Not queried. No model turn is started by reading this screen.'})
  if hasattr(self.runtime,'headless'):
   cached=self.runtime.headless.snapshot().get('antigravity',{}).get('quota') or {}
   if cached.get('cached') and cached.get('windows'):
    data['usage']['antigravity']={'status':'cached','windows':cached['windows'],'checked_at':cached.get('checked_at_unix'),'detail':'Last verified account/model quotas. A fresh metadata check is pending or unavailable; these dated values do not prove current access.'}
  for name in ['opencode','gemini','claude']:
   data['usage'][name]['detail']='Remaining model/account quota is not exposed by this connection. Completed job tokens are not a remaining quota.'
  from claude_usage import snapshot as claude_quota
  data['usage']['claude']=claude_quota(self.root)
  if data['leader'].get('provider')=='claude':
   data['usage']['claude']['call_usage']=data['leader'].get('backup_usage')
   data['usage']['claude']['model']=data['leader'].get('model')
  # Worker records are actual persisted state; never synthesize a successful result.
  for j in jobs[:35]:
   if j['status'] not in self.runtime.active_states and j['created_at']<data['created_at']:continue
   data['events'].append({'id':'job-'+j['id'],'kind':'worker','actor':j.get('agent_name','Worker'),'station':j.get('station'),'title':j.get('title','Worker task'),'detail':j.get('error') or 'Open process log and task evidence for actual output.','status':j['status'],'time':j.get('finished_at') or j.get('started_at') or j['created_at'],'job_id':j['id'],'task_id':j.get('task_id')})
  return data

 def summary(self):
  with self.lock:return {k:self.saved['leader'].get(k) for k in ['status','provider','model','thread_id','turn_id','error']}|{'continuation_authorized':bool(self.saved.get('continuation_authorized')),'paused':bool(self.saved.get('production_pause'))}

 def refresh_usage(self):
  with self.lock:
   if self.closed:raise ValueError('Studio is shutting down')
  try:
   self.rpc.start();raw=self.rpc.call('account/rateLimits/read')
   row={'status':'reported','windows':quota_windows(raw),'checked_at':stamp(),'detail':'Shared ChatGPT/Codex account limits, not a fabricated per-robot allocation. Reading limits starts no model turn.'}
  except Exception as e:row={'status':'unavailable','windows':[],'checked_at':stamp(),'detail':str(e)[:1000]}
  with self.lock:
   self.saved['usage']['codex']=row
   if row.get('status')=='reported' and row.get('windows'):self.saved['codex_quota_exhausted']=any(w.get('remaining_percent',100)<=0 and isinstance(w.get('reset_at'),(int,float)) and w['reset_at']>time.time() for w in row['windows'])
   self._persist()
  if hasattr(self.runtime,'headless') and self.runtime.headless.agy:
   raw=self.runtime.headless.query_agy('quota')
   quota=raw.get('quota') or {}
   row={'status':'reported' if raw.get('status')=='OK' else 'unavailable','windows':quota.get('windows',[]),'checked_at':stamp() if raw.get('status')=='OK' else quota.get('checked_at_unix'),'detail':'Official Antigravity account/model groups, shared by every robot using this account. Metadata only; no AI turn.' if raw.get('status')=='OK' else raw.get('error','Quota unavailable')}
   with self.lock:self.saved['usage']['antigravity']=row;self._persist()
   self.runtime.providers['antigravity']={**self.runtime.providers.get('antigravity',{}),**self.runtime.headless.snapshot()['antigravity'],'authenticated':raw.get('access_verified',False)}
  return self.snapshot()

 def request_usage_refresh(self):
  with self.lock:
   if self.closed:raise ValueError('Studio is shutting down')
   if self.usage_refresh_running:return self.snapshot()
   self.usage_refresh_running=True
   for provider in ['codex','antigravity']:
    row=self.saved['usage'].setdefault(provider,{'windows':[]})
    row.update(status='refreshing',detail='Reading account metadata; no AI turn is started. Previous numbers remain dated until verified.');self._persist()
  def refresh():
   try:self.refresh_usage()
   finally:
    with self.lock:self.usage_refresh_running=False
  self._spawn(refresh)
  return self.snapshot()

 def send(self,message,internal=False,attachments=None):
  from execution_control import stop_direction
  if not internal and stop_direction(message):
   with self.lock:
    self.saved['leader']['messages'].append({'id':uuid.uuid4().hex,'role':'user','text':str(message).strip(),'status':'sent','created_at':stamp()})
    self._record('direction','Human stop — no model call','Stop/pause routed locally; automatic continuation is revoked.','completed')
    return self.stop()
  return self._send_direction(message,internal=internal,attachments=attachments)

 @director_guard
 def _send_direction(self,message,internal=False,attachments=None):
  text=str(message).strip()
  images=ChatImages(self.root).resolve(attachments or [])
  if not text and images:text='Please review the attached screenshots.'
  if not text or len(text)>24000:raise ValueError('Enter a direction of 1–24000 characters')
  with self.lock:
   if self.closed:raise ValueError('Studio is shutting down')
   if internal and not self.saved.get('continuation_authorized'):raise ValueError('Continuation was explicitly stopped')
   leader=self.saved['leader']
   alive = any(x.is_alive() for x in self._bg_threads)
   # `uncertain` is an UNKNOWN outcome: it is cleared only by terminal evidence, never by a missing thread.
   if not alive and leader['status']=='uncertain':self._reconcile_uncertain(leader)
   # A Codex turn is owned by the live RPC connection, not by a local thread; only a thread-owned
   # (Claude/Antigravity) turn or a disconnected Codex runtime is provably stale without a thread.
   stale=not alive and (leader.get('provider') in ('claude','antigravity') or not self.connected) and not self._handoff_native_pending()
   if stale and leader['status'] in ('cancelling','starting','working','error'):
    leader['status']='idle'
    leader['error']=None
   if leader['status'] in self.active:
    if stale and leader['status']!='uncertain':
     leader['status']='idle'
    else:
     raise ValueError('Leader is already working; stop or finish the active turn first' if leader['status']!='uncertain' else 'The previous director turn has an unknown outcome. Reconcile its execution first; nothing was replayed and no request was sent.')
   from continuity import scope_sessions
   if scope_sessions(self.saved,WorkflowProfiles(self.root).snapshot()):self.connected=False
   # An explicit manual selection routes to exactly that profile and never silently falls back.
   manual=self.selector.route()
   if manual:
    backup=manual['kind']!='codex'
    from director_profiles import _capabilities
    if images and not _capabilities(manual,root=self.root,runtime=self.runtime)['images']['supported']:raise ValueError(manual['label']+' has no verified screenshot input path, so no blind text-only turn was started. Choose Sol High or a commissioned director for screenshots; your draft and attachments are kept.')
    if manual['kind']=='claude':
     ex=self.saved.get('native_claude_exhausted')
     if ex and ex.get('reset_at') and ex['reset_at']<=time.time():self.saved.pop('native_claude_exhausted',None);ex=None  # reported reset has passed: stale flag cleared
     if ex:raise ValueError('Selected native Claude refused for allowance and no other director is substituted. Use Retry Claude after its reset or select another director explicitly.')
   else:
    # No explicit selection: the route follows the policy's primary provider; Codex state gates only a Codex route.
    policy=self.director_policy()
    backup=policy.get('enabled') is True and (policy.get('primary','codex')!='codex' or self._codex_exhausted())
   if images and backup and not manual and not self._native_vision_ready():raise ValueError('Screenshots need the Codex director or the native Claude director. Only the Gemini fallback is available right now, and it cannot see images; your draft is kept.')
   if not backup and time.time()<leader.get('retry_after',0):raise ValueError('Provider is temporarily unavailable. Wait a few minutes before trying again. No AI request was sent.')
   windows=self.saved.get('usage',{}).get('codex',{}).get('windows',[])
   if not backup and self._codex_exhausted():raise ValueError('Reported Codex allowance is exhausted until its reset. No AI request was sent.')
   if not backup:
    leader['provider']='codex'
    if (leader.get('model') or '').startswith(('gemini-','claude-')):leader['model']=self.director_policy().get('primary_model','gpt-6.1-sol')
   context_note=('' if backup else self._bound_context())+self.saved.pop('toolset_handoff','')
   if not internal:
    self.saved['continuation_authorized']=True;self.saved['pending_image_input']=bool(images)
    self.saved.pop('production_pause',None)
    self.saved['production_direction']=uuid.uuid4().hex
    self.saved['production_outcome']={'status':'direction_received','title':'New direction received','detail':'Previous production results are preserved; current-direction checkpoints must be reconciled before production work.'}
   self.saved['backup_suppressed']=False;self.backup_cancel=threading.Event()
   if not internal:
    (self.root/'shared').mkdir(exist_ok=True)
    (self.root/'shared/LATEST_DIRECTOR_DIRECTION.md').write_text(text,encoding='utf-8')
    from production import ProductionBoard
    ProductionBoard(self.root).direction_received()
   leader.update(status='starting',error=None,turn_id=None)
   leader['messages'].append({'id':uuid.uuid4().hex,'role':'system' if internal else 'user','text':text,'status':'sent','created_at':stamp(),**({'attachments':images} if images else {})})
   from continuity import director_context
   oversight=bool(manual and manual['kind']=='claude' and self.director_policy().get('oversight_mode',True))
   context_note+=director_context(self.root,self.saved,compact=bool(oversight and leader.get('claude_session_id')),
                                  oversight=oversight,native_pending=self._handoff_native_pending())
   self._record('direction','Worker completion' if internal else 'Human direction received',text,'starting');self._persist()
  if manual and manual['kind']!='codex':self._spawn(self._manual_turn,manual,context_note+text,images)
  elif backup:self._spawn(self._backup_turn,context_note+text,**({'images':images} if images else {}))
  else:self._spawn(self._turn,*((context_note+text,images) if images else (context_note+text,)))
  return self.snapshot()

 def _reconcile_uncertain(self,leader):
  """Clear an UNKNOWN director outcome only from terminal evidence; never replay and never guess.

  Evidence: the director run RESULT.json (process stopped, no remote inference) or Codex thread/read
  (no in-progress turn), AND no unresolved exact native command. Otherwise stay blocked and publish
  exactly one deduplicated attention event."""
  evidence=None;key='uncertain-director:'+str(leader.get('turn_id') or Path(self.saved.get('director_route',{}).get('run','') or 'none').name)
  try:
   if self._handoff_native_pending():raise ValueError('native command unresolved')
   if leader.get('provider') in ('claude','antigravity'):
    folder=Path(self.saved.get('director_route',{}).get('run','')).resolve()
    if not folder.is_relative_to((self.root/'data/command/director-runs').resolve()):raise ValueError('no run folder')
    r=load(folder/'RESULT.json')
    if r.get('status') in ('FAILED','COMPLETED','TIMED_OUT') and r.get('process_stopped') is True and r.get('idle_inference') is False:
     evidence={'source':str(folder/'RESULT.json'),'status':r['status'],'kind':'director-run-result'}
   elif leader.get('thread_id') and self.connected:
    turns=self.rpc.call('thread/read',{'threadId':leader['thread_id'],'includeTurns':True}).get('thread',{}).get('turns')
    if turns is not None and not any(t.get('status') in ('inProgress','running') for t in turns):
     evidence={'source':'codex thread/read '+str(leader['thread_id']),'status':'no in-progress turn','kind':'codex-thread-read'}
  except Exception:evidence=None
  if not evidence:
   try:
    from attention import AttentionStore
    AttentionStore(self.root).publish(key,'Director outcome is UNKNOWN','No terminal evidence was found for the previous director turn or its native command. Nothing was replayed and no new director will start. Reconcile the run result / native bridge result, then choose a director.')
   except Exception:pass
   return False
  leader.update(status='interrupted',turn_id=None,error='Previous director outcome reconciled from terminal evidence; nothing was replayed.')
  self.saved.setdefault('uncertain_reconciliations',[]).append({**evidence,'at':stamp(),'key':key})
  self._record('director','Unknown director outcome reconciled',json.dumps(evidence),'completed');self._persist()
  return True

 def _manual_turn(self,profile,text,images):
  from director_profiles import run_manual_turn
  return run_manual_turn(self,profile,text,images)

 def _provenance(self):
  """Host-attributed model/provider identity of the director that produced a message."""
  with self.lock:
   leader=self.saved['leader'];route=self.saved.get('director_route',{})
   return {'provider':leader.get('provider') or 'codex','model':leader.get('model'),'profile_id':route.get('profile_id') or (self.selector.selected_id() if hasattr(self,'selector') else None),'run':route.get('run')}

 def _bound_context(self):
  # Keep the provider conversation across human directions AND completion wakes.
  # Input size is not evidence that history must be replaced: the official
  # runtime owns context compaction within this thread. A local checkpoint is
  # durable evidence, not a substitute for continuing the actual conversation.
  # Workflow isolation and incompatible dynamic-tool upgrades are handled
  # separately; neither a token count nor a new project clears thread_id here.
  return ''

 def workflow_changed(self,profile_id):
  """Keep the visible conversation, but do not reuse another workflow's model context."""
  with self.lock:
   if self.saved['leader']['status'] in self.active:raise ValueError('Finish the active director before changing workflow')
   previous=self.saved['leader'].get('thread_id')
   if previous:self.saved.setdefault('archived_threads',[]).append({'thread_id':previous,'time':stamp(),'reason':'Workflow changed to '+profile_id})
   from continuity import scope_sessions
   scope_sessions(self.saved,WorkflowProfiles(self.root).snapshot())
   self.connected=False
   self.saved['toolset_handoff']='The human selected workflow '+profile_id+'. Apply its current instructions. The visible older conversation is history, not a new assignment. Do not resume historical projects.\n\n'
   self._record('workflow','Workflow selected',profile_id+' · next explicit send starts a fresh workflow context; no inference started.')
   self._persist()

 def instructions(self):
  permission_note='The human has authorized unattended local workflow execution. Local command/file permissions are handled by the app; do not ask for the same permission repeatedly.' if self.execution_policy()['local_execution']=='unattended' else 'Requests for local execution approval are shown in this app.'
  return f'''You are Leader, the main Codex director inside Neural Posthouse, a local Windows desktop studio.
The human uses this app as their primary workflow workspace for both video production and general-assistant tasks (engineering, research, local scripting, file/shell/web help). Speak to them here. Be concise; expose real assignments, public decisions and tool evidence here. Non-video assistant requests may be answered or executed directly without forcing a video production checklist, while all video/editing work follows the production checklist and TonyFX rules below.
Active workflow (overrides artistic defaults): {WorkflowProfiles(self.root).snapshot('editing')['instructions']}.
Workspace: {self.root}. Start by reading shared/LEADER_CONTEXT.md and relevant station START_HERE.md and skills only when needed. Use neural_status for real state.
Read shared/PRODUCTION_CHECKPOINT_WORKFLOW.md. At the start of authorized production, create/update a concrete revision-bound checklist with neural_production (or tools/production.py); update once per real decision/checkpoint before ending a turn. Include outstanding human requirements, not only mechanical render steps. Existing sessions may use the loopback API /api/production and /api/production/update. Record estimates as justified remaining-minute ranges only when supported; leave unknown rather than inventing a deadline. Verified steps require matching evidence and an appropriate method. Built, sampled picture, full-speed motion, actual listening and human acceptance are separate. Never silently drop a failed/pending requirement or mark human approval yourself. A review copy with untested gates is ready for review, not a finished accepted edit.
Required work is not blocked just because it has not been done. Continue repairable work before ending. A true blocked checkpoint requires blocker: {{kind: recoverable|capability|human_input|native_unknown|quota, reason: exact obstacle, attempted: actual diagnosis performed, next_action: what resolves it}}. Continue other independent work. The app reconciles the checklist after a completed turn: one recovery per unchanged unfinished state; a persistent or externally blocked state creates a visible persistent alert and requests a Windows system sound. Human acceptance is the normal final pause; unverified motion/listening needs a real capability assessment or explicit human-review handoff, never invented PASS.
Mechanical work MUST use neural_local_ops (capabilities first) or tools/local_ops.py before considering model delegation or handwritten project scripts. Read shared/LOCAL_OPS_WORKFLOW.md for the plan contract. Chain probes, exact frames, numeric audio preparation, collision checks, state diffs, format QA, review copies and registration in ONE local plan. Wake only at the final decision/failure gate, then finish your turn. Engine model_calls=0 excludes any director/creative/provider turns. Inspect compact SUMMARY.json and relevant failed/ambiguous evidence instead of raw logs or every frame. Unsupported creative/native operations stay explicit; never quietly substitute a rough cut for the requested edit.
Existing station adapters are bounded evidence/planning workers, not full native editors. Do not claim they watched/listened, edited AE, or completed work without validated evidence.
Read shared/TEAMWORK_PROTOCOL.md and shared/STATION_ROUTING_AND_MEMORY.md. Use neural_team for shared goal/owners and recall earlier edits; record supported findings/corrections/help. Read neural_team action=channel for addressed messages. Use action=message with message {{project_id,kind,to,text,reply_to?,source?}} to explain your diagnosis/decision visibly; assign a bounded consultation if a peer needs help, and have the real consultant reply to the message ID. Do not invent conversations or accept bad work as done. A failed teammate gets a NEW scoped handoff with recovery_of and a concrete changed approach after execution is reconciled. Use neural_staffing for capability, availability and task-depth advice before neural_assign/neural_dispatch. Home stations do not restrict AI assignments. Record why the selected adapter fits the actual task; a text sound planner cannot listen. Delegate capable bounded work with neural_assign and neural_dispatch. Include exact scope, acceptance criteria, required skills and source preservation in the brief. Tool calls/instructions are visible in the app. Respect configured worker limits. When parallel_text_stations is enabled, independent text-evidence specialists in different departments may overlap (maximum two workers); local media jobs, renders and native editing stay serialized. No blind command retries or provider/model substitutions. Diagnose confirmed failures and apply scoped corrections autonomously; quota routing is owned by the app. No API keys, paid APIs, installations or credentials access.
You own routine debugging and recovery with the available file/shell tools, including native script failures. A static worker PASS is not proof that an AE API call is valid. Inspect actual property state and the relevant skill before correction; never repeat a helper that caused the failure. No six-turn continuation limit exists: real registered completions keep the already authorized task moving until done or explicitly stopped. Do not ask the human to type continue for normal execution errors. When waiting, register wake_on_completion on dispatch and finish your turn. The local service wakes you ONCE on terminal result. No LLM polling, sleep/status loops, repeated prompts or empty progress reports. Idle is no model turn. Each active turn uses the account allowance; never promise zero usage while working.
If a TonyFX wait expires with UNKNOWN completion, register neural_watch_native with the exact submitted command ID before finishing. It observes local result files without inference and wakes once on matching completion or a bounded needs-attention timeout. For an older session without this dynamic tool, POST JSON {{"command_id":"exact-id","timeout_seconds":900}} to the local /api/command/watch-native route using the X-Studio-Token from /api/config, without printing the token. Never redispatch or remove locks to recover a timeout. Inspect the matching transport result, script report and actual AE state before any corrected command. Register completed playable native MP4 proofs with neural_register_preview (or POST /api/previews/register in an older session) so the human can review them in the world; state which revision they are and distinguish technical evidence from artistic acceptance.
Keep usage bounded: use compact file sections and concise tool results; do not print full inventories, transcripts or prior analysis. Reuse validated measurements from the current project. Workers return bounded outputs. If a provider fails or is at capacity, stop rather than probing it repeatedly. Long sessions continue from a local checkpoint; the full history stays saved and need not be reread.
Use native file/shell tools for actual local work when required. Preserve source files and unrelated projects. Read workflow skills before native editing. Only one serialized TonyFX editor, no MCP Bridge Auto. Never reuse completed scenes, mattes, outros or old builders as fresh work. Never resume paused projects on your own.
The Tyler LET GO repair is DEFERRED while this app task is being completed. Do not touch AE or dispatch that edit unless the human explicitly resumes it here.
{permission_note} This does not authorize new paid services, credentials, unrelated destructive changes or publishing. Ask only for genuinely missing creative information. The human gives final artistic acceptance. Never invent usage, auth, job cancellation, or tool success.
This is a persistent app-owned Codex session using the existing account. It is not a live clone of the earlier Codex desktop conversation. Read the handoff for continuity. Inherit no imaginary plugins or GUI access.
'''

 def _turn(self,text,images=None):
  phase='connect'
  try:
   # A saved conversation must not silently pin the previously used model.
   requested_model=self.director_policy().get('primary_model')
   requested_effort=self.director_policy().get('primary_effort','medium')
   if requested_effort not in ('none','minimal','low','medium','high','xhigh','max','ultra'):raise ValueError('Unsupported configured director reasoning effort')
   self.rpc.start()
   if not self.connected:
    with self.lock:thread_id=self.saved['leader'].get('thread_id')
    unattended=self.execution_policy()['local_execution']=='unattended'
    params={'cwd':str(self.root),'approvalPolicy':'never' if unattended else 'on-request','sandbox':'danger-full-access' if unattended else 'workspace-write','developerInstructions':self.instructions(),**({'model':requested_model} if requested_model else {})}
    if thread_id:result=self.rpc.call('thread/resume',{'threadId':thread_id,'excludeTurns':True,**params})
    else:result=self.rpc.call('thread/start',{**params,**({'model':self.saved['leader']['model']} if not requested_model and self.saved['leader'].get('model') else {}),'dynamicTools':tool_specs(),'allowProviderModelFallback':False,'serviceName':'Neural Posthouse'})
    if thread_id and result['thread']['id']!=thread_id:raise ValueError('Codex returned a different conversation ID on resume. Original conversation preserved; no blank replacement was started.')
    with self.lock:
     self.saved['leader'].update(thread_id=result['thread']['id'],model=result.get('model'));self.connected=True;self._persist()
   with self.lock:
    if self.saved['leader']['status']=='cancelling':
     self.saved['leader'].update(status='idle');self._persist();return
    thread_id=self.saved['leader']['thread_id']
    if requested_model:self.saved['leader']['model']=requested_model
   phase='turn/start'
   unattended=self.execution_policy()['local_execution']=='unattended'
   inputs=[{'type':'text','text':text,'text_elements':[]}]+[{'type':'localImage','path':str(ChatImages(self.root).path(row['id']))} for row in images or []]
   result=self.rpc.call('turn/start',{'threadId':thread_id,'input':inputs,**({'model':requested_model} if requested_model else {}),'effort':requested_effort,'approvalPolicy':'never' if unattended else 'on-request','sandboxPolicy':{'type':'dangerFullAccess'} if unattended else {'type':'workspaceWrite','writableRoots':[str(self.root)],'networkAccess':True}})
   with self.lock:
    if self.saved['leader']['status'] in ['starting','working','cancelling']:
     self.saved['leader']['turn_id']=result['turn']['id'];self._persist()
    cancelled=self.saved['leader']['status']=='cancelling'
   if cancelled:self.rpc.call('turn/interrupt',{'threadId':thread_id,'turnId':result['turn']['id']})
  except Exception as e:
   with self.lock:
    quota_refusal=isinstance(e,ValueError) and any(s in str(e).lower() for s in ['usagelimitexceeded','you have hit your usage limit',"you've hit your usage limit",'usage limit reached'])
    if quota_refusal:self.saved['codex_quota_exhausted']=True
    uncertain=phase=='turn/start' and self.saved['leader']['status']!='idle'
    if quota_refusal:uncertain=False
    self.saved['leader'].update(status='uncertain' if uncertain else 'error',error=str(e)[:1600]);self._record('error','Leader request needs reconciliation' if uncertain else 'Leader could not complete the request',str(e),'uncertain' if uncertain else 'failed');self._persist()
    direction=next((e for e in reversed(self.saved['events']) if e['kind']=='direction' and e['status']=='starting'),None)
    if direction:direction['status']='uncertain' if uncertain else 'failed'
    self._persist()
   if quota_refusal:
    from usage_routing import request as request_quota_failover
    request_quota_failover(self,'codex',self.saved.get('production_direction') or 'unknown-direction')
   self.production_turn_finished('failed')

 def _event(self,method,p):
  with self.lock:
   leader=self.saved['leader']
   if method=='account/rateLimits/updated':
    self.saved['usage']['codex']={'status':'reported','windows':quota_windows(p),'checked_at':stamp(),'detail':'Shared account limits reported by Codex.'}
   elif method=='neural/runtimeClosed':
    self.connected=False
    if leader['status'] in self.active:leader.update(status='interrupted',error='Runtime connection closed. Execution state is uncertain; no automatic replay.')
    if leader.get('status')=='interrupted':threading.Thread(target=self.production_turn_finished,args=('failed',),daemon=True).start()
   elif p.get('threadId') and p['threadId']!=leader.get('thread_id'):return
   elif method=='turn/started':
    from inference_usage import begin
    begin(leader,p['turn']['id'])
    leader.update(status='working',turn_id=p['turn']['id'],retry_after=0)
    from production_workbench import call_event
    call_event(self.root,'codex:'+p['turn']['id'],'codex',leader.get('model'),'director',purpose='recovery' if self.saved.get('ledger_recovery_turn') else 'direction',source='Codex turn/started')
    self.saved['ledger_recovery_turn']=False
   elif method=='item/agentMessage/delta':
    row=next((m for m in leader['messages'] if m['id']==p['itemId']),None)
    if row is None:
     row={'id':p['itemId'],'role':'assistant','text':'','status':'streaming','created_at':stamp(),'provenance':{'provider':'codex','model':leader.get('model'),'profile_id':'sol-high'}};leader['messages'].append(row)
    row['text']+=p.get('delta','')
   elif method in ['item/started','item/completed']:
    item=p.get('item',{});kind=item.get('type');iid=item.get('id');done=method.endswith('completed')
    if kind=='agentMessage' and done:
     row=next((m for m in leader['messages'] if m['id']==iid),None)
     if row:row.update(text=item.get('text') or row['text'],status='completed')
     else:leader['messages'].append({'id':iid,'role':'assistant','text':item.get('text',''),'status':'completed','created_at':stamp()})
    elif kind in ['commandExecution','fileChange','dynamicToolCall','mcpToolCall','webSearch']:
     row=next((e for e in self.saved['events'] if e.get('item_id')==iid),None)
     detail=item.get('command') or item.get('tool') or item.get('query') or json.dumps(item.get('changes',[]),ensure_ascii=False)
     if row is None:row=self._record('tool',kind,detail,'working',item_id=iid)
     if done:row.update(status=item.get('status','completed'),detail=(str(detail)+'\n'+str(item.get('aggregatedOutput') or item.get('result') or ''))[:16000])
   elif method=='item/commandExecution/outputDelta':
    row=next((e for e in self.saved['events'] if e.get('item_id')==p.get('itemId')),None)
    if row:row['detail']=(row['detail']+'\n'+p.get('delta',''))[-16000:]
   elif method=='thread/tokenUsage/updated':
    leader['token_usage']=p.get('tokenUsage')
    if leader.get('turn_id'):
     from production_workbench import UsageLedger
     from inference_usage import observe
     UsageLedger(self.root).record('codex:'+leader['turn_id'],**observe(leader,p.get('tokenUsage') or {}))
   elif method=='turn/completed':
    if leader.get('turn_id'):
     from production_workbench import UsageLedger
     UsageLedger(self.root).record('codex:'+leader['turn_id'],status=p.get('turn',{}).get('status','unknown'),finished_at=stamp())
    turn=p.get('turn',{});status=turn.get('status','unknown');completed_turn_id=leader.get('turn_id') or turn.get('id');leader.update(status='idle' if status in ['completed','interrupted'] else 'error',turn_id=None,error=turn.get('error'))
    if status=='completed':self.saved['pending_image_input']=False
    if 'usagelimitexceeded' in json.dumps(turn.get('error') or {}).lower():self.saved['codex_quota_exhausted']=True
    self._record('turn','Leader '+status,'No further inference until a direction or registered completion. ',status)
    direction=next((e for e in reversed(self.saved['events']) if e['kind']=='direction' and e['status']=='starting'),None)
    if direction:direction['status']=status
    self.pending_requests.clear();self.saved['approvals']=[]
    if status=='failed' and 'usagelimitexceeded' in json.dumps(turn.get('error') or {}).lower():
     from usage_routing import request as request_quota_failover
     request_quota_failover(self,'codex',completed_turn_id or self.saved.get('production_direction') or 'unknown-direction')
    else:self._spawn(self._drain_wakes)
    self._spawn(self.production_turn_finished,status)
   elif method=='error':
    self._record('error','Runtime error',json.dumps(p,ensure_ascii=False),'failed')
    failure=(p.get('error') or {}).get('codexErrorInfo')
    if failure in ['serverOverloaded','usageLimitExceeded','rateLimitExceeded']:leader['retry_after']=time.time()+300
    if failure=='usageLimitExceeded':self.saved['codex_quota_exhausted']=True
   else:return
   self._persist()

 def _request(self,request):
  method=request['method'];p=request.get('params') or {};rid=request['id']
  if method=='item/tool/call':
   name=p.get('tool');args=p.get('arguments') or {}
   try:
    if not isinstance(args,dict):raise ValueError('Tool arguments must be an object')
    with self.lock:entry=self._record('delegation' if name in ['neural_assign','neural_dispatch'] else 'tool',name,json.dumps(args,ensure_ascii=False),'working');self._persist()
    result=self._tool(name,args)
    reply=self._compact_result(name,result)
    self.rpc.respond(rid,{'success':True,'contentItems':[{'type':'inputText','text':json.dumps(reply,ensure_ascii=False,default=str)}]})
    with self.lock:entry['status']='completed';self._record('tool',name+' result',json.dumps(result,ensure_ascii=False,default=str)[:8000]);self._persist()
   except Exception as e:
    with self.lock:
     if 'entry' in locals():entry['status']='failed'
     self._record('error',str(name)+' failed',str(e),'failed');self._persist()
    self.rpc.respond(rid,{'success':False,'contentItems':[{'type':'inputText','text':str(e)[:2000]}]})
   return
  if method in ['item/commandExecution/requestApproval','item/fileChange/requestApproval']:
   if self.execution_policy()['local_execution']=='unattended':
    with self.lock:
     if p.get('threadId') and p['threadId']!=self.saved['leader'].get('thread_id'):
      self.rpc.respond(rid,{'decision':'decline'});self._record('permission','Unmatched conversation permission declined',method,'failed');self._persist();return
     decision='acceptForSession' if not p.get('availableDecisions') or 'acceptForSession' in p['availableDecisions'] else 'accept'
     self.rpc.respond(rid,{'decision':decision});self._record('permission','Local execution allowed · standing authorization',method,request_id=str(rid));self._persist()
    return
   key=uuid.uuid4().hex
   with self.lock:
    self.pending_requests[key]=rid;self.saved['approvals'].append({'id':key,'title':'Allow local command?' if 'commandExecution' in method else 'Allow file changes?','detail':str(p.get('command') or p.get('reason') or json.dumps(p))[:8000],'choices':[{'value':'accept','label':'Allow once'},{'value':'decline','label':'Decline'}]});self.saved['leader']['status']='awaiting_approval';self._persist()
   return
  if method=='item/permissions/requestApproval' and self.execution_policy()['local_execution']=='unattended':
   permissions=p.get('permissions')
   with self.lock:
    if not isinstance(permissions,dict) or not permissions or (p.get('threadId') and p['threadId']!=self.saved['leader'].get('thread_id')):
     self.rpc.respond(rid,error={'code':-32602,'message':'Missing requested permissions or unmatched conversation'});return
    self.rpc.respond(rid,{'permissions':copy.deepcopy(permissions),'scope':'session'})
    self._record('permission','Requested tool access granted · standing authorization',method,request_id=str(rid));self._persist()
   return
  # Execution permission is distinct from creative questions/authentication.
  self.rpc.respond(rid,error={'code':-32601,'message':'Neural does not support this request type yet. Ask the human in your final message: '+method})

 def _tool(self,name,args):
  if name=='neural_local_ops':
   engine=getattr(self.runtime,'local_ops',None)
   if not engine:raise ValueError('Local execution engine is unavailable')
   action=args.get('action')
   if action=='capabilities':return engine.capabilities()
   if action=='status':return self._local_compact(engine.job(args['job_id'])) if args.get('job_id') else {'active':engine.snapshot()['active'],'recent':[self._local_compact(j) for j in engine.snapshot()['jobs'][:5]],'model_calls':0}
   if action=='cancel':return engine.cancel(args['job_id'])
   if action=='submit':
    with self.lock:
     wake=args.get('wake_on_completion',True)
     if wake and not self.saved.get('continuation_authorized'):raise ValueError('Continuation was stopped; no automatic director wake is authorized')
     plan=engine.recipe(args['recipe'],args.get('args',{})) if args.get('recipe') else args['plan']
     from production_workbench import project_of
     plan={**plan,'project_id':plan.get('project_id') or project_of(self.root).get('project_id')}
     job=engine.submit(plan)
     if wake:self.watch_local({'job_id':job['id']})
    # Handles a very short pipeline completing before the watch was installed.
    self.local_operation_finished(engine.job(job['id']))
    return self._local_compact(job)
   raise ValueError('Unknown local operation action')
  r=self.runtime
  if name=='neural_workbench':
   from production_workbench import action
   return action(self.root,args.get('action','status'),args.get('data',{}),runtime=r)
  if name=='neural_lumen_editor':
   editor=r.lumen_editor;action=args.get('action','status')
   if action=='assign':return editor.submit({**args,'wake_director':True})
   if action=='feedback':return editor.feedback(args)
   if action in ('stop','reconcile','resume','release'):return getattr(editor,action)()
   return editor.snapshot()
  if name=='neural_team':
   from team_memory import TeamMemory
   team=TeamMemory(self.root);action=args.get('action','status')
   if action=='channel':return team.channel(args.get('project_id'))
   if action=='message':return team.message(args.get('message',{}),sender='Director',attribution=self._provenance())
   if action=='recall':return {'matches':team.recall(args.get('query',''),args.get('station')),'model_calls':0}
   if action=='note':return team.note(args.get('note',{}))
   return team.director_brief(args.get('project_id'))
  if name=='neural_staffing':
   from staffing import roster
   return roster(r,args.get('station'),args.get('required_capabilities'),args.get('difficulty','standard'))
  if name=='neural_status':
   return {'agents':r.agents(),'projects':[{'id':p['id'],'name':p['name'],'mode':p['mode']} for p in r.projects()[:12]],'jobs':[{k:j.get(k) for k in ['id','task_id','station','agent_id','provider','model','status','title','error']} for j in r.jobs()[:20]],'max_concurrent_jobs':r.max_concurrent_jobs,'providers':r.providers,'note':'Historical jobs do not authorize resuming a project. Full task details are in their station folders.'}
  if name=='neural_create_project':return r.create_project(args)
  if name=='neural_production':
   from production import ProductionBoard
   board=ProductionBoard(self.root)
   if args.get('action','status')=='update':return board.update(args.get('plan',{}))
   return board.snapshot(r.local_ops.snapshot())
  if name=='neural_assign':return r.create_task(args)
  if name=='neural_dispatch':
   args=dict(args);wake=args.pop('wake_on_completion',True);job=r.dispatch(args)
   if wake:
    with self.lock:
     if self.saved.get('continuation_authorized'):self.saved['watches'][job['id']]={'status':'waiting'};self._persist()
    # Catch a local worker finishing between dispatch and registration.
    self.worker_changed(r.job(job['id']))
   return job
  if name=='neural_result':
   f=r.store.task_folder(args['station'],args['task_id']);out={'validation':r.store.validate(args['station'],f)}
   if (f/'RESULT.json').exists():
    result=load(f/'RESULT.json');out['result']=result
    from operations import bounded
    p=bounded(f/'outputs',f/result['primary_output'])
    if p.suffix in ['.json','.txt','.md','.csv'] and p.stat().st_size<=50000:out['output']=p.read_text(encoding='utf-8')
   return out
  if name=='neural_review':return r.store.review(args['station'],args['task_id'],args['decision'],args.get('note','')+' [Director structural review; human artistic acceptance remains separate.]')
  if name=='neural_cancel':return r.cancel(args['job_id'])
  if name=='neural_watch_native':return self.watch_native(args)
  if name=='neural_register_preview':
   from previews import PreviewCatalog
   return PreviewCatalog(self.root).register(args)
  if name=='neural_render':
   args=dict(args)
   if args.get('music_start',0):raise ValueError('This rough assembly supports the project music from its start. Use the native editing workflow for measured offsets.')
   if args.get('music_path'):
    assets=r.project(args['project_id'])['assets'];music=next((a for a in assets if Path(a['path']).resolve()==Path(args['music_path']).resolve()),None)
    if music is None:raise ValueError('Music must be an existing project-bin asset')
    args['music_id']=music['id']
   return r.render(args)
  raise ValueError('Unknown Neural tool: '+str(name))

 def _compact_result(self,name,result):
  if not isinstance(result,dict):return result
  fields={'neural_assign':['id','station','project_id','status','folder','readiness','skills','primary_output','errors'],
          'neural_dispatch':['id','station','task_id','agent_id','provider','model','status','title','error'],
          'neural_create_project':['id','name','mode','folder']}.get(name)
  reply={k:result[k] for k in fields if k in result} if fields else copy.deepcopy(result)
  if len(json.dumps(reply,ensure_ascii=False,default=str))>10000:
   folder=self.path.parent/'tool-results';folder.mkdir(parents=True,exist_ok=True);path=folder/(uuid.uuid4().hex+'.json')
   save(path,json.loads(json.dumps(result,ensure_ascii=False,default=str)))
   reply={'details_path':str(path),'note':'Full result saved locally. Read only the needed sections.'}
   for k in ['id','status','summary','validation','result']:
    if k in result and len(json.dumps(result[k],default=str))<2200:reply[k]=result[k]
  return reply

 def _local_compact(self,job):
  return {k:job.get(k) for k in ['id','title','status','current_step','error','cache_hits','model_calls']}|{'summary_path':str(self.root/'data/local-ops/jobs'/job['id']/'SUMMARY.json'),'steps':[{'id':s['id'],'status':s['status'],'cached':s.get('cached',False),'summary':s.get('report',{}).get('summary'),'checks':s.get('report',{}).get('checks',[])} for s in job['steps']]}

 def local_operation_finished(self,job):
  if job.get('status') in ['QUEUED','RUNNING','CANCELLING']:return
  if any(e.get('status')=='waiting' for e in self.saved.get('quota_failover_events',{}).values()):self._spawn(self._drain_wakes)
  key='local:'+job['id']
  with self.lock:
   watch=self.saved['watches'].get(key)
   if self.closed or not watch or watch['status']!='waiting':return
   watch.update(status='ready',job_status=job['status'],summary_path=str(self.root/'data/local-ops/jobs'/job['id']/'SUMMARY.json'),detail=job.get('error') or 'Local pipeline terminal; structural evidence only. Creative/human review remains pending.')
   self._record('local','Local execution finished: '+job.get('title',''),watch['detail'],job['status'],job_id=job['id']);self._persist()
  self._spawn(self._drain_wakes)

 def watch_local(self,data):
  job=self.runtime.local_ops.job(data['job_id']);key='local:'+job['id']
  with self.lock:
   if self.closed or not self.saved.get('continuation_authorized'):raise ValueError('Continuation was explicitly stopped')
   if key not in self.saved['watches']:self.saved['watches'][key]={'status':'waiting','kind':'local','job_id':job['id']};self._persist()
   if self.saved['watches'][key]['status']!='waiting':return copy.deepcopy(self.saved['watches'][key])
   if key not in self.native_watch_stops:
    stop=threading.Event();self.native_watch_stops[key]=stop
    threading.Thread(target=self._watch_local_loop,args=(key,stop),daemon=True).start()
  self.local_operation_finished(job)
  return copy.deepcopy(self.saved['watches'][key])

 def _watch_local_loop(self,key,stop):
  while not stop.is_set():
   with self.lock:watch=copy.deepcopy(self.saved['watches'].get(key))
   if not watch or watch['status']!='waiting':break
   try:self.local_operation_finished(self.runtime.local_ops.job(watch['job_id']))
   except (OSError,ValueError,KeyError):pass
   stop.wait(.5)
  with self.lock:
   if self.native_watch_stops.get(key) is stop:self.native_watch_stops.pop(key,None)

 def approval(self,key,decision):
  if decision not in ['accept','decline']:raise ValueError('Invalid decision')
  with self.lock:
   if key not in self.pending_requests:raise ValueError('Approval expired or already answered')
   rid=self.pending_requests.pop(key);self.rpc.respond(rid,{'decision':decision});self.saved['approvals']=[a for a in self.saved['approvals'] if a['id']!=key];self.saved['leader']['status']='awaiting_approval' if self.pending_requests else 'working';self._record('approval','Human '+decision);self._persist()
  return self.snapshot()

 def execution_policy(self):
  try:policy=load(self.path.with_name('EXECUTION_POLICY.json'))
  except (OSError,ValueError):policy={}
  unattended=policy.get('local_execution')=='unattended' and policy.get('authorized_by')=='human'
  return {'local_execution':'unattended' if unattended else 'ask','authorization_date':policy.get('authorization_date') if unattended else None,'detail':'Local execution is pre-authorized. No repeated Allow prompts.' if unattended else 'Local execution may ask for approval.'}

 def stop(self):
  with self.lock:
   self.saved['backup_suppressed']=True;self.backup_cancel.set();self.saved['continuation_authorized']=False
   engine=getattr(self.runtime,'local_ops',None)
   if engine:
    for job in engine.snapshot().get('active',[]):
     try:engine.cancel(job['id'])
     except (OSError,ValueError,KeyError):pass
    for watch in self.saved['watches'].values():
     if watch.get('kind')=='local':
      try:engine.cancel(watch['job_id'])
      except (OSError,ValueError,KeyError):pass
   for job in self.runtime.jobs():
    if job['status'] in self.runtime.active_states:
     try:self.runtime.cancel(job['id'])
     except (OSError,ValueError,KeyError):pass
   leader=self.saved['leader'];self.saved['watches']={};self.saved['continuation_authorized']=False
   try:
    plan=load(self.root/'data/production/CURRENT.json')
    self.saved['production_pause']={'project_id':plan['project_id'],'revision':plan['revision'],'at':stamp(),'reason':'Human paused execution. Preserve current work; a new explicit direction is required before continuing.'}
   except (OSError,ValueError,KeyError):pass
   self._cancel_reset_timers();self.saved['reset_wakes']={}
   self._cancel_native_watches();self._persist()
   if leader['status'] not in self.active and leader['status'] != 'error':return self.snapshot()
   if leader.get('provider') in ('antigravity','claude'):
    alive = any(x.is_alive() for x in self._bg_threads)
    if not alive:
     leader['status']='idle'
     leader['error']=None
    else:
     leader['status']='cancelling'
    self._persist();return self.snapshot()
   leader['status']='cancelling';thread_id=leader.get('thread_id');turn_id=leader.get('turn_id');self._persist()
  if not turn_id and thread_id and self.connected:
   try:
    result=self.rpc.call('thread/read',{'threadId':thread_id,'includeTurns':True})
    turns=result.get('thread',{}).get('turns')
    if turns is None:raise ValueError('Runtime did not report turn state')
    active_turn=next((t for t in reversed(turns) if t.get('status') in ['inProgress','running']),None)
    if active_turn:turn_id=active_turn['id']
    else:
     with self.lock:self.saved['leader'].update(status='idle',turn_id=None,error=None);self._persist()
   except Exception as e:
    with self.lock:self.saved['leader'].update(status='uncertain',error='Could not confirm execution state: '+str(e)[:500]);self._persist()
  if turn_id:self.rpc.call('turn/interrupt',{'threadId':thread_id,'turnId':turn_id})
  return self.snapshot()

 def _cancel_reset_timers(self):
  for t in list(self.reset_timers.values()):t.cancel()
  self.reset_timers.clear()

 def _cancel_native_watches(self):
  for stop in self.native_watch_stops.values():stop.set()
  self.native_watch_stops.clear()

 def restore_observations(self):
  """Reattach persisted local observers; only a real completion may wake a turn."""
  self.reconcile_native_timeout()
  self._rearm_reset_wakes()
  recovered_cap=False
  with self.lock:
   if self.closed or not self.saved.get('continuation_authorized'):return
   leader=self.saved['leader']
   if leader.get('provider')=='claude' and leader.get('status')=='error' and 'maximum number of turns' in str(leader.get('error','')).lower():
    # Upgrade recovery for the old cap-error state: only a persisted, confirmed
    # stopped result may rejoin its existing event chain. Never infer cancellation.
    try:
     folder=Path(self.saved.get('director_route',{}).get('run','')).resolve()
     allowed=(self.root/'data/command/director-runs').resolve()
     result=load(folder/'RESULT.json') if folder.is_relative_to(allowed) else {}
     if result.get('status')=='FAILED' and result.get('process_stopped') is True and result.get('idle_inference') is False:
      leader.update(status='idle',error=None)
      recovered_cap=True
      self._record('director','Reconciled stopped Claude step limit','Restoring only existing completion watches; no command replay.','completed');self._persist()
    except (OSError,ValueError,TypeError):pass
   if leader['status'] not in ['idle','completed']:return
   pending=copy.deepcopy(self.saved['watches'])
  for key,watch in pending.items():
   if watch.get('status')=='delivered' and watch.get('job_status')!='NEEDS_ATTENTION':continue
   if watch.get('kind')=='native':
    # Read only the exact result. Never dispatch the command saved in a watch.
    stop=threading.Event()
    with self.lock:
     if self.closed or key in self.native_watch_stops:continue
     self.native_watch_stops[key]=stop
    threading.Thread(target=self._watch_native_loop,args=(key,stop),daemon=True).start()
   elif watch.get('kind')=='local' and watch.get('status')=='waiting':
    try:self.watch_local({'job_id':watch['job_id']})
    except (OSError,ValueError,KeyError):pass
   elif watch.get('status')=='waiting':
    try:self.worker_changed(self.runtime.job(key))
    except (OSError,ValueError,KeyError):pass
  self._drain_wakes()
  if recovered_cap and not pending:self.production_turn_finished('completed')

 def _native_json(self,name):
  path=self.native_bridge/name
  if path.stat().st_size>1024*1024:raise ValueError('Native bridge record is unexpectedly large')
  value=load(path)
  if not isinstance(value,dict):raise ValueError('Native bridge record must be an object')
  return value

 def watch_native(self,args):
  command_id=args.get('command_id');seconds=args.get('timeout_seconds',900)
  if not isinstance(command_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',command_id):raise ValueError('Invalid native command ID')
  if type(seconds) is not int or not 5<=seconds<=3600:raise ValueError('Native watch timeout must be 5–3600 seconds')
  command=self._native_json('ae_command.json')
  if command.get('id')!=command_id or command.get('command')!='runScriptFile':raise ValueError('Only the exact current runScriptFile command may be watched')
  if command.get('servicedBy') not in [None,'TonyFX']:raise ValueError('Native command is owned by another bridge')
  script=Path((command.get('args') or {}).get('scriptPath','')).resolve();data=(self.root/'data').resolve()
  if not script.is_relative_to(data) or script.suffix.lower()!='.jsx' or not script.is_file():raise ValueError('Native command script must be an existing JSX inside studio/data')
  key='native:'+command_id
  with self.lock:
   if self.closed:raise ValueError('Studio is shutting down')
   if key in self.saved['watches']:return copy.deepcopy(self.saved['watches'][key])
   if not self.saved.get('continuation_authorized'):raise ValueError('Work was explicitly stopped; a new human direction is required')
   if any(k.startswith('native:') and w['status']=='waiting' for k,w in self.saved['watches'].items()):raise ValueError('A native command is already watched; keep the editor serialized')
   watch={'status':'waiting','kind':'native','command_id':command_id,'script':str(script),'deadline':time.time()+seconds}
   self.saved['watches'][key]=watch;stop=threading.Event();self.native_watch_stops[key]=stop
   self._record('native','Watching TonyFX completion',command_id+' · no inference while waiting','waiting',job_id=key);self._persist()
   threading.Thread(target=self._watch_native_loop,args=(key,stop),daemon=True).start()
   return copy.deepcopy(watch)

 def _watch_native_loop(self,key,stop):
  while not stop.is_set():
   if self._check_native_watch(key):
    with self.lock:
     watch=self.saved['watches'].get(key)
     late=watch and watch.get('job_status')=='NEEDS_ATTENTION' and self.saved.get('continuation_authorized')
    if not late:break
    self._check_late_native_result(key)
    stop.wait(5);continue
   stop.wait(1)
  with self.lock:
   if self.native_watch_stops.get(key) is stop:self.native_watch_stops.pop(key,None)

 def _check_late_native_result(self,key):
  with self.lock:
   watch=self.saved['watches'].get(key)
   if self.closed or not watch or watch.get('job_status')!='NEEDS_ATTENTION' or not self.saved.get('continuation_authorized'):return False
   command_id=watch['command_id']
  try:result=self._native_json('ae_mcp_result.json')
  except (OSError,ValueError):return False
  if result.get('_commandId')!=command_id or result.get('_servicedBy')!='TonyFX' or type(result.get('ok')) is not bool:return False
  with self.lock:
   watch=self.saved['watches'].get(key)
   if not watch or watch.get('job_status')!='NEEDS_ATTENTION':return False
   watch.update(status='ready',job_status='COMPLETED' if result['ok'] else 'FAILED',detail=str(result.get('error') or 'Matching late TonyFX result; inspect own report.'),result_path=str(self.native_bridge/'ae_mcp_result.json'))
   self._record('native','Late TonyFX completion',watch['detail'],watch['job_status'],job_id=key);self._persist()
  self._spawn(self._drain_wakes)
  return True

 def resume_native_observation(self,data):
  # Explicit authenticated continuation after a guarded application upgrade.
  # watch_native verifies the exact existing request/owner/script; never writes AE.
  with self.lock:
   if self.saved['leader']['status'] in self.active:raise ValueError('A director is already active')
   self.saved['continuation_authorized']=True;self.saved['backup_suppressed']=False
  if data.get('job_id'):
   job=self.runtime.job(data['job_id'])
   with self.lock:
    self.saved['watches'][job['id']]={'status':'waiting'};self._persist()
   self.worker_changed(job)
   return self.saved['watches'][job['id']]
  return self.watch_native(data)

 def _check_native_watch(self,key):
  # File observation only: never sends AE commands, modifies locks or invokes a model.
  with self.lock:
   watch=self.saved['watches'].get(key)
   if self.closed or not watch or watch['status']!='waiting':return True
   command_id=watch['command_id'];deadline=watch['deadline']
  outcome=None
  try:
   result=self._native_json('ae_mcp_result.json')
   if result.get('_commandId')==command_id and result.get('_servicedBy')=='TonyFX' and type(result.get('ok')) is bool:
    outcome={'job_status':'COMPLETED' if result['ok'] else 'FAILED','result_path':str(self.native_bridge/'ae_mcp_result.json'),'detail':str(result.get('error') or 'Matching TonyFX transport result; inspect script report and live state.')[:1600]}
  except (OSError,ValueError):pass  # Partial/atomic writes and unrelated old results are not completion.
  if outcome is None and time.time()>=deadline:
   outcome={'job_status':'NEEDS_ATTENTION','detail':'Native completion is still unverified at the watch deadline. Reconcile current command/result, script report and AE state. Do not resend or delete locks.'}
  if outcome is None:return False
  with self.lock:
   watch=self.saved['watches'].get(key)
   if self.closed or not watch or watch['status']!='waiting':return True
   watch.update(status='ready',**outcome);self._record('native','TonyFX completion' if outcome['job_status']!='NEEDS_ATTENTION' else 'TonyFX needs attention',outcome['detail'],outcome['job_status'],job_id=key);self._persist()
  self._spawn(self._drain_wakes)
  return True

 def worker_changed(self,job):
  if job.get('agent_id')=='lumen-editor' and job.get('status') in ('QUEUED','RUNNING','WAITING_LOCAL','UNKNOWN','PAUSED'):return  # Owned trial has not safely handed the editor back.
  if job.get('status') not in self.runtime.active_states and any(e.get('status')=='waiting' for e in self.saved.get('quota_failover_events',{}).values()):self._spawn(self._drain_wakes)
  with self.lock:
   watch=self.saved['watches'].get(job['id'])
   # An explicitly dispatched member of THIS director's team may not silently
   # disappear if a provider forgot its watch registration. Historical or paused
   # work never gains continuation merely by being present in the job store.
   if not watch and job.get('director_direction') and job['director_direction']==self.saved.get('production_direction') and self.saved.get('continuation_authorized') and job['status'] not in self.runtime.active_states:
    watch={'status':'waiting','kind':'team','detail':'Team member terminal; inspect shared failure/partial-result evidence before a new scoped attempt.'}
    self.saved['watches'][job['id']]=watch
   if not watch or job['status'] in self.runtime.active_states or watch['status']!='waiting':return
   watch.update(status='ready',job_status=job['status'],task_id=job.get('task_id'),detail=str(job.get('error') or '')[:600],result_path=job.get('result_path'));self._record('worker','Worker finished: '+job.get('title',''),job.get('error') or job['status'],job['status'],job_id=job['id'],task_id=job.get('task_id'),station=job.get('station'));self._persist()
  self._spawn(self._drain_wakes)

 def watch_job(self,data):
  job=self.runtime.job(data['job_id'])
  with self.lock:
   if not self.saved.get('continuation_authorized'):raise ValueError('Production continuation is not authorized')
   watch={'status':'waiting'}
   if self.saved['leader']['status'] not in self.active:
    from production import ProductionBoard
    plan=ProductionBoard(self.root).snapshot()['plan'] or {}
    direction=self.saved.get('production_direction')
    if (self.saved['leader']['status'] not in ('idle','completed') or self.saved.get('production_pause')
        or not direction or data.get('expected_direction_id')!=direction or plan.get('direction_id')!=direction
        or not job.get('project_id') or job['project_id']!=plan.get('project_id')
        or not job.get('project_revision') or job['project_revision']!=plan.get('revision')
        or job.get('context_mode')!='fresh_review' or not job.get('provider_not_run_recovery')
        or job.get('director_direction') not in (None,direction) or job.get('idle_inference')=='unknown'):
     raise ValueError('An authorized working director must register the job, or supply the exact current direction for its recovered review')
    watch.update(kind='team',direction_id=direction)
   if job['id'] not in self.saved['watches']:self.saved['watches'][job['id']]=watch;self._persist()
   # Fetch again after persisting so a completion concurrent with registration is observed.
   job=self.runtime.job(job['id'])
  self.worker_changed(job)
  return self.saved['watches'][job['id']]

 FAILURE_WAKE=('FAILED','TIMED_OUT','UNKNOWN','NEEDS_ATTENTION')
 MAX_FAILURE_WAKES=3
 LOOP_CEILING_WAKES=6  # escalated changed-approach wakes stop here (usage-loop guard)

 def _failure_wake_filter(self,ready):
  """Idempotent, capped failure wakes (caller holds self.lock). Returns the watches to deliver, failures as compact packets.

  Key is `provider:event_id:status`; a duplicate delivers nothing. MAX_FAILURE_WAKES ordinary wakes per task; later
  failures still wake the director but tell it to stop redispatching that task and create a NEW task with a changed
  approach or worker (Tony 8 Nov 2026: never stall waiting for a human). At LOOP_CEILING_WAKES one attention event
  records the stopped loop and no further wake for that task. Nothing here replays a command."""
  done=self.saved.setdefault('failure_wakes',{});counts=self.saved.setdefault('failure_wake_counts',{});out=[]
  for k,w in ready:
   if w.get('job_status') not in self.FAILURE_WAKE:out.append((k,w));continue
   ekey=str(w.get('kind') or 'worker')+':'+k+':'+w['job_status'];task=str(w.get('task_id') or k)
   if ekey in done:w['status']='delivered';continue
   if counts.get(task,0)>=self.LOOP_CEILING_WAKES:
    w['status']='delivered';done[ekey]={'at':stamp(),'task':task,'capped':True}
    try:
     from attention import AttentionStore
     AttentionStore(self.root).publish('failure-wake-cap:'+task,'Failure loop stopped for one task','Task '+task+' failed '+str(self.LOOP_CEILING_WAKES)+' times after director wakes; that task gets no further wake. The director was told to replace it with a new task. Latest: '+str(w.get('detail') or w['job_status'])[:600])
    except Exception:pass
    continue
   if counts.get(task,0)>=self.MAX_FAILURE_WAKES:
    w['detail']=('CHANGE APPROACH: task '+task+' has failed '+str(counts.get(task,0)+1)+' times. Do not dispatch it again unchanged. Diagnose the cause from its job log and outputs, then create a NEW task with a changed brief, limits or available capable worker from staffing and watch it. Latest: '+str(w.get('detail') or ''))[:900]
   counts[task]=counts.get(task,0)+1;done[ekey]={'at':stamp(),'task':task}
   out.append((k,{'kind':w.get('kind'),'job_status':w['job_status'],'task_id':w.get('task_id'),'detail':str(w.get('detail') or '')[:600],'result_path':w.get('result_path'),'status':'ready'}|{'_watch':w}))
  # The compact packet replaces the full watch in the message; mark the real watch delivered by the caller.
  final=[]
  for k,w in out:
   if '_watch' in w:
    real=w.pop('_watch');real['status']='ready';final.append((k,real))
   else:final.append((k,w))
  return final

 def register_reset_wake(self,provider,reset_at):
  """One persisted, no-inference wake at a provider-reported reset time. Unknown reset: reported, not retried."""
  if not isinstance(reset_at,(int,float)) or isinstance(reset_at,bool):return False
  key=provider+':'+str(int(reset_at))
  with self.lock:
   if self.closed or not self.saved.get('continuation_authorized'):return False
   wakes=self.saved.setdefault('reset_wakes',{})
   direction=self.saved.get('production_direction')
   generation=self.selector.state.get('human_selection_generation',0)
   for prior in wakes.values():
    if prior.get('provider')!=provider or prior.get('direction_id')!=direction or prior.get('selection_generation',0)!=generation:continue
    if prior['status']=='waiting':return False
    if prior['status'] in ('fired','blocked'):
     if prior['status']=='fired':
      prior.update(status='blocked',detail='The provider refused again after the single reset wake for this direction. Select another available director or send a new direction after allowance returns.')
      self._record('director','Allowance reset wake blocked',prior['detail'],'failed');self._persist()
     return False
   wakes[key]={'status':'waiting','provider':provider,'reset_at':reset_at,'registered_at':stamp(),
               'direction_id':direction,'selection_generation':generation};self._persist()
  self._arm_reset_timer(key,reset_at)
  return True

 def _arm_reset_timer(self,key,reset_at):
  with self.lock:
   old=self.reset_timers.pop(key,None)
   if old:old.cancel()
   t=threading.Timer(max(0,reset_at-time.time()),self._fire_reset_wake,(key,));t.daemon=True;self.reset_timers[key]=t
  t.start()

 def _fire_reset_wake(self,key):
  with self.lock:
   self.reset_timers.pop(key,None)
   rw=self.saved.get('reset_wakes',{}).get(key)
   if self.closed or not rw or rw['status']!='waiting' or not self.saved.get('continuation_authorized'):return False
   if (rw.get('direction_id')!=self.saved.get('production_direction') or
       rw.get('selection_generation',0)!=self.selector.state.get('human_selection_generation',0)):
    rw.update(status='cancelled',cancel_reason='Direction or director selection changed.');self._persist();return False
   rw.update(status='fired',fired_at=stamp())
   if rw['provider']=='claude':self.saved.pop('native_claude_exhausted',None)
   else:self.saved.pop('codex_quota_exhausted',None)
   self.saved['watches']['reset:'+key]={'status':'ready','kind':'reset','job_status':'RESET_REACHED','detail':'The provider-reported allowance reset time was reached. No inference ran while waiting. Continue only the already authorized scope; if the limit persists the app records it as blocked.'}
   self._record('director','Allowance reset reached',key,'completed');self._persist()
  self._spawn(self._drain_wakes)
  return True

 def _rearm_reset_wakes(self):
  with self.lock:
   pending=[(k,w['reset_at']) for k,w in self.saved.get('reset_wakes',{}).items() if w.get('status')=='waiting' and k not in self.reset_timers]
  for k,r in pending:self._arm_reset_timer(k,r)

 def _drain_wakes(self):
  # Every completion path uses the same editor -> service lock order as send
  # and selector transitions. Concurrent quota/native wakes must not invert it.
  from lumen_editor import EDITOR_LOCK
  with EDITOR_LOCK:self._drain_wakes_in_editor_order()

 def _drain_wakes_in_editor_order(self):
  from usage_routing import reconcile as reconcile_quota_failover
  if reconcile_quota_failover(self):return
  with self.lock:
   if self.closed or self.saved['leader']['status'] in self.active or not self.saved.get('continuation_authorized'):return
   if time.time()<self.saved['leader'].get('retry_after',0):return
   for watch in self.saved['watches'].values():
    if (watch['status'] in ('waiting','ready') and watch.get('kind')=='team' and watch.get('direction_id')
        and watch['direction_id']!=self.saved.get('production_direction')):
     watch['status']='cancelled';self._persist()
   ready=[(j,w) for j,w in self.saved['watches'].items() if w['status']=='ready']
   if not ready:return
   urgent=[(j,w) for j,w in ready if w.get('job_status') in self.FAILURE_WAKE]
   if urgent:
    # A terminal failure is urgent: it wakes even while siblings run or a quota event is blocked.
    ready=self._failure_wake_filter(ready)
    if not ready:self._persist();return
   else:
    # A pending (waiting) quota succession holds ordinary wakes; a blocked one never suppresses any wake.
    if any(e.get('status')=='waiting' and e.get('direction_id')==self.saved.get('production_direction') for e in self.saved.get('quota_failover_events',{}).values()):return
    # One completion turn per registered batch, not one turn per parallel worker.
    if any(w['status']=='waiting' for w in self.saved['watches'].values()):return
   from execution_control import native_crash_hold
   if native_crash_hold(self,ready):return
   self.saved['ledger_recovery_turn']=any(w.get('kind')=='production' or w.get('job_status') in ('FAILED','BLOCKED','INCOMPLETE_REQUIREMENTS') for _,w in ready)
   for _,w in ready:w['status']='delivered'
   self.saved['completion_wakes']=self.saved.get('completion_wakes',0)+1;self._persist()
   self.send('Registered completion (real local event): '+json.dumps(ready)+'. Inspect matching job/task or native command results, validate evidence, then continue only the already authorized scope. A native transport result is not script or artistic approval. Never replay a failed or unresolved command. For confirmed native failures, inspect partial state, fix the identified cause in a NEW guarded script, validate and continue the same human task. Routine debugging does not require the human to send continue.',internal=True)

 def production_turn_finished(self,status):
  try:
   from production_guard import finished
   finished(self,status)
  except Exception as e:
   from attention import AttentionStore
   AttentionStore(self.root).publish('supervisor-error:'+str(e),'Production supervisor needs attention',str(e))

 def shutdown(self):
  with self.lock:self.closed=True;self.backup_cancel.set();self._cancel_native_watches();self._cancel_reset_timers();self._persist(force=True);threads=list(getattr(self,'_bg_threads',[]))
  self.rpc.close()
  for t in threads:
   if t is not threading.current_thread():t.join(timeout=1.5)
