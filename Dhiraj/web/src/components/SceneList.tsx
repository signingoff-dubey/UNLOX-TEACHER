import React from "react";
import type { Track } from "../types";

const LABELS: Record<string, string> = {
  title: "Hook", bullets: "Key points", flow: "Steps", cycle: "Cycle", compare: "Compare",
  diagram: "Diagram", quiz: "Quiz", summary: "Recap",
};

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Clickable outline of the lesson; jumps the player to a scene. */
export const SceneList: React.FC<{ track: Track; current: number; onSeek: (seconds: number) => void }> = (
  { track, current, onSeek },
) => (
  <ol className="scenes">
    {track.scenes.map((s, i) => (
      <li key={i}>
        <button className={i === current ? "scene on" : "scene"} onClick={() => onSeek(s.start_s)}
          aria-current={i === current ? "step" : undefined}>
          <span className="time">{mmss(s.start_s)}</span>
          <span className="kind">{LABELS[s.template] ?? s.template}</span>
          <span className="heading">{s.heading}</span>
        </button>
      </li>
    ))}
  </ol>
);
