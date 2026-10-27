import React, { useEffect, useState } from "react";
import type { Job } from "../types";

const STEPS = [
  { match: /plan/i, label: "Planning the lesson" },
  { match: /translat/i, label: "Translating" },
  { match: /voice|narrat|speak/i, label: "Recording the voice" },
  { match: /caption|time|ready|done/i, label: "Timing scenes to the audio" },
];

/** Screen 2: shown while the backend builds the lesson. */
export const Creating: React.FC<{ concept: string; job: Job | null; languages: string[]; onCancel: () => void }> = (
  { concept, job, languages, onCancel },
) => {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const stage = job?.stage ?? "Starting";
  const at = Math.max(0, STEPS.findIndex((s) => s.match.test(stage)));
  const pct = Math.round((job?.progress ?? 0) * 100);

  return (
    <div className="screen creating">
      <div className="create-card" role="status" aria-live="polite">
        <div className="empty-art" aria-hidden><span /><span /><span /></div>
        <div className="muted">Making your lesson</div>
        <h1>{concept}</h1>
        <div className="bar big"><div style={{ transform: `scaleX(${job?.progress ?? 0.03})` }} /></div>
        <div className="create-meta"><b>{stage}…</b><span className="muted">{pct}% · {secs}s</span></div>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.label} className={i < at ? "done" : i === at ? "now" : ""}>
              <span className="tick" aria-hidden>{i < at ? "✓" : i + 1}</span>{s.label}
            </li>
          ))}
        </ol>
        <div className="muted small-note">English{languages.length ? ` + ${languages.length} language${languages.length > 1 ? "s" : ""}` : ""}. All on this laptop, no internet needed.</div>
        <button type="button" className="ghost" onClick={onCancel}>Back</button>
      </div>
    </div>
  );
};
