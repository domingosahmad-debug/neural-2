"""Only consume official CLI rate-limit events; never inspect credentials or probe a model."""
import math
import threading
from pathlib import Path
from operations import load, save, stamp
LOCK=threading.RLock()

def windows(raw):
    info=raw.get('rate_limit_info') or {}
    kind=info.get('rateLimitType')
    if kind not in ('five_hour','seven_day','seven_day_opus','seven_day_sonnet'):return []
    used=info.get('utilization')
    # SDK utilization is a fraction; absence/status alone does not imply 0/100.
    valid=isinstance(used,(int,float)) and not isinstance(used,bool) and math.isfinite(used) and 0<=used<=1
    return [{'name':kind.replace('_',' '),'limit_id':kind,'remaining_percent':round(100*(1-used),3) if valid else None,
             'window_minutes':300 if kind=='five_hour' else 10080,'reset_at':info.get('resetsAt'),
             'provider_status':info.get('status'),'scope':'native Claude subscription'}]

def record(root,event):
    rows=event.get('quota_windows')
    if not rows:return
    p=Path(root)/'data/command/CLAUDE_QUOTA.json'
    with LOCK:
        try:prior=load(p)
        except (OSError,ValueError):prior={'windows':[]}
        merged={r['limit_id']:r for r in prior.get('windows',[])}
        for row in rows:merged[row['limit_id']]=row
        save(p,{'status':'reported','checked_at':stamp(),'windows':list(merged.values()),'source':'official Claude Code stream rate_limit_event','detail':'Provider-reported native account limits. Missing utilization remains unknown. Readings are dated; no quota probe/model turn was started.'})

def snapshot(root):
    try:return load(Path(root)/'data/command/CLAUDE_QUOTA.json')
    except (OSError,ValueError):return {'status':'not_exposed','windows':[],'detail':'Native Claude is connected. This CLI session has not supplied subscription utilization. Call tokens are shown separately; remaining percent is unknown.'}
