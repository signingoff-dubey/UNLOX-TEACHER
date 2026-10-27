"""Headless render of one 3D lesson.  blender -b --factory-startup --python render3d.py -- job.json

job.json: {"template", "params", "fps", "resolution": [w, h], "samples", "audio": wav path or null,
           "shots": [{"focus", "start", "frames"}], "out": mp4 path, "log": log path}
Writes the MP4 (H.264 + AAC narration) and appends progress lines to the log file, since the Store build's
launcher does not pass stdout back."""
import json
import os
import sys
import time
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
log_file = open(job["log"], "a", encoding="utf-8", buffering=1)


def log(msg):
    log_file.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


try:
    from templates import TEMPLATES

    t0 = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = job["fps"]
    sc.render.resolution_x, sc.render.resolution_y = job["resolution"]
    sc.render.resolution_percentage = 100
    total = job["shots"][-1]["start"] + job["shots"][-1]["frames"]
    sc.frame_start, sc.frame_end = 0, total - 1

    if job["template"] == "custom":
        from scene_dsl import build_scene
        info = build_scene(job["scene"], job["shots"], job.get("labels", {}), job["fps"])
    else:
        build, _ = TEMPLATES[job["template"]]
        info = build(job.get("params", {}), job["shots"])
    log(f"built {job['template']} {info if isinstance(info, dict) and len(str(info)) < 200 else ''} in {time.perf_counter() - t0:.1f}s")

    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    for attr, val in (("taa_render_samples", job.get("samples", 16)), ("use_shadows", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"

    # narration as a sequencer sound strip; it is mixed into the video's audio track
    if job.get("audio"):
        ed = sc.sequence_editor_create()
        strips = ed.strips if hasattr(ed, "strips") else ed.sequences      # Blender 4.4+ renamed it
        strips.new_sound("narration", job["audio"], 1, 0)

    im = sc.render.image_settings
    if hasattr(im, "media_type"):
        im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    ff = sc.render.ffmpeg
    ff.format, ff.codec = "MPEG4", "H264"
    ff.constant_rate_factor = "MEDIUM"
    ff.audio_codec = "AAC" if job.get("audio") else "NONE"
    ff.audio_bitrate = 160
    sc.render.filepath = job["out"]

    frames_done = [0]
    t_render = time.perf_counter()

    def on_frame(scene, *_):
        frames_done[0] += 1
        if frames_done[0] % 24 == 0 or frames_done[0] == total:
            el = time.perf_counter() - t_render
            log(f"frame {frames_done[0]}/{total}  {el / frames_done[0]:.3f}s/frame")

    bpy.app.handlers.render_post.append(on_frame)
    bpy.ops.render.render(animation=True)
    log(f"DONE {total} frames in {time.perf_counter() - t_render:.1f}s -> {job['out']}")
except Exception:
    log("ERROR " + traceback.format_exc())
    raise
finally:
    log_file.close()
