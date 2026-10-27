import React, { useCallback, useEffect, useRef, useState } from "react";
import type { Job, Lesson } from "./types";
import {
  api, getApiBase, runJob, type Lang, type LessonSettings, type LessonSummary, type Playlist, type PlaylistSummary,
} from "./api";
import { Home } from "./screens/Home";
import { LessonScreen } from "./screens/LessonScreen";
import type { UploadItem } from "./components/UploadArea";

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
  const [uploads, setUploads] = useState<UploadItem[]>([]);
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
    if (text.length < 2) return;
    setConcept(text);
    setError("");
    setJob(null);
    setLesson(null);
    setPlaylist(null);
    setEpisode(0);
    setScreen("lesson");                      // straight to the lesson screen; the video area shows progress
    const mine = ++run.current;
    const documents = uploads.flatMap((u) => (u.state === "done" && u.doc ? [u.doc.id] : []));
    try {
      if (course) {
        const started = await api<{ playlist: Playlist; job: Job }>("/api/playlists", { topic: text, ...settings, episodes, documents });
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
        api<Job>("/api/lessons", { concept: text, ...settings, documents }),
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
          uploads={uploads} onUploads={(u) => setUploads(u)} recent={recent} error={error}
          onCreate={create} onOpen={openLesson} onBaseChange={loadLists}
          course={course} onCourse={setCourse} episodes={episodes} onEpisodes={setEpisodes}
          courses={courses} onOpenCourse={(id) => openCourse(id)} />
      )}
      {screen === "lesson" && (
        <LessonScreen lesson={lesson} generating={lesson ? undefined : { concept, job, languages: settings.languages }}
          lang={active} onLang={setActive} assetBase={assetBase} onBack={goHome} onVideo={onVideo}
          playlist={playlist} episode={episode} onEpisode={(i) => playlist && openEpisode(playlist, i)} />
      )}
    </div>
  );
}
