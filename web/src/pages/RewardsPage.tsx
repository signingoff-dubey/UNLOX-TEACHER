import React from "react";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { Ring } from "../ds/Ring";
import { Stat } from "../ds/Stat";
import { useRewards, type Badge, type RewardState } from "../rewards/RewardsContext";

const DAY = ["S", "M", "T", "W", "T", "F", "S"];

export const WeekRow: React.FC<{ week: RewardState["week"] }> = ({ week }) => (
  <div className="week" role="list" aria-label="This week">
    {week.map((d) => (
      <div key={d.day} role="listitem" className={`wk${d.done ? " done" : ""}${d.today ? " today" : ""}`} aria-label={`${d.day}: ${d.done ? "counted" : "not yet"}`}>
        <i>{d.done ? <Glyph name="check" size={16} /> : null}</i>
        <span>{DAY[new Date(`${d.day}T12:00:00`).getDay()]}</span>
      </div>
    ))}
  </div>
);

export const BadgeGrid: React.FC<{ badges: Badge[]; limit?: number }> = ({ badges, limit }) => {
  const sorted = [...badges].sort((a, b) => Number(!!b.earned) - Number(!!a.earned) || b.progress / b.goal - a.progress / a.goal);
  return (
    <ul className="badges">
      {sorted.slice(0, limit ?? sorted.length).map((b) => (
        <li key={b.id} className={b.earned ? "badge" : "badge locked"}>
          <span className="medal"><Glyph name={b.earned ? b.icon : "lock"} size={24} /></span>
          <b>{b.name}</b>
          <span>{b.desc}</span>
          {!b.earned && (
            <>
              <div className="slider sm" role="progressbar" aria-valuenow={b.progress} aria-valuemax={b.goal} aria-label={`${b.name} progress`}>
                <div style={{ width: `${(b.progress / b.goal) * 100}%` }} />
              </div>
              <span>{b.progress} / {b.goal}</span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
};

/** Everything about the learner's progress: level, streak, goal, totals and every badge. */
export const RewardsPage: React.FC = () => {
  const { state, setGoal } = useRewards();
  if (!state) return <div className="main"><div className="empty">Loading your progress…</div></div>;
  const levelPct = (state.xp - state.level_xp) / Math.max(state.next_xp - state.level_xp, 1);
  const earned = state.badges.filter((b) => b.earned).length;
  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">Rewards</div>
          <h1>Every lesson you finish moves you forward.</h1>
          <div className="stats">
            <Stat value={state.xp} label="Score" accent />
            <Stat value={state.streak.best} label="Best streak" />
            <Stat value={state.totals.lessons} label="Lessons finished" />
            <Stat value={state.totals.quiz} label="Right answers" />
          </div>
        </div>
      </header>

      <div className="board">
        <section className="aura green" style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 28, alignItems: "center" }} aria-label="Level">
          <Ring value={levelPct} size={150} stroke={10} color="#1c1c1c" track="rgba(28,28,28,0.14)" label={`Level ${state.level}, ${Math.round(levelPct * 100)} percent to the next`}>
            <div><DotNumber value={state.level} size={52} /><div style={{ fontSize: 13, marginTop: 6 }}>level</div></div>
          </Ring>
          <div style={{ position: "relative" }}>
            <div className="aura-title" style={{ textAlign: "left" }}>Level {state.level}</div>
            <p style={{ textAlign: "left" }}>
              {state.next_xp - state.xp} XP to reach level {state.level + 1}. XP is paid for finishing lessons, right answers, flashcards you know and good questions to the tutor.
            </p>
          </div>
        </section>
        <div className="stack">
          <section className="pending" aria-label="Daily goal">
            <div className="pending-title">Daily goal</div>
            <div className="goal-top"><DotNumber value={state.today.xp} size={40} /><small>/ {state.today.goal} XP today</small></div>
            <div className="seg" role="radiogroup" aria-label="Daily goal">
              {state.goals.map((g) => (
                <button type="button" key={g} role="radio" aria-checked={state.today.goal === g} className={state.today.goal === g ? "on" : ""} onClick={() => void setGoal(g)}>{g} XP</button>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 12 }}>
              A day counts for your streak at {state.today.qualify} XP. Finishing one lesson is enough. A streak shield (one every 7 days, up to 2) covers a missed day.
            </p>
          </section>
        </div>
      </div>

      <section className="aura orange" aria-label="This week">
        <div className="streak-top">
          <div className="aura-title" style={{ margin: 0 }}>This week</div>
          <span className="chip"><Glyph name="shield" size={14} />{state.streak.shields} shield{state.streak.shields === 1 ? "" : "s"}</span>
        </div>
        <div className="aura-big left" style={{ margin: "10px 0 18px" }}><DotNumber value={state.streak.current} size={64} /><span>day streak · best {state.streak.best}</span></div>
        <WeekRow week={state.week} />
      </section>

      <section className="section">
        <div className="section-head"><div><h2>Badges</h2><p>{earned} of {state.badges.length} earned</p></div></div>
        <BadgeGrid badges={state.badges} />
      </section>
    </main>
  );
};
