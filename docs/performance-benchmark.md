# Realtime Subtitle v2.10.0 — performance and regression benchmark

Last updated: 2026-09-01

This document defines a repeatable, privacy-safe benchmark for the v2.10.0
streaming pipeline. Results below are measurements, not marketing estimates.
Generated audio and machine-local result JSON are intentionally ignored by Git.

## Test machine and reproducibility

- MacBook Air `Mac17,3`, Apple M5, 10 logical cores, 24 GB RAM, macOS 26.5.
- Backend: faster-whisper/CTranslate2, bundled `tiny` model, CPU `int8`.
- Runtime profile: **Balanced**, five inference threads and one model worker.
- Fixture text: project-authored CC0 phrases in
  [`benchmarks/phrases.json`](../benchmarks/phrases.json).
- Audio generation: macOS `say`, resampled to mono 16 kHz PCM WAV; selected
  cases add deterministic gain reduction, white noise, or a low music-like tone.
- The generated WAV files contain no user recordings and are excluded from the
  repository to avoid bloating release history.

Reproduce locally:

```bash
./.venv/bin/python tools/generate_benchmark_audio.py --include-long-session
./.venv/bin/python tools/run_streaming_benchmark.py --profile balanced
./.venv/bin/python tools/run_long_session_benchmark.py --profile balanced
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m pytest -q
```

## Metrics

- **First partial**: wall-clock time from simulated speech start until any draft
  recognition is available.
- **First stable**: time until LocalAgreement-style matching confirms a stable
  prefix. This can be later than the acoustic end for very short fixtures because
  a second hypothesis is required.
- **Final after end-of-speech**: final recognition compute after the complete
  fixture is available. The application also adds endpoint decision time.
- **WER/CER-like rate**: normalized word edit rate for English; normalized
  character/token edit rate for Chinese and mixed text.
- **RTF**: recognition compute time divided by audio duration; below `1.0` is
  faster than real time.
- **Stable conflict**: final decoding disagreed with an already confirmed draft
  prefix. The UI preserves monotonic stable text during partial updates and
  resolves the conflict once at finalization.

## Short streaming corpus results

| Case | Audio | First partial | First stable | Final after EOS | Error | RTF |
|---|---:|---:|---:|---:|---:|---:|
| English short | 1.79 s | 1.36 s | 2.02 s | 0.16 s | 0.0% WER | 0.088 |
| English hesitation | 4.03 s | 1.36 s | 2.73 s | 0.19 s | 0.0% WER | 0.048 |
| English long/fast | 7.53 s | 1.36 s | 2.73 s | 0.25 s | 0.0% WER | 0.033 |
| Chinese short | 5.33 s | 1.36 s | 4.12 s | 0.22 s | 50.0% CER-like | 0.042 |
| Chinese hesitation | 5.65 s | 1.36 s | 2.73 s | 0.22 s | 38.1% CER-like | 0.038 |
| Chinese/English mixed | 5.49 s | 1.47 s | 4.42 s | 0.34 s | 31.3% CER-like | 0.062 |
| Weak noisy English | 3.35 s | 1.37 s | 3.72 s | 0.18 s | 40.0% WER | 0.054 |
| Chinese with tonal noise | 4.85 s | 1.37 s | 5.39 s | 0.25 s | 21.1% CER-like | 0.051 |

Aggregate: mean RTF `0.052`, mean normalized error `22.55%`, maximum RSS
`349.67 MB`. The `tiny` model is decisively fast, but Chinese, mixed-language,
quiet and noisy audio do not meet a high-accuracy claim. Balanced therefore
remains the low-latency default; the app recommends/downloads a larger model
when accuracy matters rather than silently raising sustained compute cost.

## Thirty-minute acoustic session

The long harness processed a 30-minute generated bilingual/noise fixture in 200
nine-second segments while reusing one model instance:

| Metric | Balanced result |
|---|---:|
| Completed / failures | yes / 0 |
| Wall inference time | 73.906 s |
| RTF | 0.0411 |
| Average process CPU | 571.74% |
| RSS start / peak / end | 521.09 / 538.78 / 538.78 MB |
| RSS growth | 17.69 MB |
| Empty / repetitive segments | 0 / 0 |

This is an accelerated **30-minute acoustic workload**, not a claim that the
machine stayed thermally cool for 30 wall-clock minutes. It exercises model
reuse, buffers and cleanup quickly and found no crash or unbounded segment-level
growth. A prior Maximum-profile run had nearly identical RTF (`0.0407`) but
about `859%` CPU and `38.52 MB` RSS growth. That evidence is why Balanced limits
this machine to five ASR threads and one model worker; Maximum remains opt-in.

## Incremental translation validation

Provider latency is environment-dependent, so the regression suite validates
the scheduling contract separately from a network speed claim:

- only a stable source prefix is submitted;
- one request runs and at most one newest request waits;
- session and source revisions invalidate obsolete work;
- an unrelated rewrite cannot be replaced by an older response;
- final text supersedes drafts and is never changed by a late draft;
- slow providers execute outside the UI and recognition threads.

Apple Translation requires macOS 26 and installed language assets. The helper
was present on this test Mac, but an ad-hoc command-line probe timed out; this is
not counted as a passing provider benchmark. LM Studio was not listening on the
configured local port during this benchmark. Packaged, signed-app provider tests
remain part of the release smoke checklist and must report failure honestly.

## Regression matrix

| Risk | Automated coverage / gate |
|---|---|
| Partial → stable → final monotonicity | `test_streaming_transcript_state.py` |
| Stable-prefix disagreement at final | explicit conflict/finalization tests |
| Out-of-order/obsolete translation response | `test_live_translation_drafts.py`, scheduler integration tests |
| Fast start/stop and session reuse | pipeline/state-machine and shutdown tests |
| Service switch / old success state | translation page/provider tests |
| Disconnect, timeout and provider error | translation engine/scheduler tests |
| Download failure and stale progress | model-manager and translation-model-manager tests |
| Overlay destroyed or hidden | overlay lifecycle/rendering tests |
| Narrow overlay and history window | rendering tests plus screenshot comparison |
| No recording | playback controls hidden by session metadata tests |
| 30-minute model reuse | `tools/run_long_session_benchmark.py` |

## Release interpretation and remaining limits

- Synthetic speech makes runs repeatable but does not replace diverse human
  speakers, real microphones, room reverberation, accents or protected media.
- WER/CER above is a small engineering regression corpus, not a statistically
  representative model benchmark.
- CPU percentage is process-wide and can exceed 100% on a multi-core Mac.
- Power draw and temperature require external instrumentation; CPU duty cycle,
  RTF and memory growth are the portable proxies recorded here.
- The release must not claim an online, Apple, LM Studio or offline-translation
  latency result unless that provider actually ran on the release machine.
