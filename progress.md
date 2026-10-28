# Progress Log

## Current Version: v0.16.0
## Status: In Progress (pre-Gate 1)

---

## [v0.16.0] — 2026-10-29
### What's New
- **Flash and Pro** (`quality` on `/api/lessons` and `/api/playlists`, a Flash/Pro switch on the Home page, same model for both). Flash is what it was: scenes appear within seconds and flow into each other while the rest is still being written. Pro shows nothing until the whole video is planned: the video is outlined scene by scene first (`longplan.beat_sheet`), the first minute is written in one call, and each further minute is patched on in a call that sees the whole outline and the full text written so far (`longplan.plan_pro`, `PRO_BLOCK_S = 60`); the fact check gets twice the time. Measured on "teach me what avl trees are" (2 min): Flash 133 s (first scenes after 18 s), Pro 167 s (nothing until the end); Pro covers balance factor, single and double rotation, insertion, deletion and applications, Flash stayed on a "stacked books" comparison
- **Memory of what already exists** (`memory.py`): every finished lesson is summarised (headings, key points, first lines of code); the planner is told which related videos the learner already has and must not repeat their hook, definitions, examples or code. A retry of the same request is not treated as something to avoid. Course episodes get the same through the course context; Pro also sees the other episodes
- **Technical topics are shown, not described**: data structures, trees, DSA, MERN and similar are now recognised as code topics; trees, linked structures, pipelines and architectures are drawn with the `network` template (it was never documented to the model before); the language the learner names ("in C language") is used for the code; a technical lesson of only text scenes is sent back; one everyday comparison per technical video is kept and the rest are removed (`content.strip_analogies`)
- **Reference notes for the fact checker and planner** (`data/kb_extra/`, indexed by `scripts/build_knowledge.py --no-fetch`): data structures and AVL trees (balance factor, four rotation cases, worked examples, C code), MERN, coordinate geometry, Python basics. Hand-written lesson plans live in `data/curated/` (git-ignored)
- **Robustness**: Ollama calls are repeated twice with a wait when it is busy or restarting (`llm.post`); `GET /api/ready` and a start-up log say what is missing and what to run (Ollama, models, knowledge base, disk, voices, video export); `quality` is validated; `build_lesson(plan=...)` builds a hand-written plan through the same voices, templates and renderer
- **Documentation PDF**: `Chanakya-Documentation.pdf` (cover with the team details, contents, README, PRD, problem statement, pitch, plan, progress, issues, design notes and every teammate module note; 137 pages) is built by `tools/build_docs_pdf.py` (Chrome headless). Team: The Last Commit (Aryan Dubey, Priyadarshini Prasad, Niharika K P, Dhiraj Shetty), RV University, Bengaluru
- **Fact checker** (`facts.py`, from the previous work): arithmetic and canonical lists checked by calculation, statements checked against retrieved passages with a quoted proof, a focused second question before anything is changed, corrections must pass the same check; the report is saved with the lesson and shown on the web page

### Known Issues
- Android has no Flash/Pro switch yet (it keeps its own Flash-style generation)
- A bigger local model was measured and rejected: `qwen3.5:9b` is 8.8 GB with the context window, only 72 % fits on the 8 GB card, 17 tokens/s against 43 for the current 7B, and its first answer was invalid JSON. Cloud models in Ollama are refused: the project is offline
- The 7B still gets facts wrong now and then (the fact checker removes what it can prove wrong); code in code scenes is shown, not run or verified (Python snippets are parse-checked)

---

## [v0.15.2] — 2026-10-28
### What's New
- **Long videos and courses are coherent**: a "teach me about dsa in java" video with a photo came out as four 30 s mini-lessons glued together (a title card per part, "Let's learn about X." placeholders, narration of 4 to 22 words, the same code and heading repeated, a summary per part). Now a video has at most 3 parts of about 40 s, planned one after the other, and each part is told what the earlier ones taught (`content.taught_summary`). Only the first part has a title card, only the last has the quiz and the summary (`content.clean_part`, `schema.normalize(segment, last, title)`), repeated headings, narration and code are dropped from the joined plan (`content.dedupe_plan`), narration under 18 words is lengthened by the reviewer (floor 22, cap 34), and the director removes empty mid-video title cards instead of turning them into code. A course is at most 3 videos, each told what the earlier videos taught. Measured on the real models (3-video DSA course with the photo): 12, 10 and 11 scenes, narration 27 to 33 words on average, 14 different code scenes that build up (array, access, linked list node, stack class, pitfall, queue), concrete episode titles
- **A photo no longer wrecks a lesson**: llava sometimes looped (a 104-line description); descriptions are deduplicated and cut to 15 lines (`vision.clean_description`, `repeat_penalty 1.2`), and in a course only the lines of the photo that fit an episode are given to it (`vision.relevant`)
- **"Teach me" is not part of the title any more**: `content.clean_topic` (backend, Android `Topic.kt`) takes the subject out of a request: "teach me about dsa in java" is "DSA in Java", "can you make a video on the water cycle please" is "The water cycle", "explain photosynthesis" is "Photosynthesis". Questions and plain topics are left alone, a request with nothing after it is kept whole
- **Expressive voice** (`expression.py`, `TTS_EXPRESSIVE=1`): every scene has a tone (title excited, quiz curious, summary calm, common mistakes serious, code calm, else warm) and every sentence its own delivery (a question slower with a longer pause, an exclamation or a hook quicker and brighter, a very short sentence slowed and stressed, a warning serious). Piper takes per-sentence speed, pitch/rhythm variation and volume, with pauses between sentences; Indic ONNX voices get the pauses and a small speed change; Parler-TTS gets the tone as a plain-language instruction. Clips are cached per text and tone. Measured: pacing and pauses change (a clip is about 10 % longer than flat), pitch range barely moves (Piper cannot do true emotion; Parler on the GPU can)
- Web and Android: a course is 1 to 3 videos (Auto/1/2/3)
- **Checked on real lessons** (aquatic life, solar system, rainbow, MERN, sky, steel, refrigerator): topics come out clean ("The solar system", "MERN stack basics", "Why the sky is blue", "How is steel made"); fixed what they showed: a title card headed "string" (word copied from the schema), the same heading twice, two scenes opening with the same sentence, scenes still under 18 words after the writer pass. The full suite passes (294), including a test that failed only in the full run (see ISSUE-044)

### Known Issues
- Voice expression is not on the phone yet (sherpa-onnx voices are flat), and nobody has listened to the clips: the numbers show pacing and pause changes, not how natural they sound
- The Android changes (parts, topic cleaning, 3-video courses, chat video, lag) compile but are not tested on the phone
- "Common mistakes" appears once per video; one snippet lost a closing brace in a comment
- A question with two parts ("how does the rainbow have 7 colours, why does it come only with rain") is kept whole as the lesson title; a small model may list six of seven rainbow colours (facts are not checked)

---

## [v0.15.1] — 2026-10-28
### What's New
- **A photo on the home prompt no longer blocks "Create"**: the button was disabled while llava read the photo (13 s or more) and the page only learned the photo's id when the read finished. Now the upload answers at once with the photo's id (`image_id`), the button is enabled straight away ("Reading, you can create now"), and the lesson, course or homework job reads the photo first if it has not been read yet, showing "Reading your photo" (`vision.ensure`, one reader per photo so llava is never asked twice). Measured on the real models: upload answered in 0.05 s, lesson started 0.03 s later. The read itself is a little faster (image side 1024, shorter answer)

### Known Issues
- The first photo read after the model has been idle takes about 13 s (llava has to be loaded, and the language model steps aside on an 8 GB card)

---

## [v0.15.0] — 2026-10-28
### What's New
- **First scene sooner, and the same every time**: the planner's system prompt was about 1,700 tokens for every lesson, most of it graph and code templates, examples and rules that only maths and programming topics use. It is now built for the subject (`planner.system_prompt`, `llm.slim_schema_text`): a general topic gets 790 tokens (the reference block is also smaller for short lessons). Measured on the real model, alternating topics: time to the first finished scene 3.2 s on average (2.1 to 4.0 s, the 3-4 s against 6 s you saw) before, 1.2 s (0.9 to 1.3 s) now; prompt read 0.95 s to 0.30 s. Maths and programming topics keep exactly what they had; an unknown subject (a PDF, a photo) keeps everything
- **PDF upload bar is continuous and fast**: reading pages reported nothing until OCR started, indexing reported nothing, and the Markdown conversion made it 10x slower (385 ms a page). Now: vector-graphics analysis only for pages that have rules (38 ms a page, same text, ruled tables still found), a progress step for every page, one band per phase (reading to 30 %, OCR to 80 %, indexing section by section to 97 %, pictures), the bar in the browser is one run from the first byte (sending is the first 12 %, it used to jump back to 2 %), eased and creeping between reports, polled every 300 ms. A test found and fixed a jump backwards for PDFs without scanned pages
- **Android: the same continuous generation as the website**: videos over 90 s are planned in parts of about 30 s (outline first, part 1 streamed token by token, later parts handed to the player whole, in order); every video of a set is listed in the player as soon as its first scene exists, and the player moves on to the next video by itself (waiting for it while it is made); "make one more video on X" in the tutor chat (same recognition rules as the website) adds a video to the lesson's playlist and shows a card with its first frame and a play button; the planner prompt only carries the template docs the topic needs
- **Android: lag fixes**: the creator told the screen about progress on every streamed token (dozens of times a second, each rebuilding the whole app) and re-parsed the whole growing JSON for every token; now progress is published at most every 120 ms or when something visible changes, the JSON is parsed only when a closing brace has arrived, the lesson that is polled while it is made is only assigned when something changed, and the voice engine no longer runs with debug logging on four threads (3 threads, no debug). It builds; not yet measured on the phone
- **Learnverse graphics**: GPU sky with slow aurora curtains and a palette that drifts from sunset to twilight and back, twinkling stars, trees that sway in the wind (instanced vertex shader), colour sparks rising from every station, pulsing crystals and path, a colour-grade pass with vignette (stronger with speed) and film grain on high quality, a livelier avatar (breathing, squash and stretch on jump, dust on landing and while running), glass panels with an inner highlight, an animated sweep on the topic card

### Known Issues
- The Android changes compile but are not tested on the phone (lag, parts, chat video, auto-advance)
- Phone: only one extra video is made at a time, and not while another lesson is being made
- The planner still writes about 90 s of narration for a 120 s request

---

## [v0.14.4] — 2026-10-28
### What's New
- **PDF to Markdown, not OCR, for every page that has a text layer** (`ocr/markdown.py`, `pymupdf4llm`). Measured on a test PDF with known text (title and bullets, two columns, a ruled table, a figure page, Hindi in Noto Sans Devanagari): the text layer is 98.8 to 100 % identical to the original, Markdown 100 %, OCR 68 to 100 % (two columns read across each other 68 %, table 90 %, figure page 88 %, Hindi 88 %); text layer 1 to 15 ms a page, Markdown 54 to 530 ms, OCR 750 to 1330 ms. Markdown also keeps headings (`#`), lists and real table rows, which OCR and plain text lose, so the planner and the search get structured text. OCR remains for scanned pages and for broken text layers
- **Short digital pages are no longer sent to OCR**: a page needed 200 characters of text to count as digital, so a table page, a figure page with a short caption and a Hindi page (all with a perfect text layer) were OCRed and came out worse. The limit is now 40 characters
- **Fonts**: a text layer that cannot be trusted is detected and the page goes to OCR instead: `(cid:12)` marks, private-use boxes, and the old Indian-language fonts (Kruti Dev and the like) whose text layer is Latin gibberish like `ekWuhVj dksf'kdk` where Devanagari should be (mixed-case and symbol-in-word test, and "Latin text in a document marked as an Indian language"). Ligatures (ﬁ), soft hyphens, zero-width characters and words split at a line end are cleaned
- **Pictures inside a PDF are described by llava** (`ocr/figures.py`, `vision.describe_figure`): diagrams, graphs and photos are cut out (page-sized scans, icons and logos repeated on several pages are skipped, at most 40 per PDF, the pages you asked about first), described in the background (the PDF is searchable at once; the pass holds the GPU slot and steps aside for lessons), saved on the page and searched with it as `[Figure on page N: ...]`, so the planner sees them. Verified live with llava:7b on the test PDF (it read the three labels of the diagram; it also invented a fourth, so the prompt now says to mention only what is visible). Upload status reports `figures: found / described / state`
- **Caching and pre-warming**: translations are batched by length (35 % faster on mixed sentences, 4.5 s to 2.9 s for 32) and the cache is written atomically; while the planner is still writing, each finished scene is translated into the cache for the other languages (only when the translator is already on the GPU and memory is free), so the final pass finds it ready; a recording heard before is not transcribed again (cache of 300 clips; cold first question 10.2 s, warm 0.29 s, repeated 0 s); at start-up the embedding models are warmed, and the speech model is loaded once the computer is idle (it is released again after 10 quiet minutes); Whisper goes to the GPU when 2.2 GB is free (was 3)

### Known Issues
- Drawn (vector) charts are not pictures inside the PDF, so llava does not see them; only embedded bitmaps are described
- llava can add details that are not in the picture; descriptions are tagged as figures and kept short
- IndicTrans2 still runs without its KV cache (a workaround for the remote model code), which makes long sentences slow
- Pages cached by an older version as "scanned" keep their OCR text (only new uploads use the better triage)

---

## [v0.14.3] — 2026-10-28
### What's New
- **Ask the chat for another video**: "generate one more video on black holes", "make another one about volcanoes, 2 minutes", "another lesson on tides" (`videochat.py`; recognised by its words, so it is instant and uses no GPU; questions like "how do I make a video?" or "give me one more example" still go to the tutor). The backend adds the video to the playlist of the lesson being watched (a lesson with no playlist is wrapped into one, as episode 1) and starts building it at once, scene by scene. In the chat a card shows its first frame with a play button as soon as scene 1 exists ("7 of about 7 scenes ready"); the play button opens it in the center player (it starts by itself) and the playlist under the player lists it ("playing, more coming..."). Verified in the browser
- **Every course episode streams**, not only episode 1: episodes 2 and 3 of a test course were watchable 13 s after they started; the player moves on to a streaming episode by itself

### Known Issues
- A video asked for in the chat is as long as the model writes it (90 s asked, 51 s made)
- Only one extra video is built at a time (they queue); a course that is still being made cannot take extra videos

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
| d2d2546 | 2026-10-29 | v0.16.0: Flash and Pro modes, memory of existing lessons, fact checker, technical topics shown with code and network scenes, reference notes, retries and readiness checks, full README |
| d9ed0c9 | 2026-10-28 | v0.15.2: coherent long videos and courses (max 3 parts/videos, no repeats), topic cleaning, expressive narration, non-blocking photo, fixes found by live lessons |
| 342b893 | 2026-10-28 | v0.15.0: prompt tightened, PDF upload progress, Android continuous generation and lag fixes, Learnverse graphics, docs |
| 2dacea8 | 2026-10-28 | v0.14.4: PDF Markdown pipeline, font checks, llava for PDF pictures, caching and pre-warming |
| e7f578e | 2026-10-28 | v0.14.3: ask the chat for another video, every course episode streams |
| ea3b050 | 2026-10-27 | v0.14.2: 5 video course no longer hangs the laptop, GPU errors fall back to CPU, long videos and episode 1 stream, autoplay fixed |
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
