"""No provider inference. Exercise durable admission and owned-child guarantees."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers import ProviderJobs, save
from providers_engine.transport import Transport, validate, DENY


def packet(revision=1):
    return {'project':'p','station':'analysis','assignmentId':'a'+str(revision),'revision':revision,'task':'Return supplied text JSON','requiredCapabilities':['read text','return JSON']}


class FakeTransport:
    def __init__(self, block=False, session='session1'):
        self.calls=[];self.started=threading.Event();self.release=threading.Event();self.block=block;self.session=session
    def run(self,row,packet,folder,session,cancel):
        self.calls.append((row,packet,session));self.started.set()
        if self.block:
            while not self.release.wait(.01):
                if cancel.is_set():return {'status':'CANCELLED','session_id':session,'text':'partial'}
        (folder/'raw.log').write_text('full evidence',encoding='utf-8')
        return {'status':'COMPLETED','session_id':self.session,'text':'{"answer":"OK"}'}


class ProviderTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.owners=[]
    def tearDown(self):
        for owner in self.owners:owner.shutdown()
        self.tmp.cleanup()
    def owner(self,**kw):
        owner=ProviderJobs(self.root,**kw);self.owners.append(owner);return owner
    def submit(self,owner,p=None,request='request1'):
        return owner.submit(p or packet(),'claude','claude-fable-5-2','low',request)
    def test_known_unstarted_cancellation_keeps_canonical_conversation_usable(self):
        fake=FakeTransport();done=threading.Event();owner=self.owner(transport=fake,on_terminal=lambda row:done.set())
        owner.before_start=lambda row:False
        first=self.submit(owner);self.assertTrue(done.wait(2))
        self.assertFalse(owner.result(first['id'])['execution_started']);self.assertEqual(fake.calls,[])
        owner.before_start=lambda row:True;done.clear()
        self.submit(owner,packet(2),'replacement');self.assertTrue(done.wait(2));self.assertEqual(len(fake.calls),1)
    def test_preparation_race_is_known_nonexecution_not_unknown(self):
        fake=FakeTransport();entered=threading.Event();release=threading.Event();done=threading.Event()
        owner=self.owner(transport=fake,on_terminal=lambda row:done.set())
        def prepare(row,p,folder):
            entered.set();release.wait(2);raise ValueError('New direction fenced this packet')
        owner.prepare_packet=prepare;first=self.submit(owner)
        self.assertTrue(entered.wait(2));release.set();self.assertTrue(done.wait(2))
        self.assertEqual(fake.calls,[]);self.assertEqual(owner.result(first['id'])['status'],'FAILED')
        self.assertFalse(owner.result(first['id'])['execution_started'])
        owner.prepare_packet=lambda row,p,folder:p;done.clear()
        self.submit(owner,packet(2),'replacement');self.assertTrue(done.wait(2));self.assertEqual(len(fake.calls),1)
    def test_shared_pause_lock_linearizes_guard_and_running_reservation(self):
        fake=FakeTransport(block=True);owner=self.owner(transport=fake)
        entered=threading.Event();release_guard=threading.Event();pause_attempted=threading.Event();pause_done=threading.Event()
        state={'paused':False};observed=[]
        def guard(row):
            entered.set()
            if not release_guard.wait(2):raise RuntimeError('Fixture guard not released')
            return not state['paused']
        owner.before_start=guard
        row=self.submit(owner)
        self.assertTrue(entered.wait(2))
        def pause():
            pause_attempted.set()
            with owner.admission_lock:
                state['paused']=True
                observed.append(owner.status()[0]['status'])
            pause_done.set()
        thread=threading.Thread(target=pause,daemon=True);thread.start()
        try:
            self.assertTrue(pause_attempted.wait(2))
            self.assertFalse(pause_done.is_set())
            release_guard.set()
            self.assertTrue(pause_done.wait(2));thread.join(timeout=2)
            self.assertEqual(observed,['RUNNING'],'Pause must observe the reservation made atomically with the guard')
            self.assertTrue(fake.started.wait(2))
        finally:
            release_guard.set();fake.release.set()

    def test_pause_winning_shared_lock_prevents_queued_transport(self):
        fake=FakeTransport();owner=self.owner(transport=fake,max_workers=1)
        state={'paused':False};owner.before_start=lambda row:not state['paused']
        release=threading.Event();entered=threading.Event();done=threading.Event()
        def occupy():entered.set();release.wait(2)
        owner.pool.submit(occupy);self.assertTrue(entered.wait(2))
        owner.on_terminal=lambda row:done.set()
        row=self.submit(owner)
        try:
            with owner.admission_lock:state['paused']=True
            release.set()
            self.assertTrue(done.wait(2))
            self.assertEqual(fake.calls,[])
            self.assertEqual(owner.status()[0]['status'],'CANCELLED')
        finally:release.set()

    def test_prestart_terminal_callbacks_hold_neither_provider_nor_admission_lock(self):
        for reason in ('cancel','guard_reject','guard_exception'):
            with self.subTest(reason=reason):
                fake=FakeTransport();owner=ProviderJobs(self.root/reason,transport=fake,max_workers=1);self.owners.append(owner)
                entered=threading.Event();release=threading.Event();done=threading.Event();lock_available=[]
                def occupy():entered.set();release.wait(3)
                owner.pool.submit(occupy);self.assertTrue(entered.wait(2))
                if reason=='guard_reject':owner.before_start=lambda row:False
                if reason=='guard_exception':
                    def broken(row):raise ValueError('Guard failure')
                    owner.before_start=broken
                def terminal(row):
                    acquired=threading.Event()
                    def other_owner():
                        with owner.admission_lock,owner.lock:acquired.set()
                    thread=threading.Thread(target=other_owner,daemon=True);thread.start()
                    lock_available.append(acquired.wait(1))
                    done.set()
                owner.on_terminal=terminal
                row=self.submit(owner)
                if reason=='cancel':owner.cancel(row['id'])
                release.set()
                self.assertTrue(done.wait(2))
                self.assertEqual(lock_available,[True],'Cross-thread callback must acquire both locks without deadlock')
                self.assertEqual(fake.calls,[])
    def test_admission_exception_is_durable_nonexecution_without_transport(self):
        fake=FakeTransport();done=threading.Event();observed=[]
        def terminal(row):
            observed.append((row,(self.root/'data/provider-jobs'/row['id']/'result.json').is_file(),
                             (self.root/'data/provider-jobs'/row['id']/'terminal.json').is_file()))
            done.set()
        owner=self.owner(transport=fake,on_terminal=terminal)
        def broken_guard(row):raise ValueError('Malformed persisted control packet')
        owner.before_start=broken_guard
        row=self.submit(owner)
        self.assertTrue(done.wait(2));self.assertEqual(fake.calls,[])
        self.assertEqual(observed[0][0]['status'],'FAILED');self.assertEqual(observed[0][1:],(True,True))
        self.assertFalse(owner.result(row['id'])['execution_started'])
        owner.shutdown()
        restarted=self.owner(transport=FakeTransport())
        self.assertEqual(restarted.status()[0]['status'],'FAILED')
        self.assertEqual(restarted.transport.calls,[])
        self.assertFalse(restarted.status()[0]['execution_started'])
        replacement=self.submit(restarted,packet(2),'new-request')
        self.assertNotEqual(replacement['id'],row['id'])
    def test_dedupe_immutable_one_active_no_startup_calls(self):
        fake=FakeTransport(block=True);owner=self.owner(transport=fake)
        self.assertEqual(fake.calls,[]);self.assertEqual(owner.status(),[])
        p=packet();row=self.submit(owner,p);self.assertTrue(fake.started.wait(2))
        self.assertEqual(self.submit(owner,p)['id'],row['id']);self.assertEqual(len(fake.calls),1)
        p['task']='Changed after submission'
        self.assertEqual(json.loads((owner.base/row['id']/'packet.json').read_text())['task'],'Return supplied text JSON')
        with self.assertRaisesRegex(ValueError,'different immutable'):self.submit(owner,p)
        with self.assertRaisesRegex(ValueError,'provider attempt'):self.submit(owner,request='request2')
        fake.release.set();owner.shutdown()
    def test_terminal_saved_before_callback_and_persistent_resume(self):
        done=threading.Event();observed=[]
        def terminal(row):
            observed.append((row,(self.root/'data/provider-jobs'/row['id']/'result.json').is_file(),(self.root/'data/provider-jobs'/row['id']/'terminal.json').is_file()));done.set()
        fake=FakeTransport();owner=self.owner(transport=fake,on_terminal=terminal)
        self.submit(owner);self.assertTrue(done.wait(2));owner.shutdown()
        self.assertEqual(observed[0][1:],(True,True))
        next_fake=FakeTransport();second_done=threading.Event();second=self.owner(transport=next_fake,on_terminal=lambda row:second_done.set())
        self.assertEqual(next_fake.calls,[])
        self.assertTrue(second_done.is_set());second_done.clear()
        with self.assertRaisesRegex(ValueError,'provider attempt'):self.submit(second,request='request-other')
        row=self.submit(second,packet(2),'request2');self.assertTrue(second_done.wait(2))
        self.assertEqual(next_fake.calls[0][2],'session1')
        self.assertEqual(second.status()[0]['status'],'COMPLETED')
    def test_restart_unknown_never_replays(self):
        folder=self.root/'data/provider-jobs'/'crash'
        save(folder/'job.json',{'id':'crash','project':'p','assignmentId':'a','station':'analysis','session_key':'key','status':'RUNNING','created':1,'request_id':'r','request_hash':'h'})
        fake=FakeTransport();owner=self.owner(transport=fake)
        self.assertEqual(owner.status()[0]['status'],'UNKNOWN');self.assertEqual(fake.calls,[])
        self.assertTrue((folder/'terminal.json').is_file())
    def test_cancel_running_requires_reconciliation(self):
        fake=FakeTransport(block=True);done=threading.Event();owner=self.owner(transport=fake,on_terminal=lambda row:done.set())
        row=self.submit(owner);self.assertTrue(fake.started.wait(2));owner.cancel(row['id']);self.assertTrue(done.wait(2))
        self.assertEqual(owner.status()[0]['status'],'CANCELLED')
        with self.assertRaisesRegex(ValueError,'reconciliation'):self.submit(owner,packet(2),'request2')
    def test_session_mismatch_is_unknown(self):
        first=FakeTransport();done=threading.Event();owner=self.owner(transport=first,on_terminal=lambda row:done.set())
        self.submit(owner);self.assertTrue(done.wait(2));done.clear()
        owner.transport=FakeTransport(session='changed')
        self.submit(owner,packet(2),'request2');self.assertTrue(done.wait(2))
        self.assertEqual(owner.status()[0]['status'],'UNKNOWN')
        self.assertEqual(next(iter(owner.sessions.values()))['session_id'],'session1')
        self.assertEqual(owner.status()[0]['session_id'],'session1')
    def test_failed_first_turn_preserves_session_across_restart(self):
        class Failed(FakeTransport):
            def run(self,*args):return {'status':'FAILED','session_id':'failed-session','error':'Provider turn failed','execution_started':True}
        done=threading.Event();owner=self.owner(transport=Failed(),on_terminal=lambda row:done.set())
        self.submit(owner);self.assertTrue(done.wait(2));owner.shutdown()
        self.assertEqual(next(iter(owner.sessions.values()))['session_id'],'failed-session')
        # Simulate crash after job persistence but before session index persistence.
        owner.session_path.unlink()
        fake=FakeTransport(session='failed-session');done.clear()
        second=self.owner(transport=fake,on_terminal=lambda row:done.set());done.clear()
        self.submit(second,packet(2),'request2');self.assertTrue(done.wait(2))
        self.assertEqual(fake.calls[0][2],'failed-session')
        self.assertEqual(second.status()[0]['status'],'COMPLETED')
    def test_failed_without_session_blocks_except_definite_pre_execution_failure(self):
        class Failed(FakeTransport):
            execution_started=True
            def run(self,*args):return {'status':'FAILED','error':'no session','execution_started':self.execution_started}
        done=threading.Event();fake=Failed();owner=self.owner(transport=fake,on_terminal=lambda row:done.set())
        self.submit(owner);self.assertTrue(done.wait(2))
        with self.assertRaisesRegex(ValueError,'reconciliation'):self.submit(owner,packet(2),'request2')
        # A definitively rejected CLI command before model execution admits a corrected new assignment.
        p=packet();p.update(station='other',assignmentId='other1');done.clear();fake.execution_started=False
        self.submit(owner,p,'other');self.assertTrue(done.wait(2));done.clear()
        p=packet(2);p.update(station='other',assignmentId='other2')
        self.submit(owner,p,'other2');self.assertTrue(done.wait(2))
    def test_opencode_denies_unknown_and_read_tools(self):
        for key in ('*','read','glob','grep','list','write','shell','websearch','subagent','external_directory'):
            self.assertEqual(DENY[key],'deny')
    def test_opencode_free_limit_is_specific_to_exact_route_not_global_quota(self):
        model='opencode/mimo-v2.6-flash-free'
        calls=[]
        class Rejected(Transport):
            def _run(self,args,work,env,prompt,cancel,raw_path,timeout=None):
                calls.append((args,env))
                if len(calls)==1:return 'COMPLETED',[model+'\n'],None
                event={'type':'error','sessionID':'ses_mimo','error':{'type':'provider.free-limit','status':429,'message':'Free usage limit reached'}}
                return 'COMPLETED',[json.dumps(event)+'\n'],None
        with patch('providers_engine.transport.executable',return_value='opencode-cli.exe'):
            outcome=Rejected().run({'route':'opencode','model':model,'effort':'default'},packet(),self.root,None,threading.Event())
        self.assertEqual(len(calls),2)
        self.assertEqual(outcome['status'],'FAILED')
        self.assertEqual(outcome['session_id'],'ses_mimo')
        self.assertEqual(outcome['requested_model'],model)
        self.assertIn('desktop and other models are not determined',outcome['availability_scope'])
        config=Path(calls[1][1]['OPENCODE_CONFIG_DIR'])/'opencode.json'
        self.assertEqual(json.loads(config.read_text())['permission']['*'],'deny')
        self.assertEqual(calls[1][0][calls[1][0].index('--model')+1],model)
    def test_capability_and_route_fail_before_inference(self):
        fake=FakeTransport();owner=self.owner(transport=fake)
        for capability in ('image','listen','AE','tools','unrecognized'):
            p=packet();p['requiredCapabilities']=[capability]
            with self.assertRaisesRegex(ValueError,'capability'):self.submit(owner,p)
        with self.assertRaises(ValueError):validate('claude','claude-fable-5-2','high')
        with self.assertRaises(ValueError):validate('opencode','openai/gpt-paid',None)
        self.assertEqual(fake.calls,[])
    def test_lifetime_closes_on_child_completion_and_attach_failure(self):
        calls=[]
        class Child:
            def __init__(self):self.stdin=io.StringIO();self.stdout=io.StringIO('evidence\n');self.returncode=0
            def poll(self):return 0
            def wait(self,timeout=None):return 0
        class Lifetime:
            def attach(self,child):calls.append('attach')
            def close(self):calls.append('close')
        transport=Transport(popen=lambda *a,**k:Child(),lifetime_factory=Lifetime)
        status,lines,error=transport._run(['fake'],self.root,{},'',threading.Event(),self.root/'raw.log')
        self.assertEqual(status,'COMPLETED');self.assertEqual(lines,['evidence\n']);self.assertEqual(calls,['attach','close'])
        self.assertIn('transport_exit_code',(self.root/'raw.log').read_text())
        class BadLifetime(Lifetime):
            def attach(self,child):raise OSError('attach failed')
        transport.lifetime_factory=BadLifetime
        with self.assertRaises(OSError):transport._run(['fake'],self.root,{},'',threading.Event(),self.root/'raw2.log')
        self.assertEqual(calls[-1],'close')


if __name__=='__main__':unittest.main()
