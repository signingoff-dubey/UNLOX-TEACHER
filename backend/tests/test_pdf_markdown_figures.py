import io

import fitz
import pytest
from PIL import Image, ImageDraw

from app import vision
from app.ocr import figures, ingest as I
from app.ocr.markdown import clean, looks_garbled, page_markdown
from app.ocr.triage import classify_page
from app.ocr.types import PageRecord
from app.rag import search as S
from tests.fakes import FakeEmbedder, FakeReranker

E, R = FakeEmbedder(), FakeReranker()
PARA = "Plants make their own food using sunlight, water and carbon dioxide inside the green parts of the leaf."


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(S, "LIBRARY_DIR", tmp_path / "library")
    S.clear_cache()
    yield tmp_path
    assert I.wait_for_upgrades(30), "the background pass did not finish"
    S.clear_cache()


def diagram(side=300, label="Chloroplast") -> bytes:
    im = Image.new("RGB", (side, side), "white")
    ImageDraw.Draw(im).rectangle((20, 20, side - 20, side - 20), outline="green", width=6)
    ImageDraw.Draw(im).text((side // 3, side // 2), label, fill="black")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def make(tmp_path, builder, name="t.pdf"):
    doc = fitz.open()
    builder(doc)
    path = tmp_path / name
    doc.save(path)
    return path


# ------------------------------------------------------------------ Markdown keeps the structure the text layer has
def test_a_digital_page_becomes_markdown_with_headings_and_lists(tmp_path):
    def build(doc):
        p = doc.new_page()
        p.insert_text((72, 90), "Photosynthesis in Plants", fontsize=28, fontname="hebo")
        p.insert_textbox(fitz.Rect(72, 120, 520, 200), PARA, fontsize=11, fontname="helv")
        p.insert_text((72, 230), "What a plant needs", fontsize=18, fontname="hebo")
        for k, b in enumerate(["Sunlight", "Water", "Carbon dioxide"]):
            p.insert_text((90, 258 + 18 * k), "• " + b, fontsize=11, fontname="helv")

    with fitz.open(make(tmp_path, build)) as doc:
        md = page_markdown(doc, 0)
    assert md.startswith("# Photosynthesis in Plants") and "## What a plant needs" in md and "- Sunlight" in md      # the biggest font is #, the next ##
    assert "**Photosynthesis" not in md and PARA.split(",")[0] in md        # no bold clutter in headings, the words are all there


def test_a_ruled_table_becomes_table_rows(tmp_path):
    def build(doc):
        p = doc.new_page()
        rows = [["Stage", "Needs", "Makes"], ["Light reaction", "Light, water", "Oxygen"], ["Calvin cycle", "Carbon dioxide", "Glucose"]]
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                rect = fitz.Rect(72 + c * 150, 120 + r * 30, 72 + (c + 1) * 150, 120 + (r + 1) * 30)
                p.draw_rect(rect, color=(0, 0, 0), width=0.8)
                p.insert_text((rect.x0 + 6, rect.y0 + 20), cell, fontsize=11, fontname="helv")

    with fitz.open(make(tmp_path, build)) as doc:
        md = page_markdown(doc, 0)
        assert classify_page(doc[0]) == "digital"                         # a short page with a real text layer is NOT sent to OCR any more
    assert md.count("|") >= 12 and "Calvin cycle" in md and "Glucose" in md


def test_clean_fixes_ligatures_hyphens_and_invisible_characters():
    assert clean("the ﬁrst ofﬁce, a long exam-\nple­ here​") == "the first office, a long example here"


# ------------------------------------------------------------------ fonts: a broken text layer is caught and sent to OCR
@pytest.mark.parametrize("text, lang, garbled", [
    ("ekWuhVj dksf'kdk, tho ds lcls NksVs ,dd gSa vkSj blh dkj.k budk ukedj.k gqvk gS", None, True),      # legacy Devanagari font: Latin gibberish
    ("(cid:12)(cid:45)(cid:7) (cid:33)(cid:2) some text here and more words", None, True),
    ("    words words words words", None, True),
    ("Plants make food. Don't worry: it's simple, isn't it? They're green and we'll see why.", None, False),
    ("The iPhone and JavaScript are camelCase words, but one or two do not make a page garbled at all.", None, False),
    ("पौधे सूर्य के प्रकाश से अपना भोजन बनाते हैं। इसे प्रकाश संश्लेषण कहते हैं और यह पत्तियों में होता है।", "hi", False),
    ("Plants make their own food using sunlight and water in the leaf, said the teacher to the class.", "hi", True),   # a Hindi document with a Latin text layer
    ("", None, False),
])
def test_broken_text_layers_are_recognised(text, lang, garbled):
    assert looks_garbled(text, lang) is garbled


def test_a_page_with_a_gibberish_text_layer_is_scanned_even_when_it_is_long(tmp_path):
    gib = " ".join(["ekWuhVj dksf'kdk, tho ds lcls NksVs ,dd gSa vkSj blh dkj.k budk"] * 5)

    def build(doc):
        doc.new_page().insert_textbox(fitz.Rect(40, 60, 560, 400), gib, fontsize=11, fontname="helv")

    with fitz.open(make(tmp_path, build)) as doc:
        assert classify_page(doc[0], "hi") == "scanned" and classify_page(doc[0]) == "scanned"


# ------------------------------------------------------------------ pictures inside the PDF
def test_figures_are_found_and_decoration_is_skipped(tmp_path):
    def build(doc):
        p = doc.new_page()
        p.insert_textbox(fitz.Rect(72, 60, 520, 120), PARA, fontsize=11)
        p.insert_image(fitz.Rect(72, 140, 372, 440), stream=diagram())                       # a real figure
        p.insert_image(fitz.Rect(400, 140, 420, 160), stream=diagram(64))                    # an icon
        q = doc.new_page()
        q.insert_image(q.rect, stream=diagram(800))                                         # a page-sized picture = a scan
        for _ in range(3):                                                                   # a logo on every page
            doc.new_page().insert_image(fitz.Rect(10, 10, 110, 110), stream=diagram(200, "Logo"))

    with fitz.open(make(tmp_path, build)) as doc:
        found = figures.find(doc)
        assert [(f["page"], f["w"]) for f in found] == [(1, 300)]
        png = figures.png_of(doc, found[0]["xref"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_figure_captions_are_stored_on_the_page_and_found_by_search(tmp_path):
    def build(doc):
        p = doc.new_page()
        p.insert_textbox(fitz.Rect(72, 60, 520, 120), PARA, fontsize=11)
        p.insert_image(fitz.Rect(72, 140, 372, 440), stream=diagram())

    seen = []

    def fake(png):
        seen.append(len(png))
        return "A box labelled Chloroplast with the arrow Sunlight in and Glucose out."

    info = I.ingest_pdf(make(tmp_path, build), "en", None, lambda s, p: None, unlimited=False, embedder=E, notes=False, describer=fake)
    assert info["figures"] == 1
    assert I.wait_for_upgrades(30), "the background pass did not finish"
    assert len(seen) == 1
    rec = I.load_page(info["sha"], 1)
    assert rec.figures and "Chloroplast" in rec.figures[0]["caption"] and "[Figure on page 1:" in rec.indexed_text()
    hits = S.search("Which box shows Glucose out of the Chloroplast arrow", f"upload:{info['sha']}", embedder=E, reranker=R)
    assert hits and "[Figure on page 1" in hits[0].chunk.text                          # the planner gets the figure's description with the page
    st = I.upload_status(info["sha"])["figures"]
    assert st["found"] == 1 and st["described"] == 1 and st["state"] == "done"


def test_a_missing_vision_model_stops_the_figure_pass_without_breaking_the_upload(tmp_path):
    def build(doc):
        p = doc.new_page()
        p.insert_textbox(fitz.Rect(72, 60, 520, 120), PARA, fontsize=11)
        p.insert_image(fitz.Rect(72, 140, 372, 440), stream=diagram())
        q = doc.new_page()
        q.insert_textbox(fitz.Rect(72, 60, 520, 120), PARA, fontsize=11)
        q.insert_image(fitz.Rect(72, 140, 372, 440), stream=diagram(310, "Other"))

    calls = []

    def missing(png):
        calls.append(1)
        raise vision.VisionUnavailable("llava:7b is not installed")

    info = I.ingest_pdf(make(tmp_path, build), "en", None, lambda s, p: None, unlimited=False, embedder=E, notes=False, describer=missing)
    assert I.wait_for_upgrades(30), "the background pass did not finish"
    assert len(calls) == 1                                                              # it stopped at the first failure, not 40 failures
    assert I.upload_status(info["sha"])["figures"]["state"] == "unavailable"
    assert S.search("sunlight water carbon dioxide", f"upload:{info['sha']}", embedder=E, reranker=R)     # the text is still searchable


def test_old_plain_text_pages_are_redone_as_markdown(tmp_path):
    def build(doc):
        p = doc.new_page()
        p.insert_text((72, 90), "Newton's laws", fontsize=26, fontname="hebo")
        p.insert_textbox(fitz.Rect(72, 120, 520, 220), "The first law is about inertia and objects at rest. " * 3, fontsize=11)

    path = make(tmp_path, build)
    sha = I.file_sha(path)
    I.save_page(sha, PageRecord(1, "digital", "Newton's laws The first law", "text-layer", status="final"))      # fmt 0: an older version's record
    I.ingest_pdf(path, "en", None, lambda s, p: None, unlimited=False, embedder=E, notes=False, describer=False)
    rec = I.load_page(sha, 1)
    assert rec.fmt == I.FORMAT and rec.text.startswith("# Newton's laws")


def test_the_ocr_upgrade_cannot_overwrite_a_figure_caption(tmp_path):
    sha = "abcd1234abcd1234"
    (S.UPLOADS_DIR / sha).mkdir(parents=True)
    I.save_page(sha, PageRecord(1, "scanned", "tess", "tesseract", status="tesseract", tess_text="tess"))
    I.update_page(sha, 1, lambda r: r.figures.append({"xref": 5, "caption": "a diagram"}))          # the figure pass stores a caption
    I.update_page(sha, 1, lambda r: setattr(r, "text", "better OCR text"))                           # the OCR upgrade changes the text afterwards
    rec = I.load_page(sha, 1)
    assert rec.text == "better OCR text" and rec.figures == [{"xref": 5, "caption": "a diagram"}]


# ------------------------------------------------------------------ the vision call itself
def test_describe_figure_asks_llava_once_and_remembers(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "IMAGES_DIR", tmp_path)
    posts = []

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "  A bar chart of rainfall\nby month.  "}}

    monkeypatch.setattr(vision.requests, "post", lambda url, json=None, timeout=0: posts.append(json) or Resp())
    data = diagram()
    assert vision.describe_figure(data) == "A bar chart of rainfall by month."
    assert vision.describe_figure(data) == "A bar chart of rainfall by month." and len(posts) == 1
    assert posts[0]["model"] == vision.VISION_MODEL and posts[0]["messages"][0]["images"]


def test_a_missing_vision_model_is_reported_as_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "IMAGES_DIR", tmp_path)

    class Resp:
        status_code = 404

    monkeypatch.setattr(vision.requests, "post", lambda *a, **k: Resp())
    with pytest.raises(vision.VisionUnavailable):
        vision.describe_figure(diagram())
