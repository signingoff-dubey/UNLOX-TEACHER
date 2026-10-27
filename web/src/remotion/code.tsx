import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { TemplateProps } from "./templates";
import { C, FONT_STACK, STAGE, ease, fit, pop, revealFrame } from "./theme";

// Code scene: a dark editor window. The snippet is display text only, it is never run.
// Syntax colours come from a small offline tokenizer (no highlighter library, no network).

const MONO = "'Cascadia Mono','JetBrains Mono',Consolas,'DejaVu Sans Mono',monospace";
const WIN = { x: STAGE.left, y: 250, w: 1130, h: 610 };
const SIDE = { x: WIN.x + WIN.w + 40, w: STAGE.right - (WIN.x + WIN.w + 40) };

const words = (s: string) => new Set(s.split(" "));
const KEYWORDS: Record<string, Set<string>> = {
  python: words("def class return if elif else for while in not and or import from as with try except finally raise lambda pass break continue None True False yield async await is del global print"),
  rust: words("fn let mut pub struct enum impl trait use mod match if else for while loop in return self Self as ref move const static where unsafe async await true false dyn Box Vec Some None Ok Err"),
  js: words("const let var function return if else for while of in new class extends import from export default async await try catch finally throw typeof this true false null undefined switch case break continue"),
  java: words("public private protected class static void int long double float boolean char String new return if else for while do switch case break continue try catch finally throw throws import package extends implements interface this super true false null final"),
  c: words("int long double float char void struct enum typedef return if else for while do switch case break continue include define const static sizeof NULL true false class public private namespace using template auto"),
  go: words("func package import var const type struct interface map chan go defer return if else for range switch case break continue select nil true false"),
  sql: words("SELECT FROM WHERE GROUP BY ORDER INSERT INTO VALUES UPDATE SET DELETE JOIN LEFT RIGHT INNER ON AS AND OR NOT NULL LIMIT CREATE TABLE PRIMARY KEY COUNT SUM AVG HAVING DISTINCT select from where group by order insert into values update set delete join on as and or not null limit create table"),
};
const FAMILY: Record<string, string> = {
  python: "python", py: "python", rust: "rust", rs: "rust",
  javascript: "js", js: "js", jsx: "js", ts: "js", tsx: "js", typescript: "js", react: "js", html: "js", css: "js",
  java: "java", kotlin: "java", csharp: "java", cs: "java",
  c: "c", cpp: "c", "c++": "c", go: "go", sql: "sql",
};
const COLORS = { kw: "#C792EA", str: "#8BD5A0", num: "#F5A97F", com: "#7F8AA8", fn: "#7DC4FF", type: "#F5CF7D", pun: "#AAB4CE", id: "#E8ECF5" };

type Tok = { t: string; k: keyof typeof COLORS };

const tokenize = (line: string, lang: string): Tok[] => {
  const fam = FAMILY[lang] ?? "js";
  const kws = KEYWORDS[fam];
  const comment = fam === "python" ? "#.*" : fam === "sql" ? "--.*" : "\\/\\/.*";
  const re = new RegExp(`(${comment})|("(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*'|\`(?:[^\`\\\\]|\\\\.)*\`)|(\\b\\d+(?:\\.\\d+)?\\b)|([A-Za-z_][A-Za-z0-9_]*)|(\\s+)|(.)`, "g");
  const out: Tok[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m[1]) out.push({ t: m[1], k: "com" });
    else if (m[2]) out.push({ t: m[2], k: "str" });
    else if (m[3]) out.push({ t: m[3], k: "num" });
    else if (m[4]) {
      const next = line.slice(re.lastIndex).trimStart()[0];
      out.push({ t: m[4], k: kws.has(m[4]) ? "kw" : next === "(" ? "fn" : /^[A-Z]/.test(m[4]) ? "type" : "id" });
    } else if (m[5]) out.push({ t: m[5], k: "id" });
    else out.push({ t: m[6], k: "pun" });
  }
  return out;
};

const Heading: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pop(frame, fps);
  return (
    <div style={{ position: "absolute", left: STAGE.left, top: STAGE.top, right: STAGE.left, opacity: p,
      transform: `translateY(${(1 - p) * 30}px)` }}>
      <div style={{ fontSize: fit(text, 64, 34), fontWeight: 800, color: C.ink, lineHeight: 1.25 }}>{text}</div>
      <div style={{ height: 8, width: 160 * ease(frame, 6, 26), background: C.teal, borderRadius: 4, marginTop: 14 }} />
    </div>
  );
};

export const CodeScene: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const code = scene.code ?? [];
  const steps = scene.highlights ?? [];
  const lang = (scene.code_lang ?? "").toLowerCase();
  const n = steps.length;
  const fontSize = Math.min(52, Math.floor((WIN.w - 130) / (Math.max(...code.map((l) => l.length), 16) * 0.62)),
    Math.floor((WIN.h - 110) / (Math.max(code.length, 1) * 1.45)));
  const LINE_H = Math.round(fontSize * 1.45);

  // Which narrated step is active now (-1 before the first one).
  let active = -1;
  for (let k = 0; k < n; k++) if (frame >= revealFrame(k, n, speechFrames)) active = k;
  const activeLine = active >= 0 ? steps[active] : -1;
  const noteCount = Math.min(n, scene.items.length);
  const output = scene.output ?? [];
  const outAt = revealFrame(n, n + 1, speechFrames);
  const winIn = pop(frame, fps, 4);

  return (
    <>
      <Heading text={scene.heading} />
      <div style={{ position: "absolute", left: WIN.x, top: WIN.y, width: WIN.w, height: WIN.h, borderRadius: 26, background: "#1B2338",
        boxShadow: `0 10px 0 ${C.line}`, overflow: "hidden", opacity: winIn, transform: `translateY(${(1 - winIn) * 30}px)` }}>
        <div style={{ height: 62, background: "#141B2E", display: "flex", alignItems: "center", padding: "0 24px", gap: 12 }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <div key={c} style={{ width: 18, height: 18, borderRadius: "50%", background: c }} />)}
          <div style={{ marginLeft: "auto", fontFamily: FONT_STACK, fontSize: 24, fontWeight: 700, color: "#9AA6C4", letterSpacing: 1 }}>
            {lang ? lang.toUpperCase() : "CODE"}
          </div>
        </div>
        <div style={{ padding: "22px 0", fontFamily: MONO, fontSize }}>
          {code.map((line, i) => {
            const lineIn = ease(frame, 8 + i * 3, 20 + i * 3);
            const on = i === activeLine;
            return (
              <div key={i} style={{ position: "relative", height: LINE_H, display: "flex", alignItems: "center", opacity: lineIn * (activeLine >= 0 && !on ? 0.5 : 1),
                background: on ? "rgba(233,138,46,0.20)" : "transparent", borderLeft: `8px solid ${on ? C.saffron : "transparent"}`, whiteSpace: "pre" }}>
                <span style={{ width: 70, textAlign: "right", paddingRight: 26, color: "#5F6B8A", flex: "none" }}>{i + 1}</span>
                <span>{tokenize(line, lang).map((tk, j) => <span key={j} style={{ color: COLORS[tk.k], fontStyle: tk.k === "com" ? "italic" : "normal" }}>{tk.t}</span>)}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ position: "absolute", left: SIDE.x, top: WIN.y, width: SIDE.w, height: WIN.h, display: "flex", flexDirection: "column", gap: 24 }}>
        {noteCount > 0 ? (() => {
          const k = Math.max(active, 0);
          const text = scene.items[Math.min(k, noteCount - 1)] ?? "";
          const p = pop(frame, fps, active >= 0 ? revealFrame(active, n, speechFrames) : 12);
          return (
            <div style={{ background: "#fff", border: `3px solid ${C.saffron}`, borderRadius: 24, boxShadow: `0 8px 0 ${C.line}`, padding: "26px 30px",
              opacity: Math.max(p, 0.001), transform: `scale(${0.94 + 0.06 * p})`, minHeight: 170 }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: C.saffron, marginBottom: 10, letterSpacing: 1 }}>
                {active >= 0 ? `Line ${steps[active] + 1}` : ""}
              </div>
              <div style={{ fontSize: fit(text, 46, 22, 0.6), fontWeight: 700, color: C.ink, lineHeight: 1.3 }}>{text}</div>
            </div>
          );
        })() : null}
        {output.length > 0 ? (
          <div style={{ marginTop: "auto", background: "#0F1526", borderRadius: 24, padding: "20px 26px", opacity: ease(frame, outAt, outAt + 14),
            boxShadow: `0 8px 0 ${C.line}`, fontFamily: MONO }}>
            <div style={{ fontFamily: FONT_STACK, fontSize: 22, fontWeight: 800, color: "#9AA6C4", marginBottom: 10, letterSpacing: 1 }}>OUTPUT</div>
            {output.map((o, i) => (
              <div key={i} style={{ fontSize: 34, color: "#8BD5A0", opacity: ease(frame, outAt + i * 6, outAt + 12 + i * 6), whiteSpace: "pre" }}>
                <span style={{ color: "#5F6B8A" }}>{"> "}</span>{o}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </>
  );
};
