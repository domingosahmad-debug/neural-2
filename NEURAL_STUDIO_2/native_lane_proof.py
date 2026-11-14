"""No AE execution: exercise ownership and unresolved-outcome admission."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from native_lane import NativeLane

proof={}
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp); bridge=root/'bridge';bridge.mkdir()
    lane=NativeLane(root,bridge)
    def command(status='completed', identity='c1', result='c1'):
        (bridge/'ae_command.json').write_text(json.dumps({'id':identity,'status':status}))
        (bridge/'ae_mcp_result.json').write_text(json.dumps({'_commandId':result}))
    command()
    sock=MagicMock();sock.__enter__.return_value.connect_ex.return_value=1
    with patch('native_lane.socket.socket',return_value=sock):
        owner=lane.claim('Director fixture','protected-aep',True)
        try: lane.claim('Other fixture','protected-aep',True);proof['rejectsSecondWriter']=False
        except ValueError:proof['rejectsSecondWriter']=True
        command('pending')
        try: lane.release(owner['id']);proof['pendingBlocksRelease']=False
        except ValueError:proof['pendingBlocksRelease']=True
        command(result='different-command')
        proof['differentResultIsUnknown']=lane.status()['unresolved']
        command()
        proof['restartPreservesOwner']=NativeLane(root,bridge).status()['owner']==owner
        lane.release(owner['id'])
        proof['explicitSafeRelease']=lane.status()['owner'] is None
        command('running')
        try:lane.claim('Director fixture','protected-aep',True);proof['pendingBlocksClaim']=False
        except ValueError:proof['pendingBlocksClaim']=True
    proof['noNativeCommandSubmitted']=json.loads((bridge/'ae_command.json').read_text())=={'id':'c1','status':'running'}
Path(__file__).with_name('NATIVE_LANE_PROOF.json').write_text(json.dumps(proof,indent=2))
print(json.dumps(proof))
assert all(proof.values())
