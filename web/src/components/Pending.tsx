import React from "react";
import type { Job } from "../types";
import { DotNumber } from "../ds/DotNumber";
import { useSmoothProgress } from "./SmoothProgress";

/** Job progress as its own card (the "results are pending" card of the design), not inside the video. */
export const Pending: React.FC<{ job: Job | null; title?: string }> = ({ job, title = "Your lesson is on its way" }) => {
  const shown = useSmoothProgress(job?.progress ?? 0, job?.status === "done");
  const pct = Math.round(shown * 100);
  return (
    <section className="pending" role="status" aria-live="polite">
      <div className="pending-title">{title}</div>
      <div className="aura-big dark"><DotNumber value={`${pct}%`} size={44} /></div>
      <div className="slider"><div style={{ width: `${Math.max(pct, 3)}%` }} /></div>
      <div className="muted">{job?.stage || "Queued"}…</div>
    </section>
  );
};
