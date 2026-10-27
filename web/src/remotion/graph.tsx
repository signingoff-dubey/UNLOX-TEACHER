import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { Scene } from "../types";
import type { TemplateProps } from "./templates";
import { C, FONT_STACK, PALETTE, STAGE, W, ease, fit, pop, revealFrame } from "./theme";

// Graph scene: axes, grid and curves drawn from plain numbers. Nothing from the LLM is ever evaluated;
// each curve type below is our own formula, parameterised by a, b, c, d.

type Curve = NonNullable<Scene["curves"]>[number];
type Mark = NonNullable<Scene["marks"]>[number];
type Pt = { x: number; y: number };

const PLOT = { x: STAGE.left, y: 260, w: 1010, h: 590 };
const PANEL = { x: PLOT.x + PLOT.w + 50, w: STAGE.right - (PLOT.x + PLOT.w + 50) };

const fnY = (c: Curve, x: number): number | null => {
  const { a, b, c: cc, d } = c;
  switch (c.type) {
    case "line": return a * x + b;
    case "parabola": return a * x * x + b * x + cc;
    case "cubic": return a * x ** 3 + b * x * x + cc * x + d;
    case "sine": return a * Math.sin(b * x + cc) + d;
    case "cosine": return a * Math.cos(b * x + cc) + d;
    case "exp": return a * Math.exp(b * x) + cc;
    case "abs": return a * Math.abs(x - b) + cc;
    case "sqrt": return x - b >= 0 ? a * Math.sqrt(x - b) + cc : null;
    case "reciprocal": return Math.abs(x) < 1e-6 ? null : a / x;
    default: return null;
  }
};

const isRound = (c: Curve) => c.type === "circle" || c.type === "ellipse";
const radii = (c: Curve) => (c.type === "circle" ? { rx: c.c, ry: c.c } : { rx: c.c, ry: c.d });

/** Pick x/y ranges that show the curves well. Round shapes keep equal scale so circles look round. */
const autoRanges = (s: Scene) => {
  const curves = s.curves ?? [];
  let [x0, x1] = s.x_range?.length === 2 ? s.x_range : [NaN, NaN];
  let [y0, y1] = s.y_range?.length === 2 ? s.y_range : [NaN, NaN];
  const round = curves.filter(isRound);
  if (!Number.isFinite(x0) || !Number.isFinite(x1)) {
    if (round.length) {
      const ext = Math.max(...round.map((c) => Math.abs(c.a) + radii(c).rx));
      x0 = -ext * 1.35; x1 = ext * 1.35;
    } else { x0 = -6; x1 = 6; }
  }
  if (!Number.isFinite(y0) || !Number.isFinite(y1)) {
    if (round.length) {
      const ext = Math.max(...round.map((c) => Math.abs(c.b) + radii(c).ry));
      y0 = -ext * 1.35; y1 = ext * 1.35;
    } else {
      const ys: number[] = [0];
      for (const c of curves) for (let i = 0; i <= 120; i++) {
        const y = fnY(c, x0 + ((x1 - x0) * i) / 120);
        if (y !== null && Number.isFinite(y) && Math.abs(y) < 1e4) ys.push(y);
      }
      const lo = Math.min(...ys), hi = Math.max(...ys);
      const pad = Math.max((hi - lo) * 0.12, 0.5);
      y0 = Math.max(lo - pad, -40); y1 = Math.min(hi + pad, 40);
      if (y1 - y0 < 2) { y0 -= 1; y1 += 1; }
    }
  }
  if (round.length) {                       // equal aspect: widen whichever axis is too tight for the plot box
    const ratio = PLOT.w / PLOT.h;
    const xs = x1 - x0, ysn = y1 - y0;
    if (xs / ysn < ratio) { const m = (x0 + x1) / 2, h = (ysn * ratio) / 2; x0 = m - h; x1 = m + h; }
    else { const m = (y0 + y1) / 2, h = xs / ratio / 2; y0 = m - h; y1 = m + h; }
  }
  return { x0, x1, y0, y1 };
};

const niceStep = (span: number, target = 8) => {
  const raw = span / target, mag = 10 ** Math.floor(Math.log10(raw));
  const n = raw / mag;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * mag;
};
const fmt = (v: number) => (Math.abs(v) < 1e-9 ? "0" : String(Math.round(v * 100) / 100));

const Heading: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pop(frame, fps);
  return (
    <div style={{ position: "absolute", left: STAGE.left, top: STAGE.top, right: STAGE.left, opacity: p,
      transform: `translateY(${(1 - p) * 30}px)` }}>
      <div style={{ fontSize: fit(text, 64, 34), fontWeight: 800, color: C.ink, lineHeight: 1.25 }}>{text}</div>
      <div style={{ height: 8, width: 160 * ease(frame, 6, 26), background: C.saffron, borderRadius: 4, marginTop: 14 }} />
    </div>
  );
};

export const GraphScene: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const curves = scene.curves ?? [];
  const marks = scene.marks ?? [];
  const steps = curves.length + marks.length;
  const { x0, x1, y0, y1 } = autoRanges(scene);
  const sx = (x: number) => PLOT.x + ((x - x0) / (x1 - x0)) * PLOT.w;
  const sy = (y: number) => PLOT.y + PLOT.h - ((y - y0) / (y1 - y0)) * PLOT.h;
  const color = (k: number) => PALETTE[k % PALETTE.length];
  const label = (k: number) => scene.items[k] ?? "";
  const gridIn = ease(frame, 0, 20);

  const xStep = niceStep(x1 - x0), yStep = niceStep(y1 - y0, 6);
  const xt: number[] = [], yt: number[] = [];
  for (let v = Math.ceil(x0 / xStep) * xStep; v <= x1 + 1e-9; v += xStep) xt.push(v);
  for (let v = Math.ceil(y0 / yStep) * yStep; v <= y1 + 1e-9; v += yStep) yt.push(v);
  const ax = Math.min(Math.max(0, x0), x1), ay = Math.min(Math.max(0, y0), y1);

  const pathOf = (c: Curve): string => {
    if (isRound(c)) {
      const { rx, ry } = radii(c);
      return Array.from({ length: 121 }, (_, i) => {
        const t = (i / 120) * Math.PI * 2;
        return `${i ? "L" : "M"}${sx(c.a + rx * Math.cos(t))} ${sy(c.b + ry * Math.sin(t))}`;
      }).join("");
    }
    let d = "", pen = false, prev: number | null = null;
    for (let i = 0; i <= 300; i++) {
      const x = x0 + ((x1 - x0) * i) / 300, y = fnY(c, x);
      const bad = y === null || !Number.isFinite(y) || y < y0 - (y1 - y0) || y > y1 + (y1 - y0)
        || (prev !== null && y !== null && Math.abs(y - prev) > (y1 - y0) * 2);
      if (bad) { pen = false; prev = null; continue; }
      d += `${pen ? "L" : "M"}${sx(x)} ${sy(y as number)}`;
      pen = true; prev = y;
    }
    return d;
  };

  // Geometry of the first circle, for centre / radius / diameter / chord / tangent marks.
  const circle = curves.find((c) => c.type === "circle");
  const at = (deg: number): Pt => {
    const t = (deg * Math.PI) / 180;
    return { x: circle!.a + circle!.c * Math.cos(t), y: circle!.b + circle!.c * Math.sin(t) };
  };

  const markShape = (m: Mark, p: number, col: string, text: string): React.ReactNode => {
    const dot = (pt: Pt, r = 9) => <circle cx={sx(pt.x)} cy={sy(pt.y)} r={r * p} fill={col} />;
    const line = (a: Pt, b: Pt, dash?: string) => (
      <line x1={sx(a.x)} y1={sy(a.y)} x2={sx(a.x + (b.x - a.x) * p)} y2={sy(a.y + (b.y - a.y) * p)}
        stroke={col} strokeWidth={6} strokeLinecap="round" strokeDasharray={dash} />
    );
    const tag = (pt: Pt, dx: number, dy: number) => {
      if (!text) return null;
      const w = Math.max(60, text.length * 22 + 24);
      const x = Math.min(Math.max(sx(pt.x) + dx - 10, PLOT.x + 8), PLOT.x + PLOT.w - w - 8);
      const y = Math.min(Math.max(sy(pt.y) + dy - 34, PLOT.y + 8), PLOT.y + PLOT.h - 54);
      return (
        <g opacity={p}>
          <rect x={x} y={y} width={w} height={46} rx={12} fill="#fff" stroke={col} strokeWidth={3} />
          <text x={x + 12} y={y + 33} fontSize={30} fontWeight={700} fill={C.ink}>{text}</text>
        </g>
      );
    };
    if (m.kind === "point") {
      const pt = { x: m.x, y: m.y };
      return <>{dot(pt)}{tag(pt, 14, -14)}
        <text x={sx(pt.x) + 14} y={sy(pt.y) + 36} fontSize={24} fill={C.muted} opacity={p}>({fmt(m.x)}, {fmt(m.y)})</text></>;
    }
    if (!circle) return null;
    const ctr = { x: circle.a, y: circle.b };
    switch (m.kind) {
      case "center": return <>{dot(ctr, 11)}{tag(ctr, -190, 70)}</>;
      case "radius": { const e = at(35); return <>{line(ctr, e)}{dot(e, 7)}{tag({ x: (ctr.x + e.x) / 2, y: (ctr.y + e.y) / 2 }, 10, -16)}</>; }
      case "diameter": { const a = at(155), b = at(335); return <>{line(a, b)}{dot(a, 7)}{dot(b, 7)}{tag(b, 24, 56)}</>; }
      case "chord": { const a = at(215), b = at(325); return <>{line(a, b)}{dot(a, 7)}{dot(b, 7)}{tag({ x: ctr.x, y: a.y }, -40, 48)}</>; }
      case "tangent": {
        const t = at(60), dir = { x: -Math.sin((60 * Math.PI) / 180), y: Math.cos((60 * Math.PI) / 180) };
        const k = circle.c * 0.7;
        return <>{line({ x: t.x - dir.x * k, y: t.y - dir.y * k }, { x: t.x + dir.x * k, y: t.y + dir.y * k })}{dot(t, 8)}{tag(t, 18, -16)}</>;
      }
    }
    return null;
  };

  return (
    <>
      <Heading text={scene.heading} />
      <svg width={W} height={1080} style={{ position: "absolute", inset: 0, overflow: "visible" }} fontFamily={FONT_STACK}>
        <rect x={PLOT.x} y={PLOT.y} width={PLOT.w} height={PLOT.h} rx={22} fill="#fff" stroke={C.line} strokeWidth={3} opacity={gridIn} />
        <g opacity={gridIn}>
          {xt.map((v) => <line key={`x${v}`} x1={sx(v)} x2={sx(v)} y1={PLOT.y} y2={PLOT.y + PLOT.h} stroke={C.grid} strokeWidth={2} />)}
          {yt.map((v) => <line key={`y${v}`} x1={PLOT.x} x2={PLOT.x + PLOT.w} y1={sy(v)} y2={sy(v)} stroke={C.grid} strokeWidth={2} />)}
          <line x1={PLOT.x} x2={PLOT.x + PLOT.w} y1={sy(ay)} y2={sy(ay)} stroke={C.ink} strokeWidth={4} />
          <line y1={PLOT.y} y2={PLOT.y + PLOT.h} x1={sx(ax)} x2={sx(ax)} stroke={C.ink} strokeWidth={4} />
          {xt.filter((v) => Math.abs(v) > 1e-9).map((v) =>
            <text key={`tx${v}`} x={sx(v)} y={Math.min(sy(ay) + 30, PLOT.y + PLOT.h - 8)} fontSize={22} fill={C.muted} textAnchor="middle">{fmt(v)}</text>)}
          {yt.filter((v) => Math.abs(v) > 1e-9).map((v) =>
            <text key={`ty${v}`} x={Math.max(sx(ax) - 10, PLOT.x + 34)} y={sy(v) + 8} fontSize={22} fill={C.muted} textAnchor="end">{fmt(v)}</text>)}
          <text x={PLOT.x + PLOT.w - 18} y={sy(ay) - 12} fontSize={28} fontWeight={700} fill={C.ink} textAnchor="end">x</text>
          <text x={sx(ax) + 14} y={PLOT.y + 30} fontSize={28} fontWeight={700} fill={C.ink}>y</text>
        </g>
        <clipPath id="plotclip"><rect x={PLOT.x} y={PLOT.y} width={PLOT.w} height={PLOT.h} rx={22} /></clipPath>
        <g clipPath="url(#plotclip)">
          {curves.map((c, k) => {
            const start = revealFrame(k, steps, speechFrames);
            return <path key={k} d={pathOf(c)} pathLength={1} fill="none" stroke={color(k)} strokeWidth={8} strokeLinecap="round"
              strokeLinejoin="round" strokeDasharray="1 1" strokeDashoffset={1 - ease(frame, start, start + 30)} />;
          })}
        </g>
        {marks.map((m, i) => {
          const k = curves.length + i;
          const p = ease(frame, revealFrame(k, steps, speechFrames), revealFrame(k, steps, speechFrames) + 18);
          return <g key={`m${i}`}>{markShape(m, p, color(k), label(k))}</g>;
        })}
      </svg>

      {/* right panel: formula, then one card per revealed step */}
      {scene.equation ? (
        <div style={{ position: "absolute", left: PANEL.x, top: PLOT.y, width: PANEL.w, padding: "22px 26px", borderRadius: 22,
          background: C.ink, color: "#fff", fontSize: fit(scene.equation, 54, 22, 0.5), fontWeight: 700, textAlign: "center",
          fontFamily: "'Cambria Math','Noto Serif',Georgia,serif", opacity: ease(frame, 14, 34) }}>
          {scene.equation}
        </div>
      ) : null}
      {Array.from({ length: steps }, (_, k) => {
        const p = pop(frame, fps, revealFrame(k, steps, speechFrames));
        const text = label(k);
        if (!text) return null;
        return (
          <div key={k} style={{ position: "absolute", left: PANEL.x, width: PANEL.w, top: PLOT.y + (scene.equation ? 120 : 0) + k * 96,
            display: "flex", alignItems: "center", gap: 18, padding: "14px 22px", borderRadius: 20, background: "#fff",
            border: `3px solid ${color(k)}`, boxShadow: `0 6px 0 ${C.line}`, opacity: p, transform: `translateX(${(1 - p) * 40}px)` }}>
            <div style={{ width: 22, height: 22, borderRadius: "50%", background: color(k), flex: "none" }} />
            <div style={{ fontSize: fit(text, 36, 20, 0.6), fontWeight: 700, color: C.ink }}>{text}</div>
          </div>
        );
      })}
    </>
  );
};
