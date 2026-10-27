import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { LessonProps, Scene, Track } from "../types";
import { useFonts } from "./fonts";
import { TEMPLATES } from "./templates";
import { C, FONT_STACK, FPS, STAGE, W, fit } from "./theme";

/** Total frames: the sum of the narration-driven scene lengths. */
export const lessonFrames = (track: Track, fps = FPS) =>
  Math.max(1, Math.round(track.duration_s * fps));

export const LessonVideo: React.FC<LessonProps> = ({ track, assetBase, captions = true }) => {
  const { fps } = useVideoConfig();
  useFonts(assetBase);
  return (
    <AbsoluteFill style={{
      fontFamily: FONT_STACK, color: C.ink, background: C.paper,
      backgroundImage: `linear-gradient(${C.grid} 2px, transparent 2px), linear-gradient(90deg, ${C.grid} 2px, transparent 2px)`,
      backgroundSize: "60px 60px",
    }}>
      {track.scenes.map((scene, i) => {
        // Frame boundaries come from cumulative times, so rounding never leaves gaps.
        const from = Math.round(scene.start_s * fps);
        const to = Math.round((scene.start_s + scene.duration_s) * fps);
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)} name={`${i + 1}. ${scene.template}`}>
            <SceneFrame scene={scene} index={i} track={track} assetBase={assetBase} captions={captions} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const SceneFrame: React.FC<{ scene: Scene; index: number; track: Track; assetBase: string; captions: boolean }> = (
  { scene, index, track, assetBase, captions },
) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const Template = TEMPLATES[scene.template] ?? TEMPLATES.title;
  const speechFrames = Math.max(1, Math.round(scene.speech_s * fps));
  const fade = interpolate(frame, [0, 8, durationInFrames - 7, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      {scene.audio_url ? <Audio src={assetBase + scene.audio_url} /> : null}
      <Header title={track.title} index={index} count={track.scenes.length} />
      <AbsoluteFill style={{ opacity: fade }}>
        <Template scene={scene} speechFrames={speechFrames} lessonTitle={track.title} />
      </AbsoluteFill>
      {captions ? <Captions scene={scene} /> : null}
    </AbsoluteFill>
  );
};

const Header: React.FC<{ title: string; index: number; count: number }> = ({ title, index, count }) => (
  <div style={{ position: "absolute", top: 40, left: STAGE.left, right: STAGE.left, height: 60,
    display: "flex", alignItems: "center", justifyContent: "space-between" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 30, fontWeight: 700, color: C.muted }}>
      <div style={{ width: 18, height: 18, borderRadius: 5, background: C.saffron }} />
      {title}
    </div>
    <div style={{ display: "flex", gap: 10 }}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} style={{ width: i === index ? 44 : 14, height: 14, borderRadius: 7,
          background: i <= index ? C.teal : C.line }} />
      ))}
    </div>
  </div>
);

const Captions: React.FC<{ scene: Scene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cue = scene.captions.find((c) => t >= c.start && t < c.end + 0.15);
  if (!cue) return null;
  const local = (t - cue.start) * fps;
  const o = interpolate(local, [0, 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: STAGE.bottom + 40, display: "flex", justifyContent: "center" }}>
      <div style={{ maxWidth: 1640, background: "rgba(31,42,68,0.92)", color: "#fff", borderRadius: 22,
        padding: "16px 40px", fontSize: fit(cue.text, 44, 60, 0.8), fontWeight: 600, lineHeight: 1.4,
        textAlign: "center", opacity: o }}>
        {cue.text}
      </div>
    </div>
  );
};
