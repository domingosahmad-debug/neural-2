"""Safe-boundary steering fixtures; never use live jobs, media or AE."""
import os;os.environ['NEURAL_AE_DIALOGS']='0'  # fixtures never probe or touch the real desktop
import copy
import json
import threading
import unittest
from unittest.mock import patch
import tests_production as fixtures


class SteeringTests(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    start=fixtures.ProductionTests.start
    def request(self,rid='direction-1',text='Use a longer setup and avoid repeated scenes.'):
        return dict(project='alpha',revision=1,requestId=rid,text=text)
    def steer(self,request=None):
        with patch.object(self.production.watchers,'submit'):
            return self.production.steer(request or self.request())
    def settle_old(self):
        self.providers.rows[0].update(status='FAILED',execution_started=False)
    def test_direction_fences_work_then_replans_once_with_exact_context(self):
        old=self.start();run=self.steer()
        self.assertEqual(run['state'],'STEERING')
        self.assertEqual(run['generation'],old['generation']+1)
        self.assertFalse(self.production.settle_steering(run['id'],'direction-1'))
        self.assertEqual(len(self.providers.rows),1)
        self.settle_old()
        self.assertTrue(self.production.settle_steering(run['id'],'direction-1'))
        new=self.production.status('alpha');self.assertEqual(new['phase'],'plan')
        self.assertEqual(len(self.providers.rows),2)
        self.production.settle_steering(run['id'],'direction-1');self.assertEqual(len(self.providers.rows),2)
        with self.control.connection() as db:
            p=self.control.projects(db)['alpha'];packet=p['assignments'][self.providers.rows[-1]['assignmentId']]
        self.assertIn(self.request()['text'],packet['task'])
        self.assertEqual(p['assignments'][old['assignmentId']]['status'],'superseded')
        self.assertEqual(new['repairs'],old['repairs'])
    def test_idempotence_conflict_and_stale_or_paused_denials(self):
        self.start();run=self.steer();self.steer()
        self.assertEqual(len(self.production.status('alpha')['steeringHistory']),1)
        with self.assertRaisesRegex(ValueError,'different direction'):self.steer(self.request(text='different'))
        with self.assertRaisesRegex(ValueError,'different project revision'):self.steer(dict(self.request('stale'),revision=2))
        self.control.pause('alpha','Human owns edit')
        with self.assertRaisesRegex(ValueError,'paused'):self.steer(self.request('paused'))
        self.production.steer_boundary(run['id'],'direction-1')
        self.assertEqual(len(self.providers.rows),1)
    def test_unknown_gateway_and_provider_block_without_old_phase_replay(self):
        self.start();run=self.steer();self.settle_old()
        folder=self.root/'data/projects/alpha/.neural-gateway';folder.mkdir(parents=True);(folder/'registry.json').write_text('{}')
        with patch('production_gateway.unresolved',return_value=['PUBLISHING']):
            with self.assertRaisesRegex(ValueError,'unsettled native gateway'):self.production.settle_steering(run['id'],'direction-1')
        self.assertEqual(len(self.providers.rows),1)
        self.providers.rows[0]['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'prior provider outcome'):self.production.settle_steering(run['id'],'direction-1')
    def test_stale_terminal_callback_cannot_advance_old_phase(self):
        self.start();run=self.steer();row=copy.deepcopy(self.providers.rows[0]);row['status']='FAILED'
        with patch.object(self.production.watchers,'submit') as watcher:
            self.production.terminal(row);watcher.assert_called_once()
        self.assertEqual(self.production.status('alpha')['state'],'STEERING')
        self.assertEqual(len(self.providers.rows),1)
    def test_new_direction_supersedes_waiter_and_startup_recovers_without_replay(self):
        self.start();first=self.steer();second=self.steer(self.request('direction-2','Keep the knock and change the ending.'))
        self.assertTrue(self.production.settle_steering(first['id'],'direction-1'))
        self.assertEqual(len(self.providers.rows),1)
        with patch.object(self.production.watchers,'submit') as watcher:
            self.production.recover();watcher.assert_called_once_with(self.production.steer_boundary,second['id'],'direction-2')
        self.settle_old();self.production.settle_steering(second['id'],'direction-2')
        self.assertEqual(len(self.providers.rows),2)


if __name__=='__main__':unittest.main()
