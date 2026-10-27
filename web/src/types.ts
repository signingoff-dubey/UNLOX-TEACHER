// Mirrors the JSON produced by backend/app/pipeline.py

export type TemplateName =
  | "title" | "bullets" | "flow" | "cycle" | "compare" | "diagram" | "quiz" | "summary" | "graph" | "code" | "network";

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
  /** network scenes: boxes and arrows; `positions` ([x, y] of each node in a 1000 x 420 box) is computed by the backend */
  nodes?: string[];
  edges?: { src: number; dst: number }[];
  positions?: number[][];
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
  /** "nllb" | "indictrans2" | "ollama" | "none" | "untranslated" (model failed, English kept) */
  translator?: string;
  /** Citation shown on the recap scene, e.g. "Source: Science 8, Ch 3, pp. 41–44". */
  source_note?: string;
};

export type Source = { title: string; section?: string; url: string; source: string; score: number };

export type UploadStatus = {
  pages: number;
  digital: number;
  scanned: number;
  tesseract_done: number;
  unlimited_done: number;
  failed: number;
  low_confidence: number;
  state: "ocr" | "upgrading" | "ready";
  /** Study notes written 30 pages at a time while the PDF is read. */
  notes?: { total: number; done: number };
};

export type Lesson = {
  id: string;
  concept: string;
  created: number;
  languages: Record<string, Track>;
  /** Languages still being made (one by one) and the ones that failed. */
  pending?: { code: string; name: string; native: string }[];
  /** True while the first scenes can already be watched and the rest are still being made; `scenes_total` is about how many there will be. */
  building?: boolean;
  scenes_total?: number;
  failed?: { code: string; name: string; error: string }[];
  /** Articles or PDF pages retrieved to ground the lesson (RAG). */
  sources?: Source[];
  /** Set when the lesson was made from an uploaded PDF. */
  upload?: string | null;
  focus?: string;
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
  /** Set once the first scenes of a lesson are ready to watch (the lesson is still being made). */
  lesson_id?: string;
};
