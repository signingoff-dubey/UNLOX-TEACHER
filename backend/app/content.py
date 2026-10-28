"""What the student actually sees: repeated scenes, repeated code, a title card in the middle, a summary after every part, captions of four words.

A long video is planned in parts and a course in episodes. Each part used to be written like a lesson of its own (a title card, a quiz, a summary),
the parts could not see each other, and the pieces were glued together afterwards. The result was 18 scenes for 120 seconds, the heading
"Summary" three times, near-identical code blocks and narration of 4 to 16 words. These helpers give every part its role, tell it what was already
taught, and clean the joined plan the way a viewer would judge it.
"""
from __future__ import annotations

import re

from .schema import SCHEMA_WORDS, LessonPlan, ScenePlan

MIN_NARRATION_WORDS = 18                       # a scene that says less than this is a label, not teaching
PLACEHOLDER = re.compile(r"^\s*let'?s learn about\b", re.I)
_BOILER = re.compile(r"^\s*(public\s+class\b|class\s+\w+\s*[:{(]?\s*$|public\s+static\s+void\s+main|def\s+main\b|if\s+__name__|import\s|#include|using\s+namespace|package\s)", re.I)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _words(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2}


def _opening(text: str) -> list[str]:
    """The first six words of a narration: two scenes that begin the same way are the same scene said twice."""
    return _norm(text).split()[:6]


def similarity(a: str, b: str) -> float:
    x, y = _words(a), _words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _code_lines(lines: list[str]) -> set[str]:
    return {re.sub(r"\s+", " ", ln.strip()) for ln in lines if len(ln.strip()) > 3 and ln.strip() not in ("{", "}", "};", ")", "});")}


def code_overlap(a: list[str], b: list[str]) -> float:
    """How much of the shorter snippet is also in the other (boilerplate included: a second copy of the same class skeleton is a repeat too)."""
    x, y = _code_lines(a), _code_lines(b)
    return len(x & y) / min(len(x), len(y)) if x and y else 0.0


def boilerplate_lines(lines: list[str]) -> int:
    return sum(1 for ln in lines if _BOILER.search(ln))


def is_placeholder(scene: ScenePlan) -> bool:
    return bool(PLACEHOLDER.match(scene.narration)) or len(scene.narration.split()) < 5


# ---------------------------------------------------------------- the role of each part of a long video
def clean_part(plan: LessonPlan, index: int, total: int) -> list[str]:
    """Part `index` of `total` (1-based): only the first part opens with a title card, only the last has the quiz and the summary.
    The model often writes them anyway; they are removed here (never down to fewer than two scenes). Returns what was dropped."""
    notes: list[str] = []
    keep: list[ScenePlan] = []
    for k, s in enumerate(plan.scenes):
        why = ""
        if s.template == "title" and (index > 1 or k > 0):
            why = "a title card inside the video"
        elif s.template in ("summary", "quiz") and index < total:
            why = f"a {s.template} before the last part"
        elif s.template == "summary" and k != len(plan.scenes) - 1 and index == total:
            why = "a summary that is not at the end"
        if why and len(plan.scenes) - len(notes) > 2:
            notes.append(f"part {index}: dropped scene {k + 1} ({s.template}: {why})")
            continue
        keep.append(s)
    plan.scenes = keep
    if index < total:
        plan.common_mistakes = []                      # one "common mistakes" scene for the whole video, written in the last part
    return notes


# ---------------------------------------------------------------- the joined plan, judged as a viewer would
def dedupe_plan(plan: LessonPlan) -> list[str]:
    """Drop a scene that repeats an earlier one: the same heading with similar words, nearly the same narration, or nearly the same code.
    Only one summary is kept (the last). The first scene is never dropped and at least three scenes remain."""
    notes: list[str] = []
    kept: list[ScenePlan] = []
    summaries = [i for i, s in enumerate(plan.scenes) if s.template == "summary"]
    last_summary = summaries[-1] if summaries else -1
    for i, s in enumerate(plan.scenes):
        why = ""
        if i and s.template == "summary" and i != last_summary:
            why = "an earlier summary (one summary, at the end)"
        elif i and is_placeholder(s):
            why = "a placeholder caption"
        elif i:
            for e in kept:
                same_heading = _norm(e.heading) == _norm(s.heading)
                if same_heading:
                    why = f"the heading '{s.heading}' again"
                elif similarity(e.narration, s.narration) > 0.7 or (len(_opening(s.narration)) >= 6 and _opening(e.narration) == _opening(s.narration)):
                    why = "narration that repeats an earlier scene"
                elif s.template == "code" and e.template == "code" and code_overlap(e.code, s.code) >= 0.6:
                    why = "code that repeats an earlier scene"
                if why:
                    break
        if why and len(plan.scenes) - len(notes) > 3:
            notes.append(f"scene {i + 1} ({s.template}, '{s.heading}') dropped: {why}")
            continue
        kept.append(s)
    plan.scenes = kept
    return notes


def narration_problems(plan: LessonPlan) -> list[int]:
    """Indexes of scenes whose narration is too short to teach anything (not the title card, which may be one line)."""
    return [i for i, s in enumerate(plan.scenes) if i and len(s.narration.split()) < MIN_NARRATION_WORDS]


def repeated_code(plan: LessonPlan) -> str | None:
    code = [s for s in plan.scenes if s.template == "code" and s.code]
    for a in range(len(code)):
        for b in range(a + 1, len(code)):
            if code_overlap(code[a].code, code[b].code) >= 0.6:
                return "two code scenes show the same code; every code scene must show NEW code that builds on the one before, and only the lines that matter"
    if sum(1 for s in code if boilerplate_lines(s.code) >= 2) > 1:
        return "the class and main() skeleton is repeated in several code scenes; show it at most once and only the key lines afterwards"
    return None


def schema_echo(plan: LessonPlan) -> str | None:
    """The model copied a word of the JSON schema into the lesson: a heading or a sentence about "string"."""
    for s in plan.scenes:
        if s.heading.strip().lower().strip(".:") in SCHEMA_WORDS or re.search(r"\b(explore|learn about|about|called)\s+(string|heading|narration)\b", s.narration, re.I):
            return "a scene has the placeholder 'string' where its heading or narration should be; write a real heading and real narration about the topic in every scene"
    return None


def repeated_headings(plan: LessonPlan) -> str | None:
    seen: set[str] = set()
    for s in plan.scenes:
        h = _norm(s.heading)
        if h in seen:
            return f"the heading '{s.heading}' is used twice; every scene needs its own heading"
        seen.add(h)
    return None


# ---------------------------------------------------------------- what the next part (or episode) is told about this one
def taught_summary(plan: LessonPlan, limit: int = 900) -> str:
    """The headings, key points and the first lines of code of a finished part, so the next one builds on it instead of repeating it."""
    lines: list[str] = []
    for s in plan.scenes:
        if s.template in ("title", "quiz", "summary"):
            continue
        point = "; ".join(s.items[:3]) if s.items else s.narration.split(".")[0][:90]
        entry = f"- {s.heading}: {point}"
        if s.template == "code" and s.code:
            shown = [ln.strip() for ln in s.code if ln.strip() and ln.strip() not in ("{", "}") and not _BOILER.search(ln)][:2]
            if shown:
                entry += f" [code shown: {' '.join(shown)[:110]}]"
        lines.append(entry)
    out = "\n".join(lines)
    return out[:limit]


# ---------------------------------------------------------------- the subject of a request, without the request
_LEAD = re.compile(r"^(?:(?:hey|hi|hello|ok|okay|so|now|well|please|pls|kindly)[,\s]+)+", re.I)
_WRAP = re.compile(r"^(?:(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+)?|(?:i|we)\s+(?:want|wanna|need|would\s+like|'d\s+like)\s+(?:you\s+)?(?:to\s+)?|(?:let'?s|lets)\s+|go\s+ahead\s+and\s+)+", re.I)
_VERB = re.compile(
    r"^(?:(?:teach|show|tell|explain|help|walk|guide|train)\s+(?:me|us)\s+(?:about\s+|on\s+|how\s+to\s+|the\s+basics\s+of\s+|the\s+concept\s+of\s+)?"
    r"|(?:teach|explain|describe|cover|introduce)\s+(?:to\s+me\s+)?(?:about\s+)?"
    r"|(?:learn|study|understand|know|revise|review)\s+(?:more\s+)?(?:about\s+)?"
    r"|(?:make|create|generate|build|produce|give|prepare)\s+(?:me\s+|us\s+)?(?:an?\s+|the\s+|one\s+)?(?:short\s+|quick\s+|new\s+)?(?:video|lesson|course|tutorial|explainer|clip)\s*(?:on|about|for|of|regarding|covering)?\s+)",
    re.I)
_TAIL = re.compile(r"[\s,]*(?:please|pls|for me|thanks|thank you)\s*[.!?]*$", re.I)
_CASE = {"dsa": "DSA", "java": "Java", "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript", "sql": "SQL", "html": "HTML", "css": "CSS",
         "api": "API", "ai": "AI", "ml": "ML", "oop": "OOP", "dbms": "DBMS", "c++": "C++", "kotlin": "Kotlin", "react": "React", "git": "Git", "linux": "Linux"}


def clean_topic(text: str) -> str:
    """The subject of what the learner typed: "teach me about dsa in java" is "DSA in Java", "can you make a video on the water cycle please" is "the water cycle".
    The request words used to go into the lesson with the topic, so every title and caption began with "Teach me ...". Questions ("how do vaccines work") are left as they are;
    text that is only a request (nothing left after it) is kept whole."""
    original = " ".join(text.split())
    t = _LEAD.sub("", original)
    t = _WRAP.sub("", t)
    t = _VERB.sub("", t)
    t = _TAIL.sub("", t).strip(" ,.:;!?\"'")
    if len(t) < 2 or t.lower() in ("me", "us", "it", "this", "that"):
        return original
    if t.islower() or (t.upper() == t and len(t) > 4):                     # all lower case (or all capitals): put the well-known names right
        t = " ".join(_CASE.get(w.lower(), w) for w in t.split())
    if t[0].islower():
        t = t[0].upper() + t[1:]
    return t
