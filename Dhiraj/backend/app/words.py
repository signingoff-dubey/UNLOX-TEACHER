"""Word splitting that keeps Indian-language words whole.

Python's \\w and SQLite's unicode61 tokenizer both treat Indic vowel signs and viramas (Unicode Mn/Mc)
as separators, so प्रकाश would split into प, रक, श. These helpers count those marks as part of a word.
"""
from __future__ import annotations

import re
import unicodedata

INDIC_MARKS = "".join(chr(c) for c in range(0x0900, 0x0E00) if unicodedata.category(chr(c)) in ("Mn", "Mc"))
WORD = re.compile(rf"[\w{re.escape(INDIC_MARKS)}]+", re.UNICODE)


def words(text: str) -> list[str]:
    return WORD.findall(text)
