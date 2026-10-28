import type { Job } from "./types";

const KEY = "vt.apiBase";

/** Where the backend lives. "" means same origin (the backend serves this UI, or the dev proxy).
 *  Can be changed in the UI to point at another laptop on the network. */
export function getApiBase(): string {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved !== null) return saved;
  } catch {
    /* storage blocked: fall through */
  }
  return (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
}

export function setApiBase(base: string) {
  const clean = base.trim().replace(/\/$/, "");
  try {
    if (clean) localStorage.setItem(KEY, clean);
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** Absolute URL for a backend path such as /media/... */
export const url = (path: string) => getApiBase() + path;

/** The backend's error as a sentence, whatever its shape (a string, FastAPI's list of {loc, msg}, or an object). Never "[object Object]". */
export function errorText(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      if (typeof d === "string") return d;
      const e = d as { loc?: unknown[]; msg?: string };
      const where = (e.loc ?? []).filter((x) => x !== "body" && x !== "query").join(".");
      return where ? `${where}: ${e.msg ?? "invalid"}` : e.msg ?? JSON.stringify(d);
    });
    if (parts.length) return parts.join("; ");
  }
  if (detail && typeof detail === "object") return (detail as { message?: string }).message ?? JSON.stringify(detail);
  return fallback;
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(url(path), body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(errorText((await res.json().catch(() => null))?.detail, `${res.status} ${res.statusText}`));
  return res.json();
}

/** Poll a backend job until it finishes, reporting progress along the way. */
export async function runJob(start: Promise<Job>, onUpdate: (j: Job) => void, intervalMs = 600): Promise<Job> {
  let job = await start;
  while (job.status === "queued" || job.status === "running") {
    onUpdate(job);
    await new Promise((r) => setTimeout(r, intervalMs));
    job = await api<Job>(`/api/jobs/${job.id}`);
  }
  onUpdate(job);
  if (job.status === "error") throw new Error(job.error ?? "Job failed");
  return job;
}

export type Health = {
  llm: { backend: string; model: string; ollama: { ok: boolean; models: string[] } };
  knowledge: { enabled: boolean; ready: boolean; chunks?: number; articles?: number; error?: string };
  translate: { backend: string; model: string; toolkit_installed: boolean };
  tts: { engine: string; fallback: string; piper_voices: string[]; parler_installed: boolean; parler_model: string };
  render: { web_dir_ok: boolean; node_modules_ok: boolean };
  device: string;
};

export type LessonSummary = {
  id: string;
  concept: string;
  created: number;
  languages: string[];
  videos: string[];
};

export type Lang = { code: string; name: string; native: string; piper: boolean };

export type PlaylistEpisode = {
  index: number; title: string; focus: string; lesson_id: string | null;
  status: "pending" | "building" | "ready" | "failed"; duration_s?: number; error?: string | null;
  /** The first scenes exist (lesson_id is set) while the rest is still being made: it can be played already. */
  preview?: boolean;
};
/** Ready, or being made but with its first scenes already watchable. */
export const playable = (e: PlaylistEpisode | undefined): boolean => !!e && !!e.lesson_id && (e.status === "ready" || e.status === "building");
export type Playlist = {
  id: string; topic: string; title: string; languages: string[];
  status: "planning" | "building" | "ready" | "partial" | "error";
  episodes: PlaylistEpisode[]; videos?: Record<string, string>; error?: string | null;
};
export type PlaylistSummary = { id: string; topic: string; title: string; created: number; status: string; episodes: number; ready: number };

export type Level = "beginner" | "intermediate";
/** Flash: the first scenes are shown within seconds while the rest is still being written. Pro: the whole video is outlined and planned first (slower, more coherent). */
export type Quality = "flash" | "pro";
export type LessonSettings = { level: Level; duration_s: number; languages: string[]; quality: Quality };
