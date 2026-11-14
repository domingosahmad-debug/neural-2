"""Planning station contract proof; no provider calls or production state writes."""
import copy
import json
from pathlib import Path
from studio import apply, EXECUTIVE

projects={};p=apply(projects,'project',{'name':'Fixture','brief':'Plan a precise edit.'});pid=p['id'];proof={}
def assign(station=EXECUTIVE):return apply(projects,'assign',{'project':pid,'revision':1,'station':station,'model':'Any host / custom model','task':'Allocate one pass, verify availability and stop.'})
try:assign();proof['offRejectsAssignment']=False
except ValueError:proof['offRejectsAssignment']=True
apply(projects,'executive-enable',{'project':pid,'enabled':True});packet=assign()
proof['portableTask']=packet['station']==EXECUTIVE and packet['availability']['quota'].startswith('UNKNOWN') and 'Do not edit media' in packet['authority']
result=dict(packet['resultTemplate'],summary='Director coordinates; Plan measures, using verified capabilities only.',allocationPlan=[{'station':'Director','model':'Fixture director','task':'Own the brief and freeze scope.','acceptance':'Exact style brief saved.','dependsOn':[],'availabilityEvidence':'Fixture only; no provider called.'},{'station':'Plan','model':'Fixture planner','task':'Measure cuts and source clocks.','acceptance':'Frame-native varied shot plan.','dependsOn':['Director'],'availabilityEvidence':'Fixture only; no provider called.'}])
bad=copy.deepcopy(result);bad['allocationPlan'][0]['dependsOn']=['Plan']
try:apply(projects,'result',bad);proof['cycleRejected']=False
except ValueError:proof['cycleRejected']=True
apply(projects,'result',result)
try:apply(projects,'executive-apply',{'project':pid,'assignmentId':packet['assignmentId']});proof['unapprovedRejected']=False
except ValueError:proof['unapprovedRejected']=True
apply(projects,'approve',{'project':pid,'assignmentId':packet['assignmentId']})
packets=apply(projects,'executive-apply',{'project':pid,'assignmentId':packet['assignmentId']})['packets']
proof['handoffsCreated']=len(packets)==2 and packets[1]['dependsOnAssignments']==[packets[0]['assignmentId']]
try:apply(projects,'executive-apply',{'project':pid,'assignmentId':packet['assignmentId']});proof['applyOnce']=False
except ValueError:proof['applyOnce']=True
early=dict(packets[1]['resultTemplate'],summary='Premature plan')
try:apply(projects,'result',early);proof['dependencyGuard']=False
except ValueError:proof['dependencyGuard']=True
director=dict(packets[0]['resultTemplate'],summary='Brief frozen.')
apply(projects,'result',director);apply(projects,'approve',{'project':pid,'assignmentId':director['assignmentId']});apply(projects,'result',early)
proof['dependencyUnblocksOnEvidence']=p['assignments'][early['assignmentId']]['status']=='needs review'
pending=assign();apply(projects,'executive-enable',{'project':pid,'enabled':False})
try:apply(projects,'result',dict(pending['resultTemplate'],summary='Late reply',allocationPlan=result['allocationPlan']));proof['disabledRejectsLateReply']=False
except ValueError:proof['disabledRejectsLateReply']=True
proof['offByDefault']=not apply({},'project',{'name':'Fresh','brief':'Fresh'}) .get('executiveEnabled',False)
(Path(__file__).parent/'EXECUTIVE_PROOF.json').write_text(json.dumps(proof,indent=2))
assert all(proof.values()),proof
print(json.dumps(proof))
