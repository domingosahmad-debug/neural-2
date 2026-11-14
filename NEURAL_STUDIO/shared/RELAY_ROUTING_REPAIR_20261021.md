# Relay routing repair — tested source, activation pending

## Human scope / live ownership

Tony asked to inspect the actual Relay conversation and repair misinterpretations in the background only if Claude's edit is not interrupted; otherwise wait for it to finish. Claude was working on R5 with continuation_authorized=true; later it ended its turn with one legitimate local job and one completion watch still pending. This is ongoing editing, not proof it stopped. Earlier human pause was superseded by Tony's explicit Relay instruction to start working, accepted at21:18:21 Cairo in the saved chat. Do not pause/resume, re-prompt, change owner, modify edit data, native execution or active jobs for this helper maintenance.

Current server33448 loads the earlier helper. `/api/helper/state` has no routing_version marker yet. The new source marks routing_version=`2026-10-21.2` after a normal backend reload. No restart, injection or hot reload was attempted by this task. Earlier automatic review rejected companion restart with `blocked by policy`; no alternate route is authorized to bypass that rejection. The temporary heartbeat `finish-relay-routing-activation-after-edit` checks every15minutes, quiet while unchanged/progressing. Once delivered full review + quiescent ownership, request a normal human close/reopen once and pause it; if an independent normal restart already exposes the marker, verify and finish/pause. A terminal actionable edit failure is a notification, not permission to keep polling or start a duplicate recovery/edit.

## Observed failures (actual chat, not assumptions)

- “It's able to make an edit from0to100 … everything it's learned” and later pronoun questions were answered with saved lesson paragraphs. The date-follow-up branch matched any `days?`, including “one day” in a future-capability question. Learner subject/context wasn't retained for “it”; later corrections still triggered the wrong branch.
- Future question “after learning more lessons” received a current-role denial. The router did not distinguish future possibility from installed present capability.
- “For now, go to the director's tab and tell Claude to continue working,” “Send the director to start working,” and the chat/leaderboard speech variant failed narrow parsing. The broad `working` status fallback then narrated an old director message instead of forwarding an instruction. The old render-running message was obsolete.
- Active runtime can expose production_pause=null; the old fact collector called `.get` on it and could fail inspection.

## Source repair

`app/helper_intents.py`: bounded context over public recent messages; explicit learner/pronoun reference, current editing capability versus future possibility, narrowly anchored lesson-period follow-ups and status questions. Corrected/garbled questions do not silently become lessons; “be home one day” gets a specific clarification. General unrelated learner questions still reach the selected reasoning model instead of a hardcoded cannot-edit answer.

`app/helper_actions.py`: conversational imperative wrappers, director tab/chat sentence boundary, actual acting Claude/Opus/Sol aliases, explicit work-continuation commands, send/message forwarding verbs and context-scoped leaderboard speech alias. Payload remains the user's instruction. Preview-only resume remains playback. Questions do not become work authorization.

`app/studio_helper.py`: action parsing first with current director identity; explicit status questions only; no automatic replay of old progress paragraphs. Resume-only request during an active director turn reports already working without a duplicate model turn. Accepted forwards acknowledge actual send; failed sends retain the existing draft fallback. Prompt demands direct answer first and distinction of current ability versus future potential. Historical director text is labeled historical, bounded700chars, and is not current job evidence.

`app/helper_facts.py`: null-safe pause inspection; short current-role answer, conditional future answer with necessary execution/review tools and testing, role summary for “what can Lumen do.” More saved lessons alone do not grant tools or demonstrate autonomous artistic quality. No provider inference needed for these checked answers.

## Validation / activation

30 helper tests pass, including the actual failed phrases, sequential pronouns/future/correction, explicit lesson-date follow-up, forwarding once, current runtime status over historical prose, already-active duplicate guard, null pause, and unrelated learner question routing. Python syntax passes. Broader command-service suite initially had one timing timeout (32/33); the isolated failing test passed on immediate focused rerun. No command-service/editing implementation was changed for that test. The complete33-test command-service rerun then passed (0failures); no editing implementation change was needed. Evidence: .qa/RELAY_ROUTING_REPAIR_20261021.json.

Live helper asks/continuations were NOT used as tests; those would dispatch real work. Tests used mocks/local fixtures and no model calls. The patch is NOT live until routing_version marker is observed. After normal restart, inspect the marker and preserved current director/session/production state without issuing a sample continue command. Physical speech interpretation and provider general-reasoning quality remain untested.

No frontend/world rebuild, edit render, model/provider dispatch, native command, library/skill rewrite, media change or portable FINAL ZIP write occurred. The current edit owns its normal continuation. This helper change must not distract its director into app maintenance.


## Activation follow-up — 2026-10-21 21:42 Cairo

R5b full review is actually registered/current:1cce794b1fcc48908faff2c9532b2872,119505145bytes, revisionR03-v10-correction-r5-style. Production ready_for_review=true; director idle; no waiting/ready completion watch; no active local/provider job; Lumen roaming. Exact latest native command tfx-cb23d98d729544a098c91e00ed1ce115 is completed and its matching result ok=true. These are delivery/runtime checks, not artistic/audio/motion approval.

Relay routing_version is still absent: tested source has not been loaded. Tony must close Neural normally and reopen it to activate routing_version2026-10-21.2. No restart/injection was attempted because earlier automatic review rejected programmatic restart. The one-off heartbeat is removed after this single required-action notification; do not keep monitoring or resume editing. Normal restart must preserve Claude/session/current R5b review and must not itself authorize another editing turn.
