# 01. Current state of the codebase

Audit of `main` at `de42195`. Source of truth is the repo; file names are given so each claim can be checked.

## What the app does today

Concept in, narrated animated lesson out. A lesson build runs as one background job:
retrieve facts, plan with a local LLM, translate, synthesize narration per scene, return timed lesson JSON. The browser plays it with Remotion; the backend exports MP4.

## Backend inventory

| Area | File | What exists | Relevance to a voice assistant |
|---|---|---|---|
| API | `backend/app/main.py` | FastAPI. Health, languages, create lesson (job), job status, lesson list and fetch, export (job), knowledge search, static media and the built UI | No chat, STT or TTS endpoints. CORS is open. No WebSocket |
| LLM | `backend/app/planner.py` | Ollama at `127.0.0.1:11434`, model `qwen2.5:7b-instruct-q4_K_M`. Planner call is non-streaming, uses a JSON schema, sets `keep_alive` to `0` so the model unloads after planning. A plain `ollama_generate` helper exists | Chat needs streaming and a model that stays loaded during a conversation. `keep_alive=0` works against that |
| Retrieval (legacy) | `backend/app/knowledge.py` | Ollama `nomic-embed-text`, cosine search over `data/kb`, title boost, per-article dedupe. Used by the planner. Endpoint `GET /api/knowledge/search` | Works today. English-centric |
| Retrieval (new) | `backend/app/rag/` | Hybrid search: SQLite FTS5 plus FAISS, merged by rank fusion, reranked by `bge-reranker-v2-m3`. Embeddings by `multilingual-e5-small` on CPU. Scopes: `library`, `upload:<sha>`, `both:<sha>` | **Not imported by any app module.** Multilingual, so an Indic question can find an English passage. Best fit for chat |
| OCR | `backend/app/ocr/` | Page triage, Tesseract, Unlimited-OCR on GPU, arbiter | Feeds uploaded PDFs into `rag/`. Not needed for chat directly |
| TTS | `backend/app/tts.py` | `synthesize(text, lang)` returns a cached WAV and its duration. Engines: Piper (CPU, fast), Indic Parler-TTS (GPU), silent placeholder. Parler is run one sentence at a time. Chain: main engine, fallback engine, silence | Batch only: it writes a whole file per call. No streaming, no cancel. Reusable as the engine layer |
| Languages | `backend/app/languages.py` | `en hi te ml mr kn ta bn gu`. Piper voices exist for `en hi te ml mr`. `kn ta bn gu` rely on Parler | Voice quality and latency differ a lot by language |
| Translation | `backend/app/translate.py` | NLLB-200 600M on GPU (default). IndicTrans2 optional and gated | Needed if the LLM answers in English and the student asked in an Indian language |
| GPU scheduling | `backend/app/gpu.py` | `big_slot`: one large GPU model at a time (OCR versus planner), urgent requests jump the queue | Natural place to arbitrate chat LLM versus video model |
| Jobs | `backend/app/jobs.py` | In-process queue with **one worker**, polled by the UI | Wrong tool for chat. Fine for long jobs like a video clip |
| Lesson data | `backend/app/pipeline.py` | Lesson JSON: per-language track, scenes with narration, items, captions, audio URL; `sources` list; timings | This is the topic context the assistant should read |
| Config | `backend/app/config.py`, `.env.example` | Env-driven settings. `PRELOAD`, `OLLAMA_KEEP_ALIVE`, `RAG_*`, `TTS_*`, `DEVICE` | New settings go here |
| Start-up | `start.ps1`, `setup.ps1` | Windows scripts. `-Lan` exposes the server on the network | LAN mode is HTTP, which blocks the microphone in browsers |

## Frontend inventory

| Area | File | State |
|---|---|---|
| Main app | `web/src/App.tsx` | Left panel (concept, languages, status, history) and a stage (player, scene list, actions). **No chat panel** |
| API client | `web/src/api.ts` | `fetch` wrapper, job polling, configurable backend address. No streaming helper, no audio helper |
| Player | `web/src/remotion/` | Remotion templates driven by lesson JSON. Scene index is tracked in `App.tsx` (`sceneIndex`) |
| Metaverse | `metaverse/` | 3D walkable world with stations, quizzes, shop. Reads a lesson. **No chat** |
| Chat mockups | `frontend/visual-teacher-flow.html` (untracked), Figma file "Visual Teacher – Screen Flow" | Three-column lesson screen: notes left, blackboard video centre, chat right with canned replies and a "Raise hand" button |

## Gap analysis

| Needed for a voice assistant | Have | Gap |
|---|---|---|
| Chat endpoint with streaming | No | New route, streaming from Ollama, session state |
| Lesson-aware prompt | Lesson JSON exists | Context assembly, current-scene pointer from the player |
| Retrieval for questions | `knowledge.py` (wired), `rag/` (unwired) | Wire `rag/` to chat; decide what happens to `knowledge.py` |
| Answer in Indian languages | NLLB translation, Piper/Parler voices | Decide answer path: LLM in target language versus English answer then translate |
| STT | None | Model choice, endpoint, browser capture, voice activity detection |
| Streaming TTS | Batch TTS only | Sentence-level streaming synth, cancel, playback queue in the browser |
| Interruption (barge-in) | None | Cancel generation and playback when the student speaks |
| Mic over LAN | HTTP only | Local HTTPS option, or document "use localhost" |
| GPU sharing | `big_slot` | Add owners for chat, STT and video; change `keep_alive` policy |
| Chat UI | Mockups only | Real component in `web/` (and optionally in `metaverse/`) |
| Demo animation | None | See `06-ltx-live-demo.md` |
| Tests | Backend tests for OCR and RAG | Conversation, STT accuracy, latency and grounding tests |

## Things that will bite if ignored

1. **Single-worker job queue.** Do not route chat through `jobs.py`. A chat turn would wait behind lesson builds and exports.
2. **`keep_alive=0`.** The planner deliberately unloads the LLM to free VRAM for TTS. For chat the model must stay loaded between turns, which competes with Parler, OCR and any video model for 8 GB.
3. **One 8 GB card.** Qwen 7B (4-bit), Parler, NLLB, an STT model and a video model cannot all be resident. A written budget is in `02-architecture.md`.
4. **Retrieval is split across two stacks** with different embedding models. Using both would double memory and confuse tuning. Pick one for chat.
5. **Qwen 7B is weak in Telugu and mixes scripts in Hindi** (noted in the README's verification section). Direct Indic answers from it will be poor.
6. **Piper has no Kannada, Tamil, Bengali or Gujarati voice.** Spoken answers in those languages go through Parler, which is slow per sentence.
7. **Browser microphone rules.** `getUserMedia` needs a secure context. `localhost` is fine; `http://192.168.x.x` is not.
