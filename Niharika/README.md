# Voice assistant for Visual Teacher: plan

Status: draft for review. No code has been written. Nothing here is implemented yet.
Written against `main` at commit `de42195` (2026-10-27).

## Goal

Turn the chatbot in the right-hand panel into a voice assistant that:

1. Listens to the student (speech to text, "STT").
2. Answers in a spoken voice (text to speech, "TTS") and shows the answer as text.
3. Knows the topic being taught: the current lesson, the scene on screen, and the offline knowledge base.
4. Can show a short generated animation of what is being discussed, if a local video model (LTX) turns out to be practical on this hardware.

Everything must keep working offline on the demo laptop (RTX 5060 Laptop, 8 GB VRAM, 31.5 GB RAM). No external AI APIs.

## Assumption to confirm

The request said "TTS and HTTP". This plan reads "HTTP" as **STT (speech to text)**, because a voice assistant needs a listening half. If HTTP meant something else, for example "the chat should be served over HTTP endpoints", that is covered too: the transport design in `02-architecture.md` uses plain HTTP (with streaming) first and WebSocket second.

## Documents

| File | What it answers |
|---|---|
| `01-current-state.md` | What the codebase already has, and what is missing for a voice assistant |
| `02-architecture.md` | Components, API contract, transport, latency budget, GPU budget |
| `03-speech-to-text.md` | How the student's voice becomes text, offline, in English and Indian languages |
| `04-talkback-tts.md` | How answers are spoken back, interrupted, and kept in sync with the screen |
| `05-topic-knowledge.md` | How the assistant knows the current lesson and stays grounded in sources |
| `06-ltx-live-demo.md` | Research and a feasibility verdict on generating demo animations with LTX |
| `07-roadmap-testing-risks.md` | Milestones, acceptance tests, risks, open questions |

## Headline findings

- **There is no chatbot in the real app yet.** The chat panel exists only in design mockups (`frontend/visual-teacher-flow.html`, the Figma file). The backend has no chat, STT or on-demand TTS endpoint.
- **The ingredients mostly exist.** Retrieval (two stacks), a local LLM through Ollama, Piper and Indic Parler-TTS voices, NLLB translation, and a GPU scheduler are all in the repo. The work is wiring them into a low-latency conversation loop.
- **The newer retrieval stack is not used by anything.** `backend/app/rag/` (hybrid search with a reranker, multilingual embeddings, per-PDF scopes) is built and tested but not called by the planner or any endpoint. The assistant should be its first user.
- **The job queue must not carry chat.** `jobs.py` has one worker. A chat answer queued behind a 30-second lesson build would feel broken. Chat needs its own path.
- **Microphone access has a trap.** Browsers only allow the microphone on `localhost` or HTTPS. The app's LAN mode (`start.ps1 -Lan`) serves plain HTTP on a LAN address, so the mic would be blocked there. A local HTTPS option is needed.
- **LTX: not live, maybe on demand.** Real-time generation is out of reach on 8 GB. A short clip made on request may be possible with a small LTX-Video model, but that is unproven here and needs a one-day spike before any commitment. See `06-ltx-live-demo.md`.

## Recommended path (summary)

1. Text chat grounded in the lesson, streamed to the panel. (Highest value, lowest risk.)
2. Spoken answers, sentence by sentence.
3. Push-to-talk input.
4. Hands-free mode with interruption.
5. Demo clips: first a deterministic animation made from the existing scene templates, then LTX only if the spike passes.

Details and acceptance tests are in `07-roadmap-testing-risks.md`.

## Decisions needed from you

Collected in `07-roadmap-testing-risks.md`, section "Open questions". The four that block the most work:

1. Which screen hosts the chat: the main web app's right column, the metaverse overlay, or both?
2. Which languages must the voice work in on demo day (English only, English plus Hindi and Telugu, all nine)?
3. Is the demo run on the laptop alone, or from a second device over the LAN (which forces HTTPS for the mic)?
4. May the assistant unload the planner model to make room for a video model, accepting that chat is unavailable for a minute while a clip renders?
