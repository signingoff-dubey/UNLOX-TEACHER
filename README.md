# Chanakya

> Type a topic, attach a photo or a PDF, and get a narrated, animated video lesson in English and eight Indian languages, with quizzes, study tools and a tutor. Everything runs offline on one laptop (and on a phone). No outside AI service is ever called.

**Latest release: v0.16.0** · Built for the Unlox hackathon · Repo: https://github.com/signingoff-dubey/UNLOX-TEACHER

| | |
|---|---|
| **Team name** | The Last Commit |
| **Members** | Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty |
| **College** | RV University, Bengaluru |
| **Course** | B.Tech (Hons) |
| **Branch** | Computer Science Engineering |
| **Year of study** | 2nd year |

```
topic / photo / PDF
   │
   ├─► memory of what the learner already has ─┐
   ├─► offline knowledge base (Wikipedia + notes + your PDFs) ─┤
   ▼                                           ▼
 local LLM (Ollama) ──► lesson JSON (data only) ──► director ──► reviewer/writer ──► fact checker
                                                                                    │
 9 languages: NLLB / IndicTrans2 ◄──────────────────────────────────────────────────┘
        │
        ▼
 Piper / Indic-TTS / Parler voices (timed per sentence) ──► timed lesson ──► browser player (Remotion)
                                                                          └► MP4 export (headless Chrome + ffmpeg)
```

**The rule that shapes everything:** the AI only ever returns *data* (a JSON lesson that is checked against a schema). It picks one of 11 scene templates and fills in text; our own code draws, times and renders every frame. Nothing the model writes is ever executed.

---

## Contents

1. [Features](#features)
2. [Flash and Pro](#flash-and-pro)
3. [How a lesson is made](#how-a-lesson-is-made)
4. [Models used](#models-used)
5. [Languages and voices](#languages-and-voices)
6. [Tech stack](#tech-stack)
7. [Quick start](#quick-start)
8. [Configuration](#configuration)
9. [API](#api)
10. [Project layout](#project-layout)
11. [Quality, safety and fact checking](#quality-safety-and-fact-checking)
12. [Android app](#android-app)
13. [Testing](#testing)
14. [Performance and hardware](#performance-and-hardware)
15. [Known limits](#known-limits)
16. [Licences](#licences)
17. [Docs and team](#docs-and-team)
18. [Changelog](#changelog)

---

## Features

### Make a lesson
- **Any topic, any length from 30 s to 4 min.** Longer videos are written in parts; a course is 1 to 3 videos, and "Auto" lets the AI decide how many concepts a topic has.
- **11 scene templates:** `title`, `bullets`, `flow`, `cycle`, `compare`, `diagram`, `quiz`, `summary`, `graph` (11 curve types: line, parabola, cubic, sine, cosine, exp, abs, sqrt, reciprocal, circle, ellipse, plus points, segments, tangents and chords), `code` (syntax-coloured, a highlight that follows the narration, program output), and `network` (boxes and arrows laid out automatically: trees, linked structures, pipelines, architectures).
- **Modes:** Explanation, Study (key terms, memory tricks, a recall quiz), Homework (teaches the method, writes the answers into a separate file you open in the browser) and Revise (re-teaches what you keep getting wrong).
- **Level:** Beginner or Intermediate. The learner's age (Profile) shapes the wording.
- **Photos:** attach a photo of a page, a board or a worksheet; a local vision model reads it. The Create button never waits for it: the photo is read inside the job.
- **PDFs up to 2 GB / 1,000 pages:** a chapter ("chapter 4"), a page range ("pages 120 to 135") or the whole book. Text-layer pages are read as Markdown (headings, lists, tables kept), scans go through OCR, pictures inside the PDF are described by the vision model, and study notes are written while the book is read. Citations such as `Source: Science 8, Chapter 2, pp. 41-44` appear in the recap.
- **Ask in your own words:** "teach me about the solar system" becomes the title "The solar system"; "how does the rainbow have 7 colours, why does it come only when sunlight and rain are together" is answered as two questions.
- **Memory:** the planner is told which related videos you already have and does not repeat them.
- **Reference notes you can add:** drop `.md`/`.txt` files in `data/kb_extra/` (this repo ships notes on data structures and AVL trees, MERN, coordinate geometry and Python) and rebuild the index.

### Watch and study
- **Player** with scene list, captions timed to the audio, language tabs, auto-advance to the next video of a course, and early playback (Flash starts about 6 to 18 s after you ask).
- **Tutor chat** (text or voice) that knows the lesson. Say "generate one more video on ..." and it builds one, shows its first frame in the chat and adds it to the playlist.
- **Study tools** written from the lesson in your languages: flashcards, quiz, mind map, study guide, FAQ, glossary, timeline.
- **Review** (spaced repetition of what you got wrong), **Teach it back** (explain it and be graded), **Rewards** (streak, score, level, daily goal, badges), **Progress**, **Profile**.
- **Learnverse:** a walkable 3D world (three.js) the local model builds from your topic or from everything you studied, with quiz gates, points and a shop.

### Take it away
- MP4 export (720p or 1080p, H.264 + AAC), `.srt` captions per language, narration-only audio, the whole lesson as one `.chanakya.zip` with its own player (copy it to a USB stick, import it in Library), worksheets and question papers (HTML).
- Backend address is configurable, so the UI can use a backend on another laptop.

### Built to keep working
- Jobs resume after a crash; GPU out-of-memory falls back to the CPU and retries the episode; a memory gate waits when the laptop is short of RAM or VRAM; the PyTorch allocator is capped so the language model is never starved.
- Translation is checked for script and meaning (back-translation); a bad translation is replaced by English rather than shown.
- `GET /api/ready` and a start-up self-check say exactly what is missing and what to run.

---

## Flash and Pro

Pick it on the Home page (the "Build" switch) or send `"quality": "flash" | "pro"`. Both use the same model.

| | Flash | Pro |
|---|---|---|
| Idea | Scenes appear within seconds and flow into each other while the rest is still being written | The whole video is planned first; nothing is shown until it is complete |
| How | A short outline, then parts of about 40 s written one after the other, each told what the earlier parts taught; the first scenes stream to the player token by token | A scene-by-scene outline of the whole video first (`longplan.beat_sheet`); the first minute is written in one call; each further minute is patched on in a call that sees the whole outline and the full text so far (`plan_pro`) |
| Fact check | 50 s budget | 100 s budget |
| Measured ("teach me what avl trees are", 2 min) | 133 s, first scenes after 18 s | 167 s, shown at the end; covers balance factor, single and double rotation, insertion, deletion and uses |
| Choose it when | You want to start watching now | You want the most coherent video and can wait |

---

## How a lesson is made

1. **Clean the request** (`content.clean_topic`): "Teach me about dsa in java" is "DSA in Java". Questions are left as they are. A request with two questions must be answered twice.
2. **Remember** (`memory.py`): related lessons you already have are summarised for the planner.
3. **Retrieve** (`knowledge.py`, `rag/`): top passages from the offline knowledge base, your PDF first if you attached one.
4. **Plan** (`planner.py`): a prompt built for the subject (maths gets graph scenes, programming gets code scenes in the language you named, trees and structures get network scenes); Flash or Pro as above. The reply is parsed and repaired by `schema.normalize` (small models slip on types) and sent back with feedback if it repeats headings or code, has narration under 18 words, ignores a question, shows a technical topic only as text, or leans on everyday comparisons.
5. **Clean** (`content.py`): repeated scenes, headings and openings are dropped, one summary is kept, empty title cards removed, repeated everyday comparisons stripped.
6. **Direct** (`director.py`): a visual director replaces weak scene choices (a list that should be a flow, a graph with nothing to draw).
7. **Review** (`review.py`): a writer pass lengthens short narration; Python snippets are parse-checked and repaired.
8. **Fact check** (`facts.py`): see below.
9. **Translate** (`translate.py`): batched by length, cached, pre-translated while the planner is still writing.
10. **Narrate** (`tts.py`, `expression.py`): each sentence is spoken with the delivery that fits it; each scene lasts exactly as long as its audio plus 0.5 s.
11. **Show**: the Remotion player draws the timed JSON in the browser, or the renderer exports an MP4.

---

## Models used

Everything below runs locally. Nothing is called over the internet at run time, and models whose name ends in `-cloud`/`:cloud` (remote servers) are refused.

| Role | Model | Runs on | Notes |
|---|---|---|---|
| Planner, director, writer, fact checker, tutor, study tools, Learnverse builder | **Qwen2.5-7B-Instruct** Q4_K_M (`qwen2.5:7b-instruct-q4_K_M`) through **Ollama** | GPU (5.5 GB, 100 % resident), about 43 tokens/s | Apache-2.0. Context 6144 tokens. Same model for Flash and Pro |
| Photo reader, pictures inside PDFs | **LLaVA 7B** (`llava:7b`) | GPU, loaded only when needed | The language model steps aside while it runs |
| Knowledge-base embeddings | **nomic-embed-text** (Ollama) | CPU/GPU | 768 dimensions |
| PDF passage embeddings | **multilingual-e5-small** (sentence-transformers) | CPU | |
| Re-ranking | **bge-reranker-v2-m3** | CPU/GPU | Re-ranks retrieved passages (PDF search) |
| Translation | **NLLB-200 distilled 600M** (default), **AI4Bharat IndicTrans2 dist-200M** (optional, gated), Ollama as a fallback | GPU, released after 10 idle minutes | Back-translation check |
| Narration | **Piper** voices (en, hi, te, ml, mr, bn), **AI4Bharat Indic-TTS** int8 ONNX (en, ta, kn, gu, plus bn/mr), **Indic Parler-TTS** (GPU fallback, takes a tone description) | CPU (Piper, Indic-TTS), GPU (Parler) | `expression.py` sets per-sentence speed, pauses and emphasis |
| Speech to text | **faster-whisper** (`STT_MODEL`, default medium; small is bundled) | GPU if 2.2 GB is free, else CPU | Loaded on the first spoken question, cached |
| Scanned pages | **Tesseract** (fast) then **Unlimited-OCR** (accurate, when the GPU is idle) | CPU / GPU | Gives way to lessons |
| Phone | **Gemma 4 E2B** (LiteRT-LM), **Piper** via sherpa-onnx, **Whisper base** and **Vosk**, **ML Kit** translation and OCR | On the phone | See [Android app](#android-app) |


---

## Languages and voices

Nine languages. English is always available; the lesson is sized for the slowest voice you pick.

| Language | Code | Translation | Voice engine | Speed (words/s) |
|---|---|---|---|---|
| English | `en` | none | Piper `en_US-lessac` / `en_GB-alan`, Indic-TTS | 2.7 |
| Hindi | `hi` | NLLB / IndicTrans2 | Piper `hi_IN-priyamvada`, `hi_IN-pratham` | 1.9 |
| Marathi | `mr` | NLLB / IndicTrans2 | Piper `mr_IN-google`, Indic-TTS | 1.8 |
| Bengali | `bn` | NLLB / IndicTrans2 | Piper `bn_BD-google`, Indic-TTS | 1.8 |
| Gujarati | `gu` | NLLB / IndicTrans2 | Indic-TTS, Parler | 1.8 |
| Tamil | `ta` | NLLB / IndicTrans2 | Indic-TTS, Parler | 1.7 |
| Kannada | `kn` | NLLB / IndicTrans2 | Indic-TTS, Parler | 1.7 |
| Telugu | `te` | NLLB / IndicTrans2 | Piper `te_IN-padmavathi`, `te_IN-venkatesh` | 1.6 |
| Malayalam | `ml` | NLLB / IndicTrans2 | Piper `ml_IN-meera` | 1.6 |

Fonts: Noto Sans for every script (SIL OFL), bundled so the browser and the renderer draw Devanagari, Telugu, Tamil and the rest correctly, including conjuncts. If a voice is missing the next engine is tried, and finally silent audio with correct timing.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language model runtime | Ollama (local), Qwen2.5-7B, LLaVA, nomic-embed-text |
| Backend | Python 3.12, FastAPI 0.115, Uvicorn, Pydantic 2 (schema and validation), `requests`, SQLite (jobs, learning data, passage store) |
| ML | PyTorch (CUDA 12.8 wheels for RTX 50-series), Transformers 4.57, sentence-transformers, FAISS, ONNX Runtime, piper-tts, faster-whisper, NLLB-200, IndicTrans2 |
| Documents | PyMuPDF + pymupdf4llm (PDF to Markdown), Tesseract (pytesseract), Unlimited-OCR, Pillow |
| Frontend | React 18, TypeScript 5.8, Vite 6, Remotion 4.0.539 (player and scene templates), three.js (Learnverse), Mermaid 11 (mind maps), Figtree and Chakra Petch fonts |
| Video export | Remotion renderer (headless Chrome) + bundled ffmpeg, Node 20+ |
| Android | Kotlin, Jetpack Compose (Material 3), Room, WorkManager, Media3, LiteRT-LM (Gemma), sherpa-onnx, Vosk, ML Kit; min SDK 31 |
| 3D lessons (teammate) | Headless Blender pipeline in `blender 3d/` |
| Tests | pytest (345 backend tests), `tsc --noEmit` for the web app |

---

## Quick start

Windows, PowerShell. You also need **Ollama** (https://ollama.com).

```powershell
git clone https://github.com/signingoff-dubey/UNLOX-TEACHER.git
cd UNLOX-TEACHER
.\setup.ps1 -Gpu      # once, online. Leave out -Gpu for CPU only (Piper voices + Ollama translation)
.\start.ps1           # opens http://127.0.0.1:8000  (add -Lan for other devices)
```

Manual setup of the backend (Python 3.12):

```powershell
cd backend
py -V:3.12 -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128   # GPU
.\venv\Scripts\pip install -r requirements-ml.txt -r requirements-rag.txt
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull nomic-embed-text
ollama pull llava:7b                                        # photos and pictures in PDFs
.\venv\Scripts\python scripts\download_models.py [--ml]     # voices, fonts, models still missing
.\venv\Scripts\python scripts\build_knowledge.py            # the offline knowledge base (online once); later: --no-fetch
cd ..\web ; npm install ; npm run bundle ; npm run build    # UI + video renderer
cd ..\backend ; .\run.ps1
```

Then open http://127.0.0.1:8000 and check **http://127.0.0.1:8000/api/ready**, which lists what is missing and the command that fixes it.

Before a demo: set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, turn Wi-Fi off, and make one lesson end to end. Development: run the backend, then `cd web; npm run dev` (UI on :5173, proxied to :8000); `npm run studio` previews every template without the backend; `LLM_BACKEND=mock` runs the pipeline without Ollama.

---

## Configuration

Set in `backend/.env` (copy `.env.example`) or the environment. Common ones:

| Variable | Default | Meaning |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | The language model (must be in `ollama list`) |
| `VISION_MODEL` | `llava:7b` | Reads photos and PDF pictures |
| `EMBED_MODEL` | `nomic-embed-text` | Knowledge-base embeddings |
| `OLLAMA_NUM_CTX` | `6144` | Context window; the same for every call (changing it reloads the model) |
| `LLM_RETRIES` | `2` | Extra tries when Ollama is busy or restarting |
| `RAG_ENABLED`, `RAG_TOP_K`, `RAG_MIN_SCORE` | `1`, `6`, `0.68` | Retrieval |
| `FACTCHECK`, `FACTCHECK_BUDGET_S` | `1`, `50` | The fact checker and its time budget (Pro doubles it) |
| `TRANSLATE_BACKEND` | `nllb` | `nllb`, `indictrans2`, `ollama`, `none` |
| `BACKCHECK` | `1` | Translate back to English and compare |
| `TTS_ENGINE`, `TTS_FALLBACK`, `TTS_EXPRESSIVE` | `piper`, `parler`, `1` | Voices and expressive delivery |
| `STT_MODEL`, `PRELOAD_STT` | `medium`, `0` | Speech recognition |
| `DEVICE`, `OLLAMA_NUM_GPU` | `auto` | GPU/CPU choice |
| `TORCH_VRAM_FRACTION` | `0.35` | Share of the card PyTorch may hold |
| `MIN_FREE_RAM_GB`, `MIN_FREE_VRAM_GB`, `MODEL_IDLE_S` | `1.5`, `0.8`, `600` | The resource gate |
| `PDF_FIGURES`, `PDF_MAX_FIGURES` | `1`, `40` | Describe pictures inside PDFs |
| `PUBLIC_BASE_URL`, `CORS_ORIGINS`, `NODE_BIN` | | Serving and export |

Secrets are never committed (`.env` is git-ignored).

---

## API

Long work runs as a job: POST returns a job, then poll `GET /api/jobs/{id}` until `status` is `done` or `error`.

| Group | Endpoints |
|---|---|
| Status | `GET /api/ready` (what is missing, what to run), `GET /api/health`, `GET /api/languages`, `GET /api/jobs/{id}` |
| Lessons | `POST /api/lessons` (`concept`, `languages`, `level`, `duration_s` 30-240, `mode`, `quality`, `upload`, `focus`, `images`), `GET /api/lessons`, `GET /api/lessons/{id}`, `POST /api/lessons/{id}/export` |
| Courses | `POST /api/playlists` (same fields plus `episodes` 0-3), `GET /api/playlists[/{id}]`, `POST /api/playlists/{id}/export` |
| Sources | `POST /api/uploads` (PDF), `GET /api/uploads/{sha}[/notes]`, `POST /api/search`, `GET /api/knowledge/search?q=...`, `POST /api/images`, `GET /api/images/{sha}` |
| Homework | `POST /api/homework`, `GET /api/homework[/{id}[/download]]` |
| Learning | `POST /api/lessons/{id}/chat`, `.../studio[/{kind}]`, `.../teachback`, `GET /api/review/due`, `/api/review/stats`, `POST /api/review/answer`, `/api/weak*`, `/api/profile`, `/api/rewards*` |
| Take away | `GET /api/lessons/{id}/subtitles`, `POST .../podcast`, `.../say`, `GET .../bundle`, `POST /api/bundle/import`, `/api/papers*` |
| Voice and world | `POST /api/stt`, `POST /api/metaquiz`, `POST /api/metaworld`, `GET/POST /api/metaverse/save` |
| Files | `GET /media/...` (audio, MP4, `.srt`), `GET /fonts/...` |

The lesson JSON shape is mirrored in `web/src/types.ts`; the plan schema is `backend/app/schema.py`. To render a track in any React app, give it to `LessonVideo` (`web/src/remotion/Lesson.tsx`) inside Remotion's `<Player>` with `inputProps={{ track, assetBase: "" }}`.

---

## Project layout

| Path | What |
|---|---|
| `backend/app/planner.py`, `longplan.py` | Prompts by subject, Flash parts, Pro outline and blocks |
| `backend/app/content.py`, `memory.py`, `facts.py` | Quality rules, what already exists, fact checker |
| `backend/app/pipeline.py`, `playlist.py`, `streaming.py` | Orchestration, courses, scenes that play while they are made |
| `backend/app/schema.py`, `director.py`, `review.py` | Lesson schema and repair, visual director, writer/reviewer |
| `backend/app/knowledge.py`, `rag/`, `ocr/` | Retrieval, PDF ingestion, OCR, Markdown, figures, notes |
| `backend/app/translate.py`, `tts.py`, `expression.py`, `stt.py`, `languages.py` | Languages and voices |
| `backend/app/vision.py`, `homework.py`, `chat.py`, `videochat.py`, `studio.py` | Photos, homework, tutor, extra videos, study tools |
| `backend/app/jobs.py`, `resume.py`, `resources.py`, `gpu.py`, `selfcheck.py` | Jobs, crash resume, memory gate, GPU slot, readiness |
| `backend/scripts/` | `build_knowledge.py`, `fetch_library.py`, `download_models.py` |
| `backend/tests/` | 345 tests |
| `web/src/remotion/` | Scene templates, graph, code, icons, themes |
| `web/src/pages/`, `components/`, `studio/` | Home, Lesson, Library, Rewards, Progress, Review, Profile, Settings; study tools |
| `metaverse/` | The walkable 3D world (Learnverse) |
| `Unlox_Hackethon/` | The Android app (Kotlin, Compose) |
| `blender 3d/` | Offline narrated 3D lessons with headless Blender (Dhiraj) |
| `data/topics.txt`, `data/kb_extra/` | Wikipedia topic list; reference notes (committed) |
| `data/curated/` | Hand-written lesson plans (git-ignored) |
| `docs/` | Design notes; `docs/README-notes.md` is the older detailed README |

---

## Quality, safety and fact checking

- **Schema first.** Every model reply is parsed as JSON, repaired and validated; bad plans are retried with the error, and a plan that is weak (repeats, short captions, an unanswered question, a technical topic with no code or drawing) is sent back with feedback. A minimal fallback lesson means a job never ends empty.
- **Grounded.** The planner reads retrieved passages (Simple English Wikipedia, reference notes in `data/kb_extra/`, your PDFs). Sources are listed with each lesson.
- **Fact checker (`facts.py`).** Runs on the English plan before translation, using no outside service:
  1. *Calculation:* arithmetic and linear equations are worked out ("x = 20 / 3" for 3x + 5 = 20 is corrected to x = 5); a count that does not match its list ("7 colours: red ... indigo") and a few lists every child learns (rainbow, planets in order, continents, oceans, senses) are checked against the real list.
  2. *Sources:* each statement is compared with passages that are about it; a verdict only counts if the judge quotes words that really are in the source, and a focused second question must agree before anything changes.
  3. *Second opinion:* the model, when no source covers a statement, may only say "wrong" if the opposite question ("is it true?") agrees.
  4. *Repair:* a correction must pass the same check, keep what the sentence taught and have no notes or brackets, else the statement is removed (never leaving a scene too thin). Quiz answers change only when a source and the model agree. Analogies are not treated as claims.
  The report (checked, confirmed, corrected, removed, sources) is saved with the lesson and shown in the notes panel.
- **Safe translation.** Script checks and back-translation; a failure keeps English.
- **No code runs.** Code scenes are text; Python is only parse-checked.
- **Privacy.** Everything stays on the machine; the learner profile is a local file.

---

## Android app

`Unlox_Hackethon/` is the same product as a native app that runs fully on the phone (tested on a OnePlus 13R, 16 GB): lesson planner, tutor and homework solver on Gemma 4 E2B (LiteRT-LM), narration with Piper through sherpa-onnx (and the phone's voice for Tamil and Kannada), speech to text with Whisper + Vosk, translation and OCR with ML Kit, long videos in parts, a set of videos that plays on by itself, and "make one more video" in the chat. Models (about 4 GB) are not in git: copy them to `Android/data/com.kabir.unlox_hackethon/files/models/` (`llm/`, `stt/`, `tts/`, `embeddings/`). Build with `gradlew :app:assembleDebug` (JDK 21). The Android app does not have the Flash/Pro switch, the fact checker or the memory yet.

---

## Testing

```powershell
cd backend ; .\venv\Scripts\python -m pytest -q          # 345 tests; run with the backend stopped (a few thread-timing tests are flaky under load)
cd ..\web ; npx tsc --noEmit ; npx vite build
cd ..\Unlox_Hackethon ; .\gradlew.bat :app:assembleDebug
```

Live checks used while building: lessons on the aquatic life of earth, the solar system, rainbows, the MERN stack, why the sky is blue, how steel is made, how a refrigerator works, and AVL trees, in Flash and Pro, with the fact checker on.

---

## Performance and hardware

Built and measured on a laptop with an RTX 5060 (8 GB VRAM), 15 GB RAM, Windows 11.

- Language model: 43 tokens/s, 100 % on the GPU. First scene of a short lesson about 1.2 s warm; the player opens 6 to 18 s after you ask (Flash).
- A 2-minute video: about 2 to 3 minutes to build (planning, checking, translation, narration), then export about 1.5 times its length.
- PDF reading: text-layer pages 1 to 15 ms each, Markdown 50 to 500 ms, OCR about 1 s; a 1,000-page scan is searchable in under 3 minutes.
- Translation of 32 sentences: 2.9 s after batching and caching.
- The three GPU users (language model, translator, voices) share 8 GB by taking turns; the resource gate and a PyTorch cap keep the language model from being starved.

---

## Known limits

- The 7B model still gets facts wrong now and then. The fact checker removes or corrects what it can prove wrong; the rest is reported as "not confirmed".
- Code is shown, not run; only Python is syntax-checked.
- Very short labels can be mistranslated for lack of context; IndicTrans2 is gated and needs a C compiler on Windows (NLLB is the default).
- Android lacks Flash/Pro, the fact checker and memory; its changes since v0.15.0 are compiled but not tested on the device.
- Only one extra chat video at a time.
- Hand-written lessons are not fact-checked.

---

## Licences

Verified from the model's own licence file or from Ollama (`ollama show <model> --license`) where noted; the rest are the published licences and should be re-checked before redistribution.

| Component | Licence | Basis |
|---|---|---|
| Qwen2.5-7B-Instruct (planner, tutor) | Apache-2.0 | `ollama show --license` |
| LLaVA 7B (photos) | Apache-2.0 | `ollama show --license` |
| nomic-embed-text (knowledge-base embeddings) | Apache-2.0 | `ollama show --license` |
| Unlimited-OCR (accurate OCR) | MIT | `models/Unlimited-OCR/LICENSE` |
| Whisper / faster-whisper (speech to text) | MIT | model card |
| IndicTrans2 (translation) | MIT (gated download) | `models/indictrans2/LICENSE` |
| AI4Bharat Indic-TTS, Indic Parler-TTS | MIT / Apache-2.0 | upstream cards (ONNX repack is unofficial) |
| multilingual-e5-small, bge-reranker-v2-m3 | MIT / Apache-2.0 | upstream cards |
| NLLB-200 distilled 600M (translator used when IndicTrans2 is not installed) | **CC-BY-NC 4.0 (non-commercial)** | upstream card; set `TRANSLATE_BACKEND=indictrans2` (MIT) to avoid it |
| piper-tts (voice engine) | GPL-3.0-or-later | pip metadata; each Piper voice has its own card |
| Tesseract | Apache-2.0 | upstream |
| Wikipedia text | CC BY-SA 4.0 | downloaded at setup; each lesson lists its articles |
| Noto fonts | SIL OFL 1.1 | upstream |
| Remotion (renderer) | Remotion licence (free for individuals and small teams) | upstream terms |
| ffmpeg | LGPL/GPL by build | upstream |
| Gemma 4 E2B (Android only) | Gemma terms of use | upstream |
| NCERT / OpenStax (optional library) | NCERT: local use only; OpenStax: CC BY 4.0 | upstream |

---|---|
| Qwen2.5-7B-Instruct | Apache-2.0 |
| LLaVA, nomic-embed-text, bge-reranker, multilingual-e5-small | see each model card |
| NLLB-200 | CC-BY-NC (research/education use; check before commercial use) |
| IndicTrans2, AI4Bharat Indic-TTS | MIT (gated download; ONNX repack is unofficial) |
| piper-tts | GPL-3.0-or-later (voices: per-voice cards) |
| Wikipedia text | CC BY-SA 4.0 (downloaded at setup, each lesson lists its articles) |
| Noto fonts | SIL OFL 1.1 |
| Remotion | Remotion licence (free for individuals and small teams; read the terms) |
| ffmpeg | LGPL/GPL by build |
| NCERT / OpenStax (optional library) | NCERT: local use only; OpenStax: CC BY 4.0 |

Please verify the licences of anything you redistribute.

---

## Docs and team

`prd.md`, `problem_statement.md`, `pitch.md`, `progress.md` (versions and git history), `issues.md` (every bug and its fix), `todo.md`, `docs/` (long videos, voice assistant, presentation mode, RAG and OCR design), `blender 3d/README.md`, `CLAUDE.md`.

Team folders in the repo: `Dhiraj/` (Dhiraj Shetty's snapshot of the RAG, OCR and library work), `Niharika/` (Niharika K P's voice-assistant and metaverse notes), `Priya/` (Priyadarshini Prasad's screen designs). See the team table at the top.

---

## Changelog

Current: **v0.16.0** (2026-10-29): Flash and Pro, memory of what already exists, technical topics shown with code and network scenes, reference notes, retries and readiness checks, fact checker.
Earlier: v0.15.2 coherent long videos and courses, "Teach me" removed from titles, expressive narration, non-blocking photos; v0.15.0 subject-aware prompt and faster first scene, PDF progress, Android parts and chat video; v0.14.x PDF Markdown and figures, caching, Learnverse worlds, chat videos, resilience; v0.13 Android app; v0.10 photos, modes, homework; v0.9 grey-glass home, rewards, long videos.
Full per-version notes: `progress.md` and `docs/README-notes.md`.
