import { useEffect, useRef, useState } from "react";

/**
 * A progress value that moves continuously. The backend reports progress in steps (and a long step, like the
 * planner, can sit still for seconds), so the shown value glides toward the real one and, when it catches up,
 * creeps ahead slowly inside a small allowance. It never goes backwards and never reaches 100% until `done`.
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
        next += (s.target - next) * Math.min(dt * 2.5, 1) + dt * 0.002;       // glide to the real value
      } else {
        const ceiling = Math.min(s.target + 0.05, 0.985);                      // creep a little past it
        next += Math.max(ceiling - next, 0) * dt * 0.18;
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
