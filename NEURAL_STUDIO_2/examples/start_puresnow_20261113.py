"""One persisted new-project admission; never replays an existing run or job."""
import json,sys
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/puresnow-20261113';OUT.mkdir(exist_ok=True)
base=json.loads((ROOT/'.desktop-service.json').read_text())['url']
with urlopen(base+'api/workspace',timeout=10) as r: workspace=json.load(r)
def post(route,body):
    req=Request(base+'api/'+route,json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Neural-Token':workspace['token']})
    with urlopen(req,timeout=30) as r:return json.load(r)['result']
def save(name,value): (OUT/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
brief='''TONY NEW AUTHORIZATION 13 November 2026: Build a NEW Dexter Pure Snow edit entirely through Neural2 production stations/tools, in a brand-new lightweight AE project; preserve all current/accepted/paused projects. The old readiness wait is superseded by this brief. Save a verified preservation copy of the currently open AE work before closing it through guarded ae_bootstrap; never overwrite it. Import only selected new source ranges/assets, not the heavy existing project.

INTRO EPISODE: C:/Users/TUF/Desktop/dexter.resurrection.s02e02.1080p.web.h264-cakes[EZTVx.to].mkv
BODY SOURCES: C:/Users/TUF/Desktop/DEXTER - RES/dexter old seasons (four scene packs; inspect source manifest).
SONG AND REFERENCES: C:/Users/TUF/Desktop/new pure snow edit and reference. Clean song PureSnow - I'm Never Looking Back.mp3; two ssstik.io MP4s. Measure BOTH references' exact clean-song offsets/speed/first body cut and pacing. Same part of song MUST be playing when the edit starts its body, matching their musical cut accents. Do not choose a filename/BPM guess or substitute the older PureSnow edit's clock. If refs differ, choose the coherent measured common hook and document which reference anchors it. Duration follows the measured song phrase and selected intro, not an arbitrary30-second default. Make the intro cold, authentic, complete and Dexter-centered, from the supplied episode. Other speakers allowed in intro; Dexter must be present or its story revolve around him. No invented quote or truncated phrase. Add a retention hook around firstsecond, motivated black/white flashback or camera-style insert with digital-camera/shutter SFX, like the accepted uploads, then meaningful short flashbacks attached to quote words. Sound effect must have a real source/provenance or be explicitly synthesized non-voice, not imaginary evidence.

Use the THREE accepted uploads as stylistic authority: knowledge/accepted-uploads-20261112.md and selected native trees JSON; preserve established accepted workflow too. Reuse measured methods, not completed shots/timelines. Do NOT copy typography from the two song references. Our own flawless editable kinetic typography: native letter/word reveals aligned to actual word clocks, readable holds/exits, contextual balanced placement, separate bloom; impactful payoff words such as BUTCHER need a deliberately oversized display face, bold effects and authored animation, still readable and face-safe. Do not use uniform sentence fades, evenly guessed word clocks, generic alternating zooms or clipped overshoot. Verify installed fonts and actual readback. Visible profanity must be censored consistently, including intermediate reveals; apply established posting censorship policy. Original transcript remains exact. Prefer censoring explicit spoken intro profanity with a short designed mute/bleep preserving complete surrounding words; document exact audio interval rather than truncating the phrase.

MUSIC BODY: ONLY Dexter shots, centered deliberately through entry/movement/zoom extrema/exit. Best strong expressive/moving moments, e.g. deliberate hoodie walk, kill-room preparation, controlled cool movement/looks. No running, passive sitting/doing nothing, weak static filler, generic random inserts, talking mouths without motivated audio or repeated scene families. Enough real motion/source handles for isolated Twixtor smooth150→35→150 where suitable; reject warped faces/hands, freezes or source-cut crossing. Separate retime owner, shot-specific Sapphire Z Dist adjustment and cut-local directional blur, source MotionTile coverage. New footage decisions. Accurate one continuous clean-song source clock, duck under authentic intro then rise on matched body entrance; separate editable dialogue/music/SFX. Prepare/verify clean dialogue without episode-score leakage using installed capability, never fabricate a separation result.

Target accepted1080square at24000/1001 unless actual source/reference evidence justifies a documented adaptation; original packFPS retained for retiming. Master and full playable review, editable lightweight AEP with media links. No paid APIs/billing/provider reset, no original Neural restart, no CA02/closedQuinn resumption.

CREW: supervising Codex is director. Hydrogen High is primary scoped production worker, Sol medium and Flash High bounded fallbacks. Terra medium harsh reviewer; distinct Flash High fresh Goldfish/EGM reviewer and plan reviewer. Mandatory consequential plan review plus representative difficult typography/motion proof before propagation, complete technical/render review and final human gate. Actual pixels via read_artifact, no pretending text-only checks are listening/playback. Independent reviewers cannot copy verdicts. Diagnose/repair actual failed regions without endless review loops. Use deterministic media/native completion events, return waiting with exact waitMedia/waitNative then stop inference. No UNKNOWN replay or second native writer. Handle recoverable technical issues yourself; ask human only genuinely missing creative inputs. The exact original user brief is recorded in project intake.

FIRST PLAN TASK: Read project intake/source-manifest.json and preparation-job.json under projectRoot. Reuse or await that exact prep job; do not duplicate it. Read all three accepted-upload summary mappings, especially current bold typography, and installed applicable skills. Scout references and the supplied episode/scene packs using Neural media tools and existing source/transcript caches where hash-matching, never infer identity from filename alone. Build a revision-bound frame-native source/quote/music/type/ending blueprint with exact sources/clocks and bounded supporting artifacts. Unmeasured requirements remain explicit, not fabricated. Source paths are read-only; artifact outputs stay in this NEW project. Return plan complete only with evidence sufficient for independent plan critique, not a speculative storyboard.'''
if len(brief)>12000:raise ValueError(len(brief))
if (OUT/'project.json').exists():raise SystemExit('Existing intake found; inspect it instead of creating another project.')
p=post('workspace',{'action':'project','name':'Dexter · Pure Snow · fresh AE · 13 Nov','brief':brief})
save('project.json',p);pid=p['id'];project=ROOT/'data/projects'/pid;project.mkdir(parents=True,exist_ok=True)
songfolder=Path('C:/Users/TUF/Desktop/new pure snow edit and reference')
packs=Path('C:/Users/TUF/Desktop/DEXTER - RES/dexter old seasons')
refs=sorted(songfolder.glob('*.mp4'));song=next(songfolder.glob('*.mp3'))
episode=Path('C:/Users/TUF/Desktop/dexter.resurrection.s02e02.1080p.web.h264-cakes[EZTVx.to].mkv')
inputs=[episode,song,*refs,*sorted(packs.glob('*.mp4'))]
manifest={'project':pid,'revision':1,'files':[{'path':str(x),'bytes':x.stat().st_size} for x in inputs],'accepted_reference':str(ROOT/'knowledge/accepted-uploads-20261112.md')}
(project/'source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(project/'INTAKE.md').write_text(brief,encoding='utf-8')
steps=[]
for i,ref in enumerate(refs,1):
    steps.extend([{'id':f'ref{i}','operation':'ingest','args':{'input':str(ref),'sample_count':48,'width':480,'columns':6}},
                  {'id':f'cuts{i}','operation':'detect_events','args':{'input':str(ref)}},
                  {'id':f'refbeats{i}','operation':'detect_beats','args':{'input':str(ref),'fps':24000/1001}}])
steps.extend([{'id':'song','operation':'ingest','args':{'input':str(song)}},
              {'id':'songbeats','operation':'detect_beats','args':{'input':str(song),'fps':24000/1001}},
              {'id':'episode','operation':'probe','args':{'input':str(episode)}},
              {'id':'packs','operation':'batch_inventory','args':{'inputs':[str(x) for x in sorted(packs.glob('*.mp4'))]}}])
save('preparation-intent.json',{'project':pid,'plan':{'version':1,'title':'Pure Snow new edit · reference/source preparation','steps':steps}})
job=post('services',{'action':'media-submit','project':pid,'plan':{'version':1,'title':'Pure Snow new edit · reference/source preparation','steps':steps}})
save('preparation-job.json',job);(project/'preparation-job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
lease=post('production',{'action':'native-claim','owner':'Neural2 Pure Snow production · single guarded station writer','project':pid,'oldDisabled':True});save('lease.json',lease)
candidates=[{'route':'gemini','model':'gemini-4-hydrogen-high','effort':'high'},{'route':'codex','model':'gpt-6.1-sol','effort':'medium'},{'route':'gemini','model':'gemini-3.8-flash-high','effort':'high'}]
reviewers=[{'route':'codex','model':'gpt-6.1-terra','effort':'medium'},{'route':'gemini','model':'gemini-3.8-flash-high','effort':'high'}]
request={'action':'start-production','project':pid,'nativeLeaseId':lease['id'],'candidates':candidates,'reviewers':reviewers,'artifactRoots':[str(songfolder),str(packs),str(episode.parent),str(ROOT.parent/'NEURAL_STUDIO/data/local-ops'),str(ROOT.parent/'TFX_REPLICA_LAB')]}
save('production-intent.json',request)
run=post('control',request);save('run.json',run)
print(json.dumps({'project':pid,'run':run['id'],'state':run['state'],'phase':run['phase'],'preparationJob':job['id'],'brief_chars':len(brief)},indent=2))
