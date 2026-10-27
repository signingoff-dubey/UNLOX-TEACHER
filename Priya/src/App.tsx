import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import type { Job, Lesson } from "./types";
import { api, getApiBase, runJob, url, type Lang, type LessonSummary } from "./api";
import { LessonVideo, lessonFrames } from "./remotion/Lesson";
import { FPS, H, W } from "./remotion/theme";
import { StatusPanel } from "./components/StatusPanel";
import { PdfUpload } from "./components/PdfUpload";
import { Timeline } from "./components/Timeline";
import { DotNumber } from "./components/DotNumber";
import { Glyph } from "./components/Glyph";

// The 3D metaverse is a separate chunk: it only loads when the student opens it.
const Metaverse = lazy(() => import("metaverse"));

const EXAMPLES: [string, string][] = [
  ["Photosynthesis", "leaf"], ["The water cycle", "drop"], ["Newton's third law", "bolt"],
  ["How a rainbow forms", "rainbow"], ["Fractions", "pie"],
];
const DEFAULT_LANGS = ["hi", "te"];

const Stat: React.FC<{ value: string | number; label: string; accent?: boolean }> = ({ value, label, accent }) => (
  <div className="stat">
    <DotNumber value={value} size={34} />
    <span className={accent ? "chip lime" : "chip"}>{label}</span>
  </div>
);

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
  const [metaverse, setMetaverse] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [assetBase, setAssetBase] = useState(getApiBase());
  const [upload, setUpload] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [tab, setTab] = useState<"create" | "library">("create");
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
  const canGenerate = !busy && (concept.trim().length >= 2 || !!upload);

  async function generate(topic = concept) {
    if (busy || (topic.trim().length < 2 && !upload)) return;
    setConcept(topic);
    setError("");
    try {
      const body = { concept: topic.trim(), languages: selected, upload, focus: upload ? focus.trim() : "" };
      const done = await runJob(api<Job>("/api/lessons", body), setJob);
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

  // Follow playback so the timeline highlights the current scene.
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
    <div className={lesson ? "shell has-lesson" : "shell"}>
      <aside className="side">
        <div className="brand">visual teacher</div>
        <div className="side-tabs" role="tablist" aria-label="Sidebar">
          <button role="tab" aria-selected={tab === "create"} className={tab === "create" ? "on" : ""}
            onClick={() => setTab("create")}>Create</button>
          <button role="tab" aria-selected={tab === "library"} className={tab === "library" ? "on" : ""}
            onClick={() => setTab("library")}>Library</button>
        </div>

        {tab === "create" ? (
          <>
            <form className="ask" onSubmit={(e) => { e.preventDefault(); generate(); }}>
              <label htmlFor="concept" className="sr-only">What do you want to learn?</label>
              <div className="ask-row">
                <Glyph name="sparkle" />
                <input id="concept" value={concept} onChange={(e) => setConcept(e.target.value)}
                  placeholder={upload ? "A topic in this PDF, or leave empty" : "What do you want to learn?"}
                  autoComplete="off" disabled={busy} maxLength={200} />
                {concept && !busy && (
                  <button type="button" className="round" aria-label="Clear" onClick={() => setConcept("")}>
                    <Glyph name="x" size={16} />
                  </button>
                )}
              </div>
              <button type="submit" className="primary" disabled={!canGenerate}>
                {busy ? "Creating…" : upload && !concept.trim() ? "Create lesson from PDF" : "Create lesson"}
              </button>
            </form>

            <PdfUpload sha={upload} onSha={setUpload} focus={focus} onFocus={setFocus} disabled={busy} />

            <div className="side-label">Try a topic</div>
            <ul className="rows">
              {EXAMPLES.map(([ex, icon]) => (
                <li key={ex}>
                  <button className="row" disabled={busy} onClick={() => generate(ex)}>
                    <Glyph name={icon} /><span>{ex}</span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="side-label">Languages <span className="muted">English is always included</span></div>
            <ul className="rows">
              {languages.filter((l) => l.code !== "en").map((l) => {
                const on = selected.includes(l.code);
                return (
                  <li key={l.code}>
                    <button className={on ? "row on" : "row"} disabled={busy} aria-pressed={on}
                      onClick={() => setSelected((s) => (on ? s.filter((c) => c !== l.code) : [...s, l.code]))}>
                      <Glyph name="globe" />
                      <span className="native">{l.native}<small>{l.name}</small></span>
                      <span className={on ? "chip lime" : "chip"}>{on ? "On" : l.piper ? "Off" : "GPU voice"}</span>
                    </button>
                  </li>
                );
              })}
              {!languages.length && <li className="muted pad">Languages load from the backend.</li>}
            </ul>
          </>
        ) : (
          <ul className="rows">
            {recent.map((l) => (
              <li key={l.id}>
                <button className={l.id === lesson?.id ? "row on" : "row"} onClick={() => openLesson(l.id)}>
                  <Glyph name="folder" />
                  <span>{l.concept}</span>
                  <span className="chip">{l.languages.length} lang{l.videos.length ? ` · ${l.videos.length} MP4` : ""}</span>
                </button>
              </li>
            ))}
            {!recent.length && <li className="muted pad">No lessons yet. Make one in Create.</li>}
          </ul>
        )}

        <StatusPanel onBaseChange={loadLists} />
      </aside>

      <main className="main">
        <header className="hero">
          <div>
            <h1>{track ? track.title : "What will you learn today?"}</h1>
            <div className="stats">
              {track && lesson ? (
                <>
                  <Stat value={track.scenes.length} label="Scenes" accent />
                  <Stat value={track.duration_s.toFixed(0)} label="Seconds" />
                  <Stat value={Object.keys(lesson.languages).length} label="Languages" />
                  <Stat value={totalTime.toFixed(1)} label="Built in s" />
                </>
              ) : (
                <>
                  <Stat value={recent.length} label="Lessons made" accent />
                  <Stat value={selected.length + 1} label="Languages picked" />
                  <Stat value={8} label="Scene types" />
                </>
              )}
            </div>
          </div>
          <div className="hero-actions">
            {lesson && (
              <div className="tabs" role="tablist" aria-label="Lesson language">
                {Object.values(lesson.languages).map((t) => (
                  <button key={t.lang} role="tab" aria-selected={t.lang === active}
                    className={t.lang === active ? "tab on" : "tab"} onClick={() => setActive(t.lang)}>
                    {t.native}
                  </button>
                ))}
              </div>
            )}
            <button type="button" className="round lg" onClick={() => setMetaverse(true)} aria-label="Open the metaverse"
              title="Metaverse">
              <Glyph name="cube" size={20} />
            </button>
          </div>
        </header>

        {track && <Timeline track={track} current={sceneIndex} onSeek={seek} />}

        {error && <div className="notice bad" role="alert">{error}</div>}

        {lesson && track && inputProps ? (
          <>
            <div className="board">
              <section className="aura green player-card" aria-label="Lesson player">
                <div className="aura-title">Lesson player</div>
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
              </section>

              <div className="stack">
                {busy && job ? <Pending job={job} /> : (
                  <section className="aura pink">
                    <div className="aura-title">Take it with you</div>
                    <div className="aura-actions">
                      {lesson.videos[active] ? (
                        <a className="glass-btn" href={url(lesson.videos[active])} download={`${lesson.concept}-${active}.mp4`}>
                          <Glyph name="download" /> Download MP4
                        </a>
                      ) : (
                        <button className="glass-btn" disabled={exporting} onClick={() => exportMp4(active)}>
                          <Glyph name="download" />
                          {exporting ? `${exportJob.stage} ${Math.round(exportJob.progress * 100)}%` : "Export MP4"}
                        </button>
                      )}
                      <a className="glass-btn" href={url(`/media/lessons/${lesson.id}/captions_${active}.srt`)} download>
                        <Glyph name="captions" /> Captions (.srt)
                      </a>
                    </div>
                  </section>
                )}

                <section className="aura orange">
                  <div className="aura-title">Made in</div>
                  <div className="aura-big"><DotNumber value={totalTime.toFixed(1)} size={48} /><span>seconds</span></div>
                  <ul className="breakdown">
                    {Object.entries(lesson.timings).map(([k, v]) => (
                      <li key={k}>
                        <span>{k === "plan_s" ? "Lesson plan" : `${lesson.languages[k.replace(/_s$/, "")]?.name ?? k} translation + voice`}</span>
                        <b>{v.toFixed(1)} s</b>
                      </li>
                    ))}
                  </ul>
                  <div className="ruler" aria-hidden />
                </section>
              </div>
            </div>

            {track.translator === "untranslated" && (
              <div className="notice">Translation model unavailable; {track.name} shows the English text.</div>
            )}
            {track.tts_engines.includes("silent") && (
              <div className="notice">No voice model installed for {track.name}; narration is a silent placeholder.</div>
            )}

            <section className="section">
              <div className="section-head">
                <div>
                  <h2>Sources</h2>
                  <p>What this lesson is grounded in.</p>
                </div>
              </div>
              {lesson.sources?.length ? (
                <ul className="tiles">
                  {lesson.sources.map((s) => (
                    <li key={s.title + (s.section ?? "")} className="tile">
                      <div className="tile-top"><Glyph name={s.source === "upload" ? "book" : "link"} size={16} />
                        <span>{s.section || (s.source === "upload" ? "your PDF" : s.source)}</span></div>
                      <div className="tile-score"><DotNumber value={Math.round(s.score * 100)} size={30} /><small>match</small></div>
                      {/^https?:/.test(s.url)
                        ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                        : <b>{s.title}</b>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Written from the model's own knowledge (no matching articles).</p>
              )}
              <details className="json">
                <summary>Lesson data (JSON)</summary>
                <pre>{JSON.stringify(track.scenes.map(({ captions, audio_url, ...s }) => s), null, 2)}</pre>
              </details>
            </section>
          </>
        ) : (
          <div className="board">
            <section className="aura green intro">
              <div className="aura-title">Narrated lessons</div>
              <div className="aura-big"><DotNumber value="30-90" size={56} /><span>seconds each</span></div>
              <p>Type a concept or pick a topic. You get an animated, narrated lesson made entirely on this laptop.</p>
            </section>
            <div className="stack">
              {busy && job ? <Pending job={job} /> : (
                <section className="aura orange">
                  <div className="aura-title">Languages</div>
                  <div className="aura-big"><DotNumber value={Math.max(languages.length, 1)} size={56} /><span>available</span></div>
                </section>
              )}
              <section className="aura pink">
                <div className="aura-title">Offline</div>
                <p>Planner, translation and voices run locally. Attach a PDF to teach from your own book.</p>
              </section>
            </div>
          </div>
        )}
      </main>

      {metaverse && (
        <div className="mv-overlay" role="dialog" aria-label="Metaverse">
          <Suspense fallback={<div className="mv-loading">Loading the metaverse…</div>}>
            <Metaverse lesson={lesson} lang={active} onExit={() => setMetaverse(false)} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

/** Job progress, styled like the "results are pending" card. */
const Pending: React.FC<{ job: Job }> = ({ job }) => (
  <section className="pending" role="status">
    <div className="pending-title">Your lesson is on its way</div>
    <div className="aura-big dark"><DotNumber value={`${Math.round(job.progress * 100)}%`} size={40} /></div>
    <div className="slider"><div style={{ width: `${Math.max(job.progress * 100, 3)}%` }} /></div>
    <div className="muted">{job.stage || "Queued"}…</div>
  </section>
);
