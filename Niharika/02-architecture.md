# 02. Architecture

## One conversation turn

```
 student speaks ──► mic capture (browser) ──► voice activity detection
                                                   │ end of speech
                                                   ▼
                                             STT (backend)  ──► text + detected language
                                                   │
          current lesson, scene index, language ───┤
                                                   ▼
                                   context builder (lesson JSON + retrieval + history)
                                                   │
                                                   ▼
                                  LLM via Ollama, streaming tokens
                                                   │ sentence boundary
                                                   ▼
                          (optional) translate sentence ──► TTS for that sentence
                                                   │
                       text appears ◄──────────────┤──────────────► audio chunks queue in browser
                                                   │
                                  student speaks again ──► cancel LLM, TTS and playback (barge-in)
```

The loop is **sentence-pipelined**: the first sentence is spoken while the rest is still being written. That is what makes it feel like a conversation instead of a form.

## Components

| Component | Where | Notes |
|---|---|---|
| Chat router | new `backend/app/chat/` package | Sessions, message streaming, cancel. Not built on `jobs.py` |
| Context builder | `backend/app/chat/context.py` | Lesson track, current scene, retrieval hits, recent turns. See `05-topic-knowledge.md` |
| STT service | `backend/app/stt.py` | Loads one model lazily, transcribes a clip or a stream. See `03-speech-to-text.md` |
| Streaming TTS | extend `backend/app/tts.py` | Sentence in, audio chunks out, cancellable. See `04-talkback-tts.md` |
| Sentence segmenter | reuse `split_sentences` in `tts.py` | Already handles `. ! ? । ॥` |
| GPU arbitration | extend `backend/app/gpu.py` | New owners: `chat`, `stt`, `demo`. See "GPU budget" |
| Demo clips | `backend/app/demo/` | Optional. Job-based. See `06-ltx-live-demo.md` |
| Chat panel | `web/src/components/Chat.tsx` | Right-hand panel: transcript, mic button, speaker controls, source chips, demo player |
| Audio I/O | `web/src/audio/` | Mic capture to 16 kHz mono, playback queue, echo handling |

## API contract (proposed)

Names are proposals. Everything is JSON unless stated. Errors use the existing `{detail}` shape.

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/chat/sessions` | `{lesson_id, lang}` | `{session_id}` |
| POST | `/api/chat/{session_id}/messages` | `{text, scene_index, lang, speak: bool}` | **Server-sent events**: `token`, `sentence` (text plus optional `audio_url`), `source`, `demo_offer`, `done`, `error` |
| POST | `/api/chat/{session_id}/cancel` | none | `{ok}`. Stops generation and synthesis |
| POST | `/api/stt` | audio body (WAV or WebM), query `lang` hint | `{text, lang, confidence, duration_s}` |
| POST | `/api/tts` | `{text, lang}` | WAV bytes, cached by content hash |
| WS | `/api/voice/{session_id}` | binary audio frames up; JSON control messages | binary audio frames and JSON events down (phase 2) |
| POST | `/api/chat/{session_id}/demo` | `{prompt?, scene_index}` | Job (reuse `/api/jobs/{id}`); result `{url}` under `/media/demos/` |
| GET | `/api/health` | none | Add `stt`, `chat`, `demo` sections so the status panel shows readiness |

### Why SSE first, WebSocket second

| | HTTP + SSE | WebSocket |
|---|---|---|
| Fits FastAPI and the existing proxy | Yes, no new dependency | Yes, small addition |
| Browser support, debuggability | Excellent, visible in dev tools | Good |
| Duplex audio (talk while it talks) | Needs a second request for audio | Natural |
| Barge-in | Cancel request works | Cancel message works |
| Risk | Low | Medium (reconnects, framing) |

Phase 1 uses HTTP: push-to-talk uploads a clip to `/api/stt`, the answer streams back over SSE, audio arrives as short WAV files fetched per sentence. Phase 2 adds the WebSocket for hands-free mode if latency tests demand it.

## Latency budget (target for the demo laptop)

"Speech ends" to "first audio plays" is the number users feel.

| Step | Target | Notes |
|---|---|---|
| End-of-speech detection | 0.4 to 0.7 s | Silence window; tune per environment |
| STT | 0.3 to 1.0 s | Short questions, small or distilled model |
| Retrieval | 0.05 to 0.3 s | `rag/` hybrid search plus reranker; reranker is the larger share |
| LLM time to first sentence | 0.8 to 1.5 s | Model already loaded; first sentence kept short by prompt |
| TTS first sentence | 0.2 s (Piper) to 3 s or more (Parler) | The big variable |
| **Total** | **about 2 to 3.5 s with Piper** | Parler languages will be slower; show text immediately and say so |

If the budget is missed, the first mitigation is showing text before audio. The second is a short spoken acknowledgement while the real answer is prepared.

## GPU and memory budget (8 GB VRAM, 31.5 GB RAM)

Sizes are approximate and must be measured in the spike. They are here to show why one-big-model-at-a-time matters.

| Model | Runs on | Approx. memory | Resident during chat? |
|---|---|---|---|
| Qwen2.5 7B Q4 (Ollama) | GPU | about 5 GB | **Yes**, `keep_alive` raised while a chat session is open |
| Piper voices | CPU | small | Yes |
| STT (small or medium Whisper-class) | CPU or GPU | 0.5 to 3 GB | Yes, on CPU if VRAM is tight |
| Embeddings (`multilingual-e5-small`) | CPU | about 0.5 GB RAM | Yes |
| Reranker (`bge-reranker-v2-m3`) | GPU fp16 or CPU | about 1 to 1.2 GB | Yes, or CPU |
| NLLB 600M | GPU | about 1.2 GB | Only when translating |
| Indic Parler-TTS | GPU | a few GB | Only for kn, ta, bn, gu answers |
| Unlimited-OCR | GPU | 6.7 GB | Never during chat |
| LTX video model | GPU plus offload | see `06-ltx-live-demo.md` | Never alongside the LLM |

### Priority policy (proposal)

1. **Chat turn** (urgent): may preempt anything except a model mid-forward-pass.
2. **Lesson planning** (urgent, existing).
3. **STT** (short, runs on CPU when possible, so it rarely needs the slot).
4. **Demo clip** (long): takes the slot, unloads the chat LLM first, and the UI says "Chat is paused while the demo renders."
5. **OCR** (background): already yields on urgent requests.

Needs a decision: see Open question 4 in `07-roadmap-testing-risks.md`.

## Session model

A session binds: lesson id, active language, conversation history (bounded), and the current scene index sent by the player with every message. Sessions live in memory with an idle timeout. Nothing is written to disk by default; a "save transcript" option can come later.

## Security and privacy

- Audio stays on the machine. It is not stored unless a debug flag is on.
- No new outbound network calls. Model downloads happen once, during setup, like the existing models.
- CORS is currently `*` for demo convenience. If the assistant is exposed over the LAN, restrict origins and add a simple per-session token.
- Chat input is untrusted text. It goes into the prompt as user content only, never into file paths or shell calls.

## Microphone and HTTPS

`getUserMedia` works on `http://localhost` and on HTTPS. It does not work on `http://<lan-address>`. Options:

| Option | Effort | Trade-off |
|---|---|---|
| Demo only on the laptop via `localhost` | none | Simplest; no second device |
| Local HTTPS with a locally generated certificate (for example `mkcert`) | small | Each device must trust the certificate |
| Reverse proxy with a self-signed certificate | small | Browser warning on first visit |

Recommendation: ship "use localhost" as the default and document local HTTPS as an option.
