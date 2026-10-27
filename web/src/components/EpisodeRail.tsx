import React from "react";
import type { Playlist } from "../api";
import { Ui } from "./ui-icons";

const mmss = (s = 0) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

type Props = {
  playlist: Playlist;
  current: number;
  onPick: (index: number) => void;
  /** Set while the player has finished an episode and is waiting for the next one to be made. */
  waitingForNext?: boolean;
};

/** The course as a playlist: every episode with its state. Ready ones play on tap; the player moves on by itself. */
export const EpisodeRail: React.FC<Props> = ({ playlist, current, onPick, waitingForNext }) => {
  const ready = playlist.episodes.filter((e) => e.status === "ready").length;
  const total = playlist.episodes.length;
  const making = playlist.status === "planning" || playlist.status === "building";
  return (
    <section className="rail" aria-label="Course episodes">
      <div className="rail-head">
        <h2>{playlist.title}</h2>
        <span className="muted">{ready}/{total || playlist.episodes.length} ready{making ? " · more on the way" : ""}</span>
      </div>
      {waitingForNext && <div className="rail-wait" role="status">Next episode is being made, it will start by itself…</div>}
      <ol className="rail-list">
        {playlist.episodes.map((e) => {
          const on = e.index === current;
          const can = e.status === "ready";
          return (
            <li key={e.index}>
              <button type="button" className={`ep ${on ? "on" : ""} ${e.status}`} disabled={!can} onClick={() => onPick(e.index)}
                aria-current={on ? "true" : undefined} title={e.focus}>
                <span className="ep-n">{on ? <Ui name="play" size={14} /> : e.index + 1}</span>
                <span className="ep-t">{e.title}</span>
                <span className="ep-s">
                  {e.status === "ready" ? mmss(e.duration_s) : e.status === "building" ? "making…" : e.status === "failed" ? "failed" : "queued"}
                </span>
                {e.status === "building" && <span className="ep-spin" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
