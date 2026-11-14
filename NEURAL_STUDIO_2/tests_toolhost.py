"""Fake CLI streams only; no provider inference or native operations."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers_engine.toolhost import ClaudeToolHost


class Lifetime:
    def attach(self, child): self.child = child
    def close(self): pass


class Child:
    def __init__(self, events):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(''.join(json.dumps(e) + '\n' for e in events))
    def wait(self, timeout=None): return 0
    def poll(self): return 0


class ToolHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.calls = []
        self.events = [
            {'type': 'system', 'subtype': 'init', 'model': 'claude-fable-5-2', 'session_id': 'canonical'},
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'read1', 'name': 'Read', 'input': {'file_path': str(self.root / 'image.png')}}]}},
            {'type': 'result', 'subtype': 'success', 'session_id': 'canonical', 'structured_output': {'summary': 'Read supplied evidence', 'nextAction': 'Wait', 'evidence': ['image.png']}}]
        self.host = ClaudeToolHost(popen=self.popen, lifetime_factory=Lifetime)
        self.packet = {'toolMode': 'planning', 'projectRoot': str(self.root), 'project': 'p', 'revision': 2, 'checkpoint': {'id': 'c2'}, 'task': 'Inspect evidence'}
        self.row = {'route': 'claude', 'model': 'claude-fable-5-2', 'effort': 'low'}
    def tearDown(self): self.tmp.cleanup()
    def popen(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[1:3] == ['auth', 'status']:
            return Child([{'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}])
        return Child(self.events)
    def run_host(self, session=None):
        with patch('providers_engine.toolhost.executable', return_value='fake claude.exe'):
            return self.host.run(self.row, self.packet, self.root / 'job evidence', session, threading.Event())
    def test_restricted_argv_paths_structured_result_and_raw_tools(self):
        result = self.run_host()
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(result['session_id'], 'canonical')
        args, options = self.calls[1]
        self.assertEqual(options['cwd'], self.root)
        self.assertEqual(args[args.index('--tools') + 1], 'Read,Glob,Grep')
        self.assertEqual(args[args.index('--permission-mode') + 1], 'dontAsk')
        self.assertEqual(args[args.index('--permission-prompts') + 1], 'none')
        for flag in ('--restricted', '--safe-mode', '--strict-mcp-config', '--json-schema'):
            self.assertIn(flag, args)
        self.assertFalse(any('skip-permissions' in x or x in ('--fork-session', '--fallback-model', '--bare') for x in args))
        self.assertEqual(args[args.index('--model') + 1], self.row['model'])
        self.assertEqual(result['tool_events'][0]['name'], 'Read')
        self.assertIn('tool_use', Path(result['events_path']).read_text())
        self.assertTrue(Path(result['raw_evidence']).is_file())
    def test_canonical_resume_and_mismatch_fail_closed(self):
        self.assertEqual(self.run_host('canonical')['status'], 'COMPLETED')
        args = self.calls[-1][0]
        self.assertEqual(args[args.index('--resume') + 1], 'canonical')
        result = self.run_host('different')
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['session_id'], 'different')
    def test_production_and_invalid_identity_do_not_invoke_cli(self):
        self.packet['toolMode'] = 'production'
        self.assertFalse(self.run_host()['execution_started'])
        self.packet['toolMode'] = 'planning'
        self.assertFalse(self.run_host('../unsafe')['execution_started'])
        self.assertEqual(self.calls, [])
    def test_missing_structure_and_wrong_fable_model_are_unknown(self):
        self.events[-1].pop('structured_output')
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')
        self.events[0]['model'] = 'other-model'
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')
    def test_unexpected_tool_and_cancellation_are_not_success(self):
        self.events[1]['message']['content'][0]['name'] = 'Bash'
        self.assertEqual(self.run_host()['status'], 'UNKNOWN')
        cancel = threading.Event(); cancel.set()
        with patch('providers_engine.toolhost.executable', return_value='fake'):
            result = self.host.run(self.row, self.packet, self.root / 'cancel', None, cancel)
        self.assertEqual(result['status'], 'CANCELLED')
        self.assertFalse(result['execution_started'])
    def test_invalid_mode_model_effort_and_root_fail_before_cli(self):
        for field, value in [('model', 'unregistered'), ('effort', 'high'), ('route', 'codex')]:
            previous = self.row[field]; self.row[field] = value
            self.assertFalse(self.run_host()['execution_started'])
            self.row[field] = previous
        self.packet['projectRoot'] = 'relative'
        self.assertFalse(self.run_host()['execution_started'])
        self.assertEqual(self.calls, [])


if __name__ == '__main__': unittest.main()
