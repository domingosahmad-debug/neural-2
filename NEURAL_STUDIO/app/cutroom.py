"""Versioned manual cut-room document and guarded After Effects compilation/application.

* The timeline JSON is the canonical, frame-exact document (rational fps, integer frames). Saves use optimistic
  concurrency; a stale write is rejected with ``ConflictError`` (HTTP 409) and nothing is overwritten.
* Application never mutates an existing composition, master or user tweak. The generated ExtendScript only ADDS a new
  folder + composition (nesting the original comp as an editable source so its effects stay live, or using imported footage),
  then saves the in-memory project as a NEW revision file. The original .aep on disk is not rewritten.
* All writers share the one existing TonyFX lane. The native hold (``require_native_ready``), the director/Lumen/local lane,
  bridge state, project identity and media identity are checked before anything is submitted. A dry run is never reported as
  native success; an UNKNOWN submission is never retried.
* No arbitrary script text from the renderer is ever executed: the script is built here from validated plan data only.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
import re
import threading
import time
import uuid
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlencode

ID_RE = re.compile(r'[A-Za-z0-9_.:-]{1,80}')
PROJECT_RE = re.compile(r'[A-Za-z0-9_-]{1,80}')
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.webm', '.mxf', '.mpg', '.mpeg', '.wmv', '.png', '.jpg', '.jpeg', '.tif', '.tiff'}
AUDIO_EXT = {'.wav', '.mp3', '.aac', '.m4a', '.flac', '.ogg', '.aif', '.aiff', '.wma', '.opus'}
MAX_FRAMES = 10_000_000
MAX_DOC_BYTES = 2_000_000
DEFAULT_FPS = '24000/1001'
ACTIVE_STATES = {'SUBMITTING', 'SUBMITTED', 'UNKNOWN'}
GAIN_MIN, GAIN_MAX = -192.0, 24.0
DOCUMENT_LOCK = threading.RLock()  # shared across per-request Store instances


class ConflictError(ValueError):
    """Stale optimistic-concurrency write (HTTP 409)."""


class CapabilityError(ValueError):
    """The document contains values that the compiler cannot faithfully apply; nothing is silently ignored."""
    def __init__(self, message, problems=None):
        super().__init__(message)
        self.problems = problems or []


def _atomic(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    for attempt in range(8):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.015 * (attempt + 1))


def _read(path: Path):
    for attempt in range(6):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.015 * (attempt + 1))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def parse_rate(value, label='fps') -> Fraction:
    """Rational frame rate as an exact string 'N' or 'N/D' (or an int). Floats are rejected: they are not canonical."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(label + ' must be an exact rational string like "24000/1001" (floats are not canonical)')
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,6}(/\d{1,6})?', value.strip()):
        raise ValueError(label + ' must be an exact rational string like "24000/1001"')
    n, _, d = value.strip().partition('/')
    if int(d or 1) == 0 or int(n) == 0:
        raise ValueError(label + ' must be positive')
    rate = Fraction(int(n), int(d or 1))
    if not 1 <= rate <= 240:
        raise ValueError(label + ' must be between 1 and 240 frames per second')
    return rate


def _int(value, label, low=0, high=MAX_FRAMES):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer from {low} to {high}')
    return value


def _number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be a number from {low} to {high}')
    return value


def _bool(value, label):
    if type(value) is not bool:
        raise ValueError(label + ' must be true or false')
    return value


def _path(value, label, allowed_ext):
    if not isinstance(value, str) or not value or len(value) > 1000 or '\x00' in value:
        raise ValueError(label + ' must be an absolute file path string')
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts:
        raise ValueError(label + ' must be absolute without ".." segments')
    if allowed_ext is not None and p.suffix.lower() not in allowed_ext:
        raise ValueError(label + ' has an unsupported extension ' + p.suffix)
    return value


def empty_timeline() -> dict:
    return {'fps': DEFAULT_FPS, 'duration_frames': 0,
            'tracks': [{'id': 'V1', 'name': 'Video 1', 'kind': 'video', 'muted': False, 'clips': []},
                       {'id': 'A1', 'name': 'Audio 1', 'kind': 'audio', 'muted': False, 'clips': []}], 'notes': [], 'markers': []}


def validate_timeline(timeline) -> dict:
    """Validate and canonicalize. Raises ValueError with a specific field message."""
    if not isinstance(timeline, dict):
        raise ValueError('timeline must be an object')
    allowed = {'fps', 'duration_frames', 'width', 'height', 'tracks', 'notes', 'markers', 'ui'}
    extra = set(timeline) - allowed
    if extra:
        raise ValueError('Unknown timeline field(s): ' + ', '.join(sorted(extra)) + ' (view state belongs under "ui")')
    rate = parse_rate(timeline.get('fps', DEFAULT_FPS))
    duration = _int(timeline.get('duration_frames', 0), 'duration_frames')
    out = {'fps': str(rate), 'duration_frames': duration}
    for key in ('width', 'height'):
        if key in timeline and timeline[key] is not None:
            out[key] = _int(timeline[key], key, 64, 7680)
    ui = timeline.get('ui')
    if ui is not None:
        if not isinstance(ui, dict) or len(json.dumps(ui)) > 65536:
            raise ValueError('ui must be an object under 64 KB')
        out['ui'] = ui
    tracks = timeline.get('tracks')
    if not isinstance(tracks, list) or len(tracks) > 64:
        raise ValueError('tracks must be a list of at most 64 tracks')
    seen_tracks, seen_clips, total = set(), set(), 0
    out_tracks = []
    for ti, track in enumerate(tracks):
        label = f'tracks[{ti}]'
        if not isinstance(track, dict):
            raise ValueError(label + ' must be an object')
        extra = set(track) - {'id', 'name', 'kind', 'muted', 'clips', 'locked', 'height'}
        if extra:
            raise ValueError(label + ' has unknown field(s): ' + ', '.join(sorted(extra)))
        tid = track.get('id')
        if not isinstance(tid, str) or not ID_RE.fullmatch(tid) or tid in seen_tracks:
            raise ValueError(label + '.id must be a unique short identifier')
        seen_tracks.add(tid)
        if track.get('kind') not in ('video', 'audio'):
            raise ValueError(label + '.kind must be video or audio')
        name = track.get('name', tid)
        if not isinstance(name, str) or len(name) > 120:
            raise ValueError(label + '.name must be a string up to 120 characters')
        row = {'id': tid, 'name': name, 'kind': track['kind'], 'muted': _bool(track.get('muted', False), label + '.muted'), 'clips': []}
        for opt in ('locked',):
            if opt in track:
                row[opt] = _bool(track[opt], label + '.' + opt)
        clips = track.get('clips', [])
        if not isinstance(clips, list) or len(clips) > 5000:
            raise ValueError(label + '.clips must be a list of at most 5000 clips')
        for ci, clip in enumerate(clips):
            total += 1
            if total > 20000:
                raise ValueError('A cut-room document supports at most 20000 clips')
            row['clips'].append(_validate_clip(clip, f'{label}.clips[{ci}]', row['kind'], seen_clips, duration))
        enabled = sorted((c for c in row['clips'] if c['enabled']), key=lambda c: c['start_frame'])
        for a, b in zip(enabled, enabled[1:]):
            if b['start_frame'] < a['start_frame'] + a['duration_frames']:
                raise ValueError(f"Clips {a['id']} and {b['id']} overlap on track {tid}; place overlapping material on another track")
        out_tracks.append(row)
    out['tracks'] = out_tracks
    out['notes'] = _validate_notes(timeline.get('notes', []))
    markers = timeline.get('markers', [])
    if not isinstance(markers, list) or len(markers) > 2000:
        raise ValueError('markers must be a list of at most 2000 items')
    out['markers'] = []
    for i, m in enumerate(markers):
        if not isinstance(m, dict) or set(m) - {'frame', 'label'}:
            raise ValueError(f'markers[{i}] must contain only frame and label')
        label = m.get('label', '')
        if not isinstance(label, str) or len(label) > 200:
            raise ValueError(f'markers[{i}].label must be a string up to 200 characters')
        out['markers'].append({'frame': _int(m.get('frame'), f'markers[{i}].frame'), 'label': label})
    if len(json.dumps(out)) > MAX_DOC_BYTES:
        raise ValueError('The cut-room document exceeds 2 MB')
    return out


def _validate_clip(clip, label, track_kind, seen_ids, timeline_duration):
    if not isinstance(clip, dict):
        raise ValueError(label + ' must be an object')
    allowed = {'id', 'source_path', 'preview_path', 'source_kind', 'source_comp_id', 'source_in_frame', 'start_frame', 'duration_frames', 'gain_db',
               'fade_in_frames', 'fade_out_frames', 'enabled', 'velocity', 'source_fps', 'source_duration_frames', 'name', 'preview_url', 'peaks'}
    extra = set(clip) - allowed
    if extra:
        raise ValueError(label + ' has unknown field(s): ' + ', '.join(sorted(extra)))
    cid = clip.get('id')
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in seen_ids:
        raise ValueError(label + '.id must be a unique short identifier')
    seen_ids.add(cid)
    kind = clip.get('source_kind', 'file')
    if kind not in ('file', 'ae_comp'):
        raise ValueError(label + '.source_kind must be file or ae_comp')
    row = {'id': cid, 'source_kind': kind}
    # preview_url is a host-derived read-only field. Never use a client URL for file access.
    if clip.get('peaks') is not None:
        if not isinstance(clip['peaks'], list) or len(clip['peaks']) > 256:
            raise ValueError(label + '.peaks must contain at most 256 measured values')
        row['peaks'] = [_number(v, label + '.peaks', 0, 1) for v in clip['peaks']]
    if kind == 'file':
        ext = (VIDEO_EXT | AUDIO_EXT) if track_kind == 'audio' else VIDEO_EXT
        row['source_path'] = _path(clip.get('source_path'), label + '.source_path', ext)
    else:
        row['source_path'] = _path(clip.get('source_path'), label + '.source_path', {'.aep', '.aepx'})
        row['source_comp_id'] = _int(clip.get('source_comp_id'), label + '.source_comp_id', 1)
    if clip.get('preview_path') is not None:
        if not isinstance(clip['preview_path'], str) or len(clip['preview_path']) > 1000 or '\x00' in clip['preview_path']:
            raise ValueError(label + '.preview_path must be a path string')
        row['preview_path'] = clip['preview_path']
    if clip.get('source_fps') is not None:
        row['source_fps'] = str(parse_rate(clip['source_fps'], label + '.source_fps'))
    if clip.get('source_duration_frames') is not None:
        row['source_duration_frames'] = _int(clip['source_duration_frames'], label + '.source_duration_frames', 1)
    row['source_in_frame'] = _int(clip.get('source_in_frame', 0), label + '.source_in_frame')
    row['start_frame'] = _int(clip.get('start_frame'), label + '.start_frame')
    row['duration_frames'] = _int(clip.get('duration_frames'), label + '.duration_frames', 1)
    if timeline_duration and row['start_frame'] + row['duration_frames'] > timeline_duration:
        raise ValueError(f'{label} ends at frame {row["start_frame"] + row["duration_frames"]}, beyond duration_frames {timeline_duration}')
    row['gain_db'] = _number(clip.get('gain_db', 0), label + '.gain_db', GAIN_MIN, GAIN_MAX)
    row['fade_in_frames'] = _int(clip.get('fade_in_frames', 0), label + '.fade_in_frames', 0, row['duration_frames'])
    row['fade_out_frames'] = _int(clip.get('fade_out_frames', 0), label + '.fade_out_frames', 0, row['duration_frames'])
    if row['fade_in_frames'] + row['fade_out_frames'] > row['duration_frames']:
        raise ValueError(label + ' fades overlap: fade_in_frames + fade_out_frames exceeds the clip length')
    row['enabled'] = _bool(clip.get('enabled', True), label + '.enabled')
    if clip.get('name') is not None:
        if not isinstance(clip['name'], str) or len(clip['name']) > 200:
            raise ValueError(label + '.name must be a string up to 200 characters')
        row['name'] = clip['name']
    if clip.get('velocity') is not None:
        vel = clip['velocity']
        if not isinstance(vel, list) or len(vel) > 256:
            raise ValueError(label + '.velocity must be a list of at most 256 points')
        pts, last = [], -1.0
        for k, pt in enumerate(vel):
            if not isinstance(pt, dict) or set(pt) != {'time', 'value'}:
                raise ValueError(f'{label}.velocity[{k}] needs time and value')
            t = _number(pt['time'], f'{label}.velocity[{k}].time', 0, 1e7)
            if t <= last:
                raise ValueError(label + '.velocity times must strictly increase')
            last = t
            pts.append({'time': t, 'value': _number(pt['value'], f'{label}.velocity[{k}].value', 0, 100)})
        row['velocity'] = pts
    return row


def _validate_notes(notes):
    if not isinstance(notes, list) or len(notes) > 2000:
        raise ValueError('notes must be a list of at most 2000 items')
    out, seen = [], set()
    for i, n in enumerate(notes):
        if not isinstance(n, dict) or set(n) - {'id', 'frame', 'end_frame', 'text'}:
            raise ValueError(f'notes[{i}] must contain only id, frame, end_frame and text')
        nid = n.get('id')
        if not isinstance(nid, str) or not ID_RE.fullmatch(nid) or nid in seen:
            raise ValueError(f'notes[{i}].id must be a unique short identifier')
        seen.add(nid)
        text = n.get('text')
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError(f'notes[{i}].text must be a string up to 2000 characters')
        row = {'id': nid, 'frame': _int(n.get('frame'), f'notes[{i}].frame'), 'text': text}
        if n.get('end_frame') is not None:
            row['end_frame'] = _int(n['end_frame'], f'notes[{i}].end_frame', row['frame'])
        out.append(row)
    return out


# ------------------------------------------------------------------- compiler
def seconds(frames, rate: Fraction):
    """Exact rational seconds as an [numerator, denominator] pair."""
    s = Fraction(frames) / rate
    return [s.numerator, s.denominator]


def _fade_keys(start, duration, fade_in, fade_out, rate, plateau, floor, mode, steps=8):
    """Keyframes for a linear-AMPLITUDE (audio dB) or linear-opacity (video) fade, exact in frames."""
    keys = []

    def value(fraction):
        if mode == 'audio':
            return floor if fraction <= 0 else max(floor, round(plateau + 20 * math.log10(fraction), 4))
        return round(100 * fraction, 4)
    if fade_in:
        for i in range(0, steps + 1):
            f = Fraction(i, steps)
            keys.append({'t': seconds(Fraction(start) + Fraction(fade_in) * f, rate), 'v': value(float(f))})
    if fade_out:
        end = start + duration
        for i in range(0, steps + 1):
            f = Fraction(i, steps)
            keys.append({'t': seconds(Fraction(end - fade_out) + Fraction(fade_out) * f, rate), 'v': value(float(1 - f))})
    # No key may repeat a time (a fade ending exactly where the other begins keeps the lower-level key).
    unique = {}
    for k in keys:
        unique[tuple(k['t'])] = k
    return sorted(unique.values(), key=lambda k: Fraction(*k['t']))


def compile_timeline(timeline: dict, *, project_id: str, document_version: int, expected_project: str | None, source_comp_id: int | None,
                     expected_comp_name: str | None = None, stat=None) -> dict:
    """Pure, deterministic compile of a VALIDATED timeline into a plan. Raises CapabilityError for unsupported values."""
    timeline = validate_timeline(timeline)
    rate = parse_rate(timeline['fps'])
    problems, warnings, skipped = [], [], []
    sources, layers = {}, []
    stat = stat or (lambda p: (lambda s: {'size': s.st_size, 'mtime_ns': s.st_mtime_ns})(Path(p).stat()))
    if timeline['duration_frames'] < 1:
        raise CapabilityError('The timeline is empty (duration_frames is 0); nothing to apply.', ['duration_frames'])
    order = [t for t in timeline['tracks'] if t['kind'] == 'audio'] + [t for t in timeline['tracks'] if t['kind'] == 'video']
    for track in order:
        for clip in sorted(track['clips'], key=lambda c: (c['start_frame'], c['id'])):
            cid = clip['id']
            if not clip['enabled']:
                skipped.append({'clip_id': cid, 'reason': 'disabled'})
                continue
            if clip.get('velocity'):
                if any(abs(p['value'] - 1) > 1e-9 for p in clip['velocity']):
                    problems.append(f'{cid}: velocity/time-remap is saved in the document but cannot be applied to AE yet (non-identity speed)')
                    continue
            if clip['source_kind'] == 'ae_comp':
                if expected_project is None or str(Path(clip['source_path'])).lower() != str(Path(expected_project)).lower():
                    problems.append(f'{cid}: nested AE comp belongs to a different project than the expected project')
                    continue
                key = 'comp:' + str(clip['source_comp_id'])
                source = {'key': key, 'kind': 'ae_comp', 'comp_id': clip['source_comp_id'], 'path': clip['source_path']}
            else:
                try:
                    st = stat(clip['source_path'])
                except OSError:
                    problems.append(f'{cid}: source file is missing or unreadable: {clip["source_path"]}')
                    continue
                key = 'file:' + str(Path(clip['source_path'])).lower()
                source = {'key': key, 'kind': 'file', 'path': clip['source_path'], 'size': st['size'], 'mtime_ns': st['mtime_ns']}
            src_rate = parse_rate(clip['source_fps'], cid + '.source_fps') if clip.get('source_fps') else rate
            if clip.get('source_duration_frames') is not None:
                needed = Fraction(clip['duration_frames']) * src_rate / rate
                if clip['source_in_frame'] + needed > clip['source_duration_frames']:
                    problems.append(f'{cid}: needs source frames {clip["source_in_frame"]}..{math.ceil(clip["source_in_frame"] + needed)} but the source has {clip["source_duration_frames"]}')
                    continue
            else:
                warnings.append(f'{cid}: source length unknown; bounds are checked inside After Effects before anything is saved')
            source['fps'] = str(src_rate)
            sources.setdefault(key, source)
            if sources[key].get('fps') != str(src_rate) and source['kind'] == 'ae_comp':
                problems.append(f'{cid}: the same comp is used with two different source rates')
                continue
            start_s = Fraction(clip['start_frame']) / rate
            in_s = Fraction(clip['source_in_frame']) / src_rate
            muted = track['muted']
            row = {'id': cid, 'name': clip.get('name') or cid, 'track_id': track['id'], 'track_name': track['name'], 'kind': track['kind'], 'source_key': key,
                   'start_frame': clip['start_frame'], 'duration_frames': clip['duration_frames'], 'source_in_frame': clip['source_in_frame'],
                   'source_fps': str(src_rate), 'gain_db': clip['gain_db'], 'fade_in_frames': clip['fade_in_frames'], 'fade_out_frames': clip['fade_out_frames'],
                   'in_point': seconds(clip['start_frame'], rate), 'out_point': seconds(clip['start_frame'] + clip['duration_frames'], rate),
                   'layer_start': [(start_s - in_s).numerator, (start_s - in_s).denominator], 'muted': muted, 'audio_keys': [], 'opacity_keys': []}
            if clip['fade_in_frames'] or clip['fade_out_frames']:
                row['audio_keys'] = _fade_keys(clip['start_frame'], clip['duration_frames'], clip['fade_in_frames'], clip['fade_out_frames'], rate, clip['gain_db'], GAIN_MIN, 'audio')
            if track['kind'] == 'video' and (clip['fade_in_frames'] or clip['fade_out_frames']):
                row['opacity_keys'] = _fade_keys(clip['start_frame'], clip['duration_frames'], clip['fade_in_frames'], clip['fade_out_frames'], rate, 100, 0, 'video')
            layers.append(row)
    if problems:
        raise CapabilityError('The document cannot be applied faithfully: ' + '; '.join(problems[:8]) + ('; …' if len(problems) > 8 else ''), problems)
    if not layers:
        raise CapabilityError('No enabled clips to apply.', ['no clips'])
    if any(s['kind'] == 'ae_comp' for s in sources.values()) and source_comp_id is None:
        raise CapabilityError('This timeline nests an AE comp; supply source_comp_id so the exact comp identity is verified.', ['source_comp_id'])
    markers = [{'kind': 'note', 'id': n['id'], 'frame': n['frame'], 'duration': seconds(n.get('end_frame', n['frame']) - n['frame'], rate), 'time': seconds(n['frame'], rate), 'text': n['text']} for n in timeline['notes']]
    markers += [{'kind': 'marker', 'id': 'marker-' + str(i), 'frame': m['frame'], 'duration': [0, 1], 'time': seconds(m['frame'], rate), 'text': m['label']} for i, m in enumerate(timeline['markers'])]
    plan = {'version': 1, 'project_id': project_id, 'document_version': document_version, 'document_sha256': canonical_hash(timeline), 'fps': timeline['fps'],
            'fps_num': rate.numerator, 'fps_den': rate.denominator, 'duration_frames': timeline['duration_frames'], 'duration': seconds(timeline['duration_frames'], rate),
            'width': timeline.get('width'), 'height': timeline.get('height'), 'comp_name': f'Manual cutroom v{document_version}', 'source_comp_id': source_comp_id,
            'expected_comp_name': expected_comp_name, 'expected_project': expected_project, 'sources': list(sources.values()), 'layers': layers, 'markers': markers,
            'skipped': skipped, 'warnings': warnings,
            'semantics': {'frames': 'integer frames at the timeline rate; times are exact [numerator, denominator] seconds',
                          'source_offset': 'layer_start = start - source_in/source_fps (frame-exact, no retime)',
                          'audio': 'source audio retained on video and audio clips; gain_db and linear-amplitude fades on Audio Levels',
                          'video': 'fades are linear opacity ramps', 'nesting': 'ae_comp sources are nested live; their internal effects are untouched',
                          'unsupported': 'velocity/retime (non-identity) is refused, never ignored'}}
    plan['plan_sha256'] = canonical_hash({k: v for k, v in plan.items() if k not in ('plan_sha256',)})
    return plan


JSX_TEMPLATE = r'''(function(){__ENCODER__
var cfg=__CONFIG__, p=app.project, folder=null, comp=null, created=[];
function fail(s){throw new Error('Neural cutroom: '+s);}
function write(v){var f=new File(cfg.report);f.encoding='UTF-8';if(!f.open('w'))fail('Report unavailable');f.write(neuralEncode(v));f.close();}
function T(a){return a[0]/a[1];}
function rate(n,d){return n/d;}
function itemById(id){for(var i=1;i<=p.numItems;i++)if(p.item(i).id===id)return p.item(i);return null;}
function run(){
 if(!p||!p.file||p.file.fsName!==new File(cfg.expected_project).fsName)fail('Expected project is not open');
 if(new File(cfg.output).exists)fail('Revision file exists; do not replay');
 for(var i=1;i<=p.numItems;i++)if(p.item(i).comment==='NEURAL_CUTROOM_'+cfg.token)fail('This revision already exists; reconcile, do not replay');
 var originalItems=p.numItems, srcComp=null, w=cfg.width||1920, h=cfg.height||1080, par=1;
 if(cfg.source_comp_id!==null){srcComp=itemById(cfg.source_comp_id);if(!srcComp||!(srcComp instanceof CompItem))fail('Source comp identity changed');
  if(cfg.expected_comp_name&&srcComp.name!==cfg.expected_comp_name)fail('Source comp name differs from the prepared plan');
  if(!cfg.width)w=srcComp.width;if(!cfg.height)h=srcComp.height;par=srcComp.pixelAspect;}
 var items={},k,s;
 // Phase 1: verify every source BEFORE any change.
 for(k=0;k<cfg.sources.length;k++){s=cfg.sources[k];
  if(s.kind==='file'){var f=new File(s.path);if(!f.exists)fail('Missing source file '+s.path);if(f.length!==s.size)fail('Source file changed since preparation: '+s.path);}
  else{var ci=itemById(s.comp_id);if(!ci||!(ci instanceof CompItem))fail('Nested comp '+s.comp_id+' is missing');
   var sr=s.fps.split('/');var want=Number(sr[0])/Number(sr[1]||1);if(Math.abs(ci.frameRate-want)>0.001)fail('Nested comp frame rate differs from the document');}}
 // Preserve unsaved manual work into its own recovery file before additive edits.
 if(p.dirty){var recovery=new File(new File(cfg.output).parent.fsName+'/RECOVERY_before_manual_'+cfg.token+'.aep');if(recovery.exists)fail('Recovery exists; reconcile');p.save(recovery);}
 // Phase 2: additive changes only. Existing items, comps and effects are never modified.
 folder=p.items.addFolder('Manual cutroom v'+cfg.document_version+' '+cfg.token.substr(0,6));
 for(k=0;k<cfg.sources.length;k++){s=cfg.sources[k];
  if(s.kind==='ae_comp'){items[s.key]=itemById(s.comp_id);continue;}
  var found=null;for(var q=1;q<=p.numItems;q++){var it=p.item(q);if(it instanceof FootageItem&&it.mainSource&&it.mainSource.file&&it.mainSource.file.fsName===new File(s.path).fsName){found=it;break;}}
  if(found){items[s.key]=found;}else{var imp=p.importFile(new ImportOptions(new File(s.path)));imp.parentFolder=folder;items[s.key]=imp;created.push(imp.id);}}
 comp=p.items.addComp(cfg.comp_name,w,h,par,T(cfg.duration),rate(cfg.fps_num,cfg.fps_den));comp.parentFolder=folder;comp.comment='NEURAL_CUTROOM_'+cfg.token;
 for(k=0;k<cfg.layers.length;k++){var L=cfg.layers[k];var src=items[L.source_key];
  if(L.kind==='video'||L.kind==='audio'){
   var sf=L.source_fps.split('/');var srate=Number(sf[0])/Number(sf[1]||1);
   if(src.duration>0&&L.has_bounds!==false){var needed=(L.source_in_frame/srate)+(L.duration_frames/cfg.fps_num*cfg.fps_den);if(needed>src.duration+1/srate)fail('Clip '+L.id+' reads past the end of its source');}
  }
  var layer=comp.layers.add(src);layer.name=L.name;layer.comment='NEURAL_CLIP:'+L.id;
  if(L.kind==='video'&&src.width>0&&src.height>0){var fit=Math.min(w/src.width,h/src.height)*100;layer.property('ADBE Transform Group').property('ADBE Scale').setValue([fit,fit]);}
  layer.startTime=T(L.layer_start);layer.inPoint=T(L.in_point);layer.outPoint=T(L.out_point);
  if(L.kind==='video'){layer.audioEnabled=!!src.hasAudio&&!L.muted;if(L.muted)layer.enabled=false;
   if(L.opacity_keys.length){var op=layer.property('ADBE Transform Group').property('ADBE Opacity');for(var o=0;o<L.opacity_keys.length;o++)op.setValueAtTime(T(L.opacity_keys[o].t),L.opacity_keys[o].v);}}
  else{layer.enabled=false;layer.audioEnabled=!L.muted;}
  if(src.hasAudio){var al=layer.property('ADBE Audio Group').property('ADBE Audio Levels');if(L.audio_keys.length){for(var a=0;a<L.audio_keys.length;a++){var v=L.audio_keys[a].v;al.setValueAtTime(T(L.audio_keys[a].t),[v,v]);}}else{al.setValue([L.gain_db,L.gain_db]);}}
 }
 for(k=0;k<cfg.markers.length;k++){var m=cfg.markers[k];var mv=new MarkerValue(m.text);if(m.duration[0]>0)mv.duration=T(m.duration);try{mv.chapter=m.kind;}catch(e){}comp.markerProperty.setValueAtTime(T(m.time),mv);}
 if(p.numItems<originalItems)fail('Project item count shrank; refusing to save');
 p.save(new File(cfg.output));
 write({ok:true,comp_id:comp.id,comp_name:comp.name,project:cfg.output,original_project_untouched:cfg.expected_project,original_items_before:originalItems,layers:comp.numLayers,
  fps:rate(cfg.fps_num,cfg.fps_den),frames:cfg.duration_frames,notes:'New revision saved as a separate project file. The original project file was not rewritten; the open project now points at the revision.'});
}
app.beginUndoGroup('Neural manual cutroom revision');try{run();}catch(e){write({ok:false,error:String(e),partial_folder_id:folder?folder.id:null,partial_comp_id:comp?comp.id:null,note:'Nothing was saved. Items created in memory can be removed with Undo.'});throw e;}finally{app.endUndoGroup();}
})();'''


def render_script(plan: dict, token: str, output: str, report: str, encoder: str) -> str:
    cfg = {k: plan[k] for k in ('fps_num', 'fps_den', 'duration', 'duration_frames', 'width', 'height', 'comp_name', 'source_comp_id', 'expected_comp_name', 'expected_project',
                                'sources', 'layers', 'markers')}
    cfg.update(token=token, output=output, report=report, document_version=plan['document_version'])
    return JSX_TEMPLATE.replace('__ENCODER__', encoder).replace('__CONFIG__', json.dumps(cfg, ensure_ascii=True))


# ----------------------------------------------------------------- the store
def lane_blockers(runtime) -> list[str]:
    """Reasons another TonyFX writer must wait. Read-only; an unreadable state counts as owned."""
    reasons = []
    try:
        editor = getattr(runtime, 'lumen_editor', None)
        if editor and editor.owns_editor() is True:
            reasons.append('A Lumen trial owns the editing lane.')
    except Exception:
        reasons.append('Lumen ownership could not be read.')
    command = getattr(runtime, 'command', None)
    if command is not None:
        try:
            if command.saved['leader']['status'] in command.active:
                reasons.append('A director turn is ' + command.saved['leader']['status'] + '; only one TonyFX writer may act.')
            if any(w.get('kind') == 'native' and w.get('status') in ('waiting', 'ready') for w in command.saved.get('watches', {}).values()):
                reasons.append('A native command watch is unresolved.')
            pending = command._handoff_native_pending()
            if pending:
                reasons.append('Native command ' + str(pending) + ' is unresolved.')
        except Exception:
            reasons.append('Director/native state could not be read.')
    engine = getattr(runtime, 'local_ops', None)
    if engine is not None:
        try:
            if engine.snapshot().get('active'):
                reasons.append('A local/native job is active.')
        except Exception:
            reasons.append('Local engine state could not be read.')
    return reasons


class CutroomStore:
    def __init__(self, root, *, bridge=None, runtime=None, submitter=None, lane=None, project_sha=sha256_file):
        self.root = Path(root).resolve()
        self.base = self.root / 'data' / 'cutroom'
        self.bridge = Path(bridge or os.environ.get('NEURAL_TONYFX_BRIDGE') or (Path.home() / 'Documents/ae-mcp-bridge'))
        self.runtime = runtime
        self.lane = lane or (lambda: lane_blockers(runtime) if runtime is not None else [])
        self.submitter = submitter
        self.project_sha = project_sha
        self.lock = DOCUMENT_LOCK

    # --- paths
    def _doc(self, pid):
        if not isinstance(pid, str) or not PROJECT_RE.fullmatch(pid):
            raise ValueError('Invalid project_id')
        return self.base / 'documents' / (pid + '.json')

    def _apply_path(self, pid):
        self._doc(pid)
        return self.base / 'apply' / (pid + '.json')

    def capabilities(self):
        return {'document': {'schema': 'cutroom-timeline-1', 'rational_fps': True, 'optimistic_concurrency': True, 'max_clips': 20000, 'max_bytes': MAX_DOC_BYTES},
                'apply': {'mode': 'new_revision_comp_in_new_project_file', 'retains_original_comps_and_effects': True, 'rewrites_original_project_file': False,
                          'ae_comp_nesting': True, 'audio_gain': True, 'audio_fades': 'linear amplitude, 8 segments', 'video_fades': 'linear opacity',
                          'notes_markers': True, 'source_offsets': 'frame exact', 'retime_velocity': 'saved only; non-identity refused at apply',
                          'video_clip_audio_gain': True, 'effects_authored': False,
                          'dry_run_is_native_success': False, 'live_roundtrip': 'UNTESTED in this environment'},
                'preview': 'Browser proxy playback cannot show AE effects; those need native preview.'}

    # --- document
    def import_preview(self, data):
        """User-requested preparation through the shared local engine, with zero model calls."""
        from previews import PreviewCatalog
        source = PreviewCatalog(self.root).media(data.get('preview_id', ''))
        rate = parse_rate(data.get('fps', DEFAULT_FPS), 'fps')
        return self._prepare_source(source, rate, '/api/preview-media?id=' + data['preview_id'])

    def import_source(self, data):
        """Prepare user-selected media; keep source ownership separate from a saved timeline."""
        pid = data.get('project_id')
        self._doc(pid)  # validate the project key before using it in a filename
        source = Path(str(data.get('source_path', '')))
        if not source.is_absolute() or not source.is_file() or source.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac'):
            raise ValueError('Choose an existing video or audio file using its full path')
        source = source.resolve()
        path = self.base / (pid + '.sources.json')
        with self.lock:
            try: rows = _read(path)
            except FileNotFoundError: rows = {}
            key = next((k for k, r in rows.items() if r['path'] == str(source)), None) or uuid.uuid4().hex
            rows[key] = {'path': str(source)}
            # Only small path records are stored; original media is never copied or removed.
            _atomic(path, rows)
        rate = parse_rate(data.get('fps', DEFAULT_FPS), 'fps')
        return self._prepare_source(source, rate, '/api/cutroom/source?project_id=' + pid + '&source_id=' + key)

    def prepared_source(self, project_id, source_id):
        self._doc(project_id)
        with self.lock:
            rows = _read(self.base / (project_id + '.sources.json'))
            row = rows.get(source_id)
            if not row or not Path(row['path']).is_file():
                raise ValueError('This media source is not registered in the manual editing project')
            return Path(row['path'])

    def _prepare_source(self, source, rate, preview_url):
        from local_engine import LocalEngine
        engine = getattr(self.runtime, 'local_ops', None)
        owned = engine is None
        if owned:
            engine = LocalEngine(self.root)
        try:
            if engine.snapshot().get('active'):
                raise ValueError('The local media lane is busy. The import was not started; try after current processing finishes.')
            job = engine.submit({'version': 1, 'title': 'Cutroom source metadata', 'steps': [{'id': 'probe', 'operation': 'probe', 'args': {'input': str(source)}}]}, background=False)
            if job['status'] != 'COMPLETED':
                raise ValueError('Source preparation failed: ' + str(job.get('error')))
            meta = job['steps'][0]['report']['metadata']
            video = next((s for s in meta.get('streams', []) if s.get('codec_type') == 'video'), None)
            duration = float(meta.get('format', {}).get('duration') or (video or {}).get('duration') or 0)
            if not 0 < duration <= 86400:
                raise ValueError('The source has no supported measured duration')
            raw_rate = (video or {}).get('avg_frame_rate')
            src_rate = parse_rate(raw_rate if raw_rate not in (None, '0/0') else str(rate), 'source fps')
            raw_frames = (video or {}).get('nb_frames')
            frames = int(raw_frames) if str(raw_frames).isdigit() else round(Fraction(str(duration)) * src_rate)
            clip = {'id': 'import-' + uuid.uuid4().hex[:16], 'name': source.stem, 'source_path': str(source), 'source_kind': 'file',
                    'source_in_frame': 0, 'start_frame': 0, 'duration_frames': max(1, round(Fraction(frames) * rate / src_rate)),
                    'source_fps': str(src_rate), 'source_duration_frames': frames, 'gain_db': 0,
                    'fade_in_frames': 0, 'fade_out_frames': 0, 'enabled': True,
                    'preview_path': str(source),
                    # Registered, host-owned media can play before the first timeline save.
                    'preview_url': preview_url}
            wave_job = None
            if duration <= 180 and any(s.get('codec_type') == 'audio' for s in meta.get('streams', [])):
                wave_job = engine.submit({'version': 1, 'title': 'Cutroom measured waveform', 'steps': [{'id': 'wave', 'operation': 'audio_measure', 'args': {'input': str(source)}}]}, background=False)
                wave_file = engine.folder(wave_job['id']) / 'wave' / 'waveform.json'
                if wave_file.is_file():
                    samples = [p[1] for p in _read(wave_file)['peaks']]
                    if samples:
                        clip['peaks'] = [max(samples[i * len(samples) // min(256, len(samples)):(i + 1) * len(samples) // min(256, len(samples))]) for i in range(min(256, len(samples)))]
            return {'clip': clip, 'metadata_job_id': job['id'], 'waveform_job_id': wave_job['id'] if wave_job else None,
                    'model_calls': 0, 'native_applied': False, 'width': (video or {}).get('width'), 'height': (video or {}).get('height')}
        finally:
            if owned:
                engine.shutdown()

    def get(self, project_id):
        with self.lock:
            path = self._doc(project_id)
            try:
                doc = _read(path)
            except FileNotFoundError:
                doc = {'project_id': project_id, 'version': 0, 'timeline': empty_timeline()}
            timeline = json.loads(json.dumps(doc['timeline']))
            for track in timeline['tracks']:
                for clip in track['clips']:
                    candidate = self._media_candidate(clip)
                    if candidate:
                        clip['preview_url'] = '/api/cutroom/media?' + urlencode({'project_id': project_id, 'clip_id': clip['id']})
            return {'project_id': project_id, 'version': doc['version'], 'timeline': timeline, 'capabilities': self.capabilities(), 'apply_status': self.apply_status(project_id)}

    @staticmethod
    def _media_candidate(clip):
        for raw in (clip.get('preview_path'), clip.get('source_path') if clip.get('source_kind') == 'file' else None):
            if isinstance(raw, str):
                p = Path(raw)
                if p.is_absolute() and p.suffix.lower() in (VIDEO_EXT | AUDIO_EXT) and p.is_file():
                    return p
        return None

    def media(self, project_id, clip_id):
        with self.lock:
            doc = _read(self._doc(project_id))
            clip = next((c for t in doc['timeline']['tracks'] for c in t['clips'] if c['id'] == clip_id), None)
            path = self._media_candidate(clip) if clip else None
            if path is None:
                raise ValueError('No playable local media belongs to this saved clip; AE comp previews need a rendered proxy')
            return path

    def save(self, project_id, expected_version, timeline):
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('expected_version must be a non-negative integer')
        timeline = validate_timeline(timeline)
        with self.lock:
            path = self._doc(project_id)
            try:
                current = _read(path)
            except FileNotFoundError:
                current = {'version': 0}
            if current['version'] != expected_version:
                raise ConflictError(f'Stale cut-room document: you edited version {expected_version} but the saved version is {current["version"]}. Reload before saving; nothing was overwritten.')
            version = current['version'] + 1
            doc = {'project_id': project_id, 'version': version, 'timeline': timeline, 'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'sha256': canonical_hash(timeline)}
            history = path.parent / (project_id + '.history')
            _atomic(history / f'v{version:05d}.json', doc)
            _atomic(path, doc)
            for old in sorted(history.glob('v*.json'))[:-50]:   # bounded revision history of small documents
                try:
                    old.unlink()
                except OSError:
                    pass
            return self.get(project_id)

    # --- apply
    def apply_status(self, project_id):
        path = self._apply_path(project_id)
        try:
            status = _read(path)
        except FileNotFoundError:
            return {'state': 'NONE', 'native_applied': False, 'detail': 'Nothing prepared. A dry run is not an application.'}
        return self._observe(project_id, status)

    def _observe(self, project_id, status):
        """Read-only completion check against exact bridge records; never sends or retries anything."""
        if status.get('state') not in ('SUBMITTED', 'UNKNOWN') or not status.get('command_id'):
            return status
        try:
            command = _read(self.bridge / 'ae_command.json')
            result = _read(self.bridge / 'ae_mcp_result.json')
        except (OSError, ValueError):
            return status
        if command.get('id') == status['command_id'] and command.get('status') not in ('pending', 'running') and result.get('_commandId') == status['command_id'] and result.get('_servicedBy') == 'TonyFX' and type(result.get('ok')) is bool:
            report = None
            try:
                report = _read(Path(status['report_path']))
            except (OSError, ValueError, KeyError):
                pass
            ok = result['ok'] is True and bool(report) and report.get('ok') is True
            status = {**status, 'state': 'COMPLETED' if ok else 'FAILED', 'native_applied': ok, 'completed_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                      'script_report': report, 'detail': ('TonyFX completed and the script wrote its own ok report. Visual/artistic review is still required.' if ok
                                                          else 'TonyFX transport or the script reported failure/no report: ' + str((report or {}).get('error') or result.get('error') or 'missing script report') + ' Inspect before any new attempt; nothing is retried.')}
            _atomic(self._apply_path(project_id), status)
        return status

    def _load_submitter(self):
        if self.submitter:
            return self.submitter
        helper = self.root / 'knowledge/skills/tfx-tonyfx-execution/scripts/bridge.py'
        spec = importlib.util.spec_from_file_location('neural_tonyfx_client_cutroom', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.submit

    def apply(self, data):
        from lumen_editor import EDITOR_LOCK
        project_id = data.get('project_id')
        self._doc(project_id)
        expected_version = data.get('expected_version')
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('expected_version must be a non-negative integer')
        dry_run = data.get('dry_run', True)
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be true or false')
        expected_project = data.get('expected_project')
        if isinstance(expected_project, dict):
            expected_project = expected_project.get('path')
        if not isinstance(expected_project, str) or len(expected_project) > 1000:
            raise ValueError('expected_project must be the absolute path of the open .aep project')
        _path(expected_project, 'expected_project', {'.aep'})
        comp_id = data.get('source_comp_id')
        if comp_id is not None:
            comp_id = _int(comp_id, 'source_comp_id', 1)
        comp_name = data.get('expected_comp_name')
        if comp_name is not None and (not isinstance(comp_name, str) or len(comp_name) > 300):
            raise ValueError('expected_comp_name must be a string')
        with EDITOR_LOCK, self.lock:
            try:
                doc = _read(self._doc(project_id))
            except FileNotFoundError:
                raise ValueError('No cut-room document is saved for this project; save one first.')
            if doc['version'] != expected_version:
                raise ConflictError(f'Stale cut-room document: requested version {expected_version}, saved version {doc["version"]}. Reload; nothing was applied.')
            project_file = Path(expected_project)
            if not project_file.is_file():
                raise ValueError('The expected project file does not exist on disk: the apply plan is kept but cannot be prepared.')
            project_hash = self.project_sha(project_file)
            plan = compile_timeline(doc['timeline'], project_id=project_id, document_version=doc['version'], expected_project=expected_project, source_comp_id=comp_id, expected_comp_name=comp_name)
            plan['project_sha256'] = project_hash
            plan['project_mtime_ns'] = project_file.stat().st_mtime_ns
            plan['plan_sha256'] = canonical_hash({k: v for k, v in plan.items() if k != 'plan_sha256'})
            prior = None
            try:
                prior = _read(self._apply_path(project_id))
            except FileNotFoundError:
                pass
            if dry_run:
                return self._prepare(project_id, plan, doc, prior)
            return self._submit(project_id, plan, prior, project_file)

    def _prepare(self, project_id, plan, doc, prior):
        if prior and prior.get('state') in ACTIVE_STATES:
            return {'status': 'blocked', 'detail': 'A native application for this project is ' + prior['state'] + '; it must finish or be reconciled first.', 'native_applied': False,
                    'plan_path': prior.get('plan_path')}
        token = uuid.uuid4().hex
        folder = self.base / 'revisions' / project_id / f'v{plan["document_version"]:05d}-{token[:8]}'
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'revision.aep'
        report = folder / 'native-report.json'
        encoder = (Path(__file__).parent / 'ae_json.jsxinc').read_text(encoding='utf-8')
        plan['token'] = token
        plan['output'] = str(output)
        plan['report'] = str(report)
        plan['plan_sha256'] = canonical_hash({k: v for k, v in plan.items() if k not in ('plan_sha256', 'token', 'output', 'report')})
        script = render_script(plan, token, str(output), str(report), encoder)
        _atomic(folder / 'plan.json', plan)
        (folder / 'apply.jsx').write_text(script, encoding='utf-8')
        status = {'state': 'PREPARED', 'native_applied': False, 'project_id': project_id, 'document_version': plan['document_version'], 'plan_path': str(folder / 'plan.json'),
                  'script_path': str(folder / 'apply.jsx'), 'plan_sha256': plan['plan_sha256'], 'token': token, 'report_path': str(report), 'output_path': str(output),
                  'prepared_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'detail': 'DRY RUN ONLY. Nothing was sent to After Effects.'}
        _atomic(self._apply_path(project_id), status)
        return {'status': 'dry_run', 'detail': status['detail'] + ' Review the plan, then apply explicitly.', 'plan_path': status['plan_path'], 'script_path': status['script_path'],
                'native_applied': False, 'warnings': plan['warnings'], 'skipped': plan['skipped'], 'layers': len(plan['layers']), 'plan_sha256': plan['plan_sha256']}

    def _blocked(self, detail, prior=None, **extra):
        return {'status': 'blocked', 'detail': detail + ' The saved plan is kept intact.', 'native_applied': False, 'plan_path': (prior or {}).get('plan_path'), **extra}

    def _submit(self, project_id, plan, prior, project_file):
        if not prior or prior.get('state') != 'PREPARED' or prior.get('document_version') != plan['document_version']:
            return self._blocked('Prepare this exact version with a dry run first.', prior)
        saved_plan = _read(Path(prior['plan_path']))
        comparable = lambda p: canonical_hash({k: v for k, v in p.items() if k not in ('plan_sha256', 'token', 'output', 'report')})
        if comparable(saved_plan) != comparable(plan):
            return self._blocked('The document, project file or media changed since the dry run; prepare again.', prior)
        # Every writer shares one TonyFX lane and honors the existing native hold.
        from execution_control import require_native_ready
        try:
            require_native_ready(self.root)
        except ValueError as e:
            return self._blocked(str(e), prior)
        others = [s for s in self._all_active() if s.get('project_id') != project_id]
        if others:
            return self._blocked('Another cut-room application is ' + others[0]['state'] + '; only one native writer may act.', prior)
        reasons = self.lane()
        if reasons:
            return self._blocked(' '.join(reasons), prior)
        if not self.bridge.is_dir():
            return self._blocked('The TonyFX bridge is unavailable; no host is launched.', prior)
        try:
            current = _read(self.bridge / 'ae_command.json')
            if current.get('servicedBy') not in (None, 'TonyFX'):
                return self._blocked('The native bridge is owned by another host.', prior)
            if current.get('status') in ('pending', 'running'):
                return self._blocked('The native bridge is busy.', prior)
            if current.get('id'):
                terminal = _read(self.bridge / 'ae_mcp_result.json')
                if terminal.get('_commandId') != current['id'] or terminal.get('_servicedBy') != 'TonyFX' or type(terminal.get('ok')) is not bool:
                    return self._blocked('The previous native completion is unresolved.', prior)
        except FileNotFoundError:
            return self._blocked('Native bridge records are missing; verify TonyFX first.', prior)
        except (OSError, ValueError):
            return self._blocked('Native bridge records are unreadable.', prior)
        script = Path(prior['script_path'])
        if not script.is_file() or canonical_hash(script.read_text(encoding='utf-8')) != canonical_hash(render_script(saved_plan, prior['token'], prior['output_path'], prior['report_path'], (Path(__file__).parent / 'ae_json.jsxinc').read_text(encoding='utf-8'))):
            return self._blocked('The prepared script no longer matches its plan; prepare again.', prior)
        if Path(prior['output_path']).exists():
            return self._blocked('The revision output already exists; reconcile instead of replaying.', prior)
        # Exact project/comp identity and native state are persisted BEFORE the side effect.
        intent = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'project': str(project_file), 'project_sha256': plan['project_sha256'], 'source_comp_id': plan['source_comp_id'],
                  'expected_comp_name': plan['expected_comp_name'], 'bridge_before': {'command': current if 'current' in locals() else None},
                  'plan_sha256': plan['plan_sha256'], 'replay': 'FORBIDDEN; reconcile exact native state after an UNKNOWN result'}
        _atomic(Path(prior['plan_path']).parent / 'apply-intent.json', intent)
        status = {**prior, 'state': 'SUBMITTING', 'native_applied': False, 'submitted_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'detail': 'Submitting through the single TonyFX lane.'}
        _atomic(self._apply_path(project_id), status)
        try:
            request = self._load_submitter()(self.bridge, script)
        except (RuntimeError, ValueError, FileExistsError) as e:
            status.update(state='PREPARED', detail='Not sent: ' + str(e))
            _atomic(self._apply_path(project_id), status)
            return self._blocked('Not sent: ' + str(e), prior)
        except Exception as e:  # ambiguous: the command may or may not have been written. Never retry.
            status.update(state='UNKNOWN', detail='Submission outcome unknown (' + str(e)[:200] + '). Inspect the bridge; this application is never retried automatically.')
            _atomic(self._apply_path(project_id), status)
            return {'status': 'unknown', 'detail': status['detail'], 'native_applied': False, 'plan_path': prior['plan_path'], 'script_path': prior['script_path']}
        status.update(state='SUBMITTED', command_id=request['id'], detail='Submitted to TonyFX. Completion is observed from the exact command result; nothing is retried.')
        _atomic(self._apply_path(project_id), status)
        return {'status': 'submitted', 'detail': status['detail'], 'native_applied': False, 'plan_path': prior['plan_path'], 'script_path': prior['script_path'], 'command_id': request['id']}

    def _all_active(self):
        rows = []
        folder = self.base / 'apply'
        if folder.is_dir():
            for p in folder.glob('*.json'):
                try:
                    s = self._observe(p.stem, _read(p))
                except (OSError, ValueError):
                    s = {'state': 'UNKNOWN', 'project_id': p.stem}
                if s.get('state') in ACTIVE_STATES:
                    rows.append({**s, 'project_id': s.get('project_id', p.stem)})
        return rows

    def reconcile(self, data):
        """Explicit human resolution of an UNKNOWN submission. It records a decision; it never resubmits."""
        project_id = data.get('project_id')
        path = self._apply_path(project_id)
        with self.lock:
            status = self._observe(project_id, _read(path))
            if status.get('state') in ('COMPLETED', 'FAILED'):
                return status
            if status.get('state') not in ACTIVE_STATES:
                raise ValueError('Nothing to reconcile for this project')
            if data.get('resolution') not in ('not_applied', 'applied'):
                raise ValueError('resolution must be not_applied or applied after inspecting After Effects and the bridge')
            status.update(state='RECONCILED_' + data['resolution'].upper(), native_applied=data['resolution'] == 'applied',
                          detail='Human reconciled this UNKNOWN submission as ' + data['resolution'] + '; no command was sent.')
            _atomic(path, status)
            return status
