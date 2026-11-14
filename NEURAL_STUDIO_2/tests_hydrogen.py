"""Hydrogen admission and identity regressions. All provider calls are fakes."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers_engine.gemini import GeminiTransport, MODELS, parse, validate
from providers_engine.transport import validate as route_validate
from tests_gemini import events, SID, OTHER
import tests_gemini as fixtures

MODEL = 'gemini-4-hydrogen-high'


class HydrogenTests(unittest.TestCase):
    def test_exact_high_admission_and_catalog_ui_choice(self):
        route_validate('gemini', MODEL, 'high')
        self.assertTrue({'gemini-4-argon-high', 'gemini-3.8-flash-high', MODEL} <= MODELS)
        for model, effort in [(MODEL, 'medium'), (MODEL, 'xhigh'), ('gemini-4-hydrogen-xhigh', 'high'),
                              ('gemini-4-hydrogen', 'high'), ('auto', 'high')]:
            with self.subTest(model=model, effort=effort), self.assertRaises(ValueError):
                validate(model, effort)
        from control import Control
        control = object.__new__(Control)
        control.root = Path(__file__).resolve().parent
        with patch('providers_engine.transport.executable', return_value='installed-cli'):
            rows = control.capabilities()
        choice, = [row for row in rows if row['model'] == MODEL]
        self.assertEqual(choice['route'], 'gemini')
        self.assertEqual(choice['efforts'], ['high'])
        self.assertTrue(choice['available'])
        self.assertEqual(choice['capabilities'], ['supplied_text'])

    def test_observed_model_and_session_must_match(self):
        self.assertEqual(parse(events(model=MODEL), 'COMPLETED', MODEL, SID)['status'], 'COMPLETED')
        for observed in ('gemini-4-argon-high', 'gemini-3.8-flash-high', 'gemini-4-hydrogen-xhigh'):
            with self.subTest(observed=observed):
                result = parse(events(model=observed), 'COMPLETED', MODEL, SID)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertEqual(result['requested_model'], MODEL)
        result = parse(events(model=MODEL, sid=OTHER), 'COMPLETED', MODEL, SID)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['session_id'], SID)

    def test_transport_preserves_hydrogen_high_and_durable_workspace(self):
        calls = []
        def runner(args, cwd, env, prompt, cancel, raw_path, timeout=None):
            calls.append((args, cwd))
            if args[-1] == 'models':
                return 'COMPLETED', [MODEL+'\tGemini 4 Hydrogen (High)'], None
            self.assertEqual(args[args.index('--model')+1], MODEL)
            self.assertEqual(args[args.index('--effort')+1], 'high')
            self.assertEqual(args[args.index('--conversation')+1], SID)
            settings = json.loads(Path(args[args.index('--settings')+1]).read_text())
            self.assertEqual(settings['model'], MODEL)
            self.assertFalse(settings['useG1Credits'])
            self.assertEqual(settings['toolPermission'], 'strict')
            return 'COMPLETED', events(model=MODEL), None
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch('providers_engine.gemini.executable', return_value=['official-agy']), patch('providers_engine.gemini.Path.home', return_value=base/'home'):
                row = {'model': MODEL, 'effort': 'high', 'project': 'p1', 'station': 'planner'}
                first = GeminiTransport(runner).run(row, {}, base/'job1', SID, threading.Event())
                # Reconstruct adapter to model a process restart, retaining saved session identity.
                second = GeminiTransport(runner).run(row, {}, base/'job2', first['session_id'], threading.Event())
            expected = hashlib.sha256(json.dumps(['p1', 'planner', MODEL], separators=(',', ':')).encode()).hexdigest()[:24]
            self.assertEqual(calls[1][1], base/'_gemini-conversations'/expected)
            self.assertEqual(calls[1][1], calls[3][1])
            self.assertEqual(second['status'], 'COMPLETED')
            self.assertEqual(second['session_id'], SID)

    def test_absent_hydrogen_blocks_inference_without_substitution(self):
        calls = []
        def runner(args, *a, **kw):
            calls.append(args)
            return 'COMPLETED', ['gemini-4-argon-high\tArgon High'], None
        with tempfile.TemporaryDirectory() as temp, patch('providers_engine.gemini.executable', return_value=['official-agy']), patch('providers_engine.gemini.Path.home', return_value=Path(temp)/'home'):
            result = GeminiTransport(runner).run({'model': MODEL, 'effort': 'high'}, {}, Path(temp)/'job', None, threading.Event())
        self.assertEqual(result['status'], 'FAILED')
        self.assertFalse(result['execution_started'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], 'models')

    def test_hydrogen_uses_existing_scoped_production_permissions(self):
        from providers_engine.production_host import APP_ROOT, CONTEXT_TOOLS
        with tempfile.TemporaryDirectory(dir=APP_ROOT/'data') as temp:
            base = Path(temp)
            row, packet = fixtures.GeminiProductionTests().fixture(base)
            row['model'] = MODEL
            scope_path = Path(packet['productionScope'])
            scope = json.loads(scope_path.read_text())
            scope.update(model=MODEL, contextOnly=True)
            scope_path.write_text(json.dumps(scope))
            def runner(args, cwd, env, prompt, cancel, raw_path, timeout=None):
                if args[-1] == 'models': return 'COMPLETED', [MODEL+' High'], None
                server = json.loads((cwd/'.agents/mcp_config.json').read_text())['mcpServers']['neural']
                self.assertEqual(server['enabledTools'], list(CONTEXT_TOOLS))
                self.assertIn('--read-only', server['args'])
                self.assertFalse({'ae_submit', 'ae_bootstrap'} & set(server['enabledTools']))
                result = {**packet['resultTemplate'], 'summary': 'complete', 'production': {'outcome': 'complete'}}
                return 'COMPLETED', events(model=MODEL, response=json.dumps(result), permission='request-review'), None
            with patch('providers_engine.gemini.executable', return_value=['official-agy']), patch('providers_engine.gemini.Path.home', return_value=base/'home'):
                result = GeminiTransport(runner).run(row, packet, base/'job', SID, threading.Event())
            self.assertEqual(result['status'], 'COMPLETED')
            self.assertEqual(result['session_id'], SID)
            self.assertEqual(result['execution_classification'], 'scoped_mcp')


if __name__ == '__main__': unittest.main()
