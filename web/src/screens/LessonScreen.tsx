import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import type { Job, Lesson } from "../types";
import { api, runJob, url } from "../api";
import { LessonVideo, lessonFrames } from "../remotion/Lesson";
import { FPS, H, W } from "../remotion/theme";
import { PlayerControls } from "../components/PlayerControls";
import { SceneList } from "../components/SceneList";
import { Ui } from "../components/ui-icons";

type Props = {
  lesson: Lesson;
  lang: string;
  onLang: (code: string) => void;
  assetBase: string;
  onBack: () => void;
  onVideo: (key: string, url: string) => void;
};

/** Screen 3: the lesson. Video with tap zones, full control bar, scene list, downloads. */
export const LessonScreen: React.FC<Props> = ({ lesson, lang, onLang, assetBase, onBack, onVideo }) => {
  const track = lesson.languages[lang];
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

  const inputProps = useMemo(() => ({ track, assetBase, captions }), [track, assetBase, captions]);
  const frames = lessonFrames(track);

  // Highlight the scene being played in the list.
  useEffect(() => {
    const p = player.current;
    if (!p) return;
    const onFrame = (e: { detail: { frame: number } }) => {
      const t = e.detail.frame / FPS;
      const i = track.scenes.findIndex((s) => t >= s.start_s && t < s.start_s + s.duration_s);
      if (i >= 0) setSceneIndex(i);
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, [track]);

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
    if ((e.target as HTMLElement).closest("button,input,[role=slider]")) return;
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

  // ---- downloads
  const key = quality === 1080 ? `${lang}_1080p` : lang;
  const video = lesson.videos[key];
  const job = exportJobs[key];
  const exporting = job && (job.status === "queued" || job.status === "running");
  async function exportMp4() {
    setError("");
    try {
      const done = await runJob(api<Job>(`/api/lessons/${lesson.id}/export`, { lang, height: quality }),
        (j) => setExportJobs((x) => ({ ...x, [key]: j })));
      onVideo(key, done.result.url);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const totalTime = Object.values(lesson.timings).reduce((a, b) => a + b, 0);

  return (
    <div className="screen lesson">
      <header className="lesson-top">
        <button type="button" className="ghost back" onClick={onBack}><Ui name="arrowLeft" size={18} />New lesson</button>
        <h1>{track.title}</h1>
        <div className="tabs" role="tablist" aria-label="Lesson language">
          {Object.values(lesson.languages).map((t) => (
            <button key={t.lang} type="button" role="tab" aria-selected={t.lang === lang} className={t.lang === lang ? "tab on" : "tab"}
              onClick={() => switchLang(t.lang)}>{t.native}</button>
          ))}
        </div>
      </header>

      <div className="lesson-main">
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

        <aside className="lesson-side">
          <section className="card flat">
            <div className="label">Scenes <span className="muted">tap to jump</span></div>
            <SceneList track={track} current={sceneIndex} onSeek={seekPlay} />
          </section>

          <section className="card flat">
            <div className="label">Save this lesson</div>
            <div className="dl">
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
            </div>
            <div className="muted note">{quality === 720 ? "720p renders about 2× faster. Switch to 1080p in ⚙ Settings." : "1080p takes longer to render."}</div>
          </section>
        </aside>
      </div>

      {track.translator === "untranslated" && <div className="warn">Translation model unavailable; {track.name} shows the English text.</div>}
      {track.tts_engines.includes("silent") && <div className="warn">No voice model installed for {track.name}; narration is a silent placeholder.</div>}
      {error && <div className="error" role="alert">{error}</div>}

      <div className="lesson-foot muted">
        {track.scenes.length} scenes · {track.duration_s.toFixed(0)} s · made in {totalTime.toFixed(1)} s
        <details className="json">
          <summary>Lesson data (JSON)</summary>
          <pre>{JSON.stringify(track.scenes.map(({ captions: _c, audio_url: _a, ...s }) => s), null, 2)}</pre>
        </details>
      </div>
    </div>
  );
};
