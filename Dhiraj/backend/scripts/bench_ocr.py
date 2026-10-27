"""Benchmark both OCR engines on this laptop: speed, GPU memory and accuracy.

    python scripts/bench_ocr.py BOOK.pdf --pages 20 --lang hi [--start 10] [--batch 1 4 8] [--no-unlimited]

Accuracy uses digital PDFs as ground truth: each page is rendered to an image (a perfect "scan"),
OCR'd, and compared with the page's own text layer (rapidfuzz ratio on normalised text).
So a Hindi NCERT PDF measures Hindi OCR quality with no hand-made answer key.

Results decide app/ocr/paths.py: UNLIMITED_BATCH and UNLIMITED_SCRIPTS_DISABLED.

Findings, 2026-10-27, RTX 5060 Laptop 8 GB, Windows, torch 2.11 cu128, transformers 4.57.1,
6 pages of NCERT Class 10 Science ch. 6 (Hindi, hesc106.pdf):
  Tesseract (22 procs)       82-91 pages/min   accuracy 77.3
  Unlimited gundam, b=1       2.9 pages/min    accuracy 78.9   peak 8.19 GB (spills past VRAM)
  Unlimited base,   b=1       4.3 pages/min    accuracy 78.8   peak 6.77 GB
  Unlimited base,   b=4       3.8 pages/min    accuracy 78.5   peak 7.21 GB
Decisions: base mode, UNLIMITED_BATCH = 1 (batching is no faster). Hindi is not disabled
(Unlimited is slightly better). At ~4 pages/min, pass 2 needs hours for a 1,000-page scan, so
Tesseract makes it searchable first and pass 2 is opportunistic. WSL2 + vLLM is the follow-up
for speed. infer_multi prints through a TextStreamer: run with PYTHONIOENCODING=utf-8 on Windows.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import fitz
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ocr.ingest import TESS_DPI, UNLIMITED_DPI  # noqa: E402
from app.ocr.tesseract import ocr_many, tess_langs  # noqa: E402
from app.ocr.triage import render_png  # noqa: E402


def norm(s: str) -> str:
    return " ".join(s.replace("#", " ").replace("*", " ").replace("|", " ").split()).lower()


def accuracy(truth: list[str], got: list[str]) -> float:
    return sum(fuzz.ratio(norm(t), norm(g)) for t, g in zip(truth, got)) / max(len(truth), 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", type=int, default=20)
    ap.add_argument("--start", type=int, default=1, help="first page (1-based); skip covers and blank pages")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--batch", type=int, nargs="*", default=[1, 4])
    ap.add_argument("--no-unlimited", action="store_true")
    ap.add_argument("--mode", default="base", choices=["base", "gundam"])
    args = ap.parse_args()

    with fitz.open(args.pdf) as doc:
        nums = [p for p in range(args.start, min(args.start + args.pages, doc.page_count + 1))
                if len(doc[p - 1].get_text().strip()) > 200]
        truth = [doc[p - 1].get_text() for p in nums]
        tess_png = [render_png(doc[p - 1], TESS_DPI) for p in nums]
        uni_png = [render_png(doc[p - 1], UNLIMITED_DPI) for p in nums]
    print(f"{args.pdf.name}: {len(nums)} text pages from page {args.start}, lang={args.lang}")

    t0 = time.perf_counter()
    got = dict(ocr_many(list(enumerate(tess_png)), tess_langs(args.lang)))
    dt = time.perf_counter() - t0
    tess = [got[i].text for i in range(len(nums))]
    print(f"Tesseract      : {len(nums) / dt * 60:6.1f} pages/min   accuracy {accuracy(truth, tess):5.1f}"
          f"   mean conf {sum(got[i].confidence for i in got) / len(got):4.1f}")

    if args.no_unlimited:
        return
    import torch

    from app.ocr.unlimited import UnlimitedOCR
    ocr = UnlimitedOCR(mode=args.mode)
    t0 = time.perf_counter()
    ocr.load()
    print(f"Unlimited load : {time.perf_counter() - t0:5.1f}s, "
          f"{torch.cuda.memory_allocated() / 2**30:.2f} GB allocated")
    ocr.ocr(uni_png[:1])                                  # warm-up
    for b in args.batch:
        torch.cuda.reset_peak_memory_stats()
        texts, t0 = [], time.perf_counter()
        for i in range(0, len(uni_png), b):
            texts += [r.text for r in ocr.ocr(uni_png[i:i + b])]
        dt = time.perf_counter() - t0
        print(f"Unlimited b={b:<2}: {len(nums) / dt * 60:6.1f} pages/min   accuracy {accuracy(truth, texts):5.1f}"
              f"   peak {torch.cuda.max_memory_allocated() / 2**30:.2f} GB")
    ocr.unload()


if __name__ == "__main__":
    main()
