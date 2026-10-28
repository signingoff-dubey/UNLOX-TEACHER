import React, { useEffect, useRef, useState } from "react";
import { api, runJob, url } from "../api";
import type { Job, Lesson } from "../types";
import { Glyph } from "../ds/Glyph";
import { PaperReady, type Paper } from "./PaperReady";

type Busy = { key: string; label: string; progress: number } | null;

const FLASH_MS = 1800;          // a download link glows this long after the click (the file is on its way)

/** Light ways to take a lesson away: subtitles only, narration only (a "podcast"), the whole lesson as one file for a USB stick, and printable papers.
 *  Like the study tools above the chat, a clicked button gets a border of flowing colour: for as long as its job runs, or briefly for a download. */
export const TakeAway: React.FC<{ lesson: Lesson; lang: string }> = ({ lesson, lang }) => {
  const [busy, setBusy] = useState<Busy>(null);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [podcast, setPodcast] = useState<Record<string, string>>({});
  const [ready, setReady] = useState<Paper | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const making = !!lesson.building;

  useEffect(() => () => { if (flashTimer.current) clearTimeout(flashTimer.current); }, []);

  const glow = (key: string) => {
    setFlash(key);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(""), FLASH_MS);
  };
  const cls = (key: string, extra = "") => {
    const working = busy?.key === key;
    return `glass-btn${working || flash === key ? " is-busy" : ""}${extra}`;
  };
  const fill = (key: string) => ({ ["--p" as string]: busy?.key === key ? Math.round(busy.progress * 100) : 0 });

  const job = async (key: string, label: string, start: Promise<Job>): Promise<Job["result"]> => {
    setError(""); setBusy({ key, label, progress: 0 });
    try {
      const done = await runJob(start, (j) => setBusy({ key, label, progress: j.progress }));
      return done.result;
    } catch (e) { setError((e as Error).message); return null; } finally { setBusy(null); }
  };

  const makePodcast = async (format: "mp3" | "wav") => {
    const r = await job("mp3", "Joining the narration", api<Job>(`/api/lessons/${lesson.id}/podcast`, { lang, format }));
    if (r?.url) setPodcast((p) => ({ ...p, [`${lang}.${format}`]: r.url as string }));
  };
  const makePaper = async (kind: "worksheet" | "paper") => {
    const counts = kind === "worksheet" ? { mcq: 6, short: 3, long: 0 } : { mcq: 10, short: 5, long: 2 };
    const paper = await job(kind, kind === "worksheet" ? "Writing the worksheet" : "Writing the paper",
      api<Job>("/api/papers", { lesson_id: lesson.id, ...counts, lang, title: "" }));
    if (paper?.id) setReady({ ...(paper as unknown as Omit<Paper, "kind">), kind });          // a popup to save it (a new tab was blocked by some browsers)
  };
  const mp3 = podcast[`${lang}.mp3`];

  return (
    <section className="aura blue takeaway" aria-label="More ways to take it">
      <div className="aura-title">More ways to take it</div>
      <div className="aura-actions">
        <a className={cls("srt")} onClick={() => glow("srt")} href={url(`/api/lessons/${lesson.id}/subtitles?lang=${lang}&fmt=srt`)} download><Glyph name="captions" />Subtitles .srt</a>
        <a className={cls("txt")} onClick={() => glow("txt")} href={url(`/api/lessons/${lesson.id}/subtitles?lang=${lang}&fmt=txt`)} download><Glyph name="book" />Transcript</a>
        {mp3 ? (
          <a className={cls("mp3dl")} onClick={() => glow("mp3dl")} href={url(mp3)} download={`${lesson.concept}-${lang}.mp3`}><Glyph name="download" />Narration .mp3</a>
        ) : (
          <button type="button" className={cls("mp3")} style={fill("mp3")} disabled={(!!busy && busy.key !== "mp3") || making} aria-busy={busy?.key === "mp3"}
            onClick={() => { if (!busy) void makePodcast("mp3"); }}><Glyph name="mic" />Make narration .mp3</button>
        )}
        <a className={cls("bundle", making ? " disabled" : "")} onClick={() => glow("bundle")} href={making ? undefined : url(`/api/lessons/${lesson.id}/bundle`)} aria-disabled={making}
          title="One file with the lesson, its voice and a player that works with no internet. Copy it to a USB stick."><Glyph name="folder" />Lesson file (USB)</a>
        <button type="button" className={cls("worksheet")} style={fill("worksheet")} disabled={(!!busy && busy.key !== "worksheet") || making} aria-busy={busy?.key === "worksheet"}
          onClick={() => { if (!busy) void makePaper("worksheet"); }}><Glyph name="check" />Worksheet</button>
        <button type="button" className={cls("paper")} style={fill("paper")} disabled={(!!busy && busy.key !== "paper") || making} aria-busy={busy?.key === "paper"}
          onClick={() => { if (!busy) void makePaper("paper"); }}><Glyph name="target" />Question paper</button>
      </div>
      {busy && <p className="muted" role="status">{busy.label}… {Math.round(busy.progress * 100)}%</p>}
      {error && <p className="notice bad" role="alert">{error}</p>}
      {ready && <PaperReady paper={ready} language={lesson.languages[ready.lang]?.name ?? (ready.lang === "en" ? "English" : ready.lang)} onClose={() => setReady(null)} />}
    </section>
  );
};
