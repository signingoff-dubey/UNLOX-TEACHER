import { useEffect, useRef, useState } from "react";

/**
 * Progress that never stops moving while work is going on.
 *
 * The backend reports progress in bursts: nothing while the model reads the lesson, then a rush of tokens. Showing that
 * directly makes a bar sit at 15% and then jump to 30%. Instead a clock drives the bar: it rises steadily and slows down
 * the longer the work takes (it never reaches the end by itself). Real progress can only pull it further ahead, and when
 * it does the bar glides to the new value at a limited speed instead of snapping. It never goes backwards.
 *
 * `tau` is roughly how many seconds the work takes (bigger = slower rise).
 */
export function useSteadyProgress(real: number, active: boolean, tau = 22): number {
  const [shown, setShown] = useState(0);
  const live = useRef({ v: 0, vel: 0, real, t0: 0, last: 0 });
  live.current.real = real;

  useEffect(() => {
    const s = live.current;
    if (!active) { s.v = 0; s.vel = 0; s.t0 = 0; s.last = 0; setShown(0); return; }
    let raf = 0;
    const tick = (now: number) => {
      if (!s.t0) s.t0 = now;
      const dt = s.last ? Math.min((now - s.last) / 1000, 0.1) : 0.016;
      s.last = now;
      const clock = 0.93 * (1 - Math.exp(-(now - s.t0) / 1000 / tau));
      const target = Math.min(0.985, Math.max(s.real, clock));
      const want = target > s.v ? (target - s.v) * 1.6 + 0.012 : 0;        // faster when far behind, never zero while behind
      s.vel += (want - s.vel) * Math.min(dt * 4, 1);                       // the speed itself changes smoothly
      s.v = Math.min(0.985, s.v + s.vel * dt);
      setShown(s.v);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, tau]);

  return shown;
}
