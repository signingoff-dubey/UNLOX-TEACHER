# Presenting without the laptop hanging

The laptop has 8 GB of graphics memory and 16 GB of RAM. The language model alone takes 5.5 GB of the card, and Windows draws the screen on the same card, so anything else that fills it makes the whole desktop stutter. The backend now protects itself (below-normal priority, half the cores, background work waits for free memory, idle models are released), but the apps around it matter too.

## Before the demo (2 minutes)

1. Close what you do not need: Figma, Android Studio, extra Chrome windows and tabs, the Vite dev server. In a terminal in `Unlox_Hackethon`, run `gradlew --stop` (the Gradle and Kotlin daemons keep 1 to 3 GB).
2. Run the built app, not the dev server: build once with `cd web && npx vite build`, then open `http://localhost:8000` (the backend serves `web/dist`). Do not run `npm run dev` during the demo.
3. Start the backend and Ollama only (`backend/run.ps1`). Check `http://localhost:8000/api/health`: `resources` should show about 6 GB or more of free RAM and 6 GB or more of free VRAM before you start.
4. Warm it with one short lesson before you present (30 s, English): the language model is then loaded and the first real lesson starts at once.

## During the demo

- Ask for what you will show, not more: a course of 3 videos of 1 minute is ready in a few minutes; 5 videos of 2 minutes takes about ten.
- Episode 1 plays while it is made; episode 2 and later appear as they finish. Start talking about the first one while the rest builds.
- Study tools (flashcards, quiz, mind map) are written when you open them; the first one takes about half a minute.
- Hindi and the other languages arrive after the English version. The page adds them by itself.

## If something is slow

- `/api/health` shows `resources`. Under 1.5 GB of free RAM or 0.8 GB of VRAM, background work pauses on its own; closing a browser window or Figma frees it again.
- After a CUDA error the backend uses the CPU for the translator until it is restarted (slower but it does not fail). Restart the backend to get the GPU back.
- Lower the load further with environment variables before starting the backend: `STUDIO_WORKERS=1`, `PLAYLIST_WORKERS=1`, `STT_DEVICE=cpu`.
