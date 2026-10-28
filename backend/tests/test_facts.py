import pytest

from app import content, facts
from app.knowledge import Passage
from app.schema import LessonPlan, ScenePlan

SRC = Passage("Rainbow", "", "A rainbow is made when light is bent and split inside raindrops. Violet light bends the most and red light bends the least.", "u", "kb", 0.8)
QUOTE = "Violet light bends the most and red light bends the least"


def sc(template="bullets", heading="H", narration="", items=None, **kw):
    return ScenePlan(template=template, heading=heading, narration=narration, items=items or ["a", "b", "c"], **kw)


def plan(*scenes):
    return LessonPlan(title="Rainbows", scenes=list(scenes))


@pytest.mark.parametrize("sentence, expect", [
    ("A rainbow has 7 colors: red, orange, yellow, green, blue, indigo.", "says 7"),
    ("The 3 states of matter are solid, liquid and gas.", None),
    ("There are nine planets in the solar system.", "8 planets"),
    ("Light splits into red, orange, yellow, green, blue and indigo in a rainbow.", "leaves out violet"),
    ("A rainbow shows 7 colors: red, orange, yellow, green, blue, indigo and violet.", None),
    ("The planets in order from the Sun are Mercury, Earth, Venus, Mars.", "from the Sun"),
    ("Earth takes 365 days to go around the Sun.", None),
    ("There are 7 continents on Earth.", None),
    ("There are 6 continents on Earth.", "7 continents"),
    ("It shows how Earth is just one of many planets.", None),                                   # "one of many planets" is not "1 planet"
    ("Earth is one of the eight planets of the solar system.", None),
])
def test_helpers_catch_a_list_that_does_not_match_its_number_or_the_real_list(sentence, expect):
    got = facts.count_issue(sentence) or facts.table_issue(sentence)
    assert (got is None) if expect is None else (got and expect in got)


def test_arithmetic_and_equations_are_checked_by_calculating():
    assert facts.math_issue("So 15 ÷ 3 = 6.")[1] == "So 15 / 3 = 5."[:0] + "So 15 ÷ 3 = 5."
    assert facts.math_issue("Then 2 + 3 × 4 = 14.") is None or "14" in facts.math_issue("Then 2 + 3 × 4 = 14.")[0]
    assert facts.math_issue("12 + 8 = 20") is None
    why, fixed = facts.math_issue("x = 20 ÷ 3", "Solve 3x + 5 = 20. Subtract 5 to get 3x = 15.")
    assert "x = 5" in why and fixed == "x = 5"
    assert facts.math_issue("x = 15 ÷ 3", "Solve 3x + 5 = 20.") is None
    assert facts.solution_of("2x - 4 = 10")[1] == 7.0


def test_only_statements_of_fact_are_checked_and_analogies_are_not():
    p = plan(sc("title", "Hook", "Have you ever seen a rainbow after the rain? Let's find out how it forms in the sky!"),
             sc("bullets", "Light", "Sunlight is made of many colors mixed together. Raindrops bend each color by a different amount, just like a glass prism does.",
                items=["Red bends least and violet bends most", "Rainbow = Colorful Bridge in the sky", "Short"]),
             sc("code", "Code", "This loop prints every number from one to ten on the screen."),
             sc("quiz", "Quiz", "Which color bends the most? Think about it.", items=["Red", "Violet", "Green"], answer_index=1))
    got = [(c.scene, c.kind, c.text) for c in facts.claims_of(p)]
    assert got[:2] == [(1, "narration", "Sunlight is made of many colors mixed together."), (1, "narration", "Raindrops bend each color by a different amount")]   # the analogy is cut off
    assert (1, "item", "Red bends least and violet bends most") in got and not any("Colorful" in t for _, _, t in got) and got[-1][1] == "quiz"
    assert not any(s == 2 for s, _, _ in got)                                                     # code scenes are not fact-checked


class Model:
    """Stands in for the language model: judges by what the statement says."""

    def __init__(self, wrong_if="bends less than red", fix="Violet light bends more than red light.", unsure=False, fake_quote=False, confirms=True):
        self.wrong_if, self.fix, self.unsure, self.fake_quote, self.confirms, self.calls = wrong_if, fix, unsure, fake_quote, confirms, 0

    def __call__(self, prompt, num_predict=450):
        self.calls += 1
        if "SOURCE SENTENCE" in prompt:                                  # the focused question about one quote and one statement
            bad = self.wrong_if in prompt.split("STATEMENT:")[1]
            return {"same_fact": bad and self.confirms, "contradicts": bad and self.confirms}
        lines = [ln for ln in prompt.split("\n") if ln.split(". ", 1)[0].isdigit() and ". " in ln[:5]]
        out = []
        for ln in lines:
            n, text = ln.split(". ", 1)
            bad = self.wrong_if in text
            if "Is each statement true" in prompt:
                out.append({"n": int(n), "true": not bad})
            elif "SOURCE" in prompt:
                v = "contradicted" if bad else ("not_mentioned" if self.unsure else "supported")
                out.append({"n": int(n), "verdict": v, "source": 1, "quote": "nothing like this appears" if self.fake_quote else QUOTE, "fix": self.fix if bad else ""})
            else:
                out.append({"n": int(n), "verdict": "wrong" if bad else ("unsure" if self.unsure else "correct"), "fix": self.fix if bad else ""})
        return {"results": out}


def lesson():
    return plan(
        sc("title", "Rainbows", "Have you ever seen a rainbow after the rain? Let's find out how it forms today."),
        sc("flow", "Bending", "Raindrops split sunlight into colors, and every color leaves the drop at its own angle. Violet light bends less than red light, so violet ends up inside the arc. "
                              "That is why the colors always appear in the same order.", items=["Sunlight enters a drop", "Each color bends differently"]))


def test_a_contradicted_statement_is_replaced_by_a_correction_that_passes_the_check(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", Model())
    p = lesson()
    rep = facts.check_plan(p, "rainbows")
    assert "Violet light bends more than red light." in p.scenes[1].narration and "bends less than red" not in p.scenes[1].narration
    assert rep.fixed and rep.fixed[0]["scene"] == 2 and rep.supported >= 1 and "Rainbow" in rep.sources
    assert rep.scenes[2] == "fixed" and any("corrected" in n for n in rep.notes()) and "Violet light bends the most" in rep.fixed[0]["why"]


def test_a_verdict_without_a_real_quote_changes_nothing(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", Model(fake_quote=True, wrong_if="bends less than red"))
    monkeypatch.setattr(facts, "judge_with_knowledge", lambda claims, topic: None)             # the model's own opinion is a separate layer
    p = lesson()
    before = p.scenes[1].narration
    rep = facts.check_plan(p, "rainbows")
    assert p.scenes[1].narration == before and not rep.fixed and not rep.removed


def test_a_correction_that_fails_the_check_is_not_used_and_the_statement_is_removed(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", Model(fix="Violet light bends less than red light does here."))        # still wrong: not trusted
    monkeypatch.setattr(facts, "rewrite", lambda *a, **k: None)
    p = lesson()
    rep = facts.check_plan(p, "rainbows")
    assert "bends less than red" not in p.scenes[1].narration and rep.removed and not rep.fixed
    only = plan(sc("title", "T", "Hello and welcome to this short lesson about light today."), sc("flow", "Bending", "Violet light bends less than red light, so it ends up inside the arc."))
    rep2 = facts.check_plan(only, "rainbows")
    assert only.scenes[1].narration and rep2.scenes[2] == "unconfirmed"                   # too little left to remove: reported, not hidden


def test_a_correction_with_notes_or_brackets_is_never_accepted():
    old = "Violet light bends less than red light, so it ends up inside."
    assert facts.acceptable(old, "Violet light bends more than red light, so it ends up inside.")
    assert not facts.acceptable(old, "Violet light bends more than red light (Fix: it is the other way round).")
    assert not facts.acceptable(old, old) and not facts.acceptable(old, "No.")


def test_without_a_source_the_model_gives_a_second_opinion_and_unsure_changes_nothing(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    monkeypatch.setattr(facts, "_chat_json", Model())
    p = lesson()
    rep = facts.check_plan(p, "rainbows")
    assert "Violet light bends more than red light." in p.scenes[1].narration and rep.confirmed_by_model >= 1
    unsure = lesson()
    monkeypatch.setattr(facts, "_chat_json", Model(unsure=True, wrong_if="never matches"))
    before = unsure.scenes[1].narration
    rep = facts.check_plan(unsure, "rainbows")
    assert unsure.scenes[1].narration == before and rep.unconfirmed >= 2 and rep.scenes[2] == "unconfirmed"


def test_the_model_alone_cannot_condemn_a_statement_the_opposite_question_accepts(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])

    class Stubborn(Model):
        def __call__(self, prompt, num_predict=450):
            out = super().__call__(prompt, num_predict)
            if "Is each statement true" in prompt:
                for r in out["results"]:
                    r["true"] = True                                  # on the second look it is fine
            return out
    monkeypatch.setattr(facts, "_chat_json", Stubborn())
    p = lesson()
    before = p.scenes[1].narration
    facts.check_plan(p, "rainbows")
    assert p.scenes[1].narration == before


def test_a_calculation_that_does_not_work_out_is_corrected_without_asking_a_model(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    monkeypatch.setattr(facts, "_chat_json", lambda *a, **k: None)                         # no model at all
    p = plan(sc("title", "Equation", "Welcome to a short lesson about solving a simple equation."),
             sc("flow", "Solve", "We start with 3x + 5 = 20 and subtract five from both sides to get 3x = 15.", items=["3x + 5 = 20", "3x = 15", "x = 20 ÷ 3 here"]))
    rep = facts.check_plan(p, "equations")
    assert "x = 20" not in " ".join(p.scenes[1].items) and rep.fixed


def test_a_list_that_does_not_match_its_number_is_rewritten_even_without_a_source(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    good = "A rainbow has 7 colors: red, orange, yellow, green, blue, indigo and violet."
    monkeypatch.setattr(facts, "_chat_json", Model(wrong_if="never matches"))
    monkeypatch.setattr(facts, "rewrite", lambda s, issue, ps: good if "says 7" in issue else None)
    p = plan(sc("title", "T", "Welcome to a short lesson about the rainbow and how it forms."),
             sc("bullets", "Colors", "A rainbow has 7 colors: red, orange, yellow, green, blue, indigo. Each one is bent by a different amount."))
    rep = facts.check_plan(p, "rainbows")
    assert rep.fixed and "says 7" in rep.fixed[0]["why"] and "violet" in p.scenes[1].narration or rep.removed


def test_a_wrong_quiz_answer_is_changed_only_when_a_source_agrees(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", Model(wrong_if="Correct answer: Red", fix=""))
    monkeypatch.setattr(facts, "pick_answer", lambda q, options, ps: 1)
    p = plan(sc("title", "T", "Welcome to a short lesson about the rainbow and how it forms."),
             sc("quiz", "Quiz", "Which color bends the most when it enters a raindrop?", items=["Red", "Violet", "Green"], answer_index=0))
    rep = facts.check_plan(p, "rainbows")
    assert p.scenes[1].answer_index == 1 and rep.fixed[0]["why"] == "quiz answer contradicts the source"
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    q = plan(*[s.model_copy() for s in p.scenes])
    q.scenes[1].answer_index = 0
    facts.check_plan(q, "rainbows")
    assert q.scenes[1].answer_index == 0                                                  # no source: the answer is left alone


def test_the_fact_check_never_stops_a_lesson(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", lambda *a, **k: None)                         # Ollama is down
    p = lesson()
    before = [s.narration for s in p.scenes]
    rep = facts.check_plan(p, "rainbows")
    assert [s.narration for s in p.scenes] == before and rep.unconfirmed >= 1

    def boom(*a, **k):
        raise RuntimeError("index corrupt")
    monkeypatch.setattr(facts, "retrieve", boom)
    assert facts.check_plan(lesson(), "rainbows").partial is True


def test_a_request_with_two_questions_must_be_answered_twice():
    qs = content.sub_questions("how does the rainbow have 7 color,why does it come only when sunlight and rain are together")
    assert len(qs) == 2 and content.sub_questions("how does a refrigerator work") == [] and content.sub_questions("what is a stack and a queue") == []
    only_first = plan(sc("title", "Rainbow colors", "Seven colors appear in a rainbow."), sc("bullets", "Why seven colors", "Each color of light bends by its own amount in the drop."))
    assert "sunlight" in content.unanswered(only_first, qs) or "together" in content.unanswered(only_first, qs)
    both = plan(*only_first.scenes, sc("flow", "Sunlight and rain together", "A rainbow needs sunlight behind you and raindrops in front of you at the same time."))
    assert content.unanswered(both, qs) is None


def test_a_contradiction_the_focused_question_does_not_confirm_changes_nothing(monkeypatch):
    """The batch judge once said a quote about oxygen contradicted 'coal removes impurities'; the focused question must agree before anything changes."""
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [SRC])
    monkeypatch.setattr(facts, "_chat_json", Model(confirms=False))
    monkeypatch.setattr(facts, "judge_with_knowledge", lambda claims, topic: None)
    p = lesson()
    before = p.scenes[1].narration
    rep = facts.check_plan(p, "rainbows")
    assert p.scenes[1].narration == before and not rep.fixed and not rep.removed


def test_a_correction_must_keep_what_the_sentence_taught():
    old = "We dig up iron ore, cook it with coal to remove impurities, and add carbon to strengthen it."
    assert not facts.acceptable(old, "Steel is made in a furnace today with many workers.")                       # throws the sentence away
    assert facts.acceptable(old, "We dig up iron ore, cook it with coal to remove impurities, and add a little carbon to make strong steel.")


def test_a_quiz_without_a_question_is_not_checked():
    p = plan(sc("title", "T", "Welcome to a short lesson about the rainbow and how it forms."),
             sc("quiz", "Quiz", "Red is on the outside of a rainbow, just like crayons. Violet follows closely behind.", items=["Red", "Violet", "Yellow"], answer_index=1))
    assert not [c for c in facts.claims_of(p) if c.kind == "quiz"]


def test_the_equation_can_be_in_an_earlier_scene_than_the_wrong_step(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    monkeypatch.setattr(facts, "_chat_json", lambda *a, **k: None)
    p = plan(sc("title", "Equation", "Welcome to a short lesson about solving a simple equation."),
             sc("bullets", "The problem", "We want to solve the equation 3x + 5 = 20 for the unknown number x."),
             sc("flow", "Steps", "First we subtract five from both sides. This gives us x = 20 ÷ 3 in one step.", items=["Subtract 5", "x = 20 ÷ 3"]))
    rep = facts.check_plan(p, "equations")
    assert "x = 5" in p.scenes[2].narration and "x = 5" in " ".join(p.scenes[2].items) and len(rep.fixed) == 2


def test_the_models_doubt_alone_never_removes_a_scene(monkeypatch):
    monkeypatch.setattr(facts, "retrieve", lambda q, upload=None: [])
    monkeypatch.setattr(facts, "_chat_json", Model(wrong_if="bustling underwater cities", fix=""))
    monkeypatch.setattr(facts, "rewrite", lambda *a, **k: None)
    scenes = [sc("title", "T", "Welcome to a short lesson about coral reefs and the animals that live there.")]
    for h in ("One", "Two", "Three"):
        scenes.append(sc("bullets", h, "Coral reefs are bustling underwater cities.", items=["Coral", "Fish", "Plants"]))
    scenes.append(sc("bullets", "Reefs", "Coral reefs are bustling underwater cities.", items=["Coral", "Fish", "Plants"]))
    p = plan(*scenes)
    n = len(p.scenes)
    facts.check_plan(p, "coral")
    assert len(p.scenes) == n
