"""Shared edit contracts, approved methods and truthful local production evidence.

No model client, startup resumption or timer lives here. Model evaluations are
deliberately absent. Existing director/native ownership remains authoritative.
"""
import copy,hashlib,json,math,re,threading,time,uuid
from contextlib import contextmanager
from pathlib import Path
from fractions import Fraction
from operations import load,save,stamp
from workflows import WorkflowProfiles

VERSION='2026-10-22.1'
LOCK=threading.RLock()
STATIONS=('media','analysis','story','sound-design','editing','review-delivery')

@contextmanager
def store_lock(root,name):
 from local_engine import execution_lock
 with LOCK,execution_lock(Path(root)/'data/workbench-locks'/(name+'.lock'),lambda:None,5):yield

def read(path,default=None):
 try:return load(path)
 except (OSError,ValueError):return copy.deepcopy(default)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()
def ident(value):
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',str(value)):raise ValueError('Invalid project/record ID')
 return str(value)
def limited(value,n=400):return str(value or '')[:n]
def project_of(root):return read(Path(root)/'data/production/CURRENT.json',{})

class Blueprint:
 def __init__(self,root):self.root=Path(root)
 def path(self,project):return self.root/'data/blueprints'/ident(project)/'CURRENT.json'
 def snapshot(self,project):
  row=read(self.path(project),{}) if project else {}
  if row:
   checks=self.check(row['contract']);row={**row,'checks':checks,'structural_pass':not any(c['status']=='FAIL' for c in checks)}
  return {'version':VERSION,'blueprint':row or None,'model_calls':0}
 def check(self,contract):
  from local_ops_tasks import validate_edit
  edit=contract.get('edit',{});checks=validate_edit(edit);shots={s['id']:s for s in edit['shots']}
  def gate(name,errors):checks.append({'name':name,'status':'FAIL' if errors else 'PASS','detail':'; '.join(errors) or 'Supplied contract is structurally consistent; semantics still need review'})
  errors=[];duration=edit['duration_frames'];music=contract.get('music',{})
  ending=contract.get('ending',{});alternate=ending.get('audio_source') and type(ending.get('audio_end_frame')) is int and ending['audio_end_frame']>=duration and ending.get('intent')
  if (type(music.get('end_frame')) is not int or music['end_frame']<duration) and not alternate:errors.append('Music ends before picture; specify full coverage or a justified alternate ending-audio source')
  if contract.get('ending',{}).get('end_frame')!=duration:errors.append('Ending must account for the final picture frame')
  gate('Music and ending coverage',errors)
  errors=[];quotes={};caption_ids=set()
  for q in edit.get('dialogue',[]):
   key=q.get('id');linked=q.get('shot_ids') or [q.get('shot_id')];pictured=[shots.get(sid) for sid in linked];quotes[key]=q
   if not key or sum(v.get('id')==key for v in edit.get('dialogue',[]))!=1:errors.append('Quote IDs must be unique')
   covered=sorted([s for s in pictured if s and s['start_frame']<q['end_frame'] and s['end_frame']>q['start_frame']],key=lambda s:s['start_frame'])
   cursor=q['start_frame']
   for s in covered:
    if s['start_frame']>cursor:break
    cursor=max(cursor,s['end_frame'])
   if any(s is None for s in pictured) or cursor<q['end_frame']:errors.append(str(key)+': linked picture shots must cover the complete quote')
   if not q.get('speaker') or not q.get('text') or q.get('complete_phrase') is not True:errors.append(str(key)+': supply speaker, complete transcript and whole-phrase decision')
   if any(q.get('speaker') not in s.get('characters',[]) for s in covered) and not q.get('voiceover_reason'):errors.append(str(key)+': speaker absent from shot; explicit voiceover rationale required')
  for c in edit.get('captions',[]):
   if not c.get('id') or c['id'] in caption_ids:errors.append('Caption IDs must be unique')
   caption_ids.add(c.get('id'));q=quotes.get(c.get('quote_id'))
   if not q or c.get('speaker')!=q.get('speaker') or not(q['start_frame']<=c['start_frame']<c['end_frame']<=q['end_frame']):errors.append(str(c.get('id'))+': caption needs matching quote/speaker/timing')
   if not c.get('look'):
    methods=Recipes(self.root).listing()['recipes']
    if not any(r['id']==c.get('style_id') and r['approved'] for r in methods):errors.append(str(c.get('id'))+': supply an explicit look or an actually approved treatment ID')
  gate('Quote and caption ownership',errors)
  errors=[]
  for s in shots.values():
   if not s.get('purpose'):errors.append(s['id']+': missing sequence purpose')
   if s.get('action') and not s.get('sound',{}).get('source'):errors.append(s['id']+': action needs a source-sound plan, not implicit muting')
   if s.get('technique_id') and not s.get('technique_phase') in ('setup','action','payoff'):errors.append(s['id']+': label technique setup/action/payoff')
  for key in {s.get('technique_id') for s in shots.values()}-{None}:
   chain=[s for s in edit['shots'] if s.get('technique_id')==key];phases=[s.get('technique_phase') for s in chain]
   if phases.count('setup')!=1 or 'action' not in phases or phases[-1]!='payoff' or phases[0]!='setup':errors.append(str(key)+': repeated setup or incomplete technique payoff')
  for cue in contract.get('accents',[]):
   s=shots.get(cue.get('shot_id'));frame=cue.get('frame')
   if not s or type(frame) is not int or not s['start_frame']<=frame<s['end_frame'] or not cue.get('intent'):errors.append('Beat/zoom accent needs an in-range shot/frame and purpose')
  gate('Sequence, sound and accent intent',errors)
  return checks
 def update(self,data):
  project=ident(data.get('project_id'));revision=limited(data.get('revision'),120)
  if not revision:raise ValueError('Blueprint needs an explicit revision')
  contract=copy.deepcopy(data.get('contract',{}))
  if len(json.dumps(contract,allow_nan=False))>150000:raise ValueError('Blueprint is too large; use bounded shot ledgers')
  checks=self.check(contract)
  with store_lock(self.root,'blueprints'):
   path=self.path(project);old=read(path,{})
   if data.get('expected_hash')!=old.get('hash'):raise ValueError('Blueprint changed; reread its current hash')
   workflow=WorkflowProfiles(self.root).snapshot()['id']
   row={'project_id':project,'revision':revision,'workflow_id':workflow,'updated_at':stamp(),'contract':contract,'hash':digest({'revision':revision,'workflow':workflow,'contract':contract})}
   if old:save(path.parent/'history'/(old['hash']+'.json'),old)
   save(path,row)
  return self.snapshot(project)
 def require(self,project,revision=None):
  s=self.snapshot(project);row=s['blueprint']
  current=project_of(self.root)
  if revision is None and current.get('project_id')==project:revision=current.get('revision')
  if not row or (revision and row['revision']!=revision) or not row['structural_pass']:raise ValueError('A current structurally passing shared blueprint is required; read its failed gates before building')
  return row

class Recipes:
 _fingerprints={}
 def __init__(self,root):self.root=Path(root);self.base=self.root/'data/treatment-recipes'
 def listing(self):
  workflow=WorkflowProfiles(self.root).snapshot()['id'];rows=[]
  for p in sorted(self.base.glob('*/RECIPE.json'))[:200]:
   r=read(p,{})
   if r.get('workflow_id')==workflow:
    approval=r.get('approval');valid=False
    try:valid=bool(approval and approval.get('evidence') and approval.get('recipe_hash')==r.get('hash') and all(self.evidence(e['path'])==e for e in approval['evidence']))
    except (ValueError,OSError):pass
    rows.append({**r,'approved':valid})
  return {'recipes':rows,'starters':read(self.root/'shared/TREATMENT_METHOD_STARTERS.json',[]),'model_calls':0,'notice':'Approved methods are instructions, never reusable finished scenes or a quality guarantee.'}
 def evidence(self,value):
  p=(self.root/value).resolve()
  if not p.is_relative_to(self.root.resolve()) or not p.is_file() or p.stat().st_size>8*1024*1024:raise ValueError('Use an existing compact studio evidence file')
  stat=p.stat();signature=(stat.st_mtime_ns,stat.st_size);cached=self._fingerprints.get(str(p))
  if cached and cached[0]==signature:hashed=cached[1]
  else:
   hashed=hashlib.sha256(p.read_bytes()).hexdigest()
   if len(self._fingerprints)>=1000:self._fingerprints.clear()
   self._fingerprints[str(p)]=(signature,hashed)
  return {'path':p.relative_to(self.root.resolve()).as_posix(),'sha256':hashed}
 def propose(self,data):
  key=ident(data.get('id') or uuid.uuid4().hex);path=self.base/key/'RECIPE.json'
  with store_lock(self.root,'recipes'):
   old=read(path,{})
   if data.get('expected_hash')!=old.get('hash'):raise ValueError('Recipe changed; reread first')
   body={k:copy.deepcopy(data.get(k)) for k in ('name','station','intent','when_to_use','avoid','steps','parameters','limits','source_project','source_revision')}
   if not body['name'] or body['station'] not in STATIONS or not body['intent'] or not isinstance(body['steps'],list) or not 1<=len(body['steps'])<=24:raise ValueError('Recipe needs name, station, intent and 1–24 editable method steps')
   if len(json.dumps(body,allow_nan=False))>16000:raise ValueError('Keep recipe instructions compact')
   row={**body,'id':key,'workflow_id':WorkflowProfiles(self.root).snapshot()['id'],'updated_at':stamp(),'hash':digest(body),'approval':None}
   if old and old.get('workflow_id')!=row['workflow_id']:raise ValueError('Recipe belongs to another workflow')
   save(path,row)
  return row
 def approve(self,data,*,human=False):
  if not human:raise ValueError('Only Tony can approve a reusable treatment')
  path=self.base/ident(data['id'])/'RECIPE.json'
  with store_lock(self.root,'recipes'):
   row=load(path)
   if row['workflow_id']!=WorkflowProfiles(self.root).snapshot()['id'] or row['hash']!=data.get('expected_hash'):raise ValueError('Recipe/workflow changed; inspect it before approval')
   evidence=[self.evidence(p) for p in data.get('evidence',[])[:6]]
   if not evidence or not str(data.get('note','')).strip():raise ValueError('Approval needs evidence and Tony’s scoped decision')
   row['approval']={'by':'Tony','at':stamp(),'recipe_hash':row['hash'],'evidence':evidence,'note':limited(data['note'],1200)};save(path,row)
  return row

class UsageLedger:
 def __init__(self,root):self.root=Path(root);self.path=self.root/'data/usage-ledger/CALLS.json'
 def record(self,key,**data):
  # Public event metadata only. No prompts, credentials or inferred account quotas.
  with store_lock(self.root,'usage'):
   rows=read(self.path,{});row=rows.get(key,{'id':key,'started_at':stamp(),'status':'running'})
   row.update({k:v for k,v in data.items() if k in ('project_id','revision','provider','model','role','purpose','status','usage','usage_basis','usage_complete','finished_at','source','task_id','station','retry_of')});rows[key]=row
   save(self.path,dict(list(rows.items())[-1000:]))
 def snapshot(self,project=None):
  rows=list(read(self.path,{}).values())
  if project:rows=[r for r in rows if r.get('project_id')==project]
  rows=[{**r,'usage_basis':'legacy_last_request_unverified','usage_complete':False}
        if r.get('provider')=='codex' and r.get('role')=='director' and not r.get('usage_basis') else r for r in rows]
  return {'calls':rows[-100:][::-1],'model_calls_for_read':0,'notice':'Reported token consumption and recorded calls; not remaining subscription percent, money, or a complete historical bill. Missing usage is unknown.'}
 def restarted(self):
  with store_lock(self.root,'usage'):
   rows=read(self.path,{});changed=False
   for row in rows.values():
    if str(row.get('status','')).lower() in ('running','working','starting','queued','cancelling'):
     row.update(status='execution_unverified_after_restart');changed=True
   if changed:save(self.path,rows)

def consumption(events):
 if not events:return None
 totals={'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':0,'cache_creation_input_tokens':0};seen=False
 for event in events if isinstance(events,list) else [events]:
  for k in totals:
   v=event.get(k)
   if type(v) in (int,float) and math.isfinite(v) and v>=0:totals[k]+=v;seen=True
 return totals if seen else None

class RecoveryDesk:
 def __init__(self,root):self.root=Path(root);self.path=self.root/'data/recovery-desk/TICKETS.json'
 def record(self,data):
  key=ident(data.get('id') or uuid.uuid4().hex);allowed={'recoverable','capability','human_input','native_unknown','quota'}
  if data.get('kind') not in allowed or any(not data.get(k) for k in ('project_id','diagnosis','next_action','source')):raise ValueError('Recovery needs project, kind, actual diagnosis, source and scoped next action')
  source=(self.root/data['source']).resolve()
  if not source.is_relative_to(self.root.resolve()) or not source.is_file():raise ValueError('Recovery source must be existing studio evidence')
  source_evidence=Recipes(self.root).evidence(str(source))
  with store_lock(self.root,'recovery'):
   rows=read(self.path,{});old=rows.get(key,{})
   if old and old['project_id']!=data['project_id']:raise ValueError('Recovery ticket belongs to another project')
   state=data.get('status',old.get('status','open'))
   if state not in ('open','assigned','resolved','needs_attention'):raise ValueError('Invalid recovery state')
   evidence=[]
   if state=='resolved':
    evidence=[Recipes(self.root).evidence(p) for p in data.get('evidence',[])[:6]]
    if not evidence or not data.get('resolution'):raise ValueError('Resolved needs real new result evidence and resolution; a retry dispatch is not recovery')
    if not any(e['path']!=source.relative_to(self.root.resolve()).as_posix() for e in evidence):raise ValueError('Original failure alone cannot resolve its own recovery')
    for e in evidence:
     proof=read(self.root/e['path'],{})
     if isinstance(proof,dict) and (proof.get('status') in ('FAILED','UNKNOWN','BLOCKED','INTERRUPTED') or any(c.get('status')=='FAIL' for c in proof.get('checks',[]))):raise ValueError('Failing/unknown result evidence cannot resolve a recovery')
   row={**old,**{k:data[k] for k in ('project_id','revision','kind','diagnosis','next_action','source','owner','station','required_capabilities','replacement_job_id','resolution') if k in data},'id':key,'status':state,'updated_at':stamp(),'source_evidence':source_evidence,'evidence':evidence or old.get('evidence',[])};rows[key]=row;save(self.path,rows)
  return row
 def snapshot(self,project=None):
  rows=list(read(self.path,{}).values())
  return {'tickets':[r for r in rows if not project or r['project_id']==project][-80:][::-1],'model_calls':0}
 def consult(self,runtime,data):
  with store_lock(self.root,'recovery'):return self._consult(runtime,data)
 def _consult(self,runtime,data):
  key=ident(data['id']);row=load(self.path)[key]
  if row['kind'] in ('native_unknown','quota','human_input') or row['status']=='resolved':raise ValueError('This ticket cannot safely launch a consultation')
  if row.get('replacement_job_id'):raise ValueError('A consultation already exists; inspect its actual result and update the diagnosis before a new scoped ticket')
  station=row.get('station') or 'analysis'
  from staffing import roster
  candidates=roster(runtime,station,row.get('required_capabilities') or ['text'],'standard')['candidates']
  chosen=next((r for r in candidates if r['agent_id']==data.get('agent_id') and r['available']),None)
  if not chosen:raise ValueError('Choose an available worker with the ticket’s actual required capabilities')
  if runtime.command.snapshot()['leader']['status'] not in runtime.command.active:raise ValueError('An active director must own this consultation')
  task=runtime.create_task({'project_id':row['project_id'],'station':station,'title':'Recovery consultation · '+key[:8],'brief':'Diagnose only this failure and propose a scoped correction. No native edit or app changes. '+row['diagnosis']+'\nNext action: '+row['next_action'],'inputs':[str((self.root/row['source']).resolve())],'required_capabilities':row.get('required_capabilities') or ['text'],**({'blueprint_shot_ids':data['blueprint_shot_ids']} if data.get('blueprint_shot_ids') else {})})
  job=runtime.dispatch({'station':station,'task_id':task['id'],'agent_id':chosen['agent_id'],'assignment_reason':'Scoped consultation for recovery ticket '+key})
  runtime.command.watch_job({'job_id':job['id']})
  with LOCK:
   rows=load(self.path);rows[key].update(status='assigned',replacement_job_id=job['id'],owner=chosen['agent_id'],updated_at=stamp());save(self.path,rows)
  return job

def local_evidence(root,local):
 """Bounded summaries from the existing engine; no second queue or extraction."""
 jobs=local.get('jobs',[]);hits=0;steps=0;rows=[]
 for j in jobs:
  for s in j.get('steps',[]):
   steps+=1;hits+=bool(s.get('cached'));rows.append({'job_id':j['id'],'step':s['id'],'operation':s['operation'],'status':s['status'],'cached':s.get('cached',False),'cache':s.get('cache'), 'summary':limited(s.get('report',{}).get('summary'),240),'outputs':s.get('outputs',[])[:4]})
 return {'scope':'Active + latest 20 local jobs, not lifetime savings','steps':steps,'cache_hits':hits,'model_calls':0,'rows':rows[-100:]}

class Workbench:
 def __init__(self,root,runtime=None):self.root=Path(root);self.runtime=runtime
 def snapshot(self,project=None):
  plan=project_of(self.root);project=project or plan.get('project_id');local=self.runtime.local_ops.snapshot() if self.runtime and getattr(self.runtime,'local_ops',None) else {'jobs':[]}
  if self.runtime is None:
   index=read(self.root/'data/local-ops/INDEX.json',[]);index.sort(key=lambda j:j.get('created_at',''),reverse=True)
   chosen=[j for j in index if j.get('status') in ('QUEUED','RUNNING','CANCELLING')]+[j for j in index if j.get('status') not in ('QUEUED','RUNNING','CANCELLING')][:20]
   local={'jobs':[row for j in chosen if (row:=read(self.root/'data/local-ops/jobs'/ident(j['id'])/'JOB.json',None))]}
  if plan.get('project_id')!=project:plan={'project_id':project,'steps':[]}
  bp=Blueprint(self.root).snapshot(project);recipes=Recipes(self.root).listing();recovery=RecoveryDesk(self.root).snapshot(project)
  usage=UsageLedger(self.root).snapshot(project);stations={s:{'station':s,'artifacts':[],'next_dependency':None} for s in STATIONS}
  for s in plan.get('steps',[]):
   station=s.get('station') or {'sequence':'story','listening':'sound-design','motion':'editing','picture':'editing','human':'review-delivery','technical':'media'}.get(s.get('gate'),'analysis')
   if station not in stations:continue
   stations[station]['artifacts'].append({'type':'checkpoint','id':s['id'],'title':s['title'],'status':s['status'],'note':limited(s.get('note'),300),'evidence':s.get('evidence',[])[:3]})
   if s['status'] not in ('verified','awaiting_review') and not stations[station]['next_dependency']:stations[station]['next_dependency']=s['title']
  row=bp['blueprint']
  if row:
   e=row['contract']['edit'];stations['story']['timeline']=[{k:s.get(k) for k in ('id','start_frame','end_frame','source_id','purpose','technique_phase')} for s in e['shots']][:240];stations['story']['duration_frames']=e['duration_frames']
   stations['sound-design']['dialogue']=[{k:q.get(k) for k in ('id','speaker','text','start_frame','end_frame')} for q in e.get('dialogue',[])][:60]
   stations['editing']['captions']=[{k:q.get(k) for k in ('id','text','style_id','look','start_frame','end_frame')} for q in e.get('captions',[])][:60]
  for job in local.get('jobs',[]):
   if not project or job.get('project_id')!=project:continue
   for step in job.get('steps',[]):
    operation=step['operation'];station='sound-design' if operation.startswith('audio') else 'analysis' if operation in ('frames','detect_events') else 'review-delivery' if operation in ('verify_render','review_copy','register_preview') else 'media'
    if len(stations[station]['artifacts'])>=18:continue
    files=step.get('outputs',[]);picture=next((n for n in files if n.startswith('contact-') and n.endswith('.jpg')),None)
    stations[station]['artifacts'].append({'type':'local','id':job['id']+':'+step['id'],'title':operation,'status':step['status'],'note':limited(step.get('report',{}).get('summary')),'image_url':'/api/local-ops/artifact?job='+job['id']+'&step='+step['id']+'&file='+picture if picture else None,'cached':step.get('cached',False)})
    if self.runtime and operation=='audio_measure' and step['status']=='COMPLETED' and 'waveform.json' in files and 'waveform' not in stations[station]:
     try:
      path=self.runtime.local_ops.artifact(job['id'],step['id'],'waveform.json')
      if path.stat().st_size<=8*1024*1024:
       peaks=load(path).get('peaks',[]);stride=max(1,math.ceil(len(peaks)/200))
       stations[station]['waveform']={'source_job':job['id'],'source_step':step['id'],'peaks':[[peaks[i][0],max(p[1] for p in peaks[i:i+stride])] for i in range(0,len(peaks),stride)],'label':'Measured PCM peak envelope; not listening or score-isolation approval'}
     except (OSError,ValueError,KeyError,TypeError):pass
  from previews import PreviewCatalog
  preview=next((p for p in PreviewCatalog(self.root).listing()['previews'] if p.get('project_id')==project and p.get('kind')=='full'),None)
  stations['review-delivery']['preview']={k:preview.get(k) for k in ('id','title','revision')} if preview else None
  return {'version':VERSION,'project_id':project,'revision':plan.get('revision'),'blueprint':bp,'recipes':recipes,'usage':usage,'recovery':recovery,'local_evidence':local_evidence(self.root,local),'stations':stations,'model_calls_for_read':0}

def context(root,project=None,station=None):
 """Pointers and hashes only: every station shares one revision, not full chats."""
 root=Path(root);project=project or project_of(root).get('project_id');bp=Blueprint(root).snapshot(project)['blueprint'] if project else None
 recipes=Recipes(root).listing()['recipes'];approved=[{'id':r['id'],'name':r['name'],'hash':r['hash'],'path':str(Path('data/treatment-recipes')/r['id']/'RECIPE.json')} for r in recipes if r['approved'] and (not station or r['station']==station)]
 return {'workflow_upgrade':VERSION,'read_first':'shared/PRODUCTION_WORKBENCH_WORKFLOW.md','blueprint':{'path':str(Path('data/blueprints')/project/'CURRENT.json'),'hash':bp['hash'],'revision':bp['revision'],'structural_pass':bp['structural_pass']} if bp else None,'approved_methods':approved[:10],'authority':'Frozen task context. Reread blueprint before writes; stale hash requires re-handoff. Recipes are methods, not source scenes. No model evaluations enabled.'}

def task_context(root,task):
 """Deliver actual bounded content to tool-less workers, not unreadable pointers."""
 value=context(root,task.get('project_id'),task['station']);ref=value.get('blueprint')
 from future_delegation import policy
 value['project_delegation']=policy(root,task['project_id']) if task.get('project_id') else {'enabled':False,'instruction':'No project delegation authorized by an unlinked task.'}
 if not ref:return value
 bp=Blueprint(root).snapshot(task['project_id'])['blueprint'];c=bp['contract'];e=c['edit'];selected=task.get('blueprint_shot_ids') or [s['id'] for s in e['shots']]
 if not isinstance(selected,list) or any(i not in {s['id'] for s in e['shots']} for i in selected):raise ValueError('Select actual blueprint shot IDs for this worker')
 quotes=[q for q in e.get('dialogue',[]) if set(q.get('shot_ids') or [q.get('shot_id')])&set(selected)]
 linked=set(selected)|{s for q in quotes for s in (q.get('shot_ids') or [q.get('shot_id')])}
 shots=[s for s in e['shots'] if s['id'] in linked];source_ids={s['source_id'] for s in shots};quote_ids={q['id'] for q in quotes}
 captions=[t for t in e.get('captions',[]) if t.get('quote_id') in quote_ids]
 method_ids=set(task.get('recipe_ids') or [])|{t.get('style_id') for t in captions if not t.get('look')}-{None}
 methods=[r for r in Recipes(root).listing()['recipes'] if r['id'] in method_ids and r['approved']]
 if method_ids-{m['id'] for m in methods}:raise ValueError('Requested recipe is missing/unapproved; supply a custom look or obtain Tony’s method approval')
 brief={'revision':bp['revision'],'blueprint_hash':bp['hash'],'structural_pass':bp['structural_pass'],'fps':e['fps'],'duration_frames':e['duration_frames'],'sources':{k:v for k,v in e['sources'].items() if k in source_ids},'shots':shots,'dialogue':quotes,'captions':captions,'music':c.get('music',{}),'ending':c.get('ending',{}),'accents':[a for a in c.get('accents',[]) if a.get('shot_id') in linked],'approved_methods':methods,'limits':'Supplied plan and approved procedures, not proof of perception or execution. Diagnose mismatches for the director; never silently change the shared plan.'}
 if task['station']=='media':brief={k:brief[k] for k in ('revision','blueprint_hash','sources','music','ending','limits')}
 if len(json.dumps(brief,ensure_ascii=False))>12000:raise ValueError('Blueprint delivery exceeds 12k characters. Assign bounded blueprint_shot_ids/recipe_ids; do not dump the whole edit into every worker.')
 value['station_brief']=brief
 return value

def action(root,name,data=None,*,runtime=None,human=False):
 data=data or {};project=data.get('project_id') or project_of(root).get('project_id')
 if name=='status':return Workbench(root,runtime).snapshot(project)
 if name=='blueprint':return Blueprint(root).snapshot(project)
 if name=='save_blueprint':return Blueprint(root).update(data)
 if name=='recipes':return Recipes(root).listing()
 if name=='propose_recipe':return Recipes(root).propose(data)
 if name=='approve_recipe':return Recipes(root).approve(data,human=human)
 if name=='recovery':return RecoveryDesk(root).snapshot(project)
 if name=='save_recovery':return RecoveryDesk(root).record(data)
 if name=='consult_recovery':return RecoveryDesk(root).consult(runtime,data)
 if name=='usage':return UsageLedger(root).snapshot(project)
 raise ValueError('Unknown production workbench action')

def call_event(root,key,provider,model,role,status='running',usage=None,**extra):
 plan=project_of(root)
 ledger=UsageLedger(root);prior=read(ledger.path,{}).get(key,{})
 ledger.record(key,project_id=prior.get('project_id') or extra.pop('project_id',None) or plan.get('project_id'),revision=prior.get('revision') or plan.get('revision'),provider=provider,model=model,role=role,status=status,usage=usage,**{k:v for k,v in extra.items() if k!='project_id'})
