import React from "react";
import type { Lang, LessonSettings, LessonSummary, Level, PlaylistSummary } from "../api";
import { History } from "../components/History";
import { StatusPanel } from "../components/StatusPanel";
import { UploadArea, type UploadItem } from "../components/UploadArea";
import { Ui } from "../components/ui-icons";

const EXAMPLES = ["Teach me Python loops", "The circle in maths", "Photosynthesis", "Newton's third law", "Learn React basics"];
const LENGTHS = [30, 60, 90];

type Props = {
  concept: string;
  onConcept: (v: string) => void;
  settings: LessonSettings;
  onSettings: (s: LessonSettings) => void;
  languages: Lang[];
  uploads: UploadItem[];
  onUploads: (update: (items: UploadItem[]) => UploadItem[]) => void;
  recent: LessonSummary[];
  error: string;
  onCreate: (topic?: string) => void;
  onOpen: (id: string) => void;
  onBaseChange: () => void;
  course: boolean;
  onCourse: (on: boolean) => void;
  episodes: number;
  onEpisodes: (n: number) => void;
  courses: PlaylistSummary[];
  onOpenCourse: (id: string) => void;
};

/** Screen 1: ask for a lesson. Topic, optional documents, level, length, languages. */
export const Home: React.FC<Props> = (p) => {
  const { settings: s } = p;
  const uploading = p.uploads.some((u) => u.state === "uploading");
  const docs = p.uploads.filter((u) => u.state === "done").length;
  const toggleLang = (code: string) =>
    p.onSettings({ ...s, languages: s.languages.includes(code) ? s.languages.filter((c) => c !== code) : [...s.languages, code] });
  const noLang = s.languages.length === 0;

  return (
    <div className="screen home">
      <header className="hero">
        <div className="brand"><span className="mark" aria-hidden />Visual Teacher</div>
        <div className="tag">Runs offline · English + Indian languages</div>
      </header>

      <form className="ask-card" onSubmit={(e) => { e.preventDefault(); p.onCreate(); }}>
        <h1>What do you want to learn?</h1>
        <div className="ask-row">
          <input id="concept" value={p.concept} onChange={(e) => p.onConcept(e.target.value)} autoFocus autoComplete="off"
            maxLength={200} placeholder="e.g. Teach me Python loops" aria-label="Topic to learn" />
          <button type="submit" className="go" disabled={p.concept.trim().length < 2 || uploading || noLang}>
            <Ui name="sparkle" size={20} />{p.course ? `Create ${p.episodes}-video course` : "Create lesson"}
          </button>
        </div>
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button type="button" key={ex} className="chip" onClick={() => p.onCreate(ex)}>{ex}</button>
          ))}
        </div>
        {p.error && <div className="error" role="alert">{p.error}</div>}
      </form>

      <div className="home-grid">
        <section className="card" aria-labelledby="docs-h">
          <h2 id="docs-h">Learn from your documents <span className="pill">optional</span></h2>
          <p className="muted lead">Upload a PDF and the lesson is built from what is in it.</p>
          <UploadArea items={p.uploads} onChange={p.onUploads} />
          {docs > 0 && <div className="note ok">{docs} document{docs > 1 ? "s" : ""} will be used for this lesson.</div>}
        </section>

        <section className="card" aria-labelledby="set-h">
          <h2 id="set-h">Lesson settings</h2>

          <div className="field">
            <div className="label">Format</div>
            <div className="seg" role="radiogroup" aria-label="Format">
              <button type="button" role="radio" aria-checked={!p.course} className={!p.course ? "on" : ""} onClick={() => p.onCourse(false)}>One video</button>
              <button type="button" role="radio" aria-checked={p.course} className={p.course ? "on" : ""} onClick={() => p.onCourse(true)}>Course (playlist)</button>
            </div>
            {p.course && (
              <div className="seg sub" role="radiogroup" aria-label="Number of videos">
                {[5, 6, 7, 8].map((n) => (
                  <button type="button" key={n} role="radio" aria-checked={p.episodes === n} className={p.episodes === n ? "on" : ""} onClick={() => p.onEpisodes(n)}>{n} videos</button>
                ))}
              </div>
            )}
          </div>

          <div className="field">
            <div className="label">Level</div>
            <div className="seg" role="radiogroup" aria-label="Level">
              {(["beginner", "intermediate"] as Level[]).map((l) => (
                <button type="button" key={l} role="radio" aria-checked={s.level === l} className={s.level === l ? "on" : ""}
                  onClick={() => p.onSettings({ ...s, level: l })}>{l === "beginner" ? "Beginner" : "Intermediate"}</button>
              ))}
            </div>
          </div>

          <div className="field">
            <div className="label">Length{p.course ? " of each video" : ""}</div>
            <div className="seg" role="radiogroup" aria-label="Length">
              {LENGTHS.map((d) => (
                <button type="button" key={d} role="radio" aria-checked={s.duration_s === d} className={s.duration_s === d ? "on" : ""}
                  onClick={() => p.onSettings({ ...s, duration_s: d })}>{d} s</button>
              ))}
            </div>
          </div>

          <div className="field">
            <div className="label">Languages <span className={noLang ? "need" : "muted"}>{noLang ? "pick at least one" : `${s.languages.length} selected`}</span></div>
            <div className="langs">
              {p.languages.map((l) => {
                const on = s.languages.includes(l.code);
                return (
                  <button type="button" key={l.code} className={`lang ${on ? "on" : ""}`} aria-pressed={on} onClick={() => toggleLang(l.code)}>
                    <span className="native">{l.native}</span>
                    <span className="muted">{l.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      </div>

      <div className="home-foot">
        <div>
          <History items={p.recent} onOpen={p.onOpen} />
          {p.courses.length > 0 && (
            <div className="history">
              <div className="label">Recent courses</div>
              <ul>
                {p.courses.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="past" onClick={() => p.onOpenCourse(c.id)}>
                      <span className="concept">{c.title}</span>
                      <span className="muted">{c.ready}/{c.episodes} videos{c.status === "building" ? " · still making" : ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <StatusPanel onBaseChange={p.onBaseChange} />
      </div>
    </div>
  );
};
