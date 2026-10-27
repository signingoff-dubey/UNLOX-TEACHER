# Problem Statement

## The Problem
Learners in India need short visual explanations of concepts in their own language, but good ones are online-only, English-only, or need paid cloud AI.

## Who Is Affected
Students (beginner/intermediate) on ordinary CPU-only laptops (8–16 GB RAM), often with poor or no internet, whose first language is not English.

## Why Existing Solutions Fail
- Depend on cloud LLM/TTS/translation APIs (cost, privacy, need internet)
- English-first; Indic voices are robotic or missing
- Generic video generators do not teach (no structure, diagrams, or code walkthroughs)

## Our Solution
Chanakya (UNLOX-TEACHER): a local-first, offline engine. Typed concept -> local LLM lesson plan (validated JSON) -> local multilingual narration (audio sets scene length) -> React/Revideo visual scenes -> 720p MP4 with captions.

## Definition of Success
- Judge-given prompt becomes a 30–90 s lesson, offline, live, in English + 2+ Indian languages
- Plays interactively in browser and exports 720p H.264 MP4 with captions
- Audio, captions and visuals stay in sync
- Every model/voice/asset licensed and listed in README
