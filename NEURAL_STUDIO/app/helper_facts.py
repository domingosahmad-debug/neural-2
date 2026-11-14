"""Relay's bounded, read-only studio evidence. No inference or work dispatch."""
import re
from operations import load, stamp
from team_memory import TeamMemory

IDENTITY={'name':'Relay','human_name':'Tony','aliases':['Relay','Jarvis','Signal']}

def read(root,relative):
    try:return load(root/relative)
    except (OSError,ValueError):return None

def collect(runtime):
    root=runtime.root
    learner=read(root,'data/workflow-apprentice/STATE.json') or {}
    ledger=read(root,'data/workflow-apprentice/MISTAKE_LEDGER.json')
    rows=ledger.get('entries',[]) if isinstance(ledger,dict) else None
    if not isinstance(rows,list):rows=None
    plan=read(root,'data/production/CURRENT.json') or {}
    command=runtime.command.snapshot()
    steps=plan.get('steps',[])
    # Read local contract + recorded configuration, never ask a model to describe itself.
    editor=getattr(runtime,'lumen_editor',None)
    trial_state=editor.snapshot() if editor else {}
    trial={'installed':bool(editor),'status':trial_state.get('status','not loaded'),'adapter_supported':trial_state.get('adapter_supported',False)}
    evidence={'checked_at':stamp(),'identity':IDENTITY,'model_calls_for_inspection':0,'lumen_trial_editor':trial,
      'learner':{'name':'Lumen','provider':learner.get('provider'),'model':learner.get('model'),
        'status':learner.get('status','not reported'),'activity':str(learner.get('activity',''))[:350],
        'accepted_lessons':len(rows) if rows is not None else None,
        'categories':sorted({str(r.get('category','uncategorized')) for r in rows if isinstance(r,dict)})[:16] if rows is not None else [],
        'last_learned_at':learner.get('last_learned_at'),
        'current_role':'Observe and learn; separately assignable trial editor' if trial['installed'] else 'Observe completed evidence and distill saved corrections; not an autonomous editing executor',
        'can_reflect_and_summarize':True,'native_editor':trial['installed'] and trial['adapter_supported'],'audio_listening':False,'full_speed_playback':False,
        'lessons_are':'Retrieved instructions, not trained model weights or proven complete editing ability',
        'sources':['data/workflow-apprentice/STATE.json','data/workflow-apprentice/MISTAKE_LEDGER.json','app/apprentice_service.py','app/staffing.py']},
      'production':{'project_id':plan.get('project_id'),'title':plan.get('title'),'revision':plan.get('revision'),
        'paused':bool((command.get('production_pause') or {}).get('project_id')==plan.get('project_id') and plan.get('project_id')),
        'verified':sum(s.get('status')=='verified' for s in steps),'total':len(steps),
        'remaining':[{'title':s.get('title'),'status':s.get('status'),'gate':s.get('gate')} for s in steps if s.get('status')!='verified'][:12],
        'review_preview_id':plan.get('review_preview_id'),'sources':['data/production/CURRENT.json','data/command/STATE.json']},
      'team':TeamMemory(root).director_brief(),
      'limits':['Ordinary Claude/Gemini/OpenCode station adapters receive text, Codex specialist can also receive still images.',
        'No configured ordinary station adapter provides audio listening or full-speed video perception.',
        'One authorized director owns TonyFX native edits. Capability differs from learned rules.',
        'A saved preview or technical PASS does not establish final artistic acceptance.']}
    return evidence

def direct_answer(text,facts,context=None):
    """High-value factual questions bypass tiny-model guessing and hosted allowance."""
    low=text.lower();l=facts['learner'];p=facts['production']
    if re.fullmatch(r'(?:hey |hi |hello )?(?:relay|jarvis|signal)[,.!? ]*',low) or re.search(r'\b(your name|who are you|my name|what.*call you)\b',low):
        return 'Tony, I’m Relay, your studio assistant. You can call me Relay; your microphone stays off until you enable it.', ['data/helper/STATE.json']
    context=context or {}
    learner=context.get('learner') or bool(re.search(r'\b(lumen|learner|apprentice|learning bot)\b',low))
    capability=bool(re.search(r'\b(can|could|capable|capabilit\w*|able|ready|enough|independent\w*|autonom\w*|zero|hundred|100|0|limit\w*)\b',low))
    if context.get('unclear_transcription'):
        return ('Tony, did you mean whether Lumen could eventually create a complete edit on its own? I heard “be home,” so I need to check that wording.',l['sources'])
    if context.get('capability') and facts.get('lumen_trial_editor',{}).get('installed'):
        if not facts['lumen_trial_editor'].get('adapter_supported'):
            return ('Tony, Lumen’s trial-editor tools are installed, but its configured provider/model does not match the supported Antigravity Gemini Flash editing adapter. It can keep learning; select that supported model before assigning an editing trial. No substitute model was launched.',l['sources']+['shared/LUMEN_EDITOR_ROLE.md'])
        return ('Yes, Tony. Lumen can be assigned a complete trial edit in its separate editing role, with file/shell tools, the shared workflow, persistent session memory and the exclusive TonyFX lane. Assign it from its panel or ask me to give Lumen an edit. It still needs final human review; adding lessons does not prove its quality or retrain Gemini.',l['sources']+['shared/LUMEN_EDITOR_ROLE.md'])
    if context.get('capability') and context.get('future'):
        return ('Potentially, Tony. More lessons alone will not turn Lumen into an editor: it would need a capable execution role, the editing tools, suitable media-review support and tested quality checks. Today it is a learning/reflection bot; its future ability has not been demonstrated.',l['sources'])
    if context.get('capability'):
        count=f"{l['accepted_lessons']} accepted lessons" if l['accepted_lessons'] is not None else 'an unavailable lesson count'
        return (f"No, Tony. Lumen cannot independently finish a complete edit in its current learning role. I checked its configuration and ledger ({count}); it saves corrections, with no native editing, listening or full-speed playback tools. It can assist a capable editing worker through those shared lessons.",l['sources'])
    if learner and re.search(r'what.*\b(?:can|capabilities|able)\b',low):
        if facts.get('lumen_trial_editor',{}).get('installed'):
            return ('Tony, Lumen observes completed work, saves sourced corrections and summarizes lessons. Its separate trial-editor role can attempt a new complete edit using original assets, tools and saved memory with the supported Gemini Flash adapter. Active trials use model allowance; listening, full-speed perception and final artistic approval remain unverified.',l['sources']+['shared/LUMEN_EDITOR_ROLE.md'])
        return ('Tony, Lumen can summarize completed studio evidence and save reusable corrections. Its current learning role has no native editing, audio-listening or full-speed playback tools. Ask about a specific operation and I can compare it with that role.',l['sources'])
    if learner and re.search(r'\b(status|doing|model|active|where|working|which|who)\b',low):
        trial=facts.get('lumen_trial_editor',{})
        if trial.get('installed'):
            return (f"Tony, Lumen’s learning status is {l['status']}, using {l['model'] or 'an unreported model'}. Its separate editing role is {trial['status']}. {l['activity']} Reading this status starts no model turn; saved lessons are not proof of editing quality.",l['sources']+['shared/LUMEN_EDITOR_ROLE.md'])
        return (f"Tony, Lumen’s recorded status is {l['status']}, using {l['model'] or 'an unreported model'}. {l['activity']} Its job is to save evidence-based corrections; observation alone does not start a model turn. This reading does not prove it can execute an edit.",l['sources'])
    if re.search(r'\b(edit|task|project|production)\b',low) and re.search(r'\b(done|finished|progress|remaining|left|paused|stopped|status)\b',low) and (not context or context.get('status_question')):
        return (f"Tony, the current revision is {p['revision'] or 'not reported'}: {p['verified']} of {p['total']} checkpoints verified. "+('It is paused by your instruction; it has not resumed. ' if p['paused'] else '')+('Unfinished checks remain; a saved review is not final approval.' if p['verified']<p['total'] else 'Check the final human acceptance record before treating it as approved.'),p['sources'])
    if re.search(r'\b(team|bots|agents|collective)\b',low) and re.search(r'communicat|talk|help|shar|stuck',low):
        return ('Tony, the Team channel shows attributed messages, help requests and replies linked to real tasks. A stuck worker should report the exact failure and partial evidence; the director can assign a scoped consultation or replacement. Reading messages uses no model calls. A new model response uses that model’s allowance; there is no automatic background conversation.', ['shared/TEAMWORK_PROTOCOL.md'])
    return None
