import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from providers_engine.failures import classify_failure
from providers_engine.transport import Transport


CODEX = {'type': 'turn.failed', 'error': {'code': 'usage_limit_reached', 'message': 'Exact structured refusal'}}
CLAUDE = {'type': 'rate_limit_event', 'rate_limit_info': {'status': 'rejected', 'rateLimitType': 'five_hour', 'resetsAt': 123}}
OPEN = {'type': 'error', 'error': {'type': 'provider.free-limit', 'message': 'Exact isolated route refusal'}}


class FailureTests(unittest.TestCase):
    def test_exact_structured_provider_refusals_preserve_event_and_scope(self):
        for route, model, event in [('codex', 'gpt-6.1-sol', CODEX), ('claude', 'opus', CLAUDE),
                                     ('opencode', 'opencode/mimo-v2.6-flash-free', OPEN)]:
            with self.subTest(route=route):
                source = copy.deepcopy(event)
                result = classify_failure(route, model, [source], 'FAILED')
                self.assertEqual(result['failure_kind'], 'subscription_exhausted')
                self.assertEqual(result['exhaustion_evidence'], {'route': route, 'model': model, 'event': event})
                source.clear()
                self.assertEqual(result['exhaustion_evidence']['event'], event)

    def test_actual_codex_plan_refusal_event_is_exhaustion(self):
        event = {'type': 'turn.failed', 'error': {'message': 'You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/settings/usage to purchase more credits or try again at 6:36 PM.'}}
        self.assertEqual(classify_failure('codex', 'gpt-6.1-terra', [event], 'FAILED')['failure_kind'], 'subscription_exhausted')
        for bad in [{'type': 'error', 'message': event['error']['message']},
                    {'type': 'turn.failed', 'error': {'message': event['error']['message'], 'code': 'http_429'}},
                    {'type': 'turn.failed', 'error': {'message': 'usage limit maybe'}}]:
            self.assertEqual(classify_failure('codex', 'gpt-6.1-terra', [bad], 'FAILED'), {})
        self.assertEqual(classify_failure('claude', 'opus', [event], 'FAILED'), {})

    def test_only_failed_outcomes_qualify(self):
        for status in ('UNKNOWN', 'CANCELLED', 'COMPLETED', 'RUNNING', 'QUEUED'):
            self.assertEqual(classify_failure('codex', 'gpt-6.1-sol', [CODEX], status), {})

    def test_prose_generic429_network_auth_and_nested_model_text_are_not_evidence(self):
        for event in [
            {'type': 'error', 'message': 'usage_limit_reached subscription exhausted HTTP429'},
            {'type': 'turn.failed', 'error': {'code': 'http_429', 'message': 'usage_limit_reached'}},
            {'type': 'turn.failed', 'error': {'code': 'authentication_error'}},
            {'type': 'turn.failed', 'error': {'code': 'network_error'}},
            {'type': 'item.completed', 'item': {'text': json.dumps(CODEX)}},
            {'type': 'result', 'result': json.dumps(CLAUDE), 'is_error': True}]:
            for route in ('codex', 'claude', 'opencode'):
                self.assertEqual(classify_failure(route, 'opencode/fake-free', [event], 'FAILED'), {})

    def test_claude_warning_overage_and_unclassified_rejection_not_subscription(self):
        for status, window in [('allowed_warning', 'five_hour'), ('allowed', 'seven_day'),
                               ('rejected', 'overage'), ('rejected', 'unknown'), ('rejected', None)]:
            event = {'type': 'rate_limit_event', 'rate_limit_info': {'status': status, 'rateLimitType': window}}
            self.assertEqual(classify_failure('claude', 'opus', [event], 'FAILED'), {})

    def test_opencode_scope_requires_exact_free_route(self):
        for route, model in [('claude', 'opus'), ('opencode', 'paid/model'),
                              ('opencode', 'opencode/model-free;other'), ('codex', 'gpt-6.1-sol')]:
            self.assertEqual(classify_failure(route, model, [OPEN], 'FAILED'), {})

    def parsed(self, route, model, events, state='FAILED'):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            auth = {'claude': [json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'})],
                    'codex': ['Logged in using ChatGPT'], 'opencode': [model]}[route]
            invocations = [('COMPLETED', auth, None), (state, [json.dumps(e) for e in events], 'test failure')]
            with patch('providers_engine.transport.executable', return_value='fake-cli'), \
                 patch('providers_engine.transport.Path.home', return_value=folder), \
                 patch.object(Transport, '_run', side_effect=invocations):
                return Transport().run({'route': route, 'model': model, 'effort': 'default' if route=='opencode' else 'medium'}, {}, folder, None, threading.Event())

    def test_actual_transport_parser_classifies_failed_structured_events(self):
        for route, model, event in [('codex', 'gpt-6.1-sol', CODEX), ('claude', 'opus', CLAUDE),
                                    ('opencode', 'opencode/mimo-v2.6-flash-free', OPEN)]:
            result = self.parsed(route, model, [event])
            self.assertEqual(result['failure_kind'], 'subscription_exhausted')

    def test_transport_unknown_and_session_mismatch_never_become_quota_fallback(self):
        result = self.parsed('codex', 'gpt-6.1-sol', [CODEX], 'UNKNOWN')
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertNotIn('failure_kind', result)
        result = self.parsed('codex', 'gpt-6.1-sol', [
            {'type': 'thread.started', 'thread_id': 'first'},
            {'type': 'thread.started', 'thread_id': 'changed'}, CODEX])
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertNotIn('failure_kind', result)


if __name__ == '__main__':
    unittest.main()
