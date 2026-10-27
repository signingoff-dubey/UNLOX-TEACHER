# Progress Log

## Current Version: v0.14.2
## Status: In Progress (pre-Gate 1)

---

## [v0.14.2] — 2026-10-27
### What's New
- **A 5-video course no longer dies on "CUDA error: out of memory"**. Cause: that error is sticky (the GPU cannot be used by torch again in the process) and the cleanup after a failed translation (`_free_gpu`) raised it again, so no fallback ran and all 5 episodes failed with the same text after 384 s. Now: a CUDA error switches every torch model to the CPU for the rest of the process (`config.mark_cuda_broken`), cleanup never raises, the translator starts on the CPU when under 1.8 GB of VRAM is free (the language model holds most of the 8 GB), and a course episode that hits a CUDA error is retried once
- **Long videos stream too**: a 2 minute video is planned in 4 parts of 30 s (was 3 of 40 s). Part 1 is read token by token and its scenes are made while it is written; parts 2, 3 and 4 are added in order as each is finished, so the player starts after the first scenes and the rest follows. Measured on this laptop (cold model): first scenes watchable at 13 s, 5 scenes at 26 s, 15 scenes at 35 s, job done at 63 s
- **Courses**: episode 1 opens and plays while it is still being made (`preview` on the episode, `lesson_id` set early); the episode rail shows "playing, more coming..." and lets you pick it
- **Videos play by themselves again**: the position kept for a language switch (`resume`) was never cleared and was not tied to a lesson, so after one switch every later lesson or episode started at that old position and, if it was paused then, did not play. It now belongs to the lesson it was set in. When the browser has had no click yet (a reload) the video starts muted instead of not starting

- **The other languages are no longer starved by the study tools**: flashcards, quiz and the rest (background, 3 workers) started on the GPU the moment the English video was done and shared the card with the Hindi translation, which then took more than 9 minutes and had not finished. They now wait for the language job too (`jobs.active(..., "langs")`). Same 2 minute video: Hindi in 74 s

- **Root cause of the hangs found and fixed**: PyTorch's GPU allocator reserved 10.3 GB while translating (1 GB in use), beyond the 8 GB card, so Windows spilled into RAM (22 GB committed, 0.2 GB free). Now capped (`PYTORCH_CUDA_ALLOC_CONF`, `TORCH_VRAM_FRACTION=0.35`) and the cache is released after every batch: reserved 0.41 GB, process 4.4 GB in the same test
- **Resource manager** (`resources.py`) so a 5 video course cannot hang the laptop: the backend runs at below-normal priority (the desktop, browser and slides win), the maths libraries use half the cores, background work (extra episodes, study tools) waits while free RAM is under 1.5 GB or free VRAM under 0.8 GB, and speech recognition and the translator are released after 10 quiet minutes. Before, start-up put the translator, Whisper medium and every Piper voice on the 8 GB card next to the 5.5 GB language model, so the card was permanently full (desktop stutter, then CUDA out of memory). Now: Piper on the CPU (`PIPER_CUDA=0`), Whisper loads on the first spoken question (on the GPU only if 3 GB are free, else the CPU), study tools are not queued for every course episode (14 tools x 5 episodes of language-model work), only for episode 1 once the course is done, and 2 study builders instead of 3. `/api/health` reports free RAM and VRAM

- **Measured, the scenario that failed** (5 videos, 2 min each, English and Hindi, intermediate, this laptop): all 5 episodes ready in 496 s (it failed after 384 s before); episode 1 watchable at 25 s and ready at 72 s, then one more roughly every 90 s; lowest free RAM 4.5 GB (it was 0.2 GB), peak VRAM 7.1 of 8.15 GB, PyTorch's share of the card at most 1.97 GB (it was 10.3 GB), backend memory 8.9 GB (it was 22 GB)

### Known Issues
- The finished plan is still checked afterwards (director, reviewer), so already-playing scenes can change a little when the final lesson replaces the preview
- Episodes 2 and up of a course are shown when complete (only episode 1 streams); two episodes plus the language model and the translator share 8 GB of VRAM, so on the CPU fallback Hindi takes longer
- Video length: the model writes about 90 s of narration for a 120 s request

---

## [v0.14.1] — 2026-10-27
### What's New
- **Learnverse builds a world for any topic** (`metaworld.py`, `POST /api/metaworld`): type a topic and the local model writes four stations with questions (data only; cleaned, translated for other languages). A "Building your world" screen with animated blocks and live progress shows while it works (about 25 s for a real topic). The topic box no longer defaults to Java: ready-made worlds (Java, photosynthesis, water cycle, the open lesson) start at once, everything else is built by the AI
- **No E key**: quiz gates open their question by themselves when you reach them, so a learner who knows the answer just answers. "Read the station first" and "Not yet" are offered on the question; stations are optional and tappable ("Read: ...")
- **Jump**: Space bar and a Jump button (also on touch)
- **Points and purchases are kept** in the browser and on the backend (`GET/POST /api/metaverse/save`, newer revision wins), so another address (localhost vs 127.0.0.1, a LAN IP) or cleared browser data no longer loses them. Verified: wiped the browser copy and the 265 points came back from the server
- **Home page**: the "+" (add photo) button sits with the Create button on the bottom row, both 46 px high, centred on the text when the box shrinks; the textarea height rule works again (it was ignored inside the column wrapper)

### Known Issues
- Worlds are English first, then translated with the lesson engine; Indic fonts on in-world billboards still fall back to the system font
- The standalone `metaverse/standalone/learnverse.html` and the copy under `Dhiraj/` are not updated

---

## [v0.14.0] — 2026-10-27
### What's New
- **Scenes play while they are made** (web and phone). Before, the lesson was planned, narrated and saved whole, so nothing could be watched until the end. Now the planner's JSON is read as it streams (`streaming.py`): each finished scene is cleaned, translated, voiced and published to `lesson.json` (marked `building`), the player starts on scene 1 and the rest is added as it arrives. Measured: scene 1 watchable about 6 s after the click (a whole 60 s lesson took about 18 s), scenes 2-6 within 3 s of it. The player waits at the end of what exists and carries on by itself. Phone: `ScenePreview` does the same with Gemma (`StreamScenes.kt`)
- **Progress per stage** on the website (Plan, Design the visuals, Translate, Narrate, Finish; one row per video for a course), as on the phone
- **Study tools build in parallel** (3 workers, `STUDIO_WORKERS`): flashcards, quiz, mind map, study guide, FAQ, glossary and timeline overlap instead of queueing
- **Profile page** with name and age; the age shapes the planner's and the tutor's wording (`learner.py`)
- **Spaced repetition** (`srs.py`, SQLite): SM-2 over every flashcard and quiz question; Review page, "due today" card, rewards on remembered cards
- **Weak spots and Revise mode**: wrong quiz answers are logged per topic, right ones clear them; a Revise lesson gets the topics as the planner's focus
- **Misconception scene**: the planner's `common_mistakes` become one compare scene before the closing quiz
- **Network scene**: the model lists boxes and arrows, `layout.py` places them (layered, deterministic); drawn by a new Remotion template
- **Language fidelity** (`fidelity.py`): after translation each text is checked for the right script (mixed or Latin text is re-translated by the local model) and, with NLLB, back-translated and compared with the original; each scene carries its report
- **Glossary "Hear it"**, **subtitle-only** (srt, vtt, transcript) and **narration-only** (mp3 or wav) exports
- **Offline lesson file** (`bundle.py`): `.chanakya.zip` with the lesson, audio, captions and a standalone `player.html`; import on another computer from Library
- **Worksheet and question paper** (`paper.py`): MCQ, short, long, fixed marks, student and teacher copies, printable with the Noto fonts
- **Teach it back** (`teachback.py`): explain in your own words (typed or spoken); embedding similarity gives a score and the missed points. Threshold measured on a real lesson (off-topic 0.56 at most, paraphrase 0.75, cut at 0.62)
- **Resumable jobs** (`resume.py`): jobs are kept in SQLite; after a restart, lessons with languages still to make are finished from their saved plan, cut-off lessons and courses are closed cleanly (verified live)
- **Android**: animated scene templates, seek bar, full screen, PDF tile, videos x length, per-stage progress, progressive scenes, Piper voices working (sherpa-onnx 1.13.8)

### Known Issues
- The finished plan is checked (director, reviewer) and can lengthen narration, so scenes already shown may change when the final lesson replaces the preview (50 s vs 33 s in one test)
- Scenes preview only for single lessons up to 90 s (longer ones are planned in parts, and course episodes are made whole)
- Paper generation takes about 90 s on the 7B model; teach-back needs English explanations (the embedding model is English)
- Course from a PDF on the website (chapters as episodes) is not built; the phone has it
- The progressive-scene phone build is not tested on the device

### Future Scope
- Course from a PDF on the website; MiniLM search, MP4 export on the phone

---

## [v0.13.0] — 2026-10-27
### What's New
- **Progress page** (`#/progress`): streak heatmap (last 18 weeks), lessons / right answers / tutor questions / days counted for the week, month or year, and XP per day (or per month). New `GET /api/rewards/history` (`rewards.history`, test added)
- **Settings page** (`#/settings`): name and daily goal, spoken answers, opening animation (the intro now respects it), and what is installed on this computer (from `/api/health`). Both pages are in the sidebar
- **Voice ripple and wave** in the tutor chat: the mic spreads a circle with a ring across the panel and shows the live waveform (`VoiceRipple.tsx`), same as the Android app
- **Android app** (`Unlox_Hackethon/`, native Kotlin + Compose, all on the phone): the 8 Figma screens plus study tools, homework, rewards, settings and a profile with name and age; back stack with transitions; the web intro on every launch; book-only launcher icon. Real engines: Gemma (LiteRT-LM) plans lessons and tutors, Piper voices (sherpa-onnx 1.13.8) narrate, Whisper + Vosk (language-ID approach from NDialRecorder) hear, ML Kit translates and reads photos. Per-stage progress with translating and narrating in parallel

### Known Issues
- Android: PDF as a lesson source, MP4 export and the MiniLM search are not built yet; Tamil and Kannada narration needs the phone's own voice installed
- The running backend must be restarted to serve `/api/rewards/history`

---

## [v0.12.0] — 2026-10-27
### What's New
- **Voice and tutor detect the language**: speak or type in Hindi, Telugu, Tamil... and the answer comes back in that language, spoken in that voice. Speech: Whisper picks among our 9 languages (`stt._detect`, ~0.1 s on the GPU); typed text: by script (`languages.detect_text_language`). Ask in Hindi while watching a Marathi video and Devanagari is treated as Marathi
- **Latency**: models warm up in the background at start (translation, every voice, speech recognition, the language model); chat translation uses greedy decoding; Whisper no longer re-decodes at higher temperatures (Telugu 10 s -> 0.35 s) and ignores the English vocabulary hint for other languages (that hint was turning Hindi speech into English text). Warm tutor round trip: English ~2.5 s, Tamil 3-5 s, Hindi 5-6 s
- **Languages one by one**: the first language of a lesson is playable as soon as it is ready (a 30 s test: 13 s); the others are made in the background and appear as tabs the moment each is done (`pipeline.finish_languages`, `pending`/`failed` in lesson.json, the page polls). One failing language does not stop the rest
- Video content in the chosen language: every heading, point, label and caption is translated and the voice is that language (checked on a Hindi and a Telugu track)

### Known Issues
- Speech recognition now defaults to Whisper **medium** (small is the fallback): Hindi words clearer ("खीजता" for "खींचता" instead of "खीछता"), still 0.5-0.9 s per question, GPU memory 6.5 of 8.15 GB with the language model, translation and voices loaded. Telugu and Tamil words are still rough on the synthetic test voices; a real voice is untested. Scanned-PDF OCR (6.8 GB) next to it was not re-tested
- Hindi tutor answers still take 5-6 s (translation + a longer voice clip)

---

## [v0.11.0] — 2026-10-27
### What's New
- **Intro splash on every page load** (`web/src/shell/Intro.tsx`, logo drawing in `logoPaths.ts`, from Niharika's `intro-animation/`); click or Esc skips it; reduced-motion skips it
- **Wordmark in the top-left corner**: the logo mark is gone, the sidebar shows only the name in the splash lettering (`Wordmark.tsx`); icon-only sidebar shows its first letter
- **Voice agent faster**: Whisper now runs on the GPU (cuBLAS/cuDNN 9 DLLs live in torch's `lib` folder, added to the DLL path in `stt.py`, CPU fallback kept); recordings decode in-process (WAV with the standard library, webm/opus with PyAV) instead of starting ffmpeg. A short question: 3.4 s + 1.4 s decode -> 0.25 s

## [v0.10.0] — 2026-10-27
### What's New
- **Photos**: a plus button in the prompt box attaches up to 4 photos; llava reads them on this computer (`backend/app/vision.py`, `POST /api/images`) and the lesson uses what they show
- **Modes**: Explanation, Study, Homework pills in the settings card; Study adds key terms, a memory trick and a recall quiz, Homework teaches only the concepts needed and never gives answers inside the video
- **Homework answers**: choosing Homework with a PDF or photo also writes a Markdown answer file question by question (`backend/app/homework.py`), viewed in the browser while it grows (`#/homework/<id>`) and downloadable as .md. Nothing guesses whether a file is homework
- **"Auto" video count**: the AI lists the concepts first (`backend/app/concepts.py`, rules plus worked examples, capped at 8) and makes one video per concept
- **Parallel long videos**: parts of a 2-4 minute video are planned two at a time from the outline (`longplan.py`); 2:30 test: plan 120 s -> 66 s, length 211 s -> 156 s
- **Lesson page**: notes are the left column, the sidebar collapses to icons while a lesson is open
- **Mind map redone**: two-sided SVG tree with curved coloured branches (replaces Mermaid); click a box for its notes and an inline "Explain this" answer from the tutor
- Fixes: page no longer scrolls down at every scene (notes and chat scrolled with scrollIntoView); Hindi falls back GPU -> CPU -> Ollama before English, English text is never read with a Hindi voice; backend log at `media/backend.log`; steps strip above the video redesigned

### Known Issues
- Photo reading needs llava:7b in Ollama (it shares the GPU with the language model, so the first photo takes a while)
- Code scenes can still appear in non-code topics
- The new Home photo/mode UI, mind map and lesson layout were type-checked but not looked at in a browser (browser tests were stopped because the laptop hung)

### Future Scope
- Progressive videos that start playing before later parts exist

---

## [v0.9.0] — 2026-10-27
### What's New
- **Project renamed Chanakya** (README, PRD, API title, web title and package, Learnverse stays the name of the metaverse mode)
- **Frontend rebuilt in Priya's grey glass language**: tokens and primitives in `web/src/styles/`, design-system parts in `web/src/ds/` (Glyph, DotNumber, Ring, Stat), shell, pages (Home, Library, Rewards, Lesson), Remotion video theme ported to the same palette. Old `app.css`, `screens.css` and screens removed
- **Home**: a big prompt box is the hero; settings (videos 1-8, length 0:30-4:00, level, languages, PDF) sit in a card below. Scrolling shrinks the box into a pinned header, its topic chips slide away behind it (`--p` driven by scroll, `pages/Home.tsx`, `styles/home.css`); the dock height is measured so the chips never overlap the settings card
- **Sidebar = navigation + awards**: streak with week, score and level, daily goal, latest badges, recent lessons, system status
- **Custom scrollbars** that fade out when nothing scrolls (`shell/useScrollbars.ts`, `styles/scroll.css`)
- **Rewards**: streaks (shields, 20 XP to count a day), XP, levels, 13 badges, daily goals; backend `rewards.py` (13 tests), frontend context with XP/level toasts and a badge modal; wired to lessons, quiz, flashcards, tutor questions, study tools
- **Videos up to 4 minutes**: over 1:30 a lesson is planned in parts (`backend/app/longplan.py`: outline, then each ~40 s part knows what came before and what comes next, parts joined into one lesson); API accepts 30-240 s
- **Floating "Creating…" pill** (`shell/CreatingPill.tsx`): leaving the progress screen no longer loses the lesson; a dot globe pill sits bottom right on every page, turns "Created" and pops to 120% when done, and opens it on click. The result is no longer thrown away when you navigate
- **Faster local model**: no constrained decoding (planner 34 s -> 9.8 s), lenient schema repair, one context size, Ollama flash attention + q8 KV cache + 2 parallel slots
- Progress of a lesson being made shows only in the side card, never inside the player; stat pills show number and label together in one pill; Library cards share one size
- Unlimited-OCR (6.7 GB) downloaded and verified on a scanned page (~10-12 s/page)

### Known Issues
- A 2:30 test video came out at 3:31 before the scene cap and word floor were tightened; needs one more measurement on the next long build
- Long videos can still pick odd scene types (code scenes in a non-code topic); the director does not catch them yet
- Gemma 4 needs a newer Ollama than 0.23.1; Qwen2.5-7B stays the model (Llama 3.2 3B was slower and weaker)

### Future Scope
- Progressive videos: start playing segment 1 while later parts are still being written (`docs/plan-long-videos.md`)
- Metaverse points as a `metaverse_points` reward event

---

## [v0.8.0] — 2026-10-27
### What's New
- **Merged everything the team pushed** (origin/main `60f5253`): Dhiraj's PDF upload + OCR (Tesseract / Unlimited-OCR) + hybrid RAG (e5 embeddings, FTS5 + FAISS, bge reranker), offline library, NLLB translation, GPU scheduler, sources shown on lessons; Niharika's `metaverse/` (3D quiz world) and `Niharika/` voice-assistant plan; Dhiraj's `Dhiraj/` snapshot (kept as pushed; not used by the app)
- One pipeline for both: `build_lesson(concept, languages, level, duration_s, documents, series, focus)` keeps level/length, series (courses), director and writer agents and now also grounds the plan in the PDF/library (`plan_lesson` returns plan + sources). Page-range lessons ("chapter 4") work from a PDF with an empty topic. Playlists accept a PDF too
- Frontend: Home uses Dhiraj's `PdfUpload` (progress + OCR status + focus), lesson notes list Sources, "Metaverse quiz world" button on Home and "Quiz in the metaverse" on the lesson screen (lazy-loaded 3D chunk)
- Tutor chat grounded with the same retrieval (`knowledge.retrieve`) instead of the earlier stub (`app/rag.py` removed: it collided with Dhiraj's `app/rag/` package)
- **Voice assistant** (from Niharika's plan, see `docs/voice-assistant.md`): `POST /api/stt` (faster-whisper small, CPU, offline), spoken tutor replies (`speak` flag -> `audio_url`), mic + speaker buttons in the chat panel. Hands-free mode and LTX demo clips are not built (LTX not realistic on 8 GB)

- **Metaverse entrance** (`web/src/components/TunnelTransition.tsx`, `MetaverseStart.tsx`): click the button and the page blurs while a tunnel of blocks assembles block by block around you; you walk down it, accelerating to light speed (~2 s, streaks); the bright light at the far end grows until it floods the screen; then the metaverse appears behind a **Start** page; Start reveals the topic screen. Canvas 2D, no extra dependency, skipped for `prefers-reduced-motion`; the 3D chunk preloads at the click
- **Fast OCR** (`backend/app/ocr/tesseract.py`, `ingest.py`): Tesseract 5.4 installed and the 9 language packs (tessdata_fast) in `models/tessdata`. Workers open the PDF and render their own pages as grayscale pixels (no PNG round trip), one Tesseract per core with all math libraries pinned to one thread (this cut a worker from ~670 MB to ~80 MB and fixed "paging file too small" crashes at 10+ workers), blank pages skipped, no batch barriers, worker count capped by free memory (`OCR_WORKERS` to override), Latin 200 dpi / Indic 300 dpi. The student's focus pages (e.g. "chapter 4") are read first and a section is indexed as soon as its last page is read, so a lesson on that chapter can start while the rest of the book is still being read. Raw OCR: ~7 pages/s on 22 workers (1,000 dense pages in ~140 s). Unlimited-OCR still upgrades pages in the background (priority: contents, focus, worst-confidence)
- `backend/scripts/bench_tesseract.py [pages] [workers] [--ingest]` builds a synthetic scan and times it

- **Study tools** (flashcards, quiz, mind map, study guide, FAQ, glossary, timeline): built by a background queue as soon as a video exists (`studio.py`; click = jump the queue; English raw copy cached, other languages translated from it), progress from the model's token stream. Buttons in the chat panel: ready opens instantly; working buttons get a flowing multi-colour border and a steady percentage (`useSteadyProgress`: a clock keeps it moving, real progress can only pull it ahead). Mind map = Mermaid text parsed/re-emitted by the backend and drawn on-device. Flashcards redesigned (question front, View answer, 3D flip, slide-away rating, round review)
- **Meta quiz** (`metaquiz.py`, `POST /api/metaquiz`): one metaverse world from every study tool and every video of a course; stations carry extra reading, gates ask up to 5 questions with explanations (metaverse engine extended: `Zone.more`, `info.extra`, `Quiz.why`)
- **PDF notes in 30-page windows** (`ocr/digest.py`): written while OCR runs; 100-page scan: first notes at ~22 s, all at ~32 s; whole-PDF lessons plan from the notes; upload cap 1,000 pages; pass-1 embeddings moved to the idle GPU (OCR+index 1,002 pages: 341 s -> 171 s)
- **Metaverse entrance made smooth**: the lag was the 3D world initialising on the main thread during the animation (up to 0.9-1.6 s freeze); now state is isolated (`MetaverseLayer`), the world starts behind a still white frame and the light clears when it has painted and frames are calm, no CSS blur / backdrop-filter, precomputed tunnel geometry, adaptive canvas resolution, chunk preloaded on hover/idle

### Known Issues
- Studio background builds queue behind each other (one local model): a video's 7 tools take about 2 minutes; opening a lesson queues its tools, and a click goes first
- `transformers` in `backend/venv` is 4.46 (Dhiraj pins 4.57.1 for Unlimited-OCR); scanned-PDF OCR with Unlimited-OCR needs its own ~6.7 GB model and that pin, digital PDFs work without
- Whisper small is weak on Telugu/Tamil/Kannada speech; English and Hindi are the supported voice-input languages for the demo
- Mic needs localhost or HTTPS

---

## [v0.7.0] — 2026-10-27
### What's New
- **Fixed the repeated "bulb" scenes.** Root cause: `normalize()` demoted any scene with too few points to a plain `title` card, so a graph lesson became 4 identical lightbulb cards. Now points are rebuilt from the narration and the originally wanted template is remembered
- **Visual director agent** (`backend/app/director.py`): finds weak scenes (title mid-lesson, same type twice in a row, bullets on a maths/code topic) and redesigns each with a focused call: graphs for maths, code for programming, diagrams/flows for processes. Visual fields only; narration kept
- **Coordinate geometry**: graph scenes can plot points without a curve, draw segments between points (`link` mark), show quadrants I-IV, auto-fit the plane to the points
- **Playlists / courses** (`backend/app/playlist.py`): curriculum agent outlines 5-8 episodes, each built as a series-aware lesson (links to the previous episode, teases the next, no repeats); playlist file saved after every episode so playback starts on episode 1 while the rest are made; episodes build 2 at a time (voice of one overlaps planning of the next, episode 2 waits until episode 1 is past planning); one failed episode does not sink the course; `POST /api/playlists`, `GET /api/playlists[/{id}]`, `POST /api/playlists/{id}/export` (renders every episode and joins them into one MP4). Playlists and exports get their own job workers
- **Course UI**: Format switch on Home (One video / Course of 5-8), episode rail under the video, auto-advance when a video ends (waits if the next is still being made), deep links `#c-<id>[-<episode>]`, "whole course MP4" button
- **Multimodal visual QA** (`backend/scripts/visual_qa.py`): renders-frames-to-vision-model check. moondream (1.7B) gave unusable answers; llava:7b works: it described the old lesson's scenes 1-4 as the same "question mark and light bulb" graphic and flagged them

### Known Issues
- Planner still sometimes puts a quiz early; title/summary/quiz ordering is not enforced
- llava:7b QA needs the planner model unloaded first (8 GB VRAM) and is a script, not part of the pipeline

---

## [v0.6.0] — 2026-10-27
### What's New
- **Real translation working**: IndicTrans2 (en->hi/te/ta/mr/...) running locally from `models/indictrans2` (set `INDICTRANS2_MODEL` to that folder, `HF_HUB_OFFLINE=1`)
- **Voices verified by round-trip** (speak a known sentence, transcribe with Whisper): hi, ta, kn, en good; te, ml, gu correct sounds; mr was garbled on Piper -> now Indic-TTS (0.77 match); bn unverified (Whisper medium cannot read Bengali). `TTS_PREFER_INDIC=bn,mr`
- **Multi-agent pipeline** (all local, all data-only): Planner (Qwen2.5-7B, schema JSON) -> Reviewer (ast check + repair) -> Writer (per-scene free-text narration when the lesson is too short) -> Translator (IndicTrans2) -> Narrators (one thread per language) -> Tutor (chat). Lesson size is set from the slowest chosen language (`WORDS_PER_SEC`) so every track stays inside the requested length
- Per-language TTS locks: all languages record at once
- Planner model benchmark (see below)

### Planner model benchmark (RTX 5060 8 GB, 3 prompts, JSON-schema planner)
| Model | avg s/lesson | valid | notes |
|---|---|---|---|
| qwen2.5:7b-instruct-q4_K_M | 34 | 3/3 | picks graph for maths, code for programming; writes short lessons (writer agent fixes) |
| qwen2.5:3b-instruct-q4_K_M | 24-33 | 2/2 run | missed graph scenes on the circle prompt |
| qwen3:4b | 128 | 3/3 | right length but thinking tokens make it 4x slower; removed |
| qwen3.5:9b, llama3.2:3b | n/a | n/a | not measured (C: disk and RAM pressure) |

### Known Issues
- C: drive was nearly full (0.1 GB): HF cache and Ollama models live there. New downloads go to D: (`models/`)
- Indic Parler-TTS not installed (3.7 GB, not needed). Bengali voice quality unverified
- Whisper-medium check is a proxy: it cannot judge accent or naturalness; a human ear is still needed

---

## [v0.5.0] — 2026-10-27
### What's New
- **Lesson screen = notes | video | tutor chat.** Left: scene-by-scene notes from the lesson (follow playback, click to jump, code/equations included, "My notes" box, copy/download .md). Right: tutor chat that knows the whole lesson and the scene being watched (`POST /api/lessons/{id}/chat`; English plan -> answer -> translated to the active language)
- **Progress is inside the video area** (no separate screen) and continuous: planner now streams tokens for real progress, per-scene voice progress, plus a smoothing hook so the bar never sits still or jumps backwards
- **English is an ordinary option** (no longer forced); at least one language required; lesson stores the English plan for chat
- **Reviewer agent** (`backend/app/review.py`): `ast.parse` check of Python snippets + one small LLM repair call; notes returned in `lesson.review` and shown in the UI
- Removed the separate Creating screen

### Known Issues / findings
- Root cause of "Hindi speaks English with a Hindi accent": `TRANSLATE_BACKEND=none` in a local `.env` -> English text read by a Hindi voice. UI now warns when a non-English track was not translated
- Ollama (Qwen) translation is poor (Telugu leaked Chinese characters); IndicTrans2 needed. Hugging Face downloads stall on the Xet path: use `HF_HUB_DISABLE_XET=1`. Network ~0.5-1.3 MB/s
- Indic Parler-TTS (3.7 GB) not downloaded: not needed now that ta/kn/gu have CPU Indic-TTS voices and bn has a Piper voice

---

## [v0.4.0] — 2026-10-27
### What's New
- Merged teammate's frontend (status panel, history, remote backend)
- **Screen-by-screen UI** (`web/src/screens/`): Home (topic box, PDF upload area, level, length 30/60/90 s, languages, recent lessons, system status) -> Creating (live progress, steps) -> Lesson (player)
- **Player screen**: custom controls: seek bar with scene ticks, tap or drag to seek, hover preview (time + scene), time readout, play/pause, +-5 s, previous/next scene, volume, captions toggle, settings (language, speed 0.75-1.5x, captions, download quality 720p/1080p), full screen; double-tap left/right third of the video = -/+5 s; keyboard (space, arrows, M, C, F); language switch keeps your position; scene list tap-to-jump; MP4 + SRT download
- `POST /api/lessons` now takes `level`, `duration_s` (30-90) and `documents` (ids); prompt adapts to level and length
- `backend/app/rag.py`: single hook `retrieve_context(concept, document_ids) -> str` for the RAG/OCR service; UI uploads to `POST /api/documents` (multipart `file` -> `{id, name, pages?}`) and shows "document service not connected yet" until it exists
- Hash routing fixed (Back/forward and pasted `#id` links open the lesson)

### Known Issues
- Document upload has no backend yet (friend's RAG/OCR service); `documents` ids are accepted but ignored
- Dev-only React warning from Remotion's AbsoluteFill in the Player (pre-existing, harmless)
- Chrome extension was not reachable; UI verified with headless Chrome (screenshots in `output/ui/`)

### Ideas evaluated
- **LTX-2.5 (Lightricks) generative video**: not adopted for the core pipeline. 22B params (int8 21.5 GB + text encoder 15.4 GB, NVFP4 18.7 GB) vs this laptop's 8 GB VRAM / 15 GB RAM; far beyond the 8-16 GB CPU target; cannot render exact Indic text or follow our audio-sets-length rule; gated + community licence. Possible only as an optional, pre-generated b-roll step on a GPU machine

---

## [v0.3.0] — 2026-10-27
### What's New
- **Graph scenes** (`web/src/remotion/graph.tsx`): axes, grid, ticks, curves that draw themselves (line, parabola, cubic, sine, cosine, exp, abs, sqrt, reciprocal, circle, ellipse), circle marks (centre, radius, diameter, chord, tangent), points, formula card, legend. LLM supplies enum + numbers only; nothing is evaluated
- **Code scenes** (`web/src/remotion/code.tsx`): dark editor, offline syntax colouring (Python, Rust, JS/JSX, Java, C, Go, SQL), line highlight following the narration, per-line notes, output console. Snippets are display text, never run
- Planner routes by subject (maths -> >=2 graph scenes, programming -> >=2 code scenes) with worked examples; `normalize()` fills missing labels/highlights; keyword-routed offline samples for `LLM_BACKEND=mock`
- Export height option: `POST /api/lessons/{id}/export {"lang","height":720|1080}`, default 720. Measured 1080p 38.5 s vs 720p 21.3 s for a 40 s lesson, so 720 is default; the UI can offer 1080p as a boost
- CPU voice engine `indic` (AI4Bharat Indic-TTS ONNX: en, ta, kn, gu; RTF ~0.4) ahead of the GPU-only Parler fallback; Bengali now uses its Piper voice
- GPU+CPU: Ollama layer offload (`OLLAMA_NUM_GPU`, auto = as many as fit; 100% on RTX 5060), ONNX CUDA provider when onnxruntime-gpu is present, torch CUDA installed, `/api/health` shows `gpu.ollama_loaded[].gpu_percent`; `DEVICE=cpu` forces CPU everywhere
- Backend venv, web deps, headless Chrome, Piper voices and Noto fonts installed locally

### Known Issues
- IndicTrans2 and Indic Parler-TTS are gated on HuggingFace: account must accept each model's terms before download (translation to Indic languages untested until then)
- 7B model sometimes writes slightly invalid snippets (e.g. missing closing tag); no syntax check yet (idea: `ast.parse` for Python)
- Indic voices (ta/kn/gu ONNX repack) and Indian-accent English not yet judged by ear

---

## [v0.2.0] — 2026-10-27
### What's New
- Merged teammate's `origin/main` (5127b43): FastAPI backend (Ollama planner, IndicTrans2, Piper/Parler TTS, captions, jobs), Remotion `web/` frontend, 8 templates
- Removed our Revideo scaffold and draft `schema/` (superseded by `backend/app/schema.py` and Remotion); scaffold kept outside repo
- License note: project is hackathon-only, not published; license columns kept in README for the submission rule

### Known Issues
- Teammate's design uses Indic Parler-TTS on GPU for ta/kn/bn/gu; spec says CPU-only. Needs CPU path (our Indic-TTS ONNX voices) or accept GPU risk
- Renders at 1920x1080; spec asks 720p (RENDER setting to check)

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
| fd03bb2 | 2026-10-27 | v0.14.1: Learnverse AI worlds with a building screen, gates open by themselves, jump, saved points and purchases, home plus button aligned |
| 543e8b5 | 2026-10-27 | v0.14.0: scenes play while they are made, per-stage progress, parallel study tools, profile, spaced repetition, weak spots, exports, offline lesson file, papers, teach-back, resumable jobs |
| 2c9fb16 | 2026-10-27 | progress.md: git history for v0.13.0 |
| cddcb2a | 2026-10-27 | Android app (native Kotlin + Compose, fully on-device): Figma screens, Gemma tutor and lesson planner, Piper voices, Whisper and Vosk speech, ML Kit translation and OCR, study tools, homework, rewards, profile with name and age |
| 5f07b0c | 2026-10-27 | v0.13.0 web: Progress and Settings pages, rewards history endpoint, voice ripple and waveform in the tutor chat, opening animation switch |
| 2f926c5 | 2026-10-27 | Chanakya v0.9.0: grey-glass frontend, rewards, scroll-shrinking prompt home, videos up to 4 min, floating Creating pill |
| 1cb5b0d | 2026-10-27 | Project setup: docs, lesson schema, Revideo frontend scaffold, fonts |
| 3d9d818 .. 123513d | 2026-10-27 | Orchestration doc, graph/code scenes, merge of teammate frontend, screen-by-screen UI |
| d7527c7 | 2026-10-27 | Notes panel, tutor chat, progress |
| 4b0466c | 2026-10-27 | IndicTrans2, voices, writer/reviewer agents, pacing |
| 86a5fed | 2026-10-27 | Director agent, point-plotting graphs, playlists backend + UI, vision QA script |
| 9ae15b7 | 2026-10-27 | Merge origin/main (PDF/OCR/RAG, metaverse); voice, study tools, Meta quiz, fast OCR, tunnel entrance |
