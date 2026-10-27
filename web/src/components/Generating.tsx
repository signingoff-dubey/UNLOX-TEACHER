import React, { useEffect, useState } from "react";
import type { Job } from "../types";
import { useSmoothProgress } from "./SmoothProgress";

const STEPS = [
  { match: /plan/i, label: "Planning the lesson" },
  { match: /check/i, label: "Checking it" },
  { match: /translat|prepar/i, label: "Writing each language" },
  { match: /record|voice|narrat/i, label: "Recording the voice" },
  { match: /ready|done/i, label: "Timing scenes to the audio" },
];

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Fills the video area while the lesson is being made, so the screen layout never changes when it is ready. */
export const Generating: React.FC<{ concept: string; job: Job | null; languages: string[] }> = ({ concept, job, languages }) => {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const value = useSmoothProgress(job?.progress ?? 0, job?.status === "done");
  const stage = job?.stage ?? "Starting";
  const at = Math.max(0, STEPS.findIndex((s) => s.match.test(stage)));

  return (
    <div className="gen" role="status" aria-live="polite">
      <div className="empty-art" aria-hidden><span /><span /><span /></div>
      <div className="muted">Making your lesson</div>
      <h2 className="gen-title">{concept}</h2>
      <div className="gen-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}>
        <div style={{ transform: `scaleX(${value})` }} />
      </div>
      <div className="gen-meta">
        <b>{stage}…</b>
        <span className="muted">{Math.floor(value * 100)}% · {mmss(secs)}</span>
      </div>
      <ol className="gen-steps">
        {STEPS.map((s, i) => (
          <li key={s.label} className={i < at ? "done" : i === at ? "now" : ""}>
            <span className="tick" aria-hidden>{i < at ? "✓" : i + 1}</span>{s.label}
          </li>
        ))}
      </ol>
      <div className="muted gen-foot">{languages.length} language{languages.length === 1 ? "" : "s"} · all on this laptop, no internet needed</div>
    </div>
  );
};
