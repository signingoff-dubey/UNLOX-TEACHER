# Progress Log

## Current Version: v0.8.0
## Status: In Progress (pre-Gate 1)

---

## [v0.8.0] — 2026-10-27
### What's New
- **Merged everything the team pushed** (origin/main `60f5253`): Dhiraj's PDF upload + OCR (Tesseract / Unlimited-OCR) + hybrid RAG (e5 embeddings, FTS5 + FAISS, bge reranker), offline library, NLLB translation, GPU scheduler, sources shown on lessons; Niharika's `metaverse/` (3D quiz world) and `Niharika/` voice-assistant plan; Dhiraj's `Dhiraj/` snapshot (kept as pushed; not used by the app)
- One pipeline for both: `build_lesson(concept, languages, level, duration_s, documents, series, focus)` keeps level/length, series (courses), director and writer agents and now also grounds the plan in the PDF/library (`plan_lesson` returns plan + sources). Page-range lessons ("chapter 4") work from a PDF with an empty topic. Playlists accept a PDF too
- Frontend: Home uses Dhiraj's `PdfUpload` (progress + OCR status + focus), lesson notes list Sources, "Metaverse quiz world" button on Home and "Quiz in the metaverse" on the lesson screen (lazy-loaded 3D chunk)
- Tutor chat grounded with the same retrieval (`knowledge.retrieve`) instead of the earlier stub (`app/rag.py` removed: it collided with Dhiraj's `app/rag/` package)
- **Voice assistant** (from Niharika's plan, see `docs/voice-assistant.md`): `POST /api/stt` (faster-whisper small, CPU, offline), spoken tutor replies (`speak` flag -> `audio_url`), mic + speaker buttons in the chat panel. Hands-free mode and LTX demo clips are not built (LTX not realistic on 8 GB)

- **Metaverse entrance** (`web/src/components/TunnelTransition.tsx`, `MetaverseStart.tsx`): click the button and the page blurs while a tunnel of blocks assembles block by block around you; you walk down it, accelerating to light speed (~2 s, streaks); the bright light at the far end grows until it floods the screen; then the metaverse appears behind a **Start** page; Start reveals the topic screen. Canvas 2D, no extra dependency, skipped for `prefers-reduced-motion`; the 3D chunk preloads at the click
- **Fast OCR** (`backend/app/ocr/tesseract.py`, `ingest.py`): Tesseract 5.4 installed and the 9 language packs (tessdata_fast) in `models/tessdata`. Workers open the PDF and render their own pages as grayscale pixels (no PNG round trip), one Tesseract per core with all math libraries pinned to one thread (this cut a worker from ~670 MB to ~80 MB and fixed "paging file too small" crashes at 10+ workers), blank pages skipped, no batch barriers, worker count capped by free memory (`OCR_WORKERS` to override), Latin 200 dpi / Indic 300 dpi. The student's focus pages (e.g. "chapter 4") are read first and a section is indexed as soon as its last page is read, so a lesson on that chapter can start while the rest of the book is still being read. Raw OCR: ~7 pages/s on 22 workers (1,000 dense pages in ~140 s). Unlimited-OCR still upgrades pages in the background (priority: contents, focus, worst-confidence)
- `backend/scripts/bench_tesseract.py [pages] [workers] [--ingest]` builds a synthetic scan and times it

- **Study tools** (flashcards, quiz, mind map, study guide, FAQ, glossary, timeline): built by a background queue as soon as a video exists (`studio.py`; click = jump the queue; English raw copy cached, other languages translated from it), progress from the model's token stream. Buttons in the chat panel: ready opens instantly; working buttons get a flowing multi-colour border and a steady percentage (`useSteadyProgress`: a clock keeps it moving, real progress can only pull it ahead). Mind map = Mermaid text parsed/re-emitted by the backend and drawn on-device. Flashcards redesigned (question front, View answer, 3D flip, slide-away rating, round review)
- **Meta quiz** (`metaquiz.py`, `POST /api/metaquiz`): one metaverse world from every study tool and every video of a course; stations carry extra reading, gates ask up to 5 questions with explanations (metaverse engine extended: `Zone.more`, `info.extra`, `Quiz.why`)
- **PDF notes in 30-page windows** (`ocr/digest.py`): written while OCR runs; 100-page scan: first notes at ~22 s, all at ~32 s; whole-PDF lessons plan from the notes; upload cap 1,000 pages; pass-1 embeddings moved to the idle GPU (OCR+index 1,002 pages: 341 s -> 171 s)
- **Metaverse entrance made smooth**: the lag was the 3D world initialising on the main thread during the animation (up to 0.9-1.6 s freeze); now state is isolated (`MetaverseLayer`), the world starts behind a still white frame and the light clears when it has painted and frames are calm, no CSS blur / backdrop-filter, precomputed tunnel geometry, adaptive canvas resolution, chunk preloaded on hover/idle

### Known Issues
- Studio background builds queue behind each other (one local model): a video's 7 tools take about 2 minutes; opening a lesson queues its tools, and a click goes first
- `transformers` in `backend/venv` is 4.46 (Dhiraj pins 4.57.1 for Unlimited-OCR); scanned-PDF OCR with Unlimited-OCR needs its own ~6.7 GB model and that pin, digital PDFs work without
- Whisper small is weak on Telugu/Tamil/Kannada speech; English and Hindi are the supported voice-input languages for the demo
- Mic needs localhost or HTTPS

---

## [v0.7.0] — 2026-10-27
### What's New
- **Fixed the repeated "bulb" scenes.** Root cause: `normalize()` demoted any scene with too few points to a plain `title` card, so a graph lesson became 4 identical lightbulb cards. Now points are rebuilt from the narration and the originally wanted template is remembered
- **Visual director agent** (`backend/app/director.py`): finds weak scenes (title mid-lesson, same type twice in a row, bullets on a maths/code topic) and redesigns each with a focused call: graphs for maths, code for programming, diagrams/flows for processes. Visual fields only; narration kept
- **Coordinate geometry**: graph scenes can plot points without a curve, draw segments between points (`link` mark), show quadrants I-IV, auto-fit the plane to the points
- **Playlists / courses** (`backend/app/playlist.py`): curriculum agent outlines 5-8 episodes, each built as a series-aware lesson (links to the previous episode, teases the next, no repeats); playlist file saved after every episode so playback starts on episode 1 while the rest are made; episodes build 2 at a time (voice of one overlaps planning of the next, episode 2 waits until episode 1 is past planning); one failed episode does not sink the course; `POST /api/playlists`, `GET /api/playlists[/{id}]`, `POST /api/playlists/{id}/export` (renders every episode and joins them into one MP4). Playlists and exports get their own job workers
- **Course UI**: Format switch on Home (One video / Course of 5-8), episode rail under the video, auto-advance when a video ends (waits if the next is still being made), deep links `#c-<id>[-<episode>]`, "whole course MP4" button
- **Multimodal visual QA** (`backend/scripts/visual_qa.py`): renders-frames-to-vision-model check. moondream (1.7B) gave unusable answers; llava:7b works: it described the old lesson's scenes 1-4 as the same "question mark and light bulb" graphic and flagged them

### Known Issues
- Planner still sometimes puts a quiz early; title/summary/quiz ordering is not enforced
- llava:7b QA needs the planner model unloaded first (8 GB VRAM) and is a script, not part of the pipeline

---

## [v0.6.0] — 2026-10-27
### What's New
- **Real translation working**: IndicTrans2 (en->hi/te/ta/mr/...) running locally from `models/indictrans2` (set `INDICTRANS2_MODEL` to that folder, `HF_HUB_OFFLINE=1`)
- **Voices verified by round-trip** (speak a known sentence, transcribe with Whisper): hi, ta, kn, en good; te, ml, gu correct sounds; mr was garbled on Piper -> now Indic-TTS (0.77 match); bn unverified (Whisper medium cannot read Bengali). `TTS_PREFER_INDIC=bn,mr`
- **Multi-agent pipeline** (all local, all data-only): Planner (Qwen2.5-7B, schema JSON) -> Reviewer (ast check + repair) -> Writer (per-scene free-text narration when the lesson is too short) -> Translator (IndicTrans2) -> Narrators (one thread per language) -> Tutor (chat). Lesson size is set from the slowest chosen language (`WORDS_PER_SEC`) so every track stays inside the requested length
- Per-language TTS locks: all languages record at once
- Planner model benchmark (see below)

### Planner model benchmark (RTX 5060 8 GB, 3 prompts, JSON-schema planner)
| Model | avg s/lesson | valid | notes |
|---|---|---|---|
| qwen2.5:7b-instruct-q4_K_M | 34 | 3/3 | picks graph for maths, code for programming; writes short lessons (writer agent fixes) |
| qwen2.5:3b-instruct-q4_K_M | 24-33 | 2/2 run | missed graph scenes on the circle prompt |
| qwen3:4b | 128 | 3/3 | right length but thinking tokens make it 4x slower; removed |
| qwen3.5:9b, llama3.2:3b | n/a | n/a | not measured (C: disk and RAM pressure) |

### Known Issues
- C: drive was nearly full (0.1 GB): HF cache and Ollama models live there. New downloads go to D: (`models/`)
- Indic Parler-TTS not installed (3.7 GB, not needed). Bengali voice quality unverified
- Whisper-medium check is a proxy: it cannot judge accent or naturalness; a human ear is still needed

---

## [v0.5.0] — 2026-10-27
### What's New
- **Lesson screen = notes | video | tutor chat.** Left: scene-by-scene notes from the lesson (follow playback, click to jump, code/equations included, "My notes" box, copy/download .md). Right: tutor chat that knows the whole lesson and the scene being watched (`POST /api/lessons/{id}/chat`; English plan -> answer -> translated to the active language)
- **Progress is inside the video area** (no separate screen) and continuous: planner now streams tokens for real progress, per-scene voice progress, plus a smoothing hook so the bar never sits still or jumps backwards
- **English is an ordinary option** (no longer forced); at least one language required; lesson stores the English plan for chat
- **Reviewer agent** (`backend/app/review.py`): `ast.parse` check of Python snippets + one small LLM repair call; notes returned in `lesson.review` and shown in the UI
- Removed the separate Creating screen

### Known Issues / findings
- Root cause of "Hindi speaks English with a Hindi accent": `TRANSLATE_BACKEND=none` in a local `.env` -> English text read by a Hindi voice. UI now warns when a non-English track was not translated
- Ollama (Qwen) translation is poor (Telugu leaked Chinese characters); IndicTrans2 needed. Hugging Face downloads stall on the Xet path: use `HF_HUB_DISABLE_XET=1`. Network ~0.5-1.3 MB/s
- Indic Parler-TTS (3.7 GB) not downloaded: not needed now that ta/kn/gu have CPU Indic-TTS voices and bn has a Piper voice

---

## [v0.4.0] — 2026-10-27
### What's New
- Merged teammate's frontend (status panel, history, remote backend)
- **Screen-by-screen UI** (`web/src/screens/`): Home (topic box, PDF upload area, level, length 30/60/90 s, languages, recent lessons, system status) -> Creating (live progress, steps) -> Lesson (player)
- **Player screen**: custom controls: seek bar with scene ticks, tap or drag to seek, hover preview (time + scene), time readout, play/pause, +-5 s, previous/next scene, volume, captions toggle, settings (language, speed 0.75-1.5x, captions, download quality 720p/1080p), full screen; double-tap left/right third of the video = -/+5 s; keyboard (space, arrows, M, C, F); language switch keeps your position; scene list tap-to-jump; MP4 + SRT download
- `POST /api/lessons` now takes `level`, `duration_s` (30-90) and `documents` (ids); prompt adapts to level and length
- `backend/app/rag.py`: single hook `retrieve_context(concept, document_ids) -> str` for the RAG/OCR service; UI uploads to `POST /api/documents` (multipart `file` -> `{id, name, pages?}`) and shows "document service not connected yet" until it exists
- Hash routing fixed (Back/forward and pasted `#id` links open the lesson)

### Known Issues
- Document upload has no backend yet (friend's RAG/OCR service); `documents` ids are accepted but ignored
- Dev-only React warning from Remotion's AbsoluteFill in the Player (pre-existing, harmless)
- Chrome extension was not reachable; UI verified with headless Chrome (screenshots in `output/ui/`)

### Ideas evaluated
- **LTX-2.5 (Lightricks) generative video**: not adopted for the core pipeline. 22B params (int8 21.5 GB + text encoder 15.4 GB, NVFP4 18.7 GB) vs this laptop's 8 GB VRAM / 15 GB RAM; far beyond the 8-16 GB CPU target; cannot render exact Indic text or follow our audio-sets-length rule; gated + community licence. Possible only as an optional, pre-generated b-roll step on a GPU machine

---

## [v0.3.0] — 2026-10-27
### What's New
- **Graph scenes** (`web/src/remotion/graph.tsx`): axes, grid, ticks, curves that draw themselves (line, parabola, cubic, sine, cosine, exp, abs, sqrt, reciprocal, circle, ellipse), circle marks (centre, radius, diameter, chord, tangent), points, formula card, legend. LLM supplies enum + numbers only; nothing is evaluated
- **Code scenes** (`web/src/remotion/code.tsx`): dark editor, offline syntax colouring (Python, Rust, JS/JSX, Java, C, Go, SQL), line highlight following the narration, per-line notes, output console. Snippets are display text, never run
- Planner routes by subject (maths -> >=2 graph scenes, programming -> >=2 code scenes) with worked examples; `normalize()` fills missing labels/highlights; keyword-routed offline samples for `LLM_BACKEND=mock`
- Export height option: `POST /api/lessons/{id}/export {"lang","height":720|1080}`, default 720. Measured 1080p 38.5 s vs 720p 21.3 s for a 40 s lesson, so 720 is default; the UI can offer 1080p as a boost
- CPU voice engine `indic` (AI4Bharat Indic-TTS ONNX: en, ta, kn, gu; RTF ~0.4) ahead of the GPU-only Parler fallback; Bengali now uses its Piper voice
- GPU+CPU: Ollama layer offload (`OLLAMA_NUM_GPU`, auto = as many as fit; 100% on RTX 5060), ONNX CUDA provider when onnxruntime-gpu is present, torch CUDA installed, `/api/health` shows `gpu.ollama_loaded[].gpu_percent`; `DEVICE=cpu` forces CPU everywhere
- Backend venv, web deps, headless Chrome, Piper voices and Noto fonts installed locally

### Known Issues
- IndicTrans2 and Indic Parler-TTS are gated on HuggingFace: account must accept each model's terms before download (translation to Indic languages untested until then)
- 7B model sometimes writes slightly invalid snippets (e.g. missing closing tag); no syntax check yet (idea: `ast.parse` for Python)
- Indic voices (ta/kn/gu ONNX repack) and Indian-accent English not yet judged by ear

---

## [v0.2.0] — 2026-10-27
### What's New
- Merged teammate's `origin/main` (5127b43): FastAPI backend (Ollama planner, IndicTrans2, Piper/Parler TTS, captions, jobs), Remotion `web/` frontend, 8 templates
- Removed our Revideo scaffold and draft `schema/` (superseded by `backend/app/schema.py` and Remotion); scaffold kept outside repo
- License note: project is hackathon-only, not published; license columns kept in README for the submission rule

### Known Issues
- Teammate's design uses Indic Parler-TTS on GPU for ta/kn/bn/gu; spec says CPU-only. Needs CPU path (our Indic-TTS ONNX voices) or accept GPU risk
- Renders at 1920x1080; spec asks 720p (RENDER setting to check)

---

## [v0.1.0] — 2026-10-27
### What's New
- Project docs (prd, problem_statement, pitch, issues, progress, README)
- Draft shared lesson contract: `schema/lesson.schema.json` + `schema/sample-lesson.json` (en + hi)
- `frontend/`: Revideo 0.11.0 starter scaffolded, deps installed
- Local assets downloaded (git-ignored, under `models/` and `fonts/`):
  - Piper voices: hi, te, mr, bn, ml, en_GB-alan
  - AI4Bharat Indic-TTS int8 ONNX: en, ta, kn, gu
  - Noto Sans fonts (OFL): Devanagari, Telugu, Bengali, Malayalam, Tamil, Kannada, Gujarati, Gurmukhi, Oriya
  - Ollama: qwen2.5:7b-instruct-q4_K_M, qwen2.5:3b-instruct-q4_K_M (plus pre-existing qwen3.5:9b)
- Python venv `.venv` with piper-tts, onnxruntime, huggingface_hub (`hf` CLI)

### References reviewed
- `inspiration/` (TheoremExplainAgent, MIT): ideas only, no code reuse (needs cloud LLMs via litellm, LLM writes Manim code, English-only). Borrowed: multi-stage plan (outline -> per-scene detail -> narration), audio-duration-drives-scene pattern, learning-objective prompting. `inspiration/` is git-ignored.

### Known Issues
- No voice has been run/timed yet; ta/kn/gu/en repack quality and Indian-accent English unverified
- IndicTrans2 is gated on HuggingFace; needs `hf auth login` + terms acceptance (user action)
- Backend not started here (teammate owns it)

### Future Scope
- Revideo spike: sample lesson -> MP4 with Hindi text + audio, offline
- Scene components: TitleCard, Diagram, CodeWalkthrough driven by lesson JSON
- Player with language switch; captions (SRT + burned-in)
- Voice smoke test + CPU timing per language
- Optional: pa/or/as via official Indic-TTS zips; IndicTrans2 translation

---

## Git History
| Commit | Date | Message |
|--------|------|---------|
| 1cb5b0d | 2026-10-27 | Project setup: docs, lesson schema, Revideo frontend scaffold, fonts |
| 3d9d818 .. 123513d | 2026-10-27 | Orchestration doc, graph/code scenes, merge of teammate frontend, screen-by-screen UI |
| d7527c7 | 2026-10-27 | Notes panel, tutor chat, progress |
| 4b0466c | 2026-10-27 | IndicTrans2, voices, writer/reviewer agents, pacing |
| 86a5fed | 2026-10-27 | Director agent, point-plotting graphs, playlists backend + UI, vision QA script |
| 9ae15b7 | 2026-10-27 | Merge origin/main (PDF/OCR/RAG, metaverse); voice, study tools, Meta quiz, fast OCR, tunnel entrance |
