import threading

import fitz
import pytest

from app.ocr import ingest as I
from app.ocr.types import EngineResult, PageRecord, TocEntry
from app.rag import search as S
from tests.fakes import FakeEmbedder, FakeReranker
from tests.pdfs import make_pdf, set_toc

E, R = FakeEmbedder(), FakeReranker()
TEXT = ("Newton's laws describe motion. The first law is about inertia and objects at rest. "
        "Force equals mass times acceleration according to the second law. ") * 4


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path / "library")
    S.clear_cache()
    yield tmp_path
    I.wait_for_upgrades(10)
    S.clear_cache()


def six_page_pdf(tmp_path):
    return make_pdf(tmp_path, [TEXT, ("image", "Kepler found that planets move in elliptical orbits."), TEXT,
                               ("image", "Chlorophyll absorbs red and blue light."), TEXT,
                               ("image", "Volcanoes erupt when magma rises.")])


class FakeUnlimited:
    def __init__(self):
        self.loaded = False
        self.calls = 0

    def load(self):
        self.loaded = True

    def unload(self):
        self.loaded = False

    def ocr(self, pngs):
        self.calls += 1
        return [EngineResult("unlimited", "Upgraded page text about orbits chlorophyll magma.", None) for _ in pngs]


def ingest(path, **kw):
    stages = []
    info = I.ingest_pdf(path, "en", kw.pop("focus", None), lambda s, p: stages.append(s),
                        unlimited=kw.pop("unlimited", False), embedder=E, notes=kw.pop("notes", False), **kw)
    return info, stages


def test_ingest_indexes_digital_and_scanned_pages(tmp_path):
    info, _ = ingest(six_page_pdf(tmp_path))
    assert (info["pages"], info["digital"], info["scanned"]) == (6, 3, 3)
    hits = S.search("elliptical orbits Kepler", f"upload:{info['sha']}", embedder=E, reranker=R)
    assert hits and hits[0].chunk.page_start <= 2 <= hits[0].chunk.page_end


def test_progress_reports_page_counts(tmp_path):
    _, stages = ingest(six_page_pdf(tmp_path))
    assert any("OCR 3 / 3" in s for s in stages)


def test_upgrade_replaces_section_chunks(tmp_path):
    fake = FakeUnlimited()
    info, _ = ingest(six_page_pdf(tmp_path), unlimited=fake)
    assert I.wait_for_upgrades(20)
    sha = info["sha"]
    rec = I.load_page(sha, 2)
    assert rec.engine == "unlimited" and rec.status == "final" and rec.tess_text
    assert fake.loaded is False                       # unloaded when done
    hits = S.search("Upgraded page text", f"upload:{sha}", embedder=E, reranker=R)
    assert hits
    assert I.upload_status(sha)["unlimited_done"] == 3


def test_resume_uses_cache(tmp_path, monkeypatch):
    path = six_page_pdf(tmp_path)
    ingest(path)
    calls = []
    real = I.ocr_pdf
    monkeypatch.setattr(I, "ocr_pdf", lambda src, pages, *a, **k: calls.append(len(pages)) or real(src, pages, *a, **k))
    ingest(path)
    assert sum(calls) == 0


def test_encrypted_pdf_rejected(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "secret")
    p = tmp_path / "enc.pdf"
    doc.save(p, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    with pytest.raises(I.UploadError, match="password-protected"):
        I.validate_pdf(p)


def test_too_many_pages_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "MAX_PAGES", 5)
    with pytest.raises(I.UploadError, match="more than 5 pages"):
        I.validate_pdf(six_page_pdf(tmp_path))


def test_not_a_pdf_rejected(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"hello")
    with pytest.raises(I.UploadError, match="Not a readable PDF"):
        I.validate_pdf(p)


def test_resolve_focus_variants():
    toc = [TocEntry(1, "Motion", 1), TocEntry(1, "Light and Optics", 4), TocEntry(1, "Sound", 8)]
    assert I.resolve_focus(toc, 10, "pages 2-3") == [2, 3]
    assert I.resolve_focus(toc, 10, "explain page 7") == [7]
    assert I.resolve_focus(toc, 10, "chapter 2") == [4, 5, 6, 7]
    assert I.resolve_focus(toc, 10, "optics") == [4, 5, 6, 7]
    assert I.resolve_focus(toc, 10, "pages 9-40") == [9, 10]
    assert I.resolve_focus(toc, 10, "photosynthesis") == []
    assert I.resolve_focus(toc, 10, None) == []


def test_priority_order():
    assert I.priority_order(6, [1], [4, 5], {2: 30, 3: 90, 6: 50}) == [1, 4, 5, 2, 6, 3]


def test_failed_page_does_not_stop_job(tmp_path, monkeypatch):
    real = I.ocr_pdf

    def flaky(src, pages, *a, **k):
        for p, res in real(src, [q for q in pages if q != 4], *a, **k):
            yield p, res
        if 4 in pages:
            yield 4, RuntimeError("boom")

    def always_fails(png, langs):
        raise RuntimeError("boom again")                      # the lone retry of page 4 fails too

    path = six_page_pdf(tmp_path)
    monkeypatch.setattr(I, "ocr_pdf", flaky)
    monkeypatch.setattr(I, "ocr_image", always_fails)
    info, _ = ingest(path)
    assert I.load_page(info["sha"], 4).status == "failed"
    assert I.load_page(info["sha"], 2).status == "tesseract"
    assert I.upload_status(info["sha"])["failed"] == 1


def test_read_order_puts_the_students_pages_first():
    assert I._read_order([2, 4, 6, 8, 9], focus_pages=[8, 9, 3], front_pages=[2]) == [8, 9, 2, 4, 6]


def test_focus_pages_are_read_first(tmp_path, monkeypatch):
    seen = []
    real = I.ocr_pdf
    monkeypatch.setattr(I, "ocr_pdf", lambda src, pages, *a, **k: seen.append(list(pages)) or real(src, pages, *a, **k))
    path = six_page_pdf(tmp_path)
    set_toc(path, [[1, "Mechanics", 1], [1, "Biology", 4]])
    I.ingest_pdf(path, "en", "chapter 2", lambda s, p: None, unlimited=False, embedder=E, notes=False)
    assert seen[0] == [4, 6, 2]                       # chapter 2 (pages 4-6) before the rest


def test_toc_used_for_sections(tmp_path):
    path = six_page_pdf(tmp_path)
    set_toc(path, [[1, "Mechanics", 1], [1, "Biology", 4]])
    info, _ = ingest(path)
    assert [t["title"] for t in info["toc"]] == ["Mechanics", "Biology"]
    hits = S.search("chlorophyll light", f"upload:{info['sha']}", embedder=E, reranker=R)
    assert hits[0].chunk.section == "Biology"


def test_title_from_original_filename(tmp_path):
    path = six_page_pdf(tmp_path)
    sha = I.file_sha(path)
    I.upload_dir(sha).mkdir(parents=True)
    (I.upload_dir(sha) / "name.txt").write_text("Class 8 Science", encoding="utf-8")
    info, _ = ingest(path)
    assert info["title"] == "Class 8 Science"


def test_title_prefers_real_pdf_metadata(tmp_path):
    path = six_page_pdf(tmp_path)
    for meta, want in [("Biology for Grade 9", "Biology for Grade 9"), ("Microsoft Word - ch1.docx", "doc")]:
        doc = fitz.open(path)
        doc.set_metadata({"title": meta})
        out = tmp_path / f"m{len(meta)}.pdf"
        doc.save(out)
        doc.close()
        info, _ = ingest(out)
        assert info["title"] == (want if want != "doc" else out.stem)


class FakeDigester:
    def __init__(self):
        self.windows = []

    def submit(self, upload_dir, idx, first, last, text):
        self.windows.append((idx, first, last, text))


def test_notes_windows_are_submitted_as_their_pages_are_read(tmp_path):
    fake = FakeDigester()
    info, _ = ingest(six_page_pdf(tmp_path), notes=True, digester=fake)
    assert [w[:3] for w in fake.windows] == [(0, 1, 6)]                  # six pages = one window
    text = fake.windows[0][3]
    assert "[p2]" in text and "Kepler" in text                           # the OCR'd scanned page is in it, not an empty page
    assert I.upload_status(info["sha"])["notes"] == {"total": 1, "done": 0}


def test_upload_limit_is_one_thousand_pages():
    assert I.MAX_PAGES == 1000
