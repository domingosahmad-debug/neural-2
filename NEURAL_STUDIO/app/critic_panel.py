"""Deterministic critic-panel aggregator (B3). No model call, no vote that approves.

Input: the structured reports of at most two fresh critics at one checkpoint (and the one changed-blocker recheck).
Output: one compact report for the director. Absence of findings is never approval; a missing/NOT RUN critic or a
hash mismatch makes the panel incomplete.

BF4 (7 Nov 2026): any critic reporting `changes_requested` makes the panel `changes_requested`; a timed-out, malformed
or missing critic is NOT RUN, never clean.
BF5: a slot that was not rechecked keeps its prior hash and is reported as "prior hash, director decides", not NOT RUN.
"""
import hashlib
import json
import re
from pathlib import Path

SEVERITY = {'blocker': 0, 'major': 1, 'minor': 2}
MAX_CRITICS = 2
PRIOR_HASH = 'prior hash, director decides'
DEAD_JOB_STATES = ('TIMED_OUT', 'FAILED', 'CANCELLED', 'UNKNOWN', 'INTERRUPTED', 'BLOCKED', 'INVALID_OUTPUT', 'NOT RUN')


def _key(f):
    text = re.sub(r'\W+', ' ', (str(f.get('source', '')) + ' ' + str(f.get('evidence', ''))).lower()).strip()
    return hashlib.sha256(text[:240].encode()).hexdigest()[:16]


def _well_formed(rep):
    """Malformed critic output is NOT RUN. Uses the same validator the reviewer run applies."""
    try:
        from fresh_review import validate_report
        validate_report(rep)
        return True
    except Exception:
        return False


def aggregate(entries, target_sha256):
    """entries: [{'critic':1|2,'agent_id','provider','model','status':'REPORTED'|'NOT RUN'|'TIMED_OUT'..., 'target_sha256','report':dict|None,
    'job_id', optional 'prior_hash': True when this slot legitimately keeps the hash of an earlier round}]"""
    entries = sorted(entries, key=lambda e: e.get('critic') or 0)[:MAX_CRITICS]
    not_run, prior, merged, missing, untested, critics = [], [], {}, set(), set(), []
    for e in entries:
        rep = e.get('report')
        row = {k: e.get(k) for k in ('critic', 'agent_id', 'provider', 'model', 'job_id', 'status')}
        row['target_sha256'] = e.get('target_sha256')
        if e.get('status') in DEAD_JOB_STATES:
            row['status'] = 'NOT RUN'; row['reason'] = 'critic job ended as ' + str(e.get('status')); rep = None
        elif e.get('target_sha256') != target_sha256 and not e.get('prior_hash'):
            row['status'] = 'NOT RUN'; row['reason'] = 'critic reviewed a different target hash'; rep = None
        elif rep and not _well_formed(rep):
            row['status'] = 'NOT RUN'; row['reason'] = 'malformed critic report'; rep = None
        if not rep:
            row.setdefault('reason', 'no report')
            row['status'] = 'NOT RUN'
            not_run.append(row['critic']); critics.append(row); continue
        if e.get('target_sha256') != target_sha256:
            row['status'] = PRIOR_HASH; prior.append(row['critic'])
        row['disposition'] = rep['disposition']; critics.append(row)
        missing.update(rep.get('missing_evidence', [])); untested.update(rep.get('not_tested', []))
        for f in rep.get('findings', []):
            m = merged.setdefault(_key(f), {'severity': f['severity'], 'source': f['source'], 'evidence': f['evidence'][:400],
                                            'consequence': f['consequence'][:300], 'correction': f['correction'][:300],
                                            'verification': f['verification'][:200], 'raised_by': [], 'ids': []})
            if SEVERITY[f['severity']] < SEVERITY[m['severity']]: m['severity'] = f['severity']
            m['raised_by'].append(e['critic']); m['ids'].append('c%s:%s' % (e['critic'], f['id']))
    present = {e.get('critic') for e in entries}
    for slot in range(1, MAX_CRITICS + 1):
        if slot not in present:  # a critic that was never run is reported NOT RUN, not silently absent
            not_run.append(slot)
    findings = sorted(merged.values(), key=lambda m: (SEVERITY[m['severity']], -len(m['raised_by']), m['source']))
    for m in findings:
        m['agreement'] = 'both' if len(set(m['raised_by'])) > 1 else 'single_critic'
    if any(m['severity'] in ('blocker', 'major') for m in findings) or any(c.get('disposition') == 'changes_requested' for c in critics):
        disposition = 'changes_requested'
    elif not_run or len(entries) < MAX_CRITICS or missing or any(c.get('disposition') == 'incomplete' for c in critics):
        disposition = 'incomplete'
    else:
        disposition = 'no_supported_blocker_found'
    return {'version': 1, 'target_sha256': target_sha256, 'panel_size': len(entries), 'critics': critics, 'not_run': not_run,
            'prior_hash_slots': prior, 'disposition': disposition, 'findings': findings, 'missing_evidence': sorted(missing), 'not_tested': sorted(untested),
            'approval': 'never', 'note': 'Panel output is evidence for the director. No finding is not approval; human motion/listening/artistic review is separate.'
            + (' Slots ' + ', '.join(str(p) for p in prior) + ' were not rechecked and keep their ' + PRIOR_HASH + '.' if prior else '')}


def collect(runtime, project_id, revision, checkpoint_id):
    jobs = [j for j in runtime.jobs() if j.get('context_mode') == 'fresh_review' and j.get('project_id') == project_id
            and j.get('project_revision') == revision and j.get('review', {}).get('checkpoint_id') == checkpoint_id and j.get('review', {}).get('critic')]
    if not jobs: raise ValueError('No panel reviews at this checkpoint')
    # The recheck (if any) supersedes its original for the same critic slot; the panel target hash is the newest one.
    by_slot = {}
    for j in sorted(jobs, key=lambda j: j.get('created_at', '')):
        by_slot[j['review']['critic']] = j
    latest = max(jobs, key=lambda j: j.get('created_at', ''))['review']['target_sha256']
    rechecked_chain = any(j['review'].get('recheck_of') for j in jobs)
    entries = []
    for slot, j in by_slot.items():
        path = runtime.job_folder(j['id']) / 'REVIEW_REPORT.json'
        try: report = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): report = None
        dead = j.get('status') in DEAD_JOB_STATES
        own = j['review']['target_sha256']
        entries.append({'critic': slot, 'agent_id': j.get('agent_id'), 'provider': j.get('provider'), 'model': j.get('model'),
                        'job_id': j['id'], 'status': j['status'] if dead else 'REPORTED' if report else 'NOT RUN', 'target_sha256': own, 'report': None if dead else report,
                        'prior_hash': bool(rechecked_chain and own != latest)})
    return aggregate(entries, latest)


def write_panel(runtime, project_id, revision, checkpoint_id):
    out = collect(runtime, project_id, revision, checkpoint_id)
    from operations import save
    path = Path(runtime.root) / 'data/critic-panels' / (re.sub(r'[^A-Za-z0-9_.-]', '_', project_id + '-' + checkpoint_id) + '.json')
    save(path, out)
    return path
