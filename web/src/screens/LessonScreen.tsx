import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import type { Job, Lesson } from "../types";
import { api, runJob, url, type Playlist } from "../api";
import { EpisodeRail } from "../components/EpisodeRail";
import { LessonVideo, lessonFrames } from "../remotion/Lesson";
import { FPS, H, W } from "../remotion/theme";
import { ChatPanel } from "../components/ChatPanel";
import { preloadMetaverse } from "../components/MetaverseLayer";
import { Generating } from "../components/Generating";
import { NotesPanel } from "../components/NotesPanel";
import { PlayerControls } from "../components/PlayerControls";
import { Ui } from "../components/ui-icons";

type Props = {
  /** null while the lesson is still being made; `generating` then describes the job. */
  lesson: Lesson | null;
  generating?: { concept: string; job: Job | null; languages: string[] };
  lang: string;
  onLang: (code: string) => void;
  assetBase: string;
  onBack: () => void;
  onVideo: (key: string, url: string) => void;
  /** Set when this lesson is an episode of a course: the player moves on to the next episode by itself. */
  playlist?: Playlist | null;
  episode?: number;
  onEpisode?: (index: number) => void;
  /** Opens the 3D quiz world built from this lesson. */
  onMetaverse?: () => void;
  /** Meta quiz: a metaverse world from every study tool and every video; `metaBusy` is its progress. */
  onMetaQuiz?: () => Promise<void>;
  metaBusy?: { progress: number; stage: string } | null;
};

/** The lesson screen: notes on the left, video in the middle, tutor chat on the right. */
export const LessonScreen: React.FC<Props> = (
  { lesson, generating, lang, onLang, assetBase, onBack, onVideo, playlist, episode = 0, onEpisode, onMetaverse, onMetaQuiz, metaBusy },
) => {
  const track = lesson?.languages[lang];
  const player = useRef<PlayerRef>(null);
  const frame = useRef<HTMLDivElement>(null);
  const resume = useRef<{ frac: number; playing: boolean } | null>(null);
  const tap = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Keep the notes and the tutor in step with the scene being played.
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

  // Continuous flow: when an episode ends, start the next one; if it is still being made, wait and start it when ready.
  useEffect(() => {
    const p = player.current;
    if (!p || !playlist) return;
    const onEnd = () => {
      const next = playlist.episodes[episode + 1];
      if (!next) return;
      if (next.status === "ready") onEpisode?.(episode + 1);
      else if (next.status !== "failed") setWaitingNext(true);
    };
    p.addEventListener("ended", onEnd);
    return () => p.removeEventListener("ended", onEnd);
  }, [track, playlist, episode, onEpisode]);
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

  return (
    <div className="screen lesson">
      <header className="lesson-top">
        <button type="button" className="ghost back" onClick={onBack}><Ui name="arrowLeft" size={18} />New lesson</button>
        <h1>
          {playlist && track && <span className="ep-chip">Episode {episode + 1} of {playlist.episodes.length}</span>}
          {track?.title ?? generating?.concept ?? "Lesson"}
        </h1>
        {lesson && (
          <div className="tabs" role="tablist" aria-label="Lesson language">
            {Object.values(lesson.languages).map((t) => (
              <button key={t.lang} type="button" role="tab" aria-selected={t.lang === lang} className={t.lang === lang ? "tab on" : "tab"}
                onClick={() => switchLang(t.lang)}>{t.native}</button>
            ))}
          </div>
        )}
        {lesson && onMetaverse && (
          <button type="button" className="ghost metaverse-btn" onClick={onMetaverse} onPointerEnter={preloadMetaverse} onFocus={preloadMetaverse}>Quiz in the metaverse</button>
        )}
      </header>

      <div className="lesson-main three">
        <div className="col-notes">
          <NotesPanel lesson={lesson} track={track} current={sceneIndex} onSeek={seekPlay} />
        </div>

        <div className="col-stage">
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
              <div className="vp-screen gen-screen">
                {generating && <Generating concept={generating.concept} job={generating.job} languages={generating.languages} />}
              </div>
              <div className="controls ghosted" aria-hidden>
                <div className="seek-wrap"><div className="seek-track" /></div>
                <div className="ctrl-row"><span className="time">0:00 / 0:00</span></div>
              </div>
            </div>
          )}

          {lesson && track && (
            <>
              {untranslated && <div className="warn">{track.name} is showing English text because the translation model is switched off or unavailable.</div>}
              {track.tts_engines.includes("silent") && <div className="warn">No voice model installed for {track.name}; narration is a silent placeholder.</div>}
              {lesson.review?.length ? <div className="warn">Checked the lesson: {lesson.review.join("; ")}</div> : null}
              {error && <div className="error" role="alert">{error}</div>}

              <div className="dl-row">
                {video ? (
                  <a className="primary" href={url(video)} download={`${lesson.concept}-${lang}-${quality}p.mp4`}>
                    <Ui name="download" size={18} />Download MP4 · {quality}p
                  </a>
                ) : (
                  <button type="button" className="primary" disabled={exporting} onClick={exportMp4}>
                    <Ui name="download" size={18} />
                    {exporting ? `${job.stage} ${Math.round(job.progress * 100)}%` : `Make MP4 · ${quality}p`}
                  </button>
                )}
                <a className="ghost" href={url(`/media/lessons/${lesson.id}/captions_${lang}.srt`)} download>Captions (.srt)</a>
                {playlist && courseDone && (courseUrl ? (
                  <a className="primary alt" href={url(courseUrl)} download={`${playlist.title}-${lang}-${quality}p.mp4`}>
                    <Ui name="download" size={18} />Whole course · {quality}p
                  </a>
                ) : (
                  <button type="button" className="primary alt" disabled={!!courseBusy} onClick={exportCourse}>
                    <Ui name="download" size={18} />
                    {courseBusy ? `${courseJob.stage} ${Math.round(courseJob.progress * 100)}%` : `Make whole course MP4 · ${quality}p`}
                  </button>
                ))}
                <span className="muted dl-note">{track.scenes.length} scenes · {track.duration_s.toFixed(0)} s · made in {totalTime.toFixed(1)} s</span>
              </div>
            </>
          )}

          {playlist && playlist.episodes.length > 0 && (
            <EpisodeRail playlist={playlist} current={episode} waitingForNext={waitingNext || undefined} onPick={(i) => onEpisode?.(i)} />
          )}
        </div>

        <div className="col-chat">
          <ChatPanel lesson={lesson} track={track} lang={lang} current={sceneIndex} getTime={getTime} onMetaQuiz={onMetaQuiz} metaBusy={metaBusy} />
        </div>
      </div>
    </div>
  );
};
