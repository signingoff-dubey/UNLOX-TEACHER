# 03. Speech to text (STT)

## Requirements

- Works offline. No cloud recognition.
- English plus the Indian languages the app supports: Hindi, Telugu, Malayalam, Marathi, Kannada, Tamil, Bengali, Gujarati.
- Handles short questions (2 to 15 seconds) from a school student, often in a noisy room, often mixing English and an Indian language.
- Fits beside the LLM on an 8 GB GPU, so CPU inference must be an option.
- Final transcript within about one second of the student finishing.

## Rejected: the browser's built-in speech recognition

The Web Speech API is easy but, in Chrome, sends audio to a cloud service. That breaks the offline rule and the privacy promise. Not used.

## Candidate engines

| Option | Strengths | Weaknesses | Notes |
|---|---|---|---|
| **faster-whisper** (Whisper through CTranslate2), small or medium | Mature, runs on CPU with 8-bit weights or on GPU, simple API, many sizes | Whisper is weaker on lower-resource Indian languages than on Hindi. Smaller sizes are weaker still | Good default for English and Hindi |
| **Whisper large-v3-turbo** | Better accuracy than small or medium | Heavier. Needs GPU memory that competes with the LLM | Use only if the spike shows spare VRAM |
| **AI4Bharat IndicConformer** (multilingual, covers 22 Indian languages) | Built for Indian languages; research papers use it as a baseline next to Whisper | Newer tooling, custom loading, licence and size must be checked on the model card | Strong candidate for Telugu, Tamil, Malayalam, Kannada |
| **whisper.cpp** | No Python dependency, small binary | Another runtime to ship | Fallback if Python packaging is a problem |

Evidence from the literature (to verify before relying on it):

- A 2026 study evaluates IndicConformer next to Whisper-large-v3 across Indian-language datasets, so per-language numbers exist: arXiv 2606.09335.
- A 2026 health-conversation benchmark used IndicConformer and Whisper-large-v3 as baselines: arXiv 2603.02813.
- A 2026 India-wide speech dataset paper notes that for Indian languages Whisper does not support, researchers mapped inputs to related languages when fine-tuning, which suggests zero-shot Whisper is uneven outside Hindi: arXiv 2603.28714.

This research found no clean head-to-head table for Telugu and Tamil, and no licence terms. Both must be read from the model cards.

## Recommendation

1. **Pick by measurement, not by reputation.** Run a half-day spike: record the same 30 questions in each target language, run each candidate, compare word error rate and latency on this laptop.
2. **Default design:** one STT interface with two interchangeable backends, chosen per language by a small config table. For example: faster-whisper for English and Hindi, IndicConformer for the others, if the spike supports it.
3. **Keep STT off the GPU by default.** CPU inference with 8-bit weights keeps VRAM free for the LLM. Move to GPU only if latency demands it and the budget allows.

## Language handling

- The lesson language is a strong hint. Pass it to the engine and also allow English, since students often ask in English about a Hindi lesson.
- Detect the spoken language when the hint is "auto". Show the detected language in the UI so the student can correct it.
- **Code-mixing** (for example Hindi sentence with English technical words) is common. Test it explicitly. Do not strip Latin words from the transcript; the LLM and retrieval handle them.
- Names of the topic (for example "chlorophyll") are often misheard. Feed the current lesson's title and key terms to the engine as a vocabulary hint if the engine supports prompts, and post-correct with a fuzzy match against the lesson's terms.

## Capturing audio in the browser

| Concern | Plan |
|---|---|
| Permission | `getUserMedia` with echo cancellation, noise suppression and auto gain on. Needs `localhost` or HTTPS |
| Format | Capture through an audio worklet, resample to 16 kHz mono, send as WAV or raw PCM. Avoid lossy re-encoding where possible |
| Modes | **Push to talk** first (hold a button or a key). **Hands-free** second, using voice activity detection |
| Voice activity detection | A small on-device detector (for example Silero VAD) decides when the student has finished. Silence window is a setting |
| Feedback | Live level meter, clear states: idle, listening, thinking, speaking |
| Failure | Mic denied or missing: show a clear message and keep typing available |

## Endpoint behaviour

`POST /api/stt` accepts a short clip and returns `{text, lang, confidence, duration_s}`.

- Reject clips over a maximum length (for example 30 s) with a clear error.
- Return an empty text with low confidence for silence, so the UI can say "I did not catch that" instead of asking the LLM.
- Serialise access to the model; two simultaneous requests wait their turn.
- Stream partial results only in phase 2 (WebSocket). Phase 1 returns the final transcript.

## Privacy

Audio is processed in memory and discarded. A debug switch can keep clips for tuning; it is off by default and must be visible in the UI when on.

## Evaluation plan

| Test | Method | Pass line (proposal) |
|---|---|---|
| Accuracy per language | 30 recorded questions per language, scored by word error rate | English at most 10%, Hindi at most 20%, others reported, with a clear "works well / works roughly / not supported" label in the UI |
| Topic terms | 20 science terms said in a sentence | At least 85% recovered after vocabulary hints |
| Latency | 5 s clip, laptop on battery and on power | Final transcript within 1.0 s |
| Noise | Same clips with classroom noise | Reported, not gated |
| Code-mixing | 15 mixed-language sentences | No crash; transcript readable |
| Memory | STT loaded with LLM resident | No out-of-memory; no swap to disk |

## Open questions

- Which languages must meet the pass line on demo day?
- Is a short pre-demo calibration step (read one sentence to set the silence window) acceptable?
- Are student recordings ever allowed to be kept (for example for evaluation)? Default is no.
