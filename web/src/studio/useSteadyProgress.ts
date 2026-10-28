import { useEffect, useRef, useState } from "react";

/**
 * The real progress, shown smoothly.
 *
 * The backend reports progress in steps (the model's tokens, questions written, scenes made). Snapping to each step makes the bar
 * jerk, so the shown value glides to the newest real value. It never runs ahead of what the backend reported (no clock, no creep)
 * and never goes backwards.
 */
export function useSteadyProgress(real: number, active: boolean): number {
  const [shown, setShown] = useState(0);
  const live = useRef({ v: 0, real, last: 0 });
  live.current.real = real;

  useEffect(() => {
    const s = live.current;
    if (!active) { s.v = 0; s.last = 0; setShown(0); return; }
    let raf = 0;
    const tick = (now: number) => {
      const dt = s.last ? Math.min((now - s.last) / 1000, 0.1) : 0.016;
      s.last = now;
      const target = Math.min(Math.max(s.real, 0), 1);
      if (target > s.v) {
        s.v = Math.min(target, s.v + (target - s.v) * Math.min(dt * 5, 1) + dt * 0.01);       // glide, and always arrive
        setShown(s.v);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return shown;
}
