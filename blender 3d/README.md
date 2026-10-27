# 3D lessons on any topic, offline (headless Blender)

A separate tool, outside the Visual Teacher repo. A student's question becomes a narrated 3D video, with no internet:

1. **Plan:** the local model (Ollama) returns JSON data only, never code. `planner.py` validates and clamps it:
   - If a hand-built scene fits exactly (seasons, solar_system, atom), it writes the script for that scene.
   - Otherwise it designs a **custom scene** from building blocks: objects, colours, finishes, positions, labels,
     and per-shot actions and camera moves. A layout pass pushes overlapping objects apart.
2. **Translate** narration and labels with the backend's NLLB.
3. **Narrate** with the backend's Piper voices. Each shot lasts as long as its voice.
4. **Labels** are drawn by Windows text shaping, so Hindi, Telugu and Tamil conjuncts are correct. They float above
   objects and face the camera.
5. **Render** in Blender (EEVEE, headless). It writes `lesson.mp4` (H.264 with AAC narration) and `lesson.srt` captions.

## Use

```powershell
.\make3d.ps1 -Doctor                                        # check this PC first
.\make3d.ps1 -Concept "explain the water cycle" -Lang te
.\make3d.ps1 -Concept "how does a lever work" -Quality good
.\make3d.ps1 -Template atom -Element oxygen -Lang hi
.\make3d.ps1 -Plan out\<run>\plan.json -Lang ta             # same scene in another language
```
Each run writes `out\<time>-<topic>-<lang>\` with `lesson.mp4`, `lesson.srt`, `plan.json` (editable; re-render with
`-Plan`), `job.json` and `render.log`. `python tools_frames.py out\<run> sheet.png` makes one preview frame per shot.

## Building blocks (custom scenes)

| | |
| --- | --- |
| Shapes | sphere, box, bar, cylinder, cone, torus, ring, plane, arrow (any direction), spring, wave surface |
| Science | planet (earth, mars, saturn…), star, atom (H to Ca, real shell counts), molecule (any formula; H2O, CO2, CH4, NH3, NaCl, benzene… built from real geometry), cell |
| Nature | leaf, tree, cloud, water drop |
| Look | 16 colours × matte, glossy, metal, glass, glow; environments: space, studio, sky, lab, underwater |
| Actions | appear, disappear, move, rotate, spin, orbit, grow, shrink, stretch, pulse, highlight |
| Camera | wide, close, orbit, top, side, low |

New building blocks go in `build_kind()` in `blender/scene_dsl.py`. Add their names to `KINDS` and the prompt in
`planner.py`.

## Setting up another PC

Everything below is installed once, online. After that the tool runs with Wi-Fi off.

| Need | How |
| --- | --- |
| Visual Teacher backend + venv | the project's `setup.ps1` (Ollama with qwen2.5:7b, Piper voices, NLLB cached) |
| Blender 4.2+ | blender.org installer or portable zip, or the Microsoft Store. Found automatically, or set `BLENDER_EXE`. |
| Windows 10/11 | label text shaping uses Windows, with the Nirmala UI font (built in) |
| GPU | any; NVIDIA renders much faster |

Run `.\make3d.ps1 -Doctor`. It checks each item and says what to fix.

## Measured on this laptop (RTX 5060 8 GB, app server and Ollama running, draft 854×480)

| Run | Video | Total time |
| --- | --- | --- |
| custom: water cycle, Telugu | 21.3 s | 203 s (render 165 s) |
| custom: photosynthesis, Hindi | 23.4 s | 149 s (render 116 s) |
| template: seasons, English | 25.0 s | 62 s |
| template: atom (oxygen), Telugu | 20.6 s | 113 s |
| template: seasons, English, good 1280×720 | 25.0 s | 222 s |

The planner takes about 15 to 20 s and translation 10 to 25 s; the rest is rendering, at 2.5 to 10 times real time.
That is fine in the background or for pre-made clips, but too slow to wait on live.

## Limits

- Custom scenes are only as good as the local 7B model's plan. They are simple, and sometimes the actions only
  loosely match the narration. Edit `plan.json` and re-render with `-Plan` to fix one.
- Labels are not mirrored into the captions: the `.srt` holds only the narration.
