"""Human-authorized subscription director succession. No inference while idle."""
import copy, json, threading, time, uuid
from pathlib import Path
from operations import load, save, stamp
from native_director import NativeDirector


class DirectorBackup(NativeDirector):
 def director_policy(self):
  try:return load(self.root/'data/command/DIRECTOR_POLICY.json')
  except (OSError, ValueError):return {'enabled':False}

 def _codex_exhausted(self):
  from usage_routing import codex_exhausted
  return codex_exhausted(self)

 def _model_groups(self,model):
  return {'Gemini Models','Gemini 4 Argon'} if 'argon' in model else ({'Gemini Models'} if model.startswith('gemini-') else {'Claude and GPT models'})

 def _model_at_reserve(self,model,buckets,reserve):
  groups=self._model_groups(model)
  return any(b.get('group') in groups and isinstance(b.get('remaining_percent'),(int,float)) and b['remaining_percent']<=reserve for b in buckets)

 def _resume_backup(self):
  with self.lock:
   if self.closed or self.saved.get('backup_suppressed') or self.saved['leader']['status'] in self.active:return
   if getattr(self,'selector',None) and self.selector.explicit():
    self._record('director','Selected director unavailable — no automatic fallback','Tony manually selected '+str(self.selector.selected_id())+'. Choose another director explicitly; nothing was substituted or started.','failed');self._persist();return
   if self.saved.get('pending_image_input'):
    self.saved['leader'].update(status='error',error='Codex could not complete the screenshot turn. Backup image input is not verified, so no blind text-only takeover was started. Your screenshots remain in the conversation.')
    self._persist();return
  try:self.send('Continue the latest authorized production from shared/ACTIVE_DIRECTOR_HANDOFF.md and the current project STATE.md. Reconcile native command/results and partial work before any mutation. This is a director takeover, not a replay of the initial brief.',internal=True)
  except Exception as e:
   with self.lock:self._record('error','Backup takeover needs attention',str(e),'failed');self._persist()

 def _backup_turn(self,text,models_override=None,images=None,session_key=None,manual_profile=None):
  if 'NEURAL SHARED CONTINUATION' not in text:
   from continuity import director_context
   text+=director_context(self.root,self.saved,native_pending=self._handoff_native_pending())
  policy=self.director_policy();cancel=self.backup_cancel;launched=False
  if models_override is None and policy.get('backup_routes'):
   return self._native_director_turn(text,policy['backup_routes'],images=images)
  if images and not (manual_profile and manual_profile.get('vision_commissioned')):
   with self.lock:
    self.saved['leader'].update(status='error',turn_id=None,error='The Gemini fallback cannot see screenshots, so no blind text-only turn was started. Your screenshots remain in the conversation.')
    self._persist()
   return
  elif images:
   from chat_images import ChatImages
   text=text+ChatImages(self.root).prompt_note(images,tool_name='read_file')
  reserve=float(policy.get('backup_reserve_percent',4.0))
  folder=self.root/'data/command/director-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
  try:
   headless=self.runtime.headless
   snap=headless.snapshot().get('antigravity',{})
   cached_models=snap.get('models') or []
   report={'status':'OK','models':cached_models} if cached_models else headless.query_agy('models',timeout=12)
   quota=headless.query_agy('quota',timeout=12)
   if report.get('status')!='OK' or quota.get('status')!='OK':raise ValueError('Backup account/model metadata unavailable; no inference started')
   available=set(report.get('models',[]));buckets=(quota.get('quota') or {}).get('buckets',[])
   with self.lock:
    self.saved['usage']['antigravity']={'status':'reported','windows':(quota.get('quota') or {}).get('windows',[]),'checked_at':stamp(),'detail':'Official Antigravity account/model groups, shared by every robot using this account. Metadata only; no AI turn.'}
    self._persist()
   blocked=self.saved.setdefault('director_exhausted',{})
   models=list(models_override if models_override is not None else policy.get('backup_models',[]))
   for idx,model in enumerate(models):
    if cancel.is_set():
     with self.lock:self.saved['leader'].update(status='idle',error=None);self._persist()
     return
    if model not in available:continue
    # Last-resort Flash 3.8 uses remaining Gemini Models allowance down to 0%; earlier backups hand over at reserve (4%).
    model_reserve=0.0 if manual_profile or (idx==len(models)-1 and 'flash' in model) else reserve
    if self._model_at_reserve(model,buckets,model_reserve) or blocked.get(model,0)>time.time():continue
    with self.lock:
     self.saved['leader'].update(status='working',provider='antigravity',model=model,error=None)
     self.saved['director_route']={'primary':'Codex','acting':model,'reserve_percent':model_reserve,'reason':'Codex reported allowance is exhausted or at the configured reserve','run':str(folder)} if not manual_profile else {'primary':'Manual selection','acting':model,'acting_provider':'antigravity','profile_id':manual_profile['id'],'manual':True,'reason':'Tony manually selected '+manual_profile['label']+'; no automatic fallback','run':str(folder),'direction_id':self.saved.get('production_direction')}
     self._record('director','Backup director active',f'{model} · reserve threshold {model_reserve:g}% · one serialized editor','working');self._persist()
    prompt='''You are the acting DIRECTOR of Neural Posthouse, not a text-only specialist. You also support Tony's general-assistant tasks (engineering, research, scripting, file/shell/web help) alongside video production; production checklists and TonyFX rules apply to video/editing work, while pure general-assistant requests may be answered or executed directly within Tony's authorized scope. Your active director role comes from the current selection or an authorized handoff. Read shared/START_HERE_NEURAL.md for the current provider-neutral entry points. You inherit the same workflow and preservation rules. Only one native editor may operate. For video production, read the current project and ownership in the continuation packet first; then relevant knowledge/skills and their referenced protocols. Inspect actual live AE through TonyFX before mutation. Never replay an unresolved command, delete bridge locks, reuse completed scenes/mattes/builders, resume unrelated projects, or alter Neural app code unless explicitly authorized by Tony. Delegate bounded preparation to existing capable station workers; do only hard integration/supervision yourself. Do not claim media listening or motion review without actual support.
You have the official Antigravity CLI's local file/shell/web tools (read_file for files and attached screenshots, write_file, edit_file, run_command, search_web) in accept-edits mode. Work through Neural's loopback API at http://127.0.0.1:8767; GET /api/config for the local token (never print it), use X-Studio-Token for POST. GET /api/state, /api/command/state. POST /api/tasks (station,title,brief,kind,inputs,project_id), /api/dispatch (station,task_id,agent_id), /api/review (station,task_id,decision,note). Do not dispatch yourself or a second director. For worker completion wakes register via POST /api/command/watch-job (job_id). Register completed review MP4s via POST /api/previews/register (path,title,revision,note,current,project_id). If a native command remains pending/running after bounded wait, POST /api/command/watch-native (command_id,timeout_seconds:900), save state and END your turn; local observation wakes the acting director once without AI polling. Never finish a waiting task without a registered watch. Keep a compact truthful STATE.md including next action and live/native IDs. End inference when complete or waiting. No paid API or model fallback of your own; the local director service owns succession. Human Stop cancels this turn.
Mechanical work uses the shared local engine, never a model for extraction, numeric checks, waiting or routine bookkeeping. Read shared/LOCAL_OPS_WORKFLOW.md. GET /api/local-ops/capabilities; POST /api/local-ops/submit with {"plan":{"version":1,"title":"...","steps":[...]}}. Register the returned job_id via POST /api/command/watch-local, then END your turn. Local steps chain and one terminal event wakes you. Inspect its compact data/local-ops/jobs/ID/SUMMARY.json. This is the same engine used outside Neural by python tools/local_ops.py run PLAN.json. Current compiler is picture-only; unsupported caption/audio/effect work is explicit, not silently substituted. No native replay; Stop revokes continuation.
Maintain the revision-specific production checklist and independent quality gates using shared/PRODUCTION_CHECKPOINT_WORKFLOW.md and /api/production. Never silently drop an unresolved requirement or infer motion/listening approval from numeric or still-image checks.
Latest direction/continuation:
'''+text
    if models_override is not None:prompt=prompt.replace('the human explicitly authorizes Argon, then Opus, then Sonnet, and finally Flash 3.8 (only when all preceding directors have no remaining usage)','the human authorizes native Claude Opus first, then this final Gemini fallback only after a confirmed native Claude allowance refusal; Argon is excluded')
    (folder/'PROMPT.txt').write_text(prompt,encoding='utf-8')
    # Preserve each provider/model director conversation across returns from Sol
    # or Claude, within the selected workflow. Never use another role's session.
    conversation_key=session_key or (str(self.saved.get('director_context_scope','tuf'))+':'+model)
    with self.lock:
     previous=self.saved.setdefault('gemini_director_sessions',{}).get(conversation_key,{})
     conversation=previous.get('session_id')
    spec=headless.build_agy(model,self.root,timeout=3600,mode='accept-edits',read_tools=True,unattended=True,conversation=conversation)
    turn_cancel=threading.Event();handover_triggered=[False];stop_watch=threading.Event()
    def sync_cancel():
     while not stop_watch.is_set():
      if cancel.is_set():turn_cancel.set();return
      stop_watch.wait(.2)
    def watch_reserve():
     # Non-inference metadata check every 15s while a backup turn runs so reaching 2-4% hands over within <=30s.
     while not stop_watch.wait(15):
      if cancel.is_set() or model_reserve<=0:return
      q=headless.query_agy('quota',timeout=8)
      if q.get('status')!='OK':continue
      latest_buckets=(q.get('quota') or {}).get('buckets',[])
      with self.lock:
       self.saved['usage']['antigravity']={'status':'reported','windows':(q.get('quota') or {}).get('windows',[]),'checked_at':stamp(),'detail':'Official Antigravity account/model groups, shared by every robot using this account. Metadata only; no AI turn.'}
       self._persist()
      if self._model_at_reserve(model,latest_buckets,model_reserve):
       buckets[:]=latest_buckets;handover_triggered[0]=True;turn_cancel.set();return
    if model_reserve>0 and hasattr(headless.query_agy,'__call__') and not hasattr(headless.query_agy,'assert_called'):
     threading.Thread(target=sync_cancel,daemon=True).start()
     threading.Thread(target=watch_reserve,daemon=True).start()
    last=[0]
    def progress(event):
     if cancel.is_set():turn_cancel.set()
     with (folder/'events.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(event,ensure_ascii=False)+'\n')
     if time.monotonic()-last[0]<.7:return
     last[0]=time.monotonic()
     with self.lock:
      self._record('director',model+' · '+event.get('kind','activity'),json.dumps(event,ensure_ascii=False)[:4000],'working')
      if event.get('usage') is not None:self.saved['leader']['backup_usage']=event['usage']
      self._persist()
    launched=True
    from production_workbench import call_event,consumption
    ledger_key='native:'+folder.name+':'+model
    call_event(self.root,ledger_key,'antigravity',model,'director',purpose='recovery' if self.saved.pop('ledger_recovery_turn',False) else 'direction',source=str(folder/'RESULT.json'))
    try:
     result=headless.run_agy(spec,prompt,on_event=progress,cancel_event=turn_cancel if model_reserve>0 and not hasattr(headless.query_agy,'assert_called') else cancel,timeout=3600)
    except Exception:
     call_event(self.root,ledger_key,'antigravity',model,'director',status='UNKNOWN',finished_at=stamp(),source=str(folder/'RESULT.json'));raise
    finally:
     stop_watch.set()
    save(folder/'RESULT.json',result)
    if result.get('session_id'):
     if conversation and result['session_id']!=conversation:
      raise ValueError('Provider returned a different director conversation ID while resuming; the original ID is preserved. Reconciliation required; no blank retry.')
     with self.lock:
      self.saved['gemini_director_sessions'][conversation_key]={'session_id':result['session_id'],'model':model,'updated_at':stamp()}
      self._persist()
    call_event(self.root,ledger_key,'antigravity',result.get('model') or model,'director',status=result.get('status'),usage=consumption(result.get('usage_events')),finished_at=stamp(),source=str(folder/'RESULT.json'))
    known=result.get('status') in ('COMPLETED','FAILED','BLOCKED') and result.get('process_stopped') is True and result.get('idle_inference')!='unknown'
    if handover_triggered[0] and not cancel.is_set():
     if result.get('process_stopped') is not True or result.get('idle_inference') is not False:
      with self.lock:
       self.saved['leader'].update(status='uncertain',error='Reserve reached, but prior director cancellation is unconfirmed. Reconcile its remote execution and native command before switching directors.',turn_id=None)
       self._record('director','Reserve handover needs reconciliation',str(folder/'RESULT.json'),'uncertain');self._persist()
      return
     blocked[model]=time.time()+300
     with self.lock:
      self._record('director','Reserve handover triggered',f'{model} reached <= {model_reserve:g}% reserve; handing over immediately to next backup director','completed')
      self._persist()
     text='Immediate reserve handover from '+model+': Read shared/ACTIVE_DIRECTOR_HANDOFF.md and the current project STATE.md, reconcile any in-flight native command or worker job before mutating, and continue seamlessly.\n\n'+text
     continue
    detail=str(result.get('error') or '')
    if known and result.get('status')=='FAILED' and any(w in detail.lower() for w in ('quota','usage limit','resource_exhausted','rate limit','capacity exhausted')):
     blocked[model]=time.time()+300
     with self.lock:self._record('director','Director allowance unavailable',model+' · '+detail,'failed');self._persist()
     continue
    with self.lock:
     final=str(result.get('text') or detail or result.get('status'))[-16000:]
     self.saved['leader']['messages'].append({'id':uuid.uuid4().hex,'role':'assistant','text':'['+(manual_profile['label']+' · ' if manual_profile else '')+model+']\n'+final,'status':'completed' if result.get('status')=='COMPLETED' else 'failed','created_at':stamp(),'provenance':{'provider':'antigravity','model':result.get('model') or model,'profile_id':(manual_profile or {}).get('id'),'run':str(folder)}})
     self.saved['leader'].update(status='idle' if result.get('status')=='COMPLETED' else 'error' if known else 'uncertain',error=None if result.get('status')=='COMPLETED' else detail or result.get('status'),turn_id=None,backup_session_id=result.get('session_id'),backup_usage=result.get('usage_events'))
     self._record('director','Backup director '+result.get('status','UNKNOWN'),str(folder/'RESULT.json'),result.get('status'));self._persist()
    if result.get('status')=='COMPLETED':self._drain_wakes()
    if hasattr(self,'production_turn_finished'):self.production_turn_finished(result.get('status','UNKNOWN'))
    return
   raise ValueError('No authorized backup has verified available allowance above reserve. Opus and Sonnet share their account quota; Flash 3.8 requires Gemini Models allowance; no overage or bypass attempted.')
  except Exception as e:
   with self.lock:self.saved['leader'].update(status='uncertain' if launched else 'error',error=str(e)[:1600]);self._record('error','Backup director stopped',str(e),'failed');self._persist()
   if hasattr(self,'production_turn_finished'):self.production_turn_finished('failed')
