import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Lesson, Track } from "../types";
import { Ui } from "./ui-icons";

type Msg = { role: "user" | "assistant"; content: string; scene?: number | null; error?: boolean };

const SUGGEST = ["Explain this part again", "Give me another example", "Quiz me", "Why does it work like that?"];
const ckey = (id: string) => `vt.chat.${id}`;

function load(id: string): Msg[] {
  try { return JSON.parse(localStorage.getItem(ckey(id)) ?? "[]"); } catch { return []; }
}
function save(id: string, m: Msg[]) {
  try { localStorage.setItem(ckey(id), JSON.stringify(m.slice(-40))); } catch { /* storage blocked */ }
}

type Props = {
  lesson: Lesson | null;
  track?: Track;
  lang: string;
  current: number;
  getTime: () => number;
};

/** Right panel: a tutor that knows the whole lesson and which scene you are watching. */
export const ChatPanel: React.FC<Props> = ({ lesson, track, lang, current, getTime }) => {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const id = lesson?.id;

  useEffect(() => { setMsgs(id ? load(id) : []); }, [id]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [msgs, busy]);

  async function send(raw = text) {
    const message = raw.trim();
    if (!message || busy || !lesson) return;
    setText("");
    const next: Msg[] = [...msgs, { role: "user", content: message, scene: current }];
    setMsgs(next);
    setBusy(true);
    try {
      const history = msgs.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
      const res = await api<{ reply: string; scene: number | null }>(`/api/lessons/${lesson.id}/chat`,
        { message, lang, time_s: getTime(), history });
      const done: Msg[] = [...next, { role: "assistant", content: res.reply, scene: res.scene }];
      setMsgs(done);
      save(lesson.id, done);
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: (e as Error).message || "The tutor could not answer.", error: true }]);
    } finally {
      setBusy(false);
    }
  }

  const here = track?.scenes[current];

  return (
    <section className="panel-col chat" aria-label="Tutor chat">
      <div className="panel-head">
        <h2>Ask the tutor</h2>
        {msgs.length > 0 && lesson && (
          <button type="button" className="icon-btn" aria-label="Clear chat" onClick={() => { setMsgs([]); save(lesson.id, []); }}>
            <Ui name="x" size={18} />
          </button>
        )}
      </div>

      {here && (
        <div className="ctx" title="The tutor knows which scene you are watching">
          <span className="ctx-dot" aria-hidden />Watching {current + 1}/{track!.scenes.length}: <b>{here.heading}</b>
        </div>
      )}

      <div className="msgs" role="log" aria-live="polite">
        {!lesson ? (
          <div className="panel-empty"><p className="muted">Ask questions about the lesson here once it is ready. The tutor will know every scene.</p></div>
        ) : msgs.length === 0 ? (
          <div className="chat-hello">
            <p>Ask me anything about <b>{track?.title}</b>. I know the whole lesson and where you are in it.</p>
            <div className="suggest">
              {SUGGEST.map((q) => <button type="button" key={q} className="chip" onClick={() => send(q)}>{q}</button>)}
            </div>
          </div>
        ) : (
          msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}${m.error ? " err" : ""}`}>
              <div className="bubble">{m.content}</div>
              {m.scene != null && track?.scenes[m.scene] && <div className="msg-scene">scene {m.scene + 1}</div>}
            </div>
          ))
        )}
        {busy && <div className="msg assistant"><div className="bubble typing" aria-label="Tutor is typing"><i /><i /><i /></div></div>}
        <div ref={end} />
      </div>

      <form className="chat-in" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={!lesson || busy} maxLength={1000}
          placeholder={lesson ? "Ask about this lesson…" : "Available when the lesson is ready"} aria-label="Your question" />
        <button type="submit" className="send" disabled={!lesson || busy || !text.trim()} aria-label="Send">
          <Ui name="arrowLeft" size={20} />
        </button>
      </form>
    </section>
  );
};
