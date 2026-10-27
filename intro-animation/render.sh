#!/usr/bin/env bash
# Render the intro to MP4 + WebM: headless Chrome draws each frame at time t, ffmpeg encodes.
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
FPS=30; DURATION=4.2; N=$(python3 -c "print(int($FPS*$DURATION))")
OUT=out; FR=$(mktemp -d); mkdir -p "$OUT"
export CHROME FR PWD
shot(){ # fresh profile per frame + timeout + retry: parallel Chrome sharing a profile hangs sometimes
  for try in 1 2 3; do
    UD=$(mktemp -d)
    perl -e 'alarm 40; exec @ARGV' "$CHROME" --headless --disable-gpu --hide-scrollbars --user-data-dir="$UD" --window-size=1920,1080 \
      --screenshot="$FR/$(printf %04d $1).png" "file://$PWD/index.html?t=$(python3 -c "print($1/$FPS)")" >/dev/null 2>&1 || true
    rm -rf "$UD"; [ -s "$FR/$(printf %04d $1).png" ] && return 0
  done; echo "frame $1 failed" >&2; return 1
}
export -f shot; export FPS
seq 0 $((N-1)) | xargs -P 4 -I{} bash -c 'shot {}'
ffmpeg -y -loglevel error -framerate $FPS -i "$FR/%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 16 -movflags +faststart "$OUT/intro.mp4"
ffmpeg -y -loglevel error -framerate $FPS -i "$FR/%04d.png" -c:v libvpx-vp9 -pix_fmt yuv420p -crf 28 -b:v 0 "$OUT/intro.webm"
rm -rf "$FR"; ls -lh "$OUT"
