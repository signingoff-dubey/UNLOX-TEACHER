import React, { useEffect, useRef } from "react";

export type Creation = {
  status: "running" | "done" | "error";
  kind: "lesson" | "course";
  concept: string;
  hash?: string;                // where to go when it is ready (`<lesson id>` or `c-<course id>`)
  playlistId?: string;
};

const DOTS = 72;
const POINTS = Array.from({ length: DOTS }, (_, i) => {         // an even spread of points on a sphere (Fibonacci lattice)
  const y = 1 - (2 * (i + 0.5)) / DOTS;
  const r = Math.sqrt(1 - y * y);
  const a = i * Math.PI * (3 - Math.sqrt(5));
  return { x: r * Math.cos(a), y, z: r * Math.sin(a) };
});

/** A small globe made of dots that turns. Still (one frame) when the user prefers reduced motion or the job is over. */
const DotGlobe: React.FC<{ size: number; spin: boolean }> = ({ size, spin }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);
    const color = getComputedStyle(canvas).color;
    const still = !spin || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const draw = (t: number) => {
      ctx.clearRect(0, 0, size, size);
      const turn = t / 2600, tilt = 0.38, cosT = Math.cos(tilt), sinT = Math.sin(tilt);
      const R = size / 2 - 3;
      ctx.fillStyle = color;
      for (const p of POINTS) {
        const x = p.x * Math.cos(turn) + p.z * Math.sin(turn);
        const z = -p.x * Math.sin(turn) + p.z * Math.cos(turn);
        const y = p.y * cosT - z * sinT;
        const depth = p.y * sinT + z * cosT;                     // -1 (far side) .. 1 (near side)
        const k = (depth + 1) / 2;
        ctx.globalAlpha = 0.18 + 0.82 * k;
        ctx.beginPath();
        ctx.arc(size / 2 + x * R, size / 2 + y * R, 0.55 + 1.05 * k, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!still) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [size, spin]);
  return <canvas ref={ref} className="pill-globe" style={{ width: size, height: size }} aria-hidden />;
};

const LABEL = { running: "Creating…", done: "Created", error: "Could not finish" } as const;

/** Floats at the bottom right on every page while a lesson is being made, so the student can leave its screen and still get back.
 *  When it is ready the pill pops: from its normal size to 115% to 120%, and says "Created". */
export const CreatingPill: React.FC<{ creation: Creation; onOpen: () => void }> = ({ creation, onOpen }) => (
  <div className="pill-wrap" role="status" aria-live="polite">
    <button type="button" className={`creating-pill ${creation.status}`} onClick={onOpen}
      aria-label={`${LABEL[creation.status]} ${creation.concept}. ${creation.status === "running" ? "Go back to it" : "Open it"}`}>
      <DotGlobe size={40} spin={creation.status === "running"} />
      <span>{LABEL[creation.status]}</span>
    </button>
  </div>
);
