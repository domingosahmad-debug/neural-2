"""Gateway fixtures only. Synthetic AE in Node, no live native/provider calls."""
import os;os.environ['NEURAL_AE_DIALOGS']='0'  # fixtures never probe or touch the real desktop
import base64,io,json,shutil,sqlite3,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from production_gateway import ProductionGateway,atomic,encoded,receipts,connect
from station_tools import StationTools,serve
NODE=r'''
const fs=require('node:fs'),vm=require('node:vm'),x=JSON.parse(fs.readFileSync(0,'utf8')),files={};let undo=0,ends=0,sup=0,esup=0;
function File(p){this.fsName=p;this.exists=p===x.authorityPath;this.length=100;this.open=()=>true;this.read=()=>JSON.stringify(x.authority);this.write=t=>files[p]=t;this.close=()=>{}}
function CompItem(){Object.assign(this,{id:7,name:x.compName,width:1080,height:1080,pixelAspect:1,frameRate:24,duration:10,numLayers:0})}
const c=new CompItem(),app={version:'fixture24',project:{file:{fsName:x.projectPath},save:function(file){this.file=file;},numItems:1,item:()=>c,activeItem:c,renderQueue:{rendering:false,render:()=>{if(undo>ends)throw Error('Undo group mismatch at render');}}},beginUndoGroup:()=>undo++,endUndoGroup:()=>ends++,beginSuppressDialogs:()=>sup++,endSuppressDialogs:()=>esup++};
try{vm.runInNewContext(x.script,{File,app,CompItem,PropertyType:{PROPERTY:1},JSON,Error,String,Number,Math},{timeout:1000});console.log(JSON.stringify({files,undo,ends,sup,esup,compName:c.name}))}catch(e){console.error(e.stack);process.exit(2)}
'''
class GatewayTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();(self.root/'data').mkdir();self.project=self.root/'project';self.project.mkdir();self.bridge=self.root/'bridge';self.bridge.mkdir();self.db=self.root/'workspace.sqlite3';self.native=self.root/'data/native-ownership.sqlite3'
  self.workspace={'p':{'id':'p','revision':2,'productionControl':{'generation':3,'paused':False},'assignments':{'a':{'assignmentId':'a','revision':2,'station':'Edit','model':'gpt-6.1-terra','status':'external handoff','task':'Exact clocks12.300–14.700'}}}}
  with connect(self.db) as db:db.execute('CREATE TABLE workspace(id INTEGER PRIMARY KEY,body TEXT)');db.execute('INSERT INTO workspace VALUES(1,?)',(encoded(self.workspace),))
  with connect(self.native) as db:db.execute('CREATE TABLE owner(id INTEGER PRIMARY KEY,body TEXT)');db.execute('INSERT INTO owner VALUES(1,?)',(encoded({'id':'lease','project':'native-scope'}),))
  self.scope={'schema':'neural.production-scope.v1','root':str(self.root),'db':str(self.db),'project':'p','revision':2,'generation':3,'assignmentId':'a','jobId':'job','station':'Edit','model':'gpt-6.1-terra','nativeLeaseId':'lease','nativeProject':'native-scope','projectRoot':str(self.project),'artifactRoots':[],'allowMutation':True,'allowBootstrap':False,'authorityPath':str(self.project/'authority.json'),'bridgePath':str(self.bridge),'aeProjectPath':str(self.project/'current.aep'),'compId':7,'compName':'TARGET','serviceURL':'http://127.0.0.1:1/','serviceToken':'secret'}
  self.scope_path=self.root/'scope.json';atomic(self.scope_path,self.scope);self.authority={k:self.scope[k] for k in ('project','revision','generation','assignmentId','jobId','nativeLeaseId','nativeProject')};self.authority['paused']=False;atomic(self.scope['authorityPath'],self.authority);self.gateway=ProductionGateway(self.scope_path)
 def tearDown(self):self.tmp.cleanup()
 def persist(self):
  with connect(self.db) as db:db.execute('UPDATE workspace SET body=? WHERE id=1',(encoded(self.workspace),))

 def test_known_pending_is_not_unknown_but_changed_command_remains_unknown(self):
  self.gateway._ae_processes=lambda:None
  row=self.gateway.ae_inspect('known-pending')
  for state in ('pending','running'):
   atomic(self.bridge/'ae_command.json',{'id':row['commandId'],'status':state})
   out=self.gateway.ae_status('known-pending');self.assertEqual(out['state'],'SUBMITTED');self.assertEqual(out['continuation']['waitNative'],'known-pending')
  atomic(self.bridge/'ae_command.json',{'id':'another-command','status':'completed'})
  self.assertEqual(self.gateway.ae_status('known-pending')['state'],'UNKNOWN')
  atomic(self.bridge/'ae_command.json',{'id':row['commandId'],'status':'pending'})
  self.assertEqual(self.gateway.ae_status('known-pending')['state'],'UNKNOWN')
  self.native_execute(row);self.assertEqual(self.gateway.ae_status('known-pending')['state'],'COMPLETED')

 def test_supervisor_cannot_submit_media(self):
  self.scope['productionRole']='supervisor';atomic(self.scope_path,self.scope)
  gateway=ProductionGateway(self.scope_path)
  with self.assertRaisesRegex(ValueError,'Supervisor'):gateway.media_submit('forbidden',{'steps':[]})

 def test_unresolved_requests_are_confined_to_their_own_project(self):
  from production_gateway import unresolved
  row=self.gateway.ae_inspect('own-pending')
  other=dict(self.gateway._row('own-pending'),project='different-project',requestId='other-pending',folder=str(self.root/'different-project/.neural-gateway/request'))
  with connect(self.gateway.database) as db:self.gateway._save(db,other)
  self.assertEqual(unresolved(self.project),['own-pending'])
  registry=self.project/'.neural-gateway/registry.json'
  value=json.loads(registry.read_text());value['projectRoot']=str(self.root/'different-project');atomic(registry,value)
  with self.assertRaisesRegex(ValueError,'registry project root mismatch'):unresolved(self.project)

 def test_unattributable_native_requests_remain_blockers(self):
  from production_gateway import unresolved
  self.gateway.ae_inspect('own-pending');template=self.gateway._row('own-pending')
  for i,folder in enumerate((None,'garbage','relative/.neural-gateway/request',str(self.root/'bad/request'),str(self.root/'other/.neural-gateway/request'))):
   malformed=dict(template,requestId='malformed-'+str(i),folder=folder)
   with connect(self.gateway.database) as db:self.gateway._save(db,malformed)
  self.assertEqual(set(unresolved(self.project)),{'own-pending',*(f'malformed-{i}' for i in range(5))})

 def test_superseded_scope_can_reconcile_matching_result_but_cannot_submit(self):
  row=self.gateway.ae_inspect('pending-before-direction');self.native_execute(row)
  self.workspace['p']['productionControl']['generation']+=1
  self.workspace['p']['assignments']['a']['status']='superseded';self.persist()
  atomic(self.scope['authorityPath'],{**self.authority,'paused':True})
  with self.assertRaises(ValueError):ProductionGateway(self.scope_path)
  old=ProductionGateway(self.scope_path,reconciliation_only=True)
  self.assertEqual(old.ae_status('pending-before-direction')['state'],'COMPLETED')
  with self.assertRaisesRegex(ValueError,'restricted'):old.ae_inspect('new-forbidden')
  with self.assertRaisesRegex(ValueError,'restricted'):old.write_artifact('forbidden.txt','no')
 def native_execute(self,row,comp='TARGET',authority=None):
  if not shutil.which('node'):self.skipTest('Node synthetic AE unavailable')
  script=Path(self.gateway._row(row['requestId'])['scriptPath']).read_text(encoding='utf-8');result=subprocess.run(['node','-e',NODE],input=json.dumps({'script':script,'authority':authority or self.authority,'authorityPath':self.scope['authorityPath'],'projectPath':self.scope['aeProjectPath'],'compName':comp}),text=True,capture_output=True,timeout=5);self.assertEqual(result.returncode,0,result.stderr);output=json.loads(result.stdout)
  for path,text in output['files'].items():Path(path).write_text(text,encoding='utf-8')
  atomic(self.bridge/'ae_command.json',{'id':row['commandId'],'status':'completed'});atomic(self.bridge/'ae_mcp_result.json',{'_commandId':row['commandId'],'ok':True,'_servicedBy':'TonyFX'});return output
 def inspection(self):
  row=self.gateway.ae_inspect('inspect');self.native_execute(row);return self.gateway.ae_status('inspect')
 def test_inspect_signature_and_mutation_receipt(self):
  done=self.inspection();self.assertEqual(done['state'],'COMPLETED');self.assertEqual(len(done['guard']['signature']),64)
  row=self.gateway.ae_submit('mutate','c.name="CHANGED";return {changed:true};',done['guard']);output=self.native_execute(row);self.assertEqual((output['undo'],output['ends'],output['compName']),(1,1,'CHANGED'));done=self.gateway.ae_status('mutate');self.assertEqual(done['state'],'COMPLETED');self.assertEqual(receipts(self.project,'job')[0]['commandId'],row['commandId'])
  Path(done['reportPath']).write_text('{}')
  with self.assertRaisesRegex(ValueError,'hash mismatch'):receipts(self.project,'job')
 def test_render_batch_has_no_outer_undo_group_and_retains_guards(self):
  guard=self.inspection()['guard']
  jsx='var rq=app.project.renderQueue;rq.render();rq.render();rq.render();app.project.save(new File("other.aep"));return {rendered:3};'
  row=self.gateway.ae_submit('render-batch',jsx,guard);output=self.native_execute(row)
  self.assertEqual((output['undo'],output['ends'],output['sup'],output['esup']),(0,0,1,1))
  done=self.gateway.ae_status('render-batch');self.assertEqual(done['state'],'COMPLETED');self.assertEqual(done['report']['result']['rendered'],3);self.assertTrue(done['report']['pathRestored'])
  row=self.gateway.ae_submit('render-exception','app.project.renderQueue.render();app.project.save(new File("other.aep"));throw Error("render failed");',guard);self.native_execute(row)
  done=self.gateway.ae_status('render-exception');self.assertEqual(done['state'],'FAILED');self.assertTrue(done['report']['pathRestored'])
  row=self.gateway.ae_submit('render-stale',jsx,guard);self.native_execute(row,'MANUAL')
  self.assertEqual(self.gateway.ae_status('render-stale')['state'],'FAILED')
  row=self.gateway.ae_submit('render-paused',jsx,guard);self.native_execute(row,authority={**self.authority,'paused':True})
  self.assertEqual(self.gateway.ae_status('render-paused')['state'],'FAILED')
 def test_structural_and_execution_time_pause_guards(self):
  guard=self.inspection()['guard'];row=self.gateway.ae_submit('mutate','c.name="WRONG";',guard);output=self.native_execute(row,'MANUAL');self.assertEqual(output['compName'],'MANUAL');self.assertEqual(output['undo'],0);self.assertEqual(self.gateway.ae_status('mutate')['state'],'FAILED')
  row=self.gateway.ae_submit('pause','c.name="WRONG";',guard);output=self.native_execute(row,authority={**self.authority,'paused':True});self.assertEqual(output['compName'],'TARGET');self.assertEqual(output['undo'],0);self.assertIn('paused',self.gateway.ae_status('pause')['error'])
 def test_unknown_same_id_reconcile_never_replays(self):
  row=self.gateway.ae_inspect('unknown');self.gateway._ae_processes=lambda:None;self.assertEqual(self.gateway.ae_status('unknown')['state'],'SUBMITTED');self.assertEqual(self.gateway.ae_inspect('unknown')['commandId'],row['commandId'])
  with self.assertRaisesRegex(ValueError,'unresolved'):self.gateway.ae_inspect('replacement')
  self.native_execute(row);self.assertEqual(self.gateway.ae_status('unknown')['state'],'COMPLETED')
 def test_ae_crash_after_submit_reports_blocker_without_replay(self):
  import production_gateway;self.addCleanup(setattr,production_gateway,'CRASH_INTERVAL',production_gateway.CRASH_INTERVAL);production_gateway.CRASH_INTERVAL=0
  row=self.gateway.ae_inspect('crashy');self.gateway._ae_processes=lambda:[]
  out=self.gateway.ae_status('crashy');self.assertEqual(out['state'],'UNKNOWN');self.assertEqual(out['aeCrash']['kind'],'not_running');self.assertEqual(out['continuation']['outcome'],'blocked');self.assertIn('never be replayed',out['error'])
  self.gateway._ae_processes=lambda:['2099-01-01T00:00:00+00:00'];self.assertEqual(self.gateway.ae_status('crashy')['aeCrash']['kind'],'restarted')
  self.assertEqual(self.gateway.ae_inspect('crashy')['commandId'],row['commandId'])
  self.gateway._ae_processes=lambda:['2000-01-01T00:00:00+00:00'];self.assertEqual(self.gateway.ae_status('crashy')['continuation']['outcome'],'waiting')
  self.gateway._ae_processes=lambda:None;self.assertNotIn('aeCrash',self.gateway.ae_status('crashy'))
 def test_request_immutable_and_native_shell_denied(self):
  guard=self.inspection()['guard']
  for jsx in ('system.callSystem("cmd");','$.evalFile("x");','app.scheduleTask("x",1,false);'):
   with self.assertRaises(ValueError):self.gateway.ae_submit('bad',jsx,guard)
  self.gateway.ae_submit('same','return 1;',guard)
  with self.assertRaisesRegex(ValueError,'immutable'):self.gateway.ae_submit('same','return 2;',guard)
 def test_busy_bridge_and_foreign_lock_preserved(self):
  atomic(self.bridge/'ae_command.json',{'id':'other','status':'running'});before=(self.bridge/'ae_command.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'unresolved'):self.gateway.ae_inspect('busy')
  self.assertEqual((self.bridge/'ae_command.json').read_bytes(),before)
 def test_foreign_lock_not_removed(self):
  import production_gateway as PG
  lock=self.bridge/'tfx_skill_client.lock';lock.write_text('other');PG.LOCK_WAIT,old=.3,PG.LOCK_WAIT
  try:
   with self.assertRaises(FileExistsError):self.gateway.ae_inspect('locked')
  finally:PG.LOCK_WAIT=old
  self.assertEqual(lock.read_text(),'other')
  # Nothing reached the bridge, so the request is a settled failure and the next one is admitted.
  self.assertEqual(self.gateway._row('locked')['state'],'FAILED');self.assertTrue(self.gateway._row('locked')['notSubmitted'])
  self.assertFalse((self.bridge/'ae_command.json').exists())
  lock.unlink();self.assertEqual(self.gateway.ae_inspect('after')['state'],'SUBMITTED')
 def test_lock_of_dead_holder_is_set_aside_not_deleted(self):
  import os,time
  lock=self.bridge/'tfx_skill_client.lock';lock.write_text('dead');old=time.time()-600;os.utime(lock,(old,old))
  self.assertEqual(self.gateway.ae_inspect('stale')['state'],'SUBMITTED')
  kept=list(self.bridge.glob('tfx_skill_client.lock.stale-*'));self.assertEqual(len(kept),1);self.assertEqual(kept[0].read_text(),'dead')
  self.assertFalse(lock.exists());self.assertGreaterEqual(self.gateway._row('stale')['staleLockSetAside'],599)
 def test_busy_bridge_refusal_is_not_unknown(self):
  atomic(self.bridge/'ae_command.json',{'id':'other','status':'running'})
  with self.assertRaisesRegex(ValueError,'unresolved'):self.gateway.ae_inspect('busy')
  self.assertEqual(self.gateway._row('busy')['state'],'FAILED')
  atomic(self.bridge/'ae_command.json',{'id':'other','status':'completed'});atomic(self.bridge/'ae_mcp_result.json',{'_commandId':'other','ok':True})
  self.assertEqual(self.gateway.ae_inspect('next')['state'],'SUBMITTED')
 def test_persisted_pause_revision_generation_model_lease(self):
  for key in ('revision','generation','model','paused'):
   if key=='revision':self.workspace['p']['revision']=9
   elif key=='model':self.workspace['p']['assignments']['a']['model']='other'
   else:self.workspace['p']['productionControl'][key]=9 if key=='generation' else True
   self.persist()
   with self.assertRaises(ValueError):self.gateway.ae_inspect('bad-'+key)
   self.workspace['p']['revision']=2;self.workspace['p']['assignments']['a']['model']='gpt-6.1-terra';self.workspace['p']['productionControl']={'generation':3,'paused':False};self.persist()
  with connect(self.native) as db:db.execute('UPDATE owner SET body=?',(encoded({'id':'wrong','project':'native-scope'}),))
  with self.assertRaisesRegex(ValueError,'lease'):self.gateway.ae_inspect('bad-lease')
 def test_paused_status_reconciles_existing_request(self):
  row=self.gateway.ae_inspect('pending');self.workspace['p']['productionControl']={'generation':4,'paused':True};self.persist();atomic(self.scope['authorityPath'],{**self.authority,'paused':True,'generation':4})
  self.assertEqual(self.gateway.ae_status('pending')['commandId'],row['commandId'])
  with self.assertRaises(ValueError):self.gateway.ae_inspect('new')
 def test_artifacts_immutable_scoped_partial_and_actual_image(self):
  row=self.gateway.write_artifact('evidence/exact.json','{"clock":"12.300"}');self.assertEqual(self.gateway.write_artifact('evidence/exact.json','{"clock":"12.300"}'),row);self.assertTrue(self.gateway.read_artifact('evidence/exact.json',0,5)['partial'])
  for path in ('../escape.json','authority.json','.neural-gateway/override.json'):
   with self.assertRaises(ValueError):self.gateway.write_artifact(path,'{}')
  with self.assertRaises(ValueError):self.gateway.write_artifact('evidence/exact.json','{}')
  with self.assertRaises(ValueError):self.gateway.read_artifact('authority.json')
  from PIL import Image
  Image.new('RGB',(16,16),'red').save(self.project/'proof.png');response=StationTools(self.gateway).handle({'id':1,'method':'tools/call','params':{'name':'read_artifact','arguments':{'path':'proof.png'}}});block=response['result']['content'][1];self.assertEqual(block['type'],'image');self.assertTrue(base64.b64decode(block['data']).startswith(b'\x89PNG'))
 def test_scope_tamper_rejected(self):
  atomic(self.scope_path,{**self.scope,'allowMutation':False})
  with self.assertRaisesRegex(ValueError,'scope changed'):self.gateway.project_context()
 def test_media_own_job_exact_once_and_operation_allowlist(self):
  calls=[]
  def service(body):
   calls.append(body)
   if body['action']=='media-capabilities':return {'operations':{'probe':{}}}
   return {'id':'media-own','status':'COMPLETED','notification_project':'p'}
  plan={'version':1,'title':'Probe','steps':[{'id':'probe','operation':'probe','args':{'input':str(self.project/'input.mp4')}}]}
  with patch.object(self.gateway,'_service',side_effect=service):
   self.assertEqual(self.gateway.media_submit('media',plan)['mediaJobId'],'media-own');self.gateway.media_submit('media',plan);self.assertEqual(len([r for r in calls if r['action']=='media-submit']),1);self.assertEqual(self.gateway.media_status('media-own')['status'],'COMPLETED')
   with self.assertRaises(ValueError):self.gateway.media_status('foreign')
   with self.assertRaises(ValueError):self.gateway.media_submit('native',{**plan,'steps':[{'id':'bad','operation':'native_submit','args':{}}]})
 def test_bootstrap_preservation_order_and_new_scoped_file(self):
  old=self.inspection()['guard'];self.scope.update(allowBootstrap=True,aeProjectPath=str(self.project/'NEW.aep'),compName='NEW_TARGET',compId=None);atomic(self.scope_path,self.scope);self.gateway=ProductionGateway(self.scope_path);row=self.gateway.ae_inspect('bootstrap-inspect')
  report={'requestId':row['requestId'],'commandId':row['commandId'],'reportId':row['reportId'],'ok':True,'projectPath':old['projectPath'],'compId':7,'compName':'TARGET','structure':'prior exact structure'};atomic(row['reportPath'],report);atomic(self.bridge/'ae_command.json',{'id':row['commandId'],'status':'completed'});atomic(self.bridge/'ae_mcp_result.json',{'_commandId':row['commandId'],'ok':True});guard=self.gateway.ae_status('bootstrap-inspect')['guard'];self.gateway.ae_bootstrap('bootstrap',guard,1080,1080,24,10);script=Path(self.gateway._row('bootstrap')['scriptPath']).read_text();self.assertLess(script.index('Preservation copy was not verified'),script.index('app.project.close('));self.assertLess(script.index('app.project.close('),script.index('app.newProject()'));self.assertIn('Target AEP already exists',script)
 def test_mcp_framing_and_restricted_tool_names(self):
  server=StationTools(self.gateway,True);self.assertFalse({'ae_inspect','ae_submit','write_artifact','Bash'}&server.names());response=server.handle({'id':1,'method':'tools/call','params':{'name':'shell','arguments':{}}});self.assertTrue(response['result']['isError'])
  raw=json.dumps({'id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}}).encode()
  for source in (raw+b'\n',b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw):
   sink=io.BytesIO();serve(server,io.BytesIO(source),sink);self.assertIn(b'2025-06-18',sink.getvalue())
 def test_atomic_retries_transient_permission_error(self):
  target=self.project/'atomic-retry.json'
  real_replace=__import__('os').replace
  attempts=[]
  def flaky(src,dst):
   attempts.append(len(attempts))
   if len(attempts)<3:raise PermissionError(5,'Access is denied')
   return real_replace(src,dst)
  with patch('production_gateway.os.replace',side_effect=flaky),patch('production_gateway.time.sleep'):
   atomic(target,{'ok':True})
  self.assertEqual(len(attempts),3)
  self.assertEqual(json.loads(target.read_text(encoding='utf-8')),{'ok':True})

class _ReviewFix:
 def test_stale_lock_that_cannot_be_set_aside_is_bounded(self):
  import os,time,production_gateway as PG
  lock=self.bridge/'tfx_skill_client.lock';lock.write_text('held');old=time.time()-600;os.utime(lock,(old,old))
  PG.LOCK_WAIT,keep=.5,PG.LOCK_WAIT;start=time.time()
  try:
   with unittest.mock.patch('production_gateway.os.rename',side_effect=PermissionError('held open')):
    with self.assertRaises(FileExistsError):self.gateway.ae_inspect('held')
  finally:PG.LOCK_WAIT=keep
  self.assertLess(time.time()-start,5);self.assertEqual(lock.read_text(),'held')
  self.assertEqual(self.gateway._row('held')['state'],'FAILED');self.assertTrue(self.gateway._row('held')['notSubmitted'])
 def test_lock_cleanup_never_fails_a_submitted_command(self):
  import production_gateway as PG
  real=Path.unlink
  def unlink(path,*a,**k):
   if path.name=='tfx_skill_client.lock':raise PermissionError('scanner')
   return real(path,*a,**k)
  with unittest.mock.patch.object(Path,'unlink',unlink):row=self.gateway.ae_inspect('kept')
  self.assertEqual(row['state'],'SUBMITTED')
 def test_dialog_acknowledgements_are_capped_per_command(self):
  import production_gateway as PG
  self.gateway.ae_inspect('capped');self.gateway._ae_processes=lambda:None;limits=[]
  def probe(known,limit=5):
   limits.append(limit);return {'handled':True,'dismissed':[{'title':'After Effects','text':'x','button':'OK','at':1}]*limit} if limit else {'handled':False,'hwnd':7,'class':'#32770','title':'After Effects','text':'x','buttons':['OK'],'reason':'allowance spent','dismissed':[],'at':1}
  self.gateway._dialog_probe=probe
  with unittest.mock.patch.multiple(PG,DIALOG_HANDLING=True,DIALOG_INTERVAL=0,DIALOG_CAP=7):
   for _ in range(4):out=self.gateway.ae_status('capped')
  self.assertEqual(limits,[5,2,0,0]);self.assertEqual(self.gateway._row('capped')['dialogCount'],7)
  self.assertEqual(out['state'],'SUBMITTED');self.assertEqual(out['aeDialog']['reason'],'allowance spent')
for _name in [n for n in vars(_ReviewFix) if n.startswith('test_')]:setattr(GatewayTests,_name,vars(_ReviewFix)[_name])
if __name__=='__main__':unittest.main()
