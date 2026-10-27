import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, url } from "../api";
import { StudioModal } from "../studio/StudioModal";
import { TOOLS, type StudioKind } from "../studio/types";
import { requestTool, useStudioStatus } from "../studio/useStudio";
import { MetaButton, StudioButton } from "../studio/StudioButton";
import { useRewards } from "../rewards/RewardsContext";
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
  /** Meta quiz: build one metaverse world from every study tool and every video. `metaBusy` is its progress while it runs. */
  onMetaQuiz?: () => Promise<void>;
  metaBusy?: { progress: number; stage: string } | null;
};

/** Right panel: a tutor that knows the whole lesson and which scene you are watching. */
export const ChatPanel: React.FC<Props> = ({ lesson, track, lang, current, getTime, onMetaQuiz, metaBusy }) => {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [voice, setVoice] = useState<"off" | "listening" | "hearing">("off");   // mic state
  const [speaker, setSpeaker] = useState(() => { try { return localStorage.getItem("vt.speaker") !== "0"; } catch { return true; } });
  const [note, setNote] = useState("");
  const { award } = useRewards();
  const [studioKind, setStudioKind] = useState<StudioKind | null>(null);
  const studio = studioKind;
  const setStudio = (k: StudioKind | null) => {
    setStudioKind(k);
    if (k && lesson) award({ type: "study_tool_open", lesson_id: lesson.id, tool: k });
  };
  const [wanted, setWanted] = useState<StudioKind | null>(null);          // clicked while still being built: opens when ready
  const { tools, refresh } = useStudioStatus(lesson?.id, lang);

  useEffect(() => {
    if (!wanted || !tools) return;
    const t = tools[wanted];
    if (t.state === "ready") { setWanted(null); setStudio(wanted); }
    else if (t.state === "error") { setWanted(null); setNote(t.error ?? "That could not be made. Click it to try again."); }
  }, [tools, wanted]);

  const pick = (kind: StudioKind) => {
    const t = tools?.[kind];
    if (t?.state === "ready") { setStudio(kind); return; }
    if (!lesson) return;
    setNote("");
    setWanted(kind);                                                    // the border fills as it is built; it opens when done
    void requestTool(lesson.id, kind, lang).then(refresh).catch((e: Error) => { setWanted(null); setNote(e.message); });
  };
  const meta = async () => {
    if (!onMetaQuiz || metaBusy) return;
    try { await onMetaQuiz(); } catch (e) { setNote((e as Error).message || "The Meta quiz could not be built."); }
  };
  const box = useRef<HTMLDivElement>(null);
  const rec = useRef<{ mr: MediaRecorder; stream: MediaStream; chunks: Blob[] } | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const id = lesson?.id;
  const micOk = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

  useEffect(() => { setMsgs(id ? load(id) : []); }, [id]);
  // Scroll the message list only: scrollIntoView would move the whole page whenever a message arrives.
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" }); }, [msgs, busy]);
  useEffect(() => () => { rec.current?.stream.getTracks().forEach((t) => t.stop()); player.current?.pause(); }, []);

  const toggleSpeaker = () => {
    const on = !speaker;
    setSpeaker(on);
    try { localStorage.setItem("vt.speaker", on ? "1" : "0"); } catch { /* storage blocked */ }
    if (!on) player.current?.pause();
  };

  function say(audioUrl: string) {
    player.current?.pause();
    const a = new Audio(url(audioUrl));
    player.current = a;
    a.play().catch(() => setNote("Tap the speaker button to allow sound, then ask again."));
  }

  /** Tap once to start listening, tap again to send. The recording is transcribed on this computer (no cloud). */
  async function toggleMic() {
    if (voice === "listening") { rec.current?.mr.stop(); return; }
    if (voice !== "off" || busy || !lesson) return;
    setNote("");
    player.current?.pause();
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch {
      setNote("The microphone is blocked. Allow it in the browser (it works on localhost), or type your question.");
      return;
    }
    const mr = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      rec.current = null;
      setVoice("hearing");
      try {
        const r = await fetch(url(`/api/stt?lang=${encodeURIComponent(lang)}&lesson_id=${lesson.id}`),
          { method: "POST", body: new Blob(chunks, { type: mr.mimeType }) });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail ?? `Speech recognition failed (${r.status})`);
        if (!body.text) setNote("I did not catch that. Try again a little closer to the microphone.");
        else void send(body.text, true);
      } catch (e) {
        setNote((e as Error).message);
      } finally {
        setVoice("off");
      }
    };
    rec.current = { mr, stream, chunks };
    mr.start();
    setVoice("listening");
  }

  async function send(raw = text, spoken = false) {
    const message = raw.trim();
    if (!message || busy || !lesson) return;
    setText("");
    setNote("");
    const next: Msg[] = [...msgs, { role: "user", content: message, scene: current }];
    setMsgs(next);
    setBusy(true);
    try {
      const history = msgs.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
      const res = await api<{ reply: string; scene: number | null; audio_url?: string }>(`/api/lessons/${lesson.id}/chat`,
        { message, lang, time_s: getTime(), history, speak: speaker && (spoken || voice === "off") });
      award({ type: "tutor_question" });
      const done: Msg[] = [...next, { role: "assistant", content: res.reply, scene: res.scene }];
      setMsgs(done);
      save(lesson.id, done);
      if (res.audio_url && speaker) say(res.audio_url);
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

      <div className="studio-bar" role="group" aria-label="Study tools made from this lesson">
        {TOOLS.map((t) => (
          <StudioButton key={t.kind} kind={t.kind} label={t.label} hint={t.hint} state={tools?.[t.kind]} wanted={wanted === t.kind}
            disabled={!lesson} onClick={() => pick(t.kind)} />
        ))}
        {onMetaQuiz && <MetaButton busy={metaBusy} disabled={!lesson} onClick={meta} />}
      </div>

      {here && (
        <div className="ctx" title="The tutor knows which scene you are watching">
          <span className="ctx-dot" aria-hidden />Watching {current + 1}/{track!.scenes.length}: <b>{here.heading}</b>
        </div>
      )}

      <div className="msgs" role="log" aria-live="polite" ref={box}>
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
      </div>

      {note && <div className="chat-note" role="status">{note}</div>}
      <form className="chat-in" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <button type="button" className={`icon-btn spk${speaker ? " on" : ""}`} onClick={toggleSpeaker} aria-pressed={speaker}
          aria-label={speaker ? "Spoken answers on" : "Spoken answers off"} title={speaker ? "Spoken answers on" : "Spoken answers off"}>
          <Ui name={speaker ? "volume" : "mute"} size={18} />
        </button>
        {micOk && (
          <button type="button" className={`icon-btn mic${voice === "listening" ? " live" : ""}`} onClick={() => void toggleMic()}
            disabled={!lesson || busy || voice === "hearing"} aria-pressed={voice === "listening"}
            aria-label={voice === "listening" ? "Stop and send" : "Ask by voice"}
            title={voice === "listening" ? "Listening… tap to send" : voice === "hearing" ? "Working out what you said…" : "Ask by voice"}>
            <Ui name="mic" size={18} />
          </button>
        )}
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={!lesson || busy || voice !== "off"} maxLength={1000}
          placeholder={voice === "listening" ? "Listening… tap the mic to send" : voice === "hearing" ? "Understanding…"
            : lesson ? "Ask about this lesson…" : "Available when the lesson is ready"} aria-label="Your question" />
        <button type="submit" className="send" disabled={!lesson || busy || !text.trim()} aria-label="Send">
          <Ui name="arrowLeft" size={20} />
        </button>
      </form>

      {studio && lesson && createPortal(
        <StudioModal lesson={lesson} lang={lang} kind={studio} title={track?.title ?? lesson.concept} onClose={() => setStudio(null)}
          onAsk={(q) => { setStudio(null); void send(q); }} />,
        document.body,
      )}
    </section>
  );
};
