"""Small conversational context for Relay. Intent boundaries, not a second model call."""
import re

LEARNER=r'\b(?:lumen|learner|apprentice|learning bot)\b'
CAPABILITY=r'\b(?:can|could|able|capable|capabilit\w*|enough|independent\w*|autonom\w*|0|100|zero|hundred)\b'
FUTURE=r'\b(?:one day|someday|eventually|future|after learning|learns? more|learning more|more capable|more lessons)\b'

def context(text,history=(),last_topic=None):
    low=text.lower();previous=[m.get('text','') for m in history if m.get('role')=='user' and m.get('text')!=text][-10:]
    recent_learner=False
    for value in reversed(previous):
        if re.search(LEARNER,value,re.I):recent_learner=True;break
        if re.search(r'\b(?:director|leader|claude|nova|echo|scout|pip|sage)\b',value,re.I):break
    reference=bool(re.search(LEARNER,low)) or (recent_learner and bool(re.search(r'\b(?:it|he|this bot|that bot|on its own)\b',low)))
    if last_topic=='lessons' and re.search(r'\b(?:it|he)\b',low):reference=True
    future=bool(re.search(FUTURE,low));cap=bool(re.search(CAPABILITY,low))
    correction=bool(re.search(r'not what i (?:asked|mean)|that.s not (?:my question|what i asked)',low))
    # A complaint about the answer to a QUESTION may recover that question. Never replay an action.
    if correction and not (reference and cap):
        prior=next((v for v in reversed(previous) if re.search(LEARNER,v,re.I) or (recent_learner and re.search(r'\b(?:it|he)\b',v,re.I))),None)
        if prior and re.search(CAPABILITY+'|'+FUTURE,prior,re.I):
            reference=True;future=bool(re.search(FUTURE,prior,re.I));cap=True
    edit_operation=bool(re.search(r'\b(?:edit|video|editing|whole workflow|complete workflow)\b',low))
    inherited_edit=recent_learner and any(re.search(r'\b(?:edit|video|editing)\b',v,re.I) for v in previous[-4:])
    capability=reference and (cap or future) and (edit_operation or (inherited_edit and (future or correction)))
    # Explicit date ellipses ONLY. "One day" in a future question is never a lesson date.
    period=bool(re.fullmatch(r'(?:and |what about |for )?(?:yesterday|today|(?:the )?(?:past|last) (?:two|three|few|\d+) days?|(?:the )?last \d+ hours?)[?.! ]*',low))
    lessons=(not capability and bool(re.search(r'\b(?:what|summari[sz]e|list|show|tell|explain)\b.*\b(?:learned|learnt|lessons|corrections|learn)\b',low))) or (last_topic=='lessons' and period)
    status=bool(re.match(r'^(?:(?:relay|signal|jarvis)[, ]+)?(?:is|are|has|have|what|how|did|when)\b',low) and re.search(r'\b(?:status|progress|finished|working|stopped|running|done|remaining)\b',low)) or low.strip(' .?!') in ('status','progress')
    return {'learner':reference,'capability':capability,'future':future,'lessons':lessons,'status_question':status,
            'unclear_transcription':reference and future and bool(re.search(r'\bbe home\b',low))}
