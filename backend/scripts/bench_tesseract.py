"""Time the Tesseract pass on a synthetic scanned PDF (dense text pages stored only as pictures, no text layer).

    python scripts/bench_tesseract.py [pages=1000] [workers] [--dpi 200]

Prints pages per second and the projected time for a 1,000-page book. Add --ingest to time the whole upload job
(OCR + chunking + embeddings + index) with the real embedder.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config                                   # noqa: E402
from app.ocr.tesseract import default_workers, ocr_pdf   # noqa: E402

PARA = ("Photosynthesis is the process by which green plants make their own food. Chlorophyll in the leaves absorbs "
        "sunlight, while the roots draw water from the soil and the leaves take in carbon dioxide from the air. Inside "
        "the chloroplasts, light energy is used to split water and to build glucose. Oxygen is released as a by-product, "
        "which is why forests are called the lungs of the Earth. The rate of photosynthesis depends on light intensity, "
        "temperature and the concentration of carbon dioxide, and it stops when the stomata close in extreme heat. ")


def make_scan(path: Path, pages: int, dpi: int) -> None:
    """A distinct dense page is drawn once, photographed (rasterised to JPEG) and repeated with its own page number."""
    base = fitz.open()
    pg = base.new_page()
    pg.insert_textbox(fitz.Rect(54, 54, 541, 790), PARA * 4, fontsize=11, fontname="helv")
    jpeg = pg.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY).tobytes("jpeg", jpg_quality=70)
    out = fitz.open()
    for i in range(pages):
        page = out.new_page()
        page.insert_image(page.rect, stream=jpeg)
    out.save(path, deflate=True)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pages = int(args[0]) if args else 1000
    workers = int(args[1]) if len(args) > 1 else default_workers()
    dpi = int(sys.argv[sys.argv.index("--dpi") + 1]) if "--dpi" in sys.argv else 200
    pdf = config.ROOT / "output" / f"bench_scan_{pages}.pdf"
    pdf.parent.mkdir(exist_ok=True)
    if not pdf.exists():
        t = time.perf_counter()
        make_scan(pdf, pages, dpi)
        print(f"built {pdf.name}: {pdf.stat().st_size / 1e6:.0f} MB in {time.perf_counter() - t:.0f}s")

    if "--ingest" in sys.argv:
        from app.ocr.ingest import ingest_pdf
        t = time.perf_counter()
        last = [0.0]

        def progress(stage: str, frac: float) -> None:
            if time.perf_counter() - last[0] > 10:
                last[0] = time.perf_counter()
                print(f"  {time.perf_counter() - t:5.0f}s  {frac:4.0%}  {stage}", flush=True)

        info = ingest_pdf(pdf, "en", None, progress, unlimited=False)
        secs = time.perf_counter() - t
        print(f"full ingest of {info['pages']} pages: {secs:.0f}s ({info['pages'] / secs:.1f} pages/s)")
        return

    t = time.perf_counter()
    n = chars = bad = 0
    first_error = None
    for _, res in ocr_pdf(str(pdf), list(range(1, pages + 1)), "eng", dpi, workers):
        n += 1
        if isinstance(res, Exception):
            bad += 1
            first_error = first_error or repr(res)
        else:
            chars += len(res.text)
        if n % 100 == 0:
            print(f"  {n} pages  {time.perf_counter() - t:.0f}s", flush=True)
    secs = time.perf_counter() - t
    ok = max(n - bad, 1)
    print(f"{n} pages ({bad} failed), {workers} workers, {dpi} dpi: {secs:.0f}s = {n / secs:.1f} pages/s, "
          f"{chars // ok} chars/page; 1,000 pages would take {1000 / (n / secs):.0f}s")
    if first_error:
        print("first error:", first_error[:200])


if __name__ == "__main__":
    main()
