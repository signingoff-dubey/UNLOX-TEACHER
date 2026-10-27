# Product Requirements Document

## Product Name
Chanakya (repo: UNLOX-TEACHER) — Codestorm: Unlox 24-Hour Hackathon

## Problem Statement (one line)
Turn a typed concept into a 30–90 s narrated visual lesson in English + Indian languages, fully offline.

## Target Users
Beginner/intermediate learners on CPU-only laptops; hackathon judges (primary audience for demo).

## Core Features (must-have)
1. Concept input: topic, level (beginner/intermediate), language, target duration
2. Lesson planner: local LLM via Ollama -> JSON matching `backend/app/schema.py`; schema check + automatic fallback to built-in sample lesson
3. Visual engine: reusable components, >= 3 scene types (Title Card, Diagram w/ labels+arrows, Code Walkthrough)
4. Multilingual narration: local TTS + captions in English (Indian accent) + >= 2 Indian languages, synced to visuals
5. Audio-first timing: scene duration = narration audio length + short pause
6. Interactive in-browser player (play/pause/seek, language switch)
7. MP4 export: 720p H.264, voiceover + burned-in captions and/or SRT
8. Continuous generation: scenes are made while the planner writes (first scene in about a second), long videos in 30 s parts, every episode of a course streams, extra videos can be asked for in the tutor chat (website and Android app)
9. PDF as a source: Markdown for pages with a text layer, OCR for scans and broken fonts, llava for pictures inside the PDF, one continuous progress bar
10. Stays responsive on an 8 GB laptop: priority, headroom gates, idle release, GPU fallbacks (docs/presentation-mode.md)

## Nice-to-Have Features
- Support every Indian language with an offline voice (see Languages below)
- Offline translation (IndicTrans2) so the planner writes English once
- Auto-select planner model by free RAM
- Per-language SRT download; script-correct fonts

## Platform / Environment
Windows/Linux laptop, CPU-only target (8–16 GB RAM), browser UI, Node + Python, Ollama, ffmpeg. No internet at run time.

## Constraints
- No external AI APIs (OpenAI/Gemini/Claude/ElevenLabs/Google Translate/cloud voices)
- Fully offline; Revideo telemetry disabled (`DISABLE_TELEMETRY=true`)
- LLM returns JSON data only, never code
- All models/voices/assets listed in README with valid licenses (no NC licenses; Meta MMS excluded)
- 24 h hackathon; Gate 1 (fixed sample lesson -> MP4) by hour 5

## Languages (offline TTS availability, verify per voice before demo)
| Languages | Engine | License |
|---|---|---|
| hi, te, mr, bn, ml | Piper voices | MIT engine; verify per-voice |
| ta, kn, gu, en | AI4Bharat Indic-TTS (int8 ONNX repack) | MIT (upstream); repack unverified |
| pa, or, as | Indic-TTS official zips (optional) | MIT |

## Success Criteria (judging weights)
Working end-to-end 25%, Teaching quality 20%, Visuals 15%, Languages 15%, Engineering 15%, Speed 10%.

## Out of Scope
Cloud anything, native mobile app, STT/Whisper, generative video, user accounts.

## Ownership
- Teammate: backend (`backend/`) + frontend (`web/`) — merged from origin/main
- This workstream: docs, model/asset setup, benchmarks, orchestration design (frontend `web/` is the teammate's, Remotion-based)
