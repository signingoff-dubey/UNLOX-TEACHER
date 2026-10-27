import json

from app.ocr import digest as D


def fake_ask(text, first, last):
    return D.WindowNotes(heading=f"About pages {first}-{last}", points=[f"Point from {text[:12]}"], terms=[D.Term(term="Force", meaning="A push or pull")])


def test_windows_cover_every_page_in_blocks_of_thirty():
    assert D.windows(65) == [(1, 30), (31, 60), (61, 65)]
    assert D.windows(1000)[-1] == (991, 1000) and len(D.windows(1000)) == 34


def test_window_text_samples_every_page():
    pages = {p: f"Page {p} starts here. " + "More sentence about the topic. " * 40 for p in range(1, 31)}
    text = D.window_text(pages, 1, 30)
    assert "[p1]" in text and "[p30]" in text and len(text) < 8500


def test_digester_writes_one_file_per_window_and_skips_done_ones(tmp_path):
    d = D.Digester(ask=fake_ask)
    d.submit(tmp_path, 0, 1, 30, "Newton described force.")
    d.submit(tmp_path, 0, 1, 30, "Newton described force.")               # a repeat is ignored
    d.submit(tmp_path, 1, 31, 60, "Energy is conserved.")
    d.idle()
    notes = D.load_notes(tmp_path)
    assert [n["window"] for n in notes] == [0, 1] and notes[1]["pages"] == [31, 60]
    assert D.progress(tmp_path, 60) == {"total": 2, "done": 2}


def test_a_failed_window_does_not_stop_the_rest(tmp_path):
    def flaky(text, first, last):
        if first == 1:
            raise RuntimeError("model hiccup")
        return fake_ask(text, first, last)

    d = D.Digester(ask=flaky)
    d.submit(tmp_path, 0, 1, 30, "a")
    d.submit(tmp_path, 1, 31, 60, "b")
    d.idle()
    assert [n["window"] for n in D.load_notes(tmp_path)] == [1]


def test_tracker_submits_a_window_when_its_last_scanned_page_arrives(tmp_path):
    sent = []

    class Spy:
        def submit(self, upload_dir, idx, first, last, text):
            sent.append((idx, text))

    pages = {p: f"text {p}" for p in range(1, 61)}
    t = D.WindowTracker(tmp_path, 60, pending={5, 40}, pages=pages, digester=Spy())
    assert sent == []                                                     # both windows wait for a scanned page
    t.page_done(5)
    assert [i for i, _ in sent] == [0]
    t.page_done(40)
    assert [i for i, _ in sent] == [0, 1]


def test_fully_digital_windows_are_submitted_at_once(tmp_path):
    sent = []

    class Spy:
        def submit(self, upload_dir, idx, first, last, text):
            sent.append(idx)

    D.WindowTracker(tmp_path, 70, pending=set(), pages={p: "x" for p in range(1, 71)}, digester=Spy())
    assert sent == [0, 1, 2]


def test_reference_is_in_page_order_and_stays_in_budget(tmp_path):
    d = tmp_path / "notes"
    d.mkdir()
    for i in range(34):
        (d / f"{i}.json").write_text(json.dumps({"window": i, "pages": [i * 30 + 1, i * 30 + 30], "heading": f"Part {i}", "points": ["A fact. " * 30], "terms": []}))
    ref = D.reference(tmp_path, budget=3000)
    assert len(ref) <= 3000 and ref.index("Part 0") < ref.index("Part 33")
