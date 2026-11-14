"""Classify only typed provider rejection events; prose is never quota evidence."""
import copy
import re


SUBSCRIPTION_WINDOWS = {'five_hour', 'seven_day', 'seven_day_opus', 'seven_day_sonnet'}
FREE_MODEL = re.compile(r'opencode/[a-z0-9][a-z0-9_.-]*-free')
# The ChatGPT-subscription Codex CLI reports plan exhaustion as a terminal
# turn.failed whose error object carries only this fixed product refusal.
CODEX_PLAN_LIMIT = re.compile(r"You’ve hit your usage limit\. .*try again at [^.]+\.?")


def classify_failure(route, model, events, status):
    """Return scoped evidence only for an actual terminal FAILED provider outcome.

    Callers retain raw provider logs. This projection preserves the complete
    decisive structured event and does not infer availability of another route.
    """
    if status != 'FAILED':
        return {}
    for event in events:
        if not isinstance(event, dict):
            continue
        confirmed = False
        if route == 'codex' and event.get('type') in ('turn.failed', 'error'):
            error = event.get('error')
            confirmed = isinstance(error, dict) and (
                error.get('code') == 'usage_limit_reached' or error.get('type') == 'usage_limit_reached'
                or (event.get('type') == 'turn.failed' and set(error) == {'message'}
                    and isinstance(error['message'], str) and bool(CODEX_PLAN_LIMIT.fullmatch(error['message']))))
        elif route == 'claude' and event.get('type') == 'rate_limit_event':
            info = event.get('rate_limit_info')
            confirmed = (isinstance(info, dict) and info.get('status') == 'rejected'
                         and info.get('rateLimitType') in SUBSCRIPTION_WINDOWS)
        elif route == 'opencode' and isinstance(model, str) and FREE_MODEL.fullmatch(model):
            error = event.get('error')
            confirmed = (event.get('type') == 'error' and isinstance(error, dict)
                         and error.get('type') == 'provider.free-limit')
        if confirmed:
            return {'failure_kind': 'subscription_exhausted',
                    'exhaustion_evidence': {'route': route, 'model': model,
                                           'event': copy.deepcopy(event)}}
    return {}
