import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";

export type Badge = { id: string; name: string; desc: string; icon: string; goal: number; earned: number | null; progress: number };
export type RewardState = {
  name: string; xp: number; level: number; level_xp: number; next_xp: number;
  streak: { current: number; best: number; shields: number; today_done: boolean; at_risk: boolean };
  today: { xp: number; goal: number; lessons: number; quiz: number; cards: number; ask: number; cap: number; qualify: number };
  week: { day: string; xp: number; done: boolean; today: boolean }[];
  badges: Badge[];
  totals: { lessons: number; quiz: number; cards: number; questions: number; best_run: number };
  goals: number[];
};

export type RewardEvent =
  | { type: "lesson_complete"; lesson_id: string; lang: string }
  | { type: "course_complete"; course_id: string }
  | { type: "quiz_correct"; first_try: boolean; lesson_id?: string; card_id?: string }
  | { type: "quiz_wrong" }
  | { type: "card_known"; lesson_id: string; card_id: string }
  | { type: "tutor_question" }
  | { type: "study_tool_open"; lesson_id: string; tool: string }
  | { type: "metaverse_points"; points: number };

type AwardResult = {
  gained: number; level_up: boolean; level: number; streak_changed: boolean;
  new_badges: { id: string; name: string; desc: string; icon: string }[]; state: RewardState;
};

type Toast = { id: number; kind: "xp" | "streak" | "level"; text: string; sub?: string; xp?: number };
type Ctx = { state: RewardState | null; award: (ev: RewardEvent) => void; setGoal: (goal: number) => Promise<void>; refresh: () => void };

const RewardsCtx = createContext<Ctx>({ state: null, award: () => undefined, setGoal: async () => undefined, refresh: () => undefined });
export const useRewards = () => useContext(RewardsCtx);

/** The learner's own calendar day (yyyy-mm-dd): the streak is about their day, not the server's. */
export const localDay = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const LABELS: Record<RewardEvent["type"], string> = {
  lesson_complete: "Lesson finished", course_complete: "Course finished", quiz_correct: "Right answer", quiz_wrong: "",
  card_known: "Card known", tutor_question: "Good question", study_tool_open: "Study tool", metaverse_points: "Metaverse",
};

export const RewardsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<RewardState | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [badges, setBadges] = useState<AwardResult["new_badges"]>([]);
  const seq = useRef(0);

  const refresh = useCallback(() => {
    api<RewardState>(`/api/rewards?day=${localDay()}`).then(setState).catch(() => undefined);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = ++seq.current;
    setToasts((x) => [...x.slice(-2), { ...t, id }]);
    window.setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), 3600);
  }, []);

  const award = useCallback((ev: RewardEvent) => {
    api<AwardResult>("/api/rewards/event", { ...ev, day: localDay() })
      .then((r) => {
        setState(r.state);
        if (r.gained > 0) push({ kind: "xp", text: LABELS[ev.type], xp: r.gained });
        if (r.streak_changed && r.state.streak.current > 0) push({ kind: "streak", text: `${r.state.streak.current}-day streak`, sub: "Keep it going tomorrow" });
        if (r.level_up) push({ kind: "level", text: `Level ${r.level}`, sub: "You levelled up" });
        if (r.new_badges.length) setBadges((b) => [...b, ...r.new_badges]);
      })
      .catch(() => undefined);                    // rewards must never get in the way of learning
  }, [push]);

  const setGoal = useCallback(async (goal: number) => {
    setState(await api<RewardState>("/api/rewards/goal", { goal }));
  }, []);

  const value = useMemo(() => ({ state, award, setGoal, refresh }), [state, award, setGoal, refresh]);
  const badge = badges[0];
  return (
    <RewardsCtx.Provider value={value}>
      {children}
      {createPortal(
        <>
          <div className="toasts" aria-live="polite">
            {toasts.map((t) => (
              <div key={t.id} className={`toast ${t.kind}`}>
                {t.kind === "xp" ? <><DotNumber value={`+${t.xp}`} size={22} /><span>XP</span></> : <Glyph name={t.kind === "streak" ? "flame" : "star"} size={20} />}
                <div><b>{t.text}</b>{t.sub && <small>{t.sub}</small>}</div>
              </div>
            ))}
          </div>
          {badge && <BadgeModal badge={badge} onClose={() => setBadges((b) => b.slice(1))} />}
        </>,
        document.body,
      )}
    </RewardsCtx.Provider>
  );
};

const BadgeModal: React.FC<{ badge: AwardResult["new_badges"][number]; onClose: () => void }> = ({ badge, onClose }) => {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    btn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="badge-pop aura pink" role="dialog" aria-modal="true" aria-labelledby="badge-h">
        <div className="badge-burst" aria-hidden>{Array.from({ length: 10 }, (_, i) => <i key={i} style={{ ["--a" as string]: `${i * 36}deg` }} />)}</div>
        <div className="badge-medal"><Glyph name={badge.icon} size={44} /></div>
        <div className="aura-title">Badge unlocked</div>
        <h2 id="badge-h">{badge.name}</h2>
        <p>{badge.desc}</p>
        <button ref={btn} type="button" className="glass-btn" onClick={onClose}>Nice</button>
      </div>
    </div>
  );
};
