import React, { useEffect, useMemo, useState } from "react";
import { Player } from "@remotion/player";
import type { Job, Lesson } from "./types";
import { LessonVideo, lessonFrames } from "./remotion/Lesson";
import { FPS, H, W } from "./remotion/theme";

type Lang = { code: string; name: string; native: string; piper: boolean };

const EXAMPLES = ["Photosynthesis", "The water cycle", "Newton's third law", "How a rainbow forms", "Fractions"];

async function api<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText);
  return res.json();
}

/** Poll a backend job until it finishes, reporting progress along the way. */
async function runJob(start: Promise<Job>, onUpdate: (j: Job) => void): Promise<Job> {
  let job = await start;
  while (job.status === "queued" || job.status === "running") {
    onUpdate(job);
    await new Promise((r) => setTimeout(r, 600));
    job = await api<Job>(`/api/jobs/${job.id}`);
  }
  onUpdate(job);
  if (job.status === "error") throw new Error(job.error ?? "Job failed");
  return job;
}

export default function App() {
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [selected, setSelected] = useState<string[]>(["hi", "te"]);
  const [concept, setConcept] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [active, setActive] = useState("en");
  const [exports, setExports] = useState<Record<string, Job>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    api<Lang[]>("/api/languages").then(setLanguages).catch(() => setError("Backend not reachable on port 8000."));
    const id = location.hash.slice(1);
    if (id) api<Lesson>(`/api/lessons/${id}`).then(setLesson).catch(() => undefined);
  }, []);

  const busy = job?.status === "queued" || job?.status === "running";

  async function generate(topic = concept) {
    if (!topic.trim() || busy) return;
    setConcept(topic);
    setError("");
    try {
      const done = await runJob(api<Job>("/api/lessons", { concept: topic, languages: selected }), setJob);
      const l = done.result as Lesson;
      setLesson(l);
      setExports({});
      setActive(selected.find((c) => c in l.languages) ?? "en");
      location.hash = l.id;
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function exportMp4(lang: string) {
    if (!lesson) return;
    try {
      const done = await runJob(api<Job>(`/api/lessons/${lesson.id}/export`, { lang }),
        (j) => setExports((x) => ({ ...x, [lang]: j })));
      setLesson((l) => l && { ...l, videos: { ...l.videos, [lang]: done.result.url } });
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  const track = lesson?.languages[active];
  const inputProps = useMemo(() => track && { track, assetBase: "" }, [track]);
  const exportJob = exports[active];
  const exporting = exportJob && (exportJob.status === "queued" || exportJob.status === "running");

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark" />Visual Teacher</div>
        <div className="tag">Offline · English + Indian languages</div>
      </header>

      <main className="layout">
        <section className="panel">
          <form onSubmit={(e) => { e.preventDefault(); generate(); }}>
            <label htmlFor="concept" className="label">What do you want to learn?</label>
            <div className="ask">
              <input id="concept" value={concept} onChange={(e) => setConcept(e.target.value)}
                placeholder="e.g. Photosynthesis" autoComplete="off" disabled={busy} />
              <button type="submit" disabled={busy || !concept.trim()}>{busy ? "Creating…" : "Create lesson"}</button>
            </div>
          </form>
          <div className="examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="chip" disabled={busy} onClick={() => generate(ex)}>{ex}</button>
            ))}
          </div>

          <div className="label">Languages <span className="muted">(English is always included)</span></div>
          <div className="langs">
            {languages.filter((l) => l.code !== "en").map((l) => {
              const on = selected.includes(l.code);
              return (
                <button key={l.code} className={`lang ${on ? "on" : ""}`} disabled={busy}
                  onClick={() => setSelected((s) => on ? s.filter((c) => c !== l.code) : [...s, l.code])}>
                  <span className="native">{l.native}</span>
                  <span className="muted">{l.name}</span>
                </button>
              );
            })}
          </div>

          {busy && job && (
            <div className="progress" role="status">
              <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
              <div className="muted">{job.stage}…</div>
            </div>
          )}
          {error && <div className="error" role="alert">{error}</div>}

          {lesson && (
            <div className="stats">
              <div className="label">Built in</div>
              {Object.entries(lesson.timings).map(([k, v]) => (
                <div key={k} className="stat">
                  <span>{k === "plan_s" ? "Lesson plan" : `${lesson.languages[k.replace("_s", "")]?.name ?? k} voice`}</span>
                  <b>{v.toFixed(1)} s</b>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="stage">
          {lesson && track && inputProps ? (
            <>
              <div className="tabs" role="tablist">
                {Object.values(lesson.languages).map((t) => (
                  <button key={t.lang} role="tab" aria-selected={t.lang === active}
                    className={t.lang === active ? "tab on" : "tab"} onClick={() => setActive(t.lang)}>
                    {t.native}
                  </button>
                ))}
              </div>
              <div className="player">
                <Player
                  key={`${lesson.id}-${active}`}
                  component={LessonVideo}
                  inputProps={inputProps}
                  durationInFrames={lessonFrames(track)}
                  compositionWidth={W}
                  compositionHeight={H}
                  fps={FPS}
                  controls
                  autoPlay
                  style={{ width: "100%", aspectRatio: "16 / 9" }}
                  acknowledgeRemotionLicense
                />
              </div>
              {track.translator === "untranslated" && (
                <div className="warn">Translation model unavailable; {track.name} shows the English text.</div>
              )}
              {track.tts_engines.includes("silent") && (
                <div className="warn">No voice model installed for {track.name}; narration is a silent placeholder.</div>
              )}
              <div className="actions">
                <div className="muted">{track.scenes.length} scenes · {track.duration_s.toFixed(0)} s</div>
                <div className="buttons">
                  <a className="ghost" href={`/media/lessons/${lesson.id}/captions_${active}.srt`} download>Captions (.srt)</a>
                  {lesson.videos[active] ? (
                    <a className="primary" href={lesson.videos[active]} download={`${lesson.concept}-${active}.mp4`}>Download MP4</a>
                  ) : (
                    <button className="primary" disabled={exporting} onClick={() => exportMp4(active)}>
                      {exporting ? `${exportJob.stage} ${Math.round(exportJob.progress * 100)}%` : "Export MP4"}
                    </button>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="empty">
              <div className="empty-art" aria-hidden><span /><span /><span /></div>
              <p>Type a concept and get a narrated, animated lesson in English and Indian languages, made entirely on this laptop.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
