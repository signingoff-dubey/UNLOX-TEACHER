import React from "react";
import type { LessonSummary, PlaylistSummary } from "../api";
import { preloadMetaverse } from "../components/MetaverseLayer";
import { StatusPanel } from "../components/StatusPanel";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { useRewards } from "../rewards/RewardsContext";
import { WeekRow } from "../pages/RewardsPage";
import type { HomeworkMeta } from "../pages/HomeworkPage";

export type SidebarProps = {
  screen: "home" | "lesson" | "library" | "rewards" | "homework";
  homework: HomeworkMeta[];
  onOpenHomework: (id: string) => void;
  recent: LessonSummary[];
  courses: PlaylistSummary[];
  activeId?: string;
  onOpenLesson: (id: string) => void;
  onOpenCourse: (id: string) => void;
  onHome: () => void;
  onLibrary: () => void;
  onRewards: () => void;
  onMetaverse: () => void;
  onBaseChange: () => void;
};

/** The left column: where to go, then the student's awards (streak, score, level, today's goal, latest badges), then recent work. */
export const Sidebar: React.FC<SidebarProps> = (p) => {
  const { state } = useRewards();
  const levelPct = state ? (state.xp - state.level_xp) / Math.max(state.next_xp - state.level_xp, 1) : 0;
  const goalPct = state ? Math.min(state.today.xp / state.today.goal, 1) : 0;
  const earned = state ? state.badges.filter((b) => b.earned) : [];

  return (
    <aside className={p.screen === "lesson" ? "side compact" : "side"} aria-label="Chanakya">
      <button type="button" className="brand" onClick={p.onHome} aria-label="Chanakya home">
        <span className="brand-mark" aria-hidden><i /></span><span className="lbl">chanakya</span>
      </button>

      <nav className="side-nav" aria-label="Pages">
        <button type="button" className={p.screen === "home" ? "on" : ""} aria-current={p.screen === "home" ? "page" : undefined} onClick={p.onHome}><Glyph name="home" size={18} /><span className="lbl">Home</span></button>
        <button type="button" className={p.screen === "library" ? "on" : ""} aria-current={p.screen === "library" ? "page" : undefined} onClick={p.onLibrary}><Glyph name="library" size={18} /><span className="lbl">Library</span></button>
        <button type="button" className={p.screen === "rewards" ? "on" : ""} aria-current={p.screen === "rewards" ? "page" : undefined} onClick={p.onRewards}><Glyph name="trophy" size={18} /><span className="lbl">Rewards</span></button>
        <button type="button" onClick={p.onMetaverse} onPointerEnter={preloadMetaverse} onFocus={preloadMetaverse}><Glyph name="cube" size={18} /><span className="lbl">Learnverse</span></button>
      </nav>

      {state && (
        <div className="awards" aria-label="Your awards">
          <div className="divider"><span>Your awards</span></div>

          <button type="button" className="aura orange mini" onClick={p.onRewards} aria-label={`${state.streak.current} day streak. Open rewards`}>
            <div className="mini-top">
              <span className="aura-title">Daily streak</span>
              <span className={`flame sm${state.streak.current > 0 && state.streak.today_done ? " lit" : ""}`}><Glyph name="flame" size={20} /></span>
            </div>
            <div className="aura-big left"><DotNumber value={state.streak.current} size={56} /><span>{state.streak.current === 1 ? "day" : "days"} · best {state.streak.best}</span></div>
            <WeekRow week={state.week} />
          </button>

          <button type="button" className="aura green mini" onClick={p.onRewards} aria-label={`${state.xp} XP, level ${state.level}. Open rewards`}>
            <div className="mini-top"><span className="aura-title">Score</span><span className="chip">Lv {state.level}</span></div>
            <div className="aura-big left"><DotNumber value={state.xp} size={48} /><span>XP</span></div>
            <div className="slider" role="progressbar" aria-valuenow={Math.round(levelPct * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Progress to the next level">
              <div style={{ width: `${Math.max(levelPct * 100, 3)}%` }} />
            </div>
            <div className="level-row"><span>{state.next_xp - state.xp} XP to level {state.level + 1}</span></div>
          </button>

          <div className="goal-mini">
            <div><b>Today's goal</b><span>{state.today.xp} / {state.today.goal} XP</span></div>
            <div className="slider" role="progressbar" aria-valuenow={state.today.xp} aria-valuemin={0} aria-valuemax={state.today.goal} aria-label="Today's XP">
              <div style={{ width: `${Math.max(goalPct * 100, 3)}%` }} />
            </div>
          </div>

          <div className="medal-row" aria-label={`${earned.length} of ${state.badges.length} badges earned`}>
            {earned.slice(-5).map((b) => (
              <span key={b.id} className="medal sm" title={b.name}><Glyph name={b.icon} size={18} /></span>
            ))}
            {!earned.length && <span className="muted">Badges you earn show up here.</span>}
            <button type="button" className="ghost" onClick={p.onRewards}>{earned.length}/{state.badges.length}<Glyph name="chevron" size={14} /></button>
          </div>
        </div>
      )}

      {p.homework.length > 0 && (
        <>
          <div className="divider"><span>Homework answers</span></div>
          <ul className="rows">
            {p.homework.slice(0, 4).map((h) => (
              <li key={h.id}>
                <button type="button" className="row" onClick={() => p.onOpenHomework(h.id)}>
                  <Glyph name="book" /><span>{h.title}</span>
                  <span className={h.status === "done" ? "chip lime" : "chip"}>{h.status === "done" ? "Ready" : h.status === "error" ? "Failed" : h.total ? `${h.done}/${h.total}` : "Reading"}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {(p.courses.length > 0 || p.recent.length > 0) && (
        <>
          <div className="divider"><span>Recent</span></div>
          <ul className="rows">
            {p.courses.slice(0, 3).map((c) => (
              <li key={c.id}>
                <button type="button" className={`row${`c-${c.id}` === p.activeId ? " on" : ""}`} onClick={() => p.onOpenCourse(c.id)}>
                  <Glyph name="library" /><span>{c.title}</span><span className="chip">{c.ready}/{c.episodes}</span>
                </button>
              </li>
            ))}
            {p.recent.slice(0, 5).map((l) => (
              <li key={l.id}>
                <button type="button" className={l.id === p.activeId ? "row on" : "row"} onClick={() => p.onOpenLesson(l.id)}>
                  <Glyph name="folder" /><span>{l.concept}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <StatusPanel onBaseChange={p.onBaseChange} />
    </aside>
  );
};
