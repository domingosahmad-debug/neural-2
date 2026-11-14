"""Persisted bounded jobs, isolated from original Neural and native AE ownership."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import threading
import time
from uuid import uuid4

from providers_engine.transport import Transport, validate

ACTIVE={'QUEUED','RUNNING'}


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)


class ProviderJobs:
    def __init__(self,root,on_terminal=None,on_change=None,*,transport=None,max_workers=2):
        self.root=Path(root).resolve();self.base=self.root/'data/provider-jobs'
        self.base.mkdir(parents=True,exist_ok=True)
        self.on_terminal=on_terminal or (lambda row:None)
        self.on_change=on_change or (lambda:None)
        if transport is None:
            from providers_engine.runtime import RuntimeTransport
            transport=RuntimeTransport()
        self.transport=transport
        self.lock=threading.RLock();self.closed=False
        self.admission_lock=threading.RLock()
        self.before_start=lambda row: True
        self.prepare_packet=lambda row,packet,folder: packet
        self.pool=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix='bounded-provider')
        self.cancels={};self.rows={}
        self.session_path=self.base/'sessions.json'
        self.sessions=json.loads(self.session_path.read_text(encoding='utf-8')) if self.session_path.is_file() else {}
        for path in self.base.glob('*/job.json'):
            row=json.loads(path.read_text(encoding='utf-8'))
            if row['status'] in ACTIVE:
                row.update(status='UNKNOWN',error='Owner interrupted; queued/running work is never replayed',finished=time.time())
                save(path,row)
            self.rows[row['id']]=row
            sid=row.get('session_id')
            key=row.get('session_key')
            if sid and key and re.fullmatch(r'[A-Za-z0-9_-]{1,160}',sid):
                prior=self.sessions.get(key)
                if prior and prior['session_id']!=sid:
                    row.update(status='UNKNOWN',conversation_blocked=True,error='Saved session conflicts with canonical conversation; explicit reconciliation required')
                    self._save(row)
                elif not prior:
                    self.sessions[key]={'session_id':sid,'route':row['route'],'model':row['model']}
                    save(self.session_path,self.sessions)
        # Recovery events are durable before callbacks; no inference is scheduled.
        for row in self.rows.values():
            self._persist_terminal(row)
            try:self.on_terminal(copy.deepcopy(row))
            except Exception as error:
                row['notification_error']=str(error);self._save(row)

    def _folder(self,job_id):
        if job_id not in self.rows:raise ValueError('Unknown provider job')
        return self.base/job_id

    def _save(self,row):save(self.base/row['id']/'job.json',row)

    def _persist_terminal(self,row):
        if row['status'] in ACTIVE:return
        event=self.base/row['id']/'terminal.json'
        if not event.is_file():save(event,{'id':'provider:'+row['id'],'job_id':row['id'],'status':row['status'],'created':time.time()})

    def _changed(self):
        try:self.on_change()
        except Exception:pass

    def _finish(self,row):
        # Record outcome and exactly one terminal event before notifying owners.
        with self.lock:self._save(row);self._persist_terminal(row)
        try:self.on_terminal(copy.deepcopy(row))
        except Exception as error:
            with self.lock:row['notification_error']=str(error);self._save(row)
        self._changed()

    @staticmethod
    def _public(row):
        result=copy.deepcopy(row)
        result['taskTruncated']=len(str(result.get('task','')))>2000
        result['task']=str(result.get('task',''))[:2000]
        result['resultTruncated']=False
        if result.get('result'):
            result['resultTruncated']=len(str(result['result'].get('text','')))>64000
            result['result']['text']=str(result['result'].get('text',''))[:64000]
        return result

    def status(self):
        with self.lock:return [self._public(row) for row in sorted(self.rows.values(),key=lambda r:r['created'],reverse=True)]

    def result(self,job_id):
        with self.lock:
            folder=self._folder(job_id)
            if not (folder/'result.json').is_file():raise ValueError('Provider result is not available')
            return json.loads((folder/'result.json').read_text(encoding='utf-8'))

    def submit(self,packet,route,model,effort,request_id):
        # Shared maintenance reservation: a source repair and a new invocation never overlap.
        import maintenance
        with maintenance.admission(self.root,'provider'):
            return self._submit(packet,route,model,effort,request_id)

    def _submit(self,packet,route,model,effort,request_id):
        validate(route,model,effort)
        frozen=json.loads(json.dumps(packet,ensure_ascii=False))
        if not isinstance(frozen,dict):raise ValueError('Packet must be an object')
        # Flat and portable packets use the same immutable identity fields.
        project=frozen.get('project') or frozen.get('project_id') or frozen.get('projectId')
        if isinstance(project,dict):project=project.get('id')
        station=frozen.get('station')
        if isinstance(station,dict):station=station.get('id') or station.get('name')
        assignment=frozen.get('assignmentId') or frozen.get('assignment_id')
        revision=frozen.get('revision')
        if not all(isinstance(v,(str,int)) and str(v) for v in (project,station,assignment)) or revision is None:
            raise ValueError('Packet requires project, station, assignmentId and revision')
        if frozen.get('model') is not None and frozen['model']!=model:
            raise ValueError('Packet model does not match the exact requested route model')
        capabilities=frozen.get('requiredCapabilities',frozen.get('required_capabilities',frozen.get('capabilities',['text'])))
        if isinstance(capabilities,str):capabilities=[capabilities]
        allowed={'text','supplied_text_context','read text','return JSON'}
        if frozen.get('toolMode')=='production' and callable(getattr(self.transport,'supports',None)) and self.transport.supports(route,'production'):
            allowed.add('neural_tools')
        if not isinstance(capabilities,list) or any(not isinstance(v,str) for v in capabilities) or set(capabilities)-allowed:
            raise ValueError('Required execution capability is unavailable on this provider route')
        if not isinstance(request_id,str) or not request_id or len(request_id)>200:raise ValueError('A bounded request_id is required')
        body=json.dumps({'packet':frozen,'route':route,'model':model,'effort':effort},sort_keys=True,ensure_ascii=False)
        digest=hashlib.sha256(body.encode()).hexdigest()
        session_key=json.dumps([str(project),str(station),route,model],separators=(',',':'))
        if frozen.get('toolMode')=='production':
            session_key=json.dumps([str(project),str(station),route,model,'production',str(assignment) if frozen.get('contextMode')=='fresh_review' else 'ordinary'],separators=(',',':'))
        with self.lock:
            if self.closed:raise ValueError('Provider jobs are shut down')
            for row in self.rows.values():
                if row['request_id']==request_id:
                    if row['request_hash']!=digest:raise ValueError('request_id was already used for a different immutable packet/route')
                    return self._public(row)
                if str(row['assignmentId'])==str(assignment) and str(row['project'])==str(project):
                    raise ValueError('Assignment already has a provider attempt; a new guarded assignment is required')
                if row['session_key']==session_key and row['status'] in ACTIVE:
                    raise ValueError('Persistent station conversation is busy')
                if row['session_key']==session_key and (row['status']=='UNKNOWN' or (row['status']=='CANCELLED' and row.get('execution_started') is not False) or row.get('conversation_blocked')):
                    raise ValueError('Conversation requires explicit reconciliation; no automatic retry/reset')
            prior=self.sessions.get(session_key)
            if prior and (prior.get('route')!=route or prior.get('model')!=model):raise ValueError('Saved conversation route/model mismatch')
            job_id=uuid4().hex
            row={'id':job_id,'project':project,'assignmentId':assignment,'station':station,'revision':revision,'route':route,'model':model,'effort':effort,'task':frozen.get('task') or frozen.get('title') or '', 'status':'QUEUED','request_id':request_id,'request_hash':digest,'packet_sha256':hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'session_key':session_key,'session_id':prior.get('session_id') if prior else None,'created':max([time.time()]+[r['created']+1e-6 for r in self.rows.values()]),'owner_pid':os.getpid(),'raw_evidence':str(self.base/job_id/'raw.log'),'packet_path':str(self.base/job_id/'packet.json'),'result_path':str(self.base/job_id/'result.json')}
            self.rows[job_id]=row;self.cancels[job_id]=threading.Event()
            save(self.base/job_id/'packet.json',frozen);self._save(row)
            self.pool.submit(self._run,job_id)
        self._changed()
        return self._public(row)

    def _run(self,job_id):
        stop=False
        # Control.pause shares this lock. RUNNING is the reservation point:
        # a pause either precedes the guard or observes an already active job.
        with self.admission_lock:
            try:
                with self.lock: snapshot=copy.deepcopy(self.rows[job_id])
                admitted=self.before_start(snapshot)
                with self.lock:
                    row=self.rows[job_id];cancel=self.cancels[job_id]
                    if not admitted or cancel.is_set():
                        stop=True
                        row.update(status='CANCELLED',execution_started=False,error='Project paused or task superseded before provider start; no invocation ran' if not admitted else 'Cancelled before provider start; no invocation ran',finished=time.time())
                        save(self.base/job_id/'result.json',{'status':row['status'],'error':row['error'],'execution_started':False})
                    else:
                        packet=json.loads((self.base/job_id/'packet.json').read_text(encoding='utf-8'))
                        row.update(status='RUNNING',started=time.time());self._save(row)
            except Exception as error:
                stop=True
                with self.lock:
                    row=self.rows[job_id]
                    row.update(status='FAILED',execution_started=False,error='Admission guard failed before provider start: '+str(error),
                               finished=time.time(),conversation_blocked=False)
                    save(self.base/job_id/'result.json',{'status':'FAILED','error':row['error'],
                                                        'execution_started':False})
        # Never call controller callbacks under either lock; their lock order
        # is controller admission -> provider, including status and fallback.
        if stop:
            self._finish(row)
            return
        self._changed()
        invocation_started=False
        try:
            packet=self.prepare_packet(copy.deepcopy(row),packet,self.base/job_id)
            save(self.base/job_id/'admitted-packet.json',packet)
            invocation_started=True
            outcome=self.transport.run(copy.deepcopy(row),packet,self.base/job_id,row.get('session_id'),cancel)
            if not isinstance(outcome,dict) or outcome.get('status') not in {'COMPLETED','FAILED','CANCELLED','UNKNOWN'}:raise ValueError('Invalid provider outcome')
            if cancel.is_set() and outcome['status']=='COMPLETED':outcome.update(status='CANCELLED',error='Cancellation raced provider completion; reconcile saved result')
            observed=outcome.get('session_id')
            canonical=self.sessions.get(row['session_key'],{}).get('session_id') or row.get('session_id')
            mismatch=bool(observed and (not isinstance(observed,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',observed) or (canonical and observed!=canonical)))
            if mismatch:outcome.update(status='UNKNOWN',error='Saved/provider session mismatch; no automatic reset')
            with self.lock:
                save(self.base/job_id/'result.json',outcome)
                row.update(status=outcome['status'],execution_started=outcome.get('execution_started',True),result=outcome,error=outcome.get('error'),finished=time.time())
                if observed and not mismatch:
                    row['session_id']=observed
                    self.sessions[row['session_key']]={'session_id':observed,'route':row['route'],'model':row['model']}
                    save(self.session_path,self.sessions)
                if mismatch or (outcome['status']=='FAILED' and not observed and outcome.get('execution_started',True)):
                    row['conversation_blocked']=True
        except Exception as error:
            with self.lock:
                row.update(status='UNKNOWN' if invocation_started else 'FAILED',execution_started=invocation_started,error=('Provider execution interrupted: ' if invocation_started else 'Preparation refused before provider start: ')+str(error),finished=time.time())
                save(self.base/job_id/'result.json',{'status':row['status'],'error':row['error'],'execution_started':invocation_started})
        self._finish(row)

    def cancel(self,job_id):
        with self.lock:
            self._folder(job_id)
            if self.rows[job_id]['status'] in ACTIVE:self.cancels[job_id].set()
            return self._public(self.rows[job_id])

    def shutdown(self):
        with self.lock:
            self.closed=True
            for event in self.cancels.values():event.set()
        self.pool.shutdown(wait=True,cancel_futures=False)
