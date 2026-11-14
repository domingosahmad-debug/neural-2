"""Native Claude subscription fallback, followed only by the configured final Gemini route."""
import json,time,uuid
from pathlib import Path
from operations import save,stamp

PROMPT='''You are the acting DIRECTOR in Neural Posthouse. Sol/Codex is primary; native Claude Opus is the human's backup, Gemini is last resort. Read shared/ACTIVE_DIRECTOR_HANDOFF.md, shared/LEADER_CONTEXT.md, the current compact owned-work checkpoint and latest STATE.md section (not its whole history), plus relevant bundled skills first. The latest human brief below overrides old paused-production entries for this project only. Preserve other projects and previous revisions.
You have official Claude Code file/shell/web tools (Read, Write, Edit, Glob, Grep, Bash, PowerShell, WebFetch, WebSearch). You also support Tony's general-assistant tasks (engineering, research, local scripting, file/shell/web help) alongside video production; production checklists and TonyFX rules apply to video/editing work, while non-video assistant tasks may execute directly within Tony's authorized scope. Use the Neural API at http://127.0.0.1:8767: GET /api/config for its local write token (never print it), X-Studio-Token and same Origin on POST. Station tasks: /api/tasks, /api/dispatch, /api/review; state: /api/state and /api/command/state. Read shared/TEAMWORK_PROTOCOL.md. GET /api/team/channel for real peer messages/help; POST /api/command/team-message while working with project_id, kind (finding/help/reply/decision), to (Director/team/station), text, optional reply_to/source. Diagnose failures publicly, assign a capable scoped consultation/replacement, and never invent peer replies. Read shared/LOCAL_OPS_WORKFLOW.md; submit mechanical pipelines to /api/local-ops/submit, register job_id at /api/command/watch-local and END inference while waiting. Specialist job completion: /api/command/watch-job. Exact native command completion: /api/command/watch-native. Use one final event wake, not model polling. Always save compact current STATE.md before waiting/finishing.
Only one TonyFX native editor. Inspect live project/comp identity through TonyFX before any write, preserve protected state and use matching exact command IDs/results. Never delete locks, replay unresolved commands, start MCP Bridge Auto, reuse old completed scenes/mattes/builders as new footage, or mutate a different project. A running native operation survives a model turn: register an exact watch and end your turn. Never finish a waiting edit without a watch. Correct confirmed failures with a NEW scoped guarded operation after inspecting partial state; UNKNOWN blocks replay and competing editors.
Delegate bounded semantic work to capable connected workers; local scripts handle arithmetic, frame extraction, audio processing, validation and waiting. This director may do difficult native integration and review; ordinary station Claude profiles have different tool permissions. Preserve editable audio/text/mattes; one voice/caption owner unless explicitly requested otherwise. Keep script PASS separate from pixels, actual listening/full-speed playback and human approval. Do not claim unsupported perception. No app-code edits, new billing, API keys, extra-usage/overage purchase, provider substitution or self-launched subagents. The service owns director succession. Human Stop cancels this owned process; do not spawn detached shell/model loops.
Read shared/PRODUCTION_CHECKPOINT_WORKFLOW.md. Maintain /api/production via /api/production/update or tools/production.py at real decision checkpoints, with revision-bound concrete remaining steps, evidence and independent technical/sequence/picture/motion/listening/human gates. Never call an untested gate verified or remove an unresolved human requirement. Only offer a justified remaining-time range; unknown is better than a fabricated deadline. Read compact shared/LEADER_CONTEXT.md first; historical handoff entries are not current orders.
Optional Lumen trial worker: GET /api/apprentice/editor; POST /api/apprentice/editor/start with source_project_id, brief, title and wake_director=true creates a NEW isolated trial with your completion watch, queued until your production hands off. It is not director succession. Never assign a duplicate live edit or bypass its exclusive editing lease. Read shared/LUMEN_EDITOR_ROLE.md before a trial handoff.
Latest human direction / continuation:
'''

RESUME_PROMPT='''You are continuing your Neural director session. Your earlier instructions and rules still apply. Things may have changed since your last turn: read the current compact owned-work checkpoint, latest STATE.md section, and projected /api/command/state fields before acting, and reconcile any native/local work that finished while you were away. Read shared/TEAMWORK_PROTOCOL.md; GET /api/team/channel for peer messages and help. POST /api/command/team-message (project_id, kind, to, text, optional reply_to/source) records your attributed Director messages while working. If a teammate fails, reply with a diagnosis/decision and assign a bounded capable consultation or NEW recovery task; never fake a peer answer, mark bad work done or replay UNKNOWN. Do not resume a paused edit from remembered messages.
Optional Lumen trial worker: GET /api/apprentice/editor; POST /api/apprentice/editor/start with source_project_id, brief, title and wake_director=true creates a NEW isolated trial with your completion watch, queued until your production hands off. It is not director succession. Never assign a duplicate live edit or bypass its exclusive editing lease. Read shared/LUMEN_EDITOR_ROLE.md before a trial handoff.
Latest human direction / continuation:
'''


WORKBENCH_RULE='Read shared/PRODUCTION_WORKBENCH_WORKFLOW.md. Use /api/workbench and POST /api/workbench/action {action,data} for the current shared blueprint, draft/approved treatment methods and evidence-backed recovery tickets. Freeze one shot/quote/style/music/ending contract before a new build; carry its hash through station handoffs. consult_recovery selects one capable peer and registers a completion watch. Resolve only after actual new result evidence. Reported per-task usage is not remaining account quota. No model evaluations are enabled.\n'
PROMPT=PROMPT.replace('Latest human direction / continuation:',WORKBENCH_RULE+'Latest human direction / continuation:')
RESUME_PROMPT=RESUME_PROMPT.replace('Latest human direction / continuation:',WORKBENCH_RULE+'Latest human direction / continuation:')

OVERSIGHT_PROMPT='''You are the oversight DIRECTOR in Neural. Read shared/OVERSIGHT_DIRECTOR_GUIDE.md and shared/CURRENT_WORKFLOW_20261107.md first, then only the files the task needs. The latest human brief below overrides old paused entries for this project only. Plan, assign exact bounded tasks with `python tools/neural_cli.py` (create-project, status, assign, dispatch, watch, local-ops, watch-local, accept, reject, production, channel, team-message; see the guide), register a watch and END the turn while work runs. You cannot write files or run other commands; executors apply work. Save checkpoints through assigned tasks, not directly. Never replay UNKNOWN native commands.
Latest human direction / continuation:
'''
OVERSIGHT_RESUME='''Oversight DIRECTOR session resumed. Rules are unchanged (shared/CURRENT_WORKFLOW_20261107.md). Use `python tools/neural_cli.py` only; watch and END the turn while work runs.
Latest human direction / continuation:
'''
TURN_BUDGET_RULE='Work in bounded milestones, not one uninterrupted whole-edit turn. Before expensive analysis/build, inspect /api/production: bind checkpoints to the CURRENT human direction and project via /api/production/update, preserving/archive-separating prior projects and their acceptance. A new task must not keep the old edit board. Reuse completed source analysis and saved design; do not repeat it merely after a continuation. Save current STATE and checkpoint after one native proof/build/diagnosis. Target less than ten minutes of director work per turn. Submit mechanical work to the local engine, register its exact completion watch, and END inference immediately while it runs. On a failed native property write inspect actual property bounds/types before a corrected NEW operation; ask a capable Sol read-only consultant for a specific hard bug when useful. Never keep the model alive to wait for a render.\n'
PROMPT=PROMPT.replace('Latest human direction / continuation:',TURN_BUDGET_RULE+'Latest human direction / continuation:')
RESUME_PROMPT=RESUME_PROMPT.replace('Latest human direction / continuation:',TURN_BUDGET_RULE+'Latest human direction / continuation:')


def confirmed_timeout(service):
 """A stopped local Claude process is not uncertain remote execution or native success."""
 if service.saved.get('leader',{}).get('provider') not in ('claude', 'antigravity'): return None
 try:
  folder=Path(service.saved.get('director_route',{}).get('run','')).resolve()
  allowed=(service.root/'data/command/director-runs').resolve()
  if not folder.is_relative_to(allowed):return None
  result=json.loads((folder/'RESULT.json').read_text(encoding='utf-8'))
  owner=result.get('direction_id') or service.saved.get('director_route',{}).get('direction_id')
  if owner and owner!=service.saved.get('production_direction'):return None
  if (result.get('status') in ('TIMED_OUT', 'FAILED') or 'stream idle timeout' in str(result.get('error',''))) and result.get('process_stopped') is True:
   return {'folder':str(folder),'result':result}
 except (OSError,ValueError,TypeError):pass
 return None

def _missing_session(result):
 text=str(result.get('error') or '')+' '+str(result.get('text') or '')
 return result.get('status')=='FAILED' and result.get('process_stopped') is True and any(s in text.lower() for s in ('no conversation found','session not found','no session found','could not find session'))


class NativeDirector:
 def _handoff_native_pending(self):
  bridge=getattr(self,'native_bridge',Path.home()/'Documents/ae-mcp-bridge')
  command=bridge/'ae_command.json'
  if not command.exists():return None
  try:
   c=json.loads(command.read_text(encoding='utf-8'))
   if str(c.get('status','')).lower() in ('pending','running','executing'):
    result=bridge/'ae_mcp_result.json'
    if result.is_file():
     r=json.loads(result.read_text(encoding='utf-8'))
     if c.get('id') and r.get('_commandId')==c['id'] and isinstance(r.get('ok'),bool):return None
    return str(c.get('id') or 'unknown-command')
  except (OSError,ValueError):return 'unreadable-native-command'
  return None

 def _native_vision_ready(self):
  """Native Claude can view screenshots with its Read tool; Gemini fallback cannot."""
  routes=self.director_policy().get('backup_routes') or []
  if not any(r.get('provider')=='claude' for r in routes):return False
  ex=self.saved.get('native_claude_exhausted')
  return not ex or bool(ex.get('reset_at') and ex['reset_at']<=time.time())

 def _image_note(self,images):
  if not images:return ''
  from chat_images import ChatImages
  return ChatImages(self.root).prompt_note(images)

 def _native_director_turn(self,text,routes,images=None):
  from claude_transport import connection,build_director,project_read_dirs
  cancel=self.backup_cancel;launched=False
  folder=self.root/'data/command/director-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
  try:
   if cancel.is_set():
    with self.lock:self.saved['leader'].update(status='idle',turn_id=None);self._persist()
    return
   if self._handoff_native_pending():
    self._finish_native_fallback(text,[],images=images);return
   native=next((r for r in routes if r.get('provider')=='claude'),None)
   final=[r['model'] for r in routes if r.get('provider')=='antigravity' and str(r.get('model','')).startswith('gemini-') and 'argon' not in r['model']]
   if not native:raise ValueError('No native Claude director is configured.')
   exhausted=self.saved.get('native_claude_exhausted')
   if exhausted:
    if exhausted.get('reset_at') and exhausted['reset_at']<=time.time():self.saved.pop('native_claude_exhausted',None)
    else:
     self._finish_native_fallback(text,final,images=images);return
   ready=connection()
   if not ready.get('authenticated'):raise ValueError(ready['auth'])
   model=native.get('model','opus');manual=bool(native.get('manual'))
   if model!='opus' and not (manual and model=='sonnet'):raise ValueError('This human-authorized director fallback must use native Claude Opus.')
   with self.lock:
    self.saved['leader'].update(status='working',provider='claude',model=model,error=None)
    self.saved['director_route']={'primary':'Codex / Sol','acting_provider':'claude','acting':model,'manual':manual,'profile_id':native.get('profile_id'),'run':str(folder),'direction_id':self.saved.get('production_direction'),'reason':'Human-selected temporary Claude director' if self.director_policy().get('temporary_acting_director') else 'Primary reserve reached; human-authorized native Claude backup','remaining_quota':'See dated provider quota; missing utilization is unknown'}
    self.saved['director_runtime']={'run':folder.name,'timeout_mode':'activity','inactivity_limit_seconds':1800,'started_at':stamp(),'last_progress_at':None}
    self._record('director','Native Claude '+model.capitalize()+' director active','Existing Claude subscription; exact resolved model and tools recorded by the CLI.','working');self._persist()
   session=self.saved['leader'].get('claude_session_id')
   bridge=getattr(self,'native_bridge',Path.home()/'Documents/ae-mcp-bridge')
   note=self._image_note(images)
   def launch(session):
    from continuity import director_context
    oversight=bool(self.director_policy().get('oversight_mode',True))
    prompt=((OVERSIGHT_RESUME if session else OVERSIGHT_PROMPT) if oversight else (RESUME_PROMPT if session else PROMPT))+text+note
    if 'NEURAL SHARED CONTINUATION' not in text:prompt+=director_context(self.root,self.saved,compact=bool(oversight and session),oversight=bool(oversight),native_pending=self._handoff_native_pending())
    (folder/'PROMPT.txt').write_text(prompt,encoding='utf-8')
    with self.lock:
     self._record('director','Claude director session','Continuing session '+session[:8] if session else 'New session (the previous one ended or this is the first Claude turn)','working');self._persist()
    from production_workbench import call_event,consumption
    key='native:'+folder.name+(':'+session if session else ':fresh')
    call_event(self.root,key,'claude',model,'director',purpose='recovery' if self.saved.pop('ledger_recovery_turn',False) else 'direction',source=str(folder/'RESULT.json'))
    try:outcome=self.runtime.headless.run_opencode(build_director(model,self.root,resume=session,extra_dirs=[bridge],oversight=oversight,project_dirs=project_read_dirs(self.root) if oversight else ()),prompt,on_event=progress,cancel_event=cancel,timeout=1800,_protocol='claude',timeout_mode='activity')
    except Exception:
     call_event(self.root,key,'claude',model,'director',status='UNKNOWN',finished_at=stamp(),source=str(folder/'RESULT.json'));raise
    call_event(self.root,key,'claude',outcome.get('model') or model,'director',status=outcome.get('status'),usage=consumption(outcome.get('usage_events')),finished_at=stamp(),source=str(folder/'RESULT.json'))
    outcome['direction_id']=self.saved['director_route'].get('direction_id')
    return outcome
   activity={'tools':False,'quota_exhausted':False}
   def progress(event):
    if event.get('kind')=='tool':activity['tools']=True
    if event.get('kind')=='quota':
     activity['quota_exhausted']=activity['quota_exhausted'] or any(
      w.get('limit_id') in ('five_hour','seven_day') and
      ((isinstance(w.get('remaining_percent'),(int,float)) and w['remaining_percent']<=0) or w.get('provider_status') in ('rejected','denied'))
      for w in event.get('quota_windows',[]))
    with (folder/'events.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(event,ensure_ascii=False)+'\n')
    with self.lock:
     if event.get('kind') in ('tool','text'):self.saved['director_runtime']['last_progress_at']=stamp()
     if event.get('model'):self.saved['leader']['model']=event['model']
     if event.get('session_id'):self.saved['leader']['backup_session_id']=event['session_id']
     if event.get('usage') is not None:self.saved['leader']['backup_usage']=event['usage']
     self._record('director','Claude · '+event.get('kind','activity'),json.dumps(event,ensure_ascii=False)[:4000],'working');self._persist()
   launched=True
   result=launch(session)
   with self.lock:
    self.saved['director_runtime'].update(result_status=result.get('status'),finished_at=stamp())
   if session and _missing_session(result):
    # Preserve the original conversation. A missing transcript is not permission
    # to replace Tony's continuing director with a blank context.
    save(folder/'RESULT.json',result)
    with self.lock:
     self.saved['leader'].update(status='error',turn_id=None,error='Saved Claude conversation could not be resumed. Its ID is preserved; restore it or explicitly reset the session. No blank replacement or automatic retry was started.')
     self._record('director','Claude conversation needs recovery',str(folder/'RESULT.json'),'failed');self._persist()
    return
   save(folder/'RESULT.json',result)
   if session and result.get('session_id') and result['session_id']!=session:
    raise ValueError('Claude returned a different conversation ID while resuming; original ID preserved. Reconcile the saved conversation; no blank retry.')
   if result.get('session_id'):
    with self.lock:self.saved['leader']['claude_session_id']=result['session_id'];self._persist()
   known=result.get('process_stopped') is True and result.get('idle_inference') is False and result.get('status') in ('COMPLETED','FAILED','BLOCKED','CANCELLED','TIMED_OUT')
   detail=str(result.get('error') or result.get('text') or result.get('status'))
   if cancel.is_set():
    with self.lock:
     pending=self._handoff_native_pending()
     self.saved['leader'].update(status='idle' if known and not pending else 'uncertain',turn_id=None,error=None if known and not pending else 'Stopped director; reconcile outstanding native execution before resuming.')
     self._persist()
    return
   from usage_routing import confirmed_quota, request as request_quota_failover
   quota=known and result.get('status')=='FAILED' and (confirmed_quota(detail) or activity['quota_exhausted'])
   if quota:
    with self.lock:
     from usage_routing import reset_from_text
     reset_at=result.get('quota_reset_at') or reset_from_text(detail)
     self.saved['native_claude_exhausted']={'reported_at':stamp(),'reason':detail[:1200],'reset_at':reset_at,'shared_confirmed':activity['quota_exhausted'],'retry':'Explicit Retry Claude control or a provider-reported reset only; no automatic quota probing.'}
     self._record('director','Native Claude allowance refused',detail[:1200],'failed')
     self.saved['leader'].update(status='error',turn_id=None,error='Native Claude refused for allowance; safe succession is being reconciled. '+detail[:600]);self._persist()
     self._persist()
    if isinstance(reset_at,(int,float)):self.register_reset_wake('claude',reset_at)
    else:
     with self.lock:self._record('director','Native Claude reset time unknown','The provider reported no usable reset time; no wake was registered and nothing will be retried automatically.','waiting');self._persist()
    pending=self._handoff_native_pending()
    if pending:
     try:self.watch_native({'command_id':pending,'timeout_seconds':900})
     except Exception as e:
      with self.lock:self._record('director','Native quota handoff needs reconciliation',str(e)[:500],'waiting');self._persist()
    request_quota_failover(self,'claude',folder.name);return
   if known and result.get('status')=='TIMED_OUT':
    with self.lock:
     if result.get('session_id'):self.saved['leader']['claude_session_id']=result['session_id']
     self.saved['leader'].update(status='idle',error=None,turn_id=None)
     self.saved['leader']['messages'].append({'id':uuid.uuid4().hex,'role':'assistant','text':'Claude reached its inactivity limit; this is separate from subscription allowance. Its process is confirmed stopped. Neural is reconciling saved work for a bounded continuation of the same session; no native command is being replayed.','status':'completed','created_at':stamp()})
     self._record('director','Stopped Claude timeout; reconciling partial work',str(folder/'RESULT.json'),'completed');self._persist()
    pending=self._handoff_native_pending()
    if pending:
     self.watch_native({'command_id':pending,'timeout_seconds':900})
    elif hasattr(self,'production_turn_finished'):
     self.production_turn_finished('TIMED_OUT')
    return
   if known and result.get('status')=='FAILED' and (result.get('terminal_subtype')=='error_max_turns' or 'maximum number of turns' in detail.lower()):
    # Step budget reached mid-work: not a failure. The session is saved, so the next turn resumes it.
    with self.lock:
     if result.get('session_id'):self.saved['leader']['claude_session_id']=result['session_id']
     self.saved['leader']['messages'].append({'id':uuid.uuid4().hex,'role':'assistant','text':'['+str(result.get('model') or model)+' · native Claude]\nPaused at the per-turn step limit. My session is saved; send "continue" (or a pending studio event will wake me) and I pick up exactly where I stopped.','status':'completed','created_at':stamp()})
     self.saved['leader'].update(status='idle',error=None,turn_id=None,backup_session_id=result.get('session_id'),backup_usage=result.get('usage_events'))
     self._record('director','Native Claude paused at step limit',str(folder/'RESULT.json'),'completed');self._persist()
    self._drain_wakes()
    if hasattr(self,'production_turn_finished'):self.production_turn_finished('COMPLETED')
    return
   with self.lock:
    self.saved['leader']['messages'].append({'id':uuid.uuid4().hex,'role':'assistant','text':'['+str(result.get('model') or model)+' · native Claude]\n'+str(result.get('text') or detail)[-16000:],'status':'completed' if result.get('status')=='COMPLETED' else 'failed','created_at':stamp(),'provenance':{'provider':'claude','model':result.get('model') or model,'profile_id':native.get('profile_id'),'run':str(folder)}})
    self.saved['leader'].update(status='idle' if result.get('status')=='COMPLETED' else 'error' if known else 'uncertain',error=None if result.get('status')=='COMPLETED' else detail[:1600],turn_id=None,backup_session_id=result.get('session_id'),backup_usage=result.get('usage_events'))
    if result.get('session_id') and result.get('status') in ('COMPLETED','FAILED','BLOCKED','CANCELLED'):self.saved['leader']['claude_session_id']=result['session_id']
    self._record('director','Native Claude '+result.get('status','UNKNOWN'),str(folder/'RESULT.json'),result.get('status'));self._persist()
   if result.get('status')=='COMPLETED':self._drain_wakes()
   if hasattr(self,'production_turn_finished'):self.production_turn_finished(result.get('status','UNKNOWN'))
  except Exception as e:
   with self.lock:
    self.saved['leader'].update(status='uncertain' if launched else 'error',error=str(e)[:1600],turn_id=None)
    self._record('error','Native director needs attention',str(e),'failed');self._persist()
   if hasattr(self,'production_turn_finished'):self.production_turn_finished('failed')

 def _finish_native_fallback(self,text,models,images=None):
  pending=self._handoff_native_pending()
  if pending:
   with self.lock:
    self.saved['leader'].update(status='idle',turn_id=None,error=None)
    self._record('director','Waiting for exact native result before Gemini',pending,'waiting');self._persist()
   if hasattr(self,'watch_native'):self.watch_native({'command_id':pending,'timeout_seconds':900})
   else:raise ValueError('Native execution still pending; no second director was launched.')
   return
  if self.backup_cancel.is_set():return
  if not models:raise ValueError('Claude allowance refused and no final Gemini route was authorized.')
  if images:
   with self.lock:
    self.saved['leader'].update(status='error',turn_id=None,error='Native Claude reached its allowance and the Gemini fallback cannot see screenshots, so no blind text-only turn was started. Your screenshots remain in the conversation.')
    self._persist()
   return
  self._backup_turn('Native Claude reached its reported allowance. Read the current STATE and reconcile partial native/local work before continuing.\n'+text,models_override=models)

 def reset_claude_session(self):
  with self.lock:
   if self.saved['leader']['status'] in self.active:raise ValueError('Finish or stop the current director first.')
   self.saved['leader'].pop('claude_session_id',None)
   self._record('director','Claude director session reset','The next Claude director turn starts a fresh session from STATE.md.','completed');self._persist()
  return self.snapshot()

 def retry_native_claude(self):
  with self.lock:
   if self.saved['leader']['status'] in self.active:raise ValueError('Finish or stop the current director first.')
   self.saved.pop('native_claude_exhausted',None)
   self._record('director','Native Claude retry enabled','Human requested a fresh future attempt. No model turn was started.','completed');self._persist()
  return self.snapshot()

 def reconcile_native_timeout(self):
  """Startup/manual reconciliation only, never a polling inference trigger."""
  with self.lock:
   if self.closed or not self.saved.get('continuation_authorized') or self.saved.get('backup_suppressed') or self.saved.get('production_pause'):return False
   leader=self.saved['leader']
   if leader.get('status') not in ('uncertain','error','interrupted'):return False
   evidence=confirmed_timeout(self)
   if not evidence:return False
   try:
    from production import ProductionBoard
    plan=ProductionBoard(self.root).snapshot()['plan']
    if not plan or plan.get('direction_id')!=self.saved.get('production_direction') or plan.get('needs_update') or plan.get('ready_for_review'):return False
   except (OSError,ValueError,KeyError):return False
   # A provider timeout does not imply any local/native operation was cancelled.
   if any(j.get('status') in self.runtime.active_states for j in self.runtime.jobs()):return False
   local=getattr(self.runtime,'local_ops',None)
   if local and local.snapshot().get('active'):return False
   result=evidence['result']
   if result.get('session_id'):leader['claude_session_id']=result['session_id']
   leader.update(status='idle',error=None,turn_id=None)
   self._record('director','Reconciled confirmed stopped Claude timeout',evidence['folder']+'; current authorized revision only, no command replay.','completed');self._persist()
  pending=self._handoff_native_pending()
  if pending:self.watch_native({'command_id':pending,'timeout_seconds':900})
  elif hasattr(self,'production_turn_finished'):self.production_turn_finished('TIMED_OUT')
  return True
