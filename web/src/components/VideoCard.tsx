import React, { useEffect, useMemo, useState } from "react";
import { Thumbnail } from "@remotion/player";
import { api, getApiBase } from "../api";
import type { Job, Lesson } from "../types";
import { LessonVideo, lessonFrames } from "../remotion/Lesson";
import { FPS, H, W } from "../remotion/theme";
import { Ui } from "./ui-icons";

/** A video the tutor chat started on request ("generate one more video on ..."), as the backend describes it. */
export type ChatVideo = { playlist_id: string; index: number; job_id: string; topic: string; title: string; seconds: number };

type Props = {
  video: ChatVideo;
  lang: string;
  /** Opens it in the player (and in the playlist) on the lesson page. */
  onPlay: (playlistId: string, index: number) => void;
};

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/**
 * The video in the chat: a spinner while it is planned, then its first frame with a play button as soon as the first scene exists,
 * and a line that counts the scenes while the rest is still being made.
 */
export const VideoCard: React.FC<Props> = ({ video, lang, onPlay }) => {
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const jobOpen = !job || job.status === "queued" || job.status === "running";
  const lessonId = job?.lesson_id ?? (job?.result as { lesson_id?: string } | null)?.lesson_id ?? undefined;

  useEffect(() => {
    if (!jobOpen) return;
    let off = false;
    const tick = () => api<Job>(`/api/jobs/${video.job_id}`).then((j) => { if (!off) setJob(j); }).catch(() => undefined);
    void tick();
    const t = setInterval(tick, 1200);
    return () => { off = true; clearInterval(t); };
  }, [video.job_id, jobOpen]);

  const settled = !!lesson && lesson.id === lessonId && !lesson.building;
  useEffect(() => {
    if (!lessonId || settled) return;
    let off = false;
    const tick = () => api<Lesson>(`/api/lessons/${lessonId}`).then((l) => { if (!off) setLesson(l); }).catch(() => undefined);
    void tick();
    const t = setInterval(tick, 1500);
    return () => { off = true; clearInterval(t); };
  }, [lessonId, settled]);

  const track = lesson ? lesson.languages[lang] ?? Object.values(lesson.languages)[0] : undefined;
  const scenes = track?.scenes.length ?? 0;
  const first = track?.scenes[0];
  // Only scene 1 is drawn, and only when it changes: polling must not redraw the picture every second.
  const thumb = useMemo(() => (track && first ? { ...track, scenes: [first] } : null), [first?.audio_url, first?.heading, track?.lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const failed = job?.status === "error";
  const ready = scenes > 0;

  return (
    <div className={`vcard${ready ? " ready" : ""}${failed ? " failed" : ""}`} role="group" aria-label={`Video: ${video.title}`}>
      <div className="vposter">
        {thumb ? (
          <Thumbnail component={LessonVideo} inputProps={{ track: thumb, assetBase: getApiBase(), captions: false }}
            compositionWidth={W} compositionHeight={H} frameToDisplay={Math.min(24, Math.max(lessonFrames(thumb) - 1, 0))}
            durationInFrames={Math.max(lessonFrames(thumb), 1)} fps={FPS} style={{ width: "100%", height: "100%" }} />
        ) : (
          <div className="vwait">{failed ? <span>Could not be made</span> : <><span className="tab-spin" aria-hidden /><span>{job?.stage ?? "Starting"}</span></>}</div>
        )}
        {ready && (
          <button type="button" className="vplay" onClick={() => onPlay(video.playlist_id, video.index)} aria-label={`Play ${track?.title ?? video.title}`}>
            <Ui name="play" size={26} />
          </button>
        )}
      </div>
      <div className="vmeta">
        <b>{track?.title ?? video.title}</b>
        <span>
          {failed ? job?.error ?? "Something went wrong."
            : !ready ? `Making it, about ${video.seconds} s`
            : lesson?.building ? `${scenes} of about ${Math.max(lesson.scenes_total ?? 0, scenes)} scenes ready, the rest is on its way`
            : `Ready · ${mmss(track?.duration_s ?? video.seconds)} · added to the playlist`}
        </span>
      </div>
    </div>
  );
};
