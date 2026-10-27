"""Where the OCR engines live, plus settings decided by scripts/bench_ocr.py on this laptop."""
from .. import config

TESSDATA_DIR = config.MODELS_DIR / "tessdata"
UNLIMITED_DIR = config.MODELS_DIR / "Unlimited-OCR"

# Pages per Unlimited-OCR call. 1 unless the benchmark shows infer_multi output splits per page.
UNLIMITED_BATCH = 1
# Lesson languages whose script Unlimited-OCR reads worse than Tesseract (benchmark result).
UNLIMITED_SCRIPTS_DISABLED: set[str] = set()
