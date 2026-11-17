"""Scoped, durable production gateway. Never launches AE, claims a lease, or retries UNKNOWN.

The parent creates a private scope and invalidates authorityPath BEFORE changing
pause/revision/generation/lease. JSX is authorized native writer code, not a sandbox.
No shell, arbitrary file-write, or arbitrary read tool is exposed.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


DIALOG_HANDLING=os.environ.get('NEURAL_AE_DIALOGS','1')!='0'  # tests switch real desktop probing off
DIALOG_INTERVAL=3
CRASH_INTERVAL=5  # The coordinator reads status twice a second; a process probe that often only burns CPU.
DRAWN_MODAL_SECONDS=20
DIALOG_CAP=12       # Acknowledgements one native command may receive in total; after that a dialog is a blocker.
DIALOG_TARGET=None  # (process name, pid) for proofs against a stand-in process; None is After Effects itself.
LOCK_WAIT=5     # The helper lock is held for milliseconds; a short wait covers honest contention.
LOCK_STALE=120  # A lock this old belongs to a process that died holding it.

def encoded(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
def digest(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
@contextmanager
def connect(*args,**kwargs):
    db=sqlite3.connect(*args,**kwargs)
    try:
        with db:yield db
    finally:db.close()

def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def inside(path, root):
    try: Path(path).resolve().relative_to(Path(root).resolve()); return True
    except ValueError: return False

def atomic(path, value):
    path = Path(path); tmp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if tmp.exists(): tmp.unlink()

# Exact structure is retained on disk; the model receives its SHA256 identity.
JS_COMMON = r'''
function enc(x){var t=typeof x,a=[],k,i;if(x===null||t==='undefined'||t==='function')return 'null';if(t==='string')return '"'+x.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';if(t==='number'||t==='boolean')return String(x);if(x instanceof Array){for(i=0;i<x.length;i++)a.push(enc(x[i]));return '['+a.join(',')+']';}for(k in x)if(x.hasOwnProperty(k))a.push(enc(k)+':'+enc(x[k]));return '{'+a.join(',')+'}';}
function norm(p){return p===null?null:String(p).replace(/\\/g,'/').toLowerCase();}
function prop(p){var a=[p.name,p.matchName],i;if(p.propertyType===PropertyType.PROPERTY){a.push(p.numKeys);try{a.push(p.expressionEnabled?p.expression:'');}catch(e){a.push('');}}else{for(i=1;i<=p.numProperties;i++)a.push(prop(p.property(i)));}return a;}
function structure(c){var p=app.project,a={projectPath:p.file?p.file.fsName:null,items:[],comp:null},i,l,q,j;for(i=1;i<=p.numItems;i++){q=p.item(i);a.items.push([q.id,q.name,q instanceof CompItem?'comp':'item']);}if(c){a.comp={id:c.id,name:c.name,width:c.width,height:c.height,pixelAspect:c.pixelAspect,frameRate:c.frameRate,duration:c.duration,layers:[]};for(i=1;i<=c.numLayers;i++){l=c.layer(i);q=[l.id,l.name,l.parent?l.parent.id:null,l.inPoint,l.outPoint,l.startTime,l.stretch,l.enabled,l.locked];try{q.push(l.source?l.source.id:null);}catch(e){q.push(null);}for(j=1;j<=l.numProperties;j++)q.push(prop(l.property(j)));a.comp.layers.push(q);}}return enc(a);}
function nativeValue(v){var t=typeof v,a=[],i;if(v===null||t==='string'||t==='boolean')return v;if(t==='number')return isFinite(v)?v:String(v);if(v instanceof Array){for(i=0;i<v.length;i++)a.push(nativeValue(v[i]));return a;}if(typeof TextDocument!=='undefined'&&v instanceof TextDocument)return {kind:'TextDocument',text:v.text,font:v.font,fontSize:v.fontSize,fillColor:v.fillColor,tracking:v.tracking};if(typeof Shape!=='undefined'&&v instanceof Shape)return {kind:'Shape',vertices:v.vertices,inTangents:v.inTangents,outTangents:v.outTangents,closed:v.closed};return {opaque:true,note:'Native value is not a round-trip serializer; preserve native authored effects.'};}
function nativeEase(a){var b=[],i;for(i=0;i<a.length;i++)b.push({speed:a[i].speed,influence:a[i].influence});return b;}
function nativeProp(p,t){var o={name:p.name,matchName:p.matchName,index:p.propertyIndex},i,k;if(p.propertyType!==PropertyType.PROPERTY){o.children=[];for(i=1;i<=p.numProperties;i++)o.children.push(nativeProp(p.property(i),t));return o;}try{o.value=nativeValue(p.valueAtTime(t,false));}catch(e){o.unreadable=String(e);}try{if(p.canSetExpression){o.expression=p.expression;o.expressionEnabled=p.expressionEnabled;}}catch(e){}o.keys=[];for(i=1;i<=p.numKeys;i++){k={time:p.keyTime(i),value:nativeValue(p.keyValue(i))};try{k.inType=String(p.keyInInterpolationType(i));k.outType=String(p.keyOutInterpolationType(i));k.inEase=nativeEase(p.keyInTemporalEase(i));k.outEase=nativeEase(p.keyOutTemporalEase(i));k.auto=p.keyTemporalAutoBezier(i);k.continuous=p.keyTemporalContinuous(i);}catch(e){k.interpolationUnreadable=String(e);}o.keys.push(k);}return o;}
function snapshot(c){var out={active:c?c.id:null,comps:[]},seen={};function visit(comp){if(!comp||seen[comp.id])return;seen[comp.id]=true;var row={id:comp.id,name:comp.name,width:comp.width,height:comp.height,frameRate:comp.frameRate,frameDuration:comp.frameDuration,duration:comp.duration,sampleTime:comp.time,layers:[]},i,j,l,r;out.comps.push(row);for(i=1;i<=comp.numLayers;i++){l=comp.layer(i);r={id:l.id,index:i,name:l.name,inPoint:l.inPoint,outPoint:l.outPoint,startTime:l.startTime,stretch:l.stretch,enabled:l.enabled,locked:l.locked,selected:l.selected,parent:l.parent?l.parent.id:null,properties:[]};try{r.sourceId=l.source.id;r.sourceFile=l.source.file?l.source.file.fsName:null;r.audioEnabled=l.audioEnabled;r.blendMode=String(l.blendingMode);r.matteType=String(l.trackMatteType);}catch(e){}for(j=1;j<=l.numProperties;j++)r.properties.push(nativeProp(l.property(j),comp.time));row.layers.push(r);try{if(l.source instanceof CompItem)visit(l.source);}catch(e){}}}visit(c);out.items=[];for(var ix=1;ix<=app.project.numItems;ix++){var it=app.project.item(ix),meta={id:it.id,name:it.name,type:it.typeName};try{meta.file=it.file?it.file.fsName:null;meta.duration=it.duration;meta.frameRate=it.frameRate;}catch(ignore){}out.items.push(meta);if(it instanceof CompItem)visit(it);}return out;}
function readAuthority(path){var f=new File(path);if(!f.exists||!f.open('r'))throw Error('Execution authority unavailable');var t;try{t=f.read();}finally{f.close();}if(!/^[\s\S]*\{/.test(t))throw Error('Invalid authority');return JSON.parse(t);}
function writeReport(path,r){var f=new File(path);f.encoding='UTF-8';if(!f.open('w'))throw Error('Cannot write completion report');try{f.write(enc(r));}finally{f.close();}}
'''

class Refused(ValueError):
    pass

class ProductionGateway:
    REQUIRED = ('root','db','project','revision','generation','assignmentId','jobId','nativeLeaseId','nativeProject','projectRoot','station','model','authorityPath')
    def __init__(self, scope_path, *, reconciliation_only=False):
        self.reconciliation_only=reconciliation_only
        self.scope_path = Path(scope_path).resolve(strict=True)
        self.scope = load(self.scope_path); self.scope_hash = digest(encoded(self.scope))
        if self.scope.get('schema') != 'neural.production-scope.v1' or any(key not in self.scope for key in self.REQUIRED):
            raise ValueError('Trusted complete neural.production-scope.v1 scope required.')
        s = self.scope
        for key in ('root','db','projectRoot','authorityPath'):
            if not Path(s[key]).is_absolute(): raise ValueError(key + ' must be absolute.')
        self.root = Path(s['root']).resolve(strict=True); self.project_root = Path(s['projectRoot']).resolve(strict=True)
        if not inside(s['authorityPath'], self.project_root): raise ValueError('Authority must be within the admitted project root.')
        self.folder = self.project_root / '.neural-gateway'; self.folder.mkdir(exist_ok=True)
        self.native_db = self.root / 'data/native-ownership.sqlite3'
        self.database = self.root / 'data/production-gateway.sqlite3'
        self.bridge = Path(s.get('bridgePath') or Path.home() / 'Documents/ae-mcp-bridge').resolve(strict=True)
        self.read_roots = [self.project_root] + [Path(p).resolve(strict=True) for p in s.get('artifactRoots', [])]
        if not self.native_db.is_file() or not Path(s['db']).is_file(): raise ValueError('Existing workspace and native ownership databases required.')
        with connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (request TEXT PRIMARY KEY, body TEXT NOT NULL)')
        registry=self.folder/'registry.json'
        registration={'database':str(self.database),'projectRoot':str(self.project_root)}
        if registry.exists():
            if load(registry)!=registration:raise ValueError('Private gateway registry identity changed.')
        else:
            with registry.open('x',encoding='utf-8') as stream:stream.write(encoded(registration))
        self._authorize(reconcile=reconciliation_only)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.database, timeout=10)
        try:
            db.execute('ATTACH DATABASE ? AS workspace', (str(self.scope['db']),))
            db.execute('ATTACH DATABASE ? AS native', (str(self.native_db),))
            db.execute('BEGIN IMMEDIATE')
            yield db; db.commit()
        except BaseException: db.rollback(); raise
        finally: db.close()

    def _authorize(self, db=None, *, reconcile=False):
        if self.reconciliation_only and not reconcile:raise ValueError('This gateway is restricted to existing result reconciliation; no new work admitted.')
        if digest(encoded(load(self.scope_path))) != self.scope_hash: raise ValueError('Trusted scope changed; re-admit at a safe boundary.')
        if db is None:
            with self.transaction() as connection: return self._authorize(connection, reconcile=reconcile)
        s = self.scope
        saved = db.execute('SELECT body FROM workspace.workspace WHERE id=1').fetchone()
        p = json.loads(saved[0]).get(s['project']) if saved else None
        if not p or p.get('revision') != s['revision']: raise ValueError('Exact persisted project revision required.')
        ctl = p.get('productionControl', {})
        if ctl.get('generation',0) != s['generation'] and not reconcile: raise ValueError('Production generation changed; no stale work admitted.')
        if ctl.get('paused') and not reconcile: raise ValueError('Project is paused; no new work admitted.')
        assignment = p.get('assignments', {}).get(s['assignmentId'])
        if not assignment or any(assignment.get(k) != s[k] for k in ('revision','station','model')) or (assignment.get('status') == 'superseded' and not reconcile):
            raise ValueError('Exact current persisted station assignment/model required.')
        row = db.execute('SELECT body FROM native.owner WHERE id=1').fetchone()
        lease = json.loads(row[0]) if row else {}
        if lease.get('id') != s['nativeLeaseId'] or lease.get('project') != s['nativeProject']:
            raise ValueError('Exact cooperative native lease and scope required; no transfer is automatic.')
        authority = load(s['authorityPath'])
        for key in ('project','revision','generation','assignmentId','jobId','nativeLeaseId','nativeProject'):
            if authority.get(key) != s[key] and not (reconcile and key=='generation'): raise ValueError('Execution authority mismatch: ' + key)
        if authority.get('paused') is not False and not reconcile: raise ValueError('Execution authority paused or invalid.')
        return p

    def _row(self, request_id, db=None):
        if db is None:
            with connect(self.database) as connection: return self._row(request_id, connection)
        row = db.execute('SELECT body FROM requests WHERE request=?', (request_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _save(self, db, row):
        db.execute('INSERT INTO requests VALUES(?,?) ON CONFLICT(request) DO UPDATE SET body=excluded.body', (row['requestId'],encoded(row)))

    def project_context(self):
        p = self._authorize(reconcile=True)
        return {k:self.scope[k] for k in ('project','revision','generation','assignmentId','jobId','station','model')} | {'paused':p.get('productionControl',{}).get('paused',False),'assignment':p['assignments'][self.scope['assignmentId']], 'allowMutation':bool(self.scope.get('allowMutation')),'limits':'One scoped TonyFX writer. Tool/native success is separate from playback, listening and artistic approval.'}

    def _completed_media_output(self, path):
        """Trust only hash-verified output of a settled job for this project."""
        base=(self.root/'data/local-ops/jobs').resolve()
        try:
            relative=path.resolve().relative_to(base)
            if len(relative.parts)!=3:return False
            job_id,step_id,name=relative.parts
            if not re.fullmatch(r'[a-f0-9]{32}',job_id):return False
            job=load(base/job_id/'JOB.json')
            if job.get('project')!=self.scope['project'] or job.get('status')!='COMPLETED':return False
            step=next((s for s in job.get('steps',[]) if s.get('id')==step_id and s.get('status')=='COMPLETED'),{})
            expected=step.get('hashes',{}).get(name)
            return bool(expected and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==expected)
        except (OSError,ValueError,KeyError,TypeError):return False

    def _scoped_file(self, name):
        path = Path(name)
        if not path.is_absolute(): path = self.project_root / path
        path = path.resolve(strict=True)
        if not any(inside(path, root) for root in self.read_roots) and not self._completed_media_output(path): raise ValueError('Artifact is outside the admitted read roots.')
        if path.is_dir():
            # Read-only discovery so a worker can find workflow/source files instead of guessing names.
            names = sorted(p.name + ('/' if p.is_dir() else '') for p in path.iterdir())
            raise ValueError('Path is an admitted directory, not a file. Read one entry: ' + ', '.join(names[:200]) + (' ... (%d more)' % (len(names) - 200) if len(names) > 200 else ''))
        if not path.is_file(): raise ValueError('Artifact is outside the admitted read roots.')
        if path == self.scope_path or path == Path(self.scope['authorityPath']).resolve(): raise ValueError('Private gateway authority files are not model artifacts.')
        if inside(path,self.folder):
            with connect(self.database) as db:
                owned=any(json.loads(raw).get('reportPath')==str(path) and (json.loads(raw).get('scope')==self.scope_hash or json.loads(raw).get('project')==self.scope['project'] and json.loads(raw).get('state')=='COMPLETED') for raw, in db.execute('SELECT body FROM requests'))
            if not owned:raise ValueError('Only the exact own native report is readable inside the private gateway root.')
        return path

    def read_artifact(self, path, offset=0, length=65536, jsonPointer=None):
        self._authorize(reconcile=True); source = self._scoped_file(path)
        suffix=source.suffix.lower(); size=source.stat().st_size
        if suffix in ('.png','.jpg','.jpeg'):
            if size>8_000_000: raise ValueError('Image exceeds 8MB; prepare a bounded still using media tools.')
            from PIL import Image
            with Image.open(source) as image:
                if image.width>8192 or image.height>8192 or image.width*image.height>32_000_000: raise ValueError('Image dimensions exceed the admitted evidence bound.')
                image.verify()
            return {'kind':'image','mimeType':'image/png' if suffix=='.png' else 'image/jpeg','data':base64.b64encode(source.read_bytes()).decode(),'path':str(source),'bytes':size}
        if suffix not in ('.json','.txt','.md','.csv','.tsv','.log','.jsx','.srt','.vtt'): raise ValueError('Unsupported binary artifact. Prepare a PNG/JPEG still or typed text evidence.')
        if jsonPointer is not None:
            if suffix!='.json' or not isinstance(jsonPointer,str) or jsonPointer and not jsonPointer.startswith('/'):raise ValueError('A valid JSON pointer on a JSON artifact is required.')
            selected=load(source)
            if jsonPointer:
                for part in jsonPointer[1:].split('/'):
                    key=part.replace('~1','/').replace('~0','~')
                    selected=selected[int(key)] if isinstance(selected,list) else selected[key]
            text=encoded(selected)
            if len(text.encode('utf-8'))>65536:raise ValueError('Selected JSON evidence exceeds65536bytes; choose a deeper JSON pointer. The full report is preserved.')
            return {'kind':'json','path':str(source),'jsonPointer':jsonPointer,'partial':False,'data':selected}
        if type(offset) is not int or type(length) is not int or offset<0 or not 1<=length<=65536: raise ValueError('Explicit byte offset>=0 and length1..65536 required.')
        with source.open('rb') as stream: stream.seek(offset); raw=stream.read(length)
        return {'kind':'text','path':str(source),'offset':offset,'bytes':size,'returnedBytes':len(raw),'partial':offset>0 or offset+len(raw)<size,'text':raw.decode('utf-8-sig',errors='replace')}

    def _new(self, request_id, kind, payload):
        import maintenance
        with maintenance.admission(self.root,'native-gateway'):
            return self._admit(request_id, kind, payload)

    def _admit(self, request_id, kind, payload):
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',request_id): raise ValueError('Persist an explicit requestId (1..160 safe characters).')
        immutable = digest(encoded({'scope':self.scope_hash,'kind':kind,'payload':payload}))
        with self.transaction() as db:
            self._authorize(db)
            old=self._row(request_id,db)
            if old:
                if old['immutable']!=immutable: raise ValueError('Request ID belongs to different immutable work.')
                return old,False
            # Includes other scopes/jobs using this gateway; UNKNOWN never admits replacement.
            for raw, in db.execute('SELECT body FROM requests'):
                prior=json.loads(raw)
                if kind!='media' and prior['kind']!='media' and prior['state'] in ('INTENT','PUBLISHING','SUBMITTED','UNKNOWN') and not (prior['kind']=='inspect' and prior['state']=='UNKNOWN'):
                    raise ValueError('An unresolved native gateway request exists; reconcile it without replay.')
            row={'requestId':request_id,'immutable':immutable,'scope':self.scope_hash,'project':self.scope['project'],'jobId':self.scope['jobId'],'kind':kind,'state':'INTENT','created':now(),'commandId':'tfx-'+uuid4().hex,'reportId':uuid4().hex,'payload':payload}
            row['folder']=str(self.folder / digest(request_id)); row['reportPath']=str(Path(row['folder'])/'report.json')
            self._save(db,row)
        return row,True

    def _wrapper(self, row, body, expected=None, guard=None):
        s=self.scope
        # AE's synchronous render closes its undo stack. An outer undo group
        # then produces a modal mismatch warning at each render boundary.
        # Render scripts still use the exact authority/structure guards and
        # durable command/report ledger; only the undo transaction is omitted.
        grouped = row['kind']=='mutate' and not re.search(r'\.\s*render\s*\(', body)
        authority={k:s[k] for k in ('project','revision','generation','assignmentId','jobId','nativeLeaseId','nativeProject')}
        config={'authorityPath':s['authorityPath'],'authority':authority,'reportPath':row['reportPath'],'requestId':row['requestId'],'commandId':row['commandId'],'reportId':row['reportId'],'compId':s.get('compId'),'compName':s.get('compName'),'projectPath':s.get('aeProjectPath'),'bootstrap':s.get('allowBootstrap') is True,'expected':expected}
        if guard:
            config.update(projectPath=guard['projectPath'],compId=guard['compId'],compName=guard['compName'],bootstrap=guard['compId'] is None)
        elif row['kind']=='inspect':
            config.update(compId=None,compName=None,projectPath=None,bootstrap=True,discover=True,discoverName=s.get('compName'),discoverPath=s.get('aeProjectPath'))
        # JSON.parse is provided locally when AE omits the JSON global; no eval on model input.
        parse="if(typeof JSON==='undefined')JSON={};if(!JSON.parse)JSON.parse=function(t){return eval('('+t+')');};"
        return '(function(){\n'+parse+'\n'+JS_COMMON+'\nvar cfg='+json.dumps(config,ensure_ascii=True,separators=(',',':'))+r''';
var report={requestId:cfg.requestId,commandId:cfg.commandId,reportId:cfg.reportId,ok:false},undo=false,suppressed=false;
try{
var auth=readAuthority(cfg.authorityPath),key;
for(key in cfg.authority)if(auth[key]!==cfg.authority[key])throw Error('Execution authority mismatch: '+key);
if(auth.paused!==false)throw Error('Project paused before AE execution');
if(!app.project)throw Error('No AE project');
if(app.project.renderQueue.rendering)throw Error('AE is rendering');
var c=null,i;
if(cfg.compId!==null&&cfg.compId!==undefined){for(i=1;i<=app.project.numItems;i++)if(app.project.item(i).id===cfg.compId)c=app.project.item(i);if(!(c instanceof CompItem)||c.name!==cfg.compName)throw Error('Comp ID/name guard failed');}
else if(cfg.discover){
// A bootstrapped comp is not the active item. In the exact scoped AEP only, resolve the one comp with the scoped name.
if(cfg.discoverName&&app.project.file&&norm(app.project.file.fsName)===norm(cfg.discoverPath)){var found=[];for(i=1;i<=app.project.numItems;i++)if(app.project.item(i) instanceof CompItem&&app.project.item(i).name===cfg.discoverName)found.push(app.project.item(i));if(found.length===1)c=found[0];}
if(!c){c=app.project.activeItem;if(!(c instanceof CompItem))c=null;}}
else if(!cfg.bootstrap){c=app.project.activeItem;if(!(c instanceof CompItem))throw Error('No active composition');}
if(!cfg.discover&&cfg.projectPath!==undefined&&norm(app.project.file?app.project.file.fsName:null)!==norm(cfg.projectPath))throw Error('AE project path guard failed');
var before=structure(c);
if(cfg.expected!==null&&before!==cfg.expected)throw Error('Exact structural signature guard failed');
report.projectPath=app.project.file?app.project.file.fsName:null;report.compId=c?c.id:null;report.compName=c?c.name:null;report.structure=before;report.aeVersion=app.version;
if(typeof app.beginSuppressDialogs==='function'){app.beginSuppressDialogs();suppressed=true;}
''' + ("app.beginUndoGroup('Neural '+cfg.requestId);undo=true;\n" if grouped else '')+body+r'''
report.ok=true;
}catch(e){report.error=String(e);report.line=e.line||null;}
finally{if(suppressed&&typeof app.endSuppressDialogs==='function'){try{app.endSuppressDialogs(false);}catch(ignoreSup){}}if(undo){try{app.endUndoGroup();}catch(cleanup){report.ok=false;report.cleanupError=String(cleanup);}}
// The scoped AEP path is pinned: a Save As inside worker JSX is saved back in place so later guards still match.
try{if(cfg.projectPath&&norm(app.project.file?app.project.file.fsName:null)!==norm(cfg.projectPath)){app.project.save(new File(cfg.projectPath));report.pathRestored=true;}}catch(restore){report.ok=false;report.pathError=String(restore);}writeReport(cfg.reportPath,report);}
return enc({ok:report.ok,error:report.error||null,reportId:cfg.reportId});
})();'''

    def ae_inspect(self, requestId):
        row,new=self._new(requestId,'inspect',{})
        if not new:return self.ae_status(requestId)
        return self._publish(row,self._wrapper(row,"report.snapshot=snapshot(c);report.selectedLayers=[];if(c)for(i=1;i<=c.numLayers;i++)if(c.layer(i).selected)report.selectedLayers.push({id:c.layer(i).id,name:c.layer(i).name});"))

    def ae_submit(self, requestId, jsx, guard):
        self._authorize()
        if self.scope.get('allowMutation') is not True or self.scope['station'] not in ('Director','Edit','Deliver'): raise ValueError('This scope has no native mutation authority.')
        if not isinstance(jsx,str) or not 1<=len(jsx.encode('utf-8'))<=98304: raise ValueError('Native JSX must contain1..98304 UTF-8 bytes.')
        # No shell escape hatch. This is a capability guard, not a hostile-code sandbox.
        if re.search(r'\b(?:system|Socket|BridgeTalk|eval|Function)\b|\$\s*\.|\b(?:execute|evalFile|scheduleTask|newProject|quit)\s*\(|#\s*include',jsx): raise ValueError('Shell, external execution, dynamic evaluation and delayed execution are not admitted.')
        expected=self._inspection(guard)
        scope_path=self.scope.get('aeProjectPath')
        if not scope_path or str(guard['projectPath']).replace('\\','/').casefold()!=str(scope_path).replace('\\','/').casefold() or guard['compName']!=self.scope.get('compName') or self.scope.get('compId') is not None and guard['compId']!=self.scope['compId']:raise ValueError('Mutation target is outside admitted AE project/comp.')
        row,new=self._new(requestId,'mutate',{'jsx':jsx,'guard':guard})
        if not new:return self.ae_status(requestId)
        return self._publish(row,self._wrapper(row,'report.result=(function(){\n'+jsx+'\n})();\nreport.afterStructure=structure(c);',expected,guard))

    def _bridge_state(self):
        return {key:load(self.bridge/name) if (self.bridge/name).exists() else None for key,name in (('command','ae_command.json'),('result','ae_mcp_result.json'))}

    def _publish(self,row,script):
        folder=Path(row['folder']);folder.mkdir(exist_ok=False)
        wrapper=folder/'command.jsx'
        with wrapper.open('x',encoding='utf-8') as stream: stream.write(script);stream.flush();os.fsync(stream.fileno())
        row['scriptPath']=str(wrapper);row['scriptSha256']=digest(script)
        with self.transaction() as db:
            self._authorize(db);row['state']='PUBLISHING';self._save(db,row)
        lock=self.bridge/'tfx_skill_client.lock'; fd=None; owned=False; written=False
        try:
            deadline=time.monotonic()+LOCK_WAIT
            while True:
                try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);break
                except FileExistsError:
                    try:age=time.time()-lock.stat().st_mtime
                    except OSError:age=0
                    if age>LOCK_STALE:
                        # Set aside, never deleted: the rename is atomic, so only one claimant moves it.
                        try:os.rename(lock,lock.with_name(lock.name+'.stale-'+uuid4().hex[:8]));row['staleLockSetAside']=round(age);continue
                        except OSError:pass  # Held open or protected: it is contention like any other and ends at the deadline.
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            owned=True;os.write(fd,row['commandId'].encode());os.close(fd);fd=None
            with self.transaction() as db:
                self._authorize(db)
                state=self._bridge_state();command=state['command'] or {};result=state['result'] or {}
                if command.get('status') in ('pending','running') or command.get('id') and result.get('_commandId')!=command['id']: raise ValueError('TonyFX bridge unresolved; no command overwritten.')
                request={'id':row['commandId'],'command':'runScriptFile','args':{'scriptPath':str(wrapper)},'timestamp':now(),'status':'pending'}
                # Already durable PUBLISHING. A crash after this replace is UNKNOWN, never replayed.
                written=True
                atomic(self.bridge/'ae_command.json',request)
                row.update(state='SUBMITTED',submitted=now());self._save(db,row)
        except BaseException as error:
            # Refused before the bridge command file was touched: After Effects never saw it, so it is a plain failure.
            if written:row.update(state='UNKNOWN',error=str(error))
            else:row.update(state='FAILED',notSubmitted=True,error='Not submitted; nothing reached After Effects: '+(str(error) or type(error).__name__),finished=now())
            with connect(self.database) as db:self._save(db,row)
            raise
        finally:
            if fd is not None:os.close(fd)
            if owned:
                # Remove only our own lock; a failure here never turns a submitted command into an error.
                try:
                    if lock.read_bytes()==row['commandId'].encode():lock.unlink()
                except OSError:pass
        return self._public(row)

    def _public(self,row):
        output={k:row.get(k) for k in ('requestId','project','jobId','kind','state','commandId','reportId','reportPath','created','submitted','finished','error','mediaJobId')}
        # Mechanical rows never write a native report; advertising the path made workers cite a file that cannot exist.
        if row.get('kind')=='media':output.pop('reportPath',None)
        if row.get('guard'):
            output['guard']=row['guard']
            scoped=self.scope.get('aeProjectPath');opened=row['guard'].get('projectPath')
            # A discover inspect succeeds on any open project; say so when it is not the scoped one.
            if scoped and Path(scoped).is_file() and (not opened or Path(opened).resolve()!=Path(scoped).resolve()):
                output['wrongProject']='After Effects has a different project open than the scoped AEP '+str(scoped)+'. Work there cannot count. Call ae_open with this guard, then inspect again.'
        if row.get('resultPath'):output['resultPath']=row['resultPath']
        if row.get('report') is not None:output['report']=row['report']
        if row.get('dialogsDismissed'):output['dialogsDismissed']=row['dialogsDismissed'][-5:]
        if row.get('aeCrash') and row['state'] not in ('COMPLETED','FAILED'):
            output['aeCrash']=row['aeCrash'];output['continuation']={'outcome':'blocked','reason':row['aeCrash']['message']}
        elif row.get('aeDialog') and row['state']=='SUBMITTED':
            # The command is still in flight behind a modal. The worker ends its turn; the coordinator's watcher owns the stop and the resume.
            output['aeDialog']=row['aeDialog'];output['continuation']={'outcome':'waiting','waitNative':row['requestId']}
            output['instruction']='After Effects is blocked by a dialog Neural must not answer. Do not poll, resubmit or work around it: return outcome waiting with this waitNative now.'
        elif row['state'] not in ('COMPLETED','FAILED'):
            output['continuation']={'outcome':'waiting','waitMedia':[row['mediaJobId']]} if row.get('mediaJobId') else {'outcome':'waiting','waitNative':row['requestId']} if row['kind']!='media' else {'outcome':'blocked','reason':'Mechanical admission outcome unknown; reconcile without replay.'}
        return output

    def ae_status(self, requestId, waitSeconds=0):
        self._authorize(reconcile=True)
        if not isinstance(waitSeconds,(int,float)) or not 0<=waitSeconds<=60:raise ValueError('Bounded waitSeconds0..60 required.')
        deadline=time.monotonic()+waitSeconds
        while True:
            row=self._row(requestId)
            # A continuation task has a new scope; it may read (never drive) an already settled request of the same project.
            settled=bool(row) and row.get('project')==self.scope['project'] and row.get('state') in ('COMPLETED','FAILED')
            if not row or row['kind']=='media' or (row.get('scope')!=self.scope_hash and not settled):raise ValueError('Exact own native request required.')
            if row['state'] in ('COMPLETED','FAILED'):return self._public(row)
            try:
                state=self._bridge_state();command=state['command'] or {};result=state['result'] or {}
                if command.get('id')==row['commandId'] and result.get('_commandId')==row['commandId'] and command.get('status') not in ('pending','running'):
                    if command.get('status') not in ('completed','error') or result.get('ok') is not True:
                        row.update(state='FAILED',error=result.get('error') or 'TonyFX terminal failure.',finished=now())
                    elif Path(row['reportPath']).is_file():
                        report=load(row['reportPath'])
                        if any(report.get(k)!=row[k] for k in ('requestId','commandId','reportId')):raise ValueError('JSX completion report identity mismatch.')
                        row.update(state='COMPLETED' if report.get('ok') is True else 'FAILED',error=report.get('error'),finished=now())
                        if row['kind']=='inspect' and row['state']=='COMPLETED':
                            row['guard']={k:report.get(k) for k in ('projectPath','compId','compName')};row['guard']['signature']=digest(report['structure'])
                        row['report']={k:v for k,v in report.items() if k not in ('structure','afterStructure','newStructure','snapshot')}
                        if report.get('snapshot'):row['report']['snapshotSummary']={'comps':len(report['snapshot']['comps']),'layers':sum(len(c['layers']) for c in report['snapshot']['comps']),'path':row['reportPath'],'readWith':'read_artifact jsonPointer /snapshot/comps/0/layers/0'}
                    else:row.update(state='UNKNOWN',error='TonyFX returned but own JSX report is absent. Never replay.')
                    row['resultPath']=str(Path(row['folder'])/'bridge-result.json');atomic(row['resultPath'],result)
                    row['resultSha256']=hashlib.sha256(Path(row['resultPath']).read_bytes()).hexdigest()
                    if Path(row['reportPath']).is_file():row['reportSha256']=hashlib.sha256(Path(row['reportPath']).read_bytes()).hexdigest()
                elif command.get('id') and command['id']!=row['commandId']:row.update(state='UNKNOWN',error='Bridge command changed. Reconcile; never replay.')
            except (ValueError,OSError) as error:row.update(state='UNKNOWN',error=str(error))
            if row['state']=='SUBMITTED' and time.time()-row.get('dialogChecked',0)>=DIALOG_INTERVAL:
                row['dialogChecked']=time.time()
                if self._ae_dialog(row):
                    with connect(self.database) as db:self._save(db,row)
                    return self._public(row)
            if row['state'] in ('COMPLETED','FAILED') or time.monotonic()>=deadline:
                if row['state'] not in ('COMPLETED','FAILED'):
                    crash=row.get('aeCrash')  # Between probes the last known crash stands.
                    if time.time()-row.get('crashChecked',0)>=CRASH_INTERVAL:
                        row['crashChecked']=time.time();crash=self._ae_crash(row)
                    if crash:row.update(state='UNKNOWN',aeCrash=crash,error=crash['message'])
                    elif (command.get('id')==row['commandId'] and command.get('status') in ('pending','running') and row['state']=='SUBMITTED'):
                        # A bounded status read is not an execution deadline. Keep the
                        # known request in flight; the app watcher owns completion.
                        row.pop('aeCrash',None);row.pop('error',None)
                    else:row.pop('aeCrash',None);row.update(state='UNKNOWN',error=row.get('error') or 'Bounded wait ended without complete matching result and own report. Never replay.')
                with connect(self.database) as db:self._save(db,row)
                return self._public(row)
            time.sleep(min(.2,max(0,deadline-time.monotonic())))
    def _ae_dialog(self,row):
        """Deterministic modal handling for the single native writer. True while an unhandled modal blocks After Effects.

        Plain one-button notifications are acknowledged and logged by GuardedDesktop.
        An application-drawn modal must persist before it counts, so a brief busy state is not a blocker.
        """
        if not DIALOG_HANDLING:return False
        earlier=row.get('aeDialog') or (row.get('aeDialogSeen') or {}).get('blocker') or {}
        spent=row.get('dialogCount',0)
        try:found=self._dialog_probe(earlier.get('hwnd'),max(0,min(5,DIALOG_CAP-spent)))
        except Exception as error:
            row['dialogCheckError']=str(error)[:300];return bool(row.get('aeDialog'))
        row.pop('dialogCheckError',None)
        if found and found.get('dismissed'):row['dialogCount']=spent+len(found['dismissed']);row['dialogsDismissed']=(row.get('dialogsDismissed',[])+found['dismissed'])[-20:]
        if not found or found.get('handled'):
            row.pop('aeDialog',None);row.pop('aeDialogSeen',None);return False
        if earlier.get('hwnd')==found['hwnd']:found=dict(earlier,dismissed=found['dismissed'])
        found['message']='After Effects is waiting on a dialog: "'+found['title']+'" '+found['text'][:400]+' '+found['reason']+' The command is still in flight and must never be replayed.'
        if found['class']!='#32770' and found.get('hwnd'):
            seen=row.get('aeDialogSeen') or {}
            if seen.get('hwnd')!=found['hwnd']:seen={'hwnd':found['hwnd'],'first':time.time()}
            seen['blocker']=found;row['aeDialogSeen']=seen
            if time.time()-seen['first']<DRAWN_MODAL_SECONDS:
                row.pop('aeDialog',None);return False
        row['aeDialog']=found;return True
    def _dialog_probe(self,known,limit=5):
        from guarded_desktop import GuardedDesktop
        process,pid=DIALOG_TARGET or (None,None)
        return GuardedDesktop(self.root).handle_ae_dialogs(process=process,pid=pid,known=known,limit=limit)
    def _ae_processes(self):
        """Start times (UTC ISO) of running AfterFX.exe processes; None when the check itself is unavailable."""
        import subprocess
        try:
            out=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"Get-Process AfterFX -ErrorAction SilentlyContinue | ForEach-Object { $_.StartTime.ToUniversalTime().ToString('o') }"],capture_output=True,text=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except (OSError,subprocess.SubprocessError):return None
        if out.returncode!=0:return None
        return [line.strip() for line in out.stdout.splitlines() if line.strip()]
    def _ae_crash(self,row):
        # A dead or relaunched After Effects never answers; say so instead of letting a worker poll for hours.
        if row.get('kind')=='media' or not row.get('submitted'):return None
        starts=self._ae_processes()
        if starts is None:return None
        submitted=datetime.fromisoformat(row['submitted'])
        def parsed(value):
            try:return datetime.fromisoformat(value.replace('Z','+00:00'))
            except ValueError:return None
        times=[s for s in (parsed(v) for v in starts) if s]
        if not starts:kind='not_running';detail='After Effects is not running: it exited or crashed after this command was submitted.'
        elif times and min(times)>submitted:kind='restarted';detail='After Effects restarted at '+min(times).isoformat()+' after this command was submitted at '+row['submitted']+' (crash).'
        else:return None
        return {'kind':kind,'aeStarts':starts,'submitted':row['submitted'],'checked':now(),'message':detail+' The command did not finish and must never be replayed. Report this blocker now with desktop_observe after-effects evidence; when the TonyFX panel is back it marks the command interrupted, then reopen the saved AEP (ae_inspect, ae_open) and send smaller fixes under new request IDs.'}
    def write_artifact(self,path,text):
        self._authorize()
        if not isinstance(text,str) or len(text.encode('utf-8'))>524288:raise ValueError('Text artifact must be at most512KB.')
        target=(self.project_root/Path(path)).resolve()
        if not inside(target,self.project_root) or inside(target,self.folder) or target in (self.scope_path,Path(self.scope['authorityPath']).resolve()):raise ValueError('Artifact path is outside the admitted write root or private.')
        if target.suffix.lower() not in ('.json','.jsx','.txt','.md','.srt','.vtt','.csv','.tsv'):raise ValueError('Only bounded text/JSON/JSX artifacts are writable.')
        if target.suffix.lower()=='.json':json.loads(text)
        target.parent.mkdir(parents=True,exist_ok=True)
        with self.transaction() as db:
            self._authorize(db)
            if target.exists():
                if target.read_bytes()!=text.encode('utf-8'):raise ValueError('Existing artifact is immutable; choose a new revision filename.')
            else:
                with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
        return {'path':str(target),'bytes':target.stat().st_size,'sha256':digest(text)}

    def _service(self,body):
        from urllib.parse import urlparse
        base=self.scope.get('serviceURL','');url=urlparse(base)
        if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or not self.scope.get('serviceToken'):raise ValueError('Trusted loopback serviceURL/serviceToken required for mechanical tools.')
        request=Request(base.rstrip('/')+'/api/services',encoded(body).encode('utf-8'),headers={'Content-Type':'application/json','X-Neural-Token':self.scope['serviceToken']})
        try:
            with urlopen(request,timeout=15) as response:return json.load(response)['result']
        except HTTPError as error:
            # A 4xx is the engine's definite refusal before admission: nothing ran.
            if 400<=error.code<500:
                try:reason=json.loads(error.read() or b'{}').get('error')
                except Exception:reason=None
                raise Refused(reason or 'Service refused the request (HTTP '+str(error.code)+').')
            raise

    def media_capabilities(self):
        self._authorize();return self._service({'action':'media-capabilities'})

    def media_submit(self,requestId,plan):
        self._authorize()
        if self.scope.get('productionRole')=='supervisor':raise ValueError('Supervisor directs/reviews only; delegate media work to a worker.')
        if not isinstance(plan,dict) or len(encoded(plan))>131072 or not isinstance(plan.get('steps'),list) or len(plan['steps'])>24:raise ValueError('Bounded typed mechanical plan (max24 steps) required.')
        if any(k in plan for k in ('project_id','notification_project')):raise ValueError('Project linkage is forced by trusted scope.')
        def paths(value):
            if isinstance(value,dict):
                for child in value.values():paths(child)
            elif isinstance(value,list):
                for child in value:paths(child)
            elif isinstance(value,str) and (Path(value).is_absolute() or re.match(r'^[A-Za-z]:[\\/]',value)):
                candidate=Path(value).resolve()
                if not any(inside(candidate,root) for root in self.read_roots) and not self._completed_media_output(candidate):raise ValueError('Mechanical input path is outside admitted source roots: '+str(candidate))
        paths(plan)
        allowed=set(self.media_capabilities()['operations'])
        if any(step.get('operation') not in allowed for step in plan['steps']):raise ValueError('Native dispatch/assembly/publication is forbidden through mechanical tools.')
        row,new=self._new(requestId,'media',{'plan':plan})
        if not new:return self._public(row)
        # INTENT persisted before HTTP admission. A lost response is never re-submitted.
        try:
            self._authorize();result=self._service({'action':'media-submit','project':self.scope['project'],'plan':plan})
            identity=result.get('id') or result.get('job_id')
            if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',identity):raise ValueError('Mechanical engine did not return an exact job ID.')
            row.update(state='SUBMITTED',mediaJobId=identity,submitted=now())
        except Refused as error:row.update(state='FAILED',error='Engine refused the plan; nothing ran: '+str(error),finished=now())
        except Exception as error:row.update(state='UNKNOWN',error=str(error))
        with connect(self.database) as db:self._save(db,row)
        return self._public(row)

    def media_status(self,jobId,waitSeconds=0):
        self._authorize(reconcile=True)
        if not isinstance(waitSeconds,(int,float)) or not 0<=waitSeconds<=60:raise ValueError('Bounded waitSeconds0..60 required.')
        with connect(self.database) as db:
            owner=next((json.loads(raw) for raw, in db.execute('SELECT body FROM requests') if (json.loads(raw).get('scope')==self.scope_hash or json.loads(raw).get('project')==self.scope['project']) and json.loads(raw).get('mediaJobId')==jobId),None)
        if not owner:
            # The coordinator's own technical job has no gateway row; its JOB.json names the project it belongs to.
            try:owner=len(str(jobId))==32 and str(jobId).isalnum() and load(self.root/'data/local-ops/jobs'/jobId/'JOB.json').get('project')==self.scope['project']
            except (OSError,ValueError):owner=None
        if not owner:raise ValueError('Only a mechanical job of this project can be read.')
        deadline=time.monotonic()+waitSeconds
        while True:
            result=self._service({'action':'media-job','id':jobId})
            if result.get('notification_project') not in (None,self.scope['project']):raise ValueError('Mechanical job project mismatch.')
            if result.get('status') not in ('QUEUED','RUNNING','CANCELLING') or time.monotonic()>=deadline:break
            time.sleep(min(.2,max(0,deadline-time.monotonic())))
        job_root=self.root/'data/local-ops/jobs'/jobId
        if job_root.is_dir():
            # Tell the worker where the outputs are instead of leaving it to guess folder names.
            result=dict(result,readRoot=str(job_root.resolve()),readHint=r'read_artifact <readRoot>\<stepId>\<output name>; only completed same-project hash-verified outputs are admitted.')
        return result

    def desktop_observe(self,target='neural-studio-2'):
        """Fresh pixels of one allowlisted window. Observation only: nothing is launched, focused or clicked."""
        self._authorize(reconcile=True)
        from guarded_desktop import GuardedDesktop
        desktop=GuardedDesktop(self.root);return desktop.image(desktop.observe(target))

    def ae_bootstrap(self,requestId,guard,width,height,fps,duration):
        self._authorize()
        s=self.scope
        if s.get('allowBootstrap') is not True or s.get('allowMutation') is not True:raise ValueError('Explicit trusted bootstrap and mutation authority required.')
        if type(width) is not int or type(height) is not int or not 16<=width<=8192 or not 16<=height<=8192 or not isinstance(fps,(int,float)) or not 1<=fps<=240 or not isinstance(duration,(int,float)) or not 0<duration<=3600:raise ValueError('Bounded native composition dimensions/rate/duration required.')
        target=Path(s.get('aeProjectPath','')).resolve()
        if not inside(target,self.project_root) or target.suffix.lower()!='.aep' or target.exists() or not isinstance(s.get('compName'),str) or not s['compName']:raise ValueError('New scoped AEP filename and exact target comp name required; existing files are never overwritten.')
        expected=self._inspection(guard)
        row,new=self._new(requestId,'bootstrap',{'guard':guard,'width':width,'height':height,'fps':fps,'duration':duration})
        if not new:return self.ae_status(requestId)
        preserved=Path(row['folder'])/'preserved-original.aep'
        code='var preserve=new File('+encoded(str(preserved))+');var target=new File('+encoded(str(target))+');if(target.exists)throw Error("Target AEP already exists");if(app.project.numItems>0||app.project.file){app.project.save(preserve);preserve=new File(preserve.fsName);if(!preserve.exists||preserve.length<=0)throw Error("Preservation copy was not verified");report.preservedProject=preserve.fsName;}app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);app.newProject();var created=app.project.items.addComp('+encoded(s['compName'])+','+str(width)+','+str(height)+',1,'+str(duration)+','+str(fps)+');app.project.save(target);target=new File(target.fsName);if(!target.exists||target.length<=0)throw Error("New AEP save not verified");report.newProjectPath=target.fsName;report.newCompId=created.id;report.newCompName=created.name;report.newStructure=structure(created);'
        return self._publish(row,self._wrapper(row,code,expected,guard))

    def ae_open(self,requestId,guard):
        """Reopen the existing scoped AEP when AE has another/empty project open (crash, restart, stray Save As)."""
        self._authorize()
        s=self.scope
        if s.get('allowMutation') is not True or s['station'] not in ('Director','Edit','Deliver'):raise ValueError('This scope has no native mutation authority.')
        target=Path(s.get('aeProjectPath','')).resolve()
        if not inside(target,self.project_root) or target.suffix.lower()!='.aep' or not target.is_file():raise ValueError('The scoped AEP does not exist; bootstrap it in the build phase.')
        expected=self._inspection(guard)
        if guard['projectPath'] is not None and Path(guard['projectPath']).resolve()==target:raise ValueError('The scoped AEP is already open.')
        row,new=self._new(requestId,'open',{'guard':guard})
        if not new:return self.ae_status(requestId)
        preserved=Path(row['folder'])/'preserved-original.aep'
        code='var preserve=new File('+encoded(str(preserved))+');var target=new File('+encoded(str(target))+');if(!target.exists)throw Error("Scoped AEP does not exist");if(app.project.numItems>0||app.project.file){app.project.save(preserve);preserve=new File(preserve.fsName);if(!preserve.exists||preserve.length<=0)throw Error("Preservation copy was not verified");report.preservedProject=preserve.fsName;}app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);app.open(target);if(!app.project.file||norm(app.project.file.fsName)!==norm(target.fsName))throw Error("Scoped AEP did not open");report.newProjectPath=app.project.file.fsName;'
        return self._publish(row,self._wrapper(row,code,expected,guard))

    def _inspection(self,guard):
        if not isinstance(guard,dict) or set(guard)!= {'projectPath','compId','compName','signature'}:raise ValueError('Exact returned inspect guard required.')
        with connect(self.database) as db:
            for raw, in db.execute('SELECT body FROM requests'):
                row=json.loads(raw)
                if (row.get('scope')==self.scope_hash or row.get('project')==self.scope['project']) and row['kind']=='inspect' and row['state']=='COMPLETED' and Path(row['reportPath']).is_file():
                    report=load(row['reportPath'])
                    if {k:report.get(k) for k in ('projectPath','compId','compName')}=={k:guard[k] for k in ('projectPath','compId','compName')} and digest(report['structure'])==guard['signature']:return report['structure']
        raise ValueError('Guard must match a completed inspection of this project.')


def reconcile_scopes(scope_paths):
    """Collect only existing native receipts; never publish, inspect or replay work."""
    evidence=[]
    for path in scope_paths:
        gateway=ProductionGateway(path,reconciliation_only=True)
        with connect(gateway.database) as db:
            rows=[json.loads(raw) for raw, in db.execute('SELECT body FROM requests')]
        for row in rows:
            if row.get('scope')!=gateway.scope_hash or row.get('kind')=='media' or row.get('state') in ('COMPLETED','FAILED') or not row.get('commandId'):continue
            result=gateway.ae_status(row['requestId'])
            evidence.append({k:result.get(k) for k in ('requestId','commandId','state','reportPath','error')})
    return evidence


def unresolved(projectRoot):
    """Request IDs whose native/media outcome is not yet settled (read-only)."""
    from urllib.parse import quote
    private=Path(projectRoot).resolve(strict=True)/'.neural-gateway'
    if not (private/'registry.json').is_file():return []
    registry=load(private/'registry.json')
    if registry.get('projectRoot')!=str(Path(projectRoot).resolve(strict=True)):raise ValueError('Gateway registry project root mismatch.')
    database=Path(registry['database']).resolve(strict=True)
    with connect('file:'+quote(str(database).replace('\\','/'),safe='/:')+'?mode=ro',uri=True) as db:
        rows=[json.loads(raw) for raw, in db.execute('SELECT body FROM requests')]
    # The shared database contains every project. An old request must not be
    # attributed to each unrelated run merely because they share this database.
    def positively_other_project(row):
        if not isinstance(row.get('folder'),str) or not row['folder']:return False
        folder=Path(row['folder'])
        if not folder.is_absolute():return False
        request_root=folder.parent
        project_root=request_root.parent
        return (request_root!=private and request_root.name=='.neural-gateway'
                and project_root.parent==private.parent.parent
                and row.get('project')==project_root.name)
    # Exclude only positively attributed other-project receipts. Missing, relative
    # or conflicting attribution remains a blocker rather than hiding uncertainty.
    rows=[r for r in rows if not positively_other_project(r)]
    # An admitted mechanical job is owned and settled by the local engine; only its lost admission is uncertain.
    return [r['requestId'] for r in rows if r.get('state') in (('INTENT','UNKNOWN') if r.get('kind')=='media' else ('INTENT','PUBLISHING','SUBMITTED') if r.get('kind')=='inspect' else ('INTENT','PUBLISHING','SUBMITTED','UNKNOWN'))]

def receipts(projectRoot,jobId):
    """Read authenticated gateway records, never arbitrary model-authored result JSON.

    A receipt proves exact transport + own wrapper completion. It does not prove
    artistic acceptance, playback, actual listening or the requested visual effect.
    """
    from urllib.parse import quote
    root=Path(projectRoot).resolve(strict=True);private=root/'.neural-gateway'
    registry=load(private/'registry.json')
    if registry.get('projectRoot')!=str(root):raise ValueError('Gateway registry project root mismatch.')
    database=Path(registry['database']).resolve(strict=True)
    output=[]
    with connect('file:'+quote(str(database).replace('\\','/'),safe='/:')+'?mode=ro',uri=True) as db:
        for raw, in db.execute('SELECT body FROM requests'):
            row=json.loads(raw)
            if row.get('jobId')!=jobId or row.get('state')!='COMPLETED' or row.get('kind') not in ('mutate','bootstrap'):continue
            folder=Path(row['folder']).resolve()
            if not inside(folder,private):raise ValueError('Receipt folder is outside private gateway root.')
            report_path=Path(row['reportPath']).resolve(strict=True);result_path=Path(row['resultPath']).resolve(strict=True)
            if report_path.parent!=folder or result_path.parent!=folder:raise ValueError('Receipt evidence path mismatch.')
            if hashlib.sha256(report_path.read_bytes()).hexdigest()!=row.get('reportSha256') or hashlib.sha256(result_path.read_bytes()).hexdigest()!=row.get('resultSha256'):raise ValueError('Receipt evidence hash mismatch.')
            report,result=load(report_path),load(result_path)
            if report.get('ok') is not True or result.get('ok') is not True or result.get('_commandId')!=row['commandId'] or any(report.get(k)!=row[k] for k in ('requestId','commandId','reportId')):raise ValueError('Native receipt command/report identity mismatch.')
            output.append({k:row.get(k) for k in ('requestId','project','jobId','kind','state','commandId','reportId','reportPath','resultPath','finished')} | {'report':{k:v for k,v in report.items() if k not in ('structure','afterStructure','newStructure','snapshot')}})
    return output
