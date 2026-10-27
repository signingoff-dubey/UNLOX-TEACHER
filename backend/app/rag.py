"""Document grounding hook (RAG + OCR).

Students can upload large PDFs (thousands of pages). The document service (ingest, OCR, chunking, vector
search) is built separately; this module is the single seam where it plugs into lesson planning.

Contract for the document service:
    retrieve_context(concept, document_ids) -> str
        Returns the passages most relevant to `concept` from the given uploaded documents, as plain text
        (a few short paragraphs, best first). Return "" when there is nothing to add.

Until the service is connected this returns "" and lessons are planned from the concept alone.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def retrieve_context(concept: str, document_ids: list[str]) -> str:
    if document_ids:
        log.info("Document ids %s received but no document service is connected yet", document_ids)
    return ""
