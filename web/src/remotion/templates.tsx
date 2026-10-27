import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { Scene, TemplateName } from "../types";
import { Icon } from "./icons";
import { C, PALETTE, STAGE, W, ease, fit, fitAll, pop, revealFrame } from "./theme";
import { CodeScene } from "./code";
import { GraphScene } from "./graph";

export type TemplateProps = { scene: Scene; speechFrames: number; lessonTitle: string; sourceNote?: string };

const card: React.CSSProperties = {
  background: C.card,
  border: `3px solid ${C.line}`,
  borderRadius: 26,
  boxShadow: `0 8px 0 ${C.line}`,
};

const centerText: React.CSSProperties = { textAlign: "center", lineHeight: 1.3 };

// -------------------------------------------------------------- shared pieces

const Heading: React.FC<{ text: string; color?: string }> = ({ text, color = C.saffron }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pop(frame, fps);
  return (
    <div style={{ position: "absolute", left: STAGE.left, top: STAGE.top, right: STAGE.left,
      opacity: p, transform: `translateY(${(1 - p) * 30}px)` }}>
      <div style={{ fontSize: fit(text, 64, 34), fontWeight: 800, color: C.ink, lineHeight: 1.25 }}>{text}</div>
      <div style={{ height: 8, width: 160 * ease(frame, 6, 26), background: color, borderRadius: 4, marginTop: 14 }} />
    </div>
  );
};

/** SVG path that draws itself as `p` goes 0 -> 1. */
const DrawPath: React.FC<{ d: string; p: number; color?: string; width?: number; arrow?: boolean }> = (
  { d, p, color = C.muted, width = 6, arrow = false },
) => (
  <path d={d} pathLength={1} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round"
    strokeDasharray="1 1" strokeDashoffset={1 - p}
    markerEnd={arrow && p > 0.95 ? "url(#arrowhead)" : undefined} />
);

const ArrowDefs: React.FC<{ color?: string }> = ({ color = C.muted }) => (
  <defs>
    <marker id="arrowhead" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto">
      <path d="M0 0L10 5L0 10z" fill={color} />
    </marker>
  </defs>
);

const Full: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg width={W} height={1080} style={{ position: "absolute", inset: 0, overflow: "visible" }}>{children}</svg>
);

// -------------------------------------------------------------- templates

const TitleCard: React.FC<TemplateProps> = ({ scene, lessonTitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const iconP = pop(frame, fps, 2);
  const textP = pop(frame, fps, 10);
  const bob = Math.sin(frame / 14) * 8;
  const showKicker = lessonTitle && lessonTitle.trim() !== scene.heading.trim();
  return (
    <div style={{ position: "absolute", inset: `${STAGE.top}px ${STAGE.left}px ${1080 - STAGE.bottom}px`,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 36 }}>
      <div style={{ width: 280, height: 280, borderRadius: "50%", background: "#FDE7CF",
        border: `6px solid ${C.saffron}`, display: "grid", placeItems: "center",
        transform: `scale(${iconP}) translateY(${bob}px)` }}>
        <Icon name={scene.icon} size={190} />
      </div>
      <div style={{ opacity: textP, transform: `translateY(${(1 - textP) * 40}px)`, ...centerText }}>
        {showKicker && (
          <div style={{ fontSize: 40, fontWeight: 700, color: C.teal, letterSpacing: 1, marginBottom: 12 }}>
            {lessonTitle}
          </div>
        )}
        <div style={{ fontSize: fit(scene.heading, 92, 24), fontWeight: 800, color: C.ink, maxWidth: 1500 }}>
          {scene.heading}
        </div>
      </div>
    </div>
  );
};

const ListScene: React.FC<TemplateProps & { checks: boolean }> = ({ scene, speechFrames, checks, sourceNote }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = scene.items.length;
  const rowH = Math.min(118, 560 / n);
  return (
    <>
      <Heading text={scene.heading} color={checks ? C.green : C.saffron} />
      <div style={{ position: "absolute", left: STAGE.left + 40, right: 420, top: 330,
        display: "flex", flexDirection: "column", gap: 22 }}>
        {scene.items.map((item, i) => {
          const at = revealFrame(i, n, speechFrames);
          const p = pop(frame, fps, at);
          const color = checks ? C.green : PALETTE[i % PALETTE.length];
          return (
            <div key={i} style={{ ...card, minHeight: rowH - 22, display: "flex", alignItems: "center", gap: 28,
              padding: "14px 32px", opacity: p, transform: `translateX(${(1 - p) * -80}px)` }}>
              <div style={{ width: 64, height: 64, flex: "none", borderRadius: "50%", background: color,
                color: "#fff", fontSize: 34, fontWeight: 800, display: "grid", placeItems: "center" }}>
                {checks ? (
                  <svg width="40" height="40" viewBox="0 0 40 40">
                    <DrawPath d="M9 21l8 8 15-17" p={ease(frame, at + 4, at + 16)} color="#fff" width={6} />
                  </svg>
                ) : i + 1}
              </div>
              <div style={{ fontSize: fit(item, 46, 34), fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{item}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", right: STAGE.left + 20, top: 360, opacity: 0.9,
        transform: `rotate(${Math.sin(frame / 20) * 4}deg)` }}>
        <Icon name={scene.icon} size={260} />
      </div>
      {checks && sourceNote && (
        <div style={{ position: "absolute", left: STAGE.left + 40, right: STAGE.left, top: 800,
          fontSize: 26, fontWeight: 600, color: C.muted, opacity: ease(frame, 20, 40),
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {sourceNote}
        </div>
      )}
    </>
  );
};

const Flow: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = scene.items.length;
  const gap = 80;
  const boxW = Math.min(400, (STAGE.right - STAGE.left - gap * (n - 1)) / n);
  const total = boxW * n + gap * (n - 1);
  const x0 = (W - total) / 2;
  const y = 470;
  return (
    <>
      <Heading text={scene.heading} />
      <Full>
        <ArrowDefs />
        {scene.items.slice(1).map((_, i) => {
          const at = revealFrame(i + 1, n, speechFrames);
          const xa = x0 + (i + 1) * boxW + i * gap + 12;
          return <DrawPath key={i} d={`M${xa} ${y + 110}H${xa + gap - 30}`} p={ease(frame, at - 10, at)} arrow width={7} />;
        })}
      </Full>
      {scene.items.map((item, i) => {
        const at = revealFrame(i, n, speechFrames);
        const p = pop(frame, fps, at);
        const color = PALETTE[i % PALETTE.length];
        return (
          <div key={i} style={{ ...card, position: "absolute", left: x0 + i * (boxW + gap), top: y, width: boxW,
            minHeight: 220, padding: "56px 20px 24px", display: "flex", alignItems: "center", justifyContent: "center",
            borderColor: color, opacity: p, transform: `scale(${0.6 + 0.4 * p})` }}>
            <div style={{ position: "absolute", top: -34, left: "50%", marginLeft: -34, width: 68, height: 68,
              borderRadius: "50%", background: color, color: "#fff", fontSize: 34, fontWeight: 800,
              display: "grid", placeItems: "center" }}>{i + 1}</div>
            <div style={{ fontSize: fitAll(scene.items, 42, boxW / 26), fontWeight: 700, color: C.ink, ...centerText }}>{item}</div>
          </div>
        );
      })}
    </>
  );
};

const Cycle: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = scene.items.length;
  const cx = W / 2, cy = 545, R = 270;
  const angle = (i: number) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pt = (a: number, r = R) => [cx + r * Math.cos(a) * 1.55, cy + r * Math.sin(a)] as const;
  const gapA = 0.42;
  return (
    <>
      <Heading text={scene.heading} color={C.teal} />
      <Full>
        <ArrowDefs color={C.teal} />
        {scene.items.map((_, i) => {
          const at = revealFrame((i + 1) % n || n - 0.4, n, speechFrames);
          const a1 = angle(i) + gapA, a2 = angle(i + 1) - gapA;
          const steps = 24;
          const d = Array.from({ length: steps + 1 }, (_, k) => {
            const [x, yy] = pt(a1 + ((a2 - a1) * k) / steps);
            return `${k ? "L" : "M"}${x.toFixed(1)} ${yy.toFixed(1)}`;
          }).join("");
          return <DrawPath key={i} d={d} p={ease(frame, at - 12, at + 4)} color={C.teal} arrow width={7} />;
        })}
      </Full>
      <div style={{ position: "absolute", left: cx - 90, top: cy - 90, transform: `rotate(${frame * 0.6}deg)` }}>
        <Icon name={scene.icon} size={180} />
      </div>
      {scene.items.map((item, i) => {
        const [x, yy] = pt(angle(i));
        const p = pop(frame, fps, revealFrame(i, n, speechFrames));
        return (
          <div key={i} style={{ ...card, position: "absolute", left: x - 180, top: yy - 52, width: 360,
            padding: "18px 20px", borderColor: PALETTE[i % PALETTE.length], opacity: p,
            transform: `scale(${0.5 + 0.5 * p})` }}>
            <div style={{ fontSize: fitAll(scene.items, 40, 16), fontWeight: 700, color: C.ink, ...centerText }}>{item}</div>
          </div>
        );
      })}
    </>
  );
};

const Compare: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cols = [
    { title: scene.left_title, items: scene.left, color: C.teal, x: STAGE.left + 40 },
    { title: scene.right_title, items: scene.right, color: C.saffron, x: W / 2 + 70 },
  ];
  const all = scene.left.length + scene.right.length;
  let k = 0;
  return (
    <>
      <Heading text={scene.heading} />
      {cols.map((col, c) => {
        const p = pop(frame, fps, c * 8);
        return (
          <div key={c} style={{ ...card, position: "absolute", left: col.x, top: 320, width: W / 2 - STAGE.left - 110,
            minHeight: 480, borderColor: col.color, overflow: "hidden", opacity: p, transform: `translateY(${(1 - p) * 60}px)` }}>
            <div style={{ background: col.color, color: "#fff", padding: "20px 36px", fontSize: fit(col.title, 48, 22), fontWeight: 800 }}>
              {col.title}
            </div>
            <div style={{ padding: "26px 36px", display: "flex", flexDirection: "column", gap: 20 }}>
              {col.items.map((item, i) => {
                const ip = pop(frame, fps, revealFrame(k++, all, speechFrames));
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 20, opacity: ip,
                    transform: `translateX(${(1 - ip) * 40}px)` }}>
                    <div style={{ width: 18, height: 18, borderRadius: "50%", background: col.color, flex: "none" }} />
                    <div style={{ fontSize: fit(item, 44, 26), fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{item}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      <div style={{ position: "absolute", left: W / 2 - 50, top: 520, width: 100, height: 100, borderRadius: "50%",
        background: C.ink, color: "#fff", fontSize: 38, fontWeight: 800, display: "grid", placeItems: "center",
        transform: `scale(${pop(frame, fps, 14)})` }}>vs</div>
    </>
  );
};

const Diagram: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = scene.items.length;
  const cx = W / 2, cy = 500, r = 150;
  const start = -Math.PI / 2 + Math.PI / n;
  const pos = (i: number) => {
    const a = start + (2 * Math.PI * i) / n;
    return { a, x: cx + 610 * Math.cos(a), y: cy + 270 * Math.sin(a) };
  };
  const centerP = pop(frame, fps);
  return (
    <>
      <Full>
        {scene.items.map((_, i) => {
          const { a, x, y } = pos(i);
          const at = revealFrame(i, n, speechFrames);
          const sx = cx + (r + 10) * Math.cos(a), sy = cy + (r + 10) * Math.sin(a);
          return <DrawPath key={i} d={`M${sx} ${sy}L${x} ${y}`} p={ease(frame, at - 8, at + 6)}
            color={PALETTE[i % PALETTE.length]} width={6} />;
        })}
      </Full>
      <div style={{ position: "absolute", left: cx - r, top: cy - r, width: 2 * r, height: 2 * r, borderRadius: "50%",
        background: C.card, border: `8px solid ${C.ink}`, display: "grid", placeItems: "center",
        transform: `scale(${centerP})` }}>
        <Icon name={scene.icon} size={170} />
      </div>
      <div style={{ position: "absolute", left: cx - 300, width: 600, top: cy + r + 18, ...centerText,
        opacity: centerP }}>
        <span style={{ background: C.ink, color: "#fff", padding: "8px 28px", borderRadius: 40,
          fontSize: fit(scene.heading, 46, 18), fontWeight: 800 }}>{scene.heading}</span>
      </div>
      {scene.items.map((item, i) => {
        const { x, y } = pos(i);
        const p = pop(frame, fps, revealFrame(i, n, speechFrames));
        const color = PALETTE[i % PALETTE.length];
        return (
          <div key={i} style={{ ...card, position: "absolute", left: x - 170, top: y - 46, width: 340,
            padding: "16px 18px", borderColor: color, opacity: p, transform: `scale(${0.5 + 0.5 * p})` }}>
            <div style={{ fontSize: fitAll(scene.items, 40, 15), fontWeight: 700, color: C.ink, ...centerText }}>{item}</div>
          </div>
        );
      })}
    </>
  );
};

const Quiz: React.FC<TemplateProps> = ({ scene, speechFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = scene.items.length;
  const gap = 40;
  const w = Math.min(480, (STAGE.right - STAGE.left - gap * (n - 1)) / n);
  const x0 = (W - (w * n + gap * (n - 1))) / 2;
  const revealAt = Math.round(speechFrames * 0.6);
  const reveal = ease(frame, revealAt, revealAt + 10);
  return (
    <>
      <Heading text={scene.heading} color={C.violet} />
      {scene.items.map((item, i) => {
        const p = pop(frame, fps, 14 + i * 6);
        const correct = i === scene.answer_index;
        const bg = correct ? `rgba(46,158,87,${0.16 * reveal})` : C.card;
        return (
          <div key={i} style={{ ...card, position: "absolute", left: x0 + i * (w + gap), top: 420, width: w,
            minHeight: 260, padding: "70px 24px 30px", display: "flex", alignItems: "center", justifyContent: "center",
            background: bg, borderColor: correct && reveal > 0 ? C.green : C.line,
            opacity: p * (correct ? 1 : 1 - 0.55 * reveal),
            transform: `scale(${(0.6 + 0.4 * p) * (correct ? 1 + 0.06 * reveal : 1)})` }}>
            <div style={{ position: "absolute", top: 18, left: 22, width: 64, height: 64, borderRadius: 18,
              background: correct && reveal > 0.5 ? C.green : C.violet, color: "#fff", fontSize: 36, fontWeight: 800,
              display: "grid", placeItems: "center" }}>
              {correct && reveal > 0.5 ? "✓" : String.fromCharCode(65 + i)}
            </div>
            <div style={{ fontSize: fitAll(scene.items, 46, w / 28), fontWeight: 700, color: C.ink, ...centerText }}>{item}</div>
          </div>
        );
      })}
    </>
  );
};

export const TEMPLATES: Record<TemplateName, React.FC<TemplateProps>> = {
  title: TitleCard,
  bullets: (p) => <ListScene {...p} checks={false} />,
  summary: (p) => <ListScene {...p} checks />,
  flow: Flow,
  cycle: Cycle,
  compare: Compare,
  diagram: Diagram,
  quiz: Quiz,
  graph: GraphScene,
  code: CodeScene,
};
