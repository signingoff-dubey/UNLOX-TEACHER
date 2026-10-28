import { useEffect, useRef, useState } from "react";

/**
 * The real progress, shown smoothly. The backend reports progress in steps, so the shown value glides toward the newest
 * real one. It never runs ahead of what was reported, never goes backwards, and reaches 100% only when `done`.
 */
export function useSmoothProgress(target: number, done: boolean): number {
  const [shown, setShown] = useState(0);
  const live = useRef({ v: 0, target, done, last: 0 });
  live.current.target = target;
  live.current.done = done;

  useEffect(() => {
    let raf = 0;
    const tick = (now: number) => {
      const s = live.current;
      const dt = s.last ? Math.min((now - s.last) / 1000, 0.1) : 0.016;
      s.last = now;
      let next = s.v;
      if (s.done) {
        next += (1 - next) * Math.min(dt * 7, 1);
      } else if (next < s.target) {
        next = Math.min(s.target, next + (s.target - next) * Math.min(dt * 2.5, 1) + dt * 0.002);       // glide to the real value, never past it
      }
      s.v = Math.max(s.v, Math.min(next, s.done ? 1 : 0.985));
      setShown(s.v);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return shown;
}
