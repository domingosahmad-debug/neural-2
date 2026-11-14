"""Kill a harmless owning Python process; verify its sleeping child dies too."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

root=Path(__file__).resolve().parent
fixture=root/'data/commissioning-fixtures'/uuid4().hex;fixture.mkdir(parents=True)
if os.name!='nt':raise SystemExit('This commissioning proof targets the installed Windows job guard.')
child_code="import os,time,pathlib;pathlib.Path("+repr(str(fixture/'child.pid'))+").write_text(str(os.getpid()));time.sleep(60)"
owner_code="import sys,threading;from pathlib import Path;sys.path.insert(0,"+repr(str(root))+");from providers_engine.transport import Transport;Transport()._run("+repr([sys.executable,'-u','-c',child_code])+",Path("+repr(str(fixture))+"),{},'',threading.Event(),Path("+repr(str(fixture/'raw.log'))+"))"
owner=subprocess.Popen([sys.executable,'-u','-c',owner_code],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
handle=None
try:
    deadline=time.monotonic()+10
    while not ((fixture/'child.pid').exists() and (fixture/'raw.log').exists()):
        if owner.poll() is not None:raise RuntimeError(owner.communicate()[1].decode())
        if time.monotonic()>deadline:raise TimeoutError('Harmless child did not start under guard.')
        time.sleep(.02)
    pid=int((fixture/'child.pid').read_text())
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x00100000,False,pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    owner.kill();owner.communicate(timeout=5)
    result=kernel.WaitForSingleObject(handle,5000)
    proof={'ownerKilled':owner.returncode is not None,'ownedChildExited':result==0,'ownerPid':owner.pid,'childPid':pid,'fixtureRoot':str(fixture),'modelCalls':0,'nativeCommands':0}
    (root/'PROVIDER_LIFETIME_PROOF.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof));assert proof['ownedChildExited']
finally:
    if owner.poll() is None:owner.kill();owner.communicate(timeout=5)
    if handle:kernel.CloseHandle(handle)
