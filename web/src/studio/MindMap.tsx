import React, { useMemo, useState } from "react";
import { api } from "../api";
import type { StudioData } from "./types";

type Props = { data: StudioData["mindmap"]; lessonId: string; lang: string; ask: (question: string) => void };

type Box = { id: string; label: string; x: number; y: number; w: number; h: number; side: 1 | -1; tone: number; depth: 0 | 1 | 2 };
type Link = { from: string; to: string; tone: number; depth: number };
type Info = { path: string[]; notes: string[]; kids: { id: string; label: string }[] };

const TONES = ["#41A642", "#ED8441", "#E0587F", "#4A86C5", "#7A6FD0", "#9AAE1E"];   // one colour per branch (the app's aura colours)
const SOFT = ["#e3f1e0", "#fbe8d7", "#fadde5", "#dce9f6", "#e6e3f6", "#f0f3cf"];
const H = 34, GAP = 12, COL = 64;

const width = (s: string, bold = false, max = 200) => Math.min(max, Math.round(26 + s.length * (bold ? 8.2 : 7.4)));
const clip = (s: string, w: number, bold = false) => { const n = Math.floor((w - 26) / (bold ? 8.2 : 7.4)); return s.length > n ? s.slice(0, Math.max(n - 1, 1)) + "…" : s; };

/** Two-sided tree, as in XMind and MindMeister: the topic in the middle, branches left and right, curved links, one colour per branch. */
function layout(d: StudioData["mindmap"]) {
  const rootW = width(d.root, true, 240);
  const sides: Record<string, number[]> = { "1": [], "-1": [] };
  d.branches.forEach((_, i) => sides[i % 2 === 0 ? "1" : "-1"].push(i));
  const boxes: Box[] = [], links: Link[] = [];
  const info = new Map<string, Info>();
  info.set("r", { path: [d.root], notes: [], kids: d.branches.map((b, i) => ({ id: `b${i}`, label: b.label })) });
  let top = 0, bottom = 0;
  const placed: { side: 1 | -1; rows: { i: number; y: number; ys: number[] }[] }[] = [];

  for (const side of [1, -1] as const) {
    let y = 0;
    const rows: { i: number; y: number; ys: number[] }[] = [];
    for (const i of sides[String(side)]) {
      const kids = d.branches[i].children;
      const ys = (kids.length ? kids : [null]).map(() => { const v = y; y += H + GAP; return v; });
      rows.push({ i, y: kids.length ? (ys[0] + ys[ys.length - 1]) / 2 : ys[0], ys: kids.length ? ys : [] });
      y += GAP * 1.5;
    }
    const total = Math.max(y - GAP * 2.5, 0);
    rows.forEach((r) => { r.y -= total / 2; r.ys = r.ys.map((v) => v - total / 2); });
    top = Math.min(top, -total / 2); bottom = Math.max(bottom, total / 2);
    placed.push({ side, rows });
  }
  const maxB = Math.max(...d.branches.map((b) => width(b.label, true)), 90);
  const maxC = Math.max(...d.branches.flatMap((b) => b.children.map((c) => width(c.label))), 90);
  const x1 = rootW / 2 + COL;                    // left edge of a branch box (right side); mirrored on the left
  const x2 = x1 + maxB + COL;                    // left edge of a leaf box
  const half = x2 + maxC;

  boxes.push({ id: "r", label: d.root, x: -rootW / 2, y: -H / 2 - 4, w: rootW, h: H + 8, side: 1, tone: -1, depth: 0 });
  for (const { side, rows } of placed) {
    for (const r of rows) {
      const b = d.branches[r.i];
      const bw = width(b.label, true), id = `b${r.i}`;
      boxes.push({ id, label: b.label, x: side === 1 ? x1 : -x1 - bw, y: r.y - H / 2, w: bw, h: H, side, tone: r.i % TONES.length, depth: 1 });
      links.push({ from: "r", to: id, tone: r.i % TONES.length, depth: 1 });
      info.set(id, { path: [d.root, b.label], notes: [], kids: b.children.map((c, k) => ({ id: `${id}.${k}`, label: c.label })) });
      b.children.forEach((c, k) => {
        const cw = width(c.label), cid = `${id}.${k}`;
        boxes.push({ id: cid, label: c.label, x: side === 1 ? x2 : -x2 - cw, y: r.ys[k] - H / 2, w: cw, h: H, side, tone: r.i % TONES.length, depth: 2 });
        links.push({ from: id, to: cid, tone: r.i % TONES.length, depth: 2 });
        info.set(cid, { path: [d.root, b.label, c.label], notes: c.details, kids: [] });
      });
    }
  }
  return { boxes, links, info, half, top: top - H, bottom: bottom + H };
}

/** The mind map: drawn here as SVG from the tree the backend parsed (no Mermaid). Click a box to see what is under it, and ask for more. */
export const MindMap: React.FC<Props> = ({ data, lessonId, lang, ask }) => {
  const g = useMemo(() => layout(data), [data]);
  const [sel, setSel] = useState("r");
  const [zoom, setZoom] = useState(1);
  const [more, setMore] = useState<Record<string, { text?: string; busy?: boolean; error?: string }>>({});
  const byId = useMemo(() => new Map(g.boxes.map((b) => [b.id, b])), [g]);
  const cur = g.info.get(sel) ?? g.info.get("r")!;
  const label = cur.path[cur.path.length - 1];
  const tone = byId.get(sel)?.tone ?? -1;
  const accent = tone >= 0 ? TONES[tone] : "var(--ink)";

  const link = (l: Link) => {
    const a = byId.get(l.from)!, b = byId.get(l.to)!;
    const s = b.side;
    const ax = s === 1 ? a.x + a.w : a.x, bx = s === 1 ? b.x : b.x + b.w;
    const ay = a.y + a.h / 2, by = b.y + b.h / 2, mx = (ax + bx) / 2;
    return <path key={l.to} d={`M${ax},${ay} C${mx},${ay} ${mx},${by} ${bx},${by}`} fill="none" stroke={TONES[l.tone]} strokeWidth={l.depth === 1 ? 4 : 2.2} strokeLinecap="round" opacity={l.depth === 1 ? 0.9 : 0.7} />;
  };

  const explain = async () => {
    setMore((m) => ({ ...m, [sel]: { busy: true } }));
    try {
      const res = await api<{ reply: string }>(`/api/lessons/${lessonId}/chat`, {
        message: `In 3 short sentences, explain "${label}" as part of "${cur.path[0]}"${cur.path.length > 2 ? ` (under ${cur.path[1]})` : ""}. Add one simple example.`,
        lang, time_s: 0, history: [], speak: false,
      });
      setMore((m) => ({ ...m, [sel]: { text: res.reply } }));
    } catch (e) {
      setMore((m) => ({ ...m, [sel]: { error: (e as Error).message || "The tutor could not answer." } }));
    }
  };

  const vw = g.half * 2 + 40, vh = g.bottom - g.top + 40;
  const m = more[sel];
  return (
    <div className="mm2">
      <div className="studio-actions">
        <button type="button" className="ghost small" onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.15).toFixed(2)))} aria-label="Zoom out">−</button>
        <span className="mm-zoom" aria-live="polite">{Math.round(zoom * 100)}%</span>
        <button type="button" className="ghost small" onClick={() => setZoom((z) => Math.min(2.2, +(z + 0.15).toFixed(2)))} aria-label="Zoom in">+</button>
        <button type="button" className="ghost small" onClick={() => setZoom(1)}>Fit</button>
        <span className="muted">Click any box to see more about it.</span>
      </div>
      <div className="mm2-canvas">
        <svg viewBox={`${-vw / 2} ${g.top - 20} ${vw} ${vh}`} style={{ width: `${zoom * 100}%` }} role="group" aria-label={`Mind map of ${data.root}`}>
          <g>{g.links.map(link)}</g>
          {g.boxes.map((b) => {
            const on = sel === b.id;
            const fill = b.depth === 0 ? "#1c1c1c" : b.depth === 1 ? TONES[b.tone] : SOFT[b.tone];
            const ink = b.depth === 2 ? "#1c1c1c" : b.depth === 1 && b.tone !== 5 ? "#ffffff" : b.depth === 1 ? "#1c1c1c" : "#ffffff";
            return (
              <g key={b.id} className={`mm2-node${on ? " on" : ""}`} tabIndex={0} role="button" aria-pressed={on} aria-label={b.label}
                onClick={() => setSel(b.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSel(b.id); } }}>
                <title>{b.label}</title>
                <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={b.h / 2} fill={fill} stroke={b.depth === 2 ? TONES[b.tone] : "none"} strokeWidth={1.6} />
                {on && <rect x={b.x - 4} y={b.y - 4} width={b.w + 8} height={b.h + 8} rx={(b.h + 8) / 2} fill="none" stroke="#1c1c1c" strokeWidth={2} />}
                <text x={b.x + b.w / 2} y={b.y + b.h / 2} textAnchor="middle" dominantBaseline="central" fill={ink}
                  fontSize={b.depth === 0 ? 17 : b.depth === 1 ? 14.5 : 13.5} fontWeight={b.depth === 2 ? 500 : 700}>{clip(b.label, b.w, b.depth < 2)}</text>
              </g>
            );
          })}
        </svg>
      </div>

      <section className="mm2-detail" style={{ borderColor: accent }} aria-live="polite">
        <div className="mm2-path">{cur.path.map((p, i) => <span key={i}>{p}{i < cur.path.length - 1 ? " ›" : ""}</span>)}</div>
        <h3>{label}</h3>
        {cur.notes.length > 0 && <ul>{cur.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
        {cur.kids.length > 0 && (
          <div className="mm2-kids">
            <span className="muted">{sel === "r" ? "Main ideas:" : "Inside this:"}</span>
            {cur.kids.map((k) => <button type="button" key={k.id} className="chip" onClick={() => setSel(k.id)}>{k.label}</button>)}
          </div>
        )}
        {m?.text && <p className="mm2-more">{m.text}</p>}
        {m?.error && <p className="mm2-more bad">{m.error}</p>}
        <div className="mm2-actions">
          <button type="button" className="go small" onClick={explain} disabled={m?.busy}>{m?.busy ? "Thinking…" : m?.text ? "Explain again" : "Explain this"}</button>
          <button type="button" className="ghost small" onClick={() => ask(`Explain "${label}" in the context of ${data.root}.`)}>Ask in the chat</button>
        </div>
      </section>
    </div>
  );
};
