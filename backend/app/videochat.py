"""Asking the tutor chat for another video: "generate one more video on tides", "make another one about black holes, 2 minutes".

`detect` recognises that kind of request by its words (no language-model call, so the answer is instant and the GPU is not touched).
`handle` then adds the new video to the playlist of the lesson being watched (a lesson that is not in a playlist yet is wrapped in one,
as episode 1) and starts building it in the background; it is built scene by scene like every other video, and the page shows it in the
chat, in the player and in the playlist as soon as its first scenes exist.
"""
from __future__ import annotations

import logging
import re

from . import jobs, playlist
from .pipeline import load_lesson

log = logging.getLogger(__name__)

VERB = r"(?:generate|make|create|build|produce|record|prepare|render|add|give|get|do|start|show)"
NOUN = r"(?:videos?|lessons?|episodes?|explainers?|clips?|tutorials?)"
OPENER = (r"^(?:(?:hey|hi|ok|okay|so|now|and|also|then|well)[,\s]+)*"
          r"(?:(?:can|could|would|will) (?:you|u) (?:please )?|please |pls |kindly |i (?:want|need|would like|'d like|d like) (?:you )?(?:to )?|(?:let's|lets) |go ahead and |you can )*")
CONNECTOR = r"(?:on|about|for|of|regarding|covering|that|which|explain(?:s|ing)?|teach(?:es|ing)?|show(?:s|ing)?|cover(?:s|ing)?|in|with|to explain|to teach)"
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "half": 0.5}

# "generate a (short) video on X", "make me another lesson about X", "create one more video"
_WITH_NOUN = re.compile(rf"^{VERB}\b(?: me| us)?(?: (?:a|an|the|one|another|one more|a new|new|more|next|different|second|third|short|quick|small|simple|\d+[- ]?(?:minute|min|second|sec)s?|\d+))* {NOUN}\b(?P<rest>.*)$")
# "generate one more", "make another one on tides" (the rest must start like a topic, so "give me one more example" is a normal question)
_NO_NOUN = re.compile(rf"^{VERB}\b(?: me| us)? (?:one more|another one|a new one|another|one)\b(?P<rest>.*)$")
_REST_OK = re.compile(rf"^\s*(?:$|[,.!?]|please\b|thanks\b|{CONNECTOR}\b)")
# "another video on X", "one more lesson about X"
_NOUN_FIRST = re.compile(rf"^(?:another|one more|next|a new) {NOUN}\b(?P<rest>.*)$")


def _seconds(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?|half|one|two|three|four|five)\s*(?:-\s*)?(minutes?|mins?|min|m)\b", t)
    if m:
        n = NUMBER_WORDS.get(m.group(1)) or float(m.group(1))
        return max(30, min(240, int(round(n * 60 / 5) * 5)))
    m = re.search(r"(\d+)\s*(?:-\s*)?(seconds?|secs?|sec|s)\b", t)
    if m:
        return max(30, min(240, int(round(int(m.group(1)) / 5) * 5)))
    return None


def _topic(rest: str) -> str:
    t = " ".join(rest.split()).strip(" ,.!?;:\"'")
    t = re.sub(r"\b(?:of |that is |that's |which is |in |for |lasting |about |around )?(?:\d+(?:\.\d+)?|half|one|two|three|four|five)\s*-?\s*(?:minutes?|mins?|min|seconds?|secs?|sec)(?: long| each)?\b", " ", t, flags=re.I)
    for _ in range(3):                                   # "that explains", "on", "about" ... in front of the topic
        t = re.sub(rf"^(?:please\s*,?\s*)?(?:that |which )?(?:is |are )?{CONNECTOR}\s+", "", t.strip(" ,"), flags=re.I)
    t = re.sub(r"\s*(?:,?\s*(?:please|for me|now|thanks|thank you))+$", "", t.strip(), flags=re.I)
    t = " ".join(t.split()).strip(" ,.!?;:\"'")
    return t[:120] if len(t) >= 2 else ""


def detect(message: str) -> dict | None:
    """{"topic": str, "duration_s": int | None} when the message asks for another video, else None. An empty topic means "more of this one"."""
    text = " ".join(message.split())
    low = re.sub(OPENER, "", text.lower().strip(), flags=re.I).strip()
    if not low or low.split()[0] in ("how", "what", "why", "when", "where", "who", "which", "is", "are", "does", "did", "was", "can", "could"):
        return None                                      # a question ABOUT videos ("how do I make a video?") goes to the tutor
    m = _WITH_NOUN.match(low) or _NOUN_FIRST.match(low)
    if not m:
        m = _NO_NOUN.match(low)
        if not m or not _REST_OK.match(m.group("rest")):
            return None
    return {"topic": _topic(m.group("rest")), "duration_s": _seconds(text)}


def _reply(topic: str, seconds: int, lang: str) -> str:
    text = (f"Making a {seconds} second video about {topic}. " if topic else f"Making {seconds} more seconds of this topic, from a new angle. ")
    text += "It appears below with a play button as soon as its first scenes are ready, and it is added to the playlist."
    if lang != "en":
        from .translate import translate_batch
        (text,), _ = translate_batch([text], lang, beams=1)
    return text


def handle(lesson_id: str, intent: dict, lang: str = "en", watching: str = "en", message: str = "") -> dict:
    """Add the video to the playlist and start it. Returns the chat reply plus `video` (what the page needs to follow it)."""
    from .chat import detect_text_language
    lesson = load_lesson(lesson_id)
    if lang == "auto":
        lang = detect_text_language(message, prefer=watching) if message else "en"
    pl = playlist.of_lesson(lesson_id)
    wrapped = pl is None
    if pl is None:
        pl = playlist.wrap_lesson(lesson)
    topic = intent["topic"]
    continues = not topic
    seconds = intent.get("duration_s") or pl["duration_s"]
    title = (topic[:1].upper() + topic[1:]) if topic else f"More on {lesson['concept']}"
    try:
        pl, index = playlist.append_episode(pl["id"], title=title, topic=topic or lesson["concept"], duration_s=seconds, continues=continues)
    except ValueError as e:
        return {"reply": str(e), "scene": None, "lang": lang, "translator": "none"}
    job = jobs.submit("lesson", playlist.build_extra, pl["id"], index)
    return {"reply": _reply(topic, seconds, lang), "scene": None, "lang": lang, "translator": "none",
            "video": {"playlist_id": pl["id"], "index": index, "job_id": job["id"], "topic": topic or lesson["concept"], "title": title,
                      "seconds": seconds, "new_playlist": wrapped}}
