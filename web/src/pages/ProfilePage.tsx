import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Stat } from "../ds/Stat";
import { useRewards } from "../rewards/RewardsContext";

type Profile = { name: string; age: number };

/** The learner: name and age. The age only decides how simply lessons and tutor answers are worded; it never leaves this computer. */
export const ProfilePage: React.FC<{ onSettings: () => void }> = ({ onSettings }) => {
  const { state, refresh } = useRewards();
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [saved, setSaved] = useState("");
  useEffect(() => { api<Profile>("/api/profile").then((p) => { setName(p.name === "Learner" ? "" : p.name); setAge(p.age ? String(p.age) : ""); }).catch(() => undefined); }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api<Profile>("/api/profile", { name: name.trim() || "Learner", age: age ? Math.min(Math.max(parseInt(age, 10) || 0, 0), 120) : 0 });
      refresh();
      setSaved("Saved. New lessons and answers will suit you.");
    } catch (err) { setSaved((err as Error).message); }
    window.setTimeout(() => setSaved(""), 2600);
  };

  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">Profile</div>
          <h1>{name.trim() ? `Hello, ${name.trim()}.` : "Tell Chanakya about you."}</h1>
          {state && (
            <div className="stats">
              <Stat value={state.level} label="Level" accent />
              <Stat value={state.streak.current} label="Day streak" />
              <Stat value={state.totals.lessons} label="Lessons finished" />
              <Stat value={state.xp} label="Score" />
            </div>
          )}
        </div>
      </header>
      <section className="section">
        <form className="set-card profile-card" onSubmit={save}>
          <div className="avatar" aria-hidden>{initial}</div>
          <label className="field-label" htmlFor="pf-name">Name</label>
          <input id="pf-name" className="set-input" value={name} maxLength={30} placeholder="Your name" onChange={(e) => setName(e.target.value)} autoComplete="given-name" />
          <label className="field-label" htmlFor="pf-age">Age</label>
          <input id="pf-age" className="set-input" value={age} inputMode="numeric" maxLength={3} placeholder="For example 12" onChange={(e) => setAge(e.target.value.replace(/\D/g, ""))} />
          <p className="muted">Used to choose simple words and examples that suit you. It stays on this computer.</p>
          <div className="row">
            <button type="submit" className="primary lime">Save</button>
            <button type="button" className="ghost" onClick={onSettings}>More settings</button>
          </div>
          {saved && <p className="muted" role="status">{saved}</p>}
        </form>
      </section>
    </main>
  );
};
