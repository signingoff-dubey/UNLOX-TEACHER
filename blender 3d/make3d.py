"""Make a narrated 3D lesson video on any topic, fully offline, with headless Blender.

    python make3d.py --concept "how does a lever work" --lang hi
    python make3d.py --concept "why do we have seasons" --quality good --open
    python make3d.py --template atom --element oxygen --lang te
    python make3d.py --plan out\\<run>\\plan.json --lang ta        (re-render a saved plan in another language)

1. Plan: the local model picks a hand-built scene (seasons, solar_system, atom) or designs a custom scene from 3D
   building blocks. It returns JSON data only; planner.py validates it.
2. Translate the narration and labels (NLLB), 3. narrate (Piper; each shot lasts as long as its voice),
4. render labels with Windows text shaping, 5. render in Blender (EEVEE): lesson.mp4 (H.264 + AAC) + lesson.srt.
Run `python doctor.py` first on a new PC.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

from tools import HERE, backend_dir, blender_exe

sys.path.insert(0, str(backend_dir()))
import planner  # noqa: E402
from labels import render_labels  # noqa: E402

QUALITY = {"draft": {"resolution": [854, 480], "samples": 8}, "good": {"resolution": [1280, 720], "samples": 24}}
FPS, GAP_S = 24, 0.35

DEFAULT_SCRIPTS = {
    "seasons": [("intro", "The Earth travels around the Sun once every year."),
                ("tilt", "Its axis is tilted by about twenty-three degrees, and it always points the same way in space."),
                ("june", "In June the northern half leans toward the Sun, so sunlight is stronger and days are longer. It is summer there."),
                ("december", "Six months later the north leans away. Sunlight is weaker and days are shorter, so it is winter."),
                ("orbit", "So seasons come from the tilt, not from how far the Earth is from the Sun.")],
    "solar_system": [("overview", "Our solar system has one star, the Sun, and eight planets moving around it."),
                     ("inner", "The four inner planets, Mercury, Venus, Earth and Mars, are small and rocky."),
                     ("outer", "Further out are the giants: Jupiter, Saturn, Uranus and Neptune."),
                     ("earth", "Earth is the third planet, at just the right distance for liquid water.")],
    "atom": [("overview", "Everything around us is made of atoms."),
             ("nucleus", "At the centre is the nucleus, made of protons and neutrons."),
             ("shells", "Electrons move around the nucleus in shells, each at a different energy."),
             ("electrons", "The number of protons decides the element, and the outer electrons decide how it reacts.")],
}


def narrate(shots: list[dict], lang: str, out_wav: Path) -> None:
    """Speak each shot; its length becomes the shot length (narration first). Writes one joined WAV."""
    from app import tts
    params, chunks, t = None, [], 0
    for s in shots:
        sp = tts.synthesize(s["text"], lang)
        with wave.open(str(sp.path), "rb") as wf:
            p = wf.getparams()
            params = params or p
            if (p.nchannels, p.sampwidth, p.framerate) != (params.nchannels, params.sampwidth, params.framerate):
                raise SystemExit(f"voice format changed mid-lesson ({p.framerate} Hz vs {params.framerate} Hz)")
            data = wf.readframes(wf.getnframes())
        chunks.append(data + b"\x00" * int(GAP_S * params.framerate) * params.nchannels * params.sampwidth)
        s["engine"], s["voice_s"] = sp.engine, sp.duration_s
        s["start"], s["frames"] = t, math.ceil((sp.duration_s + GAP_S) * FPS)
        t += s["frames"]
    with wave.open(str(out_wav), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(b"".join(chunks))


def write_srt(shots: list[dict], path: Path) -> None:
    def ts(sec):
        ms = int(round(sec * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    lines = []
    for i, s in enumerate(shots, 1):
        a = s["start"] / FPS
        lines += [str(i), f"{ts(a)} --> {ts(a + s['voice_s'])}", s["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def make_plan(a) -> dict:
    if a.plan:
        plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))["plan"]
        if plan["template"] == "custom":                 # re-check (and re-layout) saved or hand-edited plans
            plan["scene"] = planner.validate_scene(plan["scene"])
        return plan
    if a.template:
        return {"template": a.template, "element": a.element,
                "shots": [{"focus": f, "narration": n} for f, n in DEFAULT_SCRIPTS[a.template]]}
    choice = planner.route(a.concept)
    print(f"  scene: {choice}")
    if choice in planner.TEMPLATES:
        return planner.plan_template(a.concept, choice)
    return {"template": "custom", "scene": planner.plan_custom(a.concept)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--concept", help="any topic or question; the local model designs the 3D scene")
    ap.add_argument("--template", choices=list(planner.TEMPLATES), help="hand-built scene with its built-in script")
    ap.add_argument("--element", choices=planner.ELEMENTS, default="carbon", help="for --template atom")
    ap.add_argument("--plan", help="re-use plan.json from an earlier run (e.g. to render another language)")
    ap.add_argument("--lang", default="en", help="en, hi, te, ta, ml, mr, kn, bn, gu")
    ap.add_argument("--quality", choices=list(QUALITY), default="draft")
    ap.add_argument("--open", action="store_true", help="open the video when done")
    a = ap.parse_args()
    if not (a.concept or a.template or a.plan):
        ap.error("give --concept, --template or --plan")
    exe = blender_exe()
    if not exe:
        raise SystemExit("Blender not found. Run `python doctor.py` for setup help.")

    times = {}
    t0 = time.perf_counter()
    print("planning...")
    plan = make_plan(a)
    times["plan"] = time.perf_counter() - t0
    custom = plan["template"] == "custom"
    shots = [dict(s) for s in (plan["scene"]["shots"] if custom else plan["shots"])]
    objects = plan["scene"]["objects"] if custom else []

    topic = a.concept or a.template or Path(a.plan).parent.name.split("-", 2)[-1]
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40]
    out = HERE / "out" / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}-{a.lang}"
    out.mkdir(parents=True)

    t0 = time.perf_counter()
    texts = [s["narration"] for s in shots]
    label_ids = [o["id"] for o in objects if o["label"]]
    labels_src = [o["label"] for o in objects if o["label"]]
    if a.lang != "en":
        from app import translate
        print(f"translating {len(texts) + len(labels_src)} lines to {a.lang}...")
        done, engine = translate.translate_batch(texts + labels_src, a.lang)
        texts, labels_src = done[:len(texts)], done[len(texts):]
        print(f"  translated with {engine}")
    for s, txt in zip(shots, texts):
        s["text"] = txt
    times["translate"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    print("narrating...")
    narrate(shots, a.lang, out / "narration.wav")
    labels = render_labels(dict(zip(label_ids, labels_src)), out / "labels") if label_ids else {}
    times["voice+labels"] = time.perf_counter() - t0
    write_srt(shots, out / "lesson.srt")
    total = shots[-1]["start"] + shots[-1]["frames"]

    job = {"fps": FPS, **QUALITY[a.quality], "audio": str(out / "narration.wav"),
           "out": str(out / "lesson.mp4"), "log": str(out / "render.log")}
    if custom:
        job.update(template="custom", scene={"environment": plan["scene"]["environment"], "objects": objects},
                   shots=[{k: s[k] for k in ("camera", "focus", "actions", "start", "frames")} for s in shots],
                   labels={k: list(v) for k, v in labels.items()})
    else:
        job.update(template=plan["template"], params={"element": plan.get("element", "carbon")},
                   shots=[{"focus": s["focus"], "start": s["start"], "frames": s["frames"]} for s in shots])
    (out / "job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps({"concept": a.concept, "plan": plan, "rendered_shots": shots},
                                              indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"rendering {total} frames ({total / FPS:.1f} s) at {job['resolution'][0]}x{job['resolution'][1]}...")
    t0 = time.perf_counter()
    proc = subprocess.run([str(exe), "-b", "--factory-startup", "--python", str(HERE / "blender" / "render3d.py"),
                           "--", str(out / "job.json")], capture_output=True, text=True)
    times["render"] = time.perf_counter() - t0
    log = (out / "render.log").read_text(encoding="utf-8") if (out / "render.log").exists() else ""
    mp4 = out / "lesson.mp4"
    if proc.returncode != 0 or "ERROR" in log or not mp4.exists():
        print(log[-3000:] or proc.stderr[-3000:] or proc.stdout[-3000:])
        raise SystemExit(f"render failed (exit {proc.returncode}); see {out / 'render.log'}")

    video_s = total / FPS
    print("\n" + "\n".join(f"  {k:13} {v:6.1f} s" for k, v in times.items()))
    print(f"  {'total':13} {sum(times.values()):6.1f} s for a {video_s:.1f} s video ({sum(times.values()) / video_s:.1f}x real time)")
    print(f"\nvideo:    {mp4}\ncaptions: {out / 'lesson.srt'}\nplan:     {out / 'plan.json'}")
    if a.open:
        os.startfile(mp4)


if __name__ == "__main__":
    main()
