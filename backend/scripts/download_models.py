"""Fetch everything the app needs while you still have internet. Afterwards it runs fully offline.

    python scripts/download_models.py            # Piper voices + fonts (small, ~400 MB)
    python scripts/download_models.py --ml       # also IndicTrans2 + Indic Parler-TTS (~5 GB)
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402
from app.languages import LANGUAGES  # noqa: E402

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
FONT_BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {  # saved name -> path in google/fonts
    "NotoSans.ttf": "notosans/NotoSans%5Bwdth,wght%5D.ttf",
    "NotoSansDevanagari.ttf": "notosansdevanagari/NotoSansDevanagari%5Bwdth,wght%5D.ttf",
    "NotoSansTelugu.ttf": "notosanstelugu/NotoSansTelugu%5Bwdth,wght%5D.ttf",
    "NotoSansKannada.ttf": "notosanskannada/NotoSansKannada%5Bwdth,wght%5D.ttf",
    "NotoSansTamil.ttf": "notosanstamil/NotoSansTamil%5Bwdth,wght%5D.ttf",
    "NotoSansMalayalam.ttf": "notosansmalayalam/NotoSansMalayalam%5Bwdth,wght%5D.ttf",
    "NotoSansBengali.ttf": "notosansbengali/NotoSansBengali%5Bwdth,wght%5D.ttf",
    "NotoSansGujarati.ttf": "notosansgujarati/NotoSansGujarati%5Bwdth,wght%5D.ttf",
}


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ok      {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetch   {dest.name}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml", action="store_true", help="also download IndicTrans2 and Indic Parler-TTS")
    args = ap.parse_args()

    print("Piper voices ->", config.MODELS_DIR / "piper")
    for lang in LANGUAGES.values():
        if lang.piper_voice:
            name = Path(lang.piper_voice).name
            for ext in (".onnx", ".onnx.json"):
                fetch(PIPER_BASE + lang.piper_voice + ext, config.MODELS_DIR / "piper" / (name + ext))

    print("Fonts ->", config.FONTS_DIR)
    for name, path in FONTS.items():
        fetch(FONT_BASE + path, config.FONTS_DIR / name)

    if args.ml:
        from huggingface_hub import snapshot_download
        print("Hugging Face ->", config.NLLB_MODEL)
        snapshot_download(config.NLLB_MODEL)          # weights are pytorch_model.bin, ~2.5 GB
        if config.TRANSLATE_BACKEND == "indictrans2":
            print("Hugging Face ->", config.INDICTRANS2_MODEL, "(gated: needs huggingface-cli login)")
            snapshot_download(config.INDICTRANS2_MODEL)
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
        except ImportError:
            print("parler-tts not installed; skipping Indic Parler-TTS")
        else:
            snapshot_download(config.PARLER_MODEL)
            # Parler's description encoder is a separate model; load once to cache it.
            model = ParlerTTSForConditionalGeneration.from_pretrained(config.PARLER_MODEL)
            snapshot_download(model.config.text_encoder._name_or_path)
    print("Done. You can now go offline.")


if __name__ == "__main__":
    main()
