import React, { useEffect, useState } from "react";
import { api } from "../api";
import { Glyph } from "../ds/Glyph";
import { useRewards } from "../rewards/RewardsContext";

type Health = {
  llm: { model: string; ollama: { ok: boolean } };
  translate: { backend: string; model: string; toolkit_installed: boolean };
  tts: { engine: string; piper_voices: string[] };
  stt: { model: string; ready: boolean };
  render: { web_dir_ok: boolean; node_modules_ok: boolean };
  device: string;
};

const read = (k: string, fallback: boolean) => { try { const v = localStorage.getItem(k); return v === null ? fallback : v !== "0"; } catch { return fallback; } };
const write = (k: string, on: boolean) => { try { localStorage.setItem(k, on ? "1" : "0"); } catch { /* storage blocked */ } };

const Toggle: React.FC<{ on: boolean; label: string; sub: string; onChange: (v: boolean) => void }> = ({ on, label, sub, onChange }) => (
  <li className="set-row">
    <div><b>{label}</b><span>{sub}</span></div>
    <button type="button" role="switch" aria-checked={on} aria-label={label} className={`switch${on ? " on" : ""}`} onClick={() => onChange(!on)}><i /></button>
  </li>
);

/** Your name and daily goal, sound and the opening animation, and what is installed on this computer. */
export const SettingsPage: React.FC = () => {
  const { state, refresh } = useRewards();
  const [name, setName] = useState("");
  const [speaker, setSpeaker] = useState(() => read("vt.speaker", true));
  const [intro, setIntro] = useState(() => read("vt.intro", true));
  const [health, setHealth] = useState<Health | null>(null);
  const [saved, setSaved] = useState("");
  useEffect(() => { if (state) setName(state.name); }, [state?.name]);
  useEffect(() => { api<Health>("/api/health").then(setHealth).catch(() => setHealth(null)); }, []);

  const save = async (goal: number, nm = name) => {
    try { await api("/api/rewards/goal", { goal, name: nm.trim() || undefined }); refresh(); setSaved("Saved"); } catch (e) { setSaved((e as Error).message); }
    window.setTimeout(() => setSaved(""), 1800);
  };
  const engines: [string, string, boolean | null][] = health ? [
    ["Language model", `${health.llm.model} (Ollama)`, health.llm.ollama.ok],
    ["Translation", `${health.translate.backend} · ${health.translate.model}`, health.translate.toolkit_installed],
    ["Voices", `${health.tts.engine} · ${health.tts.piper_voices.length} Piper voices`, health.tts.piper_voices.length > 0],
    ["Speech to text", `Whisper ${health.stt.model}`, health.stt.ready],
    ["Video export", "Remotion", health.render.web_dir_ok && health.render.node_modules_ok],
    ["Graphics", health.device, null],
  ] : [];

  return (
    <main className="main">
      <header className="hero"><div><div className="eyebrow">Settings</div><h1>Make it yours.</h1></div></header>

      <section className="section">
        <div className="section-head"><div><h2>You</h2><p>The name on your streak and your daily goal.</p></div></div>
        <div className="set-card">
          <label className="field-label" htmlFor="set-name">Name</label>
          <input id="set-name" className="set-input" value={name} maxLength={30} onChange={(e) => setName(e.target.value)} onBlur={() => state && void save(state.today.goal)} />
          <div className="field-label">Daily goal</div>
          <div className="seg" role="radiogroup" aria-label="Daily goal">
            {(state?.goals ?? []).map((g) => (
              <button type="button" key={g} role="radio" aria-checked={state?.today.goal === g} className={state?.today.goal === g ? "on" : ""} onClick={() => void save(g)}>{g} XP</button>
            ))}
          </div>
          {saved && <p className="muted" role="status" style={{ marginTop: 8 }}>{saved}</p>}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><div><h2>Sound and look</h2><p>Saved in this browser.</p></div></div>
        <ul className="set-list">
          <Toggle on={speaker} label="Spoken answers" sub="The tutor reads its answers aloud" onChange={(v) => { setSpeaker(v); write("vt.speaker", v); }} />
          <Toggle on={intro} label="Opening animation" sub="Play the logo when the page loads" onChange={(v) => { setIntro(v); write("vt.intro", v); }} />
        </ul>
      </section>

      <section className="section">
        <div className="section-head"><div><h2>On this computer</h2><p>Everything runs here, with no internet and no outside AI.</p></div></div>
        {health ? (
          <ul className="set-list">
            {engines.map(([k, v, ok]) => (
              <li key={k} className="set-row">
                <div><b>{k}</b><span>{v}</span></div>
                {ok === null ? null : <span className={`chip${ok ? " lime" : ""}`}><Glyph name={ok ? "check" : "x"} size={14} />{ok ? "Ready" : "Not ready"}</span>}
              </li>
            ))}
          </ul>
        ) : <p className="muted">Checking…</p>}
      </section>
    </main>
  );
};
