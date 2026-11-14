"""Fault and event contracts for native production; fixtures never open AE."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from control import Control
from production import Production,CRITERIA


class Providers:
    def __init__(self):self.rows=[];self.outcomes={};self.prepare_packet=None
    def status(self):return copy.deepcopy(self.rows)
    def submit(self,packet,route,model,effort,request):
        row=dict(id='job'+str(len(self.rows)),project=packet['project'],assignmentId=packet['assignmentId'],station=packet['station'],revision=packet['revision'],route=route,model=model,effort=effort,request_id=request,status='QUEUED',created=len(self.rows))
        self.rows.append(row);return copy.deepcopy(row)
    def result(self,key):return copy.deepcopy(self.outcomes[key])

class Native:
    def status(self):return {'unresolved':False,'owner':{'id':'lease','project':'alpha'}}

class Services:
    def signal(self):pass

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=self.root/'workspace.sqlite3'
        (self.root/'knowledge').mkdir();(self.root/'data/provider-jobs').mkdir(parents=True)
        self.p={'id':'alpha','name':'New project','brief':'Build an isolated complete new edit','revision':1,'assignments':{},'messages':[],'productionControl':{}}
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE workspace(id INTEGER PRIMARY KEY,body TEXT)');db.execute('INSERT INTO workspace VALUES(1,?)',(json.dumps({'alpha':self.p}),))
        (self.root/'model_catalog.json').write_text('{"models":[]}')
        self.providers=Providers();self.control=Control(self.root,self.db,self.providers,Native());self.production=Production(self.control,Services());self.control.production=self.production
        self.req=dict(project='alpha',nativeLeaseId='lease',commissioning=True,candidates=[dict(route='claude',model='opus',effort='medium'),dict(route='codex',model='gpt-6.1-terra',effort='medium')])
        self.patch=patch('providers_engine.transport.executable',return_value='fake');self.patch.start()
    def tearDown(self):self.production.shutdown();self.patch.stop();self.temp.cleanup()
    def start(self):return self.production.start(self.req)
    def artifact(self,name='proof.json'):
        p=self.root/'data/projects/alpha'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{"actual":"evidence"}');return str(p)
    def complete(self,phase,extra=None,outcome='complete'):
        row=self.providers.rows[-1];run=self.production.status('alpha')
        with self.control.connection() as db:p=self.control.projects(db)['alpha'];packet=p['assignments'][row['assignmentId']]
        data=dict(packet['resultTemplate']);data.update(summary='Actual completed fixture',production=dict({'phase':phase,'outcome':outcome,'artifacts':[self.artifact()]},**(extra or {})))
        row.update(status='COMPLETED');self.providers.outcomes[row['id']]={'status':'COMPLETED','text':json.dumps(data)}
        self.production.terminal(copy.deepcopy(row));return self.production.status('alpha')
    def media_wait(self,status='FAILED',blocked=False,step_id='song-measure'):
        run=self.production.status('alpha') or self.start()
        for row in self.providers.rows:row['status']='COMPLETED'
        key='a'*32;root=self.root/'data/local-ops/jobs'/key;root.mkdir(parents=True,exist_ok=True)
        (root/'JOB.json').write_text(json.dumps(dict(project='alpha')))
        (root/'PLAN.json').write_text(json.dumps(dict(steps=[dict(id=step_id,operation='audio_measure',args={'input':'song.mp3'})])))
        with self.control.connection() as db:
            run=self.production._load(run['id'],db)
            run.update(state='BLOCKED' if blocked else 'WAIT_MEDIA',waitScope='fixture',waitMedia=[key],waitStarted=__import__('time').time())
            if blocked:run['state_before_block']='WAIT_MEDIA'
            self.production.persist(db,run)
        return run,dict(id=key,status=status,error='Failed gate in '+step_id,steps=[dict(id=step_id,status=status)])


    def test_worker_blocked_with_known_live_native_automatically_waits(self):
        self.start()
        with patch.object(self.production,'known_pending_native',return_value='exact-live-command'), patch.object(self.production.watchers,'submit') as watch:
            run=self.complete('plan',{'issues':['Native request is still running']},outcome='blocked')
        self.assertEqual(run['state'],'WAIT_NATIVE');self.assertEqual(run['waitNative'],'exact-live-command')
        self.assertEqual(run['history'][-1]['result']['deferredOutcome'],'blocked')
        watch.assert_called_once();self.assertEqual(len(self.providers.rows),1)

    def test_real_gateway_receipt_recovers_omitted_wait_and_dispatches_after_completion(self):
        from production_gateway import ProductionGateway,atomic,connect
        self.start();row=self.providers.rows[-1]
        with self.control.connection() as db:packet=self.control.projects(db)['alpha']['assignments'][row['assignmentId']]
        folder=self.root/'data/provider-jobs'/row['id'];folder.mkdir()
        self.production.prepare(row,packet,folder)
        native=self.root/'data/native-ownership.sqlite3'
        with connect(native) as db:
            db.execute('CREATE TABLE owner(id INTEGER PRIMARY KEY,body TEXT)')
            db.execute('INSERT INTO owner VALUES(1,?)',(json.dumps({'id':'lease','project':'alpha'}),))
        bridge=self.root/'synthetic-bridge';bridge.mkdir()
        scope=json.loads((folder/'scope.json').read_text());scope['bridgePath']=str(bridge)
        atomic(folder/'scope.json',scope)
        gateway=ProductionGateway(folder/'scope.json')
        pending=gateway.ae_inspect('one-known-request')
        with patch('production_gateway.ProductionGateway._ae_processes',return_value=None),patch.object(self.production.watchers,'submit'):
            run=self.complete('plan',{'issues':['Still running']},outcome='blocked')
        self.assertEqual(run['state'],'WAIT_NATIVE')
        request=gateway._row('one-known-request')
        atomic(request['reportPath'],{k:request[k] for k in ('requestId','commandId','reportId')}|{'ok':True,'projectPath':None,'compId':None,'compName':None,'structure':'[]'})
        atomic(bridge/'ae_command.json',{'id':pending['commandId'],'status':'completed'})
        atomic(bridge/'ae_mcp_result.json',{'_commandId':pending['commandId'],'ok':True})
        with patch.object(self.production,'dispatch') as dispatch:self.production.watch(run['id'])
        self.assertEqual(self.production.status('alpha')['state'],'READY');dispatch.assert_called_once_with(run['id'])
        self.assertEqual(gateway._row('one-known-request')['state'],'COMPLETED')
        self.assertEqual(len(list(bridge.glob('ae_command.json'))),1)

    def role_request(self):
        from production import PHASES, SUPERVISOR_PHASES
        director=dict(route='codex',model='gpt-6.1-sol',effort='medium')
        reviewer=dict(route='claude',model='opus',effort='medium')
        worker=dict(route='codex',model='gpt-6.1-terra',effort='medium')
        self.req.update(candidates=[director],reviewers=[director,reviewer],phaseCandidates={phase:([reviewer,director] if phase=='goldfish_review' else [director,reviewer]) if phase in SUPERVISOR_PHASES else [worker] for phase in (*PHASES,'repair')})
        return director,reviewer,worker

    def test_routing_direction_applies_once_only_after_provider_boundary(self):
        self.role_request();run=self.start()
        changed=copy.deepcopy(self.req['phaseCandidates'])
        changed['scout']=[dict(route='codex',model='gpt-6-luna',effort='medium')]
        request=dict(project='alpha',revision=1,requestId='lower-cost-workers',text='Gemini unavailable; use Luna and Terra workers.',phaseCandidates=changed)
        with patch.object(self.production.watchers,'submit'):
            steered=self.production.steer(request)
        self.assertNotEqual(steered['phaseCandidates']['scout'],changed['scout'])
        self.assertFalse(self.production.settle_steering(run['id'],request['requestId']))
        for row in self.providers.rows:row['status']='FAILED'
        self.assertTrue(self.production.settle_steering(run['id'],request['requestId']))
        current=self.production.status('alpha');self.assertEqual(current['phaseCandidates'],changed)
        self.assertEqual(self.providers.rows[-1]['model'],'gpt-6-luna')
        count=len(self.providers.rows);self.production.steer(request);self.assertEqual(len(self.providers.rows),count)
        request['phaseCandidates']['scout']=[dict(route='codex',model='gpt-6.1-terra',effort='medium')]
        with self.assertRaisesRegex(ValueError,'routing policy'):self.production.steer(request)

    def test_invalid_routing_direction_does_not_invalidate_current_work(self):
        director,_,_=self.role_request();run=self.start()
        changed=copy.deepcopy(self.req['phaseCandidates']);changed['build']=[director]
        with self.assertRaisesRegex(ValueError,'Reserved directors'):
            self.production.steer(dict(project='alpha',revision=1,requestId='bad-roles',text='Change roles',phaseCandidates=changed))
        self.assertEqual(self.production.status('alpha')['generation'],run['generation'])

    def test_explicit_role_routing_scout_then_director_no_station_extra(self):
        director,reviewer,worker=self.role_request()
        with self.control.connection() as db:
            ps=self.control.projects(db);ps['alpha']['productionControl']['routing']={'Plan':{'candidates':[director]},'Edit':{'candidates':[reviewer]}}
            self.control.save_projects(db,ps)
        run=self.start();self.assertEqual(run['phase'],'scout');self.assertEqual(self.providers.rows[-1]['model'],worker['model'])
        with self.control.connection() as db:
            self.assertEqual(self.control.projects(db)['alpha']['productionControl']['routing']['Plan']['candidates'],[worker])
        run=self.complete('scout');self.assertEqual(run['phase'],'plan');self.assertEqual(self.providers.rows[-1]['model'],director['model'])
        for row in self.providers.rows:row['status']='COMPLETED'
        with self.control.connection() as db:
            run=self.production._load(run['id'],db);run.update(state='READY',phase='build');self.production.persist(db,run)
        self.production.dispatch(run['id'])
        with self.control.connection() as db:
            self.assertEqual(self.control.projects(db)['alpha']['productionControl']['routing']['Edit']['candidates'],[worker])

    def test_directors_rejected_in_every_worker_phase_and_missing_routes(self):
        director,_,_=self.role_request()
        for phase in ('scout','prototype','build','render','repair'):
            original=self.req['phaseCandidates'][phase];self.req['phaseCandidates'][phase]=[director]
            with self.assertRaisesRegex(ValueError,'Reserved directors'):self.start()
            self.req['phaseCandidates'][phase]=original
        self.req['phaseCandidates'].pop('repair')
        with self.assertRaisesRegex(ValueError,'every production phase'):self.start()
        self.assertEqual(self.providers.rows,[])

    def test_role_run_requires_prototype_review_before_full_worker_build(self):
        director,reviewer,worker=self.role_request();self.start();self.complete('scout')
        self.complete('plan',{'blueprint':self.artifact('blueprint.json'),'expect':{'width':1080,'height':1080,'frames':120,'fps':24,'audio':True}})
        run=self.complete('plan_review');self.assertEqual(run['phase'],'prototype');self.assertEqual(self.providers.rows[-1]['model'],worker['model'])
        with patch.object(self.production,'native_proof',return_value={'projectPath':self.artifact('project.aep'),'compId':1,'compName':'NEURAL_MASTER'}):
            run=self.complete('prototype',{'aep':self.artifact('project.aep'),'compId':1,'compName':'NEURAL_MASTER','render':self.artifact('proof.mp4'),'artifacts':[self.artifact('proof.png')]})
        self.assertEqual(run['phase'],'prototype_review')
        with self.control.connection() as db:packet=self.control.projects(db)['alpha']['assignments'][self.providers.rows[-1]['assignmentId']]
        self.assertEqual(packet['contextMode'],'fresh_review');self.assertIn(packet['model'],[director['model'],reviewer['model']])
        run=self.complete('prototype_review');self.assertEqual(run['phase'],'build');self.assertEqual(self.providers.rows[-1]['model'],worker['model'])

    def test_prototype_worker_repairs_still_require_review_before_build(self):
        self.role_request();self.start();self.complete('scout')
        self.complete('plan',{'blueprint':self.artifact('blueprint.json'),'expect':{'width':1080,'height':1080,'frames':120,'fps':24,'audio':True}})
        self.complete('plan_review')
        for _ in range(2):
            run=self.complete('prototype',{'issues':['Repair this prototype']},outcome='repair')
            self.assertEqual(run['phase'],'prototype')
        with patch.object(self.production,'native_proof',return_value={'projectPath':self.artifact('project.aep'),'compId':1,'compName':'NEURAL_MASTER'}):
            run=self.complete('prototype',{'aep':self.artifact('project.aep'),'compId':1,'compName':'NEURAL_MASTER','render':self.artifact('proof.mp4'),'artifacts':[self.artifact('proof.png')]})
        self.assertEqual(run['phase'],'prototype_review')
        run=self.complete('prototype_review',{'issues':['Type proof defect']},outcome='repair')
        self.assertEqual(run['phase'],'prototype')

    def test_supervisor_scope_cannot_mutate_and_has_role(self):
        self.role_request();run=self.start();self.complete('scout')
        row=self.providers.rows[-1]
        with self.control.connection() as db:packet=self.control.projects(db)['alpha']['assignments'][row['assignmentId']]
        folder=self.root/'data/provider-jobs'/row['id'];folder.mkdir()
        self.production.prepare(row,packet,folder)
        scope=json.loads((folder/'scope.json').read_text())
        self.assertEqual(scope['productionRole'],'supervisor');self.assertFalse(scope['allowMutation']);self.assertFalse(scope['allowBootstrap'])

    def test_terminal_source_clipping_returns_to_owner_without_passing_gate_or_replaying(self):
        run,result=self.media_wait()
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            self.production.watch(run['id'])
        after=self.production.status('alpha')
        self.assertEqual(after['phase'],'plan');self.assertEqual(after['state'],'DISPATCHING')
        self.assertEqual(len(self.providers.rows),2)
        correction=after['mediaCorrections'][0]
        self.assertEqual(json.loads(Path(correction['evidence']).read_text())['jobs'][0]['status'],'FAILED')
        self.assertIn('final-render audio gates strict',after['continuationContext'])
        self.assertNotIn('waitMedia',after)
        with self.assertRaisesRegex(ValueError,'settled mechanical-only'):
            self.production.resume_failed_media(run['id'])
        self.assertEqual(len(self.providers.rows),2)

    def test_existing_blocked_media_run_reconciles_exact_failure_via_retry(self):
        run,result=self.media_wait(blocked=True)
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            after=self.production.retry(dict(project='alpha'))
        self.assertEqual(after['phase'],'plan');self.assertEqual(len(self.providers.rows),2)
        self.assertEqual(len(after['mediaCorrections']),1)

    def test_media_correction_rejects_unknown_cancelled_pending_native_and_foreign_evidence(self):
        for state in ('UNKNOWN','CANCELLED','INTERRUPTED'):
            run,result=self.media_wait(status=state)
            with patch('production_gateway.ProductionGateway') as gateway:
                gateway.return_value.media_status.return_value=result
                with self.assertRaisesRegex(ValueError,'reconciliation'):
                    self.production.resume_failed_media(run['id'])
        run,result=self.media_wait(status='RUNNING')
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            self.assertFalse(self.production.resume_failed_media(run['id']))
        run,result=self.media_wait()
        with self.control.connection() as db:
            run['waitNative']='native1';self.production.persist(db,run)
        with self.assertRaises(ValueError):self.production.resume_failed_media(run['id'])
        run,result=self.media_wait();run.pop('waitNative',None)
        with self.control.connection() as db:self.production.persist(db,run)
        (self.root/'data/local-ops/jobs'/('a'*32)/'JOB.json').write_text('{"project":"other"}')
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            with self.assertRaisesRegex(ValueError,'another project'):self.production.resume_failed_media(run['id'])
        self.assertEqual(len(self.providers.rows),1)

    def test_identical_failed_request_with_renamed_step_cannot_loop(self):
        run,result=self.media_wait()
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            self.production.resume_failed_media(run['id'])
        run,result=self.media_wait(step_id='renamed-song-measure')
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            with self.assertRaisesRegex(ValueError,'identical failed work'):self.production.resume_failed_media(run['id'])
        self.assertEqual(len(self.providers.rows),2)

    def test_configured_extra_fallbacks_survive_dispatch_after_run_candidates(self):
        extra=dict(route='claude',model='sonnet',effort='medium')
        with self.control.connection() as db:
            projects=self.control.projects(db);projects['alpha']['productionControl']['routing']={'Director':{'automatic':True,'candidates':[self.req['candidates'][1],extra]}}
            self.control.save_projects(db,projects)
        self.start()
        with self.control.connection() as db:routing=self.control.projects(db)['alpha']['productionControl']['routing']['Director']
        self.assertEqual(routing['candidates'],self.req['candidates']+[extra]);self.assertTrue(routing['automatic'])

    def test_correction_budget_pause_and_unresolved_native_all_prevent_dispatch(self):
        run,result=self.media_wait()
        with self.control.connection() as db:
            run['mediaCorrections']=[dict(fingerprint=str(i)) for i in range(8)]
            self.production.persist(db,run)
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.media_status.return_value=result
            with self.assertRaisesRegex(ValueError,'budget'):self.production.resume_failed_media(run['id'])
        run['mediaCorrections']=[]
        with self.control.connection() as db:self.production.persist(db,run)
        with patch.object(self.control.native,'status',return_value=dict(unresolved=True,owner=dict(id='lease',project='alpha'))):
            with self.assertRaisesRegex(ValueError,'settled native lease'):self.production.resume_failed_media(run['id'])
        self.control.pause('alpha','Human stopped this project')
        with self.assertRaises(ValueError):self.production.resume_failed_media(run['id'])
        self.assertEqual(len(self.providers.rows),1)

    def test_restart_rebinds_only_local_service_not_pinned_scope_authority(self):
        self.production.service_url='http://127.0.0.1:54321/'
        self.production.service_token='new-token-fixture'
        original=dict(serviceURL='http://127.0.0.1:12345/',serviceToken='old-token-fixture',project='alpha',generation=4,authorityPath='pinned-authority',nativeLeaseId='lease')
        with patch('production_gateway.ProductionGateway') as gateway:
            gateway.return_value.scope=copy.deepcopy(original)
            result=self.production.completion_gateway('persisted-scope.json')
            gateway.assert_called_once_with('persisted-scope.json')
            self.assertEqual(result.scope,{**original,'serviceURL':self.production.service_url,'serviceToken':self.production.service_token})

    def test_unapplied_human_direction_prevents_automatic_and_manual_media_correction(self):
        for manual in (False,True):
            run,result=self.media_wait(blocked=manual)
            with self.control.connection() as db:
                run['steering']={'requestId':'new-direction','text':'Change the edit'}
                self.production.persist(db,run)
            with patch('production_gateway.ProductionGateway') as gateway:
                gateway.return_value.media_status.return_value=result
                if manual:
                    with self.assertRaisesRegex(ValueError,'saved direction'):self.production.retry(dict(project='alpha'))
                else:self.production.watch(run['id'])
            after=self.production.status('alpha')
            self.assertEqual(after['state'],'BLOCKED')
            self.assertEqual(after['waitMedia'],['a'*32])
            self.assertNotIn('mediaCorrections',after)
            self.assertEqual(len(self.providers.rows),1)

    def test_requires_live_commission_outside_isolated_commissioning(self):
        self.req['commissioning']=False
        with self.assertRaisesRegex(ValueError,'commissioning'):self.start()
        self.assertEqual(self.providers.rows,[])

    def test_human_question_persists_and_answer_continues_exact_phase_once(self):
        self.start()
        run=self.complete('plan',{'question':{'text':'Choose intro duration','choices':['30 seconds','48 seconds']}},outcome='needs_input')
        self.assertEqual(run['state'],'WAIT_HUMAN')
        count=len(self.providers.rows);self.production.recover()
        self.assertEqual(len(self.providers.rows),count)
        request=dict(project='alpha',runId=run['id'],revision=1,questionId=run['question']['id'],answer='30 seconds')
        resumed=self.control.action(dict(request,action='answer-question'))
        self.assertEqual(resumed['phase'],'plan')
        self.assertEqual(resumed['decisions'][0]['answer'],'30 seconds')
        self.assertEqual(len(self.providers.rows),count+1)
        self.production.answer_question(request)
        self.assertEqual(len(self.providers.rows),count+1)
        with self.assertRaisesRegex(ValueError,'already answered differently'):
            self.production.answer_question(dict(request,answer='48 seconds'))

    def test_human_answer_cannot_resume_paused_or_stale_work(self):
        self.start()
        run=self.complete('plan',{'question':{'text':'Choose intro duration','choices':['30 seconds','48 seconds']}},outcome='needs_input')
        request=dict(project='alpha',runId=run['id'],revision=2,questionId=run['question']['id'],answer='30 seconds')
        with self.assertRaisesRegex(ValueError,'different project revision'):self.production.answer_question(request)
        self.control.pause('alpha','Human owns edit')
        with self.assertRaisesRegex(ValueError,'paused'):self.production.answer_question(dict(request,revision=1))
        self.assertEqual(len(self.providers.rows),1)

    def test_bad_question_is_blocked_without_dispatch_or_fake_human_choice(self):
        self.start()
        run=self.complete('plan',{'question':{'text':'', 'choices':['one']}},outcome='needs_input')
        self.assertEqual(run['state'],'BLOCKED')
        self.assertEqual(len(self.providers.rows),1)

    def test_answer_preserves_question_on_gateway_uncertainty_or_changed_lease(self):
        self.start()
        run=self.complete('plan',{'question':{'text':'Choose intro duration','choices':['30 seconds','48 seconds']}},outcome='needs_input')
        request=dict(project='alpha',runId=run['id'],revision=1,questionId=run['question']['id'],answer='30 seconds')
        registry=Path(run['projectRoot'])/'.neural-gateway/registry.json'
        registry.parent.mkdir();registry.write_text('{}')
        for state in ('UNKNOWN','SUBMITTED'):
            with patch('production_gateway.unresolved',return_value=[{'state':state}]):
                with self.assertRaisesRegex(ValueError,'unsettled native gateway'):self.production.answer_question(request)
            actual=self.production.status('alpha')
            self.assertEqual(actual['state'],'WAIT_HUMAN');self.assertEqual(actual['question']['id'],request['questionId'])
            self.assertFalse(actual.get('decisions'));self.assertEqual(len(self.providers.rows),1)
        with patch.object(self.control.native,'status',return_value={'unresolved':False,'owner':{'id':'another-lease','project':'alpha'}}):
            with self.assertRaisesRegex(ValueError,'exact settled native lease'):self.production.answer_question(request)
        self.assertEqual(self.production.status('alpha')['state'],'WAIT_HUMAN')

    def test_gateway_unknown_cannot_be_hidden_by_a_human_question(self):
        run=self.start();registry=Path(run['projectRoot'])/'.neural-gateway/registry.json'
        registry.parent.mkdir();registry.write_text('{}')
        with patch('production_gateway.unresolved',return_value=[{'state':'UNKNOWN'}]):
            run=self.complete('plan',{'question':{'text':'Choose intro duration','choices':['30 seconds','48 seconds']}},outcome='needs_input')
        self.assertEqual(run['state'],'BLOCKED');self.assertEqual(len(self.providers.rows),1)
        self.assertFalse(run.get('question'))
    def test_exhausted_provider_without_successor_is_not_left_working(self):
        run=self.start();row=self.providers.rows[-1]
        row.update(status='FAILED',result={'failure_kind':'subscription_exhausted','exhaustion_evidence':{'confirmed':True}})
        with self.control.connection() as db:
            current=self.production._load(run['id'],db)
            current.update(state='WAIT_QUOTA_BOUNDARY',jobId=row['id'])
            self.production.persist(db,current)
        with patch.object(self.control,'terminal'):
            self.production.quota_boundary(run['id'],row)
        actual=self.production.status('alpha')
        self.assertEqual(actual['state'],'BLOCKED')
        self.assertIn('no eligible fallback',actual['error'])

    def test_quota_fallback_cannot_skip_unresolved_gateway_report(self):
        run=self.start();row=self.providers.rows[-1]
        row.update(status='FAILED',result={'failure_kind':'subscription_exhausted','exhaustion_evidence':{'confirmed':True}})
        with self.control.connection() as db:
            current=self.production._load(run['id'],db);current.update(state='WAIT_QUOTA_BOUNDARY',jobId=row['id']);self.production.persist(db,current)
        registry=Path(run['projectRoot'])/'.neural-gateway/registry.json';registry.parent.mkdir();registry.write_text('{}')
        with patch('production_gateway.unresolved',return_value=[{'state':'UNKNOWN'}]),patch.object(self.control,'terminal') as fallback:
            self.production.quota_boundary(run['id'],row)
            fallback.assert_not_called()
        self.assertEqual(self.production.status('alpha')['state'],'BLOCKED')
        self.assertEqual(len(self.providers.rows),1)
    def test_measured_audio_clipping_gets_bounded_media_recovery_once_per_event(self):
        run=self.start()
        with self.control.connection() as db:
            current=self.production._load(run['id'],db)
            current.update(state='WAIT_TECHNICAL',phase='render',technicalJob='tech1',render=self.artifact('review.mp4'))
            self.production.persist(db,current)
        event=dict(id='tech1',project='alpha',status='FAILED',error='Failed audio gate',steps=[
            dict(id='decode',status='COMPLETED'),dict(id='audio',status='FAILED',report=dict(clipped_samples=119))])
        self.production.terminal(event)
        actual=self.production.status('alpha')
        self.assertEqual(actual['technicalRecoveries'],1)
        self.assertEqual(actual['phase'],'render')
        self.assertNotEqual(actual['state'],'BLOCKED')
        self.assertIn('audio_gain_db=-2',actual['continuationContext'])
        count=len(self.providers.rows);self.production.terminal(event)
        self.assertEqual(len(self.providers.rows),count)
    def test_paused_edit_never_starts(self):
        self.control.pause('alpha','Human paused edit')
        with self.assertRaisesRegex(ValueError,'unpaused'):self.start()
        self.assertEqual(self.providers.rows,[])
    def test_start_is_durable_no_duplicate_run(self):
        run=self.start();self.assertEqual(len(self.providers.rows),1)
        with self.assertRaises(ValueError):self.start()
        self.assertEqual(self.production.status('alpha')['id'],run['id'])
    def test_two_independent_review_models_required(self):
        self.req['reviewers']=[self.req['candidates'][0]]*2
        with self.assertRaisesRegex(ValueError,'distinct'):self.start()
    def test_plan_requires_actual_blueprint_and_full_expectation(self):
        self.start();run=self.complete('plan')
        self.assertEqual(run['state'],'BLOCKED');self.assertEqual(len(self.providers.rows),1)
    def test_plan_event_advances_once_to_fresh_critique(self):
        self.start();run=self.complete('plan',{'blueprint':self.artifact('blueprint.json'),'expect':dict(width=320,height=320,frames=72,fps='24',audio=True)})
        self.assertEqual(run['phase'],'plan_review');self.assertEqual(len(self.providers.rows),2)
        with self.control.connection() as db:p=self.control.projects(db)['alpha'];pkt=p['assignments'][run['assignmentId']]
        self.assertEqual(pkt['contextMode'],'fresh_review')
        self.production.terminal(copy.deepcopy(self.providers.rows[0]));self.assertEqual(len(self.providers.rows),2)
    def test_plan_review_receives_current_decision_and_downstream_gate_rules(self):
        run=self.start()
        with self.control.connection() as db:
            run=self.production._load(run['id'],db)
            run['continuationContext']='Human selected 30-second setup and reunion; retain later render verification.'
            self.production.persist(db,run)
        run=self.complete('plan',{'blueprint':self.artifact('blueprint.json'),'expect':dict(width=320,height=320,frames=72,fps='24',audio=True)})
        with self.control.connection() as db:
            pkt=self.control.projects(db)['alpha']['assignments'][run['assignmentId']]
        self.assertIn('Human selected 30-second setup and reunion',pkt['task'])
        self.assertIn('downstream acceptance gates',pkt['task'])
        self.assertIn('never marks those checks passed or waives final verification',pkt['task'])
        self.assertEqual(pkt['productionPhase'],'plan_review')
    def test_missing_or_foreign_artifact_cannot_pass(self):
        run=self.start()
        outside=self.root/'foreign.json';outside.write_text('{}')
        with self.assertRaisesRegex(ValueError,'out-of-scope'):self.production.artifact(run,str(outside))
    def test_native_build_cannot_pass_using_text_claim(self):
        self.start();self.complete('plan',{'blueprint':self.artifact('blueprint.json'),'expect':dict(width=320,height=320,frames=72,fps='24',audio=True)})
        self.complete('plan_review')
        result=self.complete('build',{'aep':self.artifact('project.aep'),'compId':1,'compName':'Master'})
        self.assertEqual(result['state'],'BLOCKED');self.assertIn('native',result['error'])
    def test_unknown_never_advances_or_replays(self):
        self.start();row=self.providers.rows[-1];row.update(status='UNKNOWN',error='lost command result')
        self.production.terminal(row);self.assertEqual(self.production.status('alpha')['state'],'BLOCKED');self.assertEqual(len(self.providers.rows),1)
    def test_pause_revokes_authority_before_generation_changes(self):
        self.start();row=self.providers.rows[-1];folder=self.root/'data/provider-jobs'/row['id'];folder.mkdir()
        with self.control.connection() as db:packet=self.control.projects(db)['alpha']['assignments'][row['assignmentId']]
        prepared=self.production.prepare(row,packet,folder);scope=json.loads(Path(prepared['productionScope']).read_text());authority=Path(scope['authorityPath'])
        self.assertFalse(json.loads(authority.read_text())['paused'])
        self.control.pause('alpha','Stop new admissions')
        self.assertTrue(json.loads(authority.read_text())['paused'])
        self.assertFalse(self.control.admitted(row))
    def test_review_requires_all_criteria(self):
        run=self.start()
        with self.control.connection() as db:
            run=self.production._load(run['id'],db);run['phase']='harsh_review';self.production.persist(db,run)
        result=self.complete('harsh_review',{'criteria':{'typography':{'pass':True,'evidence':[self.artifact()]}}})
        self.assertEqual(result['state'],'BLOCKED');self.assertIn('criteria',result['error'])
    def test_repair_budget_stops_repeated_rejected_work(self):
        run=self.start()
        with self.control.connection() as db:
            run=self.production._load(run['id'],db);run['repairs']=run['maxRepairs'];self.production.persist(db,run)
        result=self.complete('plan',{'issues':['Unresolved source clocks']},outcome='repair')
        self.assertEqual(result['state'],'BLOCKED');self.assertIn('budget',result['error']);self.assertEqual(len(self.providers.rows),1)
    def test_restart_recovers_missed_completion_without_replay(self):
        self.start();row=self.providers.rows[-1];run=self.production.status('alpha')
        with self.control.connection() as db:packet=self.control.projects(db)['alpha']['assignments'][row['assignmentId']]
        data=dict(packet['resultTemplate']);data.update(summary='done',production=dict(phase='plan',outcome='complete',artifacts=[self.artifact()],blueprint=self.artifact('blueprint.json'),expect=dict(width=320,height=320,frames=72,fps='24',audio=True)))
        row.update(status='COMPLETED');self.providers.outcomes[row['id']]={'status':'COMPLETED','text':json.dumps(data)}
        self.production.shutdown();self.production=Production(self.control,Services());self.control.production=self.production
        self.production.recover();self.production.pool.shutdown(wait=True);self.production.pool=__import__('concurrent.futures').futures.ThreadPoolExecutor(max_workers=1)
        self.assertEqual(self.production.status('alpha')['phase'],'plan_review');self.assertEqual(len(self.providers.rows),2)
    def test_restart_blocks_lost_dispatch_instead_of_replaying(self):
        self.start();self.providers.rows.clear()
        self.production.shutdown();self.production=Production(self.control,Services());self.control.production=self.production
        self.production.recover()
        self.assertEqual(self.production.status('alpha')['state'],'BLOCKED');self.assertEqual(self.providers.rows,[])
    def test_blocked_phase_retries_once_fixed_but_never_after_native_submit(self):
        self.start();run=self.complete('plan');self.assertEqual(run['state'],'BLOCKED')
        with self.assertRaises(ValueError):self.start()
        run=self.production.retry(dict(project='alpha'));self.assertEqual(run['phase'],'plan');self.assertEqual(len(self.providers.rows),2)
        self.providers.rows[-1]['status']='FAILED';self.production.terminal(copy.deepcopy(self.providers.rows[-1]))
        run=self.production.status('alpha');self.assertEqual(run['state'],'BLOCKED')
        reg=self.root/'data/projects/alpha/.neural-gateway/registry.json';reg.parent.mkdir(parents=True,exist_ok=True);ledger=reg.parent/'ledger.sqlite3';reg.write_text(json.dumps({'database':str(ledger),'projectRoot':str(reg.parent.parent)}))
        import sqlite3;db=sqlite3.connect(ledger);db.execute('CREATE TABLE requests(id TEXT PRIMARY KEY,body TEXT)');db.execute('INSERT INTO requests VALUES(?,?)',('m1',json.dumps({'requestId':'m1','state':'UNKNOWN'})));db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'reconcile'):self.production.retry(dict(project='alpha'))
        self.assertEqual(len(self.providers.rows),2)
    def test_restart_leaves_paused_run_untouched(self):
        self.start();self.control.pause('alpha','Human paused');before=self.production.status('alpha')
        self.production.recover();self.assertEqual(self.production.status('alpha'),before)

if __name__=='__main__':unittest.main()
