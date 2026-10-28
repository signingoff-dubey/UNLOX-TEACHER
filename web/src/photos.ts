import { runJob, url } from "./api";
import type { Job } from "./types";

export type Mode = "study" | "homework" | "explain" | "revise";

/** A photo attached to the prompt. llava reads it in the backend; `topic` is what it found. */
export type PhotoItem = { key: string; id?: string; name: string; preview: string; status: "reading" | "ready" | "error"; topic?: string; error?: string };

/** Upload one photo (POST /api/images starts a job; its result holds the id and the topic). */
export async function uploadPhoto(file: File, onId: (id: string) => void): Promise<{ id: string; topic: string }> {
  const form = new FormData();
  form.append("file", file);
  const start = fetch(url("/api/images"), { method: "POST", body: form }).then(async (r) => {
    const body = await r.json().catch(() => null);
    if (!r.ok) throw new Error(body?.detail ?? `Upload failed (${r.status})`);
    return body as Job;
  });
  const first = await start;
  const early = (first as Job & { image_id?: string }).image_id;
  if (early) onId(early);                                       // the photo can be used right away: its text is read by whoever needs it first
  const done = await runJob(Promise.resolve(first), () => undefined);
  const res = done.result as { id: string; topic: string };
  onId(res.id);
  return res;
}
