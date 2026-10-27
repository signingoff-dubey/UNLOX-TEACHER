import React from "react";
import type { Track } from "../types";
import { mmss } from "./PlayerControls";

const LABELS: Record<string, string> = {
  title: "Hook", bullets: "Key points", flow: "Steps", cycle: "Cycle", compare: "Compare", diagram: "Diagram",
  quiz: "Quiz", summary: "Recap", graph: "Graph", code: "Code",
};

// Colour per scene kind; scenes still to come are grey.
const TONES: Record<string, string> = {
  title: "#C7D43D", bullets: "#E8C8A3", flow: "#F2ABB8", cycle: "#A3C26A", compare: "#BDD9F1", diagram: "#E29F68",
  quiz: "#F589A3", summary: "#41A642", graph: "#7AA9D6", code: "#8D86C9",
};

/** The lesson's steps above the player: what is playing now, and one segment per scene (as wide as it lasts). Click a segment to jump. */
export const Timeline: React.FC<{ track: Track; current: number; onSeek: (seconds: number) => void }> = ({ track, current, onSeek }) => {
  const now = track.scenes[current];
  const kind = now ? LABELS[now.template] ?? now.template : "";
  return (
    <section className="timeline" aria-label="Lesson steps">
      <div className="tl-head">
        <div className="tl-now" aria-live="polite">
          <span className="tl-kind" style={{ background: TONES[now?.template ?? ""] ?? "#C7C7C7" }}>{kind}</span>
          <b>{now?.heading}</b>
        </div>
        <span className="tl-count">Step {current + 1} of {track.scenes.length}</span>
      </div>
      <ol className="tl-track">
        {track.scenes.map((s, i) => (
          <li key={i} style={{ flexGrow: Math.max(s.duration_s, 1) }}>
            <button type="button" className={i === current ? "tl-seg now" : i < current ? "tl-seg done" : "tl-seg"} onClick={() => onSeek(s.start_s)}
              aria-current={i === current ? "step" : undefined} aria-label={`Step ${i + 1}, ${LABELS[s.template] ?? s.template}: ${s.heading}, ${mmss(s.start_s)}`}
              title={`${i + 1}. ${s.heading} · ${mmss(s.start_s)}`}>
              <i style={i <= current ? { background: TONES[s.template] ?? "#C7C7C7" } : undefined} />
            </button>
          </li>
        ))}
      </ol>
      <div className="tl-times"><span>{mmss(now?.start_s ?? 0)}</span><span>{mmss(track.duration_s)}</span></div>
    </section>
  );
};
