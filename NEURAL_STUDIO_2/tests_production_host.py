"""Exercise argv, authority binding and real stream parsing with a fake CLI only."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers_engine.production_host import ProductionHost


class Lifetime:
    def attach(self, child): pass
    def close(self): pass


class Child:
    def __init__(self, events, text=None):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(text if text is not None else ''.join(json.dumps(e) + '\n' for e in events))
    def wait(self, timeout=None): return 0
    def poll(self): return 0


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name).resolve()
        self.work = self.root / 'data/projects/test'; self.work.mkdir(parents=True)
        self.script = self.root / 'station_tools.py'; self.script.write_text('# fake CLI gateway')
        self.scope_path = self.root / 'scope.json'
        self.scope = {'schema': 'neural.production-scope.v1', 'root': str(self.root), 'project': 'p', 'revision': 2,
                      'generation': 4, 'assignmentId': 'a', 'jobId': 'j', 'station': 'Director', 'model': 'claude-fable-5-2',
                      'nativeLeaseId': 'lease', 'nativeProject': 'native-p', 'projectRoot': str(self.work), 'allowMutation': False}
        self.row = {'id': 'j', 'project': 'p', 'revision': 2, 'assignmentId': 'a', 'station': 'Director',
                    'route': 'claude', 'model': 'claude-fable-5-2', 'effort': 'low'}
        self.template = {'schema': 'neural.station-result.v2', 'project': 'p', 'revision': 2, 'station': 'Director', 'assignmentId': 'a', 'summary': ''}
        self.packet = {**self.template, 'resultTemplate': self.template, 'controlGeneration': 4, 'productionScope': str(self.scope_path), 'task': 'Read context only'}
        self.result_text = json.dumps({**self.template, 'summary': 'Context inspected', 'production': {'phase': 'plan', 'outcome': 'blocked', 'artifacts': [], 'issues': ['Native not executed']}}, indent=2)
        self.sid = 'canonical'; self.calls = []; self.unexpected = False; self.wrong_model = False
        self.host = ProductionHost(popen=self.popen, lifetime_factory=Lifetime)
    def tearDown(self): self.tmp.cleanup()
    def popen(self, args, **kw):
        self.calls.append((args, kw))
        if args[1:3] == ['auth', 'status']:
            return Child([{'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}])
        if args[1:3] == ['login', 'status']: return Child([], 'Logged in using ChatGPT\n')
        if self.row['route'] == 'claude':
            return Child([{'type': 'system', 'subtype': 'init', 'model': 'other' if self.wrong_model else self.row['model'], 'session_id': self.sid},
                {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 't', 'name': 'Bash' if self.unexpected else 'mcp__neural__project_context', 'input': {}}]}},
                *([{'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't', 'is_error': True, 'content': '<tool_use_error>Error: No such tool available: Bash</tool_use_error>'}]}}] if getattr(self, 'refused', False) else []),
                {'type': 'result', 'subtype': 'success', 'result': self.result_text, 'session_id': self.sid}])
        Path(args[args.index('--output-last-message') + 1]).write_text(self.result_text, encoding='utf-8')
        return Child([{'type': 'thread.started', 'thread_id': self.sid},
                      {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'server': 'rogue' if self.unexpected else 'neural', 'tool': 'project_context'}},
                      {'type': 'turn.completed', 'usage': {}}])
    def run_host(self, session=None):
        self.scope_path.write_text(json.dumps(self.scope), encoding='utf-8')
        with patch('providers_engine.production_host.APP_ROOT', self.root), patch('providers_engine.production_host.SCRIPT', self.script), patch('providers_engine.production_host.executable', return_value='fake cli.exe'):
            return self.host.run(self.row, self.packet, self.root / 'job evidence', session, threading.Event())
    def codex(self):
        self.row.update(route='codex', model='gpt-6.1-sol', effort='medium'); self.scope['model'] = self.row['model']
    def test_claude_scope_only_tools_and_exact_json(self):
        result = self.run_host()
        self.assertEqual(result['status'], 'COMPLETED'); self.assertEqual(result['text'], self.result_text)
        args, kw = self.calls[-1]
        self.assertEqual(kw['cwd'], self.work)
        self.assertEqual(args[args.index('--tools') + 1], '')
        allowed = args[args.index('--allowedTools') + 1]
        self.assertIn('mcp__neural__read_artifact', allowed); self.assertNotIn('ae_submit', allowed)
        config = json.loads(args[args.index('--mcp-config') + 1])
        self.assertEqual(config['mcpServers']['neural']['args'], [str(self.script), '--scope', str(self.scope_path)])
        self.assertEqual(args[args.index('--permission-mode') + 1], 'dontAsk')
        self.assertIn('--strict-mcp-config', args)
        self.assertFalse(any('dangerously' in a or a in ('--restricted', '--bare', '--fork-session', '--fallback-model') for a in args))
        self.assertEqual(result['tool_events'][0]['name'], 'mcp__neural__project_context')
        self.assertTrue(Path(result['events_path']).is_file())
    def test_coordinator_task_schema_binds_verdict_inside_production(self):
        self.packet['productionPhase'] = 'plan'; self.run_host()
        args = self.calls[-1][0]; schema = json.loads(args[args.index('--json-schema') + 1])
        self.assertNotIn('phase', schema['properties'])
        self.assertEqual(schema['properties']['production']['properties']['phase']['enum'], ['plan'])
        self.assertEqual(schema['properties']['production']['required'], ['phase', 'outcome', 'artifacts'])
        declared = schema['properties']['production']['properties']
        for field in ('blueprint', 'expect', 'render', 'aep', 'compId', 'compName', 'criteria', 'issues', 'question', 'waitNative', 'waitMedia'):
            self.assertIn(field, declared)   # schema-strict providers drop undeclared coordinator fields
        import production, providers_engine.production_host as host
        self.assertEqual(tuple(host.CRITERIA), tuple(production.CRITERIA)); self.assertEqual(set(declared['criteria']['properties']), set(production.CRITERIA))
    def test_codex_isolated_config_sandbox_and_resume(self):
        self.codex(); result = self.run_host('canonical')
        self.assertEqual(result['status'], 'COMPLETED'); self.assertEqual(result['text'], self.result_text)
        args = self.calls[-1][0]
        self.assertIn('--ignore-user-config', args); self.assertIn('--ignore-rules', args)
        self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
        self.assertIn('mcp_servers={}', args); self.assertIn('shell_tool', args); self.assertIn('unified_exec', args)
        self.assertNotIn('code_mode_host', args)
        self.assertIn('mcp_servers.neural.tools.project_context.approval_mode="approve"', args)
        self.assertNotIn('mcp_servers.neural.tools.ae_submit.approval_mode="approve"', args)
        self.assertEqual(args[args.index('resume') + 1], 'canonical')
        self.assertTrue(any(a.startswith('mcp_servers.neural.enabled_tools=') and 'ae_submit' not in a for a in args))
    def test_mismatched_scope_and_uncommissioned_mutation_do_not_start(self):
        for key, value in [('project', 'other'), ('generation', 9), ('jobId', 'other'), ('assignmentId', 'other'), ('station', 'Edit'), ('model', 'sonnet')]:
            previous = self.scope[key]; self.scope[key] = value
            self.assertFalse(self.run_host()['execution_started']); self.scope[key] = previous
        self.scope['allowMutation'] = True
        self.assertFalse(self.run_host()['execution_started']); self.assertEqual(self.calls, [])
        self.packet['productionCommissioned'] = True
        self.assertEqual(self.run_host()['status'], 'COMPLETED')
        self.assertIn('ae_submit', self.calls[-1][0][self.calls[-1][0].index('--allowedTools') + 1])
    def test_sessions_models_and_unexpected_tools_fail_closed(self):
        self.assertEqual(self.run_host('different')['status'], 'UNKNOWN')
        self.wrong_model = True; self.assertEqual(self.run_host()['status'], 'UNKNOWN')
        self.wrong_model = False; self.unexpected = True; self.assertEqual(self.run_host()['status'], 'UNKNOWN')
        self.refused = True; result = self.run_host(); self.assertEqual(result['status'], 'COMPLETED'); self.assertEqual(result['refused_tools'], ['Bash']); self.refused = False
        self.codex(); self.assertEqual(self.run_host()['status'], 'UNKNOWN')
    def test_scope_root_and_result_identity_are_checked(self):
        self.scope['projectRoot'] = str(self.root)
        self.assertFalse(self.run_host()['execution_started']); self.assertEqual(self.calls, [])
        self.scope['projectRoot'] = str(self.work)
        self.result_text = json.dumps({**self.template, 'project': 'other', 'summary': 'bad'})
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')
    def test_context_only_server_removes_all_submission_tools(self):
        self.scope['contextOnly'] = True
        self.assertEqual(self.run_host()['status'], 'COMPLETED')
        args = self.calls[-1][0]
        config = json.loads(args[args.index('--mcp-config') + 1])
        self.assertIn('--read-only', config['mcpServers']['neural']['args'])
        allowed = args[args.index('--allowedTools') + 1]
        for forbidden in ('ae_submit', 'ae_inspect', 'write_artifact', 'media_submit', 'ae_bootstrap'):
            self.assertNotIn(forbidden, allowed)


if __name__ == '__main__': unittest.main()
