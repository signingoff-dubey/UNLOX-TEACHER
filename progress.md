# Progress Log

## Current Version: v0.1.0
## Status: In Progress (pre-Gate 1)

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
