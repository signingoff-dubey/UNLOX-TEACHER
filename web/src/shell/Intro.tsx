import React, { useEffect, useRef, useState } from "react";
import { LEFT, RIGHT, SPROUT, WORD } from "./logoPaths";

// The whole animation is a pure function of time t (seconds), as in intro-animation/index.html: a book rises, its left page flips open,
// sprouts grow, the lockup slides left and the name is wiped in, then the cover lifts away. It plays on every page load.
const SPINE = 342, BASE = 830, DUR = 3.7, LIFT = 0.8;
const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
const io = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const out = (x: number) => 1 - Math.pow(1 - x, 3);
type Tf = { x?: number; y?: number; r?: number; sx?: number; sy?: number; kY?: number };
const T = (px: number, py: number, { x = 0, y = 0, r = 0, sx = 1, sy = 1, kY = 0 }: Tf = {}) =>
  `translate(${px + x} ${py + y}) rotate(${r}) skewY(${kY}) scale(${sx} ${sy}) translate(${-px} ${-py})`;

export const Intro: React.FC = () => {
  const [gone, setGone] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const $ = (id: string) => el.querySelector<SVGElement>(`[data-i="${id}"]`)!;
    const set = (id: string, k: string, v: string | number) => $(id).setAttribute(k, String(v));
    const render = (t: number) => {
      const rise = out(seg(t, 0.15, 0.85));
      set("book", "transform", T(SPINE, BASE, { y: (1 - rise) * 40, sx: 0.9 + 0.1 * rise, sy: 0.9 + 0.1 * rise }));
      set("book", "opacity", seg(t, 0.15, 0.5));
      const th = Math.PI * (1 - io(seg(t, 0.9, 2.0)));
      set("left", "transform", T(SPINE, BASE, { sx: Math.cos(th), kY: -9 * Math.sin(th) }));
      const g = out(seg(t, 1.8, 2.7)), top = 740 - 240 * g;
      set("grow", "y", top); set("grow", "height", 740 - top);
      const sw = seg(t, 2.6, 3.4);
      set("sprout", "transform", T(348, 690, { r: Math.sin(sw * Math.PI * 2) * 1.2 * (1 - sw) }));
      set("lockup", "transform", `translate(${344 * (1 - io(seg(t, 2.2, 3.1)))} 0)`);
      const w = io(seg(t, 2.5, 3.5));
      set("wipe", "width", 680 * w + 20);
      set("word", "transform", T(860, 700, { x: -(1 - w) * 30 }));
      set("word", "opacity", seg(t, 2.5, 2.9));
      el.style.transform = `translateY(${-io(seg(t, DUR, DUR + LIFT)) * 100}%)`;
    };
    let off = false;                       // Settings > Opening animation
    try { off = localStorage.getItem("vt.intro") === "0"; } catch { /* storage blocked */ }
    const reduce = off || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let t0: number | null = null, frame = 0, alive = true;
    const finish = () => { if (alive) { setGone(true); document.dispatchEvent(new Event("intro:done")); } };
    const tick = (ts: number) => {
      t0 ??= ts;
      const t = (ts - t0) / 1000;
      render(t);
      if (t < DUR + LIFT) frame = requestAnimationFrame(tick); else finish();
    };
    const skip = (e: Event) => { if (e.type === "click" || (e as KeyboardEvent).key === "Escape") { cancelAnimationFrame(frame); finish(); } };
    if (reduce) { render(DUR + LIFT); finish(); return; }
    render(0);
    frame = requestAnimationFrame(tick);
    el.addEventListener("click", skip);
    window.addEventListener("keydown", skip);
    return () => { alive = false; cancelAnimationFrame(frame); el.removeEventListener("click", skip); window.removeEventListener("keydown", skip); };
  }, []);

  if (gone) return null;
  return (
    <div className="intro" ref={root} aria-hidden>
      <svg viewBox="150 440 1070 480" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Chanakya">
        <defs>
          <clipPath id="intro-grow"><rect data-i="grow" x="200" y="500" width="320" height="240" /></clipPath>
          <clipPath id="intro-wipe"><rect data-i="wipe" x="500" y="560" width="0" height="300" /></clipPath>
        </defs>
        <g data-i="lockup">
          <g data-i="book">
            <g data-i="left">{LEFT.map(([d, f], i) => <path key={i} d={d} fill={f} />)}</g>
            <g>{RIGHT.map(([d, f], i) => <path key={i} d={d} fill={f} />)}</g>
            <g clipPath="url(#intro-grow)"><g data-i="sprout">{SPROUT.map(([d, f], i) => <path key={i} d={d} fill={f} />)}</g></g>
          </g>
          <g clipPath="url(#intro-wipe)"><g data-i="word">{WORD.map(([d, f], i) => <path key={i} d={d} fill={f} />)}</g></g>
        </g>
      </svg>
    </div>
  );
};
