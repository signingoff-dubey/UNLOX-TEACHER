import React, { useEffect, useRef } from "react";
import { url } from "../api";
import { Ui } from "./ui-icons";

export type Paper = { id: string; title: string; lang: string; total_marks: number; counts: Record<string, number>; kind: "worksheet" | "paper" };

/** Shown when a worksheet or question paper has been written: save the student's copy or the answer key, or open it to print / save as PDF. */
export const PaperReady: React.FC<{ paper: Paper; language: string; onClose: () => void }> = ({ paper, language, onClose }) => {
  const first = useRef<HTMLAnchorElement>(null);
  const name = paper.kind === "worksheet" ? "Worksheet" : "Question paper";
  const questions = Object.values(paper.counts).reduce((a, b) => a + b, 0);
  const html = (key: boolean, download: boolean) => url(`/api/papers/${paper.id}/html?key=${key}${download ? "&download=true" : ""}`);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus?.(); };
  }, [onClose]);

  return (
    <div className="studio-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="paper-pop" role="dialog" aria-modal="true" aria-labelledby="paper-pop-h">
        <button type="button" className="icon-btn paper-pop-x" onClick={onClose} aria-label="Close"><Ui name="x" size={18} /></button>
        <div className="paper-pop-badge" aria-hidden><Ui name="check" size={26} /></div>
        <h2 id="paper-pop-h">{name} ready</h2>
        <p className="paper-pop-title">{paper.title}</p>
        <p className="muted">{questions} questions · {paper.total_marks} marks · {language}</p>
        <div className="paper-pop-actions">
          <a ref={first} className="paper-pop-btn main" href={html(false, true)} download><Ui name="download" size={18} />Download student copy</a>
          <a className="paper-pop-btn" href={html(true, true)} download><Ui name="download" size={18} />Download answer key</a>
          <a className="paper-pop-btn ghost" href={html(false, false)} target="_blank" rel="noopener"><Ui name="file" size={18} />Open to print or save as PDF</a>
        </div>
      </div>
    </div>
  );
};
