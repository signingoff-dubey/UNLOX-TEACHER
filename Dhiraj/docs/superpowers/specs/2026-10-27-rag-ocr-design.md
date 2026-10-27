# Offline RAG + Dual-Engine OCR for Visual Teacher — Design

Date: 2026-10-27
Status: approved in conversation, pending written-spec review

## 1. Goal

Ground every generated lesson in real source material, fully offline:

- A student types a concept, optionally uploads a PDF (100 to several thousand pages, digital or scanned).
- The lesson planner retrieves relevant passages (from the uploaded PDF first, then an offline library)
  and builds the lesson only from them. The final video carries knowledge from the PDF and cites pages.
- Works with Wi-Fi off. No external AI APIs. The LLM returns data (JSON), never code.

Non-goals: live internet search at demo time; redistributing copyrighted texts; training any model.

## 2. Hardware budget (this laptop)

RTX 5060 Laptop 8 GB VRAM, 31.5 GB RAM, 24 CPU threads, 189 GB free disk, Windows 11.
Consequence: at most one large GPU model is resident at a time (see §8 GPU scheduler).

Runtime environment: a dedicated Python 3.12 venv (`backend/.venv`), torch built for CUDA 12.8+
(required by Blackwell / RTX 50-series). Python 3.14 is not used.

## 3. Offline library (built once, while online)

Downloaded today by resumable scripts; each source is normalised to JSONL records
`{doc_id, source, title, lang, url, license, text}` and logged in `data/library/manifest.json`
(source, date, count, sha256).

| Source | Acquisition | Est. clean text |
|---|---|---|
| English Wikipedia — Vital Articles Level 5 (~50k) | HF dataset `wikimedia/wikipedia` (en), filter by the Level-5 title list, discard rest | ~2.5 GB |
| Simple English Wikipedia (all) | same dataset, `simple` config | ~0.8 GB |
| Indic Wikipedias: hi, te, ta, ml, mr, kn, bn, gu | same dataset, per-language configs | ~4 GB |
| NCERT textbooks, classes 6–12, English + Hindi | official PDFs, ingested through the same PDF pipeline as uploads (§4) | ~1.5 GB |
| OpenStax (CC-BY) | official PDFs, same PDF pipeline | ~0.5 GB |
| archive.org books, public-domain / CC only | advancedsearch API filtered by `licenseurl` (publicdomain, creativecommons) and subject (science, mathematics, history, technology), items that have a `_djvu.txt` text derivative | capped ~5 GB |

Quality filters: drop documents < 200 words, list/disambiguation pages, pages whose non-letter
ratio > 40%, archive.org items whose dictionary-hit rate < 70% (bad scans).

Licensing: every chunk keeps `license` + `url`. NCERT is copyrighted (free to read); it is indexed
locally for this prototype only and never redistributed.

## 4. PDF ingestion with dual-engine OCR

Applies to student uploads and to NCERT/OpenStax library PDFs.

### 4.1 Page triage (PyMuPDF, ~1 ms/page)

For each page compute: extractable text length, image-area ratio, and font/glyph sanity.

- **digital**: ≥ 200 extractable chars and text is sane → use the text layer directly. No OCR.
- **scanned**: otherwise → OCR (both engines, §4.2).
- Outline: `doc.get_toc()`; if empty, the TOC is recovered after OCR of the first ~15 pages
  (heading detection on OCR markdown).

### 4.2 Two-pass OCR, combined

**Pass 1 — Tesseract (CPU, fast, everything).**
All scanned pages are rendered at 300 DPI and run through Tesseract 5 (LSTM) in a process pool
(`cores − 4` workers), with the language set chosen from the requested lesson language plus English
(e.g. `eng+hin`, `eng+tel`; script auto-detected by Tesseract OSD when unknown). Output per page:
text + mean word confidence. Each page is chunked and indexed as soon as it finishes, so the whole
document becomes searchable within minutes.

**Pass 2 — Unlimited-OCR (GPU, high quality, priority order).**
`baidu/Unlimited-OCR` (3.3B MoE, ~0.6B active, BF16 6.7 GB, MIT) via transformers `infer_multi`,
`image_size=1024`, batches of ~8 pages per call (stays under the 32k-token context), pages rendered
at 200 DPI. Output is cleaned with the model card's `remove_det` post-processing (keeps headings,
markdown tables, LaTeX equations). Priority queue:
1. TOC/front-matter pages;
2. pages in the range relevant to the student's request (from TOC match or explicit page numbers),
   and pages whose Tesseract chunks rank in the top retrieval results for the concept;
3. pages with the lowest Tesseract confidence;
4. everything else, in background, while the GPU is otherwise idle.

**Per-page arbiter (combines the two).** When Unlimited-OCR finishes a page, pick the final text:

- Reject Unlimited-OCR output if it shows a degenerate repetition loop (any 30-token n-gram repeated
  ≥ 3×), or its word count is < 0.5× or > 2× Tesseract's on a page where Tesseract confidence ≥ 80.
- Otherwise compute: script validity (share of characters in the expected Unicode block),
  lexicon hit rate (against the library vocabulary for that language), and character-level agreement
  (normalised edit similarity) between the two outputs.
- Default winner is Unlimited-OCR (better layout, tables, equations). Tesseract wins when Unlimited-OCR
  was rejected, or when its script validity / lexicon hit rate is ≥ 10 points worse than Tesseract's.
- Agreement < 0.6 marks the page `low_confidence`; such pages are down-weighted ×0.8 in retrieval.
- The winning text replaces the page's chunks in the index (delete-by-page, re-insert).
- Every decision is logged in the page record (`engine`, scores) for debugging and the demo.

**Caching.** Per-page results are stored under `data/uploads/<sha256>/pages/<n>.json`
(`{text, engine, tess_conf, agreement, status}`). Re-uploading the same file costs nothing;
an interrupted job resumes from the last finished page.

### 4.3 Limits and failures

- Max 2 GB, 5,000 pages per file. Encrypted/password PDFs are rejected with a clear message.
- Unlimited-OCR CUDA OOM → halve batch, retry; at batch 1 still failing → keep Tesseract text.
- A page failing both engines is marked `failed` and skipped; the job continues.
- Progress is reported through the existing job system: `"OCR 340 / 1,200 pages (Tesseract done,
  Unlimited-OCR 85)"`.

## 5. Chunking

- Structure-aware: split on chapter → section → paragraph (TOC + markdown headings), then pack to
  ~350 tokens with 50-token overlap (token counts from the e5 tokenizer).
- Tables and display equations are atomic; never split.
- Chunk record: `chunk_id, doc_id, title, section_path, page_start, page_end, lang, source, license,
  engine, low_confidence, text`.

## 6. Indexes

Two kinds of collection, same code:

- `library` — the §3 corpus (~6–8 M chunks), built once, read-only.
- `uploads/<sha256>` — one per uploaded PDF, built incrementally during ingestion.

Each collection = SQLite file (chunk table + **FTS5** BM25 index) + **FAISS** index of
**multilingual-e5-small** embeddings (384-d). Library uses IVF-PQ (≈1–2 GB on disk); uploads use a
flat inner-product index (small, exact, supports delete/re-insert by page).

Embedding: library embedded once on GPU (est. 2–3 h). Uploads embedded on CPU (e5-small, 24 threads,
~5k chunks per 1,000 pages ≈ 30 s) so the GPU stays free for OCR.

## 7. Retrieval service

Module `backend/app/rag/search.py` + endpoint `POST /api/search`
`{query, scope: "library" | "upload:<sha>" | "both", k=8}` →
`[{chunk_id, text, title, page_start, page_end, source, score}]`.

1. Query normalisation: if the query is in an Indic language, IndicTrans2 produces an English
   version; both are searched.
2. Candidates: FTS5 top-50 + FAISS top-50 per scope, merged by reciprocal rank fusion (k=60).
3. Rerank with **bge-reranker-v2-m3**; keep top-k.
4. Scope weighting for `both`: upload passages first; library contributes at most 2 passages
   (background / analogy only).
5. Targets: < 400 ms library, < 150 ms single upload (warm).

## 8. Lesson agents

Modes:
- **Concept + PDF** → search within the upload (scope `both`).
- **Chapter / page range** ("explain chapter 4", "pages 120–135") → resolve the range via TOC, take
  its chunks in reading order; if longer than the planner budget, map-reduce: Qwen condenses each
  section into short notes, then plans from the notes.
- **PDF only** → topic = the dominant chapter in the TOC; overview lesson.
- **Concept only** → scope `library`.

Pipeline:
1. **Retriever** (§7) → passages labelled [P1]…[P8].
2. **Planner** (Qwen2.5-7B via Ollama, JSON schema): instructed to teach only what the passages
   support; `ScenePlan` gains `sources: list[str]` (passage labels).
3. **Fact-check**: each narration sentence is scored against its cited passages with the reranker;
   score below threshold → regenerate that scene once, then flag it.
4. Existing pipeline unchanged: translate → narration first → scene timing → visuals → MP4.
5. Summary scene shows a source line (e.g. "From: Biology Class 11, pp. 214–219"); the player lists
   all sources with page numbers.
6. If no passage clears the relevance threshold, the lesson says the PDF does not cover the concept
   and falls back to the library; it never invents content to fill the gap.

GPU scheduler (`backend/app/gpu.py`): a single lock that owns "the big slot". Unlimited-OCR (6.7 GB)
and Qwen (4.7 GB, Ollama `keep_alive=0`) never overlap; OCR pass 2 yields the GPU whenever a lesson
needs planning, then resumes. The reranker (~1.1 GB fp16) and TTS share the GPU otherwise.

## 9. Code layout

```
backend/app/
  gpu.py                 # big-slot GPU scheduler
  rag/
    __init__.py
    chunker.py           # structure-aware chunking
    store.py             # SQLite+FTS5 and FAISS collection
    embed.py             # e5-small (CPU/GPU) wrapper
    rerank.py            # bge-reranker-v2-m3 wrapper
    search.py            # hybrid search + RRF + scope weighting
  ocr/
    __init__.py
    triage.py            # digital vs scanned page detection, TOC
    tesseract.py         # pass 1 (process pool)
    unlimited.py         # pass 2 (Unlimited-OCR)
    arbiter.py           # per-page combination
    ingest.py            # orchestration, caching, progress, incremental indexing
backend/scripts/
  bench_ocr.py           # throughput + quality benchmark (plan step 1)
  fetch_library.py       # §3 downloads
  build_library.py       # chunk + embed + index the library
backend/tests/           # pytest
data/                    # gitignored: library/, uploads/, models/
```

## 10. Testing

- Unit: triage thresholds, chunk boundaries (tables/equations atomic), arbiter decisions on
  crafted inputs (repetition loop, wrong script, agreement), RRF merge, scope weighting.
- Integration: ingest a 20-page mixed PDF (digital + scanned) end to end; search returns the
  expected page.
- Retrieval benchmark: 50 question → expected-page pairs across an English NCERT book, a Hindi
  NCERT book and a scanned archive.org book; report recall@8 per engine (Tesseract-only,
  Unlimited-only, combined).
- Benchmark first: pages/min for each OCR engine on this laptop and character accuracy on
  Hindi/Telugu pages. Decision gates: if Unlimited-OCR < 4 pages/min under Windows transformers,
  evaluate WSL2 + vLLM; if its Indic accuracy is below Tesseract's, the arbiter prefers Tesseract for
  that script.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Unlimited-OCR too slow on Windows | Tesseract pass makes every page searchable anyway; priority queue OCRs relevant pages first; WSL2 + vLLM option |
| Unlimited-OCR custom code incompatible with the 5060/torch build | pin versions from the model card; Tesseract-only mode still meets the requirement |
| 8 GB VRAM contention | single big-slot scheduler; CPU embeddings for uploads |
| Library build time | run overnight; Simple-English + NCERT subset is buildable in hours as a fallback |
| Copyright | only PD/CC archive.org items; NCERT local-only; licences stored per chunk |
