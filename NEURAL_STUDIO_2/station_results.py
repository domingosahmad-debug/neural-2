"""One strict station-result import contract for manual and provider completions."""
import json
import re

def required(data, field, limit):
    value=data.get(field)
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError(f'{field} must contain 1 to {limit} characters.')
    return value

def decode(outcome):
    # The production host already validated this exact object against the task identity.
    if isinstance(outcome.get('structured_result'),dict):return outcome['structured_result']
    text=outcome.get('text')
    if not isinstance(text,str):raise ValueError('Provider did not return a station-result document.')
    match=re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*',text,re.DOTALL)
    value=json.loads(match[1] if match else text)
    if not isinstance(value,dict):raise ValueError('Station result must be one JSON object.')
    return value

def attach(project,data):
    row=project['assignments'].get(data.get('assignmentId'))
    if not row or row['revision']!=project['revision'] or row['status']!='external handoff':
        raise ValueError('Assignment is stale, superseded or already processed.')
    template=row['resultTemplate']
    if any(data.get(k)!=template.get(k) for k in ('schema','project','revision','station','assignmentId')):
        raise ValueError('Result does not match the original packet.')
    for dependency in row.get('dependsOnAssignments',[]):
        prior=project['assignments'].get(dependency)
        if not prior or prior['status']!='approved' or prior['revision']!=project['revision']:
            raise ValueError('Required predecessor evidence is not approved.')
    if row['station']=='Executive Director':
        if not project.get('executiveEnabled'):raise ValueError('Executive Director is disabled.')
        plan=data.get('allocationPlan')
        if not isinstance(plan,list) or not 1<=len(plan)<=5:raise ValueError('Return 1–5 station allocations.')
        seen=set()
        for part in plan:
            if not isinstance(part,dict) or part.get('station') not in ('Director','Plan','Edit','Review','Deliver') or part['station'] in seen:
                raise ValueError('Use each production station at most once.')
            for field,limit in [('model',100),('task',8000),('acceptance',2000),('availabilityEvidence',1000)]:required(part,field,limit)
            deps=part.get('dependsOn')
            if not isinstance(deps,list) or any(d not in seen for d in deps):raise ValueError('Dependencies must reference earlier allocations, without cycles.')
            seen.add(part['station'])
        row['allocationPlan']=plan
    row.update(summary=required(data,'summary',12000),status='needs review')
    return row
