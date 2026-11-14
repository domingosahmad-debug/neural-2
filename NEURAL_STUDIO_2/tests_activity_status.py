import unittest

from activity_status import project_activity


class ActivityStatusTests(unittest.TestCase):
    def status(self, run=None, rows=None, paused=False, settled=True):
        return project_activity(paused, settled, 'Human is editing manually.', rows or [], run)

    def test_paused_run_does_not_advertise_historic_blocker_or_review(self):
        for state in ('BLOCKED', 'HUMAN_REVIEW', 'WORKING'):
            self.assertEqual(self.status({'state': state}, paused=True)['state'], 'paused')
        self.assertEqual(self.status(paused=True, settled=False)['state'], 'stopping')

    def test_blocked_run_never_displays_ready(self):
        result = self.status({'state': 'BLOCKED', 'error': 'Exact render guard mismatch'})
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['reason'], 'Exact render guard mismatch')

    def test_waiting_and_internal_review_are_not_human_approval(self):
        for state in ('WAIT_MEDIA', 'WAIT_NATIVE', 'WAIT_TECHNICAL', 'WAIT_QUOTA_BOUNDARY'):
            self.assertEqual(self.status({'state': state})['state'], 'waiting')
        self.assertEqual(self.status({'state': 'WORKING', 'phase': 'harsh_review'}, [{'state': 'running', 'station': 'Review'}])['state'], 'running')
        self.assertEqual(self.status({'state': 'HUMAN_REVIEW'})['state'], 'human_review')

    def test_stale_working_record_without_invocation_does_not_claim_running(self):
        self.assertEqual(self.status({'state': 'WORKING'})['state'], 'waiting')
        self.assertEqual(self.status()['state'], 'idle')
        self.assertEqual(self.status({'state': 'DISPATCHING'})['state'], 'queued')

    def test_unknown_execution_has_priority_over_nominal_run_completion(self):
        self.assertEqual(self.status({'state': 'HUMAN_REVIEW'}, [{'state': 'unknown'}])['state'], 'unknown')
