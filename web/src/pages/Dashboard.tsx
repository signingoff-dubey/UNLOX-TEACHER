import React from "react";
import type { LessonSummary, PlaylistSummary } from "../api";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { useRewards } from "../rewards/RewardsContext";
import { BadgeGrid, WeekRow } from "./RewardsPage";

const TONES = ["green", "orange", "pink", "blue"] as const;

type Props = {
  recent: LessonSummary[];
  courses: PlaylistSummary[];
  onOpenLesson: (id: string) => void;
  onOpenCourse: (id: string) => void;
  onNew: () => void;
  onRewards: () => void;
  onLibrary: () => void;
};

/** The dashboard under the prompt box: streak and score first, because a visible streak is what brings a student back tomorrow. */
export const Dashboard: React.FC<Props> = (p) => {
  const { state, setGoal } = useRewards();
  const last = p.recent[0];
  if (!state) return <div className="empty">Loading your progress…</div>;
  const { streak, today, week } = state;
  const goalPct = Math.min(today.xp / today.goal, 1);
  const levelPct = (state.xp - state.level_xp) / Math.max(state.next_xp - state.level_xp, 1);
  const earned = state.badges.filter((b) => b.earned).length;
  const nextBadge = state.badges.filter((b) => !b.earned).sort((a, b) => b.progress / b.goal - a.progress / a.goal)[0];

  return (
    <div className="dash-body">
      <div className="board dash">
        <section className="aura orange" aria-label="Streak">
          <div className="streak-top">
            <div className="aura-title" style={{ margin: 0 }}>Daily streak</div>
            <span className={`flame${streak.current > 0 && streak.today_done ? " lit" : ""}`}><Glyph name="flame" size={26} /></span>
          </div>
          <div className="aura-big left"><DotNumber value={streak.current} size={92} /><span>{streak.current === 1 ? "day in a row" : "days in a row"} · best {streak.best}</span></div>
          <WeekRow week={week} />
          <div className="level-row">
            {streak.at_risk ? <span className="chip lime">Learn today to keep it</span>
              : streak.today_done ? <span className="chip lime">Today counted</span>
              : <span className="chip">Earn {today.qualify} XP to count today</span>}
            {streak.shields > 0 && <span className="chip" title="A shield covers one missed day"><Glyph name="shield" size={14} />{streak.shields} shield{streak.shields > 1 ? "s" : ""}</span>}
          </div>
        </section>

        <section className="aura green" aria-label="Score">
          <div className="aura-title">Your score</div>
          <div className="aura-big left"><DotNumber value={state.xp} size={76} /><span>total XP</span></div>
          <div className="slider" role="progressbar" aria-valuenow={Math.round(levelPct * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Progress to the next level">
            <div style={{ width: `${Math.max(levelPct * 100, 3)}%` }} />
          </div>
          <div className="level-row"><span>Level {state.level}</span><span>{state.next_xp - state.xp} XP to level {state.level + 1}</span></div>
        </section>

        <div className="stack">
          <section className="pending" aria-label="Daily goal">
            <div className="pending-title">Today's goal</div>
            <div className="goal-top"><DotNumber value={today.xp} size={46} /><small>/ {today.goal} XP</small></div>
            <div className="slider" role="progressbar" aria-valuenow={today.xp} aria-valuemin={0} aria-valuemax={today.goal} aria-label="Today's XP">
              <div style={{ width: `${Math.max(goalPct * 100, 3)}%` }} />
            </div>
            <div className="seg" role="radiogroup" aria-label="Daily goal" style={{ marginTop: 6 }}>
              {state.goals.map((g) => (
                <button type="button" key={g} role="radio" aria-checked={today.goal === g} className={today.goal === g ? "on" : ""} onClick={() => void setGoal(g)}>{g} XP</button>
              ))}
            </div>
            <div className="counts">
              <span className="chip">{today.lessons} lesson{today.lessons === 1 ? "" : "s"}</span>
              <span className="chip">{today.quiz} right answer{today.quiz === 1 ? "" : "s"}</span>
              <span className="chip">{today.cards} card{today.cards === 1 ? "" : "s"}</span>
              <span className="chip">{today.ask} question{today.ask === 1 ? "" : "s"}</span>
            </div>
          </section>
          <section className="card white next-up" aria-label="Continue">
            {last ? (
              <>
                <div className="card-title"><Glyph name="play" size={16} />Continue</div>
                <h3>{last.concept}</h3>
                <button type="button" className="primary lime" onClick={() => p.onOpenLesson(last.id)}>Open lesson</button>
              </>
            ) : (
              <>
                <div className="card-title"><Glyph name="sparkle" size={16} />Start here</div>
                <h3>Make your first lesson and your streak begins.</h3>
                <button type="button" className="primary lime" onClick={p.onNew}>Create a lesson</button>
              </>
            )}
          </section>
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <div><h2>Badges</h2><p>{earned} of {state.badges.length} earned{nextBadge ? ` · next: ${nextBadge.name}` : ""}</p></div>
          <button type="button" className="ghost" onClick={p.onRewards}>All rewards<Glyph name="chevron" size={16} /></button>
        </div>
        <BadgeGrid badges={state.badges} limit={8} />
      </section>

      <section className="section">
        <div className="section-head">
          <div><h2>Your lessons</h2><p>Pick up where you left off.</p></div>
          <button type="button" className="ghost" onClick={p.onLibrary}>Library<Glyph name="chevron" size={16} /></button>
        </div>
        {p.recent.length || p.courses.length ? (
          <ul className="tiles">
            {p.courses.slice(0, 2).map((c, i) => (
              <li key={c.id}>
                <button type="button" className="tile" onClick={() => p.onOpenCourse(c.id)}>
                  <div className={`thumb ${TONES[(i + 1) % 4]}`}><Glyph name="library" size={30} /></div>
                  <span className="tile-name">{c.title}</span>
                  <div className="tile-top"><span>Course</span><span className="chip">{c.ready}/{c.episodes} videos</span></div>
                </button>
              </li>
            ))}
            {p.recent.slice(0, 6).map((l, i) => (
              <li key={l.id}>
                <button type="button" className="tile" onClick={() => p.onOpenLesson(l.id)}>
                  <div className={`thumb ${TONES[i % 4]}`}><Glyph name="play" size={30} /></div>
                  <span className="tile-name">{l.concept}</span>
                  <div className="tile-top"><span>{l.languages.length} language{l.languages.length === 1 ? "" : "s"}</span>{l.videos.length > 0 && <span className="chip">MP4</span>}</div>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty">No lessons yet. Type a topic in Create and press Create lesson.</div>
        )}
      </section>
    </div>
  );
};
