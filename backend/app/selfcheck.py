"""Is the backend ready to make a lesson? One list of checks, each ok / warn / fail with the fix, used by /api/health and logged at start-up.

A lesson that fails after three minutes because the embedding model was never pulled, the disk is full or Node is missing is a bad experience; these are all
known in the first second. A failing check says what to run. Nothing here loads a model or does real work (a few file and HTTP-status checks).
"""
from __future__ import annotations

import importlib.util
import shutil
from dataclasses import asdict, dataclass

import requests

from . import config


@dataclass
class Check:
    name: str
    status: str            # ok | warn | fail
    detail: str
    fix: str = ""


def _ollama() -> list[Check]:
    try:
        models = {m["name"] for m in requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json().get("models", [])}
    except (requests.RequestException, ValueError):
        return [Check("ollama", "fail", f"Ollama does not answer at {config.OLLAMA_URL}", "start it with `ollama serve`")]
    out = [Check("ollama", "ok", f"{len(models)} models installed")]
    if config.LLM_BACKEND != "mock":
        out.append(Check("language model", "ok", config.OLLAMA_MODEL) if config.OLLAMA_MODEL in models else
                   Check("language model", "fail", f"{config.OLLAMA_MODEL} is not installed", f"ollama pull {config.OLLAMA_MODEL}"))
    if config.RAG_ENABLED:
        have = any(m.split(":")[0] == config.EMBED_MODEL.split(":")[0] for m in models)
        out.append(Check("embedding model", "ok", config.EMBED_MODEL) if have else
                   Check("embedding model", "warn", f"{config.EMBED_MODEL} is not installed: lessons have no sources", f"ollama pull {config.EMBED_MODEL}"))
    return out


def run() -> list[Check]:
    checks = _ollama()
    kb_ready = (config.KB_DIR / "embeddings.npy").exists()
    checks.append(Check("knowledge base", "ok", str(config.KB_DIR)) if kb_ready else
                  Check("knowledge base", "warn", "not built: lessons and the fact checker have no sources", "python scripts/build_knowledge.py"))
    free = shutil.disk_usage(config.MEDIA_DIR).free / 1024 ** 3
    checks.append(Check("disk space", "ok" if free >= 5 else "warn" if free >= 1 else "fail", f"{free:.1f} GB free for lessons and videos",
                        "" if free >= 5 else "free some disk space"))
    from . import tts
    checks.append(Check("voices", "ok", "Piper voices found") if any(tts.PIPER_DIR.glob("*.onnx")) else
                  Check("voices", "warn", "no Piper voice found: narration falls back", "python scripts/download_models.py"))
    node = shutil.which(config.NODE_BIN)
    renderer = (config.WEB_DIR / "node_modules" / "@remotion" / "renderer").exists()
    checks.append(Check("video export", "ok", "Node and the renderer are installed") if node and renderer else
                  Check("video export", "warn", "MP4 export is not available (Node or `npm install` in web/ is missing)", "cd web && npm install"))
    checks.append(Check("translation", "ok", config.TRANSLATE_BACKEND) if importlib.util.find_spec("transformers") or config.TRANSLATE_BACKEND in ("none", "ollama")
                  else Check("translation", "warn", "transformers is not installed: only English works", "pip install -r requirements-ml.txt"))
    return checks


def report() -> dict:
    checks = run()
    worst = "fail" if any(c.status == "fail" for c in checks) else "warn" if any(c.status == "warn" for c in checks) else "ok"
    return {"status": worst, "ready": worst != "fail", "checks": [asdict(c) for c in checks]}


def log_report(log) -> None:
    rep = report()
    for c in rep["checks"]:
        if c["status"] != "ok":
            log.warning("self-check %s: %s - %s%s", c["status"], c["name"], c["detail"], f" ({c['fix']})" if c["fix"] else "")
    log.info("self-check: %s (%d checks)", rep["status"], len(rep["checks"]))
