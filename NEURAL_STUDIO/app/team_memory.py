"""Persistent shared team knowledge. Local records only: no inference or dispatch."""
import hashlib
import json
import re
import threading
from pathlib import Path
from operations import load,save,stamp
from workflows import WorkflowProfiles

LOCK=threading.RLock()
TERMINAL={'FAILED','BLOCKED','UNKNOWN','INTERRUPTED','CHANGES_REQUESTED'}


def valid(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):
        raise ValueError('Invalid team project/workflow identifier')
    return value


class TeamMemory:
    def __init__(self,root):
        self.root=Path(root).resolve();self.base=self.root/'data/team'

    def workflow(self):return WorkflowProfiles(self.root).snapshot()['id']

    def path(self,project,workflow):return self.base/valid(workflow)/'projects'/(valid(project)+'.json')

    def read(self,project,workflow=None):
        workflow=workflow or self.workflow()
        try:return load(self.path(project,workflow))
        except FileNotFoundError:
            m={'project_id':project,'workflow_id':workflow,'goal':'','title':project,'revisions':{},'outcomes':{},'notes':[],'recoveries':{}}
            try:
                p=load(self.root/'data/projects'/valid(project)/'PROJECT.json')
                if p.get('workflow_id','tuf')==workflow:m.update(title=str(p.get('name') or project)[:200],goal=str(p.get('brief',''))[:4000])
            except (OSError,ValueError):pass
            return m

    def commit(self,memory,event):
        memory['updated_at']=stamp();save(self.path(memory['project_id'],memory['workflow_id']),memory)
        folder=self.base/memory['workflow_id'];folder.mkdir(parents=True,exist_ok=True)
        with (folder/'EVENTS.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'at':memory['updated_at'],'project_id':memory['project_id'],**event},ensure_ascii=False)+'\n')

    def message(self,data,*,sender='Director',job=None,workflow=None,attribution=None):
        """Reported communication. Host supplies sender identity; this never dispatches work."""
        project=valid(job['project_id'] if job else data.get('project_id'));workflow=workflow or self.workflow()
        kind=data.get('kind','finding');text=data.get('text','')
        if kind not in ('finding','help','reply','decision') or not isinstance(text,str) or not 1<=len(text.strip())<=1600:
            raise ValueError('Use a bounded finding/help/reply/decision message')
        recipient=data.get('to','Director')
        if recipient not in {'Director','team','media','analysis','story','sound-design','editing','review-delivery','Lumen'}:
            raise ValueError('Choose Director, team, Lumen or a station recipient')
        reply=data.get('reply_to') or None;source=str(data.get('source') or '')
        if source:
            p=(self.root/source).resolve()
            if not p.is_relative_to(self.root) or not p.is_file():raise ValueError('Message evidence must exist inside Neural')
            source=p.relative_to(self.root).as_posix()
        row={'from':str(sender)[:120],'to':recipient,'kind':kind,'text':text.strip(),
             'job_id':job.get('id') if job else None,'station':job.get('station') if job else data.get('station'),
             'source':source,'reply_to':reply,'reported':True}
        row['id']=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:32]
        attr=attribution if isinstance(attribution,dict) else {}
        if job:
            prov,mod,aid,aname,role=job.get('provider'),job.get('model'),job.get('agent_id'),job.get('agent_name') or str(sender)[:120],'specialist'
        elif attr:
            prov,mod=attr.get('provider'),attr.get('model')
            aid=attr.get('profile_id') or attr.get('agent_id') or ('tony' if str(sender)=='Tony' else 'director')
            aname=attr.get('agent_name') or str(sender)[:120]
            role=attr.get('role') or ('human' if str(sender)=='Tony' else 'director')
        else:
            human=str(sender)=='Tony'
            prov,mod,aid,aname,role=('human' if human else None),None,('tony' if human else 'director'),str(sender)[:120],('human' if human else 'director')
        row.update(project_id=project,provider=prov,model=mod,agent=aname,agent_name=aname,agent_id=aid,role=role)
        with LOCK:
            m=self.read(project,workflow);messages=m.setdefault('messages',[])
            if reply and not any(r['id']==reply for r in messages):raise ValueError('Reply must reference a message in this project channel')
            existing=next((r for r in messages if r['id']==row['id']),None)
            if existing:return existing
            row['at']=stamp();messages.append(row);m['messages']=messages[-200:]
            self.commit(m,{'kind':'team_message','message':row})
        return row

    def channel(self,project=None,workflow=None):
        view=self.snapshot(project,workflow)
        return {'project':view.get('project'),'paused':view.get('paused'),
                'messages':view.get('messages',[]),'open_help':view.get('open_help',[]),'model_calls':0}

    def worker_message(self,data):
        """File/tool-capable workers can report during their owned job. No invented sender field."""
        job=load(self.root/'data/jobs'/valid(data.get('job_id'))/'JOB.json')
        if job.get('status')!='RUNNING':raise ValueError('Only the current running task owner can post a worker message')
        task_path=self.root/'stations'/valid(job['station'])/'tasks'/valid(job['task_id'])/'TASK.json'
        task=load(task_path)
        if hashlib.sha256(task_path.read_bytes()).hexdigest()!=job.get('task_sha256'):raise ValueError('Task changed after dispatch')
        if data.get('task_sha256')!=job.get('task_sha256') or not job.get('task_sha256'):
            raise ValueError('Worker must supply its exact assigned task hash')
        return self.message(data,sender=job.get('agent_name') or job['station'],job=job,workflow=task.get('workflow',{}).get('id','tuf'))

    def production(self,plan):
        if not plan or not plan.get('project_id'):return
        with LOCK:
            workflow=plan.get('workflow_id') or self.workflow();m=self.read(plan['project_id'],workflow)
            try:p=load(self.root/'data/projects'/plan['project_id']/'PROJECT.json')
            except (OSError,ValueError):p={}
            m.update(title=str(p.get('name') or plan.get('title') or m['title'])[:200],goal=str((p.get('brief') if p.get('workflow_id','tuf')==workflow else None) or plan.get('scope') or '')[:4000],current_scope=str(plan.get('scope',''))[:2200],revision=plan['revision'])
            row={'at':plan.get('updated_at'),'title':plan.get('title'),'source':plan.get('_memory_source','data/production/CURRENT.json'),
                 'preview_id':plan.get('review_preview_id'),'checks':[{k:s.get(k) for k in ('id','title','status','gate','owner','note')} for s in plan.get('steps',[])],
                 'recorded_human_acceptance':any(s.get('gate')=='human' and s.get('status')=='verified' for s in plan.get('steps',[]))}
            if m['revisions'].get(plan['revision'])==row:return
            m['revisions'][plan['revision']]=row
            # Older revisions remain in production/history and the event journal.
            m['revisions']=dict(list(m['revisions'].items())[-40:])
            self.commit(m,{'kind':'production_checkpoint','revision':plan['revision'],'source':row['source']})

    def task(self,task):
        if not task.get('project_id'):return
        with LOCK:
            m=self.read(task['project_id'],task.get('workflow',{}).get('id','tuf'))
            if not m['goal']:
                try:
                    p=load(self.root/'data/projects'/valid(task['project_id'])/'PROJECT.json')
                    m.update(title=str(p.get('name') or m['title'])[:200],goal=str(p.get('brief',''))[:4000])
                except (OSError,ValueError):pass
            self.commit(m,{'kind':'task_created','task_id':task['id'],'station':task['station'],'title':task['title']})

    def job(self,job,historical=False):
        """Record status transitions, supplied results, explicit requests for help."""
        if not job.get('project_id'):return
        station=job.get('station');task_id=job.get('task_id')
        task={};result={}
        if station and task_id:
            folder=self.root/'stations'/valid(station)/'tasks'/valid(task_id)
            try:task=load(folder/'TASK.json')
            except (OSError,ValueError):pass
            p=folder/'RESULT.json'
            if p.is_file() and p.stat().st_size<=256000:
                try:result=load(p)
                except (OSError,ValueError):pass
        workflow=task.get('workflow',{}).get('id') or self.workflow()
        row={k:job.get(k) for k in ('id','task_id','station','agent_id','agent_name','provider','model','title','status','error','process_stopped','idle_inference','recovery_of','project_revision')}
        row['reported_summary']=str(result.get('summary') or '')[:1200]
        limits=result.get('limitations',[])
        row['limitations']=[str(v)[:500] for v in limits[:8]] if isinstance(limits,list) else ['Malformed limitation report; inspect RESULT.json']
        row['source']='data/jobs/'+job['id']+'/JOB.json'
        row['evidence_status']='Worker-reported outcome / structural task review; not artistic approval'
        with LOCK:
            m=self.read(job['project_id'],workflow)
            if m['outcomes'].get(job['id'])==row:return
            m['outcomes'][job['id']]=row;m['outcomes']=dict(list(m['outcomes'].items())[-80:])
            if job['status'] in TERMINAL or result.get('status')=='BLOCKED':
                ticket=m['recoveries'].setdefault(job['id'],{'job_id':job['id'],'status':'historical' if historical else 'needs_director','task_id':task_id,'station':station,'attempted_agent':job.get('agent_id'),'replacement_job_id':None})
                ticket.update(reason=str(job.get('error') or result.get('summary') or job['status'])[:1400],source=row['source'],execution_uncertain=job.get('idle_inference')=='unknown' or job['status']=='UNKNOWN',next_action='Director reconciles the exact failure and partial outputs, then chooses a capable alternate for a NEW scoped task. Do not replay UNKNOWN or start competing native editors.')
                m['recoveries']=dict(list(m['recoveries'].items())[-40:])
            if job.get('recovery_of'):
                ticket=m['recoveries'].get(job['recovery_of'])
                if ticket:
                    ticket.update(replacement_job_id=job['id'],status='replacement_failed' if job['status'] in TERMINAL else 'awaiting_review' if job['status']=='REVIEW_REQUIRED' else 'resolved_structurally' if job['status']=='APPROVED' else 'assigned')
            self.commit(m,{'kind':'worker_status','job_id':job['id'],'status':job['status'],'source':row['source']})
        if historical:return
        if job['status'] in TERMINAL or result.get('status')=='BLOCKED':
            self.message({'kind':'help','text':str(job.get('error') or result.get('summary') or job['status'])[:1600],
                          'to':'Director','source':row['source'] if (self.root/row['source']).is_file() else ''},
                         sender=job.get('agent_name') or station,job=job,workflow=workflow)
        if job['status'] not in ('QUEUED','RUNNING','CANCELLING'):
            for item in (result.get('team_messages') or [])[:4] if isinstance(result.get('team_messages',[]),list) else []:
                if not isinstance(item,dict):continue
                try:self.message(item,sender=job.get('agent_name') or station,job=job,workflow=workflow)
                except ValueError:pass

    def note(self,data,workflow=None):
        project=valid(data.get('project_id'));workflow=workflow or self.workflow()
        kind=data.get('kind','finding');text=str(data.get('text','')).strip()
        if kind not in ('finding','decision','correction','help') or not 1<=len(text)<=2200:raise ValueError('Use a bounded finding/decision/correction/help note')
        source=str(data.get('source',''))
        if source:
            p=(self.root/source).resolve()
            if not p.is_relative_to(self.root) or not p.is_file():raise ValueError('Team evidence must exist inside Neural')
            source=p.relative_to(self.root).as_posix()
        station=data.get('station')
        if station and station not in {'media','analysis','story','sound-design','editing','review-delivery'}:raise ValueError('Unknown station')
        note={'kind':kind,'text':text,'station':station,'source':source,'authority':'Reported team knowledge, not automatic approval or a new assignment'}
        note['id']=hashlib.sha256(json.dumps(note,sort_keys=True).encode()).hexdigest()[:32]
        with LOCK:
            m=self.read(project,workflow)
            if not any(n['id']==note['id'] for n in m['notes']):
                note['at']=stamp();m['notes']=(m['notes']+[note])[-80:];self.commit(m,{'kind':'team_note','note':note})
        return note

    def review(self,task,decision,note,source):
        workflow=task.get('workflow',{}).get('id','tuf')
        self.note({'project_id':task['project_id'],'station':task['station'],'kind':'correction' if decision=='CHANGES_REQUESTED' else 'finding','text':decision+': '+str(note or 'Task structural review recorded'),'source':str(source)},workflow)
        with LOCK:
            m=self.read(task['project_id'],workflow)
            for row in m['outcomes'].values():
                if row['task_id']!=task['id']:continue
                row['status']=decision;row['review_source']=str(Path(source).relative_to(self.root))
                root=m['recoveries'].get(row.get('recovery_of'))
                if root:root['status']='resolved_structurally' if decision=='APPROVED' else 'replacement_failed'
                if decision=='CHANGES_REQUESTED':
                    m['recoveries'][row['id']]={'job_id':row['id'],'task_id':task['id'],'station':task['station'],'status':'needs_director','reason':str(note)[:1400],'execution_uncertain':False,'next_action':'Inspect rejected evidence and create a NEW scoped correction; retain original output.'}
            self.commit(m,{'kind':'task_review','task_id':task['id'],'decision':decision,'source':str(source)})

    def recall(self,query='',station=None,exclude=None,limit=4,workflow=None):
        workflow=workflow or self.workflow();tokens=set(re.findall(r'[a-z0-9]{3,}',str(query)[:512].lower()))
        rows=[]
        for p in sorted((self.base/valid(workflow)/'projects').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:500]:
            m=load(p)
            if m['project_id']==exclude:continue
            notes=[{**n,'text':n['text'][:700]} for n in m['notes'] if not station or n.get('station') in (None,station)][-2:]
            outcomes=[{k:str(r.get(k) or '')[:400] for k in ('station','status','title','reported_summary','error','source')} for r in m['outcomes'].values() if not station or r.get('station')==station][-3:]
            hay=(m['title']+' '+m['goal']+' '+json.dumps(notes,ensure_ascii=False)+' '+json.dumps(outcomes,ensure_ascii=False)).lower()
            score=sum(t in hay for t in tokens)
            if tokens and not score:continue
            rows.append({'project_id':m['project_id'],'title':m['title'],'goal':m['goal'][:500],
                         'revision':m.get('revision'),'notes':notes,'recorded_outcomes':outcomes,'score':score,'memory_path':p.relative_to(self.root).as_posix(),
                         'boundary':'Historical knowledge only; no task resumption or reuse of finished scenes.'})
        rows.sort(key=lambda r:-r['score'])
        return rows[:max(1,min(limit,8))]

    def snapshot(self,project=None,workflow=None):
        workflow=workflow or self.workflow()
        try:plan=load(self.root/'data/production/CURRENT.json')
        except (OSError,ValueError):plan={}
        project=project or plan.get('project_id')
        if not project:return {'workflow_id':workflow,'project':None,'model_calls':0}
        m=self.read(project,workflow)
        try:command=load(self.root/'data/command/STATE.json')
        except (OSError,ValueError):command={}
        pause=command.get('production_pause') or {}
        recent=list(m['outcomes'].values())[-12:]
        active=[r for r in m['outcomes'].values() if r['status'] in ('QUEUED','RUNNING','CANCELLING','WAITING_LOCAL')]
        tickets=[r for r in m['recoveries'].values() if r['status'] not in ('resolved_structurally','historical')][-8:]
        messages=m.get('messages',[])[-80:]
        answered={r.get('reply_to') for r in messages if r.get('kind') in ('reply','decision')}
        return {'workflow_id':workflow,'project':{k:m.get(k) for k in ('project_id','title','goal','current_scope','revision','updated_at')},
                'director':{k:command.get('leader',{}).get(k) for k in ('provider','model','status')},
                'paused':pause.get('project_id')==project,'owners':active,'recent_outcomes':recent,'recovery_handoffs':tickets,
                'messages':messages,'open_help':[r for r in messages if r['kind']=='help' and r['id'] not in answered],
                'notes':m['notes'][-12:],'revisions':[{'revision':key,**{k:r.get(k) for k in ('at','title','preview_id','recorded_human_acceptance')},'checked':sum(s['status']=='verified' for s in r['checks']),'total':len(r['checks'])} for key,r in list(m['revisions'].items())[-8:]],
                'earlier_projects':self.recall(exclude=project,limit=3,workflow=workflow),'model_calls':0,
                'policy':'One shared goal; named task owners; reported findings stay distinct from verified evidence and final human acceptance. No automatic model call, polling or replay.'}

    def director_brief(self,project=None):
        view=self.snapshot(project)
        if not view.get('project'):return view
        return {'project':{k:str(v or '')[:700] for k,v in view['project'].items()},'paused':view['paused'],'director':view['director'],
                'owners':[{k:r.get(k) for k in ('id','station','agent_name','status','title')} for r in view['owners'][:6]],
                'help_needed':[{k:str(r.get(k) or '')[:350] for k in ('job_id','station','reason','status','replacement_job_id')} for r in view['recovery_handoffs'][-3:]],
                'team_channel':{'recent':[{k:str(r.get(k) or '')[:350] for k in ('id','from','to','kind','text','reply_to','source','provider','model','role')} for r in view.get('messages',[])[-3:]],'open_help':[{k:str(r.get(k) or '')[:350] for k in ('id','from','to','text','provider','model','role')} for r in view.get('open_help',[])[-3:]]},
                'earlier_edits':[{k:r.get(k) for k in ('project_id','title','revision','memory_path')} for r in view['earlier_projects']],
                'project_memory':self.path(view['project']['project_id'],view['workflow_id']).relative_to(self.root).as_posix(),
                'read_protocol':'shared/TEAMWORK_PROTOCOL.md','model_calls':0}

    def bootstrap(self,station='analysis'):
        registry=load(self.root/'REGISTRY.json')
        definition=next((r for r in registry['stations'] if r['id']==station),None)
        if not definition:raise ValueError('Unknown station')
        workflow=WorkflowProfiles(self.root).snapshot(station)
        skills=[]
        for name in definition['skills']:
            p=self.root/'knowledge/skills'/name/'SKILL.md'
            skills.append({'entrypoint':p.relative_to(self.root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        current=self.snapshot().get('project') or {}
        return {'orientation_only':True,'workflow':workflow,'station':station,'skills':skills,
                'read_first':['shared/NEW_MODEL_TEAM_BOOTSTRAP.md','shared/TEAMWORK_PROTOCOL.md',f'stations/{station}/START_HERE.md'],
                'team':self.worker_context({'station':station,'workflow':workflow,'project_id':current.get('project_id')}),
                'authority':'Orientation only. Wait for an explicit task; do not resume a remembered edit.','model_calls':0}

    def worker_context(self,task):
        workflow=task.get('workflow',{}).get('id','tuf')
        view=self.snapshot(task.get('project_id'),workflow) if task.get('project_id') else {'project':None,'owners':[],'recovery_handoffs':[],'notes':[],'paused':False}
        view={k:view.get(k) for k in ('project','paused','owners','recovery_handoffs','notes','messages','open_help')}
        view['messages']=(view.get('messages') or [])[-6:]
        view['open_help']=(view.get('open_help') or [])[-3:]
        revision=(view.get('project') or {}).get('revision')
        memory=self.read(task['project_id'],workflow) if task.get('project_id') else {'outcomes':{}}
        view['peer_results']=[{k:str(r.get(k) or '')[:500] for k in ('task_id','station','status','reported_summary','source','project_revision')} for r in memory['outcomes'].values() if r.get('project_revision')==revision and revision and r['status'] not in ('QUEUED','RUNNING','CANCELLING','WAITING_LOCAL')][-4:]
        view['owners']=(view['owners'] or [])[:6]
        view['recovery_handoffs']=(view['recovery_handoffs'] or [])[-3:]
        view['notes']=[n for n in (view['notes'] or []) if n.get('station') in (None,task['station'])][-3:]
        view['earlier_projects']=self.recall(station=task['station'],exclude=task.get('project_id'),limit=2,workflow=workflow)
        view['team_protocol']='Work toward the project goal through this exact assigned task. Other owners retain their work; do not overwrite or duplicate them. Send findings/help/reply via team_messages in your final response (max4; kind/to/text/reply_to). Read supplied peer messages; reply to the actual message id when asked for a consultation. Describe failed approach, partial evidence and specific help needed. Never hide failure as COMPLETED or invent a peer answer. The director records decisions in the visible channel and assigns scoped consultations/replacements; peers cannot launch each other or claim native ownership. Remember earlier lessons, never copy old completed scenes.'
        # Bound delivery, not storage: full project records stay recallable locally.
        while len(json.dumps(view,ensure_ascii=False))>10000:
            if view['messages']:view['messages'].pop(0)
            elif view['open_help']:view['open_help'].pop(0)
            elif view['earlier_projects']:view['earlier_projects'].pop()
            elif view['notes']:view['notes'].pop(0)
            elif view['recovery_handoffs']:view['recovery_handoffs'].pop(0)
            elif view['owners']:view['owners'].pop(0)
            elif view['peer_results']:view['peer_results'].pop(0)
            else:raise ValueError('Project goal exceeds the team context budget')
        return view

    def replacement(self,old,task,reason):
        if old.get('project_id')!=task.get('project_id') or old.get('station')!=task.get('station'):raise ValueError('Replacement must match project and station')
        if old.get('workflow_id') and old['workflow_id']!=task.get('workflow',{}).get('id','tuf'):raise ValueError('Replacement must retain the failed task workflow')
        if old.get('status') not in TERMINAL:raise ValueError('Only a failed/blocked/rejected task can be handed to a replacement')
        # A job that failed before any provider launch has no remote execution to reconcile (8 Nov 2026 fix).
        never_launched=not old.get('provider_launch_attempted') and old.get('idle_inference') is None and old.get('status') in ('FAILED','BLOCKED')
        if old.get('idle_inference')=='unknown' or old.get('status')=='UNKNOWN' or (old.get('process_stopped') is not True and not never_launched):raise ValueError('Reconcile exact prior execution before assigning a replacement')
        if old.get('task_id')==task['id'] or not isinstance(reason,str) or len(reason.strip())<15:raise ValueError('Create a NEW scoped task and record what the alternate attempt will change')
        return {'job_id':old['id'],'reason':reason[:1200],'source':str(self.root/old.get('source','data/jobs/'+old['id']+'/JOB.json'))}

    def seed(self):
        """One local migration of real metadata. Never resumes old work."""
        with LOCK:
            marker=self.base/'SEED.json'
            if marker.exists():return load(marker)
            projects=0;revisions=0;jobs=0
            for p in sorted((self.root/'data/projects').glob('*/PROJECT.json'))[:150]:
                row=load(p);wid=row.get('workflow_id','tuf');m=self.read(row['id'],wid)
                m.update(title=str(row.get('name') or row['id'])[:200],goal=str(row.get('brief',''))[:4000])
                self.commit(m,{'kind':'import_project_metadata','source':p.relative_to(self.root).as_posix()});projects+=1
            for p in sorted((self.root/'data/production/history').glob('*.json'))[-150:]:
                row=load(p);self.production({**row,'workflow_id':row.get('workflow_id','tuf'),'_memory_source':p.relative_to(self.root).as_posix()});revisions+=1
            p=self.root/'data/production/CURRENT.json'
            if p.exists():self.production(load(p));revisions+=1
            for p in sorted((self.root/'data/jobs').glob('*/JOB.json'),key=lambda p:p.stat().st_mtime)[-400:]:
                row=load(p)
                if row.get('project_id'):self.job(row,historical=True);jobs+=1
            result={'at':stamp(),'projects':projects,'revision_records':revisions,'worker_records':jobs,'model_calls':0,'policy':'Historical failures are archived, not automatic retry requests. Original projects/media untouched.'}
            save(marker,result);return result
