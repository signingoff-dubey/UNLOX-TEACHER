import React, { useState } from "react";
import { api, runJob, url } from "../api";
import type { Job, Lesson } from "../types";
import { Glyph } from "../ds/Glyph";

type Busy = { label: string; progress: number } | null;

/** Light ways to take a lesson away: subtitles only, narration only (a "podcast"), the whole lesson as one file for a USB stick, and printable papers. */
export const TakeAway: React.FC<{ lesson: Lesson; lang: string }> = ({ lesson, lang }) => {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState("");
  const [podcast, setPodcast] = useState<Record<string, string>>({});
  const making = !!lesson.building;

  const job = async (label: string, start: Promise<Job>): Promise<Job["result"]> => {
    setError(""); setBusy({ label, progress: 0 });
    try {
      const done = await runJob(start, (j) => setBusy({ label, progress: j.progress }));
      return done.result;
    } catch (e) { setError((e as Error).message); return null; } finally { setBusy(null); }
  };

  const makePodcast = async (format: "mp3" | "wav") => {
    const r = await job("Joining the narration", api<Job>(`/api/lessons/${lesson.id}/podcast`, { lang, format }));
    if (r?.url) setPodcast((p) => ({ ...p, [`${lang}.${format}`]: r.url as string }));
  };
  const makePaper = async (kind: "worksheet" | "paper") => {
    const counts = kind === "worksheet" ? { mcq: 6, short: 3, long: 0 } : { mcq: 10, short: 5, long: 2 };
    const paper = await job(kind === "worksheet" ? "Writing the worksheet" : "Writing the paper",
      api<Job>("/api/papers", { lesson_id: lesson.id, ...counts, lang, title: "" }));
    if (paper?.id) window.open(url(`/api/papers/${paper.id}/html`), "_blank", "noopener");
  };
  const mp3 = podcast[`${lang}.mp3`];

  return (
    <section className="aura blue takeaway" aria-label="More ways to take it">
      <div className="aura-title">More ways to take it</div>
      <div className="aura-actions">
        <a className="glass-btn" href={url(`/api/lessons/${lesson.id}/subtitles?lang=${lang}&fmt=srt`)} download><Glyph name="captions" />Subtitles .srt</a>
        <a className="glass-btn" href={url(`/api/lessons/${lesson.id}/subtitles?lang=${lang}&fmt=txt`)} download><Glyph name="book" />Transcript</a>
        {mp3 ? (
          <a className="glass-btn" href={url(mp3)} download={`${lesson.concept}-${lang}.mp3`}><Glyph name="download" />Narration .mp3</a>
        ) : (
          <button type="button" className="glass-btn" disabled={!!busy || making} onClick={() => void makePodcast("mp3")}><Glyph name="mic" />Make narration .mp3</button>
        )}
        <a className={`glass-btn${making ? " disabled" : ""}`} href={making ? undefined : url(`/api/lessons/${lesson.id}/bundle`)} aria-disabled={making}
          title="One file with the lesson, its voice and a player that works with no internet. Copy it to a USB stick."><Glyph name="folder" />Lesson file (USB)</a>
        <button type="button" className="glass-btn" disabled={!!busy || making} onClick={() => void makePaper("worksheet")}><Glyph name="check" />Worksheet</button>
        <button type="button" className="glass-btn" disabled={!!busy || making} onClick={() => void makePaper("paper")}><Glyph name="target" />Question paper</button>
      </div>
      {busy && <p className="muted" role="status">{busy.label}… {Math.round(busy.progress * 100)}%</p>}
      {error && <p className="notice bad" role="alert">{error}</p>}
    </section>
  );
};
