"""Loopback-only Neural Posthouse app and bounded worker API."""
from __future__ import annotations
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
import argparse
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import threading
import uuid
import zipfile
import atexit
import subprocess
import sys
import time
from district import DistrictStore
from previews import PreviewCatalog

ROOT = Path(__file__).resolve().parents[1]
def now():return datetime.now(timezone.utc).isoformat()
def read_json(p):return json.loads(p.read_text(encoding='utf-8'))
_DIGESTS={}
def digest(p):
    """Streamed SHA-256, cached by (path,size,mtime): large media evidence never loads whole into memory (8 Nov 2026 MemoryError fix)."""
    st=p.stat();key=(str(p),st.st_size,st.st_mtime_ns)
    hit=_DIGESTS.get(key)
    if hit:return hit
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    if len(_DIGESTS)>20000:_DIGESTS.clear()
    _DIGESTS[key]=h.hexdigest();return _DIGESTS[key]
def atomic(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    temporary=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    for attempt in range(8):
        try:temporary.replace(p);break
        except PermissionError:
            if attempt==7:raise
            time.sleep(.015*(attempt+1))
def within(base,p):
    base=base.resolve();p=p.resolve()
    if not p.is_relative_to(base):raise ValueError('Path is outside the permitted folder')
    return p

class Store:
    def __init__(self,root=ROOT):
        self.root=Path(root).resolve();from workflows import WorkflowProfiles;self.workflows=WorkflowProfiles(self.root);self.registry=read_json(self.root/'REGISTRY.json')
        self.stations={s['id']:s for s in self.registry['stations']};self.lock=threading.RLock();self.district=DistrictStore(self.root)
    def folder(self,station):
        if station not in self.stations:raise ValueError('Unknown station')
        return within(self.root/'stations',self.root/'stations'/station)
    def task_folder(self,station,task_id):
        if not re.fullmatch(r'[a-f0-9]{32}',str(task_id)):raise ValueError('Invalid task ID')
        folder=within(self.folder(station)/'tasks',self.folder(station)/'tasks'/task_id)
        if not (folder/'TASK.json').is_file():raise ValueError('Task not found')
        return folder
    def station(self,station):
        folder=self.folder(station);definition=self.stations[station]
        return {**definition,'folder':str(folder),'entrypoint':str(folder/'START_HERE.md'),
            'bootstrap':(folder/'BOOTSTRAP_PROMPT.txt').read_text(encoding='utf-8'),
            'entry_text':(folder/'START_HERE.md').read_text(encoding='utf-8'),
            'handoff_text':(folder/'HANDOFF.md').read_text(encoding='utf-8'),
            'contract':read_json(folder/'CONTRACT.json'),'tasks':self.list_tasks(station),
            'skills_manifest':[{ 'name':n,'entrypoint':str(self.root/'knowledge'/'skills'/n/'SKILL.md'),
                'sha256':digest(self.root/'knowledge'/'skills'/n/'SKILL.md')} for n in definition['skills']]}
    def create_task(self,station,payload):
        with self.lock:
            title=str(payload.get('title','')).strip();brief=str(payload.get('brief','')).strip()
            if not title or not brief:raise ValueError('A task title and actionable brief are required')
            if len(title)>160 or len(brief)>12000:raise ValueError('Task text is too long')
            inputs=payload.get('inputs',[])
            if not isinstance(inputs,list) or len(inputs)>50:raise ValueError('Inputs must be a list of at most 50 local paths')
            inspected=[]
            for raw in inputs:
                if isinstance(raw, dict):
                    raw_path = str(raw.get('path', '')).strip().strip('"')
                    is_opt = bool(raw.get('optional', False))
                elif isinstance(raw, str):
                    raw_path = raw.strip().strip('"')
                    is_opt = False
                else:
                    raise ValueError('Invalid input path')
                if not raw_path or len(raw_path) > 2000: raise ValueError('Invalid input path')
                p = Path(raw_path).expanduser()
                # Metadata-only source check. No decoding, file copying or expensive media hash.
                absolute = p.is_absolute(); exists = absolute and p.is_file()
                inspected.append({'path': str(p), 'exists': exists, 'bytes': p.stat().st_size if exists else None, 'content_inspected': False, 'optional': is_opt})
            definition=self.stations.get(station)
            if not definition:raise ValueError('Unknown station')
            parent=payload.get('parent_task_id')
            if parent:self.task_folder(station,parent)
            from staffing import requirements
            required=sorted(requirements(payload.get('required_capabilities',['text'])))
            context_mode=payload.get('context_mode','persistent')
            if context_mode not in ('persistent','fresh_review'):
                raise ValueError('Unknown station context_mode')
            if context_mode=='fresh_review':
                from fresh_review import target
                review_target=target(payload.get('review'))
                revision=payload.get('project_revision')
                if not isinstance(revision,str) or not revision.strip() or len(revision)>160:
                    raise ValueError('Fresh review requires an explicit project_revision')
            executor=payload.get('executor')
            if executor:
                if executor=='gemini-3.8-flash':raise ValueError('No verified tool-equipped Gemini station executor exists; gemini-3.8-flash executor is not supported here (the Lumen route is the Gemini editing path). Use sonnet or haiku.')
                if executor not in ('sonnet','haiku'):raise ValueError('Executor must be sonnet or haiku')
                if context_mode=='fresh_review':raise ValueError('A fresh review can never be a tool-equipped executor task')
                pid=payload.get('project_id')
                if not isinstance(pid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',pid):raise ValueError('An executor task needs a valid project_id (its work folder)')
            skill_target=payload.get('skill_target')
            if skill_target:
                if not executor:raise ValueError('skill_target needs an executor task')
                if not isinstance(skill_target,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,79}',skill_target) or not (self.root/'knowledge/skills'/skill_target/'SKILL.md').is_file():
                    raise ValueError('skill_target must name an existing knowledge/skills/<name>/SKILL.md')
            task_id=uuid.uuid4().hex;folder=self.folder(station)/'tasks'/task_id;folder.mkdir(parents=True);(folder/'outputs').mkdir()
            task={'version':1,'id':task_id,'station':station,'created_at':now(),'title':title,'brief':brief,
                'worker_hint':str(payload.get('worker_hint','Unassigned')).strip()[:160],
                'project':'shared/PROJECT_BRIEF.md','inputs':inspected,'parent_task_id':parent,
                'readiness':'READY_FOR_WORKER' if (inspected and all(x['exists'] or x.get('optional') for x in inspected)) or (not inspected and payload.get('kind')=='planning') else 'NEEDS_INPUT',
                'kind':'planning' if payload.get('kind')=='planning' else 'evidence',
                'project_id':payload.get('project_id'),
                'upstream':payload.get('upstream'),
                'adapter':'NOT_CONNECTED','worker_accepted':False,
                'skills':[f'knowledge/skills/{n}/SKILL.md' for n in definition['skills']],
                'primary_output':definition['output'],'required_fields':definition['fields'],
                'native_write_authorized':False,
                'authority':'Preparation task only. Native mutation needs a separate explicit live-project assignment.',
                'output_protocol':'shared/OUTPUT_PROTOCOL.md'}
            task['workflow']=self.workflows.snapshot(station)
            task['required_capabilities']=required
            if executor:task['executor']=executor
            if skill_target:task['skill_target']=skill_target
            if context_mode=='fresh_review':
                task.update(context_mode=context_mode,review=review_target,
                            skills=[],required_fields=['goldfish_review'])
            from continuity import station_memory
            task['shared_memory']=json.loads(station_memory(self.root,task))
            from production_workbench import task_context
            for key in ('blueprint_shot_ids','recipe_ids'):
                if key in payload:
                    if not isinstance(payload[key],list) or any(not isinstance(v,str) for v in payload[key]):raise ValueError('Use explicit blueprint shot/recipe ID lists')
                    task[key]=payload[key]
            task['production_context']=task_context(self.root,task)
            blueprint=task['production_context'].get('blueprint')
            if blueprint:
                atomic(folder/'BLUEPRINT.json',read_json(self.root/blueprint['path']))
                task['production_context']['frozen_blueprint_file']='BLUEPRINT.json'
            methods=task['production_context'].get('approved_methods',[])
            if methods:
                atomic(folder/'TREATMENT_METHODS.json',[read_json(self.root/m['path']) for m in methods])
                task['production_context']['frozen_methods_file']='TREATMENT_METHODS.json'
            atomic(folder/'PRODUCTION_CONTEXT.json',task['production_context'])
            from team_memory import TeamMemory
            team=TeamMemory(self.root)
            task['team_context']=team.worker_context(task)
            task['project_revision']=(task['team_context'].get('project') or {}).get('revision')
            if task.get('context_mode')=='fresh_review':
                task['project_revision']=revision
            context_bytes=json.dumps(task['team_context'],sort_keys=True,ensure_ascii=False).encode('utf-8')
            task['team_context_sha256']=hashlib.sha256(context_bytes).hexdigest()
            atomic(folder/'TEAM_CONTEXT.json',task['team_context'])
            atomic(folder/'TASK.json',task)
            team.task(task)
            prompt=f"You are assigned to Neural Studio / {definition['name']}.\nRead this task entrypoint first: {folder/'START_HERE.md'}\nThen read TASK.json and every required file/skill listed there.\nThe station instructions live at {self.folder(station)/'START_HERE.md'}.\nDo only task {task_id}: {title}.\nConfirm source/tool/media access; write ACCEPTANCE.json with the TASK.json SHA-256 and actual skills_read.\nIf blocked, save a truthful BLOCKED result. Save outputs under {folder/'outputs'} and RESULT.json last.\nDo not alter originals, paused production, or AE. Stop model activity after your terminal result.\nThis prompt does not supply Codex-only tools or authorize native edits.\n"
            (folder/'KICKOFF_PROMPT.txt').write_text(prompt,encoding='utf-8')
            for entry in ['AGENTS.md','GEMINI.md','CLAUDE.md']:
                (folder/entry).write_text('Read START_HERE.md and TASK.json in this task directory before work. Follow the station entrypoint, current shared rules, required skills and output protocol. Do not infer native permissions, resume legacy projects or continue inference after writing a terminal result.\n',encoding='utf-8')
            (folder/'START_HERE.md').write_text(f"# Task {task_id}\n\n{title}\n\n## Read order\n1. TASK.json beside this file (human brief, inputs, required skills and output fields).\n2. ../../START_HERE.md and ../../HANDOFF.md (station onboarding).\n3. ../../../../shared/CURRENT_RULES.md, PROJECT_BRIEF.md and OUTPUT_PROTOCOL.md.\n4. Required relevant SKILL.md files under ../../../../knowledge/skills/ and their referenced resources.\n\n## Assignment\n{brief}\n\nA packet alone does not launch a worker. Readiness is {task['readiness']}; inspect missing inputs before accepting. Inputs are references only; no real media has been inspected by creating this packet.\n\nTASK.json SHA-256: {digest(folder/'TASK.json')}\n\n## Output\nWrite outputs/{definition['output']} with required fields {', '.join(definition['fields'])}. Place evidence only under outputs/. Write RESULT.json last using shared/OUTPUT_PROTOCOL.md. Check capabilities, preserve private media and never claim unsupported playback/listening. No live native edit is authorized by this packet.\n",encoding='utf-8')
            with (folder/'START_HERE.md').open('a',encoding='utf-8') as note:note.write('\n## Frozen workflow instructions (override artistic recipes)\n'+task['workflow']['instructions']+'\n')
            if context_mode=='fresh_review':
                (folder/'START_HERE.md').write_text(
                    '# Fresh bounded Goldfish review\n\nThis task uses only the app-owned fresh no-tool adapter. '
                    'The host supplies the explicit review target and frozen evidence; ordinary station skills, '
                    'team history, private owner brief and saved worker conversations are excluded. '
                    'Do not treat this task as an ordinary persistent worker assignment.\n\n'
                    'Project/revision: '+str(task.get('project_id'))+'/'+task['project_revision']+
                    '\nTask SHA-256: '+digest(folder/'TASK.json')+
                    '\n\nExplicit target:\n'+json.dumps(task['review'],ensure_ascii=False,indent=2)+
                    '\n\nReport is saved under outputs/'+task['primary_output']+
                    ' as goldfish_review. It is an independent report, never human artistic acceptance. '
                    'No tools, native work, further reviewers or automatic retries are authorized.\n',encoding='utf-8')
                (folder/'KICKOFF_PROMPT.txt').write_text(
                    'Use the app-owned fresh_review adapter for this exact task. Read START_HERE.md for the bounded '
                    'target contract. Do not substitute a resumed station session, load team/station history, '
                    'or start a provider manually. The app supplies evidence and records the completion event.\n',encoding='utf-8')
            return self.task_summary(station,folder)
    def validate(self,station,folder):
        task=read_json(folder/'TASK.json');result_path=folder/'RESULT.json';errors=[]
        state=task['readiness'];acceptance=None;result=None
        receipt=folder/'ACCEPTANCE.json'
        if receipt.exists():
            try:
                acceptance=read_json(receipt)
                required=task['skills']
                if acceptance.get('task_id')!=task['id'] or acceptance.get('task_sha256')!=digest(folder/'TASK.json'):raise ValueError('Acceptance task/digest mismatch')
                if not acceptance.get('worker') or not isinstance(acceptance.get('capabilities'),dict):raise ValueError('Acceptance requires worker and capability map')
                if not all(n in acceptance.get('skills_read',[]) for n in required):raise ValueError('Read receipt omits required skills')
                if state=='READY_FOR_WORKER':state='WORKER_REPORTED_ACCEPTED'
            except (OSError,ValueError,TypeError) as e:errors.append(str(e))
        if result_path.exists():
            try:
                result=read_json(result_path)
                if result.get('task_id')!=task['id'] or result.get('task_sha256')!=digest(folder/'TASK.json'):raise ValueError('Result task/digest mismatch')
                if result.get('status') not in ['COMPLETED','BLOCKED','FAILED']:raise ValueError('Invalid result status')
                if not isinstance(result.get('summary'),str) or not result['summary'].strip():raise ValueError('Result needs a summary')
                if not isinstance(result.get('checks'),list) or not isinstance(result.get('limitations'),list):raise ValueError('Checks and limitations must be arrays')
                checks=result['checks']
                if any(not isinstance(c,dict) or c.get('result') not in ['PASS','FAIL','NOT TESTED'] or not c.get('name') for c in checks):raise ValueError('Invalid gate result')
                evidence=result.get('evidence',[])
                if not isinstance(evidence,list):raise ValueError('Evidence must be an array')
                verified=[]
                for item in evidence:
                    if not isinstance(item,dict) or not isinstance(item.get('path'),str):raise ValueError('Invalid evidence entry')
                    path=within(folder/'outputs',folder/item['path'])
                    if not path.is_file() or digest(path)!=item.get('sha256'):raise ValueError('Missing or changed evidence: '+item['path'])
                    verified.append(item['path'])
                if result['status']=='COMPLETED':
                    if not acceptance or errors:raise ValueError('Completed result needs a valid acceptance/read receipt')
                    if not evidence or not checks:raise ValueError('Completed result needs evidence and explicit checks')
                    expected='outputs/'+task['primary_output']
                    if result.get('primary_output')!=expected or expected not in verified:raise ValueError('Primary output is missing from verified evidence')
                    output=read_json(within(folder/'outputs',folder/expected))
                    if not isinstance(output,dict) or any(n not in output for n in task['required_fields']):raise ValueError('Primary output does not satisfy the role contract')
                    state='REVIEW_REQUIRED'
                    review_path=folder/'REVIEW.json'
                    if review_path.exists():
                        review=read_json(review_path)
                        if review.get('result_sha256')==digest(result_path) and review.get('decision') in ['APPROVED','CHANGES_REQUESTED']:state=review['decision']
                else:state=result['status']
            except (OSError,ValueError,TypeError,KeyError) as e:errors.append(str(e));state='INVALID_OUTPUT'
        return {'status':state,'errors':errors,'worker_reported':bool(acceptance),'result':result,'evidence_file_hashes_verified':bool(result and not errors and result.get('status')=='COMPLETED')}
    def task_summary(self,station,folder):
        task=read_json(folder/'TASK.json');checked=self.validate(station,folder)
        return {**task,**checked,'folder':str(folder),'kickoff_prompt':(folder/'KICKOFF_PROMPT.txt').read_text(encoding='utf-8')}
    def list_tasks(self,station):
        folder=self.folder(station)/'tasks'
        rows=[]
        for p in folder.iterdir():
            if p.is_dir() and (p/'TASK.json').is_file():
                try:rows.append(self.task_summary(station,p))
                except (ValueError,OSError):continue
        return sorted(rows,key=lambda r:r['created_at'],reverse=True)
    def review(self,station,task_id,decision,note):
        if decision not in ['APPROVED','CHANGES_REQUESTED']:raise ValueError('Invalid review decision')
        with self.lock:
            folder=self.task_folder(station,task_id);status=self.validate(station,folder)
            if status['status'] not in ['REVIEW_REQUIRED','CHANGES_REQUESTED']:raise ValueError('Validated evidence is required before review')
            if decision=='APPROVED' and any(c['result']=='FAIL' for c in status['result']['checks']):raise ValueError('Failed gates must be repaired before approval')
            atomic(folder/'REVIEW.json',{'decision':decision,'reviewed_at':now(),'reviewer':'local user/director action','result_sha256':digest(folder/'RESULT.json'),'note':str(note)[:4000],'artistic_approval':'Separate from structural file verification; this review is the recorded user/director decision.'})
            task=read_json(folder/'TASK.json')
            if task.get('project_id'):
                from team_memory import TeamMemory
                TeamMemory(self.root).review(task,decision,note,folder/'REVIEW.json')
            return self.task_summary(station,folder)
    def bundle(self,station,task_id=None):
        station_dir=self.folder(station);definition=self.stations[station];paths=[]
        for base in [self.root/'shared',self.root/'knowledge'/'workflow']+[self.root/'knowledge'/'skills'/name for name in sorted(set(definition['skills']+['tfx-workflow-director','tfx-state-handoff']))]:
            paths.extend(p for p in base.rglob('*') if p.is_file())
        paths.extend(p for p in station_dir.iterdir() if p.is_file())
        paths.append(self.root/'KNOWLEDGE_MANIFEST.json')
        if task_id:
            task_dir=self.task_folder(station,task_id)
            paths.extend(p for p in task_dir.rglob('*') if p.is_file())
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(set(paths)):z.write(within(self.root,p),p.relative_to(self.root).as_posix())
            if task_id:
                from team_memory import TeamMemory
                task=read_json(self.task_folder(station,task_id)/'TASK.json')
                z.writestr('TEAM_CONTEXT_CURRENT.json',json.dumps(TeamMemory(self.root).worker_context(task),indent=2,ensure_ascii=False))
            z.writestr('READ_ME_FIRST.txt',f"Start at stations/{station}/START_HERE.md.\n"+(f"Assigned task: stations/{station}/tasks/{task_id}/START_HERE.md\n" if task_id else 'No task is assigned by this role kit alone.\n')+'All included paths are bundle-relative. Original author-machine paths are historical; revalidate them. No tools, credentials or model access are installed by this archive.\n')
        return data.getvalue()

class Handler(BaseHTTPRequestHandler):
    server_version='NeuralStudio/0.5'
    def log_message(self,fmt,*args):pass
    @property
    def store(self):return self.server.store
    def send(self,status,body,kind='application/json; charset=utf-8',extra=None):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        try:self.end_headers();self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def valid_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def do_GET(self):
        if not self.valid_host():return self.send(403,{'error':'Local host only'})
        try:
            u=urlsplit(self.path);path=u.path;parts=path.strip('/').split('/');q=parse_qs(u.query)
            runtime=getattr(self.server,'runtime',None)
            local_ops=getattr(runtime,'local_ops',None) if runtime else None
            if path=='/api/local-ops' and local_ops:return self.send(200,local_ops.snapshot())
            if path=='/api/production' and runtime:
                from production import ProductionBoard
                return self.send(200,ProductionBoard(self.store.root).snapshot(runtime.local_ops.snapshot()))
            if path=='/api/attention':
                from attention import AttentionStore
                return self.send(200,AttentionStore(self.store.root).snapshot())
            if path=='/api/local-ops/capabilities' and local_ops:return self.send(200,local_ops.capabilities())
            if len(parts)==4 and parts[:3]==['api','local-ops','job'] and local_ops:return self.send(200,local_ops.job(parts[3]))
            if path=='/api/local-ops/artifact' and local_ops:return self.send_file(local_ops.artifact(q.get('job',[''])[0],q.get('step',[''])[0],q.get('file',[''])[0]))
            if path=='/api/previews':return self.send(200,PreviewCatalog(self.store.root).listing())
            if path=='/api/command/image':
                from chat_images import ChatImages
                return self.send_file(ChatImages(self.store.root).path(q.get('id',[''])[0]))
            if path=='/api/preview-media':return self.send_file(PreviewCatalog(self.store.root).media(q.get('id',[''])[0]))
            if path=='/api/command/state' and runtime and getattr(runtime,'command',None):return self.send(200,runtime.command.snapshot())
            if path=='/api/directors' and runtime and getattr(runtime,'command',None):return self.send(200,runtime.command.selector.snapshot())
            if path=='/api/cutroom/media':
                from cutroom import CutroomStore
                return self.send_file(CutroomStore(self.store.root).media(q.get('project_id',[''])[0],q.get('clip_id',[''])[0]))
            if path=='/api/cutroom/source':
                from cutroom import CutroomStore
                return self.send_file(CutroomStore(self.store.root).prepared_source(q.get('project_id',[''])[0],q.get('source_id',[''])[0]))
            if path=='/api/cutroom':
                from cutroom import CutroomStore
                pid=q.get('project_id',['default'])[0] or 'default'
                bridge=getattr(getattr(runtime,'command',None),'native_bridge',None) if runtime else None
                return self.send(200,CutroomStore(self.store.root,bridge=bridge,runtime=runtime).get(pid))
            if path=='/api/storage/status':
                from storage_policy import StoragePolicy
                sp=getattr(self.server,'storage_policy',None) or StoragePolicy(self.store.root)
                return self.send(200,sp.status(fresh=q.get('fresh',['0'])[0] in ('1','true')))
            if path=='/api/dictation/capabilities' and getattr(self.server,'dictation',None):
                return self.send(200,self.server.dictation.capabilities())
            if path=='/api/activity' and runtime:
                from local_activity import studio_activity
                return self.send(200,studio_activity(runtime))
            if path=='/api/workbench' and runtime:
                from production_workbench import Workbench
                return self.send(200,Workbench(self.store.root,runtime).snapshot(q.get('project_id',[None])[0]))
            if path=='/api/staffing' and runtime:
                from staffing import roster
                return self.send(200,roster(runtime,q.get('station',['analysis'])[0],q.get('capabilities',['text'])[0].split(','),q.get('difficulty',['standard'])[0]))
            if path in ('/api/team','/api/team/channel','/api/team/recall','/api/team/bootstrap') and runtime:
                from team_memory import TeamMemory
                team=TeamMemory(self.store.root)
                if path.endswith('/channel'):return self.send(200,team.channel(q.get('project_id',[None])[0]))
                if path.endswith('/bootstrap'):return self.send(200,team.bootstrap(q.get('station',['analysis'])[0]))
                return self.send(200,{'matches':team.recall(q.get('q',[''])[0],q.get('station',[None])[0]),'model_calls':0} if path.endswith('/recall') else team.snapshot(q.get('project_id',[None])[0]))
            if path=='/api/helper/state' and getattr(self.server,'helper',None):return self.send(200,self.server.helper.snapshot())
            if path=='/api/voice/state' and getattr(self.server,'voice',None):return self.send(200,self.server.voice.state())
            if path=='/api/apprentice/state' and runtime and getattr(runtime,'apprentice',None):return self.send(200,runtime.apprentice.snapshot())
            if path=='/api/apprentice/editor' and runtime:return self.send(200,runtime.lumen_editor.snapshot())
            if path=='/api/district/library':return self.send(200,{'items':self.store.district.library()})
            if path=='/api/district/ideas':return self.send(200,{'ideas':self.store.district.ideas()})
            if path=='/api/district/media':return self.send_file(self.store.district.media(q.get('id',[''])[0]))
            if path=='/api/state' and runtime:return self.send(200,runtime.state())
            if path=='/api/diagnostics' and runtime:return self.send(200,runtime.diagnostics())
            if len(parts)==3 and parts[:2]==['api','job'] and runtime:return self.send(200,runtime.job(parts[2]))
            if path=='/api/artifact' and runtime:
                f=runtime.artifact({k:v[0] for k,v in q.items()})
                return self.send_file(f)
            if path=='/api/config':return self.send(200,{'token':self.server.token,'root':str(self.store.root),'stations':[{k:s[k] for k in ['id','agent','name','purpose','skills']} for s in self.store.stations.values()],'adapters_connected':bool(runtime and runtime.provider['authenticated'])})
            if len(parts)==3 and parts[:2]==['api','station']:return self.send(200,self.store.station(parts[2]))
            if path=='/api/skill':
                station=q.get('station',[''])[0];name=q.get('name',[''])[0]
                if name not in self.store.stations.get(station,{}).get('skills',[]):raise ValueError('Skill is not assigned to this station')
                p=within(self.store.root/'knowledge'/'skills',self.store.root/'knowledge'/'skills'/name/'SKILL.md')
                return self.send(200,{'name':name,'text':p.read_text(encoding='utf-8'),'sha256':digest(p)})
            if path=='/api/bundle':
                station=q.get('station',[''])[0];task=q.get('task',[None])[0]
                return self.send(200,self.store.bundle(station,task),'application/zip',{'Content-Disposition':f'attachment; filename="neural-{station}-handoff.zip"'})
            if path=='/api/workflows':return self.send(200,self.store.workflows.list())
            if path=='/api/health':return self.send(200,{'ok':True,'version':'0.6.0','mode':'working local studio' if runtime else 'local filesystem packets','external_agents':bool(runtime and runtime.provider['authenticated'])})
            if path.startswith('/vendor/'):
                f=within(self.store.root/'web'/'vendor',self.store.root/'web'/path.lstrip('/'))
                if f.suffix.lower() not in ['.js','.mjs','.css','.txt'] or not f.is_file():return self.send(404,{'error':'Not found'})
                mime='text/javascript' if f.suffix.lower() in ('.js','.mjs') else ('text/css' if f.suffix.lower()=='.css' else (mimetypes.guess_type(f.name)[0] or 'text/plain'))
                return self.send(200,f.read_bytes(),mime)
            if path.startswith('/assets/reference-studio/'):
                # Same-origin studio art (Blender GLB, packed textures, HDR, backplate). Confined, suffix-whitelisted.
                f=within(self.store.root/'web'/'assets'/'reference-studio',self.store.root/'web'/path.lstrip('/'))
                kinds={'.glb':'model/gltf-binary','.png':'image/png','.jpg':'image/jpeg','.hdr':'application/octet-stream'}
                if f.suffix.lower() not in kinds or not f.is_file():return self.send(404,{'error':'Not found'})
                return self.send(200,f.read_bytes(),kinds[f.suffix.lower()])
            public={'/':'index.html','/index.html':'index.html','/world.mjs':'world.mjs','/station-ui.js':'station-ui.js','/station-ui.css':'station-ui.css','/operations-ui.js':'operations-ui.js','/operations-ui.css':'operations-ui.css','/office-ui.js':'office-ui.js','/office-ui.css':'office-ui.css','/icons.js':'icons.js','/command-ui.js':'command-ui.js','/command-ui.css':'command-ui.css'}
            public.update({**{'/'+n:n for n in ['chat-attachments.js','chat-attachments.css','voice-helper.js','voice-helper.css','usage-observatory.js','usage-observatory.css','team-room.js','team-room.css']},'/workspace-settings.js':'workspace-settings.js','/dictation-ui.js':'dictation-ui.js','/dictation-ui.css':'dictation-ui.css'})
            if path not in public:
                name=path.lstrip('/')
                if '/' not in name and '\\' not in name and Path(name).suffix.lower() in ('.js','.mjs','.css'):
                    cand=within(self.store.root/'web',self.store.root/'web'/name)
                    if cand.is_file():
                        mime='text/javascript' if cand.suffix.lower() in ('.js','.mjs') else 'text/css'
                        return self.send(200,cand.read_bytes(),mime)
                return self.send(404,{'error':'Not found'})
            f=self.store.root/'web'/public[path]
            return self.send(200,f.read_bytes(),mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
        except (ValueError,KeyError,OSError) as e:self.send(400,{'error':str(e)})
    def send_file(self,f):
        size=f.stat().st_size;start=0;end=size-1;status=200
        request=self.headers.get('Range')
        if request:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',request)
            if not match:return self.send(416,{'error':'Unsupported range'})
            start=int(match[1]);end=min(int(match[2]) if match[2] else end,end);status=206
            if start>end or start>=size:return self.send(416,{'error':'Range outside file'})
        kind=mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        if f.suffix.lower() not in ['.mp4','.mov','.webm','.wav','.mp3','.m4a','.jpg','.jpeg','.png','.webp','.json','.txt','.md','.csv']:kind='application/octet-stream'
        self.send_response(status);self.send_header('Content-Type',kind)
        self.send_header('Content-Security-Policy',"sandbox; default-src 'none'; style-src 'unsafe-inline'")
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with f.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                while remaining:
                    block=stream.read(min(65536,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
        except (ConnectionError,BrokenPipeError):pass
    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Studio-Token')!=self.server.token:
            # Drain a bounded request body before closing, so Windows does not
            # reset the connection before the caller receives the rejection.
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:length=0
            if 0<length<=100000:self.rfile.read(length)
            return self.send(403,{'error':'Local app token required'})
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':return self.send(403,{'error':'Same-origin requests only'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            path_only=urlsplit(self.path).path
            upload=path_only in ('/api/command/attachments','/api/voice/transcribe','/api/dictation/audio')
            max_body=8_100_000 if upload else (2_500_000 if path_only=='/api/cutroom/save' else 100000)
            if length<=0 or length>max_body:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length));path=urlsplit(self.path).path
            if not isinstance(data,dict):raise ValueError('Expected an object')
            if path=='/api/command/attachments':
                from chat_images import ChatImages
                return self.send(201,ChatImages(self.store.root).upload(data))
            if path=='/api/previews/register':return self.send(200,PreviewCatalog(self.store.root).register(data))
            if path=='/api/attention/acknowledge':
                from attention import AttentionStore
                return self.send(200,AttentionStore(self.store.root).acknowledge(data['id']))
            if path=='/api/district/suggest':return self.send(200,self.store.district.suggest(data))
            if path=='/api/district/idea':return self.send(200,self.store.district.update_idea(data))
            if path=='/api/district/reveal':return self.send(200,self.store.district.reveal(data.get('id','')))
            # Local speech in/out for the helper. No language-model call happens on these routes.
            voice=getattr(self.server,'voice',None)
            if voice and path.startswith('/api/voice/'):
                routes={'/api/voice/transcribe':lambda:voice.transcribe(data),'/api/voice/speak':lambda:voice.speak(data),'/api/voice/warm':lambda:voice.warm(data),'/api/voice/stop':lambda:voice.stop(data)}
                if path in routes:return self.send(200,routes[path]())
            # Local composer dictation: text goes into the draft only, never a send/model turn.
            dictation=getattr(self.server,'dictation',None)
            if dictation and path=='/api/dictation/start':return self.send(200,dictation.start(data.get('culture',''),engine_id=data.get('engine_id'),capture=data.get('capture')))
            if dictation and path=='/api/dictation/audio':return self.send(200,dictation.audio(data))
            if dictation and path=='/api/dictation/stop':return self.send(200,dictation.stop(data.get('session') or None))
            if dictation and path=='/api/dictation/poll':return self.send(200,dictation.poll(int(data.get('since') or 0),data.get('session') or None))
            runtime_ref=getattr(self.server,'runtime',None)
            if path=='/api/storage/policy':
                from storage_policy import StoragePolicy
                sp=getattr(self.server,'storage_policy',None) or StoragePolicy(self.store.root)
                return self.send(200,sp.set_policy(data))
            if path in ('/api/cutroom/save','/api/cutroom/apply','/api/cutroom/reconcile','/api/cutroom/import-preview','/api/cutroom/import-source'):
                from cutroom import CutroomStore
                bridge=getattr(getattr(runtime_ref,'command',None),'native_bridge',None) if runtime_ref else None
                cs=CutroomStore(self.store.root,bridge=bridge,runtime=runtime_ref)
                if path=='/api/cutroom/import-preview':return self.send(200,cs.import_preview(data))
                if path=='/api/cutroom/import-source':return self.send(200,cs.import_source(data))
                if path=='/api/cutroom/save':return self.send(200,cs.save(data.get('project_id'),data.get('expected_version'),data.get('timeline')))
                if path=='/api/cutroom/apply':return self.send(200,cs.apply(data))
                return self.send(200,cs.reconcile(data))
            if path=='/api/directors/select' and runtime_ref and getattr(runtime_ref,'command',None):
                return self.send(200,runtime_ref.command.selector.select(data))
            runtime=getattr(self.server,'runtime',None)
            if runtime:
                if path=='/api/workbench/action':
                    from production_workbench import action
                    name=data.get('action');return self.send(200,action(self.store.root,name,data.get('data',{}),runtime=runtime,human=name=='approve_recipe'))
                helper=getattr(self.server,'helper',None)
                if helper and path.startswith('/api/helper/'):
                    routes={'/api/helper/settings':lambda:helper.configure(data),'/api/helper/ask':lambda:helper.ask(data),'/api/helper/interrupt':helper.cancel,'/api/helper/off':lambda:(getattr(self.server,'voice',None) and self.server.voice.stop(),helper.off())[1]}
                    if path in routes:return self.send(200,routes[path]())
                if path.startswith('/api/local-ops/') and getattr(runtime,'local_ops',None):
                    if not runtime.accepting_work:raise ValueError('Studio is shutting down')
                    if path=='/api/local-ops/submit':
                        plan=runtime.local_ops.recipe(data['recipe'],data.get('args',{})) if data.get('recipe') else data['plan']
                        if not plan.get('project_id') and getattr(runtime,'command',None) and runtime.command.snapshot()['leader']['status'] in runtime.command.active:
                            from production_workbench import project_of
                            plan={**plan,'project_id':project_of(self.store.root).get('project_id')}
                        if getattr(runtime,'lumen_editor',None) and runtime.lumen_editor.owns_editor() and any(s.get('operation') in ('native_submit','native_snapshot','native_render','compile_ae') for s in plan.get('steps',[])):raise ValueError('Lumen owns the native lane. Its editor/local route records owned native jobs; another caller cannot dispatch native work here.')
                        return self.send(201,runtime.local_ops.submit(plan))
                    if path=='/api/local-ops/cancel':return self.send(200,runtime.local_ops.cancel(data['job_id']))
                if path in ('/api/workflows/save','/api/workflows/activate'):
                    with runtime.lock:
                        if getattr(runtime,'lumen_editor',None) and runtime.lumen_editor.owns_editor():raise ValueError('Lumen owns the trial editor; finish/release it before changing workflow')
                        if any(j['status'] in runtime.active_states for j in runtime.jobs()) or (getattr(runtime,'command',None) and runtime.command.snapshot()['leader']['status'] in runtime.command.active) or (getattr(runtime,'apprentice',None) and runtime.apprentice.snapshot().get('status')=='learning'):
                            raise ValueError('Finish active model work before changing workflow')
                        before=self.store.workflows.snapshot()
                        if getattr(runtime,'apprentice',None) and runtime.apprentice.snapshot().get('queued_questions',0):raise ValueError('Finish queued Lumen questions before changing workflow')
                        value=self.store.workflows.save_custom(data) if path.endswith('/save') else self.store.workflows.activate(data.get('id'))
                        after=self.store.workflows.snapshot()
                        if before['sha256']!=after['sha256']:
                            if getattr(runtime,'command',None):runtime.command.workflow_changed(after['id'])
                            if getattr(runtime,'apprentice',None):runtime.apprentice.workflow_changed()
                    return self.send(200,value)
                if path=='/api/apprentice/ask' and getattr(runtime,'apprentice',None):return self.send(200,runtime.apprentice.ask(data.get('message','')))
                if path.startswith('/api/apprentice/editor/') and getattr(runtime,'lumen_editor',None):
                    editor=runtime.lumen_editor
                    actions={'start':lambda:editor.submit(data),'local':lambda:editor.local(data),'watch-native':lambda:editor.watch_native(data),'stop':editor.stop,'reconcile':editor.reconcile,'resume':editor.resume,'release':editor.release,'feedback':lambda:editor.feedback(data)}
                    action=path.rsplit('/',1)[-1]
                    if action in actions:return self.send(200,actions[action]())
                if path=='/api/apprentice/settings' and getattr(runtime,'apprentice',None):return self.send(200,runtime.apprentice.configure(data))
                if path=='/api/apprentice/reconcile' and getattr(runtime,'apprentice',None):return self.send(200,runtime.apprentice.reconcile())
                command=getattr(runtime,'command',None)
                if path.startswith('/api/command/') and command:
                    routes={'/api/command/send':lambda:command.send(data.get('message',''),attachments=data.get('attachments',[])),'/api/command/stop':command.stop,'/api/command/retry-native-claude':command.retry_native_claude,'/api/command/refresh-usage':command.request_usage_refresh,'/api/command/approval':lambda:command.approval(data['id'],data['decision']),'/api/command/watch-native':lambda:command.watch_native(data),'/api/command/resume-observation':lambda:command.resume_native_observation(data),'/api/command/watch-job':lambda:command.watch_job(data),'/api/command/watch-local':lambda:command.watch_local(data)}
                    if path in routes:return self.send(200,routes[path]())
                if path in ('/api/production/update','/api/production/accept'):
                    editor=getattr(runtime,'lumen_editor',None)
                    if editor and editor.owns_editor() and (data.get('plan') or data).get('project_id')!=editor.job()['project_id']:raise ValueError('Lumen owns a separate trial; preserve other projects and their production boards')
                    from production import ProductionBoard
                    board=ProductionBoard(self.store.root)
                    result=board.accept(data) if path.endswith('/accept') else board.update(data)
                    if path.endswith('/update') and result.get('plan',{}).get('ready_for_review') and command:command.production_turn_finished('completed')
                    return self.send(200,result)
                if path=='/api/team/message':
                    from team_memory import TeamMemory
                    return self.send(200,TeamMemory(self.store.root).message(data,sender='Tony',attribution={'provider':'human','model':None,'agent_id':'tony','agent_name':'Tony','role':'human'}))
                if path=='/api/team/worker-message':
                    from team_memory import TeamMemory
                    return self.send(200,TeamMemory(self.store.root).worker_message(data))
                if path=='/api/command/team-message' and command:
                    if command.snapshot()['leader']['status'] not in command.active:raise ValueError('No working director owns this message')
                    from team_memory import TeamMemory
                    return self.send(200,TeamMemory(self.store.root).message(data,sender='Director',attribution=command._provenance()))
                if path=='/api/team/note':
                    from team_memory import TeamMemory
                    return self.send(200,TeamMemory(self.store.root).note(data))
                if path=='/api/shutdown':
                    with runtime.lock:
                        if getattr(runtime,'lumen_editor',None) and runtime.lumen_editor.owns_editor():raise ValueError('Lumen owns or must reconcile the editing lane; finish/release it before shutdown')
                        if command and command.snapshot()['leader']['status'] in command.active:raise ValueError('Leader is active; stop or finish the turn before shutdown')
                        if any(j['status'] in runtime.active_states for j in runtime.jobs()):raise ValueError('A job is active; cancel it or let it finish before shutdown')
                        if getattr(runtime,'local_ops',None) and runtime.local_ops.snapshot()['active']:raise ValueError('Local execution is active; let it finish or cancel it before shutdown')
                        if getattr(runtime,'apprentice',None) and runtime.apprentice.snapshot().get('status')=='learning':raise ValueError('Lumen is completing a real learning call; let it finish before shutdown')
                        runtime.accepting_work=False
                    self.send(200,{'stopping':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start();return
                if path=='/api/pick-files':
                    result=subprocess.run([sys.executable,str(ROOT/'app'/'picker.py')],capture_output=True,text=True,encoding='utf-8',timeout=300,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    if result.returncode:raise ValueError('The file chooser could not open. Paste absolute source paths instead.')
                    return self.send(200,json.loads(result.stdout))
                routes={'/api/agents':lambda:runtime.add_agent(data),'/api/agents/remove':lambda:runtime.remove_agent(data['agent_id']),
                        '/api/settings':lambda:runtime.update_settings(data),
                        '/api/providers/check':runtime.check_provider,'/api/providers/sign-in':lambda:runtime.sign_in(data['provider']),'/api/projects':lambda:runtime.create_project(data),
                        '/api/dispatch':lambda:runtime.dispatch(data),'/api/jobs/cancel':lambda:runtime.cancel(data['job_id']),
                        '/api/render':lambda:runtime.render(data),'/api/render/review':lambda:runtime.review_render(data),
                        '/api/tasks':lambda:runtime.create_task(data)}
                if path in routes:return self.send(200,routes[path]())
            if path=='/api/tasks':return self.send(201,self.store.create_task(data.get('station',''),data))
            if path=='/api/review':return self.send(200,self.store.review(data['station'],data['task_id'],data['decision'],data.get('note','')))
            if path=='/api/open-folder':
                folder=self.store.task_folder(data['station'],data['task_id']) if data.get('task_id') else self.store.folder(data['station'])
                if os.name!='nt':raise ValueError('Native folder opening is available on Windows')
                os.startfile(folder)
                return self.send(200,{'opened':str(folder)})
            return self.send(404,{'error':'Not found'})
        except Exception as e:
            from cutroom import ConflictError, CapabilityError
            from storage_policy import BudgetRefusal
            if isinstance(e,ConflictError):return self.send(409,{'error':str(e),'conflict':True})
            if isinstance(e,CapabilityError):return self.send(400,{'error':str(e),'problems':e.problems})
            if isinstance(e,BudgetRefusal):return self.send(400,{'error':str(e),'over_budget':True,'choices':e.choices})
            if isinstance(e,(ValueError,KeyError,TypeError,OSError)):return self.send(400,{'error':str(e)})
            raise

def run(port=8767):
    from operations import StudioRuntime
    from command_service import CommandService
    from apprentice_service import ApprenticeService
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.store=Store();server.token=secrets.token_urlsafe(32)
    server.runtime=StudioRuntime(server.store);atexit.register(server.runtime.shutdown)
    from dictation import DictationService
    from storage_policy import StoragePolicy
    server.storage_policy=StoragePolicy(ROOT)
    def dictation_busy():
        if getattr(server.runtime,'local_ops',None) and server.runtime.local_ops.snapshot().get('active'):return 'local media pipeline active'
        if getattr(server,'voice',None) and server.voice.state().get('speaking'):return 'studio voice output active'
        return None
    server.dictation=DictationService(ROOT/'.runtime'/'dictation',busy_check=dictation_busy,speech_root=ROOT);atexit.register(server.dictation.shutdown)
    server.runtime.apprentice=ApprenticeService(server.runtime);atexit.register(server.runtime.apprentice.shutdown)
    server.runtime.command=CommandService(server.runtime);atexit.register(server.runtime.command.shutdown)
    from lumen_editor import LumenEditor
    server.runtime.lumen_editor=LumenEditor(server.runtime);atexit.register(server.runtime.lumen_editor.shutdown)
    from studio_helper import StudioHelper
    server.helper=StudioHelper(server.runtime);atexit.register(server.helper.shutdown)
    from voice_engine import VoiceEngine
    server.voice=VoiceEngine(ROOT);atexit.register(server.voice.shutdown)
    server.runtime.local_ops.on_terminal=server.runtime.command.local_operation_finished
    server.runtime.command.restore_observations()
    from production_guard import startup_resume
    try:startup_resume(server.runtime.command)
    except Exception as error:print('startup idle check skipped:',error,flush=True)
    # Metadata checks run locally without inference and do not delay the window.
    def connect_metadata():
        server.runtime.check_provider()
        server.runtime.command.refresh_usage()
    threading.Thread(target=connect_metadata,daemon=True).start()
    atomic(ROOT/'.runtime'/'server.json',{'pid':os.getpid(),'port':server.server_port,'url':f'http://127.0.0.1:8767','started_at':now()})
    print(f'Neural Studio Local: http://127.0.0.1:{server.server_port}',flush=True)
    server.serve_forever()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8767);args=parser.parse_args();run(args.port)
