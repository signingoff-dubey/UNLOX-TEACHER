import React, { useEffect, useMemo, useState } from "react";
import type { MapBranch, MapChild, Question, StudioData, StudioKind } from "./types";

/** Every viewer gets `ask`: close the studio and ask the tutor about something on screen. */
type Ask = (question: string) => void;

// ------------------------------------------------------------------ quiz
export const Quiz: React.FC<{ data: StudioData["quiz"] }> = ({ data }) => {
  const [qs, setQs] = useState<Question[]>(data.questions);
  const [i, setI] = useState(0);
  const [pick, setPick] = useState<number | null>(null);
  const [wrong, setWrong] = useState<Question[]>([]);
  const [score, setScore] = useState(0);
  const q = qs[i];

  if (!q) {
    return (
      <div className="fc-done">
        <h3>{score} of {qs.length} correct</h3>
        <p className="muted">{wrong.length === 0 ? "Perfect round." : "Retry the ones you missed to lock them in."}</p>
        <div className="studio-actions">
          {wrong.length > 0 && <button type="button" className="go small" onClick={() => { setQs(wrong); setWrong([]); setScore(0); setI(0); setPick(null); }}>Retry {wrong.length} missed</button>}
          <button type="button" className="ghost" onClick={() => { setQs(data.questions); setWrong([]); setScore(0); setI(0); setPick(null); }}>Start over</button>
        </div>
      </div>
    );
  }
  const choose = (k: number) => {
    if (pick !== null) return;
    setPick(k);
    if (k === q.answer_index) setScore((s) => s + 1); else setWrong((w) => [...w, q]);
  };
  return (
    <div className="quiz">
      <div className="fc-meta"><span>Question {i + 1} of {qs.length}</span><span>{score} correct</span></div>
      <h3 className="quiz-q">{q.question}</h3>
      <div className="quiz-opts" role="group" aria-label="Answer options">
        {q.options.map((o, k) => {
          const state = pick === null ? "" : k === q.answer_index ? " right" : k === pick ? " wrong" : " dim";
          return (
            <button type="button" key={k} className={`quiz-opt${state}`} onClick={() => choose(k)} aria-disabled={pick !== null}>
              <b>{"ABCD"[k]}</b>{o}
              {pick !== null && k === q.answer_index && <span className="sr-only"> (correct)</span>}
            </button>
          );
        })}
      </div>
      {pick !== null && (
        <div className="quiz-why" role="status">
          <b>{pick === q.answer_index ? "Correct. " : "Not quite. "}</b>{q.explanation}
          <div><button type="button" className="go small" onClick={() => { setI(i + 1); setPick(null); }}>{i + 1 === qs.length ? "See result" : "Next question"}</button></div>
        </div>
      )}
    </div>
  );
};

// ------------------------------------------------------------------ mind map
type MNode = { id: string; label: string; kids: MNode[] };

function tree(d: StudioData["mindmap"]): MNode {
  const child = (c: MapChild, id: string): MNode => ({ id, label: c.label, kids: c.details.map((t, k) => ({ id: `${id}.${k}`, label: t, kids: [] })) });
  return {
    id: "r", label: d.root,
    kids: d.branches.map((b: MapBranch, i) => ({ id: `r${i}`, label: b.label, kids: b.children.map((c, k) => child(c, `r${i}.${k}`)) })),
  };
}

/** Plain HTML tree: used only if the Mermaid renderer cannot draw the map. */
export const MindMapTree: React.FC<{ data: StudioData["mindmap"]; ask: Ask }> = ({ data, ask }) => {
  const root = useMemo(() => tree(data), [data]);
  // Root and its branches start open; the small detail notes start closed.
  const [open, setOpen] = useState<Set<string>>(() => new Set(["r", ...root.kids.map((k) => k.id)]));
  const [sel, setSel] = useState<MNode>(root);
  const all = useMemo(() => { const ids: string[] = []; const walk = (n: MNode) => { if (n.kids.length) ids.push(n.id); n.kids.forEach(walk); }; walk(root); return ids; }, [root]);

  const click = (n: MNode) => {
    setSel(n);
    if (n.kids.length) setOpen((o) => { const x = new Set(o); if (x.has(n.id)) x.delete(n.id); else x.add(n.id); return x; });
  };
  const draw = (n: MNode, depth: number): React.ReactNode => (
    <div className="mm-row" key={n.id}>
      <button type="button" className={`mm-node d${Math.min(depth, 3)}${sel.id === n.id ? " sel" : ""}`} onClick={() => click(n)}
        aria-expanded={n.kids.length ? open.has(n.id) : undefined}>
        {n.label}{n.kids.length > 0 && <i aria-hidden>{open.has(n.id) ? "−" : "+"}</i>}
      </button>
      {n.kids.length > 0 && open.has(n.id) && <div className="mm-kids">{n.kids.map((k) => <div className="mm-kid" key={k.id}>{draw(k, depth + 1)}</div>)}</div>}
    </div>
  );
  return (
    <div className="mm-wrap">
      <div className="studio-actions">
        <button type="button" className="ghost small" onClick={() => setOpen(new Set(all))}>Expand all</button>
        <button type="button" className="ghost small" onClick={() => setOpen(new Set(["r"]))}>Collapse</button>
        <span className="muted">Click a branch to open or close it.</span>
      </div>
      <div className="mm-scroll">{draw(root, 0)}</div>
      <div className="mm-sel">
        <span>Selected: <b>{sel.label}</b></span>
        <button type="button" className="go small" onClick={() => ask(`Explain "${sel.label}" in the context of ${root.label}.`)}>Ask the tutor about this</button>
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ study guide, FAQ, glossary, timeline
export const StudyGuide: React.FC<{ data: StudioData["studyguide"]; open: (k: StudioKind) => void }> = ({ data, open }) => (
  <article className="guide">
    <p className="guide-lead">{data.overview}</p>
    <h3>Key points</h3>
    <ul>{data.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
    <h3>Important terms</h3>
    <dl>{data.terms.map((t, i) => <React.Fragment key={i}><dt>{t.term}</dt><dd>{t.meaning}</dd></React.Fragment>)}</dl>
    <h3>Test yourself</h3>
    <ol>{data.review_questions.map((q, i) => <li key={i}>{q}</li>)}</ol>
    <div className="studio-actions">
      <button type="button" className="ghost" onClick={() => open("flashcards")}>Make flashcards</button>
      <button type="button" className="ghost" onClick={() => open("quiz")}>Take a quiz</button>
    </div>
  </article>
);

export const Faq: React.FC<{ data: StudioData["faq"]; ask: Ask }> = ({ data, ask }) => (
  <div className="faq">
    {data.items.map((it, i) => (
      <details key={i} open={i === 0}>
        <summary>{it.question}</summary>
        <p>{it.answer}</p>
        <button type="button" className="ghost small" onClick={() => ask(it.question)}>Ask the tutor more</button>
      </details>
    ))}
  </div>
);

export const Glossary: React.FC<{ data: StudioData["glossary"]; ask: Ask }> = ({ data, ask }) => {
  const [q, setQ] = useState("");
  const shown = data.terms.filter((t) => (t.term + t.meaning).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="gloss">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a term…" aria-label="Find a term" />
      <dl>
        {shown.map((t, i) => (
          <div key={i} className="gloss-row">
            <dt>{t.term}</dt><dd>{t.meaning}</dd>
            <button type="button" className="ghost small" onClick={() => ask(`What does "${t.term}" mean? Give me an example.`)}>Explain more</button>
          </div>
        ))}
      </dl>
      {shown.length === 0 && <p className="muted">No term matches “{q}”.</p>}
    </div>
  );
};

export const Timeline: React.FC<{ data: StudioData["timeline"] }> = ({ data }) => (
  <ol className="tl">
    {data.events.map((e, i) => (
      <li key={i}><span className="tl-dot" aria-hidden>{i + 1}</span><div><b>{e.label}</b><p>{e.detail}</p></div></li>
    ))}
  </ol>
);
