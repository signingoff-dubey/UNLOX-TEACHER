import React from "react";
import type { Track } from "../types";
import { Glyph } from "../ds/Glyph";
import { mmss } from "./PlayerControls";

const LABELS: Record<string, string> = {
  title: "Hook", bullets: "Key points", flow: "Steps", cycle: "Cycle", compare: "Compare", diagram: "Diagram",
  quiz: "Quiz", summary: "Recap", graph: "Graph", code: "Code",
};

// Pastel dot colour per scene kind.
const TONES: Record<string, string> = {
  title: "#C7D43D", bullets: "#E8C8A3", flow: "#F2ABB8", cycle: "#A3C26A", compare: "#BDD9F1", diagram: "#E29F68",
  quiz: "#F589A3", summary: "#41A642", graph: "#7AA9D6", code: "#8D86C9",
};

/** Scene strip: one dotted column per scene, sized by its length. Click to jump the player there. */
export const Timeline: React.FC<{ track: Track; current: number; onSeek: (seconds: number) => void }> = ({ track, current, onSeek }) => {
  const now = track.scenes[current];
  return (
    <div className="timeline">
      <span className="tl-edge">0:00</span>
      <ol className="tl-track">
        {track.scenes.map((s, i) => {
          const dots = Math.max(1, Math.min(s.items.length || 1, 5));
          return (
            <li key={i} style={{ flexGrow: Math.max(s.duration_s, 1) }}>
              <button type="button" className={i === current ? "tl-scene on" : "tl-scene"} onClick={() => onSeek(s.start_s)}
                aria-current={i === current ? "step" : undefined}
                aria-label={`${mmss(s.start_s)} ${LABELS[s.template] ?? s.template}: ${s.heading}`}
                title={`${LABELS[s.template] ?? s.template} · ${s.heading}`}>
                {Array.from({ length: dots }, (_, k) => <i key={k} style={{ background: TONES[s.template] ?? "#C7C7C7" }} />)}
              </button>
            </li>
          );
        })}
      </ol>
      <span className="tl-edge">{mmss(track.duration_s)}</span>
      {now && (
        <div className="tl-now" aria-live="polite">
          <Glyph name="trend" size={16} />
          <div>
            <b>{now.heading}</b>
            <span>{LABELS[now.template] ?? now.template} · scene {current + 1} of {track.scenes.length} · {mmss(now.start_s)}</span>
          </div>
        </div>
      )}
    </div>
  );
};
