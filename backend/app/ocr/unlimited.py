"""OCR pass 2: baidu/Unlimited-OCR on the GPU (3.3B MoE, ~0.6B active, BF16, 6.7 GB).

Better than Tesseract at layout, tables and equations, but it needs nearly the whole 8 GB card, so it
runs under gpu.big_slot and is unloaded whenever a lesson needs the LLM.

Model facts (read from modeling_unlimitedocr.py):
- infer(..., eval_mode=True) returns the decoded text of one image.
- infer_multi(...) returns (text, n_tokens); pages are separated by "<PAGE>" markers.
- Raw output wraps blocks in <|det|>type [bbox]<|/det|> markers; remove_det() turns it into text.
"""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from .paths import UNLIMITED_DIR
from .types import EngineResult

log = logging.getLogger(__name__)

DET_RE = re.compile(r'<\|det\|>([^<\s]+)(?:\s*\[[^\]]*\])?\s*<\|/det\|>(.*)', re.DOTALL)


class OcrOOM(RuntimeError):
    """CUDA ran out of memory; the caller should retry with a smaller batch."""


def remove_det(raw: str) -> str:
    """Strip <|det|>type [bbox]<|/det|> markers, group lines belonging to the
    same block with \\n, and separate different blocks with \\n\\n.
    (Verbatim from the Unlimited-OCR model card's post-processing.)"""
    blocks = []
    cur = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = DET_RE.match(line)
        if m:
            category, content = m.group(1).strip(), m.group(2).strip()
            if category == 'image':
                continue
            if cur is not None:
                blocks.append(cur)
            cur = [content] if content else []
            continue
        if cur is None:
            cur = []
        cur.append(line)
    if cur is not None:
        blocks.append(cur)
    text = '\n\n'.join('\n'.join(b) for b in blocks).strip()
    return text


def split_pages(raw: str, n: int) -> list[str] | None:
    """Split infer_multi output into n pages, or None if the markers don't match the page count."""
    parts = [p.strip() for p in raw.split("<PAGE>")[1:]]
    return parts if len(parts) == n else None


class UnlimitedOCR:
    def __init__(self, model_dir: Path = UNLIMITED_DIR, mode: str = "base") -> None:
        # "base": one 1024px view (fewer image tokens, fits 8 GB); "gundam": 640px crops + global view.
        self.model_dir = model_dir
        self.mode = mode
        self.model = None
        self.tokenizer = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        if self.loaded:
            return
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            self.model_dir, trust_remote_code=True, use_safetensors=True, torch_dtype=torch.bfloat16,
        ).eval().cuda()

    def unload(self) -> None:
        if not self.loaded:
            return
        import gc

        import torch
        self.model = None
        self.tokenizer = None
        gc.collect()
        torch.cuda.empty_cache()

    def ocr(self, pngs: list[bytes]) -> list[EngineResult]:
        import torch
        self.load()
        with tempfile.TemporaryDirectory(prefix="uocr_") as tmp:
            paths = []
            for i, png in enumerate(pngs):
                p = Path(tmp) / f"page_{i:04d}.png"
                p.write_bytes(png)
                paths.append(str(p))
            try:
                texts = self._multi(paths, tmp) if len(paths) > 1 else None
                if texts is None:
                    texts = [self._single(p, tmp) for p in paths]
            except torch.cuda.OutOfMemoryError as e:
                torch.cuda.empty_cache()
                raise OcrOOM(str(e)) from e
        return [EngineResult("unlimited", remove_det(t), None) for t in texts]

    def _single(self, path: str, out_dir: str) -> str:
        return self.model.infer(
            self.tokenizer, prompt="<image>document parsing.", image_file=path, output_path=out_dir,
            base_size=1024, image_size=640 if self.mode == "gundam" else 1024,
            crop_mode=self.mode == "gundam", max_length=8192,
            no_repeat_ngram_size=35, ngram_window=128, eval_mode=True,
        )

    def _multi(self, paths: list[str], out_dir: str) -> list[str] | None:
        raw, _ = self.model.infer_multi(
            self.tokenizer, prompt="<image>Multi page parsing.", image_files=paths, output_path=out_dir,
            image_size=1024, max_length=32768, no_repeat_ngram_size=35, ngram_window=1024,
        )
        pages = split_pages(raw, len(paths))
        if pages is None:
            log.warning("Unlimited-OCR returned no per-page markers for %d pages; redoing one by one", len(paths))
        return pages
