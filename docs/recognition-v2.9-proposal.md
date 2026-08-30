# Recognition accuracy proposal for v2.9

This proposal keeps Realtime Subtitle local-first while addressing the main failure visible in current sessions: the bundled `tiny` model is fast, but it often mishears natural speech and commits short pauses as separate sentences.

## Recommended direction: streaming draft + accurate final pass

1. Use a fast model only for low-latency partial captions.
2. When an utterance is likely complete, run a second local pass with `small` or `turbo` over the buffered audio.
3. Replace the draft in place instead of adding a duplicate subtitle.
4. Give the final pass the preceding two finalized sentences, a fixed source language when known, and an optional user glossary.
5. Delay hard sentence boundaries when the phrase ends with a connector, is unusually short, or lacks sentence-final punctuation.

This preserves immediate feedback while improving the text that is saved, translated, and exported.

## Quality presets

| Preset | Draft model | Final model | Expected hardware | Trade-off |
|---|---|---|---|---|
| Fast | `tiny` | `small` | Intel and entry Macs | Lowest latency, moderate final accuracy |
| Balanced (recommended) | `base` | `turbo` | Apple Silicon, 8 GB+ | Strong speed/accuracy balance |
| Accurate | `small` | `large-v3` | Apple Silicon, 16 GB+ | Highest local quality, more RAM and heat |

## Endpointing and context changes

- Add adaptive silence thresholds based on the recent noise floor instead of relying only on one fixed value.
- Treat short fragments, conjunctions, and unfinished clauses as provisional for a configurable grace window.
- Keep audio overlap between chunks so words at a boundary are not lost.
- Reject obvious no-speech/hallucination results using confidence and repetition checks.
- Lock the spoken language when the user selects one; keep automatic detection only when needed.
- Add a per-session glossary for names, products, and technical terms.

## Rollout and verification

The two-pass pipeline changes latency, memory use, and the lifecycle of saved transcript revisions. It should ship behind an opt-in **Enhanced accuracy** switch first. Acceptance should compare the current and proposed pipelines on the same recorded corpus and measure:

- word error rate and named-entity accuracy;
- time to first partial caption;
- time to final caption;
- incorrect sentence splits and later corrections;
- peak memory and sustained CPU/GPU use on Intel and Apple Silicon.

The current release therefore adds clear model-quality guidance but does not silently change the recognition engine. Implementation should begin after this architecture and the default preset are approved.
