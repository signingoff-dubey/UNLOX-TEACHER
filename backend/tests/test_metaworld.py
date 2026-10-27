import pytest
from fastapi.testclient import TestClient

from app import config, metaworld
from app.metaworld import MQuestion, MStation, MWorld


def q(text="Which gas do plants take in?", options=("O2", "CO2", "N2", "H2"), idx=1):
    return MQuestion(question=text, options=list(options), answer_index=idx, hint="Think of breathing.", why="Plants use CO2.")


BODY = "Plants take in carbon dioxide and water, and the leaf turns them into sugar."


def test_clean_keeps_playable_stations_and_puts_the_right_answer_first():
    doc = MWorld(title="Photosynthesis", stations=[
        MStation(name="Inputs", title="What goes in", body=BODY, terms=["CO2"], questions=[q(), q("Bad: only three options?", ("a", "b", "c"), 0), q("Out of range answer here?", ("a", "b", "c", "d"), 9)]),
        MStation(name="Empty", title="No questions", body=BODY),                                  # dropped: nothing to ask
        MStation(name="Short", title="Too short", body="Too short.", questions=[q()]),            # dropped: nothing to read
        MStation(name="Outputs", title="What comes out", body=BODY, questions=[q("Which gas do leaves release?", ("O2", "CO2", "N2", "H2"), 0)]),
    ], finale="You know it.")
    w = metaworld.clean(doc, "photosynthesis")
    assert [z["name"] for z in w["zones"]] == ["Inputs", "Outputs"] and [z["color"] for z in w["zones"]] == metaworld.COLORS[:2]
    z = w["zones"][0]
    assert z["quiz"]["options"][0] == "CO2" and z["quiz"]["answer"] == 0 and z["more"] == []        # the one valid question
    assert w["finale"]["body"] == "You know it." and w["match"] == "photosynthesis"


def test_clean_refuses_a_world_with_fewer_than_two_stations():
    with pytest.raises(ValueError):
        metaworld.clean(MWorld(stations=[MStation(name="A", body=BODY, questions=[q()])]), "x")


def test_build_with_the_mock_model_makes_four_stations(monkeypatch):
    monkeypatch.setattr(config, "LLM_BACKEND", "mock")
    seen = []
    out = metaworld.build("  The   solar system ", progress=lambda s, p: seen.append(p))
    assert len(out["world"]["zones"]) == 4 and out["stats"]["questions"] == 4 and seen[-1] == 1.0
    with pytest.raises(ValueError):
        metaworld.build(" ")


def test_wardrobe_save_keeps_the_newer_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(metaworld, "SAVE_FILE", tmp_path / "save.json")
    assert metaworld.load_save() is None
    a = metaworld.store_save(metaworld.MetaSave(wallet=30, life=120, owned=["ride_skate", "hat_cap"], look={"ride": "skate", "hat": None}, rev=4))
    assert a["wallet"] == 30 and metaworld.load_save()["owned"] == ["ride_skate", "hat_cap"]
    stale = metaworld.store_save(metaworld.MetaSave(wallet=999, rev=2))                           # an old tab must not undo the purchase
    assert stale["wallet"] == 30 and metaworld.load_save()["rev"] == 4


def test_endpoints(monkeypatch, tmp_path):
    from app.main import app
    monkeypatch.setattr(metaworld, "SAVE_FILE", tmp_path / "save.json")
    c = TestClient(app)
    assert c.get("/api/metaverse/save").json() == {}
    assert c.post("/api/metaverse/save", json={"wallet": 5, "life": 9, "owned": ["a"], "look": {"hat": "cap"}, "rev": 1}).json()["wallet"] == 5
    assert c.get("/api/metaverse/save").json()["look"] == {"hat": "cap"}
    assert c.post("/api/metaverse/save", json={"wallet": -1}).status_code == 422
    assert c.post("/api/metaworld", json={"topic": "x", "lang": "en"}).status_code == 422
    assert c.post("/api/metaworld", json={"topic": "Gravity", "lang": "xx"}).status_code == 400
