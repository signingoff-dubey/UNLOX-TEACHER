import React, { useCallback, useEffect, useRef, useState } from "react";
import type { World } from "metaverse";
import type { Job, Lesson } from "./types";
import {
  api, getApiBase, runJob, type Lang, type LessonSettings, type LessonSummary, type Playlist, type PlaylistSummary,
} from "./api";
import { MetaverseLayer, preloadMetaverse } from "./components/MetaverseLayer";
import { Home } from "./pages/Home";
import { Library } from "./pages/Library";
import { LessonPage } from "./pages/LessonPage";
import { RewardsPage } from "./pages/RewardsPage";
import { CreatingPill, type Creation } from "./shell/CreatingPill";
import { Sidebar } from "./shell/Sidebar";
import { useScrollbars } from "./shell/useScrollbars";

type Screen = "home" | "lesson" | "library" | "rewards";
const COURSE_HASH = /^c-([a-z0-9]+)(?:-(\d+))?$/;

/** Chanakya. A sidebar (create, library, your streak and score) and a main page: dashboard, lesson, library or rewards.
 *  A lesson is `#<id>`, a course is `#c-<id>` or `#c-<id>-<episode>`, the others are `#/library` and `#/rewards`. */
export default function App() {
  useScrollbars();
  const [screen, setScreen] = useState<Screen>("home");
  const [languages, setLanguages] = useState<Lang[]>([]);
  const [settings, setSettings] = useState<LessonSettings>({ level: "beginner", duration_s: 60, languages: ["en", "hi"] });
  const [concept, setConcept] = useState("");
  const [videos, setVideos] = useState(1);                      // 1 = one video, more = a course of that many
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
  const run = useRef(0);                            // a newer creation replaces the one still running
  // What is being made, so it can be reached from any page (the floating pill), and whether the user is looking at its progress screen.
  const [creation, setCreation] = useState<Creation | null>(null);
  const [watching, setWatching] = useState(false);
  const watchingRef = useRef(false);
  const watch = (v: boolean) => { watchingRef.current = v; setWatching(v); };

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
    watchingRef.current = false;                    // any navigation leaves the progress screen
    setWatching(false);
    const m = COURSE_HASH.exec(h);
    if (m) openCourse(m[1], m[2] !== undefined ? Number(m[2]) : undefined);
    else if (h === "/library") setScreen("library");
    else if (h === "/rewards") setScreen("rewards");
    else if (h && h !== "/") openLesson(h);
    else setScreen("home");
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
    if (!playlist || lesson || screen !== "lesson") return;
    const first = playlist.episodes.findIndex((e) => e.status === "ready");
    if (first >= 0) openEpisode(playlist, first);
  }, [playlist, lesson, screen, openEpisode]);

  const busy = job?.status === "queued" || job?.status === "running";

  async function create(topic = concept) {
    const text = topic.trim();
    if (busy || (text.length < 2 && !upload)) return;
    setConcept(text);
    setError("");
    setJob(null);
    setLesson(null);
    setPlaylist(null);
    setEpisode(0);
    setScreen("lesson");                      // straight to the lesson page; the progress card shows beside the player
    const mine = ++run.current;
    watch(true);
    setCreation({ status: "running", kind: videos > 1 ? "course" : "lesson", concept: text });
    const pdf = { upload, focus: upload ? focus.trim() : "" };
    try {
      if (videos > 1) {
        const started = await api<{ playlist: Playlist; job: Job }>("/api/playlists", { topic: text, ...settings, episodes: videos, documents: upload ? [upload] : [] });
        if (mine !== run.current) return;
        const id = started.playlist.id;
        setCreation((c) => c && { ...c, playlistId: id, hash: `c-${id}` });
        if (watchingRef.current) {
          setPlaylist(started.playlist);
          window.history.replaceState(null, "", `#c-${id}`);
        }
        await runJob(Promise.resolve(started.job), (j) => { if (mine === run.current) setJob(j); });
        if (mine !== run.current) return;
        const fresh = await api<Playlist>(`/api/playlists/${id}`);
        setPlaylist((cur) => (cur && cur.id === id ? fresh : cur));
        setCreation((c) => c && { ...c, status: "done" });
        loadLists();
        return;
      }
      const done = await runJob(
        api<Job>("/api/lessons", { concept: text, ...settings, ...pdf }),
        (j) => { if (mine === run.current) setJob(j); },
      );
      if (mine !== run.current) return;
      const made = done.result as Lesson;
      setCreation({ status: "done", kind: "lesson", concept: text, hash: made.id });
      if (watchingRef.current) {                  // still on the progress screen: open it; otherwise the pill says "Created"
        show(made, settings.languages);
        window.history.replaceState(null, "", `#${made.id}`);
      }
      loadLists();
    } catch (e) {
      if (mine !== run.current) return;
      setError((e as Error).message);
      if (watchingRef.current) { setCreation(null); setScreen("home"); }
      else setCreation((c) => c && { ...c, status: "error" });
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

  const go = (hash: string) => { setPlaylist(null); window.location.hash = hash; };
  const onVideo = (key: string, path: string) => { setLesson((l) => l && { ...l, videos: { ...l.videos, [key]: path } }); };
  // The floating pill is for a creation the user is not looking at. Looking at it (its progress screen, its lesson or its course) hides it.
  const viewing = screen === "lesson" && !!creation && (creation.kind === "course"
    ? (!!playlist && playlist.id === creation.playlistId) || (watching && !creation.playlistId)
    : watching || (!!lesson && lesson.id === creation.hash));
  useEffect(() => { if (creation && creation.status !== "running" && viewing) setCreation(null); }, [creation, viewing]);
  const openCreation = () => {
    if (!creation) return;
    if (creation.status === "error") { setCreation(null); go("/"); return; }
    if (creation.hash && (creation.status === "done" || creation.kind === "course")) { go(creation.hash); if (creation.status === "done") setCreation(null); return; }
    setLesson(null); setPlaylist(null); setError("");           // a lesson still being made: back to its progress screen
    watch(true);
    setScreen("lesson");
    window.history.replaceState(null, "", location.pathname);
  };
  const activeId = screen === "lesson" ? (playlist ? `c-${playlist.id}` : lesson?.id) : undefined;

  return (
    <div className={screen === "lesson" ? "shell has-lesson" : "shell"}>
      <Sidebar
        screen={screen} recent={recent} courses={courses} activeId={activeId}
        onOpenLesson={(id) => go(id)} onOpenCourse={(id) => go(`c-${id}`)}
        onHome={() => go("/")} onLibrary={() => go("/library")} onRewards={() => go("/rewards")} onMetaverse={enterMetaverse} onBaseChange={loadLists}
      />

      {screen === "home" && (
        <Home concept={concept} onConcept={setConcept} settings={settings} onSettings={setSettings} languages={languages}
          videos={videos} onVideos={setVideos} upload={upload} onUpload={setUpload} focus={focus} onFocus={setFocus}
          busy={busy} error={error} onCreate={create} recent={recent} courses={courses}
          onOpenLesson={(id) => go(id)} onOpenCourse={(id) => go(`c-${id}`)} onRewards={() => go("/rewards")} onLibrary={() => go("/library")} />
      )}
      {screen === "library" && <Library recent={recent} courses={courses} onOpenLesson={(id) => go(id)} onOpenCourse={(id) => go(`c-${id}`)} />}
      {screen === "rewards" && <RewardsPage />}
      {screen === "lesson" && (
        <LessonPage lesson={lesson} generating={lesson ? undefined : { concept, job, languages: settings.languages }}
          lang={active} onLang={setActive} assetBase={assetBase} onVideo={onVideo}
          playlist={playlist} episode={episode} onEpisode={(i) => playlist && openEpisode(playlist, i)}
          onMetaverse={enterMetaverse} onMetaQuiz={startMetaQuiz} metaBusy={meta} />
      )}
      {creation && !viewing && <CreatingPill creation={creation} onOpen={openCreation} />}
      <MetaverseLayer trigger={mvTrigger} lesson={lesson} lang={active} world={mvWorld} />
    </div>
  );
}
