import React, { useEffect, useRef, useState } from "react";
import { useRewards } from "../rewards/RewardsContext";
import type { StudioData } from "./types";

const LEAVE_MS = 300;

/**
 * One card at a time. The front is the question; "View answer" turns the card over (the back is the answer), then you say
 * whether you knew it. Cards you were unsure about come back in a second round.
 */
export const Flashcards: React.FC<{ data: StudioData["flashcards"]; lessonId: string }> = ({ data, lessonId }) => {
  const { award } = useRewards();
  const all = data.cards;
  const [order, setOrder] = useState(() => all.map((_, i) => i));
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [leaving, setLeaving] = useState<"left" | "right" | null>(null);
  const [verdict, setVerdict] = useState<Record<number, "known" | "learning">>({});
  const [round, setRound] = useState(1);
  const timer = useRef<number>();
  const done = pos >= order.length;
  const card = all[order[pos]];
  const knownCount = order.filter((i) => verdict[i] === "known").length;

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const rate = (know: boolean) => {
    if (leaving || !flipped) return;
    setVerdict((v) => ({ ...v, [order[pos]]: know ? "known" : "learning" }));
    if (know) award({ type: "card_known", lesson_id: lessonId, card_id: String(order[pos]) });
    setLeaving(know ? "right" : "left");
    timer.current = window.setTimeout(() => { setLeaving(null); setFlipped(false); setPos((p) => p + 1); }, LEAVE_MS);
  };
  const restart = (ids: number[], keep: boolean) => {
    if (!keep) setVerdict({});
    setOrder(ids); setPos(0); setFlipped(false); setLeaving(null); setRound((r) => (keep ? r + 1 : 1));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (done || el.tagName === "INPUT") return;
      if ((e.key === " " || e.key === "Enter") && el.tagName !== "BUTTON") { e.preventDefault(); if (!flipped) setFlipped(true); }
      else if (e.key === "ArrowRight") rate(true);
      else if (e.key === "ArrowLeft") rate(false);
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") setFlipped((f) => !f);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (done) {
    const missed = order.filter((i) => verdict[i] !== "known");
    const pct = Math.round((knownCount / order.length) * 100);
    return (
      <div className="fc-done">
        <div className="fc-ring" style={{ ["--pct" as string]: `${pct}%` }} role="img" aria-label={`${knownCount} of ${order.length} known`}>
          <b>{knownCount}</b><span>of {order.length}</span>
        </div>
        <h3>{missed.length === 0 ? "Every card known" : `${missed.length} to go over again`}</h3>
        <p className="muted">{missed.length === 0 ? "Shuffle the deck for another pass, or take the quiz." : "Only the cards you were unsure about come back."}</p>
        <div className="fc-actions center">
          {missed.length > 0 && <button type="button" className="fc-btn primary" onClick={() => restart(missed, true)}>Review {missed.length} {missed.length === 1 ? "card" : "cards"}</button>}
          <button type="button" className="fc-btn" onClick={() => restart([...all.keys()].sort(() => Math.random() - 0.5), false)}>Shuffle and restart</button>
        </div>
      </div>
    );
  }

  const left = order.length - pos - 1;
  return (
    <div className="fc">
      <div className="fc-top">
        <div className="fc-track" role="progressbar" aria-valuemin={0} aria-valuemax={order.length} aria-valuenow={pos} aria-label="Progress through the deck">
          {order.map((id, k) => <i key={k} className={k === pos ? "now" : verdict[id] && k < pos ? verdict[id] : ""} />)}
        </div>
        <div className="fc-meta">
          <span>Card <b>{pos + 1}</b> of {order.length}{round > 1 ? ` · round ${round}` : ""}</span>
          <button type="button" className="fc-link" onClick={() => restart([...order].sort(() => Math.random() - 0.5), true)}>Shuffle</button>
        </div>
      </div>

      <div className="fc-stage">
        {left > 1 && <div className="fc-under u2" aria-hidden />}
        {left > 0 && <div className="fc-under u1" aria-hidden />}
        <div key={`${round}-${pos}`} className={`fc-card${flipped ? " flipped" : ""}${leaving ? ` out-${leaving}` : ""}`}>
          <div className="fc-inner">
            <section className="fc-face front" aria-hidden={flipped} aria-label="Question">
              <span className="fc-label">Question</span>
              <p>{card.front}</p>
              <span className="fc-idx" aria-hidden>{String(pos + 1).padStart(2, "0")}</span>
            </section>
            <section className="fc-face back" aria-hidden={!flipped} aria-label="Answer">
              <span className="fc-label">Answer</span>
              <p>{card.back}</p>
              <span className="fc-idx" aria-hidden>{String(pos + 1).padStart(2, "0")}</span>
            </section>
          </div>
        </div>
      </div>

      <div className="fc-actions" aria-live="polite">
        {!flipped ? (
          <button type="button" className="fc-btn primary wide" autoFocus onClick={() => setFlipped(true)}>
            View answer <kbd>Space</kbd>
          </button>
        ) : (
          <>
            <button type="button" className="fc-btn learn" onClick={() => rate(false)}><kbd>←</kbd> Still learning</button>
            <button type="button" className="fc-btn know" autoFocus onClick={() => rate(true)}>I know it <kbd>→</kbd></button>
          </>
        )}
      </div>
    </div>
  );
};
