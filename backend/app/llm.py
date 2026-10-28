"""Ask the local model for structured data, fast.

Ollama's `format` option (JSON-schema constrained decoding) runs on the CPU and scans Qwen's 152k-token vocabulary for every token it
writes. Measured on this laptop (Qwen2.5-7B Q4, RTX 5060): the same 314-token lesson plan took about 5 s without it and 12-22 s with it.
So nothing here uses `format`. The schema is given to the model as text, the answer is cut out of whatever surrounds it and checked with
pydantic (whose validators in schema.py repair the usual small slips), and one retry sends the error back to the model.
The model still only ever returns data: JSON that matches a schema, never code.
"""
from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Callable, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from . import config

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

def current_model() -> str:
    """The language model for everything that is written or checked (Flash and Pro use the same one: a bigger model does not fit the 8 GB card, see issues.md)."""
    return config.OLLAMA_MODEL


def post(path: str, payload: dict, *, timeout: float, stream: bool = False) -> requests.Response:
    """POST to Ollama, trying again (1 s, then 3 s) when it is busy loading a model, restarting or answering with a server error.
    A request that was refused for a reason of its own (a 4xx) is not repeated."""
    last: Exception | None = None
    for attempt in range(config.LLM_RETRIES + 1):
        try:
            r = requests.post(f"{config.OLLAMA_URL}{path}", json=payload, timeout=timeout, stream=stream)
            if r.status_code >= 500 and attempt < config.LLM_RETRIES:
                last = requests.HTTPError(f"{r.status_code} from Ollama", response=r)
            else:
                return r
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
        if attempt < config.LLM_RETRIES:
            log.warning("Ollama %s failed (%s); trying again", path, last)
            time.sleep(1 + 2 * attempt)
    raise last or requests.RequestException("Ollama did not answer")


RULE = ("Return ONLY one JSON object (no markdown, no commentary before or after it) shaped exactly like this example. "
        "Each value shows the type or the allowed choices (a|b|c); write real values. Use only the fields you need:\n")


def _shape(node: dict, defs: dict):
    if "$ref" in node:
        node = defs[node["$ref"].split("/")[-1]]
    if "enum" in node:
        return "|".join(str(x) for x in node["enum"])
    if "anyOf" in node:
        return _shape(next((n for n in node["anyOf"] if n.get("type") != "null"), {}), defs)
    kind = node.get("type")
    if kind == "object":
        return {k: _shape(v, defs) for k, v in node.get("properties", {}).items()}
    if kind == "array":
        return [_shape(node.get("items", {}), defs)]
    if kind == "string":
        return f"string ({node['description']})" if node.get("description") else "string"
    if kind in ("integer", "number"):
        return 0
    return "boolean" if kind == "boolean" else "any"


@lru_cache(maxsize=64)
def schema_text(cls: type[BaseModel]) -> str:
    """An example-shaped description of the model (field names, types, allowed choices), to put in a prompt.
    Plain JSON examples are followed far more reliably by a 7B model than a raw JSON Schema with $defs and $ref."""
    schema = cls.model_json_schema()
    return json.dumps(_shape(schema, schema.get("$defs", {})), separators=(",", ":"), ensure_ascii=False)


def _without(node, drop: frozenset[str]):
    if isinstance(node, dict):
        return {k: _without(v, drop) for k, v in node.items() if k not in drop}
    if isinstance(node, list):
        return [_without(v, drop) for v in node]
    return node


@lru_cache(maxsize=64)
def slim_schema_text(cls: type[BaseModel], drop: frozenset[str]) -> str:
    """schema_text without some field names (at any depth): every field left out is prompt the model does not have to read."""
    return json.dumps(_without(json.loads(schema_text(cls)), drop), separators=(",", ":"), ensure_ascii=False)


def with_schema(system: str, cls: type[BaseModel], drop: frozenset[str] = frozenset()) -> str:
    shape = slim_schema_text(cls, drop) if drop else schema_text(cls)
    return f"{system}\n\n{RULE}{shape}" if system else f"{RULE}{shape}"


def extract_json(text: str) -> str:
    """The JSON object inside a reply that may carry a markdown fence or a sentence around it."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    return text[a:b + 1] if 0 <= a < b else text


def stream_chat(messages: list[dict], options: dict | None = None, *, timeout: float = 300, expected_tokens: int = 400,
                on_progress: Callable[[float], None] | None = None, on_text: Callable[[str], None] | None = None) -> str:
    """One streamed chat call (no `format`). Progress is tokens so far over what an answer of this kind usually needs."""
    r = post("/api/chat", {
        "model": current_model(), "messages": messages, "stream": True, "think": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": config.ollama_options(options or {}),
    }, timeout=timeout, stream=True)
    r.raise_for_status()
    parts: list[str] = []
    n = 0
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        parts.append(chunk.get("message", {}).get("content", ""))
        n += 1
        if on_progress and n % 5 == 0:
            on_progress(min(n / max(expected_tokens, 1), 0.97))
        if on_text and n % 8 == 0:
            on_text("".join(parts))                      # the text so far, for whoever shows it as it is written
        if chunk.get("done"):
            break
    if on_progress:
        on_progress(1.0)
    if on_text:
        on_text("".join(parts))
    return "".join(parts)


def ask_json(cls: type[T], user: str, system: str = "", options: dict | None = None, *, retries: int = 1, timeout: float = 300,
             expected_tokens: int = 400, on_progress: Callable[[float], None] | None = None,
             on_text: Callable[[str], None] | None = None) -> T:
    """The model's answer as a validated `cls`. Raises ValueError if it still does not fit after `retries` more tries;
    requests.RequestException (Ollama not reachable) is left to the caller. Progress only goes forward: a retry carries on from
    where the bar got to (it does not start again at 0), and 100% is reported only for an answer that fits."""
    opts = {"temperature": 0.4, **(options or {})}
    err = ""
    shown = [0.0]
    base = [0.0]

    def report(f: float) -> None:
        if on_progress is None or f >= 1.0:              # the end of one call is not the end: its answer may still be invalid
            return
        v = base[0] + (0.97 - base[0]) * f
        if v > shown[0]:
            shown[0] = v
            on_progress(v)

    for attempt in range(retries + 1):
        base[0] = shown[0]
        prompt = user + (f"\n\nYour previous answer was not valid ({err}). Answer again with only the JSON object." if err else "")
        text = stream_chat([{"role": "system", "content": with_schema(system, cls)}, {"role": "user", "content": prompt}], opts,
                           timeout=timeout, expected_tokens=expected_tokens, on_progress=report, on_text=on_text)
        try:
            out = cls.model_validate_json(extract_json(text))
            if on_progress:
                on_progress(1.0)
            return out
        except (ValidationError, ValueError) as e:
            err = str(e).replace("\n", " ")[:240]
            log.warning("%s answer attempt %d invalid: %s", cls.__name__, attempt + 1, err)
    raise ValueError(f"The model did not return a valid {cls.__name__}: {err}")
