"""Revision-bound local cut editor. CPU FFmpeg export; no AE or provider calls."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from services import ROOT
from local_engine import ChildLifetime, execution_lock
from operations import find_tool, save, load

def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Number must be between {low} and {high}.')
    return value


class Editor:
    def __init__(self, services, root=ROOT):
        self.services = services
        self.app_root = Path(root)
        self.root = Path(root) / 'data' / 'editor'
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'projects.sqlite3'
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='editor-export')
        self.closed = False
        self.proc = None
        self.ffmpeg, self.ffprobe = find_tool('ffmpeg'), find_tool('ffprobe')
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT)')
        for p in self.root.glob('exports/*/job.json'):
            row = load(p)
            if row['status'] in ('queued','running'):
                row.update(status='interrupted', error='App closed during export. Not replayed.'); save(p,row)
            self.services.complete(row)

    def key(self, key):
        if not isinstance(key, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,100}', key): raise ValueError('Invalid project identity.')
        return key

    def document(self, key):
        key = self.key(key)
        with sqlite3.connect(self.db) as db:
            found = db.execute('SELECT body FROM projects WHERE id=?',(key,)).fetchone()
        return json.loads(found[0]) if found else dict(schema='neural.edit.v1', id=key, revision=0,
            width=1080, height=1080, fps=30, media=[], clips=[], music=None, captions=[])

    def store(self, doc, expected):
        with sqlite3.connect(self.db) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM projects WHERE id=?',(doc['id'],)).fetchone()
            revision = json.loads(row[0])['revision'] if row else 0
            if revision != expected: raise ValueError('The edit changed elsewhere. Reload before saving; your draft was not overwritten.')
            doc['revision'] = revision + 1
            db.execute('INSERT OR REPLACE INTO projects VALUES(?,?)',(doc['id'],json.dumps(doc)))
        return doc

    def check_source(self, media):
        p = Path(media['path'])
        if not p.is_file(): raise ValueError('Missing media: ' + media['name'])
        stat = p.stat()
        if stat.st_size != media['bytes'] or stat.st_mtime_ns != media['mtime']:
            raise ValueError('Media changed since import: ' + media['name'] + '. Reimport and review it.')
        return p

    def fingerprint(self, p):
        digest = hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda: stream.read(4*1024*1024), b''): digest.update(chunk)
        return digest.hexdigest()

    def verify_source(self, media):
        p = self.check_source(media)
        if self.fingerprint(p) != media['sha256']: raise ValueError('Source content changed: ' + media['name'])
        return p

    def import_media(self, key, paths, revision):
        if not isinstance(paths, list) or not 1 <= len(paths) <= 20: raise ValueError('Import 1–20 files at a time.')
        if not self.ffprobe: raise ValueError('FFprobe is not installed.')
        doc = self.document(key)
        if doc['revision'] != revision: raise ValueError('Reload the current edit before importing.')
        for source in paths:
            p = Path(source).resolve(strict=True)
            if p.suffix.lower() not in ('.mp4','.mov','.webm','.m4v','.wav','.mp3','.m4a','.aac','.ogg'):
                raise ValueError('Unsupported media extension: ' + p.suffix)
            before = p.stat()
            fingerprint = self.fingerprint(p)
            st = p.stat()
            if st.st_size != before.st_size or st.st_mtime_ns != before.st_mtime_ns: raise ValueError('Media changed while importing: ' + p.name)
            if any(m['path'] == str(p) and m.get('sha256') == fingerprint and m['bytes'] == st.st_size and m['mtime'] == st.st_mtime_ns for m in doc['media']): continue
            reply = subprocess.run([self.ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(p)],
                capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if reply.returncode: raise ValueError('Cannot probe ' + p.name)
            data = json.loads(reply.stdout)
            video = next((s for s in data['streams'] if s['codec_type']=='video'),None)
            audio = any(s['codec_type']=='audio' for s in data['streams'])
            duration = float(data['format'].get('duration',0))
            if not math.isfinite(duration) or duration <= 0 or (not video and not audio): raise ValueError('Media has no supported finite duration.')
            final_stat = p.stat()
            if final_stat.st_size != st.st_size or final_stat.st_mtime_ns != st.st_mtime_ns: raise ValueError('Media changed while probing: ' + p.name)
            doc['media'].append(dict(id=uuid4().hex,path=str(p),name=p.name,duration=duration,
                width=video['width'] if video else 0,height=video['height'] if video else 0,
                video=bool(video),audio=audio,bytes=st.st_size,mtime=st.st_mtime_ns,sha256=fingerprint,
                codec=video.get('codec_name') if video else None))
        return self.store(doc,revision)

    def validate(self, candidate, current):
        if not isinstance(candidate, dict): raise ValueError('Expected an edit document.')
        d = copy.deepcopy(candidate)
        d['id'], d['schema'], d['media'] = current['id'], 'neural.edit.v1', current['media']
        if d.get('fps') not in (24,25,30,60): raise ValueError('Choose 24, 25, 30 or 60 fps.')
        for k in ('width','height'):
            if type(d.get(k)) is not int or not 64 <= d[k] <= 1920 or d[k]%2: raise ValueError('Use even canvas dimensions from 64 to 1920.')
        catalog = {m['id']:m for m in d['media']}
        if not isinstance(d.get('clips'),list) or len(d['clips'])>200: raise ValueError('Maximum 200 video clips.')
        seen = set()
        for clip in d['clips']:
            if not isinstance(clip, dict): raise ValueError('Expected a clip object.')
            if clip.get('id') in seen or not isinstance(clip.get('id'),str): raise ValueError('Each clip needs a unique ID.')
            seen.add(clip['id'])
            media = catalog.get(clip.get('mediaId'))
            if not media or not media['video']: raise ValueError('A video clip needs registered video media.')
            number(clip.get('in'),0,media['duration']);number(clip.get('out'),0,media['duration'])
            if clip['out']-clip['in'] < 1/d['fps']: raise ValueError('Each clip must contain at least one output frame.')
            frames = round((clip['out']-clip['in'])*d['fps'])
            clip['out'] = clip['in'] + frames/d['fps']
            if clip['out'] > media['duration']+.0001: raise ValueError('Rounded cut exceeds the source. Trim one frame earlier.')
            number(clip.get('gain',1),0,1);clip['gain']=clip.get('gain',1)
        duration = sum(c['out']-c['in'] for c in d['clips'])
        if duration > 7200: raise ValueError('This editor currently supports cuts up to two hours.')
        music = d.get('music')
        if music:
            if not isinstance(music, dict): raise ValueError('Expected a music object.')
            m=catalog.get(music.get('mediaId'))
            if not m or not m['audio']: raise ValueError('Music requires registered audio.')
            number(music.get('in'),0,m['duration']);number(music.get('start'),0,max(duration,0));number(music.get('gain'),0,1)
        if not isinstance(d.get('captions'),list) or len(d['captions'])>500: raise ValueError('Maximum 500 captions.')
        for cap in d['captions']:
            if not isinstance(cap, dict): raise ValueError('Expected a caption object.')
            number(cap.get('start'),0,max(duration,0));number(cap.get('end'),0,max(duration,0))
            if cap['end']<=cap['start'] or not isinstance(cap.get('text'),str) or not 1<=len(cap['text'])<=300: raise ValueError('Captions need text and a positive range within the cut.')
        ordered = sorted(d['captions'], key=lambda c:c['start'])
        if any(a['end'] > b['start'] for a,b in zip(ordered,ordered[1:])): raise ValueError('Caption ranges must not overlap. Combine simultaneous words in one caption.')
        return d

    def jobs(self, project):
        return sorted([load(p) for p in self.root.glob('exports/*/job.json') if load(p).get('project')==project],key=lambda j:j['created'],reverse=True)

    def action(self, req):
        if req.get('action') in ('load','export-status','jobs'): return self._action(req)
        import maintenance
        with maintenance.admission(self.app_root,'editor'):
            return self._action(req)

    def _action(self, req):
        key = self.key(req.get('project'))
        action = req.get('action')
        if action == 'load': return {'document':self.document(key),'exports':self.jobs(key)}
        if action == 'import': return {'document':self.import_media(key, req.get('paths'),req.get('revision'))}
        if action == 'save':
            current = self.document(key)
            doc = self.validate(req['document'],current)
            return {'document':self.store(doc,req.get('revision'))}
        if action == 'export':
            with self.lock:
                if self.closed: raise ValueError('Editor is closing.')
                outstanding = sum(load(p)['status'] in ('queued','running') for p in self.root.glob('exports/*/job.json'))
                if outstanding >= 4: raise ValueError('Four exports are already pending. Let them finish before adding more.')
                if any(j['status'] in ('queued','running') for j in self.jobs(key)): raise ValueError('This project already has an export queued or running.')
                doc = self.document(key)
                if doc['revision'] != req.get('revision'): raise ValueError('Save the current revision before export.')
                doc = self.validate(doc,doc)
                if not doc['clips']: raise ValueError('Add video clips before export.')
                for m in doc['media']:
                    if m['id'] in {c['mediaId'] for c in doc['clips']} or (doc['music'] and m['id']==doc['music']['mediaId']): self.check_source(m)
                row=dict(id=uuid4().hex,status='queued',title='Editor export · r'+str(doc['revision']),project=key,recipient='Director',created=time.time(),revision=doc['revision'],progress='Queued')
                folder=self.root/'exports'/row['id'];folder.mkdir(parents=True)
                save(folder/'timeline.json',doc);save(folder/'job.json',row)
                self.pool.submit(self.render,row,doc)
            self.services.signal()
            return {'job':row}
        raise ValueError('Unsupported editor action.')

    def command(self, args, folder, label):
        if self.closed: raise ValueError('Export stopped because the app is closing.')
        lifetime=ChildLifetime()
        try:
            with (folder/(label+'.log')).open('wb') as log:
                self.proc=subprocess.Popen(args,cwd=folder,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0))
                lifetime.attach(self.proc)
                try: code=self.proc.wait(timeout=7200)
                except subprocess.TimeoutExpired:
                    self.proc.kill(); self.proc.wait(); raise ValueError(label+' exceeded the two-hour step limit.')
            if code: raise ValueError(label+' failed. See saved export log.')
        finally:
            lifetime.close();self.proc=None

    def render(self,row,doc):
        folder=self.root/'exports'/row['id']
        try:
            # Share the existing media lane and the assistant admission gate; no inference occupies either while waiting.
            with self.services.resource_gate, execution_lock(self.services.engine.base/'execution.lock',lambda:None):
                if self.closed: raise ValueError('App closed before export began.')
                row.update(status='running',started=time.time());save(folder/'job.json',row);self.services.signal()
                if not self.ffmpeg: raise ValueError('FFmpeg is not installed.')
                catalog={m['id']:m for m in doc['media']};w,h,fps=doc['width'],doc['height'],doc['fps']
                frames=0
                for index,clip in enumerate(doc['clips']):
                    media=catalog[clip['mediaId']];self.verify_source(media)
                    count=round((clip['out']-clip['in'])*fps);frames+=count;duration=count/fps
                    row['progress']=f'Encoding clip {index+1} of {len(doc["clips"])}';save(folder/'job.json',row);self.services.signal()
                    cmd=[self.ffmpeg,'-v','error','-nostdin','-y','-ss',str(clip['in']),'-i',media['path']]
                    if not media['audio']:cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
                    cmd+=['-t',str(duration),'-map','0:v:0','-map','0:a:0' if media['audio'] else '1:a:0',
                          '-vf',f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration=1,trim=end_frame={count},setpts=N/({fps}*TB),format=yuv420p',
                          '-af',f'aresample=48000,aformat=channel_layouts=stereo,volume={clip["gain"]},apad',
                          '-c:v','libx264','-preset','fast','-crf','18','-threads','2','-filter_threads','1','-c:a','pcm_s16le','-ar','48000','-ac','2',f'clip-{index}.mkv']
                    self.command(cmd,folder,f'clip-{index}')
                    self.verify_source(media)
                (folder/'concat.txt').write_text(''.join(f"file 'clip-{i}.mkv'\n" for i in range(len(doc['clips']))))
                self.command([self.ffmpeg,'-v','error','-nostdin','-y','-f','concat','-safe','1','-i','concat.txt','-c','copy','joined.mkv'],folder,'join')
                row['progress']='Captions, audio mix and final encode';save(folder/'job.json',row);self.services.signal()
                cmd=[self.ffmpeg,'-v','error','-nostdin','-y','-i','joined.mkv'];filters=[f'fps={fps},tpad=stop_mode=clone:stop_duration=1,trim=end_frame={frames},setpts=N/({fps}*TB)']
                if doc['captions']:
                    font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeui.ttf'
                    if not font.is_file():raise ValueError('Caption font Segoe UI is unavailable.')
                    shutil.copy2(font,folder/'caption-font.ttf')
                    for i,cap in enumerate(doc['captions']):
                        (folder/f'caption-{i}.txt').write_text(cap['text'],encoding='utf-8')
                        filters.append(f"drawtext=fontfile=caption-font.ttf:textfile=caption-{i}.txt:expansion=none:fontsize={round(w*.045)}:fontcolor=0xdddddd:box=1:boxcolor=black@0.45:boxborderw=8:x=(w-text_w)/2:y=h*0.84-text_h/2:enable='gte(t,{cap['start']})*lt(t,{cap['end']})'")
                audio='0:a:0'
                if doc['music']:
                    music=doc['music'];m=catalog[music['mediaId']];self.verify_source(m)
                    cmd+=['-ss',str(music['in']),'-i',m['path']]
                    delay=round(music['start']*1000)
                    cmd+=['-filter_complex',f'[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={music["gain"]},adelay={delay}|{delay},apad[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]']
                    audio='[a]'
                if filters:cmd+=['-vf',','.join(filters)]
                cmd+=['-map','0:v:0','-map',audio,'-frames:v',str(frames),'-t',str(frames/fps),'-c:v','libx264','-preset','fast','-crf','18','-threads','2','-filter_threads','1','-filter_complex_threads','1','-c:a','aac','-b:a','192k','-movflags','+faststart','output.mp4']
                self.command(cmd,folder,'finish')
                if doc['music']: self.verify_source(catalog[doc['music']['mediaId']])
                self.command([self.ffmpeg,'-v','error','-nostdin','-i','output.mp4','-f','null','-'],folder,'decode')
                probe=subprocess.run([self.ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(folder/'output.mp4')],capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if probe.returncode:raise ValueError('Cannot verify export metadata.')
                data=json.loads(probe.stdout);save(folder/'probe.json',data)
                video=next(s for s in data['streams'] if s['codec_type']=='video')
                if int(video['nb_read_frames'])!=frames or video['width']!=w or video['height']!=h: raise ValueError('Export geometry/frame count verification failed.')
                row.update(status='completed',progress='Export verified',finished=time.time(),output=str(folder/'output.mp4'),frames=frames,duration=frames/fps)
        except Exception as error:
            row.update(status='failed',error=str(error),finished=time.time())
        finally:
            save(folder/'job.json',row);self.services.complete(row)

    def media_path(self, project, media_id):
        doc=self.document(project)
        media=next((m for m in doc['media'] if m['id']==media_id),None)
        if not media: raise ValueError('Media is not registered.')
        return self.check_source(media)

    def output_path(self,key):
        if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Invalid export ID.')
        folder=self.root/'exports'/key;row=load(folder/'job.json')
        if row['status']!='completed':raise ValueError('Export has not completed.')
        return folder/'output.mp4'

    def shutdown(self):
        self.closed=True
        if self.proc and self.proc.poll() is None:self.proc.kill()
        self.pool.shutdown(wait=False,cancel_futures=True)
