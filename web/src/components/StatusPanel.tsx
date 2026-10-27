import React, { useEffect, useState } from "react";
import { api, getApiBase, setApiBase, type Health } from "../api";

type Check = { label: string; detail: string; ok: boolean | "warn" };

function checks(h: Health): Check[] {
  const voices = h.tts.piper_voices.length;
  return [
    h.llm.backend === "mock"
      ? { label: "Planner", detail: "Sample lesson (mock)", ok: "warn" }
      : { label: "Planner", detail: h.llm.ollama.ok ? h.llm.model : "Ollama not running or model missing", ok: h.llm.ollama.ok },
    h.translate.backend === "indictrans2"
      ? { label: "Translation", detail: h.translate.toolkit_installed ? "IndicTrans2" : "IndicTrans2 not installed", ok: h.translate.toolkit_installed || "warn" }
      : { label: "Translation", detail: h.translate.backend, ok: h.translate.backend === "none" ? "warn" : true },
    { label: "Voices", detail: `${voices} Piper${h.tts.parler_installed ? " + Indic Parler" : ""}`, ok: voices > 0 || h.tts.parler_installed || "warn" },
    { label: "Video export", detail: h.render.node_modules_ok ? "Ready" : "Run npm install in web/", ok: h.render.node_modules_ok },
    { label: "Device", detail: h.device === "cuda" ? "GPU" : "CPU", ok: true },
  ];
}

export const StatusPanel: React.FC<{ onBaseChange: () => void }> = ({ onBaseChange }) => {
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const [base, setBase] = useState(getApiBase());

  const refresh = () => {
    setDown(false);
    api<Health>("/api/health").then(setHealth).catch(() => { setHealth(null); setDown(true); });
  };
  useEffect(refresh, []);

  return (
    <details className="status" open={down}>
      <summary>
        <span className={`dot ${down ? "bad" : health ? "good" : ""}`} aria-hidden />
        {down ? "Backend not reachable" : health ? "System status" : "Checking backend…"}
      </summary>
      {health && (
        <ul className="checks">
          {checks(health).map((c) => (
            <li key={c.label}>
              <span className={`dot ${c.ok === true ? "good" : c.ok === "warn" ? "warn" : "bad"}`} aria-hidden />
              <b>{c.label}</b>
              <span className="muted">{c.detail}</span>
            </li>
          ))}
        </ul>
      )}
      <form className="base" onSubmit={(e) => { e.preventDefault(); setApiBase(base); onBaseChange(); refresh(); }}>
        <label htmlFor="api-base" className="muted">Backend address (blank = this server)</label>
        <div className="row">
          <input id="api-base" value={base} onChange={(e) => setBase(e.target.value)} placeholder="http://192.168.1.20:8000" />
          <button type="submit" className="small">Connect</button>
        </div>
      </form>
    </details>
  );
};
