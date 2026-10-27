import React, { useEffect, useRef, useState } from "react";
import { Ui } from "./ui-icons";

/** Same look as the Android app (and RootLens): the voice panel spreads out of the mic as a growing circle with a ring on its edge, and shrinks back into it. */
type Props = {
  open: boolean;
  /** Where the mic button is, in the coordinates of the panel this sits in (which must be position: relative). */
  origin: { x: number; y: number };
  /** Panel size, to know how far the circle has to grow to cover it. */
  size: { w: number; h: number };
  stream: MediaStream | null;
  onCancel: () => void;
  onDone: () => void;
};

const BARS = 36;
const STEP = 0.05;          // seconds per bar

/** Bars that glide: the head eases toward the mic level every frame and the bars scroll left. Drawn on a canvas, no React renders per frame. */
function Wave({ stream }: { stream: MediaStream | null }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return undefined;
    const g = canvas.getContext("2d");
    if (!g) return undefined;
    let ctx: AudioContext | null = null;
    let an: AnalyserNode | null = null;
    const buf = new Uint8Array(512);
    if (stream) {
      ctx = new AudioContext();
      an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(an);
    }
    const bars = new Array<number>(BARS).fill(0);
    let head = 0, phase = 0, last = 0, raf = 0;
    const ink = getComputedStyle(canvas).color;
    const draw = (now: number) => {
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 0;
      last = now;
      let goal = 0.05 + 0.05 * Math.sin(now / 300);
      if (an) {
        an.getByteTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += ((v - 128) / 128) ** 2;
        goal = Math.min(1, Math.sqrt(sum / buf.length) * 7);
      }
      head += (goal - head) * (1 - Math.exp(-dt * 14));
      phase += dt / STEP;
      while (phase >= 1) { bars.shift(); bars.push(head); phase -= 1; }
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, w, h);
      g.lineCap = "round";
      g.strokeStyle = ink;
      const step = w / (BARS - 1), bw = step * 0.42;
      for (let i = 0; i < BARS; i++) {
        const v = i === BARS - 1 ? head : bars[i];
        const bh = h * Math.min(1, Math.max(0.06, v));
        const x = step * (i - phase);
        if (x < -bw) continue;
        g.globalAlpha = 0.85 * (1 - (Math.abs(i - BARS / 2) / (BARS / 2)) * 0.6);
        g.lineWidth = bw;
        g.beginPath(); g.moveTo(x, (h - bh) / 2); g.lineTo(x, (h + bh) / 2); g.stroke();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); void ctx?.close().catch(() => {}); };
  }, [stream]);
  return <canvas ref={ref} className="voice-wave" aria-hidden />;
}

export const VoiceRipple: React.FC<Props> = ({ open, origin, size, stream, onCancel, onDone }) => {
  const [mounted, setMounted] = useState(open);
  useEffect(() => {
    if (open) { setMounted(true); return undefined; }
    const t = window.setTimeout(() => setMounted(false), 340);         // let the circle shrink back into the button first
    return () => window.clearTimeout(t);
  }, [open]);
  if (!mounted) return null;
  const far = Math.ceil(Math.max(
    Math.hypot(origin.x, origin.y), Math.hypot(size.w - origin.x, origin.y),
    Math.hypot(origin.x, size.h - origin.y), Math.hypot(size.w - origin.x, size.h - origin.y)));
  const vars = { "--ox": `${origin.x}px`, "--oy": `${origin.y}px`, "--far": `${far}px` } as React.CSSProperties;
  return (
    <>
      <div className={`voice-ring${open ? "" : " out"}`} style={vars} aria-hidden />
      <div className={`voice-layer${open ? "" : " out"}`} style={vars} role="group" aria-label="Recording your question">
        <p className="voice-title" role="status">Listening…</p>
        <p className="voice-sub">Ask in any language. Tap the tick when you are done.</p>
        <Wave stream={stream} />
        <div className="voice-actions">
          <button type="button" className="voice-btn" onClick={onCancel} aria-label="Cancel"><Ui name="x" size={22} /></button>
          <button type="button" className="voice-btn done" onClick={onDone} aria-label="Send what I said"><Ui name="check" size={22} /></button>
        </div>
      </div>
    </>
  );
};
