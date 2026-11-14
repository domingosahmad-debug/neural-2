import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from providers_engine.gemini import GeminiTransport, parse, session_settings, validate

MODEL='gemini-4-argon-high'
SID='f1e7186a-e8de-4e47-98e1-a78b2815adca'
OTHER='a1e7186a-e8de-4e47-98e1-a78b2815adca'

def events(model=MODEL, sid=SID, status='SUCCESS', response='A scoped plan.', permission='strict'):
    return [json.dumps(x) for x in [
        {'event':'init','conversation_id':sid,'init':{'model':model,'permission_mode':permission}},
        {'event':'step_update','step_update':{'conversation_id':sid,'step_type':'agent_response','text_delta':'partial'}},
        {'event':'result','result':{'conversation_id':sid,'status':status,'response':response,'usage':{'thinking_tokens':42}}}]]

class GeminiTests(unittest.TestCase):
    def test_high_exact_model_only(self):
        validate(MODEL,'high')
        for model,effort in [(MODEL,'medium'),('auto','high'),('gemini-4-argon-medium','high'),('gpt-6.1-sol','high')]:
            with self.subTest(model=model,effort=effort),self.assertRaises(ValueError):validate(model,effort)

    def test_terminal_answer_model_session_and_usage(self):
        result=parse(events(),'COMPLETED',MODEL)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['session_id'],SID)
        self.assertEqual(result['text'],'A scoped plan.')
        self.assertEqual(result['usage'],[{'thinking_tokens':42}])

    def test_session_drift_never_fallback(self):
        result=parse(events(),'COMPLETED',MODEL,OTHER)
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['session_id'],OTHER)
        self.assertNotIn('failure_kind',result)

    def test_model_drift_or_missing_terminal_unknown(self):
        self.assertEqual(parse(events(model='gemini-3.8-flash-high'),'COMPLETED',MODEL)['status'],'UNKNOWN')
        self.assertEqual(parse(events()[:-1],'COMPLETED',MODEL)['status'],'UNKNOWN')

    def test_unknown_cancelled_sticky(self):
        for state in ('UNKNOWN','CANCELLED'):
            self.assertEqual(parse(events(status='ERROR'),'{}'.format(state),MODEL)['status'],state)

    def test_generic_resource_exhausted_never_subscription_classification(self):
        data=events(status='ERROR',response='')
        data.insert(1,'AGY_ERROR: '+json.dumps({'status':'RESOURCE_EXHAUSTED','error_code':429,'short_error':'Individual quota reached'}))
        result=parse(data,'FAILED',MODEL)
        self.assertEqual(result['status'],'FAILED')
        self.assertNotIn('failure_kind',result)
        self.assertNotIn('exhaustion_evidence',result)

    def quota_events(self, model=MODEL, response='Partial response'):
        data=events(model=model,status='ERROR',response=response)
        terminal=json.loads(data[-1]);terminal['result']['error']='Individual quota reached. Please upgrade your subscription to increase your limits. Resets in 3h49m57s.'
        data[-1]=json.dumps(terminal);return data

    def test_terminal_subscription_quota_classifies_exact_provider_error(self):
        result=parse(self.quota_events(),'COMPLETED',MODEL)
        self.assertEqual(result['status'],'FAILED');self.assertEqual(result['failure_kind'],'subscription_exhausted')
        self.assertEqual(result['exhaustion_evidence']['reset_after_seconds'],13797)
        self.assertEqual(result['exhaustion_evidence']['event']['event'],'result')

    def test_quota_words_in_model_response_do_not_trigger_fallback(self):
        text='Individual quota reached. Please upgrade your subscription to increase your limits. Resets in 3h49m57s.'
        for status in ('SUCCESS','ERROR'):
            result=parse(events(status=status,response=text),'COMPLETED',MODEL)
            self.assertNotIn('failure_kind',result)

    def test_quota_does_not_override_unknown_cancelled_or_identity_drift(self):
        cases=[(self.quota_events(),'UNKNOWN',None),(self.quota_events(),'CANCELLED',None),(self.quota_events(model='gemini-3.8-flash-high'),'COMPLETED',None),(self.quota_events(),'COMPLETED',OTHER)]
        for data,state,session in cases:
            result=parse(data,state,MODEL,session)
            self.assertIn(result['status'],('UNKNOWN','CANCELLED'));self.assertNotIn('failure_kind',result)

    def test_generic_or_malformed_terminal_error_is_not_subscription(self):
        for error in ('Individual quota reached','RESOURCE_EXHAUSTED',{'status':429},'Individual quota reached. Please upgrade your subscription to increase your limits. Resets in .'):
            data=self.quota_events();terminal=json.loads(data[-1]);terminal['result']['error']=error;data[-1]=json.dumps(terminal)
            self.assertNotIn('failure_kind',parse(data,'COMPLETED',MODEL))

    def test_unexpected_tool_and_subagent_unknown(self):
        for step in [{'step_type':'tool','tool_name':'run_command'}, {'step_type':'agent_response','subagent_info':{'subagents':[{}]}}]:
            data=events();step['conversation_id']=SID
            data.insert(1,json.dumps({'event':'step_update','step_update':step}))
            self.assertEqual(parse(data,'COMPLETED',MODEL)['status'],'UNKNOWN')

    def test_unsafe_effective_permission_mode_unknown(self):
        self.assertEqual(parse(events(permission='always-proceed'),'COMPLETED',MODEL)['status'],'UNKNOWN')

    def test_malformed_provider_payload_unknown(self):
        self.assertEqual(parse([json.dumps({'event':'result','result':['wrong']})],'COMPLETED',MODEL)['status'],'UNKNOWN')

    def test_contradictory_terminal_id_unknown(self):
        data=events();terminal=json.loads(data[-1]);terminal['result']['conversation_id']=OTHER;data[-1]=json.dumps(terminal)
        self.assertEqual(parse(data,'COMPLETED',MODEL)['status'],'UNKNOWN')

    def test_settings_deny_all_external_actions_and_paid_fallback(self):
        s=session_settings(MODEL)
        self.assertFalse(s['useG1Credits'])
        self.assertEqual(s['modelProvider'],'')
        self.assertEqual(s['toolPermission'],'strict')
        self.assertEqual(set(s['permissions']['deny']),{x+'(*)' for x in ('read_file','write_file','read_url','execute_url','command','mcp')})
        self.assertEqual(s['permissions']['allow'],[])

    def test_transport_enforces_catalog_high_resume_stable_cwd_clean_env(self):
        calls=[]
        def runner(args,cwd,env,prompt,cancel,raw_path,timeout=None):
            calls.append((args,cwd,env,prompt,raw_path))
            if args[-1]=='models':return 'COMPLETED',[MODEL+'\tGemini 4 Argon (High)'],None
            settings=json.loads(Path(args[args.index('--settings')+1]).read_text())
            self.assertFalse(settings['useG1Credits'])
            return 'COMPLETED',events(),None
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            with patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=base/'home'),patch.dict('os.environ',{'GEMINI_API_KEY':'forbidden','GOOGLE_CLOUD_PROJECT':'forbidden'}):
                row={'model':MODEL,'effort':'high','project':'p1','station':'planner'}
                transport=GeminiTransport(runner)
                first=transport.run(row,{'task':'immutable'},base/'job1',SID,threading.Event())
                transport.run(row,{'task':'continuation'},base/'job2',SID,threading.Event())
            self.assertEqual(first['status'],'COMPLETED')
            invocation=calls[1];args,cwd,env,prompt,_=invocation
            self.assertEqual(args[args.index('--effort')+1],'high')
            self.assertEqual(args[args.index('--conversation')+1],SID)
            self.assertEqual(cwd,calls[3][1])
            self.assertNotIn('GEMINI_API_KEY',env);self.assertNotIn('GOOGLE_CLOUD_PROJECT',env)
            self.assertNotIn('--dangerously-skip-permissions',args)
            self.assertEqual(json.loads(prompt)['event'],'user')
            self.assertIn('immutable',json.loads(prompt)['message']['content'])

    def test_missing_catalog_model_prevents_inference(self):
        calls=[]
        def runner(*args,**kwargs):calls.append(args);return 'COMPLETED',['gemini-4-argon-medium\tMedium'],None
        with tempfile.TemporaryDirectory() as temp,patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=Path(temp)/'home'):
            result=GeminiTransport(runner).run({'model':MODEL,'effort':'high'}, {},Path(temp)/'job',None,threading.Event())
        self.assertEqual(len(calls),1)
        self.assertFalse(result['execution_started'])
        self.assertEqual(result['status'],'FAILED')

    def test_ambient_hook_blocks_even_metadata_child(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)/'home';hooks=home/'.gemini/config/hooks.json';hooks.parent.mkdir(parents=True);hooks.write_text('{"hooks":["unsafe"]}')
            with patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=home):
                def runner(*a,**kw):self.fail('configured hooks must not be launched')
                result=GeminiTransport(runner).run({'model':MODEL,'effort':'high'}, {},Path(temp)/'job',None,threading.Event())
            self.assertFalse(result['execution_started'])

class GeminiProductionTests(unittest.TestCase):
    def fixture(self, base, mutation=False, bootstrap=False):
        from providers_engine.production_host import APP_ROOT
        projectroot=base/'project';projectroot.mkdir()
        row={'id':'job-1','project':'p1','revision':2,'assignmentId':'a1','station':'editor','route':'gemini','model':MODEL,'effort':'high','executionClass':'production'}
        template={'schema':'station.v1','project':'p1','revision':2,'assignmentId':'a1','station':'editor','summary':''}
        packet={**template,'controlGeneration':3,'productionCommissioned':mutation,'resultTemplate':template}
        scope={'schema':'neural.production-scope.v1','root':str(APP_ROOT),'project':'p1','revision':2,'assignmentId':'a1','station':'editor','model':MODEL,'jobId':'job-1','generation':3,'allowMutation':mutation,'allowBootstrap':bootstrap,'projectRoot':str(projectroot),'nativeLeaseId':'lease-1','nativeProject':'native-1'}
        path=base/'scope.json';path.write_text(json.dumps(scope));packet['productionScope']=str(path)
        return row,packet

    def test_scoped_config_and_exact_tool_result(self):
        from providers_engine.production_host import APP_ROOT,SCRIPT
        for mutation,bootstrap in [(False,False),(False,True),(True,False),(True,True)]:
            with self.subTest(mutation=mutation,bootstrap=bootstrap),tempfile.TemporaryDirectory(dir=APP_ROOT/'data') as temp:
                base=Path(temp);row,packet=self.fixture(base,mutation,bootstrap)
                def runner(args,cwd,env,prompt,cancel,raw_path,timeout=None):
                    if args[-1]=='models':return 'COMPLETED',[MODEL+' High'],None
                    config=json.loads((cwd/'.agents/mcp_config.json').read_text())
                    self.assertEqual(set(config['mcpServers']),{'neural'})
                    server=config['mcpServers']['neural'];tools=server['enabledTools']
                    self.assertEqual(server['args'],[str(SCRIPT),'--scope',packet['productionScope']])
                    self.assertEqual('ae_submit' in tools,mutation)
                    self.assertEqual('ae_bootstrap' in tools,mutation and bootstrap)
                    self.assertIn('media_capabilities',tools)
                    self.assertTrue(all(server['tools'][name]['eager'] for name in tools))
                    settings=json.loads(Path(args[args.index('--settings')+1]).read_text())
                    self.assertEqual(settings['toolPermission'],'request-review')
                    self.assertNotIn('mcp(*)',settings['permissions']['deny'])
                    self.assertEqual(set(settings['permissions']['allow']),{'mcp(neural/'+name+')' for name in tools})
                    self.assertNotIn(packet['productionScope'],prompt)
                    self.assertIn('--json-schema',args)
                    result={**packet['resultTemplate'],'summary':'complete','production':{'outcome':'complete'}}
                    data=events(response=json.dumps(result),permission='request-review')
                    data.insert(1,json.dumps({'event':'step_update','step_update':{'conversation_id':SID,'step_type':'tool','tool_name':'mcp_neural_project_context','tool_info':{'parameters':{}}}}))
                    return 'COMPLETED',data,None
                with patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=base/'home'):
                    result=GeminiTransport(runner).run(row,packet,base/'job',None,threading.Event())
                self.assertEqual(result['status'],'COMPLETED')
                self.assertEqual(result['execution_classification'],'scoped_mcp')
                self.assertEqual(len(result['scope_hash']),64)
                self.assertTrue(GeminiTransport.supports('gemini','production'))

    def test_production_phase_schema_binds_verdict_inside_production(self):
        # Isolated-harness finding 12 Nov: without the phase-bound schema Gemini put the verdict in a sibling 'phase'.
        from providers_engine.production_host import APP_ROOT
        with tempfile.TemporaryDirectory(dir=APP_ROOT/'data') as temp:
            base=Path(temp);row,packet=self.fixture(base);packet['productionPhase']='plan';seen={}
            def runner(args,cwd,env,prompt,cancel,raw_path,timeout=None):
                if args[-1]=='models':return 'COMPLETED',[MODEL+' High'],None
                value=args[args.index('--json-schema')+1];seen['schema']=json.loads(Path(value).read_text() if Path(value).is_file() else value);seen['prompt']=prompt
                result={**packet['resultTemplate'],'summary':'done','production':{'phase':'plan','outcome':'complete','artifacts':[]}}
                data=events(response=json.dumps(result),permission='request-review')
                data.insert(1,json.dumps({'event':'step_update','step_update':{'conversation_id':SID,'step_type':'tool','tool_name':'mcp_neural_project_context','tool_info':{'parameters':{}}}}))
                return 'COMPLETED',data,None
            with patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=base/'home'):
                result=GeminiTransport(runner).run(row,packet,base/'job',None,threading.Event())
            self.assertEqual(result['status'],'COMPLETED')
            props=seen['schema']['properties'];self.assertNotIn('phase',props)
            self.assertEqual(props['production']['properties']['phase']['enum'],['plan'])
            self.assertEqual(props['production']['required'],['phase','outcome','artifacts'])
            self.assertIn('inside production',seen['prompt'])

    def test_context_only_scope_gets_context_tools_and_read_only_server(self):
        from providers_engine.production_host import APP_ROOT,SCRIPT,CONTEXT_TOOLS
        with tempfile.TemporaryDirectory(dir=APP_ROOT/'data') as temp:
            base=Path(temp);row,packet=self.fixture(base,True,True)
            scope=json.loads(Path(packet['productionScope']).read_text());scope['contextOnly']=True
            Path(packet['productionScope']).write_text(json.dumps(scope));seen={}
            def runner(args,cwd,env,prompt,cancel,raw_path,timeout=None):
                if args[-1]=='models':return 'COMPLETED',[MODEL+' High'],None
                seen.update(json.loads((cwd/'.agents/mcp_config.json').read_text())['mcpServers']['neural'])
                result={**packet['resultTemplate'],'summary':'complete','production':{'outcome':'complete'}}
                return 'COMPLETED',events(response=json.dumps(result),permission='request-review'),None
            with patch('providers_engine.gemini.executable',return_value=['official-agy']),patch('providers_engine.gemini.Path.home',return_value=base/'home'):
                result=GeminiTransport(runner).run(row,packet,base/'job',None,threading.Event())
            self.assertEqual(result['status'],'COMPLETED')
            self.assertEqual(seen['args'],[str(SCRIPT),'--scope',packet['productionScope'],'--read-only'])
            self.assertEqual(seen['enabledTools'],list(CONTEXT_TOOLS))
            self.assertFalse({'ae_submit','ae_bootstrap'}&set(seen['enabledTools']))
            self.assertIn('desktop_observe',seen['enabledTools'])

    def test_wrong_generation_prevents_all_children(self):
        from providers_engine.production_host import APP_ROOT
        with tempfile.TemporaryDirectory(dir=APP_ROOT/'data') as temp:
            base=Path(temp);row,packet=self.fixture(base);packet['controlGeneration']=999
            def runner(*a,**kw):self.fail('scope admission must precede all children')
            with patch('providers_engine.gemini.executable',return_value=['official-agy']),self.assertRaisesRegex(ValueError,'generation'):
                GeminiTransport(runner).run(row,packet,base/'job',None,threading.Event())

    def test_mcp_server_or_unallowed_tool_never_accepted(self):
        for name in ('mcp_other_project_context','mcp_neural_ae_submit','call_mcp_tool','run_command'):
            data=events();data.insert(1,json.dumps({'event':'step_update','step_update':{'conversation_id':SID,'step_type':'tool','tool_name':name}}))
            self.assertEqual(parse(data,'COMPLETED',MODEL,tools=['project_context'])['status'],'UNKNOWN')

if __name__=='__main__':unittest.main()
