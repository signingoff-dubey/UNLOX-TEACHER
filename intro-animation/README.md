# Chanakya intro animation

Standalone draft of the site-open animation. Not wired into `web/`.

Run: `python3 -m http.server 5180` here, open http://localhost:5180 (live). `./render.sh` renders out/intro.mp4 + out/intro.webm (headless Chrome frames + ffmpeg).

Timeline: book rises closed, left page flips open (0.9s), sprouts grow (1.7s), lockup slides left and wordmark wipes in (2.0-3.3s), overlay lifts (3.6s), `intro:done` event fires.
Respects `prefers-reduced-motion`. `logo-source.svg` is an untouched copy of the root SVG.
