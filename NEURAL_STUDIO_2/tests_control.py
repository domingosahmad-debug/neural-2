"""Durable station-control contracts. No provider process or native editor is used."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from control import Control


class FakeNative:
    unresolved = False

    def status(self):
        return {'unresolved': self.unresolved}


class FakeProviders:
    def __init__(self, root):
        self.root = root
        self.rows = []
        self.calls = []
        self.lose_reply = False

    def status(self):
        return copy.deepcopy(self.rows)

    def submit(self, packet, route, model, effort, request_id):
        self.calls.append((copy.deepcopy(packet), route, model, effort, request_id))
        if any(r['request_id'] == request_id for r in self.rows):
            raise AssertionError('Control submitted a duplicate request')
        packet_path = self.root / ('packet-' + str(len(self.calls)) + '.json')
        packet_path.write_text(json.dumps(packet))
        row = {'id': 'job-' + str(len(self.calls)), 'project': packet['project'],
               'station': packet['station'], 'assignmentId': packet['assignmentId'],
               'revision': packet['revision'], 'model': model, 'route': route,
               'request_id': request_id, 'status': 'QUEUED', 'created': len(self.calls),
               'packet_path': str(packet_path)}
        self.rows.append(row)
        if self.lose_reply:
            self.lose_reply = False
            raise OSError('Simulated reply loss after durable provider admission')
        return copy.deepcopy(row)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / 'workspace.sqlite3'
        packet = {'assignmentId': 'task1', 'project': 'alpha', 'revision': 1,
                  'station': 'Plan', 'model': 'opus', 'status': 'external handoff',
                  'task': 'Evaluate the supplied shot ledger', 'resultTemplate': {'assignmentId': 'task1'}}
        self.projects = {'alpha': {'id': 'alpha', 'revision': 1,
                         'assignments': {'task1': packet}, 'messages': [], 'productionControl': {}}}
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE workspace(id INTEGER PRIMARY KEY, body TEXT)')
            db.execute('INSERT INTO workspace VALUES(1,?)', (json.dumps(self.projects),))
        (self.root / 'model_catalog.json').write_text(json.dumps({'models': [
            {'provider': 'claude', 'model': 'opus'},
            {'provider': 'claude', 'model': 'claude-fable-5-2'},
            {'provider': 'antigravity', 'model': 'gemini-4-argon-high'}]}))
        self.providers = FakeProviders(self.root)
        self.native = FakeNative()
        self.patch = patch('providers_engine.transport.executable', return_value='FAKE-NOT-EXECUTED')
        self.patch.start()
        self.control = self.restart()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def restart(self):
        return Control(self.root, self.db, self.providers, self.native)

    def request(self, rid='request-1', model='opus'):
        return dict(project='alpha', station='Plan', requestId=rid, route='claude', model=model, effort='medium')

    def update_project(self, edit):
        with closing(sqlite3.connect(self.db)) as db, db:
            projects = json.loads(db.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
            edit(projects['alpha'])
            db.execute('UPDATE workspace SET body=? WHERE id=1', (json.dumps(projects),))

    def fail_job(self, index=-1, kind='subscription_exhausted', evidence=True):
        row = self.providers.rows[index]
        row.update(status='FAILED', result={'failure_kind': kind, 'exhaustion_evidence': 'exact quota rejection' if evidence else ''})
        return copy.deepcopy(row)

    def routing(self):
        self.control.routing('alpha', 'Plan', [
            {'route': 'claude', 'model': 'opus', 'effort': 'medium'},
            {'route': 'claude', 'model': 'sonnet', 'effort': 'medium'},
            {'route': 'claude', 'model': 'haiku', 'effort': 'low'}], True)

    def test_pause_survives_restart_and_invalidates_queued_generation(self):
        self.control.continue_task(self.request())
        row = self.providers.rows[0]
        self.assertTrue(self.control.admitted(row))
        self.control.pause('alpha', 'Human paused the edit')
        self.control = self.restart()
        self.assertTrue(self.control.status('alpha')['paused'])
        self.assertFalse(self.control.admitted(row))
        with self.assertRaisesRegex(ValueError, 'paused'):
            self.control.continue_task(self.request('new-request'))
        self.assertEqual(len(self.providers.calls), 1)
        self.update_project(lambda p: p['productionControl'].update(paused=False))
        self.assertFalse(self.control.admitted(row), 'Old queued packets remain invalid after unpause')

    def test_lost_reply_reconciles_persistent_request_after_restart(self):
        self.providers.lose_reply = True
        with self.assertRaises(OSError):
            self.control.continue_task(self.request())
        self.assertEqual(self.control.steps('alpha')[0]['state'], 'INTENT')
        self.control = self.restart()
        reply = self.control.continue_task(self.request())
        self.assertEqual(reply['jobId'], self.providers.rows[0]['id'])
        self.assertEqual(len(self.providers.calls), 1)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.control.continue_task(self.request(model='sonnet'))

    def test_intent_transaction_gap_dispatches_once(self):
        with patch.object(self.control, 'dispatch_intent', side_effect=OSError('before provider admission')):
            with self.assertRaises(OSError):
                self.control.continue_task(self.request())
        self.assertEqual(self.providers.calls, [])
        self.control = self.restart()
        self.control.continue_task(self.request())
        self.control.continue_task(self.request())
        self.assertEqual(len(self.providers.calls), 1)
        self.assertEqual(len(self.control.steps('alpha')), 1)

    def test_completed_and_unknown_never_replay_new_request(self):
        self.control.continue_task(self.request())
        row = self.providers.rows[0]
        row['status'] = 'COMPLETED'
        self.control.terminal(copy.deepcopy(row))
        self.assertEqual(self.control.continue_task(self.request())['status'], 'COMPLETED')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.control.continue_task(self.request('after-completion'))
        row['status'] = 'UNKNOWN'
        self.assertEqual(self.control.continue_task(self.request())['status'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
            self.control.continue_task(self.request('after-unknown'))
        self.assertEqual(len(self.providers.calls), 1)

    def check_missing_provider_row(self, outcome):
        request = self.request('durable-' + outcome)
        self.control.continue_task(request)
        row = copy.deepcopy(self.providers.rows[-1])
        row['status'] = outcome
        self.control.terminal(row)
        before = len(self.providers.calls)
        self.providers.rows.clear()
        self.control = self.restart()
        try:
            self.control.continue_task(request)
        except ValueError:
            pass
        self.assertEqual(len(self.providers.calls), before,
                         'Saved terminal evidence forbids recreating a missing provider invocation')

    def test_completed_checkpoint_blocks_replay_if_provider_row_disappears(self):
        self.check_missing_provider_row('COMPLETED')

    def test_unknown_checkpoint_blocks_replay_if_provider_row_disappears(self):
        self.check_missing_provider_row('UNKNOWN')

    def test_real_provider_queue_checks_pause_before_transport(self):
        from providers import ProviderJobs
        from unittest.mock import Mock
        transport = Mock()
        transport.run.side_effect = AssertionError('Paused queue must never invoke transport')
        provider = ProviderJobs(self.root, transport=transport, max_workers=1)
        control = Control(self.root, self.db, provider, self.native)
        provider.before_start = control.admitted
        provider.on_terminal = control.terminal
        entered, release = threading.Event(), threading.Event()

        def occupy_lane():
            entered.set()
            if not release.wait(5):
                raise AssertionError('Fixture failed to release provider lane')

        blocker = provider.pool.submit(occupy_lane)
        try:
            self.assertTrue(entered.wait(2))
            reply = control.continue_task(self.request())
            self.assertEqual(reply['status'], 'QUEUED')
            control.pause('alpha', 'Pause while station waits in provider queue')
            drained = provider.pool.submit(lambda: None)
            release.set()
            drained.result(timeout=3)
            self.assertEqual(provider.status()[0]['status'], 'CANCELLED')
            self.assertIn('paused or task superseded', provider.status()[0]['error'])
            transport.run.assert_not_called()
        finally:
            release.set()
            provider.shutdown()
            blocker.result(timeout=2)
        self.assertEqual(provider.status()[0]['status'], 'CANCELLED')
        self.assertTrue((provider.base / reply['jobId'] / 'terminal.json').is_file())

    def test_routing_effort_constraints_and_unavailable_gemini(self):
        with self.assertRaisesRegex(ValueError, 'Gemini requires high'):
            self.control.routing('alpha', 'Plan', [{'route': 'antigravity', 'model': 'gemini-4-argon-high', 'effort': 'medium'}], True)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            self.control.routing('alpha', 'Plan', [{'route': 'antigravity', 'model': 'gemini-4-argon-high', 'effort': 'high'}], True)
        with self.assertRaisesRegex(ValueError, 'low/medium'):
            self.control.routing('alpha', 'Plan', [{'route': 'claude', 'model': 'claude-fable-5-2', 'effort': 'high'}], True)
        status = self.control.routing('alpha', 'Plan', [{'route': 'claude', 'model': 'claude-fable-5-2', 'effort': 'low'}], False)
        self.assertFalse(status['routing']['Plan']['automatic'])

    def test_frontier_medium_policy_applies_to_routing_and_continuation(self):
        for route, model in [('claude','opus'), ('codex','gpt-6.1-sol'), ('codex','gpt-6-sol')]:
            for effort in ('low','high'):
                with self.assertRaisesRegex(ValueError, 'require medium'):
                    self.control.routing('alpha','Plan',[dict(route=route,model=model,effort=effort)],True)
                with self.assertRaisesRegex(ValueError, 'require medium'):
                    self.control.continue_task(dict(self.request(),route=route,model=model,effort=effort))
        self.assertEqual(self.providers.calls, [])

    def test_production_result_is_internal_and_manual_result_still_needs_review(self):
        self.control.continue_task(self.request())
        self.providers.rows[0]['status']='COMPLETED'
        self.update_project(lambda p:p['assignments'][self.providers.rows[0]['assignmentId']].update(status='needs review',productionRun='run1'))
        rows=self.control.status('alpha')['stations']
        self.assertEqual(next(r for r in rows if r['station']=='Plan')['state'],'completed')
        self.update_project(lambda p:p['assignments'][self.providers.rows[0]['assignmentId']].pop('productionRun'))
        rows=self.control.status('alpha')['stations']
        self.assertEqual(next(r for r in rows if r['station']=='Plan')['state'],'needs_review')

    def test_confirmed_exhaustion_bounded_chain_and_duplicate_terminal(self):
        self.routing()
        self.control.continue_task(self.request())
        original = self.fail_job()
        self.control.terminal(original)
        self.assertEqual([c[2] for c in self.providers.calls], ['opus', 'sonnet'])
        self.control.terminal(original)
        self.assertEqual(len(self.providers.calls), 2)
        second = self.fail_job()
        self.control.terminal(second)
        self.assertEqual([c[2] for c in self.providers.calls], ['opus', 'sonnet', 'haiku'])
        self.control.terminal(self.fail_job())
        self.assertEqual(len(self.providers.calls), 3)
        self.assertEqual(len({s['packet']['logicalTaskId'] for s in self.control.steps('alpha')}), 1)

    def test_network_429_missing_evidence_and_blocked_conversation_no_fallback(self):
        self.routing()
        self.control.continue_task(self.request())
        for kind, evidence, blocked in [('network', True, False), ('http_429', True, False),
                                         ('subscription_exhausted', False, False), ('subscription_exhausted', True, True)]:
            row = self.fail_job(kind=kind, evidence=evidence)
            row['conversation_blocked'] = blocked
            self.control.terminal(row)
        self.assertEqual(len(self.providers.calls), 1)

    def test_duplicate_parent_event_does_not_skip_failed_successor(self):
        self.routing()
        self.control.continue_task(self.request())
        original = self.fail_job()
        self.control.terminal(original)
        successor = self.fail_job(kind='network', evidence=False)
        self.control.terminal(successor)
        self.control.terminal(original)
        self.assertEqual([c[2] for c in self.providers.calls], ['opus', 'sonnet'])

    def test_startup_reconciles_terminal_checkpoint_without_inference(self):
        self.routing()
        self.control.continue_task(self.request())
        self.fail_job()
        recovered = self.restart()
        recovered.reconcile()
        self.assertEqual(recovered.steps('alpha')[0]['state'], 'FAILED')
        self.assertEqual(len(self.providers.calls), 1)

    def test_delayed_exhaustion_cannot_launch_new_assignment_or_revision(self):
        self.routing()
        self.control.continue_task(self.request())
        failed=self.fail_job()
        def supersede(p):
            for a in p['assignments'].values():a['status']='superseded'
            newer=copy.deepcopy(self.projects['alpha']['assignments']['task1'])
            newer.update(assignmentId='new-human-task',task='Different human task')
            p['assignments']['new-human-task']=newer
        self.update_project(supersede)
        self.control.terminal(failed)
        self.assertEqual(len(self.providers.calls),1)
        self.assertIn('no longer current',self.control.steps('alpha')[0]['fallbackBlocked'])

    def test_completed_json_is_imported_once_as_unapproved_evidence(self):
        def add_template(p):
            p['assignments']['task1']['resultTemplate']={
                'schema':'neural.station-result.v2','project':'alpha','revision':1,
                'station':'Plan','assignmentId':'task1'}
        self.update_project(add_template)
        self.control.continue_task(self.request())
        step=self.control.steps('alpha')[0]
        result=dict(step['packet']['resultTemplate'],summary='Measured text result; no media approval.')
        self.providers.result=lambda jid: {'status':'COMPLETED','text':'```json\n'+json.dumps(result)+'\n```'}
        row=self.providers.rows[0];row['status']='COMPLETED'
        self.control.terminal(row)
        self.control.terminal(row)
        with self.control.connection() as db:
            p=self.control.projects(db)['alpha']
        a=p['assignments'][step['packet']['assignmentId']]
        self.assertEqual(a['status'],'needs review')
        self.assertEqual(a['summary'],result['summary'])
        self.assertEqual(a['providerEvidence']['jobId'],row['id'])
        self.assertTrue(self.control.steps('alpha')[0]['resultImported'])

    def test_mismatched_result_is_not_imported_or_approved(self):
        self.control.continue_task(self.request())
        self.providers.result=lambda jid: {'status':'COMPLETED','text':json.dumps({'assignmentId':'other','summary':'wrong'})}
        row=self.providers.rows[0];row['status']='COMPLETED'
        self.control.terminal(row)
        self.assertIn('stale',self.control.steps('alpha')[0]['resultImportError'])
        with self.control.connection() as db:p=self.control.projects(db)['alpha']
        self.assertFalse(any(a.get('summary') for a in p['assignments'].values()))

    def test_continuation_rebinds_unstarted_descendant_and_keeps_history(self):
        def add_dep(p):
            child=copy.deepcopy(p['assignments']['task1'])
            child.update(assignmentId='child',station='Review',dependsOnAssignments=['task1'])
            child['resultTemplate']['assignmentId']='child'
            p['assignments']['child']=child
        self.update_project(add_dep)
        self.control.continue_task(self.request())
        with self.control.connection() as db:p=self.control.projects(db)['alpha']
        child=next(a for a in p['assignments'].values() if a['station']=='Review' and a['status']!='superseded')
        root=self.control.steps('alpha')[0]['packet']['assignmentId']
        self.assertEqual(child['dependsOnAssignments'],[root])
        self.assertEqual(p['assignments']['child']['dependsOnAssignments'],['task1'])
        self.assertEqual(p['assignments']['child']['status'],'superseded')

    def test_queued_attempt_rejects_superseded_assignment(self):
        self.control.continue_task(self.request())
        row=self.providers.rows[0]
        self.update_project(lambda p:p['assignments'][row['assignmentId']].update(status='superseded'))
        self.assertFalse(self.control.admitted(row))

    def test_native_unknown_and_paused_terminal_prevent_fallback(self):
        self.routing()
        self.native.unresolved = True
        with self.assertRaisesRegex(ValueError, 'Native outcome unresolved'):
            self.control.continue_task(self.request())
        self.native.unresolved = False
        self.control.continue_task(self.request())
        row = self.fail_job()
        self.control.pause('alpha', 'Hold all continuation')
        self.control.terminal(row)
        self.assertEqual(len(self.providers.calls), 1)


if __name__ == '__main__':
    unittest.main()
