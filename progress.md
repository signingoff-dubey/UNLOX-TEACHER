# Progress Log

## Current Version: v0.3.0
## Status: In Progress (pre-Gate 1)

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
