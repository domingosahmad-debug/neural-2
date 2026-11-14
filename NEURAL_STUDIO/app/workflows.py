"""Local, provider-independent workflow profiles; assignments freeze their instructions."""
from pathlib import Path
import hashlib
import json
import re


class WorkflowProfiles:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.folder = self.root / 'workflows'
        self.selection = self.root / 'data/workflow-selection.json'

    def profile(self, name):
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', str(name)):
            raise ValueError('Invalid workflow name')
        path = self.folder / name / 'PROFILE.json'
        if not path.is_file():
            if name == 'tuf':
                return {'id': 'tuf', 'name': 'TUF editing workflow', 'instructions': 'Follow shared/CURRENT_RULES.md, the station handoff and relevant knowledge/skills. Current human corrections override historical recipes.', 'stations': {}}
            raise ValueError('Workflow not found')
        data = json.loads(path.read_text(encoding='utf-8'))
        return {**data, 'id': name}

    def snapshot(self, station=None):
        try:
            selected = json.loads(self.selection.read_text(encoding='utf-8'))['active']
        except (OSError, ValueError, KeyError):
            selected = 'tuf'
        profile = self.profile(selected)
        text = ('WORKFLOW PROFILE: ' + profile['id'] + '\n' + profile.get('instructions', '') +
                '\nSTATION INSTRUCTIONS:\n' + profile.get('stations', {}).get(station, 'Use the assigned station contract.'))
        if selected != 'tuf':
            text += '\nThis custom workflow replaces TUF artistic recipes and learned creative preferences. Shared lifecycle, truthful evidence, source preservation, tool capability and explicit native authorization rules still apply. Treat TUF examples as optional references only. Learn new corrections with this workflow id; do not import TUF creative lessons into this workflow.'
        return {'id': selected, 'name': profile.get('name', selected), 'instructions': text,
                'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}

    def list(self):
        names = {'tuf'}
        if self.folder.is_dir():
            names.update(p.parent.name for p in self.folder.glob('*/PROFILE.json'))
        return {'active': self.snapshot()['id'], 'profiles': [self.profile(n) for n in sorted(names)]}

    def learned_context(self, profile_id=None):
        """Bounded current rules, never another workflow's creative memory."""
        selected=profile_id or self.snapshot()['id']
        try:entries=json.loads((self.root/'data/workflow-apprentice/MISTAKE_LEDGER.json').read_text(encoding='utf-8'))['entries']
        except (OSError,ValueError,KeyError):return ''
        relevant=[e for e in entries if e.get('workflow_id','tuf')==selected]
        return 'WORKFLOW-SCOPED CORRECTIONS ('+selected+'); full scoped ledger remains in data/workflow-apprentice/MISTAKE_LEDGER.json:\n'+json.dumps(relevant[-12:],ensure_ascii=False)

    def save_custom(self, data):
        name = data.get('id', '')
        if name == 'tuf' or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', str(name)):
            raise ValueError('Choose a custom id; the TUF profile is preserved')
        instructions = data.get('instructions', '')
        stations = data.get('stations', {})
        valid = {'media','analysis','story','sound-design','editing','review-delivery'}
        if not isinstance(instructions, str) or not instructions.strip() or len(instructions) > 16000:
            raise ValueError('Enter workflow instructions (1–16000 characters)')
        if not isinstance(stations, dict) or set(stations) - valid or any(not isinstance(v,str) or len(v)>8000 for v in stations.values()):
            raise ValueError('Invalid station instructions')
        value = {'id': name, 'name': str(data.get('name',name))[:100], 'instructions': instructions, 'stations': stations}
        if len(json.dumps(value)) > 64000:raise ValueError('Workflow is too large')
        from operations import save
        save(self.folder/name/'PROFILE.json',value)
        return value

    def activate(self, name):
        self.profile(name)
        from operations import save
        save(self.selection, {'active': name})
        return self.list()
