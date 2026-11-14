# Tony / Neural — chat migration and durable continuation

Written 2026-10-24 for a NEW Codex chat in the SAME `New project` workspace, at Tony's explicit request. This is a supervisor-chat migration, NOT a new Neural director session or an instruction to resume editing.

## Read first: latest human authority

Tony wants to retire the very long supervising chat, retain all useful context, and talk naturally to its successor. Read this handoff once, then use compact current-state pointers. Do not repeatedly reload the entire historical transcript. This document is a factual working-context transfer, not a claim that hidden model state or unlimited verbatim recall can be transferred.

Tony explicitly says to IGNORE the separate Antigravity Gemini 3.8 work he commissioned, which he considers poor. Do not adopt its proposals, resume its tasks, overwrite its work, cancel unrelated workers, or treat its completion prose as acceptance. If that work touched the same files, reconcile actual live identity and preserve the files before any later authorized changes. No editing was newly requested by this migration itself. Acknowledge readiness and wait for Tony's next direction.

Name: Tony. Product: **Neural / Neural Posthouse**, not Neuro (despite occasional spoken shorthand), not Neuralink. Main editor identity Sol/Codex. Tony wants consistent conversations, low usage and trustworthy evidence, not repeated optimistic status messages or identical weak revisions. Do not react defensively to frustration. State actual outcomes and limitations plainly.

## Workspace and connection

Project path `C:/Users/TUF/Documents/New project`, Codex project ID `local-41b166615ef37508374853122d2b91c8`. Use this explicit cwd in tools. Windows PowerShell, Africa/Cairo. Neural is a LOCAL desktop app launched by desktop icon, not a browser extension/site. Its companion API is `http://127.0.0.1:8767`.

Read supplied root AGENTS.md. The literal TFX trigger requires `TFX_MASTER_CONTEXT_2026-08-20.md`; STANDUP additionally requires `STANDUP_MONTAGE_MASTER_HANDOFF.md`. Skills in `C:/Users/TUF/.codex/skills` cover workflow director, reference analysis, footage story, typography, color/mattes, sound, transitions, review, TonyFX execution, local ops and state handoff. Read relevant skills for actual work; do not load everything by default.

Current state checked during migration:
- Director **idle**, model label `gemini-3.8-flash-high`; this label differs from primary policy Sol and reflects recent runtime route, not permission to adopt Gemini work.
- Saved Sol Neural thread **`01a16dbd-82ec-7840-8d69-d2197ee8cc19`**, turn null.
- Saved official native Claude session **`08d743a0-6ab0-4d99-b662-ee5c1567d9d2`**.
- Error null, **no pending completion watches, no active local jobs**. `continuation_authorized=true` is historical scope, NOT a new request to resume now.
- Conversation policy version **`2026-10-24.1`**.
- Actual latest catalog includes R06 and R05. R06 director completion text is Gemini-authored; no fresh picture/listening/artistic verification was performed by the migrating supervisor. Source STATE timestamps have apparent UTC/local inconsistencies. Prefer actual job IDs/results and encoded artifacts over narrative timestamps.

API reads: `/api/command/state`, `/api/local-ops`, `/api/production`, `/api/state`, `/api/previews`, `/api/workbench`. Command state wraps `leader`, `watches`, etc. It contains HUGE history: SELECT compact fields before serializing, never dump whole response. Likewise source snapshots can be huge.

Authenticated mutations: obtain token from GET `/api/config` WITHOUT PRINTING IT. Header `X-Studio-Token`, `Origin:http://127.0.0.1:8767`, JSON body. `/api/command/send` `{message,attachments:[id...]}` sends a real direction in the saved director chat. Check real active turn/provider/local/native/watches first; never duplicate. `/api/command/watch-native` exact command_id; `/api/command/watch-local` job_id; `/api/command/watch-job` provider job. These register actual completion wakes and permit ending inference while work runs. `/api/command/stop` stops/revokes owned chains but does NOT prove AE/native renderer stopped. `/api/team/note` persists corrections with project_id, kind, text, existing source path. `/api/production/accept` is formal HUMAN acceptance; do not fake it. `/api/command/refresh-usage` metadata only; no polling for quota.

## Where actual work belongs

Tony repeatedly insists editing runs **inside Neural** through its director, local workers, station jobs and visible evidence. This supervising chat handles brief setup, scoped maintenance, compact status/diagnosis and safe handoff. Do not start analyzing all media or independently editing AE here while a Neural director owns it. Do not use computer use to edit unless Tony newly asks. Do not repeatedly send continue or create extra chats for each execution. Actual commands and worker communication should appear in Neural, not staged decorative conversations.

Use local deterministic engine for mechanical processing before handwritten scripts/model tasks: read `shared/LOCAL_OPS_WORKFLOW.md`, `shared/PRODUCTION_WORKBENCH_WORKFLOW.md`, `shared/PRODUCTION_CHECKPOINT_WORKFLOW.md`; query `python NEURAL_STUDIO/tools/local_ops.py capabilities` and workbench CLI from proper cwd. One revision-bound blueprint holds source/quote/style/music/ending decisions; frozen bounded station context, explicit methods, protected-state checks. Models interpret compact ambiguous evidence; no AI to count frames/probe codecs/read status/bookkeep. Technical PASS is separate from sampled picture, full-speed motion, listening, and Tony's artistic acceptance.

Usage: idle model turn consumes no inference, but active director/helper turns do. End inference while real local/native/provider jobs run, register exact completion wakes. No LLM status loops, repeated directions, decorative team chatter, benchmarks (Tony excluded upgrade #4), fake percentages, quota/cancellation claims, or promises of zero usage for real model work. Current availability must be actually reported. A high-reasoning cheap model is not automatically suitable for creative story/native work. Tony prefers Claude creative treatment/effects, Sol debugging/integration; bounded Flash/Lumen/mechanical help when it actually fits, not arbitrary delegation. Do not claim tools/modality exist based on model marketing alone.

## Conversation continuity — already repaired and activated

Read `shared/ALL_PROVIDER_CONVERSATION_CONTINUITY_20261024.md` and `shared/CONVERSATION_CONTINUITY_ACTIVATION_20261024.json` if investigating. Do NOT redo this repair or restart now.

Found real former bug: `_bound_context()` reset Sol's Neural thread at >48k input tokens, including completion wakes. Six resets in ~14 minutes weakened continuity. It was removed; provider runtime now handles context management. 162 focused tests passed; normal Tony close/reopen activated it. The next actual R05 turn retained EXACT Sol thread above, proving natural continuation. Mocked tests are not proof of every provider's real resumptions.

Current contract: Sol director resumes saved Codex thread; native Claude director resumes exact saved official CLI session; Gemini director session keyed by workflow/model; moving between directors preserves individual sessions plus shared authoritative current blueprint/memory. No silent fresh conversation on missing/deleted/mismatched session: visibly reconcile. Ordinary workers in FIVE configured adapters (Codex, native Claude, Antigravity, OpenCode, legacy Gemini CLI) have registry `data/conversations/workers/<sha256>/SESSION.json`, identity robot/profile + provider + model + workflow, stable workspace. Station/project not key, so bot can move/reuse context. No `--ephemeral`/`--no-session-persistence` for these persistent workers. Tool-less ordinary worker restrictions remain; persistent memory does not grant native tools. Legacy disabled routes not enabled by this work. Future Grok/Composer adapters need explicit supported resume contract, not magical access. Old ephemeral histories cannot be reconstructed. Workflow isolation/schema migration or explicit human reset are separate from automatic per-task resets.

Important files: `app/worker_conversations.py`, `app/operations.py`, `app/command_service.py`, `app/native_director.py`, `app/director_backup.py`, `app/claude_transport.py`, `app/provider_runtime.py`, `shared/STATION_ROUTING_AND_MEMORY.md`. Preserve them and current ownership. New supervising Codex chat is explicitly authorized; that does NOT replace Neural's saved director thread.

## Current Bleach LUZ ROJA and delivered versions

Project **`3f35b5e3f5aa48358bed707efc4be279`**, folder `C:/Users/TUF/Documents/New project/NEURAL_STUDIO/data/bleach-luz-roja-reference-20261023`.

Main characters Ichigo + Aizen versus Yhwach. Raw original source footage, no stealing/reusing completed old scenes/builders/mattes/outros. Source/reference input folder `C:/Users/TUF/Downloads/New folder (24)`; read INPUTS.json for actual Unicode reference filename. Song bxkq LUZ ROJA Slowed; reference Yuta Okkotsu Luz Roja by TOUYA. Song offset **36.385s, rate1**. Current duration **1380 frames, 57.5575s at 24000/1001**,1920x1080. User allowed <=60sec with intentional opening/end. Prior song source clipping cannot be undone by lowering gain; be honest.

Latest catalog **R06** (Gemini-authored completion, pending Tony acceptance; ignore any separate Gemini trial):
- `work/r06_cinematic_finish/STATE.md` (read exact relevant tail, not whole raw snapshots).
- AEP `work/r06_cinematic_finish/LUZ_ROJA_R06_MASTER_AE24.aep`, claimed master **2681 / 214 layers**.
- Full preview **`f8b9304dc0a34dfbb00bb0e2f614b95c`**, real PC URL `http://127.0.0.1:8767/api/preview-media?id=f8b9304dc0a34dfbb00bb0e2f614b95c`.
- File `data/local-ops/jobs/e8ba479caf2f4bb8934650d7872d69e9/encode/review.mp4`, local job completed. Read actual SUMMARY.json if asked to audit. Final native command **`tfx-cc9351f09fdd4294b8c78b1cebe22e31`**, BUILD_R06_BROADER_FINISH_V2.jsx. Do not replay.
- Report claims engraved cool-metal Goryu type, optical sweep, Bodoni Tensho metallic stroke, deeper USELESS shadow, intro raised into negative space, preserved R07B grade and all20 audio owners. Report says12/15 checked, motion/listening/human pending. These are reported results, not this supervisor's perceptual approval. Verify codec rather than repeat assistant's possibly wrong PCM-in-review claim.
- A failed prototype audio-signature validation was diagnosed as visual enabled flag on audio-muted accent; corrected validator scoped to that field, not a blanket protection bypass. Existing partial preserved and finalized, no unknown replay.

**R05** last Sol-delivered baseline:
- `work/r05_tony_screenshot_repair/STATE.md`, `FULL_R05_RECONCILED.json`, `R05_FAILURE_LEDGER.json`.
- AEP `work/r05_tony_screenshot_repair/LUZ_ROJA_R05_INTEGRATED_AE24.aep`, master **1719 / 213 layers**.
- Full review **`03459a771e9945609474ffac3ef6414d`**, PC URL `http://127.0.0.1:8767/api/preview-media?id=03459a771e9945609474ffac3ef6414d`.
- File `data/local-ops/jobs/9b85494cc0f34f36897202e3ddaf358d/encode/review.mp4`.
- Technical decode/format passed, H2648bit420/AAC, peak .7137 zeroPCMclipping;85 encoded sampled frames inspected by Sol director. Actual final ending mix correlation .9263/1sample and offline SMALL locates words, neither proves listening quality.
- Restored 3-character panel; rebuilt Goryu/Tensho/USELESS; genuine ending voice and deeper duck; kept native R07B grade. Full-speed motion/listening/Tony acceptance pending.

**R04 rejected** preview `8918a62b0549436cb6e419ed84cd259b`, `work/r04/STATE.md`, master1098/154layers, same1380f. Root project STATE stops aroundR03, so work/r05/r06 states are later authority. Preserve R03/R02/R01 too; do not revive them as latest.

## Tony's most important visual/audio feedback

Screenshots `C:/Users/TUF/Pictures/Screenshots/Screenshot 2026-10-24 145611.png`,145628,145642,145652,145656,145708 (all .png) identified:
1 Three horizontal bands at~23s must show **Yhwach top, Ichigo middle, Aizen bottom**. R04 middle was blue sky. Inspect source offset, crop, remap, anchor/mattes and encoded entry/mid/exit, not one favorable still.
2 GORYU TENMETSU~30s and TENSHO~41s: chunky pale-yellow Kinetika block type childish/rejected; needs mature anime cinematic hero type, real word/beat/technique stress, distinct energy. Native font provenance does not equal artistic approval.
3 IT'S USELESS~46s should dominant purposeful central hero moment with picture impact, not small motionless bottom serif.
4 IT'S OVER~48s and MY POWER~56s had no audible quote for Tony, only music, despite numeric PASS. USER LISTENING FAILURE overrides numeric approval. Trace original complete performance through enabled layers/solo/channels/gain/remap/master and final encoded mix. No synthetic quote, truncated words, fake silent-mouth captions, music masking or overlapped speakers. R05 attempted genuine repair.

Earlier: repeated/overlong talking seated Aizen/blue flames, Yhwach mouth moving silently, truncated technique actions and end dialogue, weak/misplaced audio, missing clash/crumble sourceSFX, stale colors, glitchy zooms/joins. No repeated source ranges without justified topology, no captions for words not heard. Complete authentic phrases and believable speaker/action ownership.

Positive target actual Claude old BLEACH TITANIUM native **`data/bleach-aizen-yhwach/BLEACH_A_TITANIUM_THE_GAMBIT_R07B_AE24.aep`**. Screenshot `Screenshot 2026-10-24 003257.png` Aizen outdoors THANKS TO THAT, I CAN NOW STOP YOU praised font animation, effect impact and vibrant darker grade. `003337.png` is negative seated Aizen example. R07B native grade source95Lumetri opaqueblob,115Glow+Noise, text97PerpetuaTitlingMT-Bold, hero102Kinetika-Ultra. Copy actual native grade via carrier, not guessed JSON curves; preserve all original/manual work. Type style must be suited to CURRENT words, not assumed approved just because old project font. Do not import completed old scenes.

Current finishing brief: purposeful anticipation/impact/recovery at stressed beats/contacts; mature dialogue vs hero/technique hierarchy with authored entry/hold/exit; rich controlled color, clear faces, separation; distinct technique treatments; smooth targeted zooms without doubled owners/random jitter; readable action and genuine sound. Preserve good sequence/quotes, change timing only diagnosed. Hardest combined passage proof first, then full review. Technical success alone is not artistic success. Tony asked hypothetical Astra Low/Medium finishing cost: possible, no reliable 5h/weekly percentage estimate; use measured actual calls. No Astra switch occurred; previous finishing dispatch ran Sol then current runtime later reports Gemini. Do not silently claim Astra used.

## Single-editor AE safety and recovery

AE2026 repeatedly crashed even blank; Tony updated drivers/restarted then replaced it with **After Effects2024**. Workflow converted. Do not reinstall/switch AE or blame PC without actual evidence. Native version historical24.0x55; verify current. Blank safe mode diagnostic had stayed open; that was isolation evidence, not full stress-test success. Claude render retry loops previously wasted quota; prevent duplicates and actual unchanged-failure loops.

TonyFX file bridge `C:/Users/TUF/Documents/ae-mcp-bridge/ae_command.json` and `ae_mcp_result.json`. Use tfx-tonyfx-execution skill; one serialized native editor, exactcommandID transport AND script-report success, inspect live identity before mutation. UNKNOWN timeout requires observing exactexistingcommand, never replay/delete locks. Dirty/manual work preserved to new recovery before switching. Never run MCPBridgeAuto while TonyFX open. Confirmed failed operation can have partial work: inspect then NEW corrected bounded script.

Known AE pitfalls: effect property refs invalidate after add/move; reacquire. Add new TimeRemap keys before prune old. startTime moves in/out/keytimes; restore/readback. Native Lumetri/Curves opaque values copy natively. Half-open integerframe plans/rationalFPS. Multiple transform owners,1f reversalkeys/badhandles create jitter. No heavy default render loops; evidence/proof first. H2648bit420/AAC compatible reviews; earlier42210 files unsupportedWindowsMediaPlayer, VLCinstalled. Frameextraction sample_countmax48 or explicitmax4096, FFmpegselect<=36framebatch workaround for tool limits. Local details may evolve: capabilities authoritative.

## Broader Neural product context (do not restart these tasks)

Tony built Neural to be the human-facing main workflow surface, with director chat, task instructions/attachments, full review in a world screen, agent stations, authentic visible work, usage, reusable station skills/handoffs, shared memory and delegation. Every supportedAI can be stationed by capability; any newAI must read station instructions/skills and current blueprint. Collective means durable shared lessons, visible evidence-backed requests/help/replies and capable escalation, NOT invisible magical merged weights or fabricated conversations. Models should ask peers for concrete help rather than mark bad work done. Learner **Lumen** (Flash3.8) learns meaningful completed corrections; durable playbook != retraining/bestmodelguarantee. Access/capability must be verified before assigning independent edit. Cancelled Lumen trial is unrelated; don't resume it.

Voice assistant **Relay** (formerly Jarvis/Signal) addresses Tony, should reason modestly from actual app state, answer direct questions, navigate stations/usage/director, control review play/pause/mute, capture screenshot+time+critique into director draft in background. Enabled by default on app restart; microphone OFF by default, explicit reachabletoggle, assistantpowerbutton; off staysoff untilrestart/manualon. Announce greeting/start/block/help/finished and show completed fullreview, no always listening. Local deterministic commands avoid modelusage; optionallocal/free assistant usesreal configuredcapabilities and honestcost. Read latest actual source/audit if asked, don't assume every feature in history is currently bugfree.

World: Tony rejects bland flatlists, childishSimslook, emptyfield and giantspreadoutdeskarea. Wants compact maturecinematic editingHQ, distinctive robotdesigns/heirlooms/individualanimations, lively contextual activity, smaller localworkerbenches and propervisibleworklabels, cinematicbackground/outdoorrelax/NPC/library/ideas areas, easycamera/navigation and large interactive stationnodes showingactualtasks. Real review must fitaspectunobstructed, not clippingthroughrails/worldgeometry. Performancepriority, no expensivepermanentanimation/syntheticprogress. Source release `shared/NEURAL_CUTROOM_UPGRADE_20261023.md`, maintenanceaudit `shared/NEURAL_MAINTENANCE_AUDIT_20261023.md`. Localcrewvisibility, teamchannel/dashboard, clickabledetailedlocalbanner, chatlatestscrollflicker and Relay routing were maintenance targets. Preserve Claude latestwork. Realjobsstates distinguishscript/localAI/hostedagents, accurateerrors and measurableprogress, never inventETA. Checkpointroadmap includes production vs finalhumanreview; humanperceptualreview at END, not blockedunfinishedconstruction.

Neural portability: existing portable **FINAL ZIP preserve**; fullstationworkflow/skills/instructions/tools/learnerknowledge handoff for otherPC and configurableotherworkflows. GoogleDriveuploadmanualchosen afterextensionblocked. Websiteproject should be Neural, actualFlowadasset+realappscreenshots+beginnerinstructions, animatedresponsive/reducedmotion, downloads GoogleDrive `https://drive.google.com/file/d/1qauD7qjAx467SK3nVFdGy0-X0T5hvljD/view?usp=sharing`, nofakeupdatepackage. Website notcurrenttask. **AE/TonyFX replica explicitlydeferred**, noimplementationnow.

Usageobservatory should show actualactiveprovider/model/accountreserve/resetmetadata; stale exhaustedidleArgonnotprimarymetric; nativeClaudenoexposedpercentage meansunknownnotzero. Never equate consumedtokenswithremainingplanquota or infer resets. Codexusage tool if asked; officialOpenAIdocs for modelpricingquestions. Current `data/command/DIRECTOR_POLICY.json` Solprimary1%reserve, GeminiFlashhighfallback,ClaudeexcludeduntilTonyallowsagainafteractualweeklyrefusal. Older generalnativeClaudeOpus/Sonnetbackupauthexistsbut temporaryprojectexclusionnewer. No allowance assumedreset. NewestTonyinstructionignoreGeminiwork takesprecedenceoverolderautomaticfallbackexpectations fornewactions.

## Historical projects and authority boundaries

Cyberpunk two edits at `data/cyberpunk-two-references-20261023`, sources `C:/Users/TUF/Downloads/Refrences + Songs` and desktop Cyberpunk.Edgerunners.S02... folder (userlabels authoritative, noexternalfactassumption). R03 pair approvedfornow excepttype; approval `R03_TONY_APPROVAL_20261023.json`. A IntoVoid42.5s projectc6b3fb..., B MATRIX36s cc4adc.... Do not resume. Tony wanted Claudecreativeeffects/scenechoice, authenticcyberpunkglitch/overlap/beatuse,30–45s,not14s. Never recycleoldcompletedscenes.

OldBleachTitanium/Defiance project `09c3569fb2c94854bf6194ca2f2c71a9` indata/bleach-aizen-yhwach is positivemethodreference only. Old LOVE_ME/Tyler/STANDUPpaused. Cancelled Lumentrial task`ac55793732194d67b6b89fc35a30b845`, project4d5f5a... cancelled0turns, noresume. Older AGYunknownworker`63dee5f14ddc49e3a2cec00fa4c9e1ab` Oct23and3oldOct18–20unknowns aren'tcurrentactivewriters; processstopped notremoteidleproof. Don'tclearlocks/revive/resend. One-timeoldheartbeatwakeautomationsaren'tnewscope.

Prior automaticapprovalreview rejected programmaticcompanionrestart **blocked by policy**. Do not retryalternateinjection/hotreload/restart. Whenbackendmaintenancegenuinelyneeded,testfirst, safelyquiescewriters, thenTonyclose/reopennormallyleaveAEopen. Explainexactrestrictionifasking. CurrentmigrationrequiresNOrestart.

## Immediate next-chat procedure

1 Read this file. Acknowledge Tony and connectioncontinuity; don'tperformanedit/modelprobe toproveconnection.
2 The migration already checkedcompactlivestateabove. RefreshonceonlyifTonyasksactualstatus/workorstatechangedbeforeaction. Preserve liveNeuraldirectorIDs,even though thissupervisorchatnew.
3 Do not dispatch continue, switchdirector, changefallbackpolicy, cancelGemini, manipulateAE orscheduleanythingsolelyformigration.
4 Wait forTony'snextinstruction; if he requestsreview/repair, reconcilewhichreviewhemeans and separatecurrentGeminiR06fromSolR05baseline. No adoptionofGeminiartisticclaimswithoutverification.
5 FornewauthorizedworkinsideNeural sendONEprecisebriefinthesavedconversation aftersafeownershipcheck,verifyack, thenidlewhileactualcompletionwatchesownprocessing. New supervisorchat mustnotbecomecompetingnativeeditor.

This handoff, actual per-revision STATE/evidence, sharedworkflow/skills and persistentproviderconversations supply continuity. Historical prose is not authority to execute old scripts. No passwords/tokens/private reasoning are included.
