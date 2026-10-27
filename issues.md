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
