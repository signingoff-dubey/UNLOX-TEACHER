# Project Pitch

## One-Line Pitch
Type a concept, get a narrated visual lesson in your own language, built entirely on your laptop, offline.

## The Problem
Good explainer videos are English-first, cloud-dependent and not made for the learner's concept or language.

## Our Solution
A local pipeline: Ollama plans the lesson as validated JSON, local TTS narrates it in English and Indian languages, a React/Revideo engine animates it, and ffmpeg exports a 720p MP4 with captions. Audio sets scene length, so voice, captions and visuals never drift.

## Key Features
- Works with Wi-Fi off; no external AI API
- 3 scene types: title, labelled diagram, code walkthrough
- English + many Indian languages (Hindi, Telugu, Marathi, Bengali, Malayalam, Tamil, Kannada, Gujarati)
- Schema-checked planner with automatic fallback lesson
- In-browser player + 720p MP4 / SRT export

## Target Audience
Hackathon judges (Unlox / Codestorm), then students and teachers on low-spec laptops.

## Tech Stack
Ollama (Qwen2.5), Piper + AI4Bharat Indic-TTS, Revideo (TypeScript), React, ffmpeg, Python, Node.

## Why Us / Why Now
Open Indic TTS and small instruct models now run on CPU; privacy and offline use matter for classrooms.

## Demo / Screenshots
TBD (add rendered MP4s under `samples/`)

## Team
Unlox hackathon team (frontend/docs + backend split).
