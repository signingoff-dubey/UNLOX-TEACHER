import React, { useRef, useState } from "react";
import { api, url } from "../api";
import type { Lesson } from "../types";
import { Glyph } from "../ds/Glyph";
import { useRewards } from "../rewards/RewardsContext";

type Point = { point: string; heading: string; scene: number; similarity: number; said?: string };
type Result = { score: number; covered: Point[]; missed: Point[]; points: number; sentences: number; method: string; verdict: string };

/** Teach it back: explain the lesson in your own words, by typing or speaking, and see which points you covered and which you missed. */
export const TeachBack: React.FC<{ lesson: Lesson; onSeekScene?: (scene: number) => void }> = ({ lesson, onSeekScene }) => {
  const { award } = useRewards();
  const [text, setText] = useState("");
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState<"off" | "on" | "hearing">("off");
  const [error, setError] = useState("");
  const recorder = useRef<{ mr: MediaRecorder; stream: MediaStream } | null>(null);
  const canMic = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

  const check = async () => {
    setBusy(true); setError("");
    try {
      const r = await api<Result>(`/api/lessons/${lesson.id}/teachback`, { text });
      setRes(r);
      if (r.score >= 60) award({ type: "tutor_question" });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const toggleMic = async () => {
    if (rec === "on") { recorder.current?.mr.stop(); return; }
    if (rec !== "off") return;
    setError("");
    let stream: MediaStream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch { setError("The microphone is blocked. Allow it in the browser, or type your explanation."); return; }
    const mr = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      recorder.current = null;
      setRec("hearing");
      try {
        const r = await fetch(url(`/api/stt?lang=en&lesson_id=${lesson.id}`), { method: "POST", body: new Blob(chunks, { type: mr.mimeType }) });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail ?? `Speech recognition failed (${r.status})`);
        if (body.text) setText((t) => (t ? t + " " : "") + body.text); else setError("I did not catch that. Try again a little closer to the microphone.");
      } catch (e) { setError((e as Error).message); } finally { setRec("off"); }
    };
    recorder.current = { mr, stream };
    mr.start();
    setRec("on");
  };

  return (
    <section className="card white teachback" aria-label="Teach it back">
      <div className="card-title"><Glyph name="brain" size={16} />Teach it back</div>
      <p className="muted">Explain what you learned in your own words, in English. You will see which points you covered and which you missed.</p>
      <div className="tb-box">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} maxLength={4000} placeholder="Plants take in sunlight and water, and…" aria-label="Your explanation" disabled={rec !== "off"} />
        {canMic && (
          <button type="button" className={`icon-btn mic${rec === "on" ? " live" : ""}`} onClick={() => void toggleMic()} disabled={rec === "hearing"}
            aria-pressed={rec === "on"} aria-label={rec === "on" ? "Stop and add what I said" : "Speak my explanation"}><Glyph name="mic" size={18} /></button>
        )}
      </div>
      <div className="row">
        <button type="button" className="primary lime" disabled={busy || text.trim().split(/\s+/).length < 4} onClick={() => void check()}>{busy ? "Checking…" : "Check my explanation"}</button>
        {res && <button type="button" className="ghost" onClick={() => { setRes(null); setText(""); }}>Start again</button>}
      </div>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {res && (
        <div className="tb-res" role="status">
          <div className="tb-score"><b>{res.score}</b><span>/ 100</span><em>{res.verdict}</em></div>
          {res.covered.length > 0 && (
            <details open><summary>Covered ({res.covered.length} of {res.points})</summary>
              <ul className="tb-list ok">{res.covered.map((p) => <li key={p.point}>{p.point}</li>)}</ul></details>
          )}
          {res.missed.length > 0 && (
            <details open><summary>Missed ({res.missed.length})</summary>
              <ul className="tb-list miss">{res.missed.map((p) => (
                <li key={p.point}>{p.point}{onSeekScene && <button type="button" className="ghost small" onClick={() => onSeekScene(p.scene)}>Watch “{p.heading}”</button>}</li>
              ))}</ul></details>
          )}
          {res.method === "words" && <p className="muted">The embedding model is not running, so this used a plain word comparison.</p>}
        </div>
      )}
    </section>
  );
};
