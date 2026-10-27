# Todo (kept so nothing is lost)

Legend: [ ] to do, [~] in progress, [x] done and tested

## Website and backend (laptop)
- [x] Progressive scenes: scene 1 watchable ~6 s after the click on web (backend streaming preview + player), built on phone (install pending)
- [x] W1  Profile page (`#/profile`): name and age, age feeds the planner and tutor prompts
- [x] #1  Spaced repetition: SM-2 over flashcards and quiz, SQLite, "due today" on Home, review page, rewards hook
- [x] #2  Weak spots: log wrong quiz answers per concept; planner gets them as focus; "Revise" mode
- [x] #3  Misconception check: planner `common_mistakes` field becomes a compare scene
- [x] #9  Language fidelity: script validity + back-translation check after translation
- [x] #10 Glossary pronunciation: cached TTS clip per term, "hear it" button
- [x] #6  Subtitle-only and audio-only (mp3/wav "podcast") exports per language
- [x] #7 / W13  Offline lesson bundle (.chanakya zip: json, audio, srt, standalone player html); import with no backend, share over USB
- [x] #5 / W5   Question paper generator (MCQ, short, long, marks, answer key) to printable HTML/PDF; worksheet from a lesson
- [x] #4  Teach-back: speak or type an explanation, score by embedding similarity, list missed points (no generative judge)
- [~] W11 Course from a PDF: chapters become episodes, progress per chapter (backend playlists take a PDF; website chapters-as-episodes not built, phone has it)
- [x] #8  Diagram scene from nodes and edges (deterministic layout)
- [x] #11 Resumable jobs: queue in SQLite, resume at the last finished language
- [x] Docs, backend tests for every piece, committed locally (push only when asked)

## Android
- [x] Real engines, Figma screens, scene templates, seek bar, full screen, PDF tile, videos x length (built; install done, on-phone test pending)
- [ ] On-phone test of the latest build (ask first, popup)
