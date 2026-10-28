# Issues & Fixes Log

> AI: Read this file before debugging. If the same issue occurred before, the fix is already here.

---

## [ISSUE-001] — 2026-10-27
**Title:** Piper voice downloads truncated / missing `.onnx.json`
**Symptom:** After parallel `curl -O` of several voices, `.onnx` files were smaller than catalog size and most `.onnx.json` were absent
**Root Cause:** Backgrounded `curl` with two `-O` URLs per job in a shell loop; jobs raced/were cut off
**Fix:** Download via a Python script that checks each file against `size_bytes` from `voices.json` (`urllib`), re-fetching mismatches
**Files Changed:** `models/piper/*`
**Status:** Resolved

## [ISSUE-002] — 2026-10-27
**Title:** Windows Python cannot open `/c/Users/...` path from Git Bash
**Symptom:** `FileNotFoundError` reading scratchpad JSON
**Root Cause:** POSIX-style path passed to native Windows Python
**Fix:** Use a Windows path (`C:\Users\...`) in Python code
**Files Changed:** none
**Status:** Resolved

## [ISSUE-003] — 2026-10-27
**Title:** `npm init @revideo@latest` is interactive-only
**Symptom:** Stalls at prompts when stdin is piped all at once; creates `my-revideo-project`
**Root Cause:** `prompts` library needs newlines delivered over time; no CLI flags exist
**Fix:** Pipe empty lines with delays: `( for i in 1..8; do sleep 4; echo; done ) | npx @revideo/create@latest`, then rename folder to `frontend`
**Files Changed:** `frontend/`
**Status:** Resolved

## [ISSUE-004] — 2026-10-27
**Title:** PLAN.md license claim for sarvam-translate wrong
**Symptom:** PLAN.md says Apache 2.0
**Root Cause:** Unverified; HF license tag is GPL-3.0 and the model is a Gemma-3-4B fine-tune
**Fix:** Do not use sarvam-translate; use IndicTrans2 distilled 200M (MIT)
**Files Changed:** none (PLAN.md left as-is by request)
**Status:** Resolved

## [ISSUE-005] — 2026-10-27
**Title:** Two license problems found in the stack
**Symptom:** README claimed Piper = MIT and listed Qwen2.5-3B as usable
**Root Cause:** `pip install piper-tts` (1.8.0) is the GPL-3.0-or-later successor (OHF-Voice/piper1-gpl, uses espeak-ng); Qwen2.5-3B ships under the Qwen Research License
**Fix:** README licenses table corrected; planner fallback switched to qwen3:4b (verify Apache-2.0); 3B model not used. GPL decision for our repo is open (see progress.md)
**Files Changed:** README.md, .env.example
**Status:** Ongoing (repo license choice pending)

## [ISSUE-006] — 2026-10-27
**Title:** Backend crashed on start after editing planner prompt
**Symptom:** `ValueError: Invalid format specifier '"circle","a":0,...'` importing `app.planner`
**Root Cause:** `SYSTEM_PROMPT` is an f-string; raw JSON braces in the added examples were parsed as format fields
**Fix:** Double the braces (`{{ }}`) in prompt text that contains JSON
**Files Changed:** backend/app/planner.py
**Status:** Resolved

## [ISSUE-007] — 2026-10-27
**Title:** Stale processes: duplicate model downloads and self-killing restart
**Symptom:** `.part` file locked (WinError 32); a PowerShell restart command exited 255; old uvicorn kept serving mock lessons
**Root Cause:** Two `download_models.py` ran at once; a kill command filtered on `uvicorn app.main` also matched its own command line
**Fix:** Kill by listening port (Get-NetTCPConnection -LocalPort 8000) and by process name; run downloads once
**Files Changed:** none
**Status:** Resolved

## [ISSUE-008] — 2026-10-27
**Title:** Code line cut mid-statement on screen
**Symptom:** React snippet ended `getElementById('root'`
**Root Cause:** `normalize()` truncated lines to 58 columns
**Fix:** Cap raised to 72; prompt asks for lines under 45 characters and to split long statements
**Files Changed:** backend/app/schema.py, backend/app/planner.py
**Status:** Resolved (monitor)

## [ISSUE-009] — 2026-10-27
**Title:** Hindi/Telugu tracks spoke English
**Symptom:** Hindi voice reading English text
**Root Cause:** `TRANSLATE_BACKEND=none` in backend/.env (set for English-only testing); IndicTrans2 not downloaded
**Fix:** Translation switched on; UI warns when a non-English track is untranslated; IndicTrans2 download completed with `HF_HUB_DISABLE_XET=1`
**Files Changed:** backend/.env (local), web/src/screens/LessonScreen.tsx
**Status:** Resolved once IndicTrans2 is installed

## [ISSUE-010] — 2026-10-27
**Title:** `hf download` stalls at 0 bytes for gated models
**Symptom:** `.incomplete` blobs stay 0 bytes forever
**Root Cause:** Xet download path stalls on this network
**Fix:** `HF_HUB_DISABLE_XET=1` and a retrying `snapshot_download` script
**Files Changed:** none
**Status:** Resolved

## [ISSUE-011] — 2026-10-27
**Title:** Merge: `app/rag.py` stub shadowed by Dhiraj's `app/rag/` package
**Symptom:** After merging origin/main, `from .rag import retrieve_context` would fail (package wins over module of the same name)
**Root Cause:** Both sides used the name `rag` (my one-file hook for the friend's service, Dhiraj's real package)
**Fix:** Removed `rag.py`; pipeline/planner/chat use `knowledge.retrieve()` and `knowledge.pages_passages()`; uploads are `POST /api/uploads` (sha) instead of the placeholder `/api/documents`; frontend uses `PdfUpload`, the placeholder `UploadArea` and `uploadDocument` were deleted
**Files Changed:** backend/app/{rag.py (deleted), pipeline.py, planner.py, chat.py, main.py}, web/src/{App.tsx, api.ts, screens/Home.tsx, components/UploadArea.tsx (deleted)}
**Status:** Resolved

## [ISSUE-012] — 2026-10-27
**Title:** `/api/stt` returned 500: `open() got an unexpected keyword argument 'metadata_errors'`
**Symptom:** faster-whisper 1.2.1 crashed decoding any clip
**Root Cause:** it calls PyAV with an argument that PyAV 19 no longer has (faster-whisper expects av 14-15)
**Fix:** `stt.py` decodes with ffmpeg (already required for export) to 16 kHz mono float32 and passes the array to Whisper, so PyAV is not used
**Files Changed:** backend/app/stt.py
**Status:** Resolved

## [ISSUE-013] — 2026-10-27
**Title:** PDF ingest failed: `models/multilingual-e5-small not found`
**Symptom:** upload job errors in 4 s on a fresh machine
**Root Cause:** Dhiraj's RAG expects the e5 embedder and bge reranker under `models/` (not downloaded by `download_models.py`)
**Fix:** downloaded `intfloat/multilingual-e5-small` and `BAAI/bge-reranker-v2-m3` into `models/` with `HF_HUB_DISABLE_XET=1`
**Files Changed:** none (models are gitignored)
**Status:** Resolved on this machine; teammates need the same download

## [ISSUE-014] — 2026-10-27
**Title:** Metaverse entrance laggy at the white flash and at the Start page
**Symptom:** frame freezes right when the tunnel ends and again as the Start button appears
**Root Cause:** the 3D world initialised on the main thread in the middle of the animation (measured 0.9-1.6 s long tasks), App re-rendered the whole tree at that moment, and the Start page used `backdrop-filter: blur` over a live WebGL canvas
**Fix:** `MetaverseLayer` owns all entrance state (no App re-render); the world is mounted only once the screen is a still white frame and the light clears after it has painted and frames are calm; blur/backdrop-filter removed (opacity/transform only); tunnel geometry and colours precomputed, no per-edge strokes, adaptive canvas scale; chunk preloaded on hover and when idle
**Files Changed:** web/src/components/{TunnelTransition,MetaverseLayer,MetaverseStart}.tsx, web/src/App.tsx, web/src/screens.css
**Status:** Resolved (tunnel phase has no frame over 50 ms; remaining start-up work is hidden behind the still frame)

## [ISSUE-015] — 2026-10-27
**Title:** OCR with many workers crashed ("paging file is too small"), and ingest ran at half speed
**Symptom:** more than ~10 Tesseract workers died with BrokenProcessPool; a full upload took 2x the raw OCR time
**Root Cause:** each worker imported numpy/OpenBLAS, which reserved ~670 MB per worker; e5 embedding ran on the CPU while every core was busy with Tesseract
**Fix:** pin OpenBLAS/MKL/OMP to one thread in workers (80 MB per worker), cap workers by free memory, embed on the idle GPU during pass 1
**Files Changed:** backend/app/ocr/tesseract.py, ingest.py, rag/embed.py
**Status:** Resolved (5.9 pages/s end to end)

## [ISSUE-016] — 2026-10-27
**Title:** Study-tool progress border drew 0% and the number stalled then jumped
**Symptom:** the border arc never showed progress; the percentage sat at 15% then jumped to 30%
**Root Cause:** `@property --p` was registered with `inherits: false`, so the pseudo-element never saw it; backend progress arrives in bursts (silence while the model reads the lesson, then tokens)
**Fix:** `inherits: true`; border is now a constant flowing gradient; the displayed percentage comes from `useSteadyProgress` (a clock that always moves; real progress can only pull it ahead, and it glides)
**Files Changed:** web/src/studio/{studio.css,useSteadyProgress.ts,StudioButton.tsx}
**Status:** Resolved (measured 6% to 60% in 12 s, biggest step 1%)

## [ISSUE-017] — 2026-10-27
**Title:** Lesson lost when the user left the progress screen; blank pages after rewriting a file
**Symptom:** navigating to another page while a video was being made dropped the result and there was no way back; separately every page went blank with "does not provide an export named 'Stat'"
**Root Cause:** navigation bumped a run counter that made the finished job's result be ignored; Vite had cached `Stat.tsx` as empty because it read the file while a shell heredoc was rewriting it
**Fix:** a `creation` record in `App.tsx` outlives navigation, shows the floating `CreatingPill` anywhere except on its own progress screen, and only opens the lesson itself if the user is still watching; touching the file made Vite re-read it (check with `curl http://127.0.0.1:5173/src/<file>`)
**Files Changed:** web/src/App.tsx, web/src/shell/CreatingPill.tsx, web/src/styles/home.css, web/src/ds/Stat.tsx
**Status:** Resolved

## [ISSUE-018] — 2026-10-27
**Title:** Schema repair dropped real scenes; long plans ran 40% over length
**Symptom:** "Lesson plan has no usable scenes" from the director; a 150 s request produced 211 s
**Root Cause:** the lenient scene validator also dropped valid `ScenePlan` objects built in code; the writer agent floored every scene at 22 words and parts allowed 5 scenes each
**Fix:** the validator keeps `ScenePlan` instances (`tests/test_schema_lenient.py`); the floor is 14 words and a part has at most 4 scenes
**Files Changed:** backend/app/schema.py, review.py, planner.py
**Status:** Resolved (length to be re-measured)

## [ISSUE-019] — 2026-10-27
**Title:** Android: every Piper voice produced silence
**Symptom:** lessons made on the phone had empty narration files (44-byte .wav), no sound in the player; the voice test said "no sound"
**Root Cause:** sherpa-onnx 2.0.x removed its built-in espeak phonemizer ("--vits-data-dir is deprecated and ignored"), so text never became phonemes. The first dependency setup had picked 2.0.1
**Fix:** use sherpa-onnx 1.13.8 (the build the NDialRecorder uses) and drop the separate onnxruntime-android (1.13.8 ships its own libonnxruntime.so); added a Settings > Test the voice row and a trace file (`files/trace.log`) so native failures leave a trail
**Files Changed:** Unlox_Hackethon/app/build.gradle.kts, app/libs, data/Engines.kt, data/Trace.kt, ui/screens/More.kt
**Status:** Resolved

## [ISSUE-020] — 2026-10-27
**Title:** Android: app exits at the Telugu voice (and would at Marathi and Bengali)
**Symptom:** the app vanished mid-lesson with no Java crash; `dumpsys activity exit-info` said EXIT_SELF status 255
**Root Cause:** the tokens.txt files made for the three raw Piper voices had Windows (CRLF) line endings; the native token reader calls exit(-1) on a malformed line. Marathi and Bengali also have multi-character tokens it rejects
**Fix:** write tokens.txt with LF endings and drop the 5 multi-character tokens; a guard (`Trace.guard/dead`) skips a native step that killed the app on an earlier run, reset on every new install
**Files Changed:** models/tts (not in git), data/Trace.kt, data/Engines.kt
**Status:** Resolved

## [ISSUE-021] — 2026-10-27
**Title:** adb push to /sdcard silently copied nothing from Git Bash
**Symptom:** `adb push dir /sdcard/...` ran for minutes, no files appeared, then std::bad_alloc
**Root Cause:** MSYS path conversion rewrote `/sdcard/...` to `C:/Program Files/Git/sdcard/...`
**Fix:** `export MSYS_NO_PATHCONV=1` before any adb call with a device path; push one folder at a time
**Files Changed:** none (workflow)
**Status:** Resolved

## [ISSUE-022] — 2026-10-27
**Title:** Android progress dial stuck and jumped
**Symptom:** the Generating dial sat at 10% while Gemma planned, jumped to 45%, and showed 99% after a failure
**Root Cause:** the pipeline only reported at stage boundaries; the dial showed that directly
**Fix:** every stage has its own real percentage (the plan stage streams Gemma's output); translating and narrating run in parallel; the dial uses the website's steady-progress idea (a clock that may run only 4% ahead of real work)
**Files Changed:** data/Creator.kt, data/Engines.kt, ui/screens/CreateAndGenerating.kt, ui/UnloxApp.kt
**Status:** Resolved

## [ISSUE-023] — 2026-10-27
**Title:** The player waited for the whole lesson (web and phone)
**Symptom:** nothing could be watched until planning, translation and narration of every scene had finished (25-45 s); the "make the first scene, then keep adding" idea in `docs/plan-long-videos.md` had never been built, only languages one by one
**Root Cause:** the plan was parsed only when complete, and `lesson.json` was written once at the end
**Fix:** read the planner's JSON as it streams (`streaming.extract_scenes`), make and publish each finished scene (`ScenePreview`), poll the lesson while `building`, wait at the end of what exists, then swap in the finished lesson. Same on the phone (`StreamScenes.kt`). Scene 1 now plays after about 6 s
**Files Changed:** backend/app/streaming.py, pipeline.py, planner.py, llm.py, jobs.py, web/src/App.tsx, pages/LessonPage.tsx, Android data/StreamScenes.kt, data/Creator.kt, ui/UnloxApp.kt
**Status:** Resolved (phone build awaits an on-device test)

---

## [ISSUE-024] — 2026-10-27
**Title:** Study tools built one after another
**Symptom:** flashcards, quiz, mind map and the rest appeared one at a time
**Root Cause:** one worker thread drained the queue
**Fix:** `STUDIO_WORKERS` (default 3) builder threads; the English version of a tool is written once under a per-key lock
**Files Changed:** backend/app/studio.py, backend/tests/test_studio_queue.py
**Status:** Resolved

---

## [ISSUE-025] — 2026-10-27
**Title:** Teach-back scored off-topic text 60/100
**Symptom:** a sentence about football covered several lesson points
**Root Cause:** nomic-embed-text with the search prefix gives unrelated texts cosine 0.5-0.67, above the first threshold
**Fix:** no prefix, threshold 0.62, chosen from measurements on a real lesson (off-topic max 0.56, paraphrase 0.75)
**Files Changed:** backend/app/teachback.py
**Status:** Resolved

---

## [ISSUE-026] — 2026-10-27
**Title:** PDF tests fail in the full suite, pass alone
**Symptom:** test_ingest, test_tesseract, test_triage and test_routes_rag raise MemoryError when the whole suite runs
**Root Cause:** the laptop had about 2 GB RAM free (the backend python process holds 4.8 GB), not a code fault
**Fix:** none needed; run those files alone (27 passed) or stop the backend first
**Files Changed:** none
**Status:** Ongoing (environment)

---

## [ISSUE-027] — 2026-10-27
**Title:** Learnverse purchases and points gone the next time
**Symptom:** after buying a ride or hat the shop looked empty on the next visit and the points were back to the start
**Root Cause:** everything lived only in the browser's `localStorage`, which belongs to one address; opening the app from another address (localhost vs 127.0.0.1 vs a network IP, another dev port) or clearing site data starts from nothing
**Fix:** keep a second copy on the backend (`media/metaverse_save.json`, newer `rev` wins, a stale tab cannot overwrite); load it when the world starts
**Files Changed:** metaverse/src/engine.ts, web/src/components/MetaverseLayer.tsx, backend/app/metaworld.py, backend/app/main.py
**Status:** Resolved (verified by clearing localStorage: points restored from the server)

---

## [ISSUE-028] — 2026-10-27
**Title:** "+" button and Create button in different corners of the home prompt
**Symptom:** the add-photo "+" floated at the top right of the box while Create lesson sat at the bottom right; collapsed header was two rows tall
**Root Cause:** `align-items: flex-start` plus a margin-top on the "+", `align-self: flex-end` on Create; and `.dock-box textarea { flex: 1 }` inside the new column wrapper `.dock-field` made flex-basis 0, so the `height` rule was ignored
**Fix:** one `.dock-actions` cluster (both 46 px, bottom aligned), `flex: none` on the textarea, a wrap rule under 560 px
**Files Changed:** web/src/pages/Home.tsx, web/src/styles/home.css
**Status:** Resolved

---

## [ISSUE-029] — 2026-10-27
**Title:** 5-video course failed on every episode with "CUDA error: out of memory"
**Symptom:** the course (Pac-Man, intermediate, 120 s, English + Hindi) ran 384 s and ended with status error: all five episodes failed with the same AcceleratorError, nothing to play
**Root Cause:** the 8 GB card was full (language model + translator + voices). A CUDA out-of-memory raised as AcceleratorError is sticky: torch cannot use the GPU again in that process. `translate._translate_with_fallbacks` caught it, then called `_free_gpu()` which called `torch.cuda.empty_cache()`, which raised the same error and escaped, so the CPU and Ollama fallbacks never ran; every later episode hit the same dead GPU
**Fix:** `config.mark_cuda_broken()` (torch models use the CPU from then on), `_free_gpu` swallows everything, the translator only starts on the GPU when at least 1.8 GB is free (`TRANSLATE_MIN_FREE_GB`), a CUDA-failed episode is retried once. Tests in `tests/test_gpu_resilience.py`
**Files Changed:** backend/app/config.py, translate.py, playlist.py, tests/test_gpu_resilience.py
**Status:** Resolved (restart the backend after a CUDA error to get the GPU back)

---

## [ISSUE-030] — 2026-10-27
**Title:** Long videos and courses showed nothing until everything was done
**Symptom:** a 2 minute video (planned in parts) and every course episode were saved only when complete; the earlier "first scene in 6 s" worked only for single lessons of 90 s or less
**Root Cause:** `_build` started the scene preview only for `series is None and duration_s <= LONG_MIN`; part planning (`plan_long`) and course episodes never fed it
**Fix:** parts of 30 s; the preview streams part 1 and receives parts 2.. whole and in order (`ScenePreview.add_scenes`); episode 1 of a course is built with the preview and the course page opens it as soon as its `lesson_id` exists
**Files Changed:** backend/app/longplan.py, pipeline.py, streaming.py, playlist.py, web/src/App.tsx, api.ts, components/EpisodeRail.tsx
**Status:** Resolved (episodes 2+ of a course are not streamed)

---

## [ISSUE-032]
**Title:** Hindi of a new video stuck for minutes behind the study tools
**Symptom:** the English video was ready, Hindi stayed pending for more than 9 minutes (GPU at 84%, 7.8 of 8 GB used) while flashcards, quiz and other study tools appeared
**Root Cause:** `studio._next` held background tools back only while a `lesson` or `playlist` job was active, not while the `langs` job (the other languages) was; the tools and the translation shared the card
**Fix:** background study tools also wait while a `langs` job is active
**Files Changed:** backend/app/studio.py
**Status:** Resolved (measured: Hindi 74 s for 15 scenes)

---

## [ISSUE-031] — 2026-10-27
**Title:** Generated videos did not start playing
**Symptom:** a finished lesson or episode opened paused, or at a point in the middle
**Root Cause:** `LessonPage` kept `resume` (position and "was playing") in a ref after a language switch and never cleared it or tied it to a lesson, so every later lesson reused it
**Fix:** `resume` carries the lesson id and is used only for that lesson; muted start when the page has had no user activation
**Files Changed:** web/src/pages/LessonPage.tsx
**Status:** Resolved

---

## [ISSUE-033] — 2026-10-27
**Title:** Generating a 5 video course made the computer hang
**Symptom:** the desktop stuttered and froze while a course was made, then episodes failed with CUDA out of memory
**Root Cause:** measured: while translating, PyTorch's GPU allocator reserved 10.3 GB (only 1 GB in use) in the backend process, more than the whole 8 GB card, so Windows pushed the rest into system RAM (the backend's committed memory reached 22 GB, free RAM 0.2 GB) and froze the desktop. Also: the 8 GB card was full all the time: start-up warm-up loaded the translator (about 2 GB), Whisper medium (about 1.5 GB) and every Piper voice with CUDA next to the language model (5.5 GB); Windows then spills into system memory, which freezes the display. On top of that each finished episode queued 14 study tools (2 languages x 7), three at once, against the same model, and torch and OpenMP used every core
**Fix:** `PYTORCH_CUDA_ALLOC_CONF=garbage_collection_threshold:0.6,max_split_size_mb:128`, a cap on torch's share of the card (`TORCH_VRAM_FRACTION`, 0.35), the allocator cache handed back after every translation batch (reserved memory 10.3 GB to 0.41 GB, process memory 14 GB to 4.4 GB in the same test), plus `resources.py` (below-normal priority, headroom gate, idle release), Piper on the CPU, Whisper lazy and VRAM-aware, no automatic study tools for course episodes 2+, 2 study builders, thread caps. See docs/presentation-mode.md
**Files Changed:** backend/app/resources.py, config.py, stt.py, tts.py, translate.py, studio.py, playlist.py, pipeline.py, main.py
**Status:** Resolved (see the measured numbers in progress.md v0.14.2)

---

## [ISSUE-034] — 2026-10-28
**Title:** Digital PDF pages with little text were OCRed, and fonts that map to gibberish were trusted
**Symptom:** a table page, a figure page with a short caption and a Hindi page, all with a perfect text layer, were treated as scanned and read by OCR (88 to 90 % accurate, columns mixed up); a PDF in an old Indian-language font was indexed as Latin gibberish
**Root Cause:** `triage.classify_page` needed 200 characters to call a page digital and only checked the share of letters, which gibberish like `ekWuhVj dksf'kdk` passes
**Fix:** 40 character limit and `markdown.looks_garbled` (cid marks, private-use characters, mixed-case or symbols inside words, Latin text in a document marked as an Indian language)
**Files Changed:** backend/app/ocr/triage.py, markdown.py
**Status:** Resolved

---

## [ISSUE-035] — 2026-10-28
**Title:** Pictures inside an uploaded PDF were ignored
**Symptom:** a lesson from a PDF could not use its diagrams; llava was only called for photos uploaded on their own
**Root Cause:** ingestion read text (text layer or OCR) only
**Fix:** `ocr/figures.py` finds embedded pictures, `ingest._describe_figures` describes them with llava in the background and indexes the description with the page; page records are updated through `update_page` (one lock, fresh copy) so the OCR upgrade and the figure pass cannot overwrite each other
**Files Changed:** backend/app/ocr/figures.py, ingest.py, types.py, vision.py
**Status:** Resolved (vector drawings are not covered)

---

## [ISSUE-036] — 2026-10-28
**Title:** First scene came after 3 s sometimes and 6 s other times
**Symptom:** the first video of a session started fast, the next one noticeably later
**Root Cause:** every call sent the same 1,700-token system prompt that covers maths graphs and code scenes, plus up to 4,000 characters of reference text; the read time of that prompt (0.7 to 0.95 s, more when the model's prompt cache missed) and the length of the answer's first scene varied between topics
**Fix:** a prompt built for the subject (790 tokens for a general topic), smaller reference block for short lessons. Measured 3.2 s (2.1 to 4.0) to 1.2 s (0.9 to 1.3)
**Files Changed:** backend/app/planner.py, llm.py, tests/test_planner_prompt.py
**Status:** Resolved

---

## [ISSUE-037] — 2026-10-28
**Title:** PDF upload bar was slow, stuck and went backwards
**Symptom:** the bar sat at 2 % while pages were read, jumped, went back to 2 % when the upload ended and reading began, and stopped during indexing
**Root Cause:** no progress reports in the page-reading and indexing loops; Markdown conversion analysed vector graphics on every page (385 ms); the browser showed upload and reading progress as two separate bars from zero; the bar had no easing
**Fix:** per-page and per-section reports in bands, graphics analysis only for pages with rules, one continuous eased bar. A no-scanned-pages PDF reported OCR at 80 % and then indexing from 30 %: fixed (test)
**Files Changed:** backend/app/ocr/ingest.py, markdown.py, web/src/components/PdfUpload.tsx, api.ts, tests/test_upload_progress.py
**Status:** Resolved

---

## [ISSUE-038] — 2026-10-28
**Title:** The Android app lagged while a lesson was being made
**Symptom:** stutter on every screen during generation
**Root Cause:** `Creator.stage()` published a new state for every streamed token and the root composable rebuilt the whole app each time; `ScenePreview.feed` parsed the whole JSON for every token; the lesson polled while building was reassigned every 1.2 s even when unchanged; the voice engine ran with debug logging
**Fix:** publish at most every 120 ms (or on a visible change), parse only after a closing brace, assign only on change, TTS debug off and 3 threads
**Files Changed:** data/Creator.kt, StreamScenes.kt, Engines.kt, ui/UnloxApp.kt
**Status:** Resolved in code; to be measured on the phone

---

## [ISSUE-039] — 2026-10-28
**Title:** Attaching a photo on the home page made the user wait before they could create
**Symptom:** the Create button stayed disabled while "Reading..." showed on the photo, for as long as llava took
**Root Cause:** the page needed the finished vision job to know the photo's id, and Home disabled Create while any photo was reading
**Fix:** `POST /api/images` returns `image_id` immediately; Create is enabled for a photo being read; `vision.context/topics` read an unread photo themselves (under a per-photo lock) inside the lesson, playlist or homework job
**Files Changed:** backend/app/vision.py, main.py, pipeline.py, web/src/photos.ts, App.tsx, pages/Home.tsx, tests/test_photo_nonblocking.py
**Status:** Resolved

---

## [ISSUE-040] — 2026-10-28
**Title:** A long video or a course read like several unrelated mini-lessons with repeats and one-line captions
**Symptom:** "teach me about dsa in java" with a photo: four 30 s parts each with its own "Let's learn about X." title card, narration of 4 to 22 words, the same heading and code block repeated, "Summary" and "Common mistakes" per part, empty title cards turned into code scenes
**Root Cause:** every part was planned as a whole lesson, in parallel, without seeing the others; `schema.normalize` added a title card per part; nothing checked the joined plan for repeats or short narration
**Fix:** at most 3 parts (40 s) planned one after the other, each told what was taught (`content.taught_summary`); first part opens, last part closes (`clean_part`, `normalize(segment, last, title)`); `dedupe_plan`, `quality_issue` (repeated headings/code, narration under 18 words), reviewer lengthens short captions; director drops empty mid-video title cards; courses capped at 3 videos with `taught` handed on
**Files Changed:** backend/app/content.py (new), schema.py, planner.py, longplan.py, director.py, review.py, playlist.py, concepts.py, pipeline.py, main.py, tests/test_content_quality.py, test_longplan.py, test_homework_concepts.py; Android Creator.kt, CreateAndGenerating.kt; web Home.tsx
**Status:** Resolved (verified on the real models; not yet on the phone)

---

## [ISSUE-041] — 2026-10-28
**Title:** llava described a photo in a 104-line loop and the planner used all of it
**Symptom:** the lesson was full of the photo's repeated lines and went off topic
**Root Cause:** no repeat penalty or length cap on the vision model, no cleanup of its text, the whole text given to every episode
**Fix:** `vision.clean_description` (dedupe lines, at most 15 lines / 900 characters, keeps the Topic line), `num_predict 380`, `repeat_penalty 1.2`, prompt says never repeat, `vision.relevant` picks the lines that fit an episode, old cached descriptions are cleaned on read
**Files Changed:** backend/app/vision.py, pipeline.py, playlist.py
**Status:** Resolved

---

## [ISSUE-042] — 2026-10-28
**Title:** Titles and captions began with "Teach me ..."
**Symptom:** typing "teach me about dsa in java" gave a lesson called "Teach me about dsa in java"
**Root Cause:** the whole typed sentence was used as the topic
**Fix:** `content.clean_topic` strips the request words (and fixes the case of DSA, Java, SQL and similar) in `create_lesson`, `create_playlist`, `pipeline.build_lesson`, `playlist.start`, and on Android in `Creator.make` (`Topic.kt`). Bare "Teach me" is kept whole; a result starting with a lower-case word is capitalised
**Files Changed:** backend/app/content.py, main.py, pipeline.py, playlist.py, tests/test_content_quality.py; Android data/Topic.kt, Creator.kt
**Status:** Resolved

---

## [ISSUE-043] — 2026-10-28
**Title:** Found by generating real lessons: a heading "string", the same heading twice, scenes opening with the same sentence, short scenes left short
**Symptom:** "teach me about the solar system": title card headed "string" and narrated "Let's explore string ..."; "how does the rainbow have 7 colors...": the heading "Sunlight & Raindrops" twice and two scenes starting "Just like when sunlight passes through a glass prism"; MERN: a scene of 11 words after the writer pass
**Root Cause:** the model copied the word "string" from the JSON schema; the heading check only dropped a repeat if the template or the words matched; narration similarity needed 70 %; the writer pass accepted a rewrite that was still under 18 words
**Fix:** `schema.SCHEMA_WORDS` (heading falls back to the lesson title) and `content.schema_echo` (a retry with feedback); an identical heading is always dropped; scenes whose first six words are the same are dropped; `review` runs a second `only_short` rewrite for scenes still under 18 words
**Files Changed:** backend/app/schema.py, content.py, planner.py, review.py, tests/test_content_quality.py
**Status:** Resolved

---

## [ISSUE-044] — 2026-10-28
**Title:** test_figure_captions_are_stored_on_the_page_and_found_by_search failed only in the full suite
**Symptom:** `seen` was empty after `wait_for_upgrades(10)`
**Root Cause:** two tests in test_knowledge_bridge.py ingested a PDF without `notes=False`, which started the real study-notes writer (it holds the GPU slot, the shared Ollama model); the figures thread waited behind it
**Fix:** `notes=False` in those two tests; `wait_for_upgrades` is asserted, so a timeout fails clearly
**Files Changed:** backend/tests/test_knowledge_bridge.py, tests/test_pdf_markdown_figures.py
**Status:** Resolved


---

## [ISSUE-045] — 2026-10-29
**Title:** "teach me what avl trees are": repeated, shallow video built on a "book of stories" comparison
**Symptom:** a 2-episode course with six scenes each: "stories" instead of nodes, no definition of balance factor or rotations, no tree drawn, no code although the request said C, the same hook twice, narration of 18 to 34 words
**Root Cause:** AVL trees were not in the knowledge base, so there was no source; DSA words were not recognised as a code topic; the `network` (boxes and arrows) template was never described to the model, so a tree could not be drawn; the prompt asked for an everyday example in every scene; nothing told the planner what the learner already had
**Fix:** subjects (`planner.CODE_WORDS`, `NET_WORDS`), the network template documented only for topics that can use it, `language_of`, a retry when a technical lesson has no code/network/graph scene or leans on comparisons (`content.analogy_overload`), `content.strip_analogies`, `memory.py`, reference notes in `data/kb_extra/` (AVL, BSTs, heaps, sorting, graphs, MERN), Flash/Pro modes
**Files Changed:** backend/app/planner.py, content.py, memory.py (new), longplan.py, pipeline.py, llm.py, selfcheck.py (new), main.py, playlist.py, tests/test_modes_memory.py; web Home.tsx, api.ts, App.tsx; data/kb_extra/*
**Status:** Resolved for Flash and Pro (checked on the real model); the 7B can still pick a weak example

---

## [ISSUE-046] — 2026-10-29
**Title:** test_studio_queue tests fail in the full suite only while the machine is loaded
**Symptom:** `test_prebuild_queues_everything_once` and `test_urgent_request_jumps_ahead_of_background` failed twice in a full run made right after a GPU benchmark; they pass alone and in three other full runs (343 passed)
**Root Cause:** timing: they wait on background threads
**Fix:** none yet; rerun when the laptop is idle
**Files Changed:** none
**Status:** Ongoing (flaky under load)


---

## [ISSUE-047] — 2026-10-29
**Title:** Placeholder headings ("string") were replaced by the lesson title and the repeat cleaner then deleted the scenes
**Symptom:** "What is photosynthesis?" (60 s, three languages) came out with 3 scenes: title, diagram, compare; the log said scenes 3, 4, 5 and 7 were "dropped: the heading 'What is photosynthesis?' again"
**Root Cause:** my fix for ISSUE-043 set a placeholder heading to `plan.title`; when the model wrote "string" for several headings they all became identical, and `dedupe_plan` removes a scene with a heading that was already used
**Fix:** `schema._own_heading` (the scene's first point, else the first words of its narration, never a duplicate); regression test
**Files Changed:** backend/app/schema.py, tests/test_content_quality.py
**Status:** Resolved

---

## [ISSUE-048] — 2026-10-29
**Title:** A 60 s lesson ran 111 s in Telugu
**Symptom:** English 55 s, Hindi 95 s, Telugu 111 s for the same request; the rules ask for 30 to 90 s
**Root Cause:** the word budget used the slowest language's speed, but the number of scenes depended on the duration only (6 to 7) and every scene was written, then lengthened, to at least 22 words
**Fix:** `scenes = min(by duration, round(words / 24))` in the planner; a recap scene is added when a lesson stops on a teaching scene; now 37 s / 58 s / 66 s
**Files Changed:** backend/app/planner.py, schema.py
**Status:** Resolved
