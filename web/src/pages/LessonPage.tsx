import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import type { Job, Lesson } from "../types";
import { api, runJob, url, type Playlist } from "../api";
import { EpisodeRail } from "../components/EpisodeRail";
import { LessonVideo, lessonFrames } from "../remotion/Lesson";
import { FPS, H, W } from "../remotion/theme";
import { ChatPanel } from "../components/ChatPanel";
import { preloadMetaverse } from "../components/MetaverseLayer";
import { NotesPanel } from "../components/NotesPanel";
import { Pending } from "../components/Pending";
import { PlayerControls } from "../components/PlayerControls";
import { Timeline } from "../components/Timeline";
import { Ui } from "../components/ui-icons";
import { DotNumber } from "../ds/DotNumber";
import { Glyph } from "../ds/Glyph";
import { Stat } from "../ds/Stat";
import { useRewards } from "../rewards/RewardsContext";

type Props = {
  /** null while the lesson is still being made; `generating` then describes the job. */
  lesson: Lesson | null;
  generating?: { concept: string; job: Job | null; languages: string[] };
  lang: string;
  onLang: (code: string) => void;
  assetBase: string;
  onVideo: (key: string, url: string) => void;
  /** Set when this lesson is an episode of a course: the player moves on to the next episode by itself. */
  playlist?: Playlist | null;
  episode?: number;
  onEpisode?: (index: number) => void;
  onMetaverse?: () => void;
  onMetaQuiz?: () => Promise<void>;
  metaBusy?: { progress: number; stage: string } | null;
};

/** The lesson page in the grey glass layout: scene timeline, player card, side stack (progress or downloads, tutor), notes and sources. */
export const LessonPage: React.FC<Props> = (
  { lesson, generating, lang, onLang, assetBase, onVideo, playlist, episode = 0, onEpisode, onMetaverse, onMetaQuiz, metaBusy },
) => {
  const { award } = useRewards();
  const track = lesson?.languages[lang];
  const player = useRef<PlayerRef>(null);
  const frame = useRef<HTMLDivElement>(null);
  const resume = useRef<{ frac: number; playing: boolean } | null>(null);
  const tap = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finished = useRef(false);

  const [captions, setCaptions] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [quality, setQuality] = useState<720 | 1080>(720);
  const [fullscreen, setFullscreen] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [flash, setFlash] = useState<{ side: "l" | "r"; n: number } | null>(null);
  const [exportJobs, setExportJobs] = useState<Record<string, Job>>({});
  const [error, setError] = useState("");
  const [waitingNext, setWaitingNext] = useState(false);
  const [courseJob, setCourseJob] = useState<Job | null>(null);
  const [courseUrls, setCourseUrls] = useState<Record<string, string>>({});

  const inputProps = useMemo(() => (track ? { track, assetBase, captions } : null), [track, assetBase, captions]);
  const frames = track ? lessonFrames(track) : 1;

  // Follow playback: the timeline, notes and tutor follow the scene being played; finishing the lesson earns XP once.
  useEffect(() => {
    const p = player.current;
    if (!p || !track || !lesson) return;
    setSceneIndex(0);
    finished.current = false;
    const onFrame = (e: { detail: { frame: number } }) => {
      const t = e.detail.frame / FPS;
      const i = track.scenes.findIndex((s) => t >= s.start_s && t < s.start_s + s.duration_s);
      if (i >= 0) setSceneIndex(i);
      if (!finished.current && t >= track.duration_s * 0.9) {
        finished.current = true;
        award({ type: "lesson_complete", lesson_id: lesson.id, lang });
      }
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, [track, lesson, lang, award]);

  // Continuous flow: when an episode ends, start the next one; if it is still being made, wait and start it when ready.
  useEffect(() => {
    const p = player.current;
    if (!p || !playlist) return;
    const onEnd = () => {
      const next = playlist.episodes[episode + 1];
      if (!next) { award({ type: "course_complete", course_id: playlist.id }); return; }
      if (next.status === "ready") onEpisode?.(episode + 1);
      else if (next.status !== "failed") setWaitingNext(true);
    };
    p.addEventListener("ended", onEnd);
    return () => p.removeEventListener("ended", onEnd);
  }, [track, playlist, episode, onEpisode, award]);
  useEffect(() => {
    if (waitingNext && playlist?.episodes[episode + 1]?.status === "ready") { setWaitingNext(false); onEpisode?.(episode + 1); }
  }, [waitingNext, playlist, episode, onEpisode]);
  useEffect(() => { setWaitingNext(false); }, [episode, lesson?.id]);

  useEffect(() => {
    const on = () => setFullscreen(document.fullscreenElement === frame.current);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void frame.current?.requestFullscreen();
  }, []);

  const seekBy = useCallback((d: number) => {
    const p = player.current;
    if (!p) return;
    p.seekTo(Math.min(Math.max(p.getCurrentFrame() + d * FPS, 0), frames - 1));
  }, [frames]);

  // Switching language keeps your place in the lesson (the scenes line up across languages).
  const switchLang = (code: string) => {
    const p = player.current;
    resume.current = p ? { frac: p.getCurrentFrame() / frames, playing: p.isPlaying() } : null;
    onLang(code);
  };
  const initialFrame = resume.current ? Math.min(Math.round(resume.current.frac * frames), frames - 1) : 0;
  const autoPlay = resume.current ? resume.current.playing : true;

  // Tap the left or right third twice to jump 5 s; centre once to play/pause, twice for full screen.
  const onScreenClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const side = x < 0.33 ? "l" : x > 0.67 ? "r" : "c";
    if (tap.current) {
      clearTimeout(tap.current);
      tap.current = null;
      if (side === "c") toggleFullscreen();
      else { seekBy(side === "l" ? -5 : 5); setFlash((f) => ({ side, n: (f?.n ?? 0) + 1 })); }
      return;
    }
    tap.current = setTimeout(() => { tap.current = null; player.current?.toggle(); }, 230);
  };
  useEffect(() => { if (!flash) return; const t = setTimeout(() => setFlash(null), 650); return () => clearTimeout(t); }, [flash]);

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest("button,input,textarea,[role=slider]")) return;
    const p = player.current;
    if (e.key === " " || e.key === "k") { e.preventDefault(); p?.toggle(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); seekBy(5); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seekBy(-5); }
    else if (e.key === "m") { p?.isMuted() ? p.unmute() : p?.mute(); }
    else if (e.key === "c") setCaptions((c) => !c);
    else if (e.key === "f") toggleFullscreen();
  };

  const seekPlay = (seconds: number) => {
    player.current?.seekTo(Math.round(seconds * FPS));
    player.current?.play();
  };
  const getTime = () => (player.current ? player.current.getCurrentFrame() / FPS : 0);

  // ---- downloads
  const key = quality === 1080 ? `${lang}_1080p` : lang;
  const video = lesson?.videos[key];
  const job = exportJobs[key];
  const exporting = job && (job.status === "queued" || job.status === "running");
  async function exportMp4() {
    if (!lesson) return;
    setError("");
    try {
      const done = await runJob(api<Job>(`/api/lessons/${lesson.id}/export`, { lang, height: quality }),
        (j) => setExportJobs((x) => ({ ...x, [key]: j })));
      onVideo(key, done.result.url);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const totalTime = lesson ? Object.values(lesson.timings).reduce((a, b) => a + b, 0) : 0;

  // ---- the whole course as one MP4
  const courseKey = `${lang}_${quality}p`;
  const courseUrl = courseUrls[courseKey] ?? playlist?.videos?.[courseKey];
  const courseBusy = courseJob && (courseJob.status === "queued" || courseJob.status === "running");
  async function exportCourse() {
    if (!playlist) return;
    setError("");
    try {
      const done = await runJob(api<Job>(`/api/playlists/${playlist.id}/export`, { lang, height: quality }), setCourseJob);
      setCourseUrls((u) => ({ ...u, [courseKey]: done.result.url }));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const courseDone = playlist && playlist.status !== "planning" && playlist.status !== "building";
  const untranslated = track && (track.translator === "untranslated" || (track.translator === "none" && track.lang !== "en"));
  const title = track?.title ?? generating?.concept ?? "Your lesson";

  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">{playlist ? `Course · ${playlist.title}` : "Lesson"}</div>
          <h1>
            {playlist && track && <span className="ep-chip">Episode {episode + 1} of {playlist.episodes.length}</span>}
            {title}
          </h1>
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
                <Stat value={generating?.languages.length ?? 1} label="Languages" accent />
                <Stat value={8} label="Scene types" />
              </>
            )}
          </div>
        </div>
        <div className="hero-actions">
          {lesson && (
            <div className="tabs" role="tablist" aria-label="Lesson language">
              {Object.values(lesson.languages).map((t) => (
                <button key={t.lang} type="button" role="tab" aria-selected={t.lang === lang} className={t.lang === lang ? "tab on" : "tab"}
                  onClick={() => switchLang(t.lang)}>{t.native}</button>
              ))}
            </div>
          )}
          {lesson && onMetaverse && (
            <button type="button" className="round lg" onClick={onMetaverse} onPointerEnter={preloadMetaverse} onFocus={preloadMetaverse}
              aria-label="Quiz in the metaverse" title="Quiz in the metaverse"><Glyph name="cube" size={20} /></button>
          )}
        </div>
      </header>

      {track && <Timeline track={track} current={sceneIndex} onSeek={seekPlay} />}

      {track && lesson && (
        <>
          {untranslated && <div className="warn">{track.name} is showing English text because the translation model is switched off or unavailable.</div>}
          {track.tts_engines.includes("silent") && <div className="warn">No voice model installed for {track.name}; narration is a silent placeholder.</div>}
          {lesson.review?.length ? <div className="warn">Checked the lesson: {lesson.review.join("; ")}</div> : null}
        </>
      )}
      {error && <div className="notice bad" role="alert">{error}</div>}

      <div className="board">
        <div className="stack">
          <section className="aura green player-card" aria-label="Lesson player">
            <div className="aura-title">{lesson ? "Lesson player" : "Your lesson"}</div>
            {lesson && track && inputProps ? (
              <div ref={frame} className="vp" tabIndex={0} onKeyDown={onKey} aria-label="Lesson video. Space plays or pauses, arrow keys seek.">
                <div className="vp-screen">
                  <Player
                    ref={player}
                    key={`${lesson.id}-${lang}-${assetBase}`}
                    component={LessonVideo}
                    inputProps={inputProps}
                    durationInFrames={frames}
                    compositionWidth={W}
                    compositionHeight={H}
                    fps={FPS}
                    initialFrame={initialFrame}
                    autoPlay={autoPlay}
                    playbackRate={speed}
                    controls={false}
                    clickToPlay={false}
                    doubleClickToFullscreen={false}
                    style={{ width: "100%", height: "100%" }}
                    acknowledgeRemotionLicense
                  />
                  <div className="tap-layer" onClick={onScreenClick} />
                  {flash && (
                    <div key={flash.n} className={`flash ${flash.side}`} aria-hidden>
                      <Ui name={flash.side === "l" ? "back5" : "fwd5"} size={44} />
                      <span>5 s</span>
                    </div>
                  )}
                </div>
                <PlayerControls
                  player={player} track={track} captions={captions} onCaptions={setCaptions} speed={speed} onSpeed={setSpeed}
                  languages={Object.values(lesson.languages).map((t) => ({ code: t.lang, native: t.native }))}
                  lang={lang} onLang={switchLang} quality={quality} onQuality={setQuality}
                  fullscreen={fullscreen} onFullscreen={toggleFullscreen}
                />
              </div>
            ) : (
              <div className="vp">
                <div className="vp-screen wait">
                  <div className="wait-art">
                    <span className="wait-orb" aria-hidden><Glyph name="play" size={26} /></span>
                    <b>{generating?.concept ?? "Your lesson"}</b>
                    <span className="muted">The lesson plays here as soon as it is ready.</span>
                  </div>
                </div>
              </div>
            )}
          </section>

          {playlist && playlist.episodes.length > 0 && (
            <EpisodeRail playlist={playlist} current={episode} waitingForNext={waitingNext || undefined} onPick={(i) => onEpisode?.(i)} />
          )}

          {lesson && track && <NotesPanel lesson={lesson} track={track} current={sceneIndex} onSeek={seekPlay} />}
        </div>

        <div className="stack">
          {!lesson ? (
            <Pending job={generating?.job ?? null} title={playlist ? "Your course is on its way" : "Your lesson is on its way"} />
          ) : (
            <section className="aura pink" aria-label="Downloads">
              <div className="aura-title">Take it with you</div>
              <div className="aura-actions">
                {video ? (
                  <a className="glass-btn" href={url(video)} download={`${lesson.concept}-${lang}-${quality}p.mp4`}><Glyph name="download" />Download MP4 · {quality}p</a>
                ) : (
                  <button type="button" className="glass-btn" disabled={exporting} onClick={exportMp4}>
                    <Glyph name="download" />{exporting ? `${job.stage} ${Math.round(job.progress * 100)}%` : `Make MP4 · ${quality}p`}
                  </button>
                )}
                <a className="glass-btn" href={url(`/media/lessons/${lesson.id}/captions_${lang}.srt`)} download><Glyph name="captions" />Captions (.srt)</a>
                {playlist && courseDone && (courseUrl ? (
                  <a className="glass-btn" href={url(courseUrl)} download={`${playlist.title}-${lang}-${quality}p.mp4`}><Glyph name="download" />Whole course · {quality}p</a>
                ) : (
                  <button type="button" className="glass-btn" disabled={!!courseBusy} onClick={exportCourse}>
                    <Glyph name="download" />{courseBusy ? `${courseJob.stage} ${Math.round(courseJob.progress * 100)}%` : `Whole course MP4 · ${quality}p`}
                  </button>
                ))}
              </div>
            </section>
          )}
          <ChatPanel lesson={lesson} track={track} lang={lang} current={sceneIndex} getTime={getTime} onMetaQuiz={onMetaQuiz} metaBusy={metaBusy} />
          {lesson && track && (
            <>
              <section className="aura orange" aria-label="Build time">
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

                <section className="card" aria-label="Sources">
                <div className="card-title"><Glyph name="book" size={16} />Sources</div>
                {lesson.sources?.length ? (
                  <ul className="tiles" style={{ gridTemplateColumns: "1fr" }}>
                    {lesson.sources.map((s) => (
                      <li key={s.title + (s.section ?? "")} className="tile">
                        <div className="tile-top"><Glyph name={s.source === "upload" ? "book" : "link"} size={16} /><span>{s.section || (s.source === "upload" ? "your PDF" : s.source)}</span></div>
                        <div className="tile-score"><DotNumber value={Math.round(s.score * 100)} size={26} /><small>match</small></div>
                        {/^https?:/.test(s.url) ? <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : <b>{s.title}</b>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">Written from the model's own knowledge (no matching articles).</p>
                )}
                <details className="json">
                  <summary>Lesson data (JSON)</summary>
                  <pre>{JSON.stringify(track.scenes.map(({ captions: _c, audio_url: _a, ...s }) => s), null, 2)}</pre>
                </details>
              </section>
            </>
          )}
        </div>
      </div>

    </main>
  );
};
