import React, { useEffect, useRef, useState } from "react";
import type { Lesson, Scene, Track } from "../types";
import { Ui } from "./ui-icons";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const store = {
  get(k: string) { try { return localStorage.getItem(k) ?? ""; } catch { return ""; } },
  set(k: string, v: string) { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
};

/** The study notes for one scene, taken from the lesson itself (so they are always in the language being watched). */
export function sceneNotes(s: Scene): { points: string[]; code?: string[]; output?: string[]; equation?: string; answer?: string } {
  switch (s.template) {
    case "title": return { points: [s.narration] };
    case "compare": return { points: [`${s.left_title}: ${s.left.join(", ")}`, `${s.right_title}: ${s.right.join(", ")}`] };
    case "quiz": return { points: s.items.map((o, i) => `${String.fromCharCode(65 + i)}. ${o}`), answer: s.items[s.answer_index] };
    case "graph": return { points: s.items, equation: s.equation };
    case "code": return {
      points: (s.highlights ?? []).map((h, k) => `Line ${h + 1}: ${s.items[k] ?? ""}`), code: s.code, output: s.output,
    };
    case "flow": case "cycle": return { points: s.items.map((x, i) => `${i + 1}. ${x}`) };
    default: return { points: s.items.length ? s.items : [s.narration] };
  }
}

/** Notes as Markdown, for copy and download. */
export function notesMarkdown(track: Track, mine: string): string {
  const out = [`# ${track.title}`, ""];
  track.scenes.forEach((s, i) => {
    const n = sceneNotes(s);
    out.push(`## ${i + 1}. ${s.heading} (${mmss(s.start_s)})`);
    if (n.equation) out.push(`**${n.equation}**`);
    n.points.forEach((p) => out.push(`- ${p}`));
    if (n.code) out.push("", "```" + (s.code_lang ?? ""), ...n.code, "```");
    if (n.output?.length) out.push("", "Output: " + n.output.join(" / "));
    if (n.answer) out.push("", `Answer: ${n.answer}`);
    out.push("");
  });
  if (mine.trim()) out.push("---", "", "## My notes", "", mine.trim(), "");
  return out.join("\n");
}

type Props = {
  lesson: Lesson | null;
  track?: Track;
  current: number;
  onSeek: (seconds: number) => void;
};

/** Left panel: scene-by-scene notes that follow the video, plus your own notes. */
export const NotesPanel: React.FC<Props> = ({ lesson, track, current, onSeek }) => {
  const [mine, setMine] = useState("");
  const [copied, setCopied] = useState(false);
  const active = useRef<HTMLLIElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const key = lesson ? `vt.notes.${lesson.id}` : "";

  useEffect(() => { setMine(key ? store.get(key) : ""); }, [key]);
  // Keep the current note in view by scrolling the list itself. scrollIntoView also scrolls the page, which dragged the whole
  // page down at every new scene.
  useEffect(() => {
    const ol = list.current, el = active.current;
    if (!ol || !el) return;
    const o = ol.getBoundingClientRect(), e = el.getBoundingClientRect();
    if (e.top < o.top) ol.scrollTo({ top: ol.scrollTop - (o.top - e.top) - 6, behavior: "smooth" });
    else if (e.bottom > o.bottom) ol.scrollTo({ top: ol.scrollTop + (e.bottom - o.bottom) + 6, behavior: "smooth" });
  }, [current, track?.lang]);

  const edit = (v: string) => { setMine(v); if (key) store.set(key, v); };
  const md = track ? notesMarkdown(track, mine) : "";
  const copy = async () => {
    try { await navigator.clipboard.writeText(md); setCopied(true); setTimeout(() => setCopied(false), 1400); } catch { /* clipboard blocked */ }
  };
  const download = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    a.download = `${lesson?.concept ?? "notes"}-notes.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <section className="panel-col notes" aria-label="Notes">
      <div className="panel-head">
        <h2>Notes</h2>
        {track && (
          <div className="panel-actions">
            <button type="button" className="icon-btn" onClick={copy} aria-label="Copy notes">{copied ? <Ui name="check" size={18} /> : <Ui name="file" size={18} />}</button>
            <button type="button" className="icon-btn" onClick={download} aria-label="Download notes"><Ui name="download" size={18} /></button>
          </div>
        )}
      </div>

      {!track ? (
        <div className="panel-empty">
          <div className="skel" /><div className="skel short" /><div className="skel" /><div className="skel short" />
          <p className="muted">Notes fill in here, scene by scene, as soon as your lesson is ready.</p>
        </div>
      ) : (
        <>
          <ol className="note-list" ref={list}>
            {track.scenes.map((s, i) => {
              const n = sceneNotes(s);
              return (
                <li key={i} ref={i === current ? active : undefined} className={i === current ? "note on" : "note"}>
                  <button type="button" className="note-head" onClick={() => onSeek(s.start_s)} aria-label={`Jump to ${s.heading}`}>
                    <span className="time">{mmss(s.start_s)}</span>
                    <span className="note-title">{s.heading}</span>
                  </button>
                  {n.equation && <div className="note-eq">{n.equation}</div>}
                  <ul>{n.points.map((p, k) => <li key={k}>{p}</li>)}</ul>
                  {n.code && <pre className="note-code">{n.code.join("\n")}</pre>}
                  {n.output && n.output.length > 0 && <div className="note-out">{n.output.join("  ·  ")}</div>}
                  {n.answer && <div className="note-ans">Answer: {n.answer}</div>}
                </li>
              );
            })}
          </ol>
          {lesson?.sources && lesson.sources.length > 0 && (
            <div className="sources-box">
              <div className="label">Sources</div>
              <ul className="sources">
                {lesson.sources.map((s) => (
                  <li key={s.title + (s.section ?? "")}>
                    {/^https?:/.test(s.url)
                      ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                      : <span className="src-title">{s.title}</span>}
                    <span className="muted"> {s.section || (s.source === "upload" ? "your PDF" : s.source)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {lesson?.facts && lesson.facts.checked > 0 && (
            <div className="sources-box">
              <div className="label">Fact check</div>
              <p className="muted">
                {lesson.facts.checked} statements checked: {lesson.facts.supported} confirmed by {lesson.facts.sources.length ? lesson.facts.sources.join(", ") : "the sources"},{" "}
                {lesson.facts.confirmed_by_model} by a second look, {lesson.facts.unconfirmed} could not be confirmed
                {lesson.facts.fixed.length + lesson.facts.removed.length > 0 && `; ${lesson.facts.fixed.length} corrected, ${lesson.facts.removed.length} removed`}.
              </p>
              {lesson.facts.fixed.length > 0 && (
                <ul className="sources">
                  {lesson.facts.fixed.map((f, i) => <li key={i}><span className="src-title">Scene {f.scene}</span> <span className="muted">{f.before} → {f.after}</span></li>)}
                </ul>
              )}
            </div>
          )}
          <div className="mine">
            <label htmlFor="mynotes" className="label">My notes</label>
            <textarea id="mynotes" value={mine} onChange={(e) => edit(e.target.value)} placeholder="Type anything you want to remember…" rows={4} />
          </div>
        </>
      )}
    </section>
  );
};
