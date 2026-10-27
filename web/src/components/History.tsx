import React from "react";
import type { LessonSummary } from "../api";

/** Previously made lessons. Doubles as a demo safety net: replay one if live generation fails. */
export const History: React.FC<{ items: LessonSummary[]; activeId?: string; onOpen: (id: string) => void }> = (
  { items, activeId, onOpen },
) => {
  if (!items.length) return null;
  return (
    <div className="history">
      <div className="label">Recent lessons</div>
      <ul>
        {items.map((l) => (
          <li key={l.id}>
            <button className={l.id === activeId ? "past on" : "past"} onClick={() => onOpen(l.id)}>
              <span className="concept">{l.concept}</span>
              <span className="muted">
                {l.languages.length} languages{l.videos.length ? ` · ${l.videos.length} MP4` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
