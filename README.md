# Visual Teacher

Type a concept and get a 30–90 s narrated, animated lesson in English plus Indian languages.
It plays in the browser and exports to MP4. Everything runs offline on one laptop.

```
concept ─► Ollama LLM ─► lesson JSON (schema-checked) ─► IndicTrans2 ─► Piper / Indic Parler-TTS
                                                                         │ audio length = scene length
browser player ◄── Remotion scene templates ◄── timed lesson JSON ◄──────┘ captions timed to audio
MP4 export     ◄── Remotion renderer (headless Chrome + bundled ffmpeg)
```

- **Data, never code:** the LLM only picks one of 10 templates (title, bullets, flow, cycle, compare, diagram, quiz, summary, **graph**, **code**) and fills in its text fields.
- **Narration first:** each scene's voice is synthesized before anything is animated, and the scene lasts exactly as long as that audio plus 0.5 s. Item reveals and captions are timed against the same audio.

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
| `backend/app/planner.py` | Ollama call with JSON-schema output, validation, retry, fallback |
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

The backend renders MP4s with Node, so copy the **whole `visual-teacher` folder** (backend + web) to that machine.

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
- Not yet run here: the Ollama planner, IndicTrans2 and Indic Parler-TTS. Test these on the models machine first.

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
