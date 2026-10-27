import React, { useEffect, useRef } from "react";

type Props = {
  /** Every pixel is light: the world can be mounted behind it now (its start-up work is hidden by the still frame). */
  onCovered: () => void;
  /** True once the world behind has started up and painted. The light then clears. */
  release: boolean;
  /** The light has cleared: unmount this. */
  onDone: () => void;
};

// A square tunnel, half-width 1, made of rings of blocks (4 walls x SEG blocks), seen from inside.
const D = 1.2;                    // ring length
const RINGS = 56;
const LEND = D * RINGS;           // where it ends, in a bright light
const SEG = 5;                    // blocks across one wall
const NEAR = 0.25;
const MAXZ = 26;                  // how far ahead walls are drawn; fog hides the rest
const GAP = 0.035;                // mortar between blocks (instead of stroking every edge, which is slow)
const BUILD_START = 0.2;          // s: the first block lands
const RING_DELAY = 0.024;         // s between rings: the tunnel builds from near to far
const FLIGHT = 0.55;              // s: a block flies in and snaps into place
const MOVE_START = 1.15;          // s: the walk starts, then accelerates to light speed
const MOVE_END = 3.55;            // s: arrival at the light
const MIN_HOLD = 0.3;             // s: shortest time the screen stays white
const CALM_FRAMES = 6;            // the light clears after this many smooth frames in a row...
const MAX_CALM_WAIT = 1200;       // ...or this long (ms) after the world is ready, whichever comes first
const FADE_MS = 800;              // the light clears (a CSS transition, so it runs on the compositor)
const FOG_STEPS = 10;

const HUES = [262, 176, 14, 42, 330, 212];
const clamp = (v: number) => Math.min(Math.max(v, 0), 1);

/** Cheap deterministic hash -> [0, 1). */
function h(a: number, b: number, c: number, d = 0) {
  let x = Math.imul(a + 374761393, 668265263) ^ Math.imul(b + 1274126177, 2246822519) ^ Math.imul(c + 3266489917, 3266489917) ^ Math.imul(d + 97, 40503);
  x = Math.imul(x ^ (x >>> 13), 1274126177);
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
}

type Block = { ring: number; side: number; u0: number; u1: number; tb: number; ox: number; oy: number; oz: number; color: number };

/** Everything that never changes is worked out once, not every frame. */
function buildBlocks(): Block[] {
  const out: Block[] = [];
  for (let ring = 0; ring < RINGS; ring++) {
    for (let side = 0; side < 4; side++) {
      for (let i = 0; i < SEG; i++) {
        const a = -1 + (2 * i) / SEG, b = -1 + (2 * (i + 1)) / SEG;
        out.push({
          ring, side, u0: a + GAP, u1: b - GAP, tb: BUILD_START + ring * RING_DELAY + h(ring, side, i) * 0.3,
          ox: (h(ring, side, i, 1) - 0.5) * 6, oy: (h(ring, side, i, 2) - 0.5) * 6, oz: (h(ring, side, i, 3) * 2 - 0.5) * 4,
          color: Math.floor(h(ring, side, i, 5) * HUES.length),
        });
      }
    }
  }
  return out;
}

/** Block colour per palette entry per fog step, as ready-made strings. */
function buildPalette(): string[][] {
  return HUES.map((hue) => Array.from({ length: FOG_STEPS }, (_, s) => `hsl(${hue},58%,${18 + (26 * s) / (FOG_STEPS - 1)}%)`));
}

/**
 * Entrance to the metaverse: a tunnel of blocks assembles around you, you walk down it faster and faster (light speed),
 * and the bright light at its far end grows until it fills the screen. The world is started while the screen is a still
 * white frame, and the light clears only once the world is ready, so nothing visible ever waits on the main thread.
 */
export const TunnelTransition: React.FC<Props> = ({ onCovered, release, onDone }) => {
  const canvas = useRef<HTMLCanvasElement>(null);
  const cb = useRef({ onCovered, onDone });
  cb.current = { onCovered, onDone };
  const released = useRef(release);
  released.current = release;

  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv?.getContext("2d", { alpha: true, desynchronized: true });
    if (!cv || !ctx) { cb.current.onCovered(); cb.current.onDone(); return; }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let raf = 0, fadeTimer = 0, coveredAt = 0, releasedAt = 0, lastNow = 0, calm = 0, fading = false, t0 = 0, prevT = 0, prevZ = 0, slow = 0, frames = 0;

    const W = window.innerWidth, H = window.innerHeight;
    let scale = Math.min(window.devicePixelRatio || 1, 1.5);         // lowered by itself if frames run long
    const size = () => { cv.width = Math.round(W * scale); cv.height = Math.round(H * scale); ctx.setTransform(scale, 0, 0, scale, 0, 0); };
    size();

    const cx = W / 2, cy = H / 2, f = Math.max(W, H) * 0.62;
    const blocks = buildBlocks();
    const palette = buildPalette();
    const stars = Array.from({ length: 90 }, (_, i) => ({ x: h(i, 1, 1) * 1.8 - 0.9, y: h(i, 2, 1) * 1.8 - 0.9, z: h(i, 3, 1) * 26, hue: 180 + h(i, 4, 1) * 60 }));
    const camZ = (t: number) => (LEND - 0.55) * Math.pow(clamp((t - MOVE_START) / (MOVE_END - MOVE_START)), 2.7);   // slow first steps, then ever faster

    const cover = () => {
      cv.style.background = "#fffaeb";
      ctx.clearRect(0, 0, W, H);
      coveredAt = performance.now();
      cb.current.onCovered();
    };
    const clear = () => {
      if (fading) return;
      fading = true;
      cv.classList.add("leaving");
      fadeTimer = window.setTimeout(() => cb.current.onDone(), FADE_MS + 40);
    };

    if (reduced) { cover(); fadeTimer = window.setTimeout(clear, 250); return () => window.clearTimeout(fadeTimer); }

    const frame = (now: number) => {
      if (!t0) t0 = now;
      const t = (now - t0) / 1000;

      if (coveredAt) {                                                // white and still: wait for the world, then let the light clear
        calm = lastNow && now - lastNow < 24 ? calm + 1 : 0;
        lastNow = now;
        const nowMs = performance.now();
        if (released.current && !releasedAt) releasedAt = nowMs;
        const held = nowMs - coveredAt;
        if (!fading && ((released.current && held > MIN_HOLD * 1000 && (calm >= CALM_FRAMES || nowMs - releasedAt > MAX_CALM_WAIT)) || held > 12000)) clear();
        raf = requestAnimationFrame(frame);
        return;
      }

      // Adaptive resolution: if the first frames run long, draw fewer pixels (the motion hides it).
      if (prevT) { slow += t - prevT > 0.024 ? 1 : 0; frames++; }
      if (frames === 24 && slow > 8 && scale > 1) { scale = 1; size(); }
      else if (frames === 60 && slow > 24 && scale > 0.8) { scale = 0.75; size(); }

      const cz = camZ(t);
      const speed = prevT ? (cz - prevZ) / Math.max(t - prevT, 1e-3) : 0;
      prevT = t; prevZ = cz;
      const warp = clamp(speed / 30);

      // The page fades into the tunnel. At speed the canvas is not cleared, so motion smears into streaks.
      const dark = clamp(t / 0.8);
      if (warp < 0.15) ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = `rgba(7,4,24,${warp < 0.15 ? dark * 0.96 : 0.42 - 0.15 * warp})`;
      ctx.fillRect(0, 0, W, H);

      const n0 = Math.floor(cz / D), n1 = Math.min(RINGS - 1, n0 + Math.ceil(MAXZ / D));
      const from = n0 * 4 * SEG, to = (n1 + 1) * 4 * SEG;
      for (let bi = to - 1; bi >= from; bi--) {                       // far to near
        const bl = blocks[bi];
        const k = clamp((t - bl.tb) / FLIGHT);
        if (k <= 0) continue;
        const fly = Math.pow(1 - k, 3);
        const z0 = bl.ring * D - cz + bl.oz * fly, z1 = z0 + D;
        if (z1 <= NEAR) continue;
        const a = z0 > NEAR ? z0 : NEAR;
        const ox = bl.ox * fly, oy = bl.oy * fly;
        let x0: number, y0: number, x1: number, y1: number;         // the block's two ends along its wall
        if (bl.side === 0) { x0 = bl.u0; y0 = -1; x1 = bl.u1; y1 = -1; }
        else if (bl.side === 1) { x0 = bl.u0; y0 = 1; x1 = bl.u1; y1 = 1; }
        else if (bl.side === 2) { x0 = -1; y0 = bl.u0; x1 = -1; y1 = bl.u1; }
        else { x0 = 1; y0 = bl.u0; x1 = 1; y1 = bl.u1; }
        x0 += ox; x1 += ox; y0 += oy; y1 += oy;
        const ia = f / a, ib = f / z1;
        const fog = clamp(1 - (a + z1) / 2 / MAXZ);
        ctx.globalAlpha = k;
        ctx.fillStyle = palette[bl.color][Math.round(fog * (FOG_STEPS - 1))];
        ctx.beginPath();
        ctx.moveTo(cx + x0 * ia, cy + y0 * ia);
        ctx.lineTo(cx + x1 * ia, cy + y1 * ia);
        ctx.lineTo(cx + x1 * ib, cy + y1 * ib);
        ctx.lineTo(cx + x0 * ib, cy + y0 * ib);
        ctx.fill();
        const glow = clamp(1 - (LEND - cz - (a + z1) / 2) / 9);       // blocks near the light turn warm
        if (glow > 0.05) { ctx.fillStyle = `rgba(255,214,120,${0.85 * glow})`; ctx.fill(); }
      }
      ctx.globalAlpha = 1;

      if (speed > 6) {                                                // speed streaks
        const len = speed * 0.035, vis = clamp(speed / 25);
        ctx.lineWidth = 1.5;
        for (const s of stars) {
          const z = (((s.z - cz) % 26) + 26) % 26 + NEAR;
          ctx.strokeStyle = `hsla(${s.hue},90%,85%,${clamp(1.2 - z / 26) * vis})`;
          ctx.beginPath();
          ctx.moveTo(cx + (s.x * f) / z, cy + (s.y * f) / z);
          ctx.lineTo(cx + (s.x * f) / (z + len), cy + (s.y * f) / (z + len));
          ctx.stroke();
        }
      }

      // The light at the end: a pinpoint at first, growing as you rush toward it (only the area it covers is painted).
      const dist = Math.max(LEND - cz, 0.2);
      const r = Math.max((f / dist) * 2.2, 10), born = clamp((t - 0.7) / 0.6);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, `rgba(255,255,255,${born})`);
      g.addColorStop(0.35, `rgba(255,236,170,${0.85 * born})`);
      g.addColorStop(1, "rgba(255,200,90,0)");
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = g;
      ctx.fillRect(Math.max(cx - r, 0), Math.max(cy - r, 0), Math.min(2 * r, W), Math.min(2 * r, H));
      ctx.globalCompositeOperation = "source-over";

      const white = Math.pow(clamp((cz - (LEND - 9)) / 8.5), 1.6);
      if (white > 0) {
        ctx.fillStyle = `rgba(255,250,235,${white})`;
        ctx.fillRect(0, 0, W, H);
      }
      if (t >= MOVE_END) cover();                                     // from here the canvas is one flat colour: nothing left to draw
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.clearTimeout(fadeTimer); };
  }, []);

  return <canvas ref={canvas} className="mv-tunnel" aria-hidden />;
};
