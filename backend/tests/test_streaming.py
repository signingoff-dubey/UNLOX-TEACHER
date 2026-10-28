import json
import time

from app import pipeline, streaming
from app.streaming import ScenePreview, extract_scenes

PLAN = {"title": "Vaccines", "scenes": [
    {"template": "title", "heading": "Vaccines", "narration": "A vaccine teaches your body to fight a germ.", "icon": "heart"},
    {"template": "flow", "heading": "How it works", "narration": "The vaccine shows a harmless piece. Your body learns it. Then it remembers.",
     "items": ["Harmless piece", "Body learns", "Memory made"]},
    {"template": "bullets", "heading": "Why \"safe\"", "narration": "Vaccines are tested a lot, with { braces } in the text.", "items": ["Tested", "Checked"]},
]}


def test_complete_scenes_are_found_while_the_json_is_still_being_written():
    text = json.dumps(PLAN)
    assert extract_scenes("")[1] == []
    assert extract_scenes('{"title": "Vac')[1] == []
    cut = text.index('"flow"')                                   # in the middle of scene 2
    title, scenes = extract_scenes(text[:cut])
    assert title == "Vaccines" and [s["template"] for s in scenes] == ["title"]
    title, scenes = extract_scenes(text)
    assert [s["heading"] for s in scenes] == ["Vaccines", "How it works", 'Why "safe"']      # quotes and braces inside strings do not confuse it
    assert extract_scenes("```json\n" + text + "\n```")[1] == scenes                          # a markdown fence is fine


def test_text_grows_one_scene_at_a_time():
    text = json.dumps(PLAN)
    counts = [len(extract_scenes(text[:i])[1]) for i in range(0, len(text) + 1, 7)]
    assert counts == sorted(counts) and counts[-1] == 3 and set(counts) == {0, 1, 2, 3}


def test_preview_publishes_each_scene_as_it_is_made(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_translated_scenes", lambda plan, lang: ((plan.title, [s.model_dump() for s in plan.scenes]), "none"))

    def fake_narrate(translated, lang, on_progress=lambda f: None, voice_lang=None):
        title, scenes = translated
        t = 0.0
        for s in scenes:
            s["audio_url"], s["speech_s"], s["duration_s"], s["start_s"], s["captions"] = "/media/audio/x.wav", 2.0, 2.5, t, []
            t += 2.5
        return {"lang": lang, "name": "English", "native": "English", "title": title, "scenes": scenes, "duration_s": t, "tts_engines": ["fake"]}

    monkeypatch.setattr(pipeline, "_narrate", fake_narrate)
    path = tmp_path / "L1" / "lesson.json"
    first = []
    pv = ScenePreview("L1", "Vaccines", "en", ["hi"], ["en", "hi"], 5, path, on_first=lambda: first.append(path.exists()))
    text = json.dumps(PLAN)
    pv.feed(text[:text.index('"flow"')])
    deadline = time.time() + 5
    while time.time() < deadline and not path.exists():
        time.sleep(0.05)
    draft = json.loads(path.read_text(encoding="utf-8"))
    assert draft["building"] is True and draft["scenes_total"] == 5 and first == [True]
    assert [s["template"] for s in draft["languages"]["en"]["scenes"]] == ["title"]
    assert [p["code"] for p in draft["pending"]] == ["hi"]                                # other languages show as still being made

    pv.feed(text)                                                                         # the rest arrives
    deadline = time.time() + 5
    while time.time() < deadline and len(json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]["scenes"]) < 3:
        time.sleep(0.05)
    track = json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]
    assert [s["heading"] for s in track["scenes"]] == ["Vaccines", "How it works", 'Why "safe"']
    assert [s["start_s"] for s in track["scenes"]] == [0.0, 2.5, 5.0] and track["duration_s"] == 7.5      # appended, never overlapping

    pv.close()
    before = path.read_text(encoding="utf-8")
    pv.feed(text + " ")                                                                   # after close nothing more is written
    assert path.read_text(encoding="utf-8") == before


def test_a_retry_of_the_planner_keeps_what_is_on_screen_and_carries_on_after_it(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_translated_scenes", lambda plan, lang: ((plan.title, [s.model_dump() for s in plan.scenes]), "none"))
    monkeypatch.setattr(pipeline, "_narrate", lambda tr, lang, on_progress=None, voice_lang=None: {
        "lang": lang, "name": "English", "native": "English", "title": tr[0], "duration_s": 2.5 * len(tr[1]), "tts_engines": [],
        "scenes": [{**s, "audio_url": "", "speech_s": 2.0, "duration_s": 2.5, "start_s": 2.5 * i, "captions": []} for i, s in enumerate(tr[1])]})
    path = tmp_path / "L2" / "lesson.json"
    pv = ScenePreview("L2", "X", "en", [], ["en"], 4, path)
    pv.feed(json.dumps(PLAN))
    time.sleep(0.6)
    shown = [s["heading"] for s in json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]["scenes"]]
    assert len(shown) == 3
    retry = [{"template": "title", "heading": "Second try", "narration": "Another start."}]
    pv.feed(json.dumps({"title": "Second try", "scenes": retry}))                        # fewer scenes than before: the planner began again
    time.sleep(0.3)
    assert [s["heading"] for s in json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]["scenes"]] == shown     # nothing is taken away from the player
    retry += [{"template": "bullets", "heading": f"Retry {k}", "narration": "More about the idea here.", "items": ["a", "b"]} for k in range(3)]
    pv.feed(json.dumps({"title": "Second try", "scenes": retry}))                        # the retry goes past what was shown: only the new scenes are added
    deadline = time.time() + 5
    want = shown + ["Retry 2"]
    while time.time() < deadline:
        if [s["heading"] for s in json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]["scenes"]] == want:
            break
        time.sleep(0.05)
    assert [s["heading"] for s in json.loads(path.read_text(encoding="utf-8"))["languages"]["en"]["scenes"]] == want
    pv.close()


def test_scenes_already_shown_stay_as_they_were_in_the_final_plan():
    from app.schema import LessonPlan, ScenePlan
    shown = [ScenePlan(template="bullets", heading="Why tides happen", narration="The moon pulls the sea.", items=["Moon", "Pull"])]
    final = LessonPlan(title="Tides", scenes=[
        ScenePlan(template="compare", heading="Why  tides happen", narration="The moon pulls the sea, and the sea bulges toward it on both sides.", items=["Moon", "Pull"]),
        ScenePlan(template="bullets", heading="Spring tides", narration="When sun and moon line up the tides are biggest.", items=["Sun", "Moon"])])
    assert pipeline.keep_shown(final, shown) == 1
    assert final.scenes[0].narration == "The moon pulls the sea." and final.scenes[0].template == "bullets"     # same words, same voice as on screen
    assert final.scenes[1].heading == "Spring tides"                                                            # scenes not shown yet keep the final version
