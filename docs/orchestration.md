# Orchestration: streaming pipeline (speed-first)

Idea: JSON writer and frame builder run **at the same time** and see each other's output. Implementation: one shared **lesson doc** (blackboard) + an **event stream**; workers subscribe and react. Not two chatting LLMs.

## Why not two LLM agents
- CPU-only: two LLM calls share the same cores, so no real speedup, only contention.
- Frame building has fixed templates (title / diagram / code). Filling a template from JSON is deterministic code: instant, zero tokens, and keeps "LLM returns data, never code".
- So: **1 LLM writer** (+ optional tiny outliner) and **deterministic workers** for everything else.

## Workers and events
| Worker | Type | Listens to | Emits |
|---|---|---|---|
| Outliner (optional) | LLM, ~100-150 tokens: title + `[{id,type,name}]` | `request` | `outline` |
| Skeleton builder | code | `outline` | `scene_skeleton` (blank scene named, e.g. "s2 Diagram: Loop flow") |
| Scene writer | LLM, streamed JSON, incremental parse | `outline`, earlier `scene_ready` (context: headings, narration) | `scene_ready` per completed scene object |
| Frame filler | code | `scene_ready`, `audio_ready` | `scene_filled`: content into the skeleton, then duration |
| Translate+TTS | IndicTrans2 / Piper / Indic-TTS | `scene_ready` | `audio_ready` per scene+language (duration_s) |
| Validator | code | `scene_ready` | `scene_invalid` -> swap in fallback scene, keep going |
| Exporter | Revideo render + ffmpeg | all scenes `audio_ready` | `done` (mp4, srt) |

Shared context: every worker reads the lesson doc (heading names, scene order, ids). The writer sees the outline and previous scenes so narration doesn't repeat; the frame filler sees names and types as soon as they exist.

## Timeline (what the learner sees)
1. t~0: request -> outline (seconds) -> blank named scenes appear in the player
2. scene 1 JSON completes -> its card fills in; its TTS starts while scene 2 is still being written
3. each `audio_ready` fixes that scene's length (audio + pause) -> captions timed
4. last scene ready -> render. Revideo can split a render across workers.
Time-to-first-visual drops to seconds; total time ~ LLM time + last scene TTS + render, rather than the sum of all stages.

## Rules
- Audio sets scene length. A scene is "playable" only after its `audio_ready`; until then it shows a skeleton.
- Any schema failure on one scene replaces just that scene with a fallback; whole-lesson fallback only if the outline fails.
- Pin CPU threads: LLM gets most cores, TTS 2, so they do not thrash.

## Knobs to benchmark (do not assume)
- Single streamed call vs outline + per-scene calls (per-scene repeats prompt prefill; Ollama KV cache may hide it if the prefix is stable).
- `OLLAMA_NUM_PARALLEL` 1 vs 2 for outline + writer.
- 3B vs 7B planner: tokens/s and JSON validity on CPU-only.
- Piper vs Indic-TTS real-time factor per language.

## Decision
Start with: single streamed LLM call + incremental JSON parse + per-scene TTS overlap + deterministic frame filler. Add the outliner only if time-to-first-visual matters in the demo.

## Tools to adopt (scout report; licenses via `gh api`, re-verify before submission)
| Need | Pick | License |
|---|---|---|
| Constrained JSON | Ollama `format` = JSON schema | MIT |
| Streaming scene parse | json_repair / partial-json-parser (Py), partial-json (JS, verify license) | MIT |
| Diagram layout | dagre | MIT |
| Code highlight | shiki (per-line tokens) | MIT |
| TTS runtime (optional) | sherpa-onnx; test Indic voices first | Apache-2.0 |
| Word timing | ctc-forced-aligner (check Indic CTC model) or Piper phoneme durations | BSD-2 |
| Fallback LLM serving | llama.cpp (GBNF, speculative decoding) | MIT |
Excluded: aeneas (AGPL), MMS-TTS (NC), elkjs (EPL-2.0, unconfirmed), Qwen2.5-3B (research license).

## Measured on this laptop (2026-10-27, Ollama 0.23.1, schema-constrained `format`, ~110 tokens out)
| Model | Device | Speed | JSON valid |
|---|---|---|---|
| qwen2.5:7b q4_K_M | RTX 5060 GPU | 62.7 tok/s | yes |
| qwen2.5:7b q4_K_M | CPU only | failed to load: only 3.7 GB RAM free of 15.4 | - |
| qwen2.5:3b q4_K_M | GPU | 104.6 tok/s | yes |
| qwen2.5:3b q4_K_M | CPU only (Core Ultra 9 275HX) | 11.2 tok/s | yes |
A ~700-token lesson takes ~60 s at 11 tok/s on CPU (3B), ~11 s on GPU. Streaming scene-by-scene hides most of the CPU wait. Close Chrome etc. before CPU runs; on an 8 GB judge laptop use <=3B.
