import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Glyph } from "../ds/Glyph";
import { Stat } from "../ds/Stat";
import { localDay, useRewards } from "../rewards/RewardsContext";

type Card = { id: string; lesson_id: string; kind: "flashcard" | "quiz"; topic: string; front: string; back: string };
type Due = { day: string; due: number; cards: Card[] };
type Stats = { total: number; due: number; learned: number; new: number; reviewed_today: number };

const RATINGS: [number, string, string][] = [[1, "Again", "I forgot"], [3, "Hard", "With effort"], [4, "Good", "I knew it"], [5, "Easy", "No problem"]];

/** The card on the dashboard: how many are due today, and a way in. */
export const ReviewCard: React.FC<{ onReview: () => void }> = ({ onReview }) => {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => { api<Stats>(`/api/review/stats?day=${localDay()}`).then(setS).catch(() => setS(null)); }, []);
  if (!s || s.total === 0) return null;
  return (
    <section className="card white next-up review-card" aria-label="Review">
      <div className="card-title"><Glyph name="target" size={16} />Review today</div>
      <h3>{s.due > 0 ? `${s.due} card${s.due === 1 ? "" : "s"} to review` : "You are all caught up"}</h3>
      <p className="muted">{s.learned} learned for good · {s.total} cards in all</p>
      <button type="button" className="primary lime" onClick={onReview} disabled={s.due === 0}>{s.due > 0 ? "Start review" : "Nothing due"}</button>
    </section>
  );
};

/** Spaced repetition: the flashcards and quiz questions of every lesson, scheduled so each comes back just before it is forgotten (SM-2). */
export const ReviewPage: React.FC = () => {
  const { award } = useRewards();
  const [due, setDue] = useState<Due | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [i, setI] = useState(0);
  const [shown, setShown] = useState(false);
  const [again, setAgain] = useState<Card[]>([]);
  const [error, setError] = useState("");
  const [known, setKnown] = useState(0);

  const load = useCallback(() => {
    api<Due>(`/api/review/due?day=${localDay()}&limit=30`).then((d) => { setDue(d); setI(0); setShown(false); setAgain([]); setKnown(0); }).catch((e: Error) => setError(e.message));
    api<Stats>(`/api/review/stats?day=${localDay()}`).then(setStats).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  const queue = due ? [...due.cards, ...again] : [];
  const card = queue[i];

  const rate = async (quality: number) => {
    if (!card) return;
    try {
      await api("/api/review/answer", { card_id: card.id, quality, day: localDay() });
    } catch (e) { setError((e as Error).message); return; }
    if (quality >= 3) { setKnown((k) => k + 1); award({ type: "card_known", lesson_id: card.lesson_id, card_id: `srs-${card.id}` }); }
    else setAgain((a) => [...a, card]);                      // a forgotten card comes round again in this session
    setShown(false);
    setI((n) => n + 1);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!card) return;
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); setShown(true); }
    if (shown && "1234".includes(e.key) && e.key) rate(RATINGS[Number(e.key) - 1][0]);
  };

  return (
    <main className="main" onKeyDown={onKey}>
      <header className="hero">
        <div>
          <div className="eyebrow">Review</div>
          <h1>Remember it for good.</h1>
          <div className="stats">
            <Stat value={due?.due ?? 0} label="Due today" accent />
            <Stat value={stats?.learned ?? 0} label="Learned for good" />
            <Stat value={stats?.total ?? 0} label="Cards in all" />
            <Stat value={stats?.reviewed_today ?? 0} label="Reviewed today" />
          </div>
        </div>
      </header>
      {error && <div className="notice bad" role="alert">{error}</div>}
      {!due ? <div className="empty">Loading your cards…</div> : due.cards.length === 0 ? (
        <div className="empty">
          <h3>{stats && stats.total > 0 ? "You are all caught up." : "No cards yet."}</h3>
          <p className="muted">{stats && stats.total > 0 ? "Come back tomorrow: each card returns just before you would forget it." : "Make a lesson and open its flashcards or quiz. Every card goes into your review."}</p>
        </div>
      ) : !card ? (
        <div className="empty rv-done">
          <h3>{known} remembered</h3>
          <p className="muted">That is today's review done. The cards you knew return in a few days, the ones you forgot return tomorrow.</p>
          <button type="button" className="primary lime" onClick={load}>Check for more</button>
        </div>
      ) : (
        <section className="rv" aria-label="Card">
          <div className="rv-count">{Math.min(i + 1, queue.length)} of {queue.length}{again.length ? ` · ${again.length} to try again` : ""}</div>
          <div className={`rv-card${shown ? " flipped" : ""}`}>
            <div className="rv-kind">{card.kind === "quiz" ? "Question" : "Flashcard"}{card.topic ? ` · ${card.topic}` : ""}</div>
            <div className="rv-front">{card.front}</div>
            {shown && <div className="rv-back" aria-live="polite">{card.back}</div>}
          </div>
          {!shown ? (
            <button type="button" className="primary lime rv-show" onClick={() => setShown(true)}>Show answer <kbd>space</kbd></button>
          ) : (
            <div className="rv-rate" role="group" aria-label="How well did you remember it?">
              {RATINGS.map(([q, label, hint], n) => (
                <button type="button" key={label} className={`rv-btn q${q}`} onClick={() => rate(q)}><b>{label}</b><span>{hint}</span><kbd>{n + 1}</kbd></button>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
};
