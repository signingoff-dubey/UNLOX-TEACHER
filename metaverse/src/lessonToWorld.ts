import type { Quiz, World, Zone } from "./types";

/** The slice of the backend lesson JSON (web/src/types.ts) this module reads. */
export type SceneLike = {
  template: string;
  heading: string;
  narration: string;
  items: string[];
  left_title?: string;
  right_title?: string;
  left?: string[];
  right?: string[];
  answer_index: number;
};
export type TrackLike = { title: string; scenes: SceneLike[] };
export type LessonLike = { id: string; concept: string; languages: Record<string, TrackLike> };

const COLORS = ["#62e6ff", "#ffb454", "#ff6fa8", "#74ffb8"];
const CONTENT = new Set(["bullets", "flow", "cycle", "compare", "diagram"]);
const clip = (s: string, n = 64) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

function termsOf(s: SceneLike): string[] {
  const raw = s.template === "compare"
    ? [s.left_title, s.right_title, ...(s.left ?? []).slice(0, 1), ...(s.right ?? []).slice(0, 1)]
    : s.items;
  return raw.filter((t): t is string => !!t).slice(0, 4).map((t) => clip(t, 28));
}

function quizFromScene(q: SceneLike): Quiz {
  return {
    q: q.heading,
    options: q.items.map((i) => clip(i)),
    answer: Math.min(Math.max(q.answer_index, 0), q.items.length - 1),
    hint: "Think back to the station you just read.",
  };
}

/** Fallback quiz when the lesson has fewer quiz scenes than stations: spot the idea that belongs to this station. */
function generatedQuiz(own: SceneLike, others: SceneLike[]): Quiz {
  const right = clip(own.items[0] ?? own.heading);
  const wrong = others.flatMap((o) => o.items).filter((i) => i && clip(i) !== right).map((i) => clip(i));
  const options = [right, ...Array.from(new Set(wrong)).slice(0, 3)];
  return {
    q: `Which idea belongs to “${clip(own.heading, 40)}”?`,
    options,
    answer: 0,
    hint: "Reread the station. The right answer is mentioned there.",
  };
}

/**
 * Turn a generated lesson into a walkable world: every content scene becomes a station,
 * every quiz scene becomes a gate. Returns null when the lesson has nothing to walk through.
 */
export function lessonToWorld(lesson: LessonLike, lang = "en"): World | null {
  const track = lesson.languages[lang] ?? lesson.languages.en ?? Object.values(lesson.languages)[0];
  if (!track) return null;
  const content = track.scenes.filter((s) => CONTENT.has(s.template) && s.items.length + (s.left?.length ?? 0) > 0).slice(0, 4);
  if (!content.length) return null;
  const quizzes = track.scenes.filter((s) => s.template === "quiz" && s.items.length >= 2);
  const zones: Zone[] = content.map((s, i) => ({
    name: clip(s.heading, 22),
    color: COLORS[i % COLORS.length],
    info: { title: s.heading, body: s.narration, terms: termsOf(s) },
    quiz: quizzes[i]
      ? quizFromScene(quizzes[i])
      : generatedQuiz(s, content.filter((c) => c !== s)),
  }));
  // A station needs at least two options to be a quiz; pad from the lesson's own vocabulary if needed.
  zones.forEach((z) => {
    if (z.quiz.options.length < 2) z.quiz = { ...z.quiz, options: [...z.quiz.options, "None of these"] };
  });
  const summary = track.scenes.find((s) => s.template === "summary");
  return {
    title: track.title || lesson.concept,
    match: lesson.concept.toLowerCase(),
    zones,
    finale: { title: "Summit reached", body: summary?.narration ?? `You walked through the whole lesson on ${lesson.concept}.` },
  };
}
