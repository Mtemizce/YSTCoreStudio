---
name: hyperframes-video-director
description: >-
  Taste and judgment for directing HyperFrames videos: ads, launches,
  explainers, typography, stings, data stories, documentaries, trailers,
  beat edits, demos, character animation, reels, 3D, lyrics, news,
  tutorials and comedy shorts. Guides creative decisions and visual
  review without templates, component code, palettes or layout presets.
---

> **YEREL KURAL + STÜDYO NOTU:** Bulut/hesap/telemetri yok (`studio/CLAUDE.md`). Bu skill **zevk ve yargı** içindir; uygulama bizde `remotion-best-practices` + `kit/` (Remotion) ya da `hyperframes` skill'i. Gözden geçirme: `rubric.md` (0-4 puan). Bu skill'in betikleri KURULMADI (üçüncü taraf kod çalıştırmıyoruz); ölçümler için `studio/araclar/kalite_olc.py` ve `ses_olc.py`. Stüdyo kuralları (MARKA.md yasak listesi) bu skill'in önerilerinden önce gelir. Kaynak: github.com/artificialguybr/hyperframes-video-director (MIT).
# HyperFrames Video Director v4

## Read only what changes this video
- Read the matching `directing/<type>.md`; combine two only for a hybrid.
- Read `craft/vocabulary.md` when the plan repeats familiar moves.
- Read `craft/rules.md` for ranges; source IDs resolve in `SOURCES.md`.
- Use `rubric.md` to review; use official HyperFrames skills to implement.
- No type specified? Infer from the viewer's goal, not the video's length.

## Make four decisions before building
1. Write one sentence: what changes for the viewer during this video?
2. Name the feeling of the LAST frame.
3. Commit to ONE bold choice: visual idea, rhythm or transition language.
4. Name what you deliberately will NOT do.
Keep these four answers short. Do not write essays before animating.
Invent the layout, typography, palette and implementation for this brief.
If the plan is centered text on a flat field with repeated fade-ups,
change layout, camera, transition type or rhythm BEFORE building.

## Direct, do not fill slots
- Prefer an identifiable focal point; let supporting movement arrive later.
- Pick 2–3 techniques that express the idea, not a quota of effects.
- Vary scale, framing and temporal contrast; repetition may establish a motif.
- Density is a dial: sparse emphasizes a subject; medium builds relationships;
  dense creates spectacle or overload. Change it when the story changes.
  The genre default is a starting point, never a required layer count.
- Hold long enough to understand the result; cut sooner when tension benefits.
- Reserve stronger accents for stronger information; silence and stillness count.
- Keep accessible captions even when they duplicate speech; avoid a second
  prominent headline repeating those captions without a communicative reason.
- Choose color and type from the brand and concept, not a supplied preset.

## Build → look → fix (minimum TWO render/review passes)
1. Build the first version using the official HyperFrames contract.
2. Run official lint/check; read errors AND sample counts before trusting them.
3. Render a draft; generate a contact sheet with `scripts/contact_sheet.py`.
4. LOOK at the sheet at intended display size; watch the video and hear the mix.
5. Run `scripts/amateur_check.py` on the render and project; include browser
   layout observations for geometric clipping, contrast and caption checks.
6. Score `rubric.md`; fix the THREE worst problems, not every possible detail.
7. Re-render, regenerate the sheet and re-score. Repeat if critical faults remain.
Never claim visual review from file inspection or a tool exit code alone.

### Look for these eight observable problems
- Headline edges, descenders or overshoots cut off after an entrance settles.
- Two equally loud subjects asking for attention at the same moment.
- Accidental single-plane flatness where depth would clarify relationships.
- The same direction, entrance and duration repeating without a motif/payoff.
- Empty holds that reveal nothing; distinguish them from intentional suspense.
- Captions colliding with, or needlessly repeating, prominent on-screen text.
- Cuts between unrelated still moments without contrast, continuity or purpose.
- Sound peaks arriving after the visual landing; speech buried under effects.

## Verified render gotchas (implementation belongs to official skills)
- Read `/hyperframes-core`, `/hyperframes-animation` and `/hyperframes-cli`.
- Register one paused timeline per composition AFTER build; key matches its root ID.
- Declare finite export length; avoid render-time clocks and unseeded randomness.
- Do not animate clip display/visibility/autoAlpha; animate its contents instead.
- Do not fight an animated property with a CSS initial transform.
- Ship named fonts; audio needs an ID; media must not carry `crossorigin`.
- Do not mutate content from wall-clock or event history; seek-derived updates
  are not universally forbidden. Verify repeated seeking gives the same frame.
- Clear lint errors: zero layout samples can mean the audit never ran.

## Route by intended experience
Social ads → social-ad; launch films → product-launch; explanation → explainer;
type-led pieces → kinetic-type; identity → logo-sting; evidence → data-viz;
observational stories → documentary; anticipation → trailer;
track-led edits → music-beat; product operation → ui-demo;
character/vector stories → vector-2d; portfolio montage → showreel;
generative/product heroes → procedural-3d; sung text → lyric-video;
on-air information → broadcast; instruction → tutorial; comic shorts → meme-short.

## Delivery
Use `references/accessibility-and-delivery.md`; test the encoded output.
State which tools ran, which frames you saw, and which measurements were skipped.
Do not fabricate source support, model evaluations or photosensitivity clearance.
