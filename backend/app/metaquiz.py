"""Meta quiz: one walkable metaverse world built from EVERYTHING the AI wrote for a video or a whole course.

For every video it takes the lesson (all scenes, in the chosen language) and every study tool already made for it
(quiz, flashcards, glossary, FAQ, study guide, timeline, mind map). For the video being watched it first makes the
quiz-shaped tools if they are missing (the others are used when they exist, so nothing slow runs for other episodes).
The result is the JSON the metaverse plays: four stations to read, each followed by a gate that asks several questions.
Data only: the browser draws it; no code comes from the model.
"""
from __future__ import annotations

import json
import logging
import random
import re
from typing import Callable

from .pipeline import LESSONS_DIR, load_lesson
from . import studio

log = logging.getLogger(__name__)
Progress = Callable[[str, float], None]

COLORS = ["#62e6ff", "#ffb454", "#ff6fa8", "#74ffb8"]
SKIP = {"title", "quiz", "summary"}
ZONES = 4                                   # the world has four stations
PER_GATE = 5                                # most questions at one gate
PRIORITY = {"studio": 0, "plan": 1, "flashcard": 2, "glossary": 3}


def _clip(s: str, n: int = 64) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[\s,.;:!?()\[\]\"'/\\\-–—]+", text.lower()) if len(w) >= 3}


# ------------------------------------------------------------------ what exists
def tools_for(lesson_id: str, lang: str) -> dict[str, list[dict]]:
    """Every study-tool result already made for this lesson in `lang` (all sizes and difficulties), by kind."""
    out: dict[str, list[dict]] = {}
    for kind in studio.KINDS:
        found = []
        for f in sorted((LESSONS_DIR / lesson_id).glob(f"studio2_{kind}_{lang}_*.json")):
            try:
                found.append(json.loads(f.read_text(encoding="utf-8"))["data"])
            except (OSError, ValueError, KeyError):
                continue
        if found:
            out[kind] = found
    return out


def _units(lesson: dict, lang: str, video: int, video_title: str) -> list[dict]:
    track = lesson["languages"].get(lang) or next(iter(lesson["languages"].values()))
    units = []
    for s in track["scenes"]:
        if s["template"] in SKIP:
            continue
        items = list(s.get("items") or []) + list(s.get("left") or []) + list(s.get("right") or [])
        text = " ".join([s["heading"], s["narration"], *items])
        units.append({"video": video, "video_title": video_title, "heading": s["heading"], "narration": s["narration"], "items": items,
                      "code": s.get("code") or [], "words": _words(text)})
    return units


# ------------------------------------------------------------------ question pool
def _mcq(q: str, right: str, wrongs: list[str], why: str, source: str, text: str = "") -> dict | None:
    wrongs = [w for w in dict.fromkeys(_clip(w, 90) for w in wrongs) if w and w != _clip(right, 90)][:3]
    if len(wrongs) < 2:
        return None
    return {"q": _clip(q, 160), "options": [_clip(right, 90), *wrongs], "answer": 0, "hint": _clip(why or "Think back to the station you just read.", 140),
            "why": _clip(why, 200) if why else "", "source": source, "words": _words(f"{q} {right} {why} {text}")}


def _pool(lessons: list[dict], tools: list[dict[str, list[dict]]], lang: str) -> list[dict]:
    rng = random.Random(7)
    pool: list[dict] = []
    backs, meanings = [], []
    for t in tools:
        for d in t.get("flashcards", []):
            backs += [c["back"] for c in d["cards"]]
        for d in t.get("glossary", []) + [{"terms": g["terms"]} for g in t.get("studyguide", [])]:
            meanings += [x["meaning"] for x in d["terms"]]
    for lesson, t in zip(lessons, tools):
        for d in t.get("quiz", []):                                 # written by the model, with explanations
            for q in d["questions"]:
                opts = q["options"]
                right = opts[q["answer_index"]]
                pool.append({"q": _clip(q["question"], 160), "options": [_clip(right, 90)] + [_clip(o, 90) for i, o in enumerate(opts) if i != q["answer_index"]],
                             "answer": 0, "hint": _clip(q["explanation"], 140), "why": _clip(q["explanation"], 200), "source": "studio",
                             "words": _words(f"{q['question']} {right} {q['explanation']}")})
        track = lesson["languages"].get(lang) or next(iter(lesson["languages"].values()))
        for s in track["scenes"]:                                   # quiz scenes of the video itself
            if s["template"] == "quiz" and len(s.get("items") or []) >= 3:
                right = s["items"][s["answer_index"]]
                pool.append({"q": _clip(s["heading"], 160), "options": [_clip(right, 90)] + [_clip(o, 90) for i, o in enumerate(s["items"]) if i != s["answer_index"]][:3],
                             "answer": 0, "hint": "Think back to the lesson.", "why": _clip(s["narration"], 200), "source": "plan",
                             "words": _words(f"{s['heading']} {right} {s['narration']}")})
        for d in t.get("flashcards", []):
            for c in d["cards"]:
                m = _mcq(c["front"], c["back"], rng.sample(backs, min(3, len(backs))) if len(backs) > 3 else backs, c["back"], "flashcard")
                if m:
                    pool.append(m)
        for d in t.get("glossary", []):
            for x in d["terms"]:
                label = {"en": 'What does "{}" mean?'}.get(lang, '{}')
                m = _mcq(label.format(x["term"]), x["meaning"], rng.sample(meanings, min(4, len(meanings))), x["meaning"], "glossary", x["term"])
                if m:
                    pool.append(m)
    seen, out = set(), []
    for p in pool:
        key = " ".join(p["q"].lower().split())
        if key not in seen and len(p["options"]) >= 3:
            seen.add(key)
            out.append(p)
    return out


# ------------------------------------------------------------------ the world
def _groups(units: list[dict], videos: int) -> list[list[dict]]:
    if videos >= ZONES:                                              # a course: whole videos go together
        per = -(-videos // ZONES)
        return [g for g in ([u for u in units if i * per <= u["video"] < (i + 1) * per] for i in range(ZONES)) if g]
    n = min(ZONES, len(units))
    size, extra = divmod(len(units), n)
    out, at = [], 0
    for i in range(n):
        step = size + (1 if i < extra else 0)
        out.append(units[at: at + step])
        at += step
    return out


def _fallback(zone_units: list[dict], others: list[dict]) -> dict:
    own = zone_units[0]
    right = _clip(own["items"][0] if own["items"] else own["heading"], 60)
    wrong = [i for o in others for i in (o["items"] or [o["heading"]]) if _clip(i, 60) != right]
    return {"q": f"Which idea belongs to “{_clip(own['heading'], 40)}”?", "options": [right, *[_clip(w, 60) for w in dict.fromkeys(wrong)][:3]],
            "answer": 0, "hint": "Reread the station. The right answer is mentioned there.", "why": "", "source": "plan", "words": set()}


def build_world(lesson_ids: list[str], focus: str | None, lang: str, title: str, progress: Progress = lambda s, p: None) -> dict:
    lessons = [load_lesson(i) for i in lesson_ids]
    focus = focus if focus in lesson_ids else lesson_ids[0]
    lang = lang if lang in lessons[0]["languages"] else next(iter(lessons[0]["languages"]))
    # The video being watched gets its quiz-shaped tools made now if they are missing; everything else already made is simply used.
    for k, kind in enumerate(("quiz", "flashcards", "glossary")):
        progress(f"Writing the {kind} for your video" if kind not in tools_for(focus, lang) else "Collecting what the AI wrote", 0.05 + 0.27 * k)
        if kind not in tools_for(focus, lang):
            try:
                studio.ensure(focus, kind, lang)                     # joins the same queue as the buttons (and goes first)
            except Exception as e:  # noqa: BLE001   the world still works from the lesson itself
                log.warning("meta quiz: could not make %s for %s: %s", kind, focus, e)
    progress("Building the world", 0.85)
    tools = [tools_for(i, lang) for i in lesson_ids]
    units: list[dict] = []
    for n, lesson in enumerate(lessons):
        units += _units(lesson, lang, n, (lesson["languages"].get(lang) or next(iter(lesson["languages"].values())))["title"])
    if len(units) < 2:
        raise ValueError("These videos do not have enough content for a world yet")
    groups = _groups(units, len(lessons))
    pool = _pool(lessons, tools, lang)

    # ---- questions go to the station whose text they overlap most
    gwords = [set().union(*(u["words"] for u in g)) for g in groups]
    assigned: list[list[dict]] = [[] for _ in groups]
    for p in sorted(pool, key=lambda p: PRIORITY[p["source"]]):
        scores = [len(p["words"] & w) / (1 + len(assigned[i]) * 0.5) for i, w in enumerate(gwords)]
        best = max(range(len(groups)), key=lambda i: scores[i])
        if len(assigned[best]) < PER_GATE:
            assigned[best].append(p)
    spare = [p for p in pool if not any(p in a for a in assigned)]
    for i, a in enumerate(assigned):
        while not a and spare:
            a.append(spare.pop(0))
        if not a:
            a.append(_fallback(groups[i], [u for g in groups if g is not groups[i] for u in g]))

    # ---- extra reading from every tool that exists, spread over the stations
    extras: list[list[dict]] = [[] for _ in groups]
    G = len(groups)

    def put(i: int, label: str, text: str) -> None:
        if label and text and len(extras[i % G]) < 8:
            extras[i % G].append({"label": _clip(label, 70), "text": _clip(text, 260)})

    for t in tools:
        for d in t.get("studyguide", []):
            put(0, "Overview", d["overview"])
            for k, pt in enumerate(d["key_points"]):
                put(k, "Key point", pt)
        for d in t.get("timeline", []):
            for k, e in enumerate(d["events"]):
                put(k * G // max(len(d["events"]), 1), f"Step {k + 1}: {e['label']}", e["detail"])
        for d in t.get("faq", []):
            for k, it in enumerate(d["items"]):
                put(k, it["question"], it["answer"])
        for d in t.get("mindmap", []):
            for k, b in enumerate(d["branches"]):
                put(k, f"Map: {b['label']}", "; ".join(c["label"] for c in b["children"]))
        for d in t.get("glossary", []):
            for x in d["terms"]:
                best = max(range(G), key=lambda i: len(_words(x["term"]) & gwords[i]))
                put(best, x["term"], x["meaning"])

    glossary_terms = [x["term"] for t in tools for d in t.get("glossary", []) for x in d["terms"]]
    zones = []
    for i, g in enumerate(groups):
        text = " ".join(u["narration"] for u in g[:2])
        name = g[0]["video_title"] if len(lessons) >= ZONES else g[0]["heading"]
        terms = [t for t in glossary_terms if t.lower() in " ".join([u["narration"] + " " + " ".join(u["items"]) for u in g]).lower()][:4] \
            or [_clip(x, 28) for u in g for x in u["items"]][:4]
        code = next(("\n".join(u["code"][:8]) for u in g if u["code"]), "")
        questions = assigned[i][:PER_GATE]
        clean_q = [{k: v for k, v in q.items() if k not in ("source", "words")} for q in questions]
        zone = {"name": _clip(name, 22), "color": COLORS[i % len(COLORS)],
                "info": {"title": _clip(name, 60), "body": _clip(text, 520), "terms": terms, "extra": extras[i]},
                "quiz": clean_q[0], "more": clean_q[1:]}
        if code:
            zone["info"]["code"] = code
        zones.append(zone)

    last = lessons[-1]["languages"].get(lang) or next(iter(lessons[-1]["languages"].values()))
    summary = next((s["narration"] for s in reversed(last["scenes"]) if s["template"] == "summary"), "")
    guide = next((d["overview"] for t in reversed(tools) for d in t.get("studyguide", [])), "")
    world = {"title": _clip(title or last["title"], 40), "match": (title or lessons[0]["concept"]).lower(), "zones": zones,
             "finale": {"title": "Summit reached", "body": _clip(summary or guide or f"You walked through all of {title}.", 300)}}
    stats = {"videos": len(lessons), "questions": sum(1 + len(z["more"]) for z in zones),
             "tools": sorted({k for t in tools for k in t}), "language": lang}
    progress("Ready", 1.0)
    return {"world": world, "stats": stats}
