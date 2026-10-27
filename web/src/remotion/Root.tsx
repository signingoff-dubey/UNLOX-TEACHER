import React from "react";
import { Composition } from "remotion";
import type { LessonProps } from "../types";
import { LessonVideo, lessonFrames } from "./Lesson";
import { sampleTrack } from "./sample";
import { FPS, H, W } from "./theme";

export const Root: React.FC = () => (
  <Composition
    id="Lesson"
    component={LessonVideo}
    width={W}
    height={H}
    fps={FPS}
    durationInFrames={lessonFrames(sampleTrack)}
    defaultProps={{ track: sampleTrack, assetBase: "" } satisfies LessonProps}
    // Length is decided by the narration, so it is computed from the props at render time.
    calculateMetadata={({ props }) => ({ durationInFrames: lessonFrames(props.track) })}
  />
);
