"""Isolated regressions: no CLI, app, bridge or AE invocation."""
import ast
import copy
import inspect
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

APP_ROOT=next(p for p in Path(__file__).resolve().parents if (p/'studio.py').is_file() and (p/'tests_production.py').is_file())
# Run with NEURAL_CANDIDATE_DIR set to this folder to test candidates.
CANDIDATE=os.environ.get('NEURAL_CANDIDATE_DIR')
sys.path.insert(0,str(APP_ROOT))
if CANDIDATE:sys.path.insert(0,CANDIDATE)
import control
import production
from tests_production import ProductionTests

class ReadinessRegressions(ProductionTests):
    def test_actual_terminal_callback_defers_production_quota_fallback(self):
        self.start();row=self.providers.rows[-1]
        row.update(status='FAILED',result={'failure_kind':'subscription_exhausted','exhaustion_evidence':{'confirmed':True}})
        # Extract the real nested callback without starting the HTTP server/app.
        tree=ast.parse((Path(CANDIDATE) if CANDIDATE else APP_ROOT).joinpath('studio.py').read_text(encoding='utf-8-sig'))
        callback=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='controller_terminal')
        namespace={'terminal_callback':lambda row:None,'control':self.control,'production':Mock()}
        exec(compile(ast.Module(body=[callback],type_ignores=[]),'actual-controller-callback','exec'),namespace)
        with patch.object(self.production,'settled_native_boundary',side_effect=ValueError('Unsettled matching gateway report')):
            namespace['controller_terminal'](copy.deepcopy(row))
        self.assertEqual(len(self.providers.rows),1,'Callback launched fallback before coordinator checked the gateway report')
        namespace['production'].notify.assert_called_once()

    def test_coordinator_boundary_allows_exactly_one_settled_fallback(self):
        run=self.start();row=self.providers.rows[-1]
        row.update(status='FAILED',result={'failure_kind':'subscription_exhausted','exhaustion_evidence':{'confirmed':True}})
        with self.control.connection() as db:
            run=self.production._load(run['id'],db);run.update(state='WAIT_QUOTA_BOUNDARY',jobId=row['id']);self.production.persist(db,run)
        self.control.terminal(copy.deepcopy(row))
        self.assertEqual(len(self.providers.rows),1)
        self.production.quota_boundary(run['id'],copy.deepcopy(row))
        self.assertEqual(len(self.providers.rows),2)
        self.production.quota_boundary(run['id'],copy.deepcopy(row))
        self.assertEqual(len(self.providers.rows),2)
        self.assertTrue(any(h.get('quotaPredecessor')==row['id'] for h in self.production.status('alpha')['history']))

    def test_explicit_boundary_permission_still_rechecks_gateway(self):
        self.assertIn('production_boundary',inspect.signature(self.control.terminal).parameters,'Production fallback has no explicit settled-boundary admission')
        self.start();row=self.providers.rows[-1]
        row.update(status='FAILED',result={'failure_kind':'subscription_exhausted','exhaustion_evidence':{'confirmed':True}})
        with patch.object(self.production,'settled_native_boundary',side_effect=ValueError('Unsettled gateway report')):
            with self.assertRaisesRegex(ValueError,'Unsettled gateway'):
                self.control.terminal(copy.deepcopy(row),production_boundary=True)
        self.assertEqual(len(self.providers.rows),1)

    def test_new_repair_cannot_reuse_previous_cycle_mutation(self):
        run=self.start()
        run.update(phase='repair',history=[{'phase':'repair','jobId':'old-repair'},{'phase':'render','jobId':'old-render'},{'phase':'harsh_review','jobId':'old-review'},{'phase':'repair','jobId':'new-repair'}])
        def receipts(root,job):
            return [{'kind':'mutate','report':{'projectPath':'old.aep'}}] if job=='old-repair' else []
        with patch('pathlib.Path.is_file',return_value=True),patch('production_gateway.receipts',side_effect=receipts):
            with self.assertRaisesRegex(ValueError,'No matching completed native'):
                self.production.native_proof({'id':'new-repair'},run)

    def test_waiting_continuation_keeps_this_phase_mutation_proof(self):
        run=self.start()
        run.update(phase='repair',history=[{'phase':'harsh_review','jobId':'review'},{'phase':'repair','jobId':'waiting-repair','result':{'outcome':'waiting'}},{'phase':'repair','completionEvidence':[{'state':'COMPLETED'}]},{'phase':'repair','jobId':'continued-repair'}])
        def receipts(root,job):
            return [{'kind':'mutate','report':{'projectPath':'current.aep','compId':7}}] if job=='waiting-repair' else []
        with patch('pathlib.Path.is_file',return_value=True),patch('production_gateway.receipts',side_effect=receipts):
            self.assertEqual(self.production.native_proof({'id':'continued-repair'},run)['compId'],7)

    def test_goldfish_dispatch_excludes_actual_harsh_reviewer_and_fallback(self):
        run=self.start()
        with self.control.connection() as db:
            run=self.production._load(run['id'],db)
            run.update(phase='goldfish_review',state='READY',history=[{'phase':'harsh_review','model':'opus','result':{'outcome':'complete'}}])
            self.production.persist(db,run)
        self.production.dispatch(run['id'])
        current=self.production.status('alpha')
        with self.control.connection() as db:
            p=self.control.projects(db)['alpha']
            packet=p['assignments'][current['assignmentId']]
            candidates=p['productionControl']['routing']['Review']['candidates']
        self.assertNotEqual(packet['model'],'opus')
        self.assertNotIn('opus',[c['model'] for c in candidates])

if __name__=='__main__':unittest.main()
