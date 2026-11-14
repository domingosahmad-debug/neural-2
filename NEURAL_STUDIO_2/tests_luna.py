"""Exact Luna subscription routing tests; no real provider children."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers_engine.transport import CODEX_MODELS, Transport, validate

MODEL = 'gpt-6-luna'


class LunaTests(unittest.TestCase):
    def test_exact_luna_efforts_and_sol_policy(self):
        self.assertIn(MODEL, CODEX_MODELS)
        for effort in ('low', 'medium', 'high'):
            validate('codex', MODEL, effort)
        for model, effort in [('luna', 'medium'), ('gpt-6.1-luna', 'medium'), ('auto', 'medium'),
                              (MODEL, 'xhigh'), (MODEL, 'default'), ('gpt-6.1-sol', 'high'),
                              ('gpt-6-sol', 'low')]:
            with self.subTest(model=model, effort=effort), self.assertRaises(ValueError):
                validate('codex', model, effort)
        validate('codex', 'gpt-6.1-sol', 'medium')
        validate('codex', 'gpt-6-sol', 'medium')

    def test_luna_catalog_choice_uses_existing_efforts(self):
        from control import Control
        control = object.__new__(Control)
        control.root = Path(__file__).resolve().parent
        with patch('providers_engine.transport.executable', return_value='installed-cli'):
            choices = control.capabilities()
        row, = [row for row in choices if row['model'] == MODEL]
        self.assertEqual(row['route'], 'codex')
        self.assertEqual(row['efforts'], ['low', 'medium', 'high'])
        self.assertTrue(row['available'])

    def test_exact_luna_command_and_saved_session_without_fallback(self):
        for effort in ('low', 'medium', 'high'):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                calls = []
                transport = Transport()
                def runner(args, work, env, prompt, cancel, raw_path, timeout=None):
                    calls.append(args)
                    if args[1:] == ['login', 'status']:
                        return 'COMPLETED', ['Logged in using ChatGPT'], None
                    self.assertEqual(args[args.index('--model')+1], MODEL)
                    self.assertIn('model_reasoning_effort="'+effort+'"', args)
                    self.assertEqual(args[-3:], ['resume', 'saved-luna-session', '-'])
                    (folder/'final.txt').write_text('bounded result')
                    return 'COMPLETED', [json.dumps({'type': 'thread.started', 'thread_id': 'saved-luna-session'}),
                                         json.dumps({'type': 'turn.completed', 'usage': {}})], None
                transport._run = runner
                with patch('providers_engine.transport.executable', return_value='official-codex'), patch('providers_engine.transport.Path.home', return_value=folder/'home'):
                    result = transport.run({'route': 'codex', 'model': MODEL, 'effort': effort}, {}, folder, 'saved-luna-session', threading.Event())
                self.assertEqual(result['status'], 'COMPLETED')
                self.assertEqual(result['requested_model'], MODEL)
                self.assertEqual(result['session_id'], 'saved-luna-session')
                self.assertEqual(len(calls), 2)

    def test_alias_rejected_before_any_child(self):
        transport = Transport()
        transport._run = lambda *a, **kw: self.fail('invalid alias must not launch a child')
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            transport.run({'route': 'codex', 'model': 'luna', 'effort': 'medium'}, {}, Path(temp), None, threading.Event())


if __name__ == '__main__': unittest.main()
