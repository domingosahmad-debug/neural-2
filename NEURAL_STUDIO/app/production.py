"""Revision-bound production checkpoints. Observation never invokes a model.

An operation completing is not an artistic checkpoint. Evidence is fingerprinted
and revalidated; changing a plan's revision invalidates its old approvals.
"""
import copy
import hashlib
import math
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from operations import load, save, stamp

STATES = {'todo', 'working', 'built', 'verified', 'blocked', 'not_tested', 'awaiting_review'}
GATES = {'technical', 'sequence', 'picture', 'motion', 'listening', 'human'}
METHODS = {'technical': {'numeric', 'native_readback'},
           'sequence': {'source_ledger', 'sampled_frames', 'playback'},
           'picture': {'sampled_frames', 'playback'},
           'motion': {'playback'}, 'listening': {'listening'},
           'human': {'human_acceptance'}}


def seconds(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (AttributeError, ValueError, TypeError):
        return None


def pipeline_view(job, history, now=None):
    """Coarse local-job range only. Unmatched/variable tasks get no countdown."""
    now = time.time() if now is None else now
    steps = job.get('steps', [])
    remaining = [s for s in steps if s.get('status') not in ('COMPLETED', 'SKIPPED')]
    result = {k: job.get(k) for k in ('id', 'title', 'status', 'current_step', 'error')}
    result.update(completed=sum(s.get('status') == 'COMPLETED' for s in steps), total=len(steps),
                  steps=[{k: s.get(k) for k in ('id', 'operation', 'status', 'error', 'started_at', 'finished_at', 'cached')} for s in steps],
                  estimate=None, estimate_note='Local pipeline only; creative work and human review are excluded.')
    if job.get('status') not in ('QUEUED', 'RUNNING'):
        return result
    lower = upper = 0
    samples_min = 100000
    for step in remaining:
        samples = []
        for other in history:
            if other.get('id') == job.get('id'):
                continue
            for row in other.get('steps', []):
                if row.get('operation') != step.get('operation') or row.get('status') != 'COMPLETED' or row.get('cached'):
                    continue
                start, end = seconds(row.get('started_at')), seconds(row.get('finished_at'))
                if start is not None and end is not None and 0 < end-start < 7200:
                    samples.append(end-start)
        # These operations vary drastically with media length/resolution/model.
        # Without a matching workload signature, operation name alone is unsafe.
        if step.get('operation') in {'native_render', 'frames', 'audio_extract', 'audio_mix', 'verify_render', 'review_copy', 'rough_assembly', 'ingest', 'detect_events'} or len(samples) < 3:
            result['estimate_note'] = 'Still measuring: comparable workload timings are unavailable for '+str(step.get('operation'))+'. No overall edit deadline is inferred.'
            return result
        lo, hi = min(samples)*.5, max(samples)*2
        start = seconds(step.get('started_at'))
        elapsed = max(0, now-start) if start is not None else 0
        if elapsed >= hi:
            result['estimate_note'] = 'This step has exceeded the observed range; re-estimating when real progress arrives.'
            return result
        lower += max(0, lo-elapsed)
        upper += hi-elapsed
        samples_min = min(samples_min, len(samples))
    if remaining:
        result['estimate'] = {'low_seconds': round(lower), 'high_seconds': math.ceil(upper), 'basis': 'Observed operation timings; broad low-confidence range', 'samples_at_least': samples_min}
    return result


class ProductionBoard:
    _shared_lock = threading.RLock()
    _shared_fingerprints = {}
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root/'data/production/CURRENT.json'
        self.lock = self._shared_lock
        self._fingerprints = self._shared_fingerprints

    def evidence(self, value):
        p = (self.root/str(value)).resolve()
        if not p.is_relative_to(self.root) or not p.is_file():
            raise ValueError('Checkpoint evidence must be an existing file inside the studio')
        stat = p.stat()
        if stat.st_size > 8*1024*1024:
            raise ValueError('Use a compact report or evidence pack, not a large raw snapshot')
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._fingerprints.get(str(p))
        if cached and cached[0] == signature:
            digest = cached[1]
        else:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self._fingerprints[str(p)] = (signature, digest)
        return {'path': p.relative_to(self.root).as_posix(), 'sha256': digest}

    def update(self, data, *, human_action=False):
        with self.lock:
            try:
                previous = load(self.path)
            except FileNotFoundError:
                previous = {}
            if data.get('expected_updated_at') != previous.get('updated_at'):
                raise ValueError('Production plan changed; reread before updating')
            project, revision = str(data.get('project_id', '')), str(data.get('revision', '')).strip()
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', project) or not revision or len(revision) > 120:
                raise ValueError('An explicit project ID and revision are required')
            rows = data.get('steps', [])
            if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
                raise ValueError('Use 1–32 concrete production checkpoints')
            seen = set()
            steps = []
            same_revision = previous.get('project_id') == project and previous.get('revision') == revision
            old_steps = {s['id']: s for s in previous.get('steps', [])} if same_revision else {}
            for item in rows:
                sid = str(item.get('id', ''))
                state, gate = item.get('status', 'todo'), item.get('gate', 'technical')
                title = str(item.get('title', '')).strip()
                if not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', sid) or sid in seen or not title or len(title) > 200 or state not in STATES or gate not in GATES:
                    raise ValueError('Invalid or duplicate checkpoint')
                seen.add(sid)
                # A new revision must be checked anew; old objects cannot be copied
                # wholesale and magically keep their green ticks.
                if not same_revision and item.get('revision') not in (None, revision):
                    raise ValueError('Recheck evidence for the new revision')
                method = item.get('method')
                blocker = item.get('blocker')
                if blocker is not None:
                    if not isinstance(blocker, dict) or blocker.get('kind') not in ('recoverable', 'capability', 'human_input', 'native_unknown', 'quota') or any(not str(blocker.get(k, '')).strip() for k in ('reason', 'attempted', 'next_action')):
                        raise ValueError('A blocker needs kind, specific reason, attempted diagnosis and next_action')
                    blocker = {k: str(blocker[k])[:1800] for k in ('kind', 'reason', 'attempted', 'next_action')}
                if state == 'blocked' and blocker is None:
                    raise ValueError('Missing work is not a blocker: diagnose and record a specific blocker or keep it to do')
                evidence = [self.evidence(e.get('path') if isinstance(e, dict) else e) for e in item.get('evidence', [])[:8]]
                note = str(item.get('note', ''))[:2400]
                if state == 'verified':
                    if not evidence or method not in METHODS[gate] or not note.strip():
                        raise ValueError('Verified checkpoints need evidence, a gate-appropriate review method and scope/limits')
                    if gate == 'human' and not human_action:
                        # Retaining an existing acceptance is allowed only for
                        # exactly the same revision, evidence and description.
                        old = old_steps.get(sid, {})
                        if not (old.get('status') == 'verified' and old.get('evidence') == evidence and old.get('title') == title):
                            raise ValueError('Only the human acceptance action can approve this gate')
                estimate = item.get('estimate')
                if estimate is not None:
                    lo, hi = estimate.get('low_minutes'), estimate.get('high_minutes')
                    if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) for x in (lo, hi)) or not 0 <= lo <= hi <= 1440 or not str(estimate.get('basis', '')).strip():
                        raise ValueError('Estimate requires a justified finite minute range')
                    estimate = {'low_minutes': lo, 'high_minutes': hi, 'basis': str(estimate['basis'])[:500]}
                steps.append({'id': sid, 'title': title, 'status': state, 'gate': gate, 'revision': revision,
                              'owner': str(item.get('owner', 'Director'))[:120], 'method': method,
                              'note': note, 'evidence': evidence, 'estimate': estimate, 'blocker': blocker,
                              **({'station':item['station']} if item.get('station') in ('media','analysis','story','sound-design','editing','review-delivery') else {}),
                              **({'required_capabilities':item['required_capabilities']} if isinstance(item.get('required_capabilities'),list) and all(isinstance(c,str) for c in item['required_capabilities']) else {})})
            superseded = data.get('superseded', [])
            if not isinstance(superseded, list) or len(superseded) > 32:
                raise ValueError('Superseded checkpoints need a bounded resolution record')
            resolutions = {s.get('id'): s for s in superseded if isinstance(s, dict)}
            if previous.get('project_id') == project:
                for old in previous.get('steps', []):
                    if old['status'] != 'verified' and old['id'] not in seen:
                        resolution = resolutions.get(old['id'], {})
                        replacements = resolution.get('replacement_ids', [])
                        if old['gate'] == 'human' or not str(resolution.get('reason', '')).strip() or not replacements or any(s not in seen for s in replacements):
                            raise ValueError('Carry forward unresolved checkpoint '+old['id']+' or document its reason and replacement checkpoints')
            current = {'version': 1, 'project_id': project, 'revision': revision, 'title': str(data.get('title', revision))[:200],
                       'updated_at': stamp(), 'steps': steps,
                       'execution': 'sequential', 'superseded': superseded, 'scope': str(data.get('scope', 'Current revision only'))[:1000]}
            preview_id = data.get('review_preview_id')
            if any(s['status'] == 'awaiting_review' for s in steps):
                if any(s['status'] == 'awaiting_review' and s['gate'] not in ('motion','listening','picture','sequence') for s in steps):
                    raise ValueError('Final review is for perceptual checks, not unfinished technical work')
                if any(s['status'] not in ('verified','awaiting_review') and s['gate'] != 'human' for s in steps):
                    raise ValueError('Finish actionable production work before final review handoff')
                from previews import PreviewCatalog
                catalog = PreviewCatalog(self.root)
                entry = next((p for p in catalog.listing()['previews'] if p['id'] == preview_id), None)
                if not entry or entry.get('kind') != 'full' or entry.get('project_id') != project or entry.get('revision') != revision:
                    raise ValueError('Final review requires this revision and project\'s registered full review')
                catalog.media(preview_id)  # Existing integrity/finished-file guard.
            current['review_preview_id'] = preview_id
            try:
                current['direction_id'] = load(self.root/'data/command/STATE.json').get('production_direction')
            except FileNotFoundError:
                current['direction_id'] = None
            if previous:
                save(self.path.parent/'history'/(previous['updated_at'].replace(':', '-')+'.json'), previous)
            save(self.path, current)
            from team_memory import TeamMemory
            TeamMemory(self.root).production(current)
            return self.snapshot()

    def direction_received(self):
        """Keep the old evidence, but don't pass it off as the next task's plan."""
        with self.lock:
            if self.path.exists():
                current = load(self.path)
                current['pending_direction_at'] = stamp()
                current['updated_at'] = stamp()
                save(self.path, current)

    def accept(self, data):
        with self.lock:
            current = load(self.path)
            if data.get('revision') != current['revision'] or data.get('expected_updated_at') != current['updated_at']:
                raise ValueError('The review changed; reopen the current revision before acceptance')
            view = self.snapshot()['plan']
            if view.get('disposition') == 'manual_finish':
                raise ValueError('This revision was handed to Tony for manual finish. Register a new review before acceptance.')
            if any(s['status'] not in ('verified','awaiting_review') for s in view['steps'] if s['gate'] != 'human'):
                raise ValueError('Outstanding or changed checkpoints must be resolved before full acceptance')
            awaiting=[s for s in current['steps'] if s['status']=='awaiting_review']
            if awaiting:
                if not view.get('ready_for_review') or set(data.get('reviewed_checkpoints',[]))!={s['id'] for s in awaiting}:
                    raise ValueError('Explicitly confirm each final playback/listening review before acceptance')
                evidence=self.path.parent/'acceptances'/(uuid.uuid4().hex+'.json')
                save(evidence,{'revision':current['revision'],'preview_id':current['review_preview_id'],'reviewed_checkpoints':data['reviewed_checkpoints'],'human_confirmed_at':stamp()})
                data={**data,'evidence':str(evidence)}
                for row in awaiting:row.update(status='verified',method='listening' if row['gate']=='listening' else 'playback',blocker=None,note='Human explicitly confirmed this final review in Neural.',evidence=[self.evidence(evidence)])
            target = next((s for s in current['steps'] if s['gate'] == 'human'), None)
            if target is None:
                raise ValueError('This plan has no human acceptance checkpoint')
            target.update(status='verified', method='human_acceptance', note='Human accepted this exact revision in Neural.', evidence=[self.evidence(data['evidence'])])
            current.update(expected_updated_at=current['updated_at'])
            return self.update(current, human_action=True)

    def snapshot(self, local=None):
        with self.lock:
            try:
                plan = copy.deepcopy(load(self.path))
            except FileNotFoundError:
                plan = None
            if plan:
                for row in plan['steps']:
                    if row['status'] != 'verified':
                        continue
                    try:
                        if not all(self.evidence(e['path']) == e for e in row['evidence']):
                            raise ValueError('Evidence changed')
                    except (OSError, ValueError):
                        row.update(status='not_tested', invalidated=True, note='Checkpoint evidence changed or disappeared; recheck this revision.')
                plan['verified'] = sum(s['status'] == 'verified' for s in plan['steps'])
                plan['remaining'] = len(plan['steps'])-plan['verified']
                plan['ready_for_acceptance'] = all(s['status'] == 'verified' for s in plan['steps'] if s['gate'] != 'human')
                outstanding = [s for s in plan['steps'] if s['status'] not in ('verified','awaiting_review') and s['gate'] != 'human']
                plan['work_remaining'] = len(outstanding)
                plan['review_pending'] = sum(s['status']=='awaiting_review' or (s['gate']=='human' and s['status']!='verified') for s in plan['steps'])
                human_steps=[s for s in plan['steps'] if s['gate']=='human']
                plan['accepted']=bool(human_steps) and all(s['status']=='verified' for s in human_steps)
                try:
                    pause=load(self.root/'data/command/STATE.json').get('production_pause') or {}
                except (OSError,ValueError):pause={}
                plan['paused']=bool(pause.get('project_id')==plan['project_id'] and pause.get('revision')==plan['revision'])
                if plan['paused']:plan['pause_reason']=pause.get('reason')
                plan['ready_for_review'] = not outstanding and bool(plan.get('review_preview_id')) and not plan.get('pending_direction_at') and not plan['accepted']
                if plan['ready_for_review']:
                    try:
                        from previews import PreviewCatalog
                        PreviewCatalog(self.root).media(plan['review_preview_id'])
                    except (OSError,ValueError):
                        plan['ready_for_review']=False
                        plan['review_error']='Registered full review is missing or changed; verify delivery before review.'
                plan['estimate'] = None
                plan['estimate_note'] = 'Waiting for review; no model is running just to maintain this checklist.' if outstanding and all(s['status'] == 'not_tested' for s in outstanding) else 'No reliable whole-edit estimate yet; remaining work needs a current bounded estimate.'
                if outstanding and all(s.get('estimate') and s['status'] not in ('blocked', 'not_tested') for s in outstanding):
                    plan['estimate'] = {'low_minutes': sum(s['estimate']['low_minutes'] for s in outstanding), 'high_minutes': sum(s['estimate']['high_minutes'] for s in outstanding), 'basis': 'Director planning range for remaining sequential work; human response time excluded', 'as_of': plan['updated_at']}
                    if seconds(plan['updated_at']) is None or time.time()-seconds(plan['updated_at']) > 900:
                        plan['estimate'] = None
                        plan['estimate_note'] = 'Planning estimate is stale; awaiting the next actual checkpoint update.'
                if any(s['status'] == 'blocked' for s in outstanding):
                    plan['estimate_note'] = 'Blocked: an end-time estimate would be misleading until the failed checkpoint is resolved.'
                if plan['ready_for_review']:
                    plan['estimate_note'] = 'Production finished. Full review ready; final motion, listening and artistic checks await the human. These checks are not claimed as passed.'
                if plan['accepted']:plan['estimate_note']='This revision has been explicitly approved by the human.'
                if plan['paused']:
                    plan['estimate']=None
                    plan['estimate_note']='Paused by the human. Work and evidence are preserved; no automatic continuation is authorized.'
                if plan['paused'] and pause.get('disposition') == 'manual_finish':
                    plan['disposition'] = 'manual_finish'
                    plan['ready_for_review'] = plan['ready_for_acceptance'] = False
                    plan['estimate_note'] = pause['reason']
                elif plan.get('pending_direction_at'):
                    plan['needs_update'] = True
                    plan['estimate'] = None
                    plan['estimate_note'] = 'New direction received. This is the last recorded revision; the director must reconcile its checklist with the new scope.'
            local = local or {'active': [], 'jobs': []}
            return {'plan': plan, 'pipelines': [pipeline_view(j, local.get('jobs', [])) for j in local.get('active', [])],
                    'recent_pipeline': pipeline_view(local['jobs'][0], []) if local.get('jobs') else None,
                    'model_calls': 0, 'checked_at': stamp()}
