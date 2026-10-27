"""Records shared by the OCR engines, the arbiter and ingestion."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

PageKind = Literal["digital", "scanned"]
PageStatus = Literal["pending", "tesseract", "final", "failed"]


@dataclass
class EngineResult:
    engine: str                    # "tesseract" | "unlimited" | "text-layer"
    text: str
    confidence: float | None       # Tesseract mean word confidence, 0-100; None for Unlimited-OCR


@dataclass(frozen=True)
class TocEntry:
    level: int
    title: str
    page: int                      # 1-based


@dataclass
class PageRecord:
    page: int                      # 1-based
    kind: PageKind
    text: str = ""
    engine: str = ""
    tess_conf: float | None = None
    agreement: float | None = None
    low_confidence: bool = False
    status: PageStatus = "pending"

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "PageRecord":
        return cls(**data)
