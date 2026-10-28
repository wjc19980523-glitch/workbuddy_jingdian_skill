#!/bin/bash
# Render one city: timeline → score → frames (motion blur) → mp4 → cover → contact sheet → ffprobe.
#   template/render.sh <cityDir> [--draft]
# CS_SCALE / CS_FPS / CS_WORKERS override quality (draft = 0.5 scale, 15 fps).
set -eo pipefail
export PYTHONIOENCODING=utf-8
py() { python3 -I -X utf8 "$@"; }
HERE="$(cd "$(dirname "$0")" && pwd)"; T="$HERE/tools"
CITY="$(cd "$1" && pwd)"; shift
if [ "$1" = "--draft" ]; then export CS_SCALE=${CS_SCALE:-0.5} CS_FPS=${CS_FPS:-15}; SUF="-draft"; else export CS_SCALE=${CS_SCALE:-1} CS_FPS=${CS_FPS:-30}; SUF=""; fi
SLUG=$(py -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['slug'])" "$CITY/city.json")
# advisory lock when available (Linux); skip on Windows/Git Bash without flock
if command -v flock >/dev/null 2>&1; then
  exec 9>"$CITY/build.lock"; flock 9
fi
py "$T/build_timeline.py" "$CITY"
py "$T/music.py" "$CITY"
py "$T/make_docs.py" "$CITY"
py "$T/render.py" "$CITY"
OUT="$CITY/$SLUG-scenic$SUF.mp4"
ffmpeg -y -v error -framerate "$CS_FPS" -i "$CITY/build/frames/f%05d.jpg" -i "$CITY/build/score.wav" \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
  -c:a aac -b:a 192k -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -shortest -movflags +faststart "$OUT"
# cover: the title frame (map + city name), contact sheet: one frame per second
CT=$(py -c "import json,sys;e=json.load(open(sys.argv[1],encoding='utf-8'));print([x['t'] for x in e['events'] if x['kind']=='impact'][0]+1.6)" "$CITY/build/events.json")
ffmpeg -y -v error -ss "$CT" -i "$OUT" -frames:v 1 "$CITY/cover$SUF.png"
ffmpeg -y -v error -i "$OUT" -vf "fps=1,scale=216:-1,tile=8x8:padding=4" -frames:v 1 "$CITY/contact$SUF.jpg"
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate -show_entries format=duration,size -of compact "$OUT"
BL=$(ffmpeg -i "$OUT" -vf blackdetect=d=0.3:pix_th=0.06 -an -f null - 2>&1 | grep -c black_start || true)
echo "blackdetect segments: $BL"
echo "RENDERED $OUT"
