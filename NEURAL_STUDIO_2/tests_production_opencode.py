"""OpenCode free-model production host: argv, isolated project config and stream parsing with a fake CLI only."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from providers_engine.runtime import RuntimeTransport
import tests_production_host as base
Child = base.Child

MODEL = 'opencode/beam-free'


class OpenCodeProduction(unittest.TestCase):
    setUp = base.ProductionTests.setUp; tearDown = base.ProductionTests.tearDown; popen = base.ProductionTests.popen

    def prepare(self, events=None, catalog=MODEL):
        self.row.update(route='opencode', model=MODEL, effort='default'); self.scope['model'] = MODEL
        self.catalog = catalog
        self.events = events if events is not None else [
            {'type': 'step_start', 'sessionID': 'ses_1', 'part': {}},
            {'type': 'tool_use', 'sessionID': 'ses_1', 'part': {'type': 'tool', 'tool': 'neural_project_context', 'state': {'status': 'completed'}}},
            {'type': 'text', 'sessionID': 'ses_1', 'part': {'text': 'Done.\n```json\n' + self.result_text + '\n```'}},
            {'type': 'step_finish', 'sessionID': 'ses_1', 'part': {'tokens': {'input': 1}, 'cost': 0}}]
        self.calls = []; self.host.popen = self.fake

    def fake(self, args, **kw):
        self.calls.append((args, kw))
        if args[1] == 'models': return Child([], self.catalog + '\n')
        return Child(self.events)

    def run_host(self, session=None):
        self.scope_path.write_text(json.dumps(self.scope), encoding='utf-8')
        with patch('providers_engine.production_host.APP_ROOT', self.root), patch('providers_engine.production_host.SCRIPT', self.script), \
             patch('providers_engine.production_host.executable', return_value='opencode-cli.exe'):
            return self.host.run(self.row, self.packet, self.root / 'job evidence', session, threading.Event())

    def test_scoped_tools_deny_all_builtins_and_embedded_json(self):
        self.prepare(); result = self.run_host()
        self.assertEqual(result['status'], 'COMPLETED', result.get('error'))
        self.assertEqual(result['structured_result']['summary'], 'Context inspected'); self.assertEqual(result['session_id'], 'ses_1')
        args, kw = self.calls[-1]
        self.assertEqual(args[1:5], ['run', '--standalone', '--format', 'json']); self.assertEqual(args[args.index('--model') + 1], MODEL)
        folder = Path(kw['cwd']); self.assertEqual(folder, (self.root / 'job evidence').resolve())
        config = json.loads((folder / 'opencode.json').read_text(encoding='utf-8'))
        self.assertEqual(config['permission']['*'], 'deny'); self.assertEqual(config['permission']['bash'], 'deny')
        self.assertEqual(config['permission']['neural_project_context'], 'allow')
        self.assertNotIn('neural_ae_submit', config['permission'])  # read-only scope
        self.assertLess(list(config['permission']).index('*'), list(config['permission']).index('neural_project_context'))
        command = config['mcp']['servers']['neural']['command']
        self.assertEqual(command[1:], [str(self.script), '--scope', str(self.scope_path)])

    def test_mutation_scope_allows_native_tools_and_resume(self):
        self.prepare(); self.scope['allowMutation'] = True; self.packet['productionCommissioned'] = True
        self.events[0]['sessionID'] = self.events[1]['sessionID'] = self.events[2]['sessionID'] = self.events[3]['sessionID'] = 'ses_1'
        result = self.run_host('ses_1'); self.assertEqual(result['status'], 'COMPLETED', result.get('error'))
        args, kw = self.calls[-1]; self.assertEqual(args[args.index('--session') + 1], 'ses_1')
        self.assertEqual(json.loads((Path(kw['cwd']) / 'opencode.json').read_text())['permission']['neural_ae_submit'], 'allow')

    def test_paid_or_effort_or_missing_model_never_starts(self):
        self.prepare(); self.row['model'] = 'opencode/big-pickle'; self.scope['model'] = self.row['model']
        self.assertFalse(self.run_host()['execution_started']); self.assertEqual(self.calls, [])
        self.prepare(); self.row['effort'] = 'high'; self.assertFalse(self.run_host()['execution_started'])
        self.prepare(catalog='opencode/other-free'); result = self.run_host()
        self.assertEqual(result['status'], 'FAILED'); self.assertFalse(result['execution_started']); self.assertEqual(len(self.calls), 1)

    def test_foreign_tool_cost_and_free_limit_fail_closed(self):
        self.prepare(); self.events[1]['part']['tool'] = 'bash'
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')
        self.prepare(); self.events[1]['part'] = {'type': 'tool', 'tool': 'bash', 'state': {'status': 'error'}}
        result = self.run_host(); self.assertEqual(result['status'], 'COMPLETED'); self.assertEqual(result['refused_tools'], ['bash'])
        self.prepare(); self.events[3]['part']['cost'] = 0.01
        result = self.run_host(); self.assertEqual(result['status'], 'FAILED'); self.assertIn('free-only', result['error'])
        self.prepare(events=[{'type': 'step_start', 'sessionID': 'ses_1'}, {'type': 'error', 'sessionID': 'ses_1', 'error': {'type': 'provider.free-limit', 'status': 429}}])
        result = self.run_host(); self.assertEqual(result['status'], 'FAILED'); self.assertIn('429', result['error'])
        self.prepare(); self.events[2]['part']['text'] = 'no json here'
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')

    def test_runtime_admits_opencode_production(self):
        self.assertTrue(RuntimeTransport().supports('opencode', 'production'))


if __name__ == '__main__': unittest.main()
