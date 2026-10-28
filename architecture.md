# Architecture

How Chanakya is built: the parts, the models they call, how work is scheduled on one laptop, and where data lives.
For what happens step by step when a learner clicks something, see [flow.md](flow.md).

---

## 1. The big picture

```
                        ┌──────────────────────────── one laptop, no internet ────────────────────────────┐
                        │                                                                                   │
 Browser (React + Vite) │   FastAPI backend (Python 3.12, uvicorn, port 8000)          Ollama (port 11434)  │
 ┌───────────────────┐  │   ┌───────────────────────────────────────────────────┐     ┌──────────────────┐ │
 │ Home / Lesson /   │──┼──►│ main.py: REST API, serves web/dist and /media      │     │ qwen2.5:7b (LLM) │ │
 │ Library / Studio  │◄─┼───│ jobs.py: background job queues (poll /api/jobs/id) │────►│ llava:7b (photos)│ │
 │ Remotion <Player> │  │   │ pipeline.py: plan → check → translate → narrate    │     │ nomic-embed-text │ │
 │ Learnverse (3D)   │  │   │ in-process models: IndicTrans2/NLLB, Piper,        │     └──────────────────┘ │
 └───────────────────┘  │   │   Indic-TTS, Parler, faster-whisper, e5, reranker  │                          │
                        │   └───────────────────────────────────────────────────┘                          │
                        │        │ files: media/ (lessons, audio, mp4, papers), data/ (knowledge base)      │
                        │        ▼                                                                          │
                        │   Node: web/render.mjs (Remotion + headless Chrome + ffmpeg) for MP4 export       │
                        └───────────────────────────────────────────────────────────────────────────────────┘
```

**The one rule that shapes everything:** a model only ever returns *data*. The planner writes a JSON lesson that is validated against
a schema (`schema.py`); it picks one of 11 scene templates and fills in text. Our own code (React/Remotion templates) draws, times and
renders every frame. Nothing a model writes is ever executed.

---

## 2. Components

| Component | Where | Role |
|---|---|---|
| Web app | `web/src/` (React 18, TypeScript, Vite 6) | Home (prompt, languages, Flash/Pro), Lesson page (player, tutor, study tools, take-away), Library, Rewards, Review, Profile, Settings |
| Player | `web/src/remotion/` (Remotion 4) | Draws a timed lesson JSON in the browser: 11 templates, captions, themes, icons, graphs, code |
| Learnverse | `metaverse/` (three.js, in a shadow root) | A walkable 3D world built from a lesson or a topic, with quiz gates, points and a shop |
| Backend API | `backend/app/main.py` (FastAPI) | Every endpoint; serves the built UI (`web/dist`) and generated files (`/media`) |
| Job runner | `backend/app/jobs.py` | Long work runs as a job in a named thread pool; the browser polls `GET /api/jobs/{id}` |
| Lesson pipeline | `pipeline.py`, `planner.py`, `longplan.py`, `streaming.py` | Turns a request into a timed lesson |
| Quality | `content.py`, `director.py`, `review.py`, `facts.py`, `fidelity.py` | Cleans, re-directs, lengthens, fact-checks, checks translations |
| Knowledge | `knowledge.py`, `rag/`, `ocr/`, `memory.py` | Offline Wikipedia + notes index, PDF ingestion and search, what the learner already has |
| Languages | `translate.py`, `tts.py`, `expression.py`, `stt.py`, `languages.py`, `captions.py` | Translation, voices, delivery, speech-to-text, caption timing |
| Learning tools | `chat.py`, `videochat.py`, `studio.py`, `paper.py`, `homework.py`, `teachback.py`, `srs.py`, `rewards.py`, `metaquiz.py`, `metaworld.py` | Tutor, extra videos, study tools, papers, homework, teach-back, review, rewards, worlds |
| Resource control | `resources.py`, `gpu.py`, `resume.py`, `selfcheck.py`, `config.py` | Memory gate, GPU slot, crash resume, readiness check, settings |
| Renderer | `web/render.mjs`, `exporter.py` | MP4 export through Remotion + headless Chrome + bundled ffmpeg |
| Android | `Unlox_Hackethon/` (Kotlin, Compose) | The same product on the phone, with Gemma 4 E2B on device |

---

## 3. Models and who calls them

Everything runs locally. Remote models (`-cloud` / `:cloud` in Ollama) are refused.

| Model | Runtime | Called by | For |
|---|---|---|---|
| **Qwen2.5-7B-Instruct Q4_K_M** | Ollama `/api/chat` (streamed) | `planner.py` (lesson JSON), `longplan.py` (outline, Pro beat sheet), `playlist.py` (course outline), `concepts.py` ("Auto" course size), `director.py` (replace a weak scene), `review.py` (repair code), `facts.py` (judge claims, write corrections), `chat.py` (tutor), `studio.py` (7 study tools), `paper.py` (questions), `homework.py` (read questions, write answers), `metaworld.py` (3D world), `ocr/digest.py` (book notes), `translate.py` (fallback translation, script repair) | All the writing |
| **LLaVA 7B** | Ollama `/api/chat` with images | `vision.py` | Reading photos and pictures inside PDFs (the LLM steps aside while it runs on an 8 GB card) |
| **nomic-embed-text** | Ollama `/api/embed` | `knowledge.py` | Embeddings of the offline knowledge base |
| **multilingual-e5-small** | sentence-transformers (CPU) | `rag/embed.py` | Embeddings of PDF passages |
| **bge-reranker-v2-m3** | transformers | `rag/rerank.py` | Re-ranks retrieved PDF passages |
| **IndicTrans2 dist-200M** / **NLLB-200 600M** | transformers (GPU, CPU fallback) | `translate.py`, `fidelity.py` (back-translation) | English → 8 Indian languages, and back for checking |
| **Piper** voices | piper-tts (CPU, ONNX) | `tts.py` | en, hi, te, ml, mr, bn narration |
| **AI4Bharat Indic-TTS** | ONNX Runtime | `tts.py` | en (Indian), ta, kn, gu, bn, mr |
| **Indic Parler-TTS** | transformers (GPU) | `tts.py` | Fallback voice, takes a tone description |
| **faster-whisper** (medium/small) | CTranslate2 | `stt.py` | Spoken questions to the tutor |
| **Tesseract**, **Unlimited-OCR** | CPU / GPU | `ocr/` | Scanned PDF pages |

`llm.py` wraps Ollama: `stream_chat` streams tokens (progress = tokens so far ÷ expected tokens; `on_text` hears the text as it is
written), `ask_json` adds the schema to the prompt, validates the answer with Pydantic, retries with the error, and reports
progress that never goes backwards. `llm.post` retries when Ollama is busy or restarting.

---

## 4. The lesson data model

```
LessonPlan (schema.py, what the LLM writes)          Lesson (lesson.json, what the player reads)
  title                                               id, concept, plan (English), sources, facts report, review notes
  scenes[]:                                           order: ["en", "hi", ...]
    template  title|bullets|flow|cycle|compare|       languages: { code: Track }
              diagram|quiz|summary|graph|code|network   Track: title, duration_s, translator, tts_engines,
    heading, narration, items[], code[], graph{},              scenes[]: (translated scene) + audio_url, start_s,
    nodes/edges, quiz answer ...                                         duration_s, speech_s, captions[], tone
                                                      pending: languages still being made
                                                      building: true while the Flash preview is playing
```

A scene lasts exactly as long as its narration audio plus 0.5 s (`SCENE_PADDING_S`). The web type mirror is `web/src/types.ts`.

---

## 5. Scheduling on one laptop (8 GB GPU, 15 GB RAM)

Three GPU users (the LLM in Ollama, the translator, the voices) share one card. These pieces keep them from fighting:

| Piece | File | What it does |
|---|---|---|
| Job pools | `jobs.py` | One thread pool per kind: `default` (lessons), `playlist`, `export` (MP4, papers), `upload` (PDF OCR), `studio`, `vision`, `langs`, `homework`. A course never blocks a single lesson; OCR never blocks anything. Job progress never goes backwards |
| GPU slot | `gpu.py` `BigSlot` | One *kind* of big GPU work at a time. Lesson builds hold it **shared** (two episodes of a course overlap; Ollama queues their calls); background OCR (6.7 GB) holds it alone and yields between pages when a lesson is waiting (`should_yield`) |
| Memory gate | `resources.py` | Background work waits while RAM/VRAM is short (`wait_for_headroom`, `has_headroom`); idle models are released after `MODEL_IDLE_S` (`idle_release`); the backend runs at below-normal CPU priority |
| PyTorch cap | `config.limit_torch_vram` | PyTorch may hold only `TORCH_VRAM_FRACTION` of the card, so the LLM is never starved |
| Model locks | `translate.py`, `tts.py` | One generation at a time per translator model and per Piper voice; different languages run side by side |
| CUDA fallback | `config.mark_cuda_broken` | A CUDA out-of-memory error moves the torch models to the CPU and the episode is retried |
| Crash resume | `resume.py` | Jobs are recorded on disk; after a restart, missing languages of saved lessons are made again |

Concurrency knobs: `PLAYLIST_WORKERS` (episodes in flight, 2), `LANG_WORKERS` (languages side by side, 3), `LONGPLAN_WORKERS`
(parts of a long video, 1, because part k must know what parts 1..k-1 contain).

---

## 6. Storage

| Path | Contents |
|---|---|
| `media/lessons/{id}/lesson.json` | The lesson (atomic write: temp file, then rename, so a poller never reads half a file), `captions_{lang}.srt`, MP4 exports |
| `media/audio/*.wav` | Narration clips, named by a hash of text + voice + tone (a cache: the same sentence is never voiced twice) |
| `media/translation_cache.json` | Every translated string per language |
| `media/playlists/{id}/playlist.json` | Courses: episodes, status, what each taught |
| `media/papers/{id}.json` | Worksheets and question papers |
| `media/uploads/`, `media/images/` | PDFs (by sha), their passages, notes and figures; photos and their llava readings |
| `data/kb/` | Offline knowledge base (FAISS index + chunks from Simple English Wikipedia and `data/kb_extra/` notes) |
| `media/jobs.db`, `media/learning.db` (SQLite) | Jobs for crash resume (`resume.py`); spaced-repetition reviews and weak spots (`srs.py`) |
| `chunks.sqlite` per upload (`rag/store.py`) | The passage store of an uploaded PDF |
| `models/` | Translator, voices, OCR models (not in git) |

---

## 7. Safety and quality boundaries

- **Schema first**: every model answer is parsed and validated; bad answers are retried with the error; a fallback lesson means a job never ends empty.
- **Grounded**: the planner and the fact checker read retrieved passages; sources are listed with each lesson.
- **Fact checker** (`facts.py`): arithmetic and canonical lists by calculation; statements against passages with a quoted proof; a correction must pass the same check.
- **Safe translation** (`fidelity.py`): script check and back-translation; a failure keeps English rather than showing a bad translation.
- **No code runs**: code scenes are text; Python is only parse-checked.
- **Offline**: `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` are set by the app; `CHANAKYA_ONLINE=1` only for download scripts.
- **Privacy**: everything stays on the machine.

---

## 8. Front end structure

| Path | What |
|---|---|
| `web/src/App.tsx` | Routing between pages, the current lesson/playlist, job polling |
| `web/src/pages/` | `Home`, `Dashboard`, `LessonPage`, `HomeworkPage`, `Library`, `RewardsPage`, `ProgressPage`, `ReviewPage`, `ProfilePage`, `SettingsPage` |
| `web/src/components/` | `ChatPanel` (tutor), `TakeAway` + `PaperReady` (downloads, papers), `Pending` (build progress), `PdfUpload`, `MetaverseLayer` + `TunnelTransition` + `MetaverseStart` (Learnverse entrance), `VideoCard` |
| `web/src/studio/` | Study-tool buttons, modal and viewers (flashcards, quiz, mind map, guide, FAQ, glossary, timeline) |
| `web/src/remotion/` | `Lesson.tsx` (`LessonVideo`), one component per template, graph and code renderers |
| `web/src/api.ts` | `api()` (POST/GET), `runJob()` (poll a job until done), `url()` (backend address, configurable) |

Progress bars glide toward the backend's real value and never run ahead of it (`useSteadyProgress`, `useSmoothProgress`).
