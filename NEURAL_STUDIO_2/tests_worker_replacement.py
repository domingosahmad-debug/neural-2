"""Pure guarded replacement proof: no server, models, media or native writes."""
import copy
import unittest

from studio import apply, assignment_snapshot


def fixture():
    def row(ident,station,model='gpt-6.1-terra',deps=(),status='external handoff'):
        return {'schema':'neural.station-task.v2','project':'p','revision':4,'station':station,'assignmentId':ident,'model':model,'task':'EXACT task\nDo not alter source clocks [12,24).','brief':'Protected original brief','dependsOnAssignments':list(deps),'approvedEvidence':{'Director':'Actual completed evidence'},'editingContext':{'method':'Preserve native guards'},'requiredCapabilities':['read text','return JSON'],'status':status,'resultTemplate':{'schema':'neural.station-result.v2','project':'p','revision':4,'station':station,'assignmentId':ident,'summary':''}}
    rows={'done':row('done','Director',status='approved'),'a':row('a','Plan',deps=['done']),'b':row('b','Review',deps=['a']),'c':row('c','Deliver',deps=['b'])}
    rows['done']['summary']='Actual completed evidence'
    return {'p':{'id':'p','name':'Production','revision':4,'brief':'Protected original brief','assignments':rows,'activity':[],'notes':[],'messages':[]}}


def request(projects,model='claude-fable-5-2'):
    row=projects['p']['assignments']['a']
    return {'project':'p','revision':4,'station':'Plan','assignmentId':'a','expectedModel':row['model'],'expectedSnapshot':assignment_snapshot(row),'model':model,'reason':'Codex worker exhausted; replace exact task without resetting workflow.'}


class ReplacementTests(unittest.TestCase):
    def test_failed_worker_replacement_preserves_contract_evidence_and_rebinds_descendants(self):
        projects=fixture();initial=copy.deepcopy(projects)
        output=apply(projects,'replace-worker',request(projects),provider_jobs=[{'project':'p','assignmentId':'a','status':'FAILED','session_id':'exhausted-session','error':'Quota exhausted'}])
        current=output['packet'];self.assertEqual(current['model'],'claude-fable-5-2')
        self.assertEqual(projects['p']['revision'],4)
        self.assertEqual(projects['p']['assignments']['done'],initial['p']['assignments']['done'])
        for key in ('task','brief','approvedEvidence','editingContext','requiredCapabilities','dependsOnAssignments'):
            self.assertEqual(current[key],initial['p']['assignments']['a'][key])
        self.assertEqual(current['resultTemplate']['assignmentId'],current['assignmentId'])
        remapped={p['replacementOf']:p for p in [current,*output['dependentPackets']]}
        self.assertEqual(remapped['b']['dependsOnAssignments'],[current['assignmentId']])
        self.assertEqual(remapped['c']['dependsOnAssignments'],[remapped['b']['assignmentId']])
        for ident in ('a','b','c'):
            old=projects['p']['assignments'][ident]
            self.assertEqual(old['status'],'superseded')
            self.assertEqual(old['supersededSnapshot'],initial['p']['assignments'][ident])
        self.assertFalse(output['dispatched']);self.assertFalse(output['nativeLeaseTransferred'])
    def test_any_host_model_can_replace_without_dispatch_or_native_transfer(self):
        for model in ('claude-fable-5-2','gemini-4-argon-high','opencode/mimo-v2.6-flash-free'):
            projects=fixture();output=apply(projects,'replace-worker',request(projects,model),provider_jobs=[])
            self.assertEqual(output['packet']['model'],model)
            self.assertFalse(output['dispatched']);self.assertFalse(output['nativeLeaseTransferred'])
    def test_active_unknown_uncertain_and_completed_provider_outcomes_block_atomically(self):
        for status in ('QUEUED','RUNNING','CANCELLING','UNKNOWN','CANCELLED','INTERRUPTED','TIMED_OUT','COMPLETED','REVIEW_REQUIRED','APPROVED'):
            projects=fixture();before=copy.deepcopy(projects)
            with self.assertRaisesRegex(ValueError,'blocks replacement'):
                apply(projects,'replace-worker',request(projects),provider_jobs=[{'project':'p','assignmentId':'a','status':status}])
            self.assertEqual(projects,before)
        projects=fixture()
        with self.assertRaises(ValueError):apply(projects,'replace-worker',request(projects),provider_jobs=[{'project':'p','assignmentId':'a','status':'FAILED','conversation_blocked':True}])
    def test_completed_station_and_dependent_evidence_are_never_replayed(self):
        for ident in ('a','b','c'):
            for status in ('needs review','approved'):
                projects=fixture();projects['p']['assignments'][ident].update(status=status,summary='Saved completed work')
                before=copy.deepcopy(projects)
                with self.assertRaises(ValueError):apply(projects,'replace-worker',request(projects),provider_jobs=[])
                self.assertEqual(projects,before)
        projects=fixture()
        with self.assertRaisesRegex(ValueError,'dependent assignment has already been attempted'):
            apply(projects,'replace-worker',request(projects),provider_jobs=[{'project':'p','assignmentId':'b','status':'FAILED'}])
    def test_exact_identity_snapshot_revision_and_same_model_guards(self):
        for field,value in [('revision',3),('station','Review'),('assignmentId','missing'),('expectedModel','other'),('expectedSnapshot','wrong'),('model','gpt-6.1-terra')]:
            projects=fixture();data=request(projects);data[field]=value;before=copy.deepcopy(projects)
            with self.assertRaises(ValueError):apply(projects,'replace-worker',data,provider_jobs=[])
            self.assertEqual(projects,before)
        projects=fixture();data=request(projects);projects['p']['assignments']['a']['task']='Changed after client snapshot'
        with self.assertRaisesRegex(ValueError,'snapshot changed'):apply(projects,'replace-worker',data,provider_jobs=[])
    def test_missing_provider_snapshot_and_disabled_executive_block(self):
        projects=fixture()
        with self.assertRaisesRegex(ValueError,'provider-job snapshot'):apply(projects,'replace-worker',request(projects))
        projects['p']['assignments']['a']['station']='Executive Director';data=request(projects);data['station']='Executive Director'
        with self.assertRaisesRegex(ValueError,'off'):apply(projects,'replace-worker',data,provider_jobs=[])


if __name__=='__main__':unittest.main()
