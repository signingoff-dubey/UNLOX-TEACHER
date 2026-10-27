// Mirrors the JSON produced by backend/app/pipeline.py

export type TemplateName =
  | "title" | "bullets" | "flow" | "cycle" | "compare" | "diagram" | "quiz" | "summary" | "graph" | "code";

export type Caption = { start: number; end: number; text: string };

export type Scene = {
  template: TemplateName;
  heading: string;
  narration: string;
  items: string[];
  icon: string;
  left_title: string;
  right_title: string;
  left: string[];
  right: string[];
  answer_index: number;
  /** graph scenes: plain numbers, drawn by web/src/remotion/graph.tsx (never evaluated) */
  curves?: { type: string; a: number; b: number; c: number; d: number }[];
  marks?: { kind: string; x: number; y: number }[];
  x_range?: number[];
  y_range?: number[];
  equation?: string;
  /** code scenes: display text only, drawn by web/src/remotion/code.tsx */
  code_lang?: string;
  code?: string[];
  highlights?: number[];
  output?: string[];
  audio_url?: string;
  speech_s: number;
  duration_s: number;
  start_s: number;
  captions: Caption[];
};

export type Track = {
  lang: string;
  name: string;
  native: string;
  title: string;
  scenes: Scene[];
  duration_s: number;
  tts_engines: string[];
  /** "indictrans2" | "ollama" | "none" | "untranslated" (model failed, English kept) */
  translator?: string;
};

export type Lesson = {
  id: string;
  concept: string;
  created: number;
  languages: Record<string, Track>;
  timings: Record<string, number>;
  videos: Record<string, string>;
  /** English source plan (tutor context) and notes from the lesson reviewer. */
  plan?: unknown;
  review?: string[];
};

export type LessonProps = {
  track: Track;
  /** Prefix for audio and font URLs: "" in the browser, the backend URL when rendering MP4. */
  assetBase: string;
  /** Show burned-in captions. Defaults to true; the in-browser player can turn them off. */
  captions?: boolean;
};

export type Job = {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  result: any;
  error: string | null;
};
