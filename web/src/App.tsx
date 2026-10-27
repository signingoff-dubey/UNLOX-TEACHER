import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import type { Job, Lesson } from "./types";
import { api, getApiBase, runJob, url, type Lang, type LessonSummary } from "./api";
import { LessonVideo, lessonFrames } from "./remotion/Lesson";
import { FPS, H, W } from "./remotion/theme";
import { StatusPanel } from "./components/StatusPanel";
import { SceneList } from "./components/SceneList";
import { History } from "./components/History";

const EXAMPLES = ["Photosynthesis", "The water cycle", "Newton's third law", "How a rainbow forms", "Fractions"];
const DEFAULT_LANGS = ["hi", "te"];

export default function App() {
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [selected, setSelected] = useState<string[]>(DEFAULT_LANGS);
  const [concept, setConcept] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [recent, setRecent] = useState<LessonSummary[]>([]);
  const [active, setActive] = useState("en");
  const [exports, setExports] = useState<Record<string, Job>>({});
  const [error, setError] = useState("");
  const [sceneIndex, setSceneIndex] = useState(0);
  const [assetBase, setAssetBase] = useState(getApiBase());
  const player = useRef<PlayerRef>(null);

  const loadLists = useCallback(() => {
    setAssetBase(getApiBase());
    api<Lang[]>("/api/languages").then(setLanguages).catch(() => setLanguages([]));
    api<LessonSummary[]>("/api/lessons").then(setRecent).catch(() => setRecent([]));
  }, []);

  const openLesson = useCallback((id: string) => {
    setError("");
    api<Lesson>(`/api/lessons/${id}`)
      .then((l) => {
        setLesson(l);
        setExports({});
        setActive((cur) => (cur in l.languages ? cur : Object.keys(l.languages).find((c) => c !== "en") ?? "en"));
        window.history.replaceState(null, "", `#${l.id}`);
      })
      .catch(() => setError("That lesson could not be loaded."));
  }, []);

  useEffect(() => {
    loadLists();
    const id = location.hash.slice(1);
    if (id) openLesson(id);
  }, [loadLists, openLesson]);

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
      window.history.replaceState(null, "", `#${l.id}`);
      loadLists();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function exportMp4(lang: string) {
    if (!lesson) return;
    setError("");
    try {
      const done = await runJob(api<Job>(`/api/lessons/${lesson.id}/export`, { lang }),
        (j) => setExports((x) => ({ ...x, [lang]: j })));
      setLesson((l) => l && { ...l, videos: { ...l.videos, [lang]: done.result.url } });
      loadLists();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const track = lesson?.languages[active];
  const inputProps = useMemo(() => track && { track, assetBase }, [track, assetBase]);

  // Follow playback so the scene list highlights the current scene.
  useEffect(() => {
    const p = player.current;
    if (!p || !track) return;
    setSceneIndex(0);
    const onFrame = (e: { detail: { frame: number } }) => {
      const t = e.detail.frame / FPS;
      const i = track.scenes.findIndex((s) => t >= s.start_s && t < s.start_s + s.duration_s);
      if (i >= 0) setSceneIndex(i);
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, [track]);

  const seek = (seconds: number) => {
    player.current?.seekTo(Math.round(seconds * FPS));
    player.current?.play();
  };

  const exportJob = exports[active];
  const exporting = exportJob && (exportJob.status === "queued" || exportJob.status === "running");
  const totalTime = lesson ? Object.values(lesson.timings).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark" aria-hidden />Visual Teacher</div>
        <div className="tag">Runs offline · English + Indian languages</div>
      </header>

      <main className="layout">
        <aside className="panel">
          <form onSubmit={(e) => { e.preventDefault(); generate(); }}>
            <label htmlFor="concept" className="label">What do you want to learn?</label>
            <div className="ask">
              <input id="concept" value={concept} onChange={(e) => setConcept(e.target.value)}
                placeholder="e.g. Photosynthesis" autoComplete="off" disabled={busy} maxLength={200} />
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
                <button key={l.code} className={`lang ${on ? "on" : ""}`} disabled={busy} aria-pressed={on}
                  onClick={() => setSelected((s) => (on ? s.filter((c) => c !== l.code) : [...s, l.code]))}>
                  <span className="native">{l.native}</span>
                  <span className="muted">{l.name}{l.piper ? "" : " · GPU voice"}</span>
                </button>
              );
            })}
          </div>

          {busy && job && (
            <div className="progress" role="status">
              <div className="bar"><div style={{ transform: `scaleX(${job.progress})` }} /></div>
              <div className="muted">{job.stage}…</div>
            </div>
          )}
          {error && <div className="error" role="alert">{error}</div>}

          <History items={recent} activeId={lesson?.id} onOpen={openLesson} />
          <StatusPanel onBaseChange={loadLists} />
        </aside>

        <section className="stage">
          {lesson && track && inputProps ? (
            <>
              <div className="stage-head">
                <h1>{track.title}</h1>
                <div className="tabs" role="tablist" aria-label="Lesson language">
                  {Object.values(lesson.languages).map((t) => (
                    <button key={t.lang} role="tab" aria-selected={t.lang === active}
                      className={t.lang === active ? "tab on" : "tab"} onClick={() => setActive(t.lang)}>
                      {t.native}
                    </button>
                  ))}
                </div>
              </div>

              <div className="player">
                <Player
                  ref={player}
                  key={`${lesson.id}-${active}-${assetBase}`}
                  component={LessonVideo}
                  inputProps={inputProps}
                  durationInFrames={lessonFrames(track)}
                  compositionWidth={W}
                  compositionHeight={H}
                  fps={FPS}
                  controls
                  autoPlay
                  allowFullscreen
                  clickToPlay
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
                <div className="muted">
                  {track.scenes.length} scenes · {track.duration_s.toFixed(0)} s · made in {totalTime.toFixed(1)} s
                </div>
                <div className="buttons">
                  <a className="ghost" href={url(`/media/lessons/${lesson.id}/captions_${active}.srt`)} download>
                    Captions (.srt)
                  </a>
                  {lesson.videos[active] ? (
                    <a className="primary" href={url(lesson.videos[active])} download={`${lesson.concept}-${active}.mp4`}>
                      Download MP4
                    </a>
                  ) : (
                    <button className="primary" disabled={exporting} onClick={() => exportMp4(active)}>
                      {exporting ? `${exportJob.stage} ${Math.round(exportJob.progress * 100)}%` : "Export MP4"}
                    </button>
                  )}
                </div>
              </div>

              <div className="details-grid">
                <div>
                  <div className="label">Scenes</div>
                  <SceneList track={track} current={sceneIndex} onSeek={seek} />
                </div>
                <div>
                  <div className="label">Build time</div>
                  <div className="stats">
                    {Object.entries(lesson.timings).map(([k, v]) => (
                      <div key={k} className="stat">
                        <span>{k === "plan_s" ? "Lesson plan" : `${lesson.languages[k.replace(/_s$/, "")]?.name ?? k} translation + voice`}</span>
                        <b>{v.toFixed(1)} s</b>
                      </div>
                    ))}
                  </div>
                  <div className="label sources-label">Sources</div>
                  {lesson.sources?.length ? (
                    <ul className="sources">
                      {lesson.sources.map((s) => (
                        <li key={s.title}>
                          {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : <span>{s.title}</span>}
                          <span className="muted">{s.source}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="muted">Written from the model's own knowledge (no matching articles).</div>
                  )}
                  <details className="json">
                    <summary>Lesson data (JSON)</summary>
                    <pre>{JSON.stringify(track.scenes.map(({ captions, audio_url, ...s }) => s), null, 2)}</pre>
                  </details>
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
