import pytest

from app import content, director, planner, playlist, schema, vision
from app.schema import LessonPlan, ScenePlan


def sc(template="bullets", heading="H", narration="A full sentence that explains the idea in enough detail, with a specific example and a reason, so that the student learns something new today.", items=None, code=None, **kw):
    return ScenePlan(template=template, heading=heading, narration=narration, items=items or ["a", "b", "c"], code=code or [], code_lang="java" if code else "", **kw)


LOOP = ["int[] a = {5, 3, 8, 4, 2};", "for (int i = 0; i < a.length - 1; i++) {", "  for (int j = 0; j < a.length - 1 - i; j++) {", "    if (a[j] > a[j + 1]) { int t = a[j]; a[j] = a[j + 1]; a[j + 1] = t; }"]
MAIN = ["public class Main {", "  public static void main(String[] args) {", '    System.out.println("Data Structures and Algorithms are essential");', "  }", "}"]


# ------------------------------------------------------------------ each part of a long video has its role
def part(scenes):
    return LessonPlan(title="T", scenes=scenes)


def test_only_the_first_part_has_a_title_and_only_the_last_a_quiz_and_summary():
    first = part([sc("title", "Hook"), sc("flow", "Steps"), sc("bullets", "Idea"), sc("summary", "Summary"), sc("quiz", "Q")])
    content.clean_part(first, 1, 3)
    assert [s.template for s in first.scenes] == ["title", "flow", "bullets"]                       # summary and quiz belong to the end
    middle = part([sc("title", "Again"), sc("code", "Code", code=LOOP), sc("bullets", "Idea"), sc("summary", "Summary")])
    content.clean_part(middle, 2, 3)
    assert [s.template for s in middle.scenes] == ["code", "bullets"]                               # no title card in the middle, no summary yet
    last = part([sc("title", "Again"), sc("flow", "Steps"), sc("summary", "Sum"), sc("quiz", "Q"), sc("summary", "Summary 2")])
    content.clean_part(last, 3, 3)
    assert [s.template for s in last.scenes] == ["flow", "summary", "quiz"] or last.scenes[-1].template in ("summary", "quiz")
    assert not any(s.template == "title" for s in last.scenes)
    tiny = part([sc("title", "A"), sc("summary", "B")])
    content.clean_part(tiny, 2, 3)
    assert len(tiny.scenes) == 2                                                                    # never emptied


def test_a_segment_gets_no_title_card_of_its_own_and_only_the_last_gets_misconceptions():
    body = [sc("flow", "Steps"), sc("bullets", "Idea"), sc("diagram", "Parts"), sc("bullets", "More")]
    mid = schema.normalize(LessonPlan(title="Video", scenes=[s.model_copy() for s in body]), segment=True, last=False)
    assert mid.scenes[0].template != "title" and not any("Let's learn about" in s.narration for s in mid.scenes)
    whole = schema.normalize(LessonPlan(title="Video", scenes=[s.model_copy() for s in body]))
    assert whole.scenes[0].template == "title"                                                      # a single video still opens with one
    plan = LessonPlan(title="Video", scenes=[s.model_copy() for s in body], common_mistakes=[{"wrong": "x is y", "right": "x is z"}])
    assert not any(s.heading == "Common mistakes" for s in schema.normalize(plan.model_copy(deep=True), segment=True, last=False).scenes)
    assert any(s.heading == "Common mistakes" for s in schema.normalize(plan.model_copy(deep=True), segment=True, last=True).scenes)


# ------------------------------------------------------------------ the joined plan, as a viewer sees it (the real DSA lesson had all of these)
def dsa_plan():
    return LessonPlan(title="Basics of DSA in Java", scenes=[
        sc("title", "What is DSA?", "Let's learn about What is DSA?."),
        sc("flow", "Problem solving steps"),
        sc("summary", "Summary", "DSA helps computers solve problems faster and better, and next we will look at arrays."),
        sc("title", "Basics of DSA in Java", "Let's learn about ."),
        sc("code", "Array Example", "We can make an array to store our favourite numbers, so let us see how this works in Java.", code=["int[] myNumbers = {1, 2, 3, 4, 5};", "System.out.println(myNumbers[0]);"]),
        sc("code", "Basics of DSA in Java", "Print the class.", code=MAIN),
        sc("code", "Bubble Sort Code", "Here is a simple bubble sort that compares neighbours and swaps them when they are out of order.", code=LOOP),
        sc("code", "Bubble Sort Code", "Here is the code to sort our list, and we go through each line together.", code=LOOP),
        sc("compare", "Common mistakes", "A common mistake: many people think bubble sort is the fastest algorithm, but it is not at all."),
        sc("summary", "Summary", "Bubble sort is a simple way to organise things by comparing and swapping neighbours until all is in order."),
        sc("compare", "Common mistakes", "A common mistake: many people think bubble sort is the fastest algorithm for large lists, but it is slow."),
        sc("summary", "Summary", "We sorted the numbers using bubble sort, which is like comparing pairs of friends and putting them in order."),
    ])


def test_repeated_headings_code_summaries_and_placeholders_are_removed():
    plan = dsa_plan()
    notes = content.dedupe_plan(plan)
    heads = [s.heading for s in plan.scenes]
    assert plan.scenes[0].heading == "What is DSA?"                                                  # the opening scene stays
    assert heads.count("Summary") == 1 and plan.scenes[-1].template == "summary"                    # one summary, at the end
    assert heads.count("Common mistakes") == 1 and heads.count("Bubble Sort Code") == 1             # the same heading with the same content: once
    assert not any(content.is_placeholder(s) for s in plan.scenes[1:])                               # "Let's learn about ." is gone
    assert content.repeated_code(plan) is None and content.repeated_headings(plan) is None
    assert len(notes) >= 5 and len(plan.scenes) >= 3


def test_problems_are_named_so_the_planner_can_retry():
    bad = dsa_plan()
    assert "same code" in content.repeated_code(bad)
    assert "used twice" in content.repeated_headings(bad)
    assert content.narration_problems(bad)                                                           # the 3-word captions
    issue = planner.quality_issue(LessonPlan(title="x", scenes=[sc("title", "A"), sc("flow", "B", "Too short.", items=["1", "2"]), sc("bullets", "C", "Also short.", items=["3", "4"]), sc("diagram", "D", "Short again.", items=["5", "6"])]))
    assert issue and "too short" in issue
    assert planner.quality_issue(LessonPlan(title="x", scenes=[sc("title", "A"), sc("flow", "B", items=["1", "2"]), sc("bullets", "C", items=["3", "4"]), sc("diagram", "D", items=["5", "6"])])) is None


def test_the_class_skeleton_is_flagged_when_it_is_repeated():
    plan = LessonPlan(title="x", scenes=[sc("title", "A"), sc("code", "One", code=MAIN + ["int a = 1;"]), sc("code", "Two", code=MAIN + ["int b = 2;", "int c = 3;"])])
    assert content.repeated_code(plan)


def test_what_a_part_taught_is_summarised_for_the_next_one():
    text = content.taught_summary(dsa_plan())
    assert "Array Example" in text and "myNumbers" in text and "Bubble Sort Code" in text
    assert "What is DSA" not in text and "Summary" not in text and "public class" not in text      # no title, summary or boilerplate, only what was taught
    assert len(text) <= 900


# ------------------------------------------------------------------ the photo: a looping reading is cut, an episode sees only its part
def test_a_runaway_photo_reading_is_cut_to_something_a_photo_can_hold():
    topics = ["Data structures", "Arrays", "Linked lists", "Stacks", "Queues", "Trees", "Hash tables", "Graphs"]
    looping = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(topics)) + "\n" + "\n".join(f"{i + 9}. Data {w}" for i, w in enumerate(["archiving", "backup", "compression"] * 30)) + "\nTopic: DSA in Java"
    cleaned = vision.clean_description(looping)
    assert cleaned.count("\n") <= 15 and "Topic: DSA in Java" in cleaned and len(cleaned) < 950
    assert "Data archiving" in cleaned and cleaned.count("Data archiving") == 1                     # repeats dropped
    assert vision.clean_description("1. Arrays\n2. Arrays\n3. Stacks") == "1. Arrays\n3. Stacks"


def test_an_episode_gets_only_the_lines_of_the_photo_that_are_about_it():
    photo = "1. Data structures\n2. Arrays\n3. Linked lists\n4. Stacks\n5. Queues\n6. Cryptography\nTopic: DSA"
    assert vision.relevant(photo, "Stacks and queues: LIFO and FIFO") == "4. Stacks\n5. Queues"
    assert vision.relevant(photo, "Understanding arrays and linked lists") == "2. Arrays\n3. Linked lists"
    assert vision.relevant(photo, "Dynamic programming") == ""                                      # nothing about it: that video does not mention the photo


# ------------------------------------------------------------------ the director removes an empty title card instead of making it a code scene
def test_an_empty_title_card_in_the_middle_is_removed(monkeypatch):
    monkeypatch.setattr(director.config, "LLM_BACKEND", "ollama")
    monkeypatch.setattr(director, "_ask", lambda *a, **k: None)
    plan = LessonPlan(title="T", scenes=[sc("title", "Hook", "Why do programs need data structures at all? Let us find out together."), sc("flow", "Steps"),
                                         sc("title", "Basics", "Let's learn about ."), sc("diagram", "Parts"), sc("bullets", "More")])
    plan, notes = director.direct(plan, "DSA in Java")
    assert [s.heading for s in plan.scenes][:2] == ["Hook", "Steps"] and "Basics" not in [s.heading for s in plan.scenes]
    assert any("removed" in n for n in notes)


# ------------------------------------------------------------------ a course: 3 videos at most, each told what the earlier ones taught
def test_a_course_is_at_most_three_videos_and_later_videos_know_the_earlier_ones():
    assert playlist.MAX_EPISODES == 3
    from app import concepts
    assert concepts.MAX_CONCEPTS == 3
    pl = {"title": "DSA", "topic": "DSA", "episodes": [
        {"title": "Arrays", "focus": "arrays", "taught": "- Array Example: declare an array [code shown: int[] a = {1, 2}]"},
        {"title": "Lists", "focus": "lists"}, {"title": "Stacks", "focus": "stacks"}]}
    ctx = playlist.series_context(pl, 2)
    assert "Array Example" in ctx["taught"] and ctx["previous"][0].startswith("Arrays")
    assert playlist.series_context(pl, 0)["taught"] == ""


def test_the_course_hands_each_video_what_the_previous_one_taught(monkeypatch):
    seen = []

    def fake_build(concept, languages, level, duration_s, documents, series=None, images=None, mode="explain", progressive=False, quality="flash", progress=None):
        seen.append((concept, (series or {}).get("taught", "")))
        progress("Checking the lesson", 0.58, taught=f"- Taught in {concept}")
        progress("Almost", 0.7)
        return {"id": f"L{len(seen)}", "languages": {"en": {"duration_s": 50.0}}}

    pl = {"id": "p9", "topic": "DSA", "title": "", "languages": ["en"], "level": "beginner", "duration_s": 60, "documents": [], "images": [], "mode": "explain",
          "requested": 3, "episodes": [], "status": "planning"}
    cur = playlist.Curriculum(title="DSA", episodes=[playlist.Episode(title=t, focus=t) for t in ("Arrays", "Lists", "Stacks")])
    monkeypatch.setattr(playlist, "load", lambda pid: pl)
    monkeypatch.setattr(playlist, "save", lambda p: None)
    monkeypatch.setattr(playlist, "design_curriculum", lambda *a, **k: cur)
    monkeypatch.setattr(playlist, "build_lesson", fake_build)
    monkeypatch.setattr(playlist.resources, "wait_for_headroom", lambda *a, **k: None)         # (the real gate waits while the laptop is short of memory)
    playlist.build("p9")
    assert seen[0][1] == "" and "Taught in DSA: Arrays" in seen[1][1] and "Taught in DSA: Lists" in seen[2][1] and "Arrays" in seen[2][1]


def test_the_first_part_of_a_video_opens_with_a_title_card_and_the_others_do_not():
    body = [sc("code", "Toy Box", code=LOOP), sc("flow", "Steps", items=["1", "2"]), sc("bullets", "Idea", items=["3", "4"]), sc("diagram", "Parts", items=["5", "6"])]
    first = schema.normalize(LessonPlan(title="Data structures", scenes=[s.model_copy() for s in body]), segment=True, last=False, title=True)
    assert first.scenes[0].template == "title" and not any(s.heading == "Common mistakes" for s in first.scenes)
    second = schema.normalize(LessonPlan(title="Data structures", scenes=[s.model_copy() for s in body]), segment=True, last=False, title=False)
    assert second.scenes[0].template == "code"


def test_the_same_heading_with_overlapping_content_is_dropped_even_on_another_template():
    plan = LessonPlan(title="x", scenes=[
        sc("title", "Linked lists", "Why do we need a chain of boxes that point to each other in memory instead of one big block?"),
        sc("diagram", "Linked List Structure", "A linked list is a chain of nodes, and each node holds a value and a pointer to the next node in the chain.", items=["head", "node", "next"]),
        sc("code", "Array", "int[] a gives a block", code=["int[] a = new int[3];"]),
        sc("flow", "Linked List Structure", "A linked list is a chain of nodes where each node points to the next node, so you walk along the chain from the head.", items=["start at head", "follow next"]),
        sc("bullets", "More", "Something entirely different about memory and how the garbage collector frees unused objects automatically."),
    ])
    content.dedupe_plan(plan)
    assert [s.heading for s in plan.scenes].count("Linked List Structure") == 1


@pytest.mark.parametrize("typed, subject", [
    ("teach me about dsa in java", "DSA in Java"),
    ("Teach me about the basics of DSA in Java", "The basics of DSA in Java"),
    ("can you make a video on the water cycle please", "The water cycle"),
    ("explain photosynthesis", "Photosynthesis"),
    ("I want to learn about black holes", "Black holes"),
    ("generate a lesson about Newton's third law", "Newton's third law"),
    ("Teach me how to create a pacman game in python", "Create a pacman game in Python"),
    ("teach me OOPS Concept", "OOPS Concept"),
    ("How do vaccines work", "How do vaccines work"),             # a question is already a subject
    ("DSA in Java", "DSA in Java"),
    ("Teach me", "Teach me"),                                       # nothing but the request: kept whole
])
def test_the_request_words_are_not_part_of_the_subject(typed, subject):
    assert content.clean_topic(typed) == subject


def test_a_lesson_built_from_a_request_never_carries_the_request_words(monkeypatch):
    from app import pipeline
    seen = {}

    def fake_build(concept, languages, level, duration_s, documents, series, progress, focus, images, mode, progressive, plan_override=None, quality="flash"):
        seen["concept"] = concept
        return {"id": "x"}

    monkeypatch.setattr(pipeline, "_build", fake_build)
    monkeypatch.setattr(pipeline, "_gpu_slot", lambda: __import__("contextlib").nullcontext())
    pipeline.build_lesson("Teach me about dsa in java", ["en"])
    assert seen["concept"] == "DSA in Java"


# ------------------------------------------------------------------ found by generating real lessons
def test_a_word_copied_from_the_schema_is_not_a_heading():
    plan = LessonPlan(title="The Solar System", scenes=[sc("title", "string", "Let's explore string in our solar system, starting with the planets' orbits around the Sun today."), sc("flow", "Steps")])
    assert "placeholder" in content.schema_echo(plan)
    assert content.schema_echo(LessonPlan(title="T", scenes=[sc("title", "Why planets?"), sc("flow", "Steps")])) is None
    fixed = schema.normalize(LessonPlan(title="The Solar System", scenes=[sc("title", "string"), sc("flow", "Steps"), sc("bullets", "More"), sc("summary", "End")]))
    assert fixed.scenes[0].heading == "The Solar System"


def test_the_same_heading_is_never_shown_twice():
    plan = part([sc("title", "Rainbows"), sc("bullets", "Sunlight & Raindrops", "Sunlight acts like a spotlight and raindrops work as tiny prisms that bend every ray of light."),
                 sc("flow", "Light bends", "When the light enters a drop it slows down and changes direction, which splits it into colours."),
                 sc("flow", "Sunlight & Raindrops", "Water drops hanging in the air after a shower let the white light fall apart into a ribbon of colour."),
                 sc("quiz", "Quiz")])
    content.dedupe_plan(plan)
    assert [s.heading for s in plan.scenes].count("Sunlight & Raindrops") == 1


def test_two_scenes_that_open_with_the_same_sentence_are_one_scene():
    a = "Just like when sunlight passes through a glass prism, raindrops bend light and split it into its colours in order."
    b = "Just like when sunlight passes through a glass prism, the colours of a rainbow always appear in the same fixed order."
    plan = part([sc("title", "Rainbows"), sc("flow", "Colours order", a), sc("diagram", "Order diagram", b), sc("bullets", "Drops", "A drop acts as a tiny mirror and lens at once, sending light back toward you."), sc("quiz", "Quiz")])
    content.dedupe_plan(plan)
    assert [s.heading for s in plan.scenes].count("Order diagram") == 0


def test_a_quiz_must_ask_a_question_and_not_give_the_answer_away():
    good = part([sc("title", "T"), sc("quiz", "Q", "Which color bends the most? Think about the drop.", items=["Red", "Violet", "Green"], answer_index=1)])
    assert content.quiz_problem(good) is None
    statement = part([sc("title", "T"), sc("quiz", "Q", "Red is on the outside of a rainbow. Violet follows behind.", items=["Red", "Violet", "Green"], answer_index=1)])
    assert "question" in content.quiz_problem(statement)
    leaked = part([sc("title", "T"), sc("quiz", "Q", "Which color bends the most? It is violet.", items=["Red", "Violet", "Green"], answer_index=1)])
    assert "answer away" in content.quiz_problem(leaked)
    dup = part([sc("title", "T"), sc("quiz", "Q", "Which one is it?", items=["Red", "red", "Green"], answer_index=1)])
    assert "distinct" in content.quiz_problem(dup)
