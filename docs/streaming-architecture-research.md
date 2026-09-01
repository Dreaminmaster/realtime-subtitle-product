# Realtime Subtitle v2.10 streaming architecture research

Last reviewed: 2026-09-01

This document records the evidence used for the v2.10 streaming upgrade. It is
not a list of fashionable components: every source is mapped to a concrete
decision, a license constraint, and the Macs that the decision must support.
No source code from the projects below is copied into Realtime Subtitle.

## Product constraints

- The default experience must run on both Intel and Apple Silicon Macs.
- Partial text must appear quickly, but already-stable text must not flicker.
- Recognition, translation, downloads, and warm-up may never block the Qt UI
  thread.
- A slow or stale translation must never overwrite a newer caption.
- Optional large models may improve accuracy, but cannot become a hidden
  download or a default requirement.
- Only final text is persisted. Partial and stable text remain ephemeral.

## Evidence matrix

| Source | License / availability | Evidence relevant to this project | Decision |
| --- | --- | --- | --- |
| [WhisperStreaming repository](https://github.com/ufal/whisper_streaming) and [IJCNLP-AACL demo paper](https://aclanthology.org/2023.ijcnlp-demo.3/) | MIT | LocalAgreement confirms the longest prefix shared by consecutive updates. Word timestamps let the audio buffer be trimmed at a confirmed boundary instead of repeatedly accepting a whole unstable hypothesis. | Adopt the idea as a small project-owned state machine. Use two-observation agreement, conservative suffix retention, monotonic stable text, and a hard final transition. Do not copy its implementation. |
| [SimulStreaming](https://github.com/ufal/SimulStreaming) and [AlignAtt paper](https://arxiv.org/abs/2305.11408) | Current repository is MIT; historical releases changed terms, so a pinned dependency would require a fresh license audit. | AlignAtt delays emission while decoder attention is too close to the unsafe end of the audio buffer. The published system targets GPU-class Whisper/translation models and is considerably heavier than this desktop product. | Adopt the concept of an unsafe volatile suffix, not the model stack. Do not bundle SimulStreaming or make GPU/9B-model assumptions. |
| Apple [Meet the SpeechAnalyzer framework](https://developer.apple.com/videos/play/wwdc2025/277/) and [`volatileRange`](https://developer.apple.com/documentation/speech/speechanalyzer/volatilerange) | Apple SDK; SpeechAnalyzer is limited to recent OS versions and platform terms | Apple explicitly marks a result range that can still be replaced; content outside that range can be consolidated. Asset inventory and download are asynchronous. | Mirror the volatile/stable/final contract in the cross-version Python core. Keep a native SpeechAnalyzer backend as an optional future adapter rather than raising the minimum macOS version now. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and its [transcription API source](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) | MIT | The supported controls include Silero VAD, word timestamps, hotwords, initial prompts, repetition controls, no-speech/log-probability/compression thresholds, and hallucination-silence handling. A commonly reported failure is [repeated sentences in long transcription](https://github.com/SYSTRAN/faster-whisper/issues/465). | Keep faster-whisper as the portable default. Enable conservative final-pass word timestamps and hallucination/repetition guards. Do not run its internal batch VAD on every short partial window; the existing streaming gate already performs capture-time VAD. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT | Quantization, Metal/Core ML acceleration, low-allocation inference, Apple Silicon optimization, and Intel support make it attractive for low-power deployment. | Record as a future backend. Adding another packaged runtime in v2.10 would multiply build, model, and regression matrices; the current release instead fixes repeated work and scheduling first. |
| [WhisperKit](https://github.com/argmaxinc/WhisperKit) and [WhisperKit paper](https://arxiv.org/abs/2507.10860) | Open-source repository is MIT; commercial WhisperKit Pro is separate | Core ML/ANE execution is attractive for Apple Silicon efficiency and supports streaming-oriented timestamps/VAD, but requires a Swift/native bridge and newer macOS targets. | Do not silently substitute it for the portable backend. Keep it as an opt-in future native backend after a dedicated Swift bridge and power benchmark. |
| [Apple MLX Whisper example](https://github.com/ml-explore/mlx-examples/tree/main/whisper) | MIT | MLX and quantized models are optimized for Apple Silicon and expose word timestamps. They do not support Intel. | Preserve the existing optional MLX backend. Hardware recommendations may prefer it only when it is installed and validated; never advertise it as an Intel option. |
| [LiveKit turn detection](https://docs.livekit.io/agents/logic/turns/turn-detector/) | Plugin source and model have different terms; the current model is governed by the LiveKit Model License | Production turn detection combines VAD with semantic/acoustic context instead of using one fixed silence threshold. The model download and license are inappropriate for a transparent default dependency here. | Implement a small deterministic endpoint policy using VAD, silence, punctuation, incomplete-phrase cues, duration, word count, language, and previous context. Leave a typed extension point for a separately licensed semantic model. |
| [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) | Apache-2.0 | A complete architecture combines VAD, LocalAgreement/AlignAtt, rolling buffers, model management, and streaming delivery. Its issue history also shows that long-clip segmentation and empty-output edge cases remain system concerns, not problems solved by one model. | Adopt separation of capture, inference, stabilization, endpointing, and presentation. Do not vendor the server stack into the desktop app. |
| [STACL wait-k](https://arxiv.org/abs/1810.08398) | Research publication | A translator can stay a controlled number of source tokens behind rather than waiting for the whole sentence. | Generic API models are not trained as wait-k models, so do not claim model-native simultaneous translation. Use stable-prefix retranslation with provider-specific delay instead. |
| Google [re-translation strategies for long-form simultaneous translation](https://research.google/pubs/re-translation-strategies-for-long-form-simultaneous-spoken-language-translation/) and [revision-controllable simultaneous translation](https://arxiv.org/abs/2310.04399) | Research publications | Re-translating a growing prefix gives earlier output but needs explicit stability/revision control to avoid distracting churn. | Translate debounced stable prefixes, retain only the newest pending request, cancel or invalidate obsolete work, and freeze final translations. |
| [MacWhisper](https://www.macwhisper.com/) | Commercial product | Mature desktop expectations include local processing, application/system audio, searchable history, exports, model clarity, and custom endpoints. | Keep advanced providers and models out of the primary live screen; surface them in settings with explicit status and feedback. |
| [Buzz](https://github.com/chidiwilliams/buzz) | MIT | Playback/search/export and model management are useful precedents. Its live “append and correct” mode makes the accuracy/power trade-off explicit, and its support material acknowledges corrupt/incomplete downloads as a real failure mode. | Keep a user-selectable performance profile and atomic download/install feedback. Preserve lyric-style playback only for sessions that actually contain audio. |
| [Aiko](https://apps.apple.com/us/app/aiko/id1672085276) | Commercial App Store product | Aiko deliberately favors accuracy over speed and ships a large local model, illustrating that high-accuracy transcription and low-latency live captions are distinct products. | Do not force the largest model into the live default. Large models remain an explicit high-accuracy download. |
| Apple [Live Captions on Mac](https://support.apple.com/guide/mac-help/mchldd11f4fd/mac) | OS feature; hardware/language availability varies | A caption surface can remain independent and useful over other applications, with platform availability disclosed rather than hidden. | Preserve a non-activating floating window and never recall the dashboard on caption updates. |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/), Apple [accessibility HIG](https://developer.apple.com/design/human-interface-guidelines/accessibility/), and [Media Accessibility captions](https://developer.apple.com/documentation/mediaaccessibility/captions) | Standards / platform guidance | Live captions are an accessibility requirement; reflow must not require two-dimensional scrolling, and contrast/readability need to survive variable backgrounds. | Captions wrap within the current width, history reflows at narrow sizes, state differences use opacity plus a text status rather than color alone, and no horizontal scrolling is introduced. |

## Failure patterns extracted from products and Issues

The recurring problems are architectural rather than a single bad threshold:

1. Reprocessing the same growing audio window can create high CPU use and
   repeated text. Latest-only partial inference and a bounded audio window are
   therefore more important than adding another timer.
2. Partial hypotheses are useful but unstable. Treating them as final creates
   flashing, duplicated history entries, and translations that jump backwards.
3. A fixed silence cutoff splits hesitations and unfinished phrases, while a
   very long cutoff delays every final result. Endpointing needs multiple
   signals and a hard maximum.
4. Retranslation without revision identity lets slow network results overwrite
   current captions. Session, segment, source-revision, and request-generation
   checks are required at the presentation boundary.
5. Model downloads fail partially or are reported as installed before atomic
   completion. Progress, verification, cancellation, and explicit error states
   are product requirements.
6. “Most accurate” local models can be unsuitable for a live, battery-powered
   Mac. Accuracy, latency, memory, and sustained heat must be separate profiles.

## v2.10 target state model

Each logical caption segment owns one monotonically increasing revision:

```text
audio -> partial ASR -> agreement tracker -> PARTIAL
                                  |          (volatile suffix may change)
                                  +-------> STABLE
                                             (agreed prefix never regresses)
endpoint decision ------------------------> FINAL
                                             (only state written to history)
```

- **Partial** is the complete latest hypothesis. The UI derives a volatile
  suffix by removing the stable prefix. It may be replaced in place.
- **Stable** is the longest token prefix shared by two useful consecutive
  hypotheses, excluding a small unsafe tail. It is monotonic within a segment.
- **Final** is emitted exactly once after endpointing or an explicit stop. The
  final recognizer may revise only the volatile suffix. If it conflicts with
  committed stable text, the conflict is counted in diagnostics and the state
  machine prefers coherent final text rather than duplicating both variants.

Only a final update enters phrase composition, session persistence, export, or
the final translation scheduler.

## Incremental translation policy

The incremental coordinator consumes `(session, segment, source_revision,
stable_prefix, latest_source)`. It provides these guarantees:

- one active and at most one pending draft per segment;
- minimum stable-token/character growth before a new request;
- provider-specific debounce (shorter for Apple/offline, longer for network or
  local chat-completion servers);
- cancellation where the provider supports it, plus generation checks where it
  does not;
- stale responses may never replace a newer source revision;
- final translation has a separate final revision and invalidates every draft;
- translation exceptions become an unobtrusive status, not subtitle content.

This is bounded retranslation, not a claim that a generic provider implements
wait-k. It gives useful early translation while keeping request volume and
visual revisions controlled.

## Endpoint policy

The default endpoint policy combines:

- current capture VAD state and adaptive noise floor;
- silence duration;
- transcript punctuation and language-specific sentence endings;
- unfinished English function words and common CJK continuation particles;
- segment duration, word/character count, and a hard maximum;
- whether the latest hypothesis still changes materially;
- previous segment context for phrase merging after a hard split.

A short pause may finalize a complete, punctuated thought. An unfinished phrase
receives more time. Long speech is bounded even without silence. Visual wrapping
never creates a semantic segment.

## Hardware profiles

| Profile | Intended hardware | Default behavior |
| --- | --- | --- |
| Energy saver | Intel, low-memory Macs, long meetings | Small/tiny quantized model, one partial job at a time, longer partial interval, shorter context, no speculative translation before stable growth. |
| Balanced | Default and automatically selected | Hardware-matched model, latest-only partial inference, two-update agreement, adaptive endpointing, debounced incremental translation. |
| High accuracy | Capable M-series Macs, explicit opt-in | Shorter partial interval and continuous optional refinement. Larger models remain explicit downloads and are never fetched silently. |

Profiles are recommendations, not irreversible capability gates. A user can
choose a different profile, and diagnostics record the measured cost.

## Adopted and deferred work

Adopted in v2.10:

- LocalAgreement-inspired three-phase state machine;
- bounded, provider-aware incremental retranslation;
- multi-signal endpointing and same-position correction;
- latest-only partial scheduling and bounded repeated work;
- runtime latency/resource metrics and reproducible regression fixtures;
- responsive, non-activating presentation of partial/stable/final text.

Deferred with an explicit reason:

- **Native SpeechAnalyzer backend:** valuable, but macOS-version and native
  bridge work must not remove Intel/older-macOS support.
- **AlignAtt/SimulStreaming model stack:** GPU and model footprint are too large
  for the default desktop distribution.
- **LiveKit semantic model:** separate model license and download size require a
  deliberate opt-in integration.
- **whisper.cpp/WhisperKit migration:** both deserve isolated power/accuracy
  benchmarks before adding a second packaged runtime.

## License and release checklist

- Recheck the exact tag and license before introducing any new dependency.
- Do not bundle model weights whose training data or redistribution terms are
  unclear.
- Keep third-party notices synchronized with packaged dependencies.
- Generated benchmark audio contains only project-authored phrases and no user
  recordings.
- API keys, model caches, machine-specific paths, and benchmark outputs remain
  ignored by Git.
