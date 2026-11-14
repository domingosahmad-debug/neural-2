"""Lumen's explicit, exclusive trial-editor role. Observation is a different role.

Only queued human/director tasks and owned completion events invoke a model.
Provider file/shell permissions are instruction-scoped, not a hard sandbox.
"""
import copy, functools, hashlib, json, re, threading, time, uuid
from pathlib import Path
from operations import load,save,stamp
from workflows import WorkflowProfiles
from team_memory import TeamMemory
from previews import PreviewCatalog

EDITOR_LOCK=threading.RLock()
OWNING={'RUNNING','WAITING_LOCAL','UNKNOWN','PAUSED'}
LIVE={'QUEUED',*OWNING}

def executor_route(provider,model):
 """B2: which installed tool-equipped adapter may run the exclusive editor lane. None = unsupported (no substitution)."""
 model=str(model or '')
 if provider=='antigravity' and model.startswith('gemini-') and 'flash' in model:return 'agy'
 if provider=='claude' and model in ('opus','sonnet','haiku'):return 'claude'
 return None

def director_guard(fn):
 @functools.wraps(fn)
 def wrapped(self,*args,**kwargs):
  with EDITOR_LOCK:
   editor=getattr(self.runtime,'lumen_editor',None)
   if editor and editor.owns_editor() is True:raise ValueError('Lumen trial owns the editing lane. Finish/reconcile it before a director editing turn; no second editor was started.')
   return fn(self,*args,**kwargs)
 return wrapped

def _outcome(text):
 """Parse the worker's final JSON; a prose reply becomes an honest BLOCKED report instead of a crash (8 Nov 2026)."""
 body=re.sub(r'^```(?:json)?\s*|\s*```$','',str(text or '').strip())
 try:
  out=json.loads(body)
  if isinstance(out,dict) and out.get('status') in ('WAITING','REVIEW_REQUIRED','BLOCKED'):return out
 except ValueError:pass
 for m in re.finditer(r'\{',body):
  try:
   out=json.JSONDecoder().raw_decode(body[m.start():])[0]
   if isinstance(out,dict) and out.get('status') in ('WAITING','REVIEW_REQUIRED','BLOCKED'):return out
  except ValueError:continue
 return {'status':'BLOCKED','summary':'Worker replied in prose (no JSON result): '+body[:1700],'preview_id':'','local_jobs':[],'skills_read':[]}


class LumenEditor:
 def __init__(self,runtime,start_loop=True):
  self.runtime=runtime;self.root=Path(runtime.root);self.base=self.root/'data/lumen-editor';self.path=self.base/'STATE.json'
  self.lock=threading.RLock();self.cancel=threading.Event();self.closed=threading.Event();self.thread=None
  try:self.saved=load(self.path)
  except (OSError,ValueError):self.saved={'active_id':None}
  # A process restart never means a remote tool/model stopped and never auto-resumes an edit.
  if self.saved.get('active_id'):
   j=self.job()
   if j['status'] in LIVE:self.update(j,status='UNKNOWN',error='Companion restarted. Reconcile exact provider/local/native execution before explicit resume.')
  if start_loop:threading.Thread(target=self._loop,daemon=True,name='lumen-editor-events').start()
 def persist(self):save(self.path,self.saved)
 def job(self):return load(self.root/'data/jobs'/self.saved['active_id']/'JOB.json')
 def owns_editor(self):return bool(self.saved.get('active_id') and self.job()['status'] in OWNING)
 def snapshot(self):
  j=self.job() if self.saved.get('active_id') else None
  learner=load(self.root/'data/workflow-apprentice/STATE.json');model=learner.get('model','gemini-3.8-flash-high');provider=learner.get('provider','antigravity')
  return {'version':1,'role':'trial_editor','status':j['status'] if j else 'IDLE','job':j,'configured_model':model,'configured_provider':provider,'adapter_supported':executor_route(provider,model) is not None,'route':executor_route(provider,model),
   'capabilities':{'file_shell_tools':'official Antigravity accept-edits or Claude executor tools; instruction-scoped','native_ae':'exclusive TonyFX editing lane','local_engine':True,'provider_conversation_resume':True,'listening':False,'full_speed_perception':False},
   'projects':[{'id':p['id'],'name':p['name'],'assets':len(p.get('assets',[]))} for p in self.runtime.projects()[:40]],
   'history':self.history(),'idle_model_calls':0,'learning_is_training':False,
   'assignment_api':'/api/apprentice/editor/start','notice':'Explicit trials use model allowance; saved lessons improve retrieved instructions, not model weights. Final human approval remains separate.'}
 def history(self):
  workflow=WorkflowProfiles(self.root).snapshot()['id'];rows=[]
  for p in sorted((self.base/workflow/'trials').glob('*/TRIAL.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
   t=load(p);rows.append({k:t.get(k) for k in ('id','title','project_id','model','lesson_count','skill_count','lesson_sha256','created_at','status','preview_id','feedback')})
  return rows
 def update(self,j,**changes):
  j.update(changes,updated_at=stamp());self.runtime.write_job(j)
  trial=Path(j['trial_path'])/'TRIAL.json'
  if trial.is_file():
   row=load(trial);row.update(status=j['status'],summary=j.get('summary'),preview_id=j.get('preview_id'));save(trial,row)
  if changes.get('status') in ('FAILED','BLOCKED','UNKNOWN','REVIEW_REQUIRED'):
   from attention import AttentionStore
   AttentionStore(self.root).publish('lumen-trial:'+j['id']+':'+j['status'],'Lumen trial ready for review' if j['status']=='REVIEW_REQUIRED' else 'Lumen trial needs attention',j.get('error') or j.get('summary') or j['status'],'review_ready' if j['status']=='REVIEW_REQUIRED' else 'needs_attention')
 def native_pending(self):return self.runtime.command._handoff_native_pending()
 def _source_dirs(self,j):
  # 10 Nov 2026: a trial continuing a director-built production must read that source project's saved plans/results (read-only).
  try:source=load(Path(j['trial_path'])/'TRIAL.json').get('source_project_id')
  except (OSError,ValueError,KeyError):return []
  folder=self.root/'data/projects'/str(source) if isinstance(source,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',source) else None
  return [folder] if folder and folder.is_dir() else []
 def unavailable(self,own=None):
  from future_delegation import helper_busy
  if helper_busy(self.runtime):return 'Lumen station helper must finish or be reconciled'
  c=self.runtime.command.snapshot()
  if c['leader']['status'] in self.runtime.command.active:return 'Director is working'
  if any(key!=own and w.get('status') in ('waiting','ready') for key,w in c.get('watches',{}).items()):return 'Director completion chain is still active'
  if self.runtime.local_ops.snapshot()['active']:return 'Local/native engine is working'
  if any(j['status'] in self.runtime.active_states and j['id']!=own for j in self.runtime.jobs()):return 'A station worker is active'
  apprentice=getattr(self.runtime,'apprentice',None)
  if apprentice and (apprentice.snapshot().get('status')=='learning' or apprentice.snapshot().get('execution_unknown')):return 'Lumen learning call must finish or be reconciled'
  if self.native_pending():return 'Native execution is unresolved'
  try:plan=load(self.root/'data/production/CURRENT.json')
  except (OSError,ValueError):plan={}
  own_project=self.job()['project_id'] if own and self.saved.get('active_id') else None
  previous_trial_projects={t['project_id'] for t in self.history() if t.get('status') not in LIVE}
  parent_handoff=bool(own and self.saved.get('active_id') and self.job().get('parent_direction') and self.job().get('parent_direction')==c.get('production_direction') and c.get('watches',{}).get(own,{}).get('status')=='waiting')
  if c.get('continuation_authorized') and plan and not parent_handoff and plan.get('project_id')!=own_project and plan.get('project_id') not in previous_trial_projects and not plan.get('ready_for_review') and not plan.get('paused'):return 'Current production is not handed off; its owner keeps the editor'
  return None
 def submit(self,data):
  brief=str(data.get('brief','')).strip();source_id=data.get('source_project_id')
  if not 5<=len(brief)<=8000:raise ValueError('Give Lumen a concrete trial brief (5–8000 characters)')
  source=self.runtime.project(source_id) if source_id else None
  if source and source.get('workflow_id','tuf')!=WorkflowProfiles(self.root).snapshot()['id']:raise ValueError('Select the source project’s workflow first; trial memories are isolated by workflow')
  paths=data.get('assets') or [a['path'] for a in (source or {}).get('assets',[])]
  if not paths:raise ValueError('Choose a source project or supply original footage/music paths. No blind edit was queued.')
  learner=load(self.root/'data/workflow-apprentice/STATE.json')
  model=learner.get('model','gemini-3.8-flash-high')
  provider=learner.get('provider','antigravity')
  if executor_route(provider,model) is None:raise ValueError('This editing lane supports Gemini Flash on Antigravity or Claude opus/sonnet/haiku only. No provider substitution was made.')
  with EDITOR_LOCK,self.lock:
   if self.saved.get('active_id') and self.job()['status'] in LIVE:raise ValueError('Lumen already has a queued/owned trial; inspect it before another assignment')
   workflow=WorkflowProfiles(self.root).snapshot();wid=workflow['id'];key=uuid.uuid4().hex;folder=self.base/wid/'trials'/key;folder.mkdir(parents=True)
   title=str(data.get('title') or 'Lumen trial')[:100]
   project=self.runtime.create_project({'name':title,'brief':brief,'mode':(source or {}).get('mode','original'),'assets':paths})
   ledger=load(self.root/'data/workflow-apprentice/MISTAKE_LEDGER.json');entries=[r for r in ledger.get('entries',[]) if r.get('workflow_id','tuf')==wid]
   skill_paths=sorted({str(p.relative_to(self.root)).replace('\\','/') for p in (self.root/'knowledge/skills').glob('*/SKILL.md')})
   memory={'workflow':workflow,'source_project':source_id,'trial_project':project,'lessons':entries,'skills':[{'path':p,'sha256':hashlib.sha256((self.root/p).read_bytes()).hexdigest()} for p in skill_paths],
    'team':TeamMemory(self.root).worker_context({'station':'editing','project_id':project['id'],'workflow':workflow}),
    'earlier_trials':self.history(),'authority':'This is a new explicit editing trial. Other projects and finished scenes are not reusable source assets.'}
   save(folder/'MEMORY.json',memory)
   trial={'id':key,'title':title,'project_id':project['id'],'source_project_id':source_id,'brief':brief,'workflow_id':wid,'model':model,'created_at':stamp(),'status':'QUEUED','lesson_count':len(entries),'skill_count':len(skill_paths),'lesson_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest(),'feedback':[]}
   save(folder/'TRIAL.json',trial)
   j={'id':key,'title':title,'project_id':project['id'],'task_id':None,'station':'editing','agent_id':'lumen-editor','agent_name':'Lumen · trial editor','provider':provider,'route':executor_route(provider,model),'model':model,'status':'QUEUED','created_at':stamp(),'trial_path':str(folder),'workflow_id':wid,'turns':0,'owned_local_jobs':[],'session_id':None,'process_stopped':True,'idle_inference':False,'error':None,'native_baseline':None}
   self.saved['active_id']=key;self.persist();self.update(j)
  if data.get('wake_director') is True:
   c=self.runtime.command.snapshot()
   if c.get('continuation_authorized') and c['leader']['status'] in self.runtime.command.active:
    self.runtime.command.watch_job({'job_id':key})
    with self.lock:self.update(self.job(),parent_direction=c.get('production_direction'))
  return self.snapshot()
 def tick(self):
  if not self.saved.get('active_id') or self.closed.is_set():return
  with EDITOR_LOCK,self.lock:
   if self.thread and self.thread.is_alive():return
   j=self.job()
   if j['status']=='QUEUED':
    reason=self.unavailable(j['id'])
    if reason:
     if j.get('waiting_reason')!=reason:self.update(j,waiting_reason=reason)
     return
    self.update(j,status='RUNNING',waiting_reason=None)
   elif j['status']=='WAITING_LOCAL':
    jobs=[self.runtime.local_ops.job(k) for k in j.get('waiting_for',[])]
    if any(v['status'] in ('QUEUED','RUNNING','CANCELLING') for v in jobs):return
    if self.native_pending():self.update(j,status='UNKNOWN',error='Owned completion ended but native execution is unresolved. No replay.');return
    if j.get('final_verification') and all(v['status']=='COMPLETED' for v in jobs):
     try:PreviewCatalog(self.root).media(j['preview_id'])
     except (ValueError,OSError):self.update(j,status='BLOCKED',error='Trial review changed after registration. Register and verify the actual new file.');return
     self.update(j,status='REVIEW_REQUIRED',error=None,final_verification=None)
     TeamMemory(self.root).message({'project_id':j['project_id'],'kind':'finding','to':'Director','text':'Full trial review decoded successfully; human motion/listening/artistic review remains pending. '+str(j.get('summary',''))[:900]},sender='Lumen · trial editor')
     return
    j.pop('final_verification',None)
    self.update(j,status='RUNNING',completion_evidence=[{'id':v['id'],'status':v['status'],'summary':str(self.runtime.local_ops.folder(v['id'])/'SUMMARY.json')} for v in jobs])
   else:return
   self.cancel=threading.Event();self.thread=threading.Thread(target=self._turn,args=(j,),daemon=True,name='lumen-edit-'+j['id'][:8]);self.thread.start()
 def _loop(self):
  while not self.closed.wait(2):
   try:self.tick()
   except Exception as e:
    with self.lock:
     if self.saved.get('active_id'):self.update(self.job(),status='UNKNOWN',error=str(e)[:800])
 def local(self,data):
  with self.lock:
   j=self.job()
   if j['status']!='RUNNING' or data.get('job_id')!=j['id']:raise ValueError('Only the active Lumen task may submit owned local work')
   result=self.runtime.local_ops.submit({**data['plan'],'project_id':j['project_id']});j=self.job();j['owned_local_jobs'].append(result['id']);self.update(j)
   return {'id':result['id'],'status':result['status'],'owner':j['id']}
 def watch_native(self,data):
  j=self.job();key=data.get('command_id')
  if not key or key==j.get('native_baseline') or self.native_pending()!=key:raise ValueError('Only a new exact pending native command from this turn can be watched')
  return self.local({'job_id':data.get('job_id'),'plan':{'version':1,'title':'Lumen exact native observation','steps':[{'id':'native','operation':'native_observe','args':{'command_id':key,'timeout_seconds':900}}]}})
 def feedback(self,data):
  j=self.job();text=str(data.get('text','')).strip()
  if not 1<=len(text)<=2200:raise ValueError('Feedback must be 1–2200 characters')
  p=Path(j['trial_path'])/'TRIAL.json';t=load(p);t['feedback']=(t.get('feedback',[])+[{'at':stamp(),'text':text,'authority':'Human trial feedback; not automatically a universal rule'}])[-40:];save(p,t)
  TeamMemory(self.root).note({'project_id':j['project_id'],'kind':'correction','station':'editing','text':text,'source':str(p)},j['workflow_id'])
  apprentice=getattr(self.runtime,'apprentice',None)
  if apprentice and hasattr(apprentice,'notify_event'):apprentice.notify_event('review','completed')
  return self.snapshot()
 def stop(self):
  self.cancel.set()
  with self.lock:
   j=self.job()
   if j['status']=='QUEUED':self.update(j,status='CANCELLED',error='Cancelled before inference')
   elif j['status']=='WAITING_LOCAL':self.update(j,status='UNKNOWN',error='Stop revoked continuation. Owned local/native work may continue; reconcile before reuse.')
   elif j['status']=='RUNNING':self.update(j,status='UNKNOWN',error='Stopping the owned CLI; native/remote stop must be verified.')
  return self.snapshot()
 def reconcile(self):
  with self.lock:
   j=self.job()
   if j['status']!='UNKNOWN':return self.snapshot()
   if self.thread and self.thread.is_alive():raise ValueError('The owned CLI is still stopping')
   if j.get('process_stopped') is not True:raise ValueError('Owned process stop is unconfirmed')
   if j.get('idle_inference') is not False:
    observed=self.runtime.headless.inspect_agy_local_session(j.get('session_id'))
    if not observed.get('local_idle'):raise ValueError('Provider conversation is not confirmed idle')
   if self.runtime.local_ops.snapshot()['active'] or self.native_pending():raise ValueError('Local/native work remains active or unresolved')
   self.update(j,status='PAUSED',idle_inference=False,error='Reconciled; explicit resume or release is required')
  return self.snapshot()
 def resume(self):
  with self.lock:
   j=self.job()
   if j['status']!='PAUSED':raise ValueError('Reconcile to PAUSED before explicitly resuming')
   self.update(j,status='QUEUED',error=None)
  return self.snapshot()
 def release(self):
  with self.lock:
   j=self.job()
   if j['status']!='PAUSED':raise ValueError('Only reconciled PAUSED work may release its editing lane')
   self.update(j,status='CANCELLED',error='Explicitly released after reconciliation')
  return self.snapshot()
 def _turn(self,j):
  folder=Path(j['trial_path']);launched=False
  try:
   # Metadata check once per real turn; never a quota/model probe loop.
   route=j.get('route') or executor_route(j.get('provider'),j.get('model'))
   if route=='claude':
    from staffing import native_claude_exhausted
    from claude_transport import connection
    st=load(self.root/'data/command/STATE.json') if (self.root/'data/command/STATE.json').is_file() else {}
    if native_claude_exhausted(st) or not connection().get('available'):raise ValueError('Claude subscription executor unavailable or exhausted. No paid fallback or inference attempted.')
   elif route=='agy':
    models=self.runtime.headless.snapshot().get('antigravity',{}).get('models',[])
    q=self.runtime.headless.query_agy('quota',timeout=12)
    buckets=(q.get('quota') or {}).get('buckets',[]);remaining=[b['remaining_percent'] for b in buckets if b.get('group')=='Gemini Models' and isinstance(b.get('remaining_percent'),(int,float))]
    if j['model'] not in models or q.get('status')!='OK' or not remaining or min(remaining)<=1:raise ValueError('Exact Flash model or included Gemini allowance unavailable. No paid fallback or inference attempted.')
   else:raise ValueError('Unsupported executor route. No substitution.')
   if self.cancel.is_set():self.update(self.job(),status='PAUSED',process_stopped=True,idle_inference=False,error='Stopped before model inference');return
   if j['turns']>=16:raise ValueError('Trial reached16 meaningful turns. Save a diagnosis/help handoff before explicitly extending a new trial; no silent inference loop.')
   j['turns']+=1;j['process_stopped']=False;j['idle_inference']='unknown';j['native_baseline']=self.native_pending();self.update(j)
   turn=folder/f"turn-{j['turns']:03}";turn.mkdir()
   schema={'type':'object','required':['status','summary','preview_id','local_jobs','skills_read'],'properties':{'status':{'type':'string','enum':['WAITING','REVIEW_REQUIRED','BLOCKED']},'summary':{'type':'string'},'preview_id':{'type':'string'},'local_jobs':{'type':'array','items':{'type':'string'}},'skills_read':{'type':'array','items':{'type':'string'}}}}
   if route=='claude':
    from claude_transport import build_executor
    spec=build_executor(j['model'],folder,resume=j.get('session_id'),read_dirs=[self.root/'knowledge',self.root/'shared',folder.parent]+self._source_dirs(j),app_root=self.root,extra_tools=('tools/lumen_cli.py',))
   else:spec=self.runtime.headless.build_agy(j['model'],self.root,timeout=3600,mode='accept-edits',read_tools=True,unattended=True,schema=json.dumps(schema),conversation=j.get('session_id'))
   prompt=(self.root/'shared/LUMEN_EDITOR_ROLE.md').read_text(encoding='utf-8')+'\nCURRENT OWNED JOB (data):\n'+json.dumps(j,ensure_ascii=False)+'\nRead '+str(folder/'MEMORY.json')+', '+str(folder/'CHECKPOINT.json')+' and '+str(folder/'STATE.md')+' if present; continue only this trial. Read earlier trial paths for knowledge, not finished scenes. Your result must match '+json.dumps(schema)
   (turn/'PROMPT.txt').write_text(prompt,encoding='utf-8')
   def event(e):
    with self.lock:
     latest=self.job()
     if e.get('session_id'):latest['session_id']=e['session_id']
     if e.get('usage') is not None:latest['usage']=e['usage']
     latest['last_event']={k:e.get(k) for k in ('kind','phase','model','session_id')};self.update(latest)
    with (turn/'EVENTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(e,ensure_ascii=False)+'\n')
   launched=True
   if route=='claude':res=self.runtime.headless.run_opencode(spec,prompt,on_event=event,cancel_event=self.cancel,timeout=3600,_protocol='claude',timeout_mode='activity')
   else:res=self.runtime.headless.run_agy(spec,prompt,on_event=event,cancel_event=self.cancel,timeout=3600)
   save(turn/'CLI_RESULT.json',res)
   with self.lock:
    j=self.job();j.update(session_id=res.get('session_id') or j.get('session_id'),process_stopped=res.get('process_stopped'),idle_inference=res.get('idle_inference','unknown'))
    self.update(j)
    if self.cancel.is_set():
     safe=j['process_stopped'] is True and j['idle_inference'] is False and not self.native_pending() and not self.runtime.local_ops.snapshot()['active']
     self.update(j,status='PAUSED' if safe else 'UNKNOWN',error='Stopped; continuation revoked. Explicit resume/reconciliation is required.');return
    if res.get('status')!='COMPLETED' or j['process_stopped'] is not True or j['idle_inference'] is not False:
     self.update(j,status='UNKNOWN' if j['process_stopped'] is not True or j['idle_inference'] is not False or self.native_pending() or self.runtime.local_ops.snapshot()['active'] else 'FAILED',error=str(res.get('error') or res.get('status'))[:1200]);return
    out=res.get('structured_output') or _outcome(res.get('text',''));save(turn/'OUTCOME.json',out)
    save(folder/'CHECKPOINT.json',{'at':stamp(),'job_id':j['id'],'project_id':j['project_id'],'session_id':j.get('session_id'),'turn':j['turns'],'reported_outcome':out,'source':str(turn/'OUTCOME.json'),'authority':'Worker-reported checkpoint; reconcile real native/local state before writes. Not artistic approval.'})
    j['summary']=str(out.get('summary',''))[:1800]
    if self.cancel.is_set():self.update(j,status='UNKNOWN' if self.native_pending() or self.runtime.local_ops.snapshot()['active'] else 'PAUSED',error='Stopped; no continuation');return
    if out['status']=='WAITING':
     ids=out.get('local_jobs',[])
     if not ids or any(k not in j['owned_local_jobs'] for k in ids):raise ValueError('WAITING needs actual owned job IDs; no arbitrary polling turn')
     self.update(j,status='WAITING_LOCAL',waiting_for=ids);return
    if self.native_pending() or self.runtime.local_ops.snapshot()['active']:self.update(j,status='UNKNOWN',error='Worker ended while local/native execution remains unresolved');return
    if out['status']=='REVIEW_REQUIRED':
     row=next((p for p in PreviewCatalog(self.root).listing()['previews'] if p['id']==out.get('preview_id') and p.get('project_id')==j['project_id'] and p.get('kind')=='full'),None)
     if not row:raise ValueError('Completion needs an actual registered full review for this trial project')
     if not out.get('skills_read') or any(not (self.root/s).resolve().is_relative_to((self.root/'knowledge/skills').resolve()) or not (self.root/s).is_file() for s in out['skills_read']):raise ValueError('Trial must report actual existing bundled skills read')
     frozen={s['path']:s['sha256'] for s in load(folder/'MEMORY.json')['skills']}
     if any(s not in frozen or hashlib.sha256((self.root/s).read_bytes()).hexdigest()!=frozen[s] for s in out['skills_read']):raise ValueError('Reported skill versions no longer match this trial’s frozen knowledge delivery')
     media=PreviewCatalog(self.root).media(row['id'])
     checked=self.local({'job_id':j['id'],'plan':{'version':1,'title':'Lumen final full review decode gate','steps':[{'id':'decode','operation':'verify_render','args':{'input':str(media),'expect':{'audio':True}}}]}})
     j=self.job();self.update(j,status='WAITING_LOCAL',preview_id=row['id'],waiting_for=[checked['id']],final_verification=True,error=None)
     return
    else:self.update(j,status='BLOCKED',error=j['summary'] or 'Worker reported a block')
    TeamMemory(self.root).message({'project_id':j['project_id'],'kind':'finding' if j['status']=='REVIEW_REQUIRED' else 'help','to':'Director','text':j['summary'] or j.get('error','Trial ended'),'source':str(turn/'OUTCOME.json')},sender='Lumen · trial editor')
  except Exception as e:
   with self.lock:
    j=self.job();unknown=(launched and (j.get('process_stopped') is not True or j.get('idle_inference') is not False or self.runtime.local_ops.snapshot()['active'])) or bool(self.native_pending())
    self.update(j,status='UNKNOWN' if unknown else 'FAILED',error=str(e)[:1400])
 def shutdown(self):self.closed.set();self.cancel.set()
