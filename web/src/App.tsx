import React, { useCallback, useEffect, useState } from "react";
import type { Job, Lesson } from "./types";
import { api, getApiBase, runJob, type Lang, type LessonSettings, type LessonSummary } from "./api";
import { Home } from "./screens/Home";
import { LessonScreen } from "./screens/LessonScreen";
import type { UploadItem } from "./components/UploadArea";

type Screen = "home" | "lesson";

/** Two screens: Home (ask) -> Lesson (notes | video | tutor). Progress shows inside the video area. A lesson id in the URL hash opens it directly. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [settings, setSettings] = useState<LessonSettings>({ level: "beginner", duration_s: 60, languages: ["en", "hi"] });
  const [concept, setConcept] = useState("");
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [active, setActive] = useState("en");
  const [recent, setRecent] = useState<LessonSummary[]>([]);
  const [error, setError] = useState("");
  const [assetBase, setAssetBase] = useState(getApiBase());
  const run = React.useRef(0);                      // ignore results of a lesson the user already left

  const loadLists = useCallback(() => {
    setAssetBase(getApiBase());
    api<Lang[]>("/api/languages").then(setLanguages).catch(() => setLanguages([]));
    api<LessonSummary[]>("/api/lessons").then(setRecent).catch(() => setRecent([]));
  }, []);

  const show = useCallback((l: Lesson, preferred?: string[]) => {
    setLesson(l);
    setActive((preferred ?? []).find((c) => c in l.languages) ?? Object.keys(l.languages)[0]);
    setScreen("lesson");
    window.history.replaceState(null, "", `#${l.id}`);
  }, []);

  const openLesson = useCallback((id: string) => {
    setError("");
    api<Lesson>(`/api/lessons/${id}`).then((l) => show(l)).catch(() => {
      setError("That lesson could not be loaded.");
      setScreen("home");
    });
  }, [show]);

  useEffect(() => {
    loadLists();
    const id = location.hash.slice(1);
    if (id) openLesson(id);
    // Back/forward and pasted links change only the hash. (replaceState, which we use, does not fire this.)
    const onHash = () => {
      const next = location.hash.slice(1);
      if (next) openLesson(next);
      else { run.current++; setScreen("home"); }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [loadLists, openLesson]);

  async function create(topic = concept) {
    const text = topic.trim();
    if (text.length < 2) return;
    setConcept(text);
    setError("");
    setJob(null);
    setLesson(null);
    setScreen("lesson");                      // straight to the lesson screen; the video area shows progress
    const mine = ++run.current;
    const documents = uploads.flatMap((u) => (u.state === "done" && u.doc ? [u.doc.id] : []));
    try {
      const done = await runJob(
        api<Job>("/api/lessons", { concept: text, ...settings, documents }),
        (j) => { if (mine === run.current) setJob(j); },
      );
      if (mine !== run.current) return;
      show(done.result as Lesson, settings.languages);
      loadLists();
    } catch (e) {
      if (mine !== run.current) return;
      setError((e as Error).message);
      setScreen("home");
    }
  }

  const goHome = () => {
    run.current++;
    setScreen("home");
    window.history.replaceState(null, "", location.pathname);
    loadLists();
  };

  const onVideo = (key: string, path: string) => {
    setLesson((l) => l && { ...l, videos: { ...l.videos, [key]: path } });
    loadLists();
  };

  return (
    <div className={screen === "lesson" ? "app wide" : "app"}>
      {screen === "home" && (
        <Home concept={concept} onConcept={setConcept} settings={settings} onSettings={setSettings} languages={languages}
          uploads={uploads} onUploads={(u) => setUploads(u)} recent={recent} error={error}
          onCreate={create} onOpen={openLesson} onBaseChange={loadLists} />
      )}
      {screen === "lesson" && (
        <LessonScreen lesson={lesson} generating={lesson ? undefined : { concept, job, languages: settings.languages }}
          lang={active} onLang={setActive} assetBase={assetBase} onBack={goHome} onVideo={onVideo} />
      )}
    </div>
  );
}
