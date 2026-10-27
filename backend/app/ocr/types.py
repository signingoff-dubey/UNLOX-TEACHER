"""Records shared by the OCR engines, the arbiter and ingestion."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    tess_text: str = ""            # each engine's own read, kept for re-arbitration and benchmarks
    uni_text: str = ""
    fmt: int = 0                   # 2 = digital text stored as Markdown (older records hold the plain text layer and are redone)
    figures: list = field(default_factory=list)      # [{"xref", "caption"}]: what llava says the page's pictures show

    def indexed_text(self) -> str:
        """The text that is searched and given to the planner: the page, plus what its figures show."""
        caps = [f"[Figure on page {self.page}: {f['caption']}]" for f in self.figures if f.get("caption")]
        if not caps:
            return self.text
        return "\n\n".join([self.text, *caps]).strip()

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "PageRecord":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in known})
