# Relay: background review-frame notes — 2026-10-21

## Using it

Refresh Neural once (Ctrl+R). Open/play a registered review. For a precise moment, pause first, then say:

- “Relay, screenshot this part and add it to the director chat.”
- “Note: the quote starts early and the font needs to feel like fire.”
- “Resume.”
- At another moment, pause and repeat; alternatively say “Screenshot this: the clash is too quiet.”

An unlabelled frame prompts for criticism; the next plain description can become its note. “Note: …” explicitly adds to the last captured unsent frame. Assistant questions/navigation/playback requests do not become comments. The screening panel also has **Frame note**, a criticism field, saved-note details and **Restore unsent notes**.

These commands capture the existing decoded video picture, not the desktop/UI. They freeze picture + selected preview ID/title/revision and playback time together before awaiting uploads. They do not seek, reload, pause, resume, mute, move the camera or open the director panel. Playback time is recorded to milliseconds; it is not an independently verified source-frame number. Seeking/loading/no-review states produce an error rather than a stale or invented image. Your exact criticism is used, without generated guesses about what the image means.

## Draft and storage

Notes append to the director's existing unsent draft without starting a director/model turn. Every note has an ID, preview version, player time and original still path. New comments on that note remain linked to its ID. The normal explicit Send action is still required; adding a note or saying “add it to director chat” does not dispatch editing.

Original screenshots use the existing normalized local ChatImages upload/store. Up to four moments remain individual attachments when space permits. Larger batches become locally drawn, numbered contact sheets, at most six frames per sheet/four attached sheets (24 moments). Existing manual attachments are preserved and reduce available sheet capacity. The original full stills remain individually stored; paths accompany the note for a capable file/image director. Contact-sheet labels and draft IDs link each picture to its criticism. No new model call, online upload, image generation or media re-decode job is required for capture/packing. Explicit microphone transcription remains the existing local voice path.

Note metadata/criticism persist in localStorage; screenshot files persist under data/command/images. The director draft/attachment selection retains its existing session storage. After an app restart or cleared draft, **Restore unsent notes** rebuilds the draft and image sheets. Notes become sent only after the director Send endpoint accepts the actual direction, not when captured or when Send fails. Storage/upload/attachment/draft-limit failures are reported; saved notes are retained for restore. New sends are guarded during sheet preparation. A note is human feedback, not an artistic approval or permission to restart an old revision.

## Deployment / checks

New source web/review-notes.js/.css is embedded in the existing served index by build_web.py, so the companion's static-file allowlist does not require a backend restart. Updated cinema-preview, command-ui, attachments and voice-helper are existing served assets. The frontend intercepts supported review-note utterances before /api/helper/ask. Python helper action parsing/validation also supports them on its next normal backend load; core frontend voice capture does not depend on that fallback.

Live read-only checks: server35696 already reports Relay (the earlier Relay release has been activated since its pending note). GET / and /world.mjs contain the new note controller and frame API; no unserved review-notes.js request is left in generated index. Leader remains idle, continuation_authorized=false, R5 paused. No restart, editing/native/provider dispatch or approval was performed by this feature task. Saved edit revisions and FINAL ZIP untouched.

Validation:24 helper tests;7 offline JS fixtures (review notes, review attachments, preview controls, command UI, chat scroll, voice privacy/controls, lifecycle announcements). Coverage includes picture/time/version provenance, no playback changes, background draft preservation, exact criticism, contact-sheet packing, manual attachment preservation, capacity/upload failure and recovery, persisted restore and explicit-send boundary. Syntax, frontend build and bundled knowledge integrity pass. Tests use synthetic DOM/video/canvas/images; actual physical microphone, desktop rendering and captured pixels from the human's review remain untested. No claim of watching/listening or final edit acceptance.
