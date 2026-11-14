"""Persistent agents, bounded CLI jobs and an explicit local rough-cut renderer.

No arbitrary command endpoint, API key handling, native AE writes or idle inference.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid


def stamp(): return datetime.now(timezone.utc).isoformat()
def load(p):
    # Windows may briefly deny a read while another thread atomically replaces it.
    for attempt in range(6):
        try:return json.loads(p.read_text(encoding='utf-8'))
        except PermissionError:
            if attempt==5:raise
            time.sleep(.015*(attempt+1))
def sha(p,cancelled=None):
    digest=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            if cancelled and cancelled():raise ValueError('Cancelled by user')
            digest.update(block)
    return digest.hexdigest()
def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    for attempt in range(8):
        try:temp.replace(p);break
        except PermissionError:
            if attempt==7:raise
            time.sleep(.015*(attempt+1))
def bounded(base, path):
    base, path = base.resolve(), path.resolve()
    if not path.is_relative_to(base): raise ValueError('Path outside permitted folder')
    return path
def ident(value):
    if not re.fullmatch('[a-f0-9]{32}', str(value)): raise ValueError('Invalid identifier')
    return value
def process_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
def terminate(process):
    if process.poll() is not None: return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    else:
        os.killpg(process.pid, signal.SIGTERM)
def find_tool(name):
    found = shutil.which(name)
    if found: return str(Path(found).resolve())
    if os.name == 'nt':
        if name == 'codex':
            candidates = list((Path.home()/'AppData/Local/OpenAI/Codex/bin').glob('*/codex.exe'))
        elif name in ['ffmpeg', 'ffprobe']:
            candidates = list((Path.home()/'AppData/Local/Microsoft/WinGet/Packages').glob('Gyan.FFmpeg_*/ffmpeg-*/bin/'+name+'.exe'))
        else: candidates = []
        if candidates: return str(max(candidates, key=lambda p:p.stat().st_mtime).resolve())
    return None

