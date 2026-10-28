# Project Pitch

## One-Line Pitch
Type a concept, get a narrated visual lesson in your own language, built entirely on your laptop, offline.

## The Problem
Good explainer videos are English-first, cloud-dependent and not made for the learner's concept or language.

## Our Solution
A local pipeline: Ollama plans the lesson as validated JSON, local TTS narrates it in English and Indian languages, a React/Revideo engine animates it, and ffmpeg exports a 720p MP4 with captions. Audio sets scene length, so voice, captions and visuals never drift.

## Key Features
- Works with Wi-Fi off; no external AI API. A website on the laptop and a native Android app that runs everything on the phone
- **Plays while it is made**: the first scene is watchable in about a second after the planner starts; long videos are planned in 30 second parts and added to the player as they are written; every video of a course streams too
- Ask the tutor chat for "one more video on ..." and it appears in the chat with its first frame, joins the playlist and plays
- 15+ scene types: title, bullets, flow, cycle, compare, diagram, network, quiz, summary, graph (maths curves), code walkthrough
- English + eight Indian languages (Hindi, Telugu, Marathi, Bengali, Malayalam, Tamil, Kannada, Gujarati), with script and back-translation checks
- PDFs: pages with a text layer are read as Markdown (headings, lists, tables), broken fonts are detected and sent to OCR, pictures inside the PDF are described by llava
- Study tools (flashcards, quiz, mind map, notes, glossary), spaced repetition and weak spots, teach-it-back scoring, worksheets and question papers, offline lesson file for a USB stick
- Learnverse: a walkable 3D world the local AI builds for any topic, with quiz gates, points, a shop, a jump button
- Built for an 8 GB laptop: resource limits, GPU fallbacks and idle model release keep a 5-video course from freezing it

## Target Audience
Hackathon judges (Unlox / Codestorm), then students and teachers on low-spec laptops.

## Tech Stack
Ollama (Qwen2.5 7B, llava, nomic-embed), IndicTrans2 / NLLB, Piper + AI4Bharat Indic voices, faster-whisper, PyMuPDF + pymupdf4llm + Tesseract + Unlimited-OCR, FastAPI, React + Remotion, three.js, ffmpeg, Python; Android: Kotlin + Compose, Gemma (LiteRT-LM), sherpa-onnx (Piper, Whisper), ML Kit.

## Why Us / Why Now
Open Indic TTS and small instruct models now run on CPU; privacy and offline use matter for classrooms.

## Demo / Screenshots
TBD (add rendered MP4s under `samples/`)

## Team
| | |
|---|---|
| **Team name** | The Last Commit |
| **Members** | Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty |
| **College** | RV University, Bengaluru |
| **Course** | B.Tech (Hons) |
| **Branch** | Computer Science Engineering |
| **Year of study** | 2nd year |

Built for the Unlox hackathon.
