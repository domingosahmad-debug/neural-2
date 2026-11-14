"""Signal's command vocabulary: turn spoken requests into a short list of validated studio actions.

UI actions (open, focus, type, send, close, view) run in the window. Work actions (director messages and
robot assignments) run in the app server with the studio's normal checks. Nothing here calls a model.
"""
import re

# Robot / station vocabulary. Values: (robot id, station id, human name)
ROBOTS = {
    'pip': ('pip', 'media', 'Pip'), 'media': ('pip', 'media', 'Pip'), 'ingest': ('pip', 'media', 'Pip'), 'media lab': ('pip', 'media', 'Pip'),
    'nova': ('nova', 'analysis', 'Nova'), 'analysis': ('nova', 'analysis', 'Nova'), 'intelligence': ('nova', 'analysis', 'Nova'), 'reference': ('nova', 'analysis', 'Nova'),
    'scout': ('scout', 'story', 'Scout'), 'story': ('scout', 'story', 'Scout'),
    'echo': ('echo', 'sound-design', 'Echo'), 'sound': ('echo', 'sound-design', 'Echo'), 'audio': ('echo', 'sound-design', 'Echo'), 'sound board': ('echo', 'sound-design', 'Echo'), 'soundboard': ('echo', 'sound-design', 'Echo'), 'mixing board': ('echo', 'sound-design', 'Echo'),
    'sage': ('sage', 'review-delivery', 'Sage'), 'review': ('sage', 'review-delivery', 'Sage'), 'screening': ('sage', 'review-delivery', 'Sage'), 'delivery': ('sage', 'review-delivery', 'Sage'),
    'codex': ('codex', 'editing', 'Leader'), 'leader': ('codex', 'editing', 'Leader'), 'director': ('codex', 'editing', 'Leader'),
    'direction': ('codex', 'editing', 'Leader'), 'editing': ('codex', 'editing', 'Leader'), 'editor': ('codex', 'editing', 'Leader'),
}
PLACES = {
    'usage': ('open', 'usage'), 'usage observatory': ('open', 'usage'), 'observatory': ('open', 'usage'),
    'settings': ('open', 'settings'), 'archive': ('open', 'archive'), 'library': ('open', 'archive'), 'reference library': ('open', 'archive'),
    'ideas': ('open', 'ideas'), 'idea atelier': ('open', 'ideas'), 'atelier': ('open', 'ideas'),
    'team': ('open', 'team'), 'team channel': ('open', 'team'), 'chat room': ('open', 'team'), 'team memory': ('open', 'team'), 'common room': ('open','team'), 'bot chat': ('open','team'), 'crew chat': ('open','team'), 'local crew':('open','local-crew'), 'local workers':('open','local-crew'), 'local bots':('open','local-crew'), 'local activity':('open','local-crew'), 'activity':('open','local-crew'), 'lumen': ('open', 'lumen'), 'learner':('open','lumen'), 'learner bot':('open','lumen'), 'workflow': ('open', 'lumen'), 'workflow and lumen': ('open', 'lumen'),
    'overview': ('view', 'overview'), 'home': ('view', 'overview'), 'production': ('view', 'production'), 'production floor': ('view', 'production'),
    'campus': ('view', 'campus'), 'terrace': ('view', 'terrace'), 'outside': ('view', 'terrace'), 'tour': ('view', 'tour'), 'studio pass': ('view', 'tour'),
    'review screen': ('open', 'screening'), 'screening room': ('open', 'screening'), 'cinema': ('open', 'screening'),
}
UI_TYPES = {'open', 'focus', 'station', 'view', 'type', 'send', 'clear', 'close', 'play', 'pause', 'resume', 'mute', 'unmute', 'volume', 'seek', 'fullscreen', 'screen', 'select_review', 'capture_review', 'review_note'}
OPEN_TARGETS = {'director', 'usage', 'settings', 'archive', 'ideas', 'lumen', 'screening', 'team', 'local-crew'}
VIEWS = {'overview', 'production', 'director', 'campus', 'terrace', 'tour'}
FILLER = r'(?:please[, ]+|can you\s+|could you\s+|would you\s+|relay[, ]+|signal[, ]+|jarvis[, ]+|for now[, ]+|okay[, ]+|ok[, ]+|your task is to\s+|i (?:want|need) you to\s+|now\s+|and\s+|then\s+|also\s+)*'


def robot_for(name, agents=(), director=None):
    """Match a spoken robot, station or worker-profile name (for example "Argon") to a station."""
    n = re.sub(r"[’'`]s\b", '', str(name).lower()).strip(' .,!?')
    n = re.sub(r'\b(director|leader)s\b', r'\1', n)
    n = re.sub(r'^(the|a)\s+', '', n)
    n = re.sub(r'\s+(bot|robot|station|bay|desk|tab|room|lab|department|team)$', '', n).strip()
    if n in ROBOTS:
        return ROBOTS[n]
    d=director or {};provider=d.get('provider','');model=str(d.get('model') or '').lower()
    if (n in ('claude','claude opus','opus') and (provider=='claude' or model.startswith('claude')) and (n=='claude' or 'opus' in model)) or (n in ('sol','gpt','gpt sol') and provider=='codex'):
        return ROBOTS['director']
    for a in agents:
        first = str(a.get('name', '')).lower().split(' · ')[0].strip()
        if n and (n == first or n == str(a.get('id', '')).lower()):
            station = (a.get('stations') or [None])[0]
            for rid, sid, label in set(ROBOTS.values()):
                if sid == station:
                    return rid, sid, a.get('name', label).split(' · ')[0]
    return None


def split_steps(text):
    verbs = r'(?:type|write|send|submit|open|go|take|show|tell|ask|have|get|close|clear|focus|play|pause|resume|mute|unmute|set|turn|skip|rewind|seek|read|check|navigate|bring|switch|zoom|fly)'
    parts = re.split(r'\s*(?:,\s*)?(?:\band then\b|\bthen\b|;|\bafter that\b|\band\s+(?=' + verbs + r'\b))\s*', text.strip(), flags=re.I)
    return [p.strip(' .') for p in parts if p.strip(' .')]


def parse_step(step, agents=(), director=None):
    s = re.sub('^' + FILLER, '', step.strip(), flags=re.I).strip()
    low = s.lower()
    if re.fullmatch(r'(?:open|show(?: me)?|enter|go to|take me to|visit) (?:the )?(?:common room|team chat|bot chat|crew chat)',low):return {'type':'open','target':'team'}
    if re.fullmatch(r'(?:open|show(?: me)?|check|inspect|go to|take me to) (?:the )?(?:local (?:crew|bots|workers|activity)|activity banner)',low):return {'type':'open','target':'local-crew'}
    s=re.sub(r'\s*\.\s*this is your (?:fucking )?task\.?\s*$','',s,flags=re.I)
    # Navigation/forwarding context makes this a likely speech alias, never a global word replacement.
    if re.search(r'\b(?:chat|tab|tell|send)\b',s,re.I):s=re.sub(r'\bleaderboard\b','leader',s,flags=re.I)
    low=s.lower()
    lumen=re.fullmatch(r'(?:tell|ask|have|give|assign|let) (?:the )?(?:lumen|learner(?: bot)?|apprentice)(?: (?:to|this task)|[:,])?\s+(.+)',s,re.I)
    if lumen and re.search(r'\b(?:make|create|build|edit|assemble)\b',lumen[1],re.I) and re.search(r'\b(?:edit|video|amv|montage)\b',lumen[1],re.I):return {'type':'lumen_trial','brief':lumen[1][:8000]}
    if re.fullmatch(r"send (?:the )?(?:director|leader)(?:[’']s)? (?:tab|chat)",low):return {'type':'open','target':'director'}
    if re.fullmatch(r'(?:continue|resume|start) (?:working|editing|the edit|the current edit)(?: now| please| again)?[.!]?',low):return {'type':'director','text':s.strip(' .!')}
    capture = re.fullmatch(r'(?:take (?:a |another )?(?:screenshot|snapshot)(?: of (?:this|that|this part|the frame))?|screenshot(?: (?:this|that|this part|the frame|it))?|capture (?:this|that|the) (?:frame|part|moment))(?: and (?:add|attach|put) (?:it |this )?(?:to|in|into) (?:the )?(?:director|leader)(?:[’\']s)?(?: chat| draft| tab)?)?(?:\s*:\s*(.+))?[.!]?',s,re.I)
    if capture:return {'type':'capture_review','comment':(capture[1] or '').strip()[:1200]}
    note = re.fullmatch(r'(?:add (?:a )?(?:note|comment)|note|comment)\s*:\s*(.+)',s,re.I)
    if note:return {'type':'review_note','comment':note[1].strip()[:1200]}
    # Transport commands are explicit setters, never toggles. They need no model.
    media = r'(?:it|this|that|the (?:video|review|preview|edit|sound|audio)|video|review|preview|audio|sound)'
    if re.fullmatch(r'(?:unmute(?:\s+'+media+r')?|turn (?:the )?(?:sound|audio) (?:back )?on)', low):
        return {'type': 'unmute'}
    if re.fullmatch(r'(?:mute(?:\s+'+media+r')?|turn (?:the )?(?:sound|audio) off)', low):
        return {'type': 'mute'}
    if re.fullmatch(r'(?:pause|stop)(?:\s+'+media+r')?', low):
        return {'type': 'pause'}
    if re.fullmatch(r'(?:resume|continue playback|keep playing|play it|play that)', low):
        return {'type': 'resume'}
    if re.fullmatch(r'(?:play|open|show(?: me)?)\s+(?:(?:the|my)\s+)?(?:(?:latest|last|current|full)\s+)*(?:edit|video|review|preview)(?:\s+review)?', low):
        return {'type': 'play'}
    if re.fullmatch(r'(?:play|show|open)(?: me)? (?:the )?(?:latest |last )?(?:short )?proof', low):
        return {'type': 'select_review', 'kind': 'proof'}
    if re.fullmatch(r'(?:go|skip|seek|jump|rewind)(?: (?:it|the video))? to (?:the )?(?:start|beginning)', low):
        return {'type': 'seek', 'seconds': 0, 'relative': False}
    m = re.fullmatch(r'(?:go|skip|seek|jump)(?: (?:it|the video))? to (\d{1,3})(?::([0-5]\d))?(?:\s*(?:seconds?|s))?', low)
    if m:
        return {'type': 'seek', 'seconds': int(m[1])*60+int(m[2]) if m[2] else int(m[1]), 'relative': False}
    m = re.fullmatch(r'(?:skip|jump|go|rewind|seek)(?: (forward|back|backward|backwards))? (\d{1,3})\s*(?:seconds?|s)(?: (forward|back|backward|backwards))?', low)
    if m:
        direction = m[1] or m[3] or ('back' if low.startswith('rewind') else 'forward')
        return {'type': 'seek', 'seconds': int(m[2])*(-1 if direction.startswith('back') else 1), 'relative': True}
    m = re.fullmatch(r'(?:set |turn )?(?:the )?volume(?: to| at)? (\d{1,3})(?:\s*(?:%|percent))?', low)
    if m and int(m[1]) <= 100:
        return {'type': 'volume', 'value': int(m[1])/100}
    if re.fullmatch(r'(?:go |enter |make it |exit |leave )?full\s*screen', low):
        return {'type': 'fullscreen', 'enabled': not low.startswith(('exit', 'leave'))}
    if re.fullmatch(r'(?:play|show|move)(?: it| the (?:review|video|preview))? (?:on|at|to) (?:the )?(?:station|sky cinema|big screen)', low):
        return {'type': 'screen', 'target': 'station' if low.endswith('station') else 'cinema'}
    if re.fullmatch(r'(?:check|read|show|tell)(?: me)?(?: the| my| our| current| all| crew| model| account)*(?: usage| allowance| quotas?)(?: (?:for|of) (?:the )?(?:crew|models|accounts))?', low):
        return {'type': 'usage_report'}
    # Work: delegate to the director or a robot. Text after the colon/verb is kept verbatim.
    m = re.match(r"^(?:tell|ask|have|get|instruct|assign|send|message)\s+(?:the\s+)?(.+?)(?:\s*[:,]\s*|\s+(?:to|that)\s+)(.+)$", s, re.I)
    if m:
        who = robot_for(m.group(1), agents, director)
        if who:
            brief = m.group(2).strip()
            if who[0] == 'codex':
                return {'type': 'director', 'text': brief}
            return {'type': 'assign', 'robot': who[0], 'station': who[1], 'name': who[2], 'brief': brief}
    m = re.match(r'^(?:type|write|draft|put|enter)\s+(?:in\s+|out\s+)?(?:the\s+(?:message|text|words?)\s+)?["“]?(.+?)["”]?(?:\s+(?:in|into)\s+(?:the\s+)?(?:director|leader|chat|box|draft)\S*(?:\s+\w+)?)?$', s, re.I)
    if m:
        return {'type': 'type', 'text': m.group(1).strip()}
    if re.match(r'^(?:send|submit)\s*(?:it|that|this|the message|the draft|the direction|now)?$', low):
        return {'type': 'send'}
    if re.match(r'^(?:clear|delete|erase)\s+(?:it|that|the draft|the message|the text|everything)$', low):
        return {'type': 'clear'}
    if re.match(r'^(?:close|exit|hide|go back|back|dismiss)(?:\s+(?:it|this|that|everything|the (?:tab|panel|window|room)))?$', low):
        return {'type': 'close'}
    m = re.match(r"^(?:what(?:'s| is| are)|how(?:'s| is))\s+(?:the\s+)?(.+?)\s+(?:doing|working on|up to)\b", low)
    if m and robot_for(m.group(1), agents):
        who = robot_for(m.group(1), agents)
        return {'type': 'report', 'robot': who[0], 'station': who[1], 'name': who[2]}
    if re.search(r"what (?:did|has) (?:the )?(?:director|leader)\s+(?:say|said|reply|replied|answer)|read (?:me )?(?:the )?(?:director|leader)", low):
        return {'type': 'read_director'}
    m = re.match(r'^(?:open|show(?: me)?|go to|take me to|navigate to|bring up|pull up|switch to|enter|visit|look at|focus on|zoom (?:in )?(?:on|to)|fly to)\s+(?:the\s+)?(.+?)$', s, re.I)
    if m:
        target = m.group(1).strip(' .').lower()
        target = re.sub(r"[’'`]s\b", '', target)
        bare = re.sub(r'\s+(tab|panel|page|screen|view|room|section|window)$', '', target)
        if re.search(r'\b(directors?|leaders?|command)\b', bare) and not re.search(r'\b(bay|station|desk|bot|robot)\b', bare):
            return {'type': 'open', 'target': 'director'}
        if bare in PLACES:
            kind, value = PLACES[bare]
            return {'type': kind, 'target' if kind == 'open' else 'view': value}
        who = robot_for(bare, agents)
        if who:
            go_inside = re.search(r'\b(station|tab|room|lab|desk|workspace|tasks?)\b', target) or s.lower().startswith('open')
            return {'type': 'station' if go_inside else 'focus', 'robot': who[0], 'station': who[1], 'name': who[2]}
    return None


def parse(text, agents=(), last_robot=None, director=None):
    """All steps must be understood for a deterministic plan; otherwise the model interprets the request.
    Pronouns (him/her/them/it/this bot) refer to the robot named earlier in the request or the last turn."""
    text=re.sub('^'+FILLER,'',text.strip(),flags=re.I)
    # Sentence boundary after a navigation destination, not arbitrary sentences inside a brief.
    text=re.sub(r"((?:director|leader)(?:[’']s)?\s+(?:tab|chat))\.\s*(?=(?:send|tell|ask)\b)",r'\1; ',text,flags=re.I)
    steps = split_steps(text)
    if not steps or len(steps) > 6:
        return None
    actions = []
    for step in steps:
        if last_robot:
            step = re.sub(r'^((?:please\s+)?(?:tell|ask|have|get|instruct|assign|go to|open|show me|focus on)\s+)(?:him|her|them|it|this (?:bot|robot)|that (?:bot|robot))\b', lambda m: m.group(1) + last_robot, step, flags=re.I)
        a = parse_step(step, agents, director)
        actions.append(a)
        if a and a.get('robot'):
            last_robot = a['robot']
        elif a and a.get('type') == 'open' and a.get('target') == 'director':
            last_robot = 'director'

    if any(a is None for a in actions):
        return None
    return actions


def validate(actions, user_text, agents=()):
    """Bound and sanitise model-proposed actions. Work actions require an explicit request in the user's words."""
    out = []
    asked_work = re.search(r'\b(tell|ask|have|get|assign|instruct|send|give|start|run|delegate|let)\b', user_text, re.I)
    for a in (actions or [])[:6]:
        if not isinstance(a, dict):
            continue
        t = a.get('type')
        if t in ('open',) and a.get('target') in OPEN_TARGETS:
            out.append({'type': 'open', 'target': a['target']})
        elif t in ('capture_review','review_note') and isinstance(a.get('comment',''),str) and re.search(r'screenshot|snapshot|capture|\bnote\b|\bcomment\b',user_text,re.I):
            out.append({'type':t,'comment':a.get('comment','')[:1200]})
        elif t=='lumen_trial' and asked_work and re.search(r'\b(?:lumen|learner|apprentice)\b',user_text,re.I) and isinstance(a.get('brief'),str):
            out.append({'type':t,'brief':a['brief'][:8000]})
        elif t == 'view' and a.get('view') in VIEWS:
            out.append({'type': 'view', 'view': a['view']})
        elif t in ('focus', 'station', 'report'):
            who = robot_for(a.get('robot', ''), agents)
            if who:
                out.append({'type': t, 'robot': who[0], 'station': who[1], 'name': who[2]})
        elif t == 'type' and isinstance(a.get('text'), str) and a['text'].strip():
            out.append({'type': 'type', 'text': a['text'].strip()[:4000]})
        elif t in ('send', 'clear', 'close', 'play', 'pause', 'resume', 'mute', 'unmute', 'read_director', 'usage_report'):
            if t == 'send' and not asked_work:
                continue
            out.append({'type': t})
        elif t == 'volume' and type(a.get('value')) in (int, float) and 0 <= a['value'] <= 1:
            out.append({'type': t, 'value': a['value']})
        elif t == 'seek' and type(a.get('seconds')) in (int, float) and abs(a['seconds']) <= 36000 and type(a.get('relative')) is bool:
            out.append({'type': t, 'seconds': a['seconds'], 'relative': a['relative']})
        elif t == 'fullscreen' and type(a.get('enabled')) is bool:
            out.append({'type': t, 'enabled': a['enabled']})
        elif t == 'screen' and a.get('target') in ('station', 'cinema'):
            out.append({'type': t, 'target': a['target']})
        elif t == 'select_review' and a.get('kind') in ('full', 'proof'):
            out.append({'type': t, 'kind': a['kind']})
        elif t == 'director' and asked_work and isinstance(a.get('text'), str) and a['text'].strip():
            out.append({'type': 'director', 'text': a['text'].strip()[:4000]})
        elif t == 'assign' and asked_work and isinstance(a.get('brief'), str) and a['brief'].strip():
            who = robot_for(a.get('robot', ''), agents)
            if who and who[0] != 'codex':
                out.append({'type': 'assign', 'robot': who[0], 'station': who[1], 'name': who[2], 'brief': a['brief'].strip()[:4000]})
    return out


ACTION_GUIDE = '''You can operate the Neural app for the human. When the request needs it, reply with ONLY a JSON object:
{"say": "<one or two short spoken sentences>", "actions": [ ... ]}
Allowed actions (max 6, run in order):
{"type":"open","target":"director|usage|settings|archive|ideas|lumen|screening|team"}
{"type":"view","view":"overview|production|campus|terrace|tour"}
{"type":"focus","robot":"pip|nova|scout|echo|codex|sage"}   (fly the camera to that robot)
{"type":"station","robot":"pip|nova|scout|echo|sage"}        (open that robot's station workspace)
{"type":"type","text":"..."}      (write into the director's message box; does not send)
{"type":"send"}                   (send the director message box; only if the human asked to send)
{"type":"clear"} {"type":"close"} {"type":"play"} {"type":"pause"} {"type":"read_director"}
{"type":"resume"} {"type":"mute"} {"type":"unmute"} {"type":"usage_report"}
{"type":"volume","value":0.5} (0 to 1) {"type":"seek","seconds":10,"relative":true}
{"type":"fullscreen","enabled":true} {"type":"screen","target":"station|cinema"}
{"type":"select_review","kind":"full|proof"}
{"type":"capture_review","comment":"Tony's exact criticism, or empty"} (capture current review frame to background director DRAFT; never sends)
{"type":"review_note","comment":"Tony's exact follow-up criticism"} (add to last captured frame; never sends)
{"type":"lumen_trial","brief":"Tony's explicit editing trial brief"} (queue Lumen's separate tool-enabled worker, only on explicit request; existing production keeps ownership)
{"type":"report","robot":"..."}   (read that station's current job)
{"type":"director","text":"..."}  (send a message to the director; only if the human asked)
{"type":"assign","robot":"pip|nova|scout|echo|sage","brief":"..."}  (create and start a task for that robot; only if the human asked)
Robots: Pip=media lab, Nova=analysis, Scout=story, Echo=sound, Codex/Leader=director, Sage=review/screening.
If no app action is needed, answer in plain spoken sentences without JSON.'''
