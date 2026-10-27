import React, { useCallback, useEffect, useRef, useState } from "react";
import type { PlayerRef } from "@remotion/player";
import type { Track } from "../types";
import { FPS } from "../remotion/theme";
import { Ui } from "./ui-icons";

export const SPEEDS = [0.75, 1, 1.25, 1.5];
export const mmss = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, "0")}`;

type Props = {
  player: React.RefObject<PlayerRef>;
  track: Track;
  captions: boolean;
  onCaptions: (on: boolean) => void;
  speed: number;
  onSpeed: (s: number) => void;
  languages: { code: string; native: string }[];
  lang: string;
  onLang: (code: string) => void;
  quality: 720 | 1080;
  onQuality: (q: 720 | 1080) => void;
  fullscreen: boolean;
  onFullscreen: () => void;
  onSeek?: (t: number) => void;
};

/** Custom player bar: seek bar (tap or drag anywhere), time, scene skip, volume, captions, settings, fullscreen. */
export const PlayerControls: React.FC<Props> = (p) => {
  const { player, track } = p;
  const total = track.duration_s;
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [menu, setMenu] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const bar = useRef<HTMLDivElement>(null);
  const drag = useRef<{ resume: boolean } | null>(null);

  useEffect(() => {
    const pl = player.current;
    if (!pl) return;
    const onFrame = (e: { detail: { frame: number } }) => setFrame(e.detail.frame);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    pl.addEventListener("frameupdate", onFrame);
    pl.addEventListener("play", onPlay);
    pl.addEventListener("pause", onPause);
    pl.addEventListener("ended", onPause);
    setPlaying(pl.isPlaying());
    setFrame(pl.getCurrentFrame());
    return () => {
      pl.removeEventListener("frameupdate", onFrame);
      pl.removeEventListener("play", onPlay);
      pl.removeEventListener("pause", onPause);
      pl.removeEventListener("ended", onPause);
    };
  }, [player, track]);

  const t = frame / FPS;
  const sceneAt = (sec: number) => {
    const i = track.scenes.findIndex((s) => sec >= s.start_s && sec < s.start_s + s.duration_s);
    return i < 0 ? track.scenes.length - 1 : i;
  };
  const scene = sceneAt(t);

  const seekTo = useCallback((sec: number) => {
    const clamped = Math.min(Math.max(sec, 0), Math.max(total - 0.05, 0));
    player.current?.seekTo(Math.round(clamped * FPS));
    setFrame(Math.round(clamped * FPS));
    p.onSeek?.(clamped);
  }, [player, total, p]);

  const fromPointer = (clientX: number) => {
    const r = bar.current!.getBoundingClientRect();
    return Math.min(Math.max((clientX - r.left) / r.width, 0), 1) * total;
  };

  const toggle = () => player.current?.toggle();
  const skip = (d: number) => seekTo(t + d);
  const sceneJump = (d: number) => {
    const i = Math.min(Math.max(scene + d, 0), track.scenes.length - 1);
    // "previous" restarts the current scene first, like a music player
    seekTo(d < 0 && t - track.scenes[scene].start_s > 1.5 ? track.scenes[scene].start_s : track.scenes[i].start_s);
  };
  const setVol = (v: number) => {
    setVolume(v);
    player.current?.setVolume(v);
    if (v > 0 && muted) { player.current?.unmute(); setMuted(false); }
  };
  const toggleMute = () => {
    if (muted) player.current?.unmute(); else player.current?.mute();
    setMuted(!muted);
  };

  // Tap or drag on the bar. Audio is paused while dragging so scrubbing is silent, then resumed.
  const down = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { resume: player.current?.isPlaying() ?? false };
    if (drag.current.resume) player.current?.pause();
    seekTo(fromPointer(e.clientX));
  };
  const move = (e: React.PointerEvent) => {
    setHover(fromPointer(e.clientX));
    if (drag.current) seekTo(fromPointer(e.clientX));
  };
  const up = () => {
    if (drag.current?.resume) player.current?.play();
    drag.current = null;
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); skip(5); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); skip(-5); }
    else if (e.key === "Home") { e.preventDefault(); seekTo(0); }
    else if (e.key === "End") { e.preventDefault(); seekTo(total); }
  };

  const pct = total > 0 ? Math.min(t / total, 1) * 100 : 0;
  const hoverScene = hover === null ? null : track.scenes[sceneAt(hover)];

  return (
    <div className="controls" onClick={(e) => e.stopPropagation()}>
      <div className="seek-wrap">
        <div ref={bar} className="seek" role="slider" tabIndex={0} aria-label="Seek" aria-valuemin={0} aria-valuemax={Math.round(total)}
          aria-valuenow={Math.round(t)} aria-valuetext={`${mmss(t)} of ${mmss(total)}, scene ${scene + 1}: ${track.scenes[scene]?.heading ?? ""}`}
          onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onPointerLeave={() => setHover(null)} onKeyDown={key}>
          <div className="seek-track">
            <div className="seek-fill" style={{ width: `${pct}%` }} />
            {track.scenes.slice(1).map((s, i) => (
              <span key={i} className="seek-tick" style={{ left: `${(s.start_s / total) * 100}%` }} />
            ))}
          </div>
          <div className="seek-knob" style={{ left: `${pct}%` }} />
          {hover !== null && hoverScene && (
            <div className="seek-tip" style={{ left: `${(hover / total) * 100}%` }}>
              <b>{mmss(hover)}</b><span>{hoverScene.heading}</span>
            </div>
          )}
        </div>
      </div>

      <div className="ctrl-row">
        <button type="button" className="cbtn" aria-label="Previous scene" onClick={() => sceneJump(-1)}><Ui name="prev" /></button>
        <button type="button" className="cbtn" aria-label="Back 5 seconds" onClick={() => skip(-5)}><Ui name="back5" /></button>
        <button type="button" className="cbtn play" aria-label={playing ? "Pause" : "Play"} onClick={toggle}><Ui name={playing ? "pause" : "play"} size={26} /></button>
        <button type="button" className="cbtn" aria-label="Forward 5 seconds" onClick={() => skip(5)}><Ui name="fwd5" /></button>
        <button type="button" className="cbtn" aria-label="Next scene" onClick={() => sceneJump(1)}><Ui name="next" /></button>
        <div className="time" aria-hidden><b>{mmss(t)}</b> / {mmss(total)}</div>
        <div className="scene-now" aria-hidden>{scene + 1}/{track.scenes.length} · {track.scenes[scene]?.heading}</div>

        <div className="spacer" />
        <div className="vol">
          <button type="button" className="cbtn" aria-label={muted ? "Unmute" : "Mute"} onClick={toggleMute}><Ui name={muted || volume === 0 ? "mute" : "volume"} /></button>
          <input type="range" min={0} max={1} step={0.05} value={muted ? 0 : volume} aria-label="Volume" onChange={(e) => setVol(Number(e.target.value))} />
        </div>
        <button type="button" className={`cbtn ${p.captions ? "lit" : ""}`} aria-label="Captions" aria-pressed={p.captions} onClick={() => p.onCaptions(!p.captions)}><Ui name="cc" /></button>
        <div className="menu-anchor">
          <button type="button" className={`cbtn ${menu ? "lit" : ""}`} aria-label="Settings" aria-expanded={menu} onClick={() => setMenu(!menu)}><Ui name="gear" /></button>
          {menu && (
            <div className="menu" role="dialog" aria-label="Player settings">
              <div className="menu-sec">
                <div className="menu-h">Language</div>
                <div className="opts">
                  {p.languages.map((l) => (
                    <button type="button" key={l.code} className={l.code === p.lang ? "opt on" : "opt"} onClick={() => p.onLang(l.code)}>{l.native}</button>
                  ))}
                </div>
              </div>
              <div className="menu-sec">
                <div className="menu-h">Speed</div>
                <div className="opts">
                  {SPEEDS.map((s) => (
                    <button type="button" key={s} className={s === p.speed ? "opt on" : "opt"} onClick={() => p.onSpeed(s)}>{s === 1 ? "Normal" : `${s}×`}</button>
                  ))}
                </div>
              </div>
              <div className="menu-sec">
                <div className="menu-h">Captions</div>
                <div className="opts">
                  <button type="button" className={p.captions ? "opt on" : "opt"} onClick={() => p.onCaptions(true)}>On</button>
                  <button type="button" className={!p.captions ? "opt on" : "opt"} onClick={() => p.onCaptions(false)}>Off</button>
                </div>
              </div>
              <div className="menu-sec">
                <div className="menu-h">Download quality</div>
                <div className="opts">
                  <button type="button" className={p.quality === 720 ? "opt on" : "opt"} onClick={() => p.onQuality(720)}>720p · faster</button>
                  <button type="button" className={p.quality === 1080 ? "opt on" : "opt"} onClick={() => p.onQuality(1080)}>1080p · boost</button>
                </div>
              </div>
            </div>
          )}
        </div>
        <button type="button" className="cbtn" aria-label={p.fullscreen ? "Exit full screen" : "Full screen"} onClick={p.onFullscreen}><Ui name={p.fullscreen ? "unfull" : "full"} /></button>
      </div>
    </div>
  );
};
