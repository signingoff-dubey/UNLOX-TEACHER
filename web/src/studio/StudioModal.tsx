import React, { useEffect, useRef, useState } from "react";
import "./studio.css";
import type { Lesson } from "../types";
import { useStudioResult } from "./useStudio";
import { useSteadyProgress } from "./useSteadyProgress";
import { Ui } from "../components/ui-icons";
import { MindMap } from "./MindMap";
import { Flashcards } from "./Flashcards";
import { Faq, Glossary, Quiz, StudyGuide, Timeline } from "./viewers";
import { TOOLS, cardsCsv, toMarkdown, type Difficulty, type Size, type StudioData, type StudioKind, type StudioResult } from "./types";

type Props = {
  lesson: Lesson;
  lang: string;
  kind: StudioKind;
  title: string;
  onClose: () => void;
  /** Close this and ask the tutor in the chat. */
  onAsk: (question: string) => void;
};

const SIZES: [Size, string][] = [["few", "Fewer"], ["standard", "Standard"], ["more", "More"]];
const LEVELS: [Difficulty, string][] = [["easy", "Easy"], ["medium", "Medium"], ["hard", "Hard"]];

/** A study tool made from the lesson: flashcards, quiz, mind map, study guide, FAQ, glossary or timeline. */
export const StudioModal: React.FC<Props> = ({ lesson, lang, kind: first, title, onClose, onAsk }) => {
  const [kind, setKind] = useState<StudioKind>(first);
  const [size, setSize] = useState<Size>("standard");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [attempt, setAttempt] = useState(0);
  const { result, progress, error } = useStudioResult(lesson.id, kind, lang, size, difficulty, attempt);
  const steady = useSteadyProgress(progress.value, !result && !error);
  const tool = TOOLS.find((t) => t.kind === kind)!;
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus?.(); };
  }, [onClose]);

  const save = (text: string, name: string, type: string) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const base = `${title}-${kind}`.replace(/[^\w-]+/g, "_");
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!result) return;
    try { await navigator.clipboard.writeText(toMarkdown(result, title)); setCopied(true); setTimeout(() => setCopied(false), 1400); } catch { /* clipboard blocked */ }
  };

  const body = () => {
    if (error) return <div className="error" role="alert">{error} <button type="button" className="ghost small" onClick={() => setAttempt((a) => a + 1)}>Try again</button></div>;
    if (!result) {
      return (
        <div className="studio-wait" role="status">
          <div className="bar"><i style={{ width: `${Math.max(4, Math.round(steady * 100))}%` }} /></div>
          <p>{progress.stage || "Starting"}… making your {tool.label.toLowerCase()} from this lesson.</p>
        </div>
      );
    }
    const d = result.data;
    switch (result.kind) {
      case "flashcards": return <Flashcards key={result.size + result.difficulty} data={d as StudioData["flashcards"]} lessonId={lesson.id} />;
      case "quiz": return <Quiz key={result.size + result.difficulty} data={d as StudioData["quiz"]} lessonId={lesson.id} />;
      case "mindmap": return <MindMap data={d as StudioData["mindmap"]} ask={onAsk} />;
      case "studyguide": return <StudyGuide data={d as StudioData["studyguide"]} open={setKind} />;
      case "faq": return <Faq data={d as StudioData["faq"]} ask={onAsk} />;
      case "glossary": return <Glossary data={d as StudioData["glossary"]} ask={onAsk} />;
      default: return <Timeline data={d as StudioData["timeline"]} />;
    }
  };

  return (
    <div className="studio-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="studio" role="dialog" aria-modal="true" aria-labelledby="studio-h">
        <header className="studio-head">
          <div>
            <h2 id="studio-h">{tool.label}</h2>
            <p className="muted">{tool.hint}</p>
          </div>
          <div className="studio-tools">
            {result && <button type="button" className="icon-btn" onClick={copy} aria-label="Copy as Markdown">{copied ? <Ui name="check" size={18} /> : <Ui name="file" size={18} />}</button>}
            {result && (
              <button type="button" className="icon-btn" aria-label={kind === "flashcards" ? "Download cards as CSV for Anki" : "Download as Markdown"}
                onClick={() => kind === "flashcards"
                  ? save(cardsCsv((result.data as StudioData["flashcards"]).cards), `${base}.csv`, "text/csv")
                  : save(toMarkdown(result, title), `${base}.md`, "text/markdown")}>
                <Ui name="download" size={18} />
              </button>
            )}
            <button type="button" ref={closeBtn} className="icon-btn" onClick={onClose} aria-label="Close"><Ui name="x" size={18} /></button>
          </div>
        </header>

        <nav className="studio-switch" aria-label="Study tools">
          {TOOLS.map((t) => (
            <button type="button" key={t.kind} className={t.kind === kind ? "on" : ""} aria-current={t.kind === kind} onClick={() => setKind(t.kind)}>
              <Ui name={t.kind} size={16} />{t.label}
            </button>
          ))}
        </nav>

        {(tool.sized || tool.leveled) && (
          <div className="studio-opts">
            {tool.sized && (
              <div className="seg" role="radiogroup" aria-label="How many">
                {SIZES.map(([v, l]) => <button type="button" key={v} role="radio" aria-checked={size === v} className={size === v ? "on" : ""} onClick={() => setSize(v)}>{l}</button>)}
              </div>
            )}
            {tool.leveled && (
              <div className="seg" role="radiogroup" aria-label="Difficulty">
                {LEVELS.map(([v, l]) => <button type="button" key={v} role="radio" aria-checked={difficulty === v} className={difficulty === v ? "on" : ""} onClick={() => setDifficulty(v)}>{l}</button>)}
              </div>
            )}
          </div>
        )}

        <div className="studio-body">{body()}</div>
      </div>
    </div>
  );
};
