import React, { useRef } from "react";
import type { Job } from "../types";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { useSmoothProgress } from "./SmoothProgress";

const clamp = (x: number) => Math.min(1, Math.max(0, x));

type Row = { label: string; pct: number; note?: string };

/**
 * Where each stage of the job stands. The backend reports one number, but it spends it in fixed ranges (planning 0-43%, designing the
 * visuals up to 60%, translating, narrating up to 98%), so each stage's own percentage is read off that number. The shown (smoothed)
 * value is used, so every row glides instead of jumping.
 */
function stages(p: number, stage: string, sawTranslate: boolean, done: boolean): Row[] {
  const episode = /^Episode (\d+) of (\d+)/.exec(stage);
  if (episode) {                                           // a course: one row per video, the stage name says what is happening in it
    const i = Number(episode[1]), n = Number(episode[2]);
    return Array.from({ length: n }, (_, k) => ({
      label: `Video ${k + 1}`,
      pct: done || k + 1 < i ? 1 : k + 1 === i ? clamp(p * n - (i - 1)) : 0,
      note: k + 1 === i && !done ? stage.replace(/^Episode \d+ of \d+:\s*/, "") : undefined,
    }));
  }
  const rows: Row[] = [
    { label: "Plan the lesson", pct: done ? 1 : clamp(p / 0.43) },
    { label: "Design the visuals", pct: done ? 1 : clamp((p - 0.43) / 0.17) },
  ];
  if (sawTranslate) rows.push({ label: "Translate", pct: done || p >= 0.72 || /Recording/.test(stage) ? 1 : clamp((p - 0.6) / 0.12) });
  const from = sawTranslate ? 0.72 : 0.62;
  rows.push({ label: "Narrate", pct: done ? 1 : clamp((p - from) / (0.98 - from)) });
  rows.push({ label: "Finish", pct: done ? 1 : clamp((p - 0.98) / 0.02) });
  return rows;
}

/** Job progress as its own card (the "results are pending" card of the design), not inside the video: the total, then each stage with its own percentage. */
export const Pending: React.FC<{ job: Job | null; title?: string }> = ({ job, title = "Your lesson is on its way" }) => {
  const done = job?.status === "done";
  const shown = useSmoothProgress(job?.progress ?? 0, done);
  const pct = Math.round(shown * 100);
  const saw = useRef(false);
  if (job?.stage && /Translat/.test(job.stage)) saw.current = true;
  const rows = stages(shown, job?.stage ?? "", saw.current, done);
  const active = rows.findIndex((r) => r.pct < 1);
  return (
    <section className="pending" role="status" aria-live="polite">
      <div className="pending-title">{title}</div>
      <div className="aura-big dark"><DotNumber value={`${pct}%`} size={44} /></div>
      <div className="slider"><div style={{ width: `${Math.max(pct, 3)}%` }} /></div>
      <div className="muted">{job?.stage || "Queued"}…</div>
      <ul className="stages" aria-label="Stages">
        {rows.map((r, i) => {
          const value = Math.round(r.pct * 100);
          return (
            <li key={r.label} className={r.pct >= 1 ? "done" : i === active ? "on" : ""}>
              <span className="st-dot" aria-hidden>{r.pct >= 1 ? <Glyph name="check" size={13} /> : null}</span>
              <span className="st-name"><b>{r.label}</b>{r.note ? <small>{r.note}</small> : null}</span>
              <span className="st-bar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} aria-label={`${r.label} progress`}><i style={{ width: `${value}%` }} /></span>
              <span className="st-pct">{value}%</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
