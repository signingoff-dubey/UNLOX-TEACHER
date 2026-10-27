// Mirrors the JSON produced by backend/app/pipeline.py

export type TemplateName =
  | "title" | "bullets" | "flow" | "cycle" | "compare" | "diagram" | "quiz" | "summary";

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
  /** Knowledge-base articles retrieved to ground the lesson (RAG). */
  sources?: { title: string; url: string; source: string; score: number }[];
  timings: Record<string, number>;
  videos: Record<string, string>;
};

export type LessonProps = {
  track: Track;
  /** Prefix for audio and font URLs: "" in the browser, the backend URL when rendering MP4. */
  assetBase: string;
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
