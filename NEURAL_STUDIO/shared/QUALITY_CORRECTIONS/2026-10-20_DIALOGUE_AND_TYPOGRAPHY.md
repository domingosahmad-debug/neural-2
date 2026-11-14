# Mandatory correction — V7 dialogue and typography failures

Human rejected V7 overlapping voices, unrelated speaking picture, stacked captions, generic typography and mistimed quotes. This is corrective feedback, not an accepted design.

- Confirmed: V7 native Tanjiro audio1146 [480,570) remained active under new full mix1161. Akaza caption1176/1177 overlapped Tanjiro1147/1148. Replacement means mute superseded audio and text; do not just stack new content.
- A phase ledger and filename are NOT a transcript. Source English subtitle stream3 shows8456.436..8458.855 is 'Don't regenerate', not 'I lost'. 'I lost' begins8461.607. Do not translate approximate extraction labels into captions.
- 6265.664..6268.959 is 'Akaza! I'm going to behead you now!', not the claimed technique name. Do not assign that performance to 'Raging Sun'. Existing native Tanjiro657.4..661.15 quote is a DIFFERENT original performance and must not be conflated with that false ledger.
- 8674.528 'Welcome home, Hakuji' source picture is a different female character, NOT Koyuki. Pixel-verified Koyuki embrace performance8701.764..8705.726 is 'Welcome home, my darling'. Use the authentic performance/picture pairing.
- One speaking voice at a time. Use a source->extraction->timeline ledger at rational FPS, full native-speed words/tails and no adjacent-line spill. Quote picture is the source performance; no unrelated combat pasted beneath a speech without a separately justified narrative cutaway.
- FC channel selection is not proven dialogue isolation. Use the available cached speech separator and disclose listening limits. Original film score must not silently enter the remix.
- One caption system; short phrase blocks synchronized with the original language phrase, no simultaneous romanization+English duplicate. No invented English word-level timing. Verify actual installed font PostScript name and readback, safe bounds, entry/middle/exit pixels. No generic scale-pop for every phrase, distracting tracking, heavy comic outlines or covering faces.
- Technical decode PASS is NOT dialogue/story/typography PASS. Review each independently. Source provenance, speaker mapping, interval intersections, exact caption wording, voice ownership, unsupported modalities are mandatory gates before delivery.
- Text-only reviewers must mark scene match, translation and listening UNVERIFIED when source evidence is missing. Never mark VALID from a ledger. A confident false validation wastes the human's quota and is rejected.

V8 design uses four separated source-matched performances and independently editable music/dialogue; comparison V7 remains preserved. Human artistic approval remains pending. Future workers must cite this correction and validate the relevant gates in their result.

## Verified separation failure and correction
Cached Bandit speech-only candidate erased the sustained Tanjiro shout after1sec and Koyuki final word Anata. Separate effects stem contained those words; music stem was separate. Corrected candidates combine speech+effects (exclude music), preserve actual source duration and source-picture mapping. Never trust stem label alone; inspect alternate stems and whole-phrase completeness. Raw Koyuki source ASR confirms Okaerinasai + Anata, consistent with original subtitle Welcome home, my darling. Listening remains untested.

Native implementation correction: never reuse a serializer helper name for a mutation helper in the same ExtendScript scope. Here animation ease(q) shadowed snapshot ease(array), serializing keyframe easing as null and producing a false preservation failure. Named mutation helper setMotionEase fixes this without relaxing preservation values. Guard failures occurred before any mutation.
