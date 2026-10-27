import React, { useCallback, useEffect, useRef, useState } from "react";
import type { Job, Lesson } from "./types";
import {
  api, getApiBase, runJob, type Lang, type LessonSettings, type LessonSummary, type Playlist, type PlaylistSummary,
} from "./api";
import { Home } from "./screens/Home";
import { LessonScreen } from "./screens/LessonScreen";
import { MetaverseLayer, preloadMetaverse } from "./components/MetaverseLayer";
import type { World } from "metaverse";

type Screen = "home" | "lesson";
const COURSE_HASH = /^c-([a-z0-9]+)(?:-(\d+))?$/;

/** Two screens: Home (ask) -> Lesson (notes | video | tutor). Progress shows inside the video area.
 *  A lesson is `#<id>`, a course is `#c-<id>` or `#c-<id>-<episode>`, so links and Back work for both. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [settings, setSettings] = useState<LessonSettings>({ level: "beginner", duration_s: 60, languages: ["en", "hi"] });
  const [concept, setConcept] = useState("");
  const [course, setCourse] = useState(false);
  const [episodes, setEpisodes] = useState(5);
  const [upload, setUpload] = useState<string | null>(null);   // sha of an uploaded, read PDF
  const [focus, setFocus] = useState("");                       // e.g. "chapter 4" inside that PDF
  // The entrance animation and the world live in MetaverseLayer (its own state), so nothing here re-renders while it plays.
  const [mvTrigger, setMvTrigger] = useState(0);
  const [mvWorld, setMvWorld] = useState<World | null>(null);          // set by the Meta quiz; null = the lesson itself
  const [meta, setMeta] = useState<{ progress: number; stage: string } | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const [episode, setEpisode] = useState(0);
  const [active, setActive] = useState("en");
  const [recent, setRecent] = useState<LessonSummary[]>([]);
  const [courses, setCourses] = useState<PlaylistSummary[]>([]);
  const [error, setError] = useState("");
  const [assetBase, setAssetBase] = useState(getApiBase());
  const run = useRef(0);                            // ignore results of something the user already left

  const loadLists = useCallback(() => {
    setAssetBase(getApiBase());
    api<Lang[]>("/api/languages").then(setLanguages).catch(() => setLanguages([]));
    api<LessonSummary[]>("/api/lessons").then(setRecent).catch(() => setRecent([]));
    api<PlaylistSummary[]>("/api/playlists").then(setCourses).catch(() => setCourses([]));
  }, []);

  const show = useCallback((l: Lesson, preferred?: string[]) => {
    setLesson(l);
    setActive((cur) => (preferred ?? [cur]).find((c) => c in l.languages) ?? Object.keys(l.languages)[0]);
    setScreen("lesson");
  }, []);

  const openLesson = useCallback((id: string) => {
    setError("");
    setPlaylist(null);
    api<Lesson>(`/api/lessons/${id}`).then((l) => { show(l); window.history.replaceState(null, "", `#${l.id}`); }).catch(() => {
      setError("That lesson could not be loaded.");
      setScreen("home");
    });
  }, [show]);

  const openEpisode = useCallback((pl: Playlist, index: number) => {
    const ep = pl.episodes[index];
    if (!ep?.lesson_id) return;
    api<Lesson>(`/api/lessons/${ep.lesson_id}`).then((l) => {
      setEpisode(index);
      show(l);
      window.history.replaceState(null, "", `#c-${pl.id}-${index}`);
    }).catch(() => setError("That episode could not be loaded."));
  }, [show]);

  const openCourse = useCallback((id: string, index?: number) => {
    setError("");
    api<Playlist>(`/api/playlists/${id}`).then((pl) => {
      setPlaylist(pl);
      setConcept(pl.title);
      setScreen("lesson");
      const ready = pl.episodes.findIndex((e) => e.status === "ready");
      if (index !== undefined && pl.episodes[index]?.status === "ready") openEpisode(pl, index);
      else if (ready >= 0) openEpisode(pl, ready);
      else { setLesson(null); window.history.replaceState(null, "", `#c-${pl.id}`); }
    }).catch(() => { setError("That course could not be loaded."); setScreen("home"); });
  }, [openEpisode]);

  const openHash = useCallback(() => {
    const h = location.hash.slice(1);
    const m = COURSE_HASH.exec(h);
    if (m) openCourse(m[1], m[2] !== undefined ? Number(m[2]) : undefined);
    else if (h) openLesson(h);
    else { run.current++; setScreen("home"); }
  }, [openCourse, openLesson]);

  useEffect(() => {
    loadLists();
    openHash();
    // Back/forward and pasted links change only the hash. (replaceState, which we use, does not fire this.)
    window.addEventListener("hashchange", openHash);
    return () => window.removeEventListener("hashchange", openHash);
  }, [loadLists, openHash]);

  // While a course is being made, keep its episode list fresh and start playing as soon as episode 1 exists.
  const making = playlist && (playlist.status === "planning" || playlist.status === "building");
  useEffect(() => {
    if (!playlist?.id || !making) return;
    const id = playlist.id;
    const t = setInterval(() => {
      api<Playlist>(`/api/playlists/${id}`).then((pl) => setPlaylist((cur) => (cur && cur.id === id ? pl : cur))).catch(() => undefined);
    }, 2000);
    return () => clearInterval(t);
  }, [playlist?.id, making]);
  useEffect(() => {
    if (!playlist || lesson) return;
    const first = playlist.episodes.findIndex((e) => e.status === "ready");
    if (first >= 0) openEpisode(playlist, first);
  }, [playlist, lesson, openEpisode]);

  async function create(topic = concept) {
    const text = topic.trim();
    if (text.length < 2 && !upload) return;
    setConcept(text);
    setError("");
    setJob(null);
    setLesson(null);
    setPlaylist(null);
    setEpisode(0);
    setScreen("lesson");                      // straight to the lesson screen; the video area shows progress
    const mine = ++run.current;
    const pdf = { upload, focus: upload ? focus.trim() : "" };
    try {
      if (course) {
        const started = await api<{ playlist: Playlist; job: Job }>("/api/playlists", { topic: text, ...settings, episodes, documents: upload ? [upload] : [] });
        if (mine !== run.current) return;
        setPlaylist(started.playlist);
        window.history.replaceState(null, "", `#c-${started.playlist.id}`);
        await runJob(Promise.resolve(started.job), (j) => { if (mine === run.current) setJob(j); });
        if (mine !== run.current) return;
        setPlaylist(await api<Playlist>(`/api/playlists/${started.playlist.id}`));
        loadLists();
        return;
      }
      const done = await runJob(
        api<Job>("/api/lessons", { concept: text, ...settings, ...pdf }),
        (j) => { if (mine === run.current) setJob(j); },
      );
      if (mine !== run.current) return;
      show(done.result as Lesson, settings.languages);
      window.history.replaceState(null, "", `#${(done.result as Lesson).id}`);
      loadLists();
    } catch (e) {
      if (mine !== run.current) return;
      setError((e as Error).message);
      setScreen("home");
    }
  }

  const enterMetaverse = () => { setMvWorld(null); setMvTrigger((n) => n + 1); };

  /** Meta quiz: every video's lesson and every study tool the AI wrote, as one world. The button shows the progress. */
  const startMetaQuiz = async () => {
    if (!lesson || meta) return;
    setMeta({ progress: 0.02, stage: "Starting" });
    const ids = playlist ? playlist.episodes.flatMap((e) => (e.status === "ready" && e.lesson_id ? [e.lesson_id] : [])) : [];
    try {
      const done = await runJob(
        api<Job>("/api/metaquiz", { lesson_ids: ids.length ? ids : [lesson.id], focus: lesson.id, lang: active, title: playlist?.title ?? "" }),
        (j) => setMeta({ progress: j.progress, stage: j.stage }),
      );
      setMvWorld((done.result as { world: World }).world);
      setMvTrigger((n) => n + 1);
    } finally {
      setMeta(null);
    }
  };

  // The 3D chunk loads while the browser is idle, so opening the metaverse never waits on it.
  useEffect(() => {
    const idle = (window as unknown as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback;
    const id = idle ? idle(preloadMetaverse, { timeout: 6000 }) : window.setTimeout(preloadMetaverse, 3000);
    return () => (idle ? (window as unknown as { cancelIdleCallback: (n: number) => void }).cancelIdleCallback(id) : window.clearTimeout(id));
  }, []);

  const goHome = () => {
    run.current++;
    setScreen("home");
    setPlaylist(null);
    window.history.replaceState(null, "", location.pathname);
    loadLists();
  };

  const onVideo = (key: string, path: string) => {
    setLesson((l) => l && { ...l, videos: { ...l.videos, [key]: path } });
  };

  return (
    <div className={screen === "lesson" ? "app wide" : "app"}>
      {screen === "home" && (
        <Home concept={concept} onConcept={setConcept} settings={settings} onSettings={setSettings} languages={languages}
          upload={upload} onUpload={setUpload} focus={focus} onFocus={setFocus} onMetaverse={enterMetaverse}
          recent={recent} error={error}
          onCreate={create} onOpen={openLesson} onBaseChange={loadLists}
          course={course} onCourse={setCourse} episodes={episodes} onEpisodes={setEpisodes}
          courses={courses} onOpenCourse={(id) => openCourse(id)} />
      )}
      {screen === "lesson" && (
        <LessonScreen lesson={lesson} generating={lesson ? undefined : { concept, job, languages: settings.languages }}
          lang={active} onLang={setActive} assetBase={assetBase} onBack={goHome} onVideo={onVideo}
          playlist={playlist} episode={episode} onEpisode={(i) => playlist && openEpisode(playlist, i)}
          onMetaverse={enterMetaverse} onMetaQuiz={startMetaQuiz} metaBusy={meta} />
      )}
      <MetaverseLayer trigger={mvTrigger} lesson={lesson} lang={active} world={mvWorld} />
    </div>
  );
}
