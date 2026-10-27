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

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(url(path), body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `${res.status} ${res.statusText}`);
  return res.json();
}

/** Poll a backend job until it finishes, reporting progress along the way. */
export async function runJob(start: Promise<Job>, onUpdate: (j: Job) => void): Promise<Job> {
  let job = await start;
  while (job.status === "queued" || job.status === "running") {
    onUpdate(job);
    await new Promise((r) => setTimeout(r, 600));
    job = await api<Job>(`/api/jobs/${job.id}`);
  }
  onUpdate(job);
  if (job.status === "error") throw new Error(job.error ?? "Job failed");
  return job;
}

export type Health = {
  llm: { backend: string; model: string; ollama: { ok: boolean; models: string[] } };
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
