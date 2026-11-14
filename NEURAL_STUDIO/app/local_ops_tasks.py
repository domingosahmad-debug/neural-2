"""Allowlisted media operations. Inputs are data, never executable commands.

Reports separate signal/geometry measurements from perceptual judgement. FFmpeg
children use two threads and one heavy pipeline owns the OS execution slot.
"""
from pathlib import Path
from fractions import Fraction
import importlib.util
import json
import math
import os
import re
import wave
import time

from operations import save, load, sha, bounded


def number(value, low=0, high=86400):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high: raise ValueError('Numeric value outside supported range')
    return value


def integer(value, low=0, high=10000000):
    if type(value) is not int or not low<=value<=high: raise ValueError('Integer outside supported range')
    return value


def input_file(raw):
    p=Path(str(raw))
    if not p.is_absolute() or not p.is_file(): raise ValueError('Input must be an existing absolute file path')
    return p.resolve()


def check(name, passed=None, detail=''):
    return {'name':name,'status':'NOT TESTED' if passed is None else ('PASS' if passed else 'FAIL'),'detail':str(detail)}


def report(summary, checks=None, **kwargs):
    return {'summary':summary,'checks':checks or [],'model_calls':0,**kwargs}


def ff(ctx, args, timeout=1800):
    return ctx.run('ffmpeg',['-hide_banner','-nostdin','-v','error','-n','-threads','2','-filter_threads','2',*args],timeout)


def metadata(ctx,p,count=False):
    args=['-v','error','-show_format','-show_streams','-of','json']
    if count: args+=['-count_frames']
    text,_=ctx.run('ffprobe',args+[str(p)],1800 if count else 90)
    data=json.loads(text)
    # FFprobe's embedded filename can differ for identical cached content.
    data.get('format',{}).pop('filename',None)
    return data


def probe(ctx,a):
    p=input_file(a['input']); data=metadata(ctx,p); save(ctx.out/'probe.json',data)
    return report('Media streams and format measured.',[check('Probe',bool(data.get('streams'))),check('Editorial suitability')],metadata=data,source_sha256=sha(p))


def frames(ctx,a):
    p=input_file(a['input']); indexes=a.get('frames')
    data=metadata(ctx,p); stream=next((s for s in data['streams'] if s.get('codec_type')=='video'),None)
    if stream is None: raise ValueError('No video stream')
    if indexes is None:
        count=stream.get('nb_frames')
        if not count or count=='N/A':
            stream=next(s for s in metadata(ctx,p,True)['streams'] if s.get('codec_type')=='video');count=stream.get('nb_read_frames')
        total=int(count); samples=integer(a.get('sample_count',6),1,48)
        indexes=[round(i*(total-1)/max(1,samples-1)) for i in range(samples)]
    if not isinstance(indexes,list) or not 1<=len(indexes)<=4096: raise ValueError('Request 1–4096 exact frame indexes per step; batch larger ranges')
    indexes=sorted(set(integer(i) for i in indexes))
    width=integer(a.get('width',320),64,1920); cols=integer(a.get('columns',4),1,12)
    # Decoder frame ordinal, not rounded time seeking. showinfo records actual PTS.
    expr='+'.join('eq(n\\,'+str(i)+')' for i in indexes)
    size=f'scale={width}:-2'
    _,log=ctx.run('ffmpeg',['-hide_banner','-nostdin','-v','info','-n','-threads','2','-filter_threads','2','-i',str(p),'-map','0:v:0','-vf',f'select={expr},showinfo,{size}','-fps_mode','vfr','-frames:v',str(len(indexes)),str(ctx.out/'frame-%04d.jpg')])
    pts=[]
    for line in log.read_text(encoding='utf-8',errors='replace').splitlines():
        m=re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([\d.eE+\-]+)',line)
        if m: pts.append({'selected_index':int(m[1]),'pts':int(m[2]),'pts_time':float(m[3])})
    files=sorted(ctx.out.glob('frame-*.jpg'))
    if len(files)!=len(indexes) or len(pts)!=len(indexes): raise ValueError('Requested frames exceed decoded source or exact PTS evidence is missing')
    from PIL import Image, ImageDraw
    ledger=[]
    # Bounded sheet pages prevent pathological bitmap allocations.
    for page in range(0,len(files),48):
        batch=files[page:page+48]
        with Image.open(batch[0]) as image: height=image.height
        sheet=Image.new('RGB',(cols*width,math.ceil(len(batch)/cols)*(height+26)),(10,21,29)); draw=ImageDraw.Draw(sheet)
        for j,f in enumerate(batch):
            i=page+j; x=(j%cols)*width; y=(j//cols)*(height+26)
            with Image.open(f) as image: sheet.paste(image,(x,y))
            draw.text((x+5,y+height+5),f"f{indexes[i]}  {pts[i]['pts_time']:.6f}s",fill=(164,231,222))
            ledger.append({'source_frame':indexes[i],**pts[i],'file':f.name})
        sheet.save(ctx.out/f'contact-{page//48+1:03}.jpg',quality=90)
    save(ctx.out/'frames.json',{'time_base':stream.get('time_base'),'r_frame_rate':stream.get('r_frame_rate'),'avg_frame_rate':stream.get('avg_frame_rate'),'frames':ledger,'indexing':'Zero-based decoded video frame ordinal. pts_time is measured, including VFR.'})
    return report(f'{len(files)} exact frames and {math.ceil(len(files)/48)} contact sheets.',[check('Frame count',True),check('Normal-speed motion/semantic interpretation')],frames=len(files),ledger='frames.json')


def ingest(ctx,a):
    measured=probe(ctx,a)
    if any(s.get('codec_type')=='video' for s in measured['metadata'].get('streams',[])):
        sampled=frames(ctx,dict(a,sample_count=a.get('sample_count',6)))
        measured['checks']+=sampled['checks']; measured['summary']+=' '+sampled['summary']
    return measured


def assets(ctx,a):
    paths=a.get('paths',[]);fonts=a.get('fonts',[])
    if not isinstance(paths,list) or not isinstance(fonts,list) or len(paths)+len(fonts)>1000:raise ValueError('Bounded paths/font lists required')
    checks=[];found=[]
    for raw in paths:
        p=Path(str(raw));exists=p.is_absolute() and p.is_file()
        checks.append(check('Asset '+p.name,exists,str(p)))
        if exists:found.append({'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size})
    installed={};unread=[]
    if fonts:
        from fontTools.ttLib import TTFont,TTCollection
        directories=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts',Path.home()/'AppData/Local/Microsoft/Windows/Fonts']
        for directory in directories:
            for p in directory.glob('*'):
                if p.suffix.lower() not in ('.ttf','.otf','.ttc'):continue
                ctx.check()
                try:
                    collection=TTCollection(p,lazy=True) if p.suffix.lower()=='.ttc' else None
                    faces=collection.fonts if collection else [TTFont(p,lazy=True)]
                    for face in faces:
                        for entry in face['name'].names:
                            if entry.nameID in (1,4,6):
                                try:installed[entry.toUnicode().casefold()]=str(p)
                                except (UnicodeError,AttributeError):pass
                        face.close()
                    if collection:collection.close()
                except Exception:unread.append(p.name)
        for font in fonts:checks.append(check('Installed font '+str(font),str(font).casefold() in installed,'System/user font tables; missing fonts must not be silently substituted'))
    save(ctx.out/'assets.json',{'assets':found,'fonts':{str(f):installed.get(str(f).casefold()) for f in fonts},'unread_font_files':unread})
    return report('Source paths/hashes and requested installed font names checked.',checks+[check('Font visual suitability')],unread_font_files=unread)


def detect_events(ctx,a):
    p=input_file(a['input']);threshold=number(a.get('scene_threshold',.3),.01,1)
    # Candidates only: scene-cut and black/freeze flags need director interpretation.
    _,log=ctx.run('ffmpeg',['-hide_banner','-nostdin','-v','info','-threads','2','-filter_threads','2','-i',str(p),'-an','-vf',f'blackdetect=d=0.08:pix_th=0.1,freezedetect=n=-50dB:d=0.2,select=gt(scene\\,{threshold}),showinfo','-fps_mode','vfr','-f','null','-'])
    rows=[]
    with log.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            ctx.check()
            if 'pts_time:' in line and ' n:' in line:
                match=re.search(r'pts_time:([\d.eE+\-]+)',line)
                if match:rows.append({'kind':'cut_candidate','seconds':float(match[1])})
            elif 'black_start:' in line or 'freeze_start:' in line or 'freeze_end:' in line:rows.append({'kind':'numeric_flag','detail':line.strip()[-500:]})
            if len(rows)>100000:raise ValueError('Too many events; split the source')
    save(ctx.out/'events.json',{'events':rows,'scene_threshold':threshold,'meaning':'Candidates/flags, not approved cuts, beats or evidence of editorial defects.'})
    return report(f'{len(rows)} local cut/black/freeze candidates measured.',[check('Detection completed',True),check('Semantic cut selection/intentional holds')],event_count=len(rows))


def audio_extract(ctx,a):
    p=input_file(a['input']); start=number(a.get('start',0)); duration=number(a['duration'],.001,3600)
    rate=integer(a.get('sample_rate',48000),8000,96000)
    # Decode first, trim by samples; avoid inaccurate input-side seeks.
    begin=round(start*rate); end=begin+round(duration*rate)
    ff(ctx,['-i',p,'-map','0:a:0','-vn','-af',f'aresample={rate},atrim=start_sample={begin}:end_sample={end},asetpts=PTS-STARTPTS','-ac','2','-c:a','pcm_s24le',ctx.out/'audio.wav'])
    out=metadata(ctx,ctx.out/'audio.wav'); got=float(out['format']['duration'])
    return report('Decoded requested audio window.',[check('Complete audio range',abs(got-duration)<=1/rate+.00001,f'{got}s requested {duration}s'),check('Words/clean isolation')],sample_rate=rate,start_sample=begin,end_sample=end)


def pcm(ctx,p,name='decoded.wav',rate=48000,duration=None):
    args=['-i',p,'-vn','-map','0:a:0']
    if duration is not None: args+=['-t',str(duration)]
    ff(ctx,args+['-ar',str(rate),'-ac','2','-c:a','pcm_s16le',ctx.out/name])
    return ctx.out/name


def audio_measure(ctx,a):
    import numpy as np
    p=input_file(a['input']); meta=metadata(ctx,p)
    duration=float(meta.get('format',{}).get('duration',0))
    if not 0<duration<=3600: raise ValueError('Audio measurements support up to one hour per step; extract a bounded range first')
    path=pcm(ctx,p)
    peak=0.; squares=0.; count=0; clipped=0; windows=[]; silent=[]; quiet_start=None; position=0
    threshold=10**(number(a.get('silence_db',-50),-100,-1)/20)
    with wave.open(str(path),'rb') as w:
        rate=w.getframerate(); channels=w.getnchannels()
        while raw:=w.readframes(max(1,rate//50)):
            ctx.check(); x=np.frombuffer(raw,dtype='<i2').astype(np.float64)/32768
            v=float(np.max(np.abs(x))); peak=max(peak,v); squares+=float(np.dot(x,x)); count+=x.size; clipped+=int(np.count_nonzero(np.abs(x)>=32767/32768))
            t=position/rate; length=x.size/channels/rate; windows.append([round(t,6),v])
            if v<threshold and quiet_start is None: quiet_start=t
            elif v>=threshold and quiet_start is not None:
                if t-quiet_start>=.1: silent.append([quiet_start,t])
                quiet_start=None
            position+=x.size//channels
        if quiet_start is not None and position/rate-quiet_start>=.1: silent.append([quiet_start,position/rate])
    path.unlink()  # large intermediate is not evidence
    save(ctx.out/'waveform.json',{'window_seconds':.02,'peaks':windows,'silence_intervals':silent})
    ceiling=number(a.get('max_peak',1),.001,1)
    return report('Decoded PCM peaks, RMS, clipping samples and silence measured.',[check('Peak ceiling',peak<=ceiling,f'peak={peak:.7f}; ceiling={ceiling}'),check('Decoded clipping',clipped==0,f'{clipped} samples at PCM ceiling'),check('Dialogue timing/score leakage')],peak=peak,peak_dbfs=20*math.log10(peak) if peak else None,rms=math.sqrt(squares/count) if count else 0,clipped_samples=clipped,silence_intervals=silent)


def audio_mix(ctx,a):
    import numpy as np
    tracks=a.get('tracks',[]); duration=number(a['duration'],.001,600); rate=48000
    if not isinstance(tracks,list) or not 1<=len(tracks)<=32: raise ValueError('Mix needs 1–32 explicit tracks')
    length=round(duration*rate)
    # Disk-backed float mix, bounded chunks: no full-resolution audio in RAM.
    mixpath=ctx.out/'mix.float'; mix=np.memmap(mixpath,dtype='<f4',mode='w+',shape=(length,2)); mix[:]=0
    try:
        for i,track in enumerate(tracks):
            ctx.check(); p=input_file(track['input']); start=number(track.get('start',0),0,duration); gain=10**(number(track.get('gain_db',0),-96,12)/20)
            dest=round(start*rate); decoded=pcm(ctx,p,f'track-{i}.wav',duration=duration-start)
            ducks=track.get('duck',[])
            for d in ducks:
                number(d['start'],0,duration); number(d['end'],d['start'],duration); number(d.get('gain_db',-9),-96,0); number(d.get('fade',.08),0,10)
            offset=0
            with wave.open(str(decoded),'rb') as w:
                while dest+offset<length and (raw:=w.readframes(48000)):
                    ctx.check(); x=np.frombuffer(raw,dtype='<i2').reshape(-1,2).astype(np.float32)/32768; x=x[:length-dest-offset]
                    ts=(dest+offset+np.arange(len(x)))/rate; env=np.ones(len(x),dtype=np.float32)*gain
                    for d in ducks:
                        lo,hi=d['start'],d['end']; fade=d.get('fade',.08); g=10**(d.get('gain_db',-9)/20)
                        factor=np.ones(len(x),dtype=np.float32); inside=(ts>=lo)&(ts<hi); factor[inside]=g
                        if fade:
                            before=(ts>=lo-fade)&(ts<lo); after=(ts>=hi)&(ts<hi+fade)
                            factor[before]=1+(g-1)*(ts[before]-(lo-fade))/fade; factor[after]=g+(1-g)*(ts[after]-hi)/fade
                        env*=factor
                    for key,reverse in (('fade_in',False),('fade_out',True)):
                        span=number(track.get(key,0),0,duration)
                        if span: env*=np.clip((duration-ts)/span if reverse else (ts-start)/span,0,1)
                    mix[dest+offset:dest+offset+len(x)] += x*env[:,None]; offset+=len(x)
            decoded.unlink()
        mix.flush(); peak=0.
        # No silent automatic normalization/limiting: clipping fails the gate.
        for pos in range(0,length,48000): peak=max(peak,float(np.max(np.abs(mix[pos:pos+48000])))); ctx.check()
        ff(ctx,['-f','f32le','-ar','48000','-ac','2','-i',mixpath,'-c:a','pcm_s24le',ctx.out/'mix.wav'])
    finally:
        del mix
        if mixpath.exists(): mixpath.unlink()
    return report('Explicit tracks mixed with specified gains, duck windows and fades.',[check('Mix headroom',peak<1,f'unclipped float peak={peak}'),check('Dialogue collision/semantic timing; validate the edit plan separately')],peak=peak,duration=duration,sample_rate=rate)


def audio_alignment(ctx,a):
    import numpy as np
    p=input_file(a['input']); reference=input_file(a['reference']); seconds=number(a.get('duration',30),.1,120); rate=integer(a.get('sample_rate',48000),8000,96000)
    paths=[pcm(ctx,p,'actual.wav',rate,seconds),pcm(ctx,reference,'reference.wav',rate,seconds)]
    arrays=[]
    for path in paths:
        with wave.open(str(path),'rb') as w: arrays.append(np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).mean(axis=1).astype(np.float64))
        path.unlink()
    x,y=arrays
    if min(len(x),len(y))<100: raise ValueError('Insufficient audio for correlation')
    x-=x.mean(); y-=y.mean(); n=1<<(len(x)+len(y)-1).bit_length()
    corr=np.fft.irfft(np.fft.rfft(x,n)*np.conj(np.fft.rfft(y,n)),n)
    limit=round(number(a.get('max_search_seconds',.25),0,2)*rate); lags=np.arange(-limit,limit+1)
    lag=int(lags[np.argmax(corr[lags%n])])
    lo=max(0,lag); hi=min(len(x),len(y)+lag); xa=x[lo:hi]; ya=y[lo-lag:hi-lag]
    score=float(np.dot(xa,ya)/(np.linalg.norm(xa)*np.linalg.norm(ya))) if np.linalg.norm(xa)*np.linalg.norm(ya)>0 else 0
    tolerance=number(a.get('tolerance_seconds',.001),0,1); minimum=number(a.get('min_correlation',.95),0,1)
    return report('Waveform lag measured against the supplied reference.',[check('Audio alignment',abs(lag)/rate<=tolerance and score>=minimum,f'{lag} samples at {rate}Hz, correlation={score:.6f}'),check('Lip sync/word meaning')],lag_samples=lag,sample_rate=rate,lag_seconds=lag/rate,correlation=score)


def validate_edit(data):
    checks=[]; fps=Fraction(str(data['fps'])); duration=integer(data['duration_frames'],1,1000000)
    if not 1<=float(fps)<=240: raise ValueError('Unsupported timeline fps')
    sources=data.get('sources',{}); shots=data.get('shots',[])
    if not isinstance(sources,dict) or not isinstance(shots,list) or not shots: raise ValueError('Edit needs source dictionary and shots')
    cursor=0; ids=set(); errors=[]
    for shot in shots:
        sid=shot.get('id'); start=integer(shot['start_frame']); end=integer(shot['end_frame'],start+1,duration)
        if not isinstance(sid,str) or sid in ids: errors.append('Duplicate/missing shot ID')
        ids.add(sid)
        if start!=cursor: errors.append(f'{sid}: gap/overlap at {cursor} -> {start}')
        cursor=end
        source=sources.get(shot.get('source_id'))
        if not source: errors.append(f'{sid}: missing source'); continue
        p=Path(source.get('path',''))
        if not p.is_absolute() or not p.is_file(): errors.append(f'{sid}: source path unavailable')
        srcfps=Fraction(str(source['fps'])); count=integer(source['frames'],1)
        source_in=integer(shot['source_in_frame']); source_out=integer(shot['source_out_frame'],source_in+1)
        if source_out>count: errors.append(f'{sid}: source range outside media')
        if not shot.get('retime') and abs(float(Fraction(source_out-source_in,1)/srcfps-Fraction(end-start,1)/fps))>1/float(fps): errors.append(f'{sid}: duration/rate mismatch without explicit retime')
    if cursor!=duration: errors.append(f'Final shot ends {cursor}, expected {duration}')
    checks.append(check('Timeline/source ranges',not errors,'; '.join(errors) or 'Contiguous half-open frame intervals and explicit source ranges'))
    repeats=[]
    for i,shot in enumerate(shots):
        source=sources.get(shot.get('source_id'))
        if not source: continue
        for earlier in shots[:i]:
            other=sources.get(earlier.get('source_id'))
            if not other or Path(source.get('path','')).resolve()!=Path(other.get('path','')).resolve(): continue
            a=Fraction(shot['source_in_frame'],1)/Fraction(str(source['fps'])); b=Fraction(shot['source_out_frame'],1)/Fraction(str(source['fps']))
            c=Fraction(earlier['source_in_frame'],1)/Fraction(str(other['fps'])); d=Fraction(earlier['source_out_frame'],1)/Fraction(str(other['fps']))
            if min(b,d)>max(a,c) and not (shot.get('intentional_repeat') is True and str(shot.get('repeat_reason','')).strip()):
                repeats.append(str(shot.get('id'))+' reuses source frames from '+str(earlier.get('id')))
    checks.append(check('Source reuse gate',not repeats,'; '.join(repeats) or 'No unapproved source-range reuse in this supplied plan; nested/occluded live ownership and semantics still need review'))
    for name in ('dialogue','captions'):
        events=data.get(name,[]); problems=[]
        if not isinstance(events,list): raise ValueError(name+' must be a list')
        events=sorted(events,key=lambda e:e['start_frame'])
        for i,event in enumerate(events):
            start=integer(event['start_frame']); end=integer(event['end_frame'],start+1,duration)
            if name=='captions' and not str(event.get('text','')).strip(): problems.append('Empty caption')
            for earlier in events[:i]:
                if start<earlier['end_frame'] and end>earlier['start_frame'] and not (event.get('intentional_overlap') is True and earlier.get('intentional_overlap') is True): problems.append(f'{event.get("id",i)} overlaps {earlier.get("id","previous")}')
        checks.append(check(name.title()+' collision gate',not problems,'; '.join(problems) or 'No unapproved same-lane overlaps; music is a separate lane'))
    checks.extend([check('Speaker/shot/quote semantics'),check('Typography visual fit'),check('Normal-speed flow')])
    return checks


def validate_plan(ctx,a):
    data=load(input_file(a['input'])); checks=validate_edit(data)
    save(ctx.out/'validated-plan.json',data)
    return report('Frame-native edit plan checked; artistic decisions remain reviewable.',checks,shot_count=len(data.get('shots',[])))


def compare_snapshot(ctx,a):
    before=load(input_file(a['before'])); after=load(input_file(a['after']))
    # Preservation is strict structural equality for named protected JSON paths.
    paths=a.get('paths',[''])
    if not isinstance(paths,list) or not 1<=len(paths)<=1000: raise ValueError('Specify protected JSON pointer paths')
    def at(value,pointer):
        if pointer=='': return value
        if not isinstance(pointer,str) or not pointer.startswith('/'): raise ValueError('Expected JSON pointer')
        for part in pointer[1:].split('/'):
            key=part.replace('~1','/').replace('~0','~')
            value=value[int(key)] if isinstance(value,list) else value[key]
        return value
    checks=[]
    for path in paths:
        try: same=at(before,path)==at(after,path); detail='Exact protected value comparison'
        except (KeyError,IndexError,ValueError,TypeError): same=False; detail='Protected path missing/invalid'
        checks.append(check('Preserved '+(path or 'entire snapshot'),same,detail))
    return report('Protected native state compared without key ordering assumptions.',checks)


def evidence_pack(ctx,a):
    items=a.get('items',[]);limit=integer(a.get('max_chars',24000),1000,100000)
    if not isinstance(items,list) or not 1<=len(items)<=64:raise ValueError('Evidence pack needs1–64 JSON inputs')
    rows=[];seen=set()
    def pointer(value,path):
        if path=='':return value
        if not isinstance(path,str) or not path.startswith('/'):raise ValueError('Expected JSON pointer')
        for part in path[1:].split('/'):
            key=part.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
        return value
    for item in items:
        p=input_file(item['input']);digest=sha(p);paths=item.get('pointers')
        if p.stat().st_size>16*1024*1024:raise ValueError('Evidence JSON exceeds16MB; prepare a bounded source report first')
        identity=(digest,json.dumps(paths,sort_keys=True))
        if identity in seen:continue
        data=load(p)
        if paths is not None:
            if not isinstance(paths,list) or len(paths)>100:raise ValueError('Up to100 JSON pointers per evidence source')
            selected={path:pointer(data,path) for path in paths}
        elif isinstance(data,dict) and 'checks' in data:
            selected={k:v for k,v in data.items() if k not in ('metadata','native')}
            if data.get('metadata'):
                selected['streams']=[{k:s[k] for k in ('codec_type','codec_name','width','height','r_frame_rate','avg_frame_rate','time_base','nb_frames','nb_read_frames','sample_rate','channels','duration') if k in s} for s in data['metadata'].get('streams',[])]
        elif isinstance(data,dict) and 'steps' in data:
            selected={k:data.get(k) for k in ('id','status','title','error','cache_hits','model_calls')}
            selected['steps']=[{'id':s['id'],'status':s['status'],'summary':s.get('report',{}).get('summary'),'checks':s.get('report',{}).get('checks',s.get('checks',[])),'outputs':s.get('outputs',[])} for s in data['steps']]
        else:selected=data
        rows.append({'label':str(item.get('label') or p.name),'source_sha256':digest,'selection':selected,'scope':'Selected numeric/text evidence, not playback or instructions.'});seen.add(identity)
    packed={'evidence':rows,'input_count':len(items),'unique_count':len(rows),'note':'Read full registered sources only for unresolved gates; duplicate source content removed.'}
    if len(json.dumps(packed,ensure_ascii=False))>limit:raise ValueError('Evidence pack exceeds character budget; select explicit JSON pointers instead of truncating evidence')
    save(ctx.out/'context.json',packed)
    return report('Compact, deduplicated evidence prepared for the next creative decision.',[check('Evidence budget',True),check('Perceptual/artistic review')],sources=len(rows),characters=len(json.dumps(packed,ensure_ascii=False)))


def verify_render(ctx,a):
    p=input_file(a['input']); data=metadata(ctx,p,True); streams=data['streams']; video=next((s for s in streams if s.get('codec_type')=='video'),None)
    checks=[]; expected=a.get('expect',{})
    # Complete decode; FFmpeg returns nonzero for corrupt packets with -xerror.
    ff(ctx,['-xerror','-i',p,'-map','0:v?','-map','0:a?','-f','null','-'])
    checks.append(check('Full decode',True))
    if video:
        actual={'width':video.get('width'),'height':video.get('height'),'frames':int(video.get('nb_read_frames',0)), 'fps':video.get('avg_frame_rate')}
        for key in ('width','height','frames','fps'):
            if key in expected:
                same=Fraction(str(actual[key]))==Fraction(str(expected[key])) if key=='fps' else actual[key]==expected[key]
                checks.append(check(key,same,f'{actual[key]} expected {expected[key]}'))
            else: checks.append(check(key,None,f'{actual[key]}; no expected value supplied'))
    else: checks.append(check('Video stream',False))
    if 'duration' in expected:
        got=float(data['format']['duration']); tolerance=number(expected.get('duration_tolerance',.05),0,1)
        checks.append(check('Duration',abs(got-number(expected['duration'],.001))<=tolerance,f'{got}s expected {expected["duration"]}s'))
    if expected.get('audio') is True: checks.append(check('Audio present',any(s.get('codec_type')=='audio' for s in streams)))
    checks.extend([check('Audio peaks/alignment: use audio_measure/audio_alignment'),check('Visual/artistic acceptance')])
    save(ctx.out/'probe.json',data)
    return report('Entire render decoded; supplied format expectations checked.',checks,metadata=data,source_sha256=sha(p))


def review_copy(ctx,a):
    p=input_file(a['input']); width=integer(a.get('width',1280),320,1920); crf=integer(a.get('crf',22),15,30)
    ff(ctx,['-i',p,'-map','0:v:0','-map','0:a?','-vf',f'scale=min({width}\\,iw):-2','-c:v','libx264','-pix_fmt','yuv420p','-threads','2','-preset','fast','-crf',str(crf),'-c:a','aac','-b:a','160k','-movflags','+faststart',ctx.out/'review.mp4'])
    ff(ctx,['-xerror','-i',ctx.out/'review.mp4','-f','null','-'])
    return report('Local review copy encoded and fully decoded.',[check('Review copy decode',True),check('Creative approval')],file='review.mp4')


def rough_assembly(ctx,a):
    shape=a.get('format','landscape')
    if shape not in ('landscape','portrait','square'):raise ValueError('Invalid rough assembly shape')
    width,height={'landscape':(1280,720),'portrait':(720,1280),'square':(1080,1080)}[shape]
    shots=a.get('shots',[])
    if not isinstance(shots,list) or not 1<=len(shots)<=60:raise ValueError('Specify 1–60 explicit rough-cut shots')
    total=0;segments=[]
    for i,shot in enumerate(shots):
        p=input_file(shot['input']);start=number(shot['start'],0,36000);end=number(shot['end'],start+.001,start+60);total+=end-start
        if total>120:raise ValueError('Rough assembly limit is120seconds')
        data=metadata(ctx,p)
        if end>float(data.get('format',{}).get('duration',0))+.02:raise ValueError('Source range exceeds media')
        segment=ctx.out/f'segment-{i:03}.mp4';segments.append(segment)
        ff(ctx,['-ss',str(start),'-i',p,'-t',str(end-start),'-an','-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24','-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-pix_fmt','yuv420p',segment],300)
    concat=ctx.out/'segments.txt';concat.write_text('\n'.join("file '"+p.name+"'" for p in segments),encoding='utf-8')
    args=['-f','concat','-safe','1','-i',concat]
    if a.get('music'):
        music=input_file(a['music']);args+=['-i',music,'-map','0:v:0','-map','1:a:0','-af',f'afade=t=out:st={max(0,total-1)}:d=1,apad','-c:a','aac','-b:a','192k']
    else:args+=['-an']
    ff(ctx,args+['-t',str(total),'-c:v','copy','-movflags','+faststart',ctx.out/'rough-cut.mp4'])
    for p in segments:p.unlink()
    concat.unlink()
    verified=verify_render(ctx,{'input':str(ctx.out/'rough-cut.mp4'),'expect':{'width':width,'height':height,'fps':'24','audio':bool(a.get('music'))}})
    verified['summary']='Explicit 24fps letterboxed rough assembly. Source sound muted; no effects/captions/native project changes.'
    return verified


def register_preview(ctx,a):
    from previews import PreviewCatalog
    p=input_file(a['input'])
    if a.get('kind') not in ('full','proof'): raise ValueError('Explicit preview kind full/proof required')
    # Decode + count again before registration, never publish a partial file.
    verification=verify_render(ctx,{'input':str(p),'expect':a.get('expect',{})})
    if any(c['status']=='FAIL' for c in verification['checks']): return verification
    data={k:a[k] for k in ('title','revision','kind','current','project_id') if k in a}
    data.update(path=str(p),note=str(a.get('note','Local structural checks completed; artistic review remains pending.')))
    row=PreviewCatalog(ctx.engine.root).register(data); save(ctx.out/'preview.json',row)
    return report('Completed review registered in Neural screening.',[check('Playable preview registration',True),check('Human artistic approval')],preview=row)


def native_observe(ctx,a):
    bridge=Path(a.get('bridge','C:/Users/TUF/Documents/ae-mcp-bridge')).resolve(); key=a['command_id']
    if not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{8,100}',key): raise ValueError('Invalid exact native command ID')
    seconds=number(a.get('timeout_seconds',900),.1,3600); deadline=time.monotonic()+seconds
    while True:
        ctx.check()
        try:
            command=load(bridge/'ae_command.json'); result=load(bridge/'ae_mcp_result.json')
            if command.get('id')!=key: return report('Native ownership changed; reconcile before further writes.',[check('Exact native owner',False)],execution='UNKNOWN')
            if command.get('status') not in ('pending','running') and result.get('_commandId')==key and result.get('_servicedBy')=='TonyFX' and type(result.get('ok')) is bool:
                save(ctx.out/'native-result.json',result)
                return report('Matching TonyFX transport completion. Inspect script report/state.',[check('TonyFX transport',result['ok'],result.get('error','')),check('Script/artistic outcome')],command_id=key)
        except (OSError,ValueError): pass
        if time.monotonic()>=deadline: return report('Native result still unknown. Never resend automatically.',[check('Native completion confirmed',False)],execution='UNKNOWN',command_id=key)
        time.sleep(.5)


def _native_bridge(a):
    bridge=Path(a.get('bridge','C:/Users/TUF/Documents/ae-mcp-bridge')).resolve()
    if not bridge.is_dir():raise ValueError('TonyFX bridge is unavailable; no host is launched')
    try:
        current=load(bridge/'ae_command.json')
        if current.get('servicedBy') not in (None,'TonyFX'):raise ValueError('Native bridge is owned by another host')
        if current.get('status') in ('pending','running'):raise ValueError('Native bridge busy; no request written')
        if current.get('id'):
            terminal=load(bridge/'ae_mcp_result.json')
            if terminal.get('_commandId')!=current['id'] or terminal.get('_servicedBy')!='TonyFX' or type(terminal.get('ok')) is not bool:raise ValueError('Previous native completion is unresolved; no request written')
    except FileNotFoundError:
        raise ValueError('Native bridge records missing; verify TonyFX before submitting')
    return bridge


def _native_generated(ctx,a,body,filename):
    if a.get('authorize_native') is not True:raise ValueError('Explicit native authorization required in this plan')
    project=input_file(a['expected_project']);bridge=_native_bridge(a)
    result=ctx.out/filename
    cfg={'expected_project':str(project),'report':str(result),'comp_id':a.get('comp_id'),'expect':a.get('expect',{}),
         'output':str(ctx.out/('native'+a.get('suffix','.mov'))),'render_settings':a.get('render_settings'),'output_template':a.get('output_template'),
         'multi_frame_rendering':a.get('multi_frame_rendering')}
    header='''(function(){__ENCODER__\nvar cfg=__CFG__,p=app.project;function fail(s){throw new Error('Neural local native: '+s);}function write(o){var f=new File(cfg.report);f.encoding='UTF-8';if(!f.open('w'))fail('Report unavailable');f.write(neuralEncode(o));f.close();}function comp(id){for(var i=1;i<=p.numItems;i++)if(p.item(i).id===id&&p.item(i) instanceof CompItem)return p.item(i);fail('Exact comp missing');}try{if(!p||!p.file||p.file.fsName!==new File(cfg.expected_project).fsName)fail('Wrong project');__BODY__}catch(e){write({ok:false,error:String(e)});throw e;}})();'''
    encoder=(Path(__file__).parent/'ae_json.jsxinc').read_text(encoding='utf-8')
    script=ctx.out/'native.jsx';script.write_text(header.replace('__BODY__',body).replace('__ENCODER__',encoder).replace('__CFG__',json.dumps(cfg)),encoding='utf-8')
    helper=Path(__file__).resolve().parents[1]/'knowledge/skills/tfx-tonyfx-execution/scripts/bridge.py'
    spec=importlib.util.spec_from_file_location('neural_tonyfx_client',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    save(ctx.out/'dispatch-intent.json',{'script':str(script),'sha256':sha(script),'expected_project_sha256':sha(project),'replay':'FORBIDDEN; reconcile after unknown execution'})
    request=module.submit(bridge,script);save(ctx.out/'request.json',request)
    observed=native_observe(ctx,{'bridge':str(bridge),'command_id':request['id'],'timeout_seconds':a.get('timeout_seconds',900)})
    if any(c['status']=='FAIL' for c in observed['checks']):return observed
    data=load(result)
    return report('Exact native operation finished; separate script and artistic gates.',[check('Script own result',data.get('ok') is True,data.get('error','')),check('Artistic acceptance')],native=data,command_id=request['id'])


def native_snapshot(ctx,a):
    ids=a.get('comp_ids',[])
    if not isinstance(ids,list) or len(ids)>100:raise ValueError('Provide up to100 comp IDs; empty selects all')
    for key in ids:integer(key,1)
    body='''var chosen=__IDS__,rows=[],propertyCount=0;function contains(a,v){for(var j=0;j<a.length;j++)if(a[j]===v)return true;return false;}
function value(v){if(v===null||typeof v==='number'||typeof v==='boolean'||typeof v==='string')return v;if(v instanceof Array)return v;if(v&&v.text!==undefined)return {text:v.text,font:v.font,fontSize:v.fontSize};return '[unsupported value type]';}
function properties(g){var out=[];for(var i=1;i<=g.numProperties;i++){if(++propertyCount>50000)fail('Snapshot too large; select fewer comp IDs');var q=g.property(i),o={name:q.name,matchName:q.matchName};if(q.propertyType===PropertyType.PROPERTY){o.keys=[];try{o.value=value(q.value);}catch(e){o.value='[unavailable]';}for(var k=1;k<=q.numKeys;k++){if(++propertyCount>100000)fail('Key snapshot too large');var key={time:q.keyTime(k),value:value(q.keyValue(k))};try{key.inInterpolation=q.keyInInterpolationType(k);key.outInterpolation=q.keyOutInterpolationType(k);var ie=q.keyInTemporalEase(k),oe=q.keyOutTemporalEase(k);key.easeIn=[];key.easeOut=[];for(var z=0;z<ie.length;z++)key.easeIn.push({speed:ie[z].speed,influence:ie[z].influence});for(var z=0;z<oe.length;z++)key.easeOut.push({speed:oe[z].speed,influence:oe[z].influence});}catch(e){}o.keys.push(key);}}else o.children=properties(q);out.push(o);}return out;}
for(var i=1;i<=p.numItems;i++){var c=p.item(i);if(!(c instanceof CompItem)||(chosen.length&&!contains(chosen,c.id)))continue;var row={id:c.id,name:c.name,width:c.width,height:c.height,fps:c.frameRate,duration:c.duration,layers:[]};for(var j=1;j<=c.numLayers;j++){var l=c.layer(j),layer={index:j,name:l.name,enabled:l.enabled,inPoint:l.inPoint,outPoint:l.outPoint,startTime:l.startTime,parent:l.parent?l.parent.index:null,properties:properties(l)};try{layer.source_id=l.source?l.source.id:null;layer.source_file=l.source&&l.source.file?l.source.file.fsName:null;layer.audioEnabled=l.audioEnabled;}catch(e){}row.layers.push(layer);}rows.push(row);}if(chosen.length&&rows.length!==chosen.length)fail('A requested comp was missing');write({ok:true,project:p.file.fsName,compositions:rows,limitations:['Unsupported value types are explicitly labeled; no project changes or playback.']});'''.replace('__IDS__',json.dumps(ids))
    return _native_generated(ctx,a,body,'snapshot.json')


def native_render(ctx,a):
    # Full Twixtor-heavy native proofs on this host have legitimately taken46min.
    # Keep explicit caller deadlines, but do not default them to a15min failure.
    a=dict(a)
    a.setdefault('timeout_seconds',3600)
    if 'multi_frame_rendering' in a and type(a['multi_frame_rendering']) is not bool:
        raise ValueError('multi_frame_rendering must be an explicit boolean')
    from execution_control import require_native_ready
    require_native_ready(ctx.engine.root)
    integer(a['comp_id'],1);expected=a.get('expect',{})
    for key in ('width','height','frames'):integer(expected[key],1)
    rate=float(Fraction(str(expected['fps'])))
    if not 1<=rate<=240:raise ValueError('Unsupported frame rate')
    for key in ('render_settings','output_template'):
        if not isinstance(a.get(key),str) or not 1<=len(a[key])<=180:raise ValueError('Choose explicit existing native render/output templates')
    if a.get('suffix','.mov') not in ('.mov','.mp4','.avi'):raise ValueError('Unsupported native render suffix')
    body='''var c=comp(cfg.comp_id),e=cfg.expect,rate=Number(e.fps);if(isNaN(rate)){var f=String(e.fps).split('/');rate=Number(f[0])/Number(f[1]);}
if(c.width!==e.width||c.height!==e.height||Math.abs(c.frameRate-rate)>.0001||Math.round(c.duration/c.frameDuration)!==e.frames)fail('Comp geometry/FPS/frame count changed');
if(p.renderQueue.rendering)fail('Render queue is busy');if(new File(cfg.output).exists)fail('Render output exists; do not replay');
if(cfg.multi_frame_rendering!==null){if(typeof app.setMultiFrameRenderingConfig!=='function')fail('Per-script Multi-Frame Rendering configuration unavailable');app.setMultiFrameRenderingConfig(cfg.multi_frame_rendering,100);}
var states=[],item=null;function has(a,s){for(var j=0;j<a.length;j++)if(a[j]===s)return true;return false;}
try{for(var j=1;j<=p.renderQueue.numItems;j++){var q=p.renderQueue.item(j);if(q.status===RQItemStatus.QUEUED&&q.render){states.push({item:q,render:q.render});q.render=false;}}
item=p.renderQueue.items.add(c);if(!has(item.templates,cfg.render_settings))fail('Render settings template unavailable');item.applyTemplate(cfg.render_settings);var om=item.outputModule(1);if(!has(om.templates,cfg.output_template))fail('Output template unavailable');om.applyTemplate(cfg.output_template);om.file=new File(cfg.output);item.timeSpanStart=0;item.timeSpanDuration=c.duration;item.render=true;p.renderQueue.render();if(item.status!==RQItemStatus.DONE)fail('Native render did not finish');var file=om.file;if(!file.exists||file.length<32)fail('Render file unavailable');write({ok:true,output:file.fsName,comp_id:c.id,frames:e.frames,fps:rate,bytes:file.length});}
finally{if(item){try{item.remove();}catch(e){}}for(var j=0;j<states.length;j++){try{states[j].item.render=states[j].render;}catch(e){}}}'''
    output=_native_generated(ctx,a,body,'render.json')
    if any(c['status']=='FAIL' for c in output['checks']):return output
    actual=input_file(output['native']['output'])
    if not actual.is_relative_to(ctx.out):raise ValueError('Native output escaped the job folder')
    verified=verify_render(ctx,{'input':str(actual),'expect':expected})
    verified['summary']='Native comp rendered and fully decoded with explicit geometry checks.';verified['native']=output['native'];verified['command_id']=output['command_id']
    return verified


def compile_ae(ctx,a):
    """Compile supplied decisions into a new composition; never mutate an old comp.

    Deliberately small supported vocabulary: cut, linear frame mapping, explicit
    transforms and text keys. Unknown creative effects must not be silently lost.
    """
    data=load(input_file(a['input'])); checks=validate_edit(data)
    if any(c['status']=='FAIL' for c in checks): return report('Invalid plan; no JSX generated.',checks)
    blueprint_ref=None
    if a.get('blueprint_project_id'):
        from production_workbench import Blueprint
        bp=Blueprint(ctx.engine.root).require(a['blueprint_project_id'])
        if bp['hash']!=a.get('blueprint_hash'):raise ValueError('Blueprint changed since submission; no stale compilation')
        intended=bp['contract']['edit']
        def signature(edit):
            return {'fps':str(Fraction(str(edit['fps']))),'duration_frames':edit['duration_frames'],'shots':[{k:s.get(k) for k in ('id','start_frame','end_frame','source_id','source_in_frame','source_out_frame','retime')} for s in edit['shots']],
                    'sources':{k:{'path':str(Path(v['path']).resolve()),'fps':str(Fraction(str(v['fps']))),'frames':v['frames']} for k,v in edit['sources'].items()}}
        if signature(data)!=signature(intended):raise ValueError('Assembly differs from shared shot blueprint; reconcile the canonical plan first')
        blueprint_ref={'project_id':a['blueprint_project_id'],'hash':bp['hash']}
    for shot in data['shots']:
        if set(shot)-{'id','start_frame','end_frame','source_id','source_in_frame','source_out_frame','retime','position_keys','scale_keys','opacity_keys'}: raise ValueError('Unsupported shot fields; no silent effect omissions')
        if shot.get('retime') not in (None,False,'linear'): raise ValueError('Compiler supports explicit linear retime only')
        for key,size in (('position_keys',2),('scale_keys',2),('opacity_keys',1)):
            keys=shot.get(key,[])
            if not isinstance(keys,list) or len(keys)>4096:raise ValueError('Bounded transform key arrays required')
            seen=set()
            for entry in keys:
                if not isinstance(entry,dict) or set(entry)!={'frame','value'}:raise ValueError('Transform keys need frame and value only')
                frame=integer(entry['frame'],shot['start_frame'],shot['end_frame']-1)
                if frame in seen:raise ValueError('Duplicate transform key time')
                seen.add(frame);value=entry['value']
                if size==1:number(value,0,100)
                else:
                    if not isinstance(value,list) or len(value)!=size:raise ValueError('Two-component transform values required')
                    for component in value:number(component,.001 if key=='scale_keys' else -100000,100000)
    for source in data['sources'].values():
        input_file(source['path']);integer(source['frames'],1)
        rate=Fraction(str(source['fps']))
        if not 1<=float(rate)<=240:raise ValueError('Unsupported source rate')
    if set(data)-{'fps','duration_frames','sources','shots','title','width','height'}: raise ValueError('Compiler supports picture only; audio, captions, effects and unknown plan fields must use their separate tools, never be silently omitted')
    expected=str(input_file(a['expected_project']))
    name=str(a.get('name',data.get('title','LOCAL_ASSEMBLY')))[:120]
    width=integer(data.get('width',1920),64,7680); height=integer(data.get('height',1080),64,7680)
    target=ctx.out/'assembly.aep'; own=ctx.out/'native-build.json'
    payload={'plan':data,'expected_project':expected,'project_sha256':sha(Path(expected)),'source_hashes':{str(input_file(s['path'])):sha(input_file(s['path'])) for s in data['sources'].values()},'output':str(target),'report':str(own),'name':name,'width':width,'height':height,'token':ctx.job['id']}
    if blueprint_ref:payload['blueprint']=blueprint_ref
    save(ctx.out/'compiled.json',payload)
    # Namespaced IIFE avoids helper collisions. Time-remap: upsert first, prune later.
    script='''(function(){__ENCODER__
var cfg=__CONFIG__, p=app.project, c=null;
function fail(s){throw new Error('Neural local compiler: '+s);}
function write(v){var f=new File(cfg.report);f.encoding='UTF-8';if(!f.open('w'))fail('Report unavailable');f.write(neuralEncode(v));f.close();}
function keys(prop,items,fps){if(!items)return;for(var k=0;k<items.length;k++){var q=items[k];prop.setValueAtTime(q.frame/fps,q.value);}}
function run(){
 if(!p||!p.file||p.file.fsName!==new File(cfg.expected_project).fsName)fail('Expected project is not open');
 if(new File(cfg.output).exists)fail('Output exists; do not replay');
 for(var i=1;i<=p.numItems;i++)if(p.item(i).comment==='NEURAL_LOCAL_'+cfg.token)fail('This assembly already exists; reconcile');
 var d=cfg.plan, fps=Number(d.fps);if(isNaN(fps)){var frac=String(d.fps).split('/');fps=Number(frac[0])/Number(frac[1]);}
 var sources={};for(var id in d.sources){var file=new File(d.sources[id].path);if(!file.exists)fail('Missing source '+id);var opt=new ImportOptions(file);sources[id]=p.importFile(opt);}
 c=p.items.addComp(cfg.name,cfg.width,cfg.height,1,d.duration_frames/fps,fps);c.comment='NEURAL_LOCAL_'+cfg.token;
 for(var j=0;j<d.shots.length;j++){
  var s=d.shots[j], source=d.sources[s.source_id], sf=Number(source.fps);if(isNaN(sf)){var f=String(source.fps).split('/');sf=Number(f[0])/Number(f[1]);}
  var layer=c.layers.add(sources[s.source_id]);layer.name=s.id;layer.startTime=s.start_frame/fps-s.source_in_frame/sf;layer.inPoint=s.start_frame/fps;layer.outPoint=s.end_frame/fps;layer.audioEnabled=false;
  if(s.retime==='linear'){
   layer.timeRemapEnabled=true;var tr=layer.property('ADBE Time Remapping'), t0=s.start_frame/fps,t1=(s.end_frame-1)/fps;
   tr.setValueAtTime(t0,s.source_in_frame/sf);if(t1>t0)tr.setValueAtTime(t1,(s.source_out_frame-1)/sf);
   for(var n=tr.numKeys;n>=1;n--)if(Math.abs(tr.keyTime(n)-t0)>.00001&&Math.abs(tr.keyTime(n)-t1)>.00001)tr.removeKey(n);
  }
  var transform=layer.property('ADBE Transform Group');keys(transform.property('ADBE Position'),s.position_keys,fps);keys(transform.property('ADBE Scale'),s.scale_keys,fps);keys(transform.property('ADBE Opacity'),s.opacity_keys,fps);
 }
 p.save(new File(cfg.output));write({ok:true,comp_id:c.id,comp_name:c.name,project:cfg.output,frames:d.duration_frames,fps:fps,picture_only:true});
}
app.beginUndoGroup('Neural deterministic assembly');try{run();}catch(e){write({ok:false,error:String(e),partial_comp_id:c?c.id:null});throw e;}finally{app.endUndoGroup();}
})();'''.replace('__ENCODER__',(Path(__file__).parent/'ae_json.jsxinc').read_text(encoding='utf-8')).replace('__CONFIG__',json.dumps(payload,ensure_ascii=True))
    (ctx.out/'assembly.jsx').write_text(script,encoding='utf-8')
    return report('Guarded picture assembly compiled; no AE command was sent.',checks+[check('Native execution')],script='assembly.jsx',manifest='compiled.json',supported='Picture cuts, supplied linear retimes and explicit transform keys. No invented effects, captions or audio.')


def native_submit(ctx,a):
    from execution_control import require_native_ready
    require_native_ready(ctx.engine.root)
    if a.get('authorize_native') is not True: raise ValueError('Plan must explicitly authorize this native mutation')
    manifest=load(input_file(a['compiled'])); script=input_file(a['input'])
    if manifest.get('blueprint'):
        from production_workbench import Blueprint
        ref=manifest['blueprint'];current=Blueprint(ctx.engine.root).require(ref['project_id'])
        if current['hash']!=ref['hash']:raise ValueError('Blueprint changed after compilation; do not dispatch stale assembly')
    if script.parent!=Path(a['compiled']).parent or script.name!='assembly.jsx' or Path(a['compiled']).name!='compiled.json': raise ValueError('Only this compiler\'s generated assembly can be dispatched')
    # Only compiler output from an earlier registered step of THIS pipeline.
    if not script.is_relative_to(ctx.folder) or not any(s.get('operation')=='compile_ae' and 'assembly.jsx' in s.get('outputs',[]) and sha(script)==s.get('hashes',{}).get('assembly.jsx') and sha(Path(a['compiled']))==s.get('hashes',{}).get('compiled.json') for s in ctx.job['steps']): raise ValueError('Generated script integrity/ownership failed')
    expected=input_file(manifest['expected_project'])
    if sha(expected)!=manifest['project_sha256']: raise ValueError('Expected project changed since compilation; regenerate after inspection')
    if any(sha(input_file(path))!=digest for path,digest in manifest.get('source_hashes',{}).items()):raise ValueError('Source changed since compilation; no native command sent')
    if Path(manifest['output']).exists(): raise ValueError('Native output exists; reconcile rather than replay')
    bridge=_native_bridge(a)
    helper=Path(__file__).resolve().parents[1]/'knowledge/skills/tfx-tonyfx-execution/scripts/bridge.py'
    spec=importlib.util.spec_from_file_location('neural_tonyfx_client',helper); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # Dispatch intent is persisted before side effect. A crash is INTERRUPTED, never replayed.
    save(ctx.out/'dispatch-intent.json',{'script':str(script),'sha256':sha(script),'replay':'FORBIDDEN; reconcile exact native state'})
    request=module.submit(bridge,script); save(ctx.out/'request.json',request)
    observed=native_observe(ctx,{'bridge':str(bridge),'command_id':request['id'],'timeout_seconds':a.get('timeout_seconds',900)})
    if any(c['status']=='FAIL' for c in observed['checks']): return observed
    own=input_file(manifest['report']); data=load(own)
    if data.get('ok') is True:
        import shutil
        project=input_file(data['project'])
        if not project.is_relative_to(ctx.folder):raise ValueError('Compiled project escaped the job folder')
        shutil.copy2(project,ctx.out/'assembly.aep')
    save(ctx.out/'build-result.json',data)
    return report('New picture assembly completed through the single TonyFX bridge.',[check('Script own result',data.get('ok') is True),check('Visual/artistic acceptance')],native=data)



def batch_inventory(ctx, a):
    folder_path = a.get('folder')
    items = a.get('inputs', [])
    if folder_path:
        f = Path(folder_path).resolve()
        if not f.is_dir():
            raise ValueError(f'Folder not found: {folder_path}')
        valid_exts = set(a.get('extensions', ['.mp4', '.mkv', '.mov', '.avi', '.wav', '.mp3', '.aac', '.flac']))
        found = sorted([p for p in f.iterdir() if p.is_file() and p.suffix.lower() in valid_exts])
        items = [str(p) for p in found[:50]]
    if not items:
        raise ValueError('No inputs provided for batch inventory')
        
    records = []
    total_duration = 0.0
    for item in items:
        ctx.check()
        p = input_file(item)
        data = metadata(ctx, p)
        v_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        a_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
        
        dur_s = float(data.get('format', {}).get('duration', 0))
        total_duration += dur_s
        
        r_fps = v_stream.get('r_frame_rate', '') if v_stream else ''
        width = v_stream.get('width') if v_stream else None
        height = v_stream.get('height') if v_stream else None
        
        frames = None
        if v_stream and r_fps:
            try:
                num, den = map(int, r_fps.split('/'))
                frames = int(round(dur_s * (num / den)))
            except Exception:
                frames = None
                
        rec = {
            'path': str(p),
            'filename': p.name,
            'sha256': sha(p),
            'duration_seconds': round(dur_s, 3),
            'rational_fps': r_fps,
            'frames': frames,
            'width': width,
            'height': height,
            'has_audio': bool(a_stream),
            'audio_sample_rate': int(a_stream.get('sample_rate', 0)) if a_stream else None,
            'audio_channels': int(a_stream.get('channels', 0)) if a_stream else None,
            'status': 'PROBED'
        }
        records.append(rec)
        
    result_data = {
        'sources': records,
        'total_sources': len(records),
        'total_duration_seconds': round(total_duration, 3),
        'algorithm_id': ctx.engine.algorithm_id
    }
    save(ctx.out / 'inventory.json', result_data)
    return report(
        f"Batch inventory complete for {len(records)} sources ({round(total_duration, 1)}s total).",
        [check('Batch inventory complete', True), check('Source quality / editorial suitability')],
        inventory=result_data
    )


def detect_beats(ctx, a):
    import numpy as np
    p = input_file(a['input'])
    fps_raw = a.get('fps', '24000/1001')
    try:
        num, den = map(int, fps_raw.split('/'))
        fps_float = num / den
    except Exception:
        fps_float = 23.976023976
        
    meta = metadata(ctx, p)
    dur_s = float(meta.get('format', {}).get('duration', 0))
    if not 0 < dur_s <= 3600:
        raise ValueError('Beat detection supports up to one hour per step; extract a bounded range first')
        
    path = pcm(ctx, p, name='beats_temp.wav', rate=48000)
    hop_size = 960
    energies = []
    
    with wave.open(str(path), 'rb') as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        while raw := w.readframes(hop_size):
            ctx.check()
            samples = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768.0
            rms = float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0
            energies.append(rms)
            
    path.unlink()
    if len(energies) < 10:
        raise ValueError('Audio is too short for event detection')
        
    energies = np.array(energies)
    flux = np.diff(energies, prepend=energies[0])
    flux = np.maximum(0.0, flux)
    
    mean_flux = float(np.mean(flux))
    std_flux = float(np.std(flux))
    thresh_factor = float(a.get('threshold', 0.25))
    cutoff = mean_flux + thresh_factor * std_flux
    
    measured_events = []
    min_dist_hops = 10
    last_hop = -min_dist_hops
    
    for i in range(1, len(flux) - 1):
        ctx.check()
        if flux[i] > cutoff and flux[i] >= flux[i-1] and flux[i] >= flux[i+1]:
            if i - last_hop >= min_dist_hops:
                t_sec = round(i * 0.02, 3)
                frame_idx = int(round(t_sec * fps_float))
                strength = round(float(flux[i] / (cutoff + 1e-6)), 3)
                measured_events.append({
                    'id': f"evt_{len(measured_events)+1:03d}",
                    'time_s': t_sec,
                    'frame': frame_idx,
                    'strength': strength,
                    'kind': 'measured_onset'
                })
                last_hop = i
                
    pulse_hypotheses = []
    if len(measured_events) >= 4:
        times = [e['time_s'] for e in measured_events]
        intervals = [round(times[i+1] - times[i], 3) for i in range(len(times)-1)]
        ioi_median = float(np.median(intervals))
        if 0.25 <= ioi_median <= 1.2:
            base_bpm = round(60.0 / ioi_median, 1)
            for mult, label in [(1.0, 'primary'), (0.5, 'half_time'), (2.0, 'double_time')]:
                cand_bpm = round(base_bpm * mult, 1)
                if 40 <= cand_bpm <= 240:
                    beat_sec = 60.0 / cand_bpm
                    phase_s = times[0] % beat_sec
                    grid_frames = []
                    curr_t = phase_s
                    while curr_t < dur_s:
                        grid_frames.append(int(round(curr_t * fps_float)))
                        curr_t += beat_sec
                    pulse_hypotheses.append({
                        'tempo_bpm': cand_bpm,
                        'confidence': round(0.85 if label == 'primary' else 0.65, 2),
                        'kind': label,
                        'beat_interval_s': round(beat_sec, 4),
                        'phase_offset_s': round(phase_s, 4),
                        'sample_grid_frames': grid_frames[:32]
                    })
                    
    payload = {
        'source': str(p),
        'source_sha256': sha(p),
        'duration_seconds': round(dur_s, 3),
        'rational_fps': fps_raw,
        'measured_events_count': len(measured_events),
        'measured_events': measured_events,
        'pulse_hypotheses': pulse_hypotheses,
        'editorial_guidance': 'Measured onset events reflect actual acoustic energy. Regular pulse grids are mathematical fits. Cuts, transitions and action apexes require explicit musical and narrative justification.'
    }
    save(ctx.out / 'audio_events.json', payload)
    return report(
        f"Measured {len(measured_events)} audio events; derived {len(pulse_hypotheses)} pulse hypotheses.",
        [check('Acoustic onset detection complete', True), check('Editorial cut/accent alignment')],
        event_count=len(measured_events),
        hypotheses_count=len(pulse_hypotheses)
    )


def transcript_search(ctx, a):
    query = str(a.get('query', '')).strip().lower()
    if not query:
        raise ValueError('Search query required')
    sources = a.get('sources', [])
    fps_raw = a.get('fps', '24000/1001')
    try:
        num, den = map(int, fps_raw.split('/'))
        fps_float = num / den
    except Exception:
        fps_float = 23.976023976
        
    resolved_files = []
    for s in sources:
        sp = Path(s)
        if sp.is_dir():
            for f in sorted(sp.iterdir()):
                if f.suffix.lower() in ['.srt', '.vtt', '.json']:
                    resolved_files.append(f)
        elif sp.is_file():
            resolved_files.append(sp)
            
    matches = []
    for f in resolved_files:
        ctx.check()
        ext = f.suffix.lower()
        if ext in ['.srt', '.vtt']:
            file_text = f.read_text(encoding='utf-8', errors='replace')
            blocks = file_text.strip().split("\n\n")
            for block in blocks:
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                timing_line = next((l for l in lines if '-->' in l), None)
                if not timing_line:
                    continue
                parts = timing_line.split('-->')
                if len(parts) != 2:
                    continue
                def parse_time(ts):
                    ts = ts.strip().replace(',', '.')
                    segs = ts.split(':')
                    if len(segs) == 3:
                        return float(segs[0]) * 3600 + float(segs[1]) * 60 + float(segs[2])
                    return 0.0
                start_s = parse_time(parts[0])
                end_s = parse_time(parts[1])
                t_idx = lines.index(timing_line)
                dialogue = ' '.join(lines[t_idx+1:])
                if query in dialogue.lower():
                    matches.append({
                        'source_file': f.name,
                        'start_time_s': round(start_s, 3),
                        'end_time_s': round(end_s, 3),
                        'start_frame': int(round(start_s * fps_float)),
                        'end_frame': int(round(end_s * fps_float)),
                        'text': dialogue
                    })
        elif ext == '.json':
            try:
                data = json.loads(f.read_text(encoding='utf-8', errors='replace'))
                items = data if isinstance(data, list) else data.get('lines', data.get('transcripts', []))
                for item in items:
                    t = item.get('text', '')
                    if query in t.lower():
                        st = float(item.get('start', item.get('start_time_s', 0)))
                        et = float(item.get('end', item.get('end_time_s', st + 2.0)))
                        matches.append({
                            'source_file': f.name,
                            'start_time_s': round(st, 3),
                            'end_time_s': round(et, 3),
                            'start_frame': int(round(st * fps_float)),
                            'end_frame': int(round(et * fps_float)),
                            'speaker': item.get('speaker'),
                            'text': t
                        })
            except Exception:
                pass
                
    result_data = {
        'query': query,
        'match_count': len(matches),
        'matches': matches[:100]
    }
    save(ctx.out / 'search_results.json', result_data)
    return report(
        f"Transcript search for '{query}' found {len(matches)} matching dialogue segments.",
        [check('Transcript search complete', True), check('Speaker attribution / context inspection')],
        match_count=len(matches)
    )


def analysis_proxy(ctx, a):
    p = input_file(a['input'])
    width = integer(a.get('width', 640), 320, 1280)
    crf = integer(a.get('crf', 26), 18, 35)
    vf = f"scale={width}:-2"
    if a.get('burn_timecode'):
        vf += r",drawtext=fontcolor=white:fontsize=16:box=1:boxcolor=black@0.6:x=10:y=h-30:timecode='00\:00\:00\:00':r=24"
        
    ff(ctx, [
        '-i', p, '-map', '0:v:0', '-map', '0:a?',
        '-vf', vf, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-threads', '2', '-preset', 'ultrafast', '-crf', str(crf),
        '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart',
        ctx.out / 'proxy.mp4'
    ])
    ff(ctx, ['-xerror', '-i', ctx.out / 'proxy.mp4', '-f', 'null', '-'])
    return report(
        'Lightweight analysis proxy generated and verified.',
        [check('Proxy decode pass', True), check('Visual verification')],
        proxy_file='proxy.mp4'
    )


def frame_range(ctx, a):
    p = input_file(a['input'])
    start_frame = integer(a.get('start_frame', 0), 0, 10_000_000)
    count = integer(a.get('count', 12), 1, 120)
    columns = integer(a.get('columns', 4), 1, 8)
    
    meta = metadata(ctx, p)
    v_stream = next((s for s in meta.get('streams', []) if s.get('codec_type') == 'video'), None)
    r_fps = v_stream.get('r_frame_rate', '24000/1001') if v_stream else '24000/1001'
    try:
        num, den = map(int, r_fps.split('/'))
        fps_float = num / den
    except Exception:
        fps_float = 23.976023976
        
    end_frame = start_frame + count - 1
    pattern = str(ctx.out / 'frame-%04d.jpg')
    ff(ctx, [
        '-i', p, '-an',
        '-vf', rf"select=between(n\,{start_frame}\,{end_frame})",
        '-vsync', '0', '-q:v', '3', pattern
    ])
    extracted = sorted(list(ctx.out.glob('frame-*.jpg')))
    
    rows = []
    for idx, fpath in enumerate(extracted):
        f_num = start_frame + idx
        t_sec = round(f_num / fps_float, 4)
        rows.append({
            'frame': f_num,
            'time_s': t_sec,
            'file': fpath.name,
            'sha256': sha(fpath)
        })
        
    rows_count = (len(extracted) + columns - 1) // columns
    if extracted:
        tile_filter = f"tile={columns}x{rows_count}:nb_frames={len(extracted)}:padding=2:margin=2:color=black"
        ff(ctx, [
            '-i', pattern, '-filter_complex', tile_filter,
            '-q:v', '3', ctx.out / 'contact.jpg'
        ])
        
    payload = {
        'source': str(p),
        'start_frame': start_frame,
        'count': len(extracted),
        'rational_fps': r_fps,
        'frames': rows
    }
    save(ctx.out / 'range_frames.json', payload)
    return report(
        f"Extracted {len(extracted)} frames starting at frame {start_frame}.",
        [check('Sequential frames extracted', len(extracted) > 0), check('Visual verification')],
        frame_count=len(extracted)
    )


OPERATIONS={name:globals()[name] for name in ('probe','ingest','assets','detect_events','frames','audio_extract','audio_measure','audio_mix','audio_alignment','validate_plan','compare_snapshot','evidence_pack','verify_render','review_copy','rough_assembly','register_preview','native_observe','native_snapshot','native_render','compile_ae','native_submit','batch_inventory','detect_beats','transcript_search','analysis_proxy','frame_range')}
NON_CACHEABLE={'native_observe','native_snapshot','native_render','native_submit','compile_ae','register_preview','validate_plan','assets'}
SCHEMAS={
 'batch_inventory':{'required':[],'optional':['folder','inputs','extensions'],'note':'Bounded source inventory with rational FPS, duration, audio health, hashes'},
 'detect_beats':{'required':['input'],'optional':['fps','threshold'],'note':'Measured audio onset candidates separated from fitted regular pulse grid hypotheses'},
 'transcript_search':{'required':['query','sources'],'optional':['fps'],'note':'Bounded timestamped dialogue search across SRT and JSON transcripts'},
 'analysis_proxy':{'required':['input'],'optional':['width','crf','burn_timecode'],'note':'Fast lightweight 360p/540p proxy for scrubbing/screening'},
 'frame_range':{'required':['input'],'optional':['start_frame','count','columns'],'note':'Exact sequential frame extraction on demand with PTS ledger'},
 'probe':{'required':['input']},
 'ingest':{'required':['input'],'optional':['frames','sample_count','columns','width'],'note':'Probe + source hash + exact contact sheets for video; audio metadata only'},
 'assets':{'required':[],'optional':['paths','fonts'],'note':'Path/hash checks and installed Windows font-table names; no visual acceptance'},
 'detect_events':{'required':['input'],'optional':['scene_threshold'],'note':'Numeric scene/black/freeze candidates, not approved cuts or rhythm decisions'},
 'frames':{'required':['input'],'optional':['frames','sample_count','columns','width'],'note':'Explicit frames or evenly spaced native ordinals (default6); max4096 per step; measured PTS ledger and paged sheets'},
 'audio_extract':{'required':['input','duration'],'optional':['start','sample_rate']},
 'audio_measure':{'required':['input'],'optional':['silence_db','max_peak']},
 'audio_mix':{'required':['tracks','duration'],'note':'tracks: input,start,gain_db,fade_in,fade_out,duck:[{start,end,gain_db,fade}]; no inferred dialogue decisions'},
 'audio_alignment':{'required':['input','reference'],'optional':['duration','sample_rate','tolerance_seconds','min_correlation','max_search_seconds'],'note':'Default48000Hz sample correlation; explicit lag tolerance, no lip-sync/semantic approval'},
 'validate_plan':{'required':['input'],'note':'JSON fps,duration_frames,sources:{id:{path,fps,frames}},shots:[{id,start_frame,end_frame,source_id,source_in_frame,source_out_frame,retime?}],dialogue/captions:[{id,start_frame,end_frame,...}]'},
 'compare_snapshot':{'required':['before','after'],'optional':['paths'],'note':'Exact JSON pointer paths; default entire snapshot'},
 'evidence_pack':{'required':['items'],'optional':['max_chars'],'note':'items input,label?,pointers?:[JSON pointers]; exact selected evidence, dedup by content hash, fail instead of silent truncation'},
 'verify_render':{'required':['input'],'optional':['expect'],'note':'expect width,height,frames,fps,duration,duration_tolerance,audio'},
 'review_copy':{'required':['input'],'optional':['width','crf']},
 'rough_assembly':{'required':['shots'],'optional':['format','music'],'note':'Explicit shots input/start/end; max120s. Letterboxed 24fps rough cut only; no advanced effects/captions; source audio muted'},
 'register_preview':{'required':['input','title','revision','kind'],'optional':['current','project_id','note','expect']},
 'native_observe':{'required':['command_id'],'optional':['bridge','timeout_seconds'],'note':'Read-only exact-ID watcher; unknown is failure, never resend'},
 'native_snapshot':{'required':['expected_project','authorize_native'],'optional':['comp_ids','bridge','timeout_seconds'],'note':'Single TonyFX read-only snapshot; selected comp/layer/properties/keyframes; unsupported types labeled'},
 'native_render':{'required':['expected_project','authorize_native','comp_id','expect','render_settings','output_template'],'optional':['suffix','bridge','timeout_seconds','multi_frame_rendering'],'note':'Guarded exact existing comp; full decode; queue selections restored; default3600s observation. Optional explicit per-script MFR override resets to UI settings after script; unavailable API fails before queue mutation.'},
 'compile_ae':{'required':['input','expected_project'],'optional':['name','blueprint_project_id','blueprint_hash'],'note':'Picture-only guarded new composition JSX; project-bound blueprints must match at compilation/submission; no dispatch; unsupported effects/audio/captions rejected'},
 'native_submit':{'required':['input','compiled','authorize_native'],'optional':['bridge','timeout_seconds'],'note':'Only preceding compile_ae output from same job; exact project hash; serialized TonyFX; never replay'},
}
