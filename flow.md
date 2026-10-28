# Flow

What happens, step by step, from a click in the browser to frames on the screen: which endpoint is called, which job runs, which
model is asked what, and what is written to disk. For the parts and how they are scheduled, see [architecture.md](architecture.md).

Model shorthand: **LLM** = Qwen2.5-7B in Ollama, **Vision** = LLaVA 7B in Ollama, **Translator** = IndicTrans2 (or NLLB),
**Voice** = Piper / Indic-TTS / Parler.

---

## 1. App flow (what the learner sees)

```
 Home ──type a topic / attach a photo or PDF──► pick languages, length, mode, Flash/Pro, 1 video or a course
   │
   ▼
 Create ──► Lesson page opens with a progress card (5 stages, real percentages)
   │            Flash: the player starts on scene 1 after ~6-18 s and scenes are added while the rest is written
   │            Pro:   nothing plays until the whole video is planned and checked
   ▼
 Lesson page
   ├─ Player (Remotion): scenes, captions, language tabs, auto-advance to the next video of a course
   ├─ Ask the tutor (text or voice) ── "make one more video on X" adds a video to the course
   ├─ Study tools: flashcards, quiz, mind map, study guide, FAQ, glossary, timeline, Meta quiz (3D)
   ├─ Take away: MP4, subtitles, transcript, narration .mp3, lesson file (USB), worksheet, question paper
   └─ Teach it back, Review (spaced repetition), Rewards
 Learnverse (sidebar) ── tunnel animation ► Start page over the live 3D world ► topic ► walk, quiz gates, shop
 Library ── every lesson and course made on this laptop, import a lesson file
```

---

## 2. Making one lesson (`POST /api/lessons`)

```
Browser                         Backend                                                      Models
───────                         ───────                                                      ──────
POST /api/lessons ───────────► main.py validates (languages, 30-240 s, mode, quality)
◄── {job id} ────────────────── jobs.submit("lesson", pipeline.build_lesson)
poll GET /api/jobs/{id} ──────► stage + progress (0-1, never backwards)

                                pipeline.build_lesson  (holds the GPU slot, shared)
                                 1  content.clean_topic       "teach me about dsa in java" → "DSA in Java"
                                 2  vision.context            the photo's reading (read now if not yet) ─────────► Vision
                                 3  memory.context            related lessons the learner already has
                                 4  knowledge.retrieve / rag  top passages (your PDF first) ───────────────────────► nomic-embed / e5 + reranker
                                 5  PLAN (see 2.1)            lesson JSON, streamed ───────────────────────────────► LLM
                                 6  content.dedupe_plan, strip_analogies   repeats and extra comparisons removed
                                 7  director.direct           weak scene types replaced ───────────────────────────► LLM (one scene at a time)
                                 8  review.review             short narration lengthened, Python parse-checked ───► LLM (code repair)
                                 9  facts.check_plan          claims checked (see 2.3) ────────────────────────────► LLM
                                10  first language: translate + narrate (see 2.4) ─────────────────────────────────► Translator, Voice
                                11  save lesson.json  ◄── the page now has the finished lesson
                                12  jobs.submit("langs", finish_languages)   the other languages, side by side
                                13  studio.prebuild           study tools written in the background ──────────────► LLM
GET /api/lessons/{id} ◄──────── lesson.json (re-read while "pending" languages are still being made)
```

### 2.1 Planning (`planner.py`, `longplan.py`)

| Case | What is asked of the LLM |
|---|---|
| **Flash, ≤ 90 s** | One streamed call: a subject-aware prompt (maths → graph scenes, programming → code scenes in the language named, trees/structures → network scenes) + retrieved passages + memory. Returns `{title, scenes[]}` |
| **Flash, > 90 s** | `longplan.outline`: a title and one goal per part (2-3 parts of ~40 s). Then each part, **in order**, is planned as "part k of n of one video" and told what the earlier parts really contain (`content.taught_summary`). Only part 1 has a title card; only the last has the quiz and summary |
| **Pro** | `longplan.beat_sheet`: the whole video scene by scene (heading, template, the one point it teaches). The first minute is written in one call; each further minute is patched on in a call that sees the whole outline and the full text so far |

After every answer: `schema.normalize` repairs types; `quality_issue` looks for repeated headings/items/code, placeholder text,
a technical topic shown only as text, too many everyday comparisons, an unanswered question. If one is found, the call is repeated
with that feedback (Flash: at most once, and short narration is left to the reviewer; Pro: up to three times).

### 2.2 Flash streaming (`streaming.py`)

```
LLM tokens ──► ScenePreview.feed(text so far) ──► extract_scenes: complete scene objects
                                                     │
                       worker thread, in order ◄──────┘
                       normalize → translate (first language) → narrate → append to the draft track
                       write lesson.json with building: true  ──► the player picks it up on its next poll
                       other languages: pre-translated into the cache while the planner is still writing
```

- Every part of a long video streams token by token; later parts never show a title card, and only the last shows its quiz and summary.
- If the planner starts over (a retry), the scenes already on screen stay and the new answer continues after them.
- When planning, checking and fact-checking are done, the preview stops writing and the final lesson replaces it (voices and
  translations of the scenes already made come from the cache, so this is quick).
- The player waits when it runs out of scenes and carries on by itself when more arrive.

### 2.3 Fact check (`facts.py`, English plan, before translation)

1. **Calculation**: arithmetic and linear equations are worked out; a count that does not match its list ("7 colours" + six names) and
   well-known lists (rainbow, planets, continents, oceans, senses) are checked against the real list.
2. **Sources**: each statement is compared with passages about it; a verdict only counts if the LLM quotes words that really are in the source,
   and a focused second question must agree.
3. **Second opinion**: without a source, the LLM may only say "wrong" if the opposite question agrees.
4. **Repair**: a correction must pass the same check, or the statement is removed. Time budget: 50 s (Pro 100 s). The report is saved with the lesson.

### 2.4 Languages (`translate.py`, `fidelity.py`, `tts.py`, `expression.py`, `captions.py`)

```
English plan ─► translate_batch (every heading, narration, item; batched by length; cached) ─► Translator
             ─► fidelity.verify: right script? back-translate and compare (NLLB) ─► repair with the LLM, else keep English
             ─► per scene: expression.tone_for_scene (title excited, quiz curious, summary calm, warning serious ...)
             ─► tts.synthesize per sentence with its delivery (speed, pauses, emphasis) ─► Voice (Piper → Indic-TTS → Parler → silent)
             ─► scene duration = audio + 0.5 s;  captions.time_captions spreads the words over the audio
```

The first language is made inside the lesson job (the player can start). The others run in the `langs` job **side by side**
(`LANG_WORKERS=3`): translation takes turns on the shared model, voices record at the same time. Each language is added to
`lesson.json` as soon as it is ready. The lesson is sized for the slowest language picked (words per second per language).

---

## 3. A course (`POST /api/playlists`)

```
playlist.start ─► playlist.json (status planning)  ◄── the page has an id at once
playlist.build:
  design_curriculum ─────────────────────────────────────────────────────────► LLM (2-3 episodes: title + focus; "Auto": concepts.py)
  episode 1: build_lesson(series = course context)         ─┐
  episode 2: starts when episode 1 has finished planning,   │ two episodes in flight (PLAYLIST_WORKERS=2), sharing the GPU slot;
             told what episode 1 taught                     │ Ollama queues their LLM calls, so episode 2 plans while
  episode 3: ...                                           ─┘ episode 1 translates and records
  each episode reports lesson_id as soon as its first scenes exist ─► the course page can open it
  studio.prebuild(episode 1) when the course is done
```

The player plays episode 1 while the next is built; at the end of an episode it moves to the next one, or waits for it.

---

## 4. Tutor chat (`POST /api/lessons/{id}/chat`)

1. `videochat.detect` checks the words first ("make one more video on tides"): if it is a video request, a new episode is added to
   the lesson's course and built in the background (no LLM call for the detection).
2. Otherwise `chat.py` builds the context: the English plan (every scene's heading, narration, points, code), the scene being watched,
   passages from the uploaded PDF. **LLM** answers in English (350 tokens max), then the **Translator** puts it in the learner's language.
3. Voice questions: `POST /api/stt` → **faster-whisper** → text → the same flow; the reply can be spoken with the lesson's voice.

---

## 5. Study tools (`/api/lessons/{id}/studio[/{kind}]`)

`studio.py` keeps a queue (urgent = clicked, background = prebuilt). For each tool: the lesson text → **LLM** `ask_json` with that tool's
schema (flashcards, quiz, mind map, study guide, FAQ, glossary, timeline) → **Translator** for other languages → cached per lesson,
kind, size, difficulty and language. Background tools wait while a lesson, course or language job is running, or memory is short.
Progress is the model's token stream.

---

## 6. Worksheet and question paper (`POST /api/papers`)

```
paper.generate (export job):
  source_text: every scene's heading, narration and points + 4 reference passages
  per section (MCQ, short, long): LLM ask_json "write N questions of this kind" ─► clean: real questions only, 4 distinct options,
                                  answer index in range ─► fewer than asked? ask again for the rest (up to 3 calls), never repeating
  progress = questions the model has finished writing ("Writing question 7 of 17")
  selected language ≠ English: Translator, a few questions at a time ("Translating into Hindi: question 7 of 17")
  save media/papers/{id}.json
Browser: popup ─► GET /api/papers/{id}/html?download=true        student copy (.html file)
                  GET /api/papers/{id}/html?key=true&download=true answer key
                  GET /api/papers/{id}/html                        open to print / save as PDF
```

Marks are fixed per kind (MCQ 1, short 3, long 8), so the total is always right. The page bundles Noto fonts, so every script prints.

---

## 7. Photos, PDFs and homework

| Input | Flow |
|---|---|
| **Photo** (`POST /api/images`) | Answers at once with an id; the lesson job reads it first if needed: **Vision** describes it (cleaned, deduplicated, max 15 lines), cached next to the image. In a course, each episode gets only the lines about it |
| **PDF** (`POST /api/uploads`, `upload` job) | Pass 1: text-layer pages to Markdown (PyMuPDF + pymupdf4llm), chunked, embedded with **e5**, searchable at once. Pass 2 (background, yields to lessons): scanned pages through **Tesseract**, then **Unlimited-OCR** when the GPU is idle; pictures described by **Vision**; study notes written by the **LLM** per window of pages. Lessons can target "chapter 4" or "pages 120-135" |
| **Homework** (`POST /api/homework`) | **LLM** lists the questions from the photo/PDF text; the lesson teaches the method; the **LLM** writes the answers into a separate file (`/api/homework/{id}/download`) |

---

## 8. Take away

| Action | Flow |
|---|---|
| MP4 (`POST /api/lessons/{id}/export`) | `exporter.py` → `node web/render.mjs` (Remotion bundles the same templates, headless Chrome draws frames, ffmpeg encodes H.264 + AAC, 720p/1080p) |
| Course MP4 | Each episode rendered, then joined by ffmpeg without re-encoding |
| Subtitles / transcript | `GET /api/lessons/{id}/subtitles?fmt=srt|txt` from the timed captions |
| Narration | `POST .../podcast`: the scene clips joined into .mp3/.wav |
| Lesson file | `GET .../bundle`: `.chanakya.zip` with lesson.json, audio and its own player; `POST /api/bundle/import` on another laptop |

---

## 9. Learnverse

```
Sidebar "Learnverse" ─► MetaverseLayer: tunnel animation (TunnelTransition) while the 3D chunk loads
  ─► the world mounts behind the Start page in intro mode: only the 3D scene, camera circling (no topic card yet)
  ─► Start ─► the topic card fades in: pick a ready-made world or type a topic
        typed topic ─► POST /api/metaworld ─► LLM writes the world as data (zones, stations, quizzes) ─► engine builds it
  ─► walk (keyboard or the on-screen pad), read stations (+10), pass quiz gates (points by tries), coins, shop and wardrobe
        points saved to /api/metaverse/save
Meta quiz (study-tool bar) ─► POST /api/metaquiz: a world from the lesson + every study tool made for it
```

---

## 10. Every model call at a glance

| Step | Model | Input → output | Typical time (RTX 5060, 8 GB; approximate, from the logs) |
|---|---|---|---|
| Course outline | LLM | topic → 2-3 episode titles + focus | 5-10 s |
| Long-video outline / Pro beat sheet | LLM | topic → parts or beats | 3-8 s |
| Lesson plan (per part) | LLM, streamed | prompt + passages + memory → scene JSON | ~10 s per 40 s part, first scene in 1-2 s |
| Director | LLM | one weak scene → a better scene | 2-4 s each |
| Code repair | LLM | Python that does not parse → fixed lines | 2-3 s |
| Fact check | LLM | claim + passages → verdict + quote, correction | up to 50 s (Pro 100 s) |
| Photo reading | Vision | image → description | ~13 s cold, faster warm |
| Embeddings | nomic-embed / e5 | text → vector | ms |
| Translation | Translator | strings → strings (batched, cached) | 3-30 s per language |
| Back-translation | NLLB | translation → English | part of the above |
| Narration | Voice | sentence + delivery → wav | ~0.1-0.5 s per sentence |
| Tutor | LLM + Translator | plan + scene + question → answer | 3-8 s |
| Study tool | LLM | lesson → schema JSON | 10-30 s |
| Paper | LLM per section | lesson → N questions | ~3 s per question |
| World | LLM | topic → world JSON | 30-60 s |
| Speech to text | faster-whisper | audio → text | 1-3 s |

Measured end to end: a 30 s English + Hindi lesson in 30 s; a 2 x 2 min English + Hindi course in 171 s.
