"""Neural-only context configuration and honest per-turn provider accounting.

Never starts inference, resets a conversation, estimates quota, or changes models.
"""
import math

# Large persistent visual sessions were repeatedly carrying 300–400k tokens.
# Let the provider compact within the SAME thread earlier; preserve full logs,
# revision checkpoints and external evidence. This is not a context-window cap.
AUTO_COMPACT_TOKENS = 160_000


def context_args():
    return ['-c', f'model_auto_compact_token_limit={AUTO_COMPACT_TOKENS}']


FIELDS = {'input_tokens': 'inputTokens', 'output_tokens': 'outputTokens',
          'cache_read_input_tokens': 'cachedInputTokens',
          'reasoning_output_tokens': 'reasoningOutputTokens'}


def counters(value):
    if not isinstance(value, dict): return {}
    return {key: value[wire] for key, wire in FIELDS.items()
            if type(value.get(wire)) in (int, float) and math.isfinite(value[wire]) and value[wire] >= 0}


def begin(leader, turn_id):
    old = counters((leader.get('token_usage') or {}).get('total'))
    leader['turn_usage_tracking'] = {'turn_id': turn_id, 'baseline': old or None,
                                   'baseline_complete': bool(old)}


def observe(leader, event):
    track = leader.get('turn_usage_tracking') or {}
    total = counters(event.get('total'))
    baseline = track.get('baseline')
    if total and baseline and all(k in total and total[k] >= v for k, v in baseline.items()):
        complete = track.get('baseline_complete', False)
        return {'usage': {k: total[k] - v for k, v in baseline.items()},
                'usage_basis': 'thread_total_delta_for_turn' if complete else 'observed_delta_missing_initial_baseline',
                'usage_complete': complete}
    # Missing baseline/total or a reset means the complete turn is unknown.
    # Do not sum repeated snapshots, invent zero usage, or label last as total.
    if total and not baseline:
        track['baseline'] = total
        leader['turn_usage_tracking'] = track
    return {'usage': counters(event.get('last')) or None,
            'usage_basis': 'last_request_only_missing_turn_baseline', 'usage_complete': False}
