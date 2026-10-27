# Chanakya

Type a concept and get a 30–90 s narrated, animated lesson in English plus Indian languages.
It plays in the browser and exports to MP4. Everything runs offline on one laptop.

```
concept ─► retrieve facts from offline knowledge base (embeddings, ~1 ms search)
        ─► Ollama LLM ─► lesson JSON (schema-checked) ─► IndicTrans2 ─► Piper / Indic Parler-TTS
                                                                         │ audio length = scene length
browser player ◄── Remotion scene templates ◄── timed lesson JSON ◄──────┘ captions timed to audio
MP4 export     ◄── Remotion renderer (headless Chrome + bundled ffmpeg)
```

- **Data, never code:** the LLM only picks one of 10 templates (title, bullets, flow, cycle, compare, diagram, quiz, summary, **graph**, **code**) and fills in its text fields.
- **Narration first:** each scene's voice is synthesized before anything is animated, and the scene lasts exactly as long as that audio plus 0.5 s. Item reveals and captions are timed against the same audio.

## Knowledge base and retrieval (RAG)

Lessons are grounded in an offline knowledge base, so facts come from a source and not only from the 7B model's memory.

- **Dataset:** about 300 school topics in `data/topics.txt`, covering biology, chemistry, physics, earth and space, maths, Indian geography, history and civics, economics and computers. They are fetched from **Simple English Wikipedia**, which is written for learners, with English Wikipedia as a fallback. The current build has 308 articles split into 3,500 passages.
- **Your own material:** drop `.txt` or `.md` files (notes, syllabus text, worksheets) into `data/kb_extra/`, then rebuild.
- **Indexing:** `backend/scripts/build_knowledge.py` splits articles by section into ~700-character passages and drops references and links sections. It embeds them with `nomic-embed-text` through Ollama and saves a normalised matrix in `data/kb/`. Rebuild offline with `--no-fetch`.
- **Search:** one matrix-vector product (cosine similarity), plus a boost when the question names the article. At most 2 passages per article for variety, and a score cut-off (0.68) so unrelated topics add nothing. Takes ~35–60 ms.
- **Use:** the top passages (up to ~4,000 characters) go into the planner prompt as reference material. Each lesson lists its **Sources**.
- **Inspect it:** `GET /api/knowledge/search?q=how do vaccines work`.

Wikipedia text is CC BY-SA 4.0. The articles are downloaded during setup, not stored in this repo, and each lesson links to the articles it used.

## Lessons from your own PDF

Attach a textbook or notes PDF (up to 2 GB / 1,000 pages) in the UI, or `POST /api/uploads`. Digital pages are read directly. Scanned pages go through **Tesseract** (about 6 pages/second on 22 cores: 1,000 pages in under 3 minutes, including embeddings and the search index) and then, when the GPU is idle, a higher-accuracy **Unlimited-OCR** pass that always gives way to lesson generation.

- **Concept + PDF:** "photosynthesis" searches the PDF first, then the knowledge base.
- **Chapter or pages:** leave the concept empty and type `chapter 4` or `pages 120-135` as the focus, or type "explain chapter 4" as the concept. The lesson teaches that part of the book in reading order, condensed to fit the prompt.
- The recap scene shows a citation such as `Source: Science 8, Chapter 2, pp. 41–44`.
- Uploads run on their own job queue, so a long OCR run never delays a lesson.

Design: `docs/superpowers/specs/2026-10-27-rag-ocr-design.md`. Code: `backend/app/ocr/`, `backend/app/rag/`, `backend/app/routes_rag.py`.

## Quick start (Windows, PowerShell)

```powershell
git clone https://github.com/signingoff-dubey/UNLOX-TEACHER.git
cd UNLOX-TEACHER
.\setup.ps1 -Gpu     # once, online. Leave out -Gpu for a CPU-only setup (Piper voices + Ollama translation)
.\start.ps1          # opens http://127.0.0.1:8000; add -Lan to accept other devices
```

If PowerShell blocks the scripts, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
You also need **Ollama** (https://ollama.com); `setup.ps1` pulls the model if it's installed.

**What the UI offers:**
- Type a concept or click an example, pick languages, and get a narrated lesson in under a minute.
- Language tabs to switch the same lesson between English, Hindi, Telugu and others.
- A scene list that jumps the player to any scene and highlights the one playing.
- MP4 export and `.srt` captions download per language.
- **Recent lessons:** replay any earlier lesson. Generate backups before the demo.
- **System status:** shows whether the planner, translator, voices and video export are ready.
- **Backend address:** the UI can use a backend on another laptop (e.g. `http://192.168.1.20:8000`).
- Build-time breakdown, and the lesson JSON for judges who ask how it works.

## Layout

| Path | What |
|---|---|
| `backend/app/planner.py` | Retrieval-grounded prompt, Ollama JSON-schema output, validation, retry, fallback |
| `backend/app/knowledge.py` | Offline vector search over the knowledge base |
| `backend/scripts/build_knowledge.py` | Fetches, chunks and embeds the dataset |
| `data/topics.txt`, `data/kb_extra/` | Dataset topic list and your own documents |
| `backend/app/schema.py` | Lesson schema + `normalize()` that repairs small-model mistakes |
| `backend/app/translate.py` | IndicTrans2 (or Ollama) translation, cached on disk |
| `backend/app/tts.py` | Piper (CPU) → Indic Parler-TTS (GPU) → silent fallback chain, cached |
| `backend/app/pipeline.py` | Orchestration; builds per-language timed tracks + `.srt` |
| `backend/app/exporter.py` | Runs `web/render.mjs` to make the MP4 |
| `backend/app/main.py` | FastAPI app, job queue, serves media/fonts/built frontend |
| `web/src/remotion/` | Video: templates, icons, captions, fonts |
| `web/src/App.tsx`, `web/src/components/` | Student UI: input, player, scenes, history, status |
| `web/src/api.ts` | API client, job polling, configurable backend address |
| `setup.ps1`, `start.ps1` | One-command setup and start |

## Setup on the machine that runs the backend (the one with the models)

The backend renders MP4s with Node, so copy the **whole project folder** (backend + web) to that machine.

1. **Python 3.12** (3.14 is too new for these packages):
   ```powershell
   cd backend
   py -V:3.12 -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   # GPU extras (RTX 50-series needs CUDA 12.8 wheels):
   .\venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128
   .\venv\Scripts\pip install -r requirements-ml.txt
   ```
2. **Config:** `copy .env.example .env`, then point it at the models already on that machine:
   - `INDICTRANS2_MODEL` / `PARLER_MODEL`: a Hugging Face id (read from the HF cache) or a local folder path
   - `PIPER_DIR`: the folder with `*.onnx` + `*.onnx.json` voices. Files must be named as in `backend/app/languages.py`, e.g. `hi_IN-priyamvada-medium.onnx`.
   - `OLLAMA_MODEL`: must match a name in `ollama list`
3. **Anything missing** (voices, fonts, models) while still online: `.\venv\Scripts\python scripts\download_models.py [--ml]`
4. **Frontend + renderer** (Node 20+):
   ```powershell
   cd ..\web
   npm install
   npm run bundle      # pre-builds the video bundle + downloads headless Chrome once
   npm run build       # backend then serves the UI at http://127.0.0.1:8000
   ```
5. **Run:** `ollama serve`, then `cd backend; .\run.ps1` (add `-Lan` to accept other devices).
   Check `http://127.0.0.1:8000/api/health`: it reports what loaded (Ollama, translator, voices, renderer).
6. **Before the demo:** set `HF_HUB_OFFLINE=1`, turn Wi-Fi off, and generate one lesson end to end.

**Development:** run the backend, then `cd web; npm run dev` (UI on :5173, proxied to :8000).
`npm run studio` previews every template with no backend.
`LLM_BACKEND=mock` runs the whole pipeline without Ollama.

## Fallbacks (the demo keeps going)

| Failure | What happens | Shown in the response as |
|---|---|---|
| LLM returns bad JSON | One retry with the error message, then a minimal 2-scene lesson | — |
| Ollama not running | Job fails with a clear "start Ollama" message | `job.error` |
| Translation model won't load | English text is kept for that language | `track.translator = "untranslated"` |
| No Piper voice for a language (kn, ta, bn, gu) | Indic Parler-TTS is used | `track.tts_engines` |
| No voice model at all | Silent audio with the right timing | `track.tts_engines = ["silent"]` |

## API

All long work runs as a job: POST returns a job, then poll `GET /api/jobs/{id}` until `status` is `done` or `error`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | — | What is installed and loaded |
| GET | `/api/languages` | — | `[{code, name, native, piper}]` |
| POST | `/api/lessons` | `{"concept": "Photosynthesis", "languages": ["hi","te"]}` | Job; `result` = Lesson |
| GET | `/api/jobs/{id}` | — | `{id, status, stage, progress 0..1, result, error}` |
| GET | `/api/lessons/{id}` | — | Lesson |
| GET | `/api/lessons` | — | Recent lessons (history) |
| GET | `/api/knowledge/search?q=…&k=5` | — | Retrieved passages with scores |
| POST | `/api/lessons/{id}/export` | `{"lang": "hi"}` | Job; `result` = `{"url": "/media/.../lesson_hi.mp4"}` |
| GET | `/media/...` | — | Audio, MP4s, `captions_<lang>.srt` |
| GET | `/fonts/...` | — | Noto fonts used by the player and renderer |

English is always included. The language codes are `en hi te ml mr kn ta bn gu`.

**Lesson shape** (`web/src/types.ts` mirrors it):

```json
{
  "id": "e66517564b", "concept": "Photosynthesis",
  "timings": {"plan_s": 12.1, "en_s": 2.0, "hi_s": 3.5},
  "videos": {"en": "/media/lessons/e66517564b/lesson_en.mp4"},
  "languages": {
    "hi": {
      "lang": "hi", "name": "Hindi", "native": "हिन्दी", "title": "प्रकाश संश्लेषण",
      "duration_s": 49.6, "tts_engines": ["piper"], "translator": "indictrans2",
      "scenes": [{
        "template": "diagram", "heading": "…", "narration": "…", "items": ["…"], "icon": "leaf",
        "left_title": "", "right_title": "", "left": [], "right": [], "answer_index": 0,
        "audio_url": "/media/audio/<hash>.wav", "speech_s": 7.07, "duration_s": 7.57, "start_s": 4.85,
        "captions": [{"start": 0.0, "end": 2.4, "text": "…"}]
      }]
    }
  }
}
```

To render a track in any React frontend, pass it to `LessonVideo` (`web/src/remotion/Lesson.tsx`) with Remotion's `<Player>`:
`inputProps={{ track, assetBase: "" }}`. `assetBase` is the backend origin if the UI is served from somewhere else.

## Verified on the RTX 5060 laptop (mock planner, Piper voices)

- A 6-scene, 40 s English lesson with Hindi and Telugu tracks built through the API (narration: ~3.5 s for Hindi, ~4.2 s for Telugu).
- MP4 export: 1920×1080 H.264 + AAC, 40.2 s, matching the narration. The first export took 87 s, including the one-time bundle and Chrome download.
- Devanagari and Telugu render correctly in the video, including conjuncts, using the bundled Noto fonts.
- The backend serves the built UI, assets, lesson history and deep links (`/#<lessonId>`).
- **Full offline pipeline (Dhiraj's machine):** Ollama `qwen2.5:7b-instruct-q4_K_M` with RAG, NLLB-200 on the GPU, and Piper.
  - "Why do we have seasons?" in English, Hindi and Telugu was built in **32 s**: plan 22 s, Hindi 4.5 s, Telugu 3.9 s.
  - It drew on 5 knowledge-base sources (top match "Season", 0.80) and produced a 6-scene lesson of 47 s in English and 73 s in Hindi.
  - The Hindi MP4 export took 60 s. The server starts in ~14 s with models preloaded.
- **Translation comparison:** NLLB-200 gives fluent Hindi and Telugu. Qwen-7B mixed scripts in Hindi and produced mostly wrong Telugu, and is now only a fallback. IndicTrans2 (Kabir's machine) is also supported and handles hi/te/ta/mr well.
- **Known limits:**
  - Very short labels can be mistranslated because they lack context ("Light bends" became "lightweight bends").
  - IndicTrans2 is gated on Hugging Face and its toolkit needs a C compiler on Windows.

## Models, Voices & Assets Used (licenses)
| Component | Name | License | Source |
|---|---|---|---|
| Planner LLM | Qwen2.5-7B-Instruct, Qwen3-4B (fallback) | 7B: Apache-2.0 (verified via `ollama show --license`). 3B: Qwen Research License (verified) — NOT used. Fallback: qwen3:4b (confirm Apache-2.0 via `ollama show --license` once pulled) | ollama.com/library/qwen2.5 |
| TTS engine | piper-tts 1.8.0 (OHF-Voice/piper1-gpl; uses espeak-ng) | **GPL-3.0-or-later** (verified via pip metadata). Old rhasspy/piper is MIT but archived | github.com/OHF-Voice/piper1-gpl |
| Piper voices | hi_IN-pratham, te_IN-venkatesh, mr_IN-google, bn_BD-google, ml_IN-meera, en_GB-alan (medium) | Per-voice, see each `.onnx.json` / model card — TO VERIFY | huggingface.co/rhasspy/piper-voices |
| Indic TTS | AI4Bharat Indic-TTS, int8 ONNX repack (en, ta, kn, gu) | MIT (upstream); repack by RaunakSaha, unofficial | huggingface.co/RaunakSaha/echobharat-models |
| Translation (optional) | IndicTrans2 distilled 200M | MIT (gated download) | huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M |
| Fonts | Noto Sans (Indic scripts) | SIL OFL 1.1 | github.com/google/fonts |
| Video engine | Revideo | MIT | github.com/midrender/revideo |
| Encoder | ffmpeg | LGPL/GPL by build | ffmpeg.org |
Excluded: Meta MMS-TTS (CC-BY-NC), sarvam-translate (GPL-3.0 tag + Gemma base).

## Hackathon docs
See `prd.md`, `problem_statement.md`, `pitch.md`, `progress.md`, `issues.md`, `docs/orchestration.md`.

## Submission Checklist
- [ ] Repo with README, setup, licenses
- [ ] MP4 on judge topic (live), MP4 on our topic
- [ ] 5-min offline demo rehearsed
- [ ] Verified with network disabled

## Graph and code lessons

- Maths topics (circle, parabola, sine wave, lines...) get `graph` scenes: curves are chosen from a fixed list (`line, parabola, cubic, sine, cosine, exp, abs, sqrt, reciprocal, circle, ellipse`) with numeric parameters; circles can mark centre, radius, diameter, chord, tangent.
- Programming topics (Python, Rust, React/JSX, Java, Go, SQL...) get `code` scenes: syntax-coloured snippet, a highlight that follows the narration, one note per line, optional program output. Snippets are only displayed, never executed.
- Test offline without a model: `LLM_BACKEND=mock` with a concept containing "circle" or "python".
- Export size: `POST /api/lessons/{id}/export` takes `"height": 720` (default) or `1080`.
- GPU/CPU: `OLLAMA_NUM_GPU=auto|N|0`, `DEVICE=auto|cuda|cpu`; see `/api/health` -> `gpu`.

## Screens and document upload

- Home: topic, optional PDF (with a focus like "chapter 4"), level, length, languages. Creating: progress. Lesson: player, scenes, downloads, sources.

## Models and voices (as run on the demo laptop)

| Role | Model | Where |
|---|---|---|
| Planner / reviewer / writer / tutor | Qwen2.5-7B-Instruct Q4_K_M via Ollama (GPU layers auto) | Ollama |
| Translation | AI4Bharat IndicTrans2 dist-200M (MIT, gated) | `models/indictrans2` (`INDICTRANS2_MODEL`) |
| Voices hi, te, ml, en | Piper | `models/piper` |
| Voices ta, kn, gu, bn, mr (+ en) | AI4Bharat Indic-TTS ONNX (CPU) | `models/indic-tts/<lang>` |
| Check only | faster-whisper medium (round-trip test of voices) | HF cache |

Download gated models with `HF_HUB_DISABLE_XET=1` set (the Xet path stalls on some networks).

## Study tools, Meta quiz and the metaverse entrance (Kabir)

- **Study tools** (`backend/app/studio.py`, `web/src/studio/`): flashcards, quiz, mind map, study guide, FAQ, glossary and timeline, made from the lesson (and its PDF passages). They are written **in the background** as soon as a video exists (low priority, so lesson generation is never slowed; a tool you click jumps the queue). The buttons at the top of the chat panel show the state: ready tools open instantly; a tool being written has a border of flowing colour and a steady percentage, and opens by itself when done. API: `GET /api/lessons/{id}/studio?lang=` (status), `POST` the same path (jump the queue), `GET .../studio/{kind}` (result). Output is JSON only; the browser draws it. Size and difficulty options, Markdown export, Anki CSV export for flashcards.
- **Mind map** is Mermaid text written by the model, parsed and re-written by the backend (nothing but a clean mind-map tree can reach the browser) and rendered on-device with Mermaid (bundled, offline).
- **Meta quiz** button: builds one metaverse world from **everything** the AI wrote for the video (or for every episode of a course): the lesson, quiz, flashcards, glossary, FAQ, study guide, timeline and mind map. Four stations to read (with extra reading from every tool) and quiz gates that ask several questions each, with explanations. `POST /api/metaquiz`.
- **PDF notes** are written 30 pages at a time as the OCR reads them (`backend/app/ocr/digest.py`, `GET /api/uploads/{sha}/notes`): a 100-page scan has its first notes after about 22 s and all of them after about 32 s. A lesson about a whole PDF is planned from these notes, not from 1,000 pages. Uploads are capped at 1,000 pages.
- **Metaverse entrance** (`web/src/components/TunnelTransition.tsx`, `MetaverseLayer.tsx`): a tunnel of blocks builds around you, light speed, a bright light, then a Start page. All motion is compositor-only (no blur filters); the 3D world starts up behind a still white frame so nothing animated waits on the main thread.

## PDF lessons, RAG and the metaverse (merged from Dhiraj and Niharika)

- **PDF lessons:** `POST /api/uploads` (PDF up to 2 GB) -> job; poll `GET /api/uploads/{sha}`. Then `POST /api/lessons` with `upload=<sha>` (and optional `focus` such as "chapter 4"); an empty concept teaches that part of the PDF. Playlists take `documents: [sha]`. OCR (Tesseract + Unlimited-OCR) and hybrid search (e5 embeddings, FTS5 + FAISS, bge reranker) live in `backend/app/ocr` and `backend/app/rag`; the offline library is built with `backend/scripts/fetch_library.py` / `build_library.py`.
- **Metaverse quiz world (Niharika):** `metaverse/` is a walkable 3D world with quiz gates, points and a shop. The web app opens it from the Home screen and from a lesson ("Quiz in the metaverse"); a lesson becomes a world through `metaverse/src/lessonToWorld.ts`.
- **Voice assistant (Niharika's plan in `Niharika/`):** see `docs/voice-assistant.md` for what is built.
- `Dhiraj/` is a full snapshot of Dhiraj's own build, kept as pushed; the running app is the root `backend/` and `web/`.
- Backend tests: `cd backend && pytest` (needs `requirements-rag.txt`).

## Home screen, rewards and long videos (v0.9.0)
- The prompt box on Home shrinks into a header as you scroll; settings (1-8 videos, 0:30-4:00 each, level, languages, PDF) are in the card below it
- The left column holds your awards: streak, score, level, daily goal, badges
- Videos over 1:30 are planned in parts and joined (`backend/app/longplan.py`); the API takes `duration_s` 30-240
- While a video is being made you can leave its page: a floating "Creating…" pill (bottom right) leads back and says "Created" when it is done

## Photos, modes and homework (v0.10.0)
- Plus button in the prompt box: attach photos (read locally by llava)
- Explanation / Study / Homework pills; Homework also writes an answers file (`#/homework/<id>`, download as .md)
- Videos: Auto lets the AI pick one video per concept

## Android app (v0.13.0)
`Unlox_Hackethon/` is the same product as a native Kotlin + Jetpack Compose app that runs fully on the phone (tested on a OnePlus 13R, 16 GB). No server, no internet at run time.

| Part | Engine |
|------|--------|
| Tutor, lesson planner, study tools, homework solver | Gemma 4 E2B through LiteRT-LM |
| Narration | Piper voices through sherpa-onnx 1.13.8 (en, hi, te, mr, bn, gu, ml); the phone's own voice for Tamil and Kannada |
| Speech to text | Whisper names the language, then Vosk (en, hi, te, gu) or Whisper base (ta, kn, ml, mr, bn). The approach is borrowed from the NDialRecorder |
| Translation | ML Kit language packs (download once), Gemma as the fallback |
| Homework photos | ML Kit text recognition (Latin and Devanagari) |

Screens follow the Figma file "NOTES - Kabir Edition" (onboarding, home, create, generating, player, tutor chat, progress, library) plus study tools, homework, rewards, settings and a profile with name and age. The opening animation and the ripple and wave of the voice screen are the website's.
Models are not in git (about 4 GB): copy them to `Android/data/com.kabir.unlox_hackethon/files/models/` (`llm/`, `stt/`, `tts/`, `embeddings/`); Settings > On this phone shows what is found. Build: `cd Unlox_Hackethon && gradlew :app:assembleDebug`. A debug APK is attached to the GitHub release.
