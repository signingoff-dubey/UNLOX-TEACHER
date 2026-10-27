import React, { useState } from "react";
import type { LessonSummary, PlaylistSummary } from "../api";
import { Glyph } from "../ds/Glyph";

const TONES = ["green", "orange", "pink", "blue"] as const;

type Props = { recent: LessonSummary[]; courses: PlaylistSummary[]; onOpenLesson: (id: string) => void; onOpenCourse: (id: string) => void };

/** Every lesson and course, searchable. */
export const Library: React.FC<Props> = (p) => {
  const [q, setQ] = useState("");
  const has = (s: string) => s.toLowerCase().includes(q.trim().toLowerCase());
  const lessons = p.recent.filter((l) => has(l.concept));
  const courses = p.courses.filter((c) => has(c.title));
  return (
    <main className="main">
      <header className="hero">
        <div>
          <div className="eyebrow">Library</div>
          <h1>Everything you have made.</h1>
          <label className="search"><Glyph name="search" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search lessons and courses" aria-label="Search" /></label>
        </div>
      </header>
      {courses.length > 0 && (
        <section className="section">
          <div className="section-head"><div><h2>Courses</h2><p>{courses.length} course{courses.length === 1 ? "" : "s"}</p></div></div>
          <ul className="tiles">
            {courses.map((c, i) => (
              <li key={c.id}>
                <button type="button" className="tile" onClick={() => p.onOpenCourse(c.id)}>
                  <div className={`thumb ${TONES[(i + 1) % 4]}`}><Glyph name="library" size={30} /></div>
                  <span className="tile-name">{c.title}</span>
                  <div className="tile-top"><span>{c.status === "building" ? "Still making" : "Course"}</span><span className="chip">{c.ready}/{c.episodes} videos</span></div>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="section">
        <div className="section-head"><div><h2>Lessons</h2><p>{lessons.length} lesson{lessons.length === 1 ? "" : "s"}</p></div></div>
        {lessons.length ? (
          <ul className="tiles">
            {lessons.map((l, i) => (
              <li key={l.id}>
                <button type="button" className="tile" onClick={() => p.onOpenLesson(l.id)}>
                  <div className={`thumb ${TONES[i % 4]}`}><Glyph name="play" size={30} /></div>
                  <span className="tile-name">{l.concept}</span>
                  <div className="tile-top"><span>{l.languages.length} language{l.languages.length === 1 ? "" : "s"}</span>{l.videos.length > 0 && <span className="chip">MP4</span>}</div>
                </button>
              </li>
            ))}
          </ul>
        ) : <div className="empty">{q ? "Nothing matches that search." : "No lessons yet."}</div>}
      </section>
    </main>
  );
};
