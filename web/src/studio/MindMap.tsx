import React, { useEffect, useRef, useState } from "react";
import type { StudioData } from "./types";
import { MindMapTree } from "./viewers";

type Props = { data: StudioData["mindmap"]; ask: (question: string) => void };

// Colours follow the app palette; branch colours come from Mermaid's cScale slots.
const THEME = {
  background: "#fbf7ef", primaryColor: "#dff2ee", primaryTextColor: "#1f2a44", lineColor: "#9aa3b5",
  fontFamily: "Figtree, 'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif",
  cScale0: "#178f7e", cScale1: "#e98a2e", cScale2: "#cf4a68", cScale3: "#3b6fb6", cScale4: "#7a5cc7", cScale5: "#5a8f3c",
  cScale6: "#178f7e", cScale7: "#e98a2e", cScale8: "#cf4a68", cScale9: "#3b6fb6", cScale10: "#7a5cc7", cScale11: "#5a8f3c",
  cScaleLabel0: "#ffffff", cScaleLabel1: "#ffffff", cScaleLabel2: "#ffffff", cScaleLabel3: "#ffffff", cScaleLabel4: "#ffffff", cScaleLabel5: "#ffffff",
  cScaleLabel6: "#ffffff", cScaleLabel7: "#ffffff", cScaleLabel8: "#ffffff", cScaleLabel9: "#ffffff", cScaleLabel10: "#ffffff", cScaleLabel11: "#ffffff",
};

let counter = 0;

/**
 * The mind map is Mermaid text written by the model (parsed and re-written by the backend) and drawn here, in the browser,
 * with no network. Mermaid is a separate chunk that loads only when a map is opened.
 */
export const MindMap: React.FC<Props> = ({ data, ask }) => {
  const [svg, setSvg] = useState("");
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [sel, setSel] = useState(data.root);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setSvg(""); setFailed(false); setZoom(1); setSel(data.root);
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base", themeVariables: THEME, mindmap: { padding: 14, maxNodeWidth: 170 } });
        const out = await mermaid.render(`mm-${++counter}`, data.mermaid);
        if (alive) setSvg(out.svg);
      })
      .catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, [data]);

  if (failed) return <MindMapTree data={data} ask={ask} />;

  const pick = (e: React.MouseEvent) => {
    const node = (e.target as Element).closest(".mindmap-node, .node");
    const text = node?.textContent?.trim();
    if (text) setSel(text);
  };

  return (
    <div className="mm-wrap">
      <div className="studio-actions">
        <button type="button" className="ghost small" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))} aria-label="Zoom out">−</button>
        <span className="mm-zoom" aria-live="polite">{Math.round(zoom * 100)}%</span>
        <button type="button" className="ghost small" onClick={() => setZoom((z) => Math.min(2.5, +(z + 0.15).toFixed(2)))} aria-label="Zoom in">+</button>
        <button type="button" className="ghost small" onClick={() => setZoom(1)}>Fit</button>
        <span className="muted">Click a branch to select it.</span>
      </div>
      <div className="mm-canvas" ref={box} onClick={pick}>
        {svg ? <div className="mm-svg" style={{ width: `${zoom * 100}%` }} dangerouslySetInnerHTML={{ __html: svg }} />
          : <p className="muted mm-loading" role="status">Drawing the map…</p>}
      </div>
      <div className="mm-sel">
        <span>Selected: <b>{sel}</b></span>
        <button type="button" className="go small" onClick={() => ask(`Explain "${sel}" in the context of ${data.root}.`)}>Ask the tutor about this</button>
      </div>
    </div>
  );
};
