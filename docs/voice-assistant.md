# Voice assistant: what is built, what is not

Niharika's plan is in `Niharika/` (7 documents, no code). This page records how much of it was feasible on the demo laptop
(RTX 5060 8 GB, CPU-capable) and what was built on top of the tutor chat that already existed.

## Verdict per milestone

| Plan milestone | Verdict | Status |
|---|---|---|
| M1 grounded text chat | Feasible, and it already existed: `POST /api/lessons/{id}/chat` knows the lesson, the scene on screen and (now) the uploaded PDF / library passages | Done |
| M2 talkback (spoken answers) | Feasible with the same Piper / Indic-TTS voices as the lessons, one clip per reply | Done (whole reply, not sentence streaming) |
| M3 push-to-talk | Feasible: faster-whisper `small`, int8, on the CPU, so the GPU stays free for the LLM | Done (tap to start, tap to send) |
| M4 hands-free + barge-in | Possible later (needs a voice-activity detector in the browser) | Not built |
| M5 demo clips: template animation | Possible (planner already returns scene data) | Not built |
| M5 demo clips: LTX video model | Not realistic on 8 GB VRAM while the LLM is resident | Not built, not planned |

## How it works

```
mic (browser, tap) -> POST /api/stt?lang=hi&lesson_id=...  (raw webm/wav body)
                      faster-whisper small, CPU, int8, lesson title/terms as a vocabulary hint
                  -> {text, lang, duration_s}            (empty text = "I did not catch that")
text -> POST /api/lessons/{id}/chat {speak: true}
        tutor answers in English -> IndicTrans2/NLLB -> TTS (lesson voice for that language)
     -> {reply, scene, audio_url}  -> played in the browser; text is shown too
```

- Everything is local. Audio is held in memory, written to a temp file for decoding, and deleted.
- Languages: Whisper is good for English and Hindi; Tamil, Telugu etc. are weaker (Niharika's `03-speech-to-text.md` suggests
  AI4Bharat IndicConformer as a later per-language backend behind `stt.py`). The UI shows what was heard so a wrong transcript is visible.
- Microphone needs `http://localhost` or HTTPS (browser rule). On a second device over the LAN the mic is blocked.
- Setup: `pip install faster-whisper`, then `python scripts/download_models.py --stt` (about 460 MB into `models/whisper-small`).
  Without the model the mic button still shows and returns a clear error; typing keeps working.
- Health: `/api/health` -> `stt`.

## Metaverse

`metaverse/` (Niharika) is the quiz world. The web app opens it from Home ("Metaverse quiz world") and from a lesson
("Quiz in the metaverse"); the lesson's quiz scenes become gates in the world (`metaverse/src/lessonToWorld.ts`).
Reusing the voice tutor inside the metaverse stations is a possible next step.
