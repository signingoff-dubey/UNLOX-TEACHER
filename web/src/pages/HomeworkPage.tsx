import React, { useEffect, useState } from "react";
import { api, url } from "../api";
import { Glyph } from "../ds/Glyph";

export type HomeworkMeta = { id: string; title: string; status: "queued" | "reading" | "writing" | "done" | "error"; done: number; total: number; error: string | null; markdown?: string };

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const inline = (s: string) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");

/** A small, safe Markdown renderer for the answer file: everything is escaped first, then headings, quotes, lists, rules and bold are added. */
export function renderMarkdown(md: string): string {
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd();
    let m: RegExpMatchArray | null;
    if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) { close(); out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); }
    else if (/^-{3,}$/.test(line)) { close(); out.push("<hr/>"); }
    else if ((m = /^>\s?(.*)$/.exec(line))) { close(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); }
    else if ((m = /^\s*[-*]\s+(.*)$/.exec(line))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(m[1])}</li>`); }
    else if ((m = /^\s*\d+[.)]\s+(.*)$/.exec(line))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(m[1])}</li>`); }
    else if (!line.trim()) close();
    else { close(); out.push(`<p>${inline(line)}</p>`); }
  }
  close();
  return out.join("\n");
}

/** The homework answer file, viewed in the browser. It is written question by question, so this page polls while it grows. */
export const HomeworkPage: React.FC<{ id: string }> = ({ id }) => {
  const [hw, setHw] = useState<HomeworkMeta | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer = 0;
    const tick = () => {
      api<HomeworkMeta>(`/api/homework/${id}`).then((h) => {
        if (stop) return;
        setHw(h);
        if (h.status !== "done" && h.status !== "error") timer = window.setTimeout(tick, 2000);
      }).catch(() => { if (!stop) setGone(true); });
    };
    tick();
    return () => { stop = true; window.clearTimeout(timer); };
  }, [id]);

  if (gone) return <main className="main"><div className="empty">That homework could not be found.</div></main>;
  if (!hw) return <main className="main"><div className="empty">Loading…</div></main>;
  const working = hw.status !== "done" && hw.status !== "error";
  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">Homework answers</div>
          <h1>{hw.title}</h1>
          <div className="stats">
            <div className={working ? "stat" : "stat accent"}>
              <span className="stat-label">{hw.status === "done" ? `${hw.total} answers ready` : hw.status === "error" ? "Could not finish"
                : hw.total ? `Writing answer ${Math.min(hw.done + 1, hw.total)} of ${hw.total}` : "Reading the homework"}</span>
            </div>
          </div>
        </div>
        <div className="hero-actions">
          <a className="primary" href={url(`/api/homework/${id}/download`)} download><Glyph name="download" size={18} />Download .md</a>
        </div>
      </header>
      {hw.error && <div className="notice bad" role="alert">{hw.error}</div>}
      <article className="card white md" aria-busy={working}>
        {hw.markdown ? <div dangerouslySetInnerHTML={{ __html: renderMarkdown(hw.markdown) }} />
          : <p className="muted">The answers appear here one by one as the AI writes them.</p>}
        {working && <div className="md-cursor" aria-hidden />}
      </article>
    </main>
  );
};
