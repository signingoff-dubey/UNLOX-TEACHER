import { useCallback, useEffect, useRef, useState } from "react";
import { api, url } from "../api";
import type { Difficulty, Size, StudioKind, StudioResult } from "./types";

export type ToolState = { state: "none" | "queued" | "building" | "ready" | "error"; progress: number; stage: string; error: string | null };
export type ToolMap = Record<StudioKind, ToolState>;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * The backend writes every study tool of a lesson in the background. This follows its progress: quickly while something
 * is being made, slowly once everything is ready.
 */
export function useStudioStatus(lessonId: string | undefined, lang: string) {
  const [tools, setTools] = useState<ToolMap | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setTools(null);
    if (!lessonId) return;
    let alive = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const r = await api<{ tools: ToolMap }>(`/api/lessons/${lessonId}/studio?lang=${encodeURIComponent(lang)}`);
        if (!alive) return;
        setTools(r.tools);
        const pending = Object.values(r.tools).some((t) => t.state !== "ready" && t.state !== "error");
        timer = window.setTimeout(poll, pending ? 1200 : 10000);
      } catch {
        if (alive) timer = window.setTimeout(poll, 4000);
      }
    };
    void poll();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [lessonId, lang, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { tools, refresh };
}

/** Put a tool at the front of the build queue (a click). */
export function requestTool(lessonId: string, kind: StudioKind, lang: string, size: Size = "standard", difficulty: Difficulty = "medium") {
  return api<ToolState>(`/api/lessons/${lessonId}/studio`, { kind, lang, size, difficulty });
}

async function fetchResult(lessonId: string, kind: StudioKind, lang: string, size: Size, difficulty: Difficulty): Promise<StudioResult | null> {
  const r = await fetch(url(`/api/lessons/${lessonId}/studio/${kind}?lang=${encodeURIComponent(lang)}&size=${size}&difficulty=${difficulty}`));
  return r.ok ? ((await r.json()) as StudioResult) : null;
}

/** One tool: shown at once if it is already built, otherwise built now (with progress) and shown when done. */
export function useStudioResult(lessonId: string, kind: StudioKind, lang: string, size: Size, difficulty: Difficulty, attempt: number) {
  const [result, setResult] = useState<StudioResult | null>(null);
  const [progress, setProgress] = useState<{ value: number; stage: string }>({ value: 0, stage: "" });
  const [error, setError] = useState("");
  const run = useRef(0);

  useEffect(() => {
    const mine = ++run.current;
    const live = () => mine === run.current;
    setResult(null); setError(""); setProgress({ value: 0, stage: "" });
    (async () => {
      const ready = await fetchResult(lessonId, kind, lang, size, difficulty);
      if (!live()) return;
      if (ready) { setResult(ready); return; }
      await requestTool(lessonId, kind, lang, size, difficulty);
      for (;;) {
        await sleep(900);
        if (!live()) return;
        const s = await api<{ tools: ToolMap }>(`/api/lessons/${lessonId}/studio?lang=${encodeURIComponent(lang)}&size=${size}&difficulty=${difficulty}`);
        if (!live()) return;
        const t = s.tools[kind];
        setProgress({ value: t.progress, stage: t.stage });
        if (t.state === "ready") { setResult(await fetchResult(lessonId, kind, lang, size, difficulty)); return; }
        if (t.state === "error") { setError(t.error ?? "Could not make this."); return; }
      }
    })().catch((e: Error) => live() && setError(e.message));
  }, [lessonId, kind, lang, size, difficulty, attempt]);

  return { result, progress, error };
}
