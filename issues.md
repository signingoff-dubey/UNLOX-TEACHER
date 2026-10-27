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
