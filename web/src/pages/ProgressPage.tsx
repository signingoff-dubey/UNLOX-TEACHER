import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { Stat } from "../ds/Stat";
import { localDay, useRewards } from "../rewards/RewardsContext";
import { WeekRow } from "./RewardsPage";

type Day = { day: string; xp: number; lessons: number; quiz: number; cards: number; ask: number };
const RANGES = [["week", "Week", 7], ["month", "Month", 30], ["year", "Year", 365]] as const;
const WEEKS = 18;                         // the heatmap shows the last 18 weeks, like the phone app
const WD = ["S", "M", "T", "W", "T", "F", "S"];
const MONTH = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

const sum = (days: Day[], k: keyof Omit<Day, "day">) => days.reduce((n, d) => n + d[k], 0);

/** How the learner is doing over time: the streak heatmap, totals for the week, month or year, and XP per day. */
export const ProgressPage: React.FC = () => {
  const { state } = useRewards();
  const [days, setDays] = useState<Day[] | null>(null);
  const [range, setRange] = useState<(typeof RANGES)[number][0]>("week");
  useEffect(() => { api<Day[]>(`/api/rewards/history?day=${localDay()}&days=365`).then(setDays).catch(() => setDays([])); }, [state?.xp]);

  const span = RANGES.find((r) => r[0] === range)![2];
  const window = useMemo(() => (days ?? []).slice(-span), [days, span]);
  const bars = useMemo(() => {
    if (!days) return [];
    if (range === "week") return window.map((d) => ({ label: WD[new Date(`${d.day}T12:00:00`).getDay()], value: d.xp }));
    if (range === "month") return window.map((d, i) => ({ label: i % 5 === 0 ? d.day.slice(8) : "", value: d.xp }));
    const byMonth = new Map<string, number>();
    for (const d of window) byMonth.set(d.day.slice(0, 7), (byMonth.get(d.day.slice(0, 7)) ?? 0) + d.xp);
    return [...byMonth].map(([m, value]) => ({ label: MONTH[Number(m.slice(5)) - 1], value }));
  }, [days, window, range]);
  const max = Math.max(1, ...bars.map((b) => b.value));
  const best = bars.reduce((a, b, i) => (b.value > bars[a].value ? i : a), 0);

  // Heatmap: columns are weeks (oldest left), rows are weekdays; the first column is padded so each date lands on its weekday.
  const heat = useMemo(() => {
    const tail = (days ?? []).slice(-WEEKS * 7);
    const pad = tail.length ? new Date(`${tail[0].day}T12:00:00`).getDay() : 0;
    return { pad, cells: tail };
  }, [days]);
  if (!state) return <main className="main"><div className="empty">Loading your progress…</div></main>;
  const level = (xp: number) => (xp <= 0 ? 0 : xp < state.today.qualify ? 1 : xp < state.today.goal ? 2 : 3);
  const sessions = sum(days ?? [], "lessons") + sum(days ?? [], "quiz") + sum(days ?? [], "ask");

  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">Progress</div>
          <h1>See how far you have come.</h1>
          <div className="seg" role="radiogroup" aria-label="Time range">
            {RANGES.map(([k, label]) => (
              <button type="button" key={k} role="radio" aria-checked={range === k} className={range === k ? "on" : ""} onClick={() => setRange(k)}>{label}</button>
            ))}
          </div>
        </div>
      </header>

      <section className="aura orange" aria-label="Streak">
        <div className="streak-top">
          <div className="aura-title" style={{ margin: 0 }}>Streak</div>
          <span className={`flame${state.streak.current > 0 && state.streak.today_done ? " lit" : ""}`}><Glyph name="flame" size={26} /></span>
        </div>
        <div className="aura-big left"><DotNumber value={state.streak.current} size={76} /><span>{state.streak.current === 1 ? "day in a row" : "days in a row"} · best {state.streak.best} · {sessions} study actions in the last year</span></div>
        {days ? (
          <div className="heat" role="img" aria-label={`Activity for the last ${WEEKS} weeks`}>
            {Array.from({ length: heat.pad }, (_, i) => <i key={`p${i}`} className="pad" />)}
            {heat.cells.map((d) => <i key={d.day} className={`l${level(d.xp)}${d.day === localDay() ? " today" : ""}`} title={`${d.day}: ${d.xp} XP`} />)}
          </div>
        ) : <div className="muted">Loading…</div>}
        <WeekRow week={state.week} />
      </section>

      <div className="stats" style={{ margin: "22px 0" }}>
        <Stat value={sum(window, "lessons")} label="Lessons finished" accent />
        <Stat value={sum(window, "quiz")} label="Right answers" />
        <Stat value={sum(window, "ask")} label="Questions to the tutor" />
        <Stat value={window.filter((d) => d.xp >= state.today.qualify).length} label="Days counted" />
      </div>

      <section className="aura pink" aria-label="XP per day">
        <div className="streak-top">
          <div className="aura-title" style={{ margin: 0 }}>{range === "year" ? "XP per month" : "XP per day"}</div>
          <span className="chip">{sum(window, "xp")} XP in {range === "week" ? "7 days" : range === "month" ? "30 days" : "12 months"}</span>
        </div>
        <div className={`bars ${range}`} role="list" aria-label="XP">
          {bars.map((b, i) => (
            <div key={i} className="bar" role="listitem" aria-label={`${b.label || ""} ${b.value} XP`}>
              <i className={i === best && b.value > 0 ? "best" : ""} style={{ height: `${Math.max((b.value / max) * 100, 4)}%` }} />
              <span>{b.label}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
};
