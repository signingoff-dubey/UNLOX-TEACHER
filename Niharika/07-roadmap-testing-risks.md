# 07. Roadmap, tests, risks, open questions

Effort figures are rough, for one developer working on the existing code, and exclude waiting for model downloads.

## Milestones

Each milestone ships something usable and can be demoed on its own. Do them in order.

### M0. Spikes (about 1 to 2 days)

| Spike | Output |
|---|---|
| STT bake-off | Word error rate and latency per language per engine; chosen engine per language |
| LTX feasibility | Numbers and sample clips from `06-ltx-live-demo.md`; go or no-go for Tier 2 |
| Memory budget | Measured VRAM and RAM with the LLM, STT, reranker and a Parler voice resident together |
| LAN microphone | Confirm the HTTPS option works on the second device, or decide on localhost only |

Gate: do not start M3 or M5 before their spikes report.

### M1. Grounded text chat (about 3 days)

- Chat session and streaming message endpoint (SSE), cancel endpoint.
- Context builder: lesson, current scene, retrieval via `rag/`, short history.
- Chat panel in `web/` with transcript, source chips, "explain this scene" shortcut, current scene pushed with each message.
- `keep_alive` policy: model stays loaded while a session is open, unloads after an idle timeout.
- Health report gains a `chat` section.

Acceptance: groundedness and follow-up tests in `05-topic-knowledge.md`; first token under 1.5 s; no regression in lesson generation time.

### M2. Talkback (about 3 days)

- Sentence streaming from the LLM into TTS; per-sentence audio served to the browser.
- Playback queue, stop button, speaker toggle, speed control.
- Speech-friendly text normalisation for English and Hindi first.
- Languages: Piper set first; Parler languages with text-first display.

Acceptance: latency and intelligibility tests in `04-talkback-tts.md` for English and Hindi.

### M3. Push-to-talk (about 3 days, after the STT spike)

- `/api/stt` and the chosen engine behind one interface.
- Browser capture to 16 kHz mono, hold-to-talk button, level meter, clear errors.
- Vocabulary hints from the lesson.

Acceptance: accuracy and latency tests in `03-speech-to-text.md` for the demo languages.

### M4. Hands-free and interruption (about 4 days)

- On-device voice activity detection, silence window setting.
- Barge-in: stop speech and generation when the student talks.
- WebSocket transport only if M2 and M3 latency misses the budget.
- Echo handling and a headphones recommendation.

Acceptance: barge-in under 300 ms; no self-trigger loops in a 10-minute session on speakers at normal volume.

### M5. Demo clips (about 3 to 6 days)

- Tier 1: LLM returns a demo scene as data; render with existing templates; show inline in chat.
- Tier 2: only if the LTX spike passed. Job, GPU slot, unload and reload, cache, cancel, label.

Acceptance: Tier 1 clip within 15 s for three demo topics; Tier 2 within the spike's measured time with no out-of-memory errors across 10 consecutive runs.

### M6. Polish and demo hardening (about 2 days)

- Status panel entries for STT, voices, demo. Friendly errors for each failure.
- Pre-generate caches for the demo topics.
- Offline check with Wi-Fi off. Written demo script and a fallback if the microphone fails.
- Optional: reuse the chat inside the metaverse stations.

## Test matrix

| Area | Tests | Where defined |
|---|---|---|
| Grounding | Supported claims, unanswerable questions, follow-ups, quiz leakage, safety | `05-topic-knowledge.md` |
| STT | Accuracy per language, topic terms, latency, noise, code-mixing, memory | `03-speech-to-text.md` |
| TTS | First-audio latency, barge-in time, intelligibility, numbers and formulas, long answers | `04-talkback-tts.md` |
| End to end | Speech end to first audio under 3.5 s (Piper languages), five lessons, ten questions each | this file |
| Offline | Full conversation with Wi-Fi off and Hugging Face offline variables set | this file |
| Resource | 30-minute session: no memory growth over 10%, no out-of-memory, no stuck GPU slot | this file |
| Failure | Ollama down, STT model missing, mic denied, voice missing, lesson missing: each shows a clear message and the app keeps working | this file |
| Regression | Lesson generation time and export unchanged with chat idle | this file |

Automated tests (backend): context builder with fake retrieval, segmenter edge cases (Indic punctuation, abbreviations), session cancel, STT interface with a fake engine, TTS queue ordering. The repo already has fakes in `backend/tests/fakes.py` to build on.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| STT accuracy poor for some Indian languages | Medium | High for those languages | Spike first; per-language engine table; label language quality honestly in the UI; typed fallback |
| Parler too slow for conversation | High | Medium | Text first; limit demo languages; short first sentence; pre-rendered acknowledgements |
| 8 GB VRAM exhausted | High | High | Written budget, CPU STT, one big model at a time, unload policy, measure in M0 |
| Chat blocked behind lesson builds | Medium | High | Chat does not use the job queue; urgent priority in the GPU slot |
| Qwen 7B answers badly in Indic languages | High | High | Answer in English then translate (approach B) |
| Hallucinated answers | Medium | High | Context-first prompt, "I do not know" rule, citations, groundedness tests |
| Echo and self-triggering in hands-free | Medium | Medium | Push-to-talk default, echo cancellation, headphones advice |
| Mic blocked on LAN HTTP | High if demoed over LAN | High | Localhost default; documented local HTTPS |
| LTX too slow, too big or misleading | High | Medium | Make it optional; Tier 1 deterministic demo first; spike gates |
| LTX licence prevents intended use | Medium | Medium | Read the model card; record the licence; user downloads weights themselves |
| Scope creep | High | Medium | Ship M1 and M2 as a complete product before M3 to M5 |
| Two retrieval stacks diverge | Medium | Low | Decide on one after M1; keep `knowledge.py` only as fallback |

## Definition of done for the whole feature

1. A student can ask a question by typing or speaking, in at least English and one Indian language, and hear a correct spoken answer that matches the lesson on screen.
2. The answer cites its sources, can be interrupted, and works with Wi-Fi off.
3. The status panel shows whether chat, STT, voices and demo are ready.
4. A demo animation of the current topic can be shown on request, labelled accurately.
5. Lesson generation and export are no slower than before.

## Open questions

Answers shape the plan. The first four block the most work.

1. **Where does the chat live?** The main web app's right column, the metaverse, or both with a shared component?
2. **Demo languages.** English only, English plus Hindi and Telugu, or all nine? This decides STT engines and how much Parler slowness is acceptable.
3. **Single laptop or second device?** A second device over the LAN forces local HTTPS for the microphone.
4. **GPU policy for video.** May a demo clip pause chat for a minute or two while the LLM is unloaded?
5. **"HTTP".** Confirm it meant STT. If it meant serving chat over HTTP, `02-architecture.md` already does that first.
6. **Hands-free required, or is push-to-talk enough for the demo?**
7. **Beyond the lesson.** May the assistant answer outside the lesson and sources, or only from them?
8. **Generated video required, or is a deterministic animation enough?**
9. **Model downloads.** Is a one-time download of an STT model (hundreds of MB to a few GB) and, if approved, an LTX model (several GB) acceptable during setup?
10. **Teacher mode.** Should the assistant also quiz the student, or only answer questions?
11. **Recordings.** Are student recordings ever kept? Default: no.

## What to do next

1. Answer the open questions above, especially 1 to 4.
2. Run M0 spikes. They are cheap and remove the biggest unknowns (STT per language, LTX, memory).
3. Revise the documents with the measurements, then start M1.
