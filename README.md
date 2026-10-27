# Blu Visual Teacher (UNLOX-TEACHER)

> Local-first, offline engine: typed concept -> 30–90 s narrated visual lesson in English + Indian languages -> in-browser player + 720p MP4.

Built for Codestorm: Unlox 24-Hour Hackathon.

## Latest Release: v0.1.0 (pre-Gate 1)

## Features
- Planned: concept input, Ollama lesson planner with JSON-schema check + fallback, 3 scene types, multilingual local TTS + captions, MP4/SRT export
- Done: shared lesson schema, sample lesson, Revideo frontend scaffold, model/font downloads
- Rules: no external AI API, fully offline, CPU-only, LLM returns data not code

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Planner | Ollama, Qwen2.5 7B / 3B instruct (Q4_K_M) |
| Schema | JSON Schema (`schema/lesson.schema.json`) |
| TTS | Piper (hi, te, mr, bn, ml), AI4Bharat Indic-TTS ONNX (en, ta, kn, gu) |
| Visuals / player | Revideo 0.11.0 (TypeScript), React player |
| Export | Revideo renderer + ffmpeg (H.264, 720p) |
| Backend | Python (teammate, in `backend/`) |

## File Structure
```
UNLOX hackethon/
├── backend/            # teammate: planner, TTS, pipeline, API
├── frontend/           # Revideo project: scenes, player, render
├── schema/             # shared lesson contract + sample lesson
├── fonts/              # Noto Sans (OFL)
├── models/             # TTS models, git-ignored
├── PLAN.md  PS - FINAL.txt  PS.txt
├── prd.md  problem_statement.md  pitch.md
├── progress.md  issues.md
├── .env.example  .gitignore
└── README.md
```

## Setup & Installation
```bash
# Ollama models (once, online)
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen3:4b

# Python env (TTS, HF CLI)
python -m venv .venv
.venv/Scripts/python -m pip install piper-tts onnxruntime huggingface_hub

# Frontend
cd frontend && npm install

# ffmpeg must be on PATH
cp .env.example .env
```
Model/voice files go in `models/` (git-ignored); fonts in `fonts/` (committed, OFL).

## Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| DISABLE_TELEMETRY | `true` stops Revideo PostHog pings (keeps run fully offline) | Yes |
| OLLAMA_HOST | Ollama URL | No |
| PLANNER_MODEL / PLANNER_FALLBACK_MODEL | Ollama model tags | No |
| MODELS_DIR / OUTPUT_DIR | Asset and output paths | No |

## How to Run
```bash
cd frontend && npm start     # Revideo editor/preview
cd frontend && npm run render
```
Backend run steps: see `backend/` once teammate pushes.

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

## Offline Test
Disable network, then run a full generation end to end before submission.

## Submission Checklist
- [ ] Repo with README, setup, licenses
- [ ] MP4 on judge topic (live), MP4 on our topic
- [ ] 5-min offline demo rehearsed
- [ ] Verified with network disabled

## Changelog
### v0.1.0 — 2026-10-27
- Docs, shared schema, Revideo scaffold, asset downloads
