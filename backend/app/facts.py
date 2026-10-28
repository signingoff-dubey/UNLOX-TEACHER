"""Fact checker: is what the lesson says true?

A small model writes fluent, confident narration and sometimes gets the facts wrong ("violet bends less than red", "7 colours" followed by a list of six,
a wrong step in an equation). Nothing below needs the internet or an outside AI service; everything runs on this laptop, on the English plan, before it is
translated and recorded. The rule throughout: a lesson is only changed when the evidence is strong, and a correction is only used if it passes the same check.

Layers, cheapest and most certain first:

1. Helpers that need no model: a number that does not match the list after it ("7 colours: red, orange, ... indigo"), arithmetic and linear equations that do not
   work out ("x = 20 / 3" for 3x + 5 = 20), and a few lists every school child is taught (rainbow, planets in order, continents, oceans, senses). They also supply the
   correction, so it is right by construction.
2. The sources. Each statement is compared only with passages that are about it (retrieved for that statement, sharing its key words) from the offline library
   (Simple English Wikipedia and the learner's own PDFs). The judge must quote the words of the source that decide it, and the quote must really be in the passage;
   otherwise the verdict does not count. Supported / contradicted / not mentioned (not an error, only unconfirmed).
3. A second opinion from the language model for what no source covered. It may only say "wrong" when certain, and a second question from the opposite side
   ("is this true?") must agree.

Analogies ("like a prism", "Rainbow = bridge") are not checked: they are not claims. A contradicted statement is replaced by a correction only if the correction passes
the check too; otherwise it is removed (never leaving the scene with too little), and a scene that cannot be repaired is dropped if the lesson can spare it. Quiz answers
are changed only when a source and the model agree. The result is a short report saved with the lesson.
"""
from __future__ import annotations

import ast
import json
import logging
import operator
import re
import time
from dataclasses import dataclass, field

import requests

from . import config, llm
from .knowledge import Passage, retrieve
from .schema import LessonPlan, ScenePlan

log = logging.getLogger(__name__)

MIN_SENTENCE_WORDS = 5
MIN_KEPT_WORDS = 14                      # a scene never loses so much that it stops teaching
MIN_SHARED_TERMS = 2                     # a passage must share this many key words with a statement to be used as evidence
_HOOK = re.compile(r"^(have you|did you|do you|can you|could you|let'?s|imagine|picture|think of|think about|welcome|today|ready|wow|look|now|here'?s|get ready|"
                   r"what if|why do|how do|how does|why does|remember|in this|first,? let|so,? |for this quiz)", re.I)
_ANALOGY = re.compile(r",?\s*(?:just\s+)?(?:like|as if|as though|similar to|the way)\b.*$|\s[=≈]\s(?=[A-Za-z])", re.I)
_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}
_WORDS = "|".join(_NUMBERS)
_STOP = {"that", "this", "with", "from", "have", "what", "when", "where", "which", "there", "their", "they", "them", "then", "than", "into", "also", "each", "every",
         "more", "most", "some", "many", "does", "just", "like", "your", "about", "because", "while", "being", "other", "these", "those", "called", "makes", "make", "made"}


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in _STOP}


# ---------------------------------------------------------------- layer 1: no model needed
_COUNT = re.compile(r"\b(\d{1,2}|" + _WORDS + r")\b([^:;.!?]{0,45}?)(?::|—| are | is | namely )\s*([^.!?]+)", re.I)


def count_issue(sentence: str) -> str | None:
    """"7 colours: red, orange, yellow, green, blue, indigo" says seven and names six."""
    m = _COUNT.search(sentence)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1).isdigit() else _NUMBERS[m.group(1).lower()]
    parts = [p.strip(" .") for p in re.split(r",|;|\band\b|&", m.group(3)) if p.strip(" .")]
    if len(parts) < 3 or any(len(p.split()) > 4 for p in parts) or n == len(parts) or n < 3:
        return None
    return f"it says {n} but names {len(parts)} ({', '.join(parts)})"


# the lists every school child is taught: (members in their correct order, words that show the sentence is about the list, the noun that is counted)
CANON = {
    "colours of the rainbow": (("red", "orange", "yellow", "green", "blue", "indigo", "violet"), r"rainbow|spectrum", r"colou?rs?"),
    "planets of the solar system": (("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"), r"solar system|planets?\b", r"planets?"),
    "continents": (("asia", "africa", "north america", "south america", "antarctica", "europe", "australia"), r"continents?", r"continents?"),
    "oceans": (("pacific", "atlantic", "indian", "southern", "arctic"), r"oceans?", r"oceans?"),
    "senses": (("sight", "hearing", "smell", "taste", "touch"), r"senses", r"senses"),
}


def table_issue(sentence: str) -> str | None:
    low = sentence.lower()
    for name, (members, about, noun) in CANON.items():
        if not re.search(about, low):
            continue
        for m in re.finditer(r"\b(\d{1,2}|" + _WORDS + r")\s+(?:(?!of\b)\w+\s+){0,2}" + noun, low):
            n = int(m.group(1)) if m.group(1).isdigit() else _NUMBERS[m.group(1)]
            before = low[: m.start()]
            if n != len(members) and not re.search(r"(?:only|about|nearly|almost|over|more than|at least|one|of|in)\s*$", before):
                return f"there are {len(members)} {name} ({', '.join(members)}), not {n}"
        found = [(low.find(x), x) for x in members if re.search(r"\b" + re.escape(x) + r"\b", low)]
        if len(found) >= len(members) - 1 and len(found) < len(members):
            missing = [x for x in members if x not in {f[1] for f in found}]
            return f"the {name} are {', '.join(members)}; this leaves out {', '.join(missing)}"
        if name.startswith("planets") and len(found) >= 4 and re.search(r"order|from the sun|closest|farthest|next|then", low):
            order = [x for _, x in sorted(found)]
            if order != [x for x in members if x in order]:
                return f"the planets from the Sun are {', '.join(members)}"
    return None


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _evaluate(expr: str) -> float | None:
    """Only numbers and + - * / (also x, × and ÷): nothing else is ever evaluated."""
    expr = expr.replace("×", "*").replace("÷", "/").replace("−", "-")
    expr = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", expr)

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        raise ValueError
    try:
        return ev(ast.parse(expr.strip(), mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError):
        return None


_ARITH = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?(?:\s*[-+×x*÷/−]\s*-?\d+(?:\.\d+)?)+)\s*=\s*(-?\d+(?:\.\d+)?)(?![\w.]*\s*[-+×x*÷/])")
_LINEAR = re.compile(r"(-?\d*)\s*([a-z])\s*([-+−])\s*(\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)")
_ASSIGN = re.compile(r"\b([a-z])\s*=\s*(-?[\d.]+(?:\s*[-+×x*÷/−]\s*-?[\d.]+)*)")


def _fmt(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:.2f}".rstrip("0").rstrip(".")


def solution_of(text: str) -> tuple[str, float, str] | None:
    """The solution of the first equation like 3x + 5 = 20 in the text: (variable, value, the equation)."""
    m = _LINEAR.search(text)
    if not m:
        return None
    a = {"": 1.0, "-": -1.0}.get(m.group(1).strip(), None)
    a = a if a is not None else float(m.group(1))
    if a == 0:
        return None
    b = float(m.group(4)) * (1 if m.group(3) == "+" else -1)
    return m.group(2), (float(m.group(5)) - b) / a, m.group(0).strip()


def math_issue(sentence: str, scene_text: str = "") -> tuple[str, str] | None:
    """(what is wrong, the corrected statement) for a calculation that does not work out, or for x = ... that is not the solution of the scene's equation."""
    for m in _ARITH.finditer(sentence):
        got, claimed = _evaluate(m.group(1)), float(m.group(2))
        if got is not None and abs(got - claimed) > 0.01 * max(1.0, abs(got)):
            fixed = sentence.replace(m.group(0), f"{m.group(1).strip()} = {_fmt(got)}", 1)
            return f"{m.group(1).strip()} is {_fmt(got)}, not {m.group(2)}", fixed
    sol = solution_of(scene_text or sentence)
    if sol:
        var, value, eq = sol
        for m in _ASSIGN.finditer(sentence):
            if m.group(1) != var:
                continue
            got = _evaluate(m.group(2))
            if got is not None and abs(got - value) > 0.01 * max(1.0, abs(value)):
                return f"the solution of {eq} is {var} = {_fmt(value)}, not {_fmt(got)}", sentence.replace(m.group(0), f"{var} = {_fmt(value)}", 1)
    return None


# ---------------------------------------------------------------- claims
@dataclass
class Claim:
    scene: int
    kind: str                  # "narration", "item" or "quiz"
    text: str                  # the part that is checked (without an analogy at its end)
    full: str = ""             # the whole sentence or item, as it stands in the scene
    index: int = 0             # which item of the scene, for kind == "item"
    verdict: str = ""          # supported / contradicted / not_mentioned / supported_by_model / wrong / fixed / removed / unconfirmed
    fix: str = ""
    quote: str = ""
    source: str = ""           # title of the article that confirmed it
    issue: str = ""            # what the helpers found, if anything
    sure_fix: str = ""         # a correction that is right by construction (arithmetic, a canonical list)

    @property
    def strong(self) -> bool:
        """Certain enough to remove a whole scene: a helper found it, or a source contradicts it and the quote was confirmed. The model's own opinion alone is not."""
        return bool(self.issue or self.sure_fix or (self.verdict in ("contradicted", "unresolved") and self.quote))
    passages: list[Passage] = field(default_factory=list)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", text.strip()) if s.strip()]


def is_checkable(s: str) -> bool:
    """A statement of fact: not a question, a greeting, a hook, or a few words."""
    return len(s.split()) >= MIN_SENTENCE_WORDS and not s.endswith("?") and not _HOOK.match(s)


def claims_of(plan: LessonPlan) -> list[Claim]:
    out: list[Claim] = []
    for i, sc in enumerate(plan.scenes):
        if sc.template == "code":
            continue                                           # code is checked by review.py (it must parse); its narration only describes it
        if sc.template == "quiz":
            q = " ".join(s for s in sentences(sc.narration) if s.endswith("?"))
            if q and sc.items and 0 <= sc.answer_index < len(sc.items):
                out.append(Claim(i, "quiz", f"{q} Correct answer: {sc.items[sc.answer_index]}", full=sc.narration))
            continue
        for s in sentences(sc.narration):
            literal = _ANALOGY.sub("", s).strip(" ,;")
            if is_checkable(s) and len(literal.split()) >= MIN_SENTENCE_WORDS:
                out.append(Claim(i, "narration", literal if literal != s else s, full=s))
        for k, it in enumerate(sc.items):
            if len(it.split()) >= 4 and not it.endswith("?") and not _ANALOGY.search(it):
                out.append(Claim(i, "item", it, full=it, index=k))
    return out


# ---------------------------------------------------------------- evidence
def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def quote_is_real(quote: str, passages: list[Passage]) -> bool:
    """The judge must show the words that decide it, and they must really be in a passage (an invented quote means an invented verdict)."""
    pieces = [p for p in (_norm(x) for x in re.split(r"\.\.\.|…", quote)) if len(p.split()) >= 3]
    haystack = [_norm(p.text) for p in passages]
    return bool(pieces) and all(any(piece in h for h in haystack) for piece in pieces)


def relevant_passages(claim: Claim, upload: str | None) -> list[Passage]:
    """Passages retrieved for this statement that really share its key words (a statement about light is not judged against the article on the Moon)."""
    key = _stems(claim.text)
    out = []
    for p in retrieve(claim.text, upload=upload):
        if len(key & _stems(p.text)) >= min(MIN_SHARED_TERMS, max(1, len(key) - 1)) and p.text not in {q.text for q in out}:
            out.append(p)
    return out[:3]


# ---------------------------------------------------------------- layers 2 and 3: the language model as a judge
def _chat_json(prompt: str, num_predict: int = 450) -> dict | None:
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": llm.current_model(), "stream": False, "think": False, "format": "json", "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "messages": [{"role": "user", "content": prompt}],
            "options": config.ollama_options({"temperature": 0, "num_predict": num_predict}),
        }, timeout=120)
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("fact check call failed: %s", e)
        return None


def _numbered(claims: list[Claim]) -> str:
    return "\n".join(f"{n}. {c.text}" for n, c in enumerate(claims, 1))


def _results(data, claims: list[Claim]):
    for r in (data or {}).get("results", []) if isinstance(data, dict) else []:
        try:
            yield claims[int(r["n"]) - 1], r
        except (KeyError, ValueError, IndexError, TypeError):
            continue


def judge_with_source(claims: list[Claim]) -> None:
    """Compare statements with their own passages. Sets verdict (supported / contradicted / not_mentioned), quote, fix and source.
    A verdict only counts with a quote that is really in the source."""
    claims = [c for c in claims if c.passages]
    if not claims:
        return
    ps: list[Passage] = []
    for c in claims:
        for p in c.passages:
            if p.text not in {q.text for q in ps}:
                ps.append(p)
    ps = ps[:5]
    src = "\n".join(f"[{i}] {p.title}: {p.text[:650]}" for i, p in enumerate(ps, 1))
    prompt = (
        "You are a strict fact checker for a school lesson. Compare each STATEMENT with the SOURCE.\n"
        "supported = the source says it or clearly implies it.\n"
        "contradicted = the source says something different about the same fact (another number, order, cause, name or direction).\n"
        "not_mentioned = the source does not cover it. Do not guess: not_mentioned is not an error.\n"
        f"SOURCE:\n{src}\n\nSTATEMENTS:\n{_numbered(claims)}\n\n"
        'Answer only JSON: {"results":[{"n":1,"verdict":"supported","source":1,"quote":"words copied exactly from the source","fix":""}]}. '
        '"quote" must be copied word for word from the source and must be what decides the verdict. '
        'For contradicted, "fix" is the statement corrected using only the source, in the same simple words and about the same length.')
    for c, r in _results(_chat_json(prompt, 90 + 110 * len(claims)), claims):
        v = str(r.get("verdict", "")).lower().strip()
        if v not in ("supported", "contradicted", "not_mentioned"):
            continue
        quote = str(r.get("quote") or "")
        try:
            src_p = ps[int(r.get("source")) - 1]
        except (ValueError, IndexError, TypeError):
            src_p = None
        if v != "not_mentioned" and not quote_is_real(quote, [src_p] if src_p else ps):
            v = "not_mentioned"                                  # no real quote, no verdict
        c.verdict, c.quote = v, quote if v != "not_mentioned" else ""
        c.fix = str(r.get("fix") or "").strip() if v == "contradicted" else ""
        c.source = src_p.title if (src_p and v == "supported") else ""
    for c in claims:
        if c.verdict == "contradicted" and not confirm_contradiction(c):
            c.verdict, c.fix, c.quote = "not_mentioned", "", ""             # the batch judge was not sure enough: leave the lesson as it is


def confirm_contradiction(c: Claim) -> bool:
    """One focused question about the quote and the statement alone. Both must hold: it is the very same fact, and the two cannot both be true.
    (A quote about oxygen in steel-making does not contradict "coal removes impurities"; the batch judge said it did.)"""
    data = _chat_json(f'SOURCE SENTENCE: "{c.quote}"\nSTATEMENT: "{c.text}"\n'
                      'Answer only JSON: {"same_fact": true or false, "contradicts": true or false}. '
                      "same_fact = the source sentence is about the very same fact as the statement (not just the same subject). "
                      "contradicts = the statement cannot be true if the source sentence is true.", 40)
    return isinstance(data, dict) and data.get("same_fact") is True and data.get("contradicts") is True


def judge_with_knowledge(claims: list[Claim], topic: str) -> None:
    """A second opinion for statements no source covered. 'wrong' only when the model is certain and a question from the opposite side agrees."""
    claims = [c for c in claims]
    if not claims:
        return
    prompt = (
        f"You are a careful teacher checking a school lesson about \"{topic}\", written by a small AI model that sometimes gets facts wrong.\n"
        'For each STATEMENT answer "correct", "wrong" or "unsure". Say "wrong" only when you are certain that a textbook says the opposite '
        "(a wrong number, order, cause, direction or name). Simplifications for children are fine. When in doubt, say unsure.\n"
        f"STATEMENTS:\n{_numbered(claims)}\n\n"
        'Answer only JSON: {"results":[{"n":1,"verdict":"correct","fix":""}]}. For wrong, "fix" is the statement corrected, in the same simple words and about the same length. '
        "Keep every answer short.")
    for c, r in _results(_chat_json(prompt, 90 + 70 * len(claims)), claims):
        v = {"correct": "supported_by_model", "wrong": "wrong", "unsure": "not_mentioned"}.get(str(r.get("verdict", "")).lower().strip())
        if v:
            c.verdict = v
            c.fix = str(r.get("fix") or "").strip() if v == "wrong" else ""
    doubtful = [c for c in claims if c.verdict == "wrong"]
    if doubtful:                                                 # the opposite question: is it TRUE? Only a "no" confirms the error
        data = _chat_json(f"Topic: {topic}. Is each statement true according to a school textbook?\n{_numbered(doubtful)}\n"
                          'Answer only JSON: {"results":[{"n":1,"true":true}]}', 60 + 25 * len(doubtful))
        said_no = {id(c) for c, r in _results(data, doubtful) if r.get("true") is False}
        for c in doubtful:
            if id(c) not in said_no:
                c.verdict, c.fix = "not_mentioned", ""


_STYLE = re.compile(r"[()\[\]\"“”]|\bfix\b|\bcorrect(?:ed)?\b|\bnot all\b|^\W|\n", re.I)


def acceptable(old: str, new: str) -> bool:
    n = len(new.split())
    keep = _stems(old)
    kept = len(keep & _stems(new)) / len(keep) if keep else 1.0              # a correction changes the fact, it does not throw the sentence away
    return bool(new) and new.strip().lower() != old.strip().lower() and MIN_SENTENCE_WORDS <= n <= max(45, int(len(old.split()) * 1.6)) and kept >= 0.5 \
        and not _STYLE.search(new) and not count_issue(new) and not table_issue(new) and not math_issue(new)


def rewrite(sentence: str, issue: str, passages: list[Passage]) -> str | None:
    """A corrected version of one statement, using the source if there is one. Free text, so the model can write it plainly."""
    src = "\n".join(f"{p.title}: {p.text[:600]}" for p in passages[:2])
    prompt = (f"Rewrite this sentence from a school lesson so that it is factually correct. Problem: {issue}\n"
              + (f"Use this source:\n{src}\n" if src else "") +
              f"Sentence: {sentence}\nKeep the same simple words and about {len(sentence.split())} words. Output only the new sentence, with no brackets and no notes.")
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", json={
            "model": llm.current_model(), "stream": False, "think": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "messages": [{"role": "user", "content": prompt}],
            "options": config.ollama_options({"temperature": 0.2, "num_predict": 90}),
        }, timeout=90)
        r.raise_for_status()
        text = " ".join(r.json()["message"]["content"].split())
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("fact rewrite failed: %s", e)
        return None
    return text if acceptable(sentence, text) else None


def pick_answer(question: str, options: list[str], passages: list[Passage]) -> int | None:
    """Which option is right, according to the source? None when it cannot tell."""
    src = "\n".join(f"{p.title}: {p.text[:700]}" for p in passages[:3])
    opts = "\n".join(f"{i}. {o}" for i, o in enumerate(options, 1))
    data = _chat_json((f"Use this source:\n{src}\n" if src else "") + f"Question: {question}\nOptions:\n{opts}\n"
                      'Which option is correct? Answer only JSON: {"answer": <number of the option, or 0 if you are not sure>}', 40)
    try:
        n = int((data or {}).get("answer", 0))
    except (ValueError, TypeError):
        return None
    return n - 1 if 1 <= n <= len(options) else None


# ---------------------------------------------------------------- the whole plan
@dataclass
class Report:
    checked: int = 0
    supported: int = 0
    confirmed_by_model: int = 0
    unconfirmed: int = 0
    fixed: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    seconds: float = 0.0
    partial: bool = False
    scenes: dict[int, str] = field(default_factory=dict)         # scene number -> verified / fixed / unconfirmed

    def notes(self) -> list[str]:
        out = []
        if self.fixed or self.removed:
            out.append(f"fact check: {len(self.fixed)} statements corrected, {len(self.removed)} removed ({self.supported} confirmed by sources, {self.unconfirmed} not confirmed)")
        for f in self.fixed:
            out.append(f"scene {f['scene']}: '{f['before'][:70]}' -> '{f['after'][:70]}' ({f['why']})")
        for r in self.removed:
            out.append(f"scene {r['scene']}: removed '{r['text'][:70]}' ({r['why']})")
        return out

    def summary(self) -> dict:
        return {"checked": self.checked, "supported": self.supported, "confirmed_by_model": self.confirmed_by_model, "unconfirmed": self.unconfirmed,
                "fixed": self.fixed, "removed": self.removed, "sources": self.sources, "seconds": round(self.seconds, 1), "partial": self.partial,
                "scenes": {str(k): v for k, v in self.scenes.items()}}


def _replace(scene: ScenePlan, c: Claim, new: str | None) -> bool:
    """Put the corrected statement in place of the old one (new=None removes it). False when removing would leave too little."""
    if c.kind == "item":
        if new is None:
            if len(scene.items) <= 2:
                return False
            scene.items.pop(c.index)
            return True
        scene.items[c.index] = new
        return True
    if new is None:
        rest = " ".join(scene.narration.replace(c.full, "", 1).split())
        if len(rest.split()) < MIN_KEPT_WORDS:
            return False
        scene.narration = rest
        return True
    scene.narration = scene.narration.replace(c.text, new, 1)
    return True


def check_plan(plan: LessonPlan, concept: str, upload: str | None = None, budget_s: float | None = None, progress=lambda f: None) -> Report:
    """Checks and repairs the plan in place. Never raises: a failure here must not stop a lesson."""
    rep = Report()
    t0 = time.perf_counter()
    budget = config.FACTCHECK_BUDGET_S if budget_s is None else budget_s
    over = lambda extra=0: time.perf_counter() - t0 > budget + extra  # noqa: E731
    try:
        topic = concept or plan.title
        claims = claims_of(plan)
        rep.checked = len(claims)
        lesson_text = " ".join(f"{s.narration} {' '.join(s.items)}" for s in plan.scenes)
        # layer 1: the helpers; layer 2: each statement's own passages
        for n, c in enumerate(claims):
            progress(0.4 * n / max(len(claims), 1))
            if c.kind == "quiz":
                c.passages = [] if over() else relevant_passages(c, upload)
                continue
            m = math_issue(c.text, lesson_text)
            if m:
                c.issue, c.sure_fix = m
            else:
                c.issue = count_issue(c.text) or table_issue(c.text) or ""
            if not over() and not c.issue:
                c.passages = relevant_passages(c, upload)
        by_scene: dict[int, list[Claim]] = {}
        for c in claims:
            by_scene.setdefault(c.scene, []).append(c)
        for i, cs in sorted(by_scene.items()):
            if over():
                rep.partial = True
                break
            judge_with_source([c for c in cs if c.kind != "quiz" or c.passages])
        # layer 3: the model's own knowledge for what no source confirmed (one call for the lesson, at most 24 statements)
        if not over():
            judge_with_knowledge([c for c in claims if c.kind != "quiz" and not c.issue and c.verdict in ("", "not_mentioned")][:24], topic)
        progress(0.7)
        # repairs: a correction is used only if it passes the check too
        bad = [c for c in claims if c.kind != "quiz" and (c.verdict in ("contradicted", "wrong") or c.issue)]
        proposals: dict[int, str] = {}
        for c in bad:
            if c.sure_fix:
                proposals[id(c)] = c.sure_fix
            elif not over(15):
                new = c.fix if c.fix and acceptable(c.text, c.fix) else rewrite(c.text, c.issue or "it contradicts the source", c.passages)
                if new:
                    proposals[id(c)] = new
        if proposals and not over(25):
            candidates = [Claim(c.scene, c.kind, proposals[id(c)], full=proposals[id(c)]) for c in bad if id(c) in proposals and not c.sure_fix]
            for cand in candidates:
                cand.passages = relevant_passages(cand, upload)
            judge_with_source(candidates)
            judge_with_knowledge([cand for cand in candidates if cand.verdict in ("", "not_mentioned")], topic)
            trusted = {cand.text for cand in candidates if cand.verdict in ("supported", "supported_by_model")}
        else:
            trusted = set()
        for c in bad:
            scene = plan.scenes[c.scene]
            why = c.issue or ("contradicts " + (c.source or (c.passages[0].title if c.passages else "known facts")) + (f': "{c.quote[:90]}"' if c.quote else ""))
            new = proposals.get(id(c))
            if new and (c.sure_fix or new in trusted) and _replace(scene, c, new):
                rep.fixed.append({"scene": c.scene + 1, "before": c.text, "after": new, "why": why})
                c.verdict = "fixed"
            elif _replace(scene, c, None):
                rep.removed.append({"scene": c.scene + 1, "text": c.text, "why": why})
                c.verdict = "removed"
            elif c.strong:
                c.verdict = "unresolved"                                   # cannot be removed without leaving the scene empty
            else:
                c.verdict = "unconfirmed"                                  # only the model doubts it: reported, the scene stays
        # quiz answers: only changed when a source and the model agree
        for c in claims:
            if c.kind == "quiz" and c.verdict == "contradicted" and c.quote:
                scene = plan.scenes[c.scene]
                pick = pick_answer(c.text.split(" Correct answer:")[0], scene.items, c.passages)
                if pick is not None and pick != scene.answer_index:
                    rep.fixed.append({"scene": c.scene + 1, "before": f"answer: {scene.items[scene.answer_index]}", "after": f"answer: {scene.items[pick]}", "why": "quiz answer contradicts the source"})
                    scene.answer_index = pick
                    c.verdict = "fixed"
                else:
                    c.verdict = "unconfirmed"                                  # a quiz is never removed: it is reported
        # ... a scene with a wrong statement that cannot be removed goes, if the lesson can spare it (never the opening scene, never below four scenes)
        for i in sorted({c.scene for c in claims if c.verdict == "unresolved"}, reverse=True):
            if i > 0 and len(plan.scenes) > 4:
                wrong = next((c.text for c in claims if c.scene == i and c.verdict == "unresolved"), plan.scenes[i].heading)
                rep.removed.append({"scene": i + 1, "text": wrong, "why": f"a wrong statement that could not be corrected (the scene '{plan.scenes[i].heading}' was removed)"})
                del plan.scenes[i]
                for c in claims:
                    if c.scene == i:
                        c.verdict = "removed"
                    elif c.scene > i:
                        c.scene -= 1
        for c in claims:
            if c.verdict == "supported":
                rep.supported += 1
                if c.source and c.source not in rep.sources:
                    rep.sources.append(c.source)
            elif c.verdict == "supported_by_model":
                rep.confirmed_by_model += 1
            elif c.verdict in ("", "not_mentioned", "unresolved", "contradicted", "wrong"):
                rep.unconfirmed += 1
        for i in range(len(plan.scenes)):
            states = [c.verdict for c in claims if c.scene == i]
            if states:
                rep.scenes[i + 1] = "fixed" if any(s in ("fixed", "removed") for s in states) else \
                    "verified" if all(s in ("supported", "supported_by_model") for s in states) else "unconfirmed"
    except Exception:  # noqa: BLE001  the fact check must never stop a lesson
        log.exception("fact check stopped")
        rep.partial = True
    rep.seconds = time.perf_counter() - t0
    progress(1.0)
    return rep
