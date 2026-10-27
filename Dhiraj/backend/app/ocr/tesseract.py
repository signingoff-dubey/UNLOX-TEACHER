"""OCR pass 1: Tesseract on the CPU. Fast enough to read every scanned page in parallel."""
from __future__ import annotations

import io
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Iterator

from PIL import Image

from .paths import TESSDATA_DIR
from .types import EngineResult

TESS_CODES = {"en": "eng", "hi": "hin", "te": "tel", "ta": "tam", "ml": "mal", "mr": "mar",
              "kn": "kan", "bn": "ben", "gu": "guj"}
WINDOWS_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def tess_langs(lang: str | None) -> str:
    """English is always included: Indic textbooks mix in English terms, numbers and formulas."""
    if not lang or lang == "en":
        return "eng"
    return f"eng+{TESS_CODES[lang]}"


def _setup() -> None:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or WINDOWS_DEFAULT
    # An env var, not --tessdata-dir: pytesseract's argument splitting mangles quoted Windows paths.
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)


def ocr_image(png: bytes, langs: str) -> EngineResult:
    import pytesseract
    _setup()
    data = pytesseract.image_to_data(
        Image.open(io.BytesIO(png)), lang=langs,
        config="--oem 1 --psm 3",
        output_type=pytesseract.Output.DICT,
    )
    # Rebuild lines from the word boxes so paragraphs and line breaks survive.
    lines: dict[tuple, list[str]] = {}
    confs: list[float] = []
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if conf < 0 or not word.strip():
            continue
        confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    text, last_par = [], None
    for (block, par, _), words in lines.items():
        if last_par is not None and (block, par) != last_par:
            text.append("")
        text.append(" ".join(words))
        last_par = (block, par)
    return EngineResult("tesseract", "\n".join(text), sum(confs) / len(confs) if confs else 0.0)


def _ocr_item(item: tuple[int, bytes], langs: str) -> tuple[int, EngineResult]:
    return item[0], ocr_image(item[1], langs)


def default_workers() -> int:
    return max(1, (os.cpu_count() or 4) - 4)


def ocr_many(items: list[tuple[int, bytes]], langs: str, workers: int | None = None
             ) -> Iterator[tuple[int, EngineResult]]:
    """OCR (key, png) pairs in a process pool, yielding (key, result) as each page finishes."""
    with ProcessPoolExecutor(max_workers=workers or default_workers(), initializer=_setup) as pool:
        futures = [pool.submit(_ocr_item, item, langs) for item in items]
        for fut in as_completed(futures):
            yield fut.result()
