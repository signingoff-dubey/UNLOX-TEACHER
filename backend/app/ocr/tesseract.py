"""OCR pass 1: Tesseract on the CPU, built for speed so a 1,000-page scan is readable in minutes.

What makes it fast:
- every worker process opens the PDF itself and renders its own pages (as grayscale pixels, no PNG round trip), so the
  main process only collects text; nothing waits for a batch to finish;
- one Tesseract per core (OMP_THREAD_LIMIT=1): Tesseract's own OpenMP threads fight each other when many run at once;
- blank pages are skipped without calling Tesseract;
- Latin pages are rendered at a lower DPI than Indic scripts (conjuncts need the extra pixels).
"""
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
LATIN_DPI = int(os.getenv("OCR_DPI_LATIN", "200"))
INDIC_DPI = int(os.getenv("OCR_DPI_INDIC", "300"))
DEFAULT_CONFIG = "--oem 1 --psm 3"      # LSTM engine, automatic page layout (columns, tables)
BLANK_STDDEV = 2.5                     # a page whose pixels barely vary has nothing to read


def tess_langs(lang: str | None) -> str:
    """English is always included: Indic textbooks mix in English terms, numbers and formulas."""
    if not lang or lang == "en":
        return "eng"
    return f"eng+{TESS_CODES[lang]}"


def dpi_for(lang: str | None) -> int:
    return LATIN_DPI if not lang or lang == "en" else INDIC_DPI


def _single_thread_env() -> None:
    """Each worker is one core. Without this, numpy/OpenBLAS (pulled in by pytesseract) reserves buffers for every
    core in every worker, which cost ~600 MB each and exhausted Windows' memory commit at ~10 workers."""
    for var in ("OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"


def _setup() -> None:
    _single_thread_env()
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or WINDOWS_DEFAULT
    # An env var, not --tessdata-dir: pytesseract's argument splitting mangles quoted Windows paths.
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)


def _recognize(img: Image.Image, langs: str) -> EngineResult:
    import pytesseract
    data = pytesseract.image_to_data(img, lang=langs, config=os.getenv("TESS_CONFIG", DEFAULT_CONFIG),
                                     output_type=pytesseract.Output.DICT)
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


def ocr_image(png: bytes, langs: str) -> EngineResult:
    _setup()
    return _recognize(Image.open(io.BytesIO(png)), langs)


# ---------------------------------------------------------------- whole-PDF streaming OCR
_doc = None


def _init_pdf(pdf_path: str) -> None:
    import fitz
    global _doc
    _setup()
    _doc = fitz.open(pdf_path)


def _ocr_pdf_page(page: int, langs: str, dpi: int) -> EngineResult:
    import fitz
    from PIL import ImageStat
    pix = _doc[page - 1].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if ImageStat.Stat(img.resize((pix.width // 8 or 1, pix.height // 8 or 1))).stddev[0] < BLANK_STDDEV:
        return EngineResult("tesseract", "", 100.0)
    return _recognize(img, langs)


WORKER_MB = 160        # measured: ~80 MB Python worker + ~40 MB Tesseract + a rendered page


def default_workers() -> int:
    """One per core, but never more than the free memory can hold: on Windows a full commit limit kills the workers."""
    env = os.getenv("OCR_WORKERS")
    if env:
        return max(1, int(env))
    cores = max(1, (os.cpu_count() or 4) - 2)
    try:
        import psutil
        free_mb = psutil.virtual_memory().available / 2 ** 20
        return max(1, min(cores, int(free_mb * 0.6 // WORKER_MB)))
    except ImportError:
        return min(cores, 8)


def ocr_pdf(pdf: str, pages: list[int], langs: str, dpi: int,
            workers: int | None = None) -> Iterator[tuple[int, EngineResult | Exception]]:
    """OCR `pages` (1-based) of `pdf` in a process pool, yielding (page, result) as each finishes, in roughly the order
    given. A page that fails comes back as its exception instead of stopping the stream."""
    with ProcessPoolExecutor(max_workers=min(workers or default_workers(), max(len(pages), 1)),
                             initializer=_init_pdf, initargs=(str(pdf),)) as pool:
        futures = {pool.submit(_ocr_pdf_page, p, langs, dpi): p for p in pages}
        for fut in as_completed(futures):
            try:
                yield futures[fut], fut.result()
            except Exception as e:  # noqa: BLE001  one bad page (or a crashed worker) must not end the job
                yield futures[fut], e
