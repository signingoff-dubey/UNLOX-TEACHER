"""Is each narration sentence backed by the passages the lesson was built from?

The reranker scores every (sentence, passage) pair; a sentence whose best score is below the
threshold is unsupported, and the planner regenerates that scene once before flagging it.
"""
from __future__ import annotations

THRESHOLD = 0.3


def unsupported(sentences: list[str], passages: list[str], reranker, threshold: float = THRESHOLD) -> list[int]:
    if not sentences:
        return []
    if not passages:
        return list(range(len(sentences)))
    bad = []
    for i, sentence in enumerate(sentences):
        if max(reranker.score(sentence, passages)) < threshold:
            bad.append(i)
    return bad
