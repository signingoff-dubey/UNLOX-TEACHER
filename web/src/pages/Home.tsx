import React, { useEffect, useRef } from "react";
import type { Lang, LessonSettings, LessonSummary, Level, PlaylistSummary } from "../api";
import { Glyph } from "../ds/Glyph";
import { PdfUpload } from "../components/PdfUpload";
import type { Mode, PhotoItem } from "../photos";
import { useRewards } from "../rewards/RewardsContext";
import { Dashboard } from "./Dashboard";

export const COUNTS = [0, 1, 2, 3, 5, 8];                  // 0 = Auto: the AI picks one video per concept
export const MODES: [Mode, string, string][] = [["explain", "Explanation", "Understand it"], ["study", "Study", "Revise for a test"], ["homework", "Homework", "Learn it and get the answers"]];
/** Up to 4 minutes. Over 1:30 the backend writes the video in parts (see backend/app/longplan.py). */
export const LENGTHS: [number, string][] = [[30, "0:30"], [60, "1:00"], [90, "1:30"], [120, "2:00"], [150, "2:30"], [180, "3:00"], [210, "3:30"], [240, "4:00"]];
const TOPICS: [string, string][] = [
  ["Teach me Python loops", "bolt"], ["The circle in maths", "pie"], ["Photosynthesis", "leaf"], ["The water cycle", "drop"], ["Newton's third law", "rainbow"],
];
const SCROLL_RANGE = 260;                                   // px of scrolling in which the prompt box shrinks into the header

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Still up" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

type Props = {
  concept: string;
  onConcept: (v: string) => void;
  settings: LessonSettings;
  onSettings: (s: LessonSettings) => void;
  languages: Lang[];
  videos: number;
  mode: Mode;
  onMode: (m: Mode) => void;
  photos: PhotoItem[];
  onAddPhotos: (files: FileList) => void;
  onRemovePhoto: (key: string) => void;
  onVideos: (n: number) => void;
  upload: string | null;
  onUpload: (sha: string | null) => void;
  focus: string;
  onFocus: (f: string) => void;
  busy: boolean;
  error: string;
  onCreate: (topic?: string) => void;
  recent: LessonSummary[];
  courses: PlaylistSummary[];
  onOpenLesson: (id: string) => void;
  onOpenCourse: (id: string) => void;
  onRewards: () => void;
  onLibrary: () => void;
};

/** The first screen. The prompt box is the hero; scrolling shrinks it into a pinned header (its buttons slide away behind it)
 *  while the settings card and the dashboard pass underneath. The scroll position drives one CSS variable, `--p` (0 to 1). */
export const Home: React.FC<Props> = (p) => {
  const { state } = useRewards();
  const dock = useRef<HTMLDivElement>(null);
  const { settings: s } = p;
  const photosReady = p.photos.some((x) => x.status === "ready") && !p.photos.some((x) => x.status === "reading");
  const canCreate = !p.busy && (p.concept.trim().length >= 2 || !!p.upload || photosReady) && !p.photos.some((x) => x.status === "reading") && s.languages.length > 0;
  const course = p.videos !== 1;
  const toggleLang = (code: string) =>
    p.onSettings({ ...s, languages: s.languages.includes(code) ? s.languages.filter((c) => c !== code) : [...s.languages, code] });

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const t = Math.min(Math.max(window.scrollY / SCROLL_RANGE, 0), 1);
      dock.current?.style.setProperty("--p", t.toFixed(3));
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    // The dock keeps its full-size height while it shrinks (the settings card must not jump up), so measure that height:
    // at --p 0 with a free height. This runs again when the width changes (the title and the topic chips wrap) and when fonts load.
    const measure = () => {
      const el = dock.current;
      if (!el) return;
      const keep = el.style.getPropertyValue("--p");
      el.style.setProperty("--p", "0");
      el.style.height = "auto";
      const h = el.offsetHeight;
      el.style.height = "";
      el.style.setProperty("--dock-h", `${h}px`);
      el.style.setProperty("--p", keep || "0");
    };
    measure();
    update();
    void document.fonts?.ready.then(measure);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", measure);
    return () => { window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", measure); cancelAnimationFrame(frame); };
  }, []);

  const submit = (e: React.FormEvent) => { e.preventDefault(); if (canCreate) p.onCreate(); };

  return (
    <main className="main home">
      {p.error && <div className="notice bad" role="alert" style={{ position: "fixed", top: 18, left: "50%", transform: "translateX(-50%)", zIndex: 60 }}>{p.error}</div>}

      <div className="dock" ref={dock}>
        <div className="dock-lead">
          <div className="eyebrow">{greeting()}{state ? `, ${state.name}` : ""}</div>
          <h1>{state?.streak.at_risk ? "Learn something today and keep your streak." : "What will you learn today?"}</h1>
        </div>

        <form className="dock-box" onSubmit={submit}>
          <span className="dock-spark" aria-hidden><Glyph name="sparkle" size={22} /></span>
          <div className="dock-field">
            <label htmlFor="concept" className="sr-only">What do you want to learn?</label>
            <textarea id="concept" value={p.concept} rows={3} maxLength={200} disabled={p.busy} autoComplete="off" spellCheck
              placeholder={p.photos.length ? "Add a few words about the photo, or leave this empty" : p.upload ? "A topic in your PDF, or leave this empty" : "Type anything you want to learn…"}
              onChange={(e) => p.onConcept(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (canCreate) p.onCreate(); } }} />
            {p.photos.length > 0 && (
              <ul className="dock-photos" aria-label="Attached photos">
                {p.photos.map((x) => (
                  <li key={x.key} className={`photo ${x.status}`} title={x.status === "error" ? x.error : x.topic || x.name}>
                    <img src={x.preview} alt={x.name} />
                    <span className="photo-state">{x.status === "reading" ? "Reading…" : x.status === "error" ? "Failed" : x.topic || "Ready"}</span>
                    {!p.busy && <button type="button" className="photo-x" aria-label={`Remove ${x.name}`} onClick={() => p.onRemovePhoto(x.key)}><Glyph name="x" size={12} /></button>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <label className={`round dock-plus${p.busy || p.photos.length >= 4 ? " off" : ""}`} title="Add a photo (homework, a textbook page, a diagram)">
            <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="sr-only" disabled={p.busy || p.photos.length >= 4}
              aria-label="Add a photo" onChange={(e) => { if (e.target.files?.length) p.onAddPhotos(e.target.files); e.target.value = ""; }} />
            <Glyph name="plus" size={18} />
          </label>
          <button type="submit" className="primary dock-go" disabled={!canCreate}>
            <span className="dock-go-label">{p.busy ? "Creating…" : course ? (p.videos === 0 ? "Create a course" : `Create ${p.videos}-video course`) : p.upload && !p.concept.trim() ? "Create from PDF" : "Create lesson"}</span>
            <Glyph name="chevron" size={18} />
          </button>
        </form>

        <ul className="dock-extra" aria-label="Try a topic">
          {TOPICS.map(([t, icon]) => (
            <li key={t}><button type="button" className="ghost" disabled={p.busy} onClick={() => p.onCreate(t)}><Glyph name={icon} size={16} />{t}</button></li>
          ))}
        </ul>
      </div>

      <section className="card white settings" aria-label="Lesson settings">
        <div className="card-title"><Glyph name="settings" size={16} />Settings</div>
        <div className="settings-grid">
          <div className="wide">
            <div className="field-label">What is it for?</div>
            <div className="seg modes" role="radiogroup" aria-label="What is it for">
              {MODES.map(([m, label, hint]) => (
                <button type="button" key={m} role="radio" aria-checked={p.mode === m} className={p.mode === m ? "on" : ""} title={hint} onClick={() => p.onMode(m)}>{label}</button>
              ))}
            </div>
            <p className="mode-hint">{MODES.find(([m]) => m === p.mode)?.[2]}{p.mode === "homework" ? ". Attach the homework as a PDF or a photo; the answers are written as a file you read in the browser." : ""}</p>
          </div>
          <div>
            <div className="field-label">How many videos? <span className="muted">{p.videos === 0 ? "the AI counts the concepts" : ""}</span></div>
            <div className="seg" role="radiogroup" aria-label="Number of videos">
              {COUNTS.map((n) => (
                <button type="button" key={n} role="radio" aria-checked={p.videos === n} className={p.videos === n ? "on" : ""} onClick={() => p.onVideos(n)}>{n === 0 ? "Auto" : n}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="field-label">Level</div>
            <div className="seg" role="radiogroup" aria-label="Level">
              {(["beginner", "intermediate"] as Level[]).map((l) => (
                <button type="button" key={l} role="radio" aria-checked={s.level === l} className={s.level === l ? "on" : ""}
                  onClick={() => p.onSettings({ ...s, level: l })}>{l === "beginner" ? "Beginner" : "Intermediate"}</button>
              ))}
            </div>
          </div>
          <div className="wide">
            <div className="field-label">How long is each video? <span className="muted">{s.duration_s > 90 ? "Longer videos are written in parts and take a few minutes." : "up to 4 minutes"}</span></div>
            <div className="seg" role="radiogroup" aria-label="Length of each video">
              {LENGTHS.map(([sec, label]) => (
                <button type="button" key={sec} role="radio" aria-checked={s.duration_s === sec} className={s.duration_s === sec ? "on" : ""}
                  onClick={() => p.onSettings({ ...s, duration_s: sec })}>{label}</button>
              ))}
            </div>
          </div>
          <div className="wide">
            <div className="field-label">Languages <span className="muted">{s.languages.length ? `${s.languages.length} selected` : "pick at least one"}</span></div>
            <ul className="lang-chips">
              {p.languages.map((l) => {
                const on = s.languages.includes(l.code);
                return (
                  <li key={l.code}>
                    <button type="button" className={on ? "lang on" : "lang"} disabled={p.busy} aria-pressed={on} onClick={() => toggleLang(l.code)}>
                      {on && <Glyph name="check" size={14} />}<span>{l.native}</span><small>{l.name}</small>
                    </button>
                  </li>
                );
              })}
              {!p.languages.length && <li className="muted">Languages load from the backend.</li>}
            </ul>
          </div>
          <div className="wide">
            <PdfUpload sha={p.upload} onSha={p.onUpload} focus={p.focus} onFocus={p.onFocus} disabled={p.busy} />
          </div>
        </div>
      </section>

      <Dashboard recent={p.recent} courses={p.courses} onOpenLesson={p.onOpenLesson} onOpenCourse={p.onOpenCourse}
        onNew={() => document.getElementById("concept")?.focus()} onRewards={p.onRewards} onLibrary={p.onLibrary} />
    </main>
  );
};
