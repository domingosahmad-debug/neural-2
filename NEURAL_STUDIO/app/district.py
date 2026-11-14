"""Local idea notebook and bounded, metadata-only project library. No inference."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import random
import threading
import uuid

def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

class DistrictStore:
    def __init__(self, root):
        self.root=Path(root).resolve();self.workspace=self.root.parent;self.lock=threading.RLock()
        self.notebook=self.root/'data'/'ideas.json';self.catalog={}
    def ideas(self):
        with self.lock:
            return json.loads(self.notebook.read_text(encoding='utf-8')) if self.notebook.exists() else []
    def suggest(self, data):
        kind=data.get('kind','video')
        if kind not in ['video','app']:raise ValueError('Choose video or app ideas')
        brief=data.get('brief','')
        if not isinstance(brief,str) or len(brief)>1500:raise ValueError('Idea direction is too long')
        themes={
          'video':[
            ('The quiet before the cut','Build an edit around a held breath, then release the action on one strong musical change.','A still portrait → a small gesture → a decisive action.','Find three original shots with different energy; measure the beat before assembling.'),
            ('One motion, three worlds','Carry one screen direction through three different locations, letting a matching gesture make the transition.','A hand reaches → a matching turn → a wide reveal.','Scout source actions and make a frame ledger; avoid borrowing an existing montage.'),
            ('A world made of words','Let one short line become physical typography inside the scene.','Dialogue fragment → one hero word → depth and occlusion.','Choose a complete line, transcribe it and test one editable type treatment.'),
            ('The detail that changes everything','Open on a tiny detail, then reveal why it matters through a short visual story.','Macro detail → cause → consequence → final portrait.','Build a four-shot storyboard and check every source offset.'),
            ('A rhythm you can see','Turn a musical motif into recurring visual shapes, with an intentional pause before the peak.','Shape match → cut pattern → silence → impact.','Measure the musical phrase and sketch a beat map before adding effects.'),
            ('A miniature documentary','Give an unexpected object or character a short editorial explanation using maps, labels and original footage.','A question → three visual clues → a clean answer.','Write a 25-second script and list the facts that need evidence.'),
            ('After the impact','Tell the story through aftermath, reflections and reactions before revealing the event.','Reaction → traces → anticipation → action reveal.','Choose nonrepeating reactions and verify the emotional order against the music.'),
            ('A moving poster','Make a short loop from one strong shot, three layers of depth and one expressive title.','Foreground drift → title reveal → gentle return.','Test clean framing, matte edges and a seamless 6–10 second loop.')],
          'app':[
            ('The evidence observatory','Make every creative decision traceable to a frame, measurement or note.','A station node expands into evidence and its downstream dependencies.','Prototype one linked evidence card using existing saved task data.'),
            ('A crew memory cabinet','Give each robot a cabinet of lessons from user feedback.','Open a keepsake → see the correction → attach it to the next brief.','Define a small, explicit feedback record; do not infer approval from old jobs.'),
            ('A living production wall','Let one wall display actual project progress as a visual sequence.','Sources → plan → assembly → review, with real blocked states.','Connect a single production to its persisted records before adding animation.'),
            ('A reference cinema','Compare a reference and a rough cut side by side with measured cut markers.','Choose clips → align offsets → inspect the beat differences.','Prototype a local viewer with explicit file selection and synchronized controls.'),
            ('A tiny daily commission','Offer one optional creative exercise from the idea atelier.','Collect a prompt → sketch a plan → save or dismiss.','Keep suggestions local; require an explicit Run action for any model work.'),
            ('The handoff railway','Show approved context moving between departments as linked task packets.','Inspect a carriage → read skills and evidence → choose the next worker.','Use actual upstream IDs and separate approval from dispatch.')]
        }
        with self.lock:
            rows=self.ideas();recent={r['title'] for r in rows[:12] if r['kind']==kind}
            pool=[x for x in themes[kind] if x[0] not in recent] or themes[kind]
            choices=random.sample(pool,min(3,len(pool)))
            if len(choices)<3:choices+=random.sample([x for x in themes[kind] if x not in choices],3-len(choices))
            created=[]
            for title,concept,sequence,next_step in choices:
                created.append({'id':uuid.uuid4().hex,'title':title,'concept':concept,'sequence':sequence,'next_step':next_step,
                  'kind':kind,'direction':brief.strip(),'status':'sketch','origin':'local creative prompts',
                  'created_at':datetime.now(timezone.utc).isoformat()})
            # Saved entries are never evicted by fresh sketches.
            saved=[r for r in rows if r['status']=='saved'];others=[r for r in rows if r['status']!='saved']
            _save(self.notebook,(created+saved+others)[:500]);return {'created':created,'ideas':self.ideas()}
    def update_idea(self,data):
        if data.get('status') not in ['saved','sketch','archived']:raise ValueError('Invalid idea status')
        with self.lock:
            rows=self.ideas();row=next((r for r in rows if r['id']==data.get('id')),None)
            if row is None:raise ValueError('Idea not found')
            if data['status']=='saved' and row['status']!='saved' and sum(r['status']=='saved' for r in rows)>=300:raise ValueError('Notebook has 300 saved ideas; archive one before saving more')
            row['status']=data['status'];_save(self.notebook,rows);return row
    def library(self):
        """Shallow curated discovery; no autosaves, media decoding or AE opening."""
        allowed={'.aep','.mp4','.mov'};found=[]
        bases=[self.workspace,self.root/'ad_2026-10-16',self.root/'vision_2026-10-16']
        # Original AE masters one folder below the workspace; no recursive crawl.
        skipped={'ae_bridge','Adobe After Effects Auto-Save','NEURAL_STUDIO','node_modules','.git','.codex'}
        try:bases.extend([p for p in sorted(self.workspace.iterdir()) if p.is_dir() and not p.name.startswith(('.','_')) and p.name not in skipped][:80])
        except OSError:pass
        seen=set()
        for base in bases:
            if not base.is_dir():continue
            try:files=[p for p in sorted(base.iterdir()) if p.suffix.lower() in allowed][:300]
            except OSError:continue
            for path in files:
                if path.suffix.lower() not in allowed or not path.is_file() or path.is_symlink():continue
                resolved=path.resolve()
                if not resolved.is_relative_to(self.workspace) or resolved in seen:continue
                # Nested directories contribute project files, not every source video.
                if base not in bases[:3] and path.suffix.lower()!='.aep':continue
                seen.add(resolved);stat=resolved.stat();key=hashlib.sha256(str(resolved).encode()).hexdigest()[:24]
                found.append({'id':key,'title':resolved.stem,'path':str(resolved),'kind':'project-file' if resolved.suffix.lower()=='.aep' else 'film','bytes':stat.st_size,'modified':datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat(),'note':'Local file reference · content and artistic quality not assessed'})
                if len(found)>=160:break
            if len(found)>=160:break
        with self.lock:self.catalog={r['id']:r for r in found}
        return sorted(found,key=lambda r:r['modified'],reverse=True)
    def item(self,key):
        self.library()
        with self.lock:row=self.catalog.get(key)
        if not row:raise ValueError('Library item not found')
        path=Path(row['path']).resolve()
        if not path.is_relative_to(self.workspace) or not path.is_file():raise ValueError('Library reference unavailable')
        return path
    def media(self,key):
        path=self.item(key)
        if path.suffix.lower() not in ['.mp4','.mov']:raise ValueError('Only library films can be previewed')
        return path
    def reveal(self,key):
        path=self.item(key)
        if os.name!='nt':raise ValueError('Folder reveal is available on Windows')
        os.startfile(path.parent);return {'opened':str(path.parent)}
