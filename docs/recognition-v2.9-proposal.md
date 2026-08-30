# Recognition accuracy implementation for v2.9

Status: **implemented and verified for v2.9.0**. The shipped behavior follows
the approved hardware-aware, opt-in rollout below. Larger models remain
on-demand downloads and the standard recognition path remains the default.

This proposal keeps Realtime Subtitle local-first while addressing the main failure visible in current sessions: the bundled `tiny` model is fast, but it often mishears natural speech and commits short pauses as separate sentences.

## Recommended direction: streaming draft + accurate final pass

1. Keep the user's selected model for low-latency partial and immediate captions.
2. When an utterance is likely complete, run a second local pass with `small` or `turbo` over the buffered audio.
3. Replace the draft in place instead of adding a duplicate subtitle.
4. Give both passes the fixed source language when the user selected one; keep automatic language detection otherwise.
5. Delay hard sentence boundaries when the phrase ends with a connector, is unusually short, or lacks sentence-final punctuation.

This preserves immediate feedback while improving the text that is saved, translated, and exported.

## Quality presets

| Preset | Live model | Final model | Expected hardware | Trade-off |
|---|---|---|---|---|
| Fast | User-selected | `small` | Intel and entry Macs | Lowest added load, moderate final accuracy |
| Balanced (recommended) | User-selected | `turbo` | Apple Silicon, 8 GB+ | Strong speed/accuracy balance |
| Accurate | User-selected | `large-v3` | Apple Silicon, 24 GB+ | Highest local quality, more RAM and heat |

## Endpointing and context changes

- Treat short fragments, conjunctions, and unfinished clauses as provisional for a configurable grace window.
- Keep audio overlap between chunks so words at a boundary are not lost.
- Reject obvious no-speech/hallucination results using confidence and repetition checks.
- Lock the spoken language when the user selects one; keep automatic detection only when needed.

Adaptive noise-floor endpointing and a per-session glossary remain candidates
for a later measured release; they are not presented as v2.9.0 features.

## Rollout and verification

The two-pass pipeline changes latency, memory use, and the lifecycle of saved transcript revisions. It should ship behind an opt-in **Enhanced accuracy** switch first. Acceptance should compare the current and proposed pipelines on the same recorded corpus and measure:

- word error rate and named-entity accuracy;
- time to first partial caption;
- time to final caption;
- incorrect sentence splits and later corrections;
- peak memory and sustained CPU/GPU use on Intel and Apple Silicon.

The implementation is covered by hardware-resolution, same-position revision,
merged-phrase, stale-session, local-model-only, dashboard, and same-WAV
verification tests. Use `tools/compare_recognition_quality.py` with a local
recording and optional reference transcript to compare word error rate.
