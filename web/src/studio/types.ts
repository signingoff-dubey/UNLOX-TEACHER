export type StudioKind = "flashcards" | "quiz" | "mindmap" | "studyguide" | "faq" | "glossary" | "timeline";
export type Size = "few" | "standard" | "more";
export type Difficulty = "easy" | "medium" | "hard";

export type Card = { front: string; back: string };
export type Question = { question: string; options: string[]; answer_index: number; explanation: string };
export type MapChild = { label: string; details: string[] };
export type MapBranch = { label: string; children: MapChild[] };
export type Term = { term: string; meaning: string };

export type StudioData = {
  flashcards: { cards: Card[] };
  quiz: { questions: Question[] };
  mindmap: { root: string; branches: MapBranch[]; mermaid: string };
  studyguide: { overview: string; key_points: string[]; terms: Term[]; review_questions: string[] };
  faq: { items: { question: string; answer: string }[] };
  glossary: { terms: Term[] };
  timeline: { events: { label: string; detail: string }[] };
};

export type StudioResult<K extends StudioKind = StudioKind> = {
  kind: K; lang: string; size: Size; difficulty: Difficulty; translator: string; data: StudioData[K];
};

export const TOOLS: { kind: StudioKind; label: string; hint: string; sized: boolean; leveled: boolean }[] = [
  { kind: "flashcards", label: "Flashcards", hint: "Flip cards to memorise the key ideas", sized: true, leveled: true },
  { kind: "quiz", label: "Quiz", hint: "Test yourself, with an explanation for every answer", sized: true, leveled: true },
  { kind: "mindmap", label: "Mind map", hint: "See how the ideas connect. Click a branch to open it", sized: false, leveled: false },
  { kind: "studyguide", label: "Study guide", hint: "Overview, key points, terms and review questions", sized: false, leveled: false },
  { kind: "faq", label: "FAQ", hint: "Questions a curious student would ask", sized: true, leveled: false },
  { kind: "glossary", label: "Glossary", hint: "Key terms in plain words", sized: true, leveled: false },
  { kind: "timeline", label: "Timeline", hint: "The steps or events in order", sized: false, leveled: false },
];

/** The same content as plain Markdown (copy, download, paste into notes). */
export function toMarkdown(r: StudioResult, title: string): string {
  const d = r.data as StudioData[StudioKind];
  const head = `# ${title}\n\n`;
  switch (r.kind) {
    case "flashcards":
      return head + "## Flashcards\n\n" + (d as StudioData["flashcards"]).cards.map((c, i) => `${i + 1}. **${c.front}**\n   ${c.back}`).join("\n\n");
    case "quiz":
      return head + "## Quiz\n\n" + (d as StudioData["quiz"]).questions.map((q, i) =>
        `${i + 1}. ${q.question}\n${q.options.map((o, k) => `   - ${"ABCD"[k]}. ${o}${k === q.answer_index ? "  (correct)" : ""}`).join("\n")}\n   Why: ${q.explanation}`).join("\n\n");
    case "mindmap": {
      const m = d as StudioData["mindmap"];
      return head + `## Mind map: ${m.root}\n\n` + m.branches.map((b) =>
        `- **${b.label}**\n` + b.children.map((c) => `  - ${c.label}${c.details.length ? `: ${c.details.join("; ")}` : ""}`).join("\n")).join("\n");
    }
    case "studyguide": {
      const g = d as StudioData["studyguide"];
      return head + `## Study guide\n\n${g.overview}\n\n### Key points\n${g.key_points.map((p) => `- ${p}`).join("\n")}\n\n### Terms\n` +
        g.terms.map((t) => `- **${t.term}**: ${t.meaning}`).join("\n") + `\n\n### Review questions\n${g.review_questions.map((q, i) => `${i + 1}. ${q}`).join("\n")}`;
    }
    case "faq":
      return head + "## FAQ\n\n" + (d as StudioData["faq"]).items.map((i) => `**${i.question}**\n${i.answer}`).join("\n\n");
    case "glossary":
      return head + "## Glossary\n\n" + (d as StudioData["glossary"]).terms.map((t) => `- **${t.term}**: ${t.meaning}`).join("\n");
    default:
      return head + "## Timeline\n\n" + (d as StudioData["timeline"]).events.map((e, i) => `${i + 1}. **${e.label}**: ${e.detail}`).join("\n");
  }
}

/** Anki / Quizlet import: two columns, quoted. */
export function cardsCsv(cards: Card[]): string {
  const q = (s: string) => `"${s.replace(/"/g, '""')}"`;
  return cards.map((c) => `${q(c.front)},${q(c.back)}`).join("\n");
}
