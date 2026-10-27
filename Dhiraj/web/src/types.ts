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
};

export type Lesson = {
  id: string;
  concept: string;
  created: number;
  languages: Record<string, Track>;
  /** Articles or PDF pages retrieved to ground the lesson (RAG). */
  sources?: Source[];
  /** Set when the lesson was made from an uploaded PDF. */
  upload?: string | null;
  focus?: string;
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
